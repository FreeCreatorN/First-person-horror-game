"""Verify fresh evidence and publish the material stage; no UE asset writes."""
import argparse,json,re,shutil,hashlib
from pathlib import Path
from datetime import datetime,timezone
from VerifyOldTownRealismRefinement import verify_stage,read,sha,reference
ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'Saved/CodexOutputs/OldTownRealismRefinement_20261013'
CANON=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
MAP=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
REPORTS=['Baseline.json','MaterialPrescription.json','ApprovedPlan.json','Applied.json','BuildReport.json',
 'After.json','AfterSnapshot.json','AppearanceSnapshot.json','MaterialBuild.json','MaterialNativeAudit.json',
 'LightInput.json','LightAudit.json','GeometryPreservation.json','PreservationAudit.json','AfterSummary.json',
 'CoplanarScan.json','InternalOcclusionScan.json','SurfaceScanSummary.json','LampMaskAudit.json',
 'CaptureSetup.json','VisualReview.json','CaptureReview.json','RunCompletion.json','FinalReview.json']
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def require(ok,message):
    if not ok:raise RuntimeError(message)
def captures(directory,cameras,lighting,mapsha,packages):
    runs=read(directory/'CaptureRuns.json');by={r['camera']:r for r in runs}
    require(set(by)==set(cameras),'Capture coverage differs: '+str(directory))
    rows=[];owned={}
    for name in cameras:
        r=by[name];require(r['captured'] and not r.get('reused') and not r.get('forced_cleanup') and r.get('exit_code')==0 and r.get('normal_exit'),
                         'Capture helper did not finish normally: '+name)
        png=directory/'Renders'/(name+'.png');meta=png.with_suffix('.json');m=read(meta)
        require(m['status']=='PASS' and m['map_sha256']==mapsha and m['source']=='fresh_persisted_map_load'
            and m['png_sha256']==sha(png) and m['bytes']==png.stat().st_size and png.stat().st_size>20000
            and [m['width'],m['height']]==[1920,1080] and m['lighting_mode']==lighting and m['view_mode_verified']=='lit',
            'Wrong capture binding: '+name)
        require(m['new_asset_sha256']==m['asset_sha256_after_cleanup']==packages and m['appearance_assets_unchanged'] is True
            and m['temporary_lighting_cleanup_verified_zero'] is True and m['temporary_lighting_cleanup_remaining_count']==0
            and m['persisted_map_unchanged'] is True and m['map_save_requested'] is False,'Capture changed source or left lights: '+name)
        run_id=m['run_id'];owned[run_id]=m['owned_editor_pid']
        row=dict(camera=name,lighting=lighting,image=reference(png),metadata=reference(meta));rows.append(row)
    for run_id,pid in owned.items():
        run=directory/'Runs'/run_id;o=read(run/'OwnedProcess.json');b=read(run/'CaptureBatch.json')
        require(o['owned_editor_pid']==pid==b['owned_editor_pid'] and b['status']=='PASS' and b['map_sha256']==mapsha,
                'Wrong capture process ownership.')
        require(b['temporary_lighting']['cleanup_verified_zero'] and b['temporary_lighting']['remaining_count']==0,
                'Capture cleanup incomplete.')
        require(b['new_asset_sha256']==b['asset_sha256_after_cleanup']==packages and b['persisted_map_unchanged'],
                'Capture batch source changed.')
    return dict(passed=True,directory=str(directory),runs=reference(directory/'CaptureRuns.json'),rows=rows,
        normally_exited_batches=len(owned),temporary_lights_remaining=0)
