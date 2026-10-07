"""Fix the verified hotel preview's sign and add a reception review camera."""
import hashlib
import json
import shutil
import sys
import traceback
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
WORK = ROOT / 'Saved/CodexOutputs/HotelOpenings_20261004'
INTEGRATION = ROOT / 'Saved/CodexOutputs/HotelIntegration_20261004'
SOURCE = ROOT / 'SourceArt/OldTownHotelOpenings_20261004'
from OldTownOpeningSpecs import ASSET_ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    (WORK / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    build = json.loads((WORK / 'BuildReport.json').read_text(encoding='utf-8'))
    plan = json.loads((WORK / 'RevisionPlan.json').read_text(encoding='utf-8'))
    target = build['target_level']
    map_file = ROOT / ('Content/' + target.removeprefix('/Game/') + '.umap')
    assert sha(map_file) == build['map_sha256'], 'Preview has changed since verification'
    comparison = json.loads((INTEGRATION / 'MergeComparison.json').read_text(encoding='utf-8'))
    source_map = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
    assert sha(source_map) == comparison['current_sha256'], 'User street changed during repair'
    backup = INTEGRATION / 'BeforePreviewRepair'
    backup.mkdir(parents=True, exist_ok=True)
    for path in (map_file, WORK / 'BuildReport.json', WORK / 'RevisionPlan.json'):
        if not (backup / path.name).exists():
            shutil.copy2(path, backup / path.name)
    asset_file = ROOT / 'Content/Yastar/Meshes/hOUSE/HotelOpenings_20261004/SM_OTS_HotelSignLetters.uasset'
    if not (backup / asset_file.name).exists():
        shutil.copy2(asset_file, backup / asset_file.name)
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert level.load_level(target)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.FBX 0')
    options = unreal.FbxImportUI()
    for key, value in {'import_mesh': True, 'import_as_skeletal': False, 'import_animations': False,
                       'import_materials': False, 'import_textures': False,
                       'mesh_type_to_import': unreal.FBXImportType.FBXIT_STATIC_MESH}.items():
        options.set_editor_property(key, value)
    for key, value in {'combine_meshes': True, 'auto_generate_collision': False,
                       'generate_lightmap_u_vs': True, 'convert_scene': True,
                       'convert_scene_unit': True, 'import_uniform_scale': 1.0}.items():
        options.static_mesh_import_data.set_editor_property(key, value)
    task = unreal.AssetImportTask()
    sign_name = 'SM_OTS_HotelSignLetters'
    for key, value in {'filename': str(SOURCE / (sign_name + '.fbx')), 'destination_path': ASSET_ROOT,
                       'destination_name': sign_name, 'automated': True, 'replace_existing': True,
                       'save': False, 'options': options, 'factory': unreal.FbxFactory()}.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(ASSET_ROOT + '/' + sign_name)
    assert isinstance(mesh, unreal.StaticMesh)
    material = unreal.load_asset('/Game/Yastar/OldTownSchoolStreet/Materials/M_OTS_OldConcrete')
    assert material
    for index in range(len(mesh.static_materials)):
        mesh.set_material(index, material)
    source_sha = sha(SOURCE / (sign_name + '.fbx'))
    unreal.EditorAssetLibrary.set_metadata_tag(mesh, 'OldTownOpeningSourceSHA256', source_sha)
    bounds = mesh.get_bounds()
    size = [2 * float(getattr(bounds.box_extent, axis)) for axis in ('x', 'y', 'z')]
    assert 150 < size[0] < 450 and 0 < size[1] < 2 and abs(size[2] - 48) < .02, size
    assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    sign = by['OTS_Hotel_SignLetters']
    center = build['hotel_plan']['sign']['center_cm']
    sign.set_actor_location(unreal.Vector(center[0], center[1], center[2] - bounds.origin.z), False, False)
    sign.set_actor_rotation(unreal.Rotator(pitch=0, yaw=90, roll=0), False)
    camera_name = 'CAM_Hotel_Reception'
    position, look_at = [9230., 158., 175.], [9830., -510., 150.]
    rotation = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position), unreal.Vector(*look_at))
    camera = by.get(camera_name) or sub.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*position), rotation, False)
    camera.set_actor_label(camera_name)
    camera.set_actor_location(unreal.Vector(*position), False, False)
    camera.set_actor_rotation(rotation, False)
    camera.set_folder_path(unreal.Name('OldTownSchoolStreet/Hotel/ReviewCameras'))
    camera.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view', 80.)
    if camera_name not in build['hotel_openings_review_cameras']:
        build['hotel_openings_review_cameras'].append(camera_name)
    # The source street was saved by the user after this preview was built.
    # Preserve the old input hash as provenance and protect its current version.
    build['preview_repair'] = {'original_preview_sha256': comparison['preview_sha256'],
                               'source_street_sha256': comparison['current_sha256'],
                               'sign_dimensions_cm': size, 'sign_source_sha256': source_sha,
                               'reception_camera': camera_name}
    build['protected_map_sha256'][str(source_map)] = comparison['current_sha256']
    assert sha(source_map) == comparison['current_sha256']
    assert level.save_current_level()
    current_hash = sha(map_file)
    build['map_sha256'] = current_hash
    for section in ('architecture_seal', 'detail_polish', 'hotel_openings'):
        build[section]['map_sha256'] = current_hash
    build['hotel_openings']['new_cameras'] = len(build['hotel_openings_review_cameras'])
    build['actor_count'] = len(sub.get_all_level_actors())
    opening_import = json.loads((WORK / 'OpeningImportReport.json').read_text(encoding='utf-8'))
    for row in opening_import['imports']:
        if row['asset'].split('.')[-1] == sign_name:
            row['source_sha256'] = source_sha
    build['opening_imports'] = opening_import
    write('OpeningImportReport.json', opening_import)
    write('BuildReport.json', build)
    write('RevisionPlan.json', plan)
    write('HotelPlan.json', build['hotel_plan'])
    import VerifyOldTownHotelReview as verification
    verification.main()
    write('PreviewRepair.json', {'passed': True, 'map_sha256': current_hash, **build['preview_repair']})
    unreal.log('OTS_HOTEL_PREVIEW_REPAIR_PASS sign_height_cm={} cameras={}'.format(size[2], len(build['hotel_openings_review_cameras'])))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write('PreviewRepairFailure.json', {'passed': False, 'traceback': traceback.format_exc()})
        raise
