"""Validate the Pen export, bake PBR atlases, and render the model.

This script opens the canonical source saved by build.py. It never rewrites the
FBXs or the model report. All helper code lives beside this script.
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

OUT = Path(__file__).resolve().parent
SOURCE = OUT / 'Pen.blend'
TEXTURES = OUT / 'Textures'
PARTS = ('SM_Pen',)
COLOR_RES = int(os.environ.get('PEN_BAKE_COLOR_RES', '2048'))
DATA_RES = int(os.environ.get('PEN_BAKE_DATA_RES', '1024'))
BAKE_SAMPLES = int(os.environ.get('PEN_BAKE_SAMPLES', '8'))
report = {'success': False, 'geometry': {}, 'uv': {}, 'fbx_roundtrip': {},
          'bakes': {}, 'baked_materials': {}, 'renders': {},
          'settings': {'color_resolution': COLOR_RES, 'data_resolution': DATA_RES,
                       'cycles_device': 'CPU', 'bake_samples': BAKE_SAMPLES,
                       'channels': ['BaseColor', 'Roughness', 'Normal', 'Metallic'],
                       'margin_pixels': 16, 'selected_to_active': False,
                       'normal_space': 'TANGENT', 'normal_green': 'POS_Y'}}
started = time.perf_counter()


def log(message):
    print('PEN_BAKE ' + message, flush=True)


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
    path = OUT / 'validation_helpers.py'
    parsed = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    required = {'geometry_info', 'uv_info', 'verify_roundtrip'}
    definitions = [node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in required]
    assert {node.name for node in definitions} == required, 'Missing Pen validation helpers'
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), 'exec'), globals())
    path = OUT / 'bake_functions.py'
    exec(compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec'), globals())


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


def camera_pose(scene, center, offset, ortho_scale):
    camera = scene.camera
    center = Vector(center)
    camera.location = center + Vector(offset)
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.shift_x = camera.data.shift_y = 0.
    camera.data.ortho_scale = ortho_scale
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
    display = bpy.data.collections.get('Pen - display assembly')
    source_collection = bpy.data.collections.get('SOURCE - individual components')
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
        # Generated/Object coordinates are intentionally baked into each UV atlas.
        # Nib, barrel, clip, and click-button are intentionally connected components.
        try:
            verify_roundtrip(obj, source_report)
        finally:
            roundtrips[MESH_NAME] = report['fbx_roundtrip']
            report['fbx_roundtrip'] = dict(roundtrips)
        write_report()
    report['assembly_contact'] = {
        'cross_object_zero_overlap_required': False,
        'reason': 'Single joined mesh; nib, barrel, clip, and click-button meet intentionally.',
    }
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
                  for channel in ('BaseColor', 'Roughness', 'Normal', 'Metallic')}
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
    scene.cycles.samples = int(os.environ.get('PEN_RENDER_SAMPLES', '32'))
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    camera = scene.camera
    camera_state = {'matrix': camera.matrix_world.copy(), 'type': camera.data.type,
                    'lens': camera.data.lens, 'ortho_scale': camera.data.ortho_scale,
                    'shift_x': camera.data.shift_x, 'shift_y': camera.data.shift_y}
    record_render(scene, 'Pen_Preview.png', PARTS)
    # Keep the authored front-facing azimuth so the clip remains visible.
    authored_direction = Vector((camera.location.x, camera.location.y, 0.))
    if authored_direction.length < .001:
        authored_direction = Vector((.25, -1., 0.))
    authored_direction.normalize()
    detail_offset = authored_direction * .16 + Vector((0., 0., .028))
    camera_pose(scene, (0., 0., .112), detail_offset, .068)
    record_render(scene, 'Pen_Detail.png', PARTS)
    camera_pose(scene, (0., 0., .012), detail_offset, .038)
    record_render(scene, 'Pen_TipDetail.png', PARTS)

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
    scene.render.filepath = str(OUT / 'Pen_Preview.png')
    bpy.ops.object.select_all(action='DESELECT')
    for view in views.values():
        view.select_set(True)
    bpy.context.view_layer.objects.active = views['SM_Pen']
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
