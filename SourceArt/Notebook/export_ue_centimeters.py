"""Produce unit-scale-one UE FBX copies, without modifying the meter-based source.

Small bone translations must be in centimeters before compression; a scale-100
armature otherwise lets UE discard paper movement as sub-centimeter noise.
"""
import bpy,json,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Notebook.blend'))
s=bpy.context.scene;rig=bpy.data.objects['Armature'];mesh=bpy.data.objects['SK_Notebook']
report=json.loads((OUT/'model_report.json').read_text(encoding='utf-8'))
s.frame_set(1)
for vertex in mesh.data.vertices:vertex.co*=100
mesh.data.update()
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
for bone in rig.data.edit_bones:
    bone.head*=100;bone.tail*=100
bpy.ops.object.mode_set(mode='OBJECT')
action=rig.animation_data.action;slot=rig.animation_data.action_slot
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                if curve.data_path.endswith('.location'):
                    for key in curve.keyframe_points:
                        key.co.y*=100;key.handle_left.y*=100;key.handle_right.y*=100
s.unit_settings.scale_length=.01
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
opts=dict(use_selection=True,object_types={'ARMATURE','MESH'},global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Z',axis_up='Y',add_leaf_bones=False,use_armature_deform_only=True,armature_nodetype='NULL',mesh_smooth_type='FACE',use_mesh_modifiers=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,path_mode='STRIP')
rig.animation_data.action=None;rig.data.pose_position='REST';s.frame_set(1)
bpy.ops.export_scene.fbx(filepath=str(OUT/'Exports/SK_Notebook.fbx'),bake_anim=False,**opts)
rig.data.pose_position='POSE';rig.animation_data.action=action;rig.animation_data.action_slot=slot
all_clips=[{'name':'A_Notebook_FullCycle','file':'Exports/A_Notebook_FullCycle.fbx','frame_start':1,'frame_end':781}]+report['clips']
for clip in all_clips:
    s.frame_start=clip['frame_start'];s.frame_end=clip['frame_end'];s.frame_set(s.frame_start);bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=str(OUT/clip['file']),bake_anim=True,bake_anim_step=1,bake_anim_simplify_factor=0,**opts)
for label,marker in report['markers'].items():
    s.frame_set(marker['frame']);bpy.context.view_layer.update()
    for name,expected in report['source_marker_bone_locations_cm'][label].items():
        v=rig.pose.bones[name].matrix.translation
        actual=[v.x,-v.y,v.z]
        assert all(abs(a-b)<.00001 for a,b in zip(actual,expected)),(label,name,actual,expected)
for path in (OUT/'Exports').glob('*.fbx'):report['files'][str(path.relative_to(OUT))]=hashlib.sha256(path.read_bytes()).hexdigest()
report['fbx_unit']='centimeter';report['fbx_armature_scale']=1;report['ue_import_uniform_scale']=1
report['source_blend_unit']='meter; unchanged; use export_ue_centimeters.py after rebuilding'
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('NOTEBOOK_UE_CM_EXPORT_VERIFIED',len(all_clips)+1,flush=True)
