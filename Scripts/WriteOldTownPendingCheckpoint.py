from pathlib import Path
import shutil
R=Path(__file__).resolve().parents[1]
W=R/'Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013'
text='''# UE5 老城区精简接续点

当前是软装模型验收及其后方向光复制任务。不要重新开始，不要重跑已应用的 Stage1/Stage2/Stage3 Apply。

- 已保存老城区 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，地图 SHA `d01be344714fc7656061791bfd920098605a6db95026df0ad61280da12395792`。Stage3 20模型/222组件/40新增包已应用，8014Actor/13920组件、材料覆盖、木框、BodySetup、WPO及原19灯均保留。原1166包字节不变。Native SavedAudit2通过。
- **尚未发布Stage3**：Canonical `Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json` 仍指向已验收Stage2（地图SHA 12cbb0…；材质与16亮灯罩发光）。当前磁盘地图比发布指针新，不得把Stage2当当前地图验收。
- Stage3 WORK `Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013`。第一轮全图8719可见组件/344可见模型/9281596三角面扫描发现14外露重面，均为街区LegacyBedMattress的7个实例各2组；原503埋藏组/0跨模型外露/0重复块。原因已独立证明为竖侧面长三角扇被Z褶皱折回，不能豁免或放宽扫描阈值。
- 修复前971文件已备份 `Saved/CodexBackups/SoftGoodsBeforeOverlapCorrection_20261015T145916Z`，BeforeCorrectionBackup.json与Manifest逐文件SHA核验。源生成器目前由 soft_overlap_diagnosis agent 负责：仅重建LegacyBedMattress，冻结侧壁/圆角/包边/底面，褶皱仅在原水平上表面作单值高度变化。其余19源变体、38源文件、3酒店预览不改，完整Blend保留，重验55接触及局部全法向扫描。
- 源修复后 root 运行 `ApplyOldTownSoftGoodsOverlapCorrection.py`（原owned mesh+cache仅2包重导，其余38包不变，不保存地图）；接着 SourceAudit、SavedAudit3、全图扫描、重新全部19图、VisualReview、Finalize --publish。初轮失败/超时证据完整留在备份。现有CaptureRuns含重拍历史，要保存历史后建立每相机最新正常退出索引，不能把exit=-1算通过。
- 原4角色运行收据已扩充 InputExport/BuildApply/SavedAudit/OverlapCorrection，必须观察真实正常0后登记。Capture frozen Python/PS不能静默改；CaptureSetup修复后重新绑定BuildReport和资产SHA，旧截图不能混入新资产验收。
- **用户新增任务（必须此顺序）：** 当前软装完成并验收→备份完成的老城区地图/1206配套包/源和证据→复制L_Main的两盏方向光→隐藏旧目标方向光（若存在）→重新载入和实际灯光截图。当前保存的OldTown方向光为0，不要误隐藏天空大气、点光、路灯。
- Stage4 WORK `Saved/CodexOutputs/OldTownMainLighting_20261015`，只读DirectionalInput2正常0：Main `DirectionalLight`5000lux/大气索引0，`MoonDirectionalLight`0.1lux/索引1，皆Movable；使用完整duplicate_actor，不能只抄强度。Main最新只读SHA a22ec1fc…；实际复制前再核当前保存版。Moon Euler多圈，按四元数等价比较。
- Stage4已准备但**未执行** `BackupOldTownBeforeMainLighting.py`、`ApplyOldTownMainLighting.py`、`AuditOldTownMainLighting.py`、`OldTownMainLightingCommon.py`。临时流送Main后会切current，复制前切回并断言OldTown persistent；卸载Main后源UObject包装失效，先转纯数据；只保存OldTown。Stage4脚本正独立静态复核。禁止在Stage3发布/备份前运行Apply。
- 用户已授权自己编辑/保存Main并行；不关闭用户UE、不写Main、不回滚拾取BP（SHA cc934d57…）。Root独占UE辅助进程启动，仅管理自己PID；-NOINI/-NoAutoSave、私有DDC、不能并发两个Cmd。所有新包只进CodexGenerated，原Yastar/Meshes不改。
- 保持酒店4层27房、中央门/前台、办公室左/安全梯右上/公厕右下，7m机动车道/1.8m人行道/5开放巷/路缘9灯及8单向Spot。现有18开口BP与MainHome只证结构保护，未新做运行时通关，住宅单元改造未实施。
- 视觉限制：酒店立面/墙仍较均匀，木纹较软，床品临时补光下略有蜡感；不能宣称全图已达最终写实品质。旧NightStreet相机名不能证明夜晚；Main灯复制后的实拍另行评估。
'''
for name in ('UE5GreyboxCheckpoint.md','OldTownRealismProgress.md'):
    p=R/'Docs'/name;history=W/'DocsHistory'/('BeforeOverlapCorrection_'+name);history.parent.mkdir(parents=True,exist_ok=True)
    if not history.exists():shutil.copy2(p,history)
    p.write_text(text,encoding='utf-8')
print('PENDING_CHECKPOINT_UPDATED')
