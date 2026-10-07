"""Inspect saved alley access and directional street lamps using real collision.

The audit registers loaded collision bodies, but never saves or edits authored
geometry. Sampled capsule checks are editor physics queries, not player input.
"""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import traceback

import unreal

from AuditOldTownLightingCleanup import _bounds, _near, _union, _xyz
from ValidateEnterableStreet import (
    capsule_blocking_components, refresh_world_collision,
)

TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
TOLERANCE = 0.5
GAP_NAMES = {
    "ClosedServiceGapSouth01", "ClosedServiceGapSouth02",
    "ClosedServiceGapSouth03", "ClosedServiceGapNorth01",
    "ClosedServiceGapNorth02",
}
PARTY_WALLS = {
    "OTS_RoadRevision_AlleyPartyWallNorthWest",
    "OTS_RoadRevision_AlleyPartyWallNorthEast",
    "OTS_RoadRevision_AlleyPartyWallSouthWest",
    "OTS_RoadRevision_AlleyPartyWallSouthEast",
}


def _check(report, name, passed, **details):
    report["checks"].append(dict(details, name=name, passed=bool(passed)))
    if not passed:
        report["errors"].append(name)


def _section(report, name, callback):
    try:
        callback()
    except Exception:
        _check(report, name + ":exception", False,
               traceback=traceback.format_exc(limit=4))


def _component_name(component):
    return component.get_owner().get_actor_label() + ":" + component.get_name()


def _blocks_pawn(component):
    return (component.get_collision_enabled().value
            != unreal.CollisionEnabled.NO_COLLISION.value
            and component.get_collision_response_to_channel(
                unreal.CollisionChannel.ECC_PAWN).value
            == unreal.CollisionResponseType.ECR_BLOCK.value)


def _samples(route):
    for first, second in zip(route, route[1:]):
        count = max(1, math.ceil(math.dist(first, second) / 25.0))
        for index in range(count + 1):
            yield [first[axis] + (second[axis] - first[axis]) * index / count
                   for axis in range(3)]


def _pawn_floor_support(world, foot, tolerance):
    """Find a physical floor without treating overlap triggers as support.

    Object traces also report the home's interaction box. Multi-hit queries
    keep every actor eligible and let us select an actual Pawn-blocking top
    surface rather than ignoring the whole home to get past its trigger.
    """
    hits = unreal.SystemLibrary.line_trace_multi_for_objects(
        world, unreal.Vector(foot[0], foot[1], foot[2] + 45.0),
        unreal.Vector(foot[0], foot[1], foot[2] - 45.0),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1,
         unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
        False, [], unreal.DrawDebugTrace.NONE) or []
    floors, nonblocking = [], []
    for hit in hits:
        values = hit.to_tuple()
        component = values[10]
        if component is None:
            continue
        if not _blocks_pawn(component):
            nonblocking.append(_component_name(component))
            continue
        # Tuple fields were inspected in the same installed UE build:
        # 0 blocking_hit, 1 start_penetrating, 5 impact_point, 7 impact_normal.
        if values[0] and not values[1] and float(values[7].z) >= 0.5:
            floors.append((float(values[5].z), _component_name(component)))
    details = {"foot": foot,
               "excluded_nonblocking_support_components": sorted(set(nonblocking))}
    if not floors:
        return dict(details, passed=False, reason="No Pawn-blocking supporting top surface")
    support_z, component_name = max(floors)
    error = support_z - float(foot[2])
    return dict(details, passed=abs(error) <= tolerance, support_z=support_z,
                error_cm=error, support_component=component_name)


