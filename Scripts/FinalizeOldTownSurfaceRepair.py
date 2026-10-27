"""Publish only fresh saved-map evidence for the whole-map surface repair.

Historical V4 Blender geometry remains a structural reference. It is not the
source of the current render offsets, frame profiles or independent mesh clones.
The current source of truth is the saved map, its verified assets and a fresh
export of the actual rendered triangles (including persisted material WPO).
"""
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
CANON=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
sys.path.insert(0,str(ROOT/'Scripts'))
import FinalizeOldTownHotelV4 as hotel_captures
hotel_captures.WORK=WORK
hotel_captures.lifecycle.WORK=WORK


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition,message):
    if not condition:raise RuntimeError(message)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_name(path.name+'.tmp')
    pending.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    pending.replace(path)


def _hashes(values,label):
    require(bool(values),label+' hash manifest is empty.')
    for name,digest in values.items():
        path=Path(name)
        require(path.is_file() and sha(path)==digest,label+' file changed: '+name)
    return len(values)


def _close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-9,abs_tol=1e-6)


def _row_identity(row):
    # Visibility classification may change, but no raw face pairs, planes,
    # bounds or measured overlap areas may be discarded by the occlusion pass.
    fields=('components','component_metadata','intra_component','normal','plane_cm',
        'projection_axis','area_cm2','face_pair_count','max_plane_gap_cm',
        'face_pair_samples','face_indices_by_component','overlap_bounds_cm')
    require(all(k in row for k in fields),'Incomplete raw overlap identity.')
    return json.dumps({k:row[k] for k in fields},sort_keys=True,separators=(',',':'))


