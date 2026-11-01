"""Create the new Notebook UE assets only. Run via run_import.ps1 in a full editor.

The model contract is model_report.json in the parent directory. Animation times
are (Blender frame - frame_start) / fps. No user blueprint or level is edited.
"""
import hashlib
import json
import math
import os
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import unreal

UE = Path(__file__).resolve().parent
OUT = UE.parent
PROJECT = OUT.parents[1]
CONTENT = PROJECT / 'Content'
ROOT = '/Game/Yastars/Mesh/Notebook'
TARGET = CONTENT / 'Yastars' / 'Mesh' / 'Notebook'
FBX_CVAR = 'Interchange.FeatureFlags.Import.FBX'
report = {'success': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
          'run_id': os.environ.get('NOTEBOOK_IMPORT_RUN_ID') or str(uuid.uuid4()),
          'editor_pid': os.getpid(), 'target_root': ROOT, 'created_assets': [],
          'assets': {}, 'materials': {}, 'textures': {}, 'poses': {},
          'actors_spawned': 0, 'map_save_executed': False, 'level_load_executed': False,
          'asset_delete_executed': False, 'asset_or_map_rename_executed': False,
          'imported_cameras': 0, 'imported_lights': 0, 'emissive_connections': 0}
world = None
fbx_before = None


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def checkpoint():
    (UE / 'ue_import_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def src(name):
    path = (OUT / name).resolve()
    assert path.is_relative_to(OUT) and path.is_file(), str(path)
    return path


def protected_files():
    paths = set(CONTENT.rglob('*.umap'))
    for directory in (PROJECT / 'Config', CONTENT / 'Yastar' / 'UI', CONTENT / 'Yastar' / 'Items'):
        paths.update(path for path in directory.rglob('*') if path.is_file())
    return {str(path.resolve()) for path in paths}


def check_protected():
    baseline = json.loads((UE / 'protected_content_sha256.json').read_text(encoding='utf-8-sig'))
    assert set(baseline) == protected_files(), 'Protected file set changed'
    changed = [path for path, digest in baseline.items() if sha(path).lower() != digest.lower()]
    assert not changed, ('Protected files changed', changed)
    return len(baseline)


def close(actual, expected, tolerance=.001):
    return len(actual) == len(expected) and all(abs(float(a)-float(b)) <= tolerance for a, b in zip(actual, expected))


def vec(value):
    return [value.x, value.y, value.z]


def transform(value):
    q = value.rotation
    return {'translation': vec(value.translation), 'rotation': [q.x, q.y, q.z, q.w], 'scale': vec(value.scale3d)}


def new_asset(name, path, cls, factory):
    asset = asset_tools.create_asset(name, path, cls, factory)
    assert asset, (name, path)
    report['created_assets'].append(asset.get_path_name())
    to_save.append(asset)
    return asset


def import_asset(filename, name, path, options=None):
    task = unreal.AssetImportTask()
    for key, value in {'filename': str(filename), 'destination_path': path, 'destination_name': name,
                       'automated': True, 'replace_existing': False, 'save': False}.items():
        task.set_editor_property(key, value)
    if options is not None:
        task.set_editor_property('options', options)
    asset_tools.import_asset_tasks([task])
    result = []
    for object_path in task.get_editor_property('imported_object_paths'):
        assert str(object_path).split('.')[0].startswith(ROOT+'/'), str(object_path)
        asset = edit.load_asset(str(object_path))
        if asset and asset not in result:
            result.append(asset)
            if asset not in to_save:
                to_save.append(asset)
                report['created_assets'].append(asset.get_path_name())
    assert result, ('No imported asset', name)
    return result


def scalar(material, name, default, prop, x, y):
    node = ml.create_material_expression(material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', float(default))
    assert ml.connect_material_property(node, '', prop)


def texture_node(material, parameter, texture, prop, x, y):
    node = ml.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    node.set_editor_property('parameter_name', parameter)
    node.set_editor_property('texture', texture)
    node.set_editor_property('const_coordinate', 0)
    assert ml.connect_material_property(node, 'RGB' if prop == unreal.MaterialProperty.MP_BASE_COLOR else 'R', prop)


def material(name, spec, page=False):
    result = new_asset(name, ROOT+'/Materials', unreal.Material, unreal.MaterialFactoryNew())
    result.set_editor_property('two_sided', bool(spec.get('two_sided', page)))
    color = spec.get('base_color', [1., 1., 1.])
    if spec.get('texture'):
        texture_node(result, 'PageTexture' if page else 'BaseColorTexture', textures[spec['texture']],
                     unreal.MaterialProperty.MP_BASE_COLOR, -500, -170)
    else:
        tint = ml.create_material_expression(result, unreal.MaterialExpressionVectorParameter, -450, -170)
        tint.set_editor_property('parameter_name', 'Tint')
        tint.set_editor_property('default_value', unreal.LinearColor(*color[:3], 1.))
        assert ml.connect_material_property(tint, '', unreal.MaterialProperty.MP_BASE_COLOR)
    if spec.get('roughness_texture'):
        texture_node(result, 'PageRoughnessTexture' if page else 'RoughnessTexture', textures[spec['roughness_texture']],
                     unreal.MaterialProperty.MP_ROUGHNESS, -500, 130)
    else:
        scalar(result, 'Roughness', spec.get('roughness', .8), unreal.MaterialProperty.MP_ROUGHNESS, -400, 130)
    scalar(result, 'Metallic', 0., unreal.MaterialProperty.MP_METALLIC, -400, 280)
    ml.recompile_material(result)
    report['materials'][name] = {'asset': result.get_path_name(), 'source': spec, 'page_parent': page,
                                'two_sided': result.get_editor_property('two_sided'), 'emissive_connected': False}
    return result


def fbx_options(skeletal, skeleton=None, animation_name='A_Notebook_FullCycle'):
    options = unreal.FbxImportUI()
    values = {'import_mesh': skeletal, 'import_as_skeletal': True, 'import_animations': not skeletal,
              'import_materials': False, 'import_textures': False, 'create_physics_asset': False,
              'automated_import_should_detect_type': False,
              'mesh_type_to_import': unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_ANIMATION}
    for key, value in values.items():
        options.set_editor_property(key, value)
    if skeleton:
        options.set_editor_property('skeleton', skeleton)
    data = options.get_editor_property('skeletal_mesh_import_data' if skeletal else 'anim_sequence_import_data')
    # Skeletal FBX carries Blender's meter-to-centimeter unit conversion already.
    # Unlike the earlier static props, a scale of 100 here makes the rig 100x too large.
    data.set_editor_property('import_uniform_scale', 1.)
    if skeletal:
        data.set_editor_property('normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
        data.set_editor_property('update_skeleton_reference_pose', False)
        data.set_editor_property('use_t0_as_ref_pose', False)
        data.set_editor_property('threshold_position', .0000001)
    else:
        data.set_editor_property('animation_length', unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
        data.set_editor_property('use_default_sample_rate', False)
        data.set_editor_property('custom_sample_rate', int(model['fps']))
        data.set_editor_property('remove_redundant_keys', False)
        options.set_editor_property('override_animation_name', animation_name)
    return options


def make_actor_blueprint(name, playing):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', unreal.SkeletalMeshActor)
    bp = new_asset(name, ROOT, unreal.Blueprint, factory)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    cdo = unreal.get_default_object(bp.generated_class())
    component = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
    assert component and component.get_path_name().startswith(ROOT+'/'+name+'.'), component
    component.set_skeletal_mesh_asset(mesh)
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    component.override_animation_data(animation, False, playing, 0., 1.)
    component.set_collision_profile_name('BlockAll')
    component.set_simulate_physics(False)
    component.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    play_data = component.get_editor_property('animation_data')
    assert play_data.get_editor_property('anim_to_play') == animation
    assert play_data.get_editor_property('saved_playing') == playing
    assert not play_data.get_editor_property('saved_looping')
    assert play_data.get_editor_property('saved_position') == 0.
    # Native inherited component overrides live on this generated-class CDO.
    report['assets'][name] = {'asset': bp.get_path_name(), 'component': component.get_path_name(),
                            'mesh': component.get_skeletal_mesh_asset().get_path_name(),
                            'animation': animation.get_path_name(), 'playing': playing, 'looping': False,
                            'position_seconds': 0., 'simulation_enabled': False}
    return bp


try:
    assert Path(unreal.Paths.project_dir()).resolve() == PROJECT
    report['import_script_sha256'] = sha(UE/'import_ue.py')
    edit = unreal.EditorAssetLibrary
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    ml = unreal.MaterialEditingLibrary
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    sk_editor = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    world = editor.get_editor_world()
    report['world_before'] = world.get_path_name() if world else None
    assert world and report['world_before'].startswith('/Engine/Maps/Entry'), 'Exclusive temporary engine world required'
    registry.search_all_assets(True)
    registry.wait_for_completion()
    report['existing_target_packages'] = [str(a.package_name) for a in registry.get_assets_by_path(ROOT, recursive=True)]
    report['existing_target_files'] = [str(p) for p in TARGET.rglob('*') if p.is_file()] if TARGET.exists() else []
    checkpoint()
    assert not report['existing_target_packages'] and not report['existing_target_files'], 'New target required; no overwriting'
    report['protected_files_checked'] = check_protected()
    model = json.loads(src('model_report.json').read_text(encoding='utf-8-sig'))
    assert int(model['fps']) == 30 and int(model['frame_end']) > int(model['frame_start'])
    assert int(model['triangles']) > 0 and len(model['bones']) > 3
    assert model.get('exported_lights', 0) == model.get('exported_cameras', 0) == 0
    slots = model['material_slots']
    assert len(slots) == len(set(slots)) and set(slots) == set(model['materials'])
    page_slots = [name for name in slots if name.startswith('M_Notebook_Page') and name != 'M_Notebook_PageEdges']
    assert len(page_slots) == 32
    source_paths = {src('Notebook.blend'), src('model_report.json'), src('Exports/SK_Notebook.fbx'), src('Exports/A_Notebook_FullCycle.fbx')}
    clips = model.get('clips', [])
    assert len(clips) == 18 and len({clip['name'] for clip in clips}) == 18
    source_paths.update(src(clip['file']) for clip in clips)
    texture_specs = {}
    for spec in model['materials'].values():
        for key in ('texture', 'roughness_texture'):
            if spec.get(key):
                path = src(spec[key])
                source_paths.add(path)
                texture_specs[spec[key]] = key == 'texture'
    report['source_files_sha256'] = {str(path): sha(path) for path in sorted(source_paths)}
    report['source_preflight_passed'] = True
    report['model_contract'] = {'triangles': model['triangles'], 'bones': model['bones'], 'material_slots': slots,
                                'fps': model['fps'], 'frame_start': model['frame_start'], 'frame_end': model['frame_end'],
                                'markers': model['markers']}
    fbx_before = unreal.SystemLibrary.get_console_variable_int_value(FBX_CVAR)
    unreal.SystemLibrary.execute_console_command(world, FBX_CVAR+' 0')
    report['fbx_backend_flag_before'] = fbx_before
    report['fbx_backend_flag_during_import'] = unreal.SystemLibrary.get_console_variable_int_value(FBX_CVAR)
    assert report['fbx_backend_flag_during_import'] == 0
    to_save, textures, slot_materials = [], {}, {}
    used_texture_names = set()
    for filename, srgb in texture_specs.items():
        name = Path(filename).stem
        assert name not in used_texture_names, ('Duplicate texture asset name', name)
        used_texture_names.add(name)
        values = import_asset(src(filename), name, ROOT+'/Textures')
        assert len(values) == 1 and isinstance(values[0], unreal.Texture2D)
        tex = values[0]
        tex.set_editor_property('srgb', srgb)
        if not srgb:
            tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
        textures[filename] = tex
        report['textures'][name] = {'asset': tex.get_path_name(), 'source': filename, 'srgb': srgb}
    for name in slots:
        if name not in page_slots:
            slot_materials[name] = material(name, model['materials'][name])
    page_parent = material('M_Notebook_Page', model['materials'][page_slots[0]], page=True)
    for name in page_slots:
        instance_name = 'MI_'+name[2:]
        instance = new_asset(instance_name, ROOT+'/Materials', unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        ml.set_material_instance_parent(instance, page_parent)
        spec = model['materials'][name]
        ml.set_material_instance_texture_parameter_value(instance, 'PageTexture', textures[spec['texture']])
        assert ml.get_material_instance_texture_parameter_value(instance, 'PageTexture') == textures[spec['texture']]
        if spec.get('roughness_texture'):
            ml.set_material_instance_texture_parameter_value(instance, 'PageRoughnessTexture', textures[spec['roughness_texture']])
            assert ml.get_material_instance_texture_parameter_value(instance, 'PageRoughnessTexture') == textures[spec['roughness_texture']]
        slot_materials[name] = instance
        report['materials'][instance_name] = {'asset': instance.get_path_name(), 'parent': page_parent.get_path_name(),
                                            'PageTexture': textures[spec['texture']].get_path_name(), 'source_slot': name}
    imported = import_asset(src('Exports/SK_Notebook.fbx'), 'SK_Notebook', ROOT, fbx_options(True))
    mesh = next(value for value in imported if isinstance(value, unreal.SkeletalMesh))
    skeleton = mesh.get_editor_property('skeleton')
    assert mesh.get_name() == 'SK_Notebook' and skeleton
    if skeleton not in to_save:
        to_save.append(skeleton)
        report['created_assets'].append(skeleton.get_path_name())
    original_materials = list(mesh.get_editor_property('materials'))
    assert [str(s.material_slot_name) for s in original_materials] == slots
    for slot, source_name in zip(original_materials, slots):
        slot.set_editor_property('material_interface', slot_materials[source_name])
    mesh.set_editor_property('materials', original_materials)
    build = sk_editor.get_lod_build_settings(mesh, 0)
    build.set_editor_property('remove_degenerates', False)
    build.set_editor_property('use_full_precision_u_vs', True)
    build.set_editor_property('threshold_position', .0000001)
    sk_editor.set_lod_build_settings(mesh, 0, build)
    data = unreal.AssetRegistryHelpers.create_asset_data(mesh)
    triangles = int(data.get_tag_value('Triangles'))
    bones_count = int(data.get_tag_value('Bones'))
    assert triangles == model['triangles'], ('Triangle loss', triangles, model['triangles'])
    assert bones_count == len(model['bones']), ('Bone count changed', bones_count, len(model['bones']))
    bounds = mesh.get_bounds()
    dims = [2*v for v in vec(bounds.box_extent)]
    expected_dims = [(b-a)*100 for a, b in zip(model['bounds_min_m'], model['bounds_max_m'])]
    assert close(dims, expected_dims, .02), ('Dimensions changed', dims, expected_dims)
    report['assets']['SK_Notebook'] = {'asset': mesh.get_path_name(), 'skeleton': skeleton.get_path_name(),
                                      'triangles': triangles, 'bones': bones_count, 'dimensions_cm': dims,
                                      'materials': [s.material_interface.get_path_name() for s in mesh.get_editor_property('materials')],
                                      'remove_degenerates': sk_editor.get_lod_build_settings(mesh, 0).get_editor_property('remove_degenerates')}
    values = import_asset(src('Exports/A_Notebook_FullCycle.fbx'), 'A_Notebook_FullCycle', ROOT, fbx_options(False, skeleton))
    animation = next(value for value in values if isinstance(value, unreal.AnimSequence))
    length = animation.get_play_length()
    expected_length = (model['frame_end']-model['frame_start'])/model['fps']
    assert abs(length-expected_length) <= .001, ('Animation length changed', length, expected_length)
    assert animation.get_editor_property('skeleton') == skeleton
    report['assets']['A_Notebook_FullCycle'] = {'asset': animation.get_path_name(), 'seconds': length,
                                             'frames': unreal.AnimationBlueprintLibrary.get_num_frames(animation)}
    evaluation = unreal.AnimPoseEvaluationOptions()
    evaluation.set_editor_property('evaluation_type', unreal.AnimDataEvalType.COMPRESSED)
    evaluation.set_editor_property('optional_skeletal_mesh', mesh)
    sampled = set()
    for label, marker in model['markers'].items():
        frame = marker['frame'] if isinstance(marker, dict) else marker
        time = (int(frame)-model['frame_start'])/model['fps']
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, time, evaluation)
        assert unreal.AnimPoseExtensions.is_valid(pose), label
        names = [str(name) for name in unreal.AnimPoseExtensions.get_bone_names(pose)]
        assert set(names) == set(model['bones']), ('Bone names differ', set(names)^set(model['bones']))
        requested = marker.get('bones', names) if isinstance(marker, dict) else names
        values = {name: transform(unreal.AnimPoseExtensions.get_bone_pose(pose, name, unreal.AnimPoseSpaces.WORLD)) for name in requested}
        assert all(math.isfinite(v) for value in values.values() for group in value.values() for v in group)
        source_locations = model.get('source_marker_bone_locations_cm', {}).get(label, {})
        assert source_locations, ('Source marker bone positions are missing', label)
        for name, expected_location in source_locations.items():
            assert name in values and close(values[name]['translation'], expected_location, .02), (
                'Animation bone position differs from Blender', label, name,
                values.get(name), expected_location)
        report['poses'][label] = {'frame': frame, 'seconds': time, 'bones': values}
        sampled.add(json.dumps({name: transform(unreal.AnimPoseExtensions.get_bone_pose(
            pose, name, unreal.AnimPoseSpaces.WORLD)) for name in names}, sort_keys=True))
    assert len(sampled) >= 3, 'Animation poses do not change'
    report['actual_compressed_bone_poses_verified'] = True
    report['source_marker_bone_locations_verified'] = True
    report['clip_pose_comparisons'] = {}
    for clip in clips:
        name = clip['name']
        imported_clip = import_asset(src(clip['file']), name, ROOT, fbx_options(False, skeleton, name))
        clip_animation = next(value for value in imported_clip if isinstance(value, unreal.AnimSequence))
        assert clip_animation.get_name() == name
        clip_length = clip_animation.get_play_length()
        expected = (clip['frame_end']-clip['frame_start'])/model['fps']
        assert abs(clip_length-expected) <= .001 and abs(clip_length-clip['seconds']) <= .001, name
        assert clip_animation.get_editor_property('skeleton') == skeleton
        comparisons = {}
        for endpoint, time, frame in (('start', 0., clip['frame_start']), ('end', clip_length, clip['frame_end'])):
            clip_pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip_animation, time, evaluation)
            full_time = (frame-model['frame_start'])/model['fps']
            full_pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, full_time, evaluation)
            assert unreal.AnimPoseExtensions.is_valid(clip_pose) and unreal.AnimPoseExtensions.is_valid(full_pose), name
            names = [str(bone) for bone in unreal.AnimPoseExtensions.get_bone_names(clip_pose)]
            assert set(names) == set(model['bones']), name
            maximum_translation_error = 0.
            maximum_rotation_dot_error = 0.
            values = {}
            for bone in names:
                a = transform(unreal.AnimPoseExtensions.get_bone_pose(clip_pose, bone, unreal.AnimPoseSpaces.WORLD))
                b = transform(unreal.AnimPoseExtensions.get_bone_pose(full_pose, bone, unreal.AnimPoseSpaces.WORLD))
                translation_error = max(abs(x-y) for x, y in zip(a['translation'], b['translation']))
                rotation_error = abs(1.-abs(sum(x*y for x, y in zip(a['rotation'], b['rotation']))))
                assert translation_error <= .005 and rotation_error <= .0001 and close(a['scale'], b['scale'], .0001), (name, endpoint, bone, a, b)
                maximum_translation_error = max(maximum_translation_error, translation_error)
                maximum_rotation_dot_error = max(maximum_rotation_dot_error, rotation_error)
                values[bone] = a
            comparisons[endpoint] = {'frame': frame, 'clip_seconds': time, 'full_cycle_seconds': full_time,
                                     'max_translation_error_cm': maximum_translation_error,
                                     'max_rotation_dot_error': maximum_rotation_dot_error, 'bones': values}
        report['assets'][name] = {'asset': clip_animation.get_path_name(), 'seconds': clip_length,
                                  'frames': unreal.AnimationBlueprintLibrary.get_num_frames(clip_animation),
                                  'source_frame_start': clip['frame_start'], 'source_frame_end': clip['frame_end']}
        report['clip_pose_comparisons'][name] = comparisons
    report['independent_clip_count'] = len(clips)
    checkpoint()
    # No factory: the native PhysicsAssetFactory opens an interactive dialog.
    physics = new_asset('PHYS_Notebook', ROOT, unreal.PhysicsAsset, None)
    body = unreal.new_object(unreal.SkeletalBodySetup, outer=physics, name='NotebookRootCollision')
    root_bone = model.get('root_bone', 'root')
    assert root_bone in model['bones']
    body.set_editor_property('bone_name', root_bone)
    body.set_editor_property('physics_type', unreal.PhysicsType.PHYS_TYPE_KINEMATIC)
    lo, hi = model['bounds_min_m'], model['bounds_max_m']
    center = [(a+b)*50 for a, b in zip(lo, hi)]
    center[1] *= -1
    rest = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, 0., evaluation)
    root_transform = unreal.AnimPoseExtensions.get_bone_pose(rest, root_bone, unreal.AnimPoseSpaces.WORLD)
    root_scale = vec(root_transform.scale3d)
    assert min(root_scale) > 0. and max(root_scale)-min(root_scale) < .0001
    box = unreal.KBoxElem()
    box.set_editor_property('center', unreal.MathLibrary.inverse_transform_location(root_transform, unreal.Vector(*center)))
    box.set_editor_property('rotation', unreal.MathLibrary.inverse_transform_rotation(root_transform, unreal.Rotator()))
    for axis, value, scale in zip(('x', 'y', 'z'), expected_dims, root_scale):
        box.set_editor_property(axis, value/scale)
    aggregate = unreal.KAggregateGeom()
    aggregate.set_editor_property('box_elems', [box])
    body.set_editor_property('agg_geom', aggregate)
    physics.set_editor_property('skeletal_body_setups', [body])
    physics.set_editor_property('constraint_setup', [])
    physics.set_editor_property('bounds_bodies', [0])
    mesh.set_editor_property('physics_asset', physics)
    assert sk_editor.is_physics_asset_compatible(mesh, physics)
    report['assets']['PHYS_Notebook'] = {'asset': physics.get_path_name(), 'bodies': 1, 'boxes': 1,
                                        'bone': str(body.get_editor_property('bone_name')), 'dimensions_cm': expected_dims,
                                        'closed_book_proxy': True, 'page_simulation': False}
    make_actor_blueprint('BP_Notebook', False)
    make_actor_blueprint('BP_Notebook_Demo', True)
    report['protected_files_checked_after'] = check_protected()
    report['protected_content_unchanged'] = True
    report['source_files_unchanged'] = all(sha(path) == digest for path, digest in report['source_files_sha256'].items())
    assert report['source_files_unchanged']
    assert len(set(report['created_assets'])) == len(to_save)
    for asset in to_save:
        assert asset.get_path_name().split('.')[0].startswith(ROOT+'/')
        assert edit.save_loaded_asset(asset, False), asset.get_path_name()
    expected = {asset.get_path_name().split('.')[0] for asset in to_save}
    report['new_packages_on_disk'] = {}
    for package in expected:
        path = CONTENT/(package[6:]+'.uasset')
        assert path.is_file(), str(path)
        report['new_packages_on_disk'][package] = {'file': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}
    assert {p.resolve() for p in TARGET.rglob('*.uasset')} == {Path(i['file']).resolve() for i in report['new_packages_on_disk'].values()}
    report['new_package_count'] = len(expected)
    report['same_world_object'] = editor.get_editor_world() == world
    report['world_after'] = editor.get_editor_world().get_path_name()
    assert report['same_world_object']
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()
    unreal.log_error('NOTEBOOK_IMPORT_ERROR '+report['error'])
finally:
    if world is not None and fbx_before is not None:
        unreal.SystemLibrary.execute_console_command(world, FBX_CVAR+' '+str(fbx_before))
        report['fbx_backend_flag_restored'] = unreal.SystemLibrary.get_console_variable_int_value(FBX_CVAR) == fbx_before
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    checkpoint()
    unreal.log('NOTEBOOK_IMPORT_RESULT '+json.dumps({'success': report['success'], 'run_id': report['run_id']}))
