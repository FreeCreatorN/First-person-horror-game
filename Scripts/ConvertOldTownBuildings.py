"""Convert the loaded school street's solid buildings into modular interiors.

Importing is side effect free. Call convert_buildings(actor_subsystem) only in
/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet. Original meshes and materials
are read only; new structural meshes live in the existing Meshes/hOUSE folder.
"""
from pathlib import Path
import json
import math
import sys

try:
    import unreal
except ImportError:
    unreal = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = PROJECT_ROOT / "Saved/CodexOutputs/EnterableStreet_20261002/SourceInventory.json"
TARGET_LEVEL = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
ASSET_ROOT = "/Game/Yastar/Meshes/hOUSE"
TAG = "OTS_Enterable_20261002"
FOLDER = "OldTownSchoolStreet/EnterableBuildings"
WALL = 20.0
SLAB = 20.0
TREAD = 28.0
FLIGHT_WIDTH = 140.0
LANDING_DEPTH = 140.0


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _is_building(label):
    return ((label.startswith("BLK_") and label.endswith("_Mass"))
            or label in ("Blockout_School_MainBuilding", "Blockout_School_Building_L", "Blockout_School_Building_R")
            or label.startswith("OTS_SchoolGuardMass_")
            or label.startswith("OTS_PerimeterBackdrop")
            or (label.startswith("OTS_PerimeterBoundary") and "Cap" not in label))


def _vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def _bounds(row):
    mesh = row["meshes"][0]
    center, extent = mesh["world_origin"], mesh["world_extent"]
    return [center[i] - extent[i] for i in range(3)], [center[i] + extent[i] for i in range(3)]


def _intersects(low, high, other_low, other_high, epsilon=0.01):
    return all(min(high[i], other_high[i]) - max(low[i], other_low[i]) > epsilon for i in range(3))


def _subtract_box(low, high, cut_low, cut_high):
    """Exact axis aligned difference, with no overlap between remaining boxes."""
    if not _intersects(low, high, cut_low, cut_high):
        return [(list(low), list(high))]
    intersection_low = [max(low[i], cut_low[i]) for i in range(3)]
    intersection_high = [min(high[i], cut_high[i]) for i in range(3)]
    remaining = []
    inner_low, inner_high = list(low), list(high)
    for axis in range(3):
        if intersection_low[axis] > inner_low[axis] + .01:
            end = list(inner_high)
            end[axis] = intersection_low[axis]
            remaining.append((list(inner_low), end))
            inner_low[axis] = intersection_low[axis]
        if intersection_high[axis] < inner_high[axis] - .01:
            start = list(inner_low)
            start[axis] = intersection_high[axis]
            remaining.append((start, list(inner_high)))
            inner_high[axis] = intersection_high[axis]
    return remaining


