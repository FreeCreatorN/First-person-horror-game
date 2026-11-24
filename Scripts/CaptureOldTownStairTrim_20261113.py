"""Capture the repaired stair using the viewport saved with the request."""
import json
import sys
import time
from pathlib import Path
import unreal

sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from ApplyOldTownStairTrim_20261113 import MAP, OUTPUT, load, read, sha

started = time.monotonic()
task = None
frames = 0
image = OUTPUT/'NorthStair_After.png'


def tick(_):
    global task, frames
    try:
        frames += 1
        if task is None and frames >= 35:
            task = unreal.AutomationLibrary.take_high_res_screenshot(1000,1080,str(image),camera,False,False)
        if task is not None and task.is_task_done() and image.is_file() and image.stat().st_size > 20000:
            assert sha(MAP)==read('Applied.json')['saved_sha256']
            unreal.log('OLDTOWN_STAIR_TRIM_CAPTURE_OK')
            finish()
        elif time.monotonic()-started>85:
            unreal.log_error('Stair screenshot timed out')
            finish()
    except Exception as exc:
        unreal.log_error(str(exc))
        finish()


def finish():
    le.eject_pilot_level_actor()
    ae.destroy_actor(camera)
    unreal.unregister_slate_post_tick_callback(handle)
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


assert sha(MAP)==read('Applied.json')['saved_sha256']
le, ae, world = load()
view = read('Inspection.json')['viewport'][0]
pitch,yaw,roll = view['rotation']
camera = ae.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*view['position']),unreal.Rotator(pitch=pitch,yaw=yaw,roll=roll),True)
assert camera
camera.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',90.0)
le.pilot_level_actor(camera)
unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_UNLIT)
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
handle = unreal.register_slate_post_tick_callback(tick)
