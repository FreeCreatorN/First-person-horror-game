"""Read-only full-precision export provenance and stable-file preflight."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    expected = sys.argv[1]
    assert re.fullmatch('[0-9a-f]{64}', expected)
    geometry = WORK / 'GeometryAfter.json'
    summary_path = WORK / 'AfterSummary.json'
    build_path = WORK / 'BuildReport.json'
    target = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    build = json.loads(build_path.read_text(encoding='utf-8'))
    assert summary['passed'] and summary['map_sha256'] == expected
    assert summary['new_asset_sha256'] == build['new_asset_sha256']
    assert len(build['new_asset_sha256']) == 927
    closure = build['model_closure_import_repairs']
    assert closure['passed'] and closure['map_sha256'] == expected
    assert closure['changed_target_count'] == closure['added_import_cache_count'] == 22
    assert closure['after_asset_sha256'] == build['new_asset_sha256']
    before = (geometry.stat().st_size, geometry.stat().st_mtime_ns)
    time.sleep(1)
    assert before == (geometry.stat().st_size, geometry.stat().st_mtime_ns)
    geometry_hash = sha(geometry)
    assert before == (geometry.stat().st_size, geometry.stat().st_mtime_ns)
    # Geometry's last appended field is the native saved audit asset dictionary.
    # Read only this footer, avoiding another full 8.4-million-triangle parse.
    with geometry.open('rb') as stream:
        head = stream.read(300).decode('utf-8')
        stream.seek(-min(geometry.stat().st_size, 400000), 2)
        tail = stream.read().decode('utf-8')
    assert json.loads(re.search(r'"map_sha256"\s*:\s*("[0-9a-f]{64}")', head).group(1)) == expected
    start = tail.rfind('"new_asset_sha256"')
    assert start >= 0
    assets = json.JSONDecoder().raw_decode(tail[tail.index(':', start)+1:].lstrip())[0]
    assert assets == build['new_asset_sha256']
    serialization = 'unrounded native local positions and unrounded native transformed world positions, plus verified material WPO'
    assert serialization in tail
    map_hash = sha(target)
    assert map_hash == expected
    result = dict(schema='OldTownRealismFullPrecisionScanPreflightV1', passed=True,
        created_utc=datetime.now(timezone.utc).isoformat(), map_file=str(target), map_sha256=map_hash,
        geometry_file=str(geometry), geometry_sha256=geometry_hash,
        geometry_bytes=before[0], geometry_mtime_ns=before[1],
        export_summary_file=str(summary_path), export_summary_sha256=sha(summary_path),
        build_file=str(build_path), build_sha256=sha(build_path), new_asset_count=len(assets),
        all_geometry_summary_and_build_asset_hashes_identical=True,
        coordinate_serialization=serialization, exported_triangles=summary['triangles'],
        visible_components=summary['visible_components'], actor_count=summary['actors'])
    (WORK / 'ScanPreflight.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
