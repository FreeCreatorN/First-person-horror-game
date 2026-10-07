"""Run the individual functions through Blender MCP, preserving original source."""
from pathlib import Path
import json
import sys
import bpy
import bmesh
from mathutils import Vector

PROJECT = Path(r'D:\UE\Project\HorrorGame')
ROOT = PROJECT / 'SourceArt/OldTownScaleRevision_20261003'
BASE = PROJECT / 'SourceArt/OldTownModular_20261002/ImportManifest.json'
sys.path.insert(0, str(PROJECT / 'Scripts'))
from OldTownHumanScalePlan import transform_point


def resize_furniture():
    manifest = json.loads(BASE.read_text(encoding='utf-8'))
    result = []
    for entry in manifest['assets']:
        obj = bpy.data.objects[entry['name']]
        if not obj.get('ots_scale_revision_20261003'):
            assert all(abs(v - 1) < .001 for v in obj.scale), obj.name
            for vertex in obj.data.vertices:
                vertex.co = Vector(transform_point(entry['group'], [v * 100 for v in vertex.co])) / 100
            old_offset = entry['offset_cm']
            new_offset = transform_point(entry['group'], old_offset)
            obj.location += (Vector(new_offset) - Vector(old_offset)) / 100
            obj['ots_assembly_offset_cm'] = new_offset
            obj['ots_semantic_group'] = entry['group']
            obj['ots_scale_revision_20261003'] = True
            obj.data.update()
        result.append({'name': obj.name, 'dimensions_cm': [round(v * 100, 3) for v in obj.dimensions],
                       'offset_cm': list(obj['ots_assembly_offset_cm'])})
    bpy.context.view_layer.update()
    print(json.dumps(result))


def build_human():
    name = 'SM_OTS_HumanReference_180x50'
    if name in bpy.data.objects:
        print('Human reference already exists')
        return
    mat = bpy.data.materials.get('ScaleReferenceBlue') or bpy.data.materials.new('ScaleReferenceBlue')
    mat.use_nodes = True
    mat.diffuse_color = (.025, .22, .52, 1)
    shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = mat.diffuse_color
    shader.inputs['Roughness'].default_value = .7
    parts = []
    def ellipsoid(center, size):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=center)
        obj = bpy.context.object
        obj.scale = [v * .5 for v in size]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append(obj)
    ellipsoid((0, 0, 1.705), (.18, .21, .19))
    ellipsoid((0, 0, 1.56), (.12, .13, .18))
    ellipsoid((0, 0, 1.32), (.38, .24, .53))
    ellipsoid((0, 0, 1.01), (.31, .23, .3))
    for sign in (-1, 1):
        ellipsoid((sign * .087, 0, .68), (.16, .18, .65))
        ellipsoid((sign * .087, 0, .255), (.13, .14, .5))
        ellipsoid((sign * .087, -.05, .045), (.14, .27, .09))
        ellipsoid((sign * .208, 0, 1.19), (.085, .1, .59))
        ellipsoid((sign * .208, -.01, .865), (.08, .085, .15))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    low = [min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    high = [max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    for vertex in obj.data.vertices:
        vertex.co.x *= .5 / (high[0] - low[0])
        vertex.co.z = (vertex.co.z - low[2]) * 1.8 / (high[2] - low[2])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    obj['ots_semantic_group'] = 'Reference'
    obj['ots_assembly_offset_cm'] = (0, 0, 0)
    obj.location = (-.5, -1.75, 0)
    obj.data.update()
    print(json.dumps({'name': name, 'dimensions_cm': [round(v * 100, 3) for v in obj.dimensions]}))


def export_revision():
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(BASE.read_text(encoding='utf-8'))
    entries = list(manifest['assets']) + [{'name': 'SM_OTS_HumanReference_180x50',
        'destination': '/Game/Yastar/Meshes/hOUSE', 'group': 'Reference'}]
    output = []
    for entry in entries:
        obj = bpy.data.objects[entry['name']]
        saved = obj.location.copy()
        obj.location = (0, 0, 0)
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        bm.free()
        file = entry['name'] + '.fbx'
        bpy.ops.export_scene.fbx(filepath=str(ROOT / file), use_selection=True,
            object_types={'MESH'}, global_scale=1, apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS', use_mesh_modifiers=True,
            use_triangles=True, bake_anim=False, add_leaf_bones=False,
            axis_forward='-Y', axis_up='Z', bake_space_transform=False,
            path_mode='AUTO', use_custom_props=False)
        corners = [Vector(v) for v in obj.bound_box]
        item = dict(entry)
        item.update(file=file, dimensions_cm=[round(v * 100, 4) for v in obj.dimensions],
            offset_cm=[round(v, 4) for v in obj['ots_assembly_offset_cm']],
            bounds_cm=[[round(min(v[i] for v in corners) * 100, 4) for i in range(3)],
                       [round(max(v[i] for v in corners) * 100, 4) for i in range(3)]],
            material_slots=[m.name for m in obj.data.materials], vertices=len(obj.data.vertices),
            triangles=sum(len(p.vertices)-2 for p in obj.data.polygons),
            source='Original geometry resized through Blender MCP for 180cm human reference')
        output.append(item)
        obj.location = saved
    material = bpy.data.materials['ScaleReferenceBlue']
    manifest['materials']['ScaleReferenceBlue'] = {'color': list(material.diffuse_color[:3]), 'roughness': .7, 'metallic': 0}
    manifest.update(version=2, assets=output, reference_height_cm=180, reference_shoulder_width_cm=50)
    (ROOT / 'ImportManifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'OldTown_HumanScaleRevision.blend'))
    print(json.dumps({'manifest': str(ROOT / 'ImportManifest.json'), 'assets': len(output)}))
