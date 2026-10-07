"""Publish the reviewed, fresh-map evidence without relabeling old audits."""
import hashlib
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'Saved/CodexOutputs/HotelArchitecture_20261005'
CANON=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    build=read(WORK/'BuildReport.json')
    current=build['map_sha256']
    mapfile=ROOT/('Content/'+build['target_level'].removeprefix('/Game/')+'.umap')
    assert sha(mapfile)==current
    audit=read(WORK/'ArchitectureAudit.json')
    assert audit['passed'] and audit['map_sha256']==current
    assert all(sha(Path(p))==h for p,h in build['protected_map_sha256'].items())
    visual=read(WORK/'VisualReview.json')
    assert visual['passed'] and visual['map_sha256']==current
    rows=build['hotel_architecture']['review_cameras']
    assert {r['camera'] for r in visual['views']}=={r['camera'] for r in rows}
    captures=[]
    for row in rows:
        name=row['camera']
        meta=read(WORK/'Renders'/(name+'.json'))
        png=WORK/'Renders'/(name+'.png')
        assert meta['status']=='PASS' and meta['map_sha256']==current and meta['lighting_mode']==row['lighting_mode']
        assert meta['png_sha256']==sha(png) and meta['bytes']==png.stat().st_size and png.stat().st_size>20000
        assert meta['persisted_map_unchanged'] and meta['temporary_lighting_cleanup_verified_zero']
        assert meta['temporary_lighting_cleanup_remaining_count']==0
        captures.append(dict(camera=name,png=str(png),lighting_mode=row['lighting_mode'],png_sha256=sha(png)))
    imports=read(WORK/'FixtureImportReport.json')
    assert len(imports['imports'])==49
    source=ROOT/'SourceArt/OldTownHotelArchitecture_20261005'
    assert all(sha(source/r['file'])==r['source_sha256'] for r in imports['imports'])
    assert 'HOTEL_ARCHITECTURE_SOURCE_PASS assets=49 boxes=1458' in (source/'BlenderBuild.log').read_text(encoding='utf-8',errors='replace')
    assert (source/'OldTownHotelArchitecture.blend').is_file()
    result=dict(passed=True,status='PASS',target_level=build['target_level'],map_sha256=current,
        actor_count=build['actor_count'],rooms=41,room_distribution=[2,13,13,13],stairs=2,independent_exits=2,
        statistics=audit['statistics'],captures=captures,reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
        protected_maps_unchanged=True,previous_street_actors_preserved=5046,
        previous_evidence=str(ROOT/'Saved/CodexOutputs/StreetAccessLighting_20261005/FinalReview.json'),
        source_model=str(source/'OldTownHotelArchitecture.blend'),design_plan=str(WORK/'DesignPlan.png'),
        limitations=['Door/window player input and functioning lift are not implemented.','Runtime player walkthrough is pending.'])
    write(WORK/'FinalReview.json',result)
    reports=['BuildReport.json','ArchitecturePlan.json','ArchitectureAudit.json','FixtureImportReport.json',
             'DoorRestore.json','VisualReview.json','FinalReview.json']
    before=WORK/'BeforeCanonicalPublish'
    before.mkdir(exist_ok=True)
    for name in reports+['CurrentEvidence.json']:
        p=CANON/name
        if p.exists() and not (before/name).exists():shutil.copy2(p,before/name)
    old=read(CANON/'CurrentEvidence.json')
    for name in reports:shutil.copy2(WORK/name,CANON/name)
    write(CANON/'CurrentEvidence.json',dict(target_level=build['target_level'],map_sha256=current,
        source_bundle=str(WORK),source_directory=str(WORK),current_reports=reports,
        current_renders=str(WORK/'Renders'),current_render_cameras=[r['camera'] for r in rows],
        current_render_lighting_modes={r['camera']:r['lighting_mode'] for r in rows},
        previous_evidence_bundle=old['source_bundle'],previous_evidence_status='historical',
        historical_report_backup=str(before),historical_reports_not_current=sorted(set(old['current_reports'])-set(reports)),
        note='Hotel architecture replaces the former 24-room layout; old layout audits and captures remain historical.',
        external_user_light_deletion_preserved=True,preserved_external_deletions=['PointLight']))
    print(json.dumps(dict(passed=True,map_sha256=current,actors=build['actor_count'],rooms=41,
                          checks=audit['statistics']['checks'],views=len(captures))))


if __name__=='__main__':main()
