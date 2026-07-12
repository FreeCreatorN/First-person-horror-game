# Main Home Door, Shutter, and Material Polish Design

## Goal

Polish the existing interactive old-town shop without changing its overall
layout: reduce the double-door center gap, make an opened shutter reliably
close on `E` without precise aiming, and replace the flat colors with aged
materials closer to `333.png`.

## Constraints retained

- Closed bounds stay exactly X `[-250,250]`, Y `[-400,400]`, Z `[1,401]` cm.
- The storefront still faces local `-Y`.
- The fixed frame never moves; the shutter and two door leaves remain separate
  components in one `AMainHomeInteractiveActor`.
- Existing maps, player Blueprint, input assets, OldShop assets, and project
  settings remain untouched.
- The generator never saves the current level and remains repeatable.

## Double-door seam

The current closed leaves end at world X `143` and begin at X `145`, leaving a
visible 2 cm center gap. Keep the hinges at X `78` and X `210`, but increase
each leaf from 65 cm to 65.75 cm:

- left leaf: X `[78,143.75]`;
- right leaf: X `[144.25,210]`;
- final center gap: `0.5 cm`.

Add a narrow raised center stile inside each leaf's bounds. The stiles move
with their own leaves, remain depth-offset from the door panel, and never
overlap each other or the fixed frame. Door pivots, swing directions, opening
angle, and collision ownership do not change.

## Shutter closing interaction

The current shutter becomes non-colliding when fully open, after which the
only close target is a hidden 6 cm strip near the top. A normal camera ray
through the empty opening therefore misses the actor and `E` appears broken.

Remove the hidden visibility-blocking trace strip. While the shutter is open
or opening and the local pawn overlaps `ShutterInteractionZone`, any `E` press
closes the shutter immediately, regardless of camera aim. When the shutter is
closed, opening it still requires looking at the real shutter, preventing
accidental activation. Closing restores shutter collision before motion starts.

The door interaction path remains camera-targeted and independent.

## Aged external materials

Use Fab resources first. The preferred free assets are Quixel Megascans
`Construction Plaster` (listing `c61bd44e-ce01-47ae-b0b8-eb0f4ff3cc60`) and
`Rusty Metal Sheet` (listing `54c7decd-5aac-491c-ad3f-cdfde8d4b1c8`). Import
them through the UE Fab integration, keep the selected texture maps under
`/Game/MainHome/Textures`, and record the Fab URLs and applicable license
beside them. Acquiring or adding a Fab asset to an account remains an explicit
user action; the generator never purchases or downloads marketplace content.

Use approximately 1K texture sets to keep this low-poly building inexpensive:

- aged beige plaster: base color, normal, and roughness;
- faded painted metal with restrained rust: base color, normal, and roughness;
- optional subtle dirty-glass variation if a suitable lightweight source is
  available.

Reuse the existing material names and slot order so generated meshes and the
runtime actor keep stable assignments:

- wall and sign materials use the plaster texture with different warm beige
  tints and roughness;
- shutter, double doors, and fixed storefront frame use faded olive-green
  painted metal with muted rust, matching the reference;
- stains and lower-wall grime remain gray-brown, not black;
- trim stays dark weathered metal and glass stays dark but readable.

Use mesh UVs on movable parts so textures do not swim while the doors rotate or
the shutter retracts. Material setup must update in place without destructively
deleting expressions referenced by loaded assets. If a texture is missing, the
generator uses an improved aged procedural/constant-color fallback and emits a
clear warning. A non-Fab external download is not used unless the user later
approves it explicitly.

## Verification

- A geometry regression test requires the exact 0.5 cm closed center gap and
  proves both leaves stay inside the fixed door frame.
- C++ automation covers close-without-aim while in the shutter zone, collision
  restoration, normal targeted opening, and no effect outside the zone.
- Existing independent-door, inward/outward, input, bounds, overlap, material
  slot, collision, and repeat-run tests remain green.
- Run a real UE5.7 plugin build, all automation tests, generator repeat check,
  and serialized-asset inspection.
- Final manual acceptance: in PIE, open the shutter, look anywhere, press `E`
  while still near the shutter, and confirm it closes; inspect the seam and
  aged material balance under the project's actual lighting.
