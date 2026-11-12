# CLAUDE.md

imgforge：讓 Claude 以最低 token 產出正確尺寸 / 格式 / 動畫幀圖片的全域 Python 工具與 skill。
設計見 [docs/design.md](docs/design.md)。

## 規則

- **回答一律用繁體中文，並且精簡。**
- 文件放 `docs/`。
- `skill/` 是實際部署內容（由 `install.py` 連結至 Claude 設定目錄的 `skills/imgforge`；Windows 用 junction、其他用 symlink），只放執行需要的檔案。
- 相依只允許 Pillow 與 SVG 點陣化後端；不引入 numpy 等重套件（需能上傳 claude.ai）。
- CLI 輸出要精簡：成功一行、錯誤只印原因與位置。
- 優先使用成熟套件處理重活（點陣化、編碼、縮放），自己只寫串接層與無現成套件的小邏輯；但若自寫的總成本（程式碼、相依、token）比引入套件低，可自寫。
- 工具非必用：執行時若直接產出比呼叫 imgforge 更省 token（例：使用者只要一份 SVG 原檔），直接產出即可。

## 需求

- Python 3.10+、Pillow、SVG 點陣化後端（resvg-py 首選；ImageMagick / cairosvg 為選用備援）。
- 不寫死任何一台電腦的環境；需要工具時執行前先檢查。
- 讀寫中文檔案指定 UTF-8。
- 全域 skill 安裝位置依 Claude 設定目錄而定（`$CLAUDE_CONFIG_DIR`，未設定則為 `~/.claude`）下的 `skills/imgforge`。
