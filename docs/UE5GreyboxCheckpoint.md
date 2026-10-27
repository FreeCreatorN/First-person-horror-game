# UE5 老城区精简接续点

**2026-10-21 最新：酒店前方两头遮挡已完成，纠正此前只做正Y端的遗漏。保留北端4Actor，新增南端4Actor、复用3冻结模型，无资源包改动。原7993Actor完整Native/其他2941文件逐SHA保持；Main/V2/用户资产只读。当前7997Actor、SHA cef9d5588df2763a053f47b799e97d4d290f392a7d25feec2dbed6b5097f5112。492双向射线、5路线段438胶囊支撑采样及4新鲜截图通过，临时相机灯清零，Apply1/Audit1正常0。见Docs/HotelFrontBoundaryBothEndsResult.md与Saved/CodexOutputs/HotelFrontBoundaryBothEnds_20261021/FinalReview.json。本次两端均获明确授权；勿恢复历史map或重跑旧Apply，其他窄巷不擅自封。**

**2026-10-21 酒店前方正Y端遮挡完成：以用户新保存208f0ab3为输入，只加4自有Actor(旧院墙/实心院门、两回墙、角部补实)，3个独立SM_Hotel模型。原7989Actor完整Native及旧Content/Config全SHA保持；Main/V2/用户资源未改。105条遮挡射线、2条实际绕行/接近路线与4新鲜截图通过，检查相机/灯清零。当前SHA 207475fc8f25798a3243938a619d2b73aa2f4ebf788e6c34a46ac5fb912669a9。见Docs/HotelFrontBoundaryResult.md与Saved/CodexOutputs/HotelFrontBoundary_20261021/FinalReview.json。历史单端限制已由用户本次双端纠正取代；其他窄巷仍不擅自封。勿重跑旧Apply/恢复旧map。**

**2026-10-19 第一版酒店局部修订完成：用户新输入88b4保留，当前SHA 7121a0b22abd6754861c108324b0c8b81a1ddb5b7338c2754a5ddc251fb58d72。四巨型占位柜换低矮实用设施；正面除中央门外三门撤掉并补墙；两侧四内衬墙+六半层平台补片；93门共用八个独立DualHandle新BP，126有效背面把手，原组件/接口/姿态/材质保留。7985Actor，其余7875完整Native一致，1057原门组件Native精确保留；六段楼梯780采样、93闭合门与九截图验证通过，临时相机/灯清零。只保存原版+新Hotel/Revision_20261019资产，旧共享资产/Config不改，用户并行Main与钥匙编辑保留。见Docs/HotelRevisionResult.md及Saved/CodexOutputs/HotelRevision_20261019/FinalReview.json。禁止重跑Apply或恢复历史map。**

**2026-10-19 原版酒店96门闭合修复完成：用户新输入b6756330…保留。62平开+34推拉，8同尺寸共享BP仍复用；叶/把/碰撞/附属玻璃Y内移5cm，96DoorStops组件，62活动合页换3个复用新mesh、其中11个改挂DoorHinge，另11门挡mesh。关闭面齐框，130真实门板射线通过，原保存开合角度/材质/图表/接口不改。7986Actor，其他7828完整Native相同；28街区门、用户资源/Main/V2/Config字节保护。当前原图SHA 909e409519a1ca07c0b21a54ddd85e1afd3b41411823b73ea188ff6cc3b53862。Apply5/HingeParents1/Audit2正常0，4新鲜截图目视检查/临时清零且恢复原姿态，FinalReview PASS。见Docs/HotelDoorClosureResult.md，WORK=Saved/CodexOutputs/OldTownHotelDoorClosure_20261019。勿重跑Apply/恢复旧map；一般优化仍在第二版。**

**2026-10-19 原版两处穿模修复完成：用户输入932de807…保留，在原版仅调整17个助手对象根变换（电杆5+接线3+酒店旧设施9）。电杆向路缘115cm并横担沿街，酒店出口设施沿墙移200cm；门材质/开90度保留。7986Actor、其余7969完整Native一致；所有其他Content/Config字节相同，用户资产/Main/V2未改。当前原图SHA db1d130458a01f70f988080cbf2bcfde355410b78617c311fff590dfe506e92f。保存前/独立重开/4截图正常0、临时相机灯清零，FinalReview PASS。见Docs/OldTownIntersectionFixResult.md，WORK=Saved/CodexOutputs/OldTownIntersectionFix_20261019。勿重跑Apply或恢复旧map；一般优化仍在第二版。**

