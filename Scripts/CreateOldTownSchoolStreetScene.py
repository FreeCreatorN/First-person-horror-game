"""Build the Old Town School Street scene in an independent UE5 level.

Run inside Unreal Editor 5.7 with:
  -ExecutePythonScript=D:/UE/Project/HorrorGame/Scripts/CreateOldTownSchoolStreetScene.py

The script deliberately saves only its own assets and the duplicated target
level.  It never saves the source blockout level or every dirty package.
"""

from pathlib import Path
import importlib.util
import json
import math
import sys
import traceback

import unreal


PROJECT_ROOT = Path(unreal.Paths.project_dir()).resolve()
SOURCE_LEVEL = "/Game/Yastar/Maps/Blockout/L_Chapter01_Blockout"
TARGET_LEVEL = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
ASSET_ROOT = "/Game/Yastar/OldTownSchoolStreet"
TEXTURE_ROOT = ASSET_ROOT + "/Textures"
MATERIAL_ROOT = ASSET_ROOT + "/Materials"
PROP_ROOT = ASSET_ROOT + "/Props"
POLE_ROOT = PROP_ROOT + "/PolyHaven_ElectricityPoles"
DETAILED_PROP_ROOT = PROP_ROOT + "/Detailed"
P3_PROP_ROOT = PROP_ROOT + "/P3"
P5_PROP_ROOT = PROP_ROOT + "/P5"
ARCHITECTURAL_MODULE_ROOT = ASSET_ROOT + "/Architecture/Windows"

GENERATOR_TAG = "OldTownSchoolStreet_Generated"
FOLDER_ROOT = "OldTownSchoolStreet"
SUCCESS_MARKER = "OTS_BUILD_SUCCESS"
POINT_LIGHT_INTENSITY_SCALE = 1.35

CUBE_PATH = "/Engine/BasicShapes/Cube.Cube"
CYLINDER_PATH = "/Engine/BasicShapes/Cylinder.Cylinder"
MAIN_HOME_BP = "/Game/Yastar/Blockout/Buildings/BP_MainHomeInteractive"

SOURCE_FILES = {
    "T_OTS_Asphalt_BaseColor": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/AmbientCG/Asphalt027C_2K-JPG/"
        "Asphalt027C_2K-JPG_Color.jpg"
    ),
    "T_OTS_Asphalt_Normal": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/AmbientCG/Asphalt027C_2K-JPG/"
        "Asphalt027C_2K-JPG_NormalDX.jpg"
    ),
    "T_OTS_Asphalt_Roughness": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/AmbientCG/Asphalt027C_2K-JPG/"
        "Asphalt027C_2K-JPG_Roughness.jpg"
    ),
    "T_OTS_Concrete_BaseColor": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/concrete_wall_003_2k/"
        "concrete_wall_003_diff_2k.jpg"
    ),
    "T_OTS_Concrete_Normal": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/concrete_wall_003_2k/"
        "concrete_wall_003_nor_dx_2k.jpg"
    ),
    "T_OTS_Concrete_Roughness": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/concrete_wall_003_2k/"
        "concrete_wall_003_rough_2k.jpg"
    ),
    "T_OTS_PaintedPlaster_BaseColor": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/painted_plaster_wall_2k/"
        "painted_plaster_wall_diff_2k.jpg"
    ),
    "T_OTS_PaintedPlaster_Normal": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/painted_plaster_wall_2k/"
        "painted_plaster_wall_nor_dx_2k.jpg"
    ),
    "T_OTS_PaintedPlaster_Roughness": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/painted_plaster_wall_2k/"
        "painted_plaster_wall_rough_2k.jpg"
    ),
    "T_OTS_GreenMetalRust_BaseColor": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/green_metal_rust_2k/"
        "green_metal_rust_diff_2k.jpg"
    ),
    "T_OTS_GreenMetalRust_Normal": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/green_metal_rust_2k/"
        "green_metal_rust_nor_dx_2k.jpg"
    ),
    "T_OTS_GreenMetalRust_Roughness": (
        PROJECT_ROOT
        / "SourceArt/ThirdParty/PolyHaven/green_metal_rust_2k/"
        "green_metal_rust_rough_2k.jpg"
    ),
}

POLE_FBX = (
    PROJECT_ROOT
    / "SourceArt/ThirdParty/PolyHaven/modular_electricity_poles_1k/"
    "modular_electricity_poles_1k.fbx"
)

MATERIAL_NAMES = (
    "M_OTS_WetAsphalt",
    "M_OTS_OldConcrete",
    "M_OTS_Sidewalk",
    "M_OTS_SchoolWall",
    "M_OTS_FadedBlueWall",
    "M_OTS_FadedGreenWall",
    "M_OTS_RedBrick",
    "M_OTS_DarkTrim",
    "M_OTS_OldGreenMetal",
    "M_OTS_FadedBlueMetal",
    "M_OTS_FadedRedMetal",
    "M_OTS_RustMetal",
    "M_OTS_DarkGlass",
    "M_OTS_WarmWindow",
    "M_OTS_CoolWindow",
    "M_OTS_NeutralWindow",
    "M_OTS_FluorescentTube",
    "M_OTS_Stain",
    "M_OTS_RoadMarking",
    "M_OTS_Puddle",
    "M_OTS_BlackWire",
    "M_OTS_Cardboard",
    "M_OTS_DarkGround",
    "M_OTS_FadedRedSign",
    "M_OTS_FadedBlueSign",
    "M_OTS_FadedOchreSign",
    "M_OTS_OldGreenSign",
    "M_OTS_StorefrontShadow",
)

_name_counter = {}


def log(message):
    unreal.log("OTS: {}".format(message))


def warn(message):
    unreal.log_warning("OTS: {}".format(message))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def safe_set(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception as exc:
        warn(
            "{}.{} was not set: {}".format(
                obj.get_class().get_name()
                if hasattr(obj, "get_class")
                else type(obj).__name__,
                property_name,
                exc,
            )
        )
        return False


def make_rotator(rotation):
    """Convert our (pitch, yaw, roll) tuples without UE positional ambiguity."""
    return unreal.Rotator(
        roll=float(rotation[2]),
        pitch=float(rotation[0]),
        yaw=float(rotation[1]),
    )


def unique_label(prefix):
    count = _name_counter.get(prefix, 0) + 1
    _name_counter[prefix] = count
    return "{}_{:02d}".format(prefix, count)


def asset_exists(path):
    return unreal.EditorAssetLibrary.does_asset_exist(path)


def load_asset(path, required=True):
    asset = (
        unreal.EditorAssetLibrary.load_asset(path)
        if asset_exists(path)
        else None
    )
    if required and asset is None:
        raise RuntimeError("Missing required asset: {}".format(path))
    return asset


def ensure_asset_directories():
    for path in (
        "/Game/Yastar/Maps/Scenes",
        ASSET_ROOT,
        TEXTURE_ROOT,
        MATERIAL_ROOT,
        PROP_ROOT,
        POLE_ROOT,
    ):
        unreal.EditorAssetLibrary.make_directory(path)


def import_texture(asset_name, filename, kind):
    require(filename.is_file(), "Missing texture source: {}".format(filename))
    asset_path = TEXTURE_ROOT + "/" + asset_name
    existing = load_asset(asset_path, required=False)
    if existing is not None:
        log("Reusing imported texture {}".format(asset_path))
        return existing
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(filename))
    task.set_editor_property("destination_path", TEXTURE_ROOT)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset_path = "{}/{}".format(TEXTURE_ROOT, asset_name)
    texture = load_asset(asset_path)
    require(
        isinstance(texture, unreal.Texture2D),
        "{} did not import as Texture2D".format(asset_path),
    )
    if kind == "normal":
        safe_set(texture, "srgb", False)
        safe_set(
            texture,
            "compression_settings",
            unreal.TextureCompressionSettings.TC_NORMALMAP,
        )
    elif kind == "roughness":
        safe_set(texture, "srgb", False)
        compression = getattr(
            unreal.TextureCompressionSettings,
            "TC_GRAYSCALE",
            None,
        )
        if compression is not None:
            safe_set(texture, "compression_settings", compression)
    safe_set(texture, "virtual_texture_streaming", False)
    require(
        unreal.EditorAssetLibrary.save_loaded_asset(texture, False),
        "Unable to save imported texture {}".format(asset_path),
    )
    return texture


def import_scene_textures():
    textures = {}
    for asset_name, filename in SOURCE_FILES.items():
        kind = (
            "normal"
            if asset_name.endswith("_Normal")
            else "roughness"
            if asset_name.endswith("_Roughness")
            else "color"
        )
        textures[asset_name] = import_texture(asset_name, filename, kind)
    log("Imported or updated {} CC0 textures".format(len(textures)))
    return textures


def create_material_asset(name):
    path = "{}/{}".format(MATERIAL_ROOT, name)
    material = load_asset(path, required=False)
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name,
            MATERIAL_ROOT,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
    require(material is not None, "Unable to create material {}".format(path))
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    safe_set(material, "two_sided", False)
    return material


def expression(material, expression_type, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        expression_type,
        x,
        y,
    )
    require(
        node is not None,
        "Unable to create {}".format(expression_type.__name__),
    )
    return node


def connect(source, output_name, target, input_name):
    require(
        unreal.MaterialEditingLibrary.connect_material_expressions(
            source,
            output_name,
            target,
            input_name,
        ),
        "Unable to connect {} to {}".format(output_name, input_name),
    )


def connect_property(source, output_name, material_property):
    require(
        unreal.MaterialEditingLibrary.connect_material_property(
            source,
            output_name,
            material_property,
        ),
        "Unable to connect material property {}".format(material_property),
    )


def constant_scalar(material, value, x, y):
    node = expression(
        material,
        unreal.MaterialExpressionConstant,
        x,
        y,
    )
    node.set_editor_property("r", float(value))
    return node


def constant_color(material, color, x, y):
    node = expression(
        material,
        unreal.MaterialExpressionConstant3Vector,
        x,
        y,
    )
    node.set_editor_property("constant", unreal.LinearColor(*color))
    return node


def texture_sample(material, texture, x, y, uv_node=None, normal=False):
    node = expression(
        material,
        unreal.MaterialExpressionTextureSample,
        x,
        y,
    )
    node.set_editor_property("texture", texture)
    if normal:
        node.set_editor_property(
            "sampler_type",
            unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
        )
    if uv_node is not None:
        connect(uv_node, "", node, "UVs")
    return node


def build_world_aligned_sample(
    material,
    texture,
    texture_size_cm,
    x,
    y,
    normal=False,
):
    function_path = (
        "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
        + (
            "WorldAlignedNormal.WorldAlignedNormal"
            if normal
            else "WorldAlignedTexture.WorldAlignedTexture"
        )
    )
    material_function = load_asset(function_path)
    texture_node = expression(
        material,
        unreal.MaterialExpressionTextureObject,
        x,
        y,
    )
    texture_node.set_editor_property("texture", texture)
    if normal:
        safe_set(
            texture_node,
            "sampler_type",
            unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
        )
    size_node = constant_color(
        material,
        (
            float(texture_size_cm),
            float(texture_size_cm),
            float(texture_size_cm),
            1.0,
        ),
        x,
        y + 130,
    )
    call_node = expression(
        material,
        unreal.MaterialExpressionMaterialFunctionCall,
        x + 260,
        y,
    )
    require(
        call_node.set_material_function(material_function),
        "Unable to set {}".format(function_path),
    )
    connect(texture_node, "", call_node, "TextureObject")
    connect(size_node, "", call_node, "TextureSize")
    return call_node, "XYZ Texture"


def build_uv_sample(
    material,
    texture,
    x,
    y,
    normal=False,
    tiling=4.0,
):
    uv = expression(
        material,
        unreal.MaterialExpressionTextureCoordinate,
        x,
        y + 120,
    )
    uv.set_editor_property("u_tiling", float(tiling))
    uv.set_editor_property("v_tiling", float(tiling))
    return texture_sample(
        material,
        texture,
        x + 240,
        y,
        uv_node=uv,
        normal=normal,
    ), "RGB"


def create_textured_material(
    name,
    base_texture,
    normal_texture,
    roughness_texture,
    tint,
    texture_size_cm,
    roughness_multiplier,
    anti_tile=False,
    secondary_scale=1.381966,
    macro_size_cm=1500.0,
    metallic=0.0,
    secondary_texture=None,
    secondary_size_cm=None,
):
    material = create_material_asset(name)

    # Build the graph explicitly so the UV fallback stays readable.  Wall
    # materials receive a second, non-harmonic scale plus low-frequency world
    # noise.  This prevents one concrete stain from repeating in lockstep
    # across every building while keeping Normal/Roughness to one sample each.
    try:
        base_node, base_output = build_world_aligned_sample(
            material,
            base_texture,
            texture_size_cm,
            -1050,
            -420,
            False,
        )
        normal_node, normal_output = build_world_aligned_sample(
            material,
            normal_texture,
            texture_size_cm,
            -1050,
            -80,
            True,
        )
        rough_node, rough_output = build_world_aligned_sample(
            material,
            roughness_texture,
            texture_size_cm,
            -1050,
            280,
            False,
        )
        secondary_node = None
        secondary_output = ""
        if anti_tile:
            secondary_node, secondary_output = build_world_aligned_sample(
                material,
                secondary_texture if secondary_texture is not None else base_texture,
                secondary_size_cm if secondary_size_cm is not None else texture_size_cm * float(secondary_scale),
                -1050,
                -760,
                False,
            )
    except Exception as exc:
        warn(
            "{} uses UV fallback because world alignment failed: {}".format(
                name,
                exc,
            )
        )
        unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
        base_node, base_output = build_uv_sample(
            material,
            base_texture,
            -950,
            -320,
            False,
            4.0,
        )
        normal_node, normal_output = build_uv_sample(
            material,
            normal_texture,
            -950,
            0,
            True,
            4.0,
        )
        rough_node, rough_output = build_uv_sample(
            material,
            roughness_texture,
            -950,
            320,
            False,
            4.0,
        )
        secondary_node = None
        secondary_output = ""
        if anti_tile:
            secondary_node, secondary_output = build_uv_sample(
                material,
                secondary_texture if secondary_texture is not None else base_texture,
                -950,
                -640,
                False,
                4.0 / float(secondary_scale),
            )

    base_source = base_node
    base_source_output = base_output
    macro_noise = None
    if anti_tile:
        world_position = expression(
            material,
            unreal.MaterialExpressionWorldPosition,
            -820,
            -650,
        )
        macro_noise = expression(
            material,
            unreal.MaterialExpressionNoise,
            -660,
            -650,
        )
        for property_name, value in (
            ("scale", 1.0 / float(macro_size_cm)),
            ("levels", 2),
            ("output_min", 0.0),
            ("output_max", 1.0),
        ):
            require(
                safe_set(macro_noise, property_name, value),
                "Unable to configure {} anti-tile noise {}".format(
                    name,
                    property_name,
                ),
            )
        safe_set(macro_noise, "desc", "OTS_WALL_BLEND_NOISE")
        connect(world_position, "", macro_noise, "World Position")

        scale_blend = expression(
            material,
            unreal.MaterialExpressionLinearInterpolate,
            -420,
            -500,
        )
        scale_weight = expression(
            material,
            unreal.MaterialExpressionLinearInterpolate,
            -470,
            -670,
        )
        safe_set(scale_weight, "desc", "OTS_WALL_SCALE_ALPHA")
        scale_min = constant_scalar(material, 0.22, -650, -790)
        scale_max = constant_scalar(material, 0.62, -650, -740)
        connect(scale_min, "", scale_weight, "A")
        connect(scale_max, "", scale_weight, "B")
        connect(macro_noise, "", scale_weight, "Alpha")
        connect(base_node, base_output, scale_blend, "A")
        connect(secondary_node, secondary_output, scale_blend, "B")
        connect(scale_weight, "", scale_blend, "Alpha")
        base_source = scale_blend
        base_source_output = ""

    tint_node = constant_color(material, tint, -170, -350)
    tint_multiply = expression(
        material,
        unreal.MaterialExpressionMultiply,
        80,
        -300,
    )
    connect(base_source, base_source_output, tint_multiply, "A")
    connect(tint_node, "", tint_multiply, "B")

    final_base = tint_multiply
    if anti_tile:
        # A warm grey-brown multiplier produces broad aged areas without
        # turning them into black "holes".
        worn_multiplier = constant_color(
            material,
            (0.68, 0.64, 0.56, 1.0),
            310,
            -370,
        )
        worn_base = expression(
            material,
            unreal.MaterialExpressionMultiply,
            530,
            -330,
        )
        connect(tint_multiply, "", worn_base, "A")
        connect(worn_multiplier, "", worn_base, "B")
        macro_blend = expression(
            material,
            unreal.MaterialExpressionLinearInterpolate,
            780,
            -300,
        )
        connect(tint_multiply, "", macro_blend, "A")
        connect(worn_base, "", macro_blend, "B")
        age_strength = constant_scalar(material, 0.20, 530, -650)
        age_alpha = expression(
            material,
            unreal.MaterialExpressionMultiply,
            720,
            -610,
        )
        safe_set(age_alpha, "desc", "OTS_WALL_AGE_ALPHA")
        connect(macro_noise, "", age_alpha, "A")
        connect(age_strength, "", age_alpha, "B")
        connect(age_alpha, "", macro_blend, "Alpha")
        final_base = macro_blend

    connect_property(
        final_base,
        "",
        unreal.MaterialProperty.MP_BASE_COLOR,
    )
    connect_property(
        normal_node,
        normal_output,
        unreal.MaterialProperty.MP_NORMAL,
    )

    rough_scale = constant_scalar(
        material,
        roughness_multiplier,
        -210,
        250,
    )
    rough_multiply = expression(
        material,
        unreal.MaterialExpressionMultiply,
        60,
        230,
    )
    connect(rough_node, rough_output, rough_multiply, "A")
    connect(rough_scale, "", rough_multiply, "B")
    connect_property(
        rough_multiply,
        "",
        unreal.MaterialProperty.MP_ROUGHNESS,
    )

    metallic_node = constant_scalar(
        material,
        metallic,
        60,
        390,
    )
    connect_property(
        metallic_node,
        "",
        unreal.MaterialProperty.MP_METALLIC,
    )

    unreal.MaterialEditingLibrary.recompile_material(material)
    require(
        unreal.EditorAssetLibrary.save_loaded_asset(material, False),
        "Unable to save material {}".format(name),
    )
    return material


def create_flat_material(
    name,
    color,
    roughness,
    metallic=0.0,
    emissive_color=None,
    emissive_strength=0.0,
):
    material = create_material_asset(name)
    color_node = constant_color(material, color, -400, -120)
    rough_node = constant_scalar(material, roughness, -400, 100)
    metal_node = constant_scalar(material, metallic, -400, 220)
    connect_property(
        color_node,
        "",
        unreal.MaterialProperty.MP_BASE_COLOR,
    )
    connect_property(
        rough_node,
        "",
        unreal.MaterialProperty.MP_ROUGHNESS,
    )
    connect_property(
        metal_node,
        "",
        unreal.MaterialProperty.MP_METALLIC,
    )
    if emissive_color is not None and emissive_strength > 0.0:
        emissive = constant_color(
            material,
            emissive_color,
            -400,
            -300,
        )
        strength = constant_scalar(
            material,
            emissive_strength,
            -400,
            -420,
        )
        multiply = expression(
            material,
            unreal.MaterialExpressionMultiply,
            -80,
            -340,
        )
        connect(emissive, "", multiply, "A")
        connect(strength, "", multiply, "B")
        connect_property(
            multiply,
            "",
            unreal.MaterialProperty.MP_EMISSIVE_COLOR,
        )
    unreal.MaterialEditingLibrary.recompile_material(material)
    require(
        unreal.EditorAssetLibrary.save_loaded_asset(material, False),
        "Unable to save material {}".format(name),
    )
    return material


