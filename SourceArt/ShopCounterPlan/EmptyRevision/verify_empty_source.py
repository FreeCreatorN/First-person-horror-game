"""Read-only audit of the final empty planning-sheet counter source.

Run in an already-opened final .blend, or pass --report <model_report.json>
after Blender's '--' separator. No scene or source data is modified.
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy

HERE = Path(__file__).resolve().parent
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
report_path = Path(args[args.index('--report') + 1]) if '--report' in args else HERE.parent / 'model_report.json'
model = json.loads(report_path.read_text(encoding='utf-8-sig'))
expected_parts = {'Body', 'MetalFrame', 'GlassTop', 'GlassSurround', 'DisplayShelf', 'InteriorShelf',
                  'WoodDoorLeft', 'WoodDoorRight', 'GlassDoorLeft', 'GlassDoorRight'}
assert set(model['parts']) == expected_parts, sorted(model['parts'])
assert len(bpy.data.scenes) == 1, ('Unexpected archived/extra scenes', [s.name for s in bpy.data.scenes])
scene = bpy.context.scene
assert scene.name == model['source_scene'], (scene.name, model['source_scene'])

category_rows = model.get('planning_categories', [])
expected_categories = {'GlassTop', 'GlassSurround', 'MetalFrame', 'DisplayShelf', 'Body',
                       'WoodSlidingDoors', 'GlassSlidingDoors', 'InteriorShelf'}
assert len(category_rows) == 8 and {r['key'] for r in category_rows} == expected_categories
categories = {row['key']: bpy.data.collections[row['collection']] for row in category_rows}
preview_name = model.get('preview_collection')
model_roots = [c for c in scene.collection.children if c.name != preview_name]
assert len(model_roots) == 1, ('Expected one model root plus optional preview root', [c.name for c in scene.collection.children])
assert set(model_roots[0].children) == set(categories.values()), 'Planning categories must be the eight direct model-root children'
assert not list(model_roots[0].objects), 'Unexpected loose object directly under model root'

door_groups = {}
for group_key, prefix in [('WoodSlidingDoors', 'WoodDoor'), ('GlassSlidingDoors', 'GlassDoor')]:
    category = categories[group_key]
    empties = [o for o in category.objects if o.type == 'EMPTY']
    assert len(empties) == 1, (group_key, [o.name for o in category.objects])
    group = empties[0]
    assert group.name == group_key and group.parent is None
    assert all(abs(v) < 1e-6 for v in group.location) and all(abs(v) < 1e-6 for v in group.rotation_euler)
    assert all(abs(v-1) < 1e-6 for v in group.scale)
    leaves = [bpy.data.objects[model['parts'][prefix+side]['object']] for side in ('Left', 'Right')]
    assert set(group.children) == set(leaves), (group_key, [o.name for o in group.children])
    assert len(category.children) == 2
    assert set(category.children) == {bpy.data.collections[model['parts'][prefix+side]['collection']] for side in ('Left', 'Right')}
    for leaf in leaves:
        assert leaf.parent == group and leaf.type == 'MESH'
    door_groups[group_key] = [o.name for o in leaves]

allowed_objects = set()
triangles = {}
deps = bpy.context.evaluated_depsgraph_get()
for part, spec in model['parts'].items():
    coll = bpy.data.collections[spec['collection']]
    allowed_objects.update(coll.all_objects)
    mesh_objects = [o for o in coll.all_objects if o.type == 'MESH']
    assert len(mesh_objects) == 1 and mesh_objects[0].name == spec['object'], (part, [o.name for o in mesh_objects])
    if part in categories:
        assert coll == categories[part] and mesh_objects[0].parent is None, part
    count = 0
    for obj in coll.all_objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        count += len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    triangles[part] = count
    assert count == model['triangles_by_part'][part], (part, count, model['triangles_by_part'][part])

if preview_name:
    allowed_objects.update(bpy.data.collections[preview_name].all_objects)
for category in categories.values():
    allowed_objects.update(category.all_objects)

# Parent grouping empties are permitted; all mesh/light/camera data must belong
# to one of the cabinet/preview collections. Inspect global data, not only the
# active scene, so a hidden old scene or orphaned merchandise does not pass.
extras = [o.name for o in bpy.data.objects if o not in allowed_objects]
assert not extras, ('Unexpected objects outside final cabinet/preview collections', extras)
banned = ('removable merchandise', 'carton label', 'removable candy jar', 'jar paper label',
          'removable jar lid', 'display product', 'sweet jar', 'shop price stand')
goods = [o.name for o in bpy.data.objects if any(k in o.name.casefold() for k in banned)]
assert not goods, ('Merchandise still present in source', goods)
assert not model.get('stock_collection'), model.get('stock_collection')
assert model.get('optional_stock_triangles', 0) == 0
assert triangles['GlassTop'] == 12, triangles['GlassTop']
assert triangles['GlassSurround'] == 36, triangles['GlassSurround']
assert sum(triangles.values()) == model['total_triangles']
assert 1800 <= sum(triangles.values()) <= 3500

source = Path(bpy.data.filepath)
assert source.is_file(), source
result = {'success': True, 'source': str(source),
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'scene_count': len(bpy.data.scenes), 'scene': scene.name,
          'part_count': len(expected_parts), 'triangles_by_part': triangles,
          'total_triangles': sum(triangles.values()), 'merchandise_objects': goods,
          'unexpected_objects': extras, 'all_scenes_and_global_objects_checked': True,
          'planning_category_count': len(categories), 'planning_categories': [r['label'] for r in category_rows],
          'door_groups': door_groups, 'global_object_count': len(bpy.data.objects)}
(HERE / 'empty_source_audit.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('EMPTY_SOURCE_AUDIT', json.dumps(result, ensure_ascii=True), flush=True)
