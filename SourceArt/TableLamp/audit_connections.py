import bpy,json
s=bpy.context.scene;o=bpy.data.objects['SM_TableLamp'];parents=list(range(len(o.data.vertices)))
def find(x):
 while parents[x]!=x:parents[x]=parents[parents[x]];x=parents[x]
 return x
for e in o.data.edges:
 a,b=map(find,e.vertices)
 if a!=b:parents[a]=b
g={}
for v in o.data.vertices:g.setdefault(find(v.index),[]).append(v.co)
rows=[]
for vs in g.values():
 lo=[min(v[i] for v in vs) for i in range(3)];hi=[max(v[i] for v in vs) for i in range(3)]
 rows.append({'vertices':len(vs),'min':lo,'max':hi})
print(json.dumps({'file':bpy.data.filepath,'components':sorted(rows,key=lambda x:x['vertices'],reverse=True)[:25]}))
