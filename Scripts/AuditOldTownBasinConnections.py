"""Fresh saved-world regression and actual render geometry for fixture repair."""
import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
WORK=ROOT/'Saved/CodexOutputs/BasinConnections_20261011'
def write(n,v):(WORK/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    import AuditOldTownHotelDetails as audit
    audit.WORK=WORK;audit.main()
    from PolishOldTownHotel import actor_state,sha
    from RepairOldTownBasinConnections import collision_signature
    build=json.loads((WORK/'BuildReport.json').read_text(encoding='utf-8-sig'))
    before=json.loads((WORK/'InputSnapshot.json').read_text(encoding='utf-8-sig'))['actors']
    after=json.loads((WORK/'AfterSnapshot.json').read_text(encoding='utf-8-sig'))['actors']
    repair=build['basin_connection_repair'];targets=set(repair['actors']);cameras={r['camera'] for r in repair['new_cameras']}
    checks=[];errors=[]
    def check(n,ok,**data):
        checks.append(dict(name=n,passed=bool(ok),**data))
        if not ok:errors.append(n)
    check('complete_actor_manifest',set(after)==set(before)|cameras)
    for n,old in before.items():
        import copy
        expected=copy.deepcopy(old)
        if n in targets:
            for c in expected['components']:
                if c.get('mesh')==repair['source']:c['mesh']=repair['asset']
        check('only_approved_state_change:'+n,after.get(n)==expected)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by={a.get_actor_label():a for a in actors}
    original=unreal.load_asset(repair['source']);fixed=unreal.load_asset(repair['asset'])
    check('mesh_collision_unchanged',collision_signature(original)==collision_signature(fixed)==repair['collision_signature'])
    for n in targets:
        c=by[n].get_component_by_class(unreal.StaticMeshComponent)
        check('fixture_mesh_and_no_collision:'+n,c.static_mesh==fixed and c.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION)
    for n in repair['unchanged_collision_actors']:check('independent_fixture_collision_unchanged:'+n,actor_state(by[n])==before[n])
    check('original_shared_basin_read_only',sha(Path(repair['source_file']))==repair['source_sha256'])
    digest=sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')
    check('persisted_map_unchanged',digest==build['map_sha256'])
    result=dict(passed=not errors,target_level=build['target_level'],map_sha256=digest,source='fresh_persisted_map_load',persisted_map_unchanged=digest==build['map_sha256'],checks=checks,errors=errors,statistics=dict(checks=len(checks),basins=len(targets),unchanged_existing_actors=len(before)-len(targets),unchanged_fixture_collision_actors=len(repair['unchanged_collision_actors'])))
    write('BasinSavedAudit.json',result);assert result['passed'],errors[:10]
    unreal.log('BASIN_SAVED_AUDIT_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:write('BasinAuditFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
