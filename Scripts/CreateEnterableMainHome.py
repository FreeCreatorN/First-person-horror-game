from dataclasses import dataclass

try:
    import unreal
except ImportError:
    unreal = None


SHOP_WIDTH_CM = 500.0
SHOP_DEPTH_CM = 800.0
SHOP_HEIGHT_CM = 400.0
BASE_Z_CM = 1.0
STATIC_MESH_ASSET_PATH = "/Game/MainHome/SM_MainHome_Enterable"
SHUTTER_STATIC_MESH_ASSET_PATH = "/Game/MainHome/SM_MainHome_Shutter"
LEFT_DOOR_STATIC_MESH_ASSET_PATH = "/Game/MainHome/SM_MainHome_Door_Left"
RIGHT_DOOR_STATIC_MESH_ASSET_PATH = "/Game/MainHome/SM_MainHome_Door_Right"
MATERIAL_FOLDER = "/Game/MainHome/Materials"
GENERATOR_TAG = "MainHome_Interactive"
FOLDER_NAME = "MainHome_Enterable"
INSTANCE_LABEL = "SM_MainHome_Enterable_Instance"

FAB_TEXTURE_ASSET_PATHS = {
    "plaster": {
        "base_color": (
            "/Game/MainHome/Textures/"
            "T_Fab_ConstructionPlaster_BaseColor"
        ),
        "normal": (
            "/Game/MainHome/Textures/"
            "T_Fab_ConstructionPlaster_Normal"
        ),
        "roughness": (
            "/Game/MainHome/Textures/"
            "T_Fab_ConstructionPlaster_Roughness"
        ),
    },
    "metal": {
        "base_color": (
            "/Game/MainHome/Textures/"
            "T_Fab_RustyMetalSheet_BaseColor"
        ),
        "normal": (
            "/Game/MainHome/Textures/"
            "T_Fab_RustyMetalSheet_Normal"
        ),
        "roughness": (
            "/Game/MainHome/Textures/"
            "T_Fab_RustyMetalSheet_Roughness"
        ),
    },
}
FAB_NODE_DESCRIPTIONS = {
    "base_color": "MainHome_Fab_BaseColor",
    "normal": "MainHome_Fab_Normal",
    "roughness": "MainHome_Fab_Roughness",
    "tint": "MainHome_Fab_Tint",
    "multiply": "MainHome_Fab_TintMultiply",
}
FAB_FALLBACK_NODE_DESCRIPTIONS = {
    "normal": "MainHome_Fab_FallbackNormal",
    "roughness": "MainHome_Fab_FallbackRoughness",
}
PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS = {
    "world_position": "MainHome_Aged_WorldPosition",
    "noise": "MainHome_Aged_Noise",
    "aged_tint": "MainHome_Aged_DarkTint",
    "lerp": "MainHome_Aged_ColorLerp",
}
FAB_TEXTURE_SET_BY_MATERIAL = {
    "M_MainHome_Wall": "plaster",
    "M_MainHome_Sign": "plaster",
    "M_MainHome_FadedGreenMetal": "metal",
}
PROCEDURAL_FALLBACK_SETTINGS = {
    "M_MainHome_Wall": {
        "aged_color": (0.24, 0.20, 0.145, 1.0),
        "noise_size_cm": 110.0,
        "noise_quality": 2,
        "noise_levels": 3,
        "noise_min": 0.06,
        "noise_max": 0.38,
        "roughness": 0.96,
    },
    "M_MainHome_Sign": {
        "aged_color": (0.205, 0.145, 0.085, 1.0),
        "noise_size_cm": 82.0,
        "noise_quality": 2,
        "noise_levels": 3,
        "noise_min": 0.08,
        "noise_max": 0.42,
        "roughness": 0.95,
    },
    "M_MainHome_FadedGreenMetal": {
        "aged_color": (0.23, 0.105, 0.045, 1.0),
        "noise_size_cm": 24.0,
        "noise_quality": 1,
        "noise_levels": 3,
        "noise_min": 0.02,
        "noise_max": 0.48,
        "roughness": 0.91,
    },
}

SHUTTER_PIVOT_CM = (-96.0, -394.5, 277.0)
SHUTTER_OPEN_SCALE_Z = 0.04
FRAME_UNDERLAP_CM = 1.0
LEFT_HINGE_CM = (76.0, -394.0, 121.0)
RIGHT_HINGE_CM = (212.0, -394.0, 121.0)
DOOR_CENTER_GAP_CM = 0.5
DOOR_VISIBLE_SPAN_CM = (
    RIGHT_HINGE_CM[0]
    - LEFT_HINGE_CM[0]
    - DOOR_CENTER_GAP_CM
) / 2.0
DOOR_PANEL_WIDTH_CM = DOOR_VISIBLE_SPAN_CM + FRAME_UNDERLAP_CM
DOOR_PANEL_HEIGHT_CM = 214.0

MATERIAL_ORDER = [
    "M_MainHome_Wall",
    "M_MainHome_Interior",
    "M_MainHome_Floor",
    "M_MainHome_Sign",
    "M_MainHome_Trim",
    "M_MainHome_Letters",
    "M_MainHome_Stain",
    "M_MainHome_FadedGreenMetal",
    "M_MainHome_DarkGlass",
]
MATERIAL_ID_BY_NAME = {
    name: index for index, name in enumerate(MATERIAL_ORDER)
}
MATERIAL_SETTINGS = {
    "M_MainHome_Wall": ((0.46, 0.39, 0.29, 1.0), 0.94),
    "M_MainHome_Interior": ((0.16, 0.145, 0.12, 1.0), 0.92),
    "M_MainHome_Floor": ((0.20, 0.18, 0.15, 1.0), 0.96),
    "M_MainHome_Sign": ((0.40, 0.32, 0.23, 1.0), 0.92),
    "M_MainHome_Trim": ((0.10, 0.085, 0.07, 1.0), 0.91),
    "M_MainHome_Letters": ((0.30, 0.07, 0.045, 1.0), 0.88),
    "M_MainHome_Stain": ((0.24, 0.19, 0.145, 1.0), 0.97),
    "M_MainHome_FadedGreenMetal": ((0.20, 0.30, 0.21, 1.0), 0.88),
    "M_MainHome_DarkGlass": ((0.025, 0.04, 0.035, 1.0), 0.18),
}

