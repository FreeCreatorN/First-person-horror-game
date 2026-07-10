# Interactive Main Home Shop Design

## Goal

Update the existing 500 x 800 x 400 cm enterable old-town shop to match `333.png`: a wide rolling shutter on the left and a narrower double door with a fixed transom on the right. The shutter and both door leaves are separate movable mesh components inside one reusable actor.

## Fixed envelope and orientation

- Closed-state bounds remain exactly X `[-250, 250]`, Y `[-400, 400]`, Z `[1, 401]` cm.
- The storefront faces `-Y`; actor location Z `0` leaves the model bottom at world Z `1` cm.
- The shell, roof, sign, pillars, shutter guides, shutter hood, thresholds, door frame, and transom stay fixed.
- Door leaves may extend beyond the closed-state envelope while open.

## Storefront proportions

- Left shutter opening: X `[-220, 28]`, width `248` cm.
- Center pillar: X `[28, 68]`, width `40` cm, shifted right as in the reference.
- Right double-door opening: X `[68, 220]`, width `152` cm.
- Shutter-to-door opening ratio: about `1.63:1`.
- Both structural openings occupy Z `[11, 291]` cm.

## Mesh assets

The generator produces four static mesh assets under `/Game/MainHome`:

1. `SM_MainHome_Enterable`: fixed shell and all fixed trim.
2. `SM_MainHome_Shutter`: one movable shutter mesh, including slats and bottom rail; top-pivoted.
3. `SM_MainHome_Door_Left`: left leaf including its panels, glass, and handle; outer-edge pivot.
4. `SM_MainHome_Door_Right`: right leaf including its panels, glass, and handle; outer-edge pivot.

The shutter panel is about `230 x 3 x 262` cm inside the wider 248 cm opening. Each door leaf is about `65 x 3 x 210` cm; the fixed transom occupies the upper portion of the 152 cm door opening. Fixed frames are part of the shell mesh and never move.

All visible layers use explicit depth offsets of at least 0.5 cm. No visible coplanar patches or positive-volume overlaps are allowed between the roof, sign, frames, shutter, door panels, glass, and handles.

## Interaction actor

A small runtime project plugin provides `AMainHomeInteractiveActor`. It owns:

- fixed shell `UStaticMeshComponent`;
- movable shutter `UStaticMeshComponent`;
- left and right hinge `USceneComponent` pivots;
- one movable door-leaf component under each hinge;
- separate shutter and door interaction zones.

The actor binds the `E` key only while the local player is within an interaction zone. A camera trace confirms that this actor and one of its movable components is being targeted, preventing multiple nearby shops from responding to one key press.

- Looking at the shutter toggles it between closed and rolled-up states.
- Looking at a door leaf toggles that leaf independently.
- The shutter uses a low-poly roll-up approximation: it retracts from bottom to top by interpolating Z scale around its top pivot, then disables collision while open.
- Door leaves interpolate yaw around their outside hinges.
- An instance-editable `DoorOpenDirection` setting selects inward or outward opening; the two leaf signs are mirrored.
- Animation duration, interaction distance, and door angle are instance-editable with safe defaults.
- Tick is enabled only while at least one component is moving.

The plugin does not modify the existing player character Blueprint or its input mapping. Direct `E` binding keeps the actor self-contained.

## Materials and look

- Preserve the aged beige wall, faded dark-red lettering, grime, and parapet from the current asset.
- Add faded green metal materials for the shutter and door frames.
- Add dark glass for the transom and door glazing, plus darker metal for handles and shutter rails.
- Keep the low-poly, no-texture workflow; material colors and roughness are sufficient.

## Repeatability and level safety

- Re-running the Python generator updates the four mesh assets and materials in place.
- It places or refreshes at most one interactive shop actor tagged `MainHome_Interactive` when the plugin class is available.
- It never saves the current level and never modifies OldShop assets.

## Verification

- Python tests cover exact closed bounds, 248:152 opening layout, independent asset partitions, pivot placement, doorway clearance, material IDs, collision ownership, and no coplanar/volume overlap.
- Plugin automation tests cover nearest-target selection, shutter state/collision, independent door state, mirrored inward/outward yaw, and tick shutdown.
- UE5.7 command-line generation must finish with zero errors and warnings.
- Manual acceptance: place one actor, operate shutter and both leaves with E, walk through both openings, and confirm inward/outward selection.
