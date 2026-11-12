# RPG Maker MV 素材指引

規格以 `presets` 指令列出的 `mv-*` 為準；此處只寫 preset 表達不了的規則與理由。

## 行走圖 `mv-character-single`

- 動畫名 `down/left/right/up` 各 3 幀，第 1 幀為站立（遊戲播放 1-0-1-2）。
- 右向可由左向鏡像：同軌道再加 `"*": {"sx": -1}`，省一份原圖。

## SV 戰鬥圖 `mv-sv-actor`

- 18 個動作名見 `presets`；缺的動作留空並在結果行標 `missing:`。

## IconSet `mv-iconset`

- 引擎以 `iconIndex % 16` 定位（寫死 16 欄、32px）→ 寬固定 512，不可少欄。
- index 0 = 無圖示（資料庫預設值、狀態圖示視為無）→ preset 以 `skip: 1` 自動留空。
- 高度依數量即可（32 的倍數），不必補到內建的 640。
- 最小單位 = 一列 16 格；測試/示範時填滿 15 格，不要留一排空白。
- 像素風 16px 原圖放大到 32 格 → 置中用 `step: 2` 保格線。
- 同造型換色：`frames` 重複該幀 + `palette` 指定範圍，不必重畫。
- MV 視窗為深藍底：深色外框與暗部會被吃掉，render 加 `--preview-bg #1d2b4a` 自查輪廓。

完整範例：`examples/iconset.json`（原圖 `examples/items.pix`）。精簡寫法：

```json
{"source": "items.pix", "frames": {}, "outputs": [{"preset": "mv-iconset",
  "frames": [0, 0, 1, 2],
  "palette": [{"frames": [1], "set": {"r": "#3a7bd5"}}],
  "ops": [{"op": "center", "step": 2, "frames": ["0-1", 3]}]}]}
```
