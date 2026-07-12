# Main Home Polish Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the double-door seam to 0.5 cm, make an open shutter close on `E` without aiming while the player remains in its interaction zone, and add a Fab-first aged material pipeline.

**Architecture:** Keep the existing four-mesh Geometry Script pipeline and native `AMainHomeInteractiveActor`. Geometry changes remain inside the two movable door assets; shutter closing becomes a state-and-zone decision before the existing camera trace; materials retain the current nine stable slots and optionally bind imported Fab texture maps at deterministic asset paths, with an aged fallback when those maps are absent.

**Tech Stack:** UE 5.7 Python Geometry Script, Unreal C++ runtime plugin, UE Automation Tests, Python `unittest`, Fab/Quixel texture assets.

## Global Constraints

- Closed bounds remain exactly X `[-250,250]`, Y `[-400,400]`, Z `[1,401]` cm.
- Storefront faces local `-Y`; actor Z `0` keeps the model base at world Z `1` cm.
- Fixed frame never moves; shutter and both leaves remain independent movable components.
- Door pivots remain `(78,-394,120)` and `(210,-394,120)` cm.
- Player Blueprint, input assets, maps, `.uproject`, and OldShop assets are not modified.
- Generator remains idempotent, places at most one tagged actor, and never saves the current level.
- Fab is the primary resource source; marketplace acquisition is never automated.
- Work happens in an isolated `.worktrees/` worktree because the main checkout contains user map, project, and regenerated MainHome changes.

---

### Task 1: Close the double-door seam

**Files:**
- Modify: `Scripts/CreateEnterableMainHome.py:22-24, 518-585`
- Test: `Tests/test_create_enterable_main_home.py:484-580`

**Interfaces:**
- Produces: `DOOR_CENTER_GAP_CM = 0.5`, `DOOR_LEAF_WIDTH_CM = 65.75`.
- Produces: `Door_Left_CenterStile` and `Door_Right_CenterStile` visual boxes, owned by their respective movable meshes.
- Preserves: `LEFT_HINGE_CM`, `RIGHT_HINGE_CM`, collision ownership, glass/lower-panel offsets, and handle separation.

- [ ] **Step 1: Write the failing geometry tests**

Add this focused regression test and update the existing required-bound test to use the new values:

```python
def test_closed_double_door_center_gap_is_half_centimeter(self):
    left = self._asset_definition(
        self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH
    )
    right = self._asset_definition(
        self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH
    )
    left_panel = next(
        box for box in left.visual_boxes if box.label == "Door_Left_Panel"
    )
    right_panel = next(
        box for box in right.visual_boxes if box.label == "Door_Right_Panel"
    )
    left_bounds = self._translated_bounds(
        left_panel, left.actor_relative_transform.location_cm
    )
    right_bounds = self._translated_bounds(
        right_panel, right.actor_relative_transform.location_cm
    )

    self.assertEqual(65.75, left_panel.size_cm[0])
    self.assertEqual(65.75, right_panel.size_cm[0])
    self.assertAlmostEqual(0.5, right_bounds[0][0] - left_bounds[0][1])
    self.assertEqual((78.0, 143.75), left_bounds[0])
    self.assertEqual((144.25, 210.0), right_bounds[0])

    self.assertIn(
        "Door_Left_CenterStile",
        {box.label for box in left.visual_boxes},
    )
    self.assertIn(
        "Door_Right_CenterStile",
        {box.label for box in right.visual_boxes},
    )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -B -m unittest Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_closed_double_door_center_gap_is_half_centimeter -v
```

Expected: FAIL because the current leaves are 65 cm, the gap is 2 cm, and the center stiles do not exist.

- [ ] **Step 3: Implement the 0.5 cm seam and stiles**

Add constants next to the hinge constants:

```python
DOOR_CENTER_GAP_CM = 0.5
DOOR_LEAF_WIDTH_CM = (
    RIGHT_HINGE_CM[0]
    - LEFT_HINGE_CM[0]
    - DOOR_CENTER_GAP_CM
) / 2.0
```

