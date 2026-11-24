"""Update repaired mesh data in the user's existing editor; leave BP and level intact."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,shutil,traceback
import unreal
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'UE'))
import empty_manifest as C
import import_ue as I
import blueprint as B
REPORT=HERE/'side_live_report.json'
EDIT=unreal.EditorAssetLibrary

def state(bp):
    subsystem,library=B.services();components=B.components(bp,subsystem,library)
    result={}
    for name,(handle,obj) in components.items():
        location=obj.get_editor_property('relative_location');rotation=obj.get_editor_property('relative_rotation');scale=obj.get_editor_property('RelativeScale3D')
        mesh=obj.get_editor_property('static_mesh') if isinstance(obj,unreal.StaticMeshComponent) else None
        result[name]={'position':[location.x,location.y,location.z],'rotation':[rotation.pitch,rotation.yaw,rotation.roll],
            'scale':[scale.x,scale.y,scale.z],'mesh':mesh.get_path_name() if mesh else None}
    return result

def reimport(tools,cls,name,folder,path,**extra):
    package=folder+'/'+name;assert package.startswith(C.TARGET+'/')
    before=I.load(package,cls)
    task=unreal.AssetImportTask()
    fields=dict(filename=str(path),destination_name=name,destination_path=folder,automated=True,
        replace_existing=True,replace_existing_settings=False,save=False)
    fields.update(extra)
    for key,value in fields.items():task.set_editor_property(key,value)
    tools.import_asset_tasks([task])
    result=I.load(package,cls);assert result==before,package
    assert {str(x).split('.')[0] for x in task.get_editor_property('imported_object_paths')}=={package}
    return result

def run():
    report={'success':False,'started':datetime.now(timezone.utc).isoformat()}
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world=editor.get_editor_world();assert world and editor.get_game_world() is None,'Stop PIE before repairing assets'
    assert Path(unreal.Paths.project_dir()).resolve()==C.PROJECT.resolve()
    old_import=I.run_import
    previous_backend=unreal.SystemLibrary.get_console_variable_int_value(I.FBX_CVAR)
    try:
        manifest,rows,expected,source_hashes=C.read_export()
        report.update(world=world.get_path_name(),source_hashes=source_hashes)
        original=C.packages();assert set(original)==expected
        backup=ROOT/'Archives'/('BeforeSideFix_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(parents=True,exist_ok=False)
        for package,row in original.items():
            path=Path(row['file']);dest=backup/path.relative_to(C.CONTENT);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,dest);assert C.digest(dest)==row['sha256']
        C.write(backup/'packages.json',original);report['backup_directory']=str(backup)
        protected=C.protected_snapshot();bp=I.load(C.TARGET+'/'+C.BLUEPRINT,unreal.Blueprint)
        before_bp=state(bp);report['blueprint_before']=before_bp
        parent=I.load(C.MATERIAL_ROOT+'/'+C.PARENT,unreal.Material);glass=I.load(C.MATERIAL_ROOT+'/'+C.GLASS,unreal.Material)
        stable=[C.TARGET+'/'+C.BLUEPRINT,C.MATERIAL_ROOT+'/'+C.PARENT,C.MATERIAL_ROOT+'/'+C.GLASS]
        stable_hash={key:original[key]['sha256'] for key in stable}
        unreal.SystemLibrary.execute_console_command(world,I.FBX_CVAR+' 0');I.run_import=reimport
        tools=unreal.AssetToolsHelpers.get_asset_tools();mesh_editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        textures={channel:I.make_texture(tools,C.source(relative),channel) for channel,relative in C.TEXTURES.items()}
        meshes={name:I.make_mesh(tools,mesh_editor,name,row,parent,glass) for name,row in rows.items()}
        unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
        report['meshes']={name:I.verify_mesh(mesh,mesh_editor,rows[name],glass,textures,parent) for name,mesh in meshes.items()}
        assert state(bp)==before_bp,'User Blueprint component state changed'
        for asset in [*textures.values(),*meshes.values()]:
            assert EDIT.save_loaded_asset(asset,False);report.setdefault('saved',[]).append(asset.get_path_name())
        assert editor.get_editor_world()==world
        actual=C.packages();assert set(actual)==expected
        assert {key:actual[key]['sha256'] for key in stable}==stable_hash,'Unmodified Blueprint/material package changed'
        assert state(bp)==before_bp
        report.update(success=True,packages=actual,protected_paths_verified=C.verify_protected(protected),
            blueprint_unchanged=True,mesh_count=len(meshes),saved_count=len(report['saved']),
            triangles=sum(row['triangles'] for row in rows.values()),verified_in_running_editor=True)
    except Exception:
        report['error']=traceback.format_exc();unreal.log_error('SIDE_FIX_FAILED '+report['error'])
    finally:
        I.run_import=old_import;unreal.SystemLibrary.execute_console_command(world,I.FBX_CVAR+' '+str(previous_backend))
        report['completed']=datetime.now(timezone.utc).isoformat();C.write(REPORT,report)
        unreal.log('SIDE_FIX_COMPLETED '+str(report['success']))
    return report['success']

if __name__=='__main__':run()
