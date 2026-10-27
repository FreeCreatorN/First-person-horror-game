"""Fresh all-Game registry export; never load/save/compile a Content asset."""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import unreal

R = Path(unreal.Paths.project_dir()).resolve()
W = R / 'Saved/CodexOutputs/OldTownDoorReuse_20261017'
MAP = R / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def files():
    return {str(p): sha(p) for root in (R / 'Content', R / 'Config')
            for p in root.rglob('*') if p.is_file()}


def main():
    assert not (W / 'FinalReview.json').exists(), 'Accepted evidence may not be overwritten'
    name = os.environ.get('OTS_REFERENCES_NAME', 'AssetReferencesFresh.json')
    assert re.fullmatch(r'AssetReferences[A-Za-z0-9_]*\.json', name), name
    output = W / name
    assert not output.exists(), 'Choose a fresh export name; previous evidence is immutable'
    before = files()
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    registry.scan_paths_synchronous(['/Game'], True)
    options = unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=True, include_hard_package_references=True,
        include_searchable_names=True, include_soft_management_references=True,
        include_hard_management_references=True)
    rows = []
    for asset in registry.get_assets_by_path('/Game', True, False):
        package = str(asset.package_name)
        rows.append(dict(package=package, asset_name=str(asset.asset_name),
            class_path=str(asset.asset_class_path),
            dependencies=sorted(str(p) for p in (registry.get_dependencies(package, options) or [])),
            referencers=sorted(str(p) for p in (registry.get_referencers(package, options) or []))))
    after = files()
    assert before == after, 'Content/Config changed during the read-only export'
    report = dict(passed=True, target_level='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',
        map_sha256=before[str(MAP)], map_last_write_utc=datetime.fromtimestamp(
            MAP.stat().st_mtime, timezone.utc).isoformat(), created_utc=datetime.now(timezone.utc).isoformat(),
        project_asset_count=len(rows), distinct_package_count=len({r['package'].casefold() for r in rows}),
        includes_hard_soft_and_management=True, includes_searchable_names=True,
        forced_disk_rescan=True, no_save_or_explicit_compile_called=True,
        changed_content_or_config_files={}, file_sha256=before, assets=rows)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('OLD_TOWN_FRESH_REFERENCES_PASS ' + name + ' ' + report['map_sha256'])


if __name__ == '__main__':
    main()
