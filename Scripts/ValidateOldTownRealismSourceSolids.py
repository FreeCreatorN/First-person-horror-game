"""Independent, read-only audit of repaired source recipes and binary FBX payloads.

This deliberately does not load Blender or Unreal, and does not consume the
repair's claimed topology/UV/tangent result as evidence. Every calculation is
performed on serialized vertices, polygon corners, UVs and vector layers.
"""
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'SourceArt/OldTownRealism_20261012'
WORK = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012'
EXPECTED = {'Architecture': 82, 'Furniture': 33, 'Sanitary': 4, 'Street': 24}
UV_ZERO_THRESHOLD = 1e-12
VECTOR_TOLERANCE = 2e-5
POSITION_TOLERANCE_CM = 2e-5
UV_SCALE_TOLERANCE = 2e-6


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def dot(a, b):
    return sum(a[i]*b[i] for i in range(3))


def norm(a):
    return math.sqrt(dot(a, a))


def normalize(a):
    length = norm(a)
    if length == 0:
        raise ValueError('Zero vector')
    return tuple(v/length for v in a)


def vector_error(a, b):
    return max(abs(x-y) for x, y in zip(a, b))


class FbxNode:
    def __init__(self, name, properties, children):
        self.name, self.properties, self.children = name, properties, children

    def child(self, name):
        rows = [node for node in self.children if node.name == name]
        if len(rows) != 1:
            raise ValueError(f'Expected one {name!r} in {self.name!r}, got {len(rows)}')
        return rows[0]

    def value(self, name):
        properties = self.child(name).properties
        if len(properties) != 1:
            raise ValueError(f'Expected one value in {name!r}')
        return properties[0]


def parse_fbx(path):
    data = Path(path).read_bytes()
    if data[:23] != b'Kaydara FBX Binary  \x00\x1a\x00':
        raise ValueError('Expected binary FBX')
    version = struct.unpack_from('<I', data, 23)[0]
    cursor = 27
    wide = version >= 7500
    header = '<QQQB' if wide else '<IIIB'
    header_size = struct.calcsize(header)
    scalar_types = {b'Y': '<h', b'C': '<?', b'I': '<i', b'F': '<f', b'D': '<d', b'L': '<q'}
    array_types = {b'f': 'f', b'd': 'd', b'l': 'q', b'i': 'i', b'b': 'b', b'c': 'b'}

    def read_property():
        nonlocal cursor
        kind = data[cursor:cursor+1]
        cursor += 1
        if kind in scalar_types:
            fmt = scalar_types[kind]
            value = struct.unpack_from(fmt, data, cursor)[0]
            cursor += struct.calcsize(fmt)
            return value
        if kind in (b'S', b'R'):
            length = struct.unpack_from('<I', data, cursor)[0]
            cursor += 4
            value = data[cursor:cursor+length]
            cursor += length
            return value
        if kind in array_types:
            length, encoding, size = struct.unpack_from('<III', data, cursor)
            cursor += 12
            raw = data[cursor:cursor+size]
            cursor += size
            if encoding == 1:
                raw = zlib.decompress(raw)
            elif encoding != 0:
                raise ValueError(f'Unknown FBX array encoding {encoding}')
            values = array(array_types[kind])
            values.frombytes(raw)
            if sys.byteorder != 'little':
                values.byteswap()
            if len(values) != length:
                raise ValueError('FBX array length mismatch')
            return values
        raise ValueError(f'Unknown FBX property type {kind!r}')

    def read_node():
        nonlocal cursor
        end, count, prop_size, name_size = struct.unpack_from(header, data, cursor)
        cursor += header_size
        if end == 0:
            return None
        name = data[cursor:cursor+name_size]
        cursor += name_size
        prop_start = cursor
        properties = [read_property() for _ in range(count)]
        if cursor-prop_start != prop_size:
            raise ValueError(f'FBX property byte count mismatch in {name!r}')
        children = []
        while cursor < end:
            node = read_node()
            if node is None:
                break
            children.append(node)
        if cursor != end:
            raise ValueError(f'FBX node end mismatch in {name!r}')
        return FbxNode(name, properties, children)

    nodes = []
    while cursor+header_size <= len(data):
        node = read_node()
        if node is None:
            break
        nodes.append(node)
    return version, FbxNode(b'Root', [], nodes)


def chunks(values, size):
    if len(values) % size:
        raise ValueError('Corner/vector array is not divisible by its dimension')
    return [tuple(values[i:i+size]) for i in range(0, len(values), size)]


