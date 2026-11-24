"""Read-only coverage check for the original Old Town emissive-material audit.

Include surfaces outside ordinary primitive slots and material graph outputs
that cannot be classified solely by looking at the classic emissive pin.
"""
import hashlib
import math
from pathlib import Path
import re

import OldTownNonLightEmission as legacy


_OBJECT_PATH = re.compile(r'''\bExportPath="[^']+'([^']+)'"''')
_NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def _parse_native_emission(text, asset_path):
    """Read only the master MaterialEditorOnlyData property block.

    ObjectExporterT3D emits a declaration and then a second block containing
    properties. An empty declaration alone is not evidence of default values.
    """
    stack, declarations, blocks = [], [], []
    root_found = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('Begin Object '):
            match = _OBJECT_PATH.search(line)
            object_path = match.group(1) if match else None
            target = (len(stack) == 1 and stack[0][0] == asset_path and object_path is not None
                      and object_path.startswith(asset_path + ':')
                      and 'MaterialEditorOnlyData\'' in line)
            if not stack and object_path == asset_path and 'Class=/Script/Engine.Material ' in line:
                root_found = True
            props = [] if target else None
            stack.append((object_path, props))
            if target:
                (declarations if 'Class=/Script/Engine.MaterialEditorOnlyData ' in line else blocks).append((object_path, props))
        elif line == 'End Object':
            if not stack:
                raise ValueError('Unmatched End Object in material export')
            stack.pop()
        elif stack and stack[-1][1] is not None and line.startswith('EmissiveColor='):
            stack[-1][1].append(line.split('=', 1)[1])
    if stack or not root_found or len(declarations) != 1 or len(blocks) != 1:
        raise ValueError('Missing complete native material EditorOnlyData property block')
    object_path, records = blocks[0]
    if object_path != declarations[0][0] or len(records) > 1:
        raise ValueError('Ambiguous native EmissiveColor property')
    record = records[0] if records else None
    enabled = False
    rgb = None
    if record is not None:
        switch = re.search(r'(?:^|[(,])\s*UseConstant\s*=\s*([^,)\s]+)', record)
        if switch:
            raw = switch.group(1).lower()
            if raw not in ('true', 'false', '1', '0'):
                raise ValueError('Unrecognized UseConstant value: ' + raw)
            enabled = raw in ('true', '1')
        if enabled:
            color = re.search(r'(?:^|[(,])\s*Constant\s*=\s*\(([^()]*)\)', record)
            rgb = [0.0, 0.0, 0.0]
            if color:
                for index, channel in enumerate('RGB'):
                    value = re.search(r'(?:^|,)\s*' + channel + r'\s*=\s*(' + _NUMBER + r')\s*(?=,|$)', color.group(1))
                    if value:
                        rgb[index] = float(value.group(1))
                    elif re.search(r'(?:^|,)\s*' + channel + r'\s*=', color.group(1)):
                        raise ValueError('Invalid native emissive color channel: ' + channel)
            elif re.search(r'(?:^|[(,])\s*Constant\s*=', record):
                raise ValueError('Invalid native emissive color tuple')
            if not all(map(math.isfinite, rgb)):
                raise ValueError('Nonfinite native emissive color')
    return dict(enabled=enabled, rgb=rgb, editor_only_data=object_path, native_property=record)


def _color(value):
    if value is None:
        return None
    return [getattr(value, field) for field in ('r', 'g', 'b')]


def _root_emission_constant(master):
    data = legacy._get(master, 'editor_only_data')
    if data is None:
        data = legacy._get(master, 'EditorOnlyData')
    value = legacy._get(data, 'emissive_color') if data is not None else None
    if value is None and data is not None:
        value = legacy._get(data, 'EmissiveColor')
    enabled = legacy._get(value, 'use_constant') if value is not None else None
    if enabled is None and value is not None:
        enabled = legacy._get(value, 'UseConstant')
    color = (legacy._get(value, 'constant') or legacy._get(value, 'Constant')) if enabled else None
    return enabled, _color(color)


