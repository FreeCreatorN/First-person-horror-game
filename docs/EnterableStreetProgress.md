# 老城区可进入建筑续作记录

记录更新：2026-10-05。续接聊天「查找UE5灰盒生成聊天记录」及「生成UE5老城区商铺灰盒」。

## 2026-10-05 窄巷与路灯修订（最新）

当前地图 SHA256 为 `f288e7c72d528eea2b44b443f1a1a333ccd8b97341fe080ceb5f54c0f625b85f`，5633 Actors。五条150cm小巷重新开放并铺平；六根路灯避开门口和巷口，八个光源改为向下Spot；700cm机动车道、180cm人行道与既有铺装边界保持。电线杆及线缆、墙面设施和两花盆同步避让。最新外部保存只删除了PointLight，本轮保留该删除。

全部11份独立重载审计、250项街道检查、969个通行采样及141项测试通过，246份既有共享素材未改变。五张新图已逐张查看，捕获正常退出、补光无残留且未保存截图改动。18份当前报告已发布。详见 [OldTownStreetAccessLightingProgress.md](D:/UE/Project/HorrorGame/docs/OldTownStreetAccessLightingProgress.md)；[CurrentEvidence.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json) 指定本轮证据，以下阶段的哈希和图片均为历史版本。

## 2026-10-05 酒店增量优化（历史版本）

当前原街道保存 SHA256 为 `2687cbab9a35580326cc2f5bb372be692f4e2d7cdda3dcadd6eb3a5837b32aa7`，5629 Actors。24 张客房床垫改为米白布面；201–408 共 24 个房号牌与独立 3D 数字贴墙安装；前台背景增加酒店文字。保留原尺寸、碰撞和通路，未制作玩家开关输入。

493 项本轮检查、全部原有保存后审计和 141 项测试通过；四张受影响机位已逐张复核，捕获正常退出且补光无残留。原 5579 Actor 除 24 张床垫材质覆盖外保存状态保持，219 份共享素材及用户灯光、主地图、章节灰盒、预览均不变。完整成果见 [OldTownHotelPolishProgress.md](D:/UE/Project/HorrorGame/docs/OldTownHotelPolishProgress.md)，最新验收见 [FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005/FinalReview.json)。[CurrentEvidence.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json) 标明 18 份当前报告和四张新图；旧 17 图属于下面的合入历史。

## 2026-10-05 酒店与独立门窗合入（历史版本）

原街道 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet` 已保存并独立重载通过，当前 SHA256 为 `7067f6e9e3227b2e00dd6aa8b9dca2e0bf34848980d1c54eee084dd34ef0d3d0`，5579 Actors。四层酒店含接待大堂及 24 间客房；全街 315 个独立窗模块、53 个独立门模块，2 处街角休息区，8 块屋顶盖板及招牌比例已修正。用户新增 PointLight 的位置、160 cd 强度及组件属性保留；L_Main、章节灰盒与修正版预览未改变。

全部保存后审计与 141 项测试通过，17 张最终截图已逐张复核，5 个捕获进程均正常退出且无补光残留。夜景使用实际场景灯光；其他检查图的临时补光不写入地图。门窗已有独立铰链及跟随碰撞，尚未实现玩家开关输入；编辑器碰撞采样不替代实时玩家巡游。

当前详细成果见 [OldTownHotelOpeningsProgress.md](D:/UE/Project/HorrorGame/docs/OldTownHotelOpeningsProgress.md)，验收见 [FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/FinalReview.json)。canonical 报告已更新，以 [CurrentEvidence.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json) 清单及其当前截图路径为准。下方章节是历史版本，数字、哈希及截图不可作为当前状态。

## 2026-10-04 DetailPolish 细节优化（历史版本）

既有目标 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet` 已保存为 SHA-256 `06E34C6F95BE4E4D3E57205BAE451BBB80947142EADA5F15E21756E49721FD9F`，共 5877 个 Actor、4430 个结构实例。本轮保持 108 块完整绿色矩形楼梯封板、69 个成人尺度家具部件、4 个人体参照和 MainHome 原有交互；实际道路照明仍仅有 8 盏路灯，未新增灯光。

