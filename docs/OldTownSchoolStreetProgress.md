# 老城区学校街道场景进度记录

记录更新：2026-10-04  
当前状态：DetailPolish 细节优化已保存为 06E34C6F…，5877 个 Actor、4430 个结构实例，最终独立重载及 Detail3182、Architecture6227、Revision458、Lighting120、Triangle779 项审计和 115/115 Python 检查均 PASS。实际导入三角面最小净高为 230.847372955 cm；六机位图像与 FinalReview 的最终核对通过。详情见 [可进入建筑续作记录](D:/UE/Project/HorrorGame/docs/EnterableStreetProgress.md)。下方 F5 建筑拼合、E6 灯光道路及更早阶段保留历史数据。

## 2026-10-04 DetailPolish 细节优化（最新）

目标仍为 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，当前保存 SHA-256 为 `06E34C6F95BE4E4D3E57205BAE451BBB80947142EADA5F15E21756E49721FD9F`，共 5877 个 Actor、4430 个结构实例。108 块完整绿色矩形封板、69 个成人尺度家具部件、4 个人体参照和 MainHome 原有交互维持；未增加灯光，实际道路仍仅有 8 盏路灯。

- Blender MCP 生成 46 个独立倒角轮廓网格，导入 563 个视觉实例，组成 162 个梯段、81 个平台、291 个内窗框和 29 个门组件。原 1502 个踏步、81 个中间平台和 29 扇原门叶及门把隐藏渲染并保留原碰撞设置；门把原有 `NoCollision` 保持。
- 29 个门洞地面填充仅覆盖墙厚内侧局部法向 n=0..19.5 cm，与楼层同高且无外凸，三条轨迹按 5 cm 间隔的细致地面支撑检查通过。
- 48 对铺地共面重叠裁为 0，按高度和材质分组的前后覆盖对称差为 0；原通行带五条轨迹的真实碰撞和支撑检查全通过。
- 街尾线脚、檐口、招牌和雨棚 6 个部件贴墙，5 个电气部件沿 Y 移动 -460 cm、后侧贴 X=9000.5 cm，并增加 4 个独立墙装支撑件。
- 新门面板配圆形执手及每片 3 个铰链，固定 90° 开放，没有新增开关交互。
- 291 个内窗框采用四格窗与 3 cm 宽十字分隔，使用已有磨旧木材质，无新增自发光，源网格闭合且无重复重叠。

[BuildReport.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/BuildReport.json) 最终 06E34C6F… 保存及 [SavedVerification.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/SavedVerification.json) 独立重载 PASS。最终重新加载后的 [DetailPolishAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/DetailPolishAudit.json) 为 3182 项、[ArchitectureSealAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/ArchitectureSealAudit.json) 为 6227 项、[RevisionAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/RevisionAudit.json) 为 458 项、[LightingCleanupAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/LightingCleanupAudit.json) 为 120 项，均 PASS、0 失败；[PythonTests.log](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/PythonTests.log) 为 115/115 通过。采样不代替实时玩家巡游。

最终 06E34C6F… 的 [DetailTriangleAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/DetailTriangleAudit.json) 为 779 项、0 失败，导入三角面最小垂直净高为 230.847372955 cm，高于 225 cm 目标；规划解析保守值为 230.6875 cm。这项几何净高验证不代替完整实时玩家巡游。6 个最终机位已全部生成并逐张查看，PNG 与 metadata 均匹配 06E34C6F… 保存地图。稳定 [FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/FinalReview.json) 的场景与图像核验为 PASS，capture_count=6。可查看 [内窗四格框](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Renders/CAM_Polish_InnerTrim.png)、[齐平门口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Renders/CAM_Polish_EntryFloor.png)、[连续楼梯底面](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Renders/CAM_Polish_Stair.png)。楼梯、门窗、内窗框、门口地面和背街转弯为 Unlit，街尾路口为 Lit；视口模式已实际设置并回读，未增加补光。捕获辅助进程采用有界清理，exit=-1 不表示正常退出。

