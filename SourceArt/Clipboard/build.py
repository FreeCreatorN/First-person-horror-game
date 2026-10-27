"""A4 hardboard clipboard, functional hinge construction and independent letter."""
import bpy,bmesh,math,json,random
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
OUT=Path(__file__).resolve().parent
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
export_col=bpy.data.collections.new('UE meshes - canonical origins');s.collection.children.link(export_col)
source_col=bpy.data.collections.new('SOURCE - individual components');s.collection.children.link(source_col)
display_col=bpy.data.collections.new('Clipboard - display assembly');s.collection.children.link(display_col)
groups={'Board':[],'Clip':[],'Paper':[]};colliders={k:[] for k in groups}

def principled(name,color,rough=.5,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    return m,p

def textured(name,color,rough,metal=0,texture='fiber'):
    m,p=principled(name,color,rough,metal);ns=m.node_tree.nodes;ls=m.node_tree.links
    tc=ns.new('ShaderNodeTexCoord');scale=ns.new('ShaderNodeVectorMath');scale.operation='MULTIPLY'
    scale.inputs[1].default_value=(1,24,5) if texture=='metal' else (3,1,4)
    ls.new(tc.outputs['Object'],scale.inputs[0]);noise=ns.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=270 if texture=='metal' else 2400
    noise.inputs['Detail'].default_value=2;ls.new(scale.outputs[0],noise.inputs['Vector'])
    ramp=ns.new('ShaderNodeValToRGB');variation=.09 if texture=='metal' else .22
    ramp.color_ramp.elements[0].position=.15;ramp.color_ramp.elements[0].color=(*(c*(1-variation) for c in color),1)
    ramp.color_ramp.elements[1].position=.85;ramp.color_ramp.elements[1].color=(*(c*(1+variation) for c in color),1)
    ls.new(noise.outputs['Fac'],ramp.inputs[0]);ls.new(ramp.outputs[0],p.inputs['Base Color'])
    bump=ns.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.12;bump.inputs['Distance'].default_value=.000009 if metal else .000018
    ls.new(noise.outputs['Fac'],bump.inputs['Height']);ls.new(bump.outputs[0],p.inputs['Normal'])
    rr=ns.new('ShaderNodeMapRange');rr.inputs['To Min'].default_value=rough-.04;rr.inputs['To Max'].default_value=rough+.04
    ls.new(noise.outputs['Fac'],rr.inputs['Value']);ls.new(rr.outputs[0],p.inputs['Roughness'])
    return m

front=textured('M_Clipboard_HardboardFront',(.18,.083,.028),.55)
edge=textured('M_Clipboard_HardboardEdge',(.24,.129,.053),.76)
back=textured('M_Clipboard_HardboardBack',(.125,.057,.022),.8)
metal=textured('M_Clipboard_Nickel',(.48,.51,.55),.31,1,'metal')
dark=textured('M_Clipboard_Steel',(.12,.14,.16),.33,1,'metal')
rubber,_=principled('M_Clipboard_PressureStrip',(.018,.020,.021),.77)
paper_mat=textured('M_Clipboard_WhitePaper',(.86,.85,.82),.83)
exec(compile((OUT/'paper_style.py').read_text(encoding='utf-8'),str(OUT/'paper_style.py'),'exec'))
apply_ruled_paper(paper_mat)

def bevel(o,width=.00035,segments=3):
    mod=o.modifiers.new('Manufactured edge radius','BEVEL');mod.width=width;mod.segments=segments;mod.harden_normals=True
    o.modifiers.new('Weighted face normals','WEIGHTED_NORMAL')
    for p in o.data.polygons:p.use_smooth=True

def mesh_obj(name,verts,faces,mat,group):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);me.materials.append(mat);groups[group].append(o);return o

def rr(w,h,r,steps=10):
    pts=[]
    for cx,cy,deg in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
        for j in range(steps+1):
            a=math.radians(deg+90*j/steps);pts.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return pts

def prism(name,outline,zlo,zhi,mat,group,offset=(0,0),radius=.0002):
    n=len(outline);verts=[(x+offset[0],y+offset[1],z) for z in (zlo,zhi) for x,y in outline]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    obj=mesh_obj(name,verts,faces,mat,group)
    if radius:bevel(obj,radius)
    return obj

def box(name,loc,size,mat,group,radius=.0003):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat);groups[group].append(o)
    if radius:bevel(o,radius)
    return o

