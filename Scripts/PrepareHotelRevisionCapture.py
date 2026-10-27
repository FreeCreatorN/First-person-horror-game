"""Offline report binds fresh captures to saved map and all new assets."""
import json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/HotelRevision_20261019'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    applied=json.loads((W/'Applied.json').read_text(encoding='utf-8-sig'))
    assert applied['passed'] and sha(R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==applied['map_sha256']
    specs={
      'REV_CleanLinen':([9620,1370,160],[9930,1410,64],78),
      'REV_DirtyLinen':([9620,1780,160],[9930,1810,62],78),
      'REV_Changing':([9620,2170,160],[9930,2200,65],78),
      'REV_Equipment':([9620,2700,158],[9930,2760,62],68),
      'REV_SouthStair':([9400,-3290,164],[9870,-3200,220],90),
      'REV_NorthStair':([9400,3110,164],[9870,3200,220],90),
      'REV_FrontNorth':([8490,2900,175],[9010,2900,145],102),
      'REV_FrontSouth':([8490,-3200,175],[9010,-3200,145],75),
      'REV_DoubleHandle':([9418,-2485.5,490],[9350,-2485.5,478.25],52),
    }
    value=dict(target_level='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',map_sha256=applied['map_sha256'],new_asset_sha256=applied['new_asset_sha256'],
        hotel_openings_review_cameras=list(specs),review_camera_overrides={n:dict(location_cm=p,target_cm=t,fov_degrees=f) for n,(p,t,f) in specs.items()})
    (W/'CaptureBuildReport.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    source=(R/'Scripts/CaptureOldTownIntersectionViews.ps1').read_text(encoding='utf-8-sig')
    source=source.replace('Scripts\\CaptureOldTownIntersectionViews.py','Scripts\\CaptureHotelRevisionViews.py')
    (R/'Scripts/CaptureHotelRevisionViews.ps1').write_text(source,encoding='utf-8-sig')
    print('CAPTURE_REPORT_READY',len(specs))
if __name__=='__main__':main()
