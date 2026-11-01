# 可翻页的「手记」笔记本

按 `Design_v01/Notebook_OverallStyle_v01.png` 制作的独立三维资源。牛皮纸硬封面、深色布脊、印刷标签、红棕织带书签、双面横线内页。封面标签和横线是贴图，没有浮空字或线。

- Blender源文件：`Notebook.blend`，单位米，时间线1～781，30fps。
- 16张独立可弯曲的纸叶，32个可换内容的纸面；35756个三角形、156根骨骼，最多2个权重/顶点。
- `Exports/SK_Notebook.fbx`：模型和骨架；其它19个FBX是完整动画与18个独立动作。
- `Notebook_Closed.png`、`Notebook_Open.png`、`Notebook_Turning.png`、`Notebook_LastPage.png`：实际模型渲染。
- `Notebook_Flip_Preview.gif`：保存的骨骼动画实际渲染，演示开封和前两次翻页。
- `UE使用说明.md`：蓝图调用、上一页/下一页、页内容替换及碰撞说明。
- `page_stops.json`：完整动画的阅读驻留时间。
- UE目标目录：`/Game/Yastars/Mesh/Notebook`。现有 `Yastar/UI` 和 `Yastar/Items` 的笔记本逻辑独立保留。

## 重建顺序

`make_textures.py` 生成原创新纹理；`seed_cli.ps1` 使用已安装的 CLI-Anything skill 创建场景及真实预览；Blender中运行 `build.py` 构建源文件和渲染；运行 `finish_exports.py` 生成源骨姿态证据；最后运行 `export_ue_centimeters.py` 输出给UE使用的厘米FBX。

**最后一步不可省略。** Blender可编辑源文件保持米单位；导出器临时把网格、骨骼原点和位移曲线一起转换为厘米，骨架缩放保持1。UE模型与动画的导入缩放均为1。这样UE压缩器能保留纸页和书脊的小幅位移。直接使用米制骨架的100倍父级缩放，会导致压缩器错误省略页片位移。

`model_report.json` 中的SHA绑定最后导出的文件。UE导入期间不要另存源文件或替换FBX/贴图。仅改变Blender视角和时间线且不保存不会影响证据。

## 验证

`model_report.json` 记录源拓扑、权重、材质顺序、动画范围、阅读位置与关键骨的厘米坐标。UE文件夹中的报告和验证器负责检查导入后的实际压缩动画，而不是只检查原始曲线；独立动作的首尾姿态应与整条动画一致。

预览灯光和地面只在Blender源文件的STUDIO集合中；FBX只导出模型和骨架。导入资源没有灯光和发光材质。
