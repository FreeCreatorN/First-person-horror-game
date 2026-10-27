"""Read-only handoff verification for the pen source and its six UE packages."""
import hashlib
import json
import re
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[1]
CONTENT = PROJECT / 'Content'
ROOT = '/Game/Yastars/Mesh/Pen'
CHANNELS = ('BaseColor', 'Roughness', 'Normal', 'Metallic')
EXPECTED_PACKAGES = ({ROOT + '/SM_Pen', ROOT + '/Materials/M_Pen'}
                     | {ROOT + '/Textures/T_Pen_' + channel for channel in CHANNELS})
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
    assert set(model['parts']) == {'SM_Pen'}
    assert set(model['texture_sets']) == {'Pen'}
    assert set(model['materials']) == {'M_Pen'}
    assert model['exported_lights'] == model['exported_cameras'] == 0
    assert validation['success'] and ue['success'], 'Blender or UE validation did not succeed'
    assert completed['normal_zero_exit'] and completed['exit_code'] == 0, completed
    begin, end = utc(completed['started_utc']), utc(completed['completed_utc'])
    assert begin <= end
    assert begin - timedelta(seconds=1) <= utc(ue['started_utc']) <= utc(ue['completed_utc']) <= end + timedelta(seconds=1)
    assert datetime.fromtimestamp((OUT / 'ue_import_report.json').stat().st_mtime, timezone.utc) >= begin
    assert Path(completed['report']).resolve() == OUT / 'ue_import_report.json'
    assert completed['target_root'] == ROOT and ue['target_root'] == ROOT
    assert ue['source_preflight_passed'] and ue['source_files_unchanged']
    assert ue['new_package_count'] == 6 and set(ue['new_packages_on_disk']) == EXPECTED_PACKAGES
    assert len(ue['assets']) == len(ue['materials']) == 1 and len(ue['textures']) == 4
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
        report['package_files'][package] = verified_file(expected, within=CONTENT / 'Yastars' / 'Mesh' / 'Pen')
    current_package_files = {path.resolve() for path in (CONTENT / 'Yastars' / 'Mesh' / 'Pen').rglob('*.uasset')}
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

    part = model['parts']['SM_Pen']
    assert part['collision_hulls'] == 2 and part['uv_channels'] == 1
    geometry = validation['geometry']['SM_Pen']
    uv = validation['uv']['SM_Pen']
    roundtrip = validation['fbx_roundtrip']['SM_Pen']
    assert geometry['non_manifold_edges'] == geometry['loose_vertices'] == 0
    assert geometry['triangles'] == part['triangles'] and len(uv['layers']) >= part.get('uv_channels', 1)
    assert roundtrip['success'] and roundtrip['geometry']['non_manifold_edges'] == 0
    assert roundtrip['ucx_count'] == roundtrip['expected_ucx_count'] == part['collision_hulls']
    assert roundtrip['uv_layers'] >= part.get('uv_channels', 1)
    assert roundtrip['geometry']['triangles'] == geometry['triangles']
    assert max(abs(value) for value in roundtrip['pivot_world_m']) < .00001
    for axis in range(3):
        assert abs(roundtrip['geometry']['dimensions_m'][axis] - geometry['dimensions_m'][axis]) < .00002
    base_name = lambda name: re.sub(r'\.\d{3}$', '', name)
    assert {base_name(name) for name in roundtrip['material_slots']} == set(part['material_slots'])
    fbx = OUT / part['filename']
    assert Path(roundtrip['source']).resolve() == fbx
    report['source_files'] = {'Pen.blend': verified_file(OUT / 'Pen.blend', within=OUT),
                              part['filename']: verified_file(fbx, roundtrip['sha256'], within=OUT)}
    assert ue['source_files_sha256'][str(fbx)] == roundtrip['sha256']
    for path, digest in ue['source_files_sha256'].items():
        verified_file(path, digest, within=OUT)

    assert set(validation['bakes']) == {'T_Pen_' + channel for channel in CHANNELS}
    report['bakes'] = {}
    for channel in CHANNELS:
        name = 'T_Pen_' + channel
        info = validation['bakes'][name]
        path = OUT / model['texture_sets']['Pen'][channel]
        assert Path(info['path']).resolve() == path
        assert info['reloaded_from_saved_png']
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
    material = ue['materials']['M_Pen']
    assert 'Tint' in material['vector_parameters'] and material['Tint'] == [1., 1., 1., 1.]
    assert not material['emissive_connected'] and material['emissive_default'] == [0., 0., 0.]
    assert material['connections'] == {'BaseColor': 'BaseColor.RGB * Tint.RGB', 'Roughness': 'Roughness.R',
                                        'Normal': 'Normal.RGB', 'Metallic': 'Metallic.R'}
    mesh = ue['assets']['SM_Pen']
    assert mesh['dimension_tolerance_cm'] <= .001 and mesh['bounds_tolerance_cm'] <= .001
    assert max(mesh['dimension_error_cm']) <= mesh['dimension_tolerance_cm']
    assert max(mesh['bounds_error_cm']) <= mesh['bounds_tolerance_cm']
    assert mesh['render_triangles_lod0'] == mesh['expected_triangles'] == part['triangles'] == geometry['triangles']
    assert mesh['fbx_import_remove_degenerates'] is False
    assert mesh['lightmap_build_settings']['remove_degenerates'] is False
    assert mesh['convex_collision_hulls'] == mesh['expected_collision_hulls'] == part['collision_hulls']
    assert mesh['uv_channels_lod0'] >= part.get('uv_channels', 1)
    assert {slot['slot_name'] for slot in mesh['matSlots']} == set(part['material_slots'])
    assert 'M_Pen_TungstenBall' in {slot['slot_name'] for slot in mesh['matSlots']}
    assert all(slot['material'] == ROOT + '/Materials/M_Pen.M_Pen' for slot in mesh['matSlots'])
    backup_dir = OUT / 'FailedImportBeforeFix'
    if backup_dir.is_dir():
        previous_failed = read('FailedImportBeforeFix/ue_import_report.json')
        assert not previous_failed['success'] and previous_failed['target_root'] == ROOT
        report['previous_failure_preserved'] = {name: verified_file(backup_dir / name, within=backup_dir)
                                                 for name in ('ue_import_report.json', 'ue_import_completion.json', 'ue_import.log')}
    report['physical_tungsten_ballpoint_preserved'] = {'slot': 'M_Pen_TungstenBall',
                                                      'all_source_triangles_preserved': True,
                                                      'bounds_match_within_cm': mesh['bounds_tolerance_cm']}
    assert validation['renders'], 'No actual render was generated'
    report['renders'] = {}
    for name, info in validation['renders'].items():
        assert info['materials_from_saved_pngs']
        report['renders'][name] = verified_file(info['path'], info['sha256'], within=OUT)
    report['geometry'] = geometry
    report['fbx_roundtrip'] = roundtrip
    report['ue_mesh'] = mesh
    report['ue_material'] = material
    report['ue_completion'] = completed
    report['no_exported_lights_or_cameras'] = True
    report['no_emissive_material_connection'] = True
    report['success'] = True
except Exception:
    report['errors'].append(traceback.format_exc())

(OUT / 'final_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('PEN_FINAL_VERIFIED ' + str(report['success']))
if not report['success']:
    raise RuntimeError('Pen final verification failed; inspect final_verification.json')
