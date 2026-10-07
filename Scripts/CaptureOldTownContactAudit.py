"""Capture temporary player-distance audit views without modifying the map."""

from pathlib import Path
import math
import time
import traceback

import unreal


TARGET_LEVEL = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
OUTPUT_ROOT = (
    Path(unreal.Paths.project_dir()).resolve()
    / "Saved/CodexOutputs/OldTownSchoolStreet/ContactAudit"
)
WIDTH = 1440
HEIGHT = 810
WARMUP_FRAMES = 150
BETWEEN_CAMERA_FRAMES = 75
TIMEOUT_SECONDS = 90.0

# label, camera location, target, focal length
VIEW_SPECS = (
    (
        "AUDIT_StreetLampContact",
        (1030.0, -260.0, 195.0),
        (1420.0, 360.0, 198.0),
        20.0,
    ),
    (
        "AUDIT_StreetLampUpperJoint",
        (1260.0, 170.0, 385.0),
        (1420.0, 350.0, 382.0),
        48.0,
    ),
    (
        "AUDIT_StreetLampRearJoint",
        (1290.0, 555.0, 390.0),
        (1420.0, 350.0, 382.0),
        44.0,
    ),
    (
        "AUDIT_BicycleContact",
        (675.0, 245.0, 145.0),
        (675.0, 498.0, 60.0),
        34.0,
    ),
    (
        "AUDIT_BicycleJointOblique",
        (850.0, 200.0, 118.0),
        (675.0, 498.0, 64.0),
        38.0,
    ),
    (
        "AUDIT_NorthAlleyConnections",
        (2560.0, 640.0, 165.0),
        (2570.0, 1040.0, 292.0),
        22.0,
    ),
    (
        "AUDIT_NorthWallUtility",
        (2650.0, 720.0, 165.0),
        (2470.0, 720.0, 145.0),
        21.0,
    ),
    (
        "AUDIT_SouthAlleyConnections",
        (2575.0, -640.0, 165.0),
        (2570.0, -1040.0, 292.0),
        22.0,
    ),
    (
        "AUDIT_UtilityPoleClearance",
        (1750.0, -250.0, 180.0),
        (2200.0, 350.0, 330.0),
        16.0,
    ),
    (
        "AUDIT_WallMaterialOblique",
        (3200.0, -75.0, 210.0),
        (4060.0, 525.0, 520.0),
        30.0,
    ),
    (
        "AUDIT_MainHomeShelfContact",
        (1010.0, 1080.0, 175.0),
        (1090.0, 1265.0, 190.0),
        28.0,
    ),
    (
        "AUDIT_MainHomeCounterFurniture",
        (1025.0, 1030.0, 150.0),
        (1065.0, 1192.0, 132.0),
        34.0,
    ),
    (
        "AUDIT_MainHomePharmacyCabinet",
        (1080.0, 1110.0, 174.0),
        (1216.0, 1270.0, 156.0),
        38.0,
    ),
    # Wide evidence complements close-ups: reveal the floor, support legs,
    # approach route and the entire cabinet, not merely one attractive part.
    (
        "AUDIT_MainHomeInteriorWide",
        (1030.0, 760.0, 168.0),
        (1030.0, 1240.0, 163.0),
        18.0,
    ),
    (
        "AUDIT_MainHomeCounterTop",
        (1025.0, 1000.0, 238.0),
        (1025.0, 1195.0, 115.0),
        22.0,
    ),
    (
        "AUDIT_MainHomeCabinetFull",
        (1130.0, 990.0, 160.0),
        (1210.0, 1260.0, 139.0),
        22.0,
    ),
    (
        "AUDIT_SchoolGatePlayerEntry",
        (-1460.0, 0.0, 168.0),
        (-955.0, 0.0, 150.0),
        20.0,
    ),
    (
        "AUDIT_StaticShutterOblique",
        (3410.0, -210.0, 160.0),
        (3115.0, -512.0, 145.0),
        32.0,
    ),
    (
        "AUDIT_SignAwningOblique",
        (760.0, -150.0, 240.0),
        (1050.0, -510.0, 310.0),
        34.0,
    ),
    (
        "AUDIT_TJunctionApproach",
        (5310.0, -90.0, 168.0),
        (6250.0, 0.0, 185.0),
        20.0,
    ),
    (
        "AUDIT_TJunctionNorthArm",
        (6250.0, 150.0, 168.0),
        (6280.0, 1360.0, 170.0),
        22.0,
    ),
    (
        "AUDIT_TJunctionSouthArm",
        (6250.0, -150.0, 168.0),
        (6280.0, -1360.0, 170.0),
        22.0,
    ),
    (
        "AUDIT_TJunctionFocalShop",
        (5990.0, -470.0, 175.0),
        (6555.0, 0.0, 215.0),
        24.0,
    ),
    (
        "AUDIT_P5ServiceDoorSeal",
        (6150.0, -245.0, 175.0),
        (6572.0, 158.0, 152.0),
        46.0,
    ),
    (
        "AUDIT_P5WallLampOverlap",
        (6415.0, -300.0, 300.0),
        (6572.0, 0.0, 282.0),
        52.0,
    ),
    (
        "AUDIT_ReadableShopSigns",
        (1500.0, -190.0, 240.0),
        (1900.0, -515.0, 296.0),
        38.0,
    ),
)

