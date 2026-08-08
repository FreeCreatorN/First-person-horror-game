# 老城区学校街道场景进度记录

记录时间：2026-08-05  
当前状态：P4 玩家视角精修已完成并通过最终验证。关卡、模型资产、截图和报告均已保存。

## 本轮已完成

- 目标关卡：`/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet`
- 原始灰盒关卡保持只读：`/Game/Yastar/Maps/Blockout/L_Chapter01_Blockout`
- 重建后的关卡包含：
  - 798 个 Actor，其中 724 个为本场景生成内容
  - 223 个单体高细节窗户模块
  - 20 种独立高细节道具资产、61 个场景实例
  - 10 种 P3 一体化模块资产、33 个场景实例
  - 5 个固定对比机位
- 新增可复用建筑模块：
  - `/Game/Yastar/OldTownSchoolStreet/Architecture/Windows/SM_OTS_Window_Residential`
  - `/Game/Yastar/OldTownSchoolStreet/Architecture/Windows/SM_OTS_Window_School`
- 已提升垃圾桶和纸箱模型：带轮、盖、把手、踏板、折叠纸板和胶带等结构，不再只是单个方块。
- 新增一体化高细节单体资产：
  - 老式自行车（轮胎、轮圈、辐条、车架、链轮、货架和车篮）
  - 墙面设备组（排水管、电表箱、接线盒、线圈和卡箍）
  - 街灯（底座、锥形灯杆、检修盖、弯臂、灯罩和镜片）
  - 路边排水篦子与单层不规则水坑
- 路灯已改为不对称分布，并保留一盏故障熄灭灯，削弱重复的模块走廊感。
- 修正 Geometry Script 圆柱连接器的 Pitch 方向；路灯弯臂、自行车车架/辐条、线缆弯头等斜向构件的两端现在准确相接。
- 北、南巷道横杆均嵌入两侧墙体 2 cm；分段悬空管改为落地连续管并增加三道实体卡箍。
- 墙挂电表、空调、排水管、水槽、垃圾桶和晾衣架支点均按真实墙面重新贴合；自行车轮胎落地并靠墙摆放。
- 电线杆移到街沿，杆身距立面约 180 cm，朝楼横担端到立面保留约 95 cm 净距。
- 大面积墙材质使用非整数双尺度采样与低频世界噪声旧化，打破同一混凝土污斑的规则周期和跨建筑同步。
- 普通商铺卷帘片已改为紧密的 22 片节奏；巷道悬浮薄板和 MainHome 侧墙重复设备已清除。
- MainHome 商铺保持四个稳定资产：
  - `/Game/MainHome/SM_MainHome_Enterable`
  - `/Game/MainHome/SM_MainHome_Shutter`
  - `/Game/MainHome/SM_MainHome_Door_Left`
  - `/Game/MainHome/SM_MainHome_Door_Right`
- 交互 Actor：`/Game/Yastar/Blockout/Buildings/BP_MainHomeInteractive`
- 商铺招牌已修正为正确朝向的“大众小卖部”。
- 门、门框、上方气窗和卷帘门的可视结构已覆盖接缝；没有可见黑缝。

## 已完成验证

- 场景生成：`OTS_BUILD_SUCCESS actors=798 generated=724 cameras=5`
- 场景截图：`OTS_CAPTURE_SUCCESS count=5`，5 张 1600×900 PNG
- 近景贴合审计：`OTS_CONTACT_AUDIT_SUCCESS count=19`，19 张 1440×810 PNG
- 独立关卡验证：`PASS`，798 Actor、724 个生成 Actor、4 个 MainHome 网格组件、2 个交互区、5 张固定截图
- Map Check：0 Error、0 Warning
- Python 契约测试：101/101 通过
- MainHomeInteractive 原生 UE 自动化测试：9/9 通过
  - 左右门独立瞄准和开关
  - 内推/外拉角度计算
  - 卷帘门开启、关闭和端点碰撞
  - 从室内瞄准顶部保留段关闭卷帘门
  - 开启后的玩家通行碰撞
  - 门板精确碰撞边界
  - 可视压条覆盖双门中心缝
- 验证报告：`Saved/CodexOutputs/OldTownSchoolStreet/ValidationReport.json`
- 交互测试报告：
  `Saved/CodexOutputs/OldTownSchoolStreet/P4FinalMainHomeTestReport/index.json`

## 当前哈希

- 原始 Blockout：
  `D15F1749800233495469ACB72E60A7C0D837319EECF57FB14BFF25FDBBD9DE09`
- 目标场景：
  `7ACBFC104C52A2680774081DF312C3F96453F8A042E2ADCABB9DDAFD60E46622`

## 当前截图

- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_Hero.png`
- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_MainHome.png`
- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_Alley.png`
- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_StreetDiagonal.png`
- `Saved/CodexOutputs/OldTownSchoolStreet/Renders/CAM_OTS_TopDown.png`
- MainHome 近景：
  `Saved/CodexOutputs/OldTownSchoolStreet/HeroFidelity/`
- 贴合审计近景：
  `Saved/CodexOutputs/OldTownSchoolStreet/ContactAudit/`

## 后续继续时的入口

1. 先读取本文件和 `SceneBuildManifest.json`，不要重做已通过内容。
2. 从现有五个固定机位继续做美术差距对比。
3. 若进入 P3，可优先：
   - 使用授权明确的 Fab 免费资产替换少数仍较简化的生活道具
   - 为远端屋顶增加水箱、天线和更细的女儿墙轮廓
   - 对 MainHome 墙面与绿色金属增加更丰富的宏观湿污和掉漆变化
