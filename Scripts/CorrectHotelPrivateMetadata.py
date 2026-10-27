"""Restore source slot identities and import resolution in private Hotel copies only."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';C=R/'Content';HOTEL=C/'CodexGenerated/Hotel'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,x):native.write(W/n,x)
def import_info(asset):
    try:data=asset.get_editor_property('asset_import_data')
    except Exception:return None,[]
    return (data,[str(Path(p).resolve()) for p in data.extract_filenames()]) if data else (None,[])
def main():
    assert not (W/'PrivateAssetCorrections.json').exists()
    copied=read('CopiedPackages.json');plan=read('HotelNamePlan.json');assert copied['passed'] and plan['passed']
    assert read('StagedAudit.json')['passed'] and read('StagedAudit2.Completion.json')['normal_zero_exit']
    baseline=read('ProtectedBeforeAfterRestore.json')['file_sha256']
    before={str(p):native.sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
    assert all(before.get(p)==h for p,h in baseline.items())
    assert all(before.get(p)==h for p,h in copied['new_asset_sha256'].items())
    corrections=[]
    for row in plan['mappings']:
        if row['asset_class'] not in ('StaticMesh','Texture2D'):continue
        source=unreal.load_asset(row['source_package']);target=unreal.load_asset(row['destination_package'])
        assert source and target and Path(row['destination_file']).is_relative_to(HOTEL)
        slot_changes=[];import_change=None
        if row['asset_class']=='StaticMesh':
            src=source.get_editor_property('static_materials');dst=target.get_editor_property('static_materials');assert len(src)==len(dst)
            restored_slots=[]
            for i,(s,t) in enumerate(zip(src,dst)):
                restored=s.copy()
                restored.set_editor_property('material_interface',t.get_editor_property('material_interface'),notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                for prop in ('material_slot_name','imported_material_slot_name'):
                    a=s.get_editor_property(prop);b=t.get_editor_property(prop)
                    if a!=b:
                        slot_changes.append(dict(index=i,property=prop,old=str(b),restored=str(a)))
                restored_slots.append(restored)
            if slot_changes:target.set_editor_property('static_materials',restored_slots,notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        source_import,source_files=import_info(source);target_import,target_files=import_info(target)
        assert bool(source_import)==bool(target_import)
        if source_files!=target_files:
            assert len(source_files)==len(target_files)==1
            before_import=native.reflect_editor_properties(target_import)
            assert unreal.HotelPackageCopyLibrary.restore_private_import_filename(target_import,source_import)
            assert import_info(target)[1]==source_files
            import_change=dict(old_resolved=target_files,restored_resolved=source_files,
                before_properties=before_import,after_properties=native.reflect_editor_properties(target_import),
                source_properties=native.reflect_editor_properties(source_import),
                preserved_import_source_sha256={p:native.sha(Path(p)) if Path(p).is_file() else None for p in source_files})
        if slot_changes or import_change:
            corrections.append(dict(package=row['destination_package'],file=row['destination_file'],source_package=row['source_package'],
                source_file=row['source_file'],source_sha256=row['source_sha256'],before_sha256=before[row['destination_file']],
                material_slot_identity_changes=slot_changes,import_filename_correction=import_change))
    # Complete every in-memory preflight before saving the first private copy.
    write('PrivateMetadataPreflight.json',dict(passed=True,corrections=corrections))
    for correction in corrections:
        target=unreal.load_asset(correction['package'])
        assert unreal.EditorAssetLibrary.save_loaded_asset(target,False)
        correction['after_sha256']=native.sha(Path(correction['file']))
    after={str(p):native.sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
    changed={p for p in before if after.get(p)!=before[p]}
    assert set(before)==set(after) and changed=={r['file'] for r in corrections}
    assert all(after.get(p)==h for p,h in baseline.items())
    assert all(Path(p).is_relative_to(HOTEL) for p in changed)
    effective={p:after[p] for p in copied['new_asset_sha256']}
    write('PrivateAssetCorrections.json',dict(passed=True,corrections=corrections,changed_private_assets=len(corrections),
        restored_material_slot_meshes=sum(bool(r['material_slot_identity_changes']) for r in corrections),
        restored_import_resolution_assets=sum(bool(r['import_filename_correction']) for r in corrections),
        all_original_content_config_unchanged=True,no_reimport=True,no_render_geometry_rebuild=True,
        reason='Header name remapping changed imported material slot identities and relative import paths; restored original semantics in private copies only.'))
    write('EffectivePrivateHashes.json',dict(passed=True,new_asset_sha256=effective,initial_copy_sha256=native.sha(W/'CopiedPackages.json'),
        correction_report_sha256=native.sha(W/'PrivateAssetCorrections.json')))
    unreal.log('HOTEL_PRIVATE_METADATA_CORRECTION_PASS '+str(len(corrections)))
if __name__=='__main__':
    try:main()
    except Exception:write('PrivateMetadataCorrectionFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
