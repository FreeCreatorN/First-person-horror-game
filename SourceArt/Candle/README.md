# 未点燃蜡烛

UE 资源：`/Game/Yastars/Mesh/Candle/SM_Candle`。

米黄色蜡身、连续流蜡、融蜡凹槽、弯曲烛芯和做旧黄铜承蜡盘，合成一个完整静态网格，拖入关卡即可摆放。原点位于底部中心。

整体约 **11.24 × 11.24 × 15 cm**，蜡身直径约 **4.5 cm**。流蜡直接塑在蜡身表面，底部蜡迹与蜡身相接。

提供 BaseColor、Roughness、Normal、Metallic 四张贴图，材质带 Tint 参数。包含 UV 和自定义凸碰撞。

**没有自发光、火焰或场景灯光。** 后续可在 UE 中单独添加并控制火焰、光源和开灭；烛芯顶端相对模型原点的参考位置约为 `(-0.1, 0.06, 14.65)` cm。

源文件：`Candle.blend`。预览灯光、相机和地面仅用于 Blender 展示，没有导出到 UE。隐藏集合保留原点统一的导出网格与独立源零件。

`validation_report.json` 记录网格、UV、FBX 回读、贴图烘焙和实际渲染；`ue_import_report.json`、`ue_import_completion.json` 与 `final_verification.json` 记录导入与最终检查。
