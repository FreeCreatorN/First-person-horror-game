# Main Home Material and Shutter Final Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shop visibly aged without Fab downloads, make the raised shutter closable only by aiming at its top strip, preserve independent doors and the true 0.5 cm closed seam, and verify player clearance.

**Architecture:** Keep the four existing Static Mesh assets and nine material slots. Extend the generator's idempotent material graph for procedural fallback, and keep interaction logic in `AMainHomeInteractiveActor`; pure helper functions remain automation-testable without PIE. Reset component layout when meshes are assigned so native values win over stale instance overrides.

**Tech Stack:** UE 5.7 Python Geometry Script, UE material expressions, C++ Actor components, Unreal Automation Tests, Python `unittest`.

## Global Constraints

- Overall bounds remain X -250..250, Y -400..400, Z 1..401 cm.
- Front remains -Y and the bottom remains Z=1 cm.
- Doors remain independent: aiming at one toggles only that leaf.
- Closed center seam remains exactly 0.5 cm.
- A complete Fab texture set always takes precedence over procedural fallback.
- Raised shutter leaves an approximately 10 cm visible top strip and at least 230 x 250 cm usable clearance.
- Current level contains one generated `MainHomeInteractiveActor` and no temporary Cube actors.

---

### Task 1: Preserve the closed door layout

**Files:**
- Modify: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/MainHomeInteractiveActor.cpp`
- Test: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/Tests/MainHomeInteractiveActorTests.cpp`
- Test: `Tests/test_create_enterable_main_home.py`

**Interfaces:**
- Consumes: existing `SetMainHomeMeshes(...)`, hinge constants X=78/210 cm.
- Produces: `ResetMainHomeComponentLayout()` with leaf relative location zero, rotation zero, and scale one.

- [ ] **Step 1: Add failing layout and seam tests**

Add a native test-only pure validation helper or actor test proving the left and right hinge locations are 78 and 210 cm and both leaf relative transforms are identity after mesh assignment. Extend the Python seam test to assert `DOOR_CENTER_GAP_CM == 0.5` and world leaf ranges `[78,143.75]` and `[144.25,210]`.

- [ ] **Step 2: Run RED tests**

Run `python -m unittest Tests.test_create_enterable_main_home -v`; expect the new reset-layout contract test to fail because the reset function is absent. Build/run the focused native test and expect the same missing behavior.

- [ ] **Step 3: Implement the reset**

Add `ResetMainHomeComponentLayout()` and call it from the constructor and `SetMainHomeMeshes`. Restore shutter, hinge, leaf, and activation-zone relative transforms; reset leaf scale to one. Do not couple left/right targets.

- [ ] **Step 4: Run GREEN tests and commit**

Run the Python suite and native automation tests; expect all to pass. Commit `fix: preserve main home closed door layout`.

### Task 2: Aim at the raised shutter strip and preserve clearance

**Files:**
- Modify: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Public/MainHomeInteractiveActor.h`
- Modify: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/MainHomeInteractiveActor.cpp`
- Test: `Plugins/MainHomeInteractive/Source/MainHomeInteractive/Private/Tests/MainHomeInteractiveActorTests.cpp`
- Test: `Tests/test_create_enterable_main_home.py`

**Interfaces:**
- Removes: `ShouldCloseShutterWithoutAim(...)` and its early E-key branch.
- Produces: `ComputeShutterScale(1.0f) == 0.04f` and `GetShutterCollisionMode(alpha,target)` returning query-only at settled-open and query-and-physics otherwise.

- [ ] **Step 1: Add failing shutter behavior tests**

Assert open scale `0.04`, retained height `262 * 0.04 = 10.48 cm`, clear height `262 * 0.96 = 251.52 cm`, and shutter width `230 cm`. Native tests assert settled-open collision is query-only, closing immediately becomes query-and-physics, hit classification still requires the shutter component, and independent door target tests remain unchanged.

- [ ] **Step 2: Run RED tests**

Run focused Python and native automation tests; expect failures at the old 0.03 scale, no query-only collision mode, and the obsolete no-aim close behavior.

