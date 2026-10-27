> 2026-10-21 双端修正已完成：用户明确要求两头都挡，负Y端已补齐。当前状态与新截图见 [双端修正版](D:/UE/Project/HorrorGame/Docs/HotelFrontBoundaryBothEndsResult.md)。下文为此前仅正Y端的历史记录。

# 第一版酒店前方边界遮挡

已在用户最新保存的第一版 `/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet` 上完成。输入SHA：`208f0ab3164301bc57d38793e4beffee9153036e82d5c9d30b122f870092b4ee`，没有恢复旧地图。

针对截图中酒店前方正Y端空地，新增旧院墙、实心锈铁院门和两侧回墙，遮住地面终点及转角露空。院墙含露砖、柱、压顶，铁门有波纹钢板、搭接缝、拉手和合页，作为固定场景边界。墙脚落地并在原建筑角补实接头。

只新增四个自有Actor、三个SM_Hotel模型，资源在 `/Game/CodexGenerated/Hotel/FrontBoundary_20261021/Meshes/`。原有7989个Actor完整Native、变换、父子关系、材质、碰撞及灯光状态在保存前和独立重开均一致；Main、第二版、用户制作/导入资产和所有旧包逐SHA保持。没有移动或删除原有建筑、门窗、相机、导航范围；没有添加永久灯光或更改项目性能设置。

遮挡射线105条通过，包括院门中缝；酒店后侧绕行和前方接近路线共215个胶囊/支撑采样通过。四张新鲜引擎截图已目视检查；临时检查照明与相机清零，截图未保存地图。已保存第一版并备份输入原图。

当前地图SHA：`207475fc8f25798a3243938a619d2b73aa2f4ebf788e6c34a46ac5fb912669a9`。
备份：`D:\UE\Project\HorrorGame\Saved\CodexBackups\HotelFrontBoundaryBefore_20261021T084657Z\L_OldTownSchoolStreet.umap`。
完整验收：`Saved/CodexOutputs/HotelFrontBoundary_20261021/FinalReview.json`。

- [巷口人眼视角](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelFrontBoundary_20261021/Captures/Renders/BOUNDARY_LaneEye.png)
- [整体斜视](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelFrontBoundary_20261021/Captures/Renders/BOUNDARY_Oblique.png)
- [实心旧院门](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelFrontBoundary_20261021/Captures/Renders/BOUNDARY_Gate.png)
- [俯视位置](D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelFrontBoundary_20261021/Captures/Renders/BOUNDARY_Top.png)
