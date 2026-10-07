"""Read the saved street level without saving or changing its packages."""
import json
from pathlib import Path
import unreal

level = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(level)
actors = []
xyz = lambda v: [float(v.x), float(v.y), float(v.z)]
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    row = {"label": actor.get_actor_label(), "class": actor.get_class().get_name(),
           "location": xyz(actor.get_actor_location()), "scale": xyz(actor.get_actor_scale3d()),
           "yaw": float(actor.get_actor_rotation().yaw), "folder": str(actor.get_folder_path()),
           "tags": [str(t) for t in actor.tags]}
    components = []
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.static_mesh
        if not mesh:
            continue
        origin, extent = actor.get_actor_bounds(False)
        lo, hi = component.get_local_bounds()
        components.append({"mesh": mesh.get_path_name(), "min": xyz(lo), "max": xyz(hi),
                           "world_origin": xyz(origin), "world_extent": xyz(extent),
                           "collision": str(component.get_collision_enabled()),
                           "materials": [component.get_material(i).get_path_name() if component.get_material(i) else None
                                         for i in range(component.get_num_materials())]})
    row["meshes"] = components
    actors.append(row)
root = "/Game/Yastar/Meshes"
assert unreal.EditorAssetLibrary.does_directory_exist(root), "User mesh root missing"
output = Path(unreal.Paths.project_dir()) / "Saved/CodexOutputs/EnterableStreet_20261002"
output.mkdir(parents=True, exist_ok=True)
(output / "SourceInventory.json").write_text(json.dumps({"level": level, "actors": actors,
    "mesh_root": root, "existing_assets": [str(a) for a in unreal.EditorAssetLibrary.list_assets(root)]}, ensure_ascii=False, indent=2), encoding="utf-8")
unreal.log("OTS_CONVERSION_INVENTORY_SUCCESS actors={}".format(len(actors)))
