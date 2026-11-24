import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
R=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
labels=json.loads((ROOT/'Textures/stock_labels_manifest.json').read_text(encoding='utf-8'))
c=bpy.data.collections[R['stock_collection']]
image=bpy.data.images.load(str(ROOT/'Textures'/labels['atlas']),check_existing=True);image.pack()
mat=bpy.data.materials.new('M_OptionalStock_PrintedPaper');mat.use_nodes=True
p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Roughness'].default_value=.78
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;mat.node_tree.links.new(tex.outputs['Color'],p.inputs['Base Color'])
def uvlabel(o,entry):
    uv=o.data.uv_layers.active or o.data.uv_layers.new(name='UVMap')
    xmin=min(v.co.x for v in o.data.vertices);xmax=max(v.co.x for v in o.data.vertices)
    zmin=min(v.co.z for v in o.data.vertices);zmax=max(v.co.z for v in o.data.vertices)
    u0,v0,u1,v1=labels['labels'][entry]['uv_blender']
    for poly in o.data.polygons:
        for li in poly.loop_indices:
            v=o.data.vertices[o.data.loops[li].vertex_index].co
            uv.data[li].uv=(u0+(v.x-xmin)/(xmax-xmin)*(u1-u0),v0+(v.z-zmin)/(zmax-zmin)*(v1-v0))
    o.data.materials.clear();o.data.materials.append(mat)
cartons=sorted([o for o in c.objects if o.type=='MESH' and o.name.startswith('Carton label')],key=lambda o:(round(o.data.vertices[0].co.y,2),o.data.vertices[0].co.x))
for i,o in enumerate(cartons):uvlabel(o,(i//2+i//10)%4)
jars=sorted([o for o in c.objects if o.type=='MESH' and o.name.startswith('Jar paper label')],key=lambda o:o.data.vertices[0].co.x)
for i,o in enumerate(jars):uvlabel(o,4+i%2)
s=bpy.context.scene;s.frame_set(1)
s.render.engine='BLENDER_EEVEE';s.eevee.use_raytracing=True
for w in bpy.context.window_manager.windows:
    for a in w.screen.areas:
        if a.type=='VIEW_3D':
            sp=a.spaces.active;sp.shading.type='RENDERED';sp.overlay.show_overlays=False
            sp.region_3d.view_rotation=s.camera.rotation_euler.to_quaternion()
notes=bpy.data.texts.get('ShopCounterPlan · usage') or bpy.data.texts.new('ShopCounterPlan · usage')
notes.clear();notes.write('小卖铺柜台规划版\n196 x 62 x 109 cm / 2640 triangles / 9 primary parts\n'+
    '四扇门沿各自本地 X 滑动。帧34/94显示玻璃门打开，帧154/214显示木门打开。帧1全部关闭。\n'+
    '可选商品与预览灯光均位于独立集合，UE 导出只包含九个主要部件。\n'+
    'UE BP_ShopCounterPlan 已独立装配门，交互事件与按键需接入项目逻辑。\n')
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'ShopCounterPlan.blend'))
print('FINISHES_SAVED',len(cartons),len(jars))
