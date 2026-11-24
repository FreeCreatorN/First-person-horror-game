"""Read-only independent editor reload of saved cartons, PBR and assemblies."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import traceback
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carton_manifest as C
import carton_import as I
import carton_blueprint as B

r = {'success': False, 'verified_in_fresh_editor': True,
     'started_utc': datetime.now(timezone.utc).isoformat()}
try:
    assert Path(unreal.Paths.project_dir()).resolve() == C.PROJECT.resolve()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name().startswith('/Engine/Maps/Entry')
    assert editor.get_game_world() is None
    manifest, rows, expected, sources = C.read_export()
    prior = C.read(C.HERE / 'ue_import_report.json')
    assert prior['success'] and prior['source_hashes'] == sources
    actual = C.packages()
    assert actual == prior['packages'] and set(actual) == expected
    spec = C.texture_spec(manifest)
    normal = I.load(C.TEXTURE_ROOT + '/' + Path(spec['normal']).stem, unreal.Texture2D)
    textures = {variant: {channel: I.load(C.TEXTURE_ROOT + '/' + Path(spec[variant][channel]).stem, unreal.Texture2D)
                          for channel in ('base_color', 'orm')} for variant in C.MATERIAL_VARIANTS}
    for pair in textures.values():
        pair['normal'] = normal
    materials = {name: I.load(C.MATERIAL_ROOT + '/' + name, unreal.Material) for name in C.MATERIAL_NAMES}
    meshes = {name: I.load(C.TARGET + '/' + name, unreal.StaticMesh) for name in C.MESH_NAMES}
    unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    r['materials'] = I.verify_materials(materials, textures)
    r['meshes'] = {name: I.verify_mesh(mesh, subsystem, rows[name], materials) for name, mesh in meshes.items()}
    r['blueprints'] = {name: B.verify_blueprint(I.load(C.TARGET + '/' + name, unreal.Blueprint), meshes, rows)
                       for name in C.ASSEMBLIES}
    assert C.packages() == actual, 'Read-only verification changed saved packages'
    r.update(success=True, target_root=C.TARGET, source_hashes=sources, package_hashes=actual,
             package_count=len(actual), mesh_count=len(meshes),
             triangles=sum(row['triangles'] for row in rows.values()),
             protected_paths_verified=C.verify_protected(C.read(C.HERE / 'protected_content_sha256.json')))
except Exception:
    r['error'] = traceback.format_exc()
    unreal.log_error('CARTON_FRESH_VERIFY_ERROR ' + r['error'])
finally:
    r['completed_utc'] = datetime.now(timezone.utc).isoformat()
    C.write(C.HERE / 'fresh_editor_verification.json', r)
    unreal.log('CARTON_FRESH_VERIFIED ' + str(r['success']))
