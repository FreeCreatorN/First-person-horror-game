"""Traditional plank-top writing desk with a genuinely hollow sliding drawer."""
import bpy, bmesh, math, json, random
from pathlib import Path
from mathutils import Vector
OUT=Path(r'D:\UE\Project\HorrorGame\SourceArt\OldWoodDesk');rng=random.Random(73)
seed=(OUT/'cli_seed.py').read_text(encoding='utf-8-sig');exec(seed.split('scene.render.image_settings.file_format')[0])
s=bpy.context.scene
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
s.unit_settings.system='METRIC';s.unit_settings.scale_length=1
base_parts=[];drawer_parts=[];collision_specs={'SM_OldWoodDesk_Base':[],'SM_OldWoodDesk_Drawer':[]}

def node(nodes,kind,name=None):
    n=nodes.new(kind)
    if name:n.name=name;n.label=name
    return n
def vector_scale(nodes,links,source,scale):
    n=node(nodes,'ShaderNodeVectorMath');n.operation='MULTIPLY';links.new(source,n.inputs[0]);n.inputs[1].default_value=scale;return n.outputs[0]
def math_node(nodes,links,operation,a,b):
    n=node(nodes,'ShaderNodeMath');n.operation=operation
    for value,socket in [(a,n.inputs[0]),(b,n.inputs[1])]:
        if isinstance(value,(int,float)):socket.default_value=value
        else:links.new(value,socket)
    return n.outputs[0]
def ramp(nodes,links,source,stops):
    n=node(nodes,'ShaderNodeValToRGB')
    cr=n.color_ramp
    while len(cr.elements)>2:cr.elements.remove(cr.elements[-1])
    for i,(position,color) in enumerate(stops):
        e=cr.elements[i] if i<2 else cr.elements.new(position);e.position=position;e.color=(*color,1)
    links.new(source,n.inputs['Fac']);return n.outputs['Color']
def noise(nodes,links,source,scale=2,detail=3):
    n=node(nodes,'ShaderNodeTexNoise');links.new(source,n.inputs['Vector']);n.inputs['Scale'].default_value=scale;n.inputs['Detail'].default_value=detail;n.inputs['Roughness'].default_value=.7
    return n.outputs['Fac']
