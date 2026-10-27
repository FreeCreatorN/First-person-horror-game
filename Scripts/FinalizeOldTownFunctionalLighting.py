"""Validate the complete original-town lamp evidence, then publish this stage only.

This script does not launch Unreal, save assets, alter a map, or rewrite an older
accepted bundle. FinalReview and CurrentLighting are written only after every
check succeeds, with CurrentLighting published last.
"""
import hashlib
import json
import math
import os
import re
import struct
from datetime import datetime, timezone
from pathlib import Path


R = Path(__file__).resolve().parents[1]
W = R / 'Saved/CodexOutputs/OldTownFunctionalLighting_20261017'
OLD = R / 'Saved/CodexOutputs/OldTownCallableLighting_20261016'
MAP = R / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
TARGET = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
WORLD = TARGET + '.L_OldTownSchoolStreet:PersistentLevel.'
SOURCE_SHA = 'd907f4dfff07ec83011337b34107427b61d39efd1479134035ed749d73a8a8c7'
ASSETS = R / 'Content/CodexGenerated/OldTown/FunctionalLighting_20261017'
PLUGIN = R / 'Plugins/CodexOldTownLights'
BUILD = R / 'Saved/CodexBuilds/CodexOldTownLights_20261017_Run2'
RUNTIME_MODULE = PLUGIN / 'Source/CodexOldTownLights/Private/CodexOldTownLightsModule.cpp'
LABELS = ('FUNC_Hotel_On', 'FUNC_Hotel_Off', 'FUNC_Street_On', 'FUNC_Street_Off')
STEP_NAMES = ('off', 'half', 'on', 'repeated_on', 'toggle_off', 'toggle_on',
              'interface_off', 'interface_on', 'restored_initial')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def native_text(path):
    raw = Path(path).read_bytes()
    return raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def polygon_count(text):
    return len(re.findall(r'^\s*Begin Polygon(?:\s|$)', text, flags=re.MULTILINE))


def check_export_mark_probe():
    first = read(W / 'ExportMarkProbe1.Completion.json')
    require(first['normal_zero_exit'] is False and first['exit_code'] != 0,
            'The first export-mark inspection failure must remain recorded as a failure')
    check_completion('ExportMarkProbe2')
    proof = read(W / 'ExportMarkProbe.json')
    require(proof['passed'] is True and proof['no_map_save'] is True
            and proof['map_sha256'] == SOURCE_SHA
            and proof['missing_brush_reproduced_on_repeat'] is True
            and proof['full_brush_restored_after_native_mark_reset'] is True
            and proof['direct_model_and_all_six_polygons_unchanged_after_light_creation'] is True,
            'The complete unsaved exporter mark probe did not pass')
    names = ('Initial', 'RepeatedWithoutReset', 'ModelBefore', 'ModelAfterLightCreation',
             'AfterReset', 'AfterSecondReset')
    texts = {name: native_text(W / 'ExportMarkProbe' / (name + '.t3d')) for name in names}
    require(texts['Initial'] == texts['AfterReset'] == texts['AfterSecondReset']
            and texts['RepeatedWithoutReset'] != texts['Initial'],
            'Reset did not restore the complete exact Actor export text')
    require(all(polygon_count(texts[n]) == 6 for n in ('Initial', 'AfterReset', 'AfterSecondReset'))
            and polygon_count(texts['RepeatedWithoutReset']) == 0,
            'The Actor export probe does not reproduce zero polygons and restore all six')
    require('/Script/Engine.PostProcessVolume' in texts['Initial']
            and texts['ModelBefore'] == texts['ModelAfterLightCreation']
            and polygon_count(texts['ModelBefore']) == polygon_count(texts['ModelAfterLightCreation']) == 6,
            'The independent model export changed or is missing brush geometry')
    require(text_sha(texts['Initial']) == proof['actor_text_sha256']
            == 'd4fb41e6088b36aef517772d4a47f43725b77e1e5018449e3ac730f383f4f153'
            and text_sha(texts['ModelBefore']) == proof['model_text_sha256']
            == '62b3f63d1db76504f0857f4af8672507a1e09959346b6115ac4bd9d220abafd6',
            'Actual complete Actor/Model text does not match the diagnosed export probe')
    return dict(passed=True, complete_actor_polygon_count=6, independent_model_polygon_count=6,
        repeated_without_reset_polygon_count=0, full_actor_restored_exactly_twice=True,
        independent_model_unchanged_after_light_creation=True,
        actor_text_sha256=proof['actor_text_sha256'], model_text_sha256=proof['model_text_sha256'],
        omission_or_filtering_allowed=False)


def check_hashes(hashes, description):
    require(bool(hashes), description + ': empty hash set')
    for path, expected in hashes.items():
        require(Path(path).is_file() and digest(path) == expected,
                description + ': changed or missing ' + path)


