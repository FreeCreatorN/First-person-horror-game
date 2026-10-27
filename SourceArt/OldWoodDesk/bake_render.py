"""Validate, bake six atlases, and render the old desk. Run with Blender -b.

The source FBXs are read for verification and never rewritten. Studio lights
remain preview helpers in the .blend only; final prop shaders have no emission
input and respond to ordinary scene lighting.
"""
import hashlib
import json
import math
import os
import time
import traceback
from array import array
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'OldWoodDesk.blend'
TEXTURES = OUT / 'Textures'
PARTS = ('Base', 'Drawer')
COLOR_RES = int(os.environ.get('DESK_BAKE_COLOR_RES', '4096'))
DATA_RES = int(os.environ.get('DESK_BAKE_DATA_RES', '2048'))
BAKE_SAMPLES = int(os.environ.get('DESK_BAKE_SAMPLES', '8'))
REPORT = OUT / 'validation_report.json'
report = {
    'success': False,
    'geometry': {},
    'uv': {},
    'drawer_motion': [],
    'fbx_roundtrip': {},
    'bakes': {},
    'baked_materials': {},
    'renders': {},
    'settings': {'color_resolution': COLOR_RES, 'data_resolution': DATA_RES,
                 'cycles_device': 'CPU', 'bake_samples': BAKE_SAMPLES,
                 'margin_pixels': 16, 'selected_to_active': False,
                 'normal_space': 'TANGENT', 'normal_green': 'POS_Y'},
}
started = time.perf_counter()


def log(message):
    print('DESK_BAKE ' + message, flush=True)


def write_report():
    report['elapsed_seconds'] = time.perf_counter() - started
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def part_object(part):
    for name in ('SM_OldWoodDesk_' + part, 'OldWoodDesk_' + part, part):
        obj = bpy.data.objects.get(name)
        if obj and obj.type == 'MESH':
            return obj
    raise AssertionError('Missing mesh object for ' + part)


def evaluated_geometry(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh(preserve_all_data_layers=True,
                             depsgraph=bpy.context.evaluated_depsgraph_get())
    try:
        mesh.calc_loop_triangles()
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            manifold = {
                'vertices': len(bm.verts), 'edges': len(bm.edges), 'faces': len(bm.faces),
                'non_manifold_edges': sum(not edge.is_manifold for edge in bm.edges),
                'loose_vertices': sum(not vertex.link_edges for vertex in bm.verts),
            }
        finally:
            bm.free()
        minimum = [min(v[axis] for v in vertices) for axis in range(3)]
        maximum = [max(v[axis] for v in vertices) for axis in range(3)]
        manifold['dimensions_m'] = [maximum[i] - minimum[i] for i in range(3)]
        manifold['bounds_min_m'] = minimum
        manifold['bounds_max_m'] = maximum
        manifold['triangles'] = len(triangles)
        return vertices, triangles, manifold
    finally:
        evaluated.to_mesh_clear()


def uv_validation(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    assert mesh.uv_layers.active, obj.name + ' has no active UV layer'
    uvs = mesh.uv_layers.active.data
    minimum = [min(item.uv[axis] for item in uvs) for axis in range(2)]
    maximum = [max(item.uv[axis] for item in uvs) for axis in range(2)]
    area = 0.
    degenerates = 0
    for triangle in mesh.loop_triangles:
        a, b, c = [uvs[index].uv for index in triangle.loops]
        triangle_area = abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) * .5
        area += triangle_area
        degenerates += triangle_area < 1.e-13
    result = {'layers': [layer.name for layer in mesh.uv_layers],
              'active': mesh.uv_layers.active.name, 'min': minimum, 'max': maximum,
              'triangle_uv_area_sum': area, 'zero_area_triangles': degenerates}
    assert all(x >= -1.e-5 for x in minimum) and all(x <= 1.00001 for x in maximum), result
    assert degenerates == 0, (obj.name, result)
    assert 0. < area <= 1.001, (obj.name, result)
    return result


def expected_hulls(source_report, mesh_name):
    value = source_report['parts'][mesh_name]['collision_hulls']
    return value if isinstance(value, int) else len(value)


def verify_roundtrip(obj, part, source_report):
    name = 'SM_OldWoodDesk_' + part
    path = OUT / (name + '.fbx')
    assert path.is_file(), str(path)
    old_objects = set(bpy.data.objects)
    old_meshes = set(bpy.data.meshes)
    old_materials = set(bpy.data.materials)
    old_actions = set(bpy.data.actions)
    old_collections = set(bpy.data.collections)
    expected_geometry = evaluated_geometry(obj)[2]
    result = {'source': str(path), 'sha256': sha256(path), 'success': False}
    report['fbx_roundtrip'][name] = result
    log('FBX roundtrip begin ' + name)
    try:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=False)
        imported = set(bpy.data.objects) - old_objects
        render_meshes = [x for x in imported if x.type == 'MESH' and not x.name.startswith('UCX_')]
        collision_meshes = [x for x in imported if x.type == 'MESH' and x.name.startswith('UCX_')]
        assert len(render_meshes) == 1, [x.name for x in render_meshes]
        assert not any(x.type in ('LIGHT', 'CAMERA') for x in imported), [x.name for x in imported]
        imported_obj = render_meshes[0]
        actual = evaluated_geometry(imported_obj)[2]
        result.update({'imported_mesh': imported_obj.name, 'geometry': actual,
                       'ucx_count': len(collision_meshes),
                       'expected_ucx_count': expected_hulls(source_report, name),
                       'uv_layers': len(imported_obj.data.uv_layers),
                       'pivot_world_m': list(imported_obj.matrix_world.translation),
                       'material_slots': [slot.material.name if slot.material else None
                                          for slot in imported_obj.material_slots]})
        assert result['ucx_count'] == result['expected_ucx_count'], result
        assert actual['non_manifold_edges'] == 0 and actual['loose_vertices'] == 0, result
        assert len(imported_obj.data.uv_layers) >= len(obj.data.uv_layers), result
        for key in ('dimensions_m', 'bounds_min_m', 'bounds_max_m'):
            assert max(abs(a - b) for a, b in zip(actual[key], expected_geometry[key])) < .00002, (key, result)
        assert imported_obj.matrix_world.translation.length < .00001, result
        source_slots = {slot.material.name for slot in obj.material_slots if slot.material}
        imported_slots = {slot.material.name.split('.')[0] for slot in imported_obj.material_slots if slot.material}
        assert source_slots == imported_slots, (source_slots, imported_slots)
        result['success'] = True
    finally:
        for imported_obj in list(set(bpy.data.objects) - old_objects):
            bpy.data.objects.remove(imported_obj, do_unlink=True)
        for collection in list(set(bpy.data.collections) - old_collections):
            bpy.data.collections.remove(collection)
        for datablocks, originals in ((bpy.data.meshes, old_meshes), (bpy.data.materials, old_materials),
                                     (bpy.data.actions, old_actions)):
            for item in list(set(datablocks) - originals):
                if item.users == 0:
                    datablocks.remove(item)
    log('FBX roundtrip passed ' + name)


