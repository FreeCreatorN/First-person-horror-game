# 透明螺口灯泡

UE 资源：`/Game/Yastars/Mesh/LightBulb/SM_LightBulb`。

约 **6 cm 直径、10.5 cm 高**，透明玻璃壳、内部玻璃支撑柱、引线、线圈灯丝、连续螺旋灯头、黑色绝缘体和底部触点，合为一个完整静态网格。原点位于灯头底部触点中心，含自定义凸碰撞和 UV。

三种独立材质：

| 材质 | 用途 |
| --- | --- |
| M_LightBulb_Opaque | 金属灯头、触点、绝缘体与内部引线，使用四通道 PBR 贴图 |
| M_LightBulb_Glass | 玻璃，参数 Opacity、GlassRoughness、IOR、GlassTint 可调 |
| M_LightBulb_Filament | 灯丝，参数 GlowStrength、EmissiveColor、BaseColor 可调 |

**默认不发光：GlowStrength=0。** 右键灯丝材质创建材质实例，即可勾选并调节 GlowStrength；例如 5 可作为较弱发光的起点。运行时可对灯丝所在材质槽创建动态材质实例，再用 Set Scalar Parameter Value 设置 GlowStrength。EmissiveColor 控制颜色。

这里提供灯丝材质的视觉发光，不包含场景 Point Light 或 Spot Light。需要照亮环境时，可另加由你控制的灯光。玻璃和金属不会跟随灯丝参数一起发光。

Blender 源文件：`LightBulb.blend`。默认关灯；`LightBulb_OnPreview.png` 仅为临时开启灯丝发光的效果预览。预览灯光、地面和相机未导入 UE。

比例与外形参考：
https://www.signify.com/global/prof/conventional-lamps-and-tubes/incandescent-lamps/gls-specialties/philips-standard-extra-low-voltage-a60/920021020517_EU/product

`validation_report.json` 记录网格、UV、FBX 回读、贴图与实际渲染；`ue_import_report.json`、`ue_import_completion.json` 和 `final_verification.json` 记录导入及最终核对。
