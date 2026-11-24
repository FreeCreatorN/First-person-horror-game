"""Author the reference sofa in the connected Blender scene, with real separate parts."""
import bpy,bmesh,math,json,random
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent
S=bpy.context.scene
assert S.name=='ThreeSeatSofa' and not list(S.objects)
S.unit_settings.system='METRIC';S.unit_settings.scale_length=1
COL=bpy.data.collections.new('Three seat sofa - 15 independent parts');S.collection.children.link(COL)
PRE=bpy.data.collections.new('_PreviewOnly');S.collection.children.link(PRE)
M={};T={};G={};PARTS={};COLL={}
def linear(c):return c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
for kind in ['Fabric','Plaid','Underside']:
    name='M_Sofa_'+kind;m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF')
    p.inputs['Specular IOR Level'].default_value=.24;p.inputs['Sheen Weight'].default_value=.22;p.inputs['Sheen Roughness'].default_value=.8
    T[name]={}
    for ch,suffix,space in [('base_color','BaseColor','sRGB'),('normal','Normal','Non-Color'),('orm','ORM','Non-Color')]:
        filename=f'T_Sofa_{kind}_{suffix}.png';im=bpy.data.images.load(str(ROOT/'Textures'/filename),check_existing=True);im.colorspace_settings.name=space;im.pack()
        tx=n.new('ShaderNodeTexImage');tx.image=im;tx.extension='REPEAT';T[name][ch]=filename
        if ch=='base_color':l.new(tx.outputs['Color'],p.inputs['Base Color'])
        elif ch=='normal':
            nn=n.new('ShaderNodeNormalMap');nn.inputs['Strength'].default_value=.55;l.new(tx.outputs['Color'],nn.inputs['Color']);l.new(nn.outputs['Normal'],p.inputs['Normal'])
        else:
            sep=n.new('ShaderNodeSeparateColor');l.new(tx.outputs['Color'],sep.inputs[0]);l.new(sep.outputs['Green'],p.inputs['Roughness'])
    m.diffuse_color=(.18,.12,.08,1);M[kind]=m
def solid(key,color,rough):
    name='M_Sofa_'+key;m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*[linear(c) for c in color],1);p.inputs['Roughness'].default_value=rough
    m.diffuse_color=(*[linear(c) for c in color],1);M[key]=m;G[name]={'type':'solid','color':list(color),'roughness':rough,'metallic':0,'color_space':'srgb'}
