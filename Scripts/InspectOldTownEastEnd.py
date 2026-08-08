"""Write a read-only spatial audit of the generated street's east end."""

from pathlib import Path
import json
import traceback

import unreal


TARGET_LEVEL = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
OUTPUT_PATH = (
    Path(unreal.Paths.project_dir()).resolve()
    / "Saved/CodexOutputs/OldTownSchoolStreet/EastEndSpatialAudit.json"
)


def vector(value):
    return [
        round(float(value.x), 2),
        round(float(value.y), 2),
        round(float(value.z), 2),
    ]


def main():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.load_level(TARGET_LEVEL):
        raise RuntimeError("Unable to load target level")

    rows = []
    for actor in actors.get_all_level_actors():
        location = actor.get_actor_location()
        try:
            origin, extent = actor.get_actor_bounds(False, False)
        except Exception:
            origin = location
            extent = unreal.Vector(0.0, 0.0, 0.0)
        if float(origin.x + extent.x) < 5250.0:
            continue
        if abs(float(origin.y)) > 2600.0:
            continue
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        mesh = None
        if component is not None:
            asset = component.get_editor_property("static_mesh")
            mesh = asset.get_path_name() if asset is not None else None
        rows.append(
            {
                "label": actor.get_actor_label(),
                "class": actor.get_class().get_name(),
                "location": vector(location),
                "bounds_origin": vector(origin),
                "bounds_extent": vector(extent),
                "mesh": mesh,
            }
        )
    rows.sort(key=lambda row: (row["bounds_origin"][0], row["label"]))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    unreal.log(
        "OTS_EAST_END_AUDIT_SUCCESS count={} output={}".format(
            len(rows),
            OUTPUT_PATH,
        )
    )


try:
    main()
except Exception:
    unreal.log_error("OTS_EAST_END_AUDIT_FAILED\n{}".format(traceback.format_exc()))
    raise

