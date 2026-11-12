"""SVG 點陣化後端：resvg-py → cairosvg → ImageMagick。"""
import io
import shutil
import subprocess

from PIL import Image

from . import ForgeError

_picked = None


def backends():
    found = []
    try:
        import resvg_py  # noqa: F401
        found.append("resvg-py")
    except ImportError:
        pass
    try:
        import cairosvg  # noqa: F401
        found.append("cairosvg")
    except (ImportError, OSError):
        pass
    if shutil.which("magick"):
        found.append("magick")
    return found


def _backend():
    global _picked
    if _picked is None:
        found = backends()
        if not found:
            raise ForgeError("svg: 無可用點陣化後端（pip install resvg-py）")
        _picked = found[0]
    return _picked


def rasterize(svg: str, w: int, h: int, crisp: bool = False) -> Image.Image:
    """svg 根節點須已設 width/height=w/h 與 preserveAspectRatio=none。"""
    b = _backend()
    try:
        if b == "resvg-py":
            import resvg_py
            kw = {"shape_rendering": "crisp_edges"} if crisp else {}
            data = bytes(resvg_py.svg_to_bytes(svg_string=svg, **kw))
        elif b == "cairosvg":
            import cairosvg
            data = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
        else:
            data = subprocess.run(
                ["magick", "-background", "none", "svg:-", "png:-"],
                input=svg.encode("utf-8"), capture_output=True, check=True).stdout
    except Exception as e:  # 後端錯誤統一轉為一行訊息
        raise ForgeError(f"svg render ({b}): {str(e).strip()[:160]}")
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    if img.size != (w, h):
        img = img.resize((w, h), Image.LANCZOS)
    return img
