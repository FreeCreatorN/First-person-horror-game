"""Import the flashlight and expose low-intensity, instance-editable lens glow.

Run in the full UE editor with the legacy FBX importer enabled. Existing assets
are inspected without resetting their geometry, slot assignments, or parameters.
"""
import json
import traceback
from pathlib import Path

import unreal


OUT = Path(r'D:\UE\Project\HorrorGame\SourceArt\Flashlight')
ROOT = '/Game/Yastars/Mesh/Flashlight'
MATERIAL_ROOT = ROOT + '/Materials'
LIGHT_COLOR = (.86, .93, 1.0)
LIGHT_STRENGTH = .35
LENS_OPACITY = .14
SPECS = {
    'M_Flashlight_Anodized': ((.026, .036, .045), .8, .31),
    'M_Flashlight_Rubber': ((.013, .016, .020), 0., .74),
    'M_Flashlight_Steel': ((.38, .42, .45), .85, .24),
    'M_Flashlight_Reflector': ((.65, .69, .73), 1., .19),
    'M_Flashlight_Print': ((.64, .67, .62), 0., .55),
    'M_Flashlight_Lens': ((.60, .67, .70), .05, .20),
    'M_Flashlight_LED': ((.7, .72, .63), 0., .28),
}
report = {
    'success': False,
    'created_assets': [],
    'preserved_assets': [],
    'slot_indices': {},
    'instance_paths': {},
    'parameter_readback': {},
}


def color_values(value):
    return [value.r, value.g, value.b, value.a]


