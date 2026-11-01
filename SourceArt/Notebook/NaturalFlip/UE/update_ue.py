"""Update only changed Notebook AnimSequences, or verify them in a fresh editor."""
import gc
import hashlib
import json
import math
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

import unreal

UE = Path(__file__).resolve().parent
REV = UE.parent
OUT = REV.parent
PROJECT = OUT.parents[1]
CONTENT = PROJECT/'Content'
TARGET = CONTENT/'Yastars'/'Mesh'/'Notebook'
ROOT = '/Game/Yastars/Mesh/Notebook'
BEFORE = REV/'Before'
VERIFY = os.environ.get('NOTEBOOK_NATURAL_VERIFY_ONLY') == '1'
REPORT = UE/('ue_reload_report.json' if VERIFY else 'update_ue_report.json')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def vector(value):
    return [value.x,value.y,value.z]


def transform(value):
    q = value.rotation
    return {'translation':vector(value.translation),'rotation':[q.x,q.y,q.z,q.w],'scale':vector(value.scale3d)}


def close(a,b,tolerance):
    return len(a)==len(b) and all(abs(x-y)<=tolerance for x,y in zip(a,b))


def normal_from_quaternion(values):
    x,y,z,w=values
    direction=[2.*(x*z+w*y),2.*(y*z-w*x),1.-2.*(x*x+y*y)]
    length=math.sqrt(sum(value*value for value in direction))
    assert length>0.
    return [value/length for value in direction]


def protected_set():
    files = set(CONTENT.rglob('*.umap'))
    for directory in (PROJECT/'Config',CONTENT/'Yastar'/'UI',CONTENT/'Yastar'/'Items'):
        files.update(path for path in directory.rglob('*') if path.is_file())
    return {str(path.resolve()) for path in files}


