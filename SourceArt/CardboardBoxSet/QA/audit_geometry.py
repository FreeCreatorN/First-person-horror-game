"""Read-only independent audit of exact authored leaf meshes, not collections."""
import bpy, bmesh, json, hashlib, math
from pathlib import Path
from collections import defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'CardboardBoxSet.blend'
SOURCE_SHA = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
R = json.loads((ROOT / 'model_report.json').read_text(encoding='utf-8-sig'))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
S = bpy.data.scenes[R['source_scene']]
S.frame_set(1)
bpy.context.view_layer.update()
EPS = 2e-6
RESULT = {'source': str(SOURCE), 'source_sha256': SOURCE_SHA, 'read_only': True,
          'parts': {}, 'coplanar_method': 'Same-facing coplanar triangle intersections across different parts/shells; opposite-normal assembly contacts excluded.'}
TRIS = []


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def area(poly):
    return abs(sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(poly, poly[1:] + poly[:1]))) * .5 if len(poly) > 2 else 0


def clip(subject, boundary):
    result = subject
    if cross(*boundary) < 0:
        boundary = list(reversed(boundary))
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        old = result
        result = []
        if not old:
            break
        for p, q in zip(old, old[1:] + old[:1]):
            cp, cq = cross(a, b, p), cross(a, b, q)
            ip, iq = cp >= -1e-12, cq >= -1e-12
            if ip:
                result.append(p)
            if ip != iq:
                t = cp / (cp - cq)
                result.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return result


def hits(bvh, origin, direction, limit=2.0):
    origin, direction = Vector(origin), Vector(direction).normalized()
    result = []
    total = 0
    for _ in range(30):
        loc, normal, index, dist = bvh.ray_cast(origin, direction, limit - total)
        if loc is None:
            break
        result.append({'position_m': list(loc), 'normal': list(normal), 'face_index': index, 'distance_from_start_m': total + dist})
        origin = loc + direction * 1e-6
        total += dist + 1e-6
        if total >= limit:
            break
    return result


