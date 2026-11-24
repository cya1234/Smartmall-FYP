# 每週自動報告：設定說明

每週二自動生成一份 Word 報告，存到你的 Google Drive，並用 Telegram 通知你。

**不需要開著任何聊天界面** —— 報告由 Windows 排程任務產生。

---

## 它是怎樣運作的

```
Windows 排程任務
   ├── 逢星期二 20:00
   └── 每次登入時（若上次報告已超過 6 天 → 補跑）
        ↓
tools/weekly_task.ps1
        ↓
tools/build_weekly_report.py
   ├── 從 git 讀事實（提交、程式碼行數、測試、商品數）
   ├── 生成 Word 報告（6 頁：概況／進度／技術／問答／風險／待確認）
   ├── 複製到 Google Drive 同步資料夾
   └── 發 Telegram 訊息
```

**為甚麼要「登入時補跑」**：你部電腦有時關著。單純的定時任務在你關機時會直接跳過，之後也不會補。所以加了一個登入觸發器，用「上次報告距今超過 6 天」做判斷，最壞情況是你下次開機時補發一份。

---

## 一次性設定（約 10 分鐘）

### 第一步：開 Google Drive 桌面版

1. 開始選單搜「Google Drive」→ 開啟
2. 登入你的 Google 帳號
3. 等它掛載出「My Drive」磁碟（通常係 `G:\My Drive`）

> 如果唔想開著，報告會存在專案的 `reports\` 資料夾，Telegram 訊息會註明「未偵測到 Google Drive」。

### 第二步：建立 Telegram Bot

1. 在 Telegram 搜尋 **@BotFather**（有藍色勾號嗰個）
2. 傳送 `/newbot`
3. 輸入名字，例如 `SmartMall 週報`
4. 輸入 username，必須以 `bot` 結尾，例如 `smartmall_report_bot`
5. BotFather 會回你一串 **token**，長這樣：
   ```
   123456789:AAH4xK9pQrStUvWxYz0123456789abcdef
   ```
   **複製佢。**

### 第三步：取得你的 chat id

1. 在 Telegram 搜尋你自己剛剛建立的 bot（用上面那個 username）
2. **按 Start** 或隨便傳一句話給它（例如 `hi`）
   > 這一步很重要 —— 唔傳訊息，bot 就唔知道要發給誰
3. 用瀏覽器打開（把 `<TOKEN>` 換成你的 token）：
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
4. 在回傳的 JSON 裡面找 `"chat":{"id":123456789,` —— 那個數字就是 **chat_id**

### 第四步：填寫設定檔

複製範本：

```powershell
cd C:\Users\wpuil\Downloads\SmartMall
Copy-Item tools\report_config.example.json .report\report.json
notepad .report\report.json
```

填入 token 和 chat_id：

```json
{
  "telegram": {
    "token": "123456789:AAH4xK9pQrStUvWxYz0123456789abcdef",
    "chat_id": "987654321"
  },
  "drive_folder": ""
}
```

> `drive_folder` 留空會自動偵測。如果自動偵測唔到，填完整路徑，例如
> `"G:\\My Drive\\SmartMall 週報"`

### 第五步：註冊排程任務

```powershell
.\tools\install_weekly_task.ps1
```

想改時間（例如晚上 9 點半）：

```powershell
.\tools\install_weekly_task.ps1 -At 21:30
```

---

## 測試

**先本地測試（不發 Telegram、不寫 Drive）**：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\weekly_task.ps1 -DryRun
```

成功的話會在 `reports\` 見到 `SmartMall 週報 YYYY-MM-DD.docx`。

**再測試真實發送**：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\weekly_task.ps1
```

你應該即刻收到 Telegram 訊息。

**檢查排程任務狀態**：

```powershell
Get-ScheduledTask -TaskName "SmartMall Weekly Report" | Select-Object TaskName, State
Get-ScheduledTaskInfo -TaskName "SmartMall Weekly Report"
```

---

## 報告裡面有甚麼

| 章節 | 內容 |
|---|---|
| 一、本週概況 | 提交數、涉及範疇、程式碼規模、商品數 |
| 二、逐項進度 | 按範疇分組的提交清單 |
| 三、技術重點 | 每個提交「為什麼改」，不只是「改了什麼」 |
| 四、老師可能會問的問題 | 按本週改動挑選，附可直接照讀的答案 |
| 五、下一步與風險 | 優先次序 + 最大風險 |
| 六、需要你自己確認的事 | 示範資料清單、教授六點完成度、無數據支持的宣稱 |
| 附錄 | 事實來源（全部由程式讀取，不是憑記憶） |

---

## 常見問題

**報告沒有出現？**

1. 看 `reports\task.log` —— 有時間戳和錯誤訊息
2. 手動跑一次：`.\tools\weekly_task.ps1 -DryRun`
3. 檢查排程任務：`Get-ScheduledTaskInfo -TaskName "SmartMall Weekly Report"`

**Telegram 沒收到？**

1. 你必須先向 bot 傳過訊息（見第三步）
2. 用瀏覽器測 token 是否有效：
   `https://api.telegram.org/bot<TOKEN>/getMe`
3. 看 `reports\task.log` 裡面 `telegram : not sent (...)` 的原因

**改了程式碼，報告會自動反映嗎？**

會。報告每次都是即時從 git 讀取的，不是預先寫死的。

**想加新的「老師可能會問的問題」？**

編輯 `tools/report_faq.json`，加一個 `{ "id": "...", "tags": [...], "q": "...", "a": "..." }`。
`tags` 對應上方的範疇，`"always": true` 代表每次都出現。

**想停掉？**

```powershell
.\tools\install_weekly_task.ps1 -Remove
```

---

## 檔案位置

| 檔案 | 作用 |
|---|---|
| `tools/weekly_report.py` | 收集事實（git、檔案系統） |
| `tools/build_weekly_report.py` | 生成 Word + 送 Telegram |
| `tools/weekly_task.ps1` | 排程任務的入口 + 寫 log |
| `tools/install_weekly_task.ps1` | 註冊／移除排程任務 |
| `tools/report_faq.json` | 老師問題庫 |
| `.report/report.json` | 你的設定（token 等，**不會進入 git**） |
| `reports/` | 報告輸出與 log |
