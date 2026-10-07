"""Continue the saved old-town level while the user edits L_Main separately."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import traceback
import unreal

PROJECT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = PROJECT / "Saved/CodexOutputs/EnterableStreet_20261002"
TARGET = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
sys.path.insert(0, str(PROJECT / "Scripts"))


def write_report(name, report):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def add_review_cameras(actor_subsystem, report, placements):
    plans = []
    for label, camera_label in (("BLK_L_Enter_C_Mass", "CAM_Enterable_ShopEntry"),
                                ("Blockout_School_MainBuilding", "CAM_Enterable_SchoolEntry")):
        b = next(item for item in report["buildings"] if item["label"] == label)
        outside, inside = b["primary_entry_route"]
        direction = [inside[i] - outside[i] for i in range(2)]
        length = sum(v*v for v in direction) ** .5
        position = [outside[i] - direction[i] * 140.0 / length for i in range(2)] + [outside[2] + 160.0]
        plans.append((camera_label, position, [inside[0], inside[1], inside[2] + 135.0]))
    b = next(item for item in report["buildings"] if item["label"] == "BLK_L_Enter_C_Mass")
    stair = b["stairs"][0]["foot_waypoints"]
    ground = b["ground_route"]
    position = ground[1][:2] + [ground[1][2] + 160.0]
    target = stair[len(stair)//2][:2] + [stair[len(stair)//2][2] + 70.0]
    plans.append(("CAM_Enterable_Stair", position, target))
    bedrooms = [p for p in placements if p["building"] == b["label"] and p["group"] == "Bed"]
    if bedrooms:
        bed = bedrooms[0]["location_cm"]
        position = [b["interior_max"][0] - 330.0, b["interior_max"][1] - 230.0, b["floor_z"][1] + 155.0]
        plans.append(("CAM_Enterable_Bedroom", position, [bed[0], bed[1], b["floor_z"][1] + 65.0]))
    by_label = {a.get_actor_label(): a for a in actor_subsystem.get_all_level_actors()}
    for label, position, target in plans:
        actor = by_label.get(label)
        rotation = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position), unreal.Vector(*target))
        if actor is None:
            actor = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*position), rotation, False)
        actor.set_actor_label(label)
        actor.set_actor_location(unreal.Vector(*position), False, False)
        actor.set_actor_rotation(rotation, False)
        actor.set_folder_path(unreal.Name("OldTownSchoolStreet/EnterableReview"))
        actor.get_component_by_class(unreal.CameraComponent).set_editor_property("field_of_view", 85.0)
    return [plan[0] for plan in plans]


def ensure_walkable_ground(actor_subsystem):
    """Give level-local walk surfaces exact collision without editing Engine Cube."""
    mesh = unreal.load_asset("/Game/Yastar/Meshes/hOUSE/SM_OTS_Enterable_FloorSlab")
    assert mesh, "Structural floor module missing"
    repaired = []
    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if not any(word in label for word in ("Road", "Sidewalk", "Ground", "Apron", "SchoolEntranceStep")):
            continue
        components = actor.get_components_by_class(unreal.StaticMeshComponent)
        if len(components) != 1:
            continue
        component = components[0]
        if not component.static_mesh or component.static_mesh.get_path_name() != "/Engine/BasicShapes/Cube.Cube":
            continue
        material = component.get_material(0)
        component.set_static_mesh(mesh)
        component.set_material(0, material)
        actor.set_actor_enable_collision(True)
        component.set_collision_object_type(unreal.CollisionChannel.ECC_WORLD_STATIC)
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        component.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
        repaired.append(label)
    return repaired


def main():
    from ConvertOldTownBuildings import convert_buildings
    from ExtractOldTownReusableAssets import extract_reusable_assets
    from ImportOldTownBlenderFurniture import import_furniture, place_furniture
    from ValidateEnterableStreet import validate_main_home, refresh_world_collision
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # A recovery file outside Content is not another UE map asset. Keep the
    # first on-disk version; subsequent validation retries never replace it.
    saved_map = PROJECT / "Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
    recovery = OUTPUT / "Before_L_OldTownSchoolStreet.umap"
    if not recovery.exists():
        shutil.copy2(saved_map, recovery)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert levels.load_level(TARGET), "Target level failed to load"
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert world.get_path_name().startswith(TARGET + "."), "Refusing to edit another level"
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    refresh_world_collision(list(actor_subsystem.get_all_level_actors()))
    before_home = validate_main_home(list(actor_subsystem.get_all_level_actors()))
    buildings = convert_buildings(actor_subsystem)
    walk_surfaces = ensure_walkable_ground(actor_subsystem)
    write_report("BuildingReport.json", buildings)
    unreal.log("OTS_BUILDING_CONVERSION_DONE")
    assets = extract_reusable_assets(actor_subsystem)
    write_report("AssetReport.json", assets)
    unreal.log("OTS_MODULAR_EXTRACTION_DONE")
    furniture, furniture_import = import_furniture()
    write_report("BlenderImportReport.json", furniture_import)
    placements = place_furniture(actor_subsystem, furniture, buildings)
    review_cameras = add_review_cameras(actor_subsystem, buildings, placements)
    actors = list(actor_subsystem.get_all_level_actors())
    # Re-register bodies after mesh swaps; commandlets do not tick the editor
    # to update every existing component's physics state automatically.
    refreshed_components = refresh_world_collision(actors)
    after_home = validate_main_home(actors)
    assert before_home == after_home, "MainHome interaction structure changed"
    from ValidateEnterableStreet import validate_buildings
    validation = validate_buildings(world, actors, buildings)
    write_report("CollisionValidation.json", validation)
    assert validation["passed"], "World collision checks failed; target level was not saved"
    assert levels.save_current_level(), "Unable to save converted street level"
    report = {"status": "PASS", "target_level": TARGET, "actor_count": len(actors),
              "buildings": buildings, "assets": assets, "blender_imports": furniture_import,
              "furniture_placements": placements, "collision": validation, "main_home": after_home,
              "review_cameras": review_cameras,
              "walkable_surface_repairs": walk_surfaces,
              "refreshed_collision_components": refreshed_components,
              "map_sha256": hashlib.sha256(saved_map.read_bytes()).hexdigest()}
    write_report("BuildReport.json", report)
    unreal.SystemLibrary.execute_console_command(world, "MAP CHECK DONTDISPLAYDIALOG NOCLEARLOG")
    unreal.log("OTS_ENTERABLE_STREET_SUCCESS actors={}".format(len(actors)))
    return report


if __name__ == "__main__":
    try:
        main()
    except Exception:
        unreal.log_error("OTS_ENTERABLE_STREET_FAILED\n" + traceback.format_exc())
        raise
