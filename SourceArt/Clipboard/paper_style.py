"""Printed ruling applied directly to the paper shader, front face only."""
def apply_ruled_paper(material):
    nodes=material.node_tree.nodes;links=material.node_tree.links
    shader=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    if nodes.get('Ruled paper blue ink'):
        return
    original=shader.inputs['Base Color'].links[0].from_socket if shader.inputs['Base Color'].is_linked else None
    def calc(operation,a,b):
        n=nodes.new('ShaderNodeMath');n.operation=operation
        for value,socket in ((a,n.inputs[0]),(b,n.inputs[1])):
            if isinstance(value,(int,float)):socket.default_value=value
            else:links.new(value,socket)
        return n.outputs[0]
    coord=nodes.new('ShaderNodeTexCoord');xyz=nodes.new('ShaderNodeSeparateXYZ');links.new(coord.outputs['Object'],xyz.inputs[0])
    x,y=xyz.outputs['X'],xyz.outputs['Y']
    geom=nodes.new('ShaderNodeNewGeometry');normal=nodes.new('ShaderNodeSeparateXYZ');links.new(geom.outputs['Normal'],normal.inputs[0])
    front=calc('GREATER_THAN',normal.outputs['Z'],.5)
    delta=calc('SUBTRACT',.108,y)
    row=calc('LESS_THAN',calc('MODULO',delta,.008),.00035)
    row=calc('MULTIPLY',row,calc('GREATER_THAN',delta,0))
    row=calc('MULTIPLY',row,calc('GREATER_THAN',y,-.145))
    row=calc('MULTIPLY',row,calc('LESS_THAN',calc('ABSOLUTE',x,0),.096))
    row=calc('MULTIPLY',row,front)
    blue=nodes.new('ShaderNodeMixRGB');blue.name='Ruled paper blue ink';blue.label='Blue rules: 8 mm spacing, 0.35 mm ink'
    links.new(row,blue.inputs[0])
    if original:links.new(original,blue.inputs[1])
    else:blue.inputs[1].default_value=shader.inputs['Base Color'].default_value
    blue.inputs[2].default_value=(.13,.30,.48,1)
    margin=calc('LESS_THAN',calc('ABSOLUTE',calc('ADD',x,.081),0),.0002)
    margin=calc('MULTIPLY',margin,calc('GREATER_THAN',y,-.147))
    margin=calc('MULTIPLY',margin,calc('LESS_THAN',y,.116))
    margin=calc('MULTIPLY',margin,front)
    red=nodes.new('ShaderNodeMixRGB');red.name='Ruled paper red margin';red.label='Red margin, 24 mm from left edge'
    links.new(margin,red.inputs[0]);links.new(blue.outputs[0],red.inputs[1]);red.inputs[2].default_value=(.52,.13,.12,1)
    links.new(red.outputs[0],shader.inputs['Base Color'])
    material['paper_style']='Blue horizontal ruling with red left margin; unprinted back'
    material['rule_spacing_mm']=8.0
