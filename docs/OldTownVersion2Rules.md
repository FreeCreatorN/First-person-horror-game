# 老城区版本分工

2026-10-17 灯光适配特例已完成：用户明确指定原版、仅允许改助手制作的灯具，并追加要求剩余装饰灯也可用。现在共33套可调用灯（24酒店+9街灯），原有16身份/参数/初始状态不变，新增17真实光源、17控制器和17灯罩槽2覆盖；新增17默认关，总13亮20关。Main、BP_LightSwitch、BPI_Interact、V2、既有共享资源及上一轮19灯光资产均字节不变。最新证据为Saved/CodexOutputs/OldTownFunctionalLighting_20261017/{FinalReview,CurrentLighting}.json，说明Docs/OldTownCallableLighting.md；旧10-16报告保留为历史，不覆盖。此灯光授权不得扩大到其他原版内容。以下规则适用于一般后续优化。

用户使用原版L_OldTownSchoolStreet。助手今后只在 /Game/CodexGenerated/OldTownVersion2/Maps/老城区第二版 做优化。

原版81台助手截图摄像机已清理。除顶部明确授权的助手灯具适配外，不再写原版；不改Main、不恢复用户灯光、环境或PickupBP的旧版本。此次临时截图相机已清零，没有保存进原版。

地图副本仍共享部分资产。助手编辑模型、材质、蓝图、RT前，必须先建立OldTownVersion2目录下的专用副本并只更换第二版引用，旧共享资产对助手只读。项目级渲染设置不能为第二版随意修改。

性能相关实例化、流送、阴影、Nanite、纹理、角色预览捕获频率等改动，须取得用户对具体审核方案的同意；当前仅有待审方案，未实施。一般“继续优化”不替代这项审核。

最新证据见Saved/CodexOutputs/EnterableStreet_20261002/CurrentEvidence.json与OldTownVersion2_20261016目录。
