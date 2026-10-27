# A4 文件板夹

UE 路径：`/Game/Yastars/Mesh/Clipboard`。

| 模型 | 用途 |
| --- | --- |
| SM_Clipboard_Board | 23 × 33.8 cm 硬质纤维底板，含固定安装板、铆钉、铰轴和弹簧 |
| SM_Clipboard_Clip | 可独立控制的金属压夹，含卷边轴套、挂孔和橡胶压条 |
| SM_Clipboard_Paper | 21 × 29.7 cm 独立 A4 横线纸，底角轻微卷曲 |

三件使用相同坐标原点。在蓝图中将它们放在相同位置、相同旋转、相同缩放，即可完成装配。白纸可隐藏或单独拿走。

纸张已改为 8 mm 间距的浅蓝横线，并加上左侧红色页边线；线条烘焙在 4K BaseColor 中，背面不印线。最新更新记录见 `RuledPaper/update_report.json` 和 `RuledPaper/ue_update_report.json`。

底板厚约 3.3 mm。压夹转轴相对 **UE 模型原点**的位置为 **X=0、Y=-14.8 cm、Z=1.1 cm**，轴向为 X。Blender 源文件中该点为 `(0, 0.148, 0.011)` 米，FBX 导入 UE 后 Y 方向翻转。需要张合动画时，可在 UE 的该位置放一个 Scene Component，再将活动压夹挂到它下面旋转。当前交付为静态模型，未包含动画或弹簧模拟。

每件都有 BaseColor、Roughness、Normal、Metallic 贴图和独立材质，UE 材质提供 Tint 参数。包含自定义碰撞与 UV；预览中的灯光、地面和相机仅保留在 Blender，未导入 UE。

源文件为 `Clipboard.blend`。默认显示完整装配，隐藏集合保留原点统一的导出网格与独立零件。

尺寸和结构参考 Rapesco 硬质文件板夹：
https://rapesco.com/product/business-pack-pack-of-4-heavy-duty-hardboard-clipboard-a4-brown/

`validation_report.json` 记录网格、UV、FBX 回读、贴图和实际渲染；`contact_verification.json` 记录装配检查；`ue_import_report.json` 与 `final_verification.json` 记录 UE 和最终文件检查。
