"""Read the current saved world before the approved V4 replacement. Never save UE."""
import json, sys, hashlib, traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import actor_state, shared_asset_hashes, sha
from PolishOldTownDetails import actor_bounds
from ValidateEnterableStreet import validate_main_home
WORK=ROOT/'Saved/CodexOutputs/HotelRedesign_20261008_V4'
TARGET='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'


def main():
    WORK.mkdir(parents=True,exist_ok=True)
    source=json.loads((ROOT/'Saved/CodexOutputs/StreetRefinement_20261007/BuildReport.json').read_text(encoding='utf-8-sig'))
    mapfile=ROOT/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    digest=sha(mapfile)
    assert digest==source['map_sha256'],'Changed saved map must be rebased explicitly.'
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(TARGET)
    actors=list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    states={a.get_actor_label():actor_state(a) for a in actors}
    assert len(states)==len(actors)
    bounds={}
    for a in actors:
        try:
            lo,hi=actor_bounds(a)
            if hi[0]>=8500 and lo[0]<=10700 and hi[1]>=-3800 and lo[1]<=4300:
                bounds[a.get_actor_label()]=[lo,hi]
        except Exception:
            pass
    data=dict(passed=True,target_level=TARGET,source_map_sha256=digest,actor_count=len(actors),actors=states,
        shared_asset_sha256=shared_asset_hashes(actors),main_home=validate_main_home(actors),
        protected_map_sha256={p:sha(Path(p)) for p in source['protected_map_sha256']},
        historical_protected_map_sha256=source['protected_map_sha256'],near_hotel_bounds=bounds,
        source_bundle=str(ROOT/'Saved/CodexOutputs/StreetRefinement_20261007'))
    (WORK/'InputSnapshot.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    changed={p:dict(previous=h,current=data['protected_map_sha256'][p]) for p,h in source['protected_map_sha256'].items() if h!=data['protected_map_sha256'][p]}
    (WORK/'InputRebaseReport.json').write_text(json.dumps(dict(passed=True,target_map_unchanged=True,
        protected_map_user_state_rebased=changed,note='Record current unrelated saved maps as protected inputs; never restore historical copies.'),ensure_ascii=False,indent=2),encoding='utf-8')
    assert sha(mapfile)==digest
    unreal.log('HOTEL_V4_INPUT_PASS actors=%d bounds=%d'%(len(actors),len(bounds)))


if __name__=='__main__':
    try:main()
    except Exception:
        WORK.mkdir(parents=True,exist_ok=True)
        (WORK/'InputFailure.json').write_text(traceback.format_exc(),encoding='utf-8')
        raise