def check_completion(name, runtime=False):
    c = read(W / (name + '.Completion.json'))
    require(c['normal_zero_exit'] is True and c['exit_code'] == 0,
            name + ': helper did not exit normally with zero')
    if runtime:
        require(c['passed'] is True and c['forced'] is False and c['map_unchanged'] is True,
                name + ': runtime completion failed')
    return c


def check_observation(state, level, actor=None, source=None, base=None):
    require(state['has_begun_play'] is True and state['initialized'] is True
            and state['game_world'] is True, 'Observation is not an initialized GameWorld circuit')
    require(state['configuration_error'] == '' and state['mid']
            and state['mid_transient'] is True, 'Invalid circuit or persistent/missing MID')
    if actor is not None:
        require(state['actor'] == actor, 'Observed a different controller')
    require(state['on'] is (level > 0) and state['level'] == level
            and state['light_strength'] == level * 20, 'Logical/emissive state mismatch')
    require(state['interact_text'] == ('关灯' if level > 0 else '开灯'), 'Incorrect interaction text')
    require(len(state['lights']) == 1, 'Circuit does not have exactly one real local source')
    light = state['lights'][0]
    require(light['class'] in ('/Script/Engine.RectLight', '/Script/Engine.SpotLight'),
            'Circuit controls an unexpected light class')
    if source is not None:
        require(light['actor'] == source, 'Circuit controls a different source Actor')
    actual_base = light['base_intensity']
    require(math.isfinite(actual_base) and actual_base > 0, 'Invalid base photometry')
    if base is not None:
        require(actual_base == base, 'Base intensity changed')
    require(math.isclose(light['intensity'], actual_base * level, rel_tol=1e-5, abs_tol=1e-4)
            and light['visible'] is (level > 0)
            and light['hidden_in_game'] is (level <= 0)
            and light['actor_hidden'] is False, 'Physical source state mismatch')


def check_old_bundle():
    pointer = read(OLD / 'CurrentLighting.json')
    require(pointer['passed'] is True
            and same_path(pointer['final_review_file'], OLD / 'FinalReview.json')
            and pointer['final_review_sha256'] == digest(OLD / 'FinalReview.json'),
            'Previous accepted lighting pointer changed')
    old = read(OLD / 'FinalReview.json')
    require(old['passed'] is True and old['published'] is True
            and old['map_sha256'] == SOURCE_SHA, 'Unexpected previous accepted stage')
    check_hashes({str(OLD / name): value for name, value in old['report_sha256'].items()},
                 'Previous accepted reports')
    check_hashes(old['new_asset_sha256'], 'Previous 19 lighting assets')
    return old, read(OLD / 'Applied.json')


