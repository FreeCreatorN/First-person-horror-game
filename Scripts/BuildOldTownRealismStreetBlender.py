"""Refine actual street render meshes at their measured physical scale."""
import bpy,bmesh,json,hashlib,sys,math
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Scripts'))
from OldTownRealismRoles import role
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
OUT=ROOT/'SourceArt/OldTownRealism_20261012/Street';OUT.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
inp=read(WORK/'RealismStreetInput.json');groups=defaultdict(list)
need=('WindowReveal','WindowFrame','WindowSash','StreetLamp','StormDrain','CardboardBox')
for n,records in inp['component_records'].items():
    if 'MainHome' in n:continue
    for c in records:
        if not c.get('mesh') or not c.get('primitive_properties',{}).get('visible') or c.get('primitive_properties',{}).get('hidden_in_game'):continue
        if not any(k in c['mesh'] for k in need):continue
        scale=tuple(round(abs(v),6) for v in c['world_pose']['scale'])
        if min(scale)<.0001:continue
        groups[(c['mesh'],scale)].append((n,c))
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.
materials={};variants=[]
for (source,scale),members in sorted(groups.items()):
    summary=inp['meshes'][source];native=read(summary['geometry_file'])
    verts=[];faces=[];face_roles=[]
    for sec in native['sections']:
        mat=inp['materials'][sec['default_material']]['base_material'];r=role(mat)
        assert r,(source,mat)
        offset=len(verts);verts.extend([[v[i]*scale[i]/100 for i in range(3)] for v in sec['vertices_cm']])
        faces.extend([tuple(offset+j for j in sec['triangle_indices'][i:i+3]) for i in range(0,len(sec['triangle_indices']),3)])
        face_roles.extend([r]*sec['triangle_count'])
    roles=sorted(set(face_roles));key=hashlib.sha256(json.dumps([source,scale]).encode()).hexdigest()[:12]
    name='SM_R_Street_'+source.rsplit('/',1)[-1].split('.')[0].removeprefix('SM_OTS_')+'_'+key
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj)
    for r in roles:
        if r not in materials:
            m=bpy.data.materials.new(r);m.diffuse_color=(.26,.37,.27,1);materials[r]=m
        mesh.materials.append(materials[r])
    for poly,r in zip(mesh.polygons,face_roles):poly.material_index=roles.index(r)
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0000001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bmesh.ops.dissolve_limit(bm,angle_limit=.0001,verts=list(bm.verts),edges=list(bm.edges),delimit={'MATERIAL'})
    bm.to_mesh(mesh);bm.free();mesh.update()
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    # Architectural reveals get sub-millimetre highlights; props get 1 mm edges.
    bevel=obj.modifiers.new('PhysicalEdgeRadius','BEVEL');bevel.width=.0004 if 'Window' in source else .001
    bevel.segments=3;bevel.limit_method='ANGLE';bevel.angle_limit=math.radians(50);bevel.use_clamp_overlap=True
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    mesh=obj.data
    for poly in mesh.polygons:poly.use_smooth=True
    norm=obj.modifiers.new('WeightedPhysicalNormals','WEIGHTED_NORMAL');norm.keep_sharp=True;norm.weight=50
    bpy.ops.object.modifier_apply(modifier=norm.name)
    triangulate=obj.modifiers.new('RenderTriangles','TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    mesh=obj.data;mesh.calc_loop_triangles();mesh.calc_smooth_groups()
    uv=mesh.uv_layers.new(name='PhysicalUV_1m')
    for p in mesh.polygons:
        normal=p.normal;axis=max(range(3),key=lambda i:abs(normal[i]));axes=[i for i in range(3) if i!=axis]
        for li in p.loop_indices:
            v=mesh.vertices[mesh.loops[li].vertex_index].co;uv.data[li].uv=(v[axes[0]],v[axes[1]])
    mesh.calc_tangents(uvmap=uv.name)
    normals=[tuple(n.vector) for n in mesh.corner_normals]
    for vertex in mesh.vertices:
        for i in range(3):vertex.co[i]/=scale[i]
    mesh.update()
    converted=[]
    for v in normals:
        vv=[v[i]*scale[i] for i in range(3)];length=math.sqrt(sum(x*x for x in vv));converted.append(tuple(x/length for x in vv))
    mesh.normals_split_custom_set(converted);mesh.calc_loop_triangles();mesh.calc_tangents(uvmap=uv.name)
    actual=[[min(v.co[i]*100 for v in mesh.vertices) for i in range(3)],[max(v.co[i]*100 for v in mesh.vertices) for i in range(3)]]
    err=max(abs(x-y) for a,b in zip(actual,summary['bounds_cm']) for x,y in zip(a,b));assert err<.15,(name,actual,summary['bounds_cm'])
    recipe=OUT/(name+'.geometry.json');write(recipe,dict(vertices_cm=[[x*100 for x in v.co] for v in mesh.vertices],triangles=[list(t.vertices) for t in mesh.loop_triangles],material_roles=roles,physical_scale=scale,features=['measured physical edge rounding','weighted corner normals','one metre physical UV']))
    fbx=OUT/(name+'.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',use_space_transform=True,bake_space_transform=False,object_types={'MESH'},use_mesh_modifiers=True,mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,bake_anim=False)
    variants.append(dict(key=key,mesh_name=name,source_asset=source,source_asset_sha256=summary.get('sha256'),local_bounds_cm=actual,original_local_bounds_cm=summary['bounds_cm'],world_dimensions_cm=[summary['dimensions_cm'][i]*scale[i] for i in range(3)],component_scale=scale,fbx_file=fbx.name,source_file_sha256=sha(fbx),geometry_recipe_file=str(recipe),geometry_recipe_sha256=sha(recipe),material_roles=roles,triangles=len(mesh.loop_triangles),components=[dict(actor=n,component=c['name']) for n,c in members],source_actor_labels=sorted({n for n,c in members}),maximum_bounds_change_cm=err,kind='StreetMeasuredDetail'))
    obj.hide_set(True);obj.hide_render=True
    print('STREET_MODEL',name,len(members),len(mesh.loop_triangles),flush=True)
blend=OUT/'OldTownRealStreet.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
write(OUT/'ModelDataManifest.json',dict(status='COMPLETE',variants=variants,variant_count=len(variants),component_count=sum(len(v['components']) for v in variants),source_input_file=str(WORK/'RealismStreetInput.json'),source_input_sha256=sha(WORK/'RealismStreetInput.json'),source_script_sha256=sha(__file__),blend_file=str(blend),blend_sha256=sha(blend),no_original_files_modified=True))
print('STREET_MODELS_COMPLETE',len(variants),flush=True)
