"""Merge the verified hotel and the user's new light into the original street."""
import hashlib
import json
import re
import shutil
import sys
import traceback
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
WORK = ROOT / 'Saved/CodexOutputs/HotelIntegration_20261004'
PREVIEW = ROOT / 'Saved/CodexOutputs/HotelOpenings_20261004'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
MAP_FILE = ROOT / ('Content/' + TARGET.removeprefix('/Game/') + '.umap')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, value):
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    comparison = read(WORK / 'MergeComparison.json')
    user = comparison['changes']['current']
    assert user == {'added': ['PointLight_0'], 'removed': [], 'changed': []}, user
    assert not comparison['overlapping_actor_names']
    assert comparison['outside_actor_text_equal_current']
    assert sha(MAP_FILE) == comparison['current_sha256'], 'Original street changed; re-inspect before merging'
    build = read(PREVIEW / 'BuildReport.json')
    plan = read(PREVIEW / 'RevisionPlan.json')
    preview_target = build['target_level']
    preview_map = ROOT / ('Content/' + preview_target.removeprefix('/Game/') + '.umap')
    preview_sha = sha(preview_map)
    fresh = read(PREVIEW / 'FreshHotelVerification.json')
    assert fresh['passed'] and fresh['map_sha256'] == preview_sha == build['map_sha256']
    protected = {path: sha(Path(path)) for path in build['protected_map_sha256'] if Path(path) != MAP_FILE}
    protected[str(preview_map)] = preview_sha
    backup = WORK / 'BeforeIntegration'
    backup.mkdir(parents=True, exist_ok=True)
    if not (backup / MAP_FILE.name).exists():
        shutil.copy2(MAP_FILE, backup / MAP_FILE.name)
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(preview_target)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    before = list(sub.get_all_level_actors())
    assert not any(actor.get_actor_label() == 'PointLight' for actor in before)
    text = (WORK / 'Current.t3d').read_text(encoding='utf-8-sig')
    block = next(block for block in re.findall(r'(?ms)^ *Begin Actor .*?^ *End Actor$', text)
                 if ' Name=PointLight_0 ' in block)
    current_world = read(WORK / 'Current.json')['world']
    block = block.replace(current_world, world.get_path_name())
    import_file = WORK / 'PreservedUserLight.t3d'
    import_file.write_text('Begin Map\n   Begin Level\n' + block + '\n   End Level\nEnd Map\n', encoding='utf-8')
    # UE 5.7 Map_Import determines the extension from the remaining command
    # string, including a trailing quote. Our fixed workspace path has no
    # spaces, so pass it without quotes to avoid rejecting the t3d format.
    assert ' ' not in import_file.as_posix()
    unreal.SystemLibrary.execute_console_command(world, 'MAP IMPORTADD FILE=' + import_file.as_posix())
    actors = list(sub.get_all_level_actors())
    assert len(actors) == len(before) + 1, (len(before), len(actors))
    added = [actor for actor in actors if actor.get_actor_label() == 'PointLight']
    assert len(added) == 1 and isinstance(added[0], unreal.PointLight)
    light = added[0].get_component_by_class(unreal.PointLightComponent)
    position = light.get_world_location()
    assert all(abs(value - expected) < .001 for value, expected in zip(
        (position.x, position.y, position.z), (6090., 1690., 1460.)))
    assert abs(light.get_editor_property('intensity') - 160.) < .001
    assert light.get_editor_property('intensity_units') == unreal.LightUnits.CANDELAS
    build['lighting_cleanup']['allowed_scene_light_labels'].append('PointLight')
    build['lighting_cleanup']['light_expected_positions']['PointLight'] = [6090., 1690., 1460.]
    build['lighting_cleanup'].setdefault('light_expected_intensities', {})['PointLight'] = 160.
    build['lighting_cleanup']['preserved_user_lights'] = [{
        'actor': 'PointLight', 'source_actor_name': 'PointLight_0', 'intensity': 160.,
        'intensity_units': 'Candelas', 'source_map_sha256': comparison['current_sha256']}]
    build['target_level'] = TARGET
    build['buildings']['target_level'] = TARGET
    plan['target_level'] = TARGET
    plan['translated_inventory']['level'] = TARGET
    build['protected_map_sha256'] = protected
    build['hotel_openings'].update(preview=False, preview_level=preview_target,
                                   preview_sha256=preview_sha,
                                   source_before_merge_sha256=comparison['current_sha256'])
    assert sha(MAP_FILE) == comparison['current_sha256'], 'User street changed before save'
    assert all(sha(Path(path)) == expected for path, expected in protected.items())
    assert unreal.EditorLoadingAndSavingUtils.save_map(world, TARGET), 'Integrated street save failed'
    merged_sha = sha(MAP_FILE)
    assert all(sha(Path(path)) == expected for path, expected in protected.items())
    build['map_sha256'] = merged_sha
    for section in ('architecture_seal', 'detail_polish', 'hotel_openings'):
        build[section]['map_sha256'] = merged_sha
    build['actor_count'] = len(actors)
    write('BuildReport.json', build)
    write('RevisionPlan.json', plan)
    write('BuildingReport.json', build['buildings'])
    write('HotelPlan.json', build['hotel_plan'])
    write('MergeApplied.json', {'passed': True, 'target_level': TARGET, 'map_sha256': merged_sha,
                              'preview_sha256': preview_sha, 'source_before_sha256': comparison['current_sha256'],
                              'actor_count': len(actors), 'preserved_user_actors': ['PointLight'],
                              'backup': str(backup / MAP_FILE.name), 'fresh_audits_pending': True})
    import VerifyOldTownHotelReview as verification
    verification.WORK = WORK
    verification.main()
    applied = read(WORK / 'MergeApplied.json')
    applied['fresh_audits_pending'] = False
    write('MergeApplied.json', applied)
    unreal.log('OTS_HOTEL_INTEGRATION_PASS actors={} preserved_user_light=True'.format(len(actors)))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('IntegrationFailure.json', {'passed': False, 'traceback': traceback.format_exc()})
        raise