[OldTownDetailPolish.blend](D:/UE/Project/HorrorGame/SourceArt/OldTownDetailPolish_20261004/OldTownDetailPolish.blend) 及独立 FBX 位于 [源文件目录](D:/UE/Project/HorrorGame/SourceArt/OldTownDetailPolish_20261004)。[Before](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Before) 保存 F5 地图、报告及截图；MainHome 原有交互保持。本轮 09:03 完成的场景核验中，L_Main 保持 BA484854… 基准，原始 Blockout 为 D15F1749…。收尾检查发现 L_Main 在 10:58 另有保存为 EE46F2CF…；目标场景仍为 06E34C6F…，Blockout 未变。已保留 L_Main 当前较新版本，没有覆盖或回退；操作者未确定，差异记入 [ExternalMapChange.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/ExternalMapChange.json)。

## 2026-10-04 建筑拼合与门窗优化（已完成历史版本）

本节数量、哈希及五机位验收属于 F5 版本；当前细节优化结果以上方最新章节为准。

目标仍为 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，地图 SHA-256 为 `F5CB706E2A45E20DCD2EF239246587604A0D147E3ADEE4A7A784BAB6E76E39F4`。共 5281 个 Actor、4397 个结构实例，29 个单户主要入口、69 个成人尺度家具部件、4 个人体参照及 MainHome 原有交互保持。

- 27 个楼梯核心使用 108 块整高规则绿色封板，中部 20 cm 间隔填满，靠墙和后侧用 25 cm 宽封板补齐。140 cm 梯段和转弯平台保留，无跨层封板重叠。
- 382 个楼板/屋面模块边界向墙内搭接 0.5 cm，墙角内侧同样搭接 0.5 cm，封闭模块拼合缝，同时保留真实楼梯开口。
- 29 个主要入口各有一扇实体门叶，固定 90° 打开，本轮未添加开关交互；MainHome 原有门和卷帘交互保持。
- 29 栋共 291 个窗模块，采用真实墙洞、全墙厚窗套和阻挡玻璃。窗按实际层高布置，不穿楼板；替换旧窗及 42 个学校迁移窗，清除重复叠窗。

[ArchitectureSealReport.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/ArchitectureSealReport.json) 为 PASS，[ArchitectureSealAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/ArchitectureSealAudit.json) 为 6194 项、0 失败，覆盖玻璃实际碰撞、旧窗残留、108 块规则整板、跨层不重叠及结构实测。[SavedVerification.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Before/SavedVerification.json) 独立重载 F5CB706E… 通过；[RevisionAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/RevisionAudit.json) 为 492 项、[LightingCleanupAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/LightingCleanupAudit.json) 为 90 项、[PythonTests.log](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/PythonTests.log) 为 115/115，均 PASS，Map Check 为 0 错误、0 警告。

[ArchitectureSeal_20261004/Before](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before) 备份修改前 E6BA8307… 地图、报告及截图。`L_Main` 的 BA484854… 和原始 Blockout 的 D15F1749… 保持进入任务时基准状态。物理采样不代替真人玩家巡游。继续优化使用 [SealOldTownArchitecture.py](D:/UE/Project/HorrorGame/Scripts/SealOldTownArchitecture.py)，避免旧全量重建覆盖当前规则封板与门窗。

五张 1280×720 最新图像已生成并逐张查看，[FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/FinalReview.json) 为 PASS、`capture_count=5`，PNG 及 metadata 均匹配 F5CB706E…。[楼梯整板](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Seal_Stair.png)、[门窗外侧](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Seal_DoorWindow.png)、[室内窗套](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Seal_WindowInterior.png)、[背街转弯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Cleanup_TurnNorth.png) 是 Unlit 几何核对视图；[街尾路口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Cleanup_Junction.png) 为 Lit，全部视口模式均经回读确认并写入 `view_mode_verified`。结构预览没有新增补光，实际道路照明仅有 8 盏路灯，地下 2 盏 UI 灯保持隔离。新门固定 90° 开放，本轮未新增开关交互。隐藏捕获辅助进程采用有界清理，收尾时无 UnrealEditor 残留；图像核验不表示辅助进程一定正常退出。

