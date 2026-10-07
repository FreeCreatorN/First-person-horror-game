"""Publish the saved street refinement after independent audit/capture checks.

Only the metadata for the five current images selects their helper runs. Older
failed helper attempts remain available as diagnostics and are never promoted
to successful current captures.
"""
import hashlib
import json
import re
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/StreetRefinement_20261007'
BASE = ROOT / 'Saved/CodexOutputs/OpeningRelocation_20261007'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
SOURCE = ROOT / 'SourceArt/OldTownStreetRefinement_20261007'
OPENINGS = '/Game/CodexGenerated/OldTown/Blueprints/Openings'
REPORTS = ['BuildReport.json', 'StreetRefinementAudit.json',
           'ArchitectureAudit.json', 'OperationsAudit.json',
           'InputRebaseReport.json', 'SignUVRepair.json', 'VisualReview.json',
           'CaptureReview.json', 'FinalReview.json']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    pending = path.with_name(path.name + '.tmp')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def current_audit(name, digest, target):
    result = read(WORK / name)
    require(result.get('passed') is True, name + ' has not passed.')
    require(result.get('map_sha256') == digest, name + ' belongs to another map hash.')
    if 'target_level' in result:
        require(result['target_level'] == target, name + ' belongs to another level.')
    require(not result.get('errors'), name + ' has recorded errors.')
    return result


def helper_run(run_id, metadata, digest, target, camera, lighting_mode):
    require(isinstance(run_id, str) and re.fullmatch(r'[A-Za-z0-9_-]+', run_id),
            'Unsafe or missing capture run ID for ' + camera)
    run_dir = WORK / 'Runs' / run_id
    owned = read(run_dir / 'OwnedProcess.json')
    shutdown = read(run_dir / 'ShutdownRequest.json')
    batch = read(run_dir / 'CaptureBatch.json')
    pid = metadata['owned_editor_pid']
    require(owned.get('run_id') == shutdown.get('run_id') == batch.get('run_id') == run_id,
            'Capture helper run identity differs for ' + camera)
    require(owned.get('owned_editor_pid') == shutdown.get('owned_editor_pid')
            == batch.get('owned_editor_pid') == pid, 'Capture helper PID differs for ' + camera)
    require(owned.get('normal_exit') is True and owned.get('helper_has_exited') is True
            and owned.get('exit_code') == 0 and owned.get('forced_cleanup') is False
            and owned.get('lifecycle_status') == 'NORMAL_EXIT',
            'The current image helper did not exit normally: ' + run_id)
    require(owned.get('map_sha256') == owned.get('map_sha256_after') == digest
            and owned.get('persisted_map_unchanged') is True,
            'The current image helper changed the map: ' + run_id)
    require(owned.get('lighting_mode') == lighting_mode and owned.get('view_mode') == 'lit'
            and camera in owned.get('cameras', []), 'Helper capture parameters differ for ' + camera)
    require(Path(owned['output_directory']).resolve() == WORK.resolve()
            and owned.get('window_style') == 'Hidden'
            and owned.get('map_save_requested') is False
            and owned.get('no_auto_save') is True
            and owned.get('cleanup_only_owned_process') is True,
            'Helper ownership/output evidence differs for ' + camera)
    require(shutdown.get('status') == 'REQUESTED'
            and shutdown.get('keep_alive_released') is True
            and shutdown.get('deferred_quit_returned') is True
            and shutdown.get('map_save_requested') is False
            and owned.get('shutdown_request') == shutdown,
            'Normal shutdown request is not verified: ' + run_id)
    lighting = batch.get('temporary_lighting', {})
    require(batch.get('status') == 'PASS' and batch.get('target_level') == target
            and batch.get('map_sha256') == batch.get('map_sha256_after_cleanup') == digest
            and batch.get('source') == 'fresh_persisted_map_load'
            and batch.get('persisted_map_unchanged') is True
            and batch.get('map_save_requested') is False
            and batch.get('lighting_mode') == lighting_mode
            and batch.get('view_mode') == 'lit'
            and camera in batch.get('requested_cameras', [])
            and lighting.get('cleanup_verified_zero') is True
            and lighting.get('remaining_count') == 0
            and not lighting.get('remaining_labels') and not lighting.get('errors'),
            'Capture batch cleanup/provenance failed: ' + run_id)
    launched = datetime.fromisoformat(owned['launch_time_utc'].replace('Z', '+00:00')).timestamp()
    require((WORK / 'Renders' / (camera + '.png')).stat().st_mtime >= launched
            and (WORK / 'Renders' / (camera + '.json')).stat().st_mtime >= launched,
            'Current files predate their capture helper: ' + camera)
    archive = run_dir / 'Renders' / (camera + '.png')
    archived_metadata = read(archive.with_suffix('.json'))
    require(archive.is_file() and sha(archive) == metadata['png_sha256']
            and archived_metadata == metadata, 'Current files differ from their run archive: ' + camera)
    return dict(run_id=run_id, owned_editor_pid=pid, normal_exit=True, exit_code=0,
                forced_cleanup=False, persisted_map_unchanged=True,
                owned_process=str(run_dir / 'OwnedProcess.json'),
                shutdown_request=str(run_dir / 'ShutdownRequest.json'),
                capture_batch=str(run_dir / 'CaptureBatch.json'))


