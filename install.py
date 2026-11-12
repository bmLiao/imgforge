"""將 skill/ 連結至 <Claude 設定目錄>/skills/imgforge。

Claude 設定目錄：$CLAUDE_CONFIG_DIR，未設定則為 ~/.claude。
Windows 建 junction（免管理員權限），其他系統建 symlink。
用法：python install.py [--dry-run] [--uninstall]
"""
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "skill"


def target():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base).expanduser() / "skills" / "imgforge"


def is_link(p: Path):
    return p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())


def main():
    dry, uninstall = "--dry-run" in sys.argv, "--uninstall" in sys.argv
    dst = target()
    if uninstall:
        if not is_link(dst):
            print(f"ERR {dst}: 不是 imgforge 連結，不處理")
            return 1
        if not dry:
            os.rmdir(dst) if os.name == "nt" else dst.unlink()
        print(f"OK removed {dst}")
        return 0
    if dst.exists() or is_link(dst):
        if is_link(dst) and dst.resolve() == SRC:
            print(f"OK 已安裝 {dst} -> {SRC}")
            return 0
        print(f"ERR {dst}: 已存在且非指向本專案，請手動確認後移除")
        return 1
    if not dry:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(SRC)],
                           check=True, capture_output=True)
        else:
            dst.symlink_to(SRC, target_is_directory=True)
    print(f"OK {'(dry-run) ' if dry else ''}{dst} -> {SRC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