class Building:
    def __init__(self, row, all_rows, revision_entry=None):
        self.row = row
        self.label = row["label"]
        self.revision_entry = revision_entry
        self.public_route = list(revision_entry.get("outdoor_route", [])) if revision_entry else []
        self.stair_side_panels = []
        self.low, self.high = _bounds(row)
        self.center = [(self.low[i] + self.high[i]) * .5 for i in range(3)]
        name = self.label
        # u is across the facade, v increases into the room, z is world height.
        if name.startswith("Blockout_School_") or "SchoolGuard" in name or name == "OTS_PerimeterBoundaryWest_01":
            self.normal_axis, self.inward = 0, -1.0
        elif name == "OTS_PerimeterBoundaryEast_01":
            self.normal_axis, self.inward = 0, 1.0
        else:
            self.normal_axis = 1
            self.inward = 1.0 if self.center[1] > 0.0 else -1.0
        self.u_axis = 1 - self.normal_axis
        self.width = self.high[self.u_axis] - self.low[self.u_axis]
        self.depth = self.high[self.normal_axis] - self.low[self.normal_axis]
        self.height = self.high[2] - self.low[2]
        self.front = self.low[self.normal_axis] if self.inward > 0 else self.high[self.normal_axis]
        self.ground = 35.0 if (name.startswith("Blockout_School_") or "BoundarySchool" in name or name == "OTS_PerimeterBoundaryWest_01") else 11.0
        if revision_entry is not None:
            self.ground = float(revision_entry["floor_z_override_cm"])
        self.count = max(1, int(round((self.height - 30.0) / 330.0)))
        self.story = (self.high[2] - SLAB - self.ground) / self.count
        self.floors = [self.ground + self.story * index for index in range(self.count)]
        self.door_width = 120.0 if self.width < 300.0 else 140.0
        self.door_height = min(230.0, self.story - 8.0)
        self.portals = []
        offset = 158.0 if name == "OTS_PerimeterBoundaryEast_01" else 0.0
        if name == "OTS_PerimeterBackdropNorth02_01":
            # This row sits only 50 cm behind the residential shell. Align the
            # front doorway with that shell's matching rear-court portal.
            offset = 390.0
        street_prefix = name[:-5] if name.endswith("_Mass") else None
        for candidate in all_rows:
            if street_prefix and candidate["label"] == street_prefix + "_Door":
                offset = candidate["location"][self.u_axis] - self.center[self.u_axis]
        # Align the school annex entrance with the adjacent school's real portal.
        if "BoundarySchool" in name:
            if "West" in name:
                offset = -100.0
            elif "Mid" in name:
                offset = 100.0
        if revision_entry is not None:
            wall = revision_entry["door_wall"]
            coordinate = float(revision_entry["door_coordinate_cm"])
            _require(wall in ("Front", "Rear", "Left", "Right"), "Invalid revised door wall for " + name)
            _require(revision_entry.get("door_count") == 1, "Revised building requires exactly one door: " + name)
            if wall in ("Front", "Rear"):
                _require(abs(coordinate) + self.door_width*.5 <= self.width*.5-WALL,
                         "Revised door exceeds facade width: " + name)
            else:
                _require(WALL+self.door_width*.5 <= coordinate <= self.depth-WALL-self.door_width*.5,
                         "Revised side door exceeds facade depth: " + name)
            self.add_portal(wall, coordinate, True)
        else:
            self.add_portal("Front", offset, True)
            if name.startswith("BLK_") or name.startswith("Blockout_School_"):
                self.add_portal("Rear", offset)
        if self.count > 1:
            self.risers = int(math.ceil(self.story / 18.0))
            self.rise = self.story / self.risers
            self.n1 = int(math.ceil(self.risers / 2.0))
            self.n2 = self.risers - self.n1
            self.run = max(self.n1, self.n2) * TREAD
            self.core_width = 2.0 * FLIGHT_WIDTH + 20.0
            self.core_u = self.width * .5 - WALL - self.core_width * .5 - 25.0
            if name == "Blockout_School_Building_R":
                # Its north 120 cm overlaps the existing school annex. Keep
                # the stairs on the courtyard side instead of inside that wall.
                self.core_u = -self.core_u
            self.core_v = self.depth - WALL - self.run - LANDING_DEPTH - 25.0
            _require(self.core_v >= 155.0, "Stair core does not fit " + name)
            _require(self.width - 2.0 * WALL >= self.core_width + 120.0, "Stair landing too narrow " + name)

    def world(self, u, v, z):
        result = [0.0, 0.0, float(z)]
        result[self.u_axis] = self.center[self.u_axis] + u
        result[self.normal_axis] = self.front + self.inward * v
        return result

    def world_box(self, low, high):
        corners = (self.world(*low), self.world(*high))
        return ([min(c[axis] for c in corners) for axis in range(3)],
                [max(c[axis] for c in corners) for axis in range(3)])

    def local(self, point):
        return [point[self.u_axis] - self.center[self.u_axis],
                (point[self.normal_axis] - self.front) * self.inward, point[2]]

    def add_portal(self, wall, coordinate, primary=False):
        for portal in self.portals:
            if portal["wall"] == wall and abs(portal["coordinate"] - coordinate) < self.door_width * .7:
                return
        self.portals.append({"wall": wall, "coordinate": float(coordinate), "primary": primary})

    def aperture(self, portal, margin=0.0):
        half = self.door_width * .5 + margin
        c = portal["coordinate"]
        if portal["wall"] in ("Front", "Rear"):
            v = 0.0 if portal["wall"] == "Front" else self.depth
            low, high = [c-half, v-55.0, self.ground-12.0], [c+half, v+55.0, self.ground+self.door_height]
        else:
            u = -self.width*.5 if portal["wall"] == "Left" else self.width*.5
            low, high = [u-55.0, c-half, self.ground-12.0], [u+55.0, c+half, self.ground+self.door_height]
        return self.world_box(low, high)

    def door_route(self, portal):
        c = portal["coordinate"]
        if portal["wall"] in ("Front", "Rear"):
            v = 0.0 if portal["wall"] == "Front" else self.depth
            sign = 1.0 if portal["wall"] == "Front" else -1.0
            return [self.world(c, v-sign*110.0, self.ground), self.world(c, v+sign*125.0, self.ground)]
        u = -self.width*.5 if portal["wall"] == "Left" else self.width*.5
        sign = 1.0 if portal["wall"] == "Left" else -1.0
        return [self.world(u-sign*110.0, c, self.ground), self.world(u+sign*125.0, c, self.ground)]


