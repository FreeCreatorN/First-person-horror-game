"""Import one altar-table mesh and its three baked maps, preserving old assets."""
import json
import traceback
from pathlib import Path

import unreal

OUT = Path(r'D:\UE\Project\HorrorGame\SourceArt\AltarTable')
ROOT = '/Game/Yastars/Mesh/AltarTable'
MESH_NAME = 'SM_AltarTable'
MATERIAL_NAME = 'M_AltarTable'
SOURCE_SLOTS = {'M_Altar_Wood', 'M_Altar_Endgrain', 'M_Altar_Dark'}
REIMPORT_EXISTING_MESH = False
report = {'success': False, 'assets': {}, 'textures': {}, 'materials': {},
          'created_assets': [], 'preserved_assets': [], 'reimported_assets': [], 'warnings': []}

try:
    model_report = json.loads((OUT / 'model_report.json').read_text(encoding='utf-8-sig'))
    part_report = model_report['parts'][MESH_NAME]
    expected_hulls = part_report['collision_hulls']
    expected_hulls = expected_hulls if isinstance(expected_hulls, int) else len(expected_hulls)
    assert expected_hulls > 0, expected_hulls
    edit = unreal.EditorAssetLibrary
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    ml = unreal.MaterialEditingLibrary
    sm_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    edit.make_directory(ROOT + '/Textures')
    edit.make_directory(ROOT + '/Materials')
    assets_to_save, textures = [], {}

    for channel in ('BaseColor', 'Roughness', 'Normal'):
        name = 'T_AltarTable_' + channel
        source = OUT / 'Textures' / (name + '.png')
        assert source.is_file(), str(source)
        texture = edit.load_asset(ROOT + '/Textures/' + name)
        created = not bool(texture)
        if texture:
            report['preserved_assets'].append(texture.get_path_name())
        else:
            task = unreal.AssetImportTask()
            for key, value in {'filename': str(source), 'destination_path': ROOT + '/Textures',
                               'destination_name': name, 'automated': True,
                               'replace_existing': False, 'save': False,
                               'factory': unreal.TextureFactory()}.items():
                task.set_editor_property(key, value)
            asset_tools.import_asset_tasks([task])
            texture = edit.load_asset(ROOT + '/Textures/' + name)
            assert texture, name
            texture.set_editor_property('srgb', channel == 'BaseColor')
            texture.set_editor_property('compression_settings', {
                'BaseColor': unreal.TextureCompressionSettings.TC_DEFAULT,
                'Roughness': unreal.TextureCompressionSettings.TC_MASKS,
                'Normal': unreal.TextureCompressionSettings.TC_NORMALMAP,
            }[channel])
            if channel == 'Normal':
                texture.set_editor_property('flip_green_channel', True)
            assets_to_save.append(texture)
            report['created_assets'].append(texture.get_path_name())
        textures[channel] = texture
        info = {'asset': texture.get_path_name(), 'source': str(source), 'created': created,
                'srgb': texture.get_editor_property('srgb'),
                'compression_settings': str(texture.get_editor_property('compression_settings'))}
        if channel == 'Normal':
            info['flip_green_channel'] = texture.get_editor_property('flip_green_channel')
        report['textures'][name] = info

    material = edit.load_asset(ROOT + '/Materials/' + MATERIAL_NAME)
    material_created = not bool(material)
    if material:
        report['preserved_assets'].append(material.get_path_name())
    else:
        material = asset_tools.create_asset(MATERIAL_NAME, ROOT + '/Materials',
                                            unreal.Material, unreal.MaterialFactoryNew())
        assert material, MATERIAL_NAME
        samples = {}
        for channel, y in (('BaseColor', -180), ('Roughness', 100), ('Normal', 370)):
            node = ml.create_material_expression(material, unreal.MaterialExpressionTextureSample, -750, y)
            node.set_editor_property('texture', textures[channel])
            node.set_editor_property('sampler_type', {
                'BaseColor': unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                'Roughness': unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                'Normal': unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
            }[channel])
            samples[channel] = node
        tint = ml.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -750, -420)
        tint.set_editor_property('parameter_name', 'Tint')
        tint.set_editor_property('default_value', unreal.LinearColor(1., 1., 1., 1.))
        tint.set_editor_property('group', 'Appearance')
        multiply = ml.create_material_expression(material, unreal.MaterialExpressionMultiply, -390, -150)
        assert ml.connect_material_expressions(samples['BaseColor'], 'RGB', multiply, 'A')
        assert ml.connect_material_expressions(tint, 'RGB', multiply, 'B')
        assert ml.connect_material_property(multiply, '', unreal.MaterialProperty.MP_BASE_COLOR)
        assert ml.connect_material_property(samples['Roughness'], 'R', unreal.MaterialProperty.MP_ROUGHNESS)
        assert ml.connect_material_property(samples['Normal'], 'RGB', unreal.MaterialProperty.MP_NORMAL)
        ml.recompile_material(material)
        assets_to_save.append(material)
        report['created_assets'].append(material.get_path_name())
    parameter_names = [str(name) for name in ml.get_vector_parameter_names(material)]
    material_info = {'asset': material.get_path_name(), 'created': material_created,
                     'textures': {key: value.get_path_name() for key, value in textures.items()},
                     'vector_parameter_names': parameter_names}
    if 'Tint' in parameter_names:
        color = ml.get_material_default_vector_parameter_value(material, 'Tint')
        material_info['Tint'] = [color.r, color.g, color.b, color.a]
    if material_created:
        assert material_info.get('Tint') == [1., 1., 1., 1.], material_info
    report['materials'][MATERIAL_NAME] = material_info

    mesh = edit.load_asset(ROOT + '/' + MESH_NAME)
    existed = bool(mesh)
    should_import = not existed or REIMPORT_EXISTING_MESH
    if should_import:
        source_fbx = OUT / (MESH_NAME + '.fbx')
        assert source_fbx.is_file(), str(source_fbx)
        options = unreal.FbxImportUI()
        for key, value in {'import_mesh': True, 'import_as_skeletal': False,
                           'import_materials': False, 'import_textures': False,
                           'automated_import_should_detect_type': False,
                           'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH}.items():
            options.set_editor_property(key, value)
        for key, value in {'import_uniform_scale': 100., 'combine_meshes': True,
                           'auto_generate_collision': False, 'one_convex_hull_per_ucx': True,
                           'generate_lightmap_u_vs': True,
                           'normal_import_method': unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
                           'transform_vertex_to_absolute': True, 'bake_pivot_in_vertex': False}.items():
            options.static_mesh_import_data.set_editor_property(key, value)
        task = unreal.AssetImportTask()
        for key, value in {'filename': str(source_fbx), 'destination_path': ROOT,
                           'destination_name': MESH_NAME, 'automated': True,
                           'replace_existing': existed, 'save': False, 'options': options}.items():
            task.set_editor_property(key, value)
        asset_tools.import_asset_tasks([task])
        mesh = edit.load_asset(ROOT + '/' + MESH_NAME)
        assert mesh, MESH_NAME
        for index, slot in enumerate(mesh.static_materials):
            assert str(slot.material_slot_name) in SOURCE_SLOTS, str(slot.material_slot_name)
            mesh.set_material(index, material)
        mesh.set_editor_property('light_map_resolution', 256)
        settings = sm_editor.get_lod_build_settings(mesh, 0)
        settings.set_editor_property('generate_lightmap_u_vs', True)
        settings.set_editor_property('src_lightmap_index', 0)
        settings.set_editor_property('dst_lightmap_index', 1)
        sm_editor.set_lod_build_settings(mesh, 0, settings)
        mesh.set_editor_property('light_map_coordinate_index', 1)
        assets_to_save.append(mesh)
        report['reimported_assets' if existed else 'created_assets'].append(mesh.get_path_name())
    else:
        report['preserved_assets'].append(mesh.get_path_name())

    bounds = mesh.get_bounds()
    extent, origin = bounds.box_extent, bounds.origin
    dimensions = [extent.x * 2., extent.y * 2., extent.z * 2.]
    hulls = sm_editor.get_convex_collision_count(mesh)
    uv_count = sm_editor.get_num_uv_channels(mesh, 0)
    settings = sm_editor.get_lod_build_settings(mesh, 0)
    slots = [{'index': i, 'slot_name': str(slot.material_slot_name),
              'material': slot.material_interface.get_path_name() if slot.material_interface else None}
             for i, slot in enumerate(mesh.static_materials)]
    report['assets'][MESH_NAME] = {
        'asset': mesh.get_path_name(), 'dimensions_cm': dimensions,
        'bounds_origin_cm': [origin.x, origin.y, origin.z],
        'expected_collision_hulls': expected_hulls, 'convex_collision_hulls': hulls,
        'source_uv_channels_expected': part_report.get('uv_channels', 1),
        'uv_channels_lod0': uv_count, 'texture_atlas_uv0_present': uv_count >= 1,
        'lightmap_coordinate_index': mesh.get_editor_property('light_map_coordinate_index'),
        'lightmap_resolution': mesh.get_editor_property('light_map_resolution'),
        'lightmap_build_settings': {
            'generate_lightmap_u_vs': settings.get_editor_property('generate_lightmap_u_vs'),
            'src_lightmap_index': settings.get_editor_property('src_lightmap_index'),
            'dst_lightmap_index': settings.get_editor_property('dst_lightmap_index'),
            'generated_render_data_uv1_separately_verified': False,
        }, 'matSlots': slots,
    }
    if should_import:
        assert hulls == expected_hulls, (hulls, expected_hulls)
        assert uv_count >= 1, uv_count
        assert slots and all(slot['material'] == material.get_path_name() for slot in slots), slots
        assert 218. <= dimensions[0] <= 223. and 59. <= dimensions[1] <= 65. and 94. <= dimensions[2] <= 99., dimensions
    elif hulls != expected_hulls or uv_count < 1:
        report['warnings'].append('Existing geometry/UVs preserved; differs from source report.')
    for asset in assets_to_save:
        assert edit.save_loaded_asset(asset, False), asset.get_path_name()
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()

(OUT / 'ue_import_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('ALTAR_TABLE_IMPORT ' + json.dumps(report))
