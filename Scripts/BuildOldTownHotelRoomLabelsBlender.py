"""Generate the 24 hotel room numbers in an isolated background Blender process."""
import bpy
import bmesh
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from mathutils import Vector


ROOT = Path('D:/UE/Project/HorrorGame')
OUT = ROOT / 'SourceArt/OldTownHotelPolish_20261005'
BLEND = OUT / 'OldTownHotelRoomNumbers.blend'
MANIFEST = OUT / 'ImportManifest.json'
REPORT = OUT / 'RoomNumberVerification.json'
ROOM_IDS = [str(floor * 100 + room) for floor in (2, 3, 4) for room in range(1, 9)]
PREFIX = 'SM_OTS_HotelRoomNumber_'
COLLECTION = 'OldTownHotelRoomNumbers_20261005'
HEIGHT_M = .12
DEPTH_M = .0025
EXPORT_SETTINGS = dict(
    use_selection=True,
    global_scale=1,
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_UNITS',
    use_mesh_modifiers=True,
    use_triangles=True,
    bake_anim=False,
    axis_forward='-Y',
    axis_up='Z',
    bake_space_transform=False,
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds_cm(obj):
    # The mesh is authoritative; Blender's dimensions can lag after conversion.
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    assert points, f'{obj.name}: empty mesh'
    low = [min(point[axis] for point in points) * 100 for axis in range(3)]
    high = [max(point[axis] for point in points) * 100 for axis in range(3)]
    return [low, high], [high[axis] - low[axis] for axis in range(3)]


def validate(obj, room_id, check_properties=True):
    assert obj.name == PREFIX + room_id, (obj.name, room_id)
    assert obj.type == 'MESH', obj.type
    if check_properties:
        assert obj.get('room_id') == room_id, obj.get('room_id')
        assert obj.get('source_text') == room_id, obj.get('source_text')
        assert obj.get('source_font') == 'Bfont', obj.get('source_font')
    bounds, dimensions = bounds_cm(obj)
    assert 0 < dimensions[0] <= 32, (obj.name, dimensions)
    assert abs(dimensions[1] - .25) <= .0001, (obj.name, dimensions)
    assert abs(dimensions[2] - 12) <= .0001, (obj.name, dimensions)
    assert abs(bounds[0][0] + bounds[1][0]) <= .0001, (obj.name, bounds)
    assert abs(bounds[0][1] + bounds[1][1]) <= .0001, (obj.name, bounds)
    assert abs(bounds[0][2]) <= .0001, (obj.name, bounds)
    assert all(abs(value) < .000001 for value in obj.location), tuple(obj.location)
    assert all(abs(value) < .000001 for value in obj.rotation_euler), tuple(obj.rotation_euler)
    assert all(abs(value - 1) < .000001 for value in obj.scale), tuple(obj.scale)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    nonmanifold = sum(not edge.is_manifold for edge in bm.edges)
    bm.free()
    assert nonmanifold == 0, (obj.name, nonmanifold)
    # The outward text face remains -Y in Blender and becomes +Y in UE.
    front_faces = sum(poly.normal.y < -.99 for poly in obj.data.polygons)
    back_faces = sum(poly.normal.y > .99 for poly in obj.data.polygons)
    assert front_faces > 0 and back_faces > 0, (obj.name, front_faces, back_faces)
    return {
        'room_id': room_id,
        'name': obj.name,
        'bounds_cm': bounds,
        'dimensions_cm': dimensions,
        'vertices': len(obj.data.vertices),
        'faces': len(obj.data.polygons),
        'polygons': len(obj.data.polygons),
        'nonmanifold_edges': nonmanifold,
        'front_axis_blender': '-Y',
        'front_axis_unreal': '+Y',
        'pivot': 'bottom_center',
        'source_text': room_id,
        'source_font': 'Bfont',
    }


def select_only(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def build_number(room_id, collection, material):
    name = PREFIX + room_id
    text = bpy.data.curves.new(name + '_Text', 'FONT')
    text.body = room_id
    # Blender 5.2 names its bundled default font "Bfont Regular".
    assert text.font.name.startswith('Bfont'), text.font.name
    font_display_name = text.font.name
    text.align_x = 'CENTER'
    text.resolution_u = 3
    text.extrude = DEPTH_M / 2
    text.bevel_depth = 0
    obj = bpy.data.objects.new(name, text)
    collection.objects.link(obj)
    obj.rotation_euler = (math.pi / 2, 0, 0)
    select_only(obj)
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    low = [min(vertex.co[axis] for vertex in obj.data.vertices) for axis in range(3)]
    high = [max(vertex.co[axis] for vertex in obj.data.vertices) for axis in range(3)]
    height_scale = HEIGHT_M / (high[2] - low[2])
    depth_scale = DEPTH_M / (high[1] - low[1])
    offset = Vector(((low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]))
    for vertex in obj.data.vertices:
        point = vertex.co - offset
        vertex.co = (point.x * height_scale, point.y * depth_scale, point.z * height_scale)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.0000001)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.name = name + '_Mesh'
    obj.data.materials.append(material)
    obj['room_id'] = room_id
    obj['source_text'] = room_id
    obj['source_font'] = 'Bfont'
    obj['source_font_display_name'] = font_display_name
    obj['pivot'] = 'bottom_center'
    obj['front_axis_blender'] = '-Y'
    obj.data.update()
    bpy.context.view_layer.update()
    validate(obj, room_id)
    return obj


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    # This script is only launched in our disposable background process.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    scene.unit_settings.length_unit = 'CENTIMETERS'
    collection = bpy.data.collections.new(COLLECTION)
    scene.collection.children.link(collection)
    material = bpy.data.materials.new('M_OTS_HotelRoomNumber_Brass')
    material.diffuse_color = (.42, .31, .14, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (.42, .31, .14, 1)
    bsdf.inputs['Metallic'].default_value = .7
    bsdf.inputs['Roughness'].default_value = .52
    assets = []
    for room_id in ROOM_IDS:
        obj = build_number(room_id, collection, material)
        entry = validate(obj, room_id)
        fbx = OUT / (obj.name + '.fbx')
        select_only(obj)
        bpy.ops.export_scene.fbx(filepath=str(fbx), **EXPORT_SETTINGS)
        entry.update(file=fbx.name, sha256=sha256(fbx))
        assets.append(entry)
    assert len(bpy.data.objects) == 24, len(bpy.data.objects)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    manifest = {
        'units': 'centimeters',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_blend': BLEND.name,
        'source_blend_sha256': sha256(BLEND),
        'source_font': 'Bfont',
        'source_axis': {'X': 'horizontal', 'Y': 'depth', 'Z': 'vertical'},
        'unreal_axis_mapping': {'X': '+X', 'Y': '-Y', 'Z': '+Z'},
        'unreal_front_axis': '+Y',
        'fbx_export_settings': EXPORT_SETTINGS,
        'assets': assets,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('HOTEL_ROOM_NUMBERS_BUILD_PASS ' + json.dumps({
        'assets': len(assets),
        'width_cm_min': min(asset['dimensions_cm'][0] for asset in assets),
        'width_cm_max': max(asset['dimensions_cm'][0] for asset in assets),
        'height_cm': 12,
        'depth_cm': .25,
    }), flush=True)


def verify():
    assert Path(bpy.data.filepath).resolve() == BLEND.resolve(), bpy.data.filepath
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert sha256(BLEND) == manifest['source_blend_sha256'], 'Source blend changed'
    assert manifest['units'] == 'centimeters'
    assert [asset['room_id'] for asset in manifest['assets']] == ROOM_IDS
    assert sorted(obj.name for obj in bpy.data.objects) == sorted(PREFIX + room for room in ROOM_IDS)
    source = []
    for entry in manifest['assets']:
        obj = bpy.data.objects[entry['name']]
        result = validate(obj, entry['room_id'])
        for field in ('name', 'source_text', 'source_font', 'vertices', 'faces', 'bounds_cm'):
            assert result[field] == entry[field], (entry['name'], field)
        source.append(result)

    # Reimport every delivery FBX in this separate disposable process, exercising
    # the actual saved artifact's unit and axis transforms rather than cached data.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    imported = []
    for entry in manifest['assets']:
        fbx = OUT / entry['file']
        assert sha256(fbx) == entry['sha256'], entry['file']
        bpy.ops.import_scene.fbx(filepath=str(fbx), use_custom_props=True)
        objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        assert len(objects) == 1, (entry['file'], len(objects))
        obj = objects[0]
        result = validate(obj, entry['room_id'], check_properties=False)
        for axis in range(3):
            assert abs(result['dimensions_cm'][axis] - entry['dimensions_cm'][axis]) <= .0001
            for side in range(2):
                assert abs(result['bounds_cm'][side][axis] - entry['bounds_cm'][side][axis]) <= .0001
        assert result['faces'] == entry['faces'], (entry['name'], result['faces'], entry['faces'])
        imported.append(result)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.ops.object.delete(use_global=False)
    report = {
        'passed': True,
        'verified_utc': datetime.now(timezone.utc).isoformat(),
        'room_ids': ROOM_IDS,
        'source_objects_reloaded': len(source),
        'fbx_files_reimported': len(imported),
        'fbx_sha256_verified': True,
        'source_blend_sha256_verified': True,
        'all_text_names_verified': True,
        'all_pivots_bottom_center': True,
        'source': source,
        'reimported_fbx': imported,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('HOTEL_ROOM_NUMBERS_RELOAD_VERIFY_PASS ' + json.dumps({
        'assets': len(imported),
        'height_cm': 12,
        'depth_cm': .25,
        'width_cm_max': max(asset['dimensions_cm'][0] for asset in imported),
        'all_nonmanifold_edges': 0,
    }), flush=True)


if __name__ == '__main__':
    verify() if '--verify-only' in sys.argv else build()