def verify_scans(digest,geometry,geometry_hash,summary):
    raw=read(WORK/'SavedScan.json');occluded=read(WORK/'SavedScanOcclusion.json')
    counts={}
    for name,scan in [('SavedScan.json',raw),('SavedScanOcclusion.json',occluded)]:
        scope=scan.get('scope',{})
        require(scan.get('source_map_sha256')==digest,name+' belongs to another saved map.')
        require(scan.get('source_geometry_sha256')==geometry_hash,name+' belongs to another triangle export.')
        require(Path(scan['source_geometry_path']).resolve()==(WORK/'GeometryAfter.json').resolve(),name+' references another geometry export.')
        require(scope.get('include_internal') is True and scope.get('axis_only') is False,
            name+' must scan internal and arbitrary-normal surfaces.')
        require(scope.get('component_count')==len(geometry['components']),name+' does not cover the full visible map.')
        require(_close(scope.get('plane_tolerance_cm',0),.03) and _close(scope.get('minimum_overlap_area_cm2',0),1.),
            name+' has an unexpected scanning tolerance or minimum area.')
        require(scan.get('overlap_count')==len(scan.get('overlaps',[])),name+' overlap count differs from its evidence.')
        require(not scan.get('exact_duplicate_boxes'),name+' retains exact duplicate visible boxes.')
        require(scan.get('completed_utc'),name+' has no completion record.')
        counts[name]=dict(groups=len(scan['overlaps']),
            exposed_groups=sum(not r.get('buried',False) for r in scan['overlaps']))
    require(raw['scope']['normal_tolerance']==occluded['scope']['normal_tolerance'],
        'Normal tolerances differ between raw and occlusion scans.')
    raw_rows={_row_identity(r):r for r in raw['overlaps']}
    occlusion_rows={_row_identity(r):r for r in occluded['overlaps']}
    require(len(raw_rows)==len(raw['overlaps']) and len(occlusion_rows)==len(occluded['overlaps']),
        'Duplicate overlap identities prevent a complete comparison.')
    require(set(raw_rows)==set(occlusion_rows),'Occlusion classification discarded or changed raw overlap identities.')
    require(not any(not r.get('buried',False) and not r['intra_component'] for r in raw['overlaps']),
        'Raw full-map scan still has exposed inter-component coplanar surfaces.')
    component_ids={r['id'] for r in geometry['components']}
    recomputed=[]
    for identity,before in raw_rows.items():
        after=occlusion_rows[identity]
        require(all(c in component_ids for c in after['components']),'Overlap refers to a component outside the exported saved map.')
        require(after.get('buried') is True and _close(after.get('exposed_area_cm2',-1),0.),
            'Occlusion scan still has a visible coplanar overlap: '+str(after['components']))
        require(_close(after['buried_area_cm2'],after['area_cm2']),
            'A retained buried group has unclassified overlap area.')
        changed=(before.get('buried')!=after.get('buried') or
            not _close(before.get('exposed_area_cm2',0),after.get('exposed_area_cm2',0)) or
            not _close(before.get('buried_area_cm2',0),after.get('buried_area_cm2',0)))
        if not changed:continue
        require(before['intra_component'] is True and after['components'][0]==after['components'][1],
            'Internal occlusion changed an inter-component group.')
        proof=after.get('self_occlusion',{})
        require(proof.get('complete_group_recomputed') is True and proof.get('closed_mesh') is True
            and proof.get('odd_boundary_edges')==0,'Internal buried classification lacks a complete closed-mesh proof.')
        require(proof.get('tested_face_pairs')==proof.get('expected_face_pairs')==after['face_pair_count'],
            'Internal occlusion tested only a sample of the overlap group.')
        require(_close(proof.get('recomputed_area_cm2',-1),after['area_cm2'])
            and _close(proof.get('internal_buried_area_cm2',-1),after['area_cm2']),
            'Internal occlusion did not account for every overlapping face area.')
        method=str(proof.get('method','')).lower()
        require('signed ray' in method and 'centre' in method and 'vertex' in method,
            'Internal occlusion lacks signed-ray centre/vertex evidence.')
        recomputed.append(dict(components=after['components'],face_pair_count=after['face_pair_count'],
            area_cm2=after['area_cm2'],method=proof['method']))
    provenance=summary.get('provenance',{})
    require(provenance.get('source_map_sha256')==digest and provenance.get('source_geometry_sha256')==geometry_hash,
        'SavedScanSummary is stale.')
    require(Path(provenance['source_geometry_path']).resolve()==(WORK/'GeometryAfter.json').resolve(),
        'SavedScanSummary points at another geometry export.')
    actual_counts=dict(groups=len(occluded['overlaps']),exposed_groups=0,
        fully_buried_groups=len(occluded['overlaps']),inter_exposed=0,intra_exposed=0)
    require(all(summary.get('counts',{}).get(k)==v for k,v in actual_counts.items()),
        'SavedScanSummary counts do not match the complete final scan.')
    require(not summary.get('exposed_candidates'),'SavedScanSummary still contains exposed candidates.')
    require(summary.get('scope',{}).get('include_internal') is True
        and summary.get('scope',{}).get('axis_only') is False,'SavedScanSummary omitted non-axis/internal faces.')
    return dict(passed=True,map_sha256=digest,geometry_sha256=geometry_hash,
        scanned_visible_components=len(geometry['components']),scanned_render_triangles=geometry['triangles'],
        arbitrary_normal_surfaces=True,internal_surfaces=True,plane_tolerance_cm=.03,
        minimum_overlap_area_cm2=1.,raw_counts=counts['SavedScan.json'],final_counts=actual_counts,
        retained_buried_groups=len(occluded['overlaps']),completely_recomputed_internal_buried_groups=len(recomputed),
        internal_occlusion_proofs=recomputed,
        scope='Same-facing coplanar overlap of at least 1cm2 within 0.03cm plane tolerance; buried interior groups retained with evidence.')


