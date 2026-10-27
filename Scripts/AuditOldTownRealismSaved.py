"""Fresh saved level architecture, render export and native PBR acceptance."""
import sys,json,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
WORK=ROOT/'Saved/CodexOutputs/OldTownRealism_20261012'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    import AuditOldTownHotelDetails as detail
    detail.WORK=WORK;detail.main()
    build=read(WORK/'BuildReport.json')
    for n in ('GeometryAfter.json','AfterSummary.json'):
        data=read(WORK/n);data['new_asset_sha256']=build['new_asset_sha256']
        (WORK/n).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    import AuditOldTownRealismAppearance as appearance
    appearance.main()
    unreal.log('REALISM_FULL_SAVED_AUDIT_PASS')
if __name__=='__main__':
    try:main()
    except Exception:(WORK/'SavedAuditFailure.json').write_text(json.dumps(dict(passed=False,traceback=traceback.format_exc())),encoding='utf-8');raise
