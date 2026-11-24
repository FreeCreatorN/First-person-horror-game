"""Reload only this counter's saved packages and verify their actual UE state."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import traceback
import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from counter_manifest import (BLUEPRINT, GLASS, HERE, MATERIAL_ROOT, MESH_NAMES, PARENT,
    PROJECT, TARGET, TEXTURES, TEXTURE_ROOT, packages, read, read_export, source, verify_protected, write)
import blueprint
import import_ue

report = {'success': False, 'verified_in_fresh_editor': True,
          'started_utc': datetime.now(timezone.utc).isoformat()}
try:
    assert Path(unreal.Paths.project_dir()).resolve() == PROJECT.resolve()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name().startswith('/Engine/Maps/Entry')
    assert editor.get_game_world() is None
    manifest, rows, expected, source_hashes = read_export()
    imported = read(HERE / 'ue_import_report.json')
    assert imported['success'] and imported['source_hashes'] == source_hashes
    actual = packages()
    assert actual == imported['packages'] and set(actual) == expected
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    textures = {channel: import_ue.load(TEXTURE_ROOT + '/' + Path(relative).stem, unreal.Texture2D)
                for channel, relative in TEXTURES.items()}
    parent = import_ue.load(MATERIAL_ROOT + '/' + PARENT, unreal.Material)
    glass = import_ue.load(MATERIAL_ROOT + '/' + GLASS, unreal.Material)
    meshes = {name: import_ue.load(TARGET + '/' + name, unreal.StaticMesh) for name in MESH_NAMES}
    unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
    report['materials'] = import_ue.verify_materials(parent, glass)
    report['meshes'] = {name: import_ue.verify_mesh(mesh, mesh_editor, rows[name], glass, textures, parent)
                        for name, mesh in meshes.items()}
    bp = import_ue.load(TARGET + '/' + BLUEPRINT, unreal.Blueprint)
    report['blueprint'] = blueprint.verify_blueprint(bp, meshes, manifest['doors'])
    # Do not compile or save anything in this fresh read-only verification.
    assert packages() == actual
    report['protected_paths_verified'] = verify_protected(read(HERE / 'protected_content_sha256.json'))
    report.update(success=True, target_root=TARGET, package_count=len(actual), mesh_count=len(meshes),
                  triangles=sum(row['triangles'] for row in report['meshes'].values()),
                  source_hashes=source_hashes, package_hashes=actual, doors=manifest['doors'])
except Exception:
    report['error'] = traceback.format_exc()
    unreal.log_error('SHOP_COUNTER_FRESH_VERIFY_ERROR ' + report['error'])
finally:
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    write(HERE / 'fresh_editor_verification.json', report)
    unreal.log('SHOP_COUNTER_FRESH_VERIFIED ' + str(report['success']))
