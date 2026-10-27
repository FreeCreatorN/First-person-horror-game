"""Import independent FBX detail meshes, retaining the source BodySetup."""
import json,math,hashlib,itertools,re
from pathlib import Path
import unreal
import OldTownRealismMaterials as pbr
ROOT=Path(unreal.Paths.project_dir()).resolve()
ASSET=pbr.ASSET
assets=unreal.EditorAssetLibrary
def high_precision(mesh):
    assert mesh.get_path_name().startswith(ASSET+'/')
    sub=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) or unreal.StaticMeshEditorSubsystem()
    settings=sub.get_lod_build_settings(mesh,0)
    settings.set_editor_property('use_full_precision_u_vs',True)
    settings.set_editor_property('use_high_precision_tangent_basis',True)
    settings.set_editor_property('remove_degenerates',False)
    sub.set_lod_build_settings(mesh,0,settings)
def bounds(m):
    b=m.get_bounds();return [[float(getattr(b.origin,k)-getattr(b.box_extent,k)) for k in ('x','y','z')],[float(getattr(b.origin,k)+getattr(b.box_extent,k)) for k in ('x','y','z')]]
def imported(path,name):
    folder=ASSET+'/Meshes/ImportData';assets.make_directory(folder)
    source_sha=pbr.sha(path)
    package=folder+'/'+name
    # Keep prior imports for traceability and import repaired source geometry
    # into a fresh cache package rather than reading an obsolete FBX result.
    if assets.does_asset_exist(package) and assets.get_metadata_tag(assets.load_asset(package),'RealismFBXSourceSHA')!=source_sha:
        name=name+'_'+source_sha[:12]
        package=folder+'/'+name
    if assets.does_asset_exist(package):
        m=assets.load_asset(package)
        assert assets.get_metadata_tag(m,'RealismFBXSourceSHA')==source_sha,package
        high_precision(m);pbr.save(m)
        return m
    ui=unreal.FbxImportUI()
    for k,v in dict(import_mesh=True,import_as_skeletal=False,import_animations=False,import_materials=False,import_textures=False,mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():ui.set_editor_property(k,v)
    data=ui.get_editor_property('static_mesh_import_data')
    for k,v in dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,remove_degenerates=False,convert_scene=True,convert_scene_unit=True,import_uniform_scale=1.).items():data.set_editor_property(k,v)
    data.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    task=unreal.AssetImportTask()
    for k,v in dict(filename=str(path),destination_path=folder,destination_name=name,automated=True,replace_existing=False,save=False,options=ui,factory=unreal.FbxFactory()).items():task.set_editor_property(k,v)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task]);m=assets.load_asset(package);assert isinstance(m,unreal.StaticMesh),package
    assets.set_metadata_tag(m,'RealismFBXSourceSHA',source_sha);high_precision(m);pbr.save(m)
    return m
def axis_probe(path):
    expected=[[-2,-7,-13],[3,11,17]]
    m=imported(path,'SM_R_AxisProbe');actual=bounds(m);choices=[]
    for order in itertools.permutations(range(3)):
        for signs in itertools.product((-1,1),repeat=3):
            b=[[min(signs[i]*expected[0][order[i]],signs[i]*expected[1][order[i]]) for i in range(3)],[max(signs[i]*expected[0][order[i]],signs[i]*expected[1][order[i]]) for i in range(3)]]
            error=sum(abs(actual[j][i]-b[j][i]) for i in range(3) for j in range(2))
            choices.append((error,order,signs))
    error,order,signs=min(choices);assert error<.005,(actual,choices[:4])
    return dict(import_order=list(order),import_signs=list(signs),error_cm=error,actual_bounds=actual,authored_bounds=expected,probe=pbr.save(m))
