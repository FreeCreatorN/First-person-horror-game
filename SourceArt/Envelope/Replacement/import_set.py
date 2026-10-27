"""Import the replacement envelope set, then remove exactly five backed-up old packages.

Requires full UE, exclusive parent execution and a successful inspect_legacy.py
report. No directory deletion, map load/save, asset rename or scene placement.
"""
import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

import unreal

PROJECT = Path(r'D:\UE\Project\HorrorGame')
CONTENT = (PROJECT / 'Content').resolve()
OUT = (PROJECT / 'SourceArt' / 'Envelope' / 'Replacement').resolve()
ROOT = '/Game/Yastars/Mesh/Envelope'
BACKUP = (PROJECT / 'Saved' / 'CodexBackups' / 'EnvelopeBeforeReplacement_20261020').resolve()
LEGACY = (
    ROOT + '/SM_Envelope',
    ROOT + '/Materials/M_Envelope',
    ROOT + '/Textures/T_Envelope_BaseColor',
    ROOT + '/Textures/T_Envelope_Roughness',
    ROOT + '/Textures/T_Envelope_Normal',
)
LEGACY_SET = set(LEGACY)
MESH_NAMES = {'SM_Envelope_Closed', 'SM_Envelope_Open', 'SM_LetterPaper'}
MATERIAL_NAMES = {'M_EnvelopeClosed', 'M_EnvelopeOpen', 'M_LetterPaper'}
TEXTURE_PREFIXES = {'Closed': 'T_EnvelopeClosed', 'Open': 'T_EnvelopeOpen', 'LetterPaper': 'T_LetterPaper'}
CHANNELS = ('BaseColor', 'Roughness', 'Normal')
report = {'success': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
          'assets': {}, 'materials': {}, 'textures': {},
          'created_assets': [], 'preserved_assets': [], 'deleted_legacy': [],
          'legacy_external_referencers_before_delete': {}, 'legacy_deletion_checks': [],
          'new_packages_on_disk': {}, 'warnings': [], 'asset_or_map_rename_executed': False,
          'map_save_executed': False, 'level_load_executed': False, 'actors_spawned': 0}


