import bpy, math, os, json
from mathutils import Vector
out=r'D:\UE\Project\HorrorGame\SourceArt\PeachwoodSword'
s=bpy.context.scene;s.frame_set(1)
root=bpy.data.objects['SWORD_CONTROL | reference design']
wood=next(m for m in bpy.data.materials if m.name.startswith('Peach wood | longitudinal grain')); n=wood.node_tree.nodes;l=wood.node_tree.links
p=next(x for x in n if x.type=='BSDF_PRINCIPLED')
p.inputs['Roughness'].default_value=.55
p.inputs['Specular IOR Level'].default_value=.28
mapping=next(x for x in n if x.type=='VECT_MATH');mapping.inputs[1].default_value=(22,22,.65)
ramp=next(x for x in n if x.type=='VALTORGB');ramp.color_ramp.elements[0].color=(.065,.021,.009,1);ramp.color_ramp.elements[1].color=(.30,.135,.063,1)
bump=next(x for x in n if x.type=='BUMP');bump.inputs['Strength'].default_value=.20;bump.inputs['Distance'].default_value=.00018
for name in [m.name for m in bpy.data.materials if m.name.startswith(('Deep vermilion silk','Dark brown woven grip'))]:
 m=bpy.data.materials.get(name)
 if not m:continue
 nd=m.node_tree.nodes;lk=m.node_tree.links;bs=next(x for x in nd if x.type=='BSDF_PRINCIPLED')
 bs.inputs['Roughness'].default_value=.76;bs.inputs['Specular IOR Level'].default_value=.22;bs.inputs['Sheen Weight'].default_value=.22
 if name.startswith('Deep'):
  bs.inputs['Base Color'].default_value=(.24,.009,.014,1);m.diffuse_color=(.24,.009,.014,1)
  no=nd.new('ShaderNodeTexNoise');no.inputs['Scale'].default_value=230;no.inputs['Detail'].default_value=2
  bu=nd.new('ShaderNodeBump');bu.inputs['Strength'].default_value=.16;bu.inputs['Distance'].default_value=.00009;lk.new(no.outputs['Fac'],bu.inputs['Height']);lk.new(bu.outputs[0],bs.inputs['Normal'])
# Accent the existing wrap geometry with subtle alternating cord tones.
wraps=[o for o in bpy.data.objects if o.name.startswith('Cross woven grip wrap')]
for i,o in enumerate(wraps):
 m=bpy.data.materials['Dark brown woven grip'].copy();m.name='Woven grip warm '+str(i)
 bs=next(x for x in m.node_tree.nodes if x.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(.052+i*.015,.027+i*.009,.017+i*.005,1)
 o.data.materials.clear();o.data.materials.append(m)
# Keep baked simulation and all transform actions intact.
cl=next(m for o in bpy.data.objects for m in o.modifiers if m.type=='CLOTH')
report={'cloth_baked':cl.point_cache.is_baked,'frame_end':s.frame_end,'fps':s.render.fps,'actions':len(bpy.data.actions),'materials_refined':True}
assert report['cloth_baked']
s['Visual refinement']='Finer longitudinal wood grain, matte vermilion woven silk, alternating warm grip wraps. Existing baked motion retained.'
cam=s.camera
pom=bpy.data.objects['Round cloud-carved pommel'].matrix_world.translation
blade=bpy.data.objects['Peachwood blade | broad engraved face']
pts=[blade.matrix_world@Vector(c) for c in blade.bound_box];low=min(v.z for v in pts)
center=Vector((pom.x+.025,0,(pom.z+low)/2))
def view(target,offset,scale,path,w,h):
 cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=scale
 s.render.resolution_x=w;s.render.resolution_y=h;s.render.resolution_percentage=100;s.render.filepath=os.path.join(out,path)
s.cycles.samples=32;s.cycles.use_denoising=True
view(center,(.32,-2,.10),1.16,'Optimized_Full.png',900,1400)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Optimized.blend'))
bpy.ops.render.render(write_still=True)
view(pom+Vector((.04,0,-.14)),(.18,-1,.06),.43,'Optimized_Detail.png',1200,1300)
bpy.ops.render.render(write_still=True)
view(center,(.32,-2,.10),1.16,'Optimized_Full.png',900,1400)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'PeachwoodSword_Optimized.blend'))
with open(os.path.join(out,'optimized_verification.json'),'w') as f:json.dump(report,f,indent=2)
print(report)

