"""Remove scene fill lights and repair street-lamp placement and the east junction."""
import copy
import fnmatch
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unreal

PROJECT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(PROJECT/'Scripts'))
from ReviseOldTownLayout import emit_roads
from ValidateEnterableStreet import refresh_world_collision,validate_buildings,validate_main_home
from AuditOldTownRevision import audit_revision
from AuditOldTownLightingCleanup import audit_cleanup

OUT=PROJECT/'Saved/CodexOutputs/EnterableStreet_20261002'
WORK=PROJECT/'Saved/CodexOutputs/LightRoadCleanup_20261003'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=PROJECT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
EAST='OTS_PerimeterBoundaryEast_01'
FIX_TAG='OTS_LightRoadCleanup_20261003'

def write(name,data):
    for p in (OUT,WORK):
        (p/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def xyz(v):
    return [float(v.x),float(v.y),float(v.z)]

def translate_data(data,delta):
    """Translate only explicit world geometry, never local geometry or dimensions."""
    point_keys={'world_min','world_max','opening_min','opening_max','interior_min','interior_max','min','max'}
    route_keys={'route','primary_entry_route','ground_route','public_route','foot_waypoints','floor_support_points','outdoor_route'}
    if isinstance(data,dict):
        for k,v in data.items():
            if k in point_keys and isinstance(v,list) and len(v)==3 and all(isinstance(x,(int,float)) for x in v):
                data[k]=[v[i]+delta[i] for i in range(3)]
            elif k in route_keys:
                data[k]=[[point[i]+delta[i] for i in range(3)] for point in v]
            elif k not in ('local_min','local_max','coverage'):
                translate_data(v,delta)
    elif isinstance(data,list):
        for v in data:
            translate_data(v,delta)

def surface(name,rect,top=11.,width=None,clear=None):
    row={'name':name,'kind':'slab','rect_xy':list(rect),
         'world_min':[rect[0],rect[1],top-20.],'world_max':[rect[2],rect[3],top],
         'surface_z_cm':top,'purpose':'visible east T junction and setback frontage'}
    if width is not None:
        row['target_clear_width_cm']=width
    if clear is not None:
        row['clear_rect_xy']=list(clear)
    return row

WORK.mkdir(parents=True,exist_ok=True)
before=WORK/'Before'
before.mkdir(exist_ok=True)
if not (before/MAP.name).exists():
    shutil.copy2(MAP,before/MAP.name)
    for name in ('BuildReport.json','BuildingReport.json','RevisionPlan.json','RevisionAudit.json','SavedVerification.json','FinalReview.json'):
        shutil.copy2(OUT/name,before/name)
build=json.loads((OUT/'BuildReport.json').read_text(encoding='utf-8'))
plan=json.loads((OUT/'RevisionPlan.json').read_text(encoding='utf-8'))
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level(TARGET)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
by={a.get_actor_label():a for a in sub.get_all_level_actors()}
removed=list(build.get('lighting_cleanup',{}).get('removed_actor_labels',[]))
allowed=['OTS_Light_StreetLamp'+n for n in ('01','02','04','05','06','07','08','09')]
for label,actor in list(by.items()):
    if actor.get_components_by_class(unreal.LightComponentBase) and label not in allowed and label!='BP_InventoryCharacterPreview':
        assert sub.destroy_actor(actor),label
        removed.append(label)
        by.pop(label)

# Remove independent non-street fixtures; integrated awnings retain their geometry.
fixture_tokens=('WallLampGooseneck','MainHomeCeilingTube','SchoolGateTube','SchoolEntranceTube',
                'SchoolFacadeTube','SchoolWingTube','AlleyEndLampFixture','SchoolCourtyardLampHead','SchoolCourtyardLampPole')
for label,actor in list(by.items()):
    if any(token in label for token in fixture_tokens):
        assert sub.destroy_actor(actor),label
        removed.append(label)
        by.pop(label)

lamp_positions={}
light_positions={}
for i in range(1,8):
    label='OTS_P2Prop_StreetLamp_{:02d}'.format(i)
    actor=by[label]
    old=actor.get_actor_location()
    pos=[old.x,-500. if old.y<0 else 500.,old.z]
    actor.set_actor_location(unreal.Vector(*pos),False,False)
    lamp_positions[label]=pos
    light=by.get('OTS_Light_StreetLamp{:02d}'.format(i))
    if light:
        p=unreal.Vector(pos[0],pos[1]+(112.32 if pos[1]<0 else -112.32),11.+306.*actor.get_actor_scale3d().z)
        light.set_actor_location(p,False,False)
        c=light.get_component_by_class(unreal.PointLightComponent)
        c.set_editor_property('intensity',600.)
        light_positions[light.get_actor_label()]=xyz(p)

base=by['OTS_P2Prop_StreetLamp_05']
base_c=base.get_component_by_class(unreal.StaticMeshComponent)
for i,y in ((8,-650.),(9,650.)):
    name='OTS_P2Prop_StreetLamp_{:02d}'.format(i)
    pos=[8400.,y,11.]
    actor=by.get(name) or sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*pos),unreal.Rotator(pitch=0.,yaw=-90.,roll=0.),False)
    actor.set_actor_label(name)
    actor.set_actor_location(unreal.Vector(*pos),False,False)
    actor.set_actor_rotation(unreal.Rotator(pitch=0.,yaw=-90.,roll=0.),False)
    actor.set_actor_scale3d(base.get_actor_scale3d())
    actor.set_folder_path(unreal.Name('OldTownSchoolStreet/StreetLighting'))
    c=actor.get_component_by_class(unreal.StaticMeshComponent)
    c.set_static_mesh(base_c.static_mesh)
    for slot in range(base_c.get_num_materials()):
        c.set_material(slot,base_c.get_material(slot))
    c.set_collision_profile_name('BlockAll')
    lamp_positions[name]=pos
    name='OTS_Light_StreetLamp{:02d}'.format(i)
    pos=[8287.68,y,375.14]
    light=by.get(name) or sub.spawn_actor_from_class(unreal.PointLight,unreal.Vector(*pos),unreal.Rotator(),False)
    light.set_actor_label(name)
    light.set_actor_location(unreal.Vector(*pos),False,False)
    light.set_folder_path(unreal.Name('OldTownSchoolStreet/StreetLighting'))
    c=light.get_component_by_class(unreal.PointLightComponent)
    c.set_editor_property('intensity_units',unreal.LightUnits.LUMENS)
    c.set_editor_property('intensity',900.)
    c.set_editor_property('attenuation_radius',1100.)
    c.set_editor_property('light_color',unreal.Color(255,221,174,255))
    c.set_editor_property('cast_shadows',True)
    light_positions[name]=pos

