"""Split-camera import; run exclusively in the full editor using run_update.ps1.

Only the existing body and new shutter mesh may be saved. Source textures,
materials, UI, maps and configuration are hash-checked and never saved here.
"""
import hashlib
import json
import os
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import unreal

PROJECT = Path(r'D:\UE\Project\HorrorGame').resolve()
CONTENT = PROJECT / 'Content'
SOURCE = PROJECT / 'SourceArt' / 'Camera'
OUT = SOURCE / 'ShutterSplit'
ROOT = '/Game/Yastars/Mesh/Camera'
CONTENT_ROOT = CONTENT / 'Yastars' / 'Mesh' / 'Camera'
BODY = 'SM_Camera'
BUTTON = 'SM_Camera_ShutterButton'
NAMES = {BODY, BUTTON}
MATERIALS = {'M_Camera_Opaque', 'M_Camera_Glass'}
CHANNELS = ('BaseColor', 'Roughness', 'Normal', 'Metallic')
BASE_PACKAGES = ({ROOT + '/' + BODY}
                 | {ROOT + '/Materials/' + name for name in MATERIALS}
                 | {ROOT + '/Textures/T_Camera_' + channel for channel in CHANNELS})
EXPECTED_PACKAGES = BASE_PACKAGES | {ROOT + '/' + BUTTON}
BODY_SLOTS = {
    'M_Camera_SatinChrome': 'M_Camera_Opaque',
    'M_Camera_Leatherette': 'M_Camera_Opaque',
    'M_Camera_PolishedTrim': 'M_Camera_Opaque',
    'M_Camera_OpticalInterior': 'M_Camera_Opaque',
    'M_Camera_BlackEnamel': 'M_Camera_Opaque',
    'M_Camera_ContactBrass': 'M_Camera_Opaque',
    'M_Camera_EngravedIvory': 'M_Camera_Opaque',
    'M_Camera_RubberGrip': 'M_Camera_Opaque',
    'M_Camera_OpticalGlass': 'M_Camera_Glass',
    'M_Camera_FilmMemoPaper': 'M_Camera_Opaque',
}
BUTTON_SLOTS = {key: 'M_Camera_Opaque' for key in
                ('M_Camera_PolishedTrim', 'M_Camera_OpticalInterior')}
REPORT_PATH = OUT / 'update_ue_report.json'
report = {
    'success': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
    'run_id': os.environ.get('CAMERA_SHUTTER_UPDATE_RUN_ID') or str(uuid.uuid4()),
    'editor_pid': os.getpid(), 'target_root': ROOT,
    'update_script_sha256': hashlib.sha256((OUT / 'update_ue.py').read_bytes()).hexdigest(),
    'assets': {}, 'source_files_sha256': {}, 'packages_before': {}, 'packages_after': {},
    'saved_assets': [], 'import_order': [],
    'map_save_executed': False, 'level_load_executed': False,
    'asset_delete_executed': False, 'asset_or_map_rename_executed': False,
    'actors_spawned': 0, 'materials_created': 0, 'textures_created': 0,
}
fbx_backend_before = None
fbx_backend_world = None
FBX_BACKEND_CVAR = 'Interchange.FeatureFlags.Import.FBX'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def checkpoint():
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))


def package_file(package):
    assert package in EXPECTED_PACKAGES, package
    result = (CONTENT / (package[6:] + '.uasset')).resolve()
    assert result.is_relative_to(CONTENT_ROOT.resolve()), str(result)
    return result


def track_source(path, expected=None):
    path = Path(path).resolve()
    assert path.is_relative_to(SOURCE.resolve()) and path.is_file(), str(path)
    digest = sha(path)
    if expected is not None:
        assert digest == expected.lower(), ('Source changed', str(path))
    report['source_files_sha256'][str(path)] = digest
    return path


def sources_unchanged():
    return all(Path(path).is_file() and sha(path) == digest
               for path, digest in report['source_files_sha256'].items())


