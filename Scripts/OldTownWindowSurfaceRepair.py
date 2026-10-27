"""UE window render repairs preserving original frame and pane physics.

Import and call apply_window(actor, placed_row) inside the parent's UE mutation.
Returns (updated_placed_row, report). The module has no executable main function.
Engine/Yastar assets and Blueprint classes are read-only. Corrected frame render
vertices live in independent CodexGenerated Cube duplicates; their original
simple collision and the actor/component transforms remain exactly unchanged.
"""
from collections import Counter
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path

import unreal

from AnalyzeOldTownWindowPlaqueSurfaces import separated_window_components

CUBE = '/Engine/BasicShapes/Cube.Cube'
ASSET_ROOT = '/Game/CodexGenerated/OldTown/Meshes/SurfaceSeparation_20261009'
RECIPE_VERSION = 'WindowFrameRenderOnlyV3'
_CACHE = {}


def _xyz(v):
    return [float(v.x),float(v.y),float(v.z)]


def _rot(v):
    return [float(v.pitch),float(v.yaw),float(v.roll)]


def _pose(component):
    return dict(location=_xyz(component.get_editor_property('relative_location')),
                rotation=_rot(component.get_editor_property('relative_rotation')),
                scale=_xyz(component.get_editor_property('relative_scale3d')),
                world_location=_xyz(component.get_world_location()),
                world_rotation=_rot(component.get_world_rotation()),
                world_scale=_xyz(component.get_world_scale()),
                collision=str(component.get_collision_enabled()),
                collision_profile=str(component.get_collision_profile_name()))


def _materials(component):
    return [component.get_material(i).get_path_name() if component.get_material(i) else None
            for i in range(component.get_num_materials())]


def _pane_differences(before,after):
    """Only roundoff may pass; physics labels/assets/materials remain exact."""
    differences = []
    if set(before) != set(after):
        return [dict(path='component_names',before=sorted(before),after=sorted(after),within_roundoff=False)]
    tolerances = dict(location=1e-6,rotation=1e-6,scale=1e-8,
                      world_location=1e-6,world_rotation=1e-6,world_scale=1e-8)
    for name in before:
        a,b = before[name],after[name]
        for key in ('mesh','materials'):
            if a[key] != b[key]:
                differences.append(dict(path=name+'.'+key,before=a[key],after=b[key],within_roundoff=False))
        for key,old in a['pose'].items():
            new = b['pose'][key]
            if old == new:
                continue
            if key in tolerances:
                maximum = max(abs(x-y) for x,y in zip(old,new))
                close = maximum <= tolerances[key]
            else:
                maximum,close = None,False
            differences.append(dict(path=name+'.pose.'+key,before=old,after=new,
                                    maximum_absolute_delta=maximum,tolerance=tolerances.get(key),within_roundoff=close))
    return differences


def simple_collision_signature(mesh):
    """Readable source Cube simple boxes plus flags; reject incomplete geometry."""
    body = mesh.get_editor_property('body_setup')
    assert body is not None, mesh.get_path_name()+' has no BodySetup'
    trace = str(body.get_editor_property('collision_trace_flag'))
    assert 'USE_COMPLEX_AS_SIMPLE' not in trace.upper(), 'Render repair requires simple frame collision.'
    geometry = body.get_editor_property('agg_geom')
    boxes = []
    for e in geometry.get_editor_property('box_elems'):
        boxes.append(dict(center=_xyz(e.get_editor_property('center')),
                          rotation=_rot(e.get_editor_property('rotation')),
                          size=[float(e.get_editor_property(k)) for k in ('x','y','z')]))
    other_counts = {}
    for name in ('sphere_elems','sphyl_elems','convex_elems','tapered_capsule_elems',
                 'level_set_elems','skinned_level_set_elems','ml_level_set_elems','skinned_triangle_mesh_elems'):
        try:
            count = len(geometry.get_editor_property(name))
        except Exception:
            continue
        assert count == 0, 'Unexpected non-box source collision: '+name
        other_counts[name] = count
    assert boxes, 'Frame source has no readable simple collision boxes.'
    return dict(collision_trace_flag=trace,boxes=boxes,other_shape_counts=other_counts)


def simple_collision_world_bounds(component):
    signature = simple_collision_signature(component.static_mesh)
    world = component.get_world_transform()
    bounds = []
    for box in signature['boxes']:
        transform = unreal.Transform(location=unreal.Vector(*box['center']),
                     rotation=unreal.Rotator(pitch=box['rotation'][0],yaw=box['rotation'][1],roll=box['rotation'][2]),
                     scale=unreal.Vector(1,1,1))
        points = [_xyz(unreal.MathLibrary.transform_location(world,
                         unreal.MathLibrary.transform_location(transform,unreal.Vector(*corner))))
                  for corner in itertools.product(*[(-v/2,v/2) for v in box['size']])]
        bounds.append([[min(p[i] for p in points) for i in range(3)],
                       [max(p[i] for p in points) for i in range(3)]])
    return bounds


