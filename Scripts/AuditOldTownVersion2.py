"""Fresh saved readback of the V2 copy and the original's camera-only cleanup."""
import sys,json
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from CreateOldTownVersion2 import W,MAP,MAIN,V2FILE,ORIGINAL,V2,current,environment,protected
from OldTownMainLightingCommon import capture_geometry_state,sha,read,write,ref
from ApplyOldTownRealismRefinement import light_inventory
def main():
    c=read(W/'Created.json');i=read(W/'Input.json');protected(i)
    hashes={str(MAP):sha(MAP),str(V2FILE):sha(V2FILE),str(MAIN):sha(MAIN)}
    assert hashes[str(MAP)]==c['original_map_sha256_after_camera_cleanup'] and hashes[str(V2FILE)]==c['version2_map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    summaries=[]
    for path,name in ((ORIGINAL,'OriginalAfterCleanup.json'),(V2,'V2Snapshot.json')):
        expected=read(W/name);assert le.load_level(path)
        actors,states=current(ae);assert states==expected['actors']
        assert capture_geometry_state(actors)==expected['exact_scene_components']
        assert environment(actors)==expected['environment'] and light_inventory(actors)==expected['lights']
        cameras=[a.get_actor_label() for a in actors if isinstance(a,unreal.CameraActor)]
        assert len(cameras)==(0 if path==ORIGINAL else 81)
        captures=[dict(actor=a.get_actor_label(),name=x.get_name(),capture_every_frame=x.get_editor_property('capture_every_frame'))
            for a in actors for x in a.get_components_by_class(unreal.SceneCaptureComponent)]
        assert len(captures)==1 and captures[0]['actor']=='BP_InventoryCharacterPreview' and captures[0]['capture_every_frame']
        summaries.append(dict(level=path,actors=len(actors),camera_actors=len(cameras),scene_capture_components=captures,
            all_saved_actor_component_environment_and_light_states_preserved=True))
    assert all(sha(p)==h for p,h in hashes.items());protected(i)
    write(W/'ReadbackAudit.json',dict(passed=True,source='fresh saved maps read only',map_hashes=hashes,
        maps=summaries,original_camera_removals=81,performance_changes_applied=False,
        original_user_edits_preserved=True,main_unchanged_from_copy=True,all_shared_packages_unchanged=True,
        original_map_future_write_allowed=False,future_assistant_target=V2))
    unreal.log('OLDTOWN_VERSION2_READBACK_PASS '+json.dumps(summaries,ensure_ascii=False))
if __name__=='__main__':main()