def verify_preservation(build,plan,architecture,input_snapshot,after_snapshot,baseline,repair):
    digest=build['map_sha256'];before=input_snapshot['actors'];after=after_snapshot['actors']
    require(input_snapshot.get('passed') is True and input_snapshot['source_map_sha256']==build['source_map_sha256'],
        'Input snapshot does not match the user-saved starting map.')
    require(baseline.get('source_map_sha256')==build['source_map_sha256']
        and repair.get('source_map_sha256')==build['source_map_sha256'],
        'Preservation or repair baseline belongs to another starting map.')
    require(after_snapshot.get('passed') is True and after_snapshot['source_map_sha256']==digest,
        'AfterSnapshot is not the current fresh saved map.')
    require(input_snapshot['target_level']==after_snapshot['target_level']==TARGET,'Snapshot level differs.')
    require(set(before)<=set(after),'The surface repair deleted an original actor.')
    added=set(after)-set(before);created=set(repair.get('created_cameras',[]))
    require(added==created and len(added)==3,'Unexpected actor additions outside the three inspection cameras.')
    require(build['actor_count']==len(after)==after_snapshot['actor_count']==input_snapshot['actor_count']+len(added),
        'Actor count differs from the preserved user map and inspection cameras.')
    require(not baseline.get('removed_actor_labels') and architecture['preservation']['removed_actors']==0,
        'Surface repair must not remove any actors.')
    expected=dict(baseline['preserved_actors']);expected.update(baseline.get('allowed_surface_overrides',{}));expected.update(plan['expected_actor_states'])
    require(set(expected)==set(after),'The complete saved-actor manifest is missing actors.')
    mismatched=[n for n,s in expected.items() if after[n]!=s]
    require(not mismatched,'Fresh saved actor states differ from approved visual changes: '+str(mismatched[:12]))
    users=['BP_ItemPickup','PointLight']
    require(set(repair.get('user_added_actors_preserved',[]))==set(users),'The user-added actor record is incomplete.')
    require(all(n in before and after.get(n)==before[n] for n in users),'A user-added actor changed or disappeared.')
    require(after_snapshot.get('main_home')==input_snapshot.get('main_home')==baseline.get('main_home')
        and after_snapshot['main_home'].get('interaction_preserved') is True,
        'MainHome interaction structure is not preserved.')
    checks={r['name']:r for r in architecture['checks']}
    required=('exact_current_actor_set','all_new_actor_saved_states_match','shared_assets_unchanged',
        'protected_maps_unchanged','MainHome_interaction_structure_preserved','temporary_inspection_objects_absent')
    require(all(checks.get(k,{}).get('passed') is True for k in required),'Required fresh physical/preservation checks are missing.')
    for name in ('all_nonhotel_actors_match_approved_surface_overrides','all_nonhotel_actors_unchanged'):
        if name in checks:require(checks[name]['passed'] is True,'Non-hotel actor preservation failed.');break
    else:raise RuntimeError('Non-hotel saved-state preservation was not checked.')
    shared=_hashes(input_snapshot['shared_asset_sha256'],'Original shared assets')
    require(baseline['shared_asset_sha256']==input_snapshot['shared_asset_sha256'],'Original shared-asset baseline changed.')
    # This snapshot lists currently referenced meshes, including independent
    # clones. Replaced originals may disappear from it while remaining intact
    # on disk; the original baseline above is checked separately in full.
    referenced=_hashes(after_snapshot['shared_asset_sha256'],'Current referenced mesh assets')
    before_refs=input_snapshot['shared_asset_sha256'];after_refs=after_snapshot['shared_asset_sha256']
    require(all(after_refs[p]==before_refs[p] for p in set(before_refs)&set(after_refs)),
        'An original asset retained by the saved map changed its SHA.')
    generated=(ROOT/'Content/CodexGenerated').resolve()
    require(all(Path(p).resolve().is_relative_to(generated) for p in set(after_refs)-set(before_refs)),
        'A newly referenced visual asset is outside CodexGenerated.')
    protected=_hashes(input_snapshot['protected_map_sha256'],'Protected maps')
    require(build['protected_map_sha256']==baseline['protected_map_sha256']==input_snapshot['protected_map_sha256'],
        'Protected-map baselines differ.')
    require(after_snapshot.get('protected_map_sha256')==input_snapshot['protected_map_sha256'],
        'Fresh saved-map protected assets differ from the original baseline.')
    require(len(plan['rooms'])==architecture['statistics']['rooms']==27 and len(plan['floor_z_cm'])==4,
        'The approved four-storey, 27-room hotel layout changed.')
    return dict(passed=True,input_map_sha256=build['source_map_sha256'],current_map_sha256=digest,
        input_actors=len(before),current_actors=len(after),deleted_original_actors=0,
        added_inspection_cameras=sorted(added),user_added_actors_preserved=users,
        shared_assets_unchanged=shared,current_referenced_mesh_assets=referenced,
        protected_maps_unchanged=protected,MainHome_interaction_structure_preserved=True,
        approved_rooms=27,approved_storeys=4,exact_saved_actor_manifest_verified=True)