def fbx_raw_info(path):
    version, root = parse_fbx(path)
    objects = root.child(b'Objects')
    meshes = [node for node in objects.children if node.name == b'Geometry' and node.properties[2] == b'Mesh']
    models = [node for node in objects.children if node.name == b'Model' and node.properties[2] == b'Mesh']
    if len(meshes) != 1 or len(models) != 1:
        raise ValueError('Expected one FBX geometry and model')
    properties = {node.properties[0]: node.properties[4:] for node in models[0].child(b'Properties70').children if node.name == b'P'}
    settings = {node.properties[0]: node.properties[4:] for node in root.child(b'GlobalSettings').child(b'Properties70').children if node.name == b'P'}
    return dict(vertices=chunks(meshes[0].value(b'Vertices'), 3), model_properties=properties, global_properties=settings)


def fbx_mesh(path):
    version, root = parse_fbx(path)
    objects = root.child(b'Objects')
    meshes = [node for node in objects.children if node.name == b'Geometry' and node.properties[2] == b'Mesh']
    if len(meshes) != 1:
        raise ValueError(f'Expected one FBX mesh, got {len(meshes)}')
    mesh = meshes[0]
    vertices = chunks(mesh.value(b'Vertices'), 3)
    polygons, current = [], []
    for vertex in mesh.value(b'PolygonVertexIndex'):
        current.append(-vertex-1 if vertex < 0 else vertex)
        if vertex < 0:
            polygons.append(current)
            current = []
    if current:
        raise ValueError('Unterminated FBX polygon')
    if any(len(polygon) != 3 for polygon in polygons):
        raise ValueError('FBX contains polygons other than triangles')
    corner_vertices = [v for polygon in polygons for v in polygon]

    def corner_layer(layer_name, values_name, index_name, dimensions):
        layer = mesh.child(layer_name)
        values = chunks(layer.value(values_name), dimensions)
        mapping = layer.value(b'MappingInformationType')
        reference = layer.value(b'ReferenceInformationType')
        if reference == b'IndexToDirect':
            indices = layer.value(index_name)
        elif reference == b'Direct':
            indices = None
        else:
            raise ValueError(f'Unknown FBX layer reference {reference!r}')
        result = []
        for corner, vertex in enumerate(corner_vertices):
            if mapping == b'ByPolygonVertex':
                mapped = corner
            elif mapping in (b'ByVertice', b'ByVertex'):
                mapped = vertex
            elif mapping == b'ByPolygon':
                mapped = corner//3
            elif mapping == b'AllSame':
                mapped = 0
            else:
                raise ValueError(f'Unknown FBX layer mapping {mapping!r}')
            result.append(values[indices[mapped] if indices is not None else mapped])
        return [result[i:i+3] for i in range(0, len(result), 3)]

    material = mesh.child(b'LayerElementMaterial')
    material_mapping = material.value(b'MappingInformationType')
    material_values = list(material.value(b'Materials'))
    if material_mapping == b'AllSame':
        material_indices = material_values*len(polygons)
    elif material_mapping == b'ByPolygon':
        material_indices = material_values
    else:
        raise ValueError(f'Unexpected material mapping {material_mapping!r}')
    models = [node for node in objects.children if node.name == b'Model' and node.properties[2] == b'Mesh']
    if len(models) != 1:
        raise ValueError('Expected one FBX mesh model')
    model = models[0]
    properties = {node.properties[0]: node.properties[4:] for node in model.child(b'Properties70').children if node.name == b'P'}
    material_nodes = {node.properties[0]: node for node in objects.children if node.name == b'Material'}
    role_ids = [node.properties[1] for node in root.child(b'Connections').children
                if node.name == b'C' and node.properties[0] == b'OO'
                and node.properties[2] == model.properties[0] and node.properties[1] in material_nodes]
    roles = [material_nodes[mid].properties[1].split(b'\x00\x01', 1)[0].decode('utf-8') for mid in role_ids]
    settings = {node.properties[0]: node.properties[4:] for node in root.child(b'GlobalSettings').child(b'Properties70').children if node.name == b'P'}
    return dict(version=version, vertices=vertices, triangles=polygons, material_indices=material_indices,
                material_roles=roles, model_properties=properties, global_properties=settings,
                normals=corner_layer(b'LayerElementNormal', b'Normals', b'NormalsIndex', 3),
                uv=corner_layer(b'LayerElementUV', b'UV', b'UVIndex', 2),
                tangents=corner_layer(b'LayerElementTangent', b'Tangents', b'TangentsIndex', 3),
                bitangents=corner_layer(b'LayerElementBinormal', b'Binormals', b'BinormalsIndex', 3))


class Problems:
    def __init__(self):
        self.counts, self.examples = Counter(), defaultdict(list)

    def add(self, kind, example=None):
        self.counts[kind] += 1
        if example is not None and len(self.examples[kind]) < 5:
            self.examples[kind].append(example)


