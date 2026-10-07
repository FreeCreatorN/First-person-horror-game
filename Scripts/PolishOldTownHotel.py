"""Incremental saved-hotel polish; preserve existing geometry and shared assets."""
import hashlib
import json
import re
import shutil
import sys
import traceback
from copy import deepcopy
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
BASE = ROOT / 'Saved/CodexOutputs/HotelIntegration_20261004'
WORK = ROOT / 'Saved/CodexOutputs/HotelPolish_20261005'
SOURCE = ROOT / 'SourceArt/OldTownHotelPolish_20261005'
ASSETS = '/Game/Yastar/Meshes/hOUSE/HotelPolish_20261005'
TAG = 'HotelPolish_20261005'
MATERIALS = {
    'Linen': {'color': [.62, .58, .49], 'roughness': .97, 'metallic': 0.},
    'Plaque': {'color': [.035, .075, .055], 'roughness': .78, 'metallic': 0.},
    'Letters': {'color': [.80, .72, .53], 'roughness': .72, 'metallic': 0.},
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, value):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xyz(value):
    return [round(float(getattr(value, axis)), 4) for axis in ('x', 'y', 'z')]


def actor_state(actor):
    rot = actor.get_actor_rotation()
    state = {'class': actor.get_class().get_path_name(), 'name': actor.get_name(),
             'location': xyz(actor.get_actor_location()), 'scale': xyz(actor.get_actor_scale3d()),
             'rotation': [round(float(getattr(rot, k)), 4) for k in ('pitch', 'yaw', 'roll')],
             'tags': [str(t) for t in actor.tags], 'folder': str(actor.get_folder_path()), 'components': []}
    for c in actor.get_components_by_class(unreal.SceneComponent):
        r = c.get_editor_property('relative_rotation')
        parent = c.get_attach_parent()
        row = {'name': c.get_name(), 'class': c.get_class().get_path_name(),
               'parent': parent.get_name() if parent else None,
               'location': xyz(c.get_editor_property('relative_location')),
               'rotation': [round(float(getattr(r, k)), 4) for k in ('pitch', 'yaw', 'roll')],
               'scale': xyz(c.get_editor_property('relative_scale3d')),
               'mobility': str(c.get_editor_property('mobility'))}
        if isinstance(c, unreal.StaticMeshComponent):
            row.update(mesh=c.static_mesh.get_path_name() if c.static_mesh else None,
                       materials=[c.get_material(i).get_path_name() if c.get_material(i) else None
                                  for i in range(c.get_num_materials())],
                       collision=str(c.get_collision_enabled()),
                       collision_profile=str(c.get_collision_profile_name()),
                       visible=bool(c.get_editor_property('visible')),
                       hidden_in_game=bool(c.get_editor_property('hidden_in_game')))
        if isinstance(c, unreal.PointLightComponent):
            color = c.get_editor_property('light_color')
            row.update(intensity=float(c.get_editor_property('intensity')),
                       intensity_units=str(c.get_editor_property('intensity_units')),
                       attenuation_radius=float(c.get_editor_property('attenuation_radius')),
                       light_color=[int(getattr(color, channel)) for channel in ('r', 'g', 'b', 'a')])
        state['components'].append(row)
    state['components'].sort(key=lambda row: row['name'])
    return state


def shared_asset_hashes(actors):
    paths = set()
    for a in actors:
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            objects = [c.static_mesh] + [c.get_material(i) for i in range(c.get_num_materials())]
            for obj in objects:
                if obj and obj.get_path_name().startswith('/Game/'):
                    paths.add(obj.get_path_name().split('.')[0])
    files = [ROOT / ('Content/' + p.removeprefix('/Game/') + '.uasset') for p in paths]
    assert all(path.is_file() for path in files)
    return {str(path): sha(path) for path in files}


