import bpy,os
from mathutils import Vector
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
s=bpy.context.scene;world=s.rigidbody_world
cl=next(m for m in bpy.data.objects['TASSEL | 96 physical silk strands'].modifiers if m.type=='CLOTH')
for pc in [world.point_cache,cl.point_cache]:
 if pc.is_baked:
  with bpy.context.temp_override(point_cache=pc):bpy.ops.ptcache.free_bake()
s.frame_set(1)
if not s.get('High rate suspension'):
 for ob in [bpy.data.objects['SWORD_CONTROL | reference design'],bpy.data.objects['SUSPENSION | fixed pommel attachment']]:
  for layer in ob.animation_data.action.layers:
   for strip in layer.strips:
    for bag in strip.channelbags:
     for fc in bag.fcurves:
      for k in fc.keyframe_points:
       k.co.x=1+(k.co.x-1)*4;k.handle_left.x=1+(k.handle_left.x-1)*4;k.handle_right.x=1+(k.handle_right.x-1)*4
 for marker in s.timeline_markers:marker.frame=1+(marker.frame-1)*4
 s['High rate suspension']=True
s.render.fps=120;s.frame_end=637
world.point_cache.frame_end=637;cl.point_cache.frame_end=637
world.substeps_per_frame=32;world.solver_iterations=250;cl.settings.quality=8;cl.collision_settings.collision_quality=8
for ob in bpy.data.objects:
 if ob.name.startswith('SUSPENSION | cord link'):ob.rigid_body.mass=.0008
bpy.data.objects['SUSPENSION | hanging knot body'].rigid_body.mass=.008
# A proper fastening knot at the drilled pommel eye covers the short attachment joint.
if bpy.data.objects.get('Pommel eye fastening knot') is None:
 anchor=bpy.data.objects['SUSPENSION | fixed pommel attachment']; root=bpy.data.objects['SWORD_CONTROL | reference design']
 bpy.context.view_layer.update();p=anchor.matrix_world.translation.copy()
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.006,location=p)
 ob=bpy.context.object;ob.name='Pommel eye fastening knot';ob.data.materials.append(bpy.data.materials['Deep vermilion silk'])
 pose=ob.matrix_world.copy();ob.parent=root;ob.matrix_parent_inverse=root.matrix_world.inverted();ob.matrix_world=pose
cl.show_viewport=False
s.frame_set(1)
with bpy.context.temp_override(point_cache=world.point_cache):bpy.ops.ptcache.bake(bake=True)
cl.show_viewport=True;s.frame_set(1)
s['Animation demo']='Full midpoint flip in 5.3 seconds, 637 frames at 120 fps. Higher sample rate for articulated cord attachment stability.'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
print('HIGH_RATE_RIGID_READY')
