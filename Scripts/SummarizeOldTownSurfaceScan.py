"""Summarize a saved-map coplanar scan with verified input provenance."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def summarize(geometry_path, scan_path, classified_path, map_path, after_summary_path=None):
    geometry_sha = hashlib.sha256(geometry_path.read_bytes()).hexdigest()
    scan = json.loads(scan_path.read_text(encoding='utf-8-sig'))
    classified = json.loads(classified_path.read_text(encoding='utf-8-sig'))
    map_sha = hashlib.sha256(map_path.read_bytes()).hexdigest()
    for report in (scan, classified):
        if report['source_geometry_sha256'] != geometry_sha:
            raise ValueError('Scan geometry SHA does not match current input')
        if report['source_map_sha256'] != map_sha:
            raise ValueError('Scan map SHA does not match current saved map')
    if scan['scope']['axis_only'] or not scan['scope']['include_internal']:
        raise ValueError('Final verification requires all normals and component internals')
    if scan['stats'].get('non_axis_faces_skipped', 0):
        raise ValueError('Final verification skipped non-axis faces')
    rows = classified['overlaps']
    exposed = [row for row in rows if not row['buried']]
    mesh_pairs = Counter(tuple(sorted(item.get('mesh', '') for item in row['component_metadata']))
                         for row in exposed)
    counts = {
        'groups': len(rows),
        'exposed_groups': len(exposed),
        'fully_buried_groups': len(rows) - len(exposed),
        'inter_exposed': sum(not row['intra_component'] for row in exposed),
        'intra_exposed': sum(row['intra_component'] for row in exposed),
        'exact_duplicate_box_groups': len(scan['exact_duplicate_boxes']),
    }
    result = {
        'schema': 'oldtown-saved-surface-verification-v1',
        'passed': not exposed and not scan['exact_duplicate_boxes'],
        'provenance': {
            'source_map_path': str(map_path.resolve()),
            'source_map_sha256': map_sha,
            'source_geometry_path': str(geometry_path.resolve()),
            'source_geometry_sha256': geometry_sha,
            'scan_path': str(scan_path.resolve()),
            'scan_sha256': hashlib.sha256(scan_path.read_bytes()).hexdigest(),
            'classified_scan_path': str(classified_path.resolve()),
            'classified_scan_sha256': hashlib.sha256(classified_path.read_bytes()).hexdigest(),
            'scan_completed_utc': scan['completed_utc'],
            'completed_utc': datetime.now(timezone.utc).isoformat(),
        },
        'scope': classified['scope'],
        'stats': classified['stats'],
        'normal_group_count': classified['normal_group_count'],
        'internal_occlusion_stats': classified.get('internal_occlusion_stats', {}),
        'counts': counts,
        'mesh_pairs': [{'meshes': list(pair), 'groups': count}
                       for pair, count in mesh_pairs.most_common()],
        'exposed_candidates': exposed,
        'limitations': [
            'LOD0 geometry of exported visible static mesh components, including exported material world offsets',
            'Same-facing planes within the configured distance and angular tolerance with overlapping area above the configured minimum',
            'Buried classification samples overlap centres and inset vertices at 0.1 cm along the face normal; it is geometric occupancy, not a rendered visibility proof',
            'Opposing touching faces and zero-area shared edges are intentionally excluded',
        ],
    }
    if after_summary_path:
        after = json.loads(after_summary_path.read_text(encoding='utf-8-sig'))
        if not after['passed'] or after['map_sha256'] != map_sha:
            raise ValueError('Fresh export summary does not match saved map')
        result['export_summary'] = after
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('geometry', type=Path)
    parser.add_argument('scan', type=Path)
    parser.add_argument('classified', type=Path)
    parser.add_argument('map', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--export-summary', type=Path)
    args = parser.parse_args()
    result = summarize(args.geometry, args.scan, args.classified, args.map, args.export_summary)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('passed', 'provenance', 'counts', 'stats')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
