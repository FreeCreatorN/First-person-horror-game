"""Reference notebook: textured hardcovers, 16 individually skinned double-sided leaves.
All lengths in meters. One baked deterministic animation can be scrubbed in UE.
"""
import bpy, bmesh, math, json, hashlib
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
for obj in list(bpy.data.objects): bpy.data.objects.remove(obj,do_unlink=True)
s=bpy.context.scene
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
s.render.fps=30;s.frame_start=1;s.frame_end=781
(OUT/'Exports').mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def coll(name):
    c=bpy.data.collections.new(name);s.collection.children.link(c);return c
asset=coll('NOTEBOOK - skinned game asset')
studio=coll('STUDIO - preview only, never exported')
mats=[];material_report={}
def material(name,stem,roughstem=None,rough=.8):
    m=bpy.data.materials.new(name);m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Roughness'].default_value=rough;p.inputs['Emission Strength'].default_value=0
    p.inputs['Specular IOR Level'].default_value=.26
    texture=f'Textures/T_Notebook_{stem}_BaseColor.png'
    img=bpy.data.images.load(str(OUT/texture),check_existing=True)
    tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=img
    m.node_tree.links.new(tx.outputs['Color'],p.inputs['Base Color'])
    rr=f'Textures/T_Notebook_{roughstem or stem}_Roughness.png'
    rt=m.node_tree.nodes.new('ShaderNodeTexImage');rt.image=bpy.data.images.load(str(OUT/rr),check_existing=True)
    rt.image.colorspace_settings.name='Non-Color';m.node_tree.links.new(rt.outputs['Color'],p.inputs['Roughness'])
    bump=m.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.13
    bump.inputs['Distance'].default_value=.00006 if stem in ('Cloth','Ribbon') else .000025
    m.node_tree.links.new(rt.outputs['Color'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    m.diffuse_color=(.48,.34,.20,1) if stem=='Kraft' else ((.06,.085,.07,1) if stem=='Cloth' else (.75,.7,.59,1))
    material_report[name]={'base_color':[1,1,1],'roughness':rough,'texture':texture,'roughness_texture':rr,'two_sided':False,'page_parameter':'PageTexture' if 'Page' in name and name[-2:].isdigit() else None}
    mats.append(m);return len(mats)-1
KRAFT=material('M_Notebook_Kraft','Kraft');CLOTH=material('M_Notebook_Cloth','Cloth')
END=material('M_Notebook_Endpaper','Endpaper','Paper');EDGES=material('M_Notebook_PageEdges','PageEdges')
RIBBON=material('M_Notebook_Ribbon','Ribbon');LABEL=material('M_Notebook_Label','Label')
PAGES=[material(f'M_Notebook_Page{i+1:02d}','PaperFront' if i%2==0 else 'PaperBack','Paper') for i in range(32)]
parts=[];bone_heads={'root':(0,0,0),'FrontCover':(0,0,.0092),'BackCover':(0,0,.0035)}
def make_mesh(name,verts,faces,slots,uvs,weights):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    for m in mats:me.materials.append(m)
    for p,mi in zip(me.polygons,slots):p.material_index=mi;p.use_smooth=True
    uv=me.uv_layers.new(name='UVMap')
    for p,coords in zip(me.polygons,uvs):
        for li,co in zip(p.loop_indices,coords):uv.data[li].uv=co
    o=bpy.data.objects.new(name,me);asset.objects.link(o)
    for vid,ww in enumerate(weights):
        for bn,w in ww:
            vg=o.vertex_groups.get(bn) or o.vertex_groups.new(name=bn);vg.add([vid],w,'REPLACE')
    parts.append(o);return o
def slab(name,xmin,xmax,ymin,ymax,zmin,zmax,bone,topmat,bottommat,sidemat,r=.0025):
    # Rounded rectangle prism, small applied edge bevel; no stacked coplanar surfaces.
    ring=[]
    for cx,cy,a in [(xmax-r,ymax-r,0),(xmin+r,ymax-r,90),(xmin+r,ymin+r,180),(xmax-r,ymin+r,270)]:
        for j in range(7):
            th=math.radians(a+j*15);ring.append((cx+r*math.cos(th),cy+r*math.sin(th)))
    n=len(ring);v=[(x,y,z) for z in (zmin,zmax) for x,y in ring]
    f=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    mi=[bottommat,topmat]
    for i in range(n):j=(i+1)%n;f.append((i,j,n+j,n+i));mi.append(sidemat)
    uv=[]
    for face in f:
        uv.append([((v[i][0]-xmin)/(xmax-xmin),(v[i][1]-ymin)/(ymax-ymin)) for i in face])
    o=make_mesh(name,v,f,mi,uv,[[(bone,1)]]*len(v))
    bpy.context.view_layer.objects.active=o;o.select_set(True)
    bevel=o.modifiers.new('Soft worn board edges','BEVEL');bevel.width=min(.00035,(zmax-zmin)*.25);bevel.segments=3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    o.select_set(False)
    return o
front=slab('Front board',-.004,.150,-.111,.111,.0092,.0117,'FrontCover',KRAFT,END,KRAFT)
back=slab('Back board',-.004,.150,-.111,.111,.001,.0035,'BackCover',END,KRAFT,KRAFT)
# Split cover faces exactly at the cloth hinge boundary, preserving the exterior surface.
for o in (front,back):
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-8,plane_co=(.0195,0,0),plane_no=(1,0,0),clear_inner=False,clear_outer=False)
    for f in bm.faces:
        if f.calc_center_median().x<.0195:f.material_index=CLOTH
    bm.to_mesh(o.data);bm.free();o.data.update()
label=slab('Glued hand-written label',.045,.128,.024,.065,.011705,.011775,'FrontCover',LABEL,KRAFT,LABEL,r=.0010)

PAGE_W=.142;PAGE_H=.210;N=40;NY=12;BONE_N=9;SHEETS=16;THICK=.00028;SPACING=.00032
for page in range(SHEETS):
    z=.0089-page*SPACING
    names=[f'Page_{page+1:02d}_{j:02d}' for j in range(BONE_N)]
    for j,bn in enumerate(names):bone_heads[bn]=(.0015+PAGE_W*j/(BONE_N-1),0,z)
    vs=[];ws=[]
    for side in (1,-1):
        for i in range(N+1):
            u=i/N
            for k in range(NY+1):
                y=(k/NY-.5)*PAGE_H
                corner=max(0,abs(y)-(PAGE_H/2-.0025))
                maxx=PAGE_W-.0025+math.sqrt(max(0,.0025**2-corner**2)) if corner>0 else PAGE_W
                x=.0015+maxx*u
                vs.append((x,y,z+side*THICK/2))
                q=(x-.0015)/PAGE_W*(BONE_N-1);a=min(BONE_N-2,int(q));t=q-a
                ws.append([(names[a],1-t),(names[a+1],t)] if t>1e-7 else [(names[a],1)])
    row=NY+1;layer=(N+1)*row;fs=[];mis=[];uv=[]
    def face(ids,slot,backside=False,edge=False):
        fs.append(tuple(ids));mis.append(slot)
        if edge:uv.append([(q/(len(ids)-1),0 if q<2 else 1) for q in range(len(ids))])
        else:uv.append([((1-(vs[t][0]-.0015)/PAGE_W) if backside else (vs[t][0]-.0015)/PAGE_W,vs[t][1]/PAGE_H+.5) for t in ids])
    for i in range(N):
        for k in range(NY):
            a=i*row+k;b=(i+1)*row+k
            face((a,b,b+1,a+1),PAGES[page*2]);face((layer+a+1,layer+b+1,layer+b,layer+a),PAGES[page*2+1],True)
    perimeter=list(range(row))+[i*row+NY for i in range(1,N+1)]+[N*row+k for k in range(NY-1,-1,-1)]+[i*row for i in range(N-1,0,-1)]
    for a,b in zip(perimeter,perimeter[1:]+perimeter[:1]):face((a,layer+a,layer+b,b),EDGES,edge=True)
    make_mesh(f'Leaf {page+1:02d} - independent double sided',vs,fs,mis,uv,ws)
# Flexible fabric between the two boards. Nine strips collapse naturally into the open gutter.
spine_nodes=[]
for j in range(9):
    t=j/8;x=-.004-.0027*math.sin(math.pi*t);z=.0035+(.0092-.0035)*t
    bone_heads[f'Spine_{j:02d}']=(x,0,z);spine_nodes.append((x,z))
vs=[];ws=[]
for side in (-1,1):
    for j,(x,z) in enumerate(spine_nodes):
        for y in (-.1105,.1105):vs.append((x+side*.00018,y,z));ws.append([(f'Spine_{j:02d}',1)])
fs=[];uv=[]
for side in range(2):
    for j in range(8):
        a=side*18+j*2;ids=(a,a+2,a+3,a+1) if side else (a+1,a+3,a+2,a)
        fs.append(ids);uv.append([(j/8,0),((j+1)/8,0),((j+1)/8,1),(j/8,1)])
for ids in [(0,1,19,18),(16,34,35,17)]:fs.append(ids);uv.append([(0,0),(1,0),(1,1),(0,1)])
for yidx in (0,1):
    for j in range(8):a=j*2+yidx;fs.append((a,a+18,a+20,a+2));uv.append([(0,0),(1,0),(1,1),(0,1)])
make_mesh('Flexible cloth spine',vs,fs,[CLOTH]*len(fs),uv,ws)
# Sewn-in red ribbon: a thin closed ribbon with a slightly curved, V-cut tail.
vs=[];ws=[];RN=30
for side in (-1,1):
    for j in range(RN+1):
        t=j/RN;y=.080-.216*t
        for k in (0,1):
            x=.051+(k-.5)*.007+.0012*math.sin(t*4)
            z=.00366-.0022*max(0,(t-.86)/.14)**1.25+.00004*math.sin(t*8)
            yy=y+(.002 if j==RN and k==0 else 0)
            vs.append((x,yy,z+side*.00008));ws.append([('BackCover',1)])
fs=[];uv=[];L=2*(RN+1)
for j in range(RN):
    a=j*2
    fs.extend([(a,a+1,a+3,a+2),(L+a+2,L+a+3,L+a+1,L+a)])
    uv.extend([[(0,j/RN),(1,j/RN),(1,(j+1)/RN),(0,(j+1)/RN)]]*2)
    for k in (0,1):a=j*2+k;fs.append((a,a+2,a+2+L,a+L));uv.append([(0,0),(1,0),(1,1),(0,1)])
for a in (0,2*RN):fs.append((a,a+L,a+L+1,a+1));uv.append([(0,0),(1,0),(1,1),(0,1)])
make_mesh('Woven red bookmark',vs,fs,[RIBBON]*len(fs),uv,ws)
# Join the render mesh without losing the individual weights/material slots.
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();mesh=bpy.context.object;mesh.name='SK_Notebook'
# Remove duplicated slots generated by joining but retain the explicit, documented order.
old=list(mesh.data.materials);indices=[mats.index(old[p.material_index]) for p in mesh.data.polygons]
mesh.data.materials.clear()
for m in mats:mesh.data.materials.append(m)
for p,mi in zip(mesh.data.polygons,indices):p.material_index=mi
bm=bmesh.new();bm.from_mesh(mesh.data)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bm.to_mesh(mesh.data);bm.free();mesh.data.update()
tri=mesh.modifiers.new('Explicit game triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
arm=bpy.data.armatures.new('Notebook skeleton');rig=bpy.data.objects.new('Armature',arm);asset.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
for bn,head in bone_heads.items():
    b=arm.edit_bones.new(bn);b.head=head;b.tail=(head[0],head[1]+.016,head[2]);b.use_deform=True
    if bn!='root':b.parent=arm.edit_bones['root']
bpy.ops.object.mode_set(mode='OBJECT')
mod=mesh.modifiers.new('Continuous paper skinning','ARMATURE');mod.object=rig;mesh.parent=rig
rig.show_in_front=True
for pb in rig.pose.bones:pb.rotation_mode='XYZ'
def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
def prog(frame,a,b):return smooth((frame-a)/(b-a))
def pose(frame,key=False):
    op=prog(frame,1,49);cl=prog(frame,721,769)
    for bn,p,ang in [('FrontCover',op,-math.pi*op),('BackCover',cl,-math.pi*cl)]:
        pb=rig.pose.bones[bn];pb.location=(0,0,(-.0057 if bn=='FrontCover' else .0057)*p);pb.rotation_euler=(0,ang,0)
    for page in range(SHEETS):
        p=prog(frame,71+40*page,99+40*page)
        # Arc length integration keeps a pliable sheet, rather than rotating a rigid plane.
        zrest=.0089-page*SPACING;ztarget=.00395+page*SPACING
        angle=-math.pi*p;curl=.58*math.sin(math.pi*p)
        xx=.0015*math.cos(angle);zz=-.0015*math.sin(angle)
        nodes=[]
        for j in range(BONE_N):
            u=j/(BONE_N-1)
            if j:
                for sub in range(12):
                    q=((j-1)+(sub+.5)/12)/(BONE_N-1)
                    th=angle+curl*math.sin(math.pi*q)
                    ds=PAGE_W/(BONE_N-1)/12;xx+=ds*math.cos(th);zz-=ds*math.sin(th)
            nodes.append((xx,zz,angle+curl*math.sin(math.pi*u)))
        for j,(x,z,th) in enumerate(nodes):
            bn=f'Page_{page+1:02d}_{j:02d}';pb=rig.pose.bones[bn];head=Vector(bone_heads[bn])
            base=zrest*(1-p)+ztarget*p
            pb.location=(x-head.x,0,z+base-head.z);pb.rotation_euler=(0,th,0)
    for j,(x,z) in enumerate(spine_nodes):
        t=j/8;flatx=-.0055+.011*t;flatz=.00175+.0005*math.sin(math.pi*t)
        targetx=x*(1-op)+flatx*op;targetz=z*(1-op)+flatz*op
        endx=-x;endz=.0092-.0057*t
        targetx=targetx*(1-cl)+endx*cl;targetz=targetz*(1-cl)+endz*cl
        pb=rig.pose.bones[f'Spine_{j:02d}'];pb.location=(targetx-x,0,targetz-z);pb.rotation_euler=(0,-math.pi/2*(op+cl),0)
    if key:
        for pb in rig.pose.bones:
            pb.keyframe_insert(data_path='location',frame=frame,group=pb.name)
            pb.keyframe_insert(data_path='rotation_euler',frame=frame,group=pb.name)
print('NOTEBOOK_GEOMETRY_READY',flush=True)
frames=sorted(set(range(1,782,2))|{49,60,71,99,710,721,769,781}|{71+40*i for i in range(16)}|{99+40*i for i in range(16)}|{110+40*i for i in range(16)})
for frame in frames:pose(frame,True)
action=rig.animation_data.action;action.name='A_Notebook_FullCycle'
for f in action.layers[0].strips[0].channelbags[0].fcurves:
    for key in f.keyframe_points:key.interpolation='LINEAR'
markers={'Closed':{'frame':1,'bones':['FrontCover','BackCover']},'Open':{'frame':60,'bones':['FrontCover']},'MidTurn':{'frame':85,'bones':['Page_01_04']},'LastPage':{'frame':710,'bones':['Page_16_04']},'ClosedEnd':{'frame':781,'bones':['BackCover']}}
page_stops=[{'spread':0,'frame':60,'time_seconds':59/30,'left_page':0,'right_page':1}]
for i in range(16):
    frame=110+40*i;markers[f'Spread_{i+1:02d}']={'frame':frame,'bones':[f'Page_{i+1:02d}_04']}
    page_stops.append({'spread':i+1,'frame':frame,'time_seconds':(frame-1)/30,'left_page':2*i+2,'right_page':2*i+3 if i<15 else 0})
for name,item in markers.items():s.timeline_markers.new(name,frame=item['frame'])
(OUT/'page_stops.json').write_text(json.dumps({'fps':30,'page_faces':32,'leaves':16,'stops':page_stops,'animation':'A_Notebook_FullCycle','closed_seconds':0,'closed_end_seconds':26},indent=2),encoding='utf-8')
# Closed, rest-space geometry report and genuine topology checks.
s.frame_set(1);pose(1);bpy.context.view_layer.update()
mesh.data.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(mesh.data)
nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free()
points=[v.co for v in mesh.data.vertices]
report={'asset':'Notebook','triangles':len(mesh.data.loop_triangles),'vertices':len(mesh.data.vertices),'nonmanifold_edges':nonmanifold,'bones':list(bone_heads),'material_slots':[m.name for m in mats],'materials':material_report,'bounds_min_m':[min(v[i] for v in points) for i in range(3)],'bounds_max_m':[max(v[i] for v in points) for i in range(3)],'fps':30,'frame_start':1,'frame_end':781,'markers':markers,'leaves':16,'printable_faces':32,'max_vertex_influences':max(len(v.groups) for v in mesh.data.vertices),'source_axis':'+Y page top, +Z cover front, spine along Y'}
assert nonmanifold==0,nonmanifold
assert report['max_vertex_influences']<=2
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
fbx=dict(use_selection=True,object_types={'ARMATURE','MESH'},global_scale=1,apply_unit_scale=True,axis_forward='-Z',axis_up='Y',add_leaf_bones=False,use_armature_deform_only=True,armature_nodetype='NULL',mesh_smooth_type='FACE',use_mesh_modifiers=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,path_mode='STRIP')
saved_action=rig.animation_data.action;rig.animation_data.action=None;arm.pose_position='REST'
bpy.ops.export_scene.fbx(filepath=str(OUT/'Exports'/'SK_Notebook.fbx'),bake_anim=False,**fbx)
arm.pose_position='POSE';rig.animation_data.action=saved_action
bpy.ops.export_scene.fbx(filepath=str(OUT/'Exports'/'A_Notebook_FullCycle.fbx'),bake_anim=True,bake_anim_step=1,bake_anim_simplify_factor=0,**fbx)
clips=[{'name':'A_Notebook_Open','frame_start':1,'frame_end':49}]+[{'name':f'A_Notebook_Turn{i+1:02d}','frame_start':71+40*i,'frame_end':99+40*i} for i in range(16)]+[{'name':'A_Notebook_CloseLast','frame_start':721,'frame_end':769}]
for clip in clips:
    s.frame_start=clip['frame_start'];s.frame_end=clip['frame_end']
    clip['file']='Exports/'+clip['name']+'.fbx';clip['seconds']=(s.frame_end-s.frame_start)/30
    bpy.ops.export_scene.fbx(filepath=str(OUT/clip['file']),bake_anim=True,bake_anim_step=1,bake_anim_simplify_factor=0,**fbx)
s.frame_start=1;s.frame_end=781;report['clips']=clips
print('NOTEBOOK_FBX_READY',flush=True)
# Lighting exists only in the source preview collection, exports contain only the skinned asset.
groundmat=bpy.data.materials.new('Studio ground');groundmat.diffuse_color=(.052,.043,.032,1);groundmat.use_nodes=True
pp=next(n for n in groundmat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');pp.inputs['Base Color'].default_value=(.052,.043,.032,1);pp.inputs['Roughness'].default_value=.88
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.0005));ground=bpy.context.object;ground.name='Studio ground';ground.data.materials.append(groundmat)
for c in list(ground.users_collection):c.objects.unlink(ground)
studio.objects.link(ground)
def area(name,loc,power,size,target):
    d=bpy.data.lights.new(name,'AREA');o=bpy.data.objects.new(name,d);studio.objects.link(o);o.location=loc;d.energy=power;d.shape='DISK';d.size=size;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Studio Key',(-.15,-.18,.43),2.8,.34,(.05,0,0));area('Studio Fill',(.28,.12,.27),1.3,.3,(.05,0,0));area('Studio Edge',(-.12,.26,.30),2.3,.26,(0,0,0))
camdata=bpy.data.cameras.new('Preview Camera');camera=bpy.data.objects.new('Preview Camera',camdata);studio.objects.link(camera);s.camera=camera;camdata.type='ORTHO';camdata.clip_start=.0001;camdata.clip_end=300
s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True
s.render.resolution_x=1500;s.render.resolution_y=1200;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.world.color=(.22,.22,.22)
s.view_settings.view_transform='AgX'
def render(name,frame,pos,target,scale):
    s.frame_set(frame);pose(frame);bpy.context.view_layer.update();camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camdata.ortho_scale=scale
    s.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
render('Notebook_Closed.png',1,(.31,-.34,.42),(.073,-.004,.005),.315)
render('Notebook_Open.png',350,(.08,-.32,.53),(0,0,.009),.395)
render('Notebook_Turning.png',85,(.08,-.32,.43),(0,0,.045),.395)
render('Notebook_LastPage.png',710,(.08,-.32,.53),(0,0,.009),.395)
s.frame_set(1);pose(1);camera.location=(.31,-.34,.42);camera.rotation_euler=(Vector((.073,0,.005))-camera.location).to_track_quat('-Z','Y').to_euler();camdata.ortho_scale=.315
# Save a usable opening view. The animation remains fully editable in the timeline.
for window in bpy.context.window_manager.windows:
    for a in window.screen.areas:
        if a.type=='VIEW_3D':
            a.spaces.active.region_3d.view_distance=.40;a.spaces.active.region_3d.view_location=(.075,0,.005)
            a.spaces.active.shading.type='MATERIAL';a.spaces.active.overlay.show_overlays=False
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);bpy.context.view_layer.objects.active=mesh
for img in bpy.data.images:
    if img.source=='FILE':img.filepath=bpy.path.relpath(img.filepath,start=str(OUT))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Notebook.blend'))
report['files']={str(p.relative_to(OUT)):sha(p) for p in [OUT/'Notebook.blend',OUT/'Exports'/'SK_Notebook.fbx',OUT/'Exports'/'A_Notebook_FullCycle.fbx',OUT/'page_stops.json']}
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('NOTEBOOK_BUILD_VERIFIED',report['triangles'],len(report['bones']),flush=True)
