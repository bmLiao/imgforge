# imgforge 設計文件

> 狀態：P0–P2 核心已實作（2026-11-12）；待 SKILL 實際使用驗證 token 與 P4 claude.ai 實測。

## 1. 目的

讓 Claude（Claude Code CLI / 桌面版 / claude.ai）依使用者對圖片的描述，**以最低 token 穩定產出正確尺寸、格式的圖片**，包含單圖、多尺寸、sprite sheet、連續動畫幀。

分工原則：

| 角色 | 負責 | 不負責 |
|---|---|---|
| Claude | 理解需求、寫**一次**原圖（最精簡的描述格式）、寫簡短的任務設定、看預覽修正 | 尺寸、縮放、排列、逐幀重畫、轉檔 |
| Python | 點陣化、變體/多幀、縮放、排列、格式輸出、驗證、預覽 | 構圖與美術判斷 |

### 1.1 核心原則：原圖與輸出分離

Claude 只產出「與輸出尺寸無關」的原圖；**要哪種尺寸、格式、排列，全由 job.json 參數交給 Python 轉出**。同一份原圖可重複產出任意規格，改規格不需重畫。

原圖格式依「哪種描述最短」選擇，不是一律 SVG：

| 情境 | 格式 | 原因 |
|---|---|---|
| 扁平向量、圖示、Q 版、UI | SVG | token 與輸出尺寸無關，放大縮小都清晰 |
| 像素風（≤64px） | `.pix` | 16×16 鏡像後約 128 字元；同圖用 SVG `<rect>` 逐點畫會貴數倍 |
| 已有素材 / 外部 AI 產圖 | PNG / JPG | Claude 不需產生原圖，只寫 job |

SVG 的 token 隨**圖的複雜度**增加，與輸出尺寸無關；細節越多越貴，精緻插畫不划算（見 §2）。

### 1.2 工具非必用

以總 token 最低為準。以下情況可不經 imgforge，直接產出：

- 使用者只要 SVG 原檔，或 HTML/CSS 內嵌即可。
- 單一小修改，直接 Edit 現有檔案比寫 job 便宜。

判斷依據是**交付格式**而非尺寸：交付點陣圖（png/jpg/gif/webp…）一律用工具——Claude 無法直接寫出點陣圖，base64 硬寫成本以十萬 token 計；單圖用 `quick` 一行即可（~50 token）。SVG 原圖成本與輸出尺寸無關，大圖小圖相同。

## 2. 範圍與定位

**保證**：尺寸正確、格式正確、排列正確、剛性變換動畫（位移/旋轉/縮放/換色/顯隱）。

**畫質定位**：扁平向量、Q 版、圖示、UI、像素風。精緻插畫 / 厚塗 / 寫實不在保證範圍（受限於 Claude 繪圖能力，非工具能補）。

**開放入口**：流程也接受一般 PNG/JPG 輸入，未來外部 AI 或手繪素材可共用同一套縮放、排列、多幀流程。

### 動畫可行性

| 類型 | 可行性 |
|---|---|
| 待機呼吸、浮動、搖尾、閃爍、旋轉、彈跳 | ✅ 穩定 |
| 眨眼 | ✅ 以 `eye_open` / `eye_closed` 兩組交替顯隱 |
| 簡單走路（腿擺動）、揮手、前衝攻擊 | ✅ 需設定關節軸心 |
| 轉身、4 方向視角 | ⚠️ 每個方向各需一份原圖，一致性難保證 |
| 擠壓變形、布料、透視變化 | ❌ 不支援（需逐幀重畫） |

## 3. 架構

```
原圖 (SVG / .pix / PNG)  ← Claude 唯一花大量 token 的地方
   │
   ▼
[載入/展開 lib:] ─► [變體/多幀：依 id 套變換] ─► [點陣化] ─► [後處理] ─► [排版] ─► [輸出]
                                                                              │
                                                                  預覽圖 ≤512px + 一行結果
```

- **點陣化後端**（可抽換）：`resvg-py`（首選，P0 已驗證，見 §13）→ ImageMagick（備援）→ cairosvg（備援）。
- **降級**：找不到任何 SVG 後端時，`.pix` 與 PNG/JPG 流程仍須只靠 Pillow 正常運作；遇到 SVG 輸入才報錯並提示安裝方式。
- **向量優先**：變換在 SVG 層做，再依各輸出的目標尺寸分別點陣化，避免先縮小再變換造成的模糊。
- **像素風**：`.pix` 直接以像素建構，縮放一律最近鄰。

## 4. 輸入格式

### 4.1 SVG（主格式）

