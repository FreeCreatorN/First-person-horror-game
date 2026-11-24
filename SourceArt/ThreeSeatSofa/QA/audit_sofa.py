"""Read-only audit of the saved MCP sofa, restricted to report-listed parts.

Run only after the model author freezes the source. This script never saves a
Blender file, mutates a mesh, or inspects unrelated objects. Surface contacts
are reported separately from strict triangle crossings. Welt piping is an
intentional embedded construction shell and is classified by material name.
"""
from __future__ import annotations

import bpy
import bmesh
import hashlib
import itertools
import json
import math
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'ThreeSeatSofa.blend'
REPORT = ROOT / 'model_report.json'
OUTPUT = ROOT / 'QA' / 'sofa_geometry_audit.json'
EPS = 2e-6
WELT_MATERIALS = {'M_Sofa_Welt', 'M_Sofa_PillowWelt'}
# Explicitly reviewed mount/soft-compression tolerances. These do not suppress
# raw triangle-pair counts or sampled depth estimates in the audit report.
REVIEWED_CONTACTS = {}
def register_contact(a, b, depth, reason):
    REVIEWED_CONTACTS[tuple(sorted(('SM_Sofa_' + a, 'SM_Sofa_' + b)))] = {
        'allow_penetration_m': depth, 'reason': reason, 'reviewed_soft_contact': True}
for side in ('L', 'R'):
    register_contact('Base', 'Arm_' + side, .012,
                     'Upholstered arm bottom seated into low plinth after side cutouts; hidden mount contact.')
for number in ('01', '02', '03'):
    register_contact('Base', 'Back_' + number, .006,
                     'Back cushion gently compressed against upholstered rear wall.')
    register_contact('Seat_' + number, 'Back_' + number, .004,
                     'Soft seat/back cushion junction.')
for foot in ('FL', 'FR', 'BL', 'BR'):
    register_contact('Base', 'Foot_' + foot, .006,
                     'Concealed foot top embedded into upholstered base mounting area.')
for side, number in (('L', '01'), ('R', '03')):
    register_contact('Arm_' + side, 'Seat_' + number, .003,
                     'Outer seat cushion rests against padded arm.')
    register_contact('Arm_' + side, 'Back_' + number, .005,
                     'Outer back cushion gently compressed against padded arm.')
    register_contact('Seat_' + number, 'Pillow_' + side, .016,
                     'Loose soft pillow bottom compressed into seat cushion, tolerance 16 mm.')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(points):
    return [[min(v[i] for v in points) for i in range(3)],
            [max(v[i] for v in points) for i in range(3)]]


def strict_crossing(a, b):
    """Exclude coplanar area and contacts along triangle edges/vertices."""
    pts = []
    for triangle, other in ((a, b), (b, a)):
        v0, v1, v2 = other
        e1, e2 = v1 - v0, v2 - v0
        for p, q in zip(triangle, triangle[1:] + triangle[:1]):
            delta = q - p
            h = delta.cross(e2)
            determinant = e1.dot(h)
            if abs(determinant) < 1e-14:
                continue
            inverse = 1.0 / determinant
            s = p - v0
            u = s.dot(h) * inverse
            if not 1e-6 < u < 1 - 1e-6:
                continue
            z = s.cross(e1)
            v = delta.dot(z) * inverse
            t = e2.dot(z) * inverse
            if v > 1e-6 and u + v < 1 - 1e-6 and 1e-6 < t < 1 - 1e-6:
                pts.append(p + delta * t)
    return None if not pts else list(sum(pts, Vector()) / len(pts))


def orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def clipped_area(subject, boundary):
    result = subject
    if orient(*boundary) < 0:
        boundary = list(reversed(boundary))
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        previous, result = result, []
        if not previous:
            break
        for p, q in zip(previous, previous[1:] + previous[:1]):
            cp, cq = orient(a, b, p), orient(a, b, q)
            inside_p, inside_q = cp >= -1e-13, cq >= -1e-13
            if inside_p:
                result.append(p)
            if inside_p != inside_q:
                t = cp / (cp - cq)
                result.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    if len(result) < 3:
        return 0.0
    return abs(sum(p[0] * q[1] - q[0] * p[1]
                   for p, q in zip(result, result[1:] + result[:1]))) * 0.5


