# 酒店马桶水箱和箱盖细化

2026-10-12，保存到原地图 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，地图SHA `ade3fcc6a6482713618e3fadbd4534771549e773097fd2b9d34886318451e1f6`，8014 Actors。

- 30个马桶的方块水箱/重叠箱盖重建为两件闭合圆角陶瓷体，顶部保留浅盖缝。整体20×35×33cm及原位置保持；箱体XY圆角1.8cm、边沿倒角0.6cm，盖圆角2.2cm、边沿倒角0.25cm。
- 盖中心嵌接0.3cm，箱/盖同位外直壁在高度上相隔0.55cm，避免产生新的暴露重面。仅删除14个明确旧完整组件的215面，保留其余3672原面，包括前后底脚、座圈、中空杯体、后承托和旧按钮。
- 新资产仅在 `/Game/CodexGenerated/OldTown/Meshes/SanitaryFinish_20261012`。30处可见网格引用更新，7984个其他Actor精确保持，0新增Actor，60独立碰撞、全部30个洗手盆实际面/状态保持。
- 保存后重载：3193项建筑、1206项原细节、8080项保存状态及2035项独立实际几何检查全通过。新面全部法线朝外、闭合拓扑和五个实体接合验证；实际四平面错开0.55cm，新水箱最低面距旧杯顶4.3cm，原杯净空/底壳保持。
- 全图8720个可见组件、1911548个检测面未发现暴露重合面或重复块，490组埋面保留遮蔽证据。四张新近景经两次实际目视复核；辅助进程正常退出0，临时检查灯清零，未改变保存地图。

本轮开始前发现 `L_Main.umap` 已从历史b20更新为629d。只更新当前保护基线，并保存原报告、当前文件实际备份及唯一更新记录；酒店输入图仍为96a9，另外两张保护地图不变，未回滚主地图。

证据 `Saved/CodexOutputs/SanitaryFinish_20261012/FinalReview.json`，当前图仅在同阶段 `CorrectedCaptures/Renders`。Canonical `EnterableStreet_20261002/CurrentEvidence.json`指向本轮；之前4张SanitaryShapes、4张SanitaryFixtures、3张BasinConnections和21张HotelDetails图均为历史。Applied已存在，禁止重跑。

仍属灰盒：盖缝在截图中有像素级深浅差异，旧座圈/底脚分段、原陶瓷材质、碗内无排污孔/水面等保留。旧按钮大部分嵌在箱壁中，本轮未做可操作把手。新截图使用临时检查灯，不代表最终场景照明。精简接续点见 `Docs/UE5GreyboxCheckpoint.md`。
