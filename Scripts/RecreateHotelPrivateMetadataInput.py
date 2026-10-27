"""Recreate the exact private copies isolated after an interrupted metadata pass."""
import sys,json,os
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
suffix=os.environ.get('HOTEL_RESET_SUFFIX','');assert suffix in ('','2','3')
reset=read('MetadataPassReset'+suffix+'.json');copied=read('CopiedPackages.json');plan=read('HotelNamePlan.json')
assert reset['passed'] and not (W/('MetadataInputRecreated'+suffix+'.json')).exists()
files={r['file'] for r in reset['files']};sources=[r['source_package'] for r in plan['mappings'] if r['destination_file'] in files]
assert len(sources)==reset['quarantined_count']
result=json.loads(unreal.HotelPackageCopyLibrary.patch_packages_exact(copied['package_remapping'],sources))
native.write(W/('MetadataInputRecreateProof'+suffix+'.json'),result);assert result['passed'] and len(result['patched_files'])==len(sources)
assert all(native.sha(Path(p))==h for p,h in copied['new_asset_sha256'].items())
baseline=read('ProtectedBeforeAfterRestore.json')['file_sha256'];assert all(native.sha(Path(p))==h for p,h in baseline.items())
native.write(W/('MetadataInputRecreated'+suffix+'.json'),dict(passed=True,all_private_initial_hashes_restored=True,all_original_files_unchanged=True,recreated=len(sources)))
unreal.log('HOTEL_METADATA_INITIAL_INPUT_RECREATED_PASS')
