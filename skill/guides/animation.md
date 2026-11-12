# 動畫（anims / tracks）

輸出 GIF / WebP / APNG 動畫、或動畫幀 sheet 時讀。

## SVG 準備

- 要動的部位用 `<g id="...">` 分組。
- 預設隱藏的部位寫 `display="none"`，以 `hide:false` 顯示。眨眼 = `eye_open`/`eye_closed` 兩組交替。
- 巢狀群組：動畫附加在原 transform 後；`pivot` 用該群組內的座標；子群組跟隨父群組。

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
    {"file": "sheet.png", "anim": "idle", "cell": [64, 64], "layout": {"cols": 4}},
    {"file": "pet.webp", "anim": "idle", "size": [128, 128]}
  ]
}
```

- 只有一組動畫可寫頂層 `"frames": {...}`（= `anims.default`），輸出用 `"anim": true`。`.pix` 多幀未給 `count` 時取檔內幀數。
- 軌道值：常數 / `[每幀值]` / `{"wave": 振幅, "phase": 0~1}` / `{"keys": {"幀": 值}, "ease": "linear|in|out|inOut"}`（預設循環回第 0 幀）。
- 屬性：`tx ty rot sx sy s opacity`（數值）、`hide fill`（不可 wave）。`rot/sx/sy` 必須給 `pivot`。
- `"*"` = 整張圖（.pix/PNG 只能用 `*`，單位為像素）。左右鏡像：`"*": {"sx": -1}`。
- 輸出：`fps` 覆寫、`frames` 指定播放順序（如 `[1,0,1,2]`）。透明動畫優先 WebP / APNG；GIF 只有 1-bit 透明，加 `matte` 底色。
- `center` 等 op 逐格套用：動畫勿逐格置中（會抖動）。
