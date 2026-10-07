import bpy, math, json
from mathutils import Vector
from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\KraftBook')
bpy.ops.wm.open_mainfile(filepath=str(out/'KraftBook.blend'))
s=bpy.context.scene;s.render.fps=24;s.frame_start=1;s.frame_end=1428
def pivot(name,objects,location):
 h=bpy.data.objects.new(name,None);s.collection.objects.link(h);h.location=location;h.empty_display_size=.006
 bpy.context.view_layer.update()
 for o in objects:
  world=o.matrix_world.copy();o.parent=h;o.matrix_world=world
 return h
def key(h,f,degrees):
 h.rotation_euler.y=math.radians(-degrees);h.keyframe_insert(data_path='rotation_euler',index=1,frame=f)
bpy.data.objects['Continuous rounded kraft spine'].dimensions.x=.0022
spine=pivot('Spine lays flat',[bpy.data.objects['Continuous rounded kraft spine']],(-.0742,0,.0011))
cover=pivot('Cover opening hinge',[bpy.data.objects['Front kraft cover'],bpy.data.objects['Front pressed hinge']],(-.0742,0,.0232))
world=cover.matrix_world.copy();cover.parent=spine;cover.matrix_world=world
for f,a in [(1,0),(10,0),(48,90),(1428,90)]:
 key(spine,f,a);key(cover,f,a)
for idx in range(112):
 old=bpy.data.objects['Paper leaf %03d'%idx]
 loc=old.location.copy();width=old.dimensions.x;length=old.dimensions.y;mat=old.data.materials[0];collection=old.users_collection[0]
 bpy.data.objects.remove(old,do_unlink=True)
 # An animated surface, with its binding edge sliding across the open spine.
 verts=[]
 for j in range(33):
  x=-width/2+width*j/32
  verts.extend([(x,-length/2,0),(x,length/2,0)])
 faces=[(2*j,2*j+2,2*j+3,2*j+1) for j in range(32)]
 mesh=bpy.data.meshes.new('Flexible paper mesh %03d'%idx);mesh.from_pydata(verts,[],faces);mesh.materials.append(mat);mesh.update()
 sheet=bpy.data.objects.new('Paper leaf %03d'%idx,mesh);collection.objects.link(sheet);sheet.location=loc
 for p in mesh.polygons:p.use_smooth=True
 sheet.shape_key_add(name='Rest')
 binding=sheet.shape_key_add(name='Flexible bound margin')
 bindx=-.08325;bindz=.0025+idx*.000002
 for j,v in enumerate(binding.data):
  u=(j//2)/32;q=min(1,u/.125);q=q*q*(3-2*q)
  v.co.x=(bindx*(1-q)+(loc.x-width/2+width*u)*q)-loc.x
  v.co.z=(bindz*(1-q)+loc.z*q)-loc.z
 for f,val in [(1,0),(10,0),(48,1),(1428,1)]:
  binding.value=val;binding.keyframe_insert(data_path='value',frame=f)
 solid=sheet.modifiers.new('Paper thickness','SOLIDIFY');solid.thickness=.000155;solid.offset=0
 start=60+(111-idx)*12;end=start+12
 # One leaf at a time avoids intersecting fans; easing is sampled into shape keys.
 for step in range(1,13):
  t=step/12;ease=t*t*(3-2*t);angle=math.pi*ease
  shape=sheet.shape_key_add(name='Turn %02d'%step)
  shape.relative_key=binding
  rootx=(loc.x-width/2)*(1-ease)+(-.0963)*ease
  targetz=.00265+(111-idx)*.000177
  rootz=loc.z*(1-ease)+targetz*ease+.004*math.sin(math.pi*ease)
  for j,v in enumerate(shape.data):
   u=(j//2)/32;distance=width*u
   bend=.012*math.sin(math.pi*ease)*math.sin(math.pi*u)
   x=rootx+distance*math.cos(angle)-bend*math.sin(angle)
   z=rootz+distance*math.sin(angle)+bend*math.cos(angle)
   q=min(1,u/.125);q=q*q*(3-2*q)
   x=bindx*(1-q)+x*q;z=bindz*(1-q)+z*q
   v.co.x=x-loc.x;v.co.z=z-loc.z
  for frame,value in [(1,0),(start+step-1,0),(start+step,1)]:
   shape.value=value;shape.keyframe_insert(data_path='value',frame=frame)
  if step<12:
   shape.value=0;shape.keyframe_insert(data_path='value',frame=start+step+1)
  else:
   shape.value=1;shape.keyframe_insert(data_path='value',frame=1428)
 # Linear blending between sampled shapes avoids overshoot through adjacent leaves.
 action=sheet.data.shape_keys.animation_data.action
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     for point in fc.keyframe_points:point.interpolation='LINEAR'
for f,name in [(1,'Closed'),(48,'Spine and cover flat'),(60,'First page'),(726,'Middle pages'),(1404,'Last page complete'),(1428,'All pages turned')]:s.timeline_markers.new(name,frame=f)
s.camera.location=(.29,-.44,.43);target=Vector((-.083,0,.025));s.camera.rotation_euler=(target-s.camera.location).to_track_quat('-Z','Y').to_euler();s.camera.data.ortho_scale=.49
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   v=area.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.55;v.region_3d.view_rotation=s.camera.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
bpy.ops.object.select_all(action='DESELECT')
s.cycles.samples=16;s.render.resolution_percentage=70
for frame,name in [(726,'KraftBook_Optimized_MidFlip.png'),(1410,'KraftBook_Optimized_LastPage.png')]:
 s.frame_set(frame);s.render.filepath=str(out/name);bpy.ops.render.render(write_still=True)
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'KraftBook_AllPages_Optimized.blend'))
(out/'all_pages_report.json').write_text(json.dumps({'animated_leaves':112,'fps':24,'frames':1428,'last_page_finishes':1404,'duration_seconds':1428/24,'spine_folds_flat':True,'one_leaf_at_a_time':True},indent=2))
