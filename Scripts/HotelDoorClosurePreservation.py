"""Strict, offline preservation proof for the original hotel's door closure fix.

``verify(before, after, plan)`` consumes ApplyOldTownCallableLighting.snapshot
records.  It does not load Unreal or modify any file.  The caller separately
validates the new DoorStops mesh/material/shape and the door operation tests.

Plan schema::

    {"doors": [{"label": "...", "changed_components": ["DoorLeaf", ...]}],
     "moving_hinges": [{"label": "..._MovingHinges", "mesh": "/Game/...X.X",
                        "door": "...", "reparent_to_hinge": True,
                        "expected_parent": "...DoorHinge"}]}

Only the named existing child components may move, by exactly local Y -5 cm.
Only the named hinge Actor's sole mesh reference may change. Existing door
SceneComponent Native location/rotation overrides are numerically checked
against that phase's structured record before normalization, because changed
Blueprint defaults can add/remove explicit overrides without changing values.
All actual local/world values and all remaining Native state are compared.
When explicitly planned, the eleven originally misparented moving hinges may
attach to their own door's DoorHinge with identity local transform; their world
transform must match that hinge. Other moving hinges remain mesh-only changes.
"""
from copy import deepcopy
import difflib
import hashlib
import math
from pathlib import Path
import re


SHIFT_CM = -5.0
STOPS_NAME = 'DoorStops'
STATIC_MESH_COMPONENT = '/Script/Engine.StaticMeshComponent'
NO_COLLISION = '<CollisionEnabled.NO_COLLISION: 0>'
_SWING = {'DoorLeaf', 'Handle', 'LeafCollision'}
_SLIDER = {side + name for side in ('Left', 'Right')
           for name in ('Leaf', 'LeafCollision', 'Handle', 'GlassPanel')}


def _require(ok, message, **details):
    if not ok:
        raise AssertionError(dict(message=message, **details))


def _same(actual, expected, message, **details):
    _require(actual == expected, message, expected=expected, actual=actual, **details)


def _vector(actual, expected, message, tolerance=1e-6, **details):
    _require(isinstance(actual, list) and isinstance(expected, list)
             and len(actual) == len(expected)
             and all(isinstance(x, (int, float)) and math.isfinite(x)
                     for x in actual + expected)
             and all(abs(x - y) <= tolerance for x, y in zip(actual, expected)),
             message, expected=expected, actual=actual, **details)


def _shift(vector):
    _require(len(vector) == 3, 'Expected a three-component local location')
    return [vector[0], vector[1] + SHIFT_CM, vector[2]]


def _components(actor):
    rows = {c['name']: c for c in actor['components']}
    _require(len(rows) == len(actor['components']), 'Duplicate component name')
    return rows


def _stops(row, label, exact=False):
    _same(row['class_path' if exact else 'class'], STATIC_MESH_COMPONENT,
          'DoorStops must be a StaticMeshComponent', actor=label)
    parent = row['parent']
    _require(parent is not None and
             (parent.endswith('.OpeningRoot') if exact else parent == 'OpeningRoot'),
             'DoorStops must attach to OpeningRoot', actor=label, parent=parent)
    _same(row['collision'], NO_COLLISION, 'DoorStops collision changed', actor=label)
    _same(row['collision_profile'], 'NoCollision',
          'DoorStops collision profile changed', actor=label)
    _require(bool(row['mesh']) and row['mesh'].startswith('/Game/CodexGenerated/Hotel/'),
             'DoorStops mesh must be an owned Hotel asset', actor=label, mesh=row['mesh'])


def _rotate(q, vector):
    # UE uses xyzw quaternions. q * v * inverse(q), including non-unit roundoff.
    x, y, z, w = q
    norm = x*x + y*y + z*z + w*w
    _require(abs(norm - 1) < 1e-6, 'Parent quaternion is not normalized', quaternion=q)
    ux, uy, uz = vector
    tx, ty, tz = 2*(y*uz-z*uy), 2*(z*ux-x*uz), 2*(x*uy-y*ux)
    return [ux + (w*tx + y*tz-z*ty)/norm,
            uy + (w*ty + z*tx-x*tz)/norm,
            uz + (w*tz + x*ty-y*tx)/norm]


