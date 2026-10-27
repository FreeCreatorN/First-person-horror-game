import bpy, json
from pathlib import Path
from collections import Counter
from mathutils import Vector
out=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(out.parent/'Camera.blend'))
scene=bpy.context.scene
report={'version':bpy.app.version_string,'collections':{},'objects':{},'materials':{}}
for c in bpy.data.collections:
    report['collections'][c.name]={'hide_render':c.hide_render,'hide_viewport':c.hide_viewport,'objects':len(c.objects)}
for o in bpy.data.objects:
    if o.type=='MESH':
        report['objects'][o.name]={'collections':[c.name for c in o.users_collection],'hide_render':o.hide_render,'location':list(o.location),'scale':list(o.scale),'polygons':len(o.data.polygons),'materials':[m.name if m else None for m in o.data.materials]}
        if o.name in ('SM_Camera','VIEW_Camera') or any(x in o.name for x in ('Top shoulder plate','Film memo insert','Flush front designation')):
            report['objects'][o.name]['largest_polys']=[{'area':p.area,'center':list(o.matrix_world @ p.center),'normal':list(o.matrix_world.to_3x3() @ p.normal),'mat':p.material_index,'smooth':p.use_smooth} for p in sorted(o.data.polygons,key=lambda p:p.area,reverse=True)[:12]]
            report['objects'][o.name]['normal_counts']=Counter(tuple(round(a,3) for a in p.normal) for p in o.data.polygons).most_common(12)
for m in bpy.data.materials:
    if not m.use_nodes:continue
    report['materials'][m.name]={'nodes':[],'links':[]}
    for n in m.node_tree.nodes:
        nd={'name':n.name,'type':n.type}
        if n.type=='BSDF_PRINCIPLED':
            nd['inputs']=[]
            for p in n.inputs:
                val=getattr(p,'default_value',None)
                if hasattr(val,'__iter__'):val=list(val)
                nd['inputs'].append({'name':p.name,'identifier':p.identifier,'value':val,'linked':p.is_linked})
        report['materials'][m.name]['nodes'].append(nd)
    for l in m.node_tree.links:report['materials'][m.name]['links'].append((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier))
(out/'inspect_report.json').write_text(json.dumps(report,indent=2))
print('CAMERA_DIAGNOSTIC_WRITTEN',str(out/'inspect_report.json'))
