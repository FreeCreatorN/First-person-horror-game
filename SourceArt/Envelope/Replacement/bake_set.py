"""Validate, bake, and render three independent replacement envelope assets.

Run only after build.py has finished. Original FBXs and model_report.json stay
unchanged. Final previews use PNG files reloaded from disk, not procedural maps.
"""
import ast
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
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'EnvelopeSet.blend'
TEXTURES = OUT / 'Textures'
PARTS = ('SM_Envelope_Closed', 'SM_Envelope_Open', 'SM_LetterPaper')
COLOR_RES = int(os.environ.get('ENVELOPE_BAKE_COLOR_RES', '2048'))
DATA_RES = int(os.environ.get('ENVELOPE_BAKE_DATA_RES', '1024'))
BAKE_SAMPLES = int(os.environ.get('ENVELOPE_BAKE_SAMPLES', '8'))
report = {'success': False, 'geometry': {}, 'uv': {}, 'fbx_roundtrip': {},
          'bakes': {}, 'baked_materials': {}, 'renders': {},
          'settings': {'color_resolution': COLOR_RES, 'data_resolution': DATA_RES,
                       'cycles_device': 'CPU', 'bake_samples': BAKE_SAMPLES,
                       'margin_pixels': 16, 'selected_to_active': False,
                       'normal_space': 'TANGENT', 'normal_green': 'POS_Y'}}
started = time.perf_counter()


def log(message):
    print('ENVELOPE_SET_BAKE ' + message, flush=True)


