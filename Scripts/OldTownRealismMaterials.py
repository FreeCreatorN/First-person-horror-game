"""Owned, physical-scale PBR materials for the realistic old hotel.

FBX UVs use one unit per metre; existing architectural cubes use world projection.
Every variant retains the previously verified constant world displacement.
"""
import hashlib,json
from pathlib import Path
import unreal

ROOT=Path(unreal.Paths.project_dir()).resolve()
ASSET='/Game/CodexGenerated/OldTown/Realism_20261012'
PARAM='CodexSurfaceTranslationCM_20261009'
edit=unreal.MaterialEditingLibrary
assets=unreal.EditorAssetLibrary
_cache={};_textures={};_report=[]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def file(obj):return ROOT/('Content/'+obj.get_path_name().split('.')[0][6:]+'.uasset')
def save(obj):
    assert obj.get_path_name().startswith(ASSET+'/')
    assert assets.save_loaded_asset(obj,False)
    return dict(asset=obj.get_path_name(),file=str(file(obj)),sha256=sha(file(obj)))
def node(m,cls,**props):
    n=edit.create_material_expression(m,getattr(unreal,'MaterialExpression'+cls))
    assert n
    for k,v in props.items():n.set_editor_property(k,v)
    return n
def connect(a,b,p,output=''):
    ok=edit.connect_material_expressions(a,output,b,p)
    if not ok and p in ('Input','VectorInput','Coordinates'):
        names=list(edit.get_material_expression_input_names(b))
        assert names,(b,p)
        ok=edit.connect_material_expressions(a,output,b,str(names[0]))
    assert ok,(a,b,p,output,list(edit.get_material_expression_input_names(b)))
def prop(a,p,output=''):assert edit.connect_material_property(a,output,getattr(unreal.MaterialProperty,'MP_'+p))
def scalar(m,v):return node(m,'Constant',r=float(v))
def color(m,v):return node(m,'Constant3Vector',constant=unreal.LinearColor(*v,1))
def mul(m,a,b,out=''):
    n=node(m,'Multiply');connect(a,n,'A',out);connect(b,n,'B');return n
def add(m,a,b):
    n=node(m,'Add');connect(a,n,'A');connect(b,n,'B');return n

def texture(path,name,kind):
    key=(name,kind)
    if key in _textures:return _textures[key]
    package=ASSET+'/Textures/T_R_'+name
    t=assets.load_asset(package) if assets.does_asset_exist(package) else None
    if not t:
        task=unreal.AssetImportTask()
        for k,v in dict(filename=str(path),destination_path=ASSET+'/Textures',destination_name='T_R_'+name,automated=True,replace_existing=False,save=False,factory=unreal.TextureFactory()).items():task.set_editor_property(k,v)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task]);t=assets.load_asset(package)
    assert isinstance(t,unreal.Texture2D),package
    t.set_editor_property('srgb',kind=='color')
    t.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP if kind=='normal' else unreal.TextureCompressionSettings.TC_DEFAULT if kind=='color' else unreal.TextureCompressionSettings.TC_MASKS)
    row=save(t);row.update(kind='texture',channel=kind,source=str(path),source_sha256=sha(path),srgb=kind=='color');_report.append(row)
    _textures[key]=t;return t

def scan(prefix,folder,names):
    return [texture(folder/n,prefix+'_'+k,k) for k,n in zip(('color','normal','rough'),names)]

def load_textures():
    third=ROOT/'SourceArt/ThirdParty/PolyHaven'
    own=ROOT/'SourceArt/OldTownRealism_20261012/Textures'
    result={}
    for role,base in [('Wood','wood_table_worn'),('Plaster','painted_plaster_wall'),('PaintedMetal','green_metal_rust')]:
        result[role]=scan(role,third/(base+'_2k'),[base+'_diff_2k.jpg',base+'_nor_dx_2k.jpg',base+'_rough_2k.jpg'])
    result['Fabric']=scan('Fabric',own,['Fabric_col_2.jpg','Fabric_nor_dx.jpg','Fabric_Rough.jpg'])
    result['Stone']=scan('Terrazzo',own,['Terrazzo_diff.jpg','Terrazzo_nor_dx.jpg','Terrazzo_Rough.jpg'])
    result['Asphalt']=scan('Asphalt',own,['Asphalt_diff.jpg','Asphalt_nor_dx.jpg','Asphalt_Rough.jpg'])
    result['Brick']=scan('Brick',own,['Brick_diff.jpg','Brick_nor_dx.jpg','Brick_Rough.jpg'])
    result['Concrete']=scan('ConcreteFloor',own,['ConcreteFloor_diff.jpg','ConcreteFloor_nor_dx.jpg','ConcreteFloor_Rough.jpg'])
    result['ConcreteWall']=scan('Concrete',third/'concrete_wall_003_2k',['concrete_wall_003_diff_2k.jpg','concrete_wall_003_nor_dx_2k.jpg','concrete_wall_003_rough_2k.jpg'])
    return result

