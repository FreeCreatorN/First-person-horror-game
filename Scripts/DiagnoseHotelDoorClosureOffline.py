import json,pathlib,re,difflib
W=pathlib.Path(__file__).resolve().parents[1]/'Saved/CodexOutputs/OldTownHotelDoorClosure_20261019'
def rd(p):
    b=p.read_bytes();return b.decode('utf-16' if b[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
n='BP_Hotel_DoorSlider_W85_H205_D12.t3d';a=rd(W/'BlueprintNative'/n);b=rd(W/'BlueprintNativeAfter'/n)
def extract(t,n):return re.search(r'(?ms)^   Begin Object Name="'+n+r'"[^\n]*\n.*?^   End Object\s*$',t).group(0)
for n in ('EventGraph','UserConstructionScript'):
    print(n);print(''.join(difflib.unified_diff(extract(a,n).splitlines(True),extract(b,n).splitlines(True)))[:10000])
for label,t in [('before',a),('after',b)]:print(label,[s for s in t.splitlines() if s.lstrip().startswith(('NewVariables','ImplementedInterfaces','ParentClass='))])
