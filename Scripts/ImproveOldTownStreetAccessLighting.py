"""Open usable narrow passages and move/aim street lamps without changing roads."""
import json
import math
import os
import shutil
import sys
import traceback
from copy import deepcopy
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
BASE = ROOT / 'Saved/CodexOutputs/HotelPolish_20261005'
WORK = ROOT / 'Saved/CodexOutputs/StreetAccessLighting_20261005'
TAG = 'StreetAccessLighting_20261005'
from PolishOldTownHotel import actor_state, shared_asset_hashes, sha
from PolishOldTownDetails import actor_bounds

LAMP_X = {1: 1625., 2: 3380., 3: 4460., 4: 5865., 5: 1575., 6: 3580., 7: 5075., 8: 8400., 9: 8400.}
LIGHT_IDS = (1, 2, 4, 5, 6, 7, 8, 9)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, value):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def verify_preservation(actors, build):
    baseline = read(WORK / 'PreservationBaseline.json')
    states = {a.get_actor_label(): actor_state(a) for a in actors}
    expected = baseline['expected_actors']
    errors = [name for name in set(states) | set(expected) if states.get(name) != expected.get(name)]
    assets = [p for p, h in baseline['shared_asset_sha256'].items() if sha(Path(p)) != h]
    result = {'passed': not errors and not assets, 'map_sha256': build['map_sha256'],
              'checked_actors': len(expected), 'actor_errors': errors, 'changed_shared_assets': assets,
              'checked_shared_assets': len(baseline['shared_asset_sha256']),
              'allowed_changed_actors': baseline['allowed_changed_actors'],
              'removed_actor_labels': baseline['removed_actor_labels'],
              'added_actor_labels': baseline['added_actor_labels']}
    write('PreservationAudit.json', result)
    assert result['passed'], 'Persisted state mismatch: {} actors / {} assets'.format(len(errors), len(assets))
    return result


