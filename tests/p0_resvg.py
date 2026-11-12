"""P0 實測：resvg-py 點陣化能力。輸出至 <repo>/temp/p0/。"""
import io
import time
from pathlib import Path

import resvg_py
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "temp" / "p0"
OUT.mkdir(parents=True, exist_ok=True)

PET = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<style>.fur{fill:#f08a24}.dark{fill:#1a1a1a}</style>
<defs><radialGradient id="g"><stop offset="0" stop-color="#ffd9a8"/><stop offset="1" stop-color="#f08a24"/></radialGradient></defs>
<g id="body" transform="translate(0,{ty})">
  <g id="tail" transform="rotate({rot} 70 60)"><rect class="fur" x="68" y="40" width="8" height="22" rx="4"/></g>
  <ellipse cx="50" cy="62" rx="24" ry="20" fill="url(#g)"/>
  <circle class="fur" cx="50" cy="38" r="18"/>
  <g id="eye_open" opacity="{eo}"><circle class="dark" cx="43" cy="36" r="3"/><circle class="dark" cx="57" cy="36" r="3"/></g>
  <g id="eye_closed" opacity="{ec}"><rect class="dark" x="40" y="35" width="6" height="2"/><rect class="dark" x="54" y="35" width="6" height="2"/></g>
  <circle cx="50" cy="62" r="6" fill="#fff" fill-opacity="0.5"/>
</g></svg>"""


def fill(t, **kv):
    for k, v in kv.items():
        t = t.replace("{" + k + "}", str(v))
    return t


def render(svg, **kw):
    t = time.perf_counter()
    img = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, **kw))))
    return img, (time.perf_counter() - t) * 1000


def check(name, cond, info=""):
    print(f"{'OK  ' if cond else 'FAIL'} {name} {info}")
    return cond


ok = True
base = fill(PET, ty=0, rot=0, eo=1, ec=0)

# 1. 多尺寸、尺寸精確、透明
for s in (16, 48, 128, 512):
    img, ms = render(base, width=s, height=s)
    img.save(OUT / f"pet_{s}.png")
    ok &= check(f"size {s}", img.size == (s, s) and img.mode == "RGBA", f"{img.size} {img.mode} {ms:.1f}ms")
img, _ = render(base, width=128, height=128)
ok &= check("alpha 角落透明", img.getpixel((0, 0))[3] == 0)
ok &= check("alpha 邊緣抗鋸齒", any(0 < img.getpixel((x, y))[3] < 255 for x in range(128) for y in range(128)))

# 2. 只給寬（等比）、非正方
img, _ = render(base, width=200)
ok &= check("只給寬", img.size == (200, 200), str(img.size))
wide = base.replace('viewBox="0 0 100 100"', 'viewBox="0 0 200 100"')
img, _ = render(wide, width=256, height=128)
ok &= check("非正方 viewBox", img.size == (256, 128), str(img.size))

# 3. 4 幀動畫（巢狀 transform + 軸心 + 顯隱）→ sheet + GIF + WebP
frames = []
for i, (ty, rot, blink) in enumerate([(0, 0, 0), (-2, 15, 0), (0, 0, 0), (2, -15, 1)]):
    svg = fill(PET, ty=ty, rot=rot, eo=1 - blink, ec=blink)
    f, _ = render(svg, width=64, height=64)
    frames.append(f)
sheet = Image.new("RGBA", (256, 64))
for i, f in enumerate(frames):
    sheet.paste(f, (i * 64, 0))
sheet.save(OUT / "pet_sheet.png")
frames[0].save(OUT / "pet.webp", save_all=True, append_images=frames[1:], duration=125, loop=0, lossless=True)
frames[0].save(OUT / "pet.png", save_all=True, append_images=frames[1:], duration=125, loop=0)  # APNG
frames[0].save(OUT / "pet.gif", save_all=True, append_images=frames[1:], duration=125, loop=0, disposal=2)
ok &= check("幀間差異", frames[0].tobytes() != frames[1].tobytes())
ok &= check("APNG 幀數", Image.open(OUT / "pet.png").n_frames == 4)
ok &= check("WebP 幀數", Image.open(OUT / "pet.webp").n_frames == 4)

# 4. crisp_edges（小尺寸）
img, _ = render(base, width=16, height=16, shape_rendering="crisp_edges")
img.save(OUT / "pet_16_crisp.png")
ok &= check("crisp_edges", img.size == (16, 16))

# 5. 背景色（jpg 用）
img, _ = render(base, width=128, height=128, background="#ffffff")
img.convert("RGB").save(OUT / "pet_bg.jpg", quality=90)
ok &= check("background", img.getpixel((0, 0)) == (255, 255, 255, 255), str(img.getpixel((0, 0))))

# 6. CSS 變數支援（設計文件建議用於換色）
var_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><style>:root{--c:#ff0000}</style><rect width="10" height="10" style="fill:var(--c)"/></svg>'
img, _ = render(var_svg, width=10, height=10)
print("INFO CSS var() 支援:", img.getpixel((5, 5))[:3] == (255, 0, 0))  # 結論：不支援，換色改用 class

# 7. 換色：外部 style_sheet 優先序低於內嵌 <style>；需 !important 或追加至內嵌 <style>
BLUE = (0x3a, 0x7b, 0xd5)
img, _ = render(base, width=128, height=128, style_sheet=".fur{fill:#3a7bd5}")
print("INFO style_sheet 無 !important 可覆寫內嵌:", img.getpixel((64, 30))[:3] == BLUE)
img, _ = render(base, width=128, height=128, style_sheet=".fur{fill:#3a7bd5 !important}")
ok &= check("style_sheet !important 換色", img.getpixel((64, 30))[:3] == BLUE)
img, _ = render(base.replace("</style>", ".fur{fill:#3a7bd5}</style>"), width=128, height=128)
img.save(OUT / "pet_recolor.png")
ok &= check("追加內嵌 <style> 換色", img.getpixel((64, 30))[:3] == BLUE)

# 8. 錯誤處理
try:
    render("<svg><broken", width=10)
    ok &= check("無效 SVG 報錯", False)
except Exception as e:
    ok &= check("無效 SVG 報錯", True, f"{type(e).__name__}: {str(e)[:60]}")

# 9. 效能
t = time.perf_counter()
for _ in range(50):
    render(base, width=128, height=128)
print(f"INFO 128px 平均 {(time.perf_counter() - t) * 20:.2f}ms/張")

print("ALL OK" if ok else "HAS FAIL", f"-> {OUT}")