Use `half_width = DOOR_LEAF_WIDTH_CM / 2.0` in both leaf builders. The left panel is centered at `+half_width`; the right panel is centered at `-half_width`. Move glass/lower-inset X centers to the same signed half-width and add non-colliding, depth-offset stiles:

```python
_pivot_box(
    "Door_Left_CenterStile",
    (DOOR_LEAF_WIDTH_CM - 2.0, -2.5, 0.0),
    (4.0, 1.0, 210.0),
    "M_MainHome_FadedGreenMetal",
    "door_detail",
)
```

```python
_pivot_box(
    "Door_Right_CenterStile",
    (-DOOR_LEAF_WIDTH_CM + 2.0, -2.5, 0.0),
    (4.0, 1.0, 210.0),
    "M_MainHome_FadedGreenMetal",
    "door_detail",
)
```

The stile X ranges are `[61.75,65.75]` and `[-65.75,-61.75]`; they remain separated from the glass, lower panel, and handles.

- [ ] **Step 4: Run all Python geometry tests and verify GREEN**

Run:

```powershell
python -B -m unittest discover -s Tests -p "test_create_enterable_main_home.py" -v
```

Expected: zero failures; exact envelope, overlap, collision, and doorway tests remain green.

- [ ] **Step 5: Commit Task 1**

```powershell
git add -- Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py
git commit -m "fix: reduce main home door seam"
```

---

### Task 2: Close an open shutter without camera aiming

**Files:**
- Modify: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Public/MainHomeInteractiveActor.h`
- Modify: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/MainHomeInteractiveActor.cpp`
- Test: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/Tests/MainHomeInteractiveActorTests.cpp`

**Interfaces:**
- Produces: `bool ShouldCloseShutterWithoutAim(const FAnimationState&, bool bPawnInShutterZone)`.
- Simplifies: `ClassifyHitComponent(Hit, Shutter, LeftDoor, RightDoor)`; the hidden shutter trace component is removed.
- Runtime rule: if the shutter target is open and the pawn overlaps `ShutterInteractionZone`, `E` closes it before camera tracing.

- [ ] **Step 1: Write the failing C++ automation test**

Replace `MainHomeInteractive.Input.ShutterTraceTargetBounds` with:

```cpp
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeShutterCloseWithoutAimTest,
    "MainHomeInteractive.Input.ShutterCloseWithoutAim",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeShutterCloseWithoutAimTest::RunTest(const FString& Parameters)
{
    MainHomeInteractive::FAnimationState State;
    TestFalse(
        TEXT("Closed shutter does not consume arbitrary E"),
        ShouldCloseShutterWithoutAim(State, true)
    );

    State.ShutterTarget = 1.0f;
    TestFalse(
        TEXT("Open target outside shutter zone still requires no action"),
        ShouldCloseShutterWithoutAim(State, false)
    );
    TestTrue(
        TEXT("Open target inside shutter zone closes without aim"),
        ShouldCloseShutterWithoutAim(State, true)
    );

    ToggleShutterTarget(State);
    TestEqual(TEXT("Fallback E targets closed"), State.ShutterTarget, 0.0f);
    TestTrue(
        TEXT("Closing restores collision immediately"),
        ShouldEnableShutterCollision(1.0f, State.ShutterTarget)
    );
    return true;
}
```

Update hit classification tests to remove `ShutterTraceTarget` from the helper signature and delete the trace-target hit assertion.

- [ ] **Step 2: Build once and verify compiler RED**

Run:

```powershell
& 'D:\UE_5.7\Engine\Build\BatchFiles\RunUAT.bat' BuildPlugin `
  -Plugin='D:\UE\Project\HorrorGame\.worktrees\main-home-polish\Plugins\MainHomeInteractive\MainHomeInteractive.uplugin' `
  -Package='D:\UE\Project\HorrorGame\.worktrees\main-home-polish\Saved\MainHomeInteractiveBuild' `
  -TargetPlatforms=Win64 -Rocket
```

