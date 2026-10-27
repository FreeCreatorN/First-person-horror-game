"""Independent actual-face and solid checks for the saved rounded cisterns.

Ordinary Python only; no Unreal, map or package mutation. Reads five saved
geometry/state/build inputs plus persisted render-normal evidence. Only writes
FinishGeometryAudit.json in the new stage. All earlier stages stay untouched.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import AnalyzeOldTownSanitaryShapes as core
import AnalyzeOldTownSanitaryFixtures as prior
import OldTownToiletConnectionPlan as solid
import OldTownSanitaryShapePlan as cup
import OldTownSanitaryFinishPlan as finish

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK = ROOT/'Saved/CodexOutputs/SanitaryFinish_20261012'
DEFAULT_SOURCE = ROOT/'Saved/CodexOutputs/SanitaryShapes_20261011'
SOURCE_SHA = '96a927f42d52477d371665aad35ac8fdd85406eb42a91940cf047213cde8c44d'
SOURCE_TOILET = '/Game/CodexGenerated/OldTown/Meshes/SanitaryShapes_20261011/SM_OTS_Arch_Toilet_Shaped.SM_OTS_Arch_Toilet_Shaped'
SOURCE_BASIN = '/Game/CodexGenerated/OldTown/Meshes/SanitaryShapes_20261011/SM_OTS_Arch_Washbasin_Shaped.SM_OTS_Arch_Washbasin_Shaped'
MAIN_PREVIOUS_SHA = 'b20f1046a0d099a3f1baa4fdefa0ff6be6771fed0f8f30e4f6523f3fe63371d7'
MAIN_CURRENT_INPUT_SHA = '629d295921d48a016aad82113e70eb740378b917120ed31354005c9c6bff5578'
EPS = .002


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_toilet(before_v, before_t, after_v, after_t, state, asset_row):
    checks = []

    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))

    recipe = finish.build_pieces()
    removals = finish.source_removal_specs()
    check('only_fourteen_complete_cistern_and_lid_source_islands_removed', len(removals) == 14 and
          asset_row.get('removed_part_names') == [r['name'] for r in removals] and
          sum(r['triangles'] for r in removals) == 215 and
          all(r['fixture'] == 'Toilet' and r['material_id'] == 0 for r in removals))
    check('exactly_two_new_ceramic_toilet_solids', len(recipe) == 2 and
          all(p['fixture'] == 'Toilet' and p['material_id'] == 0 for p in recipe))
    reversed_for_render = asset_row.get('render_indices_reversed') is True
    check('outward_recipe_faces_explicitly_reversed_for_ue_render', reversed_for_render)
    removed = set()
    for row in removals:
        triangles = core._part_by_bounds(before_v, before_t, row['bounds_cm'], row['name'])
        check('removed_whole_source_island_'+row['name'], len(triangles) == row['triangles'],
              actual_faces=len(triangles), expected_faces=row['triangles'],
              actual_bounds_cm=solid._bounds(before_v, triangles))
        removed.update(tuple(t) for t in triangles)
    retained = [t for t in before_t if tuple(t) not in removed]
    retained_after, unmatched, proof = core._match_faces(before_v, retained, after_v, after_t,
                         core._coordinate_budgets(state, before_v, source_comparison=True))
    check('all_retained_source_faces_match_one_to_one', proof.pop('passed'), **proof)
    check('exactly_215_original_faces_removed', len(removed) == 215,
          actual_removed=len(removed), retained_source_faces=len(retained))
    parts = {}
    for piece in recipe:
        vv, tt = piece['vertices'], piece['triangles']
        expected_t = [[t[0], t[2], t[1]] for t in tt] if reversed_for_render else tt
        actual, unmatched, proof = core._match_faces(vv, expected_t, after_v, unmatched,
                                                    core._coordinate_budgets(state, vv))
        check(piece['name']+'_all_prescribed_faces_present', proof.pop('passed'), **proof)
        parts[piece['name']] = actual
        topology = core._topology(after_v, actual, -1 if reversed_for_render else 1)
        check(piece['name']+'_actual_closed_oriented_solid', topology.pop('passed'), **topology)
        actual_bounds = solid._bounds(after_v, actual)
        expected_bounds = [[min(p[j] for p in vv) for j in range(3)],
                           [max(p[j] for p in vv) for j in range(3)]]
        check(piece['name']+'_actual_bounds_match_prescribed_envelope',
              core._bounds_same(actual_bounds, expected_bounds),
              actual_bounds_cm=actual_bounds, expected_bounds_cm=expected_bounds)
        lo, hi = actual_bounds
        midpoint = [(lo[j]+hi[j])/2 for j in range(3)]
        corner_results = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                point = [lo[0]+.05 if sx < 0 else hi[0]-.05,
                         lo[1]+.05 if sy < 0 else hi[1]-.05, midpoint[2]]
                corner_results.append(dict(point_cm=point,
                                           inside=solid._inside(point, after_v, actual)))
        check(piece['name']+'_all_four_old_sharp_corners_are_actually_clipped',
              not any(r['inside'] for r in corner_results), actual_solid_tests=corner_results)
        core_points = [midpoint]
        for axis in (0, 1):
            for sign in (-1, 1):
                p = list(midpoint)
                p[axis] = lo[axis]+.05 if sign < 0 else hi[axis]-.05
                core_points.append(p)
        core_results = [dict(point_cm=p, inside=solid._inside(p, after_v, actual)) for p in core_points]
        check(piece['name']+'_centre_and_side_panels_remain_solid',
              all(r['inside'] for r in core_results), actual_solid_tests=core_results)
    check('no_unprescribed_added_or_removed_faces', not unmatched and
          len(retained_after)+sum(len(ts) for ts in parts.values()) == len(after_t),
          extra_faces=len(unmatched), actual_faces=len(after_t))
    check('entire_original_fixture_envelope_preserved', core._bounds_same(
          solid._bounds(before_v, before_t), solid._bounds(after_v, after_t)),
          before_bounds_cm=solid._bounds(before_v, before_t),
          after_bounds_cm=solid._bounds(after_v, after_t))
    expected_parts = dict(
        HollowCeramicBowl=(1920, [[-30.76, -17., 25.], [12.76, 17., 40.7]]),
        TaperedRearCeramicShoulder=(896, [[-3., -12., 29.5], [29., 12., 46.]]),
        Seat=(512, [[-32.01, -17.7, 40.3], [14.01, 17.7, 42.7]]),
        Pedestal=(92, [[-21.4, -11.2, 0.], [9.4, 11.2, 32.]]),
        RearCeramicPedestal=(144, [[1., -9., 0.], [25., 9., 31.]]))
    for name, (count, bounds) in expected_parts.items():
        old_part = core._part_by_bounds(before_v, retained, bounds, name)
        actual, _, proof = core._match_faces(before_v, old_part, after_v, retained_after,
                            core._coordinate_budgets(state, before_v, source_comparison=True))
        check('original_'+name+'_actual_faces_are_unchanged', proof.pop('passed') and
              len(old_part) == len(actual) == count, source_part_expected_faces=count, **proof)
        parts[name] = actual
    preserve_checks = [c for c in checks if c['name'].startswith('original_') and
                       c['name'].endswith('_actual_faces_are_unchanged')]
    check('source_bowl_seat_feet_and_shoulder_preserved', len(preserve_checks) == 5 and
          all(c['passed'] for c in preserve_checks))
    lever_main = core._part_by_bounds(before_v, retained,
                       [[32.2, -1.75, 67.], [33., 1.75, 69.]], 'FlushLeverMain')
    lever_patch = core._part_by_bounds(before_v, retained,
                       [[32.966, -1.55, 67.2], [32.966, 1.55, 68.8]], 'FlushLeverPatch')
    lever = lever_main+lever_patch
    lever_actual, _, proof = core._match_faces(before_v, lever, after_v, retained_after,
                            core._coordinate_budgets(state, before_v, source_comparison=True))
    check('all_108_original_metal_flush_lever_faces_preserved', proof.pop('passed') and
          len(lever_main) == 106 and len(lever_patch) == 2 and len(lever_actual) == 108, **proof)
    parts['FlushLever'] = lever_actual
    for witness in finish.CONNECTION_WITNESSES:
        inside = {name: solid._inside(witness['point'], after_v, parts[name])
                  for name in witness['parts'] if name in parts}
        check('solid_connection_'+witness['name'], len(inside) == len(witness['parts'])
              and all(inside.values()), point_local_cm=witness['point'], actual_inside_parts=inside)
    check('exactly_five_prescribed_new_connection_witnesses', len(finish.CONNECTION_WITNESSES) == 5)
    for index, point in enumerate(cup.CAVITY_EMPTY_WITNESSES):
        inside = {name: solid._inside(point, after_v, triangles) for name, triangles in parts.items()}
        check('preserved_cavity_remains_empty_'+str(index), not any(inside.values()),
              point_local_cm=point, actual_inside_parts=inside)
    for index, point in enumerate(([-9., 0., 41.], [-11., 0., 41.], [-7., 0., 41.], [-9., 1., 41.])):
        distances = core._ray_hits(point, [0., 0., -1.], after_v, parts['HollowCeramicBowl'])
        good = len(distances) == 2 and all(abs(a-b) <= EPS for a, b in zip(distances, [7.5, 16.]))
        check('preserved_cavity_floor_and_bottom_shell_ray_'+str(index), good,
              actual_ray_distances_cm=distances, expected_distances_cm=[7.5, 16.],
              actual_floor_thickness_cm=distances[1]-distances[0] if len(distances) == 2 else None)
    new_bounds = [solid._bounds(after_v, parts[p['name']]) for p in recipe]
    ordered = sorted(new_bounds, key=lambda b: b[0][2])
    check('body_and_lid_keep_approved_heights_and_embedded_joint',
          core._bounds_same(ordered[0], [[13., -17.5, 45.], [33., 17.5, 75.7]]) and
          core._bounds_same(ordered[1], [[13., -17.5, 75.4], [33., 17.5, 78.]]) and
          abs(ordered[0][1][2]-ordered[1][0][2]-.3) <= EPS,
          actual_body_bounds_cm=ordered[0], actual_lid_bounds_cm=ordered[1],
          actual_vertical_embedding_cm=ordered[0][1][2]-ordered[1][0][2])
    body_faces, lid_faces = parts['RoundedCisternBody'], parts['RoundedCisternLid']
    plane_rows = []
    for axis, value in ((0, 13.), (0, 33.), (1, -17.5), (1, 17.5)):
        def planar_faces(ts):
            return [t for t in ts if all(abs(after_v[i][axis]-value) <= EPS for i in t)]
        bf, lf = planar_faces(body_faces), planar_faces(lid_faces)
        bz = max((after_v[i][2] for t in bf for i in t), default=None)
        lz = min((after_v[i][2] for t in lf for i in t), default=None)
        gap = lz-bz if bz is not None and lz is not None else None
        plane_rows.append(dict(axis=axis, plane_cm=value, body_faces=len(bf), lid_faces=len(lf),
                               body_actual_wall_top_z_cm=bz, lid_actual_wall_bottom_z_cm=lz,
                               vertical_clearance_cm=gap))
    check('actual_flat_side_planes_have_055_cm_vertical_separation',
          all(r['body_faces'] > 0 and r['lid_faces'] > 0 and
              abs(r['vertical_clearance_cm']-.55) <= EPS and
              r['vertical_clearance_cm'] > .03 for r in plane_rows), actual_plane_rows=plane_rows)
    new_low = min(b[0][2] for b in new_bounds)
    cup_top = solid._bounds(after_v, parts['HollowCeramicBowl'])[1][2]
    check('all_new_cistern_geometry_stays_43_cm_above_preserved_cup',
          abs(new_low-cup_top-4.3) <= EPS, actual_vertical_gap_cm=new_low-cup_top)
    return dict(passed=all(c['passed'] for c in checks), checks=checks,
                retained_source_faces=len(retained), removed_source_faces=len(removed),
                new_faces=sum(len(p['triangles']) for p in recipe))


def analyze(work=DEFAULT_WORK, source=DEFAULT_SOURCE, write_output=True):
    work, source = Path(work).resolve(), Path(source).resolve()
    paths = dict(newGeo=work/'GeometryAfter.json', newSnapshot=work/'AfterSnapshot.json',
                 newBuild=work/'BuildReport.json', oldGeo=source/'GeometryAfter.json',
                 oldSnapshot=source/'AfterSnapshot.json')
    ng, ns, build, og, os = [read(p) for p in paths.values()]
    map_sha = build['map_sha256']
    refinement = build.get('sanitary_finish_refinement', {})
    checks, fixtures = [], []

    def check(name, passed, actor=None, **details):
        identity = actor if actor is not None else details.get('mesh')
        row = dict(name=identity+':'+name if identity is not None else name,
                   passed=bool(passed), **details)
        if actor is not None:
            row['actor'] = actor
        checks.append(row)

    check('fresh_saved_exports_match_current_build', ng.get('map_sha256') == ns.get('source_map_sha256') == map_sha
          and ns.get('passed') is True and not ng.get('errors') and build.get('status') == 'PASS')
    check('expected_verified_source_baseline', og.get('map_sha256') == os.get('source_map_sha256') == SOURCE_SHA
          and os.get('passed') is True and not og.get('errors'))
    check('build_source_matches_verified_baseline', build.get('source_map_sha256') == SOURCE_SHA)
    # The user saved L_Main before this stage. Only that explicitly recorded
    # pre-apply hash rebase is allowed. The immutable source remains untouched;
    # its actor states, all references and every other snapshot field must be
    # identical to the stage's input snapshot.
    input_path, rebase_path = work/'InputSnapshot.json', work/'ProtectedMapInputRebase.json'
    original_snapshot = os
    input_snapshot = read(input_path) if input_path.is_file() else {}
    rebase = read(rebase_path) if rebase_path.is_file() else {}
    main_path = str(ROOT/'Content/Yastar/Maps/L_Main.umap')
    recorded_protected = original_snapshot.get('protected_map_sha256', {})
    expected_protected = deepcopy(recorded_protected)
    expected_protected[main_path] = MAIN_CURRENT_INPUT_SHA
    expected_input = deepcopy(original_snapshot)
    expected_input['protected_map_sha256'] = expected_protected
    check('input_snapshot_only_rebases_preexisting_user_saved_main_map', input_snapshot == expected_input and
          recorded_protected.get(main_path) == MAIN_PREVIOUS_SHA and len(recorded_protected) == 3)
    expected_backup = work/'Before/ProtectedMaps/L_Main.umap'
    expected_change = [dict(file=main_path, previous_sha256=MAIN_PREVIOUS_SHA,
                            current_sha256=MAIN_CURRENT_INPUT_SHA)]
    check('strict_single_preapply_main_map_rebase_record', rebase.get('passed') is True and
          rebase.get('source_map_sha256') == SOURCE_SHA and
          rebase.get('source') == 'current_disk_before_map_apply' and
          rebase.get('recorded_input') == recorded_protected and
          rebase.get('current_input') == expected_protected and
          rebase.get('changes') == expected_change and
          rebase.get('preserved_current_copy') == str(expected_backup) and
          rebase.get('preserved_current_copy_sha256') == MAIN_CURRENT_INPUT_SHA)
    check('current_user_saved_main_map_and_preapply_copy_preserved', Path(main_path).is_file() and
          sha(main_path) == MAIN_CURRENT_INPUT_SHA and expected_backup.is_file() and
          sha(expected_backup) == MAIN_CURRENT_INPUT_SHA)
    os = input_snapshot
    assets = refinement.get('new_assets', [])
    check('exactly_one_new_owned_toilet_mesh_asset', len(assets) == 1 and
          assets[0].get('asset_key') == 'Toilet' and assets[0].get('source') == SOURCE_TOILET)
    asset_row = assets[0] if len(assets) == 1 else {}
    toilets = [c for c in og['components'] if c['mesh'] == SOURCE_TOILET]
    basins = [c for c in og['components'] if c['mesh'] == SOURCE_BASIN]
    targets = {c['actor'] for c in toilets}
    all_fixture_labels = targets | {c['actor'] for c in basins}
    check('thirty_existing_toilets_and_thirty_basins', len(toilets) == len(basins) == 30 and
          len(targets) == 30 and len(all_fixture_labels) == 60)
    check('declared_change_scope_is_only_thirty_toilets', prior.names(refinement.get('changed_actors')) == targets)
    new_components = {c['id']: c for c in ng['components']}
    collider_labels = set()
    for oc in toilets:
        label = oc['actor']
        try:
            nc = new_components[oc['id']]
            oa, osc = prior.component_state(os, oc)
            na, nsc = prior.component_state(ns, nc)
            check('only_one_render_mesh_reference_changed',
                  na == prior._expected_actor(oa, oc['mesh'], asset_row['asset'], False), label)
            check('materials_collision_and_wpo_preserved',
                  nc['mesh'] == asset_row['asset'] and
                  nc['mesh'].startswith('/Game/CodexGenerated/OldTown/Meshes/SanitaryFinish_20261012/') and
                  oc['materials'] == nc['materials'] and oc['collision'] == nc['collision'] and
                  oc.get('render_offset_cm') == nc.get('render_offset_cm') == [0., 0., 0.] and
                  osc['scale'] == nsc['scale'] == [1., 1., 1.], label)
            check('render_mesh_remains_no_collision', 'NO_COLLISION' in nsc['collision'] and
                  nsc['collision_profile'] == 'NoCollision', label)
            ov, nv = prior.local_vertices(oc, osc, 0.), prior.local_vertices(nc, nsc, 0.)
            result = audit_toilet(ov, oc['triangles'], nv, nc['triangles'], nsc, asset_row)
            for row in result['checks']:
                check(row['name'], row['passed'], label,
                      **{k: v for k, v in row.items() if k not in ('name', 'passed')})
            fixtures.append(dict(actor=label, category='Toilet', mesh=nc['mesh'],
                                 geometry_passed=result['passed'], retained_source_faces=result['retained_source_faces'],
                                 removed_source_faces=result['removed_source_faces'], new_faces=result['new_faces']))
        except (KeyError, ValueError, TypeError, IndexError) as exc:
            check('actual_saved_toilet_analysis', False, label, error=str(exc))
    for oc in basins:
        label = oc['actor']
        nc = new_components.get(oc['id'])
        check('basin_actor_state_is_completely_unchanged', os['actors'][label] == ns['actors'].get(label), label)
        check('all_actual_basin_faces_materials_and_wpo_are_exactly_unchanged', nc == oc, label)
        check('all_original_basin_faces_and_state_preserved', nc == oc and
              os['actors'][label] == ns['actors'].get(label), label)
        if 'Staff' in label:
            offset = (nc or {}).get('render_offset_cm', [])
            check('staff_basin_preserved_existing_material_render_translation', len(offset) == 3 and
                  abs(offset[0]) < 1.e-7 and abs(offset[1]-.09) < 1.e-7 and abs(offset[2]) < 1.e-7, label)
        fixtures.append(dict(actor=label, category='Washbasin', mesh=oc['mesh'], geometry_passed=nc == oc))
    for label in sorted(all_fixture_labels):
        collider = label+'_Collision0'
        collider_labels.add(collider)
        check('independent_fixture_collider_unchanged', os['actors'].get(collider) is not None and
              os['actors'][collider] == ns['actors'].get(collider), label, collision_actor=collider)
    other_changes = [name for name, state in os['actors'].items() if name not in targets and
                     ns['actors'].get(name) != state]
    check('all_7984_other_original_actor_states_preserved', len(os['actors'])-len(targets) == 7984 and
          not other_changes, checked=len(os['actors'])-len(targets), changed=other_changes[:20])
    check('exact_8014_actor_manifest_and_no_new_cameras', set(ns['actors']) == set(os['actors']) and
          len(ns['actors']) == len(os['actors']) == build.get('actor_count') == 8014 and
          refinement.get('new_cameras') == [])
    check('all_sixty_fixture_colliders_declared_and_audited', len(collider_labels) == 60 and
          prior.names(refinement.get('preserved_fixture_collision_actors')) == collider_labels)
    protected = os.get('protected_map_sha256', {})
    protected_errors = [p for p, digest in protected.items() if not Path(p).is_file() or sha(p) != digest]
    check('three_original_protected_maps_preserved_in_manifest_and_on_disk', len(protected) == 3 and
          protected == ns.get('protected_map_sha256') and not protected_errors, changed=protected_errors)
    old_references = os.get('shared_asset_sha256', {})
    file_errors = [p for p, digest in old_references.items() if not Path(p).is_file() or sha(p) != digest]
    check('all_400_source_referenced_files_unchanged_on_disk', len(old_references) == 400 and not file_errors,
          checked=len(old_references), changed=file_errors[:20])
    expected_references = deepcopy(old_references)
    sp, tp = asset_row.get('source_file'), asset_row.get('file')
    ss, ts = asset_row.get('source_sha256'), asset_row.get('sha256')
    references_valid = bool(sp and tp and ss and ts and sp != tp and expected_references.get(sp) == ss)
    if sp in expected_references:
        del expected_references[sp]
    if tp and ts:
        expected_references[tp] = ts
    check('exactly_one_owned_mesh_reference_replaced', references_valid and
          ns.get('shared_asset_sha256') == expected_references,
          expected_count=len(expected_references), actual_count=len(ns.get('shared_asset_sha256', {})))
    check('new_owned_asset_file_matches_saved_hash', tp and Path(tp).is_file() and sha(tp) == ts)
    recipe = dict(schema=finish.SCHEMA, pieces=finish.build_pieces(), removals=finish.source_removal_specs())
    normalized_recipe = core._normal_json(recipe)
    check('declared_new_recipe_matches_pure_module', core._recipe_equal(asset_row.get('shape_recipe'), normalized_recipe))
    rp, rh = refinement.get('recipe_file'), refinement.get('recipe_sha256')
    check('saved_source_art_recipe_matches_hash_and_module', rp and Path(rp).is_file() and
          sha(rp) == rh and core._recipe_equal(read(rp), normalized_recipe))
    new_count = sum(len(p['triangles']) for p in recipe['pieces'])
    check('all_new_faces_in_original_ceramic_slot_and_remaining_old_sections_preserved',
          asset_row.get('added_triangles_per_material_section') == [new_count, 0] and
          asset_row.get('retained_source_faces_verified_in_original_sections') is True)
    np = work/'FinishRenderNormals.json'
    normals = read(np) if np.is_file() else {}
    normal_rows = normals.get('assets', [])
    nr = normal_rows[0] if len(normal_rows) == 1 else {}
    normal_parts = nr.get('parts', {})
    check('fresh_render_normal_evidence_matches_exact_new_asset_hash', normals.get('map_sha256') == map_sha and
          len(normal_rows) == 1 and nr.get('asset_key') == 'Toilet' and nr.get('asset') == asset_row.get('asset') and
          nr.get('sha256') == ts)
    check('all_new_render_indices_have_correct_ue_winding', asset_row.get('render_indices_reversed') is True and
          normal_parts.get('new') == dict(positive=0, negative=new_count, zero=0))
    check('all_actual_new_render_normals_point_toward_solid_exterior',
          normal_parts.get('new_relative_to_pure_outward_cross') == dict(positive=new_count, negative=0, zero=0))
    check('all_retained_source_render_normals_keep_original_orientation',
          normal_parts.get('retained') == dict(positive=0, negative=3672, zero=0))
    check('globally_unique_check_names', len({c['name'] for c in checks}) == len(checks))
    errors = [c for c in checks if not c['passed']]
    report = dict(passed=bool(checks) and not errors, errors=errors, checks=checks, map_sha256=map_sha,
                  source_map_sha256=SOURCE_SHA,
                  statistics=dict(toilets=len(toilets), basins=len(basins), fixture_actors_audited=len(fixtures),
                                  changed_toilet_actors=len(targets), unchanged_other_original_actors=7984,
                                  unchanged_fixture_colliders=len(collider_labels), new_review_cameras=0,
                                  actors=len(ns['actors']), checks=len(checks)),
                  input_sha256={str(p): sha(p) for p in paths.values()}, input_files={k: str(p) for k, p in paths.items()},
                  normals_input_sha256={str(np): sha(np)} if np.is_file() else {}, fixtures=fixtures,
                  rebase_input_sha256={str(p): sha(p) for p in (input_path, rebase_path) if p.is_file()},
                  geometry_source='Actual saved render vertices and oriented triangle faces', units='cm',
                  coordinate_budget_components_cm=dict(world_half_step=core.WORLD_EXPORT_HALF_STEP_CM,
                      local_half_step=core.LOCAL_EXPORT_HALF_STEP_CM, transform_half_step=core.WORLD_EXPORT_HALF_STEP_CM,
                      float32=core.FLOAT32_LOCAL_BUDGET_CM), cross_runtime_recipe_float_budget_cm=1.e-10)
    output = work/'FinishGeometryAudit.json'
    if write_output:
        work.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=DEFAULT_WORK)
    parser.add_argument('--old-work', type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    report, output = analyze(args.work, args.old_work)
    print(json.dumps(dict(passed=report['passed'], statistics=report['statistics'],
                         errors=report['errors'], output=str(output)), ensure_ascii=False))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
