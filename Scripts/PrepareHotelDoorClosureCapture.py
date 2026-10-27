import json,math
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelDoorClosure_20261019'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
applied=read('Applied.json');expected=read('ProtectedBefore.json')['file_sha256'];expected.update(applied['modified_existing_files']);expected.update(applied['new_assets'])
rows={r['label']:r for r in read('Doors.json')['all_doors']}
def point(label,p):
    tf=rows[label]['actor_transform'];q=tf['rotation_quaternion_xyzw'];angle=2*math.atan2(q[2],q[3]);c,s=math.cos(angle),math.sin(angle)
    return [tf['translation'][0]+p[0]*c-p[1]*s,tf['translation'][1]+p[0]*s+p[1]*c,tf['translation'][2]+p[2]]
specs={}
for name,label,eye,target,fov in [
 ('CLOSURE_GuestClosed','OTS_HotelV4_Door_Room201_Door',[65,170,135],[0,8,110],65),
 ('CLOSURE_GuestHinge','OTS_HotelV4_Door_Room201_Door',[-10,65,120],[-47,9,110],65),
 ('CLOSURE_BathClosed','OTS_HotelV4_Door_Room201_BathDoor',[50,145,125],[0,4,103],65),
 ('CLOSURE_MainClosed','OTS_HotelV4_Door_MainEntry',[120,380,165],[0,8,115],65),
]:specs[name]=dict(location_cm=point(label,eye),target_cm=point(label,target),fov_degrees=fov)
expected.pop(str(R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'))
report=dict(target_level='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',map_sha256=applied['map_sha256'],new_asset_sha256=expected,
    hotel_openings_review_cameras=list(specs),review_camera_overrides=specs)
(W/'CaptureReport.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
source=(R/'Scripts/CaptureOldTownIntersectionViews.ps1').read_text(encoding='utf-8-sig').replace('CaptureOldTownIntersectionViews.py','CaptureHotelDoorClosureViews.py')
(R/'Scripts/CaptureHotelDoorClosureViews.ps1').write_text(source,encoding='utf-8')
print('Prepared 4 closed-door capture views')