- `viewBox` 自訂，尺寸無關。
- 需要動畫的部位用 `<g id="...">` 分組命名，例：`body`、`head`、`tail`、`eye_open`。
- 顏色以 **class + 內嵌 `<style>`** 定義（例：`.fur{fill:#f08a24}`），方便換色變體。**不要用 CSS 變數**（resvg 不支援 `var()`）。
- 換色（`fill` 軌道、變體）由工具在內嵌 `<style>` 尾端追加覆寫規則；只對 class 上色的部位有效。
- **巢狀與軸心**：
  - 動畫變換**附加在群組原有 `transform` 之後**（不取代）。
  - `pivot` 使用該群組的內部座標，即檔案中寫在該群組內的座標；無祖先 transform 時等同 viewBox 座標。
  - 父群組的動畫自動帶動子群組（例：`tail` 在 `body` 內，身體浮動時尾巴跟著動，再疊加自己的擺動）。
- **部件庫**：`<use href="lib:eye_round">` 於載入階段展開為內嵌元素，後端只會看到標準 SVG。

### 4.2 `.pix` 像素字串（像素風輔助）

```
size: 16x16
palette: .=transparent k=#1a1a1a w=#ffffff o=#f08a24
mirror: x          # 只寫左半，自動鏡像右半（省一半 token）
---
......kk
....kkoo
...koooo
...
```

- **多幀**：再寫一個 `---` 開始下一幀（像素風逐幀重畫成本低）；動畫幀 i 取第 `i % 幀數` 幀。
- `mirror: x`：每行寫 `ceil(w/2)` 字元；寬度為奇數時最後一字元為中央欄，不重複鏡像。`mirror: y` 同理作用於行。
- 工具驗證：每行長度、行數、未定義的調色盤字元、鏡像後的尺寸。

### 4.3 PNG / JPG（外部素材）

只做後處理、排版與輸出；GIF/WebP 動畫輸入讀為多幀。

## 5. 任務設定（job.json）

```json
{
  "source": "pet.svg",
  "anims": {
    "idle": {
      "count": 4,
      "fps": 8,
      "tracks": {
        "body": { "ty": { "wave": 2 } },
        "tail": { "rot": [0, 15, 0, -15], "pivot": [40, 60] },
        "eye_closed": { "hide": [true, true, true, false] },
        "eye_open":   { "hide": [false, false, false, true] }
      }
    },
    "walk_left": { "source": "pet_left.svg", "count": 3, "tracks": { "...": {} } }
  },
  "outputs": [
    { "file": "pet_128.png", "size": [128, 128], "fit": "contain" },
    { "file": "pet_sheet.png", "anim": "idle", "cell": [64, 64], "layout": { "cols": 4 } },
    { "file": "pet.webp", "anim": "idle", "size": [128, null] },
    { "file": "pet.jpg", "size": [256, 256], "bg": "#ffffff", "quality": 90 },
    { "preset": "mv-character-single" }
  ]
}
```

- `anims`：具名動畫，各自可用 `source` 覆寫原圖（多方向、多動作用）。
- 簡寫：只有一組動畫時可在頂層寫 `frames: {count, fps, tracks}`，等同 `anims.default`。
- 未指定 `anim` 的靜態輸出取原圖本身（不套變換）。

### 5.1 軌道（tracks）寫法：越短越好

| 寫法 | 意義 | 適用 |
|---|---|---|
| `[v0, v1, ...]` | 每幀明確值（長度 = count） | 全部 |
| `{"wave": a}` | 正弦一個週期，振幅 a，自動循環 | 數值屬性 |
| `{"keys": {"0": 0, "2": 15}, "ease": "inOut"}` | 關鍵幀內插（`hide`/`fill` 為階梯式） | 全部 |

也可寫常數（每幀同值）。`wave` 可加 `phase`（0–1）、`base`；`keys` 預設 `loop: true`（最後一個關鍵幀內插回第 0 幀）。

屬性：`tx` `ty` `rot` `sx` `sy` `s`（等比）`opacity`（數值）、`hide` `fill`（非數值，不可用 `wave`；`fill` 作用於群組與所有子孫）。`rot/sx/sy` 必須給 `pivot`（座標規則見 §4.1）。

軌道 id `"*"` 代表整張圖（SVG 預設軸心為 viewBox 中心）。`.pix` / PNG 只支援 `"*"`，單位為原圖像素。

### 5.2 輸出選項