def main(publish=False):
    baseline,plan,after=map(read,[W/'Baseline.json',W/'ApprovedPlan.json',W/'After.json'])
    preservation=verify_stage(baseline,plan,after);digest=sha(MAP);build=read(W/'BuildReport.json')
    packages={**baseline['previous_asset_sha256'],**plan['new_asset_sha256']}
    require(packages==build['new_asset_sha256'] and build['map_sha256']==digest,'Wrong current BuildReport binding.')
    require(len(plan['new_asset_sha256'])==239 and len(packages)==1166 and len(plan['components'])==3430 and not plan['models'],
            'Unapproved material-only stage footprint.')
    runs=read(W/'RunCompletion.json');require(runs['passed'] and len(runs['runs'])>=2,'Missing helper normal exits.')
    for run in runs['runs']:
        require(run['exit_code']==0,'A required commandlet failed.')
        text=Path(run['log']['file']).read_text(encoding='utf-8-sig',errors='replace')
        require(sha(run['log']['file'])==run['log']['sha256'] and run['success_token'] in text and 'LogExit: Exiting.' in text,
                'Helper log lacks completion or changed.')
        require(not re.search(r'(?:LogMaterial|LogShaderCompilers).*?(?:Error:|Failed to compile|error [A-Z]+\d+|Missing.*Texture)',text,re.I),
                'A shader failed in the completed helper.')
        require('Python script executed with errors' not in text,'A required Python commandlet failed.')
    for name in ['MaterialNativeAudit.json','LightAudit.json','GeometryPreservation.json','PreservationAudit.json','LampMaskAudit.json','AfterSummary.json']:
        d=read(W/name);require(d['passed'] and d.get('map_sha256',digest)==digest,name+' rejected or stale.')
    geometry=reference(W/'GeometryAfter.json');surface=read(W/'SurfaceScanSummary.json')
    require(surface['passed'] and surface['provenance']['source_map_sha256']==digest
        and surface['provenance']['source_geometry_sha256']==geometry['sha256'],'Surface scan source differs.')
    require(surface['scope']['include_internal'] is True and surface['scope']['axis_only'] is False
        and surface['scope']['plane_tolerance_cm']==.03 and surface['scope']['normal_tolerance']==.0001
        and surface['scope']['minimum_overlap_area_cm2']==1. and surface['stats'].get('non_axis_faces_skipped',0)==0,
        'The scan scope/threshold changed or skipped faces.')
    require(surface['counts']['exposed_groups']==surface['counts']['exact_duplicate_box_groups']==0,'Exposed overlap remains.')
    cap=captures(W/'Captures',build['hotel_openings_review_cameras'],'temporary',digest,packages)
    lampcap=captures(W/'LampCaptures',['CAM_StreetAccess_Lamp','CAM_V4_TopGallery','CAM_StreetAccess_NightStreet'],'street_only',digest,packages)
    write(W/'CaptureReview.json',dict(passed=True,map_sha256=digest,material_review=cap,actual_light_review=lampcap))
    visual=read(W/'VisualReview.json')
    expected={r['image']['file']:r['image']['sha256'] for data in [cap,lampcap] for r in data['rows']}
    require(visual['passed'] and visual['map_sha256']==digest and visual['image_sha256']==expected,
            'Actual visual review is absent, incomplete or stale.')
    for path,h in {**packages,**baseline['protected_file_sha256']}.items():require(sha(path)==h,'Protected/source package changed: '+path)
    require(sha(baseline['preexisting_actor_reload_change']['source_blueprint']['file'])
        ==baseline['preexisting_actor_reload_change']['source_blueprint']['sha256'],'User pickup Blueprint changed after input freeze.')
    result=dict(passed=True,published=bool(publish),stage='OldTownRealismRefinement_20261013',
        target_level=build['target_level'],source_map_sha256=baseline['source_map_sha256'],map_sha256=digest,
        actor_count=8014,scene_component_count=13920,changed_components=3430,changed_actors=preservation['changed_actors'],
        model_changes=0,new_material_masters=14,new_material_instances=225,emissive_fixtures=16,
        immutable_previous_packages=927,new_packages=239,current_asset_sha256=packages,
        actual_light_properties_preserved=True,pose_parent_collision_and_wpo_preserved=True,
        original_mainhome_structure_preserved=True,whole_map_geometry=geometry,
        scan=reference(W/'SurfaceScanSummary.json'),captures=reference(W/'CaptureReview.json'),
        visual_review=reference(W/'VisualReview.json'),current_user_main_sha256=sha(ROOT/'Content/Yastar/Maps/L_Main.umap'),
        preexisting_user_changes=[baseline['preexisting_protected_map_changes'],baseline['preexisting_actor_reload_change']],
        limitations=visual['limitations'],completed_utc=datetime.now(timezone.utc).isoformat())
    write(W/'FinalReview.json',result)
    if publish:
        historical=W/'Before/CanonicalReports';historical.mkdir(parents=True,exist_ok=True)
        pointer=read(W/'Before/CurrentEvidence.json')
        for name in pointer['current_reports']:
            if (CANON/name).exists():shutil.copy2(CANON/name,historical/name)
        for name in REPORTS:shutil.copy2(W/name,CANON/name)
        hashes={name:sha(W/name) for name in REPORTS}
        require(all(sha(CANON/name)==h for name,h in hashes.items()),'Canonical report copy differs.')
        current=dict(target_level=build['target_level'],map_sha256=digest,source_map_sha256=baseline['source_map_sha256'],
            source_bundle_name='OldTownRealismRefinement_20261013',source_directory=str(W),source_bundle=str(W),
            current_reports=REPORTS,current_report_sha256=hashes,current_asset_sha256=packages,
            current_final_review=str(W/'FinalReview.json'),current_final_review_sha256=sha(W/'FinalReview.json'),
            current_capture_directory=str(W/'Captures'),current_capture_runs_file=str(W/'Captures/CaptureRuns.json'),
            current_capture_runs_sha256=sha(W/'Captures/CaptureRuns.json'),current_render_cameras=build['hotel_openings_review_cameras'],
            current_render_geometry=geometry['file'],current_render_geometry_sha256=geometry['sha256'],
            current_actor_snapshot=str(W/'AfterSnapshot.json'),current_actor_snapshot_sha256=sha(W/'AfterSnapshot.json'),
            current_lamp_capture_directory=str(W/'LampCaptures'),current_renders=expected,
            previous_bundle=pointer['source_directory'],previous_evidence_status='preserved prior accepted stage; current materials supersede',
            actor_count=8014,hotel_actor_count=2975,outside_hotel_actor_count=5039,
            changed_component_count=3430,changed_actor_count=preservation['changed_actors'],
            scope='Whole-map wall/wood/fabric materials plus 16 luminous lamp surfaces; geometry/layout/photometry preserved.',
            opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',
            published_utc=datetime.now(timezone.utc).isoformat())
        write(CANON/'CurrentEvidence.json',current)
    print(json.dumps(dict(passed=True,published=publish,map_sha256=digest,emissive_fixtures=16,current_packages=len(packages))))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args();main(args.publish)
