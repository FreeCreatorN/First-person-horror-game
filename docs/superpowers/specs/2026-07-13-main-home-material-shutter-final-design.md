# Main Home material and shutter final polish design

## Scope

Polish the existing enterable `MainHomeInteractiveActor` without changing the
500 x 800 x 400 cm building envelope or the reference facade proportions.

## Door behavior and seam

- Keep the two doors independent: aiming at one leaf toggles only that leaf.
- Keep the closed center seam at exactly 0.5 cm.
- Do not widen either leaf or couple the two door targets.
- Reset the native hinge locations and door-leaf relative transforms whenever
  meshes are assigned so saved component overrides cannot create a false gap.
- The reported screenshot shows an open leaf and the doorway, not the closed
  0.5 cm seam. Tests must verify the closed world-space leaf bounds.

The full double-door opening is passable when both leaves are opened. A single
65.75 cm leaf opening is intentionally not enlarged because that would change
the facade structure; the user explicitly accepted this limitation.

## Shutter interaction and clearance

- The open shutter remains compressed at its top pivot to a visible strip of
  approximately 10 cm.
- While fully open, the shutter uses query-only collision. This leaves the
  passage physically clear while allowing a visibility trace to hit the strip.
- Remove the current zone-wide, no-aim close shortcut. Closing requires aiming
  at the visible top strip and pressing E.
- Keep only a compact invisible proximity activation zone in front of the
  shutter. It enables input but does not replace the aimed trace target.
- Verify a minimum 230 cm width and 250 cm height of usable open clearance,
  exceeding the current player capsule requirements.

## Materials

Material priority is:

1. Complete Fab Base Color, Normal, and Roughness sets at the documented stable
   paths.
2. Procedural aged fallback when Fab assets are missing.

The fallback must no longer be flat color. Wall/sign materials receive
large-scale low-contrast plaster mottling and darker grime variation. The faded
green metal receives smaller rust/dirt breakup, high roughness, and muted green
variation. Existing nine material slots and material IDs stay unchanged.

The graph must be deterministic and idempotent: repeated generator runs reuse
tagged expressions instead of multiplying nodes. The fallback graph is active
only when a complete Fab set is unavailable.

## Verification

- Python unit tests cover closed seam math, shutter strip height, passage
  clearance, Fab priority, procedural fallback graph, and repeated runs.
- Native automation tests cover query-only open-shutter collision, aimed
  interaction classification, and unchanged independent doors.
- Build the plugin for Editor, Development Game, and Shipping.
- Run the generator twice, verify one actor, exact envelope, four mesh assets,
  nine material slots, and expected simple collision.
- Perform a final PIE check for independent doors, top-strip shutter closure,
  and player passage through the fully open shutter and double doors.
