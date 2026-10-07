"""Replace phase-owned door instances; mechanics tests use disposable copies."""
import sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from ApplyOldTownHotelArchitecture import read,write,sha,WORK,TAG
from AuditOldTownHotelArchitecture import audit
from ValidateEnterableStreet import refresh_world_collision
build=read(WORK/'BuildReport.json')
mapfile=ROOT/('Content/'+build['target_level'].removeprefix('/Game/')+'.umap')
assert sha(mapfile)==build['map_sha256']
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert level.load_level(build['target_level'])
sub=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
by={a.get_actor_label():a for a in sub.get_all_level_actors()}
for row in build['hotel_architecture']['placed_doors']:
    old=by[row['actor']]
    assert TAG in [str(t) for t in old.tags]
    assert sub.destroy_actor(old)
    cls=unreal.EditorAssetLibrary.load_blueprint_class(row['blueprint'])
    a=sub.spawn_actor_from_class(cls,unreal.Vector(*row['actor_position_cm']),
                               unreal.Rotator(pitch=0,yaw=row['yaw'],roll=0),False)
    a.set_actor_label(row['actor'])
    a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelArchitecture/Doors'))
    a.set_editor_property('tags',[unreal.Name(TAG)])
actors=list(sub.get_all_level_actors())
profiles=[(c,str(c.get_collision_profile_name())) for a in actors for c in a.get_components_by_class(unreal.PrimitiveComponent)]
refresh_world_collision(actors)
for c,p in profiles:
    if p!='Custom' and str(c.get_collision_profile_name())!=p:c.set_collision_profile_name(p)
report=audit(world,actors,build)
write('DoorRestoreAudit.json',report)
assert report['passed'],report['errors'][:10]
assert level.save_current_level()
old_hash=build['map_sha256']
build['map_sha256']=sha(mapfile)
write('BuildReport.json',build)
write('DoorRestore.json',dict(passed=True,source_map_sha256=old_hash,map_sha256=build['map_sha256'],
    doors=108,mechanical_test_policy='Disposable actors outside the building; never mutate saved door instances.'))
unreal.log('HOTEL_ARCHITECTURE_DOOR_RESTORE_PASS '+build['map_sha256'])
