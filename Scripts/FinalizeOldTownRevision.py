"""Finish owned wires/camera review changes in the saved revision only."""
import hashlib
import json
from pathlib import Path
import sys
import unreal

PROJECT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(PROJECT/'Scripts'))
from ReviseOldTownLayout import TARGET,MAP_FILE,OUTPUT,REVISION,write,adjust_overhead_wires
from ValidateEnterableStreet import refresh_world_collision,validate_buildings,validate_main_home
from AuditOldTownRevision import audit_revision

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level(TARGET)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().startswith(TARGET+'.')
subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
build=json.loads((OUTPUT/'BuildReport.json').read_text(encoding='utf-8'))
plan=json.loads((OUTPUT/'RevisionPlan.json').read_text(encoding='utf-8'))
build['overhead_wire_adjustments']=adjust_overhead_wires(subsystem)
adjustments_file=REVISION/'CameraAdjustments.json'
if adjustments_file.exists():
    by_label={a.get_actor_label():a for a in subsystem.get_all_level_actors()}
    for adjustment in json.loads(adjustments_file.read_text(encoding='utf-8')):
        actor=by_label[adjustment['camera']]
        if 'position_cm' in adjustment:
            position,target=adjustment['position_cm'],adjustment['target_cm']
            actor.set_actor_location(unreal.Vector(*position),False,False)
            actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position),unreal.Vector(*target)),False)
        if 'roll_degrees' in adjustment:
            rotation=actor.get_actor_rotation()
            actor.set_actor_rotation(unreal.Rotator(pitch=rotation.pitch,yaw=rotation.yaw,roll=adjustment['roll_degrees']),False)
        c=actor.get_component_by_class(unreal.CameraComponent)
        if 'fov_degrees' in adjustment:
            c.set_editor_property('field_of_view',adjustment['fov_degrees'])
        if 'exposure_bias' in adjustment:
            pp=c.get_editor_property('post_process_settings')
            pp.set_editor_property('override_auto_exposure_bias',True)
            pp.set_editor_property('auto_exposure_bias',adjustment['exposure_bias'])
            c.set_editor_property('post_process_settings',pp)
            c.set_editor_property('post_process_blend_weight',1.)
    build['camera_adjustments']=json.loads(adjustments_file.read_text(encoding='utf-8'))
actors=list(subsystem.get_all_level_actors())
refresh_world_collision(actors)
assert validate_main_home(actors)==build['main_home']
build['collision']=validate_buildings(world,actors,build['buildings'])
write('CollisionValidation.json',build['collision'])
assert build['collision']['passed']
audit=audit_revision(world,actors,build,plan)
write('RevisionAudit.json',audit)
assert audit['passed'],audit['errors']
assert levels.save_current_level()
build['map_sha256']=hashlib.sha256(MAP_FILE.read_bytes()).hexdigest()
build['revision_audit']=audit
write('BuildReport.json',build)
unreal.SystemLibrary.execute_console_command(world,'MAP CHECK DONTDISPLAYDIALOG NOCLEARLOG')
unreal.log('OTS_REVISION_FINALIZE_SUCCESS '+build['map_sha256'])
