"""Move only overlapping planar face patches of independent mesh clones.

Read RenderData rather than SourceModel so scan coordinates match the mesh
actually drawn. Disconnection retains normal, tangent, UV and material overlays;
only patch positions change, by at most 0.1 cm. Shared source assets stay intact.
"""
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
import unreal
from OldTownCoplanarScan import scan_components, _cross, _dot

DEFAULT_ROOT='/Game/CodexGenerated/OldTown/SurfaceSeparation_20261009/Meshes'
VERSION='render-planar-patches-v1'


def _xyz(v):return [float(getattr(v,k)) for k in ('x','y','z')]
def _length(v):return math.sqrt(_dot(v,v))
def _sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def _package(obj):return obj.get_path_name().split('.')[0]


def _file(obj):
    p=_package(obj)
    if p.startswith('/Game/'):return Path(unreal.Paths.project_dir()).resolve()/('Content/'+p[6:]+'.uasset')
    if p.startswith('/Engine/'):return Path(unreal.Paths.engine_content_dir()).resolve()/(p[8:]+'.uasset')
    return None


def _geometry(dynamic):
    q=unreal.GeometryScript_MeshQueries;l=unreal.GeometryScript_List
    _,positions,_=q.get_all_vertex_positions(dynamic,False)
    vertices=[_xyz(v) for v in l.convert_vector_list_to_array(positions)]
    _,indices,_=q.get_all_triangle_indices(dynamic,False)
    triples=[tuple(int(getattr(t,k)) for k in ('x','y','z')) for t in l.convert_triangle_list_to_array(indices)]
    return vertices,triples


def _normal(vertices,t):
    a,b,c=[vertices[i] for i in t]
    v=_cross([b[i]-a[i] for i in range(3)],[c[i]-a[i] for i in range(3)])
    size=_length(v)
    return tuple(x/size for x in v) if size>1e-10 else None


def _patches(vertices,triangles):
    """Union adjacent coplanar triangles into their original quad/face patch."""
    valid=[i for i,t in enumerate(triangles) if min(t)>=0 and _normal(vertices,t)]
    parents={i:i for i in valid};normals={i:_normal(vertices,triangles[i]) for i in valid}
    edges=defaultdict(list);signatures={}
    duplicate_ids=set()
    for tid in valid:
        signature=tuple(sorted(tuple(round(v,5) for v in vertices[i]) for i in triangles[tid]))
        if signature in signatures:duplicate_ids.add(tid)
        else:signatures[signature]=tid
        for j in range(3):edges[tuple(sorted((triangles[tid][j],triangles[tid][(j+1)%3])))].append(tid)
    def find(i):
        while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
        return i
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parents[b]=a
    for edge,tids in edges.items():
        a,b=[vertices[i] for i in edge];along=[b[k]-a[k] for k in range(3)]
        for ai in range(len(tids)):
            for bi in range(ai+1,len(tids)):
                x,y=tids[ai],tids[bi]
                if x in duplicate_ids or y in duplicate_ids:continue
                if _dot(normals[x],normals[y])<1.-1e-10:continue
                # True neighbouring triangles lie on opposite sides of their
                # common edge. Overlapping triangles must remain separate.
                thirdx=next(i for i in triangles[x] if i not in edge)
                thirdy=next(i for i in triangles[y] if i not in edge)
                sx=_dot(_cross(along,[vertices[thirdx][k]-a[k] for k in range(3)]),normals[x])
                sy=_dot(_cross(along,[vertices[thirdy][k]-a[k] for k in range(3)]),normals[x])
                if sx*sy< -1e-10:union(x,y)
    result=defaultdict(list)
    for tid in valid:result[find(tid)].append(tid)
    return list(result.values())


def _records(vertices,triangles,patches,offsets=None):
    result=[]
    for i,patch in enumerate(patches):
        d=(offsets or {}).get(i,(0.,0.,0.))
        points=[[[vertices[v][k]+d[k] for k in range(3)] for v in triangles[tid]] for tid in patch]
        result.append(dict(id='patch%d'%i,actor='patch%d'%i,component='face',triangles=points,visible=True))
    return result


