"""原圖載入：SVG / .pix / 點陣圖。各來源提供 size、frames、render()。"""
import copy
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageColor, ImageSequence

from . import ForgeError
from .raster import rasterize

NS = "http://www.w3.org/2000/svg"
XL = "http://www.w3.org/1999/xlink"
ET.register_namespace("", NS)
ET.register_namespace("xlink", XL)
LIB = Path(__file__).resolve().parent.parent / "library"
RASTER_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def q(tag):
    return f"{{{NS}}}{tag}"


def num(v):
    return f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def load(path: Path):
    if not path.exists():
        raise ForgeError(f"{path}: 檔案不存在")
    ext = path.suffix.lower()
    if ext == ".svg":
        return SvgSource(path)
    if ext == ".pix":
        return PixSource(path)
    if ext in RASTER_EXT:
        return RasterSource(path)
    raise ForgeError(f"{path.name}: 不支援的原圖格式（svg/pix/png/jpg/gif/webp）")


# ---------- SVG ----------

class SvgSource:
    pixel = False

    def __init__(self, path: Path):
        self.name = path.name
        try:
            self.root = ET.parse(path).getroot()
        except ET.ParseError as e:
            raise ForgeError(f"{path.name}: XML 錯誤 {e}")
        if self.root.tag != q("svg"):
            raise ForgeError(f"{path.name}: 根節點須為 <svg xmlns=\"{NS}\">")
        self._expand_lib()
        self.vb = self._viewbox()
        self.size = (self.vb[2], self.vb[3])
        self.frames = 1
        self.ids = [el.get("id") for el in self.root.iter() if el.get("id")]

    def _viewbox(self):
        vb = self.root.get("viewBox")
        if vb:
            try:
                x, y, w, h = (float(v) for v in re.split(r"[\s,]+", vb.strip()))
                if w > 0 and h > 0:
                    return x, y, w, h
            except ValueError:
                pass
            raise ForgeError(f"{self.name}: viewBox 格式錯誤 '{vb}'")
        try:
            w, h = (float(re.sub(r"px$", "", self.root.get(k, ""))) for k in ("width", "height"))
            return 0.0, 0.0, w, h
        except ValueError:
            raise ForgeError(f"{self.name}: 需要 viewBox 或數值 width/height")

    def _expand_lib(self):
        for parent in list(self.root.iter()):
            for i, ch in enumerate(list(parent)):
                href = ch.get("href") or ch.get(f"{{{XL}}}href") or ""
                if ch.tag != q("use") or not href.startswith("lib:"):
                    continue
                f = LIB / f"{href[4:]}.svg"
                if not f.exists():
                    raise ForgeError(f"{self.name}: 找不到部件 {href}（{f}）")
                part = ET.parse(f).getroot()
                skip = {"href", f"{{{XL}}}href", "x", "y", "width", "height", "transform"}
                g = ET.Element(q("g"), {k: v for k, v in ch.attrib.items() if k not in skip})
                x, y = ch.get("x", "0"), ch.get("y", "0")
                tr = " ".join(t for t in (ch.get("transform", ""),
                                          f"translate({x} {y})" if (x, y) != ("0", "0") else "") if t)
                if tr:
                    g.set("transform", tr)
                g.extend(list(part))
                parent.remove(ch)
                parent.insert(i, g)

    def build(self, props, css=None, size=None, exact=True):
        """套用當幀屬性，回傳 SVG 字串。size=(w,h) 時改寫根節點尺寸；exact 時不保持比例（精確填滿）。"""
        root = copy.deepcopy(self.root)
        idmap = {el.get("id"): el for el in root.iter() if el.get("id")}
        rules = []
        for gid, p in props.items():
            if gid == "*":
                el = ET.Element(q("g"))
                keep = (q("defs"), q("style"))
                for ch in [c for c in root if c.tag not in keep]:
                    root.remove(ch)
                    el.append(ch)
                root.append(el)
                p.setdefault("pivot", [self.vb[0] + self.vb[2] / 2, self.vb[1] + self.vb[3] / 2])
                sel = "svg *"
            else:
                el = idmap.get(gid)
                if el is None:
                    raise ForgeError(f"{self.name}: 找不到 id '{gid}'（現有：{' '.join(self.ids[:12])}）")
                sel = f"#{gid}, #{gid} *"
            _apply(el, p, gid)
            if p.get("fill"):
                rules.append(f"{sel}{{fill:{p['fill']} !important}}")
        if css:
            rules.insert(0, css)
        if rules:
            st = root.find(f".//{q('style')}")
            if st is None:
                st = ET.Element(q("style"))
                root.insert(0, st)
            st.text = (st.text or "") + "\n" + "\n".join(rules)
        if size:
            root.set("width", str(size[0]))
            root.set("height", str(size[1]))
            if exact:
                root.set("preserveAspectRatio", "none")
            if not self.root.get("viewBox"):
                root.set("viewBox", " ".join(num(v) for v in self.vb))
        return ET.tostring(root, encoding="unicode")

    def render(self, idx, props, w, h, css=None, crisp=False, resample=None, pal=None):
        if pal:
            raise ForgeError(f"{self.name}: palette 只適用 .pix（SVG 換色用 css）")
        return rasterize(self.build(props, css, (w, h)), w, h, crisp)