solid('Welt',(.34,.27,.205),.82);solid('PillowWelt',(.35,.32,.275),.86);solid('Feet',(.095,.085,.07),.72)
def select(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
def mesh(name,verts,faces,material='Fabric'):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();me.materials.append(M[material]);bm=bmesh.new();bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();me.update()
    o=bpy.data.objects.new(name,me);COL.objects.link(o);return o
def uvbox(o,repeat=.45):
    me=o.data;uv=me.uv_layers.new(name='UVMap') if not me.uv_layers else me.uv_layers.active
    rng=random.Random(o.name);du,dv=rng.random()*2,rng.random()*2
    for f in me.polygons:
        a=max(range(3),key=lambda i:abs(f.normal[i]));axes=[(1,2),(0,2),(0,1)][a]
        for li in f.loop_indices:
            p=me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv=(p[axes[0]]/repeat+du,p[axes[1]]/repeat+dv)
def cubehull(center,half,rot=None):
    mat=rot or Matrix.Identity(3)
    return {'vertices_m':[list(Vector(center)+mat@Vector([a*half[0],b*half[1],c*half[2]])) for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]}
def register(o,name,role,pivot,colliders):
    o.name='SM_Sofa_'+name;o.data.name=o.name+' Mesh';o.location=pivot
    for p in o.data.polygons:p.use_smooth=True
    o.data.calc_loop_triangles();PARTS[o.name]={'object':o.name,'mesh':o.name,'role':role,'pivot_m':list(pivot),'triangles':len(o.data.loop_triangles)};COLL[o.name]=colliders
    return o
def rounded(p,h,r):
    core=Vector([max(-h[i]+r,min(h[i]-r,p[i])) for i in range(3)]);d=Vector(p)-core
    return core+d.normalized()*r,d.normalized()
def make_soft(name,size,center,counts,r,kind='seat',angles=(0,0,0),material='Fabric',seed=0):
    h=Vector(size)/2;mat=__import__('mathutils').Euler(angles).to_matrix();rng=random.Random(seed);phase=rng.random()*6.2
    def deform(p,normal):
        x,y,z=p;nx,ny,nz=normal
        xx=x/h.x;yy=y/h.y;zz=z/h.z
        if kind=='seat':
            # Broad cushion dome with a shallow, broad sitter compression.
            p.z+=max(0,nz)*(.034*(1-xx*xx)*(1-yy*yy)-.014*math.exp(-((xx-.08)**2/.25+(yy+.08)**2/.28)))
            fold=.0035*math.sin(24*xx+4*yy+phase)*math.exp(-((abs(yy)-.83)/.23)**2)*(1-xx*xx)
            fold+=.0030*math.sin(26*yy+3*xx+phase)*math.exp(-((abs(xx)-.84)/.23)**2)*(1-yy*yy)
        elif kind=='back':
            p.y-=max(0,-ny)*(.030*(1-xx*xx)*(1-zz*zz))
            p.z+=.0035*math.sin(9*xx+phase)*max(0,nz)
            fold=.0042*math.sin(24*xx+5*zz+phase)*math.exp(-((zz+.7)/.3)**2)*(1-xx*xx)
            fold+=.0030*math.sin(27*zz+3*xx+phase)*math.exp(-((abs(xx)-.8)/.25)**2)
        elif kind=='arm':
            p.x+=math.copysign(1,x)*.008*(1-yy*yy)*max(0,zz)
            p.z+=.016*(1-yy*yy)*max(0,nz)
            fold=.0035*math.sin(26*yy+4*zz+phase)*math.exp(-((zz-.45)/.3)**2)*(1-yy*yy)
            fold+=.0025*math.sin(28*zz+phase)*math.exp(-((yy+.8)/.25)**2)
        else:
            # Puffy pillow face, with pinched edge gathering.
            p.y+=math.copysign(1,y)*.012*(1-xx*xx)*(1-zz*zz)
            fold=.0025*math.sin(26*xx+phase+4*zz)*math.exp(-((abs(zz)-.85)/.23)**2)
            fold+=.002*math.sin(23*zz+phase)*math.exp(-((abs(xx)-.85)/.23)**2)
        return p+normal*fold
    def surface(p):
        p,n=rounded(p,h,r);p=deform(p,n);return mat@p,mat@n
    verts=[];faces=[];nx,ny,nz=counts;ct=(nx,ny,nz)
    # Six sampled faces sharing vertices at their edges after the mesh weld.
    for axis in range(3):
        a,b=[i for i in range(3) if i!=axis]
        for sign in [-1,1]:
            off=len(verts)
            for j in range(ct[b]+1):
                for i in range(ct[a]+1):
                    p=Vector((0,0,0));p[axis]=sign*h[axis];p[a]=-h[a]*math.cos(math.pi*i/ct[a]);p[b]=-h[b]*math.cos(math.pi*j/ct[b])
                    verts.append(tuple(surface(p)[0]))
            for j in range(ct[b]):
                for i in range(ct[a]):
                    q=off+j*(ct[a]+1)+i;faces.append((q,q+1,q+ct[a]+2,q+ct[a]+1))
    o=mesh(name,verts,faces,material);uvbox(o,.28 if material=='Plaid' else .45)
    # Embedded piping follows the exact same deformed cushion surface.
    # axis is the constant coordinate of the contour.
    axis=2 if kind=='seat' else 1
    const=(h.z-.035) if kind=='seat' else (-h.y+.027 if kind!='arm' else -h.y+.045)
    corec=max(-h[axis]+r,min(h[axis]-r,const));delta=const-corec;rr=math.sqrt(max(1e-8,r*r-delta*delta));other=[i for i in range(3) if i!=axis]
    aa,bb=other;path=[];norms=[]
    # 32 contour segments: enough for a soft welt without dense stitch geometry.
    for ca,cb,ang in [(1,1,0),(-1,1,90),(-1,-1,180),(1,-1,270)]:
        for j in range(8):
            theta=math.radians(ang+j*90/8);p=Vector((0,0,0));p[axis]=const
            p[aa]=ca*(h[aa]-r)+rr*math.cos(theta);p[bb]=cb*(h[bb]-r)+rr*math.sin(theta)
            pp,nn=surface(p);path.append(pp);norms.append(nn)
    o.data.calc_loop_triangles()
    tree=BVHTree.FromPolygons([v.co for v in o.data.vertices],[tuple(t.vertices) for t in o.data.loop_triangles],all_triangles=True)
    for i,p in enumerate(path):
        nearest,face_n,face_index,distance=tree.find_nearest(p)
        if nearest is not None:path[i]=nearest+norms[i]*.00030
    vs=[];fs=[];rad=.00165 if kind!='pillow' else .00145
    for i,p in enumerate(path):
        tangent=(path[(i+1)%len(path)]-path[i-1]).normalized();n=norms[i];side=tangent.cross(n).normalized()
        for j in range(4):
            a=math.tau*j/4;vs.append(tuple(p+rad*(n*math.cos(a)+side*math.sin(a))))
    for i in range(len(path)):
        for j in range(4):fs.append((i*4+j,i*4+(j+1)%4,((i+1)%len(path))*4+(j+1)%4,((i+1)%len(path))*4+j))
    welt=mesh(name+' attached welt',vs,fs,'PillowWelt' if kind=='pillow' else 'Welt');uvbox(welt)
    select([o,welt]);bpy.ops.object.join()
    return register(o,name,kind,center,[cubehull(center,[v*.475 for v in size],mat)])

# A single closed, upholstered L profile unites the base and rear panel.
profile=[(-.46,.075),(.47,.075),(.47,.765),(.390,.765),(.308,.305),(-.46,.305)]
verts=[(x,y,z) for x in [-1.09,1.09] for y,z in profile];n=len(profile)
faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
base=mesh('Base',verts,faces);select([base]);b=base.modifiers.new('Soft upholstered continuous edge','BEVEL');b.width=.042;b.segments=4;b.affect='EDGES';bpy.ops.object.modifier_apply(modifier=b.name)
# The low full-width plinth remains, but the hidden volume under each arm
# is removed. This keeps all15 requested components without buried solid slabs.
for side in [-1,1]:
    cx=side*1.12;hx=.205;cy=0;hy=.60;cz=.70;hz=.57
    vv=[(cx+a*hx,cy+b*hy,cz+c*hz) for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    cutter=mesh('Temporary arm clearance cutter',vv,[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    select([base]);mod=base.modifiers.new('Upholstery support clearance','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
base.data.materials.append(M['Underside'])
for f in base.data.polygons:
    if f.normal.z<-.7 and f.center.z<.13:f.material_index=1
uvbox(base)
# Keep broad base planes calm, with smooth bevel bands.
for f in base.data.polygons:f.use_smooth=len(f.vertices)==4 and f.area<.02
base=register(base,'Base','upholstered base and rear panel',(0,0,0),[cubehull((0,.005,.1025),(1.08,.45,.0275)),cubehull((0,.005,.2175),(.91,.45,.0875)),cubehull((0,.435,.52),(.91,.035,.245))])
for side in [-1,1]:
    make_soft('Arm_'+('L' if side<0 else 'R'),(.245,.95,.510),(side*1.0275,0,.380),(8,16,10),.105,'arm',seed=12+side)
for i,x in enumerate([-.605,0,.605],1):
    make_soft(f'Seat_{i:02d}',(.598,.675,.165),(x,-.1025,.3825),(14,14,4),.073,'seat',seed=40+i)
for i,x in enumerate([-.603,0,.603],1):
    make_soft(f'Back_{i:02d}',(.600,.190,.400),(x,.272,.6485),(14,4,10),.074,'back',(math.radians(-10),math.radians((i-2)*.55),math.radians((i-2)*.45)),seed=70+i)
for side in [-1,1]:
    make_soft('Pillow_'+('L' if side<0 else 'R'),(.310,.135,.310),(side*.715,-.087,.647),(8,4,8),.060,'pillow',(math.radians(-13),math.radians(side*19),math.radians(side*10)),'Plaid',seed=90+side)
for x,y,label in [(-.94,-.34,'FL'),(.94,-.34,'FR'),(-.94,.35,'BL'),(.94,.35,'BR')]:
    vs=[];fs=[];ns=12
    for radius,z in [(.034,0),(.038,.012),(.035,.080)]:
        for i in range(ns):a=math.tau*i/ns;vs.append((radius*math.cos(a),radius*math.sin(a),z))
    fs=[tuple(reversed(range(ns))),tuple(range(2*ns,3*ns))]
    for j in range(2):
        for i in range(ns):fs.append((j*ns+i,j*ns+(i+1)%ns,(j+1)*ns+(i+1)%ns,(j+1)*ns+i))
    foot=mesh('Foot_'+label,vs,fs,'Feet');uvbox(foot)
    register(foot,'Foot_'+label,'concealed low foot',(x,y,0),[cubehull((x,y,.04),(.034,.034,.04))])

# Ground contact and full model bounds are exact; tiny per-axis normalization
# preserves the designed cushion shapes while including all piping/wrinkles.
allobjs=[S.objects[k] for k in PARTS]
bpy.context.view_layer.update()
lo=Vector([min((o.matrix_world@v.co)[a] for o in allobjs for v in o.data.vertices) for a in range(3)])
hi=Vector([max((o.matrix_world@v.co)[a] for o in allobjs for v in o.data.vertices) for a in range(3)])
factors=Vector([target/(hi[a]-lo[a]) for a,target in enumerate((2.30,.95,.85))]);mid=(lo+hi)/2;offset=Vector((-mid.x,-mid.y,-lo.z))
for o in allobjs:
    name=o.name;oldpivot=o.location.copy();newpivot=Vector([(oldpivot[a]+offset[a])*factors[a] for a in range(3)])
    for v in o.data.vertices:
        globalp=v.co+oldpivot;v.co=Vector([(globalp[a]+offset[a])*factors[a]-newpivot[a] for a in range(3)])
    o.location=newpivot;PARTS[name]['pivot_m']=list(newpivot)
    for hull in COLL[name]:hull['vertices_m']=[[ (v[a]+offset[a])*factors[a] for a in range(3)] for v in hull['vertices_m']]
    o.data.update();o.data.calc_loop_triangles();PARTS[name]['triangles']=len(o.data.loop_triangles)
    # Actual geometry is closed; seam loops are intentionally embedded material shells.
    bm=bmesh.new();bm.from_mesh(o.data);assert all(e.is_manifold for e in bm.edges),name;bm.free()
for name,row in PARTS.items():row['bounds_local_m']=[[min(v.co[a] for v in S.objects[name].data.vertices) for a in range(3)],[max(v.co[a] for v in S.objects[name].data.vertices) for a in range(3)]]
total=sum(r['triangles'] for r in PARTS.values());assert total<=15000,total

def move_preview(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    PRE.objects.link(o)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.0015));ground=bpy.context.object;ground.name='Preview ground - not exported';move_preview(ground)
gm=bpy.data.materials.new('Preview charcoal floor');gm.diffuse_color=(.035,.035,.035,1);gm.use_nodes=True;gm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.035,.035,.035,1);gm.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.85;ground.data.materials.append(gm)
def camera(name,loc,target,ortho):
    d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);PRE.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.type='ORTHO';d.ortho_scale=ortho;return o
S.camera=camera('01 Sofa hero',(-3.0,-4.4,2.35),(0,0,.40),2.85)
camera('02 Sofa rear',(3,4,1.8),(0,0,.4),2.9);camera('03 Sofa front',(0,-5,1.45),(0,0,.40),2.70)
for name,loc,power,size in [('Key',(-3,-4,4),450,4),('Fill',(3,-1,2.8),250,3),('Rim',(1,3,3),500,3)]:
    d=bpy.data.lights.new('Preview '+name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(d.name,d);PRE.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,.4))-o.location).to_track_quat('-Z','Y').to_euler()
