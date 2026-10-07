"""Replace only the hotel shell/interior, with backed-up street preservation."""
import hashlib
import json
import math
import shutil
import sys
import traceback
from copy import deepcopy
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
from PolishOldTownHotel import actor_state, shared_asset_hashes, sha
from OldTownHotelArchitecturePlan import validate_plan, BUILDING
from OldTownOpeningSpecs import door_specs, window_specs
from BuildOldTownOpeningBlueprints import create_blueprint
from ImportOldTownBlenderFurniture import _infer_axes
from ValidateEnterableStreet import refresh_world_collision, validate_main_home

BASE = ROOT / 'Saved/CodexOutputs/StreetAccessLighting_20261005'
WORK = ROOT / 'Saved/CodexOutputs/HotelArchitecture_20261005'
SOURCE = ROOT / 'SourceArt/OldTownHotelArchitecture_20261005'
ASSETS = '/Game/Yastar/Meshes/hOUSE/HotelArchitecture_20261005'
TAG = 'HotelArchitecture_20261005'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, data):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def materials(base):
    paths = base['hotel_plan']['material_paths']
    result = {key: unreal.load_asset(paths[alias]) for key, alias in
              {'concrete': 'concrete', 'plaster': 'plaster', 'wood': 'wood',
               'green': 'green_metal', 'dark': 'dark_trim', 'linen': 'linen', 'plaque': 'plaque'}.items()}
    folder = ASSETS + '/Materials'
    unreal.EditorAssetLibrary.make_directory(folder)
    edit = unreal.MaterialEditingLibrary
    colors = {'Ceramic': [.46, .43, .35], 'Glass': [.19, .24, .20],
              'Letters': [.68, .62, .44], 'Dust': [.25, .22, .16]}
    for key, color in colors.items():
        path = folder + '/M_OTS_Arch_' + key
        m = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
        if m is None:
            m = unreal.AssetToolsHelpers.get_asset_tools().create_asset(path.rsplit('/', 1)[1], folder,
                                                                       unreal.Material, unreal.MaterialFactoryNew())
        edit.delete_all_material_expressions(m)
        c = edit.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -300, 0)
        c.set_editor_property('constant', unreal.LinearColor(*color, 1.))
        assert edit.connect_material_property(c, '', unreal.MaterialProperty.MP_BASE_COLOR)
        r = edit.create_material_expression(m, unreal.MaterialExpressionConstant, -300, 150)
        r.set_editor_property('r', .88 if key != 'Glass' else .32)
        assert edit.connect_material_property(r, '', unreal.MaterialProperty.MP_ROUGHNESS)
        edit.recompile_material(m)
        assert unreal.EditorAssetLibrary.save_loaded_asset(m, False)
        result[key.lower()] = m
    assert all(result.values())
    return result


