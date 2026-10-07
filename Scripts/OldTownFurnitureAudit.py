"""Check real mesh bounds against furniture supports and the customer aisle."""

import itertools
import math


FLOOR_Z = 10.0
TOP_Z = FLOOR_Z + 79.5 * 1.25
LOWER_Z = FLOOR_Z + 25.75 * 1.25
SUPPORTS = {
    "OTS_P5Prop_MainHomeShopShelf": (FLOOR_Z, (795, 1240, 1180, 1300)),
    "OTS_P5Prop_MainHomeTallPharmacyCabinet": (FLOOR_Z, (1180, 1240, 1255, 1300)),
    "OTS_P5Prop_MainHomeCounterDisplayLeft": (TOP_Z, (873.18, 1166.65, 1022.82, 1223.35)),
    "OTS_P5Prop_MainHomeCounterDisplayRight": (TOP_Z, (1027.18, 1166.65, 1176.82, 1223.35)),
    "OTS_MainHomeProp_Thermos": (TOP_Z, (873.18, 1166.65, 1022.82, 1223.35)),
    "OTS_MainHomeProp_CounterBoxLeft": (LOWER_Z, (883.5, 1174.8, 1012.5, 1215.2)),
    "OTS_MainHomeProp_CounterBoxRight": (LOWER_Z, (1037.5, 1174.8, 1166.5, 1215.2)),
    "OTS_MainHomeProp_Toolbox": (LOWER_Z, (883.5, 1174.8, 1012.5, 1215.2)),
}


def world_bounds(local_min, local_max, location, scale, yaw):
    angle = math.radians(yaw)
    c, s = math.cos(angle), math.sin(angle)
    points = []
    for x, y, z in itertools.product(*zip(local_min, local_max)):
        x, y, z = x * scale[0], y * scale[1], z * scale[2]
        points.append((location[0] + c*x - s*y,
                       location[1] + s*x + c*y, location[2] + z))
    return tuple(min(p[i] for p in points) for i in range(3)), tuple(
        max(p[i] for p in points) for i in range(3))


def validate_bounds(bounds):
    """Reject floating/overhanging furniture and overlapping loose objects."""
    report = {}
    for label, (support_z, footprint) in SUPPORTS.items():
        if label not in bounds:
            raise ValueError("Missing furniture: " + label)
        lo, hi = bounds[label]
        gap = lo[2] - support_z
        if not -0.65 <= gap <= 0.35:
            raise ValueError("{} support gap {:.3f} cm".format(label, gap))
        xmin, ymin, xmax, ymax = footprint
        if not (lo[0] >= xmin-0.5 and lo[1] >= ymin-0.5
                and hi[0] <= xmax+0.5 and hi[1] <= ymax+0.5):
            raise ValueError("{} overhangs support: {} {}".format(label, lo, hi))
        report[label] = {"min": lo, "max": hi, "support_gap_cm": round(gap, 3)}
    for left, right in itertools.combinations(SUPPORTS, 2):
        a, b = bounds[left], bounds[right]
        overlap = [min(a[1][i], b[1][i])-max(a[0][i], b[0][i]) for i in range(3)]
        if all(d > 0.2 for d in overlap):
            raise ValueError("Furniture overlaps: {} / {}".format(left, right))
    return report


def audit_actors(actors):
    import unreal
    bounds = {}
    for actor in actors:
        label = actor.get_actor_label()
        # Scene placements use unique_label(prefix), including a _01 suffix.
        if label.endswith("_01"):
            label = label[:-3]
        if label not in SUPPORTS:
            continue
        if label in bounds:
            raise ValueError("Duplicate furniture: " + label)
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        lo, hi = component.get_local_bounds()
        pos, scale = actor.get_actor_location(), actor.get_actor_scale3d()
        rot = actor.get_actor_rotation()
        if abs(rot.pitch) > 0.01 or abs(rot.roll) > 0.01:
            raise ValueError("Unsupported furniture tilt: " + label)
        xyz = lambda v: (float(v.x), float(v.y), float(v.z))
        bounds[label] = world_bounds(xyz(lo), xyz(hi), xyz(pos), xyz(scale), rot.yaw)
    return validate_bounds(bounds)


def validate_end_window_bounds(bounds):
    ends = [name for name in bounds if name.startswith((
        "OTS_StreetEndWindow_North_01", "OTS_StreetEndWindow_South_01"))]
    if len(ends) != 2:
        raise ValueError("Expected both street-end windows")
    backdrop = [name for name in bounds if name.startswith("OTS_PerimeterWindow")]
    if not backdrop:
        raise ValueError("Missing backdrop windows")
    for end in ends:
        a = bounds[end]
        for name in backdrop:
            b = bounds[name]
            if all(min(a[1][i], b[1][i]) - max(a[0][i], b[0][i]) > 0.2 for i in range(3)):
                raise ValueError("Facade windows overlap: {} / {}".format(end, name))
    return {"end_windows": ends, "backdrop_windows_checked": len(backdrop), "overlaps": 0}


def audit_end_windows(actors):
    import unreal
    bounds = {}
    xyz = lambda v: (float(v.x), float(v.y), float(v.z))
    for actor in actors:
        label = actor.get_actor_label()
        if not label.startswith(("OTS_StreetEndWindow_North_01", "OTS_StreetEndWindow_South_01", "OTS_PerimeterWindow")):
            continue
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        lo, hi = component.get_local_bounds()
        bounds[label] = world_bounds(xyz(lo), xyz(hi), xyz(actor.get_actor_location()),
                                    xyz(actor.get_actor_scale3d()), actor.get_actor_rotation().yaw)
    return validate_end_window_bounds(bounds)