def _native_constant(unreal, master, evidence_dir):
    from InspectOldTownRealismInput import native_text_export

    asset = legacy._path(master)
    name = re.sub(r'[^A-Za-z0-9_]+', '_', master.get_name())[:72]
    stamp = hashlib.sha256(asset.encode()).hexdigest()[:12]
    file = evidence_dir / (name + '_' + stamp + '.t3d')
    # The UE native exporter uses global TagImp/TagExp. Clear them without
    # changing any UObject properties so repeated inspect/verify exports are
    # complete. See ProbeOldTownNativeExportMarks.py for an independent check.
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, 'OBJ COMPONENTS Default__Object')
    text, proof = native_text_export(master, file)
    try:
        if not proof['passed']:
            raise ValueError('Native text export produced no evidence')
        parsed = _parse_native_emission(text, asset)
    except ValueError as error:
        return dict(method='native_t3d', export=proof, error=str(error), enabled=None, rgb=None)
    return dict(parsed, method='native_t3d', export=proof)


def _master_constant(unreal, master, evidence_dir):
    enabled, rgb = _root_emission_constant(master)
    if enabled is not None and (not enabled or rgb is not None):
        return dict(method='reflected_editor_data', enabled=enabled, rgb=rgb)
    return _native_constant(unreal, master, evidence_dir)


def _material_graph(unreal, master, material, constant):
    edit = unreal.MaterialEditingLibrary
    props = unreal.MaterialProperty
    state, source = legacy._graph(master)
    front = edit.get_material_property_input_node(master, props.MP_FRONT_MATERIAL)
    attribute = edit.get_material_property_input_node(master, props.MP_MATERIAL_ATTRIBUTES)
    emissive = edit.get_material_property_input_node(master, props.MP_EMISSIVE_COLOR)
    enabled, color = constant['enabled'], constant['rgb']
    shading_model = str(legacy._get(master, 'shading_model', ''))
    overrides = legacy._get(material, 'base_property_overrides')
    if overrides is not None and legacy._get(overrides, 'override_shading_model', False):
        shading_model = str(legacy._get(overrides, 'shading_model', shading_model))
    effective_zero = bool(state == 'emissive_pin' and
                          legacy._effective_zero(material, master, emissive))
    return dict(graph=state, emissive_node=source,
                effective_emissive_provably_black=effective_zero,
                root_constant_enabled=enabled, root_constant_rgb=color,
                material_attributes_node=legacy._path(attribute),
                use_material_attributes=bool(legacy._get(master, 'use_material_attributes', False)),
                front_material_node=legacy._path(front),
                front_material_class=front.get_class().get_name() if front is not None else None,
                shading_model=shading_model, unlit='MSM_UNLIT' in shading_model,
                material_domain=str(legacy._get(master, 'material_domain', '')))


def _extra_materials(unreal, actors):
    """Yield nonstandard render material bindings without touching components."""
    for actor in actors:
        for component in actor.get_components_by_class(unreal.DecalComponent):
            material = component.get_decal_material()
            if material is not None:
                yield actor, component, 0, 'Decal', material, 'decal'
        for component in actor.get_components_by_class(unreal.MeshComponent):
            if isinstance(component, unreal.WidgetComponent):
                continue
            material = component.get_overlay_material()
            if material is not None:
                yield actor, component, -1, 'Overlay', material, 'overlay'
            mesh = legacy._get(component, 'static_mesh') or legacy._get(component, 'skeletal_mesh_asset')
            if mesh is None:
                continue
            slots = legacy._get(mesh, 'static_materials') or legacy._get(mesh, 'materials', [])
            overrides = list(legacy._get(component, 'material_slots_overlay_material', []))
            for index in range(max(len(slots), len(overrides))):
                slot = slots[index] if index < len(slots) else None
                material = overrides[index] if index < len(overrides) else None
                material = material or legacy._get(slot, 'overlay_material_interface')
                if material is not None:
                    yield actor, component, index, str(legacy._get(slot, 'material_slot_name', '')), material, 'mesh_slot_overlay'