def _changed_world(before, after, parent, label, component):
    _same(set(before), set(after), 'World transform schema changed',
          actor=label, component=component)
    for key in set(before) - {'translation'}:
        _same(after[key], before[key], 'Existing world rotation/scale changed',
              actor=label, component=component, field=key)
    delta = _rotate(parent['rotation_quaternion_xyzw'],
                    [0.0, SHIFT_CM * parent['scale'][1], 0.0])
    expected = [x+y for x, y in zip(before['translation'], delta)]
    _vector(after['translation'], expected, 'World location is not parent-space Y -5 cm',
            actor=label, component=component)


def _native(record):
    raw = Path(record['file']).read_bytes()
    text = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')
    _same(hashlib.sha256(text.encode()).hexdigest(), record['native_text_sha256'],
          'Native evidence file hash mismatch', file=record['file'])
    return text


def _node_name(header):
    found = re.search(r'\bName="([^"]+)"', header)
    _require(found is not None, 'Native object header has no quoted Name', header=header)
    return found.group(1)


def _parse_native(text):
    # Retain all text and ordering. Only explicitly authorized fields are edited
    # in the comparison copy; this is not a generic property normalization.
    root = None
    stack = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith('Begin Object '):
            node = dict(header=line, name=_node_name(line), body=[], end=None)
            if stack:
                stack[-1]['body'].append(node)
            else:
                _require(root is None, 'Multiple root objects in Native export')
                root = node
            stack.append(node)
        elif line.strip() == 'End Object':
            _require(bool(stack), 'Unbalanced Native End Object')
            stack.pop()['end'] = line
        else:
            _require(bool(stack) or not line.strip(), 'Text outside Native root')
            if stack:
                stack[-1]['body'].append(line)
    _require(root is not None and not stack, 'Incomplete Native export')
    return root


def _render(node):
    return node['header'] + ''.join(_render(x) if isinstance(x, dict) else x
                                  for x in node['body']) + node['end']


def _native_location(line):
    found = re.fullmatch(r'\s*RelativeLocation=\(X=([^,]+),Y=([^,]+),Z=([^\)]+)\)\s*', line)
    _require(found is not None, 'Unexpected Native RelativeLocation syntax', line=line)
    return [float(x) for x in found.groups()]


def _native_rotation(line):
    found = re.fullmatch(r'\s*RelativeRotation=\(Pitch=([^,]+),Yaw=([^,]+),Roll=([^\)]+)\)\s*', line)
    _require(found is not None, 'Unexpected Native RelativeRotation syntax', line=line)
    return [float(x) for x in found.groups()]


def _native_scale(line):
    found = re.fullmatch(r'\s*RelativeScale3D=\(X=([^,]+),Y=([^,]+),Z=([^\)]+)\)\s*', line)
    _require(found is not None, 'Unexpected Native RelativeScale3D syntax', line=line)
    return [float(x) for x in found.groups()]


