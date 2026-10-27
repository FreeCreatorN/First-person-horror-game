"""Read-only source/package verification after the exclusive camera update.

The sole output is final_verification.json beside this script. No UE process
is launched, and no source, package, material, texture or map is modified.
"""
import hashlib
import json
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
SOURCE = OUT.parent
PROJECT = SOURCE.parents[1]
CONTENT = PROJECT / 'Content'
CONTENT_ROOT = CONTENT / 'Yastars' / 'Mesh' / 'Camera'
ROOT = '/Game/Yastars/Mesh/Camera'
BODY, BUTTON = 'SM_Camera', 'SM_Camera_ShutterButton'
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
BUTTON_SLOTS = {name: 'M_Camera_Opaque' for name in
                ('M_Camera_PolishedTrim', 'M_Camera_OpticalInterior')}
report = {'success': False, 'checked_utc': datetime.now(timezone.utc).isoformat(),
          'target_root': ROOT, 'errors': [], 'read_only': True}


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert result.tzinfo is not None, value
    return result.astimezone(timezone.utc)


def verified_file(path, digest=None, within=None):
    path = Path(path).resolve()
    if within is not None:
        assert path.is_relative_to(Path(within).resolve()), str(path)
    assert path.is_file() and path.stat().st_size > 0, str(path)
    actual = sha(path)
    if digest is not None:
        assert actual == digest.lower(), ('File changed', str(path))
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': actual}


def close_enough(actual, expected, tolerance=.001):
    assert len(actual) == len(expected)
    return all(abs(float(a) - float(b)) <= tolerance for a, b in zip(actual, expected))


