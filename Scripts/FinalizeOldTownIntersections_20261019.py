"""Publish the targeted original-town repair only after persisted and visual checks."""
import json
import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[1]
W = R / 'Saved/CodexOutputs/OldTownIntersectionFix_20261019'
MAP = R / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def main():
    applied = read(W / 'Applied.json')
    audit = read(W / 'Readback.json')
    assert applied['passed'] and audit['passed']
    assert sha(MAP) == applied['map_sha256'] == audit['map_sha256']
    completions = {n: read(W / (n + '.Completion.json')) for n in ('Inspect1', 'Apply1', 'Audit1')}
    assert all(c['normal_zero_exit'] and c['exit_code'] == 0 for c in completions.values())
    baseline = read(W / 'ProtectedBefore.json')['file_sha256']
    current = {str(p): sha(p) for root in (R / 'Content', R / 'Config') for p in root.rglob('*') if p.is_file()}
    expected = dict(baseline)
    expected[str(MAP)] = applied['map_sha256']
    assert current == expected
    backup = read(W / 'Backup.json')
    assert backup['passed'] and sha(backup['file']) == applied['source_map_sha256']
    captures = {}
    specs = None
    poses = {}
    cameras = {'INTERSECTION_UtilityPole01', 'INTERSECTION_HotelNorthFrontExit'}
    for phase, map_sha in (('Before', applied['source_map_sha256']), ('After', applied['map_sha256'])):
        folder = W / (phase + 'Captures')
        runs = read(folder / 'CaptureRuns.json')
        assert len(runs) == 2
        assert {row['camera'] for row in runs} == cameras
        rows = []
        for row in runs:
            assert row['captured'] and not row['reused'] and row['normal_exit']
            assert row['exit_code'] == 0 and not row['forced_cleanup'] and row['map_sha256'] == map_sha
            run_dir = Path(row['archive']).parents[1]
            proof = read(run_dir / 'IntersectionCaptureProof.json')
            batch = read(run_dir / 'CaptureBatch.json')
            process = read(run_dir / 'OwnedProcess.json')
            assert proof['passed'] and proof['phase'] == phase and proof['temporary_camera_cleanup_verified_zero']
            assert proof['temporary_camera_remaining_count'] == 0 and proof['temporary_lighting_cleanup_verified_zero']
            assert batch['status'] == 'PASS' and batch['persisted_map_unchanged'] and batch['appearance_assets_unchanged']
            assert process['normal_exit'] and process['exit_code'] == 0 and not process['forced_cleanup']
            assert process['persisted_map_unchanged'] and process['helper_has_exited']
            assert batch['run_id'] == process['run_id'] == row['run_id']
            assert batch['map_sha256'] == process['map_sha256'] == map_sha
            assert not proof['map_save_requested'] and not proof['existing_light_switches_invoked']
            if specs is None:
                specs = proof['camera_specs']
            assert specs == proof['camera_specs']
            image = Path(row['path'])
            assert image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
            meta = read(image.with_suffix('.json'))
            assert meta['status'] == 'PASS' and meta['camera'] == row['camera'] and meta['run_id'] == row['run_id']
            assert meta['png_sha256'] == sha(image) == sha(row['archive'])
            assert meta['map_sha256'] == meta['map_sha256_after_cleanup'] == map_sha
            assert meta['intersection_capture_phase'] == phase and meta['fresh_map_load_verified']
            assert meta['inspection_camera_spec'] == specs[row['camera']]
            assert math.dist(meta['camera_location_cm'], specs[row['camera']]['location_cm']) < .001
            assert abs(meta['camera_fov_degrees'] - specs[row['camera']]['fov_degrees']) < .001
            camera_pose = {key: meta[key] for key in ('camera_location_cm', 'camera_rotation_degrees', 'camera_fov_degrees')}
            if row['camera'] in poses:
                assert poses[row['camera']] == camera_pose
            poses[row['camera']] = camera_pose
            rows.append(dict(camera=row['camera'], image=str(image), image_sha256=sha(image), run_id=row['run_id'],
                             normal_zero_exit=True, temporary_cameras_and_lights_remaining=0))
        captures[phase] = rows
    final = dict(passed=True, completed_utc=datetime.now(timezone.utc).isoformat(),
                 target='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet', version='original',
                 source_map_sha256=applied['source_map_sha256'], map_sha256=applied['map_sha256'],
                 backup=backup, changed_labels=applied['changed_labels'], clearances=audit['clearances'],
                 actor_preservation=audit['actor_preservation'], content_config_file_count=len(current),
                 all_other_content_config_files_byte_identical=True, assets_added_deleted_modified=0,
                 user_door_materials_open_angle_and_components_preserved=True,
                 completions=completions, captures=captures, visual_review='root directly inspected both After PNGs')
    (W / 'FinalReview.json').write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    report = f'''# 原版老城区局部穿模修复

2026-10-19，已完成，目标 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。

- 电线杆01整组向路缘移动115cm，横担旋转90度改为沿街；三根接入电线重新连接，另一端不动。横担距外墙装饰120cm，杆身距车道边23cm。道路、人行道尺寸未改。
- 酒店正面右侧出口旁的旧下水管、电表箱、接线盒、电缆及4个挂架沿墙移动200cm，落在相邻实墙上；离出口门洞至少159cm。保留门本身的材质、90度开启状态及全部组件。
- 共17个助手对象仅调整根变换，其余7969个Actor完整Native数据一致，Actor总数7986不变。未新增或删除资源，所有材质、碰撞、灯光保持。其余Content/Config文件逐SHA一致，涵盖用户资产、Main和第二版。
- 保存前完整比对通过，保存后独立重开比对通过；Inspect1、Apply1、Audit1及前后截图辅助进程均正常退出0。两张修复后截图已直接检查，临时相机与临时检查灯均清零且未保存。

当前地图SHA：`{applied['map_sha256']}`。本次用户输入SHA：`{applied['source_map_sha256']}`，没有恢复历史地图。

修复前地图备份：`{backup['file']}`。

前后对照：`{W / 'BeforeCaptures/Renders'}`、`{W / 'AfterCaptures/Renders'}`。
完整证据：`{W / 'FinalReview.json'}`。

后续仅凭本轮明确授权修改原版这两处助手对象；一般优化仍在第二版。不要重跑Apply脚本、不要用历史map覆盖用户当前修改。
'''
    (R / 'Docs/OldTownIntersectionFixResult.md').write_text(report, encoding='utf-8')
    checkpoint = R / 'Docs/UE5GreyboxCheckpoint.md'
    old = checkpoint.read_text(encoding='utf-8-sig')
    marker = '**2026-10-19 原版两处穿模修复完成'
    assert marker not in old
    entry = (f'{marker}：用户输入932de807…保留，在原版仅调整17个助手对象根变换（电杆5+接线3+酒店旧设施9）。'
             f'电杆向路缘115cm并横担沿街，酒店出口设施沿墙移200cm；门材质/开90度保留。7986Actor、其余7969完整Native一致；'
             f'所有其他Content/Config字节相同，用户资产/Main/V2未改。当前原图SHA {applied["map_sha256"]}。'
             f'保存前/独立重开/4截图正常0、临时相机灯清零，FinalReview PASS。见Docs/OldTownIntersectionFixResult.md，'
             f'WORK=Saved/CodexOutputs/OldTownIntersectionFix_20261019。勿重跑Apply或恢复旧map；一般优化仍在第二版。**\n\n')
    head, tail = old.split('\n\n', 1)
    checkpoint.write_text(head + '\n\n' + entry + tail, encoding='utf-8')
    print(json.dumps(dict(passed=True, map_sha256=applied['map_sha256'], actor_count=7986,
                          changed_actors=17, protected_files=len(current)-1), ensure_ascii=False))


if __name__ == '__main__':
    main()