def create_scene_materials(textures):
    materials = {}
    materials["M_OTS_WetAsphalt"] = create_textured_material(
        "M_OTS_WetAsphalt",
        textures["T_OTS_Asphalt_BaseColor"],
        textures["T_OTS_Asphalt_Normal"],
        textures["T_OTS_Asphalt_Roughness"],
        (0.64, 0.67, 0.70, 1.0),
        220.0,
        0.74,
        True,
        macro_size_cm=920.0,
    )
    materials["M_OTS_OldConcrete"] = create_textured_material(
        "M_OTS_OldConcrete",
        textures["T_OTS_PaintedPlaster_BaseColor"],
        textures["T_OTS_PaintedPlaster_Normal"],
        textures["T_OTS_PaintedPlaster_Roughness"],
        (0.60, 0.59, 0.54, 1.0),
        210.0,
        1.05,
        True,
        1.618,
        2350.0,
        secondary_texture=textures["T_OTS_Concrete_BaseColor"],
        secondary_size_cm=1670.0,
    )
    materials["M_OTS_Sidewalk"] = create_textured_material(
        "M_OTS_Sidewalk",
        textures["T_OTS_Concrete_BaseColor"],
        textures["T_OTS_Concrete_Normal"],
        textures["T_OTS_Concrete_Roughness"],
        (0.42, 0.46, 0.48, 1.0),
        140.0,
        1.05,
        True,
        macro_size_cm=1150.0,
    )
    materials["M_OTS_SchoolWall"] = create_textured_material(
        "M_OTS_SchoolWall",
        textures["T_OTS_PaintedPlaster_BaseColor"],
        textures["T_OTS_PaintedPlaster_Normal"],
        textures["T_OTS_PaintedPlaster_Roughness"],
        (0.55, 0.57, 0.52, 1.0),
        245.0,
        0.92,
        True,
        1.327,
        1850.0,
        secondary_texture=textures["T_OTS_Concrete_BaseColor"],
        secondary_size_cm=1430.0,
    )
    materials["M_OTS_FadedBlueWall"] = create_textured_material(
        "M_OTS_FadedBlueWall",
        textures["T_OTS_PaintedPlaster_BaseColor"],
        textures["T_OTS_PaintedPlaster_Normal"],
        textures["T_OTS_PaintedPlaster_Roughness"],
        (0.34, 0.40, 0.42, 1.0),
        225.0,
        1.08,
        True,
        1.414,
        1750.0,
    )
    materials["M_OTS_FadedGreenWall"] = create_textured_material(
        "M_OTS_FadedGreenWall",
        textures["T_OTS_PaintedPlaster_BaseColor"],
        textures["T_OTS_PaintedPlaster_Normal"],
        textures["T_OTS_PaintedPlaster_Roughness"],
        (0.36, 0.39, 0.33, 1.0),
        280.0,
        1.10,
        True,
        1.732,
        2700.0,
    )
    materials["M_OTS_OldGreenMetal"] = create_textured_material(
        "M_OTS_OldGreenMetal",
        textures["T_OTS_GreenMetalRust_BaseColor"],
        textures["T_OTS_GreenMetalRust_Normal"],
        textures["T_OTS_GreenMetalRust_Roughness"],
        (0.60, 0.70, 0.60, 1.0),
        120.0,
        1.0,
        metallic=0.24,
    )
    # The same free rusted-sheet PBR is tinted into three historically
    # compatible paint batches.  This keeps a coherent material response but
    # prevents every shutter on the street reading as the same green module.
    materials["M_OTS_FadedBlueMetal"] = create_textured_material(
        "M_OTS_FadedBlueMetal",
        textures["T_OTS_GreenMetalRust_BaseColor"],
        textures["T_OTS_GreenMetalRust_Normal"],
        textures["T_OTS_GreenMetalRust_Roughness"],
        (0.34, 0.48, 0.58, 1.0),
        128.0,
        1.04,
        metallic=0.22,
    )
    materials["M_OTS_FadedRedMetal"] = create_textured_material(
        "M_OTS_FadedRedMetal",
        textures["T_OTS_GreenMetalRust_BaseColor"],
        textures["T_OTS_GreenMetalRust_Normal"],
        textures["T_OTS_GreenMetalRust_Roughness"],
        (0.62, 0.37, 0.25, 1.0),
        116.0,
        1.06,
        metallic=0.20,
    )
    flat_specs = {
        "M_OTS_RedBrick": ((0.32, 0.14, 0.095, 1.0), 0.92, 0.0),
        "M_OTS_DarkTrim": ((0.045, 0.055, 0.052, 1.0), 0.72, 0.05),
        "M_OTS_RustMetal": ((0.12, 0.065, 0.035, 1.0), 0.90, 0.28),
        "M_OTS_DarkGlass": ((0.028, 0.038, 0.042, 1.0), 0.30, 0.02),
        "M_OTS_Stain": ((0.20, 0.18, 0.15, 1.0), 0.96, 0.0),
        "M_OTS_RoadMarking": ((0.42, 0.40, 0.33, 1.0), 0.86, 0.0),
        "M_OTS_Puddle": ((0.020, 0.036, 0.050, 1.0), 0.16, 0.0),
        "M_OTS_BlackWire": ((0.008, 0.009, 0.010, 1.0), 0.62, 0.2),
        "M_OTS_Cardboard": ((0.26, 0.16, 0.075, 1.0), 0.93, 0.0),
        "M_OTS_DarkGround": ((0.095, 0.105, 0.105, 1.0), 0.94, 0.0),
        "M_OTS_FadedRedSign": ((0.18, 0.055, 0.035, 1.0), 0.95, 0.0),
        "M_OTS_FadedBlueSign": ((0.035, 0.075, 0.095, 1.0), 0.95, 0.0),
        "M_OTS_FadedOchreSign": ((0.18, 0.125, 0.05, 1.0), 0.96, 0.0),
        "M_OTS_OldGreenSign": ((0.065, 0.105, 0.070, 1.0), 0.95, 0.0),
        "M_OTS_StorefrontShadow": ((0.055, 0.062, 0.050, 1.0), 0.86, 0.03),
    }
    for name, (color, roughness, metallic) in flat_specs.items():
        materials[name] = create_flat_material(
            name,
            color,
            roughness,
            metallic,
        )
    # Wet patches share the road's world-space aggregate and colour, instead
    # of reading as opaque blue discs.  Only their surface roughness changes.
    materials["M_OTS_Puddle"] = create_textured_material(
        "M_OTS_Puddle",
        textures["T_OTS_Asphalt_BaseColor"],
        textures["T_OTS_Asphalt_Normal"],
        textures["T_OTS_Asphalt_Roughness"],
        (0.54, 0.57, 0.61, 1.0),
        220.0,
        0.25,
        True,
        macro_size_cm=920.0,
    )
    materials["M_OTS_WarmWindow"] = create_flat_material(
        "M_OTS_WarmWindow",
        (0.045, 0.032, 0.016, 1.0),
        0.30,
        0.0,
        (0.65, 0.30, 0.08, 1.0),
        0.12,
    )
    materials["M_OTS_CoolWindow"] = create_flat_material(
        "M_OTS_CoolWindow",
        (0.018, 0.030, 0.034, 1.0),
        0.30,
        0.0,
        (0.20, 0.42, 0.46, 1.0),
        0.08,
    )
    materials["M_OTS_NeutralWindow"] = create_flat_material(
        "M_OTS_NeutralWindow",
        (0.025, 0.028, 0.024, 1.0),
        0.34,
        0.0,
        (0.44, 0.39, 0.25, 1.0),
        0.075,
    )
    materials["M_OTS_FluorescentTube"] = create_flat_material(
        "M_OTS_FluorescentTube",
        (0.06, 0.075, 0.065, 1.0),
        0.32,
        0.0,
        (0.48, 0.58, 0.46, 1.0),
        0.10,
    )
    require(
        set(MATERIAL_NAMES).issubset(materials),
        "Material set is incomplete",
    )
    log("Created or updated {} scene materials".format(len(materials)))
    return materials


def import_pole_meshes():
    if not POLE_FBX.is_file():
        warn("Poly Haven pole FBX is missing; procedural poles will be used")
        return []
    existing_meshes = []
    for path in unreal.EditorAssetLibrary.list_assets(
        POLE_ROOT,
        True,
        False,
    ):
        asset = load_asset(path, required=False)
        if isinstance(asset, unreal.StaticMesh):
            existing_meshes.append(asset)
    if len(existing_meshes) >= 20:
        log(
            "Reusing {} imported modular electricity-pole meshes".format(
                len(existing_meshes)
            )
        )
        return existing_meshes
    try:
        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_as_skeletal", False)
        options.set_editor_property("import_animations", False)
        options.set_editor_property("import_materials", False)
        options.set_editor_property("import_textures", False)
        static_data = options.get_editor_property("static_mesh_import_data")
        safe_set(static_data, "combine_meshes", False)
        safe_set(static_data, "build_nanite", False)
        safe_set(static_data, "generate_lightmap_u_vs", True)
        safe_set(static_data, "auto_generate_collision", False)

        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(POLE_FBX))
        task.set_editor_property("destination_path", POLE_ROOT)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("replace_existing_settings", True)
        task.set_editor_property("save", False)
        task.set_editor_property("options", options)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        meshes = []
        for path in unreal.EditorAssetLibrary.list_assets(
            POLE_ROOT,
            True,
            False,
        ):
            asset = load_asset(path, required=False)
            if isinstance(asset, unreal.StaticMesh):
                unreal.EditorAssetLibrary.save_loaded_asset(asset, False)
                meshes.append(asset)
        log("Imported {} modular electricity-pole meshes".format(len(meshes)))
        return meshes
    except Exception as exc:
        warn("FBX import failed; procedural poles will be used: {}".format(exc))
        return []


def ensure_detailed_prop_assets():
    """Build/update the P2, P3 and player-range P5 mesh libraries."""
    module_path = PROJECT_ROOT / "Scripts/CreateOldTownDetailedProps.py"
    require(
        module_path.is_file(),
        "Missing detailed prop generator: {}".format(module_path),
    )
    spec = importlib.util.spec_from_file_location(
        "CreateOldTownDetailedProps",
        str(module_path),
    )
    require(spec is not None and spec.loader is not None, "P2 module load failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assets = module.ensure_detailed_prop_assets()
    required_names = {
        "VendorTable",
        "Thermos",
        "ChineseStool",
        "Toolbox",
        "GasCylinder",
        "Broom",
        "ChestFreezer",
        "OutdoorSink",
        "TrashBin",
        "PlantPot",
        "CardboardBox",
        "AlleyBench",
        "WashBasin",
        "ACUnit",
        "MeterBox",
        "Bicycle",
        "WallUtilityCluster",
        "StreetLamp",
        "StormDrain",
        "PuddlePatch",
    }
    require(
        required_names.issubset(assets),
        "Detailed prop library is incomplete: {}".format(
            ", ".join(sorted(required_names.difference(assets)))
        ),
    )
    for name in required_names:
        mesh = assets[name]
        require(
            isinstance(mesh, unreal.StaticMesh),
            "Detailed prop {} is not a StaticMesh".format(name),
        )
        require(
            mesh.get_path_name().startswith(DETAILED_PROP_ROOT + "/"),
            "Detailed prop {} came from unexpected path {}".format(
                name,
                mesh.get_path_name(),
            ),
        )
    p3_assets = module.ensure_p3_module_assets()
    required_p3_names = {
        "StaticShutter",
        "SignAssembly",
        "AwningAssembly",
        "SchoolGateLeaf",
        "SchoolGatePost",
        "AlleyCrossbar",
        "SignTextSnack",
        "SignTextGeneral",
        "SignTextRepair",
        "SignTextHardware",
    }
    require(
        required_p3_names == set(p3_assets),
        "P3 street module library is incomplete",
    )
    for name in required_p3_names:
        mesh = p3_assets[name]
        require(
            isinstance(mesh, unreal.StaticMesh),
            "P3 module {} is not a StaticMesh".format(name),
        )
        require(
            mesh.get_path_name().startswith(P3_PROP_ROOT + "/"),
            "P3 module {} came from unexpected path {}".format(
                name,
                mesh.get_path_name(),
            ),
        )
    p5_assets = module.ensure_p5_module_assets()
    required_p5_names = {
        "LoadedLaundryRack",
        "OldServiceDoorTransom",
        "WallLampGooseneck",
        "ShopShelfStocked",
        "CounterDisplay",
        "TallPharmacyCabinet",
    }
    require(
        required_p5_names == set(p5_assets),
        "P5 player-range module library is incomplete",
    )
    for name in required_p5_names:
        mesh = p5_assets[name]
        require(
            isinstance(mesh, unreal.StaticMesh),
            "P5 module {} is not a StaticMesh".format(name),
        )
        require(
            mesh.get_path_name().startswith(P5_PROP_ROOT + "/"),
            "P5 module {} came from unexpected path {}".format(
                name,
                mesh.get_path_name(),
            ),
        )
    assets.update(p3_assets)
    assets.update(p5_assets)
    log(
        "Prepared {} P2 props, {} P3 modules and {} P5 modules".format(
            len(required_names),
            len(p3_assets),
            len(p5_assets),
        )
    )
    return assets


def ensure_architectural_module_assets():
    """Build or update the reusable residential and school window meshes."""
    module_path = (
        PROJECT_ROOT / "Scripts/CreateOldTownArchitecturalModules.py"
    )
    require(
        module_path.is_file(),
        "Missing architectural module generator: {}".format(module_path),
    )
    spec = importlib.util.spec_from_file_location(
        "CreateOldTownArchitecturalModules",
        str(module_path),
    )
    require(
        spec is not None and spec.loader is not None,
        "Architectural module load failed",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assets = module.ensure_architectural_module_assets()
    required_names = {"ResidentialWindow", "SchoolWindow"}
    require(
        required_names.issubset(assets),
        "Architectural module library is incomplete: {}".format(
            ", ".join(sorted(required_names.difference(assets)))
        ),
    )
    for name in required_names:
        mesh = assets[name]
        require(
            isinstance(mesh, unreal.StaticMesh),
            "Architectural module {} is not a StaticMesh".format(name),
        )
        require(
            mesh.get_path_name().startswith(
                ARCHITECTURAL_MODULE_ROOT + "/"
            ),
            "Architectural module {} came from unexpected path {}".format(
                name,
                mesh.get_path_name(),
            ),
        )
    log("Prepared {} reusable architectural modules".format(len(assets)))
    return assets


def create_target_level():
    level_subsystem = unreal.get_editor_subsystem(
        unreal.LevelEditorSubsystem
    )
    require(level_subsystem is not None, "LevelEditorSubsystem is unavailable")
    require(
        level_subsystem.load_level(SOURCE_LEVEL),
        "Unable to load source level {}".format(SOURCE_LEVEL),
    )
    if asset_exists(TARGET_LEVEL):
        require(
            unreal.EditorAssetLibrary.delete_asset(TARGET_LEVEL),
            "Unable to delete old target level {}".format(TARGET_LEVEL),
        )
    require(
        level_subsystem.new_level_from_template(
            TARGET_LEVEL,
            SOURCE_LEVEL,
        ),
        "Unable to create target level from template",
    )
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    require(world is not None, "Target editor world was not created")
    require(
        world.get_path_name().startswith(TARGET_LEVEL + "."),
        "Refusing to edit unexpected world {}".format(
            world.get_path_name(),
        ),
    )
    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    count = len(actor_subsystem.get_all_level_actors())
    require(
        count >= 70,
        "Template copy lost actors; expected at least 70, got {}".format(count),
    )
    log("Created independent target level with {} actors".format(count))
    return level_subsystem, actor_subsystem


def set_generated_metadata(actor, label, folder):
    actor.set_actor_label(label)
    actor.set_folder_path(unreal.Name(folder))
    actor.set_editor_property("tags", [unreal.Name(GENERATOR_TAG)])


def spawn_mesh_actor(
    actor_subsystem,
    mesh,
    label,
    location,
    size_cm,
    material,
    rotation=(0.0, 0.0, 0.0),
    collision=False,
    folder=FOLDER_ROOT + "/Details",
    cast_shadow=True,
):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(*location),
        make_rotator(rotation),
        False,
    )
    require(actor is not None, "Unable to spawn {}".format(label))
    set_generated_metadata(actor, label, folder)
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    require(component is not None, "{} has no StaticMeshComponent".format(label))
    require(component.set_static_mesh(mesh) is not False, "Mesh set failed")
    actor.set_actor_scale3d(
        unreal.Vector(
            float(size_cm[0]) / 100.0,
            float(size_cm[1]) / 100.0,
            float(size_cm[2]) / 100.0,
        )
    )
    component.set_material(0, material)
    safe_set(component, "mobility", unreal.ComponentMobility.STATIC)
    safe_set(component, "cast_shadow", bool(cast_shadow))
    actor.set_actor_enable_collision(bool(collision))
    component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS
        if collision
        else unreal.CollisionEnabled.NO_COLLISION
    )
    return actor


def spawn_native_prop(
    actor_subsystem,
    mesh,
    prefix,
    location,
    rotation=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
    collision=False,
    folder=FOLDER_ROOT + "/P2/DetailedProps",
):
    """Place a centimetre-authored prop without Cube-style size scaling."""
    label = unique_label(prefix)
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(*location),
        make_rotator(rotation),
        False,
    )
    require(actor is not None, "Unable to spawn {}".format(label))
    set_generated_metadata(actor, label, folder)
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    require(component is not None, "{} has no StaticMeshComponent".format(label))
    require(component.set_static_mesh(mesh) is not False, "Mesh set failed")
    actor.set_actor_scale3d(unreal.Vector(*scale))
    safe_set(component, "mobility", unreal.ComponentMobility.STATIC)
    safe_set(component, "cast_shadow", True)
    actor.set_actor_enable_collision(bool(collision))
    component.set_collision_enabled(
        unreal.CollisionEnabled.QUERY_AND_PHYSICS
        if collision
        else unreal.CollisionEnabled.NO_COLLISION
    )
    return actor


def spawn_architectural_window(
    actor_subsystem,
    architectural_modules,
    materials,
    module_name,
    prefix,
    location,
    rotation,
    scale,
    glass_material_name,
    folder,
):
    """Place one multi-material window module with no gameplay collision."""
    require(
        module_name in architectural_modules,
        "Missing architectural window module {}".format(module_name),
    )
    actor = spawn_native_prop(
        actor_subsystem,
        architectural_modules[module_name],
        prefix,
        location,
        rotation,
        scale,
        False,
        folder,
    )
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    require(
        component is not None,
        "{} has no StaticMeshComponent".format(actor.get_actor_label()),
    )
    # These indices are the stable slot contract owned by
    # CreateOldTownArchitecturalModules.py.
    slot_materials = (
        "M_OTS_DarkTrim",
        glass_material_name,
        "M_OTS_OldConcrete",
        "M_OTS_RustMetal",
        "M_OTS_DarkTrim",
    )
    for slot_index, material_name in enumerate(slot_materials):
        component.set_material(slot_index, materials[material_name])
    actor.set_actor_enable_collision(False)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return actor


def spawn_cube(
    actor_subsystem,
    meshes,
    materials,
    prefix,
    location,
    size_cm,
    material_name,
    rotation=(0.0, 0.0, 0.0),
    collision=False,
    folder=FOLDER_ROOT + "/Details",
    cast_shadow=True,
):
    return spawn_mesh_actor(
        actor_subsystem,
        meshes["cube"],
        unique_label(prefix),
        location,
        size_cm,
        materials[material_name],
        rotation,
        collision,
        folder,
        cast_shadow,
    )


def spawn_cylinder(
    actor_subsystem,
    meshes,
    materials,
    prefix,
    location,
    diameter_cm,
    height_cm,
    material_name,
    collision=False,
    folder=FOLDER_ROOT + "/Details",
):
    return spawn_mesh_actor(
        actor_subsystem,
        meshes["cylinder"],
        unique_label(prefix),
        location,
        (diameter_cm, diameter_cm, height_cm),
        materials[material_name],
        (0.0, 0.0, 0.0),
        collision,
        folder,
    )


def look_at_rotation(origin, target):
    dx = float(target[0]) - float(origin[0])
    dy = float(target[1]) - float(origin[1])
    dz = float(target[2]) - float(origin[2])
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return (pitch, yaw, 0.0)


def spawn_beam_between(
    actor_subsystem,
    meshes,
    materials,
    prefix,
    start,
    end,
    thickness_cm,
    material_name,
    folder=FOLDER_ROOT + "/Utilities",
):
    midpoint = tuple(
        (float(start[index]) + float(end[index])) * 0.5
        for index in range(3)
    )
    length = math.sqrt(
        sum(
            (float(end[index]) - float(start[index])) ** 2
            for index in range(3)
        )
    )
    return spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        prefix,
        midpoint,
        (length, thickness_cm, thickness_cm),
        material_name,
        look_at_rotation(start, end),
        False,
        folder,
        False,
    )


