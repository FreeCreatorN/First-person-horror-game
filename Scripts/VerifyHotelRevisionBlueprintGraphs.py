"""Compare every saved source/new Blueprint graph without importing Unreal."""
import difflib
import hashlib
import json
import re
from pathlib import Path
from HotelDoorClosurePreservation import _parse_native, _render

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Saved/CodexOutputs/HotelRevision_20261019'


def read(path):
    raw = Path(path).read_bytes()
    return raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')


def graphs(text):
    tree = _parse_native(text)
    declarations = {node['name'] for node in tree['body'] if isinstance(node, dict)
                    and 'Class=/Script/Engine.EdGraph ' in node['header']}
    found = {}
    for node in tree['body']:
        if not isinstance(node, dict) or node['name'] not in declarations:
            continue
        if 'Class=' in node['header']:
            continue
        found[node['name']] = dict(
            header=node['header'],
            nodes=sorted(_render(child) for child in node['body'] if isinstance(child, dict)),
            properties=[line for line in node['body'] if isinstance(line, str)],
            end=node['end'])
    assert set(found) == declarations, (declarations, set(found))
    root_properties = [line for line in tree['body'] if isinstance(line, str) and line.lstrip().startswith(
        ('NewVariables', 'ImplementedInterfaces', 'ParentClass=', 'Timelines', 'FunctionGraphs', 'UbergraphPages'))]
    return dict(graphs=found, variables_interfaces_parent_graph_arrays=root_properties)


def node_map(graph):
    return {re.search(r'\bName="([^"]+)"', text).group(1): text for text in graph['nodes']}


def canonicalize_compiler_identities(expected, actual):
    """Map clone identities, proving node/pin names and all links remain exact."""
    ledger = []
    generated = {'DisableHighlight', 'EnableHighlight', 'Interact'}
    for name in list(actual['graphs']):
        if name in expected['graphs']:
            continue
        graph = actual['graphs'][name]
        entry = [text for text in graph['nodes'] if 'CustomGeneratedFunctionName=' in text]
        assert len(entry) == 1, ('Unrecognized added graph', name)
        canonical = re.search(r'CustomGeneratedFunctionName="([^"]+)"', entry[0]).group(1)
        assert canonical in generated and canonical in expected['graphs']
        assert all('bIsIntermediateNode=True' in text for text in graph['nodes'])
        assert all('bIsIntermediateNode=True' in text for text in expected['graphs'][canonical]['nodes'])
        transformed = json.loads(json.dumps(graph).replace(':' + name, ':' + canonical))
        transformed['header'] = transformed['header'].replace('Name="' + name + '"', 'Name="' + canonical + '"')
        actual['graphs'][canonical] = transformed
        del actual['graphs'][name]
        ledger.append(dict(kind='compiler_intermediate_graph_name', new=name, source=canonical))
    assert set(actual['graphs']) == set(expected['graphs'])
    for name, source in expected['graphs'].items():
        target = actual['graphs'][name]
        sn, tn = node_map(source), node_map(target)
        assert set(sn) == set(tn), name
        remap = {}

        def add(new, old, kind, **context):
            if new in remap:
                assert remap[new] == old
            remap[new] = old
            if new != old:
                ledger.append(dict(kind=kind, graph=name, new=new, source=old, **context))

        is_generated = name in generated and all('bIsIntermediateNode=True' in text for text in sn.values())
        for node_name, source_text in sn.items():
            target_text = tn[node_name]
            source_guid = re.findall(r'\bNodeGuid=([A-F0-9]{32})', source_text)
            target_guid = re.findall(r'\bNodeGuid=([A-F0-9]{32})', target_text)
            assert len(source_guid) == len(target_guid) == 1
            add(target_guid[0], source_guid[0], 'duplicated_node_guid', node=node_name)
            source_pins = re.findall(r'CustomProperties Pin \(PinId=([A-F0-9]{32}),PinName="([^"]+)"', source_text)
            target_pins = re.findall(r'CustomProperties Pin \(PinId=([A-F0-9]{32}),PinName="([^"]+)"', target_text)
            assert [pin[1] for pin in source_pins] == [pin[1] for pin in target_pins], (name, node_name)
            for (old, pin_name), (new, _) in zip(source_pins, target_pins):
                if new != old:
                    assert is_generated, ('User authored graph pin identity changed', name, node_name, pin_name)
                add(new, old, 'compiler_intermediate_pin_guid', node=node_name, pin=pin_name)
        assert len(set(remap.values())) == len(remap), 'Identity mapping must be bijective'
        if is_generated:
            source_guid = re.findall(r'\bGraphGuid=([A-F0-9]{32})', ''.join(source['properties']))
            target_guid = re.findall(r'\bGraphGuid=([A-F0-9]{32})', ''.join(target['properties']))
            assert len(source_guid) == len(target_guid) == 1
            add(target_guid[0], source_guid[0], 'compiler_intermediate_graph_guid')
        # Rebase actual identities everywhere within the graph, including LinkedTo.
        # Unknown identifiers and all other graph/node/pin properties remain exact.
        serialized = json.dumps(target, ensure_ascii=False)
        actual['graphs'][name] = json.loads(re.sub(r'\b[A-F0-9]{32}\b', lambda m: remap.get(m.group(0), m.group(0)), serialized))
    return ledger


