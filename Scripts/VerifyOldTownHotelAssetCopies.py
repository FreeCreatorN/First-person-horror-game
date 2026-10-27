"""Read-only fresh-process proof for every explicitly copied Hotel asset.

Run only through root's owned UE helper. This script never saves, compiles,
renames, or edits a Content object. Differences are reported, never repaired.
"""
import hashlib
import json
import re
import sys
import traceback
from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import unreal

R = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(R / 'Scripts'))
import InspectOldTownRealismInput as native
from OldTownHotelNamingVerification import normalize_asset_paths, normalize_native_text, read_native_text

W = R / 'Saved/CodexOutputs/OldTownHotelNaming_20261017'
V = W / 'AssetCopyValidation3'
REPORT = W / 'AssetCopyVerification3.json'
EXPECTED_COUNTS = {'Blueprint': 19, 'MaterialInstanceConstant': 334,
                   'Material': 63, 'StaticMesh': 174, 'Texture2D': 27}
INPUT_HASHES = {}
IMPORT_TAG_ENGINE_SOURCE = Path('D:/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/Obj.cpp')
IMPORT_TAG_ENGINE_SOURCE_SHA256 = '98e01929644be422f8b8cd7730627458228f5a83c10aa270bc1595605279469d'


def read(path):
    path = Path(path).resolve()
    INPUT_HASHES[str(path)] = native.sha(path)
    return json.loads(path.read_text(encoding='utf-8-sig'))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def file_hashes():
    return {str(p): native.sha(p) for root in (R / 'Content', R / 'Config')
            for p in root.rglob('*') if p.is_file()}


def write(path, value):
    path = Path(path)
    assert path.is_relative_to(W) and not path.exists(), 'Evidence may not be overwritten: ' + str(path)
    native.write(path, value)


def differences(expected, actual, path='$', limit=30):
    out = []
    if type(expected) is not type(actual):
        return [dict(path=path, kind='type', expected=type(expected).__name__, actual=type(actual).__name__)]
    if isinstance(expected, dict):
        if set(expected) != set(actual):
            out.append(dict(path=path, kind='keys', missing=sorted(set(expected) - set(actual)),
                unexpected=sorted(set(actual) - set(expected))))
        for key in sorted(set(expected) & set(actual)):
            out.extend(differences(expected[key], actual[key], path + '[' + repr(key) + ']', limit - len(out)))
            if len(out) >= limit:
                break
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            out.append(dict(path=path, kind='length', expected=len(expected), actual=len(actual)))
        for i, (a, b) in enumerate(zip(expected, actual)):
            out.extend(differences(a, b, path + '[' + str(i) + ']', limit - len(out)))
            if len(out) >= limit:
                break
    elif expected != actual:
        out.append(dict(path=path, kind='value', expected=expected, actual=actual))
    return out[:max(0, limit)]


def first_text_difference(expected, actual):
    if expected == actual:
        return None
    a, b = expected.splitlines(keepends=True), actual.splitlines(keepends=True)
    for i in range(max(len(a), len(b))):
        left, right = a[i] if i < len(a) else None, b[i] if i < len(b) else None
        if left != right:
            return dict(line=i + 1, expected=left, actual=right)
    return dict(kind='encoding_or_line_endings', expected_chars=len(expected), actual_chars=len(actual))


def extra_identity_rules(mapping):
    # Loaded Material/MI assets retain the real serialized OLD inner
    # EditorOnlyData name. Never rename it to the constructor's empty new shell.
    # Only exact generated-class/function identities are mapped here.
    rules = {}
    for src, dst in mapping.items():
        a, b = src.rsplit('/', 1)[1], dst.rsplit('/', 1)[1]
        for left, right in (('SKEL_' + a + '_C', 'SKEL_' + b + '_C'),
                ('Default__SKEL_' + a + '_C', 'Default__SKEL_' + b + '_C')):
            rules[src + '.' + left] = dst + '.' + right
        for owner_a, owner_b in ((a, b), (a + '_C', b + '_C'), ('SKEL_' + a + '_C', 'SKEL_' + b + '_C')):
            for delimiter in (':', '.'):
                rules[src + '.' + owner_a + delimiter + 'ExecuteUbergraph_' + a] = dst + '.' + owner_b + delimiter + 'ExecuteUbergraph_' + b
    pattern = re.compile(r'(?<![\w/\\:])(?:' + '|'.join(re.escape(p) for p in sorted(rules, key=len, reverse=True))
                         + r')(?=[.:\s"\'<>(),;{}\[\]=]|$)')
    return rules, pattern


def normalize_extra(value, rules, pattern):
    if isinstance(value, str):
        return pattern.sub(lambda match: rules[match.group(0)], value)
    if isinstance(value, list):
        return [normalize_extra(v, rules, pattern) for v in value]
    if isinstance(value, dict):
        out = {k: normalize_extra(v, rules, pattern) for k, v in value.items()}
        if value.get('struct') == 'TopLevelAssetPath' and isinstance(value.get('fields'), dict):
            fields = value['fields']
            package, asset = fields.get('package_name'), fields.get('asset_name')
            if isinstance(package, str) and isinstance(asset, str) and package + '.' + asset in rules:
                out['fields']['package_name'], out['fields']['asset_name'] = rules[package + '.' + asset].split('.', 1)
        return out
    return value


