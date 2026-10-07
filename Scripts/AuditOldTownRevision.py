"""Read-only checks of a loaded revised street, suitable for a UE commandlet.

audit_revision(world, actors, build_report, revision_plan) returns JSON data.
It neither changes actors/assets nor saves the map. Missing expectations fail
explicitly. Bounds checks are conservative; they do not certify triangle-level
contacts, navigation, lighting, or a runtime player walkthrough.
"""
from collections import defaultdict
import itertools
import json
import math
from pathlib import Path
import traceback

import unreal

TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
OUTPUT_RELATIVE = "Saved/CodexOutputs/EnterableStreet_20261002/RevisionAudit.json"
TOLERANCE = 0.5


def _xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def _box(origin, extent):
    return [[float(origin[i] - extent[i]) for i in range(3)],
            [float(origin[i] + extent[i]) for i in range(3)]]


def _union(boxes):
    return [[min(box[0][i] for box in boxes) for i in range(3)],
            [max(box[1][i] for box in boxes) for i in range(3)]]


def _dimensions(box):
    return [box[1][i] - box[0][i] for i in range(3)]


def _overlap(a, b):
    return [min(a[1][i], b[1][i]) - max(a[0][i], b[0][i]) for i in range(3)]


def _street_lamp_collision_boxes(component):
    """Read shaft collision boxes; fall back to render bounds if unsupported.

    The lamp's head and arm are above standing height, while its authored
    simple box follows the shaft. Transform each box's eight corners through
    its own center/rotation and then the real component world transform.
    This only refines the conservative bounds check; physics probes still
    inspect the unchanged component and its Pawn collision response.
    """
    result = {"used_collision_boxes": False, "world_bounds_cm": [],
              "local_boxes": [], "fallback_reason": None}
    try:
        mesh = component.get_editor_property("static_mesh")
        body = mesh.get_editor_property("body_setup")
        if body is None:
            raise ValueError("No readable body_setup")
        trace_flag = str(body.get_editor_property("collision_trace_flag"))
        if "USE_COMPLEX_AS_SIMPLE" in trace_flag.upper():
            raise ValueError("Complex-as-simple collision does not use the box elements")
        geometry = body.get_editor_property("agg_geom")
        boxes = list(geometry.get_editor_property("box_elems"))
        if not boxes:
            raise ValueError("No readable simple collision boxes")
        # Never replace other authored simple shapes with an incomplete set.
        for name in ("sphere_elems", "sphyl_elems", "convex_elems",
                     "tapered_capsule_elems", "level_set_elems", "skinned_level_set_elems"):
            try:
                other_shapes = geometry.get_editor_property(name)
            except Exception:
                continue  # This engine version may not expose newer shape types.
            if len(other_shapes):
                raise ValueError("Additional simple collision shapes: " + name)
        world = component.get_world_transform()
        for index, element in enumerate(boxes):
            center = element.get_editor_property("center")
            rotation = element.get_editor_property("rotation")
            size = [float(element.get_editor_property(axis)) for axis in ("x", "y", "z")]
            if not all(math.isfinite(v) and v > 0.0 for v in size):
                raise ValueError("Invalid simple box dimensions at index " + str(index))
            if not all(math.isfinite(v) for v in _xyz(center) +
                       [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)]):
                raise ValueError("Invalid simple box center/rotation at index " + str(index))
            local = unreal.Transform(location=center, rotation=rotation,
                                     scale=unreal.Vector(1.0, 1.0, 1.0))
            points = [_xyz(world.transform_location(local.transform_location(unreal.Vector(*corner))))
                      for corner in itertools.product(*[(-v * .5, v * .5) for v in size])]
            if not all(math.isfinite(v) for point in points for v in point):
                raise ValueError("Nonfinite transformed simple box at index " + str(index))
            result["world_bounds_cm"].append([[min(point[i] for point in points) for i in range(3)],
                                               [max(point[i] for point in points) for i in range(3)]])
            result["local_boxes"].append({"index": index, "center_cm": _xyz(center), "size_cm": size,
                                          "rotation_degrees": [float(rotation.pitch), float(rotation.yaw),
                                                               float(rotation.roll)]})
        result["used_collision_boxes"] = True
    except Exception as exc:
        result["world_bounds_cm"] = []
        result["local_boxes"] = []
        result["fallback_reason"] = str(exc)
    return result


