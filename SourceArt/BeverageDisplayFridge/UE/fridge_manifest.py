"""Scoped import contract for the planning-sheet upright beverage fridge."""
from hashlib import sha256
import json,math,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
ASSET=HERE.parent
PROJECT=ASSET.parents[1]
CONTENT=PROJECT/'Content'
EXPORTS=ASSET/'Exports'
MANIFEST=EXPORTS/'export_report.json'
TARGET='/Game/Yastars/Mesh/BeverageDisplayFridge'
DESTINATION=CONTENT/TARGET.removeprefix('/Game/')
PREFIX='SM_BeverageDisplayFridge_'
PARTS=('TopLightbox','GlassDoor','DoorHandle','DoorFrame',
       'Shelf01','Shelf02','Shelf03','Shelf04','Shelf05',
       'InnerLiner','OuterBody','VentGrille','FootFL','FootFR','FootRL','FootRR')
MESH_NAMES=tuple(PREFIX+part for part in PARTS)
TEXTURE_ROOT=TARGET+'/Textures'
MATERIAL_ROOT=TARGET+'/Materials'
PARENT='M_BeverageDisplayFridge_Opaque'
GLASS='M_BeverageDisplayFridge_Glass'
SIGN='M_BeverageDisplayFridge_Sign'
BLUEPRINT='BP_BeverageDisplayFridge'
TEXTURES={'base_color':'T_BeverageDisplayFridge_BaseColor.png','orm':'T_BeverageDisplayFridge_ORM.png'}
DOOR_PARTS=('GlassDoor','DoorHandle','DoorFrame')
GROUPS={'DoorHinge':DOOR_PARTS,'Shelves':('Shelf01','Shelf02','Shelf03','Shelf04','Shelf05'),
        'BaseFeet':('FootFL','FootFR','FootRL','FootRR')}
PLANNING={'TopLightbox':'顶部灯箱与顶盖','GlassDoor':'玻璃门','DoorHandle':'门把手','DoorFrame':'门框',
          'Shelves':'内部层板（五层）','InnerLiner':'内胆','OuterBody':'外壳主体','VentGrille':'散热格栅','BaseFeet':'底座与底脚'}

def digest(path):
    result=sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,value):
    path=Path(path);pending=path.with_suffix(path.suffix+'.tmp')
    pending.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');pending.replace(path)
def source(relative):
    path=(EXPORTS/relative).resolve()
    assert path.is_relative_to(EXPORTS.resolve()) and path.is_file(),str(path)
    return path
def packages():
    return {'/Game/'+path.relative_to(CONTENT).with_suffix('').as_posix():
        {'file':str(path),'sha256':digest(path),'bytes':path.stat().st_size}
        for path in sorted(DESTINATION.rglob('*.uasset'))}
def protected_snapshot():
    candidates=set(CONTENT.rglob('*.umap'));candidates.add(PROJECT/'HorrorGame.uproject')
    scopes=[PROJECT/'Config',CONTENT/'Yastars'/'Mesh',CONTENT/'__ExternalActors__',CONTENT/'__ExternalObjects__']
    scopes.extend(CONTENT/root/folder for root in ('Yastar','Yastars') for folder in ('UI','Items'))
    for folder in scopes:candidates.update(path for path in folder.rglob('*') if path.is_file())
    return {path.relative_to(PROJECT).as_posix():digest(path) for path in sorted(candidates)
            if path.is_file() and not path.is_relative_to(DESTINATION)}
def verify_protected(baseline):
    current=protected_snapshot();changed=sorted(p for p in baseline.keys()|current.keys() if baseline.get(p)!=current.get(p))
    assert not changed,('Unrelated project files changed',changed)
    return len(current)
def image_dimensions(path):
    with path.open('rb') as stream:header=stream.read(24)
    assert header[:8]==b'\x89PNG\r\n\x1a\n' and header[12:16]==b'IHDR',str(path)
    return list(struct.unpack('>II',header[16:24]))
def hinge_spec(doors):
    assert set(doors)=={'main'},doors
    raw=doors['main'];pivot=raw.get('hinge_m',raw.get('pivot_m'))
    assert pivot is not None and len(pivot)==3 and all(math.isfinite(float(v)) for v in pivot)
    closed=raw.get('closed_ue_cm',[100*pivot[0],-100*pivot[1],100*pivot[2]])
    assert len(closed)==3 and all(abs(float(a)-b)<.003 for a,b in zip(closed,[100*pivot[0],-100*pivot[1],100*pivot[2]]))
    angle=float(raw.get('open_yaw_deg',-105.0));assert 15<=abs(angle)<=150,angle
    return {'hinge_m':list(map(float,pivot)),'closed_ue_cm':list(map(float,closed)),
            'open_yaw_deg':angle,'component':'DoorHinge'}
def read_export():
    manifest=read(MANIFEST);assert manifest['success'] is True
    rows={row['name']:row for row in manifest['assets']}
    assert len(rows)==len(manifest['assets'])==16 and set(rows)==set(MESH_NAMES)
    resolution=manifest['baked_resolution'];assert isinstance(resolution,int) and resolution>=512
    total=sum(int(row['triangles']) for row in rows.values());assert 4500<=total<=8000,('Planning LOD0 budget',total)
    used={slot for row in rows.values() for slot in row['slots']}
    assert used<= {'M_Fridge_Opaque','M_Fridge_Glass','M_Fridge_Sign'}
    expected={MATERIAL_ROOT+'/'+PARENT,MATERIAL_ROOT+'/'+GLASS,TARGET+'/'+BLUEPRINT}
    if 'M_Fridge_Sign' in used:expected.add(MATERIAL_ROOT+'/'+SIGN)
    inputs={MANIFEST.name:digest(MANIFEST)};sources=manifest['sha256']
    for name,row in rows.items():
        assert row['fbx']==name+'.fbx'
        assert int(row['triangles'])>=12 and int(row['collision_hulls'])>=1
        assert row['slots'] and len(row['slots'])==len(set(row['slots']))
        assert len(row['bounds_min_m'])==len(row['bounds_max_m'])==3
        assert all(a<b for a,b in zip(row['bounds_min_m'],row['bounds_max_m']))
        path=source(row['fbx']);assert digest(path)==sources[row['fbx']].lower(),path
        inputs[row['fbx']]=digest(path);expected.add(TARGET+'/'+name)
        pivot=row.get('pivot_m',[0,0,0]);assert len(pivot)==3 and all(math.isfinite(float(v)) for v in pivot)
    for filename in TEXTURES.values():
        path=source(filename);assert digest(path)==sources[filename].lower()
        assert image_dimensions(path)==[resolution,resolution]
        inputs[filename]=digest(path);expected.add(TEXTURE_ROOT+'/'+path.stem)
    hinge=hinge_spec(manifest['doors'])
    for part in DOOR_PARTS:
        row=rows[PREFIX+part]
        assert all(abs(float(a)-b)<.00001 for a,b in zip(row.get('pivot_m',hinge['hinge_m']),hinge['hinge_m'])),part
        assert row.get('component_parent','DoorHinge')=='DoorHinge',part
    return manifest,rows,expected,inputs
