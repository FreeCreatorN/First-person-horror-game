"""Quarantine only changed private copies from the interrupted metadata pass."""
import hashlib,json,shutil,subprocess,os
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017';H=R/'Content/CodexGenerated/Hotel'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def main():
    round_suffix=os.environ.get('HOTEL_RESET_SUFFIX','');assert round_suffix in ('','2','3')
    report='MetadataPassReset'+round_suffix+'.json';assert not (W/report).exists()
    p=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True);assert p.stdout.strip()=='0'
    baseline=read('ProtectedBeforeAfterRestore.json')['file_sha256'];assert all(sha(p)==h for p,h in baseline.items())
    copied=read('CopiedPackages.json');changed=[(Path(p),h) for p,h in copied['new_asset_sha256'].items() if sha(p)!=h]
    assert len(changed)==(156 if round_suffix else 125) and all(p.resolve().is_relative_to(H.resolve()) and p.suffix=='.uasset' for p,h in changed)
    backup=R/'Saved/CodexBackups'/('HotelFailedPrivateMetadata_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    rows=[]
    for p,h in changed:
        b=backup/p.relative_to(H);b.parent.mkdir(parents=True,exist_ok=True);current=sha(p);shutil.copy2(p,b);assert sha(b)==current
        rows.append(dict(file=str(p),backup=str(b),failed_pass_sha256=current,initial_copy_sha256=h))
    for row in rows:
        p=Path(row['file']);assert p.resolve().is_relative_to(H.resolve()) and sha(p)==row['failed_pass_sha256'];p.unlink()
    assert all(sha(p)==h for p,h in baseline.items())
    (W/report).write_text(json.dumps(dict(passed=True,quarantined_count=len(rows),files=rows,all_original_files_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print('HOTEL_FAILED_PRIVATE_RESET_PASS',len(rows))
if __name__=='__main__':main()
