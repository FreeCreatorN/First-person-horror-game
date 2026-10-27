def geometry_info(obj):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
    try:
        mesh.calc_loop_triangles()
        world_vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        minimum = [min(v[i] for v in world_vertices) for i in range(3)]
        maximum = [max(v[i] for v in world_vertices) for i in range(3)]
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            result = {'vertices': len(bm.verts), 'faces': len(bm.faces),
                      'non_manifold_edges': sum(not edge.is_manifold for edge in bm.edges),
                      'loose_vertices': sum(not vertex.link_edges for vertex in bm.verts)}
        finally:
            bm.free()
        result.update({'triangles': len(mesh.loop_triangles), 'bounds_min_m': minimum,
                       'bounds_max_m': maximum,
                       'dimensions_m': [maximum[i] - minimum[i] for i in range(3)]})
        return result
    finally:
        evaluated.to_mesh_clear()

def uv_info(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    assert mesh.uv_layers.active, MESH_NAME + ' has no UV0'
    data = mesh.uv_layers.active.data
    minimum = [min(item.uv[i] for item in data) for i in range(2)]
    maximum = [max(item.uv[i] for item in data) for i in range(2)]
    area, degenerates = 0., 0
    for triangle in mesh.loop_triangles:
        a, b, c = [data[i].uv for i in triangle.loops]
        triangle_area = abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) * .5
        area += triangle_area
        degenerates += triangle_area < 1.e-13
    result = {'layers': [layer.name for layer in mesh.uv_layers],
              'active': mesh.uv_layers.active.name, 'min': minimum, 'max': maximum,
              'triangle_uv_area_sum': area, 'zero_area_triangles': degenerates}
    assert all(v >= -1.e-5 for v in minimum) and all(v <= 1.00001 for v in maximum), result
    assert degenerates == 0 and 0. < area <= 1.001, result
    return result

def verify_roundtrip(obj, source_report):
    expected = geometry_info(obj)
    original_objects = set(bpy.data.objects)
    original_meshes = set(bpy.data.meshes)
    original_materials = set(bpy.data.materials)
    original_collections = set(bpy.data.collections)
    result = {'success': False, 'source': str(FBX), 'sha256': sha256(FBX)}
    report['fbx_roundtrip'] = result
    log('FBX roundtrip begin')
    try:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.import_scene.fbx(filepath=str(FBX), use_anim=False)
        imported = set(bpy.data.objects) - original_objects
        meshes = [o for o in imported if o.type == 'MESH' and not o.name.startswith('UCX_')]
        collisions = [o for o in imported if o.type == 'MESH' and o.name.startswith('UCX_')]
        assert len(meshes) == 1, [o.name for o in meshes]
        assert not any(o.type in ('CAMERA', 'LIGHT') for o in imported), [o.name for o in imported]
        imported_obj = meshes[0]
        actual = geometry_info(imported_obj)
        expected_count = source_report['parts'][MESH_NAME]['collision_hulls']
        expected_count = expected_count if isinstance(expected_count, int) else len(expected_count)
        result.update({'imported_mesh': imported_obj.name, 'geometry': actual,
                       'ucx_count': len(collisions), 'expected_ucx_count': expected_count,
                       'uv_layers': len(imported_obj.data.uv_layers),
                       'pivot_world_m': list(imported_obj.matrix_world.translation),
                       'material_slots': [slot.material.name if slot.material else None
                                          for slot in imported_obj.material_slots]})
        assert len(collisions) == expected_count, result
        assert actual['non_manifold_edges'] == 0 and actual['loose_vertices'] == 0, result
        assert len(imported_obj.data.uv_layers) >= 1, result
        assert imported_obj.matrix_world.translation.length < .00001, result
        for key in ('dimensions_m', 'bounds_min_m', 'bounds_max_m'):
            assert max(abs(a - b) for a, b in zip(actual[key], expected[key])) < .00002, (key, result)
        original_slots = {slot.material.name for slot in obj.material_slots if slot.material}
        imported_slots = {slot.material.name.split('.')[0] for slot in imported_obj.material_slots if slot.material}
        assert original_slots == imported_slots, (original_slots, imported_slots)
        result['success'] = True
    finally:
        for imported_obj in list(set(bpy.data.objects) - original_objects):
            bpy.data.objects.remove(imported_obj, do_unlink=True)
        for collection in list(set(bpy.data.collections) - original_collections):
            bpy.data.collections.remove(collection)
        for datablocks, originals in ((bpy.data.meshes, original_meshes),
                                     (bpy.data.materials, original_materials)):
            for item in list(set(datablocks) - originals):
                if item.users == 0:
                    datablocks.remove(item)
    log('FBX roundtrip passed')
