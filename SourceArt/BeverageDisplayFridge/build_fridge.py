"""MCP-authored single-door beverage display fridge, nine planning categories."""
import bpy,bmesh,math,json,runpy,ast
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parent;S=bpy.context.scene
assert S.name=='BeverageDisplayFridge' and not list(S.objects)
T=runpy.run_path(str(ROOT/'surface_tools.py'));Surface=T['Surface'];linear=T['linear_color'];M={}
tree=ast.parse((ROOT.parent/'IceCreamFreezer/build_freezer.py').read_text(encoding='utf-8'))
utilities=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('simple','mesh','box','apply','cylinder','camera')]
exec(compile(ast.Module(body=utilities,type_ignores=[]),'fridge_geometry_helpers','exec'))
M['dark']=simple('M_Fridge_DarkRubber',(.075,.07,.065),.78)
M['white']=simple('M_Fridge_WhiteCoating',(.73,.74,.70),.57,.12)
for key,color,metal,rough in [('red',(.48,.065,.045),.2,.60),('steel',(.53,.55,.54),.80,.40)]:
    a=Surface('M_Fridge_'+key,color,rough,metal)
    n=a.noise('Scattered aging',34,2.8,-700,300)
    col=a.blend('Paint and wear variation',n,linear(tuple(c*.63 for c in color)),linear(color),300,300)
    if key=='red':
        dirt=a.noise('Chipped red lacquer',130,2,-700,-100)
        mask=a.remap('Sparse paint loss',dirt,(.63,.78),(0,.52),-300,-100)
        col=a.blend('Chipped exposed undercoat',mask,col,linear((.29,.21,.14)),650,300)
    a.connect(col,a.shader.inputs['Base Color']);a.bump('Fine coating texture',n,.12,.00023,850,-100);M[key]=a.material
M['glass']=T['clear_glass']();M['glass'].name='M_Fridge_GlassPreview'
def printed(name,filename,roughname,emission=0):
    m=simple(name,(.5,.1,.07),.6,.1);p=m.node_tree.nodes.get('Principled BSDF');t=m.node_tree
    uv=t.nodes.new('ShaderNodeUVMap');uv.uv_map='PrintUV'
    for fn,socket,space in [(filename,'Base Color','sRGB'),(roughname,'Roughness','Non-Color')]:
        img=bpy.data.images.load(str(ROOT/'Textures'/fn),check_existing=True);img.colorspace_settings.name=space;img.pack()
        node=t.nodes.new('ShaderNodeTexImage');node.image=img;t.links.new(uv.outputs['UV'],node.inputs['Vector']);t.links.new(node.outputs['Color'],p.inputs[socket])
        if socket=='Base Color' and emission:t.links.new(node.outputs['Color'],p.inputs['Emission Color'])
    p.inputs['Emission Strength'].default_value=emission;return m
M['side']=printed('M_Fridge_SidePrint','T_BeverageSide_BaseColor.png','T_BeverageSide_Roughness.png')
M['sign']=printed('M_Fridge_Sign','T_BeverageHeader_BaseColor.png','T_BeverageHeader_Roughness.png',.25)
M['diffuser']=simple('M_Fridge_SignWhite',(.86,.88,.83),.35)
p=M['diffuser'].node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=linear((.86,.88,.83));p.inputs['Emission Strength'].default_value=.25

root=bpy.data.collections.new('饮料柜组件 · 规划书九类');S.collection.children.link(root)
definitions=[('TopLightbox','01 顶部灯箱与顶盖'),('GlassDoor','02 玻璃门'),('DoorHandle','03 门把手'),('DoorFrame','04 门框'),
    ('Shelves','05 内部层板'),('InnerLiner','06 内胆'),('OuterBody','07 外壳主体'),('VentGrille','08 散热格栅'),('BaseFeet','09 底座与底脚')]
cats={};groups={};COL={}
for key,label in definitions:
    c=bpy.data.collections.new(label);root.children.link(c);cats[key]=c
    if key in ('Shelves','BaseFeet'):
        e=bpy.data.objects.new(key,None);c.objects.link(e);e.empty_display_size=.035;groups[key]=e
