"""Read-only assembly and exported convex-collision checks.

Opens Clipboard.blend and imports the three FBXs in memory. It never saves the
Blender source or rewrites an export. Distances and tolerances are in meters.
"""
import hashlib
import json
import time
import traceback
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'Clipboard.blend'
PARTS = ('SM_Clipboard_Board', 'SM_Clipboard_Clip', 'SM_Clipboard_Paper')
PAPER = 'SM_Clipboard_Paper'
# A numerical inset, not a modeling allowance: 0.2 micrometers. The designed
# pressure-pad clearance is 5 micrometers and remains explicitly measured.
INSET = .0000002
report = {'success': False, 'errors': [], 'warnings': [], 'units': 'meters',
          'numerical_collision_inset_m': INSET, 'source_mesh_contacts': {},
          'pressure_strip': {}, 'fbx': {}, 'main_file_saved': False}
started = time.perf_counter()


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def geometry(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        polys = [tuple(poly.vertices) for poly in mesh.polygons]
    finally:
        evaluated.to_mesh_clear()
    assert vertices and triangles, obj.name
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True, epsilon=0.)
    bounds = [(min(vertex[axis] for vertex in vertices), max(vertex[axis] for vertex in vertices))
              for axis in range(3)]
    return {'object': obj.name, 'vertices': vertices, 'triangles': triangles,
            'polygons': polys, 'tree': tree, 'bounds': bounds}


def overlaps(a, b):
    pairs = a['tree'].overlap(b['tree'])
    return {'triangle_intersection_count': len(pairs),
            'first_triangle_pairs': [list(pair) for pair in pairs[:12]]}


def nearest_vertices(a, b):
    best = None
    for point in a['vertices']:
        location, normal, index, distance = b['tree'].find_nearest(point)
        if location is not None and (best is None or distance < best['distance_m']):
            best = {'distance_m': distance, 'point_a_m': list(point),
                    'point_b_m': list(location), 'triangle_b': index}
    return best


def bounds_overlap(a, b, inset=0.):
    return all(a[axis][1] >= b[axis][0] + inset and b[axis][1] >= a[axis][0] + inset
               for axis in range(3))


def convex_planes(hull):
    center = sum(hull['vertices'], Vector()) / len(hull['vertices'])
    planes, unique = [], set()
    for face in hull['polygons']:
        a, b, c = (hull['vertices'][index] for index in face[:3])
        normal = (b - a).cross(c - a)
        if normal.length < 1.e-14:
            continue
        normal.normalize()
        if normal.dot(center - a) > 0:
            normal.negate()
        offset = normal.dot(a)
        key = tuple(round(value, 7) for value in (*normal, offset))
        if key not in unique:
            planes.append((normal, offset))
            unique.add(key)
    assert len(planes) >= 4, hull['object']
    # Every hull vertex must lie inside every outward plane. These exported
    # UCX meshes are convex; fail rather than treating an invalid mesh as UCX.
    assert all(normal.dot(vertex) - offset < 1.e-6 for vertex in hull['vertices']
               for normal, offset in planes), ('UCX is not convex', hull['object'])
    return planes


def clipped_triangle(triangle, planes):
    polygon = list(triangle)
    for normal, offset in planes:
        if not polygon:
            break
        previous = polygon[-1]
        previous_d = normal.dot(previous) - offset + INSET
        output = []
        for current in polygon:
            current_d = normal.dot(current) - offset + INSET
            current_in, previous_in = current_d <= 0., previous_d <= 0.
            if current_in != previous_in:
                denominator = previous_d - current_d
                if abs(denominator) > 1.e-16:
                    output.append(previous + (current - previous) * (previous_d / denominator))
            if current_in:
                output.append(current)
            previous, previous_d = current, current_d
        polygon = output
    if len(polygon) < 3:
        return 0.
    return sum((polygon[index] - polygon[0]).cross(polygon[index + 1] - polygon[0]).length * .5
               for index in range(1, len(polygon) - 1))


def collision_against_paper(hull, paper):
    info = {'object': hull['object'], 'aabb_overlaps_paper': bounds_overlap(hull['bounds'], paper['bounds']),
            'paper_triangles_inside_inset_hull': 0, 'paper_surface_area_inside_inset_hull_m2': 0.,
            'first_penetrating_paper_triangles': []}
    if not info['aabb_overlaps_paper']:
        return info
    planes = convex_planes(hull)
    info['outward_convex_planes'] = len(planes)
    for index, indices in enumerate(paper['triangles']):
        area = clipped_triangle([paper['vertices'][vertex] for vertex in indices], planes)
        if area > 1.e-14:
            info['paper_triangles_inside_inset_hull'] += 1
            info['paper_surface_area_inside_inset_hull_m2'] += area
            if len(info['first_penetrating_paper_triangles']) < 12:
                info['first_penetrating_paper_triangles'].append(index)
    return info


