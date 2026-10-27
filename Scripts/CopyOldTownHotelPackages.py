"""Create only private Hotel-named packages and a staged map; never alter sources."""
import sys,json,shutil,traceback
from pathlib import Path
from datetime import datetime,timezone
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017'
C=R/'Content';HOTEL=C/'CodexGenerated/Hotel'
ORIGINAL='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
STAGED='/Game/CodexGenerated/Hotel/Maps/L_Hotel_Stage'
MAP=C/'Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,x):native.write(W/n,x)
def main():
    assert not (W/'CopiedPackages.json').exists() and not HOTEL.exists(),'Private destination must start absent'
    plan=read('HotelNamePlan.json');assert plan['passed'] and plan['planned_copy_count']==617 and plan['frozen_package_count']==0
    assert native.sha(MAP)==plan['source_map_sha256']
    before=read('ProtectedBeforeAfterRestore.json')['file_sha256']
    assert all(native.sha(Path(p))==h for p,h in before.items())
    assert read('BeforeScene1.Completion.json')['normal_zero_exit']
    assert len(read('BeforeScene.json')['full_existing_actor_native'])==7986
    for file,digest in plan['input_sha256'].items():assert native.sha(Path(file))==digest
    remapping=dict(plan['source_to_destination']);assert len(remapping)==617
    remapping[ORIGINAL]=STAGED
    expected={str(Path(r['destination_file'])) for r in plan['mappings']}
    expected.add(str(HOTEL/'Maps/L_Hotel_Stage.umap'))
    assert len(expected)==618
    for row in plan['mappings']:
        source=Path(row['source_file']);destination=Path(row['destination_file'])
        assert source.is_relative_to(C/'CodexGenerated/OldTown') and destination.is_relative_to(HOTEL)
        assert native.sha(source)==row['source_sha256']==before[str(source)] and not destination.exists()
    backup=R/'Saved/CodexBackups'/('HotelNamesBeforeCopy_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True,exist_ok=False)
    source_files={Path(r['source_file']) for r in plan['mappings']}|{MAP}
    backup_proof=[]
    for source in sorted(source_files):
        target=backup/'Content'/source.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);assert native.sha(target)==before[str(source)]
        backup_proof.append(dict(source=str(source),backup=str(target),sha256=before[str(source)]))
    write('Backup.json',dict(passed=True,created_before_asset_copy=True,directory=str(backup),map_sha256=native.sha(MAP),files=backup_proof))
    result=json.loads(unreal.HotelPackageCopyLibrary.patch_packages_exact(remapping,list(remapping)))
    write('HeaderCopyProof.json',result)
    assert result['passed'] and result['exact_write_set'] and not result['dependency_gathering']
    actual={str(p):native.sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
    assert all(actual.get(p)==h for p,h in before.items())
    assert set(actual)-set(before)==expected
    assert len(result['patched_files'])==618 and not result['error_files']
    write('CopiedPackages.json',dict(passed=True,source_map_sha256=plan['source_map_sha256'],original_level=ORIGINAL,staged_level=STAGED,
        private_asset_count=617,window_count=348,window_blueprints=8,door_count=124,door_blueprints=10,
        package_remapping=remapping,new_asset_sha256={p:actual[p] for p in sorted(expected)},
        all_existing_content_config_unchanged=True,no_source_asset_save=True,no_redirectors_created=True,
        plan_sha256=native.sha(W/'HotelNamePlan.json')))
    unreal.log('HOTEL_EXACT_PRIVATE_PACKAGE_COPY_PASS 618')
if __name__=='__main__':
    try:main()
    except Exception:native.write(W/'CopyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
