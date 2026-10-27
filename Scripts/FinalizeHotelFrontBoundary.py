"""Final acceptance and small continuation note for this additive screen."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/HotelFrontBoundary_20261021'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    applied=read(W/'Applied.json');audit=read(W/'Readback.json');assets=read(W/'Assets.json');visual=read(W/'VisualReview.json')
    assert applied['passed'] and audit['passed'] and visual['passed']
    assert sha(MAP)==applied['map_sha256']==audit['map_sha256']
    stages={}
    for name in ['Inspect1','Assets1','Apply1','Audit1']:
        d=read(W/(name+'.Completion.json'));assert d['normal_zero_exit'] and d['exit_code']==0
        stages[name]=d
    report=read(W/'CaptureBuildReport.json');captures=[]
    for name in report['hotel_openings_review_cameras']:
        p=W/'Captures/Renders'/(name+'.png');meta=read(p.with_suffix('.json'));process=read(W/'Captures/Runs'/meta['run_id']/'OwnedProcess.json')
        assert process['normal_exit'] and process['exit_code']==0 and not process['forced_cleanup']
        assert meta['status']=='PASS' and meta['png_sha256']==sha(p) and meta['map_sha256']==applied['map_sha256']
        assert meta['persisted_map_unchanged'] and meta['appearance_assets_unchanged']
        assert meta['temporary_camera_cleanup_verified_zero'] and meta['temporary_lighting_cleanup_verified_zero']
        assert meta['temporary_camera_cleanup_remaining_count']==0 and meta['temporary_lighting_cleanup_remaining_count']==0
        assert sha(meta['source_build_report']['file'])==meta['source_build_report']['sha256']
        assert meta['inspection_camera_spec']==report['review_camera_overrides'][name]
        assert visual['images'][name]['sha256']==sha(p) and visual['images'][name]['passed']
        captures.append(dict(camera=name,file=str(p),sha256=sha(p),run_id=meta['run_id'],normal_exit=True))
    before=read(W/'ProtectedBefore.json')['file_sha256'];changed=[p for p,h in before.items() if Path(p)!=MAP and sha(p)!=h]
    assert not changed,changed
    assert all(sha(p)==h for p,h in assets['new_asset_sha256'].items())
    final=dict(passed=True,completed_utc=datetime.now(timezone.utc).isoformat(),source_map_sha256=applied['source_map_sha256'],map_sha256=applied['map_sha256'],
        target_level=applied['target_level'],actor_count=audit['actor_count'],original_actors_native_exact=audit['original_actors_native_exact'],
        added_actors=applied['added_actor_labels'],new_meshes=3,new_asset_sha256=assets['new_asset_sha256'],existing_packages_other_than_original_map_unchanged=len(before)-1,
        main_user_assets_and_V2_unchanged=True,permanent_new_lights=0,clear_routes=audit['clear_routes'],route_samples=audit['route_samples'],
        blocked_visibility_rays=audit['blocked_visibility_rays'],backup=read(W/'Backup.json'),successful_stages=stages,captures=captures)
    write(W/'FinalReview.json',final)
    text='''# 第一版酒店前方边界遮挡

已在用户最新保存的第一版 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet` 上完成。输入SHA：`{source}`，没有恢复旧地图。

针对截图中酒店前方正Y端空地，新增旧院墙、实心锈铁院门和两侧回墙，遮住地面终点及转角露空。院墙含露砖、柱、压顶，铁门有波纹钢板、搭接缝、拉手和合页，作为固定场景边界。墙脚落地并在原建筑角补实接头。

只新增四个自有Actor、三个SM_Hotel模型，资源在 `/Game/CodexGenerated/Hotel/FrontBoundary_20261021/Meshes/`。原有{count}个Actor完整Native、变换、父子关系、材质、碰撞及灯光状态在保存前和独立重开均一致；Main、第二版、用户制作/导入资产和所有旧包逐SHA保持。没有移动或删除原有建筑、门窗、相机、导航范围；没有添加永久灯光或更改项目性能设置。

遮挡射线{rays}条通过，包括院门中缝；酒店后侧绕行和前方接近路线共{samples}个胶囊/支撑采样通过。四张新鲜引擎截图已目视检查；临时检查照明与相机清零，截图未保存地图。已保存第一版并备份输入原图。

当前地图SHA：`{mapsha}`。
备份：`{backup}`。
完整验收：`Saved/CodexOutputs/HotelFrontBoundary_20261021/FinalReview.json`。

'''.format(source=applied['source_map_sha256'],count=audit['original_actors_native_exact'],rays=audit['blocked_visibility_rays'],samples=audit['route_samples'],mapsha=applied['map_sha256'],backup=final['backup']['file'])
    for label,name in [('巷口人眼视角','BOUNDARY_LaneEye'),('整体斜视','BOUNDARY_Oblique'),('实心旧院门','BOUNDARY_Gate'),('俯视位置','BOUNDARY_Top')]:
        text+='- ['+label+']('+(W/'Captures/Renders'/(name+'.png')).as_posix()+')\n'
    (R/'Docs/HotelFrontBoundaryResult.md').write_text(text,encoding='utf-8')
    checkpoint=R/'Docs/UE5GreyboxCheckpoint.md';previous=checkpoint.read_text(encoding='utf-8-sig')
    entry='**2026-10-21 酒店前方正Y端遮挡完成：以用户新保存208f0ab3为输入，只加4自有Actor(旧院墙/实心院门、两回墙、角部补实)，3个独立SM_Hotel模型。原7989Actor完整Native及旧Content/Config全SHA保持；Main/V2/用户资源未改。105条遮挡射线、2条实际绕行/接近路线与4新鲜截图通过，检查相机/灯清零。当前SHA '+applied['map_sha256']+'。见Docs/HotelFrontBoundaryResult.md与Saved/CodexOutputs/HotelFrontBoundary_20261021/FinalReview.json。勿重跑Apply/恢复旧map，不自动封另一端或其他窄巷。**\n\n'
    assert entry not in previous
    checkpoint.write_text(previous.replace('# UE5 老城区精简接续点\n\n','# UE5 老城区精简接续点\n\n'+entry,1),encoding='utf-8')
    print('HOTEL_FRONT_BOUNDARY_FINAL_PASS',applied['map_sha256'])
if __name__=='__main__':main()
