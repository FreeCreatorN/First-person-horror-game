"""Save the user's completed town as V2, then remove only owned review cameras."""
import sys,traceback,json
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor,light_inventory
from OldTownMainLightingCommon import capture_geometry_state,sha,read,write,ref
W=R/'Saved/CodexOutputs/OldTownVersion2_20261016'
ORIGINAL='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
V2='/Game/CodexGenerated/OldTownVersion2/Maps/老城区第二版'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
V2FILE=R/'Content/CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap'
MAIN=R/'Content/Yastar/Maps/L_Main.umap'
ENV=['DirectionalLight','MoonDirectionalLight','SkyLight','BP_EnvironmentController','ExponentialHeightFog','SkyAtmosphere','VolumetricCloud','PostProcessVolume']
def normalize(v):
    if isinstance(v,str):return v.replace(ORIGINAL+'.L_OldTownSchoolStreet',V2+'.老城区第二版')
    if isinstance(v,list):return [normalize(x) for x in v]
    if isinstance(v,dict):return {k:normalize(x) for k,x in v.items()}
    return v
def identity_free(v):
    if isinstance(v,dict):return {k:identity_free(x) for k,x in v.items() if k not in ('actor_guid','actor_instance_guid','instance_guid','light_guid')}
    if isinstance(v,list):return [identity_free(x) for x in v]
    return v
def environment(actors):
    by={a.get_actor_label():a for a in actors};assert set(ENV).issubset(by)
    return {n:identity_free(dict(actor=native.reflect_editor_properties(by[n]),
        components={c.get_name():native.reflect_editor_properties(c) for c in by[n].get_components_by_class(unreal.ActorComponent)})) for n in ENV}
def protected(i):
    files={**i['referenced_game_package_sha256'],**i['all_original_generated_file_sha256']}
    files.pop(str(MAP),None);files.pop(str(MAIN),None)
    for p,h in files.items():assert sha(p)==h,p
def current(ae):
    actors=list(ae.get_all_level_actors());states={a.get_actor_label():stable_actor(a) for a in actors}
    assert len(states)==len(actors)
    return actors,states