def wood(name,endgrain=False):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(.16,.082,.031,1)
    ns=m.node_tree.nodes;ls=m.node_tree.links;ns.clear()
    p=node(ns,'ShaderNodeBsdfPrincipled','Wood surface');out=node(ns,'ShaderNodeOutputMaterial');ls.new(p.outputs['BSDF'],out.inputs['Surface'])
    p.inputs['Roughness'].default_value=.66;p.inputs['Metallic'].default_value=0
    coord=node(ns,'ShaderNodeAttribute','Local grain orientation');coord.attribute_name='WoodCoord'
    tone=node(ns,'ShaderNodeAttribute','Individual board tone');tone.attribute_name='WoodTone'
    wear=node(ns,'ShaderNodeAttribute','Wear amount');wear.attribute_name='Wear'
    stretched=vector_scale(ns,ls,coord.outputs['Vector'],(2.8,95,95))
    grain=noise(ns,ls,stretched,2.2,3.5)
    if endgrain:
        wave=node(ns,'ShaderNodeTexWave');wave.wave_type='RINGS';wave.rings_direction='X';ls.new(coord.outputs['Vector'],wave.inputs['Vector']);wave.inputs['Scale'].default_value=620;wave.inputs['Distortion'].default_value=5;wave.inputs['Detail Scale'].default_value=1.4;grain=wave.outputs['Fac']
    color=ramp(ns,ls,grain,[(.18,(.041,.019,.008)),(.42,(.095,.043,.016)),(.62,(.162,.083,.032)),(.82,(.23,.138,.063))])
    broad=noise(ns,ls,coord.outputs['Vector'],7,4)
    tint=ramp(ns,ls,broad,[(.12,(.48,.39,.31)),(.8,(1.0,.93,.83))])
    mix=node(ns,'ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.48;ls.new(color,mix.inputs[1]);ls.new(tint,mix.inputs[2])
    scaled=node(ns,'ShaderNodeVectorMath');scaled.operation='SCALE';ls.new(mix.outputs[0],scaled.inputs[0]);ls.new(tone.outputs['Fac'],scaled.inputs['Scale'])
    scratches=noise(ns,ls,vector_scale(ns,ls,coord.outputs['Vector'],(32,650,47)),2,1)
    scratches=math_node(ns,ls,'MULTIPLY',math_node(ns,ls,'GREATER_THAN',scratches,.71),wear.outputs['Fac'])
    mix=node(ns,'ShaderNodeMixRGB','Fine worn scratches');ls.new(scratches,mix.inputs[0]);ls.new(scaled.outputs[0],mix.inputs[1]);mix.inputs[2].default_value=(.21,.12,.054,1)
    geom=node(ns,'ShaderNodeNewGeometry');edge=node(ns,'ShaderNodeMapRange');ls.new(geom.outputs['Pointiness'],edge.inputs['Value']);edge.inputs['From Min'].default_value=.505;edge.inputs['From Max'].default_value=.57;edge.inputs['To Max'].default_value=.28
    worn=node(ns,'ShaderNodeMixRGB','Soft edge wear');ls.new(math_node(ns,ls,'MULTIPLY',edge.outputs[0],wear.outputs['Fac']),worn.inputs[0]);ls.new(mix.outputs[0],worn.inputs[1]);worn.inputs[2].default_value=(.245,.15,.075,1)
    # A faint broken cup ring on the top is baked into the atlas, not separate geometry.
    distance=node(ns,'ShaderNodeVectorMath');distance.operation='DISTANCE';ls.new(geom.outputs['Position'],distance.inputs[0]);distance.inputs[1].default_value=(.29,.075,.770)
    dist=math_node(ns,ls,'ABSOLUTE',math_node(ns,ls,'SUBTRACT',distance.outputs['Value'],.055),0)
    ring=math_node(ns,ls,'LESS_THAN',dist,.0022)
    xyz=node(ns,'ShaderNodeSeparateXYZ');ls.new(geom.outputs['Position'],xyz.inputs[0])
    ring=math_node(ns,ls,'MULTIPLY',ring,math_node(ns,ls,'GREATER_THAN',xyz.outputs['Z'],.73))
    ring=math_node(ns,ls,'MULTIPLY',ring,math_node(ns,ls,'MULTIPLY',broad,.38))
    stain=node(ns,'ShaderNodeMixRGB','Faded cup mark');ls.new(ring,stain.inputs[0]);ls.new(worn.outputs[0],stain.inputs[1]);stain.inputs[2].default_value=(.04,.020,.009,1);ls.new(stain.outputs[0],p.inputs['Base Color'])
    rough=math_node(ns,ls,'ADD',math_node(ns,ls,'MULTIPLY',broad,.23),.53);ls.new(rough,p.inputs['Roughness'])
    pores=noise(ns,ls,vector_scale(ns,ls,coord.outputs['Vector'],(3,800,800)),1.8,2)
    bump=node(ns,'ShaderNodeBump','Fine wood pores');bump.inputs['Strength'].default_value=.23;bump.inputs['Distance'].default_value=.00023;ls.new(pores,bump.inputs['Height']);ls.new(bump.outputs['Normal'],p.inputs['Normal'])
    return m
wood_mat=wood('M_OldDesk_Wood');end_mat=wood('M_OldDesk_Endgrain',True)
iron=bpy.data.materials.get('M_OldDesk_Iron') or bpy.data.materials.new('M_OldDesk_Iron');iron.use_nodes=True;iron.diffuse_color=(.022,.017,.013,1)
p=next(n for n in iron.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.022,.017,.013,1);p.inputs['Metallic'].default_value=.35;p.inputs['Roughness'].default_value=.82

def grain(o,axis='X',tone=None,wear=.35):
    if o.type!='MESH':return
    tone=rng.uniform(.85,1.12) if tone is None else tone
    coords=o.data.attributes.new('WoodCoord','FLOAT_VECTOR','POINT');tones=o.data.attributes.new('WoodTone','FLOAT','POINT');wears=o.data.attributes.new('Wear','FLOAT','POINT')
    shift=Vector((rng.random()*5,rng.random()*.11,rng.random()*.13))
    for v in o.data.vertices:
        x,y,z=v.co;co=(x,y,z) if axis=='X' else ((z,x,y) if axis=='Z' else (y,x,z))
        coords.data[v.index].vector=Vector(co)+shift;tones.data[v.index].value=tone;wears.data[v.index].value=wear

def edges(o,amount=.0015):
    b=o.modifiers.new('Worn solid edges','BEVEL');b.width=amount;b.segments=3;b.harden_normals=True
    o.modifiers.new('Face normals','WEIGHTED_NORMAL')
    for p in o.data.polygons:p.use_smooth=True

def box(name,loc,size,group=base_parts,axis='X',mat=wood_mat,bevel=.0015,tone=None,wear=.35,endfaces=False):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat)
    if endfaces and mat==wood_mat:
        o.data.materials.append(end_mat);k={'X':0,'Y':1,'Z':2}[axis]
        for p in o.data.polygons:
            if abs(p.normal[k])>.9:p.material_index=1
    grain(o,axis,tone,wear)
    if bevel:edges(o,bevel)
    group.append(o);return o

