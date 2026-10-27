# 配套老式木餐椅

与大餐桌配套的旧木餐椅，实木座面，无坐垫。设计整体尺寸约 48 × 53 × 106 cm，实际尺寸以模型和 UE 导入报告为准。

实测约 **48 × 52.4 × 106 cm**，座缘高 **46 cm**，座面中心浅凹 **6.5 mm**，靠背后倾约 **8.25°**。前方为圆转木腿，后腿连续延伸为靠背立柱，配三根弯曲竖木条、弧形冠梁及 H 形低横撑。材质与 `LargeDiningTable` 使用相同木色设置。餐桌围板下高 64.8 cm，与座缘之间约有 18.8 cm 高度差。

成品为 **10,270 个三角形**，**23 个分段凸碰撞体**，保留靠背及椅腿之间的实际空隙。原点位于地面中心，UE 本地 +Y 为椅子正面。

源文件：`DiningChair.blend`。导出网格：`SM_DiningChair.fbx`。模型使用米建模，导入后为 UE 厘米单位；缩放保持 `(1,1,1)`。

## UE5 资源

唯一目标目录：`/Game/Yastars/Mesh/DiningChair`。

- `SM_DiningChair`：完整餐椅静态网格。
- `Materials/M_DiningChair`：无自发光的烘焙 PBR 材质，`Tint` 默认白色，可调整木色。
- `Textures/T_DiningChair_BaseColor`：颜色，sRGB。
- `Textures/T_DiningChair_Roughness`：粗糙度，线性数据。
- `Textures/T_DiningChair_Normal`：切线法线，线性数据；Blender 为 +Y，UE 翻转绿通道。

原始 `M_Chair_Wood`、`M_Chair_Endgrain`、`M_Chair_Dark` 三个槽统一绑定同一图集材质。分段 UCX 碰撞数量从 `model_report.json` 读取，并与 UE 实际数量核对。

颜色图为 4096²，粗糙度及法线为 2048²；Blender 成品显示从磁盘重新读取的同套 PNG。隐藏的 `SOURCE - editable hardwood chair components` 集合保留独立木件和原始程序材质；`Preview studio - excluded from FBX` 内的相机、灯光与地面只用于预览，均未导出。

## 导入

`run_import.ps1` 使用完整 UE 编辑器、`-ExecutePythonScript`、无人值守及离屏渲染执行 `import_ue.py`，完成后自动退出。若已有 UE 编辑器运行，脚本会停止，避免第二个进程同时写项目。

此辅助进程使用引擎自带 Entry 作为临时工作环境；不加载或保存用户地图，不放置 Actor，也不创建项目关卡。导入仅写上述专用资源目录，已有模型、材质和贴图默认保留。

必须同时检查 `ue_import_completion.json` 的正常退出，以及本次新生成 `ue_import_report.json` 中的 `success=true`；脚本会拒绝把上次遗留报告当作本次导入成功。

## 核验

`model_report.json` 记录尺寸、材质槽、拓扑和碰撞数据；`validation_report.json` 记录 Blender、UV、FBX 导回和贴图检查；`ue_import_report.json` 记录 UE 中实际读回的资源路径、尺寸、材质、UV 和碰撞。贴图需要 UV0，生成光照 UV 的设置另行记录，不用源通道数量判断渲染数据中是否包含生成的 UV1。

`DiningChair_Preview.png` 为完整餐椅渲染，`DiningChair_Detail.png` 展示座面、后柱和靠背接合。模型非流形边、孤立顶点、零面积 UV 三角形均为 0；榫接检查记录实际组件包围盒重叠，并进行了结构审阅及渲染目视检查。