keys=['TopLightbox','GlassDoor','DoorHandle','DoorFrame',*[f'Shelf{i:02d}' for i in range(1,6)],'InnerLiner','OuterBody','VentGrille','FootFL','FootFR','FootRL','FootRR']
COLL={key:[] for key in keys}
for key in keys:
    parent='Shelves' if key.startswith('Shelf') else 'BaseFeet' if key.startswith('Foot') else key
    if parent==key:COL[key]=cats[key]
    else:
        c=bpy.data.collections.new(key);cats[parent].children.link(c);COL[key]=c
hinge=Vector((.289,-.338,.285));h=bpy.data.objects.new('DoorHinge',None);cats['DoorFrame'].objects.link(h);h.location=hinge;h.empty_display_size=.06
preview=bpy.data.collections.new('_PreviewOnly');S.collection.children.link(preview)

def collar(name,outerx,y0,y1,z,thickness,width,mat,part):
    x0,x1=-outerx,outerx
    v=[(x,y,zz) for zz in (z-thickness/2,z+thickness/2) for ring in ([(x0,y0),(x1,y0),(x1,y1),(x0,y1)],[(x0+width,y0+width),(x1-width,y0+width),(x1-width,y1-width),(x0+width,y1-width)]) for x,y in ring]
    f=[]
    for i in range(4):
        n=(i+1)%4;f += [(i,n,4+n,4+i),(8+i,12+i,12+n,8+n),(i,8+i,8+n,n),(4+i,4+n,12+n,12+i)]
    return mesh(name,v,f,mat,part)
def ring_front(name,x0,x1,z0,z1,y,depth,border,mat,part):
    box(name+' left',(x0+border/2,y,(z0+z1)/2),(border,depth,z1-z0),mat,part)
    box(name+' right',(x1-border/2,y,(z0+z1)/2),(border,depth,z1-z0),mat,part)
    for z in (z0+border/2,z1-border/2):box(name+' cross',( (x0+x1)/2,y,z),(x1-x0-2*border,depth,border),mat,part)
def wire(name,a,b,r,part,n=6):
    a,b=Vector(a),Vector(b);d=(b-a).normalized();u=d.cross(Vector((0,0,1)))
    if u.length<.1:u=d.cross(Vector((0,1,0)))
    u.normalize();v=d.cross(u)
    pts=[tuple(p+u*r*math.cos(i*math.tau/n+math.pi/6)+v*r*math.sin(i*math.tau/n+math.pi/6)) for p in (a,b) for i in range(n)]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
    o=mesh(name,pts,faces,'steel',part)
    for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
    return o

# Closed case panels form an open-front insulated housing, without a stacked skin.
for sign in (-1,1):
    o=box('Red exterior side',(sign*.3025,-.0175,1.015),(.035,.625,1.83),'red','OuterBody',.0015)
    o.data.materials.append(M['side']);uv=o.data.uv_layers.new(name='PrintUV')
    for p in o.data.polygons:
        if p.normal.x*sign>.999:p.material_index=o.data.materials.find(M['side'].name)
        for li in p.loop_indices:
            v=o.data.vertices[o.data.loops[li].vertex_index].co;uv.data[li].uv=((v.y+.330)/.625,(v.z-.10)/1.83)
box('Back service shell',(0,.3125,1.015),(.570,.035,1.83),'steel','OuterBody',.0012,True)
box('Bottom chassis',(0,-.0175,.115),(.570,.625,.030),'steel','OuterBody',.001,True)
box('Top chassis cover',(0,-.0175,1.918),(.570,.625,.024),'steel','OuterBody',.001)
for x in (-.3025,.3025):
    box('Front corner steel angle',(x,-.332,1.015),(.035,.004,1.83),'steel','OuterBody')
    box('Side corner steel angle',(math.copysign(.322,x),-.315,1.015),(.004,.030,1.83),'steel','OuterBody')
ring_front('Closed door gasket',-.285,.285,.285,1.680,-.336,.004,.033,'dark','OuterBody')
for x in (-.276,.276):box('Inner front reveal',(x,-.32125,.993),(.012,.0175,1.374),'white','OuterBody')
for z in (.309,1.677):box('Front reveal cross',(0,-.32125,z),(.540,.0175,.006),'white','OuterBody')
box('Compressor dark cavity',(0,-.285,.215),(.56,.008,.170),'dark','OuterBody')
for z in (.45,1.52):
    box('Fixed hinge mounting plate',(.300,-.332,z),(.028,.008,.050),'steel','OuterBody')
