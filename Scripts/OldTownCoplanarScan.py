"""Read-only, pure Python detection of genuinely overlapping coplanar faces.

Input components use ``id``, ``actor``, ``component``, ``visible`` and either
``vertices`` plus indexed ``triangles`` (world centimetres), unindexed triangles,
or ``kind='box', axisaligned=True, bounds_cm=[minimum, maximum]``.  Box bounds
must describe real axis-aligned cube geometry, never an arbitrary mesh AABB.
``reverse_winding`` must be verified against mesh normals and XORed with a
negative world transform determinant. Unreal render-buffer winding normally
needs reversal; analytic boxes already supply outward faces independently.
The scanner handles arbitrary face normals and uses actual polygon clipping;
opposing faces that merely meet, shared triangle edges and hidden geometry do
not produce results.  Set include_internal=True for duplicate faces inside a
combined mesh.  Results are evidence candidates, not instructions to move walls.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import product
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


def _dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])


def _signed_area(poly):
    return .5*sum(poly[i][0]*poly[(i+1) % len(poly)][1]
                  - poly[(i+1) % len(poly)][0]*poly[i][1]
                  for i in range(len(poly)))


def polygon_intersection(subject, clip, epsilon=1e-8):
    """Convex polygon intersection, in any shared 2D projection."""
    subject = list(subject)
    clip = list(clip)
    if _signed_area(subject) < 0:
        subject.reverse()
    if _signed_area(clip) < 0:
        clip.reverse()
    result = subject
    for i, a in enumerate(clip):
        b = clip[(i+1) % len(clip)]
        if not result:
            break
        edge = (b[0]-a[0], b[1]-a[1])
        def distance(p):
            return edge[0]*(p[1]-a[1])-edge[1]*(p[0]-a[0])
        old = result
        result = []
        previous = old[-1]
        previous_distance = distance(previous)
        for current in old:
            current_distance = distance(current)
            previous_inside = previous_distance >= -epsilon
            current_inside = current_distance >= -epsilon
            if current_inside != previous_inside:
                denominator = previous_distance-current_distance
                if abs(denominator) > 1e-20:
                    t = previous_distance/denominator
                    result.append((previous[0]+t*(current[0]-previous[0]),
                                   previous[1]+t*(current[1]-previous[1])))
            if current_inside:
                result.append(current)
            previous = current
            previous_distance = current_distance
    return result


def box_faces(bounds):
    """Six outward-wound polygons of a real world-axis aligned box."""
    lo, hi = bounds
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    return [
        [(x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0)],
        [(x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1)],
        [(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)],
        [(x0,y1,z0),(x0,y1,z1),(x1,y1,z1),(x1,y1,z0)],
        [(x0,y0,z0),(x0,y1,z0),(x1,y1,z0),(x1,y0,z0)],
        [(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)],
    ]


@dataclass(slots=True)
class _Face:
    owner: int
    index: int
    points: tuple
    normal: tuple
    plane: float
    key: tuple
    bounds: tuple


def _face(owner, index, points, normal_step, reverse=False):
    points = tuple(tuple(float(c) for c in p) for p in points)
    a, b, c = points[:3]
    cross = _cross(tuple(b[i]-a[i] for i in range(3)),
                   tuple(c[i]-a[i] for i in range(3)))
    length = math.sqrt(_dot(cross, cross))
    if length < 1e-10:
        return None
    normal = tuple(v/length*(-1 if reverse else 1) for v in cross)
    if reverse:
        points = tuple(reversed(points))
    key = tuple(math.floor(v/normal_step) for v in normal)
    return _Face(owner, index, points, normal, _dot(normal, a), key,
                 (tuple(min(p[i] for p in points) for i in range(3)),
                  tuple(max(p[i] for p in points) for i in range(3))))


def _project(points, axis):
    axes = tuple(i for i in range(3) if i != axis)
    return [(p[axes[0]], p[axes[1]]) for p in points]


def _world_point(point, axis, normal, plane):
    axes = tuple(i for i in range(3) if i != axis)
    result = [0., 0., 0.]
    result[axes[0]], result[axes[1]] = point
    result[axis] = (plane-normal[axes[0]]*point[0]
                    -normal[axes[1]]*point[1])/normal[axis]
    return tuple(result)


def _ranges(face, group, plane_tolerance, cell_size, expand_plane=False):
    # Index the whole projection of a face onto the quantized normal.  This
    # prevents quantization of a slightly noisy normal splitting a large real
    # coplanar triangle into a different plane bucket from its neighbours.
    values = [_dot(group['normal'], p) for p in face.points]
    delta = plane_tolerance if expand_plane else 0.
    plane_range = range(math.floor((min(values)-delta)/plane_tolerance),
                        math.floor((max(values)+delta)/plane_tolerance)+1)
    axes = group['axes']
    u_range = range(math.floor(face.bounds[0][axes[0]]/cell_size),
                    math.floor(face.bounds[1][axes[0]]/cell_size)+1)
    v_range = range(math.floor(face.bounds[0][axes[1]]/cell_size),
                    math.floor(face.bounds[1][axes[1]]/cell_size)+1)
    return plane_range, u_range, v_range


def _group(key):
    length = math.sqrt(sum(v*v for v in key))
    normal = tuple(v/length for v in key)
    axis = max(range(3), key=lambda i: abs(normal[i]))
    return {'normal': normal, 'axis': axis,
            'axes': tuple(i for i in range(3) if i != axis),
            'grid': defaultdict(list), 'large': [], 'all': []}


class _BoxOcclusion:
    def __init__(self, components, cell_size):
        self.cell_size = cell_size
        self.boxes = {}
        self.grid = defaultdict(list)
        self.large = []
        for owner, record in enumerate(components):
            if not _visible(record) or not _is_box(record):
                continue
            if record.get('solid', True) is False:
                continue
            bounds = record['bounds_cm']
            self.boxes[owner] = bounds
            ranges = [range(math.floor(bounds[0][i]/cell_size),
                            math.floor(bounds[1][i]/cell_size)+1)
                      for i in range(3)]
            if math.prod(len(r) for r in ranges) > 30000:
                self.large.append(owner)
            else:
                for key in product(*ranges):
                    self.grid[key].append(owner)

    def containing(self, point, excluded):
        key = tuple(math.floor(v/self.cell_size) for v in point)
        result = []
        for owner in self.grid.get(key, ()):
            if owner not in excluded and self._inside(point, self.boxes[owner]):
                result.append(owner)
        for owner in self.large:
            if owner not in excluded and self._inside(point, self.boxes[owner]):
                result.append(owner)
        return result

    @staticmethod
    def _inside(point, bounds):
        return all(bounds[0][i]+1e-5 < point[i] < bounds[1][i]-1e-5
                   for i in range(3))


def _visible(record):
    return record.get('visible', True) and not record.get('hidden', False) \
        and not record.get('hidden_in_game', False)


def _is_box(record):
    return ('bounds_cm' in record and
            (record.get('kind') in ('box', 'cube') or
             record.get('axisaligned_box', False)) and
            record.get('axisaligned', True))


def annotate_axisaligned_cubes(records, tolerance_cm=.001):
    """Recognize transformed Engine Cube triangles without guessing from AABB.

    Returns shallow record copies. Every real triangle must lie on an outer
    axis face, so a rotated cube is retained as real triangles.
    """
    result = []
    for original in records:
        record = original
        if ('/Engine/BasicShapes/Cube' in str(original.get('mesh','')) and
                original.get('vertices') and not _is_box(original)):
            vertices = original['vertices']
            bounds = [[min(p[i] for p in vertices) for i in range(3)],
                      [max(p[i] for p in vertices) for i in range(3)]]
            good = True
            for triangle in original.get('triangles',()):
                points = [vertices[int(i)] for i in triangle]
                if not any(max(p[axis] for p in points)-min(p[axis] for p in points)
                           <= tolerance_cm and
                           min(abs(points[0][axis]-bounds[0][axis]),
                               abs(points[0][axis]-bounds[1][axis])) <= tolerance_cm
                           for axis in range(3)):
                    good = False
                    break
            if good:
                record = dict(original,kind='box',axisaligned=True,bounds_cm=bounds)
        result.append(record)
    return result


def scan_components(records, plane_tolerance_cm=.03,
                    min_overlap_area_cm2=1., cell_size_cm=200.,
                    include_internal=False, axis_only=False,
                    normal_tolerance=1e-4, classify_buried=True,
                    maximum_cells_per_face=12000, progress=None):
    """Detect actual same-facing coplanar area across visible components.

    Non-axis faces are scanned by default. ``include_internal`` additionally
    scans distinct triangles of the same combined mesh. An overlap buried under
    a third visible solid box is marked, never silently discarded. Occlusion is
    a centre/vertex sampling classification, not a renderer visibility proof.
    Faces whose normal deviates by > normal_tolerance or whose vertices differ
    from the other plane by > plane_tolerance_cm are not coplanar candidates.
    """
    if plane_tolerance_cm <= 0 or normal_tolerance <= 0 or cell_size_cm <= 0:
        raise ValueError('Tolerances and spatial cell size must be positive')
    records = list(records)
    ids = [str(r.get('id', str(r.get('actor', ''))+'::'+str(r.get('component', i))))
           for i, r in enumerate(records)]
    if len(ids) != len(set(ids)):
        raise ValueError('Every component needs a unique id')
    metadata = [{key:r[key] for key in ('actor','component','mesh','kind') if key in r}
                for r in records]
    stats = Counter()
    groups = {}
    faces = []
    overlaps = {}
    normal_step = normal_tolerance
    normal_offsets = tuple(product((-1,0,1), repeat=3))
    neighbours_cache = {}
    group_revision = 0
    occlusion = _BoxOcclusion(records, cell_size_cm) if classify_buried else None
    duplicate_groups = defaultdict(list)

    def make_result(face, other, intersection, axis, area, plane_gap):
        owners = tuple(sorted((face.owner, other.owner)))
        # Quantized groups are only a broad phase. This key averages the real
        # equations, preserving the outward normal orientation in the report.
        report_key = (owners, face.key,
                      round(((face.plane+other.plane)/2)/plane_tolerance_cm))
        row = overlaps.get(report_key)
        if row is None:
            row = {'components':[ids[i] for i in owners],
                   'component_metadata':[metadata[i] for i in owners],
                   'intra_component': owners[0] == owners[1],
                   'normal':list(face.normal),
                   'plane_cm':(face.plane+other.plane)/2,
                   'projection_axis':'xyz'[axis], 'area_cm2':0.,
                   'face_pair_count':0, 'max_plane_gap_cm':0.,
                   'face_pair_samples':[],
                   'face_indices_by_component':{ids[i]:set() for i in owners},
                   'buried_area_cm2':0.,
                   'exposed_area_cm2':0., 'buried_by':set(),
                   'overlap_bounds_cm':[[math.inf]*3,[-math.inf]*3]}
            overlaps[report_key] = row
        row['area_cm2'] += area
        row['face_pair_count'] += 1
        row['max_plane_gap_cm'] = max(row['max_plane_gap_cm'], plane_gap)
        if len(row['face_pair_samples']) < 12:
            ordered = [face.index,other.index] if face.owner == owners[0] else [other.index,face.index]
            row['face_pair_samples'].append(ordered)
        row['face_indices_by_component'][ids[face.owner]].add(face.index)
        row['face_indices_by_component'][ids[other.owner]].add(other.index)
        world_points = [_world_point(p, axis, face.normal, face.plane)
                        for p in intersection]
        for p in world_points:
            for i in range(3):
                row['overlap_bounds_cm'][0][i] = min(row['overlap_bounds_cm'][0][i],p[i])
                row['overlap_bounds_cm'][1][i] = max(row['overlap_bounds_cm'][1][i],p[i])
        buried = False
        if occlusion and world_points:
            centre = tuple(sum(p[i] for p in world_points)/len(world_points)
                           for i in range(3))
            # Pull perimeter samples slightly inside the intersection so a
            # touching box edge is not mistaken for an exposed interior face.
            samples = [centre]+[tuple(.99*p[i]+.01*centre[i] for i in range(3))
                                for p in world_points]
            containing = [occlusion.containing(tuple(p[i]+face.normal[i]*.1
                                                     for i in range(3)), owners)
                          for p in samples]
            buried = all(containing)
            if buried:
                row['buried_by'].update(ids[i] for sample in containing for i in sample)
        row['buried_area_cm2' if buried else 'exposed_area_cm2'] += area

    for owner, record in enumerate(records):
        if progress and owner % 100 == 0:
            progress({'components_scanned':owner,'component_count':len(records),
                      'faces_scanned':len(faces),'overlaps':len(overlaps),
                      'broad_phase_face_pairs':stats['broad_phase_face_pairs']})
        if not _visible(record):
            stats['hidden_components_skipped'] += 1
            continue
        stats['visible_components'] += 1
        if _is_box(record):
            points_iter = enumerate(box_faces(record['bounds_cm']))
            duplicate_groups[tuple(round(float(v),5)
                                   for bound in record['bounds_cm'] for v in bound)].append(owner)
        else:
            vertices = record.get('vertices')
            triangles = record.get('triangles', ())
            if vertices is not None:
                points_iter = ((i, [vertices[int(j)] for j in tri])
                               for i, tri in enumerate(triangles))
            else:
                points_iter = enumerate(triangles)
        # Analytic box_faces already uses outward mathematical winding. Only
        # original SDK triangles need the explicitly verified winding reversal.
        reverse = record.get('reverse_winding', False) and not _is_box(record)
        for index, points in points_iter:
            stats['input_faces'] += 1
            face = _face(owner, index, points, normal_step, reverse)
            if face is None:
                stats['degenerate_faces_skipped'] += 1
                continue
            major_axis = max(range(3), key=lambda i: abs(face.normal[i]))
            axis_aligned = (abs(face.normal[major_axis]) > 1.-1e-10)
            if axis_only and not axis_aligned:
                stats['non_axis_faces_skipped'] += 1
                continue
            stats['axis_faces_scanned' if axis_aligned else 'non_axis_faces_scanned'] += 1
            cached = neighbours_cache.get(face.key)
            if cached is None or cached[0] != group_revision:
                keys = []
                for offset in normal_offsets:
                    key = tuple(face.key[i]+offset[i] for i in range(3))
                    if key in groups:
                        keys.append(key)
                neighbours_cache[face.key] = (group_revision, keys)
            else:
                keys = cached[1]
            candidates = set()
            for key in keys:
                group = groups[key]
                ranges = _ranges(face, group, plane_tolerance_cm, cell_size_cm, True)
                if math.prod(len(r) for r in ranges) > maximum_cells_per_face:
                    candidates.update(group['all'])
                    stats['oversized_queries'] += 1
                else:
                    for bucket in product(*ranges):
                        candidates.update(group['grid'].get(bucket, ()))
                    candidates.update(group['large'])
            for other_index in candidates:
                other = faces[other_index]
                if owner == other.owner and not include_internal:
                    continue
                stats['broad_phase_face_pairs'] += 1
                if _dot(face.normal,other.normal) < 1.-normal_tolerance**2/2:
                    continue
                if any(face.bounds[0][i] > other.bounds[1][i]+plane_tolerance_cm or
                       other.bounds[0][i] > face.bounds[1][i]+plane_tolerance_cm
                       for i in range(3)):
                    continue
                plane_gap = max(max(abs(_dot(face.normal,p)-face.plane) for p in other.points),
                                max(abs(_dot(other.normal,p)-other.plane) for p in face.points))
                if plane_gap > plane_tolerance_cm:
                    continue
                axis = major_axis
                polygon = polygon_intersection(_project(face.points,axis),
                                               _project(other.points,axis))
                if len(polygon) < 3:
                    continue
                area = abs(_signed_area(polygon))/abs(face.normal[axis])
                if area < min_overlap_area_cm2:
                    continue
                stats['overlapping_face_pairs'] += 1
                make_result(face,other,polygon,axis,area,plane_gap)
            if face.key not in groups:
                groups[face.key] = _group(face.key)
                group_revision += 1
            group = groups[face.key]
            face_index = len(faces)
            faces.append(face)
            group['all'].append(face_index)
            ranges = _ranges(face, group, plane_tolerance_cm, cell_size_cm)
            if math.prod(len(r) for r in ranges) > maximum_cells_per_face:
                group['large'].append(face_index)
                stats['oversized_indexed_faces'] += 1
            else:
                for bucket in product(*ranges):
                    group['grid'][bucket].append(face_index)
    result_rows = []
    for row in overlaps.values():
        row['buried_by'] = sorted(row['buried_by'])
        row['face_indices_by_component'] = {key:sorted(values) for key,values
                                             in row['face_indices_by_component'].items()}
        row['buried'] = row['exposed_area_cm2'] <= 1e-6
        result_rows.append(row)
    result_rows.sort(key=lambda r:(r['buried'],-r['exposed_area_cm2'],-r['area_cm2'],r['components']))
    duplicates = []
    for bounds, owners in duplicate_groups.items():
        if len(owners) > 1:
            duplicates.append({'components':[ids[i] for i in owners],
                               'component_metadata':[metadata[i] for i in owners],
                               'bounds_cm':[list(bounds[:3]),list(bounds[3:])]})
    return {'schema':'oldtown-coplanar-scan-v1',
            'scope':{'component_count':len(records),
                     'include_internal':include_internal,'axis_only':axis_only,
                     'plane_tolerance_cm':plane_tolerance_cm,
                     'normal_tolerance':normal_tolerance,
                     'minimum_overlap_area_cm2':min_overlap_area_cm2,
                     'occlusion_method':'third solid box centre and inset vertices + 0.1cm normal'
                                        if classify_buried else 'disabled'},
            'stats':dict(stats),'normal_group_count':len(groups),
            'overlap_count':len(result_rows),'exact_duplicate_boxes':duplicates,
            'overlaps':result_rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--include-internal',action='store_true')
    parser.add_argument('--axis-only',action='store_true')
    parser.add_argument('--plane-tolerance-cm',type=float,default=.03)
    parser.add_argument('--recognize-cubes',action='store_true')
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8-sig'))
    records = data.get('components',data.get('records')) if isinstance(data,dict) else data
    if records is None:
        raise ValueError('Input must be a component list or contain components/records')
    if args.recognize_cubes:
        records = annotate_axisaligned_cubes(records)
    result = scan_components(records,include_internal=args.include_internal,
                             axis_only=args.axis_only,
                             plane_tolerance_cm=args.plane_tolerance_cm,
                             progress=lambda p: print(json.dumps(p),flush=True))
    result['source_geometry_path'] = str(args.input.resolve())
    result['source_geometry_sha256'] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    result['source_map_sha256'] = data.get('map_sha256') if isinstance(data,dict) else None
    result['completed_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('stats','normal_group_count','overlap_count')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
