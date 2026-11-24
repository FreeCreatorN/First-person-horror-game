"""Assemble six planning categories and eleven independently usable meshes."""
import math
import unreal
from freezer_manifest import BLUEPRINT,DOORS,GROUPS,PARTS,PLANNING,PREFIX

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

def xyz(value):return [float(value.x),float(value.y),float(value.z)]
def near(a,b):return len(a)==len(b) and all(abs(x-y)<.003 for x,y in zip(a,b))

def closed_positions(doors,rows):
    result={}
    for part in PARTS:
        row=rows[PREFIX+part]
        pivot=row.get('pivot_m',[0,0,0])
        result[part]=list(map(float,row.get('closed_ue_cm',[100*pivot[0],-100*pivot[1],100*pivot[2]])))
    for key,part in DOORS.items():result[part]=list(map(float,doors[key]['closed_ue_cm']))
    assert all(len(v)==3 and all(math.isfinite(x) for x in v) for v in result.values())
    return result

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
    for group in GROUPS:
        obj=add(bp,subsystem,library,group,unreal.SceneComponent,'DefaultSceneRoot');configure(obj)
        obj.set_editor_property('component_tags',['FreezerPlanningCategory',PLANNING[group]])
    points=closed_positions(doors,rows)
    for part in PARTS:
        parent=next((group for group,children in GROUPS.items() if part in children),'DefaultSceneRoot')
        obj=add(bp,subsystem,library,part,unreal.StaticMeshComponent,parent)
        obj.set_static_mesh(meshes[PREFIX+part]);assert obj.get_editor_property('static_mesh')==meshes[PREFIX+part]
        configure(obj,points[part]);obj.set_collision_profile_name('BlockAllDynamic')
        category=parent if parent!='DefaultSceneRoot' else part
        obj.set_editor_property('component_tags',['FreezerPart',part,'PlanningCategory',PLANNING[category]])
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    try:status=str(bp.get_editor_property('status'))
    except Exception:status=None
    assert status is None or 'ERROR' not in status.upper(),status
    verify_blueprint(bp,meshes,doors,rows)
    return bp

def verify_blueprint(bp,meshes,doors,rows):
    subsystem,library=services();current=components(bp,subsystem,library)
    assert set(current)=={'DefaultSceneRoot',*PARTS,*GROUPS},sorted(current)
    assert sum(isinstance(obj,unreal.StaticMeshComponent) for handle,obj in current.values())==11
    direct={name for name,(handle,obj) in current.items() if name!='DefaultSceneRoot' and parent_name(handle,library)=='DefaultSceneRoot'}
    assert direct==set(PLANNING),(direct,set(PLANNING))
    points=closed_positions(doors,rows);result={}
    for group,children in GROUPS.items():
        handle,obj=current[group];assert not isinstance(obj,unreal.StaticMeshComponent)
        assert near(xyz(obj.get_editor_property('relative_location')),[0,0,0])
        assert near(xyz(obj.get_editor_property('RelativeScale3D')),[1,1,1])
        rotation=obj.get_editor_property('relative_rotation');assert near([rotation.pitch,rotation.yaw,rotation.roll],[0,0,0])
        assert {name for name,(h,_) in current.items() if parent_name(h,library)==group}==set(children)
    for part in PARTS:
        handle,obj=current[part]
        parent=next((g for g,children in GROUPS.items() if part in children),'DefaultSceneRoot')
        assert parent_name(handle,library)==parent,(part,parent_name(handle,library),parent)
        assert obj.get_editor_property('static_mesh')==meshes[PREFIX+part]
        assert obj.get_editor_property('mobility')==unreal.ComponentMobility.MOVABLE
        assert str(obj.get_collision_profile_name())=='BlockAllDynamic'
        assert near(xyz(obj.get_editor_property('relative_location')),points[part])
        assert near(xyz(obj.get_editor_property('RelativeScale3D')),[1,1,1])
        record={'mesh':meshes[PREFIX+part].get_path_name(),'parent':parent,'relative_location_cm':points[part],
            'movable':True,'collision':'BlockAllDynamic'}
        for key,name in DOORS.items():
            if name==part:
                travel=float(doors[key]['travel_cm']);record.update(travel_cm=travel,
                    open_ue_cm=[points[part][0]+travel,*points[part][1:]])
        result[part]=record
    assert bp.generated_class()
    return {'asset':bp.get_path_name(),'components':result,'planning_categories':PLANNING,
        'planning_category_count':6,'static_mesh_count':11,'groups':GROUPS,
        'sliding_axis':'local X','blueprint_ready':True,'interaction_events_installed':False}
