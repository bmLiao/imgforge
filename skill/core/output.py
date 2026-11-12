"""輸出：尺寸/fit、sprite sheet、格式寫出、預覽。"""
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import ForgeError
from .ops import apply as apply_ops
from .sources import SvgSource, _color

FMT = {".png": "png", ".apng": "apng", ".jpg": "jpg", ".jpeg": "jpg",
       ".webp": "webp", ".gif": "gif", ".svg": "svg"}
RESAMPLE = {"lanczos": Image.LANCZOS, "nearest": Image.NEAREST,
            "bilinear": Image.BILINEAR, "bicubic": Image.BICUBIC}
FITS = ("contain", "cover", "stretch", "pad")


class Frame:
    """單一幀：來源 + 原生幀號 + 當幀軌道屬性。"""

    def __init__(self, src, idx=0, props=None):
        self.src, self.idx, self.props = src, idx, props or {}


def target_size(size, nat, where):
    nw, nh = nat
    if size is None:
        return max(1, round(nw)), max(1, round(nh))
    if isinstance(size, (int, float)):
        size = [size, size]
    if not (isinstance(size, list) and len(size) == 2):
        raise ForgeError(f"{where}: size 需為 [w, h]，等比的一邊填 null")
    w, h = size
    if w is None and h is None:
        return max(1, round(nw)), max(1, round(nh))
    if h is None:
        h = w * nh / nw
    if w is None:
        w = h * nw / nh
    return max(1, round(w)), max(1, round(h))


