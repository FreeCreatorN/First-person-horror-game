# Main Home Zero-Light-Leak and Material Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every visible perimeter light leak around the shutter, both door leaves, and the fixed transom glass, then rebuild the fallback materials toward the supplied warm plaster and aged green-metal reference.

**Architecture:** Keep the existing four-asset/one-Actor structure. Solve light leaks geometrically by extending panels behind fixed trim in a different Y layer, update the native Actor pivots so saved instances reset to the new layout, and keep Fab-complete texture sets as the first material path. When Fab textures are absent, use brighter low-contrast reference-derived source textures or tagged procedural nodes without accumulating expressions.

**Tech Stack:** UE 5.7 Python API, Geometry Script/Dynamic Mesh, UE C++ runtime plugin, Unreal Automation Tests, Python `unittest`, Win64 BuildPlugin.

## Global Constraints

- Overall bounds stay inside X=-250..250, Y=-400..400, Z=1..401 cm.
- Front faces -Y; width X; depth Y; height Z.
- One `MainHomeInteractiveActor` only; no temporary Cube actors.
- Fixed frame remains fixed; shutter and both doors remain separate movable mesh components.
- Door aiming remains independent: a hit changes only the hit leaf.
- Raised shutter closes only when the player aims at its 10.52 cm top strip (`263 cm * 0.04`).
- Complete Fab plaster/metal texture sets remain first priority.
- Existing dirty maps, `HorrorGame.uproject`, OldShop assets, and user-generated map geometry must not be staged, stashed, or overwritten.
- Before replacing dirty `Content/MainHome`, make a timestamped physical backup and a path-limited stash containing only `Content/MainHome`.

---

### Task 1: Concealed-edge geometry in the Python generator

**Files:**
- Modify: `Tests/test_create_enterable_main_home.py`
- Modify: `Scripts/CreateEnterableMainHome.py`

**Interfaces:**
- Consumes: `build_fixed_shell_box_specs()`, `build_shutter_box_specs()`, `build_left_door_box_specs()`, `build_right_door_box_specs()`, `box_bounds()`, and existing Actor transform constants.
- Produces: closed shutter bounds X=-213..21/Z=14..277, left leaf X=75..143.75/Z=14..228, right leaf X=144.25..213/Z=14..228, transom glass X=75..213/Z=236..282.

- [ ] **Step 1: Write failing geometry tests**

Add focused assertions that select boxes by label and compare exact world bounds:

```python
def test_closed_partitions_underlap_fixed_frames_without_light_leaks(self):
    shutter_asset = self._asset_definition(
        self.generator.SHUTTER_STATIC_MESH_ASSET_PATH
    )
    shutter = next(
        box for box in shutter_asset.visual_boxes
        if box.label == "Shutter_Panel"
    )
    self.assertEqual(
        ((-213.0, 21.0), (-394.5, -391.5), (14.0, 277.0)),
        self._translated_bounds(
            shutter, shutter_asset.actor_relative_transform.location_cm
        ),
    )

    expected = {
        self.generator.LEFT_DOOR_STATIC_MESH_ASSET_PATH: (
            "Door_Left_Panel", (75.0, 143.75)
        ),
        self.generator.RIGHT_DOOR_STATIC_MESH_ASSET_PATH: (
            "Door_Right_Panel", (144.25, 213.0)
        ),
    }
    for asset_path, (label, expected_x) in expected.items():
        asset = self._asset_definition(asset_path)
        panel = next(
            box for box in asset.visual_boxes if box.label == label
        )
        bounds = self._translated_bounds(
            panel, asset.actor_relative_transform.location_cm
        )
        self.assertEqual(expected_x, bounds[0])
        self.assertEqual((14.0, 228.0), bounds[2])

def test_transom_glass_is_concealed_behind_all_four_frame_edges(self):
    shell = self._asset_definition(self.generator.STATIC_MESH_ASSET_PATH)
    glass = next(
        box for box in shell.visual_boxes
        if box.label == "DoorTransom_Glass"
    )
    self.assertEqual(
        ((75.0, 213.0), (-393.5, -392.5), (236.0, 282.0)),
        self.generator.box_bounds(glass),
    )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m unittest Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_closed_partitions_underlap_fixed_frames_without_light_leaks Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_transom_glass_is_concealed_behind_all_four_frame_edges
```

