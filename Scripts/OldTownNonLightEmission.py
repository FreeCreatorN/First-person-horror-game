"""Inspect or neutralize non-lamp emissive slots in the original Old Town map.

Only scene component overrides and new map-specific material packages are
written. The caller owns saving the current level after combined validation.
"""
import hashlib
import re

try:
    import unreal
except ImportError:
    unreal = None

TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
ASSET_ROOT = '/Game/CodexGenerated/OldTown/OriginalNonLightEmission_20261113'


def _path(obj):
    return obj.get_path_name() if obj is not None else None


def _get(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def _actors(actor_subsystem):
    if unreal is None:
        raise RuntimeError('Run this script inside Unreal Editor')
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None or _path(world).split('.', 1)[0] != TARGET:
        raise RuntimeError('Original Old Town map must be active: ' + str(_path(world)))
    actor_subsystem = actor_subsystem or unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return sorted(actor_subsystem.get_all_level_actors(), key=_path)


def _tokens(value):
    value = re.sub(r'([a-z])([A-Z])', r'\1 \2', value or '')
    return set(re.findall('[a-z]+', value.lower()))


def _controller_bindings(actors):
    slots = {}
    controllers = []
    for actor in actors:
        target = _get(actor, 'target_lamp_mesh')
        slot = _get(actor, 'emissive_material_slot')
        if target is None or not isinstance(slot, int):
            continue
        lights = list(_get(actor, 'controlled_lights', []))
        component = target.get_component_by_class(unreal.StaticMeshComponent)
        if component is None or not 0 <= slot < component.get_num_materials():
            raise RuntimeError('Invalid light circuit slot: ' + _path(actor))
        row = dict(actor=_path(actor), target=_path(target), component=_path(component),
                   slot=slot, lights=[_path(light) for light in lights],
                   base_intensities=list(_get(actor, 'base_intensities', [])),
                   initially_on=_get(actor, 'initially_on'))
        controllers.append(row)
        if lights and all(light is not None and light.get_component_by_class(unreal.LightComponent)
                          for light in lights):
            slots[(_path(component), slot)] = row
    return slots, controllers


def _light_state(actors):
    fields = ('intensity', 'intensity_units', 'light_color', 'visible', 'hidden_in_game',
              'attenuation_radius', 'cast_shadows', 'temperature', 'use_temperature',
              'mobility', 'indirect_lighting_intensity', 'volumetric_scattering_intensity')
    def plain(value):
        if isinstance(value, (unreal.Color, unreal.LinearColor)):
            return [getattr(value, key) for key in ('r', 'g', 'b', 'a')]
        if isinstance(value, (bool, int, float, str)) or value is None:
            return value
        return str(value)

    def transform(c):
        t = c.get_world_transform()
        return dict(translation=[t.translation.x, t.translation.y, t.translation.z],
                    rotation=[t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w],
                    scale=[t.scale3d.x, t.scale3d.y, t.scale3d.z])

    return sorted([dict(component=_path(c), transform=transform(c),
                        properties={field: plain(_get(c, field)) for field in fields})
                   for a in actors for c in a.get_components_by_class(unreal.LightComponentBase)],
                  key=lambda row: row['component'])


_HARDWARE = {'body', 'base', 'bracket', 'housing', 'pole', 'mount', 'socket', 'frame',
             'cap', 'arm', 'fastener', 'hood', 'baffle', 'trim', 'reflector', 'backplate'}
_EMITTER = {'tube', 'bulb', 'lens', 'diffuser', 'led', 'filament', 'emitter'}
_FIXTURE = {'lamp', 'light', 'fixture', 'fluorescent', 'lantern', 'luminaire', 'torch', 'flashlight'}
_KNOWN_MASTERS = {'M_OTS_Callable_HotelTube', 'M_OTS_Callable_StreetLens',
                  'M_OTS_Street03_GlassCallable', 'M_RF_StreetLens', 'M_RF_HotelTube'}
_HOTEL_STREET_LENS = {'M_Hotel_StreetLens', 'M_Hotel_Street03_GlassCallable'}


def _emitter_reason(row, circuit):
    slot_words = _tokens(row['slot_name'])
    material_words = _tokens(row['material_name'])
    base = row['master_name']
    if (slot_words | material_words | _tokens(base)) & _HARDWARE:
        return None
    owner_words = _tokens(row['label']) | _tokens(row['mesh_name']) | _tokens(row['component_name'])
    fixture = bool(owner_words & _FIXTURE or 'gallerytube' in row['label'].lower())
    emitter = bool((slot_words | material_words) & _EMITTER)
    # This street fixture models the luminous face as a dedicated recessed
    # lens in its glass slot, with the pole, hood and bracket on other slots.
    if (circuit and base in _HOTEL_STREET_LENS and row['slot'] == 2
            and row['slot_name'] == 'M_R_Glass_UV'
            and row['mesh_name'].startswith('SM_Hotel_StreetLamp')
            and re.fullmatch(r'OTS_P2Prop_StreetLamp_\d+', row['label'])):
        return 'street luminaire recessed optical face, isolated from hardware'
    if circuit and (emitter or base in _KNOWN_MASTERS):
        return 'verified circuit emitter slot'
    if fixture and emitter:
        return 'physical emitter material slot'
    if fixture and row['slot'] == 2 and base in _KNOWN_MASTERS:
        return 'known masked tube/lens master on emitter slot'
    if base == 'M_OTS_FluorescentTube' and re.fullmatch(r'OTS_P2Prop_StreetLamp_\d+', row['label']):
        return 'legacy street luminaire tube material'
    return None


def _chain(material):
    chain = []
    seen = set()
    while material is not None:
        path = _path(material)
        if path in seen:
            raise RuntimeError('Material inheritance cycle: ' + path)
        seen.add(path)
        chain.append(material)
        if isinstance(material, unreal.Material):
            return chain
        if not isinstance(material, unreal.MaterialInstance):
            break
        material = _get(material, 'parent')
    return chain


def _is_zero(expression):
    if isinstance(expression, unreal.MaterialExpressionConstant):
        return float(_get(expression, 'r', 1.0)) == 0.0
    if isinstance(expression, unreal.MaterialExpressionConstant3Vector):
        value = _get(expression, 'constant')
        return value is not None and all(getattr(value, axis) == 0.0 for axis in ('r', 'g', 'b'))
    return False


def _effective_zero(material, master, node, visited=None):
    """Prove zero through simple constants, multiply and static switches.

    This never guesses that a complex shader is black. In particular, a
    fixture with runtime LightStrength must remain eligible for preservation.
    """
    if _is_zero(node):
        return True
    if node is None:
        return False
    visited = set() if visited is None else visited
    if _path(node) in visited:
        return False
    visited = visited | {_path(node)}
    edit = unreal.MaterialEditingLibrary
    cls = node.get_class().get_name()
    if cls == 'MaterialExpressionStaticSwitchParameter':
        name = _get(node, 'parameter_name')
        if name is None:
            return False
        if isinstance(material, unreal.MaterialInstanceConstant):
            active = edit.get_material_instance_static_switch_parameter_value(material, name)
        elif isinstance(material, unreal.Material):
            active = _get(node, 'default_value')
        else:
            return False
        inputs = list(edit.get_inputs_for_material_expression(master, node))
        return isinstance(active, bool) and len(inputs) == 2 and _effective_zero(
            material, master, inputs[0 if active else 1], visited)
    if cls == 'MaterialExpressionMultiply':
        inputs = list(edit.get_inputs_for_material_expression(master, node))
        return len(inputs) == 2 and any(
            _effective_zero(material, master, value, visited) if value is not None
            else _get(node, ('const_a', 'const_b')[index]) == 0.0
            for index, value in enumerate(inputs))
    return False


def _graph(material):
    edit = unreal.MaterialEditingLibrary
    props = unreal.MaterialProperty
    domain = str(_get(material, 'material_domain', ''))
    if any(name in domain for name in ('MD_UI', 'MD_POST_PROCESS', 'MD_LIGHT_FUNCTION', 'MD_VOLUME')):
        return 'other_domain', None
    if _get(material, 'use_material_attributes', False):
        source = edit.get_material_property_input_node(material, props.MP_MATERIAL_ATTRIBUTES)
        if source is not None:
            return 'material_attributes', _path(source)
        return 'no_emission', None
    node = edit.get_material_property_input_node(material, props.MP_EMISSIVE_COLOR)
    if node is None or _is_zero(node):
        return 'no_emission', _path(node)
    return 'emissive_pin', _path(node)


def _component_slots(actors):
    for actor in actors:
        for comp in actor.get_components_by_class(unreal.PrimitiveComponent):
            # WidgetComponent's fixed unlit composite is the visible UI itself.
            if isinstance(comp, unreal.WidgetComponent):
                continue
            if isinstance(comp, unreal.DecalComponent):
                material = comp.get_decal_material()
                if material is not None:
                    yield actor, comp, 0, 'Decal', material, 'decal'
                continue
            slots = list(comp.get_material_slot_names())
            for index in range(comp.get_num_materials()):
                material = comp.get_material(index)
                if material is not None:
                    name = str(slots[index]) if index < len(slots) else ''
                    yield actor, comp, index, name, material, 'slot'


def _inventory(actor_subsystem=None):
    actors = _actors(actor_subsystem)
    bindings, controllers = _controller_bindings(actors)
    report = dict(target_level=TARGET, candidates=[], preserved=[], unsupported=[],
                  attributes_review=[], ignored_domains=[], inactive_emissive=[],
                  scanned_slots=0, distinct_materials=0,
                  controllers=controllers, light_components=_light_state(actors))
    graphs = {}
    materials = {}
    refs = {}
    for actor, comp, slot, slot_name, material, setter in _component_slots(actors):
        report['scanned_slots'] += 1
        material_path = _path(material)
        if material_path not in materials:
            chain = _chain(material)
            master = chain[-1] if isinstance(chain[-1], unreal.Material) else None
            if master is not None and _path(master) not in graphs:
                graphs[_path(master)] = _graph(master)
            state, node = graphs[_path(master)] if master is not None else ('unsupported', None)
            zero = state == 'emissive_pin' and _effective_zero(material, master,
                unreal.MaterialEditingLibrary.get_material_property_input_node(
                    master, unreal.MaterialProperty.MP_EMISSIVE_COLOR))
            materials[material_path] = master, state, node, zero
        master, state, node, zero = materials[material_path]
        if state == 'no_emission':
            continue
        mesh = _get(comp, 'static_mesh') or _get(comp, 'skeletal_mesh_asset')
        row = dict(actor=_path(actor), label=actor.get_actor_label(), component=_path(comp),
                   component_name=comp.get_name(), mesh=_path(mesh), mesh_name=mesh.get_name() if mesh else '',
                   slot=slot, slot_name=slot_name, material=material_path, material_name=material.get_name(),
                   master=_path(master), master_name=master.get_name() if master else '',
                   node=node, graph=state, setter=setter)
        circuit = bindings.get((_path(comp), slot))
        reason = _emitter_reason(row, circuit)
        if state == 'other_domain':
            report['ignored_domains'].append(row)
        elif reason:
            report['preserved'].append(dict(row, reason=reason, controller=circuit['actor'] if circuit else None))
        elif zero and not circuit:
            report['inactive_emissive'].append(dict(row, reason='effective emissive branch is provably black'))
        elif state == 'material_attributes':
            report['attributes_review'].append(row)
        elif state == 'unsupported' or not isinstance(material, (unreal.Material, unreal.MaterialInstanceConstant)):
            report['unsupported'].append(row)
        else:
            report['candidates'].append(row)
            refs[(row['component'], slot)] = (comp, material)
    report['distinct_materials'] = len(materials)
    return report, refs


def inspect_non_light_emission(actor_subsystem=None):
    """Return effective emissive slots, protected light slots, and uncertain graphs."""
    return _inventory(actor_subsystem)[0]


def _package(obj):
    return _path(obj).split('.', 1)[0]


def _asset_destination(material, version='v1'):
    prefix = 'M_' if isinstance(material, unreal.Material) else 'MI_'
    readable = re.sub(r'[^A-Za-z0-9_]+', '_', material.get_name())[:61]
    stamp = hashlib.sha256((_path(material) + version).encode()).hexdigest()[:10]
    return ASSET_ROOT + '/' + prefix + 'NoEmission_' + readable + '_' + stamp


def _master_inputs(material):
    """Graph pin references by local name, comparable across asset duplication."""
    edit = unreal.MaterialEditingLibrary
    result = {}
    # UE's getter dereferences the returned input; enum entries without an
    # actual editor pin are unsafe to query (e.g. MP_CUSTOM_OUTPUT).
    names = ('BASE_COLOR', 'METALLIC', 'SPECULAR', 'ROUGHNESS', 'ANISOTROPY',
             'NORMAL', 'TANGENT', 'WORLD_POSITION_OFFSET', 'DISPLACEMENT',
             'SUBSURFACE_COLOR', 'CUSTOM_DATA0', 'CUSTOM_DATA1', 'AMBIENT_OCCLUSION',
             'REFRACTION', 'MATERIAL_ATTRIBUTES', 'PIXEL_DEPTH_OFFSET', 'SHADING_MODEL',
             'SURFACE_THICKNESS', 'FRONT_MATERIAL', 'OPACITY', 'OPACITY_MASK')
    names += tuple('CUSTOMIZED_UVS{}'.format(i) for i in range(8))
    for name in names:
        prop = getattr(unreal.MaterialProperty, 'MP_' + name, None)
        if prop is None:
            continue
        node = edit.get_material_property_input_node(material, prop)
        if node is not None:
            result[name] = (node.get_name(), edit.get_material_property_input_node_output_name(material, prop))
    return result


def _neutralize(material, cache, packages):
    source = _path(material)
    if source in cache:
        return cache[source]
    edit = unreal.MaterialEditingLibrary
    assets = unreal.EditorAssetLibrary
    destination = _asset_destination(material)
    is_master = isinstance(material, unreal.Material)
    parent = None if is_master else _get(material, 'parent')
    neutral_parent = _neutralize(parent, cache, packages) if parent is not None else None
    if assets.does_asset_exist(destination):
        clone = assets.load_asset(destination)
        if assets.get_metadata_tag(clone, 'OldTownNonLightEmissionSource') != source:
            raise RuntimeError('Refusing to overwrite existing asset: ' + destination)
        reused = True
    else:
        assets.make_directory(ASSET_ROOT)
        clone = assets.duplicate_asset(_package(material), destination)
        if clone is None or clone.get_class() != material.get_class():
            raise RuntimeError('Unable to duplicate complete material: ' + source)
        if is_master:
            old_inputs = _master_inputs(material)
            black = edit.create_material_expression(clone, unreal.MaterialExpressionConstant, -360, 260)
            black.set_editor_property('r', 0.0)
            if not edit.connect_material_property(black, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR):
                raise RuntimeError('Unable to set emissive output to black: ' + destination)
            if old_inputs != _master_inputs(clone):
                raise RuntimeError('A non-emissive material input changed: ' + destination)
            edit.recompile_material(clone)
        else:
            if neutral_parent is None:
                raise RuntimeError('Missing cloned instance parent: ' + source)
            edit.set_material_instance_parent(clone, neutral_parent)
            edit.update_material_instance(clone)
        assets.set_metadata_tag(clone, 'OldTownNonLightEmissionSource', source)
        if not assets.save_loaded_asset(clone, False):
            raise RuntimeError('Unable to save neutral material: ' + destination)
        reused = False
    if is_master and _graph(clone)[0] != 'no_emission':
        raise RuntimeError('Cloned material remains emissive: ' + destination)
    if not is_master and _path(_get(clone, 'parent')) != _path(neutral_parent):
        raise RuntimeError('Unexpected cloned material parent: ' + destination)
    packages.append(dict(source=source, asset=_path(clone), reused=reused))
    cache[source] = clone
    return clone


def _key(row):
    return row['component'], row['slot'], row['material']


def _light_identity(report):
    return sorted((_key(row), row['reason'], row['controller']) for row in report['preserved'])


def verify_non_light_emission(actor_subsystem=None, expected=None):
    report = inspect_non_light_emission(actor_subsystem)
    problems = list(report['candidates']) + list(report['unsupported']) + list(report['attributes_review'])
    if problems:
        raise RuntimeError('Unresolved non-light emissive/material slots: ' + str(problems[:8]))
    if expected is not None:
        expected = expected.get('before', expected)
        for key in ('light_components', 'controllers'):
            if expected[key] != report[key]:
                raise RuntimeError('Light state changed: ' + key)
        if _light_identity(expected) != _light_identity(report):
            raise RuntimeError('Preserved light surface bindings changed')
    return dict(report, passed=True)


def apply_non_light_emission(actor_subsystem=None, expected=None):
    """Apply only approved original-level component material overrides; do not save map."""
    before, refs = _inventory(actor_subsystem)
    if expected is not None:
        expected = expected.get('before', expected)
        if before != expected:
            raise RuntimeError('Non-light material inventory changed since inspection')
    if before['unsupported'] or before['attributes_review']:
        raise RuntimeError('Review unsupported material graph(s) before applying: ' +
                           str((before['unsupported'] + before['attributes_review'])[:8]))
    cache, packages, changes, rollback = {}, [], [], []
    # Prepare all clones before modifying any level component.
    for row in before['candidates']:
        material = refs[(row['component'], row['slot'])][1]
        _neutralize(material, cache, packages)
    try:
        for row in before['candidates']:
            comp, material = refs[(row['component'], row['slot'])]
            clone = cache[_path(material)]
            if row['setter'] == 'decal':
                rollback.append((comp, None, material))
                comp.set_decal_material(clone)
                actual = comp.get_decal_material()
            else:
                overrides = _get(comp, 'override_materials')
                if overrides is not None:
                    rollback.append((comp, 'override_materials', list(overrides)))
                else:
                    rollback.append((comp, row['slot'], material))
                comp.set_material(row['slot'], clone)
                actual = comp.get_material(row['slot'])
            if _path(actual) != _path(clone):
                raise RuntimeError('Material override failed: ' + str(row))
            changes.append(dict(row, replacement=_path(clone)))
        after = verify_non_light_emission(actor_subsystem, before)
    except Exception:
        for comp, slot, previous in reversed(rollback):
            if slot is None:
                comp.set_decal_material(previous)
            elif slot == 'override_materials':
                comp.set_editor_property(slot, previous)
            else:
                comp.set_material(slot, previous)
        raise
    return dict(passed=True, before=before, after=after, changes=changes, assets=packages,
                changed_slots=len(changes), preserved_emissive_slots=len(after['preserved']),
                map_saved=False)