def expected_state(value, mapping, rules, pattern):
    return normalize_asset_paths(normalize_extra(value, rules, pattern), mapping)


def expected_native(text, row, mapping, rules, pattern):
    text = normalize_native_text(normalize_extra(text, rules, pattern), mapping)
    a, b = row['source_asset_name'], row['destination_asset_name']
    identities = {a: b, a + '_C': b + '_C', 'Default__' + a + '_C': 'Default__' + b + '_C',
        'SKEL_' + a + '_C': 'SKEL_' + b + '_C', 'Default__SKEL_' + a + '_C': 'Default__SKEL_' + b + '_C',
        'ExecuteUbergraph_' + a: 'ExecuteUbergraph_' + b}
    changed, result, object_scopes = [], [], []
    # ObjectExporter also writes class-qualified owner-relative UObject paths,
    # such as SimpleConstructionScript'BP_X_C:SimpleConstructionScript_0' or
    # Material'M_X'. Only this exact asset's self/class/CDO symbols can change.
    object_reference = re.compile(r"(?P<class>/Script/[A-Za-z0-9_./]+)'(?P<path>[^'\r\n]+)'")
    declaration = re.compile(r'^(\s*Begin Object\b[^\r\n]*?\bName=)("[^"\r\n]+"|[^\s\r\n]+)')
    for i, line in enumerate(text.splitlines(keepends=True), 1):
        def relative_reference(match):
            path = match.group('path')
            if path.startswith('/'):
                return match.group(0)
            for old, new in identities.items():
                if path == old or path.startswith(old + ':') or path.startswith(old + '.'):
                    changed.append(dict(line=i, old=path, new=new + path[len(old):],
                        scope='Class-qualified relative UObject reference to this exact asset self/generated/CDO/SKEL identity'))
                    return match.group('class') + "'" + new + path[len(old):] + "'"
            return match.group(0)
        line = object_reference.sub(relative_reference, line)
        if re.match(r'^\s*Begin Object\b', line):
            object_scopes.append('K2Node_FunctionEntry' in line and ':ExecuteUbergraph_' + b + '.' in line)
        match = declaration.search(line)
        if match:
            name = match.group(2).strip('"')
            if name in identities:
                replacement = '"' + identities[name] + '"' if match.group(2).startswith('"') else identities[name]
                line = line[:match.start(2)] + replacement + line[match.end(2):]
                changed.append(dict(line=i, old=name, new=identities[name], scope='This asset self/generated/CDO/SKEL/automatic ExecuteUbergraph Begin Object identity only'))
        if object_scopes and object_scopes[-1]:
            function_name = re.compile(r'^(\s*CustomGeneratedFunctionName=)"ExecuteUbergraph_' + re.escape(a) + r'"')
            if function_name.search(line):
                line = function_name.sub(lambda m: m.group(1) + '"ExecuteUbergraph_' + b + '"', line)
                changed.append(dict(line=i, old='ExecuteUbergraph_' + a, new='ExecuteUbergraph_' + b,
                    scope='Automatic ExecuteUbergraph K2Node_FunctionEntry CustomGeneratedFunctionName only'))
        result.append(line)
        if re.match(r'^\s*End Object\b', line) and object_scopes:
            object_scopes.pop()
    return ''.join(result), changed


def strip_unreferenced_constructor_shell(text, row):
    """Remove only a proved empty, unreferenced new-name material ctor shell.

    The real OLD EditorOnlyData object, its properties, and the owner's actual
    EditorOnlyData reference remain verbatim. Any property/nesting/reference in
    the new shell makes this rule inapplicable and the normal comparison fails.
    """
    if row['asset_class'] not in ('Material', 'MaterialInstanceConstant'):
        return text, dict(applied=False)
    cls = 'MaterialEditorOnlyData' if row['asset_class'] == 'Material' else 'MaterialInstanceEditorOnlyData'
    old = row['source_asset_name'] + 'EditorOnlyData'
    new = row['destination_asset_name'] + 'EditorOnlyData'
    actual_reference = 'EditorOnlyData="/Script/Engine.' + cls + "'" + old + "'\""
    if actual_reference not in text:
        return text, dict(applied=False, reason='Owner does not point to the real old-name serialized object')
    block = re.compile(r'(?m)^(?P<indent>[ \t]*)Begin Object(?P<header>[^\n]*)\n'
        r'(?P<body>(?:[ \t\r]*\n)*)(?P=indent)End Object[ \t\r]*(?:\n|$)')
    found = []
    qualified = row['destination_object_path'] + ':' + new
    for match in block.finditer(text):
        header = match.group('header')
        if not re.search(r'\bName="' + re.escape(new) + r'"(?:\s|$)', header):
            continue
        if ('ExportPath="/Script/Engine.' + cls + "'" + qualified + "'\"") not in header:
            continue
        class_match = re.search(r'\bClass=([^\s]+)', header)
        if class_match and class_match.group(1) != '/Script/Engine.' + cls:
            continue
        found.append(match)
    if len(found) != 2 or sum('Class=' in m.group('header') for m in found) != 1:
        return text, dict(applied=False, reason='Exact empty declaration+definition pair not proved', matched_blocks=len(found))
    normalized = text
    for match in reversed(found):
        normalized = normalized[:match.start()] + normalized[match.end():]
    if re.search(r'(?<![A-Za-z0-9_])' + re.escape(new) + r'(?![A-Za-z0-9_])', normalized):
        return text, dict(applied=False, reason='The constructor-named object is referenced outside its two empty blocks')
    return normalized, dict(applied=True, object_name=new, exact_object_path=qualified,
        class_path='/Script/Engine.' + cls, stripped_empty_blocks=2,
        owner_actual_editor_only_data=old, actual_serialized_object_preserved=True,
        empty_body=True, unreferenced_outside_blocks=True,
        removed_block_sha256=[text_sha(m.group(0)) for m in found])