def geometry_audit(vertices, triangles, normals, uv, tangents, bitangents, physical_scale):
    problems = Problems()
    edge_faces = defaultdict(list)
    parent = list(range(len(vertices)))

    def find(vertex):
        while parent[vertex] != vertex:
            parent[vertex] = parent[parent[vertex]]
            vertex = parent[vertex]
        return vertex

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    physical = [tuple(p[i]*physical_scale[i] for i in range(3)) for p in vertices]
    minimum_uv_det = float('inf')
    minimum_normal_facing = float('inf')
    maximum_frame_error = 0.
    maximum_uv_derivative_frame_error = 0.
    maximum_uv_scale_error = 0.
    minimum_physical_area = float('inf')
    geometric_zero_cross_count = 0
    duplicate_faces = Counter(tuple(sorted(face)) for face in triangles)
    if any(count > 1 for count in duplicate_faces.values()):
        problems.add('duplicate_triangle', sum(count-1 for count in duplicate_faces.values() if count > 1))
    for face_index, triangle in enumerate(triangles):
        if len(set(triangle)) != 3 or any(v < 0 or v >= len(vertices) for v in triangle):
            problems.add('invalid_triangle_indices', face_index)
            continue
        for a, b in zip(triangle, triangle[1:]+triangle[:1]):
            edge_faces[min(a, b), max(a, b)].append((face_index, 1 if a < b else -1))
            union(a, b)
        a, b, c = [vertices[v] for v in triangle]
        pa, pb, pc = [physical[v] for v in triangle]
        normal_cross = cross(sub(b, a), sub(c, a))
        physical_cross = cross(sub(pb, pa), sub(pc, pa))
        physical_area = norm(physical_cross)/2
        minimum_physical_area = min(minimum_physical_area, physical_area)
        if norm(normal_cross) == 0:
            geometric_zero_cross_count += 1
        if physical_area <= 1e-10 or norm(normal_cross) == 0:
            problems.add('geometric_degenerate_triangle', face_index)
            continue
        geometric_normal = normalize(normal_cross)
        physical_unit = normalize(physical_cross)
        uva, uvb, uvc = uv[face_index]
        u1 = tuple(uvb[i]-uva[i] for i in range(2))
        u2 = tuple(uvc[i]-uva[i] for i in range(2))
        determinant = u1[0]*u2[1]-u1[1]*u2[0]
        minimum_uv_det = min(minimum_uv_det, abs(determinant))
        if abs(determinant) < UV_ZERO_THRESHOLD:
            problems.add('uv_degenerate_native_1e_12', dict(triangle=face_index, determinant=determinant))
            continue
        # Compare all actual physical coordinate planes and take the best one.
        # Near a bevel's 45-degree tie, serialization can change the dominant
        # normal axis without changing the truthful physical UV edge scale.
        # Edges remove absolute chart phase, so phase cannot hide stretching.
        candidate_planes = []
        for axes in ((0, 1), (0, 2), (1, 2)):
            error = max(abs((uv[face_index][corner][axis]-uva[axis])-
                            (physical[triangle[corner]][axes[axis]]-pa[axes[axis]])/100)
                        for corner in (1, 2) for axis in (0, 1))
            candidate_planes.append((error, axes))
        triangle_uv_error, axes = min(candidate_planes)
        maximum_uv_scale_error = max(maximum_uv_scale_error, triangle_uv_error)
        if triangle_uv_error > UV_SCALE_TOLERANCE:
            problems.add('physical_projection_uv_scale', dict(triangle=face_index, error=triangle_uv_error, axes=axes))
        e1, e2 = sub(b, a), sub(c, a)
        raw_tangent = tuple((e1[i]*u2[1]-e2[i]*u1[1])/determinant for i in range(3))
        raw_bitangent = tuple((e2[i]*u1[0]-e1[i]*u2[0])/determinant for i in range(3))
        for corner in range(3):
            normal, tangent, bitangent = normals[face_index][corner], tangents[face_index][corner], bitangents[face_index][corner]
            if not all(math.isfinite(v) for vector in (normal, tangent, bitangent) for v in vector):
                problems.add('nonfinite_corner_frame', [face_index, corner])
                continue
            facing = dot(normal, geometric_normal)
            minimum_normal_facing = min(minimum_normal_facing, facing)
            if facing <= 1e-7:
                problems.add('corner_normal_not_facing_double_cross', dict(triangle=face_index, corner=corner, dot=facing))
            frame_error = max(abs(norm(vector)-1) for vector in (normal, tangent, bitangent))
            frame_error = max(frame_error, abs(dot(normal, tangent)), abs(dot(normal, bitangent)), abs(dot(tangent, bitangent)))
            maximum_frame_error = max(maximum_frame_error, frame_error)
            if frame_error > VECTOR_TOLERANCE:
                problems.add('corner_frame_not_unit_orthogonal', dict(triangle=face_index, corner=corner, error=frame_error))
            normalized_normal = normalize(normal)
            projected = tuple(raw_tangent[i]-normalized_normal[i]*dot(raw_tangent, normalized_normal) for i in range(3))
            if norm(projected) <= 1e-12:
                problems.add('normal_parallel_to_uv_tangent', [face_index, corner])
                continue
            expected_tangent = normalize(projected)
            expected_bitangent = normalize(cross(normalized_normal, expected_tangent))
            if dot(expected_bitangent, raw_bitangent) < 0:
                expected_bitangent = tuple(-v for v in expected_bitangent)
            derivative_error = max(vector_error(tangent, expected_tangent), vector_error(bitangent, expected_bitangent))
            maximum_uv_derivative_frame_error = max(maximum_uv_derivative_frame_error, derivative_error)
    for edge, faces in edge_faces.items():
        if len(faces) != 2:
            problems.add('boundary_or_nonmanifold_edge', dict(edge=edge, face_count=len(faces)))
        elif faces[0][1]+faces[1][1] != 0:
            problems.add('inconsistent_edge_orientation', dict(edge=edge, faces=faces))
    shells = defaultdict(list)
    for face in triangles:
        shells[find(face[0])].append(face)
    shell_volumes = []
    for faces in shells.values():
        reference = physical[faces[0][0]]
        volume = math.fsum(dot(sub(physical[t[0]], reference), cross(sub(physical[t[1]], reference), sub(physical[t[2]], reference)))/6 for t in faces)
        shell_volumes.append(volume)
        if volume <= 0:
            problems.add('nonpositive_closed_shell_volume_cm3', volume)
    unused_vertices = len(vertices)-len({v for triangle in triangles for v in triangle})
    if unused_vertices:
        problems.add('unused_vertices', unused_vertices)
    return dict(passed=not problems.counts, vertices=len(vertices), triangles=len(triangles),
                connected_shell_count=len(shell_volumes), signed_shell_volumes_cm3=shell_volumes,
                minimum_physical_triangle_area_cm2=minimum_physical_area,
                minimum_uv_area2=minimum_uv_det, native_uv_zero_threshold=UV_ZERO_THRESHOLD,
                minimum_corner_normal_geometric_facing=minimum_normal_facing,
                normal_facing_bad_corner_count=problems.counts.get('corner_normal_not_facing_double_cross', 0),
                geometric_zero_cross_triangle_count=geometric_zero_cross_count,
                maximum_corner_frame_unit_orthogonality_error=maximum_frame_error,
                maximum_double_vs_blender_float_uv_derivative_frame_error=maximum_uv_derivative_frame_error,
                maximum_physical_uv_projected_edge_error=maximum_uv_scale_error,
                issue_counts=dict(problems.counts), issue_examples=dict(problems.examples))


