"""Refine the CLI layout into two independently usable wall-switch meshes."""
import bpy, bmesh, math, json
from pathlib import Path
from mathutils import Vector
OUT = Path(r'D:\UE\Project\HorrorGame\SourceArt\Switch')
seed = (OUT / 'cli_seed.py').read_text(encoding='utf-8')
exec(seed.split('# \u2500\u2500 Render Output')[0].split('# Render single frame')[0].split('scene.render.image_settings.file_format')[0])
s = bpy.context.scene
s.unit_settings.system = 'METRIC'
s.unit_settings.scale_length = 1
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
base_parts, rocker_parts = [], []

def material(name, color, metallic, roughness):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*color, 1)
    p = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    p.inputs['Emission Strength'].default_value = 0
    return m
ivory = material('M_Switch_Ivory', (.72,.70,.64), 0, .29)
dark = material('M_Switch_Charcoal', (.025,.029,.031), 0, .52)
steel = material('M_Switch_Steel', (.34,.37,.40), .8, .32)

def boundary(w, h, r, steps=12):
    pts = []
    for x,z,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
        for i in range(steps+1):
            a = math.radians(start+90*i/steps)
            pts.append((x+r*math.cos(a), z+r*math.sin(a)))
    return pts

def mesh_object(name, verts, faces, mat, group):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); s.collection.objects.link(o)
    o.data.materials.append(mat); group.append(o)
    return o

def rounding(o, width=.0005):
    b = o.modifiers.new('Manufactured edge radius', 'BEVEL')
    b.width = width; b.segments = 4; b.limit_method = 'ANGLE'; b.harden_normals = True
    o.modifiers.new('Surface normals', 'WEIGHTED_NORMAL')
    for p in o.data.polygons: p.use_smooth = True

def prism(name, w, h, r, front, back, mat, group, loc=(0,0,0), bevel=.0005):
    pts = boundary(w,h,r); n=len(pts)
    verts = [(x, y, z) for y in [front,back] for x,z in pts]
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    o=mesh_object(name,verts,faces,mat,group); o.location=loc
    if bevel: rounding(o,bevel)
    return o

def ring(name, outer, inner, front, back, mat, group, bevel=.0004):
    a=boundary(*outer); b=boundary(*inner); n=len(a)
    verts=[(x,y,z) for y in [front,back] for pts in [a,b] for x,z in pts]
    faces=[]
    for i in range(n):
        j=(i+1)%n
        faces += [(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),
                  (i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)]
    o=mesh_object(name,verts,faces,mat,group)
    if bevel: rounding(o,bevel)
    return o

def box(name,loc,size,mat,group,bevel=.0004):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object; o.name=name; o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mat); group.append(o)
    if bevel: rounding(o,bevel)
    return o

def boolean(o,cutter):
    bpy.context.view_layer.objects.active=o
    m=o.modifiers.new('Real recess','BOOLEAN');m.operation='DIFFERENCE';m.solver='EXACT';m.object=cutter
    bpy.ops.object.modifier_move_up(modifier=m.name)
    while o.modifiers.find(m.name)>0: bpy.ops.object.modifier_move_up(modifier=m.name)
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter,do_unlink=True)

ring('Rounded faceplate',(.086,.086,.005),(.060,.064,.0035),-.006,0,ivory,base_parts,.00055)
ring('Recessed button surround',(.060,.064,.0035),(.056,.060,.003),-.0052,.007,dark,base_parts,.0003)
prism('Rear mechanism housing',.054,.054,.003,.007,.025,dark,base_parts,bevel=.0006)
# Molded rear ribs and terminal sockets remain behind the mounting surface.
for x in [-.020,0,.020]:
    box('Rear housing rib',(x,.026,0),(.002,.002,.038),dark,base_parts,.0003)
for x in [-.014,.014]:
    temp=[]
    cutter=box('Terminal recess cutter',(x,.025,.013),(.009,.010,.011),dark,temp,0)
    boolean(bpy.data.objects['Rear mechanism housing'],cutter)
    box('Terminal clamp',(x,.022,.013),(.006,.002,.008),steel,base_parts,.0002)
for x in [-.033,.033]:
    box('Mounting bracket',(x,.002,0),(.010,.003,.036),steel,base_parts,.0006)
    for z in [-.012,.012]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.0023,depth=.0015,location=(x,-.0004,z),rotation=(math.pi/2,0,0))
        o=bpy.context.object;o.name='Bracket fixing screw';o.data.materials.append(steel);base_parts.append(o)
        rounding(o,.0002)
        temp=[];c=box('Screw slot',(x,-.0011,z),(.0032,.001,.0005),dark,temp,0);boolean(o,c)
# Axis runs horizontally through the rocker centre. End seats overlap the spindle.
for x in [-.029,.029]:
    box('Pivot bearing',(x,.001,0),(.002,.009,.008),dark,base_parts,.0005)
