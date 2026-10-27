"""Verify the copied current user world and publish V2 as the future work target."""
import argparse,json,os,re,shutil
from datetime import datetime,timezone
from pathlib import Path
from OldTownMainLightingCommon import R,sha,read,write,ref
from FinalizeOldTownRealismRefinement import captures
W=R/'Saved/CodexOutputs/OldTownVersion2_20261016';CANON=R/'Saved/CodexOutputs/EnterableStreet_20261002'
S=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
V2='/Game/CodexGenerated/OldTownVersion2/Maps/老城区第二版'
MAP=R/'Content/CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap'
ORIGINAL=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
REPORTS=['Input.json','UserMapBackup.json','Backup.json','UserEnvironmentBefore.json','CameraRemovalPlan.json',
    'V2Snapshot.json','CopiedBeforeCleanup.json','OriginalAfterCleanup.json','Created.json','ReadbackAudit.json',
    'ExistingDirectionalComparison.json','GeometryDerivation.json','GeometryReady.json','AfterSummary.json',
    'CoplanarScan.json','InternalOcclusionScan.json','SurfaceScanSummary.json','BuildReport.json','CaptureSetup.json',
    'InventoryPreviewReadOnly.json','PerformanceProposal.json','VisualReview.json','RunCompletion.json','CaptureReview.json','FinalReview.json']
def bound(r):
    assert sha(r['file'])==r['sha256'],r['file'];return read(r['file'])
def normalize_copy_paths(value,oldlevel):
    """Native SaveAs changes only the owning world's package/object prefix."""
    if isinstance(value,str):return value.replace(oldlevel+'.'+oldlevel.rsplit('/',1)[1],V2+'.老城区第二版')
    if isinstance(value,list):return [normalize_copy_paths(x,oldlevel) for x in value]
    if isinstance(value,dict):return {k:normalize_copy_paths(x,oldlevel) for k,x in value.items()}
    return value
