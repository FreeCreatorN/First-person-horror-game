"""Eight-seat farmhouse dining table, metric source art and UE-ready UCX."""
import bpy, bmesh, math, json, random
from pathlib import Path
from mathutils import Vector

OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable')
rng=random.Random(362)
exec((OUT/'cli_seed.py').read_text(encoding='utf-8-sig').split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
base_parts=[];collider_specs=[];joinery=[]
exec(compile((OUT/'shader_helpers.py').read_text(encoding='utf-8'),'shader_helpers.py','exec'))
wood_mat=wood('M_Dining_Wood');end_mat=wood('M_Dining_Endgrain',True)
for m in (wood_mat,end_mat):
    ns=m.node_tree.nodes;ls=m.node_tree.links
    p=next(n for n in ns if n.type=='BSDF_PRINCIPLED')
    old=p.inputs['Base Color'].links[0].from_socket
    tint=ns.new('ShaderNodeVectorMath');tint.operation='MULTIPLY'
    ls.new(old,tint.inputs[0]);tint.inputs[1].default_value=(.98,.83,.69)
    ls.new(tint.outputs[0],p.inputs['Base Color'])
    m.diffuse_color=(.20,.108,.049,1)
iron=bpy.data.materials.new('M_Dining_Dark');iron.use_nodes=True
p=next(n for n in iron.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
p.inputs['Base Color'].default_value=(.035,.030,.022,1);p.inputs['Metallic'].default_value=.55;p.inputs['Roughness'].default_value=.73
iron.diffuse_color=(.035,.030,.022,1)
exec(compile((OUT/'mesh_helpers.py').read_text(encoding='utf-8'),'mesh_helpers.py','exec'))

def collision(loc,size):collider_specs.append((loc,size))
def lathe(name,cx,cy,profile):
    steps=40
    vs=[(cx+r*math.cos(j*math.tau/steps),cy+r*math.sin(j*math.tau/steps),z)
        for z,r in profile for j in range(steps)]
    fs=[tuple(range(steps-1,-1,-1)),tuple((len(profile)-1)*steps+j for j in range(steps))]
    fs += [(i*steps+j,i*steps+(j+1)%steps,(i+1)*steps+(j+1)%steps,(i+1)*steps+j)
           for i in range(len(profile)-1) for j in range(steps)]
    o=custom(name,vs,fs,base_parts,'Z',bevel=0)
    for poly in o.data.polygons:poly.use_smooth=len(poly.vertices)==4
    o.modifiers.new('Turned wood face normals','WEIGHTED_NORMAL')
    return o

def contact(a,b,label):
    # Record measurable overlap at intended mortise/shoulder connections.
    bpy.context.view_layer.update()
    def bounds(o):
        ps=[o.matrix_world@Vector(v) for v in o.bound_box]
        return [min(p[i] for p in ps) for i in range(3)],[max(p[i] for p in ps) for i in range(3)]
    amin,amax=bounds(a);bmin,bmax=bounds(b)
    overlap=[min(amax[i],bmax[i])-max(amin[i],bmin[i]) for i in range(3)]
    assert min(overlap)>-.00001,(label,overlap)
    joinery.append({'joint':label,'bounds_overlap_mm':[round(v*1000,4) for v in overlap]})

# Six long boards with narrow join lines; transverse breadboard ends.
top=[]
for i,tone in enumerate((.97,1.04,.99,1.025,.96,1.01)):
    top.append(box('Top plank %02d'%(i+1),(0,(i-2.5)*.175,.738),(2.224,.17465,.044),
                   bevel=.0018,tone=tone,wear=.23,endfaces=True))
for sx in (-1,1):
    top.append(box('Breadboard end', (sx*1.155,0,.738),(.090,1.05,.044),axis='Y',
                   bevel=.0025,tone=1.01 if sx<0 else .97,wear=.27,endfaces=True))
    # Dowel heads are let into the breadboard surface rather than floating.
    for y in (-.37,0,.37):
        peg('Breadboard drawbore peg',(sx*1.157,y,.7592),.004,.002,(0,0,0),base_parts,end_mat)
collision((0,0,.738),(2.40,1.05,.044))

profile=[(0,.035),(.004,.040),(.012,.041),(.020,.040),(.028,.035),(.042,.032),
         (.068,.031),(.095,.028),(.16,.025),(.25,.024),(.30,.027),(.329,.036),
         (.350,.045),(.372,.049),(.392,.050),(.414,.047),(.434,.039),(.450,.031),
         (.464,.029),(.470,.034),(.474,.040),(.483,.041),(.492,.040),(.498,.034),
         (.510,.029),(.554,.028),(.586,.031),(.602,.035)]
shoulders=[]
for sx in (-1,1):
    for sy in (-1,1):
        x,y=sx*.995,sy*.375
        turned=lathe('Turned leg %s %s'%(sx,sy),x,y,profile)
        shoulder=box('Square mortise shoulder',(x,y,.658),(.100,.100,.128),axis='Z',bevel=.0018,tone=.99,wear=.30,endfaces=True)
        shoulders.append(shoulder)
        contact(turned,shoulder,'Turned leg into upper block')
        # The upper shoulder penetrates the underside by 6 mm.
        contact(shoulder,top[0 if sy<0 else 5],'Leg shoulder into tabletop')
        collision((x,y,.361),(.101,.101,.722))
        peg('Apron drawbore pin',(x,sy*.4253,.685),.0034,.004,(math.pi/2,0,0),base_parts,end_mat)
        peg('End apron pin',(sx*1.0453,y,.670),.0034,.004,(0,math.pi/2,0),base_parts,end_mat)

aprons=[]
for sy in (-1,1):
    o=box('Long load bearing apron',(0,sy*.375,.684),(1.895,.035,.072),bevel=.0020,tone=.94,wear=.24,endfaces=True)
    aprons.append(o);collision((0,sy*.375,.684),(1.895,.035,.072))
    for shoulder in [a for a in shoulders if a.location.y*sy>0]:contact(o,shoulder,'Long apron tenon into leg')
    contact(o,top[0 if sy<0 else 5],'Long apron into tabletop')
    for z in (.654,.711):
        box('Inset long apron bead',(0,sy*.3928,z),(1.887,.005,.005),bevel=.0023,tone=.96,wear=.17)
for sx in (-1,1):
    o=box('End load bearing apron',(sx*.995,0,.684),(.035,.655,.072),axis='Y',bevel=.0020,tone=.96,wear=.24,endfaces=True)
    aprons.append(o);collision((sx*.995,0,.684),(.035,.655,.072))
    for shoulder in [a for a in shoulders if a.location.x*sx>0]:contact(o,shoulder,'End apron tenon into leg')
    contact(o,top[2],'End apron into tabletop')
    for z in (.654,.711):
        box('Inset end apron bead',(sx*1.0128,0,z),(.005,.647,.005),axis='Y',bevel=.0023,tone=.97,wear=.17)

# Cross battens touch the table underside; short diagonal corner braces sit high.
for x in (-.56,.56):
    cleat=box('Underside cross batten',(x,0,.705),(.052,.718,.028),axis='Y',bevel=.0015,tone=.91,wear=.18,endfaces=True)
    contact(cleat,top[2],'Batten into tabletop')
    collision((x,0,.705),(.052,.718,.028))
    for y in (-.26,.26):peg('Recessed underside screw',(x,y,.6906),.0025,.0018,(0,0,0),base_parts,iron)
for sx in (-1,1):
    for sy in (-1,1):
        brace=box('Hidden diagonal corner block',(sx*.933,sy*.313,.688),(.153,.040,.050),bevel=.0015,tone=.92,wear=.12)
        brace.rotation_euler.z=math.atan2(-sy,sx)

# Preserve separate editable components in a hidden source collection.
source_collection=bpy.data.collections.new('SOURCE - editable joinery components')
s.collection.children.link(source_collection)
for part in base_parts:
    duplicate=part.copy();duplicate.data=part.data.copy();source_collection.objects.link(duplicate)
source_collection.hide_viewport=True;source_collection.hide_render=True

bpy.ops.object.select_all(action='DESELECT')
for part in base_parts:part.select_set(True)
bpy.context.view_layer.objects.active=base_parts[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join()
asset=bpy.context.object;asset.name='SM_LargeDiningTable'
s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
for uv in list(asset.data.uv_layers):asset.data.uv_layers.remove(uv)
asset.data.uv_layers.new(name='UVMap')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(70),island_margin=.007)
bpy.ops.object.mode_set(mode='OBJECT')
tri=asset.modifiers.new('Game triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
asset['size_cm']='240 x 105 x 76';asset['seats']=8;asset['apron_clearance_cm']=64.8

cols=[]
for i,(loc,size) in enumerate(collider_specs):box('UCX_SM_LargeDiningTable_%02d'%i,loc,size,cols,mat=iron,bevel=0)
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True)
for c in cols:c.select_set(True)
bpy.context.view_layer.objects.active=asset
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_LargeDiningTable.fbx'),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
for c in cols:bpy.data.objects.remove(c,do_unlink=True)

studio=bpy.data.collections.new('Preview studio - excluded from FBX');s.collection.children.link(studio)
def studio_object(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
floor=bpy.data.materials.new('Preview floor');floor.use_nodes=True
p=next(n for n in floor.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
p.inputs['Base Color'].default_value=(.070,.073,.078,1);p.inputs['Roughness'].default_value=.88
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.0015));o=bpy.context.object;o.name='Preview floor';o.data.materials.append(floor);studio_object(o)
target=Vector((0,0,.40));bpy.ops.object.camera_add(location=(3.1,-3.65,2.48))
cam=bpy.context.object;cam.name='Camera_DiningTable';cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=3.14;cam.data.clip_start=.01;s.camera=cam;studio_object(cam)
for name,pos,power,size,col in [('Key',(-1.5,-2.0,3.3),440,2.8,(1,.90,.78)),
    ('Fill',(2.4,-.2,2.4),260,2.5,(.79,.87,1)),('Rim',(0,2.5,2.8),400,2.2,(1,.92,.83))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name
    o.data.energy=power;o.data.size=size;o.data.color=col
    o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();studio_object(o)
s.world.use_nodes=True
next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.12,.14,.17,1)
s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True
s.render.resolution_x=1600;s.render.resolution_y=1100;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'LargeDiningTable_Preview.png')
s.view_settings.view_transform='AgX';s.view_settings.exposure=-.25;studio.hide_viewport=True
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
bm=bmesh.new();bm.from_mesh(asset.data)
report={'parts':{'SM_LargeDiningTable':{'dimensions_cm':[v*100 for v in asset.dimensions],
    'triangles':len(asset.data.polygons),'collision_hulls':len(cols),
    'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'uv_channels':len(asset.data.uv_layers),
    'material_slots':[m.name for m in asset.data.materials]}},
    'style':'eight-seat old solid wood dining table with breadboard top and turned legs',
    'seats':8,'apron_clearance_cm':64.8,'long_side_clear_span_cm':189.0,'end_clear_span_cm':65.0,
    'joinery_contacts':joinery,'origin':[0,0,0],'exported_lights':0,'exported_cameras':0}
bm.free();assert report['parts']['SM_LargeDiningTable']['non_manifold_edges']==0,report
assert abs(asset.dimensions.z-.7602)<.002
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'LargeDiningTable.blend'))
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