def assign_existing_materials(actor_subsystem, materials):
    changed = 0
    for actor in actor_subsystem.get_all_level_actors():
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if component is None:
            continue
        label = actor.get_actor_label()
        material_name = None
        if label in ("Blockout_MainRoad", "Blockout_TJunctionRoad"):
            material_name = "M_OTS_WetAsphalt"
        elif label == "Plane":
            material_name = "M_OTS_DarkGround"
        elif any(
            token in label
            for token in (
                "Sidewalk",
                "_Floor",
                "SchoolGround",
                "SchoolFront_Apron",
            )
        ) or (
            label.startswith("BLK_")
            and not any(
                token in label
                for token in (
                    "_Mass",
                    "_Shutter",
                    "_Sign",
                    "_Door",
                    "_Window",
                    "_Storefront",
                    "EndWall",
                )
            )
        ):
            material_name = "M_OTS_Sidewalk"
        elif label.startswith("Blockout_School"):
            material_name = "M_OTS_SchoolWall"
        elif "Shutter" in label:
            material_name = "M_OTS_OldGreenMetal"
        elif "Sign" in label:
            sign_palette = (
                "M_OTS_FadedRedSign",
                "M_OTS_FadedBlueSign",
                "M_OTS_FadedOchreSign",
                "M_OTS_OldGreenSign",
                "M_OTS_FadedBlueSign",
                "M_OTS_FadedRedSign",
                "M_OTS_FadedOchreSign",
            )
            location = actor.get_actor_location()
            side_offset = 0 if location.y < 0.0 else 2
            palette_index = (
                int(abs(location.x) // 300.0) + side_offset
            ) % len(sign_palette)
            material_name = sign_palette[palette_index]
        elif "Window" in label:
            material_name = "M_OTS_DarkGlass"
        elif "Storefront" in label:
            material_name = "M_OTS_StorefrontShadow"
        elif "Door" in label:
            material_name = "M_OTS_OldGreenMetal"
        elif "_Mass" in label or "EndWall" in label:
            if "_R_" in label:
                material_name = (
                    "M_OTS_FadedGreenWall"
                    if ("ResShell" in label or "Back" in label)
                    else "M_OTS_OldConcrete"
                )
            else:
                material_name = (
                    "M_OTS_FadedBlueWall"
                    if ("Back" in label or "Filler_02" in label)
                    else "M_OTS_OldConcrete"
                )
        elif "RoadBarrier" in label:
            material_name = "M_OTS_RedBrick"
        if material_name is not None:
            component.set_material(0, materials[material_name])
            changed += 1
    log("Reassigned materials on {} blockout actors".format(changed))


def remove_replaced_actors(actor_subsystem):
    targets = []
    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if label.startswith("BLK_R_Filler_01") or label == (
            "Blockout_SchoolGate_Closed"
        ) or label == "Plane":
            targets.append(actor)
    require(
        len([a for a in targets if a.get_actor_label().startswith(
            "BLK_R_Filler_01"
        )]) == 4,
        "Expected exactly four right filler actors",
    )
    require(
        actor_subsystem.destroy_actors(targets),
        "Unable to remove replaced blockout actors",
    )
    log("Removed {} replaced blockout actors".format(len(targets)))


def spawn_main_home(actor_subsystem):
    log("Spawning interactive MainHome blueprint")
    blueprint = load_asset(MAIN_HOME_BP)
    generated_class = blueprint.generated_class()
    require(generated_class is not None, "MainHome blueprint has no class")
    actor = actor_subsystem.spawn_actor_from_class(
        generated_class,
        unreal.Vector(1025.0, 920.0, 0.0),
        make_rotator((0.0, 0.0, 0.0)),
        False,
    )
    require(actor is not None, "Unable to spawn BP_MainHomeInteractive")
    log("Interactive MainHome blueprint spawned")
    set_generated_metadata(
        actor,
        "BP_OTS_MainHomeInteractive",
        FOLDER_ROOT + "/HeroShop",
    )
    # The four source meshes already have dedicated bounds/collision tests.
    # Avoid querying render bounds here: UE 5.7's NullRHI editor path can divide
    # by zero while calculating screen-size-dependent static-mesh bounds.
    return actor


def add_main_home_interior_details(
    actor_subsystem,
    meshes,
    materials,
    detailed_props,
    main_home,
):
    """Give the interactive shell a readable, uncluttered walk-in interior."""
    location = main_home.get_actor_location()
    require(
        abs(location.x - 1025.0) < 0.1
        and abs(location.y - 920.0) < 0.1,
        "MainHome interior layout requires the approved world transform",
    )
    for prefix, location, size, material_name in (
        (
            "OTS_MainHomeBaseboardLeft",
            (800.0, 920.0, 25.0),
            (6.0, 720.0, 28.0),
            "M_OTS_Stain",
        ),
        (
            "OTS_MainHomeBaseboardRight",
            (1250.0, 920.0, 25.0),
            (6.0, 720.0, 28.0),
            "M_OTS_Stain",
        ),
        (
            "OTS_MainHomeBaseboardBack",
            (1025.0, 1292.0, 25.0),
            (440.0, 6.0, 28.0),
            "M_OTS_Stain",
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            material_name,
            folder=FOLDER_ROOT + "/HeroShop/Interior",
            cast_shadow=not prefix.startswith("OTS_MainHomeBaseboard"),
        )

    # Replace the previous floating bars and repeated cardboard cubes with one
    # centimetre-authored stocked shelf.  Its bounds are X=880..1170 and
    # Y=1248..1282, leaving the 450 cm-wide customer aisle intact; it remains
    # collision-free so it cannot alter MainHome's approved interaction route.
    spawn_native_prop(
        actor_subsystem,
        detailed_props["ShopShelfStocked"],
        "OTS_P5Prop_MainHomeShopShelf",
        (1025.0, 1265.0, 80.0),
        (0.0, 0.0, 0.0),
        (1.0, 1.0, 1.0),
        False,
        FOLDER_ROOT + "/P5/MainHomeInterior",
    )
    # A narrow glazed medicine cabinet fills the rear-right return rather than
    # the customer aisle.  At X=1216/Y=1280 its rear stays 2 cm inside the
    # wall envelope and its front remains behind the counter line.
    spawn_native_prop(
        actor_subsystem,
        detailed_props["TallPharmacyCabinet"],
        "OTS_P5Prop_MainHomeTallPharmacyCabinet",
        (1216.0, 1280.0, 10.0),
        (0.0, 0.0, 0.0),
        (1.0, 1.0, 1.0),
        False,
        FOLDER_ROOT + "/P5/MainHomeInterior",
    )
    # Two manufactured counter modules replace the former 300 cm featureless
    # Cube.  Their rounded timber tops, metal edge bands, framed legs, lower
    # slatted shelves, drawers and real handles remain readable at first-person
    # inspection distance.  The modules meet in the middle and keep the same
    # overall counter footprint and blocking behaviour.
    for suffix, x in (("Left", 948.0), ("Right", 1102.0)):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["VendorTable"],
            "OTS_MainHomeCounter{}".format(suffix),
            (x, 1195.0, 10.0),
            (0.0, 0.0, 0.0),
            (1.29, 1.05, 1.25),
            True,
            FOLDER_ROOT + "/HeroShop/Interior/Counter",
        )

    # Two small register/scale assemblies stay wholly on the counter tops.
    # They add inspectable shop furniture while avoiding the middle seam and
    # leaving the door-to-counter clearance unchanged.
    counter_top_z = 10.0 + 79.5 * 1.25
    lower_shelf_z = 10.0 + 25.75 * 1.25
    for suffix, x, yaw in (("Left", 948.0, 0.0), ("Right", 1102.0, 0.0)):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["CounterDisplay"],
            "OTS_P5Prop_MainHomeCounterDisplay" + suffix,
            (x, 1195.0, counter_top_z - 0.20),
            (0.0, yaw, 0.0),
            (0.72, 0.72, 0.72),
            False,
            FOLDER_ROOT + "/P5/MainHomeInterior",
        )
    for index, y in enumerate((850.0, 1120.0)):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_MainHomeCeilingTube{:02d}".format(index + 1),
            (1025.0, y, 343.0),
            (130.0, 18.0, 5.0),
            "M_OTS_WarmWindow",
            folder=FOLDER_ROOT + "/HeroShop/Interior",
            cast_shadow=False,
        )

    # Use the centimetre-authored prop library for the objects the player can
    # inspect at arm's length.  The centre aisle and both entrances remain
    # clear; small loose objects deliberately have no collision.
    for asset_name, prefix, location, rotation, scale in (
        (
            "CardboardBox",
            "OTS_MainHomeProp_CounterBoxLeft",
            (915.0, 1195.0, lower_shelf_z - 0.20),
            (0.0, 0.0, 0.0),
            (0.50, 0.50, 0.50),
        ),
        (
            "CardboardBox",
            "OTS_MainHomeProp_CounterBoxRight",
            (1120.0, 1195.0, lower_shelf_z - 0.20),
            (0.0, 0.0, 0.0),
            (0.62, 0.58, 0.58),
        ),
        (
            "Thermos",
            "OTS_MainHomeProp_Thermos",
            (995.0, 1195.0, counter_top_z - 0.20),
            (0.0, 0.0, 0.0),
            (0.72, 0.72, 0.72),
        ),
        (
            "Toolbox",
            "OTS_MainHomeProp_Toolbox",
            (980.0, 1195.0, lower_shelf_z - 0.20),
            (0.0, 0.0, 0.0),
            (0.70, 0.70, 0.70),
        ),
        (
            "ChineseStool",
            "OTS_MainHomeProp_Stool",
            (1212.0, 1050.0, 10.0),
            (0.0, -12.0, 0.0),
            (0.88, 0.88, 0.88),
        ),
        (
            "Broom",
            "OTS_MainHomeProp_Broom",
            (820.0, 1244.0, 10.0),
            (0.0, 7.0, -8.0),
            (0.94, 0.94, 0.94),
        ),
        (
            "PlantPot",
            "OTS_MainHomeProp_PlantPot",
            (1218.0, 1235.0, 10.0),
            (0.0, 14.0, 0.0),
            (0.66, 0.66, 0.72),
        ),
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props[asset_name],
            prefix,
            location,
            rotation,
            scale,
            False,
            FOLDER_ROOT + "/HeroShop/Interior/Props",
        )
    log("Added readable MainHome interior fixtures, shelving, and props")


def add_main_home_school_side_details(
    actor_subsystem,
    meshes,
    materials,
):
    """Break up the shop wall visible from the school-gate hero view.

    The MainHome west envelope begins at world X=775 cm.  Every layer below
    stays at or behind that plane, so these details improve the approach view
    without expanding the approved 500 cm building width.
    """
    folder = FOLDER_ROOT + "/HeroShop/SchoolSide"
    for prefix, location, size, material_name in (
        (
            "OTS_MainHomeWestWindowGlass",
            (776.25, 800.0, 210.0),
            (0.5, 94.0, 76.0),
            "M_OTS_DarkGlass",
        ),
        (
            "OTS_MainHomeWestWindowTop",
            (775.5, 800.0, 252.0),
            (1.0, 110.0, 8.0),
            "M_OTS_DarkTrim",
        ),
        (
            "OTS_MainHomeWestWindowBottom",
            (775.5, 800.0, 168.0),
            (1.0, 110.0, 8.0),
            "M_OTS_DarkTrim",
        ),
        (
            "OTS_MainHomeWestWindowFront",
            (775.5, 749.0, 210.0),
            (1.0, 8.0, 76.0),
            "M_OTS_DarkTrim",
        ),
        (
            "OTS_MainHomeWestWindowBack",
            (775.5, 851.0, 210.0),
            (1.0, 8.0, 76.0),
            "M_OTS_DarkTrim",
        ),
        (
            "OTS_MainHomeWestDampPatch",
            (775.5, 920.0, 55.0),
            (1.0, 110.0, 55.0),
            "M_OTS_Stain",
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            material_name,
            folder=folder,
            cast_shadow=False,
        )
    log("Added bounded school-side MainHome facade details")


def add_window_y(
    actor_subsystem,
    meshes,
    materials,
    prefix,
    x,
    wall_y,
    z,
    width,
    height,
    outward,
    lit=False,
    cool=False,
    architectural_modules=None,
):
    """Place one reusable residential window on a Y-facing facade."""
    require(
        architectural_modules is not None,
        "{} requires architectural window modules".format(prefix),
    )
    glass_material = (
        "M_OTS_CoolWindow"
        if cool
        else "M_OTS_WarmWindow"
        if lit
        else "M_OTS_DarkGlass"
    )
    # Window assets face local -Y.  A 180-degree yaw turns them toward +Y.
    yaw = 0.0 if outward < 0.0 else 180.0
    return spawn_architectural_window(
        actor_subsystem,
        architectural_modules,
        materials,
        "ResidentialWindow",
        prefix,
        (x, wall_y, z),
        (0.0, yaw, 0.0),
        (float(width) / 125.0, 1.0, float(height) / 120.0),
        glass_material,
        FOLDER_ROOT + "/FacadeWindows",
    )


def add_window_x(
    actor_subsystem,
    meshes,
    materials,
    prefix,
    wall_x,
    y,
    z,
    width_y,
    height,
    outward_x,
    lit=False,
    lit_material=None,
    architectural_modules=None,
    module_name="SchoolWindow",
    folder=None,
):
    """Place one reusable window module on an X-facing facade."""
    require(
        architectural_modules is not None,
        "{} requires architectural window modules".format(prefix),
    )
    module_opening_size = {
        "ResidentialWindow": (125.0, 120.0),
        "SchoolWindow": (200.0, 150.0),
    }
    require(
        module_name in module_opening_size,
        "Unknown architectural window style {}".format(module_name),
    )
    nominal_width, nominal_height = module_opening_size[module_name]
    glass_material = (
        lit_material
        if lit and lit_material is not None
        else "M_OTS_CoolWindow"
        if lit
        else "M_OTS_DarkGlass"
    )
    # Local -Y rotated +90 degrees faces +X; -90 degrees faces -X.
    yaw = 90.0 if outward_x > 0.0 else -90.0
    return spawn_architectural_window(
        actor_subsystem,
        architectural_modules,
        materials,
        module_name,
        prefix,
        (wall_x, y, z),
        (0.0, yaw, 0.0),
        (
            float(width_y) / nominal_width,
            1.0,
            float(height) / nominal_height,
        ),
        glass_material,
        folder if folder is not None else FOLDER_ROOT + "/SchoolWindows",
    )


def add_facade_windows(
    actor_subsystem,
    meshes,
    materials,
    architectural_modules,
):
    facade_specs = (
        ("R_D", 1875.0, 530.0, -1.0, 950.0, (520.0, 820.0), 3),
        ("R_Res", 3240.0, 530.0, -1.0, 900.0, (520.0, 820.0, 1120.0, 1420.0), 3),
        ("R_B", 4340.0, 530.0, -1.0, 1000.0, (520.0, 820.0, 1120.0), 4),
        ("R_Back", 5390.0, 530.0, -1.0, 800.0, (520.0, 820.0, 1120.0, 1420.0, 1680.0), 3),
        ("L_C", 1900.0, -530.0, 1.0, 900.0, (520.0, 820.0, 1080.0), 3),
        ("L_A", 4090.0, -530.0, 1.0, 1000.0, (520.0, 820.0, 1120.0, 1380.0), 4),
        ("L_Back", 5190.0, -530.0, 1.0, 900.0, (520.0, 820.0, 1120.0, 1420.0, 1680.0), 3),
    )
    window_index = 0
    for name, center_x, wall_y, outward, total_width, rows, columns in facade_specs:
        spacing = total_width / float(columns)
        for row_index, z in enumerate(rows):
            for column in range(columns):
                window_index += 1
                x = (
                    center_x
                    - total_width * 0.5
                    + spacing * (column + 0.5)
                )
                add_window_y(
                    actor_subsystem,
                    meshes,
                    materials,
                    "OTS_Window_{}_R{}_C{}".format(
                        name,
                        row_index + 1,
                        column + 1,
                    ),
                    x,
                    wall_y,
                    z,
                    min(125.0, spacing - 45.0),
                    120.0,
                    outward,
                    lit=(
                        (
                            window_index * 7
                            + row_index * 3
                            + column
                        ) % 23
                        in (0, 6)
                    ),
                    cool=(
                        (
                            window_index * 7
                            + row_index * 3
                            + column
                        ) % 23
                        == 13
                    ),
                    architectural_modules=architectural_modules,
                )
    log("Added {} old residential window assemblies".format(window_index))


def add_school_windows(
    actor_subsystem,
    meshes,
    materials,
    architectural_modules,
):
    count = 0
    main_lit_windows = {
        (0, 2): "M_OTS_NeutralWindow",
        (1, 4): "M_OTS_CoolWindow",
        (2, 1): "M_OTS_NeutralWindow",
        (3, 3): "M_OTS_NeutralWindow",
    }
    for row_index, z in enumerate((420.0, 740.0, 1060.0, 1380.0)):
        for column, y in enumerate((-1900.0, -1150.0, -380.0, 380.0, 1150.0, 1900.0)):
            count += 1
            lit_material = main_lit_windows.get((row_index, column))
            add_window_x(
                actor_subsystem,
                meshes,
                materials,
                "OTS_SchoolMain_R{}_C{}".format(
                    row_index + 1,
                    column + 1,
                ),
                -3195.0,
                y,
                z,
                260.0,
                150.0,
                1.0,
                lit=lit_material is not None,
                lit_material=lit_material,
                architectural_modules=architectural_modules,
            )
    wing_lit_windows = {
        ("L", 2, 1): "M_OTS_NeutralWindow",
        ("R", 0, 2): "M_OTS_CoolWindow",
    }
    for side, y_center in (("L", -2100.0), ("R", 2100.0)):
        for row_index, z in enumerate((360.0, 680.0, 980.0)):
            for column, y_offset in enumerate((-280.0, 0.0, 280.0)):
                count += 1
                lit_material = wing_lit_windows.get(
                    (side, row_index, column)
                )
                add_window_x(
                    actor_subsystem,
                    meshes,
                    materials,
                    "OTS_SchoolWing_{}_R{}_C{}".format(
                        side,
                        row_index + 1,
                        column + 1,
                    ),
                    -1695.0,
                    y_center + y_offset,
                    z,
                    150.0,
                    130.0,
                    1.0,
                    lit=lit_material is not None,
                    lit_material=lit_material,
                    architectural_modules=architectural_modules,
                )
    log("Added {} school window assemblies".format(count))


def add_open_school_gate(actor_subsystem, meshes, materials, detailed_props):
    # Each leaf is now one welded, centimetre-authored mesh with a single
    # simple collision box instead of nine independently colliding Cube actors.
    for side_name, hinge_y, y_scale in (
        ("South", -400.0, -1.0),
        ("North", 400.0, 1.0),
    ):
        leaf = spawn_native_prop(
            actor_subsystem,
            detailed_props["SchoolGateLeaf"],
            "OTS_P3Prop_SchoolGateLeaf" + side_name,
            (-980.0, hinge_y, 7.5),
            scale=(1.0, y_scale, 1.0),
            collision=True,
            folder=FOLDER_ROOT + "/P3/SchoolGate",
        )
        component = leaf.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, materials["M_OTS_OldGreenMetal"])
        component.set_material(1, materials["M_OTS_RustMetal"])
    # Substantial masonry hinge posts keep the open leaves readable from the
    # player's school-side start.  The leaves remain fully open and the clear
    # path between the posts is wider than the player capsule.
    for side_name, y, y_scale in (
        ("South", -430.0, -1.0),
        ("North", 430.0, 1.0),
    ):
        post = spawn_native_prop(
            actor_subsystem,
            detailed_props["SchoolGatePost"],
            "OTS_P3Prop_SchoolGatePost" + side_name,
            (-910.0, y, 0.0),
            scale=(1.0, y_scale, 1.0),
            collision=True,
            folder=FOLDER_ROOT + "/P3/SchoolGate",
        )
        component = post.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, materials["M_OTS_OldConcrete"])
        component.set_material(1, materials["M_OTS_RustMetal"])
        component.set_material(2, materials["M_OTS_Stain"])
    for stripe_index, x in enumerate(
        (-560.0, -490.0, -420.0, -350.0, -280.0, -210.0, -140.0)
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_ZebraStripe",
            (x, 0.0, 2.0),
            (38.0, 650.0, 2.0),
            "M_OTS_RoadMarking",
            folder=FOLDER_ROOT + "/RoadDetails",
            cast_shadow=False,
        )
    # School notice boards flank the gate and create a readable threshold.
    for y in (-620.0, 620.0):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SchoolNoticeBoard",
            (-940.0, y, 215.0),
            (8.0, 250.0, 170.0),
            "M_OTS_FadedBlueSign",
            folder=FOLDER_ROOT + "/SchoolGate",
        )


def add_school_identity_details(actor_subsystem, meshes, materials):
    """Turn the blockout school mass into a readable old-town school entrance."""
    for prefix, location, size, material_name, collision, cast_shadow in (
        (
            "OTS_SchoolGatePlaque",
            (-896.5, 0.0, 436.0),
            (7.0, 760.0, 54.0),
            "M_OTS_FadedRedSign",
            False,
            True,
        ),
        (
            "OTS_SchoolGateTube",
            (-950.0, 0.0, 397.0),
            (16.0, 150.0, 8.0),
            "M_OTS_FluorescentTube",
            False,
            False,
        ),
        (
            "OTS_SchoolPath",
            (-2100.0, 0.0, 2.0),
            (2100.0, 360.0, 2.0),
            "M_OTS_OldConcrete",
            False,
            False,
        ),
        (
            "OTS_SchoolPathEdgeSouth",
            (-2100.0, -184.0, 2.5),
            (2100.0, 8.0, 3.0),
            "M_OTS_Stain",
            False,
            False,
        ),
        (
            "OTS_SchoolPathEdgeNorth",
            (-2100.0, 184.0, 2.5),
            (2100.0, 8.0, 3.0),
            "M_OTS_Stain",
            False,
            False,
        ),
        (
            "OTS_SchoolStepLow",
            (-3040.0, 0.0, 9.0),
            (220.0, 560.0, 16.0),
            "M_OTS_OldConcrete",
            True,
            True,
        ),
        (
            "OTS_SchoolStepHigh",
            (-3130.0, 0.0, 18.0),
            (140.0, 520.0, 34.0),
            "M_OTS_OldConcrete",
            True,
            True,
        ),
        (
            "OTS_SchoolEntranceRecess",
            (-3194.0, 0.0, 170.0),
            (6.0, 420.0, 270.0),
            "M_OTS_DarkTrim",
            False,
            True,
        ),
        (
            "OTS_SchoolEntranceFrameSouth",
            (-3188.0, -216.0, 170.0),
            (8.0, 16.0, 290.0),
            "M_OTS_OldGreenMetal",
            False,
            True,
        ),
        (
            "OTS_SchoolEntranceFrameNorth",
            (-3188.0, 216.0, 170.0),
            (8.0, 16.0, 290.0),
            "M_OTS_OldGreenMetal",
            False,
            True,
        ),
        (
            "OTS_SchoolEntranceFrameTop",
            (-3188.0, 0.0, 315.0),
            (8.0, 448.0, 18.0),
            "M_OTS_OldGreenMetal",
            False,
            True,
        ),
        (
            "OTS_SchoolEntranceCanopy",
            (-3102.0, 0.0, 350.0),
            (204.0, 600.0, 18.0),
            "M_OTS_OldConcrete",
            False,
            True,
        ),
        (
            "OTS_SchoolCanopyPostSouth",
            (-3020.0, -270.0, 175.0),
            (20.0, 20.0, 350.0),
            "M_OTS_OldConcrete",
            True,
            True,
        ),
        (
            "OTS_SchoolCanopyPostNorth",
            (-3020.0, 270.0, 175.0),
            (20.0, 20.0, 350.0),
            "M_OTS_OldConcrete",
            True,
            True,
        ),
        (
            "OTS_SchoolEntranceTube",
            (-3070.0, 0.0, 337.0),
            (60.0, 150.0, 6.0),
            "M_OTS_FluorescentTube",
            False,
            False,
        ),
        (
            "OTS_SchoolMainNameBand",
            (-3194.0, 0.0, 1570.0),
            (6.0, 1400.0, 80.0),
            "M_OTS_FadedRedSign",
            False,
            True,
        ),
        (
            "OTS_SchoolGuardMass",
            (-1260.0, 700.0, 125.0),
            (230.0, 240.0, 248.0),
            "M_OTS_OldConcrete",
            True,
            True,
        ),
        (
            "OTS_SchoolGuardRoof",
            (-1260.0, 700.0, 259.0),
            (260.0, 270.0, 18.0),
            "M_OTS_DarkTrim",
            False,
            True,
        ),
        (
            "OTS_SchoolGuardWindow",
            (-1140.5, 700.0, 165.0),
            (9.0, 140.0, 82.0),
            "M_OTS_DarkGlass",
            False,
            True,
        ),
        (
            "OTS_SchoolCourtyardLampHead",
            (-2050.0, 232.0, 292.0),
            (35.0, 56.0, 10.0),
            "M_OTS_DarkTrim",
            False,
            True,
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            material_name,
            collision=collision,
            folder=FOLDER_ROOT + "/SchoolIdentity",
            cast_shadow=cast_shadow,
        )
    for z in (300.0, 620.0, 940.0, 1260.0):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SchoolFloorBand",
            (-3189.0, 0.0, z),
            (10.0, 4700.0, 10.0),
            "M_OTS_OldConcrete",
            folder=FOLDER_ROOT + "/SchoolIdentity",
        )
    for index, y in enumerate((-1400.0, 0.0, 1400.0)):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SchoolFacadeTube{:02d}".format(index + 1),
            (-3185.0, y, 900.0),
            (8.0, 180.0, 10.0),
            "M_OTS_FluorescentTube",
            folder=FOLDER_ROOT + "/SchoolIdentity",
            cast_shadow=False,
        )
    for side, y in (("South", -2100.0), ("North", 2100.0)):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SchoolWingTube" + side,
            (-1685.0, y, 650.0),
            (8.0, 130.0, 10.0),
            "M_OTS_FluorescentTube",
            folder=FOLDER_ROOT + "/SchoolIdentity",
            cast_shadow=False,
        )
    spawn_cylinder(
        actor_subsystem,
        meshes,
        materials,
        "OTS_SchoolCourtyardLampPole",
        (-2050.0, 260.0, 145.0),
        8.0,
        290.0,
        "M_OTS_RustMetal",
        collision=True,
        folder=FOLDER_ROOT + "/SchoolIdentity",
    )
    for side, y in (("South", -520.0), ("North", 520.0)):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SchoolBenchSeat" + side,
            (-2200.0, y, 46.0),
            (180.0, 42.0, 10.0),
            "M_OTS_Cardboard",
            collision=True,
            folder=FOLDER_ROOT + "/SchoolIdentity",
        )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SchoolBenchBack" + side,
            (-2200.0, y + (-18.0 if y < 0.0 else 18.0), 88.0),
            (180.0, 8.0, 75.0),
            "M_OTS_Cardboard",
            folder=FOLDER_ROOT + "/SchoolIdentity",
        )
    log("Added school path, gate identity, guard room, and main entrance")


