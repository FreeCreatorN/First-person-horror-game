"""Import only the new display freezer and its six planning categories."""

from datetime import datetime, timezone
import gc
from pathlib import Path
import sys
import traceback
from uuid import uuid4

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from freezer_manifest import (
    BLUEPRINT, DESTINATION, GLASS, HERE, MANIFEST, MATERIAL_ROOT, PARENT,
    PROJECT, TARGET, TEXTURE_ROOT, TEXTURES, digest, packages, protected_snapshot,
    read_export, source, verify_protected, write,
)


EDIT = unreal.EditorAssetLibrary
MATERIALS = unreal.MaterialEditingLibrary
FBX_CVAR = 'Interchange.FeatureFlags.Import.FBX'
BASE = 'FreezerBaseColor'
ORM = 'FreezerORM'
PALETTE = {
    'base_color': (BASE, unreal.MaterialSamplerType.SAMPLERTYPE_COLOR, unreal.TextureCompressionSettings.TC_DEFAULT, True),
    'orm': (ORM, unreal.MaterialSamplerType.SAMPLERTYPE_MASKS, unreal.TextureCompressionSettings.TC_MASKS, False),
}
CONNECTIONS = (
    (BASE, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR),
    (ORM, 'R', unreal.MaterialProperty.MP_AMBIENT_OCCLUSION),
    (ORM, 'G', unreal.MaterialProperty.MP_ROUGHNESS),
    (ORM, 'B', unreal.MaterialProperty.MP_METALLIC),
)
GLASS_SCALARS = {unreal.MaterialProperty.MP_OPACITY: ('GlassOpacity', .095),
                 unreal.MaterialProperty.MP_ROUGHNESS: ('GlassRoughness', .105),
                 unreal.MaterialProperty.MP_REFRACTION: ('GlassIOR', 1.025)}


def now():
    return datetime.now(timezone.utc).isoformat()


def checkpoint(report):
    write(HERE / 'ue_import_report.json', report)


def load(path, cls):
    asset = EDIT.load_asset(path)
    assert isinstance(asset, cls), path
    return asset


def run_import(tools, cls, name, folder, path, **extra):
    task = unreal.AssetImportTask()
    settings = dict(filename=str(path), destination_path=folder, destination_name=name,
                    automated=True, replace_existing=False, save=False)
    settings.update(extra)
    for key, value in settings.items():
        task.set_editor_property(key, value)
    tools.import_asset_tasks([task])
    package = folder + '/' + name
    imported = {str(value).split('.')[0] for value in task.get_editor_property('imported_object_paths')}
    assert imported == {package}, (package, imported)
    return load(package, cls)


def make_texture(tools, path, channel):
    texture = run_import(tools, unreal.Texture2D, path.stem, TEXTURE_ROOT, path, factory=unreal.TextureFactory())
    compression, srgb = PALETTE[channel][2:]
    texture.set_editor_property('compression_settings', compression)
    texture.set_editor_property('srgb', srgb)
    return texture


def make_parent(tools, defaults):
    material = tools.create_asset(PARENT, MATERIAL_ROOT, unreal.Material, unreal.MaterialFactoryNew())
    assert material is not None
    nodes = {}
    for index, (channel, (param, sampler, _, _)) in enumerate(PALETTE.items()):
        node = MATERIALS.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D, -480, index*300)
        for key, value in dict(parameter_name=param, texture=defaults[channel], sampler_type=sampler,
                               const_coordinate=0).items():
            node.set_editor_property(key, value)
        nodes[param] = node
    for param, pin, prop in CONNECTIONS:
        assert MATERIALS.connect_material_property(nodes[param], pin, prop), str(prop)
    MATERIALS.recompile_material(material)
    return material


def make_glass(tools):
    material = tools.create_asset(GLASS, MATERIAL_ROOT, unreal.Material, unreal.MaterialFactoryNew())
    assert material is not None
    for key, value in dict(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT,
                           translucency_lighting_mode=unreal.TranslucencyLightingMode.TLM_SURFACE,
                           shading_model=unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
                           refraction_method=unreal.RefractionMode.RM_INDEX_OF_REFRACTION,
                           two_sided=False).items():
        material.set_editor_property(key, value)
    tint = MATERIALS.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -440, -140)
    tint.set_editor_property('parameter_name', 'GlassTint')
    tint.set_editor_property('default_value', unreal.LinearColor(.85, .94, .90, 1.))
    assert MATERIALS.connect_material_property(tint, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
    for i, (prop, (name, value)) in enumerate(GLASS_SCALARS.items()):
        node = MATERIALS.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -440, 50+i*130)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('default_value', value)
        assert MATERIALS.connect_material_property(node, '', prop), str(prop)
    MATERIALS.recompile_material(material)
    return material


