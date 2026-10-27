"""Verify and publish Stage3 evidence, without Unreal or asset/map writes.

The source Stage2 bundle is immutable. Only the explicitly authorized parallel
Main-map edit is excluded from protection. Publication copies verified reports
and atomically replaces CurrentEvidence.json last.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil

from VerifyOldTownSoftGoodsRefinement import (
    ART, CANON, GENERATED, MAP, SOURCE, WORK, bound, index, near, read,
    reference, require, sha, verify_stage,
)
from FinalizeOldTownRealismRefinement import captures

W = WORK
LAMP_CAMERAS = ['CAM_StreetAccess_Lamp', 'CAM_V4_TopGallery', 'CAM_StreetAccess_NightStreet']
CONTACT_LIMITS = dict(contact_distance_cm=.02, penetration_tolerance_cm=.002,
                      minimum_contact_vertices=10, minimum_contact_area_fraction=.20)
REPORTS = ['Baseline.json', 'ApprovedPlan.json', 'Applied.json', 'BuildReport.json',
           'ExpectedSnapshot.json', 'After.json', 'AfterSnapshot.json', 'AppearanceSnapshot.json',
           'PreservationAudit.json', 'GeometryPreservation.json', 'LightAudit.json', 'AfterSummary.json',
           'SourceAudit.json', 'SourceContactProof.json', 'SourceContactAudit.json', 'CoplanarScan.json',
           'InternalOcclusionScan.json', 'SurfaceScanSummary.json', 'CaptureSetup.json',
           'CaptureReview.json', 'VisualReview.json', 'RunCompletion.json', 'OverlapCorrection.json', 'FinalReview.json']


def write(path, value):
    """Atomic report write; callers pass only owned evidence destinations."""
    path = Path(path)
    require(path.parent.is_dir(), 'Evidence directory does not exist: ' + str(path.parent))
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def plus(a, b, weight):
    return tuple(x+weight*y for x, y in zip(a, b))


def closest_point(p, a, b, c):
    """Closest point on a real triangle, including its edges and vertices."""
    ab, ac, ap = sub(b, a), sub(c, a), sub(p, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0: return a
    bp = sub(p, b); d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0 and d4 <= d3: return b
    vc = d1*d4-d3*d2
    if vc <= 0 and d1 >= 0 and d3 <= 0: return plus(a, ab, d1/(d1-d3))
    cp = sub(p, c); d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6: return c
    vb = d5*d2-d1*d6
    if vb <= 0 and d2 >= 0 and d6 <= 0: return plus(a, ac, d2/(d2-d6))
    va = d3*d6-d5*d4
    if va <= 0 and d4-d3 >= 0 and d5-d6 >= 0:
        return plus(b, sub(c, b), (d4-d3)/((d4-d3)+(d5-d6)))
    denominator = va+vb+vc
    require(denominator != 0, 'Degenerate contact triangle.')
    v, w = vb/denominator, vc/denominator
    return tuple(a[i]+ab[i]*v+ac[i]*w for i in range(3))


def transform_points(recipe, component, offset, origin):
    pose = component['world_pose']; x, y, z, w = pose['rotation_quaternion_xyzw']
    require(abs(x*x+y*y+z*z+w*w-1) < 1e-6, 'Invalid original contact rotation.')
    out = []
    for p in recipe['vertices_cm']:
        a, b, c = [p[i]*pose['scale'][i] for i in range(3)]
        tx, ty, tz = 2*(y*c-z*b), 2*(z*a-x*c), 2*(x*b-y*a)
        rotated = (a+w*tx+y*tz-z*ty, b+w*ty+z*tx-x*tz, c+w*tz+x*ty-y*tx)
        out.append(tuple(rotated[i]+pose['translation'][i]-origin[i]+offset[i] for i in range(3)))
    return out


def contact_measure(pp, mp, pillow_triangles, mattress_triangles):
    """Recompute all underside ray hits and true nearest-point witnesses."""
    grid = defaultdict(list); cell = 6.
    def projected_cross(t, points):
        a, b, c = [points[i] for i in t]
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    for ti, triangle in enumerate(mattress_triangles):
        if projected_cross(triangle, mp) <= 1e-10: continue
        points = [mp[i] for i in triangle]
        for x in range(math.floor(min(p[0] for p in points)/cell), math.floor(max(p[0] for p in points)/cell)+1):
            for y in range(math.floor(min(p[1] for p in points)/cell), math.floor(max(p[1] for p in points)/cell)+1):
                grid[x, y].append(ti)
    bottom = [t for t in pillow_triangles if projected_cross(t, pp) < -1e-10]
    vertices = sorted({i for t in bottom for i in t}); gaps = {}; best = math.inf
    for vi in vertices:
        p = pp[vi]; hit = None
        for ti in grid[math.floor(p[0]/cell), math.floor(p[1]/cell)]:
            a, b, c = [mp[i] for i in mattress_triangles[ti]]
            denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denominator) < 1e-12: continue
            u = ((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/denominator
            v = ((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/denominator
            weights = (u, v, 1-u-v)
            if min(weights) < -1e-7: continue
            height = sum(weights[i]*q[2] for i, q in enumerate((a, b, c)))
            if hit is None or height > hit[0]: hit = (height, ti)
        require(hit is not None, 'A pillow underside vertex lies outside the actual mattress surface.')
        gaps[vi] = p[2]-hit[0]
        best = min(best, math.dist(p, closest_point(p, *[mp[i] for i in mattress_triangles[hit[1]]])))
    area = sum(abs(projected_cross(t, pp))/2 for t in bottom
               if all(abs(gaps[i]) <= CONTACT_LIMITS['contact_distance_cm'] for i in t))
    footprint = (max(p[0] for p in pp)-min(p[0] for p in pp))*(max(p[1] for p in pp)-min(p[1] for p in pp))
    require(footprint > 0 and vertices, 'Empty contact surface.')
    separation = max(0., min(p[2] for p in pp)-max(p[2] for p in mp))
    require(abs(best-separation) < 1e-7, 'A real closest-point witness did not certify the global surface minimum.')
    return dict(minimum_vertex_triangle_distance_cm=best, minimum_surface_distance_cm=best,
                minimum_vertical_gap_cm=min(gaps.values()), contact_vertex_count=sum(abs(v) <= .02 for v in gaps.values()),
                contact_area_cm2=area, contact_area_fraction=area/footprint,
                tested_underside_vertices=len(vertices), tested_underside_triangles=len(bottom),
                global_vertical_separation_lower_bound_cm=separation, global_minimum_distance_certified=True)


def verify_contacts(baseline, manifest):
    ref = dict(file=manifest['source_contact_proof_file'], sha256=manifest['source_contact_proof_sha256'])
    require(Path(ref['file']).resolve() == (ART/'SourceContactProof.json').resolve(), 'Wrong source contact report.')
    report = bound(ref)
    require(report['schema'] == 'OldTownSoftGoodsSourceContactProofV1' and report['passed'] is True
            and report['pair_count'] == len(report['pairs']) == 55 and report['thresholds'] == CONTACT_LIMITS
            and report['source_map_sha256'] == baseline['source_map_sha256'], 'Incomplete source contact proof.')
    require(dict(file=report['source_snapshot_file'], sha256=report['source_snapshot_sha256'])
            == baseline['source_snapshot']['actors'], 'Contact actor snapshot differs.')
    require(dict(file=report['source_native_snapshot_file'], sha256=report['source_native_snapshot_sha256'])
            == baseline['source_snapshot']['native'], 'Contact exact native snapshot differs.')
    for prefix, expected in [('source_wpo', Path(__file__).resolve().parents[1]/'Saved/CodexOutputs/OldTownRealism_20261012/RealismApply.json'),
                             ('stage2_material_audit', SOURCE/'MaterialNativeAudit.json')]:
        require(Path(report[prefix+'_file']).resolve() == expected.resolve()
                and sha(expected) == report[prefix+'_sha256'] == manifest[prefix+'_sha256'], 'Contact WPO/material source changed.')
    actors = bound(baseline['source_snapshot']['actors'])['actors']
    native = index(bound(baseline['source_snapshot']['native'])['component_records'], True)
    components = {r['id']:(v, r) for v in manifest['variants'] for r in v['components']}
    expected_pillows = {i for i, (v, _) in components.items() if v['kind'] == 'BedPillow'}
    expected_mattresses = {i for i, (v, _) in components.items() if v['kind'] == 'BedMattress'}
    require({p['pillow_id'] for p in report['pairs']} == expected_pillows
            and {p['mattress_id'] for p in report['pairs']} == expected_mattresses
            and len(expected_pillows) == len(expected_mattresses) == 55, 'Contact pair identities differ.')
    recipes = {}; memo = {}; results = []
    for pair in report['pairs']:
        require(pair['passed'] is True, 'A source contact pair failed.')
        records = {}
        for name in ('pillow', 'mattress'):
            ident = pair[name+'_id']; variant, component = components[ident]
            actor, component_name = ident.split('::', 1)
            original_component = next(c for c in actors[actor]['components'] if c['name'] == component_name)
            require(pair[name+'_source_actor_state'] == {k:v for k,v in actors[actor].items() if k != 'components'}
                    and pair[name+'_source_component_state'] == original_component == component['source_component_state'],
                    'Contact original pose/state changed: ' + ident)
            original_native = native[ident]; offset = original_native['expected_surface_translation_cm_to_preserve']
            require(pair[name+'_source_native_world_pose'] == original_native['world_pose']
                    and pair[name+'_source_native_component_record'] == original_native,
                    'Contact native transform/component receipt changed: '+ident)
            require(offset is not None and original_native['uniform_slot_surface_translation']
                    and pair[name+'_effective_offset_cm'] == offset, 'Contact original effective WPO differs: ' + ident)
            recipe_ref = dict(file=pair[name+'_recipe_file'], sha256=pair[name+'_recipe_sha256'])
            fbx = Path(variant['fbx_file']); fbx = fbx if fbx.is_absolute() else ART/fbx
            require(recipe_ref == dict(file=variant['geometry_recipe_file'], sha256=variant['geometry_recipe_sha256'])
                    and Path(pair[name+'_fbx_file']).resolve() == fbx.resolve()
                    and pair[name+'_fbx_sha256'] == variant['fbx_sha256'] == sha(fbx), 'Contact source model binding differs.')
            key = recipe_ref['sha256']
            if key not in recipes: recipes[key] = bound(recipe_ref)
            records[name] = (recipes[key], original_native, offset, key)
        origin = records['mattress'][1]['world_pose']['translation']
        pr, pn, po, ph = records['pillow']; mr, mn, mo, mh = records['mattress']
        pp = transform_points(pr, pn, po, origin); mp = transform_points(mr, mn, mo, origin)
        cache_key = (ph, mh, json.dumps(pn['world_pose']['rotation_quaternion_xyzw']),
                     tuple(pn['world_pose']['scale']), tuple(mn['world_pose']['scale']),
                     tuple(sub(pn['world_pose']['translation'], origin)), tuple(po), tuple(mo),
                     tuple(mn['world_pose']['rotation_quaternion_xyzw']))
        if cache_key not in memo: memo[cache_key] = contact_measure(pp, mp, pr['triangles'], mr['triangles'])
        actual = memo[cache_key]
        for key, value in actual.items():
            require(near(pair[key], value, 1e-6) if not isinstance(value, bool) else pair[key] is value,
                    'Contact metric differs from actual source triangles: ' + pair['pillow_id'] + '/' + key)
        require(actual['minimum_surface_distance_cm'] <= .02 and actual['minimum_vertical_gap_cm'] >= -.002
                and actual['contact_vertex_count'] >= 10 and actual['contact_area_fraction'] >= .20,
                'Actual source contact fails its unchanged threshold.')
        require(len(pair['contact_points']) >= 10, 'Missing actual point/triangle contact witnesses.')
        for witness in pair['contact_points']:
            vi, ti = witness['pillow_vertex_index'], witness['mattress_triangle_index']
            require(type(vi) is int and 0 <= vi < len(pp) and type(ti) is int and 0 <= ti < len(mr['triangles']),
                    'Invalid contact witness triangle/vertex index.')
            triangle = [mp[i] for i in mr['triangles'][ti]]; closest = closest_point(pp[vi], *triangle)
            require(near(pp[vi], witness['pillow_vertex_relative_world_cm'], 1e-6)
                    and near(closest, witness['closest_triangle_point_relative_world_cm'], 1e-6)
                    and near([pp[vi][i]+origin[i] for i in range(3)], witness['pillow_vertex_world_cm'], 1e-6)
                    and near([closest[i]+origin[i] for i in range(3)], witness['closest_point_cm'], 1e-6)
                    and abs(math.dist(pp[vi], closest)-witness['distance_cm']) <= 1e-6,
                    'Contact witness is not on the actual source triangle.')
            weights = witness['barycentric']
            require(len(weights) == 3 and min(weights) >= -1e-7 and abs(sum(weights)-1) < 1e-7,
                    'Contact ray barycentrics are invalid.')
            ray = [sum(weights[j]*triangle[j][i] for j in range(3)) for i in range(3)]
            require(near(ray[:2], pp[vi][:2], 1e-6)
                    and abs(pp[vi][2]-ray[2]-witness['vertical_gap_cm']) <= 1e-6, 'Contact vertical ray witness differs.')
        results.append(dict(passed=True, pillow_id=pair['pillow_id'], mattress_id=pair['mattress_id'], **actual))
    return dict(passed=True, source_report=ref, pair_count=55, source_map_sha256=baseline['source_map_sha256'],
                thresholds=CONTACT_LIMITS, method='Independent actual world-triangle ray/closest-point/area recomputation with original native pose and WPO.', pairs=results)


def commandlets():
    result = read(W/'RunCompletion.json'); require(result['passed'] is True and len(result['runs']) == 3, 'Three helper completions required.')
    tokens = {'InputExport':'SOFT_GOODS_INPUT_EXPORT_PASS', 'BuildApply':'SOFT_GOODS_APPLIED', 'SavedAudit':'SOFT_GOODS_SAVED_AUDIT_PASS',
              'OverlapCorrection':'SOFT_GOODS_OVERLAP_CORRECTION_PASS'}
    seen = set()
    for run in result['runs']:
        role = next((r for r in tokens if re.fullmatch(re.escape(r)+r'\d*', run['name'])), None)
        require(role is not None and role not in seen and run['exit_code'] == 0
                and run.get('normal_exit_observed_by_root') is True
                and run['success_token'] == tokens[role], 'A required owned helper failed or has the wrong role.')
        seen.add(role); path = Path(run['log']['file'])
        require(path.resolve().is_relative_to(W.resolve()) and sha(path) == run['log']['sha256'], 'Helper log ownership/hash differs.')
        text = path.read_text(encoding='utf-8-sig', errors='replace')
        require(tokens[role] in text and 'LogExit: Exiting.' in text and 'Python script executed with errors' not in text,
                'Required helper lacks its success token and normal exit.')
        require(not re.search(r'(?:LogMaterial|LogShaderCompilers).*?(?:Error:|Failed to compile|error [A-Z]+\d+|Missing.*Texture)', text, re.I), 'Completed helper has a shader failure.')
        require(run.get('forced_cleanup', False) is False and run.get('reused', False) is False,
                'A required helper was forcibly terminated or reused.')
    require(seen == set(tokens), 'Missing InputExport/BuildApply/SavedAudit completion.')
    return reference(W/'RunCompletion.json')


def verify_capture_setup(baseline, build, build_ref, digest):
    setup = read(W/'CaptureSetup.json')
    require(setup['passed'] is True and setup['map_sha256'] == digest
            and setup['source'] == 'fresh_persisted_map_load'
            and dict(file=setup['build_report_file'], sha256=setup['build_report_sha256']) == build_ref,
            'Capture setup is failed, stale or bound to another BuildReport.')
    scripts = {str((Path(__file__).resolve().parent/name).resolve()):sha(Path(__file__).resolve().parent/name)
               for name in ('CaptureOldTownSoftGoodsViews.py', 'CaptureOldTownSoftGoodsViews.ps1')}
    require(setup['scripts'] == scripts, 'Capture helper set or frozen script hashes differ.')
    source_build = bound(dict(file=str(SOURCE/'BuildReport.json'),
                              sha256=baseline['source_report_sha256'][str(SOURCE/'BuildReport.json')]))
    cameras = setup['standard_cameras']; soft = setup['softgoods_cameras']
    require(cameras == build['hotel_openings_review_cameras'] == source_build['hotel_openings_review_cameras']
            and len(cameras) == len(set(cameras)) == 14
            and soft == build['softgoods_review_cameras'] and len(soft) == len(set(soft)) == 2
            and set(soft) == {'CAM_V4_UpperCore', 'CAM_V4_CentralStair'}
            and len(LAMP_CAMERAS) == len(set(LAMP_CAMERAS)) == 3
            and set(LAMP_CAMERAS).issubset(cameras) and not set(soft).intersection(cameras)
            and len(cameras)+len(LAMP_CAMERAS)+len(soft) == 19,
            'Capture setup does not prescribe the exact14 standard,3 actual-light and2 cloth views.')
    require(setup['camera_poses_transient_only'] is True and setup['saved_cameras_preserved'] is True
            and setup['view_mode'] == 'lit' and setup['width'] == 1920 and setup['height'] == 1080
            and setup['maximum_cameras_per_batch'] == 4,
            'Capture setup altered saved cameras, render configuration or batch size.')
    require(setup['parallel_user_main_editor_authorized'] is True
            and baseline['parallel_main_edit']['assistant_map_write_allowed'] is False
            and build['target_level'] == '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',
            'Parallel user Main editing or assistant Main-write isolation differs.')
    return reference(W/'CaptureSetup.json')


def capture_group(directory, cameras, lighting, digest, packages, build_ref):
    runs = read(directory/'CaptureRuns.json')
    require(len(runs) == len(cameras) == len({r['camera'] for r in runs}), 'Duplicate/missing capture run.')
    proof = captures(directory, cameras, lighting, digest, packages)
    for row in proof['rows']:
        meta = bound(row['metadata'])
        require(meta['fresh_map_load_verified'] is True and meta['source_build_report'] == build_ref
                and meta['map_sha256_after_cleanup'] == digest, 'Capture BuildReport/fresh-source binding differs.')
        if lighting == 'street_only': require(meta['temporary_lighting_created_count'] == 0, 'Actual-light capture used inspection fill.')
        batch = read(directory/'Runs'/meta['run_id']/'CaptureBatch.json')
        require(batch['source_build_report'] == build_ref, 'Capture batch BuildReport binding differs.')
    return proof


def verify_visual(visual, digest, expected):
    require(visual['passed'] is True and visual['map_sha256'] == digest and visual['image_sha256'] == expected,
            'Actual visual review is missing, incomplete or stale.')
    viewed = set()
    def rows(items):
        for row in items:
            path = row.get('file', row.get('png_file'))
            if path and row.get('directly_viewed') is True:
                require(path in expected, 'Review names an unbound screenshot.')
                if 'png_sha256' in row: require(row['png_sha256'] == expected[path], 'Reviewed PNG hash differs.')
                viewed.add(path)
    for field in ('root_reviewed_frames', 'reviewed_frames', 'screenshots'): rows(visual.get(field, []))
    for field, ref in visual.items():
        if field.endswith('_review') and isinstance(ref, dict) and set(('file','sha256')).issubset(ref):
            review = bound(ref); require(review['passed'] is True and review['map_sha256'] == digest, 'Referenced visual review is stale.')
            for key in ('screenshots','reviewed_frames','root_reviewed_frames'): rows(review.get(key, []))
    require(viewed == set(expected), 'Some required frames were not directly viewed.')


def publish_reports(baseline, build, result, geometry, expected, cameras):
    pointer = bound(baseline['source_current_evidence'])
    require(sha(CANON/'CurrentEvidence.json') == baseline['source_current_evidence']['sha256'], 'Published source pointer changed before publication.')
    historical = W/'Before/CanonicalReports'; historical.mkdir(parents=True, exist_ok=True)
    for name, digest in pointer['current_report_sha256'].items():
        require(Path(name).name == name and sha(CANON/name) == digest, 'Prior canonical report changed: ' + name)
        backup = historical/name
        if backup.exists(): require(sha(backup) == digest, 'Existing historical report differs.')
        else: shutil.copy2(CANON/name, backup)
    hashes = {name:sha(W/name) for name in REPORTS}
    for name, digest in hashes.items():
        temporary = CANON/(name+'.stage3.tmp'); shutil.copy2(W/name, temporary)
        require(sha(temporary) == digest, 'Staged canonical report copy differs.')
        os.replace(temporary, CANON/name)
    require(all(sha(CANON/name) == digest for name, digest in hashes.items()), 'Canonical reports differ.')
    # No source Stage2 file or package may change during the copy operation.
    for path, digest in {**baseline['source_report_sha256'], **baseline['previous_asset_sha256'],
                         **baseline['protected_file_sha256'], **result['current_asset_sha256']}.items():
        require(sha(path) == digest, 'Protected source changed during publication: ' + path)
    require(sha(MAP) == result['map_sha256'], 'Target map changed during publication.')
    current = dict(target_level=build['target_level'], map_sha256=result['map_sha256'], source_map_sha256=baseline['source_map_sha256'],
        source_bundle_name=W.name, source_directory=str(W), source_bundle=str(W), current_reports=REPORTS,
        current_report_sha256=hashes, current_asset_sha256=result['current_asset_sha256'],
        current_final_review=str(W/'FinalReview.json'), current_final_review_sha256=hashes['FinalReview.json'],
        current_actor_snapshot=str(W/'AfterSnapshot.json'), current_actor_snapshot_sha256=hashes['AfterSnapshot.json'],
        current_render_geometry=geometry['file'], current_render_geometry_sha256=geometry['sha256'],
        current_capture_directory=str(W/'Captures'), current_capture_runs_file=str(W/'Captures/CaptureRuns.json'),
        current_capture_runs_sha256=sha(W/'Captures/CaptureRuns.json'), current_render_cameras=cameras,
        current_lamp_capture_directory=str(W/'LampCaptures'), current_softgoods_capture_directory=str(W/'SoftGoodsCaptures'),
        current_renders=expected, source_current_evidence_before=baseline['source_current_evidence'],
        previous_bundle=pointer['source_directory'], previous_evidence_status='Preserved accepted Stage2 materials and lamps; Stage3 changes only the selected cloth meshes.',
        actor_count=8014, scene_component_count=13920, hotel_actor_count=2975, outside_hotel_actor_count=5039,
        changed_component_count=222, changed_actor_count=222, new_meshes=20, new_packages=40,
        emissive_fixture_count=16, parallel_main_edit=baseline['parallel_main_edit'], assistant_main_map_write_allowed=False,
        scope='20 softgoods variants, 222 mesh assignments; all old packages, rigid geometry, materials, pose, collision, WPO and lights preserved.',
        opening_blueprints_folder='/Game/CodexGenerated/OldTown/Blueprints/Openings',
        published_utc=datetime.now(timezone.utc).isoformat())
    write(CANON/'CurrentEvidence.json', current)


def main(publish=False):
    generated_here = {'SourceContactProof.json', 'SourceContactAudit.json', 'CaptureReview.json', 'FinalReview.json'}
    required = [W/name for name in REPORTS if name not in generated_here]
    required += [W/group/'CaptureRuns.json' for group in ('Captures','LampCaptures','SoftGoodsCaptures')]
    missing = [str(path) for path in required if not path.is_file()]
    require(not missing, 'Stage3 evidence is incomplete; nothing was published: ' + ', '.join(missing))
    baseline, plan, applied, after, build = [read(W/name) for name in
        ('Baseline.json','ApprovedPlan.json','Applied.json','After.json','BuildReport.json')]
    manifest_ref = applied['manifest']; manifest = bound(manifest_ref)
    source_audit = read(W/'SourceAudit.json')
    require(source_audit['schema'] == 'OldTownSoftGoodsIndependentSourceAuditV1'
            and source_audit['passed'] is True and not source_audit['errors']
            and source_audit['source_map_sha256'] == baseline['source_map_sha256']
            and source_audit['manifest'] == manifest_ref and source_audit['variant_count'] == 20
            and source_audit['component_count'] == 222
            and source_audit['source_recipe_binary_fbx_and_float32_all_closed_valid'] is True
            and source_audit['original_structural_faces_and_corner_buffers_preserved'] is True,
            'Independent frozen source audit failed or is stale.')
    require(len(source_audit['variants']) == 20
            and {v['key'] for v in source_audit['variants']} == {v['key'] for v in manifest['variants']}
            and all(v['passed'] is True and all(v[k]['passed'] is True for k in
                    ('recipe','binary_fbx','float32_local_cm')) for v in source_audit['variants']),
            'Independent source proof does not cover all20 models.')
    for path, digest in source_audit['input_sha256'].items():
        require(Path(path).is_absolute() and sha(path) == digest, 'Independent source audit input changed: '+path)
    require(sha(manifest['source_script_file']) == manifest['source_script_sha256'], 'Authoring script changed after source freeze.')
    preservation = verify_stage(baseline, manifest_ref, after); digest = sha(MAP)
    proofs = preservation['mesh_proofs']
    require(len(proofs) == 20 and all(all(p[key]['passed'] is True for key in
        ('source','closed','frames','physical_uv','binary_faces','original_native_structural_buffers')) for p in proofs.values()), 'An actual source/native proof failed.')
    require(preservation['changed_components'] == 222 and preservation['previous_packages_preserved'] == 1166
            and preservation['new_packages'] == 40 and preservation['assistant_main_map_write_allowed'] is False, 'Unapproved mesh-only footprint.')
    new = after['new_asset_sha256']; packages = after['current_asset_sha256']
    mesh_files = {str(Path(r['file']).resolve()) for r in after['mesh_records'].values()}
    caches = set(new)-mesh_files
    require(len(new) == 40 and len(packages) == 1206 and len(mesh_files) == len(caches) == 20
            and all(Path(p).suffix == '.uasset' and Path(p).resolve().is_relative_to(GENERATED.resolve()) for p in new)
            and all(Path(p).parent == GENERATED/'Meshes/ImportData' for p in caches), 'Expected exactly 20 new meshes plus 20 owned import caches.')
    require(build['new_asset_sha256'] == packages and build['map_sha256'] == digest == applied['map_sha256'] == after['map_sha256']
            and applied['models'] == 20 and applied['components'] == 222 and applied['new_asset_sha256'] == new
            and plan['passed'] is True and plan['manifest'] == manifest_ref and plan['new_asset_sha256'] == new
            and len(plan['components']) == len({r['id'] for r in plan['components']}) == 222, 'Build/apply/plan binding differs.')
    correction = bound(applied['overlap_correction'])
    require(applied['overlap_correction'] == reference(W/'OverlapCorrection.json')
            and correction['passed'] is True and correction['source_manifest'] == manifest_ref
            and correction['map_sha256'] == digest and correction['map_save_requested'] is False
            and correction['model'] == 'LegacyBedMattress' and correction['instances'] == 7
            and len(correction['changed_owned_packages']) == 2
            and set(correction['changed_owned_packages']).issubset(new)
            and correction['other_38_owned_packages_unchanged'] is True
            and correction['original_1166_packages_unchanged'] is True
            and correction['actor_component_material_collision_pose_and_lights_unchanged'] is True
            and correction['lateral_fold_guard']['passed'] is True
            and all(p['passed'] is True for p in correction['native_proof'].values()),
            'The discovered legacy side-fold overlap correction is incomplete.')
    require(set(plan['mesh_records']) == set(proofs), 'Approved model records differ.')
    runs = commandlets()
    for name in ('PreservationAudit.json','GeometryPreservation.json','LightAudit.json','AfterSummary.json'):
        document = read(W/name); require(document['passed'] is True and document['map_sha256'] == digest, 'Failed/stale '+name)
    light = read(W/'LightAudit.json'); old_light = bound(baseline['source_snapshot']['lights'])
    require(light['lights'] == after['light_inventory'] == old_light['lights'] and light['emissive_fixture_count'] == 16
            and light['total_light_components'] == old_light['total_light_components'] == 19
            and light['unchanged_from_material_stage'] is True, 'Original16-fixture light state changed.')
    geom_protection = read(W/'GeometryPreservation.json')
    require(geom_protection['changed_models'] == 20 and geom_protection['unchanged_models'] == 325
            and len(geom_protection['unchanged_native_models']) == 325
            and geom_protection['pose_parent_collision_and_material_wpo_preserved'] is True, 'Whole-map native preservation coverage differs.')
    for row in geom_protection['unchanged_native_models']:
        require(row['actual_buffers_unchanged'] is True and sha(row['geometry_file']) == row['geometry_sha256'], 'An unchanged model export differs.')
    contact = verify_contacts(baseline, manifest)
    geometry = reference(W/'GeometryAfter.json'); scan = read(W/'SurfaceScanSummary.json')
    require(scan['passed'] is True and scan['provenance']['source_map_sha256'] == digest
            and scan['provenance']['source_geometry_sha256'] == geometry['sha256'], 'Whole-map scan geometry differs.')
    scope, stats = scan['scope'], scan['stats']
    require(scope['component_count'] == stats['visible_components'] == 8719 and scope['include_internal'] is True
            and scope['axis_only'] is False and scope['plane_tolerance_cm'] == .03 and scope['normal_tolerance'] == .0001
            and scope['minimum_overlap_area_cm2'] == 1. and stats.get('non_axis_faces_skipped', 0) == 0
            and stats['input_faces'] == stats['axis_faces_scanned']+stats['non_axis_faces_scanned']
            and all(value == 0 for key, value in stats.items() if 'skip' in key.lower()), 'Incomplete or weakened all-normal/internal scan.')
    require(scan['counts']['exposed_groups'] == scan['counts']['exact_duplicate_box_groups'] == 0, 'An exposed overlap/duplicate remains.')
    for key, filename in [('scan','CoplanarScan.json'), ('classified_scan','InternalOcclusionScan.json')]:
        require(Path(scan['provenance'][key+'_path']).resolve() == (W/filename).resolve()
                and sha(W/filename) == scan['provenance'][key+'_sha256'], 'Scan report hash differs.')
    summary = read(W/'AfterSummary.json'); require(summary == scan['export_summary'] and summary['actors'] == 8014
        and summary['visible_components'] == 8719 and summary['unique_meshes'] == 344 and not summary['errors'], 'Scan/export world coverage differs.')
    build_ref = reference(W/'BuildReport.json'); cameras = build['hotel_openings_review_cameras']
    verify_capture_setup(baseline, build, build_ref, digest)
    soft_cameras = build['softgoods_review_cameras']
    require(len(cameras) == len(set(cameras)) == 14 and len(soft_cameras) == len(set(soft_cameras)) == 2
            and set(soft_cameras) == {'CAM_V4_UpperCore','CAM_V4_CentralStair'}, 'Required14+3+2 review views differ.')
    groups = {'standard':capture_group(W/'Captures', cameras, 'temporary', digest, packages, build_ref),
              'actual_lights':capture_group(W/'LampCaptures', LAMP_CAMERAS, 'street_only', digest, packages, build_ref),
              'softgoods_closeups':capture_group(W/'SoftGoodsCaptures', soft_cameras, 'temporary', digest, packages, build_ref)}
    expected = {r['image']['file']:r['image']['sha256'] for group in groups.values() for r in group['rows']}
    require(len(expected) == 19, 'Nineteen distinct fresh captures required.')
    visual = read(W/'VisualReview.json'); verify_visual(visual, digest, expected)
    # All gates pass before writing any publication result.
    shutil.copy2(contact['source_report']['file'], W/'SourceContactProof.json')
    require(sha(W/'SourceContactProof.json') == contact['source_report']['sha256'], 'Source contact report copy differs.')
    write(W/'SourceContactAudit.json', contact)
    write(W/'CaptureReview.json', dict(passed=True, map_sha256=digest, source_build_report=build_ref, required_frames=19, groups=groups))
    result = dict(passed=True, published=bool(publish), stage=W.name, target_level=build['target_level'],
        source_map_sha256=baseline['source_map_sha256'], map_sha256=digest, actor_count=8014, scene_component_count=13920,
        models=20, changed_components=222, changed_actors=222, immutable_previous_packages=1166, new_packages=40,
        current_asset_sha256=packages, source_manifest=manifest_ref, source_contact_proof=reference(W/'SourceContactProof.json'),
        independent_source_audit=reference(W/'SourceAudit.json'),
        source_contact_audit=reference(W/'SourceContactAudit.json'), contact_pairs=55,
        actual_source_native_frames_uv_binary_faces_and_rigid_buffers_passed=True,
        materials_pose_parent_body_collision_wpo_and_lights_preserved=True, emissive_fixtures=16,
        opening_blueprints_preserved=18, original_mainhome_structure_preserved=True,
        parallel_main_edit=baseline['parallel_main_edit'], assistant_main_map_write_allowed=False,
        source_current_evidence_before=baseline['source_current_evidence'], whole_map_geometry=geometry,
        preservation=reference(W/'PreservationAudit.json'), scan=reference(W/'SurfaceScanSummary.json'),
        captures=reference(W/'CaptureReview.json'), required_frames=19, visual_review=reference(W/'VisualReview.json'),
        normally_exited_commandlets=runs, limitations=visual['limitations'], completed_utc=datetime.now(timezone.utc).isoformat())
    write(W/'FinalReview.json', result)
    if publish: publish_reports(baseline, build, result, geometry, expected, cameras)
    print(json.dumps(dict(passed=True, published=bool(publish), map_sha256=digest, models=20,
                         changed_components=222, new_packages=40, contact_pairs=55, reviewed_frames=19)))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--publish', action='store_true')
    main(parser.parse_args().publish)
