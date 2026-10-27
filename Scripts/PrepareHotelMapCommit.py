"""Create a logical-original map candidate under Saved; never overwrite Content."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';C=R/'Content'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,x):native.write(W/n,x)
def main():
    assert not (W/'PreparedCommit.json').exists()
    copied=read('CopiedPackages.json');assert copied['passed'] and read('StagedAudit.json')['passed']
    assert read('StagedAudit2.Completion.json')['normal_zero_exit']
    assets=read('AssetCopyVerification3.json');assert assets['passed']
    assert read('AssetsAudit3.Completion.json')['normal_zero_exit']
    original=copied['original_level'];staged=copied['staged_level']
    original_file=C/(original.removeprefix('/Game/')+'.umap')
    assert native.sha(original_file)==copied['source_map_sha256']
    effective=read('EffectivePrivateHashes.json');assert effective['passed']
    assert effective['initial_copy_sha256']==native.sha(W/'CopiedPackages.json')
    assert effective['correction_report_sha256']==native.sha(W/'PrivateAssetCorrections.json')
    assert read('MetadataFix5.Completion.json')['normal_zero_exit']
    assert all(native.sha(Path(p))==h for p,h in effective['new_asset_sha256'].items())
    plan=read('HotelNamePlan.json');temporary_references=[]
    for row in plan['mappings']:
        data=Path(row['destination_file']).read_bytes()
        if staged.encode() in data or staged.encode('utf-16-le') in data:
            temporary_references.append(row['destination_package'])
    write('TemporaryWorldReferenceScan.json',dict(passed=not temporary_references,source=staged,checked_private_assets=617,temporary_world_references=temporary_references))
    assert not temporary_references,'Private assets must not depend on a temporary map'
    output=W/'CommitCandidate'
    assert not output.exists()
    result=json.loads(unreal.HotelPackageCopyLibrary.patch_packages_to_saved({staged:original},[staged],str(output)))
    write('MapCommitPatchProof.json',result)
    assert result['passed'] and result['writes_only_saved'] and result['expected_written_files']==1
    candidate=output/'Content'/(original.removeprefix('/Game/')+'.umap')
    assert candidate.exists() and native.sha(original_file)==copied['source_map_sha256']
    baseline=read('ProtectedBeforeAfterRestore.json')['file_sha256']
    assert all(native.sha(Path(p))==h for p,h in baseline.items())
    write('PreparedCommit.json',dict(passed=True,original_map_file=str(original_file),original_map_sha256=copied['source_map_sha256'],
        candidate_file=str(candidate),candidate_sha256=native.sha(candidate),candidate_logical_package=original,
        all_existing_content_config_unchanged=True,staged_audit_passed=True,asset_audit_passed=True))
    unreal.log('HOTEL_MAP_COMMIT_CANDIDATE_PASS')
if __name__=='__main__':
    try:main()
    except Exception:write('PrepareCommitFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