def _apply(el, p, gid):
    parts = []
    tx, ty = p.get("tx", 0), p.get("ty", 0)
    if tx or ty:
        parts.append(f"translate({num(tx)} {num(ty)})")
    rot = p.get("rot", 0)
    sx, sy = p.get("sx", p.get("s", 1)), p.get("sy", p.get("s", 1))
    if rot or sx != 1 or sy != 1:
        if "pivot" not in p:
            raise ForgeError(f"track {gid}: rot/sx/sy 需要 pivot")
        px, py = p["pivot"]
        if rot:
            parts.append(f"rotate({num(rot)} {num(px)} {num(py)})")
        if sx != 1 or sy != 1:
            parts.append(f"translate({num(px)} {num(py)}) scale({num(sx)} {num(sy)}) "
                         f"translate({num(-px)} {num(-py)})")
    if parts:
        el.set("transform", (el.get("transform", "") + " " + " ".join(parts)).strip())
    if "opacity" in p:
        el.set("opacity", num(float(el.get("opacity", 1)) * p["opacity"]))
    if "hide" in p:
        if p["hide"]:
            el.set("display", "none")
        else:
            el.attrib.pop("display", None)
            if "display" in el.get("style", ""):
                el.set("style", re.sub(r"display\s*:\s*none\s*;?", "", el.get("style")))


# ---------- 整張影像變換（.pix / 點陣圖） ----------

def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def transform_image(img, p, nearest):
    if not p:
        return img
    if p.get("hide"):
        return Image.new("RGBA", img.size)
    tx, ty, rot = p.get("tx", 0), p.get("ty", 0), p.get("rot", 0)
    sx, sy = p.get("sx", p.get("s", 1)), p.get("sy", p.get("s", 1))
    if tx or ty or rot or sx != 1 or sy != 1:
        px, py = p.get("pivot", (img.width / 2, img.height / 2))
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        T = lambda x, y: [[1, 0, x], [0, 1, y], [0, 0, 1]]  # noqa: E731
        # 逆映射：輸出 → 輸入 = T(piv) S⁻¹ R⁻¹ T(-piv) T(-t)
        m = T(px, py)
        m = _mul(m, [[1 / sx, 0, 0], [0, 1 / sy, 0], [0, 0, 1]])
        m = _mul(m, [[c, s, 0], [-s, c, 0], [0, 0, 1]])
        m = _mul(m, T(-px - tx, -py - ty))
        img = img.transform(img.size, Image.AFFINE, (*m[0], *m[1]),
                            Image.NEAREST if nearest else Image.BICUBIC)
    if "opacity" in p:
        a = img.getchannel("A").point(lambda v: round(v * p["opacity"]))
        img = img.copy()
        img.putalpha(a)
    return img


class _BitmapSource:
    pixel = False

    def frame(self, idx, pal=None):
        if pal:
            raise ForgeError(f"{self.name}: palette 只適用 .pix")
        return self.images[idx % self.frames]

    def render(self, idx, props, w, h, css=None, crisp=False, resample=None, pal=None):
        img = self.frame(idx, pal)
        bad = [k for k in props if k != "*"]
        if bad:
            raise ForgeError(f"{self.name}: 點陣來源只支援 '*' 軌道（收到 {bad[0]}）")
        img = transform_image(img, props.get("*"), self.pixel)
        if img.size != (w, h):
            rs = resample if resample is not None else (Image.NEAREST if self.pixel else Image.LANCZOS)
            img = img.resize((w, h), rs)
        return img


