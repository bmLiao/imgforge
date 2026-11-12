"""內建後處理：sharpen、outline、shadow、center。"""
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


@register("center")
def center(img, axis="xy", step=1, dx=0, dy=0):
    """依不透明像素範圍置中，再偏移 (dx, dy)（輸出像素）。靜態圖示用；動畫逐格置中會抖動。
    step：位移取倍數，像素風放大 N 倍時填 N 保持格線。"""
    if axis not in ("x", "y", "xy"):
        raise TypeError("axis 只能是 x / y / xy")
    box = img.getchannel("A").getbbox()
    if not box:
        return img
    l, t, r, b = box
    mx = (img.width - (r - l)) // 2 - l if "x" in axis else 0
    my = (img.height - (b - t)) // 2 - t if "y" in axis else 0
    dx, dy = mx // step * step + dx, my // step * step + dy  # 無法整除時偏上/左
    if not (dx or dy):
        return img
    out = Image.new("RGBA", img.size)
    out.paste(img, (dx, dy))
    return out
