import sys,traceback
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from OldTownIntersectionFixCommon import *
def main():
    assert not (W/'Readback.json').exists()
    plan=read('Plan.json');applied=read('Applied.json');assert applied['passed'] and native.sha(MAP)==applied['map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    actual=base.snapshot(actors,'AfterIntersectionFix');write('AfterScene.json',actual)
    proof=verify(read('BeforeScene.json'),actual,plan);clearance=validate_geometry(by,plan)
    baseline=read('ProtectedBefore.json')['file_sha256'];current=files();expected=dict(baseline);expected[str(MAP)]=applied['map_sha256'];assert current==expected
    write('Readback.json',dict(passed=True,map_sha256=applied['map_sha256'],actor_preservation=proof,clearances=clearance,all_other_content_config_unchanged=True,no_save=True))
    unreal.log('OLDTOWN_INTERSECTION_READBACK_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ReadbackFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
