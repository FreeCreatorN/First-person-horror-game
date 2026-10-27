"""Long rectangular Chinese altar table with seated, carved cloud reliefs."""
import bpy,bmesh,math,json,random
from pathlib import Path
from mathutils import Vector
OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\AltarTable');rng=random.Random(108)
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
base_parts=[];collider_specs=[]
exec(compile((OUT/'shader_helpers.py').read_text(encoding='utf-8'),'shader_helpers.py','exec'))
wood_mat=wood('M_Altar_Wood');end_mat=wood('M_Altar_Endgrain',True)
for m in [wood_mat,end_mat]:
    ns=m.node_tree.nodes;ls=m.node_tree.links;p=next(n for n in ns if n.type=='BSDF_PRINCIPLED')
    original=p.inputs['Base Color'].links[0].from_socket
    tint=ns.new('ShaderNodeVectorMath');tint.name='Deep aged rosewood';tint.operation='MULTIPLY';ls.new(original,tint.inputs[0]);tint.inputs[1].default_value=(.80,.43,.32);ls.new(tint.outputs[0],p.inputs['Base Color'])
    original=p.inputs['Roughness'].links[0].from_socket
    rough=ns.new('ShaderNodeMath');rough.operation='MULTIPLY';rough.inputs[1].default_value=.84;ls.new(original,rough.inputs[0]);ls.new(rough.outputs[0],p.inputs['Roughness'])
    m.diffuse_color=(.125,.040,.020,1)
iron=bpy.data.materials.get('M_Altar_Dark') or bpy.data.materials.new('M_Altar_Dark');iron.use_nodes=True;iron.diffuse_color=(.030,.012,.006,1)
p=next(n for n in iron.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.030,.012,.006,1);p.inputs['Roughness'].default_value=.76
exec(compile((OUT/'mesh_helpers.py').read_text(encoding='utf-8'),'mesh_helpers.py','exec'))

def collision(loc,size):collider_specs.append((loc,size))
def prism_xy(name,outline,bottom,top,axis='X',bevel=.002):
    n=len(outline);vs=[(x,y,z) for z in [bottom,top] for x,y in outline]
    fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return custom(name,vs,fs,base_parts,axis,bevel=bevel)
def smooth_points(points,steps=5,closed=False):
    result=[];n=len(points)
    for i in range(n if closed else n-1):
        p0=Vector(points[(i-1)%n] if closed or i>0 else points[0]);p1=Vector(points[i]);p2=Vector(points[(i+1)%n]);p3=Vector(points[(i+2)%n] if closed or i+2<n else points[-1])
        for j in range(steps):
            t=j/steps;v=.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t);result.append(tuple(v))
    if not closed:result.append(tuple(points[-1]))
    return result
def prism_xz(name,outline,front,back,axis='X',bevel=.0015):
    n=len(outline)
    vs=[(x,d,z) if axis=='X' else (d,x,z) for d in [front,back] for x,z in outline]
    fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return custom(name,vs,fs,base_parts,axis,bevel=bevel)
def tube_mesh(name,points,radius,group=base_parts,mat=wood_mat,axis='X'):
    pts=[Vector(p) for p in points];n=12;vs=[]
    for i,p in enumerate(pts):
        tangent=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        normal=Vector((0,1,0)) if abs(tangent.y)<.9 else Vector((1,0,0))
        normal=(normal-tangent*normal.dot(tangent)).normalized();binormal=tangent.cross(normal).normalized()
        for j in range(n):vs.append(tuple(p+radius*(normal*math.cos(j*math.tau/n)+binormal*math.sin(j*math.tau/n))))
    fs=[tuple(range(n-1,-1,-1)),tuple((len(pts)-1)*n+j for j in range(n))]
    fs += [(k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j) for k in range(len(pts)-1) for j in range(n)]
    return custom(name,vs,fs,group,axis,mat,0)