def normalize_generated_graph_guids(expected, current, row):
    """Alpha-rename IDs only in proved compiler-generated Blueprint graphs.

    Node classes/order, functions, pin names/types/defaults, EntryPoint and all
    LinkedTo node targets are still compared by the resulting whole text.
    Every PinId replacement in LinkedTo must have its declaration in that same
    graph. Original user graphs and their GUIDs are never rewritten.
    """
    if row['asset_class'] != 'Blueprint':
        return expected, dict(applied=False, passed=expected == current)
    allowed = {'ExecuteUbergraph_' + row['destination_asset_name']}
    if row['source_asset_name'] == 'BP_OTS_LightCircuit':
        allowed.update(('DisableHighlight', 'EnableHighlight', 'Interact'))
    left, right = expected.splitlines(keepends=True), current.splitlines(keepends=True)
    if len(left) != len(right):
        return expected, dict(applied=False, passed=False, reason='Line count differs before generated identity matching')

    def contexts(lines):
        stack, out = [], []
        for line in lines:
            if re.match(r'^\s*Begin Object\b', line):
                name = re.search(r'\bName="([^"]+)"', line)
                graph = bool(name and name.group(1) in allowed and len(stack) == 1
                    and 'ExportPath="/Script/Engine.EdGraph\'' in line)
                stack.append(dict(name=name.group(1) if name else None, generated_graph=graph))
            graph = next((x['name'] for x in stack if x['generated_graph']), None)
            out.append((graph, stack[-1]['name'] if stack else None,
                        bool(stack and stack[-1]['generated_graph'])))
            if re.match(r'^\s*End Object\b', line) and stack:
                stack.pop()
        return out

    lc, rc = contexts(left), contexts(right)
    if lc != rc:
        return expected, dict(applied=False, passed=False, reason='Generated graph/node nesting or order differs')
    guids, reverse, pins, pairs = {}, {}, {}, []
    guid_property = re.compile(r'^(\s*)(GraphGuid|NodeGuid)=([0-9A-Fa-f]{32})(\s*)$')
    pin_property = re.compile(r'\bPinId=([0-9A-Fa-f]{32})(?=[,)])')

    def register(a, b, kind, line, graph, node, pin_name=None):
        assert a != '0' * 32 and b != '0' * 32, 'Zero GUID is not a generated identity'
        assert guids.get(a, b) == b and reverse.get(b, a) == a, 'Generated ID mapping is not bijective'
        guids[a], reverse[b] = b, a
        if kind == 'PinId':
            assert pins.get((graph, a), b) == b
            pins[graph, a] = b
        pairs.append(dict(kind=kind, line=line, graph=graph, node=node, pin_name=pin_name,
            source=a, destination=b, changed=a != b))

    for i, (a, b) in enumerate(zip(left, right)):
        graph, node, is_graph = lc[i]
        if not graph:
            continue
        ga, gb = guid_property.match(a), guid_property.match(b)
        if ga or gb:
            assert ga and gb and ga.group(2) == gb.group(2), 'GUID property kind changed'
            assert ga.group(2) != 'GraphGuid' or is_graph, 'Nested unexpected graph GUID'
            register(ga.group(3), gb.group(3), ga.group(2), i + 1, graph, node)
        elif a.lstrip().startswith('CustomProperties Pin '):
            pa, pb = pin_property.search(a), pin_property.search(b)
            assert pa and pb and b.lstrip().startswith('CustomProperties Pin '), 'Pin declaration shape changed'
            na, nb = re.search(r'\bPinName="([^"]*)"', a), re.search(r'\bPinName="([^"]*)"', b)
            assert (na.group(1) if na else None) == (nb.group(1) if nb else None), 'Pin names/order changed'
            register(pa.group(1), pb.group(1), 'PinId', i + 1, graph, node, na.group(1) if na else None)
    result, linked_rewrites, function_renames = [], [], []
    for i, line in enumerate(left):
        graph, node, _ = lc[i]
        if graph:
            auto_function = re.compile(r'^(\s*FunctionReference=\([^\r\n]*\bMemberName=)"ExecuteUbergraph_'
                + re.escape(row['source_asset_name']) + r'"')
            if auto_function.search(line):
                line = auto_function.sub(lambda m: m.group(1) + '"ExecuteUbergraph_' + row['destination_asset_name'] + '"', line)
                function_renames.append(dict(line=i + 1, graph=graph, node=node,
                    source='ExecuteUbergraph_' + row['source_asset_name'], destination='ExecuteUbergraph_' + row['destination_asset_name']))
            prop = guid_property.match(line)
            if prop:
                line = line[:prop.start(3)] + guids[prop.group(3)] + line[prop.end(3):]
            elif line.lstrip().startswith('CustomProperties Pin '):
                line = pin_property.sub(lambda m: 'PinId=' + pins[graph, m.group(1)], line, count=1)
                links = re.search(r'\bLinkedTo=\(([^)]*)\)', line)
                if links:
                    content = links.group(1)
                    def replace_link(match):
                        old = match.group(0)
                        assert (graph, old) in pins, 'LinkedTo target has no PinId declaration in this exact graph'
                        new = pins[graph, old]
                        linked_rewrites.append(dict(line=i + 1, graph=graph, node=node, source_pin=old, destination_pin=new))
                        return new
                    content = re.sub(r'(?<![A-Za-z0-9_])[0-9A-Fa-f]{32}(?![A-Za-z0-9_])', replace_link, content)
                    line = line[:links.start(1)] + content + line[links.end(1):]
        result.append(line)
    normalized = ''.join(result)
    return normalized, dict(applied=any(p['changed'] for p in pairs), passed=normalized == current,
        allowed_graphs=sorted(allowed), guid_pairs=pairs, linked_to_pin_pairs=linked_rewrites,
        exact_automatic_function_reference_renames=function_renames,
        guid_bijection_verified=True, same_graph_pin_declarations_required=True,
        node_classes_order_function_defaults_entrypoint_and_all_connections_compared_by_full_text=True,
        original_event_construction_interface_user_graphs_and_other_guids_unchanged=True,
        normalized_expected_text_sha256=text_sha(normalized), destination_text_sha256=text_sha(current))


