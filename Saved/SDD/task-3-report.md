# Task 3 Report: Reference-oriented material fallback

## Scope and outcome

- Updated only the Task 3 generator/test files, two new source-art PNGs, and this report.
- Did not modify or stage any `Content/MainHome` `.uasset` file.
- Preserved all nine material names and IDs.
- Preserved the complete-Fab-set branch as the first-priority material path.

## TDD evidence

### RED

Focused command:

```powershell
python -m unittest Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_reference_texture_paths_node_tags_and_material_mapping_are_stable Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_load_reference_fallback_textures_returns_existing_texture2d_assets Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_reference_palette_matches_exact_linear_targets Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_reference_palette_is_warm_bright_and_low_contrast Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_missing_fab_builds_idempotent_procedural_aged_color_graph Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_complete_fab_set_binds_tagged_nodes_and_reuses_them Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_reference_fallback_reuses_tagged_nodes_and_keeps_fab_nodes Tests.test_create_enterable_main_home.EnterableMainHomeGeometryTests.test_generation_iterates_all_asset_definitions_and_logs_design_summary
```

Observed result: `EEFFEEEF`; 8 tests ran with 3 failures and 5 errors.

Expected failure causes:

- `REFERENCE_TEXTURE_ASSET_PATHS` and `load_reference_fallback_textures()` did not exist.
- `ensure_material()` did not accept `reference_textures`.
- The old wall red channel was `0.46`, below the new `0.58` minimum.
- The generator did not load or pass reference fallback textures.

### GREEN

- Focused material tests: 8/8 passed.
- Full command: `python -m unittest discover -s Tests -p 'test_*.py'`
- Full result: 64/64 passed with no failures or errors.
- `git diff --check`: passed.

## Source textures

Reference: `C:/Users/aa131/Downloads/333.png`.

Built-in image generation was used for both assets. Each selected result was
given one targeted seamless-tiling revision, resized to the required 1024 x
1024 RGB PNG, and finished with a deterministic wrapped edge crossfade after
a 2 x 2 preview exposed a residual horizontal seam.

### Aged plaster prompt

> Create a single square 1024 x 1024 seamless tileable PBR base-color/albedo texture only, visually derived from the warm aged storefront plaster in the supplied reference image. Orthographic flat surface scan, warm ivory-beige old plaster, broad low-contrast gray-brown mottling, restrained sparse grime character distributed subtly (not a directional bottom gradient), fine worn mineral texture and faint irregular trowel marks. The left, right, top, and bottom edges must match perfectly for repetition. Uniform diffuse color information only: absolutely no directional illumination, no ambient occlusion, no highlights, no specular shine, no cast shadow, no baked shadow, no perspective, no objects, no architecture, no text, no symbols, no border, no frame, no watermark. Avoid deep cracks and high-contrast stains. Game-ready albedo map, full-bleed surface texture.

Final asset:

- `SourceArt/MainHome/T_MainHome_AgedPlaster_BaseColor.png`
- 1024 x 1024, 24-bit RGB PNG
- Broad warm ivory-beige mottling remains low contrast; no lighting, text,
  frame, or baked shadow is present.

### Old green metal prompt

> Create a single square 1024 x 1024 seamless tileable PBR base-color/albedo texture only, visually derived from the faded green painted metal doors and shutter in the supplied reference image. Orthographic flat surface scan of aged painted sheet metal: muted faded dark green paint, very subtle low-contrast tonal variation, sparse small brown-orange rust chips, tiny paint losses and short fine scratches. No corrugation, no slats, no panels, no seams, no bolts, because all slats and panel forms are modeled geometry. The left, right, top, and bottom edges must match perfectly for repetition. Uniform diffuse color information only: absolutely no directional illumination, no ambient occlusion, no highlights, no specular shine, no cast shadow, no baked shadow, no perspective, no objects, no architecture, no text, no symbols, no border, no frame, no watermark. Keep rust restrained and small, avoid large flakes and high contrast. Game-ready albedo map, full-bleed surface texture.

Final asset:

- `SourceArt/MainHome/T_MainHome_OldGreenMetal_BaseColor.png`
- 1024 x 1024, 24-bit RGB PNG
- Muted green paint has sparse small rust chips and fine scratches; no
  corrugation, lighting, text, frame, or baked shadow is present.

### Visual inspection

- Inspected both selected single-tile outputs at full size.
- Inspected both final assets as 2 x 2 tiled previews after seam finishing.
- No hard horizontal or vertical tile boundary remained in the final previews.
- Plaster stays brighter and warmer than the metal; metal remains green-led
  with restrained brown-orange wear.

## Implementation details

- Added exact reference texture asset paths and material-to-texture mapping.
- Added `load_reference_fallback_textures()` with existing-asset and
  `Texture2D` type filtering.
- Complete Fab base-color/normal/roughness sets still win without creating
  reference fallback nodes.
- In the incomplete-Fab path, one tagged reference texture sample and one
  tagged multiply node are reused, then feed the existing aged-color Lerp.
- Missing reference textures reconnect the tint constant as the final fallback.
- Repeated runs and Fab-to-reference switching retain exactly one node for each
  tagged description and do not delete material expressions.
- Reference base color is connected only through RGB to the tint multiply; it
  is never connected to Normal.
- Wall/sign noise maximum is `0.18`; metal noise maximum is `0.20`.

## Changed files

- `Scripts/CreateEnterableMainHome.py`
- `Tests/test_create_enterable_main_home.py`
- `SourceArt/MainHome/T_MainHome_AgedPlaster_BaseColor.png`
- `SourceArt/MainHome/T_MainHome_OldGreenMetal_BaseColor.png`
- `Saved/SDD/task-3-report.md`

## Self-review

- Confirmed reference fallback selection occurs only after a complete Fab set
  check fails.
- Confirmed the original Fab node tags and three-map connections are unchanged.
- Confirmed stable tagged expression reuse across repeated generation.
- Confirmed reciprocal-centimeter Noise scale and distinct graph positions are
  retained.
- Confirmed material IDs/ordering remain stable and no `Content/MainHome`
  assets are part of this task.
