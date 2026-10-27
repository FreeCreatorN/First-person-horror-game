# 第一版酒店局部修订

已完成并保存 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。以用户最新保存的88b4版本为输入，未恢复历史地图；原图已备份。

四处巨型方块是布草、更衣和设备柜的占位模型，已换为高90cm的布草分格柜、带轮脏布草分类筐、低更衣柜和设备工作台；后窗下保留15cm净距。正面只保留中央入口，撤掉三个侧门/服务门及对应合页、门槛，门洞补为同材质实墙。

两侧楼梯增加四道连续内衬墙，使踏步贴墙，并补齐六处半层平台到后墙的52cm缺口。保留原有梯段宽度、转向平台和上方净高，未把踏步下方填到地面。

93套酒店门补齐内外把手；共126个新增有效背面把手，随原门轴或滑轨运动，保留原有闭合深度、开合姿态、材质和用户交互接口。仍按尺寸共用八个蓝图。新蓝图和四个家具mesh独立放在 `/Game/CodexGenerated/Hotel/Revision_20261019/`，遵守BP/SM_Hotel命名；旧共享蓝图、模型、材质保持不变。

正式写入和独立回读正常退出。其余7,875个Actor完整Native一致；93门顶层状态与1,057原组件Native精确保留，接口图连接检查通过。93门临时关闭/碰撞检查后恢复原姿态；两侧楼梯六段共780处支撑与胶囊通行检查通过。九张新鲜截图均完成目视审查，临时相机/灯清零，截图未保存地图。

用户可同时在Main编辑。助手只保存第一版及新增独立资源；过程中检测到Main及钥匙资源由并行编辑发生变化，已原样保留，未恢复或覆盖。没有应用性能或项目配置更改。中央楼梯未改；最初扩大的九路线诊断中，其既有开门姿态挡住原采样起点，正式验收范围为本次修改的两侧六段楼梯。

当前地图SHA：`7121a0b22abd6754861c108324b0c8b81a1ddb5b7338c2754a5ddc251fb58d72`。
备份：`D:\UE\Project\HorrorGame\Saved\CodexBackups\HotelRevisionBefore_20261019T095205Z\L_OldTownSchoolStreet.umap`。
验收：`Saved/CodexOutputs/HotelRevision_20261019/FinalReview.json`。
截图：`Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/`。

后续勿重跑Apply/恢复旧地图；继续以当前保存文件为准。常规全图优化仍在第二版，第一版只按用户明确请求改助手对象。

实景截图：

- [布草柜](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_CleanLinen.png)
- [分类车](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_DirtyLinen.png)
- [更衣柜](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_Changing.png)
- [设备台](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_Equipment.png)
- [南侧楼梯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_SouthStair.png)
- [北侧楼梯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_NorthStair.png)
- [正面北部](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_FrontNorth.png)
- [正面南部](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_FrontSouth.png)
- [双面把手](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelRevision_20261019/Captures/Renders/REV_DoubleHandle.png)
