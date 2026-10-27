"""Import prescribed closed soft goods into new packages; replace only 222 meshes."""
import json,sys,traceback
from copy import deepcopy
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import OldTownRealismImport as importer
import OldTownRealismMaterials as pbr
from ApplyOldTownRealismRefinement import stable_actor,light_inventory
from AuditOldTownRealismAppearance import collision_signature
from FinalizeOldTownRealism import native_closed_solid,native_frame_proof,native_physical_uv
from VerifyOldTownSoftGoodsRefinement import verify_baseline,binary_face_proof,source_variant_proof,structural_native_proof,read,sha,reference
W=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
ART=R/'SourceArt/OldTownRealismRefinement_20261013/SoftGoods'
S=R/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
ASSET='/Game/CodexGenerated/OldTown/SoftGoodsRefinement_20261013'
assets=unreal.EditorAssetLibrary
def write(name,d):native.write(W/name,d)
def hashes(d):
    for p,h in d.items():assert sha(p)==h,p
def build_variant(v,original,axes):
    authored=source_variant_proof(v)
    file=ART/v['fbx_file'];assert sha(file)==v['fbx_sha256']
    fb=importer.imported(file,v['mesh_name']+'_SourceModel')
    d=importer.undo_axes(importer.dynamic(fb,True),axes)
    roles=v['material_roles'];source=unreal.load_asset(v['source_asset']);assert source
    mats=[s.material_interface for s in source.static_materials];assert len(mats)==len(roles)
    imported_slot_names=[str(s.material_slot_name) for s in fb.static_materials]
    fb_roles=[next((r for r in roles if r.lower()==n.lower()),None) for n in imported_slot_names]
    assert all(x in roles for x in fb_roles),(v['mesh_name'],imported_slot_names,roles)
    imported_mats=[mats[roles.index(r)] for r in fb_roles]
    if fb_roles!=roles:
        remap=next(getattr(unreal.GeometryScript_Materials,n) for n in
            ('remap_to_new_material_i_ds_by_material','remap_to_new_material_ids_by_material') if hasattr(unreal.GeometryScript_Materials,n))
        d=remap(d,imported_mats,mats,-1)
    if original['uv_channel_count']>1:
        # Legacy beds originally have three UV channels and lightmap channel2.
        # Keep physical UV0; make valid new packed secondary charts for changed
        # cloth topology instead of retaining an index into absent channels.
        uv=unreal.GeometryScript_UVs
        setter=next(getattr(uv,n) for n in ('set_num_uv_sets','set_num_u_v_sets') if hasattr(uv,n))
        d=setter(d,original['uv_channel_count'])
        atlas=next(getattr(uv,n) for n in ('auto_generate_x_atlas_mesh_u_vs','auto_generate_xatlas_mesh_u_vs') if hasattr(uv,n))
        d=atlas(d,original['properties']['light_map_coordinate_index'],unreal.GeometryScriptXAtlasOptions())
        copy=next(getattr(uv,n) for n in ('copy_uv_set','copy_u_v_set') if hasattr(uv,n))
        for channel in range(1,original['uv_channel_count']):
            if channel!=original['properties']['light_map_coordinate_index']:
                d=copy(d,original['properties']['light_map_coordinate_index'],channel)
    out=importer.copy_to_source_clone(d,source,ASSET+'/Meshes/'+v['mesh_name'],mats)
    out.set_editor_property('static_materials',list(source.static_materials))
    for name in original['properties']:out.set_editor_property(name,source.get_editor_property(name))
    assets.set_metadata_tag(out,'SoftGoodsSourceAsset',source.get_path_name())
    assets.set_metadata_tag(out,'SoftGoodsFBXSourceSHA',sha(file));pbr.save(out)
    record=native.mesh_record(out)
    assert record['static_material_slots']==original['static_material_slots']
    assert record['properties']==original['properties'],'Original mesh settings changed: '+v['key']
    assert record['uv_channel_count']==original['uv_channel_count']
    assert collision_signature(record['collision_signature'])==collision_signature(original['collision_signature'])
    geometry=read(Path(record['geometry_file']));recipe=read(Path(v['geometry_recipe_file']))
    proof=dict(authored=authored,closed=native_closed_solid(geometry),frames=native_frame_proof(geometry),
        rigid_structure=structural_native_proof(read(Path(original['geometry_file'])),geometry,roles),
        physical_uv=native_physical_uv(geometry,recipe['physical_scale']),binary_faces=binary_face_proof(geometry,recipe,file))
    assert all(x['passed'] for x in proof.values())
    assert max(abs(x-y) for a,b in zip(record['bounds_cm'],original['bounds_cm']) for x,y in zip(a,b))<.0002
    return out,record,proof