def audit_variant(category, variant, repair_row, old_variant):
    recipe_file = Path(variant['geometry_recipe_file'])
    fbx_file = Path(variant['fbx_file'])
    if not fbx_file.is_absolute():
        fbx_file = BASE/category/fbx_file
    recipe = load(recipe_file)
    fbx = fbx_mesh(fbx_file)
    original_fbx = fbx_raw_info(BASE/category/'BeforeSolids'/(fbx_file.name+'.bak'))
    errors = []
    recipe_sha, fbx_sha = sha(recipe_file), sha(fbx_file)
    for owner, item in (('manifest', variant), ('repair_report', repair_row)):
        if item['geometry_recipe_sha256'] != recipe_sha:
            errors.append(owner+'_recipe_sha256_mismatch')
        if item['fbx_sha256'] != fbx_sha:
            errors.append(owner+'_fbx_sha256_mismatch')
    scale = recipe['physical_scale']
    if any(s <= 0 or not math.isfinite(s) for s in scale):
        errors.append('invalid_physical_scale')
    recipe_audit = geometry_audit(recipe['vertices_cm'], recipe['triangles'], recipe['triangle_corner_normals'],
                                 recipe['triangle_corner_uv0'], recipe['triangle_corner_tangents'],
                                 recipe['triangle_corner_bitangents'], scale)
    if not recipe_audit['passed']:
        errors.append('recipe_geometry_audit_failed')
    # FBX geometry is deliberately exported in local Blender metres and the
    # Model scaling is 100, yielding the same local Unreal centimetre geometry.
    fbx_vertices_cm = [tuple(v*100 for v in vertex) for vertex in fbx['vertices']]
    fbx_audit = geometry_audit(fbx_vertices_cm, fbx['triangles'], fbx['normals'], fbx['uv'], fbx['tangents'], fbx['bitangents'], scale)
    if not fbx_audit['passed']:
        errors.append('fbx_geometry_audit_failed')
    rounded_centimetre_vertices = [tuple(struct.unpack('<f', struct.pack('<f', coordinate))[0] for coordinate in vertex)
                                   for vertex in fbx_vertices_cm]
    float32_cm_audit = geometry_audit(rounded_centimetre_vertices, fbx['triangles'], fbx['normals'], fbx['uv'],
                                    fbx['tangents'], fbx['bitangents'], scale)
    if not float32_cm_audit['passed']:
        errors.append('float32_centimetre_geometry_audit_failed')
    if fbx['triangles'] != recipe['triangles']:
        errors.append('fbx_recipe_triangle_indices_mismatch')
    if fbx['material_indices'] != recipe['material_indices']:
        errors.append('fbx_recipe_material_indices_mismatch')
    roles = recipe['material_roles']
    if roles != variant['material_roles'] or roles != old_variant['material_roles'] or roles != fbx['material_roles']:
        errors.append('material_role_slot_order_changed')
    if any(index < 0 or index >= len(roles) for index in recipe['material_indices']):
        errors.append('material_index_out_of_range')
    maximum_vertex_error = float('inf')
    if len(fbx_vertices_cm) == len(recipe['vertices_cm']):
        maximum_vertex_error = max(vector_error(a, b) for a, b in zip(fbx_vertices_cm, recipe['vertices_cm']))
    if maximum_vertex_error > POSITION_TOLERANCE_CM:
        errors.append('fbx_recipe_vertices_mismatch')
    maximum_corner_errors = {}
    for fbx_key, recipe_key in (('normals', 'triangle_corner_normals'), ('uv', 'triangle_corner_uv0'),
                                ('tangents', 'triangle_corner_tangents'), ('bitangents', 'triangle_corner_bitangents')):
        a, b = fbx[fbx_key], recipe[recipe_key]
        error = float('inf')
        if len(a) == len(b):
            error = max(vector_error(x, y) for ta, tb in zip(a, b) for x, y in zip(ta, tb))
        maximum_corner_errors[fbx_key] = error
        if error > VECTOR_TOLERANCE:
            errors.append('fbx_recipe_'+fbx_key+'_mismatch')
    bounds = [[min(vertex[axis] for vertex in recipe['vertices_cm']) for axis in range(3)],
              [max(vertex[axis] for vertex in recipe['vertices_cm']) for axis in range(3)]]
    original_vertices_cm = [tuple(v*100 for v in vertex) for vertex in original_fbx['vertices']]
    old_bounds = [[min(vertex[axis] for vertex in original_vertices_cm) for axis in range(3)],
                  [max(vertex[axis] for vertex in original_vertices_cm) for axis in range(3)]]
    maximum_bounds_error = max(abs(bounds[j][i]-old_bounds[j][i]) for j in range(2) for i in range(3))
    if maximum_bounds_error >= .005:
        errors.append('original_local_envelope_changed_0_005_cm')
    model_properties = fbx['model_properties']
    model_scale = model_properties.get(b'Lcl Scaling', [1., 1., 1.])
    model_translation = model_properties.get(b'Lcl Translation', [0., 0., 0.])
    model_rotation = model_properties.get(b'Lcl Rotation', [0., 0., 0.])
    if vector_error(model_scale, [100., 100., 100.]) > 1e-8:
        errors.append('fbx_model_scale_not_centimetre_export')
    old_model = original_fbx['model_properties']
    if vector_error(model_translation, old_model.get(b'Lcl Translation', [0., 0., 0.])) > 1e-8 or vector_error(model_rotation, old_model.get(b'Lcl Rotation', [0., 0., 0.])) > 1e-8:
        errors.append('fbx_model_pivot_or_axis_changed')
    for key in (b'UpAxis', b'UpAxisSign', b'FrontAxis', b'FrontAxisSign', b'CoordAxis', b'CoordAxisSign', b'UnitScaleFactor'):
        if fbx['global_properties'][key] != original_fbx['global_properties'][key]:
            errors.append('fbx_global_axis_or_unit_changed_'+key.decode('ascii'))
    return dict(category=category, key=variant['key'], mesh_name=variant['mesh_name'], passed=not errors,
                errors=errors, recipe_file=str(recipe_file), recipe_sha256=recipe_sha, fbx_file=str(fbx_file), fbx_sha256=fbx_sha,
                material_role_slot_order=roles, original_role_order_verified=roles == old_variant['material_roles'],
                maximum_local_envelope_change_cm=maximum_bounds_error,
                maximum_fbx_recipe_vertex_error_cm=maximum_vertex_error, maximum_fbx_recipe_corner_errors=maximum_corner_errors,
                fbx_model_scaling=model_scale, fbx_model_translation=model_translation, fbx_model_rotation=model_rotation,
                recipe=recipe_audit, fbx=fbx_audit, float32_centimetre=float32_cm_audit)


