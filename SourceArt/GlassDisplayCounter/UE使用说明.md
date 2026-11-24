# 玻璃柜拉门

在 `/Game/Yastars/Mesh/GlassDisplayCounter` 里将 `BP_GlassDisplayCounter` 拖到关卡。柜体和两扇玻璃门已经对位，开口在店员侧。`GlassDoorLeft` 和 `GlassDoorRight` 是各自可移动的静态网格组件。

| 门组件 | 关闭相对坐标 X、Y、Z（厘米） | 打开相对坐标 X、Y、Z（厘米） |
|---|---|---|
| `GlassDoorLeft` | `(-47, -26.05, 76.3)` | `(45.2, -26.05, 76.3)` |
| `GlassDoorRight` | `(47, -28.35, 76.3)` | `(-45.2, -28.35, 76.3)` |

一次打开一侧。让左门叠在右门前可露出左半边，让右门叠在左门后可露出右半边。

## 接入已有交互

两扇门的蓝图事件为 `SetLeftGlassDoorOpen`、`SetRightGlassDoorOpen`，布尔输入 `Open` 设为真时滑开，设为假时滑回。运动时间为 0.55 秒，使用相对坐标，所以柜子旋转后仍沿柜身滑动。

如打开的蓝图还没有这两个事件，复制 `UE/SlidingDoorBlueprintNodes.txt` 的全文，粘贴到蓝图的 **事件图表** 中，再编译并保存。也可以从门组件引出 `Move Component To`，目标相对位置用表格中的坐标，勾选缓入和缓出，时间设为 0.55 秒。

游戏中调用哪个事件由玩家交互决定。柜顶糖罐、商品盒和小立牌是 Blender 文件里的可拆分陈列摆件。UE 中的柜子可以放入项目自己的商品。
