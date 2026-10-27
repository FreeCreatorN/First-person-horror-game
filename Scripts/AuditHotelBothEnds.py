"""Fresh readback of both screens; preserve all 7,993 pre-correction Actors."""
import sys,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelBothEndsCommon import *
from AuditOldTownHotelV4 import refresh,route_probe

def trace(world,start,end):
    hit=unreal.SystemLibrary.line_trace_single_for_objects(world,unreal.Vector(*start),unreal.Vector(*end),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],False,[],unreal.DrawDebugTrace.NONE)
    return hit.to_tuple() if hit is not None else None

def main():
    applied=read('Applied.json');assets=prev('Assets.json')
    assert applied['passed'] and native.sha(MAP)==applied['map_sha256']
    le,ae,world,actors,by=load();south=set(applied['new_labels']);north=set(applied['north_labels']);allnames=south|north
    assert len(actors)==7997 and len(south)==4 and len(north)==4
    assert {a.get_actor_label() for a in actors if TAG in [str(t) for t in a.tags]}==south
    bounds=[]
    for row in applied['plan']+assets['plan']:
        a=by[row['label']];c=a.static_mesh_component
        assert c.static_mesh.get_path_name()==assets['meshes'][row['mesh_key']]['asset']
        assert all(abs(x-y)<1.e-6 for x,y in zip(native.value(a.get_actor_location()),row['position']))
        assert all(abs(x-y)<1.e-6 for x,y in zip(native.value(a.get_actor_scale3d()),row['scale']))
        assert abs(a.get_actor_rotation().yaw-row['yaw'])<1.e-6
        assert c.get_collision_enabled()==unreal.CollisionEnabled.QUERY_AND_PHYSICS
        assert str(c.get_collision_profile_name())=='BlockAll' and not c.get_editor_property('override_materials')
        o,e,_=unreal.SystemLibrary.get_component_bounds(c)
        bounds.append(dict(label=row['label'],bounds=[[getattr(o,k)-getattr(e,k) for k in ('x','y','z')],[getattr(o,k)+getattr(e,k) for k in ('x','y','z')]]))
    for label in allnames:
        c=by[label].static_mesh_component
        assert c.get_collision_enabled()==unreal.CollisionEnabled.QUERY_AND_PHYSICS and str(c.get_collision_profile_name())=='BlockAll'
    refresh(actors)
    blocking=[]
    def checkray(key,start,end,expected):
        for a,b in ((start,end),(end,start)):
            hit=trace(world,a,b)
            owner=hit[10].get_owner().get_actor_label() if hit and hit[0] else None
            assert owner==expected,(key,a,b,owner,expected)
            blocking.append(dict(id=key,start=a,end=b,blocked_by=owner))
    for side,sign in [('North',1.),('South',-1.)]:
        for x in list(range(6650,10300,125))+[7650.,7775.,7900.,8025.,8150.]:
            for z in (40.,170.,240.):
                checkray(side+'_main',[x,sign*3780.,z],[x,sign*4050.,z],'OTS_Hotel_FrontBoundary_'+side+'Main')
        for y in (3350.,3500.,3750.):
            for z in (40.,170.,240.):
                checkray(side+'_west',[6500.,sign*y,z],[6740.,sign*y,z],'OTS_Hotel_FrontBoundary_'+side+'WestReturn')
                checkray(side+'_east',[10200.,sign*y,z],[10450.,sign*y,z],'OTS_Hotel_FrontBoundary_'+side+'EastReturn')
    ground=[]
    screens=[by[n] for n in allnames]
    for sign in (1.,-1.):
        for x,y in [(6800.,3900.),(7350.,3900.),(7900.,3900.),(8600.,3900.),(9800.,3900.),(6612.,3250.),(10320.,3350.)]:
            hit=unreal.SystemLibrary.line_trace_single_for_objects(world,unreal.Vector(x,sign*y,20),unreal.Vector(x,sign*y,-40),
                [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],False,screens,unreal.DrawDebugTrace.NONE)
            assert hit and hit.to_tuple()[0],(x,sign*y)
            ground.append(dict(x=x,y=sign*y,ground_z=hit.to_tuple()[5].z,wall_base_z=-3.))
    routes=[]
    for key,points,curb in [
        ('north_hotel_rear_escape',[[10190.,1000.,13.],[10190.,3650.,13.],[8850.,3650.,13.],[8850.,3350.,13.]],False),
        ('north_front_lane_approach',[[7900.,2700.,1.],[7900.,3100.,1.],[7900.,3650.,1.]],False),
        ('south_front_lane_approach',[[7900.,-2700.,1.],[7900.,-3100.,1.],[7900.,-3650.,1.]],False),
        ('south_hotel_rear_passage',[[10190.,-1000.,-1.],[10190.,-3650.,-1.],[8850.,-3650.,-1.],[8850.,-3525.,-1.]],False),
        ('south_forecourt_existing_12cm_curb',[[8850.,-3525.,-1.],[8850.,-3475.,11.],[8850.,-3350.,11.]],True)]:
        p=route_probe(world,points,curb);p['id']=key;p['existing_curb_step_allowed']=curb;routes.append(p)
    write('CollisionReadback.json',dict(passed=all(p['passed'] for p in routes),blocking_rays=blocking,ground=ground,routes=routes))
    assert all(p['passed'] for p in routes),'A physical access route failed; see CollisionReadback'
    original=[a for a in actors if a.get_actor_label() not in south]
    current=snap(original,'ReadbackOriginalActors',world);write('ReadbackOriginalActors.json',current)
    base.compare_snapshot(read('BeforeScene.json'),current)
    assert native.sha(MAP)==applied['map_sha256']
    for p,h in applied['reused_asset_sha256'].items():assert native.sha(Path(p))==h
    write('Readback.json',dict(passed=True,map_sha256=applied['map_sha256'],actor_count=len(actors),original_actors_native_exact=len(original),
        added_actor_count=4,total_boundary_actors=8,resource_packages_added_or_modified=0,mesh_bounds=bounds,
        blocked_visibility_and_collision_rays=len(blocking),clear_routes=len(routes),route_samples=sum(p['sample_count'] for p in routes),
        permanent_new_lights=0,original_camera_count_preserved=True,protection=protect(read('ProtectedBefore.json')['file_sha256'],True),no_save=True))
    unreal.log('HOTEL_BOTH_ENDS_READBACK_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ReadbackFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
