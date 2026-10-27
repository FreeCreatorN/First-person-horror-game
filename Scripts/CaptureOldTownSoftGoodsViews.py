"""Fresh-map inspection captures in an owned, unsaved editor helper.

Execute through -ExecutePythonScript; the companion PowerShell wrapper limits
each helper to four cameras. Temporary inspection lights are destroyed before
successful metadata is committed, and this script never saves a map.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import struct
import time
import traceback

import unreal

TARGET_LEVEL = os.environ.get('OTS_CAPTURE_LEVEL', "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet")
PROJECT = Path(unreal.Paths.project_dir()).resolve()
MAP_FILE = PROJECT / ('Content/'+TARGET_LEVEL.removeprefix('/Game/')+'.umap')
OUTPUT_ROOT = (PROJECT / "Saved/CodexOutputs").resolve()
if not OUTPUT_ROOT.is_relative_to(PROJECT):
    raise ValueError("Project Saved/CodexOutputs resolves outside the project")
_output_requested = Path(os.environ.get("OTS_CAPTURE_OUTPUT", str(
    OUTPUT_ROOT / "HotelOpenings_20261004")))
OUTPUT = (_output_requested if _output_requested.is_absolute() else PROJECT / _output_requested).resolve()
if OUTPUT == OUTPUT_ROOT or not OUTPUT.is_relative_to(OUTPUT_ROOT):
    raise ValueError("Capture output must stay below project Saved/CodexOutputs")
RENDERS = OUTPUT / "Renders"
BUILD_REPORT = Path(os.environ.get("OTS_CAPTURE_BUILD_REPORT", str(
    PROJECT / "Saved/CodexOutputs/EnterableStreet_20261002/BuildReport.json")))
WIDTH, HEIGHT = 1920, 1080
MAX_CAMERAS = 4
WARMUP_FRAMES, BETWEEN_CAMERA_FRAMES = 75, 40
TIMEOUT_SECONDS = 150.
TEMP_TAG = "TemporaryInspection"

_state = {
    "tick_handle": None, "task": None, "index": 0, "frames": 0,
    "starting": False, "closing": False, "map_sha256": None,
    "cameras": [], "temporary_actors": [], "temporary_actor_labels": [],
    "metadata_paths": [], "started_at": time.time(), "run_dir": None,
    "temporary_created_count": 0, "lighting_mode": None, "view_mode": None,
    "new_asset_sha256": {}, "source_build_report": None,
}


def _hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _spawn_light(actor_class, component_class, label, location, rotation, intensity,
                 color, casts_shadow, attenuation=None):
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_class(actor_class, unreal.Vector(*location),
                                          unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]), False)
    if actor is None:
        raise RuntimeError("Unable to create inspection light " + label)
    actor.set_actor_label(label)
    actor.set_editor_property("tags", [unreal.Name(TEMP_TAG), unreal.Name(_state["run_id"])])
    actor.set_folder_path(unreal.Name("OldTownSchoolStreet/TemporaryInspection"))
    # Track ownership immediately, including when subsequent property setup fails.
    _state["temporary_actors"].append(actor)
    _state["temporary_actor_labels"].append(label)
    _state["temporary_created_count"] += 1
    component = actor.get_component_by_class(component_class)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    if isinstance(component,unreal.PointLightComponent):
        component.set_editor_property('intensity_units',unreal.LightUnits.LUMENS)
    component.set_editor_property("intensity", intensity)
    component.set_editor_property("light_color", unreal.Color(*color))
    component.set_editor_property("cast_shadows", casts_shadow)
    if attenuation is not None:
        component.set_editor_property("attenuation_radius", attenuation)
    return actor


def _create_temporary_lighting():
    if _state["lighting_mode"] != "temporary":
        return
    prefix = "OTS_TemporaryInspection_" + _state["run_id"]
    _spawn_light(unreal.DirectionalLight, unreal.DirectionalLightComponent,
                 prefix + "_Key", [2500., -1500., 5000.], [-45., -35., 0.],
                 .8, [255, 247, 230, 255], True)
    _spawn_light(unreal.DirectionalLight, unreal.DirectionalLightComponent,
                 prefix + "_Fill", [2500., 1500., 5000.], [-35., 145., 0.],
                 .4, [220, 237, 255, 255], False)
    _spawn_light(unreal.PointLight, unreal.PointLightComponent,
                 prefix + "_HotelLobby", [9680., 158., 300.], [0., 0., 0.],
                 400., [255, 246, 232, 255], False, 1500.)
    _state["camera_fill"] = _spawn_light(
        unreal.PointLight, unreal.PointLightComponent, prefix + "_CameraFill",
        [2000., 0., 300.], [0., 0., 0.], 120., [242, 247, 255, 255], False, 1300.)


def _destroy_owned_temporary_lights():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    errors = []
    for actor in reversed(_state["temporary_actors"]):
        try:
            if not actors.destroy_actor(actor):
                errors.append("Destroy returned false for " + actor.get_actor_label())
        except Exception as error:
            errors.append(str(error))
    owned_labels = set(_state["temporary_actor_labels"])
    remaining = [a.get_actor_label() for a in actors.get_all_level_actors()
                 if a.get_actor_label() in owned_labels]
    return {"created_count": _state["temporary_created_count"],
            "destroyed_count": _state["temporary_created_count"] - len(remaining),
            "remaining_count": len(remaining), "remaining_labels": remaining,
            "errors": errors, "cleanup_verified_zero": not remaining and not errors,
            "actor_labels": _state["temporary_actor_labels"]}


def _request_shutdown():
    # Keep the editor lifecycle separate from capture validity. The wrapper can
    # tell whether a native shutdown call returned before its bounded cleanup.
    shutdown = {
        "run_id": _state.get("run_id"), "owned_editor_pid": os.getpid(),
        "method": "release_execute_python_keep_alive_and_defer_quit_editor",
        "status": "REQUESTING", "keep_alive_released": False,
        "deferred_quit_returned": False, "map_save_requested": False,
    }
    path = _state["run_dir"] / "ShutdownRequest.json" if _state["run_dir"] else None

    def record():
        if path is not None:
            try:
                _write(path, shutdown)
            except Exception:
                # Diagnostics must not prevent the actual shutdown request.
                shutdown["record_failure"] = traceback.format_exc()

    # This file is deliberately written before calling native APIs: a native
    # call that stalls still leaves a useful stage for the owning wrapper.
    record()
    try:
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        shutdown["keep_alive_released"] = True
        record()
        # QuitEditor must not close Slate on the active callback stack. The
        # engine's ExecutePythonScript runner also defers its automatic quit.
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world, "DEFER QUIT_EDITOR")
        shutdown["deferred_quit_returned"] = True
        shutdown["status"] = "REQUESTED"
    except Exception:
        shutdown["status"] = "REQUEST_FAILED"
        shutdown["failure"] = traceback.format_exc()
    finally:
        record()


def cleanup(success=False, failure_message=None):
    if _state["closing"]:
        return
    _state["closing"] = True
    handle = _state.get("tick_handle")
    if handle is not None:
        try:
            unreal.unregister_slate_post_tick_callback(handle)
        except Exception:
            pass
        _state["tick_handle"] = None
    try:
        _commit_cleanup(success, failure_message)
    except Exception:
        # A cleanup exception leaves any images unverified, but is terminal
        # work. Tell the wrapper promptly instead of making it wait 720 sec.
        if _state["run_dir"]:
            try:
                _write(_state["run_dir"] / "CaptureBatch.json", {
                    "status": "FAIL", "run_id": _state.get("run_id"),
                    "owned_editor_pid": os.getpid(), "target_level": TARGET_LEVEL,
                    "cleanup_completed": False, "map_save_requested": False,
                    "failure": traceback.format_exc(),
                })
            except Exception:
                pass
        raise
    finally:
        # Cleanup/reporting errors must not strand the owned helper with its
        # keep-alive flag set. The wrapper still enforces its process timeout.
        _request_shutdown()


def _commit_cleanup(success, failure_message):
    for camera, transform, fov in _state.get("review_original_cameras", []):
        camera.set_actor_transform(transform, False, True)
        camera.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", fov)
        assert camera.get_actor_transform().translation == transform.translation
    _state["review_cameras_restored"] = True
    lighting = _destroy_owned_temporary_lights()
    lighting["mode"] = _state["lighting_mode"]
    try:
        final_hash = _hash_file(MAP_FILE)
    except Exception:
        final_hash = None
    map_unchanged = final_hash == _state["map_sha256"] and _hash_file(BUILD_REPORT) == _state["source_build_report"]["sha256"]
    asset_hashes = {p: _hash_file(Path(p)) for p in _state["new_asset_sha256"]}
    assets_unchanged = asset_hashes == _state["new_asset_sha256"]
    passed = success and lighting["cleanup_verified_zero"] and map_unchanged and assets_unchanged
    if not lighting["cleanup_verified_zero"]:
        failure_message = "Owned temporary-light cleanup failed: " + str(lighting)
    if not map_unchanged:
        failure_message = "Persisted map changed during capture"
    if not assets_unchanged:
        failure_message = "Referenced appearance assets changed during capture"
    for meta_path in _state["metadata_paths"]:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        metadata.update({"status": "PASS" if passed else "FAIL",
                         "temporary_lighting": lighting,
                         "temp_lighting": lighting,
                         "temporary_lighting_cleanup_remaining_count": lighting["remaining_count"],
                         "temporary_lighting_cleanup_verified_zero": lighting["cleanup_verified_zero"],
                         "map_sha256_after_cleanup": final_hash,
                         "new_asset_sha256": _state["new_asset_sha256"],
                "source_build_report": _state["source_build_report"],
                         "asset_sha256_after_cleanup": asset_hashes,
                         "appearance_assets_unchanged": assets_unchanged,
                         "persisted_map_unchanged": map_unchanged})
        if failure_message:
            metadata["failure"] = failure_message
        _write(meta_path, metadata)
    summary = {
        "status": "PASS" if passed else "FAIL", "run_id": _state.get("run_id"),
        "owned_editor_pid": os.getpid(), "target_level": TARGET_LEVEL,
        "output_directory": str(OUTPUT),
        "map_sha256": _state["map_sha256"], "map_sha256_after_cleanup": final_hash,
        "source_build_report": _state["source_build_report"],
        "new_asset_sha256": _state["new_asset_sha256"], "asset_sha256_after_cleanup": asset_hashes,
        "appearance_assets_unchanged": assets_unchanged,
        "persisted_map_unchanged": map_unchanged, "map_save_requested": False,
        "source": "fresh_persisted_map_load", "lighting_mode": _state["lighting_mode"],
        "view_mode": _state["view_mode"], "temporary_lighting": lighting,
        "capture_count": len(_state["metadata_paths"]),
        "requested_cameras": [c.get_actor_label() for c in _state["cameras"]],
        "failure": failure_message,
    }
    if _state["run_dir"]:
        _write(_state["run_dir"] / "CaptureBatch.json", summary)
    unreal.log("OTS_HOTEL_CAPTURE_{} count={} temporary_remaining={}".format(
        "SUCCESS" if passed else "FAILED", summary["capture_count"], lighting["remaining_count"]))
    if failure_message:
        unreal.log_error(failure_message)


def fail(message):
    cleanup(False, message)


def start_next_capture():
    if _state["starting"] or _state["closing"]:
        return
    _state["starting"] = True
    index = _state["index"]
    if index >= len(_state["cameras"]):
        cleanup(True)
        return
    camera = _state["cameras"][index]
    view_mode = _state["view_mode"]
    requested = getattr(unreal.ViewModeIndex, "VMI_UNLIT" if view_mode == "unlit" else "VMI_LIT")
    unreal.AutomationLibrary.set_editor_viewport_view_mode(requested)
    if unreal.AutomationLibrary.get_editor_active_viewport_view_mode() != requested:
        raise RuntimeError("Editor viewport did not apply " + view_mode)
    _state["view_mode_verified"] = view_mode
    if _state.get("camera_fill") is not None:
        location = camera.get_actor_location()
        _state["camera_fill"].set_actor_location(unreal.Vector(location.x, location.y, location.z + 110.),
                                                 False, False)
    path = RENDERS / (camera.get_actor_label() + ".png")
    if path.exists():
        path.unlink()
    _state["current_path"] = path
    _state["started_at"] = time.time()
    _state["task"] = unreal.AutomationLibrary.take_high_res_screenshot(
        WIDTH, HEIGHT, str(path), camera, False, False, unreal.ComparisonTolerance.LOW,
        "Old-town hotel and independent openings inspection", .35, True)
    _state["starting"] = False
    unreal.log("OTS_HOTEL_CAPTURE_STARTED {}".format(camera.get_actor_label()))


def on_tick(_delta_seconds):
    try:
        if _state["closing"]:
            return
        if _state["task"] is None:
            if _state["frames"] == 0 and _state.get("camera_fill") is not None:
                camera = _state["cameras"][_state["index"]]
                location = camera.get_actor_location()
                _state["camera_fill"].set_actor_location(
                    unreal.Vector(location.x, location.y, location.z + 110.), False, False)
            _state["frames"] += 1
            needed = WARMUP_FRAMES if _state["index"] == 0 else BETWEEN_CAMERA_FRAMES
            if _state["frames"] >= needed:
                _state["frames"] = 0
                start_next_capture()
            return
        task = _state["task"]
        if not task.is_valid_task():
            fail("Automation screenshot task became invalid")
            return
        if task.is_task_done():
            path = _state["current_path"]
            if not path.is_file() or path.stat().st_size < 20000:
                fail("Capture is missing or too small: " + str(path))
                return
            png_bytes = path.read_bytes()
            if png_bytes[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", png_bytes[16:24]) != (WIDTH, HEIGHT):
                fail("Capture PNG signature or actual resolution differs")
                return
            camera = _state["cameras"][_state["index"]]
            location, rotation = camera.get_actor_location(), camera.get_actor_rotation()
            metadata = {
                "status": "CAPTURED", "camera": camera.get_actor_label(),
                "target_level": TARGET_LEVEL, "map_sha256": _state["map_sha256"],
                "new_asset_sha256": _state["new_asset_sha256"],
                "source_build_report": _state["source_build_report"],
                "width": WIDTH, "height": HEIGHT, "bytes": path.stat().st_size,
                "png_sha256": _hash_file(path), "run_id": _state["run_id"],
                "owned_editor_pid": os.getpid(), "source": "fresh_persisted_map_load",
                "source_persisted_map": str(MAP_FILE), "fresh_map_load_verified": True,
                "camera_location_cm": [location.x, location.y, location.z],
                "camera_rotation_degrees": [rotation.pitch, rotation.yaw, rotation.roll],
                "camera_fov_degrees": camera.get_component_by_class(unreal.CameraComponent).get_editor_property("field_of_view"),
                "camera_pose_scope": "temporary inspection override; original restored at cleanup; saved map unchanged",
                "view_mode_requested": _state["view_mode"],
                "view_mode_verified": _state["view_mode_verified"],
                "lighting_mode": _state["lighting_mode"],
                "temporary_lighting_created_count": _state["temporary_created_count"],
                "temp_lighting": {"mode": _state["lighting_mode"],
                                  "created_count": _state["temporary_created_count"],
                                  "cleanup_verified_zero": False, "remaining_count": None},
                "temporary_lighting_cleanup_verified_zero": False,
                "temporary_lighting_cleanup_remaining_count": None,
                "map_save_requested": False,
            }
            meta_path = path.with_suffix(".json")
            _write(meta_path, metadata)
            _state["metadata_paths"].append(meta_path)
            unreal.log("OTS_HOTEL_CAPTURE_DONE {} bytes={}".format(path.name, metadata["bytes"]))
            _state.update({"task": None, "starting": False, "index": _state["index"] + 1, "frames": 0})
            if _state["index"] >= len(_state["cameras"]):
                cleanup(True)
            return
        if time.time() - _state["started_at"] > TIMEOUT_SECONDS:
            fail("Screenshot timed out")
    except Exception:
        fail(traceback.format_exc())


def main():
    RENDERS.mkdir(parents=True, exist_ok=True)
    run_id = os.environ.get("OTS_CAPTURE_RUN_ID", "hotel_%d" % os.getpid())
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Unsafe capture run id")
    _state["run_id"] = run_id
    _state["run_dir"] = OUTPUT / "Runs" / run_id
    _state["run_dir"].mkdir(parents=True, exist_ok=True)
    lighting = os.environ.get("OTS_REVIEW_LIGHTING", "temporary").lower()
    view_mode = os.environ.get("OTS_REVIEW_VIEW_MODE", "lit").lower()
    if lighting not in ("temporary", "street_only") or view_mode not in ("lit", "unlit"):
        raise ValueError("Unsupported inspection lighting or viewport mode")
    _state["lighting_mode"], _state["view_mode"] = lighting, view_mode
    _state["source_build_report"] = dict(file=str(BUILD_REPORT.resolve()),sha256=_hash_file(BUILD_REPORT))
    report = json.loads(BUILD_REPORT.read_text(encoding="utf-8-sig"))
    expected_assets = report.get("new_asset_sha256", {})
    actual_assets = {p: _hash_file(Path(p)) for p in expected_assets}
    if actual_assets != expected_assets:
        raise RuntimeError("Build report and persisted appearance asset hashes differ")
    _state["new_asset_sha256"] = actual_assets
    requested = os.environ.get("OTS_CAPTURE_CAMERAS", "")
    labels = [v.strip() for v in requested.split(",") if v.strip()] if requested else list(
        report.get("hotel_openings_review_cameras", []))[:MAX_CAMERAS]
    if not labels or len(labels) > MAX_CAMERAS or len(set(labels)) != len(labels):
        raise ValueError("A helper needs one to four unique review cameras")
    if any(not re.fullmatch(r"[A-Za-z0-9_]+", v) for v in labels):
        raise ValueError("Unsafe camera label")
    map_hash = _hash_file(MAP_FILE)
    if report.get("map_sha256", "").lower() != map_hash:
        raise RuntimeError("Build report and persisted map hashes differ")
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level.load_level(TARGET_LEVEL):
        raise RuntimeError("Unable to freshly load " + TARGET_LEVEL)
    _state["map_sha256"] = map_hash
    if _hash_file(MAP_FILE) != map_hash:
        raise RuntimeError("Persisted map changed while loading")
    if not list(level.get_viewport_config_keys()):
        raise RuntimeError("Owned capture helper has no editor viewport")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by_label = {}
    for actor in actors.get_all_level_actors():
        label = actor.get_actor_label()
        if label in labels:
            if label in by_label:
                raise RuntimeError("Duplicate camera label: " + label)
            by_label[label] = actor
    if set(by_label) != set(labels):
        raise RuntimeError("Missing hotel cameras: " + str(set(labels) - set(by_label)))
    _state["review_original_cameras"] = []
    for label, settings in report.get("review_camera_overrides", {}).items():
        if label not in by_label:
            continue
        camera = by_label[label]
        cc = camera.get_component_by_class(unreal.CameraComponent)
        _state["review_original_cameras"].append((camera, camera.get_actor_transform(), cc.get_editor_property("field_of_view")))
        location = unreal.Vector(*settings["location_cm"])
        rotation = unreal.MathLibrary.find_look_at_rotation(location, unreal.Vector(*settings["target_cm"]))
        camera.set_actor_location(location, False, True)
        camera.set_actor_rotation(rotation, True)
        cc.set_editor_property("field_of_view", settings["fov_degrees"])
    _state["cameras"] = [by_label[label] for label in labels]
    actors.set_selected_level_actors([])
    _create_temporary_lighting()
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _state["tick_handle"] = unreal.register_slate_post_tick_callback(on_tick)
    unreal.log("OTS_HOTEL_CAPTURE_READY cameras={} lighting={} owned_pid={}".format(
        len(labels), lighting, os.getpid()))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        fail(traceback.format_exc())
        raise
