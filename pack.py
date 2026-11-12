"""打包 skill/ 為 claude.ai 可上傳的 zip：dist/imgforge.zip（內含 imgforge/ 資料夾）。"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC, OUT = ROOT / "skill", ROOT / "dist" / "imgforge.zip"


def main():
    OUT.parent.mkdir(exist_ok=True)
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(SRC.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                z.write(f, Path("imgforge") / f.relative_to(SRC))
                n += 1
    print(f"OK {OUT.relative_to(ROOT).as_posix()} {n} files {OUT.stat().st_size // 1024}KB")


if __name__ == "__main__":
    sys.exit(main())