COLL['OuterBody']=[{'center_m':[x,-.0175,1.015],'half_m':[.0175,.3125,.915]} for x in (-.3025,.3025)]+[
    {'center_m':[0,.3125,1.015],'half_m':[.285,.0175,.915]},
    {'center_m':[0,-.0175,.115],'half_m':[.285,.3125,.015]},
    {'center_m':[0,-.0175,1.918],'half_m':[.285,.3125,.012]}]

# Rear service panel and a short connected power cable, all part of the shell.
box('Rear service identification plate',(.145,.332,.42),(.175,.004,.105),'steel','OuterBody',.001)
box('Rear cable socket',(.20,.342,.47),(.035,.016,.045),'dark','OuterBody',.002)
cable=[(.20,.346,.47),(.20,.370,.42),(.19,.385,.30),(.17,.385,.17),(.18,.37,.13),(.23,.37,.14)]
for a,b in zip(cable,cable[1:]):
    o=wire('Rear power cable',a,b,.0035,'OuterBody',8);o.data.materials.clear();o.data.materials.append(M['dark'])
box('Rear cable plug',(.237,.37,.14),(.034,.020,.022),'dark','OuterBody',.001)
for x in (.23,.244):box('Plug contact',(x,.37,.121),(.004,.006,.016),'steel','OuterBody')

# Separate inner liner: four rim loops give a genuine open-front thin shell.
rects=[(.278,.306,1.680,.286),(.278,.306,1.680,-.3125),(.272,.312,1.674,-.3125),(.272,.312,1.674,.280)]
verts=[(x,y,z) for w,z0,z1,y in rects for x,z in [(-w,z0),(w,z0),(w,z1),(-w,z1)]]
faces=[(3,2,1,0),(12,13,14,15)]
for j in range(3):faces.extend((j*4+i,j*4+(i+1)%4,(j+1)*4+(i+1)%4,(j+1)*4+i) for i in range(4))
mesh('Open refrigerated inner liner',verts,faces,'white','InnerLiner')
COLL['InnerLiner']=[{'center_m':[x,-.01625,.993],'half_m':[.003,.29625,.687]} for x in (-.275,.275)]+[
    {'center_m':[0,.283,.993],'half_m':[.272,.003,.681]},
    {'center_m':[0,-.01625,.309],'half_m':[.272,.29625,.003]},
    {'center_m':[0,-.01625,1.677],'half_m':[.272,.29625,.003]}]
for x in (-.271,.271):
    for y in (-.205,.175):box('Shelf adjustment rail',(x,y,1.0),(.002,.020,1.32),'steel','InnerLiner')
shelf_heights=[.53,.76,.99,1.22,1.45]
for i,z in enumerate(shelf_heights,1):
    part=f'Shelf{i:02d}';collar('Bent shelf perimeter',.264,-.294,.234,z,.008,.006,'steel',part)
    for j in range(1,18):
        x=-.258+j*.516/18;wire('Shelf depth wire',(x,-.288,z+.0026),(x,.228,z+.0026),.0018,part)
    for j in range(1,13):
        y=-.288+j*.516/13;wire('Shelf cross wire',(-.258,y,z-.001),(.258,y,z-.001),.0018,part)
    for x in (-.264,.264):
        for y in (-.205,.175):box('Shelf wall support',(x,y,z-.015),(.015,.026,.022),'steel','InnerLiner')
    COLL[part]=[{'center_m':[0,-.030,z],'half_m':[.264,.264,.0045]}]

# Fixed header, independent sign material with externally adjustable emission.
box('Top lightbox housing',(0,-.0175,1.793),(.570,.625,.226),'steel','TopLightbox')
ring_front('Marquee front surround',-.285,.285,1.680,1.906,-.333,.006,.013,'steel','TopLightbox')
sign=box('Printed acrylic marquee',(0,-.332,1.793),(.544,.004,.200),'sign','TopLightbox')
uv=sign.data.uv_layers.new(name='PrintUV')
for p in sign.data.polygons:
    for li in p.loop_indices:
        v=sign.data.vertices[sign.data.loops[li].vertex_index].co;uv.data[li].uv=((v.x+.272)/.544,(v.z-1.693)/.200)
