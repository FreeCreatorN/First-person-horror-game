"""MCP authored goods collection: 30 looks, 14 families, separable packaging."""
import bpy,bmesh,json,math,random
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parent;S=bpy.context.scene
assert S.name=='SnackIceCreamSet' and not list(S.objects)
ICE=json.loads((ROOT/'Textures/IcePackagingUV.json').read_text(encoding='utf-8'))['families']
SNACK=json.loads((ROOT/'Textures/SnackPackaging_AtlasManifest.json').read_text(encoding='utf-8'))['families']
ART={**ICE,**SNACK};M={};TEXTURES={};GEN={}
def linear(rgb):return tuple(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb)
def solid(name,color,rough=.5,metal=0,opacity=None):
    key='M_Goods_'+name;m=bpy.data.materials.new(key);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*linear(color),1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    p.inputs['Specular IOR Level'].default_value=.30
    spec={'type':'solid','color':list(color),'roughness':rough,'metallic':metal,'color_space':'srgb'}
    if opacity is not None:
        spec.update(type='translucent',opacity=opacity,ior=1.035,two_sided=True)
        p.inputs['Transmission Weight'].default_value=1;p.inputs['IOR'].default_value=1.45
        m.diffuse_color=(*linear(color),opacity)
    else:m.diffuse_color=(*linear(color),1)
    M[name]=m;GEN[key]=spec;return m
for name,color,rough in [('PaperInside',(.89,.86,.77),.76),('CreamVanilla',(.95,.85,.64),.46),('CreamPink',(.91,.51,.60),.46),
    ('CreamChocolate',(.34,.13,.055),.43),('CapRed',(.72,.055,.035),.33),('CapGold',(.84,.60,.13),.36),
    ('CandyRed',(.82,.075,.055),.28),('CandyGold',(.95,.69,.12),.3),('CandyPink',(.89,.35,.60),.3),
    ('CandyPurple',(.42,.15,.57),.3),('CandyGreen',(.15,.55,.23),.3)]:solid(name,color,rough)
solid('FoilSilver',(.78,.80,.77),.32,.65)
solid('ClearPET',(.96,.98,1),.10,opacity=.13);solid('JarGlass',(.94,.98,1),.095,opacity=.10)
solid('TrayPET',(.94,.97,1),.20,opacity=.22)
solid('JellyOrange',(.96,.52,.045),.16,opacity=.72);solid('JellyStrawberry',(.85,.16,.26),.16,opacity=.72);solid('JellyGrape',(.40,.12,.52),.16,opacity=.72)
for family,art in ART.items():
    name='M_Goods_'+family;m=bpy.data.materials.new(name);m.use_nodes=True;t=m.node_tree;p=t.nodes.get('Principled BSDF')
    p.inputs['Specular IOR Level'].default_value=.32
    for channel,socket,space in [('base_color','Base Color','sRGB'),('orm',None,'Non-Color'),('normal',None,'Non-Color')]:
        filename='T_Goods_Pack_Normal.png' if channel=='normal' else art[channel]
        im=bpy.data.images.load(str(ROOT/'Textures'/filename),check_existing=True);im.colorspace_settings.name=space;im.pack()
        node=t.nodes.new('ShaderNodeTexImage');node.image=im
        if socket:t.links.new(node.outputs['Color'],p.inputs[socket])
        elif channel=='orm':
            sep=t.nodes.new('ShaderNodeSeparateColor');t.links.new(node.outputs['Color'],sep.inputs[0]);t.links.new(sep.outputs['Green'],p.inputs['Roughness'])
        else:
            normal=t.nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.45;t.links.new(node.outputs['Color'],normal.inputs['Color']);t.links.new(normal.outputs[0],p.inputs['Normal'])
    M[family]=m;TEXTURES[name]={k:art[k] for k in ('base_color','orm')}
TEXTURES['normal']='T_Goods_Pack_Normal.png'

PRE=bpy.data.collections.new('_PreviewOnly');S.collection.children.link(PRE)
ROOTS={};COLS={};PARTS={};COLL={};PRODUCTS={};ASSEMBLIES={};CURRENT=None
def uvrect(family,index,front=True):
    flavor=ART[family]['flavors'][index]
    if family in ICE:return flavor['front_uv_rect' if front else 'back_uv_rect']
    return flavor['rects']['front' if front else 'back']['uv_content']
