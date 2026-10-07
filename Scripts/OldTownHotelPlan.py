"""Pure centimetre layout for the saved East building and street corners.

No Unreal imports or file writes. ``build_hotel_plan`` accepts the current
building report row, or the converter's Building instance. Movable door leaf
specifications are separate from every fixed wall and frame specification.
"""
import math

EAST_BUILDING = "OTS_PerimeterBoundaryEast_01"
PLAYER_RADIUS_CM = 34.0
PLAYER_HEIGHT_CM = 180.0
WALL_CM = 12.0
ROOM_DOOR_WIDTH_CM = 90.0
ROOM_DOOR_HEIGHT_CM = 200.0


def _as_report(building):
    if isinstance(building, dict):
        return building
    low, high = list(building.low), list(building.high)
    return {
        "label": building.label, "world_min": low, "world_max": high,
        "interior_min": [low[0] + 20., low[1] + 20., building.ground],
        "interior_max": [high[0] - 20., high[1] - 20., high[2] - 20.],
        "floor_z": list(building.floors),
        "door_width_cm": building.door_width,
        "primary_entry_route": building.door_route(building.portals[0]),
        "ground_route": [building.world(158., 125., building.ground),
                         building.world(158., 350., building.ground),
                         building.world(building.core_u - 80., 350., building.ground),
                         building.world(building.core_u - 80., building.core_v - 65., building.ground)],
        "stair_keepout": {
            "min": building.world(building.core_u - 200., building.core_v - 140., building.ground),
            "max": building.world(building.core_u + 200., building.depth - 25., high[2])},
    }


def _box(name, role, low, high, material, category, floor=None,
         room_id=None, collision=True):
    if not all(float(high[i]) > float(low[i]) for i in range(3)):
        raise ValueError("Degenerate hotel box: " + name)
    result = {"name": name, "role": role,
              "world_min": [float(v) for v in low],
              "world_max": [float(v) for v in high],
              "material": material, "category": category,
              "collision": collision}
    if floor is not None:
        result["floor"] = floor
    if room_id is not None:
        result["room_id"] = room_id
    return result


def _overlap(a_low, a_high, b_low, b_high, epsilon=.01):
    return all(min(a_high[i], b_high[i]) - max(a_low[i], b_low[i]) > epsilon
               for i in range(len(a_low)))


def _point_box_distance_xy(point, low, high):
    return math.hypot(max(low[0] - point[0], 0., point[0] - high[0]),
                      max(low[1] - point[1], 0., point[1] - high[1]))


def _sample_path(points, spacing=10.):
    for start, end in zip(points, points[1:]):
        count = max(1, int(math.ceil(math.dist(start[:2], end[:2]) / spacing)))
        for index in range(count):
            t = index / count
            yield [start[i] + (end[i] - start[i]) * t for i in range(3)]
    if points:
        yield points[-1]


def validate_hotel_plan(plan):
    """Check capsule path clearance and fixed boxes against explicit corridors.

    This is a planning check. Unreal collision, movable leaves and saved asset
    pivots still require independent verification after applying the layout.
    """
    failures = []
    checks = 0
    minimum_path_clearance = float("inf")
    obstacles = [b for b in plan["boxes"] if b["collision"]
                 and b["category"] != "ground"]
    for reserved in plan["corridor_keepouts"]:
        for box in obstacles:
            checks += 1
            if _overlap(box["world_min"], box["world_max"],
                        reserved["world_min"], reserved["world_max"]):
                failures.append({"kind": "reserved_corridor_intrusion",
                                 "corridor": reserved["name"], "box": box["name"]})
    for route in plan["routes"]:
        for point in _sample_path(route["points"]):
            for box in obstacles:
                lo, hi = box["world_min"], box["world_max"]
                if hi[2] <= point[2] + .01 or lo[2] >= point[2] + PLAYER_HEIGHT_CM:
                    continue
                checks += 1
                clearance = _point_box_distance_xy(point, lo, hi) - PLAYER_RADIUS_CM
                minimum_path_clearance = min(minimum_path_clearance, clearance)
                if clearance < -.01:
                    failures.append({"kind": "capsule_path_blocked", "route": route["name"],
                                     "box": box["name"], "point": point,
                                     "clearance_cm": clearance})
    for room in plan["rooms"]:
        checks += 1
        matching = [door for door in plan["room_doors"] if door["room_id"] == room["id"]]
        if len(matching) != 1:
            failures.append({"kind": "room_door_count", "room": room["id"]})
    return {"status": "PASS" if not failures else "FAIL", "check_count": checks,
            "failure_count": len(failures), "failures": failures,
            "minimum_fixed_box_path_clearance_cm": None if math.isinf(minimum_path_clearance)
            else minimum_path_clearance,
            "scope": "pure geometry; saved Unreal collision and movable parts need separate checks"}