**2026-10-17 本轮已完成：原版617个助手资产统一Hotel命名并同步引用；348窗/8BP，124门/10BP，7986Actor。原map SHA d906951ed283739c20d3e8491afea6c3b83c193690b6c4e21e0eaa7fa3e2de7c。本轮隔离46个无用旧包+1临时地图；用户资产/Main/V2/Config全字节保护。上轮601追溯修正为595，6个不明材质已原样恢复并保护。FinalReview PASS；见Docs/HotelAssetNamingResult.md及本轮Saved/CodexOutputs/OldTownHotelNaming_20261017。勿重跑任何Apply或恢复旧map覆盖当前用户修改。一般后续优化仍在第二版，用户原版仅按本次明确授权处理。**

**最新完成，2026-10-17：原版124套助手门按实际净尺寸归并10个共享蓝图，124铰链及其他7862Actor完整Native/场景状态相同；原图SHA8d58ec6a…，7986Actor。601个经创建证据/SHA/全项目引用验证的无用自有包已移出Content到Saved可恢复隔离备份，62.25MiB；Main、用户资源、V2和V2仍用的15旧门BP字节保持。15变体探针、Apply、独立重开、fresh引用、cleanup gate、隔离及清理后完整重开/引用检查均通过且正式UE进程正常0，无新增缺失依赖。FinalReview.json已PASS，见Docs/OldTownDoorReuseResult.md；WORK=Saved/CodexOutputs/OldTownDoorReuse_20261017。用户输入8149497f…/历史灯光5dc…禁止恢复覆盖。勿重跑Apply/清理；以后一般优化仍仅第二版，用户资产始终只读。**

**最新完成，2026-10-17：用户授权在原版中继续适配助手灯具，并把剩余装饰灯改成可用灯。原版SHA `5dc2b414c8be65d06c3501cee3895cca28a535540a731f0cc5907b5eab0e1fee`，7986Actor=上轮7952+17真实光源+17无碰撞控制器；共33套（24酒店+9街灯），新增17默认关，旧16身份/参数/13亮3关保留，总13亮20关。新增17槽2私有MI+1玻璃母材，位于FunctionalLighting_20261017；共用M_R_Ceramic_UV仍只读（86非灯具用途），看灯具关卡组件Element2，不看模型默认材质。33个LightStrength=20/0、开关/调光/BPI_Interact均可调用；无实体墙面开关。297实际GameWorld步骤+6提前调用、7952完整Native仅17材质引用变化、2863旧文件保护、4实际照明亮灭截图及临时相机清零全部通过。新证据Saved/CodexOutputs/OldTownFunctionalLighting_20261017/{FinalReview,CurrentLighting}.json；说明Docs/OldTownCallableLighting.md。备份OriginalTownBeforeFunctionalLights_20261017T001824Z；正式Apply3/Readback1/PluginBuild2/RuntimeGame2已正常0。未保存失败已隔离；PP导出标记问题用独立完整6面确认，未放宽比对。Main/BP_LightSwitch/BPI_Interact/V2/旧共享资产/上一轮19灯光资产字节不变；仅自有plugin的显式验证命令扩展，Actor/Editor库源码冻结。后续不要重跑任何旧Apply或覆盖旧验收目录；一般优化继续第二版，原版这次特例不扩展到其他对象。**

2026-10-16。用户已分出自己的原版，助手今后只在“老城区第二版”优化。不要恢复旧版本、重跑旧Apply、覆盖用户原图或共享资产。