try:
    split, ue, completion = read('split_report.json'), read('update_ue_report.json'), read('update_ue_completion.json')
    assert split['success'] and ue['success'] and completion['success'], 'A required source/import/completion stage failed'
    assert set(split['parts']) == set(ue['assets']) == NAMES
    assert split['original_total_triangles'] == ue['render_triangles_total'] == 45168
    assert sum(part['triangles'] for part in split['parts'].values()) == 45168
    assert split['parts'][BODY]['material_slots'] == BODY_SLOTS
    assert split['parts'][BUTTON]['material_slots'] == BUTTON_SLOTS
    assert close_enough(split['pivot_blender_m'], [.061, -.011, .0824], 1.e-6)
    assert close_enough(split['socket_ue_cm'], [6.1, 1.1, 8.24], 1.e-6)
    assert abs(split['press_travel_cm'] - .12) < 1.e-6
    assert completion['execution_mode'] == 'exclusive_editor'
    assert completion['normal_zero_exit'] and completion['exit_code'] == 0
    assert completion['editor_pid'] == ue['editor_pid']
    assert completion['run_id'] == ue['run_id'] and ue['run_id']
    assert completion['script_sha256'] == ue['update_script_sha256'] == sha(OUT / 'update_ue.py')
    assert completion['report_sha256'] == sha(OUT / 'update_ue_report.json')
    assert utc(completion['script_completed_utc']) == utc(ue['completed_utc'])
    assert completion['target_root'] == ue['target_root'] == ROOT
    assert completion['temporary_engine_world'] == '/Engine/Maps/Entry'
    assert completion['private_ddc'] == 'D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
    assert Path(completion['report']).resolve() == OUT / 'update_ue_report.json'
    begin, end = utc(completion['started_utc']), utc(completion['completed_utc'])
    assert begin <= end
    assert begin - timedelta(seconds=1) <= utc(ue['started_utc']) <= utc(ue['completed_utc']) <= end + timedelta(seconds=1)
    assert datetime.fromtimestamp((OUT / 'update_ue_report.json').stat().st_mtime, timezone.utc) >= begin
    assert ue['source_preflight_passed'] and ue['source_files_unchanged']
    assert ue['all_mesh_validation_passed_before_save']
    assert ue['import_order'] == [BUTTON, BODY]
    assert ue['saved_assets'] == [ROOT + '/' + name + '.' + name for name in (BUTTON, BODY)]
    assert ue['body_asset_path_before'] == ROOT + '/' + BODY + '.' + BODY
    assert ue['fbx_backend_flag_during_import'] == 0 and ue['fbx_backend_flag_restored']
    assert ue['fbx_backend_flag_before'] == ue['fbx_backend_flag_after']
    assert ue['world_before'].startswith('/Engine/Maps/Entry.')
    assert ue['same_world_object'] and ue['world_before'] == ue['world_after']
    assert not ue['map_save_executed'] and not ue['level_load_executed']
    assert not ue['asset_delete_executed'] and not ue['asset_or_map_rename_executed']
    assert ue['actors_spawned'] == ue['materials_created'] == ue['textures_created'] == 0
    assert ue['package_count_after'] == 8 and set(ue['packages_after']) == EXPECTED_PACKAGES
    assert set(ue['packages_before']) == BASE_PACKAGES
    assert ue['changed_existing_packages'] == [ROOT + '/' + BODY]
    assert set(ue['unchanged_material_texture_packages']) == BASE_PACKAGES - {ROOT + '/' + BODY}

    before = read('ue_before_manifest.json')
    assert isinstance(before, list) and len(before) == 7
    baseline = {Path(info['path']).resolve(): info['sha256'].lower() for info in before}
    assert len(baseline) == 7
    assert set(baseline) == {(CONTENT / (package[6:] + '.uasset')).resolve() for package in BASE_PACKAGES}
    report['package_files'] = {}
    for package, info in ue['packages_after'].items():
        expected = (CONTENT / (package[6:] + '.uasset')).resolve()
        assert Path(info['file']).resolve() == expected
        result = verified_file(expected, info['sha256'], within=CONTENT_ROOT)
        assert result['bytes'] == info['bytes']
        report['package_files'][package] = result
        if package in BASE_PACKAGES:
            original = ue['packages_before'][package]
            assert Path(original['file']).resolve() == expected
            assert original['sha256'] == baseline[expected]
            if package.endswith('/' + BODY):
                assert result['sha256'] != baseline[expected]
            else:
                assert result['sha256'] == baseline[expected]
    assert {p.resolve() for p in CONTENT_ROOT.rglob('*.uasset')} == {
        Path(info['path']) for info in report['package_files'].values()}
    report['six_original_material_texture_packages_unchanged'] = True
    report['body_reimport_preserved_asset_path'] = True

    protected = read('protected_content_sha256.json')
    assert isinstance(protected, list) and protected
    protected_paths = {Path(info['path']).resolve() for info in protected}
    assert len(protected_paths) == len(protected)
    report['protected_files_checked'] = len(protected)
    report['protected_files_changed'] = [info['path'] for info in protected
        if not Path(info['path']).is_file() or sha(info['path']) != info['sha256'].lower()]
    assert not report['protected_files_changed'], report['protected_files_changed']
    ui, config = CONTENT / 'Yastar' / 'UI', PROJECT / 'Config'
    current = {
        'ui': {p.resolve() for p in ui.rglob('*') if p.is_file()},
        'maps': {p.resolve() for p in CONTENT.rglob('*.umap')},
        'config': {p.resolve() for p in config.rglob('*') if p.is_file()},
    }
    expected = {
        'ui': {p for p in protected_paths if p.is_relative_to(ui)},
        'maps': {p for p in protected_paths if p.suffix.lower() == '.umap'},
        'config': {p for p in protected_paths if p.is_relative_to(config)},
    }
    assert current == expected, 'Protected UI, map or config file set changed'
    assert ue['ui_maps_and_config_unchanged']
    report['ui_maps_and_config_unchanged'] = True

    report['source_files'] = {}
    report['source_files']['Camera.blend'] = verified_file(SOURCE / 'Camera.blend', split['blend_sha256'], within=SOURCE)
    for name, part in split['parts'].items():
        assert part['filename'] == name + '.fbx'
        assert part['uv_channels'] == 1 and part['collision_hulls'] == (4 if name == BODY else 1)
        assert len(part['dimensions_cm']) == len(part['bounds_min_m']) == len(part['bounds_max_m']) == 3
        assert all(value > 0 for value in part['dimensions_cm'])
        fbx = (SOURCE / part['filename']).resolve()
        report['source_files'][part['filename']] = verified_file(fbx, part['sha256'], within=SOURCE)
        assert ue['source_files_sha256'][str(fbx)] == part['sha256']
        mesh = ue['assets'][name]
        source_min, source_max = part['bounds_min_m'], part['bounds_max_m']
        expected_min = [source_min[0] * 100., -source_max[1] * 100., source_min[2] * 100.]
        expected_max = [source_max[0] * 100., -source_min[1] * 100., source_max[2] * 100.]
        assert mesh['asset'] == ROOT + '/' + name + '.' + name
        assert mesh['dimension_tolerance_cm'] <= .001 and mesh['bounds_tolerance_cm'] <= .001
        assert close_enough(mesh['dimensions_cm'], part['dimensions_cm'], mesh['dimension_tolerance_cm'])
        assert close_enough(mesh['bounds_min_cm'] + mesh['bounds_max_cm'], expected_min + expected_max,
                            mesh['bounds_tolerance_cm'])
        assert close_enough(mesh['expected_bounds_min_cm'] + mesh['expected_bounds_max_cm'], expected_min + expected_max, 1.e-6)
        assert mesh['axis_transform'] == 'X*100,-Y*100,Z*100'
        assert mesh['render_triangles_lod0'] == mesh['expected_triangles'] == part['triangles']
        assert mesh['convex_collision_hulls'] == mesh['expected_collision_hulls'] == part['collision_hulls']
        assert mesh['uv_channels_lod0'] >= mesh['source_uv_channels_expected'] == part['uv_channels']
        assert mesh['fbx_import_remove_degenerates'] is False
        assert mesh['lightmap_coordinate_index'] == 1
        assert mesh['lightmap_build_settings'] == {
            'generate_lightmap_u_vs': True, 'remove_degenerates': False,
            'src_lightmap_index': 0, 'dst_lightmap_index': 1,
        }
        slots = mesh['matSlots']
        assert len(slots) == len(part['material_slots'])
        assert {slot['slot_name'] for slot in slots} == set(part['material_slots'])
        assert all(slot['material'] == ROOT + '/Materials/' + part['material_slots'][slot['slot_name']]
                   + '.' + part['material_slots'][slot['slot_name']] for slot in slots)
    texture_sources = {str((SOURCE / 'Textures' / ('T_Camera_' + channel + '.png')).resolve()) for channel in CHANNELS}
    assert set(split['texture_files_sha256']) == texture_sources
    for path, digest in split['texture_files_sha256'].items():
        report['source_files'][Path(path).name] = verified_file(path, digest, within=SOURCE / 'Textures')
        assert ue['source_files_sha256'][str(Path(path).resolve())] == digest
    for path, digest in ue['source_files_sha256'].items():
        verified_file(path, digest, within=SOURCE)
    mandatory = {str((SOURCE / 'Camera.blend').resolve()), str((OUT / 'split_report.json').resolve()),
                 str((OUT / 'ue_before_manifest.json').resolve()),
                 str((OUT / 'protected_content_sha256.json').resolve())}
    mandatory.update(str((SOURCE / (name + '.fbx')).resolve()) for name in NAMES)
    mandatory.update(texture_sources)
    assert set(ue['source_files_sha256']) == mandatory

    socket = ue['shutter_socket']
    assert socket['name'] == 'ShutterButton'
    assert close_enough(socket['relative_location_cm'], split['socket_ue_cm'], 1.e-6)
    assert close_enough(socket['relative_rotation_deg'], [0., 0., 0.], 1.e-6)
    assert close_enough(socket['relative_scale'], [1., 1., 1.], 1.e-6)
    assert ue['existing_sockets_preserved']
    assert ue['socket_query_api'] == 'Transient StaticMeshComponent.get_all_socket_names + StaticMesh.find_socket'
    assert len(ue['body_sockets_after']) == len(ue['existing_sockets_before']) + 1
    assert ue['body_sockets_after']['ShutterButton'] == socket
    assert all(ue['body_sockets_after'].get(name) == info
               for name, info in ue['existing_sockets_before'].items())
    assert abs(ue['press_travel_cm'] - split['press_travel_cm']) < 1.e-6
    # The button's local pivot is at its base; the body socket reconstructs the
    # original resting position without changing the body's existing origin.
    assert abs(split['parts'][BUTTON]['bounds_min_m'][2]) < .00002
    report['shutter_socket'] = socket
    report['press_travel_cm'] = split['press_travel_cm']
    assert set(split['renders']) == {'Released','Pressed'}
    report['press_previews'] = {name: verified_file(info['path'], info['sha256'], within=OUT)
                              for name, info in split['renders'].items()}
    assert abs(split['renders']['Released']['button_world_z_m'] -
               split['renders']['Pressed']['button_world_z_m'] - .0012) < 1.e-7
    report['ue_assets'] = ue['assets']
    report['render_triangles_total'] = 45168
    report['completion_evidence'] = 'Exclusive editor exited normally with status 0; fresh report run ID, PID, timestamps and hashes verified.'
    report['ue_completion'] = completion
    report['success'] = True
except Exception:
    report['errors'].append(traceback.format_exc())

(OUT / 'final_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('CAMERA_SHUTTER_FINAL_VERIFIED ' + str(report['success']))
if not report['success']:
    raise RuntimeError('Camera shutter final verification failed; inspect final_verification.json')
