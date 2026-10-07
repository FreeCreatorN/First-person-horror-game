"""Fresh saved-map audits for the incremental hotel polish; never save a map."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
WORK = ROOT / 'Saved/CodexOutputs/HotelPolish_20261005'
TAG = 'HotelPolish_20261005'
POSITION_TOLERANCE_CM = .05


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, value):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xyz(value):
    return [float(getattr(value, axis)) for axis in ('x', 'y', 'z')]


def asset_path(value):
    if value is None:
        return None
    path = value if isinstance(value, str) else value.get_path_name()
    return path.split('.', 1)[0]


def near(actual, expected, tolerance=POSITION_TOLERANCE_CM):
    return len(actual) == len(expected) and all(
        math.isfinite(float(a)) and math.isfinite(float(b)) and abs(float(a) - float(b)) <= tolerance
        for a, b in zip(actual, expected))


def mesh_component(actor):
    components = [c for c in actor.get_components_by_class(unreal.StaticMeshComponent) if c.static_mesh]
    if len(components) != 1:
        raise RuntimeError('Expected one visual mesh on ' + actor.get_actor_label())
    return components[0]


def no_collision(component):
    return (component.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
            and str(component.get_collision_profile_name()) == 'NoCollision')


def yaw_90(actor):
    rotation = actor.get_actor_rotation()
    yaw_difference = (float(rotation.yaw) - 90. + 180.) % 360. - 180.
    return near([rotation.pitch, yaw_difference, rotation.roll], [0., 0., 0.], .01)


def main():
    report = {'passed': False, 'checks': [], 'errors': [], 'map_sha256': None,
              'scope': 'Fresh saved-map geometry, material graph, labels and preservation audits; no map saves.'}

    def check(name, passed, **details):
        report['checks'].append(dict(details, name=name, passed=bool(passed)))
        if not passed:
            report['errors'].append(name)
        return bool(passed)

    try:
        build = read(WORK / 'BuildReport.json')
        spec = build['hotel_polish']
        target = build['target_level']
        map_file = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
        expected_hash = sha(map_file)
        report.update(map_sha256=expected_hash, target_level=target)
        if not check('saved_map_matches_build', expected_hash == build['map_sha256'] == spec['map_sha256']):
            raise RuntimeError('Polish reports do not describe the current saved map')

        # Compare the persisted state before collision/opening probes temporarily
        # change component state in memory. Those probes never save the map.
        assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(target)
        persisted_actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        import PolishOldTownHotel as polish
        preservation = polish.check_preservation(persisted_actors, build)
        check('fresh_preservation', preservation['passed'] and preservation['map_sha256'] == expected_hash)

        # This loads the persisted target and reruns every existing hotel,
        # architecture, lighting, triangle, collision and opening audit.
        import VerifyOldTownHotelReview as base_verification
        base_verification.WORK = WORK
        base_verification.main()
        base_result = read(WORK / 'FreshHotelVerification.json')
        check('base_fresh_audits', base_result['passed'] and base_result['map_sha256'] == expected_hash)
        actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        check('fresh_target_world', world is not None and world.get_path_name().startswith(target + '.'))
        by_label = defaultdict(list)
        for actor in actors:
            by_label[actor.get_actor_label()].append(actor)
        check('all_actor_labels_unique', all(len(group) == 1 for group in by_label.values()))
        check('saved_actor_count', len(actors) == build['actor_count'], actual=len(actors))

        def actor(label):
            matches = by_label.get(label, [])
            if len(matches) != 1:
                raise RuntimeError('Missing or duplicated actor label: ' + label)
            return matches[0]

        materials = spec['materials']
        material_names = Counter(row['name'] for row in materials)
        check('three_polish_materials', material_names == Counter({'Linen': 1, 'Plaque': 1, 'Letters': 1}))
        material_by_name = {row['name']: row for row in materials}
        check('material_assets_distinct', len({asset_path(row['asset']) for row in materials}) == 3)
        editing = unreal.MaterialEditingLibrary
        for row in materials:
            material = unreal.load_asset(row['asset'])
            prefix = 'material:' + row['name']
            check(prefix + ':is_material', isinstance(material, unreal.Material))
            if not isinstance(material, unreal.Material):
                continue
            color_node = editing.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
            rough_node = editing.get_material_property_input_node(material, unreal.MaterialProperty.MP_ROUGHNESS)
            metal_node = editing.get_material_property_input_node(material, unreal.MaterialProperty.MP_METALLIC)
            emissive_node = editing.get_material_property_input_node(material, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
            check(prefix + ':base_color_constant', isinstance(color_node, unreal.MaterialExpressionConstant3Vector))
            if isinstance(color_node, unreal.MaterialExpressionConstant3Vector):
                color = color_node.get_editor_property('constant')
                actual = [float(color.r), float(color.g), float(color.b)]
                check(prefix + ':base_color_value', near(actual, row['color'], .00001), actual=actual, expected=row['color'])
            for field, node in (('roughness', rough_node), ('metallic', metal_node)):
                check(prefix + ':' + field + '_constant', isinstance(node, unreal.MaterialExpressionConstant))
                if isinstance(node, unreal.MaterialExpressionConstant):
                    value = float(node.get_editor_property('r'))
                    check(prefix + ':' + field + '_value', math.isfinite(value) and 0 <= value <= 1
                          and abs(value - float(row[field])) <= .00001, actual=value, expected=row[field])
            check(prefix + ':emissive_unconnected', emissive_node is None)

        mattress_labels = {row['actor'] for row in build['hotel_plan']['placed_boxes'] if row['role'] == 'GuestMattress'}
        overrides = spec['material_overrides']
        check('mattress_override_coverage', len(overrides) == len(mattress_labels) == 24
              and Counter(row['actor'] for row in overrides) == Counter(mattress_labels))
        linen_path = asset_path(material_by_name['Linen']['asset'])
        for row in overrides:
            target_actor = actor(row['actor'])
            components = [c for c in target_actor.get_components_by_class(unreal.StaticMeshComponent)
                          if c.get_name() == row['component']]
            prefix = 'override:' + row['actor']
            check(prefix + ':component_name', len(components) == 1, component=row['component'])
            check(prefix + ':linen_declared', asset_path(row['material']) == linen_path)
            if len(components) == 1:
                check(prefix + ':material', asset_path(components[0].get_material(0)) == asset_path(row['material']))

        rooms = build['hotel_plan']['rooms']
        expected_rooms = Counter(str(room['id']) for room in rooms)
        labels = spec['room_labels']
        check('unique_room_number_coverage', len(rooms) == len(labels) == 24
              and all(count == 1 for count in expected_rooms.values())
              and Counter(str(row['room_id']) for row in labels) == expected_rooms)
        check('number_meshes_distinct', len({asset_path(row['asset']) for row in labels}) == 24)
        check('plate_actor_labels_distinct', len({row['plate_actor'] for row in labels}) == 24)
        check('number_actor_labels_distinct', len({row['number_actor'] for row in labels}) == 24)
        placed_by_actor = defaultdict(list)
        for row in build['hotel_plan']['placed_boxes']:
            placed_by_actor[row['actor']].append(row)
        letters_path = asset_path(material_by_name['Letters']['asset'])
        plaque_path = asset_path(material_by_name['Plaque']['asset'])
        from PolishOldTownDetails import actor_bounds
        for row in labels:
            prefix = 'room:' + str(row['room_id'])
            plaque = actor(row['plate_actor'])
            plaque_component = mesh_component(plaque)
            declared_boxes = placed_by_actor[row['plate_actor']]
            check(prefix + ':plaque_report', len(declared_boxes) == 1 and
                  declared_boxes[0]['role'] == 'RoomNumberPlaque' and not declared_boxes[0]['collision']
                  and str(declared_boxes[0]['room_id']) == str(row['room_id']))
            if len(declared_boxes) == 1:
                bounds = actor_bounds(plaque)
                check(prefix + ':plaque_bounds', near(bounds[0], declared_boxes[0]['world_min'])
                      and near(bounds[1], declared_boxes[0]['world_max']), actual=bounds)
            check(prefix + ':plaque_no_collision', no_collision(plaque_component))
            check(prefix + ':plaque_material', asset_path(plaque_component.get_material(0)) == plaque_path)
            number = actor(row['number_actor'])
            component = mesh_component(number)
            mesh = component.static_mesh
            check(prefix + ':number_asset', asset_path(mesh) == asset_path(row['asset']))
            metadata_hash = str(unreal.EditorAssetLibrary.get_metadata_tag(mesh, 'OldTownHotelLabelSourceSHA256'))
            check(prefix + ':source_hash', metadata_hash == row['source_sha256'] and
                  len(row['source_sha256']) == 64, actual=metadata_hash)
            size = [2. * value for value in xyz(mesh.get_bounds().box_extent)]
            check(prefix + ':imported_dimensions', near(size, row['dimensions_cm'], .02), actual=size)
            check(prefix + ':readable_mesh_size', 0 < size[0] < 32 and abs(size[1] - .25) < .02
                  and abs(size[2] - 12.) < .02 and abs(float(row['text_height_cm']) - 12.) < .001, actual=size)
            check(prefix + ':location', near(xyz(number.get_actor_location()), row['world_location_cm']))
            rotation = number.get_actor_rotation()
            check(prefix + ':orientation', yaw_90(number) and near(row['front_normal'], [-1., 0., 0.], .001),
                  actual_rotation=[float(rotation.pitch), float(rotation.yaw), float(rotation.roll)])
            check(prefix + ':unit_scale', near(xyz(number.get_actor_scale3d()), [1., 1., 1.], .001))
            check(prefix + ':number_no_collision', no_collision(component))
            check(prefix + ':number_material', component.get_num_materials() > 0 and all(
                asset_path(component.get_material(slot)) == letters_path for slot in range(component.get_num_materials())))

        reception = spec['reception_sign']
        reception_actor = actor(reception['actor'])
        reception_component = mesh_component(reception_actor)
        check('reception:asset', asset_path(reception_component.static_mesh) == asset_path(reception['asset'])
              == asset_path(build['hotel_plan']['sign']['asset']))
        check('reception:location', near(xyz(reception_actor.get_actor_location()), reception['world_location_cm']))
        check('reception:scale', near(xyz(reception_actor.get_actor_scale3d()), reception['scale'], .001)
              and near(reception['scale'], [.85, .85, .85], .001))
        rotation = reception_actor.get_actor_rotation()
        check('reception:orientation', yaw_90(reception_actor),
              actual_rotation=[float(rotation.pitch), float(rotation.yaw), float(rotation.roll)])
        check('reception:no_collision', no_collision(reception_component))
        check('reception:material', asset_path(reception_component.get_material(0)) == asset_path(reception['material'])
              == letters_path)

        new_labels = spec['new_actor_labels']
        required_new = {row[key] for row in labels for key in ('plate_actor', 'number_actor')} | {reception['actor']}
        check('new_actor_manifest_unique', len(new_labels) == len(set(new_labels)) == 50)
        check('new_actor_required_coverage', required_new <= set(new_labels))
        for label in new_labels:
            check('new_actor:' + label + ':tag', TAG in [str(tag) for tag in actor(label).get_editor_property('tags')])
        cameras = spec['review_cameras']
        check('review_camera_count', len(cameras) == len(set(cameras)) == 4)
        check('review_cameras_in_build', set(cameras) <= set(build['hotel_openings_review_cameras']))
        for label in cameras:
            check('review_camera:' + label, isinstance(actor(label), unreal.CameraActor))

        user_light = actor('PointLight')
        check('user_light:type', isinstance(user_light, unreal.PointLight))
        light = user_light.get_component_by_class(unreal.PointLightComponent)
        check('user_light:position', near(xyz(light.get_world_location()), [6090., 1690., 1460.], .001))
        check('user_light:intensity', abs(float(light.get_editor_property('intensity')) - 160.) < .001)
        check('user_light:units', light.get_editor_property('intensity_units') == unreal.LightUnits.CANDELAS)

        # The independent baseline includes all pre-existing actor/component
        # values and shared asset file hashes, allowing only listed overrides.
        check('persisted_map_unchanged', sha(map_file) == expected_hash)
        for path, expected in build['protected_map_sha256'].items():
            check('protected_map:' + Path(path).name, sha(Path(path)) == expected)
        report['statistics'] = {'checks': len(report['checks']), 'failed_checks': len(report['errors']),
                                'room_labels': len(labels), 'material_overrides': len(overrides),
                                'new_actors': len(new_labels), 'review_cameras': len(cameras)}
        report['passed'] = not report['errors']
        write('HotelPolishAudit.json', report)
        if not report['passed']:
            raise RuntimeError('Hotel polish audit failed: ' + ', '.join(report['errors'][:15]))
        applied = read(WORK / 'PolishApplied.json')
        if not (applied['passed'] and applied['map_sha256'] == expected_hash):
            raise RuntimeError('PolishApplied does not match the verified saved map')
        applied['fresh_audits_pending'] = False
        write('PolishApplied.json', applied)
        unreal.log('OLDTOWN_HOTEL_POLISH_FRESH_PASS ' + expected_hash)
        return report
    except Exception:
        report['passed'] = False
        report['failure'] = traceback.format_exc()
        write('HotelPolishAudit.json', report)
        write('HotelPolishFailure.json', {'passed': False, 'map_sha256': report['map_sha256'],
                                        'errors': report['errors'], 'traceback': report['failure']})
        raise


if __name__ == '__main__':
    main()
