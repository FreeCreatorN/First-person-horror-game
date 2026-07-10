# Interactive Main Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the equal storefront openings with a reference-matched wide shutter and narrow double door, then provide a self-contained E-interaction actor.

**Architecture:** Geometry Script continues to generate the fixed shell plus three pivot-correct movable mesh assets. A source-only runtime project plugin supplies one native actor with a fixed shell component, one shutter component, two hinged leaf components, proximity input, camera targeting, and short interpolation animations. Existing character Blueprints, maps, and OldShop assets remain untouched.

**Tech Stack:** UE 5.7 Python Geometry Script, Unreal C++ runtime plugin, UE Automation Tests, Python `unittest`.

## Global Constraints

- Closed bounds: X `[-250,250]`, Y `[-400,400]`, Z `[1,401]` cm; front faces `-Y`.
- Shutter opening width `248` cm; double-door opening width `152` cm.
- Fixed shell/frame never moves; shutter, left leaf, and right leaf are separate movable components.
- Direct nearby `E` interaction must not modify the existing player Blueprint or input mapping.
- No visible coplanar surfaces or unintended positive-volume overlap.
- Generator never saves the current level or touches `/Game/OldShop_500x800x400`.

---

### Task 1: Componentized storefront geometry

**Files:**
- Modify: `Scripts/CreateEnterableMainHome.py`
- Modify: `Tests/test_create_enterable_main_home.py`

**Interfaces:**
- Produces: `build_shell_box_specs()`, `build_shutter_box_specs()`, `build_left_door_box_specs()`, `build_right_door_box_specs()`.
- Produces: `MESH_ASSET_DEFINITIONS`, containing asset path, pivot-relative visual boxes, collision boxes, and actor-relative transform.

- [ ] **Step 1: Write failing geometry tests**

Add tests that require:

```python
def test_storefront_uses_reference_width_ratio(self):
    openings = self.generator.build_doorway_specs()
    self.assertEqual((248.0, 152.0), tuple(item.width_cm for item in openings))

def test_movable_meshes_are_three_independent_partitions(self):
    definitions = self.generator.MESH_ASSET_DEFINITIONS
    self.assertEqual(
        {
            "/Game/MainHome/SM_MainHome_Shutter",
            "/Game/MainHome/SM_MainHome_Door_Left",
            "/Game/MainHome/SM_MainHome_Door_Right",
        },
        {item.asset_path for item in definitions if not item.fixed},
    )

def test_shutter_and_door_meshes_use_required_pivots(self):
    self.assertEqual((-96.0, -394.5, 277.0), self.generator.SHUTTER_PIVOT_CM)
    self.assertEqual((78.0, -394.0, 120.0), self.generator.LEFT_HINGE_CM)
    self.assertEqual((210.0, -394.0, 120.0), self.generator.RIGHT_HINGE_CM)
```

Also require exact closed bounds, 230 cm shutter panel width, two 65 cm leaves, fixed transom, fixed-frame collision, movable collision ownership, and pairwise no-overlap/depth-offset checks.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -B -m unittest discover -s Tests -p "test_create_enterable_main_home.py" -v
```

Expected: new tests fail because the four builders and asset definitions do not exist and the openings are still equal.

- [ ] **Step 3: Implement the four geometry partitions**

Refactor the current single list into four pivot-aware lists. Keep all fixed frame pieces in the shell. Add faded green metal and dark-glass materials. Use these closed transforms:

```python
SHUTTER_PIVOT_CM = (-96.0, -394.5, 277.0)
LEFT_HINGE_CM = (78.0, -394.0, 120.0)
RIGHT_HINGE_CM = (210.0, -394.0, 120.0)