def sample(m,t,cm,mode,normal=False):
    if mode=='UV':
        coords=node(m,'TextureCoordinate',u_tiling=100./cm,v_tiling=100./cm)
        n=node(m,'TextureSample',texture=t,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if t.get_editor_property('srgb') else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
        connect(coords,n,'Coordinates');return n,'RGB'
    name='WorldAlignedNormal' if normal else 'WorldAlignedTexture'
    function=assets.load_asset('/Engine/Functions/Engine_MaterialFunctions01/Texturing/'+name+'.'+name)
    assert function
    obj=node(m,'TextureObject',texture=t)
    obj.set_editor_property('sampler_type',unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if t.get_editor_property('srgb') else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    n=node(m,'MaterialFunctionCall');assert n.set_material_function(function)
    connect(obj,n,'TextureObject');connect(color(m,[cm]*3),n,'TextureSize')
    return n,'XYZ Texture'

SPEC={
    'Wood':('Wood',120.,[.9,.83,.7],.68,0.),
    'PaintedWood':('Wood',120.,[.22,.38,.27],.77,0.),
    'Plaster':('Plaster',200.,[.91,.87,.79],.85,0.),
    'Concrete':('Concrete',200.,[.92,.90,.86],.86,0.),
    'ConcreteWall':('ConcreteWall',200.,[.92,.90,.86],.86,0.),
    'Stone':('Stone',200.,[.86,.84,.78],.58,0.),
    'PaintedMetal':('PaintedMetal',160.,[.88,.92,.84],.63,.3),
    'Linen':('Fabric',40.,[.71,.66,.54],.86,0.),
    'LinenSeam':('Fabric',40.,[.49,.46,.39],.88,0.),
    'Upholstery':('Fabric',40.,[.57,.65,.60],.9,0.),
    'DarkMetal':(None,100.,[.065,.072,.065],.43,.82),
    'Chrome':(None,100.,[.63,.64,.61],.24,1.),
    'Ceramic':(None,100.,[.75,.73,.66],.22,0.),
    'Glass':(None,100.,[.72,.79,.76],.16,0.),
    'Letters':(None,100.,[.71,.65,.48],.62,0.),
    'Paper':(None,100.,[.64,.59,.47],.88,0.),
    'Rubber':(None,100.,[.023,.026,.023],.83,0.),
    'Asphalt':('Asphalt',200.,[.69,.71,.72],.63,0.),
    'BluePlaster':('Plaster',200.,[.50,.67,.72],.86,0.),
    'GreenPlaster':('Plaster',200.,[.62,.70,.54],.86,0.),
    'BluePaint':('PaintedMetal',160.,[.38,.59,.71],.67,.3),
    'RedPaint':('PaintedMetal',160.,[.55,.31,.25],.69,.3),
    'OchrePaint':('PaintedMetal',160.,[.74,.59,.31],.69,.3),
    'GreenPaint':('PaintedMetal',160.,[.62,.76,.51],.68,.3),
    'Rust':('PaintedMetal',100.,[.51,.29,.14],.84,.25),
    'RedBrick':('Brick',100.,[.85,.83,.79],.90,0.),
    'Brass':(None,100.,[.48,.34,.14],.40,1.),
    'Plastic':(None,100.,[.15,.19,.16],.62,0.),
    'Cardboard':(None,60.,[.37,.25,.13],.91,0.),
    'Leaf':(None,100.,[.13,.19,.09],.85,0.),
    'Soil':('Concrete',100.,[.15,.12,.08],.95,0.),
    'Puddle':(None,100.,[.043,.057,.052],.06,0.),
    'Stain':(None,100.,[.14,.15,.11],.95,0.),
    'Marking':('Asphalt',200.,[.94,.87,.70],.75,0.),
}

def master(role,mode='World'):
    key=(role,mode)
    if key in _cache:return _cache[key]
    source,cm,tint,rough,metal=SPEC[role]
    path=ASSET+'/Materials/M_R_'+role+'_'+mode
    m=assets.load_asset(path) if assets.does_asset_exist(path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_R_'+role+'_'+mode,ASSET+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
    assert m
    edit.delete_all_material_expressions(m)
    m.set_editor_property('tangent_space_normal',mode=='UV')
    if source:
        textures=_scans[source]
        c,out=sample(m,textures[0],cm,mode)
        if role in ('Linen','LinenSeam'):
            # Plain hotel linen uses the scanned yarn microstructure, not a tartan dye.
            r,ro=sample(m,textures[2],cm,mode)
            c=add(m,mul(m,r,scalar(m,.14),ro),scalar(m,.86));out=''
        elif role=='Upholstery':
            des=node(m,'Desaturation');connect(c,des,'Input',out);connect(scalar(m,.78),des,'Fraction');c,out=des,''
        elif role in ('BluePaint','RedPaint','OchrePaint','GreenPaint','Rust'):
            des=node(m,'Desaturation');connect(c,des,'Input',out);connect(scalar(m,.85),des,'Fraction');c,out=des,''
        elif role=='Marking':
            c,out=color(m,[1,1,1]),''
        prop(mul(m,c,color(m,tint),out),'BASE_COLOR')
        n,no=sample(m,textures[1],cm,mode,True)
        # Preserve normals in their actual projection space.
        strength=.22 if role in ('Wood','PaintedWood') else .42 if role in ('Linen','LinenSeam','Upholstery') else .25 if source in ('Plaster','ConcreteWall') else .35 if source=='Concrete' else .65
        flatten=node(m,'LinearInterpolate',const_alpha=strength)
        flat=color(m,[0,0,1]) if mode=='UV' else node(m,'VertexNormalWS')
        connect(flat,flatten,'A');connect(n,flatten,'B',no)
        norm=node(m,'Normalize');connect(flatten,norm,'VectorInput');prop(norm,'NORMAL')
        r,ro=sample(m,textures[2],cm,mode)
        rr=add(m,mul(m,r,scalar(m,.3),ro),scalar(m,rough-.15))
        clamp=node(m,'Clamp',min_default=.08,max_default=.96);connect(rr,clamp,'Input');prop(clamp,'ROUGHNESS')
    else:
        prop(color(m,tint),'BASE_COLOR');prop(scalar(m,rough),'ROUGHNESS')
        prop(color(m,[0,0,1]) if mode=='UV' else node(m,'VertexNormalWS'),'NORMAL')
    prop(scalar(m,metal),'METALLIC');prop(scalar(m,.5),'SPECULAR')
    translation=node(m,'VectorParameter',parameter_name=unreal.Name(PARAM),default_value=unreal.LinearColor(0,0,0,0))
    prop(translation,'WORLD_POSITION_OFFSET','RGB')
    m.set_editor_property('max_world_position_offset_displacement',1.)
    m.set_editor_property('always_evaluate_world_position_offset',True)
    if role=='Glass':
        m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
        m.set_editor_property('two_sided',True)
        m.set_editor_property('translucency_lighting_mode',unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
        prop(scalar(m,.16),'OPACITY')
        prop(scalar(m,1.45),'REFRACTION')
    edit.recompile_material(m)
    row=save(m);row.update(kind='master',role=role,projection=mode,tile_size_cm=cm,normal_space='tangent' if m.get_editor_property('tangent_space_normal') else 'world',roughness_range=[max(.08,rough-.15),min(.96,rough+.15)],surface_translation_parameter=PARAM,scan=source)
    _report.append(row);_cache[key]=m;return m

_instances={}
def get(role,mode='World',offset=(0.,0.,0.)):
    values=tuple(round(float(x),6) for x in offset)
    m=master(role,mode)
    if max(abs(v) for v in values)<1.e-8:return m
    key=(role,mode,values)
    if key in _instances:return _instances[key]
    name='MI_R_'+role+'_'+hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]
    path=ASSET+'/Materials/Offsets/'+name
    mi=assets.load_asset(path) if assets.does_asset_exist(path) else unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,ASSET+'/Materials/Offsets',unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    assert mi
    edit.set_material_instance_parent(mi,m)
    edit.set_material_instance_vector_parameter_value(mi,unreal.Name(PARAM),unreal.LinearColor(*values,0))
    edit.update_material_instance(mi)
    val=edit.get_material_instance_vector_parameter_value(mi,unreal.Name(PARAM))
    assert max(abs(float(getattr(val,k))-v) for k,v in zip(('r','g','b'),values))<.000002
    row=save(mi);row.update(kind='offset_instance',role=role,projection=mode,offset_cm=list(values),parent=m.get_path_name());_report.append(row)
    _instances[key]=mi;return mi

def initialize():
    global _scans
    for suffix in ('Textures','Materials','Materials/Offsets'):assets.make_directory(ASSET+'/'+suffix)
    _scans=load_textures()
    return _scans
def report():
    rows={r['asset']:dict(r,sha256=sha(r['file'])) for r in _report}
    return dict(passed=True,assets=list(rows.values()),physical_uv_cm_per_unit=100.,source_license='https://polyhaven.com/license')
