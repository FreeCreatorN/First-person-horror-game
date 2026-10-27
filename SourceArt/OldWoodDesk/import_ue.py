"""Import the baked desk Base and Drawer without overwriting user-edited assets.

Requires the full editor, PythonScriptPlugin, EditorScriptingUtilities, and the
legacy FBX importer. Set REIMPORT_EXISTING_MESHES explicitly for a geometry
refresh; existing textures and materials are always preserved.
"""
import json
import traceback
from pathlib import Path

import unreal


OUT = Path(r'D:\UE\Project\HorrorGame\SourceArt\OldWoodDesk')
ROOT = '/Game/Yastars/Mesh/OldWoodDesk'
PARTS = ('Base', 'Drawer')
SOURCE_SLOT_NAMES = {'M_OldDesk_Wood', 'M_OldDesk_Endgrain', 'M_OldDesk_Iron'}
REIMPORT_EXISTING_MESHES = False
# Blender's default tangent-space bake uses +Y. Set False for a NEG_Y bake.
NORMAL_MAP_IS_OPENGL = True
report = {
    'success': False,
    'assets': {},
    'textures': {},
    'materials': {},
    'created_assets': [],
    'preserved_assets': [],
    'reimported_assets': [],
    'warnings': [],
    'assembly_offsets': {'Base': [0., 0., 0.], 'Drawer': [0., 0., 0.]},
    'drawer_open_offset_cm': [0., 23., 0.],
    'drawer_forward_axis': '+Y',
}


def expected_collision_hulls(model_report, mesh_name, part):
    """Read the modeler's reported UCX count rather than assume geometry count."""
    candidates = []
    for container_name in ('parts', 'assets', 'meshes', 'exported_meshes'):
        container = model_report.get(container_name, {})
        if isinstance(container, dict):
            candidates.extend(container.get(key) for key in (mesh_name, part, part.lower()))
        elif isinstance(container, list):
            candidates.extend(x for x in container if isinstance(x, dict) and
                              x.get('name', x.get('mesh_name')) in (mesh_name, part))
    candidates.extend(model_report.get(key) for key in (mesh_name, part, part.lower()))
    for item in candidates:
        if not isinstance(item, dict):
            continue
        for key in ('collision_hulls', 'convex_collision_hulls', 'ucx_count'):
            value = item.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, list):
                return len(value)
    for key in ('collision_hulls', 'convex_collision_hulls', 'ucx_counts'):
        mapping = model_report.get(key, {})
        if isinstance(mapping, dict):
            for mesh_key in (mesh_name, part, part.lower()):
                value = mapping.get(mesh_key)
                if isinstance(value, int):
                    return value
                if isinstance(value, list):
                    return len(value)
    raise AssertionError('No collision_hulls reported for ' + mesh_name)


def texture_source(name):
    for directory in (OUT / 'Textures', OUT / 'textures', OUT):
        source = directory / (name + '.png')
        if source.is_file():
            return source
    raise AssertionError('Missing baked texture ' + name + '.png')


