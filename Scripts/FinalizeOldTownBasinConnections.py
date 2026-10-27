"""Validate and publish the isolated thirty-washbasin connection correction.

This script never opens Unreal or modifies a map or an asset. Three new fixture
closeups are current; the preceding twenty-one hotel views remain historical.
Use --check-only to run the complete publication preflight without writing.
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
WORK = ROOT / 'Saved/CodexOutputs/BasinConnections_20261011'
SOURCE = ROOT / 'Saved/CodexOutputs/HotelDetails_20261009'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
SOURCE_SHA = 'f821289afb1e06cb2be98569d42b8cb2ad762be5ddf48dfbf00f1f7a4cd3617a'
ORIGINAL = '/Game/Yastar/Meshes/hOUSE/HotelArchitecture_20261005/SM_OTS_Arch_Washbasin.SM_OTS_Arch_Washbasin'
CAMERAS = {'CAM_Basin_Guest201', 'CAM_Basin_Guest409', 'CAM_Basin_PublicWC'}
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


def verify_preservation(build, previous, before, after, plan, repair, architecture, detail, saved):
    digest = build['map_sha256']
    require(previous.get('status') == 'PASS' and previous.get('map_sha256') == SOURCE_SHA,
            'Previous hotel result differs from the approved starting map.')
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
    require(repair == read(WORK / 'BasinRepairReport.json')
            and repair.get('map_sha256') == digest and repair.get('source') == ORIGINAL,
            'Basin repair report differs from the current saved build or source mesh.')
    labels = repair.get('actors', [])
    targets = set(labels)
    old, new = before['actors'], after['actors']
    actual_targets = {n for n, state in old.items() for c in state.get('components', [])
                      if c.get('mesh') == ORIGINAL}
    require(len(labels) == len(targets) == 30 and targets == actual_targets,
            'The thirty-instance shared washbasin manifest is incomplete or duplicated.')
    cameras = repair.get('new_cameras', [])
    require(len(cameras) == 3 and {r.get('camera') for r in cameras} == CAMERAS
            and build.get('hotel_openings_review_cameras') == [r['camera'] for r in cameras],
            'The three current fixture inspection cameras differ.')
    require(set(new) == set(old) | CAMERAS and not CAMERAS.intersection(old),
            'An original actor was removed or an undeclared actor was added.')
    differences, replacements = [], 0
    for name, state in old.items():
        expected = deepcopy(state)
        if name in targets:
            matches = [c for c in expected['components'] if c.get('mesh') == ORIGINAL]
            require(len(matches) == 1, 'Washbasin mesh component is ambiguous: ' + name)
            matches[0]['mesh'] = repair['asset']
            replacements += 1
        if new[name] != expected:
            differences.append(name)
    require(not differences and replacements == 30,
            'A saved actor changed beyond the thirty render mesh references: ' + str(differences[:12]))
    require(all(new[n].get('class') == '/Script/Engine.CameraActor' for n in CAMERAS),
            'An added fixture review actor is not a camera.')
    require(len(old) == before.get('actor_count') == previous.get('actor_count') == 8006
            and len(new) == after.get('actor_count') == build.get('actor_count')
            == architecture['statistics'].get('actors') == 8009,
            'The complete before/after actor counts disagree.')
    require(repair.get('unchanged_existing_actors') == saved['statistics'].get('unchanged_existing_actors')
            == len(old) - 30 and saved['statistics'].get('basins') == 30,
            'Fresh saved-state audit disagrees with the isolated repair scope.')
    expected_plan = deepcopy(previous['hotel_v4'])
    for row in expected_plan['placed_props']:
        if row.get('actor') in targets:
            require(row.get('asset') == ORIGINAL, 'The source fixture plan is inconsistent.')
            row['asset'] = repair['asset']
    for row in expected_plan['props']:
        if row.get('asset_key') == 'Washbasin':
            row['asset'] = repair['asset']
    expected_plan['asset_catalog']['Washbasin'] = repair['asset'].split('.')[0]
    expected_plan['review_cameras'] += cameras
    expected_plan['new_actor_labels'] = sorted(set(expected_plan['new_actor_labels']) | CAMERAS)
    expected_plan['expected_actor_states'] = {n: new[n] for n in expected_plan['new_actor_labels']}
    expected_plan['source_map_sha256'] = SOURCE_SHA
    require(plan == expected_plan == build.get('hotel_v4') == build.get('hotel_architecture'),
            'The architecture plan changed beyond the basin mesh and three review cameras.')
    baseline = read(WORK / 'PreservationBaseline.json')
    expected_baseline = deepcopy(read(SOURCE / 'PreservationBaseline.json'))
    expected_baseline['source_map_sha256'] = SOURCE_SHA
    require(baseline == expected_baseline, 'The existing preservation baseline changed unexpectedly.')
    require(before.get('main_home') == after.get('main_home') == baseline.get('main_home')
            and after['main_home'].get('interaction_preserved') is True,
            'MainHome interaction structure changed.')
    require(all(n in old and new[n] == old[n] for n in ('BP_ItemPickup', 'PointLight')),
            'A user-added actor changed or disappeared.')
    collider_labels = repair.get('unchanged_collision_actors', [])
    expected_colliders = [c['actor'] for r in previous['hotel_v4']['placed_props']
                          if r.get('actor') in targets for c in r['colliders']]
    require(len(collider_labels) == len(set(collider_labels)) == 30
            and set(collider_labels) == set(expected_colliders)
            and all(new.get(n) == old.get(n) for n in collider_labels),
            'An independent fixture collision actor changed or was omitted.')
    door_labels = [r['actor'] for r in plan['placed_doors']]
    require(len(door_labels) == len(set(door_labels)) == 96
            and all(new[n] == old[n] for n in door_labels), 'An existing hotel door changed.')
    arch_checks = {c['name']: c for c in architecture['checks']}
    required = {'exact_current_actor_set', 'all_new_actor_saved_states_match',
                'all_nonhotel_actors_unchanged', 'shared_assets_unchanged',
                'protected_maps_unchanged', 'MainHome_interaction_structure_preserved',
                'temporary_inspection_objects_absent'}
    require(required <= set(arch_checks), 'Required fresh architecture/preservation checks are missing.')
    detail_checks = {c['name']: c for c in detail['checks']}
    require(all(detail_checks.get('original_door_state_preserved:' + r['id'], {}).get('passed') is True
                for r in plan['placed_doors']), 'Fresh detail audit omitted an original door.')
    shared_count = hashes(before['shared_asset_sha256'], 'All original referenced mesh assets')
    require(shared_count == 400, 'The complete 400-file starting mesh manifest changed.')
    hashes(baseline['shared_asset_sha256'], 'Earlier original shared assets')
    referenced_count = hashes(after['shared_asset_sha256'], 'Current referenced mesh assets')
    old_refs, new_refs = before['shared_asset_sha256'], after['shared_asset_sha256']
    require(all(old_refs[p] == new_refs[p] for p in set(old_refs) & set(new_refs)),
            'An original retained mesh changed on disk.')
    generated = (ROOT / 'Content/CodexGenerated').resolve()
    require(all(Path(p).resolve().is_relative_to(generated) for p in set(new_refs) - set(old_refs)),
            'A newly referenced asset is outside CodexGenerated.')
    require(before['protected_map_sha256'] == after['protected_map_sha256']
            == build['protected_map_sha256'] == baseline['protected_map_sha256'],
            'Protected-map fingerprints changed during this repair.')
    protected_count = hashes(before['protected_map_sha256'], 'Current input protected maps')
    require(protected_count == 3, 'The protected-map input manifest is incomplete.')
    require(sha(repair['source_file']) == repair['source_sha256']
            == old_refs.get(repair['source_file']), 'Original shared basin asset changed.')
    return dict(passed=True, input_map_sha256=SOURCE_SHA, current_map_sha256=digest,
                input_actors=8006, current_actors=8009, render_mesh_references_replaced=30,
                all_other_existing_actor_states_preserved=7976, added_inspection_cameras=sorted(CAMERAS),
                independent_fixture_collision_actors_preserved=30, original_doors_preserved=96,
                original_referenced_mesh_assets_unchanged=shared_count,
                current_referenced_mesh_assets=referenced_count, protected_maps_unchanged=protected_count,
                MainHome_interaction_structure_preserved=True, approved_layout_and_routes_preserved=True)


def verify_connection_geometry(digest, repair):
    result = read(WORK / 'BasinConnectionGeometryAudit.json')
    checks, rows = result.get('checks', []), result.get('basins', [])
    require(result.get('passed') is True and not result.get('failed_checks')
            and result.get('source_map_sha256') == digest and result.get('previous_map_sha256') == SOURCE_SHA,
            'Actual basin connection geometry audit failed or is stale.')
    require(result.get('basin_count') == len(rows) == 30
            and len({r.get('actor') for r in rows}) == 30
            and {r['actor'] for r in rows} == set(repair['actors']),
            'Actual geometry audit omitted or duplicated a repaired basin.')
    require(result.get('check_count') == len(checks) and checks
            and all(r.get('passed') is True for r in checks)
            and len({r.get('id') for r in checks}) == len(checks),
            'Actual geometry checks are missing, duplicated or failed.')
    expected_inputs = [WORK / (n + '.json') for n in ('GeometryAfter', 'AfterSnapshot', 'BuildReport')]
    expected_inputs += [SOURCE / (n + '.json') for n in ('GeometryAfter', 'AfterSnapshot')]
    require(result.get('input_sha256') == {str(p): sha(p) for p in expected_inputs},
            'Actual geometry proof references different saved inputs.')
    connections = {'stem_into_support', 'stem_into_ceramic_under', 'tap_into_ceramic_under'}
    require(all(len(r.get('connections', [])) == 3
                and {c.get('connection') for c in r['connections']} == connections
                and all(c.get('passed') is True for c in r['connections']) for r in rows),
            'A basin lacks all three actual solid intersection witnesses.')
    return dict(passed=True, basins=30, validated_solid_connections=90,
                geometry_checks=len(checks), source='Saved actual rendered vertices and triangle connectivity',
                audit_file=str(WORK / 'BasinConnectionGeometryAudit.json'),
                audit_sha256=sha(WORK / 'BasinConnectionGeometryAudit.json'))


def capture_review(build, mapfile):
    lifecycle.WORK = WORK
    digest, views, runs = build['map_sha256'], [], {}
    cameras = build['basin_connection_repair']['new_cameras']
    for view in cameras:
        camera, mode = view['camera'], view.get('lighting_mode', 'temporary')
        require(re.fullmatch(r'[A-Za-z0-9_]+', camera), 'Unsafe camera label.')
        png = WORK / 'Renders' / (camera + '.png')
        metadata = read(png.with_suffix('.json'))
        data = png.read_bytes()
        require(len(data) > 20000 and data[:8] == b'\x89PNG\r\n\x1a\n'
                and data[12:16] == b'IHDR', 'Invalid fixture PNG: ' + camera)
        dimensions = struct.unpack('>II', data[16:24])
        require(dimensions == (1280, 720) == (metadata.get('width'), metadata.get('height')),
                'Fixture PNG resolution differs: ' + camera)
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
    require(len(views) == 3 and {v['camera'] for v in views} == CAMERAS,
            'The complete three-view current capture set is missing.')
    return dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                views=views, current_helpers=list(runs.values()),
                current_helper_normal_exit_verified=True, temporary_lighting_cleanup_verified_zero=True)


def validate():
    build, previous = read(WORK / 'BuildReport.json'), read(SOURCE / 'BuildReport.json')
    mapfile = ROOT / ('Content/' + TARGET.removeprefix('/Game/') + '.umap')
    digest = sha(mapfile)
    require(build.get('status') == 'PASS' and build.get('target_level') == TARGET
            and build.get('source_map_sha256') == SOURCE_SHA
            and build.get('map_sha256') == digest and digest != SOURCE_SHA,
            'Current saved build/map does not match the isolated basin correction.')
    applied = read(WORK / 'Applied.json')
    require(applied.get('passed') is True and applied.get('map_sha256') == digest
            and applied.get('source_map_sha256') == SOURCE_SHA
            and applied.get('basins') == 30 and applied.get('cameras') == 3
            and applied.get('actor_count') == build['actor_count'], 'Applied marker is absent or stale.')
    hotel.WORK = WORK
    architecture = hotel.current_audit('ArchitectureAudit.json', digest)
    detail = hotel.current_audit('DetailAudit.json', digest)
    saved = hotel.current_audit('BasinSavedAudit.json', digest)
    before, after = read(WORK / 'InputSnapshot.json'), read(WORK / 'AfterSnapshot.json')
    plan, repair = read(WORK / 'ArchitecturePlan.json'), build['basin_connection_repair']
    preservation = verify_preservation(build, previous, before, after, plan, repair, architecture, detail, saved)
    old_assets, new_assets = previous['new_asset_sha256'], build['new_asset_sha256']
    require(set(old_assets) <= set(new_assets) and all(new_assets[p] == h for p, h in old_assets.items()),
            'An earlier generated asset was removed or replaced.')
    require(set(new_assets) - set(old_assets) == {repair['file']}
            and new_assets[repair['file']] == repair['sha256']
            and all(Path(p).resolve().is_relative_to((ROOT / 'Content/CodexGenerated').resolve()) for p in new_assets),
            'The new generated-asset manifest differs from the one cloned basin.')
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
    connections = verify_connection_geometry(digest, repair)
    surfaces.WORK = WORK
    scans = surfaces.verify_scans(digest, geometry, geometry_hash, read(WORK / 'SavedScanSummary.json'))
    captures = capture_review(build, mapfile)
    visual = read(WORK / 'VisualReview.json')
    require(visual.get('passed') is True and not visual.get('errors')
            and visual.get('map_sha256') == digest and visual.get('target_level') == TARGET,
            'Current fixture visual review is missing, failed or stale.')
    reviewed, captured = visual.get('views', []), {v['camera']: v for v in captures['views']}
    require(len(reviewed) == 3 and {v.get('camera') for v in reviewed} == CAMERAS
            and all(v.get('passed') is True and v.get('png_sha256') == captured[v['camera']]['png_sha256']
                    for v in reviewed), 'Visual review does not cover all three current PNG hashes.')
    historical = read(SOURCE / 'FinalReview.json')
    historical_views = historical.get('current_captures', [])
    require(historical.get('passed') is True and historical.get('map_sha256') == SOURCE_SHA
            and len(historical_views) == len({v.get('camera') for v in historical_views}) == 21,
            'The previous twenty-one-view historical review is incomplete.')
    require(all(Path(v['png']).is_file() and sha(v['png']) == v['png_sha256'] for v in historical_views),
            'A historical hotel PNG differs from its archived previous review.')
    require(sha(mapfile) == digest and sha(geometry_file) == geometry_hash,
            'Map or geometry changed during finalization checks.')
    hashes(new_assets, 'Generated assets')
    hashes(before['shared_asset_sha256'], 'All original referenced mesh assets')
    hashes(build['protected_map_sha256'], 'Protected maps')
    at = datetime.now(timezone.utc).isoformat()
    captures['reviewed_utc'] = at
    evidence_names = ['BuildReport.json', 'Applied.json', 'BasinRepairReport.json', 'ArchitecturePlan.json',
                      'ArchitectureAudit.json', 'DetailAudit.json', 'BasinSavedAudit.json',
                      'BasinConnectionGeometryAudit.json', 'InputSnapshot.json', 'AfterSnapshot.json',
                      'PreservationBaseline.json', 'GeometryAfter.json', 'AfterSummary.json',
                      'SavedScan.json', 'SavedScanOcclusion.json', 'SavedScanSummary.json', 'VisualReview.json']
    audit = dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                 source_map_sha256=SOURCE_SHA, source='fresh_persisted_map_load',
                 persisted_map_unchanged=True, preservation=preservation, basin_connections=connections,
                 surface_scans=scans, generated_asset_count=generated_count,
                 earlier_generated_assets_unchanged=len(old_assets),
                 current_evidence_file_sha256={n: sha(WORK / n) for n in evidence_names}, reviewed_utc=at)
    final = dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                 source_map_sha256=SOURCE_SHA, actor_count=build['actor_count'], current_bundle=str(WORK),
                 change='Thirty shared washbasins: connect the drain stem to its support and ceramic underside; seat the tap in ceramic.',
                 basin_connections=connections, preservation=preservation,
                 fresh_architecture_validation=architecture['statistics'], fresh_detail_validation=detail['statistics'],
                 surface_scans=scans, current_render_source=str(geometry_file),
                 current_render_source_sha256=geometry_hash, current_captures=captures['views'],
                 current_helpers=captures['current_helpers'],
                 historical_hotel_views=dict(status='historical', map_sha256=SOURCE_SHA,
                    bundle=str(SOURCE), review=str(SOURCE / 'FinalReview.json'), view_count=21,
                    cameras=[v['camera'] for v in historical_views],
                    note='These 21 images precede the basin correction and are not current-map capture evidence.'),
                 limitations=['Connection proof covers all 30 washbasins using saved render triangles; it does not claim every unrelated map assembly is connected.',
                    'Current visual review covers three washbasin closeups; the earlier 21 hotel views are historical.',
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
    previous = read(CANON / 'CurrentEvidence.json')
    backup = WORK / 'BeforeCanonicalPublish'
    if Path(previous.get('source_bundle', '')).resolve() == WORK.resolve():
        require((backup / 'CurrentEvidence.json').is_file(), 'Prior canonical backup is missing.')
        previous = read(backup / 'CurrentEvidence.json')
    require(Path(previous.get('source_bundle', '')).resolve() == SOURCE.resolve()
            and previous.get('map_sha256') == SOURCE_SHA,
            'Canonical evidence advanced to another task; publication must not overwrite it.')
    names = ['BuildReport.json', 'Applied.json', 'BasinRepairReport.json', 'ArchitecturePlan.json',
             'ArchitectureAudit.json', 'DetailAudit.json', 'BasinSavedAudit.json',
             'BasinConnectionGeometryAudit.json', 'AfterSummary.json', 'SavedScan.json',
             'SavedScanOcclusion.json', 'SavedScanSummary.json', 'VisualReview.json',
             'BasinFinalAudit.json', 'CaptureReview.json', 'FinalReview.json']
    backup.mkdir(parents=True, exist_ok=True)
    for name in sorted(set(names + ['CurrentEvidence.json']) | set(previous.get('current_reports', []))):
        require(Path(name).name == name and name.endswith('.json'), 'Unsafe prior report filename.')
        source, destination = CANON / name, backup / name
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
    write(backup / 'BackupManifest.json', dict(historical_only=True, current_publication_map_sha256=digest,
        backed_up_report_sha256={p.name: sha(p) for p in backup.glob('*.json') if p.name != 'BackupManifest.json'}))
    write(WORK / 'BasinFinalAudit.json', result['audit'])
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
        historical_hotel_views=result['final']['historical_hotel_views'],
        historical_reports_not_current=sorted(set(previous.get('current_reports', [])) - set(names)),
        opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',
        note='All 30 washbasin connections verified from saved render triangles; three current closeups, fresh saved-world regression and full-map surface scan passed. The earlier 21 hotel images are historical.',
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
        bundle=str(WORK), actors=result['build']['actor_count'], basins=30, current_captures=3,
        historical_hotel_captures=21, exposed_coplanar_groups=0,
        published_report_sha256=published), ensure_ascii=False))


if __name__ == '__main__':
    main()
