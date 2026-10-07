"""Compare persisted-map snapshots, keeping detailed differences on disk."""
import difflib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'Saved/CodexOutputs/HotelIntegration_20261004'


def load(name):
    data = json.loads((OUTPUT / (name + '.json')).read_text(encoding='utf-8'))
    content = (OUTPUT / (name + '.t3d')).read_text(encoding='utf-8-sig')
    content = content.replace(data['world'], '__Map.__World')
    content = content.replace(data['world'].rsplit('.', 1)[0], '__Map')
    blocks, current, label = {}, [], None
    outside = []
    for line in content.splitlines():
        if line.strip().startswith('Begin Actor '):
            label = re.search(r'\bName=([^ ]+)', line).group(1)
            current = [line]
        elif label is not None:
            current.append(line)
            if line.strip() == 'End Actor':
                assert label not in blocks, label
                blocks[label] = current
                current, label = [], None
        else:
            outside.append(line)
    # T3D includes WorldSettings, builder brush and editor navigation actors
    # which EditorActorSubsystem intentionally omits from its returned list.
    assert {r['name'] for r in data['actors']} <= blocks.keys(), name
    return data, blocks, outside


def main():
    base, b, bo = load('Baseline')
    cur, c, co = load('Current')
    preview, p, po = load('Preview')
    labels = {r['name']: r['label'] for r in base['actors'] + cur['actors'] + preview['actors']}
    for key in b.keys() | c.keys() | p.keys():
        labels.setdefault(key, key)
    changes, detailed = {}, []
    for name, other in [('current', c), ('hotel', p)]:
        added, removed = sorted(other.keys() - b.keys()), sorted(b.keys() - other.keys())
        changed = sorted(k for k in b.keys() & other.keys() if b[k] != other[k])
        changes[name] = {'added': added, 'removed': removed, 'changed': changed}
        for key in changed:
            detailed.append('\n### {}: {} ({})\n'.format(name, labels.get(key), key))
            detailed.extend(difflib.unified_diff(b[key], other[key], fromfile='baseline', tofile=name, lineterm=''))
    user_changed = set(changes['current']['added'] + changes['current']['removed'] + changes['current']['changed'])
    hotel_changed = set(changes['hotel']['added'] + changes['hotel']['removed'] + changes['hotel']['changed'])
    overlap = sorted(user_changed & hotel_changed)
    report = {'baseline_sha256': base['source_sha256'], 'current_sha256': cur['source_sha256'],
              'preview_sha256': preview['source_sha256'], 'changes': changes,
              'overlapping_actor_names': overlap, 'actor_labels': {k: labels[k] for k in user_changed},
              'outside_actor_text_equal_current': bo == co,
              'outside_actor_text_equal_preview': bo == po}
    (OUTPUT / 'MergeComparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT / 'MergeActorDifferences.txt').write_text('\n'.join(detailed), encoding='utf-8')
    summary = {k: {s: len(v) for s, v in value.items()} for k, value in changes.items()}
    print(json.dumps({'changes': summary, 'overlapping_actor_names': overlap[:25],
                      'current_changed_labels': [labels[k] for k in sorted(user_changed)][:25],
                      'outside_actor_text_equal_current': bo == co}, ensure_ascii=False))


if __name__ == '__main__':
    main()
