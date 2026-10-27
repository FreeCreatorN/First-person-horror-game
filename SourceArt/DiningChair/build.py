"""A high-back wooden dining chair matching LargeDiningTable, with no cushion."""
import bpy,bmesh,math,json,random
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\DiningChair');rng=random.Random(628)
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
base_parts=[];collision_objects=[];joint_checks=[]
exec(compile((OUT/'shader_helpers.py').read_text(encoding='utf-8'),'shader_helpers.py','exec'))
wood_mat=wood('M_Chair_Wood');end_mat=wood('M_Chair_Endgrain',True)
for m in (wood_mat,end_mat):
    ns=m.node_tree.nodes;ls=m.node_tree.links;p=next(n for n in ns if n.type=='BSDF_PRINCIPLED')
    old=p.inputs['Base Color'].links[0].from_socket
    tint=ns.new('ShaderNodeVectorMath');tint.operation='MULTIPLY';ls.new(old,tint.inputs[0])
    tint.inputs[1].default_value=(.98,.83,.69);ls.new(tint.outputs[0],p.inputs['Base Color'])
    m.diffuse_color=(.20,.108,.049,1)
iron=bpy.data.materials.new('M_Chair_Dark');iron.use_nodes=True;iron.diffuse_color=(.035,.03,.022,1)
p=next(n for n in iron.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
p.inputs['Base Color'].default_value=(.035,.030,.022,1);p.inputs['Metallic'].default_value=.45;p.inputs['Roughness'].default_value=.73
exec(compile((OUT/'mesh_helpers.py').read_text(encoding='utf-8'),'mesh_helpers.py','exec'))

def collider_from_points(points):
    bm=bmesh.new()
    for p in points:bm.verts.new(p)
    bm.verts.ensure_lookup_table()
    result=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    removable=[g for g in result.get('geom_interior',[]) if isinstance(g,bmesh.types.BMVert)]
    if removable:bmesh.ops.delete(bm,geom=removable,context='VERTS')
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    assert bm.faces and all(e.is_manifold for e in bm.edges),'UCX hull is not closed'
    mesh=bpy.data.meshes.new('Convex chair collision');bm.to_mesh(mesh);bm.free()
    o=bpy.data.objects.new('UCX_SM_DiningChair_%02d'%len(collision_objects),mesh);s.collection.objects.link(o)
    collision_objects.append(o);return o

def box_collision(loc,size):
    return collider_from_points([(loc[0]+a*size[0]/2,loc[1]+b*size[1]/2,loc[2]+c*size[2]/2)
                                for a in (-1,1) for b in (-1,1) for c in (-1,1)])

def bounds(o):
    bpy.context.view_layer.update();ps=[o.matrix_world@Vector(v) for v in o.bound_box]
    return [min(p[i] for p in ps) for i in range(3)],[max(p[i] for p in ps) for i in range(3)]

def contact(a,b,label):
    amin,amax=bounds(a);bmin,bmax=bounds(b)
    overlap=[min(amax[i],bmax[i])-max(amin[i],bmin[i]) for i in range(3)]
    assert min(overlap)>-.00002,(label,overlap)
    joint_checks.append({'joint':label,'overlap_mm':[round(x*1000,3) for x in overlap]})

def rear_y(z):return .172+(z-.425)*.145
def rear_x(z):return .197+max(0,z-.48)*.029

def lathe(name,cx,cy,profile):
    n=32;vs=[(cx+r*math.cos(j*math.tau/n),cy+r*math.sin(j*math.tau/n),z) for z,r in profile for j in range(n)]
    fs=[tuple(range(n-1,-1,-1)),tuple((len(profile)-1)*n+j for j in range(n))]
    fs += [(i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j) for i in range(len(profile)-1) for j in range(n)]
    o=custom(name,vs,fs,base_parts,'Z',bevel=0)
    for poly in o.data.polygons:poly.use_smooth=len(poly.vertices)==4
    o.modifiers.new('Smooth turned wood','WEIGHTED_NORMAL');collider_from_points(vs)
    return o

def prism_xz(name,outline,thickness,axis='X',bow=0):
    n=len(outline);vs=[]
    for sign in (-1,1):
        for x,z in outline:
            y=rear_y(z)-bow*(1-min(1,abs(x)/.236)**2)+sign*thickness/2
            vs.append((x,y,z))
    fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return custom(name,vs,fs,base_parts,axis,bevel=.0015)

def round_beam(name,a,b,radius=.012):
    a,b=Vector(a),Vector(b);direction=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=radius,depth=direction.length,location=(a+b)/2)
    o=bpy.context.object;o.name=name;o.rotation_euler=direction.to_track_quat('Z','Y').to_euler()
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    o.data.materials.append(wood_mat);o.data.materials.append(end_mat)
    for p in o.data.polygons:
        p.use_smooth=len(p.vertices)==4
        if len(p.vertices)>4:p.material_index=1
    grain(o,'Y' if abs(direction.y)>abs(direction.x) else 'X',wear=.25);edges(o,.0008);base_parts.append(o)
    collider_from_points([o.matrix_world@v.co for v in o.data.vertices]);return o

