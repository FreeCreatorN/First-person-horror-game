# 复古胶片照相机

UE 资源路径：`/Game/Yastars/Mesh/Camera/SM_Camera`。

快门按钮已独立为同目录的 `SM_Camera_ShutterButton`。机身上提供 `ShutterButton` 插槽；将按钮组件挂到这个插槽并把相对位置、旋转设为 0，缩放设为 1，即可正确装配。沿按钮本地 Z 轴移动到 **-0.12 cm** 为按下位置，回到 **0** 为弹起位置。当前模型默认弹起。

银色金属机顶与黑色蒙皮，包含独立玻璃镜片、镜头调焦纹、光圈叶片、取景窗、快门按钮、拨盘、卷片扳手、热靴触点、背盖与胶卷提示框。机身与快门按钮为两个静态网格，装配后宽约 15.13 cm，含镜头前后深约 10.87 cm，高约 10.11 cm。

材质分为 `M_Camera_Opaque` 与 `M_Camera_Glass`。金属与蒙皮使用 2K BaseColor、Roughness、Normal、Metallic 四张贴图，玻璃保留单独的透明参数。模型自带四个简单凸碰撞体，正面朝 Blender -Y。

`Camera.blend` 中机身和按钮分别为 `VIEW_Camera`、`VIEW_Camera_ShutterButton`，`SOURCE - individual components` 保留原始可编辑零件。导出文件为 `SM_Camera.fbx`、`SM_Camera_ShutterButton.fbx`。按钮的原点在底部，保留原贴图坐标。按钮拥有独立碰撞，机身碰撞已避免包住按钮。`ShutterSplit/Camera_Shutter_Released.png`、`Camera_Shutter_Pressed.png` 是拆分后的弹起与按下预览。摄影棚灯光、地面及渲染相机仅用于预览。

`model_report.json` 和 `validation_report.json` 记录当前两个模型的几何、UV、FBX回读及原贴图复用证据。当前 UE 更新报告、按压预览和核验报告位于 `ShutterSplit`；运行根目录 `verify_final.py` 可核验当前版本。`ShutterSplit/Before` 保留拆分前的模型与 UE 资源备份。

生成流程分两阶段：先运行 `build.py`、`bake_set.py` 生成基础模型和贴图，再运行 `ShutterSplit/split_model.py` 拆分按钮并保留原 UV。直接编辑当前 `.blend` 时，按钮已是独立对象。
