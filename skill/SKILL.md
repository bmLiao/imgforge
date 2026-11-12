---
name: imgforge
description: 以最低 token 產出正確尺寸/格式的圖片：圖示、多尺寸、sprite sheet、動畫幀（GIF/WebP/APNG）、像素風、RPG Maker MV 素材。Claude 只寫一次 SVG 或 .pix 原圖加 job.json，由 Python 點陣化、縮放、排列、轉檔。使用者要求產生或轉換點陣圖、icon、sprite、動畫圖、遊戲素材時使用。
---

# imgforge

CLI：`python <本 skill 目錄>/imgforge.py <指令>`（需 Python 3.10+、Pillow；SVG 需 `pip install resvg-py`）。

環境：首次使用先跑 `check`（無 `python` 時用 `python3`）。顯示無後端 → 試 `pip install resvg-py`（失敗再試 `cairosvg`）；仍無法安裝時 SVG 不可用，改用 `.pix` 或 PNG 流程，並告知使用者。

## 何時不用

使用者只要 SVG 原檔 / HTML 內嵌 → 直接寫，不用工具。交付點陣圖（png/jpg/gif/webp）→ 一律用工具。

## 流程

1. 缺的才問：用途、尺寸/格式、是否動畫、風格。
2. 選原圖格式：一般 → SVG；像素風 ≤64px → `.pix`；已有素材 → PNG/JPG。
3. 寫原圖 + `job.json`（尺寸格式只寫在 job）。單圖可用 `quick` 免寫 job。
4. `render job.json -o <輸出目錄>`；看一行結果，錯誤依訊息修正。
5. Read `_preview.png` 自查（不要讀原尺寸輸出）。成品會放深色底時加 `--preview-bg dark`（或 `#rrggbb`）檢查，深色外框在深底會消失。
6. 修正先找 job 參數（細節見 `guides/output.md`），造型本身錯才 Edit 局部改原圖（不要整份重寫）：

| 問題 | 用 |
|---|---|
| 圖示偏上/偏左、對齊不一 | `ops: [{"op":"center"}]`，可加 `frames` 只套部分、`dx/dy` 刻意偏移 |
| 同造型要多種顏色 | `frames` 重複該幀 + `palette`（.pix）/ `css`（SVG） |
| 尺寸、格數、留空 | `size` `cell` `layout` 或 `preset` |
| 邊緣不清、要描邊陰影 | `ops`：`outline` `shadow` `sharpen` |

範例（可直接 render）：`examples/pet.json`（SVG 動畫）、`slime.json`（.pix 動畫）、`iconset.json`（換色＋置中的圖示表）。

## SVG 規則

- 必有 `viewBox`。顏色用 class + 內嵌 `<style>`（`.fur{fill:#f08a24}`）。**不可用 CSS `var()`**（後端不支援）。
- 部件庫（省 token）：`<use href="lib:eye_round" x="14" y="18"/>`，部件以 (0,0) 為中心；清單見 `check`。可用 class `.eye` `.blush` `.mouth` `.sparkle` 換色。

## .pix

```
size: 12x10
palette: .=transparent k=#1a1a1a g=#5ac54f
mirror: x        # 只寫左半 ceil(w/2) 字元；y 為上半；xy 兩者
---
......
...kkk
---              # 再一個 --- = 下一幀
```

## job.json

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

- 輸出欄位：`file`（副檔名定格式 png/apng/jpg/webp/gif/svg）、`size`（`[w,h]`，等比填 `null`）、`fit`（contain 留白 / cover 裁切 / stretch / pad 不縮放）、`bg`、`crisp`（SVG 小尺寸硬邊）、`quality`、`colors`、`source`（覆寫原圖）、`preset`（其餘欄位可覆寫）。

## 指令

```
render job.json [-o 目錄] [--no-preview] [--preview-bg light|dark|#rrggbb]
quick src.svg -s 16,32,64 -o icon_{s}.png [--fit cover] [--bg #fff]
check [檔案]        # 無參數列出後端、ops、lib 部件；svg 列出 id
presets             # 列出預設規格（icon-*、mv-*）
```

## 進階指引（需要時才 Read，路徑相對本 skill 目錄）

| 需要 | 文件 |
|---|---|
| 動畫：anims/tracks、眨眼擺動、GIF/WebP/APNG | `guides/animation.md` |
| sheet、`frames` 選幀、換色變體/範圍、ops（描邊/陰影/置中） | `guides/output.md` |
| RPG Maker MV：行走圖、SV 戰鬥圖、IconSet、臉圖 | `guides/rpgmaker-mv.md` |

新增平台或主題：在 `guides/` 加一份 md、在此表加一列。