rocker=prism('Rounded rocker',.054,.058,.003,-.009,.003,ivory,rocker_parts,bevel=.0007)
temp=[]
c=prism('Indicator slot cutter',.007,.0012,.0005,-.010,-.0082,dark,temp,loc=(0,0,.018),bevel=0)
boolean(rocker,c)
prism('Recessed non luminous indicator',.0065,.0007,.0003,-.00855,-.0081,dark,rocker_parts,loc=(0,0,.018),bevel=.00005)
bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.0019,depth=.058,location=(0,-.003,0),rotation=(0,math.pi/2,0))
o=bpy.context.object;o.name='Rocker spindle';o.data.materials.append(steel);rocker_parts.append(o);rounding(o,.00015)

def combine(group,name,pivot):
    bpy.ops.object.select_all(action='DESELECT')
    for o in group: o.select_set(True)
    bpy.context.view_layer.objects.active=group[0]
    bpy.ops.object.convert(target='MESH');bpy.ops.object.join()
    o=bpy.context.object;o.name=name
    s.cursor.location=pivot;bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.018)
    bpy.ops.object.mode_set(mode='OBJECT')
    tri=o.modifiers.new('Game triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
    return o
base=combine(base_parts,'SM_Switch_Base',(0,0,0))
button=combine(rocker_parts,'SM_Switch_Rocker',(0,-.003,0))
button['press_axis']='local X';button['press_angle_degrees']=4.0
button['assembly_offset_blender_m']=[0,-.003,0]

def export_part(o,colliders):
    pos=o.location.copy();rot=o.rotation_euler.copy()
    o.location=(0,0,0);o.rotation_euler=(0,0,0)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True)
    for c in colliders:c.select_set(True)
    bpy.context.view_layer.objects.active=o
    bpy.ops.export_scene.fbx(filepath=str(OUT/(o.name+'.fbx')),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
    o.location=pos;o.rotation_euler=rot
    for c in colliders:bpy.data.objects.remove(c,do_unlink=True)
cols=[]
for i,(loc,size) in enumerate([((-.0365,-.003,0),(.013,.006,.086)),((.0365,-.003,0),(.013,.006,.086)),((0,-.003,.0375),(.060,.006,.011)),((0,-.003,-.0375),(.060,.006,.011)),((0,.016,0),(.054,.018,.054))]):
    box('UCX_SM_Switch_Base_%02d'%i,loc,size,dark,cols,0)
export_part(base,cols)
cols=[];box('UCX_SM_Switch_Rocker_00',(0,0,0),(.054,.012,.058),dark,cols,0)
export_part(button,cols)

# An editable demonstration in Blender only. FBX exports contain two meshes and UCX only.
s.frame_start=1;s.frame_end=96;s.render.fps=24
for frame,angle in [(1,-4),(24,-4),(30,4),(60,4),(66,-4),(96,-4)]:
    button.rotation_euler.x=math.radians(angle);button.keyframe_insert(data_path='rotation_euler',frame=frame)
s.frame_set(1)
studio=bpy.data.collections.new('Preview studio - excluded from FBX');s.collection.children.link(studio)
def move_studio(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
backdrop=material('Preview_Backdrop',(.17,.19,.205),0,.8)
temp=[];wall=box('Preview wall',(0,.035,0),(.5,.010,.5),backdrop,temp,.001);move_studio(wall)
target=Vector((0,-.003,0))
bpy.ops.object.camera_add(location=(.105,-.21,.079));cam=bpy.context.object;cam.name='Camera_Switch';move_studio(cam)
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.138;cam.data.clip_start=.001;s.camera=cam
for name,loc,power,size,color in [('Key',(-.12,-.22,.23),8,.18,(1,.93,.82)),('Fill',(.2,-.1,.08),5,.22,(.8,.87,1)),('Rim',(-.05,.05,.18),4,.12,(1,1,1))]:
    bpy.ops.object.light_add(type='AREA',location=loc);l=bpy.context.object;l.name='Preview '+name;l.data.energy=power;l.data.size=size;l.data.color=color
    l.rotation_euler=(target-l.location).to_track_quat('-Z','Y').to_euler();move_studio(l)
s.world.use_nodes=True
next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.12,.14,.16,1)
s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True
s.render.resolution_x=1000;s.render.resolution_y=1000;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'Switch_Preview.png')
s.view_settings.view_transform='AgX'
bpy.ops.object.select_all(action='DESELECT');button.select_set(True);bpy.context.view_layer.objects.active=button
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':
            v=a.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=.20;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
            v.region_3d.view_perspective='ORTHO';v.clip_start=.0005;v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
studio.hide_viewport=True
s.cursor.location=(0,0,0)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'WallSwitch.blend'))
report={'faceplate_cm':[8.6,8.6],'parts':{},'rocker_local_pivot':[0,0,0],'rocker_assembly_blender_m':[0,-.003,0],'press_axis_blender':'X','press_degrees':[-4,4],'self_emission':False,'exported_lights':0}
for o in [base,button]:
    bm=bmesh.new();bm.from_mesh(o.data)
    report['parts'][o.name]={'triangles':len(o.data.polygons),'dimensions_cm':[round(v*100,5) for v in o.dimensions],'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'materials':[m.name for m in o.data.materials]}
    bm.free()
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
