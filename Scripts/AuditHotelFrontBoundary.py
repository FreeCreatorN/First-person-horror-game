"""Fresh saved-map proof: exact original scene, closed screen and clear routes."""
import sys,traceback,math
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelFrontBoundaryCommon import *
from AuditOldTownHotelV4 import refresh,route_probe

def trace(world,start,end):
    hit=unreal.SystemLibrary.line_trace_single_for_objects(world,unreal.Vector(*start),unreal.Vector(*end),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],False,[],unreal.DrawDebugTrace.NONE)
    return hit.to_tuple() if hit is not None else None
def main():
    applied=read('Applied.json');assets=read('Assets.json');inspection=read('Inspection.json')
    assert applied['passed'] and native.sha(MAP)==applied['map_sha256']
    le,ae,world,actors,by=load();newnames=set(applied['added_actor_labels'])
    new=[a for a in actors if TAG in [str(t) for t in a.tags]]
    assert {a.get_actor_label() for a in new}==newnames and len(actors)==inspection['actor_count']+4
    boxes=[]
    for row in assets['plan']:
        a=by[row['label']];c=a.static_mesh_component;record=assets['meshes'][row['mesh_key']]
        assert c.static_mesh.get_path_name()==record['asset']
        assert all(abs(x-y)<1.e-6 for x,y in zip(native.value(a.get_actor_location()),row['position']))
        assert all(abs(x-y)<1.e-6 for x,y in zip(native.value(a.get_actor_scale3d()),row['scale']))
        assert abs(a.get_actor_rotation().yaw-row['yaw'])<1.e-6
        assert c.get_collision_enabled()==unreal.CollisionEnabled.QUERY_AND_PHYSICS
        assert str(c.get_collision_profile_name())=='BlockAll'
        assert len(c.get_editor_property('override_materials'))==0
        o,e,_=unreal.SystemLibrary.get_component_bounds(c)
        boxes.append(dict(label=row['label'],bounds=[[getattr(o,k)-getattr(e,k) for k in ('x','y','z')],[getattr(o,k)+getattr(e,k) for k in ('x','y','z')]],
            materials=[c.get_material(i).get_path_name() for i in range(c.get_num_materials())]))
    refresh(actors)
    blocking=[]
    # Sample the entire solid sight screen, including the centre lap of the gate.
    for x in list(range(6650,10300,125))+[7650.,7775.,7900.,8025.,8150.]:
        for z in (40.,170.,240.):
            hit=trace(world,[x,3780.,z],[x,4050.,z])
            assert hit and hit[0] and hit[10].get_owner().get_actor_label() in newnames,(x,z,str(hit))
            blocking.append(dict(x=x,z=z,blocked_by=hit[10].get_owner().get_actor_label()))
    ground=[]
    for x,y in [(6800.,3900.),(7350.,3900.),(7900.,3900.),(8600.,3900.),(9800.,3900.),(6612.,3250.),(10320.,3350.)]:
        hit=unreal.SystemLibrary.line_trace_single_for_objects(world,unreal.Vector(x,y,20),unreal.Vector(x,y,-40),
            [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],False,new,unreal.DrawDebugTrace.NONE)
        assert hit and hit.to_tuple()[0],(x,y)
        ground.append(dict(x=x,y=y,ground_z=hit.to_tuple()[5].z,wall_base_z=-3.))
    routes=[]
    for key,points in [
        ('hotel_rear_escape',[[10190.,1000.,13.],[10190.,3650.,13.],[8850.,3650.,13.],[8850.,3350.,13.]]),
        ('front_lane_approach',[[7900.,2700.,1.],[7900.,3100.,1.],[7900.,3650.,1.]])]:
        p=route_probe(world,points,False);p['id']=key;routes.append(p)
    write('CollisionReadback.json',dict(passed=all(p['passed'] for p in routes),blocking_rays=blocking,ground=ground,routes=routes))
    assert all(p['passed'] for p in routes),'Existing access route was blocked'
    original=[a for a in actors if a.get_actor_label() not in newnames]
    current=snap(original,'ReadbackOriginalActors',world);write('ReadbackOriginalActors.json',current)
    base.compare_snapshot(read('BeforeScene.json'),current)
    assert native.sha(MAP)==applied['map_sha256']
    for p,h in assets['new_asset_sha256'].items():assert native.sha(Path(p))==h
    write('Readback.json',dict(passed=True,map_sha256=applied['map_sha256'],actor_count=len(actors),original_actors_native_exact=len(original),
        added_actor_count=4,meshes=3,new_mesh_bounds=boxes,blocked_visibility_rays=len(blocking),clear_routes=len(routes),route_samples=sum(p['sample_count'] for p in routes),
        permanent_new_lights=0,original_camera_count_preserved=True,protection=protect(read('ProtectedBefore.json')['file_sha256'],True),no_save=True))
    unreal.log('HOTEL_FRONT_BOUNDARY_READBACK_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ReadbackFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