def normalize_proven_section_defaults(expected, current, row, source_state, target_state):
    allowed = {
        '/Game/CodexGenerated/OldTown/SurfaceSeparation_20261009/Meshes/SM_OTS_Mod_MainHome_Door_Left_Separated_6f33dcf2d040':
            '/Game/CodexGenerated/Hotel/Meshes/SM_Hotel_MainHome_Door_Left_SurfaceOffset',
        '/Game/CodexGenerated/OldTown/SurfaceSeparation_20261009/Meshes/SM_OTS_Mod_MainHome_Door_Right_Separated_9b80a6022d29':
            '/Game/CodexGenerated/Hotel/Meshes/SM_Hotel_MainHome_Door_Right_SurfaceOffset',
    }
    if allowed.get(row['source_package']) != row['destination_package']:
        return expected, dict(applied=False)
    engine = {
        Path('D:/UE_5.7/Engine/Source/Runtime/Engine/Private/StaticMesh.cpp'):
            '6c73a0ede5f15c3b465a297b58ceb868eae8a0fb225ab9056b936362b5401ed8',
        Path('D:/UE_5.7/Engine/Source/Runtime/Engine/Classes/Engine/StaticMesh.h'):
            '82f4679c4ebe01050493ebba4b48e6a75edba6cd9ad7f110d9f35a3afeeb2e50',
    }
    for path, digest in engine.items():
        assert native.sha(path) == digest, 'Engine default semantics source changed'
        INPUT_HASHES[str(path)] = digest
    geometry = source_state['render_geometry']
    assert geometry == target_state['render_geometry'], 'Section defaults cannot hide any geometry change'
    assert geometry['lod_count'] == 1 and len(geometry['lods']) == 1
    sections = geometry['lods'][0]['sections']
    assert [r['section'] for r in sections] == list(range(9))
    pattern = re.compile(r'(?m)^\s*(SectionInfoMap|OriginalSectionInfoMap)=([^\n]*)\n')
    left = {m.group(1): m for m in pattern.finditer(expected)}
    right = {m.group(1): m for m in pattern.finditer(current)}
    assert set(left) == set(right) == {'SectionInfoMap', 'OriginalSectionInfoMap'}
    result, proofs = expected, []
    entries = re.compile(r'\((\d+), \(([^()]*)\)\)')
    default_flags = dict(bEnableCollision=True, bCastShadow=True, bVisibleInRayTracing=True,
        bAffectDistanceFieldLighting=True, bForceOpaque=False)
    for name in sorted(left):
        a, b = left[name], right[name]
        if a.group(0) == b.group(0):
            proofs.append(dict(map=name, applied=False, native_exact=True))
            continue
        amap = {int(m.group(1)): m.group(2) for m in entries.finditer(a.group(2))}
        bmap = {int(m.group(1)): m.group(2) for m in entries.finditer(b.group(2))}
        assert set(amap) == {0, 1, 2} and set(bmap) == set(range(9))
        assert all(amap[k] == bmap[k] for k in amap), 'An original explicit section changed'
        assert all(bmap[k] == 'MaterialIndex=' + str(k) for k in range(3, 9)), 'Additional section is not the exact implicit default'
        assert a.group(2).strip() == '(Map=(' + ','.join('(' + str(k) + ', (' + amap[k] + '))' for k in sorted(amap)) + '))'
        assert b.group(2).strip() == '(Map=(' + ','.join('(' + str(k) + ', (' + bmap[k] + '))' for k in sorted(bmap)) + '))'
        table = []
        for section in range(9):
            def effective(mapping):
                fields = mapping.get(section)
                # Exact observed fields: only optional MaterialIndex, all other
                # flags use FMeshSectionInfo's constructor defaults.
                index = int(fields.split('=', 1)[1]) if fields else (0 if section in mapping else section)
                return dict(MaterialIndex=index, **default_flags)
            aa, bb = effective(amap), effective(bmap)
            assert aa == bb
            table.append(dict(lod=0, section=section, source=aa, destination=bb))
        result = result.replace(a.group(0), b.group(0), 1)
        proofs.append(dict(map=name, applied=True, retained_explicit_keys=[0, 1, 2],
            added_exact_implicit_default_keys=[3, 4, 5, 6, 7, 8], effective_all_lod_section_table=table,
            explicit_original_fields_unchanged=True, rendered_geometry_sha256=fingerprint(geometry)))
    return result, dict(applied=any(p.get('applied') for p in proofs), source_package=row['source_package'],
        maps=proofs, geometry_unchanged=True, engine_default_constructor='StaticMesh.h:384-392',
        engine_get_semantics='StaticMesh.cpp:6376-6379 and 6405-6418',
        default_resolution='Exact key, then LOD0 key, then FMeshSectionInfo(SectionIndex)',
        no_nondefault_entries_ignored=True)