# Source windows and integrated service lights must not remain emissive.
bad=['M_OTS_FluorescentTube','M_OTS_WarmWindow','M_OTS_CoolWindow','M_OTS_NeutralWindow']
dark=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_DarkGlass')
trim=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_DarkTrim')
assert dark and trim
material_changes=[]
for actor in sub.get_all_level_actors():
    if actor.get_actor_label() in lamp_positions:
        continue
    for c in actor.get_components_by_class(unreal.StaticMeshComponent):
        for slot in range(c.get_num_materials()):
            m=c.get_material(slot)
            if m and m.get_name() in bad:
                c.set_material(slot,trim if m.get_name()=='M_OTS_FluorescentTube' else dark)
                material_changes.append({'actor':actor.get_actor_label(),'slot':slot,'old':m.get_name()})

east=next(b for b in build['buildings']['buildings'] if b['label']==EAST)
delta=[9000.-east['world_min'][0],0.,0.]
for actor in sub.get_all_level_actors():
    label=actor.get_actor_label()
    if label.startswith('OTS_Enterable_'+EAST+'_') or label.startswith('OTS_Blender_'+EAST+'_') or label.startswith('OTS_PerimeterBoundaryWindowEast') or label.startswith('OTS_PerimeterBoundaryCapEast') or label.startswith('OTS_P2Prop_WallUtilityCluster_05_'):
        p=actor.get_actor_location()
        actor.set_actor_location(unreal.Vector(p.x+delta[0],p.y,p.z),False,False)
translate_data(east,delta)
east['public_route']=[[1000.,0.,1.],[7900.,0.,1.],[7900.,158.,1.],[9125.,158.,11.]]
for collection in (build['buildings']['structural_boxes'],build['buildings']['stair_side_panels'],plan['audit_expectations']['stair_side_panels']):
    for row in collection:
        if row.get('building')==EAST or str(row.get('actor','')).startswith('OTS_Enterable_'+EAST+'_'):
            translate_data(row,delta)
for item in plan['building_transforms']:
    if item['building']==EAST:
        item['translation_cm'][0]+=delta[0]
        item['world_min'][0]+=delta[0]
        item['world_max'][0]+=delta[0]
for label,translation in plan['actor_translations'].items():
    if label==EAST or label.startswith('OTS_PerimeterBoundaryWindowEast') or label.startswith('OTS_PerimeterBoundaryCapEast'):
        translation[0]+=delta[0]
for row in plan['translated_inventory']['actors']:
    if row['label']==EAST or row['label'].startswith('OTS_PerimeterBoundaryWindowEast') or row['label'].startswith('OTS_PerimeterBoundaryCapEast'):
        row['location'][0]+=delta[0]
        for mesh in row.get('meshes',[]):
            mesh['world_origin'][0]+=delta[0]
