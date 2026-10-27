"""Validate and publish the isolated hotel sanitary-fixture refinement.

No Unreal process is started and no map or asset is modified by this script.
Four fixture closeups are current; earlier basin and hotel images are explicitly
historical. Use --check-only for the complete read-only publication preflight.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/SanitaryFixtures_20261011'
SOURCE = ROOT / 'Saved/CodexOutputs/BasinConnections_20261011'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
SOURCE_SHA = '684f1f0533cef3ab50b6c7e3b270cb0a4dab924b839139e5d9a8e2048503f33d'
NEW_CAMERAS = {'CAM_Fixture_ToiletGuest201', 'CAM_Fixture_ToiletPublicWC',
               'CAM_Fixture_FaucetPublicWC'}
CAMERAS = NEW_CAMERAS | {'CAM_Basin_Guest201'}
BOUND_FIELDS = {'world_min', 'world_max', 'bounds', 'world_bounds_cm'}
sys.path.insert(0, str(ROOT / 'Scripts'))
import FinalizeOldTownHotelDetails as hotel
import FinalizeOldTownStreetRefinement as lifecycle
import FinalizeOldTownSurfaceRepair as surfaces


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
    require(len({r['file'] for r in rows}) == len({r['asset'] for r in rows}) == 2,
            'The two fixture clones share an asset/file identity.')
    return result


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
            'Previous basin result differs from the approved starting map.')
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
    require(len(cameras) == 3 and {r.get('camera') for r in cameras} == NEW_CAMERAS
            and len(current_cameras) == len(set(current_cameras)) == 4 and set(current_cameras) == CAMERAS
            and build.get('hotel_openings_review_cameras') == current_cameras,
            'The three added and four current fixture inspection cameras differ.')
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
            if key == 'Toilet':
                require(state.get('rotation') == component.get('rotation') == [0.0, 180.0, 0.0],
                        'The source toilet orientation differs: ' + label)
                expected['rotation'] = component['rotation'] = [0.0, 0.0, 0.0]
        if new[label] != expected:
            differences.append(label)
    require(not differences, 'A saved actor changed beyond the sixty fixture mesh references and toilet yaw: '
            + str(differences[:12]))
    require(all(new[n].get('class') == '/Script/Engine.CameraActor' for n in NEW_CAMERAS),
            'An added fixture review actor is not a camera.')
    require(len(old) == before.get('actor_count') == previous.get('actor_count') == 8009
            and len(new) == after.get('actor_count') == build.get('actor_count')
            == architecture['statistics'].get('actors') == 8012,
            'The complete before/after actor counts disagree.')
    require(saved['statistics'].get('toilets') == saved['statistics'].get('basins') == 30
            and saved['statistics'].get('unchanged_existing_actors') == 7949,
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
            if key == 'Toilet':
                row['yaw'], row['rotation'] = 0.0, [0.0, 0.0, 0.0]
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
            'The architecture plan changed beyond fixture references/orientation/bounds and three cameras.')
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
                input_actors=8009, current_actors=8012, render_mesh_references_replaced=60,
                toilet_orientations_corrected=30, all_other_existing_actor_states_preserved=7949,
                added_inspection_cameras=sorted(NEW_CAMERAS), independent_fixture_collision_actors_preserved=60,
                original_doors_preserved=96, nonhotel_actors_preserved=5039,
                starting_referenced_mesh_assets_unchanged=shared_count,
                current_referenced_mesh_assets=referenced_count, protected_maps_unchanged=protected_count,
                MainHome_interaction_structure_preserved=True, approved_layout_and_routes_preserved=True)


def verify_fixture_geometry(digest, optimization):
    path = WORK / 'FixtureGeometryAudit.json'
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
    expected_inputs = [WORK / (n + '.json') for n in ('GeometryAfter', 'AfterSnapshot', 'BuildReport')]
    expected_inputs += [SOURCE / (n + '.json') for n in ('GeometryAfter', 'AfterSnapshot')]
    require(result.get('input_sha256') == {str(p): sha(p) for p in expected_inputs},
            'Actual fixture geometry proof references different saved inputs.')
    return dict(passed=True, toilets=30, basins=30, geometry_checks=len(checks),
                source='Saved actual rendered vertices and triangle connectivity',
                audit_file=str(path), audit_sha256=sha(path))


def capture_review(build, mapfile):
    lifecycle.WORK = WORK
    digest, views, runs = build['map_sha256'], [], {}
    optimization = build['fixture_optimization']
    planned = {r['camera']: r for r in build['hotel_v4']['review_cameras']}
    for camera in optimization['current_cameras']:
        require(camera in planned and re.fullmatch(r'[A-Za-z0-9_]+', camera), 'Missing/unsafe review camera.')
        mode = planned[camera].get('lighting_mode', 'temporary')
        png = WORK / 'Renders' / (camera + '.png')
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
        views.append(dict(camera=camera, png=str(png), metadata=str(png.with_suffix('.json')),
                          png_sha256=sha(png), bytes=len(data), width=1280, height=720,
                          lighting_mode=mode, view_mode='lit', run_id=run_id,
                          owned_editor_pid=metadata['owned_editor_pid'], fresh_persisted_map_load=True,
                          persisted_map_unchanged=True, temporary_lighting_cleanup_remaining_count=0))
    require(len(views) == 4 and {v['camera'] for v in views} == CAMERAS,
            'The complete four-view current capture set is missing.')
    return dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                views=views, current_helpers=list(runs.values()),
                current_helper_normal_exit_verified=True, temporary_lighting_cleanup_verified_zero=True)


def historical_review():
    prior = read(SOURCE / 'FinalReview.json')
    views = prior.get('current_captures', [])
    require(prior.get('passed') is True and prior.get('map_sha256') == SOURCE_SHA
            and len(views) == len({v.get('camera') for v in views}) == 3,
            'The previous three-view basin review is incomplete.')
    require(all(Path(v['png']).is_file() and sha(v['png']) == v['png_sha256'] for v in views),
            'A previous basin PNG differs from its archived review.')
    hotel_views = prior.get('historical_hotel_views')
    require(isinstance(hotel_views, dict) and hotel_views.get('status') == 'historical'
            and hotel_views.get('review') and hotel_views.get('map_sha256'),
            'The inherited historical hotel review pointer is missing.')
    archived = read(hotel_views['review'])
    require(archived.get('passed') is True and archived.get('map_sha256') == hotel_views['map_sha256'],
            'The inherited historical hotel review pointer differs from its archived report.')
    return (dict(status='historical', map_sha256=SOURCE_SHA, bundle=str(SOURCE),
                 review=str(SOURCE / 'FinalReview.json'), view_count=3,
                 cameras=[v['camera'] for v in views],
                 note='These three basin images precede the sanitary refinement and are not current-map evidence.'),
            deepcopy(hotel_views))


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
            and applied.get('cameras') == 3 and applied.get('actor_count') == build['actor_count'],
            'Applied marker is absent or stale.')
    hotel.WORK = WORK
    architecture = hotel.current_audit('ArchitectureAudit.json', digest)
    detail = hotel.current_audit('DetailAudit.json', digest)
    saved = hotel.current_audit('FixtureSavedAudit.json', digest)
    before, after = read(WORK / 'InputSnapshot.json'), read(WORK / 'AfterSnapshot.json')
    plan, optimization = read(WORK / 'ArchitecturePlan.json'), build['fixture_optimization']
    require(read(WORK / 'FixtureOptimizationReport.json') == optimization,
            'The independent fixture optimization report differs from the saved build.')
    assets = assets_by_key(optimization)
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
    old_basins, old_hotel = historical_review()
    require(sha(mapfile) == digest and sha(geometry_file) == geometry_hash,
            'Map or geometry changed during finalization checks.')
    hashes(new_assets, 'Generated assets')
    hashes(before['shared_asset_sha256'], 'All starting referenced mesh assets')
    hashes(build['protected_map_sha256'], 'Protected maps')
    at = datetime.now(timezone.utc).isoformat()
    captures['reviewed_utc'] = at
    evidence_names = ['BuildReport.json', 'Applied.json', 'FixtureOptimizationReport.json', 'ArchitecturePlan.json', 'ArchitectureAudit.json',
                      'DetailAudit.json', 'FixtureSavedAudit.json', 'FixtureGeometryAudit.json',
                      'InputSnapshot.json', 'AfterSnapshot.json', 'PreservationBaseline.json',
                      'GeometryAfter.json', 'AfterSummary.json', 'SavedScan.json', 'SavedScanOcclusion.json',
                      'SavedScanSummary.json', 'VisualReview.json']
    audit = dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                 source_map_sha256=SOURCE_SHA, source='fresh_persisted_map_load',
                 persisted_map_unchanged=True, preservation=preservation, sanitary_fixtures=fixtures,
                 surface_scans=scans, generated_asset_count=generated_count,
                 earlier_generated_assets_unchanged=len(old_assets),
                 current_evidence_file_sha256={n: sha(WORK / n) for n in evidence_names}, reviewed_utc=at)
    final = dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                 source_map_sha256=SOURCE_SHA, actor_count=build['actor_count'], current_bundle=str(WORK),
                 change='Thirty toilets face into their rooms with refined fixture geometry; thirty connected washbasins gain a complete faucet assembly.',
                 sanitary_fixtures=fixtures, preservation=preservation,
                 fresh_architecture_validation=architecture['statistics'], fresh_detail_validation=detail['statistics'],
                 surface_scans=scans, current_render_source=str(geometry_file),
                 current_render_source_sha256=geometry_hash, current_captures=captures['views'],
                 current_helpers=captures['current_helpers'], historical_basin_views=old_basins,
                 historical_hotel_views=old_hotel,
                 limitations=['Geometry proof covers the 30 toilets and 30 basins; it does not claim every unrelated map assembly is connected.',
                    'Current visual review covers four sanitary-fixture closeups. The prior three basin images and earlier hotel views are historical.',
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
    previous = canonical_source()
    backup = WORK / 'BeforeCanonicalPublish'
    names = ['BuildReport.json', 'Applied.json', 'FixtureOptimizationReport.json', 'ArchitecturePlan.json', 'ArchitectureAudit.json',
             'DetailAudit.json', 'FixtureSavedAudit.json', 'FixtureGeometryAudit.json', 'AfterSummary.json',
             'SavedScan.json', 'SavedScanOcclusion.json', 'SavedScanSummary.json', 'VisualReview.json',
             'FixtureFinalAudit.json', 'CaptureReview.json', 'FinalReview.json']
    backup.mkdir(parents=True, exist_ok=True)
    for name in sorted(set(names + ['CurrentEvidence.json']) | set(previous.get('current_reports', []))):
        require(Path(name).name == name and name.endswith('.json'), 'Unsafe prior report filename.')
        source, destination = CANON / name, backup / name
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
    write(backup / 'BackupManifest.json', dict(historical_only=True, current_publication_map_sha256=digest,
        backed_up_report_sha256={p.name: sha(p) for p in backup.glob('*.json') if p.name != 'BackupManifest.json'}))
    write(WORK / 'FixtureFinalAudit.json', result['audit'])
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
        current_renders=str(WORK / 'Renders'), current_render_cameras=[v['camera'] for v in views],
        current_render_lighting_modes={v['camera']: v['lighting_mode'] for v in views},
        current_render_geometry=str(result['geometry_file']), current_render_geometry_sha256=result['geometry_hash'],
        current_actor_snapshot=str(WORK / 'AfterSnapshot.json'),
        current_actor_snapshot_sha256=sha(WORK / 'AfterSnapshot.json'),
        current_architecture_plan=str(WORK / 'ArchitecturePlan.json'),
        current_architecture_plan_sha256=sha(WORK / 'ArchitecturePlan.json'),
        previous_bundle=str(SOURCE), previous_evidence_status='historical', historical_report_backup=str(backup),
        historical_basin_views=result['final']['historical_basin_views'],
        historical_hotel_views=result['final']['historical_hotel_views'],
        historical_reports_not_current=sorted(set(previous.get('current_reports', [])) - set(names)),
        opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',
        note='All 30 toilets and 30 basins verified from saved actual geometry; four current closeups, fresh saved-world regression and full-map surface scan passed. Previous basin and hotel images are historical.',
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
        current_captures=4, historical_basin_captures=3, exposed_coplanar_groups=0,
        published_report_sha256=published), ensure_ascii=False))


if __name__ == '__main__':
    main()
