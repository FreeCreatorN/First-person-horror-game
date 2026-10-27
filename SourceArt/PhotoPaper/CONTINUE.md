# PhotoPaper — completed 2026-10-26

User requested a photo-paper model to accompany the camera. Finished model is open in Blender and imported into UE at /Game/Yastars/Mesh/PhotoPaper/SM_PhotoPaper.

- 8.8 x 10.8 cm white-border card, 0.35 mm physical thickness, gently curled lower-right corner and small bevels/rounded corners.
- Photo area is 7.8 x 7.8 cm, with source UV0 covering 0–1. Single closed mesh: 720 triangles, zero non-manifold edges or zero-area UV triangles, one custom convex hull.
- Three slots: 0 Frame, 1 Photo Image, 2 Back. Slot1 uses Materials/MI_PhotoPaper_Image; exposed PhotoTexture can be replaced by a photo Texture2D or set per dynamic material instance for a Render Target. No emissive material connection.
- Six UE packages: mesh, three parent materials, one photo material instance, one blank placeholder texture. The placeholder is neutral gray and intentionally contains no photograph.
- Current effective photo texture coordinates use unconnected ConstCoordinate=0. An initial attempt to connect a named coordinate input failed before package saves; evidence is retained in FailedUVConnection. The corrected import uses a verified public const_coordinate property.
- Import exited normally with code0 and fresh successful report. verify_final.py prints PHOTOPAPER_FINAL_VERIFIED True. Source/FBX/texture/render/package hashes, material parameters/MI override, source photo UV, geometry/bounds/slots/collision, and protected UI/maps/Config all passed.
- No UE editor or shader workers remained after the import helper exited. Blender GUI remains open on PhotoPaper.blend. Its previous Camera session was preserved as Saved/CodexBackups/BeforePhotoPaper_20261026/Camera_125943.blend.
- Main PhotoPaper_Preview.png, back and edge renders were visually checked. Edge camera height was corrected and validation hash refreshed before the successful import.
- README.md documents replacement of PhotoTexture. Camera and its independent shutter assets are separate and were not modified by this task.
