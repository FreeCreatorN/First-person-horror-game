import bpy, math, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
scene=bpy.context.scene
if bpy.context.screen and bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_cancel(restore_frame=False)
root=bpy.data.objects['SWORD_CONTROL | reference design']
tassel=bpy.data.objects['TASSEL | 96 physical silk strands']
cl=next(m for m in tassel.modifiers if m.type=='CLOTH')
with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.free_bake()
scene.frame_set(1)
root.animation_data_clear()
root.rotation_mode='XYZ'
for frame,angle in [(1,0),(160,math.tau)]:
    root.rotation_euler=(0,0,angle)
    root.keyframe_insert(data_path='rotation_euler',frame=frame,group='Full 360 degree turn')
action=root.animation_data.action
# Blender 5 uses layered actions.
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                for key in fc.keyframe_points:key.interpolation='LINEAR'
scene.frame_start=1; scene.frame_end=160; scene.render.fps=30
scene.timeline_markers.clear()
for name,frame in [('START 0 degrees',1),('90 degrees',41),('180 degrees',81),('270 degrees',120),('FULL TURN 360 degrees',160)]:scene.timeline_markers.new(name,frame=frame)
scene['Animation demo']='One full 360 degree turn about the longitudinal Z axis, frames 1-160 at 30 fps. Cloth rebaked for this action.'
colliders=[bpy.data.objects[n] for n in ['Cloud silhouette carved crossguard','Peachwood blade | broad engraved face']]
# Reuse the full-frame collision validation and bake, without changing placement.
source=open(os.path.join(out,'fix_tassel_collision.py'),encoding='utf-8-sig').read()
verification=source.split('scene.frame_set(1)\ndeps=')[1].split('cam=scene.camera')[0]
exec('scene.frame_set(1)\ndeps='+verification)
scene.frame_set(160)
assert abs(root.rotation_euler.z-math.tau)<.00001
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
result={'rotation_degrees':360,'axis':'Z / sword length','frames':160,'baked':cl.point_cache.is_baked,'collision_report':report}