def check_preservation(actors, build):
    baseline = read(WORK / 'PreservationBaseline.json')
    current = {a.get_actor_label(): actor_state(a) for a in actors}
    overrides = {r['actor']: r for r in build['hotel_polish']['material_overrides']}
    errors = []
    samples = []
    for label, expected in baseline['actors'].items():
        actual = deepcopy(current.get(label))
        expected = deepcopy(expected)
        # Older baseline rows used the engine Color repr, which contains a
        # process-specific pointer. Compare only its original numeric channels.
        for row in expected['components']:
            color = row.get('light_color')
            if isinstance(color, str):
                channels = dict(re.findall(r'([rgba]):\s*(\d+)', color))
                assert set(channels) == set('rgba'), 'Unrecognised baseline light color'
                row['light_color'] = [int(channels[key]) for key in ('r', 'g', 'b', 'a')]
        if label in overrides and actual:
            component = overrides[label]['component']
            for state in (actual, expected):
                for row in state['components']:
                    if row['name'] == component:
                        row.pop('materials', None)
        if actual != expected:
            errors.append(label)
            if len(samples) < 3:
                samples.append({'actor': label, 'before': expected, 'after': actual})
    added = set(current) - set(baseline['actors'])
    if added != set(build['hotel_polish']['new_actor_labels']):
        errors.append('unexpected_added_actor_set')
    altered_assets = [p for p, h in baseline['shared_asset_sha256'].items() if sha(Path(p)) != h]
    result = {'passed': not errors and not altered_assets, 'map_sha256': build['map_sha256'],
              'checked_existing_actors': len(baseline['actors']), 'allowed_material_overrides': len(overrides),
              'added_actor_count': len(added), 'actor_errors': errors, 'changed_shared_assets': altered_assets,
              'difference_samples': samples,
              'checked_shared_assets': len(baseline['shared_asset_sha256']),
              'scope': 'Existing transforms, scene components, meshes, collision, visibility, folders, tags and PointLight physical values; only listed mattress material overrides allowed.'}
    write('PreservationAudit.json', result)
    assert result['passed'], 'Preservation mismatch: {} actors, {} shared assets; see PreservationAudit.json'.format(len(errors), len(altered_assets))
    return result


def create_materials():
    folder = ASSETS + '/Materials'
    unreal.EditorAssetLibrary.make_directory(folder)
    result = {}
    editing = unreal.MaterialEditingLibrary
    for key, spec in MATERIALS.items():
        name = 'M_OTS_HotelPolish_' + key
        path = folder + '/' + name
        material = unreal.load_asset(path)
        if material is None:
            material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
        assert material and isinstance(material, unreal.Material)
        editing.delete_all_material_expressions(material)
        node = editing.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -300, 0)
        node.set_editor_property('constant', unreal.LinearColor(*spec['color'], 1.))
        assert editing.connect_material_property(node, '', unreal.MaterialProperty.MP_BASE_COLOR)
        for index, (prop, value) in enumerate(((unreal.MaterialProperty.MP_ROUGHNESS, spec['roughness']),
                                              (unreal.MaterialProperty.MP_METALLIC, spec['metallic']))):
            node = editing.create_material_expression(material, unreal.MaterialExpressionConstant, -300, 150 + index * 100)
            node.set_editor_property('r', value)
            assert editing.connect_material_property(node, '', prop)
        editing.recompile_material(material)
        unreal.EditorAssetLibrary.set_metadata_tag(material, TAG, json.dumps(spec))
        assert unreal.EditorAssetLibrary.save_loaded_asset(material, False)
        result[key] = material
    return result


