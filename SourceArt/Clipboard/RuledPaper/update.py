"""Change only the clipboard paper's printed color; preserve all mesh exports."""
import bpy,json,hashlib,time,shutil,traceback,struct
from pathlib import Path
from array import array
from mathutils import Vector
OUT=Path(__file__).resolve().parent.parent
TASK=OUT/'RuledPaper';TEXTURES=OUT/'Textures'
report={'success':False,'bakes':{},'renders':{},'changed_texture':'T_ClipboardPaper_BaseColor.png'}
started=time.perf_counter()
def sha256(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def log(message):print('RULED_PAPER '+message,flush=True)
def write_report():
    report['elapsed_seconds']=time.perf_counter()-started
    (TASK/'update_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
def geometry_hash(obj):
    h=hashlib.sha256()
    for v in obj.data.vertices:h.update(struct.pack('<3f',*v.co))
    for p in obj.data.polygons:h.update(struct.pack('<I',len(p.vertices)));h.update(struct.pack('<'+'I'*len(p.vertices),*p.vertices))
    for layer in obj.data.uv_layers:
        for loop in layer.data:h.update(struct.pack('<2f',*loop.uv))
    return h.hexdigest()
def render(name,path):
    s.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    assert path.is_file() and path.stat().st_size>1024
    report['renders'][name]={'path':str(path),'sha256':sha256(path),'bytes':path.stat().st_size}
    write_report()
source=OUT/'Clipboard.blend';color=TEXTURES/'T_ClipboardPaper_BaseColor.png'
tracked=[*OUT.glob('*.fbx'),*(p for p in TEXTURES.glob('*.png') if p!=color)]
before={str(p):sha256(p) for p in tracked}
backup=OUT.parents[1]/'Saved'/'CodexBackups'/'ClipboardBeforeRuledPaper_20261022'
backup.mkdir(parents=True,exist_ok=True)
for p in (source,color):
    dest=backup/p.name
    if not dest.exists():shutil.copy2(p,dest)
report['backup_root']=str(backup)
try:
    bpy.ops.wm.open_mainfile(filepath=str(source));s=bpy.context.scene
    names=('SM_Clipboard_Board','SM_Clipboard_Clip','SM_Clipboard_Paper')
    geometry_before={name:geometry_hash(bpy.data.objects[name]) for name in names}
    original=bpy.data.materials.get('M_Clipboard_WhitePaper');assert original
    exec(compile((OUT/'paper_style.py').read_text(encoding='utf-8'),str(OUT/'paper_style.py'),'exec'),globals())
    apply_ruled_paper(original)
    paper=bpy.data.objects['SM_Clipboard_Paper'];baked=paper.data.materials[0]
    for slot in paper.material_slots:slot.material=original
    canonical=bpy.data.collections['UE meshes - canonical origins'];display=bpy.data.collections['Clipboard - display assembly']
    canonical.hide_viewport=False;canonical.hide_render=False;display.hide_viewport=True;display.hide_render=True
    bpy.context.view_layer.update()
    s.render.engine='CYCLES';s.cycles.samples=8;s.cycles.device='CPU';s.render.bake.use_selected_to_active=False
    exec(compile((OUT/'bake_functions.py').read_text(encoding='utf-8-sig'),str(OUT/'bake_functions.py'),'exec'),globals())
    texture_prefix='T_ClipboardPaper';image=bake_channel(paper,'BaseColor',4096)
    base_nodes=[n for n in baked.node_tree.nodes if n.type=='TEX_IMAGE' and n.label=='BaseColor'];assert len(base_nodes)==1
    base_nodes[0].image=image
    for slot in paper.material_slots:slot.material=baked
    canonical.hide_viewport=True;canonical.hide_render=True;display.hide_viewport=False;display.hide_render=False
    bpy.context.view_layer.update()
    # The printed rules belong to the front material and never add floating mesh.
    geometry_after={name:geometry_hash(bpy.data.objects[name]) for name in names}
    assert geometry_after==geometry_before
    report['geometry_before']=geometry_before;report['geometry_after']=geometry_after
    report['untouched_source_files']={str(p):sha256(p) for p in tracked};assert report['untouched_source_files']==before
    report['paper_style']={'line_spacing_mm':8,'blue_line_width_mm':.35,'red_margin_from_left_mm':24,'back_unprinted':True,'texture_resolution':[4096,4096]}
    s.cycles.samples=40;s.cycles.use_denoising=True;s.render.resolution_percentage=100
    cam=s.camera;matrix=cam.matrix_world.copy();scale=cam.data.ortho_scale
    render('overall',OUT/'Clipboard_Preview.png')
    center=Vector((0,.128,.008));cam.location=center+Vector((.15,-.14,.23));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.15
    render('clip_detail',OUT/'Clipboard_ClipDetail.png')
    center=Vector((0,-.035,.004));cam.location=center+Vector((.0,-.12,.47));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.32
    render('paper_detail',TASK/'Clipboard_RuledPaper_Detail.png')
    cam.matrix_world=matrix;cam.data.ortho_scale=scale;s.render.filepath=str(OUT/'Clipboard_Preview.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    report['source']=str(source);report['source_sha256']=sha256(source);report['success']=True;write_report()
except Exception:
    report['error']=traceback.format_exc();write_report();raise
log('COMPLETE '+str(report['success']))
