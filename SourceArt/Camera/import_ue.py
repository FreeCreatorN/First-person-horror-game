"""Import the new camera set into its own allowlisted content folder.

Run in a full editor, exclusively. Existing target packages block the entire
operation before any write. This script never deletes, renames, opens or saves
user maps, and never places actors in a level.
"""
import hashlib
import json
import os
import struct
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import unreal

PROJECT = Path(r'D:\UE\Project\HorrorGame')
CONTENT = (PROJECT / 'Content').resolve()
OUT = (PROJECT / 'SourceArt' / 'Camera').resolve()
ROOT = '/Game/Yastars/Mesh/Camera'
CONTENT_ROOT = (CONTENT / 'Yastars' / 'Mesh' / 'Camera').resolve()
MESH_NAMES = {'SM_Camera'}
MATERIAL_NAMES = {'M_Camera_Opaque', 'M_Camera_Glass'}
TEXTURE_PREFIXES = {'Opaque': 'T_Camera'}
CHANNELS = ('BaseColor', 'Roughness', 'Normal', 'Metallic')
EXPECTED_PACKAGES = ({ROOT + '/' + name for name in MESH_NAMES}
                     | {ROOT + '/Materials/' + name for name in MATERIAL_NAMES}
                     | {ROOT + '/Textures/' + prefix + '_' + channel
                        for prefix in TEXTURE_PREFIXES.values() for channel in CHANNELS})
assert len(EXPECTED_PACKAGES) == 7
report = {'success': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
          'run_id': os.environ.get('CAMERA_IMPORT_RUN_ID') or str(uuid.uuid4()), 'editor_pid': os.getpid(),
          'import_script_sha256': hashlib.sha256((OUT / 'import_ue.py').read_bytes()).hexdigest(),
          'target_root': ROOT, 'assets': {}, 'materials': {}, 'textures': {},
          'created_assets': [], 'existing_target_packages': [],
          'new_packages_on_disk': {}, 'warnings': [],
          'asset_or_map_rename_executed': False, 'asset_delete_executed': False,
          'map_save_executed': False, 'level_load_executed': False, 'actors_spawned': 0,
          'source_files_sha256': {}, 'emissive_material_connections_created': 0}
fbx_backend_before = None
fbx_backend_world = None
FBX_BACKEND_CVAR = 'Interchange.FeatureFlags.Import.FBX'


