"""Read persisted transforms and state differences for the incremental polish."""
import sys
from pathlib import Path
import unreal
ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
import PolishOldTownHotel as p
build = p.read(p.WORK / 'BuildReport.json')
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
by = {a.get_actor_label(): a for a in actors}
rotations = {}
for name in ('OTS_Hotel_RoomNumber_201', 'OTS_Hotel_ReceptionLetters'):
    r = by[name].get_actor_rotation()
    rotations[name] = [float(r.pitch), float(r.yaw), float(r.roll)]
p.write('RotationDiagnostic.json', rotations)
try:
    p.check_preservation(actors, build)
except AssertionError:
    pass
unreal.log('HOTEL_POLISH_STATE_DIAGNOSTIC_WRITTEN')
