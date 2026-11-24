"""Read-only reload of the replaced empty counter and its exact part hierarchy."""
from datetime import datetime,timezone
from pathlib import Path
import sys,traceback
import unreal
sys.path.insert(0,str(Path(__file__).resolve().parent))
import empty_manifest as C
import empty_blueprint as B
import import_ue as I
report={'success':False,'verified_in_fresh_editor':True,'started_utc':datetime.now(timezone.utc).isoformat()}
try:
    assert Path(unreal.Paths.project_dir()).resolve()==C.PROJECT.resolve()
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world=editor.get_editor_world();assert world and world.get_path_name().startswith('/Engine/Maps/Entry')
    assert editor.get_game_world() is None
    manifest,rows,expected,sources=C.read_export()
    imported=C.read(C.HERE/'ue_empty_replacement_report.json')
    assert imported['success'] and imported['source_hashes']==sources
    actual=C.packages();assert actual==imported['packages']
    optional={C.LEGACY_GLASS} if imported['legacy_glass'].get('retained_inactive') else set()
    assert set(actual)==expected|optional
    mesh_editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    textures={channel:I.load(C.TEXTURE_ROOT+'/'+Path(relative).stem,unreal.Texture2D) for channel,relative in C.TEXTURES.items()}
    parent=I.load(C.MATERIAL_ROOT+'/'+C.PARENT,unreal.Material)
    glass=I.load(C.MATERIAL_ROOT+'/'+C.GLASS,unreal.Material)
    meshes={name:I.load(C.TARGET+'/'+name,unreal.StaticMesh) for name in C.MESH_NAMES}
    unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
    report['materials']=I.verify_materials(parent,glass)
    report['meshes']={name:I.verify_mesh(mesh,mesh_editor,rows[name],glass,textures,parent) for name,mesh in meshes.items()}
    bp=I.load(C.TARGET+'/'+C.BLUEPRINT,unreal.Blueprint)
    report['blueprint']=B.verify_blueprint(bp,meshes,manifest['doors'])
    assert all('Stock' not in value['mesh'] and 'FixedGlass' not in value['mesh'] for value in report['blueprint']['components'].values())
    assert C.packages()==actual
    report.update(success=True,target_root=C.TARGET,package_count=len(actual),mesh_count=len(meshes),
        triangles=sum(row['triangles'] for row in rows.values()),source_hashes=sources,package_hashes=actual,
        doors=manifest['doors'],protected_paths_verified=C.verify_protected(C.read(C.HERE/'empty_protected_sha256.json')))
except Exception:
    report['error']=traceback.format_exc();unreal.log_error('EMPTY_COUNTER_FRESH_ERROR '+report['error'])
finally:
    report['completed_utc']=datetime.now(timezone.utc).isoformat()
    C.write(C.HERE/'empty_fresh_verification.json',report)
    unreal.log('EMPTY_COUNTER_FRESH_VERIFIED '+str(report['success']))
