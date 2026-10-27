"""Move owned front piers flush behind the 2.2m gallery and add top-floor view."""
import json,sys,traceback,shutil
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha
from AuditOldTownHotelV4 import audit,refresh
WORK=ROOT/'Saved/CodexOutputs/HotelRedesign_20261008_V4'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,d):(WORK/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    build=read(WORK/'BuildReport.json');old=build['hotel_v4'];new=read(WORK/'ArchitecturePlan.json')
    mapfile=ROOT/('Content/'+build['target_level'].removeprefix('/Game/')+'.umap');oldhash=sha(mapfile)
    assert oldhash==build['map_sha256']
    baseline=read(WORK/'PreservationBaseline.json')
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert level.load_level(build['target_level'])
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert all(actor_state(by[n])==state for n,state in old['expected_actor_states'].items())
    backup=WORK/'BeforeClearanceRefinement';backup.mkdir(exist_ok=True)
    for p in (mapfile,WORK/'BuildReport.json',WORK/'ArchitectureAudit.json'):
        if not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
    wanted={r['id']:r for r in new['boxes']};changed=[]
    for r in old['placed_boxes']:
        match=wanted[r['id']]
        if r['world_min']==match['world_min'] and r['world_max']==match['world_max']:continue
        assert r['role']=='column' and r['floor']==0 and r['id'].endswith('_2.5'),r['id']
        assert all(abs(match['world_min'][i]-r['world_min'][i]-(5. if i==0 else 0))<.001 for i in range(3))
        lo,hi=match['world_min'],match['world_max'];a=by[r['actor']]
        assert a.set_actor_location(unreal.Vector(*[(x+y)/2 for x,y in zip(lo,hi)]),False,True)
        r.update(world_min=lo,world_max=hi);changed.append(r['actor'])
    assert len(changed)==11
    old['boxes']=new['boxes'];old['review_cameras']=new['review_cameras']
    for row in new['review_cameras']:
        if row['camera'] in by:continue
        assert row['camera']=='CAM_V4_TopGallery'
        rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*row['position']),unreal.Vector(*row['look_at']))
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*row['position']),rot,False)
        a.set_actor_label(row['camera']);a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelV4/ReviewCameras'))
        a.set_editor_property('tags',[unreal.Name('HotelRedesign_20261008_V4')]);a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',row['fov'])
        old['new_actor_labels'].append(row['camera'])
    actors=list(sub.get_all_level_actors());refresh(actors);created=set(old['new_actor_labels'])
    old['expected_actor_states']={a.get_actor_label():actor_state(a) for a in actors if a.get_actor_label() in created}
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result=audit(world,old,baseline,actors);write('RefinementPreSaveAudit.json',result);assert result['passed'],result['errors'][:20]
    assert sha(mapfile)==oldhash;assert level.save_current_level();digest=sha(mapfile)
    build.update(map_sha256=digest,actor_count=len(actors),hotel_architecture=old,hotel_v4=old,
        hotel_openings_review_cameras=[r['camera'] for r in old['review_cameras']])
    write('BuildReport.json',build);write('Applied.json',dict(passed=True,map_sha256=digest,rooms=27,actor_count=len(actors)))
    write('ClearanceRefinement.json',dict(passed=True,source_map_sha256=oldhash,map_sha256=digest,
        moved_columns=changed,delta_x_cm=5,new_camera='CAM_V4_TopGallery',reason='Keep finished front piers behind the 220cm public gallery.'))
    unreal.log('HOTEL_V4_CLEARANCE_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write('ClearanceFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
