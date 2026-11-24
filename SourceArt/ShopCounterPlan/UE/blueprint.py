"""Assemble nine independent counter parts. Interaction events are not authored."""
import math
import unreal
from counter_manifest import BLUEPRINT, DOORS, PARTS, PREFIX

def services():
    unreal.load_module('BlueprintEditorLibrary')
    unreal.load_module('SubobjectDataInterface')
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem), unreal.SubobjectDataBlueprintFunctionLibrary

def components(bp, subsystem, library):
    result = {}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data = library.get_data(handle)
        component = library.get_object_for_blueprint(data, bp)
        if isinstance(component, unreal.SceneComponent):
            result[str(library.get_variable_name(data))] = (handle, component)
    return result

def door_points(specs):
    points = {}
    for key in DOORS:
        spec = specs[key]
        closed = list(map(float, spec['closed_ue_cm']))
        travel = float(spec['travel_cm'])
        assert len(closed) == 3 and all(math.isfinite(value) for value in [*closed, travel])
        opened = [closed[0] + travel, closed[1], closed[2]]
        points[key] = {'closed_ue_cm': closed, 'open_ue_cm': opened, 'travel_cm': travel,
                       'component': DOORS[key], 'event_suggested': 'Set' + DOORS[key] + 'Open'}
    for material in ('wood', 'glass'):
        a, b = points[material + '_left'], points[material + '_right']
        assert a['closed_ue_cm'][0] < b['closed_ue_cm'][0]
        assert abs(a['closed_ue_cm'][1] - b['closed_ue_cm'][1]) >= .8
    return points

def build_blueprint(tools, target, meshes, specs):
    travel = door_points(specs)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', unreal.Actor)
    bp = tools.create_asset(BLUEPRINT, target, unreal.Blueprint, factory)
    assert isinstance(bp, unreal.Blueprint)
    subsystem, library = services()
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    root_handle, root = components(bp, subsystem, library)['DefaultSceneRoot']
    root.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    for part in PARTS:
        root_handle, _ = components(bp, subsystem, library)['DefaultSceneRoot']
        params = unreal.AddNewSubobjectParams()
        for key, value in {'parent_handle': root_handle, 'new_class': unreal.StaticMeshComponent,
                           'blueprint_context': bp}.items():
            params.set_editor_property(key, value)
        handle, reason = subsystem.add_new_subobject(params)
        assert library.is_handle_valid(handle), str(reason)
        assert subsystem.rename_subobject(handle, part), part
    created = components(bp, subsystem, library)
    for part in PARTS:
        component = created[part][1]
        assert component.set_static_mesh(meshes[PREFIX + part])
        component.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
        component.set_collision_profile_name('BlockAllDynamic')
        component.set_editor_property('relative_rotation', unreal.Rotator())
        component.set_editor_property('RelativeScale3D', unreal.Vector(1, 1, 1))
        location, tags = [0, 0, 0], ['ShopCounterPart', part]
        for key, name in DOORS.items():
            if part == name:
                location = travel[key]['closed_ue_cm']
                tags += ['ShopCounterSlidingDoor', key]
        component.set_editor_property('relative_location', unreal.Vector(*location))
        component.set_editor_property('component_tags', tags)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    verify_blueprint(bp, meshes, specs)
    return bp

def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]

def near(actual, expected):
    return all(abs(a-b) <= .003 for a,b in zip(actual, expected))

def verify_blueprint(bp, meshes, specs):
    travel = door_points(specs)
    subsystem, library = services()
    created = components(bp, subsystem, library)
    root_handle = created['DefaultSceneRoot'][0]
    assert bp.generated_class()
    assert sum(isinstance(row[1], unreal.StaticMeshComponent) for row in created.values()) == 9
    result = {}
    for part in PARTS:
        handle, component = created[part]
        assert library.is_attached_to(library.get_data(handle), root_handle)
        assert component.get_editor_property('static_mesh') == meshes[PREFIX + part]
        assert component.get_editor_property('mobility') == unreal.ComponentMobility.MOVABLE
        assert str(component.get_collision_profile_name()) == 'BlockAllDynamic'
        assert near(xyz(component.get_editor_property('RelativeScale3D')), [1, 1, 1])
        expected = [0, 0, 0]
        record = {'mesh': meshes[PREFIX + part].get_path_name(), 'movable': True, 'collision': 'BlockAllDynamic'}
        for key, name in DOORS.items():
            if name == part:
                expected = travel[key]['closed_ue_cm']
                record.update(travel[key])
        location = xyz(component.get_editor_property('relative_location'))
        assert near(location, expected), (part, location, expected)
        record['relative_location_cm'] = location
        result[part] = record
    return {'asset': bp.get_path_name(), 'components': result, 'sliding_axis': 'local X',
            'blueprint_ready': True, 'interaction_events_installed': False}
