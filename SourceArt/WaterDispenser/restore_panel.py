from pathlib import Path
out=Path(r'D:\UE\Project\HorrorGame\SourceArt\WaterDispenser')
source=(out/'refine.py').read_text(encoding='utf-8-sig')
split="bpy.ops.object.select_all(action='DESELECT')\nfor o in parts:o.select_set(True)"
head,tail=source.split(split,1)
exec(head)
# Eliminate stacked floating facade panels and build an actual open storage cabinet.
for prefix in ['Lower cabinet','Lower door seam','Lower service panel','Service latch','Front vent grille','Rear service panel','Rear vent opening','Rear screw']:remove_prefix(prefix)
box('Storage left wall',(-.148,0,.291),(.024,.302,.466),cream,.005)
box('Storage right wall',(.148,0,.291),(.024,.302,.466),cream,.005)
box('Storage rear wall',(0,.144,.290),(.276,.016,.468),cream,.004)
box('Storage floor',(0,-.004,.068),(.290,.292,.020),cream,.004)
box('Storage ceiling',(0,-.004,.514),(.290,.292,.022),cream,.004)
box('Storage floor insert',(0,-.004,.080),(.265,.264,.006),dark,.003)
box('Storage front sill',(0,-.143,.078),(.279,.018,.028),cream,.004)
# Tap feet are embedded into the fascia, not hovering in front of it.
for o in parts:
 if o.name.startswith('Tap base flange'):o.location.y=-.179
 if o.name.startswith('Maker label'):
  o.location=(0,-.17199,.807);o.data.size=.009;o.data.extrude=.00003
# Rear service panel touches the shell; vent inserts and fasteners touch that panel.
box('Rear fitted service panel',(0,.153,.647),(.276,.009,.400),dark,.003)
for j in range(12):box('Rear fitted louvre',(0,.159,.55+j*.018),(.216,.006,.007),steel,.001)
for x in [-.121,.121]:
 for z in [.474,.819]:cyl('Rear seated screw',(x,.161,z),.0033,.005,steel,(math.pi/2,0,0))
# Restore a fitted front service panel, without the spare bottle.
box('Front panel gasket',(0,-.145,.291),(.277,.012,.442),dark,.004)
box('Front service cover',(0,-.153,.291),(.270,.016,.434),cream,.005)
box('Service cover grip',(0,-.164,.460),(.038,.006,.007),dark,.002)
for j in range(6):
 for x in [-.055,.055]:box('Cover ventilation slot',(x,-.162,.126+j*.014),(.091,.003,.005),dark,.001)
tail=tail.replace('WaterDispenser_Refined.png','WaterDispenser_ClosedPanel.png').replace('WaterDispenser_Refined.blend','WaterDispenser_ClosedPanel.blend')
exec(split+tail)