box('Interior light diffuser',(0,-.205,1.672),(.46,.036,.004),'diffuser','TopLightbox')
COLL['TopLightbox']=[{'center_m':[0,-.0175,1.793],'half_m':[.285,.3125,.113]}]

# A complete door assembly, with its true right-side hinge axis.
ring_front('Moving door perimeter',-.285,.285,.285,1.685,-.348,.020,.029,'steel','DoorFrame')
for z in (.45,1.52):cylinder('Door hinge barrel',(.289,-.338,z),.007,.055,'steel','DoorFrame',12)
glass=box('Closed solid display glass',(0,-.348,.985),(.512,.006,1.342),'glass','GlassDoor')
COLL['GlassDoor']=[{'center_m':[0,-.348,.985],'half_m':[.256,.003,.671]}]
COLL['DoorFrame']=[{'center_m':[x,-.348,.985],'half_m':[.0145,.010,.700]} for x in (-.2705,.2705)]+[
    {'center_m':[0,-.348,z],'half_m':[.256,.010,.0145]} for z in (.2995,1.6705)]
for z in (.69,1.13):
    box('Handle mounting pad',(-.270,-.360,z),(.026,.004,.040),'steel','DoorHandle',.001)
    cylinder('Handle stand-off',(-.270,-.3785,z),.007,.033,'steel','DoorHandle',12,'Y')
cylinder('Straight vertical door grip',(-.270,-.395,.91),.009,.460,'steel','DoorHandle',16)
COLL['DoorHandle']=[{'center_m':[-.270,-.381,.91],'half_m':[.015,.025,.250]}]

# Louvres occupy an actual compressor opening, rather than a decal or stacked face.
ring_front('Lower vent perimeter',-.285,.285,.130,.281,-.334,.008,.014,'steel','VentGrille')
for j in range(7):box('Horizontal cooling louvre',(0,-.332,.153+j*.018),(.542,.014,.009),'steel','VentGrille')
for x in (-.091,.091):box('Vent divider',(x,-.341,.2055),(.005,.004,.123),'steel','VentGrille')
COLL['VentGrille']=[{'center_m':[0,-.334,.2175],'half_m':[.285,.012,.0875]}]

def foot(part,x,y):
    n=12;rings=[(.018,0),(.026,.004),(.027,.010),(.027,.032),(.020,.038),(.012,.040),(.012,.100)]
    v=[(x+r*math.cos(i*math.tau/n),y+r*math.sin(i*math.tau/n),z) for r,z in rings for i in range(n)]
    f=[tuple(reversed(range(n)))]
    for j in range(len(rings)-1):f.extend((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n))
    f.append(tuple(range((len(rings)-1)*n,len(rings)*n)))
    o=mesh('Adjustable threaded foot',v,f,'dark',part);o.data.materials.append(M['steel'])
    for p in o.data.polygons:
        if p.center.z>.038:p.material_index=1
        p.use_smooth=len(p.vertices)==4
    COLL[part]=[{'center_m':[x,y,.050],'half_m':[.027,.027,.050]}]
for part,x,y in [('FootFL',-.250,-.245),('FootFR',.250,-.245),('FootRL',-.250,.245),('FootRR',.250,.245)]:foot(part,x,y)

# One mesh for each exported leaf. All three door meshes share the hinge origin.
PARTS={}
for key in keys:
    obs=[o for o in COL[key].objects if o.type=='MESH'];bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
        for modifier in list(o.modifiers):apply(o,modifier.name)
    bpy.context.view_layer.objects.active=obs[0]
    if len(obs)>1:bpy.ops.object.join()
    o=bpy.context.object;o.name='SM_BeverageDisplayFridge_'+key;o.data.name=o.name
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    if key in ('GlassDoor','DoorHandle','DoorFrame'):pivot=hinge.copy();parent=h
    elif key.startswith('Shelf'):pivot=Vector((0,-.03,shelf_heights[int(key[-2:])-1]));parent=groups['Shelves']
    elif key.startswith('Foot'):
        pivot=Vector((-.25 if key.endswith(('FL','RL')) else .25,-.245 if key.endswith(('FL','FR')) else .245,.10));parent=groups['BaseFeet']
    else:pivot=Vector((0,0,0));parent=None
    for v in o.data.vertices:v.co-=pivot
    if parent==h:o.parent=parent;o.location=(0,0,0)
    else:o.parent=parent;o.location=pivot
    o.matrix_parent_inverse=Matrix.Identity(4)
    PARTS[key]={'mesh':o.name,'object':o.name,'collection':COL[key].name,'pivot_m':list(pivot)}