def _canonical_door_native(text, actor, changed, is_after):
    node = _parse_native(text)
    parts = _components(actor)
    removed_stops = []
    kept = []
    for item in node['body']:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        name = item['name']
        if name == STOPS_NAME:
            _require(is_after, 'Baseline already contains DoorStops')
            _require(not any(isinstance(x, dict) for x in item['body']),
                     'DoorStops unexpectedly owns nested Native objects')
            _require(STATIC_MESH_COMPONENT in item['header'],
                     'DoorStops Native class differs', header=item['header'])
            removed_stops.append(item)
            continue
        if name in parts:
            stripped = []
            counts = {'RelativeLocation': 0, 'RelativeRotation': 0}
            for line in item['body']:
                _require(isinstance(line, str), 'Door SceneComponent has nested Native objects', component=name)
                if re.match(r'\s*RelativeLocation=', line):
                    counts['RelativeLocation'] += 1
                    _vector(_native_location(line), parts[name]['location'],
                            'Native local location disagrees with structured evidence',
                            tolerance=0.000051, component=name)
                elif re.match(r'\s*RelativeRotation=', line):
                    counts['RelativeRotation'] += 1
                    _vector(_native_rotation(line), parts[name]['rotation'],
                            'Native local rotation disagrees with structured evidence',
                            tolerance=0.000051, component=name)
                else:
                    stripped.append(line)
            _require(all(count <= 1 for count in counts.values()),
                     'Duplicate Native relative transform field', component=name, counts=counts)
            item['body'] = stripped
        kept.append(item)
    _same(len(removed_stops), 2 if is_after else 0,
          'Expected DoorStops declaration and value blocks only')
    members = 0
    array_stops = 0
    array_index = 0
    result = []
    for item in kept:
        if isinstance(item, dict):
            result.append(item)
            continue
        if re.fullmatch(r'\s*DoorStops="DoorStops"\s*', item):
            _require(is_after, 'Baseline DoorStops member reference exists')
            members += 1
            continue
        match = re.fullmatch(r'(\s*BlueprintCreatedComponents)\((\d+)\)="([^"]+)"(\r?\n)?', item)
        if match:
            if match.group(3) == STOPS_NAME:
                _require(is_after, 'Baseline DoorStops array reference exists')
                array_stops += 1
                continue
            # Adding one SCS component may shift later array indices. Preserve
            # every existing entry and its order; canonicalize only the index.
            item = '{}({})="{}"{}'.format(match.group(1), array_index,
                                           match.group(3), match.group(4) or '')
            array_index += 1
        result.append(item)
    _same(members, 1 if is_after else 0, 'DoorStops member reference count differs')
    _same(array_stops, 1 if is_after else 0, 'DoorStops created-component reference count differs')
    node['body'] = result
    return _render(node)


def _canonical_hinge_native(text, expected_mesh):
    node = _parse_native(text)
    count = 0
    for item in node['body']:
        if not isinstance(item, dict):
            continue
        rows = []
        for line in item['body']:
            _require(isinstance(line, str), 'Moving hinge component owns nested Native objects')
            if re.match(r'\s*StaticMesh=', line):
                found = re.fullmatch(r'\s*StaticMesh="/Script/Engine.StaticMesh\'([^\']+)\'"\s*', line)
                _require(found is not None and found.group(1) == expected_mesh,
                         'Native moving hinge mesh differs', expected=expected_mesh, line=line)
                count += 1
            else:
                rows.append(line)
        item['body'] = rows
    _same(count, 1, 'Expected exactly one explicit moving hinge Native mesh reference')
    return _render(node)


def _canonical_reparented_hinge_native(text, actor, expected_mesh, expected_parent):
    """Normalize only the explicitly proved mesh/attachment/root-local fields."""
    node = _parse_native(text)
    parts = _components(actor)
    _same(len(parts), 1, 'Reparented hinge must have one component')
    component_name = next(iter(parts))
    part = parts[component_name]
    counts = dict(mesh=0, parent=0, location=0, rotation=0, scale=0)
    for item in node['body']:
        if not isinstance(item, dict) or item['name'] != component_name:
            continue
        rows = []
        for line in item['body']:
            _require(isinstance(line, str), 'Reparented hinge owns nested Native objects')
            if re.match(r'\s*StaticMesh=', line):
                found = re.fullmatch(r'\s*StaticMesh="/Script/Engine.StaticMesh\'([^\']+)\'"\s*', line)
                _require(found is not None and found.group(1) == expected_mesh,
                         'Native reparented hinge mesh differs', expected=expected_mesh, line=line)
                counts['mesh'] += 1
            elif re.match(r'\s*AttachParent=', line):
                found = re.fullmatch(r'\s*AttachParent="([^"]+)"\s*', line)
                _require(found is not None, 'Unexpected Native AttachParent syntax', line=line)
                reference = found.group(1)
                if reference.startswith('/Script/Engine.SceneComponent\'') and reference.endswith("'"):
                    reference = reference[len('/Script/Engine.SceneComponent\''):-1]
                _require(reference in (expected_parent, expected_parent.rsplit('.', 1)[-1]),
                         'Native reparented hinge AttachParent disagrees with exact component proof',
                         expected=expected_parent, actual=reference)
                counts['parent'] += 1
            elif re.match(r'\s*RelativeLocation=', line):
                _vector(_native_location(line), part['location'],
                        'Native reparented hinge location disagrees with structured evidence',
                        tolerance=0.000051, component=component_name)
                counts['location'] += 1
            elif re.match(r'\s*RelativeRotation=', line):
                _vector(_native_rotation(line), part['rotation'],
                        'Native reparented hinge rotation disagrees with structured evidence',
                        tolerance=0.000051, component=component_name)
                counts['rotation'] += 1
            elif re.match(r'\s*RelativeScale3D=', line):
                _vector(_native_scale(line), part['scale'],
                        'Native reparented hinge scale disagrees with structured evidence',
                        tolerance=0.000051, component=component_name)
                counts['scale'] += 1
            else:
                rows.append(line)
        item['body'] = rows
    _same(counts['mesh'], 1, 'Expected one explicit reparented hinge mesh reference')
    _same(counts['parent'], 1, 'Expected one explicit reparented hinge AttachParent reference')
    _require(all(counts[key] <= 1 for key in ('location', 'rotation', 'scale')),
             'Duplicate reparented hinge Native local transform', counts=counts)
    return _render(node)


