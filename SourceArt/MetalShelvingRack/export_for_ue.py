"""Bake the authored rack finish and export an isolated UE static mesh."""

import hashlib
import json
import os
from pathlib import Path
import sys

import bpy
from mathutils import Vector


root = Path(__file__).resolve().parent
output = root / 'Exports'
output.mkdir(exist_ok=True)
variants = {
    '7Level': ('Metal_Shelving_Rack.blend', 'model_report.json'),
    '4Level': ('Metal_Shelving_Rack_4_Level.blend', 'model_report_4_Level.json'),
    '4Level_Low': ('Metal_Shelving_Rack_4_Level_Low.blend', 'model_report_4_Level_Low.json'),
}
resolution = 4096


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def select_only(objects, active):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active


def mesh_bounds(obj):
    world = obj.matrix_world
    corners = [world @ Vector(corner) for corner in obj.bound_box]
    return [min(p[i] for p in corners) for i in range(3)], [max(p[i] for p in corners) for i in range(3)]


def component_groups(objects):
    """One thin collision hull per tray and one per upright."""
    uprights = {}
    trays = []
    for obj in objects:
        if obj.name.startswith('Upright '):
            prefix = obj.name.split(' · ')[0]
            uprights.setdefault(prefix, []).append(mesh_bounds(obj))
        elif obj.name.endswith('folded tray'):
            trays.append(mesh_bounds(obj))
    assert len(uprights) == 8
    posts = []
    for pieces in uprights.values():
        posts.append(([min(lo[i] for lo, _ in pieces) for i in range(3)],
                      [max(hi[i] for _, hi in pieces) for i in range(3)]))
    return posts, trays


def box(name, lower, upper):
    vertices = [tuple((lower, upper)[flag][i] for i, flag in enumerate(flags))
                for flags in ((0,0,0), (1,0,0), (1,1,0), (0,1,0), (0,0,1), (1,0,1), (1,1,1), (0,1,1))]
    faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def triangulate_and_unwrap(obj):
    select_only([obj], obj)
    modifier = obj.modifiers.new('Explicit export triangles', 'TRIANGULATE')
    modifier.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=.0014, area_weight=.65, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    uv = obj.data.uv_layers.active.uv
    assert all(-.00003 <= component <= 1.00003 for uv_value in uv for component in uv_value.vector)
    assert len(uv) == len(obj.data.loops)
    return len(obj.data.polygons)


def connect_value(tree, source, target):
    if source.links:
        tree.links.new(source.links[0].from_socket, target)
    else:
        target.default_value = source.default_value


