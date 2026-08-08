"""Validate the generated Old Town School Street level and hero interaction."""

from pathlib import Path
import hashlib
import json
import math
import struct
import traceback

import unreal


PROJECT_ROOT = Path(unreal.Paths.project_dir()).resolve()
TARGET_LEVEL = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
SOURCE_MAP_FILE = (
    PROJECT_ROOT
    / "Content/Yastar/Maps/Blockout/L_Chapter01_Blockout.umap"
)
OUTPUT_ROOT = (
    PROJECT_ROOT / "Saved/CodexOutputs/OldTownSchoolStreet"
)
REPORT_PATH = OUTPUT_ROOT / "ValidationReport.json"
BUILD_MANIFEST_PATH = OUTPUT_ROOT / "SceneBuildManifest.json"
GENERATOR_TAG = unreal.Name("OldTownSchoolStreet_Generated")
DETAILED_PROP_ROOT = (
    "/Game/Yastar/OldTownSchoolStreet/Props/Detailed"
)
P3_PROP_ROOT = "/Game/Yastar/OldTownSchoolStreet/Props/P3"
ARCHITECTURAL_MODULE_ROOT = (
    "/Game/Yastar/OldTownSchoolStreet/Architecture/Windows"
)
EXPECTED_SOURCE_MAP_SHA256 = (
    "D15F1749800233495469ACB72E60A7C0D837319EECF57FB14BFF25FDBBD9DE09"
)
CAMERA_LABELS = (
    "CAM_OTS_Hero",
    "CAM_OTS_MainHome",
    "CAM_OTS_Alley",
    "CAM_OTS_StreetDiagonal",
    "CAM_OTS_TopDown",
)
REQUIRED_COMPONENTS = (
    "FixedShell",
    "Shutter",
    "LeftDoorLeaf",
    "RightDoorLeaf",
)
REQUIRED_ZONES = (
    "ShutterInteractionZone",
    "DoorInteractionZone",
)
EXPECTED_SECTION_SLOTS = {
    "FixedShell": list(range(9)),
    "Shutter": [4, 7],
    "LeftDoorLeaf": [4, 7, 8],
    "RightDoorLeaf": [4, 7, 8],
}
EXPECTED_P2_MESH_COUNTS = {
    "SM_P2_VendorTable": 1,
    "SM_P2_Thermos": 1,
    "SM_P2_ChineseStool": 1,
    "SM_P2_Toolbox": 1,
    "SM_P2_GasCylinder": 2,
    "SM_P2_Broom": 1,
    "SM_P2_ChestFreezer": 1,
    "SM_P2_OutdoorSink": 1,
    "SM_P2_TrashBin": 4,
    "SM_P2_PlantPot": 3,
    "SM_P2_CardboardBox": 6,
    "SM_P2_AlleyBench": 1,
    "SM_P2_WashBasin": 1,
    "SM_P2_ACUnit": 5,
    "SM_P2_MeterBox": 4,
    "SM_P2_Bicycle": 3,
    "SM_P2_WallUtilityCluster": 5,
    "SM_P2_StreetLamp": 7,
    "SM_P2_StormDrain": 6,
    "SM_P2_PuddlePatch": 7,
}
EXPECTED_P2_COLLISION_MESHES = {
    "SM_P2_VendorTable",
    "SM_P2_ChestFreezer",
    "SM_P2_OutdoorSink",
    "SM_P2_TrashBin",
    "SM_P2_CardboardBox",
    "SM_P2_AlleyBench",
    "SM_P2_StreetLamp",
}
EXPECTED_SOURCE_TEXTURES = {
    "T_OTS_Asphalt_BaseColor",
    "T_OTS_Asphalt_Normal",
    "T_OTS_Asphalt_Roughness",
    "T_OTS_Concrete_BaseColor",
    "T_OTS_Concrete_Normal",
    "T_OTS_Concrete_Roughness",
    "T_OTS_PaintedPlaster_BaseColor",
    "T_OTS_PaintedPlaster_Normal",
    "T_OTS_PaintedPlaster_Roughness",
    "T_OTS_GreenMetalRust_BaseColor",
    "T_OTS_GreenMetalRust_Normal",
    "T_OTS_GreenMetalRust_Roughness",
}
EXPECTED_P3_MESH_COUNTS = {
    "SM_P3_StaticShutter": 5,
    "SM_P3_SignAssembly": 7,
    "SM_P3_AwningAssembly": 4,
    "SM_P3_SchoolGateLeaf": 2,
    "SM_P3_SchoolGatePost": 2,
    "SM_P3_AlleyCrossbar": 6,
    "SM_P3_SignText_Snack": 1,
    "SM_P3_SignText_General": 2,
    "SM_P3_SignText_Repair": 2,
    "SM_P3_SignText_Hardware": 2,
}
EXPECTED_P3_COLLISION_MESHES = {
    "SM_P3_SchoolGateLeaf",
    "SM_P3_SchoolGatePost",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def vector_list(vector):
    return [
        round(float(vector.x), 3),
        round(float(vector.y), 3),
        round(float(vector.z), 3),
    ]


def rotator_list(rotation):
    return [
        round(float(rotation.pitch), 3),
        round(float(rotation.yaw), 3),
        round(float(rotation.roll), 3),
    ]


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def png_dimensions(path):
    with path.open("rb") as handle:
        header = handle.read(24)
    require(
        len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n",
        "Invalid PNG: {}".format(path),
    )
    return struct.unpack(">II", header[16:24])


def component_report(component):
    static_mesh = component.get_editor_property("static_mesh")
    return {
        "name": component.get_name(),
        "mesh": static_mesh.get_path_name() if static_mesh else None,
        "mobility": str(component.get_editor_property("mobility")),
        "collision_enabled": str(component.get_collision_enabled()),
        "pawn_response": str(component.get_collision_response_to_channel(
            unreal.CollisionChannel.ECC_PAWN
        )),
        "visibility_response": str(
            component.get_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY
            )
        ),
        "relative_location": vector_list(
            component.get_editor_property("relative_location")
        ),
        "relative_scale": vector_list(
            component.get_editor_property("relative_scale3d")
        ),
    }