def checkpoint():
    (OUT / 'ue_import_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def package_file(package):
    assert package.startswith(ROOT + '/'), package
    path = (CONTENT / (package[6:] + '.uasset')).resolve()
    assert path.is_relative_to(CONTENT / 'Yastars' / 'Mesh' / 'Envelope'), str(path)
    return path


def source_file(filename):
    path = (OUT / filename).resolve()
    assert path.is_relative_to(OUT) and path.is_file(), str(path)
    return path


def legacy_backup_check(package, inspection):
    assert package in LEGACY_SET, package
    source = package_file(package)
    assert source.is_file(), 'Missing legacy package before its authorized deletion: ' + package
    expected_backup = (BACKUP / 'Content' / source.relative_to(CONTENT)).resolve()
    item = inspection['assets'][package]
    assert Path(item['source_file']).resolve() == source, package
    assert Path(item['backup_file']).resolve() == expected_backup, package
    assert expected_backup.is_relative_to(BACKUP) and expected_backup.is_file(), str(expected_backup)
    recorded_hash = item['source_sha256']
    assert recorded_hash == item['backup_sha256'], package
    assert sha256(source) == recorded_hash, 'Legacy source changed after inspection: ' + package
    assert sha256(expected_backup) == recorded_hash, 'Backup changed or incomplete: ' + package
    for suffix in ('.uexp', '.ubulk', '.uptnl'):
        assert not source.with_suffix(suffix).exists(), 'Unexpected package sidecar: ' + str(source.with_suffix(suffix))
    return {'package': package, 'source_file': str(source), 'backup_file': str(expected_backup),
            'verified_sha256': recorded_hash}


def normalized_refs(values):
    return sorted(set(str(value).split('.')[0] for value in (values or [])))


def current_references(package, registry, options):
    registry_refs = normalized_refs(registry.get_referencers(package, options))
    library_refs = normalized_refs(unreal.EditorAssetLibrary.find_package_referencers_for_asset(package, False))
    all_refs = sorted(set(registry_refs) | set(library_refs))
    return {'registry': registry_refs, 'editor_asset_library': library_refs,
            'external': [ref for ref in all_refs if ref not in LEGACY_SET and ref != package],
            'internal_legacy': [ref for ref in all_refs if ref in LEGACY_SET]}


try:
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    sm_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    assert editor and sm_editor, 'Use the full UE editor, not a Python commandlet'
    world_before = editor.get_editor_world()
    report['world_before'] = world_before.get_path_name() if world_before else None
    edit = unreal.EditorAssetLibrary
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    ml = unreal.MaterialEditingLibrary
    inspection = json.loads((OUT / 'legacy_inspection_report.json').read_text(encoding='utf-8-sig'))
    assert inspection['success'] and inspection['deletion_gate_passed'], 'Legacy inspection found external references or failed'
    assert set(inspection['legacy_packages']) == LEGACY_SET and inspection['backed_up_package_files'] == 5
    report['legacy_backup_preflight'] = [legacy_backup_check(package, inspection) for package in LEGACY]
    model = json.loads((OUT / 'model_report.json').read_text(encoding='utf-8-sig'))
    parts, material_specs, texture_sets = model['parts'], model['materials'], model['texture_sets']
    assert set(parts) == MESH_NAMES, list(parts)
    assert set(material_specs) == MATERIAL_NAMES, list(material_specs)
    assert set(texture_sets) == set(TEXTURE_PREFIXES), list(texture_sets)
    for key, spec in texture_sets.items():
        assert spec['prefix'] == TEXTURE_PREFIXES[key], (key, spec)
        for channel in CHANNELS:
            assert Path(spec[channel]).name == spec['prefix'] + '_' + channel + '.png', spec[channel]
            source_file(spec[channel])
    for name, spec in material_specs.items():
        assert spec['texture_set'] in texture_sets, (name, spec)
    for name, spec in parts.items():
        assert spec['filename'] == name + '.fbx', spec['filename']
        source_file(spec['filename'])
        assert isinstance(spec['collision_hulls'], int) and spec['collision_hulls'] >= 1, (name, spec)
        assert len(spec['dimensions_cm']) == 3 and all(float(v) > 0 for v in spec['dimensions_cm']), (name, spec)
        assert spec['material_slots'] and set(spec['material_slots'].values()).issubset(MATERIAL_NAMES), (name, spec)
    checkpoint()
    edit.make_directory(ROOT + '/Textures')
    edit.make_directory(ROOT + '/Materials')
    to_save, textures, materials = [], {}, {}
    expected_new_packages = set()

    for set_name, spec in texture_sets.items():
        textures[set_name] = {}
        for channel in CHANNELS:
            name = spec['prefix'] + '_' + channel
            package = ROOT + '/Textures/' + name
            expected_new_packages.add(package)
            texture = edit.load_asset(package)
            created = not bool(texture)
            if created:
                task = unreal.AssetImportTask()
                for key, value in {'filename': str(source_file(spec[channel])), 'destination_path': ROOT + '/Textures',
                                   'destination_name': name, 'automated': True, 'replace_existing': False,
                                   'save': False, 'factory': unreal.TextureFactory()}.items():
                    task.set_editor_property(key, value)
                asset_tools.import_asset_tasks([task])
                texture = edit.load_asset(package)
                assert texture and isinstance(texture, unreal.Texture2D), package
                texture.set_editor_property('srgb', channel == 'BaseColor')
                texture.set_editor_property('compression_settings', {
                    'BaseColor': unreal.TextureCompressionSettings.TC_DEFAULT,
                    'Roughness': unreal.TextureCompressionSettings.TC_MASKS,
                    'Normal': unreal.TextureCompressionSettings.TC_NORMALMAP,
                }[channel])
                if channel == 'Normal':
                    texture.set_editor_property('flip_green_channel', True)
                to_save.append(texture)
            assert isinstance(texture, unreal.Texture2D), package
            report['created_assets' if created else 'preserved_assets'].append(texture.get_path_name())
            textures[set_name][channel] = texture
            info = {'asset': texture.get_path_name(), 'source': str(source_file(spec[channel])), 'created': created,
                    'srgb': texture.get_editor_property('srgb'),
                    'compression_settings': str(texture.get_editor_property('compression_settings'))}
            if channel == 'Normal':
                info['flip_green_channel'] = texture.get_editor_property('flip_green_channel')
            report['textures'][name] = info

    for name, spec in material_specs.items():
        package = ROOT + '/Materials/' + name
        expected_new_packages.add(package)
        material = edit.load_asset(package)
        created = not bool(material)
        image_set = textures[spec['texture_set']]
        if created:
            material = asset_tools.create_asset(name, ROOT + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
            assert material, package
            samples = {}
            for channel, y in (('BaseColor', -180), ('Roughness', 100), ('Normal', 370)):
                node = ml.create_material_expression(material, unreal.MaterialExpressionTextureSample, -750, y)
                node.set_editor_property('texture', image_set[channel])
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
            to_save.append(material)
        assert isinstance(material, unreal.Material), package
        report['created_assets' if created else 'preserved_assets'].append(material.get_path_name())
        materials[name] = material
        parameters = [str(value) for value in ml.get_vector_parameter_names(material)]
        info = {'asset': material.get_path_name(), 'texture_set': spec['texture_set'], 'created': created,
                'textures': {key: value.get_path_name() for key, value in image_set.items()},
                'vector_parameters': parameters}
        if 'Tint' in parameters:
            value = ml.get_material_default_vector_parameter_value(material, 'Tint')
            info['Tint'] = [value.r, value.g, value.b, value.a]
        if created:
            assert info.get('Tint') == [1., 1., 1., 1.], info
        report['materials'][name] = info

    for name, spec in parts.items():
        package = ROOT + '/' + name
        expected_new_packages.add(package)
        mesh = edit.load_asset(package)
        created = not bool(mesh)
        if created:
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
            for key, value in {'filename': str(source_file(spec['filename'])), 'destination_path': ROOT,
                               'destination_name': name, 'automated': True, 'replace_existing': False,
                               'save': False, 'options': options}.items():
                task.set_editor_property(key, value)
            asset_tools.import_asset_tasks([task])
            mesh = edit.load_asset(package)
            assert mesh and isinstance(mesh, unreal.StaticMesh), package
            for index, slot in enumerate(mesh.static_materials):
                slot_name = str(slot.material_slot_name)
                assert slot_name in spec['material_slots'], (name, slot_name)
                mesh.set_material(index, materials[spec['material_slots'][slot_name]])
            mesh.set_editor_property('light_map_resolution', 128)
            settings = sm_editor.get_lod_build_settings(mesh, 0)
            settings.set_editor_property('generate_lightmap_u_vs', True)
            settings.set_editor_property('src_lightmap_index', 0)
            settings.set_editor_property('dst_lightmap_index', 1)
            sm_editor.set_lod_build_settings(mesh, 0, settings)
            mesh.set_editor_property('light_map_coordinate_index', 1)
            to_save.append(mesh)
        assert isinstance(mesh, unreal.StaticMesh), package
        report['created_assets' if created else 'preserved_assets'].append(mesh.get_path_name())
        bounds = mesh.get_bounds()
        extent, origin = bounds.box_extent, bounds.origin
        actual_dimensions = [extent.x * 2., extent.y * 2., extent.z * 2.]
        differences = [abs(actual - float(expected)) for actual, expected in zip(actual_dimensions, spec['dimensions_cm'])]
        hulls = sm_editor.get_convex_collision_count(mesh)
        uv_count = sm_editor.get_num_uv_channels(mesh, 0)
        settings = sm_editor.get_lod_build_settings(mesh, 0)
        slots = [{'index': index, 'slot_name': str(slot.material_slot_name),
                  'material': slot.material_interface.get_path_name() if slot.material_interface else None}
                 for index, slot in enumerate(mesh.static_materials)]
        info = {'asset': mesh.get_path_name(), 'created': created,
                'dimensions_cm': actual_dimensions, 'expected_dimensions_cm': spec['dimensions_cm'],
                'dimension_error_cm': differences, 'dimension_tolerance_cm': .05,
                'bounds_origin_cm': [origin.x, origin.y, origin.z],
                'convex_collision_hulls': hulls, 'expected_collision_hulls': spec['collision_hulls'],
                'uv_channels_lod0': uv_count, 'source_uv_channels_expected': spec.get('uv_channels', 1),
                'matSlots': slots, 'lightmap_coordinate_index': mesh.get_editor_property('light_map_coordinate_index'),
                'lightmap_build_settings': {
                    'generate_lightmap_u_vs': settings.get_editor_property('generate_lightmap_u_vs'),
                    'src_lightmap_index': settings.get_editor_property('src_lightmap_index'),
                    'dst_lightmap_index': settings.get_editor_property('dst_lightmap_index'),
                    'generated_render_data_uv1_separately_verified': False}}
        report['assets'][name] = info
        assert max(differences) <= .05, (name, info)
        assert hulls == spec['collision_hulls'] and hulls >= 1, (name, info)
        assert uv_count >= 1 and slots and all(slot['material'] for slot in slots), (name, info)
        if created:
            assert set(slot['slot_name'] for slot in slots) == set(spec['material_slots']), (name, info)
            assert all(slot['material'] == materials[spec['material_slots'][slot['slot_name']]].get_path_name() for slot in slots), (name, info)
    assert len(expected_new_packages) == 15 and not (expected_new_packages & LEGACY_SET)
    for asset in to_save:
        assert edit.save_loaded_asset(asset, False), asset.get_path_name()
    for package in sorted(expected_new_packages):
        path = package_file(package)
        assert path.is_file() and path.stat().st_size > 0 and edit.does_asset_exist(package), package
        report['new_packages_on_disk'][package] = {'file': str(path), 'bytes': path.stat().st_size}
    report['new_package_count'] = len(report['new_packages_on_disk'])
    report['replacement_assets_saved_and_verified'] = True
    checkpoint()

    # All old packages are checked together before the first deletion. New
    # packages or maps referring to an old resource therefore block all removal.
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    registry.wait_for_completion()
    registry.scan_files_synchronous([str(package_file(package)) for package in LEGACY], True)
    assert not registry.is_loading_assets(), 'Reference discovery did not finish; legacy deletion is blocked'
    options = unreal.AssetRegistryDependencyOptions()
    for flag in ('include_hard_package_references', 'include_soft_package_references',
                 'include_searchable_names', 'include_hard_management_references',
                 'include_soft_management_references'):
        options.set_editor_property(flag, True)
    report['optional_reference_options_unsupported'] = {}
    for flag in ('include_game_package_references', 'include_editor_only_package_references'):
        try:
            options.set_editor_property(flag, True)
        except Exception as error:
            report['optional_reference_options_unsupported'][flag] = str(error)
    for package in LEGACY:
        legacy_backup_check(package, inspection)
        refs = current_references(package, registry, options)
        report['legacy_external_referencers_before_delete'][package] = refs
    checkpoint()
    assert all(not refs['external'] for refs in report['legacy_external_referencers_before_delete'].values()), 'STOP: an external asset still references a legacy envelope package'

    # User-authorized exact-package order: old mesh, old material, three maps.
    # UE's delete_asset is Force Delete; it is invoked only after this explicit
    # allowlist, verified backup, and fresh external-reference gate all pass.
    for package in LEGACY:
        check = legacy_backup_check(package, inspection)
        refs = current_references(package, registry, options)
        check['referencers_immediately_before_delete'] = refs
        report['legacy_deletion_checks'].append(check)
        checkpoint()
        assert not refs['external'], ('STOP: external referencer appeared', package, refs)
        assert package in LEGACY_SET and package not in expected_new_packages
        assert edit.delete_asset(package), 'Could not delete the exact old package: ' + package
        report['deleted_legacy'].append(package)
        assert not package_file(package).exists(), 'Old package file remains: ' + package
        checkpoint()

    report['legacy_files_absent'] = {package: not package_file(package).exists() for package in LEGACY}
    assert all(report['legacy_files_absent'].values()) and set(report['deleted_legacy']) == LEGACY_SET
    assert all(package_file(package).is_file() and edit.does_asset_exist(package) for package in expected_new_packages)
    world_after = editor.get_editor_world()
    report['world_after'] = world_after.get_path_name() if world_after else None
    report['same_world_object'] = world_before == world_after
    assert report['same_world_object'] and report['world_before'] == report['world_after']
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()

report['completed_utc'] = datetime.now(timezone.utc).isoformat()
checkpoint()
unreal.log('ENVELOPE_REPLACEMENT_IMPORT ' + json.dumps(report))
