# 原版老城区灯光调用

2026-10-17，已完成。目标是用户的原版关卡 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`。本轮按用户“把那几个装饰灯也改成可用灯”的要求，仅调整助手制作的灯具；Main、BP_LightSwitch、BPI_Interact、用户资产、原有共享材质和老城区第二版保持原文件。

原版现在共有 **33 套可调用灯具：24 套酒店灯、9 套街道路灯**。原有 16 套保留身份、位置、光照参数及初始状态（13 亮、3 关）。本轮给剩余 **16 套酒店装饰灯和路灯 03** 各补一个真实光源、私有灯罩材质和控制器，新增 17 套默认关闭，总初始状态为 **13 亮、20 关**。

新增酒店灯为 F0 至 F3 每层的 `GalleryTube00/02/03/05`，街灯为 `OTS_P2Prop_StreetLamp_03`。新增资源位于 `/Game/CodexGenerated/OldTown/FunctionalLighting_20261017`，包含 17 个材质实例和 1 个专用玻璃母材。原有 16 套继续使用 `/Game/CodexGenerated/OldTown/CallableLighting_20261016` 中冻结的资产和控制器蓝图。

## 找到正确的灯罩材质

在**原版关卡**选中灯具，打开 `StaticMeshComponent → Materials → Element 2` 上实际绑定的 `MI_OTS_…` 材质实例。`LightStrength` 为 20 时全亮、0 时关闭、10 时半亮。静态模型资源自身的默认材质没有改，查看模型默认材质或旧共享母材不能代替查看关卡组件的实际覆盖。

`M_R_Ceramic_UV` 是共享陶瓷母材，原先还直接用于 86 处非灯具部件，包括马桶、洗手盆和淋浴底盘，因此没有给它整体添加发光。原先漏掉的 16 个酒店灯罩已逐个换成私有实例。酒店灯保留局部灯管遮罩，端座和灯架不整体发光；路灯 03 使用原透明玻璃的专用副本，保留透明度、非发光表面通道和防重合位移。

## 调用与预览

控制器位于场景大纲的 `OldTownSchoolStreet/Lighting/CallableCircuits` 文件夹，名称为 `OTS_LightCircuit_…`，蓝图为 `BP_OTS_LightCircuit`。每个控制器只引用一套灯罩和一个真实局部光源。

在其他蓝图中取得对应控制器引用后，可以使用：

- `Interact (Message)`：沿用现有 BPI_Interact 接口，切换这一组灯。
- `Set Light On`：布尔值指定开或关。
- `Set Light Level`：0 至 1 调光，灯罩与真实光源同步；可接时间轴制作闪烁。
- `Get Light State` / `Get Light Level`：读取状态。
- `Get Interact Text (Message)`：返回“开灯”或“关灯”。

整盏灯的亮灭应通过控制器调用。单独修改材质参数只改变灯罩发光，不会同步真实光源。每套灯在 BeginPlay 创建自己的动态材质，互不串灯。私有母材使用 LightStrength/20 归一化，保留既有全亮强度。

Main 的 BP_LightSwitch 原设计固定接 RectLight 数组及材质槽 3；此适配通过接口和新控制器支持 Rect/Spot 及槽 2。因此调用目标应选对应控制器；本次没有改动原 BP_LightSwitch 的数组或逻辑。场景中尚未布置实体墙面开关，已有角色的射线不会自动命中这些无碰撞控制器。

控制器详情面板提供 `Preview On`、`Preview Off`、`Toggle Light` 和 `Restore Editor Preview`。保存地图及进入 PIE 前会还原临时预览。`Initially On` 决定运行时初始开关；想让新增灯进游戏就亮，可勾选此项。预览按钮不改变这一设置。本轮保存的灯罩与光源初始状态已同步。

## 验证、截图与备份

最终验收通过，当前地图 SHA256 为 `5dc2b414c8be65d06c3501cee3895cca28a535540a731f0cc5907b5eab0e1fee`。

- 真实 GameWorld BeginPlay：33 组各 9 步，共 297 步，另有 6 种提前调用组合，全部通过。每一步都检查其他灯不受影响；新增 17 套逐一确认默认关闭。
- 全新进程读回：既有 7952 个 Actor 的完整原生文本仅有指定的 17 处材质引用变化，旧 16 个控制器、灯光和用户环境保持原状态。新增 17 个光源与 17 个控制器后共 7986 个 Actor。
- 2863 个既有 Content/Config 文件保持原字节，目标地图之外没有改动旧资源；原有 19 个灯光适配资产、Main、用户蓝图和第二版均保持。
- 四张实际照明截图均正常完成，33 套灯的临时预览已还原，临时相机清零，地图和资源未因截图再次保存。未进行新的全图几何扫描，也未测试打包后的 Shipping 版本。

本轮新增灯具的实际亮灭对照：[酒店开灯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/OldTownFunctionalLighting_20261017/Preview/Renders/FUNC_Hotel_On.png)、[酒店关灯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/OldTownFunctionalLighting_20261017/Preview/Renders/FUNC_Hotel_Off.png)、[路灯开灯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/OldTownFunctionalLighting_20261017/Preview/Renders/FUNC_Street_On.png)、[路灯关灯](D:/UE/Project/HorrorGame/Saved/CodexOutputs/OldTownFunctionalLighting_20261017/Preview/Renders/FUNC_Street_Off.png)。关灯后的酒店画面很暗，只用于核对亮灭，不作细节质量证明。

本轮 [最终验收](D:/UE/Project/HorrorGame/Saved/CodexOutputs/OldTownFunctionalLighting_20261017/FinalReview.json) 与 [完成入口](D:/UE/Project/HorrorGame/Saved/CodexOutputs/OldTownFunctionalLighting_20261017/CurrentLighting.json) 位于 `Saved/CodexOutputs/OldTownFunctionalLighting_20261017`。修改前地图备份为 `Saved/CodexBackups/OriginalTownBeforeFunctionalLights_20261017T001824Z/L_OldTownSchoolStreet.umap`，原 SHA256 为 `d907f4dfff07ec83011337b34107427b61d39efd1479134035ed749d73a8a8c7`；旧插件也已独立备份。

前两次未保存的创建/导出尝试已隔离并保留失败证据，正式成功记录为 Apply3、Readback1、PluginBuild2、RuntimeGame2。原生导出标记残留已用独立模型六面数据确认并解决，完整对象比对没有豁免或过滤。

上一轮 2026-10-16 的 16 灯验收目录保留为历史证据，不覆盖它的报告，也不重跑旧 Apply。一般美术优化仍只在第二版进行；这次原版灯光授权不扩展到其他内容。性能优化仍需用户审核，尚未实施。
