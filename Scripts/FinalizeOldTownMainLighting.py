"""Publish a backed-up two-light change after fresh saved readback and views."""
import argparse,os,re,shutil
from datetime import datetime,timezone
from OldTownMainLightingCommon import *
from FinalizeOldTownRealismRefinement import captures
CAMERAS=['CAM_StreetAccess_NightStreet','CAM_V4_Exterior','CAM_StreetAccess_Lamp','CAM_V4_TopGallery','CAM_V4_LobbyWide','CAM_V4_GuestTwin']
REPORTS=['Before.json','Applied.json','BuildReport.json','SourceLights.json','PreSaveProof.json',
    'BackupBeforeLighting.json','AfterSnapshot.json','LightAudit.json','GeometryInvariantProof.json',
    'ReadbackAudit.json','RunCompletion.json','VisualReview.json','CaptureReview.json','FinalReview.json']
def bound(row):
    assert sha(row['file'])==row['sha256'],row['file']
    return read(row['file'])
def target_world_proof(proof):
    assert proof['passed'] and proof['loaded_level_count']==1 and proof['loaded_level_packages']==[TARGET]
    assert proof['source_main_streaming_entry_absent']
def capture_bindings(proof,rows,digest):
    assert len(rows)==len(CAMERAS)==6 and len({r['camera'] for r in rows})==6
    by={r['camera']:r for r in rows};assert set(by)==set(CAMERAS)
    build_ref=ref(W/'BuildReport.json');owned_runs={}
    for row in proof['rows']:
        name=row['camera'];record=by[name];meta=bound(row['metadata'])
        assert meta['camera']==name and meta['target_level']==TARGET and meta['source_persisted_map']==str(MAP)
        assert meta['source_build_report']==build_ref and meta['temporary_lighting_created_count']==0
        assert meta['fresh_map_load_verified'] and meta['map_sha256_after_cleanup']==digest
        assert record['run_id']==meta['run_id'] and record['owned_editor_pid']==meta['owned_editor_pid']
        assert record['map_sha256']==digest and record['lighting_mode']=='street_only' and record['view_mode']=='lit'
        run_dir=W/'Captures/Runs'/meta['run_id'];assert run_dir.resolve().is_relative_to((W/'Captures/Runs').resolve())
        owned=read(run_dir/'OwnedProcess.json');batch=read(run_dir/'CaptureBatch.json')
        assert owned['normal_exit'] and owned['exit_code']==0 and not owned['forced_cleanup'] and owned['helper_has_exited']
        assert owned['map_save_requested'] is False and owned['cleanup_only_owned_process']
        assert owned['map_sha256']==owned['map_sha256_after']==digest and owned['persisted_map_unchanged']
        assert owned['run_id']==batch['run_id']==meta['run_id'] and owned['owned_editor_pid']==batch['owned_editor_pid']==meta['owned_editor_pid']
        assert batch['source_build_report']==build_ref and batch['map_save_requested'] is False
        assert batch['source']=='fresh_persisted_map_load' and batch['lighting_mode']=='street_only' and batch['view_mode']=='lit'
        light=batch['temporary_lighting']
        assert light['created_count']==light['destroyed_count']==light['remaining_count']==0 and not light['errors']
        assert light['cleanup_verified_zero'] and not light['remaining_labels']
        cameras=batch['requested_cameras'];assert 1<=len(cameras)<=4 and len(cameras)==len(set(cameras))
        assert batch['capture_count']==len(cameras) and set(cameras)=={n for n,r in by.items() if r['run_id']==meta['run_id']}
        assert owned['cameras']==cameras and name in cameras
        owned_runs[meta['run_id']]=dict(run_id=meta['run_id'],owned_editor_pid=meta['owned_editor_pid'],
            cameras=cameras,owned_process=ref(run_dir/'OwnedProcess.json'),capture_batch=ref(run_dir/'CaptureBatch.json'))
    return list(owned_runs.values())
