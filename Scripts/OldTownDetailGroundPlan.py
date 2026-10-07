"""Data-only partitioning of the existing street paving in UE centimeters.

No Unreal imports, file access, or scene mutations occur here.  Rendering code
must honor ``material_group`` (including on Name_PartNN fragments).  Original
walking-strip expectations remain in the report for independent world checks;
a small paving fragment is not evidence of a full-width public corridor.
"""
from copy import deepcopy
import itertools
import math


EPSILON = 1e-8
_ASPHALT_NAMES = {"MainRoad", "WestCrossRoad", "EastCrossRoad"}
_PRIORITY = {
    "WestCrossRoad": 0, "EastCrossRoad": 1, "MainRoad": 2,
    "MainWalkNorth": 10, "MainWalkSouth": 11,
    "RearLaneNorth": 12, "RearLaneSouth": 13,
    "SchoolCourtyard": 0,
    "SchoolOuterWalkNorth": 10, "SchoolOuterWalkSouth": 11,
    "SchoolOuterWalkWest": 12,
}


def material_group(surface):
    """Return the existing visible material, without depending on fragment names."""
    for key in ("material_group", "material_key", "material"):
        value = surface.get(key)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise ValueError("Material identity must be a nonempty string")
            return value
    name = surface.get("source_surface_name", surface["name"])
    return "asphalt" if name in _ASPHALT_NAMES else "concrete"


def _rect(value):
    if len(value) != 4 or not all(math.isfinite(float(v)) for v in value):
        raise ValueError("Expected a finite [xmin, ymin, xmax, ymax] rectangle")
    result = [float(v) for v in value]
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError("Paving rectangles must have positive area")
    return result


def _intersection(a, b):
    result = [max(a[0], b[0]), max(a[1], b[1]),
              min(a[2], b[2]), min(a[3], b[3])]
    return result if result[2] - result[0] > EPSILON and result[3] - result[1] > EPSILON else None


def _area(rect):
    return (rect[2] - rect[0]) * (rect[3] - rect[1])


def _subtract(rect, cutter):
    """Exact rectangular difference, with disjoint interiors in the result."""
    overlap = _intersection(rect, cutter)
    if overlap is None:
        return [rect]
    x0, y0, x1, y1 = rect
    a, b, c, d = overlap
    candidates = ([x0, y0, x1, b], [x0, d, x1, y1],
                  [x0, b, a, d], [c, b, x1, d])
    return [list(r) for r in candidates
            if r[2] - r[0] > EPSILON and r[3] - r[1] > EPSILON]


def _merge(rectangles):
    """Merge complete shared edges only; never replace an L shape by its AABB."""
    result = sorted(rectangles)
    while True:
        merged = False
        for i, a in enumerate(result):
            for j in range(i + 1, len(result)):
                b = result[j]
                same_y = a[1] == b[1] and a[3] == b[3]
                same_x = a[0] == b[0] and a[2] == b[2]
                if ((same_y and (a[2] == b[0] or b[2] == a[0]))
                        or (same_x and (a[3] == b[1] or b[3] == a[1]))):
                    replacement = [min(a[0], b[0]), min(a[1], b[1]),
                                   max(a[2], b[2]), max(a[3], b[3])]
                    result = sorted([r for k, r in enumerate(result) if k not in (i, j)] + [replacement])
                    merged = True
                    break
            if merged:
                break
        if not merged:
            return result


def _covered(point, rectangles):
    return any(r[0] < point[0] < r[2] and r[1] < point[1] < r[3] for r in rectangles)


def _set_comparison(before, after):
    """Measure both set differences on the joint edge arrangement.

    Every rectangle edge partitions the plane into cells of constant coverage.
    Testing each cell therefore proves equality of the covered interiors, not
    merely equality of total areas.  Shared boundaries are checked separately
    by exact endpoint construction and never count as positive-area overlap.
    """
    all_rectangles = before + after
    xs = sorted({r[i] for r in all_rectangles for i in (0, 2)})
    ys = sorted({r[i] for r in all_rectangles for i in (1, 3)})
    old_area = new_area = lost = gained = 0.0
    differences = []
    cells = 0
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            point = ((x0 + x1) * .5, (y0 + y1) * .5)
            old, new = _covered(point, before), _covered(point, after)
            cell_area = (x1 - x0) * (y1 - y0)
            cells += 1
            old_area += cell_area if old else 0.0
            new_area += cell_area if new else 0.0
            lost += cell_area if old and not new else 0.0
            gained += cell_area if new and not old else 0.0
            if old != new:
                differences.append({"rect_xy": [x0, y0, x1, y1], "was_covered": old,
                                    "is_covered": new, "area_cm2": cell_area})
    return {"original_union_area_cm2": old_area, "updated_union_area_cm2": new_area,
            "lost_coverage_area_cm2": lost, "added_coverage_area_cm2": gained,
            "symmetric_difference_area_cm2": lost + gained,
            "edge_arrangement_cell_count": cells, "coverage_difference_cells": differences}


