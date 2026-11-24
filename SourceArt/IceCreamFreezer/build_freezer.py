"""Planning-sheet curved sliding-lid freezer, meter scale, no display products."""
import bpy,bmesh,math,json,runpy
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parent
S=bpy.context.scene
assert S.name=='IceCreamFreezer' and not list(S.objects)
T=runpy.run_path(str(ROOT/'surface_tools.py'));Surface=T['Surface'];linear=T['linear_color']
M={}

def simple(name,rgb,rough=.5,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=linear(rgb)
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=linear(rgb)
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;return m
M['dark']=simple('M_Freezer_RubberAndCavity',(.08,.09,.085),.75)
M['red']=simple('M_Freezer_RockerRed',(.47,.075,.035),.43)
M['green']=simple('M_Freezer_GreenIndicator',(.13,.29,.11),.36)
M['amber']=simple('M_Freezer_AmberIndicator',(.48,.31,.07),.36)
for key,rgb,metal,rough in [('steel',(.58,.61,.60),.82,.40),('liner',(.69,.73,.73),.50,.36),('enamel',(.73,.72,.65),.12,.62)]:
    a=Surface('M_Freezer_'+key,rgb,rough,metal)
    n=a.noise('Subtle age and handling',32,2.5,-700,300)
    base=a.blend('Mottled finish',n,linear(tuple(x*.70 for x in rgb)),linear(rgb),300,300)
    if key=='enamel':
        sep=a.node('ShaderNodeSeparateXYZ','Height',-1000,-300);a.connect(a.position,sep.inputs[0])
        low=a.remap('Dirt at base',sep.outputs['Z'],(.10,.30),(.85,.04),-500,-250)
        speck=a.noise('Isolated rusty chips',135,2,-900,-40)
        mask=a.remap('Sparse chips',speck,(.57,.73),(0,1),-500,20)
        mask=a.math('Wear exposure','MULTIPLY',mask,low,-150,0)
        base=a.blend('Old enamel chips',mask,base,linear((.27,.18,.105)),600,300)
    a.connect(base,a.shader.inputs['Base Color'])
    a.bump('Very fine surface texture',n,.13,.00023,850,-250)
    M[key]=a.material
M['glass']=T['clear_glass']();M['glass'].name='M_Freezer_ClearCurvedGlass'
front=M['enamel'].copy();front.name='M_Freezer_PrintedFront';tree=front.node_tree
shader=next(n for n in tree.nodes if n.type=='BSDF_PRINCIPLED')
uv=tree.nodes.new('ShaderNodeUVMap');uv.uv_map='PrintUV'
for filename,target,space in [('T_FreezerFront_BaseColor.png','Base Color','sRGB'),('T_FreezerFront_Roughness.png','Roughness','Non-Color')]:
    image=bpy.data.images.load(str(ROOT/'Textures'/filename),check_existing=True);image.colorspace_settings.name=space;image.pack()
    n=tree.nodes.new('ShaderNodeTexImage');n.image=image;tree.links.new(uv.outputs[0],n.inputs['Vector']);tree.links.new(n.outputs['Color'],shader.inputs[target])
M['front']=front

root=bpy.data.collections.new('冰柜组件 · 规划书六类');S.collection.children.link(root)
category_defs=[('Body','01 外壳柜体'),('TopFrame','02 上框架与滑轨'),('SlidingGlassDoors','03 玻璃滑门（左右）'),
    ('Liner','04 内胆'),('Baskets','05 内部篮筐（两个）'),('Wheels','06 万向轮（四个）')]
cats={};groups={}
for k,name in category_defs:
    c=bpy.data.collections.new(name);root.children.link(c);cats[k]=c
    if k in ('SlidingGlassDoors','Baskets','Wheels'):
        e=bpy.data.objects.new(k,None);c.objects.link(e);e.empty_display_size=.03;groups[k]=e
keys=['Body','TopFrame','GlassDoorLeft','GlassDoorRight','Liner','BasketLeft','BasketRight','WheelFL','WheelFR','WheelRL','WheelRR']
COL={};COLL={k:[] for k in keys}
for k in keys:
    group='SlidingGlassDoors' if k.startswith('GlassDoor') else 'Baskets' if k.startswith('Basket') else 'Wheels' if k.startswith('Wheel') else k
    if group==k:COL[k]=cats[k]
    else:
        c=bpy.data.collections.new(k);cats[group].children.link(c);COL[k]=c
preview=bpy.data.collections.new('_PreviewOnly');S.collection.children.link(preview)

def mesh(name,v,f,mat,part):
    me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update()
    me.materials.append(M[mat] if isinstance(mat,str) else mat)
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(me);bm.free();me.update()
    wear=me.color_attributes.new(name='Wear',type='FLOAT_COLOR',domain='POINT');wear.data.foreach_set('color',[q for _ in v for q in (.65,0,0,1)])
    obj=bpy.data.objects.new(name,me);(COL[part] if isinstance(part,str) else part).objects.link(obj);return obj
def box(name,center,size,mat,part,bevel=0,collision=False):
    x,y,z=center;a,b,c=[n/2 for n in size]
    v=[(x+sx*a,y+sy*b,z+sz*c) for sz in (-1,1) for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1))]
    o=mesh(name,v,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,part)
    if bevel:
        m=o.modifiers.new('Single edge chamfer','BEVEL');m.width=bevel;m.segments=1;m.harden_normals=True
        m=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');m.keep_sharp=True
    if collision:COLL[part].append({'center_m':center,'half_m':[a,b,c]})
    return o
