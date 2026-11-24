"""Door glass, frame, and handle share a hinge; nine logical planning categories."""
import unreal
from fridge_manifest import BLUEPRINT,PARTS,DOOR_PARTS,GROUPS,PLANNING,PREFIX,hinge_spec

def services():
    unreal.load_module('BlueprintEditorLibrary');unreal.load_module('SubobjectDataInterface')
    return unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem),unreal.SubobjectDataBlueprintFunctionLibrary
def components(bp,subsystem,library):
    result={}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data=library.get_data(handle);obj=library.get_object_for_blueprint(data,bp)
        if isinstance(obj,unreal.SceneComponent):result[str(library.get_variable_name(data))]=(handle,obj)
    return result
def parent_name(handle,library):
    parent=library.get_parent_handle(library.get_data(handle))
    return str(library.get_variable_name(library.get_data(parent))) if library.is_handle_valid(parent) else None
def xyz(v):return [float(v.x),float(v.y),float(v.z)]
def near(a,b):return len(a)==len(b) and all(abs(x-y)<.003 for x,y in zip(a,b))
def parent_for(part):return next((group for group,children in GROUPS.items() if part in children),'DefaultSceneRoot')
def category_for(part):return part if part in DOOR_PARTS else next((group for group,children in GROUPS.items() if part in children),part)
def positions(rows):
    points={}
    for part in PARTS:
        p=rows[PREFIX+part].get('pivot_m',[0,0,0])
        points[part]=[0,0,0] if part in DOOR_PARTS else [100*p[0],-100*p[1],100*p[2]]
    return points
def configure(obj,position=(0,0,0)):
    obj.set_editor_property('mobility',unreal.ComponentMobility.MOVABLE)
    obj.set_editor_property('relative_location',unreal.Vector(*position))
    obj.set_editor_property('relative_rotation',unreal.Rotator())
    obj.set_editor_property('RelativeScale3D',unreal.Vector(1,1,1))
def add(bp,subsystem,library,name,cls,parent):
    params=unreal.AddNewSubobjectParams()
    for key,value in {'parent_handle':components(bp,subsystem,library)[parent][0],
        'new_class':cls,'blueprint_context':bp,'conform_transform_to_parent':False}.items():params.set_editor_property(key,value)
    handle,reason=subsystem.add_new_subobject(params);assert library.is_handle_valid(handle),str(reason)
    assert subsystem.rename_subobject(handle,name),name
    return components(bp,subsystem,library)[name][1]
def build_blueprint(tools,target,meshes,doors,rows):
    factory=unreal.BlueprintFactory();factory.set_editor_property('parent_class',unreal.Actor)
    bp=tools.create_asset(BLUEPRINT,target,unreal.Blueprint,factory);assert isinstance(bp,unreal.Blueprint)
    subsystem,library=services();unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    configure(components(bp,subsystem,library)['DefaultSceneRoot'][1])
    hinge=hinge_spec(doors)
    for group in GROUPS:
        obj=add(bp,subsystem,library,group,unreal.SceneComponent,'DefaultSceneRoot')
        configure(obj,hinge['closed_ue_cm'] if group=='DoorHinge' else [0,0,0])
        obj.set_editor_property('component_tags',['BeverageFridgeGroup',group])
    points=positions(rows)
    for part in PARTS:
        obj=add(bp,subsystem,library,part,unreal.StaticMeshComponent,parent_for(part))
        obj.set_static_mesh(meshes[PREFIX+part]);assert obj.get_editor_property('static_mesh')==meshes[PREFIX+part]
        configure(obj,points[part]);obj.set_collision_profile_name('BlockAllDynamic')
        obj.set_editor_property('component_tags',['BeverageFridgePart',part,'PlanningCategory',PLANNING[category_for(part)]])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    try:status=str(bp.get_editor_property('status'))
    except Exception:status=None
    assert status is None or 'ERROR' not in status.upper(),status
    verify_blueprint(bp,meshes,doors,rows)
    return bp
def verify_blueprint(bp,meshes,doors,rows):
    subsystem,library=services();current=components(bp,subsystem,library)
    assert set(current)=={'DefaultSceneRoot',*PARTS,*GROUPS},sorted(current)
    assert sum(isinstance(obj,unreal.StaticMeshComponent) for handle,obj in current.values())==16
    direct={name for name,(handle,obj) in current.items() if name!='DefaultSceneRoot' and parent_name(handle,library)=='DefaultSceneRoot'}
    assert direct=={'TopLightbox','DoorHinge','Shelves','InnerLiner','OuterBody','VentGrille','BaseFeet'},direct
    hinge=hinge_spec(doors);points=positions(rows);result={}
    for group,children in GROUPS.items():
        handle,obj=current[group];assert not isinstance(obj,unreal.StaticMeshComponent)
        assert near(xyz(obj.get_editor_property('relative_location')),hinge['closed_ue_cm'] if group=='DoorHinge' else [0,0,0])
        assert near(xyz(obj.get_editor_property('RelativeScale3D')),[1,1,1])
        r=obj.get_editor_property('relative_rotation');assert near([r.pitch,r.yaw,r.roll],[0,0,0])
        assert {name for name,(h,_) in current.items() if parent_name(h,library)==group}==set(children)
    for part in PARTS:
        handle,obj=current[part];assert parent_name(handle,library)==parent_for(part)
        assert obj.get_editor_property('static_mesh')==meshes[PREFIX+part]
        assert obj.get_editor_property('mobility')==unreal.ComponentMobility.MOVABLE
        assert str(obj.get_collision_profile_name())=='BlockAllDynamic'
        assert near(xyz(obj.get_editor_property('relative_location')),points[part])
        assert near(xyz(obj.get_editor_property('RelativeScale3D')),[1,1,1])
        result[part]={'mesh':meshes[PREFIX+part].get_path_name(),'parent':parent_for(part),
            'relative_location_cm':points[part],'planning_category':PLANNING[category_for(part)],'movable':True,'collision':'BlockAllDynamic'}
    assert bp.generated_class()
    return {'asset':bp.get_path_name(),'components':result,'planning_categories':PLANNING,'planning_category_count':9,
        'static_mesh_count':16,'root_branch_count':7,'groups':GROUPS,'hinge':hinge,
        'door_local_closed_rotation_deg':[0,0,0],'door_local_open_rotation_deg':[0,hinge['open_yaw_deg'],0],
        'blueprint_ready':True,'interaction_events_installed':False,'light_components':0}