def carve(o,cutter):
    bpy.context.view_layer.objects.active=o;m=o.modifiers.new('Recessed hand carved groove','BOOLEAN');m.operation='DIFFERENCE';m.solver='EXACT';m.object=cutter
    while o.modifiers.find(m.name)>0:bpy.ops.object.modifier_move_up(modifier=m.name)
    bpy.ops.object.modifier_apply(modifier=m.name);bpy.data.objects.remove(cutter,do_unlink=True)

# A flat, mitred frame surrounds the long three-board tabletop.
for i in [-1,0,1]:box('Long solid top plank',(0,i*.170,.930),(2.068,.1697,.040),bevel=.0018,tone=[.95,1.04,.99][i+1],wear=.25,endfaces=True)
prism_xy('Front mitred top rail',[(-1.10,-.30),(1.10,-.30),(1.035,-.255),(-1.035,-.255)],.906,.950)
prism_xy('Rear mitred top rail',[(-1.035,.255),(1.035,.255),(1.10,.30),(-1.10,.30)],.906,.950)
prism_xy('Left mitred top end',[(-1.10,-.30),(-1.035,-.255),(-1.035,.255),(-1.10,.30)],.906,.950,'Y')
prism_xy('Right mitred top end',[(1.035,-.255),(1.10,-.30),(1.10,.30),(1.035,.255)],.906,.950,'Y')
for y in [-.292,.292]:box('Long lower rim bead',(0,y,.905),(2.18,.012,.010),bevel=.003,wear=.2)
for x in [-1.092,1.092]:box('End lower rim bead',(x,0,.905),(.012,.574,.010),axis='Y',bevel=.003,wear=.2)
collision((0,0,.928),(2.2,.60,.044))