try:
    edit = unreal.EditorAssetLibrary
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    ml = unreal.MaterialEditingLibrary
    edit.make_directory(MATERIAL_ROOT)
    assets_to_save = []
    materials = {}
    created_materials = set()
    created_instances = set()

    for name, (color, metallic, roughness) in SPECS.items():
        material = edit.load_asset(MATERIAL_ROOT + '/' + name)
        if material:
            report['preserved_assets'].append(material.get_path_name())
        else:
            material = asset_tools.create_asset(
                name, MATERIAL_ROOT, unreal.Material, unreal.MaterialFactoryNew())
            assert material, name
            created_materials.add(name)
            report['created_assets'].append(material.get_path_name())

            base = ml.create_material_expression(
                material, unreal.MaterialExpressionConstant3Vector, -520, -260)
            base.set_editor_property('constant', unreal.LinearColor(*color, 1.))
            assert ml.connect_material_property(
                base, '', unreal.MaterialProperty.MP_BASE_COLOR)
            for value, prop, y in [
                (metallic, unreal.MaterialProperty.MP_METALLIC, -100),
                (roughness, unreal.MaterialProperty.MP_ROUGHNESS, 30),
            ]:
                node = ml.create_material_expression(
                    material, unreal.MaterialExpressionConstant, -520, y)
                node.set_editor_property('r', value)
                assert ml.connect_material_property(node, '', prop)

            if name in ('M_Flashlight_Lens', 'M_Flashlight_LED'):
                light_color = ml.create_material_expression(
                    material, unreal.MaterialExpressionVectorParameter, -760, 210)
                light_color.set_editor_property('parameter_name', 'LightColor')
                light_color.set_editor_property('default_value', unreal.LinearColor(*LIGHT_COLOR, 1.))
                light_color.set_editor_property('group', 'Light Controls')
                strength = ml.create_material_expression(
                    material, unreal.MaterialExpressionScalarParameter, -760, 390)
                strength.set_editor_property('parameter_name', 'LightStrength')
                strength.set_editor_property('default_value', LIGHT_STRENGTH)
                strength.set_editor_property('group', 'Light Controls')
                multiply = ml.create_material_expression(
                    material, unreal.MaterialExpressionMultiply, -390, 230)
                assert ml.connect_material_expressions(light_color, 'RGB', multiply, 'A')
                assert ml.connect_material_expressions(strength, '', multiply, 'B')
                assert ml.connect_material_property(
                    multiply, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)

            if name == 'M_Flashlight_Lens':
                material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
                material.set_editor_property('two_sided', True)
                # No refraction input: keep the reflector and LED visually stable.
                opacity = ml.create_material_expression(
                    material, unreal.MaterialExpressionScalarParameter, -520, 570)
                opacity.set_editor_property('parameter_name', 'Opacity')
                opacity.set_editor_property('default_value', LENS_OPACITY)
                opacity.set_editor_property('group', 'Lens Controls')
                assert ml.connect_material_property(
                    opacity, '', unreal.MaterialProperty.MP_OPACITY)

            ml.recompile_material(material)
            assets_to_save.append(material)
        materials[name] = material

    bindings = dict(materials)
    for name in ('M_Flashlight_Lens', 'M_Flashlight_LED'):
        instance_name = name.replace('M_', 'MI_', 1)
        instance = edit.load_asset(MATERIAL_ROOT + '/' + instance_name)
        if instance:
            report['preserved_assets'].append(instance.get_path_name())
        else:
            instance = asset_tools.create_asset(
                instance_name, MATERIAL_ROOT, unreal.MaterialInstanceConstant,
                unreal.MaterialInstanceConstantFactoryNew())
            assert instance, instance_name
            ml.set_material_instance_parent(instance, materials[name])
            # UE's setter return value can be false despite a successful update;
            # authoritative checks below read the actual resulting parameters.
            ml.set_material_instance_scalar_parameter_value(
                instance, 'LightStrength', LIGHT_STRENGTH)
            ml.set_material_instance_vector_parameter_value(
                instance, 'LightColor', unreal.LinearColor(*LIGHT_COLOR, 1.))
            if name == 'M_Flashlight_Lens':
                ml.set_material_instance_scalar_parameter_value(instance, 'Opacity', LENS_OPACITY)
            ml.update_material_instance(instance)
            created_instances.add(name)
            report['created_assets'].append(instance.get_path_name())
            assets_to_save.append(instance)
        bindings[name] = instance
        report['instance_paths'][name] = instance.get_path_name()

    mesh = edit.load_asset(ROOT + '/SM_Flashlight')
    mesh_created = not bool(mesh)
    if mesh:
        report['preserved_assets'].append(mesh.get_path_name())
    else:
        assert (OUT / 'SM_Flashlight.fbx').is_file(), 'Missing SM_Flashlight.fbx'
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
        task.filename = str(OUT / 'SM_Flashlight.fbx')
        task.destination_path = ROOT
        task.destination_name = 'SM_Flashlight'
        task.automated = True
        task.replace_existing = False
        task.save = False
        task.options = options
        asset_tools.import_asset_tasks([task])
        mesh = edit.load_asset(ROOT + '/SM_Flashlight')
        assert mesh, 'SM_Flashlight failed to import'
        mesh.set_editor_property('light_map_resolution', 128)
        for index, slot in enumerate(mesh.static_materials):
            name = str(slot.material_slot_name)
            assert name in bindings, ('Unexpected material slot', name)
            mesh.set_material(index, bindings[name])
        report['created_assets'].append(mesh.get_path_name())
        assets_to_save.append(mesh)

    bounds = mesh.get_bounds()
    extent = bounds.box_extent
    dimensions = [extent.x * 2., extent.y * 2., extent.z * 2.]
    report['mesh'] = mesh.get_path_name()
    report['dimensions_cm'] = dimensions
    report['forward_axis'] = '+X'
    assert 18.5 < dimensions[0] < 20.5, ('Unexpected flashlight length', dimensions)
    body = mesh.get_editor_property('body_setup')
    assert body, 'Missing collision body setup'
    aggregate = body.get_editor_property('agg_geom')
    hull_count = len(aggregate.get_editor_property('convex_elems'))
    report['convex_collision_hulls'] = hull_count
    assert hull_count == 3, ('Expected 3 imported UCX hulls', hull_count)
    report['materials'] = []
    for index, slot in enumerate(mesh.static_materials):
        name = str(slot.material_slot_name)
        report['slot_indices'][name] = index
        report['materials'].append({
            'index': index,
            'slot_name': name,
            'material': slot.material_interface.get_path_name() if slot.material_interface else None,
        })
    assert set(SPECS).issubset(report['slot_indices']), report['slot_indices']

    for name in ('M_Flashlight_Lens', 'M_Flashlight_LED'):
        material = materials[name]
        instance = bindings[name]
        scalars = [str(x) for x in ml.get_scalar_parameter_names(instance)]
        vectors = [str(x) for x in ml.get_vector_parameter_names(instance)]
        assert 'LightStrength' in scalars and 'LightColor' in vectors, (name, scalars, vectors)
        editable_samples = []
        if name in created_instances:
            # Check actual external edits, then restore the intended soft glow.
            # Preserved instances are never changed by this validation.
            try:
                for test_value in (0., .8):
                    ml.set_material_instance_scalar_parameter_value(instance, 'LightStrength', test_value)
                    ml.update_material_instance(instance)
                    readback = ml.get_material_instance_scalar_parameter_value(instance, 'LightStrength')
                    editable_samples.append({'requested': test_value, 'readback': readback})
                    assert abs(readback - test_value) < .00001, (name, editable_samples)
            finally:
                ml.set_material_instance_scalar_parameter_value(instance, 'LightStrength', LIGHT_STRENGTH)
                ml.update_material_instance(instance)
        values = {
            'scalar_parameter_names': scalars,
            'vector_parameter_names': vectors,
            'master_LightStrength': ml.get_material_default_scalar_parameter_value(material, 'LightStrength'),
            'master_LightColor': color_values(ml.get_material_default_vector_parameter_value(material, 'LightColor')),
            'instance_LightStrength': ml.get_material_instance_scalar_parameter_value(instance, 'LightStrength'),
            'instance_LightColor': color_values(ml.get_material_instance_vector_parameter_value(instance, 'LightColor')),
            'external_edit_samples': editable_samples,
        }
        if name == 'M_Flashlight_Lens':
            assert 'Opacity' in scalars, scalars
            assert material.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_TRANSLUCENT
            values['master_Opacity'] = ml.get_material_default_scalar_parameter_value(material, 'Opacity')
            values['instance_Opacity'] = ml.get_material_instance_scalar_parameter_value(instance, 'Opacity')
            if name in created_instances:
                assert abs(values['instance_Opacity'] - LENS_OPACITY) < .00001, values
        if name in created_materials:
            assert abs(values['master_LightStrength'] - LIGHT_STRENGTH) < .00001, values
        if name in created_instances:
            assert abs(values['instance_LightStrength'] - LIGHT_STRENGTH) < .00001, values
        if mesh_created:
            slot_index = report['slot_indices'][name]
            assert mesh.static_materials[slot_index].material_interface == instance, name
        report['parameter_readback'][name] = values

    for asset in assets_to_save:
        assert edit.save_loaded_asset(asset, False), asset.get_path_name()
    report['runtime_control'] = {
        'scalar_parameter': 'LightStrength',
        'default': LIGHT_STRENGTH,
        'off': 0.,
        'color_parameter': 'LightColor',
        'note': 'Create a Dynamic Material Instance for both recorded Lens/LED slots and set LightStrength on both. No light Actor or Blueprint is created.',
    }
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()

(OUT / 'ue_import_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('FLASHLIGHT_IMPORT ' + json.dumps(report))