- 通过 Blender MCP 生成 46 个独立倒角轮廓网格，并导入 563 个视觉实例：162 个完整梯段、81 个平台、291 个内窗框及 29 个门组件。原 1502 个踏步、81 个中间平台和 29 扇门叶及门把隐藏渲染，保留原碰撞设置；门把原有 `NoCollision` 保持。新梯段和平台提供连贯表面，原规则绿色整板不变。
- 29 个 `EntryFloorFill` 仅补齐门洞墙厚内侧局部法向 n=0..19.5 cm 的地面，顶面与楼层同高，没有门前外凸台阶；门口按三条轨迹、5 cm 间隔的细致碰撞支撑检查通过。
- 48 对铺地的共面重叠裁为 0；按高度及材质分组，前后覆盖范围的对称差为 0，保留原铺装覆盖。原通行带五条轨迹的真实胶囊碰撞及地面支撑检查全部通过。
- 街尾层间线脚、檐口、招牌和雨棚共 6 个部件重新贴墙；5 个电气部件沿 Y 移动 -460 cm，后侧贴到 X=9000.5 cm，并增加 4 个独立墙装支撑件，保持道路开口。
- 新门视觉组件含面板、圆形执手和每扇 3 个铰链，仍固定开放 90°，没有新增开关门交互。
- 291 个内窗框最终采用四格窗，增加 3 cm 宽十字分隔，使用已有磨旧木材质，未新增自发光；内框源网格闭合且无重复重叠。

[BuildReport.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/BuildReport.json) 及 [SavedVerification.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/SavedVerification.json) 的最终 06E34C6F… 保存和独立重载通过。本版本重新加载后运行的 [DetailPolishAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/DetailPolishAudit.json) 为 3182 项、[ArchitectureSealAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/ArchitectureSealAudit.json) 为 6227 项、[RevisionAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/RevisionAudit.json) 为 458 项、[LightingCleanupAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/LightingCleanupAudit.json) 为 120 项，均 PASS、0 失败；[PythonTests.log](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/PythonTests.log) 为 115/115 通过。碰撞采样不替代实时玩家巡游。

最终 06E34C6F… 地图的 [DetailTriangleAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/DetailTriangleAudit.json) 为 779 项、0 失败。实际导入三角面测得最小垂直净高为 230.847372955 cm，高于 225 cm 目标；规划解析的保守值为 230.6875 cm。三角面净高和碰撞采样均不是完整实时玩家巡游。6 个最终机位已全部生成并逐张查看，PNG 与 metadata 均匹配 06E34C6F… 保存地图。稳定 [FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/FinalReview.json) 的场景与图像核验为 PASS，capture_count=6。可查看 [内窗四格框](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Renders/CAM_Polish_InnerTrim.png)、[齐平门口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Renders/CAM_Polish_EntryFloor.png)、[连续楼梯底面](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Renders/CAM_Polish_Stair.png)。楼梯、门窗、内窗框、门口地面和背街转弯为 Unlit，街尾路口为 Lit；视口模式已实际设置并回读，未增加补光。捕获辅助进程采用有界清理，exit=-1 不表示正常退出。

源文件为 [OldTownDetailPolish.blend](D:/UE/Project/HorrorGame/SourceArt/OldTownDetailPolish_20261004/OldTownDetailPolish.blend)，独立 FBX 保存在 [OldTownDetailPolish_20261004](D:/UE/Project/HorrorGame/SourceArt/OldTownDetailPolish_20261004)。[DetailPolish_20261004/Before](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Before) 保存修改前 F5CB706E… 地图、报告及截图。本轮 09:03 完成的场景核验中，L_Main 保持 BA484854… 基准，原始 Blockout 为 D15F1749…。收尾检查发现 L_Main 在 10:58 另有保存为 EE46F2CF…；目标场景仍为 06E34C6F…，Blockout 未变。已保留 L_Main 当前较新版本，没有覆盖或回退；操作者未确定，差异记入 [ExternalMapChange.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/ExternalMapChange.json)。

