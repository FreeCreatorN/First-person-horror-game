"""Create reusable old-town architectural Static Mesh modules.

Run inside Unreal Editor 5.7, or import and call
``ensure_architectural_module_assets()`` from the OldTown scene generator.

The two window meshes are authored in centimetres with their pivot at the
centre of the glazed opening.  Local -Y is the exterior/front direction,
local X is opening width, and local Z is opening height.  The scene generator
can therefore scale X/Z to the requested opening dimensions while leaving the
authored reveal, sill and grille depth unchanged.

Every module is one Static Mesh with five stable material slots:

0. WindowFrame
1. WindowGlass
2. WindowSill
3. WindowBars
4. WindowInterior

The meshes deliberately contain no collision.  Their frame depth, recessed
glass, interior occlusion board and round security grille are visual detail;
the source building shells continue to own gameplay collision.
"""

try:
    import unreal
except ImportError:
    unreal = None

import math


ASSET_ROOT = "/Game/Yastar/OldTownSchoolStreet/Architecture"
WINDOW_ROOT = ASSET_ROOT + "/Windows"
MATERIAL_ROOT = ASSET_ROOT + "/Materials"

MATERIAL_ORDER = (
    "M_OTSArch_WindowFrame",
    "M_OTSArch_WindowGlass",
    "M_OTSArch_WindowSill",
    "M_OTSArch_WindowBars",
    "M_OTSArch_WindowInterior",
)
MATERIAL_ID_BY_NAME = {
    material_name: index
    for index, material_name in enumerate(MATERIAL_ORDER)
}
MATERIAL_SLOT_NAMES = (
    "WindowFrame",
    "WindowGlass",
    "WindowSill",
    "WindowBars",
    "WindowInterior",
)
MATERIAL_SETTINGS = {
    # name: base colour, roughness, metallic
    "M_OTSArch_WindowFrame": ((0.075, 0.100, 0.070, 1.0), 0.84, 0.10),
    "M_OTSArch_WindowGlass": ((0.025, 0.042, 0.048, 1.0), 0.20, 0.04),
    "M_OTSArch_WindowSill": ((0.36, 0.31, 0.25, 1.0), 0.94, 0.00),
    "M_OTSArch_WindowBars": ((0.20, 0.105, 0.055, 1.0), 0.88, 0.58),
    "M_OTSArch_WindowInterior": ((0.018, 0.016, 0.014, 1.0), 0.98, 0.00),
}

MODULE_SPECS = {
    "ResidentialWindow": {
        "asset_name": "SM_OTS_Window_Residential",
        "opening_width_cm": 125.0,
        "opening_height_cm": 120.0,
        "vertical_bar_count": 5,
        "school_sash": False,
    },
    "SchoolWindow": {
        "asset_name": "SM_OTS_Window_School",
        "opening_width_cm": 200.0,
        "opening_height_cm": 150.0,
        "vertical_bar_count": 7,
        "school_sash": True,
    },
}

SUCCESS_MARKER = "OTS_ARCHITECTURAL_MODULES_SUCCESS"


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _require_unreal():
    _require(
        unreal is not None,
        "CreateOldTownArchitecturalModules.py must run inside Unreal Editor",
    )


def _log(message):
    if unreal is not None and callable(getattr(unreal, "log", None)):
        unreal.log("[OldTownArchitecture] {}".format(message))


def _warn(message):
    if unreal is not None and callable(getattr(unreal, "log_warning", None)):
        unreal.log_warning("[OldTownArchitecture] {}".format(message))


