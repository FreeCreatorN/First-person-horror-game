"""Independent inspection of saved street lighting and the east T junction.

This module never changes or saves the level. Its standalone entry point loads
the target level and registers collision bodies for real physics queries. The
checks are editor collision probes, not a runtime player walkthrough.
"""
from collections import defaultdict
import json
import math
from pathlib import Path
import traceback

import unreal

TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
OUTPUT = "Saved/CodexOutputs/LightRoadCleanup_20261003/LightingCleanupAudit.json"
BUILD = "Saved/CodexOutputs/EnterableStreet_20261002/BuildReport.json"
TOLERANCE = 0.5


def _xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def _bounds(component):
    origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(component)
    center, half = _xyz(origin), _xyz(extent)
    return [[center[i] - half[i] for i in range(3)],
            [center[i] + half[i] for i in range(3)]]


def _union(boxes):
    return [[min(box[0][i] for box in boxes) for i in range(3)],
            [max(box[1][i] for box in boxes) for i in range(3)]]


def _near(actual, expected, tolerance=TOLERANCE):
    return len(actual) == len(expected) and all(abs(a - b) <= tolerance
                                               for a, b in zip(actual, expected))


def _component_name(component):
    return component.get_owner().get_actor_label() + ":" + component.get_name()


def _check(report, name, passed, **details):
    report["checks"].append(dict(details, name=name, passed=bool(passed)))
    if not passed:
        report["errors"].append(name)


def _section(report, name, callback):
    try:
        callback()
    except Exception:
        _check(report, name + ":exception", False, traceback=traceback.format_exc())


def _materials(component):
    """Include material-instance parents so an instance cannot hide a lamp skin."""
    rows = []
    for index in range(component.get_num_materials()):
        material = component.get_material(index)
        chain, seen = [], set()
        while material is not None and material.get_path_name() not in seen:
            path = material.get_path_name()
            seen.add(path)
            chain.append({"name": material.get_name(), "path": path})
            if not isinstance(material, unreal.MaterialInstance):
                break
            material = material.get_editor_property("parent")
        rows.append({"slot": index, "chain": chain})
    return rows


def _samples(route, spacing=25.0):
    for first, second in zip(route, route[1:]):
        count = max(1, math.ceil(math.dist(first, second) / spacing))
        for index in range(count + 1):
            yield [first[i] + (second[i] - first[i]) * index / count
                   for i in range(3)]


def _route_probe(world, route):
    from ValidateEnterableStreet import capsule_blocking_components, floor_support
    rows, failures, previous_height = [], [], None
    for planned in _samples(route):
        support = floor_support(world, planned, tolerance=10.05)
        row = {"planned_foot_cm": planned, "support": support}
        if not support["passed"]:
            row["passed"] = False
            rows.append(row)
            failures.append(row)
            continue
        foot = planned[:2] + [support["support_z"]]
        overlapping = capsule_blocking_components(world, foot)
        obstacles = [{"component": _component_name(c),
                      "top_z_cm": _bounds(c)[1][2]} for c in overlapping]
        # A road/slab edge may rise ten centimetres. A house or lamp cannot be
        # ignored as a floor: all overlapping real collider tops must be low.
        low = all(item["top_z_cm"] <= foot[2] + 10.05 for item in obstacles)
        headroom = capsule_blocking_components(world, foot, lift=45.0)
        height_change = None if previous_height is None else foot[2] - previous_height
        passed = low and not headroom and (height_change is None or abs(height_change) <= 10.05)
        row.update(foot_cm=foot, passed=passed, overlapping_components=obstacles,
                   headroom_blockers=[_component_name(c) for c in headroom],
                   support_height_change_cm=height_change)
        rows.append(row)
        if not passed:
            failures.append(row)
        previous_height = foot[2]
    return {"passed": len(route) >= 2 and bool(rows) and not failures,
            "sample_count": len(rows), "spacing_cm": 25.0, "failures": failures,
            "samples": rows, "capsule_radius_cm": 34.0, "capsule_height_cm": 180.0,
            "allowed_road_step_cm": 10.0, "headroom_lift_cm": 45.0,
            "ignored_actors": []}


