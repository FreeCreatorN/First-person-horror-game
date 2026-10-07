import bpy, math
from mathutils import Vector
from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\KraftBook')
bpy.ops.wm.open_mainfile(filepath=str(out/'KraftBook.blend'))
s=bpy.context.scene;s.frame_start=1;s.frame_end=144;s.render.fps=24
def hinge(name,objects,pivot,keys):
 h=bpy.data.objects.new(name,None);s.collection.objects.link(h);h.location=pivot;h.empty_display_size=.015
 bpy.context.view_layer.update()
 for o in objects:
  matrix=o.matrix_world.copy();o.parent=h;o.matrix_world=matrix
 for frame,angle in keys:
  h.rotation_euler[1]=math.radians(-angle);h.keyframe_insert(data_path='rotation_euler',frame=frame,index=1)
 return h
cover=bpy.data.objects['Front kraft cover']
hinge('Cover hinge - opening',[cover,bpy.data.objects['Front pressed hinge']],(-.0742,0,.0232),[(1,0),(16,0),(80,180),(144,180)])
# Raised binding axis keeps the opened leaf above the inside cover.
page=bpy.data.objects['Paper leaf 111']
hinge('First page hinge',[page],(-.0709,0,.02345),[(1,0),(52,0),(112,180),(144,180)])
s.camera.location=(.29,-.44,.43);target=Vector((-.063,0,.035));s.camera.rotation_euler=(target-s.camera.location).to_track_quat('-Z','Y').to_euler();s.camera.data.ortho_scale=.46
for f,label in [(1,'Closed'),(16,'Cover begins'),(80,'Cover open'),(112,'Page open')]:s.timeline_markers.new(label,frame=f)
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_location=target;area.spaces.active.region_3d.view_distance=.55
   area.spaces.active.region_3d.view_rotation=s.camera.rotation_euler.to_quaternion()
   area.spaces.active.shading.color_type='MATERIAL'
   area.spaces.active.overlay.show_extras=False
bpy.ops.object.select_all(action='DESELECT')
s.frame_set(112)
s.render.filepath=str(out/'KraftBook_Open.png');s.cycles.samples=24
bpy.ops.render.render(write_still=True)
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'KraftBook_Opening.blend'))
