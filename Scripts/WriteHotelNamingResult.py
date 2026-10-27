"""Write human-readable handoff and update the local continuation checkpoint."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R/'Saved/CodexOutputs/OldTownHotelNaming_20261017'
review=json.loads((W/'FinalReview.json').read_text(encoding='utf-8'));assert review['passed']
cleanup=review['cleanup_this_task'];old_count=cleanup['packages']-1
text=f'''# 原版老城区：资产命名与窗户复用

2026-10-17 已完成，已同步到原关卡 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。

- 原版使用的617个助手资产已统一到 `/Game/CodexGenerated/Hotel/`，名称为 `BP / SM / M / MI / T_Hotel_用途与特征`。用户自己的资产和地图名称保持。
- 348套窗户共用8个尺寸蓝图；124套门共用10个尺寸蓝图。没有为每个实例各建一份蓝图。原7986个Actor的内部名、标签、变换、父子关系及原有用户字段保持。
- 本次移出Content的无用自有旧包{old_count}个，另清理1张临时验证地图，合计{cleanup['bytes']/1048576:.2f} MiB。先备份再逐个移除，恢复备份：`{cleanup['backup']}`；10个旧门的补充备份：`{cleanup['supplemental_backup']}`。
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

改名前完整618个源包备份：`{review['backup_directory']}`。

当前地图SHA256：`{review['map_sha256']}`。

最终证据：`Saved/CodexOutputs/OldTownHotelNaming_20261017/FinalReview.json`。历史失败验证保留，不作为完成证据。
'''
(R/'Docs/HotelAssetNamingResult.md').write_text(text,encoding='utf-8')
checkpoint=R/'Docs/UE5GreyboxCheckpoint.md';old=checkpoint.read_text(encoding='utf-8-sig')
start=old.index('**当前任务进行中');end=old.index('\n\n',start)
replacement=f'**2026-10-17 本轮已完成：原版617个助手资产统一Hotel命名并同步引用；348窗/8BP，124门/10BP，7986Actor。原map SHA {review["map_sha256"]}。本轮隔离{old_count}个无用旧包+1临时地图；用户资产/Main/V2/Config全字节保护。上轮601追溯修正为595，6个不明材质已原样恢复并保护。FinalReview PASS；见Docs/HotelAssetNamingResult.md及本轮Saved/CodexOutputs/OldTownHotelNaming_20261017。勿重跑任何Apply或恢复旧map覆盖当前用户修改。一般后续优化仍在第二版，用户原版仅按本次明确授权处理。**'
checkpoint.write_text(old[:start]+replacement+old[end:],encoding='utf-8')
progress=R/'Docs/OldTownHotelNamingProgress.md';previous=progress.read_text(encoding='utf-8-sig')
progress.write_text('# 本轮完成\n\n最终结果见 `Docs/HotelAssetNamingResult.md`，FinalReview已PASS。以下是过程记录，不能把历史中的“尚未同步”当作当前状态。\n\n'+previous,encoding='utf-8')
door=R/'Docs/OldTownDoorReuseResult.md';previous=door.read_text(encoding='utf-8-sig')
door.write_text('> 2026-10-17 后续归属追溯修正：本页601是当时历史隔离数，其中6个归属证据不足材质已原样恢复，当前上轮确认清理数595。门窗及原版资产现已完成Hotel命名，最新状态见 `Docs/HotelAssetNamingResult.md`。本页和旧FinalReview保留为历史证据，不应再次执行旧清理。\n\n'+previous,encoding='utf-8')
print('HOTEL_NAMING_HANDOFF_WRITTEN')
