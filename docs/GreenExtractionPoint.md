# 《代行者》绿色撤离点

参考图版本沿用 `L_GreenPortal` 和原有蓝图。使用 UE 5.7 编辑器控制台修改资产，并以实际运行渲染图对照参考图。

## 打开与复用

- 预览关卡：`/Game/Yastar/Maps/L_GreenPortal`
- 完整组合：`/Game/Yastar/Blueprints/BP_GreenExtractionPoint`
- 在其他关卡拖入 BP 即可使用。预览用人物、补光和曝光体积只属于独立预览关卡，不包含在 BP 中。

## 资产与组件

| 组件 | 资产 | 功能 |
| --- | --- | --- |
| EnergyBoundary | M_GreenPortal_Beam / MI_GreenExtraction_Body | 高透的绿色侧壁、靠近地面渐亮的左右亮边、向上逐段淡出的开放顶部 |
| GroundRings | M_GreenPortal_Ring / MI_GreenExtraction_Ring | 亮主环、两圈淡外描边和局部流光 |
| EnergyThreads | M_GreenExtraction_Filaments / MI_GreenExtraction_Filaments | 细长竖向能量丝，以及在侧壁中上升的微光点 |
| AnomalyParticles | NS_GreenExtractionParticles | 复制并调整项目现有 NS_DustMote 的轻量 Niagara emitter；持续内部漂浮和微弱 Curl |
| Niagara Sprite材质 | M_GreenExtraction_Particle / MI_GreenExtraction_Particle | ParticleColor、软圆点和可调强度 |
| LocalizedGreenLight | BP 内部 PointLight | 5.5 lm 绿色光，作用半径 178 cm |
| Preview floor | M_GreenExtraction_PreviewFloor | 深色湿地，含随观察角度变化的绿色碎反射 |

上述材质与 Niagara 均在 `/Game/Yastar/Materials`。保留了先前版本的旧材质文件，但当前 BP 不引用旧球体材质或旧内部平面材质。原先67个分散的特效Actor已在此预览关卡中替换为一个BP。

## 比例与空间约束

- 场景原来没有人物；使用项目已有 `SKM_Manny_Simple`，按实测 bounds 缩放到180cm作为参考。
- 圆柱高度 180 cm，与关卡内人物模型等高。顶部能量向上淡出。
- 圆柱半径 62 cm，直径 124 cm，比参考人物当前姿势的最宽处约多 4.3 cm。主体和光丝的 XY 轮廓保持固定。
- 上下盖使用法线遮罩。顶部淡出起点随圆周位置轻微变化，幅度上限为 2.2 cm。
- Niagara 发射外半径约 47.1 cm，向内厚度约 25.6 cm。初始高度以 82.8 cm 为中心，上下各 70 cm。
- 初速度 XY 约 ±0.46 cm/s，Z 约 −1.04 到 1.69 cm/s，包含 1.30 倍速度系数。Curl 强度 0.12，频率 0.035。

## 主要可调参数

在相应 MI 中启用参数覆盖后修改：

| 参数 | 当前值 | 作用 |
| --- | --- | --- |
| Height | 180 cm | 材质高度归一与上端淡出范围 |
| BodyOpacity | 0.019 | 透明柱壁的基础绿色光量 |
| BodyEmission | 1.0 | 主体发光 |
| FlowSpeed | 1.0 | 局部能量运动速度 |
| MoteSpeed | 1.30 | 柱壁微光点的上升速度系数 |
| TopRipple | 2.2 cm | 上部消散范围沿圆周的变化 |
| RingEmission | 9.1 | 底环亮度 |
| FilamentIntensity | 1.70 | 光丝和侧壁微光点亮度 |
| ParticleIntensity | 2.25 | Niagara 粒子材质亮度 |
| Tint | 白色乘数 | 四个材质各自的颜色乘数 |

Niagara 的 Spawn Rate 为 30/s，粒子寿命 5–8 秒，Sprite 尺寸 0.32–1.35 cm。内部粒子的初速度系数在 `Add Velocity` 模块的 `Linear Velocity Scale` 中调整。

改变整体高度时，要同时调整 BP 的 EnergyBoundary、EnergyThreads 的 Z缩放和中心Z位置，以及两个MI的 Height；粒子的初始高度与运动范围也要对应缩放。改变半径时同步调整圆柱XY缩放、地面环XY缩放和Niagara ShapeLocation半径。没有提供一键联动的Blueprint变量，避免将独立组件参数误解为全局控制器。

## 实际检查

侧壁亮边、底环和地面反射会根据画面中覆盖的像素范围平滑细线。相机拉远时，材质逐步减弱过细的光丝和微光，保留柱壁和底环的主要轮廓。

用 `--fit-check` 在 Simulate In Editor 中取样。`Saved/GreenPortalCharacterFit_UE_A.png` 是近景，`UE_B` 到 `UE_D` 是约 29 米处略微横移相机时的取样，`UE_E` 是把预览人物移到圆柱中心后拍的俯视图。`Saved/GreenPortalCharacterFitCapture.json` 记录相机位置、游戏时间和 Niagara 状态。

## 制作源与复查

本版修改入口为 `Scripts/MatchExtractionReference.py`，地面材质定义在 `Scripts/ExtractionReferenceFloor.py`，取样脚本为 `Scripts/CaptureExtractionReference.py`。早期组装脚本保留了旧版参数。

不要在用户正在另一个编辑器中打开同一项目时启动第二个写入进程；可在当前编辑器控制台用 `py` 执行所需脚本。
