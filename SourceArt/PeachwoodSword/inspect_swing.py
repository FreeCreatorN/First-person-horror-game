import bpy, json
s=bpy.context.scene
if bpy.context.screen.is_animation_playing:bpy.ops.screen.animation_cancel(restore_frame=False)
s.frame_set(1)
root=bpy.data.objects['SWORD_CONTROL | reference design'];ta=bpy.data.objects['TASSEL | 96 physical silk strands'];p=bpy.data.objects['SUSPENSION | hanging knot body']
result={'root':list(root.location),'grip':list(bpy.data.objects['Handle wood core'].matrix_world.translation),'pendant':list(p.matrix_world.translation),'cloth':{k:getattr(next(m for m in ta.modifiers if m.type=='CLOTH').settings,k) for k in ['mass','air_damping','bending_stiffness','quality','time_scale']},'poses':[]}
for f in [1,70,150,190,200,210,220,230,265,410,480]:
 s.frame_set(f);result['poses'].append((f,list(root.rotation_euler),list(bpy.data.objects['Handle wood core'].matrix_world.translation)))
s.frame_set(1)
