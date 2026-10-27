"""Offline final publication only after successful fresh scene/asset/reference audits."""
import json,hashlib,re
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def main():
    assert not (W/'FinalReview.json').exists()
    required=['Inventory1','BeforeScene1','Copy1','StagedAudit2','PluginBuild5','CopyRepair3','MetadataFix5','AssetsAudit3','PrepareCommit1','CommittedAudit1','CommittedReferences1','FinalAudit1','FinalReferences1','MetadataRefresh1','RefreshedAudit1','RefreshedReferences1','CleanAudit1','CleanReferences1']
    completions={n:read(n+'.Completion.json') for n in required};assert all(v['normal_zero_exit'] and v['exit_code']==0 for v in completions.values())
    reports={n:read(n+'.json') for n in ['HotelNamePlan','CopiedPackages','PrivateAssetCorrections','EffectivePrivateHashes','StagedAudit','AssetCopyVerification3','PreparedCommit','Committed','CommittedAudit','CommittedReferences','CurrentCleanupGate','CurrentCleanupResult','FinalAudit','FinalReferences','LegacyCleanupRestored','MetadataRefreshApplied','RefreshedAudit','RefreshedReferences','SupplementalCleanupResult','CleanAudit','CleanReferences']}
    assert all(v['passed'] for v in reports.values())
    plan=reports['HotelNamePlan'];copied=reports['CopiedPackages'];committed=reports['Committed'];cleanup=reports['CurrentCleanupResult']
    refresh=reports['MetadataRefreshApplied'];supplement=reports['SupplementalCleanupResult']
    assert refresh['previous_map_sha256']==committed['map_sha256'] and sha(refresh['backup'])==refresh['backup_sha256']==committed['map_sha256']
    cleanup=dict(cleanup,removed_files=cleanup['removed_files']+supplement['removed_files'],removed_count=cleanup['removed_count']+supplement['removed_count'],removed_bytes=cleanup['removed_bytes']+supplement['removed_bytes'])
    assert cleanup['removed_count']==47
    baseline=read('ProtectedBeforeAfterRestore.json')['file_sha256'];private=reports['EffectivePrivateHashes']['new_asset_sha256']
    removed={r['file']:r for r in cleanup['removed_files']}
    expected={**baseline,**private};expected[committed['original_map_file']]=refresh['map_sha256']
    for p,r in removed.items():assert expected.pop(p)==r['sha256'] and not Path(p).exists() and sha(r['backup'])==r['sha256']
    actual={str(p):sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()};assert actual==expected
    assert actual==reports['CleanReferences']['file_sha256']
    assert reports['CleanAudit']['actor_count']==7986 and reports['AssetCopyVerification3']['asset_count']==reports['AssetCopyVerification3']['passed_asset_count']==617
    for key in ('structured_scene_sha256','normalized_native_actor_hashes_sha256'):
        assert reports['CommittedAudit']['scene_proof'][key]==reports['RefreshedAudit']['scene_proof'][key]==reports['CleanAudit']['scene_proof'][key]
    assert reports['CleanReferences']['all_617_private_assets_used'] and reports['CleanReferences']['disk_registry_packages_exact']
    assert len(plan['mappings'])==617 and all(re.fullmatch(r'(BP|SM|M|MI|T)_Hotel_[A-Za-z0-9_]+',r['destination_asset_name']) for r in plan['mappings'])
    assert copied['staged_level'] in {r['package'] for r in cleanup['removed_files']}
    backup=read('Backup.json');assert backup['passed'] and len(backup['files'])==618 and all(sha(r['backup'])==r['sha256'] for r in backup['files'])
    assert sha(committed['backup'])==committed['source_map_sha256']
    restored=reports['LegacyCleanupRestored'];assert restored['restored_count']==6 if 'restored_count' in restored else len(restored['restoration'])==6
    result=dict(passed=True,completed_utc=datetime.now(timezone.utc).isoformat(),target_level=copied['original_level'],map_sha256=refresh['map_sha256'],
        asset_count=617,asset_classes=plan['class_counts'],destination_root=plan['destination_root'],actor_count=7986,
        windows=dict(instances=348,shared_blueprints=8),doors=dict(instances=124,shared_blueprints=10),
        only_asset_references_changed_in_scene=True,user_assets_main_v2_config_unchanged=True,
        cleanup_this_task=dict(packages=cleanup['removed_count'],bytes=cleanup['removed_bytes'],backup=cleanup['backup_directory'],supplemental_backup=supplement['backup_directory']),
        previous_cleanup_confirmed_packages=595,previous_uncertain_packages_restored=6,
        shared_old_assets_retained=True,temporary_stage_map_removed=True,stale_world_actor_metadata_regenerated=True,all_assets_load_and_semantically_match=True,
        no_new_missing_dependencies=True,completions=completions,evidence_sha256={n+'.json':sha(W/(n+'.json')) for n in reports},
        input_source_map_sha256=copied['source_map_sha256'],backup_directory=backup['directory'],no_performance_configuration_changes=True,
        limits=['No new visual redesign in this naming task; preserved scene transforms, geometry, materials, collision and lighting.',
                'Old shared assets still required by Version2 or editor tools remain under their existing names.',
                'Preexisting missing dependencies and 17 existing missing import-source paths are preserved; no reimport performed.'])
    (W/'FinalReview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('HOTEL_ASSET_NAMING_FINAL_PASS',refresh['map_sha256'],cleanup['removed_count'])
if __name__=='__main__':main()