# A shallow saddle is carved into a continuous solid timber seat.
outline=[]
for cx,cy,base_angle in ((.214,.174,0),(-.214,.174,90),(-.214,-.214,180),(.214,-.214,270)):
    for j in range(10):
        t=math.radians(base_angle+j*90/9);x=cx+.026*math.cos(t);y=cy+.026*math.sin(t)
        if y>-.12:x*=1-.08*(y+.12)/.32
        outline.append((x,y))
# The order above circles anticlockwise from the rear-right corner.
n=len(outline);vs=[(0,-.02,.4535)];rings=(.24,.48,.70,.86,1.)
for r in rings:
    for x,y in outline:
        vs.append((x*r,-.02+(y+.02)*r,.46-.0065*(1-r*r)**2))
fs=[(0,1+j,1+(j+1)%n) for j in range(n)]
for k in range(len(rings)-1):
    lo,hi=1+k*n,1+(k+1)*n
    fs += [(lo+j,hi+j,hi+(j+1)%n,lo+(j+1)%n) for j in range(n)]
bottom=len(vs);vs += [(x,y,.425) for x,y in outline]
outer=1+(len(rings)-1)*n
fs += [(outer+j,bottom+j,bottom+(j+1)%n,outer+(j+1)%n) for j in range(n)]
fs.append(tuple(bottom+j for j in range(n-1,-1,-1)))
seat=custom('Saddled solid hardwood seat',vs,fs,base_parts,'Y',bevel=.0018)
seat.data.materials.append(end_mat)
for p in seat.data.polygons:
    if abs(p.normal.y)>.85:p.material_index=1
seat['seat_height_cm']=46;seat['saddle_depth_mm']=6.5
box_collision((0,-.02,.4425),(.48,.44,.035))

front_profile=[(0,.018),(.004,.021),(.012,.022),(.020,.021),(.029,.0175),(.05,.0155),
    (.10,.014),(.17,.0135),(.208,.015),(.229,.020),(.246,.024),(.262,.025),(.279,.023),
    (.295,.017),(.305,.015),(.312,.020),(.322,.021),(.330,.018),(.34,.015),(.359,.018)]
front_legs=[];front_shoulders=[];rear_posts=[]
for sx in (-1,1):
    leg=lathe('Turned front leg',sx*.194,-.188,front_profile);front_legs.append(leg)
    shoulder=box('Front leg mortise block',(sx*.194,-.188,.394),(.052,.052,.088),axis='Z',bevel=.0014,wear=.28,endfaces=True)
    front_shoulders.append(shoulder);contact(leg,shoulder,'Front leg into shoulder');contact(shoulder,seat,'Front shoulder into hardwood seat')
    # The UCX covers the upper block as well as the turned leg.
    box_collision((sx*.194,-.188,.394),(.052,.052,.088))
    rings_back=[(0,sx*.205,.212,.018,.020),(.025,sx*.205,.212,.0205,.0215),
        (.20,sx*.197,.192,.020,.021),(.35,sx*.195,.175,.021,.023),
        (.426,sx*.197,rear_y(.426),.024,.024),(.48,sx*.197,rear_y(.48),.0235,.0235),
        (.64,sx*rear_x(.64),rear_y(.64),.022,.022),(.82,sx*rear_x(.82),rear_y(.82),.022,.022),
        (1.037,sx*rear_x(1.037),rear_y(1.037),.0235,.0235)]
    rvs=[(x+dx*hx,y+dy*hy,z) for z,x,y,hx,hy in rings_back for dx,dy in ((-1,-1),(1,-1),(1,1),(-1,1))]
    rfs=[(3,2,1,0),tuple((len(rings_back)-1)*4+j for j in range(4))]
    rfs += [(i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j) for i in range(len(rings_back)-1) for j in range(4)]
    post=custom('Continuous rear leg and back stile',rvs,rfs,base_parts,'Z',bevel=.0018);rear_posts.append(post)
    contact(post,seat,'Rear post passes into seat mortise')
    collider_from_points([v for v in rvs if v[2]<=.48]);collider_from_points([v for v in rvs if v[2]>=.426])

