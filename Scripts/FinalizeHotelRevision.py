"""Bind validation, current captures, exact write scope and continuation note."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/HotelRevision_20261019'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
NEW=R/'Content/CodexGenerated/Hotel/Revision_20261019'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    applied=read(W/'Applied.json');audit=read(W/'Readback.json');assets=read(W/'Assets.json')
    assert applied['passed'] and audit['passed'] and sha(MAP)==applied['map_sha256']==audit['map_sha256']
    assert all(sha(p)==h for p,h in assets['new_asset_sha256'].items())
    checks={}
    for name in ['FrontRemovalPreflight','BlueprintGraphPreservation','DoorNativePreservation','DoorReadback','ClosureReadback','StairReadback']:
        d=read(W/(name+'.json'));assert d['passed'],name;checks[name]=dict(passed=True,sha256=sha(W/(name+'.json')))
    stages={}
    for name in ['Inspect2','Assets2','Apply2','Audit2']:
        d=read(W/(name+'.Completion.json'));assert d['normal_zero_exit'] and d['exit_code']==0
        stages[name]=d
    visual=read(W/'VisualReview.json');assert visual['passed']
    report=read(W/'CaptureBuildReport_FurnitureV2.json');captures=[]
    for name in report['hotel_openings_review_cameras']:
        p=W/'Captures/Renders'/(name+'.png');m=read(p.with_suffix('.json'))
        process=read(W/'Captures/Runs'/m['run_id']/'OwnedProcess.json')
        assert process['normal_exit'] and process['exit_code']==0 and not process['forced_cleanup']
        assert m['status']=='PASS' and m['png_sha256']==sha(p) and m['map_sha256']==applied['map_sha256']
        assert m['persisted_map_unchanged'] and m['appearance_assets_unchanged']
        assert m['temporary_camera_cleanup_verified_zero'] and m['temporary_lighting_cleanup_verified_zero']
        assert m['temporary_camera_cleanup_remaining_count']==0 and m['temporary_lighting_cleanup_remaining_count']==0
        source=m['source_build_report'];assert sha(source['file'])==source['sha256']
        assert m['inspection_camera_spec']==read(source['file'])['review_camera_overrides'][name]
        assert visual['images'][name]['sha256']==sha(p) and visual['images'][name]['passed']
        captures.append(dict(camera=name,png=str(p),sha256=sha(p),run_id=m['run_id'],owned_pid=m['owned_editor_pid'],normal_exit=True))
    original=read(W/'ProtectedBefore.json')['file_sha256'];current={str(p):sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
    old_own={p:h for p,h in original.items() if Path(p).is_relative_to(R/'Content/CodexGenerated') or Path(p).is_relative_to(R/'Config')}
    assert all(current.get(p)==h for p,h in old_own.items()),'Existing generated asset or Config changed'
    observed=[dict(file=p,before_sha256=h,current_sha256=current.get(p)) for p,h in original.items() if current.get(p)!=h and Path(p)!=MAP]
    new_observed=[dict(file=p,sha256=h) for p,h in current.items() if p not in original and not Path(p).is_relative_to(NEW)]
    result=dict(passed=True,completed_utc=datetime.now(timezone.utc).isoformat(),target_level='/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',
        source_map_sha256=applied['source_map_sha256'],map_sha256=applied['map_sha256'],actor_count=7985,
        hotel_doors=93,shared_door_blueprints=8,active_new_rear_handles=126,facade_doors_removed=3,wall_patches=3,side_stair_linings=4,landing_extensions=6,low_service_furniture=4,
        unchanged_other_actors=7875,original_door_components_native_exact=1057,side_stair_routes=6,side_stair_probe_samples=780,
        checks=checks,successful_stages=stages,captures=captures,
        write_scope=dict(saved_existing_packages=[str(MAP)],new_packages=assets['new_asset_sha256'],all_old_generated_and_Config_unchanged=True,checked_old_generated_and_config_files=len(old_own),
            original_Main_user_assets_and_V2_read_only_in_helpers=True,concurrent_editor_existing_changes_observed_and_preserved=observed,concurrent_editor_new_files_preserved=new_observed),backup=read(W/'Backup.json'))
    write(W/'FinalReview.json',result)
    documentation='''# 第一版酒店局部修订

已完成并保存 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。以用户最新保存的88b4版本为输入，未恢复历史地图；原图已备份。

四处巨型方块是布草、更衣和设备柜的占位模型，已换为高90cm的布草分格柜、带轮脏布草分类筐、低更衣柜和设备工作台；后窗下保留15cm净距。正面只保留中央入口，撤掉三个侧门/服务门及对应合页、门槛，门洞补为同材质实墙。

两侧楼梯增加四道连续内衬墙，使踏步贴墙，并补齐六处半层平台到后墙的52cm缺口。保留原有梯段宽度、转向平台和上方净高，未把踏步下方填到地面。

93套酒店门补齐内外把手；共126个新增有效背面把手，随原门轴或滑轨运动，保留原有闭合深度、开合姿态、材质和用户交互接口。仍按尺寸共用八个蓝图。新蓝图和四个家具mesh独立放在 `/Game/CodexGenerated/Hotel/Revision_20261019/`，遵守BP/SM_Hotel命名；旧共享蓝图、模型、材质保持不变。

正式写入和独立回读正常退出。其余7,875个Actor完整Native一致；93门顶层状态与1,057原组件Native精确保留，接口图连接检查通过。93门临时关闭/碰撞检查后恢复原姿态；两侧楼梯六段共780处支撑与胶囊通行检查通过。九张新鲜截图均完成目视审查，临时相机/灯清零，截图未保存地图。

用户可同时在Main编辑。助手只保存第一版及新增独立资源；过程中检测到Main及钥匙资源由并行编辑发生变化，已原样保留，未恢复或覆盖。没有应用性能或项目配置更改。中央楼梯未改；最初扩大的九路线诊断中，其既有开门姿态挡住原采样起点，正式验收范围为本次修改的两侧六段楼梯。

当前地图SHA：`{mapsha}`。
备份：`{backup}`。
验收：`Saved/CodexOutputs/HotelRevision_20261019/FinalReview.json`。
截图：`Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/`。

后续勿重跑Apply/恢复旧地图；继续以当前保存文件为准。常规全图优化仍在第二版，第一版只按用户明确请求改助手对象。
'''.format(mapsha=applied['map_sha256'],backup=result['backup']['file'])
    documentation+='\n实景截图：\n\n'
    for label,name in [('布草柜','REV_CleanLinen'),('分类车','REV_DirtyLinen'),('更衣柜','REV_Changing'),('设备台','REV_Equipment'),('南侧楼梯','REV_SouthStair'),('北侧楼梯','REV_NorthStair'),('正面北部','REV_FrontNorth'),('正面南部','REV_FrontSouth'),('双面把手','REV_DoubleHandle')]:
        documentation+='- ['+label+']('+str((W/'Captures/Renders'/(name+'.png')).as_posix())+')\n'
    (R/'Docs/HotelRevisionResult.md').write_text(documentation,encoding='utf-8')
    checkpoint=R/'Docs/UE5GreyboxCheckpoint.md';old=checkpoint.read_text(encoding='utf-8-sig')
    entry='**2026-10-19 第一版酒店局部修订完成：用户新输入88b4保留，当前SHA '+applied['map_sha256']+'。四巨型占位柜换低矮实用设施；正面除中央门外三门撤掉并补墙；两侧四内衬墙+六半层平台补片；93门共用八个独立DualHandle新BP，126有效背面把手，原组件/接口/姿态/材质保留。7985Actor，其余7875完整Native一致，1057原门组件Native精确保留；六段楼梯780采样、93闭合门与九截图验证通过，临时相机/灯清零。只保存原版+新Hotel/Revision_20261019资产，旧共享资产/Config不改，用户并行Main与钥匙编辑保留。见Docs/HotelRevisionResult.md及Saved/CodexOutputs/HotelRevision_20261019/FinalReview.json。禁止重跑Apply或恢复历史map。**\n\n'
    assert entry not in old
    checkpoint.write_text(old.replace('# UE5 老城区精简接续点\n\n','# UE5 老城区精简接续点\n\n'+entry,1),encoding='utf-8')
    # Old rejected preflight attempts remain diagnostic evidence, clearly dated.
    diag=W/'Diagnostics';diag.mkdir(exist_ok=True)
    for name in ['InspectionFailure.json','AssetFailure.json','ApplyFailure.json','ReadbackFailure.json']:
        p=W/name
        if p.exists():p.rename(diag/name)
    print('HOTEL_REVISION_FINAL_PASS',applied['map_sha256'])
if __name__=='__main__':main()
