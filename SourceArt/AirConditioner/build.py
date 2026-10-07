import bpy,math
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\AirConditioner')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.unit_settings.system='METRIC';parts=[]
def mat(name,col,rough=.4,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;return m
white=mat('M_AC_Ivory',(.72,.72,.66));dark=mat('M_AC_Dark',(.015,.021,.023),.55);grey=mat('M_AC_Grey',(.16,.18,.18),.5);led=mat('M_AC_Display',(.36,.65,.48));p=next(n for n in led.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Emission Color'].default_value=(.36,.65,.48,1);p.inputs['Emission Strength'].default_value=1
def box(name,loc,size,m,b=.003):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);parts.append(o)
 if b:
  be=o.modifiers.new('Soft manufactured edges','BEVEL');be.width=b;be.segments=5;o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
# Wall plane is y=0, unit projects towards -Y. Open lower outlet is built between panels.
box('Rear mounting chassis',(0,-.020,0),(.83,.04,.258),grey,.012)
box('Upper enclosure',(0,-.104,.075),(.85,.190,.145),white,.025)
box('Front fascia',(0,-.204,.046),(.818,.022,.165),white,.010)
for x in [-.422,.422]:box('Side end cap',(x,-.110,-.013),(.026,.212,.257),white,.012)
box('Outlet rear cavity',(0,-.115,-.079),(.802,.012,.087),dark,.005)
box('Bottom enclosure rail',(0,-.121,-.128),(.826,.188,.021),white,.009)
for x in [-.39,.39]:box('Outlet side liner',(x,-.155,-.082),(.013,.083,.076),dark,.004)
# Vertical internal guide fins are inside the dark cavity, not stuck to the outside.
for j in range(21):
 o=box('Internal guide vane',(-.365+j*.0365,-.155,-.082),(.003,.061,.065),grey,.001);o.rotation_euler.z=math.radians(-12)
for z in [-.065,-.100]:
 o=box('Horizontal airflow blade',(0,-.190,z),(.767,.048,.006),white,.002);o.rotation_euler.x=math.radians(-18)
for x in [-.382,.382]:box('Louvre pivot support',(x,-.180,-.080),(.009,.048,.075),grey,.003)
# Top intake is a recessed dark bed with closely spaced grille ribs.
box('Top intake recess',(0,-.096,.148),(.730,.104,.003),dark,.004)
for i in range(42):box('Intake grille rib',(-.351+i*.0171,-.096,.149),(.009,.104,.006),white,.0015)
box('Front opening seam',(0,-.216,-.027),(.775,.0015,.0017),grey,.0005)
box('Display smoked window',(.274,-.216,.055),(.087,.002,.045),dark,.005)
def label(txt,loc,size,m,name):
 c=bpy.data.curves.new(name,'FONT');c.body=txt;c.align_x='CENTER';c.size=size;c.extrude=.000015;o=bpy.data.objects.new(name,c);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(math.pi/2,0,0);c.materials.append(m);parts.append(o)
label('24',(.270,-.2171,.049),.026,led,'Temperature display')
label('AIR',(-.30,-.21505,.069),.012,grey,'Printed brand')
box('Receiver',(.330,-.216,.056),(.012,.0015,.007),grey,.002)
for x in [-.39,.39]:
 bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.0035,depth=.002,location=(x,-.141,-.140));o=bpy.context.object;o.name='Underside screw';o.data.materials.append(grey);parts.append(o)
# Short conduit terminates at the wall so the model is ready to mount.
box('Pipe outlet cover',(.36,-.017,-.109),(.07,.028,.037),white,.01)
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_AirConditioner';s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.fbx(filepath=str(out/'SM_AirConditioner.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False)
target=Vector((0,-.09,0));bpy.ops.object.camera_add(location=(1,-1.8,.55));cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.12;s.camera=cam
for loc,power,size in [((0,-1,1.5),120,1.2),((-1,-.3,.2),70,.8)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
s.world.color=(.22,.22,.22);s.render.engine='CYCLES';s.cycles.samples=40;s.cycles.use_denoising=True;s.render.resolution_x=1400;s.render.resolution_y=850;s.render.resolution_percentage=100;s.render.film_transparent=True
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   v=a.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=1.3;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
s.render.filepath=str(out/'AirConditioner_Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'AirConditioner.blend'));bpy.ops.render.render(write_still=True)