4. 修改后依次重建、五机位截图、运行关卡验证和 9 项交互测试。

## 本轮主要脚本

- `Scripts/CreateOldTownSchoolStreetScene.py`
- `Scripts/CreateOldTownArchitecturalModules.py`
- `Scripts/CreateOldTownDetailedProps.py`
- `Scripts/CaptureOldTownContactAudit.py`
- `Scripts/UpgradeMainHomeHeroAsset.py`
- `Scripts/CaptureOldTownSchoolStreet.py`
- `Scripts/ValidateOldTownSchoolStreet.py`

## 2026-07-27 路灯、自行车与玩家尺度复核

- 建筑、道路、巷宽和 MainHome 保持原始厘米尺度；MainHome 仍为 Scale 1，未做全局缩放。
- 7 盏路灯从约 293–338 cm 校准为约 380–410 cm；灯头、点光源和实例比例同步更新。
- 路灯底座—锥杆、斜撑—主杆、两段灯臂、灯臂—灯壳、灯罩—灯体和镜片—灯体均改为实体穿插连接，不再依赖端面相切。
- 3 辆自行车统一为 Scale 1.04，约 191 × 55 × 102 cm，并重新贴墙落地。
- 自行车轮胎—轮圈、辐条—轮圈、链条—齿盘、座管—坐垫、把立—横把、货架支撑、脚撑和篮筐支撑均已消除真实空隙。
- 固定视图已刷新；新增路灯正反面与自行车正斜面大景深特写，共 11 张接触审计图。
- 最终验证：Map Check 0 Error / 0 Warning；Python 97/97；MainHomeInteractive 9/9。

## 2026-08-05 P3 店面、校门与材质升级

- 新增 5 个 Geometry Script 单体 Static Mesh 资产，共 17 个场景实例：
  - `SM_P3_StaticShutter`：4 个实例
  - `SM_P3_SignAssembly`：6 个实例
  - `SM_P3_AwningAssembly`：3 个实例
  - `SM_P3_SchoolGateLeaf`：2 个实例
  - `SM_P3_SchoolGatePost`：2 个实例
- 原先约 166 个卷帘条、招牌边框、雨棚支架和校门基础形状 Actor 已压缩为 17 个完整资产实例；关卡 Actor 总量由 888 降至 739。
- 静态卷帘门加入连续背板、22 片互扣叶片、嵌合导轨、顶箱、底梁、锁块和局部锈蚀；暗线只表现槽口，不再形成穿透空隙。
- 招牌、雨棚和校门的板面、边框、螺栓、支架、铰链与旧化层均采用实体交叠连接，消除了近景浮片阴影和端面黑缝。
- 南北校门叶按通道方向镜像，铰链世界高度精确对齐到 55/180 cm；门柱底座补齐对应简单碰撞。
- `M_OTS_FadedBlueWall`、`M_OTS_FadedGreenWall` 已使用 Poly Haven Painted Plaster CC0 PBR；`M_OTS_OldGreenMetal` 已使用 Poly Haven Green Metal Rust CC0 PBR。
- 场景现在验证 12 张源纹理、26 个材质、20 个 P2 道具资产/54 个实例、5 个 P3 模块资产/17 个实例和 220 个建筑窗模块实例。
- 玩家尺度复核保持真实厘米标尺：门约 230 cm、自行车约 178 cm 总长、路灯约 330 cm；未对 MainHome 或整条街做失真的全局放大。
- 重新拍摄 5 张固定整体视图和 14 张玩家距离近景，覆盖路灯正反接头、自行车节点、巷道横杆、电线杆净距、墙面材质、校门、静态卷帘门及招牌雨棚。
- 最终验证：Map Check 0 Error / 0 Warning；Python 99/99；MainHomeInteractive 9/9；受保护源地图哈希保持不变。

## 2026-08-05 P4 玩家视角精修

- 新增可步行短 T 字路口，替换原先街尾平面封墙：主街在 X=6000 cm 处接入，南北支路、转角人行道、排水槽、雨水篦子和水坑均按厘米尺度落地并保留碰撞。
- 街尾增加一组正对主路的旧百货店立面，包含一体化招牌、中文“百货店”、雨棚、静态卷帘门、侧门、气窗、墙灯和生活杂物；暖色店面光与冷色路口补光让左右转向在玩家高度可辨认。
- P3 资产库由 5 种扩展为 10 种：新增实体墙座巷道横杆，以及“小卖部、百货店、修车铺、五金店”四种独立中文招牌文字网格。
- 6 根巷道横杆全部替换为单体 Static Mesh，杆体、套环、墙座和螺栓互相嵌合，端板落入两侧墙面 2 cm；不再生成悬空 Cube 横杆。
- 北、南巷道端墙增加 3 cm 厚连续饰面层，背面贴住墙体、可见面外移 3 cm，消除原墙与加高段之间的水平材质断层且无共面闪烁。
- 墙材质由固定双纹理权重改为共享世界坐标低频噪声：同一噪声同时驱动 0.22–0.62 尺度混合和 0–0.20 旧化强度，降低跨建筑规则重复。
- 路灯上部接头、背面斜撑、自行车车架/车轮/货架、巷道墙座均通过 19 张近距离审计图再次确认实体相交。
- 最终验证：场景验证 PASS；Map Check 0 Error / 0 Warning；Python 101/101；MainHomeInteractive 9/9；受保护源地图 SHA-256 保持不变。
