"""Record the four fresh target images inspected by the primary agent."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/HotelFrontBoundary_20261021'
observations={
 'BOUNDARY_LaneEye':'Solid wall and closed gate span the foreground gap and hide the ground-edge sightline at player height. Wall feet meet the terrain.',
 'BOUNDARY_Oblique':'The screen reads as a courtyard end wall with masonry piers and a green metal gate; the forecourt stays open.',
 'BOUNDARY_Gate':'Corrugated sheet, cross braces, pulls, hinges and centre lap are present. No visible through-gap or floating leaf at this view.',
 'BOUNDARY_Top':'Wall is on the requested hotel-front +Y end. West return joins the neighbouring building corner; east return leaves the hotel rear route open. No doors or windows covered.',
}
images={}
for name,observation in observations.items():
    p=W/'Captures/Renders'/(name+'.png');m=json.loads(p.with_suffix('.json').read_text(encoding='utf-8-sig'))
    digest=hashlib.sha256(p.read_bytes()).hexdigest();assert m['status']=='PASS' and digest==m['png_sha256']
    images[name]=dict(passed=True,sha256=digest,observation=observation)
(W/'VisualReview.json').write_text(json.dumps(dict(passed=True,reviewed_utc=datetime.now(timezone.utc).isoformat(),reviewer='root',
    scope='Four actual fresh engine images; inspection lighting is temporary, original lighting is preserved.',images=images),ensure_ascii=False,indent=2),encoding='utf-8')
print('BOUNDARY_VISUAL_REVIEW_PASS')