def plan_mesh_offsets(vertices,triangles,max_offset_cm=.1,minimum_area_cm2=1.,plane_tolerance_cm=.03):
    """Pure geometry plan, independent of Unreal calls and source-model IDs."""
    assert 0<max_offset_cm<=.1
    assert math.isfinite(plane_tolerance_cm) and plane_tolerance_cm>0.
    minimum_separation_cm=plane_tolerance_cm+.001
    patches=_patches(vertices,triangles)
    rows=_records(vertices,triangles,patches)
    initial=scan_components(rows,plane_tolerance_cm=plane_tolerance_cm,min_overlap_area_cm2=minimum_area_cm2,
        cell_size_cm=20.,include_internal=True,classify_buried=False)
    # Rare non-manifold overlaps can be joined through another triangle. Split
    # only those bad patches into their individual triangles before solving.
    bad={int(q['components'][0][5:]) for q in initial['overlaps'] if q['intra_component']}
    if bad:
        patches=[part for i,p in enumerate(patches) for part in ([[t] for t in p] if i in bad else [p])]
        rows=_records(vertices,triangles,patches)
    if not initial['overlaps']:
        return dict(passed=True,initial_overlap_count=0,remaining_overlap_count=0,patch_count=len(patches),
            moved_patches=[],maximum_vertex_offset_cm=0.,triangle_count=sum(min(t)>=0 for t in triangles),
            plane_tolerance_cm=plane_tolerance_cm,minimum_required_separation_cm=minimum_separation_cm)
    # Include near planes that a later +/-0.1cm adjustment could bring together.
    potential=scan_components(rows,plane_tolerance_cm=minimum_separation_cm+2*max_offset_cm,
        min_overlap_area_cm2=minimum_area_cm2,cell_size_cm=20.,classify_buried=False)
    neighbours=defaultdict(list)
    for q in potential['overlaps']:
        a,b=[int(s[5:]) for s in q['components']]
        if a==b:raise AssertionError('Unsplit self-overlap in planar patch.')
        n=q['normal']
        pa=vertices[triangles[patches[a][0]][0]];pb=vertices[triangles[patches[b][0]][0]]
        difference=_dot(n,pa)-_dot(n,pb)
        neighbours[a].append((b,n,difference));neighbours[b].append((a,n,-difference))
    offsets={}
    palette=[0.,.034,-.034,.068,-.068,.1,-.1,.05,-.05,.085,-.085,.017,-.017]
    palette=[x for x in palette if abs(x)<=max_offset_cm+1e-8]
    for i in sorted(neighbours,key=lambda j:(-len(neighbours[j]),j)):
        n=_normal(vertices,triangles[patches[i][0]])
        selected=None
        for value in palette:
            delta=tuple(value*x for x in n)
            if all(abs(gap+_dot(normal,[delta[k]-offsets[other][k] for k in range(3)]))>minimum_separation_cm
                   for other,normal,gap in neighbours[i] if other in offsets):
                selected=delta;break
        assert selected is not None,'Cannot separate patch %d within %.3fcm'%(i,max_offset_cm)
        offsets[i]=selected
    after=scan_components(_records(vertices,triangles,patches,offsets),
        plane_tolerance_cm=plane_tolerance_cm,min_overlap_area_cm2=minimum_area_cm2,cell_size_cm=20.,
        include_internal=True,classify_buried=False)
    assert not after['overlaps'],'Planned offsets leave coplanar faces: '+str(after['overlap_count'])
    moved=[dict(patch=i,triangle_ids=patches[i],delta_cm=list(d),vertex_offset_cm=_length(d))
           for i,d in offsets.items() if _length(d)>1e-8]
    return dict(passed=True,initial_overlap_count=initial['overlap_count'],remaining_overlap_count=0,
        patch_count=len(patches),moved_patches=moved,maximum_vertex_offset_cm=max((_length(r['delta_cm']) for r in moved),default=0.),
        triangle_count=sum(min(t)>=0 for t in triangles),minimum_area_cm2=minimum_area_cm2,
        plane_tolerance_cm=plane_tolerance_cm,minimum_required_separation_cm=minimum_separation_cm,
        original_scan_stats=initial['stats'])


