from pathlib import Path
import shutil,json
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownVersion2_20261016'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def main():
    c=read(W/'Created.json');f=read(W/'FinalReview.json') if (W/'FinalReview.json').is_file() else {}
    scan=read(W/'SurfaceScanSummary.json') if (W/'SurfaceScanSummary.json').is_file() else {}
    backup=read(W/'Backup.json')
    text=f'''# UE5 老城区精简接续点

2026-10-16。用户已分出自己的原版，助手今后只在“老城区第二版”优化。不要恢复旧版本、重跑旧Apply、覆盖用户原图或共享资产。

- **未来唯一工作关卡** `{c['target_level']}`，磁盘 `Content/CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap`，SHA `{c['version2_map_sha256']}`，8017Actor/13929场景组件，保留81审查摄像机供助手截图。
- **用户原版** `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，只按本次授权删了81台历史截图CameraActor，未删玩家摄像机或背包SceneCapture。清理后7936Actor、SHA `{c['original_map_sha256_after_camera_cleanup']}`。此后用户可自行改；助手禁止再写原版及Main。
- 复制采用UE原生SaveAs后重新加载，源/目标整份Actor、精确SceneComponent、材质、碰撞和用户环境参数比对通过；fresh Input/Create/Readback/PreviewCost辅助进程均正常0。证据WORK `Saved/CodexOutputs/OldTownVersion2_20261016`。
- 用户旧原图输入SHA46c1e88a…：加入DirectionalLight/MoonDirectionalLight/SkyLight/BP_EnvironmentController，改Fog/Atmosphere/Cloud/PostProcess，移除PointLight，均保留。两方向灯已与Main完整核对（111字段+世界变换+3组件），无需再复制或隐藏。当前Main只读SHA4f186543…；用户新PickupBP SHA d3cee7f3…，不要恢复旧cc934d57。
- 完整复制前备份 `{backup['backup_directory']}`，2589文件逐SHA核验，包含当前原图、依赖/生成包、模型源与原Native数据。ReferenceOnly/Main仅参考，不能自动恢复覆盖用户Main。
- **资产隔离规则**：现在复制的是地图，1576配套资源仍共享但对助手冻结。以后改模型/材质/蓝图/RT，先复制到 `/Game/CodexGenerated/OldTownVersion2/`，只给第二版改引用；不得编辑旧OldTown或Yastar共享包，也不得改项目全局设置影响用户地图。未声称全套资产已经各自复制。
- 已完成模型源20变体/222组件（18酒店208+2街区14），原木框/BodySetup/材质覆盖/原WPO保留。SourceAudit20、NativePreservation、55床枕接触已通过。Legacy床垫初轮14侧面重叠已真实修复：冻结侧壁、包边、圆角、底面，只变形上表面；仅owned mesh+cache2包重导，其他38包不变。旧失败971文件在SoftGoodsBeforeOverlapCorrection_20261015T145916Z。
- 当前12361个非空静态模型组件的未舍入世界变换/父子/mesh/material/collision/visible及几何资源字节与修复后Native数据一致（用户PickupBP改动不改变构造出的几何）。据此构建V2当前GeometryDerivation，不假称新导出Native buffers；8719可见组件/344模型/9281596累计三角面。
- 全图全法向/内部面扫描状态：`{scan.get('passed','进行中')}`，统计 `{scan.get('counts',{})}`。仍按0.03cm平面/0.0001法向/1cm²，不能豁免重叠或放宽阈值。新6实际照明+2临时质检截图均normal0、临时灯清零、无地图保存，root已直接看8张。用户夜景的大厅/客房/门面很暗，保持用户照明，不能宣称细节在这些暗图中可见。
- V2登记状态：FinalReview passed=`{f.get('passed',False)}`，published=`{f.get('published',False)}`。发布入口 `Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json` 应以最终实际pointer为准；旧Stage3未发布就被用户新输入取代，旧Stage4方向光Apply也没有执行，不要重跑。
- **性能优化必须用户审核**。本次仅查资料/配置/日志/组件与RT，没有应用性能改动。RTX4050Laptop约6GB，当前配置Lumen/VSM等；没有运行帧时间/显存超预算证据。背包RT512×770 RGBA8、ShowOnlyList、保存态每帧捕获，不能当作渲染全老城，也未证实关闭背包后持续采集。建议先只读实测主瓶颈，再审核SC按需捕获/B单段实例化/C室内分级加载，详见WORK/PerformanceProposal.md。
- 摄像机清理不能承诺涨帧；不全局关防重合WPO、不盲目全开Nanite、不改碰撞/全局画质/流送结构。性能用户审批尚待，后续“继续”只授权一般美术优化，不等于批准待审性能选项。
- 保持4层27房酒店中央门/前台、办公室左/安全梯右上/公厕右下，7m车道/1.8m步道/5开放巷/9路缘灯8单向Spot。原18开口BP与MainHome仅证结构/包保护，未新做运行时通关；住宅单元化未实施。
'''
    for name in ('UE5GreyboxCheckpoint.md','OldTownRealismProgress.md'):
        p=R/'Docs'/name;hist=W/'DocsHistory'/('BeforeVersion2_'+name);hist.parent.mkdir(parents=True,exist_ok=True)
        if not hist.exists():shutil.copy2(p,hist)
        p.write_text(text,encoding='utf-8')
    (R/'Docs/OldTownVersion2Rules.md').write_text('''# 老城区版本分工

用户使用原版L_OldTownSchoolStreet。助手今后只在 /Game/CodexGenerated/OldTownVersion2/Maps/老城区第二版 做优化。

原版81台助手截图摄像机已清理。此后不再写原版，不改Main，不恢复用户灯光、环境或PickupBP的旧版本。

地图副本仍共享部分资产。助手编辑模型、材质、蓝图、RT前，必须先建立OldTownVersion2目录下的专用副本并只更换第二版引用，旧共享资产对助手只读。项目级渲染设置不能为第二版随意修改。

性能相关实例化、流送、阴影、Nanite、纹理、角色预览捕获频率等改动，须取得用户对具体审核方案的同意；当前仅有待审方案，未实施。一般“继续优化”不替代这项审核。

最新证据见Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json与OldTownVersion2_20261016目录。
''',encoding='utf-8')
    print('VERSION2_CHECKPOINT_AND_SCOPE_RULES_UPDATED')
if __name__=='__main__':main()
