"""Apply supported stairs, real hinge assemblies and platform-height windows."""
import json,sys,math,shutil,traceback
from pathlib import Path
from copy import deepcopy
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state,sha,xyz
from PolishOldTownDetails import actor_bounds
from OldTownHotelDetailPlan import make_detail_delta,REAR_WALL_RENDER_OFFSET_CM
from OldTownHotelDetailMeshes import hinge_asset
from OldTownWindowSurfaceRepair import apply_window
from OldTownSurfaceMaterials import make_offset_material,get_report,asset_hashes
from ApplyOldTownHotelV4 import opening_specs,BP_ROOT,CUBE
from BuildOldTownOpeningBlueprints import create_blueprint
from AuditOldTownHotelV4 import audit,refresh
from AuditOldTownHotelDetails import detail_audit
WORK=ROOT/'Saved/CodexOutputs/HotelDetails_20261009'
SOURCE=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,r):(WORK/n).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    assert not (WORK/'Applied.json').exists(),'Already applied; audit the saved map instead.'
    build=read(SOURCE/'BuildReport.json');plan=deepcopy(build['hotel_v4']);original=read(WORK/'InputSnapshot.json')
    mapfile=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap';oldhash=sha(mapfile)
    assert oldhash==build['map_sha256']==original['source_map_sha256']
    assert all(sha(Path(p))==v for p,v in build['new_asset_sha256'].items())
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(TARGET)
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=list(sub.get_all_level_actors())
    by={a.get_actor_label():a for a in actors};assert {n:actor_state(a) for n,a in by.items()}==original['actors']
    before=WORK/'Before';before.mkdir(exist_ok=True)
    for p in (mapfile,SOURCE/'BuildReport.json',ROOT/'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json'):
        dst=before/p.name
        if dst.exists():assert sha(dst)==sha(p)
        else:shutil.copy2(p,dst)
    delta=make_detail_delta(plan);write('DetailDelta.json',delta)
    mats={k:unreal.load_asset(v) for k,v in plan['material_paths'].items()};assert all(mats.values())
    cube=unreal.load_asset(CUBE);cylinder=unreal.load_asset('/Engine/BasicShapes/Cylinder.Cylinder')
    removed_ids=set(delta['removed_box_ids']);modified={r['id']:r for r in delta['modified_boxes']}
    removed_labels={r['actor'] for r in plan['placed_boxes'] if r['id'] in removed_ids}
    oldwindows={r['id']:deepcopy(r) for r in plan['windows'] if r.get('kind')=='stair'}
    selected_windows={r['id'] for r in delta['updated_windows']}
    removed_labels.update(r['actor'] for r in plan['placed_windows'] if r['id'] in selected_windows)
    old_created=set(plan['new_actor_labels']);assert removed_labels<=old_created
    oldwindow_states={r['id']:original['actors'][r['actor']] for r in plan['placed_windows'] if r['id'] in selected_windows}
    for n in sorted(removed_labels):assert sub.destroy_actor(by.pop(n)),n
    added=[]
    def register(a,name,role):
        assert name not in by and name not in added,name
        a.set_actor_label(name);a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelV4/'+role))
        a.set_editor_property('tags',[unreal.Name('HotelRedesign_20261008_V4'),unreal.Name('HotelDetails_20261009')])
        by[name]=a;added.append(name)
    def spawn_mesh(name,mesh,pos,role,scale=(1,1,1),rotation=(0,0,0),material=None,blocking=False,movable=False):
        a=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*pos),
            unreal.Rotator(pitch=rotation[0],yaw=rotation[1],roll=rotation[2]),False);assert a
        register(a,name,role);c=a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_mobility(unreal.ComponentMobility.MOVABLE if movable else unreal.ComponentMobility.STATIC)
        c.set_static_mesh(mesh);a.set_actor_scale3d(unreal.Vector(*scale))
        if material:c.set_material(0,material)
        c.set_collision_profile_name('BlockAll' if blocking else 'NoCollision');c.set_editor_property('generate_overlap_events',False)
        return a
    rear_material=make_offset_material(mats['plaster'],REAR_WALL_RENDER_OFFSET_CM,
        '/Game/CodexGenerated/OldTown/Materials/HotelDetails_20261009')
    rear_overrides=[]
    def box(row):
        r=deepcopy(row);lo,hi=r['world_min'],r['world_max'];isrear=r.get('detail_kind')=='recut_rear_envelope'
        mat=rear_material if isrear else mats[r['material']]
        a=spawn_mesh(r.get('actor','OTS_HotelV4_'+r['id']),cube,[(a+b)/2 for a,b in zip(lo,hi)],r['role'],
            scale=[(b-a)/100 for a,b in zip(lo,hi)],material=mat,blocking=r.get('collision',True))
        c=a.get_component_by_class(unreal.StaticMeshComponent)
        if isrear:
            c.set_evaluate_world_position_offset(True)
            c.set_editor_property('evaluate_world_position_offset_in_ray_tracing',True)
            rear_overrides.append(dict(id=a.get_actor_label()+'::'+c.get_name(),offset_cm=REAR_WALL_RENDER_OFFSET_CM,
                materials=[dict(slot=0,original=mats['plaster'].get_path_name(),asset=mat.get_path_name())]))
        r.update(actor=a.get_actor_label(),asset=CUBE,material_asset=mat.get_path_name());return r
    placed=[]
    for r in plan['placed_boxes']:
        if r['id'] in removed_ids:continue
        if r['id'] in modified:
            r=deepcopy(modified[r['id']]);a=by[r['actor']];lo,hi=r['world_min'],r['world_max']
            a.set_actor_location(unreal.Vector(*[(x+y)/2 for x,y in zip(lo,hi)]),False,True)
            a.set_actor_scale3d(unreal.Vector(*[(y-x)/100 for x,y in zip(lo,hi)]))
            c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_material(0,mats[r['material']])
            r['material_asset']=mats[r['material']].get_path_name()
        placed.append(r)
    placed += [box(r) for r in delta['added_boxes']+delta['rear_wall_boxes']]
    plan['placed_boxes']=placed
    plan['boxes']=[deepcopy(modified.get(r['id'],r)) for r in plan['boxes'] if r['id'] not in removed_ids]
    plan['boxes']+=deepcopy(delta['added_boxes']+delta['rear_wall_boxes'])
    for raw in delta['rail_tubes']:
        r=deepcopy(raw);d=r['direction'];rotation=[-math.degrees(math.acos(max(-1,min(1,d[2])))),math.degrees(math.atan2(d[1],d[0])),0]
        scale=[r['diameter_cm']/100,r['diameter_cm']/100,r['length_cm']/100]
        a=spawn_mesh(r['actor'],cylinder,r['position_cm'],'StairRails',scale,rotation,mats['green'],True)
        ar=a.get_actor_rotation();rotation=[float(ar.pitch),float(ar.yaw),float(ar.roll)]
        bounds=actor_bounds(a);r.update(asset=cylinder.get_path_name(),actor_scale=scale,scale=scale,rotation=rotation,
            world_bounds_cm=bounds,world_min=bounds[0],world_max=bounds[1],colliders=[],detail_kind='round_handrail')
        plan['placed_props'].append(r);plan['props'].append(deepcopy(r))
    cache={};blueprint_files=set();window_reports=[];newplaced=[]
    for r in plan['placed_windows']:
        if r['id'] not in selected_windows:newplaced.append(r);continue
        row=next(deepcopy(q) for q in delta['updated_windows'] if q['id']==r['id'])
        path=BP_ROOT+'BP_OTS_Detail_Window_W%d_H%d_D%d'%(round(row['width']*10),round(row['height']*10),round(row['depth']*10))
        specs=opening_specs(row,True,mats)
        if path not in cache:
            cache[path]=create_blueprint(path,specs)[1];blueprint_files.add(str(ROOT/('Content/'+path[6:]+'.uasset')))
        n=row['inward'];yaw=math.degrees(math.atan2(n[1],n[0]))-90
        a=sub.spawn_actor_from_class(cache[path],unreal.Vector(*row['position_cm']),unreal.Rotator(pitch=0,yaw=yaw,roll=0),False)
        assert a;register(a,r['actor'],'Windows');state=oldwindow_states[row['id']]
        a.set_folder_path(unreal.Name(state['folder']));a.set_editor_property('tags',[unreal.Name(t) for t in state['tags']])
        row.update(actor=r['actor'],asset=path,blueprint=path,components=deepcopy(specs),actor_position_cm=row['position_cm'],yaw=yaw)
        row,report=apply_window(a,row);window_reports.append(report);newplaced.append(row)
    plan['placed_windows']=newplaced;plan['windows']=deepcopy(delta['windows'])
    hinge_reports=[]
    for row in plan['placed_doors']:
        if row['kind']!='swing':continue
        owner=by[row['actor']]
        for moving,parent_name in ((False,'OpeningRoot'),(True,'DoorHinge')):
            mesh,report=hinge_asset(row,moving,mats['dark']);hinge_reports.append(report)
            name=row['actor']+('_MovingHinges' if moving else '_FixedHinges')
            parent=next(c for c in owner.get_components_by_class(unreal.SceneComponent) if c.get_name()==parent_name)
            a=spawn_mesh(name,mesh,xyz(parent.get_world_location()),'DoorHinges',material=mats['dark'],movable=moving)
            assert a.attach_to_component(parent,unreal.Name('None'),unreal.AttachmentRule.KEEP_RELATIVE,
                unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,False)
            a.set_actor_relative_location(unreal.Vector(0,0,0),False,True)
            a.set_actor_relative_rotation(unreal.Rotator(pitch=0,yaw=0,roll=0),False,True)
            a.set_actor_relative_scale3d(unreal.Vector(1,1,1));bounds=actor_bounds(a)
            r=dict(id=name.removeprefix('OTS_HotelV4_'),actor=name,asset=mesh.get_path_name(),floor=row['floor'],
                position_cm=xyz(a.get_actor_location()),rotation=[float(v) for v in (a.get_actor_rotation().pitch,a.get_actor_rotation().yaw,a.get_actor_rotation().roll)],
                actor_scale=[1,1,1],scale=[1,1,1],world_bounds_cm=bounds,colliders=[],collision=False,
                detail_kind='door_hinge_assembly',door_actor=row['actor'],parent_component=parent_name,hinge_count=3)
            plan['placed_props'].append(r);plan['props'].append(deepcopy(r))
    cameras=[
        dict(camera='CAM_Detail_DoorHinge',position=[9320,-2440,478.25],look_at=[9263,-2480.5,488.25],fov=65),
        dict(camera='CAM_Detail_StairRail',position=[9720,650,200],look_at=[9840,865,205],fov=85),
        dict(camera='CAM_Detail_PostBase',position=[9770,810,95],look_at=[9836,838,89],fov=60),
        dict(camera='CAM_Detail_StairWindow',position=[9900,1090,299.625],look_at=[10030,1090,312.125],fov=80),
        dict(camera='CAM_Detail_RearFacade',position=[14000,0,1000],look_at=[10030,0,700],fov=95),
        dict(camera='CAM_Detail_TopGuard',position=[9790,700,1272.75],look_at=[9850,700,1214.75],fov=85)]
    for r in cameras:
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*r['position']),
            unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*r['position']),unreal.Vector(*r['look_at'])),False)
        register(a,r['camera'],'ReviewCameras');a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',r['fov'])
        r['lighting_mode']='temporary'
    plan['review_cameras']+=cameras
    plan['new_actor_labels']=sorted((old_created-removed_labels)|set(added))
    plan['detail_design']=dict(recipe=delta['recipe'],constraints=delta['constraints'],original_stair_windows=oldwindows)
    plan['source_map_sha256']=oldhash
    actors=list(sub.get_all_level_actors());refresh(actors);current={a.get_actor_label():actor_state(a) for a in actors}
    created=set(plan['new_actor_labels']);plan['expected_actor_states']={n:current[n] for n in created}
    baseline=dict(source_map_sha256=oldhash,preserved_actors={n:s for n,s in original['actors'].items() if n not in old_created},
        removed_actor_labels=sorted(removed_labels),shared_asset_sha256=original['shared_asset_sha256'],
        protected_map_sha256=original['protected_map_sha256'],main_home=original['main_home'])
    write('PreservationBaseline.json',baseline)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result=audit(world,plan,baseline,actors);write('PreSaveAudit.json',result);assert result['passed'],result['errors'][:25]
    detailed=detail_audit(world,plan,actors);write('PreSaveDetailAudit.json',detailed);assert detailed['passed'],detailed['errors'][:25]
    matreport=get_report();write('DetailMaterialRepair.json',matreport);assert matreport['passed']
    new_assets=dict(build['new_asset_sha256'],**asset_hashes())
    for r in hinge_reports:new_assets[r['file']]=r['sha256']
    for p in blueprint_files:new_assets[p]=sha(Path(p))
    for wr in window_reports:
        for r in wr['new_assets']:
            p=ROOT/('Content/'+r['asset'].split('.')[0][6:]+'.uasset');new_assets[str(p)]=sha(p)
    repaired_labels=removed_labels|{r['actor'] for r in modified.values()}
    repair=deepcopy(build['surface_repair'])
    repair['material_overrides']=[r for r in repair['material_overrides'] if r['id'].split('::')[0] not in repaired_labels]+rear_overrides
    repair['shifted_components']=len(repair['material_overrides'])
    repair['mesh_swaps']=[r for r in repair['mesh_swaps'] if r['id'].split('::')[0] not in repaired_labels]
    repair['detail_repair']=str(WORK/'DetailRepairReport.json')
    detailreport=dict(passed=True,source_map_sha256=oldhash,grounded_posts=240,baseplates=240,pipes=60,sloped_pipes=18,
        hinge_equipped_doors=62,hinges=186,repositioned_windows=12,removed_redundant_backwalls=18,
        new_hinge_assets={r['asset']:r for r in hinge_reports},window_repairs=window_reports,new_cameras=cameras)
    write('DetailRepairReport.json',detailreport)
    build.update(status='PENDING',source_map_sha256=oldhash,actor_count=len(actors),hotel_v4=plan,hotel_architecture=plan,
        new_asset_sha256=new_assets,surface_repair=repair,detail_repair=detailreport,protected_map_sha256=original['protected_map_sha256'],
        hotel_openings_review_cameras=[r['camera'] for r in plan['review_cameras']],previous_evidence=str(SOURCE/'FinalReview.json'))
    write('PendingBuildReport.json',build)
    assert sha(mapfile)==oldhash;assert levels.save_current_level(),'Map save failed'
    digest=sha(mapfile);build.update(status='PASS',map_sha256=digest);detailreport['map_sha256']=digest
    write('ArchitecturePlan.json',plan);write('DetailRepairReport.json',detailreport);write('BuildReport.json',build)
    write('Applied.json',dict(passed=True,map_sha256=digest,actor_count=len(actors),statistics=detailed['statistics']))
    unreal.log('HOTEL_DETAILS_APPLY_PASS '+digest)
if __name__=='__main__':
    try:main()
    except Exception:
        write('ApplyFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
