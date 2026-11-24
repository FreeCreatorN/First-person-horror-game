# 纸箱套组 UE 资产

目标目录：`/Game/Yastars/Mesh/CardboardBoxSet`。

八个款式对应十三个独立静态网格：A 封口箱、B 箱体及四片盖板、C 收纳箱体及独立箱盖、D 破损箱、E 两箱堆叠、F 水果箱、G 饮用水箱、H 方便面箱。B 和 C 另外提供装配好的 `BP_CardboardBox_B_Open` 与 `BP_CardboardBox_C_Storage`，可直接拖入关卡。盖板和箱盖各自保留导出原点；没有添加交互事件或动画。

每个款式的组合三角面数量在 200–800 范围。所有静态网格使用导出的 UCX 简化碰撞。七个材质槽分别对应 Standard、Damaged、Fruit、Water、Noodles、Tape、Edge；前五组使用 2K BaseColor / ORM，胶带与纸板边缘使用独立 512px BaseColor / ORM，并共用 2K 法线贴图。ORM 的 R、G、B 分别为环境遮蔽、粗糙度、金属度。

源法线为 OpenGL +Y，UE 导入设置已打开 Flip Green Channel，转换成 UE 使用的 DirectX 法线方向。BaseColor 使用 sRGB；ORM 与法线关闭 sRGB，并分别使用 Masks 与 Normalmap 压缩。

UE 编辑器全部关闭后，运行 `run_exclusive.ps1`。它先校验导出清单，再使用隐藏的临时 Entry 场景导入新目录，随后另开一个隐藏编辑器重新加载验证。仅检查已完成导入的资产可运行 `run_exclusive.ps1 -VerifyOnly`。脚本拒绝覆盖已有目标目录，不改动或保存项目关卡。结果写入 `final_verification.json`。

导出清单的 `pivot_m` 是组装空间中的 Blender 米制原点，`bounds_min_m` / `bounds_max_m` 是减去该原点后的局部网格范围。蓝图将该原点转成 UE 厘米坐标重新装配。导入使用 FBX 自带厘米比例，额外缩放为 1。

验证记录 UV0 贴图通道，并记录是否具有单独灯光贴图通道；旧版 FBX 导入在部分网格上只报告 UV0 时，不阻断已通过验证的 PBR 材质。静态烘焙灯光前可按项目需求生成或检查灯光贴图 UV。
