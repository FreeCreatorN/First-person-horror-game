"""Classify coplanar overlap hidden inside a closed combined mesh.

This read-only follow-up uses signed ray crossings rather than odd/even parity,
so overlapping closed primitives in a single mesh retain their union occupancy.
Open meshes are retained as exposure candidates. Candidate polygon centres and
inset vertices are tested 0.1 cm ahead of the true outward face normal.
"""

from collections import Counter
import argparse
import copy
import json
import math
from pathlib import Path
from OldTownCoplanarScan import (_dot, _cross, _face, _project, _world_point,
                                _signed_area, polygon_intersection,
                                annotate_axisaligned_cubes, _BoxOcclusion)


def _triangle_points(record, index):
    tri = record['triangles'][index]
    if 'vertices' in record:
        return tuple(tuple(record['vertices'][int(i)]) for i in tri)
    return tuple(tuple(p) for p in tri)


def _ray_box(point, direction, bounds):
    near, far = 0., math.inf
    for i in range(3):
        a = (bounds[0][i]-point[i])/direction[i]
        b = (bounds[1][i]-point[i])/direction[i]
        near = max(near,min(a,b))
        far = min(far,max(a,b))
        if far < near:
            return False
    return far > 1e-7


def _ray_triangle(point, direction, tri, reverse):
    a,b,c = tri
    edge1 = tuple(b[i]-a[i] for i in range(3))
    edge2 = tuple(c[i]-a[i] for i in range(3))
    cross = _cross(direction,edge2)
    determinant = _dot(edge1,cross)
    if abs(determinant) < 1e-10:
        return 0
    delta = tuple(point[i]-a[i] for i in range(3))
    u = _dot(delta,cross)/determinant
    if u < -1e-8 or u > 1.+1e-8:
        return 0
    q = _cross(delta,edge1)
    v = _dot(direction,q)/determinant
    if v < -1e-8 or u+v > 1.+1e-8:
        return 0
    distance = _dot(edge2,q)/determinant
    if distance <= 1e-7:
        return 0
    # determinant is the negative of dot(direction, mathematical face normal).
    outward_dot = determinant if reverse else -determinant
    return 1 if outward_dot > 0 else -1


class _TriangleBVH:
    def __init__(self, record):
        self.record = record
        self.reverse = record.get('reverse_winding',False)
        self.triangles = [_triangle_points(record,i)
                          for i in range(len(record['triangles']))]
        self.bounds = [(tuple(min(p[i] for p in tri) for i in range(3)),
                        tuple(max(p[i] for p in tri) for i in range(3)))
                       for tri in self.triangles]
        self.centres = [tuple((b[0][i]+b[1][i])*.5 for i in range(3))
                        for b in self.bounds]
        edges = Counter()
        for tri in self.triangles:
            points = [tuple(round(float(v),5) for v in p) for p in tri]
            for i in range(3):
                if points[i] != points[(i+1)%3]:
                    edges[tuple(sorted((points[i],points[(i+1)%3])))] += 1
        # A union of disconnected closed solids may have coincident edges used
        # 4+ times. Odd counts indicate an open boundary or an ambiguous mesh.
        self.odd_boundary_edges = sum(v % 2 for v in edges.values())
        self.closed = self.odd_boundary_edges == 0
        self.root = self._build(list(range(len(self.triangles))))

    def _build(self, indices):
        bounds = (tuple(min(self.bounds[j][0][i] for j in indices) for i in range(3)),
                  tuple(max(self.bounds[j][1][i] for j in indices) for i in range(3)))
        if len(indices) <= 16:
            return bounds,None,indices
        axis = max(range(3),key=lambda i:bounds[1][i]-bounds[0][i])
        indices.sort(key=lambda j:self.centres[j][axis])
        mid = len(indices)//2
        return bounds,(self._build(indices[:mid]),self._build(indices[mid:])),None

    def _signed_crossings(self, point, direction):
        stack = [self.root]
        total = 0
        while stack:
            bounds,children,indices = stack.pop()
            if not _ray_box(point,direction,bounds):
                continue
            if children:
                stack.extend(children)
            else:
                for index in indices:
                    total += _ray_triangle(point,direction,self.triangles[index],self.reverse)
        return total

    def inside(self, point):
        if not self.closed:
            return False
        if any(point[i] < self.root[0][0][i] or point[i] > self.root[0][1][i]
               for i in range(3)):
            return False
        # Two non-axis rays avoid shared-edge ambiguities. The magnitude is the
        # occupancy count of overlapping closed solids; > 0 means inside.
        return (self._signed_crossings(point,(.371,.593,.715)) > 0 and
                self._signed_crossings(point,(-.483,.677,.555)) > 0)


