import bpy, math
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\KraftBook')
bpy.ops.wm.open_mainfile(filepath=str(out/'KraftBook_AllPages_Optimized.blend'))
s=bpy.context.scene
# Bake opening world transforms before freeing the covers from the opening rig.
for name in ['Front kraft cover','Front pressed hinge','Continuous rounded kraft spine']:
 o=bpy.data.objects[name];samples=[]
 for f in range(1,49):
  s.frame_set(f);samples.append((f,o.matrix_world.copy()))
 o.parent=None;o.animation_data_clear()
 for f,m in samples:
  o.matrix_world=m;o.keyframe_insert(data_path='location',frame=f);o.keyframe_insert(data_path='rotation_euler',frame=f);o.keyframe_insert(data_path='scale',frame=f)
 o.keyframe_insert(data_path='location',frame=1428);o.keyframe_insert(data_path='rotation_euler',frame=1428)
s.frame_set(1428)
spine=bpy.data.objects['Continuous rounded kraft spine']
spine.location=(-.0963,0,.01215);spine.rotation_euler=(0,0,0)
spine.keyframe_insert(data_path='location',frame=1488);spine.keyframe_insert(data_path='rotation_euler',frame=1488)
# Close the back cover over the pages now stacked on the left.
h=bpy.data.objects.new('Back cover closing hinge',None);s.collection.objects.link(h);h.location=(-.0742,0,.0011)
bpy.context.view_layer.update()
for name in ['Back kraft cover','Back pressed hinge','Bookmark ribbon']:
 o=bpy.data.objects[name];world=o.matrix_world.copy();o.parent=h;o.matrix_world=world
for frame,angle,pos in [(1,0,(-.0742,0,.0011)),(1428,0,(-.0742,0,.0011)),(1488,-math.pi,(-.0963,0,.0232))]:
 h.location=pos;h.rotation_euler.y=angle;h.keyframe_insert(data_path='location',frame=frame);h.keyframe_insert(data_path='rotation_euler',frame=frame)
for idx in range(112):
 o=bpy.data.objects['Paper leaf %03d'%idx];keys=o.data.shape_keys
 final=keys.key_blocks['Turn 12'];closed=o.shape_key_add(name='Closed binding on left');closed.relative_key=final
 # End leaves lie flat between both covers, including their inner margins.
 width=o.data.vertices[-1].co.x-o.data.vertices[0].co.x
 z=.00265+(111-idx)*.000177
 for j,v in enumerate(closed.data):
  u=(j//2)/32;v.co.x=-.0963-width*u-o.location.x;v.co.z=z-o.location.z
 for f,val in [(1,0),(1428,0),(1488,1)]:closed.value=val;closed.keyframe_insert(data_path='value',frame=f)
# Hold the initial closed pose for two seconds by shifting all animation.
for action in bpy.data.actions:
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for k in fc.keyframe_points:
      k.co.x+=48;k.handle_left.x+=48;k.handle_right.x+=48
for marker in s.timeline_markers:marker.frame+=48
s.timeline_markers.new('Closing back cover',frame=1476);s.timeline_markers.new('Closed - end',frame=1536)
s.frame_end=1632
s.frame_set(1600);s.render.filepath=str(out/'KraftBook_Closed_End.png');bpy.ops.render.render(write_still=True)
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'KraftBook_FullCycle.blend'))
