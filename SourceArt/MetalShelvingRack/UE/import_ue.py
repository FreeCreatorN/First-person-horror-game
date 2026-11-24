"""Exclusive UE editor import and fresh read-only verification."""
from datetime import datetime, timezone
import gc
import os
from pathlib import Path
import sys
import traceback

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rack_manifest import (DESTINATION, HERE, MANIFEST, PARENT_NAME, PROJECT, TARGET,
                           digest, packages, read, read_export, source, verify_protected, write)

EDIT = unreal.EditorAssetLibrary
ML = unreal.MaterialEditingLibrary
CVAR = 'Interchange.FeatureFlags.Import.FBX'
MATERIAL_ROOT = TARGET + '/Materials'
TEXTURE_ROOT = TARGET + '/Textures'
WORLD = '/Engine/Maps/Entry'
BASE = 'RackBaseColor'
ORM = 'RackORM'
PALETTE = {'base_color': (BASE, unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                          unreal.TextureCompressionSettings.TC_DEFAULT, True),
           'orm': (ORM, unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                   unreal.TextureCompressionSettings.TC_MASKS, False)}
CONNECTIONS = ((BASE, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR),
               (ORM, 'R', unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
               (ORM, 'G', unreal.MaterialProperty.MP_ROUGHNESS),
               (ORM, 'B', unreal.MaterialProperty.MP_METALLIC))
READ_ONLY = os.environ.get('RACK_UE_VERIFY_ONLY') == '1'
REPORT = HERE / ('ue_reload_report.json' if READ_ONLY else 'ue_import_report.json')


def checkpoint(report):
    write(REPORT, report)


def load(path, cls):
    asset = EDIT.load_asset(path)
    assert isinstance(asset, cls), path
    return asset


def run_import(asset_tools, cls, name, folder, path, extra):
    task = unreal.AssetImportTask()
    settings = dict(filename=str(path), destination_path=folder, destination_name=name,
                    automated=True, replace_existing=False, save=False)
    settings.update(extra)
    for key, value in settings.items():
        task.set_editor_property(key, value)
    asset_tools.import_asset_tasks([task])
    package = folder + '/' + name
    imported = {str(value).split('.')[0] for value in task.get_editor_property('imported_object_paths')}
    assert imported == {package}, (package, imported)
    return load(package, cls)


def make_texture(asset_tools, row, channel):
    path = source(row[channel])
    texture = run_import(asset_tools, unreal.Texture2D, path.stem, TEXTURE_ROOT,
                         path, dict(factory=unreal.TextureFactory()))
    compression, srgb = PALETTE[channel][2:]
    texture.set_editor_property('compression_settings', compression)
    texture.set_editor_property('srgb', srgb)
    return texture


def make_parent(asset_tools, defaults):
    material = asset_tools.create_asset(PARENT_NAME, MATERIAL_ROOT, unreal.Material, unreal.MaterialFactoryNew())
    assert isinstance(material, unreal.Material)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property('two_sided', False)
    nodes = {}
    for index, (channel, (param, sampler, _, _)) in enumerate(PALETTE.items()):
        node = ML.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D, -580, index * 300)
        node.set_editor_property('parameter_name', param)
        node.set_editor_property('group', 'Rack Finish')
        node.set_editor_property('texture', defaults[channel])
        node.set_editor_property('sampler_type', sampler)
        node.set_editor_property('const_coordinate', 0)
        nodes[param] = node
    for param, channel, prop in CONNECTIONS:
        assert ML.connect_material_property(nodes[param], channel, prop), str(prop)
    ML.recompile_material(material)
    return material


def make_instance(asset_tools, row, parent, textures):
    instance = asset_tools.create_asset(row['material'], MATERIAL_ROOT, unreal.MaterialInstanceConstant,
                                        unreal.MaterialInstanceConstantFactoryNew())
    assert isinstance(instance, unreal.MaterialInstanceConstant)
    ML.set_material_instance_parent(instance, parent)
    for channel, (param, _, _, _) in PALETTE.items():
        # UE 5.7 can report false here even when setting a texture succeeds.
        ML.set_material_instance_texture_parameter_value(instance, param, textures[channel])
    ML.update_material_instance(instance)
    return instance


