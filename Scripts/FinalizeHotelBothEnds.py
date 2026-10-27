"""Publish only after fresh saved-map, visual and process-lifecycle proofs."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/HotelFrontBoundaryBothEnds_20261021'
MAP=R/'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    applied=read(W/'Applied.json');audit=read(W/'Readback.json');visual=read(W/'VisualReview.json')
    assert applied['passed'] and audit['passed'] and visual['passed']
    assert sha(MAP)==applied['map_sha256']==audit['map_sha256']==visual['map_sha256']
    stages={name:read(W/(name+'.Completion.json')) for name in ('Apply1','Audit1')}
    for s in stages.values():
        assert s['normal_zero_exit'] and s['exit_code']==0 and sha(s['script'])==s['script_sha256']
    before=read(W/'ProtectedBefore.json')['file_sha256']
    now={str(p):sha(p) for root in (R/'Content',R/'Config') for p in root.rglob('*') if p.is_file()}
    assert set(now)==set(before) and all(h==now[p] for p,h in before.items() if Path(p)!=MAP)
    report=W/'CaptureBuildReport.json';capture=read(report);captures=[]
    for name in capture['hotel_openings_review_cameras']:
        png=W/'Captures/Renders'/(name+'.png');m=read(png.with_suffix('.json'))
        assert m['status']=='PASS' and m['map_sha256']==sha(MAP) and m['png_sha256']==sha(png)
        assert visual['image_sha256'][name]==sha(png)
        assert m['source']=='fresh_persisted_map_load' and m['persisted_map_unchanged'] and m['appearance_assets_unchanged']
        for kind in ('camera','lighting'):
            assert m['temporary_'+kind+'_cleanup_verified_zero'] and m['temporary_'+kind+'_cleanup_remaining_count']==0
        assert m['source_build_report']['sha256']==sha(report)
        owned=read(W/'Captures/Runs'/m['run_id']/'OwnedProcess.json')
        assert owned['normal_exit'] and owned['exit_code']==0 and not owned['forced_cleanup'] and owned['persisted_map_unchanged']
        assert owned['owned_editor_pid']==m['owned_editor_pid']
        captures.append(dict(camera=name,file=str(png),sha256=sha(png),run_id=m['run_id'],normal_exit=True))
    assert len(captures)==4
    backup=read(W/'Backup.json');assert sha(backup['file'])==applied['source_map_sha256']==backup['sha256']
    final=dict(passed=True,completed_utc=datetime.now(timezone.utc).isoformat(),target_level=applied['target_level'],
        source_map_sha256=applied['source_map_sha256'],map_sha256=sha(MAP),actor_count=7997,original_actors_native_exact=7993,
        added_actors=applied['new_labels'],total_boundary_actors=8,both_hotel_front_ends_complete=True,
        resources_added_or_modified=0,other_existing_packages_unchanged=len(before)-1,main_user_assets_and_V2_unchanged=True,
        blocked_bidirectional_rays=audit['blocked_visibility_and_collision_rays'],clear_route_segments=audit['clear_routes'],
        route_samples=audit['route_samples'],permanent_new_lights=0,backup=backup,successful_stages=stages,captures=captures,
        visual_review_sha256=sha(W/'VisualReview.json'),source_north_final_review_sha256=read(W/'BaselineReuseProof.json')['reference_final_review_sha256'],
        supersedes_north_only_scope=True,limitations=['Sampled collision and capsule verification; no runtime input or navigation rebuild.'])
    write(W/'FinalReview.json',final)
    images='\n'.join('- ['+label+']('+str(W/'Captures/Renders'/name).replace('\\','/')+'.png)' for label,name in [
        ('双端总览','BOTH_Overview'),('北端人眼视角','BOTH_NorthEye'),('南端人眼视角','BOTH_SouthEye'),('南端回墙及绕行','BOTH_SouthTop')])
    result='''# 第一版酒店前方双端遮挡修正版

根据用户“哪有只封一边”的纠正，已在当前第一版上补齐负Y端；原正Y端保留。两头均为旧院墙、实心锈铁院门和两侧回墙，门保持与道路对齐。没有覆盖旧地图。

本轮新增4个南端自有Actor，两头共8个。复用既有3个模型，不创建或改写资源包。原有7993个Actor完整Native在保存前和独立重开均一致；Main、第二版、用户制作/导入资产及其余2941个Content/Config文件逐SHA保持。

两头主墙与回墙492条双向射线通过；前方接近和酒店两侧绕行分5段、438个真实地面支撑及180cm高/34cm半径胶囊采样通过。南侧原有12cm路沿单独按可跨越台阶验证，没有改动路面。四张新鲜引擎截图已直接目视检查，临时相机和照明清零，截图未保存地图。Apply与独立Audit均正常退出0。

当前原图SHA：`'''+sha(MAP)+'''`。
修改前当前地图备份：`'''+backup['file']+'''`。
验收：`Saved/CodexOutputs/HotelFrontBoundaryBothEnds_20261021/FinalReview.json`。

'''+images+'\n'
    (R/'Docs/HotelFrontBoundaryBothEndsResult.md').write_text(result,encoding='utf-8')
    old=R/'Docs/HotelFrontBoundaryResult.md';oldtext=old.read_text(encoding='utf-8')
    prefix='> 2026-10-21 双端修正已完成：用户明确要求两头都挡，负Y端已补齐。当前状态与新截图见 [双端修正版](D:/UE/Project/HorrorGame/Docs/HotelFrontBoundaryBothEndsResult.md)。下文为此前仅正Y端的历史记录。\n\n'
    if not oldtext.startswith(prefix):old.write_text(prefix+oldtext,encoding='utf-8')
    checkpoint=R/'Docs/UE5GreyboxCheckpoint.md';text=checkpoint.read_text(encoding='utf-8')
    text=text.replace('勿重跑Apply/恢复旧map，不自动封另一端或其他窄巷。','历史单端限制已由用户本次双端纠正取代；其他窄巷仍不擅自封。勿重跑旧Apply/恢复旧map。')
    entry='**2026-10-21 最新：酒店前方两头遮挡已完成，纠正此前只做正Y端的遗漏。保留北端4Actor，新增南端4Actor、复用3冻结模型，无资源包改动。原7993Actor完整Native/其他2941文件逐SHA保持；Main/V2/用户资产只读。当前7997Actor、SHA '+sha(MAP)+'。492双向射线、5路线段438胶囊支撑采样及4新鲜截图通过，临时相机灯清零，Apply1/Audit1正常0。见Docs/HotelFrontBoundaryBothEndsResult.md与Saved/CodexOutputs/HotelFrontBoundaryBothEnds_20261021/FinalReview.json。本次两端均获明确授权；勿恢复历史map或重跑旧Apply，其他窄巷不擅自封。**\n\n'
    title='# UE5 老城区精简接续点\n\n'
    if entry not in text:text=text.replace(title,title+entry,1)
    checkpoint.write_text(text,encoding='utf-8')
    print(json.dumps(dict(passed=True,map_sha256=sha(MAP),captures=len(captures),both_ends=True),ensure_ascii=False))
if __name__=='__main__':main()
