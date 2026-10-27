"""Snapshot accepted OldTown content/sources before the authorized light change."""
import json,shutil,uuid
from datetime import datetime,timezone
from pathlib import Path
from VerifyOldTownSoftGoodsRefinement import read,sha
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownMainLighting_20261015'
S=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
def main():
    pointer_file=R/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json';pointer=read(pointer_file)
    assert pointer['source_bundle_name']==S.name
    review=read(S/'FinalReview.json');assert review['passed'] and review['published'] and sha(S/'FinalReview.json')==pointer['current_final_review_sha256']
    target=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';assert sha(target)==pointer['map_sha256']
    baseline=read(S/'Baseline.json');expected={**pointer['current_asset_sha256'],**baseline['protected_file_sha256'],str(target):pointer['map_sha256']}
    for p,h in expected.items():assert sha(p)==h,p
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    base=R/'Saved/CodexBackups';dest=base/('OldTown_BeforeMainDirectional_'+stamp)
    assert dest.resolve().is_relative_to(base.resolve());dest.mkdir(parents=True,exist_ok=False)
    files={Path(p).resolve():h for p,h in expected.items() if Path(p).resolve().is_relative_to(R)}
    # Include complete authoring sources, reproducible scripts, and current
    # acceptance reports/captures. Main stays an independent user-owned map.
    for folder in (R/'SourceArt/OldTownRealism_20261012',R/'SourceArt/OldTownRealismRefinement_20261013',R/'Scripts',R/'Docs'):
        for p in folder.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:files[p.resolve()]=sha(p)
    for name in pointer['current_reports']:
        p=S/name;assert sha(p)==pointer['current_report_sha256'][name];files[p.resolve()]=sha(p)
    for p in (pointer_file,S/'GeometryAfter.json'):
        files[p.resolve()]=sha(p)
    for folder in ('Captures','LampCaptures','SoftGoodsCaptures'):
        for p in (S/folder/'Renders').glob('*'):
            if p.is_file():files[p.resolve()]=sha(p)
    main_file=R/'Content/Yastar/Maps/L_Main.umap';main_sha=sha(main_file)
    rows=[]
    for i,(source,digest) in enumerate(sorted(files.items())):
        relative=source.relative_to(R);out=dest/relative
        assert out.resolve().is_relative_to(dest.resolve());out.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,out);assert sha(out)==digest==sha(source),str(source)
        rows.append(dict(relative_path=relative.as_posix(),source=str(source),sha256=digest,bytes=out.stat().st_size))
        if i%200==0:print('BACKUP_FILES_VERIFIED',i,'/',len(files),flush=True)
    # Reference only: intentionally outside Content, so restoring OldTown does
    # not roll the user's independently edited Main back to this snapshot.
    reference=dest/'ReferenceMain/L_Main.umap';reference.parent.mkdir();shutil.copy2(main_file,reference)
    assert sha(reference)==main_sha==sha(main_file)
    for p,h in expected.items():assert sha(p)==h,p
    manifest=dict(passed=True,completed_before_lighting_write=True,backup_directory=str(dest),
        oldtown_map_sha256=pointer['map_sha256'],accepted_bundle=str(S),files=rows,file_count=len(rows),
        total_bytes=sum(r['bytes'] for r in rows),current_asset_packages=len(pointer['current_asset_sha256']),
        engine_dependencies_not_copied={p:h for p,h in expected.items() if not Path(p).resolve().is_relative_to(R)},
        main_reference_only=dict(file=str(reference),sha256=main_sha,restore_to_main_automatically=False),
        completed_utc=datetime.now(timezone.utc).isoformat())
    (dest/'BackupManifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (dest/'恢复说明.txt').write_text('这是复制L_Main方向光之前的老城区备份。Content包含老城区地图、配套生成资产及保护的项目依赖；SourceArt、Scripts、Docs保留源模型和制作资料。\n恢复前关闭UE，再按项目相对路径恢复需要的目录。ReferenceMain仅供光源参考，不要自动覆盖你正在编辑的Main。\nBackupManifest逐文件记录SHA256并已核对。',encoding='utf-8')
    W.mkdir(parents=True,exist_ok=True)
    (W/'BackupBeforeLighting.json').write_text(json.dumps(dict(passed=True,backup_directory=str(dest),
        manifest_file=str(dest/'BackupManifest.json'),manifest_sha256=sha(dest/'BackupManifest.json'),
        oldtown_map_sha256=pointer['map_sha256'],file_count=len(rows),current_asset_packages=len(pointer['current_asset_sha256'])),ensure_ascii=False,indent=2),encoding='utf-8')
    print('OLDTOWN_BEFORE_LIGHTING_BACKUP_PASS',str(dest),len(rows),flush=True)
if __name__=='__main__':main()
