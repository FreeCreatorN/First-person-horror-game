"""Export the exact MCP-authored leaves, their UV0, local pivots and UCX hulls."""
import bpy,bmesh,json,hashlib,shutil
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'Exports';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'ThreeSeatSofa.blend';sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'));assert R['budget_target_met']
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));S=bpy.data.scenes[R['source_scene']];bpy.context.window.scene=S
sources={key:S.objects[row['object']] for key,row in R['parts'].items()}
for o in sources.values():o.name='SOURCE_ONLY_'+o.name
def select(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
def ucx(name,verts):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]);me.update();o=bpy.data.objects.new(name,me);S.collection.objects.link(o);return o
assets=[]
for name,row in R['parts'].items():
    pivot=Vector(row['pivot_m']);o=bpy.data.objects.new(name,sources[name].data.copy());S.collection.objects.link(o);assert o.name==name
    select([o]);mod=o.modifiers.new('Deterministic triangulation','TRIANGULATE');mod.keep_custom_normals=True;bpy.ops.object.modifier_apply(modifier=mod.name)
    me=o.data;assert len(me.polygons)==row['triangles'],name
    bm=bmesh.new();bm.from_mesh(me);assert all(e.is_manifold for e in bm.edges),name;bm.free()
    hulls=[ucx(f'UCX_{name}_{i:02d}',[Vector(v)-pivot for v in h['vertices_m']]) for i,h in enumerate(R['collision_hulls'][name])]
    select([o,*hulls]);bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),object_types={'MESH'},use_selection=True,global_scale=1,apply_unit_scale=True,axis_forward='-Z',axis_up='Y',use_mesh_modifiers=False,bake_anim=False,mesh_smooth_type='FACE',path_mode='STRIP')
    assets.append({'name':name,'fbx':name+'.fbx','triangles':len(me.polygons),'collision_hulls':len(hulls),'slots':[m.name for m in me.materials],'pivot_m':list(pivot),'bounds_min_m':[min(v.co[a] for v in me.vertices) for a in range(3)],'bounds_max_m':[max(v.co[a] for v in me.vertices) for a in range(3)],'product':'ThreeSeatSofa','part':row['role']})
    print('EXPORTED',name,len(me.polygons),flush=True)
files={v for material in R['textures'].values() for v in material.values()}
for filename in files:shutil.copy2(ROOT/'Textures'/filename,OUT/filename)
result={'success':True,'source_sha256':sha,'assets':assets,'assemblies':R['assemblies'],'textures':R['textures'],'generic_materials':R['generic_materials'],'normal_convention':'OpenGL +Y','total_triangles':sum(a['triangles'] for a in assets),'product_count':1,'family_count':1,'product_triangles':R['product_triangles'],'expected_dimensions_m':R['expected_dimensions_m'],'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ('.png','.fbx')}}
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==sha
(OUT/'export_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('SOFA_EXPORT_COMPLETE',len(assets),result['total_triangles'],flush=True)
