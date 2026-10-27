"""Base camera generation. After baking, ShutterSplit/split_model.py separates the shutter.

The current Camera.blend/FBXs already contain the two-part deliverable.
"""
import bpy,bmesh,math,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
def collection(name):
    c=bpy.data.collections.new(name);s.collection.children.link(c);return c
canonical=collection('UE meshes - canonical origins');source=collection('SOURCE - individual components');display=collection('Camera - display assembly')
parts=[]
def material(name,color,rough,metal=0,grain=None):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;p.inputs['Emission Strength'].default_value=0
    if grain:
        ns=m.node_tree.nodes;ls=m.node_tree.links;co=ns.new('ShaderNodeTexCoord');tex=ns.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value=2800 if grain=='leather' else 6500;tex.inputs['Detail'].default_value=3
        ls.new(co.outputs['Object'],tex.inputs['Vector'])
        bump=ns.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.34 if grain=='leather' else .07;bump.inputs['Distance'].default_value=.00012 if grain=='leather' else .000002
        ls.new(tex.outputs['Fac'],bump.inputs['Height']);ls.new(bump.outputs[0],p.inputs['Normal'])
        rr=ns.new('ShaderNodeMapRange');rr.inputs['To Min'].default_value=rough-.07;rr.inputs['To Max'].default_value=rough+.05;ls.new(tex.outputs['Fac'],rr.inputs[0]);ls.new(rr.outputs[0],p.inputs['Roughness'])
    return m,p
chrome,_=material('M_Camera_SatinChrome',(.43,.46,.49),.30,1,'metal')
edge,_=material('M_Camera_PolishedTrim',(.57,.60,.63),.20,1)
paint,_=material('M_Camera_BlackEnamel',(.017,.020,.024),.35,.18)
leather,_=material('M_Camera_Leatherette',(.013,.016,.017),.70,0,'leather')
rubber,_=material('M_Camera_RubberGrip',(.009,.011,.014),.65)
inside,_=material('M_Camera_OpticalInterior',(.006,.008,.011),.51)
white,_=material('M_Camera_EngravedIvory',(.69,.70,.65),.56)
red,_=material('M_Camera_RedIndex',(.47,.025,.016),.46)
gold,_=material('M_Camera_ContactBrass',(.36,.22,.07),.32,1)
glass,gp=material('M_Camera_OpticalGlass',(.72,.84,.94),.07)
gp.inputs['Transmission Weight'].default_value=1;gp.inputs['IOR'].default_value=1.46;gp.inputs['Alpha'].default_value=1

def mesh(name,vs,fs,mat):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update();bm=bmesh.new();bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);me.materials.append(mat);parts.append(o);return o
def bevel(o,w,seg=3):
    b=o.modifiers.new('Manufactured edge radii','BEVEL');b.width=w;b.segments=seg;b.harden_normals=True
    o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL')
    for p in o.data.polygons:p.use_smooth=True
def box(name,loc,size,mat,w=.0004):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat);parts.append(o)
    if w:bevel(o,w)
    return o