entry=next(e for e in plan['building_entrances'] if e['building']==EAST)
entry['outdoor_route']=copy.deepcopy(east['public_route'])

source=json.loads((OUT/'SourceInventory.json').read_text(encoding='utf-8'))
source_by={row['label']:row for row in source['actors']}
attachment_patterns=('OTS_StreetEndFocalUpperWindow*','OTS_StreetEndFocalFloorCourse*','OTS_StreetEndFocalCornice*',
                     'OTS_StreetEndWindow_East_*','OTS_P3Prop_SignAssemblyStreetEnd*','OTS_P3Prop_SignTextStreetEnd*','OTS_P3Prop_AwningAssemblyStreetEnd*')
attachment_positions={}
for actor in sub.get_all_level_actors():
    label=actor.get_actor_label()
    if label.startswith('OTS_P2Prop_WallUtilityCluster_05_') or label.startswith('OTS_PerimeterBoundaryWindowEast') or label.startswith('OTS_PerimeterBoundaryCapEast'):
        attachment_positions[label]=xyz(actor.get_actor_location())
    if any(fnmatch.fnmatchcase(label,p) for p in attachment_patterns):
        pos=list(source_by[label]['location'])
        pos[0]+=2420.
        actor.set_actor_location(unreal.Vector(*pos),False,False)
        attachment_positions[label]=pos
    elif label.startswith('OTS_StreetEndWindow_North_') or label.startswith('OTS_StreetEndWindow_South_'):
        pos=list(source_by[label]['location'])
        pos[1]+=320. if 'North' in label else -320.
        actor.set_actor_location(unreal.Vector(*pos),False,False)
        attachment_positions[label]=pos

replacements={
 'BaseGround':surface('BaseGround',[-6800.,-4300.,10700.,4300.],-1.),
 'MainRoad':surface('MainRoad',[-600.,-350.,8250.,350.],1.,700.),
 'EastCrossRoad':surface('EastCrossRoad',[7550.,-2075.,8250.,2075.],1.,700.),
 'MainWalkNorth':surface('MainWalkNorth',[100.,350.,7550.,530.],11.,120.,[100.,350.,7550.,470.]),
 'MainWalkSouth':surface('MainWalkSouth',[100.,-530.,7550.,-350.],11.,120.,[100.,-470.,7550.,-350.]),
 'RearLaneNorth':surface('RearLaneNorth',[280.,1755.,8250.,2075.],11.,320.),
 'RearLaneSouth':surface('RearLaneSouth',[280.,-2075.,8250.,-1755.],11.,320.),
 'EastBoundaryWalk':surface('EastBoundaryWalk',[8250.,-2075.,8430.,2075.],11.,120.,[8250.,-2075.,8370.,2075.])}
new_surface_names={'EastShopForecourt','EastJunctionWestWalkNorth','EastJunctionWestWalkSouth','EastNorthTurnCurb','EastSouthTurnCurb'}
plan['ground_surfaces']=[replacements.get(s['name'],s) for s in plan['ground_surfaces'] if s['name'] not in new_surface_names]
plan['ground_surfaces'] += [surface('EastShopForecourt',[8430.,-3500.,9000.,3500.]),
                           surface('EastJunctionWestWalkNorth',[7370.,530.,7550.,1755.]),
                           surface('EastJunctionWestWalkSouth',[7370.,-1755.,7550.,-530.]),
                           surface('EastNorthTurnCurb',[7550.,2075.,8430.,2255.]),
                           surface('EastSouthTurnCurb',[7550.,-2255.,8430.,-2075.])]
gap_closures=[]
for name,x0,x1,sign in (('South01',1300.,1450.,-1.),('South02',3440.,3590.,-1.),
                         ('South03',4590.,4740.,-1.),('North01',3690.,3840.,1.),('North02',4840.,4990.,1.)):
    y0,y1=sorted((530.*sign,550.*sign))
    row={'name':'ClosedServiceGap'+name,'world_min':[x0,y0,1.],
         'world_max':[x1,y1,301.],'purpose':'wall infill; not a public alley'}
    if not any(w['name']==row['name'] for w in plan['replacement_party_walls']):
        plan['replacement_party_walls'].append(row)
    gap_closures.append(row)
plan['closed_service_gaps']=gap_closures
for actor in list(sub.get_all_level_actors()):
    if actor.get_actor_label().startswith('OTS_RoadRevision_'):
        assert sub.destroy_actor(actor)
build['roads']=emit_roads(sub,plan)
build['buildings']['world_ground_rect']=[-6800.,-4300.,10700.,4300.]
plan['lighting_policy']='street_lamps_only'
plan['layout']['world_ground_rect']=[-6800.,-4300.,10700.,4300.]
plan['layout']['east_facade_front_x_cm']=9000.
plan['layout']['east_junction']={'carriageway_width_cm':700.,'east_facade_x_cm':9000.,'setback_after_sidewalk_cm':570.}

