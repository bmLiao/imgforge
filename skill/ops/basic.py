"""內建後處理：sharpen、outline、shadow。"""
from PIL import Image, ImageColor, ImageFilter

from core.ops import register


@register("sharpen")
def sharpen(img, amount=120, radius=1):
    """銳化（小尺寸縮圖後補細節）。amount 為百分比。"""
    rgb = img.convert("RGB").filter(ImageFilter.UnsharpMask(radius, amount, 0))
    rgb.putalpha(img.getchannel("A"))
    return rgb


@register("outline")
def outline(img, color="#1a1a1a", width=1):
    """沿不透明區外圍描邊（遊戲 sprite 常用）。"""
    a = img.getchannel("A").point(lambda v: 255 if v > 0 else 0)
    grown = a.filter(ImageFilter.MaxFilter(width * 2 + 1))
    out = Image.new("RGBA", img.size, ImageColor.getcolor(color, "RGBA"))
    out.putalpha(grown)
    out.alpha_composite(img)
    return out


@register("shadow")
def shadow(img, dx=2, dy=2, color="#00000066", blur=0):
    """投影：偏移 (dx, dy)，可模糊。"""
    sh = Image.new("RGBA", img.size, ImageColor.getcolor(color, "RGBA"))
    a = img.getchannel("A").point(lambda v, k=sh.getpixel((0, 0))[3]: v * k // 255)
    sh.putalpha(a)
    if blur:
        sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", img.size)
    out.paste(sh, (dx, dy))
    out.alpha_composite(img)
    return out