def uvpoint(rect,u,v):
    u=max(0,min(1,u));v=max(0,min(1,v));return (rect[0]+u*(rect[2]-rect[0]),rect[1]+v*(rect[3]-rect[1]))
def start_product(family,flavor,index,position):
    global CURRENT
    key=family+'_'+flavor;col=bpy.data.collections.new(key);S.collection.children.link(col);COLS[key]=col
    empty=bpy.data.objects.new(key+' display placement',None);col.objects.link(empty);empty.location=position;empty.empty_display_size=.012;ROOTS[key]=empty;CURRENT=key
    PRODUCTS[key]={'family':family,'flavor':flavor,'flavor_index':index,'position_m':list(position),'parts':[]};return key
def mesh(name,verts,faces,material):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();me.materials.append(M[material])
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();me.update();me.uv_layers.new(name='UVMap')
    o=bpy.data.objects.new(name,me);COLS[CURRENT].objects.link(o);return o
def select(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
def join(objects):
    if len(objects)>1:select(objects);bpy.ops.object.join()
    return objects[0]
def box(name,center,size,material):
    v=[tuple(center[i]+s[i]*size[i]/2 for i in range(3)) for s in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    return mesh(name,v,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],material)
def atlas_project(o,family,index,size,base=(0,0,0)):
    uv=o.data.uv_layers.active
    for p in o.data.polygons:
        n=p.normal;axis=max(range(3),key=lambda i:abs(n[i]));front=not(axis==1 and n.y>0)
        rect=uvrect(family,index,front)
        for li in p.loop_indices:
            co=o.data.vertices[o.data.loops[li].vertex_index].co-Vector(base)
            if axis==2:u=co.x/size[0]+.5;v=co.y/size[1]+.5
            elif axis==0:u=co.y/size[1]+.5;v=co.z/size[2]
            else:u=co.x/size[0]+.5 if front else .5-co.x/size[0];v=co.z/size[2]
            uv.data[li].uv=uvpoint(rect,u,v)
def rrect(w,d,r,z,n=8):
    pts=[]
    for cx,cy,start in [(w/2-r,d/2-r,0),(-w/2+r,d/2-r,90),(-w/2+r,-d/2+r,180),(w/2-r,-d/2+r,270)]:
        for i in range(n):
            a=math.radians(start+90*i/(n-1));pts.append((cx+r*math.cos(a),cy+r*math.sin(a),z))
    return pts
def ringmesh(name,rings,material,family=None,index=0,label_rows=None,label_z=None,inside='PaperInside',cyl=False):
    n=len(rings[0]);assert all(len(r)==n for r in rings)
    verts=[v for r in rings for v in r];faces=[tuple(reversed(range(n)))];meta=[None]
    for j in range(len(rings)-1):
        for i in range(n):faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i));meta.append((j,i))
    faces.append(tuple(range((len(rings)-1)*n,len(rings)*n)));meta.append(None)
    o=mesh(name,verts,faces,material);me=o.data;uv=me.uv_layers.active
    if family:
        me.materials.append(M[inside]);rows=set(label_rows if label_rows is not None else range(len(rings)-1))
        size=[max(v[a] for v in verts)-min(v[a] for v in verts) for a in range(3)]
        zlo,zhi=label_z or (min(v[2] for v in verts),max(v[2] for v in verts))
        for p in me.polygons:
            info=meta[p.index]
            if info is None or info[0] not in rows:p.material_index=1;continue
            j,i=info
            if cyl:
                front=(i+.5)/n<.5;rect=uvrect(family,index,front)
                for li in p.loop_indices:
                    vi=me.loops[li].vertex_index;u=(vi%n)/n
                    if i==n-1 and vi%n==0:u=1
                    localu=u*2 if front else (u-.5)*2
                    uv.data[li].uv=uvpoint(rect,localu,(me.vertices[vi].co.z-zlo)/(zhi-zlo))
            else:
                front=p.normal.y<.5;rect=uvrect(family,index,front)
                for li in p.loop_indices:
                    v=me.vertices[me.loops[li].vertex_index].co
                    if abs(p.normal.y)>=abs(p.normal.x):u=v.x/size[0]+.5 if front else .5-v.x/size[0]
                    else:u=v.y/size[1]+.5
                    uv.data[li].uv=uvpoint(rect,u,(v.z-zlo)/(zhi-zlo))
    for p in me.polygons:p.use_smooth=cyl and meta[p.index] is not None
    return o