for frame,angle in [(1,0),(15,0),(50,105),(95,105),(130,0),(150,0)]:
    h.rotation_euler.z=math.radians(angle);h.keyframe_insert(data_path='rotation_euler',frame=frame)
S.frame_start=1;S.frame_end=150;S.render.fps=30;S.frame_set(1);bpy.context.view_layer.update()

front=camera('01 Beverage fridge front45',(-2.7,-4.5,2.25),(0,0,.98),2.30)
camera('02 Beverage fridge open',(2.6,-4.5,2.20),(0,0,.98),2.30)
for name,pos,energy in [('Key strip',(-2.5,-3.4,3.0),450),('Upper fill',(1.4,1.5,3.4),340),('Side softbox',(-3.0,.7,2),240)]:
    data=bpy.data.lights.new(name,'AREA');o=bpy.data.objects.new(name,data);preview.objects.link(o)
    o.location=pos;o.rotation_euler=(Vector((0,0,1))-o.location).to_track_quat('-Z','Y').to_euler();data.energy=energy;data.shape='RECTANGLE';data.size=2.0;data.size_y=.30
box('Preview floor',(0,0,-.006),(100,100,.012),simple('Fridge preview floor',(.030,.028,.026),.87),preview)
S.world=bpy.data.worlds.new('Beverage fridge preview world');S.world.use_nodes=True;S.world.node_tree.nodes['Background'].inputs[0].default_value=(.14,.14,.14,1);S.world.node_tree.nodes['Background'].inputs[1].default_value=.3
S.unit_settings.system='METRIC';S.camera=front;S.render.engine='CYCLES';S.cycles.samples=28;S.cycles.use_denoising=True;S.cycles.transmission_bounces=10;S.eevee.use_raytracing=True
S.render.resolution_x=1300;S.render.resolution_y=1600;S.render.resolution_percentage=100;S.render.image_settings.file_format='PNG';S.view_settings.view_transform='AgX'
budget={}
for key,row in PARTS.items():
    me=bpy.data.objects[row['object']].data;me.calc_loop_triangles();budget[key]=len(me.loop_triangles)
    bm=bmesh.new();bm.from_mesh(me);assert all(e.is_manifold for e in bm.edges),key;assert bm.calc_volume(signed=True)>0,key;bm.free()
total=sum(budget.values());assert 4500<=total<=8000,(total,budget)
report={'success':True,'source_scene':S.name,'nominal_case_m':[.648,.752,1.93],'parts':PARTS,'collision_boxes':COLL,
    'planning_categories':[{'key':key,'label':label,'collection':cats[key].name} for key,label in definitions],
    'triangles_by_part':budget,'total_triangles':total,'preview_collection':preview.name,'front_camera':front.name,
    'open_camera':next(o.name for o in preview.objects if o.name.startswith('02 Beverage')),'no_products':True,
    'doors':{'main':{'hinge_m':list(hinge),'pivot_m':list(hinge),'closed_ue_cm':[28.9,33.8,28.5],
        'open_yaw_deg':-105,'open_blender_z_deg':105,'parent':h.name,'moving_parts':['GlassDoor','DoorHandle','DoorFrame']}}}
(ROOT/'model_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
for w in bpy.context.window_manager.windows:
    for area in w.screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='MATERIAL';sp.overlay.show_overlays=False;sp.region_3d.view_rotation=front.rotation_euler.to_quaternion();sp.region_3d.view_location=(0,0,.98);sp.region_3d.view_distance=2.8;sp.region_3d.view_perspective='ORTHO'
bpy.data.libraries.write(str(ROOT/'BeverageDisplayFridge.blend'),{S},fake_user=True,compress=True)
print('BEVERAGE_FRIDGE_CREATED_BY_MCP',json.dumps({'triangles':total,'parts':budget}))