Expected: FAIL showing old shutter X=-211..19, old door perimeter bounds, and old glass X=80..208/Z=239..279.

- [ ] **Step 3: Implement exact concealed bounds**

Use explicit constants so geometry and Actor pivots cannot drift:

```python
FRAME_UNDERLAP_CM = 1.0
LEFT_HINGE_CM = (76.0, -394.0, 121.0)
RIGHT_HINGE_CM = (212.0, -394.0, 121.0)
DOOR_CENTER_GAP_CM = 0.5
DOOR_VISIBLE_SPAN_CM = (
    RIGHT_HINGE_CM[0] - LEFT_HINGE_CM[0] - DOOR_CENTER_GAP_CM
) / 2.0
DOOR_PANEL_WIDTH_CM = DOOR_VISIBLE_SPAN_CM + FRAME_UNDERLAP_CM
DOOR_PANEL_HEIGHT_CM = 214.0
```

Build the shutter panel with local size `(234, 3, 263)` and local center `(0, 1.5, -131.5)`. Build the left panel from local X=-1..67.75 and the right panel from local X=-67.75..1. Build both panels at local Z=-107..107 so the new Z=121 pivots produce world Z=14..228. Change `DoorTransom_Glass` to size `(138, 1, 46)` at existing local center `(144, -393, 258)`.

Keep inset panels centered on the visible 67.75 cm span, not on the hidden-underlap panel span. Keep collision only on the main partition boxes.

- [ ] **Step 4: Run focused and full Python tests**

Run:

```powershell
python -m unittest discover -s Tests -p 'test_*.py'
```

Expected: all tests PASS; update prior exact-bound assertions to the confirmed concealed bounds, while the 0.5 cm center division test remains unchanged.

- [ ] **Step 5: Commit geometry generator changes**

```powershell
git add -- Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py
git commit -m "fix: conceal main home panels behind frames"
```

---

### Task 2: Reset native component layout to the new door pivots

**Files:**
- Modify: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/Tests/MainHomeInteractiveActorTests.cpp`
- Modify: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/MainHomeInteractiveActor.cpp`

**Interfaces:**
- Consumes: generated door meshes from Task 1 and `AMainHomeInteractiveActor::ResetMainHomeComponentLayout()`.
- Produces: native hinge transforms `(76,-394,121)` and `(212,-394,121)`, with leaf relative transforms reset to identity on construction and `SetMainHomeMeshes()`.

- [ ] **Step 1: Change tests first**

Update `FMainHomeComponentLayoutResetTest` to require the new pivots and extend `FMainHomeProductionGeometryAndTraceTest` with real-asset perimeter assertions:

```cpp
TestEqual(TEXT("Left hinge pivot is restored"),
    LeftHinge->GetRelativeLocation(), FVector(76.0f, -394.0f, 121.0f));
TestEqual(TEXT("Right hinge pivot is restored"),
    RightHinge->GetRelativeLocation(), FVector(212.0f, -394.0f, 121.0f));

TestTrue(TEXT("Left leaf hides under left frame"),
    FMath::IsNearlyEqual(LeftWorldBounds.Min.X, 75.0f, 0.01f));
TestTrue(TEXT("Right leaf hides under right frame"),
    FMath::IsNearlyEqual(RightWorldBounds.Max.X, 213.0f, 0.01f));
TestTrue(TEXT("Center division is unchanged"),
    FMath::IsNearlyEqual(
        RightWorldBounds.Min.X - LeftWorldBounds.Max.X, 0.5f, 0.01f));
TestTrue(TEXT("Door vertical underlap is exact"),
    FMath::IsNearlyEqual(LeftWorldBounds.Min.Z, 14.0f, 0.01f)
    && FMath::IsNearlyEqual(LeftWorldBounds.Max.Z, 228.0f, 0.01f));

TestTrue(TEXT("Open shutter retains 10.52 cm strip"),
    FMath::IsNearlyEqual(
        263.0f * ComputeShutterScale(1.0f), 10.52f, 0.01f));
TestTrue(TEXT("Open shutter clears 252.48 cm"),
    FMath::IsNearlyEqual(
        263.0f * (1.0f - ComputeShutterScale(1.0f)), 252.48f, 0.01f));
```