DESIGN_BOUNDS = (
    (-SHOP_WIDTH_CM / 2.0, SHOP_WIDTH_CM / 2.0),
    (-SHOP_DEPTH_CM / 2.0, SHOP_DEPTH_CM / 2.0),
    (BASE_Z_CM, BASE_Z_CM + SHOP_HEIGHT_CM),
)


@dataclass(frozen=True)
class BoxSpec:
    label: str
    location_cm: tuple
    size_cm: tuple
    material_name: str
    category: str
    collision: bool = False


@dataclass(frozen=True)
class DoorwaySpec:
    label: str
    minimum_cm: tuple
    maximum_cm: tuple

    @property
    def width_cm(self):
        return self.maximum_cm[0] - self.minimum_cm[0]

    @property
    def height_cm(self):
        return self.maximum_cm[2] - self.minimum_cm[2]


@dataclass(frozen=True)
class ActorRelativeTransform:
    location_cm: tuple
    rotation_degrees: tuple = (0.0, 0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0)


@dataclass(frozen=True)
class MeshAssetDefinition:
    asset_path: str
    visual_boxes: tuple
    collision_boxes: tuple
    actor_relative_transform: ActorRelativeTransform
    fixed: bool


OPENING_BOUNDS = (
    DoorwaySpec(
        "ShutterOpening",
        (-220.0, -400.0, 11.0),
        (28.0, -350.0, 291.0),
    ),
    DoorwaySpec(
        "DoubleDoorOpening",
        (68.0, -400.0, 11.0),
        (220.0, -350.0, 291.0),
    ),
)


_LETTER_BITMAPS = (
    (
        "大",
        (
            "000010000",
            "000010000",
            "000010000",
            "111111111",
            "000111000",
            "000101000",
            "001010100",
            "010010010",
            "100010001",
        ),
    ),
    (
        "众",
        (
            "000010000",
            "000111000",
            "001010100",
            "010010010",
            "100000001",
            "001010100",
            "000111000",
            "001010100",
            "010000010",
        ),
    ),
    (
        "小",
        (
            "000010000",
            "000010000",
            "000010000",
            "010010010",
            "010010010",
            "010010010",
            "100010001",
            "000010000",
            "000110000",
        ),
    ),
    (
        "卖",
        (
            "000010000",
            "111111111",
            "000010000",
            "001111100",
            "000001000",
            "111111111",
            "000010000",
            "001010100",
            "110000011",
        ),
    ),
    (
        "部",
        (
            "001111010",
            "000100111",
            "111111101",
            "001010101",
            "001111101",
            "001010101",
            "111110101",
            "001010110",
            "001010100",
        ),
    ),
)


def _local_box(
    label,
    location_cm,
    size_cm,
    material_name,
    category,
    collision=False,
):
    x_cm, y_cm, z_cm = location_cm
    return BoxSpec(
        label=label,
        location_cm=(float(x_cm), float(y_cm), float(z_cm) + BASE_Z_CM),
        size_cm=tuple(float(value) for value in size_cm),
        material_name=material_name,
        category=category,
        collision=collision,
    )


def _pivot_box(
    label,
    location_cm,
    size_cm,
    material_name,
    category,
    collision=False,
):
    return BoxSpec(
        label=label,
        location_cm=tuple(float(value) for value in location_cm),
        size_cm=tuple(float(value) for value in size_cm),
        material_name=material_name,
        category=category,
        collision=collision,
    )


def _horizontal_runs(row_bits):
    run_start = None
    for index, bit in enumerate(row_bits + "0"):
        if bit == "1" and run_start is None:
            run_start = index
        elif bit == "0" and run_start is not None:
            yield run_start, index
            run_start = None


def _build_letter_boxes():
    cell_width_cm = 7.0
    cell_height_cm = 5.0
    glyph_width_cm = 9.0 * cell_width_cm
    glyph_gap_cm = 12.0
    total_width_cm = (
        len(_LETTER_BITMAPS) * glyph_width_cm
        + (len(_LETTER_BITMAPS) - 1) * glyph_gap_cm
    )
    first_glyph_left_cm = -total_width_cm / 2.0
    bottom_local_z_cm = 299.0
    boxes = []

    for glyph_index, (_character, rows) in enumerate(_LETTER_BITMAPS):
        glyph_left_cm = first_glyph_left_cm + glyph_index * (
            glyph_width_cm + glyph_gap_cm
        )
        for row_index, row_bits in enumerate(rows):
            row_from_bottom = len(rows) - row_index - 1
            center_z_cm = bottom_local_z_cm + (
                row_from_bottom + 0.5
            ) * cell_height_cm
            for run_index, (run_start, run_end) in enumerate(
                _horizontal_runs(row_bits)
            ):
                width_cm = (run_end - run_start) * cell_width_cm
                center_x_cm = glyph_left_cm + (
                    (run_start + run_end) / 2.0
                ) * cell_width_cm
                boxes.append(
                    _local_box(
                        "Letter_{:02d}_Row_{:02d}_Run_{:02d}".format(
                            glyph_index, row_index, run_index
                        ),
                        (center_x_cm, -398.6, center_z_cm),
                        (width_cm, 1.2, cell_height_cm),
                        "M_MainHome_Letters",
                        "letter",
                    )
                )

    return boxes


