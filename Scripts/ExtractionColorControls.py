import unreal
E=unreal.MaterialEditingLibrary
for name in ['M_GreenPortal_Beam','M_GreenPortal_Ring','M_GreenExtraction_Filaments','M_GreenExtraction_Particle']:
    m=unreal.load_asset('/Game/Yastar/Materials/'+name)
    params=[o for o in unreal.ObjectIterator(unreal.MaterialExpressionVectorParameter) if o.get_path_name().startswith(m.get_path_name()+':') and str(o.get_editor_property('parameter_name'))=='Tint']
    if params:continue
    old=E.get_material_property_input_node(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    output=E.get_material_property_input_node_output_name(m,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    tint=E.create_material_expression(m,unreal.MaterialExpressionVectorParameter,-100,-400)
    tint.set_editor_property('parameter_name','Tint');tint.set_editor_property('default_value',unreal.LinearColor(1,1,1,1))
    mul=E.create_material_expression(m,unreal.MaterialExpressionMultiply,150,-200)
    E.connect_material_expressions(old,output,mul,'A');E.connect_material_expressions(tint,'',mul,'B')
    E.connect_material_property(mul,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    E.recompile_material(m);unreal.EditorAssetLibrary.save_loaded_asset(m)
for name in ['Body','Ring','Filaments','Particle']:
    m=unreal.load_asset('/Game/Yastar/Materials/MI_GreenExtraction_'+name)
    E.update_material_instance(m);unreal.EditorAssetLibrary.save_loaded_asset(m)
