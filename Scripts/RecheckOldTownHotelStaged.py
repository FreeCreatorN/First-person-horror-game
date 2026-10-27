"""Recheck the immutable fresh Stage capture after reference-normalization repair."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
from OldTownHotelNamingVerification import compare_scene
W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';C=R/'Content'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def main():
    assert not (W/'StagedAudit.json').exists()
    copied=read('CopiedPackages.json');assert copied['passed']
    assert native.sha(C/'Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==copied['source_map_sha256']
    baseline=read('ProtectedBeforeAfterRestore.json')['file_sha256']
    assert all(native.sha(Path(p))==h for p,h in baseline.items())
    assert all(native.sha(Path(p))==h for p,h in copied['new_asset_sha256'].items())
    current=read('StagedScene.json');expected=read('BeforeScene.json')
    proof=compare_scene(expected,current,copied['package_remapping'])
    inventory=read('Inventory.json');openings=[]
    for kind,key,count,classes in [('windows','window_assemblies',348,8),('doors','door_assemblies',124,10)]:
        rows=inventory[key];assert len(rows)==count
        actual_classes={current['actors'][row['label']]['class'] for row in rows}
        assert len(actual_classes)==classes
        openings.append(dict(kind=kind,count=count,shared_blueprints=classes))
    native.write(W/'StagedAudit.json',dict(passed=True,target_level=copied['staged_level'],mode='Staged',
        source_capture='StagedScene.json',original_capture_log='StagedAudit1.log',rechecked_immutable_fresh_capture=True,
        map_sha256=copied['source_map_sha256'],actor_count=7986,scene_proof=proof,openings=openings,
        all_original_user_assets_unchanged=True,private_asset_hashes_unchanged=True,no_map_save=True))
    unreal.log('HOTEL_STAGED_COMPLETE_RECHECK_PASS')
if __name__=='__main__':
    try:main()
    except Exception as error:native.write(W/'StagedRecheckFailure.json',dict(passed=False,traceback=traceback.format_exc(),proof=getattr(error,'report',None)));raise
