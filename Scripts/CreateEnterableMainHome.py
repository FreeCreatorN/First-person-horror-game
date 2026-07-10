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
INSTANCE_LABEL = "SM_MainHome_Enterable_Instance"

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
MATERIAL_SETTINGS = {
    "M_MainHome_Wall": ((0.36, 0.31, 0.23, 1.0), 0.94),
    "M_MainHome_Interior": ((0.16, 0.145, 0.12, 1.0), 0.92),
    "M_MainHome_Floor": ((0.20, 0.18, 0.15, 1.0), 0.96),
    "M_MainHome_Sign": ((0.38, 0.29, 0.20, 1.0), 0.90),
    "M_MainHome_Trim": ((0.10, 0.085, 0.07, 1.0), 0.91),
    "M_MainHome_Letters": ((0.30, 0.07, 0.045, 1.0), 0.88),
    "M_MainHome_Stain": ((0.22, 0.18, 0.14, 1.0), 0.96),
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


def _require_unreal():
    if unreal is None:
        raise RuntimeError("This generator must run inside Unreal Editor")


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


def _create_dynamic_mesh(boxes):
    _require_unreal()
    dynamic_mesh = unreal.DynamicMesh()
    unreal.GeometryScript_Materials.enable_material_ids(dynamic_mesh)

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
    validate_design(boxes)
    return _create_dynamic_mesh(boxes)


def create_collision_dynamic_mesh(boxes=None):
    boxes = build_box_specs() if boxes is None else list(boxes)
    validate_design(boxes)
    return _create_dynamic_mesh(box for box in boxes if box.collision)


def ensure_material(material_name, color=None, roughness=None):
    _require_unreal()
    if material_name not in MATERIAL_SETTINGS:
        raise ValueError("Unknown material {!r}".format(material_name))

    default_color, default_roughness = MATERIAL_SETTINGS[material_name]
    color = default_color if color is None else tuple(color)
    roughness = default_roughness if roughness is None else float(roughness)
    asset_path = "{}/{}".format(MATERIAL_FOLDER, material_name)
    material = unreal.EditorAssetLibrary.load_asset(asset_path)

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
    editing.delete_all_material_expressions(material)

    color_node = editing.create_material_expression(
        material,
        unreal.MaterialExpressionConstant3Vector,
        -300,
        -50,
    )
    roughness_node = editing.create_material_expression(
        material,
        unreal.MaterialExpressionConstant,
        -300,
        100,
    )
    if color_node is None or roughness_node is None:
        raise RuntimeError(
            "Unable to create material expressions for {}".format(asset_path)
        )

    color_node.set_editor_property("constant", unreal.LinearColor(*color))
    roughness_node.set_editor_property("r", roughness)
    if not editing.connect_material_property(
        color_node,
        "",
        unreal.MaterialProperty.MP_BASE_COLOR,
    ):
        raise RuntimeError("Unable to connect Base Color for {}".format(asset_path))
    if not editing.connect_material_property(
        roughness_node,
        "",
        unreal.MaterialProperty.MP_ROUGHNESS,
    ):
        raise RuntimeError("Unable to connect Roughness for {}".format(asset_path))

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
        raise ValueError("Exactly seven ordered materials are required")
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


def create_or_update_static_mesh(visual_mesh, materials=None):
    _require_unreal()
    materials = _ordered_materials(materials)
    static_mesh = unreal.EditorAssetLibrary.load_asset(STATIC_MESH_ASSET_PATH)

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
                STATIC_MESH_ASSET_PATH,
                create_options,
            )
        )
        static_mesh = _normalize_geometry_script_result(
            result,
            "create_new_static_mesh_asset_from_mesh",
        )

    _copy_visual_mesh_to_static_mesh(visual_mesh, static_mesh, materials)
    return static_mesh


def apply_structural_collision(collision_mesh, static_mesh):
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
            "Unable to save static mesh {}".format(STATIC_MESH_ASSET_PATH)
        )
    return static_mesh


def _has_exact_generator_tag(actor):
    tags = actor.get_editor_property("tags") or []
    return any(str(tag) == GENERATOR_TAG for tag in tags)


def place_single_instance(static_mesh):
    _require_unreal()
    if static_mesh is None:
        raise ValueError("A valid Static Mesh is required for level placement")

    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    if actor_subsystem is None:
        raise RuntimeError("EditorActorSubsystem is unavailable")

    tagged_actors = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if _has_exact_generator_tag(actor)
    ]
    first_actor = tagged_actors[0] if tagged_actors else None

    for extra_actor in tagged_actors[1:]:
        if not actor_subsystem.destroy_actor(extra_actor):
            raise RuntimeError(
                "Unable to remove an extra {} actor".format(GENERATOR_TAG)
            )

    actor = None
    component = None
    if first_actor is not None and isinstance(
        first_actor, unreal.StaticMeshActor
    ):
        component = first_actor.get_component_by_class(
            unreal.StaticMeshComponent
        )
        if component is not None:
            actor = first_actor

    if first_actor is not None and actor is None:
        if not actor_subsystem.destroy_actor(first_actor):
            raise RuntimeError(
                "Unable to replace an invalid {} actor".format(GENERATOR_TAG)
            )

    if actor is None:
        actor = actor_subsystem.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(0.0, 0.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
        )
        if actor is None:
            raise RuntimeError("Unable to spawn the Main Home StaticMeshActor")
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
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
    component.set_static_mesh(static_mesh)
    component.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS
    )
    actor_subsystem.set_selected_level_actors([actor])
    return actor


def generate_enterable_main_home():
    boxes = build_box_specs()
    validate_design(boxes)
    _require_unreal()

    materials = [ensure_material(name) for name in MATERIAL_ORDER]
    visual_mesh = create_visual_dynamic_mesh(boxes)
    collision_mesh = create_collision_dynamic_mesh(boxes)
    static_mesh = create_or_update_static_mesh(visual_mesh, materials)
    static_mesh = apply_structural_collision(collision_mesh, static_mesh)
    actor = place_single_instance(static_mesh)

    bounds = overall_bounds(boxes)
    collision_box_count = sum(1 for box in boxes if box.collision)
    unreal.log("Main Home asset: {}".format(STATIC_MESH_ASSET_PATH))
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
