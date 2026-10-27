# 整图表面修补接续记录

2026-10-09，当前地图 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。

地图 SHA256：`1015c11b5ccc54775eef291d501d4246ea3958c372fcfc56b4c00c253bd2a088`，7768 Actors。

本轮从用户保存的 7765 Actors 地图继续，保留新增的 `BP_ItemPickup`、`PointLight`；只增加 3 个检查相机。工作目录：`Saved/CodexOutputs/SurfaceSeparation_20261009`。

- 3457 个可见组件采用毫米级恒定材质位移，最大位移向量长度 2.205 mm。物理布局保持原位。
- 73 扇窗的框采用独立 V3 渲染网格：边缘退让 2.5 mm，框渲染深度 20.63 cm；原组件变换、框的简单碰撞和隐藏玻璃碰撞保持。可见玻璃与轨条留出间隔。
- 20 种原始配件通过独立网格修正内部重叠面；工具箱另按实例缩放加大最小分离。原始 Yastar 网格和材质保持，所有新增资产在 CodexGenerated。
- 27 个绿色房号牌标识 201–209、301–309、401–409。数字与底牌间距从 8.75 mm 缩至 1 mm。
- 保存后独立重载：2961 项检查通过，3769 通行采样、1170 楼梯采样通过，27 房/4 层及 MainHome 互动结构保留，3 个其他地图指纹保持。
- 实际渲染三角导出 1635500 个，覆盖 8488 个可见组件。扫描 1482494 个面，包含非轴向面与组件内部；检测距离 0.3 mm、每个相交面片面积至少 1 cm²。可见重叠残留 0、精确重复盒体 0；562 组埋藏面有遮挡分类证据，其中 41 组完成闭合网格内部射线复核。
- 15 张实景截图绑定上述保存地图指纹并逐张视觉审查 PASS，4 批自有辅助编辑器正常退出、临时灯清零；本目录 `SurfaceRepairAudit.json`、`FinalReview.json` 发布检查 PASS，统一 `Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json` 已指向本轮证据。

接续只读 `BuildReport.json`、`ArchitectureAudit.json`、`SavedScanSummary.json`、`FinalReview.json` 的摘要。`Applied.json`、`Refined.json`、`RefinedDepth.json` 已存在，不能重复应用这三个修补阶段。后续改地图前先核对当前地图指纹和用户编辑器状态；不重建酒店，不回滚用户保存对象。

独立重载检查入口为 `AuditOldTownSurfaceRepair.py`；截图使用 `CaptureOldTownHotelViews.ps1`，最终发布使用 `FinalizeOldTownSurfaceRepair.py`。临时检查灯和辅助编辑器必须有清理、正常退出记录。原 V4 Blender 文件是结构设计源；本轮表面修补的实际来源是保存的 UE 地图、独立资产和 `GeometryAfter.json`。
