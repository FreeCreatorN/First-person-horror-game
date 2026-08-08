"""Create detailed old-town prop Static Mesh assets with Geometry Script.

The module is intentionally side-effect free when imported.  Call
``ensure_detailed_prop_assets()`` from another editor script, or execute this
file directly with Unreal Editor's ``-ExecutePythonScript`` option.

All dimensions are centimetres.  Every mesh is authored around X/Y = 0 with
its lowest point at Z = 0, so the resulting Static Mesh pivot is at the centre
of the footprint on the floor.  A prop may contain several disconnected
primitive shells, but they are written into one Dynamic Mesh and saved as one
independent Static Mesh asset; no temporary level actors are created.
"""

from pathlib import Path
import math

try:
    import unreal
except ImportError:
    unreal = None


ASSET_ROOT = "/Game/Yastar/OldTownSchoolStreet/Props/Detailed"
MATERIAL_ROOT = ASSET_ROOT + "/Materials"
TEXTURE_ROOT = ASSET_ROOT + "/Textures"
P3_ASSET_ROOT = "/Game/Yastar/OldTownSchoolStreet/Props/P3"
P5_ASSET_ROOT = "/Game/Yastar/OldTownSchoolStreet/Props/P5"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLYHAVEN_ROOT = (
    PROJECT_ROOT
    / "SourceArt"
    / "ThirdParty"
    / "PolyHaven"
    / "modular_electricity_poles_1k"
)

WOOD_TEXTURE_SOURCES = {
    "T_P2_Wood_BaseColor": (
        POLYHAVEN_ROOT / "modular_electricity_poles_diff_1k.jpg",
        "color",
    ),
    "T_P2_Wood_Normal": (
        POLYHAVEN_ROOT / "modular_electricity_poles_nor_dx_1k.jpg",
        "normal",
    ),
    "T_P2_Wood_Roughness": (
        POLYHAVEN_ROOT / "modular_electricity_poles_rough_1k.jpg",
        "roughness",
    ),
}

MATERIAL_SETTINGS = {
    # name: base colour, worn colour, roughness, metallic, noise size in cm
    "M_P2_Wood": ((0.50, 0.245, 0.095, 1.0), (0.16, 0.070, 0.030, 1.0), 0.78, 0.0, 58.0),
    "M_P2_OldMetal": ((0.18, 0.19, 0.17, 1.0), (0.16, 0.055, 0.024, 1.0), 0.86, 0.72, 18.0),
    "M_P2_PaintedMetal": ((0.15, 0.24, 0.16, 1.0), (0.22, 0.070, 0.025, 1.0), 0.83, 0.12, 16.0),
    "M_P2_Enamel": ((0.78, 0.70, 0.56, 1.0), (0.28, 0.14, 0.060, 1.0), 0.48, 0.08, 13.0),
    "M_P2_Rubber": ((0.040, 0.038, 0.033, 1.0), (0.095, 0.082, 0.065, 1.0), 0.91, 0.0, 9.0),
    "M_P2_Brass": ((0.48, 0.305, 0.085, 1.0), (0.11, 0.14, 0.075, 1.0), 0.46, 0.86, 8.0),
    "M_P2_Leaf": ((0.105, 0.30, 0.085, 1.0), (0.24, 0.16, 0.045, 1.0), 0.82, 0.0, 13.0),
    "M_P2_Soil": ((0.075, 0.042, 0.022, 1.0), (0.025, 0.016, 0.010, 1.0), 0.98, 0.0, 8.0),
    "M_P2_Cardboard": ((0.55, 0.32, 0.14, 1.0), (0.24, 0.12, 0.050, 1.0), 0.92, 0.0, 24.0),
    "M_P2_Plastic": ((0.28, 0.30, 0.265, 1.0), (0.10, 0.11, 0.09, 1.0), 0.70, 0.0, 18.0),
    "M_P2_DarkGlass": ((0.025, 0.045, 0.052, 1.0), (0.008, 0.012, 0.014, 1.0), 0.16, 0.08, 55.0),
    "M_P2_WetPatch": ((0.012, 0.026, 0.036, 1.0), (0.006, 0.012, 0.018, 1.0), 0.08, 0.0, 42.0),
    "M_P2_Ceramic": ((0.77, 0.78, 0.70, 1.0), (0.28, 0.29, 0.24, 1.0), 0.38, 0.0, 24.0),
    "M_P2_Cloth": ((0.43, 0.12, 0.070, 1.0), (0.13, 0.055, 0.030, 1.0), 0.94, 0.0, 16.0),
}

PROP_ASSET_NAMES = {
    "VendorTable": "SM_P2_VendorTable",
    "Thermos": "SM_P2_Thermos",
    "ChineseStool": "SM_P2_ChineseStool",
    "Toolbox": "SM_P2_Toolbox",
    "GasCylinder": "SM_P2_GasCylinder",
    "Broom": "SM_P2_Broom",
    "ChestFreezer": "SM_P2_ChestFreezer",
    "OutdoorSink": "SM_P2_OutdoorSink",
    "TrashBin": "SM_P2_TrashBin",
    "PlantPot": "SM_P2_PlantPot",
    "CardboardBox": "SM_P2_CardboardBox",
    "AlleyBench": "SM_P2_AlleyBench",
    "WashBasin": "SM_P2_WashBasin",
    "ACUnit": "SM_P2_ACUnit",
    "MeterBox": "SM_P2_MeterBox",
    "Bicycle": "SM_P2_Bicycle",
    "WallUtilityCluster": "SM_P2_WallUtilityCluster",
    "StreetLamp": "SM_P2_StreetLamp",
    "StormDrain": "SM_P2_StormDrain",
    "PuddlePatch": "SM_P2_PuddlePatch",
}

P3_ASSET_NAMES = {
    "StaticShutter": "SM_P3_StaticShutter",
    "SignAssembly": "SM_P3_SignAssembly",
    "AwningAssembly": "SM_P3_AwningAssembly",
    "SchoolGateLeaf": "SM_P3_SchoolGateLeaf",
    "SchoolGatePost": "SM_P3_SchoolGatePost",
    "AlleyCrossbar": "SM_P3_AlleyCrossbar",
    "SignTextSnack": "SM_P3_SignText_Snack",
    "SignTextGeneral": "SM_P3_SignText_General",
    "SignTextRepair": "SM_P3_SignText_Repair",
    "SignTextHardware": "SM_P3_SignText_Hardware",
}

P5_ASSET_NAMES = {
    "LoadedLaundryRack": "SM_P5_LoadedLaundryRack",
    "OldServiceDoorTransom": "SM_P5_OldServiceDoorTransom",
    "WallLampGooseneck": "SM_P5_WallLampGooseneck",
}


# Compact 20 x 20 glyph masks sampled from Noto Sans SC Medium (SIL OFL 1.1).
# They are
# embedded rather than loaded from a font at build time, so the generated
# Static Mesh assets stay deterministic on every editor machine.
_SIGN_GLYPH_BITMAPS = {
    "小": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000001100000000000",
        "00000001100000000000", "00000001100000000000",
        "00001001100100000000", "00001001100110000000",
        "00011001100010000000", "00011001100011000000",
        "00110001100011000000", "00100001100001000000",
        "00000001100000000000", "00000001100000000000",
        "00000111000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "卖": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000001100000000000",
        "00011111111110000000", "00000001100000000000",
        "00111111111111000000", "00000000000010000000",
        "00000110100010000000", "00011100100000000000",
        "00111111111111000000", "00111111111111000000",
        "00000001010000000000", "00000110011110000000",
        "00011100000011000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "部": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000100000000000000",
        "00111111101111000000", "00000001001010000000",
        "00011001001010000000", "00001010001010000000",
        "00111111101010000000", "00000000001010000000",
        "00011111001001000000", "00010001001011000000",
        "00010001001110000000", "00011111001000000000",
        "00010001001000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "百": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00111111111111000000", "00000001000000000000",
        "00001111111100000000", "00001111111100000000",
        "00001000000100000000", "00001000000100000000",
        "00001111111100000000", "00001000000100000000",
        "00001000000100000000", "00001111111100000000",
        "00001000000100000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "货": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000110110010000000",
        "00001100111110000000", "00111101110000000000",
        "00001100110001000000", "00001100011110000000",
        "00001111111100000000", "00001111111100000000",
        "00001001100100000000", "00001001100100000000",
        "00001001010000000000", "00001110011110000000",
        "00011100000011000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "店": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000001100000000000",
        "00000000110000000000", "00011111111111000000",
        "00010000100000000000", "00010000111111000000",
        "00010000111110000000", "00010000100000000000",
        "00010111111110000000", "00010110000010000000",
        "00110110000010000000", "00110111111110000000",
        "00100110000010000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "修": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00001100110000000000",
        "00001000111110000000", "00011001100010000000",
        "00011011010100000000", "00111010011100000000",
        "00111011110111000000", "00011010001000000000",
        "00011010100100000000", "00011010011000000000",
        "00011010100010000000", "00011000011100000000",
        "00011001110000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "车": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000011000000000000",
        "00000010000000000000", "00111111111111000000",
        "00000100000000000000", "00001100100000000000",
        "00011111111110000000", "00001111111110000000",
        "00000000100000000000", "00111111111111000000",
        "00111111111111000000", "00000000100000000000",
        "00000000100000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "铺": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00011000001010000000",
        "00011110001010000000", "00110000001000000000",
        "00100000001000000000", "00011111111111000000",
        "00001001001011000000", "00111111111111000000",
        "00001001001011000000", "00001001111111000000",
        "00001011001011000000", "00001101001011000000",
        "00001001001010000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "五": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00011111111110000000", "00000001000000000000",
        "00000001000000000000", "00000001000000000000",
        "00001111111100000000", "00000010001100000000",
        "00000010001100000000", "00000010001100000000",
        "00000010001100000000", "00111111111111000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
    "金": (
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
        "00000000000000000000", "00000001100000000000",
        "00000001110000000000", "00000110011100000000",
        "00011100000110000000", "00110111111111000000",
        "00000001100000000000", "00000001100000000000",
        "00011111111110000000", "00001101100100000000",
        "00000101101000000000", "00111111111111000000",
        "00111111111111000000", "00000000000000000000",
        "00000000000000000000", "00000000000000000000",
    ),
}

_SIGN_TEXT_PHRASES = {
    "SignTextSnack": "小卖部",
    "SignTextGeneral": "百货店",
    "SignTextRepair": "修车铺",
    "SignTextHardware": "五金店",
}


def _require_unreal():
    if unreal is None:
        raise RuntimeError(
            "This function must run inside Unreal Editor with Geometry "
            "Scripting and Editor Scripting Utilities enabled."
        )


def _log(message):
    if unreal is not None:
        unreal.log("[OldTownDetailedProps] {}".format(message))


def _warn(message):
    if unreal is not None:
        unreal.log_warning("[OldTownDetailedProps] {}".format(message))


def _safe_set(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        return False


def _asset_exists(path):
    return unreal.EditorAssetLibrary.does_asset_exist(path)


def _load_asset(path):
    return (
        unreal.EditorAssetLibrary.load_asset(path)
        if _asset_exists(path)
        else None
    )


def _ensure_directories():
    for path in (
        ASSET_ROOT,
        MATERIAL_ROOT,
        TEXTURE_ROOT,
        P3_ASSET_ROOT,
        P5_ASSET_ROOT,
    ):
        unreal.EditorAssetLibrary.make_directory(path)


def _import_texture(asset_name, source_path, texture_kind):
    asset_path = "{}/{}".format(TEXTURE_ROOT, asset_name)
    existing = _load_asset(asset_path)
    if isinstance(existing, unreal.Texture2D):
        return existing

    if not source_path.is_file():
        _warn("Wood texture source is missing: {}".format(source_path))
        return None

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source_path))
    task.set_editor_property("destination_path", TEXTURE_ROOT)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("replace_existing_settings", False)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    texture = _load_asset(asset_path)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError("Failed to import Texture2D {}".format(asset_path))

    if texture_kind == "normal":
        _safe_set(texture, "srgb", False)
        _safe_set(
            texture,
            "compression_settings",
            unreal.TextureCompressionSettings.TC_NORMALMAP,
        )
    elif texture_kind == "roughness":
        _safe_set(texture, "srgb", False)
        grayscale = getattr(
            unreal.TextureCompressionSettings,
            "TC_GRAYSCALE",
            None,
        )
        if grayscale is not None:
            _safe_set(texture, "compression_settings", grayscale)
    _safe_set(texture, "virtual_texture_streaming", False)
    if not unreal.EditorAssetLibrary.save_loaded_asset(texture, False):
        raise RuntimeError("Unable to save texture {}".format(asset_path))
    return texture


def _ensure_wood_textures():
    return {
        name: _import_texture(name, source, kind)
        for name, (source, kind) in WOOD_TEXTURE_SOURCES.items()
    }


def _material_expression(material, expression_type, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        expression_type,
        int(x),
        int(y),
    )
    if node is None:
        raise RuntimeError(
            "Unable to create material expression {}".format(
                expression_type.__name__
            )
        )
    return node


def _constant_color(material, value, x, y):
    node = _material_expression(
        material,
        unreal.MaterialExpressionConstant3Vector,
        x,
        y,
    )
    node.set_editor_property("constant", unreal.LinearColor(*value))
    return node


def _constant_scalar(material, value, x, y):
    node = _material_expression(
        material,
        unreal.MaterialExpressionConstant,
        x,
        y,
    )
    node.set_editor_property("r", float(value))
    return node


def _connect(source, output_name, target, input_name):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source,
        output_name,
        target,
        input_name,
    ):
        raise RuntimeError(
            "Unable to connect material nodes {} -> {}".format(
                output_name,
                input_name,
            )
        )


def _connect_property(source, output_name, material_property):
    if not unreal.MaterialEditingLibrary.connect_material_property(
        source,
        output_name,
        material_property,
    ):
        raise RuntimeError(
            "Unable to connect material property {}".format(material_property)
        )


def _world_aligned_texture(material, texture, texture_size_cm, x, y, normal):
    function_name = (
        "WorldAlignedNormal.WorldAlignedNormal"
        if normal
        else "WorldAlignedTexture.WorldAlignedTexture"
    )
    function_path = (
        "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
        + function_name
    )
    material_function = _load_asset(function_path)
    if material_function is None:
        raise RuntimeError("Missing engine material function {}".format(function_path))

    texture_node = _material_expression(
        material,
        unreal.MaterialExpressionTextureObject,
        x,
        y,
    )
    texture_node.set_editor_property("texture", texture)
    if normal:
        _safe_set(
            texture_node,
            "sampler_type",
            unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
        )

    size_node = _constant_color(
        material,
        (
            float(texture_size_cm),
            float(texture_size_cm),
            float(texture_size_cm),
            1.0,
        ),
        x,
        y + 135,
    )
    call_node = _material_expression(
        material,
        unreal.MaterialExpressionMaterialFunctionCall,
        x + 275,
        y,
    )
    if not call_node.set_material_function(material_function):
        raise RuntimeError("Unable to use {}".format(function_path))
    _connect(texture_node, "", call_node, "TextureObject")
    _connect(size_node, "", call_node, "TextureSize")
    return call_node, "XYZ Texture"


