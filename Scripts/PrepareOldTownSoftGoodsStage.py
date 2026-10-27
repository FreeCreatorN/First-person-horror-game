"""Freeze the currently accepted material stage for the following mesh stage."""
import json,shutil
from pathlib import Path
from VerifyOldTownSoftGoodsRefinement import create_baseline,verify_baseline
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
def main():
    assert not (W/'Baseline.json').exists(),'Mesh baseline already frozen.'
    before=W/'Before';before.mkdir(parents=True,exist_ok=True)
    shutil.copy2(R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap',before/'Target.umap')
    shutil.copy2(R/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json',before/'CurrentEvidence.json')
    baseline=create_baseline(before/'Target.umap',before/'CurrentEvidence.json',before/'SourceMeshRecords.json')
    verify_baseline(baseline)
    (W/'Baseline.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SOFT_GOODS_BASELINE_FROZEN '+baseline['source_map_sha256'])
if __name__=='__main__':main()