def main():
    probe_only = os.environ.get('OTS_STREET_PROBE_ONLY') == '1'
    build = read(BASE / 'BuildReport.json')
    plan = read(BASE / 'RevisionPlan.json')
    target = build['target_level']
    mapfile = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    original_hash = sha(mapfile)
    if original_hash != build['map_sha256']:
        diff = read(WORK / 'ExternalEditComparison.json')
        assert diff['current_sha256'] == original_hash and diff['persisted_map_unchanged']
        assert not diff['added'] and not diff['changed'] and diff['removed'] == ['PointLight'], 'Inspect other external edits before rebasing.'
        write('InputRebaseReport.json', {'passed': True, 'previous_sha256': build['map_sha256'],
                                        'current_sha256': original_hash, 'preserved_external_deletions': ['PointLight']})
        build['map_sha256'] = original_hash
        build['actor_count'] = diff['actor_count']
        lighting = build['lighting_cleanup']
        lighting['allowed_scene_light_labels'].remove('PointLight')
        for key in ('light_expected_positions', 'light_expected_intensities'):
            lighting[key].pop('PointLight', None)
        lighting['preserved_user_lights'] = []
    assert not (WORK / 'AccessLightingApplied.json').exists(), 'Phase already applied; verify instead of rebuilding.'
    assert all(sha(Path(p)) == h for p, h in build['protected_map_sha256'].items())
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(target)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors = list(sub.get_all_level_actors())
    by = {a.get_actor_label(): a for a in actors}
    assert len(by) == len(actors) == build['actor_count']
    original_states = {name: actor_state(a) for name, a in by.items()}
    asset_hashes = shared_asset_hashes(actors)
    before = WORK / 'Before'
    before.mkdir(parents=True, exist_ok=True)
    for p in [mapfile] + [BASE / n for n in ('BuildReport.json', 'BuildingReport.json', 'RevisionPlan.json', 'HotelPlan.json')]:
        if not (before / p.name).exists():
            shutil.copy2(p, before / p.name)
    spec = {'source_map_sha256': original_hash, 'reopened_gaps': [], 'lamp_moves': [],
            'directional_lights': [], 'door_approaches': [], 'road_preservation': [],
            'prop_moves': [], 'utility_moves': [], 'wire_adjustments': [],
            'review_cameras': [], 'kept_party_wall_actors': [],
            'user_light_expected': 'PointLight' in by,
            'policy': 'Keep carriageway and existing sidewalks; assess passages by real clearance rather than close all narrow gaps.'}
    build['street_access_lighting'] = spec
    for s in plan['ground_surfaces']:
        if s.get('kind') == 'slab':
            spec['road_preservation'].append({'actor': s.get('actor', 'OTS_RoadRevision_' + s['name']),
                                             'world_min': s['world_min'], 'world_max': s['world_max']})
    for wall in plan['replacement_party_walls']:
        if wall['name'].startswith('AlleyPartyWall'):
            spec['kept_party_wall_actors'].append('OTS_RoadRevision_' + wall['name'])
    assert len(spec['kept_party_wall_actors']) == 4
    closures = deepcopy(plan['closed_service_gaps'])
    assert len(closures) == 5 and all(abs(r['world_max'][0] - r['world_min'][0] - 150.) < .01 for r in closures)
    removed = {'OTS_RoadRevision_' + r['name'] for r in closures}
    changed, added = set(), set()
    mesh = unreal.load_asset('/Game/Yastar/Meshes/hOUSE/SM_OTS_Enterable_FloorSlab')
    concrete = unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldConcrete')
    assert mesh and concrete
    reopened_legacy = []
    for r in closures:
        name = r['name'].replace('ClosedServiceGap', 'OpenServiceGap')
        wall_name = 'OTS_RoadRevision_' + r['name']
        assert sub.destroy_actor(by.pop(wall_name))
        x0, x1 = r['world_min'][0], r['world_max'][0]
        sign = 1 if 'North' in name else -1
        y0, y1 = sorted((sign * 530., sign * 1755.))
        low, high = [x0, y0, -9.], [x1, y1, 11.]
        center = [(low[i] + high[i]) / 2 for i in range(3)]
        a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*center), unreal.Rotator(), False)
        label = 'OTS_RoadRevision_' + name
        a.set_actor_label(label)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/RevisedRoads'))
        a.set_editor_property('tags', [unreal.Name('OTS_RoadRevision_20261003'), unreal.Name(TAG)])
        a.set_actor_scale3d(unreal.Vector(*[(high[i] - low[i]) / 100 for i in range(3)]))
        c = a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(mesh)
        c.set_material(0, concrete)
        c.set_collision_profile_name('BlockAll')
        added.add(label)
        by[label] = a
        route = [[(x0 + x1) / 2, sign * 440., 11.], [(x0 + x1) / 2, sign * 1915., 11.]]
        surface = {'name': name, 'actor': label, 'kind': 'slab', 'rect_xy': [x0, y0, x1, y1],
                   'world_min': low, 'world_max': high, 'surface_z_cm': 11., 'material_group': 'concrete',
                   'target_clear_width_cm': 120., 'width_axis': 0,
                   'clear_rect_xy': [x0 + 15., y0, x1 - 15., y1], 'purpose': 'open 150cm pedestrian passage to the rear lane'}
        plan['ground_surfaces'].append(surface)
        build['roads'].append({'actor': label, 'asset': mesh.get_path_name(), 'center_cm': center,
                               'size_cm': [high[i] - low[i] for i in range(3)]})
        spec['reopened_gaps'].append({'name': r['name'], 'removed_wall_actor': wall_name, 'actor': label,
                                     'world_min': low, 'world_max': high, 'width_cm': 150.,
                                     'route_points_cm': route, 'visual_clear_rect': [x0 + 25., y0, x1 - 25., y1]})
        reopened_legacy.append({'name': r['name'], 'former_closure_actor': wall_name,
                                'surface_actor': label, 'surface_world_min': low, 'surface_world_max': high, 'route': route})
    build['roads'] = [r for r in build['roads'] if r['actor'] not in removed]
    plan['replacement_party_walls'] = [r for r in plan['replacement_party_walls'] if 'OTS_RoadRevision_' + r['name'] not in removed]
    plan['closed_service_gaps'] = []
    plan['reopened_service_gaps'] = reopened_legacy
    plan['narrow_passage_policy'] = spec['policy']
    build['street_end_cleanup']['closed_service_gaps'] = []
    build['street_end_cleanup']['reopened_service_gaps'] = reopened_legacy
    build['street_end_cleanup']['road_surface_expectations'].extend(
        {'actor': r['surface_actor'], 'world_min': r['surface_world_min'], 'world_max': r['surface_world_max']} for r in reopened_legacy)
    # Turn the crossarm along the street so its insulators stay outside the
    # facade. Keep the opposite endpoints of its three terminal wires fixed.
    for name, a in sorted(by.items()):
        delta_x = (90. if name.startswith('OTS_UtilityPole_02_') else
                   -35. if name.startswith('OTS_P2Prop_WallUtilityCluster_03_') else 0.)
        if not delta_x:
            continue
        old = a.get_actor_location()
        position = [float(old.x + delta_x), float(old.y), float(old.z)]
        if name.startswith('OTS_UtilityPole_02_'):
            position[:2] = [4790. - (old.y + 500.), -500. + (old.x - 4700.)]
            rot = a.get_actor_rotation()
            a.set_actor_rotation(unreal.Rotator(pitch=rot.pitch, yaw=rot.yaw + 90., roll=rot.roll), False)
        a.set_actor_location(unreal.Vector(*position), False, False)
        changed.add(name)
        spec['utility_moves'].append({'actor': name, 'position_cm': position,
                                      'delta_cm': [position[0] - old.x, position[1] - old.y, 0.],
                                      'rotation': [a.get_actor_rotation().pitch, a.get_actor_rotation().yaw, a.get_actor_rotation().roll],
                                      'bounds': actor_bounds(a)})
    for suffix in (3, 6, 9):
        name = 'OTS_OverheadWire_{:02d}'.format(suffix)
        a = by[name]
        component = a.get_component_by_class(unreal.StaticMeshComponent)
        transform, bounds = component.get_world_transform(), component.static_mesh.get_bounds()
        endpoints = []
        for sign in (-1., 1.):
            point = transform.transform_location(unreal.Vector(bounds.origin.x + sign * bounds.box_extent.x,
                                                               bounds.origin.y, bounds.origin.z))
            endpoints.append([float(point.x), float(point.y), float(point.z)])
        endpoints.sort(key=lambda p: p[0])
        assert abs(endpoints[1][0] - 4700.) < .01
        endpoints[1][:2] = [4790. - (endpoints[1][1] + 500.), -500.]
        a.set_actor_location(unreal.Vector(*[(endpoints[0][i] + endpoints[1][i]) / 2 for i in range(3)]), False, False)
        a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*endpoints[0]), unreal.Vector(*endpoints[1])), False)
        scale = a.get_actor_scale3d()
        a.set_actor_scale3d(unreal.Vector(math.dist(*endpoints) / (2 * bounds.box_extent.x), scale.y, scale.z))
        changed.add(name)
        spec['wire_adjustments'].append({'actor': name, 'endpoints_cm': endpoints,
                                         'kept_first_endpoint': True, 'collision': 'NoCollision'})
    for i, x in LAMP_X.items():
        label = 'OTS_P2Prop_StreetLamp_{:02d}'.format(i)
        a = by[label]
        old = a.get_actor_location()
        pos = [x, float(old.y), float(old.z)]
        delta = [x - old.x, 0., 0.]
        if abs(delta[0]) > .01:
            changed.add(label)
        a.set_actor_location(unreal.Vector(*pos), False, False)
        build['lighting_cleanup']['lamp_positions'][label] = pos
        spec['lamp_moves'].append({'actor': label, 'position_cm': pos, 'delta_cm': delta,
                                   'render_base_radius_cm': 14.56, 'door_edge_min_distance_cm': 150.})
        if i not in LIGHT_IDS:
            continue
        name = 'OTS_Light_StreetLamp{:02d}'.format(i)
        old_light = by[name]
        old_component = old_light.get_component_by_class(unreal.PointLightComponent)
        assert old_component.get_class().get_name() == 'PointLightComponent'
        old_location = old_component.get_world_location()
        position = [old_location.x + delta[0], old_location.y, old_location.z]
        values = {k: old_component.get_editor_property(k) for k in
                  ('light_color', 'use_temperature', 'temperature', 'attenuation_radius', 'indirect_lighting_intensity', 'volumetric_scattering_intensity')}
        folder, tags = old_light.get_folder_path(), list(old_light.tags)
        assert sub.destroy_actor(old_light)
        light = sub.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(*position), unreal.Rotator(pitch=-90., yaw=0., roll=0.), False)
        light.set_actor_label(name)
        light.set_folder_path(folder)
        light.set_editor_property('tags', tags)
        component = light.get_component_by_class(unreal.SpotLightComponent)
        for k, v in values.items():
            component.set_editor_property(k, v)
        intensity = 190. if i in (8, 9) else 130.
        for k, v in {'intensity_units': unreal.LightUnits.LUMENS, 'intensity': intensity,
                     'inner_cone_angle': 35., 'outer_cone_angle': 55., 'use_inverse_squared_falloff': True,
                     'cast_shadows': True}.items():
            component.set_editor_property(k, v)
        by[name] = light
        changed.add(name)
        build['lighting_cleanup']['light_expected_positions'][name] = position
        build['lighting_cleanup']['light_expected_intensities'][name] = intensity
        spec['directional_lights'].append({'actor': name, 'position_cm': position, 'intensity_lm': intensity,
                                          'inner_cone_angle': 35., 'outer_cone_angle': 55.,
                                          'attenuation_radius_cm': float(values['attenuation_radius'])})
    build['lighting_cleanup']['light_expected_kinds'] = {name: 'spot' if name.startswith('OTS_Light_StreetLamp') else 'point'
                                                       for name in build['lighting_cleanup']['allowed_scene_light_labels']}
    for name, x, y in [('OTS_P2Prop_PlantPot_02', 3340., -1470.), ('OTS_P2Prop_PlantPot_03', 4840., -1630.)]:
        a = by[name]
        low, high = actor_bounds(a)
        old = a.get_actor_location()
        pos = [x, y, old.z - 1. - low[2]]
        a.set_actor_location(unreal.Vector(*pos), False, False)
        changed.add(name)
        spec['prop_moves'].append({'actor': name, 'position_cm': pos, 'floor_contact_z_cm': -1., 'bounds': actor_bounds(a)})
    for door in build['opening_components']['doors']:
        if door['kind'] != 'building_entry':
            continue
        p = door['entry_foot']
        if abs(abs(p[1]) - 530.) < .1:
            side = 'North' if p[1] > 0 else 'South'
            sign = 1 if p[1] > 0 else -1
            spec['door_approaches'].append({'name': door['actor'], 'side': side, 'coordinate_cm': p[0],
                                           'opening_width_cm': door['opening_width'],
                                           'route_points_cm': [[p[0], sign * 390., 11.], [p[0], sign * 485., 11.]]})
    spec['door_approaches'].extend([
        {'name': 'MainHomeDoubleDoor', 'side': 'North', 'coordinate_cm': 1169., 'opening_width_cm': 136.,
         'route_points_cm': [[1169., 390., 11.], [1169., 480., 11.]]},
        {'name': 'HotelEntry', 'side': 'East', 'coordinate_cm': 158., 'opening_width_cm': 140.,
         'route_points_cm': [[8400., 158., 11.], [8850., 158., 11.]]}])
    cameras = [('CAM_StreetAccess_HomeDoor', [1330., -80., 190.], [1320., 530., 180.], 80., 'temporary'),
               ('CAM_StreetAccess_SouthGap', [4460., -80., 235.], [4665., -1250., 95.], 75., 'temporary'),
               ('CAM_StreetAccess_NorthGap', [3570., 50., 235.], [3765., 1250., 95.], 75., 'temporary'),
               ('CAM_StreetAccess_NightStreet', [750., -50., 170.], [3700., 0., 190.], 80., 'street_only'),
               ('CAM_StreetAccess_Lamp', [1900., 0., 175.], [1575., 420., 210.], 80., 'street_only')]
    for name, position, look, fov, mode in cameras:
        rotation = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position), unreal.Vector(*look))
        camera = sub.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*position), rotation, False)
        camera.set_actor_label(name)
        camera.set_folder_path(unreal.Name('OldTownSchoolStreet/StreetAccess/ReviewCameras'))
        camera.set_editor_property('tags', [unreal.Name(TAG)])
        camera.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view', fov)
        added.add(name)
        spec['review_cameras'].append({'camera': name, 'lighting_mode': mode})
        build['hotel_openings_review_cameras'].append(name)
    current_actors = list(sub.get_all_level_actors())
    expected = {a.get_actor_label(): actor_state(a) for a in current_actors}
    assert set(expected) - set(original_states) == added
    assert set(original_states) - set(expected) == removed
    assert all(expected[name] == state for name, state in original_states.items() if name not in changed | removed)
    assert all(sha(Path(p)) == h for p, h in asset_hashes.items())
    assert sha(mapfile) == original_hash
    if probe_only:
        from AuditOldTownStreetAccessLighting import audit
        result = audit(world, current_actors, build, plan)
        write('ProbeAudit.json', result)
        assert result['passed'], 'Street access probe failed; see audit report.'
        write('ProbeSummary.json', {'passed': True, 'persisted_map_unchanged': True, 'map_sha256': original_hash,
                                    'statistics': result.get('statistics'), 'proposed_changes': spec})
        unreal.log('STREET_ACCESS_LIGHTING_PROBE_PASS')
        return
    # Physics probes ran in a separate helper. This fresh authoring helper
    # saves the same reviewed proposal without transient collision mutations.
    probe = read(WORK / 'ProbeSummary.json')
    assert probe['passed'] and probe['persisted_map_unchanged'] and probe['map_sha256'] == original_hash
    assert probe['proposed_changes'] == spec, 'Proposal differs from the successful physics probe'
    assert all(sha(Path(p)) == h for p, h in build['protected_map_sha256'].items())
    assert level.save_current_level()
    current = sha(mapfile)
    build['map_sha256'] = current
    build['actor_count'] = len(current_actors)
    for key in ('architecture_seal', 'detail_polish', 'hotel_openings', 'hotel_polish'):
        build[key]['map_sha256'] = current
    spec['map_sha256'] = current
    write('BuildReport.json', build)
    write('BuildingReport.json', build['buildings'])
    write('RevisionPlan.json', plan)
    write('HotelPlan.json', build['hotel_plan'])
    write('PreservationBaseline.json', {'expected_actors': expected, 'shared_asset_sha256': asset_hashes,
                                       'allowed_changed_actors': sorted(changed), 'removed_actor_labels': sorted(removed),
                                       'added_actor_labels': sorted(added), 'source_map_sha256': original_hash})
    write('AccessLightingApplied.json', {'passed': True, 'map_sha256': current, 'actor_count': len(current_actors),
                                       'reopened_gaps': 5, 'directional_lights': 8, 'fresh_audits_pending': True,
                                       'backup': str(before / mapfile.name)})
    unreal.log('STREET_ACCESS_LIGHTING_APPLIED ' + current)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('AccessApplyFailure.json', {'passed': False, 'traceback': traceback.format_exc()})
        raise