Expected: compile failure because `ShouldCloseShutterWithoutAim` is not declared or defined.

- [ ] **Step 3: Implement the state-and-zone close rule**

Add the pure helper:

```cpp
bool ShouldCloseShutterWithoutAim(
    const FAnimationState& State,
    const bool bPawnInShutterZone
)
{
    return bPawnInShutterZone && State.ShutterTarget >= 0.5f;
}
```

At the start of `HandleInteractPressed`, after validating controller and pawn but before tracing, add:

```cpp
if (MainHomeInteractive::ShouldCloseShutterWithoutAim(
    AnimationState,
    ShutterInteractionZone->IsOverlappingActor(Pawn)
))
{
    ToggleShutter();
    return;
}
```

Remove `ShutterTraceTarget`, `GetShutterTraceTargetLocation`, and `GetShutterTraceTargetExtent` from the header, constructor, implementation, and classification helper. Keep closed-shutter opening camera-targeted through the real `Shutter` component. Keep `ConfigureInteractionBinding` non-consuming.

- [ ] **Step 4: Build and run all plugin tests GREEN**

Repeat `BuildPlugin`, copy packaged `Binaries/Win64` into the worktree plugin, then run:

```powershell
& 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
  'D:\UE\Project\HorrorGame\.worktrees\main-home-polish\HorrorGame.uproject' `
  '-EnablePlugins=MainHomeInteractive' `
  '-ExecCmds=Automation RunTests MainHomeInteractive; Quit' `
  -unattended -nop4 -NullRHI -stdout -FullStdOutLogOutput `
  '-TestExit=Automation Test Queue Empty'
```

Expected: all seven `MainHomeInteractive` tests complete successfully with exit code `0`.

- [ ] **Step 5: Commit Task 2**

```powershell
git add -- Plugins/MainHomeInteractive/Source
git commit -m "fix: close open shutter without aiming"
```

---

### Task 3: Add Fab-first aged material binding

**Files:**
- Modify: `Scripts/CreateEnterableMainHome.py`
- Test: `Tests/test_create_enterable_main_home.py`
- Create: `docs/third-party/MainHomeFabMaterials.md`
- Optional UE-created assets after user import: `Content/MainHome/Textures/*.uasset`

**Interfaces:**
- Produces: `FAB_TEXTURE_ASSET_PATHS`, containing deterministic plaster and metal map paths.
- Produces: `load_fab_texture_sets(asset_exists, load_asset) -> dict`.
- Extends: `ensure_material(material_name, texture_sets=None)`.
- Preserves: existing nine material names and material IDs.

- [ ] **Step 1: Write failing Fab-priority and fallback tests**

Add constants and behavior tests that require these stable paths:

```python
expected = {
    "plaster": {
        "base_color": "/Game/MainHome/Textures/T_Fab_ConstructionPlaster_BaseColor",
        "normal": "/Game/MainHome/Textures/T_Fab_ConstructionPlaster_Normal",
        "roughness": "/Game/MainHome/Textures/T_Fab_ConstructionPlaster_Roughness",
    },
    "metal": {
        "base_color": "/Game/MainHome/Textures/T_Fab_RustyMetalSheet_BaseColor",
        "normal": "/Game/MainHome/Textures/T_Fab_RustyMetalSheet_Normal",
        "roughness": "/Game/MainHome/Textures/T_Fab_RustyMetalSheet_Roughness",
    },
}
self.assertEqual(expected, self.generator.FAB_TEXTURE_ASSET_PATHS)
```

Test `load_fab_texture_sets` with injected fakes:

```python
loaded = self.generator.load_fab_texture_sets(
    asset_exists=lambda path: path in existing_paths,
    load_asset=lambda path: "texture:" + path,
)
self.assertEqual({"plaster", "metal"}, set(loaded))
```

