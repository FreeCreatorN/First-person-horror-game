import bpy, math, os, json, bmesh
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
root.animation_data_clear(); root.rotation_euler=(0,0,0)
bpy.context.view_layer.update()
# Geometric midpoint of the solid sword, excluding tassel decorations.
blade=bpy.data.objects['Peachwood blade | broad engraved face']
pommel=bpy.data.objects['Round cloud-carved pommel']
bounds=[ob.matrix_world@Vector(corner) for ob in [blade,pommel] for corner in ob.bound_box]
center=Vector(((min(p.x for p in bounds)+max(p.x for p in bounds))/2,(min(p.y for p in bounds)+max(p.y for p in bounds))/2,(min(p.z for p in bounds)+max(p.z for p in bounds))/2))
poses=[(ob,ob.matrix_world.copy()) for ob in root.children]
root.location=center
bpy.context.view_layer.update()
for ob,matrix in poses:ob.matrix_world=matrix
bpy.context.view_layer.update()
root.empty_display_type='CIRCLE'; root.empty_display_size=.07
root['Pivot']='Geometric center of solid sword, excluding tassel'
root.rotation_mode='XYZ'
for frame,angle in [(1,0),(160,math.tau)]:
    root.rotation_euler=(0,angle,0)
    root.keyframe_insert(data_path='rotation_euler',frame=frame,group='End over end around sword center')
for layer in root.animation_data.action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                for key in fc.keyframe_points:key.interpolation='LINEAR'
scene.frame_start=1; scene.frame_end=160; scene.render.fps=30
scene.timeline_markers.clear()
for name,frame in [('START - point down',1),('QUARTER - horizontal',41),('HALF - point up',81),('THREE QUARTERS',120),('FULL TURN - point down',160)]:scene.timeline_markers.new(name,frame=frame)
scene['Animation demo']='End-over-end rotation 360 degrees about geometric midpoint of sword, transverse Y axis, frames 1-160. Recomputed cloth collision.'
colliders=[bpy.data.objects[n] for n in ['Cloud silhouette carved crossguard','Peachwood blade | broad engraved face','Handle wood core','Round cloud-carved pommel','Polished redwood bead']]
cc=bpy.data.collections['PHYSICS | sword colliders']
for ob in colliders:
    if ob.name not in cc.objects:cc.objects.link(ob)
    bm=bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(ob.data); bm.free()
    if not any(m.type=='COLLISION' for m in ob.modifiers):ob.modifiers.new('Silk collision surface','COLLISION')
    ob.collision.thickness_outer=.002; ob.collision.thickness_inner=.001; ob.collision.cloth_friction=5
cl.settings.quality=16; cl.collision_settings.collision_quality=12
source=open(os.path.join(out,'fix_tassel_collision.py'),encoding='utf-8-sig').read()
verification=source.split('scene.frame_set(1)\ndeps=')[1].split('cam=scene.camera')[0]
exec('scene.frame_set(1)\ndeps='+verification)
scene.frame_set(160)
assert abs(root.rotation_euler.y-math.tau)<.00001
scene.frame_set(1)
# Camera and viewport encompass the full circular path.
cam=scene.camera; cam.data.ortho_scale=1.55
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_location=center; area.spaces.active.region_3d.view_distance=1.8
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
result={'rotation_degrees':360,'axis':'transverse Y, end-over-end','pivot_world':list(center),'collision_report':report}
