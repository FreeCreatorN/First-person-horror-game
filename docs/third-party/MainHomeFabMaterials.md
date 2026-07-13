# Main Home Fab materials

Main Home supports two free Quixel resources from Fab as optional source
textures. The generator does not purchase, add, or download either listing.
Acquire and import them manually in Unreal Editor when their terms are
acceptable for the project.

| Material set | Source | Fab listing |
| --- | --- | --- |
| Construction Plaster | Quixel, free | https://www.fab.com/listings/c61bd44e-ce01-47ae-b0b8-eb0f4ff3cc60 |
| Rusty Metal Sheet | Quixel, free | https://www.fab.com/listings/54c7decd-5aac-491c-ad3f-cdfde8d4b1c8 |

## Stable import targets

Import or rename the required texture assets to these exact Unreal asset
paths. Do not change the paths in the generator to match arbitrary Fab import
names.

### Construction Plaster

- Base Color: `/Game/MainHome/Textures/T_Fab_ConstructionPlaster_BaseColor`
- Normal: `/Game/MainHome/Textures/T_Fab_ConstructionPlaster_Normal`
- Roughness: `/Game/MainHome/Textures/T_Fab_ConstructionPlaster_Roughness`

The complete set is used by `M_MainHome_Wall` and `M_MainHome_Sign`.

### Rusty Metal Sheet

- Base Color: `/Game/MainHome/Textures/T_Fab_RustyMetalSheet_BaseColor`
- Normal: `/Game/MainHome/Textures/T_Fab_RustyMetalSheet_Normal`
- Roughness: `/Game/MainHome/Textures/T_Fab_RustyMetalSheet_Roughness`

The complete set is used by `M_MainHome_FadedGreenMetal`.

## Complete-set and fallback rule

A Fab set is enabled only when its Base Color, Normal, and Roughness assets all
exist and load successfully. Base Color is multiplied by the existing aged
tint, the Normal texture uses the normal sampler type, and Roughness feeds the
material roughness input.

If any required asset is absent, the entire affected set is omitted. The
generator emits one concise warning listing the missing stable paths and uses
an aged procedural fallback instead of a flat color. Wall and sign materials
blend their base tint with broad world-space plaster grime; faded green metal
uses smaller-scale brown rust and dirt breakup. Roughness remains high and
matte so the storefront does not look newly painted.

Repeated runs reuse tagged Fab and procedural nodes without deleting
expressions. If an enabled Fab set later becomes unavailable, the procedural
fallback is reconnected and the dormant Fab nodes remain in the material graph.
When the complete Fab set returns, its Base Color, Normal, and Roughness take
priority again.