def build_shell_box_specs():
    structure = [
        ("Floor", (0, 0, 5), (500, 800, 10)),
        ("Wall_Left", (-239.25, 10, 180), (18.5, 780, 340)),
        ("Wall_Right", (239.25, 10, 180), (18.5, 780, 340)),
        ("Wall_Back", (0, 390, 180), (460, 20, 340)),
        ("RoofSlab", (0, 0, 358), (500, 800, 16)),
        ("FrontPillar_Left", (-235, -388, 150), (30, 16, 280)),
        ("FrontPillar_Between", (48, -388, 150), (40, 16, 280)),
        ("FrontPillar_Right", (235, -388, 150), (30, 16, 280)),
        ("FrontLintel", (0, -388, 320), (500, 16, 60)),
        ("Parapet_Front", (0, -391, 383), (500, 18, 34)),
        ("Parapet_Back", (0, 391, 383), (500, 18, 34)),
        ("Parapet_Left", (-241, 0, 383), (18, 764, 34)),
        ("Parapet_Right", (241, 0, 383), (18, 764, 34)),
    ]
    boxes = []
    for label, location_cm, size_cm in structure:
        material_name = (
            "M_MainHome_Floor" if label == "Floor" else "M_MainHome_Wall"
        )
        boxes.append(
            _local_box(
                label,
                location_cm,
                size_cm,
                material_name,
                "structure",
                collision=True,
            )
        )

    fixed_frame = [
        ("ShutterFrame_Threshold", (-96, -398, 12), (248, 4, 4), "M_MainHome_FadedGreenMetal"),
        ("ShutterFrame_LeftGuide", (-216, -398, 140), (8, 4, 252), "M_MainHome_FadedGreenMetal"),
        ("ShutterFrame_RightGuide", (24, -398, 140), (8, 4, 252), "M_MainHome_FadedGreenMetal"),
        ("ShutterFrame_TopBox", (-96, -398, 283), (248, 4, 14), "M_MainHome_FadedGreenMetal"),
        ("DoorFrame_Threshold", (144, -398, 12), (152, 4, 4), "M_MainHome_FadedGreenMetal"),
        ("DoorFrame_Left", (72, -398, 147), (8, 4, 266), "M_MainHome_FadedGreenMetal"),
        ("DoorFrame_Right", (216, -398, 147), (8, 4, 266), "M_MainHome_FadedGreenMetal"),
        ("DoorFrame_Top", (144, -398, 285), (152, 4, 10), "M_MainHome_FadedGreenMetal"),
        ("DoorTransom_Bar", (144, -398, 231), (136, 4, 10), "M_MainHome_FadedGreenMetal"),
        ("DoorTransom_Glass", (144, -393, 258), (138, 1, 46), "M_MainHome_DarkGlass"),
    ]
    boxes.extend(
        _local_box(
            label,
            location_cm,
            size_cm,
            material_name,
            "frame",
            collision=True,
        )
        for label, location_cm, size_cm, material_name in fixed_frame
    )

    lining = [
        ("Interior_Left", (-229.5, 0, 180), (1, 760, 340)),
        ("Interior_Right", (229.5, 0, 180), (1, 760, 340)),
        ("Interior_Back", (0, 379.5, 180), (460, 1, 340)),
        ("Interior_Ceiling", (0, 0, 349.5), (460, 760, 1)),
    ]
    boxes.extend(
        _local_box(
            label,
            location_cm,
            size_cm,
            "M_MainHome_Interior",
            "lining",
        )
        for label, location_cm, size_cm in lining
    )

    decorations = [
        (
            "Sign_Panel",
            (0, -397, 318),
            (460, 2, 56),
            "M_MainHome_Sign",
            "sign",
        ),
        (
            "SignTrim_Top",
            (0, -399, 347.5),
            (468, 2, 3),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "SignTrim_Bottom",
            (0, -399, 292),
            (468, 2, 4),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "SignTrim_Left",
            (-232, -399, 320),
            (4, 2, 52),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "SignTrim_Right",
            (232, -399, 320),
            (4, 2, 52),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "PillarTrim_LeftOuter",
            (-223, -397, 150),
            (4, 2, 280),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "PillarTrim_CenterLeft",
            (31, -397, 150),
            (4, 2, 280),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "PillarTrim_CenterRight",
            (65, -397, 150),
            (4, 2, 280),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "PillarTrim_RightOuter",
            (223, -397, 150),
            (4, 2, 280),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "Stain_Pillar_Left",
            (-234, -398.5, 38),
            (22, 1, 30),
            "M_MainHome_Stain",
            "stain",
        ),
        (
            "Stain_Pillar_Center",
            (48, -398.5, 29),
            (30, 1, 16),
            "M_MainHome_Stain",
            "stain",
        ),
        (
            "Stain_Pillar_Right",
            (234, -398.5, 45),
            (18, 1, 34),
            "M_MainHome_Stain",
            "stain",
        ),
        (
            "Stain_Sign_Left",
            (-210, -398.5, 302),
            (24, 1, 12),
            "M_MainHome_Stain",
            "stain",
        ),
        (
            "Stain_Sign_Right",
            (210, -398.5, 338),
            (18, 1, 10),
            "M_MainHome_Stain",
            "stain",
        ),
        (
            "Side_Stain_Lower",
            (249.5, 180, 55),
            (1, 110, 55),
            "M_MainHome_Stain",
            "side_detail",
        ),
        (
            "Side_Drainpipe",
            (249.5, 330, 170),
            (1, 8, 300),
            "M_MainHome_Trim",
            "side_detail",
        ),
        (
            "Side_ElectricBox",
            (249.5, 270, 175),
            (1, 36, 44),
            "M_MainHome_FadedGreenMetal",
            "side_detail",
        ),
    ]
    boxes.extend(
        _local_box(
            label,
            location_cm,
            size_cm,
            material_name,
            category,
        )
        for label, location_cm, size_cm, material_name, category in decorations
    )
    boxes.extend(_build_letter_boxes())
    return boxes


def build_shutter_box_specs():
    boxes = [
        _pivot_box(
            "Shutter_Panel",
            (0.0, 1.5, -131.5),
            (234.0, 3.0, 263.0),
            "M_MainHome_FadedGreenMetal",
            "shutter",
            collision=True,
        )
    ]
    boxes.extend(
        _pivot_box(
            "Shutter_Slat_{:02d}".format(index),
            (0.0, -1.0, float(z_cm)),
            (226.0, 1.0, 1.0),
            "M_MainHome_Trim",
            "shutter_detail",
        )
        for index, z_cm in enumerate(range(-245, -6, 14))
    )
    boxes.append(
        _pivot_box(
            "Shutter_BottomRail",
            (0.0, -1.0, -257.0),
            (230.0, 1.0, 8.0),
            "M_MainHome_Trim",
            "shutter_detail",
        )
    )
    return boxes


def build_left_door_box_specs():
    visible_center_x = DOOR_VISIBLE_SPAN_CM / 2.0
    panel_center_x = (
        DOOR_VISIBLE_SPAN_CM - FRAME_UNDERLAP_CM
    ) / 2.0
    return [
        _pivot_box(
            "Door_Left_Panel",
            (panel_center_x, 0.0, 0.0),
            (DOOR_PANEL_WIDTH_CM, 3.0, DOOR_PANEL_HEIGHT_CM),
            "M_MainHome_FadedGreenMetal",
            "door_leaf",
            collision=True,
        ),
        _pivot_box(
            "Door_Left_GlassInset",
            (visible_center_x, -2.5, 30.0),
            (51.0, 1.0, 90.0),
            "M_MainHome_DarkGlass",
            "door_detail",
        ),
        _pivot_box(
            "Door_Left_LowerInset",
            (visible_center_x, -2.5, -62.5),
            (51.0, 1.0, 65.0),
            "M_MainHome_FadedGreenMetal",
            "door_detail",
        ),
        _pivot_box(
            "Door_Left_CenterStile",
            (DOOR_VISIBLE_SPAN_CM - 2.0, -2.5, 0.0),
            (4.0, 1.0, 210.0),
            "M_MainHome_FadedGreenMetal",
            "door_detail",
        ),
        _pivot_box(
            "Door_Left_Handle",
            (62.0, -3.5, 4.0),
            (2.0, 3.0, 24.0),
            "M_MainHome_Trim",
            "door_handle",
        ),
    ]


