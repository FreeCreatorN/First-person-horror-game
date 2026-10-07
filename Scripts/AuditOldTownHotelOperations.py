"""Verify imported operation props, unobstructed architecture, and exact preservation."""
import json
import math
import sys
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state, sha, xyz
from PolishOldTownDetails import actor_bounds
from AuditOldTownHotelArchitecture import audit as architecture_audit
from ValidateEnterableStreet import refresh_world_collision
from OldTownAssetRelocation import normalize_paths
WORK = ROOT/'Saved/CodexOutputs/HotelOperations_20261006'
SOURCE = ROOT/'SourceArt/OldTownHotelOperations_20261006'
TAG = 'HotelOperations_20261006'


def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def write(name,data): (WORK/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def refresh(actors):
    profiles=[(c,str(c.get_collision_profile_name())) for a in actors for c in a.get_components_by_class(unreal.PrimitiveComponent)]
    refresh_world_collision(actors)
    for c,profile in profiles:
        if profile!='Custom' and str(c.get_collision_profile_name())!=profile:
            c.set_collision_profile_name(profile)


def audit(world,actors,build):
    arch=architecture_audit(world,actors,build)
    write('ArchitectureAudit.json',arch)
    result=dict(passed=False,map_sha256=build['map_sha256'],checks=[],errors=[],statistics={})
    def check(name,good,**details):
        result['checks'].append(dict(name=name,passed=bool(good),**details))
        if not good: result['errors'].append(name)
    check('architecture_and_all_routes',arch['passed'],errors=arch['errors'][:12])
    by={a.get_actor_label():a for a in actors}
    baseline=read(WORK/'PreservationBaseline.json')
    changed=[n for n,s in baseline['actors'].items() if n not in by or actor_state(by[n])!=normalize_paths(s,build.get('asset_relocations',[]))]
    check('all_previous_actors_preserved',not changed,count=len(baseline['actors']),changed=changed[:12])
    if changed:
        n=changed[0]
        result['preservation_difference']=dict(actor=n,before=baseline['actors'][n],after=actor_state(by[n]) if n in by else None)
    added=set(by)-set(baseline['actors'])
    check('exact_additions',added==set(build['hotel_operations']['new_actor_labels']),unexpected=sorted(added-set(build['hotel_operations']['new_actor_labels'])))
    modified=[p for p,h in baseline['shared_asset_sha256'].items() if sha(Path(p))!=h]
    check('previous_assets_unchanged',not modified,count=len(baseline['shared_asset_sha256']),changed=modified)
    for row in build['hotel_operations']['placed_props']:
        a=by.get(row['actor'])
        good=a is not None
        details={}
        if good:
            actual=actor_bounds(a)
            error=max(abs(actual[j][i]-row['world_bounds_cm'][j][i]) for j in (0,1) for i in range(3))
            c=a.get_component_by_class(unreal.StaticMeshComponent)
            good=error<.15 and c.static_mesh.get_path_name()==row['asset']
            good=good and math.dist(xyz(a.get_actor_scale3d()),row['actor_scale'])<.001
            good=good and str(c.get_collision_profile_name())=='NoCollision'
            details=dict(bounds_error_cm=error,actual=actual,expected=row['world_bounds_cm'])
        check('measured_prop:'+row['id'],good,**details)
    for row in build['hotel_operations']['imports']:
        mesh=unreal.load_asset(row['asset'])
        check('source_provenance:'+row['name'],mesh is not None and sha(SOURCE/row['file'])==row['source_sha256'] and
              unreal.EditorAssetLibrary.get_metadata_tag(mesh,TAG+'_SourceSHA256')==row['source_sha256'])
        check('material_slots:'+row['name'],mesh is not None and all(mesh.get_material(i).get_path_name()==m for i,m in enumerate(row['material_assets'])))
    check('no_transient_actors',not any(a.get_actor_label().startswith(('OTS_TransientDoorTest_','OTS_TemporaryInspection_')) for a in actors))
    result['passed']=not result['errors']
    result['statistics']=dict(checks=len(result['checks']),architecture_checks=arch['statistics']['checks'],
        route_samples=arch['statistics']['route_samples'],stair_samples=arch['statistics']['stair_samples'],
        preserved_actors=len(baseline['actors']),new_actors=len(added),props=len(build['hotel_operations']['placed_props']))
    return result


def main():
    build=read(WORK/'BuildReport.json')
    mapfile=ROOT/('Content/'+build['target_level'].removeprefix('/Game/')+'.umap')
    assert sha(mapfile)==build['map_sha256']
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    refresh(actors)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    report=audit(world,actors,build)
    write('OperationsAudit.json',report)
    assert report['passed'],report['errors'][:12]
    unreal.log('HOTEL_OPERATIONS_RELOAD_PASS '+str(report['statistics']))


if __name__=='__main__': main()
