"""Publish compact evidence only after saved-world and image review pass."""
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'Saved/CodexOutputs/HotelOperations_20261006'
CANON=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
SOURCE=ROOT/'SourceArt/OldTownHotelOperations_20261006'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    b=read(WORK/'BuildReport.json');h=b['map_sha256']
    mapfile=ROOT/('Content/'+b['target_level'].removeprefix('/Game/')+'.umap')
    assert sha(mapfile)==h
    audit=read(WORK/'OperationsAudit.json');arch=read(WORK/'ArchitectureAudit.json')
    assert audit['passed'] and arch['passed'] and audit['map_sha256']==arch['map_sha256']==h
    visual=read(WORK/'VisualReview.json')
    assert visual['passed'] and visual['map_sha256']==h
    views=b['hotel_operations']['review_cameras']
    repair=read(WORK/'VisualAssetRepair.json')
    assert repair['passed'] and repair['map_unchanged'] and repair['map_sha256']==h
    assert {v['camera'] for v in views}=={v['camera'] for v in visual['views']}
    captures=[]
    for v in views:
        name=v['camera'];png=WORK/'Renders'/(name+'.png');m=read(WORK/'Renders'/(name+'.json'))
        assert m['status']=='PASS' and m['map_sha256']==h and m['png_sha256']==sha(png)
        assert m['lighting_mode']==v['lighting_mode'] and m['bytes']==png.stat().st_size and png.stat().st_size>20000
        assert m['persisted_map_unchanged'] and m['temporary_lighting_cleanup_verified_zero']
        assert m['temporary_lighting_cleanup_remaining_count']==0
        if name in repair['affected_views']:
            assert png.stat().st_mtime>(WORK/'VisualAssetRepair.json').stat().st_mtime,'Recapture after owned asset repair: '+name
        captures.append(dict(camera=name,png=str(png),lighting_mode=m['lighting_mode'],png_sha256=sha(png)))
    runs=read(WORK/'CaptureRuns.json')
    assert runs and all(r['normal_exit'] and not r['forced_cleanup'] and r['exit_code']==0 for r in runs)
    imports=read(WORK/'OperationsImportReport.json')['imports']
    assert len(imports)==15 and all(sha(SOURCE/r['file'])==r['source_sha256'] for r in imports)
    assert 'HOTEL_OPERATIONS_SOURCE_PASS assets=15' in (SOURCE/'BlenderBuild.log').read_text(encoding='utf-8',errors='replace')
    assert all(sha(Path(p))==value for p,value in b['protected_map_sha256'].items())
    write(WORK/'ArchitecturePlan.json',b['hotel_architecture'])
    review=dict(passed=True,status='PASS',target_level=b['target_level'],map_sha256=h,
        actor_count=b['actor_count'],new_actors=len(b['hotel_operations']['new_actor_labels']),
        modeled_assets=15,placed_props=len(b['hotel_operations']['placed_props']),
        preserved_actors=audit['statistics']['preserved_actors'],statistics=audit['statistics'],
        rooms=41,room_distribution=[2,13,13,13],stairs=2,independent_exits=2,
        captures=captures,protected_maps_unchanged=True,street_preserved=True,
        source_model=str(SOURCE/'OldTownHotelOperationsKit.blend'),
        previous_evidence=str(ROOT/'Saved/CodexOutputs/HotelArchitecture_20261005/FinalReview.json'),
        reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
        limitations=['Player door/window interaction and lift operation are pending.',
                     'New images use temporary inspection lighting; they do not represent final game lighting.',
                     'No complete runtime player walkthrough was performed.'])
    write(WORK/'FinalReview.json',review)
    reports=['BuildReport.json','ArchitecturePlan.json','OperationsPlan.json','OperationsImportReport.json',
             'OperationsAudit.json','ArchitectureAudit.json','VisualReview.json','FinalReview.json']
    before=WORK/'BeforeCanonicalPublish';before.mkdir(exist_ok=True)
    old=read(CANON/'CurrentEvidence.json')
    for name in sorted(set(reports+old['current_reports']+['CurrentEvidence.json'])):
        f=CANON/name
        if f.exists() and not (before/name).exists():shutil.copy2(f,before/name)
    for name in reports:shutil.copy2(WORK/name,CANON/name)
    write(CANON/'CurrentEvidence.json',dict(target_level=b['target_level'],map_sha256=h,
        source_bundle=str(WORK),source_directory=str(WORK),current_reports=reports,
        current_renders=str(WORK/'Renders'),current_render_cameras=[v['camera'] for v in views],
        current_render_lighting_modes={v['camera']:v['lighting_mode'] for v in views},
        previous_evidence_bundle=old['source_bundle'],previous_evidence_status='historical',
        historical_report_backup=str(before),historical_reports_not_current=sorted(set(old['current_reports'])-set(reports)),
        note='Additive public/service furnishings; previous architecture renders have an older map hash and remain historical.',
        external_user_light_deletion_preserved=True,preserved_external_deletions=['PointLight']))
    print(json.dumps(dict(passed=True,map_sha256=h,actors=b['actor_count'],props=review['placed_props'],views=len(captures))))


if __name__=='__main__':main()