def cyl(name,loc,r,depth,mat,axis='Z',n=48):
    rot={'Z':(0,0,0),'Y':(math.pi/2,0,0),'X':(0,math.pi/2,0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=n,radius=r,depth=depth,location=loc,rotation=rot)
    o=bpy.context.object;o.name=name;o.data.materials.append(mat);parts.append(o);bevel(o,min(.00018,depth*.18),2);return o
def prism(name,outline,y0,y1,mat,w=.0007):
    n=len(outline);vs=[(x,y,z) for y in (y0,y1) for x,z in outline]
    fs=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    o=mesh(name,vs,fs,mat)
    if w:bevel(o,w)
    return o
def ring(name,profile,mat,axis='Y',center=(-.008,-.025,.044),n=80,knurl=0):
    if profile[-1]==profile[0]:profile=profile[:-1]
    vs=[];rs=[]
    for radius,t in profile:
        if radius<1e-9:
            rs.append([len(vs)]);vs.append(tuple(Vector(center)+Vector((0,-t,0) if axis=='Y' else (0,0,t))))
        else:
            ids=[]
            for i in range(n):
                a=math.tau*i/n;r=radius+(knurl if i%2==0 else 0)
                p=(r*math.cos(a),-t,r*math.sin(a)) if axis=='Y' else (r*math.cos(a),r*math.sin(a),t)
                ids.append(len(vs));vs.append(tuple(Vector(center)+Vector(p)))
            rs.append(ids)
    fs=[]
    for a,b in list(zip(rs,rs[1:]))+[(rs[-1],rs[0])]:
        if len(a)==len(b)==1:continue
        for i in range(n):
            j=(i+1)%n
            if len(a)==1:fs.append((a[0],b[j],b[i]))
            elif len(b)==1:fs.append((a[i],a[j],b[0]))
            else:fs.append((a[i],a[j],b[j],b[i]))
    o=mesh(name,vs,fs,mat)
    for p in o.data.polygons:p.use_smooth=knurl==0
    return o
def text(name,string,loc,size,mat,rotation=(math.pi/2,0,0),align='CENTER'):
    cu=bpy.data.curves.new(name,'FONT');cu.body=string;cu.size=size;cu.align_x=align;cu.align_y='CENTER';cu.extrude=.000018;cu.resolution_u=3
    o=bpy.data.objects.new(name,cu);s.collection.objects.link(o);o.location=loc;o.rotation_euler=rotation;cu.materials.append(mat);parts.append(o);return o
def screw(name,loc,axis='Y',r=.00125):
    o=cyl(name,loc,r,.0005,edge,axis,32)
    offset={'Y':(0,-.00026,0),'Z':(0,0,.00026),'X':(.00026,0,0)}[axis]
    dims={'Y':(r*1.35,.00008,.00020),'Z':(r*1.35,.00020,.00008),'X':(.00008,r*1.35,.00020)}[axis]
    box(name+' screw slot',tuple(Vector(loc)+Vector(offset)),dims,inside,.00004)
    return o

# Chassis, fitted skins, metal top and bottom plates.
body=box('Die-cast chassis',(0,0,.0375),(.142,.048,.071),chrome,.0048)
box('Base plate',(0,0,.0023),(.1415,.0475,.0046),chrome,.0021)
box('Top shoulder plate',(0,0,.0754),(.144,.049,.0092),chrome,.0029)
box('Front left leather panel',(-.050,-.0244,.039),(.037,.0024,.056),leather,.0022)
box('Front right leather panel',(.046,-.0244,.039),(.047,.0024,.056),leather,.0022)
box('Left body wrap',(-.0709,0,.037),(.0018,.038,.056),leather,.0008)
box('Right body wrap',(.0709,0,.037),(.0018,.038,.056),leather,.0008)
for x in (-.059,.058):
    screw('Front chassis screw',(x,-.0246,.070))
    screw('Base plate screw',(x,.009,.00035),'Z')

# The pentaprism is a solid bevelled housing with a real raised hot shoe.
prism_outline=[(-.040,.076),(-.034,.085),(-.019,.098),(.003,.098),(.019,.085),(.024,.076)]
prism('Five-sided prism housing',prism_outline,-.026,.017,chrome,.0012)
box('Front nameplate',(-.008,-.0271,.083),(.036,.0014,.0088),paint,.00065)
text('Flush front designation','M-35',(-.008,-.02783,.0832),.0055,white)
box('Hot shoe base',(-.008,-.0005,.0985),(.021,.024,.0018),paint,.0005)
for x in (-.0185,.0025):box('Raised hot shoe rail',(x,-.0005,.1000),(.0020,.023,.0021),edge,.0003)
box('Hot shoe contact plate',(-.008,-.0005,.0993),(.016,.019,.0008),chrome,.0003)
for y in (-.006,.001,.006):cyl('Flash electrical contact',(-.008,y,.09985),.0009,.00035,gold,'Z',24)

# Rewind knob, shutter dial, concentric controls and film advance lever.
for x,r in [(-.051,.0110),(.037,.0123)]:
    cyl('Control dial seating gasket',(x,.001,.0801),r+.0004,.0018,paint)
    ring('Knurled control dial',[(r-.0008,0),(r, .0008),(r,.0065),(r-.0005,.0072),(0,.0072),(0,0)],chrome,'Z',(x,.001,.0801),80,.00024)
    cyl('Black control dial face',(x,.001,.08745),r-.0012,.00050,paint)
    for i in range(12):
        a=math.tau*i/12;ob=box('Engraved dial index',(x+(r-.0021)*math.cos(a),.001+(r-.0021)*math.sin(a),.08773),(.00035,.0016,.00006),white,.00002);ob.rotation_euler.z=a-math.pi/2
text('Shutter dial scale','125',(.037,.001,.08777),.0032,white,(0,0,0))
text('Film speed dial scale','400',(-.051,.001,.08777),.0032,white,(0,0,0))
box('Rewind folding crank',(-.051,.001,.0887),(.014,.0030,.00125),edge,.00055)
cyl('Rewind crank finger button',(-.057,.001,.0900),.0017,.0018,paint)
cyl('Shutter button surround',(.061,-.011,.0815),.0052,.0032,paint)
cyl('Shutter release',(.061,-.011,.0840),.0037,.0032,edge)
cyl('Cable release socket',(.061,-.011,.08563),.0010,.00009,inside,'Z',32)
cyl('Winding lever pivot',(.057,.009,.0817),.0057,.0026,edge)
lever=box('Film advance metal lever',(.063,.015,.0831),(.019,.0040,.0016),edge,.0007);lever.rotation_euler.z=.58
grip=box('Film advance plastic grip',(.072,.020,.0830),(.010,.0052,.0030),paint,.0014);grip.rotation_euler.z=.58

# Lens mount and hollow barrel. Closed annular profiles keep the optical path open.
ring('Chrome bayonet mounting flange',[(.025,0),(.031,.0004),(.032,.002),(.032,.0046),(.0308,.0055),(.023,.0055),(.023,0)],edge)
ring('Aperture ring',[(.024,.005),(.0295,.005),(.030,.006),(.030,.015),(.0295,.0158),(.023,.0158),(.023,.005)],paint)
ring('Fine aperture ring knurl',[(.0298,.0065),(.0301,.0067),(.0301,.0118),(.0298,.012),(.0298,.0065)],paint,n=128,knurl=.00025)
ring('Focusing barrel',[(.023,.015),(.0295,.015),(.030,.016),(.030,.035),(.028,.037),(.023,.037),(.023,.015)],paint)
ring('Rubber focusing grip',[(.030,.018),(.0308,.0188),(.0308,.0318),(.030,.0325),(.030,.018)],rubber,n=144,knurl=.00065)
ring('Focus distance scale band',[(.023,.0345),(.0289,.0345),(.029,.035),(.029,.0404),(.0285,.041),(.023,.041),(.023,.0345)],paint)
ring('Polished front retaining rim',[(.023,.040),(.0285,.040),(.0288,.041),(.0288,.0505),(.0282,.052),(.023,.052),(.0226,.0505),(.0226,.043)],edge)
ring('Black lens name bezel',[(.0222,.0495),(.0279,.0495),(.0279,.0521),(.0222,.0521)],paint)
ring('Optical interior wall',[(.021,.005),(.0228,.005),(.0228,.049),(.021,.049)],inside)
ring('Visible iris diaphragm support',[(.006,.0435),(.0209,.0435),(.0209,.0440),(.006,.0440)],inside)
for i in range(6):
    a=math.tau*i/6;points=[]
    for r,t in [(.006,a),(.019,a+.18),(.020,a+.95),(.008,a+1.05)]:points.append((-.008+r*math.cos(t),.044+r*math.sin(t)))
    prism('Overlapping aperture blade',points,-.06935-i*.000015,-.06920-i*.000015,paint,0)
ring('Black interior behind aperture',[(0,.040),(.009,.040),(.009,.0406),(0,.0406)],inside)
# A solid optical element with a curved front, not a painted lens disc.
lens_profile=[(0,.0507)]+[(.0216*j/10,.0490+.0017*(1-(j/10)**2)) for j in range(1,11)]
lens_profile += [(.0216,.0479)]+[(.0216*j/10,.0479+.0005*(1-(j/10)**2)) for j in range(9,-1,-1)]
ring('Convex coated front lens',lens_profile,glass,n=96)
text('Lens focal length','50 mm',(-.008,-.07713,.0684),.0026,white)
text('Lens aperture rating','1:1.8',(-.008,-.07713,.0201),.0024,white)
for i in range(12):
    a=math.tau*i/12;r=.0261
    if abs(math.cos(a))>.5:
        ob=box('Front rim registration tick',(-.008+r*math.cos(a),-.07714,.044+r*math.sin(a)),(.00024,.00007,.0010),white,.00002);ob.rotation_euler.y=math.pi/2-a
for x,z in [(-.035,.062),(.019,.062),(-.008,.015)]:screw('Lens flange retaining screw',(x,-.0307,z),'Y',.0011)
cyl('Lens release button',(.028,-.0265,.052),.0031,.0034,paint,'Y')
cyl('Self timer pivot',(-.052,-.0266,.054),.0032,.0025,edge,'Y')
timer=box('Self timer lever',(-.055,-.0280,.045),(.0040,.0024,.018),chrome,.0008);timer.rotation_euler.y=.25
box('Self timer finger pad',(-.0570,-.0287,.0370),(.0050,.0022,.0048),paint,.0007)
for x in (-.0725,.0725):
    box('Strap eye attachment',(x,-.006,.059),(.0035,.008,.010),edge,.0010)
    bpy.ops.mesh.primitive_torus_add(major_segments=32,minor_segments=10,location=(x,-.009,.060),rotation=(0,math.pi/2,0),major_radius=.0035,minor_radius=.00085)
    o=bpy.context.object;o.name='Closed metal strap eye';o.data.materials.append(edge);parts.append(o)
    for p in o.data.polygons:p.use_smooth=True

# Back door, hinges, rubber eye cup, inset optical window and film reminder.
box('Rear door seal',(0,.0242,.0365),(.132,.0028,.060),paint,.0030)
box('Rear leather door panel',(0,.0261,.0365),(.124,.0020,.052),leather,.0022)
for z in (.017,.040,.061):cyl('Rear door rolled hinge',(.066,.0248,z),.0015,.014,chrome,'Z',32)
box('Door opening latch',(-.0718,.006,.040),(.0032,.011,.021),paint,.0013)
box('Raised viewfinder eye cup',(-.008,.0261,.078),(.029,.0088,.0205),rubber,.0021)
box('Viewfinder recess',(-.008,.0306,.078),(.0215,.0010,.0135),inside,.0008)
box('Viewfinder optical glass',(-.008,.0312,.078),(.018,.0007,.0105),glass,.0007)
box('Film memo frame',(0,.0279,.039),(.030,.0017,.021),paint,.0011)
paper,_=material('M_Camera_FilmMemoPaper',(.59,.56,.43),.85)
box('Film memo insert',(0,.0288,.039),(.025,.00025,.016),paper,.0005)
text('Film memo caption','COLOR',(0,.02896,.0430),.0026,paint,(math.pi/2,0,math.pi))
text('Film memo speed','400',(0,.02896,.0367),.0054,paint,(math.pi/2,0,math.pi))
for x in (-.058,.057):screw('Rear top plate screw',(x,.0247,.074),'Y',.0010)

# Bottom service details sit flush on the underside.
for x in (-.042,.040):
    cyl('Battery access cover',(x,0,.00024),.0080,.0004,chrome,'Z')
    box('Coin slot on battery cover',(x,0,-.00002),(.010,.0010,.00008),inside,.0001)
cyl('Tripod socket dark recess',(.006,.001,.00008),.0035,.0001,inside,'Z')
ring('Tripod brass socket',[(.0025,0),(.0034,0),(.0034,.0003),(.0025,.0003)],gold,'Z',(.006,.001,-.00005),48)

# Apply modifiers before copying editable source pieces and making the game mesh.
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=body;bpy.ops.object.convert(target='MESH')
for o in parts:
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-8)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bad=sum(not e.is_manifold for e in bm.edges)
    if bad:print('COMPONENT_TOPOLOGY',o.name,bad,flush=True)
    bm.to_mesh(o.data);bm.free()
    dup=o.copy();dup.data=o.data.copy();source.objects.link(dup);dup.select_set(False)
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=body
bpy.ops.object.join();asset=bpy.context.object;asset.name='SM_Camera'
assert len(source.objects)==len(parts),(len(source.objects),len(parts))
s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for uv in list(asset.data.uv_layers):asset.data.uv_layers.remove(uv)
asset.data.uv_layers.new(name='UVMap');bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(70),island_margin=.006);bpy.ops.object.mode_set(mode='OBJECT')
tr=asset.modifiers.new('Game ready triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tr.name)
bm=bmesh.new();bm.from_mesh(asset.data);nm=sum(not e.is_manifold for e in bm.edges);loose=sum(not v.link_edges for v in bm.verts);bm.free();assert nm==loose==0,(nm,loose)
face_keys=[tuple(sorted(tuple(round(v,9) for v in asset.data.vertices[i].co) for i in p.vertices)) for p in asset.data.polygons]
duplicate_triangles=len(face_keys)-len(set(face_keys));assert duplicate_triangles==0,duplicate_triangles
def hull(name,points):
    bm=bmesh.new()
    for p in points:bm.verts.new(p)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    unused=[v for v in bm.verts if not v.link_faces]
    if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free();o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return o
colliders=[]
colliders.append(hull('UCX_SM_Camera_00',[(x,y,z) for x in (-.074,.078) for y in (-.029,.0316) for z in (-.00006,.089)]))
colliders.append(hull('UCX_SM_Camera_01',[(x,y,z) for x,z in prism_outline for y in (-.027,.019)]+[(x,y,.1011) for x in (-.020,.004) for y in (-.013,.013)]))
for index,profile in enumerate([[(.0318,0),(.0318,.016)],[(.0315,.015),(.0288,.0523)]]):
    colliders.append(hull('UCX_SM_Camera_%02d'%(index+2),[(-.008+r*math.cos(math.tau*i/32),-.025-t,.044+r*math.sin(math.tau*i/32)) for r,t in profile for i in range(32)]))
for o in colliders:o.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_Camera.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
mapping={m.name:'M_Camera_Glass' if m==glass else 'M_Camera_Opaque' for m in asset.data.materials}
report={'parts':{'SM_Camera':{'filename':'SM_Camera.fbx','dimensions_cm':[v*100 for v in asset.dimensions],'triangles':len(asset.data.polygons),'collision_hulls':4,'uv_channels':1,'non_manifold_edges':nm,'material_slots':mapping}},'texture_sets':{'Opaque':{'prefix':'T_Camera',**{ch:'Textures/T_Camera_'+ch+'.png' for ch in ('BaseColor','Roughness','Normal','Metallic')}}},'materials':{'M_Camera_Opaque':{'shader_type':'opaque_atlas','texture_set':'Opaque'},'M_Camera_Glass':{'shader_type':'glass','opacity':.18,'roughness':.07,'ior':1.46,'tint':[.72,.84,.94]}},'assembly':{'combined_single_mesh':True,'style':'Silver and black 35 mm SLR prop','front_direction':'-Y','lens_center_m':[-.008,-.025,.044],'optical_glass_is_separate':True,'preview_only_lights':True},'exported_lights':0,'exported_cameras':0}
report['assembly']['editable_source_components']=len(source.objects)
report['parts']['SM_Camera']['exact_duplicate_triangles']=duplicate_triangles
for o in colliders:bpy.data.objects.remove(o,do_unlink=True)
for c in list(asset.users_collection):c.objects.unlink(asset)
canonical.objects.link(asset);view=asset.copy();view.data=asset.data;view.name='VIEW_Camera';display.objects.link(view)
canonical.hide_viewport=True;canonical.hide_render=True;source.hide_viewport=True;source.hide_render=True
studio=collection('Preview studio - excluded from exports')
def studio_obj(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor,_=material('Preview matte slate',(.040,.050,.060),.8)
bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,-.00015));o=bpy.context.object;o.name='Preview ground';o.data.materials.append(floor);studio_obj(o)
target=Vector((0,-.015,.046));bpy.ops.object.camera_add(location=target+Vector((.23,-.34,.20)));cam=bpy.context.object;cam.name='Camera_ProductPreview';cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.225;cam.data.clip_start=.00001;s.camera=cam;studio_obj(cam)
for name,pos,power,size,col in [('Key',(-.18,-.19,.30),9,.22,(1,.94,.86)),('Fill',(.23,-.06,.22),5,.19,(.86,.94,1)),('Rim',(-.05,.20,.28),10,.15,(1,.97,.90))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=col;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_obj(o)
s.world.use_nodes=True;bg=next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs[0].default_value=(.12,.15,.19,1);bg.inputs[1].default_value=.4
s.render.engine='CYCLES';s.cycles.samples=40;s.cycles.use_denoising=True;s.render.resolution_x=1500;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX';s.view_settings.exposure=-.3;s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'Camera_Preview.png');studio.hide_viewport=True
bpy.ops.object.select_all(action='DESELECT');view.select_set(True);bpy.context.view_layer.objects.active=view
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Camera.blend'));print(json.dumps(report,indent=2))
