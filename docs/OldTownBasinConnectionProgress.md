# 洗手盆连接纠错

2026-10-11，已保存并验收的历史轮次；当前结果见 `Docs/OldTownSanitaryFixtureProgress.md`。用户截图实际为洗手盆排水竖管，上一轮楼梯检查漏掉了这件家具网格内部的连接。

- 原竖管顶64cm、横支撑底69cm，30个实例均有5cm断口；水龙头底另有4mm浮空。
- 新独立网格将竖管接进盆底至73.3cm、龙头底落入盆面至80.7cm。原盆外形、所有非目标顶点、材质、姿态、30独立碰撞和原Yastar共享资产保持；只替换30个网格引用。
- 重新加载后，30盆274项真实连接检查、90处实体穿入验证通过；7976原Actor状态保持。门窗、楼梯、通行复验通过，全方向整图表面扫描无暴露重面/重复块。
- 3个新近景确认原缝隙消失，截图辅助进程正常退出0、临时灯清零。上一轮21图仅作历史参考。

地图：`/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，SHA `684f1f0533cef3ab50b6c7e3b270cb0a4dab924b839139e5d9a8e2048503f33d`，8009 Actors。

证据：`Saved/CodexOutputs/BasinConnections_20261011/FinalReview.json`；精简接续见 `Docs/UE5GreyboxCheckpoint.md`。Applied已存在，禁止重复执行修正。

本轮只验证洗手盆连接；其后卫生设施优化已修复原马桶座圈/水箱连接，并保留此轮全部盆体实际面。此处的3张图片和SHA均为历史参考。
