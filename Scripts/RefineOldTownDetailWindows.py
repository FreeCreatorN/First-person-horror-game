"""Finish the window mullions and readable review-camera distance in the saved detail phase."""
import hashlib,json,sys
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from PolishOldTownDetails import (PROJECT,OUT,WORK,SOURCE,MAP,TARGET,read,write,import_meshes,actor_bounds)
from ConvertOldTownBuildings import plan_buildings
from ValidateEnterableStreet import refresh_world_collision
from AuditOldTownDetailPolish import audit_details
build=read(OUT/'BuildReport.json');plan=read(OUT/'RevisionPlan.json')
assert hashlib.sha256(MAP.read_bytes()).hexdigest()==build['map_sha256']
assert all(hashlib.sha256(__import__('pathlib').Path(p).read_bytes()).hexdigest()==h for p,h in build['protected_map_sha256'].items())
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert levels.load_level(TARGET)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);by={a.get_actor_label():a for a in sub.get_all_level_actors()}
assets,imports,axes=import_meshes(world,force=True)
build['detail_polish']['imports']=imports;build['detail_polish']['axes']=axes
for row in build['detail_polish']['visuals']:
    a=by[row['actor']];box=actor_bounds(a);row['world_min'],row['world_max']=box
    if row['kind']=='inner_trim':row['window_grid']='four_panes_with_3cm_mullions';row['finish']='existing_worn_wood_material'
b=next(b for b in plan_buildings([],plan) if b.label=='BLK_L_Enter_C_Mass')
w=next(w for w in build['architecture_seal']['windows'] if w['building']==b.label and w['floor']==0)
specs=[('CAM_Polish_InnerTrim',b.world(w['u'],320.,w['z']+15),b.world(w['u'],15,w['z']),60.),
       ('CAM_Polish_DoorWindow',b.world(-85,-360,b.ground+155),b.world(15,70,b.ground+145),70.)]
for name,pos,target,fov in specs:
    a=by[name];rot=unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*pos),unreal.Vector(*target))
    a.set_actor_location(unreal.Vector(*pos),False,False);a.set_actor_rotation(rot,False)
    a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',fov)
actors=list(sub.get_all_level_actors());refresh_world_collision(actors)
report=audit_details(world,actors,build,plan);write('DetailPolishAudit.json',report);assert report['passed'],report['errors']
assert levels.save_current_level()
h=hashlib.sha256(MAP.read_bytes()).hexdigest()
build['map_sha256']=h;build['detail_polish']['map_sha256']=h;build['architecture_seal']['map_sha256']=h
write('BuildReport.json',build);write('BuildingReport.json',build['buildings']);write('RevisionPlan.json',plan)
unreal.log('OTS_DETAIL_WINDOW_FINISH_SUCCESS '+h)
