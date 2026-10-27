"""Fresh read-only geometry, Blueprint and full-scene baseline for hotel doors."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
from BuildOldTownOpeningBlueprints import _templates
W=R/'Saved/CodexOutputs/OldTownHotelDoorClosure_20261019';W.mkdir(parents=True,exist_ok=True)
base.W=W;base.TAG='DoorClosure_DoNotExcludeAnyExistingActor'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def component(c):
    d=dict(name=c.get_name(),class_path=c.get_class().get_path_name(),parent=c.get_attach_parent().get_name() if c.get_attach_parent() else None,
        local=native.props(c,['relative_location','relative_rotation','relative_scale3d','mobility','visible','hidden_in_game']),world=native.value(c.get_world_transform()))
    if isinstance(c,unreal.StaticMeshComponent) and c.static_mesh:
        low,high=c.get_local_bounds();d.update(mesh=c.static_mesh.get_path_name(),local_min=native.value(low),local_max=native.value(high),
            materials=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())],collision=str(c.get_collision_enabled()))
    return d
def main():
    assert not (W/'Inspection.json').exists()
    before=files();native.write(W/'ProtectedBefore.json',dict(passed=True,file_sha256=before))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());assert len(actors)==len({a.get_actor_label() for a in actors})
    doors=[a for a in actors if a.get_class().get_path_name().startswith('/Game/CodexGenerated/Hotel/Blueprints/BP_Hotel_Door')]
    hotel=[a for a in doors if a.get_actor_label().startswith('OTS_HotelV4_Door_') and 'HotelRedesign_20261008_V4' in [str(t) for t in a.tags]]
    assert hotel
    rows=[dict(label=a.get_actor_label(),name=a.get_name(),class_path=a.get_class().get_path_name(),is_hotel=a in hotel,
        actor_transform=native.value(a.get_actor_transform()),tags=[str(t) for t in a.tags],folder=str(a.get_folder_path()),
        components=[component(c) for c in a.get_components_by_class(unreal.SceneComponent)]) for a in doors]
    blueprints={};sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    for a in hotel:
        path=a.get_class().get_path_name().split('.')[0]
        if path in blueprints:continue
        bp=unreal.load_asset(path);export=W/'BlueprintNative'/(Path(path).name+'.t3d');_,proof=native.native_text_export(bp,export);assert proof['passed']
        blueprints[path]=dict(native=proof,file=str(export),templates={n:component(c) for n,(_,c) in _templates(sub,bp).items()})
    attached=[]
    for a in actors:
        for c in a.get_components_by_class(unreal.SceneComponent):
            p=c.get_attach_parent()
            if p and p.get_owner() in hotel and p.get_owner()!=a:
                attached.append(dict(label=a.get_actor_label(),class_path=a.get_class().get_path_name(),door=p.get_owner().get_actor_label(),component=component(c),tags=[str(t) for t in a.tags]))
    native.write(W/'Doors.json',dict(passed=True,map_sha256=before[str(MAP)],actor_count=len(actors),all_doors=rows,hotel_door_count=len(hotel),blueprints=blueprints,attached=attached))
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    native.write(W/'BeforeScene.json',base.snapshot(actors,'BeforeDoorClosure'))
    assert files()==before
    native.write(W/'Inspection.json',dict(passed=True,map_sha256=before[str(MAP)],actor_count=len(actors),hotel_door_count=len(hotel),all_content_config_unchanged=True,no_save=True))
    unreal.log('HOTEL_DOOR_CLOSURE_INSPECTION_PASS')
if __name__=='__main__':
    try:main()
    except Exception:native.write(W/'InspectionFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
