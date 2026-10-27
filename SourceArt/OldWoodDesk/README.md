# 老式实木桌

Blender 源文件：`OldWoodDesk.blend`。

桌面约 120 × 64 cm，桌高约 77 cm。结构包括五块长桌板、两侧封头板、四条收分桌腿、围板、底部横撑、榫接木销、独立抽屉和木质拉手。木纹、边缘磨损、细划痕、粗糙度与木孔凹凸已烘焙为贴图。

## UE5 资产与组装

目录：`/Game/Yastars/Mesh/OldWoodDesk`。

- `SM_OldWoodDesk_Base`：桌架与桌面，17 个凸碰撞体。
- `SM_OldWoodDesk_Drawer`：抽屉盒、前板和拉手，6 个凸碰撞体。
- `Textures`：两套 BaseColor、Roughness、Normal，共六张 PNG。
- `Materials`：桌架与抽屉各一套烘焙材质，`Tint` 参数可调整木色。

两个网格共用地面中心原点。放在同一个 Actor 下时，相对位置、旋转都设为 `(0,0,0)`，缩放保持 `(1,1,1)`，即为完整闭合状态。UE 单位为厘米。

抽屉沿本地 **+Y** 方向平移 **23 cm** 为打开状态，即相对位置从 `(0,0,0)` 到 `(0,23,0)`。若运行时移动，先将抽屉组件 Mobility 设为 Movable。Blender 对应移动方向是 -Y。

木桌碰撞按桌面、腿、围板、导轨和横撑分别设置，保留桌下空间与抽屉开口。

## 贴图与源材质

每部件的 BaseColor 为 4096 × 4096；Roughness 与 Normal 为 2048 × 2048。BaseColor 使用 sRGB，其余为 Non-Color；Blender 切线法线采用 +Y，UE 纹理已翻转绿通道。

Blender 中显示的是从磁盘重新载入的同套烘焙贴图。原始程序木纹材质仍保留在文件中，可重新分配、修改并烘焙。所有模型材质均无自发光。

预览灯、相机和地面在独立 Preview studio 集合中，不在 FBX 里。

## 验证

`model_report.json` 记录尺寸、三角形、材质槽与碰撞体。`validation_report.json` 记录无非流形边、UV 范围和零面积检查、五个抽屉位置的无相交验证、FBX 导回检查，以及六张贴图写盘重载与预览结果。`ue_import_report.json` 记录实际 UE5 导入、材质、UV 和碰撞读回。

预览：`OldWoodDesk_Preview.png`（闭合）、`OldWoodDesk_DrawerOpen.png`（打开）。