def check_protected(protected):
    assert isinstance(protected, list) and protected
    paths = {Path(item['path']).resolve() for item in protected}
    assert len(paths) == len(protected), 'Duplicate protected paths'
    for item in protected:
        path = Path(item['path']).resolve()
        assert path.is_file() and sha(path) == item['sha256'].lower(), ('Protected file changed', str(path))
    ui, config = CONTENT / 'Yastar' / 'UI', PROJECT / 'Config'
    current = {
        'ui': {p.resolve() for p in ui.rglob('*') if p.is_file()},
        'maps': {p.resolve() for p in CONTENT.rglob('*.umap')},
        'config': {p.resolve() for p in config.rglob('*') if p.is_file()},
    }
    expected = {
        'ui': {p for p in paths if p.is_relative_to(ui)},
        'maps': {p for p in paths if p.suffix.lower() == '.umap'},
        'config': {p for p in paths if p.is_relative_to(config)},
    }
    assert current == expected, 'Protected UI, map or config file set changed'
    return len(paths)


def package_info(package):
    path = package_file(package)
    assert path.is_file() and path.stat().st_size > 0, package
    return {'file': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def socket_info(socket):
    loc = socket.get_editor_property('relative_location')
    rot = socket.get_editor_property('relative_rotation')
    scale = socket.get_editor_property('relative_scale')
    return {'name': str(socket.get_editor_property('socket_name')),
            'relative_location_cm': [loc.x, loc.y, loc.z],
            'relative_rotation_deg': [rot.pitch, rot.yaw, rot.roll],
            'relative_scale': [scale.x, scale.y, scale.z]}


def mesh_sockets(mesh):
    # The StaticMesh sockets array is protected in Python. Query the public
    # SceneComponent API on an unregistered transient component instead.
    # No actor, world component registration or level change is involved.
    component = unreal.StaticMeshComponent()
    assert component.set_static_mesh(mesh), 'Cannot query mesh sockets'
    names = [str(name) for name in component.get_all_socket_names()]
    assert len(names) == len(set(names)), 'Duplicate socket names need review'
    result = {}
    for name in names:
        socket = mesh.find_socket(name)
        assert socket is not None, ('Socket query could not resolve name', name)
        result[name] = socket_info(socket)
    return result


def close_enough(actual, expected, tolerance=.001):
    assert len(actual) == len(expected)
    return all(abs(float(a) - float(b)) <= tolerance for a, b in zip(actual, expected))


def validate_mesh(mesh, name, spec, sm_editor, materials):
    bounds = mesh.get_bounds()
    extent, origin = bounds.box_extent, bounds.origin
    dimensions = [extent.x * 2., extent.y * 2., extent.z * 2.]
    bounds_min = [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z]
    bounds_max = [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]
    source_min, source_max = spec['bounds_min_m'], spec['bounds_max_m']
    expected_min = [source_min[0] * 100., -source_max[1] * 100., source_min[2] * 100.]
    expected_max = [source_max[0] * 100., -source_min[1] * 100., source_max[2] * 100.]
    settings = sm_editor.get_lod_build_settings(mesh, 0)
    import_data = mesh.get_editor_property('asset_import_data')
    slots = [{'index': i, 'slot_name': str(slot.material_slot_name),
              'material': slot.material_interface.get_path_name() if slot.material_interface else None}
             for i, slot in enumerate(mesh.static_materials)]
    result = {
        'asset': mesh.get_path_name(), 'dimensions_cm': dimensions,
        'expected_dimensions_cm': spec['dimensions_cm'], 'dimension_tolerance_cm': .001,
        'bounds_min_cm': bounds_min, 'bounds_max_cm': bounds_max,
        'expected_bounds_min_cm': expected_min, 'expected_bounds_max_cm': expected_max,
        'bounds_tolerance_cm': .001, 'axis_transform': 'X*100,-Y*100,Z*100',
        'render_triangles_lod0': mesh.get_num_triangles(0), 'expected_triangles': spec['triangles'],
        'convex_collision_hulls': sm_editor.get_convex_collision_count(mesh),
        'expected_collision_hulls': spec['collision_hulls'],
        'source_uv_channels_expected': spec['uv_channels'],
        'uv_channels_lod0': sm_editor.get_num_uv_channels(mesh, 0), 'matSlots': slots,
        'fbx_import_remove_degenerates': import_data.get_editor_property('remove_degenerates'),
        'lightmap_coordinate_index': mesh.get_editor_property('light_map_coordinate_index'),
        'lightmap_build_settings': {
            'generate_lightmap_u_vs': settings.get_editor_property('generate_lightmap_u_vs'),
            'remove_degenerates': settings.get_editor_property('remove_degenerates'),
            'src_lightmap_index': settings.get_editor_property('src_lightmap_index'),
            'dst_lightmap_index': settings.get_editor_property('dst_lightmap_index'),
        },
    }
    report['assets'][name] = result
    checkpoint()
    assert close_enough(dimensions, spec['dimensions_cm']), (name, result)
    assert close_enough(bounds_min + bounds_max, expected_min + expected_max), (name, result)
    assert result['render_triangles_lod0'] == spec['triangles'], (name, result)
    assert result['convex_collision_hulls'] == spec['collision_hulls'], (name, result)
    assert result['uv_channels_lod0'] >= spec['uv_channels'] == 1, (name, result)
    assert result['fbx_import_remove_degenerates'] is False
    assert result['lightmap_build_settings'] == {
        'generate_lightmap_u_vs': True, 'remove_degenerates': False,
        'src_lightmap_index': 0, 'dst_lightmap_index': 1,
    }
    assert result['lightmap_coordinate_index'] == 1
    assert len(slots) == len(spec['material_slots'])
    assert {slot['slot_name'] for slot in slots} == set(spec['material_slots'])
    assert all(slot['material'] == materials[spec['material_slots'][slot['slot_name']]].get_path_name()
               for slot in slots), (name, slots)
    return result


try:
    assert Path(unreal.Paths.project_dir()).resolve() == PROJECT, 'Wrong UE project'
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    sm_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    assert editor and sm_editor, 'Use the full editor, not a commandlet'
    world_before = editor.get_editor_world()
    report['world_before'] = world_before.get_path_name() if world_before else None
    assert report['world_before'] and report['world_before'].startswith('/Engine/Maps/Entry.'), report['world_before']
    edit = unreal.EditorAssetLibrary
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    registry.wait_for_completion()
    assert not registry.is_loading_assets()
    assert not package_file(ROOT + '/' + BUTTON).exists() and not edit.does_asset_exist(ROOT + '/' + BUTTON), (
        'New shutter asset already exists; refusing replacement')
    before = read('ue_before_manifest.json')
    assert isinstance(before, list) and len(before) == 7
    baseline = {Path(item['path']).resolve(): item['sha256'].lower() for item in before}
    expected_paths = {package_file(package) for package in BASE_PACKAGES}
    assert set(baseline) == expected_paths and len(baseline) == 7
    assert {p.resolve() for p in CONTENT_ROOT.rglob('*.uasset')} == expected_paths
    for package in sorted(BASE_PACKAGES):
        info = package_info(package)
        assert info['sha256'] == baseline[package_file(package)], ('Existing UE package changed', package)
        assert edit.does_asset_exist(package), package
        report['packages_before'][package] = info
    protected = read('protected_content_sha256.json')
    report['protected_files_checked'] = check_protected(protected)
    split = read('split_report.json')
    assert split['success'] and set(split['parts']) == NAMES
    assert split['original_total_triangles'] == 45168
    assert sum(part['triangles'] for part in split['parts'].values()) == 45168
    assert close_enough(split['pivot_blender_m'], [.061, -.011, .0824], 1.e-6)
    assert close_enough(split['socket_ue_cm'], [6.1, 1.1, 8.24], 1.e-6)
    assert abs(split['press_travel_cm'] - .12) < 1.e-6
    assert split['parts'][BODY]['material_slots'] == BODY_SLOTS
    assert split['parts'][BUTTON]['material_slots'] == BUTTON_SLOTS
    assert split['parts'][BODY]['collision_hulls'] == 4
    assert split['parts'][BUTTON]['collision_hulls'] == 1
    track_source(OUT / 'split_report.json')
    track_source(OUT / 'ue_before_manifest.json')
    track_source(OUT / 'protected_content_sha256.json')
    track_source(SOURCE / 'Camera.blend', split['blend_sha256'])
    for name, part in split['parts'].items():
        assert part['filename'] == name + '.fbx' and part['uv_channels'] == 1
        assert part['triangles'] > 0
        assert len(part['dimensions_cm']) == len(part['bounds_min_m']) == len(part['bounds_max_m']) == 3
        assert all(float(value) > 0 for value in part['dimensions_cm'])
        track_source(SOURCE / part['filename'], part['sha256'])
    texture_sources = {str((SOURCE / 'Textures' / ('T_Camera_' + channel + '.png')).resolve()) for channel in CHANNELS}
    assert set(split['texture_files_sha256']) == texture_sources
    for filename, digest in split['texture_files_sha256'].items():
        track_source(filename, digest)
    materials = {name: edit.load_asset(ROOT + '/Materials/' + name) for name in MATERIALS}
    assert all(isinstance(value, unreal.MaterialInterface) for value in materials.values())
    existing_body = edit.load_asset(ROOT + '/' + BODY)
    assert isinstance(existing_body, unreal.StaticMesh)
    report['body_asset_path_before'] = existing_body.get_path_name()
    assert {str(slot.material_slot_name) for slot in existing_body.static_materials} == set(BODY_SLOTS)
    old_sockets = mesh_sockets(existing_body)
    report['socket_query_api'] = 'Transient StaticMeshComponent.get_all_socket_names + StaticMesh.find_socket'
    report['existing_sockets_before'] = old_sockets
    assert 'ShutterButton' not in old_sockets, 'Existing shutter socket needs review'
    assert callable(getattr(existing_body, 'add_socket', None)) and callable(getattr(existing_body, 'find_socket', None))
    assert hasattr(unreal, 'StaticMeshSocket'), 'Static mesh socket API unavailable'
    report['source_preflight_passed'] = True
    checkpoint()
    fbx_backend_world = world_before
    fbx_backend_before = unreal.SystemLibrary.get_console_variable_int_value(FBX_BACKEND_CVAR)
    report['fbx_backend_flag_before'] = fbx_backend_before
    unreal.SystemLibrary.execute_console_command(fbx_backend_world, FBX_BACKEND_CVAR + ' 0')
    report['fbx_backend_flag_during_import'] = unreal.SystemLibrary.get_console_variable_int_value(FBX_BACKEND_CVAR)
    assert report['fbx_backend_flag_during_import'] == 0
    meshes = {}
    for name in (BUTTON, BODY):
        part = split['parts'][name]
        options = unreal.FbxImportUI()
        for key, value in {
            'import_mesh': True, 'import_as_skeletal': False, 'import_materials': False,
            'import_textures': False, 'automated_import_should_detect_type': False,
            'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH,
        }.items():
            options.set_editor_property(key, value)
        for key, value in {
            'import_uniform_scale': 100., 'combine_meshes': True,
            'auto_generate_collision': False, 'one_convex_hull_per_ucx': True,
            'generate_lightmap_u_vs': True, 'remove_degenerates': False,
            'normal_import_method': unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
            'transform_vertex_to_absolute': True, 'bake_pivot_in_vertex': False,
        }.items():
            options.static_mesh_import_data.set_editor_property(key, value)
        task = unreal.AssetImportTask()
        for key, value in {
            'filename': str(SOURCE / part['filename']), 'destination_path': ROOT,
            'destination_name': name, 'automated': True, 'replace_existing': name == BODY,
            'replace_existing_settings': name == BODY, 'save': False, 'options': options,
        }.items():
            task.set_editor_property(key, value)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        paths = {str(path).split('.')[0] for path in task.get_editor_property('imported_object_paths')}
        assert paths == {ROOT + '/' + name}, (name, paths)
        mesh = edit.load_asset(ROOT + '/' + name)
        assert isinstance(mesh, unreal.StaticMesh)
        if name == BODY:
            assert mesh.get_path_name() == report['body_asset_path_before']
        for index, slot in enumerate(mesh.static_materials):
            slot_name = str(slot.material_slot_name)
            assert slot_name in part['material_slots'], (name, slot_name)
            mesh.set_material(index, materials[part['material_slots'][slot_name]])
        mesh.set_editor_property('light_map_resolution', 128)
        settings = sm_editor.get_lod_build_settings(mesh, 0)
        for key, value in {'generate_lightmap_u_vs': True, 'remove_degenerates': False,
                           'src_lightmap_index': 0, 'dst_lightmap_index': 1}.items():
            settings.set_editor_property(key, value)
        sm_editor.set_lod_build_settings(mesh, 0, settings)
        mesh.set_editor_property('light_map_coordinate_index', 1)
        validate_mesh(mesh, name, part, sm_editor, materials)
        report['import_order'].append(name)
        meshes[name] = mesh
        checkpoint()
    body = meshes[BODY]
    # UStaticMeshSocket outer is the mesh, as required by StaticMeshSocket.h.
    socket = unreal.StaticMeshSocket(outer=body)
    socket.set_editor_property('socket_name', 'ShutterButton')
    socket.set_editor_property('relative_location', unreal.Vector(*split['socket_ue_cm']))
    socket.set_editor_property('relative_rotation', unreal.Rotator(0., 0., 0.))
    socket.set_editor_property('relative_scale', unreal.Vector(1., 1., 1.))
    body.add_socket(socket)
    saved_socket = body.find_socket('ShutterButton')
    assert saved_socket is not None
    report['shutter_socket'] = socket_info(saved_socket)
    assert report['shutter_socket']['name'] == 'ShutterButton'
    assert close_enough(report['shutter_socket']['relative_location_cm'], split['socket_ue_cm'], 1.e-6)
    assert close_enough(report['shutter_socket']['relative_rotation_deg'], [0., 0., 0.], 1.e-6)
    assert close_enough(report['shutter_socket']['relative_scale'], [1., 1., 1.], 1.e-6)
    current_sockets = mesh_sockets(body)
    report['body_sockets_after'] = current_sockets
    assert len(current_sockets) == len(old_sockets) + 1
    assert all(current_sockets.get(key) == value for key, value in old_sockets.items())
    report['existing_sockets_preserved'] = True
    report['press_travel_cm'] = split['press_travel_cm']
    report['render_triangles_total'] = sum(info['render_triangles_lod0'] for info in report['assets'].values())
    assert report['render_triangles_total'] == 45168
    assert sources_unchanged(), 'Source changed before save'
    check_protected(protected)
    assert all(package_info(package)['sha256'] == report['packages_before'][package]['sha256']
               for package in BASE_PACKAGES), 'Existing package changed before authorized mesh save'
    report['all_mesh_validation_passed_before_save'] = True
    checkpoint()
    # No package is saved until both meshes and the socket pass every check.
    for name in (BUTTON, BODY):
        assert edit.save_loaded_asset(meshes[name], False), name
        report['saved_assets'].append(meshes[name].get_path_name())
        checkpoint()
    for package in sorted(EXPECTED_PACKAGES):
        report['packages_after'][package] = package_info(package)
    assert {p.resolve() for p in CONTENT_ROOT.rglob('*.uasset')} == {package_file(package) for package in EXPECTED_PACKAGES}
    report['package_count_after'] = len(report['packages_after'])
    report['changed_existing_packages'] = sorted(package for package in BASE_PACKAGES
        if report['packages_before'][package]['sha256'] != report['packages_after'][package]['sha256'])
    assert report['changed_existing_packages'] == [ROOT + '/' + BODY]
    report['unchanged_material_texture_packages'] = sorted(BASE_PACKAGES - {ROOT + '/' + BODY})
    report['source_files_unchanged'] = sources_unchanged()
    assert report['source_files_unchanged']
    check_protected(protected)
    report['ui_maps_and_config_unchanged'] = True
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
unreal.log('CAMERA_SHUTTER_UPDATE ' + json.dumps(report))