def rr(x,y,r):return [(-x+r,-y),(x-r,-y),(x,-y+r),(x,y-r),(x-r,y),(-x+r,y),(-x,y-r),(-x,-y+r)]
def cup(name,rings,mat,part):
    v=[(x,y,z) for a,b,r,z in rings for x,y in rr(a,b,r)];f=[tuple(reversed(range(8)))]
    for j in range(len(rings)-1):
        f.extend((j*8+i,j*8+(i+1)%8,(j+1)*8+(i+1)%8,(j+1)*8+i) for i in range(8))
    f.append(tuple(range((len(rings)-1)*8,len(rings)*8)));return mesh(name,v,f,mat,part)
def apply(o,name):
    bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.modifier_apply(modifier=name)
def cut(o,center,size):
    cutter=box('Temporary aperture cutter',center,size,'dark','Body')
    mod=o.modifiers.new('Real panel aperture','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    apply(o,mod.name);bpy.data.objects.remove(cutter,do_unlink=True)

# Closed insulated enclosure, with a genuine open top and a real grille aperture.
body=cup('Insulated cabinet shell',[(.65,.35,.010,.10),(.65,.35,.010,.765),(.610,.310,.009,.765),(.610,.310,.009,.145)],'enamel','Body')
cut(body,(-.63,.05,.280),(.16,.460,.240))
body.data.materials.append(M['front']);printuv=body.data.uv_layers.new(name='PrintUV')
for p in body.data.polygons:
    if p.normal.y<-.999 and p.center.y<-.349:
        p.material_index=body.data.materials.find(M['front'].name)
    for li in p.loop_indices:
        v=body.data.vertices[body.data.loops[li].vertex_index].co;printuv.data[li].uv=((v.x+.65)/1.30,(v.z-.10)/.665)
COLL['Body']=[{'center_m':[0,-.33,.4325],'half_m':[.65,.02,.3325]},
    {'center_m':[0,.33,.4325],'half_m':[.65,.02,.3325]},
    *[{'center_m':[x,0,.4325],'half_m':[.02,.31,.3325]} for x in (-.63,.63)],
    {'center_m':[0,0,.1225],'half_m':[.610,.310,.0225]}]
# The grille sits outside the case, rather than sharing its outer plane.
for y in (-.186,.286):box('Vent vertical perimeter',(-.654,y,.280),(.008,.012,.264),'steel','Body')
for z in (.154,.406):box('Vent horizontal perimeter',(-.654,.05,z),(.008,.460,.012),'steel','Body')
box('Dark air duct',(-.608,.05,.280),(.004,.460,.240),'dark','Body')
for j in range(7):box('Recessed vent louvre',(-.646,.05,.176+j*.033),(.012,.460,.014),'steel','Body')
for y in (-.025,.125):box('Grille upright',(-.658,y,.280),(.004,.006,.240),'steel','Body')
panel=box('Control housing',(.480,-.354,.222),(.155,.008,.075),'steel','Body',.0017)
box('Control dark inset',(.480,-.359,.222),(.134,.002,.056),'dark','Body')
box('Red power rocker',(.523,-.362,.222),(.020,.004,.031),'red','Body',.001)

def cylinder(name,center,r,depth,mat,part,sides=8,axis='Z'):
    c=Vector(center);direction=Vector((0,0,1)) if axis=='Z' else Vector((0,1,0));u=Vector((1,0,0));v=direction.cross(u)
    pts=[tuple(c+direction*h+u*(r*math.cos(i*math.tau/sides))+v*(r*math.sin(i*math.tau/sides))) for h in (-depth/2,depth/2) for i in range(sides)]
    f=[tuple(reversed(range(sides))),tuple(range(sides,2*sides))]+[(i,(i+1)%sides,sides+(i+1)%sides,sides+i) for i in range(sides)]
    return mesh(name,pts,f,mat,part)
for x,mat in ((.444,'green'),(.477,'amber')):cylinder('Unlit status lens',(x,-.362,.222),.008,.004,mat,'Body',8,'Y')

# Interior liner is its own closed thin shell, clear of the insulated body.
cup('Stainless inner tub',[(.606,.306,.020,.205),(.606,.306,.020,.765),(.599,.299,.019,.765),(.599,.299,.019,.217)],'liner','Liner')
COLL['Liner']=[{'center_m':[0,0,.211],'half_m':[.606,.306,.006]},
    *[{'center_m':[x,0,.491],'half_m':[.0035,.299,.274]} for x in (-.6025,.6025)],
    *[{'center_m':[0,y,.491],'half_m':[.599,.0035,.274]} for y in (-.3025,.3025)]]

def arch(y):return .800+.067*(1-(y/.345)**2)
def profile_x(name,x0,x1,points,mat,part):
    n=len(points);verts=[(x,y,z) for x in (x0,x1) for y,z in points]
    f=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
    return mesh(name,verts,f,mat,part)
for side in (-1,1):
    ys=[-.35+i*.70/8 for i in range(9)]
    poly=[(-.35,.765),(.35,.765)]+[(y,arch(y)+.012) for y in reversed(ys)]
    profile_x('Curved upper end cap',side*.638-.012,side*.638+.012,poly,'steel','TopFrame')
    COLL['TopFrame'].append({'center_m':[side*.638,0,.815],'half_m':[.012,.35,.050]})
for y in (-.338,.338):
    top=arch(y)+.012
    box('Upper long rim',(0,y,(.765+top)/2),(1.252,.024,top-.765),'steel','TopFrame')
    COLL['TopFrame'].append({'center_m':[0,y,(.765+top)/2],'half_m':[.626,.012,(top-.765)/2]})
    for offset in (0,.012):
        z=arch(.311)-.012-.004+offset
        box('Two-level sliding track',(0,math.copysign(.322,y),z-.002),(1.244,.008,.004),'dark','TopFrame')

DOORS={}
for side,sign in [('Left',-1),('Right',1)]:
    part='GlassDoor'+side;cx=sign*.301;off=0 if side=='Left' else .012
    ys=[-.304+i*.608/8 for i in range(9)]
    points=[(y,arch(y)-.012+off+.002) for y in ys]+[(y,arch(y)-.012+off-.002) for y in reversed(ys)]
    profile_x('Curved safety glass',cx-.301,cx+.301,points,'glass',part)
    for x in (cx-.306,cx+.306):
        ys=[-.318+i*.636/8 for i in range(9)]
        poly=[(y,arch(y)-.012+off+.004) for y in ys]+[(y,arch(y)-.012+off-.004) for y in reversed(ys)]
        profile_x('Sliding lid curved side frame',x-.005,x+.005,poly,'steel',part)
    for edge in (-1,1):
        ys=[edge*.304,edge*.318];ys.sort()
        poly=[(y,arch(y)-.012+off+.004) for y in ys]+[(y,arch(y)-.012+off-.004) for y in reversed(ys)]
        bar=profile_x('Lid front or rear frame',cx-.301,cx+.301,poly,'steel',part)
        if edge==-1:
            z=arch(.311)-.012+off
            cut(bar,(cx+sign*.225,-.311,z+.004),(.065,.008,.006))
    pivot=[cx,0,.80+off]
    DOORS[side.lower()]={'part':part,'mesh':'SM_IceCreamFreezer_'+part,'pivot_m':pivot,'closed_ue_cm':[cx*100,0,pivot[2]*100],
        'travel_cm':-sign*60.2,'parent':None}
    for a in range(4):
        y0=-.318+a*.159;y1=y0+.159;zm=(min(arch(y0),arch(y1))+max(arch(y0),arch(y1)))/2-.012+off
        COLL[part].append({'center_m':[cx,(y0+y1)/2,zm],'half_m':[.311,.0795,abs(arch(y1)-arch(y0))/2+.004]})

def wire(name,a,b,r,part):
    a,b=Vector(a),Vector(b);axis=(b-a).normalized();u=axis.cross(Vector((0,0,1)))
    if u.length<.1:u=axis.cross(Vector((0,1,0)))
    u.normalize();v=axis.cross(u)
    points=[tuple(p+u*r*math.cos(i*math.pi/2+math.pi/4)+v*r*math.sin(i*math.pi/2+math.pi/4)) for p in (a,b) for i in range(4)]
    return mesh(name,points,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'steel',part)
for side,sign in [('Left',-1),('Right',1)]:
    part='Basket'+side;cx=sign*.285;x0,x1=cx-.245,cx+.245;y0,y1=-.24,.24;bottom,top=.465,.695;r=.0015
    for z in (bottom,top):
        for y in (y0,y1):wire('Basket horizontal rim',(x0,y,z),(x1,y,z),r*1.2,part)
        for x in (x0,x1):wire('Basket depth rim',(x,y0,z),(x,y1,z),r*1.2,part)
    for j in range(1,8):
        x=x0+j*(x1-x0)/8
        wire('Basket floor length wire',(x,y0,bottom+.003),(x,y1,bottom+.003),r,part)
        for y in (y0,y1):wire('Basket face upright',(x,y,bottom),(x,y,top),r,part)
    for j in range(1,7):
        y=y0+j*(y1-y0)/7
        wire('Basket floor cross wire',(x0,y,bottom+.006),(x1,y,bottom+.006),r,part)
        for x in (x0,x1):wire('Basket end upright',(x,y,bottom),(x,y,top),r,part)
    for x in (x0,x1):
        for y in (y0,y1):wire('Basket corner upright',(x,y,bottom),(x,y,top),r,part)
    # Five thin wall/floor hulls retain an accessible basket cavity.
    COLL[part]=[{'center_m':[cx,0,bottom],'half_m':[.246,.241,.003]},
        *[{'center_m':[x,0,(bottom+top)/2],'half_m':[.003,.241,(top-bottom)/2]} for x in (x0,x1)],
        *[{'center_m':[cx,y,(bottom+top)/2],'half_m':[.246,.003,(top-bottom)/2]} for y in (y0,y1)]]

# Four genuine small caster assemblies, each independently separable.
for part,x,y in [('WheelFL',-.570,-.270),('WheelFR',.570,-.270),('WheelRL',-.570,.270),('WheelRR',.570,.270)]:
    box('Caster mount plate',(x,y,.094),(.072,.055,.012),'steel',part)
    cylinder('Swivel bearing',(x,y,.079),.021,.018,'steel',part,8)
    for yy in (-.017,.017):box('Caster steel fork',(x+.009,y+yy,.045),(.036,.006,.050),'steel',part)
    n=12;rings=[(.022,-.010),(.026,-.006),(.026,.006),(.022,.010)];verts=[]
    for r,yy in rings:
        verts.extend((x+.012+r*math.cos(i*math.tau/n),y+yy,.026+r*math.sin(i*math.tau/n)) for i in range(n))
    faces=[tuple(reversed(range(n)))]
    for j in range(3):faces.extend((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n))
    faces.append(tuple(range(3*n,4*n)))
    tyre=mesh('Rubber caster wheel',verts,faces,'dark',part);tyre.data.materials.append(M['steel']);tyre.data.polygons[0].material_index=1;tyre.data.polygons[-1].material_index=1
    for poly in tyre.data.polygons:poly.use_smooth=len(poly.vertices)==4
    cylinder('Wheel axle',(x+.012,y,.026),.005,.042,'steel',part,8,'Y')
    COLL[part]=[{'center_m':[x+.004,y,.050],'half_m':[.040,.030,.050]}]

# Consolidate each planning leaf to exactly one mesh, preserving source PrintUV.
PARTS={}
for key in keys:
    obs=[o for o in COL[key].objects if o.type=='MESH'];bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
        for mod in list(o.modifiers):apply(o,mod.name)
    bpy.context.view_layer.objects.active=obs[0]
    if len(obs)>1:bpy.ops.object.join()
    obj=bpy.context.object;obj.name='SM_IceCreamFreezer_'+key;obj.data.name=obj.name
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    if key.startswith('GlassDoor'):
        spec=DOORS['left' if key.endswith('Left') else 'right'];pivot=Vector(spec['pivot_m'])
        for v in obj.data.vertices:v.co-=pivot
        obj.location=pivot;obj.parent=groups['SlidingGlassDoors'];obj.matrix_parent_inverse=Matrix.Identity(4);spec['parent']=obj.name
        start=16 if key.endswith('Left') else 80
        for frame,alpha in [(1,0),(start,0),(start+18,1),(start+38,1),(start+56,0),(150,0)]:
            obj.location.x=pivot.x+alpha*spec['travel_cm']*.01;obj.keyframe_insert(data_path='location',frame=frame)
    elif key.startswith('Basket'):obj.parent=groups['Baskets']
    elif key.startswith('Wheel'):obj.parent=groups['Wheels']
    PARTS[key]={'mesh':'SM_IceCreamFreezer_'+key,'collection':COL[key].name,'object':obj.name,'pivot_m':list(DOORS['left' if key.endswith('Left') else 'right']['pivot_m']) if key.startswith('GlassDoor') else [0,0,0]}
S.frame_start=1;S.frame_end=150;S.render.fps=30;S.frame_set(1);bpy.context.view_layer.update()

def camera(name,position,target,scale):
    data=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,data);preview.objects.link(obj)
    obj.location=position;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler();data.type='ORTHO';data.ortho_scale=scale;return obj