def import_fixtures(world, mats):
    manifest = read(SOURCE / 'ImportManifest.json')
    verify = read(SOURCE / 'IndependentFBXVerification.json')
    assert verify['passed'] and verify['asset_count'] == len(manifest['assets']) == 49
    unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
    unreal.EditorAssetLibrary.make_directory(ASSETS)
    assets, rows, named = {}, [], {}
    mapping = {'Ceramic': mats['ceramic'], 'Glass': mats['glass'], 'DarkMetal': mats['dark'],
               'Wood': mats['wood'], 'Linen': mats['linen'], 'Letters': mats['letters']}
    for row in manifest['assets']:
        assert sha(SOURCE / row['file']) == row['source_sha256'], row['name']
        ui = unreal.FbxImportUI()
        for key, value in {'import_mesh': True, 'import_as_skeletal': False, 'import_animations': False,
                           'import_materials': False, 'import_textures': False,
                           'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH}.items():
            ui.set_editor_property(key, value)
        for key, value in {'combine_meshes': True, 'auto_generate_collision': False,
                           'generate_lightmap_u_vs': True, 'convert_scene': True,
                           'convert_scene_unit': True, 'import_uniform_scale': 1.}.items():
            ui.static_mesh_import_data.set_editor_property(key, value)
        task = unreal.AssetImportTask()
        for key, value in {'filename': str(SOURCE / row['file']), 'destination_path': ASSETS,
                           'destination_name': row['name'], 'automated': True, 'replace_existing': True,
                           'save': False, 'options': ui, 'factory': unreal.FbxFactory()}.items():
            task.set_editor_property(key, value)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        mesh = unreal.load_asset(ASSETS + '/' + row['name'])
        assert isinstance(mesh, unreal.StaticMesh), row['name']
        for index, slot in enumerate(mesh.static_materials):
            name = str(slot.material_slot_name)
            material = next((v for k, v in mapping.items() if k.lower() in name.lower()), None)
            assert material, name
            mesh.set_material(index, material)
        unreal.EditorAssetLibrary.set_metadata_tag(mesh, TAG + '_SourceSHA256', row['source_sha256'])
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
        assets[row['key']] = mesh
        named[row['name']] = mesh
        rows.append(dict(row, asset=mesh.get_path_name()))
    axes = _infer_axes(manifest['assets'], named)
    assert tuple(axes['order']) == (0, 1, 2) and axes['signs'][0] == axes['signs'][2] == 1, axes
    write('FixtureImportReport.json', {'passed': True, 'imports': rows, 'axes': axes})
    return assets, rows


def main():
    assert not (WORK / 'ArchitectureApplied.json').exists(), 'Already applied; verify saved map instead.'
    base = read(BASE / 'BuildReport.json')
    plan = read(WORK / 'ArchitecturePlan.json')
    assert validate_plan(plan)['passed'], 'Planning validation failed'
    target = base['target_level']
    mapfile = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    original_hash = sha(mapfile)
    assert original_hash == base['map_sha256'], 'Current map changed; inspect before applying.'
    assert all(sha(Path(p)) == h for p, h in base['protected_map_sha256'].items())
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(target)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    actors = list(sub.get_all_level_actors())
    by = {a.get_actor_label(): a for a in actors}
    assert len(actors) == len(by) == base['actor_count']
    before = WORK / 'Before'
    before.mkdir(parents=True, exist_ok=True)
    for path in [mapfile, BASE / 'BuildReport.json', BASE / 'RevisionPlan.json']:
        if not (before / path.name).exists():
            shutil.copy2(path, before / path.name)
    remove = {r['actor'] for r in base['buildings']['structural_boxes']
              if r['building'] == BUILDING and r['role'] not in ('UtilityWallMount', 'EntryFloorFill')}
    remove.update(r['actor'] for r in base['hotel_plan']['placed_boxes']
                  if r['category'] in ('hotel_interior', 'hotel_wayfinding'))
    remove.update(r['actor'] for group in ('doors', 'windows') for r in base['opening_components'][group]
                  if r['building'] == BUILDING)
    remove.update(n for n in base['hotel_polish']['new_actor_labels'] if not n.startswith('CAM_'))
    assert remove <= set(by), sorted(remove - set(by))
    baseline = {'source_map_sha256': original_hash,
                'preserved_actors': {n: actor_state(a) for n, a in by.items() if n not in remove},
                'shared_asset_sha256': shared_asset_hashes(actors), 'removed_actor_labels': sorted(remove)}
    write('PreservationBaseline.json', baseline)
    mats = materials(base)
    fixtures, imported = import_fixtures(world, mats)
    for name in sorted(remove):
        assert sub.destroy_actor(by[name]), name
    new_names = []
    cube = unreal.load_asset('/Engine/BasicShapes/Cube.Cube')

    def spawn(name, mesh, pos, role, yaw=0., scale=(1., 1., 1.), material=None, collision=False, hidden=False):
        assert name not in by and name not in new_names, name
        a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*pos),
                                      unreal.Rotator(pitch=0., yaw=yaw, roll=0.), False)
        assert a, name
        a.set_actor_label(name)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelArchitecture/' + role))
        a.set_editor_property('tags', [unreal.Name(TAG)])
        a.set_actor_scale3d(unreal.Vector(*scale))
        c = a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_static_mesh(mesh)
        if material:
            c.set_material(0, material)
        c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
        if hidden:
            c.set_editor_property('visible', False)
            c.set_editor_property('hidden_in_game', True)
            c.set_editor_property('cast_shadow', False)
        new_names.append(name)
        return a

    def world_box(row, hidden=False):
        lo, hi = row['world_min'], row['world_max']
        name = 'OTS_HotelArch_' + row['id']
        spawn(name, cube, [(lo[i]+hi[i])/2 for i in range(3)], row['role'],
              scale=[(hi[i]-lo[i])/100 for i in range(3)], material=mats[row['material']],
              collision=row['collision'], hidden=hidden)
        return dict(row, actor=name, asset=cube.get_path_name(), material_asset=mats[row['material']].get_path_name())

    plan['placed_boxes'] = [world_box(row) for row in plan['boxes']]
    plan['placed_props'] = []
    for row in plan['props']:
        mesh = fixtures[row['asset_key']]
        name = 'OTS_HotelArch_' + row['id']
        spawn(name, mesh, row['position_cm'], 'Fixtures', row['yaw'], row['scale'])
        colliders = []
        for i, (lo, hi) in enumerate(row['collision_boxes']):
            collider = dict(id=row['id']+'_Collision%d'%i, role='FixtureCollision',
                            world_min=lo, world_max=hi, material='dark', collision=True, floor=None)
            placed = world_box(collider, True)
            colliders.append(placed)
        plan['placed_props'].append(dict(row, actor=name, asset=mesh.get_path_name(), colliders=colliders))
    cache = {}

    def opening(row, is_door):
        n = row['inward']
        yaw = math.degrees(math.atan2(n[1], n[0])) - 90.
        pos = row['position_cm']
        depth = row.get('depth', 20.)
        specs = door_specs(row['width'], row['height'], row.get('hinge_side', 1), depth, 0.) if is_door else window_specs(row['width'], row['height'], depth)
        if not is_door:
            # window_specs references the outer face; plan datum is wall center.
            pos = [pos[i] - n[i]*depth/2 for i in range(3)]
        kind = 'Door' if is_door else 'Window'
        key = kind + '_%d_%d_D%d' % (row['width'], row['height'], depth)
        if is_door:
            key += '_H' + str(row.get('hinge_side', 1))
        path = '/Game/CodexGenerated/OldTown/Blueprints/Openings/BP_OTS_Arch' + key
        if path not in cache:
            cache[path] = create_blueprint(path, specs)[1]
        a = sub.spawn_actor_from_class(cache[path], unreal.Vector(*pos),
                                      unreal.Rotator(pitch=0., yaw=yaw, roll=0.), False)
        name = 'OTS_HotelArch_' + kind + '_' + row['id']
        a.set_actor_label(name)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelArchitecture/' + kind + 's'))
        a.set_editor_property('tags', [unreal.Name(TAG)])
        new_names.append(name)
        return dict(row, actor=name, asset=path, blueprint=path, components=deepcopy(specs), yaw=yaw,
                    actor_position_cm=pos)

    plan['placed_doors'] = [opening(d, True) for d in plan['doors']]
    plan['placed_windows'] = [opening(w, False) for w in plan['windows']]
    doors = {d['id']: d for d in plan['doors']}
    plan['room_labels'] = []
    for room in plan['rooms']:
        d = doors[room['door_id']]
        x, y, z = d['position_cm']
        y -= d['width']/2 + 32
        plate = world_box(dict(id='RoomPlaque_' + room['id'], role='Wayfinding',
                              world_min=[9197., y-22, z+159], world_max=[9200., y+22, z+183],
                              material='plaque', floor=room['floor'], collision=False))
        mesh = fixtures['RoomNumber_' + room['id']]
        name = 'OTS_HotelArch_RoomNumber_' + room['id']
        pos = [9196.5, y, z+165]
        spawn(name, mesh, pos, 'Wayfinding', yaw=90.)
        plan['room_labels'].append(dict(room_id=room['id'], plate_actor=plate['actor'], number_actor=name,
                                       actor=name, asset=mesh.get_path_name(), world_location_cm=pos))
    # Reuse the existing hotel lettering on the new reception wall.
    spawn('OTS_HotelArch_ReceptionLetters', unreal.load_asset(base['hotel_plan']['sign']['asset']),
          [10016., -150, 195], 'Reception', yaw=90., scale=[.75, .75, .75], material=mats['letters'])
    for row in plan.get('interior_lights', []):
        r = row['rotation']
        a = sub.spawn_actor_from_class(unreal.RectLight, unreal.Vector(*row['position_cm']),
                                      unreal.Rotator(pitch=r[0], yaw=r[1], roll=r[2]), False)
        name = 'OTS_HotelArch_' + row['id']
        a.set_actor_label(name)
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelArchitecture/SurvivingLights'))
        a.set_editor_property('tags', [unreal.Name(TAG)])
        c = a.get_component_by_class(unreal.RectLightComponent)
        c.set_mobility(unreal.ComponentMobility.MOVABLE)
        for key, value in {'intensity_units': unreal.LightUnits.LUMENS, 'intensity': row['intensity_lm'],
                           'source_width': row['source_width_cm'], 'source_height': row['source_height_cm'],
                           'attenuation_radius': row['attenuation_radius_cm'],
                           'light_color': unreal.Color(215, 222, 188, 255)}.items():
            c.set_editor_property(key, value)
        row['actor'] = name
        new_names.append(name)
    for row in plan['review_cameras']:
        rot = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*row['position']), unreal.Vector(*row['look_at']))
        a = sub.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*row['position']), rot, False)
        a.set_actor_label(row['camera'])
        a.set_folder_path(unreal.Name('OldTownSchoolStreet/HotelArchitecture/ReviewCameras'))
        a.set_editor_property('tags', [unreal.Name(TAG)])
        a.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view', row['fov'])
        new_names.append(row['camera'])
    plan.update(new_actor_labels=new_names, removed_actor_labels=sorted(remove), source_map_sha256=original_hash,
                imported_assets=imported, material_paths={k:v.get_path_name() for k,v in mats.items()})
    current = list(sub.get_all_level_actors())
    profiles = [(c, str(c.get_collision_profile_name())) for a in current
                for c in a.get_components_by_class(unreal.PrimitiveComponent)]
    refresh_world_collision(current)
    # Registering bodies toggles CollisionEnabled and changes named profiles to
    # Custom. Restore named profiles so unrelated saved actor state stays exact.
    for c, profile in profiles:
        if profile != 'Custom' and str(c.get_collision_profile_name()) != profile:
            c.set_collision_profile_name(profile)
    assert validate_main_home(current) == base['main_home']
    build = {'status': 'PENDING', 'target_level': target, 'source_map_sha256': original_hash,
             'map_sha256': original_hash, 'actor_count': len(current), 'hotel_architecture': plan,
             'protected_map_sha256': base['protected_map_sha256'],
             'hotel_openings_review_cameras': [r['camera'] for r in plan['review_cameras']],
             'previous_evidence': str(BASE / 'FinalReview.json')}
    assert len(current) == base['actor_count'] - len(remove) + len(new_names)
    write('PendingBuildReport.json', build)
    from AuditOldTownHotelArchitecture import audit
    result = audit(world, current, build)
    write('PreSaveAudit.json', result)
    assert result['passed'], 'Physical audit failed; see PreSaveAudit.json'
    assert sha(mapfile) == original_hash
    assert level.save_current_level(), 'Failed saving target map'
    build.update(status='PASS', map_sha256=sha(mapfile))
    write('BuildReport.json', build)
    write('ArchitectureApplied.json', {'passed': True, 'map_sha256': build['map_sha256'],
                                      'rooms': len(plan['rooms']), 'actor_count': len(current)})
    unreal.log('HOTEL_ARCHITECTURE_APPLY_PASS ' + build['map_sha256'])


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('ApplyFailure.json', {'passed': False, 'traceback': traceback.format_exc()})
        raise
