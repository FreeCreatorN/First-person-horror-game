"""在 Unreal Editor 中用 Geometry Script / Dynamic Mesh 生成老城区街边小商铺。

默认整体尺寸：宽 500 cm、进深 800 cm、高 400 cm。
正面朝向：-Y。
底面高度：Z = 1 cm。
输出 Static Mesh Asset：
/Game/OldShop_500x800x400/SM_OldShop_500x800x400

运行方式：
1. 在 UE5 中启用内置的 Python Editor Script Plugin、
   Editor Scripting Utilities 和 Geometry Script 插件。
2. 打开目标关卡并退出 Play/Simulate。
3. 选择 Tools > Execute Python Script，然后选择本文件。
4. 脚本会创建/覆盖 Static Mesh Asset，并在当前关卡只放置一个实例 Actor。
5. 确认效果后手动保存关卡和资产。

重复执行会替换带 OldShop_500x800x400 Tag 的旧商铺实例，并重建 Static Mesh Asset。
脚本会保存材质和 Static Mesh 资产，但不会自动保存当前关卡。
"""

from dataclasses import dataclass

try:
    import unreal
except ImportError:
    unreal = None


# ============================================================================
# 可修改参数（UE5 单位均为 cm）
# ============================================================================

SHOP_WIDTH_CM = 500.0
SHOP_DEPTH_CM = 800.0
SHOP_HEIGHT_CM = 400.0

# 整体中心的 X/Y 坐标，以及建筑底面的 Z 坐标。
ORIGIN_X_CM = 0.0
ORIGIN_Y_CM = 0.0
BASE_Z_CM = 1.0

# 若修改整体尺寸，也可以同步修改 Folder 和 Tag 名称。
FOLDER_NAME = "OldShop_500x800x400"
GENERATOR_TAG = "OldShop_500x800x400"

CUBE_ASSET_PATH = "/Engine/BasicShapes/Cube.Cube"
MATERIAL_FOLDER = "/Game/OldShop_500x800x400/Materials"


# 设计基准。所有细节会跟随顶部整体尺寸按轴缩放。
BASE_WIDTH_CM = 500.0
BASE_DEPTH_CM = 800.0
BASE_HEIGHT_CM = 400.0
EPSILON = 1.0e-6


# 基础色材质，不使用贴图。
MATERIAL_COLORS = {
    "M_OldWall": (0.36, 0.31, 0.22, 1.0),
    "M_DarkWall": (0.18, 0.16, 0.13, 1.0),
    "M_Shutter": (0.22, 0.24, 0.23, 1.0),
    "M_Sign": (0.20, 0.055, 0.045, 1.0),
    "M_DarkGlass": (0.012, 0.020, 0.026, 1.0),
    "M_Trim": (0.045, 0.045, 0.040, 1.0),
    "M_Stain": (0.24, 0.20, 0.15, 1.0),
}


@dataclass(frozen=True)
class PartSpec:
    """一个由默认 100 cm Engine Cube 构成的商铺部件。"""

    label: str
    location_cm: tuple
    size_cm: tuple
    material_name: str
    enable_collision: bool = False

    @property
    def scale(self):
        """把实际 cm 尺寸转换成默认 Cube 的 Actor Scale。"""
        return tuple(value / 100.0 for value in self.size_cm)


