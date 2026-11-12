# imgforge

讓 Claude 以最低 token 產出**正確尺寸、格式、動畫幀**的點陣圖。

Claude 只寫一次與尺寸無關的原圖（SVG 或像素格式 `.pix`）加一份 `job.json`；點陣化、縮放、排列、換色、轉檔全交給 Python。同一份原圖可重複輸出任意規格，改規格不必重畫。

<p>
  <img src="docs/img/pet.gif" width="96" alt="待機動畫">
  <img src="docs/img/pet_sheet.png" height="64" alt="sprite sheet">
</p>
<img src="docs/img/iconset.png" alt="RPG Maker MV IconSet">

## 功能

- **輸出**：PNG / JPG / WebP / GIF / APNG / SVG；多尺寸、`contain` / `cover` / `stretch` / `pad`。
- **動畫**：以軌道（位移、旋轉、縮放、透明度、顯示隱藏）描述動作，不逐幀重畫；`wave`、關鍵幀與緩動。
- **sprite sheet**：格子、欄列、間距、留空、槽位（依動畫名稱排位）。
- **換色**：SVG 用 `css`、`.pix` 用 `palette`，可只套指定幀；同造型多色免重畫。
- **後處理 ops**：`sharpen`、`outline`、`shadow`、`center`（依實際像素置中，可偏移），可只套指定幀。
- **presets**：`icon-*`、RPG Maker MV（行走圖、SV 戰鬥圖、臉圖、IconSet、敵人）。
- **自查**：每次輸出一張精簡預覽 `_preview.png`，可換深色底檢查。

## 需求

- Python 3.10+
- [Pillow](https://pypi.org/project/pillow/)
- SVG 點陣化後端（擇一）：[resvg-py](https://pypi.org/project/resvg-py/)（首選）、ImageMagick、cairosvg

```bash
pip install pillow resvg-py
```

只用 `.pix` / PNG 原圖時不需 SVG 後端。

## 安裝為 Claude skill

```bash
python install.py            # 連結 skill/ → <Claude 設定目錄>/skills/imgforge
python install.py --dry-run  # 只顯示會做什麼
python install.py --uninstall
```

Claude 設定目錄為 `$CLAUDE_CONFIG_DIR`，未設定則為 `~/.claude`。Windows 建 junction（免管理員權限），其他系統建 symlink。安裝後在 Claude Code 中直接描述要的圖即可，Claude 會依 [skill/SKILL.md](skill/SKILL.md) 使用本工具。

## 直接使用 CLI

```bash
python skill/imgforge.py check                    # 後端、ops、部件庫
python skill/imgforge.py presets                  # 預設規格
python skill/imgforge.py render job.json -o out   # 主流程
python skill/imgforge.py quick icon.svg -s 16,32,64 -o icon_{s}.png
```

成功每個輸出一行（`OK out/icon.png 128x128 png 1f`），錯誤只印原因與位置。

### 最小範例

`icon.svg` + `job.json`：

```json
{
  "source": "icon.svg",
  "outputs": [
    {"file": "icon_128.png", "size": [128, 128]},
    {"file": "icon_blue.webp", "size": [128, null], "css": ".body{fill:#3a7bd5}"},
    {"preset": "icon-64"}
  ]
}
```

像素風 `.pix`（`mirror: x` 只寫左半）：

```
size: 12x10
palette: .=transparent k=#1a1a1a g=#5ac54f
mirror: x
---
......
...kkk
```

更多範例見 [skill/examples/](skill/examples/)：`pet.json`（SVG 動畫）、`slime.json`（.pix 動畫）、`iconset.json`（MV IconSet：換色＋置中）。

## 專案結構

```
skill/            實際部署的 skill（install.py 連結此目錄）
  SKILL.md        Claude 讀的核心說明
  guides/         進階指引，依需求載入（動畫、輸出進階、RPG Maker MV）
  imgforge.py     CLI
  core/           來源載入、動畫軌道、輸出
  ops/            後處理（@register 註冊，加檔即生效）
  presets/        命名規格（加 json 即生效）
  library/        SVG 部件庫（lib:名稱）
  examples/       範例原圖與 job
tests/            單元測試
docs/             設計文件
install.py        安裝 / 移除 skill 連結
pack.py           打包 dist/imgforge.zip（claude.ai 上傳用，該環境無 SVG 後端）
```

## 測試

```bash
python -m unittest discover tests
```

輸出至 `temp/test/`。

## 文件

- [docs/design.md](docs/design.md)：設計、格式規格、token 實測
- [docs/e2e-browser.md](docs/e2e-browser.md)：claude.ai 瀏覽器端對端測試方法