## 2026-10-04 建筑拼合与门窗优化（已完成历史版本）

本节数量、哈希及五机位验收属于 F5 版本；当前细节优化结果以上方最新章节为准。

既有目标 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet` 已保存为 SHA-256 `F5CB706E2A45E20DCD2EF239246587604A0D147E3ADEE4A7A784BAB6E76E39F4`，共 5281 个 Actor、4397 个结构实例。29 个单户主要入口、69 个成人尺度家具部件、4 个人体参照及 MainHome 原有交互保持。

- 27 个楼梯核心改用 108 块整高、规则绿色封板，替换逐踏步叠片。中部 20 cm 间隔完全填满，靠墙和后侧以 25 cm 宽封板补齐；140 cm 宽梯段和转弯平台保持，整高板无跨层重叠。
- 382 个楼板、屋面模块的边界向墙体内部搭接 0.5 cm，墙角内侧同样搭接 0.5 cm，封闭墙板与楼板拼合接缝；保留实际楼梯开口和通行空间。
- 29 个主要入口各增加一扇实体门叶，固定打开 90°。本轮没有增加开关门交互；MainHome 原有门及卷帘交互仍独立保持。
- 29 栋建筑共布置 291 个窗模块，每个对应真实墙洞、贯穿墙厚的窗套及阻挡玻璃。窗按各楼栋实际层高布置，不穿楼板；原窗口及 42 个学校迁移窗已替换，清除重复叠窗。

[ArchitectureSealReport.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/ArchitectureSealReport.json) 为 PASS，[ArchitectureSealAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/ArchitectureSealAudit.json) 的 6194 项建筑专项检查为 0 失败，包含实际玻璃阻挡碰撞、旧窗残留、108 块整板、跨层不重叠及结构边界实测。[SavedVerification.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/DetailPolish_20261004/Before/SavedVerification.json) 独立重载核对 F5CB706E… 地图通过；本版本 [RevisionAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/RevisionAudit.json) 为 492 项、[LightingCleanupAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/LightingCleanupAudit.json) 为 90 项、[PythonTests.log](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/PythonTests.log) 为 115/115，均 PASS。Map Check 为 0 错误、0 警告；采样不替代完整实时玩家巡游。

报告位于 [ArchitectureSeal_20261004](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004)，其 [Before](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before) 保存修改前 E6BA8307… 地图、报告和截图。受保护地图保持进入本任务时的基准状态；`L_Main` 的 BA484854… 与原始 Blockout 的 D15F1749… 未因本轮改造变化。

五张 1280×720 本轮截图已生成并逐张查看，[FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/FinalReview.json) 核验 PASS，`capture_count=5`，PNG 与 metadata 均对应 F5CB706E… 地图哈希。[规则楼梯封板](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Seal_Stair.png)、[实体门与窗](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Seal_DoorWindow.png)、[室内窗套](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Seal_WindowInterior.png)、[背街转弯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Cleanup_TurnNorth.png) 使用 Unlit 核对几何；[街尾路口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Renders/CAM_Cleanup_Junction.png) 使用 Lit，五个机位的视口模式均已回读确认并记录 `view_mode_verified`。Unlit 结构预览未加补光，不代表实际照明效果；实际地面道路照明仍仅有 8 盏路灯，地下 2 盏 UI 预览灯保持隔离。图中的新门固定 90° 开放，本轮没有新增开关交互。隐藏捕获辅助进程采用 PNG 完成后的有界清理，收尾时未残留 UnrealEditor 进程；截图核验通过不保证辅助进程正常退出。

后续在此版本使用 [SealOldTownArchitecture.py](D:/UE/Project/HorrorGame/Scripts/SealOldTownArchitecture.py) 继续建筑优化，避免旧全量构建覆盖新门窗和整板方案。下方灯光道路章节为已完成的 E6 历史版本。

## 2026-10-03 路灯清理与街尾路口（已完成历史版本）

本节数量、哈希、报告及五机位验收属于 E6 版本；当前建筑优化状态以上方最新章节为准。

当前已保存目标为 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，地图 SHA-256 为 `E6BA8307897D19B919DBB852D166ADCE0DBBFD17D21451C30FDFE5397240B3BE`。关卡含 6455 个 Actor、5632 个结构实例；29 个单户主要入口、绿色楼梯封板、零门前凸起门槛及 69 个成人尺度家具部件维持上一轮结果。

- 删除 162 个场景灯 Actor：124 盏楼层室内灯、36 盏道路补光/店面/学校/巷道灯，以及 DirectionalLight、SkyLight。现在地面场景只有 8 盏路灯 PointLight，包含原 6 盏及街尾 T 字路口新增 2 盏；9 座灯杆中的原故障杆 `StreetLamp_03` 仍不点亮。
- 地下 `BP_InventoryCharacterPreview` 的 2 盏 SceneCapture 专用 UI 灯保留，不覆盖地面场景，背包预览功能保持。全地图实际灯组件数为 10，不能把地面场景的 8 盏写成全地图光组件总数。
- 所有非路灯灯管和亮窗的自发光均通过当前地图网格组件上的材质覆盖关闭，共享材质没有修改；与雨棚一体的灯槽只关闭发光，保留雨棚和建筑附件。
- 原 7 座路灯从楼间夹缝移到主街实际铺装区域 Y±500 cm，灯头继续朝道路，保留主街 120 cm 行走带。5 处宽 150 cm 的非公共楼间夹缝在入口处封墙；真正主巷仍为墙间 320 cm、预留净通行 280 cm。
- 街尾东侧建筑立面从 X=7700 cm 移到 X=9000 cm，后退 13 m。街尾横向道路宽 7 m，范围收至 Y±2075 cm；南北背街均延长到 X=8250 cm，横街两端转向西接回背街，取消原 Y±3900 cm 的场景边缘终端，形成闭合路网。北、南路端各补一条宽 180 cm 的路缘，人行道与东侧建筑之间仍留 5.7 m 退距；原悬空招牌、窗户和电气附件同步归位。
- 从主街进入横街，再经 X=7900 cm / Y±1915 cm 转向西侧背街至 X=6200 cm 的两条完整转弯路径，均通过实际胶囊碰撞及地面支撑检查；五处夹缝封墙也核对了实际边界与阻挡碰撞。

本轮 [LightingCleanupReport.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/LightingCleanupReport.json) 为 PASS，[LightingCleanupAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/LightingCleanupAudit.json) 的 100 项灯光、闭合路口及封墙检查为 0 失败。原有 [RevisionAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/RevisionAudit.json) 的 3776 项检查也通过；[SavedVerification.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/SavedVerification.json) 独立重载核对最新哈希为 PASS，Map Check 为 0 错误、0 警告，[PythonTests.log](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/PythonTests.log) 为 115/115 通过。采样检查不替代实时玩家巡游。

本版本报告位于 [LightRoadCleanup_20261003](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003)，同时更新 `EnterableStreet_20261002` 中对应报告。[Before](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/Before) 已保存修改前 `9D18E94A...` 地图及报告。[ProtectedMapBaseline.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/ProtectedMapBaseline.json) 记录 `L_Main` 在本任务首次只读清单前已于 19:47 保存为 `BA484854A90452653F201682A8288C532A70D8762B447E39836F64AAB3AE1EDA`，本轮保留该进入任务前状态，原始 Blockout 仍为 `D15F1749...`，不以旧会话的 `200E70...` 作为本轮基准。

五张 1280×720 复核图像已全部生成，[FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/LightRoadCleanup_20261003/FinalReview.json) 的地图与截图核验为 PASS，`capture_count=5`，PNG 及 metadata 均匹配本版本 E6BA8307… 地图哈希。[主街](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_MainStreet.png)、[街尾路口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_Junction.png)、[原路灯夹缝](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_FormerLampGap.png) 使用 Lit；[北侧转弯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_TurnNorth.png) 与 [道路总览](D:/UE/Project/HorrorGame/Saved/CodexOutputs/ArchitectureSeal_20261004/Before/Renders/CAM_Cleanup_RoadPlan.png) 使用 Unlit 结构预览，编辑器视口模式已实际设置并回读确认，metadata 的 `view_mode_verified=unlit`。两张结构图没有新增照明，不代表实际路灯照明效果。隐藏捕获辅助进程在 PNG 完成后采用有界清理，图像核验通过不保证辅助进程正常退出。下方人体尺度章节的六张图像仍属于历史版本。

本章仅记录已经完成的 E6 灯光与道路版本，后续建筑拼合、封板及门窗优化见上方最新章节。

后续在既有地图使用 [CleanupOldTownLightingAndStreetEnd.py](D:/UE/Project/HorrorGame/Scripts/CleanupOldTownLightingAndStreetEnd.py) 继续本轮修订，不要为了查看结果重跑旧全量构建。`ConvertOldTownBuildings.py` 已按 `street_lamps_only` 策略禁止重新生成 124 盏室内灯。

## 2026-10-03 人体尺度与街道布局修订（历史版本）

以下数量、哈希及六机位验收属于灯光清理前版本，当前状态以上方最新章节为准；旧章节中的同名报告引用可能已由最新报告覆盖。

最新目标仍为 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。本次已保存的 [BuildReport.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/BuildReport.json) 为 PASS，地图含 6612 个 Actor，其中 5632 个结构实例。以下数据覆盖当前版本；后面的 72 个家具实例、旧地图哈希及 MCP 用量阻塞说明保留为前一轮历史。

- 29 栋建筑各保留一个主要入口；`DoorThreshold` 实例为 0。楼梯侧面改为连续绿色封板，保留实际踏步、平台和上下楼通道。
- 街道重铺包含 39 个地面模块及 4 块巷道隔墙。主街宽 700 cm，人行道铺装宽 180 cm，其中预留 120 cm 连续通行区域。
- 巷道墙间宽为 320 cm；物件避让与通行审计使用其中 280 cm 的预留净通道。两项宽度分别表示几何墙距和通行保留区域。
- 以 180 cm 高、50 cm 肩宽人体重新校准家具；碰撞检查仍使用半径 34 cm、高 180 cm 的胶囊。桌为 150×90×80 cm，椅为 52×52×100 cm，座面高 48 cm，柜体为 140×70×200 cm。
- 床架为 155.94×224.28×97.5 cm，床垫为 138×207.9×15 cm；保留床垫底面离地 44 cm、顶面及枕头底面离地 59 cm。左右柜门仍为独立铰链部件。
- 当前正常家具为 69 个部件实例：12 张桌、12 把椅、7 组床的 21 个部件及 8 组柜的 24 个部件。`BLK_L_Filler_02_Mass` 二层无法容纳成人尺寸床及预留通行空间，因此未放床，也未缩小模型。另有 4 个人体参照实例，分别用于桌椅、巷道、卧室和学校对比，不计入家具数量。

本次确实通过 Blender MCP 修改源网格并导出 9 件资产，包括 8 个家具部件和新增人体参照。新源文件为 [OldTown_HumanScaleRevision.blend](/D:/UE/Project/HorrorGame/SourceArt/OldTownScaleRevision_20261003/OldTown_HumanScaleRevision.blend)，尺寸、装配偏移与材质见 [ImportManifest.json](/D:/UE/Project/HorrorGame/SourceArt/OldTownScaleRevision_20261003/ImportManifest.json)，FBX 轴向复核见 [UnrealAxisVerification.json](/D:/UE/Project/HorrorGame/SourceArt/OldTownScaleRevision_20261003/UnrealAxisVerification.json)。所有网格导入比例为 1，家具实例继续使用 `NoCollision`。

布局依据为 [RevisionPlan.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/RevisionPlan.json)。当前 [RevisionAudit.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/RevisionAudit.json) 为 PASS：3776 项检查、0 项失败。保存后独立重载的 [SavedVerification.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/SavedVerification.json) 已更新并通过，核对 29 栋建筑、69 个家具实例及 123 个资产引用，地图哈希与最新 BuildReport 一致。

当前地图 SHA-256：`9D18E94A645ADB76B6D0F4914234D34150922D29AC1D4BD1C6954F91C28A84DE`。本次完整报告及修订前快照位于 [StreetRevision_20261003](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/StreetRevision_20261003)。原始 Blockout 与 `L_Main` 哈希保持不变。

最终六个修订机位已全部生成并逐张查看。每张 1280×720 PNG 及 metadata 均匹配上述最终地图哈希，[FinalReview.json](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/FinalReview.json) 的图像与保存地图核验为 PASS。可查看 [桌椅与人体](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/Renders/CAM_Revision_TableHuman.png)、[完整道路总览](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/Renders/CAM_Revision_RoadPlan.png)、[楼梯封板](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/Renders/CAM_Revision_StairClosed.png)、[平整入口](/D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/Renders/CAM_Revision_EntranceFlush.png)。道路总览采用 18000 cm 俯视高度、90 度横滚、60 度视野及 2.5 曝光补偿，完整覆盖街区和校园；独立重载后 Map Check 为 0 错误、0 警告。

截图辅助进程在 PNG 完成后采用有界清理，收尾时未残留编辑器进程；图像核验通过不表示辅助进程正常退出。碰撞采样和部件审计也不替代完整实时玩家巡游。旧机位截图保留历史用途。

## 前一轮可进入建筑结果（历史）

目标仍为 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，对应 `Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap`。

- 29 栋原实心建筑已转换为独立墙板、门洞、楼板、屋面、楼梯与平台；共 110 层、81 段层间楼梯。
- 清理相邻建筑重复生成的 10 块门槛后，关卡为 3576 个 Actor，其中 2604 个结构网格实例。
- 从原场景复制或拆出 100 个可复用网格，320 个组件换用独立资产，14 个组合 Actor 拆成 99 个语义部件。
- 新结构采用 8 类独立网格；一块墙板、楼板、踏步或平台对应一个简单盒碰撞，保留真实门洞和楼梯口。
- 8 个 Blender 家具网格已导入并放置 72 个实例，组成 40 组家具，分布在 12 栋建筑；包含 8 组床。
- 家具为床架、床垫、枕头、木桌、木椅、柜体和左右柜门。床、桌分别进入既有 `Meshes/Bed`、`Meshes/Table`，其余进入 `Meshes/Furniture`、`Meshes/hOUSE`；保留独立部件和柜门铰链原点。
- 家具显式使用 `NoCollision` 配置。修复了网格异步加载后恢复 `BlockAll` 的问题，保存后重载再次检查全部 72 个实例。
- MainHome 的四个网格组件及交互区域检查通过。本轮操作未编辑 `L_Main`。

源模型与 FBX 保存在 `SourceArt/OldTownModular_20261002/`，包括 `OldTown_OriginalFurniture.blend`、`ImportManifest.json`、`ModelValidation.json` 与 `UnrealAxisVerification.json`。

本轮已通过 Blender MCP 连接 Steam Blender，读取源场景、视口和 8 个家具网格的实际边界。FBX 到 UE 的轴向为 X 不变、Y 翻转，累计边界误差约 0.000155 cm。通过 MCP 调整视口的后续操作被自动审批服务额度限制拦截，没有执行；本轮没有以其他方式替代这项被拦截操作。

## 验证证据

报告目录：`Saved/CodexOutputs/EnterableStreet_20261002/`。

| 检查 | 当前结果 | 文件 |
| --- | --- | --- |
| 保存后独立重载 | PASS；29 栋建筑、72 个家具实例、122 个资产引用均通过 | `SavedVerification.json` |
| 入口、室内通道、楼层支撑、楼梯净空 | PASS | `CollisionValidation.json` |
| 主街至所有 29 个建筑入口的地面连通 | PASS | `SavedVerification.json` 内 `collision.ground_connectivity` |
| 碰撞对照 | 实墙被胶囊检测到，防止物理未注册产生假通过 | `collision.blocking_wall_control` |
| 家具位置、网格、材质、碰撞及组合落地 | 72/72；同层组间包围盒无重叠，床垫与枕头接触通过 | `FurnitureAudit.json` |
| Map Check | 0 Error / 0 Warning | `SavedVerification.log` |
| Python 回归 | 115/115 | `PythonTests.log` |
| MainHome 原生回归 | 9/9 | `MainHomeTests/index.json` |
| 六个复核机位 | 图像文件和地图哈希一致性通过 | `FinalReview.json`、`Renders/*.json` |

胶囊按半径 34 cm、高度 180 cm、最大跨步高度 45 cm 采样。楼梯按踏步高度不超过 18 cm、踏面 28 cm及净宽至少 110 cm检查。采样检查不是完整实时玩家巡游，也不是 AI 导航网格验收。

只读加载项目 `BP_Character` 后，实际默认胶囊为半径 34 cm、半高 88 cm，最大跨步 45 cm，见 `PlayerCapsule.json`；采样高度比该默认值高 4 cm。

六个 1280×720 机位为街道整体、MainHome、商铺入口、校舍入口、楼梯和卧室，位于报告目录的 `Renders/`。已逐张查看并确认门洞、室内楼梯与床柜摆放。室内灯光仍偏亮，招牌近景细节仍粗糙。

截图生成成功不代表截图进程正常退出：本轮部分隐藏编辑器在写入图像后异常退出，最后一次关闭复核也未在 60 秒内退出，已清理该自建截图进程。脚本已改为延后执行关闭命令，但正常退出尚未验收；此问题记录在 `CaptureQuitVerification.json`。六张图像各自记录了最终地图哈希并独立校验 PNG 尺寸与内容长度，不能把进程退出状态写成通过。

目标地图 SHA-256：`B6A2B0552907CC27F664C1D39E43F6C2B27A455A6AA725FDCF81EDDC1DABF081`。

受保护原始灰盒 `/Game/Yastar/Maps/Blockout/L_Chapter01_Blockout` 的 SHA-256 仍为 `D15F1749800233495469ACB72E60A7C0D837319EECF57FB14BFF25FDBBD9DE09`。

备份位于报告目录：`Before_L_OldTownSchoolStreet.umap` 是本次转换前地图；`Before_SharedThresholdCleanup.umap` 与 `Before_FurnitureCollisionRepair.umap` 是后续修复前快照。地图快照并不包含全部共享资产回滚副本。

## 继续工作的入口

先读取本文件与当前 `BuildReport.json`，在既有目标关卡继续，不要仅为查看结果重新运行全量构建。

- `Scripts/VerifySavedEnterableOldTown.py`：只读重载验证。
- `Scripts/AuditImportedOldTownFurniture.py`：只读家具贴合和状态审计。
- `Scripts/CaptureEnterableOldTownViews.ps1`：逐机位启动隐藏 UE 编辑器截图，减少同一进程重复高分辨率截图导致的崩溃影响。
- `Scripts/ConvertOldTownBuildings.py`：29 栋建筑转换；重复共享门槛已在生成器中去重。
- `Scripts/ExtractOldTownReusableAssets.py`：既有 Meshes 根目录中的可复用部件。
- `Scripts/ImportOldTownBlenderFurniture.py`：导入与摆放 Blender 部件，明确设置 NoCollision 配置。
- `Scripts/BuildEnterableOldTown.py`：全量构建；重跑前要评估既有报告和资产复用状态。

当前完成的是可进入建筑和家具资产这一轮续作。室内装饰、局部照明和材质仍属原型阶段，后续仍需真人玩家巡游及美术精修。

