"""Capture actual simulation frames and confirm the emitter stays active."""
import json
import sys
import time
import traceback
from pathlib import Path

import unreal

root = Path(unreal.Paths.project_dir()).resolve()
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.get_current_level().get_outermost().get_path_name() == '/Game/Yastar/Maps/L_GreenPortal'
assert not levels.is_in_play_in_editor()
started = time.monotonic()
state = {'task':None, 'next':started+6.0, 'samples':[]}
fit_check = '--fit-check' in sys.argv[1:]
particle_check = '--particle-speed' in sys.argv[1:]
prefix = 'GreenPortalCharacterFit' if fit_check else (
    'GreenPortalParticleSpeed' if particle_check else (
        'GreenPortalOpenTop' if '--open-top' in sys.argv[1:] else 'GreenPortalReference'))
sample_count = 5 if fit_check else 2
report = root / ('Saved/'+prefix+'Capture.json')

def finish(error=None):
    levels.editor_request_end_play()
    unreal.unregister_slate_post_tick_callback(state['handle'])
    report.write_text(json.dumps({'error':error,'samples':state['samples']},indent=2),encoding='utf-8')
    if error:
        unreal.log_error(error)

def tick(_delta):
    try:
        now = time.monotonic()
        if now-started > 120:
            raise RuntimeError('Screenshot timeout')
        if state['samples']:
            previous = state['samples'][-1]
            path = Path(previous['path'])
            if not path.exists() or path.stat().st_mtime < previous['requested_at']:
                return
            if len(state['samples']) >= sample_count:
                finish()
                return
        if now < state['next']:
            return
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        camera=next(actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.CameraActor)
                    if actor.get_actor_label()=='Portal preview camera')
        candidates = unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)
        portal=next(actor for actor in candidates if actor.get_actor_label()=='Green extraction point')
        assert portal.get_component_by_class(unreal.NiagaraComponent).is_active()
        index = len(state['samples'])
        size = 1254
        if fit_check and 0 < index < 4:
            # The simulation copy of the camera moves by a fraction of a pixel.
            camera.set_actor_location(unreal.Vector(-14.0+1.25*(index-1),-2900.0,245.0),False,False)
            camera.set_actor_rotation(unreal.Rotator(pitch=-3.2,yaw=90.0,roll=0.0),False)
            size = 900
        elif fit_check and index == 4:
            # Compare the actual pose to the inner edge of the floor ring.
            # Both transforms are on the play-world copies only.
            mannequin = next(actor for actor in candidates if actor.get_actor_label()=='Preview - 180cm reference')
            center = portal.get_actor_location()
            ground = mannequin.get_actor_location().z
            assert mannequin.set_actor_location(unreal.Vector(center.x,center.y,ground),False,True)
            camera.set_actor_location(unreal.Vector(center.x,center.y-110.0,center.z+480.0),False,False)
            camera.set_actor_rotation(unreal.Rotator(pitch=-77.0,yaw=90.0,roll=0.0),False)
            size = 900
        position = camera.get_actor_location()
        path = root / ('Saved/%s_UE_%s.png' % (prefix,'ABCDE'[index]))
        requested = time.time()
        # A screenshot can pump Slate while it renders. Record the pending
        # capture before entering that call so a nested tick cannot repeat it.
        state['next']=now+3.0
        state['samples'].append({'time':unreal.GameplayStatics.get_time_seconds(world),
                                 'requested_at':requested,
                                 'camera_cm':[position.x,position.y,position.z],
                                 'niagara_active':True,'path':str(path)})
        state['task']=unreal.AutomationLibrary.take_high_res_screenshot(size,size,str(path),camera,False,False)
    except Exception:
        finish(traceback.format_exc())

levels.editor_play_simulate()
state['handle']=unreal.register_slate_post_tick_callback(tick)