## 2026-10-03 路灯清理与街尾路口（已完成历史版本）

本节数量、哈希、报告及五机位验收属于 E6 版本；当前建筑优化状态以上方最新章节为准。

目标仍为 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，当前地图 SHA-256 为 `E6BA8307897D19B919DBB852D166ADCE0DBBFD17D21451C30FDFE5397240B3BE`。现有 6455 个 Actor、5632 个结构实例，29 个单户入口与 69 个成人尺度家具部件保持；门前凸起门槛为 0，绿色楼梯封板保持完整。

- 删除 162 个场景灯 Actor：124 盏室内灯、36 盏补光/门灯/学校/巷道灯，以及 DirectionalLight、SkyLight。地面场景只保留 8 盏路灯 PointLight（原 6 盏加 T 字路口 2 盏），9 座路灯杆中的故障杆 `StreetLamp_03` 未点亮。
- 地下背包人物预览 BP 内 2 盏 SceneCapture 专用 UI 灯保持，不覆盖地面；当前全地图实际有 10 个灯组件。全部非路灯灯管及亮窗的自发光已用地图实例材质覆盖关闭，共享材质保持不动，雨棚及建筑部件保持。
- 原 7 座路灯移到主街 Y±500 cm 的实际铺装区域，保留 120 cm 行走带。5 处宽 150 cm 的非公共楼间夹缝封墙，真正主巷仍为墙间 320 cm、预留净通行 280 cm。
- 街尾东侧建筑从 X=7700 cm 移到 X=9000 cm，后退 13 m；横街宽 7 m，范围收至 Y±2075 cm，南北背街均延长到 X=8250 cm。横街两端转向西接回背街，取消原 Y±3900 cm 的边缘终端，形成闭合路网；北、南端各补宽 180 cm 的路缘，人行道之后仍有 5.7 m 建筑退距。旧悬空招牌、窗户和电气附件已归位。
- 两条实测路径从主街经 X=7900 cm / Y±1915 cm 转西到 X=6200 cm / Y±1915 cm，真实胶囊通行与地面支撑检查均通过；五处封墙的实际边界和阻挡碰撞也已核对。

本轮 [LightingCleanupReport.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/LightingCleanupReport.json) 为 PASS，[LightingCleanupAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/LightingCleanupAudit.json) 为 100 项检查、0 失败；[RevisionAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/RevisionAudit.json) 的 3776 项检查和 [SavedVerification.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/SavedVerification.json) 独立重载均通过，Map Check 为 0 错误、0 警告，[PythonTests.log](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/PythonTests.log) 为 115/115 通过。

五张 1280×720 复核图像已全部完成，[FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/FinalReview.json) 为 PASS、`capture_count=5`，PNG 和 metadata 均匹配 E6BA8307… 地图哈希。[主街](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_MainStreet.png)、[街尾路口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_Junction.png)、[原路灯夹缝](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_FormerLampGap.png) 为 Lit；[北侧转弯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_TurnNorth.png) 和 [道路总览](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_RoadPlan.png) 为已设置并回读确认的 Unlit 结构预览，metadata 记录 `view_mode_verified=unlit`。两张结构图未增加灯光，不代表实际路灯照明效果。隐藏捕获辅助进程采用 PNG 完成后的有界清理，不能把图像核验通过当作正常退出保证；历史六张图像不作为本版本验收。

