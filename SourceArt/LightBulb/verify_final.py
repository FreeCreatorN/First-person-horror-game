"""Read-only handoff verification for the lightbulb source and its eight UE packages."""
import hashlib
import json
import re
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[1]
CONTENT = PROJECT / 'Content'
ROOT = '/Game/Yastars/Mesh/LightBulb'
CHANNELS = ('BaseColor', 'Roughness', 'Normal', 'Metallic')
EXPECTED_PACKAGES = ({ROOT + '/SM_LightBulb', ROOT + '/Materials/M_LightBulb_Opaque',
                      ROOT + '/Materials/M_LightBulb_Glass', ROOT + '/Materials/M_LightBulb_Filament'}
                     | {ROOT + '/Textures/T_LightBulb_' + channel for channel in CHANNELS})
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
    assert set(model['parts']) == {'SM_LightBulb'}
    assert set(model['texture_sets']) == {'Opaque'}
    assert set(model['materials']) == {'M_LightBulb_Opaque', 'M_LightBulb_Glass', 'M_LightBulb_Filament'}
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
    assert ue['new_package_count'] == 8 and set(ue['new_packages_on_disk']) == EXPECTED_PACKAGES
    assert len(ue['assets']) == 1 and len(ue['materials']) == 3 and len(ue['textures']) == 4
    assert not ue['existing_target_packages']
    assert ue['same_world_object'] and ue['world_before'] == ue['world_after']
    assert not ue['map_save_executed'] and not ue['level_load_executed']
    assert not ue['asset_delete_executed'] and not ue['asset_or_map_rename_executed']
    assert ue['actors_spawned'] == 0 and ue['emissive_material_connections_created'] == 1
    assert set(value.split('.')[0] for value in ue['created_assets']) == EXPECTED_PACKAGES

    report['package_files'] = {}
    for package, info in ue['new_packages_on_disk'].items():
        expected = (CONTENT / (package[6:] + '.uasset')).resolve()
        assert Path(info['file']).resolve() == expected
        report['package_files'][package] = verified_file(expected, within=CONTENT / 'Yastars' / 'Mesh' / 'LightBulb')
    current_package_files = {path.resolve() for path in (CONTENT / 'Yastars' / 'Mesh' / 'LightBulb').rglob('*.uasset')}
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

    part = model['parts']['SM_LightBulb']
    geometry = validation['geometry']['SM_LightBulb']
    uv = validation['uv']['SM_LightBulb']
    roundtrip = validation['fbx_roundtrip']['SM_LightBulb']
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
    report['source_files'] = {'LightBulb.blend': verified_file(OUT / 'LightBulb.blend', within=OUT),
                              part['filename']: verified_file(fbx, roundtrip['sha256'], within=OUT)}
    assert ue['source_files_sha256'][str(fbx)] == roundtrip['sha256']
    for path, digest in ue['source_files_sha256'].items():
        verified_file(path, digest, within=OUT)

    assert set(validation['bakes']) == {'T_LightBulb_' + channel for channel in CHANNELS}
    report['bakes'] = {}
    for channel in CHANNELS:
        name = 'T_LightBulb_' + channel
        info = validation['bakes'][name]
        path = OUT / model['texture_sets']['Opaque'][channel]
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
    opaque = ue['materials']['M_LightBulb_Opaque']
    assert opaque['shader_type'] == 'opaque_atlas' and opaque['texture_set'] == 'Opaque'
    assert 'Tint' in opaque['vector_parameters'] and opaque['vector_defaults']['Tint'] == [1., 1., 1., 1.]
    assert not opaque['emissive_connected']
    assert 'BLEND_OPAQUE' in opaque['blend_mode']
    assert opaque['connections'] == {'BaseColor': 'BaseColor.RGB * Tint.RGB', 'Roughness': 'Roughness.R',
                                      'Normal': 'Normal.RGB', 'Metallic': 'Metallic.R'}
    glass = ue['materials']['M_LightBulb_Glass']
    glass_spec = model['materials']['M_LightBulb_Glass']
    assert glass['shader_type'] == 'glass' and 'BLEND_TRANSLUCENT' in glass['blend_mode']
    assert 'TLM_SURFACE' in glass['translucency_lighting_mode']
    assert 'TLM_SURFACE_PER_PIXEL_LIGHTING' not in glass['translucency_lighting_mode']
    assert 'RM_INDEX_OF_REFRACTION' in glass['refraction_method'] and glass['refraction_connected']
    assert glass['metallic'] == 0. and not glass['emissive_connected']
    assert glass['two_sided'] is False
    assert set(glass['scalar_parameters']) == {'Opacity', 'GlassRoughness', 'IOR'}
    assert 'GlassTint' in glass['vector_parameters']
    assert abs(glass['scalar_parameters']['Opacity'] - float(glass_spec.get('opacity', .10))) < 1.e-6
    assert abs(glass['scalar_parameters']['GlassRoughness'] - float(glass_spec.get('roughness', .08))) < 1.e-6
    assert abs(glass['scalar_parameters']['IOR'] - float(glass_spec.get('ior', 1.45))) < 1.e-6
    assert glass['connections'] == {'BaseColor': 'GlassTint.RGB', 'Opacity': 'Opacity', 'Roughness': 'GlassRoughness',
                                     'Refraction': 'IOR', 'Metallic': '0'}
    filament = ue['materials']['M_LightBulb_Filament']
    assert filament['shader_type'] == 'filament' and 'BLEND_OPAQUE' in filament['blend_mode']
    assert filament['emissive_connected'] and filament['scalar_parameters']['GlowStrength'] == 0.
    assert {'BaseColor', 'EmissiveColor'}.issubset(set(filament['vector_parameters']))
    assert filament['emissive_default_effective'] == [0., 0., 0.]
    assert not filament['use_emissive_for_dynamic_area_lighting']
    assert filament['connections']['EmissiveColor'] == 'EmissiveColor.RGB * GlowStrength'
    mesh = ue['assets']['SM_LightBulb']
    assert max(mesh['dimension_error_cm']) <= mesh['dimension_tolerance_cm']
    assert mesh['convex_collision_hulls'] == mesh['expected_collision_hulls'] == part['collision_hulls']
    assert mesh['uv_channels_lod0'] >= part.get('uv_channels', 1)
    assert {slot['slot_name'] for slot in mesh['matSlots']} == set(part['material_slots'])
    assert all(slot['material'] == ROOT + '/Materials/' + part['material_slots'][slot['slot_name']] + '.' + part['material_slots'][slot['slot_name']] for slot in mesh['matSlots'])
    separate = validation['separate_materials']
    assert separate['glass']['preserved'] and separate['filament']['preserved']
    assert separate['glass']['transmission'] == 1. and abs(separate['glass']['ior'] - 1.45) < 1.e-6
    assert separate['filament']['default_emission_strength'] == 0.
    atlas = validation['baked_materials']['SM_LightBulb']
    assert not atlas['emission_connected'] and atlas['emission_strength'] == 0.
    assert atlas['metallic_texture_connected']
    display_materials = validation['display_materials']['SM_LightBulb']
    for index, name in atlas['source_opaque_slots'].items():
        assert part['material_slots'][name] == 'M_LightBulb_Opaque'
        assert display_materials[int(index)] == atlas['name']
    for index, name in atlas['preserved_slots'].items():
        assert part['material_slots'][name] in {'M_LightBulb_Glass', 'M_LightBulb_Filament'}
        assert display_materials[int(index)] == name
    assert set(atlas['preserved_slots'].values()) == {separate['glass']['source_name'], separate['filament']['source_name']}
    assert validation['renders'], 'No actual render was generated'
    assert {'LightBulb_Preview.png', 'LightBulb_OnPreview.png'}.issubset(validation['renders'])
    report['renders'] = {}
    for name, info in validation['renders'].items():
        assert info['opaque_material_from_saved_pngs'] and info['glass_and_filament_preserved']
        strength = float(info['filament_emission_strength'])
        if name == 'LightBulb_OnPreview.png':
            assert strength > 0., 'On preview was rendered with the filament off'
        else:
            assert strength == 0., 'Default/off preview was rendered with filament emission'
        report['renders'][name] = {**verified_file(info['path'], info['sha256'], within=OUT),
                                   'filament_emission_strength': strength,
                                   'opaque_material_from_saved_pngs': True,
                                   'glass_and_filament_preserved': True}
    assert validation['render_settings']['added_point_lights'] == 0
    assert validation['render_settings']['filament_final_emission_strength'] == 0.
    log_path = OUT / 'ue_import.log'
    log_lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    error_pattern = re.compile(r'failed to compile material|LogMaterial:\s*(?:Error|Warning):.*(?:error|failed)|LogShaderCompilers:\s*Error:', re.I)
    shader_messages = [{'line': index + 1, 'message': line[:1500]}
                       for index, line in enumerate(log_lines) if error_pattern.search(line)]
    report['ue_material_compile_log_audit'] = {'path': str(log_path), 'failure_messages': shader_messages,
                                              'method': 'Read existing completed UE import log; no editor launched',
                                              'material_stats_queried': False}
    assert not shader_messages, shader_messages
    report['separate_materials_preserved_in_source_previews'] = separate
    report['default_and_on_previews_verified'] = True
    report['geometry'] = geometry
    report['fbx_roundtrip'] = roundtrip
    report['ue_mesh'] = mesh
    report['ue_materials'] = ue['materials']
    report['ue_completion'] = completed
    report['no_exported_lights_or_cameras'] = True
    report['filament_glow_is_externally_adjustable_and_off_by_default'] = True
    report['success'] = True
except Exception:
    report['errors'].append(traceback.format_exc())

(OUT / 'final_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('LIGHTBULB_FINAL_VERIFIED ' + str(report['success']))
if not report['success']:
    raise RuntimeError('LightBulb final verification failed; inspect final_verification.json')