def dynamic(m,source_model=False):
    opt=unreal.GeometryScriptCopyMeshFromAssetOptions()
    for k,v in dict(apply_build_settings=True,request_tangents=True,use_build_scale=True).items():opt.set_editor_property(k,v)
    lod=unreal.GeometryScriptMeshReadLOD();lod.set_editor_property('lod_type',unreal.GeometryScriptLODType.SOURCE_MODEL if source_model else unreal.GeometryScriptLODType.RENDER_DATA);lod.set_editor_property('lod_index',0)
    d,out=unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(m,unreal.DynamicMesh(),opt,lod,True)
    assert out==unreal.GeometryScriptOutcomePins.SUCCESS
    return d
def undo_axes(d,axes):
    order=axes['import_order'];signs=axes['import_signs']
    # Rotations are composed from transformed X and Y bases; the residual
    # handedness change is the local Z scale. This transforms normal overlays
    # and reverses orientation on a reflection through the native mesh API.
    basis=[]
    for i in range(3):
        vec=[0.,0.,0.];vec[order[i]]=float(signs[i]);basis.append(unreal.Vector(*vec))
    rot=unreal.MathLibrary.make_rot_from_xy(basis[0],basis[1])
    actual_z=unreal.MathLibrary.get_up_vector(rot)
    sign_z=1. if unreal.MathLibrary.dot_vector_vector(actual_z,basis[2])>.9 else -1.
    t=unreal.Transform(rotation=rot,scale=unreal.Vector(1,1,sign_z))
    return unreal.GeometryScript_MeshTransforms.transform_mesh(d,t,True)
def copy_to_source_clone(d,source,path,materials):
    folder,name=path.rsplit('/',1);assets.make_directory(folder)
    out=assets.load_asset(path) if assets.does_asset_exist(path) else assets.duplicate_asset(source.get_path_name().split('.')[0],path)
    assert isinstance(out,unreal.StaticMesh)
    settings=unreal.GeometryScriptCopyMeshToAssetOptions()
    for k,v in dict(enable_recompute_normals=False,enable_recompute_tangents=False,enable_remove_degenerates=False,use_build_scale=True,replace_materials=True,apply_nanite_settings=False,emit_transaction=False,defer_mesh_post_edit_change=False).items():settings.set_editor_property(k,v)
    settings.set_editor_property('new_materials',materials)
    settings.set_editor_property('generate_lightmap_u_vs',unreal.GeometryScriptGenerateLightmapUVOptions.DO_NOT_GENERATE_LIGHTMAP_U_VS)
    lod=unreal.GeometryScriptMeshWriteLOD();lod.set_editor_property('lod_index',0)
    _,ok=unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(d,out,settings,lod,True);assert ok==unreal.GeometryScriptOutcomePins.SUCCESS
    high_precision(out)
    return out
