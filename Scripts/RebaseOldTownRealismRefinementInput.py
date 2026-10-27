"""Freeze exactly the user's pre-stage pickup Blueprint reload change."""
from pathlib import Path
import json,shutil
from VerifyOldTownRealismRefinement import verify_baseline,sha,reference
ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
p=W/'Baseline.json';b=json.loads(p.read_text());e=json.loads((W/'PickupPreflight.json').read_text())
assert not (W/'Applied.json').exists() and not (ROOT/'Content/CodexGenerated/OldTown/RealismRefinement_20261013').exists()
assert sha(ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')==b['source_map_sha256']
assert not b.get('preexisting_actor_reload_change')
shutil.copy2(p,W/'Before/InitialBaseline.json')
b['preexisting_actor_reload_change']=dict(actor='BP_ItemPickup',evidence=reference(W/'PickupPreflight.json'),
    source_blueprint=e['asset'],reason='Blueprint saved at 16:14, after the prior accepted 15:29 stage. Current ItemData references a different HeldItemMesh path; the reload state is frozen before any new material/map write.')
verify_baseline(b)
p.write_text(json.dumps(b,ensure_ascii=False,indent=2),encoding='utf-8')
print('EXACT_PREEXISTING_USER_PICKUP_INPUT_FROZEN')
