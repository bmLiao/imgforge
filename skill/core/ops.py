"""後處理操作註冊：skill/ops/*.py 以 @register("名稱") 註冊 fn(img, **參數) -> img。"""
import importlib.util
from pathlib import Path

from . import ForgeError

OPS_DIR = Path(__file__).resolve().parent.parent / "ops"
_ops = {}
_loaded = False


def register(name):
    def deco(fn):
        _ops[name] = fn
        return fn
    return deco


def available():
    _load()
    return _ops


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    for f in sorted(OPS_DIR.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"imgforge_ops_{f.stem}", f)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))


def apply(img, ops, where):
    """ops: ["sharpen", {"op": "outline", "color": "#000"}]"""
    if not ops:
        return img
    _load()
    for o in ops:
        o = {"op": o} if isinstance(o, str) else dict(o)
        name = o.pop("op", None)
        fn = _ops.get(name)
        if fn is None:
            raise ForgeError(f"{where}.ops: 無操作 '{name}'（可用 {' '.join(sorted(_ops))}）")
        try:
            img = fn(img, **o)
        except TypeError as e:
            raise ForgeError(f"{where}.ops.{name}: 參數錯誤 {e}")
    return img
