"""Replace only the existing ShopCounterPlan assets, preserving their package paths."""
from datetime import datetime, timezone
from pathlib import Path
import gc, shutil, sys, traceback
from uuid import uuid4
import unreal

sys.path.insert(0,str(Path(__file__).resolve().parent))
import empty_manifest as C
import empty_blueprint as B
import import_ue as I

EDIT=unreal.EditorAssetLibrary
REPORT=C.HERE/'ue_empty_replacement_report.json'
def checkpoint(report):C.write(REPORT,report)

def backup_existing(report):
    actual=C.packages()
    assert actual and C.TARGET+'/'+C.BLUEPRINT in actual
    directory=C.ASSET/'Archives'/('BeforeEmpty_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+report['run_id'][:8])
    assert not directory.exists()
    directory.mkdir(parents=True)
    for package,row in actual.items():
        original=Path(row['file'])
        assert original.resolve().is_relative_to(C.DESTINATION.resolve())
        target=directory/'Content'/original.relative_to(C.CONTENT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,target)
        assert C.digest(target)==row['sha256']
    # Retain the previous evidence receipts with the recoverable asset snapshot.
    for name in ('ue_import_report.json','final_verification.json','fresh_editor_verification.json'):
        path=C.HERE/name
        if path.is_file():shutil.copy2(path,directory/name)
    C.write(directory/'backup_manifest.json',{'original_packages':actual,'target':C.TARGET})
    report.update(backup_directory=str(directory),preexisting_packages=actual)
    checkpoint(report)
    return actual

def replacement_import(tools, cls, name, folder, path, **extra):
    package=folder+'/'+name
    assert folder==C.TARGET or folder.startswith(C.TARGET+'/'),folder
    existed=EDIT.does_asset_exist(package)
    before=EDIT.load_asset(package) if existed else None
    task=unreal.AssetImportTask()
    settings=dict(filename=str(path),destination_path=folder,destination_name=name,
                  automated=True,replace_existing=existed,replace_existing_settings=False,save=False)
    settings.update(extra)
    for key,value in settings.items():task.set_editor_property(key,value)
    tools.import_asset_tasks([task])
    imported={str(value).split('.')[0] for value in task.get_editor_property('imported_object_paths')}
    assert imported=={package},(package,imported)
    result=I.load(package,cls)
    # UE reimports the existing UObject; references keep the original asset identity.
    assert before is None or result==before,('Existing asset object was replaced unexpectedly',package)
    return result

def retire_combined_glass(report):
    if not EDIT.does_asset_exist(C.LEGACY_GLASS):
        report['legacy_glass']={'deleted':True,'already_absent':True};return
    references=list(map(str,EDIT.find_package_referencers_for_asset(C.LEGACY_GLASS,False)))
    external=[value for value in references if value not in (C.TARGET+'/'+C.BLUEPRINT,C.LEGACY_GLASS)]
    report['legacy_glass']={'asset':C.LEGACY_GLASS,'registry_referencers':references,'external_referencers':external}
    if external:
        report['legacy_glass'].update(deleted=False,retained_inactive=True)
        return
    confirmed=list(map(str,EDIT.find_package_referencers_for_asset(C.LEGACY_GLASS,True)))
    report['legacy_glass']['confirmed_referencers']=confirmed
    if confirmed:
        report['legacy_glass'].update(deleted=False,retained_inactive=True)
        return
    assert EDIT.delete_asset(C.LEGACY_GLASS),C.LEGACY_GLASS
    assert not EDIT.does_asset_exist(C.LEGACY_GLASS)
    report['legacy_glass']['deleted']=True

def execute(report,allow_live):
    assert Path(unreal.Paths.project_dir()).resolve()==C.PROJECT.resolve()
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world=editor.get_editor_world()
    assert world and editor.get_game_world() is None
    assert allow_live or world.get_path_name().startswith('/Engine/Maps/Entry')
    report['world']=world.get_path_name()
    manifest,rows,expected,source_hashes=C.read_export()
    report.update(source_hashes=source_hashes,doors=manifest['doors'],empty_counter=True,
                  planning_categories=C.PLANNING)
    baseline=C.protected_snapshot();assert baseline
    C.write(C.HERE/'empty_protected_sha256.json',baseline)
    report['protected_files_before']=len(baseline)
    registry=unreal.AssetRegistryHelpers.get_asset_registry();registry.wait_for_completion()
    before=backup_existing(report)
    # Guard the previous owned package set without permitting a broad directory replacement.
    permitted=expected|{C.LEGACY_GLASS}
    assert not set(before)-permitted,('Unexpected existing assets; preserve them',sorted(set(before)-permitted))
    bp=I.load(C.TARGET+'/'+C.BLUEPRINT,unreal.Blueprint)
    parent=I.load(C.MATERIAL_ROOT+'/'+C.PARENT,unreal.Material)
    glass=I.load(C.MATERIAL_ROOT+'/'+C.GLASS,unreal.Material)
    old_bp_path=bp.get_path_name()
    mesh_editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    previous_backend=unreal.SystemLibrary.get_console_variable_int_value(I.FBX_CVAR)
    original_import=I.run_import
    try:
        unreal.SystemLibrary.execute_console_command(world,I.FBX_CVAR+' 0')
        assert unreal.SystemLibrary.get_console_variable_int_value(I.FBX_CVAR)==0
        I.run_import=replacement_import
        tools=unreal.AssetToolsHelpers.get_asset_tools()
        textures={channel:I.make_texture(tools,C.source(relative),channel) for channel,relative in C.TEXTURES.items()}
        meshes={}
        for name,row in rows.items():
            meshes[name]=I.make_mesh(tools,mesh_editor,name,row,parent,glass)
            part=name.removeprefix(C.PREFIX)
            group=next((g for g,children in C.GROUPS.items() if part in children),part)
            EDIT.set_metadata_tag(meshes[name],'PlanningSheetPart',C.PLANNING[group])
            report['imported_meshes']=sorted(meshes);checkpoint(report)
        unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
        report['materials']=I.verify_materials(parent,glass)
        report['meshes']={name:I.verify_mesh(mesh,mesh_editor,rows[name],glass,textures,parent) for name,mesh in meshes.items()}
        report['blueprint']=B.update_blueprint(bp,meshes,manifest['doors'])
        assert bp.get_path_name()==old_bp_path
        assert all(C.digest(C.source(relative))==sha for relative,sha in source_hashes.items()),'Source changed during update'
        staged=[*textures.values(),parent,glass,*meshes.values(),bp]
        assert {asset.get_path_name().split('.')[0] for asset in staged}==expected
        checkpoint(report)
        # Commit only after all geometry, materials, and the migrated hierarchy validate.
        for asset in staged:
            assert EDIT.save_loaded_asset(asset,False),asset.get_path_name()
            report.setdefault('saved',[]).append(asset.get_path_name());checkpoint(report)
        retire_combined_glass(report)
        actual=C.packages()
        optional={C.LEGACY_GLASS} if report['legacy_glass'].get('retained_inactive') else set()
        assert set(actual)==expected|optional,(set(actual)-expected,expected-set(actual))
        report['packages']=actual
        report['asset_paths_preserved']=sorted(set(before)&set(actual))
        assert C.TARGET+'/'+C.BLUEPRINT in report['asset_paths_preserved']
        report['protected_files_after']=C.verify_protected(baseline)
        assert editor.get_editor_world()==world
    finally:
        I.run_import=original_import
        unreal.SystemLibrary.execute_console_command(world,I.FBX_CVAR+' '+str(previous_backend))

def run(allow_live=False):
    report={'success':False,'run_id':str(uuid4()),'mode':'live' if allow_live else 'exclusive',
            'target_root':C.TARGET,'started_utc':I.now(),'imported_meshes':[],'saved':[]}
    checkpoint(report)
    try:execute(report,allow_live);report['success']=True
    except Exception:
        report['error']=traceback.format_exc();unreal.log_error('EMPTY_COUNTER_REPLACEMENT_ERROR '+report['error'])
    finally:
        report['completed_utc']=I.now();checkpoint(report)
    unreal.log('EMPTY_COUNTER_REPLACEMENT_VERIFIED '+str(report['success']));gc.collect()
    return report['success']
if __name__=='__main__':run()