- [ ] **Step 2: Build and run automation to verify RED**

Build `HorrorGameEditor Win64 Development`, then run `Automation RunTests MainHomeInteractive;Quit`.

Expected: layout/integration tests FAIL on old X=78/210/Z=120 pivots or old asset bounds.

- [ ] **Step 3: Update production layout reset**

In `ResetMainHomeComponentLayout()` use:

```cpp
LeftHinge->SetRelativeTransform(FTransform(
    FRotator::ZeroRotator, FVector(76.0f, -394.0f, 121.0f), FVector::OneVector));
RightHinge->SetRelativeTransform(FTransform(
    FRotator::ZeroRotator, FVector(212.0f, -394.0f, 121.0f), FVector::OneVector));
```

Do not change independent target dispatch, door yaw direction, input binding, shutter collision channels, or interaction-zone sizes.

- [ ] **Step 4: Rebuild and verify GREEN**

Expected: all `MainHomeInteractive` automation tests pass after real assets from Task 1 are regenerated; if assets have not yet been regenerated, compile must pass and the real-asset test is completed in Task 4.

- [ ] **Step 5: Commit native layout changes**

```powershell
git add -- Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/MainHomeInteractiveActor.cpp Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/Tests/MainHomeInteractiveActorTests.cpp
git commit -m "fix: reset doors to concealed frame layout"
```

---

### Task 3: Rebuild the reference-oriented material fallback

**Files:**
- Create when generated fallback textures are used: `SourceArt/MainHome/T_MainHome_AgedPlaster_BaseColor.png`
- Create when generated fallback textures are used: `SourceArt/MainHome/T_MainHome_OldGreenMetal_BaseColor.png`
- Modify: `Tests/test_create_enterable_main_home.py`
- Modify: `Scripts/CreateEnterableMainHome.py`
- Regenerate: `Content/MainHome/Materials/*.uasset`
- Create/update when source textures are used: `Content/MainHome/Textures/*.uasset`

**Interfaces:**
- Consumes: complete Fab sets at the existing `FAB_TEXTURE_ASSET_PATHS`; reference `C:/Users/aa131/Downloads/333.png` for visual direction.
- Produces: `REFERENCE_TEXTURE_ASSET_PATHS`, `load_reference_fallback_textures() -> dict[str, Texture2D]`, Fab-first materials, and a reference-textured fallback with stable tagged expressions and the same nine material IDs.

- [ ] **Step 1: Write failing palette and idempotency tests**

Require warm bright plaster, muted green metal, non-black trim/stain/glass, and restrained grime:

```python
def test_reference_palette_is_warm_bright_and_low_contrast(self):
    wall, _ = self.generator.MATERIAL_SETTINGS["M_MainHome_Wall"]
    metal, _ = self.generator.MATERIAL_SETTINGS["M_MainHome_FadedGreenMetal"]
    glass, _ = self.generator.MATERIAL_SETTINGS["M_MainHome_DarkGlass"]
    self.assertGreaterEqual(wall[0], 0.58)
    self.assertGreater(wall[0], wall[1])
    self.assertGreater(wall[1], wall[2])
    self.assertGreater(metal[1], metal[0])
    self.assertGreater(metal[1], metal[2])
    self.assertGreaterEqual(glass[0] + glass[1] + glass[2], 0.12)
    self.assertLessEqual(
        self.generator.PROCEDURAL_FALLBACK_SETTINGS[
            "M_MainHome_FadedGreenMetal"
        ]["noise_max"],
        0.20,
    )
```

Extend the mocked material tests so two runs retain one node for every tagged description and preserve Fab connections when all three Fab maps exist.

Add a loader test with fake assets at exactly these paths:

```python
expected = {
    "plaster": "/Game/MainHome/Textures/T_MainHome_AgedPlaster_BaseColor",
    "metal": "/Game/MainHome/Textures/T_MainHome_OldGreenMetal_BaseColor",
}
self.assertEqual(expected, self.generator.REFERENCE_TEXTURE_ASSET_PATHS)
self.assertEqual(
    {"plaster", "metal"},
    set(self.generator.load_reference_fallback_textures()),
)
```