def _probe(world, route, support_tolerance=10.05):
    """Require support and a standing 34cm-radius, 180cm-high capsule.

    A lifted capsule is only needed when the standing capsule touches a real
    low step. This does not add 45cm of clearance to every doorway or alley.
    """
    failures, count, previous_height, nonblocking_supports = [], 0, None, set()
    for planned in _samples(route):
        count += 1
        support = _pawn_floor_support(world, planned, tolerance=support_tolerance)
        nonblocking_supports.update(support["excluded_nonblocking_support_components"])
        if not support["passed"]:
            failures.append({"planned_foot_cm": planned, "support": support})
            continue
        foot = planned[:2] + [support["support_z"]]
        blockers = capsule_blocking_components(world, foot)
        obstacles = [{"component": _component_name(component),
                      "top_z_cm": _bounds(component)[1][2]}
                     for component in blockers]
        low = all(row["top_z_cm"] <= foot[2] + 10.05 for row in obstacles)
        lifted = (capsule_blocking_components(world, foot, lift=10.1)
                  if blockers and low else [])
        height_change = (None if previous_height is None
                         else foot[2] - previous_height)
        passed = (low and not lifted
                  and (height_change is None or abs(height_change) <= 10.05))
        if not passed:
            failures.append({"planned_foot_cm": planned, "foot_cm": foot,
                             "blockers": obstacles,
                             "step_headroom_blockers": [
                                 _component_name(component) for component in lifted],
                             "support_height_change_cm": height_change})
        previous_height = foot[2]
    return {"passed": len(route) >= 2 and count > 0 and not failures,
            "sample_count": count, "spacing_cm": 25.0,
            "capsule_radius_cm": 34.0, "capsule_height_cm": 180.0,
            "support_tolerance_cm": support_tolerance,
            "support_query": "Multi-object trace; only Pawn-blocking upward top surfaces",
            "excluded_nonblocking_support_components": sorted(nonblocking_supports),
            "failures": failures, "ignored_actors": []}


def _overlap_xy(first, second):
    return (first[0] < second[2] - 0.05 and first[2] > second[0] + 0.05
            and first[1] < second[3] - 0.05 and first[3] > second[1] + 0.05)


