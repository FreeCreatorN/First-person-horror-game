"""Compare current street edits to the last verified polish state; never save."""
import sys
from pathlib import Path
import unreal
ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
import ImproveOldTownStreetAccessLighting as p
build = p.read(p.BASE / 'BuildReport.json')
reference = p.BASE / 'BeforeRotationRepair/L_OldTownSchoolStreet.umap'
assert p.sha(reference) == 'b26f093378c3fb1d4adf32f2ece1fdb814f8b9c34e43243bf264d23fb0220474'
assert unreal.EditorLoadingAndSavingUtils.load_map(str(reference))
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
expected = {a.get_actor_label(): p.actor_state(a) for a in sub.get_all_level_actors()}
names = [r['number_actor'] for r in build['hotel_polish']['room_labels']] + [build['hotel_polish']['reception_sign']['actor']]
for name in names:
    expected[name]['rotation'] = [0., 90., 0.]
    for row in expected[name]['components']:
        if row['parent'] is None:
            row['rotation'] = [0., 90., 0.]
mapfile = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
current_hash = p.sha(mapfile)
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(build['target_level'])
actual = {a.get_actor_label(): p.actor_state(a) for a in sub.get_all_level_actors()}
added = sorted(set(actual) - set(expected))
removed = sorted(set(expected) - set(actual))
changed = {name: {'before': expected[name], 'after': actual[name]}
           for name in set(actual) & set(expected) if actual[name] != expected[name]}
assert p.sha(mapfile) == current_hash
p.write('ExternalEditComparison.json', {'current_sha256': current_hash, 'reference_sha256': build['map_sha256'],
                                       'actor_count': len(actual), 'added': added, 'removed': removed,
                                       'changed': changed, 'added_states': {name: actual[name] for name in added},
                                       'reference_rotation_normalised_from_verified_repair': names,
                                       'persisted_map_unchanged': True})
unreal.log('CURRENT_STREET_EDIT_COMPARISON_WRITTEN added={} removed={} changed={}'.format(len(added), len(removed), len(changed)))
