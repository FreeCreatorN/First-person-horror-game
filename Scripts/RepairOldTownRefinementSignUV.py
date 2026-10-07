"""Correct the stock plane's V orientation in nine owned sign materials."""
import json
import sys
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
from PolishOldTownHotel import sha
WORK=ROOT/'Saved/CodexOutputs/StreetRefinement_20261007'
TAG='StreetRefinement_20261007'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    build=read(WORK/'BuildReport.json');mapfile=ROOT/('Content/'+build['target_level'].removeprefix('/Game/')+'.umap')
    digest=sha(mapfile);assert digest==build['map_sha256']
    assert all(sha(Path(p))==h for p,h in build['new_asset_sha256'].items()),'Inspect any external edits to new sign assets first.'
    lib=unreal.EditorAssetLibrary;edit=unreal.MaterialEditingLibrary
    before=WORK/'BeforeSignUVRepair';before.mkdir(exist_ok=True)
    if not (before/'BuildReport.json').exists():write(before/'BuildReport.json',build)
    fixed=[]
    for row in build['street_refinement']['new_signs']:
        path=row['material_asset'].split('.')[0]
        assert path.startswith('/Game/CodexGenerated/OldTown/StreetRefinement_20261007/Materials/')
        material=unreal.load_asset(path);assert lib.get_metadata_tag(material,TAG+'_Owned')=='true'
        if lib.get_metadata_tag(material,TAG+'_UVVFlipped')=='true':continue
        file=ROOT/('Content/'+path.removeprefix('/Game/')+'.uasset')
        import shutil
        if not (before/file.name).exists():shutil.copy2(file,before/file.name)
        edit.delete_all_material_expressions(material)
        texture=unreal.load_asset(row['texture_asset']);assert isinstance(texture,unreal.Texture2D)
        sample=edit.create_material_expression(material,unreal.MaterialExpressionTextureSample,-300,0);sample.set_editor_property('texture',texture)
        uv=edit.create_material_expression(material,unreal.MaterialExpressionTextureCoordinate,-750,0);uv.set_editor_property('v_tiling',-1.)
        offset=edit.create_material_expression(material,unreal.MaterialExpressionConstant2Vector,-750,150)
        offset.set_editor_property('r',0.);offset.set_editor_property('g',1.)
        add=edit.create_material_expression(material,unreal.MaterialExpressionAdd,-500,0)
        assert edit.connect_material_expressions(uv,'',add,'A')
        assert edit.connect_material_expressions(offset,'',add,'B')
        assert edit.connect_material_expressions(add,'',sample,'')
        assert edit.connect_material_property(sample,'RGB',unreal.MaterialProperty.MP_BASE_COLOR)
        rough=edit.create_material_expression(material,unreal.MaterialExpressionConstant,-300,150);rough.set_editor_property('r',.96)
        assert edit.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
        edit.recompile_material(material);lib.set_metadata_tag(material,TAG+'_UVVFlipped','true')
        assert lib.save_loaded_asset(material,False);fixed.append(path)
    assert sha(mapfile)==digest
    for path in build['new_asset_sha256']:build['new_asset_sha256'][path]=sha(Path(path))
    write(WORK/'BuildReport.json',build)
    write(WORK/'SignUVRepair.json',dict(passed=True,map_sha256=digest,map_unchanged=True,materials_fixed=fixed,
        method='Texture coordinates U preserved, V mapped to 1 minus V; source PNG files unchanged.'))
    unreal.log('SIGN_UV_REPAIR_PASS '+str(len(fixed)))
if __name__=='__main__':main()