def _overlaps(surfaces):
    rows = []
    for a, b in itertools.combinations(surfaces, 2):
        if a["surface_z_cm"] != b["surface_z_cm"]:
            continue
        overlap = _intersection(a["rect_xy"], b["rect_xy"])
        if overlap is not None:
            rows.append({"surfaces": [a["name"], b["name"]],
                         "surface_z_cm": a["surface_z_cm"], "rect_xy": overlap,
                         "area_cm2": _area(overlap)})
    return rows


def _corridor(surface):
    if "target_clear_width_cm" not in surface:
        return None
    clear = _rect(surface.get("clear_rect_xy", surface["rect_xy"]))
    width = float(surface["target_clear_width_cm"])
    if not math.isfinite(width) or width <= 0:
        raise ValueError("Corridor widths must be positive")
    spans = [clear[i + 2] - clear[i] for i in (0, 1)]
    axis = int(surface.get("width_axis", min((0, 1), key=lambda i: abs(spans[i] - width))))
    if axis not in (0, 1):
        raise ValueError("width_axis must be 0 or 1")
    return {"name": surface["name"], "rect_xy": list(surface["rect_xy"]),
            "clear_rect_xy": clear, "surface_z_cm": float(surface["surface_z_cm"]),
            "material_group": material_group(surface), "target_clear_width_cm": width,
            "width_axis": axis, "requires_actual_collision_validation": True}


def _fragment(surface, rect, name):
    row = deepcopy(surface)
    row.update(name=name, source_surface_name=surface.get("source_surface_name", surface["name"]),
               material_group=material_group(surface), rect_xy=list(rect))
    row["world_min"] = [rect[0], rect[1], float(surface["world_min"][2])]
    row["world_max"] = [rect[2], rect[3], float(surface["world_max"][2])]
    if "actor" in row:
        old_name = surface["name"]
        if row["actor"].endswith(old_name):
            row["actor"] = row["actor"][:-len(old_name)] + name
        else:
            row.pop("actor")
    old_clear = surface.get("clear_rect_xy")
    clipped_clear = _intersection(rect, _rect(old_clear)) if old_clear is not None else list(rect)
    if clipped_clear is None:
        row.pop("clear_rect_xy", None)
    elif old_clear is not None:
        row["clear_rect_xy"] = clipped_clear
    corridor = _corridor(surface)
    retained = None
    if corridor is not None:
        axis = corridor["width_axis"]
        retained = (clipped_clear is not None
                    and clipped_clear[axis + 2] - clipped_clear[axis] + EPSILON >= corridor["target_clear_width_cm"]
                    and clipped_clear[3-axis] - clipped_clear[1-axis] >= 74.)
        if retained:
            row["width_axis"] = axis
        else:
            row.pop("target_clear_width_cm", None)
            row.pop("width_axis", None)
            row["paving_fragment_only"] = True
    return row, retained


