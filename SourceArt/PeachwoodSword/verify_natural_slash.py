import bpy,json,math,os
from mathutils import Vector
from mathutils.bvhtree import BVHTree
s=bpy.context.scene;out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
r=bpy.data.objects['SWORD_CONTROL | reference design'];ta=bpy.data.objects['TASSEL | 96 physical silk strands'];cl=next(m for m in ta.modifiers if m.type=='CLOTH');pend=bpy.data.objects['SUSPENSION | hanging knot body']
cl.show_viewport=True;s.frame_set(240);dg=bpy.context.evaluated_depsgraph_get()
colliders=[]
for name in ['Cloud silhouette carved crossguard','Peachwood blade | broad engraved face','Handle wood core','Round cloud-carved pommel']:
 o=bpy.data.objects[name];ev=o.evaluated_get(dg);me=ev.to_mesh();colliders.append((o,BVHTree.FromPolygons([v.co.copy() for v in me.vertices],[list(p.vertices) for p in me.polygons])));ev.to_mesh_clear()
lastq=None;flips=[];worst=0;penetrations=0;maxpin=0;lowest=100;maxspan=0
pins=[v.index for v in ta.data.vertices if any(g.weight>.99 for g in v.groups)]
for f in range(240,781):
 s.frame_set(f);q=r.rotation_quaternion.copy()
 if lastq is not None:
  if q.dot(lastq)<0:flips.append(f)
  worst=max(worst,2*math.acos(min(1,abs(q.dot(lastq)))))
 lastq=q
 if f%6:continue
 dg=bpy.context.evaluated_depsgraph_get();ev=ta.evaluated_get(dg);me=ev.to_mesh();m=ev.matrix_world
 matrices=[(o.matrix_world.inverted(),bvh) for o,bvh in colliders]
 for v in list(me.vertices)[:len(ta.data.vertices):20]:
  p=m@v.co;lowest=min(lowest,p.z);maxspan=max(maxspan,(p-pend.matrix_world.translation).length)
  for inv,bvh in matrices:
   x=inv@p;near,normal,idx,d=bvh.find_nearest(x)
   if idx is not None and (x-near).dot(normal)<-.0005:penetrations+=1
 for i in pins:maxpin=max(maxpin,(m@me.vertices[i].co-m@ta.data.vertices[i].co).length)
 ev.to_mesh_clear()
result={'cloth_baked':cl.point_cache.is_baked,'rotation_sign_flips':flips,'max_sword_rotation_step_degrees':math.degrees(worst),'sampled_penetrations':penetrations,'max_pin_error_m':maxpin,'lowest_silk_z':lowest,'max_silk_distance_from_pendant_m':maxspan}
with open(os.path.join(out,'natural_slash_check.json'),'w') as f:json.dump(result,f,indent=2)
s.frame_set(390);s.render.resolution_x=900;s.render.resolution_y=900;s.cycles.samples=20;s.render.filepath=os.path.join(out,'NaturalSlash_Preview.png');bpy.ops.render.render(write_still=True)
s.frame_set(240)
