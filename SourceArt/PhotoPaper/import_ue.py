"""Create the six new PhotoPaper assets, without editing any existing asset.

Run only through run_import.ps1 in an exclusive full editor. PhotoTexture is a
TextureSampleParameter2D so a dynamic material can later accept a capture RT.
This import contains no camera, capture, light, actor or gameplay creation.
"""
import hashlib
import json
import os
import re
import struct
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import unreal

PROJECT = Path(r'D:\UE\Project\HorrorGame')
CONTENT = (PROJECT / 'Content').resolve()
OUT = (PROJECT / 'SourceArt' / 'PhotoPaper').resolve()
ROOT = '/Game/Yastars/Mesh/PhotoPaper'
CONTENT_ROOT = (CONTENT / 'Yastars' / 'Mesh' / 'PhotoPaper').resolve()
MESH_NAME = 'SM_PhotoPaper'
SOURCE_SLOTS = ['M_PhotoPaper_Frame', 'M_PhotoPaper_Image', 'M_PhotoPaper_Back']
SLOT_TARGETS = ['M_PhotoPaper_Frame', 'MI_PhotoPaper_Image', 'M_PhotoPaper_Back']
MATERIAL_NAMES = set(SOURCE_SLOTS)
TEXTURE_NAME = 'T_PhotoPaper_Blank'
EXPECTED_PACKAGES = {ROOT + '/' + MESH_NAME,
                     ROOT + '/Textures/' + TEXTURE_NAME,
                     ROOT + '/Materials/MI_PhotoPaper_Image'} | {
                         ROOT + '/Materials/' + name for name in MATERIAL_NAMES}
assert len(EXPECTED_PACKAGES) == 6
FBX_BACKEND_CVAR = 'Interchange.FeatureFlags.Import.FBX'
report = {'success': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
          'run_id': os.environ.get('PHOTOPAPER_IMPORT_RUN_ID') or str(uuid.uuid4()),
          'editor_pid': os.getpid(), 'target_root': ROOT,
          'import_script_sha256': hashlib.sha256((OUT / 'import_ue.py').read_bytes()).hexdigest(),
          'assets': {}, 'materials': {}, 'material_instances': {}, 'textures': {},
          'created_assets': [], 'existing_target_packages': [], 'new_packages_on_disk': {},
          'source_files_sha256': {}, 'map_save_executed': False,
          'level_load_executed': False, 'actors_spawned': 0,
          'asset_delete_executed': False, 'asset_or_map_rename_executed': False,
          'emissive_material_connections_created': 0,
          'imported_cameras': 0, 'imported_lights': 0}
fbx_backend_before = None
fbx_backend_world = None


