"""Complete read-only Actor/native baseline before any Hotel package copying."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';base.W=W;base.TAG='HotelNaming_ExcludeNoExistingActor'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet';MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def main():
    assert not (W/'BeforeScene.json').exists()
    inventory=json.loads((W/'Inventory.json').read_text(encoding='utf-8-sig'))
    baseline=json.loads((W/'ProtectedBeforeAfterRestore.json').read_text(encoding='utf-8-sig'))['file_sha256']
    assert native.sha(MAP)==inventory['map_sha256']
    assert all(native.sha(Path(p))==h for p,h in baseline.items())
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);actorsys=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert level.load_level(TARGET)
    actors=list(actorsys.get_all_level_actors());assert len(actors)==inventory['actor_count']
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    snapshot=base.snapshot(actors,'BeforeHotelNaming')
    assert len(snapshot['full_existing_actor_native'])==len(actors)
    assert all(native.sha(Path(p))==h for p,h in baseline.items())
    native.write(W/'BeforeScene.json',snapshot)
    unreal.log('HOTEL_NAMING_FULL_BEFORE_PASS '+str(len(actors)))
if __name__=='__main__':
    try:main()
    except Exception:native.write(W/'BeforeSceneFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
