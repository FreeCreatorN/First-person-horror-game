"""Build eight reference-based low-poly carton looks in the connected Blender scene."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parent;S=bpy.context.scene
assert S.name=='CardboardBoxSet' and len(S.objects)==0
LAYOUT=json.loads((ROOT/'Textures/TextureLayout.json').read_text(encoding='utf-8'))
M={}
for key in ['Standard','Damaged','Fruit','Water','Noodles','Tape','Edge']:
    filekey={'Edge':'Plain'}.get(key,key)
    m=bpy.data.materials.new('M_Cardboard_'+key);m.use_nodes=True;t=m.node_tree
    p=t.nodes.get('Principled BSDF');p.inputs['Specular IOR Level'].default_value=.26
    for channel,socket,space in [('BaseColor','Base Color','sRGB'),('ORM',None,'Non-Color'),('Shared_Normal',None,'Non-Color')]:
        filename='T_Carton_Shared_Normal.png' if channel=='Shared_Normal' else f'T_Carton_{filekey}_{channel}.png'
        img=bpy.data.images.load(str(ROOT/'Textures'/filename),check_existing=True);img.colorspace_settings.name=space;img.pack()
        n=t.nodes.new('ShaderNodeTexImage');n.image=img
        if socket:t.links.new(n.outputs['Color'],p.inputs[socket])
        elif channel=='ORM':
            sep=t.nodes.new('ShaderNodeSeparateColor');t.links.new(n.outputs['Color'],sep.inputs[0]);t.links.new(sep.outputs['Green'],p.inputs['Roughness'])
        else:
            normal=t.nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.32;t.links.new(n.outputs['Color'],normal.inputs['Color']);t.links.new(normal.outputs[0],p.inputs['Normal'])
    M[key]=m
PRE=bpy.data.collections.new('_PreviewOnly');S.collection.children.link(PRE)
specs=[('A','A 封箱纸箱',(-1.65,.60,0)),('B','B 开口纸箱',(-.55,.60,0)),('C','C 储物纸箱',(.55,.60,0)),('D','D 破旧纸箱',(1.65,.60,0)),
       ('E','E 堆叠组合',(-1.65,-.60,0)),('F','F 蔬果纸箱',(-.55,-.60,0)),('G','G 矿泉水纸箱',(.55,-.60,0)),('H','H 方便面纸箱',(1.65,-.60,0))]
GROUPS={};COL={};PARTS={};COLL={};SOURCE_POSES={}
for code,label,pose in specs:
    c=bpy.data.collections.new(label);S.collection.children.link(c);COL[code]=c
    root=bpy.data.objects.new(code+' preview placement',None);c.objects.link(root);root.location=pose;root.empty_display_size=.035;GROUPS[code]=root

def activate(o):
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
def mesh(name,verts,faces,mat,group):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();me.update()
    o=bpy.data.objects.new(name,me);COL[group].objects.link(o);me.materials.append(M[mat]);return o
def bevel(o,width=.0015):
    activate(o);mod=o.modifiers.new('Cardboard edge roll','BEVEL');mod.width=width;mod.segments=1;mod.limit_method='ANGLE';mod.angle_limit=.65
    bpy.ops.object.modifier_apply(modifier=mod.name)
def cube(name,center,size,mat,group):
    v=[tuple(center[i]+s[i]*size[i]/2 for i in range(3)) for s in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    return mesh(name,v,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,group)
def atlas_uv(o,size,center=(0,0,0),plain=False,open_shell=False):
    me=o.data;uv=me.uv_layers.new(name='UVMap');dims=list(size)
    if open_shell and M['Edge'] not in me.materials[:]:me.materials.append(M['Edge'])
    for p in me.polygons:
        n=p.normal;axis=max(range(3),key=lambda i:abs(n[i]));sign=1 if n[axis]>0 else -1
        face=('Right' if sign>0 else 'Left') if axis==0 else ('Back' if sign>0 else 'Front') if axis==1 else ('Top' if sign>0 else 'Bottom')
        is_plain=plain
        if open_shell:
            is_plain= not (axis<2 and sign*(p.center[axis]-center[axis])>dims[axis]/2-.001)
            if axis==2 and sign<0 and p.center.z<center[2]+.001:is_plain=False
            p.material_index=1 if is_plain else 0
        rect=(0,0,1,1) if is_plain else LAYOUT['tile_rects_uv'][face]
        for li in p.loop_indices:
            co=me.vertices[me.loops[li].vertex_index].co-Vector(center)
            if axis==0:u=(co.y/dims[1]+.5) if sign<0 else (.5-co.y/dims[1]);v=co.z/dims[2]
            elif axis==1:u=(co.x/dims[0]+.5) if sign<0 else (.5-co.x/dims[0]);v=co.z/dims[2]
            else:u=co.x/dims[0]+.5;v=co.y/dims[1]+.5
            u=max(0,min(1,u));v=max(0,min(1,v))
            uv.data[li].uv=(rect[0]+u*(rect[2]-rect[0]),rect[1]+v*(rect[3]-rect[1]))
def cubegrid(name,w,d,h,mat,group,damage=False):
    v=[];faces=[];seen={};N=4
    def index(p):
        key=tuple(round(x,9) for x in p)
        if key not in seen:seen[key]=len(v);v.append(key)
        return seen[key]
    for axis in range(3):
        others=[i for i in range(3) if i!=axis]
        for sign in (-1,1):
            ids={}
            for a in range(N+1):
                for b in range(N+1):
                    p=[0,0,0];p[axis]=sign*.5;p[others[0]]=a/N-.5;p[others[1]]=b/N-.5
                    ids[a,b]=index((p[0]*w,p[1]*d,(p[2]+.5)*h))
            for a in range(N):
                for b in range(N):faces.append([ids[a,b],ids[a+1,b],ids[a+1,b+1],ids[a,b+1]])
    o=mesh(name,v,faces,mat,group)
    for vert in o.data.vertices:
        x,y,z=vert.co
        if damage:
            # Depress the top and crush the front-right edge without adding topology.
            if z>h-.001:vert.co.z-=.026*math.exp(-((x-.055)/.22)**2-((y+.035)/.16)**2)
            if x>w/2-.001:
                vert.co.x-=.018*math.exp(-((z-.18)/.10)**2)*(.5+.5*math.cos(y*12))
            if y<-.199:vert.co.y+=.017*math.exp(-((x-.20)/.14)**2-((z-.16)/.12)**2)
            if z>.005:vert.co.x+=.0035*math.sin(27*y+18*z)
        elif z>h-.001 and abs(x)<.0001:vert.co.z-=.0012
    o.data.update();bevel(o,.0018 if damage else .0014);atlas_uv(o,(w,d,h));return o
def shell(name,w,d,h,t,mat,group,inverted=False,top=0):
    rings=[(w/2,d/2,0),(w/2,d/2,h),(w/2-t,d/2-t,h),(w/2-t,d/2-t,t)]
    v=[(x,y,top-z if inverted else z) for a,b,z in rings for x,y in [(-a,-b),(a,-b),(a,b),(-a,b)]]
    f=[(3,2,1,0),(12,13,14,15)]
    for j in range(3):f.extend((j*4+i,j*4+(i+1)%4,(j+1)*4+(i+1)%4,(j+1)*4+i) for i in range(4))
    return mesh(name,v,f,mat,group)
def boxhull(center,half,rotation=None):
    points=[Vector(tuple(center[i]+sg[i]*half[i] for i in range(3))) for sg in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    if rotation:points=[rotation@p for p in points]
    return {'vertices_m':[list(p) for p in points]}
def bodyhulls(w,d,h,t=.004):
    return [boxhull((x,0,h/2),(t/2,d/2,h/2)) for x in (-w/2+t/2,w/2-t/2)]+[
        boxhull((0,y,h/2),(w/2-t,t/2,h/2)) for y in (-d/2+t/2,d/2-t/2)]+[boxhull((0,0,t/2),(w/2-t,d/2-t,t/2))]
def finish(o,key,group,pivot=(0,0,0),hulls=None):
    o.name='SM_CardboardBox_'+key;o.data.name=o.name
    assert o.name=='SM_CardboardBox_'+key
    for vert in o.data.vertices:vert.co-=Vector(pivot)
    o.parent=GROUPS[group];o.location=pivot;o.matrix_parent_inverse=Matrix.Identity(4)
    me=o.data;me.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(me)
    assert all(e.is_manifold for e in bm.edges),key
    assert bm.calc_volume(signed=True)>0,key
    bm.free()
    PARTS[key]={'mesh':o.name,'object':o.name,'collection':COL[group].name,'pivot_m':list(pivot),'variant':group,'triangles':len(me.loop_triangles)}
    COLL[key]=hulls or [];SOURCE_POSES[group]=list(GROUPS[group].location)
    return o

def closed_handled(name,mat,group):
    o=shell(name,.6,.4,.3,.004,mat,group)
    outline=[]
    for centery,start in [(.045,-90),(-.045,90)]:
        for i in range(9):
            a=math.radians(start+i*180/8);outline.append((centery+.016*math.cos(a),.222+.016*math.sin(a)))
    n=len(outline);v=[(x,y,z) for x in (-.34,.34) for y,z in outline]
    f=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
    cutter=mesh('Temporary side handle cutter',v,f,'Edge',group);activate(o)
    mod=o.modifiers.new('Real short-side hand holes','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
    bevel(o,.0007);atlas_uv(o,(.6,.4,.3),open_shell=True)
    cap=cube('Closed top under sealing tape',(0,0,.298),(.592,.392,.004),mat,group);bevel(cap,.0005);atlas_uv(cap,(.6,.4,.3))
    cap.data.materials.append(M['Edge'])
    for p in cap.data.polygons:
        if p.normal.z<.99:p.material_index=1
    activate(o);cap.select_set(True);bpy.ops.object.join();return o

a=cubegrid('Regular sealed carton',.6,.4,.3,'Standard','A');finish(a,'A_Sealed','A',hulls=[boxhull((0,0,.15),(.3,.2,.15))])
b=shell('Open carton with real inner walls',.6,.4,.3,.004,'Standard','B');bevel(b,.0007);atlas_uv(b,(.6,.4,.3),open_shell=True)
finish(b,'B_Body','B',hulls=bodyhulls(.6,.4,.3))
flap_specs=[('Front',(0,-.198,.300),(.592,.2,.003),(0,.1,0),'X',125),
            ('Back',(0,.198,.300),(.592,.2,.003),(0,-.1,0),'X',-115),
            ('Left',(-.298,0,.300),(.30,.392,.003),(.15,0,0),'Y',-140),
            ('Right',(.298,0,.300),(.30,.392,.003),(-.15,0,0),'Y',130)]
flaps={}
for name,pivot,size,center,axis,deg in flap_specs:
    o=cube('Folded cardboard '+name,center,size,'Edge','B');bevel(o,.0005);atlas_uv(o,size,center=(center[0],center[1],-size[2]/2),plain=True)
    rot=Matrix.Rotation(math.radians(deg),4,axis);transform=Matrix.Translation(Vector(pivot))@rot
    for v in o.data.vertices:v.co=transform@v.co
    hull=boxhull(center,[a/2 for a in size],transform)
    finish(o,'B_Flap'+name,'B',pivot,[hull]);flaps[name]={'pivot_m':list(pivot),'axis':axis,'open_blender_degrees':deg}

c=shell('Storage carton with hand holes',.6,.4,.302,.004,'Edge','C')
# A single capsule cutter passes through front and back, creating two real holes.
outline=[]
for centerx,start in [(.055,-90),(-.055,90)]:
    for i in range(9):
        angle=math.radians(start+i*180/8);outline.append((centerx+.018*math.cos(angle),.222+.018*math.sin(angle)))
n=len(outline);v=[(x,y,z) for y in (-.24,.24) for x,z in outline]
f=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
cut=mesh('Temporary handle aperture',v,f,'Edge','C');activate(c);mod=c.modifiers.new('True carry handle holes','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut
bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
bevel(c,.0006);atlas_uv(c,(.6,.4,.302),plain=True);finish(c,'C_Body','C',hulls=bodyhulls(.6,.4,.302))
lid=shell('Removable storage lid',.616,.416,.036,.004,'Edge','C',True,.306);bevel(lid,.0007);atlas_uv(lid,(.616,.416,.306),plain=True)
lh=[boxhull((0,0,.304),(.308,.208,.002))]+[boxhull((x,0,.286),(.002,.208,.016)) for x in (-.306,.306)]+[boxhull((0,y,.286),(.304,.002,.016)) for y in (-.206,.206)]
finish(lid,'C_Lid','C',(0,0,.270),lh)

d=cubegrid('Crushed worn carton',.6,.4,.3,'Damaged','D',True);finish(d,'D_Damaged','D',hulls=[boxhull((0,0,.15),(.3,.2,.15))])
bottom=cubegrid('Stack base',.6,.4,.3,'Standard','E');top=cubegrid('Stack upper',.46,.34,.26,'Standard','E')
rt=Matrix.Translation(Vector((.018,.010,.300)))@Matrix.Rotation(math.radians(-4),4,'Z')
for v in top.data.vertices:v.co=rt@v.co
activate(bottom);top.select_set(True);bpy.ops.object.join()
finish(bottom,'E_Stack','E',hulls=[boxhull((0,0,.15),(.3,.2,.15)),boxhull((0,0,.13),(.23,.17,.13),rt)])
for group,key,mat in [('F','F_Fruit','Fruit'),('G','G_Water','Water'),('H','H_Noodles','Noodles')]:
    o=closed_handled(key,mat,group);finish(o,key,group,hulls=[boxhull((0,0,.15),(.3,.2,.15))])

def camera(name,loc,target,scale):
    data=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,data);PRE.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();data.type='ORTHO';data.ortho_scale=scale;data.lens=48;return o
hero=camera('01 Carton set overview',(4,-7,4.5),(0,0,.20),5.25)
camera('02 Open carton closeup',(-1.4,-1.0,1.20),(-.55,.60,.27),1.35)
camera('03 Storage handle closeup',(1.4,-.8,.9),(.55,.60,.19),1.10)
floor=cube('Preview floor',(0,0,-.012),(100,100,.024),'Edge','A')
for col in list(floor.users_collection):col.objects.unlink(floor)
PRE.objects.link(floor)
fm=bpy.data.materials.new('Preview charcoal floor');fm.use_nodes=True;p=fm.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.006,.007,.009,1);p.inputs['Roughness'].default_value=.86;floor.data.materials.clear();floor.data.materials.append(fm)
font=bpy.data.fonts.load('C:/Windows/Fonts/msyh.ttc')
for code,label,pose in specs:
    data=bpy.data.curves.new(label,'FONT');data.body=label;data.font=font;data.size=.052;data.align_x='CENTER';data.extrude=0
    o=bpy.data.objects.new(label,data);PRE.objects.link(o);o.location=(pose[0],pose[1]-.48,.002);o.rotation_euler=(0,0,0)
    # Ground-plane text is preview-only, no imported helper objects.
    tx=bpy.data.materials.get('Preview labels')
    if tx is None:
        tx=bpy.data.materials.new('Preview labels');tx.diffuse_color=(.7,.72,.74,1)
    data.materials.append(tx)
for name,loc,power,size in [('Key',(-3,-4,5),650,4),('Fill',(3,-1,3),330,3),('Rim',(0,3,4),500,3)]:
    data=bpy.data.lights.new(name,'AREA');o=bpy.data.objects.new(name,data);PRE.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,.2))-o.location).to_track_quat('-Z','Y').to_euler();data.energy=power;data.size=size
S.world=bpy.data.worlds.new('Carton preview environment');S.world.use_nodes=True;S.world.node_tree.nodes['Background'].inputs[0].default_value=(.18,.20,.23,1);S.world.node_tree.nodes['Background'].inputs[1].default_value=.18
S.unit_settings.system='METRIC';S.camera=hero;S.render.engine='CYCLES';S.cycles.samples=28;S.cycles.use_denoising=True
S.render.resolution_x=1800;S.render.resolution_y=1150;S.render.resolution_percentage=100;S.render.image_settings.file_format='PNG';S.view_settings.view_transform='AgX'
S.frame_start=1;S.frame_end=1;S.frame_set(1);bpy.context.view_layer.update()
budget={code:sum(p['triangles'] for p in PARTS.values() if p['variant']==code) for code,_,_ in specs}
assert all(v<=800 for v in budget.values()),budget
report={'success':True,'source_scene':S.name,'parts':PARTS,'collision_hulls':COLL,'placement_m':SOURCE_POSES,'variant_triangles':budget,
        'total_triangles':sum(budget.values()),'source_dimensions_m':[.60,.40,.30],'variant_count':8,'flaps':flaps,
        'storage_lid_pivot_m':[0,0,.270],'preview_collection':PRE.name,'front_camera':hero.name,'normal_convention':'OpenGL +Y'}
(ROOT/'model_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for w in bpy.context.window_manager.windows:
    for area in w.screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='MATERIAL';sp.overlay.show_overlays=False;sp.region_3d.view_rotation=hero.rotation_euler.to_quaternion();sp.region_3d.view_location=(0,0,.20);sp.region_3d.view_distance=5.3;sp.region_3d.view_perspective='ORTHO'
bpy.data.libraries.write(str(ROOT/'CardboardBoxSet.blend'),{S},fake_user=True,compress=True)
print('CARTONS_CREATED_BY_MCP',json.dumps({'parts':len(PARTS),'budget':budget,'total_triangles':report['total_triangles']}))
