import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from OldTownWindowSurfaceRepair import apply_window
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
try:
    build=json.loads((ROOT/'Saved/CodexOutputs/HotelRedesign_20261008_V4/BuildReport.json').read_text(encoding='utf-8'))
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
    by={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
    row=build['hotel_v4']['placed_windows'][0]
    new,report=apply_window(by[row['actor']],row)
    (WORK/'WindowProbe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    unreal.log('SURFACE_WINDOW_PROBE_PASS')
except Exception:
    (WORK/'WindowProbeFailure.json').write_text(traceback.format_exc(),encoding='utf-8');raise