def build_right_door_box_specs():
    visible_center_x = DOOR_VISIBLE_SPAN_CM / 2.0
    panel_center_x = (
        DOOR_VISIBLE_SPAN_CM - FRAME_UNDERLAP_CM
    ) / 2.0
    return [
        _pivot_box(
            "Door_Right_Panel",
            (-panel_center_x, 0.0, 0.0),
            (DOOR_PANEL_WIDTH_CM, 3.0, DOOR_PANEL_HEIGHT_CM),
            "M_MainHome_FadedGreenMetal",
            "door_leaf",
            collision=True,
        ),
        _pivot_box(
            "Door_Right_GlassInset",
            (-visible_center_x, -2.5, 30.0),
            (51.0, 1.0, 90.0),
            "M_MainHome_DarkGlass",
            "door_detail",
        ),
        _pivot_box(
            "Door_Right_LowerInset",
            (-visible_center_x, -2.5, -62.5),
            (51.0, 1.0, 65.0),
            "M_MainHome_FadedGreenMetal",
            "door_detail",
        ),
        _pivot_box(
            "Door_Right_CenterStile",
            (-DOOR_VISIBLE_SPAN_CM + 2.0, -2.5, 0.0),
            (4.0, 1.0, 210.0),
            "M_MainHome_FadedGreenMetal",
            "door_detail",
        ),
        _pivot_box(
            "Door_Right_Handle",
            (-62.0, -3.5, 4.0),
            (2.0, 3.0, 24.0),
            "M_MainHome_Trim",
            "door_handle",
        ),
    ]


def _asset_definition(asset_path, boxes, location_cm, fixed):
    boxes = tuple(boxes)
    return MeshAssetDefinition(
        asset_path=asset_path,
        visual_boxes=boxes,
        collision_boxes=tuple(box for box in boxes if box.collision),
        actor_relative_transform=ActorRelativeTransform(
            location_cm=tuple(float(value) for value in location_cm)
        ),
        fixed=bool(fixed),
    )


MESH_ASSET_DEFINITIONS = (
    _asset_definition(
        STATIC_MESH_ASSET_PATH,
        build_shell_box_specs(),
        (0.0, 0.0, 0.0),
        True,
    ),
    _asset_definition(
        SHUTTER_STATIC_MESH_ASSET_PATH,
        build_shutter_box_specs(),
        SHUTTER_PIVOT_CM,
        False,
    ),
    _asset_definition(
        LEFT_DOOR_STATIC_MESH_ASSET_PATH,
        build_left_door_box_specs(),
        LEFT_HINGE_CM,
        False,
    ),
    _asset_definition(
        RIGHT_DOOR_STATIC_MESH_ASSET_PATH,
        build_right_door_box_specs(),
        RIGHT_HINGE_CM,
        False,
    ),
)


def _translated_box(box, translation_cm):
    return BoxSpec(
        label=box.label,
        location_cm=tuple(
            coordinate_cm + offset_cm
            for coordinate_cm, offset_cm in zip(
                box.location_cm, translation_cm
            )
        ),
        size_cm=box.size_cm,
        material_name=box.material_name,
        category=box.category,
        collision=box.collision,
    )


def build_box_specs():
    return [
        _translated_box(
            box,
            definition.actor_relative_transform.location_cm,
        )
        for definition in MESH_ASSET_DEFINITIONS
        for box in definition.visual_boxes
    ]


def build_doorway_specs():
    return list(OPENING_BOUNDS)


def box_bounds(box):
    return tuple(
        (
            float(center_cm) - float(size_cm) / 2.0,
            float(center_cm) + float(size_cm) / 2.0,
        )
        for center_cm, size_cm in zip(box.location_cm, box.size_cm)
    )


def overall_bounds(boxes):
    boxes = list(boxes)
    if not boxes:
        raise ValueError("Cannot calculate bounds for an empty design")

    bounds = [box_bounds(box) for box in boxes]
    return tuple(
        (
            min(box_bound[axis][0] for box_bound in bounds),
            max(box_bound[axis][1] for box_bound in bounds),
        )
        for axis in range(3)
    )


def point_inside_box(point_cm, box):
    return all(
        minimum_cm < coordinate_cm < maximum_cm
        for coordinate_cm, (minimum_cm, maximum_cm) in zip(
            point_cm, box_bounds(box)
        )
    )


def boxes_overlap_open_volume(box, open_volume):
    return all(
        max(box_axis[0], volume_minimum_cm)
        < min(box_axis[1], volume_maximum_cm)
        for box_axis, volume_minimum_cm, volume_maximum_cm in zip(
            box_bounds(box), open_volume.minimum_cm, open_volume.maximum_cm
        )
    )


def validate_boxes(boxes):
    boxes = list(boxes)
    labels = [box.label for box in boxes]
    if len(labels) != len(set(labels)):
        raise ValueError("Box labels must be unique")

    for box in boxes:
        if box.material_name not in MATERIAL_ID_BY_NAME:
            raise ValueError(
                "Unknown material {!r} on {!r}".format(
                    box.material_name, box.label
                )
            )
        if any(float(size_cm) <= 0.0 for size_cm in box.size_cm):
            raise ValueError("Box {!r} has a non-positive size".format(box.label))

    return boxes


def validate_design(boxes):
    boxes = validate_boxes(boxes)

    for box in boxes:
        for axis, ((minimum_cm, maximum_cm), allowed_bounds) in enumerate(
            zip(box_bounds(box), DESIGN_BOUNDS)
        ):
            if (
                minimum_cm < allowed_bounds[0]
                or maximum_cm > allowed_bounds[1]
            ):
                raise ValueError(
                    "Box {!r} exceeds the design envelope on axis {}".format(
                        box.label, axis
                    )
                )

    doorways = build_doorway_specs()
    for box in boxes:
        if box.category != "structure":
            continue
        for doorway in doorways:
            if boxes_overlap_open_volume(box, doorway):
                raise ValueError(
                    "Structure {!r} intersects doorway {!r}".format(
                        box.label, doorway.label
                    )
                )


