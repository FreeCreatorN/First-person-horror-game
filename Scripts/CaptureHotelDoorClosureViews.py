"""Render the installed hotel doors temporarily closed; restore poses before PASS."""
import json,sys,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import CaptureOldTownIntersectionViews as view
import InspectOldTownRealismInput as native
W=R/'Saved/CodexOutputs/OldTownHotelDoorClosure_20261019'
POSES=[]
def close_doors():
    plan=json.loads((W/'AppliedPlan.json').read_text(encoding='utf-8-sig'))
    by={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    for row in plan['doors']:
        cs={c.get_name():c for c in by[row['label']].get_components_by_class(unreal.SceneComponent)}
        for name in (('DoorHinge',) if row['kind']=='swing' else ('LeftSlider','RightSlider')):
            c=cs[name];pos=native.value(c.get_editor_property('relative_location'));rot=native.value(c.get_editor_property('relative_rotation'));POSES.append((c,pos,rot))
            if name=='DoorHinge':c.set_relative_rotation(unreal.Rotator(0,0,0),False,True)
            else:c.set_relative_location(unreal.Vector(0,pos[1],pos[2]),False,True)
    return len(plan['doors'])
def commit(success,message):
    errors=[]
    for c,p,r in POSES:
        try:
            c.set_editor_property('relative_location',unreal.Vector(*p),notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
            c.set_editor_property('relative_rotation',unreal.Rotator(pitch=r[0],yaw=r[1],roll=r[2]),notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
            c.set_absolute(c.get_editor_property('absolute_location'),c.get_editor_property('absolute_rotation'),c.get_editor_property('absolute_scale'))
            assert native.value(c.get_editor_property('relative_location'))==p
            assert native.value(c.get_editor_property('relative_rotation'))==r
        except Exception:errors.append(traceback.format_exc())
    view.commit(success and not errors,message if not errors else str(errors))
    state=view.capture._state;extra=dict(temporary_closed_door_count=96,temporary_closed_pose_restoration_verified=not errors,map_save_requested=False)
    for file in [state['run_dir']/'CaptureBatch.json',state['run_dir']/'IntersectionCaptureProof.json']+state['metadata_paths']:
        d=json.loads(file.read_text(encoding='utf-8'));d.update(extra);view.capture._write(file,d)
def main():
    report=json.loads(view.capture.BUILD_REPORT.read_text(encoding='utf-8-sig'));view.SPECS=report['review_camera_overrides'];view.PHASE='After'
    view.main();view.capture._commit_cleanup=commit
    assert close_doors()==96
    unreal.log('HOTEL_CLOSED_CAPTURE_READY 96 doors temporarily closed')
if __name__=='__main__':
    try:main()
    except Exception:view.capture.fail(traceback.format_exc());raise
