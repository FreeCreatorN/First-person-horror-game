import bpy
s=bpy.context.scene;s.frame_set(1)
for a in bpy.context.screen.areas:
 if a.type=='VIEW_3D':
  with bpy.context.temp_override(area=a):bpy.ops.screen.animation_play()
  break
result={'playing':bpy.context.screen.is_animation_playing}