def add_wall_grime_and_shop_details(actor_subsystem, meshes, materials):
    patches = (
        (1520.0, 527.5, 115.0, 150.0, 5.0, 46.0, -1.0),
        (2260.0, 527.5, 80.0, 90.0, 5.0, 38.0, -1.0),
        (2920.0, 527.5, 110.0, 170.0, 5.0, 55.0, -1.0),
        (4560.0, 527.5, 85.0, 130.0, 5.0, 40.0, -1.0),
        (1680.0, -527.5, 80.0, 150.0, 5.0, 42.0, 1.0),
        (3350.0, -527.5, 105.0, 180.0, 5.0, 48.0, 1.0),
        (5000.0, -527.5, 90.0, 150.0, 5.0, 45.0, 1.0),
    )
    for index, (x, y, z, sx, sy, sz, _outward) in enumerate(patches):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_WallStain",
            (x, y, z),
            (sx, sy, sz),
            "M_OTS_Stain",
            folder=FOLDER_ROOT + "/Grime",
            cast_shadow=False,
        )
    # Hanging signs break the silhouette and guide the player toward the alley.
    for x, y, z, material_name, yaw in (
        (1450.0, 485.0, 310.0, "M_OTS_FadedRedSign", 90.0),
        (2450.0, 475.0, 310.0, "M_OTS_FadedBlueSign", 90.0),
        (3600.0, -480.0, 310.0, "M_OTS_FadedRedSign", 90.0),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_HangingSign",
            (x, y, z),
            (85.0, 14.0, 95.0),
            material_name,
            (0.0, yaw, 0.0),
            folder=FOLDER_ROOT + "/ShopSigns",
        )
        wall_y = 530.0 if y > 0.0 else -530.0
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_HangingSignBracket",
            (x, (y + wall_y) * 0.5, z + 48.0),
            (8.0, abs(wall_y - y) + 4.0, 5.0),
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/ShopSigns",
        )


def add_ac_unit(
    actor_subsystem,
    meshes,
    materials,
    prefix,
    x,
    wall_y,
    z,
    outward,
):
    center_y = wall_y + outward * 28.0
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        prefix + "_Body",
        (x, center_y, z),
        (78.0, 45.0, 58.0),
        "M_OTS_OldConcrete",
        folder=FOLDER_ROOT + "/Utilities",
    )
    front_y = center_y + outward * 24.0
    for fin in range(6):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix + "_Fin",
            (x - 28.0 + fin * 11.0, front_y, z),
            (3.0, 3.0, 42.0),
            "M_OTS_DarkTrim",
            folder=FOLDER_ROOT + "/Utilities",
            cast_shadow=False,
        )
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        prefix + "_Bracket",
        (x, wall_y + outward * 10.0, z - 38.0),
        (92.0, 12.0, 8.0),
        "M_OTS_RustMetal",
        folder=FOLDER_ROOT + "/Utilities",
    )


def add_utilities(actor_subsystem, meshes, materials, detailed_props):
    for index, spec in enumerate(
        (
            (2140.0, 530.0, 660.0, -1.0),
            (3460.0, 530.0, 910.0, -1.0),
            (4530.0, 530.0, 730.0, -1.0),
            (3770.0, -530.0, 720.0, 1.0),
            (5260.0, -530.0, 980.0, 1.0),
        )
    ):
        x, wall_y, center_z, outward = spec
        spawn_native_prop(
            actor_subsystem,
            detailed_props["ACUnit"],
            "OTS_P2Prop_ACUnit",
            (
                x,
                wall_y + outward * 20.0,
                center_z - 29.0,
            ),
            (0.0, 0.0 if outward < 0.0 else 180.0, 0.0),
            folder=FOLDER_ROOT + "/P2/Utilities",
        )
    for index, (x, y, z, height) in enumerate(
        (
            (2315.0, 520.0, 330.0, 640.0),
            (3650.0, 520.0, 430.0, 840.0),
            (4590.0, -520.0, 380.0, 740.0),
            (5520.0, 520.0, 520.0, 1020.0),
        )
    ):
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_DrainPipe",
            (x, y, z),
            10.0,
            height,
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Utilities",
        )
    for x, wall_y, z in (
        (2400.0, 530.0, 245.0),
        (3020.0, -530.0, 210.0),
        (4720.0, 530.0, 260.0),
    ):
        outward = -1.0 if wall_y > 0.0 else 1.0
        spawn_native_prop(
            actor_subsystem,
            detailed_props["MeterBox"],
            "OTS_P2Prop_MeterBox",
            (x, wall_y + outward * 7.5, z - 20.0),
            (0.0, 0.0 if outward < 0.0 else 180.0, 0.0),
            folder=FOLDER_ROOT + "/Utilities",
        )

    # Reusable multi-part utility clusters replace empty facade patches with
    # real drainpipes, recessed meter doors, conduits and coiled cable.  Each
    # entry is one non-colliding StaticMeshActor, including the X-facing
    # MainHome side wall and the street-end apartment.
    for location, yaw in (
        ((2471.0, 720.0, 1.0), 90.0),
        ((3380.0, -529.0, 1.0), 180.0),
        ((4820.0, 529.0, 1.0), 0.0),
        ((776.0, 1120.0, 1.0), -90.0),
        # Reuse the fifth cluster on the formerly blank focal wall instead of
        # adding another prop instance at the street-end approach.
        ((6567.0, 440.0, 1.0), -90.0),
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["WallUtilityCluster"],
            "OTS_P2Prop_WallUtilityCluster",
            location,
            (0.0, yaw, 0.0),
            collision=False,
            folder=FOLDER_ROOT + "/P2/Utilities",
        )


def add_puddles_and_road_wear(
    actor_subsystem,
    meshes,
    materials,
    detailed_props,
):
    def spawn_road_ellipse(
        prefix,
        x,
        y,
        z,
        sx,
        sy,
        yaw,
        material_name,
    ):
        patch = spawn_native_prop(
            actor_subsystem,
            detailed_props["PuddlePatch"],
            unique_label(prefix),
            (x, y, z),
            (0.0, yaw, 0.0),
            (sx / 210.0, sy / 83.0, 1.0),
            False,
            folder=FOLDER_ROOT + "/RoadDetails",
        )
        component = patch.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, materials["M_OTS_WetAsphalt"])
        safe_set(component, "cast_shadow", False)

    # Keep wet patches as single, shallow pieces.  The former three-layer
    # ellipses produced visible stacked edges and read like flat game tokens.
    for x, y, sx, sy, yaw in (
        (480.0, -245.0, 135.0, 52.0, -9.0),
        (1510.0, 235.0, 205.0, 68.0, 5.0),
        (2450.0, -230.0, 175.0, 48.0, -4.0),
        (3670.0, 245.0, 220.0, 72.0, 8.0),
        (4850.0, -292.0, 105.0, 35.0, -8.0),
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["PuddlePatch"],
            "OTS_P2Prop_PuddlePatch",
            (x, y, 2.0),
            (0.0, yaw, 0.0),
            (sx / 210.0, sy / 83.0, 1.0),
            collision=False,
            folder=FOLDER_ROOT + "/RoadDetails",
        )
    for x, y, sx, sy, yaw in (
        (980.0, 100.0, 135.0, 52.0, 9.0),
        (2980.0, -105.0, 185.0, 66.0, -5.0),
        (4380.0, 110.0, 150.0, 58.0, 6.0),
    ):
        spawn_road_ellipse(
            "OTS_AsphaltPatch",
            x,
            y,
            1.65,
            sx,
            sy,
            yaw,
            "M_OTS_DarkGround",
        )


def spawn_point_light(
    actor_subsystem,
    label,
    location,
    intensity,
    temperature,
    radius,
    color=(1.0, 1.0, 1.0, 1.0),
    shadows=True,
    folder=FOLDER_ROOT + "/Lighting",
    source_radius=22.0,
    soft_source_radius=35.0,
    specular_scale=0.55,
    volumetric=0.25,
):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.PointLight,
        unreal.Vector(*location),
        make_rotator((0.0, 0.0, 0.0)),
        False,
    )
    require(actor is not None, "Unable to spawn point light {}".format(label))
    set_generated_metadata(actor, label, folder)
    component = actor.get_component_by_class(unreal.PointLightComponent)
    require(component is not None, "{} has no point-light component".format(label))
    safe_set(component, "mobility", unreal.ComponentMobility.MOVABLE)
    safe_set(component, "intensity_units", unreal.LightUnits.LUMENS)
    safe_set(
        component,
        "intensity",
        float(intensity) * POINT_LIGHT_INTENSITY_SCALE,
    )
    safe_set(component, "attenuation_radius", float(radius))
    safe_set(component, "use_temperature", True)
    safe_set(component, "temperature", float(temperature))
    safe_set(component, "light_color", unreal.Color(
        int(color[0] * 255),
        int(color[1] * 255),
        int(color[2] * 255),
        255,
    ))
    safe_set(component, "cast_shadows", bool(shadows))
    safe_set(component, "source_radius", float(source_radius))
    safe_set(component, "soft_source_radius", float(soft_source_radius))
    safe_set(component, "specular_scale", float(specular_scale))
    safe_set(component, "volumetric_scattering_intensity", float(volumetric))
    return actor


def add_street_lights(
    actor_subsystem,
    meshes,
    materials,
    detailed_props,
):
    # Deliberately asymmetric placement avoids the former mirrored tunnel of
    # ten identical Cube poles.  Each visible fixture is now one manufactured
    # Static Mesh; one damaged lamp is intentionally unlit.
    lamp_specs = (
        # x, sidewalk y, yaw, z scale, lumens, temperature, radius
        # The authored fixture is 325 cm tall.  Earlier 0.90-1.04 scales made
        # it read as a garden lamp beside 240 cm doors; these values place the
        # seven fixtures in the believable 3.8-4.1 m old-street range.
        (340.0, -405.0, 180.0, 1.22, 105.0, 3750.0, 500.0),
        (1710.0, -405.0, 180.0, 1.18, 62.0, 3500.0, 430.0),
        (3460.0, -405.0, 180.0, 1.26, 0.0, 3600.0, 0.0),
        (5260.0, -405.0, 180.0, 1.20, 92.0, 3950.0, 480.0),
        (1420.0, 405.0, 0.0, 1.19, 58.0, 4150.0, 425.0),
        (2780.0, 405.0, 0.0, 1.24, 112.0, 3650.0, 520.0),
        (4470.0, 405.0, 0.0, 1.17, 54.0, 4050.0, 410.0),
    )
    lamp_xy_scale = 1.04
    for index, (
        x,
        y,
        yaw,
        z_scale,
        intensity,
        temperature,
        radius,
    ) in enumerate(lamp_specs):
        prefix = "OTS_P2Prop_StreetLamp"
        spawn_native_prop(
            actor_subsystem,
            detailed_props["StreetLamp"],
            prefix,
            (x, y, 0.0),
            (0.0, yaw, 0.0),
            (lamp_xy_scale, lamp_xy_scale, z_scale),
            collision=True,
            folder=FOLDER_ROOT + "/P2/StreetLights",
        )
        if intensity <= 0.0:
            continue
        road_sign = 1.0 if y < 0.0 else -1.0
        lamp_y = y + road_sign * 108.0 * lamp_xy_scale
        is_key_pool = intensity >= 85.0
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_StreetLamp{:02d}".format(index + 1),
            (x, lamp_y, 306.0 * z_scale),
            intensity,
            temperature,
            radius,
            shadows=is_key_pool,
            source_radius=24.0 if is_key_pool else 18.0,
            soft_source_radius=38.0 if is_key_pool else 30.0,
            specular_scale=0.34,
            volumetric=0.10 if is_key_pool else 0.045,
        )
    road_fill_specs = (
        (900.0, 42.0, 740.0),
        (2250.0, 52.0, 790.0),
        (3650.0, 38.0, 720.0),
        (5000.0, 48.0, 760.0),
    )
    for index, (x, intensity, radius) in enumerate(road_fill_specs):
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_RoadFill{:02d}".format(index + 1),
            (x, 0.0, 450.0),
            intensity,
            6000.0,
            radius,
            (0.60, 0.68, 0.78, 1.0),
            False,
            source_radius=180.0,
            soft_source_radius=250.0,
            specular_scale=0.25,
            volumetric=0.0,
        )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_RoadFillStart",
        (-250.0, 0.0, 420.0),
        38.0,
        6000.0,
        720.0,
        (0.60, 0.68, 0.78, 1.0),
        False,
        source_radius=170.0,
        soft_source_radius=230.0,
        specular_scale=0.22,
        volumetric=0.0,
    )
    # Weak awning lamps make close-range storefront details readable while
    # keeping the main street exposure and horror contrast intact.
    for index, (
        x,
        y,
        intensity,
        temperature,
        color,
    ) in enumerate(
        (
            (1050.0, -450.0, 24.0, 3500.0, (1.0, 0.94, 0.82, 1.0)),
            (1900.0, -458.0, 34.0, 3900.0, (1.0, 0.97, 0.90, 1.0)),
            (3115.0, -460.0, 28.0, 3200.0, (1.0, 0.90, 0.76, 1.0)),
            (4090.0, -455.0, 36.0, 3600.0, (1.0, 0.94, 0.84, 1.0)),
            (1875.0, 458.0, 32.0, 4100.0, (0.94, 0.98, 1.0, 1.0)),
            (4340.0, 455.0, 34.0, 3400.0, (1.0, 0.92, 0.80, 1.0)),
        )
    ):
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_P1ShopAccent{:02d}".format(index + 1),
            (x, y, 305.0),
            intensity,
            temperature,
            300.0,
            color,
            False,
            source_radius=55.0,
            soft_source_radius=85.0,
            specular_scale=0.28,
            volumetric=0.0,
        )
    # Gate fluorescent and alley/shop accents.
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_SchoolGate",
        (-1025.0, 0.0, 365.0),
        68.0,
        4300.0,
        520.0,
        (0.82, 0.90, 1.0, 1.0),
        False,
        source_radius=45.0,
        soft_source_radius=60.0,
        specular_scale=0.30,
        volumetric=0.12,
    )
    for side, y, intensity in (
        ("South", -900.0, 55.0),
        ("North", 900.0, 45.0),
    ):
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_SchoolCourtyard" + side,
            (-2050.0, y, 480.0),
            intensity,
            6500.0,
            1100.0,
            (0.45, 0.55, 0.72, 1.0),
            False,
            source_radius=180.0,
            soft_source_radius=240.0,
            specular_scale=0.20,
            volumetric=0.0,
        )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_SchoolEntrance",
        (-3070.0, 0.0, 305.0),
        75.0,
        4000.0,
        560.0,
        (0.90, 0.92, 1.0, 1.0),
        True,
        source_radius=70.0,
        soft_source_radius=90.0,
        specular_scale=0.40,
        volumetric=0.12,
    )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_SchoolCourtyardLamp",
        (-2050.0, 260.0, 285.0),
        45.0,
        3900.0,
        430.0,
        (0.82, 0.90, 0.86, 1.0),
        False,
        source_radius=28.0,
        soft_source_radius=45.0,
        specular_scale=0.35,
        volumetric=0.08,
    )
    school_facade_washes = (
        (-1400.0, 55.0, 5200.0, (0.72, 0.78, 0.86, 1.0), 850.0),
        (0.0, 70.0, 4700.0, (0.82, 0.78, 0.68, 1.0), 950.0),
        (1400.0, 48.0, 5600.0, (0.68, 0.76, 0.88, 1.0), 800.0),
    )
    for index, (
        y,
        intensity,
        temperature,
        color,
        radius,
    ) in enumerate(school_facade_washes):
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_SchoolFacadeWash{:02d}".format(index + 1),
            (-2850.0, y, 900.0),
            intensity,
            temperature,
            radius,
            color,
            False,
            source_radius=100.0,
            soft_source_radius=150.0,
            specular_scale=0.22,
            volumetric=0.0,
        )
    for side, y, intensity, temperature in (
        ("South", -2100.0, 45.0, 5000.0),
        ("North", 2100.0, 38.0, 5700.0),
    ):
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_SchoolWingWash" + side,
            (-1420.0, y, 650.0),
            intensity,
            temperature,
            780.0,
            (0.62, 0.73, 0.90, 1.0),
            False,
            source_radius=90.0,
            soft_source_radius=130.0,
            specular_scale=0.22,
            volumetric=0.0,
        )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_MainHomeFacade",
        (1025.0, 455.0, 245.0),
        45.0,
        4100.0,
        280.0,
        (1.0, 1.0, 1.0, 1.0),
        False,
        source_radius=70.0,
        soft_source_radius=100.0,
        specular_scale=0.40,
        volumetric=0.05,
    )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_MainHomeInteriorFront",
        (1025.0, 850.0, 300.0),
        70.0,
        4900.0,
        520.0,
        (1.0, 1.0, 1.0, 1.0),
        False,
        source_radius=80.0,
        soft_source_radius=110.0,
        specular_scale=0.35,
        volumetric=0.05,
    )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_MainHomeInteriorRear",
        (1025.0, 1120.0, 285.0),
        30.0,
        4600.0,
        360.0,
        (1.0, 1.0, 1.0, 1.0),
        False,
        source_radius=65.0,
        soft_source_radius=90.0,
        specular_scale=0.30,
        volumetric=0.0,
    )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_AlleyNorthEnd",
        (2570.0, 1400.0, 285.0),
        44.0,
        3800.0,
        480.0,
        (1.0, 1.0, 1.0, 1.0),
        True,
        source_radius=35.0,
        soft_source_radius=55.0,
        specular_scale=0.40,
        volumetric=0.12,
    )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_AlleyNorthEntry",
        (2570.0, 720.0, 350.0),
        25.0,
        6500.0,
        420.0,
        (0.55, 0.66, 0.82, 1.0),
        False,
        source_radius=100.0,
        soft_source_radius=130.0,
        specular_scale=0.25,
        volumetric=0.0,
    )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_AlleySouthEnd",
        (2570.0, -1400.0, 285.0),
        44.0,
        3800.0,
        480.0,
        (1.0, 1.0, 1.0, 1.0),
        True,
        source_radius=35.0,
        soft_source_radius=55.0,
        specular_scale=0.40,
        volumetric=0.12,
    )
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_AlleySouthEntry",
        (2570.0, -720.0, 350.0),
        25.0,
        6500.0,
        420.0,
        (0.55, 0.66, 0.82, 1.0),
        False,
        source_radius=100.0,
        soft_source_radius=130.0,
        specular_scale=0.25,
        volumetric=0.0,
    )
    # A very weak cool guide light preserves a readable floor and end wall
    # inside each alley without flattening the horror contrast.
    for suffix, y in (("North", 1030.0), ("South", -1030.0)):
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_AlleyGuide" + suffix,
            (2570.0, y, 145.0),
            11.0,
            6100.0,
            300.0,
            (0.48, 0.60, 0.76, 1.0),
            False,
            source_radius=75.0,
            soft_source_radius=100.0,
            specular_scale=0.18,
            volumetric=0.0,
        )


def add_alley_props(actor_subsystem, meshes, materials, detailed_props):
    # Keep a 105 cm clear walking lane through the 200 cm-wide alley.
    for x, y, yaw, scale in (
        (2505.0, 780.0, 8.0, (1.05, 1.0, 1.0)),
        (2500.0, 855.0, -6.0, (0.88, 0.92, 0.82)),
        (2638.0, 1180.0, 4.0, (0.95, 0.95, 1.15)),
        (2508.0, 1390.0, -8.0, (1.10, 1.0, 0.95)),
        (2498.0, -820.0, 7.0, (1.0, 0.95, 0.95)),
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["CardboardBox"],
            "OTS_P2Prop_CardboardBox",
            (x, y, 0.0),
            (0.0, yaw, 0.0),
            scale,
            True,
            FOLDER_ROOT + "/P2/AlleyProps",
        )
    for x, y, yaw in (
        (2644.0, 700.0, 4.0),
        (2500.0, 1260.0, -8.0),
        (2654.0, -1190.0, 7.0),
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["TrashBin"],
            "OTS_P2Prop_TrashBin",
            (x, y, 0.0),
            (0.0, yaw, 0.0),
            collision=True,
            folder=FOLDER_ROOT + "/P2/AlleyProps",
        )
    spawn_cylinder(
        actor_subsystem,
        meshes,
        materials,
        "OTS_AlleyPipe",
        (2667.0, 1030.0, 360.0),
        8.0,
        720.0,
        "M_OTS_RustMetal",
        folder=FOLDER_ROOT + "/Alley",
    )
    for z in (125.0, 350.0, 575.0):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_AlleyPipeBracket",
            (2668.0, 1030.0, z),
            (10.0, 16.0, 5.0),
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Alley",
        )
    # Complete wall-mounted crossbars replace the former floating beams.  The
    # authored end plates land 2 cm inside both party walls.
    for y in (760.0, 1010.0, 1260.0):
        start = (2468.0, y, 330.0)
        end = (2672.0, y + 15.0, 315.0)
        midpoint = tuple(
            (start[index] + end[index]) * 0.5 for index in range(3)
        )
        length = math.sqrt(
            sum((end[index] - start[index]) ** 2 for index in range(3))
        )
        spawn_native_prop(
            actor_subsystem,
            detailed_props["AlleyCrossbar"],
            "OTS_P3Prop_AlleyCrossbarNorth",
            midpoint,
            look_at_rotation(start, end),
            (length / 204.0, 1.0, 1.0),
            False,
            FOLDER_ROOT + "/P3/Alley",
        )
    # Extend the original 300 cm wall so the alley ends in masonry rather than
    # an exposed world horizon. The new section meets the old wall at Z=300.
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_AlleyEndWallExtension",
        (2570.0, 1480.0, 475.0),
        (438.0, 30.0, 350.0),
        "M_OTS_FadedBlueWall",
        collision=True,
        folder=FOLDER_ROOT + "/Alley",
    )
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_AlleyEndWallCap",
        (2570.0, 1480.0, 658.0),
        (460.0, 42.0, 16.0),
        "M_OTS_DarkTrim",
        collision=True,
        folder=FOLDER_ROOT + "/Alley",
    )
    # Mirror the northern treatment so the south opening is a complete,
    # believable service alley rather than an exposed edge of the level.
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_SouthAlleyEndWallExtension",
        (2570.0, -1480.0, 475.0),
        (438.0, 30.0, 350.0),
        "M_OTS_FadedGreenWall",
        collision=True,
        folder=FOLDER_ROOT + "/Alley",
    )
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_SouthAlleyEndWallCap",
        (2570.0, -1480.0, 658.0),
        (460.0, 42.0, 16.0),
        "M_OTS_DarkTrim",
        collision=True,
        folder=FOLDER_ROOT + "/Alley",
    )
    # One continuous, centimetre-thick finish skin hides the material break
    # between each protected 300 cm blockout wall and its new extension.  The
    # back face touches the support at Y +/-1465; the visible face sits 3 cm
    # into the alley, so it is neither coplanar nor floating.
    for prefix, location, material_name in (
        (
            "OTS_AlleyEndWallContinuousFinishNorth",
            (2570.0, 1463.5, 325.0),
            "M_OTS_FadedBlueWall",
        ),
        (
            "OTS_AlleyEndWallContinuousFinishSouth",
            (2570.0, -1463.5, 325.0),
            "M_OTS_FadedGreenWall",
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            (438.0, 3.0, 650.0),
            material_name,
            collision=False,
            folder=FOLDER_ROOT + "/Alley",
            cast_shadow=False,
        )
    spawn_cylinder(
        actor_subsystem,
        meshes,
        materials,
        "OTS_SouthAlleyPipe",
        (2677.0, -1010.0, 360.0),
        8.0,
        720.0,
        "M_OTS_RustMetal",
        folder=FOLDER_ROOT + "/Alley",
    )
    for z in (125.0, 350.0, 575.0):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SouthAlleyPipeBracket",
            (2678.0, -1010.0, z),
            (10.0, 16.0, 5.0),
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Alley",
        )
    for y in (-760.0, -1010.0, -1260.0):
        start = (2458.0, y, 325.0)
        end = (2682.0, y - 12.0, 312.0)
        midpoint = tuple(
            (start[index] + end[index]) * 0.5 for index in range(3)
        )
        length = math.sqrt(
            sum((end[index] - start[index]) ** 2 for index in range(3))
        )
        spawn_native_prop(
            actor_subsystem,
            detailed_props["AlleyCrossbar"],
            "OTS_P3Prop_AlleyCrossbarSouth",
            midpoint,
            look_at_rotation(start, end),
            (length / 204.0, 1.0, 1.0),
            False,
            FOLDER_ROOT + "/P3/Alley",
        )


