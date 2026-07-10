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
MATERIAL_FOLDER = "/Game/MainHome/Materials"
GENERATOR_TAG = "MainHome_Enterable"
FOLDER_NAME = "MainHome_Enterable"

MATERIAL_ORDER = [
    "M_MainHome_Wall",
    "M_MainHome_Interior",
    "M_MainHome_Floor",
    "M_MainHome_Sign",
    "M_MainHome_Trim",
    "M_MainHome_Letters",
    "M_MainHome_Stain",
]
MATERIAL_ID_BY_NAME = {
    name: index for index, name in enumerate(MATERIAL_ORDER)
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


def build_box_specs():
    structure = [
        ("Floor", (0, 0, 5), (500, 800, 10)),
        ("Wall_Left", (-240, 10, 180), (20, 780, 340)),
        ("Wall_Right", (240, 10, 180), (20, 780, 340)),
        ("Wall_Back", (0, 390, 180), (460, 20, 340)),
        ("RoofSlab", (0, 0, 358), (500, 800, 16)),
        ("FrontPillar_Left", (-234, -388, 180), (32, 16, 340)),
        ("FrontPillar_Center", (0, -388, 180), (44, 16, 340)),
        ("FrontPillar_Right", (234, -388, 180), (32, 16, 340)),
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
            (0, -397, 322),
            (460, 2, 64),
            "M_MainHome_Sign",
            "sign",
        ),
        (
            "SignTrim_Top",
            (0, -399, 356),
            (468, 2, 4),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "SignTrim_Bottom",
            (0, -399, 288),
            (468, 2, 4),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "SignTrim_Left",
            (-232, -399, 322),
            (4, 2, 64),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "SignTrim_Right",
            (232, -399, 322),
            (4, 2, 64),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "PillarTrim_LeftOuter",
            (-218, -397, 150),
            (4, 2, 280),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "PillarTrim_CenterLeft",
            (-22, -397, 150),
            (4, 2, 280),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "PillarTrim_CenterRight",
            (22, -397, 150),
            (4, 2, 280),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "PillarTrim_RightOuter",
            (218, -397, 150),
            (4, 2, 280),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "Threshold_Left",
            (-120, -399, 11),
            (196, 2, 2),
            "M_MainHome_Trim",
            "trim",
        ),
        (
            "Threshold_Right",
            (120, -399, 11),
            (196, 2, 2),
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
            (0, -398.5, 29),
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


def build_doorway_specs():
    return [
        DoorwaySpec(
            "Door_Left",
            (-218.0, -400.0, 11.0),
            (-22.0, -350.0, 291.0),
        ),
        DoorwaySpec(
            "Door_Right",
            (22.0, -400.0, 11.0),
            (218.0, -350.0, 291.0),
        ),
    ]


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


def validate_design(boxes):
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
