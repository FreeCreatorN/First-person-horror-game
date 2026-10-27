# 牛皮纸信封套装

UE 目录：`/Game/Yastars/Mesh/Envelope`。

| 模型 | 用途 |
| --- | --- |
| SM_Envelope_Closed | 闭合状态，清楚的大 V 形封舌和折页 |
| SM_Envelope_Open | 打开状态，实际袋内空腔、弯折封舌和内侧胶边 |
| SM_LetterPaper | 独立白纸，可单独移动和编辑材质 |

信封主体为 DL 规格，约 22 × 11 cm；白纸约 20.5 × 9.5 cm。

打开款和白纸使用相同位置与旋转时，将白纸相对 Z 调到 **0.13 cm**，即可得到预览里的袋内装配。可在蓝图中分别控制白纸与信封。这套提供三个静态模型，未包含开合或抽纸动画。

每件模型都有独立 BaseColor、Roughness、Normal 贴图与材质，材质提供 Tint 颜色参数。包含自定义碰撞、UV0 和 UE 生成光照 UV 的设置；打开款的碰撞保留了白纸所在空腔。灯光、相机和展示地面仅用于 Blender 预览，未导出到 UE。

Blender 源文件：`EnvelopeSet.blend`。默认展示左侧闭合款与右侧打开款及袋内白纸；隐藏集合保存了原点统一的导出模型和单独折页。

参考实物：

- https://www.colourcraftdirect.com/fleck-craft-recycled-gummed-dl-110-mm-x-220-mm-envelope
- https://www.vaessen-creative.com/en/p/florence-envelopes-120g-8-27x4-33inch-kraft-100x-200112-1502

`validation_report.json` 记录三件 FBX 回读、封闭网格、UV、贴图烘焙和实际渲染；`ue_import_report.json` 记录 UE 导入和旧版删除；`final_verification.json` 记录最终包文件、碰撞和受保护资源核对。