def glass_slot(slot):
    if 'glass' in str(slot.material_slot_name).casefold():
        return True
    try:
        return 'glass' in str(slot.get_editor_property('imported_material_slot_name')).casefold()
    except (AttributeError, TypeError):
        return False


def make_mesh(tools, subsystem, name, row, parent, glass):
    options = unreal.FbxImportUI()
    for key, value in dict(import_mesh=True, import_as_skeletal=False, import_materials=False, import_textures=False,
                           automated_import_should_detect_type=False,
                           mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():
        options.set_editor_property(key, value)
    # Blender FBX already carries centimeters. Keep leaf pivot at its origin.
    for key, value in dict(import_uniform_scale=1., combine_meshes=True, auto_generate_collision=False,
                           one_convex_hull_per_ucx=True, generate_lightmap_u_vs=True, remove_degenerates=False,
                           normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
                           transform_vertex_to_absolute=True, bake_pivot_in_vertex=False).items():
        options.static_mesh_import_data.set_editor_property(key, value)
    mesh = run_import(tools, unreal.StaticMesh, name, TARGET, source(row['fbx']), options=options)
    slots = mesh.static_materials
    assert len(slots) == len(row['slots']), [str(slot.material_slot_name) for slot in slots]
    assert sum(glass_slot(slot) for slot in slots) == sum('glass' in slot.casefold() for slot in row['slots'])
    for index, slot in enumerate(slots):
        mesh.set_material(index, glass if glass_slot(slot) else parent)
    mesh.set_editor_property('light_map_coordinate_index', 1)
    mesh.set_editor_property('light_map_resolution', 128 if name.endswith('_Body') else 64)
    settings = subsystem.get_lod_build_settings(mesh, 0)
    for key, value in dict(remove_degenerates=False, use_full_precision_u_vs=True, generate_lightmap_u_vs=True,
                           min_lightmap_resolution=64, src_lightmap_index=0, dst_lightmap_index=1).items():
        settings.set_editor_property(key, value)
    subsystem.set_lod_build_settings(mesh, 0, settings)
    return mesh


def verify_materials(parent, glass):
    assert parent.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_OPAQUE
    assert set(map(str, MATERIALS.get_texture_parameter_names(parent))) == {BASE, ORM}
    for param, selector, prop in CONNECTIONS:
        node = MATERIALS.get_material_property_input_node(parent, prop)
        assert str(node.get_editor_property('parameter_name')) == param
        pin = str(MATERIALS.get_material_property_input_node_output_name(parent, prop))
        assert pin in ({'RGB', '', 'None'} if selector == 'RGB' else {selector})
    assert glass.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_TRANSLUCENT
    assert glass.get_editor_property('translucency_lighting_mode') == unreal.TranslucencyLightingMode.TLM_SURFACE
    for prop, (name, value) in GLASS_SCALARS.items():
        node = MATERIALS.get_material_property_input_node(glass, prop)
        assert str(node.get_editor_property('parameter_name')) == name
        assert abs(node.get_editor_property('default_value')-value) < 1e-5
    for material in (parent, glass):
        assert MATERIALS.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is None
    return {'opaque': parent.get_path_name(), 'glass': glass.get_path_name(),
            'glass_translucent': True, 'glass_opacity': GLASS_SCALARS[unreal.MaterialProperty.MP_OPACITY][1]}


def verify_mesh(mesh, subsystem, row, glass, textures, parent):
    bounds = mesh.get_bounds()
    center, extent = bounds.origin, bounds.box_extent
    low = [center.x - extent.x, center.y - extent.y, center.z - extent.z]
    high = [center.x + extent.x, center.y + extent.y, center.z + extent.z]
    source_min, source_max = row['bounds_min_m'], row['bounds_max_m']
    expected = [source_min[0]*100, -source_max[1]*100, source_min[2]*100,
                source_max[0]*100, -source_min[1]*100, source_max[2]*100]
    assert all(abs(a-b) < .02 for a,b in zip(low + high, expected)), (row['name'], low, high, expected)
    triangles = mesh.get_num_triangles(0)
    hulls = subsystem.get_convex_collision_count(mesh)
    assert triangles == row['triangles'], (row['name'], triangles, row['triangles'])
    assert hulls == row['collision_hulls'], (row['name'], hulls, row['collision_hulls'])
    slots = mesh.static_materials
    assert len(slots) == len(row['slots'])
    assert sum(glass_slot(slot) for slot in slots) == sum('glass' in slot.casefold() for slot in row['slots'])
    assert all(slot.material_interface == (glass if glass_slot(slot) else parent) for slot in slots)
    uv_count = subsystem.get_num_uv_channels(mesh, 0)
    assert uv_count >= 1
    for channel, (param, _, compression, srgb) in PALETTE.items():
        texture = textures[channel]
        assert texture == MATERIALS.get_material_default_texture_parameter_value(parent, param)
        assert texture.get_editor_property('srgb') == srgb and texture.get_editor_property('compression_settings') == compression
    return {'asset': mesh.get_path_name(), 'min_cm': low, 'max_cm': high, 'triangles': triangles,
            'convex_hulls': hulls, 'uv_channels': uv_count,
            'materials': {str(slot.material_slot_name): slot.material_interface.get_path_name() for slot in slots},
            'textures': {channel: tex.get_path_name() for channel,tex in textures.items()}}


def execute(report, allow_live):
    import freezer_blueprint as cabinet_blueprint

    assert Path(unreal.Paths.project_dir()).resolve() == PROJECT.resolve(), 'Wrong project'
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    world = editor.get_editor_world()
    assert world and editor.get_game_world() is None, 'Stop Play in Editor before importing cabinet assets'
    assert allow_live or world.get_path_name().startswith('/Engine/Maps/Entry'), 'Expected temporary Entry world'
    report['world'] = world.get_path_name()
    manifest, rows, expected, input_hashes = read_export()
    report.update(source_hashes=input_hashes, manifest_sha256=input_hashes[MANIFEST.name], doors=manifest['doors'])
    baseline = protected_snapshot()
    assert baseline, 'Project protection baseline missing'
    write(HERE / 'protected_content_sha256.json', baseline)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.wait_for_completion()
    target_registered = sorted(str(item.package_name) for item in registry.get_assets_by_path(TARGET, recursive=True))
    target_files = sorted(str(file) for file in DESTINATION.rglob('*') if file.is_file())
    report.update(protected_files_before=len(baseline), preexisting_packages=target_registered, preexisting_files=target_files)
    checkpoint(report)
    assert not target_registered and not target_files, ('Destination not new', target_registered, target_files)
    previous_backend = unreal.SystemLibrary.get_console_variable_int_value(FBX_CVAR)
    try:
        unreal.SystemLibrary.execute_console_command(world, FBX_CVAR + ' 0')
        assert unreal.SystemLibrary.get_console_variable_int_value(FBX_CVAR) == 0
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        textures = {channel: make_texture(tools, source(relative), channel)
                    for channel, relative in TEXTURES.items()}
        parent = make_parent(tools, textures)
        glass = make_glass(tools)
        meshes = {}
        for name, row in rows.items():
            meshes[name] = make_mesh(tools, mesh_editor, name, row, parent, glass)
            report['imported_meshes'] = sorted(meshes)
            checkpoint(report)
        unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncAssetCompilationFinishAll')
        report['materials'] = verify_materials(parent, glass)
        report['meshes'] = {name: verify_mesh(mesh, mesh_editor, rows[name], glass,
                                             textures, parent) for name,mesh in meshes.items()}
        checkpoint(report)
        bp = cabinet_blueprint.build_blueprint(tools, TARGET, meshes, manifest['doors'], rows)
        assert isinstance(bp, unreal.Blueprint) and bp.get_name() == BLUEPRINT, bp
        report['blueprint'] = cabinet_blueprint.verify_blueprint(bp, meshes, manifest['doors'], rows)
        assert all(digest(source(relative)) == value for relative,value in input_hashes.items()), 'Export data changed'
        assert editor.get_editor_world() == world
        staged = [*textures.values(), parent, glass, *meshes.values(), bp]
        assert {asset.get_path_name().split('.')[0] for asset in staged} == expected
        for asset in staged:
            assert EDIT.save_loaded_asset(asset, False), asset.get_path_name()
            report.setdefault('saved', []).append(asset.get_path_name())
            checkpoint(report)
        actual = packages()
        assert set(actual) == expected
        report['packages'] = actual
        report['protected_files_after'] = verify_protected(baseline)
    finally:
        unreal.SystemLibrary.execute_console_command(world, FBX_CVAR + ' ' + str(previous_backend))
        assert unreal.SystemLibrary.get_console_variable_int_value(FBX_CVAR) == previous_backend


def run(allow_live=False):
    report = dict(success=False, run_id=str(uuid4()), mode='live' if allow_live else 'exclusive',
                  target_root=TARGET, started_utc=now(), imported_meshes=[], saved=[])
    checkpoint(report)
    try:
        execute(report, allow_live)
        report['success'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        unreal.log_error('FREEZER_IMPORT_ERROR ' + report['error'])
    finally:
        report['completed_utc'] = now()
        checkpoint(report)
    unreal.log('FREEZER_IMPORT_VERIFIED ' + str(report['success']))
    gc.collect()
    return report['success']


if __name__ == '__main__':
    run()
