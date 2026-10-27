"""Read-only handoff verification for the camera source and its seven UE packages."""
import hashlib
import json
import re
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[1]
CONTENT = PROJECT / 'Content'
ROOT = '/Game/Yastars/Mesh/Camera'
CHANNELS = ('BaseColor', 'Roughness', 'Normal', 'Metallic')
EXPECTED_PACKAGES = ({ROOT + '/SM_Camera', ROOT + '/Materials/M_Camera_Opaque', ROOT + '/Materials/M_Camera_Glass'}
                     | {ROOT + '/Textures/T_Camera_' + channel for channel in CHANNELS})
report = {'success': False, 'checked_utc': datetime.now(timezone.utc).isoformat(),
          'target_root': ROOT, 'errors': [], 'read_only': True}


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert parsed.tzinfo is not None, value
    return parsed.astimezone(timezone.utc)


def verified_file(path, digest=None, within=None):
    path = Path(path).resolve()
    if within:
        assert path.is_relative_to(Path(within).resolve()), str(path)
    assert path.is_file() and path.stat().st_size > 0, str(path)
    actual = sha(path)
    if digest:
        assert actual.lower() == digest.lower(), ('File differs from validated version', str(path))
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': actual}


try:
    model, validation = read('model_report.json'), read('validation_report.json')
    ue, completed = read('ue_import_report.json'), read('ue_import_completion.json')
    assert set(model['parts']) == {'SM_Camera'}
    assert set(model['texture_sets']) == {'Opaque'}
    assert set(model['materials']) == {'M_Camera_Opaque', 'M_Camera_Glass'}
    assert model['exported_lights'] == model['exported_cameras'] == 0
    assert validation['success'] and ue['success'], 'Blender or UE validation did not succeed'
    mode = completed['execution_mode']
    assert completed['editor_pid'] == ue['editor_pid']
    assert completed['script_sha256'] == ue['import_script_sha256'] == sha(OUT / 'import_ue.py')
    if mode == 'existing_editor_console':
        assert completed['success'] and completed['fresh_console_report_verified']
        assert completed['editor_process_still_running'] and not completed['ue_editor_exit_requested']
        assert completed['normal_zero_exit'] is None and completed['exit_code'] is None
        assert completed['run_id'] == ue['run_id'] and ue['run_id']
        assert completed['report_sha256'] == sha(OUT / 'ue_import_report.json')
        assert completed['script_completed_utc'] == ue['completed_utc']
        assert utc(completed['editor_process_created_utc']) <= utc(completed['started_utc'])
        # A console command completes while the user's editor remains open.
        # It cannot supply evidence of the editor's process exit status.
        report['completion_evidence'] = 'Fresh successful command in the existing editor; editor was left running.'
    else:
        assert mode == 'exclusive_editor', mode
        assert completed['normal_zero_exit'] and completed['exit_code'] == 0, completed
        report['completion_evidence'] = 'Exclusive editor process exited normally with status 0.'
    begin, end = utc(completed['started_utc']), utc(completed['completed_utc'])
    assert begin <= end
    assert begin - timedelta(seconds=1) <= utc(ue['started_utc']) <= utc(ue['completed_utc']) <= end + timedelta(seconds=1)
    assert datetime.fromtimestamp((OUT / 'ue_import_report.json').stat().st_mtime, timezone.utc) >= begin
    assert Path(completed['report']).resolve() == OUT / 'ue_import_report.json'
    assert completed['target_root'] == ROOT and ue['target_root'] == ROOT
    assert ue['source_preflight_passed'] and ue['source_files_unchanged']
    assert ue['fbx_backend_flag_during_import'] == 0 and ue['fbx_backend_flag_restored']
    assert ue['fbx_backend_flag_before'] == ue['fbx_backend_flag_after']
    assert ue['new_package_count'] == 7 and set(ue['new_packages_on_disk']) == EXPECTED_PACKAGES
    assert len(ue['assets']) == 1 and len(ue['materials']) == 2 and len(ue['textures']) == 4
    assert not ue['existing_target_packages']
    assert ue['same_world_object'] and ue['world_before'] == ue['world_after']
    assert not ue['map_save_executed'] and not ue['level_load_executed']
    assert not ue['asset_delete_executed'] and not ue['asset_or_map_rename_executed']
    assert ue['actors_spawned'] == ue['emissive_material_connections_created'] == 0
    assert set(value.split('.')[0] for value in ue['created_assets']) == EXPECTED_PACKAGES

    report['package_files'] = {}
    for package, info in ue['new_packages_on_disk'].items():
        expected = (CONTENT / (package[6:] + '.uasset')).resolve()
        assert Path(info['file']).resolve() == expected
        report['package_files'][package] = verified_file(expected, info['sha256'], within=CONTENT / 'Yastars' / 'Mesh' / 'Camera')
        assert report['package_files'][package]['bytes'] == info['bytes']
    current_package_files = {path.resolve() for path in (CONTENT / 'Yastars' / 'Mesh' / 'Camera').rglob('*.uasset')}
    assert current_package_files == {Path(item['path']) for item in report['package_files'].values()}

    protected = read('protected_content_sha256.json')
    assert isinstance(protected, list) and protected, 'Missing protected-content baseline'
    report['protected_files_checked'] = len(protected)
    report['protected_files_changed'] = [item['path'] for item in protected
                                        if not Path(item['path']).is_file()
                                        or sha(Path(item['path'])).lower() != item['sha256'].lower()]
    assert not report['protected_files_changed'], report['protected_files_changed']
    previous = {Path(item['path']).resolve() for item in protected}
    ui = CONTENT / 'Yastar' / 'UI'
    config = PROJECT / 'Config'
    sets = {'ui': {path.resolve() for path in ui.rglob('*') if path.is_file()},
            'maps': {path.resolve() for path in CONTENT.rglob('*.umap')},
            'config': {path.resolve() for path in config.rglob('*') if path.is_file()}}
    expected_sets = {'ui': {path for path in previous if path.is_relative_to(ui)},
                     'maps': {path for path in previous if path.suffix.lower() == '.umap'},
                     'config': {path for path in previous if path.is_relative_to(config)}}
    report['protected_file_sets'] = {}
    for key in sets:
        additions, missing = sets[key] - expected_sets[key], expected_sets[key] - sets[key]
        report['protected_file_sets'][key] = {'count': len(sets[key]),
                                             'added': sorted(str(path) for path in additions),
                                             'missing': sorted(str(path) for path in missing)}
        assert not additions and not missing, (key, report['protected_file_sets'][key])
    report['ui_maps_and_config_unchanged'] = True

    part = model['parts']['SM_Camera']
    assert part['filename'] == 'SM_Camera.fbx'
    assert part['uv_channels'] == 1 and part['collision_hulls'] >= 1
    assert part['material_slots']['M_Camera_OpticalGlass'] == 'M_Camera_Glass'
    assert all(target == ('M_Camera_Glass' if source == 'M_Camera_OpticalGlass' else 'M_Camera_Opaque')
               for source, target in part['material_slots'].items())
    geometry = validation['geometry']['SM_Camera']
    uv = validation['uv']['SM_Camera']
    roundtrip = validation['fbx_roundtrip']['SM_Camera']
    assert geometry['non_manifold_edges'] == geometry['loose_vertices'] == 0
    assert geometry['triangles'] == part['triangles'] and len(uv['layers']) >= part.get('uv_channels', 1)
    assert roundtrip['success'] and roundtrip['geometry']['non_manifold_edges'] == roundtrip['geometry']['loose_vertices'] == 0
    assert roundtrip['ucx_count'] == roundtrip['expected_ucx_count'] == part['collision_hulls']
    assert roundtrip['uv_layers'] >= part.get('uv_channels', 1)
    assert roundtrip['geometry']['triangles'] == geometry['triangles']
    assert max(abs(value) for value in roundtrip['pivot_world_m']) < .00001
    for key in ('dimensions_m', 'bounds_min_m', 'bounds_max_m'):
        assert len(roundtrip['geometry'][key]) == len(geometry[key]) == 3
        for axis in range(3):
            assert abs(roundtrip['geometry'][key][axis] - geometry[key][axis]) < .00002
    base_name = lambda name: re.sub(r'\.\d{3}$', '', name)
    assert {base_name(name) for name in roundtrip['material_slots']} == set(part['material_slots'])
    fbx = OUT / part['filename']
    assert Path(roundtrip['source']).resolve() == fbx
    report['source_files'] = {'Camera.blend': verified_file(OUT / 'Camera.blend', within=OUT),
                              part['filename']: verified_file(fbx, roundtrip['sha256'], within=OUT)}
    assert Path(validation['blend_file']).resolve() == OUT / 'Camera.blend'
    if validation.get('blend_sha256'):
        assert report['source_files']['Camera.blend']['sha256'] == validation['blend_sha256']
    assert ue['source_files_sha256'][str(fbx)] == roundtrip['sha256']
    assert ue['source_files_sha256'][str(OUT / 'model_report.json')] == sha(OUT / 'model_report.json')
    for path, digest in ue['source_files_sha256'].items():
        verified_file(path, digest, within=OUT)

    assert set(validation['bakes']) == {'T_Camera_' + channel for channel in CHANNELS}
    assert model['texture_sets']['Opaque']['prefix'] == 'T_Camera'
    report['bakes'] = {}
    for channel in CHANNELS:
        name = 'T_Camera_' + channel
        info = validation['bakes'][name]
        path = OUT / model['texture_sets']['Opaque'][channel]
        assert path.name == name + '.png'
        assert Path(info['path']).resolve() == path
        assert info['reloaded_from_saved_png']
        assert info['resolution'] == [2048, 2048], (name, info['resolution'])
        assert info['colorspace'] == ('sRGB' if channel == 'BaseColor' else 'Non-Color')
        report['bakes'][name] = verified_file(path, info['sha256'], within=OUT / 'Textures')
        assert ue['source_files_sha256'][str(path)] == info['sha256']
        texture = ue['textures'][name]
        assert texture['srgb'] == (channel == 'BaseColor')
        if channel == 'Normal':
            assert texture['flip_green_channel']
            assert 'NORMALMAP' in texture['compression_settings']
        elif channel in ('Metallic', 'Roughness'):
            assert 'MASKS' in texture['compression_settings']
    opaque = ue['materials']['M_Camera_Opaque']
    assert opaque['shader_type'] == 'opaque_atlas' and opaque['texture_set'] == 'Opaque'
    assert 'Tint' in opaque['vector_parameters'] and opaque['vector_defaults']['Tint'] == [1., 1., 1., 1.]
    assert not opaque['emissive_connected']
    assert 'BLEND_OPAQUE' in opaque['blend_mode']
    assert opaque['connections'] == {'BaseColor': 'BaseColor.RGB * Tint.RGB', 'Roughness': 'Roughness.R',
                                      'Normal': 'Normal.RGB', 'Metallic': 'Metallic.R'}
    glass = ue['materials']['M_Camera_Glass']
    glass_spec = model['materials']['M_Camera_Glass']
    assert glass_spec['shader_type'] == 'glass'
    for key, expected in {'opacity': .18, 'roughness': .07, 'ior': 1.46}.items():
        assert abs(float(glass_spec[key]) - expected) < 1.e-6, (key, glass_spec)
    assert len(glass_spec['tint']) == 3 and all(abs(float(a) - b) < 1.e-6
                                             for a, b in zip(glass_spec['tint'], [.72, .84, .94]))
    assert glass['shader_type'] == 'glass' and 'BLEND_TRANSLUCENT' in glass['blend_mode']
    assert 'TLM_SURFACE' in glass['translucency_lighting_mode']
    assert 'TLM_SURFACE_PER_PIXEL_LIGHTING' not in glass['translucency_lighting_mode']
    assert 'RM_INDEX_OF_REFRACTION' in glass['refraction_method'] and glass['refraction_connected']
    assert glass['metallic'] == 0. and not glass['emissive_connected']
    assert glass['two_sided'] is False
    assert set(glass['scalar_parameters']) == {'Opacity', 'GlassRoughness', 'IOR'}
    assert 'GlassTint' in glass['vector_parameters']
    assert len(glass['vector_defaults']['GlassTint']) == 4
    assert all(abs(a - b) < 1.e-6 for a, b in zip(glass['vector_defaults']['GlassTint'], [.72, .84, .94, 1.]))
    assert abs(glass['scalar_parameters']['Opacity'] - float(glass_spec.get('opacity', .18))) < 1.e-6
    assert abs(glass['scalar_parameters']['GlassRoughness'] - float(glass_spec.get('roughness', .07))) < 1.e-6
    assert abs(glass['scalar_parameters']['IOR'] - float(glass_spec.get('ior', 1.46))) < 1.e-6
    assert glass['connections'] == {'BaseColor': 'GlassTint.RGB', 'Opacity': 'Opacity', 'Roughness': 'GlassRoughness',
                                     'Refraction': 'IOR', 'Metallic': '0'}
    mesh = ue['assets']['SM_Camera']
    assert mesh['dimension_tolerance_cm'] <= .001 and mesh['bounds_tolerance_cm'] <= .001
    assert max(mesh['dimension_error_cm']) <= mesh['dimension_tolerance_cm']
    assert max(mesh['bounds_error_cm']) <= mesh['bounds_tolerance_cm']
    source_min, source_max = geometry['bounds_min_m'], geometry['bounds_max_m']
    expected_min = [source_min[0] * 100., -source_max[1] * 100., source_min[2] * 100.]
    expected_max = [source_max[0] * 100., -source_min[1] * 100., source_max[2] * 100.]
    for actual, expected in zip(mesh['bounds_min_cm'] + mesh['bounds_max_cm'], expected_min + expected_max):
        assert abs(actual - expected) <= .001
    for actual, expected in zip(mesh['dimensions_cm'], part['dimensions_cm']):
        assert abs(actual - expected) <= .001
    assert mesh['render_triangles_lod0'] == mesh['expected_triangles'] == part['triangles'] == geometry['triangles']
    assert mesh['fbx_import_remove_degenerates'] is False
    assert mesh['lightmap_build_settings']['remove_degenerates'] is False
    assert mesh['lightmap_coordinate_index'] == 1
    assert mesh['lightmap_build_settings']['generate_lightmap_u_vs']
    assert mesh['lightmap_build_settings']['src_lightmap_index'] == 0
    assert mesh['lightmap_build_settings']['dst_lightmap_index'] == 1
    assert mesh['convex_collision_hulls'] == mesh['expected_collision_hulls'] == part['collision_hulls']
    assert mesh['uv_channels_lod0'] >= part.get('uv_channels', 1)
    assert {slot['slot_name'] for slot in mesh['matSlots']} == set(part['material_slots'])
    assert 'M_Camera_OpticalGlass' in {slot['slot_name'] for slot in mesh['matSlots']}
    assert all(slot['material'] == ROOT + '/Materials/' + part['material_slots'][slot['slot_name']] + '.' + part['material_slots'][slot['slot_name']] for slot in mesh['matSlots'])
    separate = validation['separate_materials']['glass']
    assert separate['preserved'] and separate['source_name'] == 'M_Camera_OpticalGlass'
    assert separate['transmission'] == 1. and abs(separate['ior'] - 1.46) < 1.e-6
    assert abs(separate['roughness'] - .07) < 1.e-6 and separate['alpha'] == 1.
    assert separate['emission_strength'] == 0.
    atlas = validation['baked_materials']['SM_Camera']
    assert not atlas['emission_connected'] and atlas['emission_strength'] == 0.
    assert atlas['metallic_texture_connected']
    display_materials = validation['display_materials']['SM_Camera']
    for index, name in atlas['source_opaque_slots'].items():
        assert part['material_slots'][name] == 'M_Camera_Opaque'
        assert display_materials[int(index)] == atlas['name']
    for index, name in atlas['preserved_slots'].items():
        assert name == 'M_Camera_OpticalGlass' and display_materials[int(index)] == name
    assert set(atlas['preserved_slots'].values()) == {'M_Camera_OpticalGlass'}
    assert validation['render_settings']['added_lights'] == 0 and validation['render_settings']['glass_preserved']
    assert validation['renders'], 'No actual render was generated'
    assert all(validation['final_visibility'].values())
    report['renders'] = {}
    for name, info in validation['renders'].items():
        assert info['opaque_material_from_saved_pngs'] and info['glass_preserved']
        report['renders'][name] = verified_file(info['path'], info['sha256'], within=OUT)
    report['geometry'] = geometry
    report['fbx_roundtrip'] = roundtrip
    report['ue_mesh'] = mesh
    report['ue_materials'] = ue['materials']
    report['ue_completion'] = completed
    report['no_exported_lights_or_cameras'] = True
    report['no_emissive_material_connection'] = True
    report['optical_glass_preserved_in_source_previews'] = separate
    report['success'] = True
except Exception:
    report['errors'].append(traceback.format_exc())

(OUT / 'final_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('CAMERA_FINAL_VERIFIED ' + str(report['success']))
if not report['success']:
    raise RuntimeError('Camera final verification failed; inspect final_verification.json')
