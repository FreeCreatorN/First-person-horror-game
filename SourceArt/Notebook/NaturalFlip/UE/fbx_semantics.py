"""Read FBX animation curves without bpy; ignore file timestamps and object IDs."""
import hashlib
import importlib
import json
import sys
import types


def animation_semantic(path):
    package_name = '_notebook_natural_fbx_readonly'
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [r'D:\SteamLibrary\steamapps\common\Blender\5.2\scripts\addons_core\io_scene_fbx']
        sys.modules[package_name] = package
    parser = importlib.import_module(package_name+'.parse_fbx')
    root, _ = parser.parse(str(path))
    objects = next(element for element in root.elems if element.id == b'Objects')
    by_id = {element.props[0]:element for element in objects.elems}
    links = [element.props for element in next(element for element in root.elems if element.id == b'Connections').elems]

    def decode(value):
        return value.split(b'\x00',1)[0].decode('utf-8') if isinstance(value,bytes) else str(value)

    nodes, curves = {}, {}
    for link in links:
        if len(link)>3 and link[0] == b'OP' and link[1] in by_id and link[2] in by_id:
            source, target = by_id[link[1]], by_id[link[2]]
            if source.id == b'AnimationCurveNode' and target.id == b'Model':
                nodes[link[1]] = (decode(target.props[1]),decode(link[3]))
    for link in links:
        if len(link)>3 and link[0] == b'OP' and link[2] in nodes and link[1] in by_id and by_id[link[1]].id == b'AnimationCurve':
            key = (*nodes[link[2]],decode(link[3]))
            assert key not in curves, ('Multiple stacks or duplicate channel',key)
            attributes = {decode(element.id):list(element.props[0]) if hasattr(element.props[0],'__iter__') and not isinstance(element.props[0],(bytes,str)) else element.props[0]
                          for element in by_id[link[1]].elems if element.props}
            curves[key] = {name:attributes[name] for name in ('KeyTime','KeyValueFloat','KeyAttrFlags','KeyAttrDataFloat','KeyAttrRefCount') if name in attributes}
    assert curves, str(path)
    canonical = [{'model':key[0],'property':key[1],'axis':key[2],**curves[key]} for key in sorted(curves)]
    encoded = json.dumps(canonical,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return {'sha256':hashlib.sha256(encoded).hexdigest(),'channels':len(curves)}
