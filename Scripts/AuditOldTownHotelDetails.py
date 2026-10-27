"""Fresh saved-world verification of grounded posts, pipes, hinges and high windows."""
import json,sys,traceback,math
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import sha,xyz,actor_state
from PolishOldTownDetails import actor_bounds
import AuditOldTownHotelV4 as architecture
WORK=ROOT/'Saved/CodexOutputs/HotelDetails_20261009'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,r):(WORK/n).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')

def detail_audit(world,plan,actors):
    by={a.get_actor_label():a for a in actors};boxes={r['id']:r for r in plan['placed_boxes']}
    design=plan['detail_design'];checks=[];errors=[]
    def check(n,ok,**data):
        checks.append(dict(name=n,passed=bool(ok),**data))
        if not ok:errors.append(n)
    posts=[r for r in plan['placed_boxes'] if r.get('detail_kind') in ('grounded_flight_post','platform_post')]
    plates=[r for r in plan['placed_boxes'] if r.get('detail_kind') in ('flight_baseplate','platform_baseplate')]
    hinges=[r for r in plan['placed_props'] if r.get('detail_kind')=='door_hinge_assembly']
    stair_windows=[r for r in plan['placed_windows'] if r.get('kind')=='stair']
    swings={r['actor'] for r in plan['placed_doors'] if r['kind']=='swing'}
    check('detail_design_constraints',design['constraints']['passed'])
    check('grounded_post_count',len(posts)==240,actual=len(posts))
    check('baseplate_count',len(plates)==240,actual=len(plates))
    check('complete_plate_support_evidence',
        {r['id'] for r in plates}=={r['plate'] for r in design['constraints']['plate_support_checks']}
        and len(design['constraints']['plate_support_checks'])==240)
    for evidence in design['constraints']['plate_support_checks']:
        plate=boxes[evidence['plate']];support=boxes[evidence['support']]
        lo,hi=actor_bounds(by[plate['actor']]);sl,sh=actor_bounds(by[support['actor']])
        ok=all(lo[i]>=sl[i]-.02 and hi[i]<=sh[i]+.02 for i in (0,1)) and lo[2]<sh[2] and hi[2]>sh[2]
        check('baseplate_supported:'+plate['id'],ok,bounds=[lo,hi],support_bounds=[sl,sh])
    for row in plan['placed_boxes']:
        if row.get('detail_kind') not in ('grounded_flight_post','platform_post'):continue
        plate=boxes[row['id']+'_Baseplate'];lo,hi=actor_bounds(by[row['actor']]);pl,ph=actor_bounds(by[plate['actor']])
        ok=all(lo[i]>=pl[i]-.02 and hi[i]<=ph[i]+.02 for i in (0,1)) and lo[2]<ph[2] and hi[2]>ph[2]
        check('post_seated:'+row['id'],ok)
    tubes={r['id']:r for r in plan['placed_props'] if r.get('detail_kind')=='round_handrail'}
    check('round_pipe_count',len(tubes)==60,actual=len(tubes))
    actual_endpoints={}
    for q in tubes.values():
        actor=by[q['actor']];direction=unreal.MathLibrary.get_up_vector(actor.get_actor_rotation())
        actual=xyz(direction);good=max(abs(a-b) for a,b in zip(actual,q['direction']))<.001
        check('pipe_axis:'+q['id'],good,direction=actual)
        centre=xyz(actor.get_actor_location());scale=xyz(actor.get_actor_scale3d())
        half_length=50.*scale[2]
        endpoints=[[centre[i]+sign*actual[i]*half_length for i in range(3)] for sign in (-1,1)]
        actual_endpoints[q['id']]=endpoints
        good=all(math.dist(endpoints[i],q['endpoints_cm'][i])<.02 for i in (0,1))
        check('pipe_physical_endpoints:'+q['id'],good,endpoints=endpoints)
        check('pipe_dimensions:'+q['id'],abs(scale[0]*100-q['diameter_cm'])<.02
            and abs(scale[1]*100-q['diameter_cm'])<.02
            and abs(scale[2]*100-q['length_cm'])<.02)
    check('connected_flight_count',len(design['constraints']['rail_endpoint_checks'])==18)
    for join in design['constraints']['rail_endpoint_checks']:
        q=tubes[join['pipe']]
        good=all(any(math.dist(actual_endpoints[q['id']][end],p)<.03 for p in actual_endpoints[join[key]])
            for end,key in ((0,'start_connects_to'),(1,'end_connects_to')))
        check('connected_sloped_pipe:'+q['id'],good,endpoints=actual_endpoints[q['id']])
    check('hinge_assembly_count',len(hinges)==2*len(swings)==124,actual=len(hinges))
    check('all_swing_doors_have_fixed_and_moving_hinges',
        all(sorted(r['parent_component'] for r in hinges if r['door_actor']==door)==['DoorHinge','OpeningRoot']
            for door in swings) and {r['door_actor'] for r in hinges}==swings)
    for row in hinges:
        actor=by[row['actor']];c=actor.get_component_by_class(unreal.StaticMeshComponent);parent=c.get_attach_parent()
        check('hinge_attached:'+row['id'],parent is not None and parent.get_owner()==by[row['door_actor']]
            and parent.get_name()==row['parent_component'] and c.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION,
            parent_component=parent.get_name() if parent else None)
        check('hinge_mobility:'+row['id'],c.get_editor_property('mobility')==(
            unreal.ComponentMobility.MOVABLE if row['parent_component']=='DoorHinge' else unreal.ComponentMobility.STATIC))
        check('hinge_local_pose:'+row['id'],all(abs(v)<.001 for v in xyz(c.get_editor_property('relative_location')))
            and all(abs(float(getattr(c.get_editor_property('relative_rotation'),k)))<.001 for k in ('pitch','yaw','roll'))
            and all(abs(v-1)<.001 for v in xyz(c.get_editor_property('relative_scale3d'))))
    check('stair_window_count',len(stair_windows)==12,actual=len(stair_windows))
    for row in plan['placed_windows']:
        if row.get('kind')!='stair':continue
        f=row['floor'];floor=plan['floor_z_cm'][f];mid=floor+183.625
        check('window_above_platform:'+row['id'],abs(row['position_cm'][2]-mid-80)<.01 and row['height']==75,
            window_bottom=row['position_cm'][2],half_landing=mid)
        ceiling=plan['floor_z_cm'][f+1]-20 if f<3 else 1480.
        check('window_below_slab:'+row['id'],row['position_cm'][2]+row['height']+4<ceiling)
        x,y,z=row['position_cm'];point=[x,y,z+row['height']/2]
        walls=[c.get_owner().get_actor_label() for c in architecture._capsule_components(world,point,3,8)
            if c.get_owner().get_actor_label().startswith('OTS_HotelV4_F%d_RearWall_'%f)]
        check('new_window_hole_clear:'+row['id'],not walls,blockers=walls)
        old=design['original_stair_windows'][row['id']];x,y,z=old['position_cm'];point=[x,y,z+30]
        walls=[c.get_owner().get_actor_label() for c in architecture._capsule_components(world,point,3,8)
            if c.get_owner().get_actor_label().startswith('OTS_HotelV4_F%d_RearWall_'%f)]
        check('old_window_hole_closed:'+row['id'],bool(walls),blockers=walls)
    check('floating_well_blocks_absent',not any('_WellGuard' in n or '_Handrail0_' in n or '_Handrail1_' in n for n in by if n.startswith('OTS_HotelV4_')))
    check('top_floor_well_guards_present',sum('F3_LandingPost' in n and not n.endswith('Baseplate') for n in by)==6)
    check('redundant_central_backwalls_absent',not any('_CentralSafetyStair_Back_' in n for n in by))
    before=read(WORK/'InputSnapshot.json')['actors']
    for row in plan['placed_doors']:
        check('original_door_state_preserved:'+row['id'],actor_state(by[row['actor']])==before[row['actor']])
    return dict(passed=not errors,target_level='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',checks=checks,errors=errors,
        statistics=dict(checks=len(checks),grounded_posts=len(posts),baseplates=len(plates),
            sloped_pipes=sum('SlopedPipe' in q['id'] for q in tubes.values()),total_pipes=len(tubes),
            hinge_equipped_doors=len({r['door_actor'] for r in hinges}),
            hinge_sets=sum(r['hinge_count'] for r in hinges if r['parent_component']=='OpeningRoot'),
            stair_windows=len(stair_windows)))

def main():
    architecture.WORK=WORK;architecture.main()
    build=read(WORK/'BuildReport.json');actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result=detail_audit(world,build['hotel_v4'],actors)
    digest=sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')
    result.update(map_sha256=digest,source='fresh_persisted_map_load',persisted_map_unchanged=digest==build['map_sha256'])
    write('DetailAudit.json',result);assert result['passed'] and result['persisted_map_unchanged'],result['errors'][:20]
    import InspectOldTownSurfaceInput as geometry
    geometry.WORK=WORK;geometry.STAGE='After';geometry.main()
    assert read(WORK/'AfterSummary.json')['passed']
    unreal.log('HOTEL_DETAILS_SAVED_AUDIT_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write('AuditFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
