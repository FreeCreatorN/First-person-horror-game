# 老式实木大餐桌

设计尺寸：240 × 105 × 76 cm，按八人餐桌比例制作。单一导出模型，原点位于地面中心，UE 缩放保持 `(1,1,1)` 即为实际尺寸。

六块纵向实木桌板、横向封头、四条圆转木腿、方形榫接肩、四面围板、桌底横档和斜角撑均有实际几何。围板下净高约 64.8 cm，长边腿间净宽 189 cm，端部腿间净宽 65 cm。木销及螺钉嵌入接触面。成品约 20,272 个三角形，11 个分段凸碰撞体；桌下空间保持开放。

Blender 的 `SOURCE - editable joinery components` 隐藏集合保留独立组件，便于修改；`Preview studio - excluded from FBX` 集合只服务预览。两个集合都未导出，FBX 仅含成品网格及 UCX 碰撞。

Blender 源文件为 `LargeDiningTable.blend`，导出文件为 `SM_LargeDiningTable.fbx`。

## UE5 目录

唯一导入目录：`/Game/Yastars/Mesh/LargeDiningTable`。

- `SM_LargeDiningTable`：完整大餐桌静态网格。
- `Materials/M_LargeDiningTable`：无自发光的烘焙 PBR 材质，`Tint` 默认白色，可调整木色。
- `Textures/T_LargeDiningTable_BaseColor`：颜色贴图，sRGB。
- `Textures/T_LargeDiningTable_Roughness`：粗糙度贴图，线性数据。
- `Textures/T_LargeDiningTable_Normal`：切线法线，线性数据；Blender 使用 +Y，UE 翻转绿通道。

三个原材质槽 `M_Dining_Wood`、`M_Dining_Endgrain`、`M_Dining_Dark` 均绑定同一套烘焙材质；各处木材外观已包含在 UV 图集中。BaseColor 为 4096²，Roughness/Normal 为 2048²；Blender 成品显示重新从磁盘载入的同套 PNG，原始程序材质保留在源组件上。

## 导入与查看

`import_ue.py` 在完整 UE 编辑器中运行，默认保留已经存在的模型、材质和贴图。只操作上述专用资产目录，不加载或保存关卡，不放置场景 Actor。

已验证的自动导入入口为 `run_import.ps1`：使用完整编辑器离屏执行，成功后自动退出，检查进程正常退出和导入报告两项结果。

`open_in_ue.py` 只加载已导入的 `SM_LargeDiningTable`、在内容浏览器中定位，并打开静态网格资源编辑器；不重新执行导入。`ue_open_report.json` 记录打开前后的当前关卡路径和同一 World 对象检查。

## 核验记录

`model_report.json` 记录建模数据，`validation_report.json` 记录 Blender/FBX/贴图核验，`ue_import_report.json` 记录实际导入结果、尺寸、材质、UV 与碰撞。导入脚本只要求正确的贴图 UV0，同时记录光照 UV 的生成设置，不用源 UV 通道数量推断渲染数据中的生成通道。

`LargeDiningTable_Preview.png` 为完整餐桌实渲染，`LargeDiningTable_Detail.png` 展示桌角、封头和桌腿连接。模型非流形边、孤立顶点和零面积 UV 三角形均为 0；连接检查记录了各榫入部位的实体包围盒重叠，未将其表述为完整的表面相交检测。
