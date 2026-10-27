# 酒店卫生设施优化

此记录为历史阶段（地图SHA 412d）。后续曲面优化及当前截图见 `Docs/OldTownSanitaryShapeProgress.md`；当前精简接续点见 `Docs/UE5GreyboxCheckpoint.md`。

2026-10-11，已保存到原地图 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。

- 30个马桶座圈与碗体接合，补完整陶瓷承托连接水箱、碗体和底脚，并调整朝向室内。
- 30个洗手盆保留原盆底排水修复，给龙头补齐横向出水嘴、向下嘴头和控制柄。
- 新网格在 `/Game/CodexGenerated/OldTown/Meshes/SanitaryFixtures_20261011`，未覆盖原共享网格；房间布局、原材质及60独立碰撞保留。7949个其他原Actor状态完全不变。
- 重载地图后，3193项建筑、1206项原细节、8077项保存状态、1669项实际设施几何检查全通过。全部马桶/洗手盆逐实例检查，原始马桶面通过一一坐标对应保留验证。
- 全图8720可见组件、1670678检测面扫描未发现暴露重合面或重复块；490组埋藏面保留实际遮蔽证据。4张当前近景经两次独立目视复核；截图进程正常退出0、临时灯清零。

该历史阶段8012 Actors，地图SHA `412d31cf4b23b5ee16cb3b9d1238dae4c1f7a990a19d6db642cf21611f7349f9`。历史证据为 `Saved/CodexOutputs/SanitaryFixtures_20261011/FinalReview.json`，截图在同目录 `Renders`。Applied已存在，禁止重复应用。

设施仍为灰盒模型，马桶碗内平面、表面分段未做最终写实细化。客房马桶前40.49cm处已有淋浴托盘，不能将远处墙距当成连续空净距；本轮未移动卫浴隔墙。近景未拍全马桶底脚，地面接合由实际网格审计确认。
