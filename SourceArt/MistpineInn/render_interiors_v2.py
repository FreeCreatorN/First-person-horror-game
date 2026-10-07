import bpy,os
s=bpy.context.scene;out=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn'
bindings=[(m,m.camera) for m in s.timeline_markers]
for m,c in bindings:m.camera=None
s.render.resolution_x=1200;s.render.resolution_y=850;s.cycles.samples=24
for name,cam in [('Refined_Lobby','CAM 02 Lobby'),('Refined_GuestRoom','CAM 04 Guest room'),('Refined_Corridor','CAM 03 Corridor')]:
 s.camera=bpy.data.objects[cam];s.render.filepath=os.path.join(out,name+'.png');bpy.ops.render.render(write_still=True)
for m,c in bindings:m.camera=c
s.frame_set(1);s.camera=bpy.data.objects['CAM 01 Exterior']
print('PREVIEWS_SAVED')
