"""Publish only after full readback, real collision tests and four reviewed PNGs."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelDoorClosure_20261019'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def main():
    a=read(W/'Applied.json');audit=read(W/'Readback.json');assert a['passed'] and audit['passed'] and sha(MAP)==a['map_sha256']==audit['map_sha256']
    assert audit['hotel_doors']==96 and audit['closed_collision_leaf_traces']==130 and audit['preservation']['passed']
    joints=read(W/'HingeParentsApplied.json');assert joints['passed'] and joints['map_sha256']==a['map_sha256'] and joints['corrected_count']==11
    assert audit['preservation']['moving_hinge_parent_corrections']==11
    completions={n:read(W/(n+'.Completion.json')) for n in ('Inspect1','Apply5','HingeParents1','Audit2')}
    assert all(c['normal_zero_exit'] and c['exit_code']==0 for c in completions.values())
    expected=read(W/'ProtectedBefore.json')['file_sha256'];expected.update(a['modified_existing_files']);expected.update(a['new_assets'])
    current={str(p):sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()};assert current==expected
    backup=read(W/'Backup.json');assert backup['passed'] and len(backup['files'])==9
    assert all(sha(r['backup'])==r['sha256'] for r in backup['files'])
    folder=W/'Captures';runs=read(folder/'CaptureRuns.json');labels={'CLOSURE_GuestClosed','CLOSURE_GuestHinge','CLOSURE_BathClosed','CLOSURE_MainClosed'}
    assert len(runs)==4 and {r['camera'] for r in runs}==labels
    images=[]
    for r in runs:
        assert r['captured'] and not r['reused'] and r['normal_exit'] and r['exit_code']==0 and not r['forced_cleanup']
        assert r['map_sha256']==a['map_sha256'];run=Path(r['archive']).parents[1]
        batch=read(run/'CaptureBatch.json');proof=read(run/'IntersectionCaptureProof.json');process=read(run/'OwnedProcess.json')
        assert batch['status']=='PASS' and batch['persisted_map_unchanged'] and batch['appearance_assets_unchanged']
        assert proof['passed'] and proof['temporary_camera_remaining_count']==0 and proof['temporary_lighting_cleanup_verified_zero']
        assert proof['temporary_closed_door_count']==96 and proof['temporary_closed_pose_restoration_verified']
        assert process['normal_exit'] and process['exit_code']==0 and not process['forced_cleanup'] and process['helper_has_exited']
        assert process['persisted_map_unchanged'] and batch['run_id']==process['run_id']==r['run_id']
        image=Path(r['path']);meta=read(image.with_suffix('.json'))
        assert meta['status']=='PASS' and meta['map_sha256']==meta['map_sha256_after_cleanup']==a['map_sha256']
        assert meta['camera']==r['camera'] and meta['run_id']==r['run_id'] and meta['temporary_closed_pose_restoration_verified']
        assert image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') and sha(image)==meta['png_sha256']==sha(r['archive'])
        images.append(dict(camera=r['camera'],file=str(image),sha256=sha(image),normal_zero_exit=True,temporary_cameras_lights_remaining=0))
    result=dict(passed=True,completed_utc=datetime.now(timezone.utc).isoformat(),target='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',
        source_map_sha256=a['source_map_sha256'],map_sha256=a['map_sha256'],hotel_doors=96,swing_doors=62,slider_doors=34,
        shared_blueprints=8,new_stop_components=96,new_mesh_assets=len(a['new_assets']),closed_leaf_collision_checks=130,moving_hinge_parent_corrections=11,closed_hinge_bearing_alignment_checks=186,
        preservation=audit['preservation'],user_assets_Main_V2_and_all_other_files_byte_identical=True,
        blueprint_graphs_variables_interfaces_and_existing_materials_preserved=True,backup=backup,completions=completions,captures=images,
        root_visual_review='Directly inspected four fresh PNGs',protected_existing_files=len(current)-len(a['new_assets'])-len(a['modified_existing_files']))
    (W/'FinalReview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    text=f'''# 原版酒店门闭合修复

2026-10-19已完成。目标 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，96套酒店门（62平开、34推拉），仍按尺寸共用8个原有Hotel蓝图。

根因是旧叶片中心在框正面之外3cm，叶片厚4cm，关闭零位仍与门框之间有1cm深度空隙。旧检查只证明碰撞能堵路，没有检查叶片是否齐框。

叶片、把手、碰撞及门上玻璃部件一同内移5cm，闭合时门面与框正面齐平；新增三侧门挡遮住工作边缝，门挡与木叶后表面留0.25cm间距，合页位置留槽，转角无共面正面积重叠。原转轴和固定合页保持，活动合页安装片/连接颈配合新深度；另将原本挂在门框下的11个活动合页改挂对应DoorHinge，开关时跟随门板，旧共享mesh未改。新增14个复用mesh位于 `/Game/CodexGenerated/Hotel/Meshes/DoorClosure/`，全部遵守SM_Hotel命名。

已逐一临时关闭96门，检查130块门板/碰撞盒实际齐平与真实阻挡射线；检查后恢复地图保存的原始开合姿态。蓝图默认关闭零位已更新，原有左右开/推拉、材质、Actor身份和用户图表/变量/接口保持。

保存前及独立重开完整比对通过：7986Actor不增减，96个新增DoorStops组件，62活动合页使用新mesh，其中11个修正父级和局部零位，其余7828Actor完整Native一致。其余28扇街区门、用户自制/导入资源、Main、第二版、Config文件逐SHA不变。

四张新鲜关闭态截图已直接目视检查，截图进程正常0，临时相机和灯清零、临时关门姿态已恢复、未写地图。

当前地图SHA：`{a['map_sha256']}`。本次用户输入：`{a['source_map_sha256']}`，未恢复历史地图。
备份（原图及8蓝图）：`{backup['directory']}`。
验收：`{W/'FinalReview.json'}`；截图：`{folder/'Renders'}`。

前四个未保存尝试已保留诊断并把助手BP从本轮备份精确恢复后重试；最终正式Apply5/HingeParents1/Audit2正常0。后续不要重跑旧Apply或用历史地图覆盖用户修改。一般美术优化仍在第二版，原版这次仅按明确要求修酒店门。
'''
    (R/'Docs/HotelDoorClosureResult.md').write_text(text,encoding='utf-8')
    p=R/'Docs/UE5GreyboxCheckpoint.md';old=p.read_text(encoding='utf-8-sig');marker='**2026-10-19 原版酒店96门闭合修复完成'
    assert marker not in old;head,tail=old.split('\n\n',1)
    entry=f'{marker}：用户新输入b6756330…保留。62平开+34推拉，8同尺寸共享BP仍复用；叶/把/碰撞/附属玻璃Y内移5cm，96DoorStops组件，62活动合页换3个复用新mesh、其中11个改挂DoorHinge，另11门挡mesh。关闭面齐框，130真实门板射线通过，原保存开合角度/材质/图表/接口不改。7986Actor，其他7828完整Native相同；28街区门、用户资源/Main/V2/Config字节保护。当前原图SHA {a["map_sha256"]}。Apply5/HingeParents1/Audit2正常0，4新鲜截图目视检查/临时清零且恢复原姿态，FinalReview PASS。见Docs/HotelDoorClosureResult.md，WORK=Saved/CodexOutputs/OldTownHotelDoorClosure_20261019。勿重跑Apply/恢复旧map；一般优化仍在第二版。**\n\n'
    p.write_text(head+'\n\n'+entry+tail,encoding='utf-8')
    print(json.dumps(dict(passed=True,map_sha256=a['map_sha256'],hotel_doors=96,shared_blueprints=8,new_mesh_assets=len(a['new_assets']),closed_collision_checks=130)))
if __name__=='__main__':main()


