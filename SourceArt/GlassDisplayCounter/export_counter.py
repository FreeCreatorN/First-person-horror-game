"""Export the case and two local-origin door leaves with baked opaque paint."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parent
output = root / 'Exports'
output.mkdir(exist_ok=True)
source = root / 'GlassDisplayCounter.blend'
model = json.loads((root / 'model_report.json').read_text(encoding='utf-8'))
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
size = 2048


def select(objects, active):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active


def join_evaluated(objects, name):
    deps = bpy.context.evaluated_depsgraph_get()
    copies = []
    for obj in objects:
        evaluated = obj.evaluated_get(deps)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=deps)
        other = bpy.data.objects.new(f'Export · {obj.name}', mesh)
        bpy.context.scene.collection.objects.link(other)
        other.matrix_world = obj.matrix_world
        copies.append(other)
    bpy.context.view_layer.update()
    select(copies, copies[0])
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = name
    result.data.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    modifier = result.modifiers.new('Fixed export triangulation', 'TRIANGULATE')
    modifier.keep_custom_normals = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    result.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.06, island_margin=.0035, area_weight=.35, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert all(-.0001 <= value <= 1.0001 for uv in result.data.uv_layers.active.uv for value in uv.vector)
    return result


def assign_socket(tree, source_socket, target):
    if source_socket.links:
        tree.links.new(source_socket.links[0].from_socket, target)
    else:
        target.default_value = source_socket.default_value


def bake(obj, filename, orm):
    image = bpy.data.images.new(filename, width=size, height=size, alpha=False)
    image.colorspace_settings.name = 'Non-Color' if orm else 'sRGB'
    for material in obj.data.materials:
        tree = material.node_tree
        shader = next(n for n in tree.nodes if n.type=='BSDF_PRINCIPLED')
        surface = next(n for n in tree.nodes if n.type=='OUTPUT_MATERIAL').inputs['Surface']
        emit = tree.nodes.new('ShaderNodeEmission')
        if orm:
            rgb = tree.nodes.new('ShaderNodeCombineColor')
            rgb.inputs['Red'].default_value=1.
            assign_socket(tree, shader.inputs['Roughness'], rgb.inputs['Green'])
            assign_socket(tree, shader.inputs['Metallic'], rgb.inputs['Blue'])
            tree.links.new(rgb.outputs['Color'], emit.inputs[0])
        else:
            assign_socket(tree, shader.inputs['Base Color'], emit.inputs[0])
        tree.links.new(emit.outputs[0], surface)
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        tree.nodes.active = node
    assert bpy.ops.object.bake(type='EMIT', margin=4, margin_type='EXTEND', use_clear=True) == {'FINISHED'}
    image.filepath_raw = str(output / filename)
    image.file_format = 'PNG'
    image.save()
    assert (output / filename).stat().st_size > 4096


def ucx(name, center, half):
    vertices = [tuple(center[i] + s[i]*half[i] for i in range(3)) for s in
                ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    faces = [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def part_export(name, collection_name, texture_tag, pivot, collision_override=None):
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    scene.frame_set(1)
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    original = sorted((o for o in bpy.data.collections[collection_name].all_objects if o.type=='MESH'),key=lambda o:o.name)
    collision = collision_override or [(tuple(o['collision_center_m']),tuple(o['collision_half_m']))
                                        for o in original if 'collision_center_m' in o]
    obj = join_evaluated(original, name)
    for other in list(scene.objects):
        if other != obj:
            bpy.data.objects.remove(other, do_unlink=True)
    triangles = len(obj.data.polygons)
    indices = [i for i,mat in enumerate(obj.data.materials) if 'glass' in mat.name.casefold()]
    assert len(indices)==1
    # Preserve the opaque wear bake at the cabinet's assembled world positions.
    base = f'T_GlassDisplayCounter{texture_tag}_BaseColor.png'
    orm = f'T_GlassDisplayCounter{texture_tag}_ORM.png'
    bake(obj, base, False)
    bake(obj, orm, True)
    slots = ['M_Counter_Baked','M_Counter_Glass']
    new_indices = [int(f.material_index in indices) for f in obj.data.polygons]
    obj.data.materials.clear()
    for slot in slots:
        obj.data.materials.append(bpy.data.materials.new(slot))
    for face,index in zip(obj.data.polygons,new_indices):
        face.material_index = index
    shift=Vector(pivot)
    for vertex in obj.data.vertices:
        vertex.co -= shift
    obj.data.update()
    bounds_min = [min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    bounds_max = [max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    hulls = [ucx(f'UCX_{name}_{i:03d}', Vector(center)-shift, half) for i,(center,half) in enumerate(collision,1)]
    assert hulls and triangles > 40 and set(new_indices)=={0,1}
    select([obj,*hulls], obj)
    filename = name + '.fbx'
    bpy.ops.export_scene.fbx(filepath=str(output/filename), object_types={'MESH'}, use_selection=True,
        global_scale=1, apply_unit_scale=True, axis_forward='-Z', axis_up='Y', use_mesh_modifiers=False,
        bake_anim=False, mesh_smooth_type='FACE', path_mode='STRIP')
    print('COUNTER_FBX_VERIFIED',name,triangles,len(hulls),flush=True)
    return dict(name=name,fbx=filename,base_color=base,orm=orm,triangles=triangles,
                bounds_min_m=bounds_min,bounds_max_m=bounds_max,collision_hulls=len(hulls),slots=slots)


def verify_motion():
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    left=bpy.data.objects['Left door · local X translation']
    right=bpy.data.objects['Right door · local X translation']
    names=[left,right]
    for frame, active, change in ((1,None,0),(31,left,.922),(92,right,-.922),(132,None,0)):
        scene.frame_set(frame)
        for pivot,side in zip(names,('left','right')):
            expected = model['doors'][side]['pivot_m'][0] + (change if pivot==active else 0)
            assert abs(pivot.location.x-expected) < .000005
        bounds=[[(min((child.matrix_world@Vector(vertex))[axis] for child in pivot.children for vertex in child.bound_box),
                   max((child.matrix_world@Vector(vertex))[axis] for child in pivot.children for vertex in child.bound_box)) for axis in range(3)] for pivot in names]
        assert bounds[0][1][1] + .005 <= bounds[1][1][0], (frame, bounds)
        assert all(-.956<limits[0][0] and limits[0][1]<.956 for limits in bounds), (frame,bounds)
    print('COUNTER_DOOR_TRANSFORM_AND_TRACK_CLEARANCE_VERIFIED',flush=True)


def previews():
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene=bpy.context.scene
    scene.cycles.samples=21
    for filename, camera, frame in [('Glass_Display_Counter.png','01 Customer view',1),
                                    ('Glass_Display_Counter_Rear_Open.png','02 Staff side · open',31)]:
        scene.camera=bpy.data.objects[camera]
        scene.frame_set(frame)
        scene.render.filepath=str(root/filename)
        bpy.ops.render.render(write_still=True)


if '--render' in sys.argv:
    verify_motion()
    previews()
else:
    verify_motion()
    assets = [part_export('SM_GlassDisplayCounter',model['body_collection'],'',(0,0,0))]
    for side,collection,tag in [('left','02 Left sliding glass door','_DoorLeft'),('right','03 Right sliding glass door','_DoorRight')]:
        door=model['doors'][side]
        pivot=door['pivot_m']
        half=door['mesh_collision_extent_m']
        collision=[([pivot[0],pivot[1],pivot[2]+half[2]],half)]
        assets.append(part_export(door['mesh'],collection,tag,pivot,collision))
    hashes={row[key]:hashlib.sha256((output/row[key]).read_bytes()).hexdigest() for row in assets for key in ('fbx','base_color','orm')}
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    report=dict(success=True,baked_resolution=size,assets=assets,sha256=hashes,doors=model['doors'],source_sha256=source_hash)
    (output/'export_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