报告保存在 [LightRoadCleanup_20261003](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003) 并更新 canonical 报告；[Before](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/Before) 保存修改前 `9D18E94A...` 地图和报告。[ProtectedMapBaseline.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/ProtectedMapBaseline.json) 证明 `L_Main` 在首次只读清单前已于 19:47 保存为 `BA484854A90452653F201682A8288C532A70D8762B447E39836F64AAB3AE1EDA`，本轮保留该进入任务前状态，原始 Blockout 仍为 `D15F1749...`，旧会话的 `200E70...` 不是本轮基准。后续使用 [CleanupOldTownLightingAndStreetEnd.py](D:/UE/Project/HorrorGame/Scripts/CleanupOldTownLightingAndStreetEnd.py) 在既有地图继续，不要重跑旧全量构建；转换器的 `street_lamps_only` 策略已禁止重建 124 盏室内灯。以上物理采样不代替完整实时玩家巡游。

## 2026-10-03 人体尺度与街道布局修订（历史版本）

以下数量、哈希及六机位验收属于灯光清理前版本，当前状态以上方最新章节为准；旧章节中的同名报告引用可能已由最新报告覆盖。

- 既有目标 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet` 保存为 6612 个 Actor、5632 个结构实例。29 栋建筑各有一个主要入口；`DoorThreshold` 为 0，楼梯侧面使用连续绿色封板。
- 重铺 39 个地面模块并增加 4 块巷道隔墙。主街宽 700 cm，人行道铺装宽 180 cm、保留通行宽 120 cm。巷道墙间宽 320 cm，其中预留净通道宽 280 cm。
- 通过 Blender MCP 实际修改并导出 9 件源资产：8 个家具部件加 180 cm 高、50 cm 肩宽人体参照。桌为 150×90×80 cm，椅为 52×52×100 cm、座面高 48 cm，柜体为 140×70×200 cm；床垫底面/顶面仍离地 44/59 cm。
- 放置 69 个正常家具部件，包含 7 组成人尺寸床；另放置 4 个人体参照实例。`BLK_L_Filler_02_Mass` 二层成人床不适配，未缩小家具。实例使用 `NoCollision`，视觉人体宽 50 cm 与物理胶囊宽 68 cm 分别复核。

本次 Blender 源文件为 [OldTown_HumanScaleRevision.blend](/D:/UE/Project/HorrorGame/SourceArt/OldTownScaleRevision_20261003/OldTown_HumanScaleRevision.blend)，导出尺寸及偏移见 [ImportManifest.json](/D:/UE/Project/HorrorGame/SourceArt/OldTownScaleRevision_20261003/ImportManifest.json)。前一轮记录的 MCP 用量限制属于历史阶段，不适用于这次实际修改和导出。

最新 [BuildReport.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/BuildReport.json)、[RevisionPlan.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/RevisionPlan.json) 与 [RevisionAudit.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/RevisionAudit.json) 是当前版本依据。RevisionAudit 为 PASS，3776 项检查无失败；[SavedVerification.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/SavedVerification.json) 独立重载通过，检查 29 栋建筑、69 个家具实例及 123 个资产引用。当前地图 SHA-256 为 `9D18E94A645ADB76B6D0F4914234D34150922D29AC1D4BD1C6954F91C28A84DE`。

最终六张 1280×720 修订截图已生成并逐张查看，PNG 与 metadata 均匹配最终地图哈希，[FinalReview.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/FinalReview.json) 核验为 PASS。可查看 [桌椅与人体](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/Renders/CAM_Revision_TableHuman.png)、[完整道路总览](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/Renders/CAM_Revision_RoadPlan.png)、[楼梯封板](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/Renders/CAM_Revision_StairClosed.png)、[平整入口](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/Renders/CAM_Revision_EntranceFlush.png)。道路总览完整覆盖街区及校园，已调整方向、取景和曝光。

截图辅助进程在 PNG 完成后采用有界清理，收尾时未残留编辑器进程；图像核验通过不表示辅助进程正常退出。碰撞采样不替代完整实时玩家巡游。旧机位图像保留历史用途；以下原有 Actor 数量、哈希、测试和截图结果均属于对应历史阶段。

## 本轮已完成

- 目标关卡：`/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`
- 原始灰盒关卡保持只读：`/Game/Yastar/Maps/Blockout/L_Chapter01_Blockout`
- 重建后的关卡包含：
  - 757 个 Actor，其中 683 个为本场景生成内容
  - 225 个单体高细节窗户模块
  - 20 种 P2 独立高细节道具资产、61 个场景实例
  - 10 种 P3 一体化模块资产、33 个场景实例
  - 6 种 P5 玩家距离模块资产、15 个非阻挡场景实例
  - 5 个固定对比机位
- 新增可复用建筑模块：
  - `/Game/Yastar/OldTownSchoolStreet/Architecture/Windows/SM_OTS_Window_Residential`
  - `/Game/Yastar/OldTownSchoolStreet/Architecture/Windows/SM_OTS_Window_School`
- 已提升垃圾桶和纸箱模型：带轮、盖、把手、踏板、折叠纸板和胶带等结构，不再只是单个方块。
- 新增一体化高细节单体资产：
  - 老式自行车（轮胎、轮圈、辐条、车架、链轮、货架和车篮）
  - 墙面设备组（排水管、电表箱、接线盒、线圈和卡箍）
  - 街灯（底座、锥形灯杆、检修盖、弯臂、灯罩和镜片）
  - 路边排水篦子与单层不规则水坑
- 路灯已改为不对称分布，并保留一盏故障熄灭灯，削弱重复的模块走廊感。
- 修正 Geometry Script 圆柱连接器的 Pitch 方向；路灯弯臂、自行车车架/辐条、线缆弯头等斜向构件的两端现在准确相接。
- 北、南巷道横杆均嵌入两侧墙体 2 cm；分段悬空管改为落地连续管并增加三道实体卡箍。
- 墙挂电表、空调、排水管、水槽、垃圾桶和晾衣架支点均按真实墙面重新贴合；自行车轮胎落地并靠墙摆放。
- 电线杆移到街沿，杆身距立面约 180 cm，朝楼横担端到立面保留约 95 cm 净距。
- 大面积墙材质使用非整数双尺度采样与低频世界噪声旧化，打破同一混凝土污斑的规则周期和跨建筑同步。
- 普通商铺卷帘片已改为紧密的 22 片节奏；巷道悬浮薄板和 MainHome 侧墙重复设备已清除。
- MainHome 商铺保持四个稳定资产：
  - `/Game/MainHome/SM_MainHome_Enterable`
  - `/Game/MainHome/SM_MainHome_Shutter`
  - `/Game/MainHome/SM_MainHome_Door_Left`
  - `/Game/MainHome/SM_MainHome_Door_Right`
- 交互 Actor：`/Game/Yastar/Blockout/Buildings/BP_MainHomeInteractive`
- 商铺招牌已修正为正确朝向的“大众小卖部”。
- 门、门框、上方气窗和卷帘门的可视结构已覆盖接缝；没有可见黑缝。

## 已完成验证

- 场景生成：`OTS_BUILD_SUCCESS actors=757 generated=683 cameras=5`
- 场景截图：`OTS_CAPTURE_SUCCESS count=5`，5 张 1600×900 PNG
- 近景贴合审计：`OTS_CONTACT_AUDIT_SUCCESS count=23`，23 张 1440×810 PNG
- 独立关卡验证：`PASS`，757 Actor、683 个生成 Actor、4 个 MainHome 网格组件、2 个交互区、5 张固定截图
- Map Check：0 Error、0 Warning
- Python 契约测试：103/103 通过
- MainHomeInteractive 原生 UE 自动化测试：9/9 通过
  - 左右门独立瞄准和开关
  - 内推/外拉角度计算
  - 卷帘门开启、关闭和端点碰撞
  - 从室内瞄准顶部保留段关闭卷帘门
  - 开启后的玩家通行碰撞
  - 门板精确碰撞边界
  - 可视压条覆盖双门中心缝
- 验证报告：`Saved/CodexOutputs/OldTownSchoolStreet/ValidationReport.json`
- 交互测试报告：
  `Saved/CodexOutputs/OldTownSchoolStreet/P5MainHomeTestReport/index.json`

## 当前哈希

- 原始 Blockout：
  `D15F1749800233495469ACB72E60A7C0D837319EECF57FB14BFF25FDBBD9DE09`
- 目标场景：
  `6A272C843EF61230A40E64CA050E79E4729611A1915541E6068684E8B646E27B`

## 当前截图

- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_Hero.png`
- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_MainHome.png`
- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_Alley.png`
- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_StreetDiagonal.png`
- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_TopDown.png`
- MainHome 近景：
  `Saved/CodexOutputs/OldTownSchoolStreet/HeroFidelity/`