def bake(obj, filename, orm):
    bpy.context.scene.cycles.samples = 1
    image = bpy.data.images.new(filename, width=resolution, height=resolution, alpha=False)
    image.colorspace_settings.name = 'Non-Color' if orm else 'sRGB'
    for material in obj.data.materials:
        tree = material.node_tree
        shader = next(node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED')
        surface = next(node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL').inputs['Surface']
        emission = tree.nodes.new('ShaderNodeEmission')
        if orm:
            channels = tree.nodes.new('ShaderNodeCombineColor')
            channels.inputs['Red'].default_value = 1.
            connect_value(tree, shader.inputs['Roughness'], channels.inputs['Green'])
            connect_value(tree, shader.inputs['Metallic'], channels.inputs['Blue'])
            tree.links.new(channels.outputs['Color'], emission.inputs['Color'])
        else:
            connect_value(tree, shader.inputs['Base Color'], emission.inputs['Color'])
        tree.links.new(emission.outputs[0], surface)
        texture = tree.nodes.new('ShaderNodeTexImage')
        texture.image = image
        tree.nodes.active = texture
    if bpy.ops.object.bake(type='EMIT', margin=4, margin_type='EXTEND', use_clear=True) != {'FINISHED'}:
        raise RuntimeError(f'Bake did not complete: {filename}')
    image.filepath_raw = str(output / filename)
    image.file_format = 'PNG'
    image.save()
    assert (output / filename).stat().st_size > 4096


def export_variant(variant):
    source_name, source_report = variants[variant]
    source = root / source_name
    digest = sha(source)
    reference = json.loads((root / source_report).read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = int(os.environ.get('RACK_EXPORT_THREADS', 9))
    asset = bpy.data.collections['METAL SHELVING RACK']
    originals = sorted(asset.all_objects, key=lambda obj: obj.name)
    assert len([obj for obj in originals if obj.name.endswith('folded tray')]) == reference['shelf_trays']
    depsgraph = bpy.context.evaluated_depsgraph_get()
    copies = []
    for obj in originals:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
        new = bpy.data.objects.new('Export ' + obj.name, mesh)
        scene.collection.objects.link(new)
        new.matrix_world = obj.matrix_world
        copies.append(new)
    bpy.context.view_layer.update()
    posts, trays = component_groups(originals)
    select_only(copies, copies[0])
    bpy.ops.object.join()
    obj = bpy.context.object
    mesh_name = 'SM_MetalShelvingRack_' + variant
    obj.name = mesh_name
    obj.data.name = mesh_name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for item in list(scene.objects):
        if item != obj:
            bpy.data.objects.remove(item, do_unlink=True)
    print(f'RACK_EXPORT {variant} unwrapping', flush=True)
    triangles = triangulate_and_unwrap(obj)
    assert triangles == reference['evaluated_triangles'], (triangles, reference['evaluated_triangles'])
    assert obj.data.color_attributes.get('Wear') is not None
    lower, upper = mesh_bounds(obj)
    for i, size in enumerate(reference['evaluated_dimensions_m']):
        assert abs(upper[i] - lower[i] - size) < .00015
    texture_prefix = 'T_MetalShelvingRack_' + variant
    base_color, orm = texture_prefix + '_BaseColor.png', texture_prefix + '_ORM.png'
    print(f'RACK_EXPORT {variant} bake base color', flush=True)
    bake(obj, base_color, orm=False)
    print(f'RACK_EXPORT {variant} bake ORM', flush=True)
    bake(obj, orm, orm=True)
    obj.data.materials.clear()
    obj.data.materials.append(bpy.data.materials.new('M_Rack_Baked'))
    for face in obj.data.polygons:
        face.material_index = 0
    hulls = [box(f'UCX_{mesh_name}_{i:03d}', lo, hi) for i, (lo,hi) in enumerate(posts+trays, 1)]
    assert len(trays) == reference['shelf_trays']
    select_only([obj, *hulls], obj)
    fbx = mesh_name + '.fbx'
    bpy.ops.export_scene.fbx(filepath=str(output / fbx), use_selection=True, object_types={'MESH'},
                             global_scale=1, apply_unit_scale=True, axis_forward='-Z', axis_up='Y',
                             bake_anim=False, use_mesh_modifiers=False, mesh_smooth_type='FACE', path_mode='STRIP')
    assert sha(source) == digest
    entry = {'name':mesh_name, 'fbx':fbx, 'base_color':base_color, 'orm':orm,
             'material':'MI_MetalShelvingRack_' + variant, 'source':source_name, 'source_sha256':digest,
             'triangles':triangles, 'bounds_min_m':lower, 'bounds_max_m':upper, 'collision_hulls':len(hulls),
             'levels':reference['levels'], 'slots':['M_Rack_Baked'], 'sha256':{filename:sha(output/filename) for filename in (fbx,base_color,orm)}}
    (output / f'report_{variant}.json').write_text(json.dumps(entry, indent=2), encoding='utf-8')
    print(f'RACK_EXPORT_VERIFIED {variant} {triangles} triangles {len(hulls)} collision hulls', flush=True)


args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(variants)
for variant in args:
    export_variant(variant)
if set(args) == set(variants):
    assets = [json.loads((output/f'report_{variant}.json').read_text(encoding='utf-8')) for variant in variants]
    hashes = {name:digest for entry in assets for name,digest in entry['sha256'].items()}
    (output/'export_report.json').write_text(json.dumps({'success':True,'assets':assets,'sha256':hashes,
                                                       'baked_resolution':resolution},indent=2),encoding='utf-8')
