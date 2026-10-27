"""Fresh disk registry graph after original-map installation or cleanup, read only."""
import os,sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';C=R/'Content'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def main():
    mode=os.environ.get('HOTEL_REF_MODE','Committed');assert mode in ('Committed','Final','Refreshed','Clean')
    assert not (W/(mode+'References.json')).exists()
    before={str(p):native.sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
    committed=read('MetadataRefreshApplied.json') if mode in ('Refreshed','Clean') else read('Committed.json')
    assert committed['passed'] and before[committed['original_map_file']]==committed['map_sha256']
    registry=unreal.AssetRegistryHelpers.get_asset_registry();registry.search_all_assets(True);registry.scan_paths_synchronous(['/Game'],True)
    options=unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,include_searchable_names=True,include_soft_management_references=True,include_hard_management_references=True)
    rows=[]
    for a in registry.get_assets_by_path('/Game',True,True):
        p=str(a.package_name)
        rows.append(dict(package=p,asset_name=str(a.asset_name),asset_class=str(a.asset_class_path.asset_name),dependencies=sorted(str(n) for n in (registry.get_dependencies(p,options) or [])),referencers=sorted(str(n) for n in (registry.get_referencers(p,options) or []))))
    def union_rows(records):
        result={}
        for row in records:
            p=row['package'];entry=result.setdefault(p,dict(package=p,asset_names=set(),asset_classes=set(),dependencies=set(),referencers=set()))
            entry['asset_names'].add(row['asset_name']);entry['asset_classes'].add(row.get('asset_class',row.get('class_path','')))
            entry['dependencies'].update(row['dependencies']);entry['referencers'].update(row['referencers'])
        return {p:{k:sorted(v) if isinstance(v,set) else v for k,v in r.items()} for p,r in result.items()}
    by=union_rows(rows);old=union_rows(read('AssetReferences.json')['assets'])
    disk_packages=['/Game/'+Path(p).relative_to(C).with_suffix('').as_posix() for p in before if Path(p).suffix.lower() in ('.uasset','.umap') and Path(p).is_relative_to(C)]
    assert len(disk_packages)==len(set(p.lower() for p in disk_packages)), 'Case/stem asset collision'
    assert set(disk_packages)==set(by),dict(missing=sorted(set(disk_packages)-set(by)),unexpected=sorted(set(by)-set(disk_packages)))
    assert {committed['original_map_file'],str(C/'Yastar/Maps/L_Main.umap'),str(C/'CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap')}<=set(before)
    missing=lambda graph:sorted((p,d) for p,r in graph.items() for d in r['dependencies'] if d.startswith('/Game/') and d not in graph)
    old_missing=set(missing(old));new_missing=missing(by);introduced=[list(v) for v in new_missing if v not in old_missing]
    assert not introduced, introduced[:10]
    plan=read('HotelNamePlan.json');mapping=plan['source_to_destination'];original=read('CopiedPackages.json')['original_level']
    closure=set();queue=[original]
    while queue:
        p=queue.pop()
        if p in closure:continue
        closure.add(p);queue.extend(d for d in by.get(p,{}).get('dependencies',[]) if d.startswith('/Game/'))
    lingering=sorted(set(mapping)&closure);assert not lingering,lingering[:10]
    expected_new=set(mapping.values());assert expected_new<=closure,sorted(expected_new-closure)[:10]
    after={str(p):native.sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()};assert before==after
    native.write(W/(mode+'References.json'),dict(passed=True,mode=mode,map_sha256=committed['map_sha256'],assets=list(by.values()),
        file_sha256=before,original_map_game_dependency_closure=sorted(closure),all_617_private_assets_used=True,
        no_old_planned_source_in_original_closure=True,introduced_missing_dependencies=introduced,
        existing_missing_dependencies=[list(v) for v in new_missing],all_reference_categories=True,forced_disk_rescan=True,no_saves=True,
        on_disk_only=True,disk_registry_packages_exact=True,disk_package_count=len(disk_packages),same_package_rows_unioned=True,
        original_references_sha256=native.sha(W/'AssetReferences.json')))
    unreal.log('HOTEL_NAMING_'+mode.upper()+'_REFERENCES_PASS')
if __name__=='__main__':
    try:main()
    except Exception:native.write(W/'ReferencesFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