Also require an incomplete set to be omitted entirely, so material generation uses the fallback instead of a half-connected PBR graph.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -B -m unittest discover -s Tests -p "test_create_enterable_main_home.py" -v
```

Expected: FAIL because the Fab constants and loader do not exist.

- [ ] **Step 3: Implement deterministic Fab map loading**

Add:

```python
FAB_TEXTURE_ASSET_PATHS = {
    "plaster": {
        "base_color": "/Game/MainHome/Textures/T_Fab_ConstructionPlaster_BaseColor",
        "normal": "/Game/MainHome/Textures/T_Fab_ConstructionPlaster_Normal",
        "roughness": "/Game/MainHome/Textures/T_Fab_ConstructionPlaster_Roughness",
    },
    "metal": {
        "base_color": "/Game/MainHome/Textures/T_Fab_RustyMetalSheet_BaseColor",
        "normal": "/Game/MainHome/Textures/T_Fab_RustyMetalSheet_Normal",
        "roughness": "/Game/MainHome/Textures/T_Fab_RustyMetalSheet_Roughness",
    },
}

def load_fab_texture_sets(asset_exists=None, load_asset=None):
    asset_exists = asset_exists or unreal.EditorAssetLibrary.does_asset_exist
    load_asset = load_asset or unreal.EditorAssetLibrary.load_asset
    result = {}
    for set_name, paths in FAB_TEXTURE_ASSET_PATHS.items():
        if not all(asset_exists(path) for path in paths.values()):
            continue
        result[set_name] = {
            role: load_asset(path) for role, path in paths.items()
        }
    return result
```

Map material names to sets:

```python
FAB_SET_BY_MATERIAL = {
    "M_MainHome_Wall": "plaster",
    "M_MainHome_Sign": "plaster",
    "M_MainHome_FadedGreenMetal": "metal",
}
```

- [ ] **Step 4: Bind complete Fab sets without destructive expression deletion**

Extend `ensure_material` to accept `texture_sets=None`. For a complete selected set, create or reuse tagged `MaterialExpressionTextureSample` nodes for Base Color, Normal, and Roughness; multiply Base Color by the material's existing tint; connect Normal using `SAMPLERTYPE_NORMAL`; connect Roughness directly. Reuse nodes by their `desc` values:

```python
FAB_NODE_DESCRIPTIONS = {
    "base_color": "MainHome_Fab_BaseColor",
    "normal": "MainHome_Fab_Normal",
    "roughness": "MainHome_Fab_Roughness",
    "tint": "MainHome_Fab_Tint",
    "multiply": "MainHome_Fab_TintMultiply",
}
```

Never call `delete_all_material_expressions`. If the selected set is absent, retain the flat material path but use the lighter aged palette:

```python
"M_MainHome_Wall": ((0.46, 0.39, 0.29, 1.0), 0.94),
"M_MainHome_Sign": ((0.40, 0.32, 0.23, 1.0), 0.92),
"M_MainHome_FadedGreenMetal": ((0.20, 0.30, 0.21, 1.0), 0.88),
"M_MainHome_Stain": ((0.24, 0.19, 0.145, 1.0), 0.97),
```

Update `generate_enterable_main_home()` to load texture sets once and pass them into every `ensure_material` call. Emit one concise warning listing missing stable paths.

- [ ] **Step 5: Record the Fab sources and manual import contract**

Create `docs/third-party/MainHomeFabMaterials.md` containing:

```markdown
# MainHome Fab material sources

- Construction Plaster — Quixel Megascans — Free on Fab
  https://www.fab.com/listings/c61bd44e-ce01-47ae-b0b8-eb0f4ff3cc60
- Rusty Metal Sheet — Quixel Megascans — Free on Fab
  https://www.fab.com/listings/54c7decd-5aac-491c-ad3f-cdfde8d4b1c8

