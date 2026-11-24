from pathlib import Path
import sys,traceback
import unreal
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));import update_live as U
C,I=U.C,U.I
report={'success':False,'verified_in_fresh_editor':True}
try:
    prior=C.read(HERE/'side_live_report.json');assert prior['success']
    manifest,rows,expected,hashes=C.read_export();assert hashes==prior['source_hashes']
    current=C.packages();assert current==prior['packages'] and set(current)==expected
    editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world=editor.get_editor_world();assert world.get_path_name().startswith('/Engine/Maps/Entry')
    bp=I.load(C.TARGET+'/'+C.BLUEPRINT,unreal.Blueprint);assert U.state(bp)==prior['blueprint_before']
    mesh_editor=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    textures={key:I.load(C.TEXTURE_ROOT+'/'+Path(value).stem,unreal.Texture2D) for key,value in C.TEXTURES.items()}
    parent=I.load(C.MATERIAL_ROOT+'/'+C.PARENT,unreal.Material);glass=I.load(C.MATERIAL_ROOT+'/'+C.GLASS,unreal.Material)
    meshes={name:I.load(C.TARGET+'/'+name,unreal.StaticMesh) for name in C.MESH_NAMES}
    unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
    report['meshes']={name:I.verify_mesh(mesh,mesh_editor,rows[name],glass,textures,parent) for name,mesh in meshes.items()}
    assert C.packages()==current
    report.update(success=True,mesh_count=10,triangles=sum(row['triangles'] for row in rows.values()),
        package_hashes=current,blueprint_unchanged=True,source_hashes=hashes)
except Exception:report['error']=traceback.format_exc();unreal.log_error(report['error'])
C.write(HERE/'side_fresh_report.json',report)
unreal.log('SIDE_FIX_FRESH_VERIFIED '+str(report['success']))
