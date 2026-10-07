"""Publish the fresh incremental polish evidence after affected-view review."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/HotelPolish_20261005'
CANON = ROOT / 'Saved/CodexOutputs/EnterableStreet_20261002'
AUDITS = ['SavedVerification.json', 'FreshHotelVerification.json', 'OpeningComponentsAudit.json',
          'RevisionAudit.json', 'LightingCleanupAudit.json', 'ArchitectureSealAudit.json',
          'DetailPolishAudit.json', 'DetailTriangleAudit.json', 'HotelLayoutAudit.json',
          'HotelPolishAudit.json', 'PreservationAudit.json']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    build = read(WORK / 'BuildReport.json')
    current = build['map_sha256']
    target = build['target_level']
    mapfile = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    assert sha(mapfile) == current
    applied = read(WORK / 'PolishApplied.json')
    assert applied['passed'] and not applied['fresh_audits_pending'] and applied['map_sha256'] == current
    for name in AUDITS:
        result = read(WORK / name)
        assert result['passed'] and result['map_sha256'] == current, name
    assert all(sha(Path(p)) == h for p, h in build['protected_map_sha256'].items())
    tests = (WORK / 'UnitTests.log').read_text(encoding='utf-8-sig')
    assert 'Ran 141 tests' in tests and tests.rstrip().endswith('OK')
    review = read(WORK / 'VisualReview.json')
    cameras = build['hotel_polish']['review_cameras']
    assert review['passed'] and review['map_sha256'] == current
    assert len(review['views']) == len(cameras) and {v['camera'] for v in review['views']} == set(cameras)
    assert all(v['passed'] is True for v in review['views'])
    captures = []
    for camera in cameras:
        meta = read(WORK / 'Renders' / (camera + '.json'))
        png = WORK / 'Renders' / (camera + '.png')
        assert meta['status'] == 'PASS' and meta['map_sha256'] == current and meta['target_level'] == target
        assert meta['camera'] == camera and meta['source'] == 'fresh_persisted_map_load' and meta['fresh_map_load_verified']
        assert meta['bytes'] == png.stat().st_size and meta['png_sha256'] == sha(png)
        assert meta['lighting_mode'] == 'temporary' and meta['view_mode_verified'] == 'lit'
        assert meta['temporary_lighting_cleanup_verified_zero'] and meta['temporary_lighting_cleanup_remaining_count'] == 0
        assert meta['persisted_map_unchanged'] and meta['map_sha256_after_cleanup'] == current
        process = read(WORK / 'Runs' / meta['run_id'] / 'OwnedProcess.json')
        assert process['owned_editor_pid'] == meta['owned_editor_pid']
        assert process['exit_code'] == 0 and process['normal_exit'] and not process['forced_cleanup']
        captures.append({'camera': camera, 'png': str(png), 'png_sha256': meta['png_sha256'], 'lighting_mode': 'temporary'})
    final = {'passed': True, 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
             'target_level': target, 'map_sha256': current, 'actor_count': build['actor_count'],
             'hotel_rooms': build['hotel_openings']['hotel_rooms'], 'windows': build['hotel_openings']['windows'],
             'doors': build['hotel_openings']['doors'], 'mattresses_refined': 24, 'room_number_plaques': 24,
             'reception_branding': True, 'capture_count': len(captures), 'captures': captures,
             'audits': AUDITS, 'python_tests': 141, 'protected_maps_unchanged': True,
             'preserved_user_actors': ['PointLight'],
             'previous_full_view_review': str(ROOT / 'Saved/CodexOutputs/HotelIntegration_20261004/FinalReview.json'),
             'interaction_status': 'independent hinged components ready; player input not implemented',
             'limitations': ['Incremental greybox polish; visual review covers four affected viewpoints.',
                             'Previous 17-view images belong to the prior map hash and are historical.',
                             'Route verification uses editor collision samples, not a runtime player walkthrough.',
                             'Inspection images use temporary light removed without saving.']}
    (WORK / 'FinalReview.json').write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    backup = WORK / 'BeforeCanonicalPublish'
    backup.mkdir(parents=True, exist_ok=True)
    for path in CANON.glob('*.json'):
        if not (backup / path.name).exists():
            shutil.copy2(path, backup / path.name)
    publish = ['BuildReport.json', 'BuildingReport.json', 'RevisionPlan.json', 'HotelPlan.json',
               'PolishApplied.json', 'VisualReview.json', 'FinalReview.json'] + AUDITS
    for name in publish:
        shutil.copy2(WORK / name, CANON / name)
    (CANON / 'CurrentEvidence.json').write_text(json.dumps({
        'target_level': target, 'map_sha256': current, 'source_bundle': str(WORK),
        'current_reports': publish, 'historical_report_backup': str(backup),
        'current_renders': str(WORK / 'Renders'), 'current_render_cameras': cameras,
        'previous_evidence_bundle': str(ROOT / 'Saved/CodexOutputs/HotelIntegration_20261004')}, ensure_ascii=False, indent=2), encoding='utf-8')
    assert sha(mapfile) == current
    print(json.dumps({'passed': True, 'map_sha256': current, 'captures': len(captures),
                      'python_tests': 141, 'published_reports': len(publish)}))


if __name__ == '__main__':
    main()
