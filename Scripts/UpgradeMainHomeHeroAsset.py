"""Upgrade MainHome's four stable mesh assets to a detailed hero-shop pass.

Run inside Unreal Editor 5.7:

    py "D:/UE/Project/HorrorGame/Scripts/UpgradeMainHomeHeroAsset.py"

The script deliberately keeps the public contract owned by
CreateEnterableMainHome.py:

* the same four Static Mesh asset paths;
* the same nine ordered material slots;
* the same movable-component pivots;
* the same authored collision boxes; and
* the same 500 x 800 x 400 cm design envelope.

Only visual LOD0 geometry and the relevant material graphs are replaced.  The
interactive Actor therefore continues to use its existing collision and motion
logic without spawning temporary Cube actors.
"""

from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys
import traceback

try:
    import unreal
except ImportError:
    unreal = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_GENERATOR_PATH = PROJECT_ROOT / "Scripts" / "CreateEnterableMainHome.py"
TEXTURE_ROOT = "/Game/MainHome/Textures"

PLASTER_SOURCE_ROOT = (
    PROJECT_ROOT
    / "SourceArt"
    / "ThirdParty"
    / "PolyHaven"
    / "painted_plaster_wall_2k"
)
GREEN_METAL_SOURCE_ROOT = (
    PROJECT_ROOT
    / "SourceArt"
    / "ThirdParty"
    / "PolyHaven"
    / "green_metal_rust_2k"
)
SIGN_SOURCE = (
    PROJECT_ROOT
    / "SourceArt"
    / "Generated"
    / "MainHome"
    / "T_MainHome_SignText.png"
)

TEXTURE_SOURCES = {
    "T_CC0_PaintedPlaster_BaseColor": (
        PLASTER_SOURCE_ROOT / "painted_plaster_wall_diff_2k.jpg",
        "color",
    ),
    "T_CC0_PaintedPlaster_Normal": (
        PLASTER_SOURCE_ROOT / "painted_plaster_wall_nor_dx_2k.jpg",
        "normal",
    ),
    "T_CC0_PaintedPlaster_Roughness": (
        PLASTER_SOURCE_ROOT / "painted_plaster_wall_rough_2k.jpg",
        "roughness",
    ),
    "T_CC0_GreenMetalRust_BaseColor": (
        GREEN_METAL_SOURCE_ROOT / "green_metal_rust_diff_2k.jpg",
        "color",
    ),
    "T_CC0_GreenMetalRust_Normal": (
        GREEN_METAL_SOURCE_ROOT / "green_metal_rust_nor_dx_2k.jpg",
        "normal",
    ),
    "T_CC0_GreenMetalRust_Roughness": (
        GREEN_METAL_SOURCE_ROOT / "green_metal_rust_rough_2k.jpg",
        "roughness",
    ),
    "T_CC0_MainHome_SignText": (SIGN_SOURCE, "mask"),
}

PBR_MATERIAL_CONFIG = {
    "M_MainHome_Wall": {
        "texture_prefix": "T_CC0_PaintedPlaster",
        "texture_size_cm": 130.0,
        "tint": (0.82, 0.76, 0.66, 1.0),
        "roughness_multiplier": 1.04,
        "metallic": 0.0,
    },
    "M_MainHome_Sign": {
        "texture_prefix": "T_CC0_PaintedPlaster",
        "texture_size_cm": 105.0,
        "tint": (0.69, 0.61, 0.49, 1.0),
        "roughness_multiplier": 1.08,
        "metallic": 0.0,
    },
    "M_MainHome_FadedGreenMetal": {
        "texture_prefix": "T_CC0_GreenMetalRust",
        "texture_size_cm": 92.0,
        "tint": (0.60, 0.70, 0.60, 1.0),
        "roughness_multiplier": 1.0,
        # The source is predominantly old paint over metal, not exposed bare
        # metal.  A restrained value prevents the doors looking chrome-plated.
        "metallic": 0.24,
    },
}

SUCCESS_MARKER = "MAIN_HOME_HERO_UPGRADE_SUCCESS"


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _require_unreal():
    _require(
        unreal is not None,
        "UpgradeMainHomeHeroAsset.py must run inside Unreal Editor",
    )


def _log(message):
    if unreal is not None and callable(getattr(unreal, "log", None)):
        unreal.log("[MainHomeHeroUpgrade] {}".format(message))


def _warn(message):
    if unreal is not None and callable(getattr(unreal, "log_warning", None)):
        unreal.log_warning("[MainHomeHeroUpgrade] {}".format(message))