def lathe(name,profile,material,n=20,family=None,index=0,label_rows=None,label_z=None,inside='PaperInside',wave=0):
    rings=[]
    for j,(radius,z) in enumerate(profile):
        ring=[]
        for i in range(n):
            a=math.tau*i/n-math.pi;r=radius*(1+wave*math.sin(a*5+j*.7))
            ring.append((r*math.cos(a),r*math.sin(a),z))
        rings.append(ring)
    return ringmesh(name,rings,material,family,index,label_rows,label_z,inside,True)
def thin_cap(name,profile,material,n=20,thickness=.0008,rib=False):
    verts=[]
    for radius,z in profile:
        for i in range(n):
            a=math.tau*i/n-math.pi;r=radius*(1+.012*math.cos(a*12) if rib else 1)
            verts.append((r*math.cos(a),r*math.sin(a),z))
    pole=len(verts);verts.append((0,0,profile[-1][1]));faces=[]
    for j in range(len(profile)-1):faces.extend((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n))
    faces.extend(((len(profile)-1)*n+i,(len(profile)-1)*n+(i+1)%n,pole) for i in range(n))
    o=mesh(name,verts,faces,material);select([o]);mod=o.modifiers.new('Real thin wall and open underside','SOLIDIFY');mod.thickness=thickness;mod.offset=-1;mod.use_even_offset=True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for p in o.data.polygons:p.use_smooth=True
    return o
def paper_shell(name,w,d,h,t,material,family=None,index=0,top=None,n=8):
    profiles=[(w,d,.004,0),(w,d,.004,h),(w-2*t,d-2*t,.003,h),(w-2*t,d-2*t,.003,t)]
    rings=[rrect(a,b,r,(top-z) if top is not None else z,n) for a,b,r,z in profiles]
    o=ringmesh(name,rings,material)
    if family:
        atlas_project(o,family,index,(w,d,h if top is None else top))
        o.data.materials.append(M['PaperInside'])
        perimeter=4*n
        for p in o.data.polygons:
            if 1+2*perimeter<=p.index<=3*perimeter or p.index==len(o.data.polygons)-1:p.material_index=1
    return o
