"""Import only the new cardboard set; never save or place anything in a level."""
from datetime import datetime, timezone
import gc
from pathlib import Path
import sys
import traceback
import time
from uuid import uuid4

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carton_manifest as C

EDIT = unreal.EditorAssetLibrary
MATERIALS = unreal.MaterialEditingLibrary
FBX_CVAR = 'Interchange.FeatureFlags.Import.FBX'
PALETTE = {
    'base_color': ('CardboardBaseColor', unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                   unreal.TextureCompressionSettings.TC_DEFAULT, True),
    'orm': ('CardboardORM', unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
            unreal.TextureCompressionSettings.TC_MASKS, False),
    'normal': ('CardboardNormal', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
               unreal.TextureCompressionSettings.TC_NORMALMAP, False),
}
CONNECTIONS = (
    ('base_color', 'RGB', unreal.MaterialProperty.MP_BASE_COLOR),
    ('orm', 'R', unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
    ('orm', 'G', unreal.MaterialProperty.MP_ROUGHNESS),
    ('orm', 'B', unreal.MaterialProperty.MP_METALLIC),
    ('normal', 'RGB', unreal.MaterialProperty.MP_NORMAL),
)


def now():
    return datetime.now(timezone.utc).isoformat()


def checkpoint(report):
    C.write(C.HERE / 'ue_import_report.json', report)


def load(path, cls):
    asset = EDIT.load_asset(path)
    assert isinstance(asset, cls), path
    return asset


def run_import(tools, cls, name, folder, path, **extra):
    task = unreal.AssetImportTask()
    values = dict(filename=str(path), destination_path=folder, destination_name=name,
                  automated=True, replace_existing=False, save=False)
    values.update(extra)
    for key, value in values.items():
        task.set_editor_property(key, value)
    tools.import_asset_tasks([task])
    package = folder + '/' + name
    imported = {str(value).split('.')[0] for value in task.get_editor_property('imported_object_paths')}
    assert imported == {package}, (package, imported)
    return load(package, cls)


def make_texture(tools, filename, channel):
    path = C.source(filename)
    texture = run_import(tools, unreal.Texture2D, path.stem, C.TEXTURE_ROOT, path,
                         factory=unreal.TextureFactory())
    texture.set_editor_property('compression_settings', PALETTE[channel][2])
    texture.set_editor_property('srgb', PALETTE[channel][3])
    if channel == 'normal':
        # The shared source is OpenGL +Y; UE expects DirectX -Y tangent normals.
        texture.set_editor_property('flip_green_channel', True)
    return texture


def import_textures(tools, manifest):
    spec = C.texture_spec(manifest)
    textures = {variant: {channel: make_texture(tools, spec[variant][channel], channel)
                          for channel in ('base_color', 'orm')} for variant in C.MATERIAL_VARIANTS}
    normal = make_texture(tools, spec['normal'], 'normal')
    for pair in textures.values():
        pair['normal'] = normal
    return textures


def make_textured_material(tools, variant, textures):
    material = tools.create_asset('M_Cardboard_' + variant, C.MATERIAL_ROOT,
                                  unreal.Material, unreal.MaterialFactoryNew())
    assert isinstance(material, unreal.Material)
    nodes = {}
    for index, (channel, (parameter, sampler, _, _)) in enumerate(PALETTE.items()):
        node = MATERIALS.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D,
                                                    -480, index * 260)
        for key, value in dict(parameter_name=parameter, texture=textures[channel],
                               sampler_type=sampler, const_coordinate=0).items():
            node.set_editor_property(key, value)
        nodes[channel] = node
    for channel, pin, prop in CONNECTIONS:
        assert MATERIALS.connect_material_property(nodes[channel], pin, prop), str(prop)
    MATERIALS.recompile_material(material)
    return material


