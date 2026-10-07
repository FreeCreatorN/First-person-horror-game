"""Read the saved architectural attachments without changing the level."""
import json
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir()).resolve()
output = project / 'Saved/CodexOutputs/ArchitectureSeal_20261004'
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert level.load_level('/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet')
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

def vec(p):
    return [float(p.x), float(p.y), float(p.z)]

rows = []
for actor in sub.get_all_level_actors():
    name = actor.get_actor_label()
    if not any(t in name for t in ('Window', 'Door', 'Shutter', 'Facade', 'Cornice', 'Cap')):
        continue
    meshes = []
    for c in actor.get_components_by_class(unreal.StaticMeshComponent):
        if not c.static_mesh:
            continue
        center, extent, _ = unreal.SystemLibrary.get_component_bounds(c)
        center, extent = vec(center), vec(extent)
        meshes.append({'mesh': c.static_mesh.get_path_name(), 'component': c.get_name(),
                       'min': [center[i]-extent[i] for i in range(3)],
                       'max': [center[i]+extent[i] for i in range(3)],
                       'materials': [c.get_material(i).get_path_name() if c.get_material(i) else None
                                     for i in range(c.get_num_materials())]})
    rows.append({'actor': name, 'location': vec(actor.get_actor_location()),
                 'tags': [str(t) for t in actor.tags], 'meshes': meshes})
output.mkdir(parents=True, exist_ok=True)
(output/'AttachmentInventory.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('OTS_ARCHITECTURE_INVENTORY actors={}'.format(len(rows)))