def _legacy_alley_props_removed(
    actor_subsystem,
    meshes,
    materials,
):
    """Retained only to make stale diff context obvious; never called."""
    for index, (x, y, z, size, yaw) in enumerate(
        (
            (2505.0, 780.0, 30.0, (52.0, 42.0, 60.0), 8.0),
            (2500.0, 855.0, 22.0, (45.0, 38.0, 44.0), -6.0),
            (2638.0, 1180.0, 35.0, (48.0, 48.0, 70.0), 4.0),
            (2508.0, 1390.0, 28.0, (56.0, 44.0, 56.0), -8.0),
        )
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_AlleyBox",
            (x, y, z),
            size,
            "M_OTS_Cardboard",
            (0.0, yaw, 0.0),
            folder=FOLDER_ROOT + "/Alley",
            collision=True,
        )
    for x, y, z in (
        (2638.0, 760.0, 50.0),
        (2500.0, 1260.0, 55.0),
    ):
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_AlleyBin",
            (x, y, z),
            58.0,
            100.0,
            "M_OTS_OldGreenMetal",
            collision=True,
            folder=FOLDER_ROOT + "/Alley",
        )
    for z in (180.0, 380.0, 620.0):
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_AlleyPipe",
            (2645.0, 1030.0, z),
            8.0,
            180.0,
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Alley",
        )
    # Low cable canopy makes the alley feel compressed without blocking it.
    for y in (760.0, 1010.0, 1260.0):
        spawn_beam_between(
            actor_subsystem,
            meshes,
            materials,
            "OTS_AlleyCable",
            (2480.0, y, 330.0),
            (2660.0, y + 15.0, 315.0),
            2.5,
            "M_OTS_BlackWire",
            FOLDER_ROOT + "/Alley",
        )
    # Extend the original 300 cm wall so the alley ends in masonry rather than
    # an exposed world horizon. The new section meets the old wall at Z=300.
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_AlleyEndWallExtension",
        (2570.0, 1480.0, 475.0),
        (438.0, 30.0, 350.0),
        "M_OTS_OldConcrete",
        collision=True,
        folder=FOLDER_ROOT + "/Alley",
    )
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_AlleyEndWallCap",
        (2570.0, 1480.0, 658.0),
        (460.0, 42.0, 16.0),
        "M_OTS_DarkTrim",
        collision=True,
        folder=FOLDER_ROOT + "/Alley",
    )
    # Mirror the northern treatment so the south opening is a complete,
    # believable service alley rather than an exposed edge of the level.
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_SouthAlleyEndWallExtension",
        (2570.0, -1480.0, 475.0),
        (438.0, 30.0, 350.0),
        "M_OTS_OldConcrete",
        collision=True,
        folder=FOLDER_ROOT + "/Alley",
    )
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_SouthAlleyEndWallCap",
        (2570.0, -1480.0, 658.0),
        (460.0, 42.0, 16.0),
        "M_OTS_DarkTrim",
        collision=True,
        folder=FOLDER_ROOT + "/Alley",
    )
    for index, (x, y, z, size, material_name) in enumerate(
        (
            (
                2498.0,
                -820.0,
                28.0,
                (52.0, 42.0, 56.0),
                "M_OTS_Cardboard",
            ),
            (
                2640.0,
                -1190.0,
                48.0,
                (58.0, 58.0, 96.0),
                "M_OTS_OldGreenMetal",
            ),
        )
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SouthAlleyProp{:02d}".format(index + 1),
            (x, y, z),
            size,
            material_name,
            collision=True,
            folder=FOLDER_ROOT + "/Alley",
        )
    for z in (180.0, 380.0, 580.0):
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SouthAlleyPipe",
            (2645.0, -1010.0, z),
            8.0,
            180.0,
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Alley",
        )
    for y in (-760.0, -1010.0, -1260.0):
        spawn_beam_between(
            actor_subsystem,
            meshes,
            materials,
            "OTS_SouthAlleyCable",
            (2480.0, y, 330.0),
            (2660.0, y - 15.0, 315.0),
            2.5,
            "M_OTS_BlackWire",
            FOLDER_ROOT + "/Alley",
        )
    for y, inward in ((1480.0, -1.0), (-1480.0, 1.0)):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_AlleyEndLampFixture",
            (2570.0, y + inward * 16.0, 310.0),
            (100.0, 16.0, 8.0),
            "M_OTS_WarmWindow",
            folder=FOLDER_ROOT + "/Alley",
            cast_shadow=False,
        )


def add_perimeter_closure(
    actor_subsystem,
    meshes,
    materials,
    architectural_modules,
):
    """Close every practical sightline while preserving approved walkable lanes."""
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_PerimeterGround",
        (790.0, 0.0, -41.0),
        (13660.0, 7000.0, 80.0),
        "M_OTS_WetAsphalt",
        collision=True,
        folder=FOLDER_ROOT + "/Closure",
    )

    # Party walls bridge the exact gaps between the alley floors and the
    # original building shells. Inner faces preserve 200/220 cm clear widths.
    for prefix, location, size, material_name in (
        (
            "OTS_AlleyPartyWallNorthWest",
            (2410.0, 1015.0, 450.0),
            (120.0, 970.0, 900.0),
            "M_OTS_FadedBlueWall",
        ),
        (
            "OTS_AlleyPartyWallNorthEast",
            (2730.0, 1015.0, 450.0),
            (120.0, 970.0, 900.0),
            "M_OTS_FadedGreenWall",
        ),
        (
            "OTS_AlleyPartyWallSouthWest",
            (2405.0, -1012.5, 450.0),
            (110.0, 965.0, 900.0),
            "M_OTS_FadedGreenWall",
        ),
        (
            "OTS_AlleyPartyWallSouthEast",
            (2735.0, -1012.5, 450.0),
            (110.0, 965.0, 900.0),
            "M_OTS_FadedBlueWall",
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            material_name,
            collision=True,
            folder=FOLDER_ROOT + "/Closure",
        )

    backdrop_specs = (
        (
            "North01",
            (1350.0, 2280.0, 550.0),
            (1500.0, 1000.0, 1100.0),
            "M_OTS_FadedBlueWall",
            -1.0,
        ),
        (
            "North02",
            (2850.0, 2330.0, 750.0),
            (1500.0, 1100.0, 1500.0),
            "M_OTS_FadedGreenWall",
            -1.0,
        ),
        (
            "North03",
            (4350.0, 2230.0, 600.0),
            (1500.0, 900.0, 1200.0),
            "M_OTS_OldConcrete",
            -1.0,
        ),
        (
            "North04",
            (5850.0, 2330.0, 800.0),
            (1500.0, 1100.0, 1600.0),
            "M_OTS_FadedBlueWall",
            -1.0,
        ),
        (
            "South01",
            (1350.0, -2280.0, 650.0),
            (1500.0, 1000.0, 1300.0),
            "M_OTS_OldConcrete",
            1.0,
        ),
        (
            "South02",
            (2850.0, -2330.0, 550.0),
            (1500.0, 1100.0, 1100.0),
            "M_OTS_FadedBlueWall",
            1.0,
        ),
        (
            "South03",
            (4350.0, -2230.0, 800.0),
            (1500.0, 900.0, 1600.0),
            "M_OTS_FadedGreenWall",
            1.0,
        ),
        (
            "South04",
            (5850.0, -2330.0, 600.0),
            (1500.0, 1100.0, 1200.0),
            "M_OTS_OldConcrete",
            1.0,
        ),
    )
    for index, (name, location, size, material_name, outward) in enumerate(
        backdrop_specs
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_PerimeterBackdrop" + name,
            location,
            size,
            material_name,
            collision=True,
            folder=FOLDER_ROOT + "/Closure",
        )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_PerimeterRoofCap" + name,
            (
                location[0],
                location[1],
                size[2] + 12.0,
            ),
            (size[0] + 20.0, size[1] + 20.0, 24.0),
            "M_OTS_DarkTrim",
            folder=FOLDER_ROOT + "/Closure",
        )
        inward_face_y = (
            location[1] - size[1] * 0.5
            if outward < 0.0
            else location[1] + size[1] * 0.5
        )
        columns = 3
        spacing = size[0] / float(columns + 1)
        max_rows = max(1, min(4, int(size[2] // 320.0)))
        for row in range(max_rows):
            z = 260.0 + row * 300.0
            if z + 75.0 >= size[2]:
                continue
            for column in range(columns):
                x = (
                    location[0]
                    - size[0] * 0.5
                    + spacing * (column + 1)
                )
                add_window_y(
                    actor_subsystem,
                    meshes,
                    materials,
                    "OTS_PerimeterWindow{}_R{}_C{}".format(
                        name,
                        row + 1,
                        column + 1,
                    ),
                    x,
                    inward_face_y,
                    z,
                    120.0,
                    120.0,
                    outward,
                    lit=((index + row + column) % 9 == 0),
                    cool=False,
                    architectural_modules=architectural_modules,
                )

    # These blocks overlap the school-ground edge and the street end by a few
    # centimetres, intentionally eliminating hairline horizon leaks.
    boundary_specs = (
        (
            "SchoolNorthWest",
            (-3900.0, 2990.0, 650.0),
            (2200.0, 1020.0, 1300.0),
            "M_OTS_SchoolWall",
        ),
        (
            "SchoolNorthMid",
            (-2200.0, 2990.0, 500.0),
            (1200.0, 1020.0, 1000.0),
            "M_OTS_OldConcrete",
        ),
        (
            "SchoolNorthEast",
            (-500.0, 2990.0, 700.0),
            (2200.0, 1020.0, 1400.0),
            "M_OTS_FadedBlueWall",
        ),
        (
            "SchoolSouthWest",
            (-3900.0, -2990.0, 650.0),
            (2200.0, 1020.0, 1300.0),
            "M_OTS_SchoolWall",
        ),
        (
            "SchoolSouthMid",
            (-2200.0, -2990.0, 500.0),
            (1200.0, 1020.0, 1000.0),
            "M_OTS_OldConcrete",
        ),
        (
            "SchoolSouthEast",
            (-500.0, -2990.0, 700.0),
            (2200.0, 1020.0, 1400.0),
            "M_OTS_FadedBlueWall",
        ),
        (
            "West",
            (-5400.0, 0.0, 800.0),
            (1280.0, 7000.0, 1600.0),
            "M_OTS_SchoolWall",
        ),
        (
            "East",
            (7100.0, 0.0, 750.0),
            (1040.0, 7000.0, 1500.0),
            "M_OTS_FadedGreenWall",
        ),
    )
    for name, location, size, material_name in boundary_specs:
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_PerimeterBoundary" + name,
            location,
            size,
            material_name,
            collision=True,
            folder=FOLDER_ROOT + "/Closure",
        )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_PerimeterBoundaryCap" + name,
            (location[0], location[1], size[2] + 12.0),
            (size[0] + 20.0, size[1] + 20.0, 24.0),
            "M_OTS_DarkTrim",
            folder=FOLDER_ROOT + "/Closure",
        )
    log("Added continuous ground, alley party walls, and perimeter backdrops")


def add_procedural_electric_poles(
    actor_subsystem,
    meshes,
    materials,
):
    # Keep the first pole clear of the 200 cm alley entrance at X=2570.
    pole_points = ((2200.0, 350.0), (4700.0, -350.0))
    for index, (x, y) in enumerate(pole_points):
        prefix = "OTS_UtilityPole_{:02d}".format(index + 1)
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            (x, y, 325.0),
            24.0,
            650.0,
            "M_OTS_OldConcrete",
            collision=True,
            folder=FOLDER_ROOT + "/Utilities",
        )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix + "_Crossarm",
            (x, y, 610.0),
            (30.0, 170.0, 14.0),
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Utilities",
        )
        for offset in (-62.0, 0.0, 62.0):
            spawn_cylinder(
                actor_subsystem,
                meshes,
                materials,
                prefix + "_Insulator",
                (x, y + offset, 628.0),
                12.0,
                34.0,
                "M_OTS_DarkGlass",
                folder=FOLDER_ROOT + "/Utilities",
            )
    # Three sagged cable runs between poles.
    for offset in (-62.0, 0.0, 62.0):
        points = (
            (2200.0, 350.0 + offset, 640.0),
            (3050.0, 150.0 + offset * 0.45, 570.0),
            (3900.0, -150.0 + offset * 0.45, 570.0),
            (4700.0, -350.0 + offset, 640.0),
        )
        for start, end in zip(points, points[1:]):
            spawn_beam_between(
                actor_subsystem,
                meshes,
                materials,
                "OTS_OverheadWire",
                start,
                end,
                2.2,
                "M_OTS_BlackWire",
            )


def add_balconies(actor_subsystem, meshes, materials):
    for index, (x, y, z, outward) in enumerate(
        (
            (3120.0, 530.0, 760.0, -1.0),
            (3380.0, 530.0, 1060.0, -1.0),
            (5200.0, -530.0, 1250.0, 1.0),
        )
    ):
        platform_y = y + outward * 38.0
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_BalconyPlatform",
            (x, platform_y, z),
            (230.0, 78.0, 12.0),
            "M_OTS_OldConcrete",
            folder=FOLDER_ROOT + "/Balconies",
            collision=True,
        )
        rail_y = y + outward * 78.0
        for bar_x in (x - 105.0, x - 52.0, x, x + 52.0, x + 105.0):
            spawn_cube(
                actor_subsystem,
                meshes,
                materials,
                "OTS_BalconyRail",
                (bar_x, rail_y, z + 55.0),
                (5.0, 5.0, 105.0),
                "M_OTS_RustMetal",
                folder=FOLDER_ROOT + "/Balconies",
            )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_BalconyTopRail",
            (x, rail_y, z + 108.0),
            (220.0, 6.0, 6.0),
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Balconies",
        )


def add_rooftop_details(actor_subsystem, meshes, materials):
    """Add a few readable old-town silhouettes without blocking roof access."""
    roof_tanks = (
        (3310.0, 1130.0, 1601.0),
        (5260.0, -1030.0, 1701.0),
    )
    for index, (x, y, roof_z) in enumerate(roof_tanks):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_RoofTankBase",
            (x, y, roof_z + 8.0),
            (132.0, 132.0, 16.0),
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Rooftops",
        )
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_RoofWaterTank",
            (x, y, roof_z + 70.0),
            104.0,
            120.0,
            "M_OTS_OldGreenMetal",
            folder=FOLDER_ROOT + "/Rooftops",
        )
        for band_z in (roof_z + 38.0, roof_z + 100.0):
            spawn_cylinder(
                actor_subsystem,
                meshes,
                materials,
                "OTS_RoofTankBand",
                (x, y, band_z),
                108.0,
                5.0,
                "M_OTS_RustMetal",
                folder=FOLDER_ROOT + "/Rooftops",
            )

    for index, (x, y, roof_z) in enumerate(
        (
            (4320.0, -1080.0, 1501.0),
            (5480.0, 1030.0, 1801.0),
        )
    ):
        mast_top = roof_z + 210.0
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_RoofAntennaMast",
            (x, y, roof_z + 105.0),
            7.0,
            210.0,
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Rooftops",
        )
        spawn_beam_between(
            actor_subsystem,
            meshes,
            materials,
            "OTS_RoofAntennaArm",
            (x - 45.0, y, mast_top - 35.0),
            (x + 45.0, y, mast_top - 35.0),
            4.0,
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/Rooftops",
        )
        for offset in (-32.0, 0.0, 32.0):
            spawn_beam_between(
                actor_subsystem,
                meshes,
                materials,
                "OTS_RoofAntennaElement",
                (x + offset, y - 24.0, mast_top - 35.0),
                (x + offset, y + 24.0, mast_top - 35.0),
                3.0,
                "M_OTS_RustMetal",
                folder=FOLDER_ROOT + "/Rooftops",
            )


def add_shopfront_p1_details(
    actor_subsystem,
    meshes,
    materials,
    detailed_props,
):
    """Add centimetre-authored, single-asset old shopfront fixtures.

    These assemblies replace the former collections of thin Cube actors.  The
    visible layers are welded into five reusable Dynamic Mesh assets, so there
    are no open shutter gaps or floating frame pieces at first-person range.
    """
    sign_specs = (
        (
            "SchoolSnack",
            1050.0,
            -510.0,
            296.0,
            400.0,
            1.0,
            "M_OTS_FadedOchreSign",
        ),
        (
            "SouthGrocery",
            1900.0,
            -518.0,
            296.0,
            520.0,
            1.0,
            "M_OTS_FadedBlueSign",
        ),
        (
            "SouthRepair",
            3115.0,
            -510.0,
            296.0,
            500.0,
            1.0,
            "M_OTS_FadedRedSign",
        ),
        (
            "SouthHardware",
            4090.0,
            -518.0,
            296.0,
            600.0,
            1.0,
            "M_OTS_OldGreenSign",
        ),
        (
            "NorthRepair",
            1875.0,
            518.0,
            296.0,
            520.0,
            -1.0,
            "M_OTS_FadedBlueSign",
        ),
        (
            "NorthHardware",
            4340.0,
            518.0,
            296.0,
            600.0,
            -1.0,
            "M_OTS_FadedRedSign",
        ),
    )
    sign_text_assets = {
        "SchoolSnack": "SignTextSnack",
        "SouthGrocery": "SignTextGeneral",
        "SouthRepair": "SignTextRepair",
        "SouthHardware": "SignTextHardware",
        "NorthRepair": "SignTextRepair",
        "NorthHardware": "SignTextHardware",
    }
    for name, x, y, z, width, outward, material_name in sign_specs:
        sign_location = (x, y - outward * 0.5, z - 42.0)
        sign_rotation = (0.0, 180.0 if outward > 0.0 else 0.0, 0.0)
        sign_scale = (width / 400.0, 1.0, 1.0)
        actor = spawn_native_prop(
            actor_subsystem,
            detailed_props["SignAssembly"],
            "OTS_P3Prop_SignAssembly" + name,
            sign_location,
            rotation=sign_rotation,
            scale=sign_scale,
            collision=False,
            folder=FOLDER_ROOT + "/P3/Shopfronts",
        )
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, materials[material_name])
        component.set_material(1, materials["M_OTS_RustMetal"])
        component.set_material(2, materials[material_name])

        text_actor = spawn_native_prop(
            actor_subsystem,
            detailed_props[sign_text_assets[name]],
            "OTS_P3Prop_SignText" + name,
            sign_location,
            rotation=sign_rotation,
            scale=sign_scale,
            collision=False,
            folder=FOLDER_ROOT + "/P3/Shopfronts",
        )
        text_component = text_actor.get_component_by_class(
            unreal.StaticMeshComponent
        )
        text_component.set_material(
            0,
            materials[
                "M_OTS_DarkTrim"
                if material_name == "M_OTS_FadedOchreSign"
                else "M_OTS_FadedOchreSign"
                if material_name == "M_OTS_FadedBlueSign"
                else "M_OTS_OldConcrete"
            ],
        )

    awning_specs = (
        (
            "SchoolSnack",
            (1050.0, -480.0, 335.0),
            (400.0, 76.0, 8.0),
            "M_OTS_FadedBlueSign",
            1.0,
        ),
        (
            "NorthRepair",
            (1875.0, 480.0, 338.0),
            (430.0, 76.0, 8.0),
            "M_OTS_OldGreenMetal",
            -1.0,
        ),
        (
            "SouthHardware",
            (4090.0, -480.0, 338.0),
            (520.0, 76.0, 8.0),
            "M_OTS_FadedRedSign",
            1.0,
        ),
    )
    for name, location, size, material_name, outward in awning_specs:
        wall_y = location[1] - outward * size[1] * 0.5
        actor = spawn_native_prop(
            actor_subsystem,
            detailed_props["AwningAssembly"],
            "OTS_P3Prop_AwningAssembly" + name,
            (location[0], wall_y, location[2] - 32.0),
            rotation=(0.0, 180.0 if outward > 0.0 else 0.0, 0.0),
            scale=(size[0] / 400.0, 1.0, 1.0),
            collision=False,
            folder=FOLDER_ROOT + "/P3/Shopfronts",
        )
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, materials[material_name])
        component.set_material(1, materials["M_OTS_RustMetal"])
        component.set_material(3, materials["M_OTS_FluorescentTube"])

    shutter_specs = (
        (
            "SouthSnack", 1050.0, -515.0, 141.0, 340.0, 220.0, 1.0,
            "M_OTS_OldGreenMetal",
        ),
        (
            "SouthRepair", 3115.0, -515.0, 141.0, 420.0, 220.0, 1.0,
            "M_OTS_FadedBlueMetal",
        ),
        (
            "SouthHardware", 4260.0, -518.0, 141.0, 340.0, 220.0, 1.0,
            "M_OTS_FadedRedMetal",
        ),
        (
            "NorthHardware", 4160.0, 518.0, 141.0, 340.0, 220.0, -1.0,
            "M_OTS_FadedBlueMetal",
        ),
    )
    for (
        name,
        x,
        y,
        z,
        width,
        height,
        outward,
        shutter_material,
    ) in shutter_specs:
        actor = spawn_native_prop(
            actor_subsystem,
            detailed_props["StaticShutter"],
            "OTS_P3Prop_StaticShutter" + name,
            (x, y, z - height * 0.5 - 8.0),
            rotation=(0.0, 180.0 if outward > 0.0 else 0.0, 0.0),
            scale=(width / 340.0, 1.0, height / 220.0),
            collision=False,
            folder=FOLDER_ROOT + "/P3/Shopfronts",
        )
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, materials[shutter_material])
        component.set_material(1, materials["M_OTS_RustMetal"])
    log("Added 19 single-asset P3 shopfront assemblies")