def plan_buildings(rows, revision_plan=None):
    """Pure geometry planning, also usable outside UE for constraint checks."""
    entries = {}
    if revision_plan is not None:
        _require(revision_plan.get("target_level") == TARGET_LEVEL, "Revision targets another level")
        translated = revision_plan["translated_inventory"]
        _require(translated.get("level") == TARGET_LEVEL, "Translated inventory targets another level")
        rows = translated["actors"]
        planned_entries = revision_plan["building_entrances"]
        entries = {item["building"]: item for item in planned_entries}
        _require(len(planned_entries) == len(entries) == 29, "Revision requires 29 unique single-door entries")
        labels = {row["label"] for row in rows if _is_building(row["label"])}
        _require(set(entries) == labels, "Revised entry labels differ from translated building labels")
    buildings = [Building(row, rows, entries.get(row["label"])) for row in rows if _is_building(row["label"])]
    _require(len(buildings) == 29, "Expected 29 substantial building masses, got {}".format(len(buildings)))
    if revision_plan is not None:
        _require(all(len(building.portals) == 1 for building in buildings), "Revised portal count is not one per building")
        return buildings
    # Create aligned portals on actual adjoining walls, including small intentional
    # overlaps in the old blockout. Ground-floor doors connect the street rear
    # courts, schools, and annexes without pretending a closed wall is walkable.
    for index, first in enumerate(buildings):
        for second in buildings[index+1:]:
            overlap = [min(first.high[i],second.high[i])-max(first.low[i],second.low[i]) for i in (0,1)]
            axis = 0 if overlap[0] < overlap[1] else 1
            other_axis = 1-axis
            if overlap[other_axis] < 180.0 or not -320.0 <= overlap[axis] <= 250.0:
                continue
            middle = (max(first.low[other_axis],second.low[other_axis])+min(first.high[other_axis],second.high[other_axis]))*.5
            # If a nearby existing primary/rear portal is reused, both sides
            # must share its actual center. Merely deduplicating close holes
            # can leave <68 cm overlapping clearance across two party walls.
            for building,neighbor in ((first,second),(second,first)):
                positive = neighbor.center[axis] > building.center[axis]
                if axis == building.normal_axis:
                    wall = "Rear" if (positive == (building.inward > 0.0)) else "Front"
                    local_middle = middle-building.center[building.u_axis]
                    coordinate_to_world = lambda c: building.center[building.u_axis]+c
                else:
                    wall = "Right" if positive else "Left"
                    local_middle = (middle-building.front)*building.inward
                    coordinate_to_world = lambda c: building.front+building.inward*c
                matching = [p for p in building.portals if p["wall"] == wall and abs(p["coordinate"]-local_middle) < building.door_width*.7]
                if matching:
                    middle = coordinate_to_world(matching[0]["coordinate"])
                    break
            for building, neighbor in ((first,second),(second,first)):
                positive = neighbor.center[axis] > building.center[axis]
                if axis == building.normal_axis:
                    wall = "Rear" if (positive == (building.inward > 0.0)) else "Front"
                    coordinate = middle-building.center[building.u_axis]
                else:
                    wall = "Right" if positive else "Left"
                    coordinate = (middle-building.front)*building.inward
                building.add_portal(wall, coordinate)
    return buildings


def _load_material(path):
    material = unreal.EditorAssetLibrary.load_asset(path)
    _require(material is not None, "Missing existing material " + str(path))
    return material