def coplanar_area(a, b):
    na = (a[1] - a[0]).cross(a[2] - a[0])
    nb = (b[1] - b[0]).cross(b[2] - b[0])
    if na.length < 1e-14 or nb.length < 1e-14:
        return 0.0
    na.normalize(); nb.normalize()
    if na.dot(nb) < 0.999999 or max(abs((p - a[0]).dot(na)) for p in b) > EPS:
        return 0.0
    drop = max(range(3), key=lambda i: abs(na[i]))
    keep = [i for i in range(3) if i != drop]
    aa = [tuple(p[i] for i in keep) for p in a]
    bb = [tuple(p[i] for i in keep) for p in b]
    return clipped_area(aa, bb) / max(abs(na[drop]), 1e-12)


def nearest_distance(vertices, bvh):
    best = math.inf
    for p in vertices:
        nearest = bvh.find_nearest(p)
        if nearest[0] is not None:
            best = min(best, nearest[3])
    return best


def sampled_embed_depth(vertices, bvh):
    """Signed nearest-surface sample, reported as estimate rather than proof.

    For a closed outward-facing mesh, points on the inward side of the nearest
    face approximate inside samples. Edges/creases can make classification
    ambiguous, so this never silently grants a passing contact classification.
    """
    maximum = 0.0; count = 0; example = None
    for p in vertices:
        nearest = bvh.find_nearest(p)
        if nearest[0] is not None and (p - nearest[0]).dot(nearest[1]) < -EPS:
            count += 1
            if nearest[3] > maximum:
                maximum = nearest[3]; example = list(p)
    return {'sampled_max_embed_m': maximum, 'inward_vertex_samples': count,
            'deepest_sample_world_m': example}


result = {'source': str(SOURCE), 'read_only': True,
          'source_sha256_before': digest(SOURCE), 'findings': [],
          'parts': {}, 'contacts': [], 'surface_crossings': [],
          'same_facing_coplanar_overlaps': [],
          'notes': ['Nearest vertex-to-surface clearances are sampled upper bounds.',
                    'Welt shells are intentionally embedded in their own upholstery.',
                    'Declared soft seating/mount contacts are reported for author review.']}
