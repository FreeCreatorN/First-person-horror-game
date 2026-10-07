# 老城街道通行与路灯修订记录

2026-10-05：修改已保存，独立重新加载、5 张截图逐张复核和当前报告发布均通过。

工作目录：`D:\UE\Project\HorrorGame`；目标地图：`/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。

当前地图 SHA256：`f288e7c72d528eea2b44b443f1a1a333ccd8b97341fe080ceb5f54c0f625b85f`；保存后共 5633 个 Actor。

证据目录：[StreetAccessLighting_20261005](D:/UE/Project/HorrorGame/Saved/CodexOutputs/StreetAccessLighting_20261005)。输入地图及报告备份位于其 `Before` 子目录，地图文件为 `L_OldTownSchoolStreet.umap`；`InputRebaseReport.json` 记录本轮输入与外部修改。

本轮重新开放南侧 3 条、北侧 2 条原封闭小巷，保留 150 cm 实际宽度，补齐连续地面并接入后巷。6 根路灯沿街移位，避开主家门口及巷口；9 根灯杆中现有 8 个灯源改为正下照射的 Spot，内外锥角 35°/55°，普通灯 130 lm、街口灯 190 lm，保留原照射半径。700 cm 机动车道和 180 cm 人行道均未改变。

2 个花盆移至后院。电杆 02 的 5 件组合整体沿 X 增加 90 cm，横担旋转 90° 沿街布置，绝缘子随组合转动；3 根电线保留另一端点并保持接线。墙面设施组 03 的 5 件沿 X 减少 35 cm，退出巷口。

只读输入对比确认新保存中在本轮开始前已删除 `PointLight`，没有其他增改；该外部删除已保留，未重建此灯。地面探测改用真实静态及动态地面射线，修正交互 trigger 被误认作支撑面的误报。

保存和独立验证均正常退出。141 项测试及 11 份审计报告通过；街道专项 250 项检查、969 个通行采样无失败。5633 个 Actor 的保存状态与本阶段预期一致；246 份既有共享素材未改变。

3 张临时照明检查图、2 张真实街灯夜景图均已查看通过。两个捕获进程正常退出 0，无强制清理；临时补光残留为 0，截图未改变保存关卡。18 份当前报告已发布，以 [CurrentEvidence.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json) 清单为准。酒店上一轮 493 项检查及 4 张图片属于历史阶段，不代表此地图哈希。通行验证采用真实编辑器碰撞采样，尚未进行运行时玩家巡游。

最终验收：[FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/StreetAccessLighting_20261005/FinalReview.json)。

[门口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/StreetAccessLighting_20261005/Renders/CAM_StreetAccess_HomeDoor.png) · [南巷](D:/UE/Project/HorrorGame/Saved/CodexOutputs/StreetAccessLighting_20261005/Renders/CAM_StreetAccess_SouthGap.png) · [北巷](D:/UE/Project/HorrorGame/Saved/CodexOutputs/StreetAccessLighting_20261005/Renders/CAM_StreetAccess_NorthGap.png) · [街道夜景](D:/UE/Project/HorrorGame/Saved/CodexOutputs/StreetAccessLighting_20261005/Renders/CAM_StreetAccess_NightStreet.png) · [路灯近景](D:/UE/Project/HorrorGame/Saved/CodexOutputs/StreetAccessLighting_20261005/Renders/CAM_StreetAccess_Lamp.png)。

