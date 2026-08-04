# 全域與專案規則 - AGENTS.md

## 核心行為模式：工具使用規範 (Tool Usage Guidelines)

為了盡可能減少打擾使用者（避免頻繁觸發系統權限確認視窗），你**必須嚴格遵守**以下工具使用規範，最小化終端機指令的使用次數：

1. **禁止使用終端機指令（如 `powershell`, `bash`, `cmd`）來執行單純的檔案讀取、搜尋或列出目錄。**
2. **檔案搜尋**：請一律使用內建的 `grep_search` 工具，絕對不要使用 `Select-String`、`grep` 或 `findstr` 等終端機指令。
3. **檔案讀取**：請一律使用內建的 `view_file` 工具，絕對不要使用 `Get-Content`、`cat` 或 `type` 等終端機指令。
4. **目錄瀏覽**：請一律使用內建的 `list_dir` 工具，絕對不要使用 `Get-ChildItem`、`ls`、`dir` 或 `tree` 等終端機指令。任何用終端機列出檔案的行為都是被禁止的！
5. **優先權原則**：永遠優先使用「最特定、最精確」的內建 API 工具。
6. **合法使用終端機的時機**：只有在「真正需要執行腳本或應用程式」時（例如：編譯程式、啟動伺服器、執行 node/python 腳本、或操作 git），才允許呼叫 `run_command` 來執行終端機指令。

## 技能自動觸發規則 (Skill Automation Rules)

身為進階 AI 助理，你擁有自行判斷何時該呼叫外掛技能的能力，無須使用者明確下達指令：

1. **UI 與視覺設計情境**：當你在製作、修改或建議任何有關網頁前端、UI 介面或視覺排版的程式碼時 $\rightarrow$ 必須**自動載入並套用 impeccable** 技能，以確保提供頂級的美學設計與微互動。
2. **重構與優化情境**：當你在審查現有程式碼、尋找潛在問題，或被要求優化架構時 $\rightarrow$ 必須**自動載入並套用 improve** 技能，以最高標準審查程式碼。
3. **溝通與回覆情境**：在日常對話與解釋技術細節時 $\rightarrow$ 必須**自動套用 stop-slop** 技能的精神，去除無意義的開場白、罐頭回覆和冗言贅字，保持對話精練、像真人資深工程師一般。
4. **困難決策情境**：遇到困難決策、兩難選擇時 $\rightarrow$ 必須**自動載入並套用 llm-council** 技能。

## 鐵律：嚴禁假資料與模擬資料 (Strict Anti-Mock & Anti-Dummy Rule)

1. **嚴禁私自填充假資料**：在撰寫程式碼、API 介面、資料庫操作或前端邏輯時，**絕對禁止**自行發明假資料（Mock Data）、Dummy Array、模擬靜態資料或回傳硬編碼（Hardcoded）的假數值來掩蓋欠缺的實際資料與 API。
2. **欠缺真實資料時的強制處理流程**：
   - 遇缺乏真實資料、API Endpoint 或環境變數時，**禁止**私自以 Mock/Dummy 代替。
   - **必須先以繁體中文向使用者詳細說明**：缺乏何種真實資料、為什麼需要該資料、若使用模擬資料會有何差異。
   - 必須獲得使用者明確同意後，方可暫時使用替代或模擬資料。

5. **極致 UI 與效能流暢度 (Apple-Grade Craftsmanship)**：當製作或修改網頁 UI、動畫、視覺或前端架構時 $\rightarrow$ 必須**自動載入並無條件執行 apple-web-craftsmanship 技能**，嚴格執行 5 大架構支柱（Compositor 合成層動畫、rAF VSYNC 同步、G2+ Continuous Curvature Squircle 超橢圓圓角、彈簧物理動畫 Spring Physics、SF Pro 視覺光學字型、微動態響應與 Web Jetsam 記憶體修剪策略）。

6. **高精準度程式碼審查 (OpenCodeReview)**：當進行程式碼審查、Code Review、Diff 檢查或資安/效能掃描時 $\rightarrow$ 必須**自動載入並執行 open-code-review 技能**，進行高精準度、行號層級的 P0/P1/P2 缺陷分類與零誤報審計。
