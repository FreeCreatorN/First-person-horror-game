"""Verify saved replacement packages and preserve the project's UI and maps."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[2]
CONTENT=PROJECT/'Content'
ROOT='/Game/Yastars/Mesh/Envelope'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def package_file(package):return CONTENT/(package[6:]+'.uasset')
report={'success':False,'checked_utc':datetime.now(timezone.utc).isoformat()}
try:
    validation=read('validation_report.json');model=read('model_report.json')
    imported=read('ue_import_report.json');completed=read('import_set_completion.json')
    review=read('review_geometry_report.json')
    assert validation['success'] and imported['success'] and review['success']
    assert completed['normal_zero_exit'] and completed['exit_code']==0
    assert imported['completed_utc']>=completed['started_utc']
    assert imported['same_world_object'] and not imported['map_save_executed']
    assert not imported['level_load_executed'] and imported['actors_spawned']==0
    packages=set(imported['new_packages_on_disk'])
    assert len(packages)==15 and imported['new_package_count']==15
    assert all(p.startswith(ROOT+'/') for p in packages)
    assert set(imported['assets'])=={'SM_Envelope_Closed','SM_Envelope_Open','SM_LetterPaper'}
    assert len(imported['textures'])==9 and len(imported['materials'])==3
    report['new_packages']={p:{'bytes':package_file(p).stat().st_size,'sha256':sha(package_file(p))} for p in sorted(packages)}
    deleted=imported['deleted_legacy']
    assert len(deleted)==5 and all(not package_file(p).exists() for p in deleted)
    report['deleted_legacy']=deleted
    report['ue_completion']=completed
    report['ue_meshes']=imported['assets']
    report['assembly']=model['assembly']
    report['paper_hinge_and_collision_review']={key:review[key] for key in ('hinge','open_ucx_count','minimum_ucx_aabb_separation_mm')}
    assert validation['paper_insertion']['overlapping_triangle_pairs']==0
    protected=read('protected_content_sha256.json')
    changed=[v['path'] for v in protected if not Path(v['path']).is_file() or sha(Path(v['path'])).lower()!=v['sha256'].lower()]
    report['protected_files_checked']=len(protected)
    report['protected_files_changed']=changed
    report['preexisting_user_settings_preserved']=[]
    # The user visited Python settings before closing UE. Preserve that change;
    # require its exact byte diff and a timestamp predating this import helper.
    for filename in changed:
        path=Path(filename)
        assert path==PROJECT/'Config'/'DefaultEngine.ini'
        data=path.read_bytes()
        suffix=b'[/Script/PythonScriptPlugin.PythonScriptPluginSettings]\r\nbRemoteExecution=False\r\n\r\n'
        expected=next(v['sha256'].lower() for v in protected if v['path']==filename)
        assert data.endswith(suffix) and hashlib.sha256(data[:-len(suffix)]).hexdigest()==expected
        assert path.stat().st_mtime<datetime.fromisoformat(completed['started_utc'].replace('Z','+00:00')).timestamp()
        report['preexisting_user_settings_preserved'].append({'path':filename,'change':'Only appended bRemoteExecution=False section; saved before import','sha256':sha(path)})
    report['yastar_ui_file_count']=len(list((CONTENT/'Yastar'/'UI').rglob('*.uasset')))
    assert len(changed)==len(report['preexisting_user_settings_preserved']) and report['yastar_ui_file_count']==19
    report['ui_and_maps_unchanged']=all(v['path'] not in changed for v in protected if v['path'].endswith(('.uasset','.umap')))
    assert report['ui_and_maps_unchanged']
    report['source_files']={name:{'bytes':(OUT/name).stat().st_size,'sha256':sha(OUT/name)} for name in ['EnvelopeSet.blend']+[v['filename'] for v in model['parts'].values()]}
    report['renders']=validation['renders']
    report['geometry']=validation['geometry']
    report['success']=True
finally:
    (OUT/'final_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ENVELOPE_SET_FINAL_VERIFIED '+str(report['success']))