- 贴合审计近景：
  `Saved/CodexOutputs/OldTownSchoolStreet/ContactAudit/`

## 后续继续时的入口

1. 先读取本文件和 `SceneBuildManifest.json`，不要重做已通过内容。
2. 从现有五个固定机位继续做美术差距对比。
3. 若进入 P6，可优先：
   - 由已登录用户在 Fab 中领取并导入授权明确的免费家具包，再替换少数室内陈列资产
   - 为远端屋顶增加水箱、天线和更细的女儿墙轮廓
   - 对 MainHome 墙面与绿色金属增加更丰富的宏观湿污和掉漆变化
4. 修改后依次重建、五机位截图、运行关卡验证和 9 项交互测试。

## 本轮主要脚本

- `Scripts/CreateOldTownSchoolStreetScene.py`
- `Scripts/CreateOldTownArchitecturalModules.py`
- `Scripts/CreateOldTownDetailedProps.py`
- `Scripts/CaptureOldTownContactAudit.py`
- `Scripts/UpgradeMainHomeHeroAsset.py`
- `Scripts/CaptureOldTownSchoolStreet.py`
- `Scripts/ValidateOldTownSchoolStreet.py`

## 2026-07-27 路灯、自行车与玩家尺度复核

- 建筑、道路、巷宽和 MainHome 保持原始厘米尺度；MainHome 仍为 Scale 1，未做全局缩放。
- 7 盏路灯从约 293–338 cm 校准为约 380–410 cm；灯头、点光源和实例比例同步更新。
- 路灯底座—锥杆、斜撑—主杆、两段灯臂、灯臂—灯壳、灯罩—灯体和镜片—灯体均改为实体穿插连接，不再依赖端面相切。
- 3 辆自行车统一为 Scale 1.04，约 191 × 55 × 102 cm，并重新贴墙落地。
- 自行车轮胎—轮圈、辐条—轮圈、链条—齿盘、座管—坐垫、把立—横把、货架支撑、脚撑和篮筐支撑均已消除真实空隙。
- 固定视图已刷新；新增路灯正反面与自行车正斜面大景深特写，共 11 张接触审计图。
- 最终验证：Map Check 0 Error / 0 Warning；Python 97/97；MainHomeInteractive 9/9。

