"""Compose the four independently reloaded model renders for review."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
FONT = 'C:/Windows/Fonts/msyh.ttc'
title = ImageFont.truetype(FONT, 32)
label = ImageFont.truetype(FONT, 25)
small = ImageFont.truetype(FONT, 17)
canvas = Image.new('RGB', (1240, 1390), (23, 27, 27))
draw = ImageDraw.Draw(canvas)
draw.text((35, 22), '旧旅馆卫浴 · 几何细化预览', font=title, fill=(222, 220, 207))
draw.text((35, 72), '实际摆放尺寸与原点保持；图中为材质角色预览，最终材质由场景统一处理。',
          font=small, fill=(166, 177, 171))
items = (
    ('Toilet', '马桶', '保留碗体与水箱，补全座圈铰链与外侧冲水柄'),
    ('Washbasin', '洗手盆', '连续瓷盆、空心排水管、两根落地金属支脚'),
    ('ShowerTray', '淋浴底盘', '圆角瓷质底盘、朝地漏坡度、实体金属格栅'),
    ('ShowerScreen', '淋浴隔断', '连续框架、密封条、夹具与相连的拉手'),
)
inputs = {}
for index, (key, heading, detail) in enumerate(items):
    path = OUT/('Preview_'+key+'.png')
    inputs[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    x = 25 + (index % 2) * 610
    y = 115 + (index // 2) * 625
    with Image.open(path) as preview:
        canvas.paste(preview.convert('RGB').resize((590, 550), Image.Resampling.LANCZOS), (x, y))
    draw.text((x+12, y+554), heading, font=label, fill=(226, 226, 212))
    draw.text((x+12, y+588), detail, font=small, fill=(171, 183, 177))
path = OUT/'ContactSheet.png'
canvas.save(path)
(OUT/'ContactSheetManifest.json').write_text(json.dumps(dict(
    image=str(path), image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    input_image_sha256=inputs,
    input_model_manifest_sha256=hashlib.sha256((OUT/'ModelDataManifest.json').read_bytes()).hexdigest(),
    verification_report_sha256=hashlib.sha256((OUT/'IndependentFBXVerification.json').read_bytes()).hexdigest(),
    note='Four current independent FBX reload previews, composed without geometry or asset changes.'
), ensure_ascii=False, indent=2), encoding='utf-8')
print(path)
