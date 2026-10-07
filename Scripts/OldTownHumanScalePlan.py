"""Pure data proposal for a 180 cm tall, 50 cm wide visual human reference.

Baseline is the saved eight-part furniture manifest before this revision.
This module neither imports Unreal/Blender nor reads or changes project assets.
All tuples use Blender author-space XYZ centimetres; UE conversion remains
X, -Y, Z. Scale geometry and assembly offsets together for multipart groups.
"""
HUMAN = {"height_cm": 180.0, "shoulder_width_cm": 50.0}
VALIDATION_CAPSULE = {"height_cm": 180.0, "radius_cm": 34.0, "diameter_cm": 68.0}
GROUP_SCALES = {
    "Bed": (1.15, 1.05, 1.0),
    "Table": (150.0 / 121.8, 90.0 / 78.0, 80.0 / 76.0),
    "Chair": (52.0 / 43.0, 52.0 / 42.3, None),
    "Wardrobe": (140.0 / 121.0, 70.0 / 61.85, 200.0 / 192.0),
}
# The chair seat remains at adult sitting height while its back becomes taller.
CHAIR_Z = {"source_seat_top_cm": 47.0, "target_seat_top_cm": 48.0,
           "source_back_top_cm": 92.0, "target_back_top_cm": 100.0}
BASELINE = (
    ("BedFrame", "Bed", (135.6, 213.6, 97.5), (0.0, 0.0, 0.0)),
    ("BedMattress", "Bed", (120.0, 198.0, 15.0), (0.0, 0.0, 44.0)),
    ("BedPillow", "Bed", (58.0, 37.0, 10.9738), (0.0, 69.0, 59.0)),
    ("OldWoodTable", "Table", (121.8, 78.0, 76.0), (0.0, 0.0, 0.0)),
    ("OldWoodChair", "Chair", (43.0, 42.3, 92.0), (0.0, 0.0, 0.0)),
    ("WardrobeCase", "Wardrobe", (121.0, 61.85, 192.0), (0.0, 0.0, 0.0)),
    ("WardrobeDoorL", "Wardrobe", (56.0, 7.45, 170.8), (-55.8, -33.0, 16.0)),
    ("WardrobeDoorR", "Wardrobe", (56.0, 7.45, 170.8), (55.8, -33.0, 16.0)),
)
PLACEMENT = {
    "wall_margin_cm": 40.0,
    "room_main_route_clear_width_cm": 120.0,
    "chair_pullback_clearance_cm": 85.0,
    "wardrobe_front_clearance_cm": 100.0,
    "bedside_clearance_cm": 85.0,
    "alley_min_clear_width_after_props_cm": 180.0,
    "alley_review_target_clear_width_cm": (240.0, 260.0),
    "human_eye_height_cm": 165.0,
    "comparison_camera_horizontal_fov_degrees": 60.0,
}


def chair_height(source_z_cm):
    seat = CHAIR_Z["source_seat_top_cm"]
    new_seat = CHAIR_Z["target_seat_top_cm"]
    if source_z_cm <= seat:
        return source_z_cm * new_seat / seat
    return new_seat + (source_z_cm - seat) * (
        (CHAIR_Z["target_back_top_cm"] - new_seat) /
        (CHAIR_Z["source_back_top_cm"] - seat))


def transform_point(group, point):
    scale = GROUP_SCALES[group]
    return (point[0] * scale[0], point[1] * scale[1],
            chair_height(point[2]) if group == "Chair" else point[2] * scale[2])


def target_parts():
    return [{"name": "SM_OTS_Blender_" + name, "group": group,
             "source_dimensions_cm": dimensions,
             "target_dimensions_cm": transform_point(group, dimensions),
             "source_offset_cm": offset,
             "target_offset_cm": transform_point(group, offset),
             "scale_xyz": GROUP_SCALES[group],
             "z_policy": "seat_48_back_100_piecewise" if group == "Chair" else "linear_about_support_or_hinge"}
            for name, group, dimensions, offset in BASELINE]


if __name__ == "__main__":
    import json
    print(json.dumps({"human": HUMAN, "validation_capsule": VALIDATION_CAPSULE,
                      "parts": target_parts(), "placement": PLACEMENT}, indent=2))
