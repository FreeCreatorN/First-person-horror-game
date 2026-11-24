"""Ready-assembled sofa actors with independently movable mesh components."""
import unreal
import sofa_manifest as C


def services():
    unreal.load_module('BlueprintEditorLibrary')
    unreal.load_module('SubobjectDataInterface')
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem), unreal.SubobjectDataBlueprintFunctionLibrary


def components(bp, subsystem, library):
    result = {}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data = library.get_data(handle)
        obj = library.get_object_for_blueprint(data, bp)
        if isinstance(obj, unreal.SceneComponent):
            result[str(library.get_variable_name(data))] = (handle, obj)
    return result


def parent_name(handle, library):
    parent = library.get_parent_handle(library.get_data(handle))
    return str(library.get_variable_name(library.get_data(parent))) if library.is_handle_valid(parent) else None


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def near(a, b):
    return len(a) == len(b) and all(abs(x-y) < .003 for x, y in zip(a, b))


def configure(obj, position=(0, 0, 0)):
    obj.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    obj.set_editor_property('relative_location', unreal.Vector(*position))
    obj.set_editor_property('relative_rotation', unreal.Rotator())
    obj.set_editor_property('RelativeScale3D', unreal.Vector(1, 1, 1))


def component_name(mesh_name):
    return mesh_name.removeprefix(C.PREFIX)


def build_blueprint(tools, name, parts, meshes, rows):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', unreal.Actor)
    bp = tools.create_asset(name, C.TARGET, unreal.Blueprint, factory)
    assert isinstance(bp, unreal.Blueprint)
    subsystem, library = services()
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    configure(components(bp, subsystem, library)['DefaultSceneRoot'][1])
    for mesh_name in parts:
        part = component_name(mesh_name)
        params = unreal.AddNewSubobjectParams()
        for key, value in dict(parent_handle=components(bp, subsystem, library)['DefaultSceneRoot'][0],
                               new_class=unreal.StaticMeshComponent, blueprint_context=bp,
                               conform_transform_to_parent=False).items():
            params.set_editor_property(key, value)
        handle, reason = subsystem.add_new_subobject(params)
        assert library.is_handle_valid(handle), str(reason)
        assert subsystem.rename_subobject(handle, part), part
        obj = components(bp, subsystem, library)[part][1]
        obj.set_static_mesh(meshes[mesh_name])
        configure(obj, C.ue_position(rows[mesh_name]['pivot_m']))
        obj.set_collision_profile_name('BlockAllDynamic')
        obj.set_editor_property('component_tags', ['SofaPart', part])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    try:
        status = str(bp.get_editor_property('status'))
    except Exception:
        status = None
    assert status is None or 'ERROR' not in status.upper(), status
    verify_blueprint(bp, parts, meshes, rows)
    return bp


def verify_blueprint(bp, parts, meshes, rows):
    subsystem, library = services()
    current = components(bp, subsystem, library)
    assert set(current) == {'DefaultSceneRoot', *(component_name(name) for name in parts)}, sorted(current)
    root = current['DefaultSceneRoot'][1]
    assert root.get_editor_property('mobility') == unreal.ComponentMobility.MOVABLE
    assert near(xyz(root.get_editor_property('relative_location')), [0, 0, 0])
    result = {}
    for mesh_name in parts:
        part = component_name(mesh_name)
        handle, obj = current[part]
        position = C.ue_position(rows[mesh_name]['pivot_m'])
        assert isinstance(obj, unreal.StaticMeshComponent)
        assert parent_name(handle, library) == 'DefaultSceneRoot'
        assert obj.get_editor_property('static_mesh') == meshes[mesh_name]
        assert obj.get_editor_property('mobility') == unreal.ComponentMobility.MOVABLE
        assert str(obj.get_collision_profile_name()) == 'BlockAllDynamic'
        assert near(xyz(obj.get_editor_property('relative_location')), position)
        assert near(xyz(obj.get_editor_property('RelativeScale3D')), [1, 1, 1])
        rotation = obj.get_editor_property('relative_rotation')
        assert near([rotation.pitch, rotation.yaw, rotation.roll], [0, 0, 0])
        result[part] = dict(mesh=meshes[mesh_name].get_path_name(), parent='DefaultSceneRoot',
                            relative_location_cm=position, movable=True, collision='BlockAllDynamic')
    assert bp.generated_class()
    return dict(asset=bp.get_path_name(), components=result, static_mesh_count=len(result),
                blueprint_ready=True, interaction_events_installed=False, animation_installed=False)
