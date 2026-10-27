import sys,json
from pathlib import Path
import unreal
out=Path(unreal.Paths.project_dir()).resolve()/'Saved/CodexOutputs/SurfaceSeparation_20261009/API.txt'
items=[unreal.MaterialExpressionScalarParameter,unreal.GeometryScriptCopyMeshToAssetOptions,
 *[getattr(unreal,n) for n in dir(unreal) if 'GeometryScript' in n and ('Asset' in n or 'MeshQuery' in n or 'MeshEdit' in n)],
 unreal.MaterialEditingLibrary.set_material_instance_parent,
 unreal.MaterialEditingLibrary.connect_material_property,
 unreal.StaticMesh,unreal.Actor.add_component_by_class if hasattr(unreal.Actor,'add_component_by_class') else None]
text='\n\n'.join(str(o)+'\n'+str(getattr(o,'__doc__','')) for o in items)
for o in items:
    for n in dir(o):
        if any(k in n for k in ('copy_mesh','vertex_position','triangle','parent')):
            text+='\n'+n+'\n'+str(getattr(getattr(o,n),'__doc__',''))
out.write_text(text,encoding='utf-8')
unreal.log('SURFACE_API_PASS')