class MeshFactory:
    """Independent structural modules, each with exactly one simple box.

    Scaling a single convex box per panel keeps door holes and stair voids exact;
    no concave shell is converted into a blocking whole-building convex hull.
    """
    def __init__(self, actor_subsystem):
        script_dir = str(PROJECT_ROOT / "Scripts")
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        import CreateOldTownDetailedProps as props
        self.props = props
        self.actors = actor_subsystem
        self.modules = {}
        self.count = 0
        self.roles = {}
        self.placed_boxes = []
        self.threshold_keys = set()
        self.floor_material = _load_material("/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldConcrete")
        self.trim_material = _load_material("/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldGreenMetal")

    def module(self, role):
        if role not in self.modules:
            existing = unreal.load_asset(ASSET_ROOT + "/SM_OTS_Enterable_" + role)
            if existing is not None:
                bounds = existing.get_bounds()
                _require(all(abs(float(v)*2.-100.) < .01 for v in (bounds.box_extent.x,bounds.box_extent.y,bounds.box_extent.z)), "Structural cube dimensions changed")
                shapes = unreal.GeometryScript_Collision.get_simple_collision_from_static_mesh(existing)
                _require(unreal.GeometryScript_Collision.get_simple_collision_shape_count(shapes) == 1, "Structural cube collider missing")
                self.modules[role] = existing
                return existing
            builder = self.props.PropMeshBuilder(role)
            builder.box((0.,0.,0.), (100.,100.,100.), "M_P2_OldMetal", bevel=0.)
            builder.collision_boxes.append(((0.,0.,0.),(100.,100.,100.),(0.,0.,0.)))
            self.modules[role] = self.props._create_or_update_asset(
                ASSET_ROOT, "SM_OTS_Enterable_"+role, builder,
                {"M_P2_OldMetal": self.floor_material})
        return self.modules[role]

    def box(self, building, role, low, high, material=None, collision=True, suffix=""):
        world_low, world_high = building.world_box(low, high)
        return self.world_box(building.label,role,world_low,world_high,material,collision,suffix)

    def world_box(self, building_label, role, low, high, material=None, collision=True, suffix=""):
        size = [high[i]-low[i] for i in range(3)]
        if min(size) < .05:
            return None
        # Adjoining rooms share a doorway; their identical threshold needs
        # one physical panel rather than two coplanar instances.
        if role == "DoorThreshold":
            key = tuple(round(v, 3) for v in low + high)
            if key in self.threshold_keys:
                return None
            self.threshold_keys.add(key)
        center = [(high[i]+low[i])*.5 for i in range(3)]
        actor = self.actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*center),unreal.Rotator(0.,0.,0.),False)
        _require(actor is not None,"Cannot spawn structural panel")
        self.count += 1
        actor.set_actor_label("OTS_Enterable_{}_{}_{:04d}{}".format(building_label,role,self.count,suffix))
        actor.set_folder_path(unreal.Name(FOLDER + "/" + building_label))
        actor.set_editor_property("tags",[unreal.Name(TAG),unreal.Name("OTS_Building_"+building_label)])
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_static_mesh(self.module(role))
        component.set_material(0,material or self.floor_material)
        actor.set_actor_scale3d(unreal.Vector(*(value/100. for value in size)))
        actor.set_actor_enable_collision(bool(collision))
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS if collision else unreal.CollisionEnabled.NO_COLLISION)
        if collision:
            component.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
        self.roles[role] = self.roles.get(role,0)+1
        self.placed_boxes.append({"building":building_label,"role":role,"min":low,"max":high,
                                  "actor":actor.get_actor_label(),"collision":bool(collision)})
        return actor


def _emit_wall(factory, building, name, low, high, material):
    boxes = [(low,high)]
    for portal in building.portals:
        if portal["wall"] != name:
            continue
        world_low,world_high = building.aperture(portal)
        local_a,local_b = building.local(world_low),building.local(world_high)
        cut_low = [min(local_a[i],local_b[i]) for i in range(3)]
        cut_high = [max(local_a[i],local_b[i]) for i in range(3)]
        boxes = [part for a,b in boxes for part in _subtract_box(a,b,cut_low,cut_high)]
    for a,b in boxes:
        factory.box(building,"WallPanel",a,b,material)


def _emit_floor(factory,building,z,cut_stairs):
    low = [-building.width*.5+WALL,WALL,z-SLAB]
    high = [building.width*.5-WALL,building.depth-WALL,z]
    boxes = [(low,high)]
    if cut_stairs:
        cut_low = [building.core_u-building.core_width*.5,building.core_v,z-SLAB-1.]
        cut_high = [building.core_u+building.core_width*.5,building.core_v+building.run+LANDING_DEPTH,z+1.]
        boxes = _subtract_box(low,high,cut_low,cut_high)
    for a,b in boxes:
        factory.box(building,"FloorSlab",a,b)


def _stair_side_panel(factory, building, level, low, high, coverage):
    actor = factory.box(building, "StairSidePanel", low, high, factory.trim_material)
    _require(actor is not None, "Cannot emit closed stair panel for " + building.label)
    world_low, world_high = building.world_box(low, high)
    record = {"building": building.label, "from_floor": level, "to_floor": level+1,
              "actor": actor.get_actor_label(), "world_min": world_low, "world_max": world_high,
              "local_min": list(low), "local_max": list(high), "coverage": coverage,
              "collision": True, "material": "M_OTS_OldGreenMetal"}
    building.stair_side_panels.append(record)
    return record


