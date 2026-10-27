"""Record the actual image inspection, bound to the reviewed PNG hashes."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/HotelRevision_20261019'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
f=json.loads((W/'FurnitureVisualReview.json').read_text(encoding='utf-8-sig'));assert f['passed']
images={}
for row in f['images']:
    p=Path(row['image']);assert row['passed'] and sha(p)==row['sha256']
    images[row['view']]=dict(passed=True,sha256=row['sha256'],reviewer=f['reviewer'],observation=row['observation'])
root_observations={
    'REV_SouthStair':'Both flights meet the new side walls; risers have no open gaps. Rear landing and raised window are clear.',
    'REV_NorthStair':'Continuous side walls close the former slots alongside both flights. Landing and rear window remain clear.',
    'REV_FrontNorth':'The north exit and service-door positions are solid plaster wall; no orphan door frames or hinges are visible. Existing utility assembly remains.',
    'REV_FrontSouth':'The former south front-exit opening is solid matching wall without an orphan frame or threshold.',
    'REV_DoubleHandle':'Latch-edge view shows one metal handle on each face of the same door leaf, correctly mirrored and mounted.',
}
for name,observation in root_observations.items():
    p=W/'Captures/Renders'/(name+'.png');m=json.loads(p.with_suffix('.json').read_text(encoding='utf-8-sig'))
    assert m['status']=='PASS' and sha(p)==m['png_sha256']
    images[name]=dict(passed=True,sha256=sha(p),reviewer='root',observation=observation)
assert len(images)==9
(W/'VisualReview.json').write_text(json.dumps(dict(passed=True,reviewed_utc=datetime.now(timezone.utc).isoformat(),
    scope='Nine targeted fresh saved-map images; numeric collision/preservation checks are separate.',images=images),ensure_ascii=False,indent=2),encoding='utf-8')
print('VISUAL_REVIEW_PASS',len(images))