def check_existing_actors(applied):
    before = read(W / 'BeforeSnapshot.json')
    expected = read(W / 'ExpectedExistingSnapshot.json')
    actual = read(W / 'ReadbackSnapshot.json')
    require(before['actor_count'] == expected['actor_count'] == actual['actor_count'] == 7952,
            'Existing Actor count changed')
    for section in ('actors', 'exact_scene_components', 'lights', 'full_light_properties', 'actor_properties'):
        require(expected[section] == actual[section], 'Readback differs from expected ' + section)
    require(before['lights'] == actual['lights']
            and before['full_light_properties'] == actual['full_light_properties']
            and before['actor_properties'] == actual['actor_properties'],
            'Existing light or Actor properties changed')
    pairs = {p['lamp_actor']: p for p in applied['pairs']}
    allowed = {f'OTS_HotelV4_F{floor}_GalleryTube{slot:02d}'
               for floor in range(4) for slot in (0, 2, 3, 5)} | {'OTS_P2Prop_StreetLamp_03'}
    require(len(pairs) == 17 and set(pairs) == allowed,
            'New fixture recipes do not match the 17 authorized decorative lamps')
    for label, pair in pairs.items():
        hotel = label != 'OTS_P2Prop_StreetLamp_03'
        original = ('/Game/CodexGenerated/OldTown/Realism_20261012/Materials/M_R_'
                    + ('Ceramic' if hotel else 'Glass') + '_UV')
        material = '/Game/CodexGenerated/OldTown/FunctionalLighting_20261017/Materials/Instances/MI_' + label
        require(pair['kind'] == ('HotelTube' if hotel else 'StreetLens')
                and pair['component'] == 'StaticMeshComponent0'
                and pair['original_material'] == original + '.' + original.rsplit('/', 1)[1]
                and pair['material'] == material + '.' + material.rsplit('/', 1)[1]
                and pair['controller_label'] == 'OTS_LightCircuit_' + label.removeprefix('OTS_'),
                'Fixture recipe changes assets or scope: ' + label)
    bn, an = before['full_existing_actor_native'], actual['full_existing_actor_native']
    require(set(bn) == set(an) == set(before['actors']) == set(actual['actors']),
            'Existing Actor identities changed')
    changed = []
    for label, record in bn.items():
        text = native_text(record['file'])
        require(text_sha(text) == record['native_text_sha256'], 'Input Native export changed: ' + label)
        wanted = text
        if label in pairs:
            pair = pairs[label]
            old_ref = "/Script/Engine.Material'" + pair['original_material'] + "'"
            new_ref = "/Script/Engine.MaterialInstanceConstant'" + pair['material'] + "'"
            require(text.count(old_ref) == 1, 'Expected one exact old material reference: ' + label)
            wanted = text.replace(old_ref, new_ref)
        reread = native_text(an[label]['file'])
        require(text_sha(reread) == an[label]['native_text_sha256'], 'Readback Native export changed: ' + label)
        require(reread == wanted, 'Unapproved existing Actor Native delta: ' + label)
        require(expected['full_existing_actor_native'][label]['native_text_sha256'] == text_sha(wanted),
                'Expected Native hash is not the allowed replacement: ' + label)
        if text != reread:
            changed.append(label)
    require(set(changed) == set(pairs), 'Native changes do not match precisely 17 lamp fixtures')
    require('PostProcessVolume' in bn
            and polygon_count(native_text(bn['PostProcessVolume']['file'])) == 6
            and polygon_count(native_text(an['PostProcessVolume']['file'])) == 6,
            'Complete PostProcessVolume brush geometry is missing from input/readback Native exports')
    old_controller_names = [n for n, a in before['actors'].items()
                            if a['class'].endswith('/BP_OTS_LightCircuit.BP_OTS_LightCircuit_C')]
    require(len(old_controller_names) == 16, 'Previous 16 controller identities missing')
    require(all(bn[n]['native_text_sha256'] == an[n]['native_text_sha256'] for n in old_controller_names),
            'Previous controller Native state changed')
    static = [c for c in actual['exact_scene_components'].values()
              if c['class_path'] == '/Script/Engine.StaticMeshComponent']
    require(len(static) == 12362 and sum(bool(c.get('mesh')) for c in static) == 12361,
            'Existing static geometry inventory changed')
    return before, actual, dict(passed=True, existing_actors=7952,
        existing_controllers_byte_equivalent_native=16, changed_fixture_material_references=17,
        exact_static_mesh_components=12362, nonempty_mesh_components=12361,
        method='Every actual before/readback Native Actor text checked; only exact slot material object references replaced.',
        fresh_native_geometry_export_or_overlap_scan_performed=False)


def expected_bindings(applied, old_applied, before):
    expected = {}
    for p in old_applied['pairs']:
        source = WORLD + before['actors'][p['light_actor']]['name']
        expected[p['controller_path']] = dict(lamp=p['lamp_actor'], source=source,
            base=p['base_intensity'], on=p['initially_on'], material=p['material'], added=False)
    for p in applied['pairs']:
        require(p['initially_on'] is False and p['new_light_properties']['visible'] is False
                and p['new_light_properties']['hidden_in_game'] is False,
                'New light is not saved initially off: ' + p['lamp_actor'])
        require(p['base_intensity'] == (75.0 if p['kind'] == 'HotelTube' else 130.0)
                and p['new_light_properties']['intensity'] == p['base_intensity'],
                'New light lost template photometry')
        require(p['controller_path'] not in expected, 'New controller reuses an old identity')
        expected[p['controller_path']] = dict(lamp=p['lamp_actor'], source=p['light_actor_path'],
            base=p['base_intensity'], on=False, material=p['material'], added=True)
    require(len(expected) == 33
            and len({v['source'] for v in expected.values()}) == 33
            and len({v['lamp'] for v in expected.values()}) == 33,
            'Expected controllers, sources or lamps are not unique')
    old_paths = {WORLD + a['name'] for a in before['actors'].values()}
    added_paths = [p['controller_path'] for p in applied['pairs']] + [p['light_actor_path'] for p in applied['pairs']]
    require(len(set(added_paths)) == 34 and not old_paths.intersection(added_paths),
            'New Actor identities overlap each other or existing Actors')
    return expected