def main():
    build=read(WORK/'BuildReport.json');require(build.get('status')=='PASS' and build['target_level']==TARGET,'Current build is not PASS for the requested street.')
    mapfile=ROOT/('Content/'+TARGET[6:]+'.umap');digest=sha(mapfile)
    require(build['map_sha256']==digest,'Saved map changed after the current surface repair.')
    applied=read(WORK/'Applied.json');require(applied.get('passed') is True and applied['map_sha256']==digest,'Applied marker is stale.')
    marker=Path(applied.get('refinement',str(WORK/'Refined.json'))).resolve()
    require(marker.is_relative_to(WORK.resolve()) and marker.is_file(),'Current refinement marker is missing or outside this bundle.')
    refined=read(marker);require(refined.get('passed') is True and refined.get('map_sha256')==digest,'Latest refinement marker is stale.')
    repair=read(WORK/'RepairReport.json');require(repair.get('passed') is True and repair==build['surface_repair'],'Repair report differs from the saved build.')
    require(repair.get('refinement')==refined,'Build does not reference the latest frame refinement.')
    architecture=read(WORK/'ArchitectureAudit.json')
    require(architecture.get('passed') is True and not architecture.get('errors') and architecture['map_sha256']==digest,
        'Current architecture/collision audit failed or is stale.')
    require(architecture.get('target_level')==TARGET and architecture.get('checks')
        and all(r.get('passed') is True for r in architecture['checks']),
        'Fresh architecture audit contains a failed or missing check.')
    require(architecture.get('source')=='fresh_persisted_map_load' and architecture.get('persisted_map_unchanged') is True,
        'Architecture audit did not inspect a fresh unchanged saved map.')
    plan=read(WORK/'ArchitecturePlan.json');require(plan==build['hotel_v4']==build['hotel_architecture'],'Current render/architecture plan differs from the saved build.')
    input_snapshot=read(WORK/'InputSnapshot.json');after_snapshot=read(WORK/'AfterSnapshot.json');baseline=read(WORK/'PreservationBaseline.json')
    preservation=verify_preservation(build,plan,architecture,input_snapshot,after_snapshot,baseline,repair)
    rebase=read(WORK/'InputRebaseReport.json')
    require(rebase.get('passed') is True and rebase.get('current_input_map_sha256')==build['source_map_sha256']
        and rebase.get('no_original_actors_removed') is True and set(rebase.get('user_added_actors_preserved',[]))=={'BP_ItemPickup','PointLight'},
        'User-saved map changes are not covered by the input rebase report.')
    new_assets=_hashes(build['new_asset_sha256'],'Generated assets')
    generated=(ROOT/'Content/CodexGenerated').resolve()
    require(all(Path(p).resolve().is_relative_to(generated) for p in build['new_asset_sha256']),
        'Generated assets were published outside CodexGenerated.')
    material=read(WORK/'MaterialRepair.json');require(material.get('passed') is True and not material.get('changed_original_files'),'Original material preservation failed.')
    _hashes(material['original_asset_sha256'],'Original material assets')
    geometry_file=WORK/'GeometryAfter.json';geometry_hash=sha(geometry_file);geometry=read(geometry_file)
    after_summary=read(WORK/'AfterSummary.json')
    require(after_summary.get('passed') is True and not after_summary.get('errors') and after_summary['map_sha256']==digest,
        'AfterSummary is not a successful current export.')
    require(geometry['map_sha256']==digest and not geometry.get('errors'),'Actual saved render geometry is stale or incomplete.')
    require(after_summary['actors']==build['actor_count'] and after_summary['visible_components']==len(geometry['components'])
        and after_summary['triangles']==geometry['triangles'] and after_summary['unique_meshes']==geometry['unique_meshes'],
        'AfterSummary counts differ from the actual saved render geometry.')
    require(all(not any(abs(float(v))>1e-8 for v in c.get('render_offset_cm',[0,0,0]))
        or c.get('wpo_verified_from_persisted_material') is True for c in geometry['components']),
        'A render offset was inferred instead of read from the persisted material.')
    scan_summary=read(WORK/'SavedScanSummary.json');scans=verify_scans(digest,geometry,geometry_hash,scan_summary)
    cameras=[r['camera'] for r in plan['review_cameras']]
    require(len(cameras)==len(set(cameras))==15 and cameras==build['hotel_openings_review_cameras'],
        'Exactly 15 current hotel/street/detail inspection cameras are required.')
    require({'CAM_Surface_WindowInside','CAM_Surface_WindowOutside','CAM_Surface_RoomNumber','CAM_Openings_Window',
        'CAM_OTS_MainHome','CAM_OTS_StreetDiagonal'}<=set(cameras),'Whole-map and opening detail inspection views are missing.')
    captures=hotel_captures.capture_review(build,mapfile)
    require(len(captures['views'])==15 and {r['camera'] for r in captures['views']}==set(cameras),'Current captures do not cover every camera.')
    visual=read(WORK/'VisualReview.json')
    require(visual.get('passed') is True and visual.get('map_sha256')==digest,'Visual review is missing or belongs to another map.')
    require(not visual.get('errors'),'Visual review recorded unresolved problems.')
    visual_views=visual.get('views',[])
    require(len(visual_views)==15 and len({v.get('camera') for v in visual_views})==15
        and {v.get('camera') for v in visual_views}==set(cameras),
        'Visual review must cover all 15 distinct current captures.')
    capture_by_camera={v['camera']:v for v in captures['views']}
    require(all(v.get('passed') is True and v.get('png_sha256')==capture_by_camera[v['camera']]['png_sha256']
        for v in visual_views),'Visual review does not match the approved current PNG hashes.')
    # Recheck immutable inputs immediately before writing/publishing evidence.
    require(sha(mapfile)==digest and sha(geometry_file)==geometry_hash,'Map or geometry changed during publication checks.')
    _hashes(build['new_asset_sha256'],'Generated assets');_hashes(input_snapshot['shared_asset_sha256'],'Original shared assets');_hashes(build['protected_map_sha256'],'Protected maps')
    audited=datetime.now(timezone.utc).isoformat()
    files=['BuildReport.json','Applied.json',marker.name,'ArchitectureAudit.json','ArchitecturePlan.json',
        'RepairReport.json','InputRebaseReport.json','InputSnapshot.json','AfterSnapshot.json','AfterSummary.json',
        'PreservationBaseline.json','MaterialRepair.json','GeometryAfter.json','SavedScan.json',
        'SavedScanOcclusion.json','SavedScanSummary.json','VisualReview.json']
    surface=dict(passed=True,status='PASS',target_level=TARGET,map_sha256=digest,reviewed_utc=audited,
        source='fresh_persisted_map_load',persisted_map_unchanged=True,preservation=preservation,
        scans=scans,generated_asset_count=new_assets,changed_actor_count=repair['changed_actor_count'],
        shifted_render_components=repair['shifted_components'],maximum_world_translation_cm=repair['maximum_world_translation_cm'],
        current_refinement_marker=str(marker),current_refinement_sha256=sha(marker),
        current_evidence_file_sha256={n:sha(WORK/n) for n in files},
        render_source='Persisted UE map, independent generated assets and GeometryAfter actual rendered triangles.',
        historical_blender_source_role='V4 Blender source is structural reference only; it does not contain the current render offsets, frame profiles or cloned face repairs.')
    write(WORK/'SurfaceRepairAudit.json',surface);write(WORK/'CaptureReview.json',captures)
    final=dict(passed=True,status='PASS',target_level=TARGET,map_sha256=digest,actor_count=build['actor_count'],
        rooms=27,storeys=4,validation=architecture['statistics'],preservation=preservation,surface_scans=scans,
        current_bundle=str(WORK),current_render_source=str(geometry_file),current_render_source_sha256=geometry_hash,
        current_captures=captures['views'],current_refinement_marker=str(marker),
        original_shared_assets_unchanged=True,MainHome_interaction_structure_preserved=True,
        user_added_actors_preserved=['BP_ItemPickup','PointLight'],deleted_original_actors=0,
        historical_source_model_role=surface['historical_blender_source_role'],
        limitations=['Scanning covers same-facing coplanar overlaps of at least 1cm2 within 0.03cm plane tolerance; smaller fragments are outside this measured scope.',
            'Fully buried interior groups are retained and individually accounted for; the final scan has zero exposed groups.',
            'Physical saved-world architecture, doors and routes are verified; a working lift and runtime player-input implementation are outside this repair.'],reviewed_utc=audited)
    write(WORK/'FinalReview.json',final)
    names=list(dict.fromkeys(['BuildReport.json','Applied.json',marker.name,'ArchitectureAudit.json','SurfaceRepairAudit.json',
        'RepairReport.json','InputRebaseReport.json','AfterSummary.json','SavedScan.json','SavedScanOcclusion.json',
        'SavedScanSummary.json','CaptureReview.json','VisualReview.json','FinalReview.json']))
    previous=read(CANON/'CurrentEvidence.json') if (CANON/'CurrentEvidence.json').exists() else {}
    backup=WORK/'BeforeCanonicalPublish';backup.mkdir(parents=True,exist_ok=True);CANON.mkdir(parents=True,exist_ok=True)
    backup_names=set(names+['CurrentEvidence.json'])|set(previous.get('current_reports',[]))
    for name in sorted(backup_names):
        require(Path(name).name==name,'Unsafe report name in previous publication.')
        source=CANON/name;destination=backup/name
        if source.is_file() and not destination.exists():shutil.copy2(source,destination)
    write(backup/'BackupManifest.json',dict(backed_up_report_sha256={p.name:sha(p) for p in backup.glob('*.json') if p.name!='BackupManifest.json'},
        historical_only=True,current_publication_map_sha256=digest))
    expected={n:sha(WORK/n) for n in names}
    for name in names:
        pending=CANON/(name+'.tmp');shutil.copy2(WORK/name,pending);pending.replace(CANON/name)
        require(sha(CANON/name)==expected[name],'Published report hash differs: '+name)
    evidence=dict(target_level=TARGET,map_sha256=digest,source_bundle=str(WORK),source_directory=str(WORK),
        current_reports=names,current_report_sha256=expected,current_renders=str(WORK/'Renders'),
        current_render_cameras=cameras,current_render_lighting_modes={r['camera']:r['lighting_mode'] for r in captures['views']},
        current_render_geometry=str(geometry_file),current_render_geometry_sha256=geometry_hash,
        current_actor_snapshot=str(WORK/'AfterSnapshot.json'),current_actor_snapshot_sha256=sha(WORK/'AfterSnapshot.json'),
        current_refinement_marker=str(marker),current_refinement_sha256=sha(marker),
        previous_bundle=previous.get('source_bundle',previous.get('source_directory')),previous_evidence_status='historical',
        historical_reports_not_current=sorted(set(previous.get('current_reports',[]))-set(names)),
        opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',
        source_model_role='Historical V4 Blender source is structural reference; saved UE map and generated render assets are current.',
        note='Whole-map surface separation published only after a fresh full-normal/internal rendered-triangle scan, complete actor preservation, physical audit and 15 current captures.',
        published_utc=audited)
    write(CANON/'CurrentEvidence.json',evidence)
    require(sha(mapfile)==digest,'Publication unexpectedly changed the saved map.')
    print(json.dumps(dict(passed=True,map_sha256=digest,bundle=str(WORK),actors=build['actor_count'],
        captures=len(captures['views']),exposed_coplanar_groups=0,retained_buried_groups=scans['retained_buried_groups'],
        published_report_sha256=expected),ensure_ascii=False))


if __name__=='__main__':main()