def import_numbers(world, material):
    manifest = read(SOURCE / 'ImportManifest.json')
    expected = {str(f * 100 + i) for f in (2, 3, 4) for i in range(1, 9)}
    assert {str(row['room_id']) for row in manifest['assets']} == expected
    assert manifest['units'] == 'centimeters'
    unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
    ui = unreal.FbxImportUI()
    for k, v in {'import_mesh': True, 'import_as_skeletal': False, 'import_animations': False,
                 'import_materials': False, 'import_textures': False,
                 'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH}.items():
        ui.set_editor_property(k, v)
    for k, v in {'combine_meshes': True, 'auto_generate_collision': False, 'generate_lightmap_u_vs': True,
                 'convert_scene': True, 'convert_scene_unit': True, 'import_uniform_scale': 1.}.items():
        ui.static_mesh_import_data.set_editor_property(k, v)
    rows = {}
    for row in manifest['assets']:
        fbx = SOURCE / row['file']
        assert sha(fbx) == row['sha256']
        task = unreal.AssetImportTask()
        for k, v in {'filename': str(fbx), 'destination_path': ASSETS, 'destination_name': row['name'],
                     'automated': True, 'replace_existing': True, 'save': False, 'options': ui,
                     'factory': unreal.FbxFactory()}.items():
            task.set_editor_property(k, v)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        mesh = unreal.load_asset(ASSETS + '/' + row['name'])
        assert isinstance(mesh, unreal.StaticMesh)
        bounds = mesh.get_bounds()
        size = [2 * float(getattr(bounds.box_extent, a)) for a in ('x', 'y', 'z')]
        assert 0 < size[0] <= 32 and abs(size[1] - .25) < .02 and abs(size[2] - 12) < .02, (row['name'], size)
        for index in range(len(mesh.static_materials)):
            mesh.set_material(index, material)
        unreal.EditorAssetLibrary.set_metadata_tag(mesh, 'OldTownHotelLabelSourceSHA256', row['sha256'])
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
        rows[str(row['room_id'])] = dict(row, asset=mesh.get_path_name(), dimensions_cm=size)
    return rows


def main():
    build = read(BASE / 'BuildReport.json')
    target = build['target_level']
    mapfile = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    assert sha(mapfile) == build['map_sha256'], 'Saved street changed; inspect it before applying polish.'
    assert all(sha(Path(p)) == h for p, h in build['protected_map_sha256'].items())
    before = WORK / 'Before'
    before.mkdir(parents=True, exist_ok=True)
    if (WORK / 'PolishApplied.json').exists():
        raise RuntimeError('This phase has already been applied; verify instead of regenerating.')
    for path in [mapfile] + [BASE / n for n in ('BuildReport.json', 'BuildingReport.json', 'HotelPlan.json', 'RevisionPlan.json')]:
        if not (before / path.name).exists():
            shutil.copy2(path, before / path.name)
    plan = read(BASE / 'RevisionPlan.json')
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(target)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(sub.get_all_level_actors())
    assert len(actors) == build['actor_count']
    by = {a.get_actor_label(): a for a in actors}
    assert len(by) == len(actors), 'Duplicate actor labels'
    write('PreservationBaseline.json', {'actors': {name: actor_state(a) for name, a in by.items()},
                                        'shared_asset_sha256': shared_asset_hashes(actors),
                                        'map_sha256': build['map_sha256']})
    mats = create_materials()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    number_assets = import_numbers(world, mats['Letters'])
    spec = {'source_map_sha256': build['map_sha256'], 'material_overrides': [], 'room_labels': [],
            'new_actor_labels': [], 'materials': [dict(s, name=k, asset=mats[k].get_path_name()) for k, s in MATERIALS.items()],
            'generated_assets': [m.get_path_name() for m in mats.values()] + [r['asset'] for r in number_assets.values()],
            'review_cameras': ['CAM_Hotel_Room', 'CAM_Hotel_Corridor', 'CAM_Hotel_Reception', 'CAM_Hotel_RoomNumber']}
    build['hotel_polish'] = spec
    hotel = build['hotel_plan']
    hotel['material_paths'].update(linen=mats['Linen'].get_path_name(), plaque=mats['Plaque'].get_path_name())
    mattresses = [r for r in hotel['placed_boxes'] if r['role'] == 'GuestMattress']
    assert len(mattresses) == 24
    for row in mattresses:
        a = by[row['actor']]
        c = a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_material(0, mats['Linen'])
        spec['material_overrides'].append({'actor': a.get_actor_label(), 'component': c.get_name(), 'material': mats['Linen'].get_path_name()})
        row['material'] = 'linen'
    for row in hotel['boxes']:
        if row['role'] == 'GuestMattress':
            row['material'] = 'linen'

    def spawn(name, mesh, material, position, scale=(1., 1., 1.), yaw=0.):
        assert name not in by, name
        a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*position), unreal.Rotator(pitch=0., yaw=yaw, roll=0.), False)
        a.set_actor_label(name)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/Hotel/Polish'))
        a.set_editor_property('tags', [unreal.Name(TAG)])
        a.set_actor_scale3d(unreal.Vector(*scale))
        c = a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(mesh)
        c.set_material(0, material)
        c.set_collision_profile_name('NoCollision')
        spec['new_actor_labels'].append(name)
        by[name] = a
        return a

    cube = unreal.load_asset('/Engine/BasicShapes/Cube.Cube')
    for room in hotel['rooms']:
        room_id = str(room['id'])
        x, door_y, z = room['world_center']
        low, high = [9398.5, door_y - 102., z + 159.], [9400.2, door_y - 58., z + 183.]
        plate_name = 'OTS_Hotel_RoomPlaque_' + room_id
        center = [(low[i] + high[i]) * .5 for i in range(3)]
        spawn(plate_name, cube, mats['Plaque'], center, [(high[i] - low[i]) / 100 for i in range(3)])
        box = {'name': 'RoomPlaque_' + room_id, 'role': 'RoomNumberPlaque', 'world_min': low, 'world_max': high,
               'material': 'plaque', 'category': 'hotel_wayfinding', 'floor': room['floor'], 'room_id': room_id, 'collision': False}
        hotel['boxes'].append(box)
        hotel['placed_boxes'].append(dict(box, actor=plate_name, asset=cube.get_path_name()))
        source = number_assets[room_id]
        name = 'OTS_Hotel_RoomNumber_' + room_id
        position = [9398.275, door_y - 80., z + 165.]
        spawn(name, unreal.load_asset(source['asset']), mats['Letters'], position, yaw=90.)
        spec['room_labels'].append({'room_id': room_id, 'plate_actor': plate_name, 'number_actor': name,
                                   'source_sha256': source['sha256'], 'asset': source['asset'], 'dimensions_cm': source['dimensions_cm'],
                                   'world_location_cm': position, 'front_normal': [-1., 0., 0.], 'text_height_cm': 12.})
    sign = hotel['sign']
    name = 'OTS_Hotel_ReceptionLetters'
    position = [10011.6, -525., hotel['floor_z_cm'][0] + 190.]
    scale = [.85, .85, .85]
    spawn(name, unreal.load_asset(sign['asset']), mats['Letters'], position, scale, yaw=90.)
    spec['reception_sign'] = {'actor': name, 'asset': sign['asset'], 'material': mats['Letters'].get_path_name(),
                              'world_location_cm': position, 'scale': scale}
    name = 'CAM_Hotel_RoomNumber'
    position = [9160., -3420., hotel['floor_z_cm'][1] + 172.]
    look = [9400., -3400., hotel['floor_z_cm'][1] + 170.]
    rotation = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position), unreal.Vector(*look))
    camera = sub.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*position), rotation, False)
    camera.set_actor_label(name)
    camera.set_folder_path(unreal.Name('OldTownSchoolStreet/Hotel/ReviewCameras'))
    camera.set_editor_property('tags', [unreal.Name(TAG)])
    camera.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view', 62.)
    spec['new_actor_labels'].append(name)
    build['hotel_openings_review_cameras'].append(name)
    current_actors = list(sub.get_all_level_actors())
    build['actor_count'] = len(current_actors)
    assert build['actor_count'] == len(actors) + 50
    assert sha(mapfile) == spec['source_map_sha256']
    assert all(sha(Path(p)) == h for p, h in build['protected_map_sha256'].items())
    assert level.save_current_level()
    current = sha(mapfile)
    build['map_sha256'] = current
    for key in ('architecture_seal', 'detail_polish', 'hotel_openings'):
        build[key]['map_sha256'] = current
    build['hotel_openings']['new_cameras'] = len(build['hotel_openings_review_cameras'])
    spec['map_sha256'] = current
    write('BuildReport.json', build)
    write('BuildingReport.json', build['buildings'])
    write('HotelPlan.json', hotel)
    write('RevisionPlan.json', plan)
    check_preservation(current_actors, build)
    write('PolishApplied.json', {'passed': True, 'map_sha256': current, 'actor_count': build['actor_count'],
                                 'mattresses': 24, 'room_numbers': 24, 'added_actor_count': 50,
                                 'backup': str(before / mapfile.name), 'fresh_audits_pending': True})
    unreal.log('OLDTOWN_HOTEL_POLISH_APPLIED ' + current)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('PolishApplyFailure.json', {'passed': False, 'traceback': traceback.format_exc()})
        raise