def hull(center,half,matrix=None):
    pts=[Vector(tuple(center[i]+s[i]*half[i] for i in range(3))) for s in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    if matrix:pts=[matrix@v for v in pts]
    return {'vertices_m':[list(v) for v in pts]}
def shell_hulls(w,d,h,t,top=None):
    hs=[hull((x,0,h/2),(t/2,d/2,h/2)) for x in (-w/2+t/2,w/2-t/2)]+[hull((0,y,h/2),(w/2-t,t/2,h/2)) for y in (-d/2+t/2,d/2-t/2)]+[hull((0,0,t/2),(w/2-t,d/2-t,t/2))]
    if top is not None:
        for a in hs:
            for v in a['vertices_m']:v[2]=top-v[2]
    return hs
def finish(objects,part,pivot=(0,0,0),hulls=None):
    o=join(objects);name='SM_Goods_'+CURRENT+'_'+part;o.name=name;o.data.name=name
    for v in o.data.vertices:v.co-=Vector(pivot)
    o.parent=ROOTS[CURRENT];o.location=pivot;o.matrix_parent_inverse=Matrix.Identity(4)
    me=o.data;me.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(me)
    assert all(e.is_manifold for e in bm.edges),name
    assert bm.calc_volume(signed=True)>0,name
    bm.free()
    if not hulls:
        points=[v.co+Vector(pivot) for v in me.vertices];low=[min(v[a] for v in points) for a in range(3)];high=[max(v[a] for v in points) for a in range(3)]
        hulls=[hull([(a+b)/2 for a,b in zip(low,high)],[(b-a)/2 for a,b in zip(low,high)])]
    PARTS[name]={'mesh':name,'object':name,'product':CURRENT,'part':part,'pivot_m':list(pivot),'triangles':len(me.loop_triangles),'collection':COLS[CURRENT].name}
    COLL[name]=hulls;PRODUCTS[CURRENT]['parts'].append(name);return o
def assembly():ASSEMBLIES['BP_Goods_'+CURRENT]=list(PRODUCTS[CURRENT]['parts'])

def sealed_bag(family,flavor,index,position,w,h,depth):
    start_product(family,flavor,index,position);rings=[];N=12
    for j,(fz,ws,ds) in enumerate([(0,.49,.04),(.045,.49,.10),(.12,.48,.65),(.30,.52,.95),(.53,.53,1),(.78,.51,.90),(.90,.48,.58),(.96,.49,.10),(1,.49,.04)]):
        ring=[]
        for i in range(N):
            a=math.tau*i/N-math.pi;c=math.cos(a);si=math.sin(a)
            x=math.copysign(abs(c)**.38,c)*w*ws;y=math.copysign(abs(si)**.65,si)*depth*.5*ds
            y+=.0007*math.sin(j*1.9+i*2.3)*math.sin(math.pi*fz)
            ring.append((x,y,h*fz))
        rings.append(ring)
    o=ringmesh('Sealed pillow wrapper',rings,family);atlas_project(o,family,index,(w*1.06,depth,h))
    objects=[o]
    for top in (False,True):
        v=[];segments=10
        for i in range(segments+1):
            x=(-.49+i/segments*.98)*w;zig=.00065*(1 if i%2 else -1)
            lo=h-.0055 if top else -.0003+zig;hi=h+.0003+zig if top else .0055
            v.extend([(x,-.00095,lo),(x,.00095,lo),(x,.00095,hi),(x,-.00095,hi)])
        f=[(3,2,1,0),tuple(range(segments*4,segments*4+4))]
        for i in range(segments):f.extend((4*i+k,4*(i+1)+k,4*(i+1)+(k+1)%4,4*i+(k+1)%4) for k in range(4))
        strip=mesh('Crimped heat seal',v,f,family);atlas_project(strip,family,index,(w,depth,h));objects.append(strip)
    finish(objects,'Pack')

def box_ice(flavor,index,position):
    start_product('BoxIce',flavor,index,position);w,d,h=.16,.075,.1005;t=.0015
    body=paper_shell('Printed folded ice carton',w,d,h,t,'BoxIce','BoxIce',index)
    finish([body],'Body',hulls=shell_hulls(w,d,h,t))
    lid=paper_shell('Separate carton lid',w+.003,d+.003,.0135,t,'BoxIce','BoxIce',index,top=.102)
    # The outer top is artwork; only its hidden underside uses the plain lining.
    lid.data.polygons[0].material_index=0;atlas_project(lid,'BoxIce',index,(w+.003,d+.003,.102))
    finish([lid],'Lid',(0,0,.0885),shell_hulls(w+.003,d+.003,.0135,t,top=.102));assembly()

def cup_ice(flavor,index,position):
    start_product('CupIce',flavor,index,position)
    p=[(.025,0),(.027,.003),(.034,.069),(.035,.072),(.035,.074),(.0335,.074),(.033,.071),(.025,.004)]
    body=lathe('Tapered paper cup',p,'CupIce',20,'CupIce',index,[1,2],(.003,.072))
    cream=lathe('Ruffled ice cream',[(.028,.067),(.030,.079),(.027,.087),(.023,.096),(.014,.105),(.002,.111)],'CreamPink' if flavor=='Strawberry' else 'CreamVanilla',20,wave=.08)
    finish([body,cream],'Body')
    outer=[(.0348,.074),(.039,.074),(.040,.075),(.038,.078),(.035,.094),(.024,.111),(.004,.118)]
    lid=thin_cap('Thin clear dome and snap rim',outer,'ClearPET',16,.0008)
    finish([lid],'Dome',(0,0,.074));assembly()

def cone(flavor,index,position):
    start_product('Cone',flavor,index,position)
    o=lathe('Sealed cone wrapper',[(.0018,0),(.007,.021),(.015,.058),(.023,.100),(.029,.139),(.030,.145),(.029,.149)],'Cone',24,'Cone',index,[0,1,2,3,4,5],(0,.149))
    lid=lathe('Folded foil top',[(.0285,.149),(.0295,.150),(.002,.151)],'FoilSilver',24)
    finish([o,lid],'Pack')

def family_tub(flavor,index,position):
    start_product('FamilyTub',flavor,index,position);w,d,h=.22,.15,.10;t=.0018
    profiles=[(.184,.12,.018,0),(.19,.125,.02,.005),(.217,.147,.021,.094),(.22,.15,.022,.098),(.22,.15,.022,.10),(.2164,.1464,.020,.10),(.213,.143,.02,.094),(.183,.119,.016,.005)]
    body=ringmesh('Rounded family ice tub',[rrect(*p,8) for p in profiles],'FamilyTub','FamilyTub',index,[1,2],(.005,.098))
    fill=ringmesh('Ice cream below tub lid',[rrect(.177,.113,.015,.008,8),rrect(.209,.137,.018,.094,8),rrect(.208,.136,.018,.096,8)],'CreamVanilla' if flavor=='Vanilla' else 'CreamPink')
    finish([body,fill],'Body',hulls=shell_hulls(w,d,h,t))
    lid=ringmesh('Seated rounded family lid',[rrect(.225,.155,.024,.1015,8),rrect(.225,.155,.024,.094,8),rrect(.222,.152,.0225,.094,8),rrect(.222,.152,.0225,.100,8)],'FamilyTub')
    atlas_project(lid,'FamilyTub',index,(.225,.155,.1015))
    lid.data.materials.append(M['PaperInside']);lid.data.polygons[-1].material_index=1
    finish([lid],'Lid',(0,0,.094),shell_hulls(.225,.155,.0075,.0015,top=.1015));assembly()

def biscuit(flavor,index,position):
    start_product('Biscuits',flavor,index,position)
    body=paper_shell('Real hollow biscuit sleeve',.08,.06,.14,.0012,'Biscuits','Biscuits',index,n=8)
    trans=Matrix.Translation(Vector((-.07,0,.04)))@Matrix.Rotation(math.pi/2,4,'Y')
    for v in body.data.vertices:v.co=trans@v.co
    atlas_project(body,'Biscuits',index,(.14,.06,.08))
    hs=shell_hulls(.08,.06,.14,.0012)
    for a in hs:a['vertices_m']=[list(trans@Vector(v)) for v in a['vertices_m']]
    finish([body],'Body',hulls=hs)
    tray=paper_shell('Open clear biscuit insert',.133,.054,.014,.0008,'TrayPET',n=8)
    for v in tray.data.vertices:v.co.z+=.0012
    ribs=[box('Tray divider',(x,0,.005),(.0015,.051,.006),'TrayPET') for x in (-.022,.022)]
    for obj in [tray,*ribs]:
        for v in obj.data.vertices:v.co.y*=.94
    finish([tray,*ribs],'Tray',(0,0,.0012),[hull((0,0,.0082),(.0665,.02538,.007))]);assembly()

def jelly(flavor,index,position):
    start_product('Jelly',flavor,index,position);mat='Jelly'+flavor
    body=lathe('Glossy filled jelly cup',[(.023,0),(.024,.003),(.030,.047),(.032,.050),(.032,.053),(.030,.054)],mat,20)
    finish([body],'Cup')
    film=lathe('Independent printed sealing film',[(.033,.054),(.0335,.0546),(.033,.055)],'Jelly',20)
    atlas_project(film,'Jelly',index,(.067,.067,.055));finish([film],'Film',(0,0,.054));assembly()

def candy_jar(flavor,index,position):
    start_product('CandyJar',flavor,index,position)
    profile=[(.037,0),(.042,.004),(.044,.015),(.044,.034),(.044,.090),(.043,.111),(.036,.126),(.035,.139),(.033,.139),(.034,.127),(.041,.109),(.041,.015),(.035,.004)]
    body=lathe('Glass candy jar with flush printed band',profile,'CandyJar',20,'CandyJar',index,[3],(.034,.090),inside='JarGlass')
    finish([body],'Jar',hulls=[hull((0,0,.07),(.044,.044,.07))])
    cap_profile=[(.038,.154),(.039,.1525),(.039,.139),(.0375,.137),(.0355,.137),(.03531,.139),(.037,.152)]
    cap=lathe('Hollow seated ribbed screw lid',cap_profile,'CapRed' if flavor=='Fruit' else 'CapGold',24)
    for v in cap.data.vertices:
        if v.index//24<4:
            a=math.atan2(v.co.y,v.co.x);scale=1+.008*math.cos(a*12);v.co.x*=scale;v.co.y*=scale
    finish([cap],'Lid',(0,0,.137))
    pieces=[];colors=['CandyRed','CandyGold','CandyPink','CandyPurple','CandyGreen'];rng=random.Random(919+index)
    if flavor=='Fruit':
        for layer in range(5):
            for i in range(6):
                a=math.tau*i/6+layer*.22;c=Vector((.022*math.cos(a),.022*math.sin(a),.023+layer*.020));rot=Matrix.Rotation(a+.4,4,'Z');color=colors[(layer*6+i)%len(colors)]
                b=box('Wrapped candy',tuple(c),(.011,.006,.005),color)
                for v in b.data.vertices:v.co=c+rot@(v.co-c)
                pieces.append(b)
                for side in (-1,1):
                    vv=[(.005*side,-.003,-.002),(.005*side,.003,-.002),(.005*side,0,.003),(.009*side,0,0)]
                    pieces.append(mesh('Twisted wrapper end',[tuple(c+rot@Vector(v)) for v in vv],[(0,2,1),(0,1,3),(1,2,3),(2,0,3)],color))
    else:
        for i in range(14):
            layer=i//7;a=math.tau*(i%7)/7+layer*math.pi/7;r=.024;c=Vector((r*math.cos(a),r*math.sin(a),.085+layer*.021));color=colors[i%5]
            stick=lathe('Lollipop stick',[(.0007,.017),(.0007,c.z-.003)],'PaperInside',6)
            for v in stick.data.vertices:v.co.x+=c.x;v.co.y+=c.y
            head=lathe('Wrapped lollipop head',[(.002,c.z-.009),(.006,c.z-.006),(.007,c.z),(.006,c.z+.006),(.002,c.z+.009)],color,8)
            for v in head.data.vertices:v.co.x+=c.x;v.co.y+=c.y
            pieces.extend([stick,head])
    finish(pieces,'Contents');assembly()

families=[('BoxIce',['Vanilla','Strawberry'],(-.62,.65)),('IcePop',['Milk','Orange'],(0,.65)),('ChocoBar',['Chocolate','Vanilla'],(.62,.65)),
    ('CupIce',['Strawberry','Vanilla'],(-.62,.25)),('Cone',['Vanilla','Chocolate','Strawberry'],(0,.25)),('FamilyTub',['Vanilla','Strawberry'],(.62,.25)),
    ('Chips',['Original','Cucumber'],(-.78,-.22)),('Biscuits',['Butter','Milk'],(-.26,-.22)),('CandyBag',['Fruit','Mint'],(.26,-.22)),('Bakery',['Bread','Cake'],(.78,-.22)),
    ('Spicy',['Hot','Original'],(-.78,-.64)),('Nuts',['Seeds','Peanut'],(-.26,-.64)),('Jelly',['Orange','Strawberry','Grape'],(.26,-.64)),('CandyJar',['Fruit','Mint'],(.78,-.64))]
for family,flavors,(cx,cy) in families:
    spacing=.24 if family=='FamilyTub' else .18 if family in ('BoxIce','Biscuits') else .09 if family in ('CupIce','Cone','Jelly','CandyJar') else .125
    for index,flavor in enumerate(flavors):
        position=(cx+(index-(len(flavors)-1)/2)*spacing,cy,0)
        if family=='BoxIce':box_ice(flavor,index,position)
        elif family=='CupIce':cup_ice(flavor,index,position)
        elif family=='Cone':cone(flavor,index,position)
        elif family=='FamilyTub':family_tub(flavor,index,position)
        elif family=='Biscuits':biscuit(flavor,index,position)
        elif family=='Jelly':jelly(flavor,index,position)
        elif family=='CandyJar':candy_jar(flavor,index,position)
        else:
            whd={'IcePop':(.063,.17,.018),'ChocoBar':(.074,.17,.026),'Chips':(.10,.14,.035),'CandyBag':(.085,.125,.027),'Bakery':(.105,.14,.035),'Spicy':(.085,.16,.027),'Nuts':(.09,.14,.03)}[family]
            sealed_bag(family,flavor,index,position,*whd)

def camera(name,loc,target,scale):
    d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);PRE.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='ORTHO';d.ortho_scale=scale;return o
