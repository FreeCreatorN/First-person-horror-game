# 笔记本在 UE 中的用法

资源目录：`/Game/Yastars/Mesh/Notebook`。骨骼模型为 `SK_Notebook`，有 16 张可弯曲的纸、32 个可替换内容的纸面。

## 放进场景

- 拖入 `BP_Notebook`：默认保持闭合，动画暂停，适合摆放和拾取。
- 拖入 `BP_Notebook_Demo`：运行游戏后演示开封面、逐张翻完 16 张纸、最后反面合上。

模型没有光源或发光材质。现有笔记本 UI、按钮事件和数据资产不在这次模型的修改范围内；下面的翻页控制需要接到你自己的交互事件。

## 推荐：每次播放一个动作

独立动作在 `Yastars/Mesh/Notebook` 目录：`A_Notebook_Open`、`A_Notebook_Turn01` 到 `A_Notebook_Turn16`、`A_Notebook_CloseLast`。

在蓝图中取得笔记本的 **Skeletal Mesh 组件**，用整数 `CurrentSpread` 记录已翻过的张数，范围 0～16；再用一个 `IsTurning` 布尔值避免一次翻页没完成就重复触发。

1. 打开：`Play Animation(A_Notebook_Open, Looping=false)`，并设置 `Set Play Rate(1)`。播放结束后，`CurrentSpread=0`。
2. 下一页：当 `CurrentSpread<16`，播放 `Turn(CurrentSpread+1)`，例如 0 对应 `Turn01`。用 `Play Animation`，关闭 Looping，设置 `Set Play Rate(1)`。结束后 `CurrentSpread` 加 1。
3. 上一页：当 `CurrentSpread>0`，取 `Turn(CurrentSpread)`，依次调用 `Set Animation` → `Set Position(该动作长度, Fire Notifies=false)` → `Set Play Rate(-1)` → `Play(Looping=false)`。结束后 `CurrentSpread` 减 1。
4. 从最后一页合上：在 `CurrentSpread=16` 时播放 `A_Notebook_CloseLast`。这是从末页反面合书；从中间页直接播放会跳姿势，应先翻到末页，或倒翻回首页后反播 Open。

每个动作关闭循环后会自动停止，并保持终点姿势。可用组件的 `Is Playing` 判断动作结束，再更新 `CurrentSpread`、清除 `IsTurning`。每次正向播放前都恢复播放速率为 1。

这里的 `Play` 是 Skeletal Mesh 组件的节点；它会继续当前时间，适合上述倒放步骤。`Set Playing(true)` 属于动画实例，并非该组件同名节点。

## 另一种：用一条动画控制全部页码

`A_Notebook_FullCycle` 长 26 秒，包含完整开合和翻页。先设置组件使用此动画并保持暂停，然后用 **Timeline** 的 0～1 值，在当前页与目标页的时间之间插值，每次更新调用 `Set Position(插值结果, Fire Notifies=false)`。Timeline 完成后不再更新时间，即停在该页；上一页只需换成前一个停留时间。

所有停留时间见同目录的 `page_stops.json`，单位为秒。例如：

| 状态 | 时间 | 左侧 / 右侧 |
|---|---:|---|
| 正面闭合 | 0 | 封面 |
| CurrentSpread=0 | 1.966667 | 衬页 / 第 1 页 |
| CurrentSpread=1 | 3.633333 | 第 2 页 / 第 3 页 |
| CurrentSpread=16 | 23.633333 | 第 32 页 / 衬页 |
| 反面合上 | 26 | 封底 |

`CurrentSpread` 统计的是翻过几张纸，不是印刷页码。不要一边正常播放整条动画，一边用 Timeline 设置位置。

## 替换纸上的内容

`Materials` 中的 `MI_Notebook_Page01`～`MI_Notebook_Page32` 分别对应第 1～32 个纸面，修改其中的 **PageTexture** 即可替换该面。

运行时可在对应纸面材质槽创建动态材质实例，再调用 `Set Texture Parameter Value`，参数名填 `PageTexture`，值可用普通 Texture2D 或 Render Target。它替换整张纸面的底图；如果要保留横线，把默认横线纸先绘入 Render Target，再叠加文字和照片。内容贴在纸面上，会随翻页弯曲。

纸页使用 UV0，图片顶部对应 V=1。封面标签上的“手记”是印刷纹理。

## 碰撞

`BP_Notebook` 的独立 Box 组件提供初始正面闭合状态的碰撞，适合摆放、射线命中和拾取；它不会追随纸页或最终反面合书的位置。进入阅读/翻页状态时，将这个 Box 设为 `No Collision`，回到初始正面闭合姿势后再恢复。`BP_Notebook_Demo` 默认关闭碰撞。

单独的 `SK_Notebook` 没有 PhysicsAsset；需要摆放与拾取碰撞时使用 `BP_Notebook`。翻页使用动画控制，不采用物理模拟。