class Renderer:
    def __init__(self):
        self.cache = {}

    def fit(self, fr: Frame, W, H, spec, where):
        fit = spec.get("fit", "contain")
        if fit not in FITS:
            raise ForgeError(f"{where}: fit 只能是 {'/'.join(FITS)}")
        nw, nh = fr.src.size
        if fit == "stretch":
            cw, ch = W, H
        elif fit == "pad":
            cw, ch = max(1, round(nw)), max(1, round(nh))
        else:
            s = (min if fit == "contain" else max)(W / nw, H / nh)
            if fr.src.pixel and fit == "contain" and s >= 1:
                s = math.floor(s)  # 像素風整數倍，像素大小一致
            cw, ch = max(1, round(nw * s)), max(1, round(nh * s))
        rs = spec.get("resample")
        if rs is not None and rs not in RESAMPLE:
            raise ForgeError(f"{where}: resample 只能是 {'/'.join(RESAMPLE)}")
        key = (id(fr.src), fr.idx, json.dumps(fr.props, sort_keys=True), cw, ch,
               spec.get("css"), bool(spec.get("crisp")), rs)
        img = self.cache.get(key)
        if img is None:
            img = fr.src.render(fr.idx, json.loads(key[2]), cw, ch, spec.get("css"),
                                bool(spec.get("crisp")), RESAMPLE.get(rs))
            self.cache[key] = img
        if (cw, ch) != (W, H):
            canvas = Image.new("RGBA", (W, H))
            canvas.paste(img, ((W - cw) // 2, (H - ch) // 2))
            img = canvas
        return apply_ops(img, spec.get("ops"), where)


def anim_frames(anim, sel, where):
    idx = sel if sel is not None else range(anim.count)
    out = []
    for i in idx:
        if not isinstance(i, int) or not 0 <= i < anim.count:
            raise ForgeError(f"{where}: frames 含無效幀號 {i}（0..{anim.count - 1}）")
        out.append(Frame(anim.src, i % anim.src.frames, anim.props(i)))
    return out


def build_sheet(job, spec, r, where):
    cell = spec["cell"]
    if not (isinstance(cell, list) and len(cell) == 2):
        raise ForgeError(f"{where}: cell 需為 [w, h]")
    cw, ch = cell
    lay = spec.get("layout") or {}
    gap, order = lay.get("gap", 0), lay.get("order", "row")
    cols, rows = lay.get("cols"), lay.get("rows")
    per = spec.get("per")
    cells, missing = [], []
    if per:  # 槽位模式：每個槽位 = 一組動畫的前 per 幀
        names = spec.get("slots") or list(job.anims)
        if not cols:
            raise ForgeError(f"{where}: 槽位模式需 layout.cols")
        bcols = cols // per
        rows = rows or math.ceil(len(names) / bcols)
        if len(names) > bcols * rows:
            raise ForgeError(f"{where}: 槽位 {len(names)} 個超過容量 {bcols * rows}")
        for i, n in enumerate(names):
            bx, by = (i // rows, i % rows) if order == "col" else (i % bcols, i // bcols)
            a = job.anims.get(n)
            if a is None:
                missing.append(n)
                continue
            if a.count < per:
                raise ForgeError(f"anims.{n}: {a.count} 幀 < 槽位需要的 {per} 幀")
            for j, fr in enumerate(anim_frames(a, list(range(per)), where)):
                cells.append((bx * per + j, by, fr))
    else:
        a = job.anim(spec.get("anim", True if len(job.anims) == 1 else None), where)
        frs = anim_frames(a, spec.get("frames"), where) if a else [static_frame(job, spec, where)]
        n = len(frs)
        if not cols:
            cols = math.ceil(n / rows) if rows else n
        rows = rows or math.ceil(n / cols)
        for k, fr in enumerate(frs):
            x, y = (k // rows, k % rows) if order == "col" else (k % cols, k // cols)
            cells.append((x, y, fr))
    W, H = cols * cw + (cols - 1) * gap, rows * ch + (rows - 1) * gap
    sheet = Image.new("RGBA", (W, H))
    for x, y, fr in cells:
        sheet.paste(r.fit(fr, cw, ch, spec, where), (x * (cw + gap), y * (ch + gap)))
    return sheet, len(cells), missing


def static_frame(job, spec, where):
    if spec.get("source"):
        return Frame(job.src(spec["source"], f"{where}.source"))
    if job.source is None:
        if len(job.anims) == 1:
            a = next(iter(job.anims.values()))
            return Frame(a.src, 0, a.props(0))
        raise ForgeError(f"{where}: 無頂層 source，請指定 anim")
    return Frame(job.source)


def _flatten(img, color):
    bg = Image.new("RGBA", img.size, color)
    bg.alpha_composite(img)
    return bg


def _gif_frame(img, matte, colors):
    a = img.getchannel("A")
    rgb = (_flatten(img, matte) if matte else img).convert("RGB")
    p = rgb.quantize(min(colors or 255, 255))
    pal = p.getpalette()[:765]
    p.putpalette(pal + [0] * (768 - len(pal)))
    p.paste(255, mask=a.point(lambda v: 255 if v < 128 else 0))
    return p


def write_output(job, out, i, outdir: Path, r: Renderer):
    spec, where = job.resolve(out, i)
    path = outdir / spec["file"]
    fmt = FMT.get(path.suffix.lower())
    if fmt is None:
        raise ForgeError(f"{where}: 不支援的副檔名 '{path.suffix}'（{' '.join(FMT)}）")
    path.parent.mkdir(parents=True, exist_ok=True)
    missing = []

    if fmt == "svg":
        a = job.anim(spec.get("anim"), where)
        fr = anim_frames(a, spec.get("frames", [0]), where)[0] if a else static_frame(job, spec, where)
        if not isinstance(fr.src, SvgSource):
            raise ForgeError(f"{where}: svg 輸出需 SVG 原圖")
        W, H = target_size(spec.get("size"), fr.src.size, where)
        path.write_text(fr.src.build(fr.props, spec.get("css"), (W, H), exact=False), "utf-8")
        return _ok(path, W, H, fmt, 1), (spec["file"], [])

    if "cell" in spec:
        img, n, missing = build_sheet(job, spec, r, where)
        frames = [img]
    else:
        a = job.anim(spec.get("anim"), where)
        frs = anim_frames(a, spec.get("frames"), where) if a else [static_frame(job, spec, where)]
        W, H = target_size(spec.get("size"), frs[0].src.size, where)
        frames = [r.fit(fr, W, H, spec, where) for fr in frs]
        n = len(frames)
    W, H = frames[0].size

    bg = spec.get("bg", "#ffffff" if fmt == "jpg" else None)
    if bg:
        col = _color(bg, f"{where}.bg")
        frames = [_flatten(f, col) for f in frames]
    colors = spec.get("colors")
    fps = spec.get("fps") or (job.anim(spec.get("anim"), where).fps if spec.get("anim") else 8)
    dur = max(10, round(1000 / fps))

    if len(frames) > 1 and fmt == "jpg":
        raise ForgeError(f"{where}: jpg 不支援多幀（改用 cell 排 sheet，或 gif/webp/apng）")
    if fmt == "gif":
        matte = _color(spec["matte"], f"{where}.matte") if spec.get("matte") else None
        g = [_gif_frame(f, matte, colors) for f in frames]
        g[0].save(path, save_all=True, append_images=g[1:], duration=dur, loop=0,
                  disposal=2, transparency=255, optimize=False)
    else:
        if colors:
            frames = [f.quantize(colors, method=Image.FASTOCTREE) for f in frames]
        kw = {}
        if fmt == "jpg":
            frames = [f.convert("RGB") for f in frames]
            kw["quality"] = spec.get("quality", 90)
        elif fmt == "webp":
            kw.update(quality=spec["quality"]) if "quality" in spec else kw.update(lossless=True)
        if len(frames) > 1:
            kw.update(save_all=True, append_images=frames[1:], duration=dur, loop=0)
        frames[0].save(path, format="PNG" if fmt == "apng" else None, **kw)
    line = _ok(path, W, H, fmt, n)
    if missing:
        line += f" missing:{','.join(missing)}"
    return line, (spec["file"], frames if "cell" not in spec else frames[:1])


def _ok(path, w, h, fmt, n):
    try:
        p = os.path.relpath(path)
    except ValueError:
        p = str(path)
    return f"OK {p.replace(os.sep, '/')} {w}x{h} {fmt} {n}f"


# ---------- 預覽 ----------

def _font(size):
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def preview(items, path: Path, limit=512):
    """items: [(標籤, [影像...])]；每列一個輸出，多幀並排標號。"""
    font = _font(11)
    rows = []
    for label, imgs in items:
        thumbs = []
        for im in imgs:
            im = im.convert("RGBA")
            if im.height < 48:
                f = math.ceil(48 / im.height)
                im = im.resize((im.width * f, im.height * f), Image.NEAREST)
            elif im.height > 160:
                im = im.resize((max(1, round(im.width * 160 / im.height)), 160), Image.LANCZOS)
            thumbs.append(im)
        multi = len(thumbs) > 1
        w = sum(t.width for t in thumbs) + 6 * (len(thumbs) - 1)
        h = max(t.height for t in thumbs) + 14 + (12 if multi else 0)
        row = Image.new("RGBA", (max(w, 60), h))
        d = ImageDraw.Draw(row)
        d.text((0, 0), label, fill=(60, 60, 60, 255), font=font)
        x = 0
        for k, t in enumerate(thumbs):
            row.paste(_checker(t.size), (x, 14))
            row.alpha_composite(t, (x, 14))
            if multi:
                d.text((x, 14 + t.height), str(k), fill=(200, 0, 0, 255), font=font)
            x += t.width + 6
        if row.width > limit:
            row = row.resize((limit, max(1, round(row.height * limit / row.width))), Image.LANCZOS)
        rows.append(row)
    W = max(r.width for r in rows)
    H = sum(r.height for r in rows) + 6 * (len(rows) - 1)
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    y = 0
    for r in rows:
        canvas.alpha_composite(r, (0, y))
        y += r.height + 6
    if H > limit:
        canvas = canvas.resize((max(1, round(W * limit / H)), limit), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(path)


def _checker(size, n=8):
    img = Image.new("RGBA", size, (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, size[1], n):
        for x in range((y // n % 2) * n, size[0], 2 * n):
            d.rectangle([x, y, x + n - 1, y + n - 1], fill=(220, 220, 220, 255))
    return img