def _create_material_asset(material_name):
    asset_path = "{}/{}".format(MATERIAL_ROOT, material_name)
    material = _load_asset(asset_path)
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            material_name,
            MATERIAL_ROOT,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
    if material is None:
        raise RuntimeError("Unable to create material {}".format(asset_path))
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    _safe_set(material, "two_sided", material_name == "M_P2_Leaf")
    return material


def _build_world_aligned_wood(material, textures):
    base_texture = textures.get("T_P2_Wood_BaseColor")
    normal_texture = textures.get("T_P2_Wood_Normal")
    rough_texture = textures.get("T_P2_Wood_Roughness")
    if any(
        texture is None
        for texture in (base_texture, normal_texture, rough_texture)
    ):
        return False

    base_node, base_output = _world_aligned_texture(
        material,
        base_texture,
        58.0,
        -1100,
        -420,
        False,
    )
    normal_node, normal_output = _world_aligned_texture(
        material,
        normal_texture,
        58.0,
        -1100,
        -60,
        True,
    )
    rough_node, rough_output = _world_aligned_texture(
        material,
        rough_texture,
        58.0,
        -1100,
        300,
        False,
    )
    tint = _constant_color(
        material,
        MATERIAL_SETTINGS["M_P2_Wood"][0],
        -400,
        -300,
    )
    base_multiply = _material_expression(
        material,
        unreal.MaterialExpressionMultiply,
        -125,
        -300,
    )
    rough_multiply = _material_expression(
        material,
        unreal.MaterialExpressionMultiply,
        -125,
        245,
    )
    rough_scale = _constant_scalar(material, 1.08, -400, 350)
    metallic = _constant_scalar(material, 0.0, -125, 430)

    _connect(base_node, base_output, base_multiply, "A")
    _connect(tint, "", base_multiply, "B")
    _connect(rough_node, rough_output, rough_multiply, "A")
    _connect(rough_scale, "", rough_multiply, "B")
    _connect_property(
        base_multiply,
        "",
        unreal.MaterialProperty.MP_BASE_COLOR,
    )
    _connect_property(
        normal_node,
        normal_output,
        unreal.MaterialProperty.MP_NORMAL,
    )
    _connect_property(
        rough_multiply,
        "",
        unreal.MaterialProperty.MP_ROUGHNESS,
    )
    _connect_property(metallic, "", unreal.MaterialProperty.MP_METALLIC)
    return True


