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
5. Read `_preview.png` 自查（不要讀原尺寸輸出）。
6. 修正用 Edit 局部改原圖，不要整份重寫。

## SVG 規則

- 必有 `viewBox`；要動的部位用 `<g id="...">` 分組。
- 顏色用 class + 內嵌 `<style>`（`.fur{fill:#f08a24}`）。**不可用 CSS `var()`**（後端不支援）。
- 預設隱藏的部位寫 `display="none"`，以 `hide:false` 顯示。眨眼 = `eye_open`/`eye_closed` 兩組交替。
- 巢狀群組：動畫附加在原 transform 後；`pivot` 用該群組內的座標；子群組跟隨父群組。
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
  "source": "pet.svg",
  "anims": {
    "idle": {"count": 4, "fps": 8, "tracks": {
      "body": {"ty": {"wave": 2}},
      "tail": {"rot": [0, 15, 0, -15], "pivot": [72, 60]},
      "eye_closed": {"hide": {"keys": {"0": true, "3": false}}}
    }},
    "walk_left": {"source": "pet_left.svg", "count": 3, "tracks": {}}
  },
  "outputs": [
    {"file": "pet_128.png", "size": [128, 128]},
    {"file": "pet_blue.png", "size": [128, null], "css": ".fur{fill:#3a7bd5}"},
    {"file": "sheet.png", "anim": "idle", "cell": [64, 64], "layout": {"cols": 4}},
    {"file": "pet.webp", "anim": "idle", "size": [128, 128]},
    {"preset": "mv-character-single"}
  ]
}
```

- 只有一組動畫可寫頂層 `"frames": {...}`（= `anims.default`），輸出用 `"anim": true`。
- 軌道值：常數 / `[每幀值]` / `{"wave": 振幅, "phase": 0~1}` / `{"keys": {"幀": 值}, "ease": "linear|in|out|inOut"}`（預設循環回第 0 幀）。
- 屬性：`tx ty rot sx sy s opacity`（數值）、`hide fill`（不可 wave）。`rot/sx/sy` 必須給 `pivot`。`"*"` = 整張圖（.pix/PNG 只能用 `*`，單位為像素）。
- 輸出欄位：`file`（副檔名定格式 png/apng/jpg/webp/gif/svg）、`size`（`[w,h]`，等比填 `null`）、`fit`（contain 留白 / cover 裁切 / stretch / pad 不縮放）、`bg`、`matte`（GIF 邊緣底色）、`css`（追加樣式，換色變體）、`crisp`、`resample`、`frames`（如 `[1,0,1,2]`）、`fps`、`quality`、`colors`、`source`（覆寫原圖）、`ops`（後處理，逐格套用：`["sharpen", {"op":"outline","color":"#000","width":1}, {"op":"shadow","dx":2,"dy":2}]`）。
- sheet：`cell` + `layout {cols, rows, gap, order: row|col}`。槽位模式：`per` + `slots`（每槽位取同名動畫前 per 幀）。

## 指令

```
render job.json [-o 目錄] [--no-preview]
quick src.svg -s 16,32,64 -o icon_{s}.png [--fit cover] [--bg #fff]
check [檔案]        # 無參數列出後端、ops、lib 部件；svg 列出 id
presets             # 列出預設規格（icon-*、mv-*）
```

MV 行走圖：動畫名 `down/left/right/up` 各 3 幀，第 1 幀為站立（遊戲播放 1-0-1-2）。右向可由左向鏡像：同軌道再加 `"*": {"sx": -1}`，省一份原圖。SV 戰鬥圖：18 個動作名見 `presets`。