def classify_internal_occlusion(records, scan, progress=None):
    records = annotate_axisaligned_cubes(records)
    by = {str(r['id']):(i,r) for i,r in enumerate(records)}
    result = copy.deepcopy(scan)
    cache = {}
    stats = Counter()
    tol = scan['scope']['plane_tolerance_cm']
    normal_tol = scan['scope']['normal_tolerance']
    minimum_area = scan['scope']['minimum_overlap_area_cm2']
    occlusion = _BoxOcclusion(records,200.)
    intra_rows = [r for r in result['overlaps'] if r['intra_component']]
    for row_index,row in enumerate(intra_rows):
        component_id = row['components'][0]
        owner,record = by[component_id]
        if record.get('kind') == 'box':
            continue
        if owner not in cache:
            cache[owner] = _TriangleBVH(record)
        bvh = cache[owner]
        if not bvh.closed:
            row['self_occlusion'] = {'closed_mesh':False,
                                     'odd_boundary_edges':bvh.odd_boundary_edges,
                                     'classification':'retained open mesh candidate'}
            stats['open_mesh_groups_retained'] += 1
            continue
        ids = row['face_indices_by_component'][component_id]
        faces = [_face(owner,i,_triangle_points(record,i),normal_tol,bvh.reverse)
                 for i in ids]
        key = tuple(math.floor(v/normal_tol) for v in row['normal'])
        plane_key = round(row['plane_cm']/tol)
        area_total = buried_total = exposed_total = internal_total = 0.
        count = 0
        for j,face in enumerate(faces):
            if face is None or face.key != key:
                continue
            for other in faces[:j]:
                if other is None or round(((face.plane+other.plane)/2)/tol) != plane_key:
                    continue
                if _dot(face.normal,other.normal) < 1.-normal_tol**2/2:
                    continue
                plane_gap = max(max(abs(_dot(face.normal,p)-face.plane) for p in other.points),
                                max(abs(_dot(other.normal,p)-other.plane) for p in face.points))
                if plane_gap > tol:
                    continue
                axis = max(range(3),key=lambda i:abs(face.normal[i]))
                polygon = polygon_intersection(_project(face.points,axis),
                                               _project(other.points,axis))
                if len(polygon) < 3:
                    continue
                area = abs(_signed_area(polygon))/abs(face.normal[axis])
                if area < minimum_area:
                    continue
                count += 1
                area_total += area
                world_points = [_world_point(p,axis,face.normal,face.plane) for p in polygon]
                centre = tuple(sum(p[i] for p in world_points)/len(world_points) for i in range(3))
                points = [centre]+[tuple(.99*p[i]+.01*centre[i]+.1*face.normal[i]
                                           for i in range(3)) for p in world_points]
                points[0] = tuple(centre[i]+.1*face.normal[i] for i in range(3))
                internally_buried = all(bvh.inside(p) for p in points)
                externally_buried = all(occlusion.containing(p,(owner,)) for p in points)
                if internally_buried:
                    internal_total += area
                if internally_buried or externally_buried:
                    buried_total += area
                else:
                    exposed_total += area
        matches = count == row['face_pair_count'] and abs(area_total-row['area_cm2']) <= max(.02,area_total*1e-7)
        row['self_occlusion'] = {'closed_mesh':True,'odd_boundary_edges':0,
                                 'tested_face_pairs':count,'expected_face_pairs':row['face_pair_count'],
                                 'recomputed_area_cm2':area_total,
                                 'internal_buried_area_cm2':internal_total,
                                 'complete_group_recomputed':matches,
                                 'method':'two signed rays per centre/inset vertex at +0.1cm normal'}
        if matches:
            row['buried_area_cm2'] = buried_total
            row['exposed_area_cm2'] = exposed_total
            row['buried'] = exposed_total <= 1e-6
            stats['closed_mesh_groups_classified'] += 1
            if row['buried']:
                stats['fully_self_buried_groups'] += 1
        else:
            stats['incomplete_groups_retained'] += 1
        if progress and row_index % 50 == 0:
            progress({'internal_groups_processed':row_index,'total_internal_groups':len(intra_rows),
                      'stats':dict(stats)})
    result['internal_occlusion_stats'] = dict(stats)
    result['scope']['internal_occlusion_method'] = 'closed composite mesh signed ray union occupancy'
    result['overlaps'].sort(key=lambda r:(r['buried'],-r['exposed_area_cm2'],-r['area_cm2'],r['components']))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('geometry',type=Path)
    parser.add_argument('scan',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    data = json.loads(args.geometry.read_text(encoding='utf-8-sig'))
    records = data['components'] if isinstance(data,dict) else data
    scan = json.loads(args.scan.read_text(encoding='utf-8-sig'))
    result = classify_internal_occlusion(records,scan,progress=lambda p:print(json.dumps(p),flush=True))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['internal_occlusion_stats']),flush=True)


if __name__ == '__main__':
    main()
