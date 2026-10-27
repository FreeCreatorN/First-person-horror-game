"""Read-only, saved-mesh checks for the thirty repaired hotel washbasins.

Only the audit JSON is written. No Unreal runtime or asset mutation is used.
Run with ordinary Python after the saved world has been exported.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK = ROOT / 'Saved/CodexOutputs/BasinConnections_20261011'
DEFAULT_OLD_WORK = ROOT / 'Saved/CodexOutputs/HotelDetails_20261009'
OLD_MESH_NAME = 'SM_OTS_Arch_Washbasin.'
EPS = .002  # cm; transforms in snapshots are rounded, comparisons share that transform.


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _key(p):
    return tuple(round(float(x), 3) for x in p)


def _local(vertices, component, render_offset_cm=None):
    rotation = component['rotation']
    if any(abs(float(x)) > 1.e-5 for x in rotation):
        raise ValueError('This audit explicitly rejects nonzero basin rotations: %r' % rotation)
    if any(float(x) <= 0 for x in component['scale']):
        raise ValueError('Only positive basin scales are supported')
    # Exported geometry already includes the persisted material's world-space
    # translation. Actor/component poses intentionally do not include that WPO.
    offset = render_offset_cm or [0., 0., 0.]
    if len(offset) != 3 or not all(math.isfinite(float(x)) for x in offset):
        raise ValueError('Invalid persisted render translation')
    return [[(p[i]-offset[i]-component['location'][i])/component['scale'][i]
             for i in range(3)] for p in vertices]


def _islands(vertices, triangles):
    """Weld position-identical split normals for connectivity only."""
    nodes, indices = {}, []
    for p in vertices:
        k = _key(p)
        if k not in nodes:
            nodes[k] = len(nodes)
        indices.append(nodes[k])
    parent = list(range(len(nodes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for t in triangles:
        for j in (1, 2):
            parent[find(indices[t[j]])] = find(indices[t[0]])
    groups = {}
    for i, p in enumerate(vertices):
        group = groups.setdefault(find(indices[i]), dict(indices=[], triangles=[]))
        group['indices'].append(i)
    for t in triangles:
        groups[find(indices[t[0]])]['triangles'].append(t)
    for group in groups.values():
        points = [vertices[i] for i in group['indices']]
        group['low'] = [min(p[i] for p in points) for i in range(3)]
        group['high'] = [max(p[i] for p in points) for i in range(3)]
    return list(groups.values())


def _part(groups, low, high, name):
    # X/Y incur at most a few thousandths of a centimetre from rounded scales.
    matches = [g for g in groups if all(abs(g['low'][i]-low[i]) < .02 and
               abs(g['high'][i]-high[i]) < .02 for i in range(3))]
    if len(matches) != 1:
        raise ValueError('Expected one %s island; found %d' % (name, len(matches)))
    return matches[0]


def _parts(vertices, triangles, repaired):
    groups = _islands(vertices, triangles)
    return {
        'stem': _part(groups, [9.5, -2.5, 0.],
                      [14.5, 2.5, 73.3 if repaired else 64.], 'stem'),
        'support': _part(groups, [11., -25., 69.], [21., 25., 75.], 'support'),
        'under': _part(groups, [-21., -29., 73.], [20., 29., 81.], 'under'),
        'tap': _part(groups, [14.8, -1.2, 80.7 if repaired else 81.4],
                     [17.2, 1.2, 85.], 'tap'),
    }


def _dot(a, b):
    return sum(a[i]*b[i] for i in range(3))


def _cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def _inside(point, vertices, triangles):
    """Closed oriented mesh winding test; both winding directions are accepted."""
    total = 0.
    for t in triangles:
        a, b, c = [[vertices[v][i]-point[i] for i in range(3)] for v in t]
        la, lb, lc = [math.sqrt(_dot(q, q)) for q in (a, b, c)]
        if min(la, lb, lc) < 1.e-9:
            return True
        numerator = _dot(a, _cross(b, c))
        denominator = la*lb*lc+_dot(a, b)*lc+_dot(b, c)*la+_dot(c, a)*lb
        total += 2.*math.atan2(numerator, denominator)
    return abs(total) > 2.*math.pi


def _points_preserved(actual, expected):
    # A position set makes this independent of normal-split vertex reordering.
    def nearby(p, pool):
        k = tuple(math.floor(x/EPS) for x in p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q in pool.get((k[0]+dx, k[1]+dy, k[2]+dz), ()):
                        if max(abs(p[i]-q[i]) for i in range(3)) <= EPS:
                            return True
        return False

    def grid(points):
        pool = {}
        for p in points:
            pool.setdefault(tuple(math.floor(x/EPS) for x in p), []).append(p)
        return pool

    actual_grid, expected_grid = grid(actual), grid(expected)
    missing = [p for p in expected if not nearby(p, actual_grid)]
    unexpected = [p for p in actual if not nearby(p, expected_grid)]
    return not missing and not unexpected, missing[:5], unexpected[:5]


def _triangle_signature(vertices, triangles):
    # Permit winding reversal and vertex split reordering, preserve all faces.
    return Counter(tuple(sorted(_key(vertices[i]) for i in t)) for t in triangles)


def _component_state(snapshot, component):
    actor = snapshot['actors'][component['actor']]
    matches = [c for c in actor['components'] if c['name'] == component['component']]
    if len(matches) != 1:
        raise ValueError('Component is absent or ambiguous: '+component['id'])
    return actor, matches[0]


def _actor_except_mesh(actor):
    copy = json.loads(json.dumps(actor))
    for c in copy['components']:
        if 'mesh' in c:
            c['mesh'] = '<permitted render mesh replacement>'
    return copy


def analyze(work=DEFAULT_WORK, old_work=DEFAULT_OLD_WORK, write_output=True):
    work, old_work = Path(work), Path(old_work)
    paths = {name: work/(name+'.json') for name in ('GeometryAfter', 'AfterSnapshot', 'BuildReport')}
    old_paths = {name: old_work/(name+'.json') for name in ('GeometryAfter', 'AfterSnapshot')}
    new, old = {k: read(p) for k, p in paths.items()}, {k: read(p) for k, p in old_paths.items()}
    map_sha = new['BuildReport']['map_sha256']
    checks, rows = [], []

    def check(name, passed, **details):
        checks.append(dict(id=name, passed=bool(passed), **details))

    check('fresh_saved_exports', new['GeometryAfter']['map_sha256'] == map_sha and
          new['AfterSnapshot']['source_map_sha256'] == map_sha and
          bool(new['AfterSnapshot'].get('passed')) and new['BuildReport']['status'] == 'PASS')
    check('baseline_export_matches_snapshot', old['GeometryAfter']['map_sha256'] ==
          old['AfterSnapshot']['source_map_sha256'])
    old_components = [c for c in old['GeometryAfter']['components'] if OLD_MESH_NAME in c['mesh']]
    new_components = {c['id']: c for c in new['GeometryAfter']['components']}
    check('thirty_shared_basins', len(old_components) == 30, actual=len(old_components))
    source_collision_actors = {}

    for oc in old_components:
        label = oc['actor']
        try:
            nc = new_components[oc['id']]
            oa, os = _component_state(old['AfterSnapshot'], oc)
            na, ns = _component_state(new['AfterSnapshot'], nc)
            ov = _local(oc['vertices'], os, oc.get('render_offset_cm'))
            nv = _local(nc['vertices'], ns, nc.get('render_offset_cm'))
            op, np = _parts(ov, oc['triangles'], False), _parts(nv, nc['triangles'], True)
            expected = [list(p) for p in ov]
            moved_stem, moved_tap = 0, 0
            for i in op['stem']['indices']:
                if abs(ov[i][2]-64.) < .002:
                    expected[i][2] = 73.3
                    moved_stem += 1
            for i in op['tap']['indices']:
                if abs(ov[i][2]-81.4) < .002:
                    expected[i][2] = 80.7
                    moved_tap += 1
            good, missing, unexpected = _points_preserved(nv, expected)
            check(label+':only_target_end_vertices_moved', good and moved_stem > 0 and moved_tap > 0,
                  stem_end_vertices=moved_stem, tap_end_vertices=moved_tap,
                  missing_expected=missing, unexpected_actual=unexpected)
            # Compare triangle surfaces too, so equal bounds or a point cloud is insufficient.
            check(label+':all_original_faces_preserved',
                  _triangle_signature(nv, nc['triangles']) == _triangle_signature(expected, oc['triangles']),
                  before_triangles=len(oc['triangles']), after_triangles=len(nc['triangles']))
            check(label+':pose_materials_and_component_settings_preserved',
                  _actor_except_mesh(oa) == _actor_except_mesh(na) and oc['materials'] == nc['materials'] and
                  oc['collision'] == nc['collision'] and
                  oc.get('render_offset_cm', [0., 0., 0.]) == nc.get('render_offset_cm', [0., 0., 0.]))
            check(label+':render_remains_no_collision', 'NO_COLLISION' in ns['collision'] and
                  ns['collision_profile'] == 'NoCollision')
            overlap = []
            for name, point, a, b in (
                    ('stem_into_support', [12., 0., 70.], 'stem', 'support'),
                    ('stem_into_ceramic_under', [12., 0., 73.15], 'stem', 'under'),
                    ('tap_into_ceramic_under', [16., 0., 80.85], 'tap', 'under')):
                good = _inside(point, nv, np[a]['triangles']) and _inside(point, nv, np[b]['triangles'])
                check(label+':'+name, good, witness_local_cm=point)
                overlap.append(dict(connection=name, passed=good, witness_local_cm=point))
            collision_label = label+'_Collision0'
            before = old['AfterSnapshot']['actors'].get(collision_label)
            after = new['AfterSnapshot']['actors'].get(collision_label)
            check(label+':independent_collision_unchanged', before is not None and before == after)
            source_collision_actors[collision_label] = before
            check(label+':new_owned_render_asset', nc['mesh'].startswith('/Game/CodexGenerated/'))
            rows.append(dict(actor=label, component=nc['id'], mesh=nc['mesh'],
                bounds={k:[np[k]['low'], np[k]['high']] for k in np},
                connections=overlap, material_slots=nc['materials'],
                preserved_world_render_offset_cm=nc.get('render_offset_cm', [0., 0., 0.])))
        except (KeyError, ValueError, IndexError) as exc:
            check(label+':analysis', False, error=str(exc))

    old_labels = {c['actor'] for c in old_components}
    # Components outside the thirty basins must retain the same state, except cameras.
    excluded = old_labels | set(source_collision_actors)
    unchanged, changed = 0, []
    for label, state in old['AfterSnapshot']['actors'].items():
        if label in excluded or state['class'] == '/Script/Engine.CameraActor':
            continue
        if new['AfterSnapshot']['actors'].get(label) == state:
            unchanged += 1
        else:
            changed.append(label)
    check('all_other_original_actors_unchanged', not changed, checked=unchanged+len(changed), changed=changed[:20])
    passed = bool(checks) and all(q['passed'] for q in checks)
    report = dict(passed=passed, source_map_sha256=map_sha,
        previous_map_sha256=old['GeometryAfter']['map_sha256'],
        input_sha256={str(p): sha(p) for p in list(paths.values())+list(old_paths.values())},
        basin_count=len(rows), geometry_source='Saved actual rendered vertices and triangle connectivity',
        units='cm', position_tolerance_cm=EPS, stem_top_cm=73.3, tap_bottom_cm=80.7,
        unchanged_original_non_camera_actor_count=unchanged, check_count=len(checks),
        failed_checks=[q for q in checks if not q['passed']], checks=checks, basins=rows)
    output = work/'BasinConnectionGeometryAudit.json'
    if write_output:
        work.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=DEFAULT_WORK)
    parser.add_argument('--old-work', type=Path, default=DEFAULT_OLD_WORK)
    args = parser.parse_args()
    report, output = analyze(args.work, args.old_work)
    print(json.dumps(dict(passed=report['passed'], basin_count=report['basin_count'],
                         failed_checks=report['failed_checks'], output=str(output)), ensure_ascii=False))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