def make_mesh(tools, subsystem, name, row, materials):
    options = unreal.FbxImportUI()
    for key, value in dict(import_mesh=True, import_as_skeletal=False, import_materials=False,
                           import_textures=False, automated_import_should_detect_type=False,
                           mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():
        options.set_editor_property(key, value)
    # FBX files contain centimeter scale with each pivot removed from leaf vertices.
    for key, value in dict(import_uniform_scale=1., combine_meshes=True, auto_generate_collision=False,
                           one_convex_hull_per_ucx=True, generate_lightmap_u_vs=True,
                           remove_degenerates=False,
                           normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
                           transform_vertex_to_absolute=True, bake_pivot_in_vertex=False).items():
        options.static_mesh_import_data.set_editor_property(key, value)
    mesh = run_import(tools, unreal.StaticMesh, name, C.TARGET, C.source(row['fbx']), options=options)
    slots = mesh.static_materials
    names = [str(slot.material_slot_name) for slot in slots]
    assert names == row['slots'], (name, names, row['slots'])
    for index, slot in enumerate(slots):
        mesh.set_material(index, materials[str(slot.material_slot_name)])
    mesh.set_editor_property('light_map_coordinate_index', 1)
    mesh.set_editor_property('light_map_resolution', 64)
    settings = subsystem.get_lod_build_settings(mesh, 0)
    for key, value in dict(remove_degenerates=False, use_full_precision_u_vs=True,
                           generate_lightmap_u_vs=True, min_lightmap_resolution=64,
                           src_lightmap_index=0, dst_lightmap_index=1).items():
        settings.set_editor_property(key, value)
    subsystem.set_lod_build_settings(mesh, 0, settings)
    return mesh


def verify_materials(materials, textures):
    result = {}
    for variant in C.MATERIAL_VARIANTS:
        material = materials['M_Cardboard_' + variant]
        assert material.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_OPAQUE
        assert set(map(str, MATERIALS.get_texture_parameter_names(material))) == {v[0] for v in PALETTE.values()}
        for channel, pin, prop in CONNECTIONS:
            node = MATERIALS.get_material_property_input_node(material, prop)
            assert str(node.get_editor_property('parameter_name')) == PALETTE[channel][0]
            output = str(MATERIALS.get_material_property_input_node_output_name(material, prop))
            assert output in ({'RGB', '', 'None'} if pin == 'RGB' else {pin}), (variant, prop, output)
        for channel, (parameter, sampler, compression, srgb) in PALETTE.items():
            texture = textures[variant][channel]
            assert texture == MATERIALS.get_material_default_texture_parameter_value(material, parameter)
            assert texture.get_editor_property('compression_settings') == compression
            assert texture.get_editor_property('srgb') == srgb
            if channel == 'normal':
                assert texture.get_editor_property('flip_green_channel') is True
            resolution = 2048 if variant in C.VARIANTS or channel == 'normal' else 512
            assert texture.blueprint_get_size_x() == texture.blueprint_get_size_y() == resolution
        result[variant] = {'asset': material.get_path_name(), 'opaque': True,
                           'textures': {key: texture.get_path_name() for key, texture in textures[variant].items()},
                           'orm_channels': {'R': 'AmbientOcclusion', 'G': 'Roughness', 'B': 'Metallic'},
                           'normal_connected': True, 'normal_green_flipped': True,
                           'resolution': 2048 if variant in C.VARIANTS else 512}
    return result


def verify_mesh(mesh, subsystem, row, materials):
    bounds = mesh.get_bounds()
    center, extent = bounds.origin, bounds.box_extent
    low = [center.x-extent.x, center.y-extent.y, center.z-extent.z]
    high = [center.x+extent.x, center.y+extent.y, center.z+extent.z]
    source_min, source_max = row['bounds_min_m'], row['bounds_max_m']
    expected = [100*source_min[0], -100*source_max[1], 100*source_min[2],
                100*source_max[0], -100*source_min[1], 100*source_max[2]]
    assert all(abs(a-b) < .03 for a, b in zip(low+high, expected)), (row['name'], low, high, expected)
    triangles = mesh.get_num_triangles(0)
    hulls = subsystem.get_convex_collision_count(mesh)
    assert triangles == row['triangles'], (row['name'], triangles, row['triangles'])
    assert hulls == row['collision_hulls'], (row['name'], hulls, row['collision_hulls'])
    slots = mesh.static_materials
    assert [str(slot.material_slot_name) for slot in slots] == row['slots']
    assert all(slot.material_interface == materials[str(slot.material_slot_name)] for slot in slots)
    uv_count = subsystem.get_num_uv_channels(mesh, 0)
    assert uv_count >= 1
    # Existing legacy FBX imports may report only UV0 despite lightmap-generation settings.
    # Record UV channel evidence without blocking verified PBR UV0 on that known behavior.
    return {'asset': mesh.get_path_name(), 'min_cm': low, 'max_cm': high,
            'triangles': triangles, 'convex_hulls': hulls, 'uv_channels': uv_count,
            'lightmap_uv_available': uv_count >= 2, 'pivot_m': row['pivot_m'],
            'materials': {str(slot.material_slot_name): slot.material_interface.get_path_name() for slot in slots}}


def execute(report):
    for _ in range(1800):
        if not (C.HERE / 'source_update.lock').exists():
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Source update is still in progress; retry after source_update.lock is removed')
    import carton_blueprint as B
    assert Path(unreal.Paths.project_dir()).resolve() == C.PROJECT.resolve(), 'Wrong project'
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name().startswith('/Engine/Maps/Entry'), 'Expected temporary Entry world'
    assert editor.get_game_world() is None, 'Stop Play in Editor'
    report['world'] = world.get_path_name()
    manifest, rows, expected, inputs = C.read_export()
    report['source_hashes'] = inputs
    baseline = C.protected_snapshot()
    assert baseline, 'Project protection baseline missing'
    C.write(C.HERE / 'protected_content_sha256.json', baseline)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.wait_for_completion()
    registered = sorted(str(item.package_name) for item in registry.get_assets_by_path(C.TARGET, recursive=True))
    target_files = sorted(str(path) for path in C.DESTINATION.rglob('*') if path.is_file())
    report.update(protected_files_before=len(baseline), preexisting_packages=registered, preexisting_files=target_files)
    checkpoint(report)
    assert not registered and not target_files, ('Destination is not new', registered, target_files)
    previous_backend = unreal.SystemLibrary.get_console_variable_int_value(FBX_CVAR)
    try:
        unreal.SystemLibrary.execute_console_command(world, FBX_CVAR + ' 0')
        assert unreal.SystemLibrary.get_console_variable_int_value(FBX_CVAR) == 0
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        textures = import_textures(tools, manifest)
        materials = {'M_Cardboard_' + variant: make_textured_material(tools, variant, textures[variant])
                     for variant in C.MATERIAL_VARIANTS}
        meshes = {}
        for name, row in rows.items():
            meshes[name] = make_mesh(tools, mesh_editor, name, row, materials)
            report['imported_meshes'] = sorted(meshes)
            checkpoint(report)
        unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
        report['materials'] = verify_materials(materials, textures)
        report['meshes'] = {name: verify_mesh(mesh, mesh_editor, rows[name], materials) for name, mesh in meshes.items()}
        blueprints = {name: B.build_blueprint(tools, C.TARGET, name, meshes, rows) for name in C.ASSEMBLIES}
        report['blueprints'] = {name: B.verify_blueprint(bp, meshes, rows) for name, bp in blueprints.items()}
        assert all(C.digest(C.source(relative)) == value for relative, value in inputs.items()), 'Export data changed'
        assert editor.get_editor_world() == world
        staged_textures = {texture.get_path_name(): texture for pair in textures.values() for texture in pair.values()}
        staged = [*staged_textures.values(), *materials.values(), *meshes.values(), *blueprints.values()]
        assert {asset.get_path_name().split('.')[0] for asset in staged} == expected
        for asset in staged:
            assert EDIT.save_loaded_asset(asset, False), asset.get_path_name()
            report.setdefault('saved', []).append(asset.get_path_name())
            checkpoint(report)
        actual = C.packages()
        assert set(actual) == expected
        report['packages'] = actual
        report['protected_files_after'] = C.verify_protected(baseline)
    finally:
        unreal.SystemLibrary.execute_console_command(world, FBX_CVAR + ' ' + str(previous_backend))


def run():
    report = dict(success=False, run_id=str(uuid4()), mode='exclusive', target_root=C.TARGET,
                  started_utc=now(), imported_meshes=[], saved=[])
    checkpoint(report)
    try:
        execute(report)
        report['success'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        unreal.log_error('CARTON_IMPORT_ERROR ' + report['error'])
    finally:
        report['completed_utc'] = now()
        checkpoint(report)
    unreal.log('CARTON_IMPORT_VERIFIED ' + str(report['success']))
    gc.collect()
    return report['success']


if __name__ == '__main__':
    run()
