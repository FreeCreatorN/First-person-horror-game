"""Verify an animation-only Notebook revision and fresh readback, without UE."""
import hashlib
import json
import traceback
from datetime import datetime,timezone
from pathlib import Path

UE=Path(__file__).resolve().parent
REV=UE.parent
OUT=REV.parent
PROJECT=OUT.parents[1]
CONTENT=PROJECT/'Content'
TARGET=CONTENT/'Yastars'/'Mesh'/'Notebook'
BEFORE=REV/'Before'
ROOT='/Game/Yastars/Mesh/Notebook'
result={'success':False,'checked_utc':datetime.now(timezone.utc).isoformat(),'target_root':ROOT}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


try:
    plan,before,model=read(UE/'update_plan.json'),read(BEFORE/'state_manifest.json'),read(OUT/'model_report.json')
    updated,reloaded,completion=read(UE/'update_ue_report.json'),read(UE/'ue_reload_report.json'),read(UE/'completion.json')
    assert plan['success'] and updated['success'] and reloaded['success'] and completion['success']
    assert updated['mode']=='animation_only_update' and reloaded['mode']=='verify_saved'
    assert updated['editor_pid']!=reloaded['editor_pid'] and len(completion['runs'])==2
    assert updated['run_id']==reloaded['run_id']==completion['run_id']
    assert updated['script_sha256']==reloaded['script_sha256']==completion['script_sha256']==sha(UE/'update_ue.py')
    assert updated['plan_sha256']==reloaded['plan_sha256']==completion['plan_sha256']==sha(UE/'update_plan.json')
    assert reloaded['update_report_sha256']==sha(UE/'update_ue_report.json')
    assert plan['before_manifest_sha256']==sha(BEFORE/'state_manifest.json')
    assert all(sha(path)==digest for path,digest in plan['preflight_scripts_sha256'].items())
    for report,run in zip((updated,reloaded),completion['runs']):
        assert run['normal_zero_exit'] and run['exit_code']==run['log_error_count']==0
        assert report['editor_pid']==run['editor_pid'] and report['mode']==run['mode']
        assert sha(run['report'])==run['report_sha256']
        assert utc(run['started_utc'])<=utc(report['started_utc'])<=utc(report['completed_utc'])<=utc(run['completed_utc'])
        assert report['world_before']==report['world_after'] and report['world_before'].startswith('/Engine/Maps/Entry')
        assert report['protected_content_unchanged'] and report['source_files_unchanged'] and report['unrelated_packages_unchanged']
        assert report['blueprint_references_verified'] and report['geometry']==updated['geometry']
        assert report['geometry']['triangles']==35756 and report['geometry']['bones']==156 and report['geometry']['materials']==38
        assert not any(report[key] for key in ('actors_spawned','map_save_executed','new_assets_created','asset_delete_executed','asset_rename_executed','geometry_materials_or_blueprints_saved'))
        assert set(report['poses'])==set(model['markers']) and len(report['clips'])==18
        for label,sample in report['poses'].items():
            marker=model['markers'][label]
            assert sample['frame']==marker['frame']
            for bone,position in model['source_marker_bone_locations_cm'][label].items():
                assert max(abs(a-b) for a,b in zip(sample['bones'][bone]['translation'],position))<=.02
            for bone,normal in model.get('source_marker_bone_normals',{}).get(label,{}).items():
                check=sample['normal_checks'][bone]
                assert check['source_normal']==normal and check['dot_error']<=.0001
        assert report['source_normal_checks']==sum(len(values) for values in model.get('source_marker_bone_normals',{}).values())
        for spec in model['clips']:
            clip=report['clips'][spec['name']]
            assert abs(clip['seconds']-spec['seconds'])<=.001
            assert set(clip['endpoints'])=={'start','end'}
            for sample in clip['endpoints'].values():
                assert sample['bone_count']==156 and sample['max_position_error_cm']<=.02 and sample['max_rotation_dot_error']<=.0001
    assert updated['fbx_backend_restored']
    assert not reloaded['saved_animation_packages']
    expected_updates={ROOT+'/'+name for name in plan['replace_names']}
    assert set(updated['saved_animation_packages'])==set(updated['updated_packages'])==expected_updates
    assert updated['updated_packages']==reloaded['updated_packages']
    assert {p.resolve() for p in TARGET.rglob('*.uasset')}=={Path(item['file']).resolve() for item in before['packages'].values()}
    for package,item in before['packages'].items():
        expected=updated['updated_packages'][package]['sha256'] if package in expected_updates else item['sha256']
        assert sha(item['file'])==expected
        if item['replace_allowed']:
            assert sha(item['backup'])==item['sha256']
        if package in expected_updates:
            assert item['replace_allowed'] and updated['updated_packages'][package]['before_sha256']==item['sha256']
    for name,spec in plan['animations'].items():
        assert spec['replace']==(spec['old_semantic']['sha256']!=spec['new_semantic']['sha256'])
    assert all(sha(path)==digest for path,digest in plan['sources_sha256'].items())
    protected=set(CONTENT.rglob('*.umap'))
    for directory in (PROJECT/'Config',CONTENT/'Yastar'/'UI',CONTENT/'Yastar'/'Items'):
        protected.update(path for path in directory.rglob('*') if path.is_file())
    assert {str(path.resolve()) for path in protected}==set(before['protected_files'])
    assert all(sha(path)==digest for path,digest in before['protected_files'].items())
    result.update(success=True,updated_animation_packages=len(expected_updates),preserved_package_count=76-len(expected_updates),
        unchanged_animations=plan['preserve_names'],package_count=76,protected_files_checked=len(protected),
        source_pose_samples=len(model['markers']),independent_clips=18,fresh_editor_persistence_verified=True,
        source_normal_checks=updated['source_normal_checks'],
        geometry_skeleton_materials_blueprints_unchanged=True,source_and_packages_sha256_verified=True)
except Exception:
    result['error']=traceback.format_exc()
(UE/'final_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('NOTEBOOK_NATURAL_FLIP_VERIFIED',result['success'])
if not result['success']:
    print(result['error'])
    raise SystemExit(1)
