import bpy,math,bmesh
from mathutils import Vector
from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\WaterDispenser')
# Reuse the modelling helpers, replacing the first model before its export stage.
src=(out/'build.py').read_text(encoding='utf-8-sig');exec(src.split('# Export only the asset')[0])
def remove_prefix(prefix):
 for o in list(parts):
  if o.name.startswith(prefix):parts.remove(o);bpy.data.objects.remove(o,do_unlink=True)
for prefix in ['Main cabinet','Recess surround','Recess back','Tap canopy','Tap mounting','Tap forward','Downward outlet','Outlet opening','Push lever','Drip tray','Tray grille','Drain slot','Bottle socket','Inverted water bottle','Bottle reinforcement','Vent louvre']:remove_prefix(prefix)
# Cabinet built from real walls around an open dispensing bay.
box('Lower cabinet',(0,.009,.287),(.32,.292,.474),cream,.013)
box('Left structural side',(-.148,0,.697),(.024,.302,.346),cream,.009)
box('Right structural side',(.148,0,.697),(.024,.302,.346),cream,.009)
box('Upper machinery compartment',(0,.01,.84),(.284,.278,.055),cream,.008)
box('Bay rear wall',(0,-.07,.685),(.273,.014,.269),dark,.006)
box('Bay left liner',(-.134,-.105,.685),(.006,.082,.269),dark,.003)
box('Bay right liner',(.134,-.105,.685),(.006,.082,.269),dark,.003)
box('Bay overhead liner',(0,-.104,.810),(.269,.085,.009),dark,.003)
box('Tap fascia',(0,-.158,.805),(.274,.028,.059),cream,.007)
def text_obj(text,loc,size,material,name):
 c=bpy.data.curves.new(name,'FONT');c.body=text;c.size=size;c.align_x='CENTER';c.extrude=.00003
 o=bpy.data.objects.new(name,c);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(math.pi/2,0,0);c.materials.append(material);parts.append(o);return o
text_obj('AQUA  /  02',(0,-.160,.848),.012,dark,'Maker label')
for x,color,label in [(-.066,red,'HOT'),(.066,blue,'COLD')]:
 cyl('Tap base flange',(x,-.184,.785),.020,.019,dark,(math.pi/2,0,0))
 cyl('Valve barrel',(x,-.202,.785),.014,.035,cream,(math.pi/2,0,0))
 cyl('Valve cap',(x,-.224,.785),.0125,.011,color,(math.pi/2,0,0))
 # Hollow nozzle, including a dark bore recessed inside its lip.
 cyl('Nozzle body',(x,-.212,.765),.0095,.030,cream)
 bpy.ops.mesh.primitive_torus_add(major_radius=.0078,minor_radius=.0016,major_segments=48,minor_segments=12,location=(x,-.212,.749));o=finish(bpy.context.object,'Nozzle rounded lip',cream)
 for p in o.data.polygons:p.use_smooth=True
 cyl('Recessed nozzle bore',(x,-.212,.751),.0063,.0006,dark)
 box('Lever stem',(x,-.197,.809),(.009,.011,.029),color,.003)
 box('Thumb paddle',(x,-.206,.825),(.030,.037,.009),color,.004)
 if label=='HOT':box('Hot safety latch',(x,-.213,.833),(.010,.017,.006),dark,.002)
 text_obj(label,(x,-.174,.793),.008,color,label+' lettering')
