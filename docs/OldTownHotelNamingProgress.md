# 本轮完成

最终结果见 `Docs/HotelAssetNamingResult.md`，FinalReview已PASS。以下是过程记录，不能把历史中的“尚未同步”当作当前状态。

# 最新接续状态 2026-10-17

**当前任务进行中，2026-10-17：原版617自有资产已统一Hotel命名并同步；348窗/8BP、124门/10BP、7986Actor。AssetsAudit3全617 PASS正常0，Committed/Final完整7986审计、全盘graph正常0；已隔离36旧灯光包+Stage。后发现World plural ActorsMetaData仍缓存10旧门类路径（HeaderPatcher只处理singular），已备份8adf后仅UE重新保存原图刷新索引，新SHA d906951ed283739c20d3e8491afea6c3b83c193690b6c4e21e0eaa7fa3e2de7c，其他Content/Config全字节不变、旧10路径消失，MetadataRefresh1正常0。RefreshedAudit1当前正在完整7986重读；待Refreshed graph正常0→SupplementalCleanup10→CleanAudit完整7986+Clean graph→FinalizeHotelNaming/WriteHotelNamingResult。原用户输入8d58备份、用户/Main/V2始终保护；上轮595已确认清理、6归属不明材质已恢复，禁止再删。W=Saved/CodexOutputs/OldTownHotelNaming_20261017，续读Docs/OldTownHotelNamingProgress.md，当前未FinalReview不要冒称完成。**

以下为前序过程记录。

# 原版 Hotel 资产命名与窗户复用

2026-10-17，进行中。用户已再次保存关闭UE。仅处理原版中助手创建的资产和对应引用；用户资源、Main、第二版只读。

- 当前输入原图 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，SHA256 `8d58ec6a0634ffeb7feb245a5510246cd473bdbcdff4df3d332d72f94be68240`，7986 Actor。`Inventory1` 与完整7986 Native `BeforeScene1` 均正常0。窗348套共8尺寸类，门124套共10尺寸类，均保留现状。8旧窗BP全部被V2引用。
- 新工作目录 `Saved/CodexOutputs/OldTownHotelNaming_20261017`。计划617个明确自有资源，私有复制到 `/Game/CodexGenerated/Hotel/`，按 BP/SM/M/MI/T_Hotel_类型特征命名；用户及外部依赖保持原引用。共享旧包不直接改名。窗名如BP_Hotel_WindowDouble_W117_H112_D20；门按同尺寸实际类型命名DoorL/DoorR/DoorLR/DoorSlider/DoorSwingSlide，不为左右另拆同尺寸BP。
- 上轮601隔离归属证据已独立追溯修正163项累积清单误归因；595确证自有，6个材质证据不足已从原隔离备份原样恢复（103245字节）。见 LegacyCleanupProvenanceAudit.json、LegacyCleanupRestored.json；新的保护基线为 ProtectedBeforeAfterRestore.json。原上轮FinalReview是历史验收，不据此删除恢复的6包。
- 新独立编辑器工具 `Plugins/CodexHotelAssetTools`，默认禁用，仅本任务命令行显式启用；不改已有灯光插件/用户项目配置。BuildPlugin2正常0，源码与已安装二进制核验通过。API PatchPackagesExact 两参数只能创建私有新包；PatchPackagesToSaved三参数只写本轮Saved子目录。都禁自动依赖扩展，逐文件精确验证错误与写集合；不全局consolidate、不创建redirector、不直接覆盖原图。
- `Copy1` 正常0：已备份618源文件，创建617个Hotel私有包与L_Hotel_Stage临时图，全部旧Content/Config字节保持。临时图7986Actor完整Native与结构/几何/灯光比较通过，`StagedAudit2`正常0。原图仍是8d58…，尚未写回。
- 资产逐项审查发现header复制把143个模型的材质槽名称一并重映射、32个导入路径因目录深度变化解析错误。仅修正新私有副本，保持原槽身份与原源文件解析路径，不重导模型。两次未完成修正的125个新包已精确隔离并按初始SHA全部重建，`CopyRepair1`正常0。自建默认禁用helper Build3新增仅限Hotel私有导入路径的C++桥接，保持MD5/时间戳；MetadataFix3正在运行。
- 接下来须逐项617资产语义/全Native/几何/材质/贴图检查通过，再仅把临时图逻辑名修回原map写到Saved，UE退出后原子替换原map，fresh完整读回、全项目引用、无用自有旧包再审并隔离，最终验收。不得把仅创建新包称为已经同步原图。
- 根统一运行 `Scripts/RunOldTownHotelNamingTask.ps1`，需要headerpatch工具的脚本加 `-EnableCopyTools`；UE辅助进程串行。资产复制/改名未完成，不得声称已同步地图。其他脚本和设计见本轮W。
