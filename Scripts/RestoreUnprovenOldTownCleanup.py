"""Restore exact six quarantined packages whose direct creation evidence is incomplete."""
import hashlib,json,shutil,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert not (W/'LegacyCleanupRestored.json').exists()
    result=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True)
    assert result.stdout.strip()=='0','UE must be closed'
    audit_file=W/'LegacyCleanupProvenanceAudit.json';audit=json.loads(audit_file.read_text(encoding='utf-8-sig'))
    assert audit['passed'] and audit['summary']['uncertainToRestore']==6
    rows=audit['uncertainToRestore'];copies=[]
    for row in rows:
        source=Path(row['isolated_file']).resolve();target=Path(row['original_file']).resolve()
        assert source.is_relative_to(R/'Saved/CodexBackups') and target.is_relative_to(R/'Content/CodexGenerated/OldTown/Realism_20261012/Materials')
        assert not target.exists() and sha(source)==row['current_sha256']
        copies.append((source,target,row['current_sha256']))
    for source,target,digest in copies:
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);assert sha(target)==digest
    before=json.loads((W/'ProtectedBefore.json').read_text(encoding='utf-8-sig'))['file_sha256']
    after={str(p):sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
    assert all(after.get(p)==digest for p,digest in before.items())
    assert set(after)-set(before)=={str(t) for _,t,_ in copies}
    report=dict(passed=True,restored_count=6,remaining_isolated_owned_packages=595,audit_sha256=sha(audit_file),
        restoration=[dict(file=str(t),backup=str(s),sha256=d) for s,t,d in copies],existing_files_unchanged=True)
    (W/'LegacyCleanupRestored.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (W/'ProtectedBeforeAfterRestore.json').write_text(json.dumps(dict(file_sha256=after),ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESTORED_UNPROVEN_OWNERSHIP_PACKAGES=6; CONFIRMED_OLD_CLEANUP=595')
if __name__=='__main__':main()
