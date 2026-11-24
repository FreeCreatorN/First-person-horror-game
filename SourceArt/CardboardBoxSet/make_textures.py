"""Original procedural carton textures. Pillow + numpy; no external artwork.

Atlas faces use a 3 x 2 grid, 24 pixel edge dilation and bottom-origin UV rows.
ORM = ambient occlusion (R), roughness (G), metallic (B). Normal is tangent +Y.
"""
from pathlib import Path
import json
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "Textures"
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 2048
PAD = 24
X = [0, 683, 1365, 2048]
FACES = {"Front": (0, 0), "Back": (1, 0), "Left": (2, 0),
         "Right": (0, 1), "Top": (1, 1), "Bottom": (2, 1)}
FONTS = Path("C:/Windows/Fonts")


def font(size, bold=False):
    return ImageFont.truetype(str(FONTS / ("msyhbd.ttc" if bold else "msyh.ttc")), size)


def noise(w, h, rng, scale, blur=0):
    a = rng.normal(128, 29, (max(2, h // scale), max(2, w // scale)))
    im = Image.fromarray(np.uint8(np.clip(a, 0, 255))).resize((w, h), Image.Resampling.BICUBIC)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return (np.asarray(im).astype(np.float32) - 128) / 29


def board(w, h, seed, damaged=False, pale_stock=False):
    rng = np.random.default_rng(seed)
    n = noise(w, h, rng, 230) * 3.6 + noise(w, h, rng, 45) * 2.3
    n += noise(w, h, rng, 9) * 0.8 + rng.normal(0, 0.8, (h, w))
    # Thin, irregular cellulose fibres, well below the visual scale of scratches.
    fibres = Image.new("L", (w, h), 128)
    d = ImageDraw.Draw(fibres)
    for _ in range(int(w * h / 67)):
        xx = int(rng.integers(w)); yy = int(rng.integers(h))
        le = int(rng.integers(2, 11)); sl = int(rng.integers(-2, 3))
        d.line((xx, yy, xx + le, yy + sl), fill=int(rng.integers(108, 149)), width=1)
    f = (np.asarray(fibres).astype(np.float32) - 128) * 0.23
    yy, xx = np.mgrid[:h, :w]
    edge = np.minimum.reduce([xx, w - 1 - xx, yy, h - 1 - yy]).astype(np.float32)
    edge_dark = np.exp(-edge / 12.0) * 9.0
    stains = noise(w, h, rng, 110)
    stains = np.maximum(stains - (0.8 if damaged else 1.4), 0)
    stains *= 10.0 if damaged else 4.2
    scalar = n + f - edge_dark - stains
    base = np.array([143, 108, 68], dtype=np.float32)
    if damaged:
        base = np.array([135, 101, 65], dtype=np.float32)
    if pale_stock:
        base = np.array([210, 211, 200], dtype=np.float32)
    rgb = base[None, None, :] + scalar[:, :, None] * np.array([1.0, .88, .68])
    if pale_stock:
        # Grey-white coated stock, worn through to the brown liner near exposed edges.
        exposure = np.clip(np.exp(-edge / 11) * (.38 + noise(w, h, rng, 22) * .16), 0, .72)
        rgb = rgb * (1 - exposure[:, :, None]) + np.array([143, 108, 68]) * exposure[:, :, None]
    im = Image.fromarray(np.uint8(np.clip(rgb, 0, 255)), "RGB")
    rough = np.clip(220 + noise(w, h, rng, 30) * 3.0 + stains * .35, 205, 240).astype(np.uint8)
    ao = np.clip(255 - edge_dark * .8 - stains * .25, 234, 255).astype(np.uint8)
    orm = Image.merge("RGB", (Image.fromarray(ao), Image.fromarray(rough), Image.new("L", (w, h), 0)))
    return im, orm


def centre(draw, xy, text, size, color, bold=False):
    ft = font(size, bold)
    bb = draw.textbbox((0, 0), text, font=ft)
    draw.text((xy[0] - (bb[2] - bb[0]) / 2, xy[1]), text, font=ft, fill=color)


def draw_symbols(d, x, y, ink, scale=1.0):
    # All marks are original vector drawings, with their standard physical meaning.
    def line(p, width=4):
        d.line([(x + a * scale, y + b * scale) for a, b in p], fill=ink, width=max(1, int(width * scale)))
    # Up arrows.
    for ax in (12, 41):
        line([(ax, 58), (ax, 9)], 5)
        line([(ax - 12, 24), (ax, 9), (ax + 12, 24)], 5)
    line([(0, 66), (54, 66)], 3)
    # Keep dry umbrella.
    ux = x + 91 * scale
    uy = y + 13 * scale
    box = (ux, uy, ux + 64 * scale, uy + 54 * scale)
    d.pieslice(box, 180, 360, fill=ink)
    for off in (0, 21, 42):
        d.ellipse((ux + off * scale, uy + 22 * scale, ux + (off + 22) * scale, uy + 34 * scale), fill=(0, 0, 0, 0))
    line([(123, 13), (123, 62), (129, 68), (136, 65)], 4)
    for ax in (98, 120, 142):
        line([(ax, -1), (ax - 3, 6)], 2)
    # Fragile stem glass.
    line([(193, 7), (230, 7), (227, 31), (219, 41), (211, 43), (202, 38), (196, 30), (193, 7)], 4)
    line([(211, 43), (211, 65)], 4)
    line([(198, 66), (226, 66)], 4)
    # Crack identifies the fragile handling mark.
    line([(215, 9), (207, 22), (217, 25), (211, 37)], 2)
    for xx, txt in ((28, "向上"), (123, "防潮"), (211, "易碎")):
        centre(d, (x + xx * scale, y + 77 * scale), txt, max(8, int(16 * scale)), ink)


def shipping_label(d, rng, variant):
    x, y, w, h = 622, 63, 238, 174
    # Slightly uneven warm paper edge and understated adhesive stain.
    d.rounded_rectangle((x - 3, y - 2, x + w + 2, y + h + 3), 2, fill=(35, 29, 21, 25))
    d.polygon([(x + 1, y + 2), (x + w, y), (x + w - 1, y + h - 1), (x, y + h)], fill=(221, 216, 199, 247))
    k = (43, 42, 37, 238)
    d.rectangle((x + 9, y + 8, x + w - 9, y + h - 9), outline=k, width=1)
    d.text((x + 17, y + 10), "物流配送 / SHIPPING", font=font(13, True), fill=k)
    d.line((x + 9, y + 35, x + w - 9, y + 35), fill=k, width=1)
    d.text((x + 17, y + 41), "到站：城南仓储中心", font=font(13), fill=k)
    d.text((x + 17, y + 63), "件数  01    普通货物", font=font(12), fill=k)
    d.text((x + 17, y + 83), "批次  24-08 / " + variant[:3].upper(), font=font(11), fill=k)
    bx = x + 21
    for i in range(77):
        width = int(rng.choice([1, 1, 2, 3]))
        if i % 2 == 0:
            d.rectangle((bx, y + 110, bx + width - 1, y + 143), fill=k)
        bx += width + 1
        if bx > x + w - 20:
            break
    centre(d, (x + w / 2, y + 147), "8824  0618  0371", 10, k)


def face_art(variant, face, seed):
    # Draw in physical face proportions: front 2:1, side 4:3, top 3:2.
    w, h = ((900, 450) if face in ("Front", "Back") else ((600, 450) if face in ("Left", "Right") else (900, 600)))
    art = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(art)
    rng = np.random.default_rng(seed)
    ink = (43, 39, 30, 235)
    colors = {"Fruit": (50, 89, 47, 231), "Water": (33, 75, 109, 235), "Noodles": (151, 46, 33, 231)}
    titles = {"Fruit": "新鲜蔬果", "Water": "矿泉水", "Noodles": "方便面"}
    if face in ("Front", "Back"):
        if variant in colors:
            color = colors[variant]
            title = titles[variant]
            subtitle = {"Fruit": "FRESH FRUIT & VEGETABLES", "Water": "NATURAL MINERAL WATER", "Noodles": "INSTANT NOODLES"}[variant]
            centre(d, (410, 145), title, 72, color, True)
            centre(d, (410, 231), subtitle, 17, color, True)
            d.line((128, 266, 690, 266), fill=color, width=2)
            details = {"Fruit": "新鲜采摘  ·  轻拿轻放", "Water": "饮用天然矿泉水  /  24瓶装", "Noodles": "香浓好味道  /  12桶装"}[variant]
            centre(d, (410, 279), details, 20, color)
            if variant == "Fruit":
                # Original two-fruit line art printed directly onto the carton.
                d.ellipse((107, 179, 151, 229), outline=color, width=4)
                d.ellipse((137, 179, 181, 229), outline=color, width=4)
                d.line((144, 184, 147, 159), fill=color, width=4)
                d.ellipse((150, 158, 179, 174), fill=color)
                d.line((153, 167, 176, 164), fill=(0, 0, 0, 0), width=2)
            elif variant == "Water":
                for yy in (315, 325):
                    d.line([(xx, yy + math.sin(xx * .047) * 3) for xx in range(145, 666, 3)], fill=color, width=2)
            else:
                d.rounded_rectangle((102, 139, 709, 263), radius=12, outline=color, width=3)
                d.arc((124, 172, 213, 242), 0, 180, fill=color, width=4)
                d.ellipse((124, 174, 213, 192), outline=color, width=4)
                d.line((150, 228, 186, 228), fill=color, width=4)
                for xx in (148, 166, 184):
                    d.line([(xx, 169), (xx - 3, 161), (xx + 2, 153), (xx, 146)], fill=color, width=3)
        elif variant == "Damaged":
            d.rectangle((0, 211, 899, 238), fill=(128, 49, 35, 138))
            d.line((0, 204, 899, 204), fill=(128, 49, 35, 119), width=2)
            d.text((59, 252), "仓储周转箱  /  STORAGE", font=font(21), fill=(50, 42, 30, 139))
        else:
            d.text((62, 218), "STORAGE / CARTON", font=font(22, True), fill=(56, 45, 31, 135))
            d.text((63, 254), "通用包装箱     请保持干燥", font=font(18), fill=(56, 45, 31, 125))
        draw_symbols(d, 69, 345, ink, .67)
        d.text((657, 371), "毛重 G.W.  12 KG", font=font(13), fill=ink)
        d.text((657, 395), "净重 N.W.  10 KG", font=font(13), fill=ink)
        if face == "Front":
            label_art = Image.new("RGBA", (900, 650), (0, 0, 0, 0))
            shipping_label(ImageDraw.Draw(label_art), rng, variant)
            label_art = label_art.crop((618, 59, 866, 243)).resize((184, 137), Image.Resampling.LANCZOS)
            art.alpha_composite(label_art, (680, 31))
        else:
            d.text((650, 61), "BATCH NO. 240818", font=font(14), fill=(50, 44, 31, 183))
            d.text((650, 87), "QC PASSED", font=font(15, True), fill=(50, 44, 31, 183))
    elif face in ("Left", "Right"):
        if variant == "Damaged":
            d.rectangle((0, 211, 599, 238), fill=(128, 49, 35, 138))
        elif variant in colors:
            centre(d, (300, 156), titles[variant], 54, colors[variant], True)
            centre(d, (300, 229), "请置于阴凉干燥处", 20, colors[variant])
        d.text((48, 324), "规格 / SPECIFICATION", font=font(17, True), fill=ink)
        d.text((48, 356), "生产批次  240818", font=font(16), fill=ink)
        d.text((48, 386), "堆码层数  ≤ 5", font=font(16), fill=ink)
    else:
        d.text((68, 516), "RECYCLE  /  可回收纸制品", font=font(18), fill=(54, 45, 31, 143))
        if face == "Bottom":
            centre(d, (450, 260), "瓦楞纸箱", 37, (54, 45, 31, 130), True)
            centre(d, (450, 317), "CORRUGATED FIBREBOARD", 17, (54, 45, 31, 130))
    # Ink loses small areas to porous liner and rubs down on the reused carton.
    aa = np.asarray(art).copy()
    a = aa[:, :, 3].astype(np.float32)
    wear = noise(w, h, rng, 5)
    a *= np.clip(.91 + wear * .09, .55, 1)
    dropout = rng.random(a.shape) < (.027 if variant == "Damaged" else .008)
    a[dropout] *= .18
    aa[:, :, 3] = np.uint8(a)
    return Image.fromarray(aa, "RGBA")

def add_crease_and_wear(im, seed, damaged=False, face="Front", pale_stock=False):
    rng = np.random.default_rng(seed)
    w, h = ((900, 450) if face in ("Front", "Back") else ((600, 450) if face in ("Left", "Right") else (900, 600)))
    scratches = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(scratches)
    # Damp tide mark is concentrated at the lower edge, rather than blanket grunge.
    xx = np.arange(w)
    water_level = h - (34 if damaged else 17) - 7 * np.sin(xx * .019) - 4 * np.sin(xx * .061)
    poly = [(0, h), *[(int(x), int(water_level[x])) for x in range(0, w, 3)], (w, h)]
    d.polygon(poly, fill=(73, 49, 27, 48 if damaged else 29))
    d.line([(int(x), int(water_level[x])) for x in range(0, w, 2)], fill=(73, 48, 25, 36 if damaged else 20), width=2)
    count = 64 if damaged else 24
    for _ in range(count):
        sx = int(rng.integers(w)); sy = int(rng.integers(h))
        le = int(rng.integers(8, 59 if damaged else 24))
        dy = int(rng.integers(-9, 10))
        d.line((sx, sy, sx + le, sy + dy), fill=(214, 181, 125, int(rng.integers(24, 72))), width=int(rng.integers(1, 3)))
    # A few long physical fold scores: broad shadow, compressed valley, lifted fibre.
    paths = [[(.12, .0), (.22, .28), (.27, .62), (.31, .98)],
             [(.96, .05), (.79, .41), (.84, .78), (.98, .96)]] if damaged else [[(.17, .04), (.20, .32), (.21, .71), (.24, .98)]]
    if damaged:
        paths.append([(.01, .69), (.31, .64), (.59, .72), (.99, .61)])
    for path in paths:
        p = [(int(a * w), int(b * h)) for a, b in path]
        d.line(p, fill=(54, 35, 18, 37 if damaged else 18), width=8 if damaged else 5)
        d.line(p, fill=(61, 39, 19, 94 if damaged else 43), width=2)
        d.line([(a + 2, b + 1) for a, b in p], fill=(222, 187, 130, 103 if damaged else 61), width=2)
    # Corner compression / folded liner scratches.
    corners = [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]
    for i, (cx, cy) in enumerate(corners):
        sx = 1 if cx < w / 2 else -1
        sy = 1 if cy < h / 2 else -1
        reach = (145 if damaged else 64) + int(rng.integers(-17, 24))
        points = [(cx, cy), (cx + sx * reach * .3, cy + sy * reach * .24), (cx + sx * reach, cy + sy * reach * .8)]
        d.line(points, fill=(68, 44, 24, 99 if damaged else 45), width=4 if damaged else 2)
        d.line([(a + 2, b + 2) for a, b in points], fill=(220, 184, 125, 98 if damaged else 57), width=2)
    # Exposed pulped paper flakes follow high-contact borders and crushed corners.
    for _ in range(90 if damaged else 24):
        side = int(rng.integers(4))
        along = float(rng.random())
        margin = float(rng.random() ** 2) * (16 if damaged else 7)
        px, py = ((margin, along * h) if side == 0 else ((w - margin, along * h) if side == 1 else ((along * w, margin) if side == 2 else (along * w, h - margin))))
        le = int(rng.integers(3, 23 if damaged else 12))
        d.polygon([(px, py), (px + le, py + 1), (px + le * .7, py + 4), (px + 2, py + 3)], fill=(202, 164, 104, 143 if damaged or pale_stock else 90))
    scratches = scratches.resize(im.size, Image.Resampling.LANCZOS)
    return Image.alpha_composite(im.convert("RGBA"), scratches).convert("RGB")


def tape_on_face(im, orm, seed, full=True, damaged=False):
    rng = np.random.default_rng(seed)
    w, h = im.size
    width = int(round(w * .13))
    x0 = (w - width) // 2
    length = h if full else int(h * .12)
    yy, xx = np.mgrid[:length, :width]
    a = np.asarray(im).copy().astype(np.float32)
    strip = a[:length, x0:x0 + width]
    grain = rng.normal(0, 1.0, (length, width))
    sheen = np.sin(xx / max(width, 1) * math.pi) * 4.5
    tint = np.array([138, 99, 53] if damaged else [151, 109, 58]) + (grain + sheen)[:, :, None]
    a[:length, x0:x0 + width] = strip * .3 + tint * .7
    # Small adhesive ridges on the long edges.
    a[:length, x0] *= .77
    a[:length, x0 + width - 1] *= .82
    a[:length, x0 + 2] += 7
    if damaged:
        # Scraped/lifted tape edge exposes patches of the underlying liner.
        original = np.asarray(im)
        for y in range(length):
            missing = int(1 + max(0, math.sin(y * .073) + math.sin(y * .023)) * width * .10)
            a[y, x0:x0 + missing] = original[y, x0:x0 + missing]
        for fraction in (.15, .32, .71, .86):
            cy = int(length * fraction)
            for x in range(width):
                y = min(length - 2, max(1, cy + int(math.sin(x * .18) * 2 + x * .04)))
                a[y, x0 + x] *= .73
                a[y + 1, x0 + x] += 23
    img = Image.fromarray(np.uint8(np.clip(a, 0, 255)), "RGB")
    oo = np.asarray(orm).copy()
    oo[:length, x0:x0 + width, 1] = np.clip((166 if damaged else 139) + rng.normal(0, 4, (length, width)), 126, 183)
    return img, Image.fromarray(oo)


def paste_dilated(atlas, tile, col, row):
    x0, x1 = X[col], X[col + 1]
    # Python image origin is upper left; UV origin is lower left.
    y0 = SIZE - (row + 1) * 1024
    inner_w, inner_h = x1 - x0 - 2 * PAD, 1024 - 2 * PAD
    tile = tile.resize((inner_w, inner_h), Image.Resampling.LANCZOS)
    arr = np.asarray(tile)
    arr = np.pad(arr, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
    atlas.paste(Image.fromarray(arr), (x0, y0))


def main():
    for vid, variant in enumerate(("Standard", "Damaged", "Fruit", "Water", "Noodles")):
        color = Image.new("RGB", (SIZE, SIZE))
        orm = Image.new("RGB", (SIZE, SIZE))
        for fid, (face, (col, row)) in enumerate(FACES.items()):
            w, h = X[col + 1] - X[col] - 2 * PAD, 1024 - 2 * PAD
            seed = 3118 + fid * 71
            im, om = board(w, h, seed, variant == "Damaged", variant == "Water")
            art = face_art(variant, face, seed + 200 + vid * 11).resize((w, h), Image.Resampling.LANCZOS)
            im = Image.alpha_composite(im.convert("RGBA"), art).convert("RGB")
            # Printed/paper areas retain diffuse, dielectric response.
            oa = np.asarray(om).copy()
            alpha = np.asarray(art)[:, :, 3] / 255.0
            oa[:, :, 1] = np.uint8(oa[:, :, 1] * (1 - alpha * .11))
            om = Image.fromarray(oa)
            im = add_crease_and_wear(im, seed + 700, variant == "Damaged", face, variant == "Water")
            if face == "Top":
                im, om = tape_on_face(im, om, seed + 900, True, variant == "Damaged")
            elif face in ("Front", "Back"):
                im, om = tape_on_face(im, om, seed + 900, False, variant == "Damaged")
            paste_dilated(color, im, col, row)
            paste_dilated(orm, om, col, row)
        color.save(OUT / f"T_Carton_{variant}_BaseColor.png")
        orm.save(OUT / f"T_Carton_{variant}_ORM.png")
        print(f"Saved {variant}", flush=True)
    # Shared fibre normal. Very gentle corrugation lies under the outer liner.
    rng = np.random.default_rng(4813)
    height = noise(SIZE, SIZE, rng, 3) * .45 + noise(SIZE, SIZE, rng, 22) * .35
    height += rng.normal(0, .1, (SIZE, SIZE))
    dy, dx = np.gradient(height)
    nx, ny = -dx * .12, dy * .12
    nz = np.ones_like(nx)
    length = np.sqrt(nx * nx + ny * ny + 1)
    normal = np.stack([nx / length, ny / length, nz / length], axis=-1)
    Image.fromarray(np.uint8(np.clip((normal * .5 + .5) * 255, 0, 255)), "RGB").save(OUT / "T_Carton_Shared_Normal.png")
    # Plain liner for the separate thin flaps and raw inner box surfaces.
    plain, plain_orm = board(512, 512, 9135)
    plain.save(OUT / "T_Carton_Plain_BaseColor.png")
    plain_orm.save(OUT / "T_Carton_Plain_ORM.png")
    # An all-tape swatch for narrow tape geometry. Runs vertically in UV.
    base = np.asarray(plain).astype(np.float32)
    yy, xx = np.mgrid[:512, :512]
    tint = np.array([157, 115, 64]) + (rng.normal(0, 1, (512, 512)) + np.sin(xx / 512 * math.pi) * 3)[:, :, None]
    tape = np.uint8(np.clip(base * .24 + tint * .76, 0, 255))
    Image.fromarray(tape, "RGB").save(OUT / "T_Carton_Tape_BaseColor.png")
    tape_orm = np.zeros((512, 512, 3), dtype=np.uint8)
    tape_orm[:, :, 0] = 255
    tape_orm[:, :, 1] = np.uint8(np.clip(140 + rng.normal(0, 2, (512, 512)), 130, 150))
    Image.fromarray(tape_orm, "RGB").save(OUT / "T_Carton_Tape_ORM.png")
    metadata = {"resolution": [2048, 2048], "padding_pixels": PAD,
                "origin": "bottom-left UV", "orm_channels": ["Occlusion", "Roughness", "Metallic"],
                "normal_convention": "tangent-space positive Y; set Flip Green Channel for Unreal if importing as DirectX",
                "tile_rects_uv": {}, "top_tape": {"tile_local_u_center": .5, "tile_local_u_width": .13, "v": [0, 1]},
                "license": "Original procedural artwork created for this project; no external artwork used."}
    for face, (col, row) in FACES.items():
        metadata["tile_rects_uv"][face] = [(X[col] + PAD) / SIZE, (row * 1024 + PAD) / SIZE,
                                                   (X[col + 1] - PAD) / SIZE, ((row + 1) * 1024 - PAD) / SIZE]
    (OUT / "TextureLayout.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    # Human-readable visual contact sheet, not imported as a game texture.
    previews = Image.new("RGB", (1500, 936), (39, 36, 32))
    p = ImageDraw.Draw(previews)
    for i, variant in enumerate(("Standard", "Damaged", "Fruit", "Water", "Noodles")):
        src = Image.open(OUT / f"T_Carton_{variant}_BaseColor.png")
        front = src.crop((24, 1048, 659, 2024)).resize((280, 140), Image.Resampling.LANCZOS)
        previews.paste(front, (i * 300 + 10, 41))
        p.text((i * 300 + 10, 12), variant, font=font(18), fill=(232, 225, 212))
        atlas = src.resize((280, 280), Image.Resampling.LANCZOS)
        previews.paste(atlas, (i * 300 + 10, 267))
        detail = src.crop((50, 1330, 570, 1760)).resize((280, 232), Image.Resampling.LANCZOS)
        previews.paste(detail, (i * 300 + 10, 572))
    p.text((12, 832), "ORIGINAL CARTON TEXTURES  |  2048 px / Base Color + ORM / shared fibre normal", font=font(23), fill=(220, 210, 192))
    p.text((12, 874), "Faces: front, back, left / right, top, bottom   |   24 px island padding", font=font(20), fill=(173, 162, 145))
    previews.save(OUT / "TexturePreview.jpg", quality=94)


if __name__ == "__main__":
    main()