def _safe_set(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        return False


def _load_base_module():
    _require(
        BASE_GENERATOR_PATH.is_file(),
        "Missing base MainHome generator: {}".format(BASE_GENERATOR_PATH),
    )
    module_name = "CreateEnterableMainHome_HeroUpgradeBase"
    spec = importlib.util.spec_from_file_location(
        module_name,
        str(BASE_GENERATOR_PATH),
    )
    _require(
        spec is not None and spec.loader is not None,
        "Unable to construct the MainHome base-module loader",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _validate_base_contract(base):
    expected_paths = (
        "/Game/MainHome/SM_MainHome_Enterable",
        "/Game/MainHome/SM_MainHome_Shutter",
        "/Game/MainHome/SM_MainHome_Door_Left",
        "/Game/MainHome/SM_MainHome_Door_Right",
    )
    actual_paths = (
        base.STATIC_MESH_ASSET_PATH,
        base.SHUTTER_STATIC_MESH_ASSET_PATH,
        base.LEFT_DOOR_STATIC_MESH_ASSET_PATH,
        base.RIGHT_DOOR_STATIC_MESH_ASSET_PATH,
    )
    _require(
        actual_paths == expected_paths,
        "The base generator's four stable asset paths have changed: {}".format(
            actual_paths
        ),
    )
    expected_material_order = [
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
    _require(
        list(base.MATERIAL_ORDER) == expected_material_order,
        "The base generator's stable material order has changed",
    )
    _require(
        tuple(base.DESIGN_BOUNDS)
        == ((-250.0, 250.0), (-400.0, 400.0), (1.0, 401.0)),
        "The MainHome design envelope is no longer 500 x 800 x 400 cm",
    )
    definition_paths = tuple(
        definition.asset_path for definition in base.MESH_ASSET_DEFINITIONS
    )
    _require(
        definition_paths == expected_paths,
        "The base mesh-definition order no longer matches the stable assets",
    )


def _load_asset(asset_path, required=True):
    asset = (
        unreal.EditorAssetLibrary.load_asset(asset_path)
        if unreal.EditorAssetLibrary.does_asset_exist(asset_path)
        else None
    )
    if required and asset is None:
        raise RuntimeError("Missing required asset: {}".format(asset_path))
    return asset


def _import_texture(asset_name, source_path, texture_kind):
    _require(
        source_path.is_file(),
        "Missing texture source: {}".format(source_path),
    )
    unreal.EditorAssetLibrary.make_directory(TEXTURE_ROOT)

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source_path))
    task.set_editor_property("destination_path", TEXTURE_ROOT)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset_path = "{}/{}".format(TEXTURE_ROOT, asset_name)
    texture = _load_asset(asset_path)
    _require(
        isinstance(texture, unreal.Texture2D),
        "{} did not import as Texture2D".format(asset_path),
    )

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
    else:
        _safe_set(texture, "srgb", True)

    if texture_kind == "mask":
        texture_address = getattr(unreal, "TextureAddress", None)
        clamp = getattr(texture_address, "TA_CLAMP", None)
        if clamp is not None:
            _safe_set(texture, "address_x", clamp)
            _safe_set(texture, "address_y", clamp)

    _safe_set(texture, "virtual_texture_streaming", False)
    _require(
        unreal.EditorAssetLibrary.save_loaded_asset(texture, False),
        "Unable to save imported texture {}".format(asset_path),
    )
    return texture


def _import_cc0_textures():
    return {
        asset_name: _import_texture(asset_name, source_path, texture_kind)
        for asset_name, (source_path, texture_kind) in TEXTURE_SOURCES.items()
    }


def _material_expression(material, expression_type, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        expression_type,
        int(x),
        int(y),
    )
    _require(
        node is not None,
        "Unable to create material expression {}".format(
            getattr(expression_type, "__name__", expression_type)
        ),
    )
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


def _constant_color(material, color, x, y):
    node = _material_expression(
        material,
        unreal.MaterialExpressionConstant3Vector,
        x,
        y,
    )
    node.set_editor_property("constant", unreal.LinearColor(*color))
    return node


def _connect(source, output_name, target, input_name, description):
    _require(
        unreal.MaterialEditingLibrary.connect_material_expressions(
            source,
            output_name,
            target,
            input_name,
        ),
        "Unable to connect material nodes for {}".format(description),
    )


def _connect_property(node, output_name, material_property, description):
    _require(
        unreal.MaterialEditingLibrary.connect_material_property(
            node,
            output_name,
            material_property,
        ),
        "Unable to connect material property for {}".format(description),
    )


def _ensure_material_asset(base, material_name):
    asset_path = "{}/{}".format(base.MATERIAL_FOLDER, material_name)
    material = _load_asset(asset_path, required=False)
    if material is None:
        unreal.EditorAssetLibrary.make_directory(base.MATERIAL_FOLDER)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            material_name,
            base.MATERIAL_FOLDER,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
    _require(material is not None, "Unable to create {}".format(asset_path))
    return material


def _world_aligned_sample(
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
    material_function = _load_asset(function_path)
    texture_object = _material_expression(
        material,
        unreal.MaterialExpressionTextureObject,
        x,
        y,
    )
    texture_object.set_editor_property("texture", texture)
    if normal:
        _safe_set(
            texture_object,
            "sampler_type",
            unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
        )

    texture_size = _constant_color(
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
    function_call = _material_expression(
        material,
        unreal.MaterialExpressionMaterialFunctionCall,
        x + 280,
        y,
    )
    _require(
        function_call.set_material_function(material_function),
        "Unable to bind {}".format(function_path),
    )
    _connect(
        texture_object,
        "",
        function_call,
        "TextureObject",
        function_path,
    )
    _connect(
        texture_size,
        "",
        function_call,
        "TextureSize",
        function_path,
    )
    return function_call, "XYZ Texture"


def _rebuild_world_aligned_pbr_material(
    base,
    material_name,
    textures,
    config,
):
    material = _ensure_material_asset(base, material_name)
    # UE 5.7 can keep expressions from an already-saved material rooted while
    # an unattended editor script is running.  DeleteAllMaterialExpressions
    # then asserts inside MaterialEditor.  New output connections safely
    # replace the active inputs; leaving the old, disconnected nodes in the
    # editor graph is harmless and makes repeat runs crash-free.
    _safe_set(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    _safe_set(material, "two_sided", False)

    prefix = config["texture_prefix"]
    base_color_texture = textures[prefix + "_BaseColor"]
    normal_texture = textures[prefix + "_Normal"]
    roughness_texture = textures[prefix + "_Roughness"]

    base_node, base_output = _world_aligned_sample(
        material,
        base_color_texture,
        config["texture_size_cm"],
        -1180,
        -420,
        False,
    )
    normal_node, normal_output = _world_aligned_sample(
        material,
        normal_texture,
        config["texture_size_cm"],
        -1180,
        -45,
        True,
    )
    rough_node, rough_output = _world_aligned_sample(
        material,
        roughness_texture,
        config["texture_size_cm"],
        -1180,
        330,
        False,
    )

    tint = _constant_color(material, config["tint"], -520, -350)
    tint_multiply = _material_expression(
        material,
        unreal.MaterialExpressionMultiply,
        -235,
        -300,
    )
    _connect(base_node, base_output, tint_multiply, "A", material_name)
    _connect(tint, "", tint_multiply, "B", material_name)

    roughness_scale = _constant_scalar(
        material,
        config["roughness_multiplier"],
        -500,
        300,
    )
    roughness_multiply = _material_expression(
        material,
        unreal.MaterialExpressionMultiply,
        -210,
        265,
    )
    _connect(rough_node, rough_output, roughness_multiply, "A", material_name)
    _connect(roughness_scale, "", roughness_multiply, "B", material_name)

    metallic = _constant_scalar(
        material,
        config["metallic"],
        -180,
        425,
    )
    specular = _constant_scalar(material, 0.38, -180, 505)

    _connect_property(
        tint_multiply,
        "",
        unreal.MaterialProperty.MP_BASE_COLOR,
        material_name,
    )
    _connect_property(
        normal_node,
        normal_output,
        unreal.MaterialProperty.MP_NORMAL,
        material_name,
    )
    _connect_property(
        roughness_multiply,
        "",
        unreal.MaterialProperty.MP_ROUGHNESS,
        material_name,
    )
    _connect_property(
        metallic,
        "",
        unreal.MaterialProperty.MP_METALLIC,
        material_name,
    )
    _connect_property(
        specular,
        "",
        unreal.MaterialProperty.MP_SPECULAR,
        material_name,
    )

    unreal.MaterialEditingLibrary.recompile_material(material)
    asset_path = "{}/{}".format(base.MATERIAL_FOLDER, material_name)
    _require(
        unreal.EditorAssetLibrary.save_loaded_asset(material, False),
        "Unable to save material {}".format(asset_path),
    )
    return material


def _rebuild_masked_sign_material(base, sign_texture):
    material_name = "M_MainHome_Letters"
    material = _ensure_material_asset(base, material_name)
    # See the UE 5.7 rooted-expression note in
    # _rebuild_world_aligned_pbr_material.  Rewire the output pins without
    # deleting the previously saved graph.
    _safe_set(material, "blend_mode", unreal.BlendMode.BLEND_MASKED)
    # The generated card is a single triangle pair.  Keeping the masked text
    # material two-sided makes the sign robust to primitive winding changes
    # between Geometry Script versions; the PNG itself remains directional.
    _safe_set(material, "two_sided", True)
    _safe_set(material, "opacity_mask_clip_value", 0.18)
    _safe_set(material, "cast_shadow_as_masked", True)

    sample = _material_expression(
        material,
        unreal.MaterialExpressionTextureSample,
        -650,
        -120,
    )
    sample.set_editor_property("texture", sign_texture)
    # FRectangleMeshGenerator preserves texel density by shrinking the V
    # coordinate to Height / Width for a wide rectangle.  Expand V back to
    # 0..1 so the transparent sign texture is sampled in full instead of only
    # its empty lower margin.
    sign_uv = _material_expression(
        material,
        unreal.MaterialExpressionTextureCoordinate,
        -900,
        -120,
    )
    # Negative tiling reverses the axes; adding (1, 1) below keeps the result
    # inside the texture's 0..1 range.
    sign_uv.set_editor_property("u_tiling", -1.0)
    sign_uv.set_editor_property("v_tiling", -(408.0 / 88.0))
    orientation_fix = _material_expression(
        material,
        unreal.MaterialExpressionAdd,
        -760,
        -120,
    )
    uv_offset = _material_expression(
        material,
        unreal.MaterialExpressionConstant2Vector,
        -900,
        20,
    )
    uv_offset.set_editor_property("r", 1.0)
    uv_offset.set_editor_property("g", 1.0)
    _connect(sign_uv, "", orientation_fix, "A", "sign UV scale")
    _connect(uv_offset, "", orientation_fix, "B", "sign UV offset")
    # The front camera looks along +Y, while this -Y-facing Geometry Script
    # card presents both generated UV axes reversed.  Flip the corrected pair
    # so the Chinese lettering reads upright and left-to-right.
    _connect(orientation_fix, "", sample, "UVs", "sign orientation")
    roughness = _constant_scalar(material, 0.78, -300, 180)
    metallic = _constant_scalar(material, 0.0, -300, 270)

    _connect_property(
        sample,
        "RGB",
        unreal.MaterialProperty.MP_BASE_COLOR,
        material_name,
    )
    _connect_property(
        sample,
        "A",
        unreal.MaterialProperty.MP_OPACITY_MASK,
        material_name,
    )
    _connect_property(
        roughness,
        "",
        unreal.MaterialProperty.MP_ROUGHNESS,
        material_name,
    )
    _connect_property(
        metallic,
        "",
        unreal.MaterialProperty.MP_METALLIC,
        material_name,
    )

    unreal.MaterialEditingLibrary.recompile_material(material)
    asset_path = "{}/{}".format(base.MATERIAL_FOLDER, material_name)
    _require(
        unreal.EditorAssetLibrary.save_loaded_asset(material, False),
        "Unable to save material {}".format(asset_path),
    )
    return material


def _prepare_materials(base, textures):
    materials = {}
    for material_name in base.MATERIAL_ORDER:
        if material_name in PBR_MATERIAL_CONFIG:
            materials[material_name] = _rebuild_world_aligned_pbr_material(
                base,
                material_name,
                textures,
                PBR_MATERIAL_CONFIG[material_name],
            )
        elif material_name == "M_MainHome_Letters":
            materials[material_name] = _rebuild_masked_sign_material(
                base,
                textures["T_CC0_MainHome_SignText"],
            )
        else:
            # Retain the stable project materials that do not have a supplied
            # CC0 PBR set.  The base helper is idempotent and keeps their paths
            # and material-slot ownership unchanged.
            materials[material_name] = base.ensure_material(material_name)
    return materials


def _make_transform(location, rotation=(0.0, 0.0, 0.0)):
    return unreal.Transform(
        location=unreal.Vector(
            float(location[0]),
            float(location[1]),
            float(location[2]),
        ),
        rotation=unreal.Rotator(
            pitch=float(rotation[0]),
            yaw=float(rotation[1]),
            roll=float(rotation[2]),
        ),
        scale=unreal.Vector(1.0, 1.0, 1.0),
    )


def _normalise_mesh_result(result, current_mesh, operation_name):
    outcome = None
    if isinstance(result, tuple):
        mesh = result[0] if result else None
        if len(result) > 1:
            outcome = result[1]
    else:
        mesh = result
    success_pin = getattr(unreal, "GeometryScriptOutcomePins", None)
    if outcome is not None and success_pin is not None:
        _require(
            outcome == success_pin.SUCCESS,
            "{} failed: {}".format(operation_name, outcome),
        )
    return current_mesh if mesh is None else mesh


class HeroMeshBuilder:
    """Append bevelled visual primitives while tracking exact local bounds."""

    def __init__(self, base, logical_name):
        self.base = base
        self.logical_name = logical_name
        self.mesh = unreal.DynamicMesh()
        base._enable_material_ids(self.mesh)
        self.material_names = set()
        self.primitive_bounds = []

    def _options(self, material_name):
        _require(
            material_name in self.base.MATERIAL_ID_BY_NAME,
            "Unknown material {} on {}".format(
                material_name,
                self.logical_name,
            ),
        )
        self.material_names.add(material_name)
        return self.base.primitive_options_for(
            self.base.MATERIAL_ID_BY_NAME[material_name]
        )

    def _record_box_bounds(self, location, size):
        self.primitive_bounds.append(
            tuple(
                (
                    float(location[axis]) - float(size[axis]) * 0.5,
                    float(location[axis]) + float(size[axis]) * 0.5,
                )
                for axis in range(3)
            )
        )

    def _record_cylinder_bounds(self, location, radius, height, axis):
        x, y, z = (float(value) for value in location)
        radius = float(radius)
        half_height = float(height) * 0.5
        if axis == "x":
            bounds = (
                (x - half_height, x + half_height),
                (y - radius, y + radius),
                (z - radius, z + radius),
            )
        elif axis == "y":
            bounds = (
                (x - radius, x + radius),
                (y - half_height, y + half_height),
                (z - radius, z + radius),
            )
        else:
            bounds = (
                (x - radius, x + radius),
                (y - radius, y + radius),
                (z - half_height, z + half_height),
            )
        self.primitive_bounds.append(bounds)

    def _append_raw_box(self, target_mesh, location, size, material_name):
        result = unreal.GeometryScript_Primitives.append_box(
            target_mesh,
            self._options(material_name),
            _make_transform(location),
            float(size[0]),
            float(size[1]),
            float(size[2]),
            0,
            0,
            0,
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        return _normalise_mesh_result(result, target_mesh, "append_box")

    def box(self, location, size, material_name, bevel=0.0):
        _require(
            min(float(value) for value in size) > 0.0,
            "{} contains a zero-size box".format(self.logical_name),
        )
        self._record_box_bounds(location, size)
        bevel = min(
            float(bevel),
            max(0.0, float(min(size)) * 0.42),
        )
        if bevel <= 0.0:
            self.mesh = self._append_raw_box(
                self.mesh,
                location,
                size,
                material_name,
            )
            return self

        temporary_mesh = unreal.DynamicMesh()
        self.base._enable_material_ids(temporary_mesh)
        temporary_mesh = self._append_raw_box(
            temporary_mesh,
            location,
            size,
            material_name,
        )
        try:
            bevel_options = unreal.GeometryScriptMeshBevelOptions()
            bevel_options.set_editor_property("bevel_distance", bevel)
            bevel_options.set_editor_property("infer_material_id", True)
            bevel_options.set_editor_property(
                "set_material_id",
                int(self.base.MATERIAL_ID_BY_NAME[material_name]),
            )
            bevel_options.set_editor_property("subdivisions", 2)
            bevel_options.set_editor_property("round_weight", 0.72)
            result = unreal.GeometryScript_MeshModeling.apply_mesh_polygroup_bevel(
                temporary_mesh,
                bevel_options,
            )
            temporary_mesh = _normalise_mesh_result(
                result,
                temporary_mesh,
                "apply_mesh_polygroup_bevel",
            )
            append_options = unreal.GeometryScriptAppendMeshOptions()
            result = unreal.GeometryScript_MeshEdits.append_mesh(
                self.mesh,
                temporary_mesh,
                _make_transform((0.0, 0.0, 0.0)),
                False,
                append_options,
            )
            self.mesh = _normalise_mesh_result(
                result,
                self.mesh,
                "append_bevelled_mesh",
            )
        except Exception as exc:
            _warn(
                "{} bevel skipped for size {}: {}".format(
                    self.logical_name,
                    size,
                    exc,
                )
            )
            self.mesh = self._append_raw_box(
                self.mesh,
                location,
                size,
                material_name,
            )
        return self

    def cylinder(
        self,
        location,
        radius,
        height,
        material_name,
        axis="z",
        radial_steps=20,
        height_steps=1,
    ):
        axis = str(axis).lower()
        _require(axis in ("x", "y", "z"), "Invalid cylinder axis {}".format(axis))
        rotation = {
            "x": (90.0, 0.0, 0.0),
            "y": (0.0, 0.0, 90.0),
            "z": (0.0, 0.0, 0.0),
        }[axis]
        result = unreal.GeometryScript_Primitives.append_cylinder(
            self.mesh,
            self._options(material_name),
            _make_transform(location, rotation),
            float(radius),
            float(height),
            int(radial_steps),
            int(height_steps),
            True,
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        self.mesh = _normalise_mesh_result(
            result,
            self.mesh,
            "append_cylinder",
        )
        self._record_cylinder_bounds(location, radius, height, axis)
        return self

    def rectangle_xz(self, location, size_x, size_z, material_name):
        """Append one UV-complete card whose visible normal faces -Y."""
        result = unreal.GeometryScript_Primitives.append_rectangle_xy(
            self.mesh,
            self._options(material_name),
            # UE uses a left-handed coordinate system.  Roll -90 maps the
            # rectangle's +Z normal to -Y while keeping its local +Y axis
            # upright as world +Z.
            _make_transform(location, (0.0, 0.0, -90.0)),
            float(size_x),
            float(size_z),
            0,
            0,
        )
        self.mesh = _normalise_mesh_result(
            result,
            self.mesh,
            "append_rectangle_xy",
        )
        x, y, z = (float(value) for value in location)
        self.primitive_bounds.append(
            (
                (x - float(size_x) * 0.5, x + float(size_x) * 0.5),
                (y, y),
                (z - float(size_z) * 0.5, z + float(size_z) * 0.5),
            )
        )
        return self

    def cylinder_between(
        self,
        start,
        end,
        radius,
        material_name,
        radial_steps=20,
    ):
        start = tuple(float(value) for value in start)
        end = tuple(float(value) for value in end)
        delta = tuple(end[index] - start[index] for index in range(3))
        varying_axes = [
            index for index, value in enumerate(delta) if abs(value) > 0.001
        ]
        _require(
            len(varying_axes) == 1,
            "{} only accepts axis-aligned detail cylinders".format(
                self.logical_name
            ),
        )
        axis_index = varying_axes[0]
        axis = ("x", "y", "z")[axis_index]
        midpoint = tuple(
            (start[index] + end[index]) * 0.5 for index in range(3)
        )
        return self.cylinder(
            midpoint,
            radius,
            abs(delta[axis_index]),
            material_name,
            axis=axis,
            radial_steps=radial_steps,
        )

    def validate_world_bounds(self, translation, design_bounds):
        _require(
            self.primitive_bounds,
            "{} produced no visual primitives".format(self.logical_name),
        )
        translated_bounds = []
        for bounds in self.primitive_bounds:
            translated_bounds.append(
                tuple(
                    (
                        bounds[axis][0] + float(translation[axis]),
                        bounds[axis][1] + float(translation[axis]),
                    )
                    for axis in range(3)
                )
            )
        overall = tuple(
            (
                min(bounds[axis][0] for bounds in translated_bounds),
                max(bounds[axis][1] for bounds in translated_bounds),
            )
            for axis in range(3)
        )
        epsilon = 0.001
        for axis, (actual, allowed) in enumerate(zip(overall, design_bounds)):
            _require(
                actual[0] >= float(allowed[0]) - epsilon
                and actual[1] <= float(allowed[1]) + epsilon,
                "{} exceeds the MainHome envelope on axis {}: {} not in {}".format(
                    self.logical_name,
                    axis,
                    actual,
                    allowed,
                ),
            )
        return overall


def _fixed_box_bevel(box):
    if box.category == "structure":
        return min(1.25, min(box.size_cm) * 0.13)
    if box.category in ("frame", "trim", "sign"):
        return min(0.65, min(box.size_cm) * 0.18)
    if box.category in ("side_detail",):
        return min(0.45, min(box.size_cm) * 0.16)
    return 0.0


def _front_frame_visual_parameters(box):
    location = list(box.location_cm)
    size = list(box.size_cm)
    front_detail_labels = (
        "ShutterFrame_",
        "DoorFrame_",
        "DoorTransom_Bar",
    )
    if box.label.startswith(front_detail_labels) and size[1] >= 3.5:
        original_front = location[1] - size[1] * 0.5
        original_back = location[1] + size[1] * 0.5
        visual_front = original_front + 0.9
        location[1] = (visual_front + original_back) * 0.5
        size[1] = original_back - visual_front
    return tuple(location), tuple(size)


def _add_fixed_shell_hardware(builder):
    trim = "M_MainHome_Trim"
    green = "M_MainHome_FadedGreenMetal"

    # A dedicated rectangle gives the sign the full 0..1 UV range.  A box
    # primitive packs its six faces into UV0 and can sample only transparent
    # corners of this PNG.  The card is 0.55 cm in front of the sign panel,
    # faces -Y, cannot Z-fight, and remains behind the proud outer trim.
    builder.rectangle_xz(
        (0.0, -398.55, 319.0),
        408.0,
        88.0,
        "M_MainHome_Letters",
    )

    # Sign-panel fasteners.
    for x in (-215.0, 215.0):
        for z in (301.5, 336.5):
            builder.cylinder(
                (x, -398.9, z),
                1.8,
                1.8,
                trim,
                axis="y",
                radial_steps=18,
            )

    # Rivets on both shutter guides and both double-door jambs.  The visual
    # frame faces were moved inward 0.9 cm, but collision remains unchanged.
    for x, z_values in (
        (-216.0, (35.0, 82.0, 129.0, 176.0, 223.0, 260.0)),
        (24.0, (35.0, 82.0, 129.0, 176.0, 223.0, 260.0)),
        (72.0, (30.0, 78.0, 126.0, 174.0, 222.0, 268.0)),
        (216.0, (30.0, 78.0, 126.0, 174.0, 222.0, 268.0)),
    ):
        for z in z_values:
            builder.cylinder(
                (x, -399.5, z),
                1.25,
                1.0,
                trim,
                axis="y",
                radial_steps=14,
            )

    # Replace the old one-centimetre side-drainpipe strip with a round pipe and
    # three round wall clips, all contained by X=250 cm.
    builder.cylinder(
        (247.0, 330.0, 171.0),
        2.4,
        300.0,
        trim,
        axis="z",
        radial_steps=20,
        height_steps=3,
    )
    for z in (65.0, 170.0, 275.0):
        builder.cylinder(
            (248.0, 330.0, z),
            3.1,
            3.5,
            green,
            axis="x",
            radial_steps=18,
        )

    # Round shutter drum and double-door header tube, visible below the fixed
    # square housings without interfering with the movable leaves.
    builder.cylinder(
        (-96.0, -392.0, 283.0),
        6.4,
        230.0,
        green,
        axis="x",
        radial_steps=28,
    )
    builder.cylinder(
        (144.0, -393.0, 286.0),
        2.1,
        136.0,
        trim,
        axis="x",
        radial_steps=18,
    )


def _build_fixed_shell(base, definition):
    builder = HeroMeshBuilder(base, "FixedShell")
    for box in definition.visual_boxes:
        if box.label.startswith("Letter_") or box.label == "Side_Drainpipe":
            continue
        location, size = _front_frame_visual_parameters(box)
        builder.box(
            location,
            size,
            box.material_name,
            bevel=_fixed_box_bevel(box),
        )
    _add_fixed_shell_hardware(builder)
    return builder


def _build_shutter(base, definition):
    builder = HeroMeshBuilder(base, "Shutter")
    green = "M_MainHome_FadedGreenMetal"
    trim = "M_MainHome_Trim"

    panel = next(
        box
        for box in definition.visual_boxes
        if box.label == "Shutter_Panel"
    )
    # Shallow backing makes the real gaps between slats dark without adding
    # coplanar groove cards.
    builder.box(
        (panel.location_cm[0], 1.25, panel.location_cm[2]),
        (panel.size_cm[0], 2.0, panel.size_cm[2]),
        green,
        bevel=0.55,
    )

    slat_count = 20
    slat_step = 12.6
    slat_height = 10.8
    for index in range(slat_count):
        z = -6.3 - float(index) * slat_step
        builder.box(
            (0.0, -1.7, z),
            (226.0, 3.6, slat_height),
            green,
            bevel=0.62,
        )
        # Rolled lower lip catches highlights and makes every slat read as a
        # folded sheet rather than a line painted onto one panel.
        builder.box(
            (0.0, -3.55, z - 4.45),
            (223.0, 0.75, 0.9),
            trim,
            bevel=0.18,
        )
        for x in (-114.5, 114.5):
            builder.box(
                (x, -2.0, z),
                (3.0, 4.0, 10.4),
                trim,
                bevel=0.38,
            )

    builder.box(
        (0.0, -2.3, -257.0),
        (232.0, 5.0, 10.0),
        trim,
        bevel=1.1,
    )

    # Central lock case, key cylinder, latch pins and a round pull handle.
    builder.box(
        (0.0, -4.35, -242.0),
        (25.0, 1.6, 16.0),
        trim,
        bevel=0.65,
    )
    builder.cylinder(
        (0.0, -5.0, -242.0),
        2.5,
        1.0,
        trim,
        axis="y",
        radial_steps=22,
    )
    for x in (-7.5, 7.5):
        builder.cylinder(
            (x, -5.05, -247.0),
            1.1,
            0.9,
            trim,
            axis="y",
            radial_steps=14,
        )
    builder.cylinder(
        (0.0, -4.2, -257.0),
        1.15,
        30.0,
        trim,
        axis="x",
        radial_steps=16,
    )
    for x in (-15.0, 15.0):
        builder.cylinder_between(
            (x, -2.6, -257.0),
            (x, -4.2, -257.0),
            1.15,
            trim,
            radial_steps=16,
        )
    return builder


def _door_panel_box(definition):
    return next(
        box for box in definition.visual_boxes if box.category == "door_leaf"
    )


def _add_door_frame_ring(builder, center_x, direction):
    green = "M_MainHome_FadedGreenMetal"
    trim = green
    glass = "M_MainHome_DarkGlass"

    inner_width = 52.0
    vertical_edge = 29.0
    left_x = center_x - vertical_edge
    right_x = center_x + vertical_edge

    # Outer perimeter rails.
    for x in (left_x, right_x):
        builder.box(
            (x, -2.35, 0.0),
            (5.0, 1.7, 205.0),
            trim,
            bevel=0.55,
        )
    for z in (-102.0, 102.0):
        builder.box(
            (center_x, -2.35, z),
            (63.0, 1.7, 5.0),
            trim,
            bevel=0.55,
        )

    # Recessed upper glass, separated from the frame face by 0.85 cm.
    builder.box(
        (center_x, -1.72, 30.0),
        (inner_width, 0.35, 78.0),
        glass,
        bevel=0.15,
    )
    # Continue the dark glazing into the small upper leaf panel.  This meets
    # the top and divider rails exactly, eliminating the bright "gap" that
    # previously read between the black transom and the door frame.
    builder.box(
        (center_x, -1.72, 86.5),
        (inner_width, 0.35, 25.0),
        glass,
        bevel=0.15,
    )
    for z in (-11.5, 71.5):
        builder.box(
            (center_x, -2.35, z),
            (63.0, 1.7, 5.0),
            trim,
            bevel=0.5,
        )

    # Lower recessed sheet and its four-sided frame.
    builder.box(
        (center_x, -1.72, -64.0),
        (inner_width, 0.35, 52.0),
        green,
        bevel=0.15,
    )
    for z in (-92.5, -35.5):
        builder.box(
            (center_x, -2.35, z),
            (63.0, 1.7, 5.0),
            trim,
            bevel=0.5,
        )

    # Small corner fasteners around the glass/lower-panel frame.
    for x in (left_x, right_x):
        for z in (-91.0, -36.5, -10.0, 70.0):
            builder.cylinder(
                (x, -3.0, z),
                0.85,
                0.9,
                trim,
                axis="y",
                radial_steps=12,
            )


def _add_door_hardware(builder, direction, center_x):
    trim = "M_MainHome_Trim"
    green = "M_MainHome_FadedGreenMetal"
    handle_x = direction * 59.0

    # True round U handle: vertical grip plus two capped stand-offs.
    builder.cylinder(
        (handle_x, -4.3, 4.0),
        1.2,
        24.0,
        trim,
        axis="z",
        radial_steps=18,
    )
    for z in (-8.0, 16.0):
        builder.cylinder_between(
            (handle_x, -2.55, z),
            (handle_x, -4.3, z),
            1.2,
            trim,
            radial_steps=18,
        )
        builder.cylinder(
            (handle_x, -2.45, z),
            2.0,
            0.8,
            trim,
            axis="y",
            radial_steps=18,
        )

    lock_x = direction * 58.5
    builder.box(
        (lock_x, -2.7, -20.0),
        (8.0, 1.0, 12.0),
        green,
        bevel=0.35,
    )
    builder.cylinder(
        (lock_x, -3.55, -20.0),
        2.25,
        1.2,
        trim,
        axis="y",
        radial_steps=22,
    )

    # Three hinge barrels and their mounting leaves at the local hinge edge.
    for z in (-76.0, 0.0, 76.0):
        builder.cylinder(
            (0.0, -1.9, z),
            2.15,
            13.0,
            trim,
            axis="z",
            radial_steps=20,
        )
        builder.box(
            (direction * 3.0, -1.95, z),
            (6.0, 1.2, 13.0),
            green,
            bevel=0.35,
        )


def _build_door(base, definition, side):
    _require(side in ("left", "right"), "Invalid door side {}".format(side))
    direction = 1.0 if side == "left" else -1.0
    builder = HeroMeshBuilder(base, "{}Door".format(side.title()))
    panel = _door_panel_box(definition)

    builder.box(
        panel.location_cm,
        panel.size_cm,
        panel.material_name,
        bevel=0.82,
    )
    center_x = direction * (float(base.DOOR_VISIBLE_SPAN_CM) * 0.5)
    _add_door_frame_ring(builder, center_x, direction)
    _add_door_hardware(builder, direction, center_x)

    if side == "left":
        # The astragal overlaps the nominal 0.5 cm closed gap and the right
        # leaf by less than one centimetre.  It is visual-only, so independent
        # door collision and opening behaviour remain unchanged.
        builder.box(
            (float(base.DOOR_VISIBLE_SPAN_CM) + 0.15, -3.0, 0.0),
            (2.2, 2.0, 208.0),
            "M_MainHome_Trim",
            bevel=0.48,
        )
    else:
        builder.box(
            (-float(base.DOOR_VISIBLE_SPAN_CM) + 0.35, -2.25, 0.0),
            (1.0, 1.4, 204.0),
            "M_MainHome_FadedGreenMetal",
            bevel=0.28,
        )
    return builder


def _compact_visual_mesh(base, builder, ordered_materials):
    compact = getattr(base, "_compact_visual_material_sections", None)
    if not callable(compact):
        return builder.mesh, sorted(
            base.MATERIAL_ID_BY_NAME[name] for name in builder.material_names
        ), False
    material_uses = [
        SimpleNamespace(material_name=material_name)
        for material_name in sorted(
            builder.material_names,
            key=lambda name: base.MATERIAL_ID_BY_NAME[name],
        )
    ]
    return compact(builder.mesh, ordered_materials, material_uses)


def _create_or_update_static_mesh(
    base,
    definition,
    builder,
    materials,
):
    translation = definition.actor_relative_transform.location_cm
    bounds = builder.validate_world_bounds(translation, base.DESIGN_BOUNDS)
    ordered_materials = [materials[name] for name in base.MATERIAL_ORDER]
    visual_mesh, used_slots, compacted = _compact_visual_mesh(
        base,
        builder,
        ordered_materials,
    )
    collision_mesh = base.create_collision_dynamic_mesh(
        definition.collision_boxes
    )
    static_mesh = base._load_asset_if_exists(definition.asset_path)

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
        static_mesh = base._normalize_geometry_script_result(
            result,
            "create_new_static_mesh_asset_from_mesh",
        )

    base._copy_visual_mesh_to_static_mesh(
        visual_mesh,
        static_mesh,
        ordered_materials,
    )
    if compacted:
        base._remap_compacted_sections_to_global_slots(
            static_mesh,
            used_slots,
        )
    static_mesh = base.apply_structural_collision(
        collision_mesh,
        static_mesh,
        definition.asset_path,
    )
    _log(
        "Updated {} materials={} world_bounds={}".format(
            definition.asset_path,
            ",".join(
                sorted(
                    builder.material_names,
                    key=lambda name: base.MATERIAL_ID_BY_NAME[name],
                )
            ),
            bounds,
        )
    )
    return static_mesh


def upgrade_main_home_assets(base_module=None):
    """Import CC0 inputs and overwrite the four stable MainHome mesh assets.

    Args:
        base_module: Optional already-imported CreateEnterableMainHome module.
            Supplying it is useful when this upgrade is invoked by a larger
            editor pipeline.  When omitted, the stable generator is loaded from
            ``Scripts/CreateEnterableMainHome.py``.

    Returns:
        A dictionary containing ``textures``, ``materials`` and
        ``static_meshes`` mappings.  No temporary actors are spawned.
    """

    _require_unreal()
    base = base_module if base_module is not None else _load_base_module()
    _validate_base_contract(base)

    # Validate the unchanged collision/opening contract before touching assets.
    base.validate_design(base.build_box_specs())
    textures = _import_cc0_textures()
    materials = _prepare_materials(base, textures)

    definitions = {
        definition.asset_path: definition
        for definition in base.MESH_ASSET_DEFINITIONS
    }
    builders = {
        base.STATIC_MESH_ASSET_PATH: _build_fixed_shell(
            base,
            definitions[base.STATIC_MESH_ASSET_PATH],
        ),
        base.SHUTTER_STATIC_MESH_ASSET_PATH: _build_shutter(
            base,
            definitions[base.SHUTTER_STATIC_MESH_ASSET_PATH],
        ),
        base.LEFT_DOOR_STATIC_MESH_ASSET_PATH: _build_door(
            base,
            definitions[base.LEFT_DOOR_STATIC_MESH_ASSET_PATH],
            "left",
        ),
        base.RIGHT_DOOR_STATIC_MESH_ASSET_PATH: _build_door(
            base,
            definitions[base.RIGHT_DOOR_STATIC_MESH_ASSET_PATH],
            "right",
        ),
    }

    static_meshes = {}
    for definition in base.MESH_ASSET_DEFINITIONS:
        static_meshes[definition.asset_path] = _create_or_update_static_mesh(
            base,
            definition,
            builders[definition.asset_path],
            materials,
        )

    _log(
        "{} textures={} materials={} meshes={}".format(
            SUCCESS_MARKER,
            len(textures),
            len(materials),
            len(static_meshes),
        )
    )
    return {
        "textures": textures,
        "materials": materials,
        "static_meshes": static_meshes,
    }


def main():
    return upgrade_main_home_assets()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if unreal is not None and callable(getattr(unreal, "log_error", None)):
            unreal.log_error(traceback.format_exc())
        raise
