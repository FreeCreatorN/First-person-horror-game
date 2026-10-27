"""Independent saved-geometry audit of 30 toilets and 30 hotel washbasins.

Ordinary Python only: reads persisted GeometryAfter, AfterSnapshot, BuildReport;
does not import Unreal or edit assets/maps. Writes FixtureGeometryAudit.json.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import AnalyzeOldTownBasinConnections as basin
import OldTownFaucetDetailPlan as faucet
import OldTownToiletConnectionPlan as toilet

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK = ROOT/'Saved/CodexOutputs/SanitaryFixtures_20261011'
DEFAULT_SOURCE = ROOT/'Saved/CodexOutputs/BasinConnections_20261011'
SOURCE_SHA = '684f1f0533cef3ab50b6c7e3b270cb0a4dab924b839139e5d9a8e2048503f33d'
EPS = .002
# Each world export rounds to 0.0001 cm. Two exports can therefore differ
# by 0.0001 cm per coordinate; 1e-10 cm covers inverse-transform arithmetic.
# The toilets use only cardinal yaw and unit scale, checked separately below.
SOURCE_FACE_COORDINATE_BUDGET_CM = .0001 + 1.e-10


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def names(value):
    if isinstance(value, dict):
        return set(value)
    if not isinstance(value, list):
        return set()
    return {v if isinstance(v, str) else v.get('actor', v.get('camera', v.get('label')))
            for v in value} - {None}


def component_state(snapshot, component):
    actor = snapshot['actors'][component['actor']]
    cs = [c for c in actor['components'] if c['name'] == component['component']]
    if len(cs) != 1:
        raise ValueError('Component absent or ambiguous: '+component['id'])
    return actor, cs[0]


def local_vertices(component, state, expected_yaw):
    rotation = state['rotation']
    if any(abs(a-b) > 1.e-5 for a, b in zip(rotation, [0., expected_yaw, 0.])):
        raise ValueError('Unexpected fixture rotation: %r' % rotation)
    scale = state['scale']
    if any(v <= 0 or not math.isfinite(v) for v in scale):
        raise ValueError('Unexpected fixture scale')
    offset = component.get('render_offset_cm', [0., 0., 0.])
    if len(offset) != 3 or not all(math.isfinite(v) for v in offset):
        raise ValueError('Invalid render translation')
    pos = state['location']
    cosine, sine = math.cos(math.radians(expected_yaw)), math.sin(math.radians(expected_yaw))
    result = []
    for p in component['vertices']:
        q = [p[i]-pos[i]-offset[i] for i in range(3)]
        result.append([(q[0]*cosine+q[1]*sine)/scale[0],
                       (-q[0]*sine+q[1]*cosine)/scale[1], q[2]/scale[2]])
    return result


def _expected_actor(old, old_mesh, new_mesh, rotate):
    expected = deepcopy(old)
    if rotate:
        expected['rotation'] = [0., 0., 0.]
    found = 0
    for c in expected['components']:
        if c.get('mesh') == old_mesh:
            c['mesh'] = new_mesh
            if rotate:
                c['rotation'] = [0., 0., 0.]
            found += 1
    if found != 1:
        raise ValueError('Expected one fixture render component')
    return expected


def _primitive_axis(spec):
    axis = spec['axis']
    ai = max(range(3), key=lambda j: abs(axis[j]))
    if any(abs(axis[j]-(1. if j == ai else 0.)) > 1.e-6 for j in range(3)):
        raise ValueError('This audit explicitly accepts positive cardinal axes only')
    return ai, [j for j in range(3) if j != ai]


def _primitive_bounds(spec):
    ai, _ = _primitive_axis(spec)
    ext = [spec['radius']]*3
    ext[ai] = spec['height']/2
    return [[spec['center'][j]-ext[j] for j in range(3)],
            [spec['center'][j]+ext[j] for j in range(3)]]


def _same_bounds(actual, expected):
    return all(abs(a-b) <= EPS for aa, bb in zip(actual, expected)
               for a, b in zip(aa, bb))


def _closed_cylinder(vertices, triangles, spec):
    """Cardinal-axis cylinder surface/topology/solid volume checks.

    Supports native GeometryScript triangulation and split cap normals. No
    reliance on labels, bounds alone, vertex count, or a particular cap fan.
    """
    ai, radial = _primitive_axis(spec)
    center, radius, half = spec['center'], spec['radius'], spec['height']/2
    edges, directions, points = Counter(), Counter(), set()
    surfaces = True
    volume = 0.
    for triangle in triangles:
        ps = [vertices[i] for i in triangle]
        kk = [toilet._key(p) for p in ps]
        points.update(kk)
        for j in range(3):
            a, b = kk[j], kk[(j+1) % 3]
            edges[tuple(sorted((a, b)))] += 1
            directions[(a, b)] += 1
        cap = any(all(abs(p[ai]-center[ai]-sign*half) <= EPS for p in ps)
                  for sign in (-1, 1))
        side = all(abs(sum(((p[j]-center[j])/radius)**2 for j in radial)-1.) < .002
                   and abs(p[ai]-center[ai]) <= half+EPS for p in ps)
        surfaces &= cap or side
        # Subtract the primitive centre to limit roundoff for large world frames.
        q = [[p[j]-center[j] for j in range(3)] for p in ps]
        volume += toilet._dot(q[0], toilet._cross(q[1], q[2]))/6
    closed = bool(edges) and all(v == 2 for v in edges.values()) and all(
        directions[(a, b)] == directions[(b, a)] for a, b in edges)
    euler = len(points)-len(edges)+len(triangles)
    n = spec['radial_sides']
    expected_volume = .5*n*math.sin(2*math.pi/n)*radius*radius*spec['height']
    actual_bounds = toilet._bounds(vertices, triangles)
    volume_error = abs(abs(volume)-expected_volume)
    good = closed and euler == 2 and surfaces and volume_error < .012 and _same_bounds(
        actual_bounds, _primitive_bounds(spec))
    return dict(passed=bool(good), closed=closed, euler=euler,
                bounds_cm=actual_bounds, expected_bounds_cm=_primitive_bounds(spec),
                actual_surface_equations_match=bool(surfaces),
                triangle_count=len(triangles), volume_cm3=abs(volume),
                expected_volume_cm3=expected_volume, volume_error_cm3=volume_error)


def _match_toilet_original_faces(before_v, before_t, after_v, after_t):
    """Match prescribed source faces one to one using actual coordinate error.

    Rounding a local coordinate to three decimals is not a valid error test:
    sin(pi) can put identical 3.3845 cm points on opposite rounding boundaries.
    This correspondence instead verifies each coordinate within the explicit
    export budget, then compares face multiplicity with exact actual positions.
    All subsequent topology, bounds, and solid tests use unmodified after_v.
    """
    expected = toilet.expected_original_vertices(before_v)
    budget = SOURCE_FACE_COORDINATE_BUDGET_CM
    buckets = {}
    actual_points = {tuple(p) for p in after_v}
    for p in actual_points:
        cell = tuple(math.floor(v/budget) for v in p)
        buckets.setdefault(cell, []).append(p)
    correspondence, reverse, failures = {}, {}, []
    maximum_error = 0.
    for p in {tuple(v) for v in expected}:
        cell = tuple(math.floor(v/budget) for v in p)
        candidates = []
        for x in (-1, 0, 1):
            for y in (-1, 0, 1):
                for z in (-1, 0, 1):
                    for q in buckets.get((cell[0]+x, cell[1]+y, cell[2]+z), ()):
                        if all(abs(p[j]-q[j]) <= budget for j in range(3)):
                            candidates.append(q)
        # Prior cistern separation leaves some real source vertices 0.0001 cm
        # apart. Require a unique nearest correspondence rather than mistaking
        # that retained neighbour for ambiguity anywhere in the error budget.
        distance_squared = lambda q: sum((p[j]-q[j])**2 for j in range(3))
        candidates.sort(key=distance_squared)
        ambiguous = len(candidates) > 1 and abs(distance_squared(candidates[0])-
                                               distance_squared(candidates[1])) <= 1.e-20
        if not candidates or ambiguous or candidates[0] in reverse:
            failures.append(dict(expected_local_cm=p, candidates=len(candidates),
                                 nearest_match_ambiguous=ambiguous,
                                 reused_actual_point=bool(candidates and candidates[0] in reverse)))
            continue
        q = candidates[0]
        correspondence[p], reverse[q] = q, p
        maximum_error = max(maximum_error, *(abs(p[j]-q[j]) for j in range(3)))
    proof = dict(passed=not failures,
                 expected_unique_positions=len({tuple(v) for v in expected}),
                 matched_unique_positions=len(correspondence),
                 max_actual_coordinate_error_cm=maximum_error,
                 coordinate_error_budget_cm=budget, failures=failures[:20])
    if failures:
        return [], list(after_t), len(before_t), proof
    expected_faces = Counter(tuple(sorted(correspondence[tuple(expected[i])] for i in t))
                             for t in before_t)
    original, added = [], []
    for t in after_t:
        signature = tuple(sorted(tuple(after_v[i]) for i in t))
        if expected_faces[signature] > 0:
            expected_faces[signature] -= 1
            original.append(t)
        else:
            added.append(t)
    return original, added, sum(expected_faces.values()), proof


def audit_toilet(before_v, before_t, after_v, after_t):
    """Same prescribed solids and witnesses, with verified source correspondence."""
    checks = []

    def check(name, passed, **details):
        checks.append(dict(id=name, passed=bool(passed), **details))

    original, added, missing, proof = _match_toilet_original_faces(
        before_v, before_t, after_v, after_t)
    check('source_positions_match_one_to_one_within_export_error', proof.pop('passed'), **proof)
    check('only_bowl_top_changed_original_faces_retained', missing == 0,
          lifted_split_vertices=len(toilet.bowl_top_vertex_ids(before_v)),
          missing_original_faces=missing, original_face_count=len(before_t),
          matched_original_faces=len(original))
    groups = toilet._groups(after_v, added) if added else []
    check('exactly_two_added_closed_supports', len(groups) == 2, actual=len(groups))
    pieces = {}
    for spec in toilet.primitive_specs():
        expected_bounds = [
            [spec['center'][0]-spec['radii'][0], spec['center'][1]-spec['radii'][1],
             spec['center'][2]-spec['height']/2],
            [spec['center'][0]+spec['radii'][0], spec['center'][1]+spec['radii'][1],
             spec['center'][2]+spec['height']/2]]
        candidates = [ts for ts in groups if _same_bounds(toilet._bounds(after_v, ts),
                                                        expected_bounds)]
        check(spec['name']+':present_once', len(candidates) == 1, actual=len(candidates))
        if len(candidates) == 1:
            pieces[spec['name']] = candidates[0]
            row = toilet._closed_primitive(after_v, candidates[0], spec)
            row.pop('name')
            check(spec['name']+':closed_prescribed_geometry', row.pop('passed'), **row)
    actual_bounds = toilet._bounds(after_v, after_t)
    check('entire_old_envelope_retained', _same_bounds(actual_bounds, toilet.LOCAL_ENVELOPE),
          actual_cm=actual_bounds)
    if missing == 0:
        pieces.update(toilet._original_parts(after_v, original, True))
    for witness in toilet.CONNECTION_WITNESSES:
        have = all(p in pieces for p in witness['parts'])
        result = {p: toilet._inside(witness['point'], after_v, pieces[p])
                  for p in witness['parts']} if have else {}
        check(witness['name'], have and all(result.values()),
              witness_local_cm=witness['point'], actual_inside_parts=result)
    if 'RearCeramicPedestal' in pieces:
        ground = toilet._bounds(after_v, pieces['RearCeramicPedestal'])[0][2]
        check('rear_support_has_actual_floor_plane_contact', abs(ground) <= EPS,
              bottom_local_cm=ground, contact_local_cm=[13., 0., 0.])
    return dict(passed=all(q['passed'] for q in checks), checks=checks,
                errors=[q for q in checks if not q['passed']], added_triangles=len(added))


def audit_basin(before_v, before_t, after_v, after_t):
    checks = []

    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))

    remaining = basin._triangle_signature(before_v, before_t)
    original_after, additions = [], []
    for t in after_t:
        signature = toilet._signature(after_v, t)
        if remaining[signature] > 0:
            remaining[signature] -= 1
            original_after.append(t)
        else:
            additions.append(t)
    check('all_original_basin_faces_preserved', not any(remaining.values()),
          original_face_count=len(before_t), matched_original_faces=len(original_after),
          missing_original_faces=sum(remaining.values()))
    groups = toilet._groups(after_v, additions) if additions else []
    check('exactly_seven_added_closed_faucet_solids', len(groups) == 7, actual=len(groups))
    pieces = {}
    for spec in faucet.primitive_specs():
        candidates = [ts for ts in groups if _same_bounds(toilet._bounds(after_v, ts),
                                                        _primitive_bounds(spec))]
        check(spec['name']+':present_once', len(candidates) == 1, actual=len(candidates))
        if len(candidates) == 1:
            pieces[spec['name']] = candidates[0]
            row = _closed_cylinder(after_v, candidates[0], spec)
            check(spec['name']+':closed_prescribed_geometry', row.pop('passed'), **row)
    check('basin_envelope_only_extends_up_to_faucet', _same_bounds(
          toilet._bounds(after_v, after_t), faucet.LOCAL_ENVELOPE),
          actual_local_cm=toilet._bounds(after_v, after_t), expected_local_cm=faucet.LOCAL_ENVELOPE)
    old_parts = {}
    if not any(remaining.values()):
        old_parts = basin._parts(after_v, original_after, True)
        pieces.update({name: part['triangles'] for name, part in old_parts.items()})
    witnesses = list(faucet.CONNECTION_WITNESSES)+[
        dict(name='OriginalDrainIntoSupport', point=[12., 0., 70.], parts=['stem', 'support']),
        dict(name='OriginalDrainIntoCeramic', point=[12., 0., 73.15], parts=['stem', 'under']),
        dict(name='OriginalTapIntoCeramic', point=[16., 0., 80.85], parts=['tap', 'under']),
    ]
    for witness in witnesses:
        have = all(p in pieces for p in witness['parts'])
        result = {p: basin._inside(witness['point'], after_v, pieces[p])
                  for p in witness['parts']} if have else {}
        check(witness['name'], have and all(result.values()),
              witness_local_cm=witness['point'], actual_inside_parts=result)
    return dict(passed=all(q['passed'] for q in checks), checks=checks,
                errors=[q for q in checks if not q['passed']], added_triangles=len(additions))


def analyze(work=DEFAULT_WORK, old_work=DEFAULT_SOURCE, write_output=True):
    work, old_work = Path(work).resolve(), Path(old_work).resolve()
    paths = dict(newGeo=work/'GeometryAfter.json', newSnapshot=work/'AfterSnapshot.json',
                 newBuild=work/'BuildReport.json', oldGeo=old_work/'GeometryAfter.json',
                 oldSnapshot=old_work/'AfterSnapshot.json')
    data = {k: read(p) for k, p in paths.items()}
    ng, ns, build, og, os = [data[k] for k in paths]
    map_sha = build['map_sha256']
    checks, rows = [], []

    def check(name, passed, actor=None, **details):
        # Every saved check is independently identifiable in the publisher.
        # Instance checks otherwise repeat the same names across sixty actors.
        identity = actor if actor is not None else details.get('mesh')
        row = dict(name=(identity+':'+name if identity is not None else name),
                   passed=bool(passed), **details)
        if actor is not None:
            row['actor'] = actor
        checks.append(row)

    check('fresh_new_saved_exports', ng['map_sha256'] == ns['source_map_sha256'] == map_sha
          and bool(ns.get('passed')) and build.get('status') == 'PASS')
    check('exact_expected_saved_baseline', og['map_sha256'] == os['source_map_sha256'] == SOURCE_SHA)
    check('build_source_matches_baseline', build.get('source_map_sha256') == SOURCE_SHA)
    old_toilets = [c for c in og['components'] if c['mesh'].split('.')[0] == toilet.SOURCE_ASSET]
    old_basins = [c for c in og['components'] if c['mesh'].split('.')[0] == faucet.SOURCE_ASSET]
    check('all_thirty_existing_toilets_in_scope', len(old_toilets) == 30, actual=len(old_toilets))
    check('all_thirty_existing_basins_in_scope', len(old_basins) == 30, actual=len(old_basins))
    targets = {c['actor'] for c in old_toilets+old_basins}
    check('sixty_distinct_original_fixtures', len(targets) == 60, actual=len(targets))
    optimization = build.get('fixture_optimization', {})
    declared = set()
    for key in ('changed_actor_labels', 'changed_actors', 'actors'):
        declared |= names(optimization.get(key))
    check('declared_optimization_matches_actual_scope', declared == targets,
          declared=len(declared), expected=len(targets), differences=sorted(declared ^ targets)[:20])
    new_components = {c['id']: c for c in ng['components']}
    new_meshes = set()
    collider_labels = set()
    for category, components in (('Toilet', old_toilets), ('Basin', old_basins)):
        for oc in components:
            label = oc['actor']
            try:
                nc = new_components[oc['id']]
                oa, osc = component_state(os, oc)
                na, nsc = component_state(ns, nc)
                rotate = category == 'Toilet'
                ov = local_vertices(oc, osc, 180. if rotate else 0.)
                nv = local_vertices(nc, nsc, 0.)
                expected = _expected_actor(oa, oc['mesh'], nc['mesh'], rotate)
                check('only_permitted_mesh_and_toilet_yaw_change', na == expected, label)
                check('materials_collision_and_wpo_preserved', oc['materials'] == nc['materials']
                      and oc['collision'] == nc['collision']
                      and oc.get('render_offset_cm', [0., 0., 0.]) == nc.get('render_offset_cm', [0., 0., 0.]), label,
                      render_offset_cm=nc.get('render_offset_cm'))
                check('render_remains_no_collision', 'NO_COLLISION' in nsc['collision']
                      and nsc['collision_profile'] == 'NoCollision', label)
                if rotate:
                    check('toilet_unit_scale_and_zero_wpo', osc['scale'] == nsc['scale'] == [1., 1., 1.]
                          and nc.get('render_offset_cm', [0., 0., 0.]) == [0., 0., 0.], label)
                elif 'Staff' in label:
                    staff_offset = nc.get('render_offset_cm', [])
                    check('staff_basin_retains_existing_y_render_translation',
                          staff_offset == oc.get('render_offset_cm') and len(staff_offset) == 3
                          and abs(staff_offset[0]) < 1.e-7 and abs(staff_offset[1]-.09) < 1.e-7
                          and abs(staff_offset[2]) < 1.e-7, label)
                collider = label+'_Collision0'
                collider_labels.add(collider)
                check('independent_fixture_collider_unchanged', os['actors'].get(collider) is not None
                      and os['actors'][collider] == ns['actors'].get(collider), label,
                      collision_actor=collider)
                check('new_owned_render_asset', nc['mesh'].startswith('/Game/CodexGenerated/')
                      and nc['mesh'] != oc['mesh'], label, mesh=nc['mesh'])
                new_meshes.add(nc['mesh'])
                if rotate:
                    result = audit_toilet(ov, oc['triangles'], nv, nc['triangles'])
                    for q in result['checks']:
                        details = {k: v for k, v in q.items() if k not in ('id', 'passed')}
                        check(q['id'], q['passed'], label, **details)
                else:
                    result = audit_basin(ov, oc['triangles'], nv, nc['triangles'])
                    for q in result['checks']:
                        details = {k: v for k, v in q.items() if k not in ('name', 'passed')}
                        check(q['name'], q['passed'], label, **details)
                rows.append(dict(actor=label, category=category, mesh=nc['mesh'],
                                 geometry_passed=result['passed'], render_offset_cm=nc.get('render_offset_cm')))
            except (KeyError, ValueError, IndexError, TypeError) as exc:
                check('actual_fixture_analysis', False, label, error=str(exc))
    check('sixty_independent_collision_actors_audited', len(collider_labels) == 60,
          actual=len(collider_labels))
    check('exactly_two_new_render_mesh_assets', len(new_meshes) == 2, actual=len(new_meshes))
    new_asset_hashes = {Path(p).resolve(): digest for p, digest in build.get('new_asset_sha256', {}).items()}
    for mesh in sorted(new_meshes):
        path = ROOT/('Content/'+mesh.split('.')[0][6:]+'.uasset')
        digest = new_asset_hashes.get(path.resolve())
        check('new_render_asset_hash_matches_saved_asset', path.is_file() and digest is not None
              and sha(path) == digest, mesh=mesh, file=str(path))
    other_changed = [label for label, state in os['actors'].items() if label not in targets
                     and ns['actors'].get(label) != state]
    check('all_other_7949_original_actors_unchanged', not other_changed
          and len(os['actors'])-len(targets) == 7949,
          checked=len(os['actors'])-len(targets), changed=other_changed[:30])
    added = set(ns['actors'])-set(os['actors'])
    removed = set(os['actors'])-set(ns['actors'])
    declared_cameras = names(optimization.get('new_cameras'))
    check('exactly_three_new_review_cameras_and_no_actor_removals', len(added) == 3 and not removed
          and all(ns['actors'][label]['class'] == '/Script/Engine.CameraActor' for label in added)
          and added == declared_cameras, added=sorted(added), removed=sorted(removed),
          declared_cameras=sorted(declared_cameras))
    check('protected_map_manifests_preserved',
          os.get('protected_map_sha256') == ns.get('protected_map_sha256'))
    old_references = os.get('shared_asset_sha256', {})
    old_file_errors = [p for p, digest in old_references.items()
                       if not Path(p).is_file() or sha(p) != digest]
    check('all_400_old_shared_files_unchanged_on_disk', len(old_references) == 400
          and not old_file_errors, checked=len(old_references), changed=old_file_errors[:30])
    expected_references = deepcopy(old_references)
    asset_rows = optimization.get('new_assets', [])
    reference_plan_valid = isinstance(asset_rows, list) and len(asset_rows) == 2
    if isinstance(asset_rows, list):
        for asset_row in asset_rows:
            source_file, target_file = asset_row.get('source_file'), asset_row.get('file')
            source_hash, target_hash = asset_row.get('source_sha256'), asset_row.get('sha256')
            reference_plan_valid &= bool(source_file and target_file and source_hash and target_hash)
            reference_plan_valid &= expected_references.get(source_file) == source_hash
            if source_file in expected_references:
                del expected_references[source_file]
            if target_file and target_hash:
                expected_references[target_file] = target_hash
            sections = asset_row.get('added_triangles_per_material_section', [])
            check('persisted_new_mesh_additions_only_use_slot_zero', len(sections) >= 2
                  and sections[0] > 0 and all(v == 0 for v in sections[1:])
                  and asset_row.get('original_faces_retained') is True,
                  mesh=asset_row.get('asset'), added_triangles_per_material_section=sections)
    check('new_shared_references_replace_only_two_source_clones', reference_plan_valid
          and ns.get('shared_asset_sha256') == expected_references,
          expected_reference_count=len(expected_references),
          actual_reference_count=len(ns.get('shared_asset_sha256', {})))
    errors = [q for q in checks if not q['passed']]
    report = dict(passed=bool(checks) and not errors, errors=errors, checks=checks,
                  map_sha256=map_sha, source_map_sha256=SOURCE_SHA,
                  statistics=dict(toilets=len(old_toilets), basins=len(old_basins), checks=len(checks),
                                  fixture_actors_audited=len(rows), unchanged_other_original_actors=7949,
                                  unchanged_fixture_colliders=len(collider_labels), new_review_cameras=len(added)),
                  input_sha256={str(path): sha(path) for path in paths.values()},
                  input_files={key: str(path) for key, path in paths.items()},
                  fixtures=rows, geometry_source='Saved actual rendered vertices and triangles',
                  units='cm', position_tolerance_cm=EPS)
    output = work/'FixtureGeometryAudit.json'
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
