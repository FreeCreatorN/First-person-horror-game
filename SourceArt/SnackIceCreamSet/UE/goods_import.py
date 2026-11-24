"""Create only new goods assets, with shared textured parent and movable assemblies."""
from datetime import datetime, timezone
import gc
from pathlib import Path
import sys
import traceback
from uuid import uuid4

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goods_manifest as C

EDIT = unreal.EditorAssetLibrary
MATERIALS = unreal.MaterialEditingLibrary
FBX_CVAR = 'Interchange.FeatureFlags.Import.FBX'
PALETTE = {
    'base_color': ('GoodsBaseColor', unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                   unreal.TextureCompressionSettings.TC_DEFAULT, True),
    'orm': ('GoodsORM', unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
            unreal.TextureCompressionSettings.TC_MASKS, False),
    'normal': ('GoodsNormal', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
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
        texture.set_editor_property('flip_green_channel', True)
    return texture


def import_textures(tools, manifest):
    spec = C.texture_spec(manifest)
    normal = make_texture(tools, spec['normal'], 'normal')
    return {name: dict(base_color=make_texture(tools, pair['base_color'], 'base_color'),
                       orm=make_texture(tools, pair['orm'], 'orm'), normal=normal)
            for name, pair in spec.items() if name != 'normal'}


def load_textures(manifest):
    spec = C.texture_spec(manifest)
    normal = load(C.TEXTURE_ROOT + '/' + Path(spec['normal']).stem, unreal.Texture2D)
    return {name: dict(base_color=load(C.TEXTURE_ROOT + '/' + Path(pair['base_color']).stem, unreal.Texture2D),
                       orm=load(C.TEXTURE_ROOT + '/' + Path(pair['orm']).stem, unreal.Texture2D), normal=normal)
            for name, pair in spec.items() if name != 'normal'}


def make_parent(tools, defaults):
    material = tools.create_asset(C.PARENT, C.MATERIAL_ROOT, unreal.Material, unreal.MaterialFactoryNew())
    assert isinstance(material, unreal.Material)
    nodes = {}
    for index, (channel, (parameter, sampler, _, _)) in enumerate(PALETTE.items()):
        node = MATERIALS.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D,
                                                    -480, index * 260)
        for key, value in dict(parameter_name=parameter, texture=defaults[channel],
                               sampler_type=sampler, const_coordinate=0).items():
            node.set_editor_property(key, value)
        nodes[channel] = node
    for channel, pin, prop in CONNECTIONS:
        assert MATERIALS.connect_material_property(nodes[channel], pin, prop), str(prop)
    MATERIALS.recompile_material(material)
    return material


def make_instance(tools, name, parent, textures):
    material = tools.create_asset(name, C.MATERIAL_ROOT, unreal.MaterialInstanceConstant,
                                  unreal.MaterialInstanceConstantFactoryNew())
    assert isinstance(material, unreal.MaterialInstanceConstant)
    MATERIALS.set_material_instance_parent(material, parent)
    for channel, (parameter, _, _, _) in PALETTE.items():
        MATERIALS.set_material_instance_texture_parameter_value(material, parameter, textures[channel])
    MATERIALS.update_material_instance(material)
    return material


def linear_color(spec):
    def convert(value):
        return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
    raw = spec['color']
    rgb = [convert(value) for value in raw[:3]] if spec['color_space'] == 'srgb' else raw[:3]
    return [*rgb, raw[3]]


def generic_scalars(spec):
    values = {unreal.MaterialProperty.MP_ROUGHNESS: ('GoodsRoughness', spec['roughness']),
              unreal.MaterialProperty.MP_METALLIC: ('GoodsMetallic', spec['metallic'])}
    if spec['type'] == 'translucent':
        values[unreal.MaterialProperty.MP_OPACITY] = ('GoodsOpacity', spec['opacity'])
        values[unreal.MaterialProperty.MP_REFRACTION] = ('GoodsIOR', spec['ior'])
    return values


def make_generic(tools, name, spec):
    material = tools.create_asset(name, C.MATERIAL_ROOT, unreal.Material, unreal.MaterialFactoryNew())
    assert isinstance(material, unreal.Material)
    material.set_editor_property('two_sided', spec['two_sided'])
    if spec['type'] == 'translucent':
        for key, value in dict(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT,
                               translucency_lighting_mode=unreal.TranslucencyLightingMode.TLM_SURFACE,
                               shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
                               refraction_method=unreal.RefractionMode.RM_INDEX_OF_REFRACTION).items():
            material.set_editor_property(key, value)
    color = MATERIALS.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -440, -140)
    color.set_editor_property('parameter_name', 'GoodsColor')
    color.set_editor_property('default_value', unreal.LinearColor(*linear_color(spec)))
    assert MATERIALS.connect_material_property(color, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
    for index, (prop, (parameter, value)) in enumerate(generic_scalars(spec).items()):
        node = MATERIALS.create_material_expression(material, unreal.MaterialExpressionScalarParameter,
                                                    -440, 40 + index * 150)
        node.set_editor_property('parameter_name', parameter)
        node.set_editor_property('default_value', value)
        assert MATERIALS.connect_material_property(node, '', prop), str(prop)
    MATERIALS.recompile_material(material)
    return material


def make_mesh(tools, subsystem, name, row, materials):
    options = unreal.FbxImportUI()
    for key, value in dict(import_mesh=True, import_as_skeletal=False, import_materials=False,
                           import_textures=False, automated_import_should_detect_type=False,
                           mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():
        options.set_editor_property(key, value)
    for key, value in dict(import_uniform_scale=1., combine_meshes=True, auto_generate_collision=False,
                           one_convex_hull_per_ucx=True, generate_lightmap_u_vs=True,
                           remove_degenerates=False,
                           normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
                           transform_vertex_to_absolute=True, bake_pivot_in_vertex=False).items():
        options.static_mesh_import_data.set_editor_property(key, value)
    mesh = run_import(tools, unreal.StaticMesh, name, C.TARGET, C.source(row['fbx']), options=options)
    slots = mesh.static_materials
    assert [str(slot.material_slot_name) for slot in slots] == row['slots'], (name, row['slots'])
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


def verify_parent(parent):
    assert parent.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_OPAQUE
    assert set(map(str, MATERIALS.get_texture_parameter_names(parent))) == {v[0] for v in PALETTE.values()}
    for channel, pin, prop in CONNECTIONS:
        node = MATERIALS.get_material_property_input_node(parent, prop)
        assert str(node.get_editor_property('parameter_name')) == PALETTE[channel][0]
        assert node.get_editor_property('sampler_type') == PALETTE[channel][1]
        output = str(MATERIALS.get_material_property_input_node_output_name(parent, prop))
        assert output in ({'RGB', '', 'None'} if pin == 'RGB' else {pin}), (prop, output)
    assert MATERIALS.get_material_property_input_node(parent, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None
    return dict(asset=parent.get_path_name(), opaque=True, uv_index=0,
                orm_channels={'R': 'AmbientOcclusion', 'G': 'Roughness', 'B': 'Metallic'}, normal_connected=True)


def verify_materials(manifest, parent, materials, textures):
    result = {}
    spec = C.texture_spec(manifest)
    for name, pair in textures.items():
        material = materials[name]
        assert isinstance(material, unreal.MaterialInstanceConstant)
        assert material.get_editor_property('parent') == parent
        stored = {str(item.parameter_info.name): item.parameter_value
                  for item in material.get_editor_property('texture_parameter_values')}
        assert set(stored) == {v[0] for v in PALETTE.values()}
        evidence = {}
        for channel, (parameter, _, compression, srgb) in PALETTE.items():
            texture = pair[channel]
            assert stored[parameter] == texture == MATERIALS.get_material_instance_texture_parameter_value(material, parameter)
            assert texture.get_editor_property('compression_settings') == compression
            assert texture.get_editor_property('srgb') == srgb
            if channel == 'normal':
                assert texture.get_editor_property('flip_green_channel') is True
            filename = spec['normal'] if channel == 'normal' else spec[name][channel]
            evidence[channel] = dict(asset=texture.get_path_name(), source_size=C.image_dimensions(C.source(filename)),
                                     srgb=srgb, compression=str(compression), parameter=parameter)
        result[name] = dict(asset=material.get_path_name(), kind='textured_instance', parent=parent.get_path_name(),
                            textures=evidence, normal_green_flipped=True)
    for name, raw in C.generic_spec(manifest).items():
        material = materials[name]
        translucent = raw['type'] == 'translucent'
        blend = unreal.BlendMode.BLEND_TRANSLUCENT if translucent else unreal.BlendMode.BLEND_OPAQUE
        assert material.get_editor_property('blend_mode') == blend
        assert material.get_editor_property('two_sided') == raw['two_sided']
        if translucent:
            assert material.get_editor_property('translucency_lighting_mode') == unreal.TranslucencyLightingMode.TLM_SURFACE
            assert material.get_editor_property('refraction_method') == unreal.RefractionMode.RM_INDEX_OF_REFRACTION
        node = MATERIALS.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
        assert str(node.get_editor_property('parameter_name')) == 'GoodsColor'
        color = node.get_editor_property('default_value')
        assert all(abs(a-b) < 1e-5 for a, b in zip([color.r, color.g, color.b, color.a], linear_color(raw)))
        for prop, (parameter, value) in generic_scalars(raw).items():
            node = MATERIALS.get_material_property_input_node(material, prop)
            assert str(node.get_editor_property('parameter_name')) == parameter
            assert abs(node.get_editor_property('default_value') - value) < 1e-5
        assert MATERIALS.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None
        result[name] = dict(asset=material.get_path_name(), kind=raw['type'], source_spec=raw,
                            linear_color=linear_color(raw), translucent=translucent)
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
    settings = subsystem.get_lod_build_settings(mesh, 0)
    assert settings.get_editor_property('use_full_precision_u_vs') is True
    return dict(asset=mesh.get_path_name(), min_cm=low, max_cm=high, triangles=triangles,
                convex_hulls=hulls, uv_channels=uv_count, lightmap_uv_available=uv_count >= 2,
                full_precision_uvs=True, pivot_m=row['pivot_m'],
                materials={str(slot.material_slot_name): slot.material_interface.get_path_name() for slot in slots})


def execute(report):
    import goods_blueprint as B
    assert Path(unreal.Paths.project_dir()).resolve() == C.PROJECT.resolve(), 'Wrong project'
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    assert world and world.get_path_name().startswith('/Engine/Maps/Entry'), 'Expected temporary Entry world'
    assert editor.get_game_world() is None, 'Stop Play in Editor'
    assert not (C.HERE / 'source_update.lock').exists(), 'Source is still being authored'
    report['world'] = world.get_path_name()
    manifest, rows, expected, inputs = C.read_export()
    groups = C.assemblies(manifest, rows)
    report['source_hashes'] = inputs
    baseline = C.read(C.HERE / 'protected_content_sha256.json')
    assert baseline, 'Pre-launch project protection baseline missing'
    C.verify_protected(baseline)
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
        parent = make_parent(tools, next(iter(textures.values())))
        materials = {name: make_instance(tools, name, parent, pair) for name, pair in textures.items()}
        materials.update({name: make_generic(tools, name, spec) for name, spec in C.generic_spec(manifest).items()})
        meshes = {}
        for name, row in rows.items():
            meshes[name] = make_mesh(tools, mesh_editor, name, row, materials)
            report['imported_meshes'] = sorted(meshes)
            checkpoint(report)
        unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
        report['parent_material'] = verify_parent(parent)
        report['materials'] = verify_materials(manifest, parent, materials, textures)
        report['meshes'] = {name: verify_mesh(mesh, mesh_editor, rows[name], materials) for name, mesh in meshes.items()}
        blueprints = {name: B.build_blueprint(tools, name, parts, meshes, rows) for name, parts in groups.items()}
        report['blueprints'] = {name: B.verify_blueprint(bp, groups[name], meshes, rows) for name, bp in blueprints.items()}
        assert all(C.digest(C.source(relative)) == value for relative, value in inputs.items()), 'Export data changed'
        assert editor.get_editor_world() == world
        staged_textures = {texture.get_path_name(): texture for pair in textures.values() for texture in pair.values()}
        staged = [*staged_textures.values(), parent, *materials.values(), *meshes.values(), *blueprints.values()]
        assert {asset.get_path_name().split('.')[0] for asset in staged} == expected
        for asset in staged:
            assert asset.get_path_name().split('.')[0].startswith(C.TARGET + '/')
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
        unreal.log_error('GOODS_IMPORT_ERROR ' + report['error'])
    finally:
        report['completed_utc'] = now()
        checkpoint(report)
    unreal.log('GOODS_IMPORT_VERIFIED ' + str(report['success']))
    gc.collect()
    return report['success']


if __name__ == '__main__':
    run()
