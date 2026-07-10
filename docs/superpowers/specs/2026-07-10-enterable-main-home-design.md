# 可进入式“大众小卖部”模型设计

## 目标

在 UE5.7 当前编辑器关卡中生成一个参考 `MainHome.png` 的低模旧城区小卖部。建筑必须真正可进入，最终保存为单个 Static Mesh Asset，并在当前关卡中只保留一个实例 Actor。

## 固定边界与朝向

- 整体尺寸严格为 500 × 800 × 400 cm。
- 世界局部边界：X = -250～250，Y = -400～400，Z = 1～401 cm。
- 正面朝向 -Y；沿街方向为 X；进深为 Y；高度为 Z。
- Actor 生成在世界原点，模型底部位于 Z = 1 cm。
- 输出资产：`/Game/MainHome/SM_MainHome_Enterable`。
- 实例标签与生成器标签均使用独立的 `MainHome_Enterable` 命名，不覆盖现有 `/Game/OldShop_500x800x400` 资产。

## 建筑结构

模型不用实心主体，也不用布尔切门洞。结构由互相独立但合入同一 Dynamic Mesh 的长方体组成：

- 10 cm 厚地板，覆盖完整 500 × 800 cm 平面。
- 左右各 20 cm 厚侧墙，室内净宽 460 cm。
- 20 cm 厚后墙，室内最深位置位于 Y = 380 cm。
- 16 cm 厚屋顶板，屋内净高 340 cm。
- 正面三根承重立柱：左右边柱各 32 cm 宽，中央柱 44 cm 宽。
- 正面过梁位于门洞上方。
- 两个入口完全留空，每个净宽 196 cm、净高 280 cm；入口后方为左右连通的一间空铺。
- 屋顶四边设置 34 cm 高的女儿墙/压边，最高点严格为 Z = 401 cm。

结构外表面与装饰的前后层级固定为：正面结构最外侧 Y = -396 cm；饰面层最外侧逐层向 -Y 延伸，最终不越过 Y = -400 cm。相邻层只接触或明确错开，不放置两张共面的可见表面。

## 参考图外观

- 正面保留左右双开口和中央宽柱的构图。
- 门洞上方设置旧米灰招牌底板、四边框条和上檐口。
- 招牌使用无外部字体依赖的低模凸起笔画表现“**大众小卖部**”；文字作为同一 Dynamic Mesh 中的装饰几何，不参与碰撞。
- 正面边柱、中柱和墙脚设置少量压条。
- 墙脚、柱脚、招牌边缘添加少量灰褐污渍块；污渍不使用纯黑，也不与墙面共面。
- 内墙颜色比外墙更暗，地面为旧灰褐色，文字为褪色暗红。
- 不生成复杂曲面、外部贴图、外部模型或 Blender 依赖。

## Mesh 与材质

脚本使用 `unreal.DynamicMesh` 和 `unreal.GeometryScript_Primitives.append_box` 构建所有结构及装饰。首次追加几何前必须调用 `unreal.GeometryScript_Materials.enable_material_ids`，确保材质 ID 0 也能与其余材质槽一起正确保留。

材质槽固定且连续：

0. `M_MainHome_Wall`：旧米灰外墙
1. `M_MainHome_Interior`：较暗的室内墙
2. `M_MainHome_Floor`：旧灰褐地面
3. `M_MainHome_Sign`：褪色米黄招牌
4. `M_MainHome_Trim`：深灰褐边框
5. `M_MainHome_Letters`：褪色暗红文字
6. `M_MainHome_Stain`：深灰褐污渍

材质只使用基础颜色与粗糙度，不依赖贴图。重复运行时更新已有材质与 Static Mesh Asset；不通过强制删除仍被关卡 Actor 引用的资产来覆盖。

## 碰撞与可进入性

- 视觉 Dynamic Mesh 包含结构、招牌、文字、压条和污渍。
- 单独构建碰撞 Dynamic Mesh，只包含地板、屋顶、墙体、立柱、过梁和女儿墙。
- 使用 Geometry Script 的 `ALIGNED_BOXES` 从每个独立结构盒生成 Simple Collision。
- 招牌、文字、框条和污渍不生成碰撞，避免玩家被薄装饰绊住。
- 不使用循环 `append_box_with_collision`，因为 UE5.7 中该调用会在每次执行时清空此前的简单碰撞。
- 两个入口对应的通行体积内不得出现结构盒或简单碰撞盒。

## 重复运行与关卡实例

- 若 `/Game/MainHome/SM_MainHome_Enterable` 不存在，创建新 Static Mesh Asset。
- 若资产已存在，使用 Geometry Script 的复制到 Static Mesh API 原位更新 LOD0，保留资产引用稳定。
- 查找带 `MainHome_Enterable` 标签的旧实例：保留或重建一个，删除多余实例。
- 最终当前关卡只留下一个 `SM_MainHome_Enterable_Instance` Actor，并选中该 Actor。
- 保存材质资产、Static Mesh Asset 和当前关卡中的实例修改。

## 验证标准

纯 Python 测试必须验证：

- 总边界精确等于 X[-250,250]、Y[-400,400]、Z[1,401]。
- 两个入口分别具有 196 × 280 cm 的最小净空。
- 从 Y = -400 到室内的入口通道不与任何结构盒相交。
- 室内多个采样点不在任何实体结构盒内。
- 碰撞盒集合不包含任何装饰件，也不横跨入口。
- 材质 ID 连续为 0～6，文字、招牌和污渍均使用正确材质。
- 所有可见贴片厚度至少为 1 cm，并与依附表面具有明确前后层级。
- 重复生成逻辑使用独立资产路径、标签和单实例策略。

UE 编辑器内最终验收：运行脚本后资产浏览器出现目标 Static Mesh，当前关卡只有一个生成实例，第一人称角色可从任一门洞进入并在室内左右连通移动。
