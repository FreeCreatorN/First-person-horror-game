# UE5 灰盒精简接续点

2026-10-07：路灯位置、旅馆标牌与本轮验证已完成。后续从此记录接续，不重复生成。

- 活动地图 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`；SHA256 `ec2be07dd8af07628a89079dbf1ea4088b3bb49aafe2723d2db5cd6f23b96054`，7282 Actors。
- 本轮 `Saved/CodexOutputs/StreetRefinement_20261007`：9根路灯移到靠路缘处，轴线距车道边35cm，主街杆底距建筑约130.44cm；不贴墙。8盏原单向向下Spot灯随杆移动，参数保留；电线杆5部件、3根终端电线一起调整。只修改25个原对象，新增9张旧旅馆标牌及5个检查机位。
- 700cm车道、180cm步道、5条已开放窄巷保持；路灯避开门口和巷口。3张楼层房号方向牌、4张电梯停用告示、清/污布草库标牌均无碰撞；9张标牌材质V方向已修正，新素材在 `/Game/CodexGenerated/OldTown/StreetRefinement_20261007`。
- 11个生成门窗蓝图现位于 `/Game/CodexGenerated/OldTown/Blueprints/Openings`；原 `/Game/Yastar/Blueprints/OldTownOpenings_20261004` 已清空移除，生成/装配/探针脚本已改路径。两图共844实例、12846对象记录状态一致，原组件模板一致，旧引用为0；备份与验证在 `Saved/CodexOutputs/OpeningRelocation_20261007`。
- 70×10.4m四层旧招待所，街侧1.8m长廊；首层101/102加宽双人房，上三层各13间，共41间。客房含私用卫浴、衣柜、床、书桌、外窗和房号。
- 南北双梯/双出口，真实楼板洞口和门槛；中央封闭电梯井及楼层布草间。首层前台/会客/茶餐/独立备餐/公共与员工WC/办公室/独立清污布草库。湿区叠层，备餐避开卫浴投影。
- 修正家具与床、墙、管井交叠；洗手盆朝室内、卫浴门避马桶、外门不扫过长廊。4处单面日光灯、旧绿墙裙与漆面缺失形成废弃氛围。
- 前轮 `Saved/CodexOutputs/HotelOperations_20261006`：15种新配件、33处摆放、11碰撞体、5机位，共49个新对象；电话/登记簿/铃/停走挂钟、相向软垫候客椅/茶几/行李、早餐座椅/台盆/壶、办公桌椅、清布草堆、污布草车/袋、140cm双扇电梯门面及按钮。
- 本轮独立重载通过434项街区检查、2643项建筑检查、68项营业细节检查；2185处街区通行、4066处酒店通行、762处楼梯采样通过。除列明25个对象，其余原对象不变，共享素材未改；保存前用户变更已保留。L_Main/章节及历史预览未改，用户PointLight删除保留。
- 统一入口 `Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json` 指本轮 `StreetRefinement_20261007`，9报告已发布。当前5图为4张临时检查补光图及1张仅现有街灯的夜景；全部匹配当前地图，补光清理为0，3个当前截图辅助进程正常退出。前轮截图和迁移报告保留为历史证据。
- 平面图 `Saved/CodexOutputs/HotelArchitecture_20261005/DesignPlan.png`；说明 `docs/OldTownHotelArchitectureProgress.md`；Blender结构源及49配件在 `SourceArt/OldTownHotelArchitecture_20261005`，活动门窗在UE装配。
- 新配件源 `SourceArt/OldTownHotelOperations_20261006/OldTownHotelOperationsKit.blend`，说明 `docs/OldTownHotelOperationsProgress.md`。标牌源在 `SourceArt/OldTownStreetRefinement_20261007`；本轮说明 `docs/OldTownStreetRefinementProgress.md`。当前复验 `Scripts/AuditOldTownStreetRefinement.py`，归档 `Scripts/FinalizeOldTownStreetRefinement.py`；`Applied.json` 为防重入标记，勿重新执行装配。重新导出/导入素材需更新指纹。
- 机械开关审计使用临时副本并销毁，不修改实际门实例；此前编辑器实例测试状态曾影响保存，已重建酒店门并独立重载确认修复。
- 限制：本轮未新增门窗玩家输入或运行电梯；未复验完整运行时玩家巡游。后续可继续交互、材质旧化和环境叙事。用户当前打开的编辑器与玩家蓝图修改不由辅助进程关闭或覆盖。

覆盖更新本短记录；完整日志留磁盘，工具只输出短摘要。聊天连接历史调查在 `docs/UE5GreyboxChatRecovery_20261004.md`：上下文超限及远端响应断流已确认，具体网络根因未确定。
