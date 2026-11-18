# 在「重開就還原」的學校電腦上跑這個專案

前提：那台 4090 機器每次重開都會清空。所以**不能在上面開發**，只能做兩種事：

1. **一次性的實驗**（跑完把結果帶走）
2. **一次性的示範**（跑給人看）

這份文件回答三件事：帶什麼過去、在那裡做什麼、帶什麼回來。

---

## 一、USB 還是 GitHub？

| 方式 | 要帶多少 | 需要網路 | 適合 |
|---|---|---|---|
| **USB（推薦）** | 12 GB | 只有裝套件時 | 學校網路常封鎖 HuggingFace／GitHub |
| GitHub clone | 22 MB | 要快 | 網路好、且模型能重新下載 |
| 混合 | 22 MB + 10.8 GB | 部分 | 程式碼想用最新版時 |

**我的建議：USB 帶整套。**

原因：專案裡 **10.8 GB 是模型權重**，那是唯一真正花時間的部分。學校網路要嘛慢、要嘛擋 HuggingFace；USB 複製 12 GB 只要幾分鐘，而且一定成功。

```powershell
# 在家先做好
cd C:\Users\wpuil\Downloads\SmartMall
.\tools\make-portable.ps1 -Out E:\SmartMall -Force
```

打包會**自動排除**：

| 排除 | 為什麼 |
|---|---|
| `.venv` | Windows 路徑寫死在裡面，換機器不能用 |
| `.git` | 22 MB，不需要 |
| `data/users.json` | **你的帳號與密碼雜湊不該帶去學校電腦** |
| `data/sessions.json` | 同上 |
| `data/analytics.db` | 含你的搜尋紀錄；到那邊會自動重鋪示範資料 |

想離線安裝套件（學校可能連 pip 都擋）：

```powershell
.\tools\make-portable.ps1 -Out E:\SmartMall -Wheels -Force
```

多約 3 GB 的 wheel，但那邊 `pip install` 變成 2 分鐘、不需網路。

---

## 二、到了那台機器：15 分鐘設定

```powershell
# 1. 複製到本機（比直接在 USB 上跑快很多）
#    建議 D:\ 或 C:\Temp，需要約 15 GB
robocopy E:\SmartMall D:\SmartMall /E /NFL /NDL

# 2. 建虛擬環境
cd D:\SmartMall
python -m venv .venv

# 3a. 有網路
.venv\Scripts\pip install -r requirements.txt

# 3b. 沒網路（用打包時帶的 wheel）
.venv\Scripts\pip install --no-index --find-links wheels -r requirements.txt

# 4. 啟動
.\start-with-ai.bat
```

**檢查四件事**（缺一項就別開始做實驗）：

```powershell
.venv\Scripts\python.exe -c "import torch; print(torch.cuda.get_device_name(0), torch.cuda.is_available())"
curl -s localhost:3000/api/visual-search/status
curl -s localhost:3000/api/tryon/status
curl -s localhost:3000/api/aesthetic/status
```

⚠️ 如果 `torch.cuda.is_available()` 是 False，就是 pip 裝到了 CPU 版 —— 這是你之前踩過兩次的坑。修法：

```powershell
.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

---

## 三、在那台機器上做什麼（這是重點）

### 為什麼值得去：24 GB vs 你的 12 GB

你家的 4070 只有 12 GB，所以**有一個實驗你根本做不了**：

| 配置 | 你家 4070（12 GB） | 學校 4090（24 GB） |
|---|---|---|
| CatVTON 試穿 | ✅ 22 秒 | ✅ 更快 |
| qwen2.5:7b 路由 | ✅ 100% 準確 | ✅ 一樣 |
| **7B + 試穿同時跑** | ❌ **實測失敗**（11565 MiB，試穿逾時） | ✅ **應該可行** |

這是唯一一個「必須去那台機器才能做」的實驗，而且它直接影響你的產品建議：

> 如果 7B + 試穿在 24 GB 上可行，那「想要 100% 準確的路由」就從「必須關掉試穿」變成「買 24 GB 的卡」。

### 建議的 75 分鐘流程

| 時間 | 做什麼 | 為什麼 |
|---|---|---|
| T+0 | 複製、建 venv、裝套件 | 15 分鐘 |
| T+15 | 啟動、四個 status 檢查 | 確認真的在跑模型 |
| **T+20** | **實驗 A：7B + 試穿共存** | 只有這裡能做 |
| T+40 | 實驗 B：試穿速度基準（5 件商品） | 報告要一張 4090 vs 4070 的表 |
| T+50 | 實驗 C：跑完整評估（retrieval / forecast / assistant） | 換硬體後數字應該一致 —— 這是**可重現性**的證據 |
| T+60 | 實驗 D：多人示範（可選） | 同學用 LAN 連進來，順便收 A/B 數據 |
| T+70 | **把結果複製回 USB** | 沒做這步，前面全白費 |

---

### 實驗 A：7B + 試穿共存（最重要）

```powershell
# 1. 裝 Ollama（如果學校機器允許）
winget install --id Ollama.Ollama -e
ollama pull qwen2.5:7b-instruct

