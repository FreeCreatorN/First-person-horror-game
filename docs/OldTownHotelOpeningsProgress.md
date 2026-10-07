# 老城酒店与独立门窗


本文件为酒店阶段历史记录。当前街道已完成窄巷与路灯修订，最新状态及截图见 [OldTownStreetAccessLightingProgress.md](D:/UE/Project/HorrorGame/docs/OldTownStreetAccessLightingProgress.md)；本文件的旧哈希、检查数量和图片不作为当前证据。

最新增量优化已完成，见 [OldTownHotelPolishProgress.md](D:/UE/Project/HorrorGame/docs/OldTownHotelPolishProgress.md)：24 张床垫改布面、24 个房号牌及前台字样，当前 hash 为 2687cbab…、5629 Actors。以下是上一轮合入阶段记录，17 张图和 5579 Actor 数量属于历史版本。

2026-10-05 合入阶段：酒店与独立门窗已合入原街道 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，保存后重新加载验收通过。

## 合入阶段成果

- 对街 East 四层楼改为老城酒店：一层接待大堂，上三层各 8 间客房，共 24 间；保留前侧公共走廊与北端楼梯。
- 共 315 个独立窗模块、53 个独立门模块。窗移除铁栏；固定框为 Static，铰链、扇、玻璃和阻挡为 Movable，阻挡跟随铰链旋转。
- 北、南街尾各有休息区，保留 320 cm 连接巷道；8 块后排屋顶盖板已对齐。
- 招牌源资产缩放错误已修复，UE 实测文字宽约 201.99 cm、高 48 cm；接待台另设独立检查机位。
- 用户后来添加的 PointLight 已保留：位置（6090，1690，1460）cm，强度 160 cd。原生导入重建灯光标识，其余序列化属性一致。
- 主地图 L_Main、章节灰盒及修正版酒店预览均未改变。

合入阶段地图 SHA256：`7067f6e9e3227b2e00dd6aa8b9dca2e0bf34848980d1c54eee084dd34ef0d3d0`，共 5579 个 Actor。

## 验收与证据

保存后独立重载的门窗组件、道路、灯光、建筑接缝、细节、楼梯三角面及酒店布局检查均通过；141 项 Python 测试通过。81 个楼梯连接的实际最小垂直净高仍为 230.847 cm。

17 张最终截图逐张查看，未见明显结构问题。16 张结构检查图使用临时补光，清理后残留为 0，且不保存关卡；NightFront 使用实际场景灯光，室内较黑。5 个捕获进程均正常退出，无强制清理。

本阶段历史验收为 [FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/FinalReview.json)；[VisualReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/VisualReview.json) 记录当时逐机位结论。当前权威清单 [CurrentEvidence.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json) 已由最新优化阶段更新。

原街道合入前完整备份：[L_OldTownSchoolStreet.umap](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/BeforeIntegration/L_OldTownSchoolStreet.umap)。源资产及招牌修复记录保存在 [SourceArt](D:/UE/Project/HorrorGame/SourceArt/OldTownHotelOpenings_20261004)。

门窗铰链与碰撞已准备好，玩家输入和开关交互尚未实现。此阶段为灰盒；通行验收采用编辑器碰撞采样，尚未完成实时玩家巡游。

## 最终图片

[正面](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/Renders/CAM_Hotel_Front.png) · [接待台](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/Renders/CAM_Hotel_Reception.png) · [客房](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/Renders/CAM_Hotel_Room.png) · [门](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/Renders/CAM_Openings_Door.png) · [窗](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/Renders/CAM_Openings_Window.png) · [实际夜景](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelIntegration_20261004/Renders/CAM_Hotel_NightFront.png)。

简短接续状态见 [UE5GreyboxCheckpoint.md](D:/UE/Project/HorrorGame/docs/UE5GreyboxCheckpoint.md)。