def check_runtime(applied, expected):
    runtime = read(W / 'RuntimeValidation.json')
    failed = read(W / 'RuntimeGame1.Completion.json')
    failed_owned = read(W / 'RuntimeGame1.OwnedProcess.json')
    require(failed['passed'] is False and failed['normal_zero_exit'] is False
            and failed['exit_code'] != 0 and failed['forced'] is False
            and failed['runtime_report_written'] is False and failed['map_unchanged'] is True
            and failed['owned_pid'] == failed_owned['owned_pid'] > 0
            and failed['map_sha256'] == failed_owned['map_sha256'] == applied['map_sha256']
            and failed_owned['map_save_requested'] is False,
            'The first refused runtime validation must remain a failed, unsaved owned run')
    completion = check_completion('RuntimeGame2', runtime=True)
    owned = read(W / 'RuntimeGame2.OwnedProcess.json')
    require(runtime['passed'] is True and runtime['world'] == TARGET
            and runtime['world_begun_play'] is True and runtime['game_world'] is True
            and runtime['no_asset_save_called'] is True, 'Runtime is not the required actual GameWorld')
    require(runtime['customized_validation'] is True
            and runtime['source_evidence_unchanged'] is True
            and runtime['source_evidence_world_matches'] is True
            and same_path(runtime['validation_directory'], W)
            and same_path(runtime['source_evidence_file'], W / 'Applied.json')
            and runtime['source_evidence_sha1'] == digest(W / 'Applied.json', 'sha1')
            and runtime['source_evidence'] == applied, 'Runtime source evidence binding failed')
    require(runtime['owned_process_id'] == completion['owned_pid'] == owned['owned_pid'] > 0,
            'Runtime PID does not match owned helper')
    require(completion['map_sha256'] == owned['map_sha256'] == applied['map_sha256']
            and owned['map_save_requested'] is False and owned['window_style'] == 'Hidden',
            'Owned runtime helper map/saving evidence mismatch')
    require(tuple(runtime[k] for k in ('expected_circuit_count', 'expected_initial_on_count', 'expected_initial_off_count',
            'circuit_count', 'initial_on_count', 'initial_off_count', 'unique_mid_count',
            'unique_local_light_count', 'unique_lamp_count')) == (33, 13, 20, 33, 13, 20, 33, 33, 33),
            'Incorrect runtime counts')
    records = runtime['circuits']
    require(len(records) == 33 and {c['initial']['actor'] for c in records} == set(expected),
            'Runtime controller identities differ from applied fixtures')
    mids, sources = set(), set()
    added_off = []
    for c in records:
        initial = c['initial']; actor = initial['actor']; p = expected[actor]
        require(c['passed'] is True and c['unique_mid'] is True and c['exactly_one_real_light'] is True,
                'Circuit validation did not pass: ' + actor)
        require(initial['initially_on'] is p['on'], 'Fixture initial flag changed: ' + actor)
        check_observation(initial, 1.0 if p['on'] else 0.0, actor, p['source'], p['base'])
        mids.add(initial['mid']); sources.add(initial['lights'][0]['actor'])
        steps = c['steps']
        require(tuple(s['step'] for s in steps) == STEP_NAMES, 'Missing/reordered runtime steps')
        levels = (0.0, 0.5, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0 if p['on'] else 0.0)
        for s, level in zip(steps, levels):
            require(s['passed'] is True and s['other_circuits_unchanged'] is True
                    and s['expected_level'] == level and s['mid'] == initial['mid']
                    and s['initially_on'] is p['on'], 'Runtime isolation or requested state failed')
            check_observation(s, level, actor, p['source'], p['base'])
            require(s['interface_interact_text'] == s['interact_text'], 'Blueprint interface text differs')
        if p['added']:
            require(initial['initially_on'] is False and initial['light_strength'] == 0
                    and initial['lights'][0]['intensity'] == 0
                    and initial['lights'][0]['visible'] is False, 'One of the 17 added lamps starts on')
            added_off.append(dict(controller=actor, lamp=p['lamp'], source=p['source'], initially_on=False))
    require(len(mids) == len(sources) == 33 and len(added_off) == 17,
            'Runtime MID/source uniqueness or new-off fixture coverage failed')
    cases = runtime['before_begin_play_cases']
    require(runtime['before_begin_play_calls_preserved'] is True and len(cases) == 6,
            'Early-call validation missing')
    require({(c['initially_on'], c['requested_before_begin_play']) for c in cases}
            == {(on, level) for on in (False, True) for level in (0.0, 0.5, 1.0)},
            'Early-call cases do not cover both initial states and all three levels')
    for c in cases:
        require(c['passed'] is True, 'Early-call case failed')
        check_observation(c['after_begin_play'], c['requested_before_begin_play'], base=100.0)
    return dict(passed=True, actual_game_world_steps=sum(len(c['steps']) for c in records),
                early_initialization_cases=6, unique_mids=33, unique_local_sources=33,
                unique_lamps=33, added_lamps_individually_verified_off=added_off,
                owned_pid=owned['owned_pid'], applied_exact_bytes_sha1=runtime['source_evidence_sha1'])


