"""Probe school approaches after conversion in memory; never save the map."""
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / "Saved/CodexOutputs/EnterableStreet_20261002"
TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
MAP = PROJECT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
sys.path.insert(0, str(PROJECT / "Scripts"))


def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def trace(world, xy, top=58.0, bottom=-25.0, complex_trace=False):
    hit = unreal.SystemLibrary.line_trace_single_for_objects(
        world, unreal.Vector(xy[0], xy[1], top), unreal.Vector(xy[0], xy[1], bottom),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
        complex_trace, [], unreal.DrawDebugTrace.NONE)
    result = {"start_z": top, "end_z": bottom, "complex": complex_trace, "hit": hit is not None}
    if hit is not None:
        values = hit.to_tuple()
        result["hit_tuple"] = [str(value) for value in values]
        result.update({"blocking_hit": bool(values[0]), "initial_penetration": bool(values[1]),
                       "time": float(values[2]), "distance": float(values[3]),
                       "location": xyz(values[4]), "impact": xyz(values[5]),
                       "normal": xyz(values[6]), "impact_normal": xyz(values[7]),
                       "actor": values[9].get_actor_label() if values[9] is not None else None,
                       "component": values[10].get_name() if values[10] is not None else None})
        if values[10] is not None and isinstance(values[10], unreal.StaticMeshComponent):
            mesh = values[10].static_mesh
            result["mesh"] = mesh.get_path_name() if mesh is not None else None
    return result


def sample(world, point):
    from ValidateEnterableStreet import capsule_blockers
    short = trace(world, point)
    high = trace(world, point, 350.0, -100.0)
    result = {"xy": list(point[:2]), "validator_trace": short, "higher_trace": high,
              "complex_trace": trace(world, point, complex_trace=True)}
    if short["hit"]:
        result["validator_capsule_blockers"] = capsule_blockers(world, point[:2] + [short["impact"][2]])
    if high["hit"]:
        result["higher_trace_capsule_blockers"] = capsule_blockers(world, point[:2] + [high["impact"][2]])
    # Nominal foot heights distinguish an initial-overlap "floor" from support.
    result["nominal_capsules"] = {str(z): capsule_blockers(world, point[:2] + [z])
                                  for z in (1.0, 6.0, 11.0, 35.0)}
    return result


def sample_route(world, route, spacing=25.0):
    points = []
    for first, second in zip(route, route[1:]):
        count = max(1, math.ceil(math.dist(first[:2], second[:2]) / spacing))
        for index in range(count + 1):
            ratio = index / count
            points.append([first[i] + (second[i] - first[i]) * ratio for i in (0, 1)])
    return [sample(world, point) for point in points]


def main():
    report = {"target_level": TARGET, "completed": False, "errors": [], "routes": {}}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    try:
        from ConvertOldTownBuildings import convert_buildings
        from BuildEnterableOldTown import ensure_walkable_ground
        from ValidateEnterableStreet import refresh_world_collision
        report["map_sha256_before"] = hashlib.sha256(MAP.read_bytes()).hexdigest()
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        assert levels.load_level(TARGET), "Target level failed to load"
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        assert world.get_path_name().startswith(TARGET + "."), "Unexpected world"
        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        refresh_world_collision(list(actor_subsystem.get_all_level_actors()))
        buildings = convert_buildings(actor_subsystem)
        report["ground_repairs"] = ensure_walkable_ground(actor_subsystem)
        from ExtractOldTownReusableAssets import extract_reusable_assets
        report["extraction"] = extract_reusable_assets(actor_subsystem)
        actors = list(actor_subsystem.get_all_level_actors())
        report["refreshed_components"] = refresh_world_collision(actors)
        report["building_count"] = buildings["building_count"]
        candidates = []
        for actor in actors:
            label = actor.get_actor_label()
            if not ("School" in label or label in ("Blockout_TJunctionRoad", "OTS_PerimeterGround_01")):
                continue
            if label.startswith("OTS_Enterable_"):
                continue
            for component in actor.get_components_by_class(unreal.StaticMeshComponent):
                mesh = component.static_mesh
                if mesh is None:
                    continue
                origin, extent = actor.get_actor_bounds(False)
                body = mesh.get_editor_property("body_setup")
                candidates.append({"actor": label, "component": component.get_name(), "mesh": mesh.get_path_name(),
                                   "bounds_center": xyz(origin), "bounds_extent": xyz(extent),
                                   "collision": str(component.get_collision_enabled()),
                                   "object_type": str(component.get_collision_object_type()),
                                   "pawn_response": str(component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN)),
                                   "simple_shape_count": unreal.GeometryScript_Collision.get_simple_collision_shape_count(
                                       unreal.GeometryScript_Collision.get_simple_collision_from_static_mesh(mesh)),
                                   "trace_flag": str(body.get_editor_property("collision_trace_flag")) if body else None})
        report["school_source_components_after_conversion"] = candidates
        plans = {
            "street_through_school_gate": [[1100.0, 0.0], [-1500.0, 0.0]],
            "school_path_to_main_entry": [[-1500.0, 0.0], [-3250.0, 0.0]],
            "north_courtyard": [[-1300.0, 0.0], [-1500.0, 0.0], [-1500.0, 2200.0], [-3100.0, 2200.0]],
            "south_courtyard": [[-1300.0, 0.0], [-1500.0, 0.0], [-1500.0, -2200.0], [-3100.0, -2200.0]],
        }
        for building in buildings["buildings"]:
            if "School" in building["label"] or "BoundaryWest" in building["label"]:
                plans[building["label"]] = building["primary_entry_route"]
        for name, route in plans.items():
            report["routes"][name] = sample_route(world, route)
        report["gate_grid"] = [sample(world, [float(x), float(y)])
                               for x in range(-1100, -799, 25) for y in range(-350, 351, 50)]
        report["map_sha256_after"] = hashlib.sha256(MAP.read_bytes()).hexdigest()
        report["map_unchanged"] = report["map_sha256_before"] == report["map_sha256_after"]
        from ValidateEnterableStreet import validate_ground_connectivity
        report["connectivity"] = validate_ground_connectivity(world, buildings)
        report["completed"] = True
    except Exception:
        report["errors"].append(traceback.format_exc())
    finally:
        (OUTPUT / "ApproachDiagnostics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["completed"]:
        unreal.log_error("OTS_APPROACH_DIAGNOSTICS_FAILED " + "\n".join(report["errors"]))
        raise RuntimeError("Approach diagnostics failed; see ApproachDiagnostics.json")
    unreal.log("OTS_APPROACH_DIAGNOSTICS_SUCCESS map_unchanged={}".format(report["map_unchanged"]))
    return report


if __name__ == "__main__":
    main()
