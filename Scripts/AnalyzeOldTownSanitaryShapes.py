"""Read-only correspondence and solid-surface audit of saved sanitary shapes.

This ordinary-Python analysis consumes saved render vertices, triangles and
actor snapshots. It never imports Unreal or edits maps or asset packages.
Source faces and new recipe faces are matched one to one by actual coordinate
errors rather than rounded signatures. Only the final audit JSON is written.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import itertools
import json
import math
from pathlib import Path

import AnalyzeOldTownSanitaryFixtures as prior
import OldTownToiletConnectionPlan as solid
import OldTownSanitaryShapePlan as shape

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK = ROOT/'Saved/CodexOutputs/SanitaryShapes_20261011'
DEFAULT_SOURCE = ROOT/'Saved/CodexOutputs/SanitaryFixtures_20261011'
SOURCE_SHA = '412d31cf4b23b5ee16cb3b9d1238dae4c1f7a990a19d6db642cf21611f7349f9'
WORLD_EXPORT_HALF_STEP_CM = .00005
LOCAL_EXPORT_HALF_STEP_CM = .00005
FLOAT32_LOCAL_BUDGET_CM = .00002
GEOMETRY_EPS_CM = .002


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _oriented_face(points):
    """Cyclic reindexing is harmless; reversing an oriented face is not."""
    p = tuple(tuple(v) for v in points)
    return min(p, p[1:]+p[:1], p[2:]+p[:2])


def _coordinate_budgets(state, expected_vertices, source_comparison=False):
    scales = state['scale']
    if source_comparison:
        # Unchanged source/new poses cancel snapshot location and scale errors.
        # Each world export has a half-step error in a 0.0001 cm output grid.
        return [2*WORLD_EXPORT_HALF_STEP_CM/abs(s)+1.e-10 for s in scales]
    extent = [max(abs(p[j]) for p in expected_vertices) for j in range(3)]
    # Expected recipe points are exact local coordinates. The inverse uses a
    # four-decimal snapshot scale/location; propagate that rounding separately
    # from the world-vertex export and StaticMesh float32 quantization.
    return [((2+extent[j])*WORLD_EXPORT_HALF_STEP_CM)/abs(scales[j])+
            LOCAL_EXPORT_HALF_STEP_CM+FLOAT32_LOCAL_BUDGET_CM for j in range(3)]


def _match_faces(expected_v, expected_t, actual_v, actual_t, budgets):
    """Bijective position matching followed by oriented face multiplicity.

    A candidate is accepted only when every coordinate has a measured error
    inside the declared budget. Integer cells index nearby candidates; they
    are never a rounded equality test. Actual geometry is kept unmodified for
    every subsequent winding, ray, topology and volume calculation.
    """
    points = {tuple(actual_v[i]) for t in actual_t for i in t}
    pool = {}
    for p in points:
        cell = tuple(math.floor(p[j]/budgets[j]) for j in range(3))
        pool.setdefault(cell, []).append(p)
    expected_points = {tuple(expected_v[i]) for t in expected_t for i in t}
    correspondence, reverse, failures = {}, {}, []
    maximum = [0., 0., 0.]
    for p in sorted(expected_points):
        cell = tuple(math.floor(p[j]/budgets[j]) for j in range(3))
        candidates = []
        for delta in itertools.product((-1, 0, 1), repeat=3):
            for q in pool.get(tuple(cell[j]+delta[j] for j in range(3)), ()):
                if all(abs(p[j]-q[j]) <= budgets[j] for j in range(3)):
                    candidates.append(q)
        distance = lambda q: sum((p[j]-q[j])**2 for j in range(3))
        candidates.sort(key=distance)
        ambiguous = len(candidates) > 1 and abs(distance(candidates[0])-
                                               distance(candidates[1])) < 1.e-20
        if not candidates or ambiguous or candidates[0] in reverse:
            failures.append(dict(expected_cm=p, candidates=len(candidates),
                                 nearest_ambiguous=ambiguous,
                                 reused_actual=bool(candidates and candidates[0] in reverse)))
            continue
        q = candidates[0]
        correspondence[p], reverse[q] = q, p
        maximum = [max(maximum[j], abs(p[j]-q[j])) for j in range(3)]
    wanted = Counter()
    if not failures:
        wanted.update(_oriented_face([correspondence[tuple(expected_v[i])] for i in t])
                      for t in expected_t)
    matched, remaining = [], []
    for t in actual_t:
        signature = _oriented_face([actual_v[i] for i in t])
        if wanted[signature] > 0:
            matched.append(t)
            wanted[signature] -= 1
        else:
            remaining.append(t)
    missing = sum(wanted.values()) if not failures else len(expected_t)
    proof = dict(passed=not failures and missing == 0,
                 expected_faces=len(expected_t), matched_faces=len(matched),
                 missing_faces=missing, expected_unique_positions=len(expected_points),
                 matched_unique_positions=len(correspondence),
                 max_actual_coordinate_error_cm=maximum,
                 per_axis_coordinate_error_budget_cm=budgets,
                 position_failures=failures[:12])
    return matched, remaining, proof


def _topology(vertices, triangles, expected_orientation=-1):
    points, edges, directions = set(), Counter(), Counter()
    degenerate, volume = 0, 0.
    for t in triangles:
        pp = [tuple(vertices[i]) for i in t]
        points.update(pp)
        normal = solid._cross([pp[1][j]-pp[0][j] for j in range(3)],
                              [pp[2][j]-pp[0][j] for j in range(3)])
        degenerate += solid._dot(normal, normal) < 1.e-16
        for j in range(3):
            a, b = pp[j], pp[(j+1) % 3]
            edges[tuple(sorted((a, b)))] += 1
            directions[(a, b)] += 1
        volume += solid._dot(pp[0], solid._cross(pp[1], pp[2]))/6
    closed = bool(edges) and all(v == 2 for v in edges.values())
    oriented = all(directions[(a, b)] == directions[(b, a)] for a, b in edges)
    euler = len(points)-len(edges)+len(triangles)
    return dict(passed=closed and oriented and euler == 2 and degenerate == 0 and
                volume*expected_orientation > 1.e-8, closed=closed, consistently_oriented=oriented,
                euler=euler, degenerate_triangles=degenerate,
                triangle_count=len(triangles), signed_volume_cm3=volume,
                expected_index_orientation=expected_orientation)


def _ray_hits(point, direction, vertices, triangles):
    """Moller-Trumbore intersections, retaining actual unrounded triangles."""
    hits = []
    for t in triangles:
        a, b, c = [vertices[i] for i in t]
        e1, e2 = [[q[j]-a[j] for j in range(3)] for q in (b, c)]
        h = solid._cross(direction, e2)
        det = solid._dot(e1, h)
        if abs(det) < 1.e-12:
            continue
        s = [point[j]-a[j] for j in range(3)]
        u = solid._dot(s, h)/det
        q = solid._cross(s, e1)
        v = solid._dot(direction, q)/det
        distance = solid._dot(e2, q)/det
        if u >= -1.e-10 and v >= -1.e-10 and u+v <= 1+1.e-10 and distance > 1.e-8:
            hits.append(distance)
    hits.sort()
    unique = []
    for distance in hits:
        if not unique or abs(distance-unique[-1]) > 1.e-5:
            unique.append(distance)
    return unique


def _bounds_same(a, b):
    return all(abs(x-y) <= GEOMETRY_EPS_CM for aa, bb in zip(a, b)
               for x, y in zip(aa, bb))


def _part_by_bounds(vertices, triangles, bounds, name):
    matches = [group for group in solid._groups(vertices, triangles)
               if _bounds_same(solid._bounds(vertices, group), bounds)]
    if len(matches) != 1:
        raise ValueError('Expected one source island for '+name+': '+str(len(matches)))
    return matches[0]


def _recipe(asset_key):
    # Kept in one adapter so the independent audit does not call the module's
    # own audit function or borrow its pass/fail conclusions.
    return [p for p in shape.build_pieces() if p['fixture'] == asset_key]


def _normal_json(value):
    return json.loads(json.dumps(value))


def _recipe_equal(actual, expected):
    """Same schema/indices with bounded cross-Python libm/sum roundoff only.

    UE's Python and the ordinary audit runtime evaluate ring-centre sums with
    slightly different floating-point summation implementations. The observed
    difference is about 1e-14 cm. This 1e-10 cm budget covers that arithmetic
    and is orders of magnitude smaller than any saved render export step.
    Integer triangle indices, categorical fields and structures remain exact.
    """
    if isinstance(actual, float) and isinstance(expected, float):
        return math.isfinite(actual) and math.isfinite(expected) and abs(actual-expected) <= 1.e-10
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(_recipe_equal(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(_recipe_equal(a, e) for a, e in zip(actual, expected))
    return actual == expected


def _profile_at_z(profiles, z):
    profiles = sorted(profiles, key=lambda row: row[1])
    for first, last in zip(profiles, profiles[1:]):
        if first[1]-1.e-10 <= z <= last[1]+1.e-10:
            fraction = (z-first[1])/(last[1]-first[1])
            return [first[i]+fraction*(last[i]-first[i]) for i in range(4)]
    raise ValueError('No profile brackets z='+str(z))


def _retained_solid_parts(asset_key, vertices, triangles):
    if asset_key == 'Toilet':
        boxes = dict(
            Pedestal=[[-21.4, -11.2, 0.], [9.4, 11.2, 32.]],
            Seat=[[-32.01, -17.7, 40.3], [14.01, 17.7, 42.7]],
            RearCeramicPedestal=[[1., -9., 0.], [25., 9., 31.]])
        result = {name: _part_by_bounds(vertices, triangles, box, name)
                  for name, box in boxes.items()}
        # Historical cistern separation creates 22 disconnected patches. All
        # existing retained faces above the tank bottom form its actual test
        # surface, exactly as in the source audit; they are never resealed.
        result['Cistern'] = [t for t in triangles if
                             min(vertices[i][2] for i in t) >= 45.-GEOMETRY_EPS_CM]
        return result
    boxes = dict(
        FaucetSleeve=[[14.7, -1.3, 84.4], [17.3, 1.3, 94.]],
        FaucetAerator=[[2.9, -1.1, 89.125], [5.1, 1.1, 89.975]])
    return {name: _part_by_bounds(vertices, triangles, box, name)
            for name, box in boxes.items()}


def _audit_geometry(asset_key, before_v, before_t, after_v, after_t, state, asset_row):
    """Actual-face retention, complete recipe correspondence and solid tests."""
    checks = []

    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))

    recipe = _recipe(asset_key)
    reversed_for_render = asset_row.get('render_indices_reversed') is True
    check('outward_recipe_indices_explicitly_reversed_for_ue_render', reversed_for_render)
    removed = [r for r in shape.source_removal_specs() if r['fixture'] == asset_key]
    check('declared_removed_source_parts_match_recipe',
          asset_row.get('removed_part_names') == [r['name'] for r in removed])
    removed_ids, removed_parts = set(), {}
    for row in removed:
        part = _part_by_bounds(before_v, before_t, row['bounds_cm'], row['name'])
        removed_parts[row['name']] = part
        removed_ids.update(tuple(t) for t in part)
        check('source_removal_'+row['name']+'_present_once', len(part) == row['triangles'],
              faces=len(part), expected_faces=row['triangles'])
    retained = [t for t in before_t if tuple(t) not in removed_ids]
    retained_after, added_after, match = _match_faces(
        before_v, retained, after_v, after_t,
        _coordinate_budgets(state, before_v, source_comparison=True))
    check('all_retained_source_faces_match_one_to_one', match.pop('passed'), **match)
    check('at_least_one_source_face_retained', bool(retained))
    pieces, unmatched = {}, added_after
    for piece in recipe:
        rv, rt = piece['vertices'], piece['triangles']
        expected_rt = [[t[0], t[2], t[1]] for t in rt] if reversed_for_render else rt
        actual, unmatched, match = _match_faces(rv, expected_rt, after_v, unmatched,
                                              _coordinate_budgets(state, rv))
        check(piece['name']+'_all_prescribed_faces_present', match.pop('passed'), **match)
        pieces[piece['name']] = actual
        topology = _topology(after_v, actual, -1 if reversed_for_render else 1)
        check(piece['name']+'_actual_closed_oriented_solid', topology.pop('passed'), **topology)
    check('no_unprescribed_added_or_removed_faces', not unmatched and
          len(retained_after)+sum(len(t) for t in pieces.values()) == len(after_t),
          unprescribed_faces=len(unmatched), actual_faces=len(after_t))
    check('entire_original_fixture_envelope_preserved', _bounds_same(
          solid._bounds(before_v, before_t), solid._bounds(after_v, after_t)),
          before_bounds_cm=solid._bounds(before_v, before_t),
          after_bounds_cm=solid._bounds(after_v, after_t))
    # Source connection witnesses refer to existing retained solids. Recipes
    # explicitly describe the relevant source part boxes, rather than relying
    # on a whole-asset bounding box to stand in for occupied material.
    pieces.update(_retained_solid_parts(asset_key, after_v, retained_after))
    for witness in shape.CONNECTION_WITNESSES:
        if not any(name in [p['name'] for p in recipe] for name in witness['parts']):
            continue
        actual_inside = {name: solid._inside(witness['point'], after_v, pieces[name])
                         for name in witness['parts'] if name in pieces}
        check('solid_connection_'+witness['name'], len(actual_inside) == len(witness['parts'])
              and all(actual_inside.values()), actual_inside_parts=actual_inside,
              witness_local_cm=witness['point'])
    if asset_key == 'Toilet':
        bowl = pieces['HollowCeramicBowl']
        for index, point in enumerate(shape.CAVITY_EMPTY_WITNESSES):
            inside_parts = {name: solid._inside(point, after_v, part)
                            for name, part in pieces.items()}
            check('empty_cavity_point_'+str(index), not any(inside_parts.values()),
                  point_local_cm=point, actual_inside_parts=inside_parts)
        for index, point in enumerate(([-9., 0., 41.], [-11., 0., 41.],
                                        [-7., 0., 41.], [-9., 1., 41.])):
            actual_hits = _ray_hits(point, [0., 0., -1.], after_v, bowl)
            expected_hits = [7.5, 16.]
            good = len(actual_hits) == len(expected_hits) and all(
                abs(x-y) <= GEOMETRY_EPS_CM for x, y in zip(actual_hits, expected_hits))
            check('actual_cavity_down_ray_'+str(index), good, actual_distances_cm=actual_hits,
                  expected_distances_cm=expected_hits, point_local_cm=point,
                  floor_thickness_cm=actual_hits[1]-actual_hits[0] if len(actual_hits) == 2 else None)
        for index, point in enumerate(([-9., 0., 29.], [-29., 0., 38.],
                                       [11., 0., 38.], [-9., 15., 38.], [-9., -15., 38.])):
            check('actual_ceramic_shell_solid_'+str(index), solid._inside(point, after_v, bowl),
                  point_local_cm=point)
        foot_tops = {name: solid._bounds(after_v, pieces[name])[1][2]
                     for name in ('Pedestal', 'RearCeramicPedestal')}
        floor_z = min(row[1] for row in shape.BOWL_INNER)
        check('actual_existing_feet_remain_below_cavity_floor',
              all(top < floor_z-GEOMETRY_EPS_CM for top in foot_tops.values()),
              inner_floor_z_cm=floor_z, actual_foot_top_z_cm=foot_tops,
              gap_cm={name: floor_z-top for name, top in foot_tops.items()})
        breakpoints = sorted({row[1] for row in shape.BOWL_INNER+shape.SHOULDER
                              if floor_z <= row[1] <= 40.7})
        gaps = []
        for z in breakpoints:
            inner = _profile_at_z(shape.BOWL_INNER, z)
            shoulder = _profile_at_z(shape.SHOULDER, z)
            gaps.append(dict(z_cm=z, shoulder_front_x_cm=shoulder[0]-shoulder[2],
                             inner_rear_x_cm=inner[0]+inner[2],
                             clearance_cm=shoulder[0]-shoulder[2]-inner[0]-inner[2]))
        # Both profiles are linear between their combined breakpoints. At a
        # given height the shoulder's smallest X occurs at Y=0, as does the
        # cavity's largest X. Positive gaps at all breakpoints prove the whole
        # prescribed shoulder stays behind the cup. The actual full-face
        # correspondence above is a prerequisite for this analytic conclusion.
        actual_shape_matched = all(q['passed'] for q in checks
                                   if q['name'].endswith('_all_prescribed_faces_present'))
        check('actual_rear_shoulder_cannot_intrude_into_inner_cup', actual_shape_matched and
              bool(gaps) and all(row['clearance_cm'] > 0.01 for row in gaps),
              combined_linear_profile_breakpoints=gaps,
              min_clearance_cm=min(row['clearance_cm'] for row in gaps))
    return dict(passed=bool(checks) and all(q['passed'] for q in checks), checks=checks,
                retained_source_faces=len(retained), removed_source_faces=len(removed_ids),
                added_recipe_faces=sum(len(p['triangles']) for p in recipe))


def analyze(work=DEFAULT_WORK, old_work=DEFAULT_SOURCE, write_output=True):
    work, old_work = Path(work).resolve(), Path(old_work).resolve()
    paths = dict(newGeo=work/'GeometryAfter.json', newSnapshot=work/'AfterSnapshot.json',
                 newBuild=work/'BuildReport.json', oldGeo=old_work/'GeometryAfter.json',
                 oldSnapshot=old_work/'AfterSnapshot.json')
    ng, ns, build, og, os = [read(p) for p in paths.values()]
    map_sha = build['map_sha256']
    refinement = build.get('sanitary_shape_refinement', {})
    checks, rows = [], []

    def check(name, passed, actor=None, **details):
        identity = actor if actor is not None else details.get('mesh')
        full_name = identity+':'+name if identity is not None else name
        row = dict(name=full_name, passed=bool(passed), **details)
        if actor is not None:
            row['actor'] = actor
        checks.append(row)

    check('fresh_new_saved_exports', ng['map_sha256'] == ns['source_map_sha256'] == map_sha
          and bool(ns.get('passed')) and build.get('status') == 'PASS')
    check('expected_source_saved_baseline', og['map_sha256'] == os['source_map_sha256'] == SOURCE_SHA)
    check('build_source_matches_baseline', build.get('source_map_sha256') == SOURCE_SHA)
    assets = refinement.get('new_assets', [])
    asset_rows = {row['asset_key']: row for row in assets}
    check('exactly_toilet_and_washbasin_asset_rows', len(assets) == 2 and
          set(asset_rows) == {'Toilet', 'Washbasin'})
    recipe_file, recipe_hash = refinement.get('recipe_file'), refinement.get('recipe_sha256')
    expected_full_recipe = _normal_json(dict(schema=shape.SCHEMA, pieces=shape.build_pieces(),
                                            removals=shape.source_removal_specs()))
    check('saved_full_recipe_file_matches_hash_and_pure_module', recipe_file and
          Path(recipe_file).is_file() and sha(recipe_file) == recipe_hash and
          _recipe_equal(read(recipe_file), expected_full_recipe))
    normals_path = work/'ShapeRenderNormals.json'
    normals = read(normals_path) if normals_path.is_file() else {}
    normal_rows = {row.get('asset_key'): row for row in normals.get('assets', [])}
    check('fresh_current_saved_render_normal_evidence', normals.get('map_sha256') == map_sha and
          len(normals.get('assets', [])) == 2 and set(normal_rows) == {'Toilet', 'Washbasin'})
    components = {c['id']: c for c in ng['components']}
    scoped = {key: [c for c in og['components'] if c['mesh'] == row['source']]
              for key, row in asset_rows.items()}
    targets = {c['actor'] for cs in scoped.values() for c in cs}
    check('sixty_distinct_existing_fixture_actors', len(targets) == 60, actual=len(targets))
    check('declared_modified_actors_match_scope', prior.names(refinement.get('changed_actors')) == targets)
    collider_labels = set()
    for asset_key, source_components in scoped.items():
        check('thirty_existing_'+asset_key+'_components', len(source_components) == 30,
              actual=len(source_components))
        asset_row = asset_rows[asset_key]
        for oc in source_components:
            label = oc['actor']
            try:
                nc = components[oc['id']]
                oa, osc = prior.component_state(os, oc)
                na, nsc = prior.component_state(ns, nc)
                expected = prior._expected_actor(oa, oc['mesh'], asset_row['asset'], False)
                check('only_permitted_render_mesh_changes', na == expected, label)
                check('exact_declared_new_owned_render_mesh', nc['mesh'] == asset_row['asset'] and
                      nc['mesh'].startswith('/Game/CodexGenerated/OldTown/Meshes/SanitaryShapes_20261011/')
                      and nc['mesh'] != oc['mesh'], label, mesh=nc['mesh'])
                check('materials_collision_and_wpo_preserved', oc['materials'] == nc['materials']
                      and oc['collision'] == nc['collision'] and
                      oc.get('render_offset_cm', [0., 0., 0.]) == nc.get('render_offset_cm', [0., 0., 0.])
                      and oc.get('wpo_verified_from_persisted_material') ==
                          nc.get('wpo_verified_from_persisted_material')
                      and oc.get('world_transform_negative_determinant') ==
                          nc.get('world_transform_negative_determinant'), label)
                check('render_remains_no_collision', 'NO_COLLISION' in nsc['collision'] and
                      nsc['collision_profile'] == 'NoCollision', label)
                if asset_key == 'Washbasin' and 'Staff' in label:
                    offset = nc.get('render_offset_cm', [])
                    check('staff_basin_existing_wpo_accounted_for', len(offset) == 3 and
                          abs(offset[0]) < 1.e-7 and abs(offset[1]-.09) < 1.e-7 and
                          abs(offset[2]) < 1.e-7, label, world_render_offset_cm=offset)
                collider = label+'_Collision0'
                collider_labels.add(collider)
                check('independent_fixture_collider_unchanged', os['actors'].get(collider) is not None
                      and os['actors'][collider] == ns['actors'].get(collider), label,
                      collision_actor=collider)
                ov, nv = prior.local_vertices(oc, osc, 0.), prior.local_vertices(nc, nsc, 0.)
                result = _audit_geometry(asset_key, ov, oc['triangles'], nv,
                                         nc['triangles'], nsc, asset_row)
                for row in result['checks']:
                    check(row['name'], row['passed'], label,
                          **{k: v for k, v in row.items() if k not in ('name', 'passed')})
                rows.append(dict(actor=label, asset_key=asset_key, mesh=nc['mesh'],
                                 geometry_passed=result['passed'],
                                 retained_source_faces=result['retained_source_faces'],
                                 removed_source_faces=result['removed_source_faces'],
                                 added_recipe_faces=result['added_recipe_faces']))
            except (KeyError, ValueError, IndexError, TypeError) as exc:
                check('actual_saved_fixture_analysis', False, label, error=str(exc))
    other_changed = [label for label, state in os['actors'].items() if label not in targets
                     and ns['actors'].get(label) != state]
    check('all_7952_other_original_actors_unchanged', not other_changed and
          len(os['actors'])-len(targets) == 7952,
          checked=len(os['actors'])-len(targets), changed=other_changed[:30])
    check('sixty_independent_fixture_colliders_audited', len(collider_labels) == 60,
          actual=len(collider_labels))
    added, removed = set(ns['actors'])-set(os['actors']), set(os['actors'])-set(ns['actors'])
    check('exactly_two_new_review_cameras_no_actor_removal', len(added) == 2 and not removed and
          added == prior.names(refinement.get('new_cameras')) and
          all(ns['actors'][label]['class'] == '/Script/Engine.CameraActor' for label in added),
          actual=sorted(added), removed=sorted(removed))
    check('protected_map_manifests_preserved',
          os.get('protected_map_sha256') == ns.get('protected_map_sha256'))
    protected_maps = os.get('protected_map_sha256', {})
    protected_errors = [p for p, digest in protected_maps.items()
                        if not Path(p).is_file() or sha(p) != digest]
    check('all_three_protected_maps_unchanged_on_disk', len(protected_maps) == 3 and
          not protected_errors, changed=protected_errors)
    old_references = os.get('shared_asset_sha256', {})
    old_file_errors = [p for p, digest in old_references.items()
                       if not Path(p).is_file() or sha(p) != digest]
    check('all_400_source_referenced_files_unchanged_on_disk', len(old_references) == 400 and
          not old_file_errors, checked=len(old_references), changed=old_file_errors[:20])
    expected_references = deepcopy(old_references)
    reference_rows_valid = len(assets) == 2
    for row in assets:
        sp, tp = row.get('source_file'), row.get('file')
        ss, ts = row.get('source_sha256'), row.get('sha256')
        reference_rows_valid &= bool(sp and tp and ss and ts and sp != tp)
        reference_rows_valid &= expected_references.get(sp) == ss
        if sp in expected_references:
            del expected_references[sp]
        if tp and ts:
            expected_references[tp] = ts
        check('new_render_asset_saved_hash_matches', tp and Path(tp).is_file() and
              sha(tp) == ts, mesh=row.get('asset'), file=tp)
        sections = row.get('added_triangles_per_material_section', [])
        expected_added = sum(len(p['triangles']) for p in _recipe(row['asset_key']))
        check('actual_saved_new_faces_only_in_material_slot_zero', sections == [expected_added, 0]
              and row.get('retained_source_faces_verified_in_original_sections') is True,
              mesh=row.get('asset'), added_triangles_per_material_section=sections,
              expected_added_faces=expected_added)
        normal_row = normal_rows.get(row['asset_key'], {})
        normal_parts = normal_row.get('parts', {})
        raw = normal_parts.get('new', {})
        outward = normal_parts.get('new_relative_to_pure_outward_cross', {})
        check('new_render_normal_evidence_matches_current_asset_file',
              normal_row.get('asset') == row.get('asset') and
              normal_row.get('sha256', normal_row.get('asset_sha256')) == ts,
              mesh=row.get('asset'))
        check('new_render_indices_and_normals_have_consistent_ue_winding',
              row.get('render_indices_reversed') is True and raw ==
              dict(positive=0, negative=expected_added, zero=0),
              mesh=row.get('asset'), actual_raw_index_cross_dot_normal=raw)
        check('all_new_render_normals_point_toward_actual_solid_exterior',
              outward == dict(positive=expected_added, negative=0, zero=0),
              mesh=row.get('asset'), actual_pure_outward_cross_dot_normal=outward)
        check('declared_shape_recipe_matches_immutable_module',
              _recipe_equal(row.get('shape_recipe'), _normal_json(dict(schema=shape.SCHEMA,
                  pieces=_recipe(row['asset_key']), removals=[r for r in shape.source_removal_specs()
                                                           if r['fixture'] == row['asset_key']]))),
              mesh=row.get('asset'))
    check('only_two_render_clone_file_references_replaced', reference_rows_valid and
          ns.get('shared_asset_sha256') == expected_references,
          expected_count=len(expected_references), actual_count=len(ns.get('shared_asset_sha256', {})))
    check('globally_unique_check_names', len({q['name'] for q in checks}) == len(checks))
    errors = [q for q in checks if not q['passed']]
    report = dict(passed=bool(checks) and not errors, errors=errors, checks=checks,
                  map_sha256=map_sha, source_map_sha256=SOURCE_SHA,
                  statistics=dict(toilets=len(scoped.get('Toilet', [])),
                                  basins=len(scoped.get('Washbasin', [])), checks=len(checks),
                                  fixture_actors_audited=len(rows),
                                  unchanged_other_original_actors=7952,
                                  unchanged_fixture_colliders=len(collider_labels),
                                  new_review_cameras=len(added)),
                  input_sha256={str(p): sha(p) for p in paths.values()},
                  input_files={k: str(p) for k, p in paths.items()}, fixtures=rows,
                  normals_input_sha256={str(normals_path): sha(normals_path)} if normals_path.is_file() else {},
                  geometry_source='Actual persisted rendered vertices and oriented faces',
                  source_face_coordinate_budget='2 world half steps divided by unchanged scale',
                  recipe_coordinate_budget='world/local and transform four-decimal export errors plus float32',
                  coordinate_budget_components_cm=dict(world_export_half_step=WORLD_EXPORT_HALF_STEP_CM,
                      local_export_half_step=LOCAL_EXPORT_HALF_STEP_CM,
                      transform_export_half_step=WORLD_EXPORT_HALF_STEP_CM,
                      static_mesh_float32=FLOAT32_LOCAL_BUDGET_CM),
                  units='cm')
    output = work/'ShapeGeometryAudit.json'
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
