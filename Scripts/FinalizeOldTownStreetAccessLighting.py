"""Publish only fresh street-access and directional-light evidence after review."""
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/StreetAccessLighting_20261005'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
PREVIOUS = ROOT / 'Saved/CodexOutputs/HotelPolish_20261005'
AUDITS = ['SavedVerification.json', 'FreshHotelVerification.json',
          'OpeningComponentsAudit.json', 'RevisionAudit.json',
          'LightingCleanupAudit.json', 'ArchitectureSealAudit.json',
          'DetailPolishAudit.json', 'DetailTriangleAudit.json', 'HotelLayoutAudit.json',
          'StreetAccessLightingAudit.json', 'PreservationAudit.json']
EXPECTED_MODES = {'CAM_StreetAccess_HomeDoor': 'temporary',
                  'CAM_StreetAccess_SouthGap': 'temporary',
                  'CAM_StreetAccess_NorthGap': 'temporary',
                  'CAM_StreetAccess_NightStreet': 'street_only',
                  'CAM_StreetAccess_Lamp': 'street_only'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    build = read(WORK / 'BuildReport.json')
    spec = build['street_access_lighting']
    current = build['map_sha256']
    target = build['target_level']
    mapfile = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    assert sha(mapfile) == current == spec['map_sha256']
    applied = read(WORK / 'AccessLightingApplied.json')
    assert applied['passed'] is True and applied['fresh_audits_pending'] is False
    assert applied['map_sha256'] == current and applied['actor_count'] == build['actor_count']
    checks = {}
    for name in AUDITS:
        result = read(WORK / name)
        assert result['passed'] is True and result['map_sha256'] == current, name
        checks[name] = {'passed': True, 'map_sha256': current,
                        'statistics': result.get('statistics')}
    assert all(sha(Path(p)) == h for p, h in build['protected_map_sha256'].items())
    tests = (WORK / 'UnitTests.log').read_text(encoding='utf-8-sig')
    assert 'Ran 141 tests' in tests and tests.rstrip().endswith('OK')
    assert read(WORK / 'BuildingReport.json') == build['buildings']
    assert read(WORK / 'HotelPlan.json') == build['hotel_plan']
    plan = read(WORK / 'RevisionPlan.json')
    assert plan['target_level'] == target
    assert plan['layout']['main_road_width_cm'] == 700.
    assert plan['layout']['main_sidewalk_width_cm'] == 180.
    assert len(spec['reopened_gaps']) == applied['reopened_gaps'] == 5
    assert len(spec['directional_lights']) == applied['directional_lights'] == 8
    assert len(spec['lamp_moves']) == len(build['lighting_cleanup']['lamp_positions']) == 9
    moved_lamps = sum(any(abs(float(v)) > .01 for v in row['delta_cm'])
                      for row in spec['lamp_moves'])
    assert moved_lamps == 6
    preservation = read(WORK / 'PreservationAudit.json')
    assert all('PointLight' not in preservation[key] for key in
               ('allowed_changed_actors', 'removed_actor_labels', 'added_actor_labels'))
    baseline = read(WORK / 'PreservationBaseline.json')
    user_light_expected = spec.get('user_light_expected', True)
    assert isinstance(user_light_expected, bool)
    assert ('PointLight' in baseline['expected_actors']) == user_light_expected
    external_deletions = []
    if user_light_expected:
        previous_baseline = read(PREVIOUS / 'PreservationBaseline.json')
        previous_user_light = previous_baseline['actors']['PointLight']
        # The preceding phase stored Color reprs with process-specific pointers.
        # Compare the original numeric channels with the current stable snapshot.
        for row in previous_user_light['components']:
            color = row.get('light_color')
            if isinstance(color, str):
                channels = dict(re.findall(r'([rgba]):\s*(\d+)', color))
                assert set(channels) == set('rgba'), 'Unrecognised previous user-light color'
                row['light_color'] = [int(channels[channel]) for channel in ('r', 'g', 'b', 'a')]
        assert baseline['expected_actors']['PointLight'] == previous_user_light
    else:
        rebase = read(WORK / 'InputRebaseReport.json')
        assert rebase['passed'] is True
        assert rebase['current_sha256'] == spec['source_map_sha256'] == baseline['source_map_sha256']
        assert rebase['preserved_external_deletions'] == ['PointLight']
        lighting = build['lighting_cleanup']
        assert 'PointLight' not in lighting['allowed_scene_light_labels']
        assert all('PointLight' not in lighting.get(key, {}) for key in
                   ('light_expected_positions', 'light_expected_intensities', 'light_expected_kinds'))
        assert not lighting.get('preserved_user_lights', [])
        external_deletions = list(rebase['preserved_external_deletions'])

    camera_rows = spec['review_cameras']
    cameras = [row['camera'] for row in camera_rows]
    modes = {row['camera']: row['lighting_mode'] for row in camera_rows}
    assert len(camera_rows) == len(set(cameras)) == 5 and modes == EXPECTED_MODES
    review = read(WORK / 'VisualReview.json')
    assert review['passed'] is True and review['map_sha256'] == current
    assert len(review['views']) == len(cameras)
    assert {row['camera'] for row in review['views']} == set(cameras)
    assert all(row['passed'] is True for row in review['views'])
    captures = []
    for camera in cameras:
        mode = modes[camera]
        meta = read(WORK / 'Renders' / (camera + '.json'))
        png = WORK / 'Renders' / (camera + '.png')
        assert meta['status'] == 'PASS' and meta['camera'] == camera
        assert meta['target_level'] == target and meta['map_sha256'] == current
        assert meta['source'] == 'fresh_persisted_map_load' and meta['fresh_map_load_verified'] is True
        assert meta['png_sha256'] == sha(png) and meta['bytes'] == png.stat().st_size
        assert meta['lighting_mode'] == mode and meta['view_mode_verified'] == 'lit'
        assert meta['temporary_lighting_cleanup_verified_zero'] is True
        assert meta['temporary_lighting_cleanup_remaining_count'] == 0
        assert meta['persisted_map_unchanged'] is True and meta['map_sha256_after_cleanup'] == current
        owned = read(WORK / 'Runs' / meta['run_id'] / 'OwnedProcess.json')
        assert owned['owned_editor_pid'] == meta['owned_editor_pid']
        assert owned['exit_code'] == 0 and owned['normal_exit'] is True
        assert owned['forced_cleanup'] is False
        captures.append({'camera': camera, 'png': str(png), 'png_sha256': meta['png_sha256'],
                         'lighting_mode': mode, 'owned_helper_exit_code': 0})
    assert sha(mapfile) == current
    final = {'passed': True, 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
             'target_level': target, 'map_sha256': current, 'actor_count': build['actor_count'],
             'reopened_gaps': 5, 'directional_lights': 8, 'street_lamp_positions': 9,
             'moved_lamps': moved_lamps, 'carriageway_width_cm': 700.,
             'unchanged_sidewalk_width_cm': 180., 'user_light_preserved': user_light_expected,
             'external_user_light_deletion_preserved': not user_light_expected,
             'preserved_external_deletions': external_deletions,
             'preserved_user_actors': ['PointLight'] if user_light_expected else [],
             'capture_count': len(captures),
             'captures': captures, 'audits': checks, 'python_tests': 141,
             'protected_maps_unchanged': True,
             'previous_evidence_bundle': str(PREVIOUS),
             'limitations': [
                 'Route verification uses real editor collision samples, not a runtime player walkthrough.',
                 'Images from prior phases belong to their prior map hashes and are historical.',
                 'Three inspection views use temporary light removed without saving; two night views use persisted street lighting.']}
    (WORK / 'FinalReview.json').write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    backup = WORK / 'BeforeCanonicalPublish'
    backup.mkdir(parents=True, exist_ok=True)
    for path in CANON.glob('*.json'):
        if not (backup / path.name).exists():
            shutil.copy2(path, backup / path.name)
    publish = ['BuildReport.json', 'BuildingReport.json', 'RevisionPlan.json', 'HotelPlan.json',
               'AccessLightingApplied.json', 'VisualReview.json', 'FinalReview.json'] + AUDITS
    for name in publish:
        shutil.copy2(WORK / name, CANON / name)
    historical = sorted(p.name for p in CANON.glob('*.json')
                        if p.name not in set(publish) | {'CurrentEvidence.json'})
    (CANON / 'CurrentEvidence.json').write_text(json.dumps({
        'target_level': target, 'map_sha256': current, 'source_bundle': str(WORK),
        'source_directory': str(WORK), 'current_reports': publish,
        'historical_report_backup': str(backup), 'historical_reports_not_current': historical,
        'current_renders': str(WORK / 'Renders'), 'current_render_cameras': cameras,
        'current_render_lighting_modes': modes,
        'external_user_light_deletion_preserved': not user_light_expected,
        'preserved_external_deletions': external_deletions,
        'previous_evidence_bundle': str(PREVIOUS), 'previous_evidence_status': 'historical'},
        ensure_ascii=False, indent=2), encoding='utf-8')
    assert sha(mapfile) == current
    assert all(sha(Path(p)) == h for p, h in build['protected_map_sha256'].items())
    print(json.dumps({'passed': True, 'map_sha256': current, 'captures': len(captures),
                      'reopened_gaps': 5, 'directional_lights': 8, 'moved_lamps': moved_lamps,
                      'python_tests': 141, 'published_reports': len(publish)}))


if __name__ == '__main__':
    main()