| 欄位 | 說明 |
|---|---|
| `file` | 副檔名決定格式：png / apng / jpg / webp / gif / svg |
| `size` | `[w, h]`；等比時另一邊填 `null`，如 `[128, null]` |
| `fit` | `contain`（預設，等比縮放置中、留白）/ `cover`（等比縮放裁切）/ `stretch`（拉伸）/ `pad`（不縮放，只補邊或裁到目標尺寸） |
| `bg` | 背景色；jpg 無透明時必填，預設白 |
| `matte` | GIF 專用：半透明邊緣預先混合的底色，避免鋸齒白邊 |
| `resample` | `lanczos`（預設）/ `nearest`（像素風自動） |
| `anim` | 動畫名稱。配合 gif/webp/apng 輸出動畫；配合 `cell` 輸出 sheet |
| `cell` + `layout` | sprite sheet：格子尺寸、`cols`/`rows`/`gap`/`order` |
| `frames` | 取部分幀或指定播放順序，如 `[0, 2]`、`[1, 0, 1, 2]` |
| `preset` | 套用命名規格（見 §7），其餘欄位可覆寫 |
| `quality` / `colors` | jpg/webp 品質（webp 未給則無損）；減色數（像素風） |
| `css` | 追加至內嵌 `<style>` 的規則，用於換色變體，例 `.fur{fill:#3a7bd5}` |
| `crisp` | SVG 以 crispEdges 點陣化（小尺寸硬邊） |
| `fps` | 覆寫動畫 fps |
| `source` | 此輸出改用其他原圖（靜態） |

動畫格式建議：透明動畫優先 WebP / APNG；GIF 只有 1-bit 透明，需搭配 `matte`。

## 6. CLI

```
python imgforge.py render job.json          # 主流程
python imgforge.py render job.json -o temp/out   # 指定輸出目錄（預設 job 旁 out/）
python imgforge.py quick pet.svg -s 128 -o pet.png   # 單圖免寫 job
python imgforge.py quick pet.svg -s 16,32,64 -o icon_{s}.png   # 多尺寸
python imgforge.py check foo.pix            # 只驗證原圖；無參數時回報可用後端
python imgforge.py presets                  # 列出預設規格
```

**輸出原則（省 token）**：

- 成功：每個輸出一行 `OK out/pet_sheet.png 256x64 png 4f`，最後一行為預覽圖路徑。
- 失敗：只印錯誤位置與原因（例：`pix line 7: length 15 != 16`）。
- 預覽：`out/_preview.png`，≤512px、棋盤格透明底、多幀並排並標幀號。

## 7. 擴充

| 位置 | 用途 | 方式 |
|---|---|---|
| `skill/presets/*.json` | 命名規格（尺寸、格子、排列、槽位、背景、檔名規則） | 加檔即生效 |
| `skill/ops/*.py` | 新的後處理 / 變換 / 排版操作 | 以裝飾器註冊，核心自動載入 |
| `skill/library/` | 可重用的 SVG 部件與調色盤（選配） | SVG 以 `<use href="lib:eye_round">` 引用 |

### 7.1 槽位（slots）：preset 對應多組動畫

多格規格由 preset 宣告**槽位**，每個槽位取 job 中同名 `anims` 的前 `per` 幀。`slots` 未宣告時依 job 中 `anims` 的順序。缺少的槽位留空，並在結果行附 `missing:名稱`。

```json
{
  "name": "mv-character-single",
  "file": "$<name>.png",
  "cell": [48, 48],
  "layout": {"cols": 3, "rows": 4},
  "per": 3,
  "slots": ["down", "left", "right", "up"]
}
```

- 每個槽位佔 `per` 格寬；`layout.order: "col"` 時槽位縱向填（SV 戰鬥圖）。
- MV 行走遊戲播放順序為 1-0-1-2（第 1 幀為站立）；sheet 依 0,1,2 排列，要預覽 GIF 時輸出加 `"frames": [1, 0, 1, 2]`。

### 預設規格範例（第一批）

| preset | 規格 |
|---|---|
| `icon-{16,32,64,128,256,512}` | 正方形 png |
| `mv-face` | 144×144 單格；`mv-faces` 576×288（4×2） |
| `mv-character-single` | `$` 單隻 144×192，3×4 格 48×48，槽位 down/left/right/up，播放 1-0-1-2 |
| `mv-sv-actor` | 576×384，64×64，9×6；18 個動作槽位 × 3 幀 |
| `mv-iconset` | 寬 512，32×32 格 |
| `mv-enemy` | 尺寸自由、透明底 |

## 8. AI 使用流程（SKILL.md 摘要）

1. 釐清：用途、輸出尺寸/格式、是否動畫、風格。缺的才問。
   - 若直接產出更省（§1.2），不用工具。
2. 選輸入格式（§1.1）：一般 → SVG；像素風 → `.pix`；已有素材 → PNG。
3. 寫原圖（動畫部位以 id 分組）＋ job.json。尺寸格式只寫在 job，不寫進原圖。
4. `render`，看一行結果；有錯依訊息修正。
5. Read `_preview.png` 自我檢查（只看預覽，不看原尺寸輸出）。
6. 修正時以 Edit 局部修改原圖，**不要整份重寫**。
7. 交付到使用者指定位置。

