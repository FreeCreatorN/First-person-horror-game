import bmesh
import bpy
from collections import defaultdict
import json
from pathlib import Path

root = Path(__file__).resolve().parent
stem = Path(bpy.data.filepath).stem
variant = next((suffix for suffix in ('_4_Level_Low', '_4_Level') if stem.endswith(suffix)), '')
report_path = root / f'model_report{variant}.json'
scene = bpy.context.scene
asset = bpy.data.collections['METAL SHELVING RACK']
depsgraph = bpy.context.evaluated_depsgraph_get()

def boundary_count(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    adjacency = defaultdict(set)
    for edge in bm.edges:
        if edge.is_boundary:
            a, b = (vertex.index for vertex in edge.verts)
            adjacency[a].add(b)
            adjacency[b].add(a)
    bm.free()
    assert all(len(neighbors) == 2 for neighbors in adjacency.values())
    unseen = set(adjacency)
    contours = 0
    while unseen:
        contours += 1
        queue = [unseen.pop()]
        while queue:
            for vertex in adjacency[queue.pop()] & unseen:
                unseen.remove(vertex)
                queue.append(vertex)
    return contours

report = json.loads(report_path.read_text(encoding='utf-8'))
actual_trays = sum(obj.name.endswith('folded tray') for obj in asset.all_objects)
assert actual_trays == report['shelf_trays'] == report['levels']*3
triangles = 0
slot_total = 0
problems = []
bounds = [[],[],[]]
tray_bounds = defaultdict(list)
gusset_bottom = defaultdict(list)
for obj in asset.all_objects:
    if obj.get('slot_count'):
        holes = boundary_count(obj.data) - 1
        assert holes == obj['slot_count'], (obj.name, holes, obj['slot_count'])
        slot_total += holes
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    triangles += len(mesh.loop_triangles)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if any(not edge.is_manifold for edge in bm.edges):
        problems.append(obj.name)
    bm.free()
    for corner in evaluated.bound_box:
        for i, value in enumerate(corner):
            bounds[i].append(value + evaluated.location[i])
    if obj.name.endswith('folded tray') or 'hook gusset' in obj.name:
        shelf_number = int(obj.name.split(' / shelf ')[1][:2])
        z_values = [(evaluated.matrix_world @ vertex.co).z for vertex in mesh.vertices]
        if obj.name.endswith('folded tray'):
            tray_bounds[shelf_number].append((min(z_values), max(z_values)))
        else:
            gusset_bottom[shelf_number].append(min(z_values))
    evaluated.to_mesh_clear()
assert slot_total == report['through_slots']
assert not problems, problems
report.update(evaluated_triangles=triangles, sealed_asset_components=len(asset.all_objects),
              validated_cutouts=slot_total, evaluated_dimensions_m=[round(max(v)-min(v),4) for v in bounds])
if variant == '_4_Level_Low':
    assert all(len(tray_bounds[i]) == 3 and len(gusset_bottom[i]) == 12 for i in range(1,5))
    bottoms = [min(bottom for bottom, _ in tray_bounds[i]) for i in range(1,5)]
    tops = [max(top for _, top in tray_bounds[i]) for i in range(1,5)]
    top_clearances = [bottoms[i+1] - tops[i] for i in range(3)]
    side_clearances = [min(gusset_bottom[i+2]) - tops[i] for i in range(3)]
    bay_width = report['post_centers_x_m'][1] - report['post_centers_x_m'][0] - report['post_width_m']
    assert max(bounds[2]) < 1.60
    assert .418 <= min(gusset_bottom[1]) <= bottoms[0] < bay_width
    assert all(.32 < main < bay_width for main in top_clearances)
    assert all(.285 < side < .30 for side in side_clearances)
    report.update(opening_width_m=round(bay_width, 4), floor_clearance_main_m=round(bottoms[0], 4),
                  floor_clearance_at_brackets_m=round(min(gusset_bottom[1]), 4),
                  shelf_clearance_main_m=[round(value, 4) for value in top_clearances],
                  shelf_clearance_at_brackets_m=[round(value, 4) for value in side_clearances])
report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('RACK_VERIFIED', triangles, slot_total, flush=True)

for camera, output in [('01 · Front',f'Metal_Shelving{variant}_Front.png'), ('02 · Left front 45°',f'Metal_Shelving{variant}_45.png')]:
    scene.camera=bpy.data.objects[camera]
    scene.render.filepath=str(root/output)
    bpy.ops.render.render(write_still=True)
