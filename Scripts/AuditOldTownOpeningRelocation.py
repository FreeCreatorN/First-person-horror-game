"""Fresh direct-path loads after the old opening directory is completely removed."""
import json
import shutil
import sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from InspectOldTownOpeningRelocation import WORK,OLD,NEW,template_state,package_file,write
from PolishOldTownHotel import actor_state,sha
from OldTownAssetRelocation import normalize_paths
import AuditOldTownHotelOperations as operations
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))


def main():
    inventory=read(WORK/'Inventory.json');moved=read(WORK/'Moved.json')
    old_dir=ROOT/('Content/'+OLD.removeprefix('/Game/'))
    assert not old_dir.exists(),'Finish locked-file/redirector cleanup before validation.'
    relocations=moved['relocations']
    registry=unreal.AssetRegistryHelpers.get_asset_registry();registry.search_all_assets(True)
    options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,
        include_searchable_names=True,include_soft_management_references=True,include_hard_management_references=True)
    report=dict(passed=False,old_folder=OLD,new_folder=NEW,checks=[],errors=[],maps=[],assets=[])
    def check(name,good,**details):
        report['checks'].append(dict(name=name,passed=bool(good),**details))
        if not good:report['errors'].append(name)
    check('old_directory_absent',not old_dir.exists())
    check('exact_destination_packages',len({p.split('.')[0] for p in unreal.EditorAssetLibrary.list_assets(NEW,True,False)})==11)
    for row in inventory['assets']:
        bp=unreal.load_asset(row['new']);cls=unreal.EditorAssetLibrary.load_blueprint_class(row['new'])
        check('new_blueprint:'+row['new'],isinstance(bp,unreal.Blueprint) and bp.get_path_name().split('.')[0]==row['new'])
        check('new_generated_class:'+row['new'],cls is not None and cls.get_path_name()==row['new']+'.'+row['new'].rsplit('/',1)[1]+'_C')
        check('unchanged_component_templates:'+row['new'],template_state(bp)==normalize_paths(row['templates'],relocations))
        old_refs=list(registry.get_referencers(unreal.Name(row['old']),options) or [])
        check('no_old_referencers:'+row['old'],not old_refs,referencers=[str(p) for p in old_refs])
        report['assets'].append(dict(old=row['old'],new=row['new'],new_file_sha256=sha(package_file(row['new']))))
    snapshots=read(WORK/'ActorSnapshots.json')
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for p in inventory['referencer_maps']:
        check('map_loaded_without_old_directory:'+p,level.load_level(p))
        current={a.get_actor_label():actor_state(a) for a in sub.get_all_level_actors()}
        expected=normalize_paths(snapshots[p],relocations)
        changed=[n for n,s in expected.items() if current.get(n)!=s]
        count=sum(v['class'].startswith(OLD+'/') for v in snapshots[p].values())
        check('map_actor_state_preserved:'+p,not changed and set(current)==set(expected),count=len(current),changed=changed[:8])
        check('all_migrated_actors_use_destination:'+p,all(current[n]['class'].startswith(NEW+'/') for n,v in snapshots[p].items() if v['class'].startswith(OLD+'/')),count=count)
        report['maps'].append(dict(level=p,actors=len(current),migrated_instances=count,
            recorded_actor_fields_preserved=not changed,source_map_sha256=inventory['source_map_sha256'][p],map_sha256=sha(package_file(p))))
    base=read(ROOT/'Saved/CodexOutputs/HotelOperations_20261006/BuildReport.json')
    build=normalize_paths(base,relocations)
    build.update(asset_relocations=relocations,source_map_sha256=inventory['source_map_sha256'][base['target_level']],
                 map_sha256=sha(package_file(base['target_level'])),previous_evidence=str(ROOT/'Saved/CodexOutputs/HotelOperations_20261006/FinalReview.json'))
    for path in build['protected_map_sha256']:
        package='/Game/'+str(Path(path).relative_to(ROOT/'Content')).replace('\\','/').removesuffix('.umap')
        if package in inventory['referencer_maps']:build['protected_map_sha256'][path]=sha(Path(path))
    build['reference_only_map_updates']=report['maps']
    source_baseline=ROOT/'Saved/CodexOutputs/HotelOperations_20261006/PreservationBaseline.json'
    if not (WORK/'PreservationBaseline.json').exists():shutil.copy2(source_baseline,WORK/'PreservationBaseline.json')
    operations.WORK=WORK
    check('active_map_loaded',level.load_level(build['target_level']))
    actors=list(sub.get_all_level_actors());operations.refresh(actors)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    physical=operations.audit(world,actors,build);write('OperationsAudit.json',physical)
    check('architecture_circulation_and_preservation',physical['passed'],errors=physical['errors'][:8])
    allowed={str(package_file(p).relative_to(ROOT/'Content')).replace('\\','/') for p in inventory['referencer_maps']}
    old_prefix=OLD.removeprefix('/Game/')+'/'
    changes=[];missing=[]
    for rel,h in inventory['content_sha256'].items():
        if rel in allowed or rel.startswith(old_prefix):continue
        f=ROOT/'Content'/rel
        if not f.exists():missing.append(rel)
        elif sha(f)!=h:changes.append(rel)
    # A concurrently open editor may save unrelated user assets. Never restore them.
    check('no_unrelated_packages_removed',not missing,missing=missing)
    report['other_saved_content_changes']=changes
    report['statistics']=dict(assets=11,maps=len(report['maps']),map_actors_checked=sum(r['actors'] for r in report['maps']),
        migrated_instances=sum(r['migrated_instances'] for r in report['maps']),operations=physical['statistics'])
    report['passed']=not report['errors'];write('RelocationValidation.json',report)
    assert report['passed'],report['errors'][:12]
    write('BuildReport.json',build)
    unreal.log('OPENING_RELOCATION_FINAL_AUDIT_PASS '+str(report['statistics']))


if __name__=='__main__':main()
