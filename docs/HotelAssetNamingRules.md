# 酒店资源命名规则

统一使用 `类型_Hotel_用途与特征`，从名字即可判断资源类型、用途和尺寸。尺寸单位为厘米；`W / H / D` 分别表示宽、高、深。

| 类型 | 前缀 | 示例 |
| --- | --- | --- |
| 窗户蓝图 | BP | `BP_Hotel_WindowDouble_W117_H112_D20` |
| 房门蓝图 | BP | `BP_Hotel_DoorR_W80_H205_D20` |
| 灯光控制蓝图 | BP | `BP_Hotel_LightCircuit` |
| 模型 | SM | `SM_Hotel_DoorJambLeft` |
| 材质 | M | `M_Hotel_Wood_UV` |
| 材质实例 | MI | `MI_Hotel_DoorLeaf_PaintedWood_UV_50b652a3` |
| 贴图 | T | `T_Hotel_Wood_BaseColor` |

门的名字中，`DoorL` 表示左开，`DoorR` 表示右开，`DoorLR` 表示兼有左右开门，`DoorSlider` 表示推拉门，`DoorSwingSlide` 表示同尺寸组同时包含平开与推拉形式。

材质名保留具体表面和用途，例如 `DoorLeaf`、`WindowFrame`、`Ceramic`、`LampTube`、`StreetLampLens`。`UV` 表示模型 UV 贴图，`World` 表示世界投影，`SurfaceDetail` 表示表面细节版本。贴图以 `BaseColor`、`Normal`、`Roughness` 区分颜色、法线和粗糙度。

相同用途但内容不同的资源可带短码，避免重名。名称不保留旧生成前缀或日期批次，也不重复添加 `Hotel`。
