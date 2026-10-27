"""Verified complete project-side town snapshot before the requested V2 copy."""
import json,shutil
from pathlib import Path
from datetime import datetime,timezone
from OldTownMainLightingCommon import sha,read,write,ref,R
W=R/'Saved/CodexOutputs/OldTownVersion2_20261016'
def main():
    i=read(W/'Input.json');assert i['passed']
    source=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';assert sha(source)==i['map_sha256']
    files={**i['referenced_game_package_sha256'],**i['all_original_generated_file_sha256'],str(source):i['map_sha256']}
    mainfile=R/'Content/Yastar/Maps/L_Main.umap';files.pop(str(mainfile),None)
    for folder in ('SourceArt/OldTownRealism_20261012','SourceArt/OldTownRealismRefinement_20261013','Scripts','Docs'):
        for p in (R/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:files[str(p.resolve())]=sha(p)
    stage=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
    for name in ('Applied.json','After.json','AfterSnapshot.json','AppearanceSnapshot.json','SourceAudit.json','PreservationAudit.json',
        'GeometryPreservation.json','AfterSummary.json','GeometryAfter.json','OverlapCorrection.json','RunCompletion.json'):
        p=stage/name;files[str(p.resolve())]=sha(p)
    for p in W.glob('*.json'):files[str(p.resolve())]=sha(p)
    base=R/'Saved/CodexBackups';dest=base/('OldTownCompleted_BeforeVersion2_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    assert dest.resolve().is_relative_to(base.resolve());dest.mkdir(parents=True,exist_ok=False)
    rows=[]
    for n,(file,digest) in enumerate(sorted(files.items())):
        p=Path(file).resolve();assert p.is_relative_to(R)
        relative=p.relative_to(R);out=dest/relative;assert out.resolve().is_relative_to(dest.resolve())
        assert sha(p)==digest;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
        assert sha(out)==digest==sha(p)
        rows.append(dict(relative_path=relative.as_posix(),sha256=digest,bytes=p.stat().st_size))
        if n%250==0:print('VERSION2_BACKUP_VERIFIED',n,len(files),flush=True)
    main_sha=sha(mainfile);mainref=dest/'ReferenceOnly/L_Main.umap';mainref.parent.mkdir();shutil.copy2(mainfile,mainref)
    assert sha(mainref)==main_sha==sha(mainfile)
    manifest=dict(passed=True,completed_before_map_copy=True,user_map_sha256=i['map_sha256'],files=rows,file_count=len(rows),
        total_bytes=sum(r['bytes'] for r in rows),source_input=ref(W/'Input.json'),backup_directory=str(dest),
        main_reference_only=dict(relative_path='ReferenceOnly/L_Main.umap',sha256=main_sha,automatically_restore=False))
    write(dest/'Manifest.json',manifest)
    (dest/'恢复说明.txt').write_text('老城区第二版复制前的完整项目侧备份。保留了用户当前地图、引用依赖、全部原生成包、模型源与验收资料。\nReferenceOnly/L_Main.umap仅作参考，恢复老城区时不要覆盖你自己的Main。\n此备份不包含任何性能设置调整。Manifest逐文件SHA256已核验。',encoding='utf-8')
    write(W/'Backup.json',dict(passed=True,backup_directory=str(dest),manifest=ref(dest/'Manifest.json'),map_sha256=i['map_sha256'],file_count=len(rows),total_bytes=manifest['total_bytes']))
    print('CURRENT_OLDTOWN_VERSION2_BACKUP_PASS',str(dest),len(rows),flush=True)
if __name__=='__main__':main()
