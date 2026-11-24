"""Editable shop display counter, two independently animated rear glass leaves."""
import bpy
import math
from pathlib import Path
import random
import runpy
import json
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
SCENE = bpy.context.scene
assert not bpy.data.filepath and {o.name for o in SCENE.objects} <= {'Cube', 'Camera', 'Light'}, 'Use an empty or factory-start scene.'
for obj in list(SCENE.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for collection in list(SCENE.collection.children):
    if not collection.all_objects:
        SCENE.collection.children.unlink(collection)
SCENE.name = 'Old Shop · Glass Display Counter'
SCENE.unit_settings.system = 'METRIC'
randomizer = random.Random(40611)
M = runpy.run_path(str(ROOT/'make_materials.py'))['create_counter_materials']()


def group(name):
    collection = bpy.data.collections.new(name)
    SCENE.collection.children.link(collection)
    return collection


BODY = group('01 Counter body and fixed glazing')
LEFT = group('02 Left sliding glass door')
RIGHT = group('03 Right sliding glass door')
PROPS = group('04 Display dressing - removable')
STUDIO = group('05 Preview cameras and lights')


def basic_material(name, rgb, roughness=.62):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*rgb, 1)
    shader = next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (*rgb, 1)
    shader.inputs['Roughness'].default_value = roughness
    return material


