"""Independent read-only attribution of Native render holes to source faces.

Success means the failed Native topology is explained, never asset acceptance.
Binary FBX is read independently and matched to every surviving Native face.
No Unreal, Blender, assets, import settings, or acceptance predicates are edited.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
import hashlib
import json
import math
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts'))
from ValidateOldTownRealismSourceSolids import fbx_mesh

WORK = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012'
ART = ROOT / 'SourceArt/OldTownRealism_20261012'
POSITION_TOLERANCE_CM = 2e-5


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


def key(p):
    return tuple(f32(x) for x in p)


def edges(faces):
    result = Counter()
    for face in faces:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            result[tuple(sorted((face[a], face[b])))] += 1
    return result


def cross(points):
    a, b, c = points
    u = [b[i]-a[i] for i in range(3)]
    v = [c[i]-a[i] for i in range(3)]
    return (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])


def main():
    initial_path = WORK / 'NativeClosedSolidDiagnostic.json'
    initial = read(initial_path)
    failed = [r for r in initial['rows'] if r['exact_odd_edges']]
    assert len(failed) == 22
    inputs = {str(initial_path): sha(initial_path)}
    variants = {}
    for category in ('Furniture', 'Architecture', 'Sanitary', 'Street'):
        manifest_path = ART / category / 'ModelDataManifest.json'
        manifest = read(manifest_path)
        inputs[str(manifest_path)] = sha(manifest_path)
        for variant in manifest['variants']:
            variants[variant['mesh_name']] = (category, variant)
    rows = []
    for item in failed:
        name = item['asset'].rsplit('.', 1)[-1]
        category, variant = variants[name]
        native_paths = list((WORK / 'AppearanceNative/NativeMeshes').glob(name + '_*.json'))
        assert len(native_paths) == 1
        native_path = native_paths[0]
        recipe_path = Path(variant['geometry_recipe_file'])
        fbx_path = Path(variant['fbx_file'])
        if not fbx_path.is_absolute():
            fbx_path = ART / category / fbx_path
        for path in (native_path, recipe_path, fbx_path):
            inputs[str(path.resolve())] = sha(path)
        native, recipe, binary = read(native_path), read(recipe_path), fbx_mesh(fbx_path)
        assert native['asset'] == item['asset']
        assert sha(native_path) == item['geometry_sha256']
        assert binary['triangles'] == recipe['triangles']
        source_vertices = [tuple(x*100 for x in p) for p in binary['vertices']]
        assert len(source_vertices) == len(recipe['vertices_cm'])
        max_fbx_recipe_error = max(abs(a[i]-b[i]) for a, b in
            zip(source_vertices, recipe['vertices_cm']) for i in range(3))
        assert max_fbx_recipe_error < 2e-5
        # Each source coordinate is the original native-centimetre float32.
        # Actual render points differ by small import conversion ULPs. Match by
        # measured distance, then demand a vertex and face bijection.
        source_keys = {key(p) for p in source_vertices}
        buckets = defaultdict(list)
        cell = lambda p: tuple(math.floor(x/POSITION_TOLERANCE_CM) for x in p)
        for point in source_keys:
            buckets[cell(point)].append(point)
        native_keys = {tuple(p) for section in native['sections'] for p in section['vertices_cm']}
        mapping, errors, ambiguity_count = {}, [], 0
        for point in native_keys:
            at = cell(point)
            candidates = []
            for delta in product((-1, 0, 1), repeat=3):
                for other in buckets.get(tuple(at[i]+delta[i] for i in range(3)), ()):
                    error = max(abs(point[i]-other[i]) for i in range(3))
                    if error <= POSITION_TOLERANCE_CM:
                        distance2 = sum((point[i]-other[i])**2 for i in range(3))
                        candidates.append((distance2, error, other))
            candidates.sort()
            if not candidates:
                errors.append(dict(kind='no_source_coordinate_candidate', native_coordinate=point))
                continue
            ambiguity_count += len(candidates) > 1
            mapping[point] = candidates[0][2]
        collisions = len(mapping)-len(set(mapping.values()))
        if collisions:
            errors.append(dict(kind='nearest_coordinate_mapping_not_bijective', collisions=collisions))
        source_faces = [tuple(sorted(key(source_vertices[i]) for i in triangle)) for triangle in binary['triangles']]
        native_faces = []
        unmapped_face_count = 0
        for section in native['sections']:
            indices, vertices = section['triangle_indices'], section['vertices_cm']
            for start in range(0, len(indices), 3):
                pts = [tuple(vertices[i]) for i in indices[start:start+3]]
                if any(p not in mapping for p in pts):
                    unmapped_face_count += 1
                    continue
                native_faces.append(tuple(sorted(mapping[p] for p in pts)))
        sc, nc = Counter(source_faces), Counter(native_faces)
        missing, added = sc-nc, nc-sc
        missing_remaining = missing.copy()
        missing_rows = []
        for index, face in enumerate(source_faces):
            if not missing_remaining[face]:
                continue
            missing_remaining[face] -= 1
            triangle = binary['triangles'][index]
            points = [source_vertices[i] for i in triangle]
            pairs = [(points[a], points[b]) for a, b in ((0, 1), (1, 2), (2, 0))]
            minimum_max_axis_distance = min(max(abs(a[i]-b[i]) for i in range(3)) for a, b in pairs)
            minimum_edge = min(math.sqrt(sum((a[i]-b[i])**2 for i in range(3))) for a, b in pairs)
            physical = [[p[i]*recipe['physical_scale'][i] for i in range(3)] for p in points]
            cr = cross(points)
            cp = cross(physical)
            missing_rows.append(dict(source_triangle_index=index, vertex_indices=triangle,
                source_points_local_cm=points, material_index=binary['material_indices'][index],
                material_role=recipe['material_roles'][binary['material_indices'][index]],
                minimum_local_edge_length_cm=minimum_edge,
                minimum_local_edge_max_axis_distance_cm=minimum_max_axis_distance,
                local_area2_cm2=math.sqrt(sum(x*x for x in cr)),
                physical_area2_cm2=math.sqrt(sum(x*x for x in cp))))
        source_odd = sum(n % 2 for n in edges(source_faces).values())
        native_odd = sum(n % 2 for n in edges(native_faces).values())
        restored_odd = sum(n % 2 for n in edges(native_faces + list(missing.elements())).values())
        extra = sum(added.values())
        verified = (not errors and not unmapped_face_count and not extra and source_odd == 0 and
            native_odd == item['exact_odd_edges'] and restored_odd == 0 and
            len(source_faces)-len(native_faces) == len(missing_rows))
        rows.append(dict(category=category, mesh_name=name, asset=item['asset'],
            diagnosis_complete=verified, native_acceptance_passed=False,
            source_triangle_count=len(source_faces), native_triangle_count=len(native_faces),
            missing_source_face_count=len(missing_rows), native_unprescribed_face_count=extra,
            source_odd_edges=source_odd, actual_native_odd_edges=native_odd,
            restored_source_faces_odd_edges=restored_odd, source_vertex_count=len(source_keys),
            native_vertex_count=len(native_keys), coordinate_candidate_ambiguity_count=ambiguity_count,
            coordinate_mapping_collisions=collisions, unmapped_native_face_count=unmapped_face_count,
            maximum_source_native_coordinate_error_cm=max((max(abs(p[i]-q[i]) for i in range(3))
                for p, q in mapping.items()), default=None),
            maximum_binary_fbx_recipe_coordinate_error_cm=max_fbx_recipe_error,
            source_faces_lost_with_min_edge_max_axis_below_00002cm=sum(
                r['minimum_local_edge_max_axis_distance_cm'] <= .00002 for r in missing_rows),
            minimum_deleted_edge_cm=min((r['minimum_local_edge_length_cm'] for r in missing_rows), default=None),
            maximum_deleted_minimum_edge_cm=max((r['minimum_local_edge_length_cm'] for r in missing_rows), default=None),
            missing_face_material_counts=dict(Counter(r['material_role'] for r in missing_rows)),
            errors=errors, missing_faces=missing_rows))
        print(name, len(source_faces), len(native_faces), 'missing', len(missing_rows),
            'extra', extra, 'odd', source_odd, native_odd, restored_odd, 'verified', verified, flush=True)
    report = dict(schema='OldTownRealismIndependentNativeSourceFaceLossDiagnosisV1',
        passed=all(r['diagnosis_complete'] for r in rows),
        result_meaning='exact attribution of failed Native closure, not acceptance of these meshes',
        created_utc=datetime.now(timezone.utc).isoformat(), map_sha256=initial['map_sha256'],
        source_model_count=len(rows), total_missing_source_faces=sum(r['missing_source_face_count'] for r in rows),
        all_surviving_native_faces_match_source=all(r['native_unprescribed_face_count'] == 0 and
            r['unmapped_native_face_count'] == 0 for r in rows),
        coordinate_distance_budget_cm=POSITION_TOLERANCE_CM,
        input_sha256=inputs, diagnostic_script_file=str(Path(__file__).resolve()),
        diagnostic_script_sha256=sha(Path(__file__)), rows=rows)
    (WORK / 'NativeSourceFaceLossDiagnosis.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('COMPLETE', report['passed'], len(rows), report['total_missing_source_faces'], flush=True)


if __name__ == '__main__':
    main()
