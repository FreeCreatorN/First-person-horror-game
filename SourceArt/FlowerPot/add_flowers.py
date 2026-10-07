import bpy,math,random
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\FlowerPot');random.seed(18)
bpy.ops.wm.open_mainfile(filepath=str(out/'FlowerPot.blend'))
s=bpy.context.scene;pot=bpy.data.objects['SM_FlowerPot'];parts=[pot]
def material(name,col):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=.7;return m
soil=material('M_FlowerPot_Soil',(.046,.026,.012));green=material('M_FlowerPot_Green',(.07,.19,.035));white=material('M_FlowerPot_Petals',(.88,.82,.66));gold=material('M_FlowerPot_Pollen',(.65,.30,.022))
def sphere(name,pos,scale,mat,seg=20,rings=12):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=seg,ring_count=rings,location=pos);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
 for p in o.data.polygons:p.use_smooth=True
 parts.append(o);return o
sphere('Soil surface',(0,0,.183),(.096,.096,.013),soil,64,20)
for i in range(65):
 a=random.random()*math.tau;r=.089*math.sqrt(random.random());size=random.uniform(.0015,.0035)
 sphere('Soil granule',(r*math.cos(a),r*math.sin(a),.193), (size,size,size*.65),soil,8,6)
def tube(name,pts,r):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=3;c.resolution_u=12;sp=c.splines.new('BEZIER');sp.bezier_points.add(len(pts)-1)
 for p,co in zip(sp.bezier_points,pts):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
 o=bpy.data.objects.new(name,c);s.collection.objects.link(o);c.materials.append(green);parts.append(o)
heads=[(-.066,-.017,.365),(.017,-.048,.385),(.066,.003,.393),(-.034,.035,.430),(.015,.033,.464),(-.003,-.004,.417),(.059,.052,.441)]
for idx,head in enumerate(heads):
 h=Vector(head);base=Vector((h.x*.45,h.y*.45,.192));mid=base.lerp(h,.52)+Vector((.009,0,0));tube('Flower stem',[base,mid,h],.0018)
 for k in range(3):
  at=base.lerp(h,.22+k*.18);a=idx*2.3+k*2.6;direction=Vector((math.cos(a),math.sin(a),.35)).normalized();length=.045+k*.005
  tube('Leaf stalk',[at,at+direction*.012],.001)
  # Pointed curved leaf with a raised central vein.
  side=Vector((-direction.y,direction.x,0)).normalized();v=[]
  for j in range(9):
   u=j/8;center=at+direction*(.008+length*u)+Vector((0,0,.006*math.sin(math.pi*u)));w=.011*math.sin(math.pi*u)
   v.extend([tuple(center-side*w),tuple(center+Vector((0,0,.002*math.sin(math.pi*u)))),tuple(center+side*w)])
  f=[(j*3+q,(j+1)*3+q,(j+1)*3+q+1,j*3+q+1) for j in range(8) for q in range(2)]
  me=bpy.data.meshes.new('Leaf');me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new('Pointed leaf',me);s.collection.objects.link(o);me.materials.append(green);parts.append(o)
  sol=o.modifiers.new('Leaf thickness','SOLIDIFY');sol.thickness=.0003
  for p in me.polygons:p.use_smooth=True
 # Each flower has a slightly tilted petal rosette and a textured gold centre.
 normal=Vector((h.x*2,h.y*2,1)).normalized();rot=Vector((0,0,1)).rotation_difference(normal)
 for j in range(13):
  a=j*math.tau/13;radial=Vector((math.cos(a),math.sin(a),0));pos=h+rot@(radial*.019)
  o=sphere('Ivory petal',pos,(.016,.005,.0017),white);o.rotation_mode='QUATERNION';o.rotation_quaternion=rot@Vector((1,0,0)).rotation_difference(radial)
 o=sphere('Golden flower centre',h+normal*.002,(.010,.010,.004),gold);o.rotation_mode='QUATERNION';o.rotation_quaternion=rot
 for j in range(24):
  a=j*2.39996;r=.008*math.sqrt((j+.5)/24);pos=h+rot@Vector((r*math.cos(a),r*math.sin(a),.005));sphere('Pollen detail',pos,(.0009,.0009,.0008),gold,8,6)
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=pot;bpy.ops.object.convert(target='MESH');bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_FlowerPot'
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.01);bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.fbx(filepath=str(out/'SM_FlowerPot.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False)
target=Vector((0,0,.24));cam=s.camera;cam.location=(.5,-.7,.57);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.60
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.region_3d.view_location=target;a.spaces.active.region_3d.view_distance=.75;a.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
s.render.filepath=str(out/'FlowerPot_WithFlowers.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'FlowerPot_WithFlowers.blend'));bpy.ops.render.render(write_still=True)
