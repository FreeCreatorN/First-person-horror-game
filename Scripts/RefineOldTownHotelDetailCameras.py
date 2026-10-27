"""Move only review cameras; retain exact hotel geometry and interactions."""
import sys,json,shutil,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import sha,actor_state
WORK=ROOT/'Saved/CodexOutputs/HotelDetails_20261009'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,r):(WORK/n).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    assert not (WORK/'CameraRefinement.json').exists()
    build=read(WORK/'BuildReport.json');old=build['map_sha256'];mapfile=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    assert sha(mapfile)==old;levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(build['target_level'])
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    before_states={n:actor_state(a) for n,a in by.items()};backup=WORK/'BeforeCaptureRefinement';backup.mkdir(exist_ok=True)
    for p in (mapfile,WORK/'BuildReport.json',WORK/'Applied.json'):
        dst=backup/p.name
        if not dst.exists():shutil.copy2(p,dst)
    updates={'CAM_Detail_StairRail':dict(position=[9770,1075,315],look_at=[9860,850,210],fov=95),
        'CAM_Detail_StairWindow':dict(position=[9750,1080,300],look_at=[10030,1080,280],fov=90)}
    plan=build['hotel_v4']
    for r in plan['review_cameras']:
        if r['camera'] not in updates:continue
        r.update(updates[r['camera']]);a=by[r['camera']]
        a.set_actor_location(unreal.Vector(*r['position']),False,True)
        a.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*r['position']),unreal.Vector(*r['look_at'])),True)
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',r['fov'])
        plan['expected_actor_states'][r['camera']]=actor_state(a)
    current={n:actor_state(a) for n,a in by.items()};changed={n for n in before_states if current[n]!=before_states[n]}
    assert changed==set(updates),changed
    report=read(WORK/'DetailRepairReport.json')
    for r in report['new_cameras']:
        if r['camera'] in updates:r.update(updates[r['camera']])
    assert sha(mapfile)==old;assert levels.save_current_level();digest=sha(mapfile)
    report['map_sha256']=digest;build.update(map_sha256=digest,hotel_v4=plan,hotel_architecture=plan,detail_repair=report)
    applied=read(WORK/'Applied.json');applied['map_sha256']=digest
    write('Applied.json',applied);write('BuildReport.json',build);write('ArchitecturePlan.json',plan);write('DetailRepairReport.json',report)
    write('CameraRefinement.json',dict(passed=True,previous_map_sha256=old,map_sha256=digest,changed_actor_labels=sorted(changed),only_review_camera_transforms_changed=True,updates=updates))
    unreal.log('HOTEL_DETAIL_CAMERAS_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write('CameraFailure.json',dict(traceback=traceback.format_exc()));raise
