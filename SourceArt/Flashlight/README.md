# 手电筒模型与外部发光控制

Blender 源文件：`Flashlight.blend`。FBX：`SM_Flashlight.fbx`。

UE5 资产：`/Game/Yastars/Mesh/Flashlight/SM_Flashlight`。

模型长 19.5 cm，灯头直径 5.22 cm。握持中心为原点，灯口朝本地 +X，缩放保持为 1 即为实际厘米尺寸。约 25,920 个三角形，带 3 个凸碰撞体、作者 UV 和 UE5 生成的光照 UV。细节包括防滑握柄、散热环、反光碗、灯口透镜、侧面橡胶按钮、口袋夹、尾盖及真实贯通的挂绳孔。

## 可调材质

两个材质实例位于 `/Game/Yastars/Mesh/Flashlight/Materials`，已经分配给模型：

| 网格材质槽索引 | 材质实例 | 参数 |
| --- | --- | --- |
| 5 | `MI_Flashlight_LED` | `LightStrength`、`LightColor` |
| 6 | `MI_Flashlight_Lens` | `LightStrength`、`LightColor`、`Opacity` |

- `LightStrength` 默认 **0.35**，设为 **0** 关闭自发光，增大则更亮。
- `LightColor` 默认线性 RGB **(0.86, 0.93, 1.0)**，用于改变发光颜色。
- 灯口 `Opacity` 默认 **0.14**，控制透镜透明度。

在编辑器中，双击上述 MI，勾选参数覆盖后修改数值即可。

## 蓝图运行时控制

对手电筒 Static Mesh Component 的材质槽 **5** 和 **6**，分别调用一次 `Create Dynamic Material Instance`，将两个返回值保存为变量。这个创建节点会把动态实例分配到对应材质槽。

开关或调光时，对两个动态实例都调用：

```text
Set Scalar Parameter Value
Parameter Name: LightStrength
Value: 你的亮度值
```

两槽同步设为 0 可关闭整个灯口的自发光；同步设为 0.35 恢复默认柔和状态。改变颜色时，对两个动态实例调用 `Set Vector Parameter Value`，参数名为 `LightColor`。每把手电筒使用自己的动态实例，能分别控制。

灯口自发光用于表现外观，照射前方的光束和场景照明可由你后续添加、控制自己的 SpotLight 组件。

## 验证与预览

`validation_report.json` 确认最终网格无非流形边、FBX 原点与尺寸正确、包含 3 个 UCX，且未导出预览相机和灯光。预览设施位于 Blender 的独立 Preview studio 集合。

`ue_import_report.json` 确认 UE5 尺寸、碰撞体、真实材质槽索引及参数读回。两个新材质实例均实际测试了亮度 0 与 0.8，然后恢复为 0.35 并保存。

`Flashlight_Preview.png` 为整体预览；`Flashlight_Lens_Closeup.png` 和 `Flashlight_Lens_Off.png` 为默认发光及关闭后的灯口对比。实际观感会随 UE5 场景曝光和后期设置变化。
