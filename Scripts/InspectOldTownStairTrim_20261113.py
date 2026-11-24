"""Inspect the current saved original level, including its saved viewport."""
import hashlib
import json
import re
from pathlib import Path
import sys
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
OUTPUT = ROOT / 'Saved/CodexOutputs/OldTownStairTrim_20261113'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
ALT = ROOT / 'Content/CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap'


def sha(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def write(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def xyz(v):
    return [float(v.x), float(v.y), float(v.z)]


def bounds(component):
    center, extent, _ = unreal.SystemLibrary.get_component_bounds(component)
    c, e = xyz(center), xyz(extent)
    return [[c[i]-e[i] for i in range(3)], [c[i]+e[i] for i in range(3)]]


def load():
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert levels.load_level(TARGET), TARGET
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert world.get_path_name().startswith(TARGET + '.'), world.get_path_name()
    return levels, actors, world


def main():
    current_sha = sha(MAP)
    _, actor_sys, world = load()
    ini = (ROOT / 'Saved/Config/WindowsEditor/EditorPerProjectUserSettings.ini').read_text(encoding='utf-8-sig')
    settings = next(line for line in ini.splitlines() if line.startswith('EditorViews=') and TARGET in line)
    view = settings.split('"' + TARGET + '.L_OldTownSchoolStreet"', 1)[1].split('),("/', 1)[0]
    values = re.findall(r'CamPosition=\(X=([\d.-]+),Y=([\d.-]+),Z=([\d.-]+)\),CamRotation=\(Pitch=([\d.-]+),Yaw=([\d.-]+),Roll=([\d.-]+)\)', view)
    views = [{'position': [float(v) for v in row[:3]], 'rotation': [float(v) for v in row[3:]]} for row in values]
    actors = list(actor_sys.get_all_level_actors())
    rows = []
    for actor in actors:
        name = actor.get_actor_label()
        if not name.startswith('OTS_HotelV4_'):
            continue
        for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
            if not comp.static_mesh:
                continue
            lo, hi = bounds(comp)
            if not (lo[0] < 10060.0 and hi[0] > 9800.0):
                continue
            if not any(lo[1] < edge[1] and hi[1] > edge[0] for edge in ((-3380,-3020),(790,1380),(3020,3380))):
                continue
            rows.append({'label':name, 'actor':actor.get_path_name(), 'component':comp.get_name(),
                         'mesh':comp.static_mesh.get_path_name(), 'bounds':[lo,hi],
                         'materials':[comp.get_material(i).get_path_name() if comp.get_material(i) else None for i in range(comp.get_num_materials())]})
    write('Inspection.json', {'target':TARGET, 'map_sha256':current_sha, 'version2_sha256':sha(ALT),
                              'viewport':views, 'actors':len(actors), 'stair_components':rows})
    sys.path.insert(0, str(ROOT / 'Scripts'))
    try:
        from OldTownNonLightEmission import inspect_non_light_emission
    except ImportError:
        pass
    else:
        write('EmissionPlan.json', inspect_non_light_emission(actor_sys))
    assert sha(MAP) == current_sha
    unreal.log('OLDTOWN_STAIR_TRIM_INSPECTION_OK')


if __name__ == '__main__':
    main()