def captures_for(build, mapfile):
    digest, target = build['map_sha256'], build['target_level']
    views = build['street_refinement']['review_cameras']
    names = [view['camera'] for view in views]
    require(len(names) == len(set(names)) == 5, 'Five distinct refinement review cameras are required.')
    modes = [view['lighting_mode'] for view in views]
    require(modes.count('temporary') == 4 and modes.count('street_only') == 1,
            'Review requires four inspection views and one street-light-only view.')
    captures, selected_runs = [], {}
    for view in views:
        camera, mode = view['camera'], view['lighting_mode']
        require(re.fullmatch(r'[A-Za-z0-9_]+', camera), 'Unsafe camera label.')
        png = WORK / 'Renders' / (camera + '.png')
        metadata_file = png.with_suffix('.json')
        metadata = read(metadata_file)
        image = png.read_bytes()
        require(len(image) > 20000 and image[:8] == b'\x89PNG\r\n\x1a\n'
                and image[12:16] == b'IHDR', 'Invalid or incomplete PNG for ' + camera)
        dimensions = struct.unpack('>II', image[16:24])
        require(dimensions == (1280, 720)
                and dimensions == (metadata.get('width'), metadata.get('height')),
                'Actual capture resolution differs for ' + camera)
        require(metadata.get('status') == 'PASS' and metadata.get('camera') == camera
                and metadata.get('target_level') == target
                and metadata.get('map_sha256') == metadata.get('map_sha256_after_cleanup') == digest
                and metadata.get('png_sha256') == sha(png)
                and metadata.get('bytes') == len(image), 'Capture hash/identity differs for ' + camera)
        require(metadata.get('lighting_mode') == mode
                and metadata.get('view_mode_requested') == metadata.get('view_mode_verified') == 'lit',
                'Capture lighting/view mode differs for ' + camera)
        require(metadata.get('source') == 'fresh_persisted_map_load'
                and metadata.get('fresh_map_load_verified') is True
                and Path(metadata['source_persisted_map']).resolve() == mapfile.resolve()
                and metadata.get('persisted_map_unchanged') is True
                and metadata.get('map_save_requested') is False,
                'Capture is not a fresh unchanged saved-map load: ' + camera)
        lighting = metadata.get('temporary_lighting', {})
        require(metadata.get('temporary_lighting_cleanup_verified_zero') is True
                and metadata.get('temporary_lighting_cleanup_remaining_count') == 0
                and lighting.get('mode') == mode
                and lighting.get('cleanup_verified_zero') is True
                and lighting.get('remaining_count') == 0
                and not lighting.get('remaining_labels') and not lighting.get('errors')
                and lighting.get('created_count') == lighting.get('destroyed_count')
                == metadata.get('temporary_lighting_created_count'),
                'Temporary-light cleanup is incomplete for ' + camera)
        require((mode == 'temporary' and lighting['created_count'] > 0)
                or (mode == 'street_only' and lighting['created_count'] == 0),
                'Temporary-light creation contradicts the recorded mode for ' + camera)
        run_id = metadata.get('run_id')
        selected_runs[run_id] = helper_run(run_id, metadata, digest, target, camera, mode)
        captures.append(dict(camera=camera, png=str(png), metadata=str(metadata_file),
                             png_sha256=metadata['png_sha256'], bytes=len(image),
                             width=dimensions[0], height=dimensions[1], lighting_mode=mode,
                             view_mode='lit', run_id=run_id,
                             owned_editor_pid=metadata['owned_editor_pid'],
                             fresh_persisted_map_load=True, persisted_map_unchanged=True,
                             temporary_lighting_cleanup_remaining_count=0))
    recorded_runs = []
    for path in sorted((WORK / 'Runs').glob('*/OwnedProcess.json')):
        try:
            evidence = read(path)
            recorded_runs.append(dict(run_id=path.parent.name, owned_process=str(path),
                                      used_for_current_images=path.parent.name in selected_runs,
                                      lifecycle_status=evidence.get('lifecycle_status'),
                                      exit_code=evidence.get('exit_code'),
                                      normal_exit=evidence.get('normal_exit'),
                                      forced_cleanup=evidence.get('forced_cleanup')))
        except (OSError, ValueError):
            require(path.parent.name not in selected_runs, 'Current helper evidence is unreadable.')
            recorded_runs.append(dict(run_id=path.parent.name, owned_process=str(path),
                                      used_for_current_images=False, lifecycle_status='UNREADABLE_HISTORICAL_RECORD'))
    return dict(passed=True, status='PASS', target_level=target, map_sha256=digest,
                views=captures, current_helpers=list(selected_runs.values()),
                all_recorded_helper_runs=recorded_runs, current_helper_normal_exit_verified=True,
                temporary_lighting_cleanup_verified_zero=True,
                previous_failed_attempts_status='Historical diagnostics; only current image run IDs were validated.',
                validation='PNG identity, saved-map provenance, view modes, cleanup and helper lifecycle.')


