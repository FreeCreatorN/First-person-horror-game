import bpy,os,json
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
s=bpy.context.scene; root=bpy.data.objects['SWORD_CONTROL | reference design']; anchor=bpy.data.objects['SUSPENSION | fixed pommel attachment']
cloth=next(m for m in bpy.data.objects['TASSEL | 96 physical silk strands'].modifiers if m.type=='CLOTH'); cloth.show_viewport=False
s.frame_set(1); bpy.context.view_layer.update(); relative=root.matrix_world.inverted()@anchor.matrix_world
poses=[]
for frame in range(1,161):
    s.frame_set(frame); poses.append((frame,root.matrix_world@relative))
cache=s.rigidbody_world.point_cache
if cache.is_baked:
    with bpy.context.temp_override(point_cache=cache):bpy.ops.ptcache.free_bake()
s.frame_set(1); anchor.parent=None; anchor.animation_data_clear(); anchor.rotation_mode='QUATERNION'
anchor.rigid_body.type='ACTIVE'; anchor.rigid_body.kinematic=True
for frame,matrix in poses:
    anchor.matrix_world=matrix; anchor.keyframe_insert(data_path='location',frame=frame); anchor.keyframe_insert(data_path='rotation_quaternion',frame=frame)
anchor['Animation source']='World transforms sampled from sword pommel to avoid a one-frame lag in rigid-body parenting. Regenerate after changing sword animation.'
for layer in anchor.animation_data.action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for k in fc.keyframe_points:k.interpolation='LINEAR'
s.frame_set(1)
for f in range(1,161):s.frame_set(f); bpy.context.evaluated_depsgraph_get().update()
with bpy.context.temp_override(point_cache=cache):bpy.ops.ptcache.bake_from_cache()
cloth.show_viewport=True; s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
print('ANCHOR_TIMING_REBAKED',flush=True)
