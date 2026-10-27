"""Strict raw-value copying for disposable/new reusable door actors.

Nothing runs on import. These helpers never create/save/rename/destroy actors or
assets. The caller owns the target actor and must probe before saving a map.
"""
from __future__ import annotations

import inspect
import unreal
import InspectOldTownRealismInput as native
from OldTownMainLightingCommon import capture_geometry_state, compare_world_transform


# These describe ownership/attachment/instance identity, rather than door art or
# collision. Attachment and transforms have separate explicit checks below.
IDENTITY_PROPERTIES = frozenset({
    'creation_method', 'owner', 'owner_private', 'outer', 'archetype',
    'component_template', 'ucs_modified_properties', 'ucss_modified_properties',
    'attach_parent', 'attach_children', 'client_attached_children',
    'attach_socket_name', 'component_to_world',
})
TRANSFORM_PROPERTIES = frozenset({
    'relative_location', 'relative_translation', 'relative_rotation', 'relative_scale3d',
    'absolute_location', 'b_absolute_translation', 'absolute_rotation', 'absolute_scale',
    'mobility', 'modify_frequency',
})
REQUIRED_SCENE = frozenset({
    'relative_location', 'relative_rotation', 'relative_scale3d',
    'absolute_location', 'absolute_rotation', 'absolute_scale',
    'visible', 'hidden_in_game', 'mobility',
})
REQUIRED_MESH = frozenset({
    'static_mesh', 'override_materials', 'body_instance', 'cast_shadow',
    'receives_decals', 'evaluate_world_position_offset',
    'world_position_offset_disable_distance', 'custom_primitive_data',
})


class DoorCopyError(RuntimeError):
    def __init__(self, message, proof):
        super().__init__(message)
        self.proof = proof


def component_map(actor):
    result = {}
    for component in actor.get_components_by_class(unreal.SceneComponent):
        name = component.get_name()
        if name in result:
            raise DoorCopyError('Duplicate component name: ' + name, {'passed': False})
        result[name] = component
    if not result:
        raise DoorCopyError('Actor has no scene components', {'passed': False})
    return result


def _delegate(value):
    return not isinstance(value, unreal.Object) and callable(getattr(value, 'is_bound', None))


def _value(value):
    if _delegate(value):
        return {'delegate_class': type(value).__name__, 'is_bound': bool(value.is_bound())}
    return native.value(value)


def _raw_properties(component):
    required = REQUIRED_SCENE | (REQUIRED_MESH if isinstance(component, unreal.StaticMeshComponent) else set())
    raw, unreadable = {}, {}
    for name in sorted(set(dir(component)) | set(required)):
        if name.startswith('_'):
            continue
        try:
            member = getattr(component, name, None)
            if inspect.ismethod(member) or inspect.isbuiltin(member) or inspect.isfunction(member) or isinstance(member, type):
                continue
        except Exception:
            pass
        try:
            raw[name] = component.get_editor_property(name)
        except Exception as error:
            unreadable[name] = str(error)
    missing = sorted(required - raw.keys())
    if missing:
        raise DoorCopyError('Required properties are unreadable', {
            'passed': False, 'component': component.get_path_name(),
            'missing_required_properties': missing, 'getter_failures': unreadable})
    return raw, unreadable


def component_snapshot(component, source_actor_path=None, target_actor_path=None):
    """JSON-safe observations; application always reads raw UObject/struct values."""
    raw, unreadable = _raw_properties(component)
    owner = component.get_owner()
    parent = component.get_attach_parent()
    row = dict(class_path=component.get_class().get_path_name(),
        parent_name=parent.get_name() if parent and parent.get_owner() == owner else None,
        external_parent=parent.get_path_name() if parent and parent.get_owner() != owner else None,
        socket=str(component.get_attach_socket_name()),
        properties={name: _value(value) for name, value in raw.items()},
        getter_failures=unreadable, world_transform=native.value(component.get_world_transform()))
    if isinstance(component, unreal.PrimitiveComponent):
        row['collision_enabled'] = str(component.get_collision_enabled())
        row['collision_profile'] = str(component.get_collision_profile_name())
    if isinstance(component, unreal.StaticMeshComponent):
        row['mesh'] = native.path_of(component.static_mesh)
        row['effective_materials'] = [native.path_of(component.get_material(i))
                                      for i in range(component.get_num_materials())]
    return _normalize(row, source_actor_path, target_actor_path) if source_actor_path else row