def _corridor_obstacle_bounds(row):
    collision = row.get("street_lamp_collision", {})
    if collision.get("used_collision_boxes") and collision.get("world_bounds_cm"):
        return collision["world_bounds_cm"], "simple_collision_box"
    return [row["bounds_cm"]], "render_aabb"


def _mesh_box(component):
    mesh = component.get_editor_property("static_mesh")
    local = mesh.get_bounds()
    bounds = _box(_xyz(local.origin), _xyz(local.box_extent))
    transform = component.get_world_transform()
    points = [_xyz(transform.transform_location(unreal.Vector(*point)))
              for point in itertools.product(*zip(*bounds))]
    transformed = [[min(p[i] for p in points) for i in range(3)],
                   [max(p[i] for p in points) for i in range(3)]]
    origin, extent, _ = unreal.SystemLibrary.get_component_bounds(component)
    actual = _box(_xyz(origin), _xyz(extent))
    rotation = component.get_world_rotation()
    return {"asset": mesh.get_path_name().split(".", 1)[0],
            "local_bounds_cm": bounds, "bounds_cm": actual,
            "transformed_mesh_bounds_cm": transformed,
            "bounds_error_cm": max(abs(actual[j][i] - transformed[j][i])
                                   for i in range(3) for j in (0, 1)),
            "component_location_cm": _xyz(component.get_world_location()),
            "world_scale": _xyz(component.get_world_scale()),
            "world_rotation_degrees": [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)],
            "materials": [component.get_material(i).get_path_name()
                          if component.get_material(i) else None
                          for i in range(component.get_num_materials())]}


def _check(report, name, passed, status=None, **details):
    report["checks"].append(dict(details, name=name, passed=bool(passed),
                                 status=status or ("PASS" if passed else "FAIL")))
    if not passed:
        report["errors"].append(name)


def _support(world, point, ignore=(), above=5.0, below=20.0):
    hit = unreal.SystemLibrary.line_trace_single_for_objects(
        world, unreal.Vector(point[0], point[1], point[2] + above),
        unreal.Vector(point[0], point[1], point[2] - below),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
        False, list(ignore), unreal.DrawDebugTrace.NONE)
    return float(hit.to_tuple()[5].z) if hit is not None else None


def _capsule_components(world, foot, radius, height, lift=0.0):
    components = unreal.SystemLibrary.capsule_overlap_components(
        world, unreal.Vector(foot[0], foot[1], foot[2] + height * .5 + 2.0 + lift),
        radius, height * .5,
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
        unreal.PrimitiveComponent, []) or []
    return [c for c in components
            if c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN).value
            == unreal.CollisionResponseType.ECR_BLOCK.value]


def _component_label(component):
    return component.get_owner().get_actor_label() + ":" + component.get_name()


def _capsule_blockers(world, foot, radius, height):
    """Strict standing check for doorway apertures and indoor entries."""
    return sorted({_component_label(c) for c in _capsule_components(world, foot, radius, height)})


def _step_probe(world, foot, radius, height):
    """Permit low risers only when their real tops and lifted headroom pass."""
    components = _capsule_components(world, foot, radius, height)
    if not components:
        return {"passed": True, "blockers": [], "stepped_over": []}
    obstacles = []
    for component in components:
        origin, extent, _ = unreal.SystemLibrary.get_component_bounds(component)
        obstacles.append({"component": _component_label(component),
                          "top_z_cm": float(origin.z + extent.z)})
    low_enough = all(row["top_z_cm"] <= foot[2] + 45.0 + .01 for row in obstacles)
    headroom = _capsule_components(world, foot, radius, height, lift=45.0) if low_enough else []
    passed = low_enough and not headroom
    return {"passed": passed,
            "blockers": [] if passed else sorted({_component_label(c) for c in components}),
            "overlapping_components": obstacles,
            "headroom_blockers": sorted({_component_label(c) for c in headroom}),
            "stepped_over": obstacles if passed else [], "step_height_cm": 45.0}


