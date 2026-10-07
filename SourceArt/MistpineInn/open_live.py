import bpy, json, os
path=r'D:\UE\Project\HorrorGame\SourceArt\MistpineInn\MistpineInn.blend'
if bpy.data.is_dirty and bpy.data.filepath and bpy.data.filepath!=path:
 backup=bpy.data.filepath+'.before_inn.blend'
 bpy.ops.wm.save_as_mainfile(filepath=backup,copy=True)
bpy.ops.wm.open_mainfile(filepath=path)
s=bpy.context.scene;s.frame_set(1);s.camera=bpy.data.objects['CAM 01 Exterior']
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_perspective='CAMERA'
   area.spaces.active.overlay.show_overlays=False
   area.spaces.active.shading.type='MATERIAL'
print(json.dumps({'file':bpy.data.filepath,'objects':len(s.objects),'cameras':[o.name for o in s.objects if o.type=='CAMERA'],'frame':s.frame_current}))
