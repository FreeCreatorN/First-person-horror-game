"""Shared baked atlas and nine independent UE-ready meshes. Source is read-only."""
import bpy,bmesh,json,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'Exports';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'IceCreamFreezer.blend'
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
SOURCE_SHA=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
SIZE=2048
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
assert s.name==R['source_scene']
deps=bpy.context.evaluated_depsgraph_get()
def select(obs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:o.select_set(True)
    bpy.context.view_layer.objects.active=obs[0]
copies=[]
keys=list(R['parts'])
for idx,key in enumerate(keys):
    for src in bpy.data.collections[R['parts'][key]['collection']].objects:
        if src.type!='MESH':continue
        me=bpy.data.meshes.new_from_object(src.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
        att=me.attributes.new(name='ExportPart',type='INT',domain='FACE')
        for v in att.data:v.value=idx
        o=bpy.data.objects.new('Bake '+src.name,me);s.collection.objects.link(o);o.matrix_world=src.matrix_world
        copies.append(o)
bpy.context.view_layer.update();select(copies);bpy.ops.object.join()
atlas=bpy.context.object;atlas.name='Shared atlas temporary'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
tr=atlas.modifiers.new('Deterministic triangles','TRIANGULATE');tr.keep_custom_normals=True
bpy.ops.object.modifier_apply(modifier=tr.name)
assert len(atlas.data.polygons)==R['total_triangles'],(len(atlas.data.polygons),R['total_triangles'])
atlas.data.uv_layers.new(name='UVMap')
atlas.data.uv_layers.active_index=len(atlas.data.uv_layers)-1
atlas.data.uv_layers.active.active_render=True
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.05,island_margin=.004,area_weight=.40,scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
for o in list(s.objects):
    if o!=atlas:
        o.hide_render=True
        # Consolidated source objects already use the canonical SM_* names.
        # Reserve those exact names for FBX render nodes, so UCX matching works.
        if o.name.startswith('SM_IceCreamFreezer_'):o.name='SOURCE_ONLY_'+o.name
s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=1
def connect_socket(tree,src,dst):
    if src.is_linked:tree.links.new(src.links[0].from_socket,dst)
    else:dst.default_value=src.default_value
def bake(name,orm):
    image=bpy.data.images.new(name,width=SIZE,height=SIZE,alpha=False)
    image.colorspace_settings.name='Non-Color' if orm else 'sRGB'
    for mat in atlas.data.materials:
        t=mat.node_tree;p=next(n for n in t.nodes if n.type=='BSDF_PRINCIPLED')
        out=next(n for n in t.nodes if n.type=='OUTPUT_MATERIAL')
        emit=t.nodes.new('ShaderNodeEmission')
        if orm:
            rgb=t.nodes.new('ShaderNodeCombineColor');rgb.inputs['Red'].default_value=1
            connect_socket(t,p.inputs['Roughness'],rgb.inputs['Green']);connect_socket(t,p.inputs['Metallic'],rgb.inputs['Blue'])
            t.links.new(rgb.outputs[0],emit.inputs[0])
        else:connect_socket(t,p.inputs['Base Color'],emit.inputs[0])
        t.links.new(emit.outputs[0],out.inputs['Surface'])
        node=t.nodes.new('ShaderNodeTexImage');node.image=image;t.nodes.active=node
    assert bpy.ops.object.bake(type='EMIT',margin=6,margin_type='EXTEND',use_clear=True)=={'FINISHED'}
    image.filepath_raw=str(OUT/name);image.file_format='PNG';image.save()
bake('T_IceCreamFreezer_BaseColor.png',False)
bake('T_IceCreamFreezer_ORM.png',True)
groupids=[v.value for v in atlas.data.attributes['ExportPart'].data]
glassids={i for i,m in enumerate(atlas.data.materials) if 'glass' in m.name.casefold()}
uv=atlas.data.uv_layers.active
def ucx(name,center,half):
    v=[tuple(center[i]+sg[i]*half[i] for i in range(3)) for sg in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    f=[(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(name,me);s.collection.objects.link(o);return o
assets=[]
for idx,key in enumerate(keys):
    spec=R['parts'][key];name=spec['mesh'];pivot=Vector(spec['pivot_m'])
    polys=[p for p in atlas.data.polygons if groupids[p.index]==idx]
    oldindices=sorted({v for p in polys for v in p.vertices});mapping={v:i for i,v in enumerate(oldindices)}
    me=bpy.data.meshes.new(name);me.from_pydata([atlas.data.vertices[i].co-pivot for i in oldindices],[],[tuple(mapping[v] for v in p.vertices) for p in polys]);me.update()
    uvnew=me.uv_layers.new(name='UVMap')
    for old,new in zip(polys,me.polygons):
        new.use_smooth=old.use_smooth
        for a,b in zip(old.loop_indices,new.loop_indices):uvnew.data[b].uv=uv.data[a].uv
    uses=sorted({int(p.material_index in glassids) for p in polys})
    slots=[('M_Freezer_Opaque','M_Freezer_Glass')[i] for i in uses]
    for slot in slots:
        mat=bpy.data.materials.get(slot) or bpy.data.materials.new(slot);me.materials.append(mat)
    for old,new in zip(polys,me.polygons):new.material_index=uses.index(int(old.material_index in glassids))
    assert all(-.00001<=u<=1.00001 for d in uvnew.data for u in d.uv),key
    bm=bmesh.new();bm.from_mesh(me);assert all(e.is_manifold for e in bm.edges),key;bm.free()
    obj=bpy.data.objects.new(name,me);s.collection.objects.link(obj)
    assert obj.name==name,('FBX render node must match its UCX prefix',obj.name,name)
    boxes=R['collision_boxes'][key]
    hulls=[ucx(f'UCX_{name}_{i:02d}',Vector(b['center_m'])-pivot,b['half_m']) for i,b in enumerate(boxes)]
    assert hulls,key
    select([obj,*hulls])
    bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),object_types={'MESH'},use_selection=True,
        global_scale=1,apply_unit_scale=True,axis_forward='-Z',axis_up='Y',use_mesh_modifiers=False,
        bake_anim=False,mesh_smooth_type='FACE',path_mode='STRIP')
    row={'name':name,'fbx':name+'.fbx','triangles':len(me.polygons),'collision_hulls':len(hulls),'slots':slots,'pivot_m':list(pivot),
        'bounds_min_m':[min(v.co[i] for v in me.vertices) for i in range(3)],'bounds_max_m':[max(v.co[i] for v in me.vertices) for i in range(3)]}
    assets.append(row);print('EXPORTED_PART',key,row['triangles'],flush=True)
out={'success':True,'source_sha256':SOURCE_SHA,'baked_resolution':SIZE,'assets':assets,'doors':R['doors'],
     'total_triangles':sum(a['triangles'] for a in assets),'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ('.fbx','.png')}}
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
(OUT/'export_report.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print('EXPORT_COMPLETE',out['total_triangles'],flush=True)

