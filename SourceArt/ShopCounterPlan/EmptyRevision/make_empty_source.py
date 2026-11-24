"""Build a single-scene, merchandise-free source through the live Blender MCP."""
import bpy, json, hashlib, copy
from pathlib import Path
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[1]
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
old=bpy.context.scene
assert old.name==R['source_scene'],(old.name,R['source_scene'])
assert (ROOT/'EmptyRevision/source_backup_path.txt').is_file()
old.frame_set(1);bpy.context.view_layer.update()
deps=bpy.context.evaluated_depsgraph_get()
scene=bpy.data.scenes.new('ShopCounterPlan_Empty')
scene.unit_settings.system='METRIC'
model=bpy.data.collections.new('柜台组件 · 规划书八类');scene.collection.children.link(model)
names=[('GlassTop','01 玻璃顶板'),('GlassSurround','02 玻璃围挡'),('MetalFrame','03 金属框架'),
       ('DisplayShelf','04 展示层板'),('Body','05 木质柜体（储物）'),
       ('WoodSlidingDoors','06 推拉柜门'),('GlassSlidingDoors','07 推拉玻璃门'),('InteriorShelf','08 内部层板')]
categories={}
for key,name in names:
    c=bpy.data.collections.new(name);model.children.link(c);categories[key]=c
groupobjects={}
for key in ('WoodSlidingDoors','GlassSlidingDoors'):
    group=bpy.data.objects.new(key,None);categories[key].objects.link(group)
    group.empty_display_type='PLAIN_AXES';group.empty_display_size=.035;groupobjects[key]=group
scratch=bpy.data.collections.new('Empty revision · temporary copies');old.collection.children.link(scratch)
parts={};collisions=copy.deepcopy(R['collision_boxes'])
glassboxes=collisions.pop('FixedGlass')
collisions['GlassTop']=[glassboxes[-1]]
collisions['GlassSurround']=glassboxes[:-1]
order=['Body','MetalFrame','GlassTop','GlassSurround','DisplayShelf','InteriorShelf','WoodDoorLeft','WoodDoorRight','GlassDoorLeft','GlassDoorRight']
for key in order:
    previous=R['parts']['FixedGlass' if key in ('GlassTop','GlassSurround') else key]
    original=[o for o in bpy.data.collections[previous['collection']].objects if o.type=='MESH']
    if key=='GlassTop':original=[o for o in original if o.name.startswith('Flush glass countertop')]
    elif key=='GlassSurround':original=[o for o in original if not o.name.startswith('Flush glass countertop')]
    assert original,key
    copies=[]
    for src in original:
        me=bpy.data.meshes.new_from_object(src.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
        obj=bpy.data.objects.new('Empty part copy',me);scratch.objects.link(obj);obj.matrix_world=src.matrix_world.copy();copies.append(obj)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in copies:obj.select_set(True)
    bpy.context.view_layer.objects.active=copies[0]
    bpy.ops.object.join();obj=bpy.context.object
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    obj.name='SM_ShopCounterPlan_'+key;obj.data.name=obj.name
    if key.startswith(('WoodDoor','GlassDoor')):
        kind='WoodSlidingDoors' if key.startswith('Wood') else 'GlassSlidingDoors'
        coll=bpy.data.collections.new(('左门' if key.endswith('Left') else '右门')+' · '+key)
        categories[kind].children.link(coll)
        spec=next(d for d in R['doors'].values() if d['part']==key)
        pivot=Vector(spec['pivot_m'])
        for v in obj.data.vertices:v.co-=pivot
        obj.location=pivot;obj.parent=groupobjects[kind];obj.matrix_parent_inverse=Matrix.Identity(4)
        source_controller=bpy.data.objects[spec['parent']]
        if source_controller.animation_data and source_controller.animation_data.action:
            action=source_controller.animation_data.action.copy();obj.animation_data_create();obj.animation_data.action=action
            if len(action.slots):obj.animation_data.action_slot=action.slots[0]
        spec['parent']=obj.name
        obj['SlideTravelCm']=spec['travel_cm']
    else:
        coll=categories[key];pivot=Vector((0,0,0))
    coll.objects.link(obj);scratch.objects.unlink(obj)
    obj['PlanningCategory']=next(name for k,name in names if k==(kind if key.startswith(('WoodDoor','GlassDoor')) else key))
    parts[key]={'collection':coll.name,'mesh':'SM_ShopCounterPlan_'+key,'pivot_m':list(pivot),'object':obj.name}
    obj.data.update()

preview=bpy.data.collections.new('_PreviewOnly · 非模型组件');scene.collection.children.link(preview)
camera_map={}
for original in bpy.data.collections[R['preview_collection']].objects:
    duplicate=original.copy();duplicate.name=original.name+' · EmptyPreview';preview.objects.link(duplicate)
    if duplicate.type=='CAMERA':camera_map[original.name]=duplicate
scene.camera=camera_map[R['front_camera']]
scene.world=old.world.copy() if old.world else None
scene.render.engine='CYCLES';scene.cycles.samples=28;scene.cycles.use_denoising=True;scene.cycles.transmission_bounces=10
scene.render.resolution_x=1500;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
scene.eevee.use_raytracing=True
scene.frame_start=1;scene.frame_end=260;scene.render.fps=30;scene.frame_set(1)
for label,frame in [('全部关闭',1),('左玻璃门开',34),('右玻璃门开',94),('左木门开',154),('右木门开',214),('全部关闭',260)]:
    scene.timeline_markers.new(label,frame=frame)
report=copy.deepcopy(R)
report.update(parts=parts,collision_boxes=collisions,source_scene=scene.name,stock_collection='',optional_stock_triangles=0,
    preview_collection=preview.name,front_camera=scene.camera.name,rear_camera=camera_map[R['rear_camera']].name,
    planning_categories=[{'key':k,'label':label,'collection':categories[k].name} for k,label in names],empty_counter=True)
with bpy.context.temp_override(scene=scene,view_layer=scene.view_layers[0]):
    scene.view_layers[0].update()
    report['triangles_by_part']={}
    for key,row in parts.items():
        obj=bpy.data.objects[row['object']];obj.data.calc_loop_triangles();report['triangles_by_part'][key]=len(obj.data.loop_triangles)
report['total_triangles']=sum(report['triangles_by_part'].values())
assert report['total_triangles']==2640 and len(report['parts'])==10
assert report['triangles_by_part']['GlassTop']==12 and report['triangles_by_part']['GlassSurround']==36
assert len(model.children)==8
for window in bpy.context.window_manager.windows:
    window.scene=scene
    for area in window.screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active;space.shading.type='MATERIAL';space.overlay.show_overlays=False
            space.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion();space.region_3d.view_location=Vector((0,0,.55))
            space.region_3d.view_distance=2.8;space.region_3d.view_perspective='ORTHO'
# Only this clean scene and its actual dependencies enter the delivered file.
# Original scenes, goods and user session data remain in memory and in backup.
bpy.data.libraries.write(str(ROOT/'ShopCounterPlan.blend'),{scene},fake_user=True,compress=True)
(ROOT/'model_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
receipt={'success':True,'parts':list(parts),'categories':[label for _,label in names],
    'triangles':report['total_triangles'],'stock_objects':0,'source_sha256':hashlib.sha256((ROOT/'ShopCounterPlan.blend').read_bytes()).hexdigest()}
(ROOT/'EmptyRevision/source_change_receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')
print('EMPTY_COUNTER_SOURCE_WRITTEN',json.dumps(receipt,ensure_ascii=False))
