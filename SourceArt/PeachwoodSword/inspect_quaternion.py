import bpy,math
s=bpy.context.scene;r=bpy.data.objects['SWORD_CONTROL | reference design'];last=None;bad=[];maxstep=0
for f in range(1,781):
 s.frame_set(f);q=r.rotation_quaternion.copy()
 if last is not None:
  if q.dot(last)<0:bad.append(f)
  maxstep=max(maxstep,q.rotation_difference(last).angle)
 last=q
result={'sign_flips':bad,'max_quaternion_step':maxstep}
s.frame_set(240)