front=camera('01 Freezer front45',(-2.6,-3.8,2.1),(0,0,.45),1.85)
camera('02 Freezer open top',(1.9,-2.6,2.5),(0,0,.45),1.85)
for name,pos,energy,size in [('Large soft key',(-2,-3,3),450,2.7),('Rear soft fill',(1,2,2.8),310,2.5),('Cool side fill',(-3,1,1.8),200,2)]:
    data=bpy.data.lights.new(name,'AREA');obj=bpy.data.objects.new(name,data);preview.objects.link(obj)
    obj.location=pos;obj.rotation_euler=(Vector((0,0,.4))-obj.location).to_track_quat('-Z','Y').to_euler();data.energy=energy;data.shape='DISK';data.size=size
box('Preview ground',(0,0,-.010),(100,100,.012),simple('Preview ground',(.034,.035,.032),.85),preview)
S.world=bpy.data.worlds.new('Freezer preview world');S.world.use_nodes=True;S.world.node_tree.nodes['Background'].inputs[0].default_value=(.14,.15,.15,1);S.world.node_tree.nodes['Background'].inputs[1].default_value=.3
S.camera=front;S.unit_settings.system='METRIC';S.render.engine='CYCLES';S.cycles.samples=28;S.cycles.use_denoising=True;S.cycles.transmission_bounces=10;S.eevee.use_raytracing=True
S.render.resolution_x=1500;S.render.resolution_y=1100;S.render.resolution_percentage=100;S.render.image_settings.file_format='PNG';S.view_settings.view_transform='AgX'
budget={}
for key,row in PARTS.items():
    obj=bpy.data.objects[row['object']];obj.data.calc_loop_triangles();budget[key]=len(obj.data.loop_triangles)
    bm=bmesh.new();bm.from_mesh(obj.data);assert all(e.is_manifold for e in bm.edges),key;bm.free()
total=sum(budget.values());assert 1800<=total<=3400,(total,budget)
report={'success':True,'source_scene':S.name,'nominal_case_m':[1.30,.70,.879],'parts':PARTS,'doors':DOORS,'collision_boxes':COLL,
    'triangles_by_part':budget,'total_triangles':total,'planning_categories':[{'key':k,'label':label,'collection':cats[k].name} for k,label in category_defs],
    'preview_collection':preview.name,'front_camera':front.name,'open_camera':next(o.name for o in preview.objects if o.name.startswith('02 Freezer')),
    'door_track_height_difference_m':.012,'no_products':True}
(ROOT/'model_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
for w in bpy.context.window_manager.windows:
    for area in w.screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='MATERIAL';sp.overlay.show_overlays=False;sp.region_3d.view_rotation=front.rotation_euler.to_quaternion();sp.region_3d.view_location=(0,0,.44);sp.region_3d.view_distance=2.3;sp.region_3d.view_perspective='ORTHO'
bpy.data.libraries.write(str(ROOT/'IceCreamFreezer.blend'),{S},fake_user=True,compress=True)
print('FREEZER_SOURCE_CREATED',json.dumps({'triangles':total,'parts':budget}))
