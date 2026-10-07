import bpy, math, random, json
from mathutils import Vector
from pathlib import Path
OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\KraftBook')
random.seed(31)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.name='Kraft Paper Book'
scene.unit_settings.system='METRIC'
def material(name,color,rough=0.8):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
 p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED'); p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough
 return m,p
kraft,p=material('Natural brown kraft paper',(0.34,0.205,0.092))
n=kraft.node_tree.nodes;l=kraft.node_tree.links
tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=165;tex.inputs['Detail'].default_value=3
r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].position=.2;r.color_ramp.elements[0].color=(.19,.092,.032,1);r.color_ramp.elements[1].position=.8;r.color_ramp.elements[1].color=(.48,.31,.15,1)
l.new(tex.outputs['Fac'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.22;b.inputs['Distance'].default_value=.00018;l.new(tex.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])
pages=[]
for i in range(6):
 v=.65+i*.028;m,_=material('Warm paper %02d'%i,(v,v*.91,v*.73));pages.append(m)
dark,_=material('Binding crease',(.15,.071,.024))
parts=[]
def box(name,loc,scale,mat,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.data.materials.append(mat)
 if bevel:
  mod=o.modifiers.new('Soft paper edges','BEVEL');mod.width=bevel;mod.segments=3
  o.modifiers.new('Corner normals','WEIGHTED_NORMAL')
 parts.append(o);return o
# Closed A5-ish volume, thin kraft-covered boards, actual individual leaves.
box('Back kraft cover',(0,0,.0011),(.151,.216,.0022),kraft,.0008)
for i in range(112):
 z=.00265+i*.000177
 box('Paper leaf %03d'%i,(.0006+random.uniform(-.00013,.00013),random.uniform(-.00017,.00017),z),(.143+random.uniform(-.0003,.0003),.208+random.uniform(-.00035,.00035),.000167),random.choice(pages),.000035)
top=.0232
box('Front kraft cover',(0,0,top),(.151,.216,.0022),kraft,.0008)
box('Continuous rounded kraft spine',(-.0742,0,.01215),(.0035,.216,.0243),kraft,.0016)
# Pressed hinge lines lie on the cover, running parallel to the spine.
box('Front pressed hinge',(-.0678,0,top+.001105),(.00042,.213,.00005),dark,.000018)
box('Back pressed hinge',(-.0678,0,.00001),(.0004,.213,.00004),dark,.000015)
# Narrow cloth bookmark emerges between leaves at the foot.
ribbon,_=material('Muted brown bookmark',(.16,.062,.027))
box('Bookmark ribbon',(.018,-.115,.003),(.006,.028,.00028),ribbon,.00012)
asset=bpy.data.collections.new('BOOK - editable parts');scene.collection.children.link(asset)
for o in parts:
 for c in list(o.users_collection):c.objects.unlink(o)
 asset.objects.link(o)
floor,_=material('Studio warm grey',(.19,.18,.16))
ground=box('Studio floor',(0,0,-.002), (200,200,.002),floor)
bpy.ops.object.camera_add(location=(.31,-.39,.37));cam=bpy.context.object;cam.name='Book product view';cam.rotation_euler=(Vector((0,0,.005))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.345;scene.camera=cam
def light(name,pos,power,size):
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
light('Large softbox',(.05,-.15,.55),18,.42);light('Spine rim',(-.3,.2,.28),12,.25)
scene.world.color=(.22,.22,.22)
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
bpy.ops.object.select_all(action='DESELECT')
for o in asset.objects:o.select_set(True)
bpy.context.view_layer.objects.active=asset.objects.get('Front kraft cover')
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_distance=.42;area.spaces.active.region_3d.view_location=(0,0,.012)
   area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion();area.spaces.active.clip_end=1000
scene.render.filepath=str(OUT/'KraftBook_Preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'KraftBook.blend'))
bpy.ops.render.render(write_still=True)
(OUT/'report.json').write_text(json.dumps({'cover_size_cm':[15.1,21.6],'thickness_cm':2.43,'individual_leaves':112,'blend':str(OUT/'KraftBook.blend')},indent=2))