def audit_old_town_emission_coverage(actor_subsystem=None, native_evidence_dir=None):
    """Return expanded graph and binding evidence; do not modify or save the map."""
    unreal = legacy.unreal
    actors = legacy._actors(actor_subsystem)
    if native_evidence_dir is None:
        native_evidence_dir = Path(unreal.Paths.project_dir()) / 'Saved/CodexOutputs/OldTownEmissionCoverage_20261113/NativeMaterials'
    native_evidence_dir = Path(native_evidence_dir).resolve()
    saved_root = (Path(unreal.Paths.project_dir()) / 'Saved').resolve()
    if not native_evidence_dir.is_relative_to(saved_root):
        raise ValueError('Native material evidence directory must be within project Saved')
    circuits, controllers = legacy._controller_bindings(actors)
    graph_by_material = {}
    constants_by_master = {}
    report = dict(target_level=legacy.TARGET, actor_count=len(actors), ordinary_bindings=0,
                  extra_bindings=0, unknown_master=[], unresolved_special_graphs=[],
                  non_light_emission=[], protected_emitters=[], unlit_surfaces=[],
                  non_light_function_domains=[], light_component_count=len(legacy._light_state(actors)),
                  controller_count=len(controllers), constant_readable_masters=[],
                  constant_unreadable_masters=[])
    rows = list(legacy._component_slots(actors))
    extra = list(_extra_materials(unreal, actors))
    report['ordinary_bindings'] = len(rows)
    report['extra_bindings'] = len(extra)
    for actor, component, index, slot_name, material, setter in rows + extra:
        material_path = legacy._path(material)
        if material_path not in graph_by_material:
            chain = legacy._chain(material)
            master = chain[-1] if isinstance(chain[-1], unreal.Material) else None
            if master is not None:
                master_path = legacy._path(master)
                if master_path not in constants_by_master:
                    constants_by_master[master_path] = _master_constant(unreal, master, native_evidence_dir)
                graph = _material_graph(unreal, master, material, constants_by_master[master_path])
            else:
                graph = {}
            graph_by_material[material_path] = master, graph
        master, graph = graph_by_material[material_path]
        mesh = legacy._get(component, 'static_mesh') or legacy._get(component, 'skeletal_mesh_asset')
        row = dict(actor=legacy._path(actor), label=actor.get_actor_label(),
                   component=legacy._path(component), component_name=component.get_name(),
                   mesh=legacy._path(mesh), mesh_name=mesh.get_name() if mesh else '',
                   slot=index, slot_name=slot_name, setter=setter, material=material_path,
                   material_name=material.get_name(), master=legacy._path(master),
                   master_name=master.get_name() if master else '', **graph)
        if master is None:
            report['unknown_master'].append(row)
            continue
        reason = legacy._emitter_reason(row, circuits.get((row['component'], index))) if setter == 'slot' else None
        if row['graph'] == 'other_domain':
            report['non_light_function_domains'].append(row)
            continue
        if row['unlit']:
            report['unlit_surfaces'].append(row)
        if row['front_material_node'] or (row['use_material_attributes'] and row['material_attributes_node']):
            report['unresolved_special_graphs'].append(row)
            continue
        color = row['root_constant_rgb']
        # CompileWithDefault selects an authored constant before a connected
        # expression. A known zero constant can therefore suppress that graph.
        graph_emits = row['graph'] == 'emissive_pin' and not row['effective_emissive_provably_black']
        may_emit = any(color) if row['root_constant_enabled'] and color is not None else graph_emits
        if may_emit:
            if reason:
                report['protected_emitters'].append(dict(row, reason=reason))
            else:
                report['non_light_emission'].append(row)
    by_master = {legacy._path(master): (graph['root_constant_enabled'] is not None
                and (not graph['root_constant_enabled'] or graph['root_constant_rgb'] is not None))
                 for master, graph in graph_by_material.values() if master is not None}
    report['constant_readable_masters'] = sorted(k for k, v in by_master.items() if v)
    report['constant_unreadable_masters'] = sorted(k for k, v in by_master.items() if not v)
    report['constant_evidence'] = dict(sorted(constants_by_master.items()))
    report['distinct_materials'] = len(graph_by_material)
    report['passed'] = not any(report[k] for k in ('unknown_master', 'unresolved_special_graphs', 'non_light_emission',
                                                  'constant_unreadable_masters'))
    return report