def main():
    build = read(WORK / 'BuildReport.json')
    digest, target = build['map_sha256'], build['target_level']
    require(target == '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet', 'Unexpected refinement map.')
    mapfile = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    require(sha(mapfile) == digest, 'Saved map changed after the refinement audit.')
    require(all(Path(path).is_file() and sha(Path(path)) == expected
                for path, expected in build['protected_map_sha256'].items()),
            'A protected map changed after the refinement audit.')
    audit = current_audit('StreetRefinementAudit.json', digest, target)
    architecture = current_audit('ArchitectureAudit.json', digest, target)
    operations = current_audit('OperationsAudit.json', digest, target)
    required_checks = {'fresh_reload_matches_saved_actor_snapshot',
                       'unlisted_existing_actors_unchanged', 'shared_assets_unchanged',
                       'protected_maps_unchanged', 'read_only_audit_did_not_change_saved_map',
                       'full_hotel_architecture_operations_and_circulation'}
    successful_checks = {check['name'] for check in audit.get('checks', []) if check.get('passed') is True}
    require(required_checks <= successful_checks, 'Required saved-world checks are missing.')
    rebase = read(WORK / 'InputRebaseReport.json')
    require(rebase.get('passed') is True and rebase.get('all_current_user_changes_preserved') is True
            and rebase.get('source_map_sha256') == build['source_map_sha256'],
            'Current user edits are not covered by the input preservation report.')
    refinement = build['street_refinement']
    require(len(refinement['lamp_moves']) == 9 and len(refinement['directional_lights']) == 8
            and len(refinement['pole_moves']) == 5 and len(refinement['wire_adjustments']) == 3
            and len(refinement['allowed_changed_labels']) == len(set(refinement['allowed_changed_labels'])) == 25
            and len(refinement['new_signs']) == 9
            and len(refinement['new_actor_labels']) == len(set(refinement['new_actor_labels'])) == 14,
            'Unexpected refinement scope.')
    require(audit['statistics']['actors'] == build['actor_count']
            and audit['statistics']['allowed_changed_actors'] == 25
            and audit['statistics']['new_actors'] == 14, 'Audit scope differs from the build.')
    for sign in refinement['new_signs']:
        source = SOURCE / sign['source_file']
        require(source.resolve().parent == SOURCE.resolve() and source.is_file()
                and sha(source) == sign['source_sha256'], 'Sign source differs: ' + sign['actor'])
    require(all(sha(Path(p))==h for p,h in build['new_asset_sha256'].items()),'New sign asset fingerprint changed.')
    uv=read(WORK/'SignUVRepair.json')
    require(uv.get('passed') is True and uv.get('map_unchanged') is True and uv.get('map_sha256')==digest,
            'Sign UV orientation repair is not verified.')
    visual=read(WORK/'VisualReview.json')
    require(visual.get('passed') is True and visual.get('map_sha256')==digest and len(visual.get('views',[]))==5,
            'Five current images need a visual review.')
    for view in visual['views']:
        require(view.get('passed') is True and sha(WORK/'Renders'/(view['camera']+'.png'))==view['png_sha256'],
                'Visual review does not match the current image: '+view['camera'])
    relocations = build.get('asset_relocations', [])
    require(len(relocations) == 11, 'Opening relocation inventory is missing.')
    require(not (ROOT / 'Content/Yastar/Blueprints/OldTownOpenings_20261004').exists(),
            'The retired generated opening folder has reappeared.')
    relocation_review = read(BASE / 'FinalReview.json')
    require(relocation_review.get('passed') is True and relocation_review.get('new_folder') == OPENINGS,
            'The completed opening relocation evidence is missing.')
    capture_review = captures_for(build, mapfile)
    now = datetime.now(timezone.utc).isoformat()
    capture_review['reviewed_at_utc'] = now
    write(WORK / 'CaptureReview.json', capture_review)
    final = dict(passed=True, status='PASS', target_level=target, map_sha256=digest,
                 source_map_sha256=build['source_map_sha256'], actor_count=build['actor_count'],
                 changes='Curb-side lamp/pole positions, connected wires and guesthouse wayfinding signs.',
                 changed_existing_actors=25, new_actors=14, lamps=9, directional_lights=8,
                 utility_pole_parts=5, connected_wires=3, signs=9, review_cameras=5,
                 statistics=audit['statistics'], hotel_statistics=audit.get('hotel_statistics', {}),
                 architecture_checks=len(architecture.get('checks', [])),
                 operations_checks=len(operations.get('checks', [])),
                 external_actor_changes=rebase.get('external_actor_changes', []),
                 all_current_user_changes_preserved=True, protected_maps_unchanged=True,
                 roads_sidewalks_and_open_alleys_preserved=True,
                 captures=capture_review['views'], current_helpers=capture_review['current_helpers'],
                 opening_blueprints=dict(folder=OPENINGS, moved_blueprints=11,
                                         old_folder_removed=True, relocation_evidence=str(BASE / 'FinalReview.json')),
                 generated_refinement_assets='/Game/CodexGenerated/OldTown/StreetRefinement_20261007',
                 sign_uv_orientation_corrected=True,visual_review_passed=True,
                 previous_evidence=str(BASE / 'FinalReview.json'), previous_evidence_status='historical',
                 reviewed_at_utc=now,
                 limitations=['Door/window player interaction and functioning lift remain pending.',
                              'Four images use temporary inspection lighting; one uses existing street lights only.',
                              'No complete runtime player walkthrough was performed.'])
    write(WORK / 'FinalReview.json', final)
    require(sha(mapfile) == digest and all(sha(Path(path)) == expected
                for path, expected in build['protected_map_sha256'].items()),
            'Maps changed during final evidence validation.')
    before = WORK / 'BeforeCanonicalPublish'
    old = read(CANON / 'CurrentEvidence.json')
    if Path(old['source_bundle']).resolve() == WORK.resolve():
        require((before / 'CurrentEvidence.json').is_file(), 'Prior canonical evidence backup is missing.')
        old = read(before / 'CurrentEvidence.json')
    require(Path(old['source_bundle']).resolve() == BASE.resolve(), 'Canonical evidence moved to another phase.')
    before.mkdir(exist_ok=True)
    for name in sorted(set(REPORTS + old['current_reports'] + ['CurrentEvidence.json'])):
        require(Path(name).name == name and name.endswith('.json'), 'Unsafe report filename.')
        previous = CANON / name
        if previous.is_file() and not (before / name).exists():
            shutil.copy2(previous, before / name)
    for name in REPORTS:
        shutil.copy2(WORK / name, CANON / name)
    views = refinement['review_cameras']
    write(CANON / 'CurrentEvidence.json', dict(
        target_level=target, map_sha256=digest, source_bundle=str(WORK), source_directory=str(WORK),
        current_reports=REPORTS, current_report_sha256={name: sha(WORK / name) for name in REPORTS},
        current_renders=str(WORK / 'Renders'), current_render_cameras=[view['camera'] for view in views],
        current_render_lighting_modes={view['camera']: view['lighting_mode'] for view in views},
        previous_bundle=str(BASE), previous_evidence_bundle=str(BASE), previous_evidence_status='historical',
        previous_renders=old.get('current_renders') or old.get('previous_renders'),
        previous_render_status='historical_map_hash', historical_report_backup=str(before),
        historical_reports_not_current=sorted(set(old['current_reports']) - set(REPORTS)),
        opening_blueprints_folder=OPENINGS, opening_blueprints_relocation_evidence=str(BASE / 'FinalReview.json'),
        note='Current images are independently verified at this map hash. OpeningRelocation and earlier images remain historical.',
        limitations=final['limitations'], external_user_light_deletion_preserved=True,
        preserved_external_deletions=['PointLight']))
    print(json.dumps(dict(passed=True, map_sha256=digest, lamps=9, signs=9,
                          views=len(capture_review['views']), current_helpers=len(capture_review['current_helpers']))))


if __name__ == '__main__':
    main()
