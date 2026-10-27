"""Apply approved V4 to the current saved street, only after physical audit."""
import json, math, shutil, sys, traceback
from pathlib import Path
from copy import deepcopy
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state, shared_asset_hashes, sha
from PolishOldTownDetails import actor_bounds
from BuildOldTownOpeningBlueprints import create_blueprint
from OldTownOpeningSpecs import component
from AuditOldTownHotelV4 import audit, refresh
from ValidateEnterableStreet import validate_main_home

WORK=ROOT/'Saved/CodexOutputs/HotelRedesign_20261008_V4'
SOURCE=ROOT/'Saved/CodexOutputs/StreetRefinement_20261007'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
TAG='HotelRedesign_20261008_V4'
CUBE='/Engine/BasicShapes/Cube.Cube'
BP_ROOT='/Game/CodexGenerated/OldTown/Blueprints/Openings/'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,d):
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

def opening_specs(row,window=False,mats=None):
    """Dimensioned frame outside clear opening; independent movable panels."""
    w,h,depth=float(row['width']),float(row['height']),float(row.get('depth',20))
    rows=[component('OpeningRoot',None)]
    def box(name,parent,loc,size,mat,blocking=True,hidden=False):
        s=component(name,parent,CUBE,location=loc,scale=[v/100 for v in size],collision=blocking,hidden=hidden)
        s['material']=mats[mat].get_path_name()
        if parent=='OpeningRoot':s['mobility']='STATIC'
        rows.append(s)
    box('FrameLeft','OpeningRoot',[-w/2-2,0,h/2],[4,depth,h],'green')
    box('FrameRight','OpeningRoot',[w/2+2,0,h/2],[4,depth,h],'green')
    box('FrameTop','OpeningRoot',[0,0,h+2],[w+8,depth,4],'green')
    if window:
        box('FrameBottom','OpeningRoot',[0,0,-2],[w+8,depth,4],'green')
        for side,label in ((-1,'Left'),(1,'Right')):
            rows.append(component(label+'Hinge','OpeningRoot',location=[side*w/2,depth/2,0]))
            direction=-side
            box(label+'Sash',label+'Hinge',[direction*w/4,0,h/2],[w/2,3,h],'glass',False)
            box(label+'PaneCollision',label+'Hinge',[direction*w/4,0,h/2],[w/2,3,h],'dark',True,True)
            box(label+'UpperRail',label+'Hinge',[direction*w/4,0,h-2],[w/2,4,4],'green',False)
            box(label+'LowerRail',label+'Hinge',[direction*w/4,0,2],[w/2,4,4],'green',False)
            box(label+'MeetingRail',label+'Hinge',[direction*(w/2-2),0,h/2],[4,4,h],'green',False)
    elif row.get('kind','swing')=='slider':
        for side,label in ((-1,'Left'),(1,'Right')):
            offset=0. if row.get('locked') else side*(w/2+3)
            rows.append(component(label+'Slider','OpeningRoot',location=[offset,depth/2+3,0]))
            box(label+'Leaf',label+'Slider',[side*w/4,0,h/2],[w/2,4,h],'dark' if row.get('locked') else 'green',False)
            box(label+'LeafCollision',label+'Slider',[side*w/4,0,h/2],[w/2,4,h],'dark',True,True)
            box(label+'Handle',label+'Slider',[side*8,-3,102],[3,3,24],'letters',False)
            if row.get('role') in ('MainEntry','EntryFoyer','Entrance','Vestibule'):
                box(label+'GlassPanel',label+'Slider',[side*w/4,-2.2,h*.6],[max(12,w/2-12),.6,h*.6],'glass',False)
    else:
        side=int(row.get('hinge_side',1));direction=-side
        rows.append(component('DoorHinge','OpeningRoot',location=[side*(w/2-.5),depth/2+3,0],rotation=[0,0 if row.get('locked') else -side*90,0]))
        box('DoorLeaf','DoorHinge',[direction*(w-1)/2,0,h/2],[w-1,4,h],'wood',False)
        box('LeafCollision','DoorHinge',[direction*(w-1)/2,0,h/2],[w-1,4,h],'dark',True,True)
        box('Handle','DoorHinge',[direction*(w-12),-3,100],[10,3,3],'letters',False)
    for r in rows:
        if r['name']=='OpeningRoot':r['mobility']='STATIC'
    return rows

