# 原版门复用与自有资源清理

2026-10-17，已完成。正式验收见 `OldTownDoorReuseResult.md` 和本轮 `FinalReview.json`（PASS）；不要重跑应用或清理。用户要求在他的原版老城区按相同实际尺寸复用门蓝图，并清理无用的助手资源；用户导入、自制或归属不明资源只读。

- 当前输入：`/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，SHA256 `8149497ff1ad953fad2ac2bc08f3cd072f78421709cc8777fb54ebf1fc055d61`，7986 Actor。用户 BP_LightSwitch 当前 SHA `aee5e385d6e1ec6b2618a6efb0a53b58235eed04d0273cae137aa03a40998e37`，不可恢复旧版本。
- 新工作目录：`Saved/CodexOutputs/OldTownDoorReuse_20261017`。只读盘点正式成功为 `ReadOnly3`；前两次导出读取失败均未写地图。`DoorInventory.json`、`AssetReferences.json`、`DoorReuseDesign.json` 已生成。
- 124 套建筑门、15 个旧 BP，可按净开口/框深厘米归并 10 个新 BP：80×205×20(2)、85×205×12(27)、90×220×20(14)、100×220×20(28)、112×184×20(1)、120×220×20(6)、132×226×20(27)、140×220×20(16)、180×220×20(1)、200×235×20(2)。140×220 同组平开/推拉须组件并集，未用分支清空网格/隐藏/关闭碰撞。其他组可单一模板配实例覆盖。
- 15 个旧 BP 全部被第二版引用，禁止修改或删除；只新建 `/Game/CodexGenerated/OldTown/DoorReuse_20261017/Blueprints` 下 10 个 BP。保留原门 Actor 内部 FName/路径、标签、材质、碰撞、WPO、姿态和附属铰链；全图扫描其他 Actor 的组件父对象，不能只按名字查附件。
- `Scripts/OldTownDoorReuseCommon.py` 是严格 raw 属性复制工具，接口 configure_door / verify_configured_door。`BuildAndProbeOldTownReusableDoors.py` 创建 10 BP 并做 15 种旧类的无保存探针；`ApplyOldTownDoorReuse.py` / `AuditOldTownDoorReuse.py` 准备完整其他 Actor Native 保护与 fresh 读回。运行统一用 `RunOldTownDoorReuseTask.ps1`；UE 必须串行。
- BlueprintProbe1–3 均未保存原图，失败的新 BP 已移到本轮 Saved 失败归档。Probe2 已证明默认编辑通知重建组件使缓存指针变成 TRASH；helper 现全部组件属性复制使用 NEVER 通知。Probe3 只剩门轴后代世界矩阵缓存差异，现以 set_absolute(原值) 无条件刷新，不重算原始旋转。正式 BlueprintProbe4 正常退出0：10个新 BP、15种原类变体全部严格通过，2884个旧Content/Config文件哈希未变；`ReusableBlueprints.json` 是正式新资产清单。Apply1正在执行保存前全图保护，尚未确认地图应用完成。
- `OwnershipPlan.json` 与 `AnalyzeOldTownOwnedUnusedAssets.py` 已给出 601 个明确自有且无引用候选约62.25MiB，662 个仍使用的自有资源保留；另外12个归属证据不足的OldTown包与64个只有FBX源证明的Yastar包冻结。不能把 current_asset_sha2561576 全当自有，里面包含用户资产。
- 清理会在门替换后 fresh 导出全项目 Registry，再用 `--references` 重跑分析；包含硬/软/管理依赖与受保护包、Config/运行代码的UTF8/UTF16完整路径字面引用。UE 删除 API 内部会强制删除，因此不用该 API；待 UE 正常退出后，仅把最终核验通过的精确文件移出 Content 到 Saved 可恢复隔离备份，并核 SHA。历史证据、备份和脚本不删。
- 用户报错也已只读定位：10:20那次 BP_LightSwitch_C_1 的 FlickerPool 空却仍取5盏，加入None后5秒闪烁时间轴调用SetIntensity而报空引用。当前保存原图无此旧开关实例，BP图仍缺防空；用户蓝图不改。

Apply1、Readback1及ReadbackAfterCleanup1均正常退出0。当前原图SHA256 `8d58ec6a0634ffeb7feb245a5510246cd473bdbcdff4df3d332d72f94be68240`，7986Actor；124套门/10共享蓝图和124外置铰链通过，其余7862Actor完整Native/场景状态相同。fresh引用和CleanupGate1正常0，601个资源（65,273,835字节）已移出Content到 `Saved/CodexBackups/OldTownUnusedResourcesOffline_20261017T053546Z_17caa81b`；源文件缺失、隔离副本SHA及保护集精确核验通过。离线脚本首次预检的PowerShell自动日期解析和扩展名去除问题均在任何搬移前拦截并修复，正式隔离已完整通过。清理后完整独立重开和全项目fresh引用均正常0，2286个磁盘包与Registry集合完全一致，无新增缺失依赖。FinalizeOldTownDoorReuse.py正常退出0并生成FinalReview.json PASS及结果说明；Main/BP_LightSwitch/V2和用户内容字节保护全部通过。
