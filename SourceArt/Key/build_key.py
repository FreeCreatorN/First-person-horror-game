import bpy,math,bmesh,json
from pathlib import Path
from mathutils import Vector
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\Key')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.unit_settings.system='METRIC';s.name='Vintage brass key'
mat=bpy.data.materials.new('M_Key_AgedBrass');mat.use_nodes=True;mat.diffuse_color=(.38,.235,.085,1)
p=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.38,.235,.085,1);p.inputs['Metallic'].default_value=.82;p.inputs['Roughness'].default_value=.32
parts=[]
def add(o,name):
 o.name=name;o.data.materials.append(mat);parts.append(o);return o
# Oval bow with an actual opening; its bottom passes into the rounded shoulder.
bpy.ops.mesh.primitive_torus_add(major_segments=96,minor_segments=20,major_radius=.008,minor_radius=.0015,location=(0,0,.010));bow=add(bpy.context.object,'Oval key bow');bow.scale=(.85,1.18,1);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for f in bow.data.polygons:f.use_smooth=True
def cylinder(name,r,length,center):
 bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=length,location=center,rotation=(math.pi/2,0,0));o=add(bpy.context.object,name)
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 b=o.modifiers.new('Rounded metal edge','BEVEL');b.width=.0003;b.segments=3
 for f in o.data.polygons:f.use_smooth=len(f.vertices)==4
 o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');return o
cylinder('Round shaft',.0022,.041,(0,-.030,.010))
cylinder('Bow shoulder',.0031,.005,(0,-.0115,.010))
cylinder('Shoulder collar',.0037,.0018,(0,-.014,.010))
cylinder('Tip collar',.0025,.0018,(0,-.049,.010))
# Traditional stepped bit, joined to the shaft along its full inner edge.
outline=[(.001,-.049),(.009,-.049),(.009,-.046),(.006,-.046),(.006,-.0445),(.009,-.0445),(.009,-.042),(.007,-.042),(.007,-.0405),(.009,-.0405),(.009,-.038),(.001,-.038)]
N=len(outline);vs=[(x,y,z) for z in [.0084,.0116] for x,y in outline]
fs=[tuple(range(N-1,-1,-1)),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
me=bpy.data.meshes.new('Stepped key bit');me.from_pydata(vs,[],fs);me.update();bit=bpy.data.objects.new('Key bit',me);s.collection.objects.link(bit);add(bit,'Key bit')
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
b=bit.modifiers.new('Soft tooth edges','BEVEL');b.width=.00025;b.segments=3;bit.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
# Apply modifiers and combine as one asset. All components physically overlap.
bpy.ops.object.select_all(action='DESELECT')
for o in parts:
 bpy.context.view_layer.objects.active=o
 for mod in list(o.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
 o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();key=bpy.context.object;key.name='SM_BrassKey'
s.cursor.location=(0,-.020,.010);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');key.location=(0,0,.0037)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.025);bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.fbx(filepath=str(out/'SM_BrassKey.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False)
floor=bpy.data.materials.new('Studio surface');floor.diffuse_color=(.09,.085,.075,1)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,0));ground=bpy.context.object;ground.name='Preview floor';ground.data.materials.append(floor)
target=Vector((0,0,.004));bpy.ops.object.camera_add(location=(.07,-.10,.14));cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.087;s.camera=cam
for pos,power,size in [((-.07,-.05,.16),3,.13),((.10,.06,.12),2,.10)]:
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
s.world.color=(.2,.2,.2);s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.render.resolution_x=1200;s.render.resolution_y=1000;s.render.resolution_percentage=100
bpy.ops.object.select_all(action='DESELECT');key.select_set(True);bpy.context.view_layer.objects.active=key
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   v=a.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.12;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion();v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
key.data.calc_loop_triangles();(out/'model_report.json').write_text(json.dumps({'length_cm':key.dimensions.y*100,'triangles':len(key.data.loop_triangles)},indent=2))
s.render.filepath=str(out/'BrassKey_Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'BrassKey.blend'));bpy.ops.render.render(write_still=True)

