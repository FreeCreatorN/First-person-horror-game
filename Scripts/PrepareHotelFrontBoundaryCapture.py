import json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/HotelFrontBoundary_20261021'
def main():
    d=json.loads((W/'Applied.json').read_text(encoding='utf-8-sig'));assert d['passed']
    specs={
      'BOUNDARY_LaneEye':dict(location_cm=[7850.,2850.,175.],target_cm=[7900.,3900.,160.],fov_degrees=90.),
      'BOUNDARY_Oblique':dict(location_cm=[7800.,2400.,850.],target_cm=[8250.,3900.,120.],fov_degrees=93.),
      'BOUNDARY_Gate':dict(location_cm=[7900.,3500.,155.],target_cm=[7900.,3900.,145.],fov_degrees=82.),
      'BOUNDARY_Top':dict(location_cm=[8300.,5100.,3700.],target_cm=[8250.,3250.,0.],fov_degrees=85.)}
    report=dict(target_level=d['target_level'],map_sha256=d['map_sha256'],new_asset_sha256=d['new_asset_sha256'],hotel_openings_review_cameras=list(specs),review_camera_overrides=specs)
    (W/'CaptureBuildReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    s=(R/'Scripts/CaptureOldTownIntersectionViews.ps1').read_text(encoding='utf-8-sig')
    s=s.replace('Scripts\\CaptureOldTownIntersectionViews.py','Scripts\\CaptureHotelFrontBoundary.py')
    (R/'Scripts/CaptureHotelFrontBoundary.ps1').write_text(s,encoding='utf-8-sig')
    print('BOUNDARY_CAPTURE_READY')
if __name__=='__main__':main()
