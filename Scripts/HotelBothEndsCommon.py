"""Complete the second hotel-front end using frozen north-screen resources."""
import sys,json,shutil
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import InspectOldTownRealismInput as native
import ApplyOldTownCallableLighting as base
PREV=R/'Saved/CodexOutputs/HotelFrontBoundary_20261021'
W=R/'Saved/CodexOutputs/HotelFrontBoundaryBothEnds_20261021'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet';MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TAG='HotelBothEnds_20261021'
base.W=W;base.TAG='HotelBothEnds_ExcludeNoOriginalActor'
def read(n):return json.loads((W/n).read_text(encoding='utf-8-sig'))
def prev(n):return json.loads((PREV/n).read_text(encoding='utf-8-sig'))
def write(n,d):native.write(W/n,d)
def files():return {str(p):native.sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
def protect(b,allow_map=False):
    now=files();diff=[p for p,h in b.items() if now.get(p)!=h and not(allow_map and Path(p)==MAP)]
    assert not diff and set(now)==set(b),dict(changed=diff,new=list(set(now)-set(b)))
    return dict(passed=True,other_existing_packages_unchanged=len(b)-(1 if allow_map else 0),new_resource_packages=0)
def load():
    le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);ae=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    assert le.load_level(TARGET);world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();actors=list(ae.get_all_level_actors())
    by={a.get_actor_label():a for a in actors};assert len(by)==len(actors)
    return le,ae,world,actors,by
def snap(actors,phase,world):
    base.W=W;base.TAG='HotelBothEnds_ExcludeNoOriginalActor'
    unreal.SystemLibrary.execute_console_command(world,'OBJ COMPONENTS Default__Object')
    return base.snapshot(actors,phase)
