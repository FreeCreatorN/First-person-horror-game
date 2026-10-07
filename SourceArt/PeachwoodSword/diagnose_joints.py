import bpy,json
next(m for m in bpy.data.objects['TASSEL | 96 physical silk strands'].modifiers if m.type=='CLOTH').show_viewport=False
s=bpy.context.scene;s.frame_set(1);dg=bpy.context.evaluated_depsgraph_get();pairs=[]
for o in s.rigidbody_world.constraints.objects:
 c=o.rigid_body_constraint
 if c and c.object1 and c.object2:
  a,b=c.object1,c.object2;p=o.matrix_world.translation.copy();pairs.append((o.name,a,b,a.evaluated_get(dg).matrix_world.inverted()@p,b.evaluated_get(dg).matrix_world.inverted()@p))
worst=[]
for f in range(1,161):
 s.frame_set(f);dg=bpy.context.evaluated_depsgraph_get()
 for name,a,b,pa,pb in pairs:
  p=a.evaluated_get(dg).matrix_world@pa;q=b.evaluated_get(dg).matrix_world@pb;gap=(p-q).length
  if gap>.004:worst.append((gap,f,name,list(p),list(q)))
print(json.dumps(sorted(worst,reverse=True)[:12]))
