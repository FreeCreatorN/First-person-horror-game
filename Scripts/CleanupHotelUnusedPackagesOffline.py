"""Quarantine proven assistant packages only after fresh full-project reference closure."""
import hashlib,json,subprocess,shutil
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];C=R/'Content';W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,v):
    p=W/n;assert not p.exists();p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def files():return {str(p):sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
def closed():
    p=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True);assert p.stdout.strip()=='0','UE must be fully closed'
def main():
    closed();assert not (W/'CurrentCleanupResult.json').exists()
    assert read('CommittedAudit.json')['passed'] and read('CommittedAudit1.Completion.json')['normal_zero_exit']
    graph=read('CommittedReferences.json');assert graph['passed'] and read('CommittedReferences1.Completion.json')['normal_zero_exit']
    commit=read('Committed.json');assert commit['passed'] and graph['mode']=='Committed' and graph['disk_registry_packages_exact']
    assert commit['map_sha256']==graph['map_sha256']==read('CommittedAudit.json')['map_sha256']
    ownership=read('CleanupOwnershipCandidates.json');assert ownership['passed']
    copied=read('CopiedPackages.json');effective=read('EffectivePrivateHashes.json');assert effective['passed']
    current=files();assert current==graph['file_sha256']
    proposed={r['package']:dict(r) for r in ownership['candidates']}
    stage=copied['staged_level'];stagefile=str(C/(stage.removeprefix('/Game/')+'.umap'))
    proposed[stage]=dict(package=stage,file=stagefile,authored_sha256=effective['new_asset_sha256'][stagefile],
        creation_manifest=str(W/'CopiedPackages.json'),creation_manifest_sha256=sha(W/'CopiedPackages.json'),kind='temporary_stage_map')
    assert len(proposed)==47
    for p,r in proposed.items():
        f=Path(r['file']).resolve();assert f.is_relative_to((C/'CodexGenerated').resolve()) and f.suffix in ('.uasset','.umap')
        assert current[str(f)]==r['authored_sha256']
        assert not any(f.with_suffix('.'+s).exists() for s in ('uexp','ubulk','uptnl','upayload','m.ubulk'))
    rows={r['package']:r for r in graph['assets']};assert set(proposed)<=set(rows)
    protected={r['package'] for r in ownership['protected_shared_blueprints']}
    assert not (protected&set(proposed))
    restored={r['file'] for r in ownership['restored_uncertain_materials_protected']};assert not restored&{r['file'] for r in proposed.values()}
    incoming={p:set() for p in proposed}
    for p,r in rows.items():
        for d in r['dependencies']:
            if d in proposed:incoming[d].add(p)
        if p in proposed:incoming[p].update(r['referencers'])
    literal_incoming={p:set() for p in proposed}
    needles={p:(p.encode().lower(),p.encode('utf-16-le').lower()) for p in proposed}
    package_files={str(Path(r['file']).resolve()):p for p,r in proposed.items()}
    source_files=[]
    for root in (R/'Source',R/'Config',R/'Plugins'):
        if root.exists():
            source_files.extend(p for p in root.rglob('*') if p.is_file() and not {'Intermediate','Binaries','.git'}&set(p.relative_to(root).parts)
                and p.suffix.lower() in ('.h','.hpp','.cpp','.c','.cs','.ini','.json','.uplugin','.uproject','.py','.txt'))
    source_files.extend(R.glob('*.uproject'))
    source_hashes={str(p):sha(p) for p in source_files}
    for f in [Path(p) for p in current if Path(p).is_relative_to(C)]+source_files:
        blob=f.read_bytes().lower();origin=package_files.get(str(f.resolve()),'file:'+str(f.resolve()))
        for p,(a,b) in needles.items():
            if a in blob or b in blob:literal_incoming[p].add(origin)
    removable=set(proposed);reasons={}
    while True:
        rejected={p for p in removable if (incoming[p]|literal_incoming[p])-removable}
        if not rejected:break
        for p in rejected:reasons[p]=sorted((incoming[p]|literal_incoming[p])-removable)
        removable-=rejected
    assert stage in removable,'Temporary map still has a retained incoming reference'
    retained=[dict(package=p,reason=reasons[p]) for p in sorted(set(proposed)-removable)]
    gate=dict(passed=True,proposed_count=len(proposed),removable_count=len(removable),retained=retained,
        references_sha256=sha(W/'CommittedReferences.json'),ownership_sha256=sha(W/'CleanupOwnershipCandidates.json'),
        scanned_content_files=sum(Path(p).is_relative_to(C) for p in current),scanned_source_config_files=len(source_files),
        source_config_file_sha256=source_hashes,
        complete_utf8_utf16_package_literals=True,all_registry_reference_categories=True,fixed_point=True,
        removable=[dict(proposed[p],incoming=sorted(incoming[p]),literal_incoming=sorted(literal_incoming[p])) for p in sorted(removable)])
    write('CurrentCleanupGate.json',gate)
    closed();assert files()==current and all(sha(p)==h for p,h in source_hashes.items())
    backup=R/'Saved/CodexBackups'/('HotelUnusedPackages_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True,exist_ok=False)
    removed=[]
    for p in sorted(removable):
        f=Path(proposed[p]['file']).resolve();b=backup/'Content'/f.relative_to(C.resolve());b.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(f,b);assert sha(b)==current[str(f)]
        removed.append(dict(package=p,file=str(f),sha256=current[str(f)],backup=str(b),bytes=f.stat().st_size))
    write('CurrentCleanupPrepared.json',dict(passed=True,removed_files=removed,backup_directory=str(backup)))
    for r in removed:
        f=Path(r['file']).resolve();assert f.is_relative_to((C/'CodexGenerated').resolve()) and sha(f)==r['sha256'];f.unlink()
    after=files();assert after=={p:h for p,h in current.items() if p not in {r['file'] for r in removed}}
    write('CurrentCleanupResult.json',dict(passed=True,removed_count=len(removed),removed_files=removed,removed_bytes=sum(r['bytes'] for r in removed),
        backup_directory=str(backup),all_other_content_config_unchanged=True,retained_candidates=retained,no_force_delete_api=True))
    print('HOTEL_UNUSED_PACKAGE_CLEANUP_PASS',len(removed))
if __name__=='__main__':main()