# Seat-frame rails have tenons inside each leg, not disconnected end caps.
apron_front=box('Front seat apron',(0,-.188,.400),(.398,.024,.068),bevel=.0015,wear=.24,endfaces=True)
box_collision((0,-.188,.400),(.398,.024,.068))
for shoulder in front_shoulders:contact(apron_front,shoulder,'Front apron into shoulder')
contact(apron_front,seat,'Front apron against seat underside')
apron_rear=box('Rear seat apron',(0,.174,.403),(.4,.025,.062),bevel=.0015,wear=.2,endfaces=True)
box_collision((0,.174,.403),(.4,.025,.062))
for post in rear_posts:contact(apron_rear,post,'Rear apron into continuous post')
for i,sx in enumerate((-1,1)):
    side=box('Side seat apron',(sx*.194,-.007,.403),(.025,.370,.062),axis='Y',bevel=.0015,wear=.24,endfaces=True)
    box_collision((sx*.194,-.007,.403),(.025,.370,.062))
    contact(side,front_shoulders[i],'Side apron into front shoulder');contact(side,rear_posts[i],'Side apron into rear post')
    for z in (.385,.413):peg('Seated hardwood drawbore peg',(sx*.2201,-.188,z),.0027,.003,(0,math.pi/2,0),base_parts,end_mat)

# An open H stretcher reinforces the chair, while retaining the leg gaps.
side_bars=[]
for i,sx in enumerate((-1,1)):
    side=round_beam('Turned side stretcher',(sx*.194,-.188,.18),(sx*.198,.1945,.18),.012)
    side_bars.append(side);contact(side,front_legs[i],'Side stretcher into front leg');contact(side,rear_posts[i],'Side stretcher into rear leg')
middle=round_beam('H frame cross stretcher',(-.196,.015,.18),(.196,.015,.18),.0125)
for side in side_bars:contact(middle,side,'H cross stretcher into side stretcher')

# High back: lower rail, three spoon-curved wooden slats, and an arched crest.
lower=prism_xz('Lower back rail',[(-.21,.535),(.21,.535),(.21,.582),(-.21,.582)],.036)
collider_from_points([v.co for v in lower.data.vertices])
for post in rear_posts:contact(lower,post,'Lower back rail into stiles')
xs=(-.236,-.224,-.185,-.12,0,.12,.185,.224,.236)
tops=(1.020,1.040,1.048,1.054,1.060,1.054,1.048,1.040,1.020)
crest_outline=list(zip(xs,tops))+[(x,z-.064) for x,z in reversed(list(zip(xs,tops)))]
crest=prism_xz('Shaped arched top crest rail',crest_outline,.038,bow=.007)
for lo,hi in ((-.24,-.07),(-.12,.12),(.07,.24)):
    collider_from_points([v.co for v in crest.data.vertices if lo<=v.co.x<=hi])
for post in rear_posts:contact(crest,post,'Crest mortise into back stile')
for cx in (-.112,0,.112):
    levels=(.567,.62,.72,.80,.88,.96,1.005)
    widths=(.028,.037,.048,.051,.047,.034,.029) if cx else (.045,.056,.070,.073,.066,.050,.045)
    sv=[]
    for sign in (-1,1):
        for z,w in zip(levels,widths):
            # Gentle lumbar bow remains in the same physical plane as both rails.
            bow=.007*math.sin(math.pi*(z-.567)/(.438))
            y=rear_y(z)-bow+sign*.010
            sv.extend(((cx-w/2,y,z),(cx+w/2,y,z)))
    count=len(levels);sf=[]
    for side in range(2):
        start=side*count*2
        sf += [(start+2*i,start+2*i+1,start+2*(i+1)+1,start+2*(i+1)) for i in range(count-1)]
    for i in range(count-1):
        sf.append((2*i,2*(i+1),count*2+2*(i+1),count*2+2*i))
        sf.append((2*i+1,count*2+2*i+1,count*2+2*(i+1)+1,2*(i+1)+1))
    sf += [(0,count*2,count*2+1,1),(2*count-2,2*count-1,4*count-1,4*count-2)]
    slat=custom('Curved vertical back slat',sv,sf,base_parts,'Z',bevel=.0016)
    collider_from_points(sv);contact(slat,lower,'Back slat tenon into lower rail');contact(slat,crest,'Back slat tenon into crest')

