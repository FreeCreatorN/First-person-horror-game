"""Persist explicit NoCollision profiles for the target's Blender furniture."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
output = project / "Saved/CodexOutputs/EnterableStreet_20261002"
target = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
map_file = project / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
sys.path.insert(0, str(project / "Scripts"))
build = json.loads((output / "BuildReport.json").read_text(encoding="utf-8"))
assert build["status"] == "PASS" and build["target_level"] == target
assert build["map_sha256"] == hashlib.sha256(map_file.read_bytes()).hexdigest()
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level(target)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name().startswith(target + ".")
unreal.AutomationLibrary.finish_loading_before_screenshot()
actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
by_label = {actor.get_actor_label(): actor for actor in actors}
repairs = []
for placement in build["furniture_placements"]:
    actor = by_label[placement["actor"]]
    components = actor.get_components_by_class(unreal.StaticMeshComponent)
    assert len(components) == 1
    component = components[0]
    before = str(component.get_collision_profile_name())
    component.set_collision_profile_name("NoCollision")
    assert component.get_collision_enabled().value == unreal.CollisionEnabled.NO_COLLISION.value
    assert not component.get_editor_property("use_default_collision")
    repairs.append({"actor": actor.get_actor_label(), "previous_profile": before, "profile": "NoCollision"})
from ValidateEnterableStreet import refresh_world_collision, validate_buildings, validate_main_home
refresh_world_collision(actors)
assert validate_main_home(actors) == build["main_home"]
collision = validate_buildings(world, actors, build["buildings"])
assert collision["passed"], "Collision validation failed; map not saved"
for source, name in ((map_file, "Before_FurnitureCollisionRepair.umap"),
                     (output / "BuildReport.json", "Before_FurnitureCollisionRepair_BuildReport.json")):
    backup = output / name
    if not backup.exists():
        shutil.copy2(source, backup)
assert levels.save_current_level()
build.update(collision=collision, map_sha256=hashlib.sha256(map_file.read_bytes()).hexdigest(),
             furniture_collision_repairs=repairs)
for name, data in (("BuildReport.json", build), ("CollisionValidation.json", collision),
                   ("FurnitureCollisionRepair.json", {"passed": True, "instances": len(repairs),
                                                     "repairs": repairs, "map_sha256": build["map_sha256"]})):
    (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
unreal.log("OTS_FURNITURE_COLLISION_REPAIR_SUCCESS instances=" + str(len(repairs)))