- [ ] **Step 3: Implement aimed top-strip interaction**

Change open scale to `0.04f`. At settled-open use `ECollisionEnabled::QueryOnly`; otherwise use `QueryAndPhysics`. Remove the zone-wide close shortcut from `HandleInteractPressed`, so its existing visibility trace must hit the compressed shutter. Reduce the proximity zone horizontal/depth extent while keeping enough vertical overlap with a standing pawn to bind E input.

- [ ] **Step 4: Run GREEN tests and commit**

Run Python and native tests. Commit `fix: target raised shutter strip for closing`.

### Task 3: Build visible procedural aged fallback materials

**Files:**
- Modify: `Scripts/CreateEnterableMainHome.py`
- Test: `Tests/test_create_enterable_main_home.py`
- Modify: `docs/third-party/MainHomeFabMaterials.md`

**Interfaces:**
- Consumes: `ensure_material(material_name, ..., texture_sets)` and `FAB_TEXTURE_SET_BY_MATERIAL`.
- Produces: tagged procedural nodes for world position, noise, dark tint, and lerp; complete Fab sets bypass their output.

- [ ] **Step 1: Extend the fake material graph and add failing tests**

Add fake `MaterialExpressionWorldPosition`, `MaterialExpressionNoise`, and `MaterialExpressionLinearInterpolate` classes. Tests require one tagged node of each type after two fallback runs, verify the fallback lerp feeds Base Color, and verify complete Fab textures still feed Base Color/Normal/Roughness instead.

- [ ] **Step 2: Run RED tests**

Run `python -m unittest Tests.test_create_enterable_main_home -v`; expect missing procedural node tags and flat tint still connected to Base Color.

- [ ] **Step 3: Implement deterministic procedural fallback**

For wall/sign/green metal, reuse tagged expressions through `_find_or_create_tagged_expression`. Feed absolute world position into Noise, use material-specific scale/contrast and a muted dark secondary color, and connect Noise as the alpha of LinearInterpolate between the base tint and aged tint. Keep constant roughness and optional fallback normal. Do not create procedural nodes for unrelated glass/trim/floor materials.

- [ ] **Step 4: Validate idempotency and Fab priority**

Run the material tests twice in one process and assert expression counts remain constant. Update the material documentation with the procedural fallback behavior. Commit `feat: add procedural aged main home materials`.

### Task 4: Full Unreal generation and integration verification

**Files:**
- Regenerate: `Content/MainHome/Materials/*.uasset`
- Regenerate: `Content/MainHome/SM_MainHome_*.uasset`
- Verify: `Scripts/CreateEnterableMainHome.py`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: validated assets and a loadable editor plugin binary.

- [ ] **Step 1: Run all fast tests**

Run `python -m unittest discover -s Tests -p 'test_*.py'`; expect all tests to pass.

- [ ] **Step 2: Build all plugin targets**

Build the plugin for Win64 Editor Development, Game Development, and Game Shipping; expect zero compile/link errors.

- [ ] **Step 3: Run Unreal automation**

Run `MainHomeInteractive.*`; expect every test to pass, including independent doors and aimed shutter strip behavior.

- [ ] **Step 4: Generate twice and inspect assets**

Run `CreateEnterableMainHome.py` twice in the isolated worktree. Verify one tagged actor, exact bounds `((-250,250),(-400,400),(1,401))`, four mesh assets, nine material slots on each, and simple collisions `23/1/1/1`. Inspect material graphs to confirm procedural nodes are active because Fab textures are absent.

- [ ] **Step 5: Merge safely and perform PIE acceptance**

Back up/stash only dirty `Content/MainHome` assets in the main worktree, fast-forward merge, copy the verified editor DLL, and preserve all map/OldShop changes. In PIE verify: closed seam is 0.5 cm, doors remain independent, both-open doorway is passable, raised shutter leaves a visible target strip, aiming at it closes the shutter, and the open shutter passage admits the player. Commit generated assets as `fix: finalize main home materials and interaction`.
