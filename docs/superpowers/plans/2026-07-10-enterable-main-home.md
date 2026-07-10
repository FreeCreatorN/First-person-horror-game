# Enterable Main Home Shop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a UE5.7 Python generator that creates the enterable 500 × 800 × 400 cm “大众小卖部” as one Static Mesh Asset with two open doorways and reliable simple collision.

**Architecture:** A clean standalone script defines pure-Python box specifications first, then feeds those specifications into Geometry Script Dynamic Meshes. One visual mesh contains structure and decoration; a second collision-only mesh contains structural boxes and is converted into aligned-box simple collision. Existing assets are updated in place and the current level retains one tagged StaticMeshActor.

**Tech Stack:** Python 3, `unittest`, Unreal Engine 5.7 Python API, Geometry Scripting, Dynamic Mesh, Editor Scripting Utilities.

## Global Constraints

- Exact bounds: X[-250,250], Y[-400,400], Z[1,401] cm.
- Front faces -Y; street width X; depth Y; height Z.
- Output asset: `/Game/MainHome/SM_MainHome_Enterable`.
- Two openings: 196 cm clear width and 280 cm clear height each.
- One Static Mesh Asset and one current-level actor; no temporary Cube actors.
- Structural boxes alone receive collision; decoration remains NoCollision.
- No Boolean operations, external meshes, external textures, Blender, or non-built-in plugins.
- Existing `/Game/OldShop_500x800x400` content must remain untouched.

---

### Task 1: Pure geometry specification and enterability tests

**Files:**
- Create: `Tests/test_create_enterable_main_home.py`
- Create: `Scripts/CreateEnterableMainHome.py`

**Interfaces:**
- Produces: `BoxSpec`, `DoorwaySpec`, `build_box_specs()`, `build_doorway_specs()`, `box_bounds()`, `overall_bounds()`, `validate_design()`.
- Consumers: Tasks 2 and 3 use the returned `BoxSpec` objects without changing their geometry.

- [ ] **Step 1: Write the failing geometry tests**

Create `Tests/test_create_enterable_main_home.py` with a file-loader matching the existing tests and assertions equivalent to:

```python
class EnterableMainHomeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def test_asset_path_is_isolated_from_old_shop(self):
        self.assertEqual(
            "/Game/MainHome/SM_MainHome_Enterable",
            self.generator.STATIC_MESH_ASSET_PATH,
        )

    def test_exact_envelope(self):
        boxes = self.generator.build_box_specs()
        self.generator.validate_design(boxes)
        self.assertEqual(
            ((-250.0, 250.0), (-400.0, 400.0), (1.0, 401.0)),
            self.generator.overall_bounds(boxes),
        )

    def test_two_real_doorway_clearances(self):
        doors = self.generator.build_doorway_specs()
        self.assertEqual([196.0, 196.0], [door.width_cm for door in doors])
        self.assertEqual([280.0, 280.0], [door.height_cm for door in doors])
        structural = [b for b in self.generator.build_box_specs() if b.collision]
        for door in doors:
            self.assertFalse(
                any(self.generator.boxes_overlap_open_volume(box, door) for box in structural)
            )

    def test_interior_is_empty_and_left_right_connected(self):
        structural = [b for b in self.generator.build_box_specs() if b.collision]
        for point in ((-150.0, 0.0, 120.0), (0.0, 0.0, 120.0), (150.0, 0.0, 120.0)):
            self.assertFalse(any(self.generator.point_inside_box(point, b) for b in structural))

    def test_only_structure_has_collision(self):
        boxes = self.generator.build_box_specs()
        self.assertTrue(all(b.collision for b in boxes if b.category == "structure"))
        self.assertTrue(all(not b.collision for b in boxes if b.category != "structure"))

    def test_sign_contains_low_poly_chinese_letter_geometry(self):
        letters = [b for b in self.generator.build_box_specs() if b.category == "letter"]
        self.assertGreaterEqual(len(letters), 45)
        self.assertTrue(all(b.material_name == "M_MainHome_Letters" for b in letters))

    def test_material_ids_are_contiguous(self):
        self.assertEqual(list(range(7)), list(self.generator.MATERIAL_ID_BY_NAME.values()))
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -B -m unittest Tests.test_create_enterable_main_home
```

Expected: FAIL because `Scripts/CreateEnterableMainHome.py` does not yet exist.

- [ ] **Step 3: Implement the pure data layer**

Create `Scripts/CreateEnterableMainHome.py` with:

```python
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
    "M_MainHome_Wall", "M_MainHome_Interior", "M_MainHome_Floor",
    "M_MainHome_Sign", "M_MainHome_Trim", "M_MainHome_Letters",
    "M_MainHome_Stain",
]
MATERIAL_ID_BY_NAME = {name: index for index, name in enumerate(MATERIAL_ORDER)}

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
```

