"""Restore only the backed up assistant BPs after the graph-order export guard."""
import json,hashlib,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelDoorClosure_20261019'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
b=read('ProtectedBefore.json')['file_sha256'];backup=read('Backup.json');allowed={r['source']:r for r in backup['files']}
cur={str(p):sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
assert all(cur.get(p)==h for p,h in b.items() if p not in allowed)
assert cur[str(R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap')]==read('Plan.json')['source_map_sha256']
added={p:h for p,h in cur.items() if p not in b};assert len(added)==14 and all(Path(p).is_relative_to(R/'Content/CodexGenerated/Hotel/Meshes/DoorClosure') for p in added)
restored=[]
for p,row in allowed.items():
    assert sha(row['backup'])==b[p]
    if cur[p]!=b[p]:
        archived=W/'FailedAttempt4'/Path(p).relative_to(R);archived.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,archived)
        shutil.copy2(row['backup'],p);assert sha(p)==b[p];restored.append(p)
assert all(sha(p)==h for p,h in b.items())
shutil.copy2(W/'ApplyFailure.json',W/'Apply4.Failure.json')
(W/'Recovery4.json').write_text(json.dumps(dict(passed=True,restored_assistant_blueprints=restored,new_assets=added,map_was_not_saved=True,all_original_files_restored=True),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,restored_blueprints=len(restored),new_mesh_assets=len(added),original_map_unchanged=True)))