def _require_unreal():
    if unreal is None:
        raise RuntimeError("This generator must run inside Unreal Editor")


def _load_asset_if_exists(asset_path):
    _require_unreal()
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return None
    return unreal.EditorAssetLibrary.load_asset(asset_path)


def load_fab_texture_sets(asset_exists=None, load_asset=None) -> dict:
    if asset_exists is None or load_asset is None:
        _require_unreal()
    if asset_exists is None:
        asset_exists = unreal.EditorAssetLibrary.does_asset_exist
    if load_asset is None:
        load_asset = unreal.EditorAssetLibrary.load_asset

    texture_sets = {}
    missing_paths = []
    for set_name, asset_paths in FAB_TEXTURE_ASSET_PATHS.items():
        availability = {
            map_name: bool(asset_exists(asset_path))
            for map_name, asset_path in asset_paths.items()
        }
        missing_paths.extend(
            asset_paths[map_name]
            for map_name, exists in availability.items()
            if not exists
        )
        if not all(availability.values()):
            continue

        loaded_set = {
            map_name: load_asset(asset_path)
            for map_name, asset_path in asset_paths.items()
        }
        unloaded_paths = [
            asset_paths[map_name]
            for map_name, asset in loaded_set.items()
            if asset is None
        ]
        if unloaded_paths:
            missing_paths.extend(unloaded_paths)
            continue
        texture_sets[set_name] = loaded_set

    if missing_paths:
        log_warning = getattr(unreal, "log_warning", None)
        if callable(log_warning):
            log_warning(
                "Main Home Fab textures missing; using aged fallback: {}".format(
                    ", ".join(dict.fromkeys(missing_paths))
                )
            )
    return texture_sets


def make_transform(location_cm):
    _require_unreal()
    return unreal.Transform(
        location=unreal.Vector(*location_cm),
        rotation=unreal.Rotator(0.0, 0.0, 0.0),
        scale=unreal.Vector(1.0, 1.0, 1.0),
    )


def primitive_options_for(material_id):
    _require_unreal()
    options = unreal.GeometryScriptPrimitiveOptions()
    options.set_editor_property("material_id", int(material_id))
    return options


def _enable_material_ids(dynamic_mesh):
    material_library = getattr(unreal, "GeometryScript_Materials", None)
    for method_name in ("enable_material_i_ds", "enable_material_ids"):
        enable = getattr(material_library, method_name, None)
        if callable(enable):
            enable(dynamic_mesh)
            return

    for method_name in ("enable_material_i_ds", "enable_material_ids"):
        enable = getattr(dynamic_mesh, method_name, None)
        if callable(enable):
            enable()
            return

    raise RuntimeError(
        "Unreal Geometry Script does not expose a material ID enable API "
        "(expected enable_material_i_ds or enable_material_ids)"
    )


def _create_dynamic_mesh(boxes):
    _require_unreal()
    dynamic_mesh = unreal.DynamicMesh()
    _enable_material_ids(dynamic_mesh)

    for box in boxes:
        result = unreal.GeometryScript_Primitives.append_box(
            dynamic_mesh,
            primitive_options_for(MATERIAL_ID_BY_NAME[box.material_name]),
            make_transform(box.location_cm),
            box.size_cm[0],
            box.size_cm[1],
            box.size_cm[2],
            0,
            0,
            0,
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        if isinstance(result, tuple):
            result = result[0]
        if result is not None:
            dynamic_mesh = result

    return dynamic_mesh


def create_visual_dynamic_mesh(boxes=None):
    boxes = build_box_specs() if boxes is None else list(boxes)
    validate_boxes(boxes)
    return _create_dynamic_mesh(boxes)


def create_collision_dynamic_mesh(boxes=None):
    boxes = build_box_specs() if boxes is None else list(boxes)
    validate_boxes(boxes)
    return _create_dynamic_mesh(box for box in boxes if box.collision)


def _expression_description(expression):
    get_editor_property = getattr(expression, "get_editor_property", None)
    if callable(get_editor_property):
        try:
            return get_editor_property("desc") or ""
        except Exception:
            pass
    return getattr(expression, "desc", "") or ""


def _set_expression_description(expression, description):
    expression.set_editor_property("desc", description)


def _material_expressions(material):
    editing = unreal.MaterialEditingLibrary
    get_all_expressions = getattr(
        editing,
        "get_all_expressions_in_material",
        None,
    )
    if callable(get_all_expressions):
        expressions = list(get_all_expressions(material))
        if expressions:
            return expressions

    get_editor_property = getattr(material, "get_editor_property", None)
    if callable(get_editor_property):
        try:
            editor_only_data = get_editor_property("editor_only_data")
            collection = editor_only_data.get_editor_property(
                "expression_collection"
            )
            expressions = list(
                collection.get_editor_property("expressions")
            )
            if expressions:
                return expressions
        except Exception:
            pass
        try:
            collection = get_editor_property("expression_collection")
            collection_get_editor_property = getattr(
                collection,
                "get_editor_property",
                None,
            )
            if callable(collection_get_editor_property):
                expressions = list(
                    collection_get_editor_property("expressions")
                )
            else:
                expressions = list(getattr(collection, "expressions", ()))
            if expressions:
                return expressions
        except Exception:
            pass
        try:
            expressions = list(get_editor_property("expressions"))
            if expressions:
                return expressions
        except Exception:
            pass

    iterator_type = getattr(unreal, "ObjectIterator", None)
    expression_type = getattr(unreal, "MaterialExpression", None)
    if callable(iterator_type) and expression_type is not None:
        try:
            return [
                expression
                for expression in iterator_type(expression_type)
                if callable(getattr(expression, "get_outer", None))
                and expression.get_outer() is material
            ]
        except Exception:
            pass
    return []


def _find_tagged_expression(expressions, expression_type, description):
    return next(
        (
            expression
            for expression in expressions
            if isinstance(expression, expression_type)
            and _expression_description(expression) == description
        ),
        None,
    )


def _find_or_create_tagged_expression(
    material,
    expressions,
    expression_type,
    description,
    node_position,
    preferred=None,
):
    matching = [
        expression
        for expression in expressions
        if _expression_description(expression) == description
    ]
    if isinstance(preferred, expression_type):
        expression = preferred
    else:
        expression = next(
            (
                candidate
                for candidate in matching
                if isinstance(candidate, expression_type)
            ),
            None,
        )
    if expression is None:
        expression = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            expression_type,
            node_position[0],
            node_position[1],
        )
        if expression is None:
            raise RuntimeError(
                "Unable to create tagged material expression {}".format(
                    description
                )
            )
        expressions.append(expression)

    for duplicate in matching:
        if duplicate is not expression:
            _set_expression_description(
                duplicate,
                "{}_Duplicate".format(description),
            )
    _set_expression_description(expression, description)
    if expression not in expressions:
        expressions.append(expression)
    return expression