`build_box_specs()` must add these structural boxes in local centimeters before adding decorations:

```python
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
```

The Z values above are local offsets; `build_box_specs()` adds `BASE_Z_CM`, producing world Z[1,401]. Decorations add a 460 × 2 × 64 cm sign panel at Y[-398,-396], a trim frame at Y[-400,-398], 1 cm-thick gray-brown stains at Y[-399,-398], pillar/threshold trim, and compressed horizontal runs from five 9-row bitmap glyphs for `大众小卖部` at Y[-399.2,-398].

`build_doorway_specs()` returns open volumes:

```python
[
    DoorwaySpec("Door_Left", (-218, -400, 11), (-22, -350, 291)),
    DoorwaySpec("Door_Right", (22, -400, 11), (218, -350, 291)),
]
```

Implement strict positive-volume overlap checks so touching a doorway boundary is allowed. `validate_design()` rejects duplicate labels, unknown materials, non-positive sizes, envelope overflow, and structure intersecting either doorway.

- [ ] **Step 4: Run the tests and verify GREEN**

Run:

```powershell
python -B -m unittest Tests.test_create_enterable_main_home
```

Expected: all geometry tests PASS.

- [ ] **Step 5: Commit the pure geometry layer**

```powershell
git add Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py
git commit -m "feat: define enterable main home geometry"
```

---

### Task 2: Geometry Script asset, materials, and collision pipeline

**Files:**
- Modify: `Tests/test_create_enterable_main_home.py`
- Modify: `Scripts/CreateEnterableMainHome.py`

**Interfaces:**
- Consumes: `build_box_specs()` and `BoxSpec.collision` from Task 1.
- Produces: `create_visual_dynamic_mesh()`, `create_collision_dynamic_mesh()`, `create_or_update_static_mesh()`, `apply_structural_collision()`, `ensure_material()`.

- [ ] **Step 1: Add failing source-contract tests**

Add tests that read the script source and assert the required UE5.7-safe calls:

```python
def test_geometry_script_enables_material_ids_before_append(self):
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    self.assertLess(source.index("enable_material_ids"), source.index("append_box("))

def test_collision_uses_separate_aligned_box_mesh(self):
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    self.assertIn("set_static_mesh_collision_from_mesh", source)
    self.assertIn("ALIGNED_BOXES", source)
    self.assertNotIn("append_box_with_collision", source)

def test_existing_asset_is_updated_without_force_delete(self):
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    self.assertIn("copy_mesh_to_static_mesh", source)
    self.assertNotIn("delete_asset(STATIC_MESH_ASSET_PATH", source)
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
python -B -m unittest Tests.test_create_enterable_main_home
```

Expected: FAIL because the UE Geometry Script pipeline functions are absent.

- [ ] **Step 3: Implement Dynamic Mesh creation and material IDs**

Implement helpers that:

```python
dynamic_mesh = unreal.DynamicMesh()
unreal.GeometryScript_Materials.enable_material_ids(dynamic_mesh)
for box in boxes:
    unreal.GeometryScript_Primitives.append_box(
        dynamic_mesh,
        primitive_options_for(MATERIAL_ID_BY_NAME[box.material_name]),
        make_transform(box.location_cm),
        box.size_cm[0], box.size_cm[1], box.size_cm[2],
        0, 0, 0,
        unreal.GeometryScriptPrimitiveOriginMode.CENTER,
    )
```

Create one visual Dynamic Mesh from every box and one collision Dynamic Mesh from `[box for box in boxes if box.collision]`. Do not spawn any temporary Actor.

- [ ] **Step 4: Implement material creation and asset create/update**

`ensure_material()` creates or updates each material with a Constant3Vector connected to Base Color and a Constant connected to Roughness. Use colors from the design and roughness 0.88–0.96.

If the asset is absent, call:

```python
unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
    visual_mesh,
    STATIC_MESH_ASSET_PATH,
    create_options,
)
```

If present, load it and call `unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh` with LOD0, `replace_materials=True`, all seven materials, and seven stable slot names. Normalize tuple return values and require `GeometryScriptOutcomePins.SUCCESS` when an outcome is exposed.

- [ ] **Step 5: Implement aligned-box structural collision**

Create `GeometryScriptCollisionFromMeshOptions`, set `method` to `GeometryScriptCollisionGenerationMethod.ALIGNED_BOXES`, disable sphere/capsule detection, enable box detection, and call:

```python
unreal.GeometryScript_Collision.set_static_mesh_collision_from_mesh(
    collision_mesh,
    static_mesh,
    collision_options,
    set_options,
)
```

Mark the collision customized and save the Static Mesh asset.

- [ ] **Step 6: Run tests and verify GREEN**

