"""Independently reload four exported FBXs and render geometry previews only."""
import bpy, bmesh, hashlib, json, math
from pathlib import Path
from mathutils import Vector

OUT=Path(__file__).resolve().parent
manifest=json.loads((OUT/'ModelDataManifest.json').read_text(encoding='utf-8'))
checks=[]

def clean():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def bounds(points):
    return [[min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)]]

for row in manifest['variants']:
    clean()
    bpy.ops.import_scene.fbx(filepath=row['fbx_file'])
    objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert len(objs)==1,(row['key'],len(objs))
    obj=objs[0]
    points=[(obj.matrix_world@v.co)*100 for v in obj.data.vertices]
    actual=bounds(points)
    bound_pass=all(abs(a-b)<.003 for aa,bb in zip(actual,row['local_bounds_cm']) for a,b in zip(aa,bb))
    roles=[m.name.split('.')[0] for m in obj.data.materials]
    data=obj.data;data.calc_loop_triangles()
    uv=data.uv_layers.active
    degenerate_uv=0
    for tri in data.loop_triangles:
        a,b,c=[uv.data[i].uv for i in tri.loops]
        area=(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)
        degenerate_uv+=abs(area)<1.e-14
    bm=bmesh.new();bm.from_mesh(data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1.e-7)
    closed=all(e.is_manifold for e in bm.edges)
    bm.free()
    expected_tri=row['triangles']
    item=dict(key=row['key'],passed=bound_pass and closed and degenerate_uv==0
        and len(data.loop_triangles)==expected_tri and roles==row['material_roles'],
        bounds_cm=actual,bounds_match=bound_pass,closed_after_position_weld=closed,
        material_roles=roles,uv_layers=[l.name for l in data.uv_layers],
        degenerate_uv_triangles=degenerate_uv,triangles=len(data.loop_triangles),expected_triangles=expected_tri,
        fbx_file=row['fbx_file'],fbx_sha256=hashlib.sha256(Path(row['fbx_file']).read_bytes()).hexdigest())
    checks.append(item)
    # Physical roles only; these previews intentionally do not pretend to be
    # final UE textured materials. Native map capture remains root's task.
    for mat in data.materials:
        if mat is None:continue
        mat.use_nodes=True
        shader=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if shader is None:continue
        role=mat.name.split('.')[0]
        if role=='Ceramic':
            shader.inputs['Base Color'].default_value=(.60,.565,.47,1)
            shader.inputs['Roughness'].default_value=.24
        elif role in ('Chrome','DarkMetal'):
            shader.inputs['Metallic'].default_value=.9 if role=='Chrome' else .6
            shader.inputs['Roughness'].default_value=.23 if role=='Chrome' else .5
        elif role=='Glass':
            shader.inputs['Base Color'].default_value=(.29,.35,.31,1)
            shader.inputs['Transmission Weight'].default_value=.85
            shader.inputs['Roughness'].default_value=.18
            shader.inputs['IOR'].default_value=1.45
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.002))
    floor=bpy.context.object
    mat=bpy.data.materials.new('PreviewFloor')
    mat.diffuse_color=(.095,.10,.10,1)
    mat.use_nodes=True
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.095,.10,.10,1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.8
    floor.data.materials.append(mat)
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=900
    scene.render.resolution_y=900
    scene.render.resolution_percentage=100
    scene.world.color=(.07,.07,.07)
    target=Vector((0,0,.4 if row['key']=='Toilet' else .58 if row['key']=='Washbasin' else 1.0 if row['key']=='ShowerScreen' else .03))
    cam_pos=(-1.35,-1.7,1.35) if row['key']=='Toilet' else (-1.15,-1.4,1.3) if row['key']=='Washbasin' else (1.1,2.6,1.55) if row['key']=='ShowerScreen' else (-1.2,-1.4,1.3)
    bpy.ops.object.camera_add(location=cam_pos)
    camera=bpy.context.object
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'
    camera.data.ortho_scale=1.03 if row['key']=='Toilet' else 1.10 if row['key']=='Washbasin' else 2.30 if row['key']=='ShowerScreen' else 1.28
    scene.camera=camera
    for name,loc,energy,size in (('Key',(-1.5,-2,3),900,2.5),('Rim',(1.8,1.3,2.5),800,2),('Fill',(-1.2,2.3,1.8),500,2)):
        bpy.ops.object.light_add(type='AREA',location=loc)
        lamp=bpy.context.object;lamp.name=name
        lamp.data.energy=energy;lamp.data.shape='DISK';lamp.data.size=size
        lamp.rotation_euler=(target-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.render.image_settings.file_format='PNG'
    scene.render.filepath=str(OUT/('Preview_'+row['key']+'.png'))
    bpy.ops.render.render(write_still=True)
    item['geometry_preview']=scene.render.filepath

passed=all(c['passed'] for c in checks)
report=dict(passed=passed,checks=checks,source_manifest_sha256=hashlib.sha256((OUT/'ModelDataManifest.json').read_bytes()).hexdigest(),
            note='Independent FBX reload validates original pivot dimensions, materials, watertight parts and physical UV. Previews show geometry using placeholder physical roles.')
(OUT/'IndependentFBXVerification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('SANITARY_FBX_INDEPENDENT_PASS' if passed else 'SANITARY_FBX_INDEPENDENT_FAIL')
if not passed:raise RuntimeError('Independent FBX verification failed')