def door_snapshot(actor):
    components = component_map(actor)
    root = actor.get_editor_property('root_component')
    return dict(actor_path=actor.get_path_name(), actor_label=actor.get_actor_label(),
        root_name=root.get_name() if root else None,
        components={name: component_snapshot(component) for name, component in components.items()},
        geometry={key.split('::', 1)[1]: value
                  for key, value in capture_geometry_state([actor]).items()})


def _normalize(value, source_path, target_path):
    """Remap actual serialized UObject references, never arbitrary text/name data."""
    if isinstance(value, dict):
        result = {key: _normalize(item, source_path, target_path) for key, item in value.items()}
        if 'object' in result and isinstance(result['object'], str) and source_path and target_path:
            path = result['object']
            if path == source_path or path.startswith(source_path + '.'):
                result['object'] = target_path + path[len(source_path):]
        return result
    if isinstance(value, list):
        return [_normalize(item, source_path, target_path) for item in value]
    return value


def _contains_source_reference(value, source_path):
    if isinstance(value, dict):
        path = value.get('object')
        if isinstance(path, str) and (path == source_path or path.startswith(source_path + '.')):
            return True
        return any(_contains_source_reference(v, source_path) for v in value.values())
    if isinstance(value, list):
        return any(_contains_source_reference(v, source_path) for v in value)
    return False


def _remap_raw(value, source, target, targets):
    if isinstance(value, unreal.Object):
        if value == source:
            return target
        path = value.get_path_name()
        if path.startswith(source.get_path_name() + '.'):
            if value.get_name() in targets and value.get_outer() == source:
                return targets[value.get_name()]
            raise DoorCopyError('Unmapped source-owned UObject reference', {'passed': False, 'reference': path})
        return value
    if isinstance(value, (list, tuple, unreal.Array)):
        if _contains_source_reference(native.value(value), source.get_path_name()):
            return [_remap_raw(v, source, target, targets) for v in value]
    elif isinstance(value, unreal.StructBase):
        if _contains_source_reference(native.value(value), source.get_path_name()):
            raise DoorCopyError('Source-owned reference inside a struct requires explicit remapping', {'passed': False})
    return value


def _ordered_components(components):
    remaining, ordered = dict(components), []
    while remaining:
        ready = []
        for name, component in remaining.items():
            parent = component.get_attach_parent()
            if parent and parent.get_owner() != component.get_owner():
                raise DoorCopyError('External component attachment must be handled by caller',
                                    {'passed': False, 'component': name, 'parent': parent.get_path_name()})
            if not parent or parent.get_name() not in remaining:
                ready.append(name)
        if not ready:
            raise DoorCopyError('Source attachment cycle', {'passed': False})
        for name in ready:
            ordered.append(name)
            del remaining[name]
    return ordered


