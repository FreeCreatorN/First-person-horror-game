"""Validate and bake the single dining table; render the saved PNG atlases.

Run once on a freshly generated LargeDiningTable.blend. FBX files are read for
roundtrip validation only and never rewritten. Preview lights stay in Blender.
"""
import hashlib
import json
import os
import time
import traceback
from array import array
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'LargeDiningTable.blend'
FBX = OUT / 'SM_LargeDiningTable.fbx'
TEXTURES = OUT / 'Textures'
MESH_NAME = 'SM_LargeDiningTable'
COLOR_RES = int(os.environ.get('DINING_BAKE_COLOR_RES', '4096'))
DATA_RES = int(os.environ.get('DINING_BAKE_DATA_RES', '2048'))
BAKE_SAMPLES = int(os.environ.get('DINING_BAKE_SAMPLES', '8'))
report = {'success': False, 'geometry': {}, 'uv': {}, 'fbx_roundtrip': {},
          'bakes': {}, 'renders': {}, 'settings': {
              'color_resolution': COLOR_RES, 'data_resolution': DATA_RES,
              'cycles_device': 'CPU', 'bake_samples': BAKE_SAMPLES,
              'margin_pixels': 16, 'selected_to_active': False,
              'normal_space': 'TANGENT', 'normal_green': 'POS_Y'}}
started = time.perf_counter()


def log(message):
    print('DINING_BAKE ' + message, flush=True)


