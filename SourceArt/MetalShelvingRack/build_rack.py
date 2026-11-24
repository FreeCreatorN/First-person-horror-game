"""Build the reference shelf in meters. Run in a clean Blender scene."""
import bpy
import math
import json
from collections import Counter
from mathutils import Vector
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEVEL_COUNT = globals().get('RACK_LEVELS', 4)
assert LEVEL_COUNT in (4, 7)
low_rack = LEVEL_COUNT == 4
variant = '_4_Level_Low' if low_rack else ''
namespace = {}
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for group in list(scene.collection.children):
    if not group.all_objects:
        scene.collection.children.unlink(group)
bpy.data.orphans_purge(do_recursive=True)
exec(compile((ROOT / 'make_materials.py').read_text(encoding='utf-8'), 'make_materials.py', 'exec'), namespace)
materials = namespace['create_rack_materials']()
scene.name = 'Metal shelving rack · 4 levels, raised bottom' if low_rack else 'Metal shelving rack · 7 levels'
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1

def collection(name, parent):
    value = bpy.data.collections.new(name)
    parent.children.link(value)
    return value

asset = collection('METAL SHELVING RACK', scene.collection)
structure = collection('01  Perforated uprights', asset)
hardware = collection('05  Shelf connections and feet', asset)
bays = [collection(f'0{i+2}  Bay {i+1} — {LEVEL_COUNT} trays', asset) for i in range(3)]
studio = collection('STUDIO  Cameras and render lighting', scene.collection)

