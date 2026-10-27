# 原版老城区：资产命名与窗户复用

2026-10-17 已完成，已同步到原关卡 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。

- 原版使用的617个助手资产已统一到 `/Game/CodexGenerated/Hotel/`，名称为 `BP / SM / M / MI / T_Hotel_用途与特征`。用户自己的资产和地图名称保持。
- 348套窗户共用8个尺寸蓝图；124套门共用10个尺寸蓝图。没有为每个实例各建一份蓝图。原7986个Actor的内部名、标签、变换、父子关系及原有用户字段保持。
- 本次移出Content的无用自有旧包46个，另清理1张临时验证地图，合计17.64 MiB。先备份再逐个移除，恢复备份：`D:\UE\Project\HorrorGame\Saved\CodexBackups\HotelUnusedPackages_20261017T110921Z`；10个旧门的补充备份：`D:\UE\Project\HorrorGame\Saved\CodexBackups\HotelObsoleteDoors_20261017T154659Z`。
- 第二版仍用的旧门窗、共享资产和编辑器工具仍引用的旧灯光控制器保留。用户制作/导入的资产、Main、第二版和项目配置均经完整文件校验确认没有变化。

## 命名示例

| 资源 | 名称 |
|---|---|
| 左开门 | `BP_Hotel_DoorL_W100_H220_D20` |
| 双扇窗 | `BP_Hotel_WindowDouble_W117_H112_D20` |
| 灯光控制 | `BP_Hotel_LightCircuit` |
| 模型 | `SM_Hotel_DoorJambLeft` |
| 材质 | `M_Hotel_Wood_UV` |
| 贴图 | `T_Hotel_Wood_BaseColor` |

尺寸单位厘米。相同尺寸继续共用蓝图；兼有左右开或不同开门形式的组保留实际兼容行为，分别使用DoorLR、DoorSwingSlide等名称。详细规则见 `Docs/HotelAssetNamingRules.md`，逐个旧名→新名清单见本轮 `HotelNamePlan.json`。

## 验证与备份

新资产617/617加载与规定字段校验通过；所有原7986个Actor/组件完整结构及Native对比只允许明确的资产路径替换，灯光、材质、碰撞及已测模型位置/索引/法线/UV0/切线数据保持。没有将UV0比较说成所有UV通道与顶点颜色逐项验证。

原图写回后、清理后分别独立重新读取场景；磁盘全部资产包与全项目注册表严格对账，硬引用、软引用、管理和可搜索引用以及保留文件中的完整路径均已检查。没有新增缺失依赖。

额外处理了UE的旧地图对象索引：引擎的包改名工具会漏掉plural `ActorsMetaData`中的旧门类路径，导致实际门已用新蓝图，但索引仍列旧路径。已在备份后用UE重新保存原图刷新该索引，并完整重读核对7986对象；旧10门无引用后才补充隔离。没有修改用户自己的标签或逻辑。

没有进行模型重导或性能配置修改。此前已有的17条缺失导入源文件路径保持原状；不会改变已导入模型的渲染。上轮601项清理追溯后，有6个归属证据不足的材质已原样恢复，因此上轮确认清理数应为595，恢复项受到保护。

改名前完整618个源包备份：`D:\UE\Project\HorrorGame\Saved\CodexBackups\HotelNamesBeforeCopy_20261017T060803Z`。

当前地图SHA256：`d906951ed283739c20d3e8491afea6c3b83c193690b6c4e21e0eaa7fa3e2de7c`。

最终证据：`Saved/CodexOutputs/OldTownHotelNaming_20261017/FinalReview.json`。历史失败验证保留，不作为完成证据。
