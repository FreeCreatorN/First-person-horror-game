"""Duplicate saved Main's two directional actors only after accepted backup."""
import sys,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from OldTownMainLightingCommon import *
from ApplyOldTownRealismRefinement import stable_actor,light_inventory
def main():
    assert not (W/'Applied.json').exists(),'Light copy already applied; use readback audit.'
    pointer,files=frozen();old_sha=sha(MAP);assert old_sha==pointer['map_sha256']
    backup=verify_backup(old_sha);verify_files(files);main_sha=sha(MAIN)
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    persistent=le.get_current_level();assert level_package(persistent)==TARGET
    initial_world_proof=verify_target_only_world(world,persistent)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};assert len(by)==len(actors)==8014
    states={n:stable_actor(a) for n,a in by.items()};assert states==read(S/'AfterSnapshot.json')['actors']
    old_dirs=[a for a in actors if a.get_components_by_class(unreal.DirectionalLightComponent)]
    assert len(old_dirs)==0,'Current approved input has zero old directional lights; re-inventory if changed.'
    geometry=capture_geometry_state(actors);lights=light_inventory(actors)
    assert len(geometry)==13920 and len(lights)==19
    write(W/'Before.json',dict(passed=True,map_sha256=old_sha,main_sha256=main_sha,actors=states,
        exact_scene_components=geometry,lights=lights,protected_file_sha256=files,backup=backup,
        accepted_source=ref(S/'FinalReview.json'),source_current_evidence=ref(CANON/'CurrentEvidence.json'),
        old_directional_count=len(old_dirs),initial_world=initial_world_proof))
    assert sha(MAIN)==main_sha,'Main was independently saved during target inventory; retry against the new source.'
    streaming=unreal.EditorLevelUtils.add_level_to_world(world,SOURCE,unreal.LevelStreamingAlwaysLoaded)
    assert streaming
    source_level=streaming.get_loaded_level();assert source_level and level_package(source_level)==SOURCE
    sources=[a for a in ae.get_all_level_actors() if a.get_outer()==source_level and a.get_components_by_class(unreal.DirectionalLightComponent)]
    assert {a.get_actor_label() for a in sources}==set(LABELS) and len(sources)==2
    assert le.set_current_level_by_name(unreal.Name('L_OldTownSchoolStreet')) and le.get_current_level()==persistent
    source_rows=[];proofs=[];new_labels=[]
    for source in sources:
        row=directional_record(source);assert not source.get_attach_parent_actor()
        clone=ae.duplicate_actor(source,world,unreal.Vector(0,0,0));assert clone and clone.get_outer()==persistent
        clone.set_actor_label(LABELS[row['label']]);clone.set_folder_path(unreal.Name(FOLDER))
        copied=directional_record(clone);proof=compare_light(row,copied)
        source_rows.append(row);proofs.append(proof);new_labels.append(clone.get_actor_label())
    # Encode source state before unloading Main invalidates its Python wrappers.
    write(W/'SourceLights.json',dict(passed=True,main_sha256=main_sha,lights=source_rows,copy_proofs=proofs,
        source_map_save_requested=False,copy_method='EditorActorSubsystem.duplicate_actor zero offset to OldTown persistent'))
    sources=[];source=None;source_level_to_remove=source_level;source_level=None;streaming=None
    assert unreal.EditorLevelUtils.remove_level_from_world(source_level_to_remove)
    assert le.set_current_level_by_name(unreal.Name('L_OldTownSchoolStreet'))
    assert le.get_current_level()==persistent
    final_world_proof=verify_target_only_world(world,persistent)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert len(by)==len(actors)==8016 and set(by)-set(states)==set(LABELS.values())
    originals=[by[n] for n in states]
    assert {a.get_actor_label():stable_actor(a) for a in originals}==states
    assert capture_geometry_state(originals)==geometry and light_inventory(originals)==lights
    assert all(a.get_outer()==le.get_current_level() for a in actors)
    assert sha(MAIN)==main_sha and sha(MAP)==old_sha;verify_files(files)
    write(W/'PreSaveProof.json',dict(passed=True,backup=backup,main_sha256=main_sha,source_map_save_requested=False,
        source_main_level_removed=True,target_only_world=final_world_proof,all_original_actor_and_exact_component_states_preserved=True,
        directional_lights=2,old_directional_hidden_count=0,old_directional_hide_reason='none existed in accepted saved OldTown',copy_proofs=proofs))
    assert le.save_current_level()
    assert le.get_current_level()==persistent
    verify_target_only_world(world,persistent)
    verify_files(files);assert sha(MAIN)==main_sha
    digest=sha(MAP);assert digest!=old_sha
    write(W/'Applied.json',dict(passed=True,source_map_sha256=old_sha,map_sha256=digest,target_level=TARGET,
        actor_count=8016,new_actor_labels=new_labels,original_actors=8014,new_assets=0,
        source_main_sha256=main_sha,source_main_unchanged=True,assistant_main_map_write_allowed=False,
        backup=backup,source_lights=ref(W/'SourceLights.json'),pre_save_proof=ref(W/'PreSaveProof.json'),
        old_directional_count=0,old_directional_hidden_count=0))
    build=read(S/'BuildReport.json');build.update(map_sha256=digest,target_level=TARGET,
        source_softgoods_report=ref(S/'BuildReport.json'),main_lighting=ref(W/'Applied.json'))
    write(W/'BuildReport.json',build)
    unreal.log('OLDTOWN_MAIN_DIRECTIONAL_APPLIED '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write(W/'ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
