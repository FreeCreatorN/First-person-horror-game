"""Additive hotel-front screen, only new private assets and original map."""
import sys,json,hashlib,shutil,re
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
W=R/'Saved/CodexOutputs/HotelFrontBoundary_20261021'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
ASSET='/Game/CodexGenerated/Hotel/FrontBoundary_20261021'
NEW=R/('Content/'+ASSET[6:]);TAG='HotelFrontBoundary_20261021'
base.W=W;base.TAG='FrontBoundary_NoExistingActorExclusion'
def write(n,d):native.write(W/n,d)
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def load():
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET)
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();actors=list(ae.get_all_level_actors())
    by={a.get_actor_label():a for a in actors};assert len(by)==len(actors)
    return le,ae,world,actors,by
def snap(actors,phase,world):
    base.W=W;base.TAG='FrontBoundary_NoExistingActorExclusion'
    unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    return base.snapshot(actors,phase)
def protect(baseline,allow_map=False):
    now=files();changed=[p for p,h in baseline.items() if now.get(p)!=h and not(allow_map and Path(p)==MAP)]
    unexpected=[p for p in set(now)-set(baseline) if not Path(p).is_relative_to(NEW)]
    assert not changed and not unexpected,dict(changed=changed,unexpected=unexpected)
    return dict(passed=True,old_files_checked=len(baseline)-(1 if allow_map else 0),other_files_changed=[],new_assets_only_in=str(NEW))