def custom(name,verts,faces,group,axis='X',mat=wood_mat,bevel=.0015):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me);s.collection.objects.link(o);o.data.materials.append(mat);grain(o,axis);group.append(o)
    if bevel:edges(o,bevel)
    return o

def peg(name,loc,radius,depth,rotation,group,mat=end_mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20,radius=radius,depth=depth,location=loc,rotation=rotation);o=bpy.context.object;o.name=name;o.data.materials.append(mat);grain(o,'Z',wear=.3);edges(o,.00028);group.append(o);return o

def collider(part,loc,size):collision_specs[part].append((list(loc),list(size)))
BASE='SM_OldWoodDesk_Base';DRAWER='SM_OldWoodDesk_Drawer'
for i in range(5):
    box('Aged tabletop plank %02d'%i,(0,(i-2)*.128,.752+rng.uniform(-.00012,.00012)),(1.102,.1277,.036),bevel=.0018,tone=[1.02,.94,1.08,.98,.90][i],wear=.7,endfaces=True)
for side in [-1,1]:box('Breadboard end',(side*.575,0,.752),(.05,.64,.036),axis='Y',bevel=.002,wear=.65,endfaces=True)
collider(BASE,(0,0,.752),(1.2,.64,.036))
# Four tapered legs, with their grain following the vertical fibres.
for sx in [-1,1]:
    for sy in [-1,1]:
        verts=[]
        for z,half,cx,cy in [(0,.024,sx*.517,sy*.252),(.035,.025,sx*.517,sy*.252),(.575,.0325,sx*.505,sy*.245),(.735,.0325,sx*.505,sy*.245)]:
            verts += [(cx+dx*half,cy+dy*half,z) for dx,dy in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        faces=[(3,2,1,0),(12,13,14,15)]+[(4*k+i,4*k+(i+1)%4,4*(k+1)+(i+1)%4,4*(k+1)+i) for k in range(3) for i in range(4)]
        custom('Tapered square leg',verts,faces,base_parts,'Z',bevel=.0017)
        collider(BASE,(sx*.511,sy*.2485,.3675),(.077,.072,.735))
        # Peg heads are seated into the mortise zone rather than hovering above it.
        peg('Front apron wooden peg',(sx*.505,sy*.2778,.678),.003,.0024,(math.pi/2,0,0),base_parts)
        peg('Lower stretcher peg',(sx*.514,sy*.277,.205),.0027,.0024,(math.pi/2,0,0),base_parts)
for side in [-1,1]:
    box('Side apron',(side*.505,0,.660),(.026,.500,.148),axis='Y',endfaces=True)
    collider(BASE,(side*.505,0,.660),(.026,.500,.148))
    box('Side apron lower bead',(side*.519,0,.593),(.006,.475,.008),axis='Y',bevel=.002)
    box('Front apron stile',(side*.400,-.274,.658),(.170,.026,.152),bevel=.0015)
    collider(BASE,(side*.400,-.274,.658),(.170,.026,.152))
    box('Front stile moulding',(side*.400,-.289,.591),(.164,.006,.009),bevel=.002)
box('Rear apron',(0,.245,.660),(1.015,.026,.148),endfaces=True)
collider(BASE,(0,.245,.660),(1.015,.026,.148))
box('Drawer opening upper rail',(0,-.274,.7275),(1.015,.026,.015))
box('Drawer opening lower rail',(0,-.274,.586),(1.015,.028,.014))
collider(BASE,(0,-.274,.7275),(1.015,.026,.015));collider(BASE,(0,-.274,.586),(1.015,.028,.014))
for side in [-1,1]:
    box('Drawer bottom runner',(side*.319,-.0145,.59075),(.050,.511,.015),axis='Y',bevel=.0007)
    collider(BASE,(side*.319,-.0145,.59075),(.050,.511,.015))
    box('Lower side stretcher',(side*.513,0,.205),(.032,.505,.040),axis='Y',bevel=.002,endfaces=True)
    collider(BASE,(side*.513,0,.205),(.032,.505,.040))
box('Rearward lower cross stretcher',(0,.170,.205),(1.030,.032,.032),bevel=.0018,endfaces=True)
collider(BASE,(0,.170,.205),(1.030,.032,.032))
# Corner blocks are set inside the top frame, with every side seated in a rail.
for sx in [-1,1]:
    for sy in [-1,1]:
        x=sx*.505;y=sy*.245;z=.711
        vs=[(x,y,z),(x-sx*.075,y,z),(x,y-sy*.075,z),(x,y,z+.024),(x-sx*.075,y,z+.024),(x,y-sy*.075,z+.024)]
        custom('Interior corner block',vs,[(0,2,1),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)],base_parts,bevel=.001)

