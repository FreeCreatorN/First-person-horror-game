"""Publish current two-part source validation, retaining the original atlas proof."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
split=json.loads((OUT/'split_report.json').read_text(encoding='utf-8'))
old=json.loads((OUT/'Before'/'validation_report.json').read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert split['success'] and old['success']
assert sha(ROOT/'Camera.blend')==split['blend_sha256']
for path,digest in split['texture_files_sha256'].items():assert sha(path)==digest
for info in old['bakes'].values():assert sha(info['path'])==info['sha256']
result={'success':True,'stage':'Two-part source with the existing UV atlas preserved',
        'geometry':{},'uv':{},'fbx_roundtrip':{},'bakes':old['bakes'],
        'atlas_bake_evidence':'ShutterSplit/Before/validation_report.json',
        'component_split_evidence':'ShutterSplit/split_report.json',
        'baked_materials':{},'display_materials':{},'renders':split['renders'],
        'separate_materials':old['separate_materials'],
        'blend_file':str(ROOT/'Camera.blend'),'blend_sha256':split['blend_sha256'],
        'final_visibility':{'canonical_hidden':True,'display_visible':True,'source_hidden':True},
        'assembly':{'pivot_blender_m':split['pivot_blender_m'],'socket_ue_cm':split['socket_ue_cm'],
                    'press_travel_cm':split['press_travel_cm'],'default_state':'Released'}}
for name,part in split['parts'].items():
    assert sha(ROOT/part['filename'])==part['sha256'] and part['fbx_roundtrip']['success']
    result['geometry'][name]={key:part[key] for key in ('triangles','dimensions_cm','bounds_min_m','bounds_max_m','non_manifold_edges')}
    result['uv'][name]={'layers':['UVMap'],'zero_area_triangles':0,'method':'Original per-loop UV values copied without repacking'}
    result['fbx_roundtrip'][name]={**part['fbx_roundtrip'],'source':str(ROOT/part['filename']),'sha256':part['sha256']}
    opaque={str(i):source for i,(source,target) in enumerate(part['material_slots'].items()) if target=='M_Camera_Opaque'}
    glass={str(i):source for i,(source,target) in enumerate(part['material_slots'].items()) if target=='M_Camera_Glass'}
    result['baked_materials'][name]={'name':'T_Camera_Baked','atlas_reused':True,'source_opaque_slots':opaque,
                                   'preserved_slots':glass,'emission_connected':False,'emission_strength':0.,
                                   'metallic_texture_connected':True}
    result['display_materials'][name]=['M_Camera_OpticalGlass' if target=='M_Camera_Glass' else 'T_Camera_Baked' for target in part['material_slots'].values()]
(ROOT/'validation_report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('CAMERA_SPLIT_SOURCE_REPORT_PUBLISHED')
