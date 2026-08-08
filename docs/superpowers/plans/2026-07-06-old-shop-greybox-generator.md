# Old Shop Greybox Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one self-contained UE5 Python script that creates an idempotent, material-colored, 31-part old-city storefront greybox in the current editor level.

**Architecture:** Keep all dimensions, colors, paths, and generation behavior in `Scripts/CreateOldShopGreybox.py`. Represent every Cube as immutable plain-Python data, validate the full envelope before touching the level, then use UE5.7 editor APIs to create/update materials, remove previously tagged actors, and spawn the replacement actors. Use dependency injection only at the UE boundary so the geometry and editor workflow can be tested outside Unreal without changing runtime behavior.

**Tech Stack:** Python 3, standard-library `dataclasses` and `unittest`, Unreal Engine 5.7 Python API, `EditorActorSubsystem`, `MaterialEditingLibrary`, `EditorAssetLibrary`, and `AssetToolsHelpers`.

## Global Constraints

- UE unit is exactly `1 cm`; Engine Cube is exactly `100 × 100 × 100 cm`.
- Overall default envelope is exactly X `-250…250`, Y `-400…400`, Z `1…401 cm`.
- Front faces `-Y`; width is X, depth is Y, and height is Z.
- Default overall size is exactly `500 × 800 × 400 cm`.
- Use only `/Engine/BasicShapes/Cube.Cube`; no Blender, external models, textures, external plugins, or curved geometry.
- Spawn multiple `StaticMeshActor` instances in the current level and assign Folder and Actor Tag `OldShop_500x800x400`.
- Re-running removes only actors carrying the exact generator tag, then creates one replacement set.
- Create or update exactly `M_OldWall`, `M_DarkWall`, `M_Shutter`, `M_Sign`, `M_DarkGlass`, `M_Trim`, and `M_Stain`.
- Save material assets under `/Game/OldShop_500x800x400/Materials`; do not save the current level.
- Preserve all unrelated user files and existing uncommitted assets.

## File Map

- Create `Scripts/CreateOldShopGreybox.py`
  - Owns editable parameters, part descriptions, bounds validation, material creation, actor cleanup, actor spawning, logging, and direct execution.
- Create `Tests/test_create_old_shop_greybox.py`
  - Owns plain-Python geometry tests and fake-Unreal integration tests; it never launches or edits an Unreal level.

---

### Task 1: Geometry specification and hard envelope validation

**Files:**
- Create: `Scripts/CreateOldShopGreybox.py`
- Create: `Tests/test_create_old_shop_greybox.py`

**Interfaces:**
- Produces: `PartSpec`, `build_part_specs(...) -> list[PartSpec]`, `part_bounds(part)`, `overall_bounds(parts)`, and `validate_part_specs(parts, envelope)`.
- Consumes: No earlier task interfaces.

- [ ] **Step 1: Write the failing geometry tests**

Create `Tests/test_create_old_shop_greybox.py` with:

```python
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "Scripts"
    / "CreateOldShopGreybox.py"
)


def load_generator():
    spec = importlib.util.spec_from_file_location("old_shop_generator", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def test_default_layout_has_31_unique_named_parts(self):
        parts = self.generator.build_part_specs()
        labels = [part.label for part in parts]

        self.assertEqual(31, len(parts))
        self.assertEqual(31, len(set(labels)))
        self.assertEqual(15, sum("_Slat_" in label for label in labels))

    def test_main_cube_uses_requested_cm_dimensions_and_scale(self):
        parts = self.generator.build_part_specs()
        main = next(part for part in parts if part.label == "SM_OldShop_MainBlock")

        self.assertEqual((500.0, 780.0, 400.0), main.size_cm)
        self.assertEqual((0.0, 10.0, 201.0), main.location_cm)
        self.assertEqual((5.0, 7.8, 4.0), main.scale)

    def test_default_layout_fills_but_never_exceeds_hard_envelope(self):
        parts = self.generator.build_part_specs()
        envelope = self.generator.expected_envelope()

        self.generator.validate_part_specs(parts, envelope)
        self.assertEqual(
            ((-250.0, 250.0), (-400.0, 400.0), (1.0, 401.0)),
            self.generator.overall_bounds(parts),
        )

    def test_overall_parameters_scale_every_part_and_keep_base_z(self):
        parts = self.generator.build_part_specs(
            width_cm=1000.0,
            depth_cm=400.0,
            height_cm=200.0,
            origin_x_cm=50.0,
            origin_y_cm=-25.0,
            base_z_cm=11.0,
        )
        bounds = self.generator.overall_bounds(parts)

        self.assertEqual(
            ((-450.0, 550.0), (-225.0, 175.0), (11.0, 211.0)),
            bounds,
        )

    def test_duplicate_label_is_rejected_before_editor_work(self):
        parts = self.generator.build_part_specs()
        duplicate = list(parts) + [parts[0]]

        with self.assertRaisesRegex(ValueError, "Duplicate Actor Label"):
            self.generator.validate_part_specs(
                duplicate,
                self.generator.expected_envelope(),
            )

    def test_out_of_bounds_part_reports_label_and_axis(self):
        parts = self.generator.build_part_specs()
        bad_part = self.generator.PartSpec(
            label="SM_OldShop_Bad",
            location_cm=(251.0, 0.0, 100.0),
            size_cm=(2.0, 2.0, 2.0),
            material_name="M_Trim",
        )

        with self.assertRaisesRegex(
            ValueError,
            r"SM_OldShop_Bad.*X.*250",
        ):
            self.generator.validate_part_specs(
                parts + [bad_part],
                self.generator.expected_envelope(),
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the expected RED state**

Run:

```powershell
python -m unittest Tests.test_create_old_shop_greybox -v
```

Expected: FAIL during `setUpClass` with `FileNotFoundError` for
`Scripts/CreateOldShopGreybox.py`.

- [ ] **Step 3: Implement the pure geometry layer**

Create `Scripts/CreateOldShopGreybox.py` with:

```python
"""Generate an old-city street shop greybox in the current UE5 level.

Default envelope: 500 cm wide × 800 cm deep × 400 cm high.
Front direction: -Y. Bottom plane: Z=1 cm.

The three overall dimensions and world placement are the first editable
parameters below. Every detail scales with those overall dimensions.
"""

