import bpy, math, os, json
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
s=bpy.context.scene;root=bpy.data.objects['SWORD_CONTROL | reference design'];pendant=bpy.data.objects['SUSPENSION | hanging knot body']
cloth=next(m for m in bpy.data.objects['TASSEL | 96 physical silk strands'].modifiers if m.type=='CLOTH')
for pc in [s.rigidbody_world.point_cache,cloth.point_cache]:
 if pc.is_baked:
  with bpy.context.temp_override(point_cache=pc):bpy.ops.ptcache.free_bake()
s.frame_set(1);s.rigidbody_world.enabled=False;cloth.show_viewport=False;bpy.context.view_layer.update()
links=sorted([o for o in bpy.data.objects if o.name.startswith('SUSPENSION | cord link')],key=lambda o:o.name)
nodes=[bpy.data.objects['Cord ball joint %02d'%i].matrix_world.translation.copy() for i in range(18)]
nodes.append(bpy.data.objects['Cord to weighted knot'].matrix_world.translation.copy())
top_local=pendant.matrix_world.inverted()@nodes[-1]
nodes.append(pendant.matrix_world@(top_local-Vector((0,0,.10))))
rest=[(nodes[i+1]-nodes[i]).length for i in range(len(nodes)-1)]
weights=[0]+[1.0]*17+[.06,.06]
velocity=[Vector((0,0,0)) for p in nodes]
center=root.matrix_world.translation.copy();inv=root.matrix_world.inverted();anchor_local=inv@nodes[0]
colliders=[];dg=bpy.context.evaluated_depsgraph_get()
for name in ['Cloud silhouette carved crossguard','Peachwood blade | broad engraved face','Handle wood core','Round cloud-carved pommel']:
 ob=bpy.data.objects[name];ev=ob.evaluated_get(dg);me=ev.to_mesh();m=inv@ev.matrix_world
 colliders.append(BVHTree.FromPolygons([m@v.co for v in me.vertices],[list(p.vertices) for p in me.polygons]));ev.to_mesh_clear()
for ob in links+[pendant]:
 ob.animation_data_clear();ob.rigid_body.kinematic=True;ob.rotation_mode='QUATERNION'
def store(frame):
 for i,ob in enumerate(links):
  a,b=nodes[i:i+2];ob.location=(a+b)*.5;ob.rotation_quaternion=(b-a).to_track_quat('Z','Y')
  ob.keyframe_insert(data_path='location',frame=frame);ob.keyframe_insert(data_path='rotation_quaternion',frame=frame)
 q=(nodes[-2]-nodes[-1]).to_track_quat('Z','Y');pendant.rotation_quaternion=q;pendant.location=nodes[-2]-q@top_local
 pendant.keyframe_insert(data_path='location',frame=frame);pendant.keyframe_insert(data_path='rotation_quaternion',frame=frame)
store(1)
max_length_error=0;max_anchor_error=0;min_height=100
substeps=4;dt=1/(s.render.fps*substeps)
snapshots=[]
for frame in range(2,s.frame_end+1):
 for sub in range(substeps):
  time_frame=frame-1+(sub+1)/substeps
  angle=math.tau*(time_frame-1)/(s.frame_end-1)
  world=Matrix.Translation(center)@Matrix.Rotation(angle,4,'Y');inverse=world.inverted()
  previous=[p.copy() for p in nodes]
  for i in range(1,len(nodes)):
   velocity[i]+=Vector((0,0,-9.81))*dt;velocity[i]*=math.exp(-1.3*dt);nodes[i]+=velocity[i]*dt
  pinned=world@anchor_local;nodes[0]=pinned
  for iteration in range(64):
   indices=range(len(rest)) if iteration%2==0 else range(len(rest)-1,-1,-1)
   for i in indices:
    delta=nodes[i+1]-nodes[i];length=delta.length
    if length<1e-9:continue
    correction=delta*((length-rest[i])/length);total=weights[i]+weights[i+1]
    nodes[i]+=correction*(weights[i]/total);nodes[i+1]-=correction*(weights[i+1]/total)
   if iteration%4==0:
    for i in range(3,len(nodes)):
     radius=.0023 if i<18 else (.033 if i==18 else .014)
     p=inverse@nodes[i]
     for bvh in colliders:
      near,normal,index,distance=bvh.find_nearest(p)
      signed=distance if (p-near).dot(normal)>=0 else -distance
      if signed<radius:p+=normal*(radius-signed)
     nodes[i]=world@p
   nodes[0]=pinned
  for i in range(1,len(nodes)):velocity[i]=(nodes[i]-previous[i])/dt
 for i,length in enumerate(rest):max_length_error=max(max_length_error,abs((nodes[i+1]-nodes[i]).length-length))
 min_height=min(min_height,min(p.z for p in nodes))
 store(frame)
 if frame in [160,319,478,637]:snapshots.append({'frame':frame,'knot':list(pendant.location)})
 if frame%120==0:print('ROPE_SOLVE',frame,'length_error',max_length_error,flush=True)
for ob in links+[pendant]:
 for layer in ob.animation_data.action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for key in fc.keyframe_points:key.interpolation='LINEAR'
assert max_length_error<.002,max_length_error
cloth.show_viewport=True;s.frame_set(1);s.sync_mode='FRAME_DROP'
s['Suspension solver']='Length-constrained particle rope, 18 segments plus weighted knot rod; gravity and sword collision, baked transform actions. Bullet disabled. Re-run solve_suspension_rope.py and bake_full_suspension.py after changing the demo.'
with open(os.path.join(out,'rope_solver_verification.json'),'w') as f:json.dump({'maximum_segment_length_error_m':max_length_error,'lowest_rope_height':min_height,'samples':snapshots},f,indent=2)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Reference.blend'))
print('ROPE_DONE',max_length_error,flush=True)