def make_mesh(asset_tools, mesh_editor, row, instance):
    options = unreal.FbxImportUI()
    for key, value in dict(import_mesh=True, import_as_skeletal=False, import_materials=False, import_textures=False,
                           automated_import_should_detect_type=False,
                           mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():
        options.set_editor_property(key, value)
    # The FBX exporter already writes centimeter geometry. UE applies the
    # serialized unit transform before any additional user scale.
    for key, value in dict(import_uniform_scale=1., combine_meshes=True, auto_generate_collision=False,
                           one_convex_hull_per_ucx=True, generate_lightmap_u_vs=True, remove_degenerates=False,
                           normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
                           transform_vertex_to_absolute=True, bake_pivot_in_vertex=False).items():
        options.static_mesh_import_data.set_editor_property(key, value)
    mesh = run_import(asset_tools, unreal.StaticMesh, row['name'], TARGET, source(row['fbx']), dict(options=options))
    assert len(mesh.static_materials) == 1, (row['name'], [str(slot.material_slot_name) for slot in mesh.static_materials])
    mesh.set_material(0, instance)
    mesh.set_editor_property('light_map_resolution', 128)
    mesh.set_editor_property('light_map_coordinate_index', 1)
    settings = mesh_editor.get_lod_build_settings(mesh, 0)
    for key, value in dict(remove_degenerates=False, use_full_precision_u_vs=True, generate_lightmap_u_vs=True,
                           min_lightmap_resolution=128, src_lightmap_index=0, dst_lightmap_index=1).items():
        settings.set_editor_property(key, value)
    mesh_editor.set_lod_build_settings(mesh, 0, settings)
    return mesh


def verify_parent(parent, textures):
    assert parent.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_OPAQUE
    assert parent.get_editor_property('shading_model') == unreal.MaterialShadingModel.MSM_DEFAULT_LIT
    assert parent.get_editor_property('two_sided') is False
    assert set(map(str, ML.get_texture_parameter_names(parent))) == {BASE, ORM}
    assert ML.get_material_property_input_node(parent, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None
    inputs = {}
    for param, selector, prop in CONNECTIONS:
        node = ML.get_material_property_input_node(parent, prop)
        assert isinstance(node, unreal.MaterialExpressionTextureSampleParameter2D), str(prop)
        assert str(node.get_editor_property('parameter_name')) == param
        assert node.get_editor_property('const_coordinate') == 0
        actual_selector = str(ML.get_material_property_input_node_output_name(parent, prop))
        # UE often serializes the default RGB output without a displayed name.
        assert actual_selector in ({'RGB', '', 'None'} if selector == 'RGB' else {selector}), (prop, actual_selector)
        inputs[str(prop)] = f'{param}.{selector}'
    for channel, (param, _, _, _) in PALETTE.items():
        assert ML.get_material_default_texture_parameter_value(parent, param) == textures[channel]
    return {'asset': parent.get_path_name(), 'connections': inputs, 'uv_index': 0}


def verify_textures(instance, parent, textures, image_size):
    assert instance.get_editor_property('parent') == parent
    stored = {str(item.parameter_info.name): item.parameter_value
              for item in instance.get_editor_property('texture_parameter_values')}
    assert set(stored) == {BASE, ORM}
    report = {}
    for channel, (param, _, compression, srgb) in PALETTE.items():
        texture = textures[channel]
        assert texture.get_editor_property('srgb') == srgb
        assert texture.get_editor_property('compression_settings') == compression
        assert stored[param] == ML.get_material_instance_texture_parameter_value(instance, param) == texture
        # Check the original imported texture dimensions in the source manifest.
        # Platform texture size can depend on editor quality/streaming state.
        report[channel] = {'asset': texture.get_path_name(), 'source_size': [image_size]*2,
                           'srgb': srgb, 'compression': str(compression), 'parameter': param}
    return report


def close(values, expected, tolerance=.015):
    return all(abs(a - b) <= tolerance for a, b in zip(values, expected))


def verify_mesh(mesh, mesh_editor, row, instance):
    bounds = mesh.get_bounds()
    center, extent = bounds.origin, bounds.box_extent
    minimum = [center.x - extent.x, center.y - extent.y, center.z - extent.z]
    maximum = [center.x + extent.x, center.y + extent.y, center.z + extent.z]
    lo, hi = row['bounds_min_m'], row['bounds_max_m']
    # Legacy FBX import keeps X/Z and reverses the Blender Y axis.
    expected_min = [lo[0]*100, -hi[1]*100, lo[2]*100]
    expected_max = [hi[0]*100, -lo[1]*100, hi[2]*100]
    assert close(minimum + maximum, expected_min + expected_max), (row['name'], minimum, maximum, expected_min, expected_max)
    assert mesh.get_num_triangles(0) == row['triangles'], (row['name'], mesh.get_num_triangles(0), row['triangles'])
    hulls = mesh_editor.get_convex_collision_count(mesh)
    assert hulls == row['collision_hulls'], (row['name'], hulls, row['collision_hulls'])
    uv_count = mesh_editor.get_num_uv_channels(mesh, 0)
    slots = mesh.static_materials
    assert len(slots) == 1 and slots[0].material_interface == instance
    lod = mesh_editor.get_lod_build_settings(mesh, 0)
    assert lod.get_editor_property('remove_degenerates') is False
    assert mesh.get_editor_property('asset_import_data').get_editor_property('remove_degenerates') is False
    assert lod.get_editor_property('use_full_precision_u_vs') is True
    assert lod.get_editor_property('generate_lightmap_u_vs') is True
    assert uv_count >= 1
    assert mesh.get_editor_property('light_map_coordinate_index') == 1
    return {'asset': mesh.get_path_name(), 'material': instance.get_path_name(), 'material_slot': str(slots[0].material_slot_name),
            'levels': row['levels'], 'triangles': mesh.get_num_triangles(0), 'convex_hulls': hulls,
            'min_cm': minimum, 'max_cm': maximum, 'dimensions_cm': [b-a for a, b in zip(minimum, maximum)],
            'uv_channels': uv_count, 'lightmap_coordinate_index': 1,
            'lightmap_resolution': mesh.get_editor_property('light_map_resolution')}


def verify_inputs(input_hashes):
    return all(digest(source(relative)) == sha for relative, sha in input_hashes.items())


def execute(report):
    assert Path(unreal.Paths.project_dir()).resolve() == PROJECT.resolve(), 'Wrong UE project'
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name().startswith(WORLD), 'Requires temporary Engine Entry world'
    report['world'] = world.get_path_name()
    manifest, expected, input_hashes = read_export()
    report['source_hashes'] = input_hashes
    assert report['manifest_sha256'] == input_hashes[MANIFEST.name]
    baseline_path = HERE / 'protected_content_sha256.json'
    assert digest(baseline_path) == report['baseline_sha256']
    baseline = read(baseline_path)
    assert baseline
    report['protected_files_before'] = verify_protected(baseline)

    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    registry.wait_for_completion()
    registered = {str(item.package_name) for item in registry.get_assets_by_path(TARGET, recursive=True)}
    on_disk = packages()
    report['existing_target_packages'] = sorted(registered | on_disk.keys())
    checkpoint(report)
    if READ_ONLY:
        assert registered == set(on_disk) == expected
        import_report = read(HERE / 'ue_import_report.json')
        assert import_report['success'] and import_report['packages'] == on_disk
    else:
        stray_files = [str(file) for file in DESTINATION.rglob('*') if file.is_file()]
        assert not registered and not on_disk and not stray_files, ('Destination already contains assets', registered, stray_files)

    rows = {row['name']: row for row in manifest['assets']}
    assets = {}
    previous_backend = None
    try:
        if READ_ONLY:
            parent = load(MATERIAL_ROOT + '/' + PARENT_NAME, unreal.Material)
            for name, row in rows.items():
                textures = {key: load(TEXTURE_ROOT + '/' + source(row[key]).stem, unreal.Texture2D) for key in PALETTE}
                assets[name] = (load(TARGET + '/' + name, unreal.StaticMesh),
                                load(MATERIAL_ROOT + '/' + row['material'], unreal.MaterialInstanceConstant), textures)
        else:
            previous_backend = unreal.SystemLibrary.get_console_variable_int_value(CVAR)
            unreal.SystemLibrary.execute_console_command(world, CVAR + ' 0')
            assert unreal.SystemLibrary.get_console_variable_int_value(CVAR) == 0
            tools = unreal.AssetToolsHelpers.get_asset_tools()
            textures_by_mesh = {name: {key: make_texture(tools, row, key) for key in PALETTE} for name, row in rows.items()}
            parent = make_parent(tools, textures_by_mesh['SM_MetalShelvingRack_7Level'])
            for name, row in rows.items():
                instance = make_instance(tools, row, parent, textures_by_mesh[name])
                mesh = make_mesh(tools, mesh_editor, row, instance)
                assets[name] = (mesh, instance, textures_by_mesh[name])
                report['imported_meshes'] = sorted(assets)
                checkpoint(report)
            unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')

        report['parent'] = verify_parent(parent, assets['SM_MetalShelvingRack_7Level'][2])
        report['meshes'] = {}
        for name, (mesh, instance, textures) in assets.items():
            row = rows[name]
            report['meshes'][name] = verify_mesh(mesh, mesh_editor, row, instance)
            report['meshes'][name]['textures'] = verify_textures(instance, parent, textures, manifest['baked_resolution'])
            checkpoint(report)
        assert verify_inputs(input_hashes), 'Export input changed during import'
        assert editor.get_editor_world() == world

        if not READ_ONLY:
            staged = [texture for _, _, textures in assets.values() for texture in textures.values()]
            staged.append(parent)
            staged.extend(instance for _, instance, _ in assets.values())
            staged.extend(mesh for mesh, _, _ in assets.values())
            assert {asset.get_path_name().split('.')[0] for asset in staged} == expected
            for asset in staged:
                assert EDIT.save_loaded_asset(asset, False), asset.get_path_name()
                report.setdefault('saved', []).append(asset.get_path_name())
                checkpoint(report)
        report['packages'] = packages()
        assert set(report['packages']) == expected
        if READ_ONLY:
            assert report['packages'] == on_disk
            assert report['meshes'] == import_report['meshes'], 'Persisted mesh verification differs from import'
        report['protected_files_after'] = verify_protected(baseline)
        report['success'] = True
    finally:
        if previous_backend is not None:
            unreal.SystemLibrary.execute_console_command(world, CVAR + ' ' + str(previous_backend))
            assert unreal.SystemLibrary.get_console_variable_int_value(CVAR) == previous_backend


def main():
    report = dict(success=False, mode='reload' if READ_ONLY else 'import', target_root=TARGET,
                  editor_pid=os.getpid(), run_id=os.environ.get('RACK_UE_RUN_ID'),
                  script_sha256=digest(Path(__file__)), manifest_sha256=os.environ.get('RACK_UE_MANIFEST_SHA'),
                  baseline_sha256=os.environ.get('RACK_UE_BASELINE_SHA'),
                  started_utc=datetime.now(timezone.utc).isoformat())
    try:
        execute(report)
    except Exception:
        report['success'] = False
        report['error'] = traceback.format_exc()
        unreal.log_error('SHELVING_RACK_IMPORT_ERROR ' + report['error'])
    finally:
        report['completed_utc'] = datetime.now(timezone.utc).isoformat()
        checkpoint(report)
    unreal.log('SHELVING_RACK_' + report['mode'].upper() + '_VERIFIED ' + str(report['success']))


main()
gc.collect()
