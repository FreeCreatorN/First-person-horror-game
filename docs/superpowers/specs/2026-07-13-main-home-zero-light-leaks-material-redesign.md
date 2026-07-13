# Main Home Zero-Light-Leak and Material Redesign

## Goal

Update the enterable Main Home storefront so closed movable panels and the fixed transom glazing show no black light-leak gaps against their fixed frames. Rework the generated materials toward the supplied `333.png` reference while preserving the existing dimensions, one-actor structure, collision behavior, and independent interaction rules.

## Confirmed visual rule

Use a concealed-edge construction rather than mathematical edge contact. Panels sit behind the fixed frame in Y and extend 0.5-1 cm underneath the frame, guides, threshold, or transom bar. The fixed trim masks the overlap. No decorative patch may be coplanar with another surface.

## Geometry changes

All measurements remain in centimeters and the full actor stays inside X=-250..250, Y=-400..400, Z=1..401.

### Roller shutter

- Current closed gaps: 1 cm at each side and 1 cm above the threshold.
- Extend the panel from X=-211..19 to X=-213..21, hiding exactly 1 cm beneath each guide's inner edge.
- Extend the closed bottom from Z=15 to Z=14, hiding exactly 1 cm beneath the threshold whose top is Z=15.
- Keep the panel top at the top-box lower edge so the raised interaction strip remains visible and traceable.
- Preserve the raised scale, Pawn-ignore/Visibility-block collision behavior, and top-strip-only close interaction.

### Double doors

- Current perimeter gaps: 2 cm at both side frames, 1 cm above the threshold, and 2 cm below the transom bar.
- Use closed left-leaf bounds X=75..143.75 and right-leaf bounds X=144.25..213. The outer 1 cm of each leaf is concealed behind its side frame; the existing 0.5 cm center division remains unchanged.
- Use closed door-leaf bounds Z=14..228. This hides exactly 1 cm behind the threshold at the bottom and exactly 1 cm behind the transom bar at the top.
- Preserve the intentional center division between the two leaves.
- Preserve independent aiming and toggling: a hit on one leaf changes only that leaf.

### Transom glazing

- Current gaps: 4 cm on both sides and 2 cm at both top and bottom.
- Use transom-glass bounds X=75..213 and Z=236..282, hiding exactly 1 cm behind the left/right frame, top frame, and transom bar on every edge.
- Keep the glass behind the fixed frame in Y so no coplanar overlap or Z-Fighting is introduced.

## Material target

Match the supplied reference palette rather than the current dark, high-contrast fallback:

- Exterior wall/sign: warm aged ivory-beige plaster, high roughness, broad low-contrast grime, slightly darker lower wall.
- Shutter/doors/frame: muted deep old green, controlled brown-orange rust concentrated at edges, slats, handles, and lower areas; avoid full-surface orange noise.
- Glass: charcoal gray-green rather than pure black, with low roughness and restrained reflection.
- Trim/stain: warm gray-brown, never near black.
- Lettering: faded dark red-brown.

Complete Fab texture sets remain the first choice. If they are absent, the procedural fallback must use brighter base colors, lower grime contrast, and broader masks. Repeated runs must reuse tagged nodes and must not accumulate expressions.

The generator will not add a light Actor or change the level's lighting. Material verification therefore covers graph connections, palette values, and texture/fallback selection; final apparent brightness remains affected by the level lighting and exposure.

## Regeneration and stale state

- Regenerate the four Main Home mesh assets and all material assets in place.
- Re-running the script updates the single tagged `MainHomeInteractiveActor` and resets component relative transforms so stale per-instance overrides cannot retain old gaps.
- Because the currently running editor has loaded an older plugin DLL, the final verified DLL must be installed while Unreal Editor is closed before the acceptance check.

## Verification

- Python geometry tests assert the concealed overlap bounds for shutter, both door leaves, and transom glass.
- Existing boundary, collision ownership, material ID, Fab-first, idempotency, and no-Z-Fighting tests remain green.
- UE integration tests load the real generated assets, assert frame-underlap rather than perimeter gaps, preserve independent door dispatch, and trace the raised shutter strip.
- Run the generator twice in one UE process and confirm one tagged Actor, stable material node counts, exact overall bounds, and expected simple collision counts.
- Build the plugin for UnrealEditor Development, UnrealGame Development, and UnrealGame Shipping on Win64.

## Acceptance criteria

1. With shutter and doors closed, no background is visible between any movable panel and its fixed frame.
2. The transom glass has no visible gap to its fixed frame or lower bar.
3. Doors remain independently interactive; the shutter still closes only when aiming at its raised top strip.
4. Shutter and open double doors remain traversable by the project player capsule.
5. Materials visually follow the supplied warm plaster and old green metal reference without the current near-black/high-contrast fallback.
6. No component exceeds the 500 x 800 x 400 cm outer envelope.