# Recessed tray basin with separate support ribs and drain underneath.
box('Drip pan floor',(0,-.162,.526),(.281,.171,.010),dark,.006)
for x in [-.137,.137]:box('Tray side rim',(x,-.162,.538),(.008,.171,.022),cream,.003)
for y in [-.244,-.081]:box('Tray end rim',(0,y,.538),(.274,.008,.022),cream,.003)
for i in range(16):box('Removable grille bar',(-.123+i*.0164,-.163,.543),(.008,.151,.006),steel,.002)
cyl('Drain sump',(0,-.15,.533),.025,.004,dark)
box('Tray pull grip',(0,-.25,.53),(.061,.014,.016),dark,.004)
# Rear service panel, fan openings and visible fasteners.
box('Rear service panel',(0,.160,.443),(.276,.008,.71),dark,.009)
for j in range(15):box('Rear vent opening',(0,.165,.52+j*.015),(.216,.004,.006),steel,.001)
for x in [-.122,.122]:
 for z in [.11,.77]:
  cyl('Rear screw',(x,.167,z),.0033,.003,steel,(math.pi/2,0,0))
for j in range(6):
 for x in [-.055,.055]:box('Front vent grille',(x,-.165,.126+j*.014),(.091,.004,.005),dark,.001)
def tube(name,points,r,material):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=16;c.bevel_depth=r;c.bevel_resolution=4;sp=c.splines.new('BEZIER');sp.bezier_points.add(len(points)-1)
 for p,co in zip(sp.bezier_points,points):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
 o=bpy.data.objects.new(name,c);s.collection.objects.link(o);c.materials.append(material);parts.append(o);return o
tube('Power cable',[(.09,.169,.20),(.095,.20,.16),(.10,.22,.05),(.13,.25,.009),(.23,.25,.008),(.28,.19,.008)],.0035,dark)
box('Plug body',(.29,.18,.012),(.028,.038,.020),dark,.005)
for x in [.282,.299]:box('Plug pin',(x,.151,.012),(.004,.019,.004),steel,.0007)
# Rebuild bottle as a thin shell: the original solid volume looked like a glass ornament.
cyl('Bottle docking collar',(0,0,.920),.064,.035,cream)
cyl('Bottle neck gasket',(0,0,.938),.042,.006,dark)
profile=[(.034,.933),(.034,.963),(.045,.978),(.084,1.006),(.117,1.035),(.133,1.057),(.135,1.081),(.135,1.264),(.132,1.291),(.121,1.310),(.102,1.320),(.055,1.324),(0,1.324)]
N=128;vs=[(r*math.cos(j*math.tau/N),r*math.sin(j*math.tau/N),z) for r,z in profile for j in range(N)]
fs=[(k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j) for k in range(len(profile)-1) for j in range(N)]
me=bpy.data.meshes.new('Thin bottle shell');me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new('Bottle thin wall',me);s.collection.objects.link(o);finish(o,o.name,bottle)
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
for p in me.polygons:p.use_smooth=True
sub=o.modifiers.new('Bottle mould rounding','SUBSURF');sub.levels=2
solid=o.modifiers.new('Plastic wall thickness','SOLIDIFY');solid.thickness=.0018
for z in [1.083,1.105,1.256,1.278]:
 bpy.ops.mesh.primitive_torus_add(major_radius=.1345,minor_radius=.003,major_segments=128,minor_segments=12,location=(0,0,z));o=finish(bpy.context.object,'Bottle mould rib',bottle)
 for p in o.data.polygons:p.use_smooth=True
# Low-key physical mould seam, rather than raised decorative bands everywhere.
text_obj('19 L',(0,-.137,1.169),.017,blue,'Bottle capacity marking')
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_WaterDispenser';s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.015);bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.fbx(filepath=str(out/'SM_WaterDispenser.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False)
floor=mat('Preview floor',(.13,.14,.14),.8);bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.002));bpy.context.object.data.materials.append(floor)
target=Vector((.025,0,.67));bpy.ops.object.camera_add(location=(2,-3,1.85));cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.65;s.camera=cam
for loc,power,size in [((1,-2,3),450,2),((-2,0,2),350,1.5)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
s.world.color=(.22,.22,.22);s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.render.resolution_x=1100;s.render.resolution_y=1300;s.render.resolution_percentage=100
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   v=a.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=2;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
s.render.filepath=str(out/'WaterDispenser_Refined.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'WaterDispenser_Refined.blend'));bpy.ops.render.render(write_still=True)