def _render_signature(mesh):
    vertices, normals, uvs, tangents = [],[],[],[]
    triangle_count = 0
    for section in range(mesh.get_num_sections(0)):
        data = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh,0,section)
        vertices.extend(_xyz(v) for v in data[0])
        triangle_count += len(data[1])//3
        normals.extend(tuple(round(c,5) for c in _xyz(v)) for v in data[2])
        uvs.extend((round(float(v.x),5),round(float(v.y),5)) for v in data[3])
        tangents.extend(tuple(round(c,5) for c in _xyz(v.tangent_x))+(bool(v.flip_tangent_y),)
                        for v in data[4])
    assert vertices and triangle_count, mesh.get_path_name()
    def histogram(rows):
        return [[list(k),v] for k,v in sorted(Counter(rows).items())]
    return dict(bounds_cm=[[min(v[i] for v in vertices) for i in range(3)],
                           [max(v[i] for v in vertices) for i in range(3)]],
                vertex_count=len(vertices),triangle_count=triangle_count,
                normals=histogram(normals),uvs=histogram(uvs),tangents=histogram(tangents),
                material_paths=[m.material_interface.get_path_name() if m.material_interface else None
                                for m in mesh.get_editor_property('static_materials')])


def _copy_render_mesh(source):
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    options.set_editor_property('apply_build_settings',False)
    options.set_editor_property('use_build_scale',True)
    options.set_editor_property('request_tangents',True)
    lod = unreal.GeometryScriptMeshReadLOD()
    lod.set_editor_property('lod_type',unreal.GeometryScriptLODType.RENDER_DATA)
    lod.set_editor_property('lod_index',0)
    mesh,outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(
                       source,unreal.DynamicMesh(),options,lod,True)
    assert outcome == unreal.GeometryScriptOutcomePins.SUCCESS, source.get_path_name()
    return mesh


def _recipe(row, spec):
    height,depth = float(row['height']),float(row['depth'])
    scale = spec['relative_scale']
    assert all(v > 0 for v in scale), spec
    assert abs(depth-20) < 1e-6, 'Window frame proxy cache expects existing 20 cm frame depth.'
    name = spec['name']
    mesh_scale = [1.,(depth+.63)/depth,1.]
    mesh_translation = [0.,0.,0.]
    if name in ('FrameLeft','FrameRight'):
        mesh_scale[2] = (height-.5)/height
        mesh_translation[0] = (.25 if name=='FrameLeft' else -.25)/scale[0]
    elif name in ('FrameTop','FrameBottom'):
        mesh_translation[2] = (-.25 if name=='FrameTop' else .25)/scale[2]
    else:
        raise ValueError('Unsupported fixed frame part: '+name)
    return dict(version=RECIPE_VERSION,source=CUBE,height_cm=height,depth_cm=depth,type=name,
                mesh_scale=mesh_scale,mesh_translation_cm=mesh_translation)


def _frame_proxy(row, spec):
    recipe = _recipe(row,spec)
    key = (round(recipe['height_cm']*10),spec['name'])
    if key in _CACHE:
        return _CACHE[key][0],dict(_CACHE[key][1],newly_created=False,cache_reused=True)
    source = unreal.load_asset(CUBE)
    assert isinstance(source,unreal.StaticMesh)
    source_collision = simple_collision_signature(source)
    source_render = _render_signature(source)
    path = ASSET_ROOT+'/SM_OTS_Surface_WindowFrame_H%d_%s_V3'%(key[0],spec['name'].removeprefix('Frame'))
    exists = unreal.EditorAssetLibrary.does_asset_exist(path)
    recipe_text = json.dumps(recipe,sort_keys=True,separators=(',',':'))
    if exists:
        proxy = unreal.load_asset(path)
        assert unreal.EditorAssetLibrary.get_metadata_tag(proxy,'CodexWindowFrameRecipe') == recipe_text, path+' has a different existing recipe'
    else:
        unreal.EditorAssetLibrary.make_directory(ASSET_ROOT)
        proxy = unreal.EditorAssetLibrary.duplicate_asset(CUBE,path)
        assert isinstance(proxy,unreal.StaticMesh),path
        assert simple_collision_signature(proxy) == source_collision
        dynamic = _copy_render_mesh(source)
        unreal.GeometryScript_MeshTransforms.scale_mesh(dynamic,unreal.Vector(*recipe['mesh_scale']),unreal.Vector(0,0,0),True)
        unreal.GeometryScript_MeshTransforms.translate_mesh(dynamic,unreal.Vector(*recipe['mesh_translation_cm']))
        options = unreal.GeometryScriptCopyMeshToAssetOptions()
        for name,value in dict(enable_recompute_normals=False,enable_recompute_tangents=False,
                               enable_remove_degenerates=False,replace_materials=False,emit_transaction=False,
                               defer_mesh_post_edit_change=False,use_build_scale=True).items():
            options.set_editor_property(name,value)
        options.set_editor_property('generate_lightmap_u_vs',unreal.GeometryScriptGenerateLightmapUVOptions.DO_NOT_GENERATE_LIGHTMAP_U_VS)
        lod = unreal.GeometryScriptMeshWriteLOD()
        lod.set_editor_property('lod_index',0)
        lod.set_editor_property('write_hi_res_source',False)
        _,outcome = unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(dynamic,proxy,options,lod,True)
        assert outcome == unreal.GeometryScriptOutcomePins.SUCCESS,path
        unreal.EditorAssetLibrary.set_metadata_tag(proxy,'CodexWindowFrameRecipe',recipe_text)
    collision_after = simple_collision_signature(proxy)
    assert collision_after == source_collision, path+' simple collision changed'
    render_after = _render_signature(proxy)
    for name in ('triangle_count','normals','uvs','tangents','material_paths'):
        assert render_after[name] == source_render[name], (path,name,'render attributes changed')
    expected_bounds = [[source_render['bounds_cm'][side][axis]*recipe['mesh_scale'][axis]+recipe['mesh_translation_cm'][axis]
                        for axis in range(3)] for side in range(2)]
    assert max(abs(render_after['bounds_cm'][side][axis]-expected_bounds[side][axis])
               for side in range(2) for axis in range(3)) < .001, (path,render_after['bounds_cm'],expected_bounds)
    if not exists:
        assert unreal.EditorAssetLibrary.save_loaded_asset(proxy,False),path
    report = dict(asset=proxy.get_path_name(),newly_created=not exists,recipe=recipe,
                  collision_source=CUBE,simple_collision_verified_unchanged=True,
                  collision_signature=collision_after,source_render_bounds_cm=source_render['bounds_cm'],
                  corrected_render_bounds_cm=render_after['bounds_cm'],render_attributes_verified_preserved=True,
                  triangle_count=render_after['triangle_count'])
    _CACHE[key] = (proxy,report)
    return proxy,report