def main():
    exports = json.loads((WORK / 'BlueprintGraphExports.json').read_text(encoding='utf-8-sig'))
    mapping = json.loads((WORK / 'BlueprintMapping.json').read_text(encoding='utf-8-sig'))
    rows = []
    for old, row in exports.items():
        new = mapping[old]
        source = read(row['source_native'])
        target = read(row['new_native'])
        # Only the duplicated asset's package and own Blueprint short name differ.
        rebased = target.replace(new, old).replace(Path(new).name, Path(old).name)
        expected, actual = graphs(source), graphs(rebased)
        identities = canonicalize_compiler_identities(expected, actual)
        good = expected == actual
        diff = [] if good else list(difflib.unified_diff(
            json.dumps(expected, ensure_ascii=False, indent=2).splitlines(),
            json.dumps(actual, ensure_ascii=False, indent=2).splitlines(),
            fromfile='rebased_source', tofile='new_private_blueprint', lineterm=''))
        rows.append(dict(source=old, new=new, passed=good,
                         source_native_file=row['source_native'], new_native_file=row['new_native'],
                         source_native_text_sha256=hashlib.sha256(source.encode()).hexdigest(),
                         new_native_text_sha256=hashlib.sha256(target.encode()).hexdigest(),
                         graph_names=sorted(actual['graphs']),
                         graph_count=len(actual['graphs']),
                         existing_nodes_and_graph_properties_exact=good,
                         interfaces_variables_parent_and_graph_arrays_exact=good,
                         identity_remapping=identities,
                         all_pin_properties_and_linked_to_topology_exact=good,
                         differences=diff))
    result = dict(passed=all(row['passed'] for row in rows), blueprints=len(rows),
                  remapping_only='Own package/name; duplicated NodeGuid; only compiler intermediate graph names/GraphGuid/PinId mapped bijectively by graph/node/pin name. Every pin property, LinkedTo edge, node property, and graph property order compared after that explicit identity mapping. Graph objects keyed by name; node object export order ignored.',
                  read_only=True, unreal_not_loaded=True, rows=rows)
    assert len(rows) == 8
    (WORK / 'BlueprintGraphPreservation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], blueprints=len(rows),
                         graph_counts={Path(row['source']).name: row['graph_count'] for row in rows}), ensure_ascii=False))
    assert result['passed'], 'Blueprint graph state changed; see BlueprintGraphPreservation.json'


if __name__ == '__main__':
    main()
