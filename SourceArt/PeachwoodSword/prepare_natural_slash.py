from pathlib import Path
p=Path(r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword')
src=(p/'create_slash.py').read_text(encoding='utf-8-sig')
a=src.index("root.animation_data_clear();")
b=src.index("s.frame_set(1)\ncl=",a)
replacement='''root.animation_data_clear();root.rotation_mode='QUATERNION'
s.frame_start=1;s.frame_end=780;s.render.fps=120
# Hidden lead-in permits gravity and cloth to settle before the visible action.
poses=[(1,0,(0,0,0)),(110,-145,(0,0,-.10)),(240,-145,(0,0,-.10)),(270,-145,(0,0,-.10)),(350,-185,(-.10,.035,.025)),(425,-35,(.18,-.08,-.18)),(465,-20,(.23,-.09,-.20)),(495,-20,(.23,-.09,-.20)),(640,-145,(0,0,-.10)),(780,-145,(0,0,-.10))]
axis=Vector((.20,1,.12)).normalized()
for f in range(1,781):
 for i in range(len(poses)-1):
  f0,a0,v0=poses[i];f1,a1,v1=poses[i+1]
  if f0<=f<=f1:break
 t=(f-f0)/(f1-f0);u=t*t*t*(10+t*(-15+6*t))
 angle=a0+(a1-a0)*u;offset=Vector(v0).lerp(Vector(v1),u)
 rot=Matrix.Rotation(math.radians(angle),4,axis)
 root.matrix_world=Matrix.Translation(grip+offset)@rot@Matrix.Translation(-grip)@base
 root.keyframe_insert(data_path='location',frame=f);root.keyframe_insert(data_path='rotation_quaternion',frame=f)
for layer in root.animation_data.action.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for k in fc.keyframe_points:k.interpolation='LINEAR'
'''
src=src[:a]+replacement+src[b:]
src=src.replace('cl.point_cache.frame_end=480','cl.point_cache.frame_end=780\ncl.settings.quality=12\ncl.settings.air_damping=5')
src=src.replace("exec(compile(src,'slash_rope','exec'))",'''src=src.replace('math.exp(-1.3*dt)','math.exp(-2.2*dt)')
src=src.replace('def store(frame):',"previous_pendant_q=None\\ndef store(frame):\\n global previous_pendant_q")
src=src.replace("q=(nodes[-2]-nodes[-1]).to_track_quat('Z','Y');pendant.rotation_quaternion=q;pendant.location=nodes[-2]-q@top_local", "direction=(nodes[-2]-nodes[-1]).normalized()\\n q=direction.to_track_quat('Z','Y') if previous_pendant_q is None else (previous_pendant_q@Vector((0,0,1))).rotation_difference(direction)@previous_pendant_q\\n q.normalize();previous_pendant_q=q.copy();pendant.rotation_quaternion=q;pendant.location=nodes[-2]-q@top_local")
exec(compile(src,'slash_rope','exec'))''')
src=src.replace('PeachwoodSword_Slash.blend','PeachwoodSword_NaturalSlash.blend')
src=src.replace("s.frame_set(1)\ns['README']", "s.frame_start=240;s.frame_set(240)\ns['README']")
src=src.replace("s['README']='Slash demo:","s['README']='Refined grip trajectory, quaternion rotation, parallel-transport pendant twist, gravity pre-roll frames 1-239. Visible frames 240-780. Slash demo:")
src=src.replace("[('Ready',70),('Wind up',150),('Slash',210),('Follow through',265),('Recover',410)]","[('Ready',240),('Wind up',350),('Slash',390),('Follow through',465),('Recover',640)]")
src=src.replace("'frames':480","'frames':541")
src += "\nwith open(os.path.join(out,'natural_slash_result.json'),'w') as f:json.dump(result,f)\n"
(p/'create_natural_slash.py').write_text(src,encoding='utf-8')
