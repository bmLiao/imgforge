# 輸出進階：sheet、換色、ops、範圍

需要 sprite sheet、換色變體、描邊/陰影/置中、選幀時讀。

## 幀選取

- `frames`：選幀 / 重排 / 重複，如 `[1,0,1,2]`、`[0,0,3]`（重複同一幀再換色 = 不必重畫）。

## 換色

- SVG：`css` 追加樣式，如 `".fur{fill:#3a7bd5}"`。
- `.pix`：`palette`，只能覆寫原檔已定義的字元。
  - `{"r": "#3a7bd5"}` 套全部幀。
  - `[{"frames": [1, "3-5"], "set": {"r": "#3a7bd5", "R": "#24508f"}}]` 依範圍套用。

## ops（後處理，依序逐格）

| op | 參數 | 用途 |
|---|---|---|
| `sharpen` | `amount=120 radius=1` | 縮小後補細節 |
| `outline` | `color width=1` | 外圍描邊 |
| `shadow` | `dx=2 dy=2 color blur=0` | 投影 |
| `center` | `axis=xy step=1 dx=0 dy=0` | 依實際像素置中再偏移；`step` = 像素風放大倍數（保格線），無法整除時偏上/左 |

寫法：`"ops": ["sharpen", {"op": "center", "step": 2}]`。

## 範圍

`palette` 規則與每個 op 都可加 `"frames": [0, "3-5"]`。索引 = 此輸出排出的幀序（`frames` 選取後；sheet 為格序、不含 skip）。未列到的幀不套用（保留原狀）。

## sheet

- `cell: [w, h]` + `layout {cols, rows, gap, order: row|col, skip}`；`skip` = 開頭留空格數。
- 未指定 `anim` 且有多組動畫時，依序串接全部幀。
- 槽位模式：`per` + `slots`，每槽位取同名動畫前 `per` 幀，缺的留空並標 `missing:`（不可與 skip 併用）。
