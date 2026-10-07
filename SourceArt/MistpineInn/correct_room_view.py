import bpy,os
from mathutils import Vector
s=bpy.context.scene;cam=bpy.data.objects['CAM 04 Guest room']
cam.location=(3.8,-4.9,5.65);cam.rotation_euler=(Vector((6.25,-2.55,5.1))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=21
wood=bpy.data.materials['Dark aged oak']
for cx in [5.35,8.0]:
 for dx in [-.65,0,.65]:
  bpy.ops.mesh.primitive_cube_add(size=1,location=(cx+dx,-5.38,5.72));o=bpy.context.object;o.name='Interior window mullion';o.dimensions=(.065,.07,1.82);o.data.materials.append(wood)
 for dz in [-.87,0,.87]:
  bpy.ops.mesh.primitive_cube_add(size=1,location=(cx,-5.38,5.72+dz));o=bpy.context.object;o.name='Interior window transom';o.dimensions=(1.42,.07,.065);o.data.materials.append(wood)
for o in bpy.data.objects:
 if o.name.startswith(('Bedpost brass finial','Bed turned post','Headboard spindle')) and o.type=='MESH':
  for p in o.data.polygons:p.use_smooth=True
s.frame_set(31);s.camera=cam
bpy.ops.wm.save_as_mainfile(filepath=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn\MistpineInn_Refined.blend')
s.render.filepath=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn\GuestRoom_LiveRefinement.png';bpy.ops.render.render(write_still=True)
print('VIEW_CORRECTED')
