# 預先登錄（Pre-registration）v1.2 — 跑 LLM 臂前凍結

> v1.1（2026-11-09 凌晨，Fable 5.1）：依審查意見 F1/F3/F4/F5 修改，仍在 LLM 第一個請求之前，故不算事後更改。

- 撰寫：2026-11-09 01:20（Opus 5.5）。凍結時間：2026-11-09T06:36:28+00:00（UTC），exp/ git commit be449169c6995ef123262624b6fa0f99e9931d8d（題庫與分析程式凍結，之後不得改，改了要留版次與理由）

## 假設
- H1（建模）：在 SALBP-NL 上，LLM＋驗證回饋（≤3 輪）的模型等價率高於單發提示，差距 ≥ 10 個百分點。
- H2（端到端）：LLM 建模＋求解器達到最佳已知工站數的比例，高於 LLM 直接給工站分配。
- H3（難度）：模型等價率隨優先關係表達難度 L1 > L2 > L3 遞減。
- H3 補充（v1.1，Fable 審查 F1）：加入 L4（只用作業名稱指涉），預期 L4 等價率低於 L3。
- H4（加速，若有 GPU）：GPU 蒙地卡羅每秒評估情境數 ≥ CPU numpy 的 10 倍（同一組候選解與情境數）。

## 主要指標
- 模型等價率（model_equiv.py 全項一致）；**抽樣單位＝底題**（每底題每難度先取 3 種子平均），95% CI 用對底題的 bootstrap（10,000 次，seed 20261109）。列層級 Wilson 只作參考（v1.1，Fable 審查 F3）。
- 端到端主指標＝「與 oracle（真值模型＋同一求解器、同一時限）工站數相同且在真值約束下可行」的比例；gap 對 oracle 工站數算，不對已發表最佳解（v1.1，Fable 審查 F4）。
- 主結果限定 n ≤ 100；n > 100 為壓力子集，失敗原因分截斷／解析／不等價三類（v1.1，Fable 審查 F5）。
- 次要：修正輪數、token 數、延遲中位數與 p90、可行率。