camera_specs=[('CAM_Cleanup_MainStreet',[5000.,0.,166.],[8300.,0.,166.],60.),
              ('CAM_Cleanup_Junction',[7000.,0.,166.],[8450.,0.,166.],70.),
              ('CAM_Cleanup_FormerLampGap',[3300.,-180.,176.],[3515.,-700.,176.],60.),
              ('CAM_Cleanup_TurnNorth',[7900.,1200.,166.],[7150.,1915.,176.],70.),
              ('CAM_Cleanup_RoadPlan',[1950.,0.,18000.],[1950.,0.,0.],60.)]
for name,pos,target,fov in camera_specs:
    rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*pos),unreal.Vector(*target))
    if name.endswith('RoadPlan'):
        rot=unreal.Rotator(pitch=rot.pitch,yaw=rot.yaw,roll=90.)
    actor=by.get(name) or sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*pos),rot,False)
    actor.set_actor_label(name)
    actor.set_actor_location(unreal.Vector(*pos),False,False)
    actor.set_actor_rotation(rot,False)
    actor.set_folder_path(unreal.Name('OldTownSchoolStreet/LightingCleanupReview'))
    c=actor.get_component_by_class(unreal.CameraComponent)
    c.set_editor_property('field_of_view',fov)
    pp=c.get_editor_property('post_process_settings')
    pp.set_editor_property('override_auto_exposure_bias',True)
    pp.set_editor_property('auto_exposure_bias',1.0)
    c.set_editor_property('post_process_settings',pp)
    c.set_editor_property('post_process_blend_weight',1.)

build['lighting_cleanup']={'allowed_scene_light_labels':allowed,'ui_only_light_actor':'BP_InventoryCharacterPreview',
    'removed_actor_labels':removed,'lamp_positions':lamp_positions,'light_expected_positions':light_positions,
    'emissive_disallowed_materials':bad,'material_overrides':material_changes}
build['street_end_cleanup']={'junction_routes':[
    {'name':'TurnNorth','waypoints_cm':[[6900.,0.,1.],[7900.,0.,1.],[7900.,1915.,11.],[6800.,1915.,11.],[6200.,1915.,11.]]},
    {'name':'TurnSouth','waypoints_cm':[[6900.,0.,1.],[7900.,0.,1.],[7900.,-1915.,11.],[6800.,-1915.,11.],[6200.,-1915.,11.]]}],
    'east_building_label':EAST,'east_building_world_min':east['world_min'],'east_building_world_max':east['world_max'],
    'attachment_expected_positions':attachment_positions,
    'closed_service_gaps':gap_closures,
    'road_surface_expectations':[{'actor':'OTS_RoadRevision_'+s['name'],'world_min':s['world_min'],'world_max':s['world_max']}
                                 for s in plan['ground_surfaces'] if s['name'] in replacements or s['name']=='EastShopForecourt']}
build['cleanup_review_cameras']=[s[0] for s in camera_specs]
actors=list(sub.get_all_level_actors())
refresh_world_collision(actors)
assert validate_main_home(actors)==build['main_home']
build['collision']=validate_buildings(world,actors,build['buildings'])
write('CollisionValidation.json',build['collision'])
assert build['collision']['passed'],'Building collision or connectivity failed'
revision=audit_revision(world,actors,build,plan)
write('RevisionAudit.json',revision)
assert revision['passed'],revision['errors']
cleanup=audit_cleanup(world,actors,build)
write('LightingCleanupAudit.json',cleanup)
assert cleanup['passed'],cleanup['errors']
assert levels.save_current_level(),'Could not save authorized target'
build['actor_count']=len(actors)
build['revision_audit']=revision
baseline_file=WORK/'ProtectedMapBaseline.json'
if baseline_file.exists():
    baseline=json.loads(baseline_file.read_text(encoding='utf-8'))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in baseline['sha256'].items())
    build['protected_map_sha256']=baseline['sha256']
    build['protected_map_baseline_note']=baseline['note']
build['map_sha256']=hashlib.sha256(MAP.read_bytes()).hexdigest()
write('BuildReport.json',build)
write('BuildingReport.json',build['buildings'])
write('RevisionPlan.json',plan)
write('LightingCleanupReport.json',{'status':'PASS','map_sha256':build['map_sha256'],
    'actor_count':len(actors),'lighting_cleanup':build['lighting_cleanup'],'street_end_cleanup':build['street_end_cleanup']})
unreal.SystemLibrary.execute_console_command(world,'MAP CHECK DONTDISPLAYDIALOG NOCLEARLOG')
unreal.log('OTS_LIGHT_ROAD_CLEANUP_SUCCESS '+build['map_sha256'])
