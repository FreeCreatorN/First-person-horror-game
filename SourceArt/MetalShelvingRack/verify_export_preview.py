"""Render the exported low rack with its baked UE texture inputs."""

from pathlib import Path
import json

import bpy

root = Path(__file__).resolve().parent
out = root / 'Exports'
entry = json.loads((out / 'report_4Level_Low.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(root / entry['source']))
scene = bpy.context.scene
for obj in list(bpy.data.collections['METAL SHELVING RACK'].all_objects):
    bpy.data.objects.remove(obj, do_unlink=True)
before = set(scene.objects)
bpy.ops.import_scene.fbx(filepath=str(out / entry['fbx']))
imported = set(scene.objects) - before
obj = next(obj for obj in imported if obj.name == entry['name'])
for hull in imported - {obj}:
    assert hull.name.startswith('UCX_'), hull.name
    bpy.data.objects.remove(hull, do_unlink=True)
obj.data.calc_loop_triangles()
assert len(obj.data.loop_triangles) == entry['triangles']
assert len(obj.data.uv_layers) == 1
for size, lo, hi in zip(obj.dimensions, entry['bounds_min_m'], entry['bounds_max_m']):
    assert abs(size - (hi-lo)) < .0001

material = bpy.data.materials.new('Preview · baked UE shader inputs')
material.use_nodes = True
tree = material.node_tree
shader = next(node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED')
for label, texture in [('base_color', 'sRGB'), ('orm', 'Non-Color')]:
    image = bpy.data.images.load(str(out / entry[label]))
    image.colorspace_settings.name = texture
    node = tree.nodes.new('ShaderNodeTexImage')
    node.image = image
    if label == 'base_color':
        tree.links.new(node.outputs['Color'], shader.inputs['Base Color'])
    else:
        rgb = tree.nodes.new('ShaderNodeSeparateColor')
        tree.links.new(node.outputs['Color'], rgb.inputs['Color'])
        tree.links.new(rgb.outputs['Green'], shader.inputs['Roughness'])
        tree.links.new(rgb.outputs['Blue'], shader.inputs['Metallic'])
obj.data.materials.clear()
obj.data.materials.append(material)
scene.render.resolution_percentage = 78
scene.cycles.samples = 16
scene.render.filepath = str(out / 'Metal_Shelving_4_Level_Low_Baked_Preview.png')
bpy.ops.render.render(write_still=True)
print('RACK_FBX_ROUNDTRIP_AND_BAKED_PREVIEW_VERIFIED', flush=True)
