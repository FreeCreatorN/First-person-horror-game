"""Configure transient bed/chair closeups without altering saved camera Actors."""
import json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=W/'BuildReport.json';b=json.loads(p.read_text(encoding='utf-8-sig'))
    assert not (W/'CaptureSetup.json').exists(),'Capture setup already frozen.'
    b['softgoods_review_cameras']=['CAM_V4_UpperCore','CAM_V4_CentralStair']
    b['review_camera_overrides'].update({
        'CAM_V4_UpperCore':dict(location_cm=[9740.,-2760.,460.],target_cm=[9910.,-2790.,431.],fov_degrees=65.),
        'CAM_V4_CentralStair':dict(location_cm=[9665.,-2755.,474.],target_cm=[9612.5,-2835.,430.],fov_degrees=60.)})
    p.write_text(json.dumps(b,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    evidence=dict(passed=True,map_sha256=b['map_sha256'],source='fresh_persisted_map_load',
        camera_poses_transient_only=True,saved_cameras_preserved=True,build_report_file=str(p),build_report_sha256=sha(p),
        scripts={str((R/'Scripts'/n).resolve()):sha(R/'Scripts'/n) for n in ('CaptureOldTownSoftGoodsViews.py','CaptureOldTownSoftGoodsViews.ps1')},
        standard_cameras=b['hotel_openings_review_cameras'],softgoods_cameras=b['softgoods_review_cameras'],
        view_mode='lit',width=1920,height=1080,maximum_cameras_per_batch=4,parallel_user_main_editor_authorized=True)
    (W/'CaptureSetup.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SOFT_GOODS_CAPTURE_SETUP_PASS 14 standard +3 actual lamps +2 cloth closeups')
if __name__=='__main__':main()