hero=camera('01 Goods overview',(1.05,-2.3,2.2),(0,0,.045),2.28)
camera('02 Ice cream details',(.7,-1.5,1.2),(0,.44,.07),1.82)
camera('03 Snack details',(.8,-1.8,1.35),(0,-.43,.065),1.93)
# Preview objects stay out of every FBX and assembled Blueprint.
floor=box('Preview ground',(0,0,-.006),(100,100,.012),'PaperInside')
for col in list(floor.users_collection):col.objects.unlink(floor)
PRE.objects.link(floor);fm=bpy.data.materials.new('Preview dark neutral');fm.use_nodes=True;fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.0025,.003,.004,1);fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.9;floor.data.materials.clear();floor.data.materials.append(fm)
font=bpy.data.fonts.load('C:/Windows/Fonts/msyh.ttc');names={'BoxIce':'盒装雪糕','IcePop':'袋装冰棒','ChocoBar':'脆皮雪糕','CupIce':'杯装雪糕','Cone':'甜筒雪糕','FamilyTub':'家庭装雪糕','Chips':'袋装薯片','Biscuits':'饼干盒','CandyBag':'糖果袋','Bakery':'面包 / 蛋糕','Spicy':'辣条','Nuts':'瓜子 / 花生','Jelly':'果冻杯','CandyJar':'糖果罐'}
for family,flavors,(cx,cy) in families:
    d=bpy.data.curves.new(names[family],'FONT');d.body=names[family];d.font=font;d.align_x='CENTER';d.size=.024;o=bpy.data.objects.new(names[family],d);PRE.objects.link(o);o.location=(cx,cy-.105,.001)
    mat=bpy.data.materials.get('Preview label white') or bpy.data.materials.new('Preview label white');mat.diffuse_color=(.72,.74,.76,1);d.materials.append(mat)
