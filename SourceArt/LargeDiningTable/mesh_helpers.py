def grain(o, axis='X', tone=None, wear=0.35):
    if o.type != 'MESH':
        return
    tone = rng.uniform(0.85, 1.12) if tone is None else tone
    coords = o.data.attributes.new('WoodCoord', 'FLOAT_VECTOR', 'POINT')
    tones = o.data.attributes.new('WoodTone', 'FLOAT', 'POINT')
    wears = o.data.attributes.new('Wear', 'FLOAT', 'POINT')
    shift = Vector((rng.random() * 5, rng.random() * 0.11, rng.random() * 0.13))
    for v in o.data.vertices:
        x, y, z = v.co
        co = (x, y, z) if axis == 'X' else (z, x, y) if axis == 'Z' else (y, x, z)
        coords.data[v.index].vector = Vector(co) + shift
        tones.data[v.index].value = tone
        wears.data[v.index].value = wear
def edges(o, amount=0.0015):
    b = o.modifiers.new('Worn solid edges', 'BEVEL')
    b.width = amount
    b.segments = 3
    b.harden_normals = True
    o.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
    for p in o.data.polygons:
        p.use_smooth = True
def box(name, loc, size, group=base_parts, axis='X', mat=wood_mat, bevel=0.0015, tone=None, wear=0.35, endfaces=False):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if endfaces and mat == wood_mat:
        o.data.materials.append(end_mat)
        k = {'X': 0, 'Y': 1, 'Z': 2}[axis]
        for p in o.data.polygons:
            if abs(p.normal[k]) > 0.9:
                p.material_index = 1
    grain(o, axis, tone, wear)
    if bevel:
        edges(o, bevel)
    group.append(o)
    return o
def custom(name, verts, faces, group, axis='X', mat=wood_mat, bevel=0.0015):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    s.collection.objects.link(o)
    o.data.materials.append(mat)
    grain(o, axis)
    group.append(o)
    if bevel:
        edges(o, bevel)
    return o
def peg(name, loc, radius, depth, rotation, group, mat=end_mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=depth, location=loc, rotation=rotation)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(mat)
    grain(o, 'Z', wear=0.3)
    edges(o, 0.00028)
    group.append(o)
    return o