def main(publish=False):
    pointer,files=frozen();before=read(W/'Before.json');applied=read(W/'Applied.json');audit=read(W/'ReadbackAudit.json')
    digest=sha(MAP);assert applied['passed'] and audit['passed'] and digest==applied['map_sha256']==audit['map_sha256']
    assert pointer['map_sha256']==before['map_sha256']==applied['source_map_sha256']==audit['source_map_sha256']
    assert before['source_current_evidence']==ref(CANON/'CurrentEvidence.json')
    assert before['accepted_source']==ref(S/'FinalReview.json') and files==before['protected_file_sha256']
    verify_files(files);backup=verify_backup(before['map_sha256']);assert applied['backup']==before['backup']==backup
    assert applied['actor_count']==audit['actor_count']==8016 and applied['new_assets']==audit['new_assets']==0
    assert set(applied['new_actor_labels'])==set(LABELS.values()) and audit['new_directional_actors']==2
    assert audit['original_actors_preserved']==8014 and audit['scene_components_preserved']==13920 and audit['asset_count']==1206
    assert applied['source_main_unchanged'] and not applied['assistant_main_map_write_allowed']
    assert audit['source_main_not_saved_by_assistant'] and audit['map_save_requested'] is False
    assert applied['old_directional_count']==applied['old_directional_hidden_count']==0
    geometry=bound(audit['geometry_invariant']);light=bound(audit['lights']);source=bound(applied['source_lights'])
    pre=bound(applied['pre_save_proof'])
    assert pre['passed'] and pre['source_main_level_removed'] and not pre['source_map_save_requested']
    assert pre['backup']==backup and pre['main_sha256']==before['main_sha256'] and pre['directional_lights']==2
    assert pre['all_original_actor_and_exact_component_states_preserved'] and pre['old_directional_hidden_count']==0
    target_world_proof(pre['target_only_world']);target_world_proof(audit['target_only_world'])
    assert geometry['passed'] and geometry['map_sha256']==digest and geometry['source_map_sha256']==before['map_sha256']
    assert geometry['exact_unrounded_scene_transforms_parent_visibility_mesh_material_collision_and_WPO_preserved']
    assert geometry['all_1206_asset_package_bytes_preserved'] and geometry['light_only_added_actors']==2
    assert geometry['new_static_mesh_components']==0 and geometry['accepted_geometry']==ref(S/'GeometryAfter.json')
    assert geometry['accepted_source']==before['accepted_source'] and geometry['source_actor_count']==8014 and geometry['source_scene_components']==13920
    assert geometry['geometry_reused_from_accepted_stage3_with_current_saved_invariant_proof']
    assert geometry['accepted_full_surface_scan']==ref(S/'SurfaceScanSummary.json')
    scan=read(S/'SurfaceScanSummary.json');assert scan['passed'] and scan['counts']['exposed_groups']==scan['counts']['exact_duplicate_box_groups']==0
    assert scan['provenance']['source_map_sha256']==before['map_sha256']
    assert scan['provenance']['source_geometry_sha256']==geometry['accepted_geometry']['sha256']
    assert light['passed'] and light['map_sha256']==digest and light['total_light_components']==21
    assert light['original_19_light_components_preserved'] and len(light['directional_lights'])==2
    assert len(light['lights'])==21 and {k:v for k,v in light['lights'].items() if k in before['lights']}==before['lights']
    assert len(set(light['lights'])-set(before['lights']))==2
    assert source['passed'] and source['main_sha256']==applied['source_main_sha256']==before['main_sha256']
    assert not source['source_map_save_requested']
    assert len(source['lights'])==2 and {r['label'] for r in source['lights']}==set(LABELS)
    assert {r['label'] for r in light['directional_lights']}==set(LABELS.values())
    for src in source['lights']:
        clone=next(r for r in light['directional_lights'] if r['label']==LABELS[src['label']])
        compare_light(src,clone)
    runs=read(W/'RunCompletion.json');assert runs['passed'] and len(runs['runs'])==2
    tokens={'Apply':'OLDTOWN_MAIN_DIRECTIONAL_APPLIED','Audit':'OLDTOWN_MAIN_DIRECTIONAL_READBACK_PASS'}
    assert {r['role'] for r in runs['runs']}==set(tokens)
    for run in runs['runs']:
        assert run['exit_code']==0 and run['normal_exit_observed_by_root'] and not run['forced_cleanup']
        assert not run['reused'] and run['map_sha256']==digest
        assert re.fullmatch(run['role']+r'\d+',run['name']) and run['log']['file']==str((W/(run['name']+'.log')).resolve())
        expected_report=W/('Applied.json' if run['role']=='Apply' else 'ReadbackAudit.json')
        assert run['output_report']==ref(expected_report)
        assert run['success_token']==tokens[run['role']] and sha(run['log']['file'])==run['log']['sha256']
        text=Path(run['log']['file']).read_text(encoding='utf-8-sig',errors='replace')
        assert run['success_token'] in text and 'LogExit: Exiting.' in text and 'Python script executed with errors' not in text
        assert re.search(re.escape(run['success_token'])+r'\s+'+re.escape(digest)+r'\b',text)
    build=read(W/'BuildReport.json');packages=pointer['current_asset_sha256']
    assert build['target_level']==TARGET and build['map_sha256']==digest and build['new_asset_sha256']==packages
    assert build['main_lighting']==ref(W/'Applied.json') and build['source_softgoods_report']==ref(S/'BuildReport.json')
    snapshot=read(W/'AfterSnapshot.json');assert snapshot['passed'] and snapshot['map_sha256']==digest and snapshot['target_level']==TARGET
    assert snapshot['actor_count']==len(snapshot['actors'])==8016 and set(snapshot['actors'])-set(before['actors'])==set(LABELS.values())
    assert {k:v for k,v in snapshot['actors'].items() if k in before['actors']}==before['actors']
    setup=read(S/'CaptureSetup.json')
    assert setup['scripts']=={str((R/'Scripts'/n).resolve()):sha(R/'Scripts'/n) for n in ('CaptureOldTownSoftGoodsViews.py','CaptureOldTownSoftGoodsViews.ps1')}
    proof=captures(W/'Captures',CAMERAS,'street_only',digest,packages)
    rows=read(W/'Captures/CaptureRuns.json');lifecycle=capture_bindings(proof,rows,digest)
    expected={r['image']['file']:r['image']['sha256'] for r in proof['rows']}
    visual=read(W/'VisualReview.json');assert visual['passed'] and visual['map_sha256']==digest and visual['image_sha256']==expected
    assert {r['file'] for r in visual['root_reviewed_frames'] if r['directly_viewed']}==set(expected)
    write(W/'CaptureReview.json',dict(passed=True,map_sha256=digest,source_build_report=ref(W/'BuildReport.json'),
        required_frames=6,lighting='actual saved lights without inspection fill',proof=proof,lifecycle=lifecycle,
        frozen_capture_helpers=setup['scripts']))
    result=dict(passed=True,published=bool(publish),target_level=TARGET,source_map_sha256=before['map_sha256'],map_sha256=digest,
        copied_directional_lights=2,old_directional_count=0,old_directional_hidden_count=0,
        old_directional_action='No previous directional light existed in the accepted saved target.',
        source_main_sha256_at_copy=source['main_sha256'],main_map_saved_by_assistant=False,
        backup=backup,readback=ref(W/'ReadbackAudit.json'),geometry_invariant=ref(W/'GeometryInvariantProof.json'),
        source_softgoods_final=ref(S/'FinalReview.json'),source_current_evidence=before['source_current_evidence'],
        accepted_geometry=geometry['accepted_geometry'],accepted_geometry_source_map_sha256=before['map_sha256'],
        accepted_surface_scan=geometry['accepted_full_surface_scan'],new_geometry_export_or_surface_scan=False,
        geometry_validation_method='Previously accepted whole-map triangles and scan plus fresh exact saved component and asset-byte invariant.',
        actor_count=8016,original_actors_preserved=8014,previous_scene_components_preserved=13920,
        total_light_components=21,current_asset_sha256=packages,new_asset_packages=0,emissive_fixture_count=16,
        captures=ref(W/'CaptureReview.json'),visual_review=ref(W/'VisualReview.json'),required_frames=6,
        limitations=visual['limitations'],completed_utc=datetime.now(timezone.utc).isoformat())
    write(W/'FinalReview.json',result)
    if publish:
        assert before['source_current_evidence']==ref(CANON/'CurrentEvidence.json')
        history=W/'BeforeCanonicalReports';history.mkdir(exist_ok=True)
        for name,d in pointer['current_report_sha256'].items():
            assert sha(CANON/name)==d;shutil.copy2(CANON/name,history/name);assert sha(history/name)==d
        hashes={name:sha(W/name) for name in REPORTS}
        for name,h in hashes.items():
            temporary=CANON/(name+'.lighting.tmp');shutil.copy2(W/name,temporary);assert sha(temporary)==h
            os.replace(temporary,CANON/name)
        verify_files(files);assert sha(MAP)==digest
        assert before['source_current_evidence']==ref(CANON/'CurrentEvidence.json')
        frozen()  # Old accepted source bundle must remain byte exact until pointer commit.
        current=dict(target_level=TARGET,map_sha256=digest,source_map_sha256=before['map_sha256'],source_bundle_name=W.name,
            source_directory=str(W),source_bundle=str(W),current_reports=REPORTS,current_report_sha256=hashes,
            current_asset_sha256=packages,current_final_review=str(W/'FinalReview.json'),current_final_review_sha256=hashes['FinalReview.json'],
            current_actor_snapshot=str(W/'AfterSnapshot.json'),current_actor_snapshot_sha256=hashes['AfterSnapshot.json'],
            current_render_geometry=geometry['accepted_geometry']['file'],current_render_geometry_sha256=geometry['accepted_geometry']['sha256'],
            current_render_geometry_source_map_sha256=before['map_sha256'],current_geometry_invariant=ref(W/'GeometryInvariantProof.json'),
            current_capture_directory=str(W/'Captures'),current_capture_runs_file=str(W/'Captures/CaptureRuns.json'),
            current_capture_runs_sha256=sha(W/'Captures/CaptureRuns.json'),current_render_cameras=CAMERAS,current_renders=expected,
            previous_bundle=str(S),previous_accepted_evidence=ref(S/'FinalReview.json'),source_current_evidence_before=before['source_current_evidence'],
            backup_before_lighting=backup,actor_count=8016,copied_directional_lights=2,old_directional_hidden_count=0,
            emissive_fixture_count=16,assistant_main_map_write_allowed=False,
            scope='Two complete saved Main directional actors copied to OldTown; all existing geometry, materials, local lights and collision preserved.',
            opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',published_utc=datetime.now(timezone.utc).isoformat())
        write(CANON/'CurrentEvidence.json.tmp',current);os.replace(CANON/'CurrentEvidence.json.tmp',CANON/'CurrentEvidence.json')
    print(json.dumps(dict(passed=True,published=bool(publish),map_sha256=digest,copied_directional_lights=2,backup=backup['file'])))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');main(p.parse_args().publish)