def export(obj, path, world):
    assert not path.exists(), str(path)
    unreal.SystemLibrary.execute_console_command(world, 'OBJ COMPONENTS Default__Object')
    text, proof = native.native_text_export(obj, path)
    assert proof['passed'] and read_native_text(path) == text
    proof['decoded_text_sha256'] = text_sha(text)
    return text, proof


def metadata(obj):
    return {str(k): str(v) for k, v in unreal.EditorAssetLibrary.get_metadata_tag_values(obj).items()}


def import_record(obj):
    # This separate check deliberately does not normalize filesystem paths.
    # Header renaming can preserve a relative string but change its resolution.
    data = None
    try:
        data = obj.get_editor_property('asset_import_data')
    except Exception:
        pass
    if data is None:
        return dict(present=False)
    filenames = [str(p) for p in data.extract_filenames()]
    asset_data = unreal.AssetRegistryHelpers.create_asset_data(obj)
    # UObject::SourceFileTagName() is a function name, not the literal tag.
    # The bound engine source returns FName("AssetImportData") at 2571-2574.
    tag = asset_data.get_tag_value('AssetImportData')
    if isinstance(tag, (tuple, list)):
        tag = next((x for x in tag if isinstance(x, str)), None)
    source_data = json.loads(tag) if tag else []
    assert isinstance(source_data, list)
    assert len(source_data) == len(filenames), 'AssetImportData tag is missing/incomplete for the live import data'
    return dict(present=True, object_path=data.get_path_name(),
        properties=native.reflect_editor_properties(data), extracted_filenames=filenames,
        resolved_filenames=[str(Path(p).resolve()) for p in filenames],
        source_files_exist=[Path(p).is_file() for p in filenames], source_file_metadata=source_data)


def material_parameters(obj, instance):
    edit = unreal.MaterialEditingLibrary
    names, effective = {}, {}
    for kind in ('scalar', 'vector', 'texture', 'static_switch'):
        names[kind] = sorted(str(x) for x in getattr(edit, 'get_' + kind + '_parameter_names')(obj))
        if instance:
            getter = getattr(edit, 'get_material_instance_' + kind + '_parameter_value')
            effective[kind] = {name: native.value(getter(obj, unreal.Name(name))) for name in names[kind]}
    return dict(names=names, effective_instance_values=effective)


def material_graph(obj):
    edit = unreal.MaterialEditingLibrary
    outputs, pending, nodes, errors = {}, [], {}, {}
    for key in sorted(k for k in dir(unreal.MaterialProperty) if k.startswith('MP_') and k != 'MP_MAX'):
        try:
            prop = getattr(unreal.MaterialProperty, key)
            expression = edit.get_material_property_input_node(obj, prop)
            outputs[key] = dict(node=native.path_of(expression),
                output=str(edit.get_material_property_input_node_output_name(obj, prop)))
            if expression:
                pending.append(expression)
        except Exception as error:
            errors[key] = str(error)
    while pending:
        expression = pending.pop()
        path = expression.get_path_name()
        if path in nodes:
            continue
        inputs = list(edit.get_inputs_for_material_expression(obj, expression))
        nodes[path] = dict(path=path, class_path=expression.get_class().get_path_name(),
            name=expression.get_name(), properties=native.reflect_editor_properties(expression),
            input_names=[str(x) for x in edit.get_material_expression_input_names(expression)],
            inputs=[native.path_of(x) for x in inputs])
        pending.extend(x for x in inputs if x)
    return dict(expression_count=edit.get_num_material_expressions(obj), property_outputs=outputs,
        reachable_expression_nodes=[nodes[p] for p in sorted(nodes)], unsupported_property_getters=errors,
        disconnected_expression_coverage='Full primary native T3D includes every serialized orphan expression; graph traversal is additional evidence, not a replacement.')


