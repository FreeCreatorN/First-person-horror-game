"""Round only the existing toilet cistern and lid; preserve every other actor and face."""
import json, sys, traceback, shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state, sha
from PolishOldTownDetails import actor_bounds
from AuditOldTownHotelV4 import audit, refresh
import AuditOldTownHotelDetails as detail
import RefineOldTownSanitaryShapes as clone
import OldTownSanitaryFinishPlan as finish

WORK=ROOT/'Saved/CodexOutputs/SanitaryFinish_20261012'
SOURCE=ROOT/'Saved/CodexOutputs/SanitaryShapes_20261011'
SOURCE_SHA='96a927f42d52477d371665aad35ac8fdd85406eb42a91940cf047213cde8c44d'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
ASSETS='/Game/CodexGenerated/OldTown/Meshes/SanitaryFinish_20261012'
CAMERAS=['CAM_Shape_ToiletInterior201','CAM_Shape_ToiletFullPublic','CAM_Fixture_FaucetPublicWC','CAM_Basin_Guest201']

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,v):
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    assert not (WORK/'Applied.json').exists(),'Already applied; review the saved evidence.'
    assert finish.audit_recipe()['passed']
    build=read(SOURCE/'BuildReport.json');before=deepcopy(read(SOURCE/'AfterSnapshot.json'))
    assert sha(MAP)==SOURCE_SHA==build['map_sha256']==before['source_map_sha256']
    for file,digest in dict(before['shared_asset_sha256'],**build['new_asset_sha256']).items():
        assert sha(Path(file))==digest,file
    recorded=deepcopy(before['protected_map_sha256']);current=deepcopy(recorded)
    main_file=str(ROOT/'Content/Yastar/Maps/L_Main.umap')
    assert recorded[main_file]=='b20f1046a0d099a3f1baa4fdefa0ff6be6771fed0f8f30e4f6523f3fe63371d7'
    current[main_file]='629d295921d48a016aad82113e70eb740378b917120ed31354005c9c6bff5578'
    for file,digest in current.items():assert sha(Path(file))==digest,file
    before['protected_map_sha256']=deepcopy(current);build['protected_map_sha256']=deepcopy(current)
    assert len(before['actors'])==8014
    backup=WORK/'Before';backup.mkdir(parents=True,exist_ok=True)
    for n in ('BuildReport.json','AfterSnapshot.json','PreservationBaseline.json'):
        shutil.copy2(SOURCE/n,backup/n)
    shutil.copy2(MAP,backup/MAP.name);write('InputSnapshot.json',before)
    protected_backup=backup/'ProtectedMaps';protected_backup.mkdir(parents=True,exist_ok=True)
    main_copy=protected_backup/'L_Main.umap';shutil.copy2(main_file,main_copy)
    assert sha(main_copy)==current[main_file]
    write('ProtectedMapInputRebase.json',dict(passed=True,source_map_sha256=SOURCE_SHA,
          source='current_disk_before_map_apply',recorded_input=recorded,current_input=current,
          changes=[dict(file=main_file,previous_sha256=recorded[main_file],current_sha256=current[main_file])],
          preserved_current_copy=str(main_copy),preserved_current_copy_sha256=sha(main_copy)))
    recipe_file=ROOT/'SourceArt/OldTownSanitaryFinish_20261012/Recipe.json'
    recipe_file.parent.mkdir(parents=True,exist_ok=True)
    recipe_file.write_text(json.dumps(dict(schema=finish.SCHEMA,pieces=finish.build_pieces(),removals=finish.source_removal_specs()),ensure_ascii=False,indent=2),encoding='utf-8')
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert levels.load_level(TARGET)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert {n:actor_state(a) for n,a in by.items()}==before['actors']
    plan=deepcopy(build['hotel_v4'])
    clone.shapes=finish;clone.ASSETS=ASSETS
    mesh,report=clone.clone_fixture('Toilet')
    rows=[r for r in plan['placed_props'] if r.get('asset_key')=='Toilet']
    assert len(rows)==30
    changed={r['actor'] for r in rows}
    colliders=[c['actor'] for r in plan['placed_props'] if r.get('asset_key') in ('Toilet','Washbasin') for c in r['colliders']]
    assert len(colliders)==len(set(colliders))==60
    for r in rows:
        a=by[r['actor']];c=a.get_component_by_class(unreal.StaticMeshComponent)
        assert c.static_mesh.get_path_name()==report['source']
        assert c.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
        c.set_static_mesh(mesh);r['asset']=mesh.get_path_name();lo,hi=actor_bounds(a)
        for k,v in dict(world_min=lo,world_max=hi,bounds=[lo,hi],world_bounds_cm=[lo,hi]).items():r[k]=v
    plan['asset_catalog']['Toilet']=mesh.get_path_name().split('.')[0]
    placed={r['id']:r for r in rows}
    for r in plan['props']:
        if r.get('asset_key')=='Toilet':
            q=placed[r['id']];r['asset']=q['asset']
            for k in ('world_min','world_max','bounds','world_bounds_cm'):r[k]=deepcopy(q[k])
    actors=list(sub.get_all_level_actors());refresh(actors)
    current={a.get_actor_label():actor_state(a) for a in actors}
    assert set(current)==set(before['actors'])
    for n,old in before['actors'].items():
        expected=clone.expected_actor(old,mesh.get_path_name(),'Toilet') if n in changed else old
        assert current[n]==expected,'Unapproved actor change: '+n
    assert all(current[n]==before['actors'][n] for n in colliders)
    assert all(c in current for c in CAMERAS)
    plan['expected_actor_states']={n:current[n] for n in plan['new_actor_labels']}
    plan['source_map_sha256']=SOURCE_SHA
    baseline=deepcopy(read(SOURCE/'PreservationBaseline.json'));baseline['source_map_sha256']=SOURCE_SHA
    baseline['protected_map_sha256']=deepcopy(before['protected_map_sha256'])
    write('PreservationBaseline.json',baseline)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    pre=audit(world,plan,baseline,actors);write('PreSaveAudit.json',pre);assert pre['passed'],pre['errors'][:20]
    detail.WORK=WORK;pre_detail=detail.detail_audit(world,plan,actors)
    write('PreSaveDetailAudit.json',pre_detail);assert pre_detail['passed'],pre_detail['errors'][:20]
    optimization=dict(passed=True,source_map_sha256=SOURCE_SHA,changed_actors=sorted(changed),new_assets=[report],new_cameras=[],current_cameras=CAMERAS,preserved_fixture_collision_actors=sorted(colliders),unchanged_existing_actors=7984,recipe_file=str(recipe_file),recipe_sha256=sha(recipe_file),capture_directory=str(WORK/'CorrectedCaptures'),design_note='Only the old cistern and overlapped lid are replaced by closed rounded ceramic solids. The 0.3 cm embedded lid joint, flush lever and shoulder connections remain; every actor transform, existing cup, foot, seat and basin face is retained.')
    build.update(status='PENDING',source_map_sha256=SOURCE_SHA,actor_count=len(actors),hotel_v4=plan,hotel_architecture=plan,sanitary_finish_refinement=optimization,hotel_openings_review_cameras=CAMERAS,previous_evidence=str(SOURCE/'FinalReview.json'))
    build['new_asset_sha256'][report['file']]=report['sha256']
    write('PendingBuildReport.json',build)
    assert sha(MAP)==SOURCE_SHA and levels.save_current_level()
    digest=sha(MAP);build.update(status='PASS',map_sha256=digest)
    optimization.update(map_sha256=digest,geometry_revision_utc=datetime.now(timezone.utc).isoformat())
    write('BuildReport.json',build);write('FinishOptimizationReport.json',optimization);write('ArchitecturePlan.json',plan)
    write('Applied.json',dict(passed=True,map_sha256=digest,source_map_sha256=SOURCE_SHA,actor_count=len(actors),toilets=30,changed_actors=30,new_cameras=0))
    unreal.log('SANITARY_FINISH_APPLY_PASS '+digest)

if __name__=='__main__':
    try:main()
    except Exception:write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
