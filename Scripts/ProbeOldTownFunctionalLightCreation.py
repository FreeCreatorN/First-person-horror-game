"""No-save probe of native light creation and exact template property copying."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import ApplyOldTownFunctionalLighting as task
W=task.W
before=task.native.sha(task.MAP)
le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
created=[]
try:
    assert le.load_level(task.TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert len(actors)==7952
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    rows=task.recipes(by)
    proof=[]
    for row in (rows[0],rows[-1]):
        light=task.bind_light(row,by,ae,world);created.append(light)
        proof.append(row)
    assert all(ae.destroy_actor(a) for a in created);created=[]
    assert len(ae.get_all_level_actors())==7952
    assert task.native.sha(task.MAP)==before
    task.write('CreationProbe.json',dict(passed=True,no_map_save=True,map_sha256=before,rows=proof))
    unreal.log('FUNCTIONAL_LIGHT_CREATION_PROBE_PASS')
except Exception:
    task.write('CreationProbe.json',dict(passed=False,traceback=traceback.format_exc(),no_map_save=True,map_sha256=task.native.sha(task.MAP)))
    raise
finally:
    for actor in created:ae.destroy_actor(actor)
