# 原版酒店门闭合修复

2026-10-19已完成。目标 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，96套酒店门（62平开、34推拉），仍按尺寸共用8个原有Hotel蓝图。

根因是旧叶片中心在框正面之外3cm，叶片厚4cm，关闭零位仍与门框之间有1cm深度空隙。旧检查只证明碰撞能堵路，没有检查叶片是否齐框。

叶片、把手、碰撞及门上玻璃部件一同内移5cm，闭合时门面与框正面齐平；新增三侧门挡遮住工作边缝，门挡与木叶后表面留0.25cm间距，合页位置留槽，转角无共面正面积重叠。原转轴和固定合页保持，活动合页安装片/连接颈配合新深度；另将原本挂在门框下的11个活动合页改挂对应DoorHinge，开关时跟随门板，旧共享mesh未改。新增14个复用mesh位于 `/Game/CodexGenerated/Hotel/Meshes/DoorClosure/`，全部遵守SM_Hotel命名。

已逐一临时关闭96门，检查130块门板/碰撞盒实际齐平与真实阻挡射线；检查后恢复地图保存的原始开合姿态。蓝图默认关闭零位已更新，原有左右开/推拉、材质、Actor身份和用户图表/变量/接口保持。

保存前及独立重开完整比对通过：7986Actor不增减，96个新增DoorStops组件，62活动合页使用新mesh，其中11个修正父级和局部零位，其余7828Actor完整Native一致。其余28扇街区门、用户自制/导入资源、Main、第二版、Config文件逐SHA不变。

四张新鲜关闭态截图已直接目视检查，截图进程正常0，临时相机和灯清零、临时关门姿态已恢复、未写地图。

当前地图SHA：`909e409519a1ca07c0b21a54ddd85e1afd3b41411823b73ea188ff6cc3b53862`。本次用户输入：`b6756330033d3c9c51994e4410a2d5a3ad6b32867bfc5f2e8e250002fa9b45ef`，未恢复历史地图。
备份（原图及8蓝图）：`D:\UE\Project\HorrorGame\Saved\CodexBackups\HotelDoorClosureBefore_20261019T022037Z`。
验收：`D:\UE\Project\HorrorGame\Saved\CodexOutputs\OldTownHotelDoorClosure_20261019\FinalReview.json`；截图：`D:\UE\Project\HorrorGame\Saved\CodexOutputs\OldTownHotelDoorClosure_20261019\Captures\Renders`。

前四个未保存尝试已保留诊断并把助手BP从本轮备份精确恢复后重试；最终正式Apply5/HingeParents1/Audit2正常0。后续不要重跑旧Apply或用历史地图覆盖用户修改。一般美术优化仍在第二版，原版这次仅按明确要求修酒店门。
