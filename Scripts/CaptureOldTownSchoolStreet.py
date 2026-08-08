"""Capture deterministic comparison views from the generated UE5 scene."""

from pathlib import Path
import time
import traceback

import unreal


TARGET_LEVEL = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
CAMERA_LABELS = (
    "CAM_OTS_Hero",
    "CAM_OTS_MainHome",
    "CAM_OTS_Alley",
    "CAM_OTS_StreetDiagonal",
    "CAM_OTS_TopDown",
)
OUTPUT_ROOT = (
    Path(unreal.Paths.project_dir()).resolve()
    / "Saved/CodexOutputs/OldTownSchoolStreet/Renders"
)
WIDTH = 1600
HEIGHT = 900
WARMUP_FRAMES = 180
BETWEEN_CAMERA_FRAMES = 90
TIMEOUT_SECONDS = 90.0

_state = {
    "tick_handle": None,
    "task": None,
    "index": 0,
    "frames": 0,
    "started_at": time.time(),
    "current_path": None,
    "cameras": [],
    "starting": False,
}


def cleanup():
    handle = _state.get("tick_handle")
    if handle is not None:
        try:
            unreal.unregister_slate_post_tick_callback(handle)
        except Exception:
            pass
        _state["tick_handle"] = None
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def fail(message):
    unreal.log_error("OTS_CAPTURE_FAILED {}".format(message))
    cleanup()


def start_next_capture():
    if _state["starting"]:
        return
    _state["starting"] = True
    index = _state["index"]
    if index >= len(_state["cameras"]):
        unreal.log(
            "OTS_CAPTURE_SUCCESS count={} output={}".format(
                len(_state["cameras"]),
                OUTPUT_ROOT,
            )
        )
        _state["starting"] = False
        cleanup()
        return
    camera = _state["cameras"][index]
    label = camera.get_actor_label()
    output_path = OUTPUT_ROOT / "{}.png".format(label)
    if output_path.exists():
        output_path.unlink()
    _state["current_path"] = output_path
    _state["started_at"] = time.time()
    _state["task"] = unreal.AutomationLibrary.take_high_res_screenshot(
        WIDTH,
        HEIGHT,
        str(output_path),
        camera,
        False,
        False,
        unreal.ComparisonTolerance.LOW,
        "OldTownSchoolStreet deterministic comparison view",
        0.35,
        True,
    )
    _state["starting"] = False
    unreal.log(
        "OTS_CAPTURE_STARTED {} {}".format(label, output_path)
    )


def on_tick(_delta_seconds):
    try:
        if _state["task"] is None:
            _state["frames"] += 1
            needed = (
                WARMUP_FRAMES
                if _state["index"] == 0
                else BETWEEN_CAMERA_FRAMES
            )
            if _state["frames"] >= needed:
                _state["frames"] = 0
                start_next_capture()
            return

        task = _state["task"]
        if not task.is_valid_task():
            fail("Automation screenshot task became invalid")
            return
        if task.is_task_done():
            output_path = _state["current_path"]
            if (
                output_path is None
                or not output_path.is_file()
                or output_path.stat().st_size < 20000
            ):
                fail("Screenshot file is missing or too small: {}".format(
                    output_path
                ))
                return
            unreal.log(
                "OTS_CAPTURE_DONE {} bytes={}".format(
                    output_path.name,
                    output_path.stat().st_size,
                )
            )
            _state["task"] = None
            _state["starting"] = False
            _state["index"] += 1
            _state["frames"] = 0
            return
        if time.time() - _state["started_at"] > TIMEOUT_SECONDS:
            fail("Screenshot timed out")
    except Exception:
        fail(traceback.format_exc())


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for label in CAMERA_LABELS:
        output_path = OUTPUT_ROOT / "{}.png".format(label)
        if output_path.exists():
            output_path.unlink()
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not level.load_level(TARGET_LEVEL):
        raise RuntimeError("Unable to load {}".format(TARGET_LEVEL))
    try:
        viewport_keys = list(level.get_viewport_config_keys())
    except Exception:
        viewport_keys = ["unknown"]
    if not viewport_keys:
        unreal.log_error("OTS_CAPTURE_NO_VIEWPORT")
        return

    by_label = {
        actor.get_actor_label(): actor
        for actor in actors.get_all_level_actors()
    }
    missing = [label for label in CAMERA_LABELS if label not in by_label]
    if missing:
        raise RuntimeError("Missing cameras: {}".format(missing))
    _state["cameras"] = [by_label[label] for label in CAMERA_LABELS]
    # Prevent editor selection outlines from contaminating deterministic renders.
    actors.set_selected_level_actors([])

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _state["tick_handle"] = unreal.register_slate_post_tick_callback(
        on_tick
    )
    unreal.log(
        "OTS_CAPTURE_READY cameras={} resolution={}x{}".format(
            len(_state["cameras"]),
            WIDTH,
            HEIGHT,
        )
    )


try:
    main()
except Exception:
    unreal.log_error("OTS_CAPTURE_FAILED\n{}".format(traceback.format_exc()))
    cleanup()
    raise