def checkpoint():
    (OUT / 'ue_import_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def source_file(name):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT) and path.is_file(), str(path)
    return path


def package_file(package):
    assert package in EXPECTED_PACKAGES, package
    path = (CONTENT / (package[6:] + '.uasset')).resolve()
    assert path.is_relative_to(CONTENT_ROOT), str(path)
    return path


def imported_packages(task):
    return {str(value).split('.')[0] for value in task.get_editor_property('imported_object_paths')}


def close(values, expected, tolerance=1.e-6):
    return len(values) == len(expected) and all(abs(float(a) - float(b)) <= tolerance for a, b in zip(values, expected))


def vector_parameter(material, name, values, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, x, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', unreal.LinearColor(*values, 1.))
    node.set_editor_property('group', 'Appearance')
    return node


def scalar_parameter(material, name, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', float(value))
    node.set_editor_property('group', 'Appearance')
    return node


def verify_protected():
    baseline = json.loads(source_file('protected_content_sha256.json').read_text(encoding='utf-8-sig'))
    assert isinstance(baseline, list) and baseline, 'Missing protected-content baseline'
    changed = [item['path'] for item in baseline
               if not Path(item['path']).is_file() or sha(item['path']).lower() != item['sha256'].lower()]
    assert not changed, ('Protected project content changed', changed)
    return len(baseline)


try:
    assert Path(unreal.Paths.project_dir()).resolve() == PROJECT.resolve(), 'Wrong project'
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    sm_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    assert editor and sm_editor, 'A full UE editor is required'
    world_before = editor.get_editor_world()
    report['world_before'] = world_before.get_path_name() if world_before else None
    assert report['world_before'] and report['world_before'].startswith('/Engine/Maps/Entry'), report['world_before']
    edit = unreal.EditorAssetLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    ml = unreal.MaterialEditingLibrary
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    registry.wait_for_completion()
    assert not registry.is_loading_assets(), 'Asset discovery is unfinished'
    registered = {str(item.package_name) for item in registry.get_assets_by_path(ROOT, recursive=True)}
    on_disk = sorted(str(path) for path in CONTENT_ROOT.rglob('*') if path.is_file()) if CONTENT_ROOT.exists() else []
    report['existing_target_packages'] = sorted(registered | {
        package for package in EXPECTED_PACKAGES if package_file(package).exists() or edit.does_asset_exist(package)})
    report['existing_target_files'] = on_disk
    checkpoint()
    assert not registered and not on_disk and not report['existing_target_packages'], 'Target must be completely new; nothing was overwritten'
    report['protected_files_checked_before'] = verify_protected()
    model = json.loads(source_file('model_report.json').read_text(encoding='utf-8-sig'))
    validation = json.loads(source_file('validation_report.json').read_text(encoding='utf-8-sig'))
    assert validation['success'], 'Blender validation must succeed before UE import'
    assert model['exported_cameras'] == model['exported_lights'] == 0
    assert set(model['parts']) == {MESH_NAME} and set(model['materials']) == MATERIAL_NAMES
    spec = model['parts'][MESH_NAME]
    assert spec['filename'] == MESH_NAME + '.fbx'
    assert list(spec['material_slots']) == SOURCE_SLOTS
    assert list(spec['material_slots'].values()) == SLOT_TARGETS
    assert spec['collision_hulls'] == spec['uv_channels'] == 1 and spec['non_manifold_edges'] == 0
    assert int(spec['triangles']) > 0 and len(spec['dimensions_cm']) == 3
    assert all(float(value) > 0 for value in spec['dimensions_cm'])
    photo_uv = model['photo_uv']
    assert photo_uv['slot_index'] == 1 and close(photo_uv['min'], [0., 0.]) and close(photo_uv['max'], [1., 1.])
    checked_photo_uv = validation['photo_uv']
    assert checked_photo_uv['slot_index'] == 1 and close(checked_photo_uv['min'], [0., 0.]) and close(checked_photo_uv['max'], [1., 1.])
    geometry = validation['geometry'][MESH_NAME]
    assert geometry['non_manifold_edges'] == 0 and geometry['triangles'] == spec['triangles']
    assert close(geometry['bounds_min_m'], spec['bounds_min_m']) and close(geometry['bounds_max_m'], spec['bounds_max_m'])
    assert len(validation['uv'][MESH_NAME]['layers']) == 1
    roundtrip = validation['fbx_roundtrip'][MESH_NAME]
    fbx = source_file(spec['filename'])
    assert roundtrip['success'] and roundtrip['sha256'] == sha(fbx)
    assert Path(roundtrip['source']).resolve() == fbx
    assert roundtrip['ucx_count'] == roundtrip['uv_layers'] == 1
    assert roundtrip['geometry']['triangles'] == spec['triangles']
    assert roundtrip['geometry']['non_manifold_edges'] == 0
    assert [re.sub(r'\.\d{3}$', '', str(name)) for name in roundtrip['material_slots']] == SOURCE_SLOTS
    for name, expected in {'M_PhotoPaper_Frame': ([.82, .80, .75], .66),
                           'M_PhotoPaper_Back': ([.73, .72, .67], .80)}.items():
        assert close(model['materials'][name]['base_color'], expected[0])
        assert abs(float(model['materials'][name]['roughness']) - expected[1]) < 1.e-6
    image_spec = model['materials']['M_PhotoPaper_Image']
    assert image_spec['texture_parameter'] == 'PhotoTexture' and abs(float(image_spec['roughness']) - .23) < 1.e-6
    texture_spec = model['texture']
    assert texture_spec['name'] == TEXTURE_NAME and texture_spec['filename'] == 'Textures/' + TEXTURE_NAME + '.png'
    png = source_file(texture_spec['filename'])
    assert sha(png) == texture_spec['sha256']
    with png.open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR'
    assert struct.unpack('>II', header[16:24]) == (128, 128)
    source_files = {source_file(name) for name in ('PhotoPaper.blend', 'model_report.json',
                                                 'validation_report.json', 'protected_content_sha256.json',
                                                 spec['filename'], texture_spec['filename'])}
    assert validation['renders'], 'No actual preview render exists'
    for render in validation['renders'].values():
        path = Path(render['path']).resolve()
        assert path.is_relative_to(OUT) and path.is_file() and sha(path) == render['sha256']
        source_files.add(path)
    report['source_files_sha256'] = {str(path): sha(path) for path in sorted(source_files)}
    report['source_preflight_passed'] = True
    report['photo_uv'] = photo_uv
    checkpoint()

    fbx_backend_world = world_before
    fbx_backend_before = unreal.SystemLibrary.get_console_variable_int_value(FBX_BACKEND_CVAR)
    report['fbx_backend_flag_before'] = fbx_backend_before
    unreal.SystemLibrary.execute_console_command(world_before, FBX_BACKEND_CVAR + ' 0')
    report['fbx_backend_flag_during_import'] = unreal.SystemLibrary.get_console_variable_int_value(FBX_BACKEND_CVAR)
    assert report['fbx_backend_flag_during_import'] == 0
    edit.make_directory(ROOT + '/Materials')
    edit.make_directory(ROOT + '/Textures')
    to_save, materials = [], {}

    task = unreal.AssetImportTask()
    for key, value in {'filename': str(png), 'destination_path': ROOT + '/Textures',
                       'destination_name': TEXTURE_NAME, 'automated': True,
                       'replace_existing': False, 'save': False, 'factory': unreal.TextureFactory()}.items():
        task.set_editor_property(key, value)
    tools.import_asset_tasks([task])
    texture_package = ROOT + '/Textures/' + TEXTURE_NAME
    assert imported_packages(task) == {texture_package}
    texture = edit.load_asset(texture_package)
    assert isinstance(texture, unreal.Texture2D)
    texture.set_editor_property('srgb', True)
    texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_DEFAULT)
    to_save.append(texture)
    report['created_assets'].append(texture.get_path_name())
    report['textures'][TEXTURE_NAME] = {'asset': texture.get_path_name(), 'source': str(png),
                                      'srgb': texture.get_editor_property('srgb'),
                                      'compression_settings': str(texture.get_editor_property('compression_settings')),
                                      'source_dimensions_px': [128, 128], 'source_sha256': sha(png)}
    checkpoint()

    for name in SOURCE_SLOTS:
        material = tools.create_asset(name, ROOT + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
        assert material and isinstance(material, unreal.Material)
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
        material.set_editor_property('two_sided', False)
        appearance = model['materials'][name]
        tint = vector_parameter(material, 'Tint', [1., 1., 1.] if name == 'M_PhotoPaper_Image' else appearance['base_color'], -700, -230)
        roughness = scalar_parameter(material, 'Roughness', appearance['roughness'], -400, 100)
        metallic = ml.create_material_expression(material, unreal.MaterialExpressionConstant, -400, 270)
        metallic.set_editor_property('r', 0.)
        assert ml.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
        assert ml.connect_material_property(metallic, '', unreal.MaterialProperty.MP_METALLIC)
        if name == 'M_PhotoPaper_Image':
            photo = ml.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D, -720, -30)
            photo.set_editor_property('parameter_name', 'PhotoTexture')
            photo.set_editor_property('group', 'Photo')
            photo.set_editor_property('texture', texture)
            photo.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
            # An unconnected coordinate input uses ConstCoordinate (documented
            # on UMaterialExpressionTextureSample). Explicitly retain UV0.
            # No coordinate expression or coordinate-input connection is made.
            photo.set_editor_property('const_coordinate', 0)
            assert photo.get_editor_property('const_coordinate') == 0
            multiply = ml.create_material_expression(material, unreal.MaterialExpressionMultiply, -380, -140)
            assert ml.connect_material_expressions(photo, 'RGB', multiply, 'A')
            assert ml.connect_material_expressions(tint, 'RGB', multiply, 'B')
            assert ml.connect_material_property(multiply, '', unreal.MaterialProperty.MP_BASE_COLOR)
        else:
            assert ml.connect_material_property(tint, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
        ml.recompile_material(material)
        color = ml.get_material_default_vector_parameter_value(material, 'Tint')
        info = {'asset': material.get_path_name(), 'blend_mode': str(material.get_editor_property('blend_mode')),
                'shading_model': str(material.get_editor_property('shading_model')),
                'two_sided': material.get_editor_property('two_sided'),
                'vector_parameters': [str(value) for value in ml.get_vector_parameter_names(material)],
                'Tint': [color.r, color.g, color.b, color.a],
                'scalar_parameters': {str(value): ml.get_material_default_scalar_parameter_value(material, value)
                                      for value in ml.get_scalar_parameter_names(material)},
                'texture_parameters': [str(value) for value in ml.get_texture_parameter_names(material)],
                'emissive_connected': ml.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is not None,
                'metallic': float(metallic.get_editor_property('r')),
                'connections': {'BaseColor': 'PhotoTexture.RGB * Tint.RGB' if name == 'M_PhotoPaper_Image' else 'Tint.RGB',
                                'Roughness': 'Roughness', 'Metallic': '0'}}
        assert close(info['Tint'], ([1., 1., 1., 1.] if name == 'M_PhotoPaper_Image' else appearance['base_color'] + [1.]))
        assert set(info['vector_parameters']) == {'Tint'} and set(info['scalar_parameters']) == {'Roughness'}
        assert abs(info['scalar_parameters']['Roughness'] - float(appearance['roughness'])) < 1.e-6
        assert not info['emissive_connected'] and info['metallic'] == 0. and not info['two_sided']
        assert 'BLEND_OPAQUE' in info['blend_mode'] and 'MSM_DEFAULT_LIT' in info['shading_model']
        if name == 'M_PhotoPaper_Image':
            assert info['texture_parameters'] == ['PhotoTexture']
            default_texture = ml.get_material_default_texture_parameter_value(material, 'PhotoTexture')
            assert default_texture == texture
            info['PhotoTexture_default'] = default_texture.get_path_name()
            info['PhotoTexture_node_class'] = photo.get_class().get_name()
            info['PhotoTexture_sampler_type'] = str(photo.get_editor_property('sampler_type'))
            info['PhotoTexture_coordinate_index'] = photo.get_editor_property('const_coordinate')
            info['PhotoTexture_coordinate_mode'] = 'implicit_const_coordinate'
            info['connections']['PhotoTextureCoordinates'] = 'unconnected; ConstCoordinate=0 (UV0)'
            assert info['PhotoTexture_node_class'] == 'MaterialExpressionTextureSampleParameter2D'
        else:
            assert not info['texture_parameters']
        materials[name] = material
        report['materials'][name] = info
        to_save.append(material)
        report['created_assets'].append(material.get_path_name())
        checkpoint()

    instance = tools.create_asset('MI_PhotoPaper_Image', ROOT + '/Materials',
                                  unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    assert instance and isinstance(instance, unreal.MaterialInstanceConstant)
    ml.set_material_instance_parent(instance, materials['M_PhotoPaper_Image'])
    # UE 5.7's implementation returns False even after setting the texture.
    # Verify the effective value and stored override below instead.
    ml.set_material_instance_texture_parameter_value(instance, 'PhotoTexture', texture)
    ml.update_material_instance(instance)
    parent = instance.get_editor_property('parent')
    effective = ml.get_material_instance_texture_parameter_value(instance, 'PhotoTexture')
    overrides = instance.get_editor_property('texture_parameter_values')
    override_values = {str(value.parameter_info.name): value.parameter_value.get_path_name()
                       for value in overrides if value.parameter_value}
    assert parent == materials['M_PhotoPaper_Image'] and effective == texture
    assert override_values == {'PhotoTexture': texture.get_path_name()}
    report['material_instances']['MI_PhotoPaper_Image'] = {
        'asset': instance.get_path_name(), 'parent': parent.get_path_name(),
        'texture_parameters': [str(value) for value in ml.get_texture_parameter_names(instance)],
        'texture_overrides': override_values, 'PhotoTexture_effective': effective.get_path_name(),
        'runtime_parameter_name': 'PhotoTexture', 'runtime_capture_texture_compatible': True}
    to_save.append(instance)
    report['created_assets'].append(instance.get_path_name())
    checkpoint()

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
    for key, value in {'filename': str(fbx), 'destination_path': ROOT, 'destination_name': MESH_NAME,
                       'automated': True, 'replace_existing': False, 'save': False, 'options': options}.items():
        task.set_editor_property(key, value)
    tools.import_asset_tasks([task])
    assert imported_packages(task) == {ROOT + '/' + MESH_NAME}
    mesh = edit.load_asset(ROOT + '/' + MESH_NAME)
    assert mesh and isinstance(mesh, unreal.StaticMesh)
    assert [str(slot.material_slot_name) for slot in mesh.static_materials] == SOURCE_SLOTS
    for index, name in enumerate(SLOT_TARGETS):
        mesh.set_material(index, instance if name == 'MI_PhotoPaper_Image' else materials[name])
    settings = sm_editor.get_lod_build_settings(mesh, 0)
    settings.set_editor_property('generate_lightmap_u_vs', True)
    settings.set_editor_property('remove_degenerates', False)
    settings.set_editor_property('src_lightmap_index', 0)
    settings.set_editor_property('dst_lightmap_index', 1)
    sm_editor.set_lod_build_settings(mesh, 0, settings)
    settings = sm_editor.get_lod_build_settings(mesh, 0)
    mesh.set_editor_property('light_map_coordinate_index', 1)
    mesh.set_editor_property('light_map_resolution', 128)
    bounds = mesh.get_bounds()
    origin, extent = bounds.origin, bounds.box_extent
    dimensions = [extent.x * 2., extent.y * 2., extent.z * 2.]
    minimum = [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z]
    maximum = [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]
    expected_min = [spec['bounds_min_m'][0] * 100., -spec['bounds_max_m'][1] * 100., spec['bounds_min_m'][2] * 100.]
    expected_max = [spec['bounds_max_m'][0] * 100., -spec['bounds_min_m'][1] * 100., spec['bounds_max_m'][2] * 100.]
    info = {'asset': mesh.get_path_name(), 'dimensions_cm': dimensions,
            'expected_dimensions_cm': spec['dimensions_cm'],
            'dimension_error_cm': [abs(a - float(b)) for a, b in zip(dimensions, spec['dimensions_cm'])],
            'dimension_tolerance_cm': .001, 'bounds_min_cm': minimum, 'bounds_max_cm': maximum,
            'expected_bounds_min_cm': expected_min, 'expected_bounds_max_cm': expected_max,
            'bounds_error_cm': [abs(a - b) for a, b in zip(minimum + maximum, expected_min + expected_max)],
            'bounds_tolerance_cm': .001, 'render_triangles_lod0': mesh.get_num_triangles(0),
            'expected_triangles': spec['triangles'], 'convex_collision_hulls': sm_editor.get_convex_collision_count(mesh),
            'expected_collision_hulls': 1, 'uv_channels_lod0': sm_editor.get_num_uv_channels(mesh, 0),
            'source_uv_channels_expected': 1, 'fbx_import_remove_degenerates': mesh.get_editor_property('asset_import_data').get_editor_property('remove_degenerates'),
            'lightmap_build_settings': {'remove_degenerates': settings.get_editor_property('remove_degenerates'),
                                       'generate_lightmap_u_vs': settings.get_editor_property('generate_lightmap_u_vs'),
                                       'src_lightmap_index': settings.get_editor_property('src_lightmap_index'),
                                       'dst_lightmap_index': settings.get_editor_property('dst_lightmap_index'),
                                       'generated_render_data_uv1_separately_verified': False},
            'lightmap_coordinate_index': mesh.get_editor_property('light_map_coordinate_index'),
            'source_photo_uv0_verified': True,
            'matSlots': [{'index': i, 'slot_name': str(slot.material_slot_name),
                          'material': slot.material_interface.get_path_name() if slot.material_interface else None}
                         for i, slot in enumerate(mesh.static_materials)]}
    report['assets'][MESH_NAME] = info
    checkpoint()
    assert max(info['dimension_error_cm']) <= .001 and max(info['bounds_error_cm']) <= .001, info
    assert info['render_triangles_lod0'] == spec['triangles'] and info['convex_collision_hulls'] == 1
    assert info['uv_channels_lod0'] >= 1
    assert info['fbx_import_remove_degenerates'] is False and info['lightmap_build_settings']['remove_degenerates'] is False
    assert info['lightmap_build_settings']['generate_lightmap_u_vs'] is True
    assert info['lightmap_build_settings']['src_lightmap_index'] == 0
    assert info['lightmap_build_settings']['dst_lightmap_index'] == info['lightmap_coordinate_index'] == 1
    assert [slot['slot_name'] for slot in info['matSlots']] == SOURCE_SLOTS
    assert [slot['material'] for slot in info['matSlots']] == [ROOT + '/Materials/' + name + '.' + name for name in SLOT_TARGETS]
    to_save.append(mesh)
    report['created_assets'].append(mesh.get_path_name())
    assert len(to_save) == len(report['created_assets']) == 6
    assert {name.split('.')[0] for name in report['created_assets']} == EXPECTED_PACKAGES
    for asset in to_save:
        assert edit.save_loaded_asset(asset, False), asset.get_path_name()
    for package in sorted(EXPECTED_PACKAGES):
        path = package_file(package)
        assert path.is_file() and path.stat().st_size > 0 and edit.does_asset_exist(package), package
        report['new_packages_on_disk'][package] = {'file': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}
    assert {path.resolve() for path in CONTENT_ROOT.rglob('*.uasset')} == {package_file(package) for package in EXPECTED_PACKAGES}
    report['new_package_count'] = len(report['new_packages_on_disk'])
    report['source_files_unchanged'] = all(sha(path) == digest for path, digest in report['source_files_sha256'].items())
    assert report['source_files_unchanged']
    report['protected_files_checked_after'] = verify_protected()
    report['protected_content_unchanged'] = True
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
            assert report['fbx_backend_flag_restored']
        except Exception:
            report['success'] = False
            report['fbx_backend_restore_error'] = traceback.format_exc()
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    checkpoint()
    unreal.log('PHOTOPAPER_IMPORT ' + json.dumps(report))
