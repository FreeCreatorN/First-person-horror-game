from pathlib import Path
p=Path(r'D:\UE\Project\HorrorGame\SourceArt\WaterDispenser')
src=(p/'fix_fit.py').read_text(encoding='utf-8-sig')
start=src.index('# Full-sized spare water container')
end=src.index('tail=tail.replace',start)
replacement="""# Restore a fitted front service panel, without the spare bottle.
box('Front panel gasket',(0,-.145,.291),(.277,.012,.442),dark,.004)
box('Front service cover',(0,-.153,.291),(.270,.016,.434),cream,.005)
box('Service cover grip',(0,-.164,.460),(.038,.006,.007),dark,.002)
for j in range(6):
 for x in [-.055,.055]:box('Cover ventilation slot',(x,-.162,.126+j*.014),(.091,.003,.005),dark,.001)
"""
src=src[:start]+replacement+src[end:]
src=src.replace('WaterDispenser_Fitted.png','WaterDispenser_ClosedPanel.png').replace('WaterDispenser_Fitted.blend','WaterDispenser_ClosedPanel.blend')
(p/'restore_panel.py').write_text(src,encoding='utf-8')
