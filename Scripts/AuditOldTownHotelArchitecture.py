"""Fresh-world architecture, supported circulation and street preservation."""
import json
import math
import sys
import traceback
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
from PolishOldTownHotel import actor_state, sha, xyz
from PolishOldTownDetails import actor_bounds
from OldTownHotelArchitecturePlan import validate_plan
from OldTownHotelValidation import route_probe
from AuditOldTownRevision import _support, _step_probe, _route_samples, _capsule_components
from ValidateEnterableStreet import refresh_world_collision
from OldTownAssetRelocation import normalize_paths
WORK = ROOT / 'Saved/CodexOutputs/HotelArchitecture_20261005'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, value):
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def audit(world, actors, build):
    plan = build['hotel_architecture']
    by = {a.get_actor_label(): a for a in actors}
    result = {'passed': False, 'target_level': build['target_level'], 'checks': [], 'errors': [],
              'routes': [], 'stairs': [], 'map_sha256': build['map_sha256']}

    def check(name, passed, **details):
        result['checks'].append(dict(name=name, passed=bool(passed), **details))
        if not passed:
            result['errors'].append(name)

    check('target_world', world.get_path_name().startswith(build['target_level'] + '.'))
    check('unique_actor_labels', len(by) == len(actors) == build['actor_count'])
    pv = validate_plan(plan)
    check('measured_program', pv['passed'], errors=pv['errors'])
    check('room_labels', {r['room_id'] for r in plan['room_labels']} == {r['id'] for r in plan['rooms']})
    boxes = plan['placed_boxes'] + [c for p in plan['placed_props'] for c in p['colliders']]
    box_diagnostics = []
    for row in boxes:
        a = by.get(row['actor'])
        good = a is not None
        if good:
            c = a.get_component_by_class(unreal.StaticMeshComponent)
            bounds = actor_bounds(a)
            error = max(abs(bounds[j][i] - row[k][i]) for j,k in enumerate(('world_min','world_max')) for i in range(3))
            good = error < .12 and c.static_mesh.get_path_name() == row['asset']
            good = good and c.get_material(0).get_path_name() == row['material_asset']
            good = good and str(c.get_collision_profile_name()) == ('BlockAll' if row['collision'] else 'NoCollision')
        if not good and len(box_diagnostics)<3:
            box_diagnostics.append(dict(id=row['id'],actual_bounds=bounds,expected_bounds=[row['world_min'],row['world_max']],
                profile=str(c.get_collision_profile_name()),material=c.get_material(0).get_path_name(),expected_material=row['material_asset']))
        check('box:' + row['id'], good)
    result['box_diagnostics']=box_diagnostics
    for row in plan['placed_props']:
        a = by.get(row['actor'])
        good = a is not None
        if good:
            c = a.get_component_by_class(unreal.StaticMeshComponent)
            good = c.static_mesh.get_path_name() == row['asset'] and math.dist(xyz(a.get_actor_location()),row['position_cm']) < .1
            good = good and abs((a.get_actor_rotation().yaw - row['yaw'] + 180.) % 360. - 180.) < .1
            good = good and str(c.get_collision_profile_name()) == 'NoCollision'
        check('fixture:' + row['id'], good)
    for row in plan['placed_doors'] + plan['placed_windows']:
        a = by.get(row['actor'])
        good = a is not None
        if good:
            cs = {c.get_name(): c for c in a.get_components_by_class(unreal.SceneComponent)}
            good = a.get_class().get_path_name() == row['blueprint'] + '.' + row['blueprint'].rsplit('/',1)[1] + '_C'
            good = set(cs) == {c['name'] for c in row['components']}
            good = good and math.dist(xyz(a.get_actor_location()),row['actor_position_cm']) < .1
            good = good and abs((a.get_actor_rotation().yaw-row['yaw']+180.)%360.-180.) < .1
            for spec in row['components']:
                c = cs.get(spec['name'])
                if c is None:
                    good = False
                    continue
                if spec['parent'] is None:
                    continue
                good = good and math.dist(xyz(c.get_editor_property('relative_location')), spec['relative_location']) < .1
                rot = c.get_editor_property('relative_rotation')
                good = good and max(abs(float(getattr(rot, key)) - spec['relative_rotation'][i]) for i,key in enumerate(('pitch','yaw','roll'))) < .1
                if spec.get('asset'):
                    good = good and c.static_mesh.get_path_name().split('.')[0] == spec['asset'].split('.')[0]
                    good = good and c.get_collision_enabled().value == getattr(unreal.CollisionEnabled, spec['collision']).value
        if not good and 'opening_diagnostic' not in result:
            result['opening_diagnostic']=dict(id=row['id'],actual=[dict(name=n,location=xyz(c.get_editor_property('relative_location')),
                rotation=str(c.get_editor_property('relative_rotation')),collision=str(c.get_collision_enabled()) if isinstance(c,unreal.PrimitiveComponent) else None) for n,c in cs.items()],expected=row['components'])
        check('opening:' + row['id'], good)
    for row in plan['room_labels']:
        a = by.get(row['number_actor'])
        check('number:' + row['room_id'], a is not None and row['plate_actor'] in by and
              a.get_component_by_class(unreal.StaticMeshComponent).static_mesh.get_path_name() == row['asset'])
    for row in plan['imported_assets']:
        mesh=unreal.load_asset(row['asset'])
        source=ROOT/'SourceArt/OldTownHotelArchitecture_20261005'/row['file']
        check('source_asset:'+row['name'], mesh is not None and sha(source)==row['source_sha256'] and
              unreal.EditorAssetLibrary.get_metadata_tag(mesh,'HotelArchitecture_20261005_SourceSHA256')==row['source_sha256'])
    for row in plan.get('interior_lights', []):
        a = by.get(row['actor'])
        c = a.get_component_by_class(unreal.RectLightComponent) if a else None
        check('surviving_fixture:' + row['id'], c is not None and
              abs(float(c.get_editor_property('intensity')) - row['intensity_lm']) < .1 and
              abs(a.get_actor_rotation().pitch + 90.) < .1)
    for row in plan['routes']:
        probe = route_probe(world, row['points'])
        result['routes'].append(dict(id=row['id'], result=probe))
        check('route:' + row['id'], probe['passed'], sample_count=probe['sample_count'], failures=probe['failures'][:3])
    for row in plan['staircases']:
        samples, failures, previous = [], [], None
        for foot in _route_samples(row['foot_waypoints'], step=14.):
            z = _support(world, foot, above=40., below=40.)
            probe = _step_probe(world, foot[:2]+[z], 34., 180.) if z is not None else {'passed':False}
            good = z is not None and abs(z-foot[2]) < 23 and probe['passed'] and (previous is None or abs(z-previous) < 45.1)
            item = dict(planned_foot_cm=foot, support_z_cm=z, passed=good, probe=probe)
            samples.append(item)
            if not good:
                failures.append(item)
            if z is not None:
                previous = z
        result['stairs'].append(dict(id=row['id'], passed=not failures, samples=samples, failures=failures))
        check('stair:' + row['id'], not failures, sample_count=len(samples), failures=failures[:3])
    for row in plan['placed_doors']:
        a=by[row['actor']]
        sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        foot=[row['position_cm'][0],row['position_cm'][1],row['position_cm'][2]+50000.]
        clone=sub.spawn_actor_from_class(a.get_class(),unreal.Vector(*foot),a.get_actor_rotation(),False)
        clone.set_actor_label('OTS_TransientDoorTest_'+row['id'])
        hinge=next(c for c in clone.get_components_by_class(unreal.SceneComponent) if c.get_name()=='DoorHinge')
        try:
            hinge.set_relative_rotation(unreal.Rotator(pitch=0,yaw=0,roll=0),False,True)
            blockers=_capsule_components(world,foot,34.,180.)
            check('closed_door_blocks:'+row['id'],any(c.get_owner()==clone and c.get_name()=='LeafCollision' for c in blockers))
        finally:
            check('temporary_door_removed:'+row['id'],sub.destroy_actor(clone))
    baseline = read(WORK / 'PreservationBaseline.json')
    changed = [name for name,state in baseline['preserved_actors'].items()
               if name not in by or actor_state(by[name]) != normalize_paths(state,build.get('asset_relocations',[]))]
    added = set(by) - set(baseline['preserved_actors'])
    check('preserved_street_actors', not changed, checked=len(baseline['preserved_actors']), changed=changed[:20])
    if changed:
        result['preservation_difference_sample']=dict(actor=changed[0],before=baseline['preserved_actors'][changed[0]],after=actor_state(by[changed[0]]) if changed[0] in by else None)
    check('exact_added_actor_set', added == set(plan['new_actor_labels']),
          unexpected=sorted(added - set(plan['new_actor_labels'])), missing=sorted(set(plan['new_actor_labels']) - added))
    check('old_hotel_removed', not (set(plan['removed_actor_labels']) & set(by)))
    changed_assets = [p for p,h in baseline['shared_asset_sha256'].items() if sha(Path(p)) != h]
    check('shared_assets_unchanged', not changed_assets, checked=len(baseline['shared_asset_sha256']), changed=changed_assets)
    protected = [p for p,h in build['protected_map_sha256'].items() if sha(Path(p)) != h]
    check('protected_maps_unchanged', not protected, changed=protected)
    result['passed'] = not result['errors']
    result['statistics'] = dict(checks=len(result['checks']), rooms=len(plan['rooms']),
        route_samples=sum(r['result']['sample_count'] for r in result['routes']),
        stair_samples=sum(len(r['samples']) for r in result['stairs']), preserved_actors=len(baseline['preserved_actors']))
    return result


def main():
    build = read(WORK / 'BuildReport.json')
    mapfile = ROOT / ('Content/' + build['target_level'].removeprefix('/Game/') + '.umap')
    assert sha(mapfile) == build['map_sha256']
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    profiles = [(c,str(c.get_collision_profile_name())) for a in actors for c in a.get_components_by_class(unreal.PrimitiveComponent)]
    refresh_world_collision(actors)
    for c,profile in profiles:
        if profile!='Custom' and str(c.get_collision_profile_name())!=profile:
            c.set_collision_profile_name(profile)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    report = audit(world, actors, build)
    write('ArchitectureAudit.json', report)
    assert report['passed'], report['errors'][:20]
    unreal.log('HOTEL_ARCHITECTURE_AUDIT_PASS ' + str(report['statistics']))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('AuditFailure.json', {'passed':False, 'traceback':traceback.format_exc()})
        raise