tracked = [SOURCE] + [OUT / (name + '.fbx') for name in PARTS]
hashes_before = {str(path): sha256(path) for path in tracked}
try:
    model = json.loads((OUT / 'model_report.json').read_text(encoding='utf-8-sig'))
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    canonical = bpy.data.collections['UE meshes - canonical origins']
    canonical.hide_viewport = False
    canonical.hide_render = False
    for obj in canonical.all_objects:
        obj.hide_set(False)
    bpy.context.view_layer.update()
    originals = {name: geometry(bpy.data.objects[name]) for name in PARTS}
    paper = originals[PAPER]
    for name in PARTS[:2]:
        check = overlaps(paper, originals[name])
        report['source_mesh_contacts'][name] = check
        if check['triangle_intersection_count']:
            report['errors'].append('Paper intersects canonical mesh ' + name)
    # The preserved individual source strip has its own bevel modifier. Its
    # evaluated underside vertices measure the actual intended 5 um clearance.
    source = bpy.data.collections['SOURCE - individual components']
    source.hide_viewport = False
    strips = [obj for obj in source.all_objects if obj.name.startswith('Paper pressure edge')]
    assert len(strips) == 1, [obj.name for obj in strips]
    bpy.context.view_layer.update()
    strip = geometry(strips[0])
    report['pressure_strip'] = {'object': strips[0].name, **overlaps(strip, paper),
                                'nearest_evaluated_strip_vertex_to_paper': nearest_vertices(strip, paper),
                                'designed_gap_m': .000005}
    gap = report['pressure_strip']['nearest_evaluated_strip_vertex_to_paper']['distance_m']
    if report['pressure_strip']['triangle_intersection_count'] or gap < .000003 or gap > .000008:
        report['errors'].append('Pressure strip contact differs from the designed 5 micrometer clearance')

    for name in PARTS:
        before = set(bpy.data.objects)
        result = bpy.ops.import_scene.fbx(filepath=str(OUT / (name + '.fbx')), use_custom_normals=True)
        assert result == {'FINISHED'}, (name, result)
        added = [obj for obj in bpy.data.objects if obj not in before]
        meshes = [obj for obj in added if obj.type == 'MESH' and not obj.name.startswith('UCX_')]
        hulls = [obj for obj in added if obj.type == 'MESH' and obj.name.startswith('UCX_' + name + '_')]
        assert len(meshes) == 1, (name, [obj.name for obj in meshes])
        assert len(hulls) == model['parts'][name]['collision_hulls'], (name, len(hulls))
        bpy.context.view_layer.update()
        imported = geometry(meshes[0])
        dimensions = [(high - low) * 100 for low, high in imported['bounds']]
        errors = [abs(actual - expected) for actual, expected in zip(dimensions, model['parts'][name]['dimensions_cm'])]
        info = {'mesh': meshes[0].name, 'collision_hulls': len(hulls),
                'expected_collision_hulls': model['parts'][name]['collision_hulls'],
                'dimensions_cm': dimensions, 'dimension_errors_cm': errors,
                'foreign_collisions_against_actual_paper': []}
        assert max(errors) < .002, (name, info)
        if name != PAPER:
            info['exported_mesh_against_paper'] = overlaps(imported, paper)
            if info['exported_mesh_against_paper']['triangle_intersection_count']:
                report['errors'].append('Paper intersects exported mesh ' + name)
            for hull_obj in hulls:
                check = collision_against_paper(geometry(hull_obj), paper)
                info['foreign_collisions_against_actual_paper'].append(check)
                if check['paper_triangles_inside_inset_hull']:
                    report['errors'].append('Collision intrudes into actual paper: ' + hull_obj.name)
        else:
            info['own_paper_collision_role'] = 'Paper collision intentionally contains its own paper surface'
            info['exported_paper_against_canonical_parts'] = {part: overlaps(imported, originals[part]) for part in PARTS[:2]}
            if any(check['triangle_intersection_count'] for check in info['exported_paper_against_canonical_parts'].values()):
                report['errors'].append('Exported paper intersects another canonical part')
            info['own_collision_convex_planes'] = {obj.name: len(convex_planes(geometry(obj))) for obj in hulls}
        report['fbx'][name] = info
        for obj in added:
            bpy.data.objects.remove(obj, do_unlink=True)

    report['success'] = not report['errors']
except Exception:
    report['errors'].append(traceback.format_exc())

report['source_sha256_before'] = hashes_before
report['source_sha256_after'] = {str(path): sha256(path) for path in tracked}
report['source_and_exports_unchanged'] = report['source_sha256_before'] == report['source_sha256_after']
if not report['source_and_exports_unchanged']:
    report['errors'].append('Source/export file hashes changed during read-only verification')
    report['success'] = False
report['elapsed_seconds'] = time.perf_counter() - started
(OUT / 'contact_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('CLIPBOARD_CONTACT_VERIFICATION ' + json.dumps(report), flush=True)
if not report['success']:
    raise RuntimeError('Clipboard contact verification failed; inspect contact_verification.json')
