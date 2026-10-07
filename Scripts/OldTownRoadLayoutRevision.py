"""Pure planning for the revised saved old-town level; no Unreal side effects.

Call plan_road_layout(source_inventory, building_report) with loaded JSON. All
coordinates use UE centimeters. Applying this plan is restricted to TARGET.
"""
import copy
import fnmatch

TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
HUMAN_HEIGHT = 180.0
HUMAN_WIDTH = 50.0
ALLEY_WIDTH = 320.0
STREET_WALK_Z = 11.0
CAMPUS_WALK_Z = 35.0


def _bounds(row):
    mesh = row["meshes"][0]
    center, extent = mesh["world_origin"], mesh["world_extent"]
    return ([center[i] - extent[i] for i in range(3)],
            [center[i] + extent[i] for i in range(3)])


def _building(label):
    return ((label.startswith("BLK_") and label.endswith("_Mass"))
            or label in ("Blockout_School_MainBuilding", "Blockout_School_Building_L", "Blockout_School_Building_R")
            or label.startswith("OTS_SchoolGuardMass_")
            or label.startswith("OTS_PerimeterBackdrop")
            or (label.startswith("OTS_PerimeterBoundary") and "Cap" not in label))


def _slab(name, rect, top, purpose, width=None):
    result = {"name": name, "kind": "slab", "rect_xy": list(rect),
              "world_min": [rect[0], rect[1], top - 20.0],
              "world_max": [rect[2], rect[3], top],
              "surface_z_cm": top, "purpose": purpose}
    if width is not None:
        result["target_clear_width_cm"] = width
    return result


def _route(points, z=STREET_WALK_Z):
    return [list(point[:2]) + [float(point[2]) if len(point) > 2 else z] for point in points]


def _attachment_patterns(label):
    patterns = ["OTS_Enterable_" + label + "_*", "OTS_Blender_" + label + "_*"]
    if label.startswith("OTS_PerimeterBackdrop"):
        stem = label[len("OTS_PerimeterBackdrop"):].rsplit("_", 1)[0]
        patterns += ["OTS_PerimeterWindow" + stem + "_*", "OTS_PerimeterRoof" + stem + "_*",
                     "OTS_PerimeterRoofCap" + stem + "_*"]
    elif label.startswith("OTS_PerimeterBoundary"):
        stem = label[len("OTS_PerimeterBoundary"):]
        patterns += ["OTS_PerimeterBoundaryCap" + stem,
                     "OTS_PerimeterBoundaryWindow" + stem.rsplit("_", 1)[0] + "_*"]
    return patterns


def _transform_inventory(rows, translations):
    """Return translated source rows for converter planning and facade cuts."""
    result = copy.deepcopy(rows)
    for row in result:
        delta = translations.get(row["label"])
        if delta is None:
            continue
        row["location"] = [row["location"][i] + delta[i] for i in range(3)]
        for mesh in row.get("meshes", []):
            if "world_origin" in mesh:
                mesh["world_origin"] = [mesh["world_origin"][i] + delta[i] for i in range(3)]
    return result


