"""job.json 載入與正規化：來源、具名動畫、preset 合併。"""
import json
from pathlib import Path

from . import ForgeError
from .sources import load
from .tracks import evaluate

PRESETS = Path(__file__).resolve().parent.parent / "presets"


def load_presets():
    out = {}
    for f in sorted(PRESETS.glob("*.json")):
        try:
            out.update(json.loads(f.read_text("utf-8")))
        except json.JSONDecodeError as e:
            raise ForgeError(f"presets/{f.name} line {e.lineno}: {e.msg}")
    return out


class Anim:
    def __init__(self, name, spec, src, where):
        self.name, self.src = name, src
        self.count = int(spec.get("count", src.frames))
        if self.count < 1:
            raise ForgeError(f"{where}: count 需 ≥ 1")
        self.fps = spec.get("fps", 8)
        self.tracks = {}
        for gid, props in (spec.get("tracks") or {}).items():
            w = f"{where}.tracks.{gid}"
            if not isinstance(props, dict):
                raise ForgeError(f"{w}: 需為物件")
            pivot = props.get("pivot")
            vals = {k: evaluate(v, k, self.count, w) for k, v in props.items() if k != "pivot"}
            self.tracks[gid] = (pivot, vals)

    def props(self, i):
        out = {}
        for gid, (pivot, vals) in self.tracks.items():
            p = {k: v[i] for k, v in vals.items()}
            if pivot is not None:
                p["pivot"] = pivot
            out[gid] = p
        return out


class Job:
    def __init__(self, data: dict, base: Path, name: str):
        self.base = base
        self._src = {}
        self.source = self.src(data["source"], "source") if data.get("source") else None
        self.name = data.get("name") or (Path(data["source"]).stem if data.get("source") else name)
        anims = dict(data.get("anims") or {})
        if "frames" in data:
            anims.setdefault("default", data["frames"])
        self.anims = {}
        for n, spec in anims.items():
            w = f"anims.{n}"
            if spec.get("source"):
                src = self.src(spec["source"], f"{w}.source")
            elif self.source:
                src = self.source
            else:
                raise ForgeError(f"{w}: 缺少 source")
            self.anims[n] = Anim(n, spec, src, w)
        self.outputs = data.get("outputs")
        if not self.outputs:
            raise ForgeError("job: 缺少 outputs")
        self.presets = None

    def src(self, rel, where):
        p = (self.base / rel).resolve()
        if p not in self._src:
            try:
                self._src[p] = load(p)
            except ForgeError as e:
                raise ForgeError(f"{where}: {e}") from None
        return self._src[p]

    def anim(self, ref, where):
        """ref: 名稱 / True（唯一動畫）/ None。"""
        if ref in (None, False):
            return None
        if ref is True:
            if len(self.anims) != 1:
                raise ForgeError(f"{where}: anim:true 需剛好一組動畫，請改寫名稱（{' '.join(self.anims)}）")
            return next(iter(self.anims.values()))
        if ref not in self.anims:
            raise ForgeError(f"{where}: 無動畫 '{ref}'（現有：{' '.join(self.anims) or '無'}）")
        return self.anims[ref]

    def resolve(self, out, i):
        """合併 preset，回傳完整輸出設定。"""
        where = f"outputs[{i}]"
        spec = dict(out)
        if "preset" in spec:
            if self.presets is None:
                self.presets = load_presets()
            pr = self.presets.get(spec["preset"])
            if pr is None:
                raise ForgeError(f"{where}: 無 preset '{spec['preset']}'（見 presets 指令）")
            spec = {**pr, **spec}
            if "layout" in pr and "layout" in out:
                spec["layout"] = {**pr["layout"], **out["layout"]}
        if "file" not in spec:
            raise ForgeError(f"{where}: 缺少 file")
        spec["file"] = spec["file"].replace("{name}", self.name)
        return spec, where


def load_job(path: Path) -> Job:
    try:
        data = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        raise ForgeError(f"{path.name} line {e.lineno}: {e.msg}")
    except OSError as e:
        raise ForgeError(f"{path}: {e.strerror}")
    return Job(data, path.parent, path.stem)