def principled(material):
    assert material and material.use_nodes, 'Material must use nodes'
    return next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')


def socket_by_id(node, identifier):
    return next(socket for socket in node.inputs
                if socket.identifier == identifier or socket.name == identifier)


def new_image(part, channel, resolution):
    name = 'T_OldDesk_' + part + '_' + channel
    image = bpy.data.images.new(name, width=resolution, height=resolution,
                                alpha=False, float_buffer=False)
    image.colorspace_settings.name = 'sRGB' if channel == 'BaseColor' else 'Non-Color'
    image.file_format = 'PNG'
    image.filepath_raw = str(TEXTURES / (name + '.png'))
    return image


def bake_channel(obj, part, channel, image):
    log('Bake begin ' + part + ' ' + channel + ' ' + str(image.size[:]))
    channel_started = time.perf_counter()
    original_outputs = []
    temporary_nodes = []
    target_nodes = []
    materials = list(dict.fromkeys(slot.material for slot in obj.material_slots if slot.material))
    assert materials, obj.name
    disk_image = None
    image_name = image.name
    try:
        for material in materials:
            material.use_fake_user = True
            nodes, links = material.node_tree.nodes, material.node_tree.links
            output = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL' and node.is_active_output)
            surface = output.inputs[0]
            original_outputs.append((material, surface, [(link.from_socket, link.to_socket) for link in surface.links]))
            image_node = nodes.new('ShaderNodeTexImage')
            image_node.image = image
            image_node.label = 'Temporary bake target'
            target_nodes.append((material, image_node))
            if channel in ('BaseColor', 'Roughness'):
                source = socket_by_id(principled(material), 'Base Color' if channel == 'BaseColor' else 'Roughness')
                emission = nodes.new('ShaderNodeEmission')
                temporary_nodes.append((material, emission))
                emission.inputs[1].default_value = 1.
                if source.is_linked:
                    links.new(source.links[0].from_socket, emission.inputs[0])
                else:
                    value = source.default_value
                    if channel == 'Roughness':
                        value = (value, value, value, 1.)
                    emission.inputs[0].default_value = value
                links.new(emission.outputs[0], surface)
            # Set this last: newly created temporary shader nodes can be selected.
            for node in nodes:
                node.select = False
            image_node.select = True
            nodes.active = image_node
        bpy.ops.object.select_all(action='DESELECT')
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        result = bpy.ops.object.bake(type='NORMAL' if channel == 'Normal' else 'EMIT',
                                     margin=16, margin_type='EXTEND', use_selected_to_active=False,
                                     normal_space='TANGENT', normal_r='POS_X', normal_g='POS_Y',
                                     normal_b='POS_Z', target='IMAGE_TEXTURES', use_clear=True)
        assert result == {'FINISHED'}, result
        assert image.has_data, image.name
        image.save()
        path = Path(image.filepath_raw)
        assert path.is_file() and path.stat().st_size > 1024, str(path)
        disk_image = bpy.data.images.load(str(path), check_existing=False)
        disk_image.colorspace_settings.name = image.colorspace_settings.name
        # Changing color space may release the decoded buffer; force the lazy PNG load.
        disk_size = tuple(disk_image.size)
        _first_pixel = disk_image.pixels[0]
        assert disk_image.has_data and disk_size == tuple(image.size), (path.name, disk_size, tuple(image.size))
        samples = []
        width, height = disk_image.size
        channels = disk_image.channels
        # Pull the RNA buffer once. Repeated indexed reads can copy an entire
        # 4K image for every sampled component and make validation very slow.
        pixel_buffer = array('f', [0.]) * (width * height * channels)
        try:
            disk_image.pixels.foreach_get(pixel_buffer)
            for y in range(height // 64, height, max(1, height // 32)):
                for x in range(width // 64, width, max(1, width // 32)):
                    index = (y * width + x) * channels
                    samples.append(tuple(pixel_buffer[index + c] for c in range(3)))
        finally:
            del pixel_buffer
        mins = [min(pixel[i] for pixel in samples) for i in range(3)]
        maxes = [max(pixel[i] for pixel in samples) for i in range(3)]
        assert max(maxes) > .001, (part, channel, mins, maxes)
        report['bakes'][image_name] = {
            'path': str(path), 'resolution': list(disk_image.size),
            'colorspace': disk_image.colorspace_settings.name, 'bytes': path.stat().st_size,
            'sha256': sha256(path), 'sample_min_rgb': mins, 'sample_max_rgb': maxes,
            'elapsed_seconds': time.perf_counter() - channel_started,
            'method': 'NORMAL' if channel == 'Normal' else 'EMIT from Principled input',
            'reloaded_from_saved_png': True,
        }
        disk_image.filepath_raw = '//Textures/' + path.name
        log('Bake complete ' + part + ' ' + channel + ' seconds=' +
            str(round(time.perf_counter() - channel_started, 1)))
        write_report()
    finally:
        for material, surface, original_links in original_outputs:
            for link in list(surface.links):
                material.node_tree.links.remove(link)
            for from_socket, to_socket in original_links:
                material.node_tree.links.new(from_socket, to_socket)
        for material, node in temporary_nodes + target_nodes:
            material.node_tree.nodes.remove(node)
    assert disk_image, image_name
    if image.users == 0:
        bpy.data.images.remove(image)
    disk_image.name = image_name
    return disk_image


def make_baked_material(part, images):
    material = bpy.data.materials.new('M_OldDesk_' + part + '_Baked')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (520, 60)
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.location = (200, 80)
    socket_by_id(shader, 'Metallic').default_value = 0.
    links.new(shader.outputs[0], output.inputs[0])
    for channel, y in (('BaseColor', 260), ('Roughness', -20), ('Normal', -300)):
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = images[channel]
        texture.label = channel
        texture.location = (-650, y)
        if channel == 'Normal':
            normal = nodes.new('ShaderNodeNormalMap')
            normal.space = 'TANGENT'
            normal.uv_map = ''
            normal.location = (-170, -220)
            links.new(texture.outputs[0], normal.inputs[1])
            links.new(normal.outputs[0], socket_by_id(shader, 'Normal'))
        else:
            links.new(texture.outputs[0], socket_by_id(shader, 'Base Color' if channel == 'BaseColor' else 'Roughness'))
    report['baked_materials'][part] = {
        'material': material.name,
        'images': {channel: image.name for channel, image in images.items()},
        'emission_connected': False,
    }
    return material


try:
    assert COLOR_RES >= 512 and DATA_RES >= 512, 'Atlas resolutions must be at least 512'
    assert SOURCE.is_file(), str(SOURCE)
    TEXTURES.mkdir(exist_ok=True)
    log('Load ' + str(SOURCE))
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.context.scene
    assert scene.camera, 'Preview scene has no camera'
    objects = {part: part_object(part) for part in PARTS}
    source_report = json.loads((OUT / 'model_report.json').read_text(encoding='utf-8-sig'))
    drawer = objects['Drawer']
    closed_matrix = drawer.matrix_world.copy()

    log('Validate topology, UVs and shared origin')
    for part, obj in objects.items():
        geometry = evaluated_geometry(obj)[2]
        report['geometry'][part] = geometry
        assert geometry['non_manifold_edges'] == 0 and geometry['loose_vertices'] == 0, (part, geometry)
        assert obj.matrix_world.translation.length < .00001, (part, list(obj.matrix_world.translation))
        report['uv'][part] = uv_validation(obj)
        attributes = {}
        for attr_name in ('WoodCoord', 'WoodTone', 'Wear'):
            attribute = obj.data.attributes.get(attr_name)
            assert attribute and len(attribute.data) > 0, (part, 'Missing shader attribute', attr_name)
            attributes[attr_name] = {'domain': attribute.domain, 'data_type': attribute.data_type,
                                     'count': len(attribute.data)}
        report['geometry'][part]['shader_attributes'] = attributes
        report['geometry'][part]['source_materials'] = [slot.material.name if slot.material else None
                                                      for slot in obj.material_slots]
    base_vertices, base_triangles, _ = evaluated_geometry(objects['Base'])
    base_bvh = BVHTree.FromPolygons(base_vertices, base_triangles, all_triangles=True, epsilon=0.)
    log('Validate drawer travel at 0, 6, 12, 18 and 23 cm')
    try:
        for distance in (0., .06, .12, .18, .23):
            drawer.matrix_world = closed_matrix.copy()
            drawer.matrix_world.translation += Vector((0., -distance, 0.))
            drawer_vertices, drawer_triangles, _ = evaluated_geometry(drawer)
            drawer_bvh = BVHTree.FromPolygons(drawer_vertices, drawer_triangles,
                                             all_triangles=True, epsilon=0.)
            overlaps = base_bvh.overlap(drawer_bvh)
            sample = {'open_distance_m': distance, 'blender_offset_m': [0., -distance, 0.],
                      'overlapping_triangle_pairs': len(overlaps),
                      'first_pairs': [list(pair) for pair in overlaps[:10]]}
            report['drawer_motion'].append(sample)
            write_report()
            assert not overlaps, ('Drawer intersects base', sample)
    finally:
        drawer.matrix_world = closed_matrix
        bpy.context.view_layer.update()

    for part, obj in objects.items():
        verify_roundtrip(obj, part, source_report)
        write_report()

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = BAKE_SAMPLES
    scene.render.bake.margin = 16
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.normal_space = 'TANGENT'
    scene.render.bake.normal_r = 'POS_X'
    scene.render.bake.normal_g = 'POS_Y'
    scene.render.bake.normal_b = 'POS_Z'
    for part, obj in objects.items():
        images = {}
        for channel in ('BaseColor', 'Roughness', 'Normal'):
            resolution = COLOR_RES if channel == 'BaseColor' else DATA_RES
            image = new_image(part, channel, resolution)
            images[channel] = bake_channel(obj, part, channel, image)
        baked = make_baked_material(part, images)
        for slot in obj.material_slots:
            slot.material = baked

    log('Render baked-material closed preview')
    scene.cycles.samples = int(os.environ.get('DESK_RENDER_SAMPLES', '32'))
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(OUT / 'OldWoodDesk_Preview.png')
    bpy.ops.render.render(write_still=True)
    report['renders']['closed'] = scene.render.filepath
    log('Render baked-material drawer-open preview')
    try:
        drawer.matrix_world = closed_matrix.copy()
        drawer.matrix_world.translation += Vector((0., -.23, 0.))
        bpy.context.view_layer.update()
        scene.render.filepath = str(OUT / 'OldWoodDesk_DrawerOpen.png')
        bpy.ops.render.render(write_still=True)
        report['renders']['drawer_open'] = scene.render.filepath
    finally:
        drawer.matrix_world = closed_matrix
        bpy.context.view_layer.update()
    for name, validation in report['fbx_roundtrip'].items():
        assert sha256(OUT / (name + '.fbx')) == validation['sha256'], 'Source FBX unexpectedly changed'
    scene.render.filepath = str(OUT / 'OldWoodDesk_Preview.png')
    bpy.ops.object.select_all(action='DESELECT')
    objects['Base'].select_set(True)
    objects['Drawer'].select_set(True)
    bpy.context.view_layer.objects.active = objects['Base']
    log('Save baked scene ' + str(SOURCE))
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
