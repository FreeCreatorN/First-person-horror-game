from rack_manifest import DESTINATION, HERE, protected_snapshot, read_export, write


if __name__ == '__main__':
    assert not any(path.is_file() for path in DESTINATION.rglob('*')), 'Import target is occupied'
    manifest, expected, _ = read_export()
    baseline = protected_snapshot()
    assert baseline, 'Missing project baseline'
    write(HERE / 'protected_content_sha256.json', baseline)
    print(f'RACK_PREFLIGHT_OK {len(manifest["assets"])} meshes, {len(expected)} packages, {len(baseline)} protected files')
