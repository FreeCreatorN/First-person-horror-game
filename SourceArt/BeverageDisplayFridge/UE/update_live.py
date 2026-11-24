"""Update only our existing fridge assets; retain level and Blueprint assembly."""
from pathlib import Path
import sys,traceback,shutil,os
sys.path.insert(0,str(Path(__file__).resolve().parent))
import unreal
import fridge_manifest as C
import fridge_import as I
import fridge_blueprint as B
r={'success':False,'mode':'live_update','target_root':C.TARGET,'started_utc':I.now(),
   'editor_pid':os.getpid(),'saved':[],'imported_meshes':[]}
def checkpoint():C.write(C.HERE/'ue_update_report.json',r)
previous=None
try:
    assert Path(unreal.Paths.project_dir()).resolve()==C.PROJECT.resolve()
    manifest,rows,expected,inputs=C.read_export()
    prior=C.read(C.HERE/'ue_import_report.json');assert prior['success']
    before=C.packages();assert before==prior['packages'] and set(before)==expected,'Existing fridge was edited; preserve it'
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world=editor.get_editor_world();assert world
    game=editor.get_game_world()
    if game:
        in_use=[]
        for actor in unreal.GameplayStatics.get_all_actors_of_class(game,unreal.Actor):
            for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
                mesh=comp.get_editor_property('static_mesh')
                if mesh and mesh.get_path_name().startswith(C.TARGET+'/'):in_use.append(actor.get_name())
        assert not in_use,('Fridge is currently used in PIE',in_use)
    baseline=C.protected_snapshot();C.write(C.HERE/'protected_update_sha256.json',baseline)
    backup=C.ASSET/'Revisions'/'BeforeSeamFixUE';backup.mkdir(exist_ok=True)
    for value in before.values():
        src=Path(value['file']);dst=backup/src.relative_to(C.DESTINATION);dst.parent.mkdir(parents=True,exist_ok=True)
        assert not dst.exists();shutil.copy2(src,dst)
    r.update(source_hashes=inputs,manifest_sha256=inputs[C.MANIFEST.name],doors=manifest['doors'],
             world=world.get_path_name(),pie_running=bool(game),protected_files_before=len(baseline))
    checkpoint()
    original=I.run_import
    def replacing(*args,**kwargs):
        kwargs['replace_existing']=True
        return original(*args,**kwargs)
    I.run_import=replacing
    tools=unreal.AssetToolsHelpers.get_asset_tools();sub=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    previous=unreal.SystemLibrary.get_console_variable_int_value(I.FBX_CVAR)
    unreal.SystemLibrary.execute_console_command(world,I.FBX_CVAR+' 0')
    textures={channel:I.make_texture(tools,C.source(filename),channel) for channel,filename in C.TEXTURES.items()}
    parent=I.load(C.MATERIAL_ROOT+'/'+C.PARENT,unreal.Material)
    glass=I.load(C.MATERIAL_ROOT+'/'+C.GLASS,unreal.Material)
    sign=I.load(C.MATERIAL_ROOT+'/'+C.SIGN,unreal.Material)
    meshes={}
    for name,row in rows.items():
        meshes[name]=I.make_mesh(tools,sub,name,row,parent,glass,sign)
        r['imported_meshes']=sorted(meshes);checkpoint()
    unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
    r['materials']=I.verify_materials(parent,glass,sign)
    r['meshes']={name:I.verify_mesh(mesh,sub,rows[name],glass,textures,parent,sign) for name,mesh in meshes.items()}
    bp=I.load(C.TARGET+'/'+C.BLUEPRINT,unreal.Blueprint)
    r['blueprint']=B.verify_blueprint(bp,meshes,manifest['doors'],rows)
    assert editor.get_editor_world()==world and editor.get_game_world()==game
    for obj in [*textures.values(),*meshes.values()]:
        assert I.EDIT.save_loaded_asset(obj,False)
        r['saved'].append(obj.get_path_name());checkpoint()
    r['packages']=C.packages();assert set(r['packages'])==expected
    r['protected_files_after']=C.verify_protected(baseline)
    assert C.read_export()[3]==inputs
    r['success']=True
except Exception:
    r['error']=traceback.format_exc();unreal.log_error('FRIDGE_UPDATE_ERROR '+r['error'])
finally:
    if previous is not None:unreal.SystemLibrary.execute_console_command(world,I.FBX_CVAR+' '+str(previous))
    r['completed_utc']=I.now();checkpoint();unreal.log('FRIDGE_UPDATE_VERIFIED '+str(r['success']))