def check_readback(applied, expected, actual):
    audit = read(W / 'ReadbackAudit.json')
    require(audit['passed'] is True and audit['map_sha256'] == applied['map_sha256']
            and audit['existing_actor_count'] == 7952 and audit['actor_count'] == 7986
            and audit['all_33_callable_real_lights'] is True and audit['new_real_lights'] == 17
            and audit['new_controllers'] == 17 and audit['initially_on'] == 13
            and audit['initially_off'] == 20, 'Incorrect saved readback inventory')
    bindings = audit['bindings']
    require(len(bindings) == 33 and {b['diagnostics']['actor'] for b in bindings} == set(expected),
            'Saved controller identities differ')
    for b in bindings:
        diagnostic = b['diagnostics']; p = expected[diagnostic['actor']]
        require(b['lamp'] == p['lamp'] and b['material'] == p['material']
                and b['initially_on'] is p['on'] and not diagnostic['configuration_error']
                and diagnostic['initialized'] is False and not diagnostic['mid'],
                'Saved circuit binding or transient state mismatch')
        require(actual['exact_scene_components'][b['lamp'] + '::StaticMeshComponent0']['materials'][2] == p['material'],
                'Saved fixture material does not match circuit')
        require(len(diagnostic['lights']) == 1
                and diagnostic['lights'][0]['actor'] == p['source']
                and diagnostic['lights'][0]['base_intensity'] == p['base'],
                'Saved source reference or calibrated base differs')
    materials = read(W / 'MaterialPreservation.json')
    require(materials['passed'] is True and materials['all_33_have_LightStrength'] is True
            and len(materials['masters']) == 2
            and {m['kind'] for m in materials['masters']} == {'HotelTube', 'StreetLens'},
            'Material/parameter proof missing')
    require(all(m['passed'] is True and m['non_emission_properties_and_original_nodes_unchanged'] is True
                for m in materials['masters']), 'Non-emission/WPO material graph changed')
    street = next(m for m in materials['masters'] if m['kind'] == 'StreetLens')
    require(street['source'].endswith('/M_R_Glass_UV.M_R_Glass_UV')
            and street['destination'].endswith('/M_OTS_Street03_GlassCallable.M_OTS_Street03_GlassCallable'),
            'Street03 did not preserve a private copy of the original translucent Glass')
    require(audit['protected_verification']['passed'] is True
            and not audit['protected_verification']['changed_protected_files'], 'Readback reported protected file changes')


def check_plugin(old):
    change = read(W / 'PluginValidationChange.json'); backup = read(W / 'PluginBackup.json')
    require(change['passed'] is True and change['only_opt_in_debug_validation_changed'] is True
            and change['default_runtime_lighting_behavior_changed'] is False
            and change['changed_existing_source_files'] == [str(RUNTIME_MODULE)]
            and change['source_file'] == str(RUNTIME_MODULE)
            and digest(RUNTIME_MODULE) == change['source_sha256_after']
            == 'e8476d238572ab523a4652efda8c03d9703c2ac3f4ef78d601ee31ac91b5c71f',
            'Unexpected plugin source change')
    require(change['static_checks']['absolute_project_root_before_both_path_joins'] is True
            and change['static_checks']['collapse_failures_have_explicit_error_text'] is True
            and change['repair_history']
            and change['repair_history'][-1]['source_sha256_after_fix'] == change['source_sha256_after']
            and change['repair_history'][-1]['validation_only'] is True
            and change['repair_history'][-1]['no_runtime_actor_or_editor_library_change'] is True,
            'Debug validation path repair is not recorded with protected runtime behavior')
    require(backup['passed'] is True, 'Plugin backup failed')
    saved = {b['original_path']: b for b in backup['files']}
    require(set(saved) == set(old['plugin_file_sha256']), 'Plugin backup is not the accepted previous plugin')
    changed_sources = []
    for original, row in saved.items():
        require(digest(row['file']) == row['sha256'] == old['plugin_file_sha256'][original],
                'Plugin backup byte mismatch: ' + original)
        relative = Path(original).relative_to(PLUGIN)
        current = digest(original)
        if relative.parts[0] == 'Source' and current != row['sha256']:
            changed_sources.append(original)
        elif relative.parts[0] not in ('Source', 'Binaries'):
            require(current == row['sha256'], 'Plugin metadata/config changed')
    require(changed_sources == [str(RUNTIME_MODULE)]
            and saved[str(RUNTIME_MODULE)]['sha256'] == change['source_sha256_before'],
            'Runtime Actor or Editor behavior source changed')
    require(len(change['protected_runtime_actor_editor_library']) == 4, 'Missing protected plugin source checks')
    for row in change['protected_runtime_actor_editor_library']:
        require(row['unchanged'] is True and digest(row['file']) == row['sha256_before'] == row['sha256_after'],
                'Runtime Actor/Editor source no longer frozen')
    check_completion('PluginBuild2')
    require('BUILD SUCCESSFUL' in (W / 'PluginBuild2.log').read_text(encoding='utf-8', errors='replace'),
            'Plugin build did not succeed')
    for area in ('Source', 'Binaries/Win64'):
        live = {p.relative_to(PLUGIN): p for p in (PLUGIN / area).rglob('*') if p.is_file()}
        built = {p.relative_to(BUILD): p for p in (BUILD / area).rglob('*') if p.is_file()}
        require(live and set(live) == set(built), 'Plugin build file set differs: ' + area)
        require(all(digest(p) == digest(built[relative]) for relative, p in live.items()),
                'Loaded plugin files do not match successful build: ' + area)
    return {str(p): digest(p) for p in PLUGIN.rglob('*') if p.is_file() and 'Intermediate' not in p.parts}


