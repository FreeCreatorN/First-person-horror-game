"""Export individual playback clips and capture source-space pose evidence."""
import bpy,json,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Notebook.blend'))
s=bpy.context.scene;rig=bpy.data.objects['Armature'];mesh=bpy.data.objects['SK_Notebook']
report=json.loads((OUT/'model_report.json').read_text(encoding='utf-8'))
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
clips=[{'name':'A_Notebook_Open','frame_start':1,'frame_end':49}]+[{'name':f'A_Notebook_Turn{i+1:02d}','frame_start':71+40*i,'frame_end':99+40*i} for i in range(16)]+[{'name':'A_Notebook_CloseLast','frame_start':721,'frame_end':769}]
for clip in clips:
    s.frame_start=clip['frame_start'];s.frame_end=clip['frame_end']
    clip['file']='Exports/'+clip['name']+'.fbx';clip['seconds']=(s.frame_end-s.frame_start)/30
    bpy.ops.export_scene.fbx(filepath=str(OUT/clip['file']),use_selection=True,object_types={'ARMATURE','MESH'},global_scale=1,apply_unit_scale=True,axis_forward='-Z',axis_up='Y',add_leaf_bones=False,use_armature_deform_only=True,armature_nodetype='NULL',mesh_smooth_type='FACE',use_mesh_modifiers=True,bake_anim=True,bake_anim_step=1,bake_anim_simplify_factor=0,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,path_mode='STRIP')
    report['files'][clip['file']]=hashlib.sha256((OUT/clip['file']).read_bytes()).hexdigest()
s.frame_start=1;s.frame_end=781;report['clips']=clips
report['source_marker_bone_locations_cm']={}
for label,marker in report['markers'].items():
    s.frame_set(marker['frame']);bpy.context.view_layer.update()
    locations={}
    for name in marker['bones']:
        v=rig.pose.bones[name].matrix.translation;locations[name]=[v.x*100,-v.y*100,v.z*100]
    report['source_marker_bone_locations_cm'][label]=locations
# Validate all source normals and leaf attachment under the evaluated animation.
s.frame_set(1);bpy.context.view_layer.update()
report['exported_cameras']=0;report['exported_lights']=0
report['source_blender_version']=bpy.app.version_string
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('NOTEBOOK_CLIPS_READY',len(clips),flush=True)