def main():
    assert not (W/'Applied.json').exists(),'Stage already applied; do not repeat.'
    baseline=read(W/'Baseline.json');source,original=verify_baseline(baseline)
    assert sha(MAP)==baseline['source_map_sha256']
    manifest_ref=reference(ART/'ModelDataManifest.json');manifest=read(ART/'ModelDataManifest.json')
    assert manifest['passed'] and len(manifest['variants'])==20 and manifest['component_count']==222
    assert manifest['source_map_sha256']==baseline['source_map_sha256']
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors());by={a.get_actor_label():a for a in actors}
    states={n:stable_actor(a) for n,a in by.items()};assert states==source['actors']['actors']
    lights=light_inventory(actors);assert lights==source['lights']['lights']
    importer.ASSET=ASSET;pbr.ASSET=ASSET
    native.WORK=W/'BuildNative';native.MESH_CACHE.clear();native.MATERIAL_CACHE.clear();native.SOURCE_FILES.clear();native.LIMITATIONS.clear()
    axes=read(R/'Saved/CodexOutputs/OldTownRealism_20261012/AxisVerification.json')
    models={};model_records={};proofs={};rows=[]
    for v in manifest['variants']:
        obj,record,proof=build_variant(v,original[v['source_asset']],axes)
        models[v['key']]=obj;model_records[obj.get_path_name()]=record;proofs[obj.get_path_name()]=proof
        for row in v['components']:
            a=by[row['actor']];c=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()==row['component'])
            assert c.static_mesh.get_path_name()==v['source_asset']
            assert [c.get_material(i).get_path_name() for i in range(c.get_num_materials())]==row['source_materials']
            rows.append(dict(id=row['id'],actor=row['actor'],component=row['component'],before_mesh=v['source_asset'],
                after_mesh=obj.get_path_name(),materials=row['source_materials']))
        unreal.log('SOFT_GOODS_IMPORTED '+v['key'])
    assert len(models)==20 and len(rows)==222 and len({r['id'] for r in rows})==222
    assert reference(ART/'ModelDataManifest.json')==manifest_ref,'Source manifest changed during import.'
    hashes({**baseline['previous_asset_sha256'],**baseline['protected_file_sha256']})
    folder=R/('Content/'+ASSET[6:]);new={str(p.resolve()):sha(p) for p in folder.rglob('*') if p.is_file()}
    write('ApprovedPlan.json',dict(passed=True,source_map_sha256=baseline['source_map_sha256'],manifest=manifest_ref,
        components=rows,mesh_records=model_records,native_model_proofs=proofs,new_asset_sha256=new))
    expected=deepcopy(states)
    for row in rows:
        c=next(c for c in by[row['actor']].get_components_by_class(unreal.StaticMeshComponent) if c.get_name()==row['component'])
        assert c.set_static_mesh(unreal.load_asset(row['after_mesh']))
        # Preserve every prior per-component material including slot overrides.
        for i,path in enumerate(row['materials']):c.set_material(i,unreal.load_asset(path))
        e=next(x for x in expected[row['actor']]['components'] if x['name']==row['component']);e['mesh']=row['after_mesh']
    assert {n:stable_actor(a) for n,a in by.items()}==expected
    assert reference(ART/'ModelDataManifest.json')==manifest_ref,'Source manifest changed before map save.'
    assert light_inventory(actors)==lights
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    digest=sha(MAP);assert digest!=baseline['source_map_sha256']
    hashes({**baseline['previous_asset_sha256'],**baseline['protected_file_sha256'],**new})
    write('Applied.json',dict(passed=True,map_sha256=digest,source_map_sha256=baseline['source_map_sha256'],
        manifest=manifest_ref,components=222,models=20,new_asset_sha256=new))
    write('ExpectedSnapshot.json',dict(actors=expected,map_sha256=digest,actor_count=8014))
    build=read(S/'BuildReport.json');build.update(map_sha256=digest,source_map_sha256=baseline['source_map_sha256'],
        new_asset_sha256={**baseline['previous_asset_sha256'],**new},softgoods_refinement=dict(models=20,components=222,stage=str(W)))
    write('BuildReport.json',build)
    unreal.log('SOFT_GOODS_APPLIED '+json.dumps(dict(models=20,components=222,map_sha256=digest)))
if __name__=='__main__':
    try:main()
    except Exception:
        write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
