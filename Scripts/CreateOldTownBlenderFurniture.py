"""Original old Chinese residential furniture, authored in Blender via MCP.

Execute setup(), build_bed(), build_table_chair(), build_wardrobe(), export(),
and render_preview() separately. Metres in Blender, centimetres in manifest.
Existing scene objects are preserved. Each semantic asset is one mesh.
"""
import bpy
import bmesh
import math
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(r'D:\UE\Project\HorrorGame\SourceArt\OldTownModular_20261002')
COLLECTION = 'OTS_OriginalFurniture_20261002'
ASSETS = []
PARTS = []
MATS = {}

def setup():
    global COL
    ROOT.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    if COLLECTION in bpy.data.collections:
        raise RuntimeError('Furniture collection already exists; preserve it.')
    COL = bpy.data.collections.new(COLLECTION)
    scene.collection.children.link(COL)
    materials()

def move_collection(obj):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    COL.objects.link(obj)

def material(name, color, rough=0.72, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = next(node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = rough
    shader.inputs['Metallic'].default_value = metallic
    MATS[name] = mat
    return mat

def materials():
    material('Wood', (.22, .105, .042), .72)
    material('WoodPanel', (.29, .155, .072), .76)
    material('Metal', (.16, .14, .09), .54, .68)
    material('Cloth', (.34, .42, .33), .93)
    material('ClothPillow', (.68, .63, .48), .96)
    material('ClothPiping', (.18, .25, .19), .90)

def finish_part(obj, mat, bevel=0.003):
    move_collection(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(MATS[mat])
    if bevel:
        mod = obj.modifiers.new('Soft worn edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        bpy.ops.object.modifier_apply(modifier=mod.name)
    PARTS.append(obj)
    return obj

def box(name, loc, dims, mat='Wood', bevel=.003):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    return finish_part(obj, mat, bevel)

def rod(name, a, b, radius=.009, mat='Metal'):
    delta = Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius,
                                      depth=delta.length, location=(Vector(a)+Vector(b))/2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
    return finish_part(obj, mat, .001)

def path(name, points, radius, mat):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    line = curve.splines.new('POLY')
    line.points.add(len(points)-1)
    for point, pos in zip(line.points, points):
        point.co = (*pos, 1)
    obj = bpy.data.objects.new(name, curve)
    COL.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    return finish_part(bpy.context.object, mat, 0)

def asset(name, destination, group, origin=(0,0,0), display=(0,0,0)):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in PARTS:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = PARTS[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.context.scene.cursor.location = origin
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.location += Vector(display)
    ASSETS.append({'obj': obj, 'name': name, 'destination': destination,
                   'group': group, 'origin': list(origin), 'display': list(display)})
    PARTS.clear()
    return obj

def build_bed():
    display = (-1.65, 0, 0)
    for x in (-.635, .635):
        for y in (-1.025, 1.025):
            height = .96 if y > 0 else .64
            box('Bed square post', (x,y,height/2), (.075,.075,height))
        box('Bed side rail', (x,0,.385), (.055,2.04,.15))
    for y in (-1.025,1.025):
        box('Bed end rail', (0,y,.385), (1.25,.055,.15))
        top = .90 if y>0 else .58
        box('Bed upper rail', (0,y,top), (1.23,.068,.065))
        box('Bed panel lower rail', (0,y,.525), (1.23,.055,.055))
        for x in (-.395,0,.395):
            h = .31 if y>0 else .02
            box('Bed recessed board', (x,y,.69 if y>0 else .548),
                (.375,.027,h), 'WoodPanel', .002)
    for y in [-.89+i*.16 for i in range(12)]:
        box('Bed mattress support slat', (0,y,.43), (1.20,.13,.025),'Wood',.002)
    for x in (-.635,.635):
        for y in (-1.025,1.025):
            box('Post small end cap',(x,y,.965 if y>0 else .645),(.086,.086,.02))
    asset('SM_OTS_Blender_BedFrame', '/Game/Yastar/Meshes/Bed','Bed',display=display)
    box('Old cotton mattress', (0,0,.515), (1.20,1.98,.15),'Cloth',.035)
    for z in (.465,.563):
        pts = [(-.567,-.955,z),(.567,-.955,z),(.579,-.943,z),
               (.579,.943,z),(.567,.955,z),(-.567,.955,z),
               (-.579,.943,z),(-.579,-.943,z),(-.567,-.955,z)]
        path('Mattress sewn piping',pts,.003,'ClothPiping')
    asset('SM_OTS_Blender_BedMattress','/Game/Yastar/Meshes/Bed','Bed',
          origin=(0,0,.44),display=display)
    obj = box('Soft cotton pillow', (0,.69,.648),(.58,.37,.105),'ClothPillow',.045)
    for v in obj.data.vertices:
        v.co.z += .004*math.sin(v.co.x*18)*math.cos(v.co.y*16)
    pts=[(-.252,.535,.646),(.252,.535,.646),(.271,.55,.646),
         (.271,.83,.646),(.252,.845,.646),(-.252,.845,.646),
         (-.271,.83,.646),(-.271,.55,.646),(-.252,.535,.646)]
    path('Pillow stitched edge',pts,.0025,'ClothPillow')
    pillow=asset('SM_OTS_Blender_BedPillow','/Game/Yastar/Meshes/Bed','Bed',
                 origin=(0,.69,.59),display=display)
    lowest=min(v.co.z for v in pillow.data.vertices)
    for vertex in pillow.data.vertices:
        vertex.co.z-=lowest
    pillow.data.update()

def tapered_leg(name,x,y,z,h,top,bottom,mat='Wood'):
    verts=[]
    for zz,size in ((z,bottom),(z+h,top)):
        verts.extend([(x+xx*size/2,y+yy*size/2,zz)
                      for xx,yy in ((-1,-1),(1,-1),(1,1),(-1,1))])
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],[(0,3,2,1),(4,5,6,7),(0,1,5,4),
                            (1,2,6,5),(2,3,7,6),(3,0,4,7)])
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    COL.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    return finish_part(obj,mat,.003)

def build_table_chair():
    for x in (-.515,.515):
        for y in (-.295,.295):
            tapered_leg('Table tapered leg',x,y,0,.72,.065,.041)
        box('Table side apron',(x,0,.645),(.045,.58,.12))
        box('Table low side stretcher',(x,0,.20),(.028,.58,.038))
    for y in (-.295,.295):
        box('Table end apron',(0,y,.645),(1.00,.045,.12))
    for i in range(5):
        box('Table solid plank',( -.488+i*.244,0,.7325),(.242,.78,.055),
            'WoodPanel' if i%2 else 'Wood',.0025)
    box('Table drawer face',(0,-.334,.640),(.46,.025,.105),'WoodPanel',.004)
    for x in (-.060,.060):
        rod('Drawer pull fixing',(x,-.348,.640),(x,-.367,.640),.005)
    rod('Drawer pull grip',(-.06,-.367,.640),(.06,-.367,.640),.005)
    asset('SM_OTS_Blender_OldWoodTable','/Game/Yastar/Meshes/Table','Table',display=(.20,-.80,0))
    for x in (-.18,.18):
        tapered_leg('Chair front leg',x,-.18,0,.455,.045,.03)
        tapered_leg('Chair back leg',x,.18,0,.91,.04,.03)
        box('Chair side apron',(x,0,.400),(.032,.37,.080))
        box('Chair side stretcher',(x,0,.17),(.028,.37,.028))
    for y in (-.18,.18):
        box('Chair end apron',(0,y,.4),(.36,.033,.08))
        box('Chair horizontal rung',(0,y,.20),(.36,.026,.026))
    for y in (-.16,-.053,.053,.16):
        box('Chair seat plank',(0,y,.45),(.43,.103,.04),'WoodPanel',.003)
    for x in (-.10,0,.10):
        box('Chair vertical back slat',(x,.18,.69),(.057,.025,.36),'WoodPanel',.002)
    for z in (.51,.895):
        box('Chair back cross rail',(0,.18,z),(.43,.045,.050),'Wood',.005)
    asset('SM_OTS_Blender_OldWoodChair','/Game/Yastar/Meshes/Furniture','Chair',display=(1.18,-1.14,0))

def build_wardrobe():
    display=(1.28,.70,0)
    for x in (-.515,.515):
        for y in (-.215,.215):
            box('Wardrobe short foot',(x,y,.065),(.080,.080,.13),'Wood',.004)
    for x in (-.57,.57):
        box('Wardrobe structural side',(x,0,1.00),(.040,.58,1.78))
    for z in (.12,1.89):
        box('Wardrobe bottom or crown',(0,0,z),(1.18,.60,.06))
    box('Wardrobe full back',(0,.27,1.01),(1.10,.025,1.74),'WoodPanel',.002)
    box('Wardrobe center partition',(0,.00,1.0),(.022,.53,1.71),'WoodPanel',.002)
    for x in (-.278,.278):
        for z in (.48,1.24):
            box('Wardrobe usable shelf',(x,0,z),(.532,.52,.025),'WoodPanel',.002)
    box('Wardrobe base moulding',(0,-.306,.16),(1.21,.025,.07))
    box('Wardrobe top moulding',(0,-.306,1.875),(1.21,.025,.07))
    asset('SM_OTS_Blender_WardrobeCase','/Game/Yastar/Meshes/hOUSE','Wardrobe',display=display)
    for side in (-1,1):
        center=side*.285
        for x in (center-.255,center+.255):
            box('Door vertical stile',(x,-.310,1.015),(.05,.041,1.69))
        for z in (.19,1.00,1.84):
            box('Door cross rail',(center,-.310,z),(.51,.041,.058))
        for z,h in ((.605,.755),(1.42,.755)):
            box('Door recessed panel',(center,-.307,z),(.452,.018,h),'WoodPanel',.002)
        knobx=side*.075
        rod('Wardrobe handle mounts',(knobx,-.332,1.03),(knobx,-.356,1.03),.009)
        rod('Wardrobe handle grip',(knobx,-.356,.987),(knobx,-.356,1.073),.008)
        hingex=side*.558
        for z in (.40,1.62):
            box('Door hinge leaf',(side*.548,-.334,z),(.027,.007,.065),'Metal',.001)
            rod('Door hinge pin',(hingex,-.330,z-.035),(hingex,-.330,z+.035),.007)
        name='SM_OTS_Blender_WardrobeDoor'+('L' if side<0 else 'R')
        asset(name,'/Game/Yastar/Meshes/hOUSE','Wardrobe',
              origin=(hingex,-.330,.16),display=display)

def export():
    ROOT.mkdir(parents=True,exist_ok=True)
    output=[]
    material_info={n:{'color':list(m.diffuse_color[:3]),
                        'roughness':next(node for node in m.node_tree.nodes if node.type=='BSDF_PRINCIPLED').inputs['Roughness'].default_value,
                        'metallic':next(node for node in m.node_tree.nodes if node.type=='BSDF_PRINCIPLED').inputs['Metallic'].default_value}
                   for n,m in MATS.items()}
    for record in ASSETS:
        obj=record['obj']
        obj['ots_semantic_group']=record['group']
        obj['ots_assembly_offset_cm']=[v*100 for v in record['origin']]
        saved=obj.location.copy()
        obj.location=(0,0,0)
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
        file=record['name']+'.fbx'
        bpy.ops.export_scene.fbx(filepath=str(ROOT/file),use_selection=True,
            object_types={'MESH'},global_scale=1.0,apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',use_mesh_modifiers=True,
            use_triangles=True,bake_anim=False,add_leaf_bones=False,
            axis_forward='-Y',axis_up='Z',bake_space_transform=False,
            path_mode='AUTO',use_custom_props=False)
        corners=[Vector(v) for v in obj.bound_box]
        bounds=[[round(min(v[i] for v in corners)*100,4) for i in range(3)],
                [round(max(v[i] for v in corners)*100,4) for i in range(3)]]
        output.append({k:v for k,v in record.items() if k not in ('obj','origin','display')})
        output[-1].update(file=file,dimensions_cm=[round(v*100,4) for v in obj.dimensions],
            offset_cm=[round(v*100,4) for v in record['origin']],
            bounds_cm=bounds,material_slots=[m.name for m in obj.data.materials],
            vertices=len(obj.data.vertices),triangles=sum(len(p.vertices)-2 for p in obj.data.polygons),
            pivot='hinge_bottom' if 'WardrobeDoor' in obj.name else 'floor_or_support',
            source='Original geometry authored through Blender MCP')
        obj.location=saved
    manifest={'version':1,'authoring_units':'meters','import_units':'centimeters',
        'fbx_axis_forward':'-Y','fbx_axis_up':'Z',
        'authoring_axes':{'X':'width','Y':'depth, front is -Y','Z':'up'},
        'assembly_note':'Offsets are Blender authoring XYZ centimetres; verify Unreal FBX axis conversion before placement.',
        'materials':material_info,'assets':output}
    (ROOT/'ImportManifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'OldTown_OriginalFurniture.blend'))
    print(json.dumps({'manifest':str(ROOT/'ImportManifest.json'),'assets':len(output),'files':[a['file'] for a in output]}))

def render_preview():
    scene=bpy.data.scenes.new('OTS_Furniture_Preview')
    scene.collection.children.link(COL)
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1280
    scene.render.resolution_y=900
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    world=bpy.data.worlds.new('OTS_PreviewWorld')
    world.use_nodes=True
    bg=next(n for n in world.node_tree.nodes if n.type=='BACKGROUND')
    bg.inputs['Color'].default_value=(.28,.32,.38,1)
    bg.inputs['Strength'].default_value=.32
    scene.world=world
    groundmat=bpy.data.materials.new('OTS_PreviewFloor')
    groundmat.diffuse_color=(.32,.29,.24,1)
    groundmat.use_nodes=True
    shader=next(n for n in groundmat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value=(.32,.29,.24,1)
    shader.inputs['Roughness'].default_value=.85
    mesh=bpy.data.meshes.new('OTS_PreviewFloor')
    mesh.from_pydata([(-200,-200,-.012),(200,-200,-.012),(200,200,-.012),(-200,200,-.012)],[],[(0,1,2,3)])
    floor=bpy.data.objects.new('OTS_PreviewFloor',mesh)
    floor.data.materials.append(groundmat)
    scene.collection.objects.link(floor)
    camera_data=bpy.data.cameras.new('OTS_PreviewCamera')
    camera=bpy.data.objects.new('OTS_PreviewCamera',camera_data)
    scene.collection.objects.link(camera)
    camera.location=(-5.4,-6.8,4.3)
    camera.rotation_euler=(Vector((-.10,0,.68))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.type='ORTHO'
    camera_data.ortho_scale=6.4
    scene.camera=camera
    for name,loc,power,size in [('Key',(-3,-4,6),1000,5),('Fill',(4,-2,4),750,4),('Rim',(0,4,5),900,3)]:
        light_data=bpy.data.lights.new('OTS_'+name,'AREA')
        light_data.energy=power
        light_data.shape='DISK'
        light_data.size=size
        light=bpy.data.objects.new('OTS_'+name,light_data)
        scene.collection.objects.link(light)
        light.location=loc
        light.rotation_euler=(Vector((0,0,.8))-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(ROOT/'Furniture_Preview.png')
    bpy.ops.render.render(write_still=True,scene=scene.name)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'OldTown_OriginalFurniture.blend'))
    print('CPU preview rendered: '+scene.render.filepath)

if __name__ == '__main__':
    setup()
    build_bed()
    build_table_chair()
    build_wardrobe()
    export()
    render_preview()
