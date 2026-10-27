"""Offline acceptance of the door reuse and exact owned-unused isolation evidence."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone

R=Path(__file__).resolve().parents[1]
W=R/'Saved/CodexOutputs/OldTownDoorReuse_20261017'
C=R/'Content'
MAP=C/'Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def evidence(n):return read(W/n)
def graph(doc):
    result={}
    for row in doc['assets']:
        node=row['package'].casefold();result.setdefault(node,set())
        result[node].update(p.casefold() for p in row['dependencies'] if p.startswith('/Game/'))
        for parent in row['referencers']:
            if parent.startswith('/Game/'):result.setdefault(parent.casefold(),set()).add(node)
    return result
def package(p):return '/Game/'+p.relative_to(C).with_suffix('').as_posix()
def main():
    assert not (W/'FinalReview.json').exists(),'Accepted evidence is immutable'
    completed={
        'BlueprintProbe4':'BuildAndProbeOldTownReusableDoors.py',
        'Apply1':'ApplyOldTownDoorReuse.py','Readback1':'AuditOldTownDoorReuse.py',
        'ExportAfterReuse1':'ExportOldTownDoorReuseReferences.py',
        'CleanupGate1':'ApproveOldTownUnusedOfflineCleanup.py',
        'ReadbackAfterCleanup1':'AuditOldTownDoorReuseAfterCleanup.py',
        'ExportAfterCleanup1':'ExportOldTownDoorReuseReferences.py'}
    completion_files=[]
    for name,script in completed.items():
        file=W/(name+'.Completion.json');row=read(file)
        assert row['normal_zero_exit'] and row['exit_code']==0 and Path(row['script']).resolve()==R/'Scripts'/script
        completion_files.append(file)
    applied=evidence('AppliedDoorReuse.json');probe=evidence('ReusableBlueprints.json')
    audit=evidence('DoorReuseReadback.json');final=evidence('DoorReuseAfterCleanupReadback.json')
    approve=evidence('OfflineCleanupApproved.json');clean=evidence('OfflineCleanupResult.json')
    plan=evidence('OwnershipPlan.json');backup=evidence('Backup.json');design=evidence('DoorReuseDesign.json')
    refs_before=evidence('AssetReferencesFresh.json');refs_after=evidence('AssetReferencesAfterCleanup.json')
    assert all(row['passed'] for row in (applied,probe,audit,final,approve,clean,plan,backup,design,refs_before,refs_after))
    assert clean['protected_files_unchanged'] and clean['exact_file_moves_only'] and clean['no_force_delete']
    assert final['after_cleanup'] and audit['all_other_actors_native_unchanged'] and final['all_other_actors_native_unchanged']
    current_sha=sha(MAP)
    assert all(row['map_sha256']==current_sha for row in (applied,audit,final,approve,clean,plan,refs_before,refs_after))
    source_sha=applied['source_map_sha256']
    assert source_sha==probe['source_map_sha256']==design['source_map_sha256']==backup['sha256']==sha(backup['file'])
    assert source_sha=='8149497ff1ad953fad2ac2bc08f3cd072f78421709cc8777fb54ebf1fc055d61'
    for row in (audit,final):
        assert (row['actor_count'],row['door_count'],row['shared_blueprints'])==(7986,124,10)
        assert row['protected']['passed'] and not row['protected']['changed_protected_files']
        assert len(row['doors'])==124 and all(p['passed'] and p['proof']['passed'] for p in row['doors'])
    assert len(probe['variant_probes'])==15 and all(p['proof']['passed'] for p in probe['variant_probes'])
    assert len(applied['door_proofs'])==124 and len(applied['attachments'])==124
    assert all(p['passed'] and p['source_actor_unchanged'] and p['actor_name_preserved'] for p in applied['door_proofs'])
    assert len({g['blueprint'] for g in applied['groups']})==10
    assert sum(len(g['labels']) for g in applied['groups'])==124
    native_before=evidence('ExpectedOtherActors.json')
    native_after=evidence('ReadbackAfterCleanupOtherActors.json')
    assert native_before['actor_count']==native_after['actor_count']==7862
    assert {n:r['native_text_sha256'] for n,r in native_before['full_existing_actor_native'].items()}=={n:r['native_text_sha256'] for n,r in native_after['full_existing_actor_native'].items()}
    current={str(p):sha(p) for root in (C,R/'Config') for p in root.rglob('*') if p.is_file()}
    assert current==approve['protected_file_sha256']==refs_after['file_sha256']
    assert len(probe['new_asset_sha256'])==10 and probe['new_asset_sha256']==applied['new_asset_sha256']
    assert all(current[p]==h for p,h in probe['new_asset_sha256'].items())
    assert sha(W/'OfflineCleanupApproved.json')==clean['approval_sha256']
    manifest=read(clean['manifest_file']);assert sha(clean['manifest_file'])==clean['manifest_sha256']
    assert manifest['map_sha256']==current_sha
    approved={r['file']:r['current_sha256'] for r in approve['candidate_files']}
    assert len(approved)==len(manifest['files'])==clean['isolated_count']==plan['summary']['deletable_candidates']
    assert {r['original_path'] for r in manifest['files']}==set(approved)
    assert sha(W/'OwnershipPlan.json')==approve['ownership_plan_sha256']
    for row in manifest['files']:
        assert not Path(row['original_path']).exists()
        assert sha(row['isolated_path'])==row['sha256']==approved[row['original_path']]
    assert final['protected']['verified_owned_resources_isolated']==len(approved)
    # Every original file is either the single authorized map, an approved
    # exact own-unused package, or preserved byte-for-byte.
    baseline=evidence('ProtectedBefore.json')['file_sha256']
    for file,digest in baseline.items():
        if file==str(MAP):continue
        assert approved.get(file,current.get(file))==digest
    old_bps=sorted({p for g in design['groups'] for p in g['source_blueprints']})
    assert len(old_bps)==15
    after_rows={}
    for row in refs_after['assets']:after_rows.setdefault(row['package'].casefold(),[]).append(row)
    retained_old=[]
    for bp in old_bps:
        file=C/(bp.removeprefix('/Game/')+'.uasset')
        assert current[str(file)]==baseline[str(file)]
        rows=after_rows[bp.casefold()]
        v2=[r for row in rows for r in row['referencers'] if '/oldtownversion2/' in r.casefold()]
        assert v2,'Old door BP must still be retained for V2'
        retained_old.append(dict(blueprint=bp,file=str(file),sha256=current[str(file)],version2_referencers=sorted(set(v2))))
    disk={package(p).casefold() for p in C.rglob('*') if p.is_file() and p.suffix.lower() in ('.uasset','.umap')}
    assert disk==set(after_rows)
    removed_packages={r['package'].casefold() for r in approve['candidate_files']}
    before_rows={r['package'].casefold() for r in refs_before['assets']}
    assert before_rows-removed_packages==disk
    before_graph,after_graph=graph(refs_before),graph(refs_after)
    missing_before={(n,d) for n,ds in before_graph.items() if n in disk for d in ds if d not in before_rows}
    missing_after={(n,d) for n,ds in after_graph.items() if n in disk for d in ds if d not in disk}
    assert not missing_after-missing_before,sorted(missing_after-missing_before)
    assert not [(n,d) for n,ds in after_graph.items() if n not in removed_packages for d in ds if d in removed_packages]
    assert refs_after['forced_disk_rescan'] and refs_after['no_save_or_explicit_compile_called']
    protected_named={}
    for name in ('Yastar/Maps/L_Main.umap','CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap','Yastar/Blueprints/BP_LightSwitch.uasset'):
        file=C/name;assert current[str(file)]==baseline[str(file)]
        protected_named[name]=current[str(file)]
    total_bytes=sum(r['bytes'] for r in manifest['files'])
    proof_files=[W/n for n in ('AppliedDoorReuse.json','ReusableBlueprints.json','DoorReuseReadback.json','DoorReuseAfterCleanupReadback.json','OfflineCleanupApproved.json','OfflineCleanupResult.json','OwnershipPlan.json','AssetReferencesFresh.json','AssetReferencesAfterCleanup.json','Backup.json')]+completion_files
    final_report=dict(passed=True,status='PASS',completed_utc=datetime.now(timezone.utc).isoformat(),
        target_level=applied['target_level'],source_map_sha256=source_sha,map_sha256=current_sha,
        actor_count=7986,door_count=124,shared_blueprints=10,old_door_blueprints_retained=retained_old,
        groups=applied['groups'],variant_probes_passed=15,attached_hinges_preserved=124,
        other_actors_full_native_unchanged=7862,all_existing_user_content_preserved=True,
        protected_named_asset_sha256=protected_named,new_asset_sha256=probe['new_asset_sha256'],
        isolated_unused_owned_packages=len(approved),isolated_bytes=total_bytes,isolation_directory=clean['isolation_directory'],
        original_map_backup=backup['file'],no_forced_delete=True,new_missing_package_dependencies=[],
        registry_disk_packages=len(disk),evidence_sha256={str(p):sha(p) for p in proof_files})
    text=(f'# 原版老城区：门复用与自有资源清理完成\n\n'
        f'原版 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet` 的 **124套自有门现按实际尺寸共用10个蓝图**。左右开、平开/推拉、材质、碰撞和既有开合姿态均保留，124个附属铰链保留。\n\n'
        f'清理了 **{len(approved)}个已确认无引用的自有资源**，约 **{total_bytes/1024/1024:.2f} MiB**；资源已从Content移入可恢复备份。15个旧门蓝图仍被第二版使用，全部保留。归属不明或缺少创建校验的资源未清理。\n\n'
        f'独立重开地图验证通过：其余7862个对象完整数据一致；Main、第二版、BP_LightSwitch及用户原有资源文件未修改。清理后再次完整重开及全项目引用检查通过，没有新增缺失资源引用。\n\n'
        f'- 原图备份：`{backup["file"]}`\n- 资源隔离备份：`{clean["isolation_directory"]}`\n'
        f'- 新蓝图：`/Game/CodexGenerated/OldTown/DoorReuse_20261017/Blueprints`\n'
        f'- 当前地图SHA256：`{current_sha}`\n- 完整验收：`Saved/CodexOutputs/OldTownDoorReuse_20261017/FinalReview.json`\n')
    (R/'Docs/OldTownDoorReuseResult.md').write_text(text,encoding='utf-8')
    (W/'FinalReview.json').write_text(json.dumps(final_report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,doors=124,shared_blueprints=10,isolated=len(approved),MiB=round(total_bytes/1024/1024,2),map_sha256=current_sha),ensure_ascii=False))
if __name__=='__main__':main()
