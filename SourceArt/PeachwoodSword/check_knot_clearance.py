import bpy,json,os
from mathutils.bvhtree import BVHTree
scene=bpy.context.scene
next(m for m in bpy.data.objects['TASSEL | 96 physical silk strands'].modifiers if m.type=='CLOTH').show_viewport=False
scene.frame_set(1);dg=bpy.context.evaluated_depsgraph_get();root=bpy.data.objects['SWORD_CONTROL | reference design']
body=bpy.data.objects['SUSPENSION | hanging knot body'];bvhs=[]
for name in ['Cloud silhouette carved crossguard','Peachwood blade | broad engraved face','Handle wood core','Round cloud-carved pommel']:
 ob=bpy.data.objects[name];ev=ob.evaluated_get(dg);me=ev.to_mesh();matrix=root.matrix_world.inverted()@ev.matrix_world
 bvhs.append(BVHTree.FromPolygons([matrix@v.co for v in me.vertices],[list(p.vertices) for p in me.polygons]));ev.to_mesh_clear()
worst=(100,1);inside=0
for f in range(1,scene.frame_end+1):
 scene.frame_set(f);dg=bpy.context.evaluated_depsgraph_get();matrix=root.matrix_world.inverted()@body.evaluated_get(dg).matrix_world
 for v in body.data.vertices:
  p=matrix@v.co
  for bvh in bvhs:
   pos,n,idx,dist=bvh.find_nearest(p);signed=dist if (p-pos).dot(n)>=0 else -dist
   if signed<worst[0]:worst=(signed,f)
   if signed<-.0005:inside+=1
report={'knot_hull_penetrating_samples':inside,'minimum_clearance_m':worst[0],'worst_frame':worst[1]}
with open(r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword\knot_clearance.json','w') as f:json.dump(report,f)
print(json.dumps(report))
