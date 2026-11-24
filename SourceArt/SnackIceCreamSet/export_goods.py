"""Export all independent goods leaves, preserving UV0 and component origins."""
import bpy,bmesh,json,hashlib,shutil
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'Exports';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'SnackIceCreamSet.blend';sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
assert R['budget_target_met']
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));s=bpy.context.scene;assert s.name==R['source_scene']
sources={key:s.objects[row['object']] for key,row in R['parts'].items()}
for obj in sources.values():obj.name='SOURCE_ONLY_'+obj.name
def select(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
def ucx(name,verts):
    faces=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();obj=bpy.data.objects.new(name,me);s.collection.objects.link(obj);return obj
assets=[]
for key,row in R['parts'].items():
    name=row['mesh'];pivot=Vector(row['pivot_m']);obj=bpy.data.objects.new(name,sources[key].data.copy());s.collection.objects.link(obj);assert obj.name==name
    select([obj]);mod=obj.modifiers.new('Deterministic triangulation','TRIANGULATE');mod.keep_custom_normals=True;bpy.ops.object.modifier_apply(modifier=mod.name)
    me=obj.data;assert len(me.polygons)==row['triangles']
    bm=bmesh.new();bm.from_mesh(me);assert all(e.is_manifold for e in bm.edges),name;bm.free()
    hulls=[ucx(f'UCX_{name}_{i:02d}',[Vector(v)-pivot for v in data['vertices_m']]) for i,data in enumerate(R['collision_hulls'][key])]
    assert hulls;select([obj,*hulls])
    bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),object_types={'MESH'},use_selection=True,global_scale=1,apply_unit_scale=True,
        axis_forward='-Z',axis_up='Y',use_mesh_modifiers=False,bake_anim=False,mesh_smooth_type='FACE',path_mode='STRIP')
    assets.append({'name':name,'fbx':name+'.fbx','triangles':len(me.polygons),'collision_hulls':len(hulls),'slots':[mat.name for mat in me.materials],
        'pivot_m':list(pivot),'bounds_min_m':[min(v.co[a] for v in me.vertices) for a in range(3)],
        'bounds_max_m':[max(v.co[a] for v in me.vertices) for a in range(3)],'product':row['product'],'part':row['part']})
    print('EXPORTED',name,len(me.polygons),flush=True)
files={R['textures']['normal']}
for value in R['textures'].values():
    if isinstance(value,dict):files.update(value.values())
for filename in files:shutil.copy2(ROOT/'Textures'/filename,OUT/filename)
result={'success':True,'source_sha256':sha,'assets':assets,'assemblies':R['assemblies'],'textures':R['textures'],
    'generic_materials':R['generic_materials'],'normal_convention':'OpenGL +Y','total_triangles':sum(a['triangles'] for a in assets),
    'product_count':R['product_count'],'family_count':R['family_count'],'product_triangles':R['product_triangles'],
    'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ('.png','.fbx')}}
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==sha
(OUT/'export_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('GOODS_EXPORT_COMPLETE',len(assets),result['total_triangles'],flush=True)
