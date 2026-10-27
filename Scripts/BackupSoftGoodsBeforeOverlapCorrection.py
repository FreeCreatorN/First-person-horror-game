"""Keep the failed unpublished Stage3 bundle intact before its model repair."""
import shutil,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1]
W=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    assert not json.loads((W/'SurfaceScanSummary.json').read_text())['passed']
    dest=R/'Saved/CodexBackups'/('SoftGoodsBeforeOverlapCorrection_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    dest.mkdir(parents=True,exist_ok=False)
    files=[]
    for folder in (W,R/'SourceArt/OldTownRealismRefinement_20261013/SoftGoods',R/'Content/CodexGenerated/OldTown/SoftGoodsRefinement_20261013'):
        files.extend(p for p in folder.rglob('*') if p.is_file())
    files.extend([R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap',R/'Scripts/BuildOldTownRealismRefinementSoftGoods.py'])
    rows=[]
    for i,p in enumerate(sorted(set(files))):
        rel=p.relative_to(R);out=dest/rel;assert out.resolve().is_relative_to(dest.resolve())
        digest=sha(p);out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
        assert sha(out)==digest==sha(p)
        rows.append(dict(relative_path=rel.as_posix(),sha256=digest,bytes=p.stat().st_size))
        if i%100==0:print('CORRECTION_BACKUP_VERIFIED',i,len(files),flush=True)
    report=dict(passed=True,backup_directory=str(dest),files=rows,file_count=len(rows),reason='14 exposed legacy mattress side-face overlaps; Stage3 not published')
    (dest/'Manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (W/'OverlapDiagnosis/BeforeCorrectionBackup.json').write_text(json.dumps(dict(passed=True,backup_directory=str(dest),manifest_sha256=sha(dest/'Manifest.json')),indent=2),encoding='utf-8')
    print('SOFT_GOODS_CORRECTION_BACKUP_PASS',str(dest),flush=True)
if __name__=='__main__':main()