def _reparent_world(actual, hinge, label):
    _same(set(actual), set(hinge), 'Reparented hinge world transform schema differs', actor=label)
    _vector(actual['translation'], hinge['translation'],
            'Reparented hardware world location does not match DoorHinge',
            tolerance=1e-8, actor=label)
    _require(math.dist(actual['translation'], hinge['translation']) < 1e-8,
             'Reparented hardware world translation distance exceeds strict bound', actor=label)
    _same(actual['scale'], hinge['scale'], 'Reparented hardware world scale does not match DoorHinge', actor=label)
    left, right = actual['rotation_quaternion_xyzw'], hinge['rotation_quaternion_xyzw']
    _require(len(left) == len(right) == 4
             and all(isinstance(x, (int, float)) and math.isfinite(x) for x in left+right),
             'Invalid reparented hardware world quaternion', actor=label)
    error = min(max(abs(x-y) for x, y in zip(left, right)),
                max(abs(x+y) for x, y in zip(left, right)))
    _require(error < 1e-12, 'Reparented hardware world rotation does not match DoorHinge',
             actor=label, quaternion_max_abs_error=error)


def _native_compare(left, right, label, before_record, after_record):
    if left != right:
        diff = ''.join(list(difflib.unified_diff(left.splitlines(keepends=True),
                                               right.splitlines(keepends=True),
                                               fromfile='before', tofile='after', n=3))[:80])
        raise AssertionError(dict(message='Unexpected Native difference after explicit closure allowances',
                                  actor=label, before=before_record['file'],
                                  after=after_record['file'], diff=diff))