_state = {
    "tick_handle": None,
    "task": None,
    "index": 0,
    "frames": 0,
    "started_at": time.time(),
    "current_path": None,
    "cameras": [],
    "actor_subsystem": None,
    "starting": False,
}


def make_rotator(pitch, yaw, roll=0.0):
    return unreal.Rotator(
        roll=float(roll),
        pitch=float(pitch),
        yaw=float(yaw),
    )


def look_at_rotation(origin, target):
    dx = float(target[0]) - float(origin[0])
    dy = float(target[1]) - float(origin[1])
    dz = float(target[2]) - float(origin[2])
    return (
        math.degrees(math.atan2(dz, math.hypot(dx, dy))),
        math.degrees(math.atan2(dy, dx)),
    )


def cleanup():
    handle = _state.get("tick_handle")
    if handle is not None:
        try:
            unreal.unregister_slate_post_tick_callback(handle)
        except Exception:
            pass
        _state["tick_handle"] = None
    subsystem = _state.get("actor_subsystem")
    cameras = _state.get("cameras") or []
    if subsystem is not None and cameras:
        try:
            subsystem.destroy_actors(cameras)
        except Exception:
            pass
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def fail(message):
    unreal.log_error("OTS_CONTACT_AUDIT_FAILED {}".format(message))
    cleanup()


def start_next_capture():
    if _state["starting"]:
        return
    _state["starting"] = True
    index = _state["index"]
    if index >= len(_state["cameras"]):
        unreal.log(
            "OTS_CONTACT_AUDIT_SUCCESS count={} output={}".format(
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
        "Old Town physical-contact audit",
        0.35,
        True,
    )
    _state["starting"] = False
    unreal.log("OTS_CONTACT_AUDIT_STARTED {}".format(label))


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
                fail("Missing or undersized screenshot: {}".format(output_path))
                return
            unreal.log(
                "OTS_CONTACT_AUDIT_DONE {} bytes={}".format(
                    output_path.name,
                    output_path.stat().st_size,
                )
            )
            _state["task"] = None
            _state["index"] += 1
            _state["frames"] = 0
            return
        if time.time() - _state["started_at"] > TIMEOUT_SECONDS:
            fail("Screenshot timed out")
    except Exception:
        fail(traceback.format_exc())


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for old_file in OUTPUT_ROOT.glob("AUDIT_*.png"):
        old_file.unlink()

    level_subsystem = unreal.get_editor_subsystem(
        unreal.LevelEditorSubsystem
    )
    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    if not level_subsystem.load_level(TARGET_LEVEL):
        raise RuntimeError("Unable to load {}".format(TARGET_LEVEL))
    if not list(level_subsystem.get_viewport_config_keys()):
        raise RuntimeError("No editor viewport is available")

    cameras = []
    for label, location, target, focal_length in VIEW_SPECS:
        pitch, yaw = look_at_rotation(location, target)
        camera = actor_subsystem.spawn_actor_from_class(
            unreal.CineCameraActor,
            unreal.Vector(*location),
            make_rotator(pitch, yaw),
            False,
        )
        if camera is None:
            raise RuntimeError("Unable to spawn {}".format(label))
        camera.set_actor_label(label)
        component = camera.get_cine_camera_component()
        component.set_editor_property(
            "current_focal_length",
            float(focal_length),
        )
        # A high f-stop is intentional here: these are geometry/contact audit
        # frames, so both the near tube and the far joint must stay readable.
        component.set_editor_property("current_aperture", 16.0)
        component.set_editor_property("constrain_aspect_ratio", True)
        component.set_editor_property("aspect_ratio", 16.0 / 9.0)
        cameras.append(camera)

    actor_subsystem.set_selected_level_actors([])
    _state["actor_subsystem"] = actor_subsystem
    _state["cameras"] = cameras
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _state["tick_handle"] = unreal.register_slate_post_tick_callback(on_tick)
    unreal.log(
        "OTS_CONTACT_AUDIT_READY views={} resolution={}x{}".format(
            len(cameras),
            WIDTH,
            HEIGHT,
        )
    )


try:
    main()
except Exception:
    unreal.log_error(
        "OTS_CONTACT_AUDIT_FAILED\n{}".format(traceback.format_exc())
    )
    cleanup()
    raise
