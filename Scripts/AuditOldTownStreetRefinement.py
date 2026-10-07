"""Reload the saved refinement and verify its narrow edits and actual clearance.

This script never saves a world or asset. Historical hotel baselines remain
immutable; explicitly recorded street translations are projected into temporary
in-memory copies only while calling their original full audits.
"""
import json
import math
import sys
import traceback
from copy import deepcopy
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
from PolishOldTownHotel import actor_state, sha, xyz
from PolishOldTownDetails import actor_bounds
from OldTownAssetRelocation import normalize_paths
from AuditOldTownStreetAccessLighting import _probe
import AuditOldTownHotelArchitecture as architecture
import AuditOldTownHotelOperations as operations

WORK = ROOT / 'Saved/CodexOutputs/StreetRefinement_20261007'
HISTORICAL_STREET = ROOT / 'Saved/CodexOutputs/StreetAccessLighting_20261005'
ARCH_BASE = ROOT / 'Saved/CodexOutputs/HotelArchitecture_20261005/PreservationBaseline.json'
OPS_BASE = ROOT / 'Saved/CodexOutputs/HotelOperations_20261006/PreservationBaseline.json'
EPSILON = .002


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, value):
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def near(first, second, tolerance=.1):
    return len(first) == len(second) and all(abs(float(a) - float(b)) <= tolerance for a, b in zip(first, second))


def moved_state_contract(before, after, wire=False):
    """Allow transforms only, including UE's root world transform storage."""
    if before is None or after is None:
        return False, ['actor_missing']
    old, new = deepcopy(before), deepcopy(after)
    delta = [new['location'][i] - old['location'][i] for i in range(3)]
    violations = []
    old.pop('location'); new.pop('location')
    if wire:
        old.pop('rotation'); new.pop('rotation')
        old['scale'][0] = new['scale'][0]
    old_components = {c['name']: c for c in old['components']}
    new_components = {c['name']: c for c in new['components']}
    if set(old_components) != set(new_components):
        return False, ['component_set_changed']
    for name, previous in old_components.items():
        current = new_components[name]
        if previous['parent'] is None and current['parent'] is None:
            component_delta = [current['location'][i] - previous['location'][i] for i in range(3)]
            if not near(component_delta, delta, EPSILON):
                violations.append('root_location_delta:' + name)
            previous.pop('location'); current.pop('location')
            if wire:
                previous.pop('rotation'); current.pop('rotation')
                previous['scale'][0] = current['scale'][0]
    if old != new:
        violations.append('nonpermitted_actor_or_component_property_changed')
    return not violations, violations


def wire_ends(actor):
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    bounds = component.static_mesh.get_bounds()
    transform = component.get_world_transform()
    return sorted([xyz(transform.transform_location(unreal.Vector(
        bounds.origin.x + sign * bounds.box_extent.x, bounds.origin.y, bounds.origin.z)))
        for sign in (-1., 1.)], key=lambda point: point[0])


def property_value(component, key):
    value = component.get_editor_property(key)
    if key == 'light_color':
        return [int(getattr(value, channel)) for channel in ('r', 'g', 'b', 'a')]
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def hotel_audits(world, actors, build, baseline, allowed):
    """Keep the historic actor coverage and exact additions from both phases."""
    relocations = build.get('asset_relocations', [])
    derived_arch = normalize_paths(read(ARCH_BASE), relocations)
    derived_ops = normalize_paths(read(OPS_BASE), relocations)
    expected = baseline['expected_actors']
    for derived, key in ((derived_arch, 'preserved_actors'), (derived_ops, 'actors')):
        for label in allowed:
            if label in derived[key]:
                derived[key][label] = deepcopy(expected[label])
    write('DerivedHistoricalBaseline.json', dict(
        architecture=derived_arch, operations=derived_ops,
        source_baselines=[str(ARCH_BASE), str(OPS_BASE)],
        allowed_changed_labels=sorted(allowed), asset_relocations=relocations,
        note='Derived copies for this audit only; historical baseline files were not edited.'))
    old_arch_read, old_ops_read = architecture.read, operations.read
    old_arch_work, old_ops_work = architecture.WORK, operations.WORK
    architecture.WORK = WORK
    operations.WORK = WORK
    architecture.read = lambda path: derived_arch if path.name == 'PreservationBaseline.json' else old_arch_read(path)
    operations.read = lambda path: derived_ops if path.name == 'PreservationBaseline.json' else old_ops_read(path)
    try:
        result = operations.audit(world, actors, build)
        write('OperationsAudit.json', result)
        return result
    finally:
        architecture.read, operations.read = old_arch_read, old_ops_read
        architecture.WORK, operations.WORK = old_arch_work, old_ops_work


