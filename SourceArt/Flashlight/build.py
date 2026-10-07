"""Build a handheld flashlight with a recessed reflector and controllable mouth."""
import bpy, bmesh, math, json
from pathlib import Path
from mathutils import Vector
OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\Flashlight')
seed=(OUT/'cli_seed.py').read_text(encoding='utf-8-sig')
exec(seed.split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
parts=[]
def material(name,col,metal,rough,glow=False,lens=False):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True;m.diffuse_color=(*col,1)
    m.node_tree.nodes.clear()
    p=m.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    output=m.node_tree.nodes.new('ShaderNodeOutputMaterial')
    m.node_tree.links.new(p.outputs['BSDF'],output.inputs['Surface'])
    p.inputs['Base Color'].default_value=(*col,1)
    p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
    p.inputs['Emission Strength'].default_value=0
    if glow:
        color=m.node_tree.nodes.new('ShaderNodeRGB');color.name='LightColor';color.label='LightColor - external control';color.outputs[0].default_value=(.86,.93,1,1)
        strength=m.node_tree.nodes.new('ShaderNodeValue');strength.name='LightStrength';strength.label='LightStrength - 0 is off';strength.outputs[0].default_value=.35
        color.location=(-400,-100);strength.location=(-400,-220)
        m.node_tree.links.new(color.outputs[0],p.inputs['Emission Color']);m.node_tree.links.new(strength.outputs[0],p.inputs['Emission Strength'])
    if lens:
        p.inputs['Alpha'].default_value=.14;p.inputs['IOR'].default_value=1.46
        m.diffuse_color=(*col,.14)
    return m
anodized=material('M_Flashlight_Anodized',(.026,.036,.045),.8,.31)
rubber=material('M_Flashlight_Rubber',(.013,.016,.020),0,.74)
steel=material('M_Flashlight_Steel',(.38,.42,.45),.85,.24)
reflector=material('M_Flashlight_Reflector',(.65,.69,.73),1,.19)
ink=material('M_Flashlight_Print',(.64,.67,.62),0,.55)
lens=material('M_Flashlight_Lens',(.60,.67,.70),.05,.20,True,True)
led=material('M_Flashlight_LED',(.7,.72,.63),0,.28,True)

def mesh(name,verts,faces,mat,group=parts,smooth=True):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);o.data.materials.append(mat);group.append(o)
    for p in me.polygons:p.use_smooth=smooth
    return o

def lathe(name,profile,mat,n=96,loop=False):
    verts=[(x,r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n)) for x,r in profile for i in range(n)]
    faces=[];nr=len(profile)
    for k in range(nr if loop else nr-1):
        kk=(k+1)%nr
        for i in range(n):
            j=(i+1)%n;faces.append((k*n+i,k*n+j,kk*n+j,kk*n+i))
    if not loop:faces.extend([tuple(range(n-1,-1,-1)),tuple((nr-1)*n+i for i in range(n))])
    o=mesh(name,verts,faces,mat)
    # Preserve the profile's machined ridges while smoothing circumferentially.
    for e in o.data.edges:
        a,b=e.vertices
        if a//n==b//n:e.use_edge_sharp=True
    for p in o.data.polygons:
        if len(p.vertices)>4:p.use_smooth=False
    return o

def round_edges(o,width=.00035,segments=3):
    m=o.modifiers.new('Manufactured edge radius','BEVEL');m.width=width;m.segments=segments;m.harden_normals=True
    o.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL')
    for p in o.data.polygons:p.use_smooth=True

def box(name,loc,size,mat,bevel=.0004,group=parts):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat);group.append(o)
    if bevel:round_edges(o,bevel)
    return o

def boolean(o,c):
    if not len(c.data.materials):c.data.materials.append(o.data.materials[0])
    bpy.context.view_layer.objects.active=o
    m=o.modifiers.new('Machined hole','BOOLEAN');m.operation='DIFFERENCE';m.solver='EXACT';m.object=c
    while o.modifiers.find(m.name)>0:bpy.ops.object.modifier_move_up(modifier=m.name)
    bpy.ops.object.modifier_apply(modifier=m.name);bpy.data.objects.remove(c,do_unlink=True)

lathe('Sealed battery tube',[(-.070,.014),(-.068,.0148),(.026,.0148),(.031,.0153),(.040,.0153)],anodized)
lathe('Tail end cap',[(-.085,.0125),(-.084,.0145),(-.082,.0155),(-.068,.0155),(-.066,.0148)],anodized)
lathe('Tail rubber pressure pad',[(-.086,.0094),(-.0857,.0105),(-.0843,.0105)],rubber,64)
for x in [-.079,-.075,-.071]:
    lathe('Tail machining ring',[(x-.00045,.0154),(x-.00030,.0159),(x+.00030,.0159),(x+.00045,.0154)],anodized,64,True)
