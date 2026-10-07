"""Build and probe structures in memory, without saving the street map."""
from pathlib import Path
import json
import sys
import traceback
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(root / "Scripts"))
from ConvertOldTownBuildings import convert_buildings
from ValidateEnterableStreet import validate_buildings, refresh_world_collision
from BuildEnterableOldTown import ensure_walkable_ground

try:
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(
        "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    refreshed = refresh_world_collision(list(actors.get_all_level_actors()))
    buildings = convert_buildings(actors)
    repairs = ensure_walkable_ground(actors)
    out = root / "Saved/CodexOutputs/EnterableStreet_20261002"
    (out / "BuildingReport.json").write_text(json.dumps(buildings, indent=2), encoding="utf-8")
    diag = {"refreshed_components": refreshed, "walk_surfaces_repaired": repairs, "ground": []}
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label() in ("Blockout_MainRoad", "OTS_PerimeterGround_01"):
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            diag["ground"].append({"actor": actor.get_actor_label(), "collision_profile": str(component.get_collision_profile_name()),
                "object_type": str(component.get_collision_object_type()), "collision": str(component.get_collision_enabled()),
                "simple_shapes": unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).get_simple_collision_count(component.static_mesh)})
    (out / "GroundDiagnostics.json").write_text(json.dumps(diag, indent=2), encoding="utf-8")
    validation = validate_buildings(world, list(actors.get_all_level_actors()), buildings)
    (out / "PreflightCollision.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    unreal.log("OTS_PREFLIGHT_FINISHED passed={}".format(validation["passed"]))
except Exception:
    unreal.log_error("OTS_PREFLIGHT_FAILED\n" + traceback.format_exc())
    raise
