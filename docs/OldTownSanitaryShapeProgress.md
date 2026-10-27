# 酒店卫生设施曲面优化

此记录为历史阶段（地图SHA 96a9）。当前水箱/箱盖细化与最新截图见 `Docs/OldTownSanitaryFinishProgress.md`；当前接续点见 `Docs/UE5GreyboxCheckpoint.md`。

2026-10-11，已保存到原地图 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。

- 30个马桶增加有厚度、封闭底部和内壁的凹入碗腔，收窄后侧陶瓷承托，保留原座圈、水箱和落地底脚。
- 30个洗手盆的龙头横嘴与向下嘴改为一段连续圆弯管，连接原立柱和嘴帽；保留原控制柄、盆底排水和材质。
- 新网格在 `/Game/CodexGenerated/OldTown/Meshes/SanitaryShapes_20261011`。只更新60个可见设施网格并增加2个检查相机，设施原位置、朝向、比例以及60个独立碰撞保持；7952个其他原Actor精确保持。
- 重载地图后，3193项建筑、1206项原细节、8082项保存状态、1861项实际几何检查全部通过。杯腔净空、8.5cm底壳厚度、闭合面和实体连接逐实例验证；原始保留面一一对应，新增面与独立源造型对应，实际法线全部朝实体外侧。
- 全图8720个可见组件、1820078个检测面未发现暴露重合面或重复块，490组埋藏面具有遮蔽证据。4张最新近景经两次实际目视复核；截图辅助进程正常退出0，临时检查灯清零，截图未改变保存地图。

该历史阶段8014 Actors，地图SHA `96a927f42d52477d371665aad35ac8fdd85406eb42a91940cf047213cde8c44d`。历史验收为 `Saved/CodexOutputs/SanitaryShapes_20261011/FinalReview.json`；4张该阶段截图只在 `CorrectedCaptures/Renders`。该阶段已由后续SanitaryFinish更新。

首版新面的朝向错误曾造成外壳剔除并露出支柱，已反转新增面索引并重算新曲面法线后重新保存、审计和拍摄。拒绝版本的证据留在 `RejectedWindingPreview`；根目录旧 `Renders` 不是当前图。Applied和WindingRepairApplied已存在，禁止重复执行。

仍属灰盒：原座圈和底脚保留分段轮廓，水箱块状，杯腔尚无排污孔或水面，未完成写实材质。客房马桶前40.49cm处已有淋浴托盘，布局本轮未移动；检测无暴露重面不代表所有无关家具结构已完成审查。精简接续点见 `Docs/UE5GreyboxCheckpoint.md`。