def add_facade_character_details(
    actor_subsystem,
    meshes,
    materials,
    detailed_props,
):
    """Add security bars, laundry, posters and other residential cues."""
    # Round anti-theft grilles and their connected wall stand-offs now belong
    # to each reusable window Static Mesh.  Do not add the former Cube grilles
    # here, or selected windows would receive overlapping duplicate bars.

    laundry_specs = (
        ("R01", 3240.0, 530.0, 820.0, -1.0),
        ("R02", 4215.0, 530.0, 1120.0, -1.0),
        ("R03", 5390.0, 530.0, 1420.0, -1.0),
        ("L01", 3965.0, -530.0, 1120.0, 1.0),
        ("L02", 5190.0, -530.0, 1420.0, 1.0),
    )
    for name, x, wall_y, window_z, outward in laundry_specs:
        # The authored mesh uses local -Y as its visible direction.  Its wall
        # plates enter the facade by 4 cm and the lowest garment is Z=0.
        spawn_native_prop(
            actor_subsystem,
            detailed_props["LoadedLaundryRack"],
            "OTS_P5Prop_LoadedLaundryRack" + name,
            (x, wall_y, window_z - 119.0),
            (0.0, 180.0 if outward > 0.0 else 0.0, 0.0),
            (1.0, 1.0, 1.0),
            False,
            FOLDER_ROOT + "/P5/FacadeLife",
        )

    poster_specs = (
        (2470.0, 524.0, 185.0, -1.0, "M_OTS_FadedBlueSign"),
        (2740.0, -524.0, 205.0, 1.0, "M_OTS_FadedRedSign"),
        (4760.0, 524.0, 190.0, -1.0, "M_OTS_Cardboard"),
        (5680.0, -524.0, 230.0, 1.0, "M_OTS_FadedBlueSign"),
    )
    for index, (x, wall_y, z, outward, material_name) in enumerate(
        poster_specs
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1WallPoster",
            (x, wall_y + outward * 3.0, z),
            (46.0 + float((index % 2) * 12), 2.0, 68.0),
            material_name,
            folder=FOLDER_ROOT + "/P1/FacadeLife",
            cast_shadow=False,
        )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1WallPosterTear",
            (
                x + 8.0,
                wall_y + outward * 5.0,
                z - 16.0,
            ),
            (18.0, 2.0, 22.0),
            "M_OTS_Stain",
            folder=FOLDER_ROOT + "/P1/FacadeLife",
            cast_shadow=False,
        )

    # Deep trim and sills stop the two windowed ground floors reading as
    # textureless holes.  All pieces sit in front of the original surfaces.
    for name, x, wall_y, z, width, height, outward in (
        ("SouthGrocery", 1900.0, -518.0, 121.0, 180.0, 230.0, 1.0),
        ("SouthHardware", 3890.0, -518.0, 121.0, 160.0, 240.0, 1.0),
        ("NorthRepair", 1875.0, 518.0, 121.0, 180.0, 240.0, -1.0),
        ("NorthHardware", 4540.0, 518.0, 121.0, 160.0, 240.0, -1.0),
    ):
        frame_y = wall_y + outward * 7.0
        for side in (-1.0, 1.0):
            spawn_cube(
                actor_subsystem,
                meshes,
                materials,
                "OTS_P1DoorJamb" + name,
                (x + side * width * 0.5, frame_y, z),
                (10.0, 9.0, height),
                "M_OTS_RustMetal",
                folder=FOLDER_ROOT + "/P1/FacadeLife",
            )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1DoorLintel" + name,
            (x, frame_y + outward * 1.0, z + height * 0.5),
            (width + 10.0, 10.0, 10.0),
            "M_OTS_RustMetal",
            folder=FOLDER_ROOT + "/P1/FacadeLife",
        )
    for x, wall_y, outward in (
        (1660.0, -518.0, 1.0),
        (2140.0, -518.0, 1.0),
        (1615.0, 518.0, -1.0),
        (2135.0, 518.0, -1.0),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1GroundWindowSill",
            (x, wall_y + outward * 13.0, 57.0),
            (220.0, 28.0, 8.0),
            "M_OTS_OldConcrete",
            folder=FOLDER_ROOT + "/P1/FacadeLife",
        )

    for x, wall_y, width, height, material_name, outward in (
        (3240.0, 530.0, 880.0, 110.0, "M_OTS_RedBrick", -1.0),
        (5390.0, 530.0, 780.0, 120.0, "M_OTS_Stain", -1.0),
        (5190.0, -530.0, 880.0, 110.0, "M_OTS_RedBrick", 1.0),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1ResidentialBaseBand",
            (x, wall_y + outward * 6.0, height * 0.5),
            (width, 8.0, height),
            material_name,
            folder=FOLDER_ROOT + "/P1/FacadeLife",
            cast_shadow=False,
        )

    for name, x, wall_y, z, outward in (
        ("NorthBack", 5657.0, 530.0, 1120.0, -1.0),
        ("SouthBack", 4890.0, -530.0, 1420.0, 1.0),
    ):
        for board_index, z_offset in enumerate((-42.0, 0.0, 42.0)):
            spawn_cube(
                actor_subsystem,
                meshes,
                materials,
                "OTS_P1BoardedWindow" + name,
                (x, wall_y + outward * 11.0, z + z_offset),
                (145.0, 7.0, 34.0),
                (
                    "M_OTS_RustMetal"
                    if board_index == 1
                    else "M_OTS_OldGreenMetal"
                ),
                (
                    0.0,
                    0.0,
                    -2.0 if board_index == 0 else 2.0
                    if board_index == 2
                    else 0.0,
                ),
                folder=FOLDER_ROOT + "/P1/FacadeLife",
            )
    log("Added residential grilles, laundry racks, and worn wall posters")


def add_rooftop_p1_details(actor_subsystem, meshes, materials):
    """Vary roof edges and add believable silhouettes along the street canyon."""
    parapet_specs = (
        ("SouthSnack", 1050.0, -530.0, 421.0, 500.0, 1.0),
        ("NorthEarly", 1875.0, 530.0, 1101.0, 950.0, -1.0),
        ("SouthEarly", 1900.0, -530.0, 1201.0, 900.0, 1.0),
        ("SouthMid", 3115.0, -530.0, 801.0, 650.0, 1.0),
        ("NorthMid", 3240.0, 530.0, 1601.0, 900.0, -1.0),
        ("SouthLate", 4090.0, -530.0, 1501.0, 1000.0, 1.0),
        ("NorthLate", 4340.0, 530.0, 1301.0, 1000.0, -1.0),
        ("SouthBack", 5190.0, -530.0, 1701.0, 900.0, 1.0),
        ("NorthBack", 5390.0, 530.0, 1801.0, 800.0, -1.0),
    )
    for index, (name, x, edge_y, roof_z, width, outward) in enumerate(
        parapet_specs
    ):
        center_y = edge_y + outward * 8.0
        height = 48.0 + float((index % 3) * 10)
        material_name = (
            "M_OTS_OldConcrete"
            if index % 2 == 0
            else "M_OTS_DarkTrim"
        )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1RoofParapet" + name,
            (x, center_y, roof_z + height * 0.5),
            (width + 10.0, 22.0, height),
            material_name,
            folder=FOLDER_ROOT + "/P1/Rooftops",
        )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1RoofParapetCap" + name,
            (x, center_y + outward * 2.0, roof_z + height + 5.0),
            (width + 24.0, 30.0, 10.0),
            "M_OTS_RustMetal" if index % 3 == 1 else "M_OTS_OldConcrete",
            folder=FOLDER_ROOT + "/P1/Rooftops",
        )
        for side in (-1.0, 1.0):
            spawn_cube(
                actor_subsystem,
                meshes,
                materials,
                "OTS_P1RoofCornerPier" + name,
                (
                    x + side * width * 0.5,
                    center_y - outward * 38.0,
                    roof_z + height * 0.5,
                ),
                (22.0, 92.0, height),
                material_name,
                folder=FOLDER_ROOT + "/P1/Rooftops",
            )

    for index, (x, y, roof_z, size) in enumerate(
        (
            (2100.0, -1030.0, 1201.0, (170.0, 190.0, 130.0)),
            (2980.0, 1230.0, 1601.0, (160.0, 180.0, 120.0)),
            (5050.0, -1080.0, 1701.0, (190.0, 170.0, 140.0)),
        )
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1RoofStairwell",
            (x, y, roof_z + size[2] * 0.5),
            size,
            "M_OTS_OldConcrete",
            folder=FOLDER_ROOT + "/P1/Rooftops",
        )
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1RoofStairwellCap",
            (x, y, roof_z + size[2] + 7.0),
            (size[0] + 18.0, size[1] + 18.0, 14.0),
            "M_OTS_DarkTrim",
            folder=FOLDER_ROOT + "/P1/Rooftops",
        )

    for index, (x, y, roof_z) in enumerate(
        (
            (4050.0, -1080.0, 1501.0),
            (5350.0, 1030.0, 1801.0),
        )
    ):
        for offset in (-90.0, 90.0):
            spawn_cylinder(
                actor_subsystem,
                meshes,
                materials,
                "OTS_P1RoofLaundryPost",
                (x + offset, y, roof_z + 70.0),
                6.0,
                140.0,
                "M_OTS_RustMetal",
                folder=FOLDER_ROOT + "/P1/Rooftops",
            )
        for z_offset in (90.0, 120.0):
            spawn_beam_between(
                actor_subsystem,
                meshes,
                materials,
                "OTS_P1RoofLaundryLine",
                (x - 90.0, y, roof_z + z_offset),
                (x + 90.0, y, roof_z + z_offset - 5.0),
                2.0,
                "M_OTS_BlackWire",
                FOLDER_ROOT + "/P1/Rooftops",
            )
    log("Added varied parapets, stairwells, and roofline silhouettes")