def mesh_object(name, vertices, faces, material, collection, wear=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(M[material] if isinstance(material,str) else material)
    if wear is not None:
        attribute = mesh.color_attributes.new(name='Wear', type='FLOAT_COLOR', domain='POINT')
        attribute.data.foreach_set('color', [channel for value in wear for channel in (value,0.,0.,1.)])
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def bevel(obj, width, segments=2):
    if width <= 0:
        return obj
    chamfer = obj.modifiers.new('Rounded edge', 'BEVEL')
    chamfer.width = width
    chamfer.segments = segments
    chamfer.limit_method = 'ANGLE'
    chamfer.harden_normals = True
    if obj.data.color_attributes.get('Wear'):
        normal = obj.modifiers.new('Face-weighted normals', 'WEIGHTED_NORMAL')
        normal.keep_sharp = True
    return obj


def block(name, center, size, material, collection=BODY, radius=.0012, wear=.5, collision=False):
    cx,cy,cz = center
    a,b,c = [dimension/2 for dimension in size]
    vertices = [(cx+sx*a,cy+sy*b,cz+sz*c) for sz in (-1,1) for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1))]
    faces = [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    obj = mesh_object(name, vertices, faces, material, collection, [wear]*8 if wear is not None else None)
    if collision:
        obj['collision_half_m'] = list((a,b,c))
        obj['collision_center_m'] = list(center)
    return bevel(obj, radius)


def panel(name, cx, y, cz, width, height, thickness, outside, material='wood_red', collection=BODY, collision=False):
    """Solid wood board with an explicit narrow wear strip and quieter face center."""
    a,b = width/2,height/2
    edge = min(.009,width*.12,height*.12)
    near,far = y+outside*thickness/2,y-outside*thickness/2
    vertices=[]
    for x,z,depth in ((a,b,far),(a,b,near),(a-edge,b-edge,near)):
        vertices.extend([(cx+sx*x,depth,cz+sz*z) for sx,sz in ((-1,-1),(1,-1),(1,1),(-1,1))])
    quads = [tuple(reversed(range(4))), tuple(range(8,12))]
    for ring in range(2):
        for index in range(4):
            nxt=(index+1)%4
            quads.append((4*ring+index,4*ring+nxt,4*(ring+1)+nxt,4*(ring+1)+index))
    if outside>0:
        quads = [tuple(reversed(face)) for face in quads]
    obj=mesh_object(name,vertices,quads,material,collection,[.63]*8+[.08]*4)
    if collision:
        obj['collision_center_m']=[cx,y,cz]
        obj['collision_half_m']=[a,thickness/2,b]
    return bevel(obj,.0013)


def profile_mesh(name, center, rings, material, collection, axis='Z', sides=32, close_bottom=True, close_top=True):
    cx,cy,cz=center
    vertices=[]
    for radius, h in rings:
        for i in range(sides):
            angle=2*math.pi*i/sides
            u,v=radius*math.cos(angle),radius*math.sin(angle)
            vertices.append((cx+u,cy+v,cz+h) if axis=='Z' else (cx+u,cy+h,cz-v))
    faces=[]
    if close_bottom:
        faces.append(tuple(reversed(range(sides))))
    for j in range(len(rings)-1):
        for i in range(sides):
            n=(i+1)%sides
            faces.append((j*sides+i,j*sides+n,(j+1)*sides+n,(j+1)*sides+i))
    if close_top:
        faces.append(tuple(range(len(vertices)-sides,len(vertices))))
    obj=mesh_object(name,vertices,faces,material,collection,[.45]*len(vertices) if isinstance(material,str) and material not in ('glass','glass_edge') else None)
    for polygon in obj.data.polygons:
        polygon.use_smooth=len(polygon.vertices)==4
    return obj


def pane(name, center, size, collection=BODY, collision=False):
    obj=block(name,center,size,'glass',collection,.00045,None,collision)
    return obj


# Cabinet dimensions and hidden mechanical clearances are in meters.
W,D,H=1.960,.620,1.090
DISPLAY_Z=.738
INSIDE_BOTTOM=.759
INSIDE_TOP=1.066
BODY_TOP=.730

# Ground-height feet, plinth, lower shell, and an accessible back compartment.
for x in (-.919,0,.919):
    for y in (-.252,.252):
        block('Square floor foot',(x,y,.018),(.080,.086,.036),'wood_dark',radius=.003,wear=.90,collision=True)
        block('Foot contact plate',(x,y,.007),(.081,.089,.013),'metal',radius=.001,wear=.87)
block('Inset wooden plinth',(0.,0.,.054),(1.913,.568,.058),'wood_dark',radius=.002,wear=.86)
block('Storage floor with exposed plywood edge',(0,0,.106),(1.871,.544,.028),'wood_inside',radius=.0018,collision=True)
block('Full display platform',(0,0,.727),(1.929,.590,.036),'wood_inside',radius=.0015,wear=.36,collision=True)
block('Lining over the platform',(0,0,.747),(1.889,.552,.007),'wood_inside',radius=.0013,wear=.11)
block('Fixed center partition',(.203,.001,.411),(.024,.544,.592),'wood_dark',radius=.0012,wear=.35,collision=True)
block('Rear right compartment shelf',(.575,.009,.397),(.712,.524,.023),'wood_inside',radius=.0016,wear=.48,collision=True)
block('Shelf front edge',(.575,.275,.397),(.712,.009,.023),'wood_red',radius=.0007,wear=.56)

for side in (-1,1):
    x=side*.951
    for y in (-.285,.285):
        block('Lower wood stile',(x,y,.402),(.058,.050,.664),'wood_dark',radius=.0025,wear=.69)
        block('Folded corner guard front',(x,y+math.copysign(.025,y),.410),(.051,.0026,.624),'metal',radius=.0008,wear=.76)
        block('Folded corner guard side',(x+side*.029,y,.410),(.0026,.049,.624),'metal',radius=.0008,wear=.72)
    # Side wall backing and three readable wood divisions.
    block('Continuous lower side wall',(side*.955,0,.404),(.027,.541,.596),'wood_dark',radius=.0013,wear=.21,collision=True)
    for j in range(3):
        board=panel('Side field board',(j-1)*.179,side*.965,.403,.178,.574,.013,side)
        for v in board.data.vertices:
            v.co.x,v.co.y = v.co.y,-v.co.x
        board.data.update()
    for z,h in ((.104,.059),(.698,.059)):
        block('Side frame rail',(side*.964,0,z),(.030,.564,h),'wood_red',radius=.0017,wear=.73)

# Front advertising-free wood face. Hairline divisions, inset in the perimeter.
block('Unbroken inner front backing',(0,-.270,.407),(1.884,.018,.608),'wood_dark',radius=.001,wear=.19,collision=True)
for j in range(8):
    center=(j-3.5)*.2315
    panel(f'Front vertical field {j+1}',center,-.285,.408,.230,.572,.019,-1)
for y in (-.302,.302):
    block('Wood belt rail',(0,y,.724),(1.930,.030,.057),'wood_red',radius=.0024,wear=.74)
    block('Wood plinth rail',(0,y,.096),(1.930,.030,.058),'wood_red',radius=.0024,wear=.86)
    block('Bottom rubbed metal runner',(0,y+math.copysign(.003,y),.071),(1.924,.007,.009),'metal',radius=.001,wear=.86)
block('Front center joinery strip',(0,-.298,.409),(.027,.014,.569),'wood_dark',radius=.0012,wear=.55)


def pull(name,x,y,z,collection,direction=1,small=False):
    # Recess-like stamped cup surrounded by a rectangular rim. The moving leaf
    # pulls project only on its own rear face and clear the adjacent track.
    w,h,d=(.018,.064,.004) if small else (.027,.113,.005)
    block(name+' · dark well',(x,y,z),(w,d,h),'wood_dark',collection,.0018,.43)
    center_y=y+direction*.002
    for sx in (-1,1):
        block(name+' · vertical lip',(x+sx*w*.43,center_y,z),(w*.21,d*.80,h),'metal',collection,.0008,.82)
    for sz in (-1,1):
        block(name+' · cap lip',(x,center_y,z+sz*h*.44),(w*.78,d*.80,h*.17),'metal',collection,.0008,.75)


for j,(cx,width,y) in enumerate(((-.606,.643,.274),(-.100,.594,.294))):
    panel('Lower sliding storage wood leaf',cx,y,.410,width,.565,.023,1,collision=True)
    pull('Recessed lower pull',cx+(-.245 if j==0 else .229),y+.014,.416,BODY)
    for t in (-.17,0,.17):
        block('Lower rear hairline division',(cx+t,y+.0121,.416),(.0008,.0014,.530),'wood_dark',radius=.00025,wear=.28)

# Upper structure. Closed on the customer side, openable from the rear.
for x in (-.970,.970):
    for y in (-.301,.301):
        block('Upper corner angle',(x,y,.916),(.020,.020,.322),'metal',radius=.0010,wear=.83)
        block('Outer corner wood accent',(x-.007*math.copysign(1,x),y,.916),(.006,.022,.302),'wood_red',radius=.0008,wear=.65)
for z in (.759,1.075):
    for y in (-.301,.301):
        block('Long upper frame angle',(0,y,z),(1.960,.021,.018),'metal',radius=.0012,wear=.81)
    for x in (-.970,.970):
        block('Upper end frame angle',(x,0,z),(.020,.601,.018),'metal',radius=.0011,wear=.80)
block('Customer-side center mullion',(0,-.295,.915),(.014,.015,.310),'metal',radius=.0009,wear=.70)
for x in (-.480,.480):
    pane('Fixed customer display glass',(x,-.296,.917),(.944,.006,.301),collision=True)
for x in (-.969,.969):
    pane('Fixed side glazing',(x,0,.917),(.006,.574,.301),collision=True)
pane('Fixed top glass',(0,0,1.082),(1.926,.584,.008),collision=True)
for z in (.759,1.066):
    for y in (.249,.272,.295):
        block('Brass longitudinal track lip',(0,y,z),(1.910,.005,.006),'brass',radius=.00045,wear=.65)
    block('Rear track bearing rail',(0,.272,z), (1.918,.054,.006),'metal',radius=.00065,wear=.71)


DOORS={
    'left':{'collection':LEFT,'mesh':'SM_GlassDisplayCounter_DoorLeft','pivot_m':[-.470,.2605,.763],'travel_m':.922},
    'right':{'collection':RIGHT,'mesh':'SM_GlassDisplayCounter_DoorRight','pivot_m':[.470,.2835,.763],'travel_m':-.922},
}
door_width,door_height=.961,.302
for side,spec in DOORS.items():
    collection=spec['collection']
    cx,y,base=spec['pivot_m']
    pane(f'{side.title()} rear glass leaf',(cx,y,base+door_height/2),(door_width-.012,.0055,door_height-.013),collection)
    for sx in (-1,1):
        block('Sliding sash side',(cx+sx*(door_width/2-.004),y,base+door_height/2),(.009,.009,door_height),'metal',collection,.0006,.73)
    for sz in (0,1):
        block('Sliding sash horizontal',(cx,y,base+.004+sz*(door_height-.008)),(door_width,.010,.008),'metal',collection,.0006,.70)
    inside_edge = 1 if side=='left' else -1
    pull('Sliding door recessed handle',cx+inside_edge*(door_width/2-.028),y+.0046,base+.146,collection,small=True)
    spec['closed_ue_cm']=[cx*100,-y*100,base*100]
    spec['travel_cm']=spec['travel_m']*100
    spec['mesh_collision_extent_m']=[door_width/2,.005,door_height/2]


def screw(name,x,y,z,coll=BODY):
    profile_mesh(name,(x,y,z),[(.0033,0),(.0033,.0008),(.0023,.0014)],'brass',coll,axis='Y',sides=12)


for side in (-1,1):
    for z in (.091,.150,.676,.738,.770,1.068):
        screw('Corner fastener',side*.954,-.314,z)
        screw('Rear corner fastener',side*.954,.310,z)
for x in (-.857,-.498,-.167,.168,.493,.860):
    screw('Belt rail flush fastener',x,-.319,.724)

# The reference merchandise is a detachable dressing collection. The source
# remains a usable empty counter when that collection is hidden.
paper=basic_material('Stock · warm paper',(.59,.48,.32),.78)
ink=basic_material('Stock · dark ink',(.049,.034,.023),.81)
paper_white=basic_material('Stock · off-white ink',(.74,.66,.49),.76)
colors=[basic_material(f'Stock · carton color {i}',rgb,.77) for i,rgb in enumerate(((.36,.075,.038),(.12,.26,.10),(.38,.24,.067),(.08,.22,.30),(.45,.28,.18)))]


def letters(name,body,position,size,material,rotation=(math.pi/2,0,0)):
    data=bpy.data.curves.new(name,'FONT')
    data.body=body
    data.size=size
    data.align_x='CENTER'
    data.materials.append(material)
    obj=bpy.data.objects.new(name,data)
    PROPS.objects.link(obj)
    obj.location=position
    obj.rotation_euler=rotation


stems=('MALT','MINT','GINGER','SODA','TEA')
for row in range(2):
    for i in range(12):
        if row==1 and i in (3,8):
            continue
        x=(i-5.5)*.139+randomizer.uniform(-.009,.009)
        y=-.184+row*.166+randomizer.uniform(-.012,.012)
        h=randomizer.choice((.066,.079,.093))
        k=(i//2+row)%len(colors)
        center_z=.751+h/2
        block('Display product paper carton',(x,y,center_z),(.123,.133,h),colors[k],PROPS,.0014,None)
        block('Print field on carton',(x,y-.067,center_z),(.086,.0007,h*.58),paper,PROPS,.00055,None)
        block('Print field on carton top',(x,y,center_z+h/2+.00045),(.079,.076,.00065),paper,PROPS,.0006,None)
        block('Band of printed color',(x,y-.0676,center_z-h*.135),(.081,.0008,.006),colors[k],PROPS,.0002,None)
        letters('Product label',stems[k],(x,y-.0687,center_z-.004),.014,ink)
        letters('Small carton print','• SHOP •',(x,y-.0688,center_z-.018),.0064,ink)


def jar(name,x,y,r,h,color):
    z=1.086
    rings=[(r*.82,0),(r*.96,.005),(r,.015),(r,h*.77),(r*.93,h*.85),(r*.69,h*.93),(r*.69,h)]
    # Closed thin jar shell with four millimeters of glass, preserving hollow interior.
    profile_mesh(name+' · thick jar glass',(x,y,z),rings+[(a-.003,b) for a,b in reversed(rings[1:])],'glass',PROPS,sides=36)
    cap_material=basic_material(name+' · painted cap',color,.36)
    profile_mesh(name+' · screw cap',(x,y,z+h-.003),[(r*.71,0),(r*.75,.002),(r*.75,.015),(r*.70,.019)],cap_material,PROPS,sides=36)
    for n in range(52):
        theta=randomizer.uniform(0,math.tau)
        rr=(r-.016)*math.sqrt(randomizer.random())
        candy=(x+rr*math.cos(theta),y+rr*math.sin(theta),z+.012+randomizer.random()*h*.64)
        a=.0065+randomizer.random()*.0085
        profile_mesh(name+' · sweets',candy,[(a*.55,0),(a,.003),(a*.80,.012),(a*.45,.014)],colors[(n+2)%len(colors)],PROPS,sides=6)
    block(name+' · label',(x,y-r*.975,z+h*.42),(r*.95,.0027,h*.29),paper,PROPS,.0023,None)
    letters('Jar label','SWEETS',(x,y-r*.975-.0018,z+h*.41),r*.18,ink)


jar('Brick-red sweet jar',.710,.158,.078,.204,(.32,.045,.026))
jar('Amber sweet jar',.536,.177,.064,.182,(.45,.185,.032))
jar('Small sweet jar',.390,.113,.046,.116,(.37,.24,.047))
card=block('Small shop price stand',(.259,.143,1.151),(.086,.008,.128),colors[1],PROPS,.0018,None)
block('Stand foot',(.259,.160,1.090),(.086,.060,.008),'metal',PROPS,.0012,.5)
block('Printed stand insert',(.259,.138,1.153),(.063,.001,.097),paper_white,PROPS,.001,None)
letters('Shop sign title','SHOP',(.259,.1368,1.170),.018,ink)
letters('Shop sign small line','SWEETS',(.259,.1367,1.143),.011,ink)


def animate_leaf(side,spec,start,end):
    collection=spec['collection']
    pivot=bpy.data.objects.new(f'{side.title()} door · local X translation',None)
    collection.objects.link(pivot)
    pivot.empty_display_type='PLAIN_AXES'
    pivot.empty_display_size=.04
    pivot.location=spec['pivot_m']
    bpy.context.view_layer.update()
    for obj in list(collection.objects):
        if obj!=pivot:
            matrix=obj.matrix_world.copy()
            obj.parent=pivot
            obj.matrix_world=matrix
    for frame,alpha in ((1,0),(start,0),(start+16,1),(end-16,1),(end,0),(140,0)):
        pivot.location.x=spec['pivot_m'][0]+spec['travel_m']*alpha
        pivot.keyframe_insert(data_path='location',frame=frame)
    pivot['travel_x_m']=spec['travel_m']


animate_leaf('left',DOORS['left'],15,71)
animate_leaf('right',DOORS['right'],76,132)
SCENE.render.fps=30
SCENE.frame_start=1
SCENE.frame_end=140
for name,frame in [('Closed',1),('Left opens',15),('Left open',31),('Right opens',76),('Right open',92),('Both closed',132)]:
    SCENE.timeline_markers.new(name,frame=frame)
SCENE.frame_set(1)


def camera(name,position,point,ortho):
    data=bpy.data.cameras.new(name)
    obj=bpy.data.objects.new(name,data)
    STUDIO.objects.link(obj)
    obj.location=position
    obj.rotation_euler=(Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO'
    data.ortho_scale=ortho
    return obj


def light(name,position,target,energy,size,shape='DISK',width=None):
    data=bpy.data.lights.new(name,'AREA')
    obj=bpy.data.objects.new(name,data)
    STUDIO.objects.link(obj)
    obj.location=position
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    data.energy=energy
    data.shape=shape
    data.size=size
    if width is not None:
        data.size_y=width


ground=basic_material('Studio · charcoal matte',(.029,.024,.020),.83)
block('Ground outside deliverable',(0,0,-.0505),(200,200,.100),ground,STUDIO,0,None)
front=camera('01 Customer view',(-2.4,-4.8,2.1),(0,0,.58),2.52)
rear=camera('02 Staff side · open',(-2.0,4.7,1.70),(0,0,.58),2.48)
camera('03 Front elevation',(0,-5,.72),(0,0,.60),2.29)
light('Soft key',(-2.3,-3.1,3.4),(0,0,.55),530,3.0)
light('Top strip reflection',(.35,.3,3.5),(0,0,.7),345,2.75,'RECTANGLE',.51)
light('Warm side fill',(2.9,-.4,2.2),(0,0,.60),220,2.35)
light('Staff soft bounce',(-.2,3.5,2.5),(0,0,.65),275,2.6)
if SCENE.world is None:
    SCENE.world=bpy.data.worlds.new('Studio world')
SCENE.world.use_nodes=True
background=SCENE.world.node_tree.nodes.get('Background')
background.inputs[0].default_value=(.16,.147,.13,1)
background.inputs[1].default_value=.27
SCENE.render.engine='CYCLES'
SCENE.cycles.samples=32
SCENE.cycles.use_denoising=True
SCENE.cycles.transmission_bounces=10
SCENE.render.resolution_x=1560
SCENE.render.resolution_y=1080
SCENE.render.resolution_percentage=100
SCENE.render.image_settings.file_format='PNG'
SCENE.camera=front
SCENE.view_settings.view_transform='AgX'

for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.overlay.show_overlays=False
            space.shading.type='MATERIAL'
            view=space.region_3d
            view.view_location=(0,0,.583)
            view.view_distance=3.2
            view.view_rotation=front.rotation_euler.to_quaternion()
            view.view_perspective='ORTHO'
            area.tag_redraw()

assert max(spec['pivot_m'][1] for spec in DOORS.values())-min(spec['pivot_m'][1] for spec in DOORS.values())>.018
assert .920<abs(DOORS['left']['travel_m'])<.940
report={'body_collection':BODY.name,'dressings_collection':PROPS.name,'nominal_case_m':[W,D,H],
        'doors':{side:{key:value for key,value in spec.items() if key!='collection'} for side,spec in DOORS.items()},
        'door_width_m':door_width,'door_height_m':door_height,'body_mesh_objects':len(BODY.objects),
        'placement':'front -Y; sliding access +Y', 'door_tracks_spacing_mm':23.0}
(ROOT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'GlassDisplayCounter.blend'))
print('GLASS_COUNTER_SAVED',json.dumps(report),flush=True)