def _build_procedural_pbr(material, settings):
    base_color, worn_color, roughness, metallic, noise_size = settings
    base = _constant_color(material, base_color, -720, -170)
    worn = _constant_color(material, worn_color, -720, 20)
    world_position = _material_expression(
        material,
        unreal.MaterialExpressionWorldPosition,
        -980,
        215,
    )
    noise = _material_expression(
        material,
        unreal.MaterialExpressionNoise,
        -680,
        215,
    )
    for property_name, value in (
        ("scale", 1.0 / float(noise_size)),
        ("quality", 2),
        ("levels", 3),
        ("output_min", 0.04),
        ("output_max", 0.32),
    ):
        _safe_set(noise, property_name, value)
    lerp = _material_expression(
        material,
        unreal.MaterialExpressionLinearInterpolate,
        -325,
        -85,
    )
    rough_clean = _constant_scalar(material, roughness, -390, 175)
    rough_worn = _constant_scalar(
        material,
        min(1.0, float(roughness) + 0.16),
        -390,
        260,
    )
    rough_lerp = _material_expression(
        material,
        unreal.MaterialExpressionLinearInterpolate,
        -80,
        205,
    )
    metal_clean = _constant_scalar(material, metallic, -390, 370)
    metal_worn = _constant_scalar(
        material,
        max(0.0, float(metallic) * 0.18),
        -390,
        455,
    )
    metal_lerp = _material_expression(
        material,
        unreal.MaterialExpressionLinearInterpolate,
        -80,
        400,
    )
    _connect(world_position, "", noise, "World Position")
    _connect(base, "", lerp, "A")
    _connect(worn, "", lerp, "B")
    _connect(noise, "", lerp, "Alpha")
    _connect(rough_clean, "", rough_lerp, "A")
    _connect(rough_worn, "", rough_lerp, "B")
    _connect(noise, "", rough_lerp, "Alpha")
    _connect(metal_clean, "", metal_lerp, "A")
    _connect(metal_worn, "", metal_lerp, "B")
    _connect(noise, "", metal_lerp, "Alpha")
    _connect_property(lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    _connect_property(rough_lerp, "", unreal.MaterialProperty.MP_ROUGHNESS)
    _connect_property(metal_lerp, "", unreal.MaterialProperty.MP_METALLIC)


def _ensure_materials(wood_textures):
    materials = {}
    for material_name, settings in MATERIAL_SETTINGS.items():
        material = _create_material_asset(material_name)
        built_wood = (
            material_name == "M_P2_Wood"
            and _build_world_aligned_wood(material, wood_textures)
        )
        if not built_wood:
            _build_procedural_pbr(material, settings)
        unreal.MaterialEditingLibrary.recompile_material(material)
        if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
            raise RuntimeError(
                "Unable to save material {}/{}".format(
                    MATERIAL_ROOT,
                    material_name,
                )
            )
        materials[material_name] = material
    return materials


def _make_transform(location, rotation=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
    # Rotation tuple is (pitch, yaw, roll), matching familiar UE labels.
    return unreal.Transform(
        location=unreal.Vector(*[float(value) for value in location]),
        rotation=unreal.Rotator(
            pitch=float(rotation[0]),
            yaw=float(rotation[1]),
            roll=float(rotation[2]),
        ),
        scale=unreal.Vector(*[float(value) for value in scale]),
    )


def _enable_material_ids(dynamic_mesh):
    material_library = getattr(unreal, "GeometryScript_Materials", None)
    for method_name in ("enable_material_i_ds", "enable_material_ids"):
        method = getattr(material_library, method_name, None)
        if callable(method):
            method(dynamic_mesh)
            return
    for method_name in ("enable_material_i_ds", "enable_material_ids"):
        method = getattr(dynamic_mesh, method_name, None)
        if callable(method):
            method()
            return
    raise RuntimeError("Geometry Script material ID support is unavailable")


def _primitive_options(material_id):
    options = unreal.GeometryScriptPrimitiveOptions()
    options.set_editor_property("material_id", int(material_id))
    polygroup_mode = getattr(
        unreal,
        "GeometryScriptPrimitivePolygroupMode",
        None,
    )
    if polygroup_mode is not None:
        _safe_set(options, "polygroup_mode", polygroup_mode.PER_FACE)
    return options


def _normalise_mesh_result(result, current_mesh):
    if isinstance(result, tuple):
        result = result[0] if result else None
    return current_mesh if result is None else result


class PropMeshBuilder:
    """Accumulate detailed primitive shells into one material-aware mesh."""

    def __init__(self, logical_name):
        self.logical_name = logical_name
        self.mesh = unreal.DynamicMesh()
        _enable_material_ids(self.mesh)
        self.material_names = []
        self.collision_boxes = []

    def _material_id(self, material_name):
        if material_name not in MATERIAL_SETTINGS:
            raise ValueError(
                "{} uses unknown material {}".format(
                    self.logical_name,
                    material_name,
                )
            )
        if material_name not in self.material_names:
            self.material_names.append(material_name)
        return self.material_names.index(material_name)

    def _options(self, material_name):
        return _primitive_options(self._material_id(material_name))

    def box(
        self,
        location,
        size,
        material_name,
        rotation=(0.0, 0.0, 0.0),
        steps=0,
        bevel=None,
        bevel_subdivisions=1,
    ):
        if min(size) <= 0.0:
            raise ValueError("{} contains a zero-size box".format(self.logical_name))
        material_id = self._material_id(material_name)
        if bevel is None:
            # Real furniture/utility objects almost never have mathematically
            # sharp manufactured edges.  Keep the radius proportional for thin
            # rails and cap it for large carcasses.
            bevel = min(1.25, max(0.12, float(min(size)) * 0.16))

        if bevel > 0.0 and min(size) >= 0.65:
            temp_mesh = unreal.DynamicMesh()
            _enable_material_ids(temp_mesh)
            result = unreal.GeometryScript_Primitives.append_box(
                temp_mesh,
                _primitive_options(material_id),
                _make_transform(location, rotation),
                float(size[0]),
                float(size[1]),
                float(size[2]),
                int(steps),
                int(steps),
                int(steps),
                unreal.GeometryScriptPrimitiveOriginMode.CENTER,
            )
            temp_mesh = _normalise_mesh_result(result, temp_mesh)
            try:
                bevel_options = unreal.GeometryScriptMeshBevelOptions()
                bevel_options.set_editor_property(
                    "bevel_distance",
                    float(bevel),
                )
                bevel_options.set_editor_property("infer_material_id", True)
                bevel_options.set_editor_property(
                    "set_material_id",
                    int(material_id),
                )
                bevel_options.set_editor_property(
                    "subdivisions",
                    max(0, int(bevel_subdivisions)),
                )
                bevel_options.set_editor_property("round_weight", 0.72)
                result = (
                    unreal.GeometryScript_MeshModeling
                    .apply_mesh_polygroup_bevel(
                        temp_mesh,
                        bevel_options,
                    )
                )
                temp_mesh = _normalise_mesh_result(result, temp_mesh)
                append_options = unreal.GeometryScriptAppendMeshOptions()
                result = unreal.GeometryScript_MeshEdits.append_mesh(
                    self.mesh,
                    temp_mesh,
                    _make_transform((0.0, 0.0, 0.0)),
                    False,
                    append_options,
                )
                self.mesh = _normalise_mesh_result(result, self.mesh)
                return self
            except Exception as exc:
                # Extremely thin pieces can occasionally reject a bevel.  They
                # are decorative, so use their valid sharp version and keep the
                # complete asset build deterministic.
                _warn(
                    "{} box bevel skipped ({}): {}".format(
                        self.logical_name,
                        size,
                        exc,
                    )
                )

        result = unreal.GeometryScript_Primitives.append_box(
            self.mesh,
            _primitive_options(material_id),
            _make_transform(location, rotation),
            float(size[0]),
            float(size[1]),
            float(size[2]),
            int(steps),
            int(steps),
            int(steps),
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        self.mesh = _normalise_mesh_result(result, self.mesh)
        return self

    def cylinder(
        self,
        location,
        radius,
        height,
        material_name,
        rotation=(0.0, 0.0, 0.0),
        radial_steps=16,
        height_steps=1,
        scale=(1.0, 1.0, 1.0),
    ):
        result = unreal.GeometryScript_Primitives.append_cylinder(
            self.mesh,
            self._options(material_name),
            _make_transform(location, rotation, scale),
            float(radius),
            float(height),
            int(radial_steps),
            int(height_steps),
            True,
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        self.mesh = _normalise_mesh_result(result, self.mesh)
        return self

    def cylinder_between(
        self,
        start,
        end,
        radius,
        material_name,
        radial_steps=12,
    ):
        """Append a cylinder whose capped ends meet two authored points."""
        start = tuple(float(value) for value in start)
        end = tuple(float(value) for value in end)
        direction = tuple(end[i] - start[i] for i in range(3))
        length = math.sqrt(sum(value * value for value in direction))
        if length <= 0.001:
            raise ValueError(
                "{} contains a zero-length connector".format(
                    self.logical_name
                )
            )
        midpoint = tuple((start[i] + end[i]) * 0.5 for i in range(3))
        unit_z = max(-1.0, min(1.0, direction[2] / length))
        # Geometry Script cylinders are authored along local +Z.  Unreal's
        # positive Pitch rotates +Z toward -X/-Y, so the former positive angle
        # mirrored every sloped connector around its midpoint.  A negative
        # Pitch makes the cylinder caps land on the two authored endpoints.
        pitch = -math.degrees(math.acos(unit_z))
        yaw = math.degrees(math.atan2(direction[1], direction[0]))
        return self.cylinder(
            midpoint,
            radius,
            length,
            material_name,
            rotation=(pitch, yaw, 0.0),
            radial_steps=radial_steps,
        )

    def cone(
        self,
        location,
        base_radius,
        top_radius,
        height,
        material_name,
        rotation=(0.0, 0.0, 0.0),
        radial_steps=16,
        height_steps=2,
        scale=(1.0, 1.0, 1.0),
    ):
        result = unreal.GeometryScript_Primitives.append_cone(
            self.mesh,
            self._options(material_name),
            _make_transform(location, rotation, scale),
            float(base_radius),
            float(top_radius),
            float(height),
            int(radial_steps),
            int(height_steps),
            True,
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        self.mesh = _normalise_mesh_result(result, self.mesh)
        return self

    def sphere(
        self,
        location,
        radius,
        material_name,
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        phi_steps=12,
        theta_steps=20,
    ):
        result = unreal.GeometryScript_Primitives.append_sphere_lat_long(
            self.mesh,
            self._options(material_name),
            _make_transform(location, rotation, scale),
            float(radius),
            int(phi_steps),
            int(theta_steps),
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        self.mesh = _normalise_mesh_result(result, self.mesh)
        return self

    def capsule(
        self,
        location,
        radius,
        line_length,
        material_name,
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        hemisphere_steps=5,
        circle_steps=16,
    ):
        result = unreal.GeometryScript_Primitives.append_capsule(
            self.mesh,
            self._options(material_name),
            _make_transform(location, rotation, scale),
            float(radius),
            float(line_length),
            int(hemisphere_steps),
            int(circle_steps),
            1,
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        self.mesh = _normalise_mesh_result(result, self.mesh)
        return self

    def torus(
        self,
        location,
        major_radius,
        minor_radius,
        material_name,
        rotation=(0.0, 0.0, 0.0),
        major_steps=24,
        minor_steps=8,
        revolve_degrees=360.0,
        degree_offset=0.0,
        scale=(1.0, 1.0, 1.0),
    ):
        revolve = unreal.GeometryScriptRevolveOptions()
        _safe_set(revolve, "revolve_degrees", float(revolve_degrees))
        _safe_set(revolve, "degree_offset", float(degree_offset))
        _safe_set(revolve, "hard_normals", False)
        _safe_set(revolve, "fill_partial_revolve_endcaps", True)
        result = unreal.GeometryScript_Primitives.append_torus(
            self.mesh,
            self._options(material_name),
            _make_transform(location, rotation, scale),
            revolve,
            float(major_radius),
            float(minor_radius),
            int(major_steps),
            int(minor_steps),
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        self.mesh = _normalise_mesh_result(result, self.mesh)
        return self

    def extruded_polygon(
        self,
        vertices,
        height,
        material_name,
        location=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
    ):
        """Append a capped custom 2D outline with a shallow Z thickness."""
        polygon = [
            unreal.Vector2D(x=float(x), y=float(y))
            for x, y in vertices
        ]
        result = (
            unreal.GeometryScript_Primitives
            .append_simple_extrude_polygon(
                self.mesh,
                self._options(material_name),
                _make_transform(location, rotation, scale),
                polygon,
                float(height),
                0,
                True,
                unreal.GeometryScriptPrimitiveOriginMode.BASE,
            )
        )
        self.mesh = _normalise_mesh_result(result, self.mesh)
        return self

    def collision_box(self, location, size, rotation=(0.0, 0.0, 0.0)):
        self.collision_boxes.append(
            (
                tuple(float(value) for value in location),
                tuple(float(value) for value in size),
                tuple(float(value) for value in rotation),
            )
        )
        return self


def _build_vendor_table():
    b = PropMeshBuilder("VendorTable")
    # A rounded timber slab with a separate metal edge band reads as one
    # manufactured counter instead of a bare cube resting on four posts.
    b.box(
        (0, 0, 76.25),
        (116, 54, 6.5),
        "M_P2_Wood",
        steps=1,
        bevel=1.6,
        bevel_subdivisions=3,
    )
    for y in (-28.0, 28.0):
        b.box(
            (0, y, 76.0),
            (116, 2.0, 6.5),
            "M_P2_OldMetal",
            bevel=0.55,
            bevel_subdivisions=2,
        )
    for x in (-59.0, 59.0):
        b.box(
            (x, 0, 76.0),
            (2.0, 54, 6.5),
            "M_P2_OldMetal",
            bevel=0.55,
            bevel_subdivisions=2,
        )

    # Connected leg frame, mounting plates and rubber feet.  Every stretcher
    # reaches a leg, so close views no longer expose floating braces.
    for x in (-52, 52):
        for y in (-22, 22):
            b.box(
                (x, y, 37),
                (7, 7, 70),
                "M_P2_OldMetal",
                bevel=0.8,
                bevel_subdivisions=2,
            )
            b.box(
                (x, y, 69.0),
                (11, 11, 3),
                "M_P2_OldMetal",
                bevel=0.55,
                bevel_subdivisions=2,
            )
            b.cylinder((x, y, 2), 4.6, 4, "M_P2_Rubber", radial_steps=12)
    for y in (-22, 22):
        b.box(
            (0, y, 31),
            (104, 3.2, 3.2),
            "M_P2_OldMetal",
            bevel=0.6,
            bevel_subdivisions=2,
        )
    for x in (-52, 52):
        b.box(
            (x, 0, 37),
            (3.2, 44, 3.2),
            "M_P2_OldMetal",
            bevel=0.6,
            bevel_subdivisions=2,
        )

    # The lower shelf is built from individual boards with narrow drainage
    # gaps, a common construction detail on improvised street counters.
    for y in (-14, 0, 14):
        b.box(
            (0, y, 24),
            (100, 10.5, 3.5),
            "M_P2_Wood",
            bevel=0.65,
            bevel_subdivisions=2,
        )

    for y in (-24.5, 24.5):
        b.box(
            (0, y, 68),
            (104, 3, 8),
            "M_P2_OldMetal",
            bevel=0.6,
            bevel_subdivisions=2,
        )
    for x in (-52, 52):
        b.box(
            (x, 0, 68),
            (3, 46, 8),
            "M_P2_OldMetal",
            bevel=0.6,
            bevel_subdivisions=2,
        )

    # Real drawer depth, recessed shadow gap, rounded face and a connected
    # stand-off handle replace the previous flat square pasted on the apron.
    b.box(
        (0, -21.5, 55),
        (40, 14, 17),
        "M_P2_PaintedMetal",
        bevel=0.9,
        bevel_subdivisions=2,
    )
    b.box(
        (0, -28.85, 55),
        (44, 0.9, 21),
        "M_P2_Rubber",
        bevel=0.25,
        bevel_subdivisions=2,
    )
    b.box(
        (0, -30.0, 55),
        (40, 1.4, 17),
        "M_P2_PaintedMetal",
        bevel=0.75,
        bevel_subdivisions=2,
    )
    for x in (-7, 7):
        b.cylinder_between(
            (x, -30.7, 55),
            (x, -32.0, 55),
            1.0,
            "M_P2_Brass",
            radial_steps=12,
        )
    b.cylinder_between(
        (-7, -32.0, 55),
        (7, -32.0, 55),
        1.0,
        "M_P2_Brass",
        radial_steps=14,
    )
    for x in (-48, 48):
        b.cylinder(
            (x, -26.5, 68),
            1.5,
            1.2,
            "M_P2_Brass",
            rotation=(0, 0, 90),
            radial_steps=12,
        )
    b.collision_box((0, 0, 42), (120, 58, 84))
    return b


def _build_thermos():
    b = PropMeshBuilder("Thermos")
    b.cylinder((0, 0, 3), 9.2, 6, "M_P2_Rubber", radial_steps=20)
    b.cone((0, 0, 20), 9.5, 8.5, 30, "M_P2_Enamel", radial_steps=24, height_steps=3)
    b.cone((0, 0, 36), 8.5, 5.8, 7, "M_P2_Enamel", radial_steps=24)
    b.cylinder((0, 0, 41), 5.8, 5, "M_P2_OldMetal", radial_steps=20)
    b.cylinder((0, 0, 45), 4.8, 4, "M_P2_Plastic", radial_steps=20)
    b.torus(
        (0, 0, 32),
        11.8,
        1.7,
        "M_P2_Plastic",
        rotation=(0, 0, 90),
        major_steps=28,
        revolve_degrees=180.0,
    )
    b.cylinder((0, -10.5, 35), 2.2, 13, "M_P2_Enamel", rotation=(0, 0, 90), radial_steps=16)
    b.cone((0, -18, 35), 3.2, 1.7, 7, "M_P2_Enamel", rotation=(0, 0, 90), radial_steps=16)
    b.torus((0, 0, 8), 8.8, 0.7, "M_P2_OldMetal", major_steps=24)
    return b


def _build_chinese_stool():
    b = PropMeshBuilder("ChineseStool")
    b.cylinder((0, 0, 40), 16, 5, "M_P2_Wood", radial_steps=24)
    b.cylinder((0, 0, 43), 14, 1.5, "M_P2_OldMetal", radial_steps=24)
    for x, y, pitch, roll in (
        (-10, -10, -6, 6),
        (10, -10, 6, 6),
        (-10, 10, -6, -6),
        (10, 10, 6, -6),
    ):
        b.cylinder(
            (x, y, 20),
            2.5,
            39,
            "M_P2_Wood",
            rotation=(pitch, 0, roll),
            radial_steps=12,
        )
    for y in (-10, 10):
        b.cylinder((0, y, 16), 1.6, 22, "M_P2_Wood", rotation=(90, 0, 0), radial_steps=10)
    for x in (-10, 10):
        b.cylinder((x, 0, 18), 1.6, 22, "M_P2_Wood", rotation=(0, 0, 90), radial_steps=10)
    return b


def _build_toolbox():
    b = PropMeshBuilder("Toolbox")
    b.box(
        (0, 0, 9.5),
        (48, 26, 19),
        "M_P2_PaintedMetal",
        steps=1,
        bevel=1.35,
        bevel_subdivisions=3,
    )
    # Folded lower rails and corner guards give the carcass a believable
    # sheet-metal construction while keeping the original floor origin.
    for y in (-13.5, 13.5):
        b.box(
            (0, y, 3.0),
            (48, 2.0, 5.0),
            "M_P2_OldMetal",
            bevel=0.55,
            bevel_subdivisions=2,
        )
    for x in (-24.5, 24.5):
        b.box(
            (x, 0, 10),
            (1.5, 25, 17),
            "M_P2_OldMetal",
            bevel=0.45,
            bevel_subdivisions=2,
        )

    # Overlapping lid shell, raised centre pressing and rolled perimeter lip.
    b.box(
        (0, 0, 21.5),
        (52, 30, 4),
        "M_P2_PaintedMetal",
        steps=1,
        bevel=1.15,
        bevel_subdivisions=3,
    )
    b.box(
        (0, 0, 23.7),
        (46, 24, 1.2),
        "M_P2_PaintedMetal",
        bevel=0.45,
        bevel_subdivisions=2,
    )
    for y in (-14.8, 14.8):
        b.box(
            (0, y, 20.5),
            (48, 1.4, 4.5),
            "M_P2_OldMetal",
            bevel=0.4,
            bevel_subdivisions=2,
        )
    for x in (-25.2, 25.2):
        b.box(
            (x, 0, 20.5),
            (1.4, 27, 4.5),
            "M_P2_OldMetal",
            bevel=0.4,
            bevel_subdivisions=2,
        )

    # Rear hinge leaves and barrels are visibly connected to both shells.
    for x in (-15, 15):
        b.box(
            (x, 14.9, 20.0),
            (9, 1.6, 5),
            "M_P2_OldMetal",
            bevel=0.35,
            bevel_subdivisions=2,
        )
        b.cylinder(
            (x, 14.2, 21.0),
            1.2,
            8,
            "M_P2_OldMetal",
            rotation=(90, 0, 0),
            radial_steps=14,
        )

    # Two-piece front draw latches with backing plates and lever tabs.
    for x in (-16, 16):
        b.box(
            (x, -15.2, 13),
            (7, 1.6, 9),
            "M_P2_Brass",
            bevel=0.55,
            bevel_subdivisions=2,
        )
        b.box(
            (x, -16.2, 10.5),
            (3.5, 1.2, 4),
            "M_P2_OldMetal",
            bevel=0.35,
            bevel_subdivisions=2,
        )

    # Separate handle feet, uprights and rubber grip avoid the former floating
    # half-torus and make the load path legible at arm's length.
    for x in (-9, 9):
        b.box(
            (x, 0, 23.6),
            (5, 5, 2),
            "M_P2_OldMetal",
            bevel=0.55,
            bevel_subdivisions=2,
        )
        b.cylinder_between(
            (x, 0, 24.0),
            (x, 0, 33.0),
            1.4,
            "M_P2_OldMetal",
            radial_steps=14,
        )
    b.cylinder_between(
        (-9, 0, 33.0),
        (9, 0, 33.0),
        1.8,
        "M_P2_Rubber",
        radial_steps=16,
    )
    return b


def _build_gas_cylinder():
    b = PropMeshBuilder("GasCylinder")
    b.cylinder((0, 0, 5), 13.2, 10, "M_P2_OldMetal", radial_steps=24)
    b.cylinder((0, 0, 38), 13, 60, "M_P2_PaintedMetal", radial_steps=24, height_steps=3)
    b.cone((0, 0, 70), 13, 5.2, 10, "M_P2_PaintedMetal", radial_steps=24, height_steps=3)
    b.cylinder((0, 0, 77), 4.6, 5, "M_P2_Brass", radial_steps=16)
    b.cylinder((0, 0, 82), 2, 6, "M_P2_Brass", radial_steps=12)
    b.cylinder((4, 0, 81), 1.5, 8, "M_P2_Brass", rotation=(90, 0, 0), radial_steps=10)
    b.torus((0, 0, 79), 8.5, 1.8, "M_P2_OldMetal", major_steps=24)
    for x in (-7, 7):
        b.box((x, 0, 75), (2.2, 3, 12), "M_P2_OldMetal")
    b.torus((0, 0, 10), 12.8, 0.8, "M_P2_OldMetal", major_steps=24)
    b.collision_box((0, 0, 39), (27, 27, 78))
    return b


def _build_broom():
    b = PropMeshBuilder("Broom")
    b.cylinder((0, 0, 84), 1.5, 116, "M_P2_Wood", rotation=(0, 0, -3), radial_steps=12)
    b.cylinder((0, 0, 143), 2.3, 4, "M_P2_Rubber", radial_steps=12)
    b.box((0, 0, 24), (28, 7, 5), "M_P2_Wood")
    b.cone((0, 0, 12), 14, 11, 24, "M_P2_Cloth", radial_steps=20, height_steps=3, scale=(1.0, 0.32, 1.0))
    b.box((0, 0, 23), (24, 8, 3), "M_P2_OldMetal")
    for x in (-9, -4.5, 0, 4.5, 9):
        b.capsule((x, 0, 7), 0.65, 12, "M_P2_Cloth", circle_steps=8)
    return b


def _build_chest_freezer():
    b = PropMeshBuilder("ChestFreezer")
    b.box(
        (0, 0, 41),
        (100, 62, 78),
        "M_P2_Enamel",
        steps=1,
        bevel=2.6,
        bevel_subdivisions=3,
    )
    b.box(
        (0, 0, 82),
        (102, 64, 7),
        "M_P2_Plastic",
        steps=1,
        bevel=2.15,
        bevel_subdivisions=3,
    )
    b.box(
        (0, 0, 85.7),
        (90, 52, 1.0),
        "M_P2_Enamel",
        steps=1,
        bevel=0.35,
        bevel_subdivisions=2,
    )

    # A continuous dark door seal sits between the rounded cabinet and lid.
    for y in (-31.4, 31.4):
        b.box(
            (0, y, 79.4),
            (96, 1.6, 2.0),
            "M_P2_Rubber",
            bevel=0.3,
            bevel_subdivisions=2,
        )
    for x in (-49.4, 49.4):
        b.box(
            (x, 0, 79.4),
            (1.6, 61, 2.0),
            "M_P2_Rubber",
            bevel=0.3,
            bevel_subdivisions=2,
        )

    # Compact handle: mounting plates, diagonal stand-offs and one connected
    # grip.  It stays comfortably inside the old handle's visual envelope.
    for x in (-6.5, 6.5):
        b.box(
            (x, -32.6, 78),
            (4, 1.6, 5),
            "M_P2_OldMetal",
            bevel=0.5,
            bevel_subdivisions=2,
        )
        b.cylinder_between(
            (x, -33.0, 77.0),
            (x, -35.5, 74.0),
            1.15,
            "M_P2_OldMetal",
            radial_steps=14,
        )
    b.cylinder_between(
        (-6.5, -35.5, 74.0),
        (6.5, -35.5, 74.0),
        1.35,
        "M_P2_OldMetal",
        radial_steps=16,
    )

    # Paired rear hinge leaves and barrels expose the lid's working thickness.
    for x in (-36, 36):
        b.box(
            (x, 31.4, 79),
            (12, 2.2, 6),
            "M_P2_OldMetal",
            bevel=0.45,
            bevel_subdivisions=2,
        )
        b.cylinder(
            (x, 32.8, 80.5),
            1.7,
            11,
            "M_P2_OldMetal",
            rotation=(90, 0, 0),
            radial_steps=14,
        )

    # Recessed compressor vent: dark cavity, raised bezel and individual slats.
    b.box(
        (30, -31.45, 21),
        (32, 0.9, 30),
        "M_P2_Rubber",
        bevel=0.55,
        bevel_subdivisions=2,
    )
    for x, z, sx, sz in (
        (30, 7, 34, 2),
        (30, 35, 34, 2),
        (13, 21, 2, 30),
        (47, 21, 2, 30),
    ):
        b.box(
            (x, -32.25, z),
            (sx, 1.0, sz),
            "M_P2_OldMetal",
            bevel=0.25,
            bevel_subdivisions=2,
        )
    for z in (12, 17, 22, 27, 32):
        b.box(
            (30, -32.55, z),
            (27, 1.0, 1.4),
            "M_P2_OldMetal",
            bevel=0.3,
            bevel_subdivisions=2,
        )

    # An inset controller uses a proud frame around a deeper dark face, with
    # a mechanical thermostat, status lamps and a separate lid latch.
    b.box(
        (-30, -31.45, 53),
        (24, 0.9, 14),
        "M_P2_Rubber",
        bevel=0.45,
        bevel_subdivisions=2,
    )
    for x, z, sx, sz in (
        (-30, 60, 26, 2),
        (-30, 46, 26, 2),
        (-43, 53, 2, 14),
        (-17, 53, 2, 14),
    ):
        b.box(
            (x, -32.15, z),
            (sx, 1.0, sz),
            "M_P2_OldMetal",
            bevel=0.25,
            bevel_subdivisions=2,
        )
    b.box(
        (0, -32.7, 65),
        (9, 1.8, 7),
        "M_P2_OldMetal",
        bevel=0.55,
        bevel_subdivisions=2,
    )
    b.box(
        (0, -34.0, 63),
        (3.5, 1.2, 4),
        "M_P2_Brass",
        bevel=0.35,
        bevel_subdivisions=2,
    )
    b.cylinder(
        (-23, -32.85, 53),
        1.6,
        1.4,
        "M_P2_Brass",
        rotation=(0, 0, 90),
        radial_steps=14,
    )
    b.box((-36, -32.9, 53), (3.0, 0.8, 3.0), "M_P2_Leaf", bevel=0.3)
    b.box((-31, -32.9, 53), (3.0, 0.8, 3.0), "M_P2_Cloth", bevel=0.3)

    # Four caster forks and correctly oriented wheels keep the cabinet grounded.
    for x in (-43, 43):
        for y in (-25, 25):
            b.box(
                (x, y, 5.5),
                (5, 4, 7),
                "M_P2_OldMetal",
                bevel=0.7,
                bevel_subdivisions=2,
            )
            b.cylinder(
                (x, y, 3.5),
                3.5,
                3.2,
                "M_P2_Rubber",
                rotation=(0, 0, 90),
                radial_steps=16,
            )

    # A short power lead, moulded plug and prongs emerge from the rear without
    # changing the placement-facing front of the asset.
    b.cylinder_between((42, 31.5, 19), (49, 35, 10), 1.0, "M_P2_Rubber")
    b.cylinder_between((49, 35, 10), (53.0, 37.5, 4), 1.0, "M_P2_Rubber")
    b.box(
        (54.0, 38.5, 4),
        (2.0, 3.0, 5.0),
        "M_P2_Rubber",
        bevel=0.6,
        bevel_subdivisions=2,
    )
    for y in (38.0, 39.0):
        b.cylinder(
            (55.0, y, 4),
            0.45,
            2.0,
            "M_P2_Brass",
            rotation=(90, 0, 0),
            radial_steps=8,
        )
    b.collision_box((0, 0, 42), (102, 64, 84))
    return b


def _build_outdoor_sink():
    b = PropMeshBuilder("OutdoorSink")
    for x in (-25, 25):
        for y in (-19, 19):
            b.box((x, y, 41), (4, 4, 82), "M_P2_OldMetal")
    # A real recessed basin: four thick rim sections, inner walls, a visibly
    # lower floor and drain.  This avoids the previous black plate on legs.
    b.box((0, 0, 71), (48, 38, 3), "M_P2_Ceramic", steps=1)
    for y in (-22.5, 22.5):
        b.box((0, y, 80), (60, 5, 18), "M_P2_Ceramic", steps=1)
        b.box((0, y * 0.82, 75), (48, 2.5, 9), "M_P2_Enamel")
    for x in (-27.5, 27.5):
        b.box((x, 0, 80), (5, 40, 18), "M_P2_Ceramic", steps=1)
        b.box((x * 0.84, 0, 75), (2.5, 34, 9), "M_P2_Enamel")
    b.cylinder((0, 0, 73), 4.2, 1.4, "M_P2_OldMetal", radial_steps=18)
    b.cylinder((0, 0, 42), 2.4, 58, "M_P2_OldMetal", radial_steps=12)
    b.torus(
        (0, 6, 16),
        7.0,
        2.2,
        "M_P2_OldMetal",
        rotation=(90, 0, 0),
        major_steps=20,
        revolve_degrees=180.0,
    )
    b.cylinder((17, 17, 98), 2.2, 25, "M_P2_Brass", radial_steps=14)
    b.cylinder((17, 8, 109), 2.2, 18, "M_P2_Brass", rotation=(0, 0, 90), radial_steps=14)
    b.cylinder((17, -1, 105), 2.3, 9, "M_P2_Brass", radial_steps=14)
    b.cylinder((17, 17, 111), 1.8, 12, "M_P2_Brass", rotation=(90, 0, 0), radial_steps=12)
    b.sphere((17, 17, 111), 3.2, "M_P2_Brass", scale=(1, 1, 0.55))
    for y in (-19, 19):
        b.cylinder_between(
            (-25, y, 30),
            (25, -y, 30),
            1.2,
            "M_P2_OldMetal",
            radial_steps=10,
        )
    b.collision_box((0, 0, 78), (62, 52, 14))
    b.collision_box((-25, 0, 39), (6, 48, 78))
    b.collision_box((25, 0, 39), (6, 48, 78))
    return b


def _build_trash_bin():
    b = PropMeshBuilder("TrashBin")
    # A familiar 120-litre wheelie-bin silhouette is easier to read at player
    # height than the former round boiler shape.  Rounded body and shoulder
    # shells overlap inside their volumes, preserving the original footprint.
    b.box(
        (0, 0, 44),
        (50, 46, 78),
        "M_P2_PaintedMetal",
        steps=1,
        bevel=3.0,
        bevel_subdivisions=3,
    )
    b.box(
        (0, 0, 77),
        (52, 48, 12),
        "M_P2_PaintedMetal",
        steps=1,
        bevel=2.4,
        bevel_subdivisions=3,
    )

    # Moulded front ribs, lower kick rail and side protection strips.
    for x in (-18, -9, 0, 9, 18):
        b.box(
            (x, -23.6, 50),
            (2.0, 1.2, 46),
            "M_P2_OldMetal",
            bevel=0.4,
            bevel_subdivisions=2,
        )
    b.box(
        (0, -23.8, 12),
        (42, 1.4, 5),
        "M_P2_OldMetal",
        bevel=0.65,
        bevel_subdivisions=2,
    )
    for x in (-26.2, 26.2):
        b.box(
            (x, 0, 49),
            (1.4, 38, 52),
            "M_P2_OldMetal",
            bevel=0.45,
            bevel_subdivisions=2,
        )

    # Rolled rim, independently rounded lid and a shallow pressed top panel.
    b.box(
        (0, -1, 82),
        (54, 50, 5),
        "M_P2_OldMetal",
        steps=1,
        bevel=1.8,
        bevel_subdivisions=3,
    )
    b.box(
        (0, -1, 87),
        (54, 50, 8),
        "M_P2_OldMetal",
        steps=1,
        bevel=2.4,
        bevel_subdivisions=3,
    )
    b.box(
        (0, -3, 91.0),
        (44, 38, 2.0),
        "M_P2_PaintedMetal",
        bevel=0.9,
        bevel_subdivisions=2,
    )

    # Two working hinge barrels and leaves connect the lid to the rear collar.
    for x in (-16, 16):
        b.box(
            (x, 23.8, 83),
            (10, 1.8, 7),
            "M_P2_OldMetal",
            bevel=0.5,
            bevel_subdivisions=2,
        )
        b.cylinder(
            (x, 24.8, 85),
            1.6,
            9,
            "M_P2_OldMetal",
            rotation=(90, 0, 0),
            radial_steps=14,
        )

    # Connected rear push handle: two sockets, two uprights and one grip.
    for x in (-18, 18):
        b.box(
            (x, 22.8, 68),
            (6, 3, 8),
            "M_P2_OldMetal",
            bevel=0.7,
            bevel_subdivisions=2,
        )
        b.cylinder_between(
            (x, 23.5, 68),
            (x, 25.5, 76),
            1.8,
            "M_P2_OldMetal",
            radial_steps=14,
        )
    b.cylinder_between(
        (-18, 25.5, 76),
        (18, 25.5, 76),
        2.0,
        "M_P2_OldMetal",
        radial_steps=16,
    )

    # Rear axle, forked wheels, front pedal and its short metal linkage.
    b.cylinder_between(
        (-22, 20.5, 7),
        (22, 20.5, 7),
        1.7,
        "M_P2_OldMetal",
        radial_steps=14,
    )
    for x in (-22, 22):
        b.box(
            (x, 20.5, 8),
            (5, 5, 8),
            "M_P2_OldMetal",
            bevel=0.75,
            bevel_subdivisions=2,
        )
        b.cylinder(
            (x, 20.5, 5),
            5.0,
            6,
            "M_P2_Rubber",
            rotation=(90, 0, 0),
            radial_steps=16,
        )
    b.box(
        (0, -25.0, 7),
        (5, 6, 7),
        "M_P2_OldMetal",
        bevel=0.65,
        bevel_subdivisions=2,
    )
    b.box(
        (0, -29, 5),
        (18, 10, 3),
        "M_P2_Rubber",
        rotation=(7, 0, 0),
        bevel=1.0,
        bevel_subdivisions=2,
    )
    b.box(
        (0, -26.5, 86),
        (20, 4, 4),
        "M_P2_Rubber",
        bevel=1.2,
        bevel_subdivisions=2,
    )
    b.collision_box((0, 0, 47), (56, 56, 94))
    return b


def _build_plant_pot():
    b = PropMeshBuilder("PlantPot")
    b.cone((0, 0, 16), 14, 18, 30, "M_P2_Ceramic", radial_steps=24, height_steps=4)
    b.torus((0, 0, 31), 17, 2, "M_P2_Ceramic", major_steps=28)
    # Keep the thin thrown-pot bands in the ceramic slot.  UE's torus
    # primitive can discard their requested material IDs while still leaving
    # empty Static Mesh elements behind, which produces Map Check warnings.
    b.torus((0, 0, 5), 13.2, 1.0, "M_P2_Ceramic", major_steps=24)
    b.torus((0, 0, 18), 15.0, 0.55, "M_P2_Ceramic", major_steps=24)
    b.cylinder((0, 0, 31.2), 14.5, 1.5, "M_P2_Soil", radial_steps=24)
    for x, y, height, pitch, roll in (
        (-4, 0, 32, -8, 4),
        (4, 1, 38, 7, -5),
        (0, -3, 43, 0, 3),
    ):
        b.cylinder((x, y, 31 + height / 2), 1.0, height, "M_P2_Leaf", rotation=(pitch, 0, roll), radial_steps=10)
    leaf_specs = (
        (-12, 0, 53, -30, 15, (1.55, 0.22, 0.50), (-4, 0, 48)),
        (12, 0, 56, 30, -15, (1.70, 0.21, 0.53), (4, 1, 50)),
        (-8, 3, 67, -20, -10, (1.65, 0.20, 0.48), (-3, 0, 60)),
        (9, -2, 72, 22, 12, (1.85, 0.22, 0.55), (4, 0, 64)),
        (0, 2, 82, 0, 6, (1.45, 0.24, 0.58), (0, -1, 71)),
        (-15, -1, 72, -35, 5, (1.95, 0.19, 0.48), (-5, 0, 64)),
        (15, 2, 64, 35, -5, (1.60, 0.23, 0.52), (5, 1, 58)),
    )
    for x, y, z, pitch, roll, scale, stem_start in leaf_specs:
        b.cylinder_between(
            stem_start,
            (x, y, z),
            0.65,
            "M_P2_Leaf",
            radial_steps=8,
        )
        b.sphere(
            (x, y, z),
            7.5,
            "M_P2_Leaf",
            rotation=(pitch, 0, roll),
            scale=scale,
            phi_steps=8,
            theta_steps=14,
        )
    return b


def _build_cardboard_box():
    b = PropMeshBuilder("CardboardBox")
    # Four independent corrugated walls and a recessed bottom create a genuine
    # hollow carton.  Rounded paper edges are subtle but visible at arm's
    # length, and the outer bounds remain the original 46 x 40 footprint.
    for y in (-19.2, 19.2):
        b.box(
            (0, y, 22),
            (46, 1.6, 44),
            "M_P2_Cardboard",
            steps=1,
            bevel=0.55,
            bevel_subdivisions=2,
        )
    for x in (-22.2, 22.2):
        b.box(
            (x, 0, 22),
            (1.6, 36.8, 44),
            "M_P2_Cardboard",
            steps=1,
            bevel=0.55,
            bevel_subdivisions=2,
        )
    b.box(
        (0, 0, 1.2),
        (43, 37, 2.4),
        "M_P2_Cardboard",
        bevel=0.5,
        bevel_subdivisions=2,
    )

    # Correct hinge axes and connected centres give the four top flaps actual
    # folded-cardboard construction instead of floating rotated plates.
    flap_specs = (
        ((0, -11.0, 45.2), (44, 18, 2.0), (0, 0, -6)),
        ((0, 11.0, 45.5), (44, 18, 2.0), (0, 0, 7)),
        ((-13.0, 0, 46.0), (18, 36, 2.0), (-8, 0, 0)),
        ((13.0, 0, 45.7), (18, 36, 2.0), (6, 0, 0)),
    )
    for location, size, rotation in flap_specs:
        b.box(
            location,
            size,
            "M_P2_Cardboard",
            rotation=rotation,
            bevel=0.45,
            bevel_subdivisions=2,
        )

    # Folded corner seams catch a thin highlight and stop the walls reading as
    # four unrelated planes.
    for x in (-22.4, 22.4):
        for y in (-19.4, 19.4):
            b.cylinder_between(
                (x, y, 1.5),
                (x, y, 42.5),
                0.65,
                "M_P2_Cardboard",
                radial_steps=8,
            )

    # Packing tape wraps continuously up the front and across both near-closed
    # flaps.  A smaller offset strip reads as a repaired tear, not decoration.
    b.box(
        (0, -20.3, 22),
        (7, 0.8, 44),
        "M_P2_Cloth",
        bevel=0.25,
        bevel_subdivisions=2,
    )
    b.box(
        (0, -11.0, 46.35),
        (7, 17, 0.8),
        "M_P2_Cloth",
        rotation=(0, 0, -6),
        bevel=0.2,
        bevel_subdivisions=2,
    )
    b.box(
        (0, 11.0, 46.65),
        (7, 17, 0.8),
        "M_P2_Cloth",
        rotation=(0, 0, 7),
        bevel=0.2,
        bevel_subdivisions=2,
    )
    b.box(
        (15, -20.25, 31),
        (10, 0.7, 6),
        "M_P2_Cloth",
        rotation=(0, 0, -4),
        bevel=0.25,
        bevel_subdivisions=2,
    )

    # Bottom and upper score lines are shallow geometry, deliberately offset
    # from the wall surface to avoid coplanar flicker.
    for z in (7, 34):
        b.box(
            (0, 20.25, z),
            (43, 0.7, 0.9),
            "M_P2_Cardboard",
            bevel=0.2,
            bevel_subdivisions=2,
        )
    b.collision_box((0, 0, 23), (46, 40, 46))
    return b


def _build_alley_bench():
    b = PropMeshBuilder("AlleyBench")
    for y in (-12, 0, 12):
        b.box((0, y, 44), (120, 9, 5), "M_P2_Wood", steps=1)
    for x in (-47, 47):
        b.box((x, 0, 22), (8, 30, 44), "M_P2_OldMetal")
        b.box((x, 0, 18), (32, 3, 3), "M_P2_OldMetal", rotation=(0, 0, 35 if x < 0 else -35))
    b.box((0, 0, 22), (102, 4, 4), "M_P2_OldMetal")
    for x in (-47, 47):
        for y in (-12, 12):
            b.cylinder((x, y, 47), 1.2, 1.5, "M_P2_Brass", radial_steps=10)
    b.collision_box((0, 0, 45), (120, 34, 8))
    b.collision_box((-47, 0, 22), (10, 30, 44))
    b.collision_box((47, 0, 22), (10, 30, 44))
    return b


def _build_wash_basin():
    b = PropMeshBuilder("WashBasin")
    b.cone((0, 0, 8), 24, 20, 14, "M_P2_Enamel", radial_steps=28, height_steps=3)
    b.torus((0, 0, 15), 23.5, 1.6, "M_P2_OldMetal", major_steps=28)
    b.cylinder((0, 0, 14.7), 19, 0.8, "M_P2_DarkGlass", radial_steps=28)
    b.cylinder((0, 0, 15.3), 3, 1, "M_P2_OldMetal", radial_steps=14)
    for x in (-23, 23):
        b.torus((x, 0, 10), 5.5, 1.1, "M_P2_OldMetal", rotation=(90, 0, 0), major_steps=18)
    return b


def _build_ac_unit():
    b = PropMeshBuilder("ACUnit")
    b.box((0, 0, 38), (88, 40, 68), "M_P2_Enamel", steps=1)
    b.box((0, -21, 38), (82, 3, 60), "M_P2_Plastic")
    b.torus((0, -23, 39), 25, 2.5, "M_P2_OldMetal", rotation=(0, 0, 90), major_steps=32)
    b.torus((0, -24, 39), 18, 1.0, "M_P2_OldMetal", rotation=(0, 0, 90), major_steps=28)
    b.cylinder((0, -24, 39), 5, 4, "M_P2_OldMetal", rotation=(0, 0, 90), radial_steps=18)
    for angle in (0, 45, 90, 135):
        b.box(
            (0, -24.5, 39),
            (35, 2, 5),
            "M_P2_PaintedMetal",
            rotation=(float(angle), 0, 0),
        )
    for z in (15, 22, 56, 63):
        b.box((0, -23, z), (70, 1.2, 1.2), "M_P2_OldMetal")
    for x in (-36, 36):
        b.box((x, -23, 39), (1.2, 1.2, 50), "M_P2_OldMetal")
    b.box((-31, -23.5, 9), (16, 2, 7), "M_P2_OldMetal")
    for x in (-35, -28):
        for z in (7, 10):
            b.box((x, -25, z), (5, 1, 0.8), "M_P2_Rubber")
    b.cylinder((36, 18, 11), 2.2, 24, "M_P2_Brass", rotation=(0, 0, 90), radial_steps=12)
    b.cylinder((46, 18, 6), 2.2, 12, "M_P2_Brass", radial_steps=12)
    for x in (-34, 34):
        b.box((x, 0, 2), (8, 30, 4), "M_P2_Rubber")
    b.collision_box((0, 0, 38), (88, 40, 76))
    return b


def _build_meter_box():
    b = PropMeshBuilder("MeterBox")
    b.box((0, 0, 22), (32, 15, 44), "M_P2_PaintedMetal", steps=1)
    b.box((0, -8.2, 22), (29, 2, 41), "M_P2_OldMetal")
    b.cylinder((0, -9.5, 28), 9, 2, "M_P2_DarkGlass", rotation=(0, 0, 90), radial_steps=28)
    b.torus((0, -10.5, 28), 9.2, 1.2, "M_P2_Brass", rotation=(0, 0, 90), major_steps=28)
    b.cylinder((0, -10.8, 28), 1.2, 6, "M_P2_Brass", rotation=(28, 0, 0), radial_steps=10)
    for x in (-8, -3, 3, 8):
        b.box((x, -10, 12), (1, 1, 8), "M_P2_Enamel")
    for z in (10, 34):
        b.box((15.5, -8.2, z), (1.5, 2, 7), "M_P2_Brass")
    b.box((-11, -10, 4), (4, 2, 3), "M_P2_Rubber")
    b.cylinder((-8, 0, 7), 1.8, 14, "M_P2_Rubber", radial_steps=10)
    b.cylinder((8, 0, 7), 1.8, 14, "M_P2_Rubber", radial_steps=10)
    return b


def _build_bicycle():
    """Create a readable old utility bicycle as one reusable mesh asset."""
    b = PropMeshBuilder("Bicycle")
    rubber = "M_P2_Rubber"
    metal = "M_P2_OldMetal"
    paint = "M_P2_PaintedMetal"
    plastic = "M_P2_Plastic"

    # A 71.4 cm adult wheel.  The tyre, rim and spokes deliberately overlap
    # radially; the former dimensions left a visible 1.15 cm ring of air.
    wheel_z = 35.7
    wheel_xs = (-56.0, 56.0)
    for wheel_x in wheel_xs:
        # The torus, rim, hub and twelve true spokes give a circular silhouette
        # at both first-person and street-view distances.
        b.torus(
            (wheel_x, 0.0, wheel_z),
            33.0,
            2.7,
            rubber,
            rotation=(0.0, 0.0, 90.0),
            major_steps=36,
            minor_steps=10,
        )
        b.torus(
            (wheel_x, 0.0, wheel_z),
            30.0,
            0.85,
            metal,
            rotation=(0.0, 0.0, 90.0),
            major_steps=32,
            minor_steps=7,
        )
        b.cylinder(
            (wheel_x, 0.0, wheel_z),
            2.4,
            10.0,
            metal,
            rotation=(0.0, 0.0, 90.0),
            radial_steps=16,
        )
        for spoke_index in range(12):
            angle = math.radians(float(spoke_index) * 30.0)
            spoke_end = (
                wheel_x + math.cos(angle) * 29.5,
                0.0,
                wheel_z + math.sin(angle) * 29.5,
            )
            b.cylinder_between(
                (wheel_x, 0.0, wheel_z),
                spoke_end,
                0.42,
                metal,
                radial_steps=7,
            )

    rear_hub = (-56.0, 0.0, wheel_z)
    crank = (-6.0, 0.0, 37.0)
    seat_joint = (-17.0, 0.0, 77.0)
    head_joint = (38.0, 0.0, 73.0)
    front_hub = (56.0, 0.0, wheel_z)
    for start, end, radius in (
        (rear_hub, crank, 1.9),
        (rear_hub, seat_joint, 1.9),
        (crank, seat_joint, 2.2),
        (seat_joint, head_joint, 2.2),
        (head_joint, crank, 2.5),
    ):
        b.cylinder_between(start, end, radius, paint, radial_steps=14)
    # Manufactured frame lugs hide cap seams and make the tube network read as
    # one welded frame from every player-facing angle.
    for joint, radius in (
        (crank, 3.0),
        (seat_joint, 2.9),
        (head_joint, 3.1),
    ):
        b.sphere(
            joint,
            radius,
            paint,
            scale=(1.0, 1.08, 1.0),
            phi_steps=9,
            theta_steps=16,
        )

    # Twin fork and rear stays preserve the real frame width instead of reading
    # as a single two-dimensional line.
    for y in (-2.5, 2.5):
        b.cylinder_between(
            (head_joint[0], y, head_joint[2]),
            (front_hub[0], y, front_hub[2]),
            1.35,
            metal,
            radial_steps=12,
        )
        b.cylinder_between(
            (rear_hub[0], y, rear_hub[2]),
            (crank[0], y, crank[2]),
            1.15,
            metal,
            radial_steps=10,
        )

    # Crank, chain, pedals and guards.
    b.torus(
        crank,
        9.0,
        1.0,
        metal,
        rotation=(0.0, 0.0, 90.0),
        major_steps=24,
        minor_steps=7,
    )
    b.torus(
        rear_hub,
        5.0,
        0.8,
        metal,
        rotation=(0.0, 0.0, 90.0),
        major_steps=20,
        minor_steps=6,
    )
    for chain_start, chain_end in (
        ((-54.0, -1.0, 40.5), (-7.0, -1.0, 46.0)),
        ((-54.0, -1.0, 30.5), (-7.0, -1.0, 28.0)),
    ):
        b.cylinder_between(
            chain_start,
            chain_end,
            0.55,
            metal,
            radial_steps=7,
        )
    b.cylinder(
        crank,
        1.45,
        22.0,
        metal,
        rotation=(0.0, 0.0, 90.0),
        radial_steps=14,
    )
    for y in (-13.0, 13.0):
        b.box(
            (-6.0, y, 37.0),
            (10.0, 5.0, 2.2),
            rubber,
            rotation=(0.0, 8.0 if y < 0.0 else -8.0, 0.0),
            bevel=0.65,
            bevel_subdivisions=1,
        )

    # Seat, post, stem and curved-looking handle assembly.
    b.cylinder_between(
        seat_joint,
        (-18.0, 0.0, 90.0),
        1.5,
        metal,
        radial_steps=12,
    )
    b.box(
        (-20.0, 0.0, 91.0),
        (25.0, 11.0, 5.0),
        rubber,
        rotation=(0.0, -3.0, 0.0),
        bevel=1.7,
        bevel_subdivisions=2,
    )
    b.cylinder_between(
        head_joint,
        (42.0, 0.0, 95.0),
        1.55,
        metal,
        radial_steps=12,
    )
    b.cylinder_between(
        (42.0, -21.0, 94.0),
        (42.0, 21.0, 94.0),
        1.45,
        metal,
        radial_steps=14,
    )
    for y in (-22.0, 22.0):
        b.cylinder(
            (42.0, y, 94.0),
            2.25,
            9.0,
            rubber,
            rotation=(0.0, 0.0, 90.0),
            radial_steps=14,
        )
    b.sphere(
        (45.0, -10.0, 96.5),
        2.8,
        metal,
        scale=(1.0, 0.8, 0.65),
        phi_steps=8,
        theta_steps=14,
    )

    # Rear carrier and front wire basket give the old-city utility-bike story.
    for y in (-8.5, 8.5):
        b.cylinder_between(
            (-53.0, y, 69.0),
            (-13.0, y, 69.0),
            1.0,
            metal,
            radial_steps=9,
        )
        b.cylinder_between(
            (-49.0, y, 68.5),
            rear_hub,
            0.9,
            metal,
            radial_steps=8,
        )
        b.cylinder_between(
            (-13.0, y, 69.0),
            (-17.0, y * 0.25, 77.0),
            1.0,
            metal,
            radial_steps=9,
        )
    for x in (-47.0, -35.0, -23.0):
        b.cylinder_between(
            (x, -9.0, 69.0),
            (x, 9.0, 69.0),
            0.75,
            metal,
            radial_steps=8,
        )

    basket_center_x = 61.0
    for z in (73.0, 97.0):
        for y in (-17.0, 17.0):
            b.cylinder_between(
                (basket_center_x - 13.0, y, z),
                (basket_center_x + 13.0, y, z),
                0.75,
                metal,
                radial_steps=8,
            )
    for x in (basket_center_x - 13.0, basket_center_x + 13.0):
        for y in (-17.0, 17.0):
            b.cylinder_between(
                (x, y, 73.0),
                (x, y, 97.0),
                0.75,
                metal,
                radial_steps=8,
            )
    for y in (-17.0, -8.5, 0.0, 8.5, 17.0):
        b.cylinder_between(
            (basket_center_x - 13.0, y, 73.0),
            (basket_center_x + 13.0, y, 73.0),
            0.55,
            metal,
            radial_steps=7,
        )
    for x in (50.0, 57.0, 64.0, 71.0):
        b.cylinder_between(
            (x, -17.0, 75.0),
            (x, 17.0, 75.0),
            0.5,
            metal,
            radial_steps=7,
        )
    b.box(
        (basket_center_x, 0.0, 74.0),
        (24.0, 31.0, 2.0),
        plastic,
        bevel=0.35,
    )
    b.cylinder_between(
        (basket_center_x - 10.0, 0.0, 73.0),
        (head_joint[0], 0.0, head_joint[2]),
        0.9,
        metal,
        radial_steps=8,
    )
    for y in (-15.0, 15.0):
        b.cylinder_between(
            (basket_center_x - 13.0, y, 95.0),
            (42.0, y, 94.0),
            0.85,
            metal,
            radial_steps=8,
        )

    # A kickstand prevents the placed prop reading as magically balanced.
    b.cylinder_between(
        (-7.0, 2.5, 35.5),
        (-21.0, 14.0, 1.0),
        0.9,
        metal,
        radial_steps=9,
    )
    b.box(
        (-22.0, 15.0, 1.5),
        (7.0, 4.0, 3.0),
        rubber,
        bevel=0.4,
    )
    return b


def _build_wall_utility_cluster():
    """Create a reusable wall-mounted drain, meter and cable assembly."""
    b = PropMeshBuilder("WallUtilityCluster")
    metal = "M_P2_OldMetal"
    paint = "M_P2_PaintedMetal"
    glass = "M_P2_DarkGlass"
    rubber = "M_P2_Rubber"
    brass = "M_P2_Brass"

    # Main downpipe, wall return elbow and six independent retaining straps.
    b.cylinder((-48.0, -8.0, 142.0), 4.8, 276.0, metal, radial_steps=18)
    b.cylinder_between(
        (-48.0, -8.0, 280.0),
        (-48.0, 2.0, 287.0),
        4.8,
        metal,
        radial_steps=18,
    )
    b.cylinder_between(
        (-48.0, -8.0, 4.0),
        (-64.0, -18.0, 4.0),
        4.8,
        metal,
        radial_steps=18,
    )
    for z in (28.0, 76.0, 124.0, 172.0, 220.0, 268.0):
        b.box(
            (-48.0, -2.5, z),
            (14.0, 2.2, 5.0),
            paint,
            bevel=0.45,
        )

    # Deep meter cabinet with raised rim, recessed window, hinges and latch.
    b.box((17.0, -7.0, 171.0), (55.0, 16.0, 72.0), paint, bevel=2.1)
    b.box((17.0, -16.0, 171.0), (46.0, 2.0, 61.0), metal, bevel=0.8)
    b.box((17.0, -17.4, 181.0), (31.0, 1.0, 27.0), glass, bevel=0.4)
    for z in (148.0, 194.0):
        b.cylinder(
            (-12.0, -16.5, z),
            1.7,
            8.0,
            metal,
            radial_steps=14,
        )
    b.box((43.0, -18.0, 164.0), (4.0, 2.0, 12.0), brass, bevel=0.6)
    b.cylinder((43.0, -19.2, 164.0), 2.1, 1.6, brass, radial_steps=16)

    # Secondary junction box and protected conduits.
    b.box((28.0, -5.0, 83.0), (36.0, 13.0, 40.0), paint, bevel=1.8)
    b.box((28.0, -12.0, 83.0), (29.0, 1.2, 32.0), metal, bevel=0.55)
    for x in (18.0, 38.0):
        b.cylinder((x, -6.0, 122.0), 2.1, 44.0, metal, radial_steps=12)
        b.cylinder((x, -6.0, 49.0), 2.1, 42.0, metal, radial_steps=12)
    b.cylinder((17.0, -6.0, 241.0), 2.2, 70.0, metal, radial_steps=12)
    b.cylinder((32.0, -6.0, 239.0), 1.6, 66.0, rubber, radial_steps=10)

    # Coiled service cable, connection gland and small warning plate.
    b.torus(
        (53.0, -15.0, 112.0),
        12.0,
        1.6,
        rubber,
        rotation=(0.0, 0.0, 90.0),
        major_steps=28,
        minor_steps=8,
        scale=(1.0, 1.0, 1.25),
    )
    b.cylinder((39.0, -14.0, 113.0), 3.0, 7.0, brass, radial_steps=16)
    b.box((18.0, -18.2, 206.0), (31.0, 1.0, 10.0), brass, bevel=0.45)
    for x in (8.0, 18.0, 28.0):
        b.box((x, -18.9, 206.0), (2.0, 0.8, 7.0), metal, bevel=0.2)
    return b


def _build_street_lamp():
    """Create one manufactured old-city lamp instead of three Cube actors."""
    b = PropMeshBuilder("StreetLamp")
    metal = "M_P2_OldMetal"
    paint = "M_P2_PaintedMetal"
    glass = "M_P2_DarkGlass"
    brass = "M_P2_Brass"

    # Layered footing, tapered shaft, access hatch and clamp collars.
    b.cylinder((0.0, 0.0, 3.0), 14.0, 6.0, metal, radial_steps=24)
    b.cylinder((0.0, 0.0, 11.0), 9.0, 16.0, paint, radial_steps=22)
    b.cone(
        (0.0, 0.0, 159.0),
        6.0,
        4.4,
        284.0,
        metal,
        radial_steps=24,
        height_steps=3,
    )
    for z in (28.0, 72.0, 254.0):
        b.torus(
            (0.0, 0.0, z),
            6.2 if z < 100.0 else 4.9,
            0.8,
            paint,
            major_steps=24,
            minor_steps=7,
        )
    b.box(
        (0.0, -5.1, 116.0),
        (10.0, 2.0, 24.0),
        paint,
        bevel=0.7,
    )
    for z in (108.0, 124.0):
        b.cylinder(
            (0.0, -6.4, z),
            1.0,
            1.2,
            brass,
            rotation=(90.0, 0.0, 0.0),
            radial_steps=12,
        )

    # Segmented swan-neck arm with a diagonal brace and cable gland.
    b.cylinder_between(
        (0.0, 0.0, 297.0),
        (0.0, -29.0, 320.0),
        4.4,
        metal,
        radial_steps=18,
    )
    b.cylinder_between(
        (0.0, -22.0, 320.0),
        (0.0, -104.0, 320.0),
        4.0,
        metal,
        radial_steps=18,
    )
    b.cylinder_between(
        (0.0, -2.5, 288.0),
        (0.0, -62.0, 320.0),
        1.9,
        metal,
        radial_steps=12,
    )
    b.sphere(
        (0.0, -25.0, 320.0),
        5.2,
        metal,
        scale=(1.0, 1.1, 1.0),
        phi_steps=10,
        theta_steps=18,
    )

    # Bevelled luminaire body, rain hood, recessed lens, hinge and fasteners.
    b.box(
        (0.0, -108.0, 315.0),
        (54.0, 36.0, 13.0),
        metal,
        rotation=(0.0, 0.0, -3.0),
        bevel=2.4,
        bevel_subdivisions=2,
    )
    b.box(
        (0.0, -108.0, 322.0),
        (61.0, 41.0, 6.0),
        paint,
        rotation=(0.0, 0.0, -3.0),
        bevel=1.1,
    )
    b.box(
        (0.0, -108.0, 308.7),
        (43.0, 25.0, 2.8),
        glass,
        rotation=(0.0, 0.0, -3.0),
        bevel=0.8,
    )
    b.box(
        (0.0, -126.0, 315.0),
        (27.0, 2.2, 4.0),
        brass,
        bevel=0.55,
    )
    for x in (-21.0, 21.0):
        b.cylinder(
            (x, -108.0, 306.2),
            1.3,
            1.4,
            brass,
            radial_steps=12,
        )

    # Collision follows the pedestrian-height shaft only; the arm remains
    # non-blocking above the player.
    b.collision_box((0.0, 0.0, 150.0), (24.0, 24.0, 300.0))
    return b


def _build_storm_drain():
    """Create a recessed curb grate with frame, bars, lip and fasteners."""
    b = PropMeshBuilder("StormDrain")
    metal = "M_P2_OldMetal"
    rubber = "M_P2_Rubber"
    brass = "M_P2_Brass"

    b.box((0.0, 0.0, 1.7), (98.0, 30.0, 3.4), metal, bevel=1.8)
    b.box((0.0, 0.0, 3.0), (86.0, 19.0, 1.8), rubber, bevel=0.55)
    for x in (-36.0, -24.0, -12.0, 0.0, 12.0, 24.0, 36.0):
        b.box(
            (x, 0.0, 4.2),
            (4.0, 21.0, 2.2),
            metal,
            bevel=0.55,
        )
    b.box((0.0, 13.0, 4.2), (102.0, 5.0, 5.2), metal, bevel=0.9)
    for x in (-43.0, 43.0):
        for y in (-10.5, 10.5):
            b.cylinder(
                (x, y, 4.1),
                1.4,
                1.8,
                brass,
                radial_steps=12,
            )
    return b


def _build_static_shutter():
    """Create a continuous closed shop shutter as one wall-mounted mesh.

    The previous scene version used twenty-two isolated 2 cm Cube actors.  A
    solid backing sheet and overlapping 10.6 cm laths now guarantee that the
    grooves read as rolled metal rather than open ladder gaps.
    """
    b = PropMeshBuilder("StaticShutter")
    paint = "M_P2_PaintedMetal"
    metal = "M_P2_OldMetal"
    brass = "M_P2_Brass"

    # Local front is -Y.  The tracks define a 356 x 232 cm manufactured frame;
    # the visual sheet begins 8 cm above the pivot so its world placement can
    # preserve the old storefront sill height exactly.
    b.box((0.0, -2.0, 118.0), (330.0, 4.0, 220.0), paint, bevel=1.2)
    for slat_index in range(22):
        b.box(
            (
                0.0,
                -5.3 - float(slat_index % 2) * 0.35,
                13.0 + float(slat_index) * 10.0,
            ),
            (330.0, 5.4, 10.6),
            paint,
            bevel=1.15,
            bevel_subdivisions=2,
        )
    for side in (-1.0, 1.0):
        b.box(
            (side * 171.0, -3.5, 116.0),
            (14.0, 12.0, 232.0),
            metal,
            bevel=1.7,
            bevel_subdivisions=2,
        )
        b.box(
            (side * 176.0, -9.0, 116.0),
            (4.0, 5.0, 232.0),
            metal,
            bevel=0.7,
        )
        for z in (29.0, 111.0, 193.0):
            b.cylinder(
                (side * 176.0, -12.0, z),
                1.8,
                1.8,
                brass,
                rotation=(0.0, 0.0, 90.0),
                radial_steps=12,
            )
    b.box(
        (0.0, -2.5, 228.0),
        (356.0, 18.0, 16.0),
        metal,
        bevel=2.5,
        bevel_subdivisions=2,
    )
    b.box((0.0, -7.0, 16.0), (334.0, 10.0, 18.0), metal, bevel=1.8)
    b.box((0.0, -13.0, 22.0), (38.0, 3.0, 22.0), brass, bevel=1.0)
    b.box((-92.0, -12.4, 19.0), (88.0, 1.2, 20.0), metal, bevel=0.55)
    b.box((113.0, -12.4, 27.0), (52.0, 1.2, 28.0), metal, bevel=0.55)
    return b


def _build_sign_assembly():
    """Create one framed old shop sign with board, fasteners and wear layers."""
    b = PropMeshBuilder("SignAssembly")
    board = "M_P2_Enamel"
    metal = "M_P2_OldMetal"
    wear = "M_P2_PaintedMetal"
    brass = "M_P2_Brass"

    # Standard visible board is 400 x 70 cm and scales only along X in scene.
    b.box((0.0, -3.0, 42.0), (400.0, 6.0, 70.0), board, bevel=2.2)
    for x in (-202.5, 202.5):
        b.box((x, -6.5, 42.0), (8.0, 9.0, 84.0), metal, bevel=1.3)
    for z in (4.0, 80.0):
        b.box((0.0, -6.5, z), (416.0, 9.0, 8.0), metal, bevel=1.3)

    # Narrow edge chips replace the former large rectangular patches.  Each
    # strip overlaps the board by 0.1 cm, reads as worn paint at grazing angles
    # and leaves the centre clear for the separate readable glyph asset.
    b.box((-142.0, -6.5, 69.0), (78.0, 1.2, 5.0), wear, bevel=0.35)
    b.box((154.0, -6.5, 16.0), (52.0, 1.2, 4.0), wear, bevel=0.3)
    b.box((-188.0, -6.5, 43.0), (4.0, 1.2, 20.0), metal, bevel=0.3)
    for x in (-190.0, 190.0):
        for z in (15.0, 69.0):
            b.cylinder(
                (x, -10.2, z),
                2.0,
                2.0,
                brass,
                rotation=(0.0, 0.0, 90.0),
                radial_steps=14,
            )
    return b


def _build_awning_assembly():
    """Create a complete old shop awning with braces and service light."""
    b = PropMeshBuilder("AwningAssembly")
    cloth = "M_P2_Cloth"
    metal = "M_P2_OldMetal"
    enamel = "M_P2_Enamel"
    brass = "M_P2_Brass"

    # Pivot sits on the facade.  Local -Y points toward the street; a five
    # degree fall keeps rainwater moving away from the wall.
    b.box(
        (0.0, -38.0, 32.0),
        (400.0, 76.0, 8.0),
        cloth,
        rotation=(0.0, 0.0, 5.0),
        bevel=1.6,
        bevel_subdivisions=2,
    )
    b.box((0.0, -75.0, 20.0), (400.0, 6.0, 26.0), cloth, bevel=1.1)
    b.cylinder_between((-198.0, -73.0, 31.0), (198.0, -73.0, 31.0), 4.1, metal, radial_steps=16)
    b.cylinder_between((-198.0, -2.0, 37.0), (198.0, -2.0, 37.0), 4.1, metal, radial_steps=16)
    for x in (-182.0, 182.0):
        b.cylinder_between((x, -2.0, 39.0), (x, -70.0, 10.0), 4.0, metal, radial_steps=14)
        b.box((x, 0.0, 40.0), (18.0, 4.0, 24.0), metal, bevel=1.0)
        for z in (33.0, 47.0):
            b.cylinder(
                (x, -2.7, z),
                1.6,
                2.0,
                brass,
                rotation=(0.0, 0.0, 90.0),
                radial_steps=12,
            )
    b.box((0.0, -44.0, 17.0), (92.0, 8.0, 5.0), enamel, bevel=1.7)
    b.box((0.0, -44.0, 20.0), (104.0, 12.0, 3.0), metal, bevel=0.8)
    return b


def _build_school_gate_leaf():
    """Create one open school gate leaf with welded frame and hinge sleeves."""
    b = PropMeshBuilder("SchoolGateLeaf")
    paint = "M_P2_PaintedMetal"
    metal = "M_P2_OldMetal"
    brass = "M_P2_Brass"

    for x in (0.0, -75.0, -150.0, -225.0, -300.0, -375.0):
        b.box((x, 0.0, 117.5), (9.0, 9.0, 235.0), paint, bevel=1.15)
    for z in (27.5, 117.5, 207.5):
        b.box((-187.5, 0.0, z), (385.0, 11.0, 10.0), paint, bevel=1.25)
    b.cylinder_between((-356.0, 0.0, 25.0), (-22.0, 0.0, 208.0), 4.2, metal, radial_steps=14)

    # The actor is placed 7.5 cm above the level floor; lowering the authored
    # hinge centres by the same amount keeps them coaxial with the post straps.
    for z in (47.5, 172.5):
        b.cylinder(
            (0.0, 0.0, z),
            8.0,
            22.0,
            metal,
            rotation=(0.0, 0.0, 90.0),
            radial_steps=18,
        )
        b.box((-8.0, 0.0, z), (24.0, 18.0, 20.0), metal, bevel=1.4)
    for x in (-75.0, -225.0, -375.0):
        b.cylinder(
            (x, -6.0, 27.5),
            1.6,
            2.0,
            brass,
            rotation=(0.0, 0.0, 90.0),
            radial_steps=12,
        )
    b.box((-240.0, -6.0, 16.0), (118.0, 1.5, 24.0), metal, bevel=0.5)
    b.collision_box((-187.5, 0.0, 117.5), (385.0, 14.0, 235.0))
    return b


def _build_school_gate_post():
    """Create one masonry hinge post with embedded gate-side hardware."""
    b = PropMeshBuilder("SchoolGatePost")
    masonry = "M_P2_Ceramic"
    metal = "M_P2_OldMetal"
    damp = "M_P2_Soil"
    brass = "M_P2_Brass"

    b.box((0.0, 0.0, 180.0), (58.0, 58.0, 360.0), masonry, bevel=2.4)
    b.box((0.0, 0.0, 24.0), (70.0, 70.0, 48.0), masonry, bevel=2.7)
    b.box((0.0, 0.0, 369.0), (72.0, 72.0, 22.0), metal, bevel=3.0, bevel_subdivisions=2)
    b.box((30.5, 0.0, 54.0), (4.0, 50.0, 102.0), damp, bevel=0.8)

    # Default instance is the north post: both forged hinge straps terminate
    # at the gate leaf origin (-70,-30).  Mirroring Y places the south copy.
    for z in (55.0, 180.0):
        b.box((-30.0, -7.0, z), (6.0, 28.0, 24.0), metal, bevel=1.0)
        b.cylinder_between((-27.0, -7.0, z), (-70.0, -30.0, z), 4.4, metal, radial_steps=14)
        b.cylinder(
            (-70.0, -30.0, z),
            7.0,
            20.0,
            metal,
            rotation=(0.0, 0.0, 90.0),
            radial_steps=18,
        )
        b.cylinder(
            (-34.0, -7.0, z),
            1.8,
            2.4,
            brass,
            rotation=(90.0, 0.0, 0.0),
            radial_steps=12,
        )
    b.collision_box((0.0, 0.0, 180.0), (58.0, 58.0, 360.0))
    b.collision_box((0.0, 0.0, 24.0), (70.0, 70.0, 48.0))
    return b


def _build_alley_crossbar():
    """Create a complete wall-to-wall alley rod with real wall fixings."""
    b = PropMeshBuilder("AlleyCrossbar")
    metal = "M_P2_OldMetal"
    brass = "M_P2_Brass"

    # Local +X is the span axis.  The tube and both sleeves penetrate their
    # wall plates, so no connection relies on coincident end faces.
    b.cylinder_between(
        (-104.0, 0.0, 0.0),
        (104.0, 0.0, 0.0),
        3.0,
        metal,
        radial_steps=18,
    )
    for side in (-1.0, 1.0):
        plate_x = side * 102.0
        b.box(
            (plate_x, 0.0, 0.0),
            (6.0, 24.0, 28.0),
            metal,
            bevel=1.2,
            bevel_subdivisions=2,
        )
        b.cylinder_between(
            (side * 94.0, 0.0, 0.0),
            (side * 101.0, 0.0, 0.0),
            5.0,
            metal,
            radial_steps=16,
        )
        for y in (-7.0, 7.0):
            for z in (-8.0, 8.0):
                b.cylinder_between(
                    (side * 98.2, y, z),
                    (side * 102.2, y, z),
                    1.35,
                    brass,
                    radial_steps=12,
                )
    return b


def _horizontal_runs(row_bits):
    run_start = None
    for index, bit in enumerate(row_bits + "0"):
        if bit == "1" and run_start is None:
            run_start = index
        elif bit == "0" and run_start is not None:
            yield run_start, index
            run_start = None


def _build_sign_text(logical_name, phrase):
    """Create one readable, shallow-relief old-shop sign phrase."""
    if len(phrase) != 3:
        raise ValueError("{} must contain exactly three glyphs".format(logical_name))
    missing = [char for char in phrase if char not in _SIGN_GLYPH_BITMAPS]
    if missing:
        raise ValueError(
            "{} is missing embedded glyphs: {}".format(logical_name, missing)
        )

    b = PropMeshBuilder(logical_name)
    letter = "M_P2_PaintedMetal"
    cell_width = 3.9
    cell_height = 2.35
    glyph_width = 20.0 * cell_width
    glyph_gap = 9.0
    total_width = len(phrase) * glyph_width + (len(phrase) - 1) * glyph_gap
    first_left = -total_width * 0.5

    # SignAssembly faces local -Y.  From that side screen-left is local +X,
    # hence the reverse phrase order.  The 1.2 cm relief overlaps the board by
    # 0.2 cm and cannot cast a floating-patch gap shadow.
    for glyph_index, char in enumerate(reversed(phrase)):
        rows = _SIGN_GLYPH_BITMAPS[char]
        glyph_left = first_left + glyph_index * (glyph_width + glyph_gap)
        for row_index, row_bits in enumerate(rows):
            center_z = 42.0 + (9.5 - row_index) * cell_height
            for run_start, run_end in _horizontal_runs(row_bits):
                run_width = (run_end - run_start) * cell_width
                center_x = glyph_left + 0.5 * (run_start + run_end) * cell_width
                b.box(
                    (center_x, -6.4, center_z),
                    (run_width, 1.2, cell_height),
                    letter,
                    bevel=0.0,
                )
    return b


def _build_loaded_laundry_rack():
    """Create one complete, wall-mounted rack carrying three garments.

    Local -Y points away from the facade.  The wall face is Y=0 and the
    mounting plates extend four centimetres into the support, so every arm,
    sleeve and fastener has a physical overlap instead of an end-to-end seam.
    The lowest garment establishes Z=0 for predictable facade placement.
    """
    b = PropMeshBuilder("LoadedLaundryRack")
    metal = "M_P2_OldMetal"
    brass = "M_P2_Brass"

    # Wall plates, through-bolts and deep sleeves.  Each sleeve crosses the
    # plate's visible face and the first 9 cm of its cantilever arm.
    for x in (-72.0, 72.0):
        b.box(
            (x, 1.5, 88.0),
            (24.0, 5.0, 24.0),
            metal,
            bevel=1.2,
            bevel_subdivisions=2,
        )
        for bolt_x in (x - 6.0, x + 6.0):
            for z in (81.0, 95.0):
                b.cylinder_between(
                    (bolt_x, -3.0, z),
                    (bolt_x, 3.0, z),
                    1.45,
                    brass,
                    radial_steps=12,
                )
        b.cylinder_between(
            (x, 2.0, 84.0),
            (x, -10.0, 84.0),
            4.2,
            metal,
            radial_steps=16,
        )
        b.cylinder_between(
            (x, -1.0, 84.0),
            (x, -78.0, 84.0),
            2.55,
            metal,
            radial_steps=16,
        )
        # Diagonal braces enter both the lower wall plate and the front arm.
        b.cylinder_between(
            (x, -0.5, 76.0),
            (x, -72.0, 84.0),
            1.8,
            metal,
            radial_steps=14,
        )
        b.sphere(
            (x, -72.0, 84.0),
            3.15,
            metal,
            scale=(1.0, 1.0, 0.82),
            phi_steps=8,
            theta_steps=14,
        )

    # The front rail crosses both arm axes by 3 cm at either end.
    b.cylinder_between(
        (-80.0, -78.0, 84.0),
        (80.0, -78.0, 84.0),
        3.0,
        metal,
        radial_steps=18,
    )

    # Three differently proportioned garments create an irregular domestic
    # silhouette.  Separate existing P2 materials intentionally create three
    # overrideable cloth slots without introducing new materials.
    garment_specs = (
        (-50.0, 40.0, 40.0, 80.0, "M_P2_Cloth"),
        (0.0, 39.0, 44.0, 78.0, "M_P2_Cardboard"),
        (50.0, 46.0, 40.0, 68.0, "M_P2_PaintedMetal"),
    )
    for x, center_z, width, height, material_name in garment_specs:
        bottom_z = center_z - height * 0.5
        b.box(
            (x, -79.5, center_z),
            (width, 2.4, height),
            material_name,
            bevel=0.7,
            bevel_subdivisions=2,
        )
        # Proud folds and a hem overlap the cloth body by 0.15 cm.  They catch
        # grazing light but cannot become coplanar cards.
        for fold_x in (x - width * 0.23, x + width * 0.20):
            b.box(
                (fold_x, -81.0, center_z + 1.0),
                (1.2, 0.9, height - 8.0),
                material_name,
                bevel=0.2,
            )
        b.box(
            (x, -81.0, bottom_z + 3.0),
            (width - 4.0, 0.9, 6.0),
            material_name,
            bevel=0.25,
        )
        for clip_x in (x - width * 0.28, x + width * 0.28):
            b.box(
                (clip_x, -79.0, 82.0),
                (4.0, 5.0, 8.0),
                brass,
                rotation=(0.0, 0.0, 4.0 if clip_x < x else -4.0),
                bevel=0.55,
                bevel_subdivisions=2,
            )
    return b


def _build_old_service_door_transom():
    """Create a gap-free double service door, frame and glazed transom.

    Local -Y is the visible side.  Y=0 is the supporting wall face and the
    frame extends to Y=+4, giving a deliberate four-centimetre wall embed.
    Leaves overlap both jambs by 1 cm and a central weather strip covers their
    meeting line, so no black daylight seam is possible.
    """
    b = PropMeshBuilder("OldServiceDoorTransom")
    paint = "M_P2_PaintedMetal"
    metal = "M_P2_OldMetal"
    glass = "M_P2_DarkGlass"
    rubber = "M_P2_Rubber"
    brass = "M_P2_Brass"
    damp = "M_P2_Soil"

    # Two full-depth leaves meet at X=0.  Their outer edges enter the jambs by
    # one centimetre; the centre strip overlaps both leaves by two centimetres.
    for x in (-32.0, 32.0):
        b.box(
            (x, -3.0, 112.0),
            (64.0, 8.0, 224.0),
            paint,
            bevel=1.2,
            bevel_subdivisions=2,
        )
    b.box(
        (0.0, -8.0, 112.0),
        (4.0, 3.0, 224.0),
        rubber,
        bevel=0.55,
        bevel_subdivisions=2,
    )

    # Full-height jambs plus overlapping threshold, transom rail and top rail
    # form one continuous outer frame: 152 X x 298 Z cm.
    for x in (-69.5, 69.5):
        b.box(
            (x, -3.0, 149.0),
            (13.0, 14.0, 298.0),
            metal,
            bevel=1.6,
            bevel_subdivisions=2,
        )
    b.box((0.0, -3.0, 3.0), (152.0, 14.0, 6.0), metal, bevel=1.0)
    b.box(
        (0.0, -3.0, 230.0),
        (140.0, 14.0, 14.0),
        metal,
        bevel=1.3,
        bevel_subdivisions=2,
    )
    b.box(
        (0.0, -3.0, 291.0),
        (152.0, 14.0, 14.0),
        metal,
        bevel=1.5,
        bevel_subdivisions=2,
    )
    b.box(
        (0.0, -3.5, 261.0),
        (128.0, 5.0, 54.0),
        glass,
        bevel=0.65,
        bevel_subdivisions=2,
    )
    # A rubber gasket is proud of the glass but remains behind the metal frame.
    for x, z, sx, sz in (
        (0.0, 235.0, 132.0, 4.0),
        (0.0, 287.0, 132.0, 4.0),
        (-65.0, 261.0, 4.0, 56.0),
        (65.0, 261.0, 4.0, 56.0),
    ):
        b.box((x, -6.5, z), (sx, 2.0, sz), rubber, bevel=0.35)

    # Each leaf has an upper dark panel and a lower pressed panel.  Every
    # applied layer intersects the leaf face by 0.2 cm; its border is another
    # 0.2 cm forward, producing real relief without coplanar surfaces.
    for x in (-32.0, 32.0):
        b.box(
            (x, -7.8, 165.0),
            (46.0, 2.0, 80.0),
            glass,
            bevel=0.7,
            bevel_subdivisions=2,
        )
        for rail_x, rail_z, sx, sz in (
            (x, 123.0, 50.0, 6.0),
            (x, 207.0, 50.0, 6.0),
            (x - 25.0, 165.0, 6.0, 90.0),
            (x + 25.0, 165.0, 6.0, 90.0),
        ):
            b.box(
                (rail_x, -8.6, rail_z),
                (sx, 2.8, sz),
                metal,
                bevel=0.7,
                bevel_subdivisions=2,
            )
        b.box(
            (x, -7.8, 57.0),
            (46.0, 2.0, 74.0),
            paint,
            bevel=1.1,
            bevel_subdivisions=2,
        )
        for rail_x, rail_z, sx, sz in (
            (x, 18.0, 50.0, 6.0),
            (x, 96.0, 50.0, 6.0),
            (x - 25.0, 57.0, 6.0, 84.0),
            (x + 25.0, 57.0, 6.0, 84.0),
        ):
            b.box(
                (rail_x, -8.6, rail_z),
                (sx, 2.8, sz),
                metal,
                bevel=0.7,
                bevel_subdivisions=2,
            )

    # Hinges bridge each leaf edge into its jamb.  Twin pull handles use real
    # stand-offs and continuous grips rather than floating front-face bars.
    for x in (-64.0, 64.0):
        for z in (44.0, 112.0, 190.0):
            b.cylinder(
                (x, -5.5, z),
                2.3,
                14.0,
                metal,
                radial_steps=14,
            )
    for x in (-10.0, 10.0):
        b.box(
            (x, -8.0, 113.0),
            (5.0, 2.4, 42.0),
            rubber,
            bevel=0.7,
            bevel_subdivisions=2,
        )
        for z in (101.0, 127.0):
            b.cylinder_between(
                (x, -8.5, z),
                (x, -13.0, z),
                1.8,
                brass,
                radial_steps=14,
            )
        b.cylinder_between(
            (x, -13.0, 101.0),
            (x, -13.0, 127.0),
            1.8,
            brass,
            radial_steps=16,
        )

    # A shallow, forward-offset damp band gives the threshold age without
    # sharing either the door plane or the frame plane.
    b.box(
        (0.0, -10.6, 8.0),
        (138.0, 1.4, 16.0),
        damp,
        bevel=0.45,
    )
    return b


def _build_wall_lamp_gooseneck():
    """Create one connected wall plate, gooseneck and down-facing lamp.

    Local -Y points away from the wall.  The Y=0 mounting plane passes through
    the plate and socket, and Z=0 is the lower edge of the plate.  The shade,
    gasket, lens and diffuser overlap in depth so grazing views expose no gaps.
    """
    b = PropMeshBuilder("WallLampGooseneck")
    metal = "M_P2_OldMetal"
    paint = "M_P2_PaintedMetal"
    glass = "M_P2_DarkGlass"
    diffuser = "M_P2_Enamel"
    brass = "M_P2_Brass"

    b.box(
        (0.0, 1.5, 28.0),
        (26.0, 5.0, 56.0),
        metal,
        bevel=1.5,
        bevel_subdivisions=2,
    )
    b.box(
        (0.0, -1.2, 42.0),
        (18.0, 2.0, 22.0),
        paint,
        bevel=1.0,
        bevel_subdivisions=2,
    )
    for x in (-7.5, 7.5):
        for z in (10.0, 48.0):
            b.cylinder_between(
                (x, -3.0, z),
                (x, 3.0, z),
                1.45,
                brass,
                radial_steps=12,
            )

    # The socket crosses the wall plate and first arm segment.  Consecutive
    # cylinders deliberately overlap by 2-4 cm and receive rounded elbow nodes.
    b.cylinder_between(
        (0.0, 2.0, 42.0),
        (0.0, -12.0, 42.0),
        4.8,
        metal,
        radial_steps=18,
    )
    b.cylinder_between(
        (0.0, -10.0, 40.0),
        (0.0, -15.0, 66.0),
        3.1,
        metal,
        radial_steps=16,
    )
    b.cylinder_between(
        (0.0, -15.0, 66.0),
        (0.0, -48.0, 66.0),
        3.1,
        metal,
        radial_steps=16,
    )
    b.cylinder_between(
        (0.0, -48.0, 68.0),
        (0.0, -48.0, 55.0),
        3.1,
        metal,
        radial_steps=16,
    )
    for y, z in ((-12.0, 42.0), (-15.0, 66.0), (-48.0, 66.0)):
        b.sphere(
            (0.0, y, z),
            3.8,
            metal,
            scale=(1.0, 1.0, 0.92),
            phi_steps=9,
            theta_steps=16,
        )

    # A downward-flared shade receives a rolled metal rim.  The glass lens
    # enters the shade by 0.5 cm; the smaller diffuser sits another 0.8 cm
    # lower, making it safe to override that slot with an emissive material.
    b.cone(
        (0.0, -48.0, 49.0),
        26.0,
        13.0,
        16.0,
        paint,
        radial_steps=32,
        height_steps=4,
    )
    b.torus(
        (0.0, -48.0, 41.3),
        22.0,
        2.2,
        metal,
        major_steps=32,
        minor_steps=10,
    )
    b.cylinder(
        (0.0, -48.0, 40.0),
        21.0,
        3.0,
        glass,
        radial_steps=32,
    )
    b.cylinder(
        (0.0, -48.0, 38.8),
        17.0,
        1.2,
        diffuser,
        radial_steps=32,
    )
    b.cylinder(
        (0.0, -48.0, 56.0),
        5.0,
        5.0,
        metal,
        radial_steps=18,
    )
    return b


def _build_puddle_patch():
    """Create one low-profile, asymmetric wet patch with no stacked faces."""
    b = PropMeshBuilder("PuddlePatch")
    b.extruded_polygon(
        (
            (-105.0, -4.0),
            (-86.0, -27.0),
            (-55.0, -37.0),
            (-24.0, -31.0),
            (4.0, -43.0),
            (34.0, -34.0),
            (63.0, -25.0),
            (98.0, -10.0),
            (105.0, 7.0),
            (81.0, 24.0),
            (48.0, 31.0),
            (17.0, 24.0),
            (-12.0, 40.0),
            (-46.0, 30.0),
            (-80.0, 19.0),
        ),
        0.28,
        "M_P2_WetPatch",
    )
    return b


PROP_BUILDERS = {
    "VendorTable": _build_vendor_table,
    "Thermos": _build_thermos,
    "ChineseStool": _build_chinese_stool,
    "Toolbox": _build_toolbox,
    "GasCylinder": _build_gas_cylinder,
    "Broom": _build_broom,
    "ChestFreezer": _build_chest_freezer,
    "OutdoorSink": _build_outdoor_sink,
    "TrashBin": _build_trash_bin,
    "PlantPot": _build_plant_pot,
    "CardboardBox": _build_cardboard_box,
    "AlleyBench": _build_alley_bench,
    "WashBasin": _build_wash_basin,
    "ACUnit": _build_ac_unit,
    "MeterBox": _build_meter_box,
    "Bicycle": _build_bicycle,
    "WallUtilityCluster": _build_wall_utility_cluster,
    "StreetLamp": _build_street_lamp,
    "StormDrain": _build_storm_drain,
    "PuddlePatch": _build_puddle_patch,
}

P3_BUILDERS = {
    "StaticShutter": _build_static_shutter,
    "SignAssembly": _build_sign_assembly,
    "AwningAssembly": _build_awning_assembly,
    "SchoolGateLeaf": _build_school_gate_leaf,
    "SchoolGatePost": _build_school_gate_post,
    "AlleyCrossbar": _build_alley_crossbar,
    "SignTextSnack": lambda: _build_sign_text(
        "SignTextSnack", _SIGN_TEXT_PHRASES["SignTextSnack"]
    ),
    "SignTextGeneral": lambda: _build_sign_text(
        "SignTextGeneral", _SIGN_TEXT_PHRASES["SignTextGeneral"]
    ),
    "SignTextRepair": lambda: _build_sign_text(
        "SignTextRepair", _SIGN_TEXT_PHRASES["SignTextRepair"]
    ),
    "SignTextHardware": lambda: _build_sign_text(
        "SignTextHardware", _SIGN_TEXT_PHRASES["SignTextHardware"]
    ),
}

P5_BUILDERS = {
    "LoadedLaundryRack": _build_loaded_laundry_rack,
    "OldServiceDoorTransom": _build_old_service_door_transom,
    "WallLampGooseneck": _build_wall_lamp_gooseneck,
}


def _normalise_asset_result(result, operation_name):
    outcome = None
    if isinstance(result, tuple):
        asset = result[0] if result else None
        if len(result) > 1:
            outcome = result[1]
    else:
        asset = result
    success_pin = getattr(unreal, "GeometryScriptOutcomePins", None)
    if outcome is not None and success_pin is not None:
        if outcome != success_pin.SUCCESS:
            raise RuntimeError("{} failed: {}".format(operation_name, outcome))
    if asset is None:
        raise RuntimeError("{} returned no asset".format(operation_name))
    return asset


def _copy_dynamic_mesh_to_asset(builder, static_mesh, materials):
    ordered_materials = [materials[name] for name in builder.material_names]
    options = unreal.GeometryScriptCopyMeshToAssetOptions()
    options.set_editor_property("enable_recompute_normals", True)
    options.set_editor_property("enable_recompute_tangents", True)
    options.set_editor_property("replace_materials", True)
    options.set_editor_property("new_materials", ordered_materials)
    options.set_editor_property(
        "new_material_slot_names",
        [unreal.Name(name) for name in builder.material_names],
    )
    target_lod = unreal.GeometryScriptMeshWriteLOD()
    target_lod.set_editor_property("lod_index", 0)
    target_lod.set_editor_property("write_hi_res_source", False)
    result = unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
        builder.mesh,
        static_mesh,
        options,
        target_lod,
    )
    _normalise_asset_result(result, "copy_mesh_to_static_mesh")


def _create_collision_mesh(collision_boxes):
    collision = PropMeshBuilder("Collision")
    for location, size, rotation in collision_boxes:
        collision.box(
            location,
            size,
            "M_P2_OldMetal",
            rotation,
            bevel=0.0,
        )
    return collision.mesh


def _apply_collision(static_mesh, collision_boxes):
    if collision_boxes:
        collision_mesh = _create_collision_mesh(collision_boxes)
        generation = unreal.GeometryScriptCollisionFromMeshOptions()
        generation.set_editor_property(
            "method",
            unreal.GeometryScriptCollisionGenerationMethod.ALIGNED_BOXES,
        )
        generation.set_editor_property("auto_detect_spheres", False)
        generation.set_editor_property("auto_detect_capsules", False)
        generation.set_editor_property("auto_detect_boxes", True)
        set_options = unreal.GeometryScriptSetStaticMeshCollisionOptions()
        set_options.set_editor_property("mark_as_customized", True)
        unreal.GeometryScript_Collision.set_static_mesh_collision_from_mesh(
            collision_mesh,
            static_mesh,
            generation,
            set_options,
        )
        return

    # New assets are created collision-free.  This also clears stale simple
    # collision if an asset from an earlier generator version is updated.
    simple_collision_type = getattr(
        unreal,
        "GeometryScriptSimpleCollision",
        None,
    )
    if simple_collision_type is None:
        return
    try:
        simple_collision = simple_collision_type()
        simple_options = unreal.GeometryScriptSetSimpleCollisionOptions()
        _safe_set(simple_options, "emit_transaction", False)
        static_options = unreal.GeometryScriptSetStaticMeshCollisionOptions()
        _safe_set(static_options, "mark_as_customized", True)
        unreal.GeometryScript_Collision.set_simple_collision_of_static_mesh(
            simple_collision,
            static_mesh,
            simple_options,
            static_options,
        )
    except Exception as exc:
        _warn(
            "Could not explicitly clear collision on {}: {}".format(
                static_mesh.get_path_name(),
                exc,
            )
        )


def _create_or_update_asset(asset_root, asset_name, builder, materials):
    asset_path = "{}/{}".format(asset_root, asset_name)
    static_mesh = _load_asset(asset_path)

    if static_mesh is None:
        create_options = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        create_options.set_editor_property("enable_recompute_normals", True)
        create_options.set_editor_property("enable_recompute_tangents", True)
        create_options.set_editor_property("enable_nanite", False)
        create_options.set_editor_property("enable_collision", False)
        result = (
            unreal.GeometryScript_NewAssetUtils
            .create_new_static_mesh_asset_from_mesh(
                builder.mesh,
                asset_path,
                create_options,
            )
        )
        static_mesh = _normalise_asset_result(
            result,
            "create_new_static_mesh_asset_from_mesh",
        )
    if not isinstance(static_mesh, unreal.StaticMesh):
        raise RuntimeError("{} is not a StaticMesh".format(asset_path))

    _copy_dynamic_mesh_to_asset(builder, static_mesh, materials)
    _apply_collision(static_mesh, builder.collision_boxes)
    _safe_set(static_mesh, "light_map_resolution", 64)
    _safe_set(static_mesh, "allow_cpu_access", False)
    if not unreal.EditorAssetLibrary.save_loaded_asset(static_mesh, False):
        raise RuntimeError("Unable to save Static Mesh {}".format(asset_path))
    return static_mesh


def _create_or_update_prop(logical_name, builder, materials):
    return _create_or_update_asset(
        ASSET_ROOT,
        PROP_ASSET_NAMES[logical_name],
        builder,
        materials,
    )


def _create_or_update_p3_module(logical_name, builder, materials):
    return _create_or_update_asset(
        P3_ASSET_ROOT,
        P3_ASSET_NAMES[logical_name],
        builder,
        materials,
    )


def _create_or_update_p5_module(logical_name, builder, materials):
    return _create_or_update_asset(
        P5_ASSET_ROOT,
        P5_ASSET_NAMES[logical_name],
        builder,
        materials,
    )


def ensure_detailed_prop_assets():
    """Create/update the detailed prop library and return its meshes.

    Returns:
        dict[str, unreal.StaticMesh]: Logical prop name to independent asset.
    """
    _require_unreal()
    _ensure_directories()
    wood_textures = _ensure_wood_textures()
    materials = _ensure_materials(wood_textures)

    assets = {}
    for logical_name in PROP_ASSET_NAMES:
        builder = PROP_BUILDERS[logical_name]()
        if not builder.material_names:
            raise RuntimeError("{} produced an empty mesh".format(logical_name))
        assets[logical_name] = _create_or_update_prop(
            logical_name,
            builder,
            materials,
        )
        _log(
            "Prepared {} with {} material slots and {} collision boxes".format(
                logical_name,
                len(builder.material_names),
                len(builder.collision_boxes),
            )
        )

    if set(assets) != set(PROP_ASSET_NAMES):
        raise RuntimeError("Detailed prop asset library is incomplete")
    unreal.EditorAssetLibrary.save_directory(ASSET_ROOT, True, True)
    _log(
        "P2_DETAILED_PROPS_SUCCESS count={} root={}".format(
            len(assets),
            ASSET_ROOT,
        )
    )
    return assets


def ensure_p3_module_assets():
    """Create/update the P3 shopfront and school-gate module library."""
    _require_unreal()
    _ensure_directories()
    wood_textures = _ensure_wood_textures()
    materials = _ensure_materials(wood_textures)

    assets = {}
    for logical_name in P3_ASSET_NAMES:
        builder = P3_BUILDERS[logical_name]()
        if not builder.material_names:
            raise RuntimeError("{} produced an empty mesh".format(logical_name))
        assets[logical_name] = _create_or_update_p3_module(
            logical_name,
            builder,
            materials,
        )
        _log(
            "Prepared P3 {} with {} material slots and {} collision boxes".format(
                logical_name,
                len(builder.material_names),
                len(builder.collision_boxes),
            )
        )

    if set(assets) != set(P3_ASSET_NAMES):
        raise RuntimeError("P3 module asset library is incomplete")
    unreal.EditorAssetLibrary.save_directory(P3_ASSET_ROOT, True, True)
    _log(
        "P3_MODULES_SUCCESS count={} root={}".format(
            len(assets),
            P3_ASSET_ROOT,
        )
    )
    return assets


def ensure_p5_module_assets():
    """Create/update the P5 player-range facade module library."""
    _require_unreal()
    _ensure_directories()
    wood_textures = _ensure_wood_textures()
    materials = _ensure_materials(wood_textures)

    assets = {}
    for logical_name in P5_ASSET_NAMES:
        builder = P5_BUILDERS[logical_name]()
        if not builder.material_names:
            raise RuntimeError("{} produced an empty mesh".format(logical_name))
        if builder.collision_boxes:
            raise RuntimeError(
                "P5 facade module {} must remain collision-free".format(
                    logical_name
                )
            )
        assets[logical_name] = _create_or_update_p5_module(
            logical_name,
            builder,
            materials,
        )
        _log(
            "Prepared P5 {} with {} material slots and no collision".format(
                logical_name,
                len(builder.material_names),
            )
        )

    if set(assets) != set(P5_ASSET_NAMES):
        raise RuntimeError("P5 module asset library is incomplete")
    unreal.EditorAssetLibrary.save_directory(P5_ASSET_ROOT, True, True)
    _log(
        "P5_MODULES_SUCCESS count={} root={}".format(
            len(assets),
            P5_ASSET_ROOT,
        )
    )
    return assets


if __name__ == "__main__":
    ensure_detailed_prop_assets()
    ensure_p3_module_assets()
    ensure_p5_module_assets()
