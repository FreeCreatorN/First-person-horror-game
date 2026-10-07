import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\CeramicMug')
bpy.ops.wm.open_mainfile(filepath=str(out/'CeramicMug.blend'))
s=bpy.context.scene;o=bpy.data.objects['SM_CeramicMug']
bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
# Replace the boolean n-gons and overlapping bevels with a continuous surface.
o.modifiers.clear()
o.data.remesh_voxel_size=.0003;o.data.remesh_voxel_adaptivity=0
bpy.ops.object.voxel_remesh()
smooth=o.modifiers.new('Relax ceramic surface','SMOOTH');smooth.factor=.6;smooth.iterations=60;bpy.ops.object.modifier_apply(modifier=smooth.name)
dec=o.modifiers.new('Reduce rebuilt mesh density','DECIMATE');dec.ratio=.12;bpy.ops.object.modifier_apply(modifier=dec.name)
sub=o.modifiers.new('Smooth ceramic finish','SUBSURF');sub.levels=1;sub.render_levels=1;bpy.ops.object.modifier_apply(modifier=sub.name)
for p in o.data.polygons:p.use_smooth=True
bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data)
report={'vertices':len(bm.verts),'faces':len(bm.faces),'non_manifold_edges':sum(not e.is_manifold for e in bm.edges)};bm.free()
for attr in list(o.data.attributes):
 if attr.name in ['custom_normal','sharp_edge','sharp_face']:o.data.attributes.remove(attr)
for p in o.data.polygons:p.use_smooth=True
assert report['non_manifold_edges']==0,report
# Reset material assignment after remeshing, keeping the unglazed foot only below.
for p in o.data.polygons:p.material_index=1 if p.center.z<.002 else 0
glaze=o.data.materials[0]
for n in glaze.node_tree.nodes:
 if n.type=='BUMP':n.inputs['Strength'].default_value=.045
s.camera.location=(.20,-.28,.23);s.camera.rotation_euler=(Vector((.012,0,.05))-s.camera.location).to_track_quat('-Z','Y').to_euler()
s.render.engine='CYCLES';s.cycles.samples=32;s.render.filepath=str(out/'CeramicMug_Repaired.png');bpy.ops.render.render(write_still=True)
# Inspect the opposite side in plain studio shading, matching the user's screenshot.
s.camera.location=(.16,.28,.21);s.camera.rotation_euler=(Vector((.012,0,.05))-s.camera.location).to_track_quat('-Z','Y').to_euler()
s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_cavity=False
s.render.filepath=str(out/'CeramicMug_SolidCheck.png');bpy.ops.render.render(write_still=True)
s.render.engine='CYCLES'
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_rotation=s.camera.rotation_euler.to_quaternion()
bpy.ops.wm.save_as_mainfile(filepath=str(out/'CeramicMug_Repaired.blend'))
(out/'repair_report.json').write_text(json.dumps(report,indent=2))
