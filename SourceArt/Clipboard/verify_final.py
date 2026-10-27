"""Read-only final checks of the clipboard asset files and protected project content."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[1];CONTENT=PROJECT/'Content'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report={'success':False,'checked_utc':datetime.now(timezone.utc).isoformat()}
try:
    model=read('model_report.json');validation=read('validation_report.json')
    ue=read('ue_import_report.json');completed=read('ue_import_completion.json')
    contact=read('contact_verification.json')
    revision_path=OUT/'RuledPaper'/'ue_update_report.json'
    revision=None
    if revision_path.is_file():
        revision=read('RuledPaper/ue_update_report.json')
        revision_done=read('RuledPaper/ue_update_completion.json')
        source_revision=read('RuledPaper/update_report.json')
        assert revision['success'] and source_revision['success'] and revision_done['normal_zero_exit']
        assert revision['completed_utc']>=revision_done['started_utc']
        assert revision['other_17_package_hashes_unchanged'] and revision['target_package_changed']
        assert revision['same_texture_uobject'] and revision['same_material_uobject']
        assert sha(OUT/'Textures'/'T_ClipboardPaper_BaseColor.png')==revision['source_png_sha256']
        report['paper_material_revision']={'source':source_revision,'ue':revision,'completion':revision_done}
    assert validation['success'] and ue['success'] and contact['success']
    assert completed['normal_zero_exit'] and completed['exit_code']==0
    assert ue['completed_utc']>=completed['started_utc']
    assert ue['new_package_count']==18 and len(ue['new_packages_on_disk'])==18
    assert len(ue['assets'])==3 and len(ue['materials'])==3 and len(ue['textures'])==12
    assert ue['same_world_object'] and not ue['map_save_executed'] and not ue['level_load_executed']
    assert not ue['asset_delete_executed'] and ue['actors_spawned']==0
    assert len(validation['bakes'])==12 and len(validation['renders'])==3
    report['package_files']={}
    for package,info in ue['new_packages_on_disk'].items():
        assert package.startswith('/Game/Yastars/Mesh/Clipboard/')
        p=Path(info['file']);assert p.is_file() and p.stat().st_size>0
        report['package_files'][package]={'bytes':p.stat().st_size,'sha256':sha(p)}
    protected=read('RuledPaper/protected_content_sha256.json' if revision else 'protected_content_sha256.json')
    changed=[item['path'] for item in protected if not Path(item['path']).is_file() or sha(Path(item['path'])).lower()!=item['sha256'].lower()]
    report['protected_files_checked']=len(protected);report['protected_files_changed']=changed
    assert not changed
    report['ui_and_maps_unchanged']=True
    report['ue_meshes']=ue['assets'];report['assembly']=model['assembly'];report['contacts']=contact
    report['renders']=validation['renders'];report['ue_completion']=completed
    report['source_files']={name:{'bytes':(OUT/name).stat().st_size,'sha256':sha(OUT/name)} for name in ['Clipboard.blend']+[v['filename'] for v in model['parts'].values()]}
    report['success']=True
finally:
    (OUT/'final_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('CLIPBOARD_FINAL_VERIFIED '+str(report['success']))
