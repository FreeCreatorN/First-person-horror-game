# 按压圆珠笔

UE 资源：`/Game/Yastars/Mesh/Pen/SM_Pen`。

长约 14.21 cm，墨绿色笔身、拉丝金属上盖、连续弹片笔夹、按键、笔尖滚珠以及浅凹握持纹。完整静态网格，原点在笔尖接触点；笔尖朝 Blender -Z，模型本身位于 Z≥0。带两个自定义凸碰撞体及 UV。

材质 `M_Pen` 使用 BaseColor、Roughness、Normal、Metallic 四张贴图；`Tint` 参数可在材质实例中调整颜色。默认无发光。场景灯光、地面、相机仅供预览，未导入 UE。

`Pen.blend` 保留独立零件供编辑，显示集合为 `Pen - display assembly`。FBX：`SM_Pen.fbx`。当前版本为笔芯伸出的静态外观，没有按压动画。

主预览 `Pen_Preview.png`，笔夹与按键特写 `Pen_Detail.png`，笔尖特写 `Pen_TipDetail.png`。

`validation_report.json`、`ue_import_report.json`、`ue_import_completion.json` 和 `final_verification.json` 记录实际建模、贴图、导入及校验结果。