def _emit_closed_stair_sides(factory, building, level):
    """Emit four shared, flush rectangular panels once for the entire core.

    Their full height removes stepped edges and coplanar overlaps between
    storeys. The centre fills the 20cm gap, ending before the 140cm turning
    landing. The open front remains the entrance and upper-floor exit.
    """
    _require(0 <= level < building.count-1, "Invalid stair level for " + building.label)
    records = getattr(building, "_regular_stair_side_panels", None)
    generated_count = 0
    if records is None:
        _require(level == 0, "Shared stair panels must start at level zero for " + building.label)
        _require(not building.stair_side_panels, "Stair panels already exist for " + building.label)
        bottom, top = building.ground, building.high[2]-SLAB
        left_edge = building.core_u-building.core_width*.5
        right_edge = building.core_u+building.core_width*.5
        run_end = building.core_v+building.run
        landing_end = run_end+LANDING_DEPTH
        rear_wall = building.depth-WALL
        # One outer side is next to the building wall, including the mirrored
        # school wing. Fill its complete 25cm setback outward, retaining the
        # 140cm flight width. The room-facing side stays four centimetres.
        left_outer = -building.width*.5+WALL if building.core_u < 0.0 else left_edge-4.0
        right_outer = right_edge+4.0 if building.core_u < 0.0 else building.width*.5-WALL
        _require(left_outer < left_edge and right_outer > right_edge and rear_wall > landing_end,
                 "Stair enclosure cannot join the building walls for " + building.label)
        left_role = "wall" if building.core_u < 0.0 else "room"
        right_role = "room" if building.core_u < 0.0 else "wall"
        specs = [
            ("FullHeightLeft", left_role,
             [left_outer, building.core_v, bottom], [left_edge, landing_end, top]),
            ("FullHeightRight", right_role,
             [right_edge, building.core_v, bottom], [right_outer, landing_end, top]),
            ("FullHeightDivider", "center_gap",
             [building.core_u-10.0, building.core_v, bottom], [building.core_u+10.0, run_end, top]),
            ("FullHeightRear", "rear",
             [left_outer, landing_end, bottom], [right_outer, rear_wall, top]),
        ]
        records = []
        for part, side, low, high in specs:
            coverage = {"part": part, "side": side, "step": None,
                        "lower_floor_z_cm": bottom, "support_top_z_cm": building.floors[-1],
                        "panel_top_z_cm": top, "guard_height_cm": top-building.floors[-1],
                        "thickness_cm": high[1]-low[1] if side == "rear" else high[0]-low[0],
                        "v_start_cm": low[1], "v_end_cm": high[1],
                        "closed_from_lower_floor": True, "full_height": True,
                        "flat_top": True, "shared_between_floors": True,
                        "from_floor": 0, "to_floor": building.count-1,
                        "flight_clear_width_cm": FLIGHT_WIDTH,
                        "clear_turning_depth_cm": LANDING_DEPTH,
                        "stops_before_turning_landing": side == "center_gap"}
            record = _stair_side_panel(factory, building, 0, low, high, coverage)
            record["to_floor"] = building.count-1
            records.append(record)
        building._regular_stair_side_panels = records
        generated_count = len(records)
    return {"panel_count": len(records), "generated_panel_count": generated_count,
            "panel_actor_labels": [record["actor"] for record in records],
            "shared_between_floors": True, "full_height": True, "flat_top": True,
            "from_floor": level, "to_floor": level+1,
            "flight1_tread_skins": 0, "flight2_tread_skins": 0,
            "closed_from_lower_floor": True,
            "guard_height_cm": building.high[2]-SLAB-building.floors[-1],
            "flight_clear_width_cm": FLIGHT_WIDTH, "center_divider_width_cm": 20.0,
            "center_gap_cm": 20.0, "turning_landing_clear_depth_cm": LANDING_DEPTH,
            "upper_floor_room_side_guard_filled": True}


