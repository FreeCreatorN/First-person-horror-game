import sys,traceback
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from HotelDoorClosureCommon import *
from HotelDoorClosurePreservation import verify
from BuildOldTownOpeningBlueprints import _templates
def main():
    assert not (W/'Readback.json').exists()
    applied=read('Applied.json');plan=read('AppliedPlan.json');assert applied['passed'] and read('Apply5.Completion.json')['normal_zero_exit']
    assert read('HingeParentsApplied.json')['passed'] and read('HingeParents1.Completion.json')['normal_zero_exit']
    assert native.sha(MAP)==applied['map_sha256']
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);assert le.load_level(TARGET)
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    closure=validate_closed(by,plan);write('ReadbackClosure.json',closure)
    actual=snap(actors,'AfterDoorClosure2');write('AfterScene.json',actual);preservation=verify(read('BeforeScene.json'),actual,plan)
    defaults=[];sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);inventory=read('Doors.json')
    named={'DoorLeaf','LeafCollision','Handle','LeftLeaf','RightLeaf','LeftLeafCollision','RightLeafCollision','LeftHandle','RightHandle','LeftGlassPanel','RightGlassPanel'}
    for p,labels in plan['blueprints'].items():
        bp=unreal.load_asset(p);templates=_templates(sub,bp)
        assert set(templates)==set(inventory['blueprints'][p]['templates'])|{'DoorStops'}
        for n,old in inventory['blueprints'][p]['templates'].items():
            c=templates[n][1];expected=list(old['local']['relative_location']);rot=list(old['local']['relative_rotation'])
            if n in named and old.get('mesh'):expected[1]-=5
            if n in ('LeftSlider','RightSlider'):expected[0]=0
            if n=='DoorHinge':rot=[0,0,0]
            assert native.value(c.get_editor_property('relative_location'))==expected,(p,n)
            assert native.value(c.get_editor_property('relative_rotation'))==rot,(p,n)
            if old.get('mesh'):
                assert c.static_mesh.get_path_name()==old['mesh'] and [c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]==old['materials']
        oldpath=Path(inventory['blueprints'][p]['file']);raw=oldpath.read_bytes();oldt=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
        assert graph_sections(oldt)==graph_sections(export_text(bp,Path(p).name+'_Readback'))
        defaults.append(dict(blueprint=p,closed_default=True,existing_materials_and_graphs_preserved=True))
    expected=read('ProtectedBefore.json')['file_sha256'];expected.update(applied['modified_existing_files']);expected.update(applied['new_assets']);assert files()==expected
    write('Readback.json',dict(passed=True,map_sha256=applied['map_sha256'],hotel_doors=96,closed_collision_leaf_traces=sum(len(d['closed_collision_traces']) for d in closure['doors']),
        preservation=preservation,blueprint_defaults=defaults,all_other_content_config_unchanged=True,no_save=True))
    unreal.log('HOTEL_DOOR_CLOSURE_READBACK_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ReadbackFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
