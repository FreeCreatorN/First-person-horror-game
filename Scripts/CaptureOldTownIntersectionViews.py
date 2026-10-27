"""Read-only, unsaved before/after captures of the original-town intersections.

Use the SoftGoods capture wrapper with this entry point. BuildReport binds the
persisted map and appearance-file hashes. Identical camera labels and optional
review_camera_overrides allow the same views before and after a targeted fix.
Temporary cameras and inspection lights are removed before PASS is committed.
"""
import json
import math
import os
import re
import sys
import traceback
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / "Scripts"))
import CaptureOldTownSoftGoodsViews as capture

ORIGINAL_LEVEL = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
SPECS = {
    "INTERSECTION_UtilityPole01": {
        "location_cm": [1950.0, -200.0, 680.0],
        "target_cm": [2200.0, 470.0, 610.0],
        "fov_degrees": 60.0,
    },
    "INTERSECTION_HotelNorthFrontExit": {
        "location_cm": [8550.0, 3000.0, 180.0],
        "target_cm": [9010.0, 3200.0, 145.0],
        "fov_degrees": 65.0,
    },
}
OWN_CAMERAS = []
OWN_CAMERA_LABELS = []
LAST_INDEX = -1
CAMERA_SPECS = {}
PHASE = os.environ.get("OTS_INTERSECTION_CAPTURE_PHASE", "Unspecified")
ORIGINAL_TICK = capture.on_tick
ORIGINAL_COMMIT = capture._commit_cleanup


class _ClosedCameraLabel:
    """Only cleanup summaries use cameras after the owned Actors are destroyed."""

    def __init__(self, label):
        self.label = label

    def get_actor_label(self):
        return self.label


def _valid_spec(value):
    assert set(value) == {"location_cm", "target_cm", "fov_degrees"}, value
    assert all(len(value[key]) == 3 for key in ("location_cm", "target_cm"))
    assert all(isinstance(v, (int, float)) and math.isfinite(v)
               for key in ("location_cm", "target_cm") for v in value[key])
    assert math.dist(value["location_cm"], value["target_cm"]) > 1.0
    assert isinstance(value["fov_degrees"], (int, float))
    assert 5.0 < value["fov_degrees"] < 150.0
    return value


def on_tick(delta):
    global LAST_INDEX
    try:
        state = capture._state
        if state["closing"]:
            return
        if state["task"] is None and state["index"] < len(state["cameras"]):
            if LAST_INDEX != state["index"]:
                level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
                camera = state["cameras"][state["index"]]
                level.pilot_level_actor(camera)
                assert level.get_pilot_level_actor() == camera
                LAST_INDEX = state["index"]
        ORIGINAL_TICK(delta)
    except Exception:
        capture.fail(traceback.format_exc())


def commit(success, failure_message):
    state = capture._state
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    errors = []
    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).eject_pilot_level_actor()
    except Exception:
        errors.append("Unable to eject temporary camera: " + traceback.format_exc())
    for camera in reversed(OWN_CAMERAS):
        try:
            if not actors.destroy_actor(camera):
                errors.append("Destroy returned false for owned temporary camera")
        except Exception:
            errors.append(traceback.format_exc())
    owned = set(OWN_CAMERA_LABELS)
    remaining = [a.get_actor_label() for a in actors.get_all_level_actors()
                 if a.get_actor_label() in owned]
    camera_zero = not remaining and not errors
    # The shared cleanup only needs camera labels for its terminal summary.
    # Do not dereference destroyed UObjects or publish PASS before this check.
    state["cameras"] = [_ClosedCameraLabel(label) for label in OWN_CAMERA_LABELS]
    if not camera_zero:
        failure_message = "Owned temporary-camera cleanup failed: " + str({
            "remaining": remaining, "errors": errors,
        })
    ORIGINAL_COMMIT(success and camera_zero, failure_message)
    batch_path = state["run_dir"] / "CaptureBatch.json"
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    lighting = batch["temporary_lighting"]
    proof = {
        "passed": camera_zero and lighting["cleanup_verified_zero"],
        "phase": PHASE,
        "temporary_camera_count": len(OWN_CAMERA_LABELS),
        "temporary_camera_remaining_count": len(remaining),
        "temporary_camera_remaining_labels": remaining,
        "temporary_camera_cleanup_verified_zero": camera_zero,
        "temporary_lighting_cleanup_verified_zero": lighting["cleanup_verified_zero"],
        "camera_cleanup_errors": errors,
        "camera_specs": CAMERA_SPECS,
        "map_save_requested": False,
        "existing_light_switches_invoked": False,
    }
    capture._write(state["run_dir"] / "IntersectionCaptureProof.json", proof)
    batch.update({
        "intersection_capture_phase": PHASE,
        "temporary_camera_count": len(OWN_CAMERA_LABELS),
        "temporary_camera_remaining_count": len(remaining),
        "temporary_camera_cleanup_verified_zero": camera_zero,
        "existing_light_switches_invoked": False,
        "camera_specs": CAMERA_SPECS,
    })
    capture._write(batch_path, batch)
    for path in state["metadata_paths"]:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata.update({
            "intersection_capture_phase": PHASE,
            "temporary_camera_count": len(OWN_CAMERA_LABELS),
            "temporary_camera_cleanup_remaining_count": len(remaining),
            "temporary_camera_cleanup_verified_zero": camera_zero,
            "existing_light_switches_invoked": False,
            "inspection_camera_spec": CAMERA_SPECS[metadata["camera"]],
        })
        capture._write(path, metadata)