def write_report():
    report['elapsed_seconds'] = time.perf_counter() - started
    (OUT / 'validation_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_helpers():
    # Load definitions only; executing the old script would open the old model.
    path = OUT / 'validation_helpers.py'
    parsed = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    required = {'geometry_info', 'uv_info', 'verify_roundtrip'}
    definitions = [node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in required]
    assert {node.name for node in definitions} == required, 'Missing tested Envelope validation helpers'
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), 'exec'), globals())
    path = OUT / 'bake_functions.py'
    exec(compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec'), globals())


def pocket_tree(obj, offset):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
    try:
        mesh.calc_loop_triangles()
        vertices = [evaluated.matrix_world @ vertex.co + offset for vertex in mesh.vertices]
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        return BVHTree.FromPolygons(vertices, triangles, all_triangles=True, epsilon=0.)
    finally:
        evaluated.to_mesh_clear()


def preview_pose(canonical, display, source_collection, studio):
    canonical.hide_viewport = True
    canonical.hide_render = True
    source_collection.hide_viewport = True
    source_collection.hide_render = True
    display.hide_viewport = False
    display.hide_render = False
    studio.hide_render = False
    studio.hide_viewport = True
    bpy.context.view_layer.update()


def record_render(scene, filename, visible_parts):
    path = OUT / filename
    scene.render.filepath = str(path)
    log('Render begin ' + filename)
    render_started = time.perf_counter()
    result = bpy.ops.render.render(write_still=True)
    assert result == {'FINISHED'} and path.is_file() and path.stat().st_size > 1024, (filename, result)
    report['renders'][filename] = {
        'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha256(path),
        'resolution': [scene.render.resolution_x, scene.render.resolution_y],
        'resolution_percentage': scene.render.resolution_percentage,
        'engine': scene.render.engine, 'samples': scene.cycles.samples,
        'visible_assets': list(visible_parts), 'materials_from_saved_pngs': True,
        'elapsed_seconds': time.perf_counter() - render_started,
    }
    write_report()
    log('Render complete ' + filename)


def frame_detail(scene, objects, offset):
    geometries = [geometry_info(obj) for obj in objects]
    lower = Vector(tuple(min(item['bounds_min_m'][i] for item in geometries) for i in range(3)))
    upper = Vector(tuple(max(item['bounds_max_m'][i] for item in geometries) for i in range(3)))
    center = (lower + upper) * .5
    camera = scene.camera
    camera.location = center + Vector(offset)
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.shift_x = 0.
    camera.data.shift_y = 0.
    right = camera.rotation_euler.to_quaternion() @ Vector((1., 0., 0.))
    up = camera.rotation_euler.to_quaternion() @ Vector((0., 1., 0.))
    corners = [Vector((x, y, z)) for x in (lower.x, upper.x)
               for y in (lower.y, upper.y) for z in (lower.z, upper.z)]
    x_values, y_values = [point.dot(right) for point in corners], [point.dot(up) for point in corners]
    aspect = (scene.render.resolution_x * scene.render.pixel_aspect_x) / (scene.render.resolution_y * scene.render.pixel_aspect_y)
    camera.data.ortho_scale = max(max(x_values) - min(x_values),
                                 (max(y_values) - min(y_values)) * aspect) * 1.20
    bpy.context.view_layer.update()


canonical = display = source_collection = studio = None
camera_state = None
try:
    assert COLOR_RES >= 512 and DATA_RES >= 512
    assert SOURCE.is_file(), str(SOURCE)
    load_helpers()
    TEXTURES.mkdir(exist_ok=True)
    log('Load ' + str(SOURCE))
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.context.scene
    assert scene.camera, 'Scene has no preview camera'
    source_report = json.loads((OUT / 'model_report.json').read_text(encoding='utf-8-sig'))
    model_hash = sha256(OUT / 'model_report.json')
    assert set(source_report['parts']) == set(PARTS), list(source_report['parts'])
    canonical = bpy.data.collections.get('UE meshes - canonical origins')
    display = bpy.data.collections.get('Envelope set - display assembly')
    source_collection = bpy.data.collections.get('SOURCE - individual paper folds')
    studio = bpy.data.collections.get('Preview studio - excluded from exports')
    assert all((canonical, display, source_collection, studio)), 'Missing canonical/display/source/studio collection'
    canonical.hide_viewport = False
    canonical.hide_render = False
    display.hide_viewport = True
    display.hide_render = True
    source_collection.hide_viewport = True
    source_collection.hide_render = True
    bpy.context.view_layer.update()
    objects = {name: bpy.data.objects.get(name) for name in PARTS}
    views = {name: bpy.data.objects.get('VIEW_' + name.removeprefix('SM_')) for name in PARTS}
    assert all(obj and obj.type == 'MESH' for obj in objects.values()), 'Canonical objects missing'
    assert all(obj and obj.type == 'MESH' for obj in views.values()), 'Display objects missing'
    for name in PARTS:
        assert objects[name].data == views[name].data, 'Display mesh is not linked to canonical: ' + name
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = BAKE_SAMPLES
    scene.render.bake.margin = 16
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.normal_space = 'TANGENT'
    scene.render.bake.normal_r, scene.render.bake.normal_g, scene.render.bake.normal_b = 'POS_X', 'POS_Y', 'POS_Z'

    roundtrips = {}
    for MESH_NAME in PARTS:
        obj = objects[MESH_NAME]
        spec = source_report['parts'][MESH_NAME]
        FBX = OUT / spec['filename']
        log('Validate ' + MESH_NAME)
        geometry = geometry_info(obj)
        report['geometry'][MESH_NAME] = geometry
        assert geometry['non_manifold_edges'] == 0 and geometry['loose_vertices'] == 0, (MESH_NAME, geometry)
        assert obj.matrix_world.translation.length < .00001, (MESH_NAME, list(obj.matrix_world.translation))
        dimensions_cm = [value * 100. for value in geometry['dimensions_m']]
        assert max(abs(a - b) for a, b in zip(dimensions_cm, spec['dimensions_cm'])) <= .05, (MESH_NAME, dimensions_cm)
        report['uv'][MESH_NAME] = uv_info(obj)
        geometry['source_materials'] = [slot.material.name if slot.material else None for slot in obj.material_slots]
        assert set(geometry['source_materials']) == set(spec['material_slots']), (MESH_NAME, geometry['source_materials'])
        attributes = {}
        for attribute_name in ('PaperCoord', 'PaperTone', 'Wear'):
            attribute = obj.data.attributes.get(attribute_name)
            assert attribute and len(attribute.data) > 0, (MESH_NAME, attribute_name)
            attributes[attribute_name] = {'domain': attribute.domain, 'data_type': attribute.data_type,
                                          'count': len(attribute.data)}
        geometry['shader_attributes'] = attributes
        # The tested helper temporarily uses this key for its current result.
        try:
            verify_roundtrip(obj, source_report)
        finally:
            roundtrips[MESH_NAME] = report['fbx_roundtrip']
            report['fbx_roundtrip'] = dict(roundtrips)
        write_report()

    paper_offset = Vector(source_report['assembly']['paper_in_open_envelope_offset_blender_m'])
    pocket_overlaps = pocket_tree(objects['SM_Envelope_Open'], Vector((0., 0., 0.))).overlap(
        pocket_tree(objects['SM_LetterPaper'], paper_offset))
    report['paper_insertion'] = {
        'paper_offset_blender_m': list(paper_offset),
        'overlapping_triangle_pairs': len(pocket_overlaps),
        'first_pairs': [list(pair) for pair in pocket_overlaps[:10]],
    }
    assert not pocket_overlaps, report['paper_insertion']
    write_report()

    for MESH_NAME in PARTS:
        obj = objects[MESH_NAME]
        target_materials = set(source_report['parts'][MESH_NAME]['material_slots'].values())
        assert len(target_materials) == 1, (MESH_NAME, target_materials)
        material_name = next(iter(target_materials))
        set_name = source_report['materials'][material_name]['texture_set']
        texture_prefix = source_report['texture_sets'][set_name]['prefix']
        log('Bake asset ' + MESH_NAME + ' using ' + texture_prefix)
        images = {channel: bake_channel(obj, channel, COLOR_RES if channel == 'BaseColor' else DATA_RES)
                  for channel in ('BaseColor', 'Roughness', 'Normal')}
        material = baked_material(images)
        report['baked_materials'][MESH_NAME] = report.pop('baked_material')
        for slot in obj.material_slots:
            slot.material = material
        assert all(slot.material == material for slot in views[MESH_NAME].material_slots), MESH_NAME
        write_report()

    bpy.ops.object.select_all(action='DESELECT')
    preview_pose(canonical, display, source_collection, studio)
    for view in views.values():
        view.hide_render = False
        view.hide_set(False)
    report['display_materials'] = {name: [slot.material.name for slot in view.material_slots]
                                   for name, view in views.items()}
    scene.cycles.samples = int(os.environ.get('ENVELOPE_RENDER_SAMPLES', '40'))
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_percentage = 100
    camera = scene.camera
    camera_state = {'matrix': camera.matrix_world.copy(), 'type': camera.data.type,
                    'lens': camera.data.lens, 'ortho_scale': camera.data.ortho_scale,
                    'shift_x': camera.data.shift_x, 'shift_y': camera.data.shift_y}
    record_render(scene, 'EnvelopeSet_Preview.png', PARTS)

    views['SM_Envelope_Closed'].hide_render = True
    frame_detail(scene, [views['SM_Envelope_Open'], views['SM_LetterPaper']], (.13, -.27, .40))
    record_render(scene, 'EnvelopeOpen_Preview.png', ('SM_Envelope_Open', 'SM_LetterPaper'))
    views['SM_Envelope_Closed'].hide_render = False
    views['SM_Envelope_Open'].hide_render = True
    views['SM_LetterPaper'].hide_render = True
    frame_detail(scene, [views['SM_Envelope_Closed']], (.07, -.18, .32))
    record_render(scene, 'EnvelopeClosed_Preview.png', ('SM_Envelope_Closed',))

    for name, result in roundtrips.items():
        assert result['success'] and sha256(OUT / source_report['parts'][name]['filename']) == result['sha256'], name
    assert sha256(OUT / 'model_report.json') == model_hash, 'Model report unexpectedly modified'
    for view in views.values():
        view.hide_render = False
    camera.matrix_world = camera_state['matrix']
    for property_name in ('type', 'lens', 'ortho_scale', 'shift_x', 'shift_y'):
        setattr(camera.data, property_name, camera_state[property_name])
    camera_state = None
    preview_pose(canonical, display, source_collection, studio)
    scene.render.filepath = str(OUT / 'EnvelopeSet_Preview.png')
    bpy.ops.object.select_all(action='DESELECT')
    for view in views.values():
        view.select_set(True)
    bpy.context.view_layer.objects.active = views['SM_Envelope_Open']
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE))
    report['blend_file'] = str(SOURCE)
    report['final_visibility'] = {'canonical_hidden': canonical.hide_render and canonical.hide_viewport,
                                  'display_visible': not display.hide_render and not display.hide_viewport,
                                  'source_hidden': source_collection.hide_render and source_collection.hide_viewport}
    assert all(report['final_visibility'].values())
    report['success'] = True
    write_report()
    log('SUCCESS seconds=' + str(round(report['elapsed_seconds'], 1)))
except Exception:
    report['error'] = traceback.format_exc()
    write_report()
    log('FAILED ' + report['error'])
    raise
finally:
    # Restore a useful viewport even when the caller catches a validation error.
    if all((canonical, display, source_collection, studio)):
        for name in PARTS:
            view = bpy.data.objects.get('VIEW_' + name.removeprefix('SM_'))
            if view:
                view.hide_render = False
        if camera_state is not None and bpy.context.scene.camera:
            camera = bpy.context.scene.camera
            camera.matrix_world = camera_state['matrix']
            for property_name in ('type', 'lens', 'ortho_scale', 'shift_x', 'shift_y'):
                setattr(camera.data, property_name, camera_state[property_name])
        preview_pose(canonical, display, source_collection, studio)
