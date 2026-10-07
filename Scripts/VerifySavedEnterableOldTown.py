"""Reload and verify the saved enterable street in a fresh UE commandlet.

This script never generates assets or saves a level. Its only file output is
SavedVerification.json, including diagnostics when a check or load fails.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import traceback

import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / "Saved/CodexOutputs/EnterableStreet_20261002"
TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
MAP_FILE = PROJECT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
STRUCTURAL_TAG = "OTS_Enterable_20261002"
FURNITURE_TAG = "OldTownBlenderFurniture_20261002"
GENERATED_ROOT = "/Game/Yastar/Meshes/"
sys.path.insert(0, str(PROJECT / "Scripts"))


def _asset_path(path):
    return path.split(".", 1)[0]


def _check(report, name, passed, **details):
    report["checks"][name] = dict(details, passed=bool(passed))
    if not passed:
        report["errors"].append(name)


def _load_report(report, name):
    try:
        value = json.loads((OUTPUT / name).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object")
        _check(report, "read_" + name, True)
        return value
    except Exception:
        _check(report, "read_" + name, False, traceback=traceback.format_exc())
        return {}


def _declared_assets(value):
    """Collect generated paths from the existing build report schemas."""
    paths = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "asset" and isinstance(item, str) and item.startswith(GENERATED_ROOT):
                paths.add(_asset_path(item))
            elif key == "generated_assets" and isinstance(item, list):
                paths.update(_asset_path(path) for path in item if isinstance(path, str))
            else:
                paths.update(_declared_assets(item))
    elif isinstance(value, list):
        for item in value:
            paths.update(_declared_assets(item))
    return paths


def _verify_actor_inventory(report, actors, build, buildings):
    labels = Counter(actor.get_actor_label() for actor in actors)
    original_labels = [item["label"] for item in buildings.get("buildings", [])]
    _check(report, "building_count", buildings.get("building_count") == 29
           and len(original_labels) == 29 and len(set(original_labels)) == 29,
           reported=buildings.get("building_count"), unique_labels=len(set(original_labels)))
    remaining = sorted(label for label in original_labels if labels[label])
    _check(report, "solid_source_buildings_removed", not remaining, remaining=remaining)

    structural = []
    furniture = []
    generated_references = set()
    missing_meshes = []
    module_distribution = Counter()
    for actor in actors:
        label = actor.get_actor_label()
        tags = {str(tag) for tag in actor.get_editor_property("tags")}
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
        is_structure = STRUCTURAL_TAG in tags and bool(components)
        is_furniture = FURNITURE_TAG in tags or label.startswith("OTS_Blender_")
        if is_structure:
            structural.append(label)
        if is_furniture:
            furniture.append(actor)
        for component in components:
            mesh = component.get_editor_property("static_mesh")
            if mesh is None:
                if is_structure or is_furniture:
                    missing_meshes.append(label + ":" + component.get_name())
                continue
            path = _asset_path(mesh.get_path_name())
            if path.startswith(GENERATED_ROOT):
                generated_references.add(path)
            if is_structure:
                module_distribution[path.rsplit("/", 1)[-1].replace("SM_OTS_Enterable_", "", 1)] += 1
            for index in range(component.get_num_materials()):
                material = component.get_material(index)
                if material is not None:
                    material_path = _asset_path(material.get_path_name())
                    if material_path.startswith(GENERATED_ROOT):
                        generated_references.add(material_path)

    expected_structure = buildings.get("generated_actor_count")
    _check(report, "structural_actor_count", len(structural) == expected_structure,
           expected=expected_structure, actual=len(structural))
    _check(report, "structural_module_distribution",
           dict(module_distribution) == buildings.get("module_actor_distribution"),
           expected=buildings.get("module_actor_distribution"), actual=dict(module_distribution))
    _check(report, "generated_actor_meshes", not missing_meshes, missing=missing_meshes)
    expected_placements = build.get("furniture_placements", [])
    expected_labels = Counter(item["actor"] for item in expected_placements)
    actual_labels = Counter(actor.get_actor_label() for actor in furniture)
    _check(report, "blender_instance_count", len(furniture) == len(expected_placements)
           and actual_labels == expected_labels,
           expected=len(expected_placements), actual=len(furniture),
           missing=list((expected_labels - actual_labels).elements()),
           unexpected=list((actual_labels - expected_labels).elements()))
    expected_meshes = {item["actor"]: _asset_path(item["asset"]) for item in expected_placements}
    incorrect_furniture = []
    for actor in furniture:
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
        mesh_paths = [_asset_path(component.static_mesh.get_path_name())
                      for component in components if component.static_mesh is not None]
        if mesh_paths != [expected_meshes.get(actor.get_actor_label())]:
            incorrect_furniture.append({"actor": actor.get_actor_label(), "actual": mesh_paths,
                                        "expected": expected_meshes.get(actor.get_actor_label())})
    _check(report, "blender_mesh_references", not incorrect_furniture, mismatches=incorrect_furniture)
    _check(report, "total_actor_count", len(actors) == build.get("actor_count"),
           expected=build.get("actor_count"), actual=len(actors))
    declared_assets = _declared_assets(build) | _declared_assets(buildings)
    assets = sorted(declared_assets | generated_references)
    missing_assets = []
    asset_errors = []
    for path in assets:
        try:
            if not unreal.EditorAssetLibrary.does_asset_exist(path) or unreal.load_asset(path) is None:
                missing_assets.append(path)
        except Exception as error:
            asset_errors.append({"asset": path, "error": str(error)})
    _check(report, "generated_assets_exist", not missing_assets and not asset_errors,
           checked_count=len(assets), missing=missing_assets, errors=asset_errors)
    report["statistics"] = {"actor_count": len(actors), "building_count": len(original_labels),
                            "structural_actor_count": len(structural),
                            "blender_instance_count": len(furniture),
                            "declared_asset_count": len(declared_assets),
                            "actual_generated_reference_count": len(generated_references),
                            "asset_references_checked": len(assets)}


def main():
    report = {"passed": False, "target_level": TARGET, "map_sha256": None,
              "checks": {}, "statistics": {}, "errors": [], "collision": None}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    try:
        build = _load_report(report, "BuildReport.json")
        buildings = _load_report(report, "BuildingReport.json")
        _check(report, "completed_build_report", build.get("status") == "PASS"
               and build.get("target_level") == TARGET,
               status=build.get("status"), target_level=build.get("target_level"))
        _check(report, "building_reports_match", bool(buildings)
               and build.get("buildings") == buildings)
        if MAP_FILE.exists():
            report["map_sha256"] = hashlib.sha256(MAP_FILE.read_bytes()).hexdigest()
        _check(report, "saved_map_hash", bool(report["map_sha256"])
               and report["map_sha256"] == build.get("map_sha256"),
               expected=build.get("map_sha256"), actual=report["map_sha256"])
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if not levels.load_level(TARGET):
            raise RuntimeError("Saved target level failed to load")
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        if world is None or not world.get_path_name().startswith(TARGET + "."):
            raise RuntimeError("Loaded world is not the saved target level")
        _check(report, "loaded_saved_target", True, world=world.get_path_name())
        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actors = list(actor_subsystem.get_all_level_actors())
        _verify_actor_inventory(report, actors, build, buildings)
        from ValidateEnterableStreet import refresh_world_collision, validate_buildings, validate_main_home
        report["refreshed_collision_components"] = refresh_world_collision(actors)
        try:
            report["main_home"] = validate_main_home(actors)
            _check(report, "main_home_preserved", report["main_home"] == build.get("main_home"),
                   expected=build.get("main_home"), actual=report["main_home"])
        except Exception:
            _check(report, "main_home_preserved", False, traceback=traceback.format_exc())
        try:
            report["collision"] = validate_buildings(world, actors, buildings)
            _check(report, "saved_world_collision", report["collision"]["passed"])
        except Exception:
            _check(report, "saved_world_collision", False, traceback=traceback.format_exc())
        # Collision registration is in memory only; confirm no disk map changed.
        unreal.SystemLibrary.execute_console_command(world, "MAP CHECK DONTDISPLAYDIALOG NOCLEARLOG")
        after_hash = hashlib.sha256(MAP_FILE.read_bytes()).hexdigest()
        _check(report, "map_unchanged_during_verification", after_hash == report["map_sha256"],
               before=report["map_sha256"], after=after_hash)
        report["passed"] = not report["errors"]
    except Exception:
        _check(report, "verification_exception", False, traceback=traceback.format_exc())
    finally:
        (OUTPUT / "SavedVerification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["passed"]:
        unreal.log("OTS_SAVED_VERIFICATION_SUCCESS " + report["map_sha256"])
    else:
        unreal.log_error("OTS_SAVED_VERIFICATION_FAILED " + ", ".join(report["errors"]))
    return report


if __name__ == "__main__":
    result = main()
    if not result["passed"]:
        raise RuntimeError("Saved street verification failed; see SavedVerification.json")