def _complete_texture_set_for_material(material_name, texture_sets):
    set_name = FAB_TEXTURE_SET_BY_MATERIAL.get(material_name)
    if set_name is None or texture_sets is None:
        return None
    texture_set = texture_sets.get(set_name)
    required_maps = FAB_TEXTURE_ASSET_PATHS[set_name]
    if not isinstance(texture_set, dict) or any(
        texture_set.get(map_name) is None for map_name in required_maps
    ):
        return None
    return texture_set


def _connect_expression(
    source,
    output_name,
    target,
    input_name,
    connection_name,
):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source,
        output_name,
        target,
        input_name,
    ):
        raise RuntimeError(
            "Unable to connect material expressions for {}".format(
                connection_name
            )
        )


def _connect_material_property(node, output_name, material_property, name):
    if not unreal.MaterialEditingLibrary.connect_material_property(
        node,
        output_name,
        material_property,
    ):
        raise RuntimeError("Unable to connect material property {}".format(name))


def _connect_procedural_fallback_color(
    material,
    expressions,
    tint_node,
    material_name,
):
    settings = PROCEDURAL_FALLBACK_SETTINGS.get(material_name)
    if settings is None:
        return tint_node

    descriptions = PROCEDURAL_FALLBACK_NODE_DESCRIPTIONS
    world_position_node = _find_or_create_tagged_expression(
        material,
        expressions,
        unreal.MaterialExpressionWorldPosition,
        descriptions["world_position"],
        (-1000, -450),
    )
    noise_node = _find_or_create_tagged_expression(
        material,
        expressions,
        unreal.MaterialExpressionNoise,
        descriptions["noise"],
        (-750, -450),
    )
    aged_tint_node = _find_or_create_tagged_expression(
        material,
        expressions,
        unreal.MaterialExpressionConstant3Vector,
        descriptions["aged_tint"],
        (-600, -50),
    )
    lerp_node = _find_or_create_tagged_expression(
        material,
        expressions,
        unreal.MaterialExpressionLinearInterpolate,
        descriptions["lerp"],
        (-300, -200),
    )

    aged_tint_node.set_editor_property(
        "constant",
        unreal.LinearColor(*settings["aged_color"]),
    )
    for property_name, value in (
        ("scale", 1.0 / settings["noise_size_cm"]),
        ("quality", settings["noise_quality"]),
        ("levels", settings["noise_levels"]),
        ("output_min", settings["noise_min"]),
        ("output_max", settings["noise_max"]),
    ):
        noise_node.set_editor_property(property_name, value)

    _connect_expression(
        world_position_node,
        "",
        noise_node,
        "World Position",
        "Procedural world position for {}".format(material_name),
    )
    _connect_expression(
        tint_node,
        "",
        lerp_node,
        "A",
        "Procedural base tint for {}".format(material_name),
    )
    _connect_expression(
        aged_tint_node,
        "",
        lerp_node,
        "B",
        "Procedural aged tint for {}".format(material_name),
    )
    _connect_expression(
        noise_node,
        "",
        lerp_node,
        "Alpha",
        "Procedural age mask for {}".format(material_name),
    )
    return lerp_node