def cylinder(name,loc,radius,depth,mat,group,axis='Z',verts=32):
    rot={'X':(0,math.pi/2,0),'Y':(math.pi/2,0,0),'Z':(0,0,0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=radius,depth=depth,location=loc,rotation=rot)
    o=bpy.context.object;o.name=name;o.data.materials.append(mat);groups[group].append(o);bevel(o,.00016,2);return o

def boolean_hole(obj,center,radius,depth=.03):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=radius,depth=depth,location=center)
    cutter=bpy.context.object;bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('True hanging aperture','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)

board=prism('Rounded glazed hardboard',rr(.230,.338,.008),0,.0033,front,'Board',radius=.00032)
board.data.materials.append(edge);board.data.materials.append(back)
for p in board.data.polygons:p.material_index=0 if p.normal.z>.5 else (2 if p.normal.z<-.5 else 1)
mount=prism('Fixed nickel mounting plate',rr(.106,.035,.004),.0033,.00435,metal,'Board',offset=(0,.1465),radius=.00030)
# Rivets pass into the board; rear retainers are flush against the underside.
for x in (-.041,.041):
    cylinder('Rivet shank',(x,.157,.0017),.0017,.0048,dark,'Board')
    head=cylinder('Domed rivet head',(x,.157,.0050),.0036,.0015,metal,'Board')
    cylinder('Rear rivet washer',(x,.157,-.00035),.0039,.0007,metal,'Board')
for x in (-.049,.049):
    support=box('Fixed hinge pedestal',(x,.148,.0073),(.006,.011,.0062),metal,'Board',.0011)
pin=cylinder('Continuous hinge pin',(0,.148,.0110),.00155,.111,metal,'Board',axis='X')
for x in (-.056,.056):cylinder('Hinge pin cap',(x,.148,.0110),.0021,.0018,metal,'Board',axis='X')

# Constant-thickness spring sheet. Its narrow rear handle has a real aperture.
profile=[(.1205,.00547,.050),(.122,.00585,.050),(.127,.0082,.050),(.134,.0127,.049),(.142,.0155,.046),(.149,.0162,.042),(.155,.0182,.036),(.166,.0230,.030),(.181,.0250,.026),(.186,.0248,.022)]
n=len(profile);verts=[]
for dz in (0,-.00075):
    for y,z,w in profile:verts.extend([(-w,y,z+dz),(w,y,z+dz)])
faces=[]
for i in range(n-1):
    a=2*i;b=2*(i+1);faces.extend([(a,a+1,b+1,b),(a+2*n,b+2*n,b+1+2*n,a+1+2*n),(a,b,b+2*n,a+2*n),(a+1,a+1+2*n,b+1+2*n,b+1)])
faces.extend([(0,2*n,2*n+1,1),(2*n-2,2*n-1,4*n-1,4*n-2)])
jaw=mesh_obj('Bent spring-steel jaw and pressure lever',verts,faces,metal,'Clip')
boolean_hole(jaw,(0,.176,.0245),.0048,.015);bevel(jaw,.00028,3)
lip=box('Paper pressure edge',(0,.1212,.00468),(.099,.0018,.00015),rubber,'Clip',radius=.000055)

def tube(name,x0,x1,y,z,ro,ri,mat,group):
    steps=40;vs=[]
    for x in (x0,x1):
        for r in (ro,ri):
            for i in range(steps):
                a=2*math.pi*i/steps;vs.append((x,y+math.cos(a)*r,z+math.sin(a)*r))
    fs=[]
    for i in range(steps):
        j=(i+1)%steps
        fs.extend([(i,j,2*steps+j,2*steps+i),(steps+i,3*steps+i,3*steps+j,steps+j),
            (i,steps+i,steps+j,j),(2*steps+i,2*steps+j,3*steps+j,3*steps+i)])
    o=mesh_obj(name,vs,fs,mat,group);bevel(o,.00008,2);return o

for x0,x1 in [(-.044,-.025),(-.022,-.003),(.003,.022),(.025,.044)]:
    tube('Rolled hinge knuckle',x0,x1,.148,.011,.00345,.00180,metal,'Clip')
    box('Hinge knuckle to moving jaw',((x0+x1)/2,.148,.0140),(x1-x0,.0030,.0032),metal,'Clip',.00025)

# Two compact torsion springs, with both legs terminating inside their supports.
def curve_tube(name,points,radius,mat,group):
    vectors=[Vector(p) for p in points];segments=12;vs=[]
    for i,p in enumerate(vectors):
        tangent=(vectors[min(i+1,len(vectors)-1)]-vectors[max(0,i-1)]).normalized()
        reference=Vector((1,0,0)) if abs(tangent.x)<.95 else Vector((0,1,0))
        u=tangent.cross(reference).normalized();v=tangent.cross(u).normalized()
        for j in range(segments):
            a=math.tau*j/segments;vs.append(tuple(p+radius*(u*math.cos(a)+v*math.sin(a))))
    fs=[]
    for i in range(len(vectors)-1):
        for j in range(segments):
            a=i*segments+j;b=i*segments+(j+1)%segments;fs.append((a,b,b+segments,a+segments))
    fs.extend([tuple(reversed(range(segments))),tuple(range((len(vectors)-1)*segments,len(vectors)*segments))])
    o=mesh_obj(name,vs,fs,mat,group)
    for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
    return o
for cx in (-.0235,.0235):
    pts=[]
    for i in range(121):
        t=i/120;a=t*math.tau*3;pts.append((cx-.0012+.0024*t,.148+.0023*math.cos(a),.011+.0023*math.sin(a)))
    pts=[(cx-.0012,.153,.0042)]+pts+[(cx+.0012,.145,.0157)]
    curve_tube('Spring steel torsion coil',pts,.00032,dark,'Board')

def smooth(x):x=max(0,min(1,x));return x*x*(3-2*x)
def paper_z(x,y):
    clamp_rise=.00112*smooth((y-.108)/.010)
    curl=.0017*smooth((x-.085)/.020)*smooth((-.135-y)/.021)
    return .00348+clamp_rise+curl
nx=18;ny=26;points=[(-.105+.210*i/nx,-.156+.297*j/ny) for j in range(ny+1) for i in range(nx+1)]
vs=[(x,y,paper_z(x,y)+dz) for dz in (0,-.00013) for x,y in points];count=len(points);top=[]
for j in range(ny):
    for i in range(nx):
        a=j*(nx+1)+i;top.append((a,a+1,a+nx+2,a+nx+1))
boundary=list(range(nx+1))+[j*(nx+1)+nx for j in range(1,ny+1)]+[ny*(nx+1)+i for i in range(nx-1,-1,-1)]+[j*(nx+1) for j in range(ny-1,0,-1)]
fs=top+[tuple(v+count for v in reversed(f)) for f in top]+[(a,b,b+count,a+count) for a,b in zip(boundary,boundary[1:]+boundary[:1])]
paper=mesh_obj('A4 blank paper with natural lower curl',vs,fs,paper_mat,'Paper');bevel(paper,.000025,2)

def convex(name,points):
    bm=bmesh.new()
    for p in points:bm.verts.new(p)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));me=bpy.data.meshes.new(name);bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return o
