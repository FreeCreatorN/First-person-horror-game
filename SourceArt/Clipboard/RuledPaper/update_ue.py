"""Update only the existing clipboard paper's BaseColor texture in place.

No material, mesh, collision, level or other texture is written. All 18 original
packages must exist. Seventeen protected package hashes must remain identical.
"""
import hashlib
import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

import unreal

PROJECT = Path(r'D:\UE\Project\HorrorGame')
CONTENT = (PROJECT / 'Content').resolve()
CLIPBOARD_SOURCE = (PROJECT / 'SourceArt' / 'Clipboard').resolve()
OUT = (CLIPBOARD_SOURCE / 'RuledPaper').resolve()
ROOT = '/Game/Yastars/Mesh/Clipboard'
TARGET = ROOT + '/Textures/T_ClipboardPaper_BaseColor'
MATERIAL = ROOT + '/Materials/M_ClipboardPaper'
PNG = (CLIPBOARD_SOURCE / 'Textures' / 'T_ClipboardPaper_BaseColor.png').resolve()
MESH_NAMES = ('SM_Clipboard_Board', 'SM_Clipboard_Clip', 'SM_Clipboard_Paper')
MATERIAL_NAMES = ('M_ClipboardBoard', 'M_ClipboardClip', 'M_ClipboardPaper')
PREFIXES = ('T_ClipboardBoard', 'T_ClipboardClip', 'T_ClipboardPaper')
CHANNELS = ('BaseColor', 'Roughness', 'Normal', 'Metallic')
PACKAGES = ({ROOT + '/' + name for name in MESH_NAMES}
            | {ROOT + '/Materials/' + name for name in MATERIAL_NAMES}
            | {ROOT + '/Textures/' + prefix + '_' + channel
               for prefix in PREFIXES for channel in CHANNELS})
assert len(PACKAGES) == 18 and TARGET in PACKAGES and MATERIAL in PACKAGES
report = {'success': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
          'target': TARGET, 'source_png': str(PNG), 'target_root': ROOT,
          'allowed_saved_packages': [TARGET], 'saved_packages': [],
          'material_saved': False, 'mesh_saved': False, 'asset_deleted': False,
          'map_saved': False, 'level_loaded': False, 'actors_spawned': 0,
          'all_package_hashes_before': {}, 'all_package_hashes_after': {}}