def ensure_material(
    material_name,
    color=None,
    roughness=None,
    texture_sets=None,
):
    _require_unreal()
    if material_name not in MATERIAL_SETTINGS:
        raise ValueError("Unknown material {!r}".format(material_name))

    default_color, default_roughness = MATERIAL_SETTINGS[material_name]
    procedural_settings = PROCEDURAL_FALLBACK_SETTINGS.get(material_name)
    color = default_color if color is None else tuple(color)
    if roughness is None:
        roughness = (
            procedural_settings["roughness"]
            if procedural_settings is not None
            else default_roughness
        )
    else:
        roughness = float(roughness)
    asset_path = "{}/{}".format(MATERIAL_FOLDER, material_name)
    material = _load_asset_if_exists(asset_path)

    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            material_name,
            MATERIAL_FOLDER,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
    if material is None:
        raise RuntimeError("Unable to create material {}".format(asset_path))

    editing = unreal.MaterialEditingLibrary

    current_color_node = editing.get_material_property_input_node(
        material,
        unreal.MaterialProperty.MP_BASE_COLOR,
    )
    current_roughness_node = editing.get_material_property_input_node(
        material,
        unreal.MaterialProperty.MP_ROUGHNESS,
    )

    expressions = _material_expressions(material)
    tint_node = _find_or_create_tagged_expression(
        material,
        expressions,
        unreal.MaterialExpressionConstant3Vector,
        FAB_NODE_DESCRIPTIONS["tint"],
        (-600, -250),
        preferred=current_color_node,
    )
    fallback_roughness_node = _find_or_create_tagged_expression(
        material,
        expressions,
        unreal.MaterialExpressionConstant,
        FAB_FALLBACK_NODE_DESCRIPTIONS["roughness"],
        (-600, 250),
        preferred=current_roughness_node,
    )
    tint_node.set_editor_property("constant", unreal.LinearColor(*color))
    fallback_roughness_node.set_editor_property("r", roughness)

    texture_set = _complete_texture_set_for_material(
        material_name,
        texture_sets,
    )
    texture_sample_type = getattr(
        unreal,
        "MaterialExpressionTextureSample",
        (),
    )
    existing_fab_normal_node = _find_tagged_expression(
        expressions,
        texture_sample_type,
        FAB_NODE_DESCRIPTIONS["normal"],
    )
    fallback_normal_node = None
    if texture_set is not None or existing_fab_normal_node is not None:
        fallback_normal_node = _find_or_create_tagged_expression(
            material,
            expressions,
            unreal.MaterialExpressionConstant3Vector,
            FAB_FALLBACK_NODE_DESCRIPTIONS["normal"],
            (-600, 100),
        )
        fallback_normal_node.set_editor_property(
            "constant",
            unreal.LinearColor(0.0, 0.0, 1.0, 1.0),
        )

    if texture_set is None:
        fallback_color_node = _connect_procedural_fallback_color(
            material,
            expressions,
            tint_node,
            material_name,
        )
        if current_color_node is not fallback_color_node:
            _connect_material_property(
                fallback_color_node,
                "",
                unreal.MaterialProperty.MP_BASE_COLOR,
                "Base Color fallback for {}".format(asset_path),
            )
        if current_roughness_node is not fallback_roughness_node:
            _connect_material_property(
                fallback_roughness_node,
                "",
                unreal.MaterialProperty.MP_ROUGHNESS,
                "Roughness fallback for {}".format(asset_path),
            )
        if existing_fab_normal_node is not None:
            _connect_material_property(
                fallback_normal_node,
                "",
                unreal.MaterialProperty.MP_NORMAL,
                "Normal fallback for {}".format(asset_path),
            )
    else:
        base_color_node = _find_or_create_tagged_expression(
            material,
            expressions,
            unreal.MaterialExpressionTextureSample,
            FAB_NODE_DESCRIPTIONS["base_color"],
            (-900, -150),
        )
        normal_node = _find_or_create_tagged_expression(
            material,
            expressions,
            unreal.MaterialExpressionTextureSample,
            FAB_NODE_DESCRIPTIONS["normal"],
            (-900, 50),
        )
        roughness_node = _find_or_create_tagged_expression(
            material,
            expressions,
            unreal.MaterialExpressionTextureSample,
            FAB_NODE_DESCRIPTIONS["roughness"],
            (-900, 250),
        )
        multiply_node = _find_or_create_tagged_expression(
            material,
            expressions,
            unreal.MaterialExpressionMultiply,
            FAB_NODE_DESCRIPTIONS["multiply"],
            (-350, -150),
        )

        base_color_node.set_editor_property(
            "texture",
            texture_set["base_color"],
        )
        normal_node.set_editor_property("texture", texture_set["normal"])
        normal_node.set_editor_property(
            "sampler_type",
            unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
        )
        roughness_node.set_editor_property(
            "texture",
            texture_set["roughness"],
        )

        _connect_expression(
            base_color_node,
            "RGB",
            multiply_node,
            "A",
            "Fab Base Color",
        )
        _connect_expression(
            tint_node,
            "",
            multiply_node,
            "B",
            "Fab Tint",
        )
        _connect_material_property(
            multiply_node,
            "",
            unreal.MaterialProperty.MP_BASE_COLOR,
            "Fab Base Color for {}".format(asset_path),
        )
        _connect_material_property(
            normal_node,
            "RGB",
            unreal.MaterialProperty.MP_NORMAL,
            "Fab Normal for {}".format(asset_path),
        )
        _connect_material_property(
            roughness_node,
            "R",
            unreal.MaterialProperty.MP_ROUGHNESS,
            "Fab Roughness for {}".format(asset_path),
        )

    editing.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
        raise RuntimeError("Unable to save material {}".format(asset_path))
    return material


def _ordered_materials(materials):
    if materials is None:
        return [ensure_material(name) for name in MATERIAL_ORDER]
    if isinstance(materials, dict):
        ordered = [materials[name] for name in MATERIAL_ORDER]
    else:
        ordered = list(materials)
    if len(ordered) != len(MATERIAL_ORDER):
        raise ValueError(
            "Exactly {} ordered materials are required".format(
                len(MATERIAL_ORDER)
            )
        )
    return ordered


def _normalize_geometry_script_result(result, operation_name):
    if isinstance(result, tuple):
        value = result[0] if result else None
        if len(result) > 1:
            outcome = result[1]
            if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
                raise RuntimeError("{} failed: {}".format(operation_name, outcome))
    else:
        value = result

    if value is None:
        raise RuntimeError("{} did not return an asset".format(operation_name))
    return value


def _copy_visual_mesh_to_static_mesh(visual_mesh, static_mesh, materials):
    copy_options = unreal.GeometryScriptCopyMeshToAssetOptions()
    copy_options.set_editor_property("enable_recompute_normals", True)
    copy_options.set_editor_property("enable_recompute_tangents", True)
    copy_options.set_editor_property("replace_materials", True)
    copy_options.set_editor_property("new_materials", materials)
    copy_options.set_editor_property(
        "new_material_slot_names",
        [unreal.Name(name) for name in MATERIAL_ORDER],
    )

    target_lod = unreal.GeometryScriptMeshWriteLOD()
    target_lod.set_editor_property("lod_index", 0)
    target_lod.set_editor_property("write_hi_res_source", False)
    result = unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
        visual_mesh,
        static_mesh,
        copy_options,
        target_lod,
    )
    _normalize_geometry_script_result(result, "copy_mesh_to_static_mesh")


def create_or_update_static_mesh(definition, materials=None):
    _require_unreal()
    materials = _ordered_materials(materials)
    validate_design(
        _translated_box(
            box,
            definition.actor_relative_transform.location_cm,
        )
        for box in definition.visual_boxes
    )
    visual_mesh = create_visual_dynamic_mesh(definition.visual_boxes)
    collision_mesh = create_collision_dynamic_mesh(definition.collision_boxes)
    static_mesh = _load_asset_if_exists(definition.asset_path)

    if static_mesh is None:
        create_options = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        create_options.set_editor_property("enable_recompute_normals", True)
        create_options.set_editor_property("enable_recompute_tangents", True)
        create_options.set_editor_property("enable_nanite", False)
        create_options.set_editor_property("enable_collision", False)
        result = (
            unreal.GeometryScript_NewAssetUtils
            .create_new_static_mesh_asset_from_mesh(
                visual_mesh,
                definition.asset_path,
                create_options,
            )
        )
        static_mesh = _normalize_geometry_script_result(
            result,
            "create_new_static_mesh_asset_from_mesh",
        )

    _copy_visual_mesh_to_static_mesh(visual_mesh, static_mesh, materials)
    return apply_structural_collision(
        collision_mesh,
        static_mesh,
        definition.asset_path,
    )


