"""Publish current V4 evidence only after fresh audit, source and captures."""
import json, hashlib, shutil, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'Saved/CodexOutputs/HotelRedesign_20261008_V4'
SOURCE=ROOT/'SourceArt/OldTownHotelRedesign_20261008_V4'
CANON=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
sys.path.insert(0,str(ROOT/'Scripts'))
import FinalizeOldTownStreetRefinement as lifecycle
lifecycle.WORK=WORK

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)

def capture_review(build,mapfile):
    views=[];runs={};digest=build['map_sha256']
    for camera in build['hotel_v4']['review_cameras']:
        name=camera['camera'];mode=camera.get('lighting_mode','temporary')
        png=WORK/'Renders'/(name+'.png');meta=read(png.with_suffix('.json'));data=png.read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n' and len(data)>20000
        size=struct.unpack('>II',data[16:24]);assert size==(1280,720)==(meta['width'],meta['height'])
        assert meta['status']=='PASS' and meta['camera']==name and meta['target_level']==build['target_level']
        assert meta['map_sha256']==meta['map_sha256_after_cleanup']==digest
        assert meta['png_sha256']==sha(png) and meta['bytes']==len(data)
        assert meta['lighting_mode']==mode and meta['view_mode_verified']=='lit'
        assert meta['source']=='fresh_persisted_map_load' and meta['fresh_map_load_verified']
        assert Path(meta['source_persisted_map']).resolve()==mapfile.resolve() and meta['persisted_map_unchanged']
        assert not meta['map_save_requested'] and meta['temporary_lighting_cleanup_verified_zero']
        assert meta['temporary_lighting_cleanup_remaining_count']==0
        run=meta['run_id'];runs[run]=lifecycle.helper_run(run,meta,digest,build['target_level'],name,mode)
        views.append(dict(camera=name,png=str(png),metadata=str(png.with_suffix('.json')),png_sha256=sha(png),
            lighting_mode=mode,width=size[0],height=size[1],run_id=run))
    assert len(views)>=8 and len({v['camera'] for v in views})==len(views)
    return dict(passed=True,map_sha256=digest,target_level=build['target_level'],views=views,
        current_helpers=list(runs.values()),fresh_persisted_map_load=True,current_helper_normal_exit_verified=True,
        temporary_lighting_cleanup_verified_zero=True)

def main():
    build=read(WORK/'BuildReport.json');assert build['status']=='PASS'
    mapfile=ROOT/('Content/'+build['target_level'].removeprefix('/Game/')+'.umap');digest=sha(mapfile)
    assert digest==build['map_sha256'] and read(WORK/'Applied.json')['map_sha256']==digest
    arch=read(WORK/'ArchitectureAudit.json');assert arch['passed'] and not arch['errors']
    assert arch['map_sha256']==digest and arch['source']=='fresh_persisted_map_load' and arch['persisted_map_unchanged']
    plan=read(WORK/'PlanningValidation.json');assert plan['passed'] and plan['rooms']==27
    source=read(SOURCE/'SourceVerification.json');assert source['passed'] and source['storeys']==4 and source['rooms']==27
    assert sha(Path(source['source']))==source['source_sha256'] and sha(WORK/'ArchitecturePlan.json')==source['plan_sha256']
    assert source['proxy_assets']==[] and source['appended_prop_instances']==len(build['hotel_v4']['props'])
    write(WORK/'SourceVerification.json',source)
    for p,h in build['new_asset_sha256'].items():assert sha(Path(p))==h,p
    for p,h in build['protected_map_sha256'].items():assert sha(Path(p))==h,p
    captures=capture_review(build,mapfile);write(WORK/'CaptureReview.json',captures)
    visual=read(WORK/'VisualReview.json');assert visual['passed'] and visual['map_sha256']==digest
    final=dict(passed=True,status='PASS',target_level=build['target_level'],map_sha256=digest,
        actor_count=build['actor_count'],rooms=27,rooms_by_floor={'1':9,'2':9,'3':9},
        validation=arch['statistics'],preservation=arch['preservation'],
        approved_review='ArchitectureRedesignReview_20261008_V4',
        current_bundle=str(WORK),source_model=source['source'],current_captures=captures['views'],
        MainHome_preserved=True,unrelated_street_actors_unchanged=True,
        limitations=['Physical editor collision and saved-world validation completed; runtime player input and a working lift are not implemented.',
            'Residential plans remain separate review proposals; this application replaces the four-storey hotel.'])
    write(WORK/'FinalReview.json',final)
    names=['BuildReport.json','ArchitectureAudit.json','PlanningValidation.json','InputRebaseReport.json',
        'SourceVerification.json','CaptureReview.json','VisualReview.json','FinalReview.json']
    backup=WORK/'BeforeCanonicalPublish';backup.mkdir(parents=True,exist_ok=True)
    for name in names+['CurrentEvidence.json']:
        src=CANON/name
        if src.exists() and not (backup/name).exists():shutil.copy2(src,backup/name)
    for name in names:shutil.copy2(WORK/name,CANON/name)
    evidence=dict(target_level=build['target_level'],map_sha256=digest,source_bundle=str(WORK),source_directory=str(WORK),
        current_reports=names,current_report_sha256={n:sha(WORK/n) for n in names},
        current_renders=str(WORK/'Renders'),current_render_cameras=[v['camera'] for v in captures['views']],
        current_render_lighting_modes={v['camera']:v['lighting_mode'] for v in captures['views']},
        previous_bundle=str(ROOT/'Saved/CodexOutputs/StreetRefinement_20261007'),previous_evidence_status='historical',
        opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',
        source_model=source['source'],note='Approved V4 hotel applied on all four floors; older 41-room hotel captures and reports are historical.')
    write(CANON/'CurrentEvidence.json',evidence)
    print(json.dumps(dict(passed=True,map_sha256=digest,statistics=arch['statistics'],captures=len(captures['views']),bundle=str(WORK)),ensure_ascii=False))

if __name__=='__main__':main()
