"""Apply the authorized joint, stair enclosure and door/window refinement."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(PROJECT/'Scripts'))
from ConvertOldTownBuildings import (MeshFactory,plan_buildings,_subtract_box,
                                     _emit_closed_stair_sides)
from OldTownArchitectureSealPlan import (window_plan,sealed_local_box,door_leaf_plan,
                                          door_world_box,LAP)
from ValidateEnterableStreet import refresh_world_collision,validate_buildings,validate_main_home
from AuditOldTownRevision import audit_revision
from AuditOldTownLightingCleanup import audit_cleanup

TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
OUT = PROJECT/'Saved/CodexOutputs/EnterableStreet_20261002'
WORK = PROJECT/'Saved/CodexOutputs/ArchitectureSeal_20261004'
MAP = PROJECT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
NEW_TAG = 'OTS_ArchitectureSeal_20261004'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(name,data):
    for folder in (OUT,WORK):
        (folder/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def xyz(v):
    return [float(v.x),float(v.y),float(v.z)]

def local_box(b,lo,hi):
    a,c=b.local(lo),b.local(hi)
    return [min(a[i],c[i]) for i in range(3)],[max(a[i],c[i]) for i in range(3)]

def set_box(actor,low,high):
    actor.set_actor_location(unreal.Vector(*[(low[i]+high[i])*.5 for i in range(3)]),False,False)
    actor.set_actor_scale3d(unreal.Vector(*[(high[i]-low[i])/100. for i in range(3)]))

WORK.mkdir(parents=True,exist_ok=True)
before=WORK/'Before'
build=read(OUT/'BuildReport.json')
plan=read(OUT/'RevisionPlan.json')
current_hash=hashlib.sha256(MAP.read_bytes()).hexdigest()
assert current_hash==build['map_sha256'], 'Saved map changed outside the current build report'
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
           for p,h in build['protected_map_sha256'].items())
if not before.exists():
    before.mkdir()
    shutil.copy2(MAP,before/MAP.name)
    for name in ('BuildReport.json','BuildingReport.json','RevisionPlan.json','SavedVerification.json',
                 'FinalReview.json','RevisionAudit.json','LightingCleanupAudit.json'):
        shutil.copy2(OUT/name,before/name)
    shutil.copytree(OUT/'Renders',before/'Renders')
baseline=read(before/'BuildReport.json')
assert current_hash in (baseline['map_sha256'],build.get('architecture_seal',{}).get('map_sha256')), 'Unrecognized refinement state'
baseline_structure=baseline['buildings']
geometry=plan_buildings([],plan)
by_building={b.label:b for b in geometry}
reports={r['label']:r for r in build['buildings']['buildings']}

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level(TARGET)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().startswith(TARGET+'.')
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors=list(sub.get_all_level_actors())
by={a.get_actor_label():a for a in actors}
baseline_by={r['actor']:r for r in baseline_structure['structural_boxes']}
removed=[]
for actor in actors:
    name=actor.get_actor_label()
    old=baseline_by.get(name,{})
    attached_meshes=[c.static_mesh for c in actor.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh]
    has_window_mesh=any('/Windows/' in m.get_path_name() or 'Window_' in m.get_name() for m in attached_meshes)
    replace_window=(('Window' in name or has_window_mesh) and not name.startswith('OTS_MainHome')
                    and bool(attached_meshes))
    replace_door=name.startswith('OTS_P1DoorJamb') or name.startswith('OTS_P1DoorLintel')
    if (NEW_TAG in {str(t) for t in actor.tags} or old.get('role') in ('StairSidePanel','StairGuard','WallPanel')
            or replace_window or replace_door):
        assert sub.destroy_actor(actor),name
        removed.append(name)
structure=deepcopy(baseline_structure)
retained=[r for r in structure['structural_boxes'] if r['actor'] in by and r['actor'] not in removed
          and r['role'] not in ('WallPanel','StairSidePanel','StairGuard')]
factory=MeshFactory(sub)
factory.count=baseline_structure['generated_actor_count']
factory.lighting_policy='street_lamps_only'
seams=[]
for row in retained:
    if row['role'] not in ('FloorSlab','RoofSlab'):
        continue
    b=by_building.get(row['building'])
    if not b:
        continue
    old_low,old_high=local_box(b,row['min'],row['max'])
    low,high=sealed_local_box(b,row['role'],old_low,old_high)
    world_low,world_high=b.world_box(low,high)
    if [low,high] != [old_low,old_high]:
        set_box(by[row['actor']],world_low,world_high)
        row['min'],row['max']=world_low,world_high
        seams.append(deepcopy(row))

windows=[w for b in geometry for w in window_plan(b)]
for row in baseline_structure['structural_boxes']:
    if row['role'] != 'WallPanel':
        continue
    b=by_building[row['building']]
    lo,hi=local_box(b,row['min'],row['max'])
    lo,hi=sealed_local_box(b,'WallPanel',lo,hi)
    pieces=[(lo,hi)]
    for w in (w for w in windows if w['building']==b.label):
        pieces=[part for a,c in pieces for part in _subtract_box(a,c,w['local_min'],w['local_max'])]
    material=unreal.load_asset(b.row['meshes'][0]['materials'][0])
    assert material
    for a,c in pieces:
        factory.box(b,'WallPanel',a,c,material)

panels=[]
for b in geometry:
    if b.count > 1:
        for level in range(b.count-1):
            coverage=_emit_closed_stair_sides(factory,b,level)
            reports[b.label]['stairs'][level]['side_panel_coverage']=coverage
        panels.extend(b.stair_side_panels)
    reports[b.label]['stair_side_panels']=b.stair_side_panels

dark=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_DarkGlass')
trim=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_DarkTrim')
rust=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_RustMetal')
assert dark and trim and rust
window_asset=unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Architecture/Windows/SM_OTS_Window_Residential')
assert window_asset
for w in windows:
    b=by_building[w['building']]
    u,v,z=w['u'],w['v'],w['z']
    width,height=w['width'],w['height']
    sign=1. if w['wall']=='Front' else -1.
    yaw=(0. if b.inward>0. else 180.) if b.normal_axis==1 else (-90. if b.inward>0. else 90.)
    if w['wall']=='Rear':
        yaw+=180.
    actor=sub.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*b.world(u,v,z)),
                                    unreal.Rotator(pitch=0.,yaw=yaw,roll=0.),False)
    actor.set_actor_label('OTS_Seal_Window_'+w['name'])
    actor.set_folder_path(unreal.Name('OldTownSchoolStreet/ArchitectureRefinement/Windows'))
    actor.set_editor_property('tags',[unreal.Name(NEW_TAG)])
    actor.set_actor_scale3d(unreal.Vector(width/125.,1.,height/120.))
    c=actor.get_component_by_class(unreal.StaticMeshComponent)
    c.set_static_mesh(window_asset)
    # The existing module is non-emissive; explicitly keep closed glass dark.
    c.set_material(1,dark)
    c.set_collision_profile_name('NoCollision')
    w['actor']=actor.get_actor_label()
    w['location_cm']=b.world(u,v,z)
    w['scale']=[width/125.,1.,height/120.]
    w['yaw_degrees']=yaw
    # Full-depth reveals join the exterior frame and the interior wall face.
    n0,n1=sorted((v+sign*.0,v+sign*20.5))
    boxes=[([u-width*.5-3.,n0,z-height*.5],[u-width*.5,n1,z+height*.5]),
           ([u+width*.5,n0,z-height*.5],[u+width*.5+3.,n1,z+height*.5]),
           ([u-width*.5-3.,n0,z-height*.5-3.],[u+width*.5+3.,n1,z-height*.5]),
           ([u-width*.5-3.,n0,z+height*.5],[u+width*.5+3.,n1,z+height*.5+3.])]
    w['reveal_actors']=[]
    for a,corners in boxes:
        reveal=factory.box(b,'WindowReveal',a,corners,factory.floor_material)
        w['reveal_actors'].append(reveal.get_actor_label())
    g0,g1=sorted((v+sign*1.,v+sign*3.))
    glass=factory.box(b,'WindowGlass',[u-width*.5,g0,z-height*.5],[u+width*.5,g1,z+height*.5],dark)
    w['glass_actor']=glass.get_actor_label()

doors=[]
for b in geometry:
    p=b.portals[0]
    d=door_leaf_plan(b,reports[b.label])
    half=b.door_width*.5
    h=b.ground+b.door_height
    d['frame_actors']=[]
    for a,c in (([-half-5.,-.5,b.ground],[ -half,20.5,h]),
                ([half,-.5,b.ground],[half+5.,20.5,h]),
                ([-half-5.,-.5,h],[half+5.,20.5,h+5.])):
        lo,hi=door_world_box(b,p,a,c)
        frame=factory.world_box(b.label,'DoorFrame',lo,hi,trim)
        d['frame_actors'].append(frame.get_actor_label())
    leaf=factory.world_box(b.label,'DoorLeaf',d['world_min'],d['world_max'],factory.trim_material)
    d['actor']=leaf.get_actor_label()
    edge=d['hinge_side']*(b.door_width*.5-4.)
    a,c=[edge-4.,b.door_width-1.,b.ground+103.],[edge+4.,b.door_width+2.,b.ground+118.]
    lo,hi=door_world_box(b,p,a,c)
    handle=factory.world_box(b.label,'DoorHandle',lo,hi,rust,False)
    d['handle_actor']=handle.get_actor_label()
    doors.append(d)

spawned_by={a.get_actor_label():a for a in sub.get_all_level_actors()}
for row in factory.placed_boxes:
    actor=spawned_by[row['actor']]
    actor.set_editor_property('tags',list(actor.tags)+[unreal.Name(NEW_TAG)])
structure['structural_boxes']=retained+factory.placed_boxes
structure['generated_actor_count']=len(structure['structural_boxes'])
structure['module_actor_distribution']=dict(Counter(r['role'] for r in structure['structural_boxes']))
structure['generated_assets']=sorted(set(structure['generated_assets']+[m.get_path_name() for m in factory.modules.values()]))
structure['stair_side_panels']=panels
structure['buildings']=list(reports.values())
plan['audit_expectations']['stair_side_panels']=[{'actor':r['actor'],'world_min':r['world_min'],
    'world_max':r['world_max'],'material_contains':'OldGreen'} for r in panels]
plan['architecture_seal_policy']='rectangular_full_height_stairs_and_fitted_openings'
build['buildings']=structure
build['street_end_cleanup']['attachment_expected_positions']={k:v for k,v in
    build['street_end_cleanup']['attachment_expected_positions'].items() if k not in removed}
build['architecture_seal']={'joint_lap_cm':LAP,'seam_joint_boxes':seams,'stair_panel_count':len(panels),
    'windows':windows,'doors':doors,'removed_attachment_labels':removed,
    'door_behavior':'Single leaves fixed open 90 degrees; no new door interaction system'}

b=by_building['BLK_L_Enter_C_Mass']
first=next(w for w in windows if w['building']==b.label and w['floor']==0)
camera_specs=[('CAM_Seal_Stair',b.world(b.core_u,b.core_v-210.,b.ground+160.),
               b.world(b.core_u,b.core_v+130.,b.ground+175.),70.),
              ('CAM_Seal_DoorWindow',b.world(0.,-600.,b.ground+165.),b.world(0.,25.,b.ground+175.),70.),
              ('CAM_Seal_WindowInterior',b.world(first['u'],170.,b.ground+165.),
               b.world(first['u'],0.,first['z']),65.)]
for name,pos,target,fov in camera_specs:
    rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*pos),unreal.Vector(*target))
    actor=by.get(name) or sub.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*pos),rot,False)
    actor.set_actor_label(name)
    actor.set_actor_location(unreal.Vector(*pos),False,False)
    actor.set_actor_rotation(rot,False)
    actor.set_folder_path(unreal.Name('OldTownSchoolStreet/ArchitectureRefinement/Review'))
    actor.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',fov)
build['architecture_review_cameras']=[s[0] for s in camera_specs]+['CAM_Cleanup_Junction','CAM_Cleanup_TurnNorth']

actors=list(sub.get_all_level_actors())
refresh_world_collision(actors)
assert validate_main_home(actors)==build['main_home']
build['collision']=validate_buildings(world,actors,structure)
write('CollisionValidation.json',build['collision'])
assert build['collision']['passed'],'Refined geometry blocked an existing building route'
revision=audit_revision(world,actors,build,plan)
write('RevisionAudit.json',revision)
assert revision['passed'],revision['errors']
lighting=audit_cleanup(world,actors,build)
write('LightingCleanupAudit.json',lighting)
assert lighting['passed'],lighting['errors']
from AuditOldTownArchitectureSeal import audit_architecture
audit=audit_architecture(world,actors,build,plan)
write('ArchitectureSealAudit.json',audit)
assert audit['passed'],audit['errors']
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in build['protected_map_sha256'].items())
assert levels.save_current_level()
build['actor_count']=len(actors)
build['map_sha256']=hashlib.sha256(MAP.read_bytes()).hexdigest()
build['architecture_seal']['map_sha256']=build['map_sha256']
build['revision_audit']=revision
write('BuildReport.json',build)
write('BuildingReport.json',structure)
write('RevisionPlan.json',plan)
write('ArchitectureSealReport.json',{'status':'PASS','map_sha256':build['map_sha256'],
    'actor_count':len(actors),'stair_panels':len(panels),'door_leaves':len(doors),
    'window_modules':len(windows),'sealed_slab_joints':len(seams),'joint_lap_cm':LAP})
unreal.SystemLibrary.execute_console_command(world,'MAP CHECK DONTDISPLAYDIALOG NOCLEARLOG')
unreal.log('OTS_ARCHITECTURE_SEAL_SUCCESS '+build['map_sha256'])
