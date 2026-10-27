"""Fresh read-only baseline and bounds for two user-reported intersections."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
W=R/'Saved/CodexOutputs/OldTownIntersectionFix_20261019';W.mkdir(parents=True,exist_ok=True)
base.W=W;base.TAG='IntersectionFix_DoNotExcludeAnyExistingActor'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def main():
    assert not (W/'BeforeScene.json').exists()
    before=files();native.write(W/'ProtectedBefore.json',dict(passed=True,file_sha256=before))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());assert len(actors)==len({a.get_actor_label() for a in actors})
    rows=[]
    for a in actors:
        comps=[]
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            if not c.static_mesh:continue
            origin,extent,radius=unreal.SystemLibrary.get_component_bounds(c)
            minimum,maximum=c.get_local_bounds()
            comps.append(dict(name=c.get_name(),path=c.get_path_name(),mesh=c.static_mesh.get_path_name(),
                local_min=native.value(minimum),local_max=native.value(maximum),world_origin=native.value(origin),
                world_extent=native.value(extent),world_transform=native.value(c.get_world_transform()),
                materials=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]))
        rows.append(dict(label=a.get_actor_label(),name=a.get_name(),path=a.get_path_name(),class_path=a.get_class().get_path_name(),
            transform=native.value(a.get_actor_transform()),tags=[str(t) for t in a.tags],folder=str(a.get_folder_path()),components=comps))
    native.write(W/'Bounds.json',dict(passed=True,map_sha256=before[str(MAP)],actor_count=len(actors),actors=rows))
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    scene=base.snapshot(actors,'BeforeIntersectionFix');native.write(W/'BeforeScene.json',scene)
    assert files()==before
    native.write(W/'Inspection.json',dict(passed=True,map_sha256=before[str(MAP)],actor_count=len(actors),all_content_config_unchanged=True,no_save=True))
    unreal.log('OLDTOWN_INTERSECTION_INSPECTION_PASS')
if __name__=='__main__':
    try:main()
    except Exception:native.write(W/'InspectionFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