S.world=bpy.data.worlds.new('Sofa preview world');S.world.use_nodes=True;S.world.node_tree.nodes.get('Background').inputs[0].default_value=(.22,.22,.22,1);S.world.node_tree.nodes.get('Background').inputs[1].default_value=.30
S.render.engine='CYCLES';S.cycles.samples=48;S.cycles.use_denoising=True;S.render.resolution_x=1800;S.render.resolution_y=1200;S.render.resolution_percentage=100;S.render.image_settings.file_format='PNG';S.view_settings.view_transform='AgX';S.view_settings.exposure=0
for win in bpy.context.window_manager.windows:
    for area in win.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL';area.spaces.active.overlay.show_overlays=False
select([allobjs[0]])
report={'success':True,'source_scene':S.name,'parts':PARTS,'collision_hulls':COLL,'assemblies':{'BP_ThreeSeatSofa':list(PARTS)},'textures':T,'generic_materials':G,'total_triangles':total,'product_count':1,'family_count':1,'product_triangles':{'ThreeSeatSofa':total},'expected_dimensions_m':[2.30,.95,.85],'normal_convention':'OpenGL +Y','budget_target_met':total<=15000,'seam_materials':['M_Sofa_Welt','M_Sofa_PillowWelt'],'fit_notes':['Welt ring centers are BVH-fitted to the actual cushion surface; tube bases embed about1.3mm.','Cushions compressed against their upholstered supports; mounting contact may embed inside hidden soft surfaces.','Base is one closed L profile with arm clearance cutouts, no exposed wood or metal.'],'contact_expectations':[{'a':f'SM_Sofa_Seat_{i:02d}','b':'SM_Sofa_Base','max_gap_m':.008,'allow_penetration_m':.016} for i in [1,2,3]]}
(ROOT/'model_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.data.libraries.write(str(ROOT/'ThreeSeatSofa.blend'),{S},fake_user=True,compress=True)
print('SOFA_BUILT',len(PARTS),total)