def checkpoint():
    (OUT / 'ue_update_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def package_file(package):
    assert package in PACKAGES, package
    path = (CONTENT / (package[6:] + '.uasset')).resolve()
    assert path.is_relative_to(CONTENT / 'Yastars' / 'Mesh' / 'Clipboard'), str(path)
    return path


def package_hashes():
    result = {}
    for package in sorted(PACKAGES):
        path = package_file(package)
        assert path.is_file(), 'Missing original package: ' + package
        result[package] = {'file': str(path), 'bytes': path.stat().st_size, 'sha256': sha256(path)}
    return result


def texture_settings(texture):
    return {'srgb': texture.get_editor_property('srgb'),
            'compression_settings': str(texture.get_editor_property('compression_settings')),
            'flip_green_channel': texture.get_editor_property('flip_green_channel')}


def material_parameters(material):
    ml = unreal.MaterialEditingLibrary
    vectors, scalars = {}, {}
    for name in ml.get_vector_parameter_names(material):
        value = ml.get_material_default_vector_parameter_value(material, name)
        vectors[str(name)] = [value.r, value.g, value.b, value.a]
    for name in ml.get_scalar_parameter_names(material):
        scalars[str(name)] = ml.get_material_default_scalar_parameter_value(material, name)
    return {'asset': material.get_path_name(), 'vector_parameters': vectors, 'scalar_parameters': scalars}


def dependencies(registry, package):
    options = unreal.AssetRegistryDependencyOptions()
    for flag in ('include_hard_package_references', 'include_soft_package_references',
                 'include_searchable_names', 'include_hard_management_references',
                 'include_soft_management_references'):
        options.set_editor_property(flag, True)
    return sorted(set(str(value).split('.')[0] for value in registry.get_dependencies(package, options)))


try:
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert editor and unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem), 'Run in the full UE editor'
    edit = unreal.EditorAssetLibrary
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    registry.wait_for_completion()
    assert not registry.is_loading_assets(), 'Asset discovery is incomplete'
    world_before = editor.get_editor_world()
    report['world_before'] = world_before.get_path_name() if world_before else None
    assert PNG.is_file() and PNG.is_relative_to(CLIPBOARD_SOURCE / 'Textures'), str(PNG)
    assert all(edit.does_asset_exist(package) for package in PACKAGES), 'An original clipboard asset is missing'
    report['source_png_sha256'] = sha256(PNG)
    report['all_package_hashes_before'] = package_hashes()
    texture_before = edit.load_asset(TARGET)
    material_before = edit.load_asset(MATERIAL)
    assert isinstance(texture_before, unreal.Texture2D), TARGET
    assert isinstance(material_before, unreal.Material), MATERIAL
    report['texture_object_path_before'] = texture_before.get_path_name()
    report['texture_settings_before'] = texture_settings(texture_before)
    original_compression_setting = texture_before.get_editor_property('compression_settings')
    report['material_parameters_before'] = material_parameters(material_before)
    report['material_dependencies_before'] = dependencies(registry, MATERIAL)
    assert TARGET in report['material_dependencies_before'], 'Original paper material does not reference the expected texture'
    assert report['texture_settings_before']['srgb'], 'Original BaseColor texture is unexpectedly not sRGB'

    # Keep the exact original target package recoverable outside Content. A
    # previous backup must agree with this pre-update state; never overwrite it.
    backup = (OUT / 'BeforeUpdate' / 'T_ClipboardPaper_BaseColor.uasset').resolve()
    assert backup.is_relative_to(OUT), str(backup)
    backup.parent.mkdir(parents=True, exist_ok=True)
    original_sha = report['all_package_hashes_before'][TARGET]['sha256']
    if backup.exists():
        assert sha256(backup) == original_sha, 'Existing pre-update backup differs; review before another update'
    else:
        shutil.copy2(package_file(TARGET), backup)
    assert sha256(backup) == original_sha
    report['backup'] = {'file': str(backup), 'sha256': original_sha}
    checkpoint()

    task = unreal.AssetImportTask()
    for key, value in {'filename': str(PNG), 'destination_path': ROOT + '/Textures',
                       'destination_name': 'T_ClipboardPaper_BaseColor', 'automated': True,
                       'replace_existing': True, 'replace_existing_settings': False,
                       'save': False, 'factory': unreal.TextureFactory()}.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = [str(path) for path in task.get_editor_property('imported_object_paths')]
    report['imported_object_paths'] = imported
    assert len(imported) == 1 and imported[0].split('.')[0] == TARGET, imported
    texture_after = edit.load_asset(TARGET)
    assert isinstance(texture_after, unreal.Texture2D), TARGET
    report['same_texture_uobject'] = texture_after == texture_before
    report['texture_object_path_after'] = texture_after.get_path_name()
    assert report['same_texture_uobject'], 'Texture import unexpectedly replaced the existing UObject'
    assert report['texture_object_path_after'] == report['texture_object_path_before'], report

    # Some importer versions choose default settings despite the task option.
    # Restore the existing values only on the single authorized texture object.
    texture_after.set_editor_property('srgb', report['texture_settings_before']['srgb'])
    texture_after.set_editor_property('compression_settings', original_compression_setting)
    texture_after.set_editor_property('flip_green_channel', report['texture_settings_before']['flip_green_channel'])
    report['texture_settings_after'] = texture_settings(texture_after)
    assert report['texture_settings_after'] == report['texture_settings_before'], report
    assert edit.save_loaded_asset(texture_after, False), TARGET
    report['saved_packages'].append(TARGET)
    registry.scan_files_synchronous([str(package_file(TARGET))], True)

    material_after = edit.load_asset(MATERIAL)
    report['same_material_uobject'] = material_after == material_before
    report['material_parameters_after'] = material_parameters(material_after)
    report['material_dependencies_after'] = dependencies(registry, MATERIAL)
    assert report['same_material_uobject'], 'Original material object changed'
    assert report['material_parameters_after'] == report['material_parameters_before'], 'Material parameters changed'
    assert report['material_dependencies_after'] == report['material_dependencies_before'], 'Material references changed'
    assert TARGET in report['material_dependencies_after'], 'Paper material lost its BaseColor texture reference'
    report['all_package_hashes_after'] = package_hashes()
    report['changed_packages'] = sorted(package for package in PACKAGES
                                        if report['all_package_hashes_before'][package]['sha256']
                                        != report['all_package_hashes_after'][package]['sha256'])
    report['other_17_package_hashes_unchanged'] = all(
        report['all_package_hashes_before'][package]['sha256'] == report['all_package_hashes_after'][package]['sha256']
        for package in PACKAGES if package != TARGET)
    report['target_package_changed'] = TARGET in report['changed_packages']
    assert report['other_17_package_hashes_unchanged'], 'A protected clipboard package changed'
    assert report['changed_packages'] == [TARGET], report['changed_packages']
    assert report['saved_packages'] == [TARGET], report['saved_packages']
    assert sha256(PNG) == report['source_png_sha256'], 'Source PNG changed during import'
    world_after = editor.get_editor_world()
    report['world_after'] = world_after.get_path_name() if world_after else None
    report['same_world_object'] = world_after == world_before
    assert report['same_world_object'] and report['world_after'] == report['world_before']
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()
    try:
        report['all_package_hashes_after'] = package_hashes()
    except Exception:
        report['hash_audit_error'] = traceback.format_exc()

report['completed_utc'] = datetime.now(timezone.utc).isoformat()
checkpoint()
unreal.log('CLIPBOARD_RULED_PAPER_UPDATE ' + json.dumps(report))