try:
    model_path = OUT / 'model_report.json'
    model_report = json.loads(model_path.read_text(encoding='utf-8-sig'))
    edit = unreal.EditorAssetLibrary
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    ml = unreal.MaterialEditingLibrary
    sm_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    edit.make_directory(ROOT + '/Textures')
    edit.make_directory(ROOT + '/Materials')
    assets_to_save = []

    for part in PARTS:
        mesh_name = 'SM_OldWoodDesk_' + part
        hulls_expected = expected_collision_hulls(model_report, mesh_name, part)
        assert hulls_expected > 0, (mesh_name, hulls_expected)
        textures = {}
        for channel in ('BaseColor', 'Roughness', 'Normal'):
            texture_name = 'T_OldDesk_' + part + '_' + channel
            source = texture_source(texture_name)
            texture = edit.load_asset(ROOT + '/Textures/' + texture_name)
            created = not bool(texture)
            if texture:
                report['preserved_assets'].append(texture.get_path_name())
            else:
                task = unreal.AssetImportTask()
                task.set_editor_property('filename', str(source))
                task.set_editor_property('destination_path', ROOT + '/Textures')
                task.set_editor_property('destination_name', texture_name)
                task.set_editor_property('automated', True)
                task.set_editor_property('replace_existing', False)
                task.set_editor_property('save', False)
                task.set_editor_property('factory', unreal.TextureFactory())
                asset_tools.import_asset_tasks([task])
                texture = edit.load_asset(ROOT + '/Textures/' + texture_name)
                assert texture, texture_name
                texture.set_editor_property('srgb', channel == 'BaseColor')
                compression = {
                    'BaseColor': unreal.TextureCompressionSettings.TC_DEFAULT,
                    'Roughness': unreal.TextureCompressionSettings.TC_MASKS,
                    'Normal': unreal.TextureCompressionSettings.TC_NORMALMAP,
                }[channel]
                texture.set_editor_property('compression_settings', compression)
                if channel == 'Normal':
                    texture.set_editor_property('flip_green_channel', NORMAL_MAP_IS_OPENGL)
                assets_to_save.append(texture)
                report['created_assets'].append(texture.get_path_name())
            textures[channel] = texture
            texture_info = {
                'asset': texture.get_path_name(),
                'source': str(source),
                'created': created,
                'srgb': texture.get_editor_property('srgb'),
                'compression_settings': str(texture.get_editor_property('compression_settings')),
            }
            if channel == 'Normal':
                texture_info['flip_green_channel'] = texture.get_editor_property('flip_green_channel')
            report['textures'][texture_name] = texture_info

        material_name = 'M_OldDesk_' + part
        material = edit.load_asset(ROOT + '/Materials/' + material_name)
        material_created = not bool(material)
        if material:
            report['preserved_assets'].append(material.get_path_name())
        else:
            material = asset_tools.create_asset(
                material_name, ROOT + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
            assert material, material_name
            samples = {}
            for channel, y in (('BaseColor', -180), ('Roughness', 100), ('Normal', 370)):
                node = ml.create_material_expression(
                    material, unreal.MaterialExpressionTextureSample, -750, y)
                node.set_editor_property('texture', textures[channel])
                node.set_editor_property('sampler_type', {
                    'BaseColor': unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                    'Roughness': unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                    'Normal': unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
                }[channel])
                samples[channel] = node
            tint = ml.create_material_expression(
                material, unreal.MaterialExpressionVectorParameter, -750, -420)
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
        vector_names = [str(x) for x in ml.get_vector_parameter_names(material)]
        material_info = {
            'asset': material.get_path_name(),
            'created': material_created,
            'textures': {key: value.get_path_name() for key, value in textures.items()},
            'vector_parameter_names': vector_names,
        }
        if 'Tint' in vector_names:
            tint_value = ml.get_material_default_vector_parameter_value(material, 'Tint')
            material_info['Tint'] = [tint_value.r, tint_value.g, tint_value.b, tint_value.a]
        if material_created:
            assert 'Tint' in vector_names, material_info
        report['materials'][material_name] = material_info

        mesh = edit.load_asset(ROOT + '/' + mesh_name)
        existed = bool(mesh)
        should_import = not existed or REIMPORT_EXISTING_MESHES
        if should_import:
            source_fbx = OUT / (mesh_name + '.fbx')
            assert source_fbx.is_file(), str(source_fbx)
            options = unreal.FbxImportUI()
            for key, value in {
                'import_mesh': True,
                'import_as_skeletal': False,
                'import_materials': False,
                'import_textures': False,
                'automated_import_should_detect_type': False,
                'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH,
            }.items():
                options.set_editor_property(key, value)
            for key, value in {
                'import_uniform_scale': 100.,
                'combine_meshes': True,
                'auto_generate_collision': False,
                'one_convex_hull_per_ucx': True,
                'generate_lightmap_u_vs': True,
                'normal_import_method': unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
                'transform_vertex_to_absolute': True,
                'bake_pivot_in_vertex': False,
            }.items():
                options.static_mesh_import_data.set_editor_property(key, value)
            task = unreal.AssetImportTask()
            for key, value in {
                'filename': str(source_fbx), 'destination_path': ROOT,
                'destination_name': mesh_name, 'automated': True,
                'replace_existing': bool(existed), 'save': False, 'options': options,
            }.items():
                task.set_editor_property(key, value)
            asset_tools.import_asset_tasks([task])
            mesh = edit.load_asset(ROOT + '/' + mesh_name)
            assert mesh, mesh_name
            for index, slot in enumerate(mesh.static_materials):
                slot_name = str(slot.material_slot_name)
                assert slot_name in SOURCE_SLOT_NAMES, (mesh_name, slot_name)
                # The atlas contains all original wood/endgrain/iron appearances.
                mesh.set_material(index, material)
            mesh.set_editor_property('light_map_resolution', 256)
            # The atlas is UV0. Ask the mesh builder to generate lighting UV1
            # separately; MeshDescription's channel count may still report UV0
            # only even when generated UVs are present in built render data.
            if hasattr(sm_editor, 'get_lod_build_settings') and hasattr(sm_editor, 'set_lod_build_settings'):
                build_settings = sm_editor.get_lod_build_settings(mesh, 0)
                build_settings.set_editor_property('generate_lightmap_u_vs', True)
                build_settings.set_editor_property('src_lightmap_index', 0)
                build_settings.set_editor_property('dst_lightmap_index', 1)
                sm_editor.set_lod_build_settings(mesh, 0, build_settings)
                mesh.set_editor_property('light_map_coordinate_index', 1)
            assets_to_save.append(mesh)
            report['reimported_assets' if existed else 'created_assets'].append(mesh.get_path_name())
        else:
            report['preserved_assets'].append(mesh.get_path_name())

        bounds = mesh.get_bounds()
        extent, origin = bounds.box_extent, bounds.origin
        dimensions = [extent.x * 2., extent.y * 2., extent.z * 2.]
        hulls_actual = sm_editor.get_convex_collision_count(mesh)
        uv_count = sm_editor.get_num_uv_channels(mesh, 0)
        lightmap_build = None
        if hasattr(sm_editor, 'get_lod_build_settings'):
            build_settings = sm_editor.get_lod_build_settings(mesh, 0)
            lightmap_build = {
                'generate_lightmap_u_vs': build_settings.get_editor_property('generate_lightmap_u_vs'),
                'src_lightmap_index': build_settings.get_editor_property('src_lightmap_index'),
                'dst_lightmap_index': build_settings.get_editor_property('dst_lightmap_index'),
                'generated_render_data_uv1_separately_verified': False,
            }
        mat_slots = [
            {'index': i, 'slot_name': str(slot.material_slot_name),
             'material': slot.material_interface.get_path_name() if slot.material_interface else None}
            for i, slot in enumerate(mesh.static_materials)
        ]
        report['assets'][mesh_name] = {
            'asset': mesh.get_path_name(),
            'dimensions_cm': dimensions,
            'bounds_origin_cm': [origin.x, origin.y, origin.z],
            'convex_collision_hulls': hulls_actual,
            'expected_collision_hulls': hulls_expected,
            'uv_channels_lod0': uv_count,
            'texture_atlas_uv0_present': uv_count >= 1,
            'lightmap_build_settings': lightmap_build,
            'lightmap_coordinate_index': mesh.get_editor_property('light_map_coordinate_index'),
            'lightmap_resolution': mesh.get_editor_property('light_map_resolution'),
            'matSlots': mat_slots,
            'assembly_offset_cm': [0., 0., 0.],
        }
        if should_import:
            assert hulls_actual == hulls_expected, (mesh_name, hulls_actual, hulls_expected)
            assert uv_count >= 1, (mesh_name, uv_count)
            assert mat_slots and all(x['material'] == material.get_path_name() for x in mat_slots), mat_slots
            if part == 'Base':
                assert 119. < dimensions[0] < 121. and 63. < dimensions[1] < 65. and 76. < dimensions[2] < 78., dimensions
        elif hulls_actual != hulls_expected or uv_count < 1:
            report['warnings'].append(mesh_name + ': existing geometry/UVs preserved; differs from source report.')

    for asset in assets_to_save:
        assert edit.save_loaded_asset(asset, False), asset.get_path_name()
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()

(OUT / 'ue_import_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('OLD_WOOD_DESK_IMPORT ' + json.dumps(report))
