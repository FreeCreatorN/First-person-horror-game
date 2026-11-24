"""Optional MCP step: assign the generated atlas to existing stock-label meshes.

Does not save the .blend or alter geometry. Cabinet materials remain untouched.
"""
import bpy, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
report=json.loads((ROOT/'model_report.json').read_text(encoding='utf-8'))
labels=json.loads((ROOT/'Textures/stock_labels_manifest.json').read_text(encoding='utf-8'))
stock=bpy.data.collections[report['stock_collection']]
assert stock in list(bpy.context.scene.collection.children), 'Choose the final source scene first.'
image=bpy.data.images.load(str(ROOT/'Textures'/labels['atlas']),check_existing=True)
image.colorspace_settings.name='sRGB'
image.pack()
material=bpy.data.materials.get('M_StockLabels_OriginalPrint') or bpy.data.materials.new('M_StockLabels_OriginalPrint')
material.use_nodes=True
tree=material.node_tree
shader=tree.nodes.get('Principled BSDF')
shader.inputs['Roughness'].default_value=.78
node=tree.nodes.get('Original stock label atlas') or tree.nodes.new('ShaderNodeTexImage')
node.name='Original stock label atlas';node.image=image
tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])

def assign(obj,entry):
    # Label front lies in X/Z. Existing 0.2mm thickness remains unchanged.
    me=obj.data
    mnx=min(v.co.x for v in me.vertices);mxx=max(v.co.x for v in me.vertices)
    mnz=min(v.co.z for v in me.vertices);mxz=max(v.co.z for v in me.vertices)
    u0,v0,u1,v1=entry['uv_blender']
    uv=me.uv_layers.active or me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for idx in poly.loop_indices:
            co=me.vertices[me.loops[idx].vertex_index].co
            uv.data[idx].uv=(u0+(u1-u0)*(co.x-mnx)/(mxx-mnx),v0+(v1-v0)*(co.z-mnz)/(mxz-mnz))
    me.materials.clear();me.materials.append(material)
    me.update()

cartons=sorted([o for o in stock.objects if o.type=='MESH' and o.name.startswith('Carton label')],key=lambda o:o.name)
jars=sorted([o for o in stock.objects if o.type=='MESH' and o.name.startswith('Jar paper label')],key=lambda o:o.name)
for i,obj in enumerate(cartons):assign(obj,labels['labels'][i%4])
for i,obj in enumerate(jars):assign(obj,labels['labels'][4+i%2])
print(json.dumps({'stock_labels_assigned':len(cartons),'jar_labels_assigned':len(jars),'packed_texture':image.name}))