```powershell
python -B -m unittest Tests.test_create_enterable_main_home
python -m py_compile Scripts/CreateEnterableMainHome.py
```

Expected: all tests PASS and compilation exits 0.

- [ ] **Step 7: Commit the UE asset pipeline**

```powershell
git add Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py
git commit -m "feat: generate main home static mesh asset"
```

---

### Task 3: Single level instance and safe repeat runs

**Files:**
- Modify: `Tests/test_create_enterable_main_home.py`
- Modify: `Scripts/CreateEnterableMainHome.py`

**Interfaces:**
- Consumes: target Static Mesh from Task 2.
- Produces: `place_single_instance()`, `generate_enterable_main_home()`, `main()`.

- [ ] **Step 1: Add failing instance-policy tests**

Add source-contract assertions:

```python
def test_single_instance_uses_dedicated_tag_and_actor_subsystem(self):
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    self.assertIn('GENERATOR_TAG = "MainHome_Enterable"', source)
    self.assertIn("EditorActorSubsystem", source)
    self.assertIn("SM_MainHome_Enterable_Instance", source)
    self.assertIn("set_selected_level_actors", source)

def test_active_path_never_spawns_cube_parts(self):
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    self.assertNotIn("/Engine/BasicShapes/Cube.Cube", source)
    self.assertNotIn("spawn_actor_from_object", source)
```

- [ ] **Step 2: Run and verify RED**

```powershell
python -B -m unittest Tests.test_create_enterable_main_home
```

Expected: FAIL because instance placement is not implemented.

- [ ] **Step 3: Implement single-instance placement**

Use `EditorActorSubsystem` to find actors with the exact generator tag. Reuse the first tagged `StaticMeshActor` when possible, delete only extra tagged actors, otherwise spawn one actor at `(0,0,0)`. Set:

```python
actor.set_actor_label("SM_MainHome_Enterable_Instance")
actor.set_folder_path(unreal.Name(FOLDER_NAME))
actor.set_editor_property("tags", [unreal.Name(GENERATOR_TAG)])
component.set_static_mesh(static_mesh)
component.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
```

Select the actor but do not automatically save the current level. Log asset path, box count, collision box count, exact bounds, and both doorway clearances.

- [ ] **Step 4: Add the executable entry point**

`generate_enterable_main_home()` performs validation, material creation, Dynamic Mesh creation, asset create/update, collision application, save, and instance placement. `main()` logs a clear Chinese error if required plugins/APIs are missing and re-raises the exception. Execute `main()` only under `if __name__ == "__main__":`.

- [ ] **Step 5: Run and verify GREEN**

```powershell
python -B -m unittest Tests.test_create_enterable_main_home
python -m py_compile Scripts/CreateEnterableMainHome.py
```

Expected: all tests PASS and compilation exits 0.

- [ ] **Step 6: Commit single-instance behavior**

```powershell
git add Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py
git commit -m "feat: place one enterable main home instance"
```

---

### Task 4: Final verification and UE handoff

**Files:**
- Modify only if verification exposes a defect: `Scripts/CreateEnterableMainHome.py`, `Tests/test_create_enterable_main_home.py`

**Interfaces:**
- Consumes: completed generator.
- Produces: verified script and exact UE Editor run instructions.

- [ ] **Step 1: Run the full local verification suite**

```powershell
python -B -m unittest discover -s Tests -p "test_*.py" -v
python -m py_compile Scripts/CreateEnterableMainHome.py
git diff --check
```

Expected: zero test failures, Python compilation exit 0, and no whitespace errors.

- [ ] **Step 2: Check the requirement contract from generated data**

Run a read-only Python inspection that prints asset path, overall bounds, doorway dimensions, visual box count, collision box count, and material IDs. Expected bounds are exactly `((-250, 250), (-400, 400), (1, 401))`; expected door sizes are two `196 × 280` entries; expected material IDs are `0..6`.

- [ ] **Step 3: UE Editor smoke test when the editor environment is available**

Enable `Python Editor Script Plugin`, `Editor Scripting Utilities`, and `Geometry Script`, restart UE, open the intended level, leave Play/Simulate, and execute `Scripts/CreateEnterableMainHome.py` through **Tools → Execute Python Script**.

Verify in UE:

- `/Game/MainHome/SM_MainHome_Enterable` exists and has seven material slots.
- The current level has exactly one `SM_MainHome_Enterable_Instance`.
- The Static Mesh simple collision contains separate boxes and leaves both front openings clear.
- A first-person pawn can enter through either opening and cross behind the center pillar.
- Running the script a second time updates the same asset and still leaves one actor.

- [ ] **Step 4: Report exact verification scope**

If UE Editor smoke testing cannot run in this session, state that limitation explicitly and distinguish local automated verification from editor-runtime verification. Provide the absolute script link and the short execution steps.
