"""Refine the saved repair without changing its physical design or user state."""
import json,sys,shutil,traceback
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha
from OldTownWindowSurfaceRepair import apply_window,RECIPE_VERSION
from OldTownSurfaceMeshClones import clone_and_separate
from AuditOldTownHotelV4 import audit,refresh
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
MARKER='Refined.json'
BACKUP='BeforeRefinement'
REFINE_TOOLBOX=True

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,d):(WORK/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    assert not (WORK/MARKER).exists(),'Refinement already saved; use fresh audit.'
    build=read(WORK/'BuildReport.json');plan=build['hotel_v4'];baseline=read(WORK/'PreservationBaseline.json')
    mapfile=ROOT/('Content/'+build['target_level'][6:]+'.umap');before_hash=sha(mapfile)
    snapshot=read(WORK/'AfterSnapshot.json')
    assert before_hash==build['map_sha256']==snapshot['source_map_sha256']
    backup=WORK/BACKUP;backup.mkdir(exist_ok=True)
    for p in [mapfile]+[WORK/n for n in ('BuildReport.json','ArchitecturePlan.json','PreservationBaseline.json',
        'Applied.json','RepairReport.json','AfterSnapshot.json','AfterSummary.json','GeometryAfter.json',
        'ArchitectureAudit.json','SavedScan.json','SavedScanOcclusion.json','SavedScanSummary.json')]:
        if p.exists() and not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(build['target_level'])
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors())
    by={a.get_actor_label():a for a in actors};states={n:actor_state(a) for n,a in by.items()}
    assert states==snapshot['actors'],'Saved repair changed after inspected baseline.'
    refresh(actors)
    window_reports=[];windows=[]
    for r in plan['placed_windows']:
        row,report=apply_window(by[r['actor']],r);windows.append(row);window_reports.append(report)
    plan['placed_windows']=windows
    toolbox=by['OTS_MainHomeProp_Toolbox_01'];component=toolbox.get_component_by_class(unreal.StaticMeshComponent)
    source=unreal.load_asset('/Game/Yastar/Meshes/Storage/SM_OTS_Mod_Toolbox');assert source
    old_toolbox_asset=component.static_mesh.get_path_name()
    if REFINE_TOOLBOX:
        clone,mesh_report=clone_and_separate(source,plane_tolerance_cm=.05)
        component.set_static_mesh(clone)
    else:
        clone=component.static_mesh;mesh_report=None
    actors=list(sub.get_all_level_actors());refresh(actors);current={a.get_actor_label():actor_state(a) for a in actors}
    assert set(current)==set(states)
    changed=[n for n in current if states[n]!=current[n]]
    allowed={r['actor'] for r in windows}|{toolbox.get_actor_label()}
    assert set(changed)<=allowed
    for n in changed:
        old=deepcopy(states[n]);new=current[n]
        for oc,nc in zip(old['components'],new['components']):
            assert oc['name']==nc['name']
            if n==toolbox.get_actor_label() or oc['name'].startswith('Frame'):oc['mesh']=nc['mesh']
        assert old==new,'Refinement changed non-mesh state: '+n
    plan['expected_actor_states']={n:current[n] for n in plan['new_actor_labels']}
    baseline['allowed_surface_overrides'][toolbox.get_actor_label()]=current[toolbox.get_actor_label()]
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result=audit(world,plan,baseline,actors);write('RefinementPreSaveAudit.json',result)
    assert result['passed'],result['errors'][:20]
    repair=build['surface_repair'];repair['window_repairs']=window_reports
    for r in repair['mesh_swaps']:
        if r['id']=='OTS_MainHomeProp_Toolbox_01::StaticMeshComponent0':
            r['previous_repair_asset']=r['asset'];r['asset']=clone.get_path_name()
    refinement=dict(passed=True,source_map_sha256=before_hash,changed_actor_count=len(changed),changed_actor_labels=changed,
        window_frame_recipe=RECIPE_VERSION,frame_edge_retreat_cm=.25,
        toolbox_previous_asset=old_toolbox_asset,toolbox=mesh_report,
        actor_transforms_materials_and_simple_collision_preserved=True,created_utc=datetime.now(timezone.utc).isoformat())
    repair.setdefault('refinement_history',[]).append(refinement)
    repair['refinement']=refinement
    new_assets=build['new_asset_sha256']
    if mesh_report:new_assets[mesh_report['file']]=mesh_report['sha256']
    for wr in window_reports:
        for r in wr['new_assets']:
            p=ROOT/('Content/'+r['asset'].split('.')[0][6:]+'.uasset');new_assets[str(p)]=sha(p)
    for p,h in baseline['shared_asset_sha256'].items():assert sha(Path(p))==h,p
    for p,h in baseline['protected_map_sha256'].items():assert sha(Path(p))==h,p
    assert sha(mapfile)==before_hash;assert levels.save_current_level()
    digest=sha(mapfile);refinement['map_sha256']=digest
    build.update(map_sha256=digest,actor_count=len(actors),hotel_v4=plan,hotel_architecture=plan,surface_repair=repair)
    write('BuildReport.json',build);write('ArchitecturePlan.json',plan);write('PreservationBaseline.json',baseline)
    write('RepairReport.json',repair);write(MARKER,refinement)
    applied=read(WORK/'Applied.json');applied['map_sha256']=digest;applied['refinement']=str(WORK/MARKER);write('Applied.json',applied)
    unreal.log('SURFACE_REFINEMENT_PASS '+digest)

if __name__=='__main__':
    try:main()
    except Exception:
        write('RefinementFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
