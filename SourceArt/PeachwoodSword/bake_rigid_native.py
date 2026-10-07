import bpy,os
scene=bpy.context.scene
cl=next(m for m in bpy.data.objects['TASSEL | 96 physical silk strands'].modifiers if m.type=='CLOTH');cl.show_viewport=False
cache=scene.rigidbody_world.point_cache
with bpy.context.temp_override(point_cache=cache):bpy.ops.ptcache.free_bake()
scene.frame_set(1)
with bpy.context.temp_override(point_cache=cache):bpy.ops.ptcache.bake(bake=True)
cl.show_viewport=True;scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword\PeachwoodSword_Reference.blend')
