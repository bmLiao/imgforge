"""imgforge CLI：render / quick / check / presets。"""
import argparse
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import ForgeError  # noqa: E402


def cmd_render(a):
    from core.job import load_job
    from core.output import Renderer, preview, write_output
    job_path = Path(a.job)
    job = load_job(job_path)
    outdir = Path(a.out) if a.out else job_path.parent / "out"
    r, items = Renderer(), {}
    for i, out in enumerate(job.outputs):
        line, (label, imgs) = write_output(job, out, i, outdir, r)
        print(line)
        if imgs:  # 內容相同的輸出合併成一列，省預覽 token
            key = hash(tuple((im.size, im.tobytes()) for im in imgs))
            items[key] = (items[key][0] + ", " + label, imgs) if key in items else (label, imgs)
    if not a.no_preview and items:
        p = outdir / "_preview.png"
        preview(list(items.values()), p)
        print(f"PREVIEW {os.path.relpath(p).replace(os.sep, '/')}")


def cmd_quick(a):
    from core.job import Job
    from core.output import Renderer, write_output
    src = Path(a.src)
    sizes = [None] if not a.size else [
        [int(v) if v else None for v in s.split("x")] if "x" in s else [int(s), None]
        for s in a.size.split(",")]
    outs = []
    for s in sizes:
        tag = "x".join(str(v) for v in s if v) if s else ""
        o = {"file": a.output.replace("{s}", tag), "fit": a.fit}
        if s:
            o["size"] = s
        if a.bg:
            o["bg"] = a.bg
        outs.append(o)
    if len(outs) > 1 and "{s}" not in a.output:
        raise ForgeError("quick: 多尺寸時 -o 需含 {s}，例 icon_{s}.png")
    job = Job({"source": src.name, "outputs": outs}, src.parent.resolve(), src.stem)
    r = Renderer()
    for i, o in enumerate(outs):
        print(write_output(job, o, i, Path.cwd(), r)[0])


def cmd_check(a):
    from core.raster import backends
    if not a.file:
        b = backends()
        from core.ops import available
        from core.sources import LIB
        print(f"backends: {' '.join(b) if b else '無（SVG 不可用；pip install resvg-py）'}")
        print(f"ops: {' '.join(sorted(available()))}")
        print(f"lib: {' '.join(sorted(f.stem for f in LIB.glob('*.svg'))) or '-'}")
        return
    p = Path(a.file)
    if p.suffix.lower() == ".json":
        from core.job import load_job
        job = load_job(p)
        for i, o in enumerate(job.outputs):
            job.resolve(o, i)
        print(f"OK {p.name} anims={','.join(job.anims) or '-'} outputs={len(job.outputs)}")
        return
    from core.sources import SvgSource, load
    s = load(p.resolve())
    w, h = s.size
    extra = f" ids={','.join(s.ids)}" if isinstance(s, SvgSource) else ""
    print(f"OK {p.name} {w:g}x{h:g} {s.frames}f{extra}")


def cmd_presets(a):
    from core.job import load_presets
    for n, p in load_presets().items():
        print(f"{n}: {p.get('desc', '')}")


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="imgforge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("render", help="依 job.json 產出")
    p.add_argument("job")
    p.add_argument("-o", "--out", help="輸出目錄（預設 job 旁的 out/）")
    p.add_argument("--no-preview", action="store_true")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("quick", help="單圖免寫 job")
    p.add_argument("src")
    p.add_argument("-s", "--size", help="128 / 128x64 / 16,32,64（等比填一邊）")
    p.add_argument("-o", "--output", required=True, help="輸出檔；多尺寸用 {s}")
    p.add_argument("--fit", default="contain")
    p.add_argument("--bg")
    p.set_defaults(fn=cmd_quick)
    p = sub.add_parser("check", help="驗證原圖或 job；無參數列出後端")
    p.add_argument("file", nargs="?")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("presets", help="列出預設規格")
    p.set_defaults(fn=cmd_presets)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except ForgeError as e:
        print(f"ERR {e}", file=sys.stderr)
        return 1
    except Exception as e:  # 非預期錯誤：一行原因 + 位置
        tb = traceback.extract_tb(e.__traceback__)[-1]
        print(f"ERR {type(e).__name__}: {e} @ {Path(tb.filename).name}:{tb.lineno}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