Acquisition is performed manually through the UE Fab integration. Copy or
rename the 1K Base Color, Normal, and Roughness maps to the six stable asset
paths declared in `FAB_TEXTURE_ASSET_PATHS`. The generator falls back safely
when any complete set is absent.
```

- [ ] **Step 6: Run Python tests and commit Task 3**

Run:

```powershell
python -B -m unittest discover -s Tests -p "test_*.py" -v
```

Expected: zero failures, including repeat-safe material expression tests.

Commit:

```powershell
git add -- Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py docs/third-party/MainHomeFabMaterials.md
git commit -m "feat: add Fab-first MainHome materials"
```

---

### Task 4: Regenerate assets and verify the complete fix

**Files:**
- Update via UE: `Content/MainHome/SM_MainHome_Enterable.uasset`
- Update via UE: `Content/MainHome/SM_MainHome_Shutter.uasset`
- Update via UE: `Content/MainHome/SM_MainHome_Door_Left.uasset`
- Update via UE: `Content/MainHome/SM_MainHome_Door_Right.uasset`
- Update via UE: `Content/MainHome/Materials/*.uasset`
- Optional after manual Fab import: `Content/MainHome/Textures/*.uasset`

**Interfaces:**
- Consumes: door geometry from Task 1, interaction plugin from Task 2, Fab material loader from Task 3.
- Produces: regenerated four-mesh asset set and compiled project-local editor plugin binary.

- [ ] **Step 1: Run the complete local test suite**

```powershell
python -B -m unittest discover -s Tests -p "test_*.py" -v
```

Expected: zero failures.

- [ ] **Step 2: Build the plugin for all packaged targets**

```powershell
& 'D:\UE_5.7\Engine\Build\BatchFiles\RunUAT.bat' BuildPlugin `
  -Plugin='D:\UE\Project\HorrorGame\.worktrees\main-home-polish\Plugins\MainHomeInteractive\MainHomeInteractive.uplugin' `
  -Package='D:\UE\Project\HorrorGame\.worktrees\main-home-polish\Saved\MainHomeInteractiveBuild' `
  -TargetPlatforms=Win64 -Rocket
```

Expected: UnrealEditor, UnrealGame Development, and UnrealGame Shipping succeed.

- [ ] **Step 3: Generate twice and validate idempotence**

Run the existing repeat wrapper with the newly compiled plugin:

```powershell
& 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
  'D:\UE\Project\HorrorGame\.worktrees\main-home-polish\HorrorGame.uproject' -run=pythonscript `
  '-script=D:\UE\Project\HorrorGame\.worktrees\main-home-polish\Saved\SDD\verify_main_home_repeat.py' `
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities,GeometryScripting,MainHomeInteractive' `
  -unattended -nop4 -NullRHI -stdout -FullStdOutLogOutput
```

Expected: exact bounds, 0.5 cm door seam, one native tagged actor, and `0 error(s), 0 warning(s)` except the single documented missing-Fab warning when maps have not yet been imported.

- [ ] **Step 4: Inspect serialized assets**

Run the existing asset inspector. Expected:

- four Static Mesh assets;
- nine material slots in stable order;
- simple collision counts remain `23/1/1/1`;
- no map package is saved.

- [ ] **Step 5: Run final independent reviews**

Request one geometry/material review and one interaction review. There must be no unresolved Critical or Important findings before merge.

- [ ] **Step 6: Commit regenerated assets**

```powershell
git add -- Content/MainHome Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py Plugins/MainHomeInteractive/Source docs/third-party/MainHomeFabMaterials.md
git commit -m "fix: polish interactive main home storefront"
```

- [ ] **Step 7: Merge without touching user work**

Before merging, copy and stash only overlapping dirty `Content/MainHome` assets from the main checkout. Preserve user maps, `.uproject`, OldShop files, and generated map artifacts. Fast-forward the feature branch, copy the verified editor DLL, rerun Python and UE automation on main, then remove the owned worktree.

Final manual PIE acceptance remains: inspect the 0.5 cm seam, open the shutter, look anywhere while still inside the shutter interaction zone, press `E`, and confirm collision restores as it closes.