- [ ] **Step 2: Run focused material tests and verify RED**

Expected: FAIL because wall red is 0.46, glass sum is 0.10, and metal grime maximum is 0.48.

- [ ] **Step 3: Create the reference fallback source textures**

Use the image generation tool with `333.png` as visual reference to create two seamless 1024 x 1024 albedo sources. The prompts must explicitly request orthographic, tileable PBR base color with no directional illumination, ambient occlusion, highlights, text, frame, or baked shadow:

- `T_MainHome_AgedPlaster_BaseColor.png`: warm ivory-beige old plaster, broad low-contrast gray-brown mottling, restrained lower-wall grime character, fine worn texture.
- `T_MainHome_OldGreenMetal_BaseColor.png`: faded dark green painted metal, sparse small brown-orange rust chips and scratches, no corrugation because slats are modeled geometry.

Inspect both generated images before use. Store them under `SourceArt/MainHome` and import/update deterministic `Texture2D` assets at the paths asserted in Step 1. These assets are fallback inputs only; complete Fab texture sets still override them.

- [ ] **Step 4: Implement texture-aware restrained fallback materials**

Add:

```python
REFERENCE_TEXTURE_ASSET_PATHS = {
    "plaster": "/Game/MainHome/Textures/T_MainHome_AgedPlaster_BaseColor",
    "metal": "/Game/MainHome/Textures/T_MainHome_OldGreenMetal_BaseColor",
}
REFERENCE_TEXTURE_BY_MATERIAL = {
    "M_MainHome_Wall": "plaster",
    "M_MainHome_Sign": "plaster",
    "M_MainHome_FadedGreenMetal": "metal",
}
REFERENCE_FALLBACK_NODE_DESCRIPTIONS = {
    "base_color": "MainHome_Reference_BaseColor",
    "multiply": "MainHome_Reference_TintMultiply",
}
```

`load_reference_fallback_textures()` loads only existing `Texture2D` assets and returns a dictionary keyed by `plaster`/`metal`. When a complete Fab set exists, retain the existing Fab branch unchanged. When Fab is incomplete and a reference fallback texture exists, reuse/create one tagged `MaterialExpressionTextureSample` and one tagged `MaterialExpressionMultiply`, multiply the texture RGB by the material tint constant, and feed the result into input A of the existing aged-color Lerp. When the reference texture is absent, feed the tint constant directly into the Lerp as the last-resort procedural path. Never delete or duplicate tagged expressions when switching among Fab, reference texture, and constant fallback.

Use these exact linear-color targets:

```python
MATERIAL_SETTINGS.update({
    "M_MainHome_Wall": ((0.62, 0.52, 0.39, 1.0), 0.90),
    "M_MainHome_Sign": ((0.54, 0.43, 0.30, 1.0), 0.91),
    "M_MainHome_Trim": ((0.20, 0.16, 0.12, 1.0), 0.88),
    "M_MainHome_Letters": ((0.30, 0.09, 0.055, 1.0), 0.86),
    "M_MainHome_Stain": ((0.34, 0.27, 0.20, 1.0), 0.95),
    "M_MainHome_FadedGreenMetal": ((0.16, 0.25, 0.15, 1.0), 0.84),
    "M_MainHome_DarkGlass": ((0.045, 0.065, 0.055, 1.0), 0.24),
})
```

Set wall/sign `noise_max` to `0.18` and metal `noise_max` to `0.20`. Keep WorldPosition/Noise/Lerp nodes on different graph positions, retain reciprocal centimeter noise scale, and never connect a fallback base-color texture as a normal map.

- [ ] **Step 5: Run all Python material and geometry tests**

Run the complete Python suite and expect all tests to pass with stable nine-slot material IDs and stable tagged-node counts.

- [ ] **Step 6: Commit source and material-generator changes**

```powershell
git add -- Scripts/CreateEnterableMainHome.py Tests/test_create_enterable_main_home.py SourceArt/MainHome
git commit -m "feat: match main home reference palette"
```

