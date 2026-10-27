import sys,traceback
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
from HotelBothEndsCommon import *
def main():
    assert not (W/'Applied.json').exists()
    source=prev('FinalReview.json');assert source['passed'] and native.sha(MAP)==source['map_sha256']
    baseline=files()
    # The exact saved level AND every dependency still match the prior fresh
    # validation. Reuse its 7,989 original Native records; freshly inspect the
    # four north Actors. Never restore an old level or old asset file.
    oldfiles=prev('ProtectedBefore.json')['file_sha256'];oldfiles.update(prev('Assets.json')['new_asset_sha256']);oldfiles[str(MAP)]=source['map_sha256']
    assert baseline==oldfiles,'Current scene/dependency bytes changed; a new input baseline is required'
    write('ProtectedBefore.json',dict(file_sha256=baseline))
    assert read('PlacementReview.json')['passed']
    le,ae,world,actors,by=load();north_names=set(prev('Applied.json')['added_actor_labels']);assert len(actors)==7993
    north=snap([by[n] for n in north_names],'NorthSourceBaseline',world)
    expected=deepcopy(prev('ReadbackOriginalActors.json'))
    expected['actor_count']+=north['actor_count']
    for k in ('actors','actor_properties','exact_scene_components','lights','full_light_properties','full_existing_actor_native'):
        assert not set(expected[k])&set(north[k]);expected[k].update(north[k])
    write('BeforeScene.json',expected)
    write('BaselineReuseProof.json',dict(passed=True,source_map_sha256=source['map_sha256'],all_level_and_dependency_bytes_identical=True,
        reused_original_native_records=7989,fresh_north_records=4,reference_final_review_sha256=native.sha(PREV/'FinalReview.json')))
    backup=R/'Saved/CodexBackups'/('HotelBothEndsBefore_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    b=backup/MAP.name;shutil.copy2(MAP,b);assert native.sha(b)==source['map_sha256'];write('Backup.json',dict(file=str(b),sha256=native.sha(b)))
    plan=[]
    for row in prev('Assets.json')['plan']:
        d=deepcopy(row);d['label']=d['label'].replace('North','South');d['position'][1]*=-1;d['yaw']*=-1;d['scale'][1]*=-1;plan.append(d)
    meshes=prev('Assets.json')['meshes'];new=[]
    for row in plan:
        assert row['label'] not in by
        a=ae.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*row['position']),unreal.Rotator(pitch=0,yaw=row['yaw'],roll=0),False)
        a.set_actor_label(row['label']);a.set_folder_path('CodexGenerated/Hotel/FrontBoundary_20261021')
        a.set_editor_property('tags',[unreal.Name(TAG),unreal.Name('CodexGenerated_Hotel')])
        c=a.static_mesh_component;c.set_static_mesh(unreal.load_asset(meshes[row['mesh_key']]['asset']));c.set_mobility(unreal.ComponentMobility.STATIC)
        a.set_actor_scale3d(unreal.Vector(*row['scale']));c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS);new.append(a)
    joint=prev('Assets.json')['joint'];lo,hi=joint['lo'],joint['hi'];newlo=[lo[0],-hi[1],lo[2]];newhi=[hi[0],-lo[1],hi[2]]
    center=[(a+b)/2 for a,b in zip(newlo,newhi)];scale=[(b-a)/100 for a,b in zip(newlo,newhi)]
    a=ae.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*center),unreal.Rotator(0,0,0),False)
    a.set_actor_label(joint['label'].replace('North','South'));a.set_folder_path('CodexGenerated/Hotel/FrontBoundary_20261021');a.set_editor_property('tags',[unreal.Name(TAG),unreal.Name('CodexGenerated_Hotel')])
    c=a.static_mesh_component;c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'));c.set_material(0,unreal.load_asset(joint['material']));c.set_mobility(unreal.ComponentMobility.STATIC)
    a.set_actor_scale3d(unreal.Vector(*scale));c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS);new.append(a)
    actual=snap(actors,'PreSaveOriginalActors',world);write('PreSaveOriginalActors.json',actual);base.compare_snapshot(expected,actual)
    assert len(ae.get_all_level_actors())==7997
    protect(baseline);assert native.sha(MAP)==source['map_sha256'];assert le.save_current_level()
    write('Applied.json',dict(passed=True,target_level=TARGET,source_map_sha256=source['map_sha256'],map_sha256=native.sha(MAP),plan=plan,
        new_labels=[a.get_actor_label() for a in new],north_labels=sorted(north_names),actor_count=7997,original_actors_native_exact=7993,
        reused_asset_sha256=prev('Assets.json')['new_asset_sha256'],protection=protect(baseline,True)))
    unreal.log('HOTEL_BOTH_ENDS_APPLY_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