def plan_road_layout(source_inventory, building_report=None):
    """Plan public routes and one primary entrance for each of 29 buildings.

    Streets reach the rear houses outdoors. School perimeter houses move clear
    of the school, and a public exterior loop reaches their individual doors.
    No portal crosses another dwelling or an adjoining party wall.
    """
    if isinstance(source_inventory, dict):
        if source_inventory.get("level", TARGET) != TARGET:
            raise ValueError("Source inventory belongs to another level")
        rows = source_inventory["actors"]
    else:
        rows = source_inventory
    by_label = {row["label"]: row for row in rows}
    source_buildings = [row for row in rows if _building(row["label"])]
    if len(source_buildings) != 29:
        raise ValueError("Expected 29 building masses")
    previous = building_report or {}
    if "buildings" in previous and isinstance(previous["buildings"], dict):
        previous = previous["buildings"]
    previous_by_label = {item["label"]: item for item in previous.get("buildings", [])}
    translations = {}
    transforms = []
    boxes = {}
    for row in source_buildings:
        label = row["label"]
        low, high = _bounds(row)
        delta = [0.0, 0.0, 0.0]
        if label.startswith("OTS_PerimeterBackdropNorth"):
            delta[1] = 2100.0 - low[1]
        elif label.startswith("OTS_PerimeterBackdropSouth"):
            delta[1] = -2100.0 - high[1]
        elif label.startswith("OTS_PerimeterBoundarySchoolNorth"):
            delta[1] = 3100.0 - low[1]
        elif label.startswith("OTS_PerimeterBoundarySchoolSouth"):
            delta[1] = -3100.0 - high[1]
        elif label == "OTS_PerimeterBoundaryWest_01":
            delta[0] = -5380.0 - high[0]
        elif label == "OTS_PerimeterBoundaryEast_01":
            delta[0] = 7700.0 - low[0]
        new_low = [low[i] + delta[i] for i in range(3)]
        new_high = [high[i] + delta[i] for i in range(3)]
        boxes[label] = (new_low, new_high)
        patterns = _attachment_patterns(label)
        matches = [item["label"] for item in rows
                   if item["label"] == label or any(fnmatch.fnmatchcase(item["label"], pattern) for pattern in patterns)]
        if any(delta):
            for match in matches:
                if match in translations and translations[match] != delta:
                    raise ValueError("Ambiguous attachment ownership: " + match)
                translations[match] = list(delta)
        transforms.append({"building": label, "translation_cm": delta,
                           "old_world_min": low, "old_world_max": high,
                           "world_min": new_low, "world_max": new_high,
                           "associated_source_actor_labels": matches,
                           "actor_label_patterns": patterns,
                           "generated_building_tag": "OTS_Building_" + label,
                           "apply_once_to": "structure, lights, furniture, source windows, roof caps and facade attachments"})

    surfaces = [
        _slab("BaseGround", [-6800.0, -4300.0, 9300.0, 4300.0], -1.0, "continuous fallback support"),
        _slab("MainRoad", [-600.0, -350.0, 7700.0, 350.0], 1.0, "main vehicle road", 700.0),
        _slab("WestCrossRoad", [-600.0, -2700.0, 100.0, 2700.0], 1.0, "west T junction terminating before perimeter houses", 700.0),
        _slab("EastCrossRoad", [7100.0, -3900.0, 7700.0, 3900.0], 1.0, "east T junction outside rear-house bounds", 600.0),
        _slab("MainWalkNorth", [100.0, 350.0, 7700.0, 530.0], STREET_WALK_Z, "flush shop entrances", 180.0),
        _slab("MainWalkSouth", [100.0, -530.0, 7700.0, -350.0], STREET_WALK_Z, "flush shop entrances", 180.0),
        _slab("SchoolFrontPromenade", [-935.0, -2700.0, -600.0, 2700.0], STREET_WALK_Z,
              "continuous public sidewalk along the existing school wall", 335.0),
        _slab("RearLaneNorth", [280.0, 1755.0, 6940.0, 2075.0], STREET_WALK_Z, "independent rear-house entrances", ALLEY_WIDTH),
        _slab("RearLaneSouth", [280.0, -2075.0, 6940.0, -1755.0], STREET_WALK_Z, "independent rear-house entrances", ALLEY_WIDTH),
        _slab("SchoolCourtyard", [-5350.0, -3060.0, -965.0, 3060.0], CAMPUS_WALK_Z, "continuous campus surface flush with school floors"),
        _slab("SchoolOuterWalkNorth", [-5250.0, 2700.0, 100.0, 3020.0], CAMPUS_WALK_Z, "outdoor approach to each northern perimeter house", ALLEY_WIDTH),
        _slab("SchoolOuterWalkSouth", [-5250.0, -3020.0, 100.0, -2700.0], CAMPUS_WALK_Z, "outdoor approach to each southern perimeter house", ALLEY_WIDTH),
        _slab("SchoolOuterWalkWest", [-5250.0, -3020.0, -4930.0, 3020.0], CAMPUS_WALK_Z, "reach western perimeter house around school", ALLEY_WIDTH),
        _slab("SchoolInnerWalk", [-1770.0, -1300.0, -1450.0, 1300.0], CAMPUS_WALK_Z, "center route clear of gate leaves and guard walls", ALLEY_WIDTH),
        _slab("SchoolInnerWalkNorth", [-1650.0, 960.0, -1330.0, 3020.0], CAMPUS_WALK_Z, "bent north route outside school wing", ALLEY_WIDTH),
        _slab("SchoolInnerWalkSouth", [-1650.0, -3020.0, -1330.0, -960.0], CAMPUS_WALK_Z, "bent south route outside school wing", ALLEY_WIDTH),
        _slab("EastBoundaryWalk", [7380.0, -3500.0, 7700.0, 3500.0], STREET_WALK_Z, "approach east house from road", ALLEY_WIDTH),
    ]
    for sign, side in ((1.0, "North"), (-1.0, "South")):
        ymin, ymax = sorted((sign * 350.0, sign * 2075.0))
        for x, name in ((440.0, "West"), (2570.0, "Central"), (6250.0, "East")):
            surfaces.append(_slab(name + "Connector" + side, [x - 160.0, ymin, x + 160.0, ymax],
                                  STREET_WALK_Z, "outdoor main-street to rear-lane connection", ALLEY_WIDTH))
    surfaces.append({"name": "SchoolGateRamp", "kind": "ramp", "rect_xy": [-1050.0, -360.0, -570.0, 360.0],
                     "axis": 0, "low_end_coordinate": -570.0, "high_end_coordinate": -1050.0,
                     "low_surface_z_cm": STREET_WALK_Z, "high_surface_z_cm": CAMPUS_WALK_Z,
                     "run_cm": 480.0, "rise_cm": 24.0, "grade": 0.05,
                     "purpose": "broad gate approach with no isolated raised doorway block"})
    # Short paved aprons continue the full lane surface to each facade. These
    # have the same elevation as the whole street, not raised door thresholds.
    entrances = []
    for row in source_buildings:
        label = row["label"]
        low, high = boxes[label]
        center = [(low[i] + high[i]) * 0.5 for i in range(3)]
        wall, coordinate, floor_z = "Front", 0.0, STREET_WALK_Z
        if label.startswith("BLK_"):
            sign = 1.0 if center[1] > 0 else -1.0
            old = previous_by_label.get(label)
            x = old["primary_entry_route"][-1][0] if old else center[0]
            coordinate = x - center[0]
            facade = low[1] if sign > 0 else high[1]
            route = _route([[x, 0.0, 1.0], [x, sign * 440.0], [x, facade + sign * 125.0]])
            network = "MainWalkNorth" if sign > 0 else "MainWalkSouth"
        elif label.startswith("OTS_PerimeterBackdrop"):
            sign = 1.0 if center[1] > 0 else -1.0
            x, facade = center[0], low[1] if sign > 0 else high[1]
            route = _route([[1000.0, 0.0, 1.0], [440.0, 0.0, 1.0], [440.0, sign * 1915.0],
                            [x, sign * 1915.0], [x, facade + sign * 125.0]])
            network = "RearLaneNorth" if sign > 0 else "RearLaneSouth"
            ymin, ymax = sorted((sign * 1915.0, facade))
            surfaces.append(_slab("EntryApron_" + label, [x - 160.0, ymin, x + 160.0, ymax],
                                  floor_z, "flush extension of full rear lane", ALLEY_WIDTH))
        elif label.startswith("OTS_PerimeterBoundarySchool"):
            floor_z = CAMPUS_WALK_Z
            sign = 1.0 if center[1] > 0 else -1.0
            x, facade = center[0], low[1] if sign > 0 else high[1]
            route = _route([[-1500.0, 0.0], [-1500.0, sign * 2860.0], [x, sign * 2860.0],
                            [x, facade + sign * 125.0]], floor_z)
            network = "SchoolOuterWalkNorth" if sign > 0 else "SchoolOuterWalkSouth"
            ymin, ymax = sorted((sign * 2860.0, facade))
            surfaces.append(_slab("EntryApron_" + label, [x - 160.0, ymin, x + 160.0, ymax],
                                  floor_z, "flush extension of complete campus walk", ALLEY_WIDTH))
        elif label.startswith("OTS_SchoolGuardMass"):
            floor_z = CAMPUS_WALK_Z
            wall = "Left"  # Its u axis is world Y; enter the south wall.
            coordinate = (center[0] - high[0]) * -1.0
            route = _route([[-1500.0, 0.0], [-1500.0, 500.0], [center[0], 500.0],
                            [center[0], low[1] + 125.0]], floor_z)
            network = "SchoolCourtyard"
        elif label == "OTS_PerimeterBoundaryWest_01":
            floor_z = CAMPUS_WALK_Z
            route = _route([[-1500.0, 0.0], [-1500.0, 2860.0], [-5090.0, 2860.0],
                            [-5090.0, 0.0], [high[0] - 125.0, 0.0]], floor_z)
            network = "SchoolOuterWalkWest"
            surfaces.append(_slab("EntryApron_" + label, [high[0], -160.0, -5090.0, 160.0],
                                  floor_z, "flush connection to western house", ALLEY_WIDTH))
        elif label == "OTS_PerimeterBoundaryEast_01":
            coordinate = 158.0
            route = _route([[1000.0, 0.0, 1.0], [7540.0, 0.0], [7540.0, 158.0], [low[0] + 125.0, 158.0]])
            network = "EastBoundaryWalk"
        else:
            floor_z = CAMPUS_WALK_Z
            y = center[1]
            route = _route([[-1500.0, 0.0], [-1500.0, y], [high[0] - 125.0, y]], floor_z)
            network = "SchoolCourtyard"
        entrances.append({"building": label, "door_wall": wall, "door_coordinate_cm": coordinate,
                          "door_count": 1, "floor_z_override_cm": floor_z,
                          "approach_network": network, "outdoor_route": route,
                          "rule": "exactly one primary portal; no rear, side-link or adjoining-house portal"})

    replace_ground = ("Blockout_MainRoad", "Blockout_TJunctionRoad", "Blockout_SchoolFront_Apron",
                      "Blockout_MainSidewalk_L", "Blockout_MainSidewalk_R", "Blockout_BranchSidewalk_Left",
                      "Blockout_BranchSidewalk_Right", "Blockout_SchoolGround", "BLK_Alley_L_Floor",
                      "BLK_Alley_R_Floor", "OTS_PerimeterGround_01", "OTS_SchoolPath_01",
                      "OTS_SchoolPathEdgeSouth_01", "OTS_SchoolPathEdgeNorth_01",
                      "OTS_SchoolStepLow_01", "OTS_SchoolStepHigh_01")
    remove_patterns = ["OTS_StreetEndTJunctionRoad*", "OTS_StreetEndTJunctionSidewalk*",
                       "OTS_StreetEndTJunctionDrainChannel*", "OTS_AlleyPartyWall*",
                       "OTS_AlleyEndWall*", "OTS_SouthAlleyEndWall*", "BLK_Alley_*_EndWall",
                       "OTS_StreetEndFocalFacade*", "OTS_StreetEndBaseWearEast*",
                       "OTS_P3Prop_StaticShutterStreetEnd*", "OTS_P5Prop_OldServiceDoorTransom*"]
    remove_labels = sorted({label for label in by_label if label in replace_ground
                            or label in ("Blockout_LeftRoadBarrier", "Blockout_RightRoadBarrier")
                            or any(fnmatch.fnmatchcase(label, pattern) for pattern in remove_patterns)})
    party_walls = []
    for sign, side in ((1.0, "North"), (-1.0, "South")):
        ymin, ymax = sorted((sign * 530.0, sign * 1755.0))
        for xmin, xmax, name in ((2350.0, 2410.0, "West"), (2730.0, 2790.0, "East")):
            party_walls.append({"name": "AlleyPartyWall" + side + name,
                                "world_min": [xmin, ymin, STREET_WALK_Z],
                                "world_max": [xmax, ymax, 900.0], "wall_thickness_cm": 60.0})
    # Wall fixtures remain beside dedicated walking strips. Paved width and
    # unobstructed walking width are separate and both are audited explicitly.
    for surface in surfaces:
        rect = list(surface["rect_xy"])
        if surface['name'] == 'MainWalkNorth':
            rect[3] = 470.0
            surface['target_clear_width_cm'] = 120.0
        elif surface['name'] == 'MainWalkSouth':
            rect[1] = -470.0
            surface['target_clear_width_cm'] = 120.0
        elif surface['name'] == 'SchoolFrontPromenade':
            rect[0] = -845.0
            surface['target_clear_width_cm'] = 245.0
        elif surface['name'].startswith('CentralConnector'):
            rect[0],rect[2] = 2430.0,2710.0
            surface['target_clear_width_cm'] = 280.0
        surface['clear_rect_xy'] = rect
    return {"target_level": TARGET, "units": "centimeters", "pure_plan": True,
            "human_reference": {"height_cm": HUMAN_HEIGHT, "width_cm": HUMAN_WIDTH,
                                "capsule_radius_cm": 34.0, "capsule_half_height_cm": HUMAN_HEIGHT * 0.5,
                                "capsule_note": "Actual BP_Character radius; visual shoulder width remains 50cm"},
            "layout": {"main_road_width_cm": 700.0, "main_sidewalk_width_cm": 180.0,
                       "central_alley_clear_width_cm": ALLEY_WIDTH, "rear_lane_clear_width_cm": ALLEY_WIDTH,
                       "rear_house_front_y_cm": 2100.0, "school_boundary_front_y_cm": 3100.0,
                       "school_west_house_front_x_cm": -5380.0, "east_house_front_x_cm": 7700.0,
                       "central_alley_reserved_clear_width_cm": 280.0,
                       "main_sidewalk_reserved_clear_width_cm": 120.0,
                       "world_ground_rect": [-6800.0, -4300.0, 9300.0, 4300.0]},
            "building_transforms": transforms, "actor_translations": translations,
            "translated_inventory": {"level": TARGET, "actors": _transform_inventory(rows, translations)},
            "ground_surfaces": surfaces, "building_entrances": entrances,
            "remove_source_actor_labels": remove_labels,
            "remove_generated_actor_label_patterns": ["OTS_Enterable_*_DoorThreshold_*"],
            "replacement_party_walls": party_walls,
            "alley_attachment_actions": [
                {"label_patterns": ["OTS_AlleyPipe*", "OTS_P2Prop_AlleyMeterBox_01"], "translation_cm": [60.0, 0.0, 0.0]},
                {"label_patterns": ["OTS_SouthAlleyPipe*"], "translation_cm": [50.0, 0.0, 0.0]},
                {"label_patterns": ["OTS_P2NorthAlleyDrain_01", "OTS_P2SouthAlleyDrain_01"], "target_x_cm": 2425.0},
                {"label_patterns": ["OTS_P3Prop_AlleyCrossbar*"], "width_axis": "world_x", "target_span_cm": 320.0,
                 "preserve_center_x_cm": 2570.0, "rule": "extend original assembly span only; preserve 300cm+ overhead clearance"},
                {"actor_label": "OTS_P2Prop_AlleyBench_01", "target_location_cm": [2200.0, -1660.0, 11.0],
                 "target_yaw_degrees": 0.0, "target_seat_footprint_cm": [150.0, 45.0],
                 "rule": "move bench into rear court, outside the 320cm circulation strip"}],
            "application_rules": [
                "Assert the loaded world is TARGET before touching actor copies; never write L_Main or original Blockout maps.",
                "Apply each building translation to all existing generated and associated source actors, or rebuild from translated_inventory; never do both.",
                "Replace converter portals with building_entrances before emitting walls; do not call adjoining-building portal planning.",
                "Keep source immutable on disk; use translated_inventory as the in-memory geometry basis for facade cuts and conversion.",
                "Raise the guard floor to 35cm with the campus surface; remove all isolated generated threshold blocks.",
                "Ground surfaces intentionally overlap at matching heights; their public paths never require walking through another building.",
                "Remove the old alley end walls completely; central alleys join full rear lanes instead of terminating at 140cm door holes.",
                "Preserve BP_OTS_MainHomeInteractive structure and interactions; its existing storefront remains on the main sidewalk.",
                "Update building/furniture reports and review cameras from transformed bounds after application; validate saved collision at 180x50cm."]}
