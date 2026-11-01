"""Read-only final validation of saved notebook assets and import evidence."""
import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

UE = Path(__file__).resolve().parent
OUT = UE.parent
PROJECT = OUT.parents[1]
CONTENT = PROJECT/'Content'
ROOT = '/Game/Yastars/Mesh/Notebook'
TARGET = CONTENT/'Yastars'/'Mesh'/'Notebook'
result = {'success': False, 'checked_utc': datetime.now(timezone.utc).isoformat(), 'target_root': ROOT}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


try:
    model = read(OUT/'model_report.json')
    report = read(UE/'ue_import_report.json')
    completion = read(UE/'ue_import_completion.json')
    reloaded = read(UE/'ue_reload_report.json')
    reload_completion = read(UE/'ue_reload_completion.json')
    assert report['success'] and completion['success'] and completion['normal_zero_exit']
    assert completion['exit_code'] == 0 and completion['execution_mode'] == 'exclusive_editor'
    assert report['run_id'] == completion['run_id'] and report['editor_pid'] == completion['editor_pid']
    assert report['target_root'] == completion['target_root'] == ROOT
    assert report['import_script_sha256'] == completion['script_sha256'] == sha(UE/'import_ue.py')
    assert completion['report_sha256'] == sha(UE/'ue_import_report.json')
    assert utc(completion['started_utc']) <= utc(report['started_utc']) <= utc(report['completed_utc']) <= utc(completion['completed_utc'])
    assert completion['fresh_report_verified'] and completion['material_compile_failure_log_count'] == 0
    assert reloaded['success'] and reload_completion['success'] and reload_completion['normal_zero_exit']
    assert reload_completion['exit_code'] == 0 and reloaded['editor_pid'] == reload_completion['editor_pid']
    assert reloaded['editor_pid'] != report['editor_pid']
    assert reloaded['script_sha256'] == reload_completion['script_sha256'] == sha(UE/'verify_persisted_ue.py')
    assert reloaded['import_report_sha256'] == sha(UE/'ue_import_report.json')
    assert reload_completion['report_sha256'] == sha(UE/'ue_reload_report.json')
    assert utc(completion['completed_utc']) <= utc(reload_completion['started_utc']) <= utc(reloaded['started_utc']) <= utc(reloaded['completed_utc']) <= utc(reload_completion['completed_utc'])
    assert reloaded['read_only'] and reloaded['assets_saved'] == reloaded['actors_spawned'] == 0
    assert reloaded['package_files_unchanged'] and reloaded['protected_content_unchanged']
    assert reloaded['page_texture_overrides_persisted'] == 32 and reloaded['mesh_geometry_and_materials_persisted']
    assert len(reloaded['blueprints']) == 2 and len(reloaded['clips']) == 18
    assert not report['existing_target_packages'] and not report['existing_target_files']
    assert report['fbx_backend_flag_during_import'] == 0 and report['fbx_backend_flag_restored']
    assert report['same_world_object'] and report['world_before'] == report['world_after']
    assert report['world_before'].startswith('/Engine/Maps/Entry')
    assert report['source_preflight_passed'] and report['source_files_unchanged'] and report['protected_content_unchanged']
    assert not any(report[key] for key in ('actors_spawned','map_save_executed','level_load_executed','asset_delete_executed','asset_or_map_rename_executed','imported_cameras','imported_lights','emissive_connections'))
    assert report['actual_compressed_bone_poses_verified']
    assert report['source_marker_bone_locations_verified']
    assert set(report['poses']) == set(model['markers']) and len(report['poses']) >= 3
    for label, sample in report['poses'].items():
        marker = model['markers'][label]
        frame = marker['frame'] if isinstance(marker, dict) else marker
        assert sample['frame'] == frame and abs(sample['seconds']-(frame-model['frame_start'])/model['fps']) < 1e-7
        assert sample['bones']
        for bone, expected in model['source_marker_bone_locations_cm'][label].items():
            assert max(abs(a-b) for a,b in zip(sample['bones'][bone]['translation'],expected)) <= .02
    mesh = report['assets']['SK_Notebook']
    assert mesh['triangles'] == model['triangles'] and mesh['bones'] == len(model['bones'])
    assert not mesh['remove_degenerates'] and len(mesh['materials']) == len(model['material_slots'])
    assert mesh['bounds_extensions_cm'] == {'positive':[0.,0.,16.],'negative':[15.,0.,0.]}
    assert max(abs(a-b) for a,b in zip(mesh['extended_dimensions_cm'],[mesh['dimensions_cm'][0]+15.,mesh['dimensions_cm'][1],mesh['dimensions_cm'][2]+16.])) <= .02
    for slot, material_path in zip(model['material_slots'], mesh['materials']):
        target_name = 'MI_'+slot[2:] if slot.startswith('M_Notebook_Page') and slot != 'M_Notebook_PageEdges' else slot
        assert material_path == ROOT+'/Materials/'+target_name+'.'+target_name
    animation = report['assets']['A_Notebook_FullCycle']
    assert abs(animation['seconds']-(model['frame_end']-model['frame_start'])/model['fps']) <= .001
    assert report['independent_clip_count'] == len(model['clips']) == 18
    assert set(report['clip_pose_comparisons']) == {clip['name'] for clip in model['clips']}
    for clip in model['clips']:
        imported = report['assets'][clip['name']]
        assert abs(imported['seconds']-clip['seconds']) <= .001
        assert imported['source_frame_start'] == clip['frame_start'] and imported['source_frame_end'] == clip['frame_end']
        comparisons = report['clip_pose_comparisons'][clip['name']]
        assert set(comparisons) == {'start','end'}
        for endpoint, frame in (('start',clip['frame_start']),('end',clip['frame_end'])):
            sample = comparisons[endpoint]
            assert sample['frame'] == frame
            assert abs(sample['full_cycle_seconds']-(frame-model['frame_start'])/model['fps']) < 1e-7
            assert sample['max_translation_error_cm'] <= .02 and sample['max_rotation_dot_error'] <= .0001
            assert set(sample['bones']) == set(model['bones'])
    for name, playing in (('BP_Notebook',False),('BP_Notebook_Demo',True)):
        asset = report['assets'][name]
        assert asset['playing'] == playing and not asset['looping'] and asset['position_seconds'] == 0.
        assert asset['mesh'] == mesh['asset'] and asset['animation'] == animation['asset']
        assert asset['fixed_skeletal_bounds']
        assert asset['collision_profile'] == ('NoCollision' if playing else 'BlockAll')
        assert max(abs(a*.5-b) for a,b in zip(mesh['dimensions_cm'],asset['collision_half_extents_cm'])) <= .001
    collision = report['collision']
    assert collision['implementation'] == 'Blueprint BoxComponent' and collision['boxes_per_blueprint'] == 1
    assert collision['closed_book_proxy'] and not collision['physics_asset_created'] and not collision['page_simulation']
    paths = set()
    for package, info in report['new_packages_on_disk'].items():
        path = (CONTENT/(package[6:]+'.uasset')).resolve()
        assert path.is_relative_to(TARGET) and path == Path(info['file']).resolve()
        assert path.is_file() and path.stat().st_size == info['bytes'] and sha(path) == info['sha256']
        paths.add(path)
    assert paths == {p.resolve() for p in TARGET.rglob('*.uasset')}
    assert len(paths) == report['new_package_count'] == len(report['created_assets'])
    assert not list(TARGET.rglob('*.umap'))
    for path, digest in report['source_files_sha256'].items():
        assert Path(path).resolve().is_relative_to(OUT) and sha(path) == digest
    protected = read(UE/'protected_content_sha256.json')
    current = set(CONTENT.rglob('*.umap'))
    for directory in (PROJECT/'Config', CONTENT/'Yastar'/'UI', CONTENT/'Yastar'/'Items'):
        current.update(p for p in directory.rglob('*') if p.is_file())
    assert {str(p.resolve()) for p in current} == set(protected)
    assert all(sha(path).lower() == digest.lower() for path, digest in protected.items())
    result.update(success=True, package_count=len(paths), protected_files_checked=len(protected),
                  triangles=mesh['triangles'], bones=mesh['bones'], animation_seconds=animation['seconds'],
                  compressed_pose_samples=len(report['poses']), replaceable_page_materials=32,
                  independent_clips=18, clip_endpoints_match_full_cycle=True,
                  fresh_editor_persistence_verified=True,
                  closed_collision_boxes=1, source_and_packages_sha256_verified=True)
except Exception:
    result['error'] = traceback.format_exc()
(UE/'final_verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print('NOTEBOOK_FINAL_VERIFIED', result['success'])
if not result['success']:
    print(result['error'])
    raise SystemExit(1)
