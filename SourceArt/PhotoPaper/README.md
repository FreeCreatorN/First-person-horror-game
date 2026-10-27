# 白边相纸

UE 资源：`/Game/Yastars/Mesh/PhotoPaper/SM_PhotoPaper`。

尺寸约 **8.8 × 10.8 cm**，纸张实际厚度 **0.35 mm**，右下角轻微翘起。照片区域 **7.8 × 7.8 cm**；左右与顶部白边约 5 mm，底部白边约 25 mm。圆角、细小倒边、正反面与厚度均为封闭网格，含一个简单凸碰撞体。

材质槽：

| 槽 | 用途 | UE 材质 |
| --- | --- | --- |
| 0 | 白边与侧边 | M_PhotoPaper_Frame |
| 1 | 照片正面 | MI_PhotoPaper_Image |
| 2 | 相纸背面 | M_PhotoPaper_Back |

中间的灰色为未指定照片时的占位图。打开 `Materials/MI_PhotoPaper_Image`，勾选纹理参数 **PhotoTexture** 并换成照片纹理即可；照片区域 UV 覆盖完整 0–1，方形图片正好填满照片窗口。材质默认无自发光。

后续每张照片独立显示内容时，对 **槽 1** 创建动态材质实例，用 `Set Texture Parameter Value` 设置 `PhotoTexture` 为拍照 Render Target 或照片贴图。白边和背面保留各自材质。`Tint` 和 `Roughness` 可以调整图像色调、表面粗糙度。

Blender 源文件：`PhotoPaper.blend`。正面朝 +Z、照片顶部朝 +Y；UE 导入会执行标准坐标转换。`PhotoPaper_Preview.png`、`PhotoPaper_Back.png`、`PhotoPaper_Edge.png` 是实际模型渲染。摄影棚灯光、地面和相机仅用于预览。

导入及几何、照片 UV、碰撞、材质参数与资源校验记录见 `model_report.json`、`validation_report.json`、`ue_import_report.json`、`ue_import_completion.json`、`final_verification.json`。
