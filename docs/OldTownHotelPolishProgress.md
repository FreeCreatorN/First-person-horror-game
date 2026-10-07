# 老城酒店增量优化


本文件为酒店阶段历史记录。当前街道已完成窄巷与路灯修订，最新状态及截图见 [OldTownStreetAccessLightingProgress.md](D:/UE/Project/HorrorGame/docs/OldTownStreetAccessLightingProgress.md)；本文件的旧哈希、检查数量和图片不作为当前证据。

2026-10-05：本轮已完成，原街道已保存、独立重载通过，四个受影响视角已逐张复核。

本轮直接优化原街道 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，不重建整条街道。

- 24 张客房床垫由混凝土外观改为米白粗糙布面，尺寸、位置与碰撞保持。
- 201–208、301–308、401–408 共 24 间客房增加深绿房号牌及独立 3D 数字。牌宽 44 cm、高 24 cm；数字高 12 cm，牌中心离楼面 171 cm，贴墙且不遮挡门洞，无碰撞。
- 前台背景板增加“老城酒店”字样，复用原酒店文字网格，仅覆盖新实例材质。
- 三种新材质均为有光照、非自发光材质，未修改共享木材、门窗或原招牌资产。

阶段完成时地图 SHA256：`2687cbab9a35580326cc2f5bb372be692f4e2d7cdda3dcadd6eb3a5837b32aa7`，5629 Actors。原 5579 个 Actor 除 24 张床垫的材质覆盖外，保存后的变换、组件、网格、碰撞等属性复核一致；219 份原有共享素材文件未变。用户灯光、L_Main、章节灰盒、修正版预览保持。

本轮 [HotelPolishAudit.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005/HotelPolishAudit.json) 为 493 项、0 失败；原有门窗、酒店布局、道路、灯光、建筑接缝、细节、楼梯三角面及保存后通行审计全部通过。141 项 Python 测试通过。对保存状态的比较在碰撞探测前完成，探测期间的临时组件状态不写入地图。

完整证据目录：[HotelPolish_20261005](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005)。[Before](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005/Before) 保存本轮修改前关卡与输入报告，输入 SHA256 为 `7067f6e9e3227b2e00dd6aa8b9dca2e0bf34848980d1c54eee084dd34ef0d3d0`。

源资产：[OldTownHotelRoomNumbers.blend](D:/UE/Project/HorrorGame/SourceArt/OldTownHotelPolish_20261005/OldTownHotelRoomNumbers.blend)。24 份 FBX 均完成独立重载回读，实测宽 21.19–25.35 cm、厚 0.25 cm、高 12 cm；总 3590 顶点、7068 三角面。[导入清单](D:/UE/Project/HorrorGame/SourceArt/OldTownHotelPolish_20261005/ImportManifest.json) 与 UE 元数据中的源文件 hash 一致。

此阶段仍为灰盒，新增牌和文字不参与碰撞。门窗玩家开关输入未实现，尚未完成实时玩家巡游。

四张最终图均对应当前地图 hash，使用临时检查补光，删除后残留为 0 且未保存关卡；捕获进程正常退出 0，无强制清理。[FinalReview.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005/FinalReview.json) 已通过，18 份当前报告已发布，以 [CurrentEvidence.json](D:/UE/Project/HorrorGame/Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json) 清单为准。上一轮 17 张图属于 7067f6e9… 的历史版本，不是本轮图片。

[房号与门口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005/Renders/CAM_Hotel_RoomNumber.png) · [床垫](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005/Renders/CAM_Hotel_Room.png) · [前台](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005/Renders/CAM_Hotel_Reception.png) · [走廊](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelPolish_20261005/Renders/CAM_Hotel_Corridor.png)。

