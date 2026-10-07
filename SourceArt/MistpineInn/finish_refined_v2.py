import bpy,math,os
from mathutils import Vector
s=bpy.context.scene;out=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn';C=bpy.data.collections['07 Interior craftsmanship']
# Flatten carpet motifs into the rug rather than letting them cast floating shadows.
for o in bpy.data.objects:
 if o.name.startswith('Rug woven medallion'):
  for v in o.data.vertices:v.co.z=.8529
 if o.name.startswith('Lobby rug woven border'):o.location.z=.853
 if o.name.startswith('Dormer cheek'):o.dimensions.z=.78;o.location.z=10.91
# Add stringers so stair treads read as a supported assembly.
def beam(name,a,b,width):
 a,b=Vector(a),Vector(b);bpy.ops.mesh.primitive_cube_add(size=1,location=(a+b)/2);o=bpy.context.object;o.name=name;o.dimensions=(width,width,(b-a).length);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();o.data.materials.append(bpy.data.materials['Dark aged oak'])
for x in [3.4,5.0]:beam('Stair structural stringer',(x,-3.0,.74),(x,2.6,3.79),.22)
# Use a cooler, darker window treatment where the rooms are unoccupied.
for m in bpy.data.materials:
 if m.name.startswith('Window occupancy 0'):
  p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.025,.045,.065,1)
# Low density atmospheric scattering gives the forest depth.
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,22,11));fog=bpy.context.object;fog.name='Forest haze volume';fog.dimensions=(105,65,26);fog.display_type='WIRE'
m=bpy.data.materials.new('Cool forest haze');m.use_nodes=True;n=m.node_tree.nodes;n.clear();o=n.new('ShaderNodeOutputMaterial');v=n.new('ShaderNodeVolumePrincipled');v.inputs['Density'].default_value=.005;v.inputs['Color'].default_value=(.5,.61,.72,1);v.inputs['Anisotropy'].default_value=.15;m.node_tree.links.new(v.outputs['Volume'],o.inputs['Volume']);fog.data.materials.append(m)
# Preserve a legible working viewport without volume-preview slowdowns.
fog.hide_set(True)
s.frame_set(1);s.camera=bpy.data.objects['CAM 01 Exterior']
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_overlays=False;area.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'MistpineInn_Refined.blend'))
bindings=[(m,m.camera) for m in s.timeline_markers]
for m,c in bindings:m.camera=None
for name,cam in [('Refined_Lobby','CAM 02 Lobby'),('Refined_Exterior','CAM 01 Exterior')]:
 s.camera=bpy.data.objects[cam];s.render.filepath=os.path.join(out,name+'.png');bpy.ops.render.render(write_still=True)
for m,c in bindings:m.camera=c
s.frame_set(1);s.camera=bpy.data.objects['CAM 01 Exterior']
print('FINAL_REFINEMENT',len(s.objects))
