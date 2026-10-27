"""Independent copies of hotel door Blueprints with mirrored rear handles.

Importing this module does not create assets or change a level.  The caller owns
Actor replacement and instance preservation.  Existing source Blueprints and
their meshes are read only; only newly duplicated Blueprints are compiled/saved.
"""
import hashlib
from pathlib import Path

import unreal


_HOTEL_ROOT = '/Game/CodexGenerated/Hotel/'
_RECIPE = 'HotelDualHandleMirrorLeafCentreV2'
_SLOTS = (
    ('Handle', 'DoorLeaf', 'DoorHinge', 'RearHandle'),
    ('LeftHandle', 'LeftLeaf', 'LeftSlider', 'RearLeftHandle'),
    ('RightHandle', 'RightLeaf', 'RightSlider', 'RearRightHandle'),
)


def _templates(subsystem, blueprint):
    """Use SCS handles, because template attachment pointers may be unset."""
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    result = {}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        data = library.get_data(handle)
        if not library.is_scene_component(data):
            continue
        component = library.get_object_for_blueprint(data, blueprint)
        if component is not None:
            name = str(library.get_variable_name(data))
            if name in result:
                previous = result[name][1]
                previous_path = previous.get_path_name()
                current_path = component.get_path_name()
                if previous_path == current_path:
                    # Gathering can expose one SCS template through more than
                    # one handle. Only an identical UObject path is an alias;
                    # retain the first handle and never hide two real objects.
                    unreal.log('HOTEL_REAR_HANDLE_SCS_ALIAS ' + repr(dict(
                        blueprint=blueprint.get_path_name(), variable=name,
                        object_path=current_path)))
                    continue
                raise AssertionError(dict(
                    error='Distinct SCS templates share one variable name',
                    blueprint=blueprint.get_path_name(), variable=name,
                    first_object_path=previous_path,
                    first_class_path=previous.get_class().get_path_name(),
                    duplicate_object_path=current_path,
                    duplicate_class_path=component.get_class().get_path_name()))
            result[name] = (handle, component)
    return result


def _asset_file(asset_path):
    assert asset_path.startswith('/Game/'), asset_path
    content = Path(unreal.Paths.project_content_dir()).resolve()
    return content / (asset_path[len('/Game/'):] + '.uasset')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(asset_path):
    # Accept either package paths or the corresponding object paths.
    value = str(asset_path).split('.')[0].rstrip('/')
    assert value.startswith(_HOTEL_ROOT), value
    return value


