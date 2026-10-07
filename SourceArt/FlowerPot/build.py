import bpy,math,bmesh
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\FlowerPot')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.unit_settings.system='METRIC'
m=bpy.data.materials.new('M_FlowerPot_Terracotta');m.use_nodes=True;m.diffuse_color=(.36,.13,.062,1)
p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.36,.13,.062,1);p.inputs['Roughness'].default_value=.82
n=m.node_tree.nodes;l=m.node_tree.links;noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=180;noise.inputs['Detail'].default_value=2;b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.18;b.inputs['Distance'].default_value=.00012;l.new(noise.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])
parts=[]
def lathe(name,profile):
 N=128;v=[(r*math.cos(j*math.tau/N),r*math.sin(j*math.tau/N),z) for r,z in profile for j in range(N)]
 f=[(k*N+j,k*N+(j+1)%N,(k+1)*N+(j+1)%N,(k+1)*N+j) for k in range(len(profile)-1) for j in range(N)]
 me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(name,me);s.collection.objects.link(o);me.materials.append(m)
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
 for p in me.polygons:p.use_smooth=True
 parts.append(o);return o
# Closed section around a central drain opening. Inner cavity stays empty.
profile=[(.008,.021),(.072,.021),(.076,.023),(.078,.028),(.103,.190),(.106,.201),(.112,.202),(.115,.206),(.115,.220),(.112,.224),(.105,.224),(.101,.220),(.101,.207),(.098,.201),(.070,.043),(.066,.037),(.011,.037),(.008,.034),(.008,.021)]
pot=lathe('Flower pot',profile)
tray=lathe('Matching saucer',[(0,.001),(.109,.001),(.117,.002),(.121,.006),(.123,.021),(.121,.026),(.117,.027),(.113,.024),(.111,.013),(.107,.010),(0,.010)])
# Three feet support the pot and leave drainage clearance over the saucer.
for a in [0,2*math.pi/3,4*math.pi/3]:
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=(.056*math.cos(a),.056*math.sin(a),.016));o=bpy.context.object;o.name='Drainage foot';o.scale=(.011,.011,.006);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m)
 for p in o.data.polygons:p.use_smooth=True
 parts.append(o)
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=pot;bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_FlowerPot';s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.fbx(filepath=str(out/'SM_FlowerPot.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False)
floor=bpy.data.materials.new('Preview floor');floor.diffuse_color=(.15,.14,.12,1)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,0));bpy.context.object.data.materials.append(floor)
target=Vector((0,0,.10));bpy.ops.object.camera_add(location=(.40,-.52,.48));cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.37;s.camera=cam
for pos,power,size in [((.3,-.4,.75),35,.6),((-.4,.2,.5),25,.4)]:
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
s.world.color=(.2,.2,.2);s.render.engine='CYCLES';s.cycles.samples=40;s.cycles.use_denoising=True;s.render.resolution_x=1100;s.render.resolution_y=1100;s.render.resolution_percentage=100
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   v=a.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.5;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
s.render.filepath=str(out/'FlowerPot_Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'FlowerPot.blend'));bpy.ops.render.render(write_still=True)
