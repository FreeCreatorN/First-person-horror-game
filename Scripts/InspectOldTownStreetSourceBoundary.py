import bpy,bmesh,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(root/'SourceArt/OldTownRealism_20261012/Street/BeforeSolids/OldTownRealStreet.blend.bak'))
name='SM_R_Street_Mod_CardboardBox_0fbbf3416905'
manifest=json.loads((root/'SourceArt/OldTownRealism_20261012/Street/BeforeSolids/ModelDataManifest.json.bak').read_text(encoding='utf-8'))
variant=next(v for v in manifest['variants'] if v['mesh_name']==name)
obj=bpy.data.objects[name]
bm=bmesh.new();bm.from_mesh(obj.data)
for v in bm.verts:
    for i in range(3):v.co[i]*=100*variant['component_scale'][i]
bmesh.ops.dissolve_degenerate(bm,dist=1e-4,edges=list(bm.edges))
bm.verts.ensure_lookup_table();bm.edges.ensure_lookup_table();bm.faces.ensure_lookup_table()
edges=[e for e in bm.edges if not e.is_manifold]
rows=[dict(edge=e.index,vertices=[dict(index=v.index,co=list(v.co),valence=len(v.link_edges),boundary_edges=[a.index for a in v.link_edges if a.is_boundary]) for v in e.verts],faces=[dict(index=f.index,material=f.material_index,verts=[v.index for v in f.verts]) for f in e.link_faces]) for e in edges]
print(json.dumps(rows,indent=2),flush=True)
print('FILL',len(bmesh.ops.holes_fill(bm,edges=edges,sides=0).get('faces',[])),flush=True)
print('REMAIN',len([e for e in bm.edges if not e.is_manifold]),flush=True)
unseen=set(bm.faces);groups=[]
while unseen:
    seed=unseen.pop();group={seed};stack=[seed]
    while stack:
        for edge in stack.pop().edges:
            if edge.is_manifold:
                for face in edge.link_faces:
                    if face in unseen:unseen.remove(face);group.add(face);stack.append(face)
    groups.append(group)
print('GROUPS',[(len(g), sorted({v.index for f in g for v in f.verts})[:10]) for g in groups],flush=True)
for i,group in enumerate(groups):
    vs=sorted({v for f in group for v in f.verts},key=lambda v:v.index);mapping={v:i for i,v in enumerate(vs)}
    mesh=bpy.data.meshes.new('DebugPart'+str(i));mesh.from_pydata([list(v.co) for v in vs],[],[[mapping[v] for v in f.verts] for f in group]);mesh.update()
    check=bmesh.new();check.from_mesh(mesh)
    print('GROUPDETAIL',i,len(group),sum(not e.is_manifold for e in check.edges),check.calc_volume(signed=True),[sum(e in f.edges for f in group) for e in edges],flush=True)
