"""A full-scale retractable ballpoint with continuous sprung clip and recessed details."""
import bpy, bmesh, math, json
from pathlib import Path
from mathutils import Vector, Quaternion
OUT=Path(__file__).resolve().parent
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC'; s.unit_settings.scale_length=1
def collection(name):
    c=bpy.data.collections.new(name);s.collection.children.link(c);return c
canonical=collection('UE meshes - canonical origins')
source=collection('SOURCE - individual components')
display=collection('Pen - display assembly')
components=[]

def material(name,color,roughness,metallic=0,coat=0,brushed=False):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=roughness;p.inputs['Metallic'].default_value=metallic
    p.inputs['Coat Weight'].default_value=coat;p.inputs['Coat Roughness'].default_value=.22
    ns=m.node_tree.nodes;ls=m.node_tree.links
    tc=ns.new('ShaderNodeTexCoord');scale=ns.new('ShaderNodeVectorMath');scale.operation='MULTIPLY'
    scale.inputs[1].default_value=(11000,11000,130 if brushed else 11000)
    ls.new(tc.outputs['Object'],scale.inputs[0])
    noise=ns.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1;noise.inputs['Detail'].default_value=2
    ls.new(scale.outputs[0],noise.inputs['Vector'])
    bump=ns.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.0000015 if metallic else .0000007;bump.inputs['Strength'].default_value=.09
    ls.new(noise.outputs['Fac'],bump.inputs['Height']);ls.new(bump.outputs[0],p.inputs['Normal'])
    rr=ns.new('ShaderNodeMapRange');rr.inputs['To Min'].default_value=roughness-.025;rr.inputs['To Max'].default_value=roughness+.025
    ls.new(noise.outputs['Fac'],rr.inputs[0]);ls.new(rr.outputs[0],p.inputs['Roughness'])
    return m
green=material('M_Pen_DeepGreenEnamel',(.016,.073,.057),.30,0,.25)
nickel=material('M_Pen_BrushedNickel',(.46,.49,.52),.29,1,brushed=True)
polish=material('M_Pen_PolishedEdge',(.60,.62,.64),.19,1)
dark=material('M_Pen_RecessedSeams',(.018,.023,.025),.46,.1)
ball_mat=material('M_Pen_TungstenBall',(.17,.19,.20),.23,1)

def mesh(name,vs,fs,mat,smooth=True):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);me.materials.append(mat)
    for f in me.polygons:f.use_smooth=smooth and len(f.vertices)==4
    components.append(o);return o

def lathe(name,profile,mat,segments=64):
    vs=[(r*math.cos(math.tau*i/segments),r*math.sin(math.tau*i/segments),z) for z,r in profile for i in range(segments)]
    fs=[]
    for row in range(len(profile)-1):
        for i in range(segments):
            a=row*segments+i;b=row*segments+(i+1)%segments;fs.append((a,b,b+segments,a+segments))
    fs += [tuple(reversed(range(segments))),tuple(range((len(profile)-1)*segments,len(profile)*segments))]
    return mesh(name,vs,fs,mat)

# The socket overlaps the ball at its shoulder. The ball's lowest point is Z=0.
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=.00035,location=(0,0,.00035))
ball=bpy.context.object;ball.name='Exposed writing ball';ball.data.materials.append(ball_mat);components.append(ball)
for p in ball.data.polygons:p.use_smooth=True
lathe('Ink socket and machined steel nib',[(.00045,.00030),(.00057,.00048),(.0014,.00058),(.002,.0007),(.0094,.00245),(.010,.00255),(.0103,.00255),(.0104,.00268),(.0115,.00268)],polish)
lathe('Tapered nickel nose',[(.0108,.0026),(.011,.00282),(.0115,.00295),(.0177,.00425),(.0202,.00460),(.0207,.00462),(.0211,.00455)],nickel)
lathe('Fine nose seam',[(.02075,.00453),(.0213,.00453)],dark)

