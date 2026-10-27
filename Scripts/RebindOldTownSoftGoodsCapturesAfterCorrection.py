"""Bind new captures to the corrected two packages; keep the old setup receipt."""
import json,hashlib,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    setup=Path(W/'CaptureSetup.json');old=json.loads(setup.read_text());b=json.loads((W/'BuildReport.json').read_text())
    correction=json.loads((W/'OverlapCorrection.json').read_text());assert correction['passed']
    assert old['map_sha256']==b['map_sha256'] and old['standard_cameras']==b['hotel_openings_review_cameras']
    assert old['softgoods_cameras']==b['softgoods_review_cameras']
    assert all(sha(p)==h for p,h in old['scripts'].items())
    hist=W/'OverlapDiagnosis/CaptureSetupBeforeCorrection.json'
    if not hist.exists():shutil.copy2(setup,hist)
    else:assert sha(hist)==sha(setup) or old.get('corrected_owned_mesh')=='LegacyBedMattress'
    old['build_report_sha256']=sha(W/'BuildReport.json')
    old['corrected_owned_mesh']='LegacyBedMattress'
    old['previous_setup']=dict(file=str(hist),sha256=sha(hist))
    setup.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CORRECTED_CAPTURE_SETUP_BOUND')
if __name__=='__main__':main()