from dataclasses import dataclass

try:
    import unreal
except ImportError:
    unreal = None


# ---------------------------------------------------------------------------
# Editable overall dimensions and placement, all in UE centimeters.
# ---------------------------------------------------------------------------
SHOP_WIDTH_CM = 500.0
SHOP_DEPTH_CM = 800.0
SHOP_HEIGHT_CM = 400.0
ORIGIN_X_CM = 0.0
ORIGIN_Y_CM = 0.0
BASE_Z_CM = 1.0

FOLDER_NAME = "OldShop_500x800x400"
GENERATOR_TAG = "OldShop_500x800x400"
CUBE_ASSET_PATH = "/Engine/BasicShapes/Cube.Cube"
MATERIAL_FOLDER = "/Game/OldShop_500x800x400/Materials"

BASE_WIDTH_CM = 500.0
BASE_DEPTH_CM = 800.0
BASE_HEIGHT_CM = 400.0
EPSILON = 1.0e-6

MATERIAL_COLORS = {
    "M_OldWall": (0.36, 0.31, 0.22, 1.0),
    "M_DarkWall": (0.18, 0.16, 0.13, 1.0),
    "M_Shutter": (0.22, 0.24, 0.23, 1.0),
    "M_Sign": (0.32, 0.055, 0.04, 1.0),
    "M_DarkGlass": (0.012, 0.020, 0.026, 1.0),
    "M_Trim": (0.045, 0.045, 0.040, 1.0),
    "M_Stain": (0.13, 0.105, 0.065, 1.0),
}


@dataclass(frozen=True)
class PartSpec:
    label: str
    location_cm: tuple
    size_cm: tuple
    material_name: str

    @property
    def scale(self):
        return tuple(value / 100.0 for value in self.size_cm)