## 9. 專案結構

```
imgforge/
├─ CLAUDE.md
├─ docs/design.md
├─ install.py            建立連結：Windows 用 junction，macOS/Linux 用 symlink
├─ skill/                ← 連結至 <Claude 設定目錄>/skills/imgforge
│  ├─ SKILL.md
│  ├─ imgforge.py        CLI 入口
│  ├─ core/              載入、變換、點陣化、排版、輸出
│  ├─ ops/  presets/  library/
│  └─ examples/          範例 SVG / .pix / job
└─ tests/
```

相依：Python 3.10+、Pillow、resvg-py ≥0.5（編譯型套件）。不依賴 numpy；ImageMagick / cairosvg 僅為備援。

## 10. 花費估算（單一素材）

| 項目 | token |
|---|---|
| SVG 原圖 | 1.5k–4k |
| `.pix` 原圖（16×16 鏡像） | ~100–200 |
| job.json / 多幀參數 | 200–500 |
| 預覽一次（512px） | ~350 |
| 修正 2–3 輪 | 每輪 ~1k |
| **合計（SVG）** | **約 5k–12k** |

開發：P2 核心約 600–1000 行 Python（含 anims / 槽位結構），1–2 個工作階段可達可用版。

## 11. 風險

| 風險 | 對策 |
|---|---|
| resvg-py 在 Windows / claude.ai 沙箱不可用 | 後端抽換；無後端時 `.pix`/PNG 流程降級可用；先實測 |
| SVG 縮到小尺寸（≤48px）糊掉 | 輸出選項 `crisp`；像素風改用 `.pix`；提供減色、銳化選項 |
| GIF 半透明邊緣鋸齒 | `matte` 預混底色；建議改用 WebP / APNG |
| 多方向原圖不一致 | 共用 `library/` 部件與調色盤；文件明示限制 |
| Claude 寫 `.pix` 行長出錯 | 工具嚴格驗證＋鏡像減量 |
| claude.ai 沙箱套件與網路限制 | resvg-py 為編譯型套件，不保證可裝；核心邏輯只用 Pillow，部署前實測 |

## 12. 里程碑

| 階段 | 內容 | 驗收 |
|---|---|---|
| **P0 實測** ✅ | 安裝 resvg-py，SVG → PNG | Windows 可正常點陣化 |
| **P1 PoC** ✅（token 待實際使用量測） | 1 隻寵物 SVG → 4 幀待機 → 2 尺寸 + sheet + WebP/GIF | 畫質可接受、token 實測在估算內 |
| P2 核心 ✅ | §4–6 全部（含 anims）、預覽、驗證、SKILL.md、install.py | 範例全部通過（`tests/test_imgforge.py`） |
| P3 擴充 | ~~presets 與槽位、`.pix` 多幀~~（已完成）、ops 註冊、library 部件、減色/銳化 | MV 預設規格產出可直接放進遊戲 |
| P4 claude.ai | 打包 zip、沙箱實測、降級路徑驗證 | 網頁版可用同一份 skill |

## 13. P0 實測結果（2026-11-12）

環境：Windows 11、Python 3.13、Pillow 12.0、resvg-py 0.5.0（`pip install resvg-py`，預編譯 wheel）。腳本：`tests/p0_resvg.py`，輸出：`temp/p0/`。

| 項目 | 結果 |
|---|---|
| API | `resvg_py.svg_to_bytes(svg_string=..., width=, height=, background=, shape_rendering=, style_sheet=)` → PNG bytes |
| 尺寸精確 / RGBA 透明 / 邊緣抗鋸齒 | ✅ 16–512px 皆正確 |
| 只給寬（等比）、非正方 viewBox | ✅ |
| 巢狀 transform、`rotate(a px py)` 軸心、opacity 顯隱 | ✅ 4 幀待機（浮動＋搖尾＋眨眼）正確 |
| sheet / APNG / WebP / GIF（Pillow 組裝） | ✅ |
| `shape_rendering="crisp_edges"`、`background` | ✅ |
| CSS `var()` | ❌ 不支援 → 改用 class |
| 外部 `style_sheet` 覆寫內嵌 `<style>` | ❌ 優先序較低，需 `!important` → 採「追加至內嵌 `<style>`」 |
| 無效 SVG | ✅ 拋 `ValueError` 並附原因 |
| 效能 | 128px 約 3ms/張、512px 約 30ms；首次呼叫約 15–200ms（初始化） |