def check_visuals(applied, expected):
    visual = read(W / 'DirectVisualReview.json')
    require(visual['passed'] is True and visual['root_directly_viewed_all_four_frames'] is True
            and set(visual['image_sha256']) == set(LABELS), 'Root direct review of all four new frames is required')
    runs = read(W / 'Preview/CaptureRuns.json')
    rows = {r['camera']: r for r in runs}
    require(set(rows) == set(LABELS), 'New on/off capture set is incomplete')
    captures = []
    for label in LABELS:
        row = rows[label]
        require(row['captured'] is True and row['normal_exit'] is True
                and row['forced_cleanup'] is False and row['exit_code'] == 0
                and row['map_sha256'] == applied['map_sha256'], 'Capture helper failed: ' + label)
        png = W / 'Preview/Renders' / (label + '.png'); meta = read(png.with_suffix('.json'))
        require(meta['status'] == 'PASS' and meta['camera'] == label and meta['target_level'] == TARGET
                and meta['png_sha256'] == digest(png) == visual['image_sha256'][label]
                and meta['bytes'] == png.stat().st_size and png.stat().st_size > 20000,
                'Image identity/hash mismatch: ' + label)
        require(png.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
                and struct.unpack('>II', png.read_bytes()[16:24]) == (1920, 1080), 'Unexpected PNG format/dimensions')
        require(meta['map_sha256'] == meta['map_sha256_after_cleanup'] == applied['map_sha256']
                and meta['persisted_map_unchanged'] is True and meta['appearance_assets_unchanged'] is True
                and meta['map_save_requested'] is False and meta['fresh_map_load_verified'] is True
                and meta['source'] == 'fresh_persisted_map_load', 'Capture was not a fresh unchanged saved map')
        require(meta['source_build_report']['sha256'] == digest(W / 'Applied.json')
                and same_path(meta['source_build_report']['file'], W / 'Applied.json')
                and meta['new_asset_sha256'] == meta['asset_sha256_after_cleanup'] == applied['new_asset_sha256'],
                'Capture source/assets mismatch')
        require(meta['temporary_camera_cleanup_verified_zero'] is True
                and meta['temporary_lighting_cleanup_verified_zero'] is True
                and meta['temporary_lighting_cleanup_remaining_count'] == 0
                and meta['temporary_lighting_created_count'] == 0
                and meta['lighting_mode'] == 'street_only' and meta['view_mode_verified'] == 'lit',
                'Capture cleanup or lighting mode is invalid')
        require(meta['run_id'] == row['run_id'] and meta['owned_editor_pid'] == row['owned_editor_pid'],
                'Capture metadata PID/run mismatch')
        run_dir = W / 'Preview/Runs' / row['run_id']
        require(run_dir.resolve().is_relative_to((W / 'Preview/Runs').resolve()), 'Capture run path escaped its stage')
        owned = read(run_dir / 'OwnedProcess.json'); proof = read(run_dir / 'LightingCaptureProof.json')
        require(owned['owned_editor_pid'] == row['owned_editor_pid'] and owned['run_id'] == row['run_id']
                and owned['normal_exit'] is True and owned['exit_code'] == 0
                and owned['helper_has_exited'] is True and owned['forced_cleanup'] is False
                and owned['persisted_map_unchanged'] is True and owned['map_save_requested'] is False,
                'Capture process lifecycle/ownership failed')
        require(proof['passed'] is True and proof['editor_preview_restored'] is True
                and proof['temporary_camera_remaining'] == [] and proof['map_save_requested'] is False
                and proof['circuit_state_at_capture'][label] == meta['circuit_state_at_capture'],
                'Capture preview restoration or temporary camera proof failed')
        state = meta['circuit_state_at_capture']; p = expected[state['actor']]
        wanted_lamp = ('OTS_HotelV4_F1_GalleryTube00' if 'Hotel' in label else 'OTS_P2Prop_StreetLamp_03')
        level = 1.0 if label.endswith('_On') else 0.0
        require(p['added'] and p['lamp'] == wanted_lamp and not state['configuration_error']
                and state['level'] == level and state['light_strength'] == 20 * level,
                'Preview does not show the correct added fixture/state')
        require(len(state['lights']) == 1 and state['lights'][0]['actor'] == p['source']
                and state['lights'][0]['base_intensity'] == p['base']
                and state['lights'][0]['visible'] is (level > 0)
                and state['lights'][0]['intensity'] == p['base'] * level,
                'Preview source state mismatch')
        captures.append(dict(camera=label, png=str(png), sha256=digest(png), run_id=row['run_id']))
    return captures