def run():
    result = {'success':False,'started_utc':datetime.now(timezone.utc).isoformat(),
              'run_id':os.environ.get('NOTEBOOK_NATURAL_RUN_ID'),'editor_pid':os.getpid(),
              'mode':'verify_saved' if VERIFY else 'animation_only_update','target_root':ROOT,
              'script_sha256':sha(UE/'update_ue.py'),'updated_packages':{},'poses':{},'clips':{},
              'saved_animation_packages':[],'actors_spawned':0,'map_save_executed':False,
              'new_assets_created':0,'asset_delete_executed':False,'asset_rename_executed':False,
              'source_files_changed':False,'geometry_materials_or_blueprints_saved':False,
              'source_normal_checks':0}
    world, previous_flag = None,None
    try:
        unreal.load_module('AnimationBlueprintLibrary')
        unreal.load_module('BlueprintEditorLibrary')
        assert Path(unreal.Paths.project_dir()).resolve()==PROJECT
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        assert world and world.get_path_name().startswith('/Engine/Maps/Entry')
        result['world_before']=world.get_path_name()
        plan, before, model = read(UE/'update_plan.json'),read(BEFORE/'state_manifest.json'),read(OUT/'model_report.json')
        assert plan['success'] and plan['target_root']==ROOT
        assert plan['before_manifest_sha256']==sha(BEFORE/'state_manifest.json')
        result['plan_sha256']=sha(UE/'update_plan.json')
        result['sources_sha256']=plan['sources_sha256']
        result['replace_names']=plan['replace_names']
        result['preserve_names']=plan['preserve_names']
        assert len(plan['animations'])==19 and plan['replace_names']
        assert all(sha(path)==digest for path,digest in plan['sources_sha256'].items()), 'Source changed after preflight'
        assert protected_set()==set(before['protected_files'])
        assert all(sha(path)==digest for path,digest in before['protected_files'].items()), 'Protected project files changed'
        prior = read(UE/'update_ue_report.json') if VERIFY else None
        if VERIFY:
            assert prior['success'] and prior['editor_pid']!=os.getpid()
            assert prior['run_id']==result['run_id'] and prior['plan_sha256']==result['plan_sha256']
            result['update_report_sha256']=sha(UE/'update_ue_report.json')
        assert {p.resolve() for p in TARGET.rglob('*.uasset')}=={Path(item['file']).resolve() for item in before['packages'].values()}
        for package,item in before['packages'].items():
            expected = prior['updated_packages'][package]['sha256'] if VERIFY and package in prior['updated_packages'] else item['sha256']
            assert sha(item['file'])==expected, ('Unexpected package change; do not overwrite',package)
            if item['replace_allowed']:
                assert sha(item['backup'])==item['sha256']
        edit = unreal.EditorAssetLibrary
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        mesh = edit.load_asset(ROOT+'/SK_Notebook')
        assert isinstance(mesh,unreal.SkeletalMesh)
        skeleton = mesh.get_editor_property('skeleton')
        original = read(BEFORE/'Evidence'/'ue_import_report.json')
        assert skeleton.get_path_name()==original['assets']['SK_Notebook']['skeleton']
        unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
        geometry = unreal.AssetRegistryHelpers.create_asset_data(mesh)
        assert int(geometry.get_tag_value('Triangles'))==model['triangles']==35756
        assert int(geometry.get_tag_value('Bones'))==len(model['bones'])==156
        assert len(mesh.get_editor_property('materials'))==len(model['material_slots'])==38
        result['geometry']={'triangles':35756,'bones':156,'materials':38,'skeleton':skeleton.get_path_name()}
        to_save,animations = {},{}
        if not VERIFY:
            previous_flag=unreal.SystemLibrary.get_console_variable_int_value('Interchange.FeatureFlags.Import.FBX')
            unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX 0')
            assert unreal.SystemLibrary.get_console_variable_int_value('Interchange.FeatureFlags.Import.FBX')==0
        for name,spec in plan['animations'].items():
            package=spec['package']
            asset=edit.load_asset(package)
            assert isinstance(asset,unreal.AnimSequence) and asset.get_editor_property('skeleton')==skeleton
            if not VERIFY and spec['replace']:
                assert before['packages'][package]['replace_allowed']
                assert sha(before['packages'][package]['file'])==spec['original_package_sha256']
                options=unreal.FbxImportUI()
                for key,value in {'import_mesh':False,'import_as_skeletal':True,'import_animations':True,
                    'import_materials':False,'import_textures':False,'create_physics_asset':False,
                    'automated_import_should_detect_type':False,'mesh_type_to_import':unreal.FBXImportType.FBXIT_ANIMATION,
                    'skeleton':skeleton,'override_animation_name':name}.items():
                    options.set_editor_property(key,value)
                data=options.get_editor_property('anim_sequence_import_data')
                for key,value in {'import_uniform_scale':1.,'animation_length':unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME,
                    'use_default_sample_rate':False,'custom_sample_rate':30,'remove_redundant_keys':False,
                    'preserve_local_transform':True}.items():
                    data.set_editor_property(key,value)
                task=unreal.AssetImportTask()
                for key,value in {'filename':str(OUT/spec['file']),'destination_path':ROOT,'destination_name':name,
                    'automated':True,'replace_existing':True,'replace_existing_settings':True,'save':False,'options':options}.items():
                    task.set_editor_property(key,value)
                asset_tools.import_asset_tasks([task])
                paths={str(path).split('.')[0] for path in task.get_editor_property('imported_object_paths')}
                assert paths=={package}, ('Import attempted an unexpected package',paths)
                asset=edit.load_asset(package)
                assert isinstance(asset,unreal.AnimSequence) and asset.get_editor_property('skeleton')==skeleton
                asset.set_editor_property('compression_error_threshold_scale',1000.)
                asset.set_editor_property('allow_frame_stripping',False)
                to_save[package]=asset
            unreal.SystemLibrary.execute_console_command(world,'Editor.AsyncAssetCompilationFinishAll')
            assert abs(asset.get_play_length()-spec['seconds'])<=.001,(name,asset.get_play_length(),spec['seconds'])
            animations[name]=asset
        full=animations['A_Notebook_FullCycle']
        evaluation=unreal.AnimPoseEvaluationOptions()
        evaluation.set_editor_property('evaluation_type',unreal.AnimDataEvalType.COMPRESSED)
        evaluation.set_editor_property('optional_skeletal_mesh',mesh)
        evaluation.set_editor_property('should_retarget',True)
        pose_api=unreal.AnimPoseExtensions

        def pose_at(animation,time):
            pose=pose_api.get_anim_pose_at_time(animation,time,evaluation)
            assert pose_api.is_valid(pose)
            assert {str(name) for name in pose_api.get_bone_names(pose)}==set(model['bones'])
            return pose

        for label,marker in model['markers'].items():
            frame=marker['frame']
            time=(frame-model['frame_start'])/model['fps']
            pose=pose_at(full,time)
            values={name:transform(pose_api.get_bone_pose(pose,name,unreal.AnimPoseSpaces.WORLD)) for name in marker['bones']}
            for bone,expected in model['source_marker_bone_locations_cm'][label].items():
                assert close(values[bone]['translation'],expected,.02),('Compressed source position differs',label,bone,values[bone],expected)
            normal_checks={}
            for bone,expected in model.get('source_marker_bone_normals',{}).get(label,{}).items():
                if bone not in values:
                    values[bone]=transform(pose_api.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD))
                actual=normal_from_quaternion(values[bone]['rotation'])
                dot_error=abs(1.-sum(a*b for a,b in zip(actual,expected)))
                assert dot_error<=.0001,('Compressed page normal differs from source',label,bone,actual,expected,dot_error)
                normal_checks[bone]={'normal':actual,'source_normal':expected,'dot_error':dot_error}
                result['source_normal_checks']+=1
            assert all(math.isfinite(value) for item in values.values() for group in item.values() for value in group)
            result['poses'][label]={'frame':frame,'seconds':time,'bones':values,'normal_checks':normal_checks}
        for spec in model['clips']:
            name=spec['name']
            animation=animations[name]
            checks={}
            for endpoint,time,frame in (('start',0.,spec['frame_start']),('end',animation.get_play_length(),spec['frame_end'])):
                a=pose_at(animation,time)
                b=pose_at(full,(frame-model['frame_start'])/model['fps'])
                max_position,max_rotation=0.,0.
                for bone in model['bones']:
                    x=transform(pose_api.get_bone_pose(a,bone,unreal.AnimPoseSpaces.WORLD))
                    y=transform(pose_api.get_bone_pose(b,bone,unreal.AnimPoseSpaces.WORLD))
                    position=max(abs(u-v) for u,v in zip(x['translation'],y['translation']))
                    rotation=abs(1.-abs(sum(u*v for u,v in zip(x['rotation'],y['rotation']))))
                    assert position<=.02 and rotation<=.0001 and close(x['scale'],y['scale'],.0001),(name,endpoint,bone,x,y)
                    max_position,max_rotation=max(max_position,position),max(max_rotation,rotation)
                checks[endpoint]={'source_frame':frame,'max_position_error_cm':max_position,'max_rotation_dot_error':max_rotation,'bone_count':156}
            result['clips'][name]={'asset':animation.get_path_name(),'seconds':animation.get_play_length(),
                                   'replaced':plan['animations'][name]['replace'],'endpoints':checks}
        for name in ('BP_Notebook','BP_Notebook_Demo'):
            bp=edit.load_asset(ROOT+'/'+name)
            comp=unreal.get_default_object(bp.generated_class()).get_component_by_class(unreal.SkeletalMeshComponent)
            assert comp and comp.get_skeletal_mesh_asset()==mesh
            assert comp.get_editor_property('animation_data').get_editor_property('anim_to_play')==full
        result['blueprint_references_verified']=True
        assert all(sha(path)==digest for path,digest in plan['sources_sha256'].items())
        assert all(sha(path)==digest for path,digest in before['protected_files'].items())
        if not VERIFY:
            assert set(to_save)=={ROOT+'/'+name for name in plan['replace_names']}
            # Validate every imported animation before saving any package.
            for package,asset in to_save.items():
                assert before['packages'][package]['replace_allowed']
                assert edit.save_loaded_asset(asset,False),package
                result['saved_animation_packages'].append(package)
                path=Path(before['packages'][package]['file'])
                result['updated_packages'][package]={'file':str(path),'before_sha256':before['packages'][package]['sha256'],
                                                    'sha256':sha(path),'bytes':path.stat().st_size}
        else:
            result['updated_packages']=prior['updated_packages']
        for package,item in before['packages'].items():
            expected=result['updated_packages'][package]['sha256'] if package in result['updated_packages'] else item['sha256']
            assert sha(item['file'])==expected,('Unrelated package changed',package)
        assert {p.resolve() for p in TARGET.rglob('*.uasset')}=={Path(item['file']).resolve() for item in before['packages'].values()}
        result['preserved_package_count']=len(before['packages'])-len(result['updated_packages'])
        result['protected_files_checked']=len(before['protected_files'])
        result['protected_content_unchanged']=result['source_files_unchanged']=result['unrelated_packages_unchanged']=True
        result['world_after']=editor.get_editor_world().get_path_name()
        assert editor.get_editor_world()==world and result['world_after']==result['world_before']
        result['success']=True
    except Exception:
        result['error']=traceback.format_exc()
        unreal.log_error('NOTEBOOK_NATURAL_UPDATE_ERROR '+result['error'])
    finally:
        if world is not None and previous_flag is not None:
            unreal.SystemLibrary.execute_console_command(world,'Interchange.FeatureFlags.Import.FBX '+str(previous_flag))
            result['fbx_backend_restored']=unreal.SystemLibrary.get_console_variable_int_value('Interchange.FeatureFlags.Import.FBX')==previous_flag
        result['completed_utc']=datetime.now(timezone.utc).isoformat()
        REPORT.write_text(json.dumps(result,indent=2),encoding='utf-8')
        unreal.log('NOTEBOOK_NATURAL_UPDATE_RESULT '+str(result['success']))


run()
# Release AnimPose/Subobject/native object wrappers before editor shutdown.
gc.collect()
