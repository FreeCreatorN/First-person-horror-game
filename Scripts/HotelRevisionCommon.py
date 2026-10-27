"""Revision scope: original own hotel Actors, new private assets, no shared writes."""
import sys,json,shutil,hashlib,re
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
W=R/'Saved/CodexOutputs/HotelRevision_20261019'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
ASSET='/Game/CodexGenerated/Hotel/Revision_20261019'
NEW=R/('Content/'+ASSET[6:])
base.W=W;base.TAG='HotelRevision_NoExistingActorExclusion'

def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def write(n,v):native.write(W/n,v)
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def components(a):return {c.get_name():c for c in a.get_components_by_class(unreal.SceneComponent)}
def load():
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors=list(ae.get_all_level_actors());by={a.get_actor_label():a for a in actors}
    assert len(actors)==len(by)
    return le,ae,world,actors,by
def snapshot(actors,phase,world):
    unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    return base.snapshot(actors,phase)
def text(path):
    b=Path(path).read_bytes();return b.decode('utf-16' if b[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
def own(a):
    assert a.get_actor_label().startswith('OTS_HotelV4_'),a.get_actor_label()
    assert 'HotelRedesign_20261008_V4' in [str(t) for t in a.tags],a.get_actor_label()
def protect(before,allow_map=False):
    now=files();changed=[p for p,h in before.items() if now.get(p)!=h and not(allow_map and Path(p)==MAP)]
    # Main is being edited in the other process. These observations do not
    # authorize this helper to save anything outside MAP/new private directory.
    unexpected=[p for p in set(now)-set(before) if not Path(p).is_relative_to(NEW)]
    return dict(existing_file_count=len(before),outside_changes_observed=changed,outside_new_files_observed=unexpected,
        all_old_files_unchanged=not changed,unexpected_files_absent=not unexpected)
def filtered(s,labels):
    d=dict(s);d['actor_count']=s['actor_count']-len(labels)
    for k in ('actors','actor_properties','full_existing_actor_native'):d[k]={n:v for n,v in s[k].items() if n not in labels}
    for k in ('exact_scene_components','lights','full_light_properties'):d[k]={n:v for n,v in s[k].items() if n.split('::')[0] not in labels}
    return d
