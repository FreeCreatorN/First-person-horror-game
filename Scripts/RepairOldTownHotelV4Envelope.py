"""Seal the owned envelope at slab edges without modifying the approved plan."""
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
    assert oldhash==build['map_sha256'];baseline=read(WORK/'PreservationBaseline.json')
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert level.load_level(build['target_level'])
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert all(actor_state(by[n])==state for n,state in old['expected_actor_states'].items())
    backup=WORK/'BeforeEnvelopeRepair';backup.mkdir(exist_ok=True)
    for p in (mapfile,WORK/'BuildReport.json',WORK/'ArchitectureAudit.json'):
        if not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
    wanted={r['id']:r for r in new['boxes']};assert set(wanted)=={r['id'] for r in old['placed_boxes']}
    changed=[]
    for r in old['placed_boxes']:
        match=wanted[r['id']]
        if r['world_min']==match['world_min'] and r['world_max']==match['world_max']:continue
        assert r['floor'] in (0,1,2) and any(r['id'].startswith('F%d_%s_'%(r['floor'],side)) for side in ('StreetWall','RearWall','SouthEndWall','NorthEndWall')),r['id']
        assert all(abs(r['world_min'][i]-match['world_min'][i])<.001 for i in range(3))
        assert all(abs(r['world_max'][i]-match['world_max'][i])<.001 for i in (0,1))
        assert abs(match['world_max'][2]-r['world_max'][2]-20)<.001
        lo,hi=match['world_min'],match['world_max'];a=by[r['actor']]
        assert a.set_actor_location(unreal.Vector(*[(x+y)/2 for x,y in zip(lo,hi)]),False,True)
        a.set_actor_scale3d(unreal.Vector(*[(y-x)/100 for x,y in zip(lo,hi)]))
        r.update(world_min=lo,world_max=hi);changed.append(r['actor'])
    assert changed
    old['boxes']=new['boxes'];actors=list(sub.get_all_level_actors());refresh(actors);created=set(old['new_actor_labels'])
    old['expected_actor_states']={a.get_actor_label():actor_state(a) for a in actors if a.get_actor_label() in created}
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result=audit(world,old,baseline,actors);write('EnvelopePreSaveAudit.json',result);assert result['passed'],result['errors'][:20]
    assert sha(mapfile)==oldhash;assert level.save_current_level();digest=sha(mapfile)
    build.update(map_sha256=digest,actor_count=len(actors),hotel_architecture=old,hotel_v4=old)
    write('BuildReport.json',build);write('Applied.json',dict(passed=True,map_sha256=digest,rooms=27,actor_count=len(actors)))
    write('EnvelopeRepair.json',dict(passed=True,source_map_sha256=oldhash,map_sha256=digest,changed_walls=changed,extended_top_cm=20))
    unreal.log('HOTEL_V4_ENVELOPE_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write('EnvelopeFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