# The drawer is an open box, not a solid block hidden behind the front.
drawer_specs=[('Drawer front',(0,-.284,.656),(.624,.020,.124),'X'),('Drawer bottom',(0,-.036,.603),(.600,.480,.009),'X'),('Drawer left side',(-.293,-.0335,.651),(.014,.485,.096),'Y'),('Drawer right side',(.293,-.0335,.651),(.014,.485,.096),'Y'),('Drawer rear',(0,.208,.651),(.600,.014,.096),'X')]
for name,loc,size,axis in drawer_specs:
    box(name,loc,size,drawer_parts,axis,bevel=.0012,wear=.45,endfaces=True);collider(DRAWER,loc,size)
box('Shallow raised drawer field',(0,-.2945,.656),(.552,.0035,.082),drawer_parts,bevel=.0015,tone=.97,wear=.55)
for x in [-.071,.071]:peg('Wood pull stand off',(x,-.309,.656),.006,.034,(math.pi/2,0,0),drawer_parts,wood_mat)
profile=[(-.086,.005),(-.083,.009),(-.075,.010),(-.065,.0085),(.065,.0085),(.075,.010),(.083,.009),(.086,.005)]
n=40;verts=[(x,-.326+r*math.cos(i*math.tau/n),.656+r*math.sin(i*math.tau/n)) for x,r in profile for i in range(n)]
faces=[tuple(range(n-1,-1,-1)),tuple((len(profile)-1)*n+i for i in range(n))]+[(k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i) for k in range(len(profile)-1) for i in range(n)]
custom('Turned wooden drawer pull',verts,faces,drawer_parts,bevel=.0006)
collider(DRAWER,(0,-.315,.656),(.174,.043,.022))
for x in [-.21,0,.21]:peg('Old rear drawer nail',(x,.215,.669),.0013,.0014,(math.pi/2,0,0),drawer_parts,iron)
for sx in [-1,1]:
    for z in [.625,.681]:peg('Drawer corner dowel',(sx*.3005,.17,z),.0022,.0018,(0,math.pi/2,0),drawer_parts,end_mat)
# Dark iron fasteners under the top are visible when inspecting the construction.
for x in [-.44,.44]:
    for y in [-.20,.20]:peg('Underside square nail',(x,y,.729),.0018,.002,(0,0,0),base_parts,iron)