def zone_report(zone):
    return {
        "name": zone.get_name(),
        "relative_location": vector_list(
            zone.get_editor_property("relative_location")
        ),
        "unscaled_extent": vector_list(zone.get_unscaled_box_extent()),
        "collision_enabled": str(zone.get_collision_enabled()),
        "pawn_response": str(zone.get_collision_response_to_channel(
            unreal.CollisionChannel.ECC_PAWN
        )),
        "generate_overlap_events": bool(
            zone.get_editor_property("generate_overlap_events")
        ),
    }


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    )
    require(levels.load_level(TARGET_LEVEL), "Unable to load target level")

    world = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    require(world is not None, "No editor world is loaded")
    world_path = world.get_path_name()
    require(
        world_path.startswith(TARGET_LEVEL + "."),
        "Loaded the wrong world: {}".format(world_path),
    )

    actors = list(actor_subsystem.get_all_level_actors())
    labels = [actor.get_actor_label() for actor in actors]
    generated = [
        actor for actor in actors if actor.actor_has_tag(GENERATOR_TAG)
    ]
    require(actors, "The target level contains no actors")
    require(generated, "The target level contains no generated actors")
    require("Character" not in labels, "Placed test character still exists")
    require(labels.count("PlayerStart") == 1, "PlayerStart must be unique")
    require(
        labels.count("BP_OTS_MainHomeInteractive") == 1,
        "Interactive MainHome must be unique",
    )
    require(
        all(labels.count(label) == 1 for label in CAMERA_LABELS),
        "Comparison cameras must all exist exactly once",
    )
    require(
        any(
            label.startswith("OTS_StreetEndTJunctionRoadCenter")
            for label in labels
        ),
        "Walkable street-end T-junction is missing",
    )
    require(
        not any(label.startswith("OTS_StreetEndApartment") for label in labels),
        "Obsolete flat street-end apartment still exists",
    )
    require(
        any(label.startswith("OTS_AlleyEndWallExtension") for label in labels),
        "Alley end wall extension is missing",
    )
    require(
        BUILD_MANIFEST_PATH.is_file(),
        "Scene build manifest is missing",
    )
    build_manifest = json.loads(
        BUILD_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    require(
        build_manifest.get("total_actor_count") == len(actors)
        and build_manifest.get("generated_actor_count") == len(generated),
        "Scene actor counts do not match the latest build manifest",
    )

    player = actors[labels.index("PlayerStart")]
    player_location = player.get_actor_location()
    player_rotation = player.get_actor_rotation()
    require(
        abs(player_location.x + 1800.0) < 0.1
        and abs(player_location.y) < 0.1
        and abs(player_location.z - 105.0) < 0.1,
        "PlayerStart transform is incorrect",
    )
    require(
        abs(float(player_rotation.yaw) - 10.0) < 0.1,
        "PlayerStart yaw is incorrect",
    )

    main_home = actors[labels.index("BP_OTS_MainHomeInteractive")]
    main_home_location = main_home.get_actor_location()
    require(
        abs(main_home_location.x - 1025.0) < 0.1
        and abs(main_home_location.y - 920.0) < 0.1
        and abs(main_home_location.z) < 0.1,
        "MainHome transform is incorrect",
    )

    for actor in actors:
        location = actor.get_actor_location()
        scale = actor.get_actor_scale3d()
        require(
            all(math.isfinite(value) for value in (
                float(location.x),
                float(location.y),
                float(location.z),
                float(scale.x),
                float(scale.y),
                float(scale.z),
            )),
            "Non-finite transform: {}".format(actor.get_actor_label()),
        )

    mesh_components = {
        component.get_name(): component
        for component in main_home.get_components_by_class(
            unreal.StaticMeshComponent
        )
    }
    missing_components = [
        name for name in REQUIRED_COMPONENTS if name not in mesh_components
    ]
    require(
        not missing_components,
        "Missing MainHome mesh components: {}".format(missing_components),
    )
    component_reports = [
        component_report(mesh_components[name])
        for name in REQUIRED_COMPONENTS
    ]
    for report in component_reports:
        require(report["mesh"], "{} has no mesh".format(report["name"]))
        require(
            "NO_COLLISION" not in report["collision_enabled"].upper(),
            "{} has no collision".format(report["name"]),
        )
    for name in ("Shutter", "LeftDoorLeaf", "RightDoorLeaf"):
        require(
            "MOVABLE" in str(
                mesh_components[name].get_editor_property("mobility")
            ).upper(),
            "{} is not movable".format(name),
        )

    mesh_editor = unreal.get_editor_subsystem(
        unreal.StaticMeshEditorSubsystem
    )
    mesh_section_reports = []
    for name in REQUIRED_COMPONENTS:
        static_mesh = mesh_components[name].get_editor_property("static_mesh")
        expected_slots = EXPECTED_SECTION_SLOTS[name]
        require(
            mesh_editor.get_number_materials(static_mesh) == 9,
            "{} no longer has the nine stable material slots".format(name),
        )
        actual_slots = [
            int(mesh_editor.get_lod_material_slot(
                static_mesh,
                0,
                section_index,
            ))
            for section_index in range(len(expected_slots))
        ]
        require(
            actual_slots == expected_slots,
            "{} section slots are {}, expected {}".format(
                name,
                actual_slots,
                expected_slots,
            ),
        )
        mesh_section_reports.append({
            "component": name,
            "material_slot_count": 9,
            "lod0_section_count": len(actual_slots),
            "lod0_material_slots": actual_slots,
        })

    box_components = {
        component.get_name(): component
        for component in main_home.get_components_by_class(
            unreal.BoxComponent
        )
    }
    missing_zones = [
        name for name in REQUIRED_ZONES if name not in box_components
    ]
    require(
        not missing_zones,
        "Missing interaction zones: {}".format(missing_zones),
    )
    zone_reports = [
        zone_report(box_components[name]) for name in REQUIRED_ZONES
    ]
    shutter_zone = box_components["ShutterInteractionZone"]
    shutter_extent = shutter_zone.get_unscaled_box_extent()
    require(
        shutter_extent.y >= 300.0 and shutter_extent.z >= 140.0,
        "Shutter interaction zone is too small for two-sided interaction",
    )
    for report in zone_reports:
        require(
            "QUERY_ONLY" in report["collision_enabled"].upper(),
            "{} is not query-only".format(report["name"]),
        )
        require(
            "OVERLAP" in report["pawn_response"].upper(),
            "{} does not overlap Pawn".format(report["name"]),
        )
        require(
            report["generate_overlap_events"],
            "{} overlap events are disabled".format(report["name"]),
        )

    material_assets = unreal.EditorAssetLibrary.list_assets(
        "/Game/Yastar/OldTownSchoolStreet/Materials",
        True,
        False,
    )
    texture_assets = unreal.EditorAssetLibrary.list_assets(
        "/Game/Yastar/OldTownSchoolStreet/Textures",
        True,
        False,
    )
    pole_assets = unreal.EditorAssetLibrary.list_assets(
        "/Game/Yastar/OldTownSchoolStreet/Props/PolyHaven_ElectricityPoles",
        True,
        False,
    )
    detailed_prop_assets = []
    for asset_path in unreal.EditorAssetLibrary.list_assets(
        DETAILED_PROP_ROOT,
        True,
        False,
    ):
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if isinstance(asset, unreal.StaticMesh):
            detailed_prop_assets.append(asset)
    detailed_prop_actors = [
        actor
        for actor in actors
        if actor.get_actor_label().startswith("OTS_P2Prop_")
    ]
    require(
        len(detailed_prop_assets) == len(EXPECTED_P2_MESH_COUNTS),
        "Expected exactly 20 detailed prop Static Mesh assets",
    )
    require(
        len(detailed_prop_actors) == sum(EXPECTED_P2_MESH_COUNTS.values()),
        "P2 detailed prop actor count does not match its contract",
    )
    actual_p2_mesh_counts = {
        mesh_name: 0 for mesh_name in EXPECTED_P2_MESH_COUNTS
    }
    for actor in detailed_prop_actors:
        component = actor.get_component_by_class(
            unreal.StaticMeshComponent
        )
        mesh = (
            component.get_editor_property("static_mesh")
            if component is not None
            else None
        )
        require(
            mesh is not None
            and mesh.get_path_name().startswith(DETAILED_PROP_ROOT + "/"),
            "{} does not use a detailed prop asset".format(
                actor.get_actor_label()
            ),
        )
        mesh_name = mesh.get_name()
        require(
            mesh_name in actual_p2_mesh_counts,
            "Unexpected detailed prop mesh: {}".format(mesh_name),
        )
        actual_p2_mesh_counts[mesh_name] += 1
        should_collide = mesh_name in EXPECTED_P2_COLLISION_MESHES
        require(
            bool(actor.get_actor_enable_collision()) == should_collide
            and (
                component.get_collision_enabled()
                != unreal.CollisionEnabled.NO_COLLISION
            ) == should_collide,
            "{} collision does not match its specification".format(
                actor.get_actor_label()
            ),
        )
    require(
        actual_p2_mesh_counts == EXPECTED_P2_MESH_COUNTS,
        "Detailed prop distribution drifted: {}".format(
            actual_p2_mesh_counts
        ),
    )
    p3_module_assets = []
    for asset_path in unreal.EditorAssetLibrary.list_assets(
        P3_PROP_ROOT,
        True,
        False,
    ):
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if isinstance(asset, unreal.StaticMesh):
            p3_module_assets.append(asset)
    require(
        {
            asset.get_name()
            for asset in p3_module_assets
        } == set(EXPECTED_P3_MESH_COUNTS),
        "P3 module Static Mesh asset set is incomplete",
    )

    p3_module_actors = []
    actual_p3_mesh_counts = {
        mesh_name: 0 for mesh_name in EXPECTED_P3_MESH_COUNTS
    }
    for actor in generated:
        component = actor.get_component_by_class(
            unreal.StaticMeshComponent
        )
        mesh = (
            component.get_editor_property("static_mesh")
            if component is not None
            else None
        )
        if (
            mesh is None
            or not mesh.get_path_name().startswith(P3_PROP_ROOT + "/")
        ):
            continue
        p3_module_actors.append(actor)
        mesh_name = mesh.get_name()
        require(
            mesh_name in actual_p3_mesh_counts,
            "Unexpected P3 module mesh: {}".format(mesh_name),
        )
        actual_p3_mesh_counts[mesh_name] += 1
        should_collide = mesh_name in EXPECTED_P3_COLLISION_MESHES
        require(
            bool(actor.get_actor_enable_collision()) == should_collide
            and (
                component.get_collision_enabled()
                != unreal.CollisionEnabled.NO_COLLISION
            ) == should_collide,
            "{} collision does not match its P3 specification".format(
                actor.get_actor_label()
            ),
        )
    require(
        len(p3_module_actors) == sum(EXPECTED_P3_MESH_COUNTS.values()),
        "P3 module actor count does not match its contract",
    )
    require(
        actual_p3_mesh_counts == EXPECTED_P3_MESH_COUNTS,
        "P3 module distribution drifted: {}".format(
            actual_p3_mesh_counts
        ),
    )
    expected_window_meshes = {
        "SM_OTS_Window_Residential",
        "SM_OTS_Window_School",
    }
    architectural_window_assets = []
    for asset_path in unreal.EditorAssetLibrary.list_assets(
        ARCHITECTURAL_MODULE_ROOT,
        True,
        False,
    ):
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if isinstance(asset, unreal.StaticMesh):
            architectural_window_assets.append(asset)
    require(
        {
            asset.get_name()
            for asset in architectural_window_assets
        } == expected_window_meshes,
        "Architectural window asset set is incomplete",
    )
    architectural_window_actors = []
    for actor in generated:
        component = actor.get_component_by_class(
            unreal.StaticMeshComponent
        )
        mesh = (
            component.get_editor_property("static_mesh")
            if component is not None
            else None
        )
        if mesh is None or mesh.get_name() not in expected_window_meshes:
            continue
        architectural_window_actors.append(actor)
        label = actor.get_actor_label()
        expected_mesh_name = (
            "SM_OTS_Window_School"
            if label.startswith(("OTS_SchoolMain_", "OTS_SchoolWing_"))
            else "SM_OTS_Window_Residential"
        )
        require(
            mesh.get_name() == expected_mesh_name,
            "{} uses {}, expected {}".format(
                label,
                mesh.get_name(),
                expected_mesh_name,
            ),
        )
        require(
            mesh.get_path_name().startswith(
                ARCHITECTURAL_MODULE_ROOT + "/"
            ),
            "{} uses a window mesh outside the module root".format(
                actor.get_actor_label()
            ),
        )
        require(
            component.get_num_materials() >= 5,
            "{} lost its architectural material slots".format(
                actor.get_actor_label()
            ),
        )
        scale = actor.get_actor_scale3d()
        require(
            abs(float(scale.y) - 1.0) < 0.001,
            "{} scaled its authored window depth".format(label),
        )
        require(
            not bool(actor.get_actor_enable_collision())
            and component.get_collision_enabled()
            == unreal.CollisionEnabled.NO_COLLISION,
            "{} architectural window must remain non-colliding".format(
                actor.get_actor_label()
            ),
        )
    require(
        architectural_window_actors,
        "No reusable architectural window actors were found",
    )
    window_labels = [
        actor.get_actor_label()
        for actor in architectural_window_actors
    ]
    for prefix in (
        "OTS_Window_",
        "OTS_SchoolMain_",
        "OTS_SchoolWing_",
        "OTS_PerimeterWindow",
        "OTS_StreetEndWindow_",
    ):
        require(
            any(label.startswith(prefix) for label in window_labels),
            "Architectural window family is missing: {}".format(prefix),
        )
    require(
        build_manifest.get("architectural_window_actor_count")
        == len(architectural_window_actors),
        "Architectural window actor count does not match the build manifest",
    )
    require(len(material_assets) == 26, "Expected exactly 26 materials")
    require(
        len(texture_assets) == len(EXPECTED_SOURCE_TEXTURES),
        "Expected exactly 12 textures",
    )
    texture_asset_names = {
        unreal.EditorAssetLibrary.load_asset(asset_path).get_name()
        for asset_path in texture_assets
    }
    require(
        texture_asset_names == EXPECTED_SOURCE_TEXTURES,
        "Scene texture asset set drifted: {}".format(
            sorted(texture_asset_names)
        ),
    )
    require(len(pole_assets) >= 100, "Imported pole library is incomplete")

    screenshot_reports = []
    for label in CAMERA_LABELS:
        path = OUTPUT_ROOT / "Renders/{}.png".format(label)
        require(path.is_file(), "Missing screenshot: {}".format(label))
        width, height = png_dimensions(path)
        require(
            (width, height) == (1600, 900),
            "Wrong screenshot dimensions for {}".format(label),
        )
        require(
            path.stat().st_size >= 100000,
            "Screenshot is suspiciously small: {}".format(label),
        )
        screenshot_reports.append({
            "label": label,
            "path": str(path),
            "bytes": path.stat().st_size,
            "dimensions": [width, height],
        })

    unreal.SystemLibrary.execute_console_command(
        world,
        "MAP CHECK DONTDISPLAYDIALOG NOCLEARLOG",
    )

    source_map_sha256 = sha256_file(SOURCE_MAP_FILE)
    require(
        source_map_sha256.lower() == EXPECTED_SOURCE_MAP_SHA256.lower(),
        "Protected source map changed: {}".format(source_map_sha256),
    )

    report = {
        "status": "PASS",
        "target_level": TARGET_LEVEL,
        "world_path": world_path,
        "actor_count": len(actors),
        "generated_actor_count": len(generated),
        "player_start_location": vector_list(player_location),
        "player_start_rotation_pitch_yaw_roll": rotator_list(
            player_rotation
        ),
        "main_home_location": vector_list(main_home_location),
        "main_home_components": component_reports,
        "main_home_mesh_sections": mesh_section_reports,
        "interaction_zones": zone_reports,
        "camera_count": len(CAMERA_LABELS),
        "material_count": len(material_assets),
        "texture_count": len(texture_assets),
        "pole_asset_count": len(pole_assets),
        "p2_detailed_prop_asset_count": len(detailed_prop_assets),
        "p2_detailed_prop_actor_count": len(detailed_prop_actors),
        "p2_detailed_prop_distribution": actual_p2_mesh_counts,
        "p3_module_asset_count": len(p3_module_assets),
        "p3_module_actor_count": len(p3_module_actors),
        "p3_module_distribution": actual_p3_mesh_counts,
        "architectural_window_asset_count": len(
            architectural_window_assets
        ),
        "architectural_window_actor_count": len(
            architectural_window_actors
        ),
        "screenshots": screenshot_reports,
        "source_map_sha256": source_map_sha256,
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    unreal.log(
        "OTS_VALIDATE_SUCCESS actors={} generated={} components={} "
        "zones={} screenshots={} report={}".format(
            len(actors),
            len(generated),
            len(component_reports),
            len(zone_reports),
            len(screenshot_reports),
            REPORT_PATH,
        )
    )


try:
    main()
except Exception:
    unreal.log_error(
        "OTS_VALIDATE_FAILED\n{}".format(traceback.format_exc())
    )
    raise