lathe('Tail seal groove',[(-.0672,.0149),(-.0664,.0149)],rubber,64)
lathe('Grip rear collar',[(-.0642,.0148),(-.0638,.0158),(-.0618,.0158),(-.0614,.0148)],anodized,64,True)
lathe('Grip front collar',[(.0212,.0148),(.0216,.0158),(.024,.0158),(.0244,.0148)],anodized,64,True)
# A continuous staggered pyramid mesh gives real knurl relief without texture dependencies.
n=60;rows=28;start=-.0615;end=.0215;r=.01487
verts=[]
for k in range(rows+1):
    for i in range(n):
        a=(i+.5*(k%2))*math.tau/n;verts.append((start+(end-start)*k/rows,r*math.cos(a),r*math.sin(a)))
faces=[]
for k in range(rows):
    for i in range(n):
        j=(i+1)%n;ids=[k*n+i,k*n+j,(k+1)*n+j,(k+1)*n+i]
        center=sum((Vector(verts[v]) for v in ids),Vector())/4
        yz=Vector((0,center.y,center.z)).normalized()*.01525;center.y=yz.y;center.z=yz.z
        apex=len(verts);verts.append(tuple(center))
        for a,b in zip(ids,ids[1:]+ids[:1]):faces.append((a,b,apex))
faces.extend([tuple(range(n-1,-1,-1)),tuple(rows*n+i for i in range(n))])
mesh('Diamond knurled grip',verts,faces,anodized,smooth=False)

head_profile=[(.036,.0152),(.042,.018),(.051,.022),(.061,.025),(.096,.025),(.101,.026),(.106,.026),(.108,.0249),(.108,.0226),(.102,.0226),(.087,.021),(.076,.017),(.065,.011),(.060,.007),(.059,.013),(.050,.014),(.036,.014)]
lathe('Hollow head shell',head_profile,anodized,96,True)
for x,rr in [(.045,.0196),(.049,.0217),(.053,.0234),(.057,.0248),(.061,.0254)]:
    lathe('Head heat dissipation ring',[(x-.00055,rr-.0008),(x-.0004,rr+.0005),(x+.0004,rr+.0005),(x+.00055,rr-.0008)],anodized,64,True)
lathe('Front stainless bezel',[(.103,.0256),(.105,.0261),(.1083,.0253),(.109,.0244),(.109,.0224),(.1081,.0221),(.1072,.0225),(.103,.0247)],steel,96,True)
lathe('Lens retaining gasket',[(.105,.0222),(.107,.0222),(.107,.0228),(.105,.0228)],rubber,96,True)
lathe('Recessed silver reflector',[(.1034,.02215),(.1034,.0218),(.095,.021),(.088,.019),(.081,.0155),(.075,.010),(.0715,.005),(.0705,.005),(.072,.008),(.078,.013),(.089,.0202),(.1025,.02215)],reflector,96,True)
lathe('LED carrier disc',[(.0675,.0072),(.071,.0072)],steel,64)
lathe('LED ceramic seat',[(.0705,.0047),(.072,.0047)],ink,64)
lathe('Soft LED emitter',[(.0718,.0031),(.0724,.0031)],led,64)
# The glass is behind the metal lip. Both glass and LED expose the same named controls.
lathe('Glass mouth lens',[(.1054,.0223),(.1062,.0223)],lens,96)
box('Side switch mounting saddle',(.039,0,.0175),(.019,.012,.006),anodized,.0023)
box('Side rubber switch',(.039,0,.0218),(.012,.008,.0033),rubber,.0013)
# A seated print on the switch surface, with microscopic thickness rather than floating text.
def tube(name,points,radius,mat,group=parts):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=radius;cu.bevel_resolution=2;cu.use_fill_caps=True
    sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
    for p,co in zip(sp.points,points):p.co=(*co,1)
    o=bpy.data.objects.new(name,cu);s.collection.objects.link(o);cu.materials.append(mat);group.append(o);return o
points=[]
for i in range(33):
    a=math.radians(45+270*i/32);points.append((.039+.00165*math.cos(a),.00165*math.sin(a),.02346))
