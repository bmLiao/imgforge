"""imgforge 測試。執行：python -m unittest discover tests；輸出至 <repo>/temp/test/。"""
import contextlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skill"))
import imgforge  # noqa: E402
from core.tracks import evaluate  # noqa: E402

TMP = ROOT / "temp" / "test"
EX = ROOT / "skill" / "examples"


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = imgforge.main([str(a) for a in args])
    return code, out.getvalue() + err.getvalue()


def write(name, text):
    p = TMP / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if isinstance(text, str) else json.dumps(text), "utf-8")
    return p


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TMP.mkdir(parents=True, exist_ok=True)
        shutil.copy(EX / "pet.svg", TMP / "pet.svg")

    def render(self, job, name="job.json"):
        code, out = run("render", write(name, job), "-o", TMP / "out", "--no-preview")
        return code, out


class TestExamples(Base):
    def test_examples(self):
        for j in ("pet.json", "slime.json"):
            code, out = run("render", EX / j, "-o", TMP / "ex" / j)
            self.assertEqual(code, 0, out)
            self.assertIn("PREVIEW", out)
        im = Image.open(TMP / "ex" / "pet.json" / "pet.gif")
        self.assertEqual(im.n_frames, 4)
        self.assertEqual(Image.open(TMP / "ex" / "pet.json" / "pet.jpg").getpixel((0, 0)), (255, 255, 255))


class TestTracks(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(evaluate(3, "tx", 2, "t"), [3, 3])
        w = evaluate({"wave": 2}, "ty", 4, "t")
        self.assertAlmostEqual(w[1], 2)
        self.assertAlmostEqual(w[3], -2)
        self.assertAlmostEqual(evaluate({"wave": 0.1}, "sx", 4, "t")[1], 1.1)
        self.assertEqual(evaluate({"keys": {"0": 0, "2": 10}}, "rot", 4, "t"), [0, 5, 10, 5])
        self.assertEqual(evaluate({"keys": {"0": False, "2": True}}, "hide", 4, "t"), [False, False, True, True])


class TestOutputs(Base):
    def test_fit_and_sizes(self):
        wide = (TMP / "pet.svg").read_text("utf-8").replace('viewBox="0 0 100 100"', 'viewBox="0 0 200 100"')
        write("wide.svg", wide)
        code, out = self.render({"source": "wide.svg", "outputs": [
            {"file": "c.png", "size": [100, 100], "fit": "contain"},
            {"file": "v.png", "size": [100, 100], "fit": "cover"},
            {"file": "s.png", "size": [100, 100], "fit": "stretch"},
            {"file": "p.png", "size": [300, 300], "fit": "pad"},
            {"file": "h.png", "size": [None, 50]},
        ]})
        self.assertEqual(code, 0, out)
        self.assertIn("h.png 100x50", out)
        c = Image.open(TMP / "out" / "c.png")
        self.assertEqual(c.getpixel((50, 5))[3], 0)  # contain 上方留白

    def test_mv_slots(self):
        job = {"source": "pet.svg", "anims": {}, "outputs": [
            {"preset": "mv-character-single"}, {"preset": "mv-sv-actor"}, {"preset": "mv-faces"}]}
        for d in ("down", "left", "right", "up", "walk"):
            job["anims"][d] = {"count": 3, "tracks": {"body": {"tx": [-3, 0, 3]}}}
        code, out = self.render(job)
        self.assertEqual(code, 0, out)
        self.assertIn("$pet.png 144x192 png 12f", out)
        self.assertIn("pet_sv.png 576x384 png 3f missing:wait", out)
        self.assertIn("pet_faces.png 576x288 png 5f", out)

    def test_pix_animation_tracks(self):
        code, out = self.render({"source": str(EX / "slime.pix"), "anims": {
            "hop": {"count": 4, "tracks": {"*": {"ty": [0, -2, 0, 0]}}}},
            "outputs": [{"file": "hop.png", "anim": "hop", "cell": [24, 24]}]})
        self.assertEqual(code, 0, out)
        self.assertIn("96x24 png 4f", out)

    def test_quick(self):
        code, out = run("quick", TMP / "pet.svg", "-s", "16,32", "-o", TMP / "q" / "icon_{s}.png")
        self.assertEqual(code, 0, out)
        self.assertEqual(Image.open(TMP / "q" / "icon_32.png").size, (32, 32))


class TestErrors(Base):
    def err(self, job, expect, name="job.json"):
        code, out = self.render(job, name)
        self.assertEqual(code, 1, out)
        self.assertIn(expect, out)
        self.assertEqual(out.count("\n"), 1, out)  # 錯誤只一行

    def test_pix_errors(self):
        write("bad.pix", "size: 4x2\npalette: .=transparent k=#000\n---\n....\n..k\n")
        self.err({"source": "bad.pix", "outputs": [{"file": "a.png"}]}, "bad.pix line 5: 長度 3 != 4")
        write("bad2.pix", "size: 4x1\npalette: .=transparent\n---\n..z.\n")
        self.err({"source": "bad2.pix", "outputs": [{"file": "a.png"}]}, "未定義字元 'z'")

    def test_track_errors(self):
        base = {"source": "pet.svg", "outputs": [{"file": "a.gif", "anim": "a"}]}
        self.err({**base, "anims": {"a": {"count": 2, "tracks": {"nope": {"tx": 1}}}}}, "找不到 id 'nope'")
        self.err({**base, "anims": {"a": {"count": 2, "tracks": {"tail": {"rot": 5}}}}}, "需要 pivot")
        self.err({**base, "anims": {"a": {"count": 3, "tracks": {"body": {"tx": [1, 2]}}}}}, "長度 2 != count 3")
        self.err({**base, "anims": {"a": {"count": 2, "tracks": {"body": {"hide": {"wave": 1}}}}}}, "不可用 wave")

    def test_job_errors(self):
        self.err('{"source": "pet.svg",\n "outputs": [}', "job.json line 2", name="job.json")
        self.err({"source": "pet.svg", "outputs": [{"preset": "nope"}]}, "無 preset 'nope'")
        self.err({"source": "pet.svg", "outputs": [{"file": "a.jpg", "anim": "x"}]}, "無動畫 'x'")


if __name__ == "__main__":
    unittest.main()
