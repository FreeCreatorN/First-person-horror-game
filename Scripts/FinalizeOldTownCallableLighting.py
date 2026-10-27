"""Publish the original-town lighting addendum only after all final checks pass."""
import json,hashlib,struct
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1]
W=R/'Saved/CodexOutputs/OldTownCallableLighting_20261016'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')

def main():
    assert not (W/'FinalReview.json').exists(),'Accepted lighting bundle is immutable'
    applied=read(W/'Applied.json');assert applied['passed'] and sha(MAP)==applied['map_sha256']
    for name in ('Apply2.Completion.json','Readback1.Completion.json','RuntimeGame2.Completion.json'):
        c=read(W/name);assert c['normal_zero_exit'] and c['exit_code']==0,name
    runtime=read(W/'RuntimeValidation.json')
    assert runtime['passed'] and runtime['world_begun_play'] and runtime['game_world']
    assert (runtime['circuit_count'],runtime['initial_on_count'],runtime['initial_off_count'],runtime['unique_mid_count'])==(16,13,3,16)
    assert runtime['before_begin_play_calls_preserved'] and len(runtime['before_begin_play_cases'])==6
    assert all(c['passed'] and len(c['steps'])==9 and all(s['passed'] for s in c['steps']) for c in runtime['circuits'])
    assert all(c['passed'] for c in runtime['before_begin_play_cases'])
    audit=read(W/'ReadbackAudit.json');assert audit['passed'] and audit['controllers']==16 and audit['existing_actor_count']==7936
    materials=read(W/'MaterialPreservation.json');assert materials['passed'] and len(materials['masters'])==2
    independent=read(W/'IndependentReview.json');assert independent['passed']
    assert independent['original_input_vs_accepted_v2_static_geometry']['passed']
    assert independent['original_input_vs_accepted_v2_static_geometry']['nonempty_mesh_component_count']==12361
    visual=read(W/'VisualReview.json');assert visual['passed'] and visual['root_directly_viewed_all_four_frames']
    protected=read(W/'ProtectedBefore.json')['file_sha256']
    changed=[p for p,h in protected.items() if p!=str(MAP) and sha(p)!=h]
    assert not changed,changed
    assert all(sha(p)==h for p,h in applied['new_asset_sha256'].items())
    expected=set(protected)|set(applied['new_asset_sha256'])
    actual={str(p) for base in (R/'Content',R/'Config') for p in base.rglob('*') if p.is_file()}
    assert actual==expected,dict(added=list(actual-expected),missing=list(expected-actual))
    backup=read(W/'Backup.json');assert backup['passed'] and sha(backup['file'])==applied['source_map_sha256']==backup['source_sha256']
    v2pointer=R/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json'
    assert read(v2pointer)['source_bundle_name']=='OldTownVersion2_20261016'
    assert sha(R/'Content/CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap')=='151e9409f265b3c0d890589a800129037bd318600741c59ee942bdcd2bffb80d'
    previews=read(W/'Preview/CaptureRuns.json')
    rows={v['camera']:v for v in previews}
    labels=('CALL_Hotel_On','CALL_Hotel_Off','CALL_Street_On','CALL_Street_Off')
    assert set(rows)==set(labels)
    captures=[]
    for label in labels:
        row=rows[label]
        assert row['captured'] and row['normal_exit'] and not row['forced_cleanup'] and row['exit_code']==0
        png=W/'Preview/Renders'/(label+'.png');meta=read(png.with_suffix('.json'))
        assert meta['status']=='PASS' and meta['png_sha256']==sha(png) and meta['map_sha256']==applied['map_sha256']
        assert meta['persisted_map_unchanged'] and meta['appearance_assets_unchanged'] and meta['temporary_camera_cleanup_verified_zero']
        assert meta['temporary_lighting_cleanup_verified_zero'] and meta['temporary_lighting_cleanup_remaining_count']==0
        assert meta['lighting_mode']=='street_only' and meta['view_mode_verified']=='lit'
        assert struct.unpack('>II',png.read_bytes()[16:24])==(1920,1080)
        state=meta['circuit_state_at_capture'];level=1. if label.endswith('_On') else 0.
        assert state['level']==level and state['light_strength']==20*level and not state['configuration_error']
        assert all(x['visible']==(level>0) and x['intensity']==(x['base_intensity']*level) for x in state['lights'])
        owned=read(W/'Preview/Runs'/row['run_id']/'OwnedProcess.json')
        assert owned['normal_exit'] and not owned['forced_cleanup'] and owned['persisted_map_unchanged']
        proof=read(W/'Preview/Runs'/row['run_id']/'LightingCaptureProof.json')
        assert proof['passed'] and proof['editor_preview_restored'] and not proof['temporary_camera_remaining']
        assert visual['image_sha256'][label]==sha(png)
        captures.append(dict(camera=label,png=str(png),sha256=sha(png),run_id=row['run_id']))
    build=R/'Saved/CodexBuilds/CodexOldTownLights_20261016_Run4'
    plugin=R/'Plugins/CodexOldTownLights'
    for p in (plugin/'Source').rglob('*'):
        if p.is_file():assert sha(p)==sha(build/p.relative_to(plugin)),str(p)
    for p in (plugin/'Binaries/Win64').iterdir():
        if p.is_file():assert sha(p)==sha(build/p.relative_to(plugin)),str(p)
    assert 'BUILD SUCCESSFUL' in (W/'PluginBuild4.log').read_text(encoding='utf8',errors='replace')
    write(W/'GeometryInvariance.json',dict(passed=True,geometry_changes=False,
        exact_static_mesh_components=12362,nonempty_mesh_components=12361,
        original_to_v2_geometry_proof=str(W/'IndependentReview.json'),
        new_material_WPO_and_lamp_mask_proof=str(W/'MaterialPreservation.json'),
        fresh_native_geometry_export_or_overlap_scan_performed=False,
        explanation='Current original map exact geometry matches accepted V2 geometry; only 16 material bindings changed and old connected WPO/mask nodes are identical. This is an invariance proof, not a new scan.'))
    report_names=['Applied.json','Backup.json','ReadbackAudit.json','MaterialPreservation.json','IndependentReview.json','RuntimeValidation.json','RuntimeGame2.Completion.json',
        'RuntimeGame2.OwnedProcess.json','Apply2.Completion.json','Readback1.Completion.json','VisualReview.json','GeometryInvariance.json','FixturePlan.json','ProtectedBefore.json','PreSaveRetryProof.json']
    final=dict(passed=True,published=True,target_level=applied['target_level'],map_sha256=sha(MAP),
        source_map_sha256=applied['source_map_sha256'],existing_actor_count=7936,new_light_circuit_actors=16,actor_count=7952,
        material_overrides=16,new_assets=19,default_on=13,default_off=3,
        actual_game_world_steps=144,early_initialization_cases=6,protected_existing_file_count=len(protected)-1,
        user_assets_and_shared_assets_byte_unchanged=True,v2_evidence_pointer_not_replaced=True,
        backup=backup,captures=captures,report_sha256={n:sha(W/n) for n in report_names},
        new_asset_sha256=applied['new_asset_sha256'],
        plugin_file_sha256={str(p):sha(p) for p in plugin.rglob('*') if p.is_file() and 'Intermediate' not in p.parts},
        limitations=['Call the new controller actor through BPI_Interact or its public functions; no physical wall switch/character trace hotspot was added.',
            'Runtime verified in UnrealEditor -game, including actual BeginPlay and Blueprint interface calls; a packaged shipping build was not tested.',
            'No pending performance settings or scene streaming changes were applied.'],
        historical_pre_save_retry=dict(first_attempt_map_saved=False,reason='UE5.7 scalar setter always returns false; fixed by verifying the actual read-back value.'),
        completed_utc=datetime.now(timezone.utc).isoformat())
    write(W/'FinalReview.json',final)
    write(W/'CurrentLighting.json',dict(passed=True,final_review_file=str(W/'FinalReview.json'),final_review_sha256=sha(W/'FinalReview.json'),target_level=applied['target_level'],map_sha256=sha(MAP)))
    print('ORIGINAL_TOWN_CALLABLE_LIGHTING_FINAL_PASS',sha(MAP))

if __name__=='__main__':main()
