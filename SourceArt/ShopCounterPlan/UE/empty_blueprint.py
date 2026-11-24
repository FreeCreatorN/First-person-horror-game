"""Migrate the existing Blueprint in place to the eight planning-sheet categories."""
import json
import unreal
from empty_manifest import BLUEPRINT, DOORS, GROUPS, PARTS, PLANNING, PREFIX
from blueprint import services, components, door_points, xyz, near

def direct_parent_name(handle, library):
    parent = library.get_parent_handle(library.get_data(handle))
    return str(library.get_variable_name(library.get_data(parent))) if library.is_handle_valid(parent) else None

def ensure_component(bp, subsystem, library, name, cls, parent):
    current = components(bp, subsystem, library)
    if name in current:
        handle, obj = current[name]
        assert isinstance(obj, cls), name
    else:
        params = unreal.AddNewSubobjectParams()
        for key, value in {'parent_handle': current[parent][0], 'new_class': cls, 'blueprint_context': bp,
                           'conform_transform_to_parent': False}.items():
            params.set_editor_property(key, value)
        handle, reason = subsystem.add_new_subobject(params)
        assert library.is_handle_valid(handle), str(reason)
        assert subsystem.rename_subobject(handle, name), name
        handle, obj = components(bp, subsystem, library)[name]
    if direct_parent_name(handle, library) != parent:
        assert subsystem.attach_subobject(components(bp, subsystem, library)[parent][0], handle), name
    return obj

def configure_scene(obj, position=(0,0,0)):
    obj.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    obj.set_editor_property('relative_location', unreal.Vector(*position))
    obj.set_editor_property('relative_rotation', unreal.Rotator())
    obj.set_editor_property('RelativeScale3D', unreal.Vector(1,1,1))

def update_blueprint(bp, meshes, specs):
    assert isinstance(bp, unreal.Blueprint) and bp.get_name() == BLUEPRINT
    subsystem, library = services()
    original_path = bp.get_path_name()
    before = components(bp, subsystem, library)
    allowed = {'DefaultSceneRoot', 'FixedGlass', *PARTS, *GROUPS}
    assert not set(before)-allowed, ('Unrecognized user components; do not discard', sorted(set(before)-allowed))
    assert 'DefaultSceneRoot' in before
    configure_scene(before['DefaultSceneRoot'][1])
    for group, children in GROUPS.items():
        obj = ensure_component(bp, subsystem, library, group, unreal.SceneComponent, 'DefaultSceneRoot')
        assert not isinstance(obj, unreal.StaticMeshComponent)
        configure_scene(obj)
        obj.set_editor_property('component_tags', ['PlanningSheetGroup', PLANNING[group]])
    travel = door_points(specs)
    for part in PARTS:
        parent = next((group for group, children in GROUPS.items() if part in children), 'DefaultSceneRoot')
        obj = ensure_component(bp, subsystem, library, part, unreal.StaticMeshComponent, parent)
        # SetStaticMesh returns false when the same mesh is already assigned.
        # In-place reimport deliberately preserves that UObject identity.
        obj.set_static_mesh(meshes[PREFIX+part])
        assert obj.get_editor_property('static_mesh') == meshes[PREFIX+part], part
        position = [0,0,0]
        for key, name in DOORS.items():
            if name == part:
                position = travel[key]['closed_ue_cm']
        configure_scene(obj, position)
        obj.set_collision_profile_name('BlockAllDynamic')
        tags = ['ShopCounterPart', part]
        if part in PLANNING:tags += ['PlanningSheetPart', PLANNING[part]]
        for key, name in DOORS.items():
            if name == part:tags += ['ShopCounterSlidingDoor', key]
        obj.set_editor_property('component_tags', tags)
    current = components(bp, subsystem, library)
    if 'FixedGlass' in current:
        # Remove only the retired combined-glass component, after both new parts exist.
        assert 'GlassTop' in current and 'GlassSurround' in current
        assert subsystem.delete_subobject(current['DefaultSceneRoot'][0], current['FixedGlass'][0], bp) == 1
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    assert bp.get_path_name() == original_path
    try:
        compile_status = str(bp.get_editor_property('status'))
    except Exception:
        compile_status = None
    assert compile_status is None or 'ERROR' not in compile_status.upper(), compile_status
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'CounterVersion', 'EmptyPlanningParts')
    unreal.EditorAssetLibrary.set_metadata_tag(bp, 'PlanningCategories', json.dumps(PLANNING, ensure_ascii=False))
    result = verify_blueprint(bp, meshes, specs)
    result['compile_status'] = compile_status
    return result

def verify_blueprint(bp, meshes, specs):
    travel = door_points(specs)
    subsystem, library = services()
    current = components(bp, subsystem, library)
    assert set(current) == {'DefaultSceneRoot', *PARTS, *GROUPS}, sorted(current)
    assert sum(isinstance(obj, unreal.StaticMeshComponent) for _, obj in current.values()) == 10
    direct_children = {name for name,(handle,obj) in current.items() if name!='DefaultSceneRoot'
                       and direct_parent_name(handle, library)=='DefaultSceneRoot'}
    assert direct_children == set(PLANNING), sorted(direct_children)
    result = {}
    for group, children in GROUPS.items():
        handle, obj = current[group]
        assert not isinstance(obj, unreal.StaticMeshComponent)
        assert near(xyz(obj.get_editor_property('relative_location')), [0,0,0])
        assert near(xyz(obj.get_editor_property('RelativeScale3D')), [1,1,1])
        rotation = obj.get_editor_property('relative_rotation')
        assert near([rotation.pitch,rotation.yaw,rotation.roll], [0,0,0])
        actual = {name for name,(h,_) in current.items() if direct_parent_name(h, library)==group}
        assert actual == set(children), (group, actual)
    for part in PARTS:
        handle, obj = current[part]
        parent = next((g for g, children in GROUPS.items() if part in children), 'DefaultSceneRoot')
        assert direct_parent_name(handle, library)==parent, part
        assert obj.get_editor_property('static_mesh') == meshes[PREFIX+part]
        assert obj.get_editor_property('mobility') == unreal.ComponentMobility.MOVABLE
        assert str(obj.get_collision_profile_name()) == 'BlockAllDynamic'
        assert near(xyz(obj.get_editor_property('RelativeScale3D')), [1,1,1])
        expected = [0,0,0]
        record = {'mesh': meshes[PREFIX+part].get_path_name(), 'parent': parent, 'movable': True, 'collision': 'BlockAllDynamic'}
        for key, name in DOORS.items():
            if name==part:
                expected=travel[key]['closed_ue_cm'];record.update(travel[key])
        location=xyz(obj.get_editor_property('relative_location'))
        assert near(location,expected),(part,location,expected)
        record['relative_location_cm']=location;result[part]=record
    assert bp.generated_class()
    return {'asset': bp.get_path_name(), 'components': result, 'groups': GROUPS,
            'planning_categories': PLANNING, 'planning_category_count':8, 'static_mesh_count':10,
            'sliding_axis':'local X', 'empty_counter':True, 'blueprint_ready':True, 'interaction_events_installed':False}