def _deactivate_unused(component):
    if isinstance(component, unreal.StaticMeshComponent):
        component.set_static_mesh(None)
        component.set_editor_property('override_materials', [], notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    if isinstance(component, unreal.PrimitiveComponent):
        component.set_collision_profile_name('NoCollision')
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        component.set_editor_property('generate_overlap_events', False, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        component.set_editor_property('cast_shadow', False, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    component.set_editor_property('visible', False, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    component.set_editor_property('hidden_in_game', True, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    component.set_editor_property('auto_activate', False, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    component.set_component_tick_enabled(False)
    row = component_snapshot(component)
    if isinstance(component, unreal.StaticMeshComponent):
        assert component.static_mesh is None and component.get_num_materials() == 0
    if isinstance(component, unreal.PrimitiveComponent):
        assert component.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
    assert not component.get_editor_property('visible') and component.get_editor_property('hidden_in_game')
    assert not component.is_component_tick_enabled()
    return row


def _attachment_fact(component):
    """Keep failure evidence usable even if an edit reconstructed a component."""
    if component is None:
        return None
    result = {'valid': bool(unreal.SystemLibrary.is_valid(component))}
    for key, getter in (
        ('path', component.get_path_name), ('name', component.get_name),
        ('owner', lambda: native.path_of(component.get_owner())),
        ('parent', lambda: native.path_of(component.get_attach_parent())),
        ('socket', lambda: str(component.get_attach_socket_name())),
    ):
        try:
            result[key] = getter()
        except Exception as error:
            result[key + '_error'] = str(error)
    return result


def _match_attachment(name, src, dst, target_actor, target, operations):
    """Match actual parent/socket; the API return bool alone is not evidence."""
    parent = src.get_attach_parent()
    socket = src.get_attach_socket_name()
    desired_parent = target[parent.get_name()] if parent else None
    current = component_map(target_actor)
    facts = dict(component=name, source_component=_attachment_fact(src),
                 target_component=_attachment_fact(dst),
                 source_parent=_attachment_fact(parent),
                 desired_target_parent=_attachment_fact(desired_parent),
                 current_named_target_component=_attachment_fact(current.get(name)),
                 source_socket=str(socket))
    # Default editor notifications can reconstruct Blueprint components. All raw
    # writes here use NEVER, but still guard against replacement by other calls.
    # Never attach a stale
    # reference or silently continue against a replacement with uncopied values.
    if (not unreal.SystemLibrary.is_valid(dst) or current.get(name) != dst or
            (parent and (not unreal.SystemLibrary.is_valid(desired_parent) or
                         current.get(parent.get_name()) != desired_parent))):
        raise DoorCopyError('Target component was replaced or invalidated before attachment',
                            dict(passed=False, attachment=facts))
    before_parent, before_socket = dst.get_attach_parent(), dst.get_attach_socket_name()
    if before_parent == desired_parent and before_socket == socket:
        facts['action'] = 'already_matching_parent_and_socket'
    else:
        try:
            if desired_parent:
                rule = unreal.AttachmentRule.KEEP_RELATIVE
                result = dst.attach_to_component(desired_parent, socket, rule, rule, rule, False)
                facts.update(action='attach_keep_relative', api_return=_value(result))
            elif before_parent:
                rule = unreal.DetachmentRule.KEEP_RELATIVE
                dst.detach_from_component(rule, rule, rule, False)
                facts['action'] = 'detach_keep_relative'
            else:
                facts['action'] = 'no_parent_but_socket_differs'
        except Exception as error:
            facts.update(api_error=str(error), target_component_after=_attachment_fact(dst))
            raise DoorCopyError('Attachment API raised an exception',
                                dict(passed=False, attachment=facts)) from error
    facts['target_component_after'] = _attachment_fact(dst)
    if (not unreal.SystemLibrary.is_valid(dst) or dst.get_attach_parent() != desired_parent or
            dst.get_attach_socket_name() != socket):
        raise DoorCopyError('Actual target parent/socket does not match source',
                            dict(passed=False, attachment=facts))
    operations.append(facts)


def verify_configured_door(source_snapshot, target_actor):
    """Compare a prior JSON-safe source snapshot with an existing target actor."""
    current = door_snapshot(target_actor)
    source_path, target_path = source_snapshot['actor_path'], current['actor_path']
    differences = []
    if source_snapshot['root_name'] != current['root_name']:
        differences.append({'kind': 'root_name', 'expected': source_snapshot['root_name'], 'actual': current['root_name']})
    for name, original in source_snapshot['components'].items():
        observed = current['components'].get(name)
        if observed is None:
            differences.append({'component': name, 'kind': 'missing_component'})
            continue
        expected = _normalize(original, source_path, target_path)
        for key in ('class_path', 'parent_name', 'external_parent', 'socket', 'mesh',
                    'effective_materials', 'collision_enabled', 'collision_profile'):
            if expected.get(key) != observed.get(key):
                differences.append({'component': name, 'kind': key, 'expected': expected.get(key), 'actual': observed.get(key)})
        for prop, value in expected['properties'].items():
            if prop in IDENTITY_PROPERTIES:
                continue
            if observed['properties'].get(prop) != value:
                differences.append({'component': name, 'kind': 'property', 'property': prop,
                                    'expected': value, 'actual': observed['properties'].get(prop)})
        try:
            compare_world_transform(expected['world_transform'], observed['world_transform'])
        except Exception as error:
            differences.append({'component': name, 'kind': 'world_transform', 'error': str(error),
                                'expected': expected['world_transform'], 'actual': observed['world_transform']})
    inactive = sorted(set(current['components']) - set(source_snapshot['components']))
    for name in inactive:
        component = component_map(target_actor)[name]
        row = current['components'][name]
        passed = not row['properties']['visible'] and row['properties']['hidden_in_game']
        if isinstance(component, unreal.StaticMeshComponent):
            passed &= component.static_mesh is None and component.get_num_materials() == 0
        if isinstance(component, unreal.PrimitiveComponent):
            passed &= component.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
        passed &= not component.is_component_tick_enabled()
        if not passed:
            differences.append({'component': name, 'kind': 'unused_branch_not_inactive'})
    return dict(passed=not differences, source_snapshot=source_snapshot, current_snapshot=current,
                differences=differences, inactive_union_component_names=inactive,
                excluded_identity_properties=sorted(IDENTITY_PROPERTIES),
                world_translation_scale_tolerance=1e-6, world_quaternion_tolerance=1e-7)


def configure_door(source_actor, target_actor):
    """Copy raw component values into a NEW target actor; fail on final differences.

    Actor label/folder/tags/hidden/collision, actor renaming, external actor
    attachments and hard reference remapping are exclusively the caller's work.
    OpeningRoot's relative transform already is the saved actor/world pose.
    """
    source, target = component_map(source_actor), component_map(target_actor)
    if not set(source).issubset(target):
        raise DoorCopyError('Target union omits source components',
                            {'passed': False, 'missing': sorted(set(source) - set(target))})
    for name in source:
        if source[name].get_class() != target[name].get_class():
            raise DoorCopyError('Component class mismatch', {'passed': False, 'component': name})
    baseline = door_snapshot(source_actor)
    raw = {name: _raw_properties(component)[0] for name, component in source.items()}
    setter_failures, operations, attachment_operations = [], [], []
    for name in sorted(set(target) - set(source)):
        _deactivate_unused(target[name])
    for name in _ordered_components(source):
        src, dst, values = source[name], target[name], raw[name]
        if isinstance(src, unreal.StaticMeshComponent):
            dst.set_static_mesh(src.static_mesh)
        for prop, value in values.items():
            if prop in IDENTITY_PROPERTIES or prop in TRANSFORM_PROPERTIES or prop == 'body_instance':
                continue
            if _delegate(value):
                if value.is_bound() or dst.get_editor_property(prop).is_bound():
                    raise DoorCopyError('Bound component delegate cannot be copied as static door art',
                                        {'passed': False, 'component': name, 'property': prop})
                operations.append({'component': name, 'property': prop, 'action': 'both_delegates_verified_unbound'})
                continue
            try:
                dst.set_editor_property(prop, _remap_raw(value, source_actor, target_actor, target),
                                        notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
            except Exception as error:
                setter_failures.append({'component': name, 'property': prop, 'error': str(error)})
        if isinstance(src, unreal.PrimitiveComponent):
            dst.set_collision_profile_name(src.get_collision_profile_name())
            # FBodyInstance WithCopy=false: property copying does not copy the
            # native PhysicsActor/OwnerComponent handles. Compare all reflected
            # BodyInstance fields, not just the collision profile string.
            try:
                dst.set_editor_property('body_instance', src.get_editor_property('body_instance'),
                                        notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
            except Exception as error:
                setter_failures.append({'component': name, 'property': 'body_instance', 'error': str(error)})
            dst.set_collision_enabled(src.get_collision_enabled())
        dst.set_mobility(values['mobility'])
        _match_attachment(name, src, dst, target_actor, target, attachment_operations)
        for prop in ('absolute_location', 'absolute_rotation', 'absolute_scale',
                     'relative_location', 'relative_rotation', 'relative_scale3d'):
            dst.set_editor_property(prop, values[prop], notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        # NEVER preserves the exact saved local values but skips the editor's
        # world-cache update. SetAbsolute always calls UpdateComponentToWorld,
        # even when these flags already match, without rewriting the raw local
        # FVector/FRotator/scale or reconstructing Blueprint components.
        dst.set_absolute(values['absolute_location'], values['absolute_rotation'], values['absolute_scale'])
    proof = verify_configured_door(baseline, target_actor)
    proof['setter_failures'] = setter_failures
    proof['verified_unbound_delegates'] = operations
    proof['attachment_operations'] = attachment_operations
    for failure in setter_failures:
        expected = _normalize(baseline['components'][failure['component']]['properties'][failure['property']],
                              baseline['actor_path'], target_actor.get_path_name())
        actual = proof['current_snapshot']['components'][failure['component']]['properties'].get(failure['property'])
        failure['final_value_matches_source'] = expected == actual
    proof['source_actor_unchanged'] = door_snapshot(source_actor) == baseline
    if not proof['source_actor_unchanged']:
        proof['passed'] = False
        proof['differences'].append({'kind': 'source_actor_mutated'})
    if not proof['passed']:
        raise DoorCopyError('Door component preservation failed', proof)
    return proof
