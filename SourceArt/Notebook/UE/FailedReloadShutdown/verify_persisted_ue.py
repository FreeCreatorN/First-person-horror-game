"""Read back saved Notebook assets in a fresh editor, without saving anything."""
import hashlib
import json
import math
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

import unreal

UE = Path(__file__).resolve().parent
OUT = UE.parent
PROJECT = OUT.parents[1]
ROOT = '/Game/Yastars/Mesh/Notebook'
result = {'success': False, 'started_utc': datetime.now(timezone.utc).isoformat(),
          'editor_pid': os.getpid(), 'read_only': True, 'assets_saved': 0,
          'actors_spawned': 0, 'poses': {}, 'blueprints': {}, 'clips': {}}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def transform(value):
    q = value.rotation
    return {'translation': [value.translation.x, value.translation.y, value.translation.z],
            'rotation': [q.x, q.y, q.z, q.w], 'scale': [value.scale3d.x, value.scale3d.y, value.scale3d.z]}


def near(a, b, tolerance):
    return len(a) == len(b) and all(abs(x-y) <= tolerance for x, y in zip(a, b))


try:
    unreal.load_module('AnimationBlueprintLibrary')
    unreal.load_module('BlueprintEditorLibrary')
    unreal.load_module('SubobjectDataInterface')
    report_path = UE/'ue_import_report.json'
    main = json.loads(report_path.read_text(encoding='utf-8-sig'))
    assert main['success'] and main['editor_pid'] != os.getpid(), 'A fresh editor process is required'
    result['import_report_sha256'] = sha(report_path)
    result['script_sha256'] = sha(UE/'verify_persisted_ue.py')
    assert Path(unreal.Paths.project_dir()).resolve() == PROJECT
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert world and world.get_path_name().startswith('/Engine/Maps/Entry')
    result['world'] = world.get_path_name()
    for package, info in main['new_packages_on_disk'].items():
        assert sha(info['file']) == info['sha256'], package
    model = json.loads((OUT/'model_report.json').read_text(encoding='utf-8-sig'))
    load = unreal.EditorAssetLibrary.load_asset
    mesh = load(ROOT+'/SK_Notebook')
    animation = load(ROOT+'/A_Notebook_FullCycle')
    unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
    assert isinstance(mesh, unreal.SkeletalMesh) and isinstance(animation, unreal.AnimSequence)
    assert mesh.get_editor_property('skeleton') == animation.get_editor_property('skeleton')
    data = unreal.AssetRegistryHelpers.create_asset_data(mesh)
    assert int(data.get_tag_value('Triangles')) == model['triangles']
    assert int(data.get_tag_value('Bones')) == len(model['bones'])
    assert [slot.material_interface.get_path_name() for slot in mesh.get_editor_property('materials')] == main['assets']['SK_Notebook']['materials']
    bounds = mesh.get_bounds()
    extended_dims = [v*2 for v in (bounds.box_extent.x,bounds.box_extent.y,bounds.box_extent.z)]
    assert near(extended_dims,main['assets']['SK_Notebook']['extended_dimensions_cm'],.001)
    positive = mesh.get_editor_property('positive_bounds_extension')
    negative = mesh.get_editor_property('negative_bounds_extension')
    assert near([positive.x,positive.y,positive.z],[0.,0.,16.],.001)
    assert near([negative.x,negative.y,negative.z],[15.,0.,0.],.001)
    result['mesh_geometry_and_materials_persisted'] = True
    for name, playing in (('BP_Notebook',False),('BP_Notebook_Demo',True)):
        bp = load(ROOT+'/'+name)
        assert isinstance(bp, unreal.Blueprint)
        cdo = unreal.get_default_object(bp.generated_class())
        comp = cdo.get_component_by_class(unreal.SkeletalMeshComponent)
        assert comp and comp.get_skeletal_mesh_asset() == mesh
        assert comp.get_animation_mode() == unreal.AnimationMode.ANIMATION_SINGLE_NODE
        play_data = comp.get_editor_property('animation_data')
        assert play_data.get_editor_property('anim_to_play') == animation
        assert play_data.get_editor_property('saved_playing') == playing
        assert not play_data.get_editor_property('saved_looping')
        assert play_data.get_editor_property('saved_position') == 0.
        assert play_data.get_editor_property('saved_play_rate') == 1.
        assert comp.get_editor_property('component_use_fixed_skel_bounds')
        assert str(comp.get_collision_profile_name()) == 'NoCollision'
        subobjects = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
        functions = unreal.SubobjectDataBlueprintFunctionLibrary
        handles = subobjects.k2_gather_subobject_data_for_blueprint(bp)
        boxes = [functions.get_object_for_blueprint(functions.get_data(handle),bp) for handle in handles]
        boxes = [value for value in boxes if isinstance(value,unreal.BoxComponent)]
        assert len(boxes) == 1
        box = boxes[0]
        half = box.get_unscaled_box_extent()
        assert near([half.x,half.y,half.z],main['assets'][name]['collision_half_extents_cm'],.001)
        assert str(box.get_collision_profile_name()) == ('NoCollision' if playing else 'BlockAll')
        result['blueprints'][name] = {'component': comp.get_path_name(), 'mesh': mesh.get_path_name(),
                                     'animation': animation.get_path_name(), 'playing': playing, 'looping': False,
                                     'position_seconds': 0., 'single_node_mode': True, 'fixed_skeletal_bounds': True,
                                     'box_collision_profile': str(box.get_collision_profile_name()),
                                     'box_half_extents_cm': [half.x,half.y,half.z]}
    assert mesh.get_editor_property('physics_asset') is None
    result['collision'] = {'physics_asset': None, 'blueprint_box_components': 2,
                           'closed_blueprint_blocks': True, 'demo_collision_disabled': True}
    evaluation = unreal.AnimPoseEvaluationOptions()
    evaluation.set_editor_property('evaluation_type', unreal.AnimDataEvalType.COMPRESSED)
    evaluation.set_editor_property('optional_skeletal_mesh', mesh)
    pose_api = unreal.AnimPoseExtensions
    for label, marker in model['markers'].items():
        frame = marker['frame']
        time = (frame-model['frame_start'])/model['fps']
        pose = pose_api.get_anim_pose_at_time(animation, time, evaluation)
        assert pose_api.is_valid(pose)
        assert {str(n) for n in pose_api.get_bone_names(pose)} == set(model['bones'])
        values = {bone: transform(pose_api.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD)) for bone in marker['bones']}
        for bone, expected in model['source_marker_bone_locations_cm'][label].items():
            assert near(values[bone]['translation'], expected, .02), (label,bone,values[bone],expected)
        result['poses'][label] = values
    for clip in model['clips']:
        name = clip['name']
        asset = load(ROOT+'/'+name)
        unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
        assert isinstance(asset,unreal.AnimSequence) and asset.get_editor_property('skeleton') == mesh.get_editor_property('skeleton')
        assert abs(asset.get_play_length()-clip['seconds']) <= .001
        checks = {}
        for endpoint, time, frame in (('start',0.,clip['frame_start']),('end',asset.get_play_length(),clip['frame_end'])):
            clip_pose = pose_api.get_anim_pose_at_time(asset,time,evaluation)
            full_pose = pose_api.get_anim_pose_at_time(animation,(frame-model['frame_start'])/model['fps'],evaluation)
            max_translation_error, max_rotation_error = 0., 0.
            for bone in model['bones']:
                a = transform(pose_api.get_bone_pose(clip_pose,bone,unreal.AnimPoseSpaces.WORLD))
                b = transform(pose_api.get_bone_pose(full_pose,bone,unreal.AnimPoseSpaces.WORLD))
                pos_error = max(abs(x-y) for x,y in zip(a['translation'],b['translation']))
                rot_error = abs(1.-abs(sum(x*y for x,y in zip(a['rotation'],b['rotation']))))
                assert pos_error <= .02 and rot_error <= .0001 and near(a['scale'],b['scale'],.0001), (name,endpoint,bone)
                max_translation_error, max_rotation_error = max(max_translation_error,pos_error), max(max_rotation_error,rot_error)
            checks[endpoint] = {'max_translation_error_cm':max_translation_error,'max_rotation_dot_error':max_rotation_error,'bone_count':len(model['bones'])}
        result['clips'][name] = {'seconds': asset.get_play_length(), 'endpoints': checks}
    for slot in model['material_slots']:
        if slot.startswith('M_Notebook_Page') and slot != 'M_Notebook_PageEdges':
            instance = load(ROOT+'/Materials/MI_'+slot[2:])
            expected = main['materials']['MI_'+slot[2:]]['PageTexture']
            assert unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(instance,'PageTexture').get_path_name() == expected
    result['page_texture_overrides_persisted'] = 32
    protected = json.loads((UE/'protected_content_sha256.json').read_text(encoding='utf-8-sig'))
    assert all(sha(path) == digest for path,digest in protected.items())
    assert all(sha(info['file']) == info['sha256'] for info in main['new_packages_on_disk'].values())
    result['package_files_unchanged'] = result['protected_content_unchanged'] = True
    result['success'] = True
except Exception:
    result['error'] = traceback.format_exc()
    unreal.log_error('NOTEBOOK_PERSISTENCE_ERROR '+result['error'])
finally:
    result['completed_utc'] = datetime.now(timezone.utc).isoformat()
    (UE/'ue_reload_report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    unreal.log('NOTEBOOK_PERSISTENCE_RESULT '+str(result['success']))
