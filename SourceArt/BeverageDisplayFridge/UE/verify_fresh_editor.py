"""Read-only fresh editor verification of fridge materials, pivot and assembly."""
from datetime import datetime,timezone
from pathlib import Path
import sys,traceback
import unreal
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fridge_manifest as C
import fridge_import as I
import fridge_blueprint as B
r={'success':False,'verified_in_fresh_editor':True,'started_utc':datetime.now(timezone.utc).isoformat()}
try:
    assert Path(unreal.Paths.project_dir()).resolve()==C.PROJECT.resolve()
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world=editor.get_editor_world();assert world and world.get_path_name().startswith('/Engine/Maps/Entry')
    assert editor.get_game_world() is None
    manifest,rows,expected,sources=C.read_export()
    prior=C.read(C.HERE/'ue_import_report.json');assert prior['success'] and prior['source_hashes']==sources
    actual=C.packages();assert actual==prior['packages'] and set(actual)==expected
    mesh_editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    textures={channel:I.load(C.TEXTURE_ROOT+'/'+Path(filename).stem,unreal.Texture2D) for channel,filename in C.TEXTURES.items()}
    parent=I.load(C.MATERIAL_ROOT+'/'+C.PARENT,unreal.Material);glass=I.load(C.MATERIAL_ROOT+'/'+C.GLASS,unreal.Material)
    sign=I.load(C.MATERIAL_ROOT+'/'+C.SIGN,unreal.Material) if any('M_Fridge_Sign' in row['slots'] for row in rows.values()) else None
    meshes={name:I.load(C.TARGET+'/'+name,unreal.StaticMesh) for name in C.MESH_NAMES}
    unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
    r['materials']=I.verify_materials(parent,glass,sign)
    r['meshes']={name:I.verify_mesh(mesh,mesh_editor,rows[name],glass,textures,parent,sign) for name,mesh in meshes.items()}
    bp=I.load(C.TARGET+'/'+C.BLUEPRINT,unreal.Blueprint);r['blueprint']=B.verify_blueprint(bp,meshes,manifest['doors'],rows)
    assert C.packages()==actual
    r.update(success=True,target_root=C.TARGET,package_count=len(actual),mesh_count=16,
        triangles=sum(row['triangles'] for row in rows.values()),source_hashes=sources,package_hashes=actual,
        doors=manifest['doors'],protected_paths_verified=C.verify_protected(C.read(C.HERE/'protected_content_sha256.json')))
except Exception:r['error']=traceback.format_exc();unreal.log_error('FRIDGE_FRESH_VERIFY_ERROR '+r['error'])
finally:
    r['completed_utc']=datetime.now(timezone.utc).isoformat();C.write(C.HERE/'fresh_editor_verification.json',r)
    unreal.log('FRIDGE_FRESH_VERIFIED '+str(r['success']))