def mesh_geometry(obj):
    lods = []
    for lod in range(obj.get_num_lods()):
        sections = []
        for index in range(obj.get_num_sections(lod)):
            vertices, triangles, normals, uv0, tangents = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(obj, lod, index)
            geometry = dict(vertices=[native.value(x) for x in vertices], indices=[int(x) for x in triangles],
                normals=[native.value(x) for x in normals], uv0=[native.value(x) for x in uv0],
                tangents=[dict(tangent_x=native.value(x.tangent_x), flip_tangent_y=bool(x.flip_tangent_y)) for x in tangents])
            sections.append(dict(section=index, vertex_count=len(vertices), index_count=len(triangles),
                complete_position_index_normal_uv0_tangent_sha256=fingerprint(geometry)))
        lods.append(dict(lod=lod, sections=sections))
    return dict(lod_count=obj.get_num_lods(), lods=lods, numeric_tolerance=0,
        empty_sections_preserved=True, all_render_lods_and_sections_compared=True)


def texture_source_id(obj):
    for name in ('blueprint_get_texture_source_id_string', 'get_texture_source_id_string'):
        getter = getattr(obj, name, None)
        if getter:
            value = native.value(getter())
            assert value not in (None, False, ''), 'No valid editor source ID: ' + obj.get_path_name()
            return dict(api=name, value=value)
    raise AssertionError('Texture source GUID reader is unavailable: ' + obj.get_path_name())


def capture(obj, cls, native_text):
    result = dict(class_path=obj.get_class().get_path_name(), properties=native.reflect_editor_properties(obj),
        metadata=metadata(obj), asset_import_data=import_record(obj))
    if cls == 'MaterialInstanceConstant':
        result['material_parameters'] = material_parameters(obj, True)
    elif cls == 'Material':
        result['material_parameters'] = material_parameters(obj, False)
        result['material_graph'] = material_graph(obj)
        # The actual serialized expression declarations remain part of the
        # zero-tolerance whole-text comparison, including disconnected nodes.
        result['native_expression_declaration_count'] = len(re.findall(r'Begin Object Class=[^\r\n]*MaterialExpression', native_text))
    elif cls == 'StaticMesh':
        result['material_slots'] = [native.value(slot) for slot in obj.static_materials]
        result['material_slot_identities'] = [dict(material_slot_name=str(slot.get_editor_property('material_slot_name')),
            imported_material_slot_name=str(slot.get_editor_property('imported_material_slot_name')))
            for slot in obj.static_materials]
        result['render_geometry'] = mesh_geometry(obj)
        body = obj.get_editor_property('body_setup')
        result['body_setup_properties'] = native.reflect_editor_properties(body) if body else None
    elif cls == 'Texture2D':
        result['texture_source_id'] = texture_source_id(obj)
    elif cls == 'Blueprint':
        generated = obj.generated_class()
        assert generated, 'Missing persisted GeneratedClass; never compile during verification'
        cdo = unreal.get_default_object(generated)
        result['generated_class_path'] = generated.get_path_name()
        result['generated_class_properties'] = native.reflect_editor_properties(generated)
        result['cdo_properties'] = native.reflect_editor_properties(cdo)
    return result


def expected_corrected_import(expected, current, correction):
    left, right = expected['asset_import_data'], current['asset_import_data']
    a, b = left.get('source_file_metadata', []), right.get('source_file_metadata', [])
    nonrelative_a = [{k: v for k, v in item.items() if k != 'RelativeFilename'} for item in a]
    nonrelative_b = [{k: v for k, v in item.items() if k != 'RelativeFilename'} for item in b]
    proof = dict(source_data_hash_timestamp_and_label_preserved=nonrelative_a == nonrelative_b,
        nonrelative_differences=differences(nonrelative_a, nonrelative_b), relative_filename_changes=[])
    if a != b:
        assert correction and correction.get('import_filename_correction'), 'Unapproved raw import metadata change'
        assert len(a) == len(b) and nonrelative_a == nonrelative_b, 'Import hash/timestamp/label changed'
        assert left.get('resolved_filenames', []) == right.get('resolved_filenames', []), 'Import source resolution still differs'
        approved = correction['import_filename_correction']
        assert approved['restored_resolved'] == right.get('resolved_filenames', [])
        for source, target in zip(a, b):
            assert set(source) == set(target)
            if source.get('RelativeFilename') != target.get('RelativeFilename'):
                proof['relative_filename_changes'].append(dict(old=source.get('RelativeFilename'), new=target.get('RelativeFilename')))
        left['source_file_metadata'] = deepcopy(b)
    return expected, proof


