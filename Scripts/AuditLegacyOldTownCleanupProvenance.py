"""Read-only retrospective provenance audit; never modifies a package or old report.

The former Realism cumulative new_asset_sha256 bag is not creation evidence.
This audit resolves the actual generating stage for every previously isolated
package, independently checks its backup bytes, and freezes missing evidence.
"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[1]
S = R / 'Saved/CodexOutputs'
OLD = S / 'OldTownDoorReuse_20261017'
W = S / 'OldTownHotelNaming_20261017'
OUT = W / 'LegacyCleanupProvenanceAudit.json'
INPUTS = {}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def bind(path):
    path = Path(path).resolve()
    INPUTS[str(path)] = sha(path)
    return path


def read(path):
    return json.loads(bind(path).read_text(encoding='utf-8-sig'))


def script(name):
    return str(bind(R / 'Scripts' / name))


def stage(name, filename):
    path = S / name / filename
    return path, read(path)


def checkpoint(path, field, original, expected):
    doc = read(path)
    assert doc[field][original] == expected
    return dict(manifest=str(Path(path).resolve()), field=field,
                recorded_sha256=expected, timing='Generating-stage authored package checkpoint; not claimed to be the first creation instant')


def log_index(stage_name):
    """Index exact package saves and actual source-file FactoryCreateFile blocks."""
    saves, factories = defaultdict(list), defaultdict(list)
    for path in sorted((S / stage_name).glob('*.log')):
        if '.stdout.' in path.name or 'Console' in path.name:
            continue
        lines = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
        caller = next(((i + 1, line) for i, line in enumerate(lines) if '-script=' in line), None)
        if not caller:
            continue
        caller_match = re.search(r'-script=([^\s"\r\n]+\.py)', caller[1])
        if not caller_match:
            continue
        called = Path(caller_match.group(1)).resolve()
        if not called.is_relative_to(R / 'Scripts') or not called.is_file():
            continue
        active = None
        used = False
        for i, line in enumerate(lines, 1):
            if 'FactoryCreateFile: StaticMesh with FbxFactory' in line:
                match = re.search(r'FactoryCreateFile: StaticMesh with FbxFactory \(0 0 (.+)\)$', line)
                active = (match.group(1), i, line) if match else None
            match = re.search(r'Saving Package: (/Game/[^\s]+)$', line)
            if not match:
                continue
            package = match.group(1)
            evidence = dict(file=str(path.resolve()), line=i, text=line,
                caller_script=str(called), caller_line=caller[0], caller_text=caller[1])
            saves[package].append(evidence)
            used = True
            if active and i - active[1] < 45:
                stem, name = Path(active[0]).stem, package.rsplit('/', 1)[-1]
                if (name == stem + '_Import' or name.startswith(stem + '_Import_')
                        or name == stem + '_SourceModel' or name.startswith(stem + '_SourceModel_')
                        or name == 'SM_R_AxisProbe'):
                    factories[package].append(dict(**evidence, source_file=active[0],
                        factory_line=active[1], factory_text=active[2],
                        factory_and_save_within_lines=i - active[1]))
        if used:
            bind(path)
            bind(called)
    for mapping in (saves, factories):
        for rows in mapping.values():
            rows.sort(key=lambda row: (row['text'][:25], row['file'], row['line']))
    return saves, factories


def generation_report(row, manifest, field, generating_script, helper, evidence):
    value = dict(classification='proven', actual_creation_script=script(generating_script),
        actual_creation_helper=script(helper) if helper else None,
        authored_sha256_evidence=checkpoint(manifest, field, row['file'], row['current_sha256']),
        generation_evidence=evidence,
        proof_basis='Actual generating-stage recipe/report and exact package generation log, plus that stage authored package SHA; inherited Realism bag not used as creation proof')
    return value


def main():
    assert not OUT.exists(), 'Retrospective audit evidence is append-only; do not overwrite it'
    approval = read(OLD / 'OfflineCleanupApproved.json')
    result = read(OLD / 'OfflineCleanupResult.json')
    assert approval['passed'] and result['passed']
    assert sha(OLD / 'OfflineCleanupApproved.json') == result['approval_sha256']
    manifest = read(result['manifest_file'])
    assert sha(result['manifest_file']) == result['manifest_sha256']
    candidates = approval['candidate_files']
    assert len(candidates) == approval['candidate_count'] == result['isolated_count'] == 601
    isolated = {r['original_path']: r for r in manifest['files']}
    assert len(isolated) == len(candidates)
    assert set(isolated) == {r['file'] for r in candidates}
    child_path = W / 'LegacyMaterialOrigins.json'
    child = read(child_path)
    assert child['passed'] and child['no_ue_launched'] and child['no_content_or_script_changes']
    for path, expected in child['input_sha256'].items():
        assert sha(path) == expected, 'Independent source evidence changed: ' + path
        INPUTS[path] = expected
    surface = {r['original_file']: r for r in child['proven'] + child['uncertain']}
    assert len(surface) == child['summary']['candidate_count'] == 162

    realism_path, realism = stage('OldTownRealism_20261012', 'FinalReview.json')
    assert realism['passed'] and len(realism['new_root_asset_sha256']) == 682
    material_path, materials = stage('OldTownRealism_20261012', 'MaterialBuild.json')
    material_rows = {r['file']: (i, r) for i, r in enumerate(materials['assets'])}
    rsaves, rimports = log_index('OldTownRealism_20261012')
    ssaves, simports = log_index('OldTownSoftGoodsRefinement_20261013')
    stsaves, _ = log_index('StreetRefinement_20261007')
    bsaves, _ = log_index('HotelRedesign_20261008_V4')
    street_path, street = stage('StreetRefinement_20261007', 'BuildReport.json')
    soft_path, soft = stage('OldTownSoftGoodsRefinement_20261013', 'Applied.json')
    bp_path, blueprints = stage('HotelRedesign_20261008_V4', 'BuildReport.json')
    preview_path, preview = stage('HotelOpenings_20261004', 'BuildReport.json')
    moved_path, moved = stage('OpeningRelocation_20261007', 'Moved.json')
    assert street['status'] == blueprints['status'] == preview['status'] == 'PASS'
    assert soft['passed'] and len(soft['new_asset_sha256']) == 40
    street_signs = street['street_refinement']['new_signs']

    rows = []
    for source in candidates:
        original, package, expected = source['file'], source['package'], source['current_sha256']
        backup = isolated[original]
        assert backup['sha256'] == expected and sha(backup['isolated_path']) == expected
        bind(backup['isolated_path'])
        current_exists = Path(original).exists()
        assert not current_exists or sha(original) == expected, 'Restored original has different current bytes'
        row = dict(package=package, original_file=original, isolated_file=backup['isolated_path'],
            current_sha256=expected, isolated_sha256_verified=True, original_currently_present=current_exists,
            old_claimed_origin=source['source_origin'])
        if original in surface:
            detail = surface[original]
            assert detail['current_sha256'] == expected and detail['isolated_bytes_match_historical_generation_sha256']
            row.update(classification=detail['classification'], actual_creation_script=detail['creation_script'],
                actual_creation_helper=detail.get('helper_script'), independent_detail=detail,
                proof_basis=detail['proof_basis'])
        elif '/Realism_20261012/Meshes/ImportData/' in package:
            assert realism['new_root_asset_sha256'][original] == expected
            assert rimports.get(package), 'No actual FactoryCreateFile source-to-exact-package evidence'
            evidence = rimports[package][0]
            row.update(classification='proven', actual_creation_script=evidence['caller_script'],
                actual_creation_helper=script('OldTownRealismImport.py'),
                generation_evidence=evidence,
                authored_sha256_evidence=checkpoint(realism_path, 'new_root_asset_sha256', original, expected),
                creation_api='AssetImportTask + FbxFactory; replace_existing=False; a real source import block precedes this exact package save',
                proof_basis='Actual FbxFactory import and exact package save by the recorded assistant generator, with same Realism-stage private-root authored SHA checkpoint',
                sha_timing_limit='Retained hash is a generating-stage checkpoint; not asserted to be the first import invocation hash')
        elif '/Realism_20261012/Materials/' in package:
            assert realism['new_root_asset_sha256'][original] == expected
            hit = material_rows.get(original)
            if hit and hit[1]['sha256'] == expected and rsaves.get(package):
                index, recipe = hit
                assert recipe['kind'] in ('master', 'offset_instance')
                evidence = rsaves[package][0]
                row.update(classification='proven', actual_creation_script=evidence['caller_script'],
                    actual_creation_helper=script('OldTownRealismMaterials.py'),
                    generation_evidence=evidence,
                    authored_sha256_evidence=dict(manifest=str(material_path.resolve()),
                        pointer='/assets/' + str(index) + '/sha256', recorded_sha256=expected,
                        timing='Generating-stage per-material save/report checkpoint'),
                    authored_recipe=recipe,
                    proof_basis='Per-material authored generator report with kind/role/offset and exact SHA plus actual exact-package save by its assistant caller')
            else:
                row.update(classification='uncertainToRestore', actual_creation_script=(rsaves.get(package) or [{}])[0].get('caller_script'),
                    actual_creation_helper=script('OldTownRealismMaterials.py'),
                    known_generation_save_evidence=(rsaves.get(package) or [None])[0],
                    later_same_stage_hash=checkpoint(realism_path, 'new_root_asset_sha256', original, expected),
                    reason='No surviving package-specific material creation/report entry. PrepareAssets role loop and save logs suggest assistant origin, but the later private-root checkpoint alone is not accepted as creation proof.',
                    recommendation='Restore this exact isolated file with UE closed; do not infer ownership from the folder or name.')
        elif '/SoftGoodsRefinement_20261013/Meshes/ImportData/' in package:
            assert simports.get(package)
            row.update(generation_report(source, soft_path, 'new_asset_sha256',
                Path(simports[package][0]['caller_script']).name, 'OldTownRealismImport.py', simports[package][0]))
            row['creation_api'] = 'Real source FbxFactory import into SoftGoods private namespace, followed by exact package save; replace_existing=False'
        elif '/StreetRefinement_20261007/' in package:
            signs = [r for r in street_signs if package in (r['material_asset'].split('.')[0], r['texture_asset'].split('.')[0])]
            assert len(signs) == 1 and stsaves.get(package)
            row.update(generation_report(source, street_path, 'new_asset_sha256',
                'ApplyOldTownStreetRefinement.py', None, dict(log=stsaves[package][0], authored_sign=signs[0])))
            row['creation_api'] = ('TextureFactory source import with metadata SHA guard' if '/Textures/' in package
                else 'MaterialFactoryNew; existing material branch requires explicit assistant Owned metadata')
        elif '/Blueprints/Openings/BP_OTS_V4_Window_' in package:
            placements = [r for r in blueprints['hotel_v4']['placed_windows'] if r['blueprint'] == package]
            assert placements and bsaves.get(package)
            row.update(generation_report(source, bp_path, 'new_asset_sha256',
                'ApplyOldTownHotelV4.py', 'BuildOldTownOpeningBlueprints.py',
                dict(log=bsaves[package][0], placement_count=len(placements),
                    authored_component_specs=placements[0]['components'])))
            row['creation_api'] = 'create_blueprint_asset_with_parent and authored named component specifications in the generating V4 stage'
        elif package == '/Game/Yastar/Maps/Scenes/L_OldTownHotelReview_20261004':
            assert preview['target_level'] == package and preview['hotel_openings']['preview'] is True
            changes = [r for r in moved['maps'] if r['level'] == package]
            assert len(changes) == 1 and changes[0]['old_sha256'] == preview['map_sha256']
            assert changes[0]['new_sha256'] == expected
            row.update(classification='proven', actual_creation_script=script('ApplyOldTownHotelOpenings.py'),
                actual_creation_helper=None, creation_api='duplicate_asset(SOURCE_LEVEL, TARGET) creates the assistant review map',
                generation_evidence=dict(manifest=str(preview_path.resolve()), preview=True,
                    initial_authored_map_sha256=preview['map_sha256']),
                later_assistant_reference_only_save=dict(manifest=str(moved_path.resolve()), record=changes[0]),
                authored_sha256_evidence=dict(manifest=str(moved_path.resolve()), field='maps[review].new_sha256', recorded_sha256=expected),
                proof_basis='Explicit assistant-created preview map plus exact old-to-new hash chain through the assistant opening-reference relocation')
        else:
            row.update(classification='uncertainToRestore', reason='No explicitly supported creation lineage was reconstructed',
                recommendation='Restore the exact backup; ownership remains frozen')
        row['old_creation_stage_misattributed'] = ('OldTownRealism_20261012' in source['source_origin']['manifest']
            and '/Realism_20261012/' not in package)
        rows.append(row)

    assert len(rows) == 601 and len({r['original_file'] for r in rows}) == 601
    proven = [r for r in rows if r['classification'] == 'proven']
    uncertain = [r for r in rows if r['classification'] == 'uncertainToRestore']
    assert all(sha(path) == expected for path, expected in INPUTS.items()), 'An immutable evidence input changed during audit'
    report = dict(passed=True, complete_candidate_audit=True, audit_utc=datetime.now(timezone.utc).isoformat(),
        original_stage=str(OLD), read_only=True, unreal_started=False, content_or_config_written=False,
        no_old_accepted_report_modified=True, no_restoration_or_deletion_performed=True,
        classification_standard='Explicit actual generating stage/caller/API and package-specific generation evidence plus matching historical authored SHA. Inherited cumulative bags alone are never creation proof. Missing direct material creation/report evidence is frozen for restoration.',
        summary=dict(total_isolated_candidates=len(rows), proven=len(proven), uncertainToRestore=len(uncertain),
            old_creation_stage_misattributions=sum(r['old_creation_stage_misattributed'] for r in rows),
            actual_creator_script_counts=dict(Counter(Path(r['actual_creation_script']).name for r in proven)),
            proven_bytes=sum(isolated[r['original_file']]['bytes'] for r in proven),
            uncertain_bytes=sum(isolated[r['original_file']]['bytes'] for r in uncertain)),
        inherited_realism_bag_error=dict(script=str(R / 'Scripts/AnalyzeOldTownOwnedUnusedAssets.py'),
            field='OldTownRealism FinalReview.new_asset_sha256',
            diagnosis='ApplyOldTownRealism.py reads the preceding SanitaryFinish BuildReport and updates its cumulative bag with only the new Realism root. The inherited entries must retain their true earlier creator lineage.',
            corrected_by='This report reconstructs true Surface/HotelDetails/V4 Blueprint lineage rather than treating the accumulated hash bag as ApplyRealism creation.'),
        proven=proven, uncertainToRestore=uncertain, candidate_rows=rows,
        independent_surface_hotel_audit=dict(file=str(child_path), sha256=sha(child_path), summary=child['summary']),
        source_isolation_manifest=str(Path(result['manifest_file']).resolve()),
        input_sha256=INPUTS,
        limits=['Generating-stage checkpoint hashes are explicitly distinguished from hashes retained immediately after the first creation invocation.',
            'This is an ownership audit of a past isolation operation, not authorization for any new deletion or renaming.',
            'Files classified uncertainToRestore must be restored only from their exact hash-verified isolated backup, with all UE processes closed and without overwriting any existing user file.'])
    W.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=True, summary=report['summary'], report=str(OUT), sha256=sha(OUT)), ensure_ascii=False))


if __name__ == '__main__':
    main()