# Subtly shaped inward hoof feet and square legs support the whole frame.
for sx in [-1,1]:
    for sy in [-1,1]:
        rings=[(0,.040,sx*.895,sy*.218),(.018,.041,sx*.895,sy*.218),(.060,.034,sx*.902,sy*.218),(.115,.029,sx*.902,sy*.218),(.38,.033,sx*.90,sy*.215),(.909,.038,sx*.90,sy*.215)]
        vs=[]
        for z,h,cx,cy in rings:vs += [(cx+dx*h,cy+dy*h,z) for dx,dy in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        n=len(rings);fs=[(3,2,1,0),tuple((n-1)*4+j for j in range(4))]+[(4*k+j,4*k+(j+1)%4,4*(k+1)+(j+1)%4,4*(k+1)+j) for k in range(n-1) for j in range(4)]
        custom('Square leg with hoof foot',vs,fs,base_parts,'Z',bevel=.0024)
        collision((sx*.90,sy*.216,.4545),(.088,.086,.909))
        for z in [.867,.785]:
            peg('Apron mortise wooden peg',(sx*.90,sy*.2528,z),.0031,.003,(math.pi/2,0,0),base_parts,end_mat)
        box('Leg shoulder bead',(sx*.90,sy*.215,.874),(.079,.079,.009),axis='Z',bevel=.002,tone=.95,wear=.18)

# The front apron is a solid board whose lower silhouette forms cloud spandrels.
left=[(-.940,.611),(-.898,.610),(-.876,.625),(-.864,.660),(-.850,.699),(-.814,.728),(-.777,.742),(-.742,.737),(-.721,.717),(-.698,.709),(-.675,.718),(-.645,.740),(-.601,.755),(-.545,.760)]
lower_controls=left+[(-.27,.762),(0,.761),(.27,.762)]+[(-x,z) for x,z in reversed(left)]
lower=smooth_points(lower_controls,5)
outline=[(-.940,.907),(.940,.907)]+list(reversed(lower))
front=prism_xz('Cloud shaped solid front apron',outline,-.244,-.208,bevel=.0014)
for x in [-.80,.80]:collision((x,-.227,.758),(.280,.048,.300))
collision((0,-.227,.835),(1.39,.048,.146))
tube_mesh('Seated front lower cloud moulding',[(x,-.2443,z+.006) for x,z in lower],.0028)
box('Front apron upper moulding',(0,-.245,.894),(1.85,.006,.009),bevel=.0022,wear=.2)
box('Rear solid apron',(0,.226,.832),(1.88,.036,.150),bevel=.002,endfaces=True)
collision((0,.226,.832),(1.88,.036,.150))
for sx in [-1,1]:
    side_lower=[(x*(.238/.940),z) for x,z in lower]
    side_outline=[(-.238,.907),(.238,.907)]+list(reversed(side_lower))
    prism_xz('Side cloud spandrel apron',side_outline,sx*.90-.018,sx*.90+.018,'Y',.0015)
    tube_mesh('Seated side cloud moulding',[(sx*.9183,y,z+.006) for y,z in side_lower],.0024,axis='Y')
    collision((sx*.90,0,.758),(.040,.476,.300))
    box('Side lower stretcher',(sx*.901,0,.245),(.042,.465,.046),axis='Y',bevel=.002,endfaces=True,wear=.22)
    collision((sx*.901,0,.245),(.042,.465,.046))
box('Rear lower cross stretcher',(0,.215,.245),(1.84,.036,.040),bevel=.002,endfaces=True,wear=.2)
collision((0,.215,.245),(1.84,.036,.040))

# The central ruyi-cloud relief is embedded into the apron and truly incised.
cloud=[(-1.00,-.05),(-1.04,.17),(-.96,.42),(-.77,.53),(-.56,.49),(-.48,.73),(-.28,.90),(0,.94),(.27,.85),(.44,.63),(.49,.45),(.74,.51),(.96,.39),(1.02,.17),(.93,-.03),(.68,-.11),(.42,-.04),(.18,-.24),(.04,-.53),(-.11,-.76),(-.24,-.71),(-.26,-.53),(-.15,-.40),(-.10,-.24),(-.26,-.12),(-.48,-.07),(-.72,-.15),(-.92,-.14)]
grooves=[ [(-.76,.15),(-.82,.30),(-.68,.37),(-.53,.26),(-.58,.09),(-.37,.02),(-.17,.08)],
          [(.25,.08),(.48,.04),(.67,.11),(.77,.27),(.63,.35),(.50,.22)],
          [(-.25,.38),(-.27,.62),(-.08,.76),(.14,.65),(.18,.43),(.02,.28),(-.02,.08)] ]
for cx,size in [(0,.055)]:
    scale_z=size*.80;cz=.830
    pts=[(cx+x*size,cz+z*scale_z) for x,z in smooth_points(cloud,4,True)]
    plaque=prism_xz('Ruyi cloud relief seated in apron',pts,-.248,-.2425,bevel=.0009)
    for stroke in grooves:
        path=[(cx+x*size,-.24835,cz+z*scale_z) for x,z in smooth_points(stroke,5)]
        temp=[];c=tube_mesh('Temporary carving cutter',path,.00145,temp)
        carve(plaque,c)
    for name in ['WoodCoord','WoodTone','Wear']:
        a=plaque.data.attributes.get(name)
        if a:plaque.data.attributes.remove(a)
    grain(plaque,'X',tone=.98,wear=.15)
# Patinated fixing heads sit on the underside and remain part of the wood prop.
for x in [-.80,.80]:peg('Dark underside fixing',(x,0,.906),.0022,.002,(0,0,0),base_parts,iron)

bpy.ops.object.select_all(action='DESELECT')
for o in base_parts:o.select_set(True)
bpy.context.view_layer.objects.active=base_parts[0];bpy.ops.object.convert(target='MESH')
# Remove microscopic bevel/boolean collapses inside each component independently.
# Keeping the components separate here preserves the intended mortise contacts.
for part in list(bpy.context.selected_objects):
    part.data.calc_loop_triangles()
    if any(t.area<1e-11 for t in part.data.loop_triangles):
        bm=bmesh.new();bm.from_mesh(part.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=2e-7)
        bmesh.ops.dissolve_degenerate(bm,dist=2e-7,edges=list(bm.edges))
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(part.data);bm.free()
        bpy.context.view_layer.objects.active=part
        normal=part.modifiers.new('Clean solid surface normals','WEIGHTED_NORMAL');normal.keep_sharp=True
        bpy.ops.object.modifier_apply(modifier=normal.name)
bpy.context.view_layer.objects.active=base_parts[0];bpy.ops.object.join()
asset=bpy.context.object;asset.name='SM_AltarTable';s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for uv in list(asset.data.uv_layers):asset.data.uv_layers.remove(uv)
asset.data.uv_layers.new(name='UVMap')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.006);bpy.ops.object.mode_set(mode='OBJECT')
tri=asset.modifiers.new('Game triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
cols=[]
for i,(loc,size) in enumerate(collider_specs):box('UCX_SM_AltarTable_%02d'%i,loc,size,cols,mat=iron,bevel=0)
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True)
for c in cols:c.select_set(True)
bpy.context.view_layer.objects.active=asset
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_AltarTable.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
for c in cols:bpy.data.objects.remove(c,do_unlink=True)

