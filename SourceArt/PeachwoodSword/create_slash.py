import bpy, math, os, json
from mathutils import Vector, Matrix
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
bpy.ops.wm.open_mainfile(filepath=os.path.join(out,'PeachwoodSword_Optimized.blend'))
s=bpy.context.scene
if bpy.context.screen and bpy.context.screen.is_animation_playing:bpy.ops.screen.animation_cancel(restore_frame=False)
s.frame_set(1)
root=bpy.data.objects['SWORD_CONTROL | reference design']
base=root.matrix_world.copy()
grip=bpy.data.objects['Handle wood core'].matrix_world.translation.copy()
root.animation_data_clear();root.rotation_mode='XYZ'
s.frame_end=480;s.render.fps=120
# Rotate about the hand position, adding a short forward and diagonal hand stroke.
poses=[(1,0,(0,0,0)),(70,0,(0,0,0)),(150,-135,(-.12,0,.20)),(190,-145,(-.15,0,.22)),(230,45,(.20,-.10,-.03)),(265,70,(.26,-.12,-.08)),(320,65,(.24,-.10,-.07)),(410,0,(0,0,0)),(480,0,(0,0,0))]
for f,angle,offset in poses:
 rot=Matrix.Rotation(math.radians(angle),4,Vector((.18,1,.15)).normalized())
 root.matrix_world=Matrix.Translation(grip+Vector(offset))@rot@Matrix.Translation(-grip)@base
 root.keyframe_insert(data_path='location',frame=f);root.keyframe_insert(data_path='rotation_euler',frame=f)
for layer in root.animation_data.action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for k in fc.keyframe_points:k.interpolation='BEZIER';k.handle_left_type='AUTO_CLAMPED';k.handle_right_type='AUTO_CLAMPED'
s.frame_set(1)
cl=next(m for m in bpy.data.objects['TASSEL | 96 physical silk strands'].modifiers if m.type=='CLOTH')
if cl.point_cache.is_baked:
 with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.free_bake()
cl.point_cache.frame_end=480
src=open(os.path.join(out,'solve_suspension_rope.py'),encoding='utf-8-sig').read()
src=src.replace("angle=math.tau*(time_frame-1)/(s.frame_end-1)","s.frame_set(int(time_frame),subframe=time_frame-int(time_frame));bpy.context.view_layer.update()")
src=src.replace("world=Matrix.Translation(center)@Matrix.Rotation(angle,4,'Y');inverse=world.inverted()","world=root.matrix_world.copy();inverse=world.inverted()")
src=src.replace('range(64)','range(160)').replace('substeps=4','substeps=8')
src=src.replace('PeachwoodSword_Reference.blend','PeachwoodSword_Slash.blend')
exec(compile(src,'slash_rope','exec'))
# Calculate cloth sequentially and bake its complete cache.
cl.show_viewport=True
for f in range(1,s.frame_end+1):
 s.frame_set(f);dg=bpy.context.evaluated_depsgraph_get();ev=bpy.data.objects['TASSEL | 96 physical silk strands'].evaluated_get(dg);me=ev.to_mesh();ev.to_mesh_clear()
 if f%60==0:print('SLASH_CLOTH',f,flush=True)
with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.bake_from_cache()
assert cl.point_cache.is_baked
s.frame_set(1)
s['README']='Slash demo: 120 fps / 480 frames. Settle, wind-up, diagonal slash, follow-through and recovery. Grip-centered sword motion. Rope re-solved against animated sword transforms; silk cloth re-baked.'
for m in list(s.timeline_markers):s.timeline_markers.remove(m)
for name,f in [('Ready',70),('Wind up',150),('Slash',210),('Follow through',265),('Recover',410)]:s.timeline_markers.new(name,frame=f)
cam=s.camera;target=grip+Vector((0,0,.12));cam.location=target+Vector((.25,-3,.25));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.5
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.region_3d.view_distance=2.8;a.spaces.active.region_3d.view_location=target
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Slash.blend'))
result={'file':bpy.data.filepath,'cloth_baked':cl.point_cache.is_baked,'frames':480,'fps':120}

