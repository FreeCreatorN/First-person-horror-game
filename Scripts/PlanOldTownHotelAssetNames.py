"""Freeze semantic private-copy names from the read-only old-town inventory.

Only this new stage's HotelNamePlan.json is written. No Unreal imports, asset
renames, package edits, source-map edits, or user-file edits are performed.
"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[1]
W = R / 'Saved/CodexOutputs/OldTownHotelNaming_20261017'
OLD = R / 'Saved/CodexOutputs/OldTownDoorReuse_20261017'
ROOT = '/Game/CodexGenerated/OldTown/'
DEST = '/Game/CodexGenerated/Hotel'
MAP = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
INPUTS = {}
CLASSES = {
    'Blueprint': ('BP', 'Blueprints'), 'StaticMesh': ('SM', 'Meshes'),
    'Material': ('M', 'Materials'), 'MaterialInstanceConstant': ('MI', 'Materials'),
    'MaterialInstance': ('MI', 'Materials'), 'Texture2D': ('T', 'Textures'),
    'TextureCube': ('T', 'Textures'), 'MaterialFunction': ('MF', 'Materials/Functions'),
    'AssetImportData': ('AID', 'ImportData'), 'PhysicsAsset': ('PHYS', 'Physics'),
    'SkeletalMesh': ('SK', 'Meshes'), 'SoundWave': ('SW', 'Audio'),
    'SoundCue': ('SC', 'Audio'), 'DataAsset': ('DA', 'Data'),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    path = Path(path).resolve()
    INPUTS[str(path)] = sha(path)
    return json.loads(path.read_text(encoding='utf-8-sig'))


def file_for(package):
    return R / ('Content/' + package.removeprefix('/Game/') + '.uasset')


def package_of(value):
    return value.split('.', 1)[0] if isinstance(value, str) and value.startswith('/Game/') else None


def short(package):
    return hashlib.sha256(package.casefold().encode('utf-8')).hexdigest()[:8]


def class_name(row):
    value = row['class_path']
    match = re.search(r'asset_name:\s*"([^"]+)"', value)
    return match.group(1) if match else value.rsplit('.', 1)[-1].rsplit('/', 1)[-1]


def semantic_text(name):
    value = re.sub(r'^(?:SM|M|MI|T|BP|MF)_', '', name)
    while re.match(r'^(?:OTS|R|RF|Real|V4|P2Prop|Mod|Arch|Street)_', value):
        value = value.split('_', 1)[1]
    value = re.sub(r'^Master_M_', '', value)
    value = re.sub(r'_[0-9a-fA-F]{8,64}$', '', value)
    value = re.sub(r'_Separated(?:_[0-9a-fA-F]+)?$', '_SurfaceOffset', value)
    value = value.replace('HotelV4_', '').replace('Callable_', '')
    value = value.replace('HotelTube', 'LampTube')
    value = re.sub(r'^Hotel_?', '', value) if value.startswith('Hotel') else value
    value = value.replace('_color', '_BaseColor').replace('_normal', '_Normal').replace('_rough', '_Roughness')
    value = re.sub(r'[^A-Za-z0-9_]+', '_', value)
    return re.sub(r'_+', '_', value).strip('_') or 'Asset'


def usage_semantic(use):
    name = use['component']; label = use['actor']; mesh = use.get('mesh_name', '')
    text = name + ' ' + mesh + ' ' + label
    tests = [
        (r'GalleryTube|Fluorescent', 'LampTube' if use['slot'] == 2 else 'LampHousing'),
        (r'StreetLamp', 'StreetLampLens' if use['slot'] == 2 else 'StreetLampHousing'),
        (r'DoorLeaf|SwingLeaf|SlidingLeaf|EntranceLeaf|ElevatorLeaf|LeftLeaf|RightLeaf', 'DoorLeaf'),
        (r'DoorJamb|DoorHeader', 'DoorFrame'),
        (r'WindowGlazing|LeftGlass|RightGlass|LeftSash|RightSash', 'WindowGlass'),
        (r'WindowFrame|WindowJamb|WindowHeader|WindowSill|MeetingRail', 'WindowFrame'),
        (r'Handle|Lever|PullHandle', 'Handle'), (r'Handrail|StairRail', 'Handrail'),
        (r'StairTread|StairRiser|FlightStep', 'StairStep'), (r'StairPost|RailPost', 'StairPost'),
        (r'StairBaseplate|Baseplate', 'Baseplate'),
        (r'BedMattress|Mattress', 'Mattress'), (r'Pillow', 'Pillow'),
        (r'Duvet|Blanket|Linen|BedSheet|Cloth', 'Bedding'), (r'BedBase', 'BedFrame'),
        (r'Washbasin|Basin', 'Basin'), (r'Toilet', 'Toilet'), (r'Shower', 'Shower'),
        (r'Faucet|Tap|Drain|Pipe', 'Plumbing'), (r'Chair|Seat', 'Seat'),
        (r'Sofa|Bench', 'Seat'), (r'Wardrobe|Cabinet|Locker', 'Cabinet'),
        (r'Desk|Table|Counter|Reception', 'Counter'), (r'Curtain', 'Curtain'),
        (r'ConcreteFloor|Floor|Landing', 'Floor'), (r'Ceiling', 'Ceiling'),
        (r'Roof|Parapet', 'Roof'), (r'Wall|Plaster', 'Wall'), (r'Column|Pillar', 'Column'),
        (r'Brick', 'Masonry'), (r'Road|Asphalt', 'Road'), (r'Sidewalk|Curb', 'Sidewalk'),
        (r'Sign|Letter|Notice|Poster', 'Sign'), (r'FrameLeft|FrameRight|FrameTop|FrameBottom', 'OpeningFrame'),
    ]
    for pattern, result in tests:
        if re.search(pattern, text, re.I):
            return result
    if mesh:
        return semantic_text(mesh).split('_', 1)[0]
    useful = semantic_text(label)
    useful = re.sub(r'^(?:Hotel|HotelV4|P2Prop|Blockout|Building|Room\d+)_*', '', useful)
    useful = re.sub(r'(?:StaticMeshComponent|DefaultSceneRoot|Component)\d*', '', useful)
    return useful.split('_', 1)[0] or 'Surface'


def main():
    output = W / 'HotelNamePlan.json'
    assert not output.exists(), 'A frozen name plan may not be overwritten'
    inventory = read(W / 'Inventory.json')
    references = read(W / 'AssetReferences.json')
    scene = read(W / 'SceneSnapshot.json')
    notes = read(W / 'WindowDesignNotes.json')
    baseline = read(W / 'ProtectedBeforeAfterRestore.json')['file_sha256']
    restored = read(W / 'LegacyCleanupRestored.json')
    ownership = read(OLD / 'OwnershipPlan.json')
    reusable = read(OLD / 'ReusableBlueprints.json')
    moved = read(R / 'Saved/CodexOutputs/OpeningRelocation_20261007/Moved.json')
    legacy = read(R / 'Saved/CodexOutputs/HotelOpenings_20261004/BuildReport.json')
    assert inventory['passed'] and references['passed'] and notes['passed'] and restored['passed']
    assert inventory['no_save_or_explicit_compile_called'] and inventory['existing_content_config_unchanged']
    map_file = R / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    assert sha(map_file) == inventory['map_sha256'] == references['map_sha256'] == baseline[str(map_file)]
    assert scene['actor_count'] == inventory['actor_count'] == 7986

    grouped, spelling, graph = defaultdict(list), {}, defaultdict(set)
    for row in references['assets']:
        package = row['package']; key = package.casefold()
        grouped[key].append(row); spelling[key] = package
        graph[key].update(p.casefold() for p in row['dependencies'] if p.startswith('/Game/'))
    reached, pending = set(), [MAP.casefold()]
    while pending:
        package = pending.pop()
        if package in reached:
            continue
        reached.add(package); pending.extend(graph.get(package, set()) - reached)
    owned_closure = sorted(p for p in reached if p.startswith(ROOT.casefold()))
    assert len(owned_closure) == 617

    old_used = {r['package'].casefold(): r for r in ownership['owned_still_used']}
    reusable_hashes = reusable['new_asset_sha256']
    relocation = {r['new'].casefold(): r for r in moved['relocations']}
    legacy_created = {r['blueprint'] for r in legacy['opening_components']['windows']}
    selected, frozen = [], []
    for key in owned_closure:
        rows = grouped[key]
        # GeneratedClass rows share their package with the primary Blueprint.
        # The memory address in a TopLevelAssetPath repr is never a class name.
        primary = [r for r in rows if r['asset_name'] == r['package'].rsplit('/', 1)[-1]]
        primary = sorted(primary or rows, key=lambda r: (class_name(r) != 'Blueprint', class_name(r) == 'BlueprintGeneratedClass', r['asset_name']))
        asset = primary[0]; package = asset['package']; cls = class_name(asset)
        source = file_for(package).resolve(); digest = sha(source)
        assert baseline[str(source)] == digest and references['file_sha256'][str(source)] == digest
        origin = None
        if key in old_used and old_used[key]['current_sha256'] == digest:
            prior = old_used[key]
            origin = dict(kind='Previously verified owned and retained package',
                manifest=str(OLD / 'OwnershipPlan.json'), field='owned_still_used',
                prior_source_origin=prior['source_origin'], current_authored_sha256_matches=True,
                proof_is_for_copy_scope_only=True)
        elif str(source) in reusable_hashes and reusable_hashes[str(source)] == digest:
            origin = dict(kind='New shared door Blueprint authored this session',
                manifest=str(OLD / 'ReusableBlueprints.json'), field='new_asset_sha256',
                recorded_sha256=digest, creation_script=str(R / 'Scripts/BuildAndProbeOldTownReusableDoors.py'))
        elif key in relocation and relocation[key]['old'] in legacy_created:
            origin = dict(kind='Explicit legacy assistant opening creation plus exact relocation chain',
                creation_manifest=str(R / 'Saved/CodexOutputs/HotelOpenings_20261004/BuildReport.json'),
                creation_field='opening_components.windows[].blueprint',
                creation_script=str(R / 'Scripts/ApplyOldTownHotelOpenings.py'),
                creation_helper=str(R / 'Scripts/BuildOldTownOpeningBlueprints.py'),
                relocation_manifest=str(R / 'Saved/CodexOutputs/OpeningRelocation_20261007/Moved.json'),
                relocation=relocation[key], current_source_sha256=digest,
                limitation='No immediate legacy creation SHA retained. Creation+relocation proves source identity for read-only private copying; this record is not a future deletion fingerprint.')
        if origin is None or cls not in CLASSES:
            frozen.append(dict(source_package=package, source_file=str(source), source_sha256=digest,
                asset_class=cls, reason='No proven allowed ownership source' if origin is None else 'Unrecognized asset class; no guessed prefix'))
            continue
        selected.append(dict(source_package=package, source_asset_name=asset['asset_name'], asset_class=cls,
            source_file=str(source), source_sha256=digest, origin=origin,
            source_object_path=package + '.' + asset['asset_name']))

    use_map, mesh_users = defaultdict(list), defaultdict(list)
    for label, actor in scene['actors'].items():
        for comp in actor.get('components', []):
            mesh = package_of(comp.get('mesh'))
            if mesh:
                mesh_users[mesh.casefold()].append(dict(actor=label, component=comp['name']))
            for slot, material in enumerate(comp.get('materials', [])):
                package = package_of(material)
                if package:
                    use_map[package.casefold()].append(dict(actor=label, component=comp['name'], slot=slot,
                        mesh=mesh, mesh_name=mesh.rsplit('/', 1)[-1] if mesh else ''))
    window_names = {p.casefold(): row['suggested_blueprint_name']
        for row in notes['window_groups'] for p in row['source_blueprints']}
    door_names = {row['current_blueprint'].casefold(): row['suggested_name']
                  for row in notes['door_naming_compatibility']}
    assert len(window_names) == len(inventory['window_class_counts']) == 8
    assert len(door_names) == len(inventory['door_class_counts']) == 10
    material_roles = {}
    for row in selected:
        if row['asset_class'] == 'Material':
            material_roles[row['source_package'].casefold()] = semantic_text(row['source_asset_name'])

    chosen = {}
    for row in selected:
        package, cls, old = row['source_package'], row['asset_class'], row['source_asset_name']
        key = package.casefold(); prefix, folder = CLASSES[cls]
        users = use_map.get(key, [])
        source_features = semantic_text(old)
        basis = 'Existing descriptive type/features, excluding obsolete generator prefixes'
        if key in window_names:
            name = window_names[key]; basis = 'Measured clear-opening window design recommendation'
        elif key in door_names:
            name = door_names[key]; basis = 'Measured same-size door recommendation; preserve mixed left/right/slider modes within its one shared Blueprint'
        elif cls == 'Blueprint' and old == 'BP_OTS_LightCircuit':
            name = 'BP_Hotel_LightCircuit'; basis = 'Existing callable light circuit contract'
        elif cls in ('MaterialInstanceConstant', 'MaterialInstance') and re.fullmatch(r'MI_.*_[0-9a-fA-F]{8,64}', old):
            roles = [material_roles[p] for p in sorted(graph.get(key, set())) if p in material_roles]
            role = roles[0] if roles else 'Surface'
            counts = Counter(usage_semantic(use) for use in users)
            if counts:
                usage_type = sorted(counts, key=lambda value: (-counts[value], value))[0]
            else:
                # Some old Blueprint defaults retain a material never rendered
                # by a current instance. Use its actual referring mesh's type.
                referents = [spelling.get(p, p).rsplit('/', 1)[-1] for p in owned_closure
                             if key in graph.get(p, set()) and any(class_name(a) == 'StaticMesh' for a in grouped[p])]
                usage_type = semantic_text(sorted(referents)[0]).split('_', 1)[0] if referents else role.split('_', 1)[0]
            source_features = usage_type + '_' + role
            name = prefix + '_Hotel_' + source_features + '_' + short(package)
            basis = 'Actual scene material component/mesh use plus parent material surface role and stable short source-package hash'
        else:
            if '/RealismRefinement_20261013/' in package and cls == 'Material':
                source_features += '_SurfaceDetail'
            if cls == 'Material' and '/SurfaceSeparation_20261009/' in package:
                source_features += '_SurfaceOffset'
            name = prefix + '_Hotel_' + source_features
        name = re.sub(r'_+', '_', name)
        assert re.fullmatch(r'[A-Za-z][A-Za-z0-9_]+', name), name
        dest = DEST + '/' + folder + '/' + name
        # Geometry/role names may intentionally repeat across real variants.
        # A source-derived suffix keeps one explicit, deterministic copy each.
        if dest.casefold() in chosen:
            name += '_' + short(package); dest = DEST + '/' + folder + '/' + name
        assert dest.casefold() not in chosen
        chosen[dest.casefold()] = package
        dest_file = file_for(dest)
        assert not dest_file.exists(), 'Destination already exists; freeze instead of overwrite: ' + str(dest_file)
        row.update(destination_package=dest, destination_asset_name=name,
            destination_object_path=dest + '.' + name, destination_file=str(dest_file),
            naming_basis=basis, semantic_features=source_features,
            actual_scene_material_use_count=len(users), scene_material_use_examples=users[:8],
            actual_scene_mesh_use_count=len(mesh_users.get(key, [])),
            mapped_owned_dependencies=sorted(spelling.get(p, p) for p in graph.get(key, set()) if p in owned_closure),
            external_dependencies_kept_read_only=sorted(spelling.get(p, p) for p in graph.get(key, set()) if p not in owned_closure))

    mapping = {r['source_package']: r['destination_package'] for r in selected}
    assert len(mapping) == len(selected) and len(set(x.casefold() for x in mapping.values())) == len(selected)
    assert all(sha(row['source_file']) == row['source_sha256'] for row in selected)
    assert all(sha(path) == digest for path, digest in INPUTS.items()), 'A plan evidence file changed during generation'
    report = dict(passed=not frozen, frozen=True, analysis_only=True, no_unreal_started=True,
        no_content_or_config_changes=True, created_utc=datetime.now(timezone.utc).isoformat(),
        target_level=MAP, source_map_sha256=inventory['map_sha256'], destination_root=DEST,
        source_package_count=len(owned_closure), planned_copy_count=len(selected), frozen_package_count=len(frozen),
        ownership_summary=dict(previous_verified_owned=sum(r['origin']['kind'].startswith('Previously') for r in selected),
            new_shared_door_blueprints=sum(r['origin']['kind'].startswith('New shared') for r in selected),
            explicitly_created_legacy_openings=sum(r['origin']['kind'].startswith('Explicit legacy') for r in selected)),
        class_counts=dict(Counter(r['asset_class'] for r in selected)),
        mappings=selected, source_to_destination=mapping, frozen_packages=frozen,
        window_blueprint_map={spelling[k]: DEST + '/Blueprints/' + v for k, v in window_names.items()},
        door_blueprint_map={spelling[k]: DEST + '/Blueprints/' + v for k, v in door_names.items()},
        light_circuit_destination=DEST + '/Blueprints/BP_Hotel_LightCircuit',
        unchanged_user_or_external_dependencies=sorted(spelling.get(p, p) for p in reached if not p.startswith(ROOT.casefold())),
        package_class_selection='Merge package records case-insensitively; prefer primary asset_name==package leaf and Blueprint over duplicate BlueprintGeneratedClass; parse TopLevelAssetPath.asset_name and ignore memory addresses.',
        copy_contract=['Copy the exact proven sources to these absent private destinations; never rename, save or alter a source asset.',
            'Remap dependencies only inside the fresh private copies, then rebind only authorized assistant-created instances in the original map.',
            'All non-OldTown user/engine/plugin dependencies retain their exact original paths and bytes.',
            'Preserve actor internal FNames, labels, component names/hierarchy, meshes, material slots, world pose, collisions, hidden flags, doors/windows states and callable-light links.',
            'Preserve native LightCircuit parent, LightStrength parameter spelling/20-or-0 behavior and existing initial 13-on/20-off state.',
            'Source-map staging mapping is added separately by root: original map to /Game/CodexGenerated/Hotel/Maps/L_Hotel_Stage. The original user map is never renamed.',
            'No deletion is authorized by this name plan. Legacy source assets and all Main/V2/user assets stay read-only.'],
        input_sha256=INPUTS,
        limitations=['The two legacy street window Blueprints have explicit creation+relocation lineage but no preserved immediate creation byte hash; this plan authorizes current-byte read-only copying only.',
            'The 605 retained entries reuse the prior accepted ownership inventory only for private copy scope; their inherited source-origin labels are not promoted to new creation or deletion proof.'])
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'], planned=len(selected), frozen=len(frozen), classes=report['class_counts'],
        report=str(output), sha256=sha(output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
