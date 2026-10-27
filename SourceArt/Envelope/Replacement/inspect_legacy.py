"""Inspect and back up exactly five legacy envelope packages; never delete.

Run in the full editor using ExecutePythonScript. AssetRegistry queries cover
on-disk references; this script does not load/save maps or edit any package.
It writes only the five exact backup copies and its own inspection report.
"""
import hashlib
import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

import unreal

PROJECT = Path(r'D:\UE\Project\HorrorGame')
CONTENT = (PROJECT / 'Content').resolve()
OUT = PROJECT / 'SourceArt' / 'Envelope' / 'Replacement'
BACKUP = (PROJECT / 'Saved' / 'CodexBackups' / 'EnvelopeBeforeReplacement_20261020').resolve()
ROOT = '/Game/Yastars/Mesh/Envelope'
LEGACY = (
    ROOT + '/SM_Envelope',
    ROOT + '/Materials/M_Envelope',
    ROOT + '/Textures/T_Envelope_BaseColor',
    ROOT + '/Textures/T_Envelope_Roughness',
    ROOT + '/Textures/T_Envelope_Normal',
)
LEGACY_SET = set(LEGACY)
report = {
    'success': False,
    'started_utc': datetime.now(timezone.utc).isoformat(),
    'mode': 'inspect_and_backup_only',
    'deletion_executed': False,
    'rename_executed': False,
    'asset_or_map_save_executed': False,
    'level_load_executed': False,
    'legacy_packages': list(LEGACY),
    'backup_root': str(BACKUP),
    'assets': {},
    'external_referencers': {},
    'deletion_gate_passed': False,
    'reference_scope': 'Fresh on-disk AssetRegistry hard/soft/game/editor/searchable/management references plus EditorAssetLibrary hard/soft cross-check. Does not inspect unsaved state in another editor or arbitrary string literals.',
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def package_file(package):
    assert package in LEGACY_SET and package.startswith('/Game/'), package
    path = (CONTENT / (package[6:] + '.uasset')).resolve()
    assert path.is_relative_to(CONTENT), str(path)
    assert path.is_file(), 'Missing legacy package: ' + str(path)
    sidecars = [str(path.with_suffix(suffix)) for suffix in ('.uexp', '.ubulk', '.uptnl')
                if path.with_suffix(suffix).exists()]
    assert not sidecars, ('Additional package sidecars need an explicit complete backup plan', sidecars)
    return path


def normalized_refs(values):
    return sorted(set(str(value).split('.')[0] for value in (values or [])))


try:
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert editor, 'Requires full Unreal Editor, not a Python commandlet'
    world_before = editor.get_editor_world()
    report['world_before'] = world_before.get_path_name() if world_before else None
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    files = {package: package_file(package) for package in LEGACY}
    print('ENVELOPE_INSPECT refreshing on-disk asset references', flush=True)
    registry.search_all_assets(True)
    registry.wait_for_completion()
    registry.scan_files_synchronous([str(path) for path in files.values()], True)
    assert not registry.is_loading_assets(), 'Asset discovery did not finish'

    options = unreal.AssetRegistryDependencyOptions()
    report['reference_options_applied'] = []
    report['optional_reference_options_unsupported'] = {}
    for flag in (
        'include_hard_package_references', 'include_soft_package_references',
        'include_searchable_names', 'include_hard_management_references',
        'include_soft_management_references',
    ):
        options.set_editor_property(flag, True)
        report['reference_options_applied'].append(flag)
    # These two extra filters vary between engine builds. The five core
    # hard/soft/searchable/management categories above remain mandatory.
    for flag in ('include_game_package_references', 'include_editor_only_package_references'):
        try:
            options.set_editor_property(flag, True)
            report['reference_options_applied'].append(flag)
        except Exception as error:
            report['optional_reference_options_unsupported'][flag] = str(error)
    for package in LEGACY:
        data = list(registry.get_assets_by_package_name(package, True) or [])
        assert len(data) == 1, (package, len(data))
        assert not data[0].is_redirector(), 'Legacy package is a redirector: ' + package
        registry_refs = normalized_refs(registry.get_referencers(package, options))
        library_refs = normalized_refs(unreal.EditorAssetLibrary.find_package_referencers_for_asset(package, False))
        referencers = sorted(set(registry_refs) | set(library_refs))
        external = [ref for ref in referencers if ref not in LEGACY_SET and ref != package]
        source = files[package]
        source_hash = sha256(source)
        info = {
            'asset_class': str(data[0].asset_class_path),
            'source_file': str(source),
            'source_bytes': source.stat().st_size,
            'source_sha256': source_hash,
            'registry_referencers': registry_refs,
            'editor_asset_library_referencers': library_refs,
            'internal_legacy_referencers': [ref for ref in referencers if ref in LEGACY_SET],
            'external_referencers': external,
        }
        report['assets'][package] = info
        if external:
            report['external_referencers'][package] = external

    print('ENVELOPE_INSPECT backing up the exact five legacy uasset files', flush=True)
    for package in LEGACY:
        source = files[package]
        destination = (BACKUP / 'Content' / source.relative_to(CONTENT)).resolve()
        assert destination.is_relative_to(BACKUP), str(destination)
        info = report['assets'][package]
        if destination.exists():
            assert sha256(destination) == info['source_sha256'], 'Existing backup differs; never overwrite it: ' + str(destination)
            info['backup_status'] = 'existing_identical_copy_preserved'
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            info['backup_status'] = 'created'
        assert sha256(source) == info['source_sha256'], 'Legacy package changed during inspection: ' + package
        info['backup_file'] = str(destination)
        info['backup_sha256'] = sha256(destination)
        assert info['backup_sha256'] == info['source_sha256'], str(destination)

    world_after = editor.get_editor_world()
    report['world_after'] = world_after.get_path_name() if world_after else None
    report['same_world_object'] = world_before == world_after
    assert report['same_world_object'] and report['world_before'] == report['world_after'], 'Current world unexpectedly changed'
    report['backed_up_package_files'] = len(report['assets'])
    report['external_referencer_packages'] = sorted(set(
        ref for refs in report['external_referencers'].values() for ref in refs))
    report['deletion_gate_passed'] = not bool(report['external_referencers'])
    report['next_action'] = (
        'STOP: report external references to the parent; do not delete or rewrite referenced assets.'
        if report['external_referencers'] else
        'Inspection passed for these five packages only. This script has not deleted anything. Recheck references immediately before a separately authorized exact-package replacement.'
    )
    report['success'] = True
except Exception:
    report['error'] = traceback.format_exc()

report['completed_utc'] = datetime.now(timezone.utc).isoformat()
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'legacy_inspection_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('ENVELOPE_LEGACY_INSPECTION ' + json.dumps(report))