def normalize_ground_surfaces(plan):
    """Return disjoint visible slabs and independently measured set equality.

    Ramps are copied byte-for-byte as data.  Slab heights, thicknesses and
    material-group unions are preserved.  Input ``plan`` is never mutated.
    Exact input corridor expectations are recorded as virtual walking strips;
    callers must validate those strips against the actual resulting world.
    """
    originals = deepcopy(plan["ground_surfaces"])
    names = [row["name"] for row in originals]
    if len(names) != len(set(names)):
        raise ValueError("Ground surface names must be unique")
    slabs = [row for row in originals if row.get("kind") == "slab"]
    for row in slabs:
        row["rect_xy"] = _rect(row["rect_xy"])
        row["surface_z_cm"] = float(row["surface_z_cm"])
        if not math.isfinite(row["surface_z_cm"]):
            raise ValueError("Slab top height must be finite")
        if abs(float(row["world_max"][2]) - row["surface_z_cm"]) > EPSILON:
            raise ValueError("Slab world bounds and top height disagree: " + row["name"])
        if float(row["world_min"][2]) >= row["surface_z_cm"]:
            raise ValueError("Slab must have positive thickness: " + row["name"])
    original_overlaps = _overlaps(slabs)
    by_name = {row["name"]: row for row in slabs}
    for pair in original_overlaps:
        a, b = (by_name[n] for n in pair["surfaces"])
        if material_group(a) != material_group(b):
            raise ValueError("Overlapping different materials cannot both retain their original union: "
                             + ", ".join(pair["surfaces"]))
    groups = {}
    for row in slabs:
        groups.setdefault((row["surface_z_cm"], material_group(row)), []).append(row)
    emitted = []
    group_reports = []
    mapping = []
    virtual_corridors = [c for row in slabs if (c := _corridor(row)) is not None]
    for (top, material), members in sorted(groups.items()):
        # Ownership order provides stable useful names, then exact subtraction
        # partitions their union.  Campus coverage is thus one deterministic
        # partition, even when old virtual walk strips are wholly absorbed.
        ordered = sorted(members, key=lambda r: (_PRIORITY.get(r["name"], 100), r["name"]))
        owned = []
        group_emitted = []
        for source in ordered:
            parts = [list(source["rect_xy"])]
            for cutter in owned:
                parts = [piece for rect in parts for piece in _subtract(rect, cutter)]
            parts = _merge(parts)
            outputs = []
            for index, rect in enumerate(parts, 1):
                name = source["name"] if len(parts) == 1 else source["name"] + "_Part{:02d}".format(index)
                row, corridor_retained = _fragment(source, rect, name)
                outputs.append({"name": name, "rect_xy": rect,
                                "physical_fragment_retains_clear_width": corridor_retained})
                group_emitted.append(row)
            owned.extend(parts)
            mapping.append({"source_name": source["name"], "source_rect_xy": source["rect_xy"],
                            "output_fragments": outputs,
                            "covered_by_other_group_surfaces": not bool(parts)})
        comparison = _set_comparison([r["rect_xy"] for r in members],
                                    [r["rect_xy"] for r in group_emitted])
        if comparison["coverage_difference_cells"]:
            raise AssertionError("Paving partition changed its footprint")
        group_reports.append(dict(surface_z_cm=top, material_group=material,
                                  original_surface_count=len(members),
                                  updated_surface_count=len(group_emitted), **comparison))
        emitted.extend(group_emitted)
    final_overlaps = _overlaps(emitted)
    if final_overlaps:
        raise AssertionError("Paving partition still has positive-area coplanar overlap")
    output_names = [r["name"] for r in emitted]
    if len(output_names) != len(set(output_names)):
        raise ValueError("Fragment naming collided with an existing surface name")
    other = [deepcopy(r) for r in originals if r.get("kind") != "slab"]
    emitted.sort(key=lambda r: (r["surface_z_cm"], material_group(r), r["name"]))
    updated = emitted + other
    report = {
        "status": "PASS", "pure_plan": True, "input_surface_count": len(originals),
        "updated_surface_count": len(updated), "original_slab_count": len(slabs),
        "updated_slab_count": len(emitted), "original_overlap_pair_count": len(original_overlaps),
        "final_overlap_pair_count": len(final_overlaps), "original_overlap_pairs": original_overlaps,
        "final_overlap_pairs": final_overlaps, "groups": group_reports,
        "symmetric_difference_area_cm2": sum(g["symmetric_difference_area_cm2"] for g in group_reports),
        "source_surface_mapping": mapping, "original_virtual_corridors": virtual_corridors,
        "unchanged_non_slab_names": [r["name"] for r in other],
        "ramps_unchanged": other == [r for r in originals if r.get("kind") != "slab"],
        "physical_route_validation_required": True,
        "notes": [
            "Set equality was checked in both directions on every joint-edge arrangement cell.",
            "Shared edges have zero area; surface heights and original slab thicknesses are unchanged.",
            "Use material_group for rendering; split asphalt fragments retain their original asphalt identity.",
            "Original virtual walking strips remain validation obligations, even when covered by another named slab.",
            "Only fragments retaining the original across-axis clear width keep target_clear_width_cm.",
        ],
    }
    return updated, report
