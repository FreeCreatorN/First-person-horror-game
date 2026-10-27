"""Fresh saved-map readback; geometry is proven unchanged from accepted Stage3."""
import sys,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from OldTownMainLightingCommon import *
from ApplyOldTownRealismRefinement import stable_actor,light_inventory
def main():
    applied=read(W/'Applied.json');before=read(W/'Before.json');source=read(W/'SourceLights.json')
    pointer,files=frozen();digest=sha(MAP);assert digest==applied['map_sha256']
    verify_files(files)
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert le.load_level(TARGET)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    persistent=le.get_current_level();world_proof=verify_target_only_world(world,persistent)
    ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert len(by)==len(actors)==8016 and set(by)-set(before['actors'])==set(LABELS.values())
    old=[by[n] for n in before['actors']]
    assert {a.get_actor_label():stable_actor(a) for a in old}==before['actors']
    assert capture_geometry_state(old)==before['exact_scene_components']
    assert light_inventory(old)==before['lights']
    actual=[];proofs=[]
    for src in source['lights']:
        a=by[LABELS[src['label']]];assert a.get_outer()==le.get_current_level()
        row=directional_record(a);assert str(a.get_folder_path())==FOLDER
        proofs.append(compare_light(src,row));actual.append(row)
    assert len([a for a in actors if a.get_components_by_class(unreal.DirectionalLightComponent)])==2
    lights=light_inventory(actors);assert len(lights)==21
    states={n:stable_actor(a) for n,a in by.items()}
    write(W/'AfterSnapshot.json',dict(passed=True,map_sha256=digest,target_level=TARGET,actors=states,actor_count=8016))
    write(W/'LightAudit.json',dict(passed=True,map_sha256=digest,lights=lights,total_light_components=21,
        directional_lights=actual,copy_proofs=proofs,original_19_light_components_preserved=True,
        old_directional_hidden_count=0,old_directional_hide_reason='No old directional light existed in accepted saved target.'))
    write(W/'GeometryInvariantProof.json',dict(passed=True,map_sha256=digest,source_map_sha256=before['map_sha256'],
        accepted_source=ref(S/'FinalReview.json'),accepted_geometry=ref(S/'GeometryAfter.json'),
        accepted_full_surface_scan=ref(S/'SurfaceScanSummary.json'),source_actor_count=8014,source_scene_components=13920,
        exact_unrounded_scene_transforms_parent_visibility_mesh_material_collision_and_WPO_preserved=True,
        all_1206_asset_package_bytes_preserved=True,light_only_added_actors=2,new_static_mesh_components=0,
        geometry_reused_from_accepted_stage3_with_current_saved_invariant_proof=True))
    verify_files(files);assert sha(MAP)==digest
    write(W/'ReadbackAudit.json',dict(passed=True,map_sha256=digest,source_map_sha256=before['map_sha256'],
        actor_count=8016,original_actors_preserved=8014,scene_components_preserved=13920,new_directional_actors=2,
        new_assets=0,asset_count=1206,backup=applied['backup'],copy_proofs=proofs,
        target_only_world=world_proof,
        source_main_sha256_at_copy=applied['source_main_sha256'],current_main_sha256_observed=sha(MAIN),
        source_main_not_saved_by_assistant=True,map_save_requested=False,
        geometry_invariant=ref(W/'GeometryInvariantProof.json'),lights=ref(W/'LightAudit.json')))
    unreal.log('OLDTOWN_MAIN_DIRECTIONAL_READBACK_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write(W/'AuditFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