for name,loc,power,size in [('Key',(-1.6,-1.8,2.8),330,2.0),('Fill',(1.6,-.5,2.0),220,1.6),('Rim',(0,2,2.5),360,1.7)]:
    d=bpy.data.lights.new(name,'AREA');o=bpy.data.objects.new(name,d);PRE.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,.1))-o.location).to_track_quat('-Z','Y').to_euler();d.energy=power;d.size=size
S.world=bpy.data.worlds.new('Goods studio environment');S.world.use_nodes=True;S.world.node_tree.nodes['Background'].inputs[0].default_value=(.14,.16,.20,1);S.world.node_tree.nodes['Background'].inputs[1].default_value=.23
S.unit_settings.system='METRIC';S.camera=hero;S.render.engine='CYCLES';S.cycles.samples=32;S.cycles.use_denoising=True;S.cycles.transmission_bounces=12;S.eevee.use_raytracing=True
S.render.resolution_x=2000;S.render.resolution_y=1500;S.render.resolution_percentage=100;S.render.image_settings.file_format='PNG';S.view_settings.view_transform='AgX';S.view_settings.exposure=-.3;S.frame_start=1;S.frame_end=1;S.frame_set(1)
bpy.context.view_layer.update()
budget={key:sum(PARTS[p]['triangles'] for p in product['parts']) for key,product in PRODUCTS.items()}
report={'success':True,'source_scene':S.name,'products':PRODUCTS,'parts':PARTS,'collision_hulls':COLL,'assemblies':ASSEMBLIES,
    'textures':TEXTURES,'generic_materials':GEN,'product_triangles':budget,'total_triangles':sum(budget.values()),'product_count':len(PRODUCTS),
    'family_count':len(families),'preview_collection':PRE.name,'front_camera':hero.name,'budget_target_met':8000<=sum(budget.values())<=18000,
    'normal_convention':'OpenGL +Y'}
assert len(PRODUCTS)==30 and len(PARTS)==45 and len(ASSEMBLIES)==13,(len(PRODUCTS),len(PARTS),len(ASSEMBLIES))
(ROOT/'model_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for w in bpy.context.window_manager.windows:
    for area in w.screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='MATERIAL';sp.overlay.show_overlays=False;sp.region_3d.view_rotation=hero.rotation_euler.to_quaternion();sp.region_3d.view_location=(0,0,.05);sp.region_3d.view_distance=2.5;sp.region_3d.view_perspective='ORTHO'
bpy.data.libraries.write(str(ROOT/'SnackIceCreamSet.blend'),{S},fake_user=True,compress=True)
print('GOODS_CREATED_BY_MCP',json.dumps({'products':len(PRODUCTS),'meshes':len(PARTS),'tris':report['total_triangles'],'budget':budget}))
