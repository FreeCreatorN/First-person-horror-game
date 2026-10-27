"""Read-only verification of PhotoPaper source, reports and six saved UE assets."""
import hashlib
import json
import re
import struct
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[1]
CONTENT = PROJECT / 'Content'
ROOT = '/Game/Yastars/Mesh/PhotoPaper'
TARGET = CONTENT / 'Yastars' / 'Mesh' / 'PhotoPaper'
SLOTS = ['M_PhotoPaper_Frame', 'M_PhotoPaper_Image', 'M_PhotoPaper_Back']
MATERIALS = ['M_PhotoPaper_Frame', 'MI_PhotoPaper_Image', 'M_PhotoPaper_Back']
EXPECTED = {ROOT + '/SM_PhotoPaper', ROOT + '/Textures/T_PhotoPaper_Blank'} | {
    ROOT + '/Materials/' + name for name in SLOTS + ['MI_PhotoPaper_Image']}
report = {'success': False, 'checked_utc': datetime.now(timezone.utc).isoformat(),
          'target_root': ROOT, 'read_only': True, 'errors': []}


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def file(path, digest=None, within=OUT):
    path = Path(path).resolve()
    assert path.is_relative_to(Path(within).resolve()) and path.is_file() and path.stat().st_size > 0, str(path)
    actual = sha(path)
    assert digest is None or actual.lower() == digest.lower(), ('Validated file changed', str(path))
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': actual}


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert result.tzinfo is not None
    return result.astimezone(timezone.utc)


def close(values, expected, tolerance=1.e-6):
    return len(values) == len(expected) and all(abs(float(a) - float(b)) <= tolerance for a, b in zip(values, expected))