def mesh_object(name, vertices, faces, usage, group, wear=None, interior=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(materials[usage])
    if interior is not None:
        mesh.materials.append(materials['inner'])
        for poly, index in zip(mesh.polygons, interior):
            poly.material_index = index
    if usage in ('painted', 'inner'):
        attr = mesh.color_attributes.new(name='Wear', type='FLOAT_COLOR', domain='POINT')
        attr.data.foreach_set('color', [channel for w in (wear or [0.] * len(vertices)) for channel in (w, 0., 0., 1.)])
    obj = bpy.data.objects.new(name, mesh)
    group.objects.link(obj)
    return obj

def smooth_edges(obj, width, segments=2):
    bevel = obj.modifiers.new('Rounded sheet edges', 'BEVEL')
    bevel.width = width
    bevel.segments = segments
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = .27
    bevel.harden_normals = True
    return obj

def box(name, center, size, usage, group, bevel=0., wear=.6):
    x, y, z = center
    a, b, c = (value/2 for value in size)
    vertices = [(x+i*a, y+j*b, z+k*c) for k in (-1,1) for i,j in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    faces = [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    o = mesh_object(name, vertices, faces, usage, group, [wear]*8)
    return smooth_edges(o, bevel) if bevel else o

HEIGHT = 1.6 if low_rack else 2.19
PITCH = .792
XS = [(i-1.5)*PITCH for i in range(4)]
FRONT, BACK = -.263, .263
POST_WIDTH = .048
THICKNESS = .0023
LEVELS = [.492, .852, 1.212, 1.572] if low_rack else [.122 + i*.340 for i in range(7)]
SLOT_PITCH = .056

def slotted_strip(name, width, length, columns, map_point, slot_halfwidth, group):
    # Use common polygon borders at slot ends. A Solidify modifier puts real
    # steel walls on each cutout, including its rounded corners.
    boundaries = [-width/2, *[(l+r)/2 for l,r in zip(columns,columns[1:])], width/2]
    vertices, faces, wear = [], [], []
    ids = {}
    def point(x, z, value):
        key = (round(x,9), round(z,9))
        if key not in ids:
            ids[key] = len(vertices)
            vertices.append(map_point(x,z))
            wear.append(value)
        else:
            i = ids[key]
            wear[i] = max(wear[i], value)
        return ids[key]
    def patch(points):
        faces.append([point(*value) for value in points])
    half = .0112
    first_slot = .046
    slot_count = 1 + math.floor((length - first_slot - half - .014) / SLOT_PITCH)
    slot_centers = [first_slot + i*SLOT_PITCH for i in range(slot_count)]
    for col, center in enumerate(columns):
        left, right = boundaries[col:col+2]
        end_wear = .56 if col == 0 else .0
        right_wear = .56 if col == len(columns)-1 else .0
        radius = min(.00145, slot_halfwidth*.65)
        cap_x = slot_halfwidth-radius
        previous = 0.
        for cz in slot_centers:
            lower, upper = cz-half, cz+half
            curve = [(lower,cap_x)]
            for k in range(1,3):
                angle = -math.pi*.5 + k*math.pi/4
                curve.append((lower+radius+radius*math.sin(angle),cap_x+radius*math.cos(angle)))
            curve.append((upper-radius,slot_halfwidth))
            for k in range(1,3):
                angle = k*math.pi/4
                curve.append((upper-radius+radius*math.sin(angle),cap_x+radius*math.cos(angle)))
            patch([(left,previous,end_wear),(center-cap_x,previous,.67),(center+cap_x,previous,.67),(right,previous,right_wear),(right,lower,right_wear),(center+cap_x,lower,.67),(center-cap_x,lower,.67),(left,lower,end_wear)])
            for (a,aw),(b,bw) in zip(curve,curve[1:]):
                patch([(left,a,end_wear),(center-aw,a,.76),(center-bw,b,.76),(left,b,end_wear)])
                patch([(center+aw,a,.76),(right,a,right_wear),(right,b,right_wear),(center+bw,b,.76)])
            previous=upper
        patch([(left,previous,end_wear),(center-cap_x,previous,.67),(center+cap_x,previous,.67),(right,previous,right_wear),(right,length,.72),(left,length,.72)])
    obj = mesh_object(name,vertices,faces,'painted',group,wear)
    solid = obj.modifiers.new('Formed steel thickness', 'SOLIDIFY')
    solid.thickness = THICKNESS
    solid.offset = -1
    solid.use_even_offset = True
    smooth_edges(obj, .00019, 1)
    obj['slot_count'] = len(columns)*slot_count
    return obj

for column, x in enumerate(XS):
    for y, towards, label in [(FRONT,1,'front'),(BACK,-1,'back')]:
        name = f'Upright {column+1:02d} {label}'
        # At the back, reverse the face's Y winding so both forms turn inward.
        slots = [-.0115,.0115] if column in (1,2) else [0.]
        slotted_strip(name+' · face',POST_WIDTH,HEIGHT-.014,slots,
                      lambda u,z:(x+towards*u,y,z+.013),.0038,structure)
        for side in (-1,1):
            if (column==0 and side==1) or (column==3 and side==-1):
                # The inner return is still made of steel; the facing return
                # shows the punched holes in the oblique view.
                box(name+' · inner return',(x+side*(POST_WIDTH/2-.00115),y+towards*.016,HEIGHT/2+.005),
                    (THICKNESS,.033,HEIGHT-.018),'inner',structure,.00035,.65)
                continue
            inner_x=x+side*(POST_WIDTH/2-.00035)
            slotted_strip(name+f' · return {side:+}',.035,HEIGHT-.014,[0.],
                          lambda u,z:(inner_x,y+towards*.0174+side*u,z+.013),.0030,structure)
        box(name+' · black foot',(x,y+towards*.015,.007),(.055,.043,.014),'rubber',hardware,.0016)

def tray(name, center_x, z, width, group):
    a,b=width/2,.251
    # Four nested loops form a crisp tray skin and the steel returns under it.
    loops=[(a-.002,b-.002,z),(a,b,z-.0015),(a,b,z-.034),
           (a-.0022,b-.0022,z-.035),(a-.0040,b-.0040,z-.032),
           (a-.0022,b-.0022,z-.0041),(a-.003,b-.003,z-.0021)]
    v=[];decay=[]
    for j,(x,y,h) in enumerate(loops):
        datum=.82 if j in (1,2,3) else (.25 if j==0 else .35)
        for i,k in ((-1,-1),(1,-1),(1,1),(-1,1)):
            v.append((center_x+i*x,k*y,h));decay.append(datum)
    faces=[(0,1,2,3)];inside=[0]
    for j in range(len(loops)-1):
        for i in range(4):
            k=(i+1)%4
            faces.append((j*4+k,j*4+i,(j+1)*4+i,(j+1)*4+k));inside.append(0 if j<4 else 1)
    faces.append((27,26,25,24));inside.append(1)
    obj=mesh_object(name,v,faces,'painted',group,decay,inside)
    smooth_edges(obj,.00068,3)
    return obj

def bracket(name,x,y,z,sx,dy,group):
    # Stamped folded gusset, with the shoulder cut under the shelf lip.
    profile=[(0.,0.),(.057,0.),(.057,-.007),(.037,-.012),(.025,-.023),(.013,-.046),(0.,-.052)]
    v=[(x+sx*u,y+dy*d,z+h) for d in (0.,.0024) for u,h in profile]
    n=len(profile)
    f=[tuple(range(n)),tuple(reversed(range(n,n*2)))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    if sx*dy>0:f=[tuple(reversed(k)) for k in f]
    o=mesh_object(name,v,f,'inner',group,[.5]*(2*n))
    smooth_edges(o,.00055,2)

def cap(name,x,y,z,direction):
    # Recessed flange and a shallow circular bolt head.
    ring=[(.0049,0.),(.0049,.0007),(.0037,.0010),(.0035,.0020),(.0026,.00245)]
    n=12
    v=[(x+r*math.cos(2*math.pi*i/n),y+direction*d,z+r*math.sin(2*math.pi*i/n)) for r,d in ring for i in range(n)]
    f=[tuple(reversed(range(n)))]+[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(len(ring)-1) for i in range(n)]+[tuple(range(len(v)-n,len(v)))]
    if direction>0:f=[tuple(reversed(k)) for k in f]
    obj=mesh_object(name,v,f,'zinc',hardware)
    for p in obj.data.polygons:
        p.use_smooth=len(p.vertices)==4

for bay,group in enumerate(bays):
    mid=(XS[bay]+XS[bay+1])/2
    for level,z in enumerate(LEVELS,1):
        stem=f'Bay {bay+1} / shelf {level:02d}'
        tray(stem+' · folded tray',mid,z,PITCH-.041,group)
        for rib_x in (mid-.195,mid+.195):
            box(stem+' · undertray stiffener',(rib_x,0,z-.013),(.023,.465,.016),'inner',group,.0011,.49)
        for x,sx in ((XS[bay],1),(XS[bay+1],-1)):
            for y,dy in ((FRONT,1),(BACK,-1)):
                bracket(stem+' · hook gusset',x+sx*.019,y+dy*.016,z-.020,sx,dy,hardware)
                cap(stem+' · flange bolt',x+sx*.0125,y-dy*.0003,z-.019,-dy)

# Deliver the editable object collection plus isolated inspection lighting.
ground_mat=bpy.data.materials.new('Studio · charcoal')
ground_mat.diffuse_color=(.038,.035,.033,1)
profile=[(-35.,-.0008),(3.4,-.0008)]
for j in range(1,25):
    angle=math.pi*j/48
    profile.append((3.4+2.7*math.sin(angle),2.7*(1-math.cos(angle))-.0008))
profile.append((6.1,15.))
studio_vertices=[(x,y,z) for y,z in profile for x in (-35.,35.)]
studio_faces=[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(profile)-1)]
ground=mesh_object('Studio sweep',studio_vertices,studio_faces,'rubber',studio)
for polygon in ground.data.polygons:polygon.use_smooth=True
ground.data.materials.clear()
ground.data.materials.append(ground_mat)
ground_mat.use_nodes=True
ground_mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.033,.031,.029,1)
ground_mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.78

focus=Vector((0.,0.,.80 if low_rack else 1.083))
def camera(name,position,aim,scale):
    data=bpy.data.cameras.new(name)
    obj=bpy.data.objects.new(name,data)
    studio.objects.link(obj)
    obj.location=position
    obj.rotation_euler=(Vector(aim)-obj.location).to_track_quat('-Z','Y').to_euler()
    data.type='ORTHO'
    data.ortho_scale=scale
    data.clip_end=500
    return obj

front_height=.825 if low_rack else 1.10
front=camera('01 · Front',(0,-5.7,front_height),(0,0,front_height),2.83)
front.data.type='PERSP'
front.data.lens=68
hero=camera('02 · Left front 45°',(-3.55,-3.7,1.26 if low_rack else 1.62),focus,2.78)
hero.data.type='PERSP'
hero.data.lens=57
def area(name,pos,target,power,size,shape='DISK',size_y=None):
    d=bpy.data.lights.new(name,'AREA')
    obj=bpy.data.objects.new(name,d)
    studio.objects.link(obj)
    obj.location=pos
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    d.energy=power
    d.shape=shape
    d.size=size
    if size_y:d.size_y=size_y

area('Key softbox',(-3.6,-3.8,5.2),(0,0,.85),510,4.)
area('Front fill',(2.5,-4.,2.4),(0,0,1.),200,4.)
area('Top rim',(2.5,1.4,4.0),(0,0,1.35),490,3.)
scene.camera=hero
if scene.world is None:scene.world=bpy.data.worlds.new('Studio ambience')
scene.world.use_nodes=True
ambient=scene.world.node_tree.nodes.get('Background')
ambient.inputs[0].default_value=(.18,.175,.17,1)
ambient.inputs[1].default_value=.30
scene.render.engine='CYCLES'
scene.cycles.samples=24
scene.cycles.use_denoising=True
scene.render.resolution_x=1320
scene.render.resolution_y=1000 if low_rack else 1240
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
scene.render.filepath=str(ROOT/f'Metal_Shelving{variant}_45.png')

for win in bpy.context.window_manager.windows:
    for a in win.screen.areas:
        if a.type=='VIEW_3D':
            space=a.spaces.active
            sp=space.region_3d
            sp.view_location=focus
            sp.view_rotation=hero.rotation_euler.to_quaternion()
            sp.view_distance=4.4
            sp.view_perspective='ORTHO'
            space.overlay.show_overlays=False
            space.shading.type='MATERIAL'

parts=list(asset.all_objects)
vertices=[obj.matrix_world @ v.co for obj in parts for v in obj.data.vertices]
lo=[min(v[i] for v in vertices) for i in range(3)]
hi=[max(v[i] for v in vertices) for i in range(3)]
report={'dimensions_m':[round(b-a,5) for a,b in zip(lo,hi)],'uprights':8,'bay_count':3,'levels':len(LEVELS),
        'shelf_top_z_m':LEVELS,'post_centers_x_m':XS,'post_width_m':POST_WIDTH,
        'shelf_trays':sum(obj.name.endswith('folded tray') for obj in parts),
        'through_slots':sum(obj.get('slot_count',0) for obj in parts),'asset_mesh_objects':len(parts),
        'materials':{k:v.name for k,v in materials.items()},'studio_objects':len(studio.objects)}
assert report['shelf_trays']==3*LEVEL_COUNT and report['through_slots']>500
scene['asset_dimensions_m'] = report['dimensions_m']
(ROOT/f'model_report{variant}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'Metal_Shelving_Rack{variant}.blend'))
print('METAL_RACK_SAVED',json.dumps(report))
