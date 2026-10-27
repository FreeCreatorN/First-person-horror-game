# 原版老城区局部穿模修复

2026-10-19，已完成，目标 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。

- 电线杆01整组向路缘移动115cm，横担旋转90度改为沿街；三根接入电线重新连接，另一端不动。横担距外墙装饰120cm，杆身距车道边23cm。道路、人行道尺寸未改。
- 酒店正面右侧出口旁的旧下水管、电表箱、接线盒、电缆及4个挂架沿墙移动200cm，落在相邻实墙上；离出口门洞至少159cm。保留门本身的材质、90度开启状态及全部组件。
- 共17个助手对象仅调整根变换，其余7969个Actor完整Native数据一致，Actor总数7986不变。未新增或删除资源，所有材质、碰撞、灯光保持。其余Content/Config文件逐SHA一致，涵盖用户资产、Main和第二版。
- 保存前完整比对通过，保存后独立重开比对通过；Inspect1、Apply1、Audit1及前后截图辅助进程均正常退出0。两张修复后截图已直接检查，临时相机与临时检查灯均清零且未保存。

当前地图SHA：`db1d130458a01f70f988080cbf2bcfde355410b78617c311fff590dfe506e92f`。本次用户输入SHA：`932de807d7ffa21e235c581037e99280af1003914a60c7bb5b9bcd7fe2f7bf01`，没有恢复历史地图。

修复前地图备份：`D:\UE\Project\HorrorGame\Saved\CodexBackups\OldTownIntersectionBefore_20261018T235825Z\L_OldTownSchoolStreet.umap`。

前后对照：`D:\UE\Project\HorrorGame\Saved\CodexOutputs\OldTownIntersectionFix_20261019\BeforeCaptures\Renders`、`D:\UE\Project\HorrorGame\Saved\CodexOutputs\OldTownIntersectionFix_20261019\AfterCaptures\Renders`。
完整证据：`D:\UE\Project\HorrorGame\Saved\CodexOutputs\OldTownIntersectionFix_20261019\FinalReview.json`。

后续仅凭本轮明确授权修改原版这两处助手对象；一般优化仍在第二版。不要重跑Apply脚本、不要用历史map覆盖用户当前修改。
