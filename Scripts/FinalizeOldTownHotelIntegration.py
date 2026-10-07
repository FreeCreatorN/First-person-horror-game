"""Verify the final evidence bundle and publish current canonical reports."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/HotelIntegration_20261004'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
AUDITS = ['SavedVerification.json', 'FreshHotelVerification.json',
          'OpeningComponentsAudit.json', 'RevisionAudit.json',
          'LightingCleanupAudit.json', 'ArchitectureSealAudit.json',
          'DetailPolishAudit.json', 'DetailTriangleAudit.json', 'HotelLayoutAudit.json']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    build = read(WORK / 'BuildReport.json')
    target = build['target_level']
    map_file = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    current = sha(map_file)
    assert current == build['map_sha256']
    applied = read(WORK / 'MergeApplied.json')
    assert applied['passed'] and not applied['fresh_audits_pending'] and applied['map_sha256'] == current
    checks = {}
    for name in AUDITS:
        report = read(WORK / name)
        assert report['passed'] and report['map_sha256'] == current, name
        checks[name] = {'passed': True, 'map_sha256': current}
    preservation = read(WORK / 'UserLightPreservation.json')
    assert preservation['passed'] and preservation['integrated_sha256'] == current
    assert all(sha(Path(path)) == expected for path, expected in build['protected_map_sha256'].items())
    tests = (WORK / 'UnitTests.log').read_text(encoding='utf-8-sig')
    assert 'Ran 141 tests' in tests and tests.rstrip().endswith('OK')
    visual = read(WORK / 'VisualReview.json')
    expected_cameras = set(build['hotel_openings_review_cameras'])
    assert visual['passed'] and visual['map_sha256'] == current
    assert len(visual['views']) == len(expected_cameras)
    assert {row['camera'] for row in visual['views']} == expected_cameras
    assert all(row['passed'] is True for row in visual['views'])
    captures = []
    for camera in build['hotel_openings_review_cameras']:
        meta = read(WORK / 'Renders' / (camera + '.json'))
        png = WORK / 'Renders' / (camera + '.png')
        lighting = 'street_only' if camera == 'CAM_Hotel_NightFront' else 'temporary'
        assert meta['status'] == 'PASS' and meta['camera'] == camera
        assert meta['target_level'] == target and meta['map_sha256'] == current
        assert meta['source'] == 'fresh_persisted_map_load' and meta['fresh_map_load_verified']
        assert meta['png_sha256'] == sha(png) and meta['bytes'] == png.stat().st_size
        assert meta['lighting_mode'] == lighting and meta['view_mode_verified'] == 'lit'
        assert meta['temporary_lighting_cleanup_verified_zero'] and meta['temporary_lighting_cleanup_remaining_count'] == 0
        assert meta['persisted_map_unchanged'] and meta['map_sha256_after_cleanup'] == current
        owned = read(WORK / 'Runs' / meta['run_id'] / 'OwnedProcess.json')
        assert owned['owned_editor_pid'] == meta['owned_editor_pid']
        assert owned['exit_code'] == 0 and owned['normal_exit'] and not owned['forced_cleanup']
        captures.append({'camera': camera, 'png': str(png), 'png_sha256': meta['png_sha256'],
                         'lighting_mode': lighting, 'owned_helper_exit_code': 0})
    final = {'passed': True, 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
             'target_level': target, 'map_sha256': current, 'actor_count': build['actor_count'],
             'hotel_rooms': build['hotel_openings']['hotel_rooms'],
             'doors': build['hotel_openings']['doors'], 'windows': build['hotel_openings']['windows'],
             'capture_count': len(captures), 'captures': captures, 'audits': checks,
             'preserved_user_actors': ['PointLight'], 'python_tests': 141,
             'protected_maps_unchanged': True,
             'interaction_status': 'independent hinged components ready; player input not implemented',
             'limitations': ['Scene remains a low-poly greybox.',
                             'Route validation uses editor collision samples, not a runtime player walkthrough.',
                             'The user light receives native import lighting identifiers; physical properties are preserved.']}
    (WORK / 'FinalReview.json').write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    backup = WORK / 'BeforeCanonicalPublish'
    backup.mkdir(parents=True, exist_ok=True)
    for path in CANON.glob('*.json'):
        if not (backup / path.name).exists():
            shutil.copy2(path, backup / path.name)
    publish = ['BuildReport.json', 'BuildingReport.json', 'RevisionPlan.json', 'HotelPlan.json',
               'MergeApplied.json', 'UserLightPreservation.json', 'FinalReview.json', 'VisualReview.json'] + AUDITS
    for name in publish:
        shutil.copy2(WORK / name, CANON / name)
    # Reports created by earlier phases remain historical; list the complete
    # authoritative set so future work need not treat directory contents as current.
    (CANON / 'CurrentEvidence.json').write_text(json.dumps({
        'target_level': target, 'map_sha256': current, 'source_bundle': str(WORK),
        'current_reports': publish, 'historical_report_backup': str(backup),
        'current_renders': str(WORK / 'Renders')}, ensure_ascii=False, indent=2), encoding='utf-8')
    assert sha(map_file) == current
    print(json.dumps({'passed': True, 'map_sha256': current, 'captures': len(captures),
                      'python_tests': 141, 'canonical_reports_published': len(publish)}))


if __name__ == '__main__':
    main()
