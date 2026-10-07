import bpy,math,json
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\WaterDispenser')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.unit_settings.system='METRIC';parts=[]
def mat(name,col,rough=.4,metal=0,trans=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;p.inputs['Transmission Weight'].default_value=trans;p.inputs['IOR'].default_value=1.46;return m
cream=mat('M_Dispenser_Cream',(.65,.62,.53));dark=mat('M_Dispenser_Charcoal',(.024,.029,.029),.5);steel=mat('M_Dispenser_Steel',(.37,.40,.41),.25,.8);red=mat('M_Dispenser_Red',(.4,.025,.018));blue=mat('M_Dispenser_Blue',(.018,.11,.32));bottle=mat('M_Dispenser_Bottle',(.20,.46,.58),.15,0,.82)
def finish(o,name,m,bevel=0):
 o.name=name;o.data.materials.append(m);parts.append(o)
 if bevel:
  b=o.modifiers.new('Rounded edges','BEVEL');b.width=bevel;b.segments=3;o.modifiers.new('Face normals','WEIGHTED_NORMAL')
 return o
def box(name,loc,size,m,b=.004):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return finish(o,name,m,b)
def cyl(name,loc,r,d,m,rot=(0,0,0)):
 bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=r,depth=d,location=loc,rotation=rot);o=finish(bpy.context.object,name,m,.0015)
 for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
 return o
box('Main cabinet',(0,.005,.45),(.32,.30,.85),cream,.018)
box('Bottom plinth',(0,0,.043),(.328,.312,.056),dark,.01)
for x in [-.115,.115]:
 for y in [-.105,.105]:cyl('Rubber foot',(x,y,.013),.021,.026,dark)
box('Upper housing',(0,0,.877),(.332,.314,.065),cream,.018)
cyl('Bottle socket',(0,0,.914),.079,.025,dark)
# Front dispensing recess is an inset dark surround with a protruding canopy.
box('Recess surround',(0,-.151,.673),(.281,.017,.276),dark,.014)
box('Recess back',(0,-.165,.672),(.247,.011,.239),steel,.01)
box('Tap canopy',(0,-.193,.819),(.287,.104,.042),cream,.008)
for x,m in [(-.068,red),(.068,blue)]:
 cyl('Tap mounting boss',(x,-.184,.776),.023,.026,dark,(math.pi/2,0,0))
 cyl('Tap forward barrel',(x,-.212,.776),.015,.052,cream,(math.pi/2,0,0))
 cyl('Downward outlet',(x,-.238,.757),.011,.037,cream)
 cyl('Outlet opening',(x,-.238,.738),.0075,.001,dark)
 box('Push lever',(x,-.225,.800),(.031,.052,.013),m,.005)
box('Drip tray',(0,-.196,.526),(.282,.131,.025),dark,.008)
box('Tray grille',(0,-.197,.539),(.259,.112,.007),steel,.003)
for i in range(13):box('Drain slot',(-.117+i*.0195,-.202,.543),(.006,.084,.001),dark,.002)
box('Lower door seam',(0,-.151,.276),(.275,.008,.402),dark,.01)
box('Lower service panel',(0,-.158,.276),(.264,.009,.391),cream,.008)
for j in range(7):box('Vent louvre',(0,-.164,.133+j*.015),(.20,.004,.004),dark,.001)
box('Service latch',(0,-.166,.44),(.035,.007,.006),dark,.002)
for x,m in [(-.032,red),(0,blue),(.032,dark)]:cyl('Status indicator',(x,-.161,.869),.004,.002,m,(math.pi/2,0,0))
# Inverted water bottle: rounded shoulder, moulded reinforcement bands, closed base.
profile=[(0,.919),(.031,.919),(.033,.96),(.055,.98),(.094,1.01),(.125,1.043),(.132,1.064),(.132,1.273),(.128,1.294),(.115,1.309),(.06,1.315),(0,1.315)]
N=96;v=[(r*math.cos(j*math.tau/N),r*math.sin(j*math.tau/N),z) for r,z in profile for j in range(N)]
f=[(k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j) for k in range(len(profile)-1) for j in range(N)]
me=bpy.data.meshes.new('Bottle shell');me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new('Inverted water bottle',me);s.collection.objects.link(o);finish(o,o.name,bottle)
import bmesh
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
for p in me.polygons:p.use_smooth=True
sub=o.modifiers.new('Moulded bottle curves','SUBSURF');sub.levels=2
for z in [1.075,1.101,1.238,1.264]:
 bpy.ops.mesh.primitive_torus_add(major_radius=.131,minor_radius=.0035,major_segments=96,minor_segments=12,location=(0,0,z));o=finish(bpy.context.object,'Bottle reinforcement rib',bottle)
 for p in o.data.polygons:p.use_smooth=True
# Export only the asset, with UVs and a grounded pivot.
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0]
bpy.ops.object.convert(target='MESH');bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_WaterDispenser';s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.015);bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.fbx(filepath=str(out/'SM_WaterDispenser.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False)
floor=mat('Preview floor',(.13,.14,.14),.8);bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.002));bpy.context.object.data.materials.append(floor)
target=Vector((0,0,.67));bpy.ops.object.camera_add(location=(2,-3,1.85));cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.65;s.camera=cam
for loc,power,size in [((1,-2,3),450,2),((-2,0,2),350,1.5)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
s.world.color=(.22,.22,.22);s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.render.resolution_x=1000;s.render.resolution_y=1200;s.render.resolution_percentage=100
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
for screen in bpy.data.screens:
 for ar in screen.areas:
  if ar.type=='VIEW_3D':
   a=ar.spaces.active;a.region_3d.view_location=target;a.region_3d.view_distance=2;a.region_3d.view_rotation=cam.rotation_euler.to_quaternion();a.shading.color_type='MATERIAL';a.overlay.show_overlays=False
s.render.filepath=str(out/'WaterDispenser_Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'WaterDispenser.blend'));bpy.ops.render.render(write_still=True)
