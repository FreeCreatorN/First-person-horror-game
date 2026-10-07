"""World collision checks for actual converted building entries and stairs."""
import math
from collections import deque
import unreal

RADIUS = 34.0
HALF_HEIGHT = 90.0
MAX_STEP = 45.0


def refresh_world_collision(actors):
    """Register loaded component bodies in the standalone editor commandlet."""
    # Loaded meshes may still be compiling asynchronously. Registering before
    # their body setup is ready can make a freshly loaded wall miss overlaps.
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    count = 0
    for actor in actors:
        for component in actor.get_components_by_class(unreal.PrimitiveComponent):
            state = component.get_collision_enabled()
            if state.value != unreal.CollisionEnabled.NO_COLLISION.value:
                component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                component.set_collision_enabled(state)
                count += 1
    return count


def _vector(values):
    return unreal.Vector(*[float(v) for v in values])


def capsule_blocking_components(world, foot, lift=0.0, ignore=()):
    position = _vector([foot[0], foot[1], foot[2] + HALF_HEIGHT + 2.0 + lift])
    components = unreal.SystemLibrary.capsule_overlap_components(
        world, position, RADIUS, HALF_HEIGHT,
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
        unreal.PrimitiveComponent, list(ignore)) or []
    return [component for component in components
            if component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN).value == unreal.CollisionResponseType.ECR_BLOCK.value]


def capsule_blockers(world, foot, lift=0.0, ignore=()):
    return [component.get_owner().get_actor_label() + ":" + component.get_name()
            for component in capsule_blocking_components(world, foot, lift, ignore)]


def sample_route(world, route, lift=0.0, ignore=()):
    failures = []
    checked = 0
    for a, b in zip(route, route[1:]):
        distance = math.dist(a, b)
        count = max(1, math.ceil(distance / 18.0))
        for index in range(count + 1):
            t = index / count
            point = [a[i] + (b[i] - a[i]) * t for i in range(3)]
            blockers = capsule_blockers(world, point, lift, ignore)
            checked += 1
            if blockers:
                failures.append({"foot": point, "blockers": blockers})
    return {"samples": checked, "failures": failures}


def validate_main_home(actors):
    homes = [actor for actor in actors if actor.get_actor_label() == "BP_OTS_MainHomeInteractive"]
    assert len(homes) == 1, "MainHome actor missing or duplicated"
    components = homes[0].get_components_by_class(unreal.StaticMeshComponent)
    assert len([c for c in components if c.static_mesh]) == 4, "MainHome movable meshes changed"
    assert len(homes[0].get_components_by_class(unreal.BoxComponent)) >= 2, "MainHome interaction zones missing"
    return {"actor": homes[0].get_actor_label(), "mesh_components": 4, "interaction_preserved": True}