def add_street_life_details(actor_subsystem, meshes, materials):
    """Add readable old-town life while preserving all player clearances."""
    folder = FOLDER_ROOT + "/P1/StreetLife"
    alley_folder = FOLDER_ROOT + "/P1/AlleyLife"

    # Closed breakfast stall opposite the school.
    for prefix, location, size, material_name in (
        (
            "OTS_P1BreakfastTableTop",
            (930.0, -488.0, 74.0),
            (120.0, 40.0, 8.0),
            "M_OTS_Cardboard",
        ),
        (
            "OTS_P1BreakfastTableLegA",
            (880.0, -488.0, 40.0),
            (8.0, 34.0, 64.0),
            "M_OTS_Cardboard",
        ),
        (
            "OTS_P1BreakfastTableLegB",
            (980.0, -488.0, 40.0),
            (8.0, 34.0, 64.0),
            "M_OTS_Cardboard",
        ),
        (
            "OTS_P1RepairToolbox",
            (2260.0, 490.0, 14.0),
            (48.0, 28.0, 16.0),
            "M_OTS_DarkTrim",
        ),
        (
            "OTS_P1FreezerBody",
            (4735.0, 493.0, 62.0),
            (82.0, 44.0, 112.0),
            "M_OTS_OldGreenMetal",
        ),
        (
            "OTS_P1FreezerLid",
            (4735.0, 493.0, 121.0),
            (86.0, 48.0, 6.0),
            "M_OTS_OldConcrete",
        ),
        (
            "OTS_P1FreezerHandle",
            (4735.0, 468.0, 88.0),
            (35.0, 4.0, 6.0),
            "M_OTS_RustMetal",
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            material_name,
            collision=(prefix == "OTS_P1FreezerBody"),
            folder=folder,
        )
    spawn_cylinder(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1BreakfastThermos",
        (910.0, -488.0, 103.0),
        18.0,
        42.0,
        "M_OTS_OldGreenMetal",
        folder=folder,
    )
    spawn_cylinder(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1BreakfastStool",
        (1020.0, -488.0, 24.0),
        28.0,
        36.0,
        "M_OTS_FadedRedSign",
        folder=folder,
    )
    for index, spec in enumerate(
        (
            ((2280.0, 490.0, 42.0), 28.0, 72.0, "M_OTS_OldGreenMetal"),
            ((2320.0, 492.0, 34.0), 24.0, 56.0, "M_OTS_RustMetal"),
        )
    ):
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1RepairGasBottle",
            spec[0],
            spec[1],
            spec[2],
            spec[3],
            folder=folder,
        )
    spawn_beam_between(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1BroomHandle",
        (2260.0, -506.0, 8.0),
        (2240.0, -510.0, 145.0),
        4.0,
        "M_OTS_Cardboard",
        folder,
    )
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1BroomHead",
        (2268.0, -506.0, 14.0),
        (38.0, 10.0, 10.0),
        "M_OTS_Stain",
        folder=folder,
    )
    for x in (5280.0, 5350.0):
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1PlantPot",
            (x, -493.0, 28.0),
            38.0,
            44.0,
            "M_OTS_RustMetal",
            folder=folder,
        )
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1PlantFoliage",
            (x, -493.0, 67.0),
            50.0,
            38.0,
            "M_OTS_FadedGreenWall",
            folder=folder,
        )
    for index, (x, y) in enumerate(
        (
            (1875.0, 480.0),
            (1900.0, -480.0),
            (3890.0, -480.0),
            (4540.0, 480.0),
        )
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1DoorMat",
            (x, y, 7.5),
            (86.0, 52.0, 3.0),
            "M_OTS_Stain",
            folder=folder,
            cast_shadow=False,
        )

    for x, y in ((650.0, 140.0), (3150.0, -110.0), (5350.0, 120.0)):
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1Manhole",
            (x, y, 2.0),
            76.0,
            2.0,
            "M_OTS_RustMetal",
            folder=folder,
        )
    for x, y in (
        (1650.0, 342.0),
        (2750.0, -342.0),
        (4200.0, 342.0),
        (5400.0, -342.0),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1CurbGrateBase",
            (x, y, 2.2),
            (90.0, 18.0, 2.0),
            "M_OTS_DarkTrim",
            folder=folder,
            cast_shadow=False,
        )
        for offset in (-30.0, -10.0, 10.0, 30.0):
            spawn_cube(
                actor_subsystem,
                meshes,
                materials,
                "OTS_P1CurbGrateBar",
                (x + offset, y, 3.5),
                (4.0, 16.0, 2.5),
                "M_OTS_RustMetal",
                folder=folder,
                cast_shadow=False,
            )

    # North alley: outdoor washing and drying.
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1NorthAlleyDrain",
        (2480.0, 1060.0, 2.5),
        (12.0, 780.0, 3.0),
        "M_OTS_DarkTrim",
        folder=alley_folder,
        cast_shadow=False,
    )
    for prefix, location, size, material_name in (
        (
            "OTS_P1OutdoorSinkSupport",
            (2652.0, 1040.0, 44.0),
            (30.0, 64.0, 76.0),
            "M_OTS_OldConcrete",
        ),
        (
            "OTS_P1OutdoorSinkBasin",
            (2644.0, 1040.0, 86.0),
            (46.0, 76.0, 12.0),
            "M_OTS_OldConcrete",
        ),
        (
            "OTS_P1OutdoorSinkInner",
            (2638.0, 1040.0, 89.0),
            (28.0, 52.0, 3.0),
            "M_OTS_DarkTrim",
        ),
        (
            "OTS_P1OutdoorSinkSpout",
            (2628.0, 1040.0, 128.0),
            (20.0, 4.0, 4.0),
            "M_OTS_RustMetal",
        ),
        (
            "OTS_P1NorthAlleyMeter",
            (2664.0, 1190.0, 220.0),
            (8.0, 44.0, 60.0),
            "M_OTS_OldGreenMetal",
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            material_name,
            folder=alley_folder,
        )
    spawn_cylinder(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1OutdoorSinkFaucet",
        (2637.0, 1040.0, 112.0),
        4.0,
        35.0,
        "M_OTS_RustMetal",
        folder=alley_folder,
    )
    for index, (location, size, material_name) in enumerate(
        (
            (
                (2525.0, 1012.0, 266.0),
                (42.0, 3.0, 68.0),
                "M_OTS_FadedBlueWall",
            ),
            (
                (2580.0, 1015.0, 275.0),
                (52.0, 3.0, 84.0),
                "M_OTS_Cardboard",
            ),
            (
                (2635.0, 1018.0, 260.0),
                (36.0, 3.0, 58.0),
                "M_OTS_FadedGreenWall",
            ),
        )
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1NorthAlleyCloth",
            location,
            size,
            material_name,
            folder=alley_folder,
            cast_shadow=False,
        )

    # South alley deliberately tells a different, quieter domestic story.
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1SouthAlleyDrain",
        (2480.0, -1060.0, 2.5),
        (12.0, 780.0, 3.0),
        "M_OTS_DarkTrim",
        folder=alley_folder,
        cast_shadow=False,
    )
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1SouthAlleyBench",
        (2490.0, -1080.0, 33.0),
        (34.0, 130.0, 54.0),
        "M_OTS_Cardboard",
        folder=alley_folder,
    )
    spawn_cylinder(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1SouthAlleyBasinBottom",
        (2515.0, -1220.0, 12.0),
        44.0,
        10.0,
        "M_OTS_FadedBlueWall",
        folder=alley_folder,
    )
    spawn_cylinder(
        actor_subsystem,
        meshes,
        materials,
        "OTS_P1SouthAlleyBasinTop",
        (2515.0, -1220.0, 20.0),
        38.0,
        8.0,
        "M_OTS_FadedGreenWall",
        folder=alley_folder,
    )
    for location, size, material_name in (
        (
            (2545.0, -1012.0, 265.0),
            (48.0, 3.0, 72.0),
            "M_OTS_Stain",
        ),
        (
            (2610.0, -1016.0, 272.0),
            (58.0, 3.0, 82.0),
            "M_OTS_FadedBlueWall",
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P1SouthAlleyCloth",
            location,
            size,
            material_name,
            folder=alley_folder,
            cast_shadow=False,
        )
    log("Added P1 shopfront, street, drain, and asymmetric alley life")


def add_p2_street_life_details(
    actor_subsystem,
    meshes,
    materials,
    detailed_props,
):
    """Replace P1 primitive props with complete centimetre-authored assets."""
    folder = FOLDER_ROOT + "/P2/StreetLife"
    alley_folder = FOLDER_ROOT + "/P2/AlleyLife"

    for asset_name, prefix, location, rotation, scale, collision in (
        (
            "Bicycle",
            "OTS_P2Prop_Bicycle",
            (675.0, 498.0, 0.0),
            (0.0, 8.0, 0.0),
            (1.04, 1.04, 1.04),
            False,
        ),
        (
            "Bicycle",
            "OTS_P2Prop_Bicycle",
            (2860.0, -495.0, 0.0),
            (0.0, -12.0, 0.0),
            (1.04, 1.04, 1.04),
            False,
        ),
        (
            "Bicycle",
            "OTS_P2Prop_Bicycle",
            (5200.0, 498.0, 0.0),
            (0.0, 6.0, 0.0),
            (1.04, 1.04, 1.04),
            False,
        ),
        (
            "VendorTable",
            "OTS_P2Prop_VendorTable",
            (930.0, -478.0, 0.0),
            (0.0, 180.0, 0.0),
            (1.0, 1.0, 1.0),
            True,
        ),
        (
            "Thermos",
            "OTS_P2Prop_Thermos",
            (908.0, -478.0, 79.0),
            (0.0, 168.0, 0.0),
            (1.0, 1.0, 1.0),
            False,
        ),
        (
            "ChineseStool",
            "OTS_P2Prop_ChineseStool",
            (1020.0, -474.0, 0.0),
            (0.0, 18.0, 0.0),
            (1.0, 1.0, 1.0),
            False,
        ),
        (
            "Toolbox",
            "OTS_P2Prop_Toolbox",
            (2248.0, 490.0, 0.0),
            (0.0, -8.0, 0.0),
            (1.0, 1.0, 1.0),
            False,
        ),
        (
            "GasCylinder",
            "OTS_P2Prop_GasCylinder",
            (2294.0, 492.0, 0.0),
            (0.0, 7.0, 0.0),
            (1.0, 1.0, 1.0),
            False,
        ),
        (
            "GasCylinder",
            "OTS_P2Prop_GasCylinder",
            (2330.0, 494.0, 0.0),
            (0.0, -12.0, 0.0),
            (0.82, 0.82, 0.82),
            False,
        ),
        (
            "Broom",
            "OTS_P2Prop_Broom",
            (2218.0, 506.0, 0.0),
            (0.0, 4.0, -8.0),
            (1.0, 1.0, 1.0),
            False,
        ),
        (
            "ChestFreezer",
            "OTS_P2Prop_ChestFreezer",
            (4735.0, 460.0, 0.0),
            (0.0, 10.0, 0.0),
            (1.0, 1.0, 1.0),
            True,
        ),
        (
            "PlantPot",
            "OTS_P2Prop_PlantPot",
            (5280.0, -490.0, 0.0),
            (0.0, -15.0, 0.0),
            (1.0, 1.0, 1.0),
            False,
        ),
        (
            "PlantPot",
            "OTS_P2Prop_PlantPot",
            (5350.0, -490.0, 0.0),
            (0.0, 22.0, 0.0),
            (0.84, 0.84, 0.92),
            False,
        ),
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props[asset_name],
            prefix,
            location,
            rotation,
            scale,
            collision,
            folder,
        )

    for x, y in (
        (1875.0, 480.0),
        (1900.0, -480.0),
        (3890.0, -480.0),
        (4540.0, 480.0),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P2DoorMat",
            (x, y, 7.5),
            (86.0, 52.0, 3.0),
            "M_OTS_Stain",
            folder=folder,
            cast_shadow=False,
        )

    for x, y in ((650.0, 140.0), (3150.0, -110.0), (5350.0, 120.0)):
        spawn_cylinder(
            actor_subsystem,
            meshes,
            materials,
            "OTS_P2Manhole",
            (x, y, 2.0),
            76.0,
            2.0,
            "M_OTS_RustMetal",
            folder=folder,
        )
    for x, y in (
        (1650.0, 342.0),
        (2750.0, -342.0),
        (4200.0, 342.0),
        (5400.0, -342.0),
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["StormDrain"],
            "OTS_P2Prop_StormDrain",
            (x, y, 0.0),
            (0.0, 0.0, 0.0),
            collision=False,
            folder=folder,
        )

    for y, prefix in (
        (1060.0, "OTS_P2NorthAlleyDrain"),
        (-1060.0, "OTS_P2SouthAlleyDrain"),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            (2480.0, y, 2.5),
            (12.0, 780.0, 3.0),
            "M_OTS_DarkTrim",
            folder=alley_folder,
            cast_shadow=False,
        )

    spawn_native_prop(
        actor_subsystem,
        detailed_props["OutdoorSink"],
        "OTS_P2Prop_OutdoorSink",
        (2645.0, 1040.0, 0.0),
        (0.0, -90.0, 0.0),
        collision=True,
        folder=alley_folder,
    )
    spawn_native_prop(
        actor_subsystem,
        detailed_props["MeterBox"],
        "OTS_P2Prop_AlleyMeterBox",
        (2663.0, 1190.0, 198.0),
        (0.0, -90.0, 0.0),
        folder=alley_folder,
    )
    spawn_native_prop(
        actor_subsystem,
        detailed_props["AlleyBench"],
        "OTS_P2Prop_AlleyBench",
        (2475.0, -1080.0, 0.0),
        (0.0, 90.0, 0.0),
        collision=True,
        folder=alley_folder,
    )
    spawn_native_prop(
        actor_subsystem,
        detailed_props["WashBasin"],
        "OTS_P2Prop_WashBasin",
        (2515.0, -1220.0, 0.0),
        (0.0, -12.0, 0.0),
        folder=alley_folder,
    )

    log(
        "Placed P2 independent prop assets, removed flat cloth cards, "
        "and preserved player clearances"
    )


def add_street_endcap(
    actor_subsystem,
    meshes,
    materials,
    architectural_modules,
    detailed_props,
):
    """Continue the main road into a short, fully walkable T-junction.

    The old version placed a 17 m-wide apartment directly across the road and
    read as a level-closing slab.  The source road still ends at X=6000 cm;
    these pieces meet that edge exactly and use the protected 580 cm band up
    to the east perimeter wall.  No coplanar road surfaces overlap.
    """
    folder = FOLDER_ROOT + "/StreetEnd/TJunction"

    # Road top remains Z=1 cm, exactly matching Blockout_MainRoad.  The centre
    # patch is wider at the turn, while both arms narrow to a believable 4.3 m
    # old-town lane.
    for prefix, location, size in (
        (
            "OTS_StreetEndTJunctionRoadCenter",
            (6250.0, 0.0, 0.0),
            (500.0, 1060.0, 2.0),
        ),
        (
            "OTS_StreetEndTJunctionRoadNorth",
            (6285.0, 1155.0, 0.0),
            (430.0, 1250.0, 2.0),
        ),
        (
            "OTS_StreetEndTJunctionRoadSouth",
            (6285.0, -1155.0, 0.0),
            (430.0, 1250.0, 2.0),
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            "M_OTS_WetAsphalt",
            collision=True,
            folder=folder + "/Road",
        )

    # Five-centimetre pavement rise matches the existing main-street
    # sidewalks.  The broad west returns fill the old 210 cm dead strip beside
    # the last residential blocks and leave the entire road mouth unobstructed.
    for prefix, location, size in (
        (
            "OTS_StreetEndTJunctionSidewalkWestNorth",
            (5930.0, 1155.0, -9.0),
            (280.0, 1250.0, 30.0),
        ),
        (
            "OTS_StreetEndTJunctionSidewalkWestSouth",
            (5930.0, -1155.0, -9.0),
            (280.0, 1250.0, 30.0),
        ),
        (
            "OTS_StreetEndTJunctionSidewalkEast",
            (6540.0, 0.0, -9.0),
            (80.0, 3560.0, 30.0),
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            "M_OTS_Sidewalk",
            collision=True,
            folder=folder + "/Sidewalks",
        )

    # Dark drainage seams sit 0.7 cm above the road and never share its plane.
    for prefix, location, size in (
        (
            "OTS_StreetEndTJunctionDrainChannelWestNorth",
            (6075.0, 1155.0, 1.35),
            (10.0, 1240.0, 0.7),
        ),
        (
            "OTS_StreetEndTJunctionDrainChannelWestSouth",
            (6075.0, -1155.0, 1.35),
            (10.0, 1240.0, 0.7),
        ),
        (
            "OTS_StreetEndTJunctionDrainChannelEast",
            (6495.0, 0.0, 1.35),
            (10.0, 3540.0, 0.7),
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            "M_OTS_DarkGround",
            folder=folder + "/Drainage",
            cast_shadow=False,
        )

    # A shallow old shopfront makes the surface opposite the main road a focal
    # facade, not another anonymous closing wall.  Its 76 cm awning terminates
    # two centimetres before the driveable lane and therefore never blocks the
    # turn.  All authored layers overlap their support by at least 1 cm.
    spawn_cube(
        actor_subsystem,
        meshes,
        materials,
        "OTS_StreetEndFocalFacade",
        (6576.0, 0.0, 500.0),
        (8.0, 1020.0, 1000.0),
        "M_OTS_FadedBlueWall",
        folder=folder + "/FocalShop",
    )
    for y in (-505.0, 505.0):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            "OTS_StreetEndFocalFacadePier",
            (6568.0, y, 500.0),
            (10.0, 18.0, 1000.0),
            "M_OTS_DarkTrim",
            folder=folder + "/FocalShop",
        )
    # The upper half used to be one blank ten-metre wall, making the T-junction
    # read like a stage backdrop.  Two deliberately mismatched residential
    # windows plus a waist course and deep cornice establish real storey scale.
    for index, (y, z, width, height, lit) in enumerate(
        (
            (-285.0, 640.0, 134.0, 132.0, False),
            (305.0, 700.0, 116.0, 126.0, True),
        )
    ):
        add_window_x(
            actor_subsystem,
            meshes,
            materials,
            "OTS_StreetEndFocalUpperWindow{:02d}".format(index + 1),
            6572.0,
            y,
            z,
            width,
            height,
            -1.0,
            lit=lit,
            architectural_modules=architectural_modules,
            module_name="ResidentialWindow",
            folder=folder + "/Windows",
        )
    for prefix, location, size, material_name in (
        (
            "OTS_StreetEndFocalFloorCourse",
            (6567.0, 0.0, 455.0),
            (10.0, 1010.0, 18.0),
            "M_OTS_DarkTrim",
        ),
        (
            "OTS_StreetEndFocalCornice",
            (6567.0, 0.0, 970.0),
            (10.0, 1040.0, 34.0),
            "M_OTS_OldConcrete",
        ),
        (
            "OTS_StreetEndFocalCorniceCap",
            (6560.0, 0.0, 992.0),
            (24.0, 1080.0, 10.0),
            "M_OTS_RustMetal",
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            material_name,
            collision=False,
            folder=folder + "/FocalShop",
        )
    focal_rotation = (0.0, -90.0, 0.0)
    focal_sign_location = (6573.0, 0.0, 320.0)
    focal_sign_scale = (1.15, 1.0, 1.0)
    focal_sign = spawn_native_prop(
        actor_subsystem,
        detailed_props["SignAssembly"],
        "OTS_P3Prop_SignAssemblyStreetEnd",
        focal_sign_location,
        focal_rotation,
        focal_sign_scale,
        False,
        folder + "/FocalShop",
    )
    focal_sign_component = focal_sign.get_component_by_class(
        unreal.StaticMeshComponent
    )
    focal_sign_component.set_material(0, materials["M_OTS_FadedRedSign"])
    focal_sign_component.set_material(1, materials["M_OTS_RustMetal"])
    focal_sign_component.set_material(2, materials["M_OTS_FadedRedSign"])
    focal_text = spawn_native_prop(
        actor_subsystem,
        detailed_props["SignTextGeneral"],
        "OTS_P3Prop_SignTextStreetEnd",
        focal_sign_location,
        focal_rotation,
        focal_sign_scale,
        False,
        folder + "/FocalShop",
    )
    focal_text.get_component_by_class(
        unreal.StaticMeshComponent
    ).set_material(0, materials["M_OTS_OldConcrete"])

    focal_awning = spawn_native_prop(
        actor_subsystem,
        detailed_props["AwningAssembly"],
        "OTS_P3Prop_AwningAssemblyStreetEnd",
        (6573.0, 0.0, 370.0),
        focal_rotation,
        focal_sign_scale,
        False,
        folder + "/FocalShop",
    )
    focal_awning_component = focal_awning.get_component_by_class(
        unreal.StaticMeshComponent
    )
    focal_awning_component.set_material(0, materials["M_OTS_OldGreenMetal"])
    focal_awning_component.set_material(1, materials["M_OTS_RustMetal"])
    focal_awning_component.set_material(3, materials["M_OTS_FluorescentTube"])

    focal_shutter = spawn_native_prop(
        actor_subsystem,
        detailed_props["StaticShutter"],
        "OTS_P3Prop_StaticShutterStreetEnd",
        (6573.0, -150.0, 23.0),
        focal_rotation,
        (0.82, 1.0, 1.0),
        False,
        folder + "/FocalShop",
    )
    focal_shutter_component = focal_shutter.get_component_by_class(
        unreal.StaticMeshComponent
    )
    focal_shutter_component.set_material(0, materials["M_OTS_OldGreenMetal"])
    focal_shutter_component.set_material(1, materials["M_OTS_RustMetal"])

    # The right-hand service door is one gap-free P5 asset.  Its frame enters
    # the facade by four centimetres, while its weather strip covers both
    # static leaves.  The interactive MainHome remains completely untouched.
    focal_door = spawn_native_prop(
        actor_subsystem,
        detailed_props["OldServiceDoorTransom"],
        "OTS_P5Prop_OldServiceDoorTransomFocal",
        (6572.0, 158.0, 0.0),
        focal_rotation,
        (1.0, 1.0, 1.0),
        False,
        folder + "/P5/FocalShop",
    )
    focal_door_component = focal_door.get_component_by_class(
        unreal.StaticMeshComponent
    )
    focal_door_component.set_material(0, materials["M_OTS_OldGreenMetal"])
    # P5 OldServiceDoorTransom slots are: paint, rubber, metal, glass, brass,
    # damp.  Keep rubber/brass authored in the asset and only override the
    # intended visible finish slots.
    focal_door_component.set_material(2, materials["M_OTS_RustMetal"])
    focal_door_component.set_material(3, materials["M_OTS_DarkGlass"])
    focal_door_component.set_material(5, materials["M_OTS_Stain"])

    # Irregular windows along the two arms establish human scale and avoid
    # another perfectly repeated facade grid.
    east_window_specs = (
        (-1420.0, 300.0, 118.0, 142.0, False),
        (-1080.0, 650.0, 132.0, 124.0, True),
        (-690.0, 335.0, 112.0, 138.0, False),
        (705.0, 625.0, 136.0, 126.0, True),
        (1125.0, 355.0, 108.0, 136.0, False),
        (1500.0, 770.0, 128.0, 132.0, False),
    )
    for index, (y, z, width, height, lit) in enumerate(east_window_specs):
        add_window_x(
            actor_subsystem,
            meshes,
            materials,
            "OTS_StreetEndWindow_East_{:02d}".format(index + 1),
            6580.0,
            y,
            z,
            width,
            height,
            -1.0,
            lit=lit,
            architectural_modules=architectural_modules,
            module_name="ResidentialWindow",
            folder=folder + "/Windows",
        )

    # The exposed ends of the last north/south blocks now read as true corner
    # facades rather than featureless mesh sides.
    for index, (y, z, lit) in enumerate(
        (
            (-1320.0, 470.0, False),
            (-920.0, 780.0, True),
            (920.0, 500.0, False),
            (1320.0, 820.0, False),
        )
    ):
        add_window_x(
            actor_subsystem,
            meshes,
            materials,
            "OTS_StreetEndWindow_WestCorner_{:02d}".format(index + 1),
            5790.0,
            y,
            z,
            122.0,
            132.0,
            1.0,
            lit=lit,
            architectural_modules=architectural_modules,
            module_name="ResidentialWindow",
            folder=folder + "/Windows",
        )

    # Each arm ends at an existing continuous backdrop.  Closed service doors
    # and offset frames provide an honest visual termination; the backdrop's
    # collision remains the only blocker.
    for suffix, x, wall_y, toward_road, scale, door_material in (
        (
            "North", 6325.0, 1780.0, -1.0, (0.80, 1.0, 0.90),
            "M_OTS_FadedBlueMetal",
        ),
        (
            "South", 6425.0, -1780.0, 1.0, (0.92, 1.0, 1.0),
            "M_OTS_FadedRedMetal",
        ),
    ):
        door = spawn_native_prop(
            actor_subsystem,
            detailed_props["OldServiceDoorTransom"],
            "OTS_P5Prop_OldServiceDoorTransom" + suffix,
            (x, wall_y + toward_road * 4.0, 0.0),
            (0.0, 180.0 if toward_road > 0.0 else 0.0, 0.0),
            scale,
            False,
            folder + "/P5/EndFacades",
        )
        door_component = door.get_component_by_class(unreal.StaticMeshComponent)
        door_component.set_material(0, materials[door_material])
        door_component.set_material(2, materials["M_OTS_RustMetal"])
        door_component.set_material(3, materials["M_OTS_DarkGlass"])
        door_component.set_material(5, materials["M_OTS_Stain"])
        add_window_y(
            actor_subsystem,
            meshes,
            materials,
            "OTS_StreetEndWindow_{}_01".format(suffix),
            6040.0,  # Between backdrop columns at X=5850 and X=6225.
            wall_y,
            330.0,
            118.0,
            132.0,
            toward_road,
            lit=(suffix == "South"),
            architectural_modules=architectural_modules,
        )

    # Wall-base wear is physically offset and overlaps the supporting wall by
    # 1 cm, avoiding both coplanar flicker and floating-patch shadows.
    for prefix, location, size in (
        (
            "OTS_StreetEndBaseWearEastNorth",
            (6569.0, 1210.0, 45.0),
            (8.0, 320.0, 90.0),
        ),
        (
            "OTS_StreetEndBaseWearWestSouth",
            (5794.0, -1260.0, 52.0),
            (8.0, 360.0, 104.0),
        ),
    ):
        spawn_cube(
            actor_subsystem,
            meshes,
            materials,
            prefix,
            location,
            size,
            "M_OTS_Stain",
            folder=folder + "/Wear",
            cast_shadow=False,
        )

    # A small number of centimetre-authored props break the empty-road scale
    # without narrowing the 430 cm vehicle/player lane.
    for asset_name, prefix, location, rotation, scale, collision in (
        (
            "TrashBin",
            "OTS_P2Prop_TrashBin",
            (6540.0, 840.0, 0.0),
            (0.0, -90.0, 0.0),
            (0.92, 0.92, 0.92),
            True,
        ),
        (
            "CardboardBox",
            "OTS_P2Prop_CardboardBox",
            (6538.0, -940.0, 0.0),
            (0.0, 8.0, 0.0),
            (0.72, 0.72, 0.72),
            True,
        ),
        (
            "PlantPot",
            "OTS_P2Prop_PlantPot",
            (6032.0, 1270.0, 6.0),
            (0.0, -10.0, 0.0),
            (0.72, 0.72, 0.78),
            False,
        ),
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props[asset_name],
            prefix,
            location,
            rotation,
            scale,
            collision,
            folder + "/StreetLife",
        )
    for x, y in ((6088.0, 880.0), (6482.0, -990.0)):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["StormDrain"],
            "OTS_P2Prop_StormDrain",
            (x, y, 0.0),
            (0.0, 90.0, 0.0),
            collision=False,
            folder=folder + "/Drainage",
        )
    for index, (x, y, yaw, scale) in enumerate(
        (
            (6290.0, 720.0, 86.0, (0.72, 0.58, 1.0)),
            (6315.0, -1220.0, -92.0, (0.60, 0.74, 1.0)),
        )
    ):
        spawn_native_prop(
            actor_subsystem,
            detailed_props["PuddlePatch"],
            "OTS_P2Prop_PuddlePatch",
            (x, y, 1.1),
            (0.0, yaw, 0.0),
            scale,
            False,
            folder + "/RoadWear",
        )

    # Dim wall lamps make the side routes legible without flattening the main
    # street's high-contrast horror lighting.
    for suffix, y, lamp_material in (
        ("North", 1080.0, "M_OTS_FadedBlueMetal"),
        ("South", -1120.0, "M_OTS_FadedRedMetal"),
    ):
        lamp = spawn_native_prop(
            actor_subsystem,
            detailed_props["WallLampGooseneck"],
            "OTS_P5Prop_WallLampGooseneck" + suffix,
            (6572.0, y, 246.0),
            (0.0, -90.0, 0.0),
            (1.0, 1.0, 1.0),
            False,
            folder + "/P5/Lighting",
        )
        lamp_component = lamp.get_component_by_class(unreal.StaticMeshComponent)
        lamp_component.set_material(0, materials["M_OTS_RustMetal"])
        lamp_component.set_material(1, materials[lamp_material])
        lamp_component.set_material(3, materials["M_OTS_DarkGlass"])
        lamp_component.set_material(4, materials["M_OTS_FluorescentTube"])
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_StreetEnd" + suffix,
            (6470.0, y, 245.0),
            66.0 if suffix == "North" else 60.0,
            3900.0,
            410.0,
            (1.0, 0.72, 0.48, 1.0),
            False,
            source_radius=55.0,
            soft_source_radius=80.0,
            specular_scale=0.32,
            volumetric=0.04,
        )

    # The shop directly opposite the approach needs its own visible source;
    # otherwise the turn reads as a featureless closing slab from gameplay
    # height.  The small fixture is mounted under the authored awning and its
    # warm pool reaches the shutter, door and first metres of both turns.
    focal_lamp = spawn_native_prop(
        actor_subsystem,
        detailed_props["WallLampGooseneck"],
        "OTS_P5Prop_WallLampGooseneckFocal",
        (6572.0, 0.0, 246.0),
        (0.0, -90.0, 0.0),
        (1.0, 1.0, 1.0),
        False,
        folder + "/P5/Lighting",
    )
    focal_lamp_component = focal_lamp.get_component_by_class(
        unreal.StaticMeshComponent
    )
    focal_lamp_component.set_material(0, materials["M_OTS_RustMetal"])
    focal_lamp_component.set_material(1, materials["M_OTS_OldGreenMetal"])
    focal_lamp_component.set_material(3, materials["M_OTS_DarkGlass"])
    focal_lamp_component.set_material(4, materials["M_OTS_FluorescentTube"])
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_StreetEndFocalShop",
        (6460.0, 0.0, 250.0),
        72.0,
        3650.0,
        470.0,
        (1.0, 0.84, 0.62, 1.0),
        False,
        source_radius=80.0,
        soft_source_radius=115.0,
        specular_scale=0.34,
        volumetric=0.035,
    )
    # A weak cool fill exposes the actual left/right road openings while
    # retaining the warm focal hierarchy and deep shadows farther down them.
    spawn_point_light(
        actor_subsystem,
        "OTS_Light_StreetEndJunctionFill",
        (6200.0, 0.0, 255.0),
        32.0,
        6100.0,
        520.0,
        (0.58, 0.67, 0.82, 1.0),
        False,
        source_radius=150.0,
        soft_source_radius=210.0,
        specular_scale=0.20,
        volumetric=0.0,
    )
    # Two lateral pools remain visible from the long main-street approach and
    # reveal that the road continues in both directions instead of terminating
    # at the lit shop wall.
    for suffix, y, intensity, temperature, color in (
        ("North", 650.0, 46.0, 5400.0, (0.62, 0.72, 0.88, 1.0)),
        ("South", -650.0, 43.0, 4300.0, (0.92, 0.80, 0.64, 1.0)),
    ):
        spawn_point_light(
            actor_subsystem,
            "OTS_Light_StreetEndTurnGuide" + suffix,
            (6240.0, y, 210.0),
            intensity,
            temperature,
            430.0,
            color,
            False,
            source_radius=95.0,
            soft_source_radius=145.0,
            specular_scale=0.22,
            volumetric=0.0,
        )

    log("Replaced the flat street endcap with a walkable short T-junction")


def configure_atmosphere(actor_subsystem):
    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if label == "DirectionalLight":
            actor.set_actor_rotation(
                make_rotator((-32.0, -35.0, 0.0)),
                False,
            )
            component = actor.get_component_by_class(
                unreal.DirectionalLightComponent
            )
            if component:
                safe_set(component, "intensity", 0.040)
                safe_set(component, "use_temperature", True)
                safe_set(component, "temperature", 8000.0)
                safe_set(
                    component,
                    "light_color",
                    unreal.Color(185, 200, 225, 255),
                )
                safe_set(component, "volumetric_scattering_intensity", 0.34)
        elif label == "SkyLight":
            component = actor.get_component_by_class(unreal.SkyLightComponent)
            if component:
                safe_set(component, "mobility", unreal.ComponentMobility.MOVABLE)
                safe_set(component, "real_time_capture", True)
                safe_set(component, "intensity", 0.55)
                safe_set(
                    component,
                    "light_color",
                    unreal.Color(115, 135, 165, 255),
                )
        elif label == "ExponentialHeightFog":
            component = actor.get_component_by_class(
                unreal.ExponentialHeightFogComponent
            )
            if component:
                safe_set(component, "fog_density", 0.014)
                safe_set(component, "fog_height_falloff", 0.22)
                safe_set(
                    component,
                    "fog_inscattering_luminance",
                    unreal.LinearColor(0.008, 0.015, 0.030, 1.0),
                )
                safe_set(component, "enable_volumetric_fog", True)
                safe_set(
                    component,
                    "volumetric_fog_scattering_distribution",
                    0.35,
                )
                safe_set(component, "volumetric_fog_extinction_scale", 0.72)
                safe_set(component, "volumetric_fog_distance", 5500.0)
        elif label == "PostProcessVolume":
            safe_set(actor, "unbound", True)
            settings = actor.get_editor_property("settings")
            auto_exposure_enum = getattr(
                unreal,
                "AutoExposureMethod",
                None,
            )
            exposure_method = (
                getattr(auto_exposure_enum, "AEM_HISTOGRAM", None)
                if auto_exposure_enum is not None
                else None
            )
            if exposure_method is not None:
                safe_set(
                    settings,
                    "override_auto_exposure_method",
                    True,
                )
                safe_set(
                    settings,
                    "auto_exposure_method",
                    exposure_method,
                )
            for property_name, value in (
                ("override_auto_exposure_bias", True),
                ("auto_exposure_bias", 0.0),
                ("override_auto_exposure_min_brightness", True),
                ("auto_exposure_min_brightness", -1.2),
                ("override_auto_exposure_max_brightness", True),
                ("auto_exposure_max_brightness", 0.3),
                ("override_auto_exposure_low_percent", True),
                ("auto_exposure_low_percent", 70.0),
                ("override_auto_exposure_high_percent", True),
                ("auto_exposure_high_percent", 90.0),
                ("override_auto_exposure_speed_up", True),
                ("auto_exposure_speed_up", 1.2),
                ("override_auto_exposure_speed_down", True),
                ("auto_exposure_speed_down", 0.6),
                (
                    "override_local_exposure_highlight_contrast_scale",
                    True,
                ),
                ("local_exposure_highlight_contrast_scale", 0.60),
                (
                    "override_local_exposure_shadow_contrast_scale",
                    True,
                ),
                ("local_exposure_shadow_contrast_scale", 0.42),
                ("override_local_exposure_detail_strength", True),
                ("local_exposure_detail_strength", 1.0),
                ("override_vignette_intensity", True),
                ("vignette_intensity", 0.10),
                ("override_bloom_intensity", True),
                ("bloom_intensity", 0.12),
                ("override_film_slope", True),
                ("film_slope", 0.88),
                ("override_film_toe", True),
                ("film_toe", 0.35),
                ("override_film_shoulder", True),
                ("film_shoulder", 0.26),
            ):
                safe_set(settings, property_name, value)
            safe_set(actor, "settings", settings)


def move_player_to_school_gate(actor_subsystem):
    moved = 0
    test_characters = []
    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if label == "PlayerStart":
            actor.set_actor_location(
                unreal.Vector(-1800.0, 0.0, 105.0),
                False,
                False,
            )
            actor.set_actor_rotation(
                make_rotator((0.0, 10.0, 0.0)),
                False,
            )
            moved += 1
        elif label == "Character":
            test_characters.append(actor)
    if test_characters:
        require(
            actor_subsystem.destroy_actors(test_characters),
            "Unable to remove placed test character",
        )
        log("Removed {} placed test character actor(s)".format(
            len(test_characters)
        ))
    require(moved >= 1, "No player spawn actor was found")


def spawn_camera(
    actor_subsystem,
    label,
    location,
    target,
    focal_length=24.0,
    top_down=False,
    roll_degrees=0.0,
):
    camera_rotation = (
        (-90.0, 0.0, float(roll_degrees))
        if top_down
        else (
            look_at_rotation(location, target)[0],
            look_at_rotation(location, target)[1],
            float(roll_degrees),
        )
    )
    camera = actor_subsystem.spawn_actor_from_class(
        unreal.CineCameraActor,
        unreal.Vector(*location),
        make_rotator(camera_rotation),
        False,
    )
    require(camera is not None, "Unable to spawn camera {}".format(label))
    set_generated_metadata(
        camera,
        label,
        FOLDER_ROOT + "/Cameras",
    )
    component = camera.get_cine_camera_component()
    safe_set(component, "current_focal_length", float(focal_length))
    safe_set(component, "current_aperture", 4.0)
    safe_set(component, "constrain_aspect_ratio", True)
    safe_set(component, "aspect_ratio", 16.0 / 9.0)
    if top_down:
        safe_set(
            component,
            "projection_mode",
            unreal.CameraProjectionMode.ORTHOGRAPHIC,
        )
        safe_set(component, "ortho_width", 12000.0)
    return camera


def add_cameras(actor_subsystem):
    cameras = (
        (
            "CAM_OTS_Hero",
            (-1810.0, -20.0, 172.0),
            (1025.0, 250.0, 180.0),
            20.0,
            False,
        ),
        (
            "CAM_OTS_MainHome",
            (1025.0, -350.0, 190.0),
            (1025.0, 510.0, 185.0),
            32.0,
            False,
        ),
        (
            "CAM_OTS_Alley",
            (2570.0, 600.0, 168.0),
            (2570.0, 1220.0, 160.0),
            24.0,
            False,
        ),
        (
            "CAM_OTS_StreetDiagonal",
            (5200.0, -180.0, 185.0),
            (1850.0, 260.0, 170.0),
            26.0,
            False,
        ),
        (
            "CAM_OTS_TopDown",
            (1600.0, 0.0, 8500.0),
            (1600.0, 0.0, 0.0),
            28.0,
            False,
            90.0,
        ),
    )
    return [
        spawn_camera(actor_subsystem, *spec)
        for spec in cameras
    ]


def validate_scene(actor_subsystem, main_home):
    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    require(world is not None, "No editor world is loaded")
    require(
        world.get_path_name().startswith(TARGET_LEVEL + "."),
        "Refusing to validate or save unexpected world {}".format(
            world.get_path_name(),
        ),
    )
    actors = list(actor_subsystem.get_all_level_actors())
    labels = [actor.get_actor_label() for actor in actors]
    generated = [
        actor
        for actor in actors
        if actor.actor_has_tag(unreal.Name(GENERATOR_TAG))
    ]
    require(generated, "No generated OldTown actors were found")
    require(
        labels.count("BP_OTS_MainHomeInteractive") == 1,
        "MainHome instance must be unique",
    )
    require(
        all(
            labels.count(label) == 1
            for label in (
                "CAM_OTS_Hero",
                "CAM_OTS_MainHome",
                "CAM_OTS_Alley",
                "CAM_OTS_StreetDiagonal",
                "CAM_OTS_TopDown",
            )
        ),
        "Fixed comparison cameras are incomplete",
    )
    require(
        not any(label.startswith("BLK_R_Filler_01") for label in labels),
        "Replaced filler actors still exist",
    )
    require(
        "Blockout_SchoolGate_Closed" not in labels,
        "Closed school gate still exists",
    )
    require(
        "Plane" not in labels,
        "Unbounded source ground plane still exists",
    )
    for prefix in (
        "OTS_PerimeterGround",
        "OTS_AlleyPartyWallNorthWest",
        "OTS_AlleyPartyWallNorthEast",
        "OTS_AlleyPartyWallSouthWest",
        "OTS_AlleyPartyWallSouthEast",
        "OTS_SouthAlleyEndWallExtension",
        "OTS_SchoolEntranceRecess",
        "OTS_MainHomeCounter",
        "OTS_Light_MainHomeInteriorFront",
        "OTS_P3Prop_AwningAssemblySchoolSnack",
        "OTS_Window_R_D_R1_C1",
        "OTS_P1RoofParapetNorthEarly",
        "OTS_P2Prop_VendorTable",
        "OTS_P2NorthAlleyDrain",
        "OTS_StreetEndTJunctionRoadCenter",
        "OTS_StreetEndFocalFacade",
    ):
        require(
            any(label.startswith(prefix) for label in labels),
            "Required P0 scene element is missing: {}".format(prefix),
        )
    detailed_prop_actors = [
        actor
        for actor in actors
        if actor.get_actor_label().startswith("OTS_P2Prop_")
    ]
    expected_p2_mesh_counts = {
        "SM_P2_VendorTable": 1,
        "SM_P2_Thermos": 1,
        "SM_P2_ChineseStool": 1,
        "SM_P2_Toolbox": 1,
        "SM_P2_GasCylinder": 2,
        "SM_P2_Broom": 1,
        "SM_P2_ChestFreezer": 1,
        "SM_P2_OutdoorSink": 1,
        "SM_P2_TrashBin": 4,
        "SM_P2_PlantPot": 3,
        "SM_P2_CardboardBox": 6,
        "SM_P2_AlleyBench": 1,
        "SM_P2_WashBasin": 1,
        "SM_P2_ACUnit": 5,
        "SM_P2_MeterBox": 4,
        "SM_P2_Bicycle": 3,
        "SM_P2_WallUtilityCluster": 5,
        "SM_P2_StreetLamp": 7,
        "SM_P2_StormDrain": 6,
        "SM_P2_PuddlePatch": 7,
    }
    expected_collision_meshes = {
        "SM_P2_VendorTable",
        "SM_P2_ChestFreezer",
        "SM_P2_OutdoorSink",
        "SM_P2_TrashBin",
        "SM_P2_CardboardBox",
        "SM_P2_AlleyBench",
        "SM_P2_StreetLamp",
    }
    require(
        len(detailed_prop_actors) == sum(expected_p2_mesh_counts.values()),
        "Unexpected P2 detailed prop actor count: {}".format(
            len(detailed_prop_actors)
        ),
    )
    actual_p2_mesh_counts = {
        mesh_name: 0 for mesh_name in expected_p2_mesh_counts
    }
    for actor in detailed_prop_actors:
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        mesh = (
            component.get_editor_property("static_mesh")
            if component is not None
            else None
        )
        require(
            mesh is not None
            and mesh.get_path_name().startswith(DETAILED_PROP_ROOT + "/"),
            "{} does not use a P2 detailed mesh asset".format(
                actor.get_actor_label()
            ),
        )
        mesh_name = mesh.get_name()
        require(
            mesh_name in actual_p2_mesh_counts,
            "{} uses unexpected P2 mesh {}".format(
                actor.get_actor_label(),
                mesh_name,
            ),
        )
        actual_p2_mesh_counts[mesh_name] += 1
        should_collide = mesh_name in expected_collision_meshes
        require(
            bool(actor.get_actor_enable_collision()) == should_collide,
            "{} actor collision does not match its P2 specification".format(
                actor.get_actor_label()
            ),
        )
        require(
            (
                component.get_collision_enabled()
                != unreal.CollisionEnabled.NO_COLLISION
            )
            == should_collide,
            "{} component collision does not match its P2 specification".format(
                actor.get_actor_label()
            ),
        )
    require(
        actual_p2_mesh_counts == expected_p2_mesh_counts,
        "P2 detailed prop distribution drifted: {}".format(
            actual_p2_mesh_counts
        ),
    )
    p3_module_actors = [
        actor
        for actor in actors
        if actor.get_actor_label().startswith("OTS_P3Prop_")
    ]
    expected_p3_mesh_counts = {
        "SM_P3_StaticShutter": 5,
        "SM_P3_SignAssembly": 7,
        "SM_P3_AwningAssembly": 4,
        "SM_P3_SchoolGateLeaf": 2,
        "SM_P3_SchoolGatePost": 2,
        "SM_P3_AlleyCrossbar": 6,
        "SM_P3_SignText_Snack": 1,
        "SM_P3_SignText_General": 2,
        "SM_P3_SignText_Repair": 2,
        "SM_P3_SignText_Hardware": 2,
    }
    expected_p3_collision_meshes = {
        "SM_P3_SchoolGateLeaf",
        "SM_P3_SchoolGatePost",
    }
    require(
        len(p3_module_actors) == sum(expected_p3_mesh_counts.values()),
        "Unexpected P3 street module actor count: {}".format(
            len(p3_module_actors)
        ),
    )
    actual_p3_mesh_counts = {
        mesh_name: 0 for mesh_name in expected_p3_mesh_counts
    }
    for actor in p3_module_actors:
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        mesh = (
            component.get_editor_property("static_mesh")
            if component is not None
            else None
        )
        require(
            mesh is not None
            and mesh.get_path_name().startswith(P3_PROP_ROOT + "/"),
            "{} does not use a P3 module asset".format(
                actor.get_actor_label()
            ),
        )
        mesh_name = mesh.get_name()
        require(
            mesh_name in actual_p3_mesh_counts,
            "{} uses unexpected P3 mesh {}".format(
                actor.get_actor_label(),
                mesh_name,
            ),
        )
        actual_p3_mesh_counts[mesh_name] += 1
        should_collide = mesh_name in expected_p3_collision_meshes
        require(
            bool(actor.get_actor_enable_collision()) == should_collide,
            "{} actor collision does not match its P3 specification".format(
                actor.get_actor_label()
            ),
        )
        require(
            (
                component.get_collision_enabled()
                != unreal.CollisionEnabled.NO_COLLISION
            )
            == should_collide,
            "{} component collision does not match its P3 specification".format(
                actor.get_actor_label()
            ),
        )
    require(
        actual_p3_mesh_counts == expected_p3_mesh_counts,
        "P3 street module distribution drifted: {}".format(
            actual_p3_mesh_counts
        ),
    )
    # P5 replaces the last close-range floating assemblies with authored
    # player-range meshes.  All P5 objects are deliberately non-blocking: the
    # existing MainHome shell/counter retain collision ownership and the
    # facade pieces must never create a second invisible wall.
    p5_module_actors = [
        actor
        for actor in actors
        if actor.get_actor_label().startswith("OTS_P5Prop_")
    ]
    expected_p5_mesh_counts = {
        "SM_P5_LoadedLaundryRack": 5,
        "SM_P5_OldServiceDoorTransom": 3,
        "SM_P5_WallLampGooseneck": 3,
        "SM_P5_ShopShelfStocked": 1,
        "SM_P5_CounterDisplay": 2,
        "SM_P5_TallPharmacyCabinet": 1,
    }
    require(
        len(p5_module_actors) == sum(expected_p5_mesh_counts.values()),
        "Unexpected P5 player-range module actor count: {}".format(
            len(p5_module_actors)
        ),
    )
    actual_p5_mesh_counts = {
        mesh_name: 0 for mesh_name in expected_p5_mesh_counts
    }
    for actor in p5_module_actors:
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        mesh = (
            component.get_editor_property("static_mesh")
            if component is not None
            else None
        )
        require(
            mesh is not None
            and mesh.get_path_name().startswith(P5_PROP_ROOT + "/"),
            "{} does not use a P5 module asset".format(
                actor.get_actor_label()
            ),
        )
        mesh_name = mesh.get_name()
        require(
            mesh_name in actual_p5_mesh_counts,
            "{} uses unexpected P5 mesh {}".format(
                actor.get_actor_label(),
                mesh_name,
            ),
        )
        actual_p5_mesh_counts[mesh_name] += 1
        require(
            not bool(actor.get_actor_enable_collision())
            and component.get_collision_enabled()
            == unreal.CollisionEnabled.NO_COLLISION,
            "{} P5 module must remain non-colliding".format(
                actor.get_actor_label()
            ),
        )
    require(
        actual_p5_mesh_counts == expected_p5_mesh_counts,
        "P5 player-range module distribution drifted: {}".format(
            actual_p5_mesh_counts
        ),
    )
    window_mesh_names = {
        "SM_OTS_Window_Residential",
        "SM_OTS_Window_School",
    }
    architectural_window_actors = []
    for actor in generated:
        component = actor.get_component_by_class(
            unreal.StaticMeshComponent
        )
        mesh = (
            component.get_editor_property("static_mesh")
            if component is not None
            else None
        )
        if mesh is None or mesh.get_name() not in window_mesh_names:
            continue
        architectural_window_actors.append(actor)
        label = actor.get_actor_label()
        expected_mesh_name = (
            "SM_OTS_Window_School"
            if label.startswith(("OTS_SchoolMain_", "OTS_SchoolWing_"))
            else "SM_OTS_Window_Residential"
        )
        require(
            mesh.get_name() == expected_mesh_name,
            "{} uses {}, expected {}".format(
                label,
                mesh.get_name(),
                expected_mesh_name,
            ),
        )
        require(
            mesh.get_path_name().startswith(
                ARCHITECTURAL_MODULE_ROOT + "/"
            ),
            "{} uses an architectural window from an unexpected path".format(
                actor.get_actor_label()
            ),
        )
        require(
            component.get_num_materials() >= 5,
            "{} lost its five architectural material slots".format(
                actor.get_actor_label()
            ),
        )
        scale = actor.get_actor_scale3d()
        require(
            abs(float(scale.y) - 1.0) < 0.001,
            "{} scaled its authored window depth".format(label),
        )
        require(
            not bool(actor.get_actor_enable_collision())
            and component.get_collision_enabled()
            == unreal.CollisionEnabled.NO_COLLISION,
            "{} architectural window must remain non-colliding".format(
                actor.get_actor_label()
            ),
        )
    require(
        architectural_window_actors,
        "No reusable architectural window actors were generated",
    )
    architectural_window_labels = [
        actor.get_actor_label()
        for actor in architectural_window_actors
    ]
    for prefix in (
        "OTS_Window_",
        "OTS_SchoolMain_",
        "OTS_SchoolWing_",
        "OTS_PerimeterWindow",
        "OTS_StreetEndWindow_",
    ):
        require(
            any(
                label.startswith(prefix)
                for label in architectural_window_labels
            ),
            "Architectural window family is missing: {}".format(prefix),
        )
    location = main_home.get_actor_location()
    require(
        abs(location.x - 1025.0) < 0.1
        and abs(location.y - 920.0) < 0.1
        and abs(location.z) < 0.1,
        "MainHome transform drifted",
    )
    for actor in actors:
        location = actor.get_actor_location()
        values = (location.x, location.y, location.z)
        require(
            all(math.isfinite(float(value)) for value in values),
            "Non-finite actor transform: {}".format(actor.get_actor_label()),
        )
    return {
        "total_actor_count": len(actors),
        "generated_actor_count": len(generated),
        "p2_detailed_prop_actor_count": len(detailed_prop_actors),
        "p3_module_actor_count": len(p3_module_actors),
        "p5_module_actor_count": len(p5_module_actors),
        "p5_module_distribution": actual_p5_mesh_counts,
        "architectural_window_actor_count": len(
            architectural_window_actors
        ),
        "camera_count": sum(label.startswith("CAM_OTS_") for label in labels),
        "main_home_location": [1025.0, 920.0, 0.0],
        "target_level": TARGET_LEVEL,
        "source_level": SOURCE_LEVEL,
    }


def save_manifest(manifest):
    output_dir = PROJECT_ROOT / "Saved/CodexOutputs/OldTownSchoolStreet"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "SceneBuildManifest.json"
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def main():
    ensure_asset_directories()
    textures = import_scene_textures()
    materials = create_scene_materials(textures)
    imported_poles = import_pole_meshes()
    detailed_props = ensure_detailed_prop_assets()
    architectural_modules = ensure_architectural_module_assets()

    level_subsystem, actor_subsystem = create_target_level()
    meshes = {
        "cube": load_asset(CUBE_PATH),
        "cylinder": load_asset(CYLINDER_PATH),
    }

    remove_replaced_actors(actor_subsystem)
    assign_existing_materials(actor_subsystem, materials)
    main_home = spawn_main_home(actor_subsystem)
    add_main_home_interior_details(
        actor_subsystem,
        meshes,
        materials,
        detailed_props,
        main_home,
    )
    add_main_home_school_side_details(
        actor_subsystem,
        meshes,
        materials,
    )
    add_open_school_gate(
        actor_subsystem,
        meshes,
        materials,
        detailed_props,
    )
    add_school_identity_details(actor_subsystem, meshes, materials)
    add_facade_windows(
        actor_subsystem,
        meshes,
        materials,
        architectural_modules,
    )
    add_school_windows(
        actor_subsystem,
        meshes,
        materials,
        architectural_modules,
    )
    add_wall_grime_and_shop_details(actor_subsystem, meshes, materials)
    add_shopfront_p1_details(
        actor_subsystem,
        meshes,
        materials,
        detailed_props,
    )
    add_facade_character_details(
        actor_subsystem,
        meshes,
        materials,
        detailed_props,
    )
    add_utilities(actor_subsystem, meshes, materials, detailed_props)
    add_balconies(actor_subsystem, meshes, materials)
    add_rooftop_details(actor_subsystem, meshes, materials)
    add_rooftop_p1_details(actor_subsystem, meshes, materials)
    add_street_endcap(
        actor_subsystem,
        meshes,
        materials,
        architectural_modules,
        detailed_props,
    )
    add_puddles_and_road_wear(
        actor_subsystem,
        meshes,
        materials,
        detailed_props,
    )
    add_alley_props(actor_subsystem, meshes, materials, detailed_props)
    add_p2_street_life_details(
        actor_subsystem,
        meshes,
        materials,
        detailed_props,
    )
    add_perimeter_closure(
        actor_subsystem,
        meshes,
        materials,
        architectural_modules,
    )
    add_street_lights(
        actor_subsystem,
        meshes,
        materials,
        detailed_props,
    )
    add_procedural_electric_poles(actor_subsystem, meshes, materials)
    configure_atmosphere(actor_subsystem)
    for actor in actor_subsystem.get_all_level_actors():
        if actor.get_actor_label().startswith("OTS_P2Prop_PuddlePatch"):
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            component.set_material(0, materials["M_OTS_Puddle"])
            safe_set(component, "cast_shadow", False)
    move_player_to_school_gate(actor_subsystem)
    cameras = add_cameras(actor_subsystem)

    manifest = validate_scene(actor_subsystem, main_home)
    sys.path.insert(0, str(PROJECT_ROOT / "Scripts"))
    from OldTownFurnitureAudit import audit_actors, audit_end_windows
    manifest["p6_furniture_supports"] = audit_actors(actor_subsystem.get_all_level_actors())
    manifest["p6_end_window_clearance"] = audit_end_windows(actor_subsystem.get_all_level_actors())
    manifest.update(
        {
            "camera_labels": [
                camera.get_actor_label() for camera in cameras
            ],
            "imported_pole_mesh_count": len(imported_poles),
            "p2_detailed_prop_asset_count": 20,
            "p3_module_asset_count": 10,
            "p5_module_asset_count": 6,
            "architectural_module_asset_count": len(
                architectural_modules
            ),
            "texture_count": len(textures),
            "material_count": len(materials),
            "p0_visual_repair": {
                "continuous_perimeter": True,
                "north_alley_clear_width_cm": 200.0,
                "south_alley_clear_width_cm": 220.0,
                "school_identity_pass": True,
                "main_home_interior_pass": True,
                "bounded_exposure_ev100": [-1.2, 0.3],
                "point_light_intensity_scale": POINT_LIGHT_INTENSITY_SCALE,
            },
            "p1_visual_polish": {
                "layered_shopfronts": True,
                "asymmetric_street_lights": True,
                "residential_facade_life": True,
                "varied_roof_silhouettes": True,
                "street_life_clusters": True,
                "asymmetric_alley_life": True,
                "main_home_interaction_clearance_preserved": True,
                "single_actor_architectural_windows": True,
                "dual_scale_wall_anti_tiling": True,
                "wall_contact_penetration_cm": 2.0,
                "utility_pole_facade_clearance_cm": 95.0,
                "single_asset_shopfront_modules": True,
                "single_asset_school_gate_modules": True,
                "wall_anti_tiling_mode": "shared_world_noise_blend",
                "walkable_short_t_junction": True,
            },
            "p2_object_detail": {
                "one_static_mesh_asset_per_object": True,
                "engine_basic_shape_meshes_for_p2_props": False,
                "multi_material_regions": True,
                "curved_and_structural_details": True,
                "simple_collision_only_on_blocking_props": True,
                "sloped_cylinder_endpoint_alignment_fixed": True,
                "temporary_contact_audit_view_count": 26,
                "external_download_required": False,
            },
            "free_asset_sources": [
                "Poly Haven concrete_wall_003 (CC0)",
                "Poly Haven modular_electricity_poles (CC0)",
                "Poly Haven wood_table_worn 2K furniture PBR (CC0)",
                "ambientCG Asphalt027C (CC0)",
                "Poly Haven painted_plaster_wall (CC0)",
                "Poly Haven green_metal_rust (CC0)",
                "Noto Sans SC Medium glyph reference (SIL OFL 1.1; baked as low-poly sign geometry)",
            ],
        }
    )

    require(
        level_subsystem.save_current_level(),
        "Unable to save target level",
    )
    manifest_path = save_manifest(manifest)
    unreal.log(
        "{} actors={} generated={} cameras={} manifest={}".format(
            SUCCESS_MARKER,
            manifest["total_actor_count"],
            manifest["generated_actor_count"],
            manifest["camera_count"],
            manifest_path,
        )
    )
    return manifest


try:
    SCENE_BUILD_RESULT = main()
except Exception:
    unreal.log_error("OTS_BUILD_FAILED\n{}".format(traceback.format_exc()))
    raise
