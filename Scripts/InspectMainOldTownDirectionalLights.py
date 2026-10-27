"""Read saved Main and OldTown directional lights, without saving either map."""
import json,sys
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
from ApplyOldTownRealismRefinement import stable_actor
W=R/'Saved/CodexOutputs/OldTownMainLighting_20261015'
def inventory(level,token):
    file=R/('Content/'+level.removeprefix('/Game/')+'.umap');digest=native.sha(file)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(level)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors());lights=[]
    for a in actors:
        comps=list(a.get_components_by_class(unreal.DirectionalLightComponent))
        if comps:
            _,export=native.native_text_export(a,W/token/(a.get_name()+'.t3d'))
            lights.append(dict(actor_label=a.get_actor_label(),actor_class=a.get_class().get_path_name(),
                actor_state=stable_actor(a),owner_level=a.get_outer().get_path_name(),native_export=export,
                components=[dict(name=c.get_name(),class_path=c.get_class().get_path_name(),
                    all_editor_properties=native.reflect_editor_properties(c)) for c in comps]))
    assert native.sha(file)==digest
    return dict(map_file=str(file),map_sha256=digest,level=level,actor_count=len(actors),directional_lights=lights,map_save_requested=False)
def main():
    W.mkdir(parents=True,exist_ok=True)
    before={str(p):native.sha(p) for p in (R/'Content/Yastar/Maps/L_Main.umap',R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')}
    main=inventory('/Game/Yastar/Maps/L_Main','Main');town=inventory('/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet','OldTown')
    assert all(native.sha(Path(p))==h for p,h in before.items())
    native.write(W/'DirectionalInput.json',dict(passed=True,main=main,oldtown=town,source='fresh_saved_maps_read_only',
        map_files_before=before,all_maps_unchanged=True,assistant_main_map_write_allowed=False,
        action_order='finish and accept softgoods; back up map and paired assets; only then copy Main lights and hide original target directional actors'))
    unreal.log('MAIN_OLDTOWN_DIRECTIONAL_INPUT_PASS '+str(len(main['directional_lights']))+' '+str(len(town['directional_lights'])))
if __name__=='__main__':main()
