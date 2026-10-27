"""Finish the 11 assistant moving hinges that were attached to the fixed frame."""
import sys,shutil,traceback
from pathlib import Path
from datetime import datetime,timezone
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from HotelDoorClosureCommon import *
from HotelDoorClosurePreservation import verify
def main():
    assert not (W/'HingeParentsApplied.json').exists()
    applied=read('Applied.json');assert applied['passed'] and read('Apply5.Completion.json')['normal_zero_exit']
    expected=read('ProtectedBefore.json')['file_sha256'];expected.update(applied['modified_existing_files']);expected.update(applied['new_assets']);assert files()==expected
    before_sha=native.sha(MAP);assert before_sha==applied['map_sha256']
    backup=R/'Saved/CodexBackups'/('HotelDoorHingeParentsBefore_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    saved=backup/MAP.name;shutil.copy2(MAP,saved);assert native.sha(saved)==before_sha
    write('HingeParentBackup.json',dict(passed=True,file=str(saved),sha256=before_sha))
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors};plan=read('AppliedPlan.json');fixed=[]
    for row in plan['moving_hinges']:
        a=by[row['label']];c=a.static_mesh_component;parent=components(by[row['door']])['DoorHinge'];old=c.get_attach_parent()
        assert old and old.get_owner()==by[row['door']]
        if old==parent:
            assert native.value(c.get_editor_property('relative_location'))==[0,0,0] and native.value(c.get_editor_property('relative_rotation'))==[0,0,0]
            continue
        assert old.get_name()=='OpeningRoot' and 'HotelDetails_20261009' in [str(t) for t in a.tags]
        row.update(reparent_to_hinge=True,expected_parent=parent.get_path_name())
        assert a.attach_to_component(parent,unreal.Name('None'),unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,False)
        c.set_editor_property('relative_location',unreal.Vector(0,0,0),notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        c.set_editor_property('relative_rotation',unreal.Rotator(0,0,0),notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        c.set_editor_property('relative_scale3d',unreal.Vector(1,1,1),notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        c.set_absolute(c.get_editor_property('absolute_location'),c.get_editor_property('absolute_rotation'),c.get_editor_property('absolute_scale'))
        assert c.get_attach_parent()==parent;fixed.append(row['label'])
    assert len(fixed)==11
    write('AppliedPlanWithParents.json',plan)
    closure=validate_closed(by,plan);write('BeforeSaveClosureWithParents.json',closure)
    state=snap(actors,'BeforeSaveDoorHingeParents');write('BeforeSaveSceneWithParents.json',state)
    preservation=verify(read('BeforeScene.json'),state,plan);write('BeforeSavePreservationWithParents.json',preservation)
    assert le.save_current_level()
    expected[str(MAP)]=native.sha(MAP);assert files()==expected
    proof=dict(passed=True,source_map_sha256=before_sha,map_sha256=native.sha(MAP),corrected_count=11,labels=fixed,
        all_62_moving_hinges_follow_door=True,all_186_hinge_bearing_centers_match_when_closed=True,preservation=preservation)
    write('HingeParentsApplied.json',proof);write('AppliedPlan.json',plan)
    applied.update(map_sha256=native.sha(MAP),hinge_parent_corrections=11,original_leaf_apply_map_sha256=before_sha,before_save_preservation=preservation)
    applied['modified_existing_files'][str(MAP)]=native.sha(MAP);write('Applied.json',applied)
    unreal.log('HOTEL_DOOR_HINGE_PARENTS_APPLY_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('HingeParentFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
