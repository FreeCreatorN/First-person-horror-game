"""Remove ten proven obsolete door packages after world index regeneration."""
import json,hashlib,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];C=R/'Content';W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,v):
    f=W/n;assert not f.exists();f.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def files():return {str(p):sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
def main():
    assert not (W/'SupplementalCleanupResult.json').exists()
    q=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True);assert q.stdout.strip()=='0'
    refresh=read('MetadataRefreshApplied.json');assert refresh['passed'] and read('MetadataRefresh1.Completion.json')['normal_zero_exit']
    assert read('RefreshedAudit.json')['passed'] and read('RefreshedAudit1.Completion.json')['normal_zero_exit']
    graph=read('RefreshedReferences.json');assert graph['passed'] and graph['disk_registry_packages_exact'] and read('RefreshedReferences1.Completion.json')['normal_zero_exit']
    assert graph['map_sha256']==refresh['map_sha256']==read('RefreshedAudit.json')['map_sha256']
    current=files();assert current==graph['file_sha256']
    retained={r['package'] for r in read('CurrentCleanupGate.json')['retained']};assert len(retained)==10
    proven={r['package']:r for r in read('CleanupOwnershipCandidates.json')['candidates']};assert retained<=set(proven)
    rows={r['package']:r for r in graph['assets']}
    for p in retained:assert not set(rows[p]['referencers'])-retained
    for p,r in rows.items():
        if p not in retained:assert not set(r['dependencies'])&retained
    sourcefiles=[]
    for root in (R/'Source',R/'Config',R/'Plugins'):
        if root.exists():sourcefiles.extend(p for p in root.rglob('*') if p.is_file() and not {'Intermediate','Binaries','.git'}&set(p.relative_to(root).parts) and p.suffix.lower() in ('.h','.hpp','.cpp','.c','.cs','.ini','.json','.uplugin','.uproject','.py','.txt'))
    sourcefiles.extend(R.glob('*.uproject'));sourcehash={str(p):sha(p) for p in sourcefiles}
    candidatefiles={str(Path(proven[p]['file']).resolve()) for p in retained}
    needles=[(p,p.encode().lower(),p.encode('utf-16-le').lower()) for p in retained]
    for f in [Path(p) for p in current if Path(p).is_relative_to(C) and p not in candidatefiles]+sourcefiles:
        blob=f.read_bytes().lower()
        for p,a,b in needles:assert a not in blob and b not in blob,dict(package=p,file=str(f))
    assert files()==current and all(sha(p)==h for p,h in sourcehash.items())
    backup=R/'Saved/CodexBackups'/('HotelObsoleteDoors_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    removed=[]
    for p in sorted(retained):
        row=proven[p];f=Path(row['file']).resolve();assert f.is_relative_to((C/'CodexGenerated/OldTown/DoorReuse_20261017').resolve()) and f.suffix=='.uasset'
        assert sha(f)==row['authored_sha256']==current[str(f)]
        assert not any(f.with_suffix('.'+s).exists() for s in ('uexp','ubulk','uptnl','upayload','m.ubulk'))
        b=backup/'Content'/f.relative_to(C);b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,b);assert sha(b)==current[str(f)]
        removed.append(dict(package=p,file=str(f),backup=str(b),sha256=current[str(f)],bytes=f.stat().st_size))
    write('SupplementalCleanupPrepared.json',dict(passed=True,removed_files=removed,source_sha256=sourcehash))
    for row in removed:
        f=Path(row['file']).resolve();assert f.is_relative_to((C/'CodexGenerated/OldTown/DoorReuse_20261017').resolve()) and sha(f)==row['sha256'];f.unlink()
    assert files()=={p:h for p,h in current.items() if p not in candidatefiles}
    write('SupplementalCleanupResult.json',dict(passed=True,removed_count=10,removed_files=removed,backup_directory=str(backup),removed_bytes=sum(r['bytes'] for r in removed),all_other_content_config_unchanged=True,no_asset_or_map_write=True))
    print('HOTEL_OBSOLETE_DOOR_CLEANUP_PASS 10')
if __name__=='__main__':main()
