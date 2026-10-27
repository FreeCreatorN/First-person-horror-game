"""Offline atomic installation of the sole authorized original-map candidate."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def main():
    assert not (W/'Committed.json').exists()
    processes=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True)
    assert processes.stdout.strip()=='0','UE must be fully closed'
    completion=read('PrepareCommit1.Completion.json');assert completion['normal_zero_exit'] and completion['exit_code']==0
    prepared=read('PreparedCommit.json');assert prepared['passed']
    target=Path(prepared['original_map_file']).resolve();candidate=Path(prepared['candidate_file']).resolve()
    assert target==R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    assert candidate.is_relative_to(W/'CommitCandidate') and sha(candidate)==prepared['candidate_sha256']
    assert sha(target)==prepared['original_map_sha256']
    protected=read('ProtectedBeforeAfterRestore.json')['file_sha256']
    effective=read('EffectivePrivateHashes.json');assert effective['passed']
    assert effective['initial_copy_sha256']==sha(W/'CopiedPackages.json')
    assert effective['correction_report_sha256']==sha(W/'PrivateAssetCorrections.json')
    copied=effective['new_asset_sha256']
    before={str(p):sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
    assert before=={**protected,**copied}
    original_backup=R/'Saved/CodexBackups'/('HotelMapAtomicCommit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    original_backup.mkdir(parents=True,exist_ok=False);backup=original_backup/target.name
    shutil.copy2(target,backup);assert sha(backup)==before[str(target)]
    temporary=target.with_name(target.name+'.hotel-commit-tmp')
    assert not temporary.exists()
    with candidate.open('rb') as source,temporary.open('xb') as out:
        shutil.copyfileobj(source,out);out.flush();os.fsync(out.fileno())
    assert sha(temporary)==prepared['candidate_sha256']
    os.replace(temporary,target)
    assert sha(target)==prepared['candidate_sha256']
    after={str(p):sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
    assert set(before)==set(after) and all(after[p]==h for p,h in before.items() if p!=str(target))
    (W/'Committed.json').write_text(json.dumps(dict(passed=True,map_sha256=sha(target),source_map_sha256=before[str(target)],
        original_map_file=str(target),backup=str(backup),backup_sha256=sha(backup),atomic_replace=True,
        only_original_map_changed=True,other_content_config_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print('HOTEL_ORIGINAL_MAP_ATOMIC_COMMIT_PASS')
if __name__=='__main__':main()