# Five shallow grooves are cut into the barrel profile, not floating rings.
barrel_profile=[(.0211,.00448),(.02135,.00466),(.022,.00477)]
for i in range(61):
    z=.023+i*.0005;r=.00478+(z-.023)*.009
    for center in (.028,.0315,.035,.0385,.042):
        r-=.000055*math.exp(-((z-center)/.00028)**2)
    barrel_profile.append((z,r))
barrel_profile += [(.070,.00525),(.086,.00537),(.0926,.00538),(.0930,.00531)]
lathe('Deep green lacquer barrel with recessed grip lines',barrel_profile,green)
lathe('Joint shadow gasket',[(.09265,.00529),(.09335,.00529)],dark)
lathe('Polished barrel joint',[(.0931,.00529),(.09325,.00556),(.09425,.00556),(.09442,.00535)],polish)

cap_profile=[(.0942,.00527),(.09445,.00540),(.095,.00543),(.096,.00543)]
cap_profile += [(.098+i*.002,.00543-.000004*i) for i in range(16)]
cap_profile += [(.129,.00525),(.130,.00515),(.1305,.00495),(.13075,.00465)]
lathe('Brushed metal upper cap',cap_profile,nickel)
lathe('Button guide and recessed dark annulus',[(.1305,.00460),(.131,.00467),(.1321,.00467),(.1323,.00445)],dark)
lathe('Raised button collar',[(.1318,.00445),(.132,.00480),(.1331,.00480),(.13335,.00453)],polish)
lathe('Click plunger',[(.1328,.00324),(.134,.00324),(.13415,.00353),(.1352,.00353),(.1354,.00334),(.1406,.00334),(.1413,.00323),(.14185,.00285),(.142,.00250)],nickel)
lathe('Green button inset',[(.1419,.00248),(.1420,.00248),(.1421,.00230)],green)

# A constant-thickness leaf sweeps from inside the cap to a rounded pressure tip.
clip_profile=[(-.00475,.1290,.00140),(-.0059,.1292,.00150),(-.0072,.1285,.00155),(-.0078,.1270,.00155),(-.0080,.124,.00150),(-.0078,.119,.00142),(-.0074,.112,.00130),(-.0068,.104,.00115),(-.0061,.096,.00105),(-.00565,.0927,.00125),(-.00540,.0920,.00115)]
def catmull(values,substeps=5):
    pts=[]
    for i in range(len(values)-1):
        a=Vector(values[max(i-1,0)]);b=Vector(values[i]);c=Vector(values[i+1]);d=Vector(values[min(i+2,len(values)-1)])
        for j in range(substeps):
            t=j/substeps;pts.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    pts.append(Vector(values[-1]));return pts
cp=catmull(clip_profile)
vs=[];steps=12
for i,(y,z,w) in enumerate(cp):
    tangent=(cp[min(i+1,len(cp)-1)]-cp[max(i-1,0)]);tangent=Vector((0,tangent.x,tangent.y)).normalized()
    n=Vector((1,0,0)).cross(tangent).normalized()
    for j in range(steps):
        a=math.tau*j/steps;ca=math.cos(a);sa=math.sin(a)
        x=w*math.copysign(abs(ca)**.38,ca);v=.00029*math.copysign(abs(sa)**.75,sa)
        vs.append(tuple(Vector((x,y,z))+n*v))
fs=[]
for i in range(len(cp)-1):
    for j in range(steps):
        a=i*steps+j;b=i*steps+(j+1)%steps;fs.append((a,b,b+steps,a+steps))
fs += [tuple(reversed(range(steps))),tuple(range((len(cp)-1)*steps,len(cp)*steps))]
clip=mesh('Continuous curved spring-steel pocket clip',vs,fs,polish)

# Preserve editable components and produce one combined game mesh with one atlas.
for o in components:
    duplicate=o.copy();duplicate.data=o.data.copy();source.objects.link(duplicate)