try:
    model, validation = read('model_report.json'), read('validation_report.json')
    ue, completed = read('ue_import_report.json'), read('ue_import_completion.json')
    assert validation['success'] and ue['success'] and completed['success']
    assert completed['normal_zero_exit'] and completed['exit_code'] == 0 and completed['execution_mode'] == 'exclusive_editor'
    assert completed['fresh_report_verified'] and completed['material_compile_failure_log_count'] == 0
    begin, end = utc(completed['started_utc']), utc(completed['completed_utc'])
    assert begin <= utc(ue['started_utc']) <= utc(ue['completed_utc']) <= end
    assert end <= datetime.now(timezone.utc) + timedelta(seconds=1)
    assert datetime.fromtimestamp((OUT / 'ue_import_report.json').stat().st_mtime, timezone.utc) >= begin
    assert ue['run_id'] == completed['run_id'] and ue['editor_pid'] == completed['editor_pid']
    assert ue['import_script_sha256'] == completed['script_sha256'] == sha(OUT / 'import_ue.py')
    assert Path(completed['report']).resolve() == OUT / 'ue_import_report.json'
    assert completed['report_sha256'] == sha(OUT / 'ue_import_report.json')
    assert ue['target_root'] == completed['target_root'] == ROOT
    assert ue['source_preflight_passed'] and ue['source_files_unchanged'] and ue['protected_content_unchanged']
    assert not ue['existing_target_packages'] and not ue['existing_target_files']
    assert ue['fbx_backend_flag_during_import'] == 0 and ue['fbx_backend_flag_restored']
    assert ue['same_world_object'] and ue['world_before'] == ue['world_after']
    assert ue['world_before'].startswith('/Engine/Maps/Entry')
    assert not any(ue[key] for key in ('map_save_executed', 'level_load_executed', 'asset_delete_executed', 'asset_or_map_rename_executed'))
    assert ue['actors_spawned'] == ue['imported_lights'] == ue['imported_cameras'] == ue['emissive_material_connections_created'] == 0
    assert model['exported_cameras'] == model['exported_lights'] == 0
    assert ue['new_package_count'] == 6 and set(ue['new_packages_on_disk']) == EXPECTED
    assert len(ue['created_assets']) == 6 and {name.split('.')[0] for name in ue['created_assets']} == EXPECTED
    assert set(ue['assets']) == {'SM_PhotoPaper'} and set(ue['materials']) == set(SLOTS)
    assert set(ue['textures']) == {'T_PhotoPaper_Blank'} and set(ue['material_instances']) == {'MI_PhotoPaper_Image'}
    report['package_files'] = {}
    for package, info in ue['new_packages_on_disk'].items():
        path = (CONTENT / (package[6:] + '.uasset')).resolve()
        assert Path(info['file']).resolve() == path
        report['package_files'][package] = file(path, info['sha256'], TARGET)
    assert {path.resolve() for path in TARGET.rglob('*.uasset')} == {Path(info['path']) for info in report['package_files'].values()}
    assert not list(TARGET.rglob('*.umap'))

    protected = read('protected_content_sha256.json')
    assert isinstance(protected, list) and protected
    report['protected_files_checked'] = len(protected)
    report['protected_files_changed'] = [item['path'] for item in protected
                                         if not Path(item['path']).is_file() or sha(item['path']).lower() != item['sha256'].lower()]
    assert not report['protected_files_changed'], report['protected_files_changed']
    previous = {Path(item['path']).resolve() for item in protected}
    ui, config = CONTENT / 'Yastar' / 'UI', PROJECT / 'Config'
    sets = {'ui': {path.resolve() for path in ui.rglob('*') if path.is_file()},
            'maps': {path.resolve() for path in CONTENT.rglob('*.umap')},
            'config': {path.resolve() for path in config.rglob('*') if path.is_file()}}
    expected_sets = {'ui': {path for path in previous if path.is_relative_to(ui)},
                     'maps': {path for path in previous if path.suffix.lower() == '.umap'},
                     'config': {path for path in previous if path.is_relative_to(config)}}
    report['protected_file_sets'] = {}
    for key in sets:
        added, missing = sets[key] - expected_sets[key], expected_sets[key] - sets[key]
        report['protected_file_sets'][key] = {'count': len(sets[key]), 'added': sorted(map(str, added)), 'missing': sorted(map(str, missing))}
        assert not added and not missing, (key, report['protected_file_sets'][key])
    report['ui_maps_and_config_unchanged'] = True
    assert set(model['parts']) == {'SM_PhotoPaper'} and set(model['materials']) == set(SLOTS)
    part = model['parts']['SM_PhotoPaper']
    assert part['filename'] == 'SM_PhotoPaper.fbx'
    assert part['collision_hulls'] == part['uv_channels'] == 1 and part['non_manifold_edges'] == 0
    assert list(part['material_slots']) == SLOTS and list(part['material_slots'].values()) == MATERIALS
    geometry, roundtrip = validation['geometry']['SM_PhotoPaper'], validation['fbx_roundtrip']['SM_PhotoPaper']
    assert geometry['non_manifold_edges'] == 0 and geometry['triangles'] == part['triangles']
    assert len(validation['uv']['SM_PhotoPaper']['layers']) == 1
    assert roundtrip['success'] and roundtrip['ucx_count'] == roundtrip['uv_layers'] == 1
    assert roundtrip['geometry']['triangles'] == part['triangles'] and roundtrip['geometry']['non_manifold_edges'] == 0
    assert [re.sub(r'\.\d{3}$', '', name) for name in roundtrip['material_slots']] == SLOTS
    assert close(geometry['bounds_min_m'], part['bounds_min_m']) and close(geometry['bounds_max_m'], part['bounds_max_m'])
    assert close(roundtrip['geometry']['dimensions_m'], geometry['dimensions_m'], .00002)
    for value in (model['photo_uv'], validation['photo_uv'], ue['photo_uv']):
        assert value['slot_index'] == 1 and close(value['min'], [0., 0.]) and close(value['max'], [1., 1.])
    report['photo_uv_0_1_verified'] = True
    fbx = OUT / part['filename']
    assert Path(roundtrip['source']).resolve() == fbx
    report['source_files'] = {'PhotoPaper.blend': file(OUT / 'PhotoPaper.blend'), part['filename']: file(fbx, roundtrip['sha256'])}
    assert ue['source_files_sha256'][str(fbx)] == roundtrip['sha256']
    for path, digest in ue['source_files_sha256'].items():
        report['source_files'][str(Path(path).relative_to(OUT))] = file(path, digest)
    texture_spec = model['texture']
    assert texture_spec['name'] == 'T_PhotoPaper_Blank' and texture_spec['filename'] == 'Textures/T_PhotoPaper_Blank.png'
    png = OUT / texture_spec['filename']
    report['blank_texture'] = file(png, texture_spec['sha256'])
    with png.open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', header[16:24]) == (128, 128)
    texture_path = ROOT + '/Textures/T_PhotoPaper_Blank.T_PhotoPaper_Blank'
    assert ue['textures']['T_PhotoPaper_Blank']['asset'] == texture_path
    assert ue['textures']['T_PhotoPaper_Blank']['srgb']
    assert ue['textures']['T_PhotoPaper_Blank']['source_sha256'] == texture_spec['sha256']
    for name, material in ue['materials'].items():
        assert not material['emissive_connected'] and material['metallic'] == 0. and not material['two_sided']
        assert 'BLEND_OPAQUE' in material['blend_mode'] and 'MSM_DEFAULT_LIT' in material['shading_model']
        assert material['vector_parameters'] == ['Tint'] and set(material['scalar_parameters']) == {'Roughness'}
        expected_color = [1., 1., 1.] if name == 'M_PhotoPaper_Image' else model['materials'][name]['base_color']
        assert close(material['Tint'], expected_color + [1.])
        assert abs(material['scalar_parameters']['Roughness'] - model['materials'][name]['roughness']) < 1.e-6
        if name == 'M_PhotoPaper_Image':
            assert material['texture_parameters'] == ['PhotoTexture'] and material['PhotoTexture_default'] == texture_path
            assert material['PhotoTexture_node_class'] == 'MaterialExpressionTextureSampleParameter2D'
            assert 'SAMPLERTYPE_COLOR' in material['PhotoTexture_sampler_type']
            assert material['PhotoTexture_coordinate_index'] == 0
            assert material['PhotoTexture_coordinate_mode'] == 'implicit_const_coordinate'
            assert material['connections']['PhotoTextureCoordinates'] == 'unconnected; ConstCoordinate=0 (UV0)'
            assert material['connections']['BaseColor'] == 'PhotoTexture.RGB * Tint.RGB'
        else:
            assert not material['texture_parameters'] and material['connections']['BaseColor'] == 'Tint.RGB'
    image = ue['material_instances']['MI_PhotoPaper_Image']
    assert image['parent'] == ROOT + '/Materials/M_PhotoPaper_Image.M_PhotoPaper_Image'
    assert image['texture_parameters'] == ['PhotoTexture'] and image['texture_overrides'] == {'PhotoTexture': texture_path}
    assert image['PhotoTexture_effective'] == texture_path and image['runtime_parameter_name'] == 'PhotoTexture'
    assert image['runtime_capture_texture_compatible']
    mesh = ue['assets']['SM_PhotoPaper']
    assert mesh['dimension_tolerance_cm'] == mesh['bounds_tolerance_cm'] == .001
    assert max(mesh['dimension_error_cm']) <= .001 and max(mesh['bounds_error_cm']) <= .001
    assert mesh['render_triangles_lod0'] == mesh['expected_triangles'] == part['triangles']
    assert mesh['convex_collision_hulls'] == mesh['expected_collision_hulls'] == 1
    assert mesh['uv_channels_lod0'] >= 1 and mesh['source_photo_uv0_verified']
    assert mesh['fbx_import_remove_degenerates'] is False and mesh['lightmap_build_settings']['remove_degenerates'] is False
    assert mesh['lightmap_build_settings']['generate_lightmap_u_vs'] is True
    assert mesh['lightmap_build_settings']['src_lightmap_index'] == 0
    assert mesh['lightmap_build_settings']['dst_lightmap_index'] == mesh['lightmap_coordinate_index'] == 1
    assert [slot['index'] for slot in mesh['matSlots']] == [0, 1, 2]
    assert [slot['slot_name'] for slot in mesh['matSlots']] == SLOTS
    assert [slot['material'] for slot in mesh['matSlots']] == [ROOT + '/Materials/' + name + '.' + name for name in MATERIALS]
    assert validation['renders']
    report['renders'] = {name: file(info['path'], info['sha256']) for name, info in validation['renders'].items()}
    log = (OUT / 'ue_import.log').read_text(encoding='utf-8', errors='replace')
    assert not re.search(r'Failed to compile Material[^\r\n]*PhotoPaper|PhotoPaper[^\r\n]*Failed to compile|LogShaderCompilers: Error:', log, re.I)
    report['ue_mesh'], report['ue_materials'], report['ue_material_instance'] = mesh, ue['materials'], image
    report['source_geometry'], report['fbx_roundtrip'], report['ue_completion'] = geometry, roundtrip, completed
    report['no_imported_lights_cameras_or_level_actors'] = True
    report['runtime_photo_texture_parameter_ready'] = True
    report['success'] = True
except Exception:
    report['errors'].append(traceback.format_exc())
finally:
    (OUT / 'final_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('PHOTOPAPER_FINAL_VERIFIED ' + str(report['success']))
if not report['success']:
    raise RuntimeError('PhotoPaper final verification failed; inspect final_verification.json')