## 實驗設計
- 臂：(a) RPW (b) 真值模型＋CP-SAT（oracle）(c) LLM 直接分配 (d) LLM 建模＋驗證＋CP-SAT；(d') 同 (d) 但無驗證回饋（＝單發）。
- 每題 3 個種子（temperature 0.2，seed 1/2/3；端點不支援 seed 就記錄並以 3 次重複代替）。
- 模型：Nemotron 系列一個（名稱於凍結時填入）；若時間允許加一個 Llama 作對照。
- 排除規則：API 錯誤重試 3 次仍失敗的題記為「失敗」計入分母，不剔除。

## 不做的事
- 不看結果後改提示詞再重跑同一批題目而只報最好那次；若改提示詞，報全部版本。


## v1.2 補記（2026-11-09 14:55 台北，Fable 5.1；寫於 exp/ 凍結 commit be449169 之後、第一個真實 LLM 請求之前；程式與題庫未再改動）
依對抗審查（鏡頭 A、B、C）修正分析計畫，理由見 `對抗審查回應_v1.md`：
- **H5**（原 H3 補充獨立成項）：L4（只用名稱指涉）的等價率低於 L3。
- **主指標只有一個**：臂 d（模型＋驗證器回饋）對臂 d′（單發）的模型等價率**配對差**，L1–L4 合併，抽樣單位＝底題（先取三種子平均，再把同一底題的四層一起重抽），bootstrap 10,000 次、seed 20261109、percentile 95% CI（venv 無 scipy，不做 BCa）。H1 的「≥10 個百分點」保留為預期，不做顯著性宣稱。其餘比較皆為次要或描述性。
- **端到端命中定義**：`hit_le`＝工站數 ≤ oracle 且在真值約束下可行（主）；`hit_eq`（＝）另報。oracle 與 LLM 臂用相同執行緒數（4）與時限（60 s）；oracle 解兩次取較小，兩次不同記 `oracle_unstable`。另報 `trivial_lb=0`（oracle 高於 ⌈Σt/c⌉）子集。
- **零 LLM 基線**：臂 r（規則解析器）進同一管線，四層預期 100%，作為「模板天花板」如實報告。
- **n>100 子集（4 個底題）**只報計數不報 CI。規模分佈（37/50 底題 n≤35）寫在海報。
- **失敗分類四類**：truncated／parse／taskset_time／prec_zone，加 other；各分項（tasks、times、closure、zones）通過率另列。原「name-to-id」類取消（程式無法判定）。
- **題庫變更（凍結前）**：200 份標題去實例名改匿名編號 S01–S50；50 份 L4 刪除額外提示句 "Operations are referred to by name."；真值未動。理由：洩漏風險（B7）與 L3/L4 可比性（B6）。
- **冒煙測試**：`--limit 6` 輸出到 `results/smoke/`，不併入正式資料；正式跑從空的 `results/` 開始。
- **不做**：第二個 LLM 對照、人改寫 holdout、檢定力分析（理由見回應文件第四節）。
- 海報用語：不寫 "pre-registered"，寫 "analysis plan fixed before the run; test set, prompt and code hashed in the repository (commit be449169)"。


## v1.3 補記（2026-11-10 02:35 台北，Fable 5.1；寫於正式實驗進行中、**結果尚未開啟**之時；凍結檔未動，本補記與新增分析腳本以 exp/ 第二個 commit 存入，時間戳為本機自報）
依方法論對抗審查 R1（統計）與 R2（基準效度）修正，理由與查證見 `對抗審查回應_v2_方法論五輪.md`：
- **主指標母體**：n ≤ 100 的 46 個底題（與 v1.1 第 17 行一致）；凍結的 `summarize_expB.py` 的 all 列為 50 底題，僅作敏感度。主指標數字由 `exp/poster_fill/make_poster_assets.py`（本補記前已寫好、用乾跑資料驗過）產出。
- **H1 的解讀**：臂 d 第 1 輪與臂 d′ 為同一請求（同 seed、同訊息），驗證器只檢查格式、整數時間、id 連續與無環，不看內容；因此 d − d′ 量的是「驗證器回饋在第 2、3 輪修復的增益」，在決定性端點下結構上 ≥ 0。另報四個描述量：d′ 無效率、d 修復成功率（d′ 無效而 d 等價）、同種子一致率（d′ 有效且 d rounds=1）、無回饋重抽對照（d′ 三種子任一有效）。
- **H2 判準**：臂 d 對臂 c 的 `hit_le` 配對差 > 0（n ≤ 100，底題叢集 bootstrap 95% CI 不含 0 視為支持；否則不支持）。
- **H3 判準**：描述性。報臂 d 等價率 L1、L2、L3 三個點估與 CI；L1 ≥ L2 ≥ L3 成立則稱「方向一致」，不做趨勢檢定。L1→L2→L3 同時變動版面、單位、句式、順序，不做單因素歸因。
- **H5 判準**：臂 d 的 L4 − L3 等價率配對差 < 0（CI 不含 0 視為支持）。已知 L4 相對 L3 同時重抽了句序、句型與冗餘邊，差值不能單獨歸因於名稱指涉。
- **H4**：不論快慢都報；GPU 面板只在有實跑數字時出現。
- **端到端敏感度**：`hit_le` 另對 `truth_m_max` 計算；另報兩次 oracle 皆 OPTIMAL 的底題子集與「oracle 未證明最佳」的底題數；`trivial_lb`＝⌈Σt/c⌉ 定義不變，非平凡子集一律以 k of N 報。
- **API 失敗**：報 d 與 d′ 各自的 API 失敗列數；若不對稱，另列剔除 API 失敗底題的配對差作敏感度。
- **分層描述**：等價率另依規模（n ≤ 20／21–50／51–100）與來源（Otto／Scholl）分層；失敗分項旗標（taskset／time／closure／zone）各層列出。
- **模型與設定（鎖定）**：模型以執行紀錄的 id 為準（Fable 建議 `nvidia/nemotron-3.5-lightning-30b-a3b`，Elvis 回報後填入本行：______）；temperature 0.2；max_tokens 16000；seeds 1/2/3，第 r 輪 seed＋1000(r−1)；CP-SAT 4 執行緒、60 s，2 個並行 job；ortools 9.15.6755；機器 Mac mini（型號：______）；每台機器一個 CSV，不混合。端點若拒絕 seed，程式會靜默改為重複抽樣並在 CSV 無記錄：以 Elvis 的終端輸出為準，寫入本行：______。
- **已知凍結程式限制（揭露）**：原始模型輸出未落檔，diff 只存前 5 條；`invalid:` 類併入 parse；截斷旗標任一輪觸發即黏住；JSON 浮點整數（如 333.0）判無效。
- **題庫事實更正**：站規則（同站／不相容）為合成注入，27/50 底題、四層皆有，不是公開資料的一部分；L4 不是「L3 只改指涉」。海報與 REPORT 同步更正。
- 海報用語改為："Test set, prompts and analysis code hashed in a repository before the run (commit be44916). The analysis-plan text was written before the results were opened; timestamps are self-reported."
- **（R3 補充，同時間）**凍結設定補記：每請求逾時 300 s；429／5xx／連線／逾時重試 3 次（指數退避）；其後任何例外寫成 `FAIL:<Type>` 列，計入分母（v1.0 排除規則）；失敗面板分型別報 FAIL 列數。completion_tokens 含端點計入的 reasoning token（若有），16000 上限含之。無 JSON mode／guided decoding；零樣本提示；hosted 端點無 canary、模型版本字串未記錄。另報「條件等價率」（有效輸出中等價的比例）與「範例照抄疑似列」（schema 範例含 [[4,5]]、[[2,9]] 站規則）。d′−c 的 hit_le 配對差作 d−c 的對照。
- **（R5 補充，同時間）**主指標點估＝平均配對差（等於臂 d 與臂 d′ 等價率之差），bootstrap 中位數只進結果表；CI 為底題叢集 percentile。執行紀錄以 Mac mini 上的 `results/model_id.txt`（模型 id、UTC 時間、機型）、`results/run_terminal.txt`（終端輸出）、`results/seed_probe.txt`（跑後兩次同 seed 請求比對）、`results/pip_freeze.txt` 為準，隨 `results/` 回傳。跑後先以 `poster_fill/check_run.py` 檢查完整性（期望 2000 列、FAIL 列比例、placeholder 模型名），結論 NOT_READY 時的任何補跑都寫入 Disclosed deviations。


## v1.4 補記（2026-11-10 上午台北，Fable 5.2；**寫於看過部分結果之後**：Mac mini 回傳的 940/1400 列，31/46 底題。本補記只記錄已發生的執行偏差與一項事實更正，不新增或更改任何判準）
來源：Mac mini 側工作列表與對話紀錄（`_工作暫存/macmini_partial_0912/`），決策代號 D-005，Elvis 於 2026-11-09 17:51 決定，早於正式跑。
- **模型**：`nvidia/nemotron-3.5-lightning-30b-a3b`，2026-11-09 16:09 CST 設定；機器 Mac mini。
- **偏差 1（程式）**：冒煙測試發現模型預設開啟思考模式，臂 c 18 列全數在 16000 token 截斷。`run_expB.py` 新增 `--no-think`（傳 `chat_template_kwargs.enable_thinking=false`，預設關閉、既有行為不變），加一個測試，重新凍結：程式 commit 1a60d2f、manifest commit 5f8a128（previous_freeze_commit be449169）。題庫、提示詞、評分程式未動。
- **偏差 2（設定）**：建模臂 d／d′／r 思考開、`--max-tokens 32000`、`--workers 4`（v1.3 寫 16000 與 2 並行）；臂 c 思考關、上限 16000、`--workers 2`、輸出在 `results/c_nothink/`。臂 c 與建模臂推理模式不同，H2 的比較須標明此差異。
- **偏差 3（補跑）**：夜間端點逾時造成 FAIL 列（部分結果中 d、d′ 各 32 列）。Mac mini 側計畫在主跑程結束後把 FAIL 列移出並以同指令補跑，原檔備份為 `expB_with_timeouts.csv`。補跑前後兩個版本的主指標都報。
- **事實更正**：v1.3 寫「d − d′ 在決定性端點下結構上 ≥ 0」。端點接受 seed 但同 seed 輸出不重現（Mac mini 探針與部分結果皆顯示），臂 d 第 1 輪與臂 d′ 是獨立抽樣，該結構性不成立；三個 seed 即三次抽樣。主指標定義不變。
- **冒煙資料**：`results/smoke/`（16000 上限、臂 c 思考開）不併入正式結果。
- 兩邊 git 歷史分岔：本機 exp/ 為 be44916 → 796dbb6 → 915883d（分析計畫與 poster_fill）；Mac mini 為 be44916 → 1a60d2f → 5f8a128（執行程式）。收尾時並陳，不改寫歷史。