def _safe_set(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        return False


def _asset_exists(asset_path):
    return unreal.EditorAssetLibrary.does_asset_exist(asset_path)


def _load_asset(asset_path):
    return (
        unreal.EditorAssetLibrary.load_asset(asset_path)
        if _asset_exists(asset_path)
        else None
    )


def _ensure_directories():
    for directory in (ASSET_ROOT, WINDOW_ROOT, MATERIAL_ROOT):
        unreal.EditorAssetLibrary.make_directory(directory)


def _material_expression(material, expression_type, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        expression_type,
        int(x),
        int(y),
    )
    _require(
        node is not None,
        "Unable to create {}".format(
            getattr(expression_type, "__name__", expression_type)
        ),
    )
    return node


def _expression_description(expression):
    try:
        return expression.get_editor_property("desc") or ""
    except Exception:
        return getattr(expression, "desc", "") or ""


def _material_expressions(material):
    get_all = getattr(
        unreal.MaterialEditingLibrary,
        "get_all_expressions_in_material",
        None,
    )
    if callable(get_all):
        try:
            return list(get_all(material))
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


def _tagged_material_expression(
    material,
    expressions,
    expression_type,
    description,
    x,
    y,
):
    node = next(
        (
            expression
            for expression in expressions
            if isinstance(expression, expression_type)
            and _expression_description(expression) == description
        ),
        None,
    )
    if node is None:
        node = _material_expression(material, expression_type, x, y)
        node.set_editor_property("desc", description)
        expressions.append(node)
    return node


def _connect_property(source, output_name, material_property, description):
    _require(
        unreal.MaterialEditingLibrary.connect_material_property(
            source,
            output_name,
            material_property,
        ),
        "Unable to connect {}".format(description),
    )


def _ensure_material(material_name):
    asset_path = "{}/{}".format(MATERIAL_ROOT, material_name)
    material = _load_asset(asset_path)
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            material_name,
            MATERIAL_ROOT,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
    _require(material is not None, "Unable to create {}".format(asset_path))

    colour, roughness, metallic = MATERIAL_SETTINGS[material_name]
    expressions = _material_expressions(material)
    tag_prefix = "OTS_ARCH_WINDOW:{}".format(material_name)
    colour_node = _tagged_material_expression(
        material,
        expressions,
        unreal.MaterialExpressionConstant3Vector,
        tag_prefix + ":BaseColor",
        -420,
        -80,
    )
    colour_node.set_editor_property("constant", unreal.LinearColor(*colour))
    roughness_node = _tagged_material_expression(
        material,
        expressions,
        unreal.MaterialExpressionConstant,
        tag_prefix + ":Roughness",
        -420,
        90,
    )
    roughness_node.set_editor_property("r", float(roughness))
    metallic_node = _tagged_material_expression(
        material,
        expressions,
        unreal.MaterialExpressionConstant,
        tag_prefix + ":Metallic",
        -420,
        180,
    )
    metallic_node.set_editor_property("r", float(metallic))

    _connect_property(
        colour_node,
        "",
        unreal.MaterialProperty.MP_BASE_COLOR,
        material_name + " Base Color",
    )
    _connect_property(
        roughness_node,
        "",
        unreal.MaterialProperty.MP_ROUGHNESS,
        material_name + " Roughness",
    )
    _connect_property(
        metallic_node,
        "",
        unreal.MaterialProperty.MP_METALLIC,
        material_name + " Metallic",
    )

    unreal.MaterialEditingLibrary.recompile_material(material)
    _require(
        unreal.EditorAssetLibrary.save_loaded_asset(material, False),
        "Unable to save {}".format(asset_path),
    )
    return material


def _ensure_materials():
    return {
        material_name: _ensure_material(material_name)
        for material_name in MATERIAL_ORDER
    }


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
        "Geometry Script material ID support is unavailable"
    )


def _primitive_options(material_id):
    options = unreal.GeometryScriptPrimitiveOptions()
    _safe_set(options, "material_id", int(material_id))
    polygroup_mode = getattr(
        unreal,
        "GeometryScriptPrimitivePolygroupMode",
        None,
    )
    if polygroup_mode is not None:
        _safe_set(options, "polygroup_mode", polygroup_mode.PER_FACE)
    return options


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