def build_part_specs(
    width_cm=SHOP_WIDTH_CM,
    depth_cm=SHOP_DEPTH_CM,
    height_cm=SHOP_HEIGHT_CM,
    origin_x_cm=ORIGIN_X_CM,
    origin_y_cm=ORIGIN_Y_CM,
    base_z_cm=BASE_Z_CM,
):
    if min(width_cm, depth_cm, height_cm) <= 0.0:
        raise ValueError("Shop width, depth, and height must all be positive.")

    sx = width_cm / BASE_WIDTH_CM
    sy = depth_cm / BASE_DEPTH_CM
    sz = height_cm / BASE_HEIGHT_CM
    parts = []

    def add(label, base_location, base_size, material_name):
        location = (
            origin_x_cm + base_location[0] * sx,
            origin_y_cm + base_location[1] * sy,
            base_z_cm + base_location[2] * sz,
        )
        size = (
            base_size[0] * sx,
            base_size[1] * sy,
            base_size[2] * sz,
        )
        parts.append(PartSpec(label, location, size, material_name))

    add(
        "SM_OldShop_MainBlock",
        (0.0, 10.0, 200.0),
        (500.0, 780.0, 400.0),
        "M_OldWall",
    )
    add(
        "SM_OldShop_Storefront",
        (0.0, -384.0, 185.0),
        (480.0, 8.0, 370.0),
        "M_DarkWall",
    )
    add(
        "SM_OldShop_Shutter",
        (-100.0, -390.0, 140.0),
        (240.0, 4.0, 240.0),
        "M_Shutter",
    )
    for index in range(15):
        add(
            f"SM_OldShop_Shutter_Slat_{index + 1:02d}",
            (-100.0, -393.5, 29.0 + index * 15.0),
            (232.0, 3.0, 4.0),
            "M_Trim",
        )
    add(
        "SM_OldShop_Door",
        (155.0, -390.0, 117.5),
        (110.0, 4.0, 235.0),
        "M_DarkWall",
    )
    add(
        "SM_OldShop_DoorFrame_Left",
        (96.0, -392.0, 121.5),
        (8.0, 8.0, 243.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_DoorFrame_Right",
        (214.0, -392.0, 121.5),
        (8.0, 8.0, 243.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_DoorFrame_Top",
        (155.0, -392.0, 239.0),
        (126.0, 8.0, 8.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Sign",
        (0.0, -395.0, 325.5),
        (430.0, 10.0, 65.0),
        "M_Sign",
    )
    add(
        "SM_OldShop_WindowGlass",
        (56.0, -390.0, 140.0),
        (50.0, 4.0, 90.0),
        "M_DarkGlass",
    )
    add(
        "SM_OldShop_WindowFrame_Left",
        (28.0, -392.0, 140.0),
        (6.0, 8.0, 102.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_WindowFrame_Right",
        (84.0, -392.0, 140.0),
        (6.0, 8.0, 102.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_WindowFrame_Top",
        (56.0, -392.0, 188.0),
        (62.0, 8.0, 6.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_WindowFrame_Bottom",
        (56.0, -392.0, 92.0),
        (62.0, 8.0, 6.0),
        "M_Trim",
    )
    add(
        "SM_OldShop_Stain_01",
        (-230.0, -389.0, 159.0),
        (16.0, 2.0, 120.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_Stain_02",
        (229.0, -389.0, 169.0),
        (16.0, 2.0, 140.0),
        "M_Stain",
    )
    add(
        "SM_OldShop_Stain_03",
        (135.0, -389.0, 276.0),
        (120.0, 2.0, 22.0),
        "M_Stain",
    )
    return parts


def part_bounds(part):
    return tuple(
        (
            part.location_cm[axis] - part.size_cm[axis] * 0.5,
            part.location_cm[axis] + part.size_cm[axis] * 0.5,
        )
        for axis in range(3)
    )


def overall_bounds(parts):
    if not parts:
        raise ValueError("At least one PartSpec is required.")
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
    return (
        (origin_x_cm - width_cm * 0.5, origin_x_cm + width_cm * 0.5),
        (origin_y_cm - depth_cm * 0.5, origin_y_cm + depth_cm * 0.5),
        (base_z_cm, base_z_cm + height_cm),
    )


def validate_part_specs(parts, envelope):
    labels = [part.label for part in parts]
    duplicate_labels = sorted(
        label for label in set(labels) if labels.count(label) > 1
    )
    if duplicate_labels:
        raise ValueError(
            "Duplicate Actor Label(s): " + ", ".join(duplicate_labels)
        )

    axis_names = ("X", "Y", "Z")
    for part in parts:
        for axis, (minimum, maximum) in enumerate(part_bounds(part)):
            allowed_minimum, allowed_maximum = envelope[axis]
            if (
                minimum < allowed_minimum - EPSILON
                or maximum > allowed_maximum + EPSILON
            ):
                raise ValueError(
                    f"{part.label} exceeds {axis_names[axis]} envelope "
                    f"[{allowed_minimum}, {allowed_maximum}] with "
                    f"[{minimum}, {maximum}]."
                )
    return True
```

- [ ] **Step 4: Run the geometry tests and verify GREEN**

Run:

```powershell
python -m unittest Tests.test_create_old_shop_greybox.GeometryTests -v
```

Expected: 6 tests run and all report `ok`.

- [ ] **Step 5: Commit the geometry layer**

```powershell
git add Scripts/CreateOldShopGreybox.py Tests/test_create_old_shop_greybox.py
git commit -m "feat: define old shop greybox geometry"
```

Expected: one commit containing only the script and its test file. If Git metadata
write permission is unavailable, record that limitation and continue without
staging unrelated files.

---

### Task 2: Material creation and update behavior

**Files:**
- Modify: `Scripts/CreateOldShopGreybox.py`
- Modify: `Tests/test_create_old_shop_greybox.py`

**Interfaces:**
- Consumes: `MATERIAL_COLORS` and `MATERIAL_FOLDER` from Task 1.
- Produces: `ensure_material(material_name, color, unreal_api=None) -> unreal.Material`.

- [ ] **Step 1: Add failing material tests**

Add these imports and test doubles after the existing imports in
`Tests/test_create_old_shop_greybox.py`:

```python
from types import SimpleNamespace


class FakeMaterial:
    def __init__(self, name):
        self.name = name


class FakeMaterialNode:
    def __init__(self):
        self.properties = {}

    def set_editor_property(self, name, value):
        self.properties[name] = value


class FakeMaterialEditingLibrary:
    deleted = []
    created_nodes = []
    connections = []
    recompiled = []

    @classmethod
    def reset(cls):
        cls.deleted = []
        cls.created_nodes = []
        cls.connections = []
        cls.recompiled = []

    @classmethod
    def delete_all_material_expressions(cls, material):
        cls.deleted.append(material)

    @classmethod
    def create_material_expression(
        cls,
        material,
        expression_class,
        node_pos_x,
        node_pos_y,
    ):
        node = FakeMaterialNode()
        cls.created_nodes.append(
            (material, expression_class, node_pos_x, node_pos_y, node)
        )
        return node

    @classmethod
    def connect_material_property(cls, node, output_name, property_name):
        cls.connections.append((node, output_name, property_name))
        return True

    @classmethod
    def recompile_material(cls, material):
        cls.recompiled.append(material)


class FakeEditorAssetLibrary:
    assets = {}
    saved = []

    @classmethod
    def reset(cls):
        cls.assets = {}
        cls.saved = []

    @classmethod
    def load_asset(cls, path):
        return cls.assets.get(path)

    @classmethod
    def save_loaded_asset(cls, asset, only_if_is_dirty):
        cls.saved.append((asset, only_if_is_dirty))
        return True


class FakeAssetTools:
    def __init__(self):
        self.created = []

    def create_asset(self, name, package_path, asset_class, factory):
        material = FakeMaterial(name)
        FakeEditorAssetLibrary.assets[f"{package_path}/{name}"] = material
        self.created.append((name, package_path, asset_class, factory, material))
        return material


class FakeAssetToolsHelpers:
    tools = FakeAssetTools()

    @classmethod
    def get_asset_tools(cls):
        return cls.tools


class FakeLinearColor(tuple):
    def __new__(cls, red, green, blue, alpha):
        return tuple.__new__(cls, (red, green, blue, alpha))


def make_material_unreal():
    FakeMaterialEditingLibrary.reset()
    FakeEditorAssetLibrary.reset()
    FakeAssetToolsHelpers.tools = FakeAssetTools()
    return SimpleNamespace(
        EditorAssetLibrary=FakeEditorAssetLibrary,
        AssetToolsHelpers=FakeAssetToolsHelpers,
        Material=FakeMaterial,
        MaterialFactoryNew=type("FakeMaterialFactoryNew", (), {}),
        MaterialExpressionConstant3Vector=type(
            "FakeMaterialExpressionConstant3Vector",
            (),
            {},
        ),
        MaterialEditingLibrary=FakeMaterialEditingLibrary,
        MaterialProperty=SimpleNamespace(MP_BASE_COLOR="MP_BASE_COLOR"),
        LinearColor=FakeLinearColor,
    )
```

Add this test class before the file's `if __name__ == "__main__"` block:

```python
class MaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def test_missing_material_is_created_colored_connected_and_saved(self):
        fake_unreal = make_material_unreal()
        color = (0.1, 0.2, 0.3, 1.0)

        material = self.generator.ensure_material(
            "M_Test",
            color,
            fake_unreal,
        )

        self.assertEqual("M_Test", material.name)
        self.assertEqual(1, len(FakeAssetToolsHelpers.tools.created))
        node = FakeMaterialEditingLibrary.created_nodes[0][4]
        self.assertEqual(color, node.properties["constant"])
        self.assertEqual(
            [(node, "", "MP_BASE_COLOR")],
            FakeMaterialEditingLibrary.connections,
        )
        self.assertEqual([material], FakeMaterialEditingLibrary.recompiled)
        self.assertEqual([(material, False)], FakeEditorAssetLibrary.saved)

    def test_existing_material_is_updated_without_duplicate_asset(self):
        fake_unreal = make_material_unreal()
        existing = FakeMaterial("M_Test")
        path = f"{self.generator.MATERIAL_FOLDER}/M_Test"
        FakeEditorAssetLibrary.assets[path] = existing

        result = self.generator.ensure_material(
            "M_Test",
            (0.4, 0.3, 0.2, 1.0),
            fake_unreal,
        )

        self.assertIs(existing, result)
        self.assertEqual([], FakeAssetToolsHelpers.tools.created)
        self.assertEqual([existing], FakeMaterialEditingLibrary.deleted)

    def test_material_connection_failure_is_reported(self):
        fake_unreal = make_material_unreal()
        original = FakeMaterialEditingLibrary.connect_material_property
        FakeMaterialEditingLibrary.connect_material_property = classmethod(
            lambda cls, node, output_name, property_name: False
        )
        try:
            with self.assertRaisesRegex(RuntimeError, "Base Color"):
                self.generator.ensure_material(
                    "M_Broken",
                    (0.1, 0.1, 0.1, 1.0),
                    fake_unreal,
                )
        finally:
            FakeMaterialEditingLibrary.connect_material_property = original
```

- [ ] **Step 2: Run material tests and verify RED**

Run:

```powershell
python -m unittest Tests.test_create_old_shop_greybox.MaterialTests -v
```

Expected: 3 tests error with `AttributeError` because
`ensure_material` does not exist.

- [ ] **Step 3: Implement exact material creation/update behavior**

Append this function to `Scripts/CreateOldShopGreybox.py`:

```python
def ensure_material(material_name, color, unreal_api=None):
    api = unreal_api if unreal_api is not None else unreal
    if api is None:
        raise RuntimeError(
            "Unreal Python API is unavailable. Run this script inside "
            "Unreal Editor with Python Editor Script Plugin enabled."
        )

    asset_path = f"{MATERIAL_FOLDER}/{material_name}"
    material = api.EditorAssetLibrary.load_asset(asset_path)
    if material is None:
        material = api.AssetToolsHelpers.get_asset_tools().create_asset(
            material_name,
            MATERIAL_FOLDER,
            api.Material,
            api.MaterialFactoryNew(),
        )
    if material is None:
        raise RuntimeError(f"Could not create material: {asset_path}")

    editing = api.MaterialEditingLibrary
    editing.delete_all_material_expressions(material)
    color_node = editing.create_material_expression(
        material,
        api.MaterialExpressionConstant3Vector,
        -300,
        0,
    )
    if color_node is None:
        raise RuntimeError(
            f"Could not create Constant3Vector for {asset_path}"
        )
    color_node.set_editor_property("constant", api.LinearColor(*color))

    if not editing.connect_material_property(
        color_node,
        "",
        api.MaterialProperty.MP_BASE_COLOR,
    ):
        raise RuntimeError(
            f"Could not connect Base Color for {asset_path}"
        )

    editing.recompile_material(material)
    if not api.EditorAssetLibrary.save_loaded_asset(material, False):
        raise RuntimeError(f"Could not save material: {asset_path}")
    return material
```

- [ ] **Step 4: Run all tests and verify GREEN**

Run:

```powershell
python -m unittest Tests.test_create_old_shop_greybox -v
```

Expected: 9 tests run and all report `ok`.

- [ ] **Step 5: Commit material behavior**

```powershell
git add Scripts/CreateOldShopGreybox.py Tests/test_create_old_shop_greybox.py
git commit -m "feat: create old shop base color materials"
```

Expected: one commit containing only Task 2 changes, or a recorded Git permission
limitation without disturbing unrelated user changes.

---

### Task 3: Idempotent current-level actor generation

**Files:**
- Modify: `Scripts/CreateOldShopGreybox.py`
- Modify: `Tests/test_create_old_shop_greybox.py`

**Interfaces:**
- Consumes: `build_part_specs`, `expected_envelope`, `validate_part_specs`,
  `overall_bounds`, `ensure_material`, `MATERIAL_COLORS`.
- Produces:
  `generate_old_shop(unreal_api=None, material_builder=None) -> tuple[int, list]`
  and `main()`.

- [ ] **Step 1: Add failing fake-editor tests**

Add these editor test doubles after the material doubles in
`Tests/test_create_old_shop_greybox.py`:

```python
class FakeVector(tuple):
    def __new__(cls, x=0.0, y=0.0, z=0.0):
        return tuple.__new__(cls, (x, y, z))


class FakeRotator(tuple):
    def __new__(cls, pitch=0.0, yaw=0.0, roll=0.0):
        return tuple.__new__(cls, (pitch, yaw, roll))


class FakeStaticMeshComponent:
    def __init__(self):
        self.mesh = None
        self.materials = {}
        self.properties = {}

    def set_static_mesh(self, mesh):
        self.mesh = mesh
        return True

    def set_material(self, index, material):
        self.materials[index] = material

    def set_editor_property(self, name, value):
        self.properties[name] = value


class FakeActor:
    def __init__(self, label="Actor", tags=None, location=None):
        self.label = label
        self.tags = list(tags or [])
        self.location = location
        self.rotation = None
        self.scale = None
        self.folder = None
        self.component = FakeStaticMeshComponent()

    def actor_has_tag(self, tag):
        return tag in self.tags

    def set_actor_label(self, label):
        self.label = label

    def set_folder_path(self, folder):
        self.folder = folder

    def set_editor_property(self, name, value):
        if name == "tags":
            self.tags = list(value)
        else:
            setattr(self, name, value)

    def set_actor_scale3d(self, scale):
        self.scale = scale

    def get_component_by_class(self, component_class):
        return self.component


class FakeActorSubsystem:
    def __init__(self, actors=None):
        self.actors = list(actors or [])
        self.destroyed = []
        self.spawned = []
        self.fail_after = None

    def get_all_level_actors(self):
        return list(self.actors)

    def destroy_actors(self, actors):
        for actor in actors:
            if actor in self.actors:
                self.actors.remove(actor)
                self.destroyed.append(actor)
        return True

    def destroy_actor(self, actor):
        return self.destroy_actors([actor])

    def spawn_actor_from_class(
        self,
        actor_class,
        location,
        rotation,
        transient,
    ):
        if self.fail_after is not None and len(self.spawned) >= self.fail_after:
            return None
        actor = FakeActor(location=location)
        actor.rotation = rotation
        self.actors.append(actor)
        self.spawned.append(actor)
        return actor

    def set_selected_level_actors(self, actors):
        self.selected = list(actors)


class FakeTransaction:
    def __init__(self, description):
        self.description = description

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def make_editor_unreal(subsystem):
    logs = []
    errors = []
    cube = object()
    api = SimpleNamespace(
        Name=lambda value: value,
        Vector=FakeVector,
        Rotator=FakeRotator,
        StaticMeshActor=type("FakeStaticMeshActor", (), {}),
        StaticMeshComponent=FakeStaticMeshComponent,
        ComponentMobility=SimpleNamespace(STATIC="STATIC"),
        EditorActorSubsystem=type("FakeEditorActorSubsystem", (), {}),
        ScopedEditorTransaction=FakeTransaction,
        load_asset=lambda path: cube,
        get_editor_subsystem=lambda subsystem_class: subsystem,
        log=logs.append,
        log_error=errors.append,
    )
    api._cube = cube
    api._logs = logs
    api._errors = errors
    return api
```

Add this test class before the file's execution block:

```python
class EditorGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def test_generate_replaces_only_tagged_actors_and_spawns_31_parts(self):
        old = FakeActor(tags=["OldShop_500x800x400"])
        unrelated = FakeActor(label="KeepMe", tags=["Other"])
        subsystem = FakeActorSubsystem([old, unrelated])
        fake_unreal = make_editor_unreal(subsystem)

        deleted, spawned = self.generator.generate_old_shop(
            fake_unreal,
            material_builder=lambda name, color, api: f"Material:{name}",
        )

        self.assertEqual(1, deleted)
        self.assertEqual(31, len(spawned))
        self.assertIn(unrelated, subsystem.actors)
        self.assertNotIn(old, subsystem.actors)
        self.assertEqual(
            31,
            sum(
                actor.actor_has_tag("OldShop_500x800x400")
                for actor in subsystem.actors
            ),
        )
        self.assertEqual(31, len({actor.label for actor in spawned}))
        self.assertTrue(
            all(
                actor.folder == "OldShop_500x800x400"
                for actor in spawned
            )
        )

        main = next(
            actor
            for actor in spawned
            if actor.label == "SM_OldShop_MainBlock"
        )
        self.assertEqual((0.0, 10.0, 201.0), main.location)
        self.assertEqual((5.0, 7.8, 4.0), main.scale)
        self.assertIs(fake_unreal._cube, main.component.mesh)
        self.assertEqual(
            "Material:M_OldWall",
            main.component.materials[0],
        )
        self.assertEqual("STATIC", main.component.properties["mobility"])

    def test_second_run_keeps_one_complete_generator_set(self):
        subsystem = FakeActorSubsystem()
        fake_unreal = make_editor_unreal(subsystem)
        material_builder = lambda name, color, api: f"Material:{name}"

        first_deleted, first_spawned = self.generator.generate_old_shop(
            fake_unreal,
            material_builder,
        )
        second_deleted, second_spawned = self.generator.generate_old_shop(
            fake_unreal,
            material_builder,
        )

        self.assertEqual(0, first_deleted)
        self.assertEqual(31, len(first_spawned))
        self.assertEqual(31, second_deleted)
        self.assertEqual(31, len(second_spawned))
        self.assertEqual(31, len(subsystem.actors))

    def test_spawn_failure_removes_partial_new_set_and_reports_actor(self):
        subsystem = FakeActorSubsystem()
        subsystem.fail_after = 2
        fake_unreal = make_editor_unreal(subsystem)

        with self.assertRaisesRegex(
            RuntimeError,
            "SM_OldShop_Shutter",
        ):
            self.generator.generate_old_shop(
                fake_unreal,
                material_builder=lambda name, color, api: f"Material:{name}",
            )

        self.assertEqual([], subsystem.actors)

    def test_missing_cube_stops_before_material_or_level_changes(self):
        old = FakeActor(tags=["OldShop_500x800x400"])
        subsystem = FakeActorSubsystem([old])
        fake_unreal = make_editor_unreal(subsystem)
        fake_unreal.load_asset = lambda path: None
        material_calls = []

        with self.assertRaisesRegex(RuntimeError, "Cube"):
            self.generator.generate_old_shop(
                fake_unreal,
                material_builder=lambda *args: material_calls.append(args),
            )

        self.assertEqual([], material_calls)
        self.assertEqual([old], subsystem.actors)
```

- [ ] **Step 2: Run editor generation tests and verify RED**

Run:

```powershell
python -m unittest Tests.test_create_old_shop_greybox.EditorGenerationTests -v
```

Expected: 4 tests error with `AttributeError` because
`generate_old_shop` does not exist.

- [ ] **Step 3: Implement current-level cleanup, spawn, and entry point**

Append this exact code to `Scripts/CreateOldShopGreybox.py`:

```python
def generate_old_shop(unreal_api=None, material_builder=None):
    api = unreal_api if unreal_api is not None else unreal
    if api is None:
        raise RuntimeError(
            "Unreal Python API is unavailable. Run this script inside "
            "Unreal Editor with Python Editor Script Plugin enabled."
        )
    if material_builder is None:
        material_builder = ensure_material

    parts = build_part_specs()
    envelope = expected_envelope()
    validate_part_specs(parts, envelope)

    cube_mesh = api.load_asset(CUBE_ASSET_PATH)
    if cube_mesh is None:
        raise RuntimeError(
            f"Could not load Engine Cube: {CUBE_ASSET_PATH}"
        )

    materials = {
        name: material_builder(name, color, api)
        for name, color in MATERIAL_COLORS.items()
    }
    actor_subsystem = api.get_editor_subsystem(api.EditorActorSubsystem)
    if actor_subsystem is None:
        raise RuntimeError("EditorActorSubsystem is unavailable.")

    generator_tag = api.Name(GENERATOR_TAG)
    old_actors = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if actor.actor_has_tag(generator_tag)
    ]
    spawned = []

    with api.ScopedEditorTransaction("Generate Old Shop 500x800x400"):
        if old_actors and not actor_subsystem.destroy_actors(old_actors):
            raise RuntimeError(
                "Could not remove the previous OldShop actor set."
            )

        try:
            for part in parts:
                actor = actor_subsystem.spawn_actor_from_class(
                    api.StaticMeshActor,
                    api.Vector(*part.location_cm),
                    api.Rotator(0.0, 0.0, 0.0),
                    False,
                )
                if actor is None:
                    raise RuntimeError(
                        f"Could not spawn actor: {part.label}"
                    )
                spawned.append(actor)

                actor.set_actor_label(part.label)
                actor.set_folder_path(api.Name(FOLDER_NAME))
                actor.set_editor_property("tags", [generator_tag])
                actor.set_actor_scale3d(api.Vector(*part.scale))

                component = actor.get_component_by_class(
                    api.StaticMeshComponent
                )
                if component is None:
                    raise RuntimeError(
                        f"StaticMeshComponent missing: {part.label}"
                    )
                if component.set_static_mesh(cube_mesh) is False:
                    raise RuntimeError(
                        f"Could not assign Cube mesh: {part.label}"
                    )
                component.set_material(0, materials[part.material_name])
                component.set_editor_property(
                    "mobility",
                    api.ComponentMobility.STATIC,
                )
        except Exception:
            for actor in list(spawned):
                actor_subsystem.destroy_actor(actor)
            raise

        actor_subsystem.set_selected_level_actors(spawned)

    bounds = overall_bounds(parts)
    api.log(
        f"OldShop generated: {len(spawned)} actors; "
        f"removed: {len(old_actors)}; bounds: {bounds}"
    )
    return len(old_actors), spawned


def main():
    api = unreal
    if api is None:
        raise RuntimeError(
            "This entry point must run inside Unreal Editor."
        )
    try:
        generate_old_shop(api)
    except Exception as error:
        api.log_error(f"OldShop generation failed: {error}")
        raise


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the complete automated test suite**

Run:

```powershell
python -m unittest Tests.test_create_old_shop_greybox -v
```

Expected: 13 tests run and all report `ok`.

- [ ] **Step 5: Run syntax and whitespace checks**

Run:

```powershell
python -m py_compile Scripts/CreateOldShopGreybox.py Tests/test_create_old_shop_greybox.py
git diff --check -- Scripts/CreateOldShopGreybox.py Tests/test_create_old_shop_greybox.py
```

Expected: both commands exit with code 0 and print no errors.

- [ ] **Step 6: Commit editor generation behavior**

```powershell
git add Scripts/CreateOldShopGreybox.py Tests/test_create_old_shop_greybox.py
git commit -m "feat: generate idempotent old shop greybox"
```

Expected: one commit containing only Task 3 changes, or a recorded Git permission
limitation without disturbing unrelated user changes.

---

### Task 4: UE5.7 editor smoke test and user-facing run instructions

**Files:**
- Modify: `Scripts/CreateOldShopGreybox.py`

**Interfaces:**
- Consumes: the completed `main()` entry point from Task 3.
- Produces: an editor-verified script and instructions embedded at the top of
  the delivered file.

- [ ] **Step 1: Expand the module docstring with exact run instructions**

Replace the opening docstring in `Scripts/CreateOldShopGreybox.py` with:

```python
"""Generate an old-city street shop greybox in the current UE5 level.

Default envelope: 500 cm wide × 800 cm deep × 400 cm high.
Front direction: -Y. Bottom plane: Z=1 cm.

The three overall dimensions and world placement are the first editable
parameters below. Every detail scales with those overall dimensions.

Run in Unreal Editor 5.7:
1. Enable the built-in "Python Editor Script Plugin" and restart the editor.
2. Open the destination level and leave Play/Simulate mode.
3. Use Tools > Execute Python Script and choose this file, or enter:
       py "D:/UE/Project/HorrorGame/Scripts/CreateOldShopGreybox.py"
   in the Output Log command field.
4. Confirm 31 selected actors appear inside the
   OldShop_500x800x400 World Outliner folder.
5. Save the level manually after inspecting the result.

Re-running replaces only actors tagged OldShop_500x800x400.
The script saves its seven material assets but never saves the current level.
"""
```

- [ ] **Step 2: Re-run the complete automated verification**

Run:

```powershell
python -m unittest Tests.test_create_old_shop_greybox -v
python -m py_compile Scripts/CreateOldShopGreybox.py
git diff --check -- Scripts/CreateOldShopGreybox.py Tests/test_create_old_shop_greybox.py
```

Expected: 13 tests pass; syntax and whitespace checks exit 0.

- [ ] **Step 3: Execute the Unreal Editor smoke test**

In UE5.7:

1. Open a disposable empty map or duplicate the current blockout map.
2. Run `Scripts/CreateOldShopGreybox.py`.
3. Confirm the Output Log says `OldShop generated: 31 actors`.
4. In the World Outliner, confirm Folder `OldShop_500x800x400` contains 31
   actors with unique labels.
5. Select `SM_OldShop_MainBlock` and confirm Location `(0, 10, 201)` and
   Scale `(5, 7.8, 4)`.
6. Confirm the storefront faces `-Y`, its bottom is at Z `1`, its back reaches
   Y `400`, and the sign front reaches but does not pass Y `-400`.
7. Confirm the seven materials exist under
   `/Game/OldShop_500x800x400/Materials`.
8. Run the script again and confirm the Outliner still contains 31 generated
   actors, not 62.
9. Confirm an unrelated actor without the generator tag remains untouched.
10. Close the disposable map without saving, unless the generated result is
    intentionally being kept.

Expected: all ten checks succeed. If the Python menu or `py` command is
unavailable, enable the built-in Python Editor Script Plugin, restart, and
repeat the test.

- [ ] **Step 4: Final requirement audit**

Run:

```powershell
Select-String -Path Scripts/CreateOldShopGreybox.py -Pattern `
  "Cube.Cube","M_OldWall","M_DarkWall","M_Shutter","M_Sign",`
  "M_DarkGlass","M_Trim","M_Stain","OldShop_500x800x400"
```

Expected: every required asset name, path fragment, material name, folder, and
tag is present in the output. Re-read the smoke-test observations to confirm
current-level visibility, exact orientation, strict cm dimensions, and
idempotent replacement.

- [ ] **Step 5: Commit the final instructions**

```powershell
git add Scripts/CreateOldShopGreybox.py
git commit -m "docs: add UE5 old shop script run steps"
```

Expected: the final script-only documentation commit, or a recorded Git
permission limitation without staging unrelated user changes.

## UE5.7 API References

- [EditorActorSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorActorSubsystem?application_version=5.7)
- [MaterialEditingLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialEditingLibrary?application_version=5.7)
- [EditorAssetLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorAssetLibrary?application_version=5.7)
- [MaterialProperty](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialProperty?application_version=5.7)
