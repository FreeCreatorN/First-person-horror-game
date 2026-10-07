import bpy,math,json
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\RecessedLight')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.unit_settings.system='METRIC';parts=[]
def mat(name,col,metal,rough):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;return m,p
white,_=mat('M_RecessedLight_Trim',(.72,.73,.71),.15,.3)
housing,_=mat('M_RecessedLight_Housing',(.12,.14,.15),.75,.42)
black,_=mat('M_RecessedLight_Baffle',(.016,.019,.02),.1,.65)
lens,p=mat('M_RecessedLight_Diffuser',(.8,.76,.64),0,.35);p.inputs['Emission Color'].default_value=(1,.85,.62,1);p.inputs['Emission Strength'].default_value=2
def box(name,loc,size,m,bevel=.001):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);parts.append(o)
 if bevel:
  b=o.modifiers.new('Edge rounding','BEVEL');b.width=bevel;b.segments=3;o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o
# Bottom mounting plane z=0; the 1 m housing goes upward into the ceiling void.
box('Recessed enclosure',(0,0,.025),(.178,.178,.030),housing,.004)
for x in [-.095,.095]:box('Trim side',(x,0,.004),(.010,.20,.008),white,.001)
for y in [-.095,.095]:box('Trim end',(0,y,.004),(.180,.010,.008),white,.001)
box('Dark reflector backing',(0,0,.012),(.18,.18,.008),black,.002)
box('Opal light panel',(0,0,.010),(.161,.161,.006),lens,.003)
# Slots and narrow ribs on the concealed upper housing.
for side in [-1,1]:
 for j in range(3):box('Cooling fin',(side*.091,0,.021+j*.005),(.005,.150,.006),housing,.001)
 for z in [.022]:box('Mounting clip',(side*.096,0,z),(.008,.040,.016),housing,.001)
box('Rear driver cover',(0,0,.038),(.158,.158,.004),housing,.002)
for x in [-.058,.058]:
 for y in [-.058,.058]:
  bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=.0035,depth=.001,location=(x,y,.0395));o=bpy.context.object;o.name='Driver cover screw';o.data.materials.append(black);parts.append(o)
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_RecessedLight';s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.fbx(filepath=str(out/'SM_RecessedLight.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False)
target=Vector((0,0,.02));bpy.ops.object.camera_add(location=(.28,-.34,-.22));cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.32;s.camera=cam
for pos,power,size in [((1,-2,.4),250,1.5),((-1,0,1.5),300,1)]:
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
s.world.color=(.2,.2,.2);s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.render.film_transparent=True
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   v=a.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.4;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
s.render.filepath=str(out/'RecessedLight_Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'RecessedLight.blend'));bpy.ops.render.render(write_still=True)
(out/'model_report.json').write_text(json.dumps({'dimensions_cm':[d*100 for d in asset.dimensions],'ratio':'1:1:0.2','ceiling_plane_z':0},indent=2))