def build_variant(entry,base,axes,category='Furniture'):
    path=base/entry.get('fbx_file',entry.get('file',''))
    assert pbr.sha(path)==entry.get('source_file_sha256',entry.get('fbx_sha256')),path
    name=entry.get('mesh_name',entry.get('name'))
    import_name=name+'_Import_NoDegenerateMerge' if entry.get('native_no_degenerate_merge') else name+'_Import'
    if entry.get('native_import_cache_suffix'):
        suffix=entry['native_import_cache_suffix']
        assert re.fullmatch(r'[A-Za-z0-9_]+',suffix),suffix
        import_name=name+'_Import_'+suffix
    fb=imported(path,import_name);d=undo_axes(dynamic(fb,entry.get('native_source_model_read',False) or entry.get('native_uv_chart_separation',False)),axes)
    if entry.get('native_uv_chart_separation'):
        _,id_list,_=unreal.GeometryScript_MeshQueries.get_all_triangle_i_ds(d)
        setter=unreal.GeometryScript_UVs.set_mesh_triangle_u_vs
        scale=entry.get('native_physical_scale')
        if scale is None:scale=[float(v)/100 for v in entry['world_dimensions_cm']]
        assert len(scale)==3 and all(math.isfinite(v) and v>0 for v in scale)
        for tid in unreal.GeometryScript_List.convert_index_list_to_array(id_list):
            valid,a,b,c=unreal.GeometryScript_MeshQueries.get_triangle_positions(d,tid);assert valid
            points=[[float(getattr(v,k))*scale[i] for i,k in enumerate(('x','y','z'))] for v in (a,b,c)]
            ab=[points[1][i]-points[0][i] for i in range(3)];ac=[points[2][i]-points[0][i] for i in range(3)]
            cross=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
            axis=max(range(3),key=lambda i:abs(cross[i]));assert abs(cross[axis])>0,tid
            plane=((1,2),(0,2),(0,1))[axis];phase=(.03,.01,.0)[axis]
            triangle=unreal.GeometryScriptUVTriangle()
            for i,p in enumerate(points):
                triangle.set_editor_property('uv'+str(i),unreal.Vector2D(p[plane[0]]/100+phase,1-p[plane[1]]/100-phase))
            d,ok=setter(d,0,tid,triangle,True);assert ok,tid
    source=assets.load_asset(entry.get('source_asset','/Engine/BasicShapes/Cube.Cube'));assert source
    declared_roles=entry.get('material_roles',entry.get('material_slots'))
    fb_slots=[str(s.material_slot_name) for s in fb.static_materials]
    # Do not assume the FBX material order follows the source role list.
    imported_roles=[next(r for r in declared_roles if r.lower()==n.lower()) for n in fb_slots]
    target=ASSET+'/Meshes/'+category+'/'+name
    old_manifest=base/'BeforeSolids/ModelDataManifest.json.bak'
    if old_manifest.exists():
        previous=json.loads(old_manifest.read_text(encoding='utf-8-sig'))
        original=next(v for v in previous['variants'] if v['mesh_name']==name)
        old_import=assets.load_asset(ASSET+'/Meshes/ImportData/'+name+'_Import')
        assert old_import and assets.get_metadata_tag(old_import,'RealismFBXSourceSHA')==original.get('source_file_sha256',original.get('fbx_sha256'))
        roles=[next(r for r in declared_roles if r.lower()==str(s.material_slot_name).lower())
               for s in old_import.static_materials]
        assert set(roles)==set(declared_roles),(name,roles,declared_roles)
    else:
        roles=list(imported_roles)
    # Boolean union can leave a role with no exposed triangles. Preserve the
    # complete saved slot layout and remap by material identity, including gaps.
    new_mats=[pbr.get(r,'UV') for r in roles]
    if imported_roles!=roles:
        remap=next((getattr(unreal.GeometryScript_Materials,n) for n in
            ('remap_to_new_material_i_ds_by_material','remap_to_new_material_ids_by_material')
            if hasattr(unreal.GeometryScript_Materials,n)),None)
        assert remap,dir(unreal.GeometryScript_Materials)
        d=remap(d,[pbr.get(r,'UV') for r in imported_roles],new_mats,-1)
    out=copy_to_source_clone(d,source,target,new_mats)
    actual=bounds(out);expected=entry['local_bounds_cm']
    assert max(abs(a-b) for aa,bb in zip(actual,expected) for a,b in zip(aa,bb))<.03,(name,actual,expected)
    assets.set_metadata_tag(out,'RealismSourceAsset',source.get_path_name())
    assets.set_metadata_tag(out,'RealismFBXSourceSHA',pbr.sha(path))
    triangles=sum(len(unreal.ProceduralMeshLibrary.get_section_from_static_mesh(out,0,i)[1])//3 for i in range(out.get_num_sections(0)))
    row=pbr.save(out);row.update(key=entry.get('key'),category=category,source_asset=source.get_path_name(),fbx_source=str(path),fbx_sha256=pbr.sha(path),material_roles=roles,imported_used_material_roles=imported_roles,saved_material_slot_layout_preserved=True,actual_local_bounds_cm=actual,authored_local_bounds_cm=expected,triangles=triangles,source_actor_labels=entry.get('source_actor_labels',[]))
    return out,row