def checkpoint():
    (OUT / 'ue_import_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def package_file(package):
    assert package in EXPECTED_PACKAGES, package
    path = (CONTENT / (package[6:] + '.uasset')).resolve()
    assert path.is_relative_to(CONTENT_ROOT), str(path)
    return path


def source_file(filename):
    path = (OUT / filename).resolve()
    assert path.is_relative_to(OUT) and path.is_file(), str(path)
    return path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def imported_packages(task):
    return {str(value).split('.')[0] for value in task.get_editor_property('imported_object_paths')}


def scalar_parameter(material, name, value, x, y, minimum=0., maximum=1.):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', float(value))
    node.set_editor_property('group', 'Appearance')
    node.set_editor_property('slider_min', float(minimum))
    node.set_editor_property('slider_max', float(maximum))
    return node


def vector_parameter(material, name, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, x, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', unreal.LinearColor(*[float(v) for v in value[:3]], 1.))
    node.set_editor_property('group', 'Appearance')
    return node


def constant(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property('r', float(value))
    return node


def parameter_defaults(material):
    ml = unreal.MaterialEditingLibrary
    vectors = {}
    for name in ml.get_vector_parameter_names(material):
        value = ml.get_material_default_vector_parameter_value(material, name)
        vectors[str(name)] = [value.r, value.g, value.b, value.a]
    scalars = {str(name): ml.get_material_default_scalar_parameter_value(material, name)
               for name in ml.get_scalar_parameter_names(material)}
    return {'vector_parameters': list(vectors), 'vector_defaults': vectors, 'scalar_parameters': scalars}


try:
    assert Path(unreal.Paths.project_dir()).resolve() == PROJECT.resolve(), 'Wrong UE project'
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    sm_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    assert editor and sm_editor, 'Use the full UE editor, not a Python commandlet'
    world_before = editor.get_editor_world()
    report['world_before'] = world_before.get_path_name() if world_before else None
    edit = unreal.EditorAssetLibrary
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    ml = unreal.MaterialEditingLibrary
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    registry.wait_for_completion()
    assert not registry.is_loading_assets(), 'Asset discovery did not finish'
    report['existing_target_packages'] = sorted(package for package in EXPECTED_PACKAGES
                                               if package_file(package).exists() or edit.does_asset_exist(package))
    checkpoint()
    assert not report['existing_target_packages'], (
        'No assets were changed. Existing target packages must be reviewed before a new import: '
        + ', '.join(report['existing_target_packages']))
    model = json.loads((OUT / 'model_report.json').read_text(encoding='utf-8-sig'))
    validated_source = json.loads((OUT / 'validation_report.json').read_text(encoding='utf-8-sig'))
    assert validated_source['success'], 'Source geometry and FBX must pass before importing'
    assert model['exported_lights'] == model['exported_cameras'] == 0
    parts, material_specs, texture_sets = model['parts'], model['materials'], model['texture_sets']
    assert set(parts) == MESH_NAMES, list(parts)
    assert set(material_specs) == MATERIAL_NAMES, list(material_specs)
    assert set(texture_sets) == set(TEXTURE_PREFIXES), list(texture_sets)
    for key, spec in texture_sets.items():
        assert spec['prefix'] == TEXTURE_PREFIXES[key], (key, spec)
        for channel in CHANNELS:
            assert Path(spec[channel]).name == spec['prefix'] + '_' + channel + '.png', spec[channel]
            path = source_file(spec[channel])
            with path.open('rb') as image:
                header = image.read(24)
            assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR', str(path)
            assert struct.unpack('>II', header[16:24]) == (2048, 2048), str(path)
            bake = validated_source['bakes'][spec['prefix'] + '_' + channel]
            assert Path(bake['path']).resolve() == path and bake['reloaded_from_saved_png']
            assert bake['sha256'] == sha256(path), 'Texture changed after Blender validation: ' + str(path)
    expected_shaders = {'M_Camera_Opaque': 'opaque_atlas', 'M_Camera_Glass': 'glass'}
    for name, spec in material_specs.items():
        assert spec['shader_type'] == expected_shaders[name], (name, spec)
        if spec['shader_type'] == 'opaque_atlas':
            assert spec['texture_set'] == 'Opaque'
        else:
            for key, expected in {'opacity': .18, 'roughness': .07, 'ior': 1.46}.items():
                assert abs(float(spec[key]) - expected) < 1.e-6, (name, key, spec)
            assert len(spec['tint']) == 3 and all(abs(float(a) - b) < 1.e-6
                                                  for a, b in zip(spec['tint'], [.72, .84, .94])), (name, spec)
    for name, spec in parts.items():
        assert spec['filename'] == name + '.fbx', spec['filename']
        source_file(spec['filename'])
        assert isinstance(spec['collision_hulls'], int) and spec['collision_hulls'] >= 1, (name, spec)
        assert len(spec['dimensions_cm']) == 3 and all(float(v) > 0 for v in spec['dimensions_cm']), (name, spec)
        assert int(spec.get('uv_channels', 1)) == 1, (name, spec)
        assert spec['material_slots'].get('M_Camera_OpticalGlass') == 'M_Camera_Glass', 'Optical glass must remain an independent source slot'
        assert spec['material_slots'] and set(spec['material_slots'].values()) == MATERIAL_NAMES, (name, spec)
        assert all(target == ('M_Camera_Glass' if source == 'M_Camera_OpticalGlass' else 'M_Camera_Opaque')
                   for source, target in spec['material_slots'].items()), (name, spec)
        roundtrip = validated_source['fbx_roundtrip'][name]
        assert roundtrip['success'] and roundtrip['sha256'] == sha256(source_file(spec['filename'])), (name, roundtrip)
        assert roundtrip['ucx_count'] == spec['collision_hulls']
    report['source_files_sha256'] = {str(source_file(spec[channel])): sha256(source_file(spec[channel]))
                                    for spec in texture_sets.values() for channel in CHANNELS}
    report['source_files_sha256'].update({str(source_file(spec['filename'])): sha256(source_file(spec['filename']))
                                         for spec in parts.values()})
    report['source_files_sha256'][str(OUT / 'model_report.json')] = sha256(OUT / 'model_report.json')
    report['source_preflight_passed'] = True
    checkpoint()
    # FbxImportUI uses the legacy importer whose axes and tiny-detail settings
    # were validated for this source. Restore the current editor's runtime flag
    # after the operation; setting this cvar never writes a config file.
    fbx_backend_world = world_before
    fbx_backend_before = unreal.SystemLibrary.get_console_variable_int_value(FBX_BACKEND_CVAR)
    report['fbx_backend_flag_before'] = fbx_backend_before
    unreal.SystemLibrary.execute_console_command(fbx_backend_world, FBX_BACKEND_CVAR + ' 0')
    report['fbx_backend_flag_during_import'] = unreal.SystemLibrary.get_console_variable_int_value(FBX_BACKEND_CVAR)
    assert report['fbx_backend_flag_during_import'] == 0
    edit.make_directory(ROOT + '/Textures')
    edit.make_directory(ROOT + '/Materials')
    textures, materials, to_save = {}, {}, []

    for set_name, spec in texture_sets.items():
        textures[set_name] = {}
        for channel in CHANNELS:
            name = spec['prefix'] + '_' + channel
            package = ROOT + '/Textures/' + name
            assert package in EXPECTED_PACKAGES and not edit.does_asset_exist(package), package
            task = unreal.AssetImportTask()
            for key, value in {'filename': str(source_file(spec[channel])), 'destination_path': ROOT + '/Textures',
                               'destination_name': name, 'automated': True, 'replace_existing': False,
                               'save': False, 'factory': unreal.TextureFactory()}.items():
                task.set_editor_property(key, value)
            asset_tools.import_asset_tasks([task])
            assert imported_packages(task) == {package}, (package, imported_packages(task))
            texture = edit.load_asset(package)
            assert texture and isinstance(texture, unreal.Texture2D), package
            texture.set_editor_property('srgb', channel == 'BaseColor')
            texture.set_editor_property('compression_settings', {
                'BaseColor': unreal.TextureCompressionSettings.TC_DEFAULT,
                'Roughness': unreal.TextureCompressionSettings.TC_MASKS,
                'Normal': unreal.TextureCompressionSettings.TC_NORMALMAP,
                'Metallic': unreal.TextureCompressionSettings.TC_MASKS,
            }[channel])
            if channel == 'Normal':
                texture.set_editor_property('flip_green_channel', True)
            to_save.append(texture)
            report['created_assets'].append(texture.get_path_name())
            textures[set_name][channel] = texture
            info = {'asset': texture.get_path_name(), 'source': str(source_file(spec[channel])),
                    'srgb': texture.get_editor_property('srgb'),
                    'compression_settings': str(texture.get_editor_property('compression_settings'))}
            assert info['srgb'] == (channel == 'BaseColor'), info
            if channel == 'Normal':
                info['flip_green_channel'] = texture.get_editor_property('flip_green_channel')
                assert info['flip_green_channel'], info
            report['textures'][name] = info
            checkpoint()

    for name, spec in material_specs.items():
        package = ROOT + '/Materials/' + name
        assert package in EXPECTED_PACKAGES and not edit.does_asset_exist(package), package
        material = asset_tools.create_asset(name, ROOT + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
        assert material and isinstance(material, unreal.Material), package
        shader_type = spec['shader_type']
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        info = {'asset': material.get_path_name(), 'shader_type': shader_type, 'emissive_connected': False}
        if shader_type == 'opaque_atlas':
            image_set, samples = textures[spec['texture_set']], {}
            for channel, y in (('BaseColor', -180), ('Roughness', 100), ('Normal', 370), ('Metallic', 640)):
                node = ml.create_material_expression(material, unreal.MaterialExpressionTextureSample, -750, y)
                node.set_editor_property('texture', image_set[channel])
                node.set_editor_property('sampler_type', {
                    'BaseColor': unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
                    'Roughness': unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                    'Normal': unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
                    'Metallic': unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
                }[channel])
                samples[channel] = node
            tint = vector_parameter(material, 'Tint', [1., 1., 1.], -750, -420)
            multiply = ml.create_material_expression(material, unreal.MaterialExpressionMultiply, -390, -150)
            assert ml.connect_material_expressions(samples['BaseColor'], 'RGB', multiply, 'A')
            assert ml.connect_material_expressions(tint, 'RGB', multiply, 'B')
            assert ml.connect_material_property(multiply, '', unreal.MaterialProperty.MP_BASE_COLOR)
            assert ml.connect_material_property(samples['Roughness'], 'R', unreal.MaterialProperty.MP_ROUGHNESS)
            assert ml.connect_material_property(samples['Normal'], 'RGB', unreal.MaterialProperty.MP_NORMAL)
            assert ml.connect_material_property(samples['Metallic'], 'R', unreal.MaterialProperty.MP_METALLIC)
            info.update({'texture_set': spec['texture_set'],
                         'textures': {key: value.get_path_name() for key, value in image_set.items()},
                         'connections': {'BaseColor': 'BaseColor.RGB * Tint.RGB', 'Roughness': 'Roughness.R',
                                         'Normal': 'Normal.RGB', 'Metallic': 'Metallic.R'}})
        elif shader_type == 'glass':
            # Verified against UE 5.7's public Python API and EngineTypes.h.
            material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
            material.set_editor_property('translucency_lighting_mode', unreal.TranslucencyLightingMode.TLM_SURFACE)
            material.set_editor_property('refraction_method', unreal.RefractionMode.RM_INDEX_OF_REFRACTION)
            material.set_editor_property('two_sided', False)
            tint = vector_parameter(material, 'GlassTint', spec.get('tint', [.72, .84, .94]), -550, -300)
            opacity = scalar_parameter(material, 'Opacity', spec.get('opacity', .18), -550, -50)
            rough = scalar_parameter(material, 'GlassRoughness', spec.get('roughness', .07), -550, 130)
            ior = scalar_parameter(material, 'IOR', spec.get('ior', 1.46), -550, 310, 1., 2.)
            metallic = constant(material, 0., -550, 490)
            assert ml.connect_material_property(tint, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
            assert ml.connect_material_property(opacity, '', unreal.MaterialProperty.MP_OPACITY)
            assert ml.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
            assert ml.connect_material_property(ior, '', unreal.MaterialProperty.MP_REFRACTION)
            assert ml.connect_material_property(metallic, '', unreal.MaterialProperty.MP_METALLIC)
            info.update({'translucency_lighting_mode': str(material.get_editor_property('translucency_lighting_mode')),
                         'refraction_method': str(material.get_editor_property('refraction_method')),
                         'refraction_connected': True, 'two_sided': material.get_editor_property('two_sided'),
                         'metallic': 0., 'connections': {'BaseColor': 'GlassTint.RGB', 'Opacity': 'Opacity',
                                                       'Roughness': 'GlassRoughness', 'Refraction': 'IOR', 'Metallic': '0'}})
        else:
            raise AssertionError('Unexpected shader_type ' + shader_type)
        ml.recompile_material(material)
        to_save.append(material)
        report['created_assets'].append(material.get_path_name())
        materials[name] = material
        info['blend_mode'] = str(material.get_editor_property('blend_mode'))
        info['shading_model'] = str(material.get_editor_property('shading_model'))
        info.update(parameter_defaults(material))
        if shader_type == 'opaque_atlas':
            assert info['vector_defaults']['Tint'] == [1., 1., 1., 1.]
        elif shader_type == 'glass':
            assert abs(info['scalar_parameters']['Opacity'] - float(spec.get('opacity', .18))) < 1.e-6
            assert abs(info['scalar_parameters']['GlassRoughness'] - float(spec.get('roughness', .07))) < 1.e-6
            assert abs(info['scalar_parameters']['IOR'] - float(spec.get('ior', 1.46))) < 1.e-6
            assert 'TLM_SURFACE' in info['translucency_lighting_mode']
        report['materials'][name] = info
        checkpoint()
    for name, spec in parts.items():
        package = ROOT + '/' + name
        assert package in EXPECTED_PACKAGES and not edit.does_asset_exist(package), package
        options = unreal.FbxImportUI()
        for key, value in {'import_mesh': True, 'import_as_skeletal': False,
                           'import_materials': False, 'import_textures': False,
                           'automated_import_should_detect_type': False,
                           'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH}.items():
            options.set_editor_property(key, value)
        for key, value in {'import_uniform_scale': 100., 'combine_meshes': True,
                           'auto_generate_collision': False, 'one_convex_hull_per_ucx': True,
                           'generate_lightmap_u_vs': True, 'remove_degenerates': False,
                           'normal_import_method': unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
                           'transform_vertex_to_absolute': True, 'bake_pivot_in_vertex': False}.items():
            options.static_mesh_import_data.set_editor_property(key, value)
        task = unreal.AssetImportTask()
        for key, value in {'filename': str(source_file(spec['filename'])), 'destination_path': ROOT,
                           'destination_name': name, 'automated': True, 'replace_existing': False,
                           'save': False, 'options': options}.items():
            task.set_editor_property(key, value)
        asset_tools.import_asset_tasks([task])
        assert imported_packages(task) == {package}, (package, imported_packages(task))
        mesh = edit.load_asset(package)
        assert mesh and isinstance(mesh, unreal.StaticMesh), package
        for index, slot in enumerate(mesh.static_materials):
            slot_name = str(slot.material_slot_name)
            assert slot_name in spec['material_slots'], (name, slot_name)
            mesh.set_material(index, materials[spec['material_slots'][slot_name]])
        mesh.set_editor_property('light_map_resolution', 128)
        settings = sm_editor.get_lod_build_settings(mesh, 0)
        settings.set_editor_property('generate_lightmap_u_vs', True)
        settings.set_editor_property('remove_degenerates', False)
        settings.set_editor_property('src_lightmap_index', 0)
        settings.set_editor_property('dst_lightmap_index', 1)
        sm_editor.set_lod_build_settings(mesh, 0, settings)
        settings = sm_editor.get_lod_build_settings(mesh, 0)
        mesh.set_editor_property('light_map_coordinate_index', 1)
        to_save.append(mesh)
        report['created_assets'].append(mesh.get_path_name())
        bounds = mesh.get_bounds()
        extent, origin = bounds.box_extent, bounds.origin
        dimensions = [extent.x * 2., extent.y * 2., extent.z * 2.]
        differences = [abs(actual - float(expected)) for actual, expected in zip(dimensions, spec['dimensions_cm'])]
        bounds_min = [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z]
        bounds_max = [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]
        source_geometry = validated_source['geometry'][name]
        # This project's legacy FBX axis configuration keeps X/Z and reverses Y.
        source_min, source_max = source_geometry['bounds_min_m'], source_geometry['bounds_max_m']
        expected_min = [source_min[0] * 100., -source_max[1] * 100., source_min[2] * 100.]
        expected_max = [source_max[0] * 100., -source_min[1] * 100., source_max[2] * 100.]
        bounds_errors = [abs(actual - expected) for actual, expected in zip(bounds_min + bounds_max, expected_min + expected_max)]
        render_triangles = mesh.get_num_triangles(0)
        actual_import_data = mesh.get_editor_property('asset_import_data')
        hulls = sm_editor.get_convex_collision_count(mesh)
        uv_count = sm_editor.get_num_uv_channels(mesh, 0)
        slots = [{'index': index, 'slot_name': str(slot.material_slot_name),
                  'material': slot.material_interface.get_path_name() if slot.material_interface else None}
                 for index, slot in enumerate(mesh.static_materials)]
        info = {'asset': mesh.get_path_name(), 'dimensions_cm': dimensions,
                'expected_dimensions_cm': spec['dimensions_cm'], 'dimension_error_cm': differences,
                'dimension_tolerance_cm': .001, 'bounds_origin_cm': [origin.x, origin.y, origin.z],
                'bounds_min_cm': bounds_min, 'bounds_max_cm': bounds_max,
                'expected_bounds_min_cm': expected_min, 'expected_bounds_max_cm': expected_max,
                'bounds_error_cm': bounds_errors, 'bounds_tolerance_cm': .001,
                'render_triangles_lod0': render_triangles, 'expected_triangles': spec['triangles'],
                'fbx_import_remove_degenerates': actual_import_data.get_editor_property('remove_degenerates'),
                'convex_collision_hulls': hulls, 'expected_collision_hulls': spec['collision_hulls'],
                'uv_channels_lod0': uv_count, 'source_uv_channels_expected': spec.get('uv_channels', 1),
                'source_triangles': spec.get('triangles'), 'matSlots': slots,
                'lightmap_coordinate_index': mesh.get_editor_property('light_map_coordinate_index'),
                'lightmap_build_settings': {
                    'generate_lightmap_u_vs': settings.get_editor_property('generate_lightmap_u_vs'),
                    'remove_degenerates': settings.get_editor_property('remove_degenerates'),
                    'src_lightmap_index': settings.get_editor_property('src_lightmap_index'),
                    'dst_lightmap_index': settings.get_editor_property('dst_lightmap_index'),
                    'generated_render_data_uv1_separately_verified': False}}
        report['assets'][name] = info
        checkpoint()
        assert max(differences) <= .001, (name, info)
        assert max(bounds_errors) <= .001, (name, info)
        assert render_triangles == spec['triangles'] == source_geometry['triangles'], (name, info)
        assert info['fbx_import_remove_degenerates'] is False, (name, info)
        assert info['lightmap_build_settings']['remove_degenerates'] is False, (name, info)
        assert hulls == spec['collision_hulls'] and hulls >= 1, (name, info)
        assert uv_count >= int(spec.get('uv_channels', 1)), (name, info)
        assert slots and all(slot['material'] for slot in slots), (name, info)
        assert set(slot['slot_name'] for slot in slots) == set(spec['material_slots']), (name, info)
        assert 'M_Camera_OpticalGlass' in {slot['slot_name'] for slot in slots}, (name, info)
        assert all(slot['material'] == materials[spec['material_slots'][slot['slot_name']]].get_path_name()
                   for slot in slots), (name, info)

    assert len(to_save) == len(report['created_assets']) == 7
    assert {path.split('.')[0] for path in report['created_assets']} == EXPECTED_PACKAGES
    for asset in to_save:
        assert edit.save_loaded_asset(asset, False), asset.get_path_name()
    for package in sorted(EXPECTED_PACKAGES):
        path = package_file(package)
        assert path.is_file() and path.stat().st_size > 0 and edit.does_asset_exist(package), package
        report['new_packages_on_disk'][package] = {'file': str(path), 'bytes': path.stat().st_size,
                                                  'sha256': sha256(path)}
    report['new_package_count'] = len(report['new_packages_on_disk'])
    assert report['new_package_count'] == 7
    report['source_files_unchanged'] = all(sha256(Path(path)) == digest for path, digest in report['source_files_sha256'].items())
    assert report['source_files_unchanged'], 'A source changed during import'
    world_after = editor.get_editor_world()
    report['world_after'] = world_after.get_path_name() if world_after else None
    report['same_world_object'] = world_before == world_after
    assert report['same_world_object'] and report['world_before'] == report['world_after']
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()
finally:
    if fbx_backend_before is not None:
        try:
            unreal.SystemLibrary.execute_console_command(fbx_backend_world, FBX_BACKEND_CVAR + ' ' + str(fbx_backend_before))
            report['fbx_backend_flag_after'] = unreal.SystemLibrary.get_console_variable_int_value(FBX_BACKEND_CVAR)
            report['fbx_backend_flag_restored'] = report['fbx_backend_flag_after'] == fbx_backend_before
            assert report['fbx_backend_flag_restored'], 'Could not restore the runtime FBX importer flag'
        except Exception:
            report['success'] = False
            report['fbx_backend_restore_error'] = traceback.format_exc()

report['completed_utc'] = datetime.now(timezone.utc).isoformat()
checkpoint()
unreal.log('CAMERA_IMPORT ' + json.dumps(report))
