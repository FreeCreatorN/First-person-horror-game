"""Minimal closed ceramic supports for the saved hotel toilets (centimetres).

This module imports no Unreal package and does not alter assets or reports.
The existing Separated render mesh is the input; its cistern face offsets stay
intact. Only the 39 cm bowl top ring rises, to 40.7 cm. Two closed elliptical
cylinders connect the rear pedestal, bowl, and cistern within the old envelope.
The seat, tank, lever, actor pose, material slots, and collision remain intact.

Public API: primitive_specs(), bowl_top_vertex_ids(vertices),
build_added_geometry(), audit_geometry(before_v, before_t, after_v, after_t),
diagnose_saved(work). The audit accepts normal-split or reordered vertices and
any valid triangulation of the two prescribed closed cylinders; original
triangles must still be present exactly after the prescribed bowl-top move.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path

SCHEMA = 'OldTownToiletConnectionsV1'
SOURCE_ASSET = '/Game/CodexGenerated/OldTown/SurfaceSeparation_20261009/Meshes/SM_OTS_Arch_Toilet_Separated_2329a1321be3'
ORIGINAL_ASSET = '/Game/Yastar/Meshes/hOUSE/HotelArchitecture_20261005/SM_OTS_Arch_Toilet'
CERAMIC_SLOT = 0
OLD_BOWL_TOP = 39.
NEW_BOWL_TOP = 40.7
LOCAL_ENVELOPE = [[-32.01, -17.7, 0.], [33., 17.7, 78.]]
EPS = .002  # cm; render export world coordinates are rounded to 0.0001 cm.


def primitive_specs():
    """Radius 1 Z cylinders, elliptically scaled; all appended material ID 0.

    The rear foot joins the existing front pedestal instead of occupying the
    knee/foot space in front of the bowl. It stops at 31 cm; the short rear
    shoulder starts at 29.5 cm and embeds 1 cm into the 45 cm cistern bottom.
    """
    return [
        dict(name='RearCeramicPedestal', kind='elliptical_cylinder',
             center=[13., 0., 15.5], radii=[12., 9.], height=31.,
             radius=1., axis=[0., 0., 1.], radial_sides=24, material_id=0,
             collision='NoCollision'),
        dict(name='RearCeramicShoulder', kind='elliptical_cylinder',
             center=[13., 0., 37.75], radii=[16., 12.], height=16.5,
             radius=1., axis=[0., 0., 1.], radial_sides=24, material_id=0,
             collision='NoCollision'),
    ]


CONNECTION_WITNESSES = [
    dict(name='BowlIntoSeatLeft', point=[-9., 16.5, 40.5], parts=['Bowl', 'Seat']),
    dict(name='BowlIntoSeatRight', point=[-9., -16.5, 40.5], parts=['Bowl', 'Seat']),
    dict(name='BowlIntoSeatFront', point=[-30., 0., 40.5], parts=['Bowl', 'Seat']),
    dict(name='OldPedestalIntoRearFoot', point=[7., 0., 15.5],
         parts=['Pedestal', 'RearCeramicPedestal']),
    dict(name='BowlIntoRearFoot', point=[4., 0., 28.],
         parts=['Bowl', 'RearCeramicPedestal']),
    dict(name='RearFootIntoShoulder', point=[13., 0., 30.25],
         parts=['RearCeramicPedestal', 'RearCeramicShoulder']),
    dict(name='BowlIntoShoulder', point=[4., 0., 34.],
         parts=['Bowl', 'RearCeramicShoulder']),
    dict(name='ShoulderIntoCistern', point=[20., 0., 45.5],
         parts=['Cistern', 'RearCeramicShoulder']),
]


def bowl_top_vertex_ids(vertices):
    """Select only normal-split cap/side vertices of the original bowl top.

    Current saved RenderData has 72 selected split vertices (24 positions).
    Callers may weld vertices; therefore selection accepts that equivalent
    representation and rejects a changed bowl outline or other height.
    """
    return [i for i, (x, y, z) in enumerate(vertices)
            if abs(z-OLD_BOWL_TOP) <= EPS and
            -30.76-EPS <= x <= 12.76+EPS and abs(y) <= 17.+EPS]


def expected_original_vertices(vertices):
    result = [list(p) for p in vertices]
    selected = bowl_top_vertex_ids(vertices)
    if len({tuple(round(v, 3) for v in vertices[i]) for i in selected}) != 24:
        raise ValueError('Expected exactly 24 original bowl-top positions')
    for i in selected:
        result[i][2] = NEW_BOWL_TOP
    return result


def _primitive_geometry(spec):
    n = spec['radial_sides']
    cx, cy, cz = spec['center']
    rx, ry = spec['radii']
    half = spec['height']/2
    vertices = [[cx+rx*math.cos(2*math.pi*j/n),
                 cy+ry*math.sin(2*math.pi*j/n), cz+dz]
                for dz in (-half, half) for j in range(n)]
    bottom, top = len(vertices), len(vertices)+1
    vertices += [[cx, cy, cz-half], [cx, cy, cz+half]]
    triangles = []
    for i in range(n):
        j = (i+1) % n
        triangles += [[bottom, j, i], [top, i+n, j+n],
                      [i, j, j+n], [i, j+n, i+n]]
    return vertices, triangles


def build_added_geometry():
    vertices, triangles, pieces = [], [], []
    for spec in primitive_specs():
        vv, tt = _primitive_geometry(spec)
        base, first = len(vertices), len(triangles)
        vertices.extend(vv)
        triangles.extend([[i+base for i in t] for t in tt])
        pieces.append(dict(name=spec['name'], triangle_start=first,
                           triangle_count=len(tt), material_id=CERAMIC_SLOT,
                           closed=True))
    return dict(schema=SCHEMA, vertices=vertices, triangles=triangles,
                pieces=pieces, primitive_specs=primitive_specs(),
                witnesses=CONNECTION_WITNESSES, material_id=CERAMIC_SLOT,
                collision='NoCollision', units='cm')


def _key(point):
    return tuple(round(float(v), 3) for v in point)


def _signature(vertices, triangle):
    return tuple(sorted(_key(vertices[i]) for i in triangle))


def _bounds(vertices, triangles):
    ids = {i for t in triangles for i in t}
    points = [vertices[i] for i in ids]
    if not points:
        raise ValueError('No triangle vertices')
    return [[min(p[a] for p in points) for a in range(3)],
            [max(p[a] for p in points) for a in range(3)]]


def _groups(vertices, triangles):
    """Position-weld triangles for topology only, retaining original indices."""
    ids = {i for t in triangles for i in t}
    nodes = {i: _key(vertices[i]) for i in ids}
    parent = {p: p for p in set(nodes.values())}

    def find(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    for t in triangles:
        for j in (1, 2):
            parent[find(nodes[t[j]])] = find(nodes[t[0]])
    groups = {}
    for t in triangles:
        groups.setdefault(find(nodes[t[0]]), []).append(t)
    return list(groups.values())


def _dot(a, b):
    return sum(a[i]*b[i] for i in range(3))


def _cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0]]


def _inside(point, vertices, triangles):
    """Actual closed-surface solid-angle test, independent of bounds."""
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


def _original_parts(vertices, triangles, repaired=False):
    boxes = dict(
        Pedestal=[[-21.4, -11.2, 0.], [9.4, 11.2, 32.]],
        Bowl=[[-30.76, -17., 25.], [12.76, 17., NEW_BOWL_TOP if repaired else 39.]],
        Seat=[[-32.01, -17.7, 40.3], [14.01, 17.7, 42.7]],
    )
    groups, result = _groups(vertices, triangles), {}
    for name, box in boxes.items():
        matches = [ts for ts in groups if all(abs(a-b) <= EPS for aa, bb in
                   zip(_bounds(vertices, ts), box) for a, b in zip(aa, bb))]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous original part: '+name)
        result[name] = matches[0]
    # Prior separation disconnected some cistern/lid patches by 0.034 cm.
    # Retain all such actual faces for the cistern winding test; no resealing.
    result['Cistern'] = [t for t in triangles if
                         min(vertices[i][2] for i in t) >= 45.-EPS]
    return result


def _closed_primitive(vertices, triangles, spec):
    cx, cy, cz = spec['center']
    rx, ry = spec['radii']
    lo, hi = cz-spec['height']/2, cz+spec['height']/2
    expected = [[cx-rx, cy-ry, lo], [cx+rx, cy+ry, hi]]
    bounds = _bounds(vertices, triangles)
    good_bounds = all(abs(a-b) <= EPS for aa, bb in zip(bounds, expected)
                      for a, b in zip(aa, bb))
    edges = Counter()
    keys = set()
    directions = Counter()
    surfaces_valid = True
    signed_volume = 0.
    for t in triangles:
        ps = [vertices[i] for i in t]
        kk = [_key(p) for p in ps]
        keys.update(kk)
        for i in range(3):
            a, b = kk[i], kk[(i+1) % 3]
            edges[tuple(sorted((a, b)))] += 1
            directions[(a, b)] += 1
        cap = all(abs(p[2]-lo) <= EPS for p in ps) or all(abs(p[2]-hi) <= EPS for p in ps)
        side = all(abs(((p[0]-cx)/rx)**2+((p[1]-cy)/ry)**2-1.) < .001
                   and lo-EPS <= p[2] <= hi+EPS for p in ps)
        surfaces_valid &= cap or side
        signed_volume += _dot(ps[0], _cross(ps[1], ps[2]))/6
    n = spec['radial_sides']
    expected_volume = .5*n*math.sin(2*math.pi/n)*rx*ry*spec['height']
    closed = all(v == 2 for v in edges.values()) and all(
        directions[(a, b)] == directions[(b, a)] for a, b in edges)
    euler = len(keys)-len(edges)+len(triangles)
    volume_error = abs(abs(signed_volume)-expected_volume)
    passed = good_bounds and surfaces_valid and closed and euler == 2 and volume_error < .15
    return dict(name=spec['name'], passed=bool(passed), closed=closed,
                bounds_cm=bounds, expected_bounds_cm=expected,
                surfaces_match_prescribed_cylinder=bool(surfaces_valid),
                euler=euler, triangle_count=len(triangles),
                actual_volume_cm3=abs(signed_volume), expected_volume_cm3=expected_volume,
                volume_error_cm3=volume_error)


def audit_geometry(before_vertices, before_triangles, after_vertices, after_triangles):
    """Audit actual mesh geometry, including source faces and connected solids.

    Append primitives with no boolean/remesh operation. Native GeometryScript
    cylinders are supported: no particular cap diagonal or vertex order is
    required. No new material translations should be introduced for this mesh.
    """
    checks = []

    def check(name, passed, **details):
        checks.append(dict(id=name, passed=bool(passed), **details))

    expected = expected_original_vertices(before_vertices)
    remaining = Counter(_signature(expected, t) for t in before_triangles)
    original_after, added_after = [], []
    for t in after_triangles:
        signature = _signature(after_vertices, t)
        if remaining[signature] > 0:
            remaining[signature] -= 1
            original_after.append(t)
        else:
            added_after.append(t)
    check('only_bowl_top_changed_original_faces_retained', not any(remaining.values()),
          lifted_split_vertices=len(bowl_top_vertex_ids(before_vertices)),
          missing_original_faces=sum(remaining.values()),
          original_face_count=len(before_triangles), matched_original_faces=len(original_after))
    groups = _groups(after_vertices, added_after) if added_after else []
    check('exactly_two_added_closed_supports', len(groups) == 2, actual=len(groups))
    pieces = {}
    for spec in primitive_specs():
        candidates = [ts for ts in groups if all(abs(a-b) <= EPS for aa, bb in zip(
            _bounds(after_vertices, ts), [[spec['center'][0]-spec['radii'][0],
            spec['center'][1]-spec['radii'][1], spec['center'][2]-spec['height']/2],
            [spec['center'][0]+spec['radii'][0], spec['center'][1]+spec['radii'][1],
             spec['center'][2]+spec['height']/2]]) for a, b in zip(aa, bb))]
        check(spec['name']+':present_once', len(candidates) == 1, actual=len(candidates))
        if len(candidates) == 1:
            pieces[spec['name']] = candidates[0]
            row = _closed_primitive(after_vertices, candidates[0], spec)
            row.pop('name')
            check(spec['name']+':closed_prescribed_geometry', row.pop('passed'), **row)
    actual_bounds = _bounds(after_vertices, after_triangles)
    check('entire_old_envelope_retained', all(abs(a-b) <= EPS for aa, bb in
          zip(actual_bounds, LOCAL_ENVELOPE) for a, b in zip(aa, bb)), actual_cm=actual_bounds)
    if not any(remaining.values()):
        pieces.update(_original_parts(after_vertices, original_after, True))
    for witness in CONNECTION_WITNESSES:
        present = all(p in pieces for p in witness['parts'])
        solid_tests = {p: _inside(witness['point'], after_vertices, pieces[p])
                       for p in witness['parts']} if present else {}
        check(witness['name'], present and all(solid_tests.values()),
              witness_local_cm=witness['point'], actual_inside_parts=solid_tests)
    if 'RearCeramicPedestal' in pieces:
        ground = _bounds(after_vertices, pieces['RearCeramicPedestal'])[0][2]
        check('rear_support_has_actual_floor_plane_contact', abs(ground) <= EPS,
              bottom_local_cm=ground, contact_local_cm=[13., 0., 0.])
    return dict(schema=SCHEMA, passed=all(c['passed'] for c in checks),
                checks=checks, errors=[c for c in checks if not c['passed']],
                witnesses=CONNECTION_WITNESSES, added_triangles=len(added_after),
                ceramic_material_id=CERAMIC_SLOT)


def local_vertices(component, actor_state):
    """Inverse of the actual current yaw-180, scale-1 toilet transform.

    Reject unfamiliar transforms instead of silently using the wrong frame.
    This is a saved-map diagnostic helper; callers with a live Unreal transform
    should inverse-transform positions through that actual transform.
    """
    if any(abs(a-b) > 1.e-5 for a, b in zip(actor_state['rotation'], [0., 180., 0.])):
        raise ValueError('Unexpected toilet rotation')
    if any(abs(a-1.) > 1.e-5 for a in actor_state['scale']):
        raise ValueError('Unexpected toilet scale')
    if component.get('render_offset_cm', [0., 0., 0.]) != [0., 0., 0.]:
        raise ValueError('Unexpected toilet WPO translation')
    x, y, z = actor_state['location']
    return [[x-p[0], y-p[1], p[2]-z] for p in component['vertices']]


def diagnose_saved(work):
    work = Path(work)
    geometry = json.loads((work/'GeometryAfter.json').read_text(encoding='utf-8-sig'))
    snapshot = json.loads((work/'AfterSnapshot.json').read_text(encoding='utf-8-sig'))
    build = json.loads((work/'BuildReport.json').read_text(encoding='utf-8-sig'))
    components = [c for c in geometry['components'] if 'Toilet' in c.get('mesh', '')]
    rows = []
    for c in components:
        state = snapshot['actors'][c['actor']]
        vv = local_vertices(c, state)
        parts = _original_parts(vv, c['triangles'])
        bounds = {k: _bounds(vv, ts) for k, ts in parts.items()}
        comp_state = next(s for s in state['components'] if s['name'] == c['component'])
        row = dict(actor=c['actor'], mesh=c['mesh'], bounds_cm=bounds,
                   seat_to_bowl_vertical_gap_cm=bounds['Seat'][0][2]-bounds['Bowl'][1][2],
                   cistern_to_bowl_vertical_gap_cm=bounds['Cistern'][0][2]-bounds['Bowl'][1][2],
                   cistern_to_bowl_horizontal_gap_cm=bounds['Cistern'][0][0]-bounds['Bowl'][1][0],
                   bowl_top_split_vertices=len(bowl_top_vertex_ids(vv)),
                   render_offset_cm=c.get('render_offset_cm'),
                   material_slot_0=c['materials'][0], no_collision='NO_COLLISION' in comp_state['collision'])
        added = build_added_geometry()
        expected = expected_original_vertices(vv)
        base = len(expected)
        result = audit_geometry(vv, c['triangles'], expected+added['vertices'],
                                c['triangles']+[[i+base for i in t] for t in added['triangles']])
        row['recipe_verified_on_actual_source_geometry'] = result['passed']
        row['recipe_errors'] = result['errors']
        rows.append(row)
    return dict(schema=SCHEMA, map_sha256=geometry['map_sha256'],
                fresh_saved_exports=geometry['map_sha256'] == snapshot['source_map_sha256'] == build['map_sha256'],
                actor_count=len(rows), rows=rows, primitives=primitive_specs(),
                witnesses=CONNECTION_WITNESSES)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', default=str(Path(__file__).resolve().parents[1]/
                        'Saved/CodexOutputs/BasinConnections_20261011'))
    args = parser.parse_args()
    print(json.dumps(diagnose_saved(args.work), ensure_ascii=False, indent=2))
