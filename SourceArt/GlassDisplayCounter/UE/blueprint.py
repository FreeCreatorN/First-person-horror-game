"""Assemble the three counter meshes as a Blueprint actor.

Uses Unreal Editor's reflected API. The companion authoring script emits UE's
native Blueprint clipboard format for the two sliding events.
"""

import math
from pathlib import Path

import unreal

from clipboard_nodes import write_sliding_nodes


BLUEPRINT_NAME = 'BP_GlassDisplayCounter'
BODY_NAME = 'CabinetBody'
DOOR_NAMES = {'left': 'GlassDoorLeft', 'right': 'GlassDoorRight'}
EVENT_NAMES = {'left': 'SetLeftGlassDoorOpen', 'right': 'SetRightGlassDoorOpen'}
MESH_NAMES = {
    BODY_NAME: 'SM_GlassDisplayCounter',
    'GlassDoorLeft': 'SM_GlassDisplayCounter_DoorLeft',
    'GlassDoorRight': 'SM_GlassDisplayCounter_DoorRight',
}
TRAVEL_SECONDS = 0.55


def _services():
    unreal.load_module('BlueprintEditorLibrary')
    unreal.load_module('SubobjectDataInterface')
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem), unreal.SubobjectDataBlueprintFunctionLibrary


def _components(bp, subsystem, data_library):
    result = {}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data = data_library.get_data(handle)
        component = data_library.get_object_for_blueprint(data, bp)
        if isinstance(component, unreal.SceneComponent):
            key = str(data_library.get_variable_name(data))
            result[key] = (handle, component)
    return result


def door_travel_points(specs):
    points = {}
    for side in DOOR_NAMES:
        spec = specs[side]
        closed = [float(value) for value in spec['closed_ue_cm']]
        travel = float(spec['travel_cm'])
        assert len(closed) == 3 and all(math.isfinite(value) for value in closed)
        assert math.isfinite(travel) and (travel > 0 if side == 'left' else travel < 0)
        opened = [closed[0] + travel, closed[1], closed[2]]
        points[side] = {'closed_ue_cm': closed, 'open_ue_cm': opened, 'travel_cm': travel}
    assert points['left']['closed_ue_cm'][0] < points['right']['closed_ue_cm'][0]
    assert abs(points['left']['closed_ue_cm'][1] - points['right']['closed_ue_cm'][1]) >= 0.8
    return points


def build_blueprint(asset_tools, target, meshes, door_specs):
    """Return the prepared unsaved Blueprint to the caller's save transaction."""
    travel = door_travel_points(door_specs)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', unreal.Actor)
    bp = asset_tools.create_asset(BLUEPRINT_NAME, target, unreal.Blueprint, factory)
    assert isinstance(bp, unreal.Blueprint), 'Could not create the display counter Blueprint'

    subsystem, data_library = _services()
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    components = _components(bp, subsystem, data_library)
    _, root_component = components['DefaultSceneRoot']
    assert isinstance(root_component, unreal.SceneComponent)
    root_component.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    for component_name in MESH_NAMES:
        root_handle, _ = _components(bp, subsystem, data_library)['DefaultSceneRoot']
        params = unreal.AddNewSubobjectParams()
        params.set_editor_property('parent_handle', root_handle)
        params.set_editor_property('new_class', unreal.StaticMeshComponent)
        params.set_editor_property('blueprint_context', bp)
        handle, reason = subsystem.add_new_subobject(params)
        assert data_library.is_handle_valid(handle), str(reason)
        assert subsystem.rename_subobject(handle, component_name), component_name

    components = _components(bp, subsystem, data_library)
    for name, mesh_name in MESH_NAMES.items():
        component = components[name][1]
        assert isinstance(component, unreal.StaticMeshComponent)
        mesh = meshes[mesh_name]
        assert component.set_static_mesh(mesh), mesh_name
        component.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
        component.set_collision_profile_name('BlockAllDynamic')
        component.set_editor_property('relative_rotation', unreal.Rotator(0.0, 0.0, 0.0))
        component.set_editor_property('RelativeScale3D', unreal.Vector(1.0, 1.0, 1.0))
        location = [0.0, 0.0, 0.0]
        tags = ['DisplayCounterBody']
        for side, door in DOOR_NAMES.items():
            if name == door:
                location = travel[side]['closed_ue_cm']
                tags = ['DisplayCounterGlassDoor', 'DisplayCounterGlassDoor_' + side.title()]
        component.set_editor_property('relative_location', unreal.Vector(*location))
        component.set_editor_property('component_tags', tags)

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    verify_blueprint(bp, meshes, door_specs)
    write_sliding_nodes(Path(__file__).resolve().parent, travel, DOOR_NAMES, EVENT_NAMES, TRAVEL_SECONDS)
    return bp


def _xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def _near(actual, expected):
    return all(abs(a-b) <= .003 for a, b in zip(actual, expected))


def compiled_events(bp):
    generated = bp.generated_class()
    assert generated, bp.get_path_name()
    return {side: bool(unreal.find_object(generated, name)) for side, name in EVENT_NAMES.items()}


def verify_blueprint(bp, meshes, door_specs):
    """Read component defaults and event presence without changing the asset."""
    travel = door_travel_points(door_specs)
    subsystem, data_library = _services()
    components = _components(bp, subsystem, data_library)
    root_handle = components['DefaultSceneRoot'][0]
    assert bp.generated_class(), bp.get_path_name()
    assert sum(isinstance(value[1], unreal.StaticMeshComponent) for value in components.values()) == 3
    named = {}
    for name, mesh_name in MESH_NAMES.items():
        handle, component = components[name]
        assert isinstance(component, unreal.StaticMeshComponent)
        data = data_library.get_data(handle)
        assert data_library.is_attached_to(data, root_handle), name
        assert component.get_editor_property('static_mesh') == meshes[mesh_name], name
        assert component.get_editor_property('mobility') == unreal.ComponentMobility.MOVABLE, name
        collision = str(component.get_collision_profile_name())
        assert collision == 'BlockAllDynamic', (name, collision)
        assert _near(_xyz(component.get_editor_property('RelativeScale3D')), [1.0, 1.0, 1.0]), name
        location = _xyz(component.get_editor_property('relative_location'))
        record = {'mesh': meshes[mesh_name].get_path_name(), 'movable': True, 'collision': collision,
                  'relative_location_cm': location}
        expected = [0.0, 0.0, 0.0]
        for side, door in DOOR_NAMES.items():
            if door == name:
                record.update(travel[side])
                expected = travel[side]['closed_ue_cm']
        assert _near(location, expected), (name, location, expected)
        named[name] = record
    return {'asset': bp.get_path_name(), 'components': named,
            'sliding_axis': 'local X', 'compiled_sliding_events': compiled_events(bp)}
