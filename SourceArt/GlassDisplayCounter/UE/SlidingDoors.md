# 玻璃门蓝图用法

在内容浏览器打开 `/Game/Yastars/Mesh/GlassDisplayCounter`，把 `BP_GlassDisplayCounter` 拖进关卡。柜体和两扇门在同一个 Actor 内，`GlassDoorLeft`、`GlassDoorRight` 是两块沿各自轨道移动的组件。

在交互蓝图中取得柜台的 Actor 引用，调用 `SetLeftGlassDoorOpen` 或 `SetRightGlassDoorOpen`，传入 `Open=true` 开门，`Open=false` 关门。两扇门各用 0.55 秒平滑移动 92.2 厘米。想敞开一边时控制该侧的一扇门即可。

若需要把节点加到另一份蓝图，打开 `SlidingDoorBlueprintNodes.txt`，复制全文，到柜台蓝图的 **Event Graph（事件图表）** 空白处粘贴，再编译保存。节点引用的组件名应对应 `GlassDoorLeft`、`GlassDoorRight`。

| 门组件 | 关闭位置 (X, Y, Z)，厘米 | 打开位置 (X, Y, Z)，厘米 |
| --- | --- | --- |
| `GlassDoorLeft` | `(-47, -26.05, 76.3)` | `(45.2, -26.05, 76.3)` |
| `GlassDoorRight` | `(47, -28.35, 76.3)` | `(-45.2, -28.35, 76.3)` |

自定义拉动节奏时，可在 Timeline 中以 0–1 作为 `Lerp (Vector)` 的 Alpha，把结果接到对应组件的 `Set Relative Location`。坐标以上表为准，沿柜台自身 X 轴移动。