tube('Power mark arc',points,.000105,ink)
tube('Power mark stem',[(.039+.00055,0,.02346),(.039+.0021,0,.02346)],.00011,ink)
# A spring clip with a real gap and both ends attached to the body.
clip=[(-.068,.0152),(-.066,.019),(-.061,.020),(.011,.020),(.015,.0182),(.016,.0157),(.015,.0150),(.0144,.0155),(.014,.0177),(.0107,.0192),(-.061,.0192),(-.0653,.0185),(-.0672,.0151)]
nv=len(clip);verts=[(x,y,z) for y in [-.0027,.0027] for x,z in clip]
faces=[tuple(range(nv-1,-1,-1)),tuple(range(nv,nv*2))]+[(i,(i+1)%nv,(i+1)%nv+nv,i+nv) for i in range(nv)]
o=mesh('Spring pocket clip',verts,faces,steel);round_edges(o,.00025)
tab=box('Tail lanyard eyelet',(-.077,.0185,0),(.012,.012,.0035),anodized,.0012)
bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.0028,depth=.012,location=(-.077,.0215,0));boolean(tab,bpy.context.object)

bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.convert(target='MESH')
# Curve end caps are coincident but separate after conversion; weld only these prints.
for o in list(bpy.context.selected_objects):
    if o.name.startswith('Power mark'):
        bm=bmesh.new();bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
bpy.ops.object.join()
asset=bpy.context.object;asset.name='SM_Flashlight';s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for uv in list(asset.data.uv_layers):asset.data.uv_layers.remove(uv)
asset.data.uv_layers.new(name='UVMap')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.018)
bpy.ops.object.mode_set(mode='OBJECT')
tri=asset.modifiers.new('Game triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
asset['forward_axis']='local +X';asset['grip_pivot']='centre of grip';asset['emissive_strength_default']=.35
colliders=[]
for name,rad,depth,x in [('UCX_SM_Flashlight_00',.0159,.124,-.022)]:
    bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=rad,depth=depth,location=(x,0,0),rotation=(0,math.pi/2,0))
    o=bpy.context.object;o.name=name;colliders.append(o)
bpy.ops.mesh.primitive_cone_add(vertices=24,radius1=.016,radius2=.0261,depth=.073,location=(.0725,0,0),rotation=(0,math.pi/2,0))
o=bpy.context.object;o.name='UCX_SM_Flashlight_01';colliders.append(o)
box('UCX_SM_Flashlight_02',(-.025,0,.018),(.087,.006,.006),steel,0,colliders)
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True)
for c in colliders:c.select_set(True)
bpy.context.view_layer.objects.active=asset
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_Flashlight.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
for c in colliders:bpy.data.objects.remove(c,do_unlink=True)

# Studio fixtures live in a hidden preview collection and never enter the FBX.
studio=bpy.data.collections.new('Preview studio - excluded from FBX');s.collection.children.link(studio)
def move_studio(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
target=Vector((.010,0,0))
bpy.ops.object.camera_add(location=(.29,-.36,.225));cam=bpy.context.object;cam.name='Camera_Flashlight';move_studio(cam)
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.245;cam.data.clip_start=.001;s.camera=cam
for name,pos,power,size,color in [('Key',(.03,-.17,.24),15,.18,(1,.94,.85)),('Fill',(.19,.19,.14),13,.19,(.78,.88,1)),('Strip',(-.20,.02,.10),9,.10,(1,1,1))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=color
    o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();move_studio(o)
s.world.use_nodes=True;next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.12,.14,.18,1)
s.render.engine='CYCLES';s.cycles.samples=64;s.cycles.use_denoising=True
s.render.resolution_x=1400;s.render.resolution_y=1000;s.render.resolution_percentage=100;s.render.film_transparent=False
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'Flashlight_Preview.png');s.view_settings.view_transform='AgX';s.view_settings.exposure=-1.5
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':
            v=a.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.34;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
            v.region_3d.view_perspective='ORTHO';v.clip_start=.0005;v.shading.type='MATERIAL';v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
studio.hide_viewport=True
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Flashlight.blend'))
bm=bmesh.new();bm.from_mesh(asset.data)
report={'asset':'SM_Flashlight','dimensions_cm':[round(v*100,5) for v in asset.dimensions],'triangles':len(asset.data.polygons),'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'uv_channels':len(asset.data.uv_layers),'material_slots':[m.name for m in asset.data.materials],'emissive_slots':{m.name:i for i,m in enumerate(asset.data.materials) if m.name in {'M_Flashlight_Lens','M_Flashlight_LED'}},'light_strength_default':.35,'collision_hulls':3,'forward_axis':'+X','pivot':[0,0,0],'exported_lights':0}
bm.free();(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
