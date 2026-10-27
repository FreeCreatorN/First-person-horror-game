"""Read-only, package-level ownership and conservative unused-asset analysis.

Only OwnershipPlan.json is written. A directory, SM_OTS name, dependency hash
bag, current_asset_sha256, or a preserved user's package is never ownership
proof. No Unreal process is launched and no Content package is changed.
"""
import collections
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CONTENT = R / 'Content'
OUTPUTS = R / 'Saved/CodexOutputs'
W = OUTPUTS / 'OldTownDoorReuse_20261017'
OWNED_ROOT = '/Game/CodexGenerated/OldTown/'
REQUIRED_ROOTS = ('/Game/Yastar/Maps/L_Main',
                  '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',
                  '/Game/CodexGenerated/OldTownVersion2/Maps/老城区第二版')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def package_file(package):
    stem = CONTENT / package.removeprefix('/Game/')
    for extension in ('.uasset', '.umap'):
        path = stem.with_suffix(extension)
        if path.is_file():
            return path
    return None


def file_package(path):
    return '/Game/' + Path(path).resolve().relative_to(CONTENT).with_suffix('').as_posix()


def key(package):
    return package.casefold()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', type=Path, default=W / 'AssetReferences.json',
                        help='Fresh all-project hard/soft/management registry export; permits an after-apply recheck')
    args = parser.parse_args()
    assert not (W / 'FinalReview.json').exists(), 'An accepted analysis stage is immutable'
    source = args.references.resolve()
    refs_sha = sha(source)
    refs = read(source)
    assert refs['passed'] and refs['includes_hard_soft_and_management']
    before = read(W / 'ReadOnlyProtectedBefore.json')['file_sha256']
    inventory = read(W / 'DoorInventory.json')
    source_map = CONTENT / 'Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    assert inventory['passed'] and inventory['no_save_or_explicit_compile_called']
    current_map_sha = sha(source_map)
    if source == (W / 'AssetReferences.json').resolve():
        assert current_map_sha == inventory['map_sha256'] == before[str(source_map)]
    else:
        assert source.stat().st_mtime_ns >= source_map.stat().st_mtime_ns, 'References must be exported after the current map save'
        if refs.get('map_sha256'):
            assert refs['map_sha256'] == current_map_sha
    records, spelling, graph, inputs = {}, {}, collections.defaultdict(set), {}
    for row in refs['assets']:
        node = key(row['package'])
        spelling.setdefault(node, row['package'])
        records.setdefault(node, []).append(row)
        for dependency in row.get('dependencies', []):
            if dependency.startswith('/Game/'):
                graph[node].add(key(dependency))
                spelling.setdefault(key(dependency), dependency)
        # Union reverse declarations too: an asymmetric reference is retained.
        for referencer in row.get('referencers', []):
            if referencer.startswith('/'):
                graph[key(referencer)].add(node)
                spelling.setdefault(key(referencer), referencer)
    disk = {key(file_package(p)): p for p in CONTENT.rglob('*')
            if p.is_file() and p.suffix.lower() in ('.uasset', '.umap')}
    assert set(disk) == set(records), 'Registry packages and actual disk packages differ; refresh the inventory'
    assert len(disk) == len({p.resolve() for p in disk.values()})
    provenance = collections.defaultdict(list)
    latest = {}

    def input_record(path):
        path = Path(path)
        inputs[str(path)] = sha(path)

    def add(file, digest, manifest, field, script, reason):
        file = Path(file).resolve()
        if not file.is_relative_to(CONTENT) or file.suffix.lower() not in ('.uasset', '.umap'):
            return
        package = file_package(file)
        # These manifests are explicitly creation-scoped OldTown stage manifests.
        # Never generalize their containing folders to other packages.
        assert package.startswith(OWNED_ROOT), (manifest, field, package)
        node = key(package)
        p = dict(manifest=str(manifest), field=field, creation_script=str(script),
                 recorded_sha256=digest, reason=reason)
        provenance[node].append(p)
        latest[node] = p

    # Ordered authoring evidence: later assistant stages supersede earlier
    # fingerprints only for the same explicitly declared newly authored file.
    recipes = (
        ('StreetRefinement_20261007', 'BuildReport.json', 'new_asset_sha256', 'ApplyOldTownStreetRefinement.py'),
        ('OldTownRealism_20261012', 'FinalReview.json', 'new_asset_sha256', 'ApplyOldTownRealism.py'),
        ('OldTownRealismRefinement_20261013', 'Applied.json', 'new_asset_sha256', 'ApplyOldTownRealismRefinement.py'),
        ('OldTownSoftGoodsRefinement_20261013', 'Applied.json', 'new_asset_sha256', 'ApplyOldTownSoftGoodsRefinement.py'),
        ('OldTownCallableLighting_20261016', 'Applied.json', 'new_asset_sha256', 'ApplyOldTownCallableLighting.py'),
        ('OldTownFunctionalLighting_20261017', 'Applied.json', 'new_asset_sha256', 'ApplyOldTownFunctionalLighting.py'),
    )
    for stage, name, field, script_name in recipes:
        manifest = OUTPUTS / stage / name
        script = R / 'Scripts' / script_name
        doc = read(manifest)
        assert doc.get('passed') is True or doc.get('status') == 'PASS'
        assert isinstance(doc[field], dict) and script.is_file()
        input_record(manifest); input_record(script)
        for file, digest in doc[field].items():
            add(file, digest, manifest, field, script,
                'Explicit authored/new package fingerprint, backed by its generation stage; dependency-only bags excluded')
    # This one material probe was authored outside the production map's set.
    probe_manifest = OUTPUTS / 'SurfaceSeparation_20261009/MaterialProbe.json'
    probe = read(probe_manifest)
    probe_script = R / 'Scripts/ProbeOldTownSurfaceMaterial.py'
    input_record(probe_manifest); input_record(probe_script)
    assert probe['passed']
    for row in probe['assets']:
        if row['asset'] == probe['test_material'] and not row.get('reused', False):
            add(row['file'], row['sha256'], probe_manifest, 'assets[test_material]', probe_script,
                'Explicit newly saved test instance, including exact package file fingerprint')

    # Old opening BPs have reliable creation/relocation provenance, but the
    # relocation report does not provide an immediate post-create byte hash.
    # A later current/generated snapshot is not sufficient to rule out a user
    # edit. Therefore record them, but freeze them rather than infer deletability.
    relocated = read(OUTPUTS / 'OpeningRelocation_20261007/Moved.json')
    input_record(OUTPUTS / 'OpeningRelocation_20261007/Moved.json')
    input_record(R / 'Scripts/BuildOldTownOpeningBlueprints.py')
    input_record(R / 'Scripts/ApplyOldTownHotelOpenings.py')
    input_record(R / 'Scripts/ApplyOldTownHotelArchitecture.py')
    input_record(R / 'Scripts/ProbeOldTownOpeningBlueprintAPI.py')
    assert relocated['passed']
    legacy_declared = {key(r['new']): r for r in relocated['relocations']}

    # The separately created historical review map has an exact subsequent
    # assistant rename/save hash. It is an optional candidate, never deleted here.
    review_package = '/Game/Yastar/Maps/Scenes/L_OldTownHotelReview_20261004'
    review = next(r for r in relocated['maps'] if r['level'] == review_package)
    map_creation = OUTPUTS / 'HotelOpenings_20261004/BuildReport.json'
    map_doc = read(map_creation)
    input_record(map_creation)
    assert map_doc['status'] == 'PASS' and map_doc['target_level'] == review_package
    assert map_doc['hotel_openings']['preview'] is True
    node = key(review_package)
    record = dict(manifest=str(OUTPUTS / 'OpeningRelocation_20261007/Moved.json'),
        field='maps[review].new_sha256', creation_manifest=str(map_creation),
        creation_script=str(R / 'Scripts/ApplyOldTownHotelOpenings.py'),
        recorded_sha256=review['new_sha256'],
        reason='Script explicitly created this separate preview map; exact later assistant relocation/save fingerprint')
    provenance[node].append(record); latest[node] = record

    current_hashes = {}
    owned_matching, modified, unknown_old, legacy_frozen = set(), set(), set(), set()
    for node, file in disk.items():
        in_oldtown = file_package(file).startswith(OWNED_ROOT)
        if node not in latest and not in_oldtown:
            continue
        current_hashes[node] = sha(file)
        if node in latest:
            if current_hashes[node] == latest[node]['recorded_sha256']:
                owned_matching.add(node)
            else:
                modified.add(node)
        elif node in legacy_declared:
            legacy_frozen.add(node)
        else:
            unknown_old.add(node)

    # Runtime/plugin source and configuration may use explicit string loads
    # outside the registry's package edges. Keep every actual package named by
    # such a literal. Historical generation/capture Python is not a runtime root.
    runtime_literals = []
    scan_files = [R / 'HorrorGame.uproject']
    scan_files += [p for p in (R / 'Config').rglob('*') if p.is_file() and p.suffix.lower() == '.ini']
    if (R / 'Source').is_dir():
        scan_files += [p for p in (R / 'Source').rglob('*') if p.is_file() and p.suffix.lower() in ('.cpp', '.h', '.cs')]
    for plugin in (R / 'Plugins').iterdir():
        if not plugin.is_dir():
            continue
        scan_files += list(plugin.glob('*.uplugin'))
        for area in ('Source', 'Config'):
            if (plugin / area).is_dir():
                scan_files += [p for p in (plugin / area).rglob('*') if p.is_file()
                               and p.suffix.lower() in ('.cpp', '.h', '.cs', '.ini')]
    literal_roots = set()
    for file in scan_files:
        text = file.read_text(encoding='utf-8-sig', errors='replace')
        found = sorted({token.split('.', 1)[0] for token in
                        re.findall(r"/Game/[^\s\"'<>(),;{}\\\[\]]+", text)})
        matches = sorted({key(package) for package in found if key(package) in records})
        if matches:
            runtime_literals.append(dict(file=str(file), packages=[spelling[n] for n in matches]))
            literal_roots.update(matches)
        input_record(file)
    roots = set(records) - owned_matching
    roots.update(key(p) for p in REQUIRED_ROOTS)
    roots.update(literal_roots)
    # Unknown package identifiers and external referencers are conservative roots.
    all_nodes = set(graph) | {d for ds in graph.values() for d in ds} | set(records)
    roots.update(all_nodes - set(records))
    def closure(root_set):
        reached, predecessor, pending = set(), {}, collections.deque(sorted(root_set))
        for n in root_set:
            predecessor[n] = None
        while pending:
            node = pending.popleft()
            if node in reached:
                continue
            reached.add(node)
            for dependency in sorted(graph.get(node, ())):
                if dependency not in predecessor:
                    predecessor[dependency] = node
                    pending.append(dependency)
        return reached, predecessor

    reached, predecessor = closure(roots)
    registry_only_unused = owned_matching - reached
    # A serialized FString/name can contain a complete /Game path without an
    # AssetRegistry soft-object edge. Scan every protected/non-owned package and
    # every retained dependency, then repeat for newly retained packages. UTF-16
    # strings can start at either byte alignment in an Unreal archive.
    literal_pattern = re.compile(r"/Game/[^\x00-\x20\"'<>(),;{}\[\]\\]+")
    binary_scanned, binary_reasons = set(), []
    while True:
        to_scan = (reached & set(disk)) - binary_scanned
        if not to_scan:
            break
        added_roots = set()
        for origin in sorted(to_scan):
            file = disk[origin]
            data = file.read_bytes()
            input_record(file)
            encodings = []
            if b'/Game/' in data:
                encodings.append(('utf-8', data.decode('utf-8', errors='ignore')))
            if '/Game/'.encode('utf-16-le') in data:
                encodings.extend(('utf-16-le', data[alignment:].decode('utf-16-le', errors='ignore'))
                                 for alignment in (0, 1))
            seen_matches = set()
            for encoding, text in encodings:
                for match in literal_pattern.finditer(text):
                    literal = match.group(0)
                    package = literal.split('.', 1)[0].split(':', 1)[0].rstrip('/')
                    target = key(package)
                    if target not in registry_only_unused:
                        continue
                    # Require actual contiguous bytes for the complete literal;
                    # never match a short material/asset basename or a prefix.
                    offset = data.find(literal.encode(encoding))
                    signature = (target, encoding, offset, literal)
                    if offset < 0 or signature in seen_matches:
                        continue
                    seen_matches.add(signature)
                    binary_reasons.append(dict(source_package=spelling.get(origin, file_package(file)),
                        source_file=str(file), source_sha256=inputs[str(file)],
                        target_package=spelling.get(target, package), encoding=encoding,
                        byte_offset=offset, complete_literal=literal,
                        reason='Complete serialized /Game package/object path in a protected or retained package'))
                    added_roots.add(target)
            binary_scanned.add(origin)
        roots.update(added_roots)
        reached, predecessor = closure(roots)
    unused = owned_matching - reached
    retained = owned_matching & reached
    assert not any(d in unused for n in reached for d in graph.get(n, ())), 'Retained-to-deletion dependency crosses the closure'

    def record_for(node):
        file = disk[node]
        return dict(package=spelling.get(node, file_package(file)), file=str(file), bytes=file.stat().st_size,
                    current_sha256=current_hashes[node], creation_provenance=provenance.get(node, []),
                    source_origin=latest.get(node))

    def path_to_root(node):
        out = [node]
        while predecessor.get(node) is not None:
            node = predecessor[node]
            out.append(node)
        return [spelling.get(n, n) for n in reversed(out)]

    candidates = []
    for node in sorted(unused):
        row = record_for(node)
        row.update(reason='Exact authored fingerprint matches and no path from any protected/non-owned/unknown root',
                   optional_historical_preview_map=node == key(review_package),
                   direct_referencers=sorted({p for r in records[node] for p in r.get('referencers', [])}),
                   candidate_dependencies=[spelling.get(d, d) for d in sorted(graph.get(node, ())) if d in unused],
                   deletion_performed=False)
        candidates.append(row)
    used = []
    for node in sorted(retained):
        row = record_for(node)
        row['retention_path_from_root'] = path_to_root(node)
        row['serialized_literal_reference_reasons'] = [r for r in binary_reasons
                                                       if key(r['target_package']) == node]
        used.append(row)
    frozen = []
    for node in sorted(modified | unknown_old | legacy_frozen):
        row = record_for(node)
        if node in modified:
            row['reason'] = 'Current bytes differ from the latest explicit assistant authored fingerprint; possible user edit, freeze'
        elif node in legacy_frozen:
            row.update(reason='Creation/relocation provenance exists, but no immediate authored package byte hash; later general snapshots do not prove absence of user edits',
                       relocation=legacy_declared[node])
        else:
            row['reason'] = 'No explicit package creation manifest found; folder/name alone is insufficient'
        frozen.append(row)

    # Record source import declarations outside CodexGenerated as uncertain, not
    # eligible. FBX source hashes are not hashes of the resulting UE package.
    declared_external = []
    for stage, path, script in (
        ('HotelArchitecture_20261005', ('hotel_architecture', 'imported_assets'), 'ApplyOldTownHotelArchitecture.py'),
        ('HotelOperations_20261006', ('hotel_operations', 'imports'), 'ApplyOldTownHotelOperations.py'),
    ):
        manifest = OUTPUTS / stage / 'BuildReport.json'
        doc = read(manifest)
        for p in path:
            doc = doc[p]
        input_record(manifest); input_record(R / 'Scripts' / script)
        for row in doc:
            package = row['asset'].split('.')[0]
            if key(package) in records:
                declared_external.append(dict(package=package, creation_import_manifest=str(manifest),
                    source_fbx_sha256=row.get('source_sha256'), frozen=True,
                    reason='Authored import declared, but FBX source SHA is not a post-import UAsset SHA; no safe deletion inference'))

    assert sha(source) == refs_sha and sha(source_map) == current_map_sha, 'Input changed while analyzing'
    # Also bind every binary scanned to the bytes just read, with no intervening
    # asset writes permitted during this analysis.
    assert all(sha(file) == digest for file, digest in inputs.items()), 'An analysis source changed'
    for file in (W / 'DoorInventory.json', W / 'ReadOnlyProtectedBefore.json', source):
        input_record(file)
    report = dict(passed=True, analysis_only=True, unreal_started=False, deletion_performed=False,
        created_utc=datetime.now(timezone.utc).isoformat(), map_sha256=current_map_sha,
        original_door_inventory_map_sha256=inventory['map_sha256'], references_file=str(source),
        target_level=inventory['target_level'], registry_asset_data_rows=len(refs['assets']),
        distinct_package_count=len(records), disk_package_count=len(disk), registry_disk_packages_exact_match=True,
        graph_policy='Case-insensitive package union; hard, soft and management dependency declarations plus all reverse referencer declarations',
        ownership_policy='Explicit authored-package manifest plus generation script plus fresh matching authored UAsset SHA; no directory/name/current_asset_sha256 ownership inference',
        root_policy='Main, current original, V2, every non-explicitly-owned package, every uncertain/modified package, and external/unknown reference identifiers',
        root_count=len(roots), roots=sorted(spelling.get(n, n) for n in roots),
        explicit_runtime_or_config_package_roots=runtime_literals,
        serialized_package_path_scan=dict(scanned_protected_or_retained_packages=len(binary_scanned),
            encodings=['UTF8', 'UTF16LE at both byte alignments'],
            registry_only_unused_before_binary_scan=len(registry_only_unused),
            newly_protected_after_literal_scan=len(registry_only_unused & reached),
            retained_until_fixed_point=True, complete_path_matches_only=True,
            literal_reference_reasons=binary_reasons),
        summary=dict(codex_oldtown_packages=sum(file_package(p).startswith(OWNED_ROOT) for p in disk.values()),
            explicit_authored_fingerprint_packages_on_disk=len(set(latest) & set(disk)),
            proven_owned_matching=len(owned_matching), owned_still_used=len(retained),
            deletable_candidates=len(unused), candidate_bytes=sum(r['bytes'] for r in candidates),
            optional_historical_preview_candidates=sum(r['optional_historical_preview_map'] for r in candidates),
            frozen_changed_owned_hash=len(modified), frozen_legacy_missing_authored_hash=len(legacy_frozen),
            frozen_oldtown_no_creation_manifest=len(unknown_old),
            frozen_outside_oldtown_import_declarations=len(declared_external),
            all_other_non_owned_or_unproven_packages=len(set(records) - owned_matching)),
        candidates=candidates, owned_still_used=used, frozen_oldtown_or_modified=frozen,
        frozen_external_import_declarations=declared_external, input_sha256=inputs,
        protected_scopes=['All non-owned/user Content including Characters, MainHome, user Blueprints and shared assets',
                          'Main, original old town and OldTownVersion2 maps',
                          'All Saved evidence, prior published reports, backups, source art and scripts'],
        limitations=['A candidate set is a batch proposal; candidate-to-candidate references may exist.',
                     'Refresh all project references after door consolidation and before applying any cleanup. Recheck candidate bytes and referencers immediately before deletion.',
                     'Runtime/config and protected/retained UAsset/UMAP complete UTF8/UTF16LE package strings were added as roots to a fixed point; fully dynamically constructed paths cannot be proven by any literal scan.',
                     'Saved backups and old reports are never candidates; historical ownership does not authorize deleting current user edits.'])
    (W / 'OwnershipPlan.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=True, summary=report['summary'],
                         report=str(W / 'OwnershipPlan.json'), sha256=sha(W / 'OwnershipPlan.json')), ensure_ascii=False))


if __name__ == '__main__':
    main()