def apply_window(actor, placedrow):
    """Set proxy meshes and NoCollision sash/rail geometry; never save a map."""
    assert actor.get_actor_label() == placedrow['actor']
    result = deepcopy(placedrow)
    originals = {row['name']:row for row in placedrow['components']}
    candidates = {row['name']:row for row in separated_window_components(placedrow)}
    components = {c.get_name():c for c in actor.get_components_by_class(unreal.StaticMeshComponent)}
    changes, asset_reports = [],[]
    pane_before = {name:dict(pose=_pose(c),mesh=c.static_mesh.get_path_name(),materials=_materials(c))
                   for name,c in components.items() if name.endswith('PaneCollision')}
    for spec in result['components']:
        name = spec['name']
        if name.startswith('Frame'):
            component = components[name]
            before_pose = _pose(component)
            before_world_collision = simple_collision_world_bounds(component)
            before_materials = _materials(component)
            proxy,report = _frame_proxy(placedrow,originals[name])
            component.set_static_mesh(proxy)
            assert _pose(component) == before_pose, name+' original frame pose/collision settings changed'
            assert simple_collision_world_bounds(component) == before_world_collision, name+' world physics boxes moved'
            assert _materials(component) == before_materials, name+' material overrides changed'
            spec['asset'] = proxy.get_path_name()
            spec['render_geometry_override'] = report['recipe']
            asset_reports.append(report)
            changes.append(dict(component=name,kind='render_mesh_only',asset=proxy.get_path_name(),
                                simple_world_collision_bounds_cm=before_world_collision,physics_verified_unchanged=True))
        elif name.endswith('Sash') or name.endswith('MeetingRail'):
            component = components[name]
            assert component.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION, name+' unexpectedly blocks physics'
            candidate = candidates[name]
            before_pose = _pose(component)
            # Dedicated setters update only this component; editor property
            # notifications can rerun the Actor's Blueprint construction.
            component.set_relative_location(unreal.Vector(*candidate['relative_location']),False,False)
            component.set_relative_scale3d(unreal.Vector(*candidate['relative_scale']))
            spec.update(deepcopy(candidate))
            changes.append(dict(component=name,kind='NoCollision_visible_geometry',before=before_pose,after=_pose(component)))
    pane_after = {name:dict(pose=_pose(c),mesh=c.static_mesh.get_path_name(),materials=_materials(c))
                  for name,c in components.items() if name.endswith('PaneCollision')}
    differences = _pane_differences(pane_before,pane_after)
    if differences:
        directory = Path(unreal.Paths.project_dir()).resolve()/'Saved/CodexOutputs/SurfaceSeparation_20261009'
        directory.mkdir(parents=True,exist_ok=True)
        (directory/'WindowPaneDiff.json').write_text(json.dumps(dict(actor=actor.get_actor_label(),
            before=pane_before,after=pane_after,differences=differences),ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(d['within_roundoff'] for d in differences), 'PaneCollision changed; details: '+json.dumps(differences)
    result['surface_repair'] = dict(frame_render_depth_cm=float(placedrow['depth'])+.63,
                                  unchanged_frame_transforms=True,unchanged_frame_simple_world_collision=True,
                                  unchanged_pane_collision=True)
    return result,dict(actor=actor.get_actor_label(),passed=True,changes=changes,new_assets=asset_reports,
                       pane_collision_verified_unchanged=True,pane_roundoff_differences=differences,blueprint_class_unchanged=True)