def float32_centimetre_evidence(categories=None):
    repair_file = WORK/'SourceSolidsRepair.json'
    repair = load(repair_file)
    report = dict(schema='OldTownRealismFloat32CentimetrePrecisionEvidenceV1',
                  repair_file=str(repair_file), repair_sha256=sha(repair_file),
                  created_utc=datetime.now(timezone.utc).isoformat(), variants=[],
                  policy='Parse current binary FBX; IEEE754 float32 round each local metre coordinate * 100; independently recompute double cross and corner normal dots. Original native UV determinant threshold 1e-12. No source or Unreal changes.')
    for category in EXPECTED:
        if categories and category not in categories:
            continue
        if category not in repair.get('categories', {}):
            continue
        manifest = load(BASE/category/'ModelDataManifest.json')
        for variant in manifest['variants']:
            path = Path(variant['fbx_file'])
            if not path.is_absolute():
                path = BASE/category/path
            fbx = fbx_mesh(path)
            precise = [tuple(v*100 for v in vertex) for vertex in fbx['vertices']]
            rounded = [tuple(struct.unpack('<f', struct.pack('<f', v))[0] for v in vertex) for vertex in precise]
            affected = []
            minimum_precise_facing = float('inf')
            minimum_rounded_facing = float('inf')
            minimum_uv_area = float('inf')
            zero_uv_count = 0
            zero_round_cross = 0
            bad_corners = 0
            for face_index, triangle in enumerate(fbx['triangles']):
                a, b, c = [precise[v] for v in triangle]
                ra, rb, rc = [rounded[v] for v in triangle]
                geometric = cross(sub(b, a), sub(c, a))
                rounded_geometric = cross(sub(rb, ra), sub(rc, ra))
                magnitude = norm(geometric)
                rounded_magnitude = norm(rounded_geometric)
                original_dots = [dot(normal, normalize(geometric)) for normal in fbx['normals'][face_index]] if magnitude else [0., 0., 0.]
                rounded_dots = [dot(normal, normalize(rounded_geometric)) for normal in fbx['normals'][face_index]] if rounded_magnitude else [0., 0., 0.]
                minimum_precise_facing = min(minimum_precise_facing, *original_dots)
                minimum_rounded_facing = min(minimum_rounded_facing, *rounded_dots)
                uva, uvb, uvc = fbx['uv'][face_index]
                determinant = (uvb[0]-uva[0])*(uvc[1]-uva[1])-(uvb[1]-uva[1])*(uvc[0]-uva[0])
                minimum_uv_area = min(minimum_uv_area, abs(determinant))
                if abs(determinant) < 1e-12:
                    zero_uv_count += 1
                invalid_corners = [corner for corner, facing in enumerate(rounded_dots) if facing <= 1e-7]
                if rounded_magnitude == 0:
                    zero_round_cross += 1
                bad_corners += len(invalid_corners)
                if invalid_corners or rounded_magnitude == 0:
                    affected.append(dict(triangle=face_index, vertex_indices=triangle, bad_corners=invalid_corners,
                        local_metre_vertices=[fbx['vertices'][v] for v in triangle],
                        precise_python_double_centimetre_vertices=[precise[v] for v in triangle],
                        rounded_float32_centimetre_vertices=[rounded[v] for v in triangle],
                        corner_normals=fbx['normals'][face_index],
                        precise_centimetre_double_cross=geometric, precise_cross_magnitude_cm2=magnitude,
                        float32_centimetre_double_cross=rounded_geometric, float32_cross_magnitude_cm2=rounded_magnitude,
                        precise_normal_facing_dots=original_dots, float32_normal_facing_dots=rounded_dots,
                        actual_uv0=fbx['uv'][face_index], actual_uv_determinant=determinant))
            row = dict(category=category, mesh_name=variant['mesh_name'], fbx_file=str(path), fbx_sha256=sha(path),
                       triangle_count=len(fbx['triangles']), bad_float32_cm_normal_corner_count=bad_corners,
                       zero_float32_cm_cross_triangle_count=zero_round_cross, minimum_precise_normal_facing=minimum_precise_facing,
                       minimum_float32_cm_normal_facing=minimum_rounded_facing, minimum_uv_area2=minimum_uv_area,
                       native_uv_degenerate_triangle_count=zero_uv_count, affected_triangles=affected)
            report['variants'].append(row)
            print('FLOAT32_CM_FBX_AUDIT', category, variant['mesh_name'], 'bad_corners', bad_corners, 'zero_cross', zero_round_cross, 'bad_uv', zero_uv_count, flush=True)
    report.update(audited_variant_count=len(report['variants']),
                  affected_mesh_names=[row['mesh_name'] for row in report['variants'] if row['affected_triangles']],
                  affected_mesh_count=sum(bool(row['affected_triangles']) for row in report['variants']),
                  bad_normal_corner_count=sum(row['bad_float32_cm_normal_corner_count'] for row in report['variants']),
                  zero_cross_triangle_count=sum(row['zero_float32_cm_cross_triangle_count'] for row in report['variants']),
                  native_uv_degenerate_triangle_count=sum(row['native_uv_degenerate_triangle_count'] for row in report['variants']))
    output = WORK/('SourceSolidsFloat32CentimetreEvidence.json' if not categories else
                  'SourceSolidsFloat32Centimetre'+''.join(categories)+'Evidence.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('FLOAT32_CM_FBX_AUDIT_COMPLETE', report['audited_variant_count'], report['affected_mesh_count'], report['bad_normal_corner_count'], str(output), flush=True)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inspect-fbx', type=Path)
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--float32-centimetre-evidence', action='store_true')
    parser.add_argument('--evidence-category', action='append', choices=tuple(EXPECTED))
    args = parser.parse_args()
    if args.float32_centimetre_evidence:
        float32_centimetre_evidence(args.evidence_category)
        return
    if args.inspect_fbx:
        fbx = fbx_mesh(args.inspect_fbx)
        print(json.dumps({k: v for k, v in fbx.items() if k not in ('vertices', 'triangles', 'normals', 'uv', 'tangents', 'bitangents', 'material_indices', 'model_properties', 'global_properties')}, indent=2))
        print('model_properties', fbx['model_properties'])
        print('global_properties', fbx['global_properties'])
        print('vertex_sample', fbx['vertices'][:3])
        print('triangle_sample', fbx['triangles'][:3])
        return
    repair_file = WORK/'SourceSolidsRepair.json'
    repair = load(repair_file)
    if not repair.get('passed') and not args.allow_partial:
        raise SystemExit('Source repair is not final; audit intentionally deferred.')
    report = dict(schema='OldTownRealismIndependentSerializedSourceAuditV1',
                  started_utc=datetime.now(timezone.utc).isoformat(), passed=False,
                  audit_script_file=str(Path(__file__).resolve()), audit_script_sha256=sha(__file__),
                  repair_file=str(repair_file), repair_sha256=sha(repair_file),
                  repair_final=repair.get('passed', False), target_count=143, variants=[], categories={}, errors=[],
                  methodology='Pure Python binary-FBX parser; independent double precision topology, per-shell signed volume, actual corner normal/geometric cross, native 1e-12 UV determinant, metre-projected UV edge scale up to phase, UV derivative tangent/bitangent frames; compare serialized recipe, FBX and source/backup manifests. Does not load Blender or Unreal.')
    repair_rows = {r['mesh_name']: r for r in repair['variants']}
    if repair.get('passed'):
        if len(repair_rows) != 143:
            report['errors'].append('repair_unique_mesh_count_not_143')
        repair_script = ROOT/'Scripts/RepairOldTownRealismSolidsBlender.py'
        report['repair_script_file'] = str(repair_script)
        report['repair_script_sha256'] = sha(repair_script)
        if repair['source_script_sha256'] != report['repair_script_sha256']:
            report['errors'].append('repair_source_script_sha256_mismatch')
        if sha(repair['diagnostic_file']) != repair['diagnostic_sha256']:
            report['errors'].append('repair_diagnostic_sha256_mismatch')
    for category, expected_count in EXPECTED.items():
        if args.allow_partial and category not in repair.get('categories', {}):
            continue
        manifest_file = BASE/category/'ModelDataManifest.json'
        manifest = load(manifest_file)
        old_manifest_file = BASE/category/'BeforeSolids/ModelDataManifest.json.bak'
        old_manifest = load(old_manifest_file)
        old_variants = {v['mesh_name']: v for v in old_manifest['variants']}
        variants = manifest['variants']
        if len(variants) != expected_count:
            report['errors'].append(category+'_variant_count')
        mesh_names = {v['mesh_name'] for v in variants}
        if len(mesh_names) != expected_count:
            report['errors'].append(category+'_unique_mesh_count')
        live_fbx_names = {p.stem for p in (BASE/category).glob('*.fbx')}
        # The furniture axis calibration file is an input fixture, not a model variant.
        # Verify its authored envelope and the original import result before excluding it.
        if category == 'Furniture' and 'AxisProbe' in live_fbx_names:
            probe_path = BASE/category/'AxisProbe.fbx'
            axes_path = WORK/'AxisVerification.json'
            axes = load(axes_path)
            probe_vertices = fbx_raw_info(probe_path)['vertices']
            probe_bounds_cm = [[100.0*fn(v[i] for v in probe_vertices) for i in range(3)]
                               for fn in (min, max)]
            probe_valid = (axes.get('error_cm', 1.0) < .001
                           and all(vector_error(a, b) < .0001
                                   for a, b in zip(probe_bounds_cm, axes['authored_bounds'])))
            report['axis_calibration_fixture'] = dict(file=str(probe_path.resolve()),
                sha256=sha(probe_path), axis_verification_file=str(axes_path.resolve()),
                axis_verification_sha256=sha(axes_path), authored_bounds_cm=probe_bounds_cm,
                passed=probe_valid)
            if not probe_valid:
                report['errors'].append('Furniture_axis_calibration_fixture_invalid')
            live_fbx_names.remove('AxisProbe')
        live_recipe_names = {p.name.removesuffix('.geometry.json') for p in (BASE/category).glob('*.geometry.json')}
        if mesh_names != live_fbx_names:
            report['errors'].append(category+'_live_fbx_names_mismatch')
        if mesh_names != live_recipe_names:
            report['errors'].append(category+'_live_geometry_recipe_names_mismatch')
        category_record = dict(variant_count=len(variants), expected_variant_count=expected_count,
                               manifest_file=str(manifest_file), manifest_sha256=sha(manifest_file),
                               original_manifest_file=str(old_manifest_file), original_manifest_sha256=sha(old_manifest_file))
        if category in repair.get('categories', {}):
            expected_category = repair['categories'][category]
            if category_record['manifest_sha256'] != expected_category['manifest_sha256']:
                report['errors'].append(category+'_manifest_sha256_mismatch')
            blend = Path(manifest.get('blend_file') or manifest['source_blend_file'])
            category_record.update(blend_file=str(blend), blend_sha256=sha(blend))
            if category_record['blend_sha256'] != expected_category['blend_sha256']:
                report['errors'].append(category+'_blend_sha256_mismatch')
        for variant in variants:
            if variant['mesh_name'] not in repair_rows:
                if args.allow_partial:
                    continue
                report['errors'].append('missing_repair_variant_'+variant['mesh_name'])
                continue
            try:
                row = audit_variant(category, variant, repair_rows[variant['mesh_name']], old_variants[variant['mesh_name']])
            except Exception as exc:
                row = dict(category=category, mesh_name=variant['mesh_name'], passed=False, errors=[str(exc)])
            report['variants'].append(row)
            if not row['passed']:
                report['errors'].append(variant['mesh_name'])
            print('INDEPENDENT_SOURCE_AUDIT', category, variant['mesh_name'], row['passed'], row['errors'], flush=True)
        report['categories'][category] = category_record
    report['audited_variant_count'] = len(report['variants'])
    report['all_audited_serialized_geometry_passed'] = all(row['passed'] for row in report['variants'])
    if not args.allow_partial and sha(repair_file) != report['repair_sha256']:
        report['errors'].append('repair_report_changed_during_audit')
    report['passed'] = not report['errors'] and report['repair_final'] and len(report['variants']) == 143
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    if not args.allow_partial:
        evidence_file = float32_centimetre_evidence()
        evidence = load(evidence_file)
        report['float32_centimetre_evidence_file'] = str(evidence_file)
        report['float32_centimetre_evidence_sha256'] = sha(evidence_file)
        if evidence['audited_variant_count'] != 143 or evidence['repair_sha256'] != report['repair_sha256']:
            report['errors'].append('float32_centimetre_evidence_binding_failed')
        if evidence['bad_normal_corner_count'] or evidence['zero_cross_triangle_count'] or evidence['native_uv_degenerate_triangle_count']:
            report['errors'].append('float32_centimetre_evidence_precision_failed')
        report['passed'] = not report['errors'] and report['repair_final'] and len(report['variants']) == 143
    output = WORK/('SourceSolidsPartialIndependentAudit.json' if args.allow_partial else 'SourceSolidsIndependentAudit.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print('INDEPENDENT_SOURCE_AUDIT_COMPLETE', report['passed'], len(report['variants']), len(report['errors']), str(output), flush=True)
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