def atomic_write(path, value):
    path = Path(path)
    require(path.parent == W and not path.exists(), 'Only new stage publication files may be created')
    temporary = path.with_name(path.name + '.publishing')
    require(not temporary.exists(), 'Stale publication temporary file requires review')
    with temporary.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main():
    require(not (W / 'FinalReview.json').exists() and not (W / 'CurrentLighting.json').exists(),
            'Accepted functional lighting bundle is immutable')
    applied = read(W / 'Applied.json')
    require(applied['passed'] is True and applied['target_level'] == TARGET
            and applied['source_map_sha256'] == SOURCE_SHA and digest(MAP) == applied['map_sha256']
            and applied['actor_count_before'] == 7952 and applied['actor_count_after'] == 7986
            and applied['new_real_lights'] == applied['new_controllers'] == 17
            and applied['expected_circuit_count'] == 33 and applied['expected_initially_on'] == 13
            and applied['expected_initially_off'] == 20, 'Unexpected applied functional lighting stage')
    failed_apply = read(W / 'Apply1.Completion.json')
    require(failed_apply['passed'] is False and failed_apply['normal_zero_exit'] is False
            and failed_apply['native_fatal'] is True and failed_apply['map_saved'] is False
            and failed_apply['map_sha256'] == SOURCE_SHA,
            'The failed first creation attempt is not recorded as an unsaved source-map-preserving failure')
    check_completion('CreationProbe1')
    creation_probe = read(W / 'CreationProbe.json')
    require(creation_probe['passed'] is True and creation_probe['no_map_save'] is True
            and creation_probe['map_sha256'] == SOURCE_SHA
            and len(creation_probe['rows']) == 2
            and {p['kind'] for p in creation_probe['rows']} == {'HotelTube', 'StreetLens'}
            and all(p['creation_method'] == 'spawn_actor_and_copy_all_editor_properties'
                    and not p['read_only_property_copy_errors'] for p in creation_probe['rows']),
            'The unsaved Rect/Spot creation probe did not pass')
    rejected_apply = read(W / 'Apply2.Completion.json')
    require(rejected_apply['passed'] is False and rejected_apply['normal_zero_exit'] is False
            and rejected_apply['exit_code'] != 0 and rejected_apply['map_saved'] is False
            and rejected_apply['map_sha256'] == SOURCE_SHA,
            'The second strict-preservation rejection is not recorded as unsaved with the source map unchanged')
    export_mark_proof = check_export_mark_probe()
    check_completion('Apply3'); check_completion('Readback1')
    require(read(W / 'IndependentPlan.json')['passed'] is True,
            'Independent functional lamp plan did not pass')
    old, old_applied = check_old_bundle()
    before, actual, invariance = check_existing_actors(applied)
    expected = expected_bindings(applied, old_applied, before)
    check_readback(applied, expected, actual)
    runtime_proof = check_runtime(applied, expected)
    require(runtime_proof['actual_game_world_steps'] == 297, 'Runtime step coverage is incomplete')
    captures = check_visuals(applied, expected)
    plugin_hashes = check_plugin(old)
    protected = read(W / 'ProtectedBefore.json')['file_sha256']
    require(protected[str(MAP)] == SOURCE_SHA, 'Protected source map baseline differs')
    for required in (R / 'Content/Yastar/Maps/L_Main.umap',
                     R / 'Content/Yastar/Blueprints/BP_LightSwitch.uasset',
                     R / 'Content/CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap'):
        require(str(required) in protected, 'Required user asset is missing from protection')
    check_hashes({p: h for p, h in protected.items() if p != str(MAP)}, 'All previous Content/Config files')
    new = applied['new_asset_sha256']
    require(len(new) == 18 and all(Path(p).resolve().is_relative_to(ASSETS.resolve()) for p in new),
            'Unexpected new asset scope')
    require(sum('/Instances/' in p.replace('\\', '/') for p in new) == 17
            and all(Path(p).suffix == '.uasset' for p in new), 'Expected 17 material instances and one master')
    check_hashes(new, 'New private material assets')
    actual_files = {str(p) for base in (R / 'Content', R / 'Config') for p in base.rglob('*') if p.is_file()}
    require(actual_files == set(protected) | set(new), 'Unexpected added/deleted Content or Config files')
    require(all(protected.get(p) == h for p, h in old['new_asset_sha256'].items()),
            'Previous 16-circuit materials/BP are not frozen in the new baseline')
    backup = read(W / 'Backup.json')
    require(backup['passed'] is True and backup['created_before_map_write'] is True
            and digest(backup['file']) == backup['sha256'] == backup['source_sha256'] == SOURCE_SHA,
            'Original map backup is invalid')
    v2pointer = R / 'Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json'
    require(read(v2pointer)['source_bundle_name'] == 'OldTownVersion2_20261016'
            and digest(R / 'Content/CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap')
            == '151e9409f265b3c0d890589a800129037bd318600741c59ee942bdcd2bffb80d',
            'V2 map or evidence target changed')
    report_names = ('Applied.json', 'Backup.json', 'BeforeSnapshot.json', 'ExpectedExistingSnapshot.json',
                    'ReadbackSnapshot.json', 'ReadbackAudit.json', 'MaterialPreservation.json',
                    'RuntimeValidation.json', 'RuntimeGame1.Completion.json', 'RuntimeGame1.OwnedProcess.json',
                    'RuntimeGame2.Completion.json', 'RuntimeGame2.OwnedProcess.json',
                    'Apply1.Completion.json', 'CreationProbe1.Completion.json', 'CreationProbe.json',
                    'Apply2.Completion.json', 'ExportMarkProbe1.Completion.json', 'ExportMarkProbe2.Completion.json',
                    'ExportMarkProbe.json', 'ExportMarkProbe/Initial.t3d', 'ExportMarkProbe/RepeatedWithoutReset.t3d',
                    'ExportMarkProbe/ModelBefore.t3d', 'ExportMarkProbe/ModelAfterLightCreation.t3d',
                    'ExportMarkProbe/AfterReset.t3d', 'ExportMarkProbe/AfterSecondReset.t3d',
                    'Apply3.Completion.json', 'Readback1.Completion.json', 'DirectVisualReview.json',
                    'FixturePlan.json', 'ProtectedBefore.json', 'IndependentPlan.json',
                    'PluginValidationChange.json', 'PluginBackup.json', 'PluginBuild2.Completion.json',
                    'PluginBuild2.log', 'Preview/CaptureRuns.json')
    reports = {name: digest(W / name) for name in report_names}
    require(digest(MAP) == applied['map_sha256'], 'Map changed during final verification')
    final = dict(passed=True, published=True, target_level=TARGET, map_sha256=applied['map_sha256'],
        source_map_sha256=SOURCE_SHA, existing_actor_count=7952, new_real_lights=17,
        new_light_circuit_actors=17, actor_count=7986, material_overrides=17, new_assets=18,
        real_local_lights=33, light_circuits=33, default_on=13, default_off=20,
        actual_game_world_steps=297, early_initialization_cases=6, runtime_identity_proof=runtime_proof,
        existing_actor_and_geometry_invariance=invariance,
        complete_native_export_mark_proof=export_mark_proof,
        all_33_lamps_have_LightStrength_and_one_callable_real_light=True,
        original_16_circuits_and_their_defaults_preserved=True,
        previous_accepted_reports_and_assets_unchanged=True,
        user_assets_shared_assets_and_v2_byte_unchanged=True,
        protected_existing_file_count=len(protected) - 1, v2_evidence_pointer_not_replaced=True,
        street03_original_translucent_non_emission_and_WPO_preserved=True,
        backup=backup, captures=captures, report_sha256=reports,
        new_asset_sha256=new, plugin_file_sha256=plugin_hashes,
        plugin_change_scope='Only opt-in runtime validation module source extended; Actor and Editor library source unchanged.',
        previous_accepted_lighting_review_sha256=digest(OLD / 'FinalReview.json'),
        historical_pre_save_retry=dict(first_attempt_native_fatal=True, first_attempt_map_saved=False,
            second_attempt_strict_native_rejection=True, second_attempt_map_saved=False,
            source_map_sha256=SOURCE_SHA,
            quarantined_directories=[str(W / 'FailedApply1'), str(W / 'FailedApply2')],
            successful_creation_probe='CreationProbe1', successful_export_mark_probe='ExportMarkProbe2',
            successful_apply='Apply3',
            reason='First, native duplication failed before saving; new Actors now copy template properties. Second, strict preservation rejected stale exporter marks omitting brush geometry; native marks are reset and all six brush polygons remain in exact full Actor comparisons.'),
        historical_runtime_validation_retry=dict(first_run='RuntimeGame1', first_run_passed=False,
            first_run_report_written=False, first_run_map_unchanged=True,
            reason='The opt-in validator rejected its relative project output path before validation; only debug path resolution and explicit diagnostics were repaired.',
            successful_plugin_build='PluginBuild2', successful_runtime_run='RuntimeGame2'),
        limitations=['Controller public functions and BPI_Interact remain the callable path; no physical switch mesh or character trace hotspot was added.',
                    'Real UnrealEditor -game BeginPlay and Blueprint interface calls verified; packaged shipping build was not tested.',
                    'New lights remain initially off. No pending performance settings, streaming policy or original source photometry were changed.'],
        completed_utc=datetime.now(timezone.utc).isoformat())
    atomic_write(W / 'FinalReview.json', final)
    atomic_write(W / 'CurrentLighting.json', dict(passed=True, final_review_file=str(W / 'FinalReview.json'),
        final_review_sha256=digest(W / 'FinalReview.json'), target_level=TARGET,
        map_sha256=applied['map_sha256']))
    print('ORIGINAL_TOWN_FUNCTIONAL_LIGHTING_FINAL_PASS', applied['map_sha256'])


if __name__ == '__main__':
    main()