def main(publish=False):
    # Reject a repeat before writing CaptureReview/FinalReview: published source
    # reports are immutable even when a later invocation is only a dry run.
    initial_pointer=read(CANON/'CurrentEvidence.json');initial_pointer_ref=ref(CANON/'CurrentEvidence.json')
    assert initial_pointer['source_bundle_name']!=W.name,'V2 is already published; do not rewrite its accepted source reports.'
    if publish:
        assert initial_pointer['source_bundle_name']=='OldTownRealismRefinement_20261013','Unexpected concurrent publication.'
    created=read(W/'Created.json');i=read(W/'Input.json');audit=read(W/'ReadbackAudit.json');v=read(W/'V2Snapshot.json')
    digest=sha(MAP);assert digest==created['version2_map_sha256']==v['map_sha256'] and created['target_level']==V2
    assert created['passed'] and audit['passed'] and i['passed'] and v['passed']
    assert created['source_user_map_sha256']==i['map_sha256'] and created['version2_actor_count']==8017
    assert created['original_actor_count']==7936 and created['original_camera_removed_count']==81
    assert created['original_map_future_write_allowed'] is False and created['future_assistant_work_target']==V2
    assert created['performance_changes_applied'] is False and created['extra_directional_lights_added']==0
    assert created['existing_user_directional_lights_preserved'] and created['shared_assets_read_only_future_changes_require_v2_owned_replacement']
    original=read(W/'OriginalAfterCleanup.json');plan=read(W/'CameraRemovalPlan.json')
    removed=set(plan['actors']);assert plan['passed'] and len(removed)==81 and set(original['removed_camera_labels'])==removed
    assert plan['count']==81 and plan['user_requested'] and plan['only_historical_generated_review_camera_actors']
    assert plan['player_cameras_and_scene_capture_components_preserved']
    historical=bound(plan['provenance'])['actors'];camera_rows={c['label']:c for c in i['cameras']}
    assert removed==set(camera_rows)
    for name in removed:
        state,old=i['actors'][name],historical[name]
        assert 'Camera' in old['class'] and name.startswith('CAM_') and old['folder'].startswith('OldTownSchoolStreet/')
        assert all(state[k]==old[k] for k in ('class','name','folder'))
        assert camera_rows[name]['actor_properties']['auto_activate_for_player']=='<AutoReceiveInput.DISABLED: 0>'
    assert original['actors']=={n:s for n,s in i['actors'].items() if n not in removed}
    assert v['actors']==i['actors'] and len(v['actors'])==8017
    oldlevel=created['source_level'];assert i['target_level']==original['target_level']==oldlevel and v['target_level']==V2
    expected_components={n:s for n,s in i['exact_scene_components'].items() if n.split('::',1)[0] not in removed}
    assert original['exact_scene_components']==expected_components
    assert v['exact_scene_components']==normalize_copy_paths(i['exact_scene_components'],oldlevel)
    env=read(W/'UserEnvironmentBefore.json');assert env['passed'] and env['map_sha256']==i['map_sha256']
    assert original['environment']==env['settings'] and v['environment']==normalize_copy_paths(env['settings'],oldlevel)
    assert original['lights']==v['lights']==i['light_inventory'] and len(v['lights'])==21
    copied=read(W/'CopiedBeforeCleanup.json')
    assert copied['passed'] and copied['source_original_not_saved_by_copy'] and copied['all_user_actor_component_and_environment_state_preserved']
    assert copied['original_map_sha256']==i['map_sha256'] and copied['version2_map_sha256']==digest
    assert copied['backup']==created['backup'] and copied['target_level']==V2 and copied['source_level']==oldlevel
    assert audit['original_user_edits_preserved'] and audit['all_shared_packages_unchanged'] and not audit['performance_changes_applied']
    assert audit['main_unchanged_from_copy'] and created['main_map_unchanged'] and created['shared_asset_files_unchanged']
    assert audit['original_map_future_write_allowed'] is False and audit['future_assistant_target']==V2
    assert original['map_sha256']==created['original_map_sha256_after_camera_cleanup']
    by={r['level']:r for r in audit['maps']}
    assert len(audit['maps'])==len(by)==2 and by[V2]['actors']==8017 and by[V2]['camera_actors']==81
    assert by[oldlevel]['actors']==7936 and by[oldlevel]['camera_actors']==0
    assert all(row['all_saved_actor_component_environment_and_light_states_preserved'] for row in by.values())
    assert by[V2]['scene_capture_components']==by[oldlevel]['scene_capture_components'] and len(by[V2]['scene_capture_components'])==1
    assert audit['map_hashes'][str(R/'Content/Yastar/Maps/L_Main.umap')]==created['main_map_sha256']==i['main_sha256']
    assert audit['map_hashes'][str(MAP)]==digest and audit['map_hashes'][str(ORIGINAL)]==original['map_sha256']
    backup=bound(created['backup']);manifest=bound(backup['manifest'])
    assert backup['passed'] and manifest['passed'] and manifest['completed_before_map_copy']
    assert backup['map_sha256']==manifest['user_map_sha256']==i['map_sha256'] and manifest['file_count']==backup['file_count']==2589
    assert manifest['source_input']==ref(W/'Input.json') and manifest['backup_directory']==backup['backup_directory']
    assert len(manifest['files'])==manifest['file_count']
    base=Path(backup['backup_directory']).resolve();assert base.is_relative_to((R/'Saved/CodexBackups').resolve())
    # Byte verification is repeated at acceptance, without restoring anything.
    backup_rows={}
    for row in manifest['files']:
        path=(base/row['relative_path']).resolve();assert path.is_relative_to(base)
        assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
        assert row['relative_path'] not in backup_rows,'Duplicate backup path: '+row['relative_path']
        backup_rows[row['relative_path']]=row
    assert sum(row['bytes'] for row in manifest['files'])==manifest['total_bytes']==backup['total_bytes']
    backup_map=base/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';assert sha(backup_map)==i['map_sha256']
    shared={**i['referenced_game_package_sha256'],**i['all_original_generated_file_sha256']}
    shared.pop(str(ORIGINAL),None);shared.pop(str(R/'Content/Yastar/Maps/L_Main.umap'),None)
    assert len(shared)==1576
    for source,h in shared.items():
        source_path=Path(source).resolve();assert source_path.is_relative_to(R)
        rel=source_path.relative_to(R).as_posix();assert rel in backup_rows and backup_rows[rel]['sha256']==h,'Backup omitted frozen package: '+source
    main_reference=manifest['main_reference_only'];assert main_reference['automatically_restore'] is False
    assert main_reference['sha256']==i['main_sha256'] and sha(base/main_reference['relative_path'])==i['main_sha256']
    user_backup=read(W/'UserMapBackup.json');assert user_backup['passed'] and sha(user_backup['file'])==user_backup['sha256']==i['map_sha256']
    dirs=read(W/'ExistingDirectionalComparison.json');assert dirs['passed'] and len(dirs['comparisons'])==2
    assert all(r['passed'] and r['reflected_properties_compared']==111 and r['all_actor_components_compared']==3 for r in dirs['comparisons'])
    geometry=read(W/'GeometryReady.json');derivation=bound(geometry['derivation']);geomref=geometry['geometry']
    assert geometry['passed'] and geometry['map_sha256']==digest and sha(geomref['file'])==geomref['sha256']
    assert derivation['passed'] and derivation['map_sha256']==digest and derivation['static_mesh_components_compared_exactly']==12361
    assert derivation['source_unrounded_world_pose_parent_mesh_material_collision_visibility_and_WPO_asset_bytes_equal']
    for key in ('source_native_geometry','source_native_appearance','source_native_preservation','source_audit','source_overlap_correction','fresh_user_input','fresh_v2_snapshot'):
        assert sha(derivation[key]['file'])==derivation[key]['sha256']
    assert read(S/'SourceAudit.json')['passed'] and read(S/'PreservationAudit.json')['passed']
    scan=read(W/'SurfaceScanSummary.json');assert scan['passed']
    assert scan['provenance']['source_map_sha256']==digest and scan['provenance']['source_geometry_sha256']==geomref['sha256']
    assert scan['counts']['exposed_groups']==scan['counts']['exact_duplicate_box_groups']==0
    scope,stats=scan['scope'],scan['stats']
    assert scope['component_count']==stats['visible_components']==8719 and scope['include_internal'] and not scope['axis_only']
    assert scope['plane_tolerance_cm']==.03 and scope['normal_tolerance']==.0001 and scope['minimum_overlap_area_cm2']==1.
    assert stats['input_faces']==stats['axis_faces_scanned']+stats['non_axis_faces_scanned']
    assert all(n==0 for k,n in stats.items() if 'skip' in k.lower())
    for key,name in [('scan','CoplanarScan.json'),('classified_scan','InternalOcclusionScan.json')]:
        assert Path(scan['provenance'][key+'_path']).resolve()==(W/name).resolve() and sha(W/name)==scan['provenance'][key+'_sha256']
    setup=read(W/'CaptureSetup.json');build=read(W/'BuildReport.json');packages=build['new_asset_sha256']
    assert setup['passed'] and setup['map_sha256']==build['map_sha256']==digest and build['target_level']==V2
    assert build['source_user_input']==ref(W/'Input.json') and build['source_v2_copy']==ref(W/'Created.json')
    assert setup['build_report']==ref(W/'BuildReport.json') and all(sha(s['file'])==s['sha256'] for s in setup['scripts'])
    assert packages==shared and all(sha(p)==h for p,h in packages.items())
    groups={}
    for folder,cameras,lighting in [('Captures',setup['actual_cameras'],'street_only'),('ModelCaptures',setup['model_cameras'],'temporary')]:
        rows=read(W/folder/'CaptureRuns.json');assert len(rows)==len(cameras)==len({r['camera'] for r in rows})
        proof=captures(W/folder,cameras,lighting,digest,packages)
        for row in proof['rows']:
            m=bound(row['metadata']);assert m['source_build_report']==ref(W/'BuildReport.json') and m['fresh_map_load_verified']
            assert m['map_sha256_after_cleanup']==digest
            if lighting=='street_only':assert m['temporary_lighting_created_count']==0
            owned=read(W/folder/'Runs'/m['run_id']/'OwnedProcess.json');batch=read(W/folder/'Runs'/m['run_id']/'CaptureBatch.json')
            assert owned['normal_exit'] and owned['exit_code']==0 and not owned['forced_cleanup']
            assert batch['source_build_report']==ref(W/'BuildReport.json')
        groups[folder]=proof
    images={r['image']['file']:r['image']['sha256'] for group in groups.values() for r in group['rows']}
    visual=read(W/'VisualReview.json');assert visual['passed'] and visual['map_sha256']==digest and visual['image_sha256']==images and len(images)==8
    assert {r['file'] for r in visual['root_reviewed_frames'] if r['directly_viewed']}==set(images)
    runs=read(W/'RunCompletion.json');assert runs['passed']
    tokens={'CurrentInput':'USER_OLDTOWN_V2_INPUT_PASS','Create':'OLDTOWN_VERSION2_CREATED',
        'Readback':'OLDTOWN_VERSION2_READBACK_PASS','PreviewCost':'INVENTORY_PREVIEW_COST_READONLY_PASS'}
    assert len(runs['runs'])==len(tokens) and set(tokens)=={r['role'] for r in runs['runs']}
    for row in runs['runs']:
        assert row['exit_code']==0 and row['normal_exit_observed_by_root'] and not row['forced_cleanup']
        assert row['success_token']==tokens[row['role']]
        log=Path(row['log']['file']);assert sha(log)==row['log']['sha256']
        text=log.read_text(encoding='utf-8-sig',errors='replace')
        assert row['success_token'] in text and 'LogExit: Exiting.' in text and 'Python script executed with errors' not in text
    preview=read(W/'InventoryPreviewReadOnly.json');assert preview['passed'] and preview['map_sha256']==digest and preview['no_performance_changes_applied']
    assert preview['map_save_requested'] is False
    proposal=read(W/'PerformanceProposal.json')
    assert proposal['status']=='review_required_no_performance_changes_applied' and proposal['changes_applied']==[]
    assert proposal['v2_isolation']['all_assets_independently_duplicated'] is False
    assert proposal['v2_isolation']['original_map_future_write_allowed'] is False and proposal['v2_isolation']['version2_level']==V2
    write(W/'CaptureReview.json',dict(passed=True,map_sha256=digest,required_frames=8,groups=groups))
    result=dict(passed=True,published=bool(publish),target_level=V2,map_sha256=digest,source_user_map_sha256=i['map_sha256'],
        original_map_sha256_after_assistant_cleanup=original['map_sha256'],original_map_sha256_current_observed=sha(ORIGINAL),
        original_user_edits_preserved=True,original_camera_actors_removed=81,version2_camera_actors=81,
        version2_actors=8017,original_actors_after_cleanup=7936,backup=ref(W/'Backup.json'),
        adopted_existing_user_main_matching_directional_lights=2,extra_directional_lights_added=0,
        source_model_refinement=dict(models=20,components=222,source_audit=ref(S/'SourceAudit.json'),
            native_preservation=ref(S/'PreservationAudit.json'),legacy_overlap_correction=ref(S/'OverlapCorrection.json')),
        current_geometry=geomref,geometry_derivation=ref(W/'GeometryDerivation.json'),whole_map_scan=ref(W/'SurfaceScanSummary.json'),
        fresh_map_readback=ref(W/'ReadbackAudit.json'),capture_review=ref(W/'CaptureReview.json'),visual_review=ref(W/'VisualReview.json'),
        current_asset_sha256=packages,performance_changes_applied=False,performance_proposal=ref(W/'PerformanceProposal.json'),
        performance_review_document=dict(file=str(W/'PerformanceProposal.md'),sha256=sha(W/'PerformanceProposal.md')),
        future_assistant_work_target=V2,original_map_future_write_allowed=False,
        shared_asset_policy='Shared assets remain read only. Future replacement assets must be duplicated into OldTownVersion2 before editing or assignment.',
        acceptance_verifier=ref(Path(__file__)),
        limitations=visual['limitations'],completed_utc=datetime.now(timezone.utc).isoformat())
    write(W/'FinalReview.json',result)
    if publish:
        before=W/'BeforeCanonical';before.mkdir(exist_ok=True)
        pointer=read(CANON/'CurrentEvidence.json');pointer_ref=ref(CANON/'CurrentEvidence.json')
        assert pointer_ref==initial_pointer_ref,'Unexpected concurrent publication.'
        assert pointer['source_bundle_name']=='OldTownRealismRefinement_20261013','Unexpected concurrent publication.'
        shutil.copy2(CANON/'CurrentEvidence.json',before/'CurrentEvidence.json')
        assert sha(before/'CurrentEvidence.json')==pointer_ref['sha256']
        for name,h in pointer['current_report_sha256'].items():
            assert Path(name).name==name and sha(CANON/name)==h;shutil.copy2(CANON/name,before/name)
            assert sha(before/name)==h
        hashes={n:sha(W/n) for n in REPORTS}
        for name,h in hashes.items():
            tmp=CANON/(name+'.v2.tmp');shutil.copy2(W/name,tmp);assert sha(tmp)==h
        assert sha(MAP)==digest and all(sha(p)==h for p,h in packages.items())
        assert all(sha(W/n)==h for n,h in hashes.items()) and ref(CANON/'CurrentEvidence.json')==pointer_ref
        for name in hashes:os.replace(CANON/(name+'.v2.tmp'),CANON/name)
        current=dict(target_level=V2,map_sha256=digest,source_bundle_name=W.name,source_directory=str(W),source_bundle=str(W),
            current_reports=REPORTS,current_report_sha256=hashes,current_final_review=str(W/'FinalReview.json'),
            current_final_review_sha256=hashes['FinalReview.json'],current_asset_sha256=packages,
            current_actor_snapshot=str(W/'V2Snapshot.json'),current_actor_snapshot_sha256=hashes['V2Snapshot.json'],
            current_render_geometry=geomref['file'],current_render_geometry_sha256=geomref['sha256'],
            current_geometry_derivation=ref(W/'GeometryDerivation.json'),current_capture_directory=str(W/'Captures'),
            current_capture_runs_file=str(W/'Captures/CaptureRuns.json'),current_capture_runs_sha256=sha(W/'Captures/CaptureRuns.json'),
            current_render_cameras=setup['actual_cameras'],current_model_capture_directory=str(W/'ModelCaptures'),current_renders=images,
            original_user_map=str(ORIGINAL),original_map_future_write_allowed=False,original_camera_actors_removed=81,
            future_assistant_work_target=V2,shared_asset_policy=result['shared_asset_policy'],
            acceptance_verifier=result['acceptance_verifier'],
            performance_changes_applied=False,performance_review_document=result['performance_review_document'],
            backup_before_version2=ref(W/'Backup.json'),source_current_evidence_before=dict(file=str(before/'CurrentEvidence.json'),sha256=pointer_ref['sha256']),
            previous_bundle=pointer['source_directory'],actor_count=8017,emissive_fixture_count=16,
            opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',published_utc=datetime.now(timezone.utc).isoformat())
        write(CANON/'CurrentEvidence.json.tmp',current);os.replace(CANON/'CurrentEvidence.json.tmp',CANON/'CurrentEvidence.json')
    print(json.dumps(dict(passed=True,published=bool(publish),target_level=V2,map_sha256=digest,cameras_removed=81),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');main(p.parse_args().publish)