def _emit_stairs(factory,building):
    reports = []
    if building.count == 1:
        return reports
    left_center = building.core_u-(FLIGHT_WIDTH+20.)*.5
    right_center = building.core_u+(FLIGHT_WIDTH+20.)*.5
    for level in range(building.count-1):
        z = building.floors[level]
        middle_z = z+building.n1*building.rise
        route = [building.world(left_center,building.core_v-65.,z)]
        for step in range(1,building.n1+1):
            v = building.core_v+(step-.5)*TREAD
            top = z+step*building.rise
            factory.box(building,"StairTread",
                        [left_center-FLIGHT_WIDTH*.5,v-TREAD*.5,top-building.rise-20.],
                        [left_center+FLIGHT_WIDTH*.5,v+TREAD*.5+.1,top])
            route.append(building.world(left_center,v,top))
        landing_v = building.core_v+building.run+LANDING_DEPTH*.5
        factory.box(building,"StairLanding",
                    [building.core_u-building.core_width*.5,building.core_v+building.n1*TREAD,middle_z-SLAB],
                    [building.core_u+building.core_width*.5,building.core_v+building.run+LANDING_DEPTH,middle_z])
        route += [building.world(left_center,landing_v,middle_z),building.world(right_center,landing_v,middle_z)]
        for step in range(1,building.n2+1):
            v = building.core_v+(building.n2-step+.5)*TREAD+(building.n1-building.n2)*TREAD
            top = middle_z+step*building.rise
            factory.box(building,"StairTread",
                        [right_center-FLIGHT_WIDTH*.5,v-TREAD*.5,top-building.rise-20.],
                        [right_center+FLIGHT_WIDTH*.5,v+TREAD*.5+.1,top])
            route.append(building.world(right_center,v,top))
        if building.n1 > building.n2:
            # Odd riser counts have a shorter return flight. Fill its arrival
            # strip, so there is no one-tread unsupported gap before the floor.
            factory.box(building,"StairLanding",
                        [right_center-FLIGHT_WIDTH*.5,building.core_v,building.floors[level+1]-SLAB],
                        [right_center+FLIGHT_WIDTH*.5,building.core_v+TREAD,building.floors[level+1]])
        route.append(building.world(right_center,building.core_v-65.,building.floors[level+1]))
        # A safe standing/turning area on the intact upper floor, outside the hole.
        route.append(building.world(building.core_u,building.core_v-85.,building.floors[level+1]))
        stair_report = {"from_floor":level,"to_floor":level+1,"rise_cm":building.rise,
                        "tread_cm":TREAD,"width_cm":120.,"foot_waypoints":route,
                        "headroom_cm":building.story-SLAB,
                        "landing_depth_cm":LANDING_DEPTH}
        if building.revision_entry is not None:
            stair_report["side_panel_coverage"] = _emit_closed_stair_sides(factory, building, level)
        else:
            # Preserve the original converter's guard geometry for legacy calls.
            guard_u = building.core_u-building.core_width*.5-3.
            factory.box(building,"StairGuard",
                        [guard_u-2.,building.core_v,building.floors[level+1]],
                        [guard_u+2.,building.core_v+building.run+LANDING_DEPTH,building.floors[level+1]+105.],factory.trim_material)
        reports.append(stair_report)
    return reports


def _emit_thresholds(factory,building):
    for portal in building.portals:
        c = portal["coordinate"]
        half = building.door_width*.5
        if portal["wall"] in ("Front","Rear"):
            v = 0. if portal["wall"] == "Front" else building.depth
            low,high = [c-half,v-125.,building.ground-SLAB],[c+half,v+125.,building.ground]
        else:
            u = -building.width*.5 if portal["wall"] == "Left" else building.width*.5
            low,high = [u-125.,c-half,building.ground-SLAB],[u+125.,c+half,building.ground]
        factory.box(building,"DoorThreshold",low,high)


def _emit_lights(factory,building):
    for level,z in enumerate(building.floors):
        for index,u in enumerate(([-building.width*.25,building.width*.25] if building.width > 2500. else [0.])):
            location = building.world(u,building.depth*.38,z+min(215.,building.story-45.))
            light = factory.actors.spawn_actor_from_class(unreal.PointLight,unreal.Vector(*location),unreal.Rotator(0.,0.,0.),False)
            _require(light is not None,"Cannot spawn interior light")
            light.set_actor_label("OTS_Enterable_{}_InteriorLight_{}_{}".format(building.label,level,index))
            light.set_folder_path(unreal.Name(FOLDER+"/"+building.label+"/Lights"))
            light.set_editor_property("tags",[unreal.Name(TAG)])
            component = light.get_component_by_class(unreal.PointLightComponent)
            component.set_editor_property("intensity",1800.)
            component.set_editor_property("attenuation_radius",max(750.,min(2200.,building.width*.6)))
            component.set_editor_property("light_color",unreal.Color(255,225,190,255))
            component.set_editor_property("cast_shadows",True)


