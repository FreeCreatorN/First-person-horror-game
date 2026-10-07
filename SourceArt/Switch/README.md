# 墙壁翘板开关

Blender 源文件：`WallSwitch.blend`。使用 cli-anything-blender 建立草模场景，再通过 Blender MCP 制作圆角面板、按钮凹槽、背部安装架、转轴和接线凹位。

面板长宽为 8.6 × 8.6 cm。后部机构嵌入墙面；底座原点位于墙面中心。前方在 UE5 中为本地 +Y，向上为 +Z。

UE5 资产位于 `/Game/Yastars/Mesh/Switch`：

- `SM_Switch_Base`：底座、面板及后部安装结构，5 个凸碰撞体。
- `SM_Switch_Rocker`：独立翘板和转轴，1 个凸碰撞体。原点在转轴中心。
- `Materials`：暖白塑料、深色塑料及钢材，均没有自发光。

在同一个 Actor 中添加底座和按钮两个 Static Mesh Component，保持缩放为 1。底座相对位置为 `(0, 0, 0)`；按钮相对位置为 `(0, 0.3, 0)` cm。按钮绕本地 X 轴转动，UE5 对应 Roll；两个端点为 -4° 与 +4°。若需要运行时旋转，将按钮组件 Mobility 设置为 Movable。灯具控制逻辑由使用者自行连接。

Blender 文件第 1–96 帧有按动演示；两个 FBX 为中立角度的静态模型，不包含动画、预览灯光、相机或墙面。预览设施放在单独的 Preview studio 集合中，已在编辑视图隐藏。

验证结果记录在 `validation_report.json` 与 `ue_import_report.json`：

- 两个模型均无非流形边，有 UV。
- 按钮外壳在 -4° 到 +4° 的 9 个采样角度均未与底座表面相交；转轴与轴承的安装接触不作为外壳碰撞检查对象。
- FBX 回读确认模型原点、尺寸、碰撞体数量，以及没有导出灯光或相机。
- UE5 导入后确认尺寸、材质与凸碰撞体数量，并保存成功。
