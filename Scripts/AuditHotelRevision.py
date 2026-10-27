"""Fresh persisted-map validation. Never save this level or existing assets."""
import sys,traceback,math
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelRevisionCommon import *
import OldTownDoorReuseCommon as reuse
from HotelRevisionHandles import _assert_mirrored
from OldTownMainLightingCommon import compare_world_transform
from OldTownHotelV4Plan import build_plan
from AuditOldTownHotelV4 import route_probe,refresh
from ApplyOldTownDoorReuse import actor_fields

def near(a,b,tol=.025):
    assert len(a)==len(b) and all(abs(x-y)<tol for x,y in zip(a,b)),(a,b)
def bound(c):
    o,e,_=unreal.SystemLibrary.get_component_bounds(c)
    return [[getattr(o,k)-getattr(e,k) for k in ('x','y','z')],[getattr(o,k)+getattr(e,k) for k in ('x','y','z')]]
def check_door(p,a):
    assert a.get_path_name()==p['original_actor_path']
    assert a.get_class().get_path_name().split('.')[0]==p['blueprint']
    assert actor_fields(a)==p['actor_fields'] and str(a.get_folder_path())==p['folder'] and [str(t) for t in a.tags]==p['tags']
    current=reuse.door_snapshot(a);expected=p['current_snapshot'];differences=[]
    for name,row in expected['components'].items():
        if name.startswith('Rear'):continue
        actual=current['components'][name]
        for key in row:
            if key=='world_transform':compare_world_transform(row[key],actual[key])
            elif actual[key]!=row[key]:differences.append(dict(component=name,field=key,expected=row[key],actual=actual[key]))
    assert not differences,(p['label'],differences)
    cs=components(a);rows=[]
    for row in p['rear']['rear_handles']:
        front=cs[row['original']];rear=cs[row['rear']];leaf=cs['DoorLeaf' if row['original']=='Handle' else row['original'].replace('Handle','Leaf')]
        assert rear.get_attach_parent()==front.get_attach_parent()==cs[row['parent']]
        rows.append(_assert_mirrored(front,leaf,rear))
    return dict(label=p['label'],existing_components_preserved=True,kind=p['rear']['kind'],rear_handles=rows)

def trace(world,start,end):
    hit=unreal.SystemLibrary.line_trace_single_for_objects(world,unreal.Vector(*start),unreal.Vector(*end),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],False,[],unreal.DrawDebugTrace.NONE)
    return hit.to_tuple() if hit is not None else None

def main():
    applied=read('Applied.json');assert applied['passed'] and native.sha(MAP)==applied['map_sha256']
    le,ae,world,actors,by=load();assert len(actors)==applied['actor_count']
    plan=applied['plan'];removed=set(plan['removed']);furniture=set(plan['furniture']);doors={p['label'] for p in applied['doors']};additions={r['label'] for r in plan['additions']}
    assert not removed&set(by)
    assert len(doors)==93 and len({by[n].get_class().get_path_name() for n in doors})==8
    doorproofs=[check_door(p,by[p['label']]) for p in applied['doors']]
    write('DoorReadback.json',dict(passed=True,doors=doorproofs,rear_handle_count=sum(len(p['rear_handles']) for p in doorproofs)))
    boxproofs=[]
    for row in plan['additions']:
        a=by[row['label']];own(a);c=a.static_mesh_component;bb=bound(c);near(bb[0],row['lo']);near(bb[1],row['hi'])
        assert c.get_material(0)==by[row['material_source']].static_mesh_component.get_material(0)
        assert c.get_collision_enabled()==unreal.CollisionEnabled.QUERY_AND_PHYSICS
        boxproofs.append(dict(label=row['label'],role=row['role'],bounds=bb,material=c.get_material(0).get_path_name()))
    assets=read('Assets.json');furnitureproofs=[]
    for name,row in assets['furniture'].items():
        a=by['OTS_HotelV4_'+name];c=a.static_mesh_component;bb=bound(c)
        assert c.static_mesh.get_path_name()==row['asset']
        near(native.value(a.get_actor_scale3d()),[1,1,1]);assert abs(bb[0][2]-11.)<.025 and abs(bb[1][2]-101.)<.025
        assert len(c.get_editor_property('override_materials'))==0
        assert all(c.get_material(i).get_path_name()==row['materials'][k] for i,k in enumerate(('wood','metal','ceramic','cloth')))
        furnitureproofs.append(dict(label=a.get_actor_label(),bounds=bb,below_rear_window_sill_cm=116.-bb[1][2],recognizable_facility=name))
    refresh(actors)
    walltraces=[]
    for row in plan['additions']:
        lo,hi=row['lo'],row['hi'];center=[(a+b)/2 for a,b in zip(lo,hi)]
        if row['role']=='front_wall':
            for z in (50.,120.,210.):
                hit=trace(world,[lo[0]-30,center[1],z],[hi[0]+30,center[1],z])
                assert hit and hit[0] and hit[10]==by[row['label']].static_mesh_component,(row['label'],hit)
                walltraces.append(dict(label=row['label'],height=z,blocked=True))
        elif row['role']=='landing_extension':
            hit=trace(world,[center[0],center[1],hi[2]+15],[center[0],center[1],lo[2]-15])
            assert hit and hit[0] and hit[10]==by[row['label']].static_mesh_component,(row['label'],hit)
    stairs=[]
    for row in build_plan()['stair_routes']:
        if row['stair_id'] not in ('South','North'):continue
        proof=route_probe(world,row['foot_waypoints'],True);proof.update(id=row['id'])
        stairs.append(proof)
    write('StairReadback.json',dict(passed=all(p['passed'] for p in stairs),scope='Both revised side stairs, three floor connections each; central geometry unchanged',routes=stairs))
    assert len(stairs)==6
    assert all(p['passed'] for p in stairs),'Stair support/headroom/capsule failure'
    # Re-exercise installed door closure and collision while keeping saved poses.
    import HotelDoorClosureCommon as closure
    old=closure.read('AppliedPlan.json')
    closureplan=dict(doors=[p for p in old['doors'] if p['label'] in doors])
    closureproof=closure.validate_closed(by,closureplan);write('ClosureReadback.json',closureproof)
    assert closureproof['tested_count']==93
    base.W=W;base.TAG='HotelRevision_NoExistingActorExclusion'
    full=snapshot(actors,'AfterRevision',world);write('AfterScene.json',full)
    actual=filtered(full,doors|furniture|additions);write('ReadbackOthers.json',actual)
    base.compare_snapshot(read('ExpectedOthers.json'),actual)
    # Preserve a full final checkpoint for the next continuation.
    assert native.sha(MAP)==applied['map_sha256']
    assert all(native.sha(Path(p))==h for p,h in applied['new_asset_sha256'].items())
    write('Readback.json',dict(passed=True,map_sha256=applied['map_sha256'],actor_count=len(actors),hotel_doors=93,shared_blueprints=8,
        rear_handles=sum(len(p['rear_handles']) for p in doorproofs),removed_count=len(removed),new_box_count=len(additions),furniture=furnitureproofs,
        boxes=boxproofs,front_wall_collision_traces=walltraces,stair_route_count=len(stairs),stair_route_samples=sum(p['sample_count'] for p in stairs),
        closed_door_count=93,all_other_actors_native_exact=True,protection=protect(read('ProtectedBefore.json')['file_sha256'],True),no_save=True))
    unreal.log('HOTEL_REVISION_READBACK_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ReadbackFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
