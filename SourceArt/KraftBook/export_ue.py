import bpy,json
from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\KraftBook')
bpy.ops.wm.open_mainfile(filepath=str(out/'KraftBook_FullCycle.blend'))
s=bpy.context.scene;s.frame_set(1)
objects=[o for o in s.objects if o.type=='MESH' and o.name!='Studio floor']
# Stable, UE-friendly material names shared by both exports.
for m in bpy.data.materials:
 if m.name.startswith('Natural brown'):m.name='M_Book_Kraft'
 elif m.name.startswith('Warm paper'):m.name='M_Book_Paper_'+m.name[-2:]
 elif m.name=='Binding crease':m.name='M_Book_Crease'
 elif m.name=='Muted brown bookmark':m.name='M_Book_Ribbon'
for o in objects:
 if not o.data.uv_layers:
  uv=o.data.uv_layers.new(name='UVMap')
  for p in o.data.polygons:
   for li in p.loop_indices:
    co=o.data.vertices[o.data.loops[li].vertex_index].co
    uv.data[li].uv=(co.x/.15+.5,co.y/.216+.5)
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
bpy.ops.export_scene.fbx(filepath=str(out/'SM_KraftBook.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,use_mesh_modifiers=True)
args=dict(filepath=str(out/'GC_KraftBook_FullCycle.abc'),start=1,end=1632,selected=True,flatten=True,uvs=True,normals=True,face_sets=True,subdiv_schema=False,export_custom_properties=False,as_background_job=False)
valid=bpy.ops.wm.alembic_export.get_rna_type().properties.keys()
bpy.ops.wm.alembic_export(**{k:v for k,v in args.items() if k in valid})
(out/'ue_export_report.json').write_text(json.dumps({'objects':len(objects),'frames':1632,'fps':24,'materials':[m.name for m in bpy.data.materials if m.name.startswith('M_Book')]},indent=2))
