"""Publish hotel-detail evidence only after fresh saved-map checks all pass.

Hotel-owned wall, window and rail replacements are deliberate. The complete
actor manifest, all non-hotel actors and all original doors are checked against
the user-saved input instead of requiring every old hotel actor to survive.
This script never starts Unreal or saves a map. Use --check-only for a read-only
publication preflight.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/HotelDetails_20261009'
SOURCE = ROOT / 'Saved/CodexOutputs/SurfaceSeparation_20261009'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
INPUT_MAP_SHA256 = '1015c11b5ccc54775eef291d501d4246ea3958c372fcfc56b4c00c253bd2a088'
DETAIL_CAMERAS = {
    'CAM_Detail_DoorHinge', 'CAM_Detail_StairRail', 'CAM_Detail_PostBase',
    'CAM_Detail_StairWindow', 'CAM_Detail_RearFacade', 'CAM_Detail_TopGuard',
}
sys.path.insert(0, str(ROOT / 'Scripts'))
import FinalizeOldTownStreetRefinement as lifecycle
import FinalizeOldTownSurfaceRepair as surfaces


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.tmp')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(path)


def hashes(values, label):
    require(bool(values), label + ' hash manifest is empty.')
    for name, digest in values.items():
        path = Path(name)
        require(path.is_file() and sha(path) == digest, label + ' file changed: ' + name)
    return len(values)


def current_audit(name, digest):
    result = read(WORK / name)
    require(result.get('passed') is True and not result.get('errors'), name + ' did not pass.')
    require(result.get('map_sha256') == digest and result.get('target_level') == TARGET,
            name + ' belongs to another saved map or level.')
    require(result.get('source') == 'fresh_persisted_map_load'
            and result.get('persisted_map_unchanged') is True,
            name + ' did not inspect a fresh unchanged saved map.')
    checks = result.get('checks', [])
    require(bool(checks) and all(c.get('passed') is True for c in checks),
            name + ' has missing or failed checks.')
    require(len({c.get('name') for c in checks}) == len(checks),
            name + ' has duplicate check names.')
    require(result.get('statistics', {}).get('checks') == len(checks),
            name + ' check count differs from its evidence.')
    return result


def verify_preservation(build, plan, architecture, detail, before, after, baseline, previous):
    digest = build['map_sha256']
    source_plan = previous['hotel_v4']
    source_after = read(SOURCE / 'AfterSnapshot.json')
    require(before.get('passed') is True and before.get('target_level') == TARGET
            and before.get('source_map_sha256') == build['source_map_sha256'] == INPUT_MAP_SHA256,
            'Input snapshot does not match the user-saved starting map.')
    require({k: v for k, v in source_after.items() if k != 'protected_map_sha256'}
            == {k: v for k, v in before.items() if k != 'protected_map_sha256'}
            and previous.get('map_sha256') == INPUT_MAP_SHA256,
            'The current street input differs from the verified surface-repair result.')
    # A user edit to L_Main preceded this application. Preserve that current
    # file while retaining the historical fingerprint and the rebase evidence.
    protected_rebase = read(WORK / 'ProtectedMapInputRebase.json')
    changes = protected_rebase.get('changes', [])
    require(protected_rebase.get('passed') is True and len(changes) == 1,
            'The existing protected-map input change is not explicitly accounted for.')
    rebased = dict(source_after['protected_map_sha256'])
    for change in changes:
        path = change.get('file', '')
        require(Path(path).resolve() == (ROOT / 'Content/Yastar/Maps/L_Main.umap').resolve()
                and path in rebased and change.get('historical_sha256') == rebased[path]
                and change.get('current_sha256') == before['protected_map_sha256'].get(path)
                and change.get('last_modified_utc') and change.get('reason'),
                'Protected-map input rebase identity is incomplete or unexpected.')
        rebased[path] = change['current_sha256']
    require(rebased == before['protected_map_sha256'],
            'Another protected map changed outside the recorded existing L_Main edit.')
    backup = WORK / 'Before'
    require(sha(backup / 'L_OldTownSchoolStreet.umap') == INPUT_MAP_SHA256,
            'Starting map backup is absent or has changed.')
    require(read(backup / 'BuildReport.json') == previous,
            'The immutable starting build backup differs from its original report.')
    require(after.get('passed') is True and after.get('target_level') == TARGET
            and after.get('source_map_sha256') == digest,
            'AfterSnapshot is not the current fresh saved map.')
    original = before['actors']
    current = after['actors']
    old_hotel = set(source_plan['new_actor_labels'])
    new_hotel = set(plan['new_actor_labels'])
    nonhotel = {n: state for n, state in original.items() if n not in old_hotel}
    require(len(original) == before['actor_count'] == previous['actor_count'] == 7768,
            'Starting actor count differs from the verified input.')
    require(len(nonhotel) == 5039 and set(old_hotel) <= set(original),
            'The original hotel/non-hotel manifest is incomplete.')
    require(baseline.get('source_map_sha256') == INPUT_MAP_SHA256
            and baseline.get('preserved_actors') == nonhotel,
            'The preservation baseline must contain all 5039 unmodified non-hotel actors.')
    require(not baseline.get('allowed_surface_overrides'),
            'This detail task must not introduce new non-hotel surface overrides.')
    changed_nonhotel = [n for n, state in nonhotel.items() if current.get(n) != state]
    require(not changed_nonhotel, 'A non-hotel actor changed: ' + str(changed_nonhotel[:12]))
    expected = dict(nonhotel)
    expected_created = plan.get('expected_actor_states', {})
    require(len(plan['new_actor_labels']) == len(new_hotel)
            and set(expected_created) == new_hotel and not new_hotel.intersection(nonhotel),
            'The new hotel saved-state manifest is incomplete, duplicated or overlaps non-hotel actors.')
    expected.update(expected_created)
    require(set(expected) == set(current), 'The complete saved-actor manifest omits or adds actors.')
    different = [n for n, state in expected.items() if current[n] != state]
    require(not different, 'Fresh saved actor states differ from approved changes: ' + str(different[:12]))
    require(build['actor_count'] == len(current) == after['actor_count']
            == architecture['statistics']['actors'], 'Current actor counts disagree.')
    removed = set(original) - set(current)
    added = set(current) - set(original)
    declared_removed = set(baseline.get('removed_actor_labels', []))
    require(bool(declared_removed) and declared_removed <= old_hotel
            and removed == declared_removed - new_hotel,
            'Removed labels are not the declared hotel-owned replacements.')
    require(added <= new_hotel and not removed.intersection(nonhotel),
            'The detail task added or deleted an actor outside the hotel manifest.')
    users = ['BP_ItemPickup', 'PointLight']
    require(all(n in nonhotel and current.get(n) == original[n] for n in users),
            'A user-added actor changed or disappeared.')
    doors = plan['placed_doors']
    require(len(doors) == len({r['actor'] for r in doors}) == 96
            and [r['id'] for r in doors] == [r['id'] for r in source_plan['placed_doors']],
            'The 96 original door manifest changed.')
    require(doors == source_plan['placed_doors'], 'An original door plan, pivot or mechanical state changed.')
    require(all(current.get(r['actor']) == original.get(r['actor']) for r in doors),
            'An original door actor, component or persisted pose changed.')
    require(sum(r.get('kind') == 'swing' for r in doors) == 62,
            'The hinge-equipped swing-door count differs.')
    for name in ('rooms', 'floor_z_cm', 'routes', 'stair_routes', 'shafts'):
        require(plan.get(name) == source_plan.get(name), 'Approved layout or routes changed: ' + name)
    require(len(plan['rooms']) == architecture['statistics']['rooms'] == 27
            and len(plan['floor_z_cm']) == 4, 'The four-storey, 27-room approved layout changed.')
    require(before.get('main_home') == after.get('main_home') == baseline.get('main_home')
            and after['main_home'].get('interaction_preserved') is True,
            'MainHome interaction structure is not preserved.')
    required = {'exact_current_actor_set', 'all_new_actor_saved_states_match',
                'all_nonhotel_actors_unchanged', 'shared_assets_unchanged',
                'protected_maps_unchanged', 'MainHome_interaction_structure_preserved',
                'temporary_inspection_objects_absent'}
    arch_checks = {c['name']: c for c in architecture['checks']}
    require(required <= set(arch_checks) and all(arch_checks[n]['passed'] for n in required),
            'Required fresh actor/preservation checks are absent.')
    door_checks = {c['name']: c for c in detail['checks']}
    require(all(door_checks.get('original_door_state_preserved:' + r['id'], {}).get('passed') is True
                for r in doors), 'Fresh detail audit did not verify every original door state.')
    require(architecture['preservation']['preserved_actors'] == 5039
            and architecture['preservation']['removed_actors'] == len(declared_removed)
            and architecture['preservation']['new_actors'] == len(new_hotel),
            'Fresh architecture preservation counts disagree with the complete manifest.')
    shared = hashes(before['shared_asset_sha256'], 'Original shared assets')
    require(shared == 389 and baseline['shared_asset_sha256'] == before['shared_asset_sha256'],
            'The complete 389-file shared-asset baseline changed.')
    referenced = hashes(after['shared_asset_sha256'], 'Current referenced mesh assets')
    old_refs, new_refs = before['shared_asset_sha256'], after['shared_asset_sha256']
    require(all(old_refs[p] == new_refs[p] for p in set(old_refs) & set(new_refs)),
            'An original asset retained by the saved map changed its SHA.')
    generated = (ROOT / 'Content/CodexGenerated').resolve()
    require(all(Path(p).resolve().is_relative_to(generated) for p in set(new_refs) - set(old_refs)),
            'A newly referenced mesh is outside CodexGenerated.')
    protected = hashes(before['protected_map_sha256'], 'Protected maps')
    require(protected == 3 and build['protected_map_sha256'] == baseline['protected_map_sha256']
            == before['protected_map_sha256'] == after['protected_map_sha256'],
            'Protected-map fingerprints differ from the starting map.')
    return dict(passed=True, input_map_sha256=INPUT_MAP_SHA256, current_map_sha256=digest,
                input_actors=len(original), current_actors=len(current),
                nonhotel_actors_exactly_preserved=5039, original_doors_exactly_preserved=96,
                removed_hotel_actor_labels=sorted(removed), added_hotel_actor_labels=sorted(added),
                declared_hotel_replacement_labels=sorted(declared_removed),
                shared_assets_unchanged=shared, current_referenced_mesh_assets=referenced,
                protected_maps_unchanged=protected, existing_protected_map_edit_preserved=changes,
                user_added_actors_preserved=users,
                MainHome_interaction_structure_preserved=True, approved_rooms=27,
                approved_storeys=4, approved_layout_and_routes_preserved=True,
                exact_saved_actor_manifest_verified=True)


def verify_details(build, plan, detail, report):
    digest = build['map_sha256']
    require(report.get('passed') is True and report.get('map_sha256') == digest
            and report.get('source_map_sha256') == INPUT_MAP_SHA256
            and report == build.get('detail_repair'),
            'DetailRepairReport differs from the current saved build.')
    expected_report = dict(grounded_posts=240, baseplates=240, pipes=60, sloped_pipes=18,
                           hinge_equipped_doors=62, hinges=186, repositioned_windows=12,
                           removed_redundant_backwalls=18)
    require(all(report.get(k) == v for k, v in expected_report.items()),
            'The detail-repair scope differs from the approved repair.')
    expected_stats = dict(grounded_posts=240, baseplates=240, total_pipes=60,
                          sloped_pipes=18, hinge_equipped_doors=62, hinge_sets=186,
                          stair_windows=12)
    require(all(detail['statistics'].get(k) == v for k, v in expected_stats.items()),
            'Fresh physical detail counts differ from the repair report.')
    design = plan.get('detail_design', {})
    constraints = design.get('constraints', {})
    require(constraints.get('passed') is True
            and len(constraints.get('plate_support_checks', [])) == 240
            and len(constraints.get('rail_endpoint_checks', [])) == 18
            and len(design.get('original_stair_windows', {})) == 12,
            'The stair/window geometric design proof is incomplete.')
    require(all(r.get('passed') is True for r in constraints['plate_support_checks']
                + constraints['rail_endpoint_checks']), 'A design support/connection proof failed.')
    props = plan['placed_props']
    hardware = [r for r in props if r.get('detail_kind') == 'door_hinge_assembly']
    tubes = [r for r in props if r.get('detail_kind') == 'round_handrail']
    require(len(hardware) == 124 and len(tubes) == 60,
            'Placed hinge assemblies or connected tubes are missing.')
    by_door = {}
    for row in hardware:
        by_door.setdefault(row['door_actor'], []).append(row)
    swing_actors = {r['actor'] for r in plan['placed_doors'] if r.get('kind') == 'swing'}
    require(set(by_door) == swing_actors and all(
        len(rows) == 2 and {r['parent_component'] for r in rows} == {'OpeningRoot', 'DoorHinge'}
        and all(r.get('collision') is False and r.get('hinge_count') == 3 for r in rows)
        for rows in by_door.values()), 'The fixed/moving nonblocking hinge attachments are incomplete.')
    check_names = {r['name'] for r in detail['checks']}
    required = {'floating_well_blocks_absent', 'top_floor_well_guards_present',
                'redundant_central_backwalls_absent'}
    required.update('hinge_attached:' + r['id'] for r in hardware)
    for row in plan['placed_windows']:
        if row.get('kind') == 'stair':
            required.update(prefix + row['id'] for prefix in (
                'window_above_platform:', 'window_below_slab:',
                'new_window_hole_clear:', 'old_window_hole_closed:'))
    require(required <= check_names, 'Fresh physical detail checks omitted repaired hinges or windows.')
    require(len([r for r in plan['placed_windows'] if r.get('kind') == 'stair']) == 12,
            'The 12 repaired staircase windows are incomplete.')
    return expected_report


def capture_review(build, mapfile):
    """Validate every current image and its owning helper/cleanup evidence."""
    lifecycle.WORK = WORK
    views, runs = [], {}
    digest = build['map_sha256']
    cameras = build['hotel_v4']['review_cameras']
    names = [r['camera'] for r in cameras]
    require(len(names) == len(set(names)) == 21, 'Exactly 21 distinct review cameras are required.')
    previous_cameras = read(SOURCE / 'BuildReport.json')['hotel_openings_review_cameras']
    require(set(names) == set(previous_cameras) | DETAIL_CAMERAS
            and names == build['hotel_openings_review_cameras'],
            'Current review camera manifest differs from the 15 existing and 6 detail views.')
    for view in cameras:
        camera, mode = view['camera'], view.get('lighting_mode', 'temporary')
        require(re.fullmatch(r'[A-Za-z0-9_]+', camera), 'Unsafe review camera name.')
        png = WORK / 'Renders' / (camera + '.png')
        metadata = read(png.with_suffix('.json'))
        data = png.read_bytes()
        require(data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR' and len(data) > 20000,
                'PNG is invalid or incomplete: ' + camera)
        dimensions = struct.unpack('>II', data[16:24])
        require(dimensions == (1280, 720) == (metadata.get('width'), metadata.get('height')),
                'PNG resolution differs: ' + camera)
        require(metadata.get('status') == 'PASS' and metadata.get('camera') == camera
                and metadata.get('target_level') == TARGET
                and metadata.get('map_sha256') == metadata.get('map_sha256_after_cleanup') == digest
                and metadata.get('png_sha256') == sha(png) and metadata.get('bytes') == len(data),
                'Current PNG hash or saved-map identity differs: ' + camera)
        require(metadata.get('lighting_mode') == mode
                and metadata.get('view_mode_requested') == metadata.get('view_mode_verified') == 'lit',
                'Capture lighting or view mode differs: ' + camera)
        require(metadata.get('source') == 'fresh_persisted_map_load'
                and metadata.get('fresh_map_load_verified') is True
                and Path(metadata['source_persisted_map']).resolve() == mapfile.resolve()
                and metadata.get('persisted_map_unchanged') is True
                and metadata.get('map_save_requested') is False,
                'Capture did not load the current saved map read-only: ' + camera)
        lighting = metadata.get('temporary_lighting', {})
        require(metadata.get('temporary_lighting_cleanup_verified_zero') is True
                and metadata.get('temporary_lighting_cleanup_remaining_count') == 0
                and lighting.get('mode') == mode and lighting.get('cleanup_verified_zero') is True
                and lighting.get('remaining_count') == 0 and not lighting.get('remaining_labels')
                and not lighting.get('errors') and lighting.get('created_count')
                == lighting.get('destroyed_count') == metadata.get('temporary_lighting_created_count'),
                'Temporary inspection lights were not fully cleaned: ' + camera)
        require((mode == 'temporary' and lighting['created_count'] > 0)
                or (mode == 'street_only' and lighting['created_count'] == 0),
                'Inspection light creation contradicts capture mode: ' + camera)
        run_id = metadata.get('run_id')
        runs[run_id] = lifecycle.helper_run(run_id, metadata, digest, TARGET, camera, mode)
        views.append(dict(camera=camera, png=str(png), metadata=str(png.with_suffix('.json')),
                          png_sha256=metadata['png_sha256'], bytes=len(data), lighting_mode=mode,
                          width=1280, height=720, view_mode='lit', run_id=run_id,
                          owned_editor_pid=metadata['owned_editor_pid'], fresh_persisted_map_load=True,
                          persisted_map_unchanged=True, temporary_lighting_cleanup_remaining_count=0))
    return dict(passed=True, status='PASS', map_sha256=digest, target_level=TARGET,
                views=views, current_helpers=list(runs.values()),
                fresh_persisted_map_load=True, current_helper_normal_exit_verified=True,
                temporary_lighting_cleanup_verified_zero=True,
                previous_failed_attempts_status='Historical diagnostics; only current PNG helper run IDs are validated.')


def validate():
    """Read-only preflight; returns complete reports without publishing them."""
    build = read(WORK / 'BuildReport.json')
    require(build.get('status') == 'PASS' and build.get('target_level') == TARGET,
            'Current build did not pass for the requested street.')
    mapfile = ROOT / ('Content/' + TARGET.removeprefix('/Game/') + '.umap')
    digest = sha(mapfile)
    require(build.get('map_sha256') == digest and digest != INPUT_MAP_SHA256,
            'Saved map changed after the detail repair, or the repair was not saved.')
    applied = read(WORK / 'Applied.json')
    require(applied.get('passed') is True and applied.get('map_sha256') == digest
            and applied.get('actor_count') == build['actor_count'], 'Applied marker is stale.')
    plan = read(WORK / 'ArchitecturePlan.json')
    require(plan == build.get('hotel_v4') == build.get('hotel_architecture'),
            'Current architecture plan differs from the saved build.')
    previous = read(SOURCE / 'BuildReport.json')
    architecture = current_audit('ArchitectureAudit.json', digest)
    detail = current_audit('DetailAudit.json', digest)
    before, after = read(WORK / 'InputSnapshot.json'), read(WORK / 'AfterSnapshot.json')
    baseline = read(WORK / 'PreservationBaseline.json')
    preservation = verify_preservation(build, plan, architecture, detail, before, after, baseline, previous)
    report = read(WORK / 'DetailRepairReport.json')
    statistics = verify_details(build, plan, detail, report)
    generated = (ROOT / 'Content/CodexGenerated').resolve()
    old_assets, all_assets = previous['new_asset_sha256'], build['new_asset_sha256']
    require(set(old_assets) <= set(all_assets)
            and all(all_assets[p] == h for p, h in old_assets.items()),
            'An earlier generated asset was replaced or lost from the immutable asset manifest.')
    require(all(Path(p).resolve().is_relative_to(generated) for p in all_assets),
            'A generated asset is outside CodexGenerated.')
    new_asset_count = hashes(all_assets, 'Generated assets')
    old_asset_count = hashes(old_assets, 'Earlier generated assets')
    surface_refinement=read(WORK/'SurfaceRefinement.json')
    require(surface_refinement.get('passed') is True and surface_refinement.get('map_sha256')==digest
            and surface_refinement.get('only_render_materials_changed') is True,
            'Final rear-wall render refinement is absent or stale.')
    material_reports=[read(SOURCE/'MaterialRepair.json'),read(WORK/'DetailMaterialRepair.json'),surface_refinement['original_assets_preserved']]
    for material in material_reports:
        require(material.get('passed') is True and not material.get('changed_original_files'),
                'Original material preservation failed.')
        hashes(material['original_asset_sha256'], 'Original material assets')
        require(all(all_assets.get(r['file']) == r['sha256'] for r in material.get('assets', [])),
                'A verified material asset is missing from the current immutable manifest.')
    geometry_file = WORK / 'GeometryAfter.json'
    geometry_hash = sha(geometry_file)
    geometry = read(geometry_file)
    summary = read(WORK / 'AfterSummary.json')
    require(summary.get('passed') is True and not summary.get('errors')
            and summary.get('map_sha256') == digest, 'AfterSummary is stale or failed.')
    require(geometry.get('map_sha256') == digest and not geometry.get('errors')
            and bool(geometry.get('components')), 'Saved render geometry is stale or incomplete.')
    require(summary['actors'] == build['actor_count']
            and summary['visible_components'] == len(geometry['components'])
            and summary['triangles'] == geometry['triangles']
            and summary['unique_meshes'] == geometry['unique_meshes'],
            'AfterSummary counts differ from the actual render triangle export.')
    require(all(not any(abs(float(v)) > 1e-8 for v in c.get('render_offset_cm', [0, 0, 0]))
                or c.get('wpo_verified_from_persisted_material') is True for c in geometry['components']),
            'A render offset was inferred instead of verified from the persisted material.')
    surfaces.WORK = WORK
    scans = surfaces.verify_scans(digest, geometry, geometry_hash, read(WORK / 'SavedScanSummary.json'))
    captures = capture_review(build, mapfile)
    visual = read(WORK / 'VisualReview.json')
    require(visual.get('passed') is True and not visual.get('errors')
            and visual.get('map_sha256') == digest and visual.get('target_level') == TARGET,
            'Visual review failed or belongs to another saved map.')
    reviewed = visual.get('views', [])
    captured = {v['camera']: v for v in captures['views']}
    require(len(reviewed) == len({v.get('camera') for v in reviewed}) == 21
            and {v.get('camera') for v in reviewed} == set(captured),
            'Visual review does not cover every one of the 21 current distinct views.')
    require(all(v.get('passed') is True and v.get('png_sha256') == captured[v['camera']]['png_sha256']
                for v in reviewed), 'Visual review does not match the current PNG hashes.')
    require(sha(mapfile) == digest and sha(geometry_file) == geometry_hash,
            'Map or geometry changed during publication checks.')
    hashes(all_assets, 'Generated assets')
    hashes(before['shared_asset_sha256'], 'Original shared assets')
    hashes(build['protected_map_sha256'], 'Protected maps')
    reviewed_at = datetime.now(timezone.utc).isoformat()
    evidence_files = [
        'BuildReport.json', 'Applied.json', 'ArchitecturePlan.json', 'ArchitectureAudit.json',
        'DetailAudit.json', 'DetailRepairReport.json', 'DetailMaterialRepair.json',
        'DetailDelta.json', 'CameraRefinement.json', 'SurfaceRefinement.json', 'ProtectedMapInputRebase.json', 'InputSnapshot.json', 'AfterSnapshot.json', 'AfterSummary.json',
        'PreservationBaseline.json', 'GeometryAfter.json', 'SavedScan.json',
        'SavedScanOcclusion.json', 'SavedScanSummary.json', 'VisualReview.json',
    ]
    audit = dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                 source_map_sha256=INPUT_MAP_SHA256, source='fresh_persisted_map_load',
                 persisted_map_unchanged=True, preservation=preservation, statistics=statistics,
                 surface_scans=scans, generated_asset_count=new_asset_count,
                 earlier_generated_assets_unchanged=old_asset_count,
                 current_evidence_file_sha256={n: sha(WORK / n) for n in evidence_files},
                 render_source='Persisted UE map, verified generated assets and actual render triangles.',
                 historical_blender_source_role='V4 Blender source remains a structural reference only.',
                 reviewed_utc=reviewed_at)
    captures['reviewed_utc'] = reviewed_at
    final = dict(passed=True, status='PASS', target_level=TARGET, map_sha256=digest,
                 source_map_sha256=INPUT_MAP_SHA256, actor_count=build['actor_count'], rooms=27,
                 storeys=4, detail_changes=statistics, validation=architecture['statistics'],
                 physical_detail_validation=detail['statistics'], preservation=preservation,
                 surface_scans=scans, current_bundle=str(WORK),
                 current_render_source=str(geometry_file), current_render_source_sha256=geometry_hash,
                 current_captures=captures['views'], current_helpers=captures['current_helpers'],
                 original_shared_assets_unchanged=True, earlier_generated_assets_unchanged=True,
                 MainHome_interaction_structure_preserved=True,
                 user_added_actors_preserved=['BP_ItemPickup', 'PointLight'],
                 historical_source_model_role=audit['historical_blender_source_role'],
                 limitations=[
                     'Coplanar scanning covers same-facing overlaps of at least 1cm2 within 0.03cm plane tolerance.',
                     'Fully buried internal overlap groups remain individually accounted for; exposed groups are zero.',
                     'Visual review covers static saved-map views; physical door/route checks are reported separately.',
                 ], reviewed_utc=reviewed_at)
    return dict(build=build, mapfile=mapfile, digest=digest, geometry_file=geometry_file,
                geometry_hash=geometry_hash, captures=captures, audit=audit, final=final)


def publish(result):
    build, digest = result['build'], result['digest']
    write(WORK / 'HotelDetailFinalAudit.json', result['audit'])
    write(WORK / 'CaptureReview.json', result['captures'])
    write(WORK / 'FinalReview.json', result['final'])
    names = [
        'BuildReport.json', 'Applied.json', 'ArchitectureAudit.json', 'DetailAudit.json',
        'DetailRepairReport.json', 'DetailMaterialRepair.json', 'CameraRefinement.json', 'SurfaceRefinement.json', 'ProtectedMapInputRebase.json', 'HotelDetailFinalAudit.json',
        'AfterSummary.json', 'SavedScan.json', 'SavedScanOcclusion.json',
        'SavedScanSummary.json', 'CaptureReview.json', 'VisualReview.json', 'FinalReview.json',
    ]
    require(sha(result['mapfile']) == digest
            and sha(result['geometry_file']) == result['geometry_hash'],
            'The map or render geometry changed before publication.')
    hashes(build['new_asset_sha256'], 'Generated assets')
    hashes(build['protected_map_sha256'], 'Protected maps')
    expected = {n: sha(WORK / n) for n in names}
    previous = read(CANON / 'CurrentEvidence.json')
    backup = WORK / 'BeforeCanonicalPublish'
    # Allow a repeat finalization while retaining the actual preceding bundle.
    if Path(previous.get('source_bundle', '')).resolve() == WORK.resolve():
        require((backup / 'CurrentEvidence.json').is_file(), 'Prior canonical evidence backup is missing.')
        previous = read(backup / 'CurrentEvidence.json')
    require(Path(previous.get('source_bundle', '')).resolve() == SOURCE.resolve()
            and previous.get('map_sha256') == INPUT_MAP_SHA256,
            'Canonical evidence moved to another phase; do not overwrite it.')
    backup.mkdir(parents=True, exist_ok=True)
    for name in sorted(set(names + ['CurrentEvidence.json']) | set(previous.get('current_reports', []))):
        require(Path(name).name == name and name.endswith('.json'), 'Unsafe prior report name.')
        source, destination = CANON / name, backup / name
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
    write(backup / 'BackupManifest.json', dict(
        backed_up_report_sha256={p.name: sha(p) for p in backup.glob('*.json') if p.name != 'BackupManifest.json'},
        historical_only=True, current_publication_map_sha256=digest))
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
        current_render_geometry=str(result['geometry_file']),
        current_render_geometry_sha256=result['geometry_hash'],
        current_actor_snapshot=str(WORK / 'AfterSnapshot.json'),
        current_actor_snapshot_sha256=sha(WORK / 'AfterSnapshot.json'),
        current_architecture_plan=str(WORK / 'ArchitecturePlan.json'),
        current_architecture_plan_sha256=sha(WORK / 'ArchitecturePlan.json'),
        previous_bundle=str(SOURCE), previous_evidence_status='historical',
        historical_report_backup=str(backup),
        historical_reports_not_current=sorted(set(previous.get('current_reports', [])) - set(names)),
        opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',
        source_model_role='Historical V4 Blender source is structural reference; saved UE map and generated render assets are current.',
        note='Supported stair posts, connected round rails, real door hinges and raised stair windows verified after a fresh saved-world audit, full-map surface scan and all 21 current captures.',
        published_utc=result['final']['reviewed_utc'])
    write(CANON / 'CurrentEvidence.json', evidence)
    require(sha(result['mapfile']) == digest, 'Publication unexpectedly changed the saved map.')
    return expected


def main(check_only=False):
    result = validate()
    published = {} if check_only else publish(result)
    print(json.dumps(dict(passed=True, check_only=check_only, map_sha256=result['digest'],
                          bundle=str(WORK), actors=result['build']['actor_count'],
                          captures=len(result['captures']['views']), exposed_coplanar_groups=0,
                          retained_buried_groups=result['audit']['surface_scans']['retained_buried_groups'],
                          published_report_sha256=published), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Validate without writing or publishing reports.')
    main(parser.parse_args().check_only)
