"""Audit furniture in the saved street; never generate assets or save a level."""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import traceback

import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / "Saved/CodexOutputs/EnterableStreet_20261002"
TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
MAP_FILE = PROJECT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
TAG = "OldTownBlenderFurniture_20261002"
TOLERANCE_CM = 0.1


def xyz(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def bounds(actor):
    origin, extent = actor.get_actor_bounds(False)
    center, half = xyz(origin), xyz(extent)
    return [[center[i] - half[i] for i in range(3)],
            [center[i] + half[i] for i in range(3)]]


def asset_path(path):
    return path.split(".", 1)[0]


def check(report, name, passed, **details):
    report["checks"][name] = dict(details, passed=bool(passed))
    if not passed:
        report["errors"].append(name)


def main():
    report = {"passed": False, "target_level": TARGET, "tolerance_cm": TOLERANCE_CM,
              "statistics": {}, "checks": {}, "actors": [], "groups": [], "errors": []}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    try:
        build = json.loads((OUTPUT / "BuildReport.json").read_text(encoding="utf-8"))
        check(report, "completed_build", build.get("status") == "PASS"
              and build.get("target_level") == TARGET)
        original_hash = hashlib.sha256(MAP_FILE.read_bytes()).hexdigest()
        check(report, "saved_map_matches_build", original_hash == build.get("map_sha256"),
              actual=original_hash, expected=build.get("map_sha256"))
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if not levels.load_level(TARGET):
            raise RuntimeError("Saved target level failed to load")
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        if world is None or not world.get_path_name().startswith(TARGET + "."):
            raise RuntimeError("Loaded world differs from target")
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        by_label = defaultdict(list)
        furniture_labels = []
        for actor in actors:
            label = actor.get_actor_label()
            by_label[label].append(actor)
            if TAG in {str(t) for t in actor.get_editor_property("tags")} or label.startswith("OTS_Blender_"):
                furniture_labels.append(label)
        placements = build["furniture_placements"]
        expected_labels = Counter(item["actor"] for item in placements)
        actual_labels = Counter(furniture_labels)
        check(report, "furniture_inventory", bool(placements)
              and actual_labels == expected_labels and all(n == 1 for n in expected_labels.values()),
              expected=len(placements), actual=len(furniture_labels),
              missing=list((expected_labels - actual_labels).elements()),
              unexpected=list((actual_labels - expected_labels).elements()))
        buildings = {b["label"]: b for b in build["buildings"]["buildings"]}
        grouped = defaultdict(list)
        for entry in placements:
            label = entry["actor"]
            matches = by_label[label]
            if len(matches) != 1:
                check(report, "actor:" + label, False, matched_actors=len(matches))
                continue
            actor = matches[0]
            components = actor.get_components_by_class(unreal.StaticMeshComponent)
            location = xyz(actor.get_actor_location())
            actor_bounds = bounds(actor)
            mesh_paths, missing_materials, collision_states = [], [], []
            material_count = 0
            for component in components:
                mesh = component.get_editor_property("static_mesh")
                mesh_paths.append(asset_path(mesh.get_path_name()) if mesh is not None else None)
                collision_states.append(str(component.get_collision_enabled()))
                if component.get_num_materials() == 0:
                    missing_materials.append(component.get_name() + ":no material slots")
                for index in range(component.get_num_materials()):
                    material = component.get_material(index)
                    material_count += 1
                    if material is None or not unreal.EditorAssetLibrary.does_asset_exist(
                            asset_path(material.get_path_name())):
                        missing_materials.append(component.get_name() + ":" + str(index))
            valid = (len(components) == 1 and mesh_paths == [asset_path(entry["asset"])]
                     and all(abs(location[i] - entry["location_cm"][i]) <= TOLERANCE_CM for i in range(3))
                     and all(c.get_collision_enabled().value == unreal.CollisionEnabled.NO_COLLISION.value for c in components)
                     and not missing_materials)
            check(report, "actor:" + label, valid, location_cm=location,
                  expected_location_cm=entry["location_cm"], meshes=mesh_paths,
                  expected_mesh=asset_path(entry["asset"]), collision=collision_states,
                  expected_collision=str(unreal.CollisionEnabled.NO_COLLISION),
                  collision_values=[repr(c.get_collision_enabled().value) for c in components],
                  expected_collision_value=repr(unreal.CollisionEnabled.NO_COLLISION.value),
                  collision_value_types=[str(type(c.get_collision_enabled().value)) for c in components],
                  collision_equal=[c.get_collision_enabled().value == unreal.CollisionEnabled.NO_COLLISION.value for c in components],
                  component_count=len(components), mesh_match=mesh_paths == [asset_path(entry["asset"])],
                  location_match=all(abs(location[i] - entry["location_cm"][i]) <= TOLERANCE_CM for i in range(3)),
                  material_slots=material_count, missing_materials=missing_materials)
            record = {"actor": label, "asset": asset_path(entry["asset"]), "bounds_cm": actor_bounds,
                      "building": entry["building"], "floor": entry["floor"], "group": entry["group"]}
            report["actors"].append(record)
            grouped[(entry["building"], entry["floor"], entry["group"])].append(record)
        floor_groups = defaultdict(list)
        for (building, floor, group), members in sorted(grouped.items()):
            group_bounds = [[min(m["bounds_cm"][0][i] for m in members) for i in range(3)],
                            [max(m["bounds_cm"][1][i] for m in members) for i in range(3)]]
            elevation = float(buildings[building]["floor_z"][floor - 1])
            key = "{}:F{}:{}".format(building, floor, group)
            check(report, "floor_contact:" + key,
                  abs(group_bounds[0][2] - elevation) <= TOLERANCE_CM,
                  group_min_z_cm=group_bounds[0][2], floor_z_cm=elevation)
            row = {"building": building, "floor": floor, "group": group,
                   "bounds_cm": group_bounds, "floor_z_cm": elevation, "actors": [m["actor"] for m in members]}
            report["groups"].append(row)
            floor_groups[(building, floor)].append(row)
            if group == "Bed":
                parts = {m["asset"].rsplit("/", 1)[-1]: m for m in members}
                mattress = parts.get("SM_OTS_Blender_BedMattress")
                pillow = parts.get("SM_OTS_Blender_BedPillow")
                if mattress is None or pillow is None:
                    check(report, "bed_contacts:" + key, False, reason="Mattress or pillow missing")
                else:
                    mb, pb = mattress["bounds_cm"], pillow["bounds_cm"]
                    mattress_bottom, mattress_top = mb[0][2] - elevation, mb[1][2] - elevation
                    contained = all(pb[0][i] >= mb[0][i] - TOLERANCE_CM
                                    and pb[1][i] <= mb[1][i] + TOLERANCE_CM for i in (0, 1))
                    check(report, "bed_contacts:" + key,
                          abs(mattress_bottom - 44.0) <= TOLERANCE_CM
                          and abs(mattress_top - 59.0) <= TOLERANCE_CM
                          and abs(pb[0][2] - mb[1][2]) <= TOLERANCE_CM and contained,
                          mattress_bottom_above_floor_cm=mattress_bottom,
                          mattress_top_above_floor_cm=mattress_top,
                          pillow_contact_gap_cm=pb[0][2] - mb[1][2], pillow_inside_mattress_xy=contained)
        overlaps = []
        for (building, floor), rows in sorted(floor_groups.items()):
            for first, second in itertools.combinations(rows, 2):
                a, b = first["bounds_cm"], second["bounds_cm"]
                intersection = [min(a[1][i], b[1][i]) - max(a[0][i], b[0][i]) for i in (0, 1)]
                if all(v > TOLERANCE_CM for v in intersection):
                    overlaps.append({"building": building, "floor": floor,
                                     "groups": [first["group"], second["group"]], "intersection_xy_cm": intersection})
        check(report, "same_floor_group_bounds_do_not_overlap", not overlaps, overlaps=overlaps)
        check(report, "all_placements_audited", len(report["actors"]) == len(placements))
        check(report, "map_unchanged", hashlib.sha256(MAP_FILE.read_bytes()).hexdigest() == original_hash)
        report["statistics"] = {"expected_instances": len(placements), "audited_instances": len(report["actors"]),
                                "unique_meshes": len({r["asset"] for r in report["actors"]}),
                                "assembly_groups": len(grouped), "buildings_with_furniture": len({k[0] for k in grouped}),
                                "bed_groups": sum(k[2] == "Bed" for k in grouped), "overlapping_group_pairs": len(overlaps)}
        report["passed"] = not report["errors"]
    except Exception:
        check(report, "audit_exception", False, traceback=traceback.format_exc())
    finally:
        (OUTPUT / "FurnitureAudit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["passed"]:
        unreal.log("OTS_FURNITURE_AUDIT_SUCCESS " + json.dumps(report["statistics"]))
    else:
        unreal.log_error("OTS_FURNITURE_AUDIT_FAILED " + ", ".join(report["errors"]))
    return report


if __name__ == "__main__":
    result = main()
    if not result["passed"]:
        raise RuntimeError("Furniture audit failed; see FurnitureAudit.json")