# 2. 用 7B 啟動
$env:ASSISTANT_LLM="1"; $env:LLM_MODEL="qwen2.5:7b-instruct"; node server.js

# 3. 等模型載入，量 VRAM
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

# 4. 關鍵測試：7B 開著的情況下有辦法做試穿嗎
.venv\Scripts\python.exe tools\test_tryon_e2e.py http://127.0.0.1:3000
```

**要記錄的三個數字**：

| 數字 | 怎麼量 |
|---|---|
| 7B 載入後 VRAM | `nvidia-smi` |
| 加上 CatVTON 後 VRAM | 再量一次 |
| 試穿耗時 / 是否成功 | 測試輸出的 `tookMs` |

**如果成功** → 這是報告裡很好的一段：
> 「在 24 GB 上 7B 路由與虛擬試穿可共存，試穿仍為 X 秒；在 12 GB 上則逾時。這給出明確的硬體建議門檻。」

**如果失敗** → 也一樣有價值：證明門檻高於 24 GB。

### 實驗 B：試穿速度基準

```powershell
.venv\Scripts\python.exe -c @"
import json, time, urllib.request, glob
person = glob.glob('ai-service/vendor/CatVTON/resource/demo/example/condition/person/*.jpg')[0]
import base64
with open(person,'rb') as f: per = 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
for pid in ('p004','p005','p001','p007','p031'):
    body = json.dumps({'productId': pid, 'photo': per, 'steps': 20}).encode()
    req = urllib.request.Request('http://127.0.0.1:3000/api/tryon', data=body, headers={'Content-Type':'application/json'})
    t0 = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=600))
    print('  %s  %s ms  vram=%s' % (pid, r.get('tookMs'), r.get('vramGiB')))
"@ | Tee-Object -FilePath results\tryon-4090.txt
```

### 實驗 C：可重現性

```powershell
.venv\Scripts\python.exe tools\eval_retrieval.py  | Tee-Object results\eval-retrieval.txt
.venv\Scripts\python.exe tools\eval_forecast.py   | Tee-Object results\eval-forecast.txt
.venv\Scripts\python.exe tools\eval_assistant.py  | Tee-Object results\eval-assistant.txt
```

**預期：數字與你家裡跑的一致**（Recall@5 100%、MAPE 0.34%、15/15）。如果不一致，那是發現了一個 bug。

這一段在報告裡叫「跨硬體可重現性」，是加分項。

---

## 四、帶什麼回去（最容易被忘）

**機器會還原，所以沒複製回來的東西等於沒做。**

```powershell
mkdir results
# 上面三個實驗的輸出都 Tee 進去
copy data\eval\*.json results\
copy data\eval\aesthetic-bias.json results\
# 截圖（輪盤、試穿結果、後台）
copy .cache\tryon\*.png results\
```

然後：

```powershell
robocopy D:\SmartMall\results E:\results /E
```

**離開前檢查清單**：

- [ ] `results\eval-*.txt`（三份）
- [ ] `results\tryon-4090.txt`
- [ ] `results\*.json`（評估原始數據）
- [ ] 試穿成功/失敗的截圖
- [ ] `nvidia-smi` 的 VRAM 截圖（實驗 A 的三個數字）
- [ ] A/B 數據（如果做了多人示範）：`curl -s localhost:3000/api/experiment > results\experiment.json`

---

## 五、六個風險（先問清楚再去）

| 風險 | 怎麼確認 | 備案 |
|---|---|---|
| **USB 被禁用** | 帶一支小 USB 先試插 | 改用 GitHub + 現場下載模型 |
| **不能裝 Python 套件** | 問管理員是否有 pip 權限 | `--no-index --find-links wheels` 離線安裝 |
| **PowerShell 禁止執行腳本** | 跑 `.\tools\make-portable.ps1 -List` | 用 `powershell -ExecutionPolicy Bypass -File ...` |
| **沒有網路** | — | 模型與 wheel 都在 USB 上就沒問題 |
| **磁碟空間不足** | 需要約 15 GB | 放 D:\ 而不是 C:\ |
| **中途被重開** | — | **每做完一個實驗就複製結果到 USB**，不要等最後 |

最後一項最實際：**不要假設自己能待到最後。**

---

## 六、如果你只去 30 分鐘

優先順序：

1. **實驗 A**（7B + 試穿共存）—— 只有那裡能做
2. **實驗 B**（4090 速度）—— 一張表
3. 帶走結果

其餘都可以在家做。