# ---------- .pix ----------

class PixSource(_BitmapSource):
    pixel = True

    def __init__(self, path: Path):
        self.name = path.name
        lines = path.read_text("utf-8").splitlines()
        head, i = {}, 0
        while i < len(lines) and not lines[i].startswith("---"):
            ln = re.sub(r"\s+#(\s.*)?$", "", lines[i]).strip()
            if ln:
                k, sep, v = ln.partition(":")
                if not sep:
                    raise ForgeError(f"{self.name} line {i + 1}: 需為 key: value")
                head[k.strip()] = v.strip()
            i += 1
        m = re.fullmatch(r"(\d+)x(\d+)", head.get("size", ""))
        if not m:
            raise ForgeError(f"{self.name}: 缺少 size: WxH")
        W, H = int(m[1]), int(m[2])
        pal = {}
        for tok in head.get("palette", "").split():
            ch, sep, col = tok.partition("=")
            if len(ch) != 1 or not sep:
                raise ForgeError(f"{self.name}: palette 項目 '{tok}' 需為 單字元=顏色")
            pal[ch] = _color(col, f"{self.name} palette {ch}")
        if not pal:
            raise ForgeError(f"{self.name}: 缺少 palette")
        mir = head.get("mirror", "")
        if mir not in ("", "x", "y", "xy"):
            raise ForgeError(f"{self.name}: mirror 只能是 x / y / xy")
        rw = math.ceil(W / 2) if "x" in mir else W
        rh = math.ceil(H / 2) if "y" in mir else H

        blocks = []
        for n in range(i, len(lines)):
            ln = lines[n].rstrip()
            if ln.startswith("---"):
                blocks.append([])
            elif ln:
                blocks[-1].append((n + 1, ln))
        if not blocks or not any(blocks):
            raise ForgeError(f"{self.name}: '---' 後沒有像素列")
        self.images, self.grids, self.pal = [], [], pal
        for bi, rows in enumerate(blocks):
            if len(rows) != rh:
                at = rows[-1][0] if rows else "?"
                raise ForgeError(f"{self.name} frame {bi} (line {at}): 行數 {len(rows)} != {rh}")
            grid = []
            for n, row in rows:
                if len(row) != rw:
                    raise ForgeError(f"{self.name} line {n}: 長度 {len(row)} != {rw}")
                bad = next((c for c in row if c not in pal), None)
                if bad:
                    raise ForgeError(f"{self.name} line {n}: 未定義字元 '{bad}'")
                grid.append(row + row[:W // 2][::-1] if "x" in mir else row)
            if "y" in mir:
                grid = grid + grid[:H // 2][::-1]
            self.grids.append(grid)
            self.images.append(self._paint(grid, pal))
        self.frames = len(self.images)
        self.size = (W, H)

    def _paint(self, grid, pal):
        img = Image.new("RGBA", (len(grid[0]), len(grid)))
        img.putdata([pal[c] for row in grid for c in row])
        return img

    def frame(self, idx, pal=None):
        """pal：{字元: 顏色} 覆寫調色盤（僅限原檔已定義的字元）。"""
        if not pal:
            return self.images[idx % self.frames]
        bad = next((c for c in pal if c not in self.pal), None)
        if bad:
            raise ForgeError(f"{self.name}: palette 覆寫字元 '{bad}' 未在原檔定義")
        new = {**self.pal, **{c: _color(v, f"{self.name} palette {c}") for c, v in pal.items()}}
        return self._paint(self.grids[idx % self.frames], new)


def _color(s, where):
    if s in ("transparent", "none"):
        return (0, 0, 0, 0)
    try:
        return ImageColor.getcolor(s, "RGBA")
    except ValueError:
        raise ForgeError(f"{where}: 無效顏色 '{s}'")


# ---------- PNG / JPG / GIF ----------

class RasterSource(_BitmapSource):
    def __init__(self, path: Path):
        self.name = path.name
        try:
            with Image.open(path) as im:
                self.images = [f.convert("RGBA") for f in ImageSequence.Iterator(im)]
        except OSError as e:
            raise ForgeError(f"{path.name}: 無法讀取 {e}")
        self.frames = len(self.images)
        self.size = self.images[0].size