def main():
    assert not REPORT.exists() and not V.exists() and not (W / 'FinalReview.json').exists()
    assert native.sha(IMPORT_TAG_ENGINE_SOURCE) == IMPORT_TAG_ENGINE_SOURCE_SHA256, 'Engine import-tag semantics source changed'
    INPUT_HASHES[str(IMPORT_TAG_ENGINE_SOURCE)] = IMPORT_TAG_ENGINE_SOURCE_SHA256
    plan = read(W / 'HotelNamePlan.json')
    copied = read(W / 'CopiedPackages.json')
    header = read(W / 'HeaderCopyProof.json')
    completion = read(W / 'Copy1.Completion.json')
    corrections = read(W / 'PrivateAssetCorrections.json')
    effective = read(W / 'EffectivePrivateHashes.json')
    metadata_completion = read(W / 'MetadataFix5.Completion.json')
    baseline = read(W / 'ProtectedBeforeAfterRestore.json')['file_sha256']
    assert plan['passed'] and copied['passed'] and header['passed'] and header['exact_write_set']
    assert completion['normal_zero_exit'] and completion['exit_code'] == 0
    assert copied['plan_sha256'] == native.sha(W / 'HotelNamePlan.json')
    assert corrections['passed'] and effective['passed']
    assert metadata_completion['normal_zero_exit'] and metadata_completion['exit_code'] == 0
    assert Path(metadata_completion['script']).resolve() == R / 'Scripts/CorrectHotelPrivateMetadata.py'
    assert corrections['all_original_content_config_unchanged']
    assert effective['initial_copy_sha256'] == native.sha(W / 'CopiedPackages.json')
    assert effective['correction_report_sha256'] == native.sha(W / 'PrivateAssetCorrections.json')
    corrected = {r['package']: r for r in corrections['corrections']}
    assert len(corrected) == corrections['changed_private_assets']
    current_private = effective['new_asset_sha256']
    assert set(current_private) == set(copied['new_asset_sha256'])
    changed = {p for p in current_private if current_private[p] != copied['new_asset_sha256'][p]}
    assert changed == {r['file'] for r in corrected.values()}
    for fix in corrected.values():
        assert fix['before_sha256'] == copied['new_asset_sha256'][fix['file']]
        assert fix['after_sha256'] == current_private[fix['file']]
    rows = plan['mappings']; assert len(rows) == 617
    assert dict(Counter(row['asset_class'] for row in rows)) == EXPECTED_COUNTS
    mapping = copied['package_remapping']
    assert len(mapping) == 618 and all(mapping[k] == v for k, v in plan['source_to_destination'].items())
    assert mapping['/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'] == '/Game/CodexGenerated/Hotel/Maps/L_Hotel_Stage'
    before = file_hashes()
    assert all(before.get(path) == digest for path, digest in baseline.items())
    assert all(before.get(path) == digest for path, digest in current_private.items())
    for row in rows:
        assert before[row['source_file']] == row['source_sha256']
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    assert world
    rules, pattern = extra_identity_rules(mapping)
    results, failures = [], []
    for i, row in enumerate(rows, 1):
        token = str(i).zfill(4) + '_' + row['destination_asset_name']
        asset_result = dict(source_package=row['source_package'], destination_package=row['destination_package'],
            asset_class=row['asset_class'], passed=False)
        try:
            source = unreal.load_asset(row['source_package'])
            target = unreal.load_asset(row['destination_package'])
            assert source and target
            assert source.get_name() == row['source_asset_name'] and target.get_name() == row['destination_asset_name']
            assert source.get_class() == target.get_class()
            source_text, source_export = export(source, V / 'SourceNativeText' / (token + '.t3d'), world)
            target_text, target_export = export(target, V / 'DestinationNativeText' / (token + '.t3d'), world)
            asset_result.update(source_native=source_export, destination_native=target_export)
            expected_text, identity_edits = expected_native(source_text, row, mapping, rules, pattern)
            compared_target_text, shell_proof = strip_unreferenced_constructor_shell(target_text, row)
            expected_text, generated_graph_proof = normalize_generated_graph_guids(expected_text, compared_target_text, row)
            source_state = capture(source, row['asset_class'], source_text)
            target_state = capture(target, row['asset_class'], target_text)
            expected_text, section_default_proof = normalize_proven_section_defaults(expected_text,
                compared_target_text, row, source_state, target_state)
            expected = expected_state(source_state, mapping, rules, pattern)
            expected, import_metadata_proof = expected_corrected_import(expected, target_state, corrected.get(row['destination_package']))
            state_differences = differences(expected, target_state)
            native_difference = first_text_difference(expected_text, compared_target_text)
            import_difference = differences(source_state['asset_import_data'].get('resolved_filenames', []),
                target_state['asset_import_data'].get('resolved_filenames', []), '$.resolved_import_filenames')
            body_proof = None
            if row['asset_class'] == 'StaticMesh':
                a, b = source.get_editor_property('body_setup'), target.get_editor_property('body_setup')
                assert bool(a) == bool(b)
                if a:
                    left, lp = export(a, V / 'SourceBodySetup' / (token + '.t3d'), world)
                    right, rp = export(b, V / 'DestinationBodySetup' / (token + '.t3d'), world)
                    expected_body, edits = expected_native(left, row, mapping, rules, pattern)
                    body_proof = dict(passed=expected_body == right, source=lp, destination=rp,
                        first_difference=first_text_difference(expected_body, right), identity_edits=edits)
            evidence = dict(source=source_state, expected=expected, destination=target_state)
            evidence_file = V / 'Properties' / (token + '.json')
            write(evidence_file, evidence)
            asset_result.update(passed=not state_differences and native_difference is None and not import_difference
                and (body_proof is None or body_proof['passed']), source_native=source_export, destination_native=target_export,
                native_text_equal_after_exact_path_and_self_identity_normalization=native_difference is None,
                normalized_expected_native_sha256=text_sha(expected_text), destination_native_sha256=text_sha(target_text),
                compared_destination_native_sha256=text_sha(compared_target_text), constructor_empty_shell_proof=shell_proof,
                generated_graph_identity_proof=generated_graph_proof,
                proven_redundant_section_default_proof=section_default_proof,
                import_metadata_proof=import_metadata_proof,
                preexisting_missing_import_source_paths=[path for path, exists in zip(
                    source_state['asset_import_data'].get('resolved_filenames', []),
                    source_state['asset_import_data'].get('source_files_exist', [])) if not exists],
                allowed_self_begin_object_identity_edits=identity_edits, first_native_difference=native_difference,
                reflected_semantic_differences=state_differences, import_resolution_differences=import_difference,
                body_setup_native=body_proof, source_properties_sha256=fingerprint(source_state),
                normalized_expected_properties_sha256=fingerprint(expected), destination_properties_sha256=fingerprint(target_state),
                complete_property_evidence=str(evidence_file), complete_property_evidence_sha256=native.sha(evidence_file))
        except Exception as error:
            asset_result.update(error=str(error), traceback=traceback.format_exc())
        results.append(asset_result)
        if not asset_result['passed']:
            failures.append(asset_result)
        if i % 20 == 0:
            unreal.log('HOTEL_ASSET_COPY_VERIFICATION_PROGRESS ' + str(i) + '/617 failures=' + str(len(failures)))
    after = file_hashes()
    content_unchanged = before == after
    inputs_unchanged = all(native.sha(Path(path)) == digest for path, digest in INPUT_HASHES.items())
    report = dict(passed=not failures and content_unchanged and inputs_unchanged,
        validation_utc=datetime.now(timezone.utc).isoformat(), asset_count=len(results),
        class_counts=dict(Counter(row['asset_class'] for row in rows)), passed_asset_count=len(results) - len(failures),
        failed_asset_count=len(failures), rows=results, failures=failures,
        no_save_no_compile_no_asset_mutation=True, all_content_config_bytes_unchanged=content_unchanged,
        all_input_evidence_unchanged=inputs_unchanged, input_sha256=INPUT_HASHES,
        package_mapping_count=len(mapping), package_mapping_sha256=fingerprint(mapping),
        plan_sha256=native.sha(W / 'HotelNamePlan.json'), copied_packages_sha256=native.sha(W / 'CopiedPackages.json'),
        all617_primary_native_texts_compared=all('first_native_difference' in r for r in results), numeric_tolerance=0,
        effective_private_hashes_sha256=native.sha(W / 'EffectivePrivateHashes.json'),
        private_asset_corrections_sha256=native.sha(W / 'PrivateAssetCorrections.json'),
        native_comparison_contract='Exact mapped paths and narrowly declared generated identity names; an unreferenced zero-property ctor EditorOnlyData shell may be excised. Only automatic ExecuteUbergraph and LightCircuit three interface-wrapper graph IDs admit a proved bijection with strict node/pin/LinkedTo/full-text preservation. All real serialized data and original graph IDs remain strict. Raw full native text is retained.',
        geometry_compared='All StaticMesh render LOD sections: full positions/indices/normals/UV0/tangents exact hashes, complete BodySetup native text and reflected material slots.',
        material_graph_compared='Full asset T3D with every expression, reflected reachable nodes, property outputs and all parameter types; no shader-channel or WPO exclusions.',
        texture_guid_compared='UTexture Blueprint_GetTextureSourceIdString plus complete reflection and native import metadata.',
        import_metadata_tag_proof=dict(tag='AssetImportData', function='UObject::SourceFileTagName()',
            source=str(IMPORT_TAG_ENGINE_SOURCE), sha256=IMPORT_TAG_ENGINE_SOURCE_SHA256, lines='2571-2574'),
        import_filename_resolution_compared_separately=True,
        preexisting_missing_import_sources=[dict(asset=r['source_package'], paths=r['preexisting_missing_import_source_paths'])
            for r in results if r.get('preexisting_missing_import_source_paths')],
        forbidden_normalizations=['No broad basename replacement', 'No pointer-address scrubbing',
            'No geometry exclusion', 'No material-channel/WPO exemption', 'No numeric tolerance',
            'No filesystem source-filename remapping'])
    write(REPORT, report)
    assert report['passed'], 'Hotel asset-copy mismatch; inspect ' + str(REPORT)
    unreal.log('HOTEL_ASSET_COPY_VERIFICATION_PASS 617')


if __name__ == '__main__':
    main()
