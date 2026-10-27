"""Move inspection cameras inside service rooms and clear the guest wardrobe."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/HotelRevision_20261019'
d=json.loads((W/'CaptureBuildReport.json').read_text(encoding='utf-8-sig'))
for name,y in [('CleanLinen',1410),('DirtyLinen',1810),('Changing',2200),('Equipment',2760)]:
    d['review_camera_overrides']['REV_'+name]=dict(location_cm=[9740,y,165],target_cm=[9930,y,100],fov_degrees=112 if name!='Equipment' else 100)
d['review_camera_overrides']['REV_DoubleHandle']=dict(location_cm=[9380,-2485.5,485],target_cm=[9351,-2485.5,478.25],fov_degrees=80)
(W/'CaptureBuildReport_FurnitureV2.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print('CAPTURE_V2_READY')