for sx in (-1,1):peg('Recessed underside fixing',(sx*.13,-.075,.426),.0022,.0025,(0,0,0),base_parts,iron)

# Independent editable source parts are kept hidden; only the joined asset is exported.
sources=bpy.data.collections.new('SOURCE - editable hardwood chair components');s.collection.children.link(sources)
for part in base_parts:
    duplicate=part.copy();duplicate.data=part.data.copy();sources.objects.link(duplicate)
sources.hide_viewport=True;sources.hide_render=True
bpy.ops.object.select_all(action='DESELECT')
for part in base_parts:part.select_set(True)
bpy.context.view_layer.objects.active=base_parts[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join()
asset=bpy.context.object;asset.name='SM_DiningChair';s.cursor.location=(0,0,0)
bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for uv in list(asset.data.uv_layers):asset.data.uv_layers.remove(uv)
asset.data.uv_layers.new(name='UVMap');bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(68),island_margin=.007);bpy.ops.object.mode_set(mode='OBJECT')
tri=asset.modifiers.new('Game triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
asset['seat_height_cm']=46;asset['cushion']=False;asset['paired_asset']='LargeDiningTable'
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True)
for o in collision_objects:o.select_set(True)
bpy.context.view_layer.objects.active=asset
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_DiningChair.fbx'),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
collision_count=len(collision_objects)
for o in collision_objects:bpy.data.objects.remove(o,do_unlink=True)

studio=bpy.data.collections.new('Preview studio - excluded from FBX');s.collection.children.link(studio)
def studio_object(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor=bpy.data.materials.new('Preview floor');floor.use_nodes=True
p=next(n for n in floor.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.07,.073,.078,1);p.inputs['Roughness'].default_value=.88
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));o=bpy.context.object;o.name='Preview floor';o.data.materials.append(floor);studio_object(o)
target=Vector((0,.015,.54));bpy.ops.object.camera_add(location=(1.65,-2.25,1.44));cam=bpy.context.object;cam.name='Camera_DiningChair'
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.40;cam.data.clip_start=.005;s.camera=cam;studio_object(cam)
for name,pos,power,size,col in [('Key',(-1.3,-1.6,2.6),280,2.1,(1,.9,.78)),('Fill',(1.8,-.2,1.8),150,1.7,(.79,.87,1)),('Rim',(0,1.8,2.3),230,1.8,(1,.92,.83))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=col
    o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_object(o)
s.world.use_nodes=True;next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.12,.14,.17,1)
s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.resolution_x=1200;s.render.resolution_y=1400;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'DiningChair_Preview.png');s.view_settings.view_transform='AgX';s.view_settings.exposure=-.25;studio.hide_viewport=True
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
bm=bmesh.new();bm.from_mesh(asset.data)
report={'parts':{'SM_DiningChair':{'dimensions_cm':[v*100 for v in asset.dimensions],'triangles':len(asset.data.polygons),
    'collision_hulls':collision_count,'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),
    'uv_channels':len(asset.data.uv_layers),'material_slots':[m.name for m in asset.data.materials]}},
    'style':'high back hardwood dining chair, arched crest, curved slats, turned front legs, no cushion',
    'seat_height_cm':46,'seat_center_height_cm':45.35,'saddle_depth_mm':6.5,'seat_size_cm':[48,44],
    'back_recline_degrees':math.degrees(math.atan(.145)),'joinery_contacts':joint_checks,
    'origin':[0,0,0],'front_blender':'-Y','front_ue':'+Y','exported_lights':0,'exported_cameras':0,'cushion':False}
bm.free();assert report['parts']['SM_DiningChair']['non_manifold_edges']==0,report
assert .47<asset.dimensions.x<.50 and .51<asset.dimensions.y<.57 and 1.04<asset.dimensions.z<1.08,asset.dimensions
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'DiningChair.blend'))
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