def clone_and_separate(mesh,constraints=None,assetroot=DEFAULT_ROOT,max_offset_cm=.1,minimum_area_cm2=1.,plane_tolerance_cm=.03):
    """Return ``(new_mesh, report)`` after genuine RenderData face separation.

    ``constraints`` may document caller findings, but face IDs are recalculated
    from RenderData so no source-model/section indexing mismatch is possible.
    Nothing is assigned to actors here. Caller validates actual routes/collision.
    """
    assert isinstance(mesh,unreal.StaticMesh)
    assert assetroot.startswith('/Game/CodexGenerated/') and '..' not in assetroot
    original_file=_file(mesh);original_sha=_sha(original_file) if original_file and original_file.is_file() else None
    options=unreal.GeometryScriptCopyMeshFromAssetOptions()
    options.set_editor_property('apply_build_settings',True)
    options.set_editor_property('request_tangents',True)
    options.set_editor_property('use_build_scale',True)
    lod=unreal.GeometryScriptMeshReadLOD()
    lod.set_editor_property('lod_type',unreal.GeometryScriptLODType.RENDER_DATA)
    lod.set_editor_property('lod_index',0)
    dynamic,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(mesh,unreal.DynamicMesh(),options,lod,True)
    assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS,mesh.get_path_name()
    vertices,triangles=_geometry(dynamic)
    plan=plan_mesh_offsets(vertices,triangles,max_offset_cm,minimum_area_cm2,plane_tolerance_cm)
    if not plan['moved_patches']:
        return mesh,dict(plan,original_asset=mesh.get_path_name(),asset=mesh.get_path_name(),changed=False)
    for row in plan['moved_patches']:
        _,selection=unreal.GeometryScript_MeshSelection.convert_index_array_to_mesh_selection(dynamic,row['triangle_ids'],unreal.GeometryScriptMeshSelectionType.TRIANGLES)
        unreal.GeometryScript_MeshModeling.apply_mesh_disconnect_faces(dynamic,selection,True)
        unreal.GeometryScript_MeshTransforms.translate_mesh_selection(dynamic,selection,unreal.Vector(*row['delta_cm']))
    final_vertices,final_triangles=_geometry(dynamic)
    actual=scan_components([dict(id='final',vertices=final_vertices,triangles=[t for t in final_triangles if min(t)>=0])],
        plane_tolerance_cm=plane_tolerance_cm,min_overlap_area_cm2=minimum_area_cm2,cell_size_cm=20.,
        include_internal=True,classify_buried=False)
    assert actual['overlap_count']==0,'Actual DynamicMesh still overlaps: '+mesh.get_path_name()
    encoded=json.dumps([mesh.get_path_name(),VERSION,original_sha,max_offset_cm,minimum_area_cm2,plane_tolerance_cm],separators=(',',':')).encode('utf-8')
    suffix=hashlib.sha256(encoded).hexdigest()[:12]
    name=re.sub('[^A-Za-z0-9_]+','_',mesh.get_name())[:64]+'_Separated_'+suffix
    package=assetroot.rstrip('/')+'/'+name
    assets=unreal.EditorAssetLibrary;assets.make_directory(assetroot)
    clone=unreal.load_asset(package)
    if clone:
        assert assets.get_metadata_tag(clone,'CodexSurfaceMeshSource')==mesh.get_path_name(),package
        assert assets.get_metadata_tag(clone,'CodexSurfaceMeshVersion')==VERSION,package
    else:
        clone=assets.duplicate_asset(_package(mesh),package)
    assert isinstance(clone,unreal.StaticMesh),package
    settings=unreal.GeometryScriptCopyMeshToAssetOptions()
    for key,value in dict(enable_recompute_normals=False,enable_recompute_tangents=False,
        enable_remove_degenerates=False,use_build_scale=True,replace_materials=False,
        apply_nanite_settings=False,emit_transaction=False,defer_mesh_post_edit_change=False).items():settings.set_editor_property(key,value)
    settings.set_editor_property('generate_lightmap_u_vs',unreal.GeometryScriptGenerateLightmapUVOptions.DO_NOT_GENERATE_LIGHTMAP_U_VS)
    target=unreal.GeometryScriptMeshWriteLOD();target.set_editor_property('lod_index',0)
    _,outcome=unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(dynamic,clone,settings,target,True)
    assert outcome==unreal.GeometryScriptOutcomePins.SUCCESS,package
    assets.set_metadata_tag(clone,'CodexSurfaceMeshSource',mesh.get_path_name())
    assets.set_metadata_tag(clone,'CodexSurfaceMeshVersion',VERSION)
    assets.set_metadata_tag(clone,'CodexSurfaceMeshOriginalSHA256',original_sha or '')
    assert assets.save_loaded_asset(clone,False),package
    assert original_sha is None or _sha(original_file)==original_sha,'Shared original mesh was modified.'
    file=_file(clone)
    return clone,dict(plan,original_asset=mesh.get_path_name(),original_file=str(original_file),original_sha256=original_sha,
        asset=clone.get_path_name(),file=str(file),sha256=_sha(file),changed=True,
        actual_dynamic_overlap_count=actual['overlap_count'],source_lod='RENDER_DATA 0',
        simple_collision_policy='BodySetup duplicated unchanged; no collision generation or geometry setter called.',
        complex_collision_policy='Complex mesh triangles follow the <=0.1cm render change; caller must validate actual routes.',
        external_constraint_count=len(constraints or []))
