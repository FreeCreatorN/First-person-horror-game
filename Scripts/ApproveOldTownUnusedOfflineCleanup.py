"""Final UE read-only gate for offline removal of exact assistant-owned packages.

This script intentionally never calls EditorAssetLibrary.delete_asset: in UE5.7
that API invokes ForceDeleteObjects. Only OfflineCleanupApproved.json is saved.
Run the separate offline mover after this owned UE helper exits normally.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import unreal

R = Path(unreal.Paths.project_dir()).resolve()
CONTENT = R / 'Content'
W = R / 'Saved/CodexOutputs/OldTownDoorReuse_20261017'
MAP = CONTENT / 'Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
PREVIEW = '/Game/Yastar/Maps/Scenes/L_OldTownHotelReview_20261004'
PROTECTED = {'/game/yastar/maps/l_main', '/game/yastar/maps/scenes/l_oldtownschoolstreet',
             '/game/codexgenerated/oldtownversion2/maps/老城区第二版'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def files():
    return {str(p): sha(p) for base in (CONTENT, R / 'Config') for p in base.rglob('*') if p.is_file()}


def package_for(file):
    return '/Game/' + file.relative_to(CONTENT).with_suffix('').as_posix()


def canonical_graph(rows):
    graph = {}
    for row in rows:
        package = row['package'].casefold()
        graph.setdefault(package, set())
        graph[package].update(p.casefold() for p in row.get('dependencies', []) if p.startswith('/'))
        for ref in row.get('referencers', []):
            if ref.startswith('/'):
                graph.setdefault(ref.casefold(), set()).add(package)
    return graph


def verify_origin(row, hashes):
    origin = row['source_origin']
    assert origin and origin in row['creation_provenance']
    manifest = Path(origin['manifest']).resolve()
    script = Path(origin['creation_script']).resolve()
    assert str(manifest) in hashes and sha(manifest) == hashes[str(manifest)]
    assert str(script) in hashes and sha(script) == hashes[str(script)]
    doc = read(manifest)
    assert doc.get('passed') is True or doc.get('status') == 'PASS'
    field, expected = origin['field'], row['current_sha256']
    if field == 'new_asset_sha256':
        assert doc[field][row['file']] == expected == origin['recorded_sha256']
    elif field == 'assets[test_material]':
        matches = [r for r in doc['assets'] if Path(r['file']).resolve() == Path(row['file']).resolve()
                   and r['asset'] == doc['test_material'] and not r.get('reused', False)]
        assert len(matches) == 1 and matches[0]['sha256'] == expected
    elif field == 'maps[review].new_sha256':
        assert row['package'] == PREVIEW
        matches = [r for r in doc['maps'] if r['level'] == PREVIEW]
        assert len(matches) == 1 and matches[0]['new_sha256'] == expected
        creation = Path(origin['creation_manifest']).resolve()
        assert sha(creation) == hashes[str(creation)]
        created = read(creation)
        assert created['status'] == 'PASS' and created['target_level'] == PREVIEW
        assert created['hotel_openings']['preview'] is True
    else:
        raise AssertionError('Unsupported ownership proof; freeze rather than infer: ' + field)


def main():
    assert not (W / 'FinalReview.json').exists() and not (W / 'OfflineCleanupApproved.json').exists()
    plan_file = W / 'OwnershipPlan.json'
    plan = read(plan_file)
    assert plan['passed'] and plan['analysis_only'] and not plan['deletion_performed']
    assert plan['serialized_package_path_scan']['retained_until_fixed_point']
    assert plan['serialized_package_path_scan']['complete_path_matches_only']
    assert sha(MAP) == plan['map_sha256']
    applied = read(W / 'AppliedDoorReuse.json')
    audit = read(W / 'DoorReuseReadback.json')
    assert applied['passed'] and audit['passed'] and audit['all_other_actors_native_unchanged']
    assert applied['map_sha256'] == audit['map_sha256'] == plan['map_sha256']
    assert (audit['actor_count'], audit['door_count'], audit['shared_blueprints']) == (7986, 124, 10)
    assert audit['protected']['passed'] and not audit['protected']['changed_protected_files']
    completed_readbacks = []
    for file in W.glob('*.Completion.json'):
        completion = read(file)
        if (str(Path(completion.get('script', '')).resolve()).casefold()
                == str((R / 'Scripts/AuditOldTownDoorReuse.py').resolve()).casefold()
                and completion.get('normal_zero_exit') is True and completion.get('exit_code') == 0
                and datetime.fromisoformat(completion['completed_utc'].replace('Z', '+00:00')).timestamp()
                    >= (W / 'DoorReuseReadback.json').stat().st_mtime):
            completed_readbacks.append(file)
    assert completed_readbacks, 'Successful completed fresh DoorReuseReadback helper is required'
    # Fresh all-package bytes must still match the analysis, including the
    # protected package literal-string scan sources and creation manifests.
    for file, digest in plan['input_sha256'].items():
        assert sha(file) == digest, 'Analysis evidence changed: ' + file
    references = read(plan['references_file'])
    assert references['passed'] and references['forced_disk_rescan']
    assert references['no_save_or_explicit_compile_called']
    assert references['map_sha256'] == plan['map_sha256']
    before = files()
    assert references['file_sha256'] == before, 'Fresh registry export and current packages differ'
    for file, digest in applied['new_asset_sha256'].items():
        assert before[file] == digest
    candidates = plan['candidates']
    assert candidates and len(candidates) == plan['summary']['deletable_candidates']
    packages, candidate_files = set(), {}
    for row in candidates:
        file = Path(row['file']).resolve()
        assert file.is_relative_to(CONTENT) and file.suffix.lower() in ('.uasset', '.umap')
        assert package_for(file).casefold() == row['package'].casefold()
        assert row['package'].casefold() not in PROTECTED
        assert row['package'].startswith('/Game/CodexGenerated/OldTown/') or row['package'] == PREVIEW
        assert sha(file) == row['current_sha256'] == before[str(file)]
        verify_origin(row, plan['input_sha256'])
        for suffix in ('.uexp', '.ubulk', '.uptnl'):
            assert not file.with_suffix(suffix).exists(), 'Unapproved package sidecar requires separate ownership review'
        assert row['package'].casefold() not in packages and str(file) not in candidate_files
        packages.add(row['package'].casefold()); candidate_files[str(file)] = row['current_sha256']
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    registry.scan_paths_synchronous(['/Game'], True)
    options = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,
        include_hard_package_references=True, include_searchable_names=True,
        include_soft_management_references=True, include_hard_management_references=True)
    rows = []
    for asset in registry.get_assets_by_path('/Game', True, False):
        package = str(asset.package_name)
        rows.append(dict(package=package,
            dependencies=[str(p) for p in (registry.get_dependencies(package, options) or [])],
            referencers=[str(p) for p in (registry.get_referencers(package, options) or [])]))
    graph = canonical_graph(rows)
    assert graph == canonical_graph(references['assets']), 'Registry graph changed after ownership analysis'
    assert packages.issubset({r['package'].casefold() for r in rows})
    external = [(source, target) for source, targets in graph.items() if source not in packages
                for target in targets if target in packages]
    assert not external, ('External reference found; no approval and no forced deletion', external)
    # No map or candidate is loaded/saved/deleted here. The exact saved map hash
    # binds this gate to the successful, already completed full door readback.
    assert before == files(), 'Content/Config changed during final read-only gate'
    evidence = {str(p): sha(p) for p in (plan_file, W / 'AppliedDoorReuse.json',
                W / 'DoorReuseReadback.json', Path(plan['references_file']), Path(__file__).resolve())}
    evidence.update({str(p): sha(p) for p in completed_readbacks})
    report = dict(passed=True, approved_for_offline_quarantine=True,
        approved_utc=datetime.now(timezone.utc).isoformat(), map_sha256=sha(MAP),
        map_file=str(MAP), no_map_save=True, no_content_write=True, no_delete_api_called=True,
        asset_registry_external_references=[], hard_soft_searchable_and_management_checked=True,
        candidate_count=len(candidates), candidate_files=candidates,
        all_content_config_file_sha256=before,
        protected_file_sha256={p: h for p, h in before.items() if p not in candidate_files},
        evidence_sha256=evidence, ownership_plan_sha256=sha(plan_file),
        analysis_source_sha256=plan['input_sha256'],
        offline_requirements=['UE helper and user editor must have exited before any move.',
            'Move only these exact files under Content, with matching hashes, into a fresh Saved backup directory.',
            'Verify every non-candidate protected file before and after; never delete directories or run recursive cleanup.',
            'Candidate references to each other may form cycles; offline isolation moves the full approved batch without nulling UObject references.'])
    (W / 'OfflineCleanupApproved.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('OLD_TOWN_OFFLINE_CLEANUP_GATE_PASS ' + str(len(candidates)))


if __name__ == '__main__':
    main()
