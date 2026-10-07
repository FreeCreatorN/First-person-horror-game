import bpy
def play():
 for window in bpy.context.window_manager.windows:
  for area in window.screen.areas:
   if area.type=='VIEW_3D':
    with bpy.context.temp_override(window=window,area=area):
     bpy.ops.screen.animation_play()
    return None
 return 1.0
bpy.app.timers.register(play,first_interval=2.0)
