"""Correct only newly added lettering rotations in the saved polish map."""
import shutil
import sys
from pathlib import Path
import unreal
ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
import PolishOldTownHotel as p
build = p.read(p.WORK / 'BuildReport.json')
target = build['target_level']
mapfile = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
assert p.sha(mapfile) == build['map_sha256'] == 'b26f093378c3fb1d4adf32f2ece1fdb814f8b9c34e43243bf264d23fb0220474'
backup = p.WORK / 'BeforeRotationRepair'
backup.mkdir(parents=True, exist_ok=True)
if not (backup / mapfile.name).exists():
    shutil.copy2(mapfile, backup / mapfile.name)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert level.load_level(target)
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
names = [row['number_actor'] for row in build['hotel_polish']['room_labels']] + [build['hotel_polish']['reception_sign']['actor']]
assert len(names) == 25
for name in names:
    a = by[name]
    assert p.TAG in [str(t) for t in a.tags]
    assert a.set_actor_rotation(unreal.Rotator(pitch=0., yaw=90., roll=0.), False)
    r = a.get_actor_rotation()
    assert abs(r.pitch) < .001 and abs(r.yaw - 90.) < .001 and abs(r.roll) < .001
p.check_preservation(list(sub.get_all_level_actors()), build)
assert all(p.sha(Path(path)) == expected for path, expected in build['protected_map_sha256'].items())
assert level.save_current_level()
current = p.sha(mapfile)
build['map_sha256'] = current
for key in ('architecture_seal', 'detail_polish', 'hotel_openings', 'hotel_polish'):
    build[key]['map_sha256'] = current
p.write('BuildReport.json', build)
applied = p.read(p.WORK / 'PolishApplied.json')
applied['map_sha256'] = current
applied['fresh_audits_pending'] = True
applied['letter_rotation_repair'] = {'objects': 25, 'pitch': 0., 'yaw': 90., 'roll': 0.}
p.write('PolishApplied.json', applied)
p.write('LetterRotationRepair.json', {'passed': True, 'map_sha256': current, 'repaired_actors': names})
unreal.log('OLDTOWN_HOTEL_LETTER_ROTATION_REPAIR_PASS ' + current)
