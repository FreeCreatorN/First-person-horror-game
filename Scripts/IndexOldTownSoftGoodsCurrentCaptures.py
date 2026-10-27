"""Preserve capture history and index exactly the latest fresh accepted frames."""
import json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    b=json.loads((W/'BuildReport.json').read_text());buildref=dict(file=str(W/'BuildReport.json'),sha256=sha(W/'BuildReport.json'))
    specs=[('Captures',b['hotel_openings_review_cameras'],'temporary'),('LampCaptures',['CAM_StreetAccess_Lamp','CAM_V4_TopGallery','CAM_StreetAccess_NightStreet'],'street_only'),('SoftGoodsCaptures',b['softgoods_review_cameras'],'temporary')]
    for group,cameras,lighting in specs:
        path=W/group/'CaptureRuns.json';rows=json.loads(path.read_text(encoding='utf-8-sig'))
        history=path.with_name('CaptureRuns.History.'+sha(path)[:12]+'.json')
        if not history.exists():history.write_bytes(path.read_bytes())
        index={}
        for row in rows:
            if row['camera'] not in cameras:continue
            meta=json.loads((W/group/'Renders'/(row['camera']+'.json')).read_text())
            if row['run_id']!=meta['run_id']:continue
            assert row['normal_exit'] and row['exit_code']==0 and not row['forced_cleanup'] and row['captured'] and not row['reused']
            assert meta['source_build_report']==buildref and meta['lighting_mode']==lighting
            assert meta['new_asset_sha256']==b['new_asset_sha256'] and meta['map_sha256']==b['map_sha256']
            index[row['camera']]=row
        assert set(index)==set(cameras),(group,list(index))
        path.write_text(json.dumps([index[c] for c in cameras],ensure_ascii=False,indent=2),encoding='utf-8')
    print('CURRENT_CAPTURE_INDEX_VERIFIED 19')
if __name__=='__main__':main()