def collision_box(key,loc,size):
    name='UCX_SM_Clipboard_'+key+'_%02d'%len(colliders[key])
    o=convex(name,[(loc[0]+x*size[0]/2,loc[1]+y*size[1]/2,loc[2]+z*size[2]/2) for x in (-1,1) for y in (-1,1) for z in (-1,1)]);colliders[key].append(o)

collision_box('Board',(0,0,.0013),(.230,.338,.0040))
collision_box('Board',(0,.1465,.003825),(.106,.035,.00105))
collision_box('Board',(0,.148,.011),(.113,.005,.005))
for x in (-.049,.049):collision_box('Board',(x,.148,.007),(.006,.011,.007))
for i in range(len(profile)-1):
    points=[]
    for y,z,w in profile[i:i+2]:
        for x in (-w,w):points.extend([(x,y,z+.00012),(x,y,z-.00075)])
    name='UCX_SM_Clipboard_Clip_%02d'%len(colliders['Clip']);colliders['Clip'].append(convex(name,points))
collision_box('Clip',(0,.148,.011),(.091,.007,.007))
collision_box('Clip',(0,.1212,.00468),(.099,.0018,.00015))
# Thin local hulls follow the paper instead of filling its raised top and curl.
paper_regions=[(-.105,.085,-.156,.108),(.085,.105,-.135,.108),(-.105,.105,.118,.141)]
paper_regions += [(-.105,.105,.108+j*.005,.108+(j+1)*.005) for j in range(2)]
paper_regions += [(.085+i*.010,.085+(i+1)*.010,-.156+j*.007,-.156+(j+1)*.007) for i in range(2) for j in range(3)]
for x0,x1,y0,y1 in paper_regions:
    ps=[]
    for ix in range(3):
        for iy in range(3):
            x=x0+(x1-x0)*ix/2;y=y0+(y1-y0)*iy/2;z=paper_z(x,y);ps.extend([(x,y,z),(x,y,z-.00013)])
    name='UCX_SM_Clipboard_Paper_%02d'%len(colliders['Paper']);colliders['Paper'].append(convex(name,ps))