studio=bpy.data.collections.new('Preview studio - excluded from FBX');s.collection.children.link(studio)
def move_studio(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor=bpy.data.materials.new('Preview ground');floor.use_nodes=True;p=next(n for n in floor.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.055,.060,.065,1);p.inputs['Roughness'].default_value=.86
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));o=bpy.context.object;o.name='Preview floor';o.data.materials.append(floor);move_studio(o)
target=Vector((0,0,.48));bpy.ops.object.camera_add(location=(2.65,-3.4,1.9));cam=bpy.context.object;cam.name='Camera_AltarTable';cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=2.95;cam.data.clip_start=.01;s.camera=cam;move_studio(cam)
for name,pos,power,size,col in [('Key',(-1.5,-2,3),350,2.3,(1,.89,.75)),('Fill',(2,-.2,2),210,2.2,(.76,.85,1)),('Rim',(0,2.2,2.6),310,1.8,(1,.91,.78))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=col;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();move_studio(o)
s.world.use_nodes=True;next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.12,.14,.17,1)
s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.render.resolution_x=1600;s.render.resolution_y=1050;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'AltarTable_Preview.png');s.view_settings.view_transform='AgX';s.view_settings.exposure=-.35;studio.hide_viewport=True
for o in s.objects:o.select_set(False)
asset.select_set(True);bpy.context.view_layer.objects.active=asset
if not bpy.app.background:
    for win in bpy.context.window_manager.windows:
        for a in win.screen.areas:
            if a.type=='VIEW_3D':
                v=a.spaces.active;r=v.region_3d;r.view_location=target;r.view_rotation=cam.rotation_euler.to_quaternion();r.view_distance=3.3;r.view_perspective='PERSP';v.clip_start=.005;v.shading.color_type='MATERIAL';v.overlay.show_overlays=False;r.update()
bm=bmesh.new();bm.from_mesh(asset.data)
report={'parts':{'SM_AltarTable':{'dimensions_cm':[v*100 for v in asset.dimensions],'triangles':len(asset.data.polygons),'collision_hulls':len(cols),'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'uv_channels':len(asset.data.uv_layers),'material_slots':[m.name for m in asset.data.materials]}},'style':'long flat rectangular traditional altar table with central ruyi relief and cloud aprons','origin':[0,0,0],'front_blender':'-Y','front_ue':'+Y','carved_cloud_reliefs':1,'relief_embedding_depth_mm':1.5,'exported_lights':0}
bm.free();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'AltarTable.blend'));(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
