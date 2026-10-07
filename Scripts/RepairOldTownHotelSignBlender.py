"""Repair only the oversized hotel letters in the saved opening-parts source."""
import bpy,bmesh,hashlib,json,shutil,sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path('D:/UE/Project/HorrorGame')
SOURCE=ROOT/'SourceArt/OldTownHotelOpenings_20261004'
NAME='SM_OTS_HotelSignLetters'
sys.path.insert(0,str(ROOT/'Scripts'))
from BuildOldTownOpeningBlender import normalize_hotel_sign,mesh_bounds_cm,validate_hotel_sign

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fingerprint(obj):
    digest=hashlib.sha256()
    digest.update(repr(tuple(tuple(row) for row in obj.matrix_world)).encode())
    if obj.type=='MESH':
        for vertex in obj.data.vertices:digest.update(repr(tuple(vertex.co)).encode())
        for polygon in obj.data.polygons:
            digest.update(repr((tuple(polygon.vertices),polygon.material_index)).encode())
        digest.update(repr(tuple(mat.name if mat else None for mat in obj.data.materials)).encode())
    return digest.hexdigest()

def repair():
    blend=SOURCE/'OldTownHotelOpenings.blend'
    assert Path(bpy.data.filepath).resolve()==blend.resolve(),bpy.data.filepath
    before_fbx={p.name:sha(p) for p in sorted(SOURCE.glob('*.fbx'))}
    assert len(before_fbx)==16,len(before_fbx)
    protected={obj.name:fingerprint(obj) for obj in bpy.data.objects if obj.name!=NAME}
    target=bpy.data.objects[NAME]
    assert target.type=='MESH' and len(target.data.vertices)>0
    before_bounds=mesh_bounds_cm(target)
    backup=SOURCE/'Backups'/('HotelSignRepair_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(parents=True,exist_ok=False)
    for filename in ('OldTownHotelOpenings.blend',NAME+'.fbx','ImportManifest.json','Profiles.json'):
        shutil.copy2(SOURCE/filename,backup/filename)
    bpy.ops.object.select_all(action='DESELECT')
    target.select_set(True);bpy.context.view_layer.objects.active=target
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bounds,dimensions=normalize_hotel_sign(target)
    bm=bmesh.new();bm.from_mesh(target.data)
    nonmanifold=sum(not edge.is_manifold for edge in bm.edges)
    bm.free();assert nonmanifold==0,nonmanifold
    assert protected=={obj.name:fingerprint(obj) for obj in bpy.data.objects if obj.name!=NAME},'Other Blender objects changed'
    bpy.ops.export_scene.fbx(filepath=str(SOURCE/(NAME+'.fbx')),use_selection=True,
        global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        use_mesh_modifiers=True,use_triangles=True,bake_anim=False,
        axis_forward='-Y',axis_up='Z',bake_space_transform=False)
    after_fbx={p.name:sha(p) for p in sorted(SOURCE.glob('*.fbx'))}
    changed=[name for name in before_fbx if before_fbx[name]!=after_fbx[name]]
    assert changed==[NAME+'.fbx'],changed
    manifest_path=SOURCE/'ImportManifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    entry=next(row for row in manifest['assets'] if row['name']==NAME)
    entry.update(width=dimensions[0],height=48.,bounds_cm=bounds,dimensions_cm=dimensions,
        vertices=len(target.data.vertices),polygons=len(target.data.polygons),nonmanifold_edges=nonmanifold)
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    profiles_path=SOURCE/'Profiles.json'
    profiles=json.loads(profiles_path.read_text(encoding='utf-8'))
    profile=next(row for row in profiles if row['name']==NAME)
    profile.update(width=dimensions[0],height=48.)
    profiles_path.write_text(json.dumps(profiles,indent=2),encoding='utf-8')
    # A separate snapshot already preserves the original source, without .blend1 churn.
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report={'passed':True,'target':NAME,'backup':str(backup),'before_bounds_cm':before_bounds,
        'bounds_cm':bounds,'dimensions_cm':dimensions,'nonmanifold_edges':nonmanifold,
        'protected_blender_objects':len(protected),'protected_object_fingerprints':protected,
        'fbx_before_sha256':before_fbx,'fbx_after_sha256':after_fbx,'changed_fbx':changed,
        'source_blend_sha256':sha(blend)}
    (SOURCE/'HotelSignRepairReport.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('HOTEL_SIGN_REPAIR_PASS '+json.dumps({'dimensions_cm':dimensions,'changed_fbx':changed,'backup':str(backup)}),flush=True)

def verify():
    report_path=SOURCE/'HotelSignRepairReport.json'
    report=json.loads(report_path.read_text(encoding='utf-8'))
    target=bpy.data.objects[NAME]
    source_bounds,source_dimensions=validate_hotel_sign(target)
    assert report['protected_object_fingerprints']=={
        obj.name:fingerprint(obj) for obj in bpy.data.objects if obj.name!=NAME},'Reload changed protected objects'
    assert report['fbx_after_sha256']=={p.name:sha(p) for p in sorted(SOURCE.glob('*.fbx'))},'FBX changed after repair'
    backup=Path(report['backup'])
    for filename,key in (('ImportManifest.json','assets'),('Profiles.json',None)):
        original=json.loads((backup/filename).read_text(encoding='utf-8'))
        current=json.loads((SOURCE/filename).read_text(encoding='utf-8'))
        original_rows=original[key] if key else original
        current_rows=current[key] if key else current
        assert [r for r in original_rows if r['name']!=NAME]==[r for r in current_rows if r['name']!=NAME],filename
    # Reimport the one exported FBX into this disposable verification process.
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(SOURCE/(NAME+'.fbx')))
    imported=next(obj for obj in bpy.context.selected_objects if obj.type=='MESH')
    fbx_bounds,fbx_dimensions=validate_hotel_sign(imported)
    # Exercise the corrected generation sequence on an unscaled font object too.
    curve=bpy.data.curves.new('HotelSignGenerationCheck','FONT');curve.body='老城酒店'
    curve.font=bpy.data.fonts.load('C:/Windows/Fonts/simhei.ttf');curve.align_x='CENTER'
    curve.extrude=.002;curve.bevel_depth=.0005;curve.bevel_resolution=1
    fresh=bpy.data.objects.new('HotelSignGenerationCheck',curve);bpy.context.scene.collection.objects.link(fresh)
    fresh.rotation_euler=(1.5707963267948966,0,0)
    bpy.ops.object.select_all(action='DESELECT');fresh.select_set(True);bpy.context.view_layer.objects.active=fresh
    bpy.ops.object.convert(target='MESH');fresh=bpy.context.object
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    fresh_bounds,fresh_dimensions=normalize_hotel_sign(fresh)
    report['fresh_verification']={'passed':True,'source_dimensions_cm':source_dimensions,
        'fbx_dimensions_cm':fbx_dimensions,'regenerated_font_dimensions_cm':fresh_dimensions,
        'other_manifest_and_profile_entries_unchanged':True,'protected_objects_unchanged_after_reload':True}
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('HOTEL_SIGN_FRESH_VERIFY_PASS '+json.dumps(report['fresh_verification']),flush=True)

if __name__=='__main__':
    verify() if '--verify-only' in sys.argv else repair()