## 2026-08-05 P3 店面、校门与材质升级

- 新增 5 个 Geometry Script 单体 Static Mesh 资产，共 17 个场景实例：
  - `SM_P3_StaticShutter`：4 个实例
  - `SM_P3_SignAssembly`：6 个实例
  - `SM_P3_AwningAssembly`：3 个实例
  - `SM_P3_SchoolGateLeaf`：2 个实例
  - `SM_P3_SchoolGatePost`：2 个实例
- 原先约 166 个卷帘条、招牌边框、雨棚支架和校门基础形状 Actor 已压缩为 17 个完整资产实例；关卡 Actor 总量由 888 降至 739。
- 静态卷帘门加入连续背板、22 片互扣叶片、嵌合导轨、顶箱、底梁、锁块和局部锈蚀；暗线只表现槽口，不再形成穿透空隙。
- 招牌、雨棚和校门的板面、边框、螺栓、支架、铰链与旧化层均采用实体交叠连接，消除了近景浮片阴影和端面黑缝。
- 南北校门叶按通道方向镜像，铰链世界高度精确对齐到 55/180 cm；门柱底座补齐对应简单碰撞。
- `M_OTS_FadedBlueWall`、`M_OTS_FadedGreenWall` 已使用 Poly Haven Painted Plaster CC0 PBR；`M_OTS_OldGreenMetal` 已使用 Poly Haven Green Metal Rust CC0 PBR。
- 场景现在验证 12 张源纹理、26 个材质、20 个 P2 道具资产/54 个实例、5 个 P3 模块资产/17 个实例和 220 个建筑窗模块实例。
- 玩家尺度复核保持真实厘米标尺：门约 230 cm、自行车约 178 cm 总长、路灯约 330 cm；未对 MainHome 或整条街做失真的全局放大。
- 重新拍摄 5 张固定整体视图和 14 张玩家距离近景，覆盖路灯正反接头、自行车节点、巷道横杆、电线杆净距、墙面材质、校门、静态卷帘门及招牌雨棚。
- 最终验证：Map Check 0 Error / 0 Warning；Python 99/99；MainHomeInteractive 9/9；受保护源地图哈希保持不变。

