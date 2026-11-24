"""Read-only independent reload of saved sofa packages, PBR and assemblies."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import traceback
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sofa_manifest as C
import sofa_import as I
import sofa_blueprint as B

r = dict(success=False, verified_in_fresh_editor=True,
         started_utc=datetime.now(timezone.utc).isoformat())
try:
    assert Path(unreal.Paths.project_dir()).resolve() == C.PROJECT.resolve()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name().startswith('/Engine/Maps/Entry')
    assert editor.get_game_world() is None
    manifest, rows, expected, sources = C.read_export()
    r['source_blend_sha256'] = manifest['source_sha256']
    r['manifest_sha256'] = sources[C.MANIFEST.name]
    groups = C.assemblies(manifest, rows)
    prior = C.read(C.HERE / 'ue_import_report.json')
    assert prior['success'] and prior['source_hashes'] == sources
    assert prior['target_root'] == C.TARGET
    r['import_run_id'] = prior['run_id']
    baseline = C.read(C.HERE / 'protected_content_sha256.json')
    C.verify_protected(baseline)
    actual = C.packages()
    assert actual == prior['packages'] and set(actual) == expected
    textures = I.load_textures(manifest)
    parent = I.load(C.MATERIAL_ROOT + '/' + C.PARENT, unreal.Material)
    materials = {name: I.load(C.MATERIAL_ROOT + '/' + name, unreal.MaterialInstanceConstant)
                 for name in textures}
    materials.update({name: I.load(C.MATERIAL_ROOT + '/' + name, unreal.Material)
                      for name in C.generic_spec(manifest)})
    meshes = {name: I.load(C.TARGET + '/' + name, unreal.StaticMesh) for name in rows}
    unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    r['parent_material'] = I.verify_parent(parent)
    r['materials'] = I.verify_materials(manifest, parent, materials, textures)
    r['meshes'] = {name: I.verify_mesh(mesh, subsystem, rows[name], materials) for name, mesh in meshes.items()}
    r['lod_triangles'] = I.verify_lod_budget(r['meshes'])
    r['blueprints'] = {name: B.verify_blueprint(I.load(C.TARGET + '/' + name, unreal.Blueprint), parts, meshes, rows)
                       for name, parts in groups.items()}
    assert C.packages() == actual, 'Read-only verification changed saved packages'
    assert editor.get_editor_world() == world
    r.update(success=True, target_root=C.TARGET, source_hashes=sources, package_hashes=actual,
             package_count=len(actual), mesh_count=len(meshes),
             triangles=sum(row['triangles'] for row in rows.values()),
             lod_triangles=[sum(row['lod_triangles'][lod] for row in r['meshes'].values()) for lod in range(4)],
             protected_paths_verified=C.verify_protected(baseline))
except Exception:
    r['error'] = traceback.format_exc()
    unreal.log_error('SOFA_FRESH_VERIFY_ERROR ' + r['error'])
finally:
    r['completed_utc'] = datetime.now(timezone.utc).isoformat()
    C.write(C.HERE / 'fresh_editor_verification.json', r)
    unreal.log('SOFA_FRESH_VERIFIED ' + str(r['success']))