def audit_cleanup(world, actors, build):
    """Return complete checks against the cleanup expectations in BuildReport."""
    actors = list(actors)
    report = {"passed": False, "target_level": TARGET, "checks": [], "errors": [],
              "statistics": {}, "limitations": [
                  "Physics queries sample authored paths every 25cm; this is not a runtime player walkthrough.",
                  "Mesh component world AABBs verify structure envelopes, not triangle-level intersections."]}
    if world is None or not world.get_path_name().startswith(TARGET + "."):
        _check(report, "loaded_target_world", False)
        return report
    _check(report, "loaded_target_world", True)
    lighting = build.get("lighting_cleanup", {})
    street = build.get("street_end_cleanup", {})
    _check(report, "lighting_expectations_present", bool(lighting))
    _check(report, "street_end_expectations_present", bool(street))
    by_label = defaultdict(list)
    meshes, lights = [], []
    for actor in actors:
        label = actor.get_actor_label()
        by_label[label].append(actor)
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            if component.get_editor_property("static_mesh") is not None:
                meshes.append({"actor": label, "component": component,
                               "tags": [str(t) for t in actor.get_editor_property("tags")]})
        for component in actor.get_components_by_class(unreal.LightComponentBase):
            lights.append({"actor": label, "component": component})
    duplicate_labels = {label: len(matches) for label, matches in by_label.items() if len(matches) > 1}
    _check(report, "unique_actor_labels", not duplicate_labels, duplicates=duplicate_labels)

    def scene_lighting():
        allowed = lighting.get("allowed_scene_light_labels", [])
        ui_label = lighting.get("ui_only_light_actor")
        _check(report, "allowed_scene_light_expectations", bool(allowed) and len(set(allowed)) == len(allowed))
        scene = [row for row in lights if row["actor"] != ui_label]
        unexpected = [_component_name(row["component"]) for row in scene if row["actor"] not in allowed]
        _check(report, "only_allowed_scene_lights", not unexpected and len(scene) == len(allowed),
               expected_count=len(allowed), actual_count=len(scene), unexpected=unexpected)
        positions = lighting.get("light_expected_positions", {})
        intensities = lighting.get("light_expected_intensities", {})
        kinds = lighting.get("light_expected_kinds", {})
        _check(report, "scene_light_positions_complete", set(positions) == set(allowed))
        _check(report, "scene_light_kinds_complete",
               not kinds or set(kinds) == set(allowed),
               expected_labels=allowed, recorded_kinds=kinds)
        for label in allowed:
            components = [row["component"] for row in scene if row["actor"] == label]
            # SpotLightComponent derives from PointLightComponent, so isinstance
            # cannot distinguish the requested single cone from a point source.
            kind = kinds.get(label, "point")
            expected_class = {"spot": "SpotLightComponent",
                              "point": "PointLightComponent"}.get(kind)
            valid = (len(components) == 1 and expected_class is not None
                     and components[0].get_class().get_name() == expected_class)
            _check(report, "one_scene_light:" + label, valid,
                   expected_kind=kind,
                   components=[c.get_class().get_name() for c in components])
            if not valid:
                continue
            component = components[0]
            location = _xyz(component.get_world_location())
            radius = float(component.get_editor_property("attenuation_radius"))
            intensity = float(component.get_editor_property("intensity"))
            _check(report, "scene_light_position:" + label,
                   label in positions and _near(location, positions[label]),
                   actual_cm=location, expected_cm=positions.get(label))
            _check(report, "scene_light_radius:" + label, 0.0 < radius <= 1100.01,
                   attenuation_radius_cm=radius, maximum_cm=1100.0)
            target_intensity = intensities.get(label)
            _check(report, "scene_light_intensity:" + label,
                   0.0 < intensity <= 900.01 and (target_intensity is None or abs(intensity - target_intensity) <= .01),
                   intensity=intensity, expected_intensity=target_intensity)
        ui_actors = by_label.get(ui_label, [])
        ui_components = [row["component"] for row in lights if row["actor"] == ui_label]
        capture_count = sum(len(a.get_components_by_class(unreal.SceneCaptureComponent2D)) for a in ui_actors)
        ui_details = []
        for component in ui_components:
            is_local = isinstance(component, unreal.LocalLightComponent)
            radius = float(component.get_editor_property("attenuation_radius")) if is_local else None
            z = float(component.get_world_location().z)
            ui_details.append({"component": _component_name(component), "world_z_cm": z,
                               "radius_cm": radius,
                               "below_ground": is_local and z + radius < 0.0})
        _check(report, "inventory_lights_are_isolated_below_ground",
               len(ui_actors) == 1 and len(ui_details) == 2 and capture_count >= 1
               and all(row["below_ground"] for row in ui_details),
               ui_actor=ui_label, scene_capture_components=capture_count, lights=ui_details)
        remaining = sorted(set(lighting.get("removed_actor_labels", [])) & set(by_label))
        _check(report, "removed_actors_absent", not remaining, remaining=remaining,
               expected_removed=len(lighting.get("removed_actor_labels", [])))

    def poles_and_materials():
        positions = lighting.get("lamp_positions", {})
        _check(report, "lamp_position_expectations_present", bool(positions))
        for label, expected in positions.items():
            actual = by_label.get(label, [])
            location = _xyz(actual[0].get_actor_location()) if len(actual) == 1 else None
            _check(report, "street_lamp_position:" + label,
                   location is not None and _near(location, expected), actual_cm=location, expected_cm=expected)
        disallowed = set(lighting.get("emissive_disallowed_materials", []))
        _check(report, "emissive_material_expectations_present", bool(disallowed))
        violations, tubes_on_poles = [], []
        for row in meshes:
            for slot in _materials(row["component"]):
                for material in slot["chain"]:
                    if material["name"] not in disallowed:
                        continue
                    entry = {"actor": row["actor"], "component": row["component"].get_name(),
                             "slot": slot["slot"], "material": material["path"]}
                    if material["name"] == "M_OTS_FluorescentTube" and row["actor"] in positions:
                        tubes_on_poles.append(entry)
                    else:
                        violations.append(entry)
        _check(report, "only_street_lamps_use_emissive_skins", not violations,
               violations=violations, lamp_emissive_slots=tubes_on_poles)

    def real_junction_routes():
        from ValidateEnterableStreet import capsule_blocking_components
        controls = [row for row in meshes if row["actor"].startswith("OTS_Enterable_")
                    and "_WallPanel_" in row["actor"]]
        _check(report, "blocking_wall_control_exists", bool(controls))
        if controls:
            component = controls[0]["component"]
            box = _bounds(component)
            center = [(box[0][i] + box[1][i]) * .5 for i in range(3)]
            foot = center[:2] + [center[2] - 92.0]
            hits = capsule_blocking_components(world, foot)
            names = [_component_name(c) for c in hits]
            _check(report, "real_blocking_wall_negative_control",
                   _component_name(component) in names, actor=controls[0]["actor"],
                   foot_cm=foot, detected_components=names)
        routes = street.get("junction_routes", [])
        _check(report, "north_and_south_junction_routes_present", len(routes) >= 2)
        for route in routes:
            result = _route_probe(world, route.get("waypoints_cm", []))
            passed = result.pop("passed")
            _check(report, "junction_route:" + route.get("name", "unnamed"), passed, **result)

    def junction_geometry():
        label = street.get("east_building_label")
        tagged = [row for row in meshes if row["actor"] == label or "OTS_Building_" + str(label) in row["tags"]]
        _check(report, "east_building_structure_exists", bool(tagged), building=label,
               real_mesh_components=len(tagged))
        if tagged:
            # Ground slabs are authored 20cm below their 11cm walking top;
            # their underside is -9cm, outside the reported facade envelope.
            # Verify the real exterior wall envelope against world_min/max,
            # and separately retain bounds for every structure component.
            walls = [row for row in tagged if "_WallPanel_" in row["actor"]]
            box = _union([_bounds(row["component"]) for row in walls]) if walls else None
            low, high = street.get("east_building_world_min"), street.get("east_building_world_max")
            _check(report, "east_building_actual_structure_bounds",
                   box is not None and low is not None and high is not None
                   and _near(box[0], low) and _near(box[1], high),
                   actual_exterior_wall_bounds_cm=box, expected_bounds_cm=[low, high],
                   all_structure_bounds_cm=_union([_bounds(row["component"]) for row in tagged]),
                   exterior_wall_components=len(walls),
                   scope="Real exterior walls define the building envelope; slab undersides extend below it")
            structure = build.get("buildings", {})
            expectations = {item["actor"]: item for item in structure.get("structural_boxes", [])
                            if item.get("building") == label}
            actual_parts = defaultdict(list)
            for row in tagged:
                actual_parts[row["actor"]].append(_bounds(row["component"]))
            missing = sorted(set(expectations) - set(actual_parts))
            unexpected = sorted(set(actual_parts) - set(expectations))
            invalid_parts = []
            for part_label in sorted(set(expectations) & set(actual_parts)):
                bounds = _union(actual_parts[part_label])
                expected = expectations[part_label]
                if not _near(bounds[0], expected["min"]) or not _near(bounds[1], expected["max"]):
                    invalid_parts.append({"actor": part_label, "actual_bounds_cm": bounds,
                                          "expected_bounds_cm": [expected["min"], expected["max"]]})
            _check(report, "all_east_structure_follows_envelope",
                   bool(expectations) and not missing and not unexpected and not invalid_parts,
                   expected_components=len(expectations), actual_components=len(actual_parts),
                   missing_parts=missing, unexpected_parts=unexpected, invalid_parts=invalid_parts,
                   scope="Each actual structural component matches its translated authored box exactly")
        attachments = street.get("attachment_expected_positions", {})
        _check(report, "east_attachment_expectations_present", bool(attachments))
        for label, expected in attachments.items():
            actual = by_label.get(label, [])
            position = _xyz(actual[0].get_actor_location()) if len(actual) == 1 else None
            _check(report, "east_attachment_position:" + label,
                   position is not None and _near(position, expected),
                   actual_cm=position, expected_cm=expected)
        surfaces = street.get("road_surface_expectations", [])
        _check(report, "junction_surface_expectations_present", bool(surfaces))
        for surface in surfaces:
            label = surface["actor"]
            matching = [row for row in meshes if row["actor"] == label]
            box = _union([_bounds(row["component"]) for row in matching]) if matching else None
            _check(report, "junction_surface_bounds:" + label,
                   len(by_label.get(label, [])) == 1 and box is not None
                   and _near(box[0], surface["world_min"]) and _near(box[1], surface["world_max"]),
                   actual_bounds_cm=box, expected_bounds_cm=[surface["world_min"], surface["world_max"]])
        closed_gaps = street.get("closed_service_gaps", [])
        reopened_gaps = street.get("reopened_service_gaps", [])
        expected_gaps = {"ClosedServiceGap" + suffix for suffix in
                         ("South01", "South02", "South03", "North01", "North02")}
        gap_names = [gap["name"] for gap in closed_gaps + reopened_gaps]
        _check(report, "five_service_gaps_accounted",
               len(gap_names) == 5 and set(gap_names) == expected_gaps,
               expected_count=5, closed_count=len(closed_gaps),
               reopened_count=len(reopened_gaps), recorded_names=gap_names)
        for gap in closed_gaps:
            label = "OTS_RoadRevision_" + gap["name"]
            matching = [row for row in meshes if row["actor"] == label]
            box = _bounds(matching[0]["component"]) if len(matching) == 1 else None
            blocking = False
            collision_enabled, pawn_response = None, None
            if len(matching) == 1:
                component = matching[0]["component"]
                enabled = component.get_collision_enabled()
                response = component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN)
                collision_enabled, pawn_response = str(enabled), str(response)
                blocking = enabled.value != unreal.CollisionEnabled.NO_COLLISION.value
                blocking = blocking and response.value == unreal.CollisionResponseType.ECR_BLOCK.value
            _check(report, "closed_service_gap:" + gap["name"],
                   len(by_label.get(label, [])) == 1 and box is not None and blocking
                   and _near(box[0], gap["world_min"]) and _near(box[1], gap["world_max"]),
                   actor=label, mesh_components=len(matching), actual_bounds_cm=box,
                   expected_bounds_cm=[gap["world_min"], gap["world_max"]],
                   collision_enabled=collision_enabled, pawn_response=pawn_response)
        for gap in reopened_gaps:
            former_label = gap["former_closure_actor"]
            _check(report, "reopened_service_gap_closure_absent:" + gap["name"],
                   former_label == "OTS_RoadRevision_" + gap["name"]
                   and not by_label.get(former_label),
                   former_closure_actor=former_label,
                   actual_actor_count=len(by_label.get(former_label, [])))
            label = gap["surface_actor"]
            matching = [row for row in meshes if row["actor"] == label]
            box = _bounds(matching[0]["component"]) if len(matching) == 1 else None
            blocking = False
            collision_enabled, channel_responses = None, {}
            if len(matching) == 1:
                component = matching[0]["component"]
                enabled = component.get_collision_enabled()
                collision_enabled = str(enabled)
                channels = (unreal.CollisionChannel.ECC_WORLD_STATIC,
                            unreal.CollisionChannel.ECC_WORLD_DYNAMIC,
                            unreal.CollisionChannel.ECC_PAWN,
                            unreal.CollisionChannel.ECC_VISIBILITY,
                            unreal.CollisionChannel.ECC_CAMERA)
                responses = [component.get_collision_response_to_channel(channel)
                             for channel in channels]
                channel_responses = {str(channel): str(response)
                                     for channel, response in zip(channels, responses)}
                blocking = (enabled.value != unreal.CollisionEnabled.NO_COLLISION.value
                            and all(response.value == unreal.CollisionResponseType.ECR_BLOCK.value
                                    for response in responses))
            _check(report, "reopened_service_gap_surface:" + gap["name"],
                   len(by_label.get(label, [])) == 1 and box is not None and blocking
                   and _near(box[0], gap["surface_world_min"])
                   and _near(box[1], gap["surface_world_max"]),
                   actor=label, mesh_components=len(matching), actual_bounds_cm=box,
                   expected_bounds_cm=[gap["surface_world_min"], gap["surface_world_max"]],
                   collision_enabled=collision_enabled, channel_responses=channel_responses)
            result = _route_probe(world, gap["route"])
            passed = result.pop("passed")
            _check(report, "reopened_service_gap_route:" + gap["name"], passed, **result)

    for name, callback in (("lighting", scene_lighting), ("poles_materials", poles_and_materials),
                           ("routes", real_junction_routes), ("junction_geometry", junction_geometry)):
        _section(report, name, callback)
    report["statistics"] = {"actors": len(actors), "mesh_components": len(meshes),
                            "light_components": len(lights), "checks": len(report["checks"]),
                            "failed_checks": len(report["errors"]),
                            "planned_lamps": len(lighting.get("lamp_positions", {})),
                            "planned_scene_lights": len(lighting.get("allowed_scene_light_labels", []))}
    report["passed"] = not report["errors"]
    return report


def main():
    import sys
    project = Path(unreal.Paths.project_dir()).resolve()
    sys.path.insert(0, str(project / "Scripts"))
    output = project / OUTPUT
    result = {"passed": False, "checks": [], "errors": ["commandlet_exception"], "statistics": {}}
    try:
        build = json.loads((project / BUILD).read_text(encoding="utf-8"))
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET):
            raise RuntimeError("Saved target level failed to load")
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        from ValidateEnterableStreet import refresh_world_collision
        refresh_world_collision(actors)
        result = audit_cleanup(world, actors, build)
    except Exception:
        result["traceback"] = traceback.format_exc()
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not result["passed"]:
        unreal.log_error("OTS_LIGHTING_CLEANUP_AUDIT_FAILED " + ", ".join(result["errors"]))
        raise RuntimeError("Lighting/road cleanup audit failed; see LightingCleanupAudit.json")
    unreal.log("OTS_LIGHTING_CLEANUP_AUDIT_SUCCESS " + json.dumps(result["statistics"]))
    return result


if __name__ == "__main__":
    main()