## 2026-08-05 P4 玩家视角精修

- 新增可步行短 T 字路口，替换原先街尾平面封墙：主街在 X=6000 cm 处接入，南北支路、转角人行道、排水槽、雨水篦子和水坑均按厘米尺度落地并保留碰撞。
- 街尾增加一组正对主路的旧百货店立面，包含一体化招牌、中文“百货店”、雨棚、静态卷帘门、侧门、气窗、墙灯和生活杂物；暖色店面光与冷色路口补光让左右转向在玩家高度可辨认。
- P3 资产库由 5 种扩展为 10 种：新增实体墙座巷道横杆，以及“小卖部、百货店、修车铺、五金店”四种独立中文招牌文字网格。
- 6 根巷道横杆全部替换为单体 Static Mesh，杆体、套环、墙座和螺栓互相嵌合，端板落入两侧墙面 2 cm；不再生成悬空 Cube 横杆。
- 北、南巷道端墙增加 3 cm 厚连续饰面层，背面贴住墙体、可见面外移 3 cm，消除原墙与加高段之间的水平材质断层且无共面闪烁。
- 墙材质由固定双纹理权重改为共享世界坐标低频噪声：同一噪声同时驱动 0.22–0.62 尺度混合和 0–0.20 旧化强度，降低跨建筑规则重复。
- 路灯上部接头、背面斜撑、自行车车架/车轮/货架、巷道墙座均通过 19 张近距离审计图再次确认实体相交。
- 最终验证：场景验证 PASS；Map Check 0 Error / 0 Warning；Python 101/101；MainHomeInteractive 9/9；受保护源地图 SHA-256 保持不变。

## 2026-08-26 P5 玩家距离细节与 MainHome 室内家具

- 新增 6 个 Geometry Script 一体化 Static Mesh 资产、15 个非阻挡实例：
  - `SM_P5_LoadedLaundryRack`：5 个已挂载衣物的晾衣架；
  - `SM_P5_OldServiceDoorTransom`：3 个带门框、气窗、五金和无漏光遮盖的旧服务门；
  - `SM_P5_WallLampGooseneck`：3 个墙座、弯臂、灯罩和灯泡均实体连接的墙灯；
  - `SM_P5_ShopShelfStocked`：1 个带五层货架、纸箱、罐装物和标签的室内货架；
  - `SM_P5_CounterDisplay`：2 个柜台秤、收银机、罐装物与包裹陈列组合；
  - `SM_P5_TallPharmacyCabinet`：1 个窄型玻璃药柜，含门、把手、抽屉、瓶罐和盒装物。