def _emit_building(factory,building):
    material = _load_material(building.row["meshes"][0]["materials"][0])
    w,d,z0,z1 = building.width,building.depth,building.low[2],building.high[2]
    _emit_wall(factory,building,"Front",[-w*.5,0.,z0],[w*.5,WALL,z1],material)
    _emit_wall(factory,building,"Rear",[-w*.5,d-WALL,z0],[w*.5,d,z1],material)
    _emit_wall(factory,building,"Left",[-w*.5,WALL,z0],[-w*.5+WALL,d-WALL,z1],material)
    _emit_wall(factory,building,"Right",[w*.5-WALL,WALL,z0],[w*.5,d-WALL,z1],material)
    for index,z in enumerate(building.floors):
        _emit_floor(factory,building,z,index > 0)
    # The roof remains sealed; existing rooftop silhouettes stay decorative.
    factory.box(building,"RoofSlab",[-w*.5+WALL,WALL,z1-SLAB],[w*.5-WALL,d-WALL,z1],material)
    if building.revision_entry is None:
        _emit_thresholds(factory,building)
    stairs = _emit_stairs(factory,building)
    if getattr(factory,'lighting_policy',None) != 'street_lamps_only':
        _emit_lights(factory,building)
    doors = []
    for index,portal in enumerate(building.portals):
        low,high = building.aperture(portal)
        doors.append({"name":portal["wall"]+"_"+str(index),"primary":portal["primary"],
                      "width_cm":building.door_width,"height_cm":building.door_height,
                      "route":building.door_route(portal),"opening_min":low,"opening_max":high})
    primary_route = next(door["route"] for door in doors if door["primary"])
    ground_route = [primary_route[-1]]
    if stairs:
        # Approach the stair entry along the front clear area, then turn into
        # the core. Avoid diagonally cutting across the side of the first tread.
        entry_local = building.local(primary_route[-1])
        left_u = building.core_u-(FLIGHT_WIDTH+20.)*.5
        safe_v = min(building.core_v-70.,350.)
        ground_route += [building.world(entry_local[0],safe_v,building.ground),
                         building.world(left_u,safe_v,building.ground),
                         stairs[0]["foot_waypoints"][0]]
    else:
        ground_route.append(building.world(0.,d*.5,building.ground))
    interior_low,interior_high = building.world_box([-w*.5+WALL,WALL,building.ground],[w*.5-WALL,d-WALL,z1-SLAB])
    keepout = None
    if stairs:
        keep_low,keep_high = building.world_box([building.core_u-building.core_width*.5-50.,building.core_v-140.,building.ground],
                                              [building.core_u+building.core_width*.5+50.,building.core_v+building.run+LANDING_DEPTH+20.,z1])
        keepout = {"min":keep_low,"max":keep_high}
    furniture_zones = []
    if w > 450.:
        if stairs and building.core_u < 0.:
            zone_u_low,zone_u_high = w*.5-WALL-min(260.,w*.3),w*.5-WALL-50.
        else:
            zone_u_low,zone_u_high = -w*.5+WALL+50.,-w*.5+WALL+min(260.,w*.3)
        zone_low,zone_high = building.world_box([zone_u_low,d*.55,building.ground],
                                              [zone_u_high,d-WALL-50.,building.ground])
        furniture_zones.append({"min":zone_low,"max":zone_high})
    return {"label":building.label,"world_min":building.low,"world_max":building.high,
            "floor_z":building.floors,"floor_clear_height_cm":building.story-SLAB,
            "floor_support_points":[building.world(0.,min(125.,d*.5),elevation) for elevation in building.floors],
            "door_width_cm":building.door_width,"door_height_cm":building.door_height,
            "doors":doors,"primary_entry_route":primary_route,"ground_route":ground_route,
            "stairs":stairs,"interior_min":interior_low,"interior_max":interior_high,
            "stair_keepout":keepout,"furniture_zones":furniture_zones,
            "public_route":building.public_route,"stair_side_panels":building.stair_side_panels,
            "portal_policy":"single_public_entry" if building.revision_entry is not None else "legacy_connections",
            "door_thresholds_emitted":building.revision_entry is None}


def _access_cuts(rows):
    cuts = []
    for row in rows:
        if row["label"] not in ("BLK_Alley_L_EndWall","BLK_Alley_R_EndWall"):
            continue
        low,high = _bounds(row)
        x,y = row["location"][:2]
        cuts.append({"name":row["label"],"min":[x-70.,low[1]-40.,11.],"max":[x+70.,high[1]+40.,241.],
                     "route":[[x,y-105.,11.],[x,y+105.,11.]]})
    return cuts


