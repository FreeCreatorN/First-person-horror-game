"""Add four new Actors; compare every original Actor before the sole map save."""
import sys,traceback,shutil
from pathlib import Path
from datetime import datetime,timezone
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelFrontBoundaryCommon import *
def add(ae,label,location,yaw,mesh,scale,materials=None):
    a=ae.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*location),unreal.Rotator(pitch=0,yaw=yaw,roll=0),False);assert a
    a.set_actor_label(label);a.set_folder_path('CodexGenerated/Hotel/FrontBoundary_20261021')
    a.set_editor_property('tags',[unreal.Name(TAG),unreal.Name('CodexGenerated_Hotel')])
    c=a.static_mesh_component;c.set_static_mesh(mesh);c.set_mobility(unreal.ComponentMobility.STATIC)
    a.set_actor_scale3d(unreal.Vector(*scale))
    if materials:
        for i,m in enumerate(materials):c.set_material(i,m)
    c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    return a
def main():
    assert not (W/'Applied.json').exists()
    inspection=read('Inspection.json');assets=read('Assets.json');assert assets['passed']
    review=read('PlanReview/FreshPlacementReview.json');assert review['passed']
    assert native.sha(MAP)==inspection['source_map_sha256']==assets['source_map_sha256']
    baseline=read('ProtectedBefore.json')['file_sha256'];protect(baseline)
    for p,h in assets['new_asset_sha256'].items():assert native.sha(Path(p))==h
    backup=R/'Saved/CodexBackups'/('HotelFrontBoundaryBefore_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    b=backup/MAP.name;shutil.copy2(MAP,b);assert native.sha(b)==inspection['source_map_sha256']
    write('Backup.json',dict(source=str(MAP),file=str(b),sha256=native.sha(b)))
    le,ae,world,actors,by=load();assert len(actors)==inspection['actor_count']
    assert not any(TAG in [str(t) for t in a.tags] for a in actors)
    new=[]
    for row in assets['plan']:
        assert row['label'] not in by
        mesh=unreal.load_asset(assets['meshes'][row['mesh_key']]['asset']);assert mesh
        new.append(add(ae,row['label'],row['position'],row['yaw'],mesh,row['scale']))
    joint=assets['joint'];lo,hi=joint['lo'],joint['hi'];center=[(a+b)/2 for a,b in zip(lo,hi)];scale=[(b-a)/100 for a,b in zip(lo,hi)]
    new.append(add(ae,joint['label'],center,0.,unreal.load_asset('/Engine/BasicShapes/Cube'),scale,[unreal.load_asset(joint['material'])]))
    # Snapshot only the exact original UObject set, so additions cannot hide a
    # removal, rename, changed light, component or user Blueprint property.
    actual=snap(actors,'PreSaveOriginalActors',world);write('PreSaveOriginalActors.json',actual)
    base.compare_snapshot(read('BeforeScene.json'),actual)
    assert len(ae.get_all_level_actors())==len(actors)+4
    protect(baseline);assert native.sha(MAP)==inspection['source_map_sha256']
    assert le.save_current_level()
    protected=protect(baseline,True)
    write('Applied.json',dict(passed=True,target_level=TARGET,source_map_sha256=inspection['source_map_sha256'],map_sha256=native.sha(MAP),
        actor_count_before=len(actors),actor_count_after=len(actors)+4,added_actor_labels=[a.get_actor_label() for a in new],
        original_actor_count_exact=len(actors),all_original_actors_native_exact=True,new_asset_sha256=assets['new_asset_sha256'],protection=protected))
    unreal.log('HOTEL_FRONT_BOUNDARY_APPLY_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
