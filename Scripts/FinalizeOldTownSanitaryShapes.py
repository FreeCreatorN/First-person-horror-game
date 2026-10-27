"""Validate and publish the isolated hotel hollow-bowl and rounded-faucet refinement.

No Unreal process is started and no map or asset is modified by this script.
Four fixture closeups are current; earlier basin and hotel images are explicitly
historical. Use --check-only for the complete read-only publication preflight.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/SanitaryShapes_20261011'
SOURCE = ROOT / 'Saved/CodexOutputs/SanitaryFixtures_20261011'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
SOURCE_SHA = '412d31cf4b23b5ee16cb3b9d1238dae4c1f7a990a19d6db642cf21611f7349f9'
NEW_CAMERAS = {'CAM_Shape_ToiletInterior201', 'CAM_Shape_ToiletFullPublic'}
CAMERAS = NEW_CAMERAS | {'CAM_Fixture_FaucetPublicWC', 'CAM_Basin_Guest201'}
BOUND_FIELDS = {'world_min', 'world_max', 'bounds', 'world_bounds_cm'}
sys.path.insert(0, str(ROOT / 'Scripts'))
import FinalizeOldTownHotelDetails as hotel
import FinalizeOldTownStreetRefinement as lifecycle
import FinalizeOldTownSurfaceRepair as surfaces
import OldTownSanitaryShapePlan as recipe


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.tmp')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(path)


def hashes(values, label):
    require(bool(values), label + ' manifest is empty.')
    for name, digest in values.items():
        require(Path(name).is_file() and sha(name) == digest, label + ' changed: ' + name)
    return len(values)


def same_recipe(actual, expected):
    """Only tolerate cross-runtime roundoff, never indices or structure drift."""
    if isinstance(expected, float):
        return (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                and math.isfinite(actual) and abs(actual - expected) <= 1.e-10)
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys() == expected.keys()
                and all(same_recipe(actual[k], expected[k]) for k in expected))
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(same_recipe(a, e) for a, e in zip(actual, expected)))
    return type(actual) is type(expected) and actual == expected


def assets_by_key(optimization):
    rows = optimization.get('new_assets', [])
    require(len(rows) == 2 and {r.get('asset_key') for r in rows} == {'Toilet', 'Washbasin'},
            'The two declared fixture clones are missing, duplicated or ambiguous.')
    result = {r['asset_key']: r for r in rows}
    generated = (ROOT / 'Content/CodexGenerated').resolve()
    for row in rows:
        require(all(row.get(k) for k in ('asset', 'file', 'sha256', 'source', 'source_file', 'source_sha256')),
                'Fixture asset/source hash evidence is incomplete.')
        asset = row['asset']
        require(asset.startswith('/Game/CodexGenerated/') and '.' in asset
                and Path(row['file']).resolve().is_relative_to(generated)
                and Path(row['file']).resolve() == (ROOT / ('Content/' + asset.split('.')[0].removeprefix('/Game/') + '.uasset')).resolve()
                and sha(row['file']) == row['sha256'], 'Fixture clone identity/hash differs: ' + asset)
        require(sha(row['source_file']) == row['source_sha256'],
                'The original fixture source asset changed: ' + row['source_file'])
        expected_removed = {p['name'] for p in recipe.source_removal_specs()
                            if p['fixture'] == row['asset_key']}
        require(len(row.get('removed_part_names', [])) == len(expected_removed)
                and set(row.get('removed_part_names', [])) == expected_removed,
                'The replaced source fixture components differ: ' + row['asset_key'])
        require(row.get('collision_signature') is not None
                and row.get('materials') and isinstance(row.get('shape_recipe'), dict)
                and row['shape_recipe'].get('schema') == recipe.SCHEMA
                and row['shape_recipe'].get('pieces') and row['shape_recipe'].get('removals'),
                'The shape/material/collision recipe evidence is missing: ' + row['asset_key'])
        require(row.get('render_indices_reversed') is True,
                'The new triangle indices do not declare the verified UE winding convention: ' + row['asset_key'])
        expected_recipe = json.loads(json.dumps(dict(schema=recipe.SCHEMA,
            pieces=[p for p in recipe.build_pieces() if p['fixture'] == row['asset_key']],
            removals=[r for r in recipe.source_removal_specs() if r['fixture'] == row['asset_key']])))
        require(same_recipe(row['shape_recipe'], expected_recipe),
                'The immutable shape recipe differs from the declared new geometry: ' + row['asset_key'])
    require(len({r['file'] for r in rows}) == len({r['asset'] for r in rows}) == 2,
            'The two fixture clones share an asset/file identity.')
    return result


def verify_recipe_file(optimization, assets):
    """The source-art recipe is immutable evidence; it never changes old assets."""
    path = Path(optimization.get('recipe_file', ''))
    require(path.is_file() and path.name == 'Recipe.json'
            and path.resolve().is_relative_to((ROOT / 'SourceArt').resolve())
            and sha(path) == optimization.get('recipe_sha256'),
            'The frozen independent source-art recipe/hash is missing or changed.')
    require(recipe.audit_recipe().get('passed') is True,
            'The declared pure geometry recipe no longer produces valid closed shapes.')
    return dict(passed=True, source_art_recipe=str(path), source_art_recipe_sha256=sha(path),
                recipe_schema=recipe.SCHEMA,
                independently_replaced_components={key: row['removed_part_names']
                                                   for key, row in assets.items()})


def verify_render_normals(digest, assets):
    """Compare actual persisted normals with the mathematically outward recipe.

    RenderData triangles use Unreal's clockwise convention. The old and new
    normals therefore oppose raw index cross products; only the additional
    pure outward cross comparison proves that the new shell is visible outside.
    """
    path = WORK / 'ShapeRenderNormals.json'
    result = read(path)
    rows = result.get('assets', [])
    require(result.get('map_sha256') == digest and not result.get('errors')
            and len(rows) == len({r.get('asset_key') for r in rows}) == 2
            and {r.get('asset_key') for r in rows} == set(assets),
            'The actual persisted render-normal proof is missing, failed or stale.')
    counts = {'Toilet': (1071, 2816), 'Washbasin': (1552, 2688)}
    for row in rows:
        key, source = row['asset_key'], assets[row['asset_key']]
        require(row.get('asset') == source['asset'] and row.get('sha256') == source['sha256'],
                'The render-normal proof targets another saved fixture asset: ' + key)
        retained, added = counts[key]
        require(row.get('parts', {}).get('retained') == dict(positive=0, negative=retained, zero=0)
                and row.get('parts', {}).get('new') == dict(positive=0, negative=added, zero=0)
                and row.get('parts', {}).get('new_relative_to_pure_outward_cross')
                == dict(positive=added, negative=0, zero=0),
                'The new normals do not face mathematically outward with the retained UE convention: ' + key)
    return dict(passed=True, file=str(path), sha256=sha(path),
                outward_new_toilet_faces=2816, outward_new_basin_faces=2688,
                retained_and_new_UE_raw_winding_agree=True)


def actual_bounds(geometry, labels):
    source_geometry = read(SOURCE / 'GeometryAfter.json')
    source_components = {c['actor']: c for c in source_geometry['components'] if c.get('actor') in labels}
    result = {}
    for label in labels:
        components = [c for c in geometry['components'] if c.get('actor') == label]
        require(len(components) == 1 and components[0].get('vertices'),
                'The fixture actual-render geometry is absent or ambiguous: ' + label)
        component = components[0]
        original = source_components.get(label)
        require(original is not None and component.get('render_offset_cm', [0, 0, 0])
                == original.get('render_offset_cm', [0, 0, 0])
                and component.get('materials') == original.get('materials'),
                'A fixture render offset or material changed: ' + label)
        # Actor bounds exclude material WPO, while the actual rendered export
        # includes it. The staff basin intentionally retains its 0.09 cm offset.
        offset = component.get('render_offset_cm', [0, 0, 0])
        vertices = [[float(v[i]) - float(offset[i]) for i in range(3)] for v in component['vertices']]
        result[label] = [[min(v[i] for v in vertices) for i in range(3)],
                         [max(v[i] for v in vertices) for i in range(3)]]
    return result


def check_bounds(row, bounds, label):
    for key in ('world_min', 'world_max', 'bounds'):
        require(key in row, 'The revised fixture plan omits actual bounds: ' + label)
    for key in BOUND_FIELDS & set(row):
        expected = bounds[0] if key == 'world_min' else bounds[1] if key == 'world_max' else bounds
        actual = row[key]
        flat_actual = actual if key in ('world_min', 'world_max') else [v for side in actual for v in side]
        flat_expected = expected if key in ('world_min', 'world_max') else [v for side in expected for v in side]
        require(len(flat_actual) == len(flat_expected)
                and all(abs(float(a) - float(b)) <= 0.05 for a, b in zip(flat_actual, flat_expected)),
                'The fixture plan bounds differ from actual rendered vertices: ' + label + ':' + key)


def verify_preservation(build, previous, before, after, plan, optimization, assets, geometry,
                        architecture, detail, saved):
    digest = build['map_sha256']
    require(previous.get('status') == 'PASS' and previous.get('map_sha256') == SOURCE_SHA,
            'Previous sanitary-fixture result differs from the approved starting map.')
    require(before == read(SOURCE / 'AfterSnapshot.json') and before.get('passed') is True
            and before.get('target_level') == TARGET and before.get('source_map_sha256') == SOURCE_SHA,
            'Input snapshot is not the verified previous saved map.')
    backup = WORK / 'Before'
    require(sha(backup / 'L_OldTownSchoolStreet.umap') == SOURCE_SHA
            and read(backup / 'BuildReport.json') == previous
            and read(backup / 'AfterSnapshot.json') == before
            and read(backup / 'PreservationBaseline.json') == read(SOURCE / 'PreservationBaseline.json'),
            'The immutable starting map/report backup is absent or differs.')
    require(after.get('passed') is True and after.get('target_level') == TARGET
            and after.get('source_map_sha256') == digest,
            'AfterSnapshot does not describe the freshly loaded current saved map.')
    require(optimization.get('passed') is True and optimization.get('map_sha256') == digest
            and optimization.get('source_map_sha256') == SOURCE_SHA,
            'Fixture optimization report differs from the current saved build.')
    old, new = before['actors'], after['actors']
    targets_by_key = {}
    for key, asset in assets.items():
        labels = {n for n, state in old.items() for c in state.get('components', [])
                  if c.get('mesh') == asset['source']}
        require(len(labels) == 30, 'The complete thirty-instance source fixture set differs: ' + key)
        targets_by_key[key] = labels
    toilets, basins = targets_by_key['Toilet'], targets_by_key['Washbasin']
    targets = toilets | basins
    declared = optimization.get('changed_actors', [])
    require(len(targets) == len(declared) == len(set(declared)) == 60 and set(declared) == targets,
            'The declared sixty-fixture optimization set is incomplete or duplicated.')
    cameras = optimization.get('new_cameras', [])
    current_cameras = optimization.get('current_cameras', [])
    require(len(cameras) == 2 and {r.get('camera') for r in cameras} == NEW_CAMERAS
            and len(current_cameras) == len(set(current_cameras)) == 4 and set(current_cameras) == CAMERAS
            and build.get('hotel_openings_review_cameras') == current_cameras,
            'The two added and four current shape inspection cameras differ.')
    require(set(new) == set(old) | NEW_CAMERAS and not NEW_CAMERAS.intersection(old),
            'An original actor was removed or an undeclared actor was added.')
    differences = []
    for label, state in old.items():
        expected = deepcopy(state)
        if label in targets:
            key = 'Toilet' if label in toilets else 'Washbasin'
            asset = assets[key]
            matches = [c for c in expected['components'] if c.get('mesh') == asset['source']]
            require(len(matches) == 1, 'Fixture mesh component is ambiguous: ' + label)
            component = matches[0]
            require(component.get('parent') is None and component.get('visible') is True
                    and component.get('hidden_in_game') is False
                    and component.get('collision') == '<CollisionEnabled.NO_COLLISION: 0>',
                    'A targeted fixture is not the visible collision-free root mesh: ' + label)
            component['mesh'] = asset['asset']
        if new[label] != expected:
            differences.append(label)
    require(not differences, 'A saved actor changed beyond the sixty fixture mesh references: '
            + str(differences[:12]))
    require(all(new[n].get('class') == '/Script/Engine.CameraActor' for n in NEW_CAMERAS),
            'An added fixture review actor is not a camera.')
    require(len(old) == before.get('actor_count') == previous.get('actor_count') == 8012
            and len(new) == after.get('actor_count') == build.get('actor_count')
            == architecture['statistics'].get('actors') == 8014,
            'The complete before/after actor counts disagree.')
    require(saved['statistics'].get('toilets') == saved['statistics'].get('basins') == 30
            and saved['statistics'].get('unchanged_existing_actors') == 7952,
            'Fresh saved-state audit disagrees with the isolated fixture scope.')
    collider_labels = optimization.get('preserved_fixture_collision_actors', [])
    expected_colliders = [c['actor'] for r in previous['hotel_v4']['placed_props']
                          if r.get('actor') in targets for c in r['colliders']]
    require(len(collider_labels) == len(set(collider_labels)) == 60
            and set(collider_labels) == set(expected_colliders)
            and all(new.get(n) == old.get(n) for n in collider_labels),
            'An independent fixture collision actor changed or was omitted.')
    bounds = actual_bounds(geometry, targets)
    expected_plan = deepcopy(previous['hotel_v4'])
    placed_by_id = {r['id']: r['actor'] for r in expected_plan['placed_props'] if r.get('actor') in targets}
    for collection in ('placed_props', 'props'):
        require(len(plan.get(collection, [])) == len(expected_plan[collection]),
                'The fixture plan added or removed a prop.')
        for row, current in zip(expected_plan[collection], plan[collection]):
            label = row.get('actor') if collection == 'placed_props' else placed_by_id.get(row['id'])
            if label not in targets:
                continue
            key = 'Toilet' if label in toilets else 'Washbasin'
            row['asset'] = assets[key]['asset']
            check_bounds(current, bounds[label], label)
            for field in BOUND_FIELDS & set(current):
                row[field] = deepcopy(current[field])
    for key, asset in assets.items():
        expected_plan['asset_catalog'][key] = asset['asset'].split('.')[0]
    expected_plan['review_cameras'] += cameras
    expected_plan['new_actor_labels'] = sorted(set(expected_plan['new_actor_labels']) | NEW_CAMERAS)
    expected_plan['expected_actor_states'] = {n: new[n] for n in expected_plan['new_actor_labels']}
    expected_plan['source_map_sha256'] = SOURCE_SHA
    require(plan == expected_plan == build.get('hotel_v4') == build.get('hotel_architecture'),
            'The architecture plan changed beyond fixture references/bounds and two cameras.')
    baseline = read(WORK / 'PreservationBaseline.json')
    expected_baseline = deepcopy(read(SOURCE / 'PreservationBaseline.json'))
    expected_baseline['source_map_sha256'] = SOURCE_SHA
    require(baseline == expected_baseline, 'The preservation baseline changed unexpectedly.')
    preserved = baseline.get('preserved_actors', {})
    require(len(preserved) == 5039 and all(new.get(n) == state for n, state in preserved.items()),
            'One of the 5039 non-hotel actors changed or disappeared.')
    require(before.get('main_home') == after.get('main_home') == baseline.get('main_home')
            and after['main_home'].get('interaction_preserved') is True,
            'MainHome interaction structure changed.')
    require(all(n in old and new[n] == old[n] for n in ('BP_ItemPickup', 'PointLight')),
            'A user-added actor changed or disappeared.')
    door_labels = [r['actor'] for r in plan['placed_doors']]
    require(len(door_labels) == len(set(door_labels)) == 96
            and all(new[n] == old[n] for n in door_labels), 'An existing hotel door changed.')
    arch_checks = {c['name']: c for c in architecture['checks']}
    required = {'exact_current_actor_set', 'all_new_actor_saved_states_match',
                'all_nonhotel_actors_unchanged', 'shared_assets_unchanged', 'protected_maps_unchanged',
                'MainHome_interaction_structure_preserved', 'temporary_inspection_objects_absent'}
    require(required <= set(arch_checks), 'Required fresh architecture/preservation checks are missing.')
    detail_checks = {c['name']: c for c in detail['checks']}
    require(all(detail_checks.get('original_door_state_preserved:' + r['id'], {}).get('passed') is True
                for r in plan['placed_doors']), 'Fresh detail audit omitted an original door.')
    shared_count = hashes(before['shared_asset_sha256'], 'All starting referenced mesh assets')
    require(shared_count == 400, 'The complete 400-file starting mesh manifest changed.')
    hashes(baseline['shared_asset_sha256'], 'Earlier original shared assets')
    referenced_count = hashes(after['shared_asset_sha256'], 'Current referenced mesh assets')
    old_refs, new_refs = before['shared_asset_sha256'], after['shared_asset_sha256']
    require(all(old_refs[p] == new_refs[p] for p in set(old_refs) & set(new_refs)),
            'An original retained mesh changed on disk.')
    expected_refs = deepcopy(old_refs)
    for asset in assets.values():
        require(old_refs.get(asset['source_file']) == asset['source_sha256'],
                'The declared fixture source is not the verified starting mesh file.')
        del expected_refs[asset['source_file']]
        expected_refs[asset['file']] = asset['sha256']
    require(new_refs == expected_refs,
            'Current references must replace only the two source fixture clones and retain every other file.')
    require(before['protected_map_sha256'] == after['protected_map_sha256']
            == build['protected_map_sha256'] == baseline['protected_map_sha256'],
            'Protected-map fingerprints changed during this refinement.')
    protected_count = hashes(before['protected_map_sha256'], 'Current input protected maps')
    require(protected_count == 3, 'The protected-map manifest is incomplete.')
    return dict(passed=True, input_map_sha256=SOURCE_SHA, current_map_sha256=digest,
                input_actors=8012, current_actors=8014, render_mesh_references_replaced=60,
                fixture_actor_transforms_preserved=60, all_other_existing_actor_states_preserved=7952,
                added_inspection_cameras=sorted(NEW_CAMERAS), independent_fixture_collision_actors_preserved=60,
                original_doors_preserved=96, nonhotel_actors_preserved=5039,
                starting_referenced_mesh_assets_unchanged=shared_count,
                current_referenced_mesh_assets=referenced_count, protected_maps_unchanged=protected_count,
                MainHome_interaction_structure_preserved=True, approved_layout_and_routes_preserved=True)


def verify_fixture_geometry(digest, optimization):
    path = WORK / 'ShapeGeometryAudit.json'
    result = read(path)
    checks = result.get('checks', [])
    require(result.get('passed') is True and not result.get('errors')
            and result.get('map_sha256') == digest and result.get('source_map_sha256') == SOURCE_SHA,
            'Actual fixture geometry audit failed or is stale.')
    require(result.get('statistics', {}).get('toilets') == result.get('statistics', {}).get('basins') == 30,
            'Actual geometry audit omitted a fixture type or instance.')
    require(checks and all(c.get('passed') is True and c.get('name') for c in checks)
            and len({c['name'] for c in checks}) == len(checks),
            'Actual fixture geometry checks are missing, duplicated or failed.')
    require(all(any(c.get('actor') == label or label in c['name'] for c in checks)
                for label in optimization['changed_actors']),
            'Actual geometry checks do not cover every one of the sixty fixtures.')
    check_names = {c['name'] for c in checks}
    for label in optimization['changed_actors']:
        fixture = 'Toilet' if 'Toilet' in label else 'Washbasin'
        pieces = [p for p in recipe.build_pieces() if p['fixture'] == fixture]
        required = {'all_retained_source_faces_match_one_to_one',
                    'no_unprescribed_added_or_removed_faces',
                    'entire_original_fixture_envelope_preserved',
                    'materials_collision_and_wpo_preserved',
                    'independent_fixture_collider_unchanged'}
        for piece in pieces:
            required |= {piece['name'] + '_all_prescribed_faces_present',
                         piece['name'] + '_actual_closed_oriented_solid'}
        for witness in recipe.CONNECTION_WITNESSES:
            if any(part == p['name'] for p in pieces for part in witness['parts']):
                required.add('solid_connection_' + witness['name'])
        if fixture == 'Toilet':
            required |= {'empty_cavity_point_' + str(i) for i in range(8)}
            required |= {'actual_cavity_down_ray_' + str(i) for i in range(4)}
            required |= {'actual_ceramic_shell_solid_' + str(i) for i in range(5)}
            required |= {'actual_existing_feet_remain_below_cavity_floor',
                         'actual_rear_shoulder_cannot_intrude_into_inner_cup'}
        require({label + ':' + n for n in required} <= check_names,
                'Required actual closed-shell/cavity/connections/source-face evidence is missing: ' + label)
    expected_inputs = [WORK / (n + '.json') for n in ('GeometryAfter', 'AfterSnapshot', 'BuildReport')]
    expected_inputs += [SOURCE / (n + '.json') for n in ('GeometryAfter', 'AfterSnapshot')]
    require(result.get('input_sha256') == {str(p): sha(p) for p in expected_inputs},
            'Actual fixture geometry proof references different saved inputs.')
    normals = WORK / 'ShapeRenderNormals.json'
    require(result.get('normals_input_sha256') == {str(normals): sha(normals)},
            'Actual fixture geometry proof references different actual render-normal evidence.')
    return dict(passed=True, toilets=30, basins=30, geometry_checks=len(checks),
                source='Saved actual rendered vertices and triangle connectivity',
                audit_file=str(path), audit_sha256=sha(path))


def capture_review(build, mapfile):
    digest, views, runs = build['map_sha256'], [], {}
    optimization = build['sanitary_shape_refinement']
    capture_root = Path(optimization.get('capture_directory', '')).resolve()
    require(capture_root == (WORK / 'CorrectedCaptures').resolve() and capture_root.is_dir()
            and capture_root.is_relative_to(WORK.resolve()),
            'The corrected owned capture directory is absent or differs from its designated child folder.')
    renders, run_root = capture_root / 'Renders', capture_root / 'Runs'
    require(renders.resolve().is_relative_to(capture_root)
            and run_root.resolve().is_relative_to(capture_root),
            'Corrected capture renders/runs resolve outside their owned capture directory.')
    lifecycle.WORK = capture_root
    capture_runs_path = capture_root / 'CaptureRuns.json'
    require(capture_runs_path.resolve().is_relative_to(capture_root),
            'The corrected CaptureRuns manifest resolves outside its owned capture directory.')
    capture_runs = read(capture_runs_path)
    require(isinstance(capture_runs, list) and len(capture_runs) == 4
            and {r.get('camera') for r in capture_runs} == CAMERAS,
            'The corrected directory lacks the complete four-camera CaptureRuns manifest.')
    capture_run_by_camera = {r['camera']: r for r in capture_runs}
    revision = datetime.fromisoformat(optimization.get('geometry_revision_utc', '').replace('Z', '+00:00'))
    require(revision.tzinfo is not None, 'The geometry revision has no explicit UTC/timezone identity.')
    revision_timestamp = revision.timestamp()
    planned = {r['camera']: r for r in build['hotel_v4']['review_cameras']}
    for camera in optimization['current_cameras']:
        require(camera in planned and re.fullmatch(r'[A-Za-z0-9_]+', camera), 'Missing/unsafe review camera.')
        mode = planned[camera].get('lighting_mode', 'temporary')
        png = renders / (camera + '.png')
        require(png.resolve().is_relative_to(capture_root)
                and png.with_suffix('.json').resolve().is_relative_to(capture_root),
                'A current corrected image resolves outside its owned capture directory: ' + camera)
        metadata, data = read(png.with_suffix('.json')), png.read_bytes()
        require(len(data) > 20000 and data[:8] == b'\x89PNG\r\n\x1a\n'
                and data[12:16] == b'IHDR', 'Invalid fixture PNG: ' + camera)
        require(struct.unpack('>II', data[16:24]) == (1280, 720)
                == (metadata.get('width'), metadata.get('height')), 'Fixture PNG resolution differs: ' + camera)
        require(metadata.get('status') == 'PASS' and metadata.get('camera') == camera
                and metadata.get('target_level') == TARGET
                and metadata.get('map_sha256') == metadata.get('map_sha256_after_cleanup') == digest
                and metadata.get('png_sha256') == sha(png) and metadata.get('bytes') == len(data),
                'Fixture capture hash/map identity differs: ' + camera)
        require(metadata.get('lighting_mode') == mode
                and metadata.get('view_mode_requested') == metadata.get('view_mode_verified') == 'lit'
                and metadata.get('source') == 'fresh_persisted_map_load'
                and metadata.get('fresh_map_load_verified') is True
                and Path(metadata['source_persisted_map']).resolve() == mapfile.resolve()
                and metadata.get('persisted_map_unchanged') is True
                and metadata.get('map_save_requested') is False,
                'Fixture capture did not load the current saved map read-only: ' + camera)
        lighting = metadata.get('temporary_lighting', {})
        require(metadata.get('temporary_lighting_cleanup_verified_zero') is True
                and metadata.get('temporary_lighting_cleanup_remaining_count') == 0
                and lighting.get('mode') == mode and lighting.get('cleanup_verified_zero') is True
                and lighting.get('remaining_count') == 0 and not lighting.get('remaining_labels')
                and not lighting.get('errors') and lighting.get('created_count')
                == lighting.get('destroyed_count') == metadata.get('temporary_lighting_created_count')
                and ((mode == 'temporary' and lighting['created_count'] > 0)
                     or (mode == 'street_only' and lighting['created_count'] == 0)),
                'Temporary fixture inspection lights were not cleaned: ' + camera)
        run_id = metadata.get('run_id')
        runs[run_id] = lifecycle.helper_run(run_id, metadata, digest, TARGET, camera, mode)
        require((run_root / run_id).resolve().is_relative_to(capture_root),
                'A corrected helper run resolves outside its owned capture directory: ' + camera)
        owned = read(run_root / run_id / 'OwnedProcess.json')
        run_row = capture_run_by_camera[camera]
        require(run_row.get('captured') is True and run_row.get('reused') is False
                and run_row.get('normal_exit') is True and run_row.get('forced_cleanup') is False
                and run_row.get('exit_code') == 0 and run_row.get('lifecycle_status') == 'NORMAL_EXIT'
                and run_row.get('map_sha256') == digest and run_row.get('run_id') == run_id
                and run_row.get('owned_editor_pid') == metadata['owned_editor_pid']
                and run_row.get('lighting_mode') == mode and run_row.get('view_mode') == 'lit'
                and Path(run_row.get('path', '')).resolve() == png.resolve()
                and Path(run_row.get('archive', '')).resolve()
                == (run_root / run_id / 'Renders' / (camera + '.png')).resolve(),
                'The corrected CaptureRuns row disagrees with current image/helper evidence: ' + camera)
        launched = datetime.fromisoformat(owned['launch_time_utc'].replace('Z', '+00:00'))
        require(launched.tzinfo is not None and launched.timestamp() > revision_timestamp,
                'A current PNG helper started before the corrected shape revision: ' + camera)
        views.append(dict(camera=camera, png=str(png), metadata=str(png.with_suffix('.json')),
                          png_sha256=sha(png), bytes=len(data), width=1280, height=720,
                          lighting_mode=mode, view_mode='lit', run_id=run_id,
                          owned_editor_pid=metadata['owned_editor_pid'], fresh_persisted_map_load=True,
                          geometry_revision_utc=optimization['geometry_revision_utc'],
                          helper_launched_after_geometry_revision=True,
                          persisted_map_unchanged=True, temporary_lighting_cleanup_remaining_count=0))
    require(len(views) == 4 and {v['camera'] for v in views} == CAMERAS,
            'The complete four-view current capture set is missing.')
    capture_files = {str(capture_runs_path): sha(capture_runs_path)}
    for view in views:
        for name in (view['png'], view['metadata']):
            capture_files[name] = sha(name)
    for run in runs.values():
        for field in ('owned_process', 'shutdown_request', 'capture_batch'):
            capture_files[run[field]] = sha(run[field])
    require(all(Path(p).resolve().is_relative_to(capture_root) for p in capture_files),
            'A corrected capture/helper evidence file resolves outside its owned capture directory.')
    return dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                capture_directory=str(capture_root), current_renders=str(renders),
                current_capture_runs_file=str(capture_runs_path),
                current_capture_runs_sha256=sha(capture_runs_path),
                current_capture_file_sha256=capture_files,
                views=views, current_helpers=list(runs.values()),
                current_helper_normal_exit_verified=True, temporary_lighting_cleanup_verified_zero=True)


def historical_review():
    prior = read(SOURCE / 'FinalReview.json')
    views = prior.get('current_captures', [])
    require(prior.get('passed') is True and prior.get('map_sha256') == SOURCE_SHA
            and len(views) == len({v.get('camera') for v in views}) == 4,
            'The previous four-view sanitary-fixture review is incomplete.')
    require(all(Path(v['png']).is_file() and sha(v['png']) == v['png_sha256'] for v in views),
            'A previous sanitary-fixture PNG differs from its archived review.')
    inherited = []
    for key, count in (('historical_basin_views', 3), ('historical_hotel_views', 21)):
        pointer = prior.get(key)
        require(isinstance(pointer, dict) and pointer.get('status') == 'historical'
                and pointer.get('review') and pointer.get('map_sha256')
                and pointer.get('view_count') == count,
                'An inherited historical review pointer is missing: ' + key)
        archived = read(pointer['review'])
        archived_views = archived.get('current_captures', [])
        require(archived.get('passed') is True and archived.get('map_sha256') == pointer['map_sha256']
                and len(archived_views) == len({v.get('camera') for v in archived_views}) == count
                and all(Path(v['png']).is_file() and sha(v['png']) == v['png_sha256']
                        for v in archived_views),
                'An inherited historical review report/image differs: ' + key)
        inherited.append(deepcopy(pointer))
    return (dict(status='historical', map_sha256=SOURCE_SHA, bundle=str(SOURCE),
                 review=str(SOURCE / 'FinalReview.json'), view_count=4,
                 cameras=[v['camera'] for v in views],
                 note='These four sanitary-fixture images precede the hollow-bowl refinement and are not current-map evidence.'),
            *inherited)


def canonical_source():
    previous = read(CANON / 'CurrentEvidence.json')
    backup = WORK / 'BeforeCanonicalPublish'
    if Path(previous.get('source_bundle', '')).resolve() == WORK.resolve():
        require((backup / 'CurrentEvidence.json').is_file(), 'Prior canonical backup is missing.')
        previous = read(backup / 'CurrentEvidence.json')
    require(Path(previous.get('source_bundle', '')).resolve() == SOURCE.resolve()
            and previous.get('map_sha256') == SOURCE_SHA,
            'Canonical evidence advanced to another task; publication must not overwrite it.')
    require(all(Path(n).name == n and n.endswith('.json') for n in previous.get('current_reports', [])),
            'Unsafe prior canonical report filename.')
    return previous


def validate():
    canonical_source()
    build, previous = read(WORK / 'BuildReport.json'), read(SOURCE / 'BuildReport.json')
    mapfile = ROOT / ('Content/' + TARGET.removeprefix('/Game/') + '.umap')
    digest = sha(mapfile)
    require(build.get('status') == 'PASS' and build.get('target_level') == TARGET
            and build.get('source_map_sha256') == SOURCE_SHA
            and build.get('map_sha256') == digest and digest != SOURCE_SHA,
            'Current saved build/map does not match the sanitary refinement.')
    applied = read(WORK / 'Applied.json')
    require(applied.get('passed') is True and applied.get('map_sha256') == digest
            and applied.get('source_map_sha256') == SOURCE_SHA
            and applied.get('toilets') == applied.get('basins') == 30
            and applied.get('cameras') == 2 and applied.get('actor_count') == build['actor_count'],
            'Applied marker is absent or stale.')
    hotel.WORK = WORK
    architecture = hotel.current_audit('ArchitectureAudit.json', digest)
    detail = hotel.current_audit('DetailAudit.json', digest)
    saved = hotel.current_audit('ShapeSavedAudit.json', digest)
    before, after = read(WORK / 'InputSnapshot.json'), read(WORK / 'AfterSnapshot.json')
    plan, optimization = read(WORK / 'ArchitecturePlan.json'), build['sanitary_shape_refinement']
    require(read(WORK / 'ShapeOptimizationReport.json') == optimization,
            'The independent fixture optimization report differs from the saved build.')
    assets = assets_by_key(optimization)
    frozen_recipe = verify_recipe_file(optimization, assets)
    render_normals = verify_render_normals(digest, assets)
    old_assets, new_assets = previous['new_asset_sha256'], build['new_asset_sha256']
    require(set(old_assets) <= set(new_assets) and all(new_assets[p] == h for p, h in old_assets.items()),
            'An earlier generated asset was removed or replaced.')
    require(set(new_assets) - set(old_assets) == {r['file'] for r in assets.values()}
            and all(new_assets[r['file']] == r['sha256'] for r in assets.values())
            and all(Path(p).resolve().is_relative_to((ROOT / 'Content/CodexGenerated').resolve()) for p in new_assets),
            'The new generated-asset manifest differs from the two cloned fixtures.')
    generated_count = hashes(new_assets, 'Generated assets')
    hashes(old_assets, 'Earlier generated assets')
    geometry_file = WORK / 'GeometryAfter.json'
    geometry_hash, geometry = sha(geometry_file), read(geometry_file)
    summary = read(WORK / 'AfterSummary.json')
    require(geometry.get('map_sha256') == digest and not geometry.get('errors')
            and geometry.get('components') and summary.get('passed') is True
            and not summary.get('errors') and summary.get('map_sha256') == digest,
            'Fresh full-map render export is absent, stale or failed.')
    require(summary.get('actors') == build['actor_count']
            and summary.get('visible_components') == len(geometry['components'])
            and summary.get('triangles') == geometry['triangles']
            and summary.get('unique_meshes') == geometry['unique_meshes'],
            'Fresh render export and summary counts disagree.')
    require(all(not any(abs(float(v)) > 1e-8 for v in c.get('render_offset_cm', [0, 0, 0]))
                or c.get('wpo_verified_from_persisted_material') is True for c in geometry['components']),
            'A render offset was inferred instead of verified from the persisted material.')
    preservation = verify_preservation(build, previous, before, after, plan, optimization, assets, geometry,
                                       architecture, detail, saved)
    fixtures = verify_fixture_geometry(digest, optimization)
    surfaces.WORK = WORK
    scans = surfaces.verify_scans(digest, geometry, geometry_hash, read(WORK / 'SavedScanSummary.json'))
    captures = capture_review(build, mapfile)
    visual = read(WORK / 'VisualReview.json')
    require(visual.get('passed') is True and not visual.get('errors')
            and visual.get('map_sha256') == digest and visual.get('target_level') == TARGET,
            'Current fixture visual review is missing, failed or stale.')
    reviewed, captured = visual.get('views', []), {v['camera']: v for v in captures['views']}
    require(len(reviewed) == 4 and {v.get('camera') for v in reviewed} == CAMERAS
            and all(v.get('passed') is True and v.get('png_sha256') == captured[v['camera']]['png_sha256']
                    for v in reviewed), 'Visual review does not cover all four current PNG hashes.')
    old_fixtures, old_basins, old_hotel = historical_review()
    require(sha(mapfile) == digest and sha(geometry_file) == geometry_hash,
            'Map or geometry changed during finalization checks.')
    hashes(new_assets, 'Generated assets')
    hashes(before['shared_asset_sha256'], 'All starting referenced mesh assets')
    hashes(build['protected_map_sha256'], 'Protected maps')
    at = datetime.now(timezone.utc).isoformat()
    captures['reviewed_utc'] = at
    evidence_names = ['BuildReport.json', 'Applied.json', 'ShapeOptimizationReport.json', 'ArchitecturePlan.json', 'ArchitectureAudit.json',
                      'DetailAudit.json', 'ShapeSavedAudit.json', 'ShapeGeometryAudit.json', 'ShapeRenderNormals.json',
                      'InputSnapshot.json', 'AfterSnapshot.json', 'PreservationBaseline.json',
                      'GeometryAfter.json', 'AfterSummary.json', 'SavedScan.json', 'SavedScanOcclusion.json',
                      'SavedScanSummary.json', 'VisualReview.json']
    audit = dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                 source_map_sha256=SOURCE_SHA, source='fresh_persisted_map_load',
                 persisted_map_unchanged=True, preservation=preservation, sanitary_shapes=fixtures,
                 frozen_source_art_recipe=frozen_recipe,
                 actual_render_normals=render_normals,
                 current_capture_file_sha256=captures['current_capture_file_sha256'],
                 surface_scans=scans, generated_asset_count=generated_count,
                 earlier_generated_assets_unchanged=len(old_assets),
                 current_evidence_file_sha256={n: sha(WORK / n) for n in evidence_names}, reviewed_utc=at)
    final = dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                 source_map_sha256=SOURCE_SHA, actor_count=build['actor_count'], current_bundle=str(WORK),
                 change='Thirty toilets receive closed hollow bowls and a shaped rear support; thirty washbasins receive continuously rounded faucet spouts.',
                 sanitary_shapes=fixtures, preservation=preservation, frozen_source_art_recipe=frozen_recipe,
                 actual_render_normals=render_normals,
                 fresh_architecture_validation=architecture['statistics'], fresh_detail_validation=detail['statistics'],
                 surface_scans=scans, current_render_source=str(geometry_file),
                 current_render_source_sha256=geometry_hash, current_captures=captures['views'],
                 current_helpers=captures['current_helpers'], historical_fixture_views=old_fixtures,
                 capture_directory=captures['capture_directory'], current_renders=captures['current_renders'],
                 historical_basin_views=old_basins,
                 historical_hotel_views=old_hotel,
                 limitations=['Geometry proof covers the 30 toilets and 30 basins; it does not claim every unrelated map assembly is connected.',
                    'Current visual review covers four sanitary-shape closeups. The prior four fixture, three basin and 21 hotel images are historical.',
                    'Full-map coplanar scanning covers same-facing overlaps of at least 1cm2 within 0.03cm plane tolerance; fully buried groups are retained with proof.'],
                 reviewed_utc=at)
    return dict(build=build, mapfile=mapfile, digest=digest, geometry_file=geometry_file,
                geometry_hash=geometry_hash, audit=audit, captures=captures, final=final)


def publish(result):
    digest, build = result['digest'], result['build']
    require(sha(result['mapfile']) == digest and sha(result['geometry_file']) == result['geometry_hash'],
            'Map or geometry changed before publication.')
    hashes(build['new_asset_sha256'], 'Generated assets')
    hashes(build['protected_map_sha256'], 'Protected maps')
    frozen = result['audit']['frozen_source_art_recipe']
    require(sha(frozen['source_art_recipe']) == frozen['source_art_recipe_sha256'],
            'The independent source-art recipe changed before publication.')
    require(all(sha(WORK / name) == digest for name, digest in
                result['audit']['current_evidence_file_sha256'].items()),
            'Current validation/capture/geometry evidence changed before publication.')
    hashes(result['audit']['current_capture_file_sha256'], 'Corrected image/helper manifest evidence')
    previous = canonical_source()
    backup = WORK / 'BeforeCanonicalPublish'
    names = ['BuildReport.json', 'Applied.json', 'ShapeOptimizationReport.json', 'ArchitecturePlan.json', 'ArchitectureAudit.json',
             'DetailAudit.json', 'ShapeSavedAudit.json', 'ShapeGeometryAudit.json', 'ShapeRenderNormals.json', 'AfterSummary.json',
             'SavedScan.json', 'SavedScanOcclusion.json', 'SavedScanSummary.json', 'VisualReview.json',
             'ShapeFinalAudit.json', 'CaptureReview.json', 'FinalReview.json']
    backup.mkdir(parents=True, exist_ok=True)
    for name in sorted(set(names + ['CurrentEvidence.json']) | set(previous.get('current_reports', []))):
        require(Path(name).name == name and name.endswith('.json'), 'Unsafe prior report filename.')
        source, destination = CANON / name, backup / name
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
    write(backup / 'BackupManifest.json', dict(historical_only=True, current_publication_map_sha256=digest,
        backed_up_report_sha256={p.name: sha(p) for p in backup.glob('*.json') if p.name != 'BackupManifest.json'}))
    write(WORK / 'ShapeFinalAudit.json', result['audit'])
    write(WORK / 'CaptureReview.json', result['captures'])
    write(WORK / 'FinalReview.json', result['final'])
    expected = {name: sha(WORK / name) for name in names}
    for name in names:
        pending = CANON / (name + '.tmp')
        shutil.copy2(WORK / name, pending)
        pending.replace(CANON / name)
        require(sha(CANON / name) == expected[name], 'Published report hash differs: ' + name)
    views = result['captures']['views']
    evidence = dict(target_level=TARGET, map_sha256=digest, source_bundle=str(WORK),
        source_directory=str(WORK), current_reports=names, current_report_sha256=expected,
        current_renders=result['captures']['current_renders'],
        current_capture_directory=result['captures']['capture_directory'],
        current_capture_runs_file=result['captures']['current_capture_runs_file'],
        current_capture_runs_sha256=result['captures']['current_capture_runs_sha256'],
        current_render_cameras=[v['camera'] for v in views],
        current_render_lighting_modes={v['camera']: v['lighting_mode'] for v in views},
        current_render_geometry=str(result['geometry_file']), current_render_geometry_sha256=result['geometry_hash'],
        current_actor_snapshot=str(WORK / 'AfterSnapshot.json'),
        current_actor_snapshot_sha256=sha(WORK / 'AfterSnapshot.json'),
        current_architecture_plan=str(WORK / 'ArchitecturePlan.json'),
        current_architecture_plan_sha256=sha(WORK / 'ArchitecturePlan.json'),
        previous_bundle=str(SOURCE), previous_evidence_status='historical', historical_report_backup=str(backup),
        historical_fixture_views=result['final']['historical_fixture_views'],
        historical_basin_views=result['final']['historical_basin_views'],
        historical_hotel_views=result['final']['historical_hotel_views'],
        historical_reports_not_current=sorted(set(previous.get('current_reports', [])) - set(names)),
        opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',
        note='All 30 hollow toilet bowls and 30 rounded basin spouts verified from saved actual geometry; four current closeups, fresh saved-world regression and full-map surface scan passed. Previous fixture, basin and hotel images are historical.',
        published_utc=result['final']['reviewed_utc'])
    write(CANON / 'CurrentEvidence.json', evidence)
    require(sha(result['mapfile']) == digest, 'Publication unexpectedly changed the saved map.')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Validate all evidence without publishing reports.')
    args = parser.parse_args()
    result = validate()
    published = {} if args.check_only else publish(result)
    print(json.dumps(dict(passed=True, check_only=args.check_only, map_sha256=result['digest'],
        bundle=str(WORK), actors=result['build']['actor_count'], toilets=30, basins=30,
        current_captures=4, historical_fixture_captures=4, historical_basin_captures=3,
        historical_hotel_captures=21, exposed_coplanar_groups=0,
        published_report_sha256=published), ensure_ascii=False))


if __name__ == '__main__':
    main()
