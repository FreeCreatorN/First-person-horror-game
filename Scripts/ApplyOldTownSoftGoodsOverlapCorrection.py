"""Repair one unpublished owned mattress; keep the other 38 packages exact."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import ApplyOldTownSoftGoodsRefinement as build
import InspectOldTownRealismInput as native
import OldTownRealismImport as importer
import OldTownRealismMaterials as pbr
from ApplyOldTownRealismRefinement import stable_actor,light_inventory
from VerifyOldTownSoftGoodsRefinement import read,sha,reference,verify_baseline
W=build.W;ART=build.ART
def main():
    previous=read(W/'Applied.json');assert 'overlap_correction' not in previous
    backup=read(W/'OverlapDiagnosis/BeforeCorrectionBackup.json');assert backup['passed']
    backup_dir=Path(backup['backup_directory']);assert sha(backup_dir/'Manifest.json')==backup['manifest_sha256']
    old_source=read(backup_dir/'SourceArt/OldTownRealismRefinement_20261013/SoftGoods/ModelDataManifest.json')
    manifest_ref=reference(ART/'ModelDataManifest.json');manifest=read(ART/'ModelDataManifest.json')
    assert manifest['passed'] and len(manifest['variants'])==20
    selected=next(v for v in manifest['variants'] if v['key']=='LegacyBedMattress')
    assert selected['legacy_lateral_fold_guard']['passed']
    for old in old_source['variants']:
        if old['key']!='LegacyBedMattress':assert old==next(v for v in manifest['variants'] if v['key']==old['key'])
    source,original=verify_baseline(read(W/'Baseline.json'))
    digest=sha(build.MAP);assert digest==previous['map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert le.load_level(build.TARGET)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    states={a.get_actor_label():stable_actor(a) for a in actors};lights=light_inventory(actors)
    assert states==read(W/'ExpectedSnapshot.json')['actors']
    path=build.ASSET+'/Meshes/'+selected['mesh_name'];cache=build.ASSET+'/Meshes/ImportData/'+selected['mesh_name']+'_SourceModel'
    changed_files={str(R/('Content/'+p.removeprefix('/Game/')+'.uasset')) for p in (path,cache)}
    assert len(changed_files)==2 and changed_files.issubset(previous['new_asset_sha256'])
    for p,h in previous['new_asset_sha256'].items():assert sha(p)==h,p
    def import_repaired(file,name):
        assert name==selected['mesh_name']+'_SourceModel'
        assert build.assets.does_asset_exist(cache)
        ui=unreal.FbxImportUI()
        for k,v in dict(import_mesh=True,import_as_skeletal=False,import_animations=False,import_materials=False,
            import_textures=False,mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH).items():ui.set_editor_property(k,v)
        data=ui.get_editor_property('static_mesh_import_data')
        for k,v in dict(combine_meshes=True,auto_generate_collision=False,generate_lightmap_u_vs=False,remove_degenerates=False,
            convert_scene=True,convert_scene_unit=True,import_uniform_scale=1.,
            normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS).items():data.set_editor_property(k,v)
        task=unreal.AssetImportTask()
        for k,v in dict(filename=str(file),destination_path=cache.rsplit('/',1)[0],destination_name=name,
            automated=True,replace_existing=True,replace_existing_settings=True,save=False,options=ui,factory=unreal.FbxFactory()).items():task.set_editor_property(k,v)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        mesh=build.assets.load_asset(cache);assert isinstance(mesh,unreal.StaticMesh)
        build.assets.set_metadata_tag(mesh,'RealismFBXSourceSHA',sha(file));importer.high_precision(mesh);pbr.save(mesh)
        return mesh
    importer.ASSET=build.ASSET;pbr.ASSET=build.ASSET
    native.WORK=W/'BuildNative';native.MESH_CACHE.clear();native.MATERIAL_CACHE.clear();native.SOURCE_FILES.clear();native.LIMITATIONS.clear()
    imported_function=importer.imported;importer.imported=import_repaired
    try:obj,record,proof=build.build_variant(selected,original[selected['source_asset']],read(R/'Saved/CodexOutputs/OldTownRealism_20261012/AxisVerification.json'))
    finally:importer.imported=imported_function
    assert obj.get_path_name()==path+'.'+selected['mesh_name']
    current={str(p.resolve()):sha(p) for p in (R/'Content/CodexGenerated/OldTown/SoftGoodsRefinement_20261013').rglob('*') if p.is_file()}
    assert len(current)==40 and set(current)==set(previous['new_asset_sha256'])
    changed={p for p,h in current.items() if h!=previous['new_asset_sha256'][p]}
    assert changed==changed_files,changed
    assert {a.get_actor_label():stable_actor(a) for a in actors}==states and light_inventory(actors)==lights
    assert sha(build.MAP)==digest,'This asset-only correction must not save the map.'
    for p,h in {**read(W/'Baseline.json')['previous_asset_sha256'],**read(W/'Baseline.json')['protected_file_sha256']}.items():assert sha(p)==h
    assert reference(ART/'ModelDataManifest.json')==manifest_ref
    correction=dict(passed=True,map_sha256=digest,map_save_requested=False,model='LegacyBedMattress',instances=7,
        source_manifest=manifest_ref,before_manifest=previous['manifest'],backup=reference(W/'OverlapDiagnosis/BeforeCorrectionBackup.json'),
        changed_owned_packages=sorted(changed),other_38_owned_packages_unchanged=True,original_1166_packages_unchanged=True,
        actor_component_material_collision_pose_and_lights_unchanged=True,native_proof=proof,
        lateral_fold_guard=selected['legacy_lateral_fold_guard'])
    native.write(W/'OverlapCorrection.json',correction)
    previous.update(manifest=manifest_ref,new_asset_sha256=current,overlap_correction=reference(W/'OverlapCorrection.json'))
    native.write(W/'Applied.json',previous)
    plan=read(W/'ApprovedPlan.json');plan.update(manifest=manifest_ref,new_asset_sha256=current)
    plan['mesh_records'][obj.get_path_name()]=record;plan['native_model_proofs'][obj.get_path_name()]=proof
    native.write(W/'ApprovedPlan.json',plan)
    report=read(W/'BuildReport.json');report['new_asset_sha256']={**read(W/'Baseline.json')['previous_asset_sha256'],**current}
    report['softgoods_overlap_correction']=reference(W/'OverlapCorrection.json');native.write(W/'BuildReport.json',report)
    unreal.log('SOFT_GOODS_OVERLAP_CORRECTION_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        native.write(W/'OverlapCorrectionFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
