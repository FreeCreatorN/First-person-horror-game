import bpy,math,bmesh,json
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\DoorHandle')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.name='Vintage brass door handle';s.unit_settings.system='METRIC'
def mat(name,color,metal,rough):
 m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1);p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;return m,p
brass,p=mat('M_Handle_AgedBrass',(.38,.235,.085),.82,.32)
n=brass.node_tree.nodes;l=brass.node_tree.links;noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=38;noise.inputs['Detail'].default_value=3
r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.16,.084,.024,1);r.color_ramp.elements[1].color=(.46,.30,.12,1);l.new(noise.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
dark,_=mat('M_Handle_Recess',(.035,.024,.011),.7,.46)
parts=[]
def finish(o,name,m,bevel=0):
 o.name=name;o.data.materials.append(m);parts.append(o)
 if bevel:
  b=o.modifiers.new('Machined edge bevel','BEVEL');b.width=bevel;b.segments=4
  o.modifiers.new('Weighted face normals','WEIGHTED_NORMAL')
 return o
def capsule(name,w,h,depth,y,material):
 pts=[];radius=w/2;length=h/2-radius
 for center,start in [(length,0),(-length,math.pi)]:
  for i in range(33):
   a=start+i*math.pi/32;pts.append((radius*math.cos(a),center+radius*math.sin(a)))
 v=[(x,yy,z) for yy in [y,y+depth] for x,z in pts];N=len(pts)
 f=[tuple(range(N-1,-1,-1)),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
 me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return finish(o,name,material,.0008)
plate=capsule('Backplate',.047,.205,.005,-.005,brass)
rim=capsule('Dark inset border',.042,.198,.0007,-.0057,dark)
inner=capsule('Raised central face',.039,.195,.0014,-.0071,brass)
def cyl(name,r,d,loc,m):
 bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=r,depth=d,location=loc,rotation=(math.pi/2,0,0));o=bpy.context.object
 for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
 return finish(o,name,m,.0006)
cyl('Spindle collar base',.018,.006,(0,-.010,.036),brass)
cyl('Collar shadow groove',.015,.0015,(0,-.014,.036),dark)
cyl('Spindle collar',.014,.007,(0,-.018,.036),brass)
cyl('Lever neck',.009,.030,(0,-.035,.036),brass)
# Rounded flowing lever, elliptical section. Ends taper to poles for closed caps.
path=[(0,-.049,.036,.0001),(.001,-.050,.036,.65),(.006,-.052,.036,1),(.016,-.053,.035,1),(.036,-.055,.034,1.03),(.064,-.055,.035,1.05),(.091,-.053,.038,1),(.111,-.050,.041,.90),(.119,-.047,.042,.65),(.122,-.046,.042,.0001)]
verts=[];N=32
for x,y,z,scale in path:
 for j in range(N):
  a=math.tau*j/N;verts.append((x,y+.0095*scale*math.cos(a),z+.0075*scale*math.sin(a)))
faces=[(k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j) for k in range(len(path)-1) for j in range(N)]
faces.extend([tuple(range(N-1,-1,-1)),tuple(range((len(path)-1)*N,len(path)*N))])
me=bpy.data.meshes.new('Lever control cage');me.from_pydata(verts,[],faces);me.update();lever=bpy.data.objects.new('Lever',me);s.collection.objects.link(lever);finish(lever,'Lever',brass)
for p in me.polygons:p.use_smooth=True
su=lever.modifiers.new('Rounded grip','SUBSURF');su.levels=2;su.render_levels=2
# Slotted screw heads and narrow dark slots, physically recessed.
for z in [.084,-.084]:
 screw=cyl('Slotted fixing screw',.0038,.0018,(0,-.0085,z),brass)
 bpy.ops.mesh.primitive_cube_add(size=1,location=(0,-.0094,z));cut=bpy.context.object;cut.dimensions=(.0058,.0012,.0008);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 bpy.context.view_layer.objects.active=screw;bo=screw.modifiers.new('Screw slot','BOOLEAN');bo.operation='DIFFERENCE';bo.object=cut;bpy.ops.object.modifier_apply(modifier=bo.name);bpy.data.objects.remove(cut,do_unlink=True)
# A real keyhole cut through each plate layer.
bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.0045,depth=.04,location=(0,-.005,-.038),rotation=(math.pi/2,0,0));hole=bpy.context.object
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,-.005,-.044));stem=bpy.context.object;stem.dimensions=(.005,.04,.014);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for obj in [plate,rim,inner]:
 bpy.context.view_layer.objects.active=obj
 for cutter in [hole,stem]:
  mod=obj.modifiers.new('Keyhole cut','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter;bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(hole,do_unlink=True);bpy.data.objects.remove(stem,do_unlink=True)
# Recalculate all mesh normals and establish a usable spindle pivot on the lever.
for o in parts:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
s.cursor.location=(0,-.035,.036);bpy.ops.object.select_all(action='DESELECT');lever.select_set(True);bpy.context.view_layer.objects.active=lever;bpy.ops.object.origin_set(type='ORIGIN_CURSOR');s.cursor.location=(0,0,0)
wood,p=mat('Preview dark timber',(.08,.036,.015),0,.6)
bpy.ops.mesh.primitive_cube_add(size=1,location=(.04,.025,0));board=bpy.context.object;board.name='Preview door panel';board.dimensions=(.65,.045,.65);board.data.materials.append(wood);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
bpy.ops.object.camera_add(location=(.27,-.46,.20));cam=bpy.context.object;target=Vector((.039,-.02,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.30;s.camera=cam
for loc,power,size in [((-.12,-.25,.30),22,.24),((.3,-.10,.1),12,.18)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
s.world.color=(.22,.22,.22);s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.render.resolution_x=1200;s.render.resolution_y=1200;s.render.resolution_percentage=100
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=lever
for screen in bpy.data.screens:
 for ar in screen.areas:
  if ar.type=='VIEW_3D':
   v=ar.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.4;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
bpy.ops.export_scene.fbx(filepath=str(out/'DoorHandle.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,use_mesh_modifiers=True)
s.render.filepath=str(out/'DoorHandle_Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'DoorHandle.blend'));bpy.ops.render.render(write_still=True)
(out/'report.json').write_text(json.dumps({'backplate_height_cm':20.5,'lever_length_cm':12.2,'parts':len(parts)},indent=2))