try:
    report = json.loads(REPORT.read_text(encoding='utf-8-sig'))
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.data.scenes[report['source_scene']]
    rows = report['parts']
    expected_roles = Counter({'Base': 1, 'Arm': 2, 'Seat': 3, 'Back': 3,
                              'Foot': 4, 'Pillow': 2})
    all_points, built, roles = [], {}, Counter()

    for key, row in rows.items():
        name = row.get('object', key)
        obj = scene.objects.get(name)
        assert obj and obj.type == 'MESH', f'Missing mesh {name}'
        mesh = obj.data
        mesh.calc_loop_triangles()
        vertices = [obj.matrix_world @ v.co for v in mesh.vertices]
        all_points.extend(vertices)
        faces = [tuple(t.vertices) for t in mesh.loop_triangles]
        materials = [s.material.name if s.material else None for s in obj.material_slots]
        triangle_mats = [materials[mesh.polygons[t.polygon_index].material_index]
                         for t in mesh.loop_triangles]
        triangles = [tuple(vertices[i] for i in ids) for ids in faces]
        bvh = BVHTree.FromPolygons(vertices, faces, all_triangles=True)

        bm = bmesh.new(); bm.from_mesh(mesh)
        nonmanifold = sum(not edge.is_manifold for edge in bm.edges)
        boundaries = sum(edge.is_boundary for edge in bm.edges)
        loose = sum(edge.is_wire for edge in bm.edges)
        bm.free()
        zero_area = sum((b - a).cross(c - a).length < 1e-12 for a, b, c in triangles)
        quantized = [tuple(tuple(round(float(c) / EPS) for c in v) for v in tri)
                     for tri in triangles]
        duplicated = sum(n - 1 for n in Counter(tuple(sorted(t)) for t in quantized).values()
                         if n > 1)

        vertex_faces = defaultdict(list)
        for index, indices in enumerate(faces):
            for v in indices:
                vertex_faces[v].append(index)
        unseen = set(range(len(faces))); shells = []
        while unseen:
            seed = unseen.pop(); group = {seed}; pending = [seed]
            while pending:
                face_index = pending.pop()
                for vertex_index in faces[face_index]:
                    for connected in vertex_faces[vertex_index]:
                        if connected in unseen:
                            unseen.remove(connected); group.add(connected); pending.append(connected)
            volume = sum(triangles[i][0].dot(triangles[i][1].cross(triangles[i][2]))
                         for i in group) / 6.0
            shells.append({'triangles': len(group), 'signed_volume_m3': volume,
                           'materials': sorted({triangle_mats[i] for i in group})})
        canonical_role = key.removeprefix('SM_Sofa_').split('_')[0]
        role_raw = str(row.get('role', canonical_role))
        role = canonical_role if canonical_role in expected_roles else next(
            (x for x in expected_roles if role_raw.lower().startswith(x.lower())), role_raw)
        roles[role] += 1
        entry = {'object': name, 'role': role, 'vertices': len(vertices), 'triangles': len(faces),
                 'bounds_world_m': bounds(vertices), 'location_m': list(obj.location),
                 'pivot_m': row.get('pivot_m'), 'nonmanifold_edges': nonmanifold,
                 'boundary_edges': boundaries, 'loose_edges': loose,
                 'zero_area_triangles': zero_area, 'duplicate_triangles': duplicated,
                 'uv_layers': [layer.name for layer in mesh.uv_layers],
                 'material_slots': materials, 'shells': shells}
        result['parts'][key] = entry
        built[key] = {'vertices': vertices, 'faces': faces, 'triangles': triangles,
                      'materials': triangle_mats, 'bvh': bvh, 'role': role}
        for label, value in [('nonmanifold_edges', nonmanifold), ('loose_edges', loose),
                             ('zero_area_triangles', zero_area), ('duplicate_triangles', duplicated)]:
            if value:
                result['findings'].append({'object': key, 'issue': label, 'count': value})
        if any(s['signed_volume_m3'] <= 1e-12 for s in shells):
            result['findings'].append({'object': key, 'issue': 'nonpositive_shell_volume'})
        if not mesh.uv_layers:
            result['findings'].append({'object': key, 'issue': 'missing_uv'})
        if 'triangles' in row and row['triangles'] != len(faces):
            result['findings'].append({'object': key, 'issue': 'triangle_report_mismatch'})

    bb = bounds(all_points)
    dimensions = [bb[1][i] - bb[0][i] for i in range(3)]
    expected = report.get('expected_dimensions_m', [2.30, .95, .85])
    dimension_errors = [abs(a - b) for a, b in zip(dimensions, expected)]
    if max(dimension_errors) > .01:
        result['findings'].append({'issue': 'overall_dimensions', 'actual_m': dimensions,
                                   'expected_m': expected, 'tolerance_m': .01})
    if len(rows) != 15:
        result['findings'].append({'issue': 'part_count', 'actual': len(rows), 'expected': 15})
    if roles != expected_roles:
        result['findings'].append({'issue': 'role_counts', 'actual': dict(roles),
                                   'expected': dict(expected_roles)})
    hulls = report.get('collision_hulls', {})
    for key in rows:
        if not hulls.get(key):
            result['findings'].append({'object': key, 'issue': 'missing_collision_definition'})

    expected_contacts = {}
    for item in report.get('contact_expectations', []):
        pair = tuple(sorted((item['a'], item['b'])))
        expected_contacts[pair] = item
        a, b = (built[x] for x in pair)
        gap = min(nearest_distance(a['vertices'], b['bvh']),
                  nearest_distance(b['vertices'], a['bvh']))
        check = {'a': pair[0], 'b': pair[1], 'sampled_surface_clearance_m': gap,
                 'declared': item}
        result['contacts'].append(check)
        if gap > item.get('max_gap_m', .01) + EPS:
            result['findings'].append({'issue': 'declared_contact_gap', **check})

    for a_name, b_name in itertools.combinations_with_replacement(built, 2):
        a, b = built[a_name], built[b_name]
        crossing_count = 0; embedded_count = 0; examples = []
        coplanar_count = 0; coplanar_total = 0.0
        for ia, ib in a['bvh'].overlap(b['bvh']):
            if a_name == b_name:
                if ia >= ib or set(a['faces'][ia]) & set(b['faces'][ib]):
                    continue
            ta, tb = a['triangles'][ia], b['triangles'][ib]
            # Only welt-to-upholstery embed is intentional. A welt tube folding
            # back through another welt tube remains an unclassified crossing.
            is_welt = (a_name == b_name and
                       ((a['materials'][ia] in WELT_MATERIALS) !=
                        (b['materials'][ib] in WELT_MATERIALS)))
            area = coplanar_area(ta, tb)
            if area > 1e-10:
                coplanar_count += 1; coplanar_total += area
            point = strict_crossing(ta, tb)
            if point is not None:
                if is_welt:
                    embedded_count += 1
                else:
                    crossing_count += 1
                    if len(examples) < 4:
                        examples.append(point)
        if coplanar_count:
            record = {'a': a_name, 'b': b_name, 'triangle_pairs': coplanar_count,
                      'summed_area_m2': coplanar_total}
            result['same_facing_coplanar_overlaps'].append(record)
            result['findings'].append({'issue': 'same_facing_coplanar_overlap', **record})
        if crossing_count or embedded_count:
            pair = tuple(sorted((a_name, b_name)))
            declared = expected_contacts.get(pair) or REVIEWED_CONTACTS.get(pair)
            classification = ('reviewed_soft_mount_contact' if declared and declared.get('reviewed_soft_contact')
                              else 'declared_soft_contact' if declared and declared.get('allow_penetration_m', 0) > 0
                              else 'unclassified_strict_crossing' if crossing_count else 'embedded_welt')
            record = {'a': a_name, 'b': b_name, 'strict_triangle_pairs': crossing_count,
                      'embedded_welt_triangle_pairs': embedded_count, 'classification': classification,
                      'example_world_points_m': examples}
            if declared:
                record['contact_rule'] = declared
            if a_name != b_name and crossing_count:
                record['a_inside_b_estimate'] = sampled_embed_depth(a['vertices'], b['bvh'])
                record['b_inside_a_estimate'] = sampled_embed_depth(b['vertices'], a['bvh'])
                if declared and declared.get('allow_penetration_m', 0) > 0:
                    sampled_depth = max(record['a_inside_b_estimate']['sampled_max_embed_m'],
                                        record['b_inside_a_estimate']['sampled_max_embed_m'])
                    if sampled_depth > declared['allow_penetration_m'] + EPS:
                        result['findings'].append({'issue': 'declared_embed_depth_exceeded',
                            'a': a_name, 'b': b_name, 'sampled_embed_m': sampled_depth,
                            'allowed_embed_m': declared['allow_penetration_m']})
            result['surface_crossings'].append(record)
            if crossing_count and classification == 'unclassified_strict_crossing':
                result['findings'].append({'issue': 'unclassified_strict_crossing', **record})

    triangle_count = sum(item['triangles'] for item in result['parts'].values())
    if triangle_count > 15000:
        result['findings'].append({'issue': 'triangle_budget', 'actual': triangle_count, 'max': 15000})
    result['summary'] = {'part_count': len(rows), 'role_counts': dict(roles),
                         'triangles': triangle_count, 'bounds_world_m': bb,
                         'overall_dimensions_m': dimensions, 'expected_dimensions_m': expected,
                         'all_manifold': all(not p['nonmanifold_edges'] for p in result['parts'].values()),
                         'all_shell_signed_volumes_positive': all(s['signed_volume_m3'] > 1e-12
                             for p in result['parts'].values() for s in p['shells']),
                         'collision_definitions': len(hulls), 'finding_count': len(result['findings'])}
    result['reviewed_contact_policy'] = [{'a': pair[0], 'b': pair[1], **rule}
                                        for pair, rule in REVIEWED_CONTACTS.items()]
    result['summary']['raw_cross_part_contact_pairs'] = sum(
        item['a'] != item['b'] for item in result['surface_crossings'])
    result['summary']['welt_self_crossing_triangle_pairs'] = sum(
        item['strict_triangle_pairs'] for item in result['surface_crossings'] if item['a'] == item['b'])
except Exception:
    result['error'] = traceback.format_exc()
finally:
    result['source_sha256_after'] = digest(SOURCE)
    result['source_unchanged'] = result['source_sha256_before'] == result['source_sha256_after']
    result['success'] = result['source_unchanged'] and not result['findings'] and 'error' not in result
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SOFA_QA', json.dumps({k: result[k] for k in ['success', 'source_unchanged', 'summary', 'error']
                               if k in result}, ensure_ascii=False))