Do not stage regenerated `.uasset` files until Task 4 verifies them in UE.

---

### Task 4: Regenerate, inspect, package, and safely integrate

**Files:**
- Regenerate: `Content/MainHome/SM_MainHome_Enterable.uasset`
- Regenerate: `Content/MainHome/SM_MainHome_Shutter.uasset`
- Regenerate: `Content/MainHome/SM_MainHome_Door_Left.uasset`
- Regenerate: `Content/MainHome/SM_MainHome_Door_Right.uasset`
- Regenerate: `Content/MainHome/Materials/*.uasset`
- Create/update: `Content/MainHome/Textures/T_MainHome_AgedPlaster_BaseColor.uasset`
- Create/update: `Content/MainHome/Textures/T_MainHome_OldGreenMetal_BaseColor.uasset`
- Package: `Plugins/MainHomeInteractive/Binaries/Win64/*` (ignored build output)

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: verified assets, one updated level Actor, packaged plugin binaries, and a safe fast-forward merge with user files preserved.

- [ ] **Step 1: Preserve current user MainHome assets**

Create a new timestamped physical copy under `Saved/CodexBackups/MainHome-before-zero-leak-*`. Before the final merge, create a path-limited stash with `git stash push -- Content/MainHome` only. Never include maps, OldShop, generated map geometry, scripts unrelated to MainHome, or `HorrorGame.uproject`.

- [ ] **Step 2: Build the editor target and install the new DLL while UE is closed**

If `UnrealEditor.exe` is running, ask the user to close it normally. Do not rely on a detached background updater. Build `HorrorGameEditor Win64 Development`, copy the resulting `UnrealEditor-MainHomeInteractive.dll`, `.pdb`, and `.modules`, then compare SHA-256 source/destination hashes before reopening UE.

- [ ] **Step 3: Run the generator twice in one UE process**

Launch `UnrealEditor-Cmd.exe` with `PythonScriptPlugin,EditorScriptingUtilities,GeometryScripting,MainHomeInteractive` enabled. Call `generate_enterable_main_home()` twice and assert:

- one Actor tagged `MainHome_Interactive`;
- actor class `MainHomeInteractiveActor`;
- exact overall bounds X=-250..250, Y=-400..400, Z=1..401;
- four mesh assets load successfully;
- material expression counts remain stable after the second run.

- [ ] **Step 4: Inspect final assets**

Use UE Python to verify nine material slots on all four meshes, simple collision counts `23/1/1/1` unless the fixed shell count changes for an explicitly reviewed reason, concealed panel bounds, transom material assignment, and no temporary actors.

- [ ] **Step 5: Run UE automation**

Run every `MainHomeInteractive` test. Expected: all tests pass, including real-asset bounds, independent doors, raised shutter trace, Pawn passage, collision restore, and stale-layout reset.

- [ ] **Step 6: Package all Win64 targets**

Run `RunUAT.bat BuildPlugin` and require successful builds for UnrealEditor Win64 Development, UnrealGame Win64 Development, and UnrealGame Win64 Shipping. Copy the packaged editor binary into the isolated project and rerun automation against that packaged DLL.

- [ ] **Step 7: Commit verified regenerated assets**

```powershell
git add -- Content/MainHome
git commit -m "fix: regenerate zero-leak main home assets"
```

- [ ] **Step 8: Review and merge**

Request separate geometry/interaction and material reviews. Resolve every Critical/Important finding with a new red-green cycle. Fast-forward merge only after fresh Python tests, UE automation, BuildPlugin, `git diff --check`, and clean isolated status all pass.

- [ ] **Step 9: User acceptance check**

With the target level open, run `Scripts/CreateEnterableMainHome.py`, save the level, then check in PIE:

- closed door perimeter has no visible background/shadow leak to side frame, threshold, or transom bar;
- closed shutter perimeter has no visible background/shadow leak to guides, threshold, or top box;
- transom glass fills behind all frame edges;
- aiming at each leaf opens only that leaf;
- aiming at the raised shutter strip closes it;
- materials visually follow `333.png` under the level's actual lighting/exposure.