def main():
    assert not (W/'Created.json').exists(),'V2 already created; use read-only audit.'
    assert not V2FILE.exists(),'Never overwrite a preexisting V2 map.'
    i=read(W/'Input.json');assert sha(MAP)==i['map_sha256'];main_sha=sha(MAIN);protected(i)
    backup=read(W/'Backup.json');assert backup['passed'] and backup['map_sha256']==i['map_sha256']
    manifest=read(backup['manifest']['file']);assert sha(backup['manifest']['file'])==backup['manifest']['sha256']
    base=Path(backup['backup_directory']).resolve();assert base.is_relative_to((R/'Saved/CodexBackups').resolve())
    for r in manifest['files']:
        p=(base/r['relative_path']).resolve();assert p.is_relative_to(base) and sha(p)==r['sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(ORIGINAL)
    actors,states=current(ae);assert states==i['actors'] and capture_geometry_state(actors)==i['exact_scene_components']
    before_env=environment(actors);before_lights=light_inventory(actors)
    write(W/'UserEnvironmentBefore.json',dict(passed=True,map_sha256=i['map_sha256'],settings=before_env))
    historical=read(R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013/AfterSnapshot.json')['actors']
    owned={n:s for n,s in historical.items() if 'Camera' in s['class'] and n.startswith('CAM_') and s['folder'].startswith('OldTownSchoolStreet/')}
    camera_rows={c['label']:c for c in i['cameras']}
    remove=[]
    for n,s in owned.items():
        if n not in states:continue
        assert all(states[n][k]==s[k] for k in ('class','name','folder')),(n,'Camera identity changed')
        assert camera_rows[n]['actor_properties']['auto_activate_for_player']=='<AutoReceiveInput.DISABLED: 0>'
        a=next(a for a in actors if a.get_actor_label()==n)
        assert isinstance(a,unreal.CameraActor) and not a.get_attached_actors(),n
        remove.append(n)
    assert len(remove)==81 and len(remove)==len(i['cameras'])
    write(W/'CameraRemovalPlan.json',dict(passed=True,user_requested=True,actors=sorted(remove),count=len(remove),
        provenance=ref(R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013/AfterSnapshot.json'),
        only_historical_generated_review_camera_actors=True,player_cameras_and_scene_capture_components_preserved=True))
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.EditorAssetLibrary.make_directory(V2.rsplit('/',1)[0])
    assert unreal.EditorLoadingAndSavingUtils.save_map(world,V2)
    assert sha(MAP)==i['map_sha256'] and sha(MAIN)==main_sha;protected(i)
    assert V2FILE.is_file()
    # SaveAs duplicates the native world; explicitly reload its saved package.
    assert le.load_level(V2)
    copied,copied_states=current(ae);assert copied_states==states
    copied_geometry=capture_geometry_state(copied)
    assert copied_geometry==normalize(i['exact_scene_components'])
    assert environment(copied)==normalize(before_env) and light_inventory(copied)==before_lights
    assert le.get_current_level().get_outermost().get_path_name()==V2
    tri=sum(c.static_mesh.get_num_triangles(0) for a in copied for c in a.get_components_by_class(unreal.StaticMeshComponent)
        if c.static_mesh and c.get_editor_property('visible') and not c.get_editor_property('hidden_in_game'))
    v2sha=sha(V2FILE)
    write(W/'V2Snapshot.json',dict(passed=True,map_sha256=v2sha,target_level=V2,actor_count=len(copied),actors=copied_states,
        exact_scene_components=copied_geometry,environment=normalize(before_env),lights=before_lights,
        raw_visible_instance_triangles=tri,geometry_materials_collision_user_environment_preserved=True))
    write(W/'CopiedBeforeCleanup.json',dict(passed=True,original_map_sha256=i['map_sha256'],version2_map_sha256=v2sha,
        target_level=V2,source_level=ORIGINAL,backup=ref(W/'Backup.json'),source_original_not_saved_by_copy=True,
        all_user_actor_component_and_environment_state_preserved=True,
        shared_asset_policy='Shared dependencies are frozen. Future edits must duplicate replacement assets into OldTownVersion2 and assign only in V2.'))
    # Only now perform the user's explicitly requested cleanup on their map.
    assert le.load_level(ORIGINAL)
    actors,loaded=current(ae);assert loaded==states and capture_geometry_state(actors)==i['exact_scene_components']
    for a in actors:
        if a.get_actor_label() in remove:assert ae.destroy_actor(a)
    kept,cleaned=current(ae);expected={n:s for n,s in states.items() if n not in remove}
    assert cleaned==expected
    expected_geometry={n:s for n,s in i['exact_scene_components'].items() if n.split('::',1)[0] not in remove}
    assert capture_geometry_state(kept)==expected_geometry
    assert environment(kept)==before_env and light_inventory(kept)==before_lights
    assert le.save_current_level()
    assert sha(V2FILE)==v2sha and sha(MAIN)==main_sha;protected(i)
    write(W/'OriginalAfterCleanup.json',dict(passed=True,map_sha256=sha(MAP),target_level=ORIGINAL,actors=cleaned,
        actor_count=len(kept),exact_scene_components=expected_geometry,environment=before_env,lights=before_lights,
        removed_camera_labels=sorted(remove),removed_cameras=81,other_user_edits_preserved=True))
    write(W/'Created.json',dict(passed=True,source_user_map_sha256=i['map_sha256'],source_level=ORIGINAL,
        original_map_sha256_after_camera_cleanup=sha(MAP),version2_map_sha256=v2sha,target_level=V2,
        version2_map_file=str(V2FILE),original_camera_removed_count=81,version2_review_cameras_retained=81,
        original_actor_count=len(kept),version2_actor_count=len(copied),main_map_unchanged=True,main_map_sha256=main_sha,
        shared_asset_files_unchanged=True,backup=ref(W/'Backup.json'),performance_changes_applied=False,
        existing_user_directional_lights_preserved=True,extra_directional_lights_added=0,
        future_assistant_work_target=V2,original_map_future_write_allowed=False,
        shared_assets_read_only_future_changes_require_v2_owned_replacement=True))
    unreal.log('OLDTOWN_VERSION2_CREATED '+json.dumps(dict(map_sha256=v2sha,cameras_removed=81,original_actors=len(kept),version2_actors=len(copied)),ensure_ascii=False))
if __name__=='__main__':
    try:main()
    except Exception:
        write(W/'CreateFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
