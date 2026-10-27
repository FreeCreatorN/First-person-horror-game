import sys,json,math,hashlib,re,itertools
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
W=R/'Saved/CodexOutputs/OldTownHotelDoorClosure_20261019';base.W=W;base.TAG='DoorClosure_DoNotExcludeAnyExistingActor'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
ASSET='/Game/CodexGenerated/Hotel/Meshes/DoorClosure'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,v):native.write(W/n,v)
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def components(a):return {c.get_name():c for c in a.get_components_by_class(unreal.SceneComponent)}
def export_text(obj,name):
    p=W/'BlueprintNativeAfter'/(name+'.t3d');t,proof=native.native_text_export(obj,p);assert proof['passed'];return t
def graph_sections(t):
    from HotelDoorClosurePreservation import _parse_native,_render
    names=('EventGraph','UserConstructionScript');out={}
    for n in names:
        match=re.search(r'(?ms)^   Begin Object Name="'+n+r'"[^\n]*\n.*?^   End Object\s*$',t)
        assert match,n;graph=_parse_native(match.group(0))
        out[n]=dict(nodes=sorted(_render(v) for v in graph['body'] if isinstance(v,dict)),properties=[v for v in graph['body'] if isinstance(v,str)])
    out['variables_and_interfaces']=[s for s in t.splitlines() if s.lstrip().startswith(('NewVariables','ImplementedInterfaces','ParentClass='))]
    return out
def snap(actors,phase):
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    return base.snapshot(actors,phase)
def root_box(c,root):
    low,high=c.get_local_bounds();wt=c.get_world_transform();rt=root.get_world_transform()
    corners=[]
    for v in itertools.product(*zip(native.value(low),native.value(high))):
        world=unreal.MathLibrary.transform_location(wt,unreal.Vector(*v));corners.append(native.value(unreal.MathLibrary.inverse_transform_location(rt,world)))
    return [[min(p[i] for p in corners) for i in range(3)],[max(p[i] for p in corners) for i in range(3)]]
def validate_closed(by,plan):
    """Exercise actual installed components, preserving every input hinge/slider pose."""
    proof=[]
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    for row in plan['doors']:
        cs=components(by[row['label']]);root=cs['OpeningRoot'];saved={}
        try:
            if row['kind']=='swing':
                c=cs['DoorHinge'];saved[c]=(native.value(c.get_editor_property('relative_location')),native.value(c.get_editor_property('relative_rotation')))
                c.set_relative_rotation(unreal.Rotator(0,0,0),False,True);leaves=['DoorLeaf'];blockers=['LeafCollision']
                moving=by[row['label']+'_MovingHinges'].static_mesh_component
                assert moving.get_attach_parent()==c,row['label']
                assert native.value(moving.get_editor_property('relative_location'))==[0,0,0]
                assert native.value(moving.get_editor_property('relative_rotation'))==[0,0,0]
                fixed=by[row['label']+'_FixedHinges'].static_mesh_component
                for z in (22.,row['height']/2,row['height']-22.):
                    pa=unreal.MathLibrary.transform_location(moving.get_world_transform(),unreal.Vector(0,0,z))
                    pb=unreal.MathLibrary.transform_location(fixed.get_world_transform(),unreal.Vector(row['hinge_side']*(row['width']/2-.5),row['depth']/2+3,z))
                    assert math.dist(native.value(pa),native.value(pb))<.000001,dict(door=row['label'],hinge_height=z)
            else:
                leaves=['LeftLeaf','RightLeaf'];blockers=['LeftLeafCollision','RightLeafCollision']
                for name in ('LeftSlider','RightSlider'):
                    c=cs[name];p=native.value(c.get_editor_property('relative_location'));saved[c]=(p,native.value(c.get_editor_property('relative_rotation')))
                    c.set_relative_location(unreal.Vector(0,p[1],p[2]),False,True)
            boxes={n:root_box(cs[n],root) for n in leaves+blockers}
            frame_front=root_box(cs['FrameLeft'],root)[1][1]
            for n in leaves:
                assert abs(boxes[n][1][1]-frame_front)<.025,dict(door=row['label'],component=n,box=boxes[n],frame_front=frame_front)
            for leaf,col in zip(leaves,blockers):
                assert all(abs(a-b)<.025 for va,vb in zip(boxes[leaf],boxes[col]) for a,b in zip(va,vb)),row['label']
            traces=[]
            for col in blockers:
                c=cs[col];mode=c.get_collision_enabled();profile=c.get_collision_profile_name()
                c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);c.set_collision_enabled(mode);c.set_collision_profile_name(profile)
                x=(boxes[col][0][0]+boxes[col][1][0])/2;z=min(100,row['height']/2)
                start=unreal.MathLibrary.transform_location(root.get_world_transform(),unreal.Vector(x,35,z))
                end=unreal.MathLibrary.transform_location(root.get_world_transform(),unreal.Vector(x,-25,z))
                hit=unreal.SystemLibrary.line_trace_single_for_objects(world,start,end,[unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],False,[],unreal.DrawDebugTrace.NONE)
                assert hit is not None and hit.to_tuple()[0] and hit.to_tuple()[10]==c,dict(door=row['label'],collider=col,hit=str(hit))
                traces.append(dict(component=col,closed_trace_blocks=True))
            wood_min=min(b[0][0] for n,b in boxes.items() if n in leaves);wood_max=max(b[1][0] for n,b in boxes.items() if n in leaves)
            assert abs(wood_min+row['width']/2)<.55 and abs(wood_max-row['width']/2)<.55
            stop=cs['DoorStops'];assert stop.static_mesh.get_path_name()==row['stop_mesh']
            assert stop.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
            assert stop.get_attach_parent()==root and stop.get_material(0)==cs['FrameLeft'].get_material(0)
            proof.append(dict(door=row['label'],kind=row['kind'],closed_leaf_boxes=boxes,frame_front_y=frame_front,
                front_flush=True,collider_matches_leaf=True,stop_mesh=row['stop_mesh'],closed_gap_masked_by_stops=True))
            proof[-1]['closed_collision_traces']=traces
            if row['kind']=='swing':proof[-1]['three_hinge_bearings_aligned_and_follow_leaf']=True
        finally:
            for c,(pos,rot) in saved.items():
                c.set_editor_property('relative_location',unreal.Vector(*pos),notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                c.set_editor_property('relative_rotation',unreal.Rotator(pitch=rot[0],yaw=rot[1],roll=rot[2]),notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                c.set_absolute(c.get_editor_property('absolute_location'),c.get_editor_property('absolute_rotation'),c.get_editor_property('absolute_scale'))
                assert native.value(c.get_editor_property('relative_location'))==pos and native.value(c.get_editor_property('relative_rotation'))==rot
    return dict(passed=True,tested_count=len(proof),doors=proof,all_saved_open_poses_restored=True)
