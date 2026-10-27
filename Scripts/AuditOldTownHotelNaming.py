"""Fresh full-Actor validation of Hotel staging/original map without saving it."""
import os,sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
from OldTownHotelNamingVerification import compare_scene,normalize_asset_paths
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';base.W=W;base.TAG='HotelNaming_ExcludeNoExistingActor'
C=R/'Content';MAP=C/'Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,x):native.write(W/n,x)
def main():
    mode=os.environ.get('HOTEL_AUDIT_MODE','Staged');assert mode in ('Staged','Committed','Final','Refreshed','Clean')
    assert not (W/(mode+'Audit.json')).exists()
    copied=read('CopiedPackages.json');plan=read('HotelNamePlan.json');assert copied['passed'] and plan['passed']
    mapping=dict(copied['package_remapping'])
    if mode=='Staged':
        target=copied['staged_level'];assert native.sha(MAP)==copied['source_map_sha256']
    else:
        target=copied['original_level'];mapping.pop(target)
        commit=read('MetadataRefreshApplied.json') if mode in ('Refreshed','Clean') else read('Committed.json')
        assert commit['passed'] and native.sha(MAP)==commit['map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(target)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};assert len(actors)==len(by)==7986
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    actual=base.snapshot(actors,mode+'HotelNaming')
    write(mode+'Scene.json',actual)
    proof=compare_scene(read('BeforeScene.json'),actual,mapping)
    inventory=read('Inventory.json')
    opening_rows=[]
    for kind,key,count in [('windows','window_assemblies',348),('doors','door_assemblies',124)]:
        expected=inventory[key];assert len(expected)==count
        for row in expected:
            actor=by[row['label']]
            assert actor.get_name()==row['name']
            assert actor.get_class().get_path_name()==normalize_asset_paths(row['class_path'],mapping)
        classes={by[r['label']].get_class().get_path_name() for r in expected}
        assert len(classes)==(8 if kind=='windows' else 10)
        opening_rows.append(dict(kind=kind,count=count,shared_blueprints=len(classes),all_source_labels_internal_names_preserved=True))
    current={str(p):native.sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
    protected=read('ProtectedBeforeAfterRestore.json')['file_sha256']
    removed={}
    if mode in ('Final','Refreshed','Clean'):
        cleanup=read('CurrentCleanupResult.json');assert cleanup['passed']
        removed={r['file']:r['sha256'] for r in cleanup['removed_files']}
        if mode=='Clean':
            supplemental=read('SupplementalCleanupResult.json');assert supplemental['passed']
            cleanup=dict(removed_files=cleanup['removed_files']+supplemental['removed_files'])
            removed={r['file']:r['sha256'] for r in cleanup['removed_files']}
        for row in cleanup['removed_files']:
            assert not Path(row['file']).exists() and native.sha(Path(row['backup']))==row['sha256']
    assert all(current.get(p)==h for p,h in protected.items() if p not in removed and not (mode!='Staged' and Path(p)==MAP))
    effective=read('EffectivePrivateHashes.json');assert effective['passed']
    assert effective['initial_copy_sha256']==native.sha(W/'CopiedPackages.json')
    assert effective['correction_report_sha256']==native.sha(W/'PrivateAssetCorrections.json')
    assert all(current.get(p)==h for p,h in effective['new_asset_sha256'].items() if p not in removed)
    report=dict(passed=True,target_level=target,mode=mode,map_sha256=native.sha(MAP),actor_count=7986,
        scene_proof=proof,openings=opening_rows,all_original_user_assets_unchanged=True,private_asset_hashes_unchanged=True,
        existing_files_checked=len(protected)-(1 if mode!='Staged' else 0)-len(set(protected)&set(removed)),no_map_save=True)
    write(mode+'Audit.json',report)
    unreal.log('HOTEL_NAMING_'+mode.upper()+'_AUDIT_PASS')
if __name__=='__main__':
    try:main()
    except Exception as error:write(os.environ.get('HOTEL_AUDIT_MODE','Staged')+'AuditFailure.json',dict(passed=False,traceback=traceback.format_exc(),proof=getattr(error,'report',None)));raise
