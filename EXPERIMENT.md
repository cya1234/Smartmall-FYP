# 如何收 A/B 實驗數據

這份是操作指引，不是理論。目標：讓 `#/aesthetic` 的兩個版本跑出**可以寫進報告的數字**。

---

## 一、我們在測什麼

| 組別 | 看到的分數 | 意思 |
|---|---|---|
| `personal` | 個人化分數（跟**你自己的衣櫃**比） | 現在的版本 |
| `public` | 大衆審美分數（跟**通用審美錨點**比） | 教授提的方法 1 |
| `both` | 兩個都看到 | 對照組 |

**依變數**：看到分數後，有沒有按「去逛逛，按這個分數挑」。

**假設**：個人化分數的點擊率**高於**大衆審美。理由是小衆風格的人看到「大衆審美 32 分」會離開，而看到「你的風格 88 分」會繼續逛。

⚠️ **這是代理指標**（click-through），不是下單率。示範網站收不到真實訂單，但「看完有沒有點擊」可以逐人量測，樣本累積快兩個數量級。報告裡必須這樣寫。

---

## 二、開始前

```powershell
cd C:\Users\wpuil\Downloads\SmartMall
.venv\Scripts\python.exe -c "import json,urllib.request;print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:3000/api/experiment')),ensure_ascii=False,indent=1))"
```

四個服務都要開（至少網站 + CLIP，因為分數要 CLIP）：

```powershell
.\start-with-ai.bat
```

確認 CLIP 線上：

```powershell
curl -s localhost:3000/api/aesthetic/status
```

---

## 三、收數據的實際流程

### 步驟 1：讓每個測試者用自己的瀏覽器

**不要**用同一個瀏覽器跑多次 —— 分組存在 `localStorage`，同一個瀏覽器固定在同一組，重複測試等於同一個人投多票。

三種做法，由易到難：

| 做法 | 怎麼做 | 適合 |
|---|---|---|
| **Tailscale**（推薦） | 給對方 `http://100.103.164.46:3000` | 同學、朋友 |
| 同一個 Wi-Fi | 給對方 `http://192.168.0.190:3000` | 在場的人 |
| 無痕視窗 | 每次開新的無痕視窗 | 你自己測試，或人手不夠時 |

### 步驟 2：每人做這四步

```
① 開 http://<網址>/#/aesthetic
② 上傳一張自己今天（或最近）的穿搭照
③ 看分數，停留約 5 秒
④ 按「去逛逛，按這個分數挑」→ 或直接關掉（關掉也算一次 view）
```

**關鍵**：不要提示他們該按哪個。你要的是自然反應。

### 步驟 3：事後讀數字

```powershell
curl -s localhost:3000/api/experiment
```

或開一個好讀的版本：

```powershell
.venv\Scripts\python.exe -c "import json,urllib.request;d=json.load(urllib.request.urlopen('http://localhost:3000/api/experiment'));[print(f\"{k:9s} views={v['views']:3d} actions={v['actions']:3d} ctr={v['ctr']} meanScore={v['meanScore']}\") for k,v in d['arms'].items()];print('lift',d['liftPersonalVsPublic'],'conclusive',d['conclusive'])"
```

---

## 四、要收多少才夠

以「兩個比例差異」的粗略公式（80% 檢定力、α=0.05）：

```
每組樣本 ≈ 16 × p(1-p) / d²
```

| 想偵測的差距 | 每組需要 | 三組合計 |
|---|---|---|
| 20 個百分點 | 約 **84** 次 | 約 250 |
| 15 個百分點 | 約 **150** 次 | 約 450 |
| 10 個百分點 | 約 **336** 次 | 約 1000 |

**實務建議**：

- 目標 **每組 30–50 次**，大約 15–25 位測試者（每人可能試 2–3 張照片）
- 30 次以下不要寫「顯著」，寫「方向一致」
- `/api/experiment` 的 `conclusive` 在每組 <30 次時是 `false`，**照它說的寫**

---

## 五、五個會毁掉數據的陷阱

| 陷阱 | 為什麼糟 | 怎麼避 |
|---|---|---|
| **同一人重複測試** | 一人多票，且他可能記得上一次的分數 | 每人一個瀏覽器；無痕視窗要關掉重開 |
| **你提示他們按按鈕** | 你在量你的提示，不是量分數的影響 | 只說「試用一下」，不要說「按藍色按鈕」 |
| **測試者都是你自己** | 你已經知道假設，會不自覺配合 | 至少 10 位是別人 |
| **只看平均值** | 平均高但某人極低，你看不出來 | 同時看 `meanScore` 與 views 的差距 |
| **提早停止** | 看到 personal 領先就收工 | **先決定要收多少，收滿才看結果** |

最後一項最重要。中途看結果然後停，等於用噪音製造結論。

---

## 六、寫進報告的模板

```
受測者：17 人（每人 1–2 張照片），共 34 次評分
分組：personal 12 次 / public 11 次 / both 11 次

結果：
  personal  點擊率 58.3%（7/12）
  public    點擊率 27.3%（3/11）
  差異 +31.0 個百分點

判讀：
  方向與假設一致，但每組樣本低於 30，不足以聲稱顯著。
  這是代理指標（看完分數後的點擊），不是下單率。
  下一步：擴大至每組 50 次，並改以真實下單為依變數。
```

**照這個格式寫，教授會覺得你懂統計。** 主動說樣本不足，比被問出來好。

---

## 七、第二輪之前要清資料

```powershell
# 清 analytics（實驗事件都在裡面），網站重啟後會重新 seed 示範資料
curl -s -X POST localhost:3000/api/engagement/reset
```

⚠️ 這會**同時清掉商戶後台的數據**（示範資料會在下次開機時重鋪）。

**不要**清 `data/users.json`，除非你確定不需要那些帳號。

---

## 八、如果你想用真實下單率

需要改三處：

1. 加一個「完成訂單」的真實流程（現在結帳只是動畫）
2. `checkout` 事件要帶商品 id（現在只記總額）
3. 樣本需求會變成**幾百人** —— 一個 FYP 通常做不到

**所以我的建議是：報告裡用 CTR 作主要指標，並明確說明這是代理指標、以及為什麼。** 這比假裝量到下單率誠實得多。

---

## 九、想改實驗設計

| 想改 | 改哪裡 |
|---|---|
| 分組比例 | `public/js/experiment.js` 的 `ARMS` |
| 大衆審美的錨點提示 | `ai-service/visual_search_service.py` 的 `GENERIC_TASTE_PROMPTS` |
| 依變數（不只用點擊） | `public/js/views/aesthetic.js` 的 `aes_action` |
| 顯著性門檻 | `lib/experiment.js` 的 30 次 |