def main():
    state = capture._state
    run_id = os.environ["OTS_CAPTURE_RUN_ID"]
    assert re.fullmatch(r"[A-Za-z0-9_-]+", run_id), "Unsafe capture run id"
    state["run_id"] = run_id
    state["run_dir"] = capture.OUTPUT / "Runs" / run_id
    state["run_dir"].mkdir(parents=True, exist_ok=True)
    capture._commit_cleanup = commit
    capture.RENDERS.mkdir(parents=True, exist_ok=True)
    assert PHASE in {"Before", "After", "Unspecified"}, PHASE
    assert capture.TARGET_LEVEL == ORIGINAL_LEVEL
    report = json.loads(capture.BUILD_REPORT.read_text(encoding="utf-8-sig"))
    assert report["target_level"] == ORIGINAL_LEVEL
    state["source_build_report"] = {
        "file": str(capture.BUILD_REPORT.resolve()),
        "sha256": capture._hash_file(capture.BUILD_REPORT),
    }
    assert isinstance(report["new_asset_sha256"], dict)
    state["new_asset_sha256"] = report["new_asset_sha256"]
    assert all(capture._hash_file(Path(path)) == digest
               for path, digest in state["new_asset_sha256"].items())
    state["map_sha256"] = capture._hash_file(capture.MAP_FILE)
    assert state["map_sha256"] == report["map_sha256"]
    state["lighting_mode"], state["view_mode"] = "temporary", "lit"
    requested = [v.strip() for v in os.environ.get(
        "OTS_CAPTURE_CAMERAS", ",".join(SPECS)).split(",") if v.strip()]
    assert 1 <= len(requested) <= capture.MAX_CAMERAS
    assert len(set(requested)) == len(requested)
    assert set(requested).issubset(SPECS), requested
    overrides = report.get("review_camera_overrides", {})
    assert isinstance(overrides, dict)
    for label in requested:
        CAMERA_SPECS[label] = _valid_spec(dict(overrides.get(label, SPECS[label])))
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(ORIGINAL_LEVEL)
    assert capture._hash_file(capture.MAP_FILE) == state["map_sha256"]
    assert list(level.get_viewport_config_keys()), "Owned helper has no editor viewport"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    existing = {a.get_actor_label() for a in actors.get_all_level_actors()}
    assert not existing.intersection(requested), "Temporary camera label already exists"
    for label in requested:
        spec = CAMERA_SPECS[label]
        position = unreal.Vector(*spec["location_cm"])
        rotation = unreal.MathLibrary.find_look_at_rotation(
            position, unreal.Vector(*spec["target_cm"]))
        camera = actors.spawn_actor_from_class(unreal.CameraActor, position, rotation, False)
        assert camera, label
        OWN_CAMERAS.append(camera)
        OWN_CAMERA_LABELS.append(label)
        camera.set_actor_label(label)
        camera.set_editor_property("tags", [unreal.Name(capture.TEMP_TAG), unreal.Name(run_id)])
        camera.set_folder_path(unreal.Name("OldTownSchoolStreet/TemporaryInspection"))
        camera.get_component_by_class(unreal.CameraComponent).set_editor_property(
            "field_of_view", spec["fov_degrees"])
    state["cameras"] = list(OWN_CAMERAS)
    actors.set_selected_level_actors([])
    capture._create_temporary_lighting()
    capture.WARMUP_FRAMES, capture.BETWEEN_CAMERA_FRAMES = 120, 80
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    state["tick_handle"] = unreal.register_slate_post_tick_callback(on_tick)
    unreal.log("OTS_INTERSECTION_CAPTURE_READY phase={} cameras={}".format(PHASE, len(requested)))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        capture.fail(traceback.format_exc())
        raise