def write_report():
    report['elapsed_seconds'] = time.perf_counter() - started
    (OUT / 'validation_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def geometry_info(obj):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
    try:
        mesh.calc_loop_triangles()
        world_vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        minimum = [min(v[i] for v in world_vertices) for i in range(3)]
        maximum = [max(v[i] for v in world_vertices) for i in range(3)]
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            result = {'vertices': len(bm.verts), 'faces': len(bm.faces),
                      'non_manifold_edges': sum(not edge.is_manifold for edge in bm.edges),
                      'loose_vertices': sum(not vertex.link_edges for vertex in bm.verts)}
        finally:
            bm.free()
        result.update({'triangles': len(mesh.loop_triangles), 'bounds_min_m': minimum,
                       'bounds_max_m': maximum,
                       'dimensions_m': [maximum[i] - minimum[i] for i in range(3)]})
        return result
    finally:
        evaluated.to_mesh_clear()


def uv_info(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    assert mesh.uv_layers.active, MESH_NAME + ' has no UV0'
    data = mesh.uv_layers.active.data
    minimum = [min(item.uv[i] for item in data) for i in range(2)]
    maximum = [max(item.uv[i] for item in data) for i in range(2)]
    area, degenerates = 0., 0
    for triangle in mesh.loop_triangles:
        a, b, c = [data[i].uv for i in triangle.loops]
        triangle_area = abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) * .5
        area += triangle_area
        degenerates += triangle_area < 1.e-13
    result = {'layers': [layer.name for layer in mesh.uv_layers],
              'active': mesh.uv_layers.active.name, 'min': minimum, 'max': maximum,
              'triangle_uv_area_sum': area, 'zero_area_triangles': degenerates}
    assert all(v >= -1.e-5 for v in minimum) and all(v <= 1.00001 for v in maximum), result
    assert degenerates == 0 and 0. < area <= 1.001, result
    return result


def verify_roundtrip(obj, source_report):
    expected = geometry_info(obj)
    original_objects = set(bpy.data.objects)
    original_meshes = set(bpy.data.meshes)
    original_materials = set(bpy.data.materials)
    original_collections = set(bpy.data.collections)
    result = {'success': False, 'source': str(FBX), 'sha256': sha256(FBX)}
    report['fbx_roundtrip'] = result
    log('FBX roundtrip begin')
    try:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.import_scene.fbx(filepath=str(FBX), use_anim=False)
        imported = set(bpy.data.objects) - original_objects
        meshes = [o for o in imported if o.type == 'MESH' and not o.name.startswith('UCX_')]
        collisions = [o for o in imported if o.type == 'MESH' and o.name.startswith('UCX_')]
        assert len(meshes) == 1, [o.name for o in meshes]
        assert not any(o.type in ('CAMERA', 'LIGHT') for o in imported), [o.name for o in imported]
        imported_obj = meshes[0]
        actual = geometry_info(imported_obj)
        expected_count = source_report['parts'][MESH_NAME]['collision_hulls']
        expected_count = expected_count if isinstance(expected_count, int) else len(expected_count)
        result.update({'imported_mesh': imported_obj.name, 'geometry': actual,
                       'ucx_count': len(collisions), 'expected_ucx_count': expected_count,
                       'uv_layers': len(imported_obj.data.uv_layers),
                       'pivot_world_m': list(imported_obj.matrix_world.translation),
                       'material_slots': [slot.material.name if slot.material else None
                                          for slot in imported_obj.material_slots]})
        assert len(collisions) == expected_count, result
        assert actual['non_manifold_edges'] == 0 and actual['loose_vertices'] == 0, result
        assert len(imported_obj.data.uv_layers) >= 1, result
        assert imported_obj.matrix_world.translation.length < .00001, result
        for key in ('dimensions_m', 'bounds_min_m', 'bounds_max_m'):
            assert max(abs(a - b) for a, b in zip(actual[key], expected[key])) < .00002, (key, result)
        original_slots = {slot.material.name for slot in obj.material_slots if slot.material}
        imported_slots = {slot.material.name.split('.')[0] for slot in imported_obj.material_slots if slot.material}
        assert original_slots == imported_slots, (original_slots, imported_slots)
        result['success'] = True
    finally:
        for imported_obj in list(set(bpy.data.objects) - original_objects):
            bpy.data.objects.remove(imported_obj, do_unlink=True)
        for collection in list(set(bpy.data.collections) - original_collections):
            bpy.data.collections.remove(collection)
        for datablocks, originals in ((bpy.data.meshes, original_meshes),
                                     (bpy.data.materials, original_materials)):
            for item in list(set(datablocks) - originals):
                if item.users == 0:
                    datablocks.remove(item)
    log('FBX roundtrip passed')


def input_socket(node, identifier):
    return next(socket for socket in node.inputs
                if socket.identifier == identifier or socket.name == identifier)


def bake_channel(obj, channel, resolution):
    name = 'T_LargeDiningTable_' + channel
    image = bpy.data.images.new(name, width=resolution, height=resolution,
                                alpha=False, float_buffer=False)
    image.colorspace_settings.name = 'sRGB' if channel == 'BaseColor' else 'Non-Color'
    image.file_format = 'PNG'
    image.filepath_raw = str(TEXTURES / (name + '.png'))
    materials = list(dict.fromkeys(slot.material for slot in obj.material_slots if slot.material))
    original_outputs, temporary_nodes = [], []
    disk_image = None
    channel_started = time.perf_counter()
    log('Bake begin ' + channel + ' ' + str(resolution))
    try:
        for material in materials:
            assert material.use_nodes, material.name
            material.use_fake_user = True
            nodes, links = material.node_tree.nodes, material.node_tree.links
            shader = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
            output = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL' and node.is_active_output)
            surface = output.inputs[0]
            original_outputs.append((material, surface, [(link.from_socket, link.to_socket) for link in surface.links]))
            target = nodes.new('ShaderNodeTexImage')
            target.image = image
            target.label = 'Temporary bake target'
            temporary_nodes.append((material, target))
            if channel != 'Normal':
                source = input_socket(shader, 'Base Color' if channel == 'BaseColor' else 'Roughness')
                emission = nodes.new('ShaderNodeEmission')
                temporary_nodes.append((material, emission))
                emission.inputs[1].default_value = 1.
                if source.is_linked:
                    links.new(source.links[0].from_socket, emission.inputs[0])
                else:
                    value = source.default_value
                    emission.inputs[0].default_value = (value, value, value, 1.) if channel == 'Roughness' else value
                links.new(emission.outputs[0], surface)
            for node in nodes:
                node.select = False
            target.select = True
            nodes.active = target
        bpy.ops.object.select_all(action='DESELECT')
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        result = bpy.ops.object.bake(type='NORMAL' if channel == 'Normal' else 'EMIT',
                                     margin=16, margin_type='EXTEND', use_selected_to_active=False,
                                     normal_space='TANGENT', normal_r='POS_X', normal_g='POS_Y',
                                     normal_b='POS_Z', target='IMAGE_TEXTURES', use_clear=True)
        assert result == {'FINISHED'} and image.has_data, (channel, result)
        image.save()
        path = Path(image.filepath_raw)
        assert path.is_file() and path.stat().st_size > 1024, str(path)
        disk_image = bpy.data.images.load(str(path), check_existing=False)
        disk_image.colorspace_settings.name = image.colorspace_settings.name
        disk_size = tuple(disk_image.size)
        _first_pixel = disk_image.pixels[0]  # Force the lazy PNG decode after color-space changes.
        assert disk_image.has_data and disk_size == tuple(image.size), (name, disk_size)
        width, height = disk_image.size
        channels = disk_image.channels
        pixels = array('f', [0.]) * (width * height * channels)
        samples = []
        try:
            disk_image.pixels.foreach_get(pixels)
            for y in range(height // 64, height, max(1, height // 32)):
                for x in range(width // 64, width, max(1, width // 32)):
                    index = (y * width + x) * channels
                    samples.append(tuple(pixels[index + i] for i in range(3)))
        finally:
            del pixels
        minimum = [min(p[i] for p in samples) for i in range(3)]
        maximum = [max(p[i] for p in samples) for i in range(3)]
        assert max(maximum) > .001, (channel, minimum, maximum)
        report['bakes'][name] = {
            'path': str(path), 'resolution': list(disk_image.size),
            'colorspace': disk_image.colorspace_settings.name,
            'bytes': path.stat().st_size, 'sha256': sha256(path),
            'sample_min_rgb': minimum, 'sample_max_rgb': maximum,
            'method': 'NORMAL' if channel == 'Normal' else 'EMIT from Principled input',
            'reloaded_from_saved_png': True,
            'elapsed_seconds': time.perf_counter() - channel_started,
        }
        disk_image.filepath_raw = '//Textures/' + path.name
        write_report()
    finally:
        for material, surface, original_links in original_outputs:
            for link in list(surface.links):
                material.node_tree.links.remove(link)
            for from_socket, to_socket in original_links:
                material.node_tree.links.new(from_socket, to_socket)
        for material, node in temporary_nodes:
            material.node_tree.nodes.remove(node)
    assert disk_image, name
    if image.users == 0:
        bpy.data.images.remove(image)
    disk_image.name = name
    log('Bake complete ' + channel + ' seconds=' + str(round(time.perf_counter() - channel_started, 1)))
    return disk_image


def baked_material(images):
    material = bpy.data.materials.new('M_LargeDiningTable_Baked')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (520, 60)
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.location = (200, 80)
    input_socket(shader, 'Metallic').default_value = 0.
    links.new(shader.outputs[0], output.inputs[0])
    for channel, y in (('BaseColor', 260), ('Roughness', -20), ('Normal', -300)):
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = images[channel]
        texture.label = channel
        texture.location = (-650, y)
        if channel == 'Normal':
            normal = nodes.new('ShaderNodeNormalMap')
            normal.space = 'TANGENT'
            normal.location = (-170, -220)
            links.new(texture.outputs[0], normal.inputs[1])
            links.new(normal.outputs[0], input_socket(shader, 'Normal'))
        else:
            links.new(texture.outputs[0], input_socket(shader, 'Base Color' if channel == 'BaseColor' else 'Roughness'))
    report['baked_material'] = {'name': material.name, 'emission_connected': False,
                               'images': {key: image.name for key, image in images.items()}}
    return material


try:
    assert COLOR_RES >= 512 and DATA_RES >= 512
    assert SOURCE.is_file() and FBX.is_file(), str(SOURCE)
    TEXTURES.mkdir(exist_ok=True)
    log('Load ' + str(SOURCE))
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.context.scene
    obj = bpy.data.objects.get(MESH_NAME)
    assert obj and obj.type == 'MESH', MESH_NAME
    assert scene.camera, 'Preview scene needs a camera'
    source_report = json.loads((OUT / 'model_report.json').read_text(encoding='utf-8-sig'))
    report['geometry'] = geometry_info(obj)
    assert report['geometry']['non_manifold_edges'] == 0 and report['geometry']['loose_vertices'] == 0, report['geometry']
    assert obj.matrix_world.translation.length < .00001, list(obj.matrix_world.translation)
    report['uv'] = uv_info(obj)
    report['geometry']['source_materials'] = [slot.material.name if slot.material else None for slot in obj.material_slots]
    attributes = {}
    for name in ('WoodCoord', 'WoodTone', 'Wear'):
        attribute = obj.data.attributes.get(name)
        assert attribute and len(attribute.data) > 0, ('Missing shader attribute', name)
        attributes[name] = {'domain': attribute.domain, 'data_type': attribute.data_type,
                            'count': len(attribute.data)}
    report['geometry']['shader_attributes'] = attributes
    write_report()
    verify_roundtrip(obj, source_report)
    write_report()

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = BAKE_SAMPLES
    scene.render.bake.margin = 16
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.normal_space = 'TANGENT'
    scene.render.bake.normal_r, scene.render.bake.normal_g, scene.render.bake.normal_b = 'POS_X', 'POS_Y', 'POS_Z'
    images = {channel: bake_channel(obj, channel, COLOR_RES if channel == 'BaseColor' else DATA_RES)
              for channel in ('BaseColor', 'Roughness', 'Normal')}
    material = baked_material(images)
    for slot in obj.material_slots:
        slot.material = material

    scene.cycles.samples = int(os.environ.get('DINING_RENDER_SAMPLES', '32'))
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(OUT / 'LargeDiningTable_Preview.png')
    log('Render full table preview')
    bpy.ops.render.render(write_still=True)
    report['renders']['preview'] = scene.render.filepath
    camera = scene.camera
    camera_matrix, camera_lens = camera.matrix_world.copy(), camera.data.lens
    camera_type = camera.data.type
    original_resolution = (scene.render.resolution_x, scene.render.resolution_y)
    try:
        camera.location = (1.85, -1.90, 1.26)
        target = Vector((.88, -.32, .61))
        camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.lens = 62.
        camera.data.type = 'PERSP'
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
        scene.render.filepath = str(OUT / 'LargeDiningTable_Detail.png')
        bpy.context.view_layer.update()
        log('Render tabletop corner and turned leg joinery')
        bpy.ops.render.render(write_still=True)
        report['renders']['detail'] = scene.render.filepath
    finally:
        camera.matrix_world = camera_matrix
        camera.data.lens = camera_lens
        camera.data.type = camera_type
        scene.render.resolution_x, scene.render.resolution_y = original_resolution
        bpy.context.view_layer.update()
    assert sha256(FBX) == report['fbx_roundtrip']['sha256'], 'FBX changed during baking'
    scene.render.filepath = str(OUT / 'LargeDiningTable_Preview.png')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    report['blend_file'] = str(SOURCE)
    report['success'] = True
    write_report()
    log('SUCCESS seconds=' + str(round(report['elapsed_seconds'], 1)))
except Exception:
    report['error'] = traceback.format_exc()
    write_report()
    log('FAILED ' + report['error'])
    raise