def floor_support(world, foot, tolerance=2.5):
    hit = unreal.SystemLibrary.line_trace_single_for_objects(
        world, _vector([foot[0], foot[1], foot[2] + MAX_STEP]),
        _vector([foot[0], foot[1], foot[2] - MAX_STEP]),
        [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
        False, [], unreal.DrawDebugTrace.NONE)
    if hit is None:
        return {"passed": False, "foot": foot, "reason": "No supporting collision"}
    impact = hit.to_tuple()[5]
    error = float(impact.z) - float(foot[2])
    return {"passed": abs(error) <= tolerance, "foot": foot, "support_z": float(impact.z), "error_cm": error}


def validate_buildings(world, actors, report):
    checks = []
    assert report["building_count"] == 29, "Incomplete obvious-building conversion"
    # A blocking wall is a negative control: a clear result must never be
    # accepted merely because enum conversion or physics registration failed.
    control = next(a for a in actors if a.get_actor_label().startswith("OTS_Enterable_")
                   and "_WallPanel_" in a.get_actor_label())
    control_center, _extent = control.get_actor_bounds(False)
    control_foot = [control_center.x, control_center.y, control_center.z - HALF_HEIGHT - 2.0]
    control_hits = capsule_blockers(world, control_foot)
    control_passed = any(hit.startswith(control.get_actor_label() + ":") for hit in control_hits)
    assert control_passed, "Collision negative control failed: blocking wall was not detected"
    for building in report["buildings"]:
        entry = sample_route(world, building["primary_entry_route"])
        ground = sample_route(world, building["ground_route"])
        entry_support = [floor_support(world, building["primary_entry_route"][-1])]
        stairs = []
        for flight in building["stairs"]:
            assert 0 < flight["rise_cm"] <= 18.01, flight
            assert flight["tread_cm"] >= 25.99 and flight["width_cm"] >= 109.99, flight
            # CharacterMovement can step up <=45cm. Sweep the volume at that
            # lift to check blocking upper slabs/headroom, and separately trace
            # every authored tread for support; this is not a runtime playthrough.
            headroom = sample_route(world, flight["foot_waypoints"], lift=MAX_STEP)
            supports = [floor_support(world, p, 19.0) for p in flight["foot_waypoints"]]
            stairs.append({"from_floor": flight["from_floor"], "to_floor": flight["to_floor"],
                           "headroom": headroom, "supports": supports})
        floor_checks = []
        support_points = building.get("floor_support_points") or [
            [(building["world_min"][0] + building["world_max"][0]) * .5,
             (building["world_min"][1] + building["world_max"][1]) * .5, elevation]
            for elevation in building["floor_z"]]
        for point in support_points:
            floor_checks.append(floor_support(world, point))
        passed = not entry["failures"] and not ground["failures"] and all(r["passed"] for r in entry_support + floor_checks)
        passed = passed and all(not s["headroom"]["failures"] and all(r["passed"] for r in s["supports"]) for s in stairs)
        checks.append({"label": building["label"], "passed": passed, "entry": entry,
                       "ground": ground, "entry_support": entry_support, "floors": floor_checks, "stairs": stairs})
    connectivity = validate_ground_connectivity(world, report)
    return {"passed": all(c["passed"] for c in checks) and connectivity["passed"], "building_count": len(checks),
            "capsule_radius_cm": RADIUS, "capsule_height_cm": HALF_HEIGHT * 2,
            "step_up_clearance_cm": MAX_STEP, "checks": checks, "ground_connectivity": connectivity,
            "blocking_wall_control": {"passed": control_passed, "actor": control.get_actor_label(), "hits": control_hits}}


def validate_ground_connectivity(world, report):
    """Flood actual capsule-free ground cells from the main street to entries.

    This checks connected approach space, not AI navmesh or player input. A
    50cm grid fits the 72cm center clearance left in a 140cm doorway.
    """
    spacing = 50.0
    heights = {}
    def ground_height(position):
        key = (position[0], position[1])
        if key not in heights:
            hit = unreal.SystemLibrary.line_trace_single_for_objects(
                world, _vector([position[0], position[1], 58.0]),
                _vector([position[0], position[1], -25.0]),
                [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
                False, [], unreal.DrawDebugTrace.NONE)
            heights[key] = float(hit.to_tuple()[5].z) if hit is not None else None
        return heights[key]
    def ground_clear(xy, previous_height):
        z = ground_height(xy)
        if z is None or abs(z - previous_height) > MAX_STEP + .01:
            return None
        foot = [xy[0], xy[1], z]
        blockers = capsule_blocking_components(world, foot)
        if not blockers:
            return z
        # The rounded capsule can touch the riser before its center reaches
        # the next tread. CharacterMovement steps up such low obstacles.
        # Require every overlapping obstacle to end within the configured
        # step height, and check the whole capsule at that height for headroom.
        for component in blockers:
            origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(component)
            if float(origin.z + extent.z) > z + MAX_STEP + .01:
                return None
        if capsule_blocking_components(world, foot, lift=MAX_STEP):
            return None
        return z
    cell = lambda p: (round(p[0] / spacing), round(p[1] / spacing))
    goals = {b["label"]: cell(b["primary_entry_route"][-1]) for b in report["buildings"]}
    world_rect = report.get("world_ground_rect",[-5950.,-3400.,7550.,3400.])
    xmin, xmax = math.ceil(world_rect[0]/spacing), math.floor(world_rect[2]/spacing)
    ymin, ymax = math.ceil(world_rect[1]/spacing), math.floor(world_rect[3]/spacing)
    start = cell([1000.0, 0.0])
    visited = {start}
    queue = deque([start])
    blocked = set()
    blocked_diagnostics = []
    reached = {}
    while queue:
        current = queue.popleft()
        for label, goal in goals.items():
            if label not in reached and current == goal:
                reached[label] = [current[0] * spacing, current[1] * spacing,
                                  ground_height([current[0] * spacing, current[1] * spacing])]
        if len(reached) == len(goals):
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (current[0] + dx, current[1] + dy)
            if nxt in visited or nxt in blocked or not (xmin <= nxt[0] <= xmax and ymin <= nxt[1] <= ymax):
                continue
            current_height = ground_height([current[0] * spacing, current[1] * spacing])
            xy = [nxt[0] * spacing, nxt[1] * spacing]
            next_height = ground_clear(xy, current_height)
            if next_height is None:
                blocked.add(nxt)
                if len(blocked_diagnostics) < 12 or (nxt[1] == 0 and -32 <= nxt[0] <= 25):
                    z = ground_height(xy)
                    blocked_diagnostics.append({"xy": xy, "support_z": z, "previous_z": current_height,
                        "blockers": capsule_blockers(world, [xy[0], xy[1], z]) if z is not None else []})
                continue
            # Check between cell centers as well; a thin railing must not be
            # skipped simply because both ends happen to be clear.
            middle = [(current[0] + nxt[0]) * spacing * .5,
                      (current[1] + nxt[1]) * spacing * .5]
            if ground_clear(middle, current_height) is None:
                blocked.add(nxt)
                if nxt[1] == 0 and -32 <= nxt[0] <= 25:
                    z = ground_height(middle)
                    blocked_diagnostics.append({"xy": xy, "midpoint": middle, "support_z": z,
                        "previous_z": current_height, "blockers": capsule_blockers(world, middle + [z]) if z is not None else []})
                continue
            visited.add(nxt)
            queue.append(nxt)
    unreachable = [name for name in goals if name not in reached]
    return {"passed": not unreachable, "grid_spacing_cm": spacing,
            "reachable_entries": reached, "unreachable": unreachable,
            "visited_cells": len(visited), "blocked_cells": len(blocked), "blocked_diagnostics": blocked_diagnostics}