bpy.ops.object.select_all(action='DESELECT')
for o in components:o.select_set(True)
bpy.context.view_layer.objects.active=components[1];bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_Pen'
s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for layer in list(asset.data.uv_layers):asset.data.uv_layers.remove(layer)
asset.data.uv_layers.new(name='UVMap');bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(68),island_margin=.004);bpy.ops.object.mode_set(mode='OBJECT')
tr=asset.modifiers.new('Game-ready triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tr.name)
bm=bmesh.new();bm.from_mesh(asset.data);nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free();assert nonmanifold==0,nonmanifold
def hull(name,points):
    bm=bmesh.new()
    for p in points:bm.verts.new(p)
    result=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return o
# Clip was merged above; use saved component vertices to build its own small hull.
cs=[hull('UCX_SM_Pen_00',[(r*math.cos(math.tau*i/16),r*math.sin(math.tau*i/16),z) for z,r in [(0,.00035),(.02,.00465),(.094,.00556),(.130,.0052),(.1421,.00334)] for i in range(16)]),hull('UCX_SM_Pen_01',vs)]
for o in cs:o.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_Pen.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
mapping={m.name:'M_Pen' for m in asset.data.materials}
report={'parts':{'SM_Pen':{'filename':'SM_Pen.fbx','dimensions_cm':[d*100 for d in asset.dimensions],'triangles':len(asset.data.polygons),'collision_hulls':2,'uv_channels':1,'non_manifold_edges':nonmanifold,'material_slots':mapping}},'texture_sets':{'Pen':{'prefix':'T_Pen',**{ch:'Textures/T_Pen_'+ch+'.png' for ch in ('BaseColor','Roughness','Normal','Metallic')}}},'materials':{'M_Pen':{'texture_set':'Pen'}},'assembly':{'combined_single_mesh':True,'style':'Retractable deep-green and nickel ballpoint','writing_ball_is_extended':True,'pivot':'Writing ball contact at Z=0','clip_is_continuous_spring_leaf':True,'light_actors_included':False},'exported_lights':0,'exported_cameras':0}
for o in cs:bpy.data.objects.remove(o,do_unlink=True)
for c in list(asset.users_collection):c.objects.unlink(asset)
canonical.objects.link(asset);view=asset.copy();view.data=asset.data;view.name='VIEW_Pen';display.objects.link(view)
canonical.hide_viewport=True;canonical.hide_render=True;source.hide_viewport=True;source.hide_render=True

studio=collection('Preview studio - excluded from exports')
def studio_obj(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor=material('Preview slate',(.037,.045,.052),.8)
bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,-.00005));o=bpy.context.object;o.name='Preview ground';o.data.materials.append(floor);studio_obj(o)
target=Vector((0,0,.071));bpy.ops.object.camera_add(location=target+Vector((.12,-.27,.065)));cam=bpy.context.object;cam.name='Camera_Pen'
cam.rotation_mode='QUATERNION';cam.rotation_quaternion=(target-cam.location).to_track_quat('-Z','Y') @ Quaternion((0,0,1),math.radians(-55))
cam.data.type='ORTHO';cam.data.ortho_scale=.185;cam.data.clip_start=.00001;s.camera=cam;studio_obj(cam)
for name,loc,power,width,height,color in [('Key',(-.12,-.16,.20),3.2,.065,.18,(1,.94,.86)),('Fill',(.16,-.04,.13),2.2,.045,.16,(.85,.93,1)),('Rim',(-.04,.12,.18),3,.05,.16,(1,.98,.91))]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.shape='RECTANGLE';o.data.size=width;o.data.size_y=height;o.data.color=color;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_obj(o)
s.world.use_nodes=True;bg=next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs[0].default_value=(.12,.14,.18,1);bg.inputs[1].default_value=.35
s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=1400;s.render.resolution_y=1000;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX';s.view_settings.exposure=0
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'Pen_Preview.png');studio.hide_viewport=True
bpy.ops.object.select_all(action='DESELECT');view.select_set(True);bpy.context.view_layer.objects.active=view
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Pen.blend'));print(json.dumps(report,indent=2))
