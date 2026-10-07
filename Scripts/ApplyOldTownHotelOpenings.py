"""Build a complete, separately saved review map; never overwrite the open map."""
from collections import Counter
from copy import deepcopy
import hashlib,json,math,shutil,sys,traceback
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
CANON=ROOT/'Saved/CodexOutputs/EnterableStreet_20261002'
WORK=ROOT/'Saved/CodexOutputs/HotelOpenings_20261004'
SOURCE_LEVEL='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownHotelReview_20261004'
MAP=ROOT/('Content/'+TARGET.removeprefix('/Game/')+'.umap')
SOURCE_MAP=ROOT/('Content/'+SOURCE_LEVEL.removeprefix('/Game/')+'.umap')
TAG='OTS_HotelOpenings_20261004'
from ConvertOldTownBuildings import MeshFactory,plan_buildings,_subtract_box
from OldTownArchitectureSealPlan import door_coordinates,window_plan
from OldTownHotelPlan import build_hotel_plan
from OldTownHotelValidation import route_probe
from OldTownOpeningSpecs import door_specs,window_specs,ASSET_ROOT
from BuildOldTownOpeningBlueprints import create_blueprint
from AuditOldTownOpeningComponents import run as opening_audit,portal_id_for
from ValidateEnterableStreet import refresh_world_collision,validate_buildings,validate_main_home,sample_route
from PolishOldTownDetails import actor_bounds
import AuditOldTownRevision as revision
import AuditOldTownLightingCleanup as lighting
import AuditOldTownArchitectureSeal as architecture
import AuditOldTownDetailPolish as details

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,data):
    (WORK/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def xyz(v):return [float(v.x),float(v.y),float(v.z)]
def yaw_for_normal(n):return math.degrees(math.atan2(n[1],n[0]))-90.
def axes_from_coordinates(fn):
    o=fn(0,0,0);a=fn(1,0,0);n=fn(0,1,0)
    return {'across':[a[i]-o[i] for i in range(3)],'inward':[n[i]-o[i] for i in range(3)]}

def main():
    WORK.mkdir(parents=True,exist_ok=True)
    build=read(CANON/'BuildReport.json');plan=read(CANON/'RevisionPlan.json')
    assert sha(SOURCE_MAP)==build['map_sha256'],'Saved source changed; inspect its new state before rebuilding'
    before=WORK/'Before'
    if not before.exists():
        before.mkdir();shutil.copy2(SOURCE_MAP,before/SOURCE_MAP.name)
        for p in CANON.glob('*.json'):shutil.copy2(p,before/p.name)
    protected={p:sha(Path(p)) for p in build['protected_map_sha256']}
    protected[str(SOURCE_MAP)]=sha(SOURCE_MAP)
    write('ProtectedMapBaseline.json',{'sha256':protected,'source_target_open_in_user_editor':True})
    if unreal.EditorAssetLibrary.does_asset_exist(TARGET):
        assert not (WORK/'BuildReport.json').exists(),'Completed review exists; use repair/verify'
    else:
        clone=unreal.EditorAssetLibrary.duplicate_asset(SOURCE_LEVEL,TARGET);assert clone
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert level.load_level(TARGET)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by={a.get_actor_label():a for a in sub.get_all_level_actors()}
    geometry=plan_buildings([],plan);by_b={b.label:b for b in geometry}
    structure=build['buildings'];old_rows=deepcopy(structure['structural_boxes'])
    factory=MeshFactory(sub);factory.count=max(structure['generated_actor_count'],10000)
    hotel=build_hotel_plan(next(r for r in structure['buildings'] if r['label']=='OTS_PerimeterBoundaryEast_01'))
    build['hotel_plan']=hotel
    removed=set()
    def remove(name):
        if name in by:
            assert sub.destroy_actor(by[name]),name;removed.add(name)
    for row in old_rows:
        if row['role'] in ('DoorFrame','DoorLeaf','DoorHandle','WindowGlass'):remove(row['actor'])
    for row in build['architecture_seal']['windows']:remove(row['actor'])
    migrated=[r for r in build['detail_polish']['visuals'] if r['kind'] in ('door','inner_trim')]
    for r in migrated:remove(r['actor'])
    build['detail_polish']['migrated_opening_visuals']=migrated
    build['detail_polish']['visuals']=[r for r in build['detail_polish']['visuals'] if r not in migrated]
    for name in hotel['replace_actor_labels']:remove(name)
    allowed=set(build['lighting_cleanup']['allowed_scene_light_labels'])|{build['lighting_cleanup']['ui_only_light_actor']}
    for name,a in by.items():
        if name not in removed and a.get_components_by_class(unreal.LightComponentBase) and name not in allowed:remove(name)
    build['detail_polish']['attachments']=[r for r in build['detail_polish']['attachments'] if r['actor'] not in removed]
    build['street_end_cleanup']['attachment_expected_positions']={k:v for k,v in build['street_end_cleanup']['attachment_expected_positions'].items() if k not in removed}
    build['lighting_cleanup']['material_overrides']=[r for r in build['lighting_cleanup'].get('material_overrides',[]) if r.get('actor') not in removed]
    roofs=[]
    for side in ('North','South'):
        for i in range(1,5):
            name='OTS_PerimeterRoofCap{}{:02d}_01'.format(side,i)
            b=by_b['OTS_PerimeterBackdrop{}{:02d}_01'.format(side,i)];a=by[name]
            bounds=actor_bounds(a);desired=(b.low[1]+b.high[1])/2;delta=desired-(bounds[0][1]+bounds[1][1])/2
            pos=a.get_actor_location();pos.y+=delta;a.set_actor_location(pos,False,False)
            actual=actor_bounds(a)
            assert abs(actual[0][1]-(b.low[1]-10))<.1 and abs(actual[1][1]-(b.high[1]+10))<.1,(name,actual)
            roofs.append({'actor':name,'building':b.label,'delta_cm':[0,delta,0],'world_min':actual[0],'world_max':actual[1],'eaves_cm':10.})
    # Cut genuine openings into the existing rear wall; leave the other walls intact.
    east=by_b[hotel['building']]
    # Legacy storefronts and shutters must have the same real window holes.
    facade_cuts=[]
    all_windows=[w for b in geometry for w in window_plan(b)]+hotel['guest_windows']
    for w in all_windows:
        b=by_b[w['building']];lo=list(w['world_min']);hi=list(w['world_max'])
        lo[b.normal_axis]-=65.;hi[b.normal_axis]+=65.;facade_cuts.append((lo,hi))
    candidates=[(r['actor'],r) for r in old_rows if r['role']=='FacadePanel']
    candidates += [(name,None) for name in by if 'Shutter' in name and name not in {r['actor'] for r in old_rows}]
    for name,row in candidates:
        if name in removed:continue
        a=by[name];bounds=actor_bounds(a);lo,hi=bounds
        cuts=[(cl,ch) for cl,ch in facade_cuts if all(min(hi[i],ch[i])-max(lo[i],cl[i])>.01 for i in range(3))]
        if not cuts:continue
        cs=[c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh];assert len(cs)==1,name
        mat=cs[0].get_material(0);pieces=[(lo,hi)]
        for cl,ch in cuts:pieces=[part for pl,ph in pieces for part in _subtract_box(pl,ph,cl,ch)]
        remove(name)
        for pl,ph in pieces:factory.world_box(row['building'] if row else 'Facade','FacadePanel',pl,ph,mat)
    for row in old_rows:
        if row['role']!='WallPanel' or row['building']!=east.label:continue
        cuts=[w for w in hotel['guest_windows'] if all(min(row['max'][i],w['world_max'][i])-max(row['min'][i],w['world_min'][i])>.01 for i in range(3))]
        if not cuts:continue
        pieces=[(row['min'],row['max'])]
        for w in cuts:pieces=[part for lo,hi in pieces for part in _subtract_box(lo,hi,w['world_min'],w['world_max'])]
        remove(row['actor']);mat=unreal.load_asset(east.row['meshes'][0]['materials'][0])
        for lo,hi in pieces:factory.world_box(east.label,'WallPanel',lo,hi,mat)
    hotel_actors=[]
    cube=unreal.load_asset('/Engine/BasicShapes/Cube.Cube')
    for row in hotel['boxes']:
        lo,hi=row['world_min'],row['world_max'];center=[(lo[i]+hi[i])/2 for i in range(3)]
        a=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*center),unreal.Rotator(0,0,0),False)
        name='OTS_Hotel_'+row['name'];a.set_actor_label(name);a.set_folder_path(unreal.Name('OldTownSchoolStreet/Hotel/'+row['category']))
        a.set_editor_property('tags',[unreal.Name(TAG)]);c=a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(cube);c.set_material(0,unreal.load_asset(hotel['material_paths'][row['material']]))
        a.set_actor_scale3d(unreal.Vector(*[(hi[i]-lo[i])/100 for i in range(3)]))
        c.set_collision_profile_name('BlockAll' if row['collision'] else 'NoCollision')
        hotel_actors.append(dict(row,actor=name,asset=cube.get_path_name()))
        if row['category']=='ground':
            surface=deepcopy(next(s for s in hotel['street_corner']['ground_surfaces'] if s['name']==row['name']))
            surface['actor']=name;plan['ground_surfaces'].append(surface)
            build['street_end_cleanup']['road_surface_expectations'].append({'actor':name,'world_min':lo,'world_max':hi})
    hotel['placed_boxes']=hotel_actors
    sign_mesh=unreal.load_asset(ASSET_ROOT+'/SM_OTS_HotelSignLetters');assert sign_mesh
    center=hotel['sign']['center_cm'];origin=sign_mesh.get_bounds().origin
    a=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(center[0],center[1],center[2]-origin.z),unreal.Rotator(pitch=0,yaw=90,roll=0),False)
    a.set_actor_label('OTS_Hotel_SignLetters');a.set_folder_path(unreal.Name('OldTownSchoolStreet/Hotel/hotel_exterior'))
    a.set_editor_property('tags',[unreal.Name(TAG)]);c=a.get_component_by_class(unreal.StaticMeshComponent);c.set_static_mesh(sign_mesh);c.set_collision_profile_name('NoCollision')
    hotel['sign']['actor']=a.get_actor_label();hotel['sign']['asset']=sign_mesh.get_path_name()
    cache={};assemblies={'schema_version':1,'doors':[],'windows':[],'removed_actor_labels':sorted(removed)}
    def spawn_opening(name,kind,components,pos,yaw,bpkey):
        path='/Game/CodexGenerated/OldTown/Blueprints/Openings/BP_OTS_'+bpkey
        if path not in cache:cache[path]=create_blueprint(path,components)[1]
        a=sub.spawn_actor_from_class(cache[path],unreal.Vector(*pos),unreal.Rotator(pitch=0,yaw=yaw,roll=0),False)
        assert a,name;a.set_actor_label(name);a.set_editor_property('tags',[unreal.Name(TAG)])
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/Openings/'+kind))
        rows=deepcopy(components);root=next(c for c in a.get_components_by_class(unreal.SceneComponent) if c.get_name()=='OpeningRoot')
        r=root.get_editor_property('relative_rotation');rows[0]['relative_location']=xyz(root.get_editor_property('relative_location'));rows[0]['relative_rotation']=[r.pitch,r.yaw,r.roll]
        return a,rows,path
    old_doors={d['building']:d for d in build['architecture_seal']['doors']}
    for b in geometry:
        p=b.portals[0];axes=axes_from_coordinates(lambda aa,n,z:door_coordinates(b,p,aa,n,z));yaw=yaw_for_normal(axes['inward'])
        local_x=[math.cos(math.radians(yaw)),math.sin(math.radians(yaw)),0]
        side=old_doors[b.label]['hinge_side']*sum(axes['across'][i]*local_x[i] for i in range(3));side=-1 if side<0 else 1
        specs=door_specs(b.door_width,b.door_height,side)
        pos=door_coordinates(b,p,0,0,b.ground);name='OTS_DoorModule_'+b.label
        a,cs,bp=spawn_opening(name,'Doors',specs,pos,yaw,'Door_{}_{}_{}'.format(int(b.door_width),int(b.door_height),'L' if side<0 else 'R'))
        row={'actor':name,'building':b.label,'portal_id':portal_id_for(b,p),'kind':'building_entry','opening_width':b.door_width,'opening_height':b.door_height,'hinge_side':side,'world_center':pos,'entry_foot':pos,'frame_asset':next(c['asset'] for c in cs if c['name']=='FixedFrame'),'leaf_asset':next(c['asset'] for c in cs if c['name']=='DoorLeaf'),'axes':axes,'components':cs,'blueprint':bp,'closed_hinges':{'DoorHinge':[0,0,0]},'open_hinges':{'DoorHinge':[0,-side*90,0]}}
        assemblies['doors'].append(row);old_doors[b.label]['actor']=name;old_doors[b.label]['component_module']=row
    for d in hotel['guest_rooms']:
        pos=d['world_center'];yaw=yaw_for_normal(d['axes']['inward']);side=1
        specs=door_specs(90,200,side,12,0)
        name='OTS_DoorModule_'+d['door_id'];a,cs,bp=spawn_opening(name,'HotelGuestDoors',specs,pos,yaw,'GuestDoor_90_200')
        assemblies['doors'].append({'actor':name,'building':d['building'],'portal_id':d['door_id'],'kind':'hotel_guest','opening_width':90.,'opening_height':200.,'hinge_side':side,'world_center':pos,'axes':d['axes'],'components':cs,'blueprint':bp,'closed_hinges':{'DoorHinge':[0,0,0]},'open_hinges':{'DoorHinge':[0,-90,0]}})
    old_windows={w['name']:w for w in build['architecture_seal']['windows']}
    windows=[dict(w,window_id=w['name']) for b in geometry for w in window_plan(b)]+hotel['guest_windows']
    for w in windows:
        b=by_b[w['building']];sign=1 if w['wall']=='Front' else -1
        n=[0,0,0];n[b.normal_axis]=b.inward*sign;across=[0,0,0];across[b.u_axis]=1
        center=b.world(w['u'],w['v'],w['z']);pos=center[:];pos[2]-=w['height']/2
        specs=window_specs(w['width'],w['height']);name='OTS_WindowModule_'+w['window_id']
        a,cs,bp=spawn_opening(name,'Windows',specs,pos,yaw_for_normal(n),'Window_{}_{}'.format(int(w['width']),int(w['height'])))
        row={'actor':name,'building':b.label,'window_id':w['window_id'],'kind':'hotel_guest' if w['window_id'].startswith('Hotel_') else 'building_window','width':w['width'],'height':w['height'],'world_center':center,'axes':{'across':across,'inward':n},'components':cs,'blueprint':bp,'closed_hinges':{'LeftHinge':[0,0,0],'RightHinge':[0,0,0]},'open_hinges':{'LeftHinge':[0,90,0],'RightHinge':[0,-90,0]}}
        assemblies['windows'].append(row)
        if w['window_id'] in old_windows:old_windows[w['window_id']]['actor']=name
    structure['structural_boxes']=[r for r in old_rows if r['actor'] not in removed]+factory.placed_boxes
    assemblies['removed_actor_labels']=sorted(removed)
    for row in assemblies['doors']+assemblies['windows']:
        row['frame_asset']=next(c['asset'] for c in row['components'] if c['name']=='FixedFrame')
        if 'portal_id' in row:row['leaf_asset']=next(c['asset'] for c in row['components'] if c['name']=='DoorLeaf')
    structure['generated_actor_count']=len(structure['structural_boxes'])
    structure['module_actor_distribution']=dict(Counter(r['role'] for r in structure['structural_boxes']))
    structure['generated_assets']=sorted(set(structure['generated_assets']+[m.get_path_name() for m in factory.modules.values()]))
    build['opening_components']=assemblies;build['protected_map_sha256']=protected
    build['opening_imports']=read(WORK/'OpeningImportReport.json');build['roof_cap_repairs']=roofs
    cams=[
      ('CAM_Hotel_MapOverview',[2200,-8000,8500],[2200,0,100],70),
      ('CAM_Hotel_OverviewNW',[-7300,5500,4500],[1500,0,550],75),
      ('CAM_Hotel_OverviewSE',[11600,-5200,4000],[3500,0,500],75),
      ('CAM_Hotel_Junction',[7200,-800,1100],[9000,158,420],75),
      ('CAM_Hotel_Front',[7900,-100,190],[9000,158,270],75),
      ('CAM_Hotel_Lobby',[9180,158,175],[9820,400,150],80),
      ('CAM_Hotel_Corridor',[9280,-3380,east.floors[1]+155],[9340,2000,east.floors[1]+150],75),
      ('CAM_Hotel_Room',[9600,-3290,east.floors[1]+155],[9930,-2960,east.floors[1]+125],75),
      ('CAM_Hotel_RearWindows',[11000,-1400,1300],[10040,-1500,850],75),
      ('CAM_Hotel_CornerNorth',[6850,620,175],[6800,1620,100],80),
      ('CAM_Hotel_CornerSouth',[6900,-680,190],[6850,-1650,110],80),
      ('CAM_Roof_North',[4600,1050,2150],[4600,2200,1420],80),
      ('CAM_Roof_South',[4600,-1050,2150],[4600,-2200,1420],80),
      ('CAM_Hotel_NightFront',[7900,-100,190],[9000,158,270],75)]
    b=by_b['BLK_L_Enter_C_Mass'];w=next(w for w in window_plan(b) if w['floor']==0)
    cams+= [('CAM_Openings_Window',b.world(w['u'],240,b.ground+160),b.world(w['u'],10,w['z']),65),
            ('CAM_Openings_Door',door_coordinates(b,b.portals[0],0,-230,b.ground+155),door_coordinates(b,b.portals[0],0,20,b.ground+120),75)]
    for name,pos,target,fov in cams:
        rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*pos),unreal.Vector(*target))
        a=sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*pos),rot,False);a.set_actor_label(name)
        a.set_editor_property('tags',[unreal.Name(TAG)]);a.set_folder_path(unreal.Name('OldTownSchoolStreet/Hotel/ReviewCameras'))
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',fov)
    build['hotel_openings_review_cameras']=[r[0] for r in cams]
    build['target_level']=TARGET;plan['target_level']=TARGET
    plan['translated_inventory']['level']=TARGET
    import ConvertOldTownBuildings as conversion
    conversion.TARGET_LEVEL=TARGET
    for module in (revision,lighting,details):module.TARGET=TARGET
    actors=list(sub.get_all_level_actors());refresh_world_collision(actors)
    assert validate_main_home(actors)==build['main_home'],'MainHome changed'
    build['collision']=validate_buildings(world,actors,structure);write('CollisionValidation.json',build['collision']);assert build['collision']['passed'],'Original routes failed'
    results={}
    for name,fn in [('OpeningComponentsAudit.json',lambda:opening_audit(world,actors,geometry,build)),
                    ('RevisionAudit.json',lambda:revision.audit_revision(world,actors,build,plan)),
                    ('LightingCleanupAudit.json',lambda:lighting.audit_cleanup(world,actors,build)),
                    ('ArchitectureSealAudit.json',lambda:architecture.audit_architecture(world,actors,build,plan)),
                    ('DetailPolishAudit.json',lambda:details.audit_details(world,actors,build,plan))]:
        r=fn();write(name,r);assert r['passed'],(name,r.get('failures',r.get('errors'))[:10]);results[name]=r
    routes=[]
    for route in hotel['routes']:
        result=route_probe(world,route['points'])
        routes.append(dict(route,result=result))
    write('HotelRouteAudit.json',{'passed':all(r['result']['passed'] for r in routes),'routes':routes})
    assert all(r['result']['passed'] for r in routes),'Hotel route blocked'
    assert all(sha(Path(p))==h for p,h in protected.items()),'Protected/source map changed'
    assert level.save_current_level(),'Review save failed'
    map_sha=sha(MAP);build['map_sha256']=map_sha
    for k in ('architecture_seal','detail_polish'):build[k]['map_sha256']=map_sha
    build['hotel_openings']={'status':'PASS','map_sha256':map_sha,'preview':True,'source_level':SOURCE_LEVEL,'source_sha256':sha(SOURCE_MAP),'doors':len(assemblies['doors']),'windows':len(assemblies['windows']),'roof_caps':len(roofs),'hotel_rooms':len(hotel['guest_rooms']),'new_cameras':len(cams)}
    build['actor_count']=len(actors);build['status']='PASS'
    for name,r in results.items():r['map_sha256']=map_sha;write(name,r)
    write('BuildReport.json',build);write('BuildingReport.json',structure);write('RevisionPlan.json',plan);write('HotelPlan.json',hotel)
    unreal.log('OLDTOWN_HOTEL_OPENINGS_REVIEW_PASS '+map_sha)

if __name__=='__main__':
    try:main()
    except Exception:
        write('ApplyFailure.json',{'passed':False,'traceback':traceback.format_exc()});raise