OPENING_BOUNDS = (
    DoorwaySpec("ShutterOpening", (-220.0, -400.0, 11.0), (28.0, -350.0, 291.0)),
    DoorwaySpec("DoubleDoorOpening", (68.0, -400.0, 11.0), (220.0, -350.0, 291.0)),
)
```

The shutter mesh is local X `[-115,115]`, local Z `[-262,0]`; the left leaf is local X `[0,65]`; the right leaf is local X `[-65,0]`. Handles are part of their leaf mesh.

- [ ] **Step 4: Run the full Python suite and verify GREEN**

Run the command from Step 2. Expected: all old and new tests pass with zero failures.

- [ ] **Step 5: Commit**

```powershell
git add -- Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py
git commit -m "feat: componentize interactive main home storefront"
```

---

### Task 2: Generate four Static Mesh assets safely

**Files:**
- Modify: `Scripts/CreateEnterableMainHome.py`
- Modify: `Tests/test_create_enterable_main_home.py`
- Update via UE: `Content/MainHome/SM_MainHome_Enterable.uasset`
- Create via UE: `Content/MainHome/SM_MainHome_Shutter.uasset`
- Create via UE: `Content/MainHome/SM_MainHome_Door_Left.uasset`
- Create via UE: `Content/MainHome/SM_MainHome_Door_Right.uasset`
- Create/update via UE: `Content/MainHome/Materials/*.uasset`

**Interfaces:**
- Produces: `create_or_update_static_mesh(definition, materials)`.
- Produces: four reusable mesh assets with aligned-box simple collision and stable material slots.

- [ ] **Step 1: Write failing pipeline tests**

Require that generation iterates all four definitions, creates visual and collision meshes separately, saves every asset, does not spawn Cube actors, and never calls level-save APIs.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -B -m unittest discover -s Tests -p "test_create_enterable_main_home.py" -v
```

Expected: the multi-asset pipeline assertions fail against the current single-asset function.

- [ ] **Step 3: Implement the generic asset pipeline**

Replace the single hard-coded asset build with:

```python
for definition in MESH_ASSET_DEFINITIONS:
    create_or_update_static_mesh(definition, materials)
```

Use existing UE5.7 material-ID compatibility, in-place asset updates, `ALIGNED_BOXES` collision, and missing-asset-safe loading. Keep material IDs deterministic across all assets.

- [ ] **Step 4: Verify tests, then run real UE generation**

```powershell
python -B -m unittest discover -s Tests -p "test_*.py" -v
```

Then run UE5.7 PythonScriptCommandlet with `PythonScriptPlugin`, `EditorScriptingUtilities`, and `GeometryScripting`. Expected: exit 0, zero UE errors/warnings, four assets saved, exact shell bounds retained.

- [ ] **Step 5: Commit generated assets**

```powershell
git add -- Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py Content/MainHome
git commit -m "feat: generate interactive storefront mesh assets"
```

---

### Task 3: Self-contained runtime interaction actor

**Files:**
- Create: `Plugins/MainHomeInteractive/MainHomeInteractive.uplugin`
- Create: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/MainHomeInteractive.Build.cs`
- Create: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Public/MainHomeInteractiveActor.h`
- Create: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/MainHomeInteractiveActor.cpp`
- Create: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/MainHomeInteractiveModule.cpp`
- Create: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/Tests/MainHomeInteractiveActorTests.cpp`
- Modify: `Scripts/CreateEnterableMainHome.py`
- Modify: `Tests/test_create_enterable_main_home.py`

**Interfaces:**
- Produces: `AMainHomeInteractiveActor` and `EMainHomeDoorOpenDirection { Inward, Outward }`.
- Public controls: `ToggleShutter()`, `ToggleLeftDoor()`, `ToggleRightDoor()`.
- Testable helpers: alpha advancement, shutter scale, mirrored target yaw, and hit-component classification.

- [ ] **Step 1: Write failing C++ automation tests**

Tests must assert:

```cpp
TestEqual(TEXT("Left outward"), ComputeDoorYaw(true, EMainHomeDoorOpenDirection::Outward, 95.f), -95.f);
TestEqual(TEXT("Right outward"), ComputeDoorYaw(false, EMainHomeDoorOpenDirection::Outward, 95.f), 95.f);
TestEqual(TEXT("Left inward"), ComputeDoorYaw(true, EMainHomeDoorOpenDirection::Inward, 95.f), 95.f);
TestEqual(TEXT("Right inward"), ComputeDoorYaw(false, EMainHomeDoorOpenDirection::Inward, 95.f), -95.f);
```

Also test independent door targets, shutter closed/open scales `1.0/0.03`, collision state at endpoints, and that settled states disable ticking.

- [ ] **Step 2: Build and verify RED**

Run `RunUAT.bat BuildPlugin` for Win64. Expected: compile failure because the actor and helper functions are not implemented.

- [ ] **Step 3: Implement the minimal runtime plugin**

Create the fixed shell, shutter, hinges, leaves, and two overlap boxes in the constructor. Load `/Game/MainHome` meshes by fixed soft paths. On nearby player overlap, bind `E`; on press, line trace from the player camera and toggle only the hit shutter/leaf. Animate with duration-based alphas; disable tick when settled and disable shutter collision only at the fully open endpoint. Mark direction, angle, duration, and distance instance-editable.

Set the plugin descriptor to `EnabledByDefault: true`; do not edit `HorrorGame.uproject` or existing player assets.

- [ ] **Step 4: Build and run automation tests GREEN**

Build the plugin package for Win64, copy its generated `Binaries` into the project plugin for local verification, then run:

```powershell
UnrealEditor-Cmd.exe HorrorGame.uproject -ExecCmds="Automation RunTests MainHomeInteractive; Quit" -unattended -nop4 -NullRHI -TestExit="Automation Test Queue Empty"
```

Expected: build exit 0 and all `MainHomeInteractive` tests pass.

- [ ] **Step 5: Integrate generator placement and verify idempotence**

Update Python placement to prefer `unreal.MainHomeInteractiveActor`, assign the four meshes, use tag `MainHome_Interactive`, delete exact-tag duplicates, and fall back to the fixed shell StaticMeshActor with a warning if the plugin is unavailable. Add Python tests for both branches and repeated runs.

Run the generator twice in one UE process and query `EditorActorSubsystem`. Expected: exactly one tagged interactive actor, no map save, zero errors/warnings.

- [ ] **Step 6: Commit**

```powershell
git add -- Plugins/MainHomeInteractive Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py Content/MainHome
git commit -m "feat: add interactive main home actor"
```

---

## Final verification

- Run all Python tests and AST/compile checks.
- Build the Win64 plugin and run all plugin automation tests.
- Run real UE5.7 generation twice and inspect four asset paths, material slots, collision boxes, exact actor count, and error/warning totals.
- Confirm no tracked map, existing character Blueprint, input asset, `.uproject`, or OldShop path changed.
- Manually validate E targeting, shutter clearance, both leaf swings, and inward/outward selection in Play mode.