for key, row in R['parts'].items():
    o = S.objects[row['object']]
    assert o.type == 'MESH'
    me = o.data
    me.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    adjacent = defaultdict(set)
    for e in me.edges:
        a, b = e.vertices
        adjacent[a].add(b)
        adjacent[b].add(a)
    comp, shells = {}, []
    for v in me.vertices:
        if v.index in comp:
            continue
        si = len(shells)
        todo, ids = [v.index], []
        while todo:
            j = todo.pop()
            if j in comp:
                continue
            comp[j] = si
            ids.append(j)
            todo.extend(adjacent[j] - comp.keys())
        vertex_ids = set(ids)
        es = [e for e in me.edges if e.vertices[0] in vertex_ids]
        ps = [p for p in me.polygons if p.vertices[0] in vertex_ids]
        shell_tris = [t for t in me.loop_triangles if t.vertices[0] in vertex_ids]
        vol = sum(me.vertices[t.vertices[0]].co.dot(me.vertices[t.vertices[1]].co.cross(me.vertices[t.vertices[2]].co)) / 6 for t in shell_tris)
        chi = len(ids) - len(es) + len(ps)
        points = [me.vertices[j].co for j in ids]
        shells.append({'index': si, 'vertices': len(ids), 'edges': len(es), 'faces': len(ps),
                       'euler_characteristic': chi, 'genus_if_closed_orientable': (2 - chi) / 2,
                       'signed_volume_m3': vol,
                       'min_local_m': [min(p[i] for p in points) for i in range(3)],
                       'max_local_m': [max(p[i] for p in points) for i in range(3)]})
    bvh = BVHTree.FromBMesh(bm)
    samples = []
    # Broad faces avoid measuring the intentional narrow bevel rather than panel thickness.
    for t in me.loop_triangles:
        p = me.polygons[t.polygon_index]
        if p.area < .003:
            continue
        a, b, c = [me.vertices[j].co for j in t.vertices]
        tn = (b - a).cross(c - a).normalized()
        center = (a + b + c) / 3
        inward = -tn
        loc, normal, index, distance = bvh.ray_cast(center + inward * 1e-6, inward, 2.0)
        if loc is not None:
            samples.append({'face_index': p.index, 'face_area_m2': p.area, 'distance_m': distance + 1e-6,
                            'normal': list(tn), 'from_local_m': list(center)})
    part_result = {'object': o.name, 'variant': row['variant'], 'vertices': len(me.vertices),
                   'triangles': len(me.loop_triangles), 'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
                   'boundary_edges': sum(e.is_boundary for e in bm.edges), 'loose_edges': sum(e.is_wire for e in bm.edges),
                   'zero_area_faces': sum(p.area < 1e-12 for p in me.polygons),
                   'signed_volume_m3': bm.calc_volume(signed=True), 'shells': shells,
                   'broad_face_inward_ray_min_m': min((a['distance_m'] for a in samples), default=None),
                   'broad_face_thickness_samples': samples,
                   'uv_layer': me.uv_layers.active.name if me.uv_layers.active else None,
                   'material_slots': [m.name for m in me.materials]}
    if key == 'C_Body':
        # Object-local coordinates are body coordinates. The preview parent translation is intentionally absent.
        center_ray = hits(bvh, (0, -.25, .222), (0, 1, 0), .5)
        adjacent_ray = hits(bvh, (.09, -.25, .222), (0, 1, 0), .5)
        below_ray = hits(bvh, (0, -.25, .195), (0, 1, 0), .5)
        front_axis_hits = []
        for j in range(-90, 91):
            xx = j * .001
            h = hits(bvh, (xx, -.25, .222), (0, 1, 0), .5)
            if not h:
                front_axis_hits.append(xx)
        vertical_hits = []
        for j in range(180, 266):
            zz = j * .001
            h = hits(bvh, (0, -.25, zz), (0, 1, 0), .5)
            if not h:
                vertical_hits.append(zz)
        hole_result = {'center_ray_origin_m': [0, -.25, .222], 'center_ray_direction': [0, 1, 0],
                       'center_ray_hits': center_ray, 'adjacent_x_090m_ray_hits': adjacent_ray,
                       'below_z_195m_ray_hits': below_ray,
                       'center_is_clear_through_both_front_and_back': len(center_ray) == 0,
                       'adjacent_solid_has_four_surface_hits': len(adjacent_ray) == 4,
                       'below_solid_has_four_surface_hits': len(below_ray) == 4,
                       'horizontal_clear_sample_interval_m': [min(front_axis_hits), max(front_axis_hits)] if front_axis_hits else None,
                       'vertical_clear_sample_interval_m': [min(vertical_hits), max(vertical_hits)] if vertical_hits else None,
                       'sample_resolution_m': .001,
                       'two_real_apertures_topology': len(shells) == 1 and shells[0]['genus_if_closed_orientable'] == 2}
        RESULT['storage_handholes'] = hole_result
    if key in ('F_Fruit', 'G_Water', 'H_Noodles'):
        center_ray = hits(bvh, (-.34, 0, .222), (1, 0, 0), .68)
        adjacent_ray = hits(bvh, (-.34, .08, .222), (1, 0, 0), .68)
        below_ray = hits(bvh, (-.34, 0, .195), (1, 0, 0), .68)
        horizontal_clear, vertical_clear = [], []
        for j in range(-80, 81):
            yy = j * .001
            if not hits(bvh, (-.34, yy, .222), (1, 0, 0), .68):
                horizontal_clear.append(yy)
        for j in range(190, 256):
            zz = j * .001
            if not hits(bvh, (-.34, 0, zz), (1, 0, 0), .68):
                vertical_clear.append(zz)
        RESULT.setdefault('branded_short_side_handholes', {})[key] = {
            'center_ray_origin_m': [-.34, 0, .222], 'center_ray_direction': [1, 0, 0],
            'center_ray_hits': center_ray,
            'adjacent_y_080m_ray_hits': adjacent_ray, 'below_z_195m_ray_hits': below_ray,
            'center_is_clear_through_both_short_sides': len(center_ray) == 0,
            'adjacent_solid_has_four_surface_hits': len(adjacent_ray) == 4,
            'below_solid_has_four_surface_hits': len(below_ray) == 4,
            'horizontal_clear_sample_interval_m': [min(horizontal_clear), max(horizontal_clear)] if horizontal_clear else None,
            'vertical_clear_sample_interval_m': [min(vertical_clear), max(vertical_clear)] if vertical_clear else None,
            'two_real_apertures_topology': sum(a['genus_if_closed_orientable'] == 2 for a in shells) == 1,
            'sample_resolution_m': .001}
    RESULT['parts'][key] = part_result
    for t in me.loop_triangles:
        p = [o.matrix_world @ me.vertices[i].co for i in t.vertices]
        n = (p[1] - p[0]).cross(p[2] - p[0]).normalized()
        axis = max(range(3), key=lambda i: abs(n[i]))
        plane = n.dot(p[0])
        other = [i for i in range(3) if i != axis]
        poly = [(float(v[other[0]]), float(v[other[1]])) for v in p]
        TRIS.append({'part': key, 'variant': row['variant'], 'object': o.name, 'shell': comp[t.vertices[0]],
                     'polygon': t.polygon_index, 'triangle': t.index, 'normal': list(n), 'plane': plane,
                     'axis': axis, 'poly': poly,
                     'min': [min(v[i] for v in poly) for i in range(2)],
                     'max': [max(v[i] for v in poly) for i in range(2)]})
    bm.free()