def main():
    assert not (WORK/'Applied.json').exists(),'V4 already applied. Audit the saved map instead.'
    baseline_input=read(WORK/'InputSnapshot.json')
    source=read(SOURCE/'BuildReport.json')
    plan=read(WORK/'ArchitecturePlan.json')
    assert baseline_input['passed'] and len(plan['rooms'])==27
    mapfile=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    original=sha(mapfile)
    assert original==baseline_input['source_map_sha256']==source['map_sha256'],'Rebase changed map before mutation.'
    assert all(sha(Path(p))==v for p,v in baseline_input['protected_map_sha256'].items())
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(TARGET)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=list(sub.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert {n:actor_state(a) for n,a in by.items()}==baseline_input['actors'],'Fresh input changed.'
    remove=set(n for n in source['hotel_architecture']['new_actor_labels'] if not n.startswith('CAM_Refinement_'))
    remove.update(n for n in source['hotel_operations']['new_actor_labels'] if not n.startswith('CAM_Refinement_'))
    remove.update(n for n in by if n.startswith(('OTS_Polish_Flight_OTS_PerimeterBoundaryEast_01_','OTS_Polish_Landing_OTS_PerimeterBoundaryEast_01_')))
    remove.update(['OTS_Enterable_OTS_PerimeterBoundaryEast_01_EntryFloorFill_9029',
        'OTS_Hotel_Hotel_EntranceCanopy','OTS_Hotel_Hotel_EntranceCanopyEdge',
        'OTS_Hotel_Hotel_MainSign','OTS_Hotel_SignLetters'])
    assert remove<=set(by),sorted(remove-set(by))
    baseline=dict(source_map_sha256=original,preserved_actors={n:actor_state(a) for n,a in by.items() if n not in remove},
        removed_actor_labels=sorted(remove),shared_asset_sha256=baseline_input['shared_asset_sha256'],
        protected_map_sha256=baseline_input['protected_map_sha256'],main_home=baseline_input['main_home'])
    before=WORK/'Before';before.mkdir(parents=True,exist_ok=True)
    for p in (mapfile,SOURCE/'BuildReport.json',ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json'):
        dst=before/p.name
        if dst.exists():assert sha(dst)==sha(p),'Existing backup differs: '+str(dst)
        else:shutil.copy2(p,dst)
    write('PreservationBaseline.json',baseline)
    mats={k:unreal.load_asset(v) for k,v in source['hotel_architecture']['material_paths'].items()}
    assert all(mats.values())
    cube=unreal.load_asset(CUBE);assert cube
    assets={r['key']:r['asset'] for r in source['hotel_architecture']['imported_assets']}
    for r in source['hotel_operations'].get('imports',[]):
        if 'key' in r and 'asset' in r:assets[r['key']]=r['asset']
    assets.update(plan.get('asset_catalog',{}))
    for n in sorted(remove):assert sub.destroy_actor(by[n]),n
    names=[]
    def register(a,name,role):
        assert name not in by and name not in names,name
        a.set_actor_label(name)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelV4/'+role))
        a.set_editor_property('tags',[unreal.Name(TAG)])
        names.append(name)
    def spawn_mesh(name,mesh,pos,role,rot=(0,0,0),scale=(1,1,1),mat=None,blocking=False,hidden=False):
        a=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*pos),unreal.Rotator(pitch=rot[0],yaw=rot[1],roll=rot[2]),False)
        assert a;register(a,name,role)
        a.set_actor_scale3d(unreal.Vector(*scale))
        c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(mesh)
        if mat:c.set_material(0,mat)
        c.set_collision_profile_name('BlockAll' if blocking else 'NoCollision')
        c.set_editor_property('generate_overlap_events',False)
        if hidden:
            c.set_editor_property('visible',False);c.set_editor_property('hidden_in_game',True);c.set_editor_property('cast_shadow',False)
        return a
    def world_box(row,hidden=False):
        lo,hi=row['world_min'],row['world_max'];name='OTS_HotelV4_'+row['id']
        assert all(hi[i]>lo[i] for i in range(3)),row
        spawn_mesh(name,cube,[(a+b)/2 for a,b in zip(lo,hi)],row['role'],scale=[(b-a)/100 for a,b in zip(lo,hi)],mat=mats[row['material']],blocking=row.get('collision',True),hidden=hidden or row.get('hidden',False))
        return dict(row,actor=name,asset=CUBE,material_asset=mats[row['material']].get_path_name())
    plan['placed_boxes']=[world_box(r) for r in plan['boxes']]
    plan['placed_props']=[]
    for row in plan['props']:
        path=row.get('asset') or assets[row['asset_key']]
        if isinstance(path,dict):path=path['asset']
        mesh=unreal.load_asset(path);assert mesh,(row['asset_key'],path)
        rotation=row.get('rotation',[0,row.get('yaw',0),0]);scale=row.get('scale',[1,1,1])
        name='OTS_HotelV4_'+row['id']
        a=spawn_mesh(name,mesh,row['position_cm'],'Fixtures',rot=rotation,scale=scale)
        colliders=[]
        for i,(lo,hi) in enumerate(row.get('collision_boxes',[])):
            col=dict(id=row['id']+'_Collision%d'%i,role='FixtureCollision',world_min=lo,world_max=hi,material='dark',collision=True,floor=row.get('floor'))
            colliders.append(world_box(col,True))
        plan['placed_props'].append(dict(row,actor=name,asset=mesh.get_path_name(),actor_scale=scale,rotation=rotation,world_bounds_cm=actor_bounds(a),colliders=colliders))
    cache={};blueprint_files=set()
    def opening(row,window=False):
        n=row['inward'];yaw=math.degrees(math.atan2(n[1],n[0]))-90.
        key=('Window' if window else row.get('kind','swing').title())+'_W%d_H%d_D%d'%(round(row['width']*10),round(row['height']*10),round(row.get('depth',20)*10))
        if not window:key+='_H%d_L%d'%(row.get('hinge_side',1),bool(row.get('locked')))
        path=BP_ROOT+'BP_OTS_V4_'+key
        specs=opening_specs(row,window,mats)
        if path not in cache:
            cache[path]=create_blueprint(path,specs)[1]
            blueprint_files.add(str(ROOT/('Content/'+path.removeprefix('/Game/')+'.uasset')))
        a=sub.spawn_actor_from_class(cache[path],unreal.Vector(*row['position_cm']),unreal.Rotator(pitch=0,yaw=yaw,roll=0),False)
        assert a;name='OTS_HotelV4_'+('Window_' if window else 'Door_')+row['id'];register(a,name,'Windows' if window else 'Doors')
        return dict(row,actor=name,asset=path,blueprint=path,components=deepcopy(specs),actor_position_cm=row['position_cm'],yaw=yaw)
    plan['placed_doors']=[opening(r) for r in plan['doors']]
    plan['placed_windows']=[opening(r,True) for r in plan['windows']]
    for r in plan.get('interior_lights',[]):
        rot=r.get('rotation',[-90,0,0]);a=sub.spawn_actor_from_class(unreal.RectLight,unreal.Vector(*r['position_cm']),unreal.Rotator(pitch=rot[0],yaw=rot[1],roll=rot[2]),False)
        register(a,'OTS_HotelV4_'+r['id'],'SurvivingLights');r['actor']=names[-1]
        c=a.get_component_by_class(unreal.RectLightComponent);c.set_mobility(unreal.ComponentMobility.MOVABLE)
        for k,v in dict(intensity_units=unreal.LightUnits.LUMENS,intensity=r.get('intensity_lm',75),source_width=10.,source_height=90.,attenuation_radius=r.get('attenuation_radius_cm',700),light_color=unreal.Color(215,222,188,255)).items():c.set_editor_property(k,v)
    # Existing hotel name mesh is reused without changing the shared asset.
    signmesh=unreal.load_asset(source.get('hotel_plan',{}).get('sign',{}).get('asset','')) if source.get('hotel_plan') else None
    if signmesh is None:
        for c in baseline_input['actors']['OTS_Hotel_SignLetters']['components']:
            if c.get('mesh'):signmesh=unreal.load_asset(c['mesh']);break
    assert signmesh
    spawn_mesh('OTS_HotelV4_ExteriorLetters',signmesh,[8987,0,318.5],'Signage',rot=[0,90,0],scale=[.75,.75,.75],mat=mats['letters'])
    for r in plan['review_cameras']:
        rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*r['position']),unreal.Vector(*r['look_at']))
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*r['position']),rot,False)
        register(a,r['camera'],'ReviewCameras');a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',r['fov'])
    plan.update(new_actor_labels=names,removed_actor_labels=sorted(remove),source_map_sha256=original,material_paths={k:v.get_path_name() for k,v in mats.items()},approved_user_instruction='可以，但是你要记得楼上区域也要做出相应改变，就这么开始做吧')
    current=list(sub.get_all_level_actors());refresh(current)
    plan['expected_actor_states']={a.get_actor_label():actor_state(a) for a in current if a.get_actor_label() in set(names)}
    assert len(current)==len(actors)-len(remove)+len(names)
    assert validate_main_home(current)==baseline['main_home']
    build=dict(status='PENDING',target_level=TARGET,source_map_sha256=original,map_sha256=original,actor_count=len(current),hotel_v4=plan,hotel_architecture=plan,protected_map_sha256=baseline['protected_map_sha256'],hotel_openings_review_cameras=[r['camera'] for r in plan['review_cameras']],previous_evidence=str(SOURCE/'FinalReview.json'),new_asset_sha256={p:sha(Path(p)) for p in sorted(blueprint_files)})
    write('PendingBuildReport.json',build)
    result=audit(world,plan,baseline,current);write('PreSaveAudit.json',result)
    assert result['passed'],'Physical audit failed; '+str(result['errors'][:20])
    assert sha(mapfile)==original
    assert level.save_current_level(),'Map save failed.'
    build.update(status='PASS',map_sha256=sha(mapfile));write('BuildReport.json',build)
    write('Applied.json',dict(passed=True,map_sha256=build['map_sha256'],rooms=len(plan['rooms']),actor_count=len(current)))
    unreal.log('HOTEL_V4_APPLY_PASS '+build['map_sha256'])

if __name__=='__main__':
    try:main()
    except Exception:
        write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()))
        raise