def build_hotel_plan(building):
    row = _as_report(building)
    if row.get("label") != EAST_BUILDING:
        raise ValueError("Hotel plan is restricted to the current East building")
    floors = [float(z) for z in row["floor_z"]]
    if len(floors) != 4 or abs(float(row["door_width_cm"]) - 140.) > .01:
        raise ValueError("Expected four real floors and the unchanged 140 cm exterior door")
    low, high = row["interior_min"], row["interior_max"]
    if high[0] - low[0] < 990. or high[1] - low[1] < 6900.:
        raise ValueError("Hotel building is smaller than the planned corridor and rooms")
    floor_z = floors[0]
    wall_x = low[0] + 380.
    room_x = wall_x + WALL_CM
    north_end = float(row["stair_keepout"]["min"][1]) - 345.
    room_pitch = (north_end - low[1]) / 8.
    if room_pitch < 650.:
        raise ValueError("Eight guest rooms would compress the north stair buffer")
    plan = {
        "building": EAST_BUILDING, "units": "UE centimetres",
        "hotel_name": "老城酒店", "floor_z_cm": floors,
        "exterior_entry": {"width_cm": 140., "height_cm": float(row.get("door_height_cm", 230.)),
                           "route": row["primary_entry_route"], "unchanged_opening": True},
        "boxes": [], "rooms": [], "room_doors": [], "guest_windows": [], "routes": [],
        "corridor_keepouts": [],
        "replace_actor_labels": ["OTS_P3Prop_SignAssemblyStreetEnd_01",
                                 "OTS_P3Prop_SignTextStreetEnd_01",
                                 "OTS_P3Prop_AwningAssemblyStreetEnd_01"],
        "stair_keepout": row["stair_keepout"],
        "forecourt": {"rect_xy": [8430., -3500., 9000., 3500.], "surface_z_cm": floor_z,
                      "purpose": "pedestrian hotel entrance and waiting area"},
        "street_corner": {"purpose": "small pedestrian rest areas beside the return junction",
                          "ground_surfaces": []},
        "room_windows": "preserve 16 front corridor windows; add one independent rear window per guest room",
        "material_paths": {
            "concrete": "/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldConcrete",
            "plaster": "/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_SchoolWall",
            "wood": "/Game/Yastar/OldTownSchoolStreet/Props/Detailed/Materials/M_P2_Wood",
            "green_metal": "/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldGreenMetal",
            "dark_trim": "/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_DarkTrim",
        },
    }
    boxes = plan["boxes"]

    def add(name, role, lo, hi, material, category="hotel_interior", **kwargs):
        boxes.append(_box(name, role, lo, hi, material, category, **kwargs))

    def reserved(name, lo, hi, purpose):
        plan["corridor_keepouts"].append({"name": name, "world_min": list(lo),
                                          "world_max": list(hi), "purpose": purpose})

    def route(name, points):
        plan["routes"].append({"name": name, "points": points})

    reserved("HotelGroundMainRoute", [9235., 43., floor_z], [9465., 3105., floor_z + 180.],
             "230 cm lobby route leading to the original north stair approach")
    reserved("HotelMainDoorApproach", [8250., 18., floor_z], [9465., 298., floor_z + 230.],
             "unobstructed hotel entrance and public forecourt")
    reserved("HotelNorthStair", row["stair_keepout"]["min"], row["stair_keepout"]["max"],
             "preserve original flights and landings")
    route("HotelOriginalEntry", row["primary_entry_route"])
    route("HotelOriginalGroundToStair", row["ground_route"])

    # The desk faces the entrance; its service space lies behind it.
    add("Hotel_ReceptionBase", "ReceptionCounter", [9750., -700., floor_z],
        [9815., -340., floor_z + 97.], "wood", floor=0)
    add("Hotel_ReceptionTop", "ReceptionCounterTop", [9745., -705., floor_z + 97.],
        [9820., -335., floor_z + 102.], "dark_trim", floor=0)
    add("Hotel_ReceptionBackdrop", "ReceptionBackdrop", [10012., -900., floor_z + 95.],
        [10020., -150., floor_z + 270.], "wood", floor=0, collision=False)
    for index, (x, y) in enumerate(((9580., 650.), (9760., 650.))):
        add("Hotel_LobbySeat_%02d" % (index + 1), "LobbySeat", [x, y, floor_z + 5.],
            [x + 150., y + 70., floor_z + 48.], "wood", floor=0)
        add("Hotel_LobbyBack_%02d" % (index + 1), "LobbySeatBack", [x, y + 62., floor_z + 48.],
            [x + 150., y + 70., floor_z + 95.], "wood", floor=0)
        for leg in (15., 125.):
            add("Hotel_LobbyLeg_%02d_%03d" % (index + 1, leg), "LobbySeatLeg",
                [x + leg, y + 10., floor_z], [x + leg + 10., y + 60., floor_z + 5.],
                "dark_trim", floor=0)
    add("Hotel_LobbyCoffeeTable", "LobbyTable", [9650., 850., floor_z],
        [9770., 910., floor_z + 48.], "wood", floor=0)

    # Exterior fixtures are separate boxes so fixed walls never include moving parts.
    add("Hotel_EntranceCanopy", "HotelCanopy", [8750., -42., floor_z + 257.],
        [9000.5, 358., floor_z + 273.], "green_metal", "hotel_exterior", collision=False)
    add("Hotel_EntranceCanopyEdge", "HotelCanopyEdge", [8745., -47., floor_z + 252.],
        [8755., 363., floor_z + 273.], "dark_trim", "hotel_exterior", collision=False)
    add("Hotel_MainSign", "HotelSignBacking", [8989., -92., floor_z + 294.],
        [9000.5, 408., floor_z + 369.], "green_metal", "hotel_exterior", collision=False)
    plan["sign"] = {"text": plan["hotel_name"], "center_cm": [8987., 158., floor_z + 331.5],
                    "front_normal": [-1., 0., 0.], "text_height_cm": 48., "emissive": False}

    for floor in range(1, 4):
        z = floors[floor]
        ceiling = floors[floor + 1] - 20. if floor < 3 else row["world_max"][2] - 20.
        reserved("Hotel_F%d_Corridor" % floor, [low[0], low[1], z],
                 [wall_x, north_end + 100., z + 180.],
                 "380 cm clear front corridor; existing front window holes stay untouched")
        route("Hotel_F%d_StairApproach" % floor,
              [[9350., north_end + 100., z], [9350., 3305., z], [9462., 3305., z]])
        for index in range(8):
            boundary0 = low[1] + index * room_pitch
            boundary1 = low[1] + (index + 1) * room_pitch
            y0 = boundary0 + (WALL_CM * .5 if index else 0.)
            y1 = boundary1 - WALL_CM * .5
            room_id = "%d%02d" % (floor + 1, index + 1)
            door_y = y0 + 160.
            opening_low = [wall_x, door_y - 45., z]
            opening_high = [room_x, door_y + 45., z + 200.]
            prefix = "Hotel_Room_" + room_id
            parts = []
            for name, lo, hi in (
                ("DoorWallLeft", [wall_x, y0, z], [room_x, door_y - 45., ceiling]),
                ("DoorWallRight", [wall_x, door_y + 45., z], [room_x, y1, ceiling]),
                ("DoorHeader", [wall_x, door_y - 45., z + 200.], [room_x, door_y + 45., ceiling]),
            ):
                actor_name = prefix + "_" + name
                add(actor_name, name, lo, hi, "plaster", floor=floor, room_id=room_id)
                parts.append(actor_name)
            add(prefix + "_NorthPartition", "GuestRoomPartition",
                [wall_x, boundary1 - 6., z], [high[0], boundary1 + 6., ceiling],
                "plaster", floor=floor, room_id=room_id)
            bed_y = y0 + 300.
            add(prefix + "_BedBase", "GuestBedBase", [9680., bed_y, z],
                [9830., bed_y + 210., z + 40.], "wood", floor=floor, room_id=room_id)
            add(prefix + "_Mattress", "GuestMattress", [9683., bed_y + 3., z + 40.],
                [9827., bed_y + 207., z + 55.], "concrete", floor=floor, room_id=room_id)
            add(prefix + "_Headboard", "GuestBedHeadboard", [9680., bed_y + 202., z + 40.],
                [9830., bed_y + 214., z + 100.], "wood", floor=floor, room_id=room_id)
            add(prefix + "_DeskTop", "GuestDeskTop", [9800., y1 - 160., z + 77.],
                [9950., y1 - 100., z + 80.], "wood", floor=floor, room_id=room_id)
            for leg in (0., 140.):
                add(prefix + "_DeskLeg_%03d" % leg, "GuestDeskLeg",
                    [9800. + leg, y1 - 155., z], [9810. + leg, y1 - 105., z + 77.],
                    "dark_trim", floor=floor, room_id=room_id)
            room_route = [[9350., door_y, z], [9600., door_y, z], [9600., bed_y + 100., z]]
            route(prefix + "_Entry", room_route)
            door_id = prefix + "_Door"
            window_id = prefix + "_RearWindow"
            plan["rooms"].append({"id": room_id, "floor": floor,
                                  "building": EAST_BUILDING,
                                  "world_min": [room_x, y0, z],
                                  "world_max": [high[0], y1, ceiling],
                                  "world_center": [wall_x + 6., door_y, z],
                                  "opening_width": 90., "opening_height": 200.,
                                  "axes": {"across": [0., 1., 0.], "inward": [1., 0., 0.]},
                                  "bed_dimensions_cm": [150., 210., 55.],
                                  "door_id": door_id, "window_id": window_id,
                                  "route": room_route})
            window_y = (y0 + y1) * .5
            story = floors[floor] - floors[floor - 1]
            window_z = z + .55 * story
            world_low, world_high = row["world_min"], row["world_max"]
            plan["guest_windows"].append({
                "window_id": window_id, "room_id": room_id, "building": EAST_BUILDING,
                "wall": "Rear", "floor": floor,
                "u": window_y - (world_low[1] + world_high[1]) * .5,
                "v": float(world_high[0] - world_low[0]),
                "z": window_z, "width": 125., "height": 120.,
                "world_center": [float(world_high[0]), window_y, window_z],
                "axes": {"across": [0., 1., 0.], "inward": [-1., 0., 0.]},
                "world_min": [float(high[0]) - .5, window_y - 62.5, window_z - 60.],
                "world_max": [float(world_high[0]) + .5, window_y + 62.5, window_z + 60.],
            })
            plan["room_doors"].append({
                "name": door_id, "door_id": door_id, "room_id": room_id, "floor": floor,
                "width_cm": 90., "height_cm": 200., "wall_thickness_cm": WALL_CM,
                "opening_min": opening_low, "opening_max": opening_high,
                "pivot_cm": [wall_x + 6., door_y - 43., z + 1.],
                "normal_axis": 0, "inward_sign": 1., "u_axis": 1,
                "axes": {"across": [0., 1., 0.], "inward": [1., 0., 0.]},
                "leaf_span_axis": "+Y", "hinge_side": -1,
                "closed_yaw_degrees": 0., "open_yaw_degrees": -90.,
                "leaf_dimensions_cm": [4., 86., 198.],
                "leaf_local_min": [-2., 0., 0.], "leaf_local_max": [2., 86., 198.],
                "initial_state": "open", "open_into_room": True,
                "fixed_wall_actor_names": parts, "route": room_route[:2],
                "frame_width_cm": 3., "minimum_clear_opening_cm": 84.,
                "animation_reserved": True,
            })

    def bench(name, x, y, axis="x", category="street_corner"):
        # Every bench has a 48 cm seat and actual floor contact through four legs.
        length, depth = (180., 55.) if axis == "x" else (55., 180.)
        add(name + "_Seat", "OutdoorBenchSeat", [x, y, floor_z + 43.],
            [x + length, y + depth, floor_z + 48.], "wood", category)
        if axis == "x":
            add(name + "_Back", "OutdoorBenchBack", [x, y + depth - 8., floor_z + 48.],
                [x + length, y + depth, floor_z + 95.], "wood", category)
        else:
            add(name + "_Back", "OutdoorBenchBack", [x, y, floor_z + 48.],
                [x + 8., y + depth, floor_z + 95.], "wood", category)
        for index, (dx, dy) in enumerate(((8., 8.), (length - 18., 8.),
                                         (8., depth - 18.), (length - 18., depth - 18.))):
            add(name + "_Leg_%d" % index, "OutdoorBenchLeg",
                [x + dx, y + dy, floor_z], [x + dx + 10., y + dy + 10., floor_z + 43.],
                "dark_trim", category)

    bench("Hotel_ForecourtBenchNorth", 8820., 800., "y", "hotel_exterior")
    bench("Hotel_ForecourtBenchSouth", 8820., -900., "y", "hotel_exterior")
    for side in (1, -1):
        suffix = "North" if side > 0 else "South"
        corner_rect = [6410., 530., 7370., 1755.] if side > 0 else [6410., -1755., 7370., -530.]
        surface = {"name": "HotelCornerRest" + suffix, "kind": "slab", "rect_xy": corner_rect,
                   "world_min": [corner_rect[0], corner_rect[1], floor_z - 20.],
                   "world_max": [corner_rect[2], corner_rect[3], floor_z],
                   "surface_z_cm": floor_z, "material_group": "concrete",
                   "purpose": "level rest-area paving, joined to existing side and rear walks"}
        plan["street_corner"]["ground_surfaces"].append(surface)
        add(surface["name"], "CornerRestPaving", surface["world_min"], surface["world_max"],
            "concrete", "ground")
        y = 1640. if side > 0 else -1695.
        bench("Corner" + suffix + "_EdgeBench", 6700., y)
        bench("Corner" + suffix + "_SideBench", 6465., 1050. if side > 0 else -1230., "y")
        for index, (px, py) in enumerate(((7090., 1640. if side > 0 else -1700.),
                                         (6465., 1400. if side > 0 else -1460.))):
            add("Corner%s_Planter_%d" % (suffix, index + 1), "CornerPlanter",
                [px, py, floor_z], [px + 120., py + 60., floor_z + 45.],
                "concrete", "street_corner")
        reserved("EastConnector" + suffix, [6090., 530. if side > 0 else -1755., floor_z],
                 [6410., 1755. if side > 0 else -530., floor_z + 180.],
                 "preserve full 320 cm connector")
        reserved("EastReturnLane" + suffix, [6200., 1755. if side > 0 else -2075., floor_z],
                 [8250., 2075. if side > 0 else -1755., floor_z + 180.],
                 "preserve complete closed return route")
        reserved("EastJunctionWestWalk" + suffix, [7370., 530. if side > 0 else -1755., floor_z],
                 [7550., 1755. if side > 0 else -530., floor_z + 180.],
                 "preserve junction sidewalk")
        route("EastConnector" + suffix, [[6250., side * 500., floor_z], [6250., side * 1915., floor_z]])
        route("EastReturn" + suffix, [[7900., 0., 1.], [7900., side * 1915., floor_z],
                                      [6200., side * 1915., floor_z]])
        reserved("MainWalk" + suffix, [6090., 350. if side > 0 else -530., floor_z],
                 [7550., 530. if side > 0 else -350., floor_z + 180.],
                 "preserve junction approach sidewalk")
    reserved("EastCrossRoad", [7550., -2075., 1.], [8250., 2075., 181.],
             "preserve full 700 cm vehicle road and turns")
    reserved("EastBoundaryWalk", [8250., -2075., floor_z], [8430., 2075., floor_z + 180.],
             "preserve continuous sidewalk opposite the hotel")
    plan["guest_rooms"] = plan["rooms"]
    plan["validation"] = validate_hotel_plan(plan)
    if plan["validation"]["status"] != "PASS":
        raise ValueError("Hotel plan fails corridor clearance: " + str(plan["validation"]["failures"][:5]))
    return plan
