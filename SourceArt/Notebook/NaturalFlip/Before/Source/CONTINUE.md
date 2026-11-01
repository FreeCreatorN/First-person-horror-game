# Notebook 完成记录

日期：2026-10-30。用户需求：按概念参考制作牛皮纸封面、布脊、红书签、横线内页笔记本，并能在UE调用翻页动画。

状态：已完成制作与UE导入，`UE/final_verification.json` 为 `NOTEBOOK_FINAL_VERIFIED True` 的证据。Blender GUI打开的是本目录 `Notebook.blend`；只改变过视角和时间线，没有在UE导入后另存源文件。

UE目录：`/Game/Yastars/Mesh/Notebook`，76个新包。SK/Skeleton、19条动画（完整一条+18独立片段）、2个新BP、14张纹理、7个父材质、32个页材质实例。动画在Notebook目录，不在Animations子目录。

`BP_Notebook` 初始正面闭合暂停，Box碰撞BlockAll；`BP_Notebook_Demo` 自动完整播放一次，碰撞关闭。SK没有PhysicsAsset。只适用于初始正面闭合的Box碰撞，在阅读和最终反面闭合状态不能当作逐页碰撞使用。尚未绑定已有WBP_Notebook按钮或改现有数据。

32个页实例的PageTexture可改为图片或RenderTarget；会随骨骼弯曲。已有横线底图需在自定义内容里保留。操作见 `UE使用说明.md`；帧驻留表在 `page_stops.json`。

源拓扑35756三角、17920顶点、156骨，最多2个权重。16张叶片、32面纸。骨骼弧长积分控制弯曲，封皮和可压扁的布脊同步开合。纸边/书脊/书签已统一重算法线，书签不穿底页。所有FBX只导出SK和骨架，未导出预览灯光/地面/相机。

完整动作frame1..781/30fps，26秒：封面1..49；翻第i张（i从0开始）71+40i..99+40i；最后合书721..769。源.blend使用米。**UE FBX必须跑export_ue_centimeters.py，全部骨头静态位置和位移曲线、网格均临时转换厘米，root缩放1，UE mesh/anim import scale均1。** 不要恢复先前米制FBX的root100方案，UE默认压缩会删除局部微小位移导致穿插。

验证含21个真实COMPRESSED且retarget=True的源骨关键坐标、18独立片段首尾与FullCycle比对（位置容差.02cm）、38槽/32PageTexture实例、动画bounds扩展、两个BP配置、主导入正常exit0和新UE进程回读正常exit0。46个现有UI/Items/地图/Config文件的SHA和文件集未变。UE和ShaderCompileWorker已退出。

失败诊断均保留在UE/Failed*，并未在失败时保存目标包：早期scale100令SK巨大、AnimationLibrary的Python别名、压缩异步尚未完成、米制root100下位移丢失。必须同步Editor.AsyncAssetCompilationFinishAll后检查真实压缩动画；should_retarget=False会强制回RAW，不能据此证明运行时动画正确。fresh回读需要把UE对象收进函数作用域并在退出前gc，避免Python清理崩溃。

后续重建顺序见README。不要直接对已存在UE目录重跑初次导入器（有保护拒绝覆盖）。需按明确修改范围准备备份和更新脚本。源/纹理/FBX的SHA已绑定验证报告，编辑后需重新核实。
