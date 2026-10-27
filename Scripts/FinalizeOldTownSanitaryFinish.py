"""Publish rounded cistern evidence only after saved geometry and fresh captures pass."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts'))
import FinalizeOldTownSanitaryShapes as common
import OldTownSanitaryFinishPlan as recipe

WORK=ROOT/'Saved/CodexOutputs/SanitaryFinish_20261012'
SOURCE=ROOT/'Saved/CodexOutputs/SanitaryShapes_20261011'
CANON=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET=common.TARGET
SOURCE_SHA='96a927f42d52477d371665aad35ac8fdd85406eb42a91940cf047213cde8c44d'
CAMERAS=common.CAMERAS
read,sha,require,write,hashes=common.read,common.sha,common.require,common.write,common.hashes
common.WORK,common.SOURCE,common.SOURCE_SHA=WORK,SOURCE,SOURCE_SHA

def verify_asset(optimization):
    rows=optimization.get('new_assets',[])
    require(len(rows)==1 and rows[0].get('asset_key')=='Toilet','Exactly one toilet clone is required.')
    asset=rows[0]
    package='/Game/CodexGenerated/OldTown/Meshes/SanitaryFinish_20261012/SM_OTS_Arch_Toilet_Shaped'
    file=ROOT/('Content/'+package.removeprefix('/Game/')+'.uasset')
    require(asset.get('asset')==package+'.SM_OTS_Arch_Toilet_Shaped'
            and Path(asset.get('file','')).resolve()==file.resolve()
            and sha(file)==asset.get('sha256'),'Owned clone path/hash differs.')
    source=recipe.TOILET_SOURCE
    source_file=ROOT/('Content/'+source.removeprefix('/Game/')+'.uasset')
    require(asset.get('source')==source+'.'+source.split('/')[-1]
            and Path(asset.get('source_file','')).resolve()==source_file.resolve()
            and sha(source_file)==asset.get('source_sha256'),'Starting toilet source changed.')
    expected=common.json.loads(common.json.dumps(dict(schema=recipe.SCHEMA,pieces=recipe.build_pieces(),removals=recipe.source_removal_specs())))
    require(common.same_recipe(asset.get('shape_recipe'),expected),'Declared rounded geometry differs from pure recipe.')
    require(asset.get('render_indices_reversed') is True
            and asset.get('retained_source_faces_verified_in_original_sections') is True
            and set(asset.get('removed_part_names',[]))=={r['name'] for r in recipe.source_removal_specs()}
            and len(asset.get('removed_part_names',[]))==len(recipe.source_removal_specs())
            and asset.get('added_triangles_per_material_section')==[sum(len(p['triangles']) for p in recipe.build_pieces()),0]
            and asset.get('collision_signature') and len(asset.get('materials',[]))==2,'Actual clone preservation evidence is incomplete.')
    frozen=Path(optimization.get('recipe_file',''))
    require(frozen.resolve()==(ROOT/'SourceArt/OldTownSanitaryFinish_20261012/Recipe.json').resolve()
            and sha(frozen)==optimization.get('recipe_sha256')
            and common.same_recipe(read(frozen),expected) and recipe.audit_recipe().get('passed') is True,
            'Frozen source-art geometry changed or failed.')
    normals_path=WORK/'FinishRenderNormals.json';normals=read(normals_path)
    nr=normals.get('assets',[])
    removed=sum(r['triangles'] for r in recipe.source_removal_specs())
    added=sum(len(p['triangles']) for p in recipe.build_pieces())
    require(removed==215 and normals.get('map_sha256')==optimization['map_sha256']
            and len(nr)==1 and nr[0].get('asset')==asset['asset']
            and nr[0].get('asset_key')=='Toilet' and nr[0].get('sha256')==asset['sha256']
            and nr[0].get('parts')==dict(retained=dict(positive=0,negative=3887-removed,zero=0),
                new=dict(positive=0,negative=added,zero=0),
                new_relative_to_pure_outward_cross=dict(positive=added,negative=0,zero=0)),
            'Actual saved new render normals do not all face outward.')
    return asset,dict(passed=True,source_art_recipe=str(frozen),source_art_recipe_sha256=sha(frozen),recipe_schema=recipe.SCHEMA),dict(passed=True,file=str(normals_path),sha256=sha(normals_path),outward_new_faces=added,retained_faces=3887-removed)

def preservation(build,previous,before,after,plan,optimization,asset,geometry,architecture,saved):
    digest=build['map_sha256'];old,new=before['actors'],after['actors']
    original_snapshot=read(SOURCE/'AfterSnapshot.json');rebase=read(WORK/'ProtectedMapInputRebase.json')
    main_file=str(ROOT/'Content/Yastar/Maps/L_Main.umap')
    current_protected=deepcopy(original_snapshot['protected_map_sha256'])
    current_protected[main_file]='629d295921d48a016aad82113e70eb740378b917120ed31354005c9c6bff5578'
    require(rebase.get('passed') is True and rebase.get('source_map_sha256')==SOURCE_SHA
            and rebase.get('source')=='current_disk_before_map_apply'
            and rebase.get('recorded_input')==original_snapshot['protected_map_sha256']
            and rebase.get('current_input')==current_protected
            and rebase.get('changes')==[dict(file=main_file,previous_sha256=original_snapshot['protected_map_sha256'][main_file],current_sha256=current_protected[main_file])]
            and rebase.get('preserved_current_copy')==str(WORK/'Before/ProtectedMaps/L_Main.umap')
            and rebase.get('preserved_current_copy_sha256')==current_protected[main_file]
            and sha(rebase['preserved_current_copy'])==current_protected[main_file],
            'The sole input protected-map update lacks exact current-disk/backup evidence.')
    expected_snapshot=deepcopy(original_snapshot);expected_snapshot['protected_map_sha256']=current_protected
    require(previous.get('status')=='PASS' and previous.get('map_sha256')==SOURCE_SHA
            and before==expected_snapshot and before.get('passed') is True
            and before.get('target_level')==TARGET and before.get('source_map_sha256')==SOURCE_SHA,
            'Starting map/snapshot is not the approved source.')
    backup=WORK/'Before'
    require(sha(backup/'L_OldTownSchoolStreet.umap')==SOURCE_SHA
            and read(backup/'BuildReport.json')==previous and read(backup/'AfterSnapshot.json')==original_snapshot
            and read(backup/'PreservationBaseline.json')==read(SOURCE/'PreservationBaseline.json'),
            'Source map/report backup differs.')
    require(after.get('passed') is True and after.get('target_level')==TARGET
            and after.get('source_map_sha256')==digest and set(new)==set(old)
            and len(new)==len(old)==before['actor_count']==after['actor_count']==build['actor_count']==previous['actor_count']==8014,
            'Saved manifest added, removed or omitted an actor.')
    labels={n for n,s in old.items() for c in s.get('components',[]) if c.get('mesh')==asset['source']}
    require(len(labels)==30 and set(optimization.get('changed_actors',[]))==labels
            and len(optimization['changed_actors'])==30 and optimization.get('new_cameras')==[]
            and len(optimization.get('current_cameras',[]))==4 and set(optimization['current_cameras'])==CAMERAS
            and build.get('hotel_openings_review_cameras')==optimization['current_cameras'],
            'Only the thirty cistern instances and four existing review cameras may be declared.')
    for n,s in old.items():
        expected=deepcopy(s)
        if n in labels:
            components=[c for c in expected['components'] if c.get('mesh')==asset['source']]
            require(len(components)==1 and components[0].get('collision')=='<CollisionEnabled.NO_COLLISION: 0>',
                    'Targeted toilet root component differs: '+n)
            components[0]['mesh']=asset['asset']
        require(new[n]==expected,'Actor changed outside the approved mesh reference: '+n)
    expected_plan=deepcopy(previous['hotel_v4'])
    bounds=common.actual_bounds(geometry,labels)
    placed={r['id']:r['actor'] for r in expected_plan['placed_props'] if r.get('actor') in labels}
    for collection in ('placed_props','props'):
        require(len(plan[collection])==len(expected_plan[collection]),'Plan changed prop count.')
        for row,current in zip(expected_plan[collection],plan[collection]):
            n=row.get('actor') if collection=='placed_props' else placed.get(row['id'])
            if n in labels:
                row['asset']=asset['asset'];common.check_bounds(current,bounds[n],n)
                for k in common.BOUND_FIELDS & set(current):row[k]=deepcopy(current[k])
    expected_plan['asset_catalog']['Toilet']=asset['asset'].split('.')[0]
    expected_plan['expected_actor_states']={n:new[n] for n in expected_plan['new_actor_labels']}
    expected_plan['source_map_sha256']=SOURCE_SHA
    require(plan==expected_plan==build['hotel_v4']==build['hotel_architecture'],
            'Plan changed beyond the thirty mesh references and measured bounds.')
    expected_baseline=deepcopy(read(SOURCE/'PreservationBaseline.json'));expected_baseline['source_map_sha256']=SOURCE_SHA
    expected_baseline['protected_map_sha256']=current_protected
    baseline=read(WORK/'PreservationBaseline.json')
    require(baseline==expected_baseline and len(baseline['preserved_actors'])==5039
            and all(new[n]==s for n,s in baseline['preserved_actors'].items()),'Non-hotel preservation differs.')
    require(before['main_home']==after['main_home']==baseline['main_home']
            and after['main_home'].get('interaction_preserved') is True,'MainHome interaction changed.')
    colliders=[c['actor'] for r in previous['hotel_v4']['placed_props'] if r.get('asset_key') in ('Toilet','Washbasin') for c in r['colliders']]
    require(len(colliders)==len(set(colliders))==60 and set(optimization['preserved_fixture_collision_actors'])==set(colliders)
            and len(optimization['preserved_fixture_collision_actors'])==60
            and all(new[n]==old[n] for n in colliders),'An independent fixture collider changed.')
    require(saved['statistics'].get('unchanged_existing_actors')==7984
            and saved['statistics'].get('toilets')==saved['statistics'].get('basins')==30
            and architecture['statistics'].get('actors')==8014,'Fresh saved counts disagree.')
    shared=hashes(before['shared_asset_sha256'],'All starting referenced mesh assets')
    require(shared==400,'The 400 source references are incomplete.')
    expected_refs=deepcopy(before['shared_asset_sha256'])
    require(expected_refs.get(asset['source_file'])==asset['source_sha256'],'Source mesh file was not initially referenced.')
    del expected_refs[asset['source_file']];expected_refs[asset['file']]=asset['sha256']
    require(after['shared_asset_sha256']==expected_refs,'Referenced mesh files changed beyond one replacement.')
    hashes(after['shared_asset_sha256'],'Current referenced mesh assets')
    require(before['protected_map_sha256']==after['protected_map_sha256']==build['protected_map_sha256']==baseline['protected_map_sha256'],
            'Protected map manifests changed.')
    require(hashes(before['protected_map_sha256'],'Protected maps')==3,'Protected map set is incomplete.')
    return dict(passed=True,input_map_sha256=SOURCE_SHA,current_map_sha256=digest,input_actors=8014,current_actors=8014,
                render_mesh_references_replaced=30,all_other_existing_actor_states_preserved=7984,
                fixture_actor_transforms_preserved=60,independent_fixture_collision_actors_preserved=60,
                starting_referenced_mesh_assets_unchanged=400,nonhotel_actors_preserved=5039,protected_maps_unchanged=3,
                MainHome_interaction_structure_preserved=True,approved_layout_and_routes_preserved=True)

def geometry_audit(digest,optimization):
    path=WORK/'FinishGeometryAudit.json';d=read(path);checks=d.get('checks',[])
    require(d.get('passed') is True and not d.get('errors') and d.get('map_sha256')==digest
            and d.get('source_map_sha256')==SOURCE_SHA and checks
            and all(c.get('passed') is True for c in checks)
            and len(checks)==len({c.get('name') for c in checks})==d.get('statistics',{}).get('checks'),
            'Independent actual geometry proof failed or is stale.')
    inputs=[WORK/(n+'.json') for n in ('GeometryAfter','AfterSnapshot','BuildReport')]+[SOURCE/(n+'.json') for n in ('GeometryAfter','AfterSnapshot')]
    require(d.get('input_sha256')=={str(p):sha(p) for p in inputs}
            and d.get('normals_input_sha256')=={str(WORK/'FinishRenderNormals.json'):sha(WORK/'FinishRenderNormals.json')},
            'Actual geometry proof used different saved inputs.')
    rebase_inputs=[WORK/'InputSnapshot.json',WORK/'ProtectedMapInputRebase.json']
    require(d.get('rebase_input_sha256')=={str(p):sha(p) for p in rebase_inputs},
            'Actual geometry proof used different input protected-map update evidence.')
    require(d['statistics'].get('toilets')==d['statistics'].get('basins')==30
            and d['statistics'].get('unchanged_other_original_actors')==7984
            and d['statistics'].get('unchanged_fixture_colliders')==60,'Independent geometry instance coverage differs.')
    names={c['name'] for c in checks}
    for label in optimization['changed_actors']:
        required={'all_retained_source_faces_match_one_to_one','no_unprescribed_added_or_removed_faces',
                  'entire_original_fixture_envelope_preserved','materials_collision_and_wpo_preserved',
                  'independent_fixture_collider_unchanged','source_bowl_seat_feet_and_shoulder_preserved'}
        for p in recipe.build_pieces():
            required|={p['name']+'_all_prescribed_faces_present',p['name']+'_actual_closed_oriented_solid',
                       p['name']+'_actual_bounds_match_prescribed_envelope',
                       p['name']+'_all_four_old_sharp_corners_are_actually_clipped',
                       p['name']+'_centre_and_side_panels_remain_solid'}
        for witness in recipe.CONNECTION_WITNESSES:required.add('solid_connection_'+witness['name'])
        required|={'actual_flat_side_planes_have_055_cm_vertical_separation',
                   'all_new_cistern_geometry_stays_43_cm_above_preserved_cup',
                   'exactly_five_prescribed_new_connection_witnesses',
                   'body_and_lid_keep_approved_heights_and_embedded_joint',
                   'all_108_original_metal_flush_lever_faces_preserved'}
        required|={'preserved_cavity_remains_empty_'+str(i) for i in range(8)}
        required|={'preserved_cavity_floor_and_bottom_shell_ray_'+str(i) for i in range(4)}
        require({label+':'+n for n in required}<=names,'Missing complete actual toilet checks: '+label)
    basins=[r['actor'] for r in read(SOURCE/'BuildReport.json')['hotel_v4']['placed_props'] if r.get('asset_key')=='Washbasin']
    require(all(label+':all_original_basin_faces_and_state_preserved' in names for label in basins),
            'The thirty unchanged basins lack actual face preservation evidence.')
    return dict(passed=True,toilets=30,basins=30,geometry_checks=len(checks),audit_file=str(path),audit_sha256=sha(path))

def historical_reviews():
    previous=read(SOURCE/'FinalReview.json');views=previous.get('current_captures',[])
    require(previous.get('passed') is True and previous.get('map_sha256')==SOURCE_SHA and len(views)==4,
            'The prior shape review is absent or stale.')
    require(all(sha(v['png'])==v['png_sha256'] for v in views),'A historical shape image changed.')
    pointers=dict(historical_shape_views=dict(status='historical',map_sha256=SOURCE_SHA,bundle=str(SOURCE),review=str(SOURCE/'FinalReview.json'),view_count=4,cameras=[v['camera'] for v in views]))
    for key,count in [('historical_fixture_views',4),('historical_basin_views',3),('historical_hotel_views',21)]:
        pointer=previous.get(key,{})
        require(pointer.get('status')=='historical' and pointer.get('view_count')==count,'Inherited historical pointer differs: '+key)
        old=read(pointer['review']);vv=old.get('current_captures',[])
        require(old.get('passed') is True and old.get('map_sha256')==pointer.get('map_sha256')
                and len(vv)==len({v['camera'] for v in vv})==count
                and all(sha(v['png'])==v['png_sha256'] for v in vv),'Inherited history changed: '+key)
        pointers[key]=deepcopy(pointer)
    return pointers

def validate():
    common.canonical_source()
    build,previous=read(WORK/'BuildReport.json'),read(SOURCE/'BuildReport.json')
    mapfile=ROOT/('Content/'+TARGET.removeprefix('/Game/')+'.umap');digest=sha(mapfile)
    require(build.get('status')=='PASS' and build.get('target_level')==TARGET and build.get('map_sha256')==digest
            and build.get('source_map_sha256')==SOURCE_SHA and digest!=SOURCE_SHA,'Saved current map differs.')
    optimization=build['sanitary_finish_refinement']
    require(read(WORK/'FinishOptimizationReport.json')==optimization and optimization.get('passed') is True
            and optimization.get('map_sha256')==digest and optimization.get('source_map_sha256')==SOURCE_SHA,'Finish report differs.')
    applied=read(WORK/'Applied.json')
    require(applied.get('passed') is True and applied.get('map_sha256')==digest and applied.get('source_map_sha256')==SOURCE_SHA
            and applied.get('changed_actors')==applied.get('toilets')==30 and applied.get('new_cameras')==0
            and applied.get('actor_count')==8014,'Applied marker differs.')
    allowed={'status','source_map_sha256','map_sha256','hotel_v4','hotel_architecture','previous_evidence','new_asset_sha256','sanitary_finish_refinement','protected_map_sha256'}
    require(set(build)==set(previous)|{'sanitary_finish_refinement'}
            and all(build[k]==v for k,v in previous.items() if k not in allowed),'Build changed unrelated fields.')
    asset,frozen,normals=verify_asset(optimization)
    old_assets,new_assets=previous['new_asset_sha256'],build['new_asset_sha256']
    require(set(new_assets)==set(old_assets)|{asset['file']} and all(new_assets[p]==h for p,h in old_assets.items())
            and new_assets[asset['file']]==asset['sha256'],'Generated asset manifest changed beyond one clone.')
    hashes(new_assets,'Generated assets')
    common.hotel.WORK=WORK
    architecture=common.hotel.current_audit('ArchitectureAudit.json',digest)
    detail=common.hotel.current_audit('DetailAudit.json',digest)
    saved=common.hotel.current_audit('FinishSavedAudit.json',digest)
    before,after=read(WORK/'InputSnapshot.json'),read(WORK/'AfterSnapshot.json')
    plan=read(WORK/'ArchitecturePlan.json');gf=WORK/'GeometryAfter.json';gh=sha(gf);geometry=read(gf);summary=read(WORK/'AfterSummary.json')
    require(geometry.get('map_sha256')==summary.get('map_sha256')==digest and not geometry.get('errors')
            and summary.get('passed') is True and not summary.get('errors')
            and summary.get('actors')==8014 and summary.get('visible_components')==len(geometry['components'])
            and summary.get('triangles')==geometry['triangles'] and summary.get('unique_meshes')==geometry['unique_meshes'],
            'Fresh full-map geometry/summary differs.')
    require(all(not any(abs(v)>1.e-8 for v in c.get('render_offset_cm',[0,0,0]))
            or c.get('wpo_verified_from_persisted_material') is True for c in geometry['components']),'Material WPO was not verified.')
    preserved=preservation(build,previous,before,after,plan,optimization,asset,geometry,architecture,saved)
    actual=geometry_audit(digest,optimization)
    common.surfaces.WORK=WORK;scans=common.surfaces.verify_scans(digest,geometry,gh,read(WORK/'SavedScanSummary.json'))
    capture_build=deepcopy(build);capture_build['sanitary_shape_refinement']=optimization
    captures=common.capture_review(capture_build,mapfile)
    visual=read(WORK/'VisualReview.json');current={v['camera']:v for v in captures['views']}
    require(visual.get('passed') is True and not visual.get('errors') and visual.get('map_sha256')==digest
            and visual.get('target_level')==TARGET and len(visual.get('views',[]))==4
            and {v['camera'] for v in visual['views']}==CAMERAS
            and all(v.get('passed') is True and v.get('png_sha256')==current[v['camera']]['png_sha256'] for v in visual['views']),
            'Actual visual review lacks four current image identities.')
    history=historical_reviews();at=datetime.now(timezone.utc).isoformat();captures['reviewed_utc']=at
    names=['BuildReport.json','Applied.json','FinishOptimizationReport.json','ArchitecturePlan.json','ArchitectureAudit.json',
           'DetailAudit.json','FinishSavedAudit.json','FinishGeometryAudit.json','FinishRenderNormals.json','InputSnapshot.json',
           'AfterSnapshot.json','PreservationBaseline.json','GeometryAfter.json','AfterSummary.json','SavedScan.json',
           'SavedScanOcclusion.json','SavedScanSummary.json','VisualReview.json','ProtectedMapInputRebase.json']
    audit=dict(passed=True,status='PASS',target_level=TARGET,map_sha256=digest,source_map_sha256=SOURCE_SHA,
               source='fresh_persisted_map_load',persisted_map_unchanged=True,preservation=preserved,sanitary_finish=actual,
               frozen_source_art_recipe=frozen,actual_render_normals=normals,surface_scans=scans,
               current_evidence_file_sha256={n:sha(WORK/n) for n in names},current_capture_file_sha256=captures['current_capture_file_sha256'],reviewed_utc=at)
    final=dict(passed=True,status='PASS',target_level=TARGET,map_sha256=digest,source_map_sha256=SOURCE_SHA,actor_count=8014,
               current_bundle=str(WORK),change='Only thirty ceramic cisterns and lids receive rounded edges and a distinct embedded lid joint.',
               sanitary_finish=actual,preservation=preserved,frozen_source_art_recipe=frozen,actual_render_normals=normals,
               fresh_architecture_validation=architecture['statistics'],fresh_detail_validation=detail['statistics'],surface_scans=scans,
               current_render_source=str(gf),current_render_source_sha256=gh,current_captures=captures['views'],current_helpers=captures['current_helpers'],
               capture_directory=captures['capture_directory'],current_renders=captures['current_renders'],**history,
               limitations=['The previous toilet seat and base geometry and original ceramic materials remain greybox detail.',
                   'Four current closeups use temporary inspection lighting; these lights were cleaned and never saved.',
                   'Full-map surface scan covers same-facing overlaps of at least 1cm2 within 0.03cm plane tolerance.'],reviewed_utc=at)
    require(sha(mapfile)==digest and sha(gf)==gh,'Map/geometry changed during review.')
    return dict(build=build,mapfile=mapfile,digest=digest,geometry_file=gf,geometry_hash=gh,audit=audit,captures=captures,final=final)

def publish(result):
    require(sha(result['mapfile'])==result['digest'] and sha(result['geometry_file'])==result['geometry_hash'],'Map/geometry changed before publication.')
    hashes(result['build']['new_asset_sha256'],'Generated assets');hashes(result['build']['protected_map_sha256'],'Protected maps')
    hashes({str(WORK/n):h for n,h in result['audit']['current_evidence_file_sha256'].items()},'Current reports')
    hashes(result['audit']['current_capture_file_sha256'],'Current capture proof')
    frozen=result['audit']['frozen_source_art_recipe'];require(sha(frozen['source_art_recipe'])==frozen['source_art_recipe_sha256'],'Recipe changed before publication.')
    previous=common.canonical_source();backup=WORK/'BeforeCanonicalPublish';backup.mkdir(parents=True,exist_ok=True)
    names=['BuildReport.json','Applied.json','FinishOptimizationReport.json','ArchitecturePlan.json','ArchitectureAudit.json','DetailAudit.json',
           'FinishSavedAudit.json','FinishGeometryAudit.json','FinishRenderNormals.json','AfterSummary.json','SavedScan.json','SavedScanOcclusion.json',
           'SavedScanSummary.json','VisualReview.json','ProtectedMapInputRebase.json','FinishFinalAudit.json','CaptureReview.json','FinalReview.json']
    for n in sorted(set(names+['CurrentEvidence.json'])|set(previous['current_reports'])):
        require(Path(n).name==n and n.endswith('.json'),'Unsafe report filename.')
        if (CANON/n).is_file() and not (backup/n).exists():shutil.copy2(CANON/n,backup/n)
    write(backup/'BackupManifest.json',dict(historical_only=True,current_publication_map_sha256=result['digest'],backed_up_report_sha256={p.name:sha(p) for p in backup.glob('*.json') if p.name!='BackupManifest.json'}))
    for n,data in [('FinishFinalAudit.json',result['audit']),('CaptureReview.json',result['captures']),('FinalReview.json',result['final'])]:write(WORK/n,data)
    expected={n:sha(WORK/n) for n in names}
    for n in names:
        temporary=CANON/(n+'.tmp');shutil.copy2(WORK/n,temporary);temporary.replace(CANON/n)
        require(sha(CANON/n)==expected[n],'Published report differs: '+n)
    capture=result['captures'];history={k:v for k,v in result['final'].items() if k.startswith('historical_')}
    pointer=dict(target_level=TARGET,map_sha256=result['digest'],source_bundle=str(WORK),source_directory=str(WORK),
                 current_reports=names,current_report_sha256=expected,current_renders=capture['current_renders'],
                 current_capture_directory=capture['capture_directory'],current_capture_runs_file=capture['current_capture_runs_file'],
                 current_capture_runs_sha256=capture['current_capture_runs_sha256'],current_render_cameras=[v['camera'] for v in capture['views']],
                 current_render_lighting_modes={v['camera']:v['lighting_mode'] for v in capture['views']},
                 current_render_geometry=str(result['geometry_file']),current_render_geometry_sha256=result['geometry_hash'],
                 current_actor_snapshot=str(WORK/'AfterSnapshot.json'),current_actor_snapshot_sha256=sha(WORK/'AfterSnapshot.json'),
                 current_architecture_plan=str(WORK/'ArchitecturePlan.json'),current_architecture_plan_sha256=sha(WORK/'ArchitecturePlan.json'),
                 previous_bundle=str(SOURCE),previous_evidence_status='historical',historical_report_backup=str(backup),**history,
                 historical_reports_not_current=sorted(set(previous['current_reports'])-set(names)),
                 opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',published_utc=result['final']['reviewed_utc'])
    write(CANON/'CurrentEvidence.json',pointer)
    require(sha(result['mapfile'])==result['digest'],'Publication unexpectedly changed the map.')
    return expected

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    result=validate();published={} if args.check_only else publish(result)
    print(common.json.dumps(dict(passed=True,check_only=args.check_only,map_sha256=result['digest'],actors=8014,
           changed_toilets=30,current_captures=4,exposed_coplanar_groups=0,published_reports=len(published)),ensure_ascii=False))

if __name__=='__main__':main()