def apply_structural_collision(collision_mesh, static_mesh, asset_path):
    _require_unreal()
    collision_options = unreal.GeometryScriptCollisionFromMeshOptions()
    collision_options.set_editor_property(
        "method",
        unreal.GeometryScriptCollisionGenerationMethod.ALIGNED_BOXES,
    )
    collision_options.set_editor_property("auto_detect_spheres", False)
    collision_options.set_editor_property("auto_detect_capsules", False)
    collision_options.set_editor_property("auto_detect_boxes", True)

    set_options = unreal.GeometryScriptSetStaticMeshCollisionOptions()
    set_options.set_editor_property("mark_as_customized", True)
    unreal.GeometryScript_Collision.set_static_mesh_collision_from_mesh(
        collision_mesh,
        static_mesh,
        collision_options,
        set_options,
    )

    if not unreal.EditorAssetLibrary.save_loaded_asset(static_mesh, False):
        raise RuntimeError(
            "Unable to save static mesh {}".format(asset_path)
        )
    return static_mesh


def _has_exact_generator_tag(actor):
    tags = actor.get_editor_property("tags") or []
    return any(str(tag) == GENERATOR_TAG for tag in tags)


def _placement_meshes(mesh_assets):
    if isinstance(mesh_assets, dict):
        return tuple(
            mesh_assets.get(asset_path)
            for asset_path in (
                STATIC_MESH_ASSET_PATH,
                SHUTTER_STATIC_MESH_ASSET_PATH,
                LEFT_DOOR_STATIC_MESH_ASSET_PATH,
                RIGHT_DOOR_STATIC_MESH_ASSET_PATH,
            )
        )
    return mesh_assets, None, None, None


def place_single_instance(mesh_assets):
    _require_unreal()
    fixed_shell, shutter, left_door, right_door = _placement_meshes(
        mesh_assets
    )
    if fixed_shell is None:
        raise ValueError("A valid Static Mesh is required for level placement")

    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    if actor_subsystem is None:
        raise RuntimeError("EditorActorSubsystem is unavailable")

    interactive_actor_class = getattr(
        unreal,
        "MainHomeInteractiveActor",
        None,
    )
    uses_interactive_actor = interactive_actor_class is not None
    if uses_interactive_actor and any(
        mesh is None for mesh in (shutter, left_door, right_door)
    ):
        raise ValueError(
            "All four Main Home meshes are required for interactive placement"
        )
    if not uses_interactive_actor:
        unreal.log_warning(
            "MainHomeInteractiveActor is unavailable; placing only the fixed "
            "Main Home shell as a StaticMeshActor"
        )

    desired_actor_class = (
        interactive_actor_class
        if uses_interactive_actor
        else unreal.StaticMeshActor
    )
    tagged_actors = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if _has_exact_generator_tag(actor)
    ]
    actor = None
    component = None
    for candidate_actor in tagged_actors:
        if not isinstance(candidate_actor, desired_actor_class):
            continue
        if uses_interactive_actor:
            if not callable(
                getattr(candidate_actor, "set_main_home_meshes", None)
            ):
                continue
            actor = candidate_actor
            break
        candidate_component = candidate_actor.get_component_by_class(
            unreal.StaticMeshComponent
        )
        if candidate_component is None:
            continue
        actor = candidate_actor
        component = candidate_component
        break

    for tagged_actor in tagged_actors:
        if tagged_actor is actor:
            continue
        if not actor_subsystem.destroy_actor(tagged_actor):
            raise RuntimeError(
                "Unable to remove a duplicate or invalid {} actor".format(
                    GENERATOR_TAG
                )
            )

    if actor is None:
        actor = actor_subsystem.spawn_actor_from_class(
            desired_actor_class,
            unreal.Vector(0.0, 0.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
        )
        if actor is None:
            raise RuntimeError(
                "Unable to spawn the Main Home {}".format(
                    desired_actor_class.__name__
                )
            )
        if not uses_interactive_actor:
            component = actor.get_component_by_class(
                unreal.StaticMeshComponent
            )
            if component is None:
                actor_subsystem.destroy_actor(actor)
                raise RuntimeError(
                    "Spawned Main Home actor has no StaticMeshComponent"
                )

    actor.set_actor_transform(
        make_transform((0.0, 0.0, 0.0)),
        False,
        False,
    )
    actor.set_actor_label(INSTANCE_LABEL)
    actor.set_folder_path(unreal.Name(FOLDER_NAME))
    actor.set_editor_property("tags", [unreal.Name(GENERATOR_TAG)])
    if uses_interactive_actor:
        actor.set_main_home_meshes(
            fixed_shell,
            shutter,
            left_door,
            right_door,
        )
    else:
        component.set_static_mesh(fixed_shell)
        component.set_editor_property(
            "mobility",
            unreal.ComponentMobility.STATIC,
        )
        component.set_collision_enabled(
            unreal.CollisionEnabled.QUERY_AND_PHYSICS
        )
    actor_subsystem.set_selected_level_actors([actor])
    return actor


def generate_enterable_main_home():
    boxes = build_box_specs()
    validate_design(boxes)
    _require_unreal()

    texture_sets = load_fab_texture_sets()
    materials = [
        ensure_material(name, texture_sets=texture_sets)
        for name in MATERIAL_ORDER
    ]
    static_meshes = {
        definition.asset_path: create_or_update_static_mesh(
            definition,
            materials,
        )
        for definition in MESH_ASSET_DEFINITIONS
    }
    static_mesh = static_meshes[STATIC_MESH_ASSET_PATH]
    actor = place_single_instance(static_meshes)

    bounds = overall_bounds(boxes)
    collision_box_count = sum(1 for box in boxes if box.collision)
    for definition in MESH_ASSET_DEFINITIONS:
        unreal.log("Main Home asset: {}".format(definition.asset_path))
    unreal.log("Main Home visual box count: {}".format(len(boxes)))
    unreal.log(
        "Main Home collision box count: {}".format(collision_box_count)
    )
    unreal.log("Main Home exact bounds: {}".format(bounds))
    for doorway in build_doorway_specs():
        unreal.log(
            "Main Home {} clearance: min={}, max={}, width={} cm, "
            "height={} cm".format(
                doorway.label,
                doorway.minimum_cm,
                doorway.maximum_cm,
                doorway.width_cm,
                doorway.height_cm,
            )
        )

    return static_mesh, actor


def main():
    try:
        return generate_enterable_main_home()
    except Exception as error:
        message = (
            "生成可进入式主屋失败：缺少所需的 Unreal 编辑器插件或 Python API。"
            "请启用 Python Editor Script Plugin、Editor Scripting Utilities 和 "
            "Geometry Script 后重试。错误：{}".format(error)
        )
        if unreal is None:
            print(message)
        else:
            unreal.log_error(message)
        raise


if __name__ == "__main__":
    main()
