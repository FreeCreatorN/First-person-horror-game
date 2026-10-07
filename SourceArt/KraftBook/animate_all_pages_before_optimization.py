import bpy, math, json
from mathutils import Vector
from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\KraftBook')
bpy.ops.wm.open_mainfile(filepath=str(out/'KraftBook.blend'))
s=bpy.context.scene;s.render.fps=24;s.frame_start=1;s.frame_end=764
def pivot(name,objects,location):
 h=bpy.data.objects.new(name,None);s.collection.objects.link(h);h.location=location;h.empty_display_size=.006
 bpy.context.view_layer.update()
 for o in objects:
  world=o.matrix_world.copy();o.parent=h;o.matrix_world=world
 return h
def key(h,f,degrees):
 h.rotation_euler.y=math.radians(-degrees);h.keyframe_insert(data_path='rotation_euler',index=1,frame=f)
cover=pivot('Cover opening hinge',[bpy.data.objects['Front kraft cover'],bpy.data.objects['Front pressed hinge']],(-.0742,0,.01215))
for f,a in [(1,0),(10,0),(48,180),(764,180)]:key(cover,f,a)
for idx in range(112):
 old=bpy.data.objects['Paper leaf %03d'%idx]
 loc=old.location.copy();width=old.dimensions.x;length=old.dimensions.y;mat=old.data.materials[0];collection=old.users_collection[0]
 bpy.data.objects.remove(old,do_unlink=True)
 # A flexible sheet with 32 strips across its width, plus physical thickness.
 verts=[]
 for j in range(33):
  x=-width/2+width*j/32
  verts.extend([(x,-length/2,0),(x,length/2,0)])
 faces=[(2*j,2*j+2,2*j+3,2*j+1) for j in range(32)]
 mesh=bpy.data.meshes.new('Flexible paper mesh %03d'%idx);mesh.from_pydata(verts,[],faces);mesh.materials.append(mat);mesh.update()
 sheet=bpy.data.objects.new('Paper leaf %03d'%idx,mesh);collection.objects.link(sheet);sheet.location=loc
 for p in mesh.polygons:p.use_smooth=True
 sheet.shape_key_add(name='Rest');curl=sheet.shape_key_add(name='Turning curl')
 for j,v in enumerate(curl.data):
  u=(j//2)/32;v.co.z=.019*math.sin(math.pi*u)*u
 solid=sheet.modifiers.new('Paper thickness','SOLIDIFY');solid.thickness=.000155;solid.offset=0
 # Reflect each leaf through the middle of the binding: turned leaves stack bottom to top.
 h=pivot('Turn page %03d'%(112-idx),[sheet],(-.0709,0,.0124735))
 start=52+(111-idx)*6;end=start+18
 for f,a in [(1,0),(start,0),(start+9,90),(end,180),(764,180)]:key(h,f,a)
 for f,v in [(1,0),(start,0),(start+6,1),(start+12,.7),(end,0),(764,0)]:
  curl.value=v;curl.keyframe_insert(data_path='value',frame=f)
for f,name in [(1,'Closed'),(48,'Cover fully open'),(52,'First page'),(400,'Middle pages'),(736,'Last page'),(764,'All pages turned')]:s.timeline_markers.new(name,frame=f)
s.camera.location=(.29,-.44,.43);target=Vector((-.069,0,.025));s.camera.rotation_euler=(target-s.camera.location).to_track_quat('-Z','Y').to_euler();s.camera.data.ortho_scale=.47
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   v=area.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.55;v.region_3d.view_rotation=s.camera.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_extras=False
bpy.ops.object.select_all(action='DESELECT')
s.cycles.samples=16;s.render.resolution_percentage=70
for frame,name in [(400,'KraftBook_MidFlip.png'),(750,'KraftBook_LastPage.png')]:
 s.frame_set(frame);s.render.filepath=str(out/name);bpy.ops.render.render(write_still=True)
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'KraftBook_AllPages.blend'))
(out/'all_pages_report.json').write_text(json.dumps({'animated_leaves':112,'fps':24,'frames':764,'last_page_finishes':736,'duration_seconds':764/24},indent=2))