def combine(group,name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in group:o.select_set(True)
    bpy.context.view_layer.objects.active=group[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join()
    o=bpy.context.object;o.name=name;s.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for uv in list(o.data.uv_layers):o.data.uv_layers.remove(uv)
    o.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.009);bpy.ops.object.mode_set(mode='OBJECT')
    tri=o.modifiers.new('Export triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
    return o
base=combine(base_parts,BASE);drawer=combine(drawer_parts,DRAWER)
drawer['opening_direction']='Blender -Y / UE +Y';drawer['opening_distance_cm']=23
report={'tabletop_size_cm':[120,64,77],'parts':{},'assembly_offsets_cm':[0,0,0],'drawer_open_offset_ue_cm':[0,23,0],'material_coordinates':'stored vertex attributes; stable after joining and baking'}
for o in [base,drawer]:
    cols=[]
    for i,(loc,size) in enumerate(collision_specs[o.name]):box('UCX_%s_%02d'%(o.name,i),loc,size,cols,bevel=0,mat=iron)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True)
    for c in cols:c.select_set(True)
    bpy.context.view_layer.objects.active=o
    bpy.ops.export_scene.fbx(filepath=str(OUT/(o.name+'.fbx')),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',add_leaf_bones=False,bake_anim=False)
    for c in cols:bpy.data.objects.remove(c,do_unlink=True)
    bm=bmesh.new();bm.from_mesh(o.data)
    report['parts'][o.name]={'triangles':len(o.data.polygons),'dimensions_cm':[v*100 for v in o.dimensions],'collision_hulls':len(cols),'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'material_slots':[m.name for m in o.data.materials],'uv_channels':len(o.data.uv_layers)};bm.free()

studio=bpy.data.collections.new('Preview studio - excluded from FBX');s.collection.children.link(studio)
def move_studio(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    studio.objects.link(o)
target=Vector((0,0,.43));bpy.ops.object.camera_add(location=(1.55,-1.90,1.38));cam=bpy.context.object;cam.name='Camera_OldWoodDesk';cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.80;cam.data.clip_start=.01;s.camera=cam;move_studio(cam)
floor=bpy.data.materials.new('Preview floor');floor.diffuse_color=(.07,.075,.08,1);floor.use_nodes=True;p=next(n for n in floor.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.07,.075,.08,1);p.inputs['Roughness'].default_value=.86
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));o=bpy.context.object;o.name='Preview floor';o.data.materials.append(floor);move_studio(o)
for name,pos,power,size,col in [('Key',(-1.2,-1.6,2.5),230,1.9,(1,.88,.72)),('Fill',(1.4,-.2,1.4),140,1.8,(.73,.84,1)),('Rim',(-.2,1.6,2),210,1.5,(1,.94,.82))]:
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.name='Preview '+name;o.data.energy=power;o.data.size=size;o.data.color=col;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler();move_studio(o)
s.world.use_nodes=True;next(n for n in s.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.12,.14,.17,1)
s.render.engine='CYCLES';s.cycles.samples=48;s.cycles.use_denoising=True;s.render.resolution_x=1400;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX';s.view_settings.exposure=-.4
s.render.image_settings.file_format='PNG';s.render.filepath=str(OUT/'OldWoodDesk_Preview.png');studio.hide_viewport=True
bpy.ops.object.select_all(action='DESELECT');base.select_set(True);drawer.select_set(True);bpy.context.view_layer.objects.active=base
for screen in bpy.data.screens:
    for a in screen.areas:
        if a.type=='VIEW_3D':
            v=a.spaces.active;v.region_3d.view_location=target;v.region_3d.view_distance=2.5;v.region_3d.view_rotation=cam.rotation_euler.to_quaternion();v.region_3d.view_perspective='ORTHO';v.clip_start=.002;v.shading.color_type='MATERIAL';v.overlay.show_overlays=False
if not bpy.app.background:
    for win in bpy.context.window_manager.windows:
        for a in win.screen.areas:
            if a.type=='VIEW_3D':
                with bpy.context.temp_override(window=win,area=a,region=next(r for r in a.regions if r.type=='WINDOW')):
                    bpy.ops.view3d.view_selected(use_all_regions=False)
                a.spaces.active.region_3d.update()
s.cursor.location=(0,0,0);bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'OldWoodDesk.blend'))
(OUT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