def audit(world, actors, build, plan):
    """Return checks against build.street_access_lighting and actual actors."""
    actors = list(actors)
    target = build.get("target_level") or plan.get("target_level") or TARGET
    report = {"passed": False, "target_level": target, "checks": [],
              "errors": [], "map_sha256": None, "statistics": {}}
    section = build.get("street_access_lighting", {})
    _check(report, "street_access_lighting_contract_present", bool(section))
    loaded = world is not None and world.get_path_name().startswith(target + ".")
    _check(report, "loaded_target_world", loaded)
    if not loaded or not section:
        return report

    by_label, meshes, lights = defaultdict(list), defaultdict(list), defaultdict(list)
    for actor in actors:
        label = actor.get_actor_label()
        by_label[label].append(actor)
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            if component.get_editor_property("static_mesh") is not None:
                meshes[label].append(component)
        lights[label].extend(actor.get_components_by_class(unreal.LightComponentBase))
    duplicates = {label: len(matches) for label, matches in by_label.items()
                  if len(matches) != 1}
    _check(report, "unique_actor_labels", not duplicates, duplicates=duplicates)

    def saved_map():
        path = Path(unreal.Paths.project_dir()).resolve() / "Content" / (
            target.removeprefix("/Game/") + ".umap")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        report["map_sha256"] = actual
        _check(report, "saved_map_matches_build", actual == build.get("map_sha256"),
               actual_sha256=actual, expected_sha256=build.get("map_sha256"))

    _section(report, "saved_map", saved_map)

    def collision_registration():
        count = refresh_world_collision(actors)
        report["statistics"]["refreshed_collision_components"] = count
        _check(report, "collision_components_registered", count > 0, count=count)
        control_labels = sorted(PARTY_WALLS & set(by_label))
        detected = []
        if control_labels and len(by_label[control_labels[0]]) == 1:
            control = by_label[control_labels[0]][0]
            center, _extent = control.get_actor_bounds(False)
            foot = [float(center.x), float(center.y), float(center.z) - 92.0]
            detected = [_component_name(component)
                        for component in capsule_blocking_components(world, foot)]
        _check(report, "collision_wall_negative_control",
               bool(control_labels) and any(
                   name.startswith(control_labels[0] + ":") for name in detected),
               control_actor=control_labels[0] if control_labels else None,
               detected_components=detected)

    _section(report, "collision_registration", collision_registration)
    route_sample_count = 0

    def alley_access():
        nonlocal route_sample_count
        gaps = section.get("reopened_gaps", [])
        _check(report, "five_known_gaps_reopened",
               len(gaps) == 5 and {gap["name"] for gap in gaps} == GAP_NAMES)
        old_wall_labels = {"OTS_RoadRevision_" + name for name in GAP_NAMES}
        remaining = sorted(old_wall_labels & set(by_label))
        _check(report, "former_gap_walls_absent", not remaining, remaining=remaining)
        stale_plan = [wall["name"] for wall in plan.get("replacement_party_walls", [])
                      if wall["name"] in GAP_NAMES]
        _check(report, "plan_no_longer_requires_gap_closures",
               not stale_plan and not plan.get("closed_service_gaps"),
               stale_party_wall_names=stale_plan)
        for gap in gaps:
            name, label = gap["name"], gap["actor"]
            components = meshes.get(label, [])
            bounds = _union([_bounds(component) for component in components]) if components else None
            expected_width = gap["world_max"][0] - gap["world_min"][0]
            _check(report, "gap_contract:" + name,
                   gap["removed_wall_actor"] == "OTS_RoadRevision_" + name
                   and abs(float(gap["width_cm"]) - 150.0) <= 0.01
                   and abs(expected_width - 150.0) <= 0.01
                   and abs(gap["world_max"][2] - 11.0) <= 0.01)
            _check(report, "gap_paving_bounds:" + name,
                   len(by_label.get(label, [])) == 1 and bounds is not None
                   and _near(bounds[0], gap["world_min"])
                   and _near(bounds[1], gap["world_max"])
                   and all(_blocks_pawn(component) for component in components),
                   actual_bounds_cm=bounds,
                   expected_bounds_cm=[gap["world_min"], gap["world_max"]])
            route_points = gap["route_points_cm"]
            center_x = (gap["world_min"][0] + gap["world_max"][0]) * 0.5
            _check(report, "gap_route_connects_front_and_rear:" + name,
                   len(route_points) >= 2
                   and all(abs(point[0] - center_x) <= 0.5
                           and abs(point[2] - 11.0) <= 0.5 for point in route_points)
                   and min(point[1] for point in route_points) <= gap["world_min"][1] + 0.5
                   and max(point[1] for point in route_points) >= gap["world_max"][1] - 0.5,
                   route_points_cm=route_points)
            for offset in (-25.0, 0.0, 25.0):
                route = [[point[0] + offset, point[1], point[2]]
                         for point in gap["route_points_cm"]]
                result = _probe(world, route, support_tolerance=0.5)
                route_sample_count += result["sample_count"]
                _check(report, "gap_capsule_route:" + name + ":" + str(int(offset)),
                       result["passed"], lateral_offset_cm=offset, **{
                           key: value for key, value in result.items() if key != "passed"})
            rectangle = gap["visual_clear_rect"]
            visual_blockers = []
            for actor_label, actor_meshes in meshes.items():
                if actor_label == label:
                    continue
                for component in actor_meshes:
                    if (not component.get_editor_property("visible")
                            or component.get_editor_property("hidden_in_game")):
                        continue
                    lower, upper = _bounds(component)
                    if (upper[2] > 13.0 and lower[2] < 191.0
                            and _overlap_xy(rectangle, [lower[0], lower[1], upper[0], upper[1]])):
                        visual_blockers.append({"component": _component_name(component),
                                                "bounds_cm": [lower, upper]})
            _check(report, "gap_visible_clearance:" + name, not visual_blockers,
                   rectangle_cm=rectangle, blockers=visual_blockers)

    _section(report, "alley_access", alley_access)

    def preserved_roads_and_walls():
        roads = section.get("road_preservation", [])
        required = {"OTS_RoadRevision_MainRoad", "OTS_RoadRevision_EastCrossRoad",
                    "OTS_RoadRevision_MainWalkNorth", "OTS_RoadRevision_MainWalkSouth"}
        _check(report, "road_preservation_expectations_complete",
               required <= {road["actor"] for road in roads})
        for road in roads:
            label = road["actor"]
            components = meshes.get(label, [])
            bounds = _union([_bounds(component) for component in components]) if components else None
            _check(report, "preserved_road_bounds:" + label,
                   len(by_label.get(label, [])) == 1 and bounds is not None
                   and _near(bounds[0], road["world_min"])
                   and _near(bounds[1], road["world_max"]), actual_bounds_cm=bounds,
                   expected_bounds_cm=[road["world_min"], road["world_max"]])
            if label in ("OTS_RoadRevision_MainRoad", "OTS_RoadRevision_EastCrossRoad"):
                width_axis = 1 if label.endswith("MainRoad") else 0
                width = None if bounds is None else bounds[1][width_axis] - bounds[0][width_axis]
                _check(report, "carriageway_stays_700cm:" + label,
                       width is not None and abs(width - 700.0) <= TOLERANCE,
                       actual_width_cm=width)
        kept = section.get("kept_party_wall_actors", [])
        _check(report, "four_central_alley_sidewalls_retained", len(kept) == 4 and set(kept) == PARTY_WALLS)
        planned_walls = {wall["name"]: wall for wall in plan.get("replacement_party_walls", [])}
        for label in kept:
            expected = planned_walls.get(label.removeprefix("OTS_RoadRevision_"))
            components = meshes.get(label, [])
            bounds = _union([_bounds(component) for component in components]) if components else None
            _check(report, "central_alley_sidewall:" + label,
                   len(by_label.get(label, [])) == 1 and bounds is not None and expected is not None
                   and _near(bounds[0], expected["world_min"])
                   and _near(bounds[1], expected["world_max"])
                   and all(_blocks_pawn(component) for component in components), actual_bounds_cm=bounds)

    _section(report, "road_and_wall_preservation", preserved_roads_and_walls)

    def utility_assemblies_and_wires():
        moves = section.get("utility_moves", [])
        pole_positions = {
            "OTS_UtilityPole_02_01": [4790.0, -500.0, 325.0],
            "OTS_UtilityPole_02_Crossarm_01": [4790.0, -500.0, 610.0],
            "OTS_UtilityPole_02_Insulator_01": [4852.0, -500.0, 628.0],
            "OTS_UtilityPole_02_Insulator_02": [4790.0, -500.0, 628.0],
            "OTS_UtilityPole_02_Insulator_03": [4728.0, -500.0, 628.0],
        }
        wall_parts = {"OTS_P2Prop_WallUtilityCluster_03_" + suffix for suffix in (
            "Downpipe", "MeterCabinet", "JunctionBox", "ServiceConduits",
            "ServiceCableAssembly")}
        expected_labels = set(pole_positions) | wall_parts
        actual_pole_labels = {label for label in by_label if label.startswith("OTS_UtilityPole_02_")}
        actual_wall_labels = {label for label in by_label if label.startswith("OTS_P2Prop_WallUtilityCluster_03_")}
        _check(report, "complete_moved_utility_assemblies",
               len(moves) == 10 and {move["actor"] for move in moves} == expected_labels
               and actual_pole_labels == set(pole_positions) and actual_wall_labels == wall_parts,
               pole_parts=sorted(actual_pole_labels), wall_parts=sorted(actual_wall_labels))
        source_path = (Path(unreal.Paths.project_dir()).resolve()
                       / "Saved/CodexOutputs/HotelPolish_20261005/PreservationBaseline.json")
        source_states = json.loads(source_path.read_text(encoding="utf-8-sig"))["actors"]
        actual_boxes = {}
        for move in moves:
            label = move["actor"]
            matches, components = by_label.get(label, []), meshes.get(label, [])
            position = _xyz(matches[0].get_actor_location()) if len(matches) == 1 else None
            bounds = _union([_bounds(component) for component in components]) if components else None
            source = source_states.get(label)
            expected_position = (pole_positions.get(label) if label in pole_positions else
                                 [source["location"][0] - 35.0] + source["location"][1:]
                                 if source is not None and label in wall_parts else None)
            expected_delta = ([expected_position[i] - source["location"][i] for i in range(3)]
                              if expected_position is not None and source is not None else None)
            _check(report, "moved_utility_position:" + label,
                   position is not None and expected_position is not None
                   and _near(position, expected_position, 0.05)
                   and _near(position, move["position_cm"], 0.05)
                   and expected_delta is not None and _near(move["delta_cm"], expected_delta, 0.05),
                   actual_cm=position, expected_cm=expected_position,
                   recorded_delta_cm=move["delta_cm"])
            expected_bounds = move["bounds"]
            _check(report, "moved_utility_bounds:" + label,
                   len(matches) == 1 and bounds is not None
                   and _near(bounds[0], expected_bounds[0], 0.05)
                   and _near(bounds[1], expected_bounds[1], 0.05),
                   actual_bounds_cm=bounds, expected_bounds_cm=expected_bounds)
            if bounds is not None:
                actual_boxes[label] = bounds
            if len(matches) != 1 or source is None:
                continue
            rotation = matches[0].get_actor_rotation()
            rotation_values = [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)]
            expected_rotation = [0.0, 90.0, 0.0] if label in pole_positions else source["rotation"]
            rotation_errors = [(rotation_values[i] - expected_rotation[i] + 180.0) % 360.0 - 180.0
                               for i in range(3)]
            scale = _xyz(matches[0].get_actor_scale3d())
            _check(report, "moved_utility_orientation_and_scale:" + label,
                   all(abs(error) <= 0.01 for error in rotation_errors)
                   and _near(scale, source["scale"], 0.0001),
                   actual_rotation_degrees=rotation_values, expected_rotation_degrees=expected_rotation,
                   actual_scale=scale, expected_scale=source["scale"])
            if label in pole_positions:
                _check(report, "rotated_pole_part_inside_original_sidewalk:" + label,
                       bounds is not None and bounds[0][1] >= -530.05 and bounds[1][1] <= -349.95,
                       actual_bounds_cm=bounds, original_sidewalk_y_cm=[-530.0, -350.0])
        crossarm = actual_boxes.get("OTS_UtilityPole_02_Crossarm_01")
        _check(report, "crossarm_runs_along_sidewalk",
               crossarm is not None
               and _near(crossarm[0], [4705.0, -515.0, 603.0], 0.05)
               and _near(crossarm[1], [4875.0, -485.0, 617.0], 0.05),
               actual_bounds_cm=crossarm)
        shaft = meshes.get("OTS_UtilityPole_02_01", [])
        _check(report, "moved_utility_shaft_still_blocks_pawn",
               len(shaft) == 1 and _blocks_pawn(shaft[0]))

        wires = section.get("wire_adjustments", [])
        wire_connections = {
            "OTS_OverheadWire_03": ([3900.0, -231.9, 570.0], [4852.0, -500.0, 640.0],
                                    "OTS_UtilityPole_02_Insulator_01"),
            "OTS_OverheadWire_06": ([3900.0, -204.0, 570.0], [4790.0, -500.0, 640.0],
                                    "OTS_UtilityPole_02_Insulator_02"),
            "OTS_OverheadWire_09": ([3900.0, -176.1, 570.0], [4728.0, -500.0, 640.0],
                                    "OTS_UtilityPole_02_Insulator_03"),
        }
        _check(report, "three_terminal_wires_adjusted",
               len(wires) == 3 and {wire["actor"] for wire in wires} == set(wire_connections))
        for wire in wires:
            label = wire["actor"]
            components = meshes.get(label, [])
            valid = len(by_label.get(label, [])) == 1 and len(components) == 1 and label in wire_connections
            _check(report, "terminal_wire_component:" + label, valid)
            if not valid:
                continue
            component = components[0]
            mesh_bounds = component.get_editor_property("static_mesh").get_bounds()
            transform = component.get_world_transform()
            endpoints = sorted([
                _xyz(transform.transform_location(unreal.Vector(
                    mesh_bounds.origin.x + sign * mesh_bounds.box_extent.x,
                    mesh_bounds.origin.y, mesh_bounds.origin.z))) for sign in (-1.0, 1.0)],
                key=lambda point: point[0])
            first, last, insulator_label = wire_connections[label]
            _check(report, "terminal_wire_actual_endpoints:" + label,
                   len(wire["endpoints_cm"]) == 2
                   and _near(endpoints[0], wire["endpoints_cm"][0], 0.05)
                   and _near(endpoints[1], wire["endpoints_cm"][1], 0.05)
                   and _near(endpoints[0], first, 0.05) and _near(endpoints[1], last, 0.05)
                   and wire.get("kept_first_endpoint") is True,
                   actual_endpoints_cm=endpoints, original_first_endpoint_cm=first,
                   expected_second_endpoint_cm=last)
            insulator = actual_boxes.get(insulator_label)
            _check(report, "terminal_wire_contacts_insulator:" + label,
                   insulator is not None and all(insulator[0][i] - 0.05 <= endpoints[1][i]
                                                <= insulator[1][i] + 0.05 for i in range(3)),
                   endpoint_cm=endpoints[1], insulator_actor=insulator_label,
                   insulator_bounds_cm=insulator)
            _check(report, "terminal_wire_remains_noncolliding:" + label,
                   wire.get("collision") == "NoCollision"
                   and component.get_collision_enabled().value == unreal.CollisionEnabled.NO_COLLISION.value)

    _section(report, "utility_assemblies_and_wires", utility_assemblies_and_wires)

    def door_access_and_lamp_bases():
        nonlocal route_sample_count
        doors = section.get("door_approaches", [])
        _check(report, "door_approach_expectations_present", bool(doors))
        home_doors = [door for door in doors if door["side"] == "North"
                      and abs(float(door["coordinate_cm"]) - 1169.0) <= 0.5]
        _check(report, "main_home_1169_door_included", bool(home_doors))
        missing_entrances = []
        for entrance in plan.get("building_entrances", []):
            network = entrance.get("approach_network")
            side = {"MainWalkNorth": "North", "MainWalkSouth": "South",
                    "EastBoundaryWalk": "East"}.get(network)
            if side is None:
                continue
            coordinate = entrance["outdoor_route"][-1][1 if side == "East" else 0]
            if not any(door["side"] == side
                       and abs(float(door["coordinate_cm"]) - coordinate) <= 0.5 for door in doors):
                missing_entrances.append({"building": entrance["building"],
                                          "side": side, "coordinate_cm": coordinate})
        _check(report, "all_planned_street_entrances_included", not missing_entrances,
               missing_entrances=missing_entrances)
        for door in doors:
            _check(report, "door_contract:" + door["name"],
                   door["side"] in ("North", "South", "East")
                   and float(door["opening_width_cm"]) >= 68.0)
            result = _probe(world, door["route_points_cm"])
            route_sample_count += result["sample_count"]
            _check(report, "door_capsule_approach:" + door["name"], result["passed"], **{
                key: value for key, value in result.items() if key != "passed"})
        moves = section.get("lamp_moves", [])
        expected_labels = {"OTS_P2Prop_StreetLamp_" + str(index).zfill(2)
                           for index in range(1, 10)}
        _check(report, "all_nine_lamp_positions_recorded",
               len(moves) == 9 and {row["actor"] for row in moves} == expected_labels)
        carriageways = [road for road in section.get("road_preservation", [])
                        if road["actor"] in ("OTS_RoadRevision_MainRoad", "OTS_RoadRevision_EastCrossRoad")]
        for move in moves:
            label, radius = move["actor"], float(move["render_base_radius_cm"])
            matches = by_label.get(label, [])
            position = _xyz(matches[0].get_actor_location()) if len(matches) == 1 else None
            _check(report, "lamp_base_position:" + label,
                   position is not None and _near(position, move["position_cm"])
                   and abs(radius - 14.56) <= 0.01,
                   actual_cm=position, expected_cm=move["position_cm"], rendered_radius_cm=radius)
            if position is None:
                continue
            side = "East" if position[0] >= 8250.0 else ("North" if position[1] > 0.0 else "South")
            axis = 1 if side == "East" else 0
            relevant = [door for door in doors if door["side"] == side]
            distances = [{"door": door["name"], "distance_cm":
                          abs(position[axis] - float(door["coordinate_cm"]))
                          - float(door["opening_width_cm"]) * 0.5 - radius}
                         for door in relevant]
            minimum = float(move["door_edge_min_distance_cm"])
            _check(report, "lamp_base_clear_of_doorways:" + label,
                   bool(distances) and minimum >= 150.0
                   and all(row["distance_cm"] >= minimum - 0.05 for row in distances),
                   facade_side=side, minimum_required_cm=minimum, door_edge_distances=distances)
            base_rectangle = [position[0] - radius, position[1] - radius,
                              position[0] + radius, position[1] + radius]
            road_hits = [road["actor"] for road in carriageways
                         if _overlap_xy(base_rectangle, [road["world_min"][0], road["world_min"][1],
                                                       road["world_max"][0], road["world_max"][1]])]
            _check(report, "lamp_base_outside_carriageways:" + label, not road_hits,
                   overlapping_roads=road_hits)
            gaps_in_front = []
            for gap in section.get("reopened_gaps", []):
                gap_side = "North" if gap["world_min"][1] > 0.0 else "South"
                if (side == gap_side and position[0] - radius < gap["world_max"][0]
                        and position[0] + radius > gap["world_min"][0]):
                    gaps_in_front.append(gap["name"])
            _check(report, "lamp_base_clear_of_alley_mouths:" + label,
                   not gaps_in_front, blocked_gap_fronts=gaps_in_front)

    _section(report, "door_access_and_lamp_bases", door_access_and_lamp_bases)

    def directional_lighting():
        expected = section.get("directional_lights", [])
        expected_labels = {row["actor"] for row in expected}
        actual_labels = {label for label, components in lights.items()
                         if label.startswith("OTS_Light_StreetLamp") and components}
        _check(report, "eight_directional_street_lights",
               len(expected) == 8 and len(expected_labels) == 8 and actual_labels == expected_labels,
               expected_labels=sorted(expected_labels), actual_labels=sorted(actual_labels))
        for row in expected:
            label = row["actor"]
            components = lights.get(label, [])
            valid = (len(by_label.get(label, [])) == 1 and len(components) == 1
                     and isinstance(components[0], unreal.SpotLightComponent))
            _check(report, "one_spotlight_component:" + label, valid,
                   component_classes=[component.get_class().get_name() for component in components])
            if not valid:
                continue
            component = components[0]
            position, forward = _xyz(component.get_world_location()), _xyz(component.get_forward_vector())
            inner = float(component.get_editor_property("inner_cone_angle"))
            outer = float(component.get_editor_property("outer_cone_angle"))
            intensity = float(component.get_editor_property("intensity"))
            units = component.get_editor_property("intensity_units")
            radius = float(component.get_editor_property("attenuation_radius"))
            shadows = bool(component.get_editor_property("cast_shadows"))
            inverse_squared = bool(component.get_editor_property("use_inverse_squared_falloff"))
            _check(report, "spotlight_points_down:" + label,
                   abs(forward[0]) <= 0.001 and abs(forward[1]) <= 0.001
                   and abs(forward[2] + 1.0) <= 0.001,
                   world_forward=forward)
            _check(report, "spotlight_position:" + label, _near(position, row["position_cm"]),
                   actual_cm=position, expected_cm=row["position_cm"])
            _check(report, "spotlight_cones:" + label,
                   abs(inner - 35.0) <= 0.01 and abs(outer - 55.0) <= 0.01
                   and abs(float(row["inner_cone_angle"]) - 35.0) <= 0.01
                   and abs(float(row["outer_cone_angle"]) - 55.0) <= 0.01,
                   inner_degrees=inner, outer_degrees=outer)
            _check(report, "spotlight_photometry:" + label,
                   units.value == unreal.LightUnits.LUMENS.value
                   and intensity > 0.0 and abs(intensity - float(row["intensity_lm"])) <= 0.01
                   and radius > 0.0 and abs(radius - float(row["attenuation_radius_cm"])) <= TOLERANCE
                   and shadows and inverse_squared,
                   intensity_lm=intensity, intensity_units=str(units), attenuation_radius_cm=radius,
                   cast_shadows=shadows, use_inverse_squared_falloff=inverse_squared)
        user_expected = section.get("user_light_expected")
        _check(report, "user_light_source_expectation_explicit",
               isinstance(user_expected, bool), expected_present=user_expected)
        user = lights.get("PointLight", [])
        valid_user = (len(by_label.get("PointLight", [])) == 1 and len(user) == 1
                      and user[0].get_class().get_name() == "PointLightComponent")
        user_details = {}
        if valid_user:
            component = user[0]
            user_details = {"position_cm": _xyz(component.get_world_location()),
                            "intensity": float(component.get_editor_property("intensity")),
                            "intensity_units": str(component.get_editor_property("intensity_units"))}
            valid_user = (_near(user_details["position_cm"], [6090.0, 1690.0, 1460.0])
                          and abs(user_details["intensity"] - 160.0) <= 0.01
                          and component.get_editor_property("intensity_units").value
                          == unreal.LightUnits.CANDELAS.value)
        if user_expected is True:
            _check(report, "user_point_light_preserved", valid_user, **user_details)
        elif user_expected is False:
            _check(report, "external_user_point_light_deletion_preserved",
                   not by_label.get("PointLight") and not user,
                   actor_present=bool(by_label.get("PointLight")))
            work = (Path(unreal.Paths.project_dir()).resolve()
                    / "Saved/CodexOutputs/StreetAccessLighting_20261005")
            comparison = json.loads((work / "ExternalEditComparison.json").read_text(encoding="utf-8-sig"))
            rebase = json.loads((work / "InputRebaseReport.json").read_text(encoding="utf-8-sig"))
            source_hash = section.get("source_map_sha256")
            external_deletion = (
                bool(source_hash) and comparison.get("persisted_map_unchanged") is True
                and comparison.get("current_sha256") == source_hash
                and not comparison.get("added") and not comparison.get("changed")
                and comparison.get("removed") == ["PointLight"]
                and rebase.get("passed") is True
                and rebase.get("current_sha256") == source_hash
                and rebase.get("previous_sha256") == comparison.get("reference_sha256")
                and rebase.get("preserved_external_deletions") == ["PointLight"])
            phase_removed = None
            baseline_path = work / "PreservationBaseline.json"
            if baseline_path.exists():
                baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
                phase_removed = baseline.get("removed_actor_labels", [])
                external_deletion = (external_deletion
                                     and baseline.get("source_map_sha256") == source_hash
                                     and "PointLight" not in phase_removed
                                     and "PointLight" not in baseline.get("expected_actors", {}))
            _check(report, "user_point_light_deleted_before_this_phase",
                   external_deletion, source_map_sha256=source_hash,
                   external_removed=comparison.get("removed"),
                   phase_removed_actor_labels=phase_removed)

    _section(report, "directional_lighting", directional_lighting)
    report["statistics"].update(
        actor_count=len(actors), reopened_gap_count=len(section.get("reopened_gaps", [])),
        lamp_count=len(section.get("lamp_moves", [])),
        directional_light_count=len(section.get("directional_lights", [])),
        utility_part_count=len(section.get("utility_moves", [])),
        adjusted_terminal_wire_count=len(section.get("wire_adjustments", [])),
        door_approach_count=len(section.get("door_approaches", [])),
        route_sample_count=route_sample_count, check_count=len(report["checks"]),
        failed_check_count=len(report["errors"]))
    report["passed"] = not report["errors"]
    return report