def audit(world, actors, build, baseline):
    actors = list(actors)
    states = {a.get_actor_label(): actor_state(a) for a in actors}
    by = {a.get_actor_label(): a for a in actors}
    refinement = build['street_refinement']
    expected = baseline['expected_actors']
    before = baseline['actors']
    allowed = set(refinement['allowed_changed_labels'])
    added = set(refinement['new_actor_labels'])
    wires = {row['actor'] for row in refinement.get('wire_adjustments', [])}
    report = dict(passed=False, target_level=build['target_level'], map_sha256=build['map_sha256'],
                  checks=[], errors=[], routes=[], statistics={}, preservation_difference_samples=[])

    def check(name, passed, **details):
        report['checks'].append(dict(name=name, passed=bool(passed), **details))
        if not passed:
            report['errors'].append(name)

    def section(name, callback):
        try:
            callback()
        except Exception:
            check(name + ':exception', False, traceback=traceback.format_exc(limit=5))

    check('target_world', world is not None and world.get_path_name().startswith(build['target_level'] + '.'))
    check('unique_actor_labels_and_count', len(states) == len(actors) == build['actor_count'])
    check('allowed_changes_only_existing_objects', allowed <= set(before))
    check('exact_new_actor_labels', set(states) - set(before) == added, actual=sorted(set(states) - set(before)), expected=sorted(added))
    check('no_existing_actor_removed', set(before) <= set(states), missing=sorted(set(before) - set(states)))
    check('expected_snapshot_contains_exact_current_set', set(expected) == set(states))

    def preservation():
        mismatches = [name for name in sorted(set(states) | set(expected)) if states.get(name) != expected.get(name)]
        check('fresh_reload_matches_saved_actor_snapshot', not mismatches, checked=len(expected), changed=mismatches[:20])
        for name in mismatches[:3]:
            report['preservation_difference_samples'].append(dict(actor=name, expected=expected.get(name), actual=states.get(name)))
        unchanged = set(before) - allowed
        modified = [name for name in sorted(unchanged) if states.get(name) != before[name]]
        check('unlisted_existing_actors_unchanged', not modified, checked=len(unchanged), changed=modified[:20])
        for name in sorted(allowed):
            good, violations = moved_state_contract(before.get(name), states.get(name), name in wires)
            check('restricted_transform_edit:' + name, good, permitted='location, rotation and X scale' if name in wires else 'translation only', violations=violations)
        hashes = baseline['shared_asset_sha256']
        modified_assets = [path for path, digest in hashes.items() if not Path(path).is_file() or sha(Path(path)) != digest]
        check('shared_assets_unchanged', not modified_assets, checked=len(hashes), changed=modified_assets)
        new_hashes=build.get('new_asset_sha256',{})
        changed_new=[p for p,h in new_hashes.items() if not Path(p).is_file() or sha(Path(p))!=h]
        check('new_sign_asset_files_match', len(new_hashes)==18 and not changed_new, checked=len(new_hashes),changed=changed_new)
        protected = [path for path, digest in build['protected_map_sha256'].items() if not Path(path).is_file() or sha(Path(path)) != digest]
        check('protected_maps_unchanged', not protected, changed=protected)
        check('source_map_hash_matches_baseline', baseline['source_map_sha256'] == build['source_map_sha256'])

    section('preservation', preservation)
    old_street = read(HISTORICAL_STREET / 'BuildReport.json')['street_access_lighting']

    def paving():
        required = {'OTS_RoadRevision_MainRoad', 'OTS_RoadRevision_EastCrossRoad',
                    'OTS_RoadRevision_MainWalkNorth', 'OTS_RoadRevision_MainWalkSouth',
                    'OTS_RoadRevision_EastBoundaryWalk'} | {row['actor'] for row in old_street['reopened_gaps']}
        check('road_walk_and_five_gap_actors_present', required <= set(by), missing=sorted(required - set(by)))
        rows = [row for row in old_street['road_preservation'] if row['actor'] in before]
        rows += [row for row in old_street['reopened_gaps']]
        for row in rows:
            actor = by.get(row['actor'])
            actual = actor_bounds(actor) if actor else None
            good = actual is not None and near(actual[0], row['world_min'], .1) and near(actual[1], row['world_max'], .1)
            check('paving_geometry_preserved:' + row['actor'], good, actual=actual, expected=[row['world_min'], row['world_max']])
        for label, axis, width in [('OTS_RoadRevision_MainRoad', 1, 700.), ('OTS_RoadRevision_EastCrossRoad', 0, 700.),
                                   ('OTS_RoadRevision_MainWalkNorth', 1, 180.), ('OTS_RoadRevision_MainWalkSouth', 1, 180.),
                                   ('OTS_RoadRevision_EastBoundaryWalk', 0, 180.)]:
            bounds = actor_bounds(by[label])
            check('paving_width:' + label, abs(bounds[1][axis] - bounds[0][axis] - width) < .1, width_cm=bounds[1][axis] - bounds[0][axis])
        remaining_closures = [row['removed_wall_actor'] for row in old_street['reopened_gaps'] if row['removed_wall_actor'] in by]
        check('five_passages_remain_open', len(old_street['reopened_gaps']) == 5 and not remaining_closures, remaining_closures=remaining_closures)

    section('paving', paving)

    def lamp_clearance():
        moves = refinement['lamp_moves']
        expected_lamps = {'OTS_P2Prop_StreetLamp_' + str(i).zfill(2) for i in range(1, 10)}
        check('nine_existing_lamp_posts', len(moves) == 9 and {row['actor'] for row in moves} == expected_lamps)
        roads = [actor_bounds(by[label]) for label in ('OTS_RoadRevision_MainRoad', 'OTS_RoadRevision_EastCrossRoad')]
        for row in moves:
            label, radius = row['actor'], float(row['base_radius_cm'])
            position = xyz(by[label].get_actor_location())
            axis = int(row['facade_plane_axis'])
            clearance = abs(position[axis] - float(row['facade_plane_cm'])) - radius
            check('lamp_recorded_position:' + label, near(position, row['position_cm']) and near(before[label]['location'], row['before_position_cm']) and abs(radius - 14.56) < .01,
                  actual_cm=position, expected_cm=row['position_cm'], base_radius_cm=radius)
            check('lamp_detached_from_facade:' + label, clearance >= 120. - .01, facade_clearance_cm=clearance)
            hits = [bounds for bounds in roads if position[0] - radius < bounds[1][0] - .01 and position[0] + radius > bounds[0][0] + .01
                    and position[1] - radius < bounds[1][1] - .01 and position[1] + radius > bounds[0][1] + .01]
            edge_axis = int(row['road_edge_axis'])
            check('lamp_base_fully_outside_carriageways:' + label, not hits and abs(position[edge_axis] - row['road_edge_cm']) - radius >= -.01,
                  road_overlaps=hits, road_edge_clearance_cm=abs(position[edge_axis] - row['road_edge_cm']) - radius)
            side = 'East' if position[0] >= 8250. else ('North' if position[1] > 0. else 'South')
            along = 1 if side == 'East' else 0
            doors = [door for door in old_street['door_approaches'] if door['side'] == side]
            blocked = [door['name'] for door in doors if abs(position[along] - door['coordinate_cm']) - door['opening_width_cm'] * .5 - radius < 149.95]
            check('lamp_clear_of_entry_fronts:' + label, not blocked, blocked_entries=blocked)
            gaps = [gap['name'] for gap in old_street['reopened_gaps'] if ('North' if gap['world_min'][1] > 0. else 'South') == side
                    and position[0] - radius < gap['world_max'][0] and position[0] + radius > gap['world_min'][0]]
            check('lamp_clear_of_passage_mouths:' + label, not gaps, blocked_gaps=gaps)

    section('lamp_clearance', lamp_clearance)

    def lighting():
        rows = refinement['directional_lights']
        labels = {row['actor'] for row in rows}
        street = {name for name, actor in by.items() if name.startswith('OTS_Light_StreetLamp') and actor.get_components_by_class(unreal.LightComponentBase)}
        check('eight_existing_directional_street_lights', len(rows) == len(labels) == 8 and street == labels)
        old_light_labels = {name for name, state in before.items() if any(component['class'].rsplit('.', 1)[-1].endswith('LightComponent') for component in state['components'])}
        actual_light_labels = {name for name, actor in by.items() if actor.get_components_by_class(unreal.LightComponentBase)}
        check('no_added_or_removed_light_actors', old_light_labels == actual_light_labels, added=sorted(actual_light_labels - old_light_labels), removed=sorted(old_light_labels - actual_light_labels))
        for row in rows:
            label = row['actor']
            components = by[label].get_components_by_class(unreal.LightComponentBase)
            valid = len(components) == 1 and isinstance(components[0], unreal.SpotLightComponent)
            check('one_spot_component:' + label, valid)
            if not valid:
                continue
            component = components[0]
            check('spot_position:' + label, near(xyz(component.get_world_location()), row['position_cm']))
            check('spot_points_down:' + label, near(xyz(component.get_forward_vector()), [0., 0., -1.], .001))
            check('spot_single_direction_cones:' + label, abs(component.get_editor_property('inner_cone_angle') - row['inner_cone_angle']) < .01
                  and abs(component.get_editor_property('outer_cone_angle') - row['outer_cone_angle']) < .01
                  and row['inner_cone_angle'] == 35. and row['outer_cone_angle'] == 55.)
            check('spot_photometry_preserved:' + label, abs(component.get_editor_property('intensity') - row['intensity_lm']) < .01
                  and abs(component.get_editor_property('attenuation_radius') - row['attenuation_radius_cm']) < .1
                  and component.get_editor_property('intensity_units').value == unreal.LightUnits.LUMENS.value
                  and bool(component.get_editor_property('cast_shadows')) and bool(component.get_editor_property('use_inverse_squared_falloff')))
            properties = row.get('before_physical_values', {})
            check('spot_original_physical_properties_recorded:' + label, bool(properties))
            for key, value in properties.items():
                current = property_value(component, key)
                good = abs(current - value) < .001 if isinstance(current, (int, float)) and not isinstance(current, bool) and isinstance(value, (int, float)) else current == value
                check('spot_unmodified_property:' + label + ':' + key, good, expected=value, actual=current)

    section('lighting', lighting)

    def poles_and_wires():
        for row in refinement.get('pole_moves', []):
            label = row['actor']
            check('utility_part_position:' + label, near(xyz(by[label].get_actor_location()), row['position_cm']))
        for row in refinement.get('wire_adjustments', []):
            label = row['actor']
            actual = wire_ends(by[label])
            check('wire_endpoint_geometry:' + label, all(near(actual[i], row['endpoints_cm'][i], .02) for i in (0, 1)), actual=actual, expected=row['endpoints_cm'])
            check('wire_opposite_endpoint_fixed:' + label, near(actual[0], row['fixed_first_endpoint_before'], .02))
            component = by[label].get_component_by_class(unreal.StaticMeshComponent)
            check('wire_collision_unchanged:' + label, str(component.get_collision_profile_name()) == 'NoCollision')

    section('poles_and_wires', poles_and_wires)

    def signs():
        rows = refinement['new_signs']
        check('nine_durable_operation_signs', len(rows) == 9 and len({row['actor'] for row in rows}) == 9)
        for row in rows:
            label = row['actor']
            actor = by.get(label)
            component = actor.get_component_by_class(unreal.StaticMeshComponent) if actor else None
            valid = isinstance(actor, unreal.StaticMeshActor) and component is not None and component.static_mesh is not None
            check('sign_static_mesh_actor:' + label, valid)
            if not valid:
                continue
            rotation = actor.get_actor_rotation()
            check('sign_transform:' + label, near(xyz(actor.get_actor_location()), row['position_cm'])
                  and near([rotation.pitch, rotation.yaw, rotation.roll], row['rotation'], .01)
                  and near(xyz(actor.get_actor_scale3d()), [row['size_cm'][0] / 100., row['size_cm'][1] / 100., 1.], .001))
            check('sign_plane_and_material:' + label, component.static_mesh.get_path_name() == row['asset']
                  and component.get_material(0) is not None and component.get_material(0).get_path_name() == row['material_asset'])
            check('sign_stock_plane_v_orientation_corrected:'+label,unreal.EditorAssetLibrary.get_metadata_tag(
                component.get_material(0),'StreetRefinement_20261007_UVVFlipped')=='true')
            check('sign_collision_disabled:' + label, component.get_collision_enabled().value == unreal.CollisionEnabled.NO_COLLISION.value
                  and str(component.get_collision_profile_name()) == 'NoCollision')
            check('sign_faces_planned_direction:' + label, near(xyz(component.get_up_vector()), row['normal_world'], .001))
            texture = unreal.load_asset(row['texture_asset'])
            check('sign_text_and_texture:' + label, isinstance(row.get('text'), str) and bool(row['text'].strip()) and isinstance(texture, unreal.Texture2D))
            if row.get('text_metadata_key'):
                check('sign_text_texture_provenance:' + label, unreal.EditorAssetLibrary.get_metadata_tag(texture, row['text_metadata_key']) == row['text'])
            source=ROOT/'SourceArt/OldTownStreetRefinement_20261007'/row['source_file']
            check('sign_source_texture_fingerprint:'+label,sha(source)==row['source_sha256'] and
                  unreal.EditorAssetLibrary.get_metadata_tag(texture,'StreetRefinement_20261007_SourceSHA256')==row['source_sha256'])

    section('signs', signs)

    def routes():
        control = by.get('OTS_RoadRevision_AlleyPartyWallNorthWest')
        if control:
            from ValidateEnterableStreet import capsule_blocking_components
            center, _ = control.get_actor_bounds(False)
            detected = capsule_blocking_components(world, [center.x, center.y, center.z - 92.])
            check('registered_collision_wall_negative_control', any(component.get_owner() == control for component in detected))
        else:
            check('registered_collision_wall_negative_control', False, reason='Expected retained party wall is missing')
        planned = list(refinement['route_specs'])
        planned += [dict(id='LampWalk_' + row['actor'], points=row['walk_route']) for row in refinement['lamp_moves']]
        for gap in old_street['reopened_gaps']:
            for offset in (-25., 0., 25.):
                planned.append(dict(id='RetainedGap_' + gap['name'] + '_' + str(int(offset)),
                                    points=[[point[0] + offset, point[1], point[2]] for point in gap['route_points_cm']], support_tolerance_cm=.5))
        check('route_ids_are_unique', len({row['id'] for row in planned}) == len(planned))
        check('planned_door_and_walk_routes_present', len(refinement['route_specs']) > 0)
        for row in planned:
            result = _probe(world, row['points'], support_tolerance=float(row.get('support_tolerance_cm', 10.05)))
            report['routes'].append(dict(id=row['id'], points_cm=row['points'], result=result))
            check('physical_capsule_route:' + row['id'], result['passed'], sample_count=result['sample_count'], failures=result['failures'][:3])

    section('physical_routes', routes)

    def hotel():
        result = hotel_audits(world, actors, build, baseline, allowed)
        check('full_hotel_architecture_operations_and_circulation', result['passed'], errors=result['errors'][:12])
        report['hotel_statistics'] = result['statistics']

    section('full_hotel_audits', hotel)
    report['statistics'] = dict(checks=len(report['checks']), actors=len(actors), preserved_existing_actors=len(before),
                                allowed_changed_actors=len(allowed), new_actors=len(added), lamps=len(refinement['lamp_moves']),
                                directional_lights=len(refinement['directional_lights']), signs=len(refinement['new_signs']),
                                route_samples=sum(row['result']['sample_count'] for row in report['routes']))
    report['passed'] = not report['errors']
    return report


def main():
    build = read(WORK / 'BuildReport.json')
    baseline = read(WORK / 'PreservationBaseline.json')
    mapfile = ROOT / ('Content/' + build['target_level'].removeprefix('/Game/') + '.umap')
    digest = sha(mapfile)
    assert digest == build['map_sha256'], 'The saved street differs from the refinement report.'
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    # Collision registration can reset named profiles; this helper restores them.
    operations.refresh(actors)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    report = audit(world, actors, build, baseline)
    if sha(mapfile) != digest:
        report['checks'].append(dict(name='read_only_audit_did_not_change_saved_map', passed=False))
        report['errors'].append('read_only_audit_did_not_change_saved_map')
        report['passed'] = False
    else:
        report['checks'].append(dict(name='read_only_audit_did_not_change_saved_map', passed=True))
    write('StreetRefinementAudit.json', report)
    assert report['passed'], report['errors'][:20]
    unreal.log('STREET_REFINEMENT_AUDIT_PASS ' + str(report['statistics']))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('AuditFailure.json', dict(passed=False, traceback=traceback.format_exc()))
        raise