groups = defaultdict(list)
for t in TRIS:
    groups[tuple(round(a, 4) for a in t['normal']) + (round(t['plane'], 5),)].append(t)
overlaps = []
for bucket in groups.values():
    for i, a in enumerate(bucket):
        for b in bucket[i + 1:]:
            if a['object'] == b['object'] and a['shell'] == b['shell']:
                continue
            if abs(a['plane'] - b['plane']) > EPS:
                continue
            if any(min(a['max'][j], b['max'][j]) - max(a['min'][j], b['min'][j]) <= EPS for j in range(2)):
                continue
            clipped = clip(a['poly'], b['poly'])
            # Restore area projected away from the dominant normal axis.
            ar = area(clipped) / max(abs(a['normal'][a['axis']]), 1e-12)
            if ar < 1e-9:
                continue
            overlaps.append({'a': {k: a[k] for k in ('part', 'shell', 'polygon', 'triangle')},
                             'b': {k: b[k] for k in ('part', 'shell', 'polygon', 'triangle')},
                             'normal': a['normal'], 'plane_m': a['plane'], 'overlap_area_m2': ar})
RESULT['same_facing_coplanar_overlaps'] = overlaps
RESULT['same_facing_coplanar_area_m2'] = sum(o['overlap_area_m2'] for o in overlaps)
RESULT['summary'] = {'exact_leaf_meshes': len(RESULT['parts']),
                     'triangles': sum(a['triangles'] for a in RESULT['parts'].values()),
                     'all_closed_manifold': all(a['nonmanifold_edges'] == 0 for a in RESULT['parts'].values()),
                     'all_shell_signed_volumes_positive': all(s['signed_volume_m3'] > 0 for a in RESULT['parts'].values() for s in a['shells']),
                     'all_faces_nonzero_area': all(a['zero_area_faces'] == 0 for a in RESULT['parts'].values()),
                     'same_facing_coplanar_overlap_pairs': len(overlaps),
                     'storage_real_handholes_verified': all(RESULT['storage_handholes'][k] for k in (
                         'center_is_clear_through_both_front_and_back', 'adjacent_solid_has_four_surface_hits',
                         'below_solid_has_four_surface_hits', 'two_real_apertures_topology'))}
if 'branded_short_side_handholes' in RESULT:
    RESULT['summary']['branded_real_handholes_verified'] = all(all(a[k] for k in (
        'center_is_clear_through_both_short_sides', 'adjacent_solid_has_four_surface_hits',
        'below_solid_has_four_surface_hits', 'two_real_apertures_topology'))
        for a in RESULT['branded_short_side_handholes'].values())
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
out = ROOT / 'QA' / 'geometry_audit.json'
out.write_text(json.dumps(RESULT, ensure_ascii=False, indent=2), encoding='utf-8')
print('GEOMETRY_AUDIT', json.dumps(RESULT['summary']), flush=True)
print('WALLS', json.dumps({k: v['broad_face_inward_ray_min_m'] for k, v in RESULT['parts'].items()}), flush=True)
print('HANDHOLES', json.dumps(RESULT['storage_handholes']), flush=True)
