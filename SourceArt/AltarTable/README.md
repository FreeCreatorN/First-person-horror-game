# 长方形传统供桌

Blender 源文件：`AltarTable.blend`。FBX：`SM_AltarTable.fbx`。

尺寸为 **220 × 60 × 95 cm**。平直长桌面采用边框和长桌板结构；前脸为云形牙板、中央嵌入式如意云纹浮雕和真实凹槽，配四条方腿、马蹄式脚端、侧面横撑与后部横撑。木色为红棕色，带适度磨损及木纹凹凸。

## UE5

目录：`/Game/Yastars/Mesh/AltarTable`。

- `SM_AltarTable`：完整单一静态网格，约 33,646 个三角形。
- `Materials/M_AltarTable`：统一烘焙材质，`Tint` 参数可调整木色。
- `Textures`：BaseColor 4096²、Roughness 2048²、Normal 2048²。

模型原点位于地面中心，缩放保持 1 即为实际尺寸；UE 本地 +Y 为正面。14 个分段凸碰撞体按桌面、腿、牙板与横撑设置，保留桌下空间。

模型材质没有自发光。预览灯、相机与地面属于独立 Preview studio 集合，没有导出到 FBX。

## 验证与编辑

`validation_report.json` 记录拓扑、UV、FBX 导回及贴图写盘重载验证。`ue_import_report.json` 记录 UE5 实际读取的尺寸、材质、贴图与碰撞数量。Normal 在 Blender 中使用 +Y，在 UE 纹理中翻转了绿通道。

Blender 中当前显示同套烘焙贴图，原程序木纹材质也保留在文件中。整体与雕花预览分别为 `AltarTable_Preview.png`、`AltarTable_Detail.png`。
