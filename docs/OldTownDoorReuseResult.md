> 2026-10-17 后续归属追溯修正：本页601是当时历史隔离数，其中6个归属证据不足材质已原样恢复，当前上轮确认清理数595。门窗及原版资产现已完成Hotel命名，最新状态见 `Docs/HotelAssetNamingResult.md`。本页和旧FinalReview保留为历史证据，不应再次执行旧清理。

# 原版老城区：门复用与自有资源清理完成

原版 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet` 的 **124套自有门现按实际尺寸共用10个蓝图**。左右开、平开/推拉、材质、碰撞和既有开合姿态均保留，124个附属铰链保留。

清理了 **601个已确认无引用的自有资源**，约 **62.25 MiB**；资源已从Content移入可恢复备份。15个旧门蓝图仍被第二版使用，全部保留。归属不明或缺少创建校验的资源未清理。

独立重开地图验证通过：其余7862个对象完整数据一致；Main、第二版、BP_LightSwitch及用户原有资源文件未修改。清理后再次完整重开及全项目引用检查通过，没有新增缺失资源引用。

- 原图备份：`D:\UE\Project\HorrorGame\Saved\CodexBackups\OriginalTownBeforeDoorReuse_20261017T052057Z\L_OldTownSchoolStreet.umap`
- 资源隔离备份：`D:\UE\Project\HorrorGame\Saved\CodexBackups\OldTownUnusedResourcesOffline_20261017T053546Z_17caa81b`
- 新蓝图：`/Game/CodexGenerated/OldTown/DoorReuse_20261017/Blueprints`
- 当前地图SHA256：`8d58ec6a0634ffeb7feb245a5510246cd473bdbcdff4df3d332d72f94be68240`
- 完整验收：`Saved/CodexOutputs/OldTownDoorReuse_20261017/FinalReview.json`