- **未来唯一工作关卡** `/Game/CodexGenerated/OldTownVersion2/Maps/老城区第二版`，磁盘 `Content/CodexGenerated/OldTownVersion2/Maps/老城区第二版.umap`，SHA `151e9409f265b3c0d890589a800129037bd318600741c59ee942bdcd2bffb80d`，8017Actor/13929场景组件，保留81审查摄像机供助手截图。
- **用户原版** `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`，历史上按授权删了81台截图CameraActor，未删玩家摄像机或背包SceneCapture；灯光适配前清理后7936Actor、SHA `8e30db760c32d78be98c15b821d238109577b04fbd1bf92cfe3febec0a531718`，最新状态以上方2026-10-17记录为准。除用户明确授权的助手灯具适配外，助手禁止写原版及Main；用户自己的资产始终只读。
- 复制采用UE原生SaveAs后重新加载，源/目标整份Actor、精确SceneComponent、材质、碰撞和用户环境参数比对通过；fresh Input/Create/Readback/PreviewCost辅助进程均正常0。证据WORK `Saved/CodexOutputs/OldTownVersion2_20261016`。
- 用户旧原图输入SHA46c1e88a…：加入DirectionalLight/MoonDirectionalLight/SkyLight/BP_EnvironmentController，改Fog/Atmosphere/Cloud/PostProcess，移除PointLight，均保留。两方向灯已与Main完整核对（111字段+世界变换+3组件），无需再复制或隐藏。当前Main只读SHA4f186543…；用户新PickupBP SHA d3cee7f3…，不要恢复旧cc934d57。
- 完整复制前备份 `D:\UE\Project\HorrorGame\Saved\CodexBackups\OldTownCompleted_BeforeVersion2_20261016T075512Z`，2589文件逐SHA核验，包含当前原图、依赖/生成包、模型源与原Native数据。ReferenceOnly/Main仅参考，不能自动恢复覆盖用户Main。
- **资产隔离规则**：现在复制的是地图，1576配套资源仍共享但对助手冻结。以后改模型/材质/蓝图/RT，先复制到 `/Game/CodexGenerated/OldTownVersion2/`，只给第二版改引用；不得编辑旧OldTown或Yastar共享包，也不得改项目全局设置影响用户地图。未声称全套资产已经各自复制。
- 已完成模型源20变体/222组件（18酒店208+2街区14），原木框/BodySetup/材质覆盖/原WPO保留。SourceAudit20、NativePreservation、55床枕接触已通过。Legacy床垫初轮14侧面重叠已真实修复：冻结侧壁、包边、圆角、底面，只变形上表面；仅owned mesh+cache2包重导，其他38包不变。旧失败971文件在SoftGoodsBeforeOverlapCorrection_20261015T145916Z。
- 当前12361个非空静态模型组件的未舍入世界变换/父子/mesh/material/collision/visible及几何资源字节与修复后Native数据一致（用户PickupBP改动不改变构造出的几何）。据此构建V2当前GeometryDerivation，不假称新导出Native buffers；8719可见组件/344模型/9281596累计三角面。
- 全图全法向/内部面扫描状态：`True`，统计 `{'groups': 503, 'exposed_groups': 0, 'fully_buried_groups': 503, 'inter_exposed': 0, 'intra_exposed': 0, 'exact_duplicate_box_groups': 0}`。仍按0.03cm平面/0.0001法向/1cm²，不能豁免重叠或放宽阈值。新6实际照明+2临时质检截图均normal0、临时灯清零、无地图保存，root已直接看8张。用户夜景的大厅/客房/门面很暗，保持用户照明，不能宣称细节在这些暗图中可见。
- V2登记状态：FinalReview passed=`True`，published=`True`。发布入口 `Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json` 应以最终实际pointer为准；旧Stage3未发布就被用户新输入取代，旧Stage4方向光Apply也没有执行，不要重跑。
- **性能优化必须用户审核**。本次仅查资料/配置/日志/组件与RT，没有应用性能改动。RTX4050Laptop约6GB，当前配置Lumen/VSM等；没有运行帧时间/显存超预算证据。背包RT512×770 RGBA8、ShowOnlyList、保存态每帧捕获，不能当作渲染全老城，也未证实关闭背包后持续采集。建议先只读实测主瓶颈，再审核SC按需捕获/B单段实例化/C室内分级加载，详见WORK/PerformanceProposal.md。
- 摄像机清理不能承诺涨帧；不全局关防重合WPO、不盲目全开Nanite、不改碰撞/全局画质/流送结构。性能用户审批尚待，后续“继续”只授权一般美术优化，不等于批准待审性能选项。
- 保持4层27房酒店中央门/前台、办公室左/安全梯右上/公厕右下，7m车道/1.8m步道/5开放巷/9路缘灯8单向Spot。原18开口BP与MainHome仅证结构/包保护，未新做运行时通关；住宅单元化未实施。
