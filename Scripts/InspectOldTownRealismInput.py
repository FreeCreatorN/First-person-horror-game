"""Read persisted hotel meshes, material chains, collision, and Blueprint SCS.

Only creates evidence files under Saved/CodexOutputs/OldTownRealism_20261012.
Does not compile Blueprints, mutate assets, save packages, or save the map.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import traceback

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
from PolishOldTownHotel import actor_state, sha, xyz
from BuildOldTownOpeningBlueprints import _templates
from OldTownSurfaceMaterials import PARAMETER

SOURCE = ROOT / 'Saved/CodexOutputs/SanitaryFinish_20261012'
WORK = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
SOURCE_SHA = 'ade3fcc6a6482713618e3fadbd4534771549e773097fd2b9d34886318451e1f6'
MATERIAL_CACHE = {}
MESH_CACHE = {}
SOURCE_FILES = {}
LIMITATIONS = []


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def native_text_export(obj, file):
    """Native property serialization also includes unexposed UPROPERTY data."""
    file.parent.mkdir(parents=True, exist_ok=True)
    task = unreal.AssetExportTask()
    for name, v in dict(object=obj, exporter=unreal.ObjectExporterT3D(), filename=str(file),
                        automated=True, prompt=False, replace_identical=True).items():
        task.set_editor_property(name, v)
    exported = unreal.Exporter.run_asset_export_task(task)
    raw = file.read_bytes() if exported and file.is_file() else b''
    text = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig') if raw else ''
    return text, dict(passed=bool(text), file=str(file) if text else None,
        sha256=sha(file) if text else None, bytes=len(raw))


def path_of(obj):
    return obj.get_path_name() if obj is not None else None


def asset_file(obj):
    package = obj.get_path_name().split('.')[0]
    if package.startswith('/Game/'):
        return ROOT / ('Content/' + package[6:] + '.uasset')
    if package.startswith('/Engine/'):
        return Path(unreal.Paths.engine_content_dir()).resolve() / (package[8:] + '.uasset')
    return None


def record_source(obj):
    file = asset_file(obj)
    if file is not None:
        assert file.is_file(), str(file)
        SOURCE_FILES[str(file)] = sha(file)
        return dict(file=str(file), sha256=SOURCE_FILES[str(file)])
    return dict(file=None, sha256=None)


def value(v, depth=0):
    """Stable numerical values, object paths, no UObject pointer reprs."""
    if v is None or isinstance(v, (bool, str, int)):
        return v
    if isinstance(v, float):
        assert math.isfinite(v)
        return v
    if isinstance(v, unreal.Object):
        return dict(object=path_of(v), class_path=v.get_class().get_path_name())
    if isinstance(v, unreal.Name) or isinstance(v, unreal.Text):
        return str(v)
    if isinstance(v, unreal.Vector):
        return [float(v.x), float(v.y), float(v.z)]
    if isinstance(v, unreal.Vector2D):
        return [float(v.x), float(v.y)]
    if isinstance(v, unreal.Rotator):
        return [float(v.pitch), float(v.yaw), float(v.roll)]
    if isinstance(v, unreal.Quat):
        return [float(v.x), float(v.y), float(v.z), float(v.w)]
    if isinstance(v, unreal.LinearColor):
        return [float(v.r), float(v.g), float(v.b), float(v.a)]
    if isinstance(v, unreal.Transform):
        return dict(translation=value(v.translation), rotation_quaternion_xyzw=value(v.rotation), scale=value(v.scale3d))
    if isinstance(v, unreal.Color):
        return [int(v.r), int(v.g), int(v.b), int(v.a)]
    if depth < 6:
        if isinstance(v, dict):
            return {str(k): value(x, depth + 1) for k, x in v.items()}
        if isinstance(v, (list, tuple, unreal.Array)):
            return [value(x, depth + 1) for x in v]
        if isinstance(v, unreal.StructBase):
            fields = {}
            for name in dir(v):
                if name.startswith('_'):
                    continue
                try:
                    x = v.get_editor_property(name)
                    fields[name] = value(x, depth + 1)
                except Exception:
                    pass
            return dict(struct=v.__class__.__name__, fields=fields)
    return str(v)


def props(obj, names):
    out = {}
    for name in names:
        try:
            out[name] = value(obj.get_editor_property(name))
        except Exception:
            pass
    return out


def reflect_editor_properties(obj):
    out = {}
    for name in dir(obj):
        if name.startswith('_'):
            continue
        try:
            out[name] = value(obj.get_editor_property(name))
        except Exception:
            pass
    return out


def bounds(vertices):
    assert vertices
    return [[min(p[i] for p in vertices) for i in range(3)],
            [max(p[i] for p in vertices) for i in range(3)]]


def dimensions(bb):
    return [bb[1][i] - bb[0][i] for i in range(3)]


def texture_record(texture):
    return dict(asset=path_of(texture), class_path=texture.get_class().get_path_name(),
                **record_source(texture), properties=props(texture, [
                    'srgb', 'compression_settings', 'lod_group', 'filter',
                    'address_x', 'address_y', 'virtual_texture_streaming',
                    'max_texture_size', 'mip_gen_settings']))


def material_record(material):
    path = path_of(material)
    if path in MATERIAL_CACHE:
        return MATERIAL_CACHE[path]
    edit = unreal.MaterialEditingLibrary
    chain = []
    current = material
    visited = set()
    while current is not None:
        assert path_of(current) not in visited, 'Material parent cycle'
        visited.add(path_of(current))
        try:
            metadata = {str(k): str(v) for k, v in unreal.EditorAssetLibrary.get_metadata_tag_values(current).items()}
        except Exception:
            metadata = {}
        node = dict(asset=path_of(current), class_path=current.get_class().get_path_name(),
                    **record_source(current), metadata=metadata)
        if isinstance(current, unreal.MaterialInstanceConstant):
            node['instance_overrides'] = props(current, [
                'scalar_parameter_values', 'vector_parameter_values',
                'texture_parameter_values', 'static_parameters',
                'base_property_overrides', 'physical_material'])
            current = current.get_editor_property('parent')
        else:
            node['properties'] = props(current, [
                'blend_mode', 'two_sided', 'shading_model', 'use_material_attributes',
                'translucency_lighting_mode', 'refraction_method',
                'always_evaluate_world_position_offset',
                'max_world_position_offset_displacement', 'dithered_lod_transition'])
            node['property_inputs'] = {}
            graph_nodes = {}
            for prop in ('MP_BASE_COLOR', 'MP_NORMAL', 'MP_ROUGHNESS', 'MP_METALLIC',
                         'MP_SPECULAR', 'MP_OPACITY', 'MP_OPACITY_MASK', 'MP_EMISSIVE_COLOR',
                         'MP_WORLD_POSITION_OFFSET', 'MP_REFRACTION', 'MP_AMBIENT_OCCLUSION'):
                expression = edit.get_material_property_input_node(current, getattr(unreal.MaterialProperty, prop))
                node['property_inputs'][prop] = dict(node=path_of(expression),
                    output=edit.get_material_property_input_node_output_name(current, getattr(unreal.MaterialProperty, prop)))
                pending = [expression] if expression else []
                while pending:
                    expression = pending.pop()
                    expression_path = path_of(expression)
                    if expression_path in graph_nodes:
                        continue
                    inputs = list(edit.get_inputs_for_material_expression(current, expression))
                    graph_nodes[expression_path] = dict(class_path=expression.get_class().get_path_name(),
                        input_names=list(edit.get_material_expression_input_names(expression)),
                        input_nodes=[path_of(x) for x in inputs],
                        properties=props(expression, ['constant', 'r', 'parameter_name', 'default_value',
                            'texture', 'sampler_type', 'const_a', 'const_b', 'const_alpha',
                            'a', 'b', 'alpha', 'coordinates', 'input', 'scale', 'levels',
                            'quality', 'function', 'material_function', 'desc']))
                    pending.extend(x for x in inputs if x is not None)
            node['connected_graph_nodes'] = graph_nodes
            node['expression_count'] = edit.get_num_material_expressions(current)
            node['used_textures'] = [texture_record(t) for t in edit.get_used_textures(current)]
            current = None
        chain.append(node)
    parameter_names = {}
    for prefix in ('vector', 'scalar', 'texture', 'static_switch'):
        parameter_names[prefix] = [str(x) for x in getattr(edit, 'get_' + prefix + '_parameter_names')(material)]
    effective = {}
    offset = [0., 0., 0.]
    if isinstance(material, unreal.MaterialInstanceConstant):
        for prefix, names in parameter_names.items():
            effective[prefix] = {}
            for name in names:
                v = getattr(edit, 'get_material_instance_' + prefix + '_parameter_value')(material, unreal.Name(name))
                effective[prefix][name] = value(v)
                if isinstance(v, unreal.Texture):
                    record_source(v)
        if PARAMETER in parameter_names['vector']:
            offset = effective['vector'][PARAMETER][:3]
    elif PARAMETER in parameter_names['vector']:
        for n in chain[-1].get('connected_graph_nodes', {}).values():
            if n['properties'].get('parameter_name') == PARAMETER:
                offset = n['properties']['default_value'][:3]
                break
    result = dict(asset=path, chain=chain, base_material=chain[-1]['asset'],
                  parameter_names=parameter_names, effective_instance_parameters=effective,
                  surface_translation_parameter=PARAMETER,
                  has_surface_translation_parameter=PARAMETER in parameter_names['vector'],
                  effective_surface_translation_cm=offset)
    MATERIAL_CACHE[path] = result
    return result


def collision_record(mesh):
    body = mesh.get_editor_property('body_setup')
    if body is None:
        return dict(body_setup=None)
    out = dict(body_setup=path_of(body), properties=props(body, [
        'collision_trace_flag', 'double_sided_geometry', 'generate_mirrored_collision',
        'generate_non_mirrored_collision', 'build_scale3d', 'default_instance',
        'walkable_slope_override', 'phys_material']))
    geometry = body.get_editor_property('agg_geom')
    out['aggregate_geometry'] = {}
    for name in ('box_elems', 'sphere_elems', 'sphyl_elems', 'convex_elems',
                 'tapered_capsule_elems', 'level_set_elems', 'skinned_level_set_elems',
                 'ml_level_set_elems', 'skinned_triangle_mesh_elems'):
        try:
            elements = list(geometry.get_editor_property(name))
        except Exception:
            continue
        out['aggregate_geometry'][name] = [dict(type=e.__class__.__name__, properties=props(e, [
            'center', 'rotation', 'x', 'y', 'z', 'radius', 'radius0', 'radius1',
            'length', 'vertex_data', 'index_data', 'elem_box', 'transform',
            'name', 'collision_enabled', 'contribute_to_mass', 'rest_offset'])) for e in elements]
    # Counts alone are never the geometry preservation signature.
    out['shape_counts'] = {n: len(v) for n, v in out['aggregate_geometry'].items()}
    for row in out['aggregate_geometry'].get('box_elems', []):
        assert set(('center', 'rotation', 'x', 'y', 'z')) <= set(row['properties'])
    missing_convex = any('vertex_data' not in row['properties'] for row in out['aggregate_geometry'].get('convex_elems', []))
    if any(out['shape_counts'].values()):
        file = WORK / 'NativeCollisions' / (mesh.get_name() + '_' + hashlib.sha256(path_of(mesh).encode()).hexdigest()[:10] + '.t3d')
        text, export = native_text_export(body, file)
        match = re.search(r'^\s*AggGeom=(.*)$', text, re.MULTILINE)
        out['native_body_setup_export'] = export
        out['native_aggregate_geometry_text'] = match.group(1) if match else None
        out['complete_shape_parameters_available'] = bool(match) and (not missing_convex or 'VertexData=' in match.group(1))
        if not out['complete_shape_parameters_available']:
            LIMITATIONS.append(dict(asset=path_of(mesh), collision_export_incomplete=True,
                reason='Native BodySetup export did not expose full collision parameters; source file SHA is still bound.'))
    else:
        out['complete_shape_parameters_available'] = True
    return out


def mesh_record(mesh):
    path = path_of(mesh)
    if path in MESH_CACHE:
        return MESH_CACHE[path]
    requested = unreal.GeometryScriptMeshReadLOD()
    requested.set_editor_property('lod_type', unreal.GeometryScriptLODType.RENDER_DATA)
    requested.set_editor_property('lod_index', 0)
    materials, indices, names, outcome = unreal.GeometryScript_AssetUtils.get_section_material_list_from_static_mesh(mesh, requested)
    assert outcome == unreal.GeometryScriptOutcomePins.SUCCESS
    sections = []
    all_positions = []
    slot_rows = []
    for i, slot in enumerate(mesh.static_materials):
        slot_props = props(slot, ['imported_material_slot_name'])
        slot_rows.append(dict(index=i, slot_name=str(slot.material_slot_name),
                              imported_slot_name=slot_props.get('imported_material_slot_name'), material=path_of(slot.material_interface)))
        if slot.material_interface:
            material_record(slot.material_interface)
    for section in range(mesh.get_num_sections(0)):
        vertices, triangles, normals, uvs, tangents = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, section)
        v = [value(x) for x in vertices]
        tt = [int(x) for x in triangles]
        uv = [value(x) for x in uvs]
        if not tt:
            # Old separated meshes retain unused empty render sections.
            continue
        assert v and len(tt) % 3 == 0 and len(normals) == len(v) and len(uv) == len(v),(path,section,len(v),len(tt),len(normals),len(uv))
        all_positions.extend(v)
        norms = [value(x) for x in normals]
        normal_stats = Counter()
        uv_zero_area = 0
        for k in range(0, len(tt), 3):
            ids = tt[k:k + 3]
            a, b, c = [vertices[j] for j in ids]
            dot = unreal.MathLibrary.dot_vector_vector(unreal.MathLibrary.cross_vector_vector(b - a, c - a), normals[ids[0]] + normals[ids[1]] + normals[ids[2]])
            normal_stats['positive' if dot > 1.e-6 else 'negative' if dot < -1.e-6 else 'zero'] += 1
            ua, ub, uc = [uv[j] for j in ids]
            area2 = (ub[0] - ua[0]) * (uc[1] - ua[1]) - (ub[1] - ua[1]) * (uc[0] - ua[0])
            uv_zero_area += abs(area2) < 1.e-12
        sections.append(dict(section_index=section, material_slot_index=int(indices[section]),
            slot_name=str(names[section]), default_material=path_of(materials[section]),
            vertices_cm=v, triangle_indices=tt, normals=norms, uv0=uv,
            tangents=[dict(tangent_x=value(x.tangent_x), flip_tangent_y=bool(x.flip_tangent_y)) for x in tangents],
            triangle_count=len(tt) // 3, vertex_count=len(v), bounds_cm=bounds(v),
            uv0_bounds=[[min(p[i] for p in uv) for i in range(2)], [max(p[i] for p in uv) for i in range(2)]],
            degenerate_uv0_triangles=uv_zero_area, cross_dot_vertex_normals=dict(normal_stats)))
    options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    options.set_editor_property('apply_build_settings', True)
    options.set_editor_property('request_tangents', True)
    options.set_editor_property('use_build_scale', True)
    dynamic, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(mesh, unreal.DynamicMesh(), options, requested, True)
    assert outcome == unreal.GeometryScriptOutcomePins.SUCCESS
    uv_count = unreal.GeometryScript_MeshQueries.get_num_uv_sets(dynamic)
    bb = bounds(all_positions)
    geometry = dict(schema='OldTownRealismUniqueRenderMeshV1', asset=path, render_lod=0,
                    sections=sections, static_material_slots=slot_rows)
    file = WORK / 'NativeMeshes' / (mesh.get_name() + '_' + hashlib.sha256(path.encode()).hexdigest()[:10] + '.json')
    write(file, geometry)
    result = dict(asset=path, **record_source(mesh), render_lod=0,
        geometry_file=str(file), geometry_sha256=sha(file),
        bounds_cm=bb, dimensions_cm=dimensions(bb), uv_channel_count=uv_count,
        sections=[{k: v for k, v in row.items() if k not in ('vertices_cm', 'triangle_indices', 'normals', 'uv0', 'tangents')} for row in sections],
        triangle_count=sum(s['triangle_count'] for s in sections), vertex_count=sum(s['vertex_count'] for s in sections),
        static_material_slots=slot_rows, collision_signature=collision_record(mesh),
        properties=props(mesh, ['light_map_coordinate_index', 'light_map_resolution', 'allow_cpu_access',
            'nanite_settings', 'lod_group', 'min_lod', 'support_uniformly_distributed_sampling']))
    # Unique local positions are cached in memory only; instances export bounds.
    result['_positions'] = all_positions
    MESH_CACHE[path] = result
    return result


def component_record(component, blueprint_template=False):
    parent = component.get_attach_parent()
    out = dict(name=component.get_name(), object_path=path_of(component), class_path=component.get_class().get_path_name(),
               parent_name=parent.get_name() if parent else None, parent_path=path_of(parent),
               relative_pose=props(component, ['relative_location', 'relative_rotation', 'relative_scale3d']),
               mobility=str(component.get_editor_property('mobility')))
    if not blueprint_template:
        transform = component.get_world_transform()
        out['world_pose'] = value(transform)
    if isinstance(component, unreal.PrimitiveComponent):
        out['primitive_properties'] = props(component, ['visible', 'hidden_in_game', 'cast_shadow',
            'generate_overlap_events', 'can_ever_affect_navigation', 'evaluate_world_position_offset',
            'world_position_offset_disable_distance', 'bounds_scale', 'collision_responses', 'body_instance'])
        out['collision_enabled'] = str(component.get_collision_enabled())
        out['collision_profile'] = str(component.get_collision_profile_name())
    if isinstance(component, unreal.BoxComponent):
        out['box_extent_cm'] = value(component.get_editor_property('box_extent'))
    if isinstance(component, unreal.StaticMeshComponent) and component.static_mesh:
        mesh = mesh_record(component.static_mesh)
        out['mesh'] = path_of(component.static_mesh)
        out['local_render_bounds_cm'] = mesh['bounds_cm']
        out['materials'] = []
        offsets = []
        for slot in range(component.get_num_materials()):
            mat = component.get_material(slot)
            if mat is None:
                out['materials'].append(dict(slot=slot, asset=None))
                offsets.append([0., 0., 0.])
                continue
            record = material_record(mat)
            offsets.append(record['effective_surface_translation_cm'])
            out['materials'].append(dict(slot=slot, asset=path_of(mat), base_material=record['base_material'],
                has_surface_translation_parameter=record['has_surface_translation_parameter'],
                effective_surface_translation_cm=record['effective_surface_translation_cm']))
        out['uniform_slot_surface_translation'] = all(o == offsets[0] for o in offsets) if offsets else True
        out['expected_surface_translation_cm_to_preserve'] = offsets[0] if offsets and out['uniform_slot_surface_translation'] else None
        if not blueprint_template:
            world_vertices = [value(unreal.MathLibrary.transform_location(transform, unreal.Vector(*p))) for p in mesh['_positions']]
            out['world_render_bounds_before_wpo_cm'] = bounds(world_vertices)
            if out['uniform_slot_surface_translation']:
                off = offsets[0] if offsets else [0., 0., 0.]
                out['world_render_bounds_after_surface_translation_cm'] = [[p[i] + off[i] for i in range(3)] for p in bounds(world_vertices)]
            out['world_transform_negative_determinant'] = math.prod(value(transform.scale3d)) < 0
    return out


def blueprint_record(package, actors):
    bp = unreal.load_asset(package)
    assert isinstance(bp, unreal.Blueprint)
    cls = unreal.EditorAssetLibrary.load_blueprint_class(package)
    cdo = unreal.get_default_object(cls)
    definitions = []
    variable_names = []
    text_file = WORK / 'NativeBlueprints' / (bp.get_name() + '.t3d')
    text, text_export = native_text_export(bp, text_file)
    for group in ('new_variables', 'generated_variables'):
        try:
            raw = list(bp.get_editor_property(group))
            definitions.append(dict(group=group, count=len(raw), descriptions=[value(v) for v in raw], method='reflected_native_property'))
            for row in raw:
                name = str(row.get_editor_property('var_name'))
                if name not in variable_names:
                    variable_names.append(name)
        except Exception as exc:
            exported_group = 'NewVariables' if group == 'new_variables' else 'GeneratedVariables'
            entries = re.findall(r'^\s*' + exported_group + r'\(\d+\)=(.*)$', text, flags=re.MULTILINE)
            descriptions = []
            for entry in entries:
                match = re.search(r'VarName=(?:"([^"]+)"|([^,\)]+))', entry)
                if match:
                    name = match.group(1) or match.group(2)
                    if name not in variable_names:
                        variable_names.append(name)
                descriptions.append(entry)
            definitions.append(dict(group=group, count=len(entries) if text else None,
                descriptions=descriptions, method='native_t3d_property_export' if text else 'unavailable', reflection_error=str(exc)))
            if not text:
                LIMITATIONS.append(dict(asset=package, unavailable_blueprint_property=group, error=str(exc)))
    defaults = {name: value(cdo.get_editor_property(name)) for name in variable_names}
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    templates = _templates(subsystem, bp)
    out = dict(asset=path_of(bp), **record_source(bp), generated_class=path_of(cls),
        blueprint_properties=props(bp, ['parent_class']),
        parent_class_native_text=(re.search(r'^\s*ParentClass=(.*)$', text, re.MULTILINE).group(1) if re.search(r'^\s*ParentClass=(.*)$', text, re.MULTILINE) else None),
        variable_definitions=definitions,
        all_defined_variable_names=variable_names, cdo_variable_values=defaults,
        native_t3d_export=text_export,
        cdo_editor_properties=reflect_editor_properties(cdo),
        graph_pages=props(bp, ['ubergraph_pages', 'function_graphs', 'macro_graphs', 'delegate_signature_graphs']),
        graph_pages_native_text={name: re.findall(r'^\s*' + name + r'\(\d+\)=(.*)$', text, re.MULTILINE)
            for name in ('UbergraphPages', 'FunctionGraphs', 'MacroGraphs', 'DelegateSignatureGraphs')},
        linked_exec_pin_count_native_text=sum('PinType.PinCategory="exec"' in line and 'LinkedTo=(' in line for line in text.splitlines()),
        component_templates={name: component_record(obj, True) for name, (_, obj) in templates.items()},
        instances={a.get_actor_label(): dict(object_path=path_of(a),
            variable_values={name: value(a.get_editor_property(name)) for name in variable_names},
            components=[component_record(c) for c in a.get_components_by_class(unreal.SceneComponent)]) for a in actors})
    return out


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    build = read(SOURCE / 'BuildReport.json')
    baseline = read(SOURCE / 'AfterSnapshot.json')
    assert sha(MAP) == SOURCE_SHA == build['map_sha256'] == baseline['source_map_sha256']
    before_hashes = dict(baseline['shared_asset_sha256'])
    assert all(sha(Path(p)) == digest for p, digest in before_hashes.items())
    recorded_protected = dict(baseline['protected_map_sha256'])
    protected = {p: sha(Path(p)) for p in recorded_protected}
    protected_changes = [dict(file=p, recorded_sha256=h, input_sha256=protected[p])
                         for p, h in recorded_protected.items() if protected[p] != h]
    # Inventory records a user-edited Main as its actual read-only input. This
    # is not permission for a future mutator to ignore preservation baselines.
    allowed_main = ROOT / 'Content/Yastar/Maps/L_Main.umap'
    assert all(Path(row['file']).resolve() == allowed_main for row in protected_changes)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET)
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by_name = {a.get_actor_label(): a for a in actors}
    assert len(actors) == len(by_name) == 8014
    actual_states = {name: actor_state(actor) for name, actor in by_name.items()}
    assert actual_states == baseline['actors'], 'Persisted actor state differs from accepted source'
    hotel = build['hotel_v4']
    # Release the four independent sanitary source exports immediately, so
    # parallel source-art authors do not wait for the large instance inventory.
    for kind in ('Toilet', 'Washbasin', 'ShowerTray', 'ShowerScreen'):
        row = next(r for r in hotel['placed_props'] if r.get('asset_key') == kind)
        mesh_record(unreal.load_asset(row['asset']))
    labels = set(hotel['new_actor_labels'])
    assert len(labels) == 2975 and labels <= set(by_name)
    grouped = defaultdict(list)
    for row in hotel['placed_doors'] + hotel['placed_windows']:
        grouped[row['blueprint']].append(by_name[row['actor']])
    components = {}
    for name in sorted(labels):
        components[name] = [component_record(c) for c in by_name[name].get_components_by_class(unreal.SceneComponent)]
    blueprints = {package: blueprint_record(package, subset) for package, subset in sorted(grouped.items())}
    assert len(blueprints) == 18
    # Capture recursive material textures and source Blueprint package files too.
    digest = sha(MAP)
    assert digest == SOURCE_SHA and actual_states == {n: actor_state(a) for n, a in by_name.items()}
    unchanged = {p: sha(Path(p)) for p in before_hashes}
    assert unchanged == before_hashes
    assert {p: sha(Path(p)) for p in protected} == protected
    assert all(sha(Path(p)) == h for p, h in SOURCE_FILES.items())
    rebase_file = WORK / 'InputBaselineRebase.json'
    write(rebase_file, dict(passed=True, source_map_sha256=SOURCE_SHA,
        source_snapshot_file=str(SOURCE / 'AfterSnapshot.json'), source_snapshot_sha256=sha(SOURCE / 'AfterSnapshot.json'),
        recorded_input=recorded_protected, current_input=protected, changes=protected_changes,
        scope='Only preexisting user-edited L_Main digest updates; target and 400 shared references unchanged.',
        checked_original_asset_count=len(before_hashes), all_protected_inputs_unchanged_during_export=True))
    out = dict(schema='OldTownRealismNativeInputV1', passed=True, source='fresh_persisted_map_load_read_only',
        source_map_sha256=SOURCE_SHA, map_sha256=digest, target_level=TARGET,
        source_input_sha256={str(SOURCE / f): sha(SOURCE / f) for f in ('BuildReport.json', 'AfterSnapshot.json')},
        actor_count=len(actors), hotel_actor_count=len(labels), outside_hotel_actor_count=len(actors)-len(labels),
        hotel_actor_labels=sorted(labels), component_records=components,
        baseline_snapshot_file=str(SOURCE / 'AfterSnapshot.json'),
        blueprints=blueprints, materials=MATERIAL_CACHE,
        meshes={k: {n: v for n, v in row.items() if n != '_positions'} for k, row in MESH_CACHE.items()},
        source_asset_file_sha256=SOURCE_FILES, original_400_shared_asset_sha256=before_hashes,
        protected_map_sha256=protected, recorded_source_protected_map_sha256=recorded_protected,
        preexisting_protected_map_changes=protected_changes,
        input_baseline_rebase_file=str(rebase_file), input_baseline_rebase_sha256=sha(rebase_file),
        layout_manifest=dict(shell_bounds=hotel['shell_bounds'], floor_z_cm=hotel['floor_z_cm'],
            stair_geometry=hotel['stair_geometry'], doors=hotel['placed_doors'], windows=hotel['placed_windows'],
            boxes=hotel['placed_boxes'], props=hotel['placed_props']),
        statistics=dict(blueprint_variants=len(blueprints), blueprint_instances=sum(len(v) for v in grouped.values()),
            unique_meshes=len(MESH_CACHE), unique_component_materials=len(MATERIAL_CACHE),
            unique_source_files=len(SOURCE_FILES), unique_mesh_triangles=sum(row['triangle_count'] for row in MESH_CACHE.values())),
        limitations=LIMITATIONS, read_only_verification=dict(map_unchanged=True, original_actor_states_unchanged=True,
            original_400_assets_unchanged=True, protected_maps_unchanged=True, recursively_read_assets_unchanged=True,
            no_save_or_compile_called=True))
    write(WORK / 'RealismInput.json', out)
    unreal.log('OLD_TOWN_REALISM_INPUT_PASS ' + json.dumps(out['statistics']) + ' ' + digest)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write(WORK / 'RealismInputFailure.json', dict(passed=False, traceback=traceback.format_exc()))
        raise