def _route_samples(route, step=25.0):
    for first, second in zip(route, route[1:]):
        count = max(1, math.ceil(math.dist(first, second) / step))
        for index in range(count + 1):
            yield [first[i] + (second[i] - first[i]) * index / count for i in range(3)]


def _section(report, name, callback):
    try:
        callback()
    except Exception:
        _check(report, name + ":exception", False, traceback=traceback.format_exc())


def audit_revision(world, actors, build_report, revision_plan):
    """Inspect real components using explicit plan data; return all failures.

    revision_plan accepts the dict from plan_road_layout(), optionally wrapped
    in road_layout. Additional audit_expectations keys are human_actor_labels
    (strings or {actor, width_axis}), furniture_parts (target_parts() rows),
    and stair_side_panels ({actor OR actor_labels, world_min, world_max,
    material_contains}). Side-panel expectations must describe every intended
    tread/landing side volume, rather than repeat whichever panels exist.
    """
    actors = list(actors)
    plan = revision_plan.get("road_layout", revision_plan)
    expectations = revision_plan.get("audit_expectations", plan.get("audit_expectations", {}))
    report = {"passed": False, "target_level": TARGET, "tolerance_cm": TOLERANCE,
              "checks": [], "errors": [], "statistics": {},
              "limitations": [
                  "Door counts use reported portal metadata plus real building components and collision probes; unreported extra wall holes need visual review.",
                  "World AABBs conservatively identify potential interpenetrations; overlap is not a triangle intersection proof.",
                  "Bed frame support uses authored support elevation and actual bounds; a frame AABB includes its headboard and cannot prove slat contact.",
                  "Corridor collision probes sample the plan; actual component AABB intrusion checks cover unsampled visible obstacles conservatively.",
                  "Stair coverage certifies supplied side volumes only; missing expected volumes fail instead of assuming full enclosure."]}
    if world is None or not world.get_path_name().startswith(TARGET + "."):
        _check(report, "loaded_target_world", False)
        return report
    _check(report, "plan_target", plan.get("target_level") == TARGET)
    by_label = defaultdict(list)
    mesh_rows = []
    for actor in actors:
        label = actor.get_actor_label()
        by_label[label].append(actor)
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            if not component.get_editor_property("static_mesh"):
                continue
            try:
                row = _mesh_box(component)
                row.update(actor=label, tags=[str(t) for t in actor.get_editor_property("tags")])
                if label in {"OTS_P2Prop_StreetLamp_{:02d}".format(i) for i in range(1, 10)}:
                    row["component"] = component.get_name()
                    row["street_lamp_collision"] = _street_lamp_collision_boxes(component)
                mesh_rows.append(row)
            except Exception:
                _check(report, "component_bounds:" + label, False, traceback=traceback.format_exc())
    duplicate_labels = {label: len(matches) for label, matches in by_label.items() if len(matches) > 1}
    _check(report, "unique_actor_labels", not duplicate_labels, duplicates=duplicate_labels)
    _check(report, "component_bounds_match_mesh_transforms",
           bool(mesh_rows) and all(row["bounds_error_cm"] <= TOLERANCE for row in mesh_rows),
           mismatches=[{"actor": row["actor"], "error_cm": row["bounds_error_cm"]}
                       for row in mesh_rows if row["bounds_error_cm"] > TOLERANCE])
    structure = build_report.get("buildings", {})
    if isinstance(structure, dict):
        structure = structure.get("buildings", [])
    buildings = {item["label"]: item for item in structure}
    human = plan.get("human_reference", {})
    height = float(human.get("height_cm", 180.0))
    width = float(human.get("width_cm", human.get("shoulder_width_cm", 50.0)))
    collision_spec = build_report.get("collision", {})
    capsule_radius = float(collision_spec.get("capsule_radius_cm", 34.0))
    capsule_height = float(collision_spec.get("capsule_height_cm", 180.0))
    human_specs = expectations.get("human_actor_labels") or build_report.get("human_actor_labels") or []
    human_labels = {s if isinstance(s, str) else s["actor"] for s in human_specs}
    report["physical_capsule"] = {"radius_cm": capsule_radius, "height_cm": capsule_height,
                                  "visual_human_width_cm": width, "visual_human_height_cm": height}

    def doors_and_thresholds():
        threshold_labels = sorted({row["actor"] for row in mesh_rows
                                   if "DoorThreshold" in row["actor"] or any("DoorThreshold" in t for t in row["tags"])})
        threshold_labels += [label for label in by_label if "DoorThreshold" in label and label not in threshold_labels]
        _check(report, "zero_door_threshold_actors", not threshold_labels, actors=threshold_labels)
        entrances = plan.get("building_entrances", [])
        _check(report, "complete_entrance_plan", len(entrances) == 29 and len(buildings) == 29,
               planned=len(entrances), reported=len(buildings))
        for entrance in entrances:
            label = entrance["building"]
            building = buildings.get(label, {})
            doors = building.get("doors", [])
            actual_structure = [r for r in mesh_rows if "OTS_Building_" + label in r["tags"]]
            _check(report, "one_primary_portal:" + label,
                   bool(actual_structure) and len(doors) == 1 and doors[0].get("primary") is True
                   and entrance.get("door_count") == 1,
                   portal_count=len(doors), real_building_components=len(actual_structure))
            if len(doors) != 1:
                continue
            door = doors[0]
            route = door.get("route", [])
            failures = [{"foot_cm": foot, "blockers": blockers}
                        for foot in _route_samples(route)
                        if (blockers := _capsule_blockers(world, foot, capsule_radius, capsule_height))]
            _check(report, "primary_entry_clear:" + label, len(route) >= 2 and not failures,
                   failures=failures, capsule_height_cm=capsule_height, capsule_diameter_cm=capsule_radius * 2.0)
            if "opening_min" not in door or "opening_max" not in door:
                _check(report, "door_aperture:" + label, False, status="UNSUPPORTED", reason="No actual portal opening coordinates")
                continue
            low, high = door["opening_min"], door["opening_max"]
            normal = min((0, 1), key=lambda i: high[i] - low[i])
            across = 1 - normal
            foot = [(low[i] + high[i]) * .5 for i in range(3)]
            # Converter cut boxes extend 12cm below the actual floor. That cut
            # margin is not a standing elevation and must not sink our capsule.
            foot[2] = route[-1][2] if route else building["floor_z"][0]
            samples = []
            frame_inset = 4. if build_report.get('opening_components') else 0.
            for fraction in (0.0, .5, 1.0):
                sample = list(foot)
                sample[across] = low[across] + frame_inset + capsule_radius + 3.0 + fraction * (high[across] - low[across] - 2.*frame_inset - capsule_radius * 2.0 - 6.0)
                samples.append({"foot_cm": sample, "blockers": _capsule_blockers(world, sample, capsule_radius, capsule_height)})
            _check(report, "door_aperture:" + label,
                   high[across] - low[across] >= capsule_radius * 2.0 + 6.0 and high[2] - foot[2] >= capsule_height + 4.0
                   and all(not s["blockers"] for s in samples), samples=samples,
                   aperture_dimensions_cm=_dimensions([low, high]),
                   effective_clear_width_cm=high[across]-low[across]-2.*frame_inset)
            outdoor = entrance.get("outdoor_route", [])
            invaded = set()
            outdoor_failures = []
            for foot in _route_samples(outdoor, 50.0):
                support = _support(world, foot, above=45.0, below=45.0)
                if support is None or abs(support - foot[2]) > 45.0:
                    outdoor_failures.append({"planned_foot_cm": foot, "support_z_cm": support, "reason": "No support within a player step"})
                else:
                    probe = _step_probe(world, foot[:2] + [support], capsule_radius, capsule_height)
                    if not probe["passed"]:
                        outdoor_failures.append(dict(probe, foot_cm=foot[:2] + [support]))
                for other, record in buildings.items():
                    if other == label:
                        continue
                    a, b = record["world_min"], record["world_max"]
                    if all(a[i] + 2.0 < foot[i] < b[i] - 2.0 for i in (0, 1)):
                        invaded.add(other)
            _check(report, "outdoor_route_avoids_other_house_bounds:" + label,
                   len(outdoor) >= 2 and not invaded, intersected_building_bounds=sorted(invaded),
                   scope="Reported building envelopes; collision connectivity is checked separately")
            _check(report, "outdoor_route_collision:" + label, len(outdoor) >= 2 and not outdoor_failures,
                   failures=outdoor_failures, capsule_radius_cm=capsule_radius, capsule_height_cm=capsule_height,
                   scope="50cm route samples snapped to real collision support within 45cm of planned foot elevation")

    def human_reference():
        specs = expectations.get("human_actor_labels") or build_report.get("human_actor_labels")
        if not specs:
            _check(report, "human_reference_expectations", False, status="UNSUPPORTED", reason="human_actor_labels missing")
            return
        for spec in specs:
            spec = {"actor": spec} if isinstance(spec, str) else spec
            label = spec["actor"]
            rows = [r for r in mesh_rows if r["actor"] == label]
            if not rows or len(by_label[label]) != 1:
                _check(report, "human:" + label, False, reason="Missing or duplicated mesh actor")
                continue
            box = _union([r["bounds_cm"] for r in rows])
            size = _dimensions(box)
            actual_width = size[spec["width_axis"]] if "width_axis" in spec else max(size[:2])
            point = [(box[0][i] + box[1][i]) * .5 for i in (0, 1)] + [box[0][2]]
            support_z = _support(world, point, by_label[label])
            _check(report, "human:" + label,
                   abs(size[2] - height) <= TOLERANCE and abs(actual_width - width) <= TOLERANCE
                   and support_z is not None and abs(box[0][2] - support_z) <= TOLERANCE,
                   actual_aabb_cm=box, actual_dimensions_cm=size, expected_height_cm=height,
                   expected_width_cm=width, measured_width_cm=actual_width, ground_z_cm=support_z)

    def furniture():
        parts = expectations.get("furniture_parts")
        if not parts:
            from OldTownHumanScalePlan import target_parts
            parts = target_parts()
        targets = {item["name"]: item for item in parts}
        axis_path = Path(build_report.get("furniture_manifest", Path(unreal.Paths.project_dir()) / "SourceArt/OldTownModular_20261002/ImportManifest.json")).parent / "UnrealAxisVerification.json"
        if not axis_path.exists():
            _check(report, "furniture_axes", False, status="UNSUPPORTED", reason="UnrealAxisVerification.json missing")
            return
        axes = json.loads(axis_path.read_text(encoding="utf-8"))
        order, signs = axes["order"], axes["signs"]
        _check(report, "furniture_axes", sorted(order) == [0, 1, 2] and len(signs) == 3)
        groups = defaultdict(list)
        placements = build_report.get("furniture_placements", [])
        seen = set()
        for placement in placements:
            label = placement["actor"]
            rows = [r for r in mesh_rows if r["actor"] == label]
            name = placement["asset"].split(".", 1)[0].rsplit("/", 1)[-1]
            target = targets.get(name)
            if len(rows) != 1 or target is None or len(by_label[label]) != 1:
                _check(report, "furniture:" + label, False, reason="Missing/duplicate actor or target part")
                continue
            row = rows[0]
            seen.add(name)
            expected_size = [target["target_dimensions_cm"][order[i]] for i in range(3)]
            actual_size = _dimensions(row["local_bounds_cm"])
            location = _xyz(by_label[label][0].get_actor_location())
            offset = [signs[i] * target["target_offset_cm"][order[i]] for i in range(3)]
            yaw = math.radians(placement.get("yaw_degrees",0.0))
            offset = [offset[0]*math.cos(yaw)-offset[1]*math.sin(yaw),
                      offset[0]*math.sin(yaw)+offset[1]*math.cos(yaw),offset[2]]
            actual_yaw = row["world_rotation_degrees"][1]
            recorded_yaw = float(placement.get("yaw_degrees", 0.0))
            yaw_error = (actual_yaw - recorded_yaw + 180.0) % 360.0 - 180.0
            component = by_label[label][0].get_component_by_class(unreal.StaticMeshComponent)
            no_collision = component.get_collision_enabled().value == unreal.CollisionEnabled.NO_COLLISION.value
            materials_present = bool(row["materials"]) and all(row["materials"])
            _check(report, "furniture:" + label,
                   row["asset"].rsplit("/", 1)[-1] == name
                   and all(abs(actual_size[i] - expected_size[i]) <= TOLERANCE for i in range(3))
                   and all(abs(s - 1.0) <= .001 for s in row["world_scale"])
                   and all(abs(location[i] - placement["location_cm"][i]) <= TOLERANCE for i in range(3))
                   and abs(yaw_error) <= .01 and no_collision and materials_present,
                   actual_dimensions_cm=actual_size, target_dimensions_cm=expected_size,
                   actual_actor_location_cm=location, recorded_location_cm=placement["location_cm"],
                   actual_yaw_degrees=actual_yaw, recorded_yaw_degrees=recorded_yaw,
                   yaw_error_degrees=yaw_error, no_collision=no_collision,
                   material_paths=row["materials"], materials_present=materials_present)
            groups[(placement["building"], placement["floor"], placement["group"])].append(
                dict(row, name=name, base_cm=[location[i] - offset[i] for i in range(3)], offset_cm=offset))
        _check(report, "eight_rescaled_furniture_parts_present", bool(placements) and seen == set(targets), seen=sorted(seen), target=sorted(targets))
        group_boxes = []
        for key, members in groups.items():
            label = ":".join(map(str, key))
            box = _union([m["bounds_cm"] for m in members])
            bases = [m["base_cm"] for m in members]
            error = max(max(base[i] for base in bases) - min(base[i] for base in bases) for i in range(3))
            _check(report, "assembly_offsets:" + label, error <= TOLERANCE, common_origin_error_cm=error,
                   parts=[{"name": m["name"], "assembly_origin_cm": m["base_cm"], "offset_cm": m["offset_cm"]} for m in members],
                   scope="Hinge pivots use authored offsets; elevated wardrobe door bottoms are not treated as floor pivots")
            expected_z = buildings[key[0]]["floor_z"][key[1] - 1]
            point = [(box[0][i] + box[1][i]) * .5 for i in (0, 1)] + [box[0][2]]
            floor = _support(world, point, [a for m in members for a in by_label[m["actor"]]])
            _check(report, "furniture_floor_contact:" + label,
                   abs(box[0][2] - expected_z) <= TOLERANCE and floor is not None
                   and abs(floor - box[0][2]) <= TOLERANCE,
                   actual_group_bottom_cm=box[0][2], reported_floor_z_cm=expected_z, actual_support_z_cm=floor)
            by_name = {m["name"]: m for m in members}
            if key[2] == "Bed":
                mattress = by_name.get("SM_OTS_Blender_BedMattress")
                pillow = by_name.get("SM_OTS_Blender_BedPillow")
                frame = by_name.get("SM_OTS_Blender_BedFrame")
                if not all((mattress, pillow, frame)):
                    _check(report, "bed_support_bounds:" + label, False, reason="Bed part missing")
                else:
                    mb, pb, fb = mattress["bounds_cm"], pillow["bounds_cm"], frame["bounds_cm"]
                    gap = pb[0][2] - mb[1][2]
                    contained = all(pb[0][i] >= mb[0][i] - TOLERANCE and pb[1][i] <= mb[1][i] + TOLERANCE for i in (0, 1))
                    mattress_inside = all(mb[0][i] >= fb[0][i] - TOLERANCE and mb[1][i] <= fb[1][i] + TOLERANCE for i in (0, 1))
                    _check(report, "bed_support_bounds:" + label, abs(gap) <= TOLERANCE and contained and mattress_inside
                           and abs(mb[0][2] - mattress["base_cm"][2] - mattress["offset_cm"][2]
                                   - mattress["local_bounds_cm"][0][2]) <= TOLERANCE,
                           pillow_mattress_gap_cm=gap, pillow_within_mattress_xy=contained,
                           mattress_within_frame_xy=mattress_inside, slat_triangle_contact_verified=False)
            group_boxes.append((label, box))
        overlaps = [{"groups": [a[0], b[0]], "aabb_overlap_cm": _overlap(a[1], b[1])}
                    for a, b in itertools.combinations(group_boxes, 2)
                    if all(v > TOLERANCE for v in _overlap(a[1], b[1]))]
        _check(report, "furniture_group_bounds_separated", not overlaps, potential_interpenetrations=overlaps)

    def corridors():
        surfaces = [s for s in plan.get("ground_surfaces", []) if "target_clear_width_cm" in s and s.get("kind") == "slab"]
        # Party walls share the roads' tag. Only exact planned walking surfaces
        # (including the ramp) are excluded from conservative obstacle bounds.
        ground_labels = {s.get("actor", "OTS_RoadRevision_" + s["name"])
                         for s in plan.get("ground_surfaces", [])}
        _check(report, "corridor_expectations", bool(surfaces))
        for surface in surfaces:
            name, rect = surface["name"], surface.get("clear_rect_xy",surface["rect_xy"])
            target = float(surface["target_clear_width_cm"])
            span = [rect[i + 2] - rect[i] for i in (0, 1)]
            across = int(surface.get("width_axis", min((0, 1), key=lambda i: abs(span[i] - target))))
            along = 1 - across
            z = float(surface["surface_z_cm"])
            surface_actor = surface.get("actor", "OTS_RoadRevision_" + name)
            actual_surfaces = [r for r in mesh_rows if r["actor"] == surface_actor]
            expected_surface = [surface["world_min"], surface["world_max"]]
            surface_match = len(actual_surfaces) == 1 and all(
                abs(actual_surfaces[0]["bounds_cm"][j][i] - expected_surface[j][i]) <= TOLERANCE
                for j in (0, 1) for i in range(3))
            _check(report, "road_surface_bounds:" + name, surface_match,
                   actor=surface_actor, expected_bounds_cm=expected_surface,
                   actual_bounds_cm=[r["bounds_cm"] for r in actual_surfaces])
            corridor_box = [[rect[0] + .5, rect[1] + .5, z + 3.0], [rect[2] - .5, rect[3] - .5, z + height]]
            intrusions = []
            collision_box_diagnostics = []
            for row in mesh_rows:
                if row["actor"] in human_labels or row["actor"] in ground_labels:
                    continue
                bounds, source = _corridor_obstacle_bounds(row)
                if "street_lamp_collision" in row:
                    collision_box_diagnostics.append(dict(row["street_lamp_collision"],
                                                           actor=row["actor"], component=row["component"],
                                                           bounds_source=source))
                for index, box in enumerate(bounds):
                    overlap = _overlap(corridor_box, box)
                    if all(value > TOLERANCE for value in overlap):
                        intrusions.append({"actor": row["actor"], "aabb_overlap_cm": overlap,
                                           "bounds_source": source, "bounds_index": index,
                                           "obstacle_bounds_cm": box})
            failures = []
            supports = []
            count = max(1, math.ceil(span[along] / 100.0))
            for index in range(count + 1):
                foot = [(rect[i] + rect[i + 2]) * .5 for i in (0, 1)] + [z]
                foot[along] = rect[along] + min(span[along] * .5, capsule_radius + 3.0) + index / count * max(0.0, span[along] - capsule_radius * 2.0 - 6.0)
                for fraction in (0.0, .25, .5, .75, 1.0):
                    sample = list(foot)
                    sample[across] = rect[across] + capsule_radius + 3.0 + fraction * max(0.0, span[across] - capsule_radius * 2.0 - 6.0)
                    sample_support = _support(world, sample, above=45., below=45.)
                    if sample_support is None or abs(sample_support-z) > 45.0 + .01:
                        supports.append({"planned_foot_cm": sample, "actual_support_z_cm": sample_support,
                                         "reason": "No collision support within configured step height"})
                        continue
                    sample[2] = sample_support
                    probe = _step_probe(world, sample, capsule_radius, capsule_height)
                    if not probe["passed"]:
                        failures.append(dict(probe, foot_cm=sample))
            _check(report, "corridor_clear_width:" + name, span[across] >= target - TOLERANCE
                   and not intrusions and not failures and not supports,
                   planned_width_cm=span[across], required_width_cm=target, width_axis=across,
                   actual_mesh_aabb_intrusions=intrusions, collision_failures=failures, missing_support=supports,
                   used_collision_boxes=collision_box_diagnostics,
                   ignored_ground_surface_labels=sorted(ground_labels),
                   scope="Reserved-width bounds (readable simple boxes for street lamps, otherwise render AABBs) and unchanged real-support capsule probes; low risers require clear lifted headroom")

    def stair_sides():
        panels = expectations.get("stair_side_panels")
        if not panels:
            _check(report, "stair_side_expectations", False, status="UNSUPPORTED", reason="Expected side panel coverage boxes missing")
            return
        for index, panel in enumerate(panels):
            labels = panel.get("actor_labels", [panel.get("actor")])
            rows = [r for r in mesh_rows if r["actor"] in labels]
            expected = [panel["world_min"], panel["world_max"]]
            material = panel.get("material_contains", "OldGreen")
            matching = [r for r in rows if any(material.lower() in (m or "").lower() for m in r["materials"])]
            # Each expected box is one complete rectangular side segment. This
            # intentionally cannot pass when only a subset of that box is filled.
            covering = [r for r in matching
                        if abs(r["world_rotation_degrees"][0]) <= .001 and abs(r["world_rotation_degrees"][2]) <= .001
                        and abs(r["world_rotation_degrees"][1] / 90.0 - round(r["world_rotation_degrees"][1] / 90.0)) <= .001
                        and all(r["bounds_cm"][0][i] <= expected[0][i] + TOLERANCE
                         and r["bounds_cm"][1][i] >= expected[1][i] - TOLERANCE for i in range(3))]
            _check(report, "green_stair_side:" + str(index), bool(covering), expected_box_cm=expected,
                   candidate_actors=labels, green_material_actors=[r["actor"] for r in matching],
                   covering_actors=[r["actor"] for r in covering],
                   scope="Conservative component AABB coverage of supplied rectangular side segment")

    for name, callback in (("doors", doors_and_thresholds), ("human", human_reference),
                           ("furniture", furniture), ("corridors", corridors), ("stair_sides", stair_sides)):
        _section(report, name, callback)
    report["statistics"] = {"actors": len(actors), "mesh_components": len(mesh_rows),
                            "buildings": len(buildings), "checks": len(report["checks"]),
                            "failed_checks": len(report["errors"])}
    report["passed"] = not report["errors"]
    return report


def main():
    project = Path(unreal.Paths.project_dir()).resolve()
    output = project / OUTPUT_RELATIVE
    result = {"passed": False, "errors": ["commandlet_exception"], "checks": []}
    try:
        import sys
        sys.path.insert(0, str(project / "Scripts"))
        build = json.loads((output.parent / "BuildReport.json").read_text(encoding="utf-8"))
        plan_file = output.parent / "RevisionPlan.json"
        if not plan_file.exists():
            raise RuntimeError("RevisionPlan.json missing; a saved explicit plan is required")
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(TARGET):
            raise RuntimeError("Saved target map failed to load")
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        from ValidateEnterableStreet import refresh_world_collision
        refresh_world_collision(list(actors))
        result = audit_revision(world, actors, build, plan)
    except Exception:
        result["traceback"] = traceback.format_exc()
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not result["passed"]:
        unreal.log_error("OTS_REVISION_AUDIT_FAILED " + ", ".join(result["errors"]))
        raise RuntimeError("Revision audit failed; see RevisionAudit.json")
    unreal.log("OTS_REVISION_AUDIT_SUCCESS " + json.dumps(result["statistics"]))
    return result


if __name__ == "__main__":
    main()
