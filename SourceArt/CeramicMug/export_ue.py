import bpy,json
from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\CeramicMug')
bpy.ops.wm.open_mainfile(filepath=str(out/'CeramicMug_Pouring.blend'))
s=bpy.context.scene;s.frame_set(1)
body=bpy.data.objects['SM_CeramicMug'];bpy.context.view_layer.objects.active=body
dec=body.modifiers.new('Game mesh reduction','DECIMATE');dec.ratio=.045;bpy.ops.object.modifier_apply(modifier=dec.name)
for p in body.data.polygons:p.use_smooth=True
bpy.data.materials['Water - clear'].name='M_Mug_Water'
cup=[body]+[o for o in s.objects if o.name.startswith('Olive rim accent')]
objects=[o for o in s.objects if o.type=='MESH' and o.name!='Studio floor']
for o in cup:
 if not o.data.uv_layers:
  bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
for o in cup:o.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(out/'SM_CeramicMug.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,use_mesh_modifiers=True)
for o in objects:o.select_set(True)
args=dict(filepath=str(out/'GC_CeramicMug_Pouring.abc'),start=1,end=220,selected=True,flatten=True,uvs=True,normals=True,face_sets=True,as_background_job=False)
valid=bpy.ops.wm.alembic_export.get_rna_type().properties.keys();bpy.ops.wm.alembic_export(**{k:v for k,v in args.items() if k in valid})
body.data.calc_loop_triangles()
(out/'ue_export_report.json').write_text(json.dumps({'body_triangles':len(body.data.loop_triangles),'frames':220,'fps':24,'objects':len(objects)},indent=2))
