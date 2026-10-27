"""Pure-Python render-offset planning from a correctly wound surface scan.

No Unreal calls and no map or asset writes. Separate graph colours are used for
each axis, with 0.09 cm spacing. Physics transforms and shared assets are inputs
only. Use create_offsets(scan) -> (id_to_world_cm_vector, summary).
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import heapq
import json
import math
from pathlib import Path

STEP_CM = .09
MIN_NORMAL_PROJECTION_CM = .06
MAX_OFFSET_NORM_CM = .8


def _dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def _norm(v):
    return math.sqrt(_dot(v,v))


def _axis(normal):
    axis = max(range(3), key=lambda i: abs(normal[i]))
    return axis if abs(abs(normal[axis])-1) <= 1e-5 and all(abs(normal[i]) <= 1e-5 for i in range(3) if i != axis) else None


def _colour(adjacency):
    """Deterministic DSATUR; high-degree and highly constrained nodes go first."""
    colours = {}
    used = {node:set() for node in adjacency}
    versions = Counter()
    heap = [(0,-len(edges),node,0) for node,edges in adjacency.items()]
    heapq.heapify(heap)
    while heap:
        _, _, node, version = heapq.heappop(heap)
        if node in colours or version != versions[node]:
            continue
        colour = 0
        while colour in used[node]:
            colour += 1
        colours[node] = colour
        for neighbour in adjacency[node]:
            if neighbour in colours or colour in used[neighbour]:
                continue
            used[neighbour].add(colour)
            versions[neighbour] += 1
            heapq.heappush(heap,(-len(used[neighbour]),-len(adjacency[neighbour]),neighbour,versions[neighbour]))
    return colours


def _level(colour):
    # Keep colour zero unmoved; alternate positive/negative levels thereafter.
    return 0 if colour == 0 else (colour+1)//2*(1 if colour % 2 else -1)


def _gap_aware_axis(adjacency, constraints):
    """Greedy discrete positions with original signed gaps in each constraint."""
    palette = [0.] + [sign*STEP_CM*level for level in range(1,6) for sign in (1,-1)]
    neighbours = defaultdict(list)
    for a,b,gap in constraints:
        neighbours[a].append((b,gap))
        neighbours[b].append((a,-gap))
    assigned, blocked = {},{node:set() for node in adjacency}
    versions = Counter()
    heap = [(0,-len(edges),node,0) for node,edges in adjacency.items()]
    heapq.heapify(heap)
    while heap:
        _, _, node,version = heapq.heappop(heap)
        if node in assigned or version != versions[node]:
            continue
        choice = next((i for i in range(len(palette)) if i not in blocked[node]),None)
        if choice is None:
            raise ValueError('No safe axis offset within +/-0.45 cm for '+node)
        assigned[node] = palette[choice]
        for neighbour,gap in neighbours[node]:
            if neighbour in assigned:
                continue
            # gap is nodeOriginal - neighbourOriginal; the neighbour's equation
            # is -gap + neighbourOffset - nodeOffset.
            old_size = len(blocked[neighbour])
            blocked[neighbour].update(i for i,value in enumerate(palette)
                                      if abs(-gap+value-assigned[node]) <= MIN_NORMAL_PROJECTION_CM+1e-6)
            if len(blocked[neighbour]) != old_size:
                versions[neighbour] += 1
                heapq.heappush(heap,(-len(blocked[neighbour]),-len(adjacency[neighbour]),neighbour,versions[neighbour]))
    return assigned


def _original_plane(row, component_id, geometry_by_id):
    record = geometry_by_id[component_id]
    normal = row['normal']
    axis = _axis(normal)
    if row.get('component_metadata'):
        metadata = next((m for key,m in zip(row['components'],row['component_metadata']) if key == component_id),{})
    else:
        metadata = {}
    if record.get('kind') in ('box','cube') or metadata.get('kind') == 'box':
        if 'bounds_cm' in record:
            bounds = record['bounds_cm']
        else:
            bounds = [[min(v[i] for v in record['vertices']) for i in range(3)],
                      [max(v[i] for v in record['vertices']) for i in range(3)]]
        point = bounds[1 if normal[axis] > 0 else 0]
        return _dot(normal,point)
    indices = row.get('face_indices_by_component',{}).get(component_id)
    if not indices:
        order = row['components'].index(component_id)
        indices = [pair[order] for pair in row.get('face_pair_samples',[])]
    if not indices:
        raise ValueError('No original face IDs for '+component_id)
    values = []
    for index in indices:
        triangle = record['triangles'][int(index)]
        if 'vertices' in record:
            points = [record['vertices'][int(i)] for i in triangle]
        else:
            points = triangle
        values.extend(_dot(normal,point) for point in points)
    return sum(values)/len(values)


def merge_scan_constraints(original_scan, additional_scans, geometry):
    """Accumulate newly touching pairs while recovering their ORIGINAL planes.

    Virtual scan plane_cm is intentionally not reused: it already includes the
    preceding plan's offset. Face IDs let every constraint retain its initial
    signed plane gap, so regenerated offsets cannot accidentally cancel it.
    """
    records = geometry['components'] if isinstance(geometry,dict) else geometry
    by_id = {row['id']:row for row in records}
    merged = dict(original_scan)
    rows = []
    seen = set()
    additions = Counter()
    for scan_index,scan in enumerate([original_scan]+list(additional_scans)):
        for original in scan.get('overlaps',[]):
            if original.get('intra_component') or original.get('exposed_area_cm2',0) <= 1e-6:
                if scan_index == 0:
                    rows.append(original)
                continue
            row = dict(original)
            a,b = row['components']
            pa = _original_plane(row,a,by_id)
            pb = _original_plane(row,b,by_id)
            row['original_signed_plane_gap_cm'] = pa-pb
            row['constraint_provenance_scan_index'] = scan_index
            axis = _axis(row['normal'])
            if axis is None:
                raise ValueError('Cannot merge non-axis constraint.')
            sign = 1 if row['normal'][axis] > 0 else -1
            signature = (a,b,axis,round((pa-pb)*sign,5))
            if signature in seen:
                continue
            seen.add(signature)
            rows.append(row)
            additions[str(scan_index)] += 1
    merged['overlaps'] = rows
    merged['overlap_count'] = len(rows)
    merged['constraint_closure'] = dict(source_scan_count=1+len(additional_scans),
                       unique_inter_constraint_count=len(seen),groups_added_per_scan=dict(additions),
                       original_signed_gap_preserved=True)
    return merged


def internal_mesh_summary(scan):
    """Distinct source triangle samples grouped by shared mesh, then component."""
    meshes = {}
    for row in scan.get('overlaps',[]):
        if not row.get('intra_component') or row.get('exposed_area_cm2',row.get('area_cm2',0)) <= 1e-6:
            continue
        component = row['components'][0]
        metadata = row.get('component_metadata',[])
        mesh = metadata[0].get('mesh','unknown') if metadata else 'unknown'
        record = meshes.setdefault(mesh,dict(mesh=mesh,groups=0,face_pair_count=0,exposed_area_cm2=0.,
                                             components=set(),triangles=set(),pairs=set(),normals=Counter(),
                                             examples=[]))
        record['groups'] += 1
        record['face_pair_count'] += row.get('face_pair_count',0)
        record['exposed_area_cm2'] += row.get('exposed_area_cm2',row.get('area_cm2',0))
        record['components'].add(component)
        record['normals'][tuple(round(x,5) for x in row['normal'])] += 1
        samples = row.get('face_pair_samples',[])
        for a,b in samples:
            record['triangles'].update((int(a),int(b)))
            record['pairs'].add(tuple(sorted((int(a),int(b)))))
        if len(record['examples']) < 8:
            record['examples'].append(dict(component=component,normal=row['normal'],
                                           exposed_area_cm2=row.get('exposed_area_cm2',0),
                                           triangle_pair_samples=samples[:8],overlap_bounds_cm=row.get('overlap_bounds_cm')))
    result = []
    for record in meshes.values():
        record['component_count'] = len(record['components'])
        record['component_samples'] = sorted(record.pop('components'))[:12]
        record['unique_sample_triangle_count'] = len(record['triangles'])
        record['triangle_id_samples'] = sorted(record.pop('triangles'))[:128]
        record['unique_sample_pair_count'] = len(record['pairs'])
        record['triangle_pair_samples'] = [list(p) for p in sorted(record.pop('pairs'))[:96]]
        record['normal_groups'] = [dict(normal=list(n),groups=count) for n,count in record.pop('normals').most_common(16)]
        result.append(record)
    result.sort(key=lambda r:(-r['exposed_area_cm2'],r['mesh']))
    return result


def create_offsets(scan):
    """Plan constant world-space render vectors; validate every old constraint.

    Separation is ABS(normal dot (offsetA-offsetB)), because a duplicated volume
    contains opposing normal face groups. Signed-positive separation for both
    opposing faces of one pair is mathematically impossible. This solves exposed
    cross-component groups; fully buried and intra-component groups stay reported.
    Non-axis scans are rejected explicitly rather than silently left unresolved.
    """
    graphs = [defaultdict(set) for _ in range(3)]
    axis_constraints = [[] for _ in range(3)]
    constraints = []
    classifications = Counter()
    non_axis = []
    for row in scan.get('overlaps',[]):
        if row.get('exposed_area_cm2',row.get('area_cm2',0)) <= 1e-6:
            classifications['fully_buried_groups'] += 1
            continue
        if row.get('intra_component') or row['components'][0] == row['components'][1]:
            classifications['intra_exposed_groups'] += 1
            continue
        classifications['inter_exposed_groups'] += 1
        a,b = row['components']
        axis = _axis(row['normal'])
        if axis is None:
            non_axis.append(dict(components=[a,b],normal=row['normal']))
            continue
        graphs[axis][a].add(b)
        graphs[axis][b].add(a)
        signed_gap = float(row.get('original_signed_plane_gap_cm',0.))
        sign = 1 if row['normal'][axis] > 0 else -1
        axis_constraints[axis].append((a,b,signed_gap*sign))
        constraints.append(row)
    if non_axis:
        raise ValueError('Offset planner currently requires axis normals; %d non-axis exposed groups, e.g. %r' % (len(non_axis),non_axis[:3]))
    offsets = {}
    axis_summaries = []
    for axis, graph in enumerate(graphs):
        has_gaps = any(abs(gap) > 1e-5 for _,_,gap in axis_constraints[axis])
        if has_gaps:
            assigned = _gap_aware_axis(graph,axis_constraints[axis])
            distinct = sorted(set(assigned.values()),key=lambda value:(abs(value),-value))
            colours = {node:distinct.index(value) for node,value in assigned.items()}
        else:
            colours = _colour(graph)
            assigned = {node:_level(colour)*STEP_CM for node,colour in colours.items()}
        for node, value in assigned.items():
            offsets.setdefault(node,[0.,0.,0.])[axis] = round(value,8)
        axis_summaries.append(dict(axis='XYZ'[axis],nodes=len(graph),edges=sum(len(v) for v in graph.values())//2,
                                   colour_count=max(colours.values(),default=-1)+1,
                                   colour_histogram={str(k):v for k,v in sorted(Counter(colours.values()).items())},
                                   maximum_absolute_axis_offset_cm=max((abs(v[axis]) for v in offsets.values()),default=0.)))
    projections = []
    failed = []
    for row in constraints:
        a,b = row['components']
        delta = [x-y for x,y in zip(offsets.get(a,(0,0,0)),offsets.get(b,(0,0,0)))]
        separation = abs(float(row.get('original_signed_plane_gap_cm',0.))+_dot(row['normal'],delta))
        projections.append(separation)
        if separation <= MIN_NORMAL_PROJECTION_CM:
            failed.append(dict(components=[a,b],normal=row['normal'],separation_cm=separation))
    maximum_norm = max((_norm(v) for v in offsets.values()),default=0.)
    oversized = {node:v for node,v in offsets.items() if _norm(v) > MAX_OFFSET_NORM_CM}
    if failed or oversized:
        raise ValueError('Invalid offset plan: %d under-separated groups, %d vectors > %.2f cm' % (len(failed),len(oversized),MAX_OFFSET_NORM_CM))
    constrained_nodes = len(offsets)
    unmoved = sum(_norm(v) < 1e-10 for v in offsets.values())
    offsets = {node:v for node,v in sorted(offsets.items()) if _norm(v) >= 1e-10}
    summary = dict(schema='oldtown-surface-offset-plan-v1',passed=True,
                   method='Deterministic DSATUR independently for X/Y/Z; gap-aware discrete palette for nonzero original gaps; constant world-space render offsets.',
                   step_cm=STEP_CM,minimum_required_absolute_normal_projection_cm=MIN_NORMAL_PROJECTION_CM,
                   actual_minimum_absolute_normal_projection_cm=min(projections,default=None),
                   maximum_allowed_offset_norm_cm=MAX_OFFSET_NORM_CM,actual_maximum_offset_norm_cm=maximum_norm,
                   classifications=dict(classifications),constraint_face_groups=len(constraints),
                   constrained_components=constrained_nodes,shifted_components=len(offsets),unmoved_constrained_components=unmoved,
                   axes=axis_summaries,internal_meshes=internal_mesh_summary(scan),
                   constraint_closure=scan.get('constraint_closure'),
                   full_map_rescan_required=True,
                   limitations=['Input must have independently verified correct world triangle winding.',
                                'Old-pair constraints alone do not prove absence of newly near-coplanar pairs; scan virtually shifted full map before Unreal application.',
                                'Internal same-component coplanarity needs mesh or component geometry repair; one constant offset cannot separate two faces of the same mesh.',
                                'Fully buried classifications are retained as evidence and excluded from render offsets.'])
    return offsets, summary


def apply_offsets(records, offsets):
    """Virtual rendered geometry for a later scan; never change caller records."""
    result = []
    for row in records:
        delta = offsets.get(row['id'])
        if delta is None:
            result.append(row)
            continue
        updated = dict(row)
        if 'vertices' in row:
            updated['vertices'] = [[p[i]+delta[i] for i in range(3)] for p in row['vertices']]
        elif row.get('triangles') and isinstance(row['triangles'][0][0],(list,tuple)):
            updated['triangles'] = [[[p[i]+delta[i] for i in range(3)] for p in triangle] for triangle in row['triangles']]
        if 'bounds_cm' in row:
            updated['bounds_cm'] = [[p[i]+delta[i] for i in range(3)] for p in row['bounds_cm']]
        updated['render_offset_cm'] = delta[:]
        result.append(updated)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scan',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--geometry-input',type=Path)
    parser.add_argument('--virtual-output',type=Path)
    args = parser.parse_args()
    scan = json.loads(args.scan.read_text(encoding='utf-8-sig'))
    offsets, summary = create_offsets(scan)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(offsets_cm=offsets,summary=summary),ensure_ascii=False,indent=2),encoding='utf-8')
    if args.virtual_output:
        if not args.geometry_input:
            raise ValueError('--virtual-output requires --geometry-input')
        geometry = json.loads(args.geometry_input.read_text(encoding='utf-8-sig'))
        virtual = dict(geometry,components=apply_offsets(geometry['components'],offsets),
                       virtual_geometry=True,virtual_offset_plan=str(args.output))
        args.virtual_output.parent.mkdir(parents=True,exist_ok=True)
        args.virtual_output.write_text(json.dumps(virtual,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('passed','constraint_face_groups','constrained_components','shifted_components',
                  'actual_minimum_absolute_normal_projection_cm','actual_maximum_offset_norm_cm','axes')},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
