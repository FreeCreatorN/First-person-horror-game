"""Read one persisted map and export a complete text snapshot; never save it."""
import hashlib
import json
import os
import re
import traceback
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = ROOT / 'Saved/CodexOutputs/HotelIntegration_20261004'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def main():
    name = os.environ['OTS_MERGE_SNAPSHOT_NAME']
    source = Path(os.environ['OTS_MERGE_SNAPSHOT_SOURCE']).resolve()
    assert re.fullmatch(r'[A-Za-z0-9_]+', name), name
    assert source.is_relative_to(ROOT) and source.suffix == '.umap', source
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = sha(source)
    world = unreal.EditorLoadingAndSavingUtils.load_map(str(source))
    assert world, str(source)
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    rows = []
    for actor in actors:
        rotation = actor.get_actor_rotation()
        row = {'label': actor.get_actor_label(), 'name': actor.get_name(),
               'class': actor.get_class().get_path_name(),
               'location': xyz(actor.get_actor_location()),
               'rotation': [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)],
               'scale': xyz(actor.get_actor_scale3d()), 'folder': str(actor.get_folder_path()),
               'tags': [str(t) for t in actor.tags], 'components': []}
        for component in actor.get_components_by_class(unreal.SceneComponent):
            cr = component.get_editor_property('relative_rotation')
            cr = [float(cr.pitch), float(cr.yaw), float(cr.roll)]
            parent = component.get_attach_parent()
            entry = {'name': component.get_name(), 'class': component.get_class().get_path_name(),
                     'parent': parent.get_name() if parent else None,
                     'relative_location': xyz(component.get_editor_property('relative_location')),
                     'relative_rotation': cr,
                     'relative_scale': xyz(component.get_editor_property('relative_scale3d'))}
            if isinstance(component, unreal.StaticMeshComponent):
                entry.update(mesh=component.static_mesh.get_path_name() if component.static_mesh else None,
                             materials=[component.get_material(i).get_path_name() if component.get_material(i) else None
                                        for i in range(component.get_num_materials())],
                             collision=str(component.get_collision_enabled()))
            row['components'].append(entry)
        rows.append(row)
    task = unreal.AssetExportTask()
    task.object = world
    task.filename = str(OUTPUT / (name + '.t3d'))
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.selected = False
    task.exporter = unreal.LevelExporterT3D()
    exported = bool(unreal.Exporter.run_asset_export_task(task))
    assert exported, 'Full map T3D export failed: ' + str(task.errors)
    assert sha(source) == before, 'Source map changed while inspecting'
    result = {'source': str(source), 'source_sha256': before, 'world': world.get_path_name(),
              'actor_count': len(rows), 'actors': rows, 'full_text_export': task.filename,
              'source_unchanged': True}
    (OUTPUT / (name + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('OTS_MERGE_SNAPSHOT_PASS name={} actors={} source_unchanged=True'.format(name, len(rows)))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / 'SnapshotFailure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