def verify(before, after, plan):
    """Return a passed preservation report, or raise with a specific mismatch.

    This function requires all baseline and fresh after Native files to remain
    available.  It intentionally fails on additional changes produced by a
    Blueprint compile, instead of silently expanding the modification scope.
    """
    door_rows = plan['doors']
    hinge_rows = plan['moving_hinges']
    doors = {row['label']: set(row['changed_components']) for row in door_rows}
    hinges = {row['label']: row['mesh'] for row in hinge_rows}
    _require(all(isinstance(row.get('reparent_to_hinge', False), bool) for row in hinge_rows),
             'reparent_to_hinge must be an explicit boolean')
    reparents = {row['label']: row for row in hinge_rows if row.get('reparent_to_hinge', False)}
    _require(not reparents or len(reparents) == 11,
             'Moving hinge parent correction must name exactly eleven Actors', count=len(reparents))
    _same(len(doors), len(door_rows), 'Duplicate planned door Actor')
    _same(len(hinges), len(hinge_rows), 'Duplicate planned moving hinge Actor')
    _require(not set(doors) & set(hinges), 'Door and moving hinge plan labels overlap')
    _same(before['actor_count'], after['actor_count'], 'Actor count changed')
    _same(set(before['actors']), set(after['actors']), 'Existing Actor labels changed')
    _same(before['actor_count'], len(before['actors']), 'Baseline Actor count disagrees')
    targets = set(doors) | set(hinges)
    _require(targets <= set(before['actors']), 'Plan contains nonexistent Actor',
             labels=sorted(targets-set(before['actors'])))
    reparent_paths = {}
    for label, row in reparents.items():
        door = row['door']
        _require(door in doors and label == door+'_MovingHinges',
                 'Reparent plan must target its own planned hotel door', actor=label, door=door)
        hinge_key = door+'::DoorHinge'
        _require(hinge_key in before['exact_scene_components'] and hinge_key in after['exact_scene_components'],
                 'Reparent plan door has no DoorHinge', actor=label, door=door)
        opening_parent = before['exact_scene_components'][hinge_key]['parent']
        _require(opening_parent is not None and opening_parent.endswith('.OpeningRoot'),
                 'DoorHinge must originally attach to its door OpeningRoot', actor=label)
        expected_parent = opening_parent.rsplit('.', 1)[0]+'.DoorHinge'
        if 'expected_parent' in row:
            _same(row['expected_parent'], expected_parent,
                  'Planned expected_parent is not the matching door DoorHinge', actor=label)
        component = _components(before['actors'][label])
        _same(len(component), 1, 'Reparented hinge must have a sole component', actor=label)
        name = next(iter(component))
        old_geo = before['exact_scene_components'][label+'::'+name]
        _same(old_geo['parent'], opening_parent,
              'Parent correction only allowed for originally OpeningRoot-mounted hardware', actor=label)
        reparent_paths[label] = (opening_parent, expected_parent)
    for key in ('lights', 'full_light_properties', 'actor_properties'):
        _same(before[key], after[key], 'Protected top-level snapshot field changed', field=key)
    changed_component_count = 0
    for label, old in before['actors'].items():
        new = after['actors'][label]
        if label not in targets:
            _same(new, old, 'Non-target Actor state changed', actor=label)
            continue
        old_c, new_c = _components(old), _components(new)
        expected = deepcopy(old)
        if label in doors:
            changed = doors[label]
            _require(changed and changed <= (_SWING | _SLIDER),
                     'Plan component outside explicit leaf/handle/collision/glass allowance',
                     actor=label, components=sorted(changed))
            _require(changed <= set(old_c), 'Planned existing component not found', actor=label)
            _require(STOPS_NAME not in old_c, 'Baseline already contains DoorStops', actor=label)
            _same(set(new_c), set(old_c) | {STOPS_NAME},
                  'Door existing components changed', actor=label)
            _stops(new_c[STOPS_NAME], label)
            for c in expected['components']:
                if c['name'] in changed:
                    _same(c['class'], STATIC_MESH_COMPONENT,
                          'Changed component must be StaticMeshComponent', actor=label, component=c['name'])
                    _require(c['parent'] in ('DoorHinge', 'LeftSlider', 'RightSlider'),
                             'Changed child has unexpected parent', actor=label, component=c['name'])
                    c['location'] = _shift(c['location'])
            # Components are sorted by name in stable_actor; check after adding.
            expected['components'].append(deepcopy(new_c[STOPS_NAME]))
            expected['components'].sort(key=lambda c: c['name'])
            changed_component_count += len(changed)
        else:
            _same(old['class'], '/Script/Engine.StaticMeshActor', 'Moving hinge Actor class changed', actor=label)
            _same(set(new_c), set(old_c), 'Moving hinge components changed', actor=label)
            _same(len(old_c), 1, 'Moving hinge must have a sole mesh component', actor=label)
            expected['components'][0]['mesh'] = hinges[label]
            if label in reparents:
                expected['components'][0].update(parent='DoorHinge', location=[0.0, 0.0, 0.0],
                                                  rotation=[0.0, 0.0, 0.0], scale=[1.0, 1.0, 1.0])
                # Actor location/rotation are derived from its sole root. The
                # exact component loop below proves the new root is coincident
                # with this same door's DoorHinge before accepting either.
                expected['location'] = deepcopy(new['location'])
                expected['rotation'] = deepcopy(new['rotation'])
        _same(new, expected, 'Target Actor state exceeded explicit door closure plan', actor=label)

    old_geo, new_geo = before['exact_scene_components'], after['exact_scene_components']
    additions = {label+'::'+STOPS_NAME for label in doors}
    _require(not additions & set(old_geo), 'Baseline already contains DoorStops geometry')
    _same(set(new_geo), set(old_geo) | additions, 'Exact component inventory changed')
    for key, old in old_geo.items():
        label, component = key.split('::', 1)
        new = new_geo[key]
        expected = deepcopy(old)
        if label in doors and component in doors[label]:
            _require(not old['local']['absolute_location'],
                     'Changed component uses absolute location', component=key)
            expected['local']['relative_location'] = _shift(old['local']['relative_location'])
            _vector(new['local']['relative_location'], expected['local']['relative_location'],
                    'Exact local displacement is not Y -5 cm', component=key)
            # Copy only after verifying the numeric difference, to preserve the
            # exact comparison for every other local property.
            expected['local']['relative_location'] = new['local']['relative_location']
            parent_name = old['parent'].rsplit('.', 1)[-1]
            parent_key = label+'::'+parent_name
            _require(parent_key in old_geo, 'Changed component parent missing', component=key)
            _changed_world(old['world_transform'], new['world_transform'],
                           old_geo[parent_key]['world_transform'], label, component)
            expected['world_transform'] = new['world_transform']
        elif label in hinges:
            expected['mesh'] = hinges[label]
            if label in reparents:
                door = reparents[label]['door']
                expected['parent'] = reparent_paths[label][1]
                expected['local']['relative_location'] = [0.0, 0.0, 0.0]
                expected['local']['relative_rotation'] = [0.0, 0.0, 0.0]
                expected['local']['relative_scale3d'] = [1.0, 1.0, 1.0]
                hinge_world = new_geo[door+'::DoorHinge']['world_transform']
                _reparent_world(new['world_transform'], hinge_world, label)
                _same(after['actors'][label]['location'],
                      [round(x, 4) for x in hinge_world['translation']],
                      'Reparented Actor location does not match its verified root world location', actor=label)
                expected['world_transform'] = deepcopy(new['world_transform'])
        _same(new, expected, 'Exact existing component properties changed', component=key)
    for label in doors:
        _stops(new_geo[label+'::'+STOPS_NAME], label, exact=True)

    old_native, new_native = before['full_existing_actor_native'], after['full_existing_actor_native']
    _same(set(old_native), set(before['actors']), 'Baseline Native export inventory incomplete')
    _same(set(new_native), set(old_native), 'Fresh Native export inventory changed')
    for label, record in old_native.items():
        new_record = new_native[label]
        if label not in targets:
            _same(new_record['native_text_sha256'], record['native_text_sha256'],
                  'Non-target full Native serialization changed', actor=label,
                  before_file=record['file'], after_file=new_record['file'])
            continue
        left, right = _native(record), _native(new_record)
        if label in doors:
            left = _canonical_door_native(left, before['actors'][label], doors[label], False)
            right = _canonical_door_native(right, after['actors'][label], doors[label], True)
        else:
            original_mesh = before['actors'][label]['components'][0]['mesh']
            if label in reparents:
                left = _canonical_reparented_hinge_native(left, before['actors'][label], original_mesh,
                                                          reparent_paths[label][0])
                right = _canonical_reparented_hinge_native(right, after['actors'][label], hinges[label],
                                                           reparent_paths[label][1])
            else:
                left = _canonical_hinge_native(left, original_mesh)
                right = _canonical_hinge_native(right, hinges[label])
        _native_compare(left, right, label, record, new_record)
    return dict(passed=True, actor_count=before['actor_count'], hotel_doors=len(doors),
                existing_child_components_shifted_local_y_minus_5_cm=changed_component_count,
                door_stops_components_added=len(doors), moving_hinge_meshes_replaced=len(hinges),
                moving_hinge_parent_corrections=len(reparents),
                other_actors_native_exact=before['actor_count']-len(targets),
                existing_actor_identities_materials_collision_visibility_preserved=True,
                unchanged_actor_and_door_transforms_preserved=True,
                reparented_moving_hinge_actor_transforms_derived_from_matching_door_hinge=True,
                hinge_and_slider_saved_poses_preserved=True,
                target_native_changes_limited_to_explicit_locations_stops_hinge_mesh_and_listed_parent_corrections=True,
                explicit_override_representation_normalized_with_numeric_proof=True,
                lights_and_user_actor_properties_preserved=True)
