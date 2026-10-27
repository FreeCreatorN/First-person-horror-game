import sys,math,shutil,traceback
from pathlib import Path
from datetime import datetime,timezone
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from OldTownIntersectionFixCommon import *
def main():
    assert not (W/'Applied.json').exists()
    plan=read('Plan.json');assert plan['passed'] and read('Inspection.json')['passed'] and read('Inspect1.Completion.json')['normal_zero_exit']
    baseline=read('ProtectedBefore.json')['file_sha256'];assert files()==baseline and native.sha(MAP)==plan['source_map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};assert len(actors)==len(by)==plan['actor_count']
    backup=R/'Saved/CodexBackups'/('OldTownIntersectionBefore_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    saved=backup/MAP.name;shutil.copy2(MAP,saved);assert native.sha(saved)==plan['source_map_sha256']
    write('Backup.json',dict(passed=True,file=str(saved),sha256=native.sha(saved)))
    for row in plan['moves']+plan['wires']:
        a=by[row['label']];assert isinstance(a,unreal.StaticMeshActor) and pose(a)==row['before'];assert a.static_mesh_component.get_attach_parent() is None
    for row in plan['moves']:
        a=by[row['label']];assert a.set_actor_location(unreal.Vector(*row['position']),False,True)
        if row['yaw_delta']:
            rot=a.get_actor_rotation();rot.yaw+=row['yaw_delta'];assert a.set_actor_rotation(rot,True)
    for row in plan['wires']:
        a=by[row['label']];p,q=row['endpoints'];mid=[(p[i]+q[i])/2 for i in range(3)]
        assert a.set_actor_location(unreal.Vector(*mid),False,True)
        assert a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*p),unreal.Vector(*q)),True)
        s=a.get_actor_scale3d();extent=a.static_mesh_component.static_mesh.get_bounds().box_extent.x
        a.set_actor_scale3d(unreal.Vector(math.dist(p,q)/(2*extent),s.y,s.z))
    clearance=validate_geometry(by,plan)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    in_memory=base.snapshot(actors,'BeforeSaveIntersectionFix');write('BeforeSaveScene.json',in_memory)
    preservation=verify(read('BeforeScene.json'),in_memory,plan);write('BeforeSavePreservation.json',preservation)
    assert le.save_current_level()
    after=files();assert set(after)==set(baseline) and all(after[p]==h for p,h in baseline.items() if p!=str(MAP))
    write('Applied.json',dict(passed=True,map_sha256=native.sha(MAP),source_map_sha256=plan['source_map_sha256'],changed_labels=plan['allowed_labels'],
        backup=str(saved),clearances=clearance,before_save_preservation=preservation,only_original_map_file_changed=True,no_assets_modified=True))
    unreal.log('OLDTOWN_INTERSECTION_APPLY_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