- MainHome 新家具全部放在柜台后方或后侧墙面，统一设置为 `NoCollision`；门、卷帘门与玩家主通道的碰撞归属保持不变。
- 删除了旧的零散货架 Cube 与 7 个单独存货 Cube，用三个完整的玩家距离资产替代，减少了近景拼接感。
- 修复 P5 服务门材质槽位映射：门板、锈蚀金属、玻璃和污渍均进入其正确的区域 ID；没有以纯黑色贴片伪造破洞。
- 五个固定视图重新渲染，并追加 4 个 P5 专项近景审计：室内货架、柜台陈列、药柜、服务门密封与墙灯贴合；总计 23 张 1440×810 审计图。
- 已查明可选官方免费导入路径：Fab 可由已登录用户领取免费家具资产后导入。本轮没有自动领取或下载任何外部资源，避免把账户授权和下载状态耦合到无人值守的场景重建流程。
- 最终验证：`OTS_BUILD_SUCCESS actors=757 generated=683 cameras=5`；`OTS_CAPTURE_SUCCESS count=5`；`OTS_CONTACT_AUDIT_SUCCESS count=23`；场景验证 PASS；Map Check 0 Error / 0 Warning；Python 103/103；MainHomeInteractive 9/9；原始 Blockout SHA-256 未变。

## 2026-09-06 P6 近景支撑与材质复核（进行中）

- 重新检查 P5 的截图发现：测试通过并不代表近景合格。货架标签实际悬在商品中间，商品底部离层板有间距；台面物件拥挤重叠；家具木纹误用了电线杆 UV 图集。
- 已保存重建前地图、报告和同机位截图到 `Saved/CodexOutputs/OldTownSchoolStreet/P6_Before/`，其中新增 3 个室内全景/台面机位，近景合计 26 个。
- `P6_Before` 用于对比留证，不是完整资产回滚包：共享材质和网格按原路径更新，仅恢复旧地图不能还原所有旧外观。
- 代码已修正货架支脚和商品落点、价签安装位置、柜台布局、药柜内容遮挡和把手根部连接；正在进行 UE 实际重建验收。
- 已从 Poly Haven 官方下载并校验 Wood Table Worn 的三张 2K CC0 PBR 贴图，替换家具上的错误图集；墙面改为细尺度抹灰加大尺度污渍，路面和积水共用路面纹理。
- 新增实际网格边界支撑/重叠检查及 6 项单元测试；当前 Python 109/109。首轮 UE 运行被审计器名称匹配错误拦住（实际 Actor 带 `_01` 后缀）；已修正并重跑，尚未以旧报告宣称通过。
- 验证器新增截图新鲜度检查：5 张整体图和 26 张近景必须晚于目标地图重建时间。
- 看完全部 31 个机位后又发现两类旧问题，已补修：P3 招牌只反转字序、没有反转字形内部坐标，导致汉字镜像；T 字路口南北端新增窗户与背景原有窗户重叠，已把端窗 X 从 6180 移到 6040 cm。
- 新增字形朝向和窗户包围盒重叠回归测试；Python 当前 115/115。窗户检查先在旧位置上实际报错，确认能拦截北端被暗处隐藏的重叠，不是仅从截图猜测。
- 原生 MainHomeInteractive 回归 9/9，通过报告位于 `P6MainHomeTestReport/index.json`。正在刷新包含招牌及窗户最终修正的整套验收结果（`P6Accepted*.log`）。

### 尚未达到参考图的部分

- 当前仍是可进入的程序化场景原型，不是参考概念图级别的写实成品；本轮没有把玩法级别/全场景美术验收伪称为完成。
- 金属、商品包装和玻璃仍偏简化；P3 招牌字形方向将修正，但 20×20 网格字形仍有可见台阶，需要后续更精细的字形或贴图。
- 墙面大块规律霉斑减弱后，巷内墙根的局部潮湿、雨痕与贴纸仍不足；路面湿润边缘、砖缝、局部反射和整体灯光仍需下一轮美术调整。
- 现有 31 个固定视角覆盖主要街道、巷道、路口、商铺内外和关键接点；不等价于完整实时玩家巡游或所有资产每一个面的检查。