class ArchitecturalMeshBuilder:
    """Append material-aware bevelled primitives into one visual mesh."""

    def __init__(self, logical_name):
        self.logical_name = logical_name
        self.mesh = unreal.DynamicMesh()
        _enable_material_ids(self.mesh)

    def _options(self, material_name):
        _require(
            material_name in MATERIAL_ID_BY_NAME,
            "Unknown material {} on {}".format(
                material_name,
                self.logical_name,
            ),
        )
        return _primitive_options(MATERIAL_ID_BY_NAME[material_name])

    def _append_raw_box(
        self,
        target_mesh,
        location,
        size,
        material_name,
        rotation,
    ):
        result = unreal.GeometryScript_Primitives.append_box(
            target_mesh,
            self._options(material_name),
            _make_transform(location, rotation),
            float(size[0]),
            float(size[1]),
            float(size[2]),
            0,
            0,
            0,
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        return _normalise_mesh_result(result, target_mesh, "append_box")

    def box(
        self,
        location,
        size,
        material_name,
        rotation=(0.0, 0.0, 0.0),
        bevel=0.0,
        bevel_subdivisions=2,
    ):
        _require(
            min(float(value) for value in size) > 0.0,
            "{} contains a zero-size box".format(self.logical_name),
        )
        bevel = min(
            max(0.0, float(bevel)),
            float(min(size)) * 0.42,
        )
        if bevel <= 0.0:
            self.mesh = self._append_raw_box(
                self.mesh,
                location,
                size,
                material_name,
                rotation,
            )
            return self

        temporary_mesh = unreal.DynamicMesh()
        _enable_material_ids(temporary_mesh)
        temporary_mesh = self._append_raw_box(
            temporary_mesh,
            location,
            size,
            material_name,
            rotation,
        )
        try:
            bevel_options = unreal.GeometryScriptMeshBevelOptions()
            bevel_options.set_editor_property("bevel_distance", bevel)
            bevel_options.set_editor_property("infer_material_id", True)
            bevel_options.set_editor_property(
                "set_material_id",
                MATERIAL_ID_BY_NAME[material_name],
            )
            bevel_options.set_editor_property(
                "subdivisions",
                max(0, int(bevel_subdivisions)),
            )
            bevel_options.set_editor_property("round_weight", 0.72)
            result = (
                unreal.GeometryScript_MeshModeling.apply_mesh_polygroup_bevel(
                    temporary_mesh,
                    bevel_options,
                )
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
                "{} bevel skipped for {}: {}".format(
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
                rotation,
            )
        return self

    def cylinder(
        self,
        location,
        radius,
        height,
        material_name,
        rotation=(0.0, 0.0, 0.0),
        radial_steps=16,
    ):
        result = unreal.GeometryScript_Primitives.append_cylinder(
            self.mesh,
            self._options(material_name),
            _make_transform(location, rotation),
            float(radius),
            float(height),
            int(radial_steps),
            1,
            True,
            unreal.GeometryScriptPrimitiveOriginMode.CENTER,
        )
        self.mesh = _normalise_mesh_result(
            result,
            self.mesh,
            "append_cylinder",
        )
        return self

    def cylinder_between(
        self,
        start,
        end,
        radius,
        material_name,
        radial_steps=16,
    ):
        start = tuple(float(value) for value in start)
        end = tuple(float(value) for value in end)
        direction = tuple(
            end[index] - start[index]
            for index in range(3)
        )
        length = math.sqrt(sum(value * value for value in direction))
        _require(
            length > 0.001,
            "{} contains a zero-length cylinder".format(self.logical_name),
        )
        midpoint = tuple(
            (start[index] + end[index]) * 0.5
            for index in range(3)
        )
        unit_z = max(-1.0, min(1.0, direction[2] / length))
        # Geometry Script cylinders use local +Z; negative Pitch aligns that
        # axis with the requested horizontal direction in Unreal coordinates.
        pitch = -math.degrees(math.acos(unit_z))
        yaw = math.degrees(math.atan2(direction[1], direction[0]))
        return self.cylinder(
            midpoint,
            radius,
            length,
            material_name,
            (pitch, yaw, 0.0),
            radial_steps,
        )


def _build_old_window(logical_name, spec):
    builder = ArchitecturalMeshBuilder(logical_name)
    frame = "M_OTSArch_WindowFrame"
    glass = "M_OTSArch_WindowGlass"
    sill = "M_OTSArch_WindowSill"
    bars = "M_OTSArch_WindowBars"
    interior = "M_OTSArch_WindowInterior"

    width = float(spec["opening_width_cm"])
    height = float(spec["opening_height_cm"])
    half_width = width * 0.5
    half_height = height * 0.5

    # The interior board and glass are physically separated.  From the street
    # the board blocks the source building wall, while the 0.55 cm recess
    # between it and the glass produces a stable dark window cavity.
    builder.box(
        (0.0, -0.40, 0.0),
        (width - 8.0, 0.50, height - 8.0),
        interior,
        bevel=0.10,
    )
    builder.box(
        (0.0, -1.15, 0.0),
        (width - 11.0, 0.40, height - 11.0),
        glass,
        bevel=0.10,
    )

    # Four reveal strips bridge the wall plane to the proud outer frame.  They
    # keep oblique views from exposing a paper-thin floating window.
    for x in (-half_width - 1.5, half_width + 1.5):
        builder.box(
            (x, -2.25, 0.0),
            (5.0, 4.5, height + 9.0),
            sill,
            bevel=0.45,
        )
    for z in (-half_height - 1.5, half_height + 1.5):
        builder.box(
            (0.0, -2.25, z),
            (width + 8.0, 4.5, 5.0),
            sill,
            bevel=0.45,
        )

    # Bevelled perimeter frame, with the sash set slightly behind it.
    for x in (-half_width, half_width):
        builder.box(
            (x, -4.25, 0.0),
            (7.0, 4.5, height + 14.0),
            frame,
            bevel=0.70,
            bevel_subdivisions=2,
        )
    for z in (-half_height, half_height):
        builder.box(
            (0.0, -4.25, z),
            (width + 14.0, 4.5, 7.0),
            frame,
            bevel=0.70,
            bevel_subdivisions=2,
        )

    sash_y = -4.65
    if bool(spec["school_sash"]):
        for x in (-width / 6.0, width / 6.0):
            builder.box(
                (x, sash_y, 0.0),
                (4.0, 2.4, height - 7.0),
                frame,
                bevel=0.42,
            )
    else:
        builder.box(
            (0.0, sash_y, 0.0),
            (4.5, 2.4, height - 7.0),
            frame,
            bevel=0.42,
        )
    builder.box(
        (0.0, sash_y, 0.0),
        (width - 7.0, 2.4, 4.5),
        frame,
        bevel=0.42,
    )

    # A real projecting sill has a shallow outward fall and a separate drip
    # edge.  Its depth is not scaled by the scene, so every instance remains a
    # credible 14 cm projection instead of becoming a giant slab.
    sill_z = -half_height - 7.0
    builder.box(
        (0.0, -6.75, sill_z),
        (width + 24.0, 14.0, 5.0),
        sill,
        rotation=(0.0, 0.0, -3.5),
        bevel=0.85,
        bevel_subdivisions=2,
    )
    builder.box(
        (0.0, -13.15, sill_z - 2.0),
        (width + 18.0, 1.2, 1.4),
        frame,
        bevel=0.25,
    )

    # Round anti-theft bars and connected wall stand-offs replace the previous
    # 4 x 5 cm rectangular grille actors.
    grille_y = -12.0
    vertical_count = int(spec["vertical_bar_count"])
    for index in range(vertical_count):
        alpha = (
            0.5
            if vertical_count == 1
            else float(index) / float(vertical_count - 1)
        )
        x = -width * 0.42 + alpha * width * 0.84
        builder.cylinder_between(
            (x, grille_y, -half_height - 2.0),
            (x, grille_y, half_height + 2.0),
            1.45,
            bars,
            radial_steps=14,
        )
    for z in (-height * 0.28, height * 0.28):
        builder.cylinder_between(
            (-half_width - 5.0, grille_y, z),
            (half_width + 5.0, grille_y, z),
            1.55,
            bars,
            radial_steps=14,
        )

    for x in (-half_width + 5.0, half_width - 5.0):
        for z in (-half_height + 10.0, half_height - 10.0):
            builder.box(
                (x, -6.55, z),
                (7.0, 1.2, 7.0),
                bars,
                bevel=0.55,
            )
            builder.cylinder_between(
                (x, -6.7, z),
                (x, grille_y, z),
                1.65,
                bars,
                radial_steps=14,
            )
            builder.cylinder(
                (x, -6.0, z),
                1.15,
                1.0,
                bars,
                rotation=(0.0, 0.0, 90.0),
                radial_steps=12,
            )
    return builder


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
        _require(
            outcome == success_pin.SUCCESS,
            "{} failed: {}".format(operation_name, outcome),
        )
    _require(asset is not None, "{} returned no asset".format(operation_name))
    return asset


def _copy_mesh_to_asset(builder, static_mesh, materials):
    options = unreal.GeometryScriptCopyMeshToAssetOptions()
    options.set_editor_property("enable_recompute_normals", True)
    options.set_editor_property("enable_recompute_tangents", True)
    options.set_editor_property("replace_materials", True)
    options.set_editor_property(
        "new_materials",
        [materials[name] for name in MATERIAL_ORDER],
    )
    options.set_editor_property(
        "new_material_slot_names",
        [unreal.Name(name) for name in MATERIAL_SLOT_NAMES],
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


def _clear_collision(static_mesh):
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


def _create_or_update_module(logical_name, spec, builder, materials):
    asset_path = "{}/{}".format(WINDOW_ROOT, spec["asset_name"])
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

    _require(
        isinstance(static_mesh, unreal.StaticMesh),
        "{} is not a StaticMesh".format(asset_path),
    )
    _copy_mesh_to_asset(builder, static_mesh, materials)
    _clear_collision(static_mesh)
    _safe_set(static_mesh, "light_map_resolution", 64)
    _safe_set(static_mesh, "allow_cpu_access", False)
    _require(
        unreal.EditorAssetLibrary.save_loaded_asset(static_mesh, False),
        "Unable to save {}".format(asset_path),
    )
    _log("Prepared {} at {}".format(logical_name, asset_path))
    return static_mesh


def ensure_architectural_module_assets():
    """Create/update and return the residential and school window assets."""

    _require_unreal()
    _ensure_directories()
    materials = _ensure_materials()
    assets = {}
    for logical_name, spec in MODULE_SPECS.items():
        builder = _build_old_window(logical_name, spec)
        assets[logical_name] = _create_or_update_module(
            logical_name,
            spec,
            builder,
            materials,
        )
    _require(
        set(assets) == set(MODULE_SPECS),
        "Architectural module library is incomplete",
    )
    unreal.EditorAssetLibrary.save_directory(ASSET_ROOT, True, True)
    _log(
        "{} count={} root={}".format(
            SUCCESS_MARKER,
            len(assets),
            ASSET_ROOT,
        )
    )
    return assets


if __name__ == "__main__":
    ensure_architectural_module_assets()