def build_part_specs(
    width_cm=SHOP_WIDTH_CM,
    depth_cm=SHOP_DEPTH_CM,
    height_cm=SHOP_HEIGHT_CM,
    origin_x_cm=ORIGIN_X_CM,
    origin_y_cm=ORIGIN_Y_CM,
    base_z_cm=BASE_Z_CM,
):
    """创建全部部件的数据，不修改当前关卡。"""

    if min(width_cm, depth_cm, height_cm) <= 0.0:
        raise ValueError("商铺宽度、进深和高度必须大于 0 cm。")

    scale_x = width_cm / BASE_WIDTH_CM
    scale_y = depth_cm / BASE_DEPTH_CM
    scale_z = height_cm / BASE_HEIGHT_CM
    parts = []

    def add(label, base_location, base_size, material_name, enable_collision=False):
        location = (
            origin_x_cm + base_location[0] * scale_x,
            origin_y_cm + base_location[1] * scale_y,
            base_z_cm + base_location[2] * scale_z,
        )
        size = (
            base_size[0] * scale_x,
            base_size[1] * scale_y,
            base_size[2] * scale_z,
        )
        parts.append(
            PartSpec(label, location, size, material_name, enable_collision)
        )

    # 主体前表面为 Y=-380。主体进深缩短为 780 cm，为门面细节预留
    # Y=-400~-380 的 20 cm 空间，因此最终整体进深仍严格为 800 cm。
    # 主体左右各内退 2 cm，给侧墙贴片沿法线外移留下距离，避免与主体侧墙共面。
    add(
        "SM_OldShop_MainBlock",
        (0.0, 10.0, 200.0),
        (496.0, 780.0, 400.0),
        "M_OldWall",
        True,
    )
    add(
        "SM_OldShop_Storefront",
        (0.0, -384.0, 185.0),
        (480.0, 8.0, 370.0),
        "M_DarkWall",
    )

    # 屋顶女儿墙/边缘压条。它们都压在主体顶部 25 cm 内，不增加总高度。
    add(
        "SM_OldShop_RoofEdge_Front",
        (0.0, -393.0, 387.5),
        (500.0, 14.0, 25.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_RoofEdge_Back",
        (0.0, 390.0, 389.0),
        (500.0, 20.0, 22.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_RoofEdge_Left",
        (-242.0, -3.0, 387.5),
        (16.0, 766.0, 25.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_RoofEdge_Right",
        (242.0, -3.0, 387.5),
        (16.0, 766.0, 25.0),
        "M_Trim",
    )

    # 左侧卷帘门：240 × 4 × 240 cm。
    add(
        "SM_OldShop_Shutter",
        (-100.0, -390.0, 140.0),
        (240.0, 4.0, 240.0),
        "M_Shutter",
    )
    for index in range(15):
        add(
            f"SM_OldShop_Shutter_Slat_{index + 1:02d}",
            (-100.0, -394.5, 29.0 + index * 15.0),
            (232.0, 3.0, 4.0),
            "M_Trim",
        )

    # 右侧门板与三段门框。
    add(
        "SM_OldShop_Door",
        (155.0, -390.0, 117.5),
        (110.0, 4.0, 235.0),
        "M_DarkWall",
    )
    add(
        "SM_OldShop_DoorFrame_Left",
        (95.0, -395.0, 118.5),
        (8.0, 4.0, 235.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_DoorFrame_Right",
        (215.0, -395.0, 118.5),
        (8.0, 4.0, 235.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_DoorFrame_Top",
        (155.0, -395.0, 240.0),
        (112.0, 4.0, 8.0),
        "M_Trim",
    )

    # 褪色招牌，最前端恰好到达 Y=-400。
    add(
        "SM_OldShop_Sign",
        (0.0, -394.5, 325.5),
        (430.0, 8.0, 65.0),
        "M_Sign",
    )

    # 卷帘门与侧门之间的窄窗。
    add(
        "SM_OldShop_WindowGlass",
        (56.0, -390.0, 140.0),
        (50.0, 4.0, 90.0),
        "M_DarkGlass",
    )
    add(
        "SM_OldShop_WindowFrame_Left",
        (26.0, -395.0, 140.0),
        (6.0, 4.0, 90.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_WindowFrame_Right",
        (86.0, -395.0, 140.0),
        (6.0, 4.0, 90.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_WindowFrame_Top",
        (56.0, -395.0, 188.0),
        (54.0, 4.0, 6.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_WindowFrame_Bottom",
        (56.0, -395.0, 92.0),
        (54.0, 4.0, 6.0),
        "M_Trim",
    )

    # 三块不对称墙面污渍。
    add(
        "SM_OldShop_Stain_01",
        (-230.0, -389.5, 159.0),
        (16.0, 1.0, 120.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_Stain_02",
        (229.0, -389.5, 169.0),
        (16.0, 1.0, 140.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_Stain_03",
        (135.0, -389.5, 276.0),
        (120.0, 1.0, 22.0),
        "M_Stain",
    )

    # 更丰富的正面旧化：掉色块、门边脏污、卷帘门底部锈蚀、招牌褪色。
    add(
        "SM_OldShop_Stain_04",
        (-22.0, -398.6, 250.0),
        (70.0, 1.2, 28.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_Stain_05",
        (-205.0, -398.4, 52.0),
        (55.0, 1.2, 34.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_FadedPatch_01",
        (-20.0, -398.2, 76.0),
        (70.0, 1.2, 42.0),
        "M_OldWall",
    )
    add(
        "SM_OldShop_FadedPatch_02",
        (205.0, -398.1, 298.0),
        (44.0, 1.2, 66.0),
        "M_OldWall",
    )
    add(
        "SM_OldShop_FadedPatch_03",
        (-188.0, -398.3, 305.0),
        (86.0, 1.2, 36.0),
        "M_OldWall",
    )
    add(
        "SM_OldShop_DoorDirt_Left",
        (91.0, -397.8, 87.0),
        (12.0, 1.2, 160.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_DoorDirt_Right",
        (219.0, -397.8, 88.0),
        (12.0, 1.2, 150.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_ShutterBottom_Rust",
        (-100.0, -398.0, 19.0),
        (232.0, 2.0, 18.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_ShutterSide_Rust_Left",
        (-222.0, -397.6, 118.0),
        (10.0, 2.0, 160.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_Sign_FadedPatch_01",
        (-110.0, -399.5, 333.0),
        (110.0, 1.0, 22.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_Sign_FadedPatch_02",
        (120.0, -399.5, 317.0),
        (80.0, 1.0, 18.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_WallBottom_Dirt",
        (45.0, -399.0, 10.0),
        (390.0, 1.2, 20.0),
        "M_Stain",
    )

    # 侧面低模生活化细节：排水管、小窗、空调外机、电线盒和简易通风口。
    add(
        "SM_OldShop_Side_DrainPipe",
        (249.5, -70.0, 178.0),
        (1.0, 8.0, 320.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_DrainPipe_TopElbow",
        (249.5, -102.0, 336.0),
        (1.0, 56.0, 8.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_DrainPipe_BottomElbow",
        (249.5, -38.0, 24.0),
        (1.0, 56.0, 8.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_WindowGlass",
        (249.0, 140.0, 190.0),
        (1.0, 80.0, 70.0),
        "M_DarkGlass",
    )
    add(
        "SM_OldShop_Side_WindowFrame_Front",
        (249.5, 94.0, 190.0),
        (1.0, 8.0, 84.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_WindowFrame_Back",
        (249.5, 186.0, 190.0),
        (1.0, 8.0, 84.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_WindowFrame_Top",
        (249.5, 140.0, 232.0),
        (1.0, 84.0, 6.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_WindowFrame_Bottom",
        (249.5, 140.0, 148.0),
        (1.0, 84.0, 6.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_ACUnit",
        (247.5, 270.0, 268.0),
        (3.0, 90.0, 48.0),
        "M_DarkWall",
    )
    for index in range(3):
        add(
            f"SM_OldShop_Side_ACGrille_{index + 1:02d}",
            (249.5, 270.0, 258.0 + index * 10.0),
            (1.0, 70.0, 3.0),
            "M_Trim",
        )
    add(
        "SM_OldShop_Side_WireBox",
        (-248.5, -220.0, 210.0),
        (1.0, 40.0, 38.0),
        "M_DarkWall",
    )
    add(
        "SM_OldShop_Side_Wire_Vertical",
        (-249.5, -220.0, 300.5),
        (1.0, 4.0, 141.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_Wire_Horizontal",
        (-249.5, -160.0, 373.0),
        (1.0, 120.0, 4.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Side_VentBox",
        (247.5, -250.0, 105.0),
        (3.0, 60.0, 28.0),
        "M_DarkWall",
    )
    for index in range(3):
        add(
            f"SM_OldShop_Side_VentSlat_{index + 1:02d}",
            (249.5, -250.0, 98.0 + index * 7.0),
            (1.0, 46.0, 2.0),
            "M_Trim",
        )

    return parts


def part_bounds(part):
    """返回 PartSpec 在 X/Y/Z 三个轴上的最小值与最大值。"""

    return tuple(
        (
            part.location_cm[axis] - part.size_cm[axis] * 0.5,
            part.location_cm[axis] + part.size_cm[axis] * 0.5,
        )
        for axis in range(3)
    )


def overall_bounds(parts):
    """计算全部部件的轴对齐总包围盒。"""

    if not parts:
        raise ValueError("至少需要一个商铺部件。")

    bounds = [part_bounds(part) for part in parts]
    return tuple(
        (
            min(item[axis][0] for item in bounds),
            max(item[axis][1] for item in bounds),
        )
        for axis in range(3)
    )


def expected_envelope(
    width_cm=SHOP_WIDTH_CM,
    depth_cm=SHOP_DEPTH_CM,
    height_cm=SHOP_HEIGHT_CM,
    origin_x_cm=ORIGIN_X_CM,
    origin_y_cm=ORIGIN_Y_CM,
    base_z_cm=BASE_Z_CM,
):
    """返回允许使用的严格整体边界。"""

    return (
        (origin_x_cm - width_cm * 0.5, origin_x_cm + width_cm * 0.5),
        (origin_y_cm - depth_cm * 0.5, origin_y_cm + depth_cm * 0.5),
        (base_z_cm, base_z_cm + height_cm),
    )


def validate_part_specs(parts, envelope):
    """在生成 Actor 前检查重名、材质名与严格尺寸边界。"""

    labels = [part.label for part in parts]
    duplicate_labels = sorted(
        label for label in set(labels) if labels.count(label) > 1
    )
    if duplicate_labels:
        raise ValueError(
            "发现重复 Actor Label：" + ", ".join(duplicate_labels)
        )

    axis_names = ("X", "Y", "Z")
    for part in parts:
        if part.material_name not in MATERIAL_COLORS:
            raise ValueError(
                f"{part.label} 使用了未定义材质：{part.material_name}"
            )

        for axis, (minimum, maximum) in enumerate(part_bounds(part)):
            allowed_minimum, allowed_maximum = envelope[axis]
            if (
                minimum < allowed_minimum - EPSILON
                or maximum > allowed_maximum + EPSILON
            ):
                raise ValueError(
                    f"{part.label} 超出 {axis_names[axis]} 轴边界 "
                    f"[{allowed_minimum}, {allowed_maximum}]，"
                    f"实际为 [{minimum}, {maximum}]。"
                )

    return True


def ensure_material(material_name, color):
    """创建或更新一个仅包含 Base Color 的简单 Material。"""

    if unreal is None:
        raise RuntimeError("必须在启用了 Python 的 Unreal Editor 中运行。")

    asset_path = f"{MATERIAL_FOLDER}/{material_name}"
    material = unreal.EditorAssetLibrary.load_asset(asset_path)

    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            material_name,
            MATERIAL_FOLDER,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )

    if material is None:
        raise RuntimeError(f"无法创建材质：{asset_path}")

    editing = unreal.MaterialEditingLibrary
    editing.delete_all_material_expressions(material)

    color_node = editing.create_material_expression(
        material,
        unreal.MaterialExpressionConstant3Vector,
        -300,
        0,
    )
    if color_node is None:
        raise RuntimeError(f"无法为材质创建颜色节点：{asset_path}")

    color_node.set_editor_property("constant", unreal.LinearColor(*color))

    connected = editing.connect_material_property(
        color_node,
        "",
        unreal.MaterialProperty.MP_BASE_COLOR,
    )
    if not connected:
        raise RuntimeError(f"无法连接材质 Base Color：{asset_path}")

    editing.recompile_material(material)

    if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
        raise RuntimeError(f"无法保存材质：{asset_path}")

    return material


def generate_old_shop_legacy_cube_actors():
    """旧版备份：用多个 Cube Actor 生成商铺。新版入口不会调用它。"""

    if unreal is None:
        raise RuntimeError("必须在启用了 Python 的 Unreal Editor 中运行。")

    parts = build_part_specs()
    envelope = expected_envelope()
    validate_part_specs(parts, envelope)

    cube_mesh = unreal.load_asset(CUBE_ASSET_PATH)
    if cube_mesh is None:
        raise RuntimeError(f"无法加载 Engine Cube：{CUBE_ASSET_PATH}")

    # 先完成材质创建。材质失败时不会改动当前关卡中的旧商铺。
    materials = {
        name: ensure_material(name, color)
        for name, color in MATERIAL_COLORS.items()
    }

    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    if actor_subsystem is None:
        raise RuntimeError("无法取得 EditorActorSubsystem。")

    generator_tag = unreal.Name(GENERATOR_TAG)
    old_actors = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if actor.actor_has_tag(generator_tag)
    ]
    spawned_actors = []

    with unreal.ScopedEditorTransaction("Generate Old Shop 500x800x400"):
        try:
            # 先生成完整的新商铺。若中途失败，会删除半成品并保留旧商铺。
            for part in parts:
                actor = actor_subsystem.spawn_actor_from_class(
                    unreal.StaticMeshActor,
                    unreal.Vector(*part.location_cm),
                    unreal.Rotator(0.0, 0.0, 0.0),
                    False,
                )
                if actor is None:
                    raise RuntimeError(f"无法生成 Actor：{part.label}")

                # 立即记录，确保后续任何设置失败时都能清理这个 Actor。
                spawned_actors.append(actor)

                actor.set_actor_label(part.label)
                actor.set_folder_path(unreal.Name(FOLDER_NAME))
                actor.set_editor_property("tags", [generator_tag])
                actor.set_actor_scale3d(unreal.Vector(*part.scale))

                component = actor.get_component_by_class(
                    unreal.StaticMeshComponent
                )
                if component is None:
                    raise RuntimeError(
                        f"Actor 缺少 StaticMeshComponent：{part.label}"
                    )

                mesh_set = component.set_static_mesh(cube_mesh)
                if mesh_set is False:
                    raise RuntimeError(
                        f"无法为 Actor 设置 Cube Mesh：{part.label}"
                    )

                component.set_material(0, materials[part.material_name])
                component.set_editor_property(
                    "mobility",
                    unreal.ComponentMobility.STATIC,
                )
                actor.set_actor_enable_collision(part.enable_collision)
                if part.enable_collision:
                    component.set_collision_enabled(
                        unreal.CollisionEnabled.QUERY_AND_PHYSICS
                    )
                else:
                    component.set_collision_enabled(
                        unreal.CollisionEnabled.NO_COLLISION
                    )

            # 新商铺完整生成后才删除旧商铺。
            if old_actors and not actor_subsystem.destroy_actors(old_actors):
                raise RuntimeError("无法删除旧的 OldShop Actor。")

        except Exception:
            for actor in list(spawned_actors):
                actor_subsystem.destroy_actor(actor)
            raise

        actor_subsystem.set_selected_level_actors(spawned_actors)

    bounds = overall_bounds(parts)
    unreal.log(
        f"OldShop 生成完成：{len(spawned_actors)} 个 Actor；"
        f"替换旧 Actor：{len(old_actors)} 个；"
        f"整体边界：{bounds}"
    )
    return spawned_actors


STATIC_MESH_ASSET_PATH = "/Game/OldShop_500x800x400/SM_OldShop_500x800x400"
STATIC_MESH_PACKAGE_PATH = "/Game/OldShop_500x800x400"
STATIC_MESH_ASSET_NAME = "SM_OldShop_500x800x400"

MATERIAL_ORDER = [
    "M_OldWall",
    "M_DarkWall",
    "M_Shutter",
    "M_Sign",
    "M_DarkGlass",
    "M_Trim",
    "M_Stain",
]
MATERIAL_ID_BY_NAME = {
    material_name: material_index
    for material_index, material_name in enumerate(MATERIAL_ORDER)
}


@dataclass(frozen=True)
class MeshBoxSpec:
    """一个将被写入同一 Dynamic Mesh / Static Mesh Asset 的低模盒体。"""

    label: str
    location_cm: tuple
    size_cm: tuple
    material_name: str


def build_box_specs(
    width_cm=SHOP_WIDTH_CM,
    depth_cm=SHOP_DEPTH_CM,
    height_cm=SHOP_HEIGHT_CM,
    origin_x_cm=ORIGIN_X_CM,
    origin_y_cm=ORIGIN_Y_CM,
    base_z_cm=BASE_Z_CM,
):
    """创建单个 Static Mesh 内的全部盒体几何数据，不修改当前关卡。"""

    if min(width_cm, depth_cm, height_cm) <= 0.0:
        raise ValueError("商铺宽度、进深和高度必须大于 0 cm。")

    scale_x = width_cm / BASE_WIDTH_CM
    scale_y = depth_cm / BASE_DEPTH_CM
    scale_z = height_cm / BASE_HEIGHT_CM
    boxes = []

    def add(label, base_location, base_size, material_name):
        location = (
            origin_x_cm + base_location[0] * scale_x,
            origin_y_cm + base_location[1] * scale_y,
            base_z_cm + base_location[2] * scale_z,
        )
        size = (
            base_size[0] * scale_x,
            base_size[1] * scale_y,
            base_size[2] * scale_z,
        )
        boxes.append(MeshBoxSpec(label, location, size, material_name))

    # 主体压低到屋顶女儿墙下方，避免主体顶面和屋顶边缘共面。
    add("SM_OldShop_MainBlock", (0.0, 10.0, 187.5), (496.0, 780.0, 375.0), "M_OldWall")
    add("SM_OldShop_Storefront", (0.0, -384.0, 185.0), (480.0, 8.0, 370.0), "M_DarkWall")

    # 屋顶女儿墙/压条，顶面互不重叠，整体最高点为 Z=401。
    add("SM_OldShop_RoofEdge_Front", (0.0, -393.0, 387.5), (460.0, 14.0, 25.0), "M_Trim")
    add("SM_OldShop_RoofEdge_Back", (0.0, 392.5, 390.0), (460.0, 15.0, 20.0), "M_Trim")
    add("SM_OldShop_RoofEdge_Left", (-241.5, -3.0, 387.5), (17.0, 740.0, 25.0), "M_Trim")
    add("SM_OldShop_RoofEdge_Right", (241.5, -3.0, 387.5), (17.0, 740.0, 25.0), "M_Trim")

    # 正面一层：卷帘门、侧门、招牌、窗户。
    add("SM_OldShop_Shutter", (-100.0, -390.0, 140.0), (240.0, 4.0, 240.0), "M_Shutter")
    for index in range(15):
        add(
            f"SM_OldShop_Shutter_Slat_{index + 1:02d}",
            (-100.0, -394.5, 29.0 + index * 15.0),
            (232.0, 3.0, 4.0),
            "M_Trim",
        )

    add("SM_OldShop_Door", (155.0, -390.0, 117.5), (110.0, 4.0, 235.0), "M_DarkWall")
    add("SM_OldShop_DoorFrame_Left", (95.0, -395.0, 118.5), (8.0, 4.0, 235.0), "M_Trim")
    add("SM_OldShop_DoorFrame_Right", (215.0, -395.0, 118.5), (8.0, 4.0, 235.0), "M_Trim")
    add("SM_OldShop_DoorFrame_Top", (155.0, -395.0, 240.0), (112.0, 4.0, 8.0), "M_Trim")

    add("SM_OldShop_Sign", (0.0, -394.5, 325.5), (430.0, 8.0, 65.0), "M_Sign")

    add("SM_OldShop_WindowGlass", (56.0, -390.0, 140.0), (50.0, 4.0, 90.0), "M_DarkGlass")
    add("SM_OldShop_WindowFrame_Left", (26.0, -395.0, 140.0), (6.0, 4.0, 90.0), "M_Trim")
    add("SM_OldShop_WindowFrame_Right", (86.0, -395.0, 140.0), (6.0, 4.0, 90.0), "M_Trim")
    add("SM_OldShop_WindowFrame_Top", (56.0, -395.0, 188.0), (54.0, 4.0, 6.0), "M_Trim")
    add("SM_OldShop_WindowFrame_Bottom", (56.0, -395.0, 92.0), (54.0, 4.0, 6.0), "M_Trim")

    # 正面旧化。每层沿 -Y 有明确错位，避免贴片互相共面。
    add("SM_OldShop_Stain_01", (-230.0, -389.5, 159.0), (16.0, 1.0, 120.0), "M_Stain")
    add("SM_OldShop_Stain_02", (229.0, -389.5, 169.0), (16.0, 1.0, 140.0), "M_Stain")
    add("SM_OldShop_Stain_03", (135.0, -389.5, 276.0), (120.0, 1.0, 22.0), "M_Stain")
    add("SM_OldShop_Stain_04", (-22.0, -398.6, 250.0), (70.0, 1.2, 28.0), "M_Stain")
    add("SM_OldShop_Stain_05", (-205.0, -398.4, 52.0), (55.0, 1.2, 34.0), "M_Stain")
    add("SM_OldShop_FadedPatch_01", (-20.0, -398.2, 76.0), (70.0, 1.2, 42.0), "M_OldWall")
    add("SM_OldShop_FadedPatch_02", (205.0, -398.1, 298.0), (44.0, 1.2, 66.0), "M_OldWall")
    add("SM_OldShop_FadedPatch_03", (-188.0, -398.3, 305.0), (86.0, 1.2, 36.0), "M_OldWall")
    add("SM_OldShop_DoorDirt_Left", (91.0, -397.8, 87.0), (12.0, 1.2, 160.0), "M_Stain")
    add("SM_OldShop_DoorDirt_Right", (219.0, -397.8, 88.0), (12.0, 1.2, 150.0), "M_Stain")
    add("SM_OldShop_ShutterBottom_Rust", (-100.0, -398.0, 19.0), (232.0, 2.0, 18.0), "M_Stain")
    add("SM_OldShop_ShutterSide_Rust_Left", (-222.0, -397.6, 118.0), (10.0, 2.0, 160.0), "M_Stain")
    add("SM_OldShop_Sign_FadedPatch_01", (-110.0, -399.5, 333.0), (110.0, 1.0, 22.0), "M_Stain")
    add("SM_OldShop_Sign_FadedPatch_02", (120.0, -399.5, 317.0), (80.0, 1.0, 18.0), "M_Stain")
    add("SM_OldShop_WallBottom_Dirt", (45.0, -399.0, 10.0), (390.0, 1.2, 20.0), "M_Stain")

    # 侧面生活化细节：排水管、小窗、空调外机、电线盒、通风口、侧墙旧化块。
    add("SM_OldShop_Side_DrainPipe", (249.5, -70.0, 178.0), (1.0, 8.0, 320.0), "M_Trim")
    add("SM_OldShop_Side_DrainPipe_TopElbow", (249.5, -102.0, 336.0), (1.0, 56.0, 8.0), "M_Trim")
    add("SM_OldShop_Side_DrainPipe_BottomElbow", (249.5, -38.0, 24.0), (1.0, 56.0, 8.0), "M_Trim")

    add("SM_OldShop_Side_WindowGlass", (249.0, 140.0, 190.0), (1.0, 80.0, 70.0), "M_DarkGlass")
    add("SM_OldShop_Side_WindowFrame_Front", (249.5, 94.0, 190.0), (1.0, 8.0, 84.0), "M_Trim")
    add("SM_OldShop_Side_WindowFrame_Back", (249.5, 186.0, 190.0), (1.0, 8.0, 84.0), "M_Trim")
    add("SM_OldShop_Side_WindowFrame_Top", (249.5, 140.0, 232.0), (1.0, 84.0, 6.0), "M_Trim")
    add("SM_OldShop_Side_WindowFrame_Bottom", (249.5, 140.0, 148.0), (1.0, 84.0, 6.0), "M_Trim")

    add("SM_OldShop_Side_ACUnit", (247.5, 270.0, 268.0), (3.0, 90.0, 48.0), "M_DarkWall")
    for index in range(3):
        add(
            f"SM_OldShop_Side_ACGrille_{index + 1:02d}",
            (249.5, 270.0, 258.0 + index * 10.0),
            (1.0, 70.0, 3.0),
            "M_Trim",
        )

    add("SM_OldShop_Side_WireBox", (-248.5, -220.0, 210.0), (1.0, 40.0, 38.0), "M_DarkWall")
    add("SM_OldShop_Side_Wire_Vertical", (-249.5, -220.0, 300.5), (1.0, 4.0, 141.0), "M_Trim")
    add("SM_OldShop_Side_Wire_Horizontal", (-249.5, -160.0, 373.0), (1.0, 120.0, 4.0), "M_Trim")

    add("SM_OldShop_Side_VentBox", (247.5, -250.0, 105.0), (3.0, 60.0, 28.0), "M_DarkWall")
    for index in range(3):
        add(
            f"SM_OldShop_Side_VentSlat_{index + 1:02d}",
            (249.5, -250.0, 98.0 + index * 7.0),
            (1.0, 46.0, 2.0),
            "M_Trim",
        )

    add("SM_OldShop_Side_Stain_01", (248.75, -330.0, 170.0), (1.0, 70.0, 110.0), "M_Stain")
    add("SM_OldShop_Side_Stain_02", (-248.75, 225.0, 135.0), (1.0, 58.0, 95.0), "M_Stain")

    return boxes


def box_bounds(box):
    """返回 MeshBoxSpec 在 X/Y/Z 三个轴上的最小值与最大值。"""

    return tuple(
        (
            box.location_cm[axis] - box.size_cm[axis] * 0.5,
            box.location_cm[axis] + box.size_cm[axis] * 0.5,
        )
        for axis in range(3)
    )


def overall_bounds(boxes):
    """计算全部盒体的轴对齐总包围盒。"""

    if not boxes:
        raise ValueError("至少需要一个商铺盒体。")

    bounds = [box_bounds(box) for box in boxes]
    return tuple(
        (
            min(item[axis][0] for item in bounds),
            max(item[axis][1] for item in bounds),
        )
        for axis in range(3)
    )


def validate_box_specs(boxes, envelope):
    """在写入 Dynamic Mesh 前检查重名、材质名和严格尺寸边界。"""

    labels = [box.label for box in boxes]
    duplicate_labels = sorted(
        label for label in set(labels) if labels.count(label) > 1
    )
    if duplicate_labels:
        raise ValueError("发现重复几何标签：" + ", ".join(duplicate_labels))

    axis_names = ("X", "Y", "Z")
    for box in boxes:
        if box.material_name not in MATERIAL_ID_BY_NAME:
            raise ValueError(
                f"{box.label} 使用了未定义材质：{box.material_name}"
            )

        if min(box.size_cm) <= 0.0:
            raise ValueError(f"{box.label} 的尺寸必须全部大于 0 cm。")

        for axis, (minimum, maximum) in enumerate(box_bounds(box)):
            allowed_minimum, allowed_maximum = envelope[axis]
            if (
                minimum < allowed_minimum - EPSILON
                or maximum > allowed_maximum + EPSILON
            ):
                raise ValueError(
                    f"{box.label} 超出 {axis_names[axis]} 轴边界 "
                    f"[{allowed_minimum}, {allowed_maximum}]，"
                    f"实际为 [{minimum}, {maximum}]。"
                )

    return True


def _require_unreal_attribute(*candidate_names):
    """返回第一个存在的 unreal API；若不存在，抛出清晰错误。"""

    if unreal is None:
        raise RuntimeError("必须在启用了 Python 的 Unreal Editor 中运行。")

    for candidate_name in candidate_names:
        value = getattr(unreal, candidate_name, None)
        if value is not None:
            return value

    raise RuntimeError(
        "当前 UE Python 环境缺少 Geometry Script API："
        + " / ".join(candidate_names)
        + "。请确认已启用 Geometry Script、Python Editor Script Plugin 和 Editor Scripting Utilities。"
    )


def _set_editor_property_if_present(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        return False


def _make_transform(location_cm):
    """兼容不同 UE Python 版本的 Transform 构造方式。"""

    vector = unreal.Vector(*location_cm)
    rotator = unreal.Rotator(0.0, 0.0, 0.0)
    scale = unreal.Vector(1.0, 1.0, 1.0)

    for factory in (
        lambda: unreal.Transform(location=vector, rotation=rotator, scale=scale),
        lambda: unreal.Transform(vector, rotator, scale),
    ):
        try:
            return factory()
        except Exception:
            pass

    transform = unreal.Transform()
    for property_name in ("translation", "location"):
        if _set_editor_property_if_present(transform, property_name, vector):
            break
    _set_editor_property_if_present(transform, "rotation", rotator)
    _set_editor_property_if_present(transform, "scale3d", scale)
    _set_editor_property_if_present(transform, "scale", scale)
    return transform


def _get_center_origin_mode():
    enum_type = _require_unreal_attribute(
        "GeometryScriptPrimitiveOriginMode",
        "EGeometryScriptPrimitiveOriginMode",
    )
    for candidate_name in ("CENTER", "Center", "center"):
        if hasattr(enum_type, candidate_name):
            return getattr(enum_type, candidate_name)
    raise RuntimeError("Geometry Script 缺少 PrimitiveOriginMode.Center 枚举值。")


def _get_success_outcome_pin():
    enum_type = _require_unreal_attribute(
        "GeometryScriptOutcomePins",
        "EGeometryScriptOutcomePins",
    )
    for candidate_name in ("SUCCESS", "Success", "success"):
        if hasattr(enum_type, candidate_name):
            return getattr(enum_type, candidate_name)
    raise RuntimeError("Geometry Script 缺少 OutcomePins.Success 枚举值。")


def _make_primitive_options(material_id):
    option_type = _require_unreal_attribute("GeometryScriptPrimitiveOptions")
    options = option_type()
    for property_name in ("material_id", "MaterialID"):
        if _set_editor_property_if_present(options, property_name, material_id):
            return options
    raise RuntimeError("无法设置 GeometryScriptPrimitiveOptions.MaterialID。")


def _call_append_box(dynamic_mesh, box):
    primitive_library = _require_unreal_attribute(
        "GeometryScript_Primitives",
        "GeometryScriptLibrary_MeshPrimitiveFunctions",
    )
    append_box = getattr(primitive_library, "append_box", None)
    if append_box is None:
        raise RuntimeError("当前 Geometry Script Python API 缺少 append_box。")

    options = _make_primitive_options(MATERIAL_ID_BY_NAME[box.material_name])
    transform = _make_transform(box.location_cm)
    origin = _get_center_origin_mode()

    attempts = (
        lambda: append_box(
            dynamic_mesh,
            options,
            transform,
            box.size_cm[0],
            box.size_cm[1],
            box.size_cm[2],
            0,
            0,
            0,
            origin,
        ),
        lambda: append_box(
            target_mesh=dynamic_mesh,
            primitive_options=options,
            transform=transform,
            dimension_x=box.size_cm[0],
            dimension_y=box.size_cm[1],
            dimension_z=box.size_cm[2],
            steps_x=0,
            steps_y=0,
            steps_z=0,
            origin=origin,
        ),
    )

    last_error = None
    for attempt in attempts:
        try:
            result = attempt()
            return result if result is not None else dynamic_mesh
        except Exception as error:
            last_error = error

    raise RuntimeError(f"append_box 调用失败：{last_error}")


def _create_dynamic_mesh_from_boxes(boxes):
    dynamic_mesh_type = _require_unreal_attribute("DynamicMesh")
    dynamic_mesh = dynamic_mesh_type()

    for box in boxes:
        dynamic_mesh = _call_append_box(dynamic_mesh, box)

    return dynamic_mesh


def _call_create_static_mesh_asset(dynamic_mesh):
    asset_library = _require_unreal_attribute(
        "GeometryScript_NewAssetUtils",
        "GeometryScript_CreateNewAssetFunctions",
        "GeometryScriptLibrary_CreateNewAssetFunctions",
    )
    create_function = getattr(
        asset_library,
        "create_new_static_mesh_asset_from_mesh",
        None,
    )
    if create_function is None:
        raise RuntimeError(
            "当前 Geometry Script Python API 缺少 create_new_static_mesh_asset_from_mesh。"
        )

    options_type = _require_unreal_attribute(
        "GeometryScriptCreateNewStaticMeshAssetOptions"
    )
    options = options_type()
    _set_editor_property_if_present(options, "enable_recompute_normals", True)
    _set_editor_property_if_present(options, "b_enable_recompute_normals", True)
    _set_editor_property_if_present(options, "enable_recompute_tangents", True)
    _set_editor_property_if_present(options, "b_enable_recompute_tangents", True)
    _set_editor_property_if_present(options, "enable_collision", True)
    _set_editor_property_if_present(options, "b_enable_collision", True)
    _set_editor_property_if_present(options, "enable_nanite", False)
    _set_editor_property_if_present(options, "b_enable_nanite", False)

    if unreal.EditorAssetLibrary.does_asset_exist(STATIC_MESH_ASSET_PATH):
        if not unreal.EditorAssetLibrary.delete_asset(STATIC_MESH_ASSET_PATH):
            raise RuntimeError(f"无法删除旧 Static Mesh Asset：{STATIC_MESH_ASSET_PATH}")

    attempts = (
        lambda: create_function(dynamic_mesh, STATIC_MESH_ASSET_PATH, options),
        lambda: create_function(
            dynamic_mesh,
            STATIC_MESH_ASSET_PATH,
            options,
            _get_success_outcome_pin(),
        ),
        lambda: create_function(
            from_dynamic_mesh=dynamic_mesh,
            asset_path_and_name=STATIC_MESH_ASSET_PATH,
            options=options,
        ),
        lambda: create_function(
            from_dynamic_mesh=dynamic_mesh,
            asset_path_and_name=STATIC_MESH_ASSET_PATH,
            options=options,
            outcome=_get_success_outcome_pin(),
        ),
    )

    last_error = None
    for attempt in attempts:
        try:
            result = attempt()
            static_mesh = result[0] if isinstance(result, tuple) else result
            if static_mesh is not None:
                return static_mesh
        except Exception as error:
            last_error = error

    raise RuntimeError(f"无法通过 Geometry Script 创建 Static Mesh Asset：{last_error}")


def _assign_materials_to_static_mesh(static_mesh, materials):
    for material_index, material_name in enumerate(MATERIAL_ORDER):
        material = materials[material_name]
        if hasattr(static_mesh, "set_material"):
            static_mesh.set_material(material_index, material)
        else:
            raise RuntimeError("StaticMesh Python API 缺少 set_material，无法分配材质槽。")


def _destroy_existing_old_shop_actors(actor_subsystem):
    generator_tag = unreal.Name(GENERATOR_TAG)
    actors_to_destroy = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if actor.actor_has_tag(generator_tag)
    ]
    if actors_to_destroy and not actor_subsystem.destroy_actors(actors_to_destroy):
        raise RuntimeError("无法删除旧的 OldShop 关卡实例。")
    return len(actors_to_destroy)


def _spawn_single_static_mesh_instance(static_mesh):
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if actor_subsystem is None:
        raise RuntimeError("无法取得 EditorActorSubsystem。")

    removed_count = _destroy_existing_old_shop_actors(actor_subsystem)
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if actor is None:
        raise RuntimeError("无法在当前关卡放置 Static Mesh 实例。")

    actor.set_actor_label("SM_OldShop_500x800x400_Instance")
    actor.set_folder_path(unreal.Name(FOLDER_NAME))
    actor.set_editor_property("tags", [unreal.Name(GENERATOR_TAG)])

    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    if component is None:
        raise RuntimeError("StaticMeshActor 缺少 StaticMeshComponent。")

    if component.set_static_mesh(static_mesh) is False:
        raise RuntimeError("无法为实例设置生成的 Static Mesh Asset。")

    component.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    actor_subsystem.set_selected_level_actors([actor])
    return actor, removed_count


def generate_old_shop_static_mesh_asset():
    """使用 Geometry Script / Dynamic Mesh 生成一个 Static Mesh Asset，并在关卡中放置一个实例。"""

    if unreal is None:
        raise RuntimeError("必须在启用了 Python 的 Unreal Editor 中运行。")

    boxes = build_box_specs()
    envelope = expected_envelope()
    validate_box_specs(boxes, envelope)

    materials = {
        name: ensure_material(name, MATERIAL_COLORS[name])
        for name in MATERIAL_ORDER
    }

    dynamic_mesh = _create_dynamic_mesh_from_boxes(boxes)
    static_mesh = _call_create_static_mesh_asset(dynamic_mesh)
    _assign_materials_to_static_mesh(static_mesh, materials)

    if not unreal.EditorAssetLibrary.save_loaded_asset(static_mesh, False):
        raise RuntimeError(f"无法保存 Static Mesh Asset：{STATIC_MESH_ASSET_PATH}")

    actor, removed_count = _spawn_single_static_mesh_instance(static_mesh)
    bounds = overall_bounds(boxes)
    unreal.log(
        f"OldShop Static Mesh 生成完成：{STATIC_MESH_ASSET_PATH}；"
        f"盒体数：{len(boxes)}；替换旧 Actor：{removed_count}；"
        f"整体边界：{bounds}"
    )
    return static_mesh, actor


def generate_old_shop():
    """兼容旧入口：现在生成单个 Static Mesh Asset，而不是多个 Cube Actor。"""

    return generate_old_shop_static_mesh_asset()


def main():
    try:
        generate_old_shop()
    except Exception as error:
        if unreal is not None:
            unreal.log_error(f"OldShop 生成失败：{error}")
        raise


if __name__ == "__main__":
    main()
