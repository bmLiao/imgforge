"""軌道求值：陣列 / 常數 / wave / keys。"""
import math

from . import ForgeError

NUM = {"tx", "ty", "rot", "sx", "sy", "s", "opacity"}
STEP = {"hide", "fill"}
BASE1 = {"sx", "sy", "s", "opacity"}
EASE = {
    "linear": lambda t: t,
    "in": lambda t: t * t,
    "out": lambda t: 1 - (1 - t) ** 2,
    "inOut": lambda t: t * t * (3 - 2 * t),
}


def evaluate(spec, prop, n, where):
    """回傳長度 n 的逐幀值。"""
    w = f"{where}.{prop}"
    if prop not in NUM | STEP:
        raise ForgeError(f"{w}: 未知屬性（可用 {' '.join(sorted(NUM | STEP))}）")
    if isinstance(spec, list):
        if len(spec) != n:
            raise ForgeError(f"{w}: 長度 {len(spec)} != count {n}")
        return spec
    if not isinstance(spec, dict):
        return [spec] * n
    if "wave" in spec:
        if prop in STEP:
            raise ForgeError(f"{w}: 不可用 wave")
        a, ph = spec["wave"], spec.get("phase", 0)
        base = spec.get("base", 1 if prop in BASE1 else 0)
        return [base + a * math.sin(2 * math.pi * (i / n + ph)) for i in range(n)]
    if "keys" in spec:
        return _keys(spec, prop, n, w)
    raise ForgeError(f"{w}: 物件需含 wave 或 keys")


def _keys(spec, prop, n, w):
    try:
        keys = sorted((int(k), v) for k, v in spec["keys"].items())
    except (ValueError, AttributeError):
        raise ForgeError(f'{w}: keys 格式為 {{"幀號": 值}}')
    if not keys:
        raise ForgeError(f"{w}: keys 為空")
    for k, _ in keys:
        if not 0 <= k < n:
            raise ForgeError(f"{w}: 關鍵幀 {k} 超出 0..{n - 1}")
    ease = EASE.get(spec.get("ease", "linear"))
    if ease is None:
        raise ForgeError(f"{w}: ease 只能是 {'/'.join(EASE)}")
    loop = spec.get("loop", True)
    pts = keys + ([(keys[0][0] + n, keys[0][1])] if loop else [])
    out = []
    for i in range(n):
        x = i + n if loop and i < keys[0][0] else i
        prev = max((p for p in pts if p[0] <= x), default=None, key=lambda p: p[0])
        nxt = min((p for p in pts if p[0] > x), default=None, key=lambda p: p[0])
        if prev is None:
            out.append(keys[0][1])
        elif nxt is None or prop in STEP:
            out.append(prev[1])
        else:
            t = ease((x - prev[0]) / (nxt[0] - prev[0]))
            out.append(prev[1] + (nxt[1] - prev[1]) * t)
    return out
