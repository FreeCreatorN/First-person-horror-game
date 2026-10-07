"""Read saved lighting, fixtures and street-end geometry without editing."""
import hashlib
import json
from pathlib import Path
import unreal

PROJECT=Path(unreal.Paths.project_dir()).resolve()
OUT=PROJECT/'Saved/CodexOutputs/LightRoadCleanup_20261003'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'

def vec(v):
    return [round(float(v.x),4),round(float(v.y),4),round(float(v.z),4)]

def prop(component,name):
    try:
        value=component.get_editor_property(name)
        return value if isinstance(value,(str,int,float,bool)) else str(value)
    except Exception:
        return None

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.load_level(TARGET)
subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
lights=[]
fixtures=[]
east=[]
for actor in subsystem.get_all_level_actors():
    label=actor.get_actor_label()
    row={'label':label,'class':actor.get_class().get_name(),
         'location_cm':vec(actor.get_actor_location()),'folder':str(actor.get_folder_path()),
         'tags':[str(t) for t in actor.tags]}
    components=actor.get_components_by_class(unreal.LightComponentBase)
    if components:
        entry=dict(row)
        entry['lights']=[{'name':c.get_name(),'class':c.get_class().get_name(),
                          'location_cm':vec(c.get_world_location()),
                          **{name:prop(c,name) for name in ('intensity','attenuation_radius','cast_shadows','affects_world','visible')}}
                         for c in components]
        lights.append(entry)
    meshes=[]
    for c in actor.get_components_by_class(unreal.StaticMeshComponent):
        if not c.static_mesh:
            continue
        origin,extent,_=unreal.SystemLibrary.get_component_bounds(c)
        meshes.append({'name':c.get_name(),'mesh':c.static_mesh.get_path_name(),
                       'world_origin_cm':vec(origin),'world_extent_cm':vec(extent),
                       'materials':[m.get_path_name() if m else None for m in
                                    [c.get_material(i) for i in range(c.get_num_materials())]]})
    if any(token in label.lower() for token in ('lamp','light','awning','streetend','endfacade')):
        fixtures.append({**row,'meshes':meshes})
    if meshes and (any(m['world_origin_cm'][0]+m['world_extent_cm'][0]>6900 for m in meshes)):
        east.append({**row,'meshes':meshes})
path=PROJECT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
report={'map_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'lights':lights,'fixtures':fixtures,'east_geometry':east}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'LightingRouteInventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('OTS_LIGHT_ROUTE_INVENTORY lights={} fixtures={} east={}'.format(len(lights),len(fixtures),len(east)))
