"""Remove identical shared threshold instances from the saved target street."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / "Saved/CodexOutputs/EnterableStreet_20261002"
TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
MAP_FILE = PROJECT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
sys.path.insert(0, str(PROJECT / "Scripts"))


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def main():
    build = json.loads((OUTPUT / "BuildReport.json").read_text(encoding="utf-8"))
    buildings = json.loads((OUTPUT / "BuildingReport.json").read_text(encoding="utf-8"))
    assert build["status"] == "PASS" and build["buildings"] == buildings
    assert hashlib.sha256(MAP_FILE.read_bytes()).hexdigest() == build["map_sha256"]
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert levels.load_level(TARGET)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert world.get_path_name().startswith(TARGET + ".")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    groups = defaultdict(list)
    for actor in actors.get_all_level_actors():
        label = actor.get_actor_label()
        if not label.startswith("OTS_Enterable_") or "_DoorThreshold_" not in label:
            continue
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
        assert len(components) == 1
        component = components[0]
        assert component.static_mesh is not None
        key = (component.static_mesh.get_path_name(),
               tuple(round(v, 3) for v in vec(actor.get_actor_location())),
               tuple(round(v, 5) for v in vec(actor.get_actor_scale3d())),
               str(actor.get_actor_rotation()),
               tuple(component.get_material(i).get_path_name() for i in range(component.get_num_materials())),
               component.get_collision_enabled().value)
        groups[key].append(actor)
    removals = []
    for group in groups.values():
        for actor in group[1:]:
            building = next(str(t)[len("OTS_Building_"):] for t in actor.get_editor_property("tags")
                            if str(t).startswith("OTS_Building_"))
            center, extent = actor.get_actor_bounds(False)
            low, high = [center.x - extent.x, center.y - extent.y, center.z - extent.z], [center.x + extent.x, center.y + extent.y, center.z + extent.z]
            matches = [row for row in buildings["structural_boxes"]
                       if row["building"] == building and row["role"] == "DoorThreshold"
                       and all(abs(row["min"][i] - low[i]) < .05 and abs(row["max"][i] - high[i]) < .05 for i in range(3))]
            assert len(matches) == 1, "Threshold metadata mismatch: " + actor.get_actor_label()
            buildings["structural_boxes"].remove(matches[0])
            removals.append({"actor": actor.get_actor_label(), "kept_actor": group[0].get_actor_label(),
                             "building": building, "min": low, "max": high})
            assert actors.destroy_actor(actor)
    count = len(removals)
    buildings["generated_actor_count"] -= count
    buildings["module_actor_distribution"]["DoorThreshold"] -= count
    from ValidateEnterableStreet import refresh_world_collision, validate_buildings, validate_main_home
    remaining = list(actors.get_all_level_actors())
    refresh_world_collision(remaining)
    assert validate_main_home(remaining) == build["main_home"]
    collision = validate_buildings(world, remaining, buildings)
    assert collision["passed"], "Cleanup collision checks failed; map was not saved"
    if count:
        for source, name in ((MAP_FILE, "Before_SharedThresholdCleanup.umap"),
                             (OUTPUT / "BuildReport.json", "Before_SharedThresholdCleanup_BuildReport.json"),
                             (OUTPUT / "BuildingReport.json", "Before_SharedThresholdCleanup_BuildingReport.json")):
            backup = OUTPUT / name
            if not backup.exists():
                shutil.copy2(source, backup)
        assert levels.save_current_level()
    build.update(buildings=buildings, actor_count=len(remaining), collision=collision,
                 map_sha256=hashlib.sha256(MAP_FILE.read_bytes()).hexdigest())
    build["shared_threshold_cleanup"] = removals or build.get("shared_threshold_cleanup", [])
    for name, data in (("BuildReport.json", build), ("BuildingReport.json", buildings),
                       ("CollisionValidation.json", collision),
                       ("ThresholdCleanup.json", {"passed": True, "removed_count": count,
                                                   "removals": removals, "map_sha256": build["map_sha256"]})):
        (OUTPUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    unreal.SystemLibrary.execute_console_command(world, "MAP CHECK DONTDISPLAYDIALOG NOCLEARLOG")
    unreal.log("OTS_THRESHOLD_CLEANUP_SUCCESS removed={} actors={}".format(count, len(remaining)))


if __name__ == "__main__":
    main()
