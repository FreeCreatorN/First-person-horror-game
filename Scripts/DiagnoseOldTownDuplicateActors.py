"""Inspect same-position static actors in the saved street without saving it."""
from collections import defaultdict
import json
from pathlib import Path
import unreal

target = "/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(target)
groups = defaultdict(list)
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    components = actor.get_components_by_class(unreal.StaticMeshComponent)
    if len(components) != 1 or components[0].static_mesh is None:
        continue
    component = components[0]
    p = actor.get_actor_location()
    key = (component.static_mesh.get_path_name(), *(round(v, 3) for v in (p.x, p.y, p.z)))
    origin, extent = actor.get_actor_bounds(False)
    groups[key].append({"name": actor.get_name(), "label": actor.get_actor_label(),
                        "mesh": key[0], "location_cm": list(key[1:]),
                        "bounds_center": [origin.x, origin.y, origin.z],
                        "bounds_extent": [extent.x, extent.y, extent.z],
                        "materials": [component.get_material(i).get_path_name() if component.get_material(i) else None
                                      for i in range(component.get_num_materials())]})
duplicates = [rows for rows in groups.values() if len(rows) > 1]
output = Path(unreal.Paths.project_dir()).resolve() / "Saved/CodexOutputs/EnterableStreet_20261002/DuplicateActors.json"
output.write_text(json.dumps(duplicates, ensure_ascii=False, indent=2), encoding="utf-8")
unreal.log("OTS_DUPLICATE_DIAGNOSTICS groups=" + str(len(duplicates)))