def _convert_facades(factory,rows,buildings,current_by_label,revision_plan=None):
    cuts = []
    for building in buildings:
        for portal in building.portals:
            low,high = building.aperture(portal)
            low[2] = building.ground
            cuts.append((low,high,building.label))
    accesses = _access_cuts(rows) if revision_plan is None else []
    cuts += [(item["min"],item["max"],item["name"]) for item in accesses]
    removed,split = [],[]
    protected_tokens = ("MainHome","MainRoad","Sidewalk","Alley_R_Floor","Alley_L_Floor","SchoolGround",
                        "SchoolFront_Apron","SchoolStep","PerimeterGround","StreetEndRoad","StreetEndSidewalk","Drain")
    for row in rows:
        name = row["label"]
        if _is_building(name) or not row.get("meshes") or any(token in name for token in protected_tokens):
            continue
        if len(row["meshes"]) != 1:
            continue
        low,high = _bounds(row)
        touching = [(a,b,label) for a,b,label in cuts if _intersects(low,high,a,b)]
        if not touching:
            continue
        mesh = row["meshes"][0]
        is_cube = mesh["mesh"] == "/Engine/BasicShapes/Cube.Cube" and abs(float(row.get("yaw",0.))) < .01
        if not is_cube and not any(token in name for token in ("Shutter","Door","Window","WallUtility")):
            continue
        original = current_by_label.get(name)
        if original is not None:
            _require(factory.actors.destroy_actor(original),"Cannot remove facade blocker "+name)
        removed.append(name)
        if is_cube:
            pieces = [(low,high)]
            for a,b,_ in touching:
                pieces = [part for part_low,part_high in pieces for part in _subtract_box(part_low,part_high,a,b)]
            if pieces:
                split.append(name)
                materials = mesh.get("materials") or []
                material = _load_material(materials[0]) if materials and materials[0] else factory.floor_material
                collision = "NO_COLLISION" not in mesh.get("collision","")
                for a,b in pieces:
                    factory.world_box(touching[0][2],"FacadePanel",a,b,material,collision,"_"+name)
    # Thresholds for the opened alley termination provide continuous support.
    for access in accesses:
        low,high = access["min"],access["max"]
        factory.world_box(access["name"],"DoorThreshold",
                          [low[0],access["route"][0][1]-25.,-9.],
                          [high[0],access["route"][1][1]+25.,11.])
    return removed,split,accesses


def convert_buildings(actor_subsystem, revision_plan=None):
    """Modify the authorized, already loaded target level and return a report.

    Saving the target map and validating physics are intentionally delegated to
    the caller. The immutable original inventory makes reruns deterministic.
    """
    _require(unreal is not None,"Unreal Python runtime is required")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    _require(world is not None and world.get_path_name().startswith(TARGET_LEVEL+"."),
             "Refusing to convert any level except "+TARGET_LEVEL)
    _require(unreal.EditorAssetLibrary.does_directory_exist(ASSET_ROOT),"Existing hOUSE asset folder missing")
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    _require(inventory.get("level") == TARGET_LEVEL,"Inventory level does not match target")
    rows = inventory["actors"] if revision_plan is None else revision_plan["translated_inventory"]["actors"]
    buildings = plan_buildings(rows, revision_plan)
    original_labels = {item.label for item in buildings}
    current = list(actor_subsystem.get_all_level_actors())
    current_by_label = {actor.get_actor_label():actor for actor in current}
    cleanup = [actor for actor in current if TAG in [str(tag) for tag in actor.get_editor_property("tags")]]
    if cleanup:
        _require(actor_subsystem.destroy_actors(cleanup),"Unable to remove previous generated conversion")
    factory = MeshFactory(actor_subsystem)
    factory.lighting_policy = (revision_plan or {}).get('lighting_policy','street_lamps_only')
    reports = []
    for building in buildings:
        actor = current_by_label.get(building.label)
        if actor is not None:
            # These are the original cube instances. Their Engine meshes and
            # shared old-town materials are never written by this converter.
            _require(actor_subsystem.destroy_actor(actor),"Cannot replace original mass "+building.label)
        reports.append(_emit_building(factory,building))
    removed,split,accesses = _convert_facades(factory,rows,buildings,current_by_label,revision_plan)
    leftover = [actor.get_actor_label() for actor in actor_subsystem.get_all_level_actors() if actor.get_actor_label() in original_labels]
    _require(not leftover,"Solid source masses remain: "+str(leftover))
    report = {"building_count":len(reports),"generated_actor_count":factory.count,
              "generated_assets":[mesh.get_path_name() for mesh in factory.modules.values()],
              "module_actor_distribution":factory.roles,"facade_removed":removed,"facade_split":split,
              "buildings":reports,"access_routes":accesses,"structural_boxes":factory.placed_boxes,
              "stair_side_panels":[panel for building in reports for panel in building["stair_side_panels"]],
              "revision_applied":revision_plan is not None,
              "door_thresholds_emitted":revision_plan is None,
              "collision_strategy":"One simple box per structural panel, slab, landing, and tread; no whole-building hull",
              "target_level":TARGET_LEVEL,"source_inventory":str(INVENTORY_PATH)}
    unreal.log("OTS_ENTERABLE_BUILDINGS_SUCCESS buildings={} structural_actors={} assets={}".format(len(reports),factory.count,len(factory.modules)))
    return report
