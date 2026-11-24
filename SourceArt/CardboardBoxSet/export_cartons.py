"""Export the saved carton meshes in their own local component coordinates."""
import bpy,bmesh,json,hashlib,shutil
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'Exports';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'CardboardBoxSet.blend';sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));s=bpy.context.scene;assert s.name==R['source_scene']
objects={k:s.objects[v['object']] for k,v in R['parts'].items()}
for obj in objects.values():obj.name='SOURCE_ONLY_'+obj.name
def select(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
def hull(name,verts):
    faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    obj=bpy.data.objects.new(name,me);s.collection.objects.link(obj);return obj
assets=[]
for key,part in R['parts'].items():
    name=part['mesh'];pivot=Vector(part['pivot_m']);me=objects[key].data.copy()
    obj=bpy.data.objects.new(name,me);s.collection.objects.link(obj);assert obj.name==name
    select([obj]);mod=obj.modifiers.new('Deterministic triangles','TRIANGULATE');mod.keep_custom_normals=True;bpy.ops.object.modifier_apply(modifier=mod.name)
    me=obj.data;assert len(me.polygons)==part['triangles']
    bm=bmesh.new();bm.from_mesh(me);assert all(e.is_manifold for e in bm.edges),key;bm.free()
    ucx=[hull(f'UCX_{name}_{i:02d}',[Vector(v)-pivot for v in data['vertices_m']]) for i,data in enumerate(R['collision_hulls'][key])]
    assert ucx,key;select([obj,*ucx])
    bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),object_types={'MESH'},use_selection=True,
        global_scale=1,apply_unit_scale=True,axis_forward='-Z',axis_up='Y',use_mesh_modifiers=False,
        bake_anim=False,mesh_smooth_type='FACE',path_mode='STRIP')
    assets.append({'name':name,'fbx':name+'.fbx','triangles':len(me.polygons),'collision_hulls':len(ucx),
        'slots':[m.name for m in me.materials],'pivot_m':list(pivot),
        'bounds_min_m':[min(v.co[i] for v in me.vertices) for i in range(3)],
        'bounds_max_m':[max(v.co[i] for v in me.vertices) for i in range(3)]})
    print('EXPORTED',name,len(me.polygons),flush=True)
textures={}
for key in ['Standard','Damaged','Fruit','Water','Noodles','Tape','Edge']:
    sourcekey='Plain' if key=='Edge' else key
    textures[key]={'base_color':f'T_Carton_{sourcekey}_BaseColor.png','orm':f'T_Carton_{sourcekey}_ORM.png'}
textures['normal']='T_Carton_Shared_Normal.png'
for path in (ROOT/'Textures').glob('*.png'):shutil.copy2(path,OUT/path.name)
result={'success':True,'source_sha256':sha,'assets':assets,'textures':textures,'variant_count':8,
    'variant_triangles':R['variant_triangles'],'total_triangles':sum(a['triangles'] for a in assets),
    'normal_convention':'OpenGL +Y','flaps':R['flaps'],
    'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ('.png','.fbx')}}
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==sha
(OUT/'export_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('EXPORT_COMPLETE',len(assets),result['total_triangles'],flush=True)
