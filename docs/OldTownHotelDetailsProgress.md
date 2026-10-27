# 酒店门轴与楼梯细节（历史阶段）

后续洗手盆连接纠错已完成，当前状态见 `Docs/UE5GreyboxCheckpoint.md` 和 `Saved/CodexOutputs/BasinConnections_20261011/FinalReview.json`。本页的 f821 与21张图属于上一阶段，不能代替新洗手盆连接验收。

2026-10-11，当前保存地图SHA f821289afb1e06cb2be98569d42b8cb2ad762be5ddf48dfbf00f1f7a4cd3617a。

已实现62扇平开门的186只门轴、240根有底板支承的栏杆柱、60根连续圆管（18段斜扶手）、12扇平台以上高窗，并重新切153块后墙。原96扇门和四层27房布局保留。

完整表面复扫已PASS：8720可见组件、1786820实际三角、1631798检测面、0暴露重面/0重复块、460组埋面有证据。ArchitectureAudit3193项/DetailAudit1206项均PASS；21视角重拍与逐图视觉验收已全部PASS，6批辅助进程正常退出、临时灯清零。FinalReview/HotelDetailFinalAudit和统一CurrentEvidence已发布。工作目录Saved/CodexOutputs/HotelDetails_20261009。

后墙最终渲染微偏X+0.45mm、Z-0.45mm；早期只偏X/向上偏Z扫描均为历史证据。旧洞填实、新洞打开，碰撞没有随材质微偏移动。

原L_Main用户修改按最新输入保留。不要重复Apply、相机修正或负Z修正；续做读精简Checkpoint。