def _set(component, name, value):
    # Editor notifications can rerun a Blueprint construction script. That
    # would discard the original instance overrides restored by the caller.
    component.set_editor_property(
        name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def _disable(component):
    component.set_static_mesh(None)
    _set(component, 'override_materials', [])
    component.set_collision_profile_name('NoCollision')
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    _set(component, 'generate_overlap_events', False)
    _set(component, 'visible', False)
    _set(component, 'hidden_in_game', True)


def _active_slots(components):
    swing = bool(components.get('DoorLeaf') and components['DoorLeaf'].static_mesh)
    if not swing:
        assert all(components.get(name) and components[name].static_mesh
                   for name in ('LeftLeaf', 'RightLeaf')), 'No active door-leaf pair'
    return swing, {'Handle'} if swing else {'LeftHandle', 'RightHandle'}


def _mirror(original, leaf, rear):
    """Configure one component without querying SCS-template attachments."""
    assert isinstance(original, unreal.StaticMeshComponent) and original.static_mesh
    assert original.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
    assert not any(original.get_editor_property(name) for name in
                   ('absolute_location', 'absolute_rotation', 'absolute_scale'))
    rotation = original.get_editor_property('relative_rotation')
    assert all(abs(value) < 1.e-6 for value in (rotation.pitch, rotation.yaw, rotation.roll))
    location = original.get_editor_property('relative_location')
    leaf_location = leaf.get_editor_property('relative_location')
    scale = original.get_editor_property('relative_scale3d')
    assert abs(scale.y) > 1.e-9
    rear.set_static_mesh(original.static_mesh)
    _set(rear, 'override_materials', list(original.get_editor_property('override_materials')))
    _set(rear, 'mobility', original.get_editor_property('mobility'))
    _set(rear, 'absolute_location', False)
    _set(rear, 'absolute_rotation', False)
    _set(rear, 'absolute_scale', False)
    _set(rear, 'relative_location', unreal.Vector(location.x, 2. * leaf_location.y - location.y, location.z))
    _set(rear, 'relative_rotation', rotation)
    _set(rear, 'relative_scale3d', unreal.Vector(scale.x, -scale.y, scale.z))
    rear.set_collision_profile_name('NoCollision')
    rear.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    _set(rear, 'generate_overlap_events', False)
    for name in ('visible', 'hidden_in_game', 'cast_shadow', 'receives_decals'):
        _set(rear, name, original.get_editor_property(name))
    # Flush the transforms after NEVER writes. This updates the new component
    # without a Blueprint reconstruction or a change to its original parent.
    rear.set_absolute(False, False, False)
    return _assert_mirrored(original, leaf, rear)


def _assert_mirrored(original, leaf, rear):
    location = original.get_editor_property('relative_location')
    leaf_location = leaf.get_editor_property('relative_location')
    scale = original.get_editor_property('relative_scale3d')
    actual = rear.get_editor_property('relative_location')
    actual_scale = rear.get_editor_property('relative_scale3d')
    assert rear.static_mesh == original.static_mesh
    assert abs(actual.x-location.x) < 1.e-6 and abs(actual.z-location.z) < 1.e-6
    assert abs(actual.y+location.y-2.*leaf_location.y) < 1.e-6
    assert all(abs(a-b) < 1.e-6 for a, b in zip(
        (actual_scale.x, actual_scale.y, actual_scale.z), (scale.x, -scale.y, scale.z)))
    assert rear.get_editor_property('relative_rotation') == original.get_editor_property('relative_rotation')
    assert rear.get_num_materials() == original.get_num_materials()
    assert all(rear.get_material(i) == original.get_material(i)
               for i in range(original.get_num_materials()))
    assert rear.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
    for name in ('visible', 'hidden_in_game', 'cast_shadow', 'receives_decals', 'mobility'):
        assert rear.get_editor_property(name) == original.get_editor_property(name), name
    return dict(mesh=original.static_mesh.get_path_name(),
                original_location=[location.x, location.y, location.z],
                rear_location=[actual.x, actual.y, actual.z],
                leaf_centre_y=leaf_location.y,
                rear_scale=[actual_scale.x, actual_scale.y, actual_scale.z],
                collision='NoCollision', material_slots=rear.get_num_materials())


def create_revised_blueprints(source_paths, dest_root):
    """Duplicate source BPs once, add working rear handles, then save.

    ``source_paths`` is an iterable of package/object paths under the assistant
    Hotel directory. ``dest_root`` must be a new, independent directory beneath
    that directory. Existing destinations are refused, never updated/reused.

    Return ``{source_package: destination_package}``.  Destination names are
    ``<source_BP_name>_DualHandle``.  A mixed swing/slider source receives every
    available rear slot. The active default leaf type receives mirrored rear
    handles, and unused slots stay empty. configure_back_handles selects the
    active slots again on each placed instance. No source BP is compiled/saved.
    """
    assets = unreal.EditorAssetLibrary
    dest_root = _path(dest_root)
    sources = sorted({_path(value) for value in source_paths})
    assert sources, 'No source hotel door Blueprints provided'
    mapping = {}
    source_assets = {}
    source_hashes = {}
    for source in sources:
        name = source.rsplit('/', 1)[-1]
        assert name.startswith('BP_Hotel_Door'), source
        destination = dest_root + '/' + name + '_DualHandle'
        assert destination != source and not assets.does_asset_exist(destination), destination
        assert not _asset_file(destination).exists(), destination
        blueprint = unreal.load_asset(source)
        assert isinstance(blueprint, unreal.Blueprint), source
        source_assets[source] = blueprint
        source_hashes[source] = _sha(_asset_file(source))
        mapping[source] = destination
    # Resolve and validate all inputs before creating the first destination.
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    for source, blueprint in source_assets.items():
        templates = _templates(subsystem, blueprint)
        assert 'OpeningRoot' in templates, source
        assert any(parent in templates for _, _, parent, _ in _SLOTS), source
        assert not any(rear in templates for _, _, _, rear in _SLOTS), source
        for front, leaf, parent, _ in _SLOTS:
            if parent in templates:
                assert front in templates and leaf in templates, (source, parent)
    assets.make_directory(dest_root)
    for source, destination in mapping.items():
        blueprint = assets.duplicate_asset(source, destination)
        assert isinstance(blueprint, unreal.Blueprint), destination
        assert blueprint.get_path_name().split('.')[0] == destination
        templates = _templates(subsystem, blueprint)
        for front, leaf, parent, rear in _SLOTS:
            if parent not in templates:
                continue
            handle, reason = subsystem.add_new_subobject(unreal.AddNewSubobjectParams(
                parent_handle=templates[parent][0],
                new_class=unreal.StaticMeshComponent,
                blueprint_context=blueprint,
                conform_transform_to_parent=False))
            assert library.is_handle_valid(handle) and not str(reason), (rear, str(reason))
            assert subsystem.rename_subobject(handle, rear), rear
            assert subsystem.attach_subobject(templates[parent][0], handle), (rear, parent)
            # Re-gather by SCS variable name after rename/attachment. Do not ask
            # component templates for get_attach_parent(), which is unreliable.
            templates = _templates(subsystem, blueprint)
            component = templates[rear][1]
            _set(component, 'mobility', unreal.ComponentMobility.MOVABLE)
            _set(component, 'relative_location', unreal.Vector(0, 0, 0))
            _set(component, 'relative_rotation', unreal.Rotator(0, 0, 0))
            _set(component, 'relative_scale3d', unreal.Vector(1, 1, 1))
            _disable(component)
        default_components = {name: value[1] for name, value in templates.items()}
        _, active = _active_slots(default_components)
        for front, leaf, _, rear in _SLOTS:
            if front in active:
                assert rear in templates, (destination, rear)
                _mirror(templates[front][1], templates[leaf][1], templates[rear][1])
        assets.set_metadata_tag(blueprint, 'CodexHotelRevisionSource', source)
        assets.set_metadata_tag(blueprint, 'CodexHotelRevisionRecipe', _RECIPE)
        unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
        # Verify defaults survived compilation, including the rear-side mirror.
        templates = _templates(subsystem, blueprint)
        for front, leaf, parent, rear in _SLOTS:
            if parent in templates:
                assert rear in templates, (destination, rear)
                if front in active:
                    _assert_mirrored(templates[front][1], templates[leaf][1], templates[rear][1])
                else:
                    assert templates[rear][1].static_mesh is None, (destination, rear)
        assert assets.save_loaded_asset(blueprint, False), destination
        assert assets.load_blueprint_class(destination), destination
    assert all(_sha(_asset_file(source)) == value for source, value in source_hashes.items()), 'Source Blueprint file changed'
    return mapping


def configure_back_handles(actor):
    """Mirror each active handle across its own leaf centre in parent space.

    Call after restoring the original instance component overrides, and before
    saving the revised level. Existing leaves, original handles, hinge/slider
    poses and materials are never modified. Rear handles attach to the same
    moving parent as their originals. Return a JSON-serializable proof dict.

    The existing hotel handle meshes have zero local rotation and no absolute
    transform flags. The assertions intentionally reject a different geometry
    convention instead of guessing. The mirror keeps leaf centre Y=-5cm intact:
    original handle Y=-8cm becomes rear Y=-2cm with negative scale Y.
    """
    class_path = actor.get_class().get_path_name()
    assert class_path.startswith(_HOTEL_ROOT) and '_DualHandle.' in class_path, class_path
    components = {component.get_name(): component
                  for component in actor.get_components_by_class(unreal.SceneComponent)}
    swing, active = _active_slots(components)
    for _, _, _, rear in _SLOTS:
        if rear in components:
            _disable(components[rear])
    rows = []
    for front, leaf_name, parent_name, rear_name in _SLOTS:
        if front not in active:
            continue
        assert all(name in components for name in (front, leaf_name, parent_name, rear_name)), (actor.get_actor_label(), front)
        original, leaf = components[front], components[leaf_name]
        parent, rear = components[parent_name], components[rear_name]
        assert original.get_attach_parent() == parent and leaf.get_attach_parent() == parent, front
        assert rear.get_attach_parent() == parent, (rear_name, parent_name)
        proof = _mirror(original, leaf, rear)
        assert rear.get_attach_parent() == original.get_attach_parent()
        rows.append(dict(original=front, rear=rear_name, parent=parent_name,
                         **proof))
    assert len(rows) == (1 if swing else 2), actor.get_actor_label()
    return dict(passed=True, actor=actor.get_actor_label(),
                kind='swing' if swing else 'slider', rear_handles=rows)