assets={};parts={}
for key,objects in groups.items():
    for o in objects:
        clone=o.copy();clone.data=o.data.copy();source_col.objects.link(clone)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join();o=bpy.context.object
    for index in reversed(range(len(o.data.materials))):
        if o.data.materials[index] is None:
            for p in o.data.polygons:
                if p.material_index==index:p.material_index=0
            o.data.materials.pop(index=index)
    name='SM_Clipboard_'+key;o.name=name
    s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for layer in list(o.data.uv_layers):o.data.uv_layers.remove(layer)
    o.data.uv_layers.new(name='UVMap');bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(65),island_margin=.006);bpy.ops.object.mode_set(mode='OBJECT')
    tr=o.modifiers.new('Game-ready triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tr.name)
    bm=bmesh.new();bm.from_mesh(o.data);nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free();assert nonmanifold==0,(name,nonmanifold)
    for c in colliders[key]:c.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
    parts[name]={'filename':name+'.fbx','dimensions_cm':[d*100 for d in o.dimensions],'triangles':len(o.data.polygons),'collision_hulls':len(colliders[key]),'uv_channels':1,
        'non_manifold_edges':nonmanifold,'material_slots':{m.name:'M_Clipboard'+key for m in o.data.materials}}
    for c in colliders[key]:bpy.data.objects.remove(c,do_unlink=True)
    for c in list(o.users_collection):c.objects.unlink(o)
    export_col.objects.link(o);assets[key]=o
    view=o.copy();view.data=o.data;view.name='VIEW_Clipboard_'+key;display_col.objects.link(view)

export_col.hide_viewport=True;export_col.hide_render=True;source_col.hide_viewport=True;source_col.hide_render=True
studio=bpy.data.collections.new('Preview studio - excluded from exports');s.collection.children.link(studio)
def studio_obj(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor,_=principled('Preview charcoal',(.065,.074,.085),.82)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));o=bpy.context.object;o.name='Preview ground';o.data.materials.append(floor);studio_obj(o)
target=Vector((0,.015,.006));bpy.ops.object.camera_add(location=(.30,-.48,.64));cam=bpy.context.object;cam.name='Camera_Clipboard';cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=.47;cam.data.clip_start=.0001;s.camera=cam;studio_obj(cam)
for name,pos,power,size,col in [('Key',(-.26,-.14,.55),14,.38,(1,.94,.86)),('Fill',(.32,.05,.40),6,.31,(.88,.94,1)),('Rim',(-.1,.4,.5),12,.24,(1,.97,.91))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=col;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_obj(o)
s.world.use_nodes=True;next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.12,.14,.17,1)
s.render.engine='CYCLES';s.cycles.samples=40;s.cycles.use_denoising=True;s.render.resolution_x=1500;s.render.resolution_y=1600;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX';s.view_settings.exposure=-.3
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'Clipboard_Preview.png');studio.hide_viewport=True
report={'parts':parts,'texture_sets':{k:{'prefix':'T_Clipboard'+k,**{ch:'Textures/T_Clipboard'+k+'_'+ch+'.png' for ch in ('BaseColor','Roughness','Normal','Metallic')}} for k in groups},
    'materials':{'M_Clipboard'+k:{'texture_set':k} for k in groups},'assembly':{'all_parts_share_origin':True,'relative_position_cm':[0,0,0],'hinge_pivot_blender_m':[0,.148,.011],'hinge_axis':'X','clip_is_independent':True,'paper_size_mm':[210,297]},
    'reference_url':'https://rapesco.com/product/business-pack-pack-of-4-heavy-duty-hardboard-clipboard-a4-brown/','exported_lights':0,'exported_cameras':0}
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.object.select_all(action='DESELECT');bpy.context.view_layer.objects.active=bpy.data.objects['VIEW_Clipboard_Board']
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Clipboard.blend'))
print(json.dumps(report,indent=2))
