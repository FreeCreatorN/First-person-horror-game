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
root.animation_data_clear();root.rotation_mode='QUATERNION'
s.frame_start=1;s.frame_end=780;s.render.fps=120
# Hidden lead-in permits gravity and cloth to settle before the visible action.
poses=[(1,0,(0,0,0)),(110,-145,(0,0,-.10)),(240,-145,(0,0,-.10)),(270,-145,(0,0,-.10)),(350,-185,(-.10,.035,.025)),(425,-35,(.18,-.08,-.18)),(465,-20,(.23,-.09,-.20)),(495,-20,(.23,-.09,-.20)),(640,-145,(0,0,-.10)),(780,-145,(0,0,-.10))]
axis=Vector((.20,1,.12)).normalized()
previous_root_q=None
for f in range(1,781):
 for i in range(len(poses)-1):
  f0,a0,v0=poses[i];f1,a1,v1=poses[i+1]
  if f0<=f<=f1:break
 t=(f-f0)/(f1-f0);u=t*t*t*(10+t*(-15+6*t))
 angle=a0+(a1-a0)*u;offset=Vector(v0).lerp(Vector(v1),u)
 rot=Matrix.Rotation(math.radians(angle),4,axis)
 root.matrix_world=Matrix.Translation(grip+offset)@rot@Matrix.Translation(-grip)@base
 if previous_root_q is not None:root.rotation_quaternion.make_compatible(previous_root_q)
 previous_root_q=root.rotation_quaternion.copy()
 root.keyframe_insert(data_path='location',frame=f);root.keyframe_insert(data_path='rotation_quaternion',frame=f)
for layer in root.animation_data.action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for k in fc.keyframe_points:k.interpolation='LINEAR'
s.frame_set(1)
cl=next(m for m in bpy.data.objects['TASSEL | 96 physical silk strands'].modifiers if m.type=='CLOTH')
if cl.point_cache.is_baked:
 with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.free_bake()
cl.point_cache.frame_end=780
cl.settings.quality=12
cl.settings.air_damping=5
src=open(os.path.join(out,'solve_suspension_rope.py'),encoding='utf-8-sig').read()
src=src.replace("angle=math.tau*(time_frame-1)/(s.frame_end-1)","s.frame_set(int(time_frame),subframe=time_frame-int(time_frame));bpy.context.view_layer.update()")
src=src.replace("world=Matrix.Translation(center)@Matrix.Rotation(angle,4,'Y');inverse=world.inverted()","world=root.matrix_world.copy();inverse=world.inverted()")
src=src.replace('range(64)','range(160)').replace('substeps=4','substeps=8')
src=src.replace('PeachwoodSword_Reference.blend','PeachwoodSword_NaturalSlash.blend')
src=src.replace('math.exp(-1.3*dt)','math.exp(-2.2*dt)')
src=src.replace('def store(frame):',"previous_pendant_q=None\ndef store(frame):\n global previous_pendant_q")
src=src.replace("q=(nodes[-2]-nodes[-1]).to_track_quat('Z','Y');pendant.rotation_quaternion=q;pendant.location=nodes[-2]-q@top_local", "direction=(nodes[-2]-nodes[-1]).normalized()\n q=direction.to_track_quat('Z','Y') if previous_pendant_q is None else (previous_pendant_q@Vector((0,0,1))).rotation_difference(direction)@previous_pendant_q\n q.normalize();previous_pendant_q=q.copy();pendant.rotation_quaternion=q;pendant.location=nodes[-2]-q@top_local")
exec(compile(src,'slash_rope','exec'))
# Calculate cloth sequentially and bake its complete cache.
cl.show_viewport=True
for f in range(1,s.frame_end+1):
 s.frame_set(f);dg=bpy.context.evaluated_depsgraph_get();ev=bpy.data.objects['TASSEL | 96 physical silk strands'].evaluated_get(dg);me=ev.to_mesh();ev.to_mesh_clear()
 if f%60==0:print('SLASH_CLOTH',f,flush=True)
with bpy.context.temp_override(point_cache=cl.point_cache):bpy.ops.ptcache.bake_from_cache()
assert cl.point_cache.is_baked
s.frame_start=240;s.frame_set(240)
s['README']='Refined grip trajectory, quaternion rotation, parallel-transport pendant twist, gravity pre-roll frames 1-239. Visible frames 240-780. Slash demo: 120 fps, visible frames 240-780. Settle, wind-up, diagonal slash, follow-through and recovery. Grip-centered sword motion. Rope re-solved against animated sword transforms; silk cloth re-baked.'
for m in list(s.timeline_markers):s.timeline_markers.remove(m)
for name,f in [('Ready',240),('Wind up',350),('Slash',390),('Follow through',465),('Recover',640)]:s.timeline_markers.new(name,frame=f)
cam=s.camera;target=grip+Vector((0,0,.12));cam.location=target+Vector((.25,-3,.25));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.5
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.region_3d.view_distance=2.8;a.spaces.active.region_3d.view_location=target
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_NaturalSlash.blend'))
result={'file':bpy.data.filepath,'cloth_baked':cl.point_cache.is_baked,'frames':541,'fps':120}


with open(os.path.join(out,'natural_slash_result.json'),'w') as f:json.dump(result,f)

