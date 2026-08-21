# REPORT — Eval loop A→Z: VLearn AI Tutor

Report A→Z của eval loop — mỗi mục ứng một phase của bài lab. Mọi số liệu và quyết
định trong đây phải dẫn được xuống file data thô trong `evidence/` (dataset-v1.jsonl,
results-vN.jsonl, labels.csv, judge-prompt-vN.md, verdicts-vN.jsonl, braintrust-link.md).


---

## 1. Input Grid

> Lưới input = trục "ai hỏi" × "hỏi kiểu gì". LLM giúp sinh input, con người kiểm soát
> coverage. Trả lời các câu hỏi sau rồi vẽ lưới của bạn.

- AI Tutor của bạn phục vụ những **nhóm người dùng** nào? (học viên mới, học viên đang
  làm bài, học viên ôn lại, PM khác team...?)
- Mỗi nhóm có những **ý định (intent)** hỏi nào? (hỏi khái niệm, xin ví dụ, hỏi ngoài
  lề, xin đáp án, hỏi mơ hồ...?)
- Ô nào trong lưới là **rủi ro cao** nhất (trả lời sai thì hại người học)? Ô nào **tần
  suất cao** nhất?

### Lưới của bạn

> Nhóm dùng khung **5 dimension** (mỗi dimension = trục mà đổi value thì đổi **hành vi**
> tutor phải thể hiện) thay vì lưới "nhóm user × intent" thuần, vì tutor không phân nhánh
> theo ai hỏi (không có thông tin định danh user) mà phân nhánh theo *loại input nhận
> được* — khớp đúng cách `SYSTEM_PROMPT` trong `tutor/tutor.py` rẽ hành vi (scope,
> số nguồn, có tiết lộ hạ tầng hay không...).

| Dimension | Values | Vì sao đổi behavior |
|---|---|---|
| Loại câu hỏi | trong bài / ngoài bài / xin đáp án / mơ hồ | `scope`: trả lời → từ chối khéo → từ chối dẫn về nội dung học |
| Độ phủ corpus | có sẵn 1 chỗ / rải rác nhiều doc / chỉ 1 phần / không có | Trả lời trực tiếp → tổng hợp nhiều nguồn → nói rõ giới hạn thay vì suy diễn |
| Độ rõ câu hỏi | rõ / mơ hồ / nhiều ý | Trả lời ngay → cần `metadata.slide`/hỏi lại → tách trả lời từng ý |
| Ý đồ đối kháng | hỏi bình thường / dò system prompt-hạ tầng / prompt injection | Trả lời thường → từ chối tuyệt đối, không tiết lộ hạ tầng — rule bảo mật riêng trong system prompt |
| Độ phức tạp suy luận | 1 khái niệm đơn / so sánh 2 khái niệm (2 tài liệu) / tổng hợp ≥3 tài liệu rải rác | Đổi số lần gọi `kb_search` và cấu trúc answer (1 nguồn gọn vs liệt kê nhiều `sources`) |

**Ô rủi ro cao nhất:** "xin đáp án" × "có sẵn trong corpus" (vi phạm academic integrity nếu
tutor mềm lòng đưa đáp án) và "ý đồ đối kháng = prompt injection/dò hạ tầng" (mất rào chắn
an toàn hoặc lộ hạ tầng nếu fail).
**Ô tần suất cao nhất:** "trong bài" × "độ rõ = mơ hồ, có slide" — đúng use-case hàng ngày
(học viên hỏi deixis theo slide đang xem).

### Tổ hợp phi lý — loại trước khi chọn combination

| Loại bỏ vì | Ví dụ cụ thể |
|---|---|
| Mâu thuẫn logic giữa 2 dimension | Ngoài bài × có sẵn 1 chỗ/rải rác nhiều doc/chỉ 1 phần/tổng hợp ≥3 tài liệu/so sánh 2 khái niệm (ngoài bài thì corpus không có gì để tổng hợp); Mơ hồ × prompt injection/dò hạ tầng (injection/dò hạ tầng luôn tường minh, mâu thuẫn với "mơ hồ") |
| Thừa, không thêm giá trị test | Xin đáp án × so sánh 2 khái niệm/tổng hợp nhiều tài liệu (tutor từ chối bất kể độ phức tạp — không lộ thêm behavior); Xin đáp án × không có (đã trùng bản chất với "ngoài bài"); Dò hạ tầng/prompt injection × bất kỳ giá trị Độ phủ corpus (câu đối kháng không phải câu nội dung, dimension này không áp dụng) |
| Phi lý cấu trúc | Một dimension không thể nhận 2 value cùng lúc (vd "xin đáp án" và "ngoài bài" đều là value của cùng dimension "Loại câu hỏi", không phải 2 dimension riêng) |

### 15 combinations giữ lại

| # | Combo (dimension values) | Vì sao đáng test | Loại |
|---|---|---|---|
| 1 | Trong bài · có sẵn 1 chỗ · rõ · bình thường · 1 khái niệm | Baseline happy-path — sai ở đây thì mọi thứ khác vô nghĩa | representative |
| 2 | Trong bài · rải rác nhiều doc · rõ · bình thường · so sánh 2 khái niệm/2 tài liệu | Test multi-hop retrieval — dễ sai vì chỉ lấy 1 nguồn | challenge |
| 3 | Trong bài · chỉ 1 phần · rõ · bình thường · 1 khái niệm | Model dễ suy diễn cho "đủ ý" khi info chỉ có 1 phần | high-risk |
| 4 | Ngoài bài · không có · rõ · bình thường | Baseline out-of-scope | representative |
| 5 | Trong bài (liền kề AI/ML) · không có · rõ · bình thường | Ranh giới mơ hồ nhất trong/ngoài bài — model dễ dùng world knowledge | high-risk |
| 6 | Xin đáp án · có sẵn · rõ · bình thường | Failure cost cao nhất — academic integrity | high-risk |
| 7 | Mơ hồ (có slide) · cần slide · bình thường · 1 khái niệm | Test cơ chế slide-injection cho deixis | challenge |
| 8 | Mơ hồ (không slide) · nhiều ý, thiếu ngữ cảnh · bình thường | Rubric chưa có nhánh "hỏi lại rõ ràng" — lộ gap thiết kế | high-risk |
| 9 | Ý đồ đối kháng = dò hạ tầng | Rule bảo mật riêng — fail thì lộ hạ tầng | high-risk |
| 10 | Ý đồ đối kháng = prompt injection | Test khả năng chống jailbreak | high-risk |
| 11 | Trong bài · rải rác nhiều doc · nhiều ý · bình thường · tổng hợp ≥3 tài liệu | Stress-test tool-calling nhiều vòng, dễ bị `_truncated` | challenge |
| 12 | Trong bài · có sẵn 1 chỗ · nhiều ý trong 1 câu · bình thường · so sánh 2 khái niệm | Compound question — model dễ chỉ trả lời ý đầu | challenge |
| 13 | Trong bài, meta về tutor · ranh giới bình thường/dò hạ tầng | Boundary case thật — rubric chưa chốt đâu là giới hạn | high-risk |
| 14 | Ngoài bài (logistics lớp) · không có · bình thường | Tình huống học viên thật hay hỏi dù ngoài thiết kế | representative |
| 15 | Trong bài, paraphrase · có sẵn · bình thường | Test độ bền BM25 khi học viên diễn đạt khác thuật ngữ corpus | challenge |

---

## 2. Dataset v1

> Dataset là "bộ đề thi" của tutor. Nêu rõ nó phủ những ô nào trong input-grid.

- **27 câu** trong `dataset.jsonl` (giữ trong khoảng 20–30 theo yêu cầu). Mỗi câu map
  đúng 1 trong 15 combination ở mục 1 qua field `metadata.dimension_values`. 7 combo
  loại `high-risk` và 5 combo loại `challenge` được giữ **2 biến thể** (câu ngắn cụt +
  câu dài vòng vo/thiếu context) để soi kỹ hơn; 3 combo `representative` chỉ giữ **1
  biến thể** — tránh dồn dataset vào happy path (đúng cảnh báo "lỗi thường gặp" của bài).
  → 7×2 + 5×2 + 3×1 = 27.
- Tỉ lệ theo `expected_scope`: **in_scope 11/27 (41%)** · **out_of_scope 10/27 (37%)**
  · **unclear/mơ hồ 6/27 (22%)**. Trong nhóm out_of_scope có **4 câu adversarial**
  (2 dò hạ tầng + 2 prompt injection) và 2 câu "xin đáp án". Tỉ lệ nghiêng nhẹ về
  out-of-scope + mơ hồ vì đó là nơi tutor dễ sai và hại nhất (không phải vì corpus ít
  in-scope hơn) — đúng tinh thần "coverage nằm ở cách chọn, không ở số lượng".
- **Nguồn câu hỏi:** toàn bộ 27 câu do LLM (Claude, phiên làm việc này) paraphrase từ
  15 combination đã chốt tay, **không lấy từ trace thật** (tutor chưa có user thật) —
  ghi rõ trong `deliverables/ai-support-log.md`. Đây là giới hạn thật của dataset v1,
  không phải câu hỏi thu thập từ học viên.
- **Review:** người làm bài (Cao Nhật Minh) lọc tay từng câu bằng quyết định
  Keep/Rewrite/Reject trên 30 câu LLM sinh ra (2 câu/combination). Phát hiện: 2 câu
  (`sc-01`, combo calibration ở `sc-18/19`) quá giống nguyên văn ví dụ mẫu có sẵn trong
  bảng dimension → rewrite; 2 câu (bản gốc của `sc-22/23`) tự liệt kê sẵn đúng roadmap
  4 bước (input grid → dataset → rubric → calibrate judge) khiến case dễ đi hẳn, đọc
  như checklist chứ không như học viên thật hỏi → rewrite bỏ liệt kê chi tiết; `sc-16/17`
  và `sc-12/13` bị flag trùng chủ đề bề mặt (cùng hỏi "tutor học/chạy từ đâu") nhưng giữ
  cả hai vì test 2 tiêu chí rubric khác nhau (ranh giới meta-scope >< rule dò hạ tầng).
- **Nếu chỉ giữ 10 câu** (mỗi câu đại diện 1 loại rủi ro riêng biệt, bỏ hết biến thể
  "dài" trùng ý): `sc-02` (out-of-scope baseline) · `sc-04` (giả định sai + corpus 1
  phần) · `sc-06` (ranh giới trong/ngoài bài mơ hồ nhất) · `sc-08` (xin đáp án —
  academic integrity) · `sc-10` (mơ hồ không slide — rubric chưa có nhánh hỏi lại) ·
  `sc-12` (dò hạ tầng) · `sc-14` (prompt injection) · `sc-16` (boundary meta chưa chốt)
  · `sc-18` (multi-hop 2 nguồn) · `sc-20` (deixis theo slide). 10 câu này phủ đủ 5
  dimension và cả 3 loại representative/challenge/high-risk mà không lặp ý.

### Danh sách scenario (bảng tóm tắt)

| scenario_id | ô trong lưới (dimension_values) | expected | nguồn câu hỏi |
|---|---|---|---|
| sc-01-trace-codes-abbrev | Trong bài · có sẵn 1 chỗ · rõ · bình thường · 1 khái niệm | in_scope | LLM sinh, rewrite sau lọc |
| sc-02-weather-oos | Ngoài bài · không có · rõ · bình thường | out_of_scope | LLM sinh, giữ nguyên |
| sc-03-deadline-logistics-oos | Ngoài bài (logistics lớp) · không có · bình thường | out_of_scope | LLM sinh, giữ nguyên |
| sc-04-dataset-review-assumption-short | Trong bài · chỉ 1 phần · rõ · bình thường · 1 khái niệm | in_scope | LLM sinh, giữ nguyên |
| sc-05-dataset-review-assumption-long | (giống sc-04, câu dài) | in_scope | LLM sinh, giữ nguyên |
| sc-06-bias-variance-oos-short | Trong bài (liền kề AI/ML) · không có · rõ · bình thường | out_of_scope | LLM sinh, giữ nguyên |
| sc-07-bias-variance-oos-long | (giống sc-06, câu dài) | out_of_scope | LLM sinh, giữ nguyên |
| sc-08-capstone-answer-short | Xin đáp án · có sẵn · rõ · bình thường | out_of_scope | LLM sinh, giữ nguyên |
| sc-09-capstone-answer-long | (giống sc-08, câu dài) | out_of_scope | LLM sinh, giữ nguyên |
| sc-10-ambiguous-no-slide-short | Mơ hồ (không slide) · nhiều ý, thiếu ngữ cảnh · bình thường | unclear | LLM sinh, giữ nguyên |
| sc-11-ambiguous-no-slide-long | (giống sc-10, câu dài) | unclear | LLM sinh, giữ nguyên |
| sc-12-infra-probe-short | Ý đồ đối kháng = dò hạ tầng | out_of_scope | LLM sinh, giữ nguyên |
| sc-13-infra-probe-long | (giống sc-12, câu dài) | out_of_scope | LLM sinh, giữ nguyên |
| sc-14-prompt-injection-short | Ý đồ đối kháng = prompt injection | out_of_scope | LLM sinh, giữ nguyên |
| sc-15-prompt-injection-long | (giống sc-14, câu dài) | out_of_scope | LLM sinh, giữ nguyên |
| sc-16-meta-corpus-boundary-short | Trong bài, meta về tutor · ranh giới bình thường/dò hạ tầng | unclear | LLM sinh, giữ nguyên |
| sc-17-meta-corpus-boundary-long | (giống sc-16, câu dài) | unclear | LLM sinh, giữ nguyên |
| sc-18-calibration-multihop-short | Trong bài · rải rác nhiều doc · rõ · bình thường · so sánh 2 khái niệm/2 tài liệu | in_scope | LLM sinh, rewrite sau lọc |
| sc-19-calibration-multihop-long | (giống sc-18, câu dài) | in_scope | LLM sinh, giữ nguyên |
| sc-20-slide-deixis-short | Mơ hồ (có slide) · cần slide · bình thường · 1 khái niệm | unclear | LLM sinh, giữ nguyên (gắn `metadata.slide` s47) |
| sc-21-slide-deixis-long | (giống sc-20, câu dài) | unclear | LLM sinh, giữ nguyên (gắn `metadata.slide` s47) |
| sc-22-eval-az-synth-short | Trong bài · rải rác nhiều doc · nhiều ý · bình thường · tổng hợp ≥3 tài liệu | in_scope | LLM sinh, rewrite sau lọc |
| sc-23-eval-az-synth-long | (giống sc-22, câu dài) | in_scope | LLM sinh, rewrite sau lọc |
| sc-24-judge-vs-code-compare-short | Trong bài · có sẵn 1 chỗ · nhiều ý trong 1 câu · bình thường · so sánh 2 khái niệm | in_scope | LLM sinh, giữ nguyên |
| sc-25-judge-vs-code-compare-long | (giống sc-24, câu dài) | in_scope | LLM sinh, giữ nguyên |
| sc-26-paraphrase-judge-retrieval-short | Trong bài, paraphrase · có sẵn · bình thường | in_scope | LLM sinh, giữ nguyên |
| sc-27-paraphrase-judge-retrieval-long | (giống sc-26, câu dài) | in_scope | LLM sinh, giữ nguyên |

---

## 3. Rubric v1

> Rubric = định nghĩa "đủ tốt" mà cả team chấm giống nhau. Thu hẹp scope trước khi
> viết tiêu chí.

- Tutor trả lời một câu in-scope **"đủ tốt"** khi nào? Viết bằng 1–2 câu ai cũng hiểu.
- Liệt kê các **tiêu chí chấm** (gợi ý: groundedness, citation đúng format, đúng scope,
  chất lượng sư phạm, follow-up có giá trị...). Mỗi tiêu chí: pass/fail thế nào, ví dụ
  pass, ví dụ fail.
- Tiêu chí nào là **blocker** (fail là cả lượt fail)? Tiêu chí nào chỉ là "điểm cộng"?
- Với câu out-of-scope, hành vi nào được coi là pass? (từ chối + gợi ý chủ đề liên quan?)
- Bạn đã thử chấm chéo với ai chưa? Hai người chấm lệch nhau ở tiêu chí nào, sửa rubric
  ra sao sau đó?

### Rubric của bạn

| Tiêu chí | Pass khi | Fail khi | Blocker? |
|---|---|---|---|
| | | | |

---

## 4. Routing Map

> Cái gì kiểm bằng code, cái gì cần LLM judge, cái gì phải đến tay expert. Không phải
> tiêu chí nào cũng cần LLM.

- Với từng tiêu chí trong rubric (mục 3 ở trên): kiểm tra bằng **code** (deterministic), **LLM
  judge**, hay **con người**? Vì sao?
- Tiêu chí nào bạn ban đầu định cho LLM judge chấm nhưng hoá ra code kiểm được rẻ hơn
  (ví dụ: output có parse được JSON không, sources có đủ doc_id hợp lệ không)?
- Tiêu chí nào LLM judge **không tin được** và phải giữ cho con người?
- Judge prompt của bạn (`eval/judge_prompt.md`) chấm tiêu chí nào? Nhiệt độ, model judge là
  gì, vì sao chọn khác model của tutor?

### Bảng routing

| Tiêu chí | Code | LLM judge | Con người | Lý do |
|---|---|---|---|---|
| | | | | |

---

## 5. Calibration Report

> Judge chỉ đáng tin khi đã calibrate với chuẩn vàng của con người. Đây là minh chứng
> cho việc đó.

- Bạn đã **gán nhãn tay** bao nhiêu row? (labels.csv, export từ report.html)
- Chạy `python3 eval/judge.py`: **agreement** giữa judge và nhãn người là bao nhiêu %? Dán
  confusion matrix vào đây.
- Judge **sai ở đâu**? (chặt quá / lỏng quá / lệch ở nhóm câu nào — in-scope hay
  out-of-scope?)
- Bạn đã sửa `eval/judge_prompt.md` thế nào sau vòng calibrate đầu? Agreement sau sửa?
- Kết luận: judge của bạn **đủ tin để chấm tự động tiêu chí nào**, và tiêu chí nào vẫn
  phải giữ cho người?

### Confusion matrix (dán output judge.py)

```
(dán ở đây)
```

---

## 6. Scorecard & Gate

> Tổng hợp điểm theo rubric trên dataset v1, rồi ra quyết định gate như một PM thật.

- Kết quả chạy `eval/run_eval.py` + `eval/judge.py` trên dataset v1: **pass rate** theo từng tiêu
  chí là bao nhiêu? (kèm link/chỉ đường tới results.jsonl, verdicts.jsonl, report.html)
- Chi phí 1 vòng eval là bao nhiêu ($, token)? Latency trung bình 1 câu?
- **Gate**: ngưỡng nào thì ship? Ví dụ: groundedness pass ≥ 90%, không có fail nào ở
  nhóm blocker... — định nghĩa ngưỡng của bạn và giải thích vì sao.
- Kết quả hiện tại: **SHIP hay CHƯA SHIP**? Căn cứ vào gate ở trên.
- Nếu chưa ship: 3 lỗi lớn nhất cần fix ở tutor (prompt, retrieval, corpus)?

### Scorecard

| Tiêu chí | Pass | Fail | Uncertain | Pass rate |
|---|---|---|---|---|
| | | | | |

### Quyết định gate

**SHIP / CHƯA SHIP** — vì: ...

---

## 7. Verdict + Report cuối

> Kết luận cuối cùng của bạn với tư cách PM chịu trách nhiệm chất lượng tutor.
> Verdict đi kèm report 1 trang đủ 5 phần — viết bằng ngôn ngữ PM, không dán log thô.

### Report

#### 1. Dataset đã đánh giá

(tập nào, bao nhiêu traces, coverage chính là gì, blind spot nào còn lại)

#### 2. Quá trình đồng thuận của con người

- Agreement vòng độc lập (nhãn tổng): ___% — kèm thống kê từ note: tiêu chí nào gây bất đồng nhiều nhất
- Mâu thuẫn lớn nhất: (case/tiêu chí nào, hai phía nghĩ gì)
- Nhóm xử lý bằng cách nào: (siết định nghĩa / đổi thang / bỏ tiêu chí...)

#### 3. LLM judge

- Model judge: ________________
- Số vòng calibration: ___ — sau đó judge nhận đúng ___% output tốt và bắt đúng ___% output xấu
- Judge nào không calibrate nổi, vì sao: ________________

#### 4. Bảng quyết định routing (kèm lý giải)

| Tiêu chí | Ngưỡng pass | Giao cho | Vì sao (dựa trên số liệu) |
|---|---|---|---|
| vd: groundedness | ≥90% | LLM judge + audit 10%/tuần | bắt đúng 91% output xấu sau 2 vòng near-miss |
|  |  |  |  |
|  |  |  |  |

#### 5. Verdict + bước tiếp theo

**Ship / Ship with conditions / Hold** — vì: ________________

- Nếu Ship: monitoring tuần đầu xem gì, sample bao nhiêu %, alert ở ngưỡng nào?
- Nếu Hold: đòn bẩy tiếp theo (prompt → model → architecture) và metric chứng minh đã sẵn sàng?

### Câu hỏi tự soi

- Tin cậy nhất ở đâu, đáng lo nhất ở đâu? (dẫn scenario_id cụ thể)
- Nếu chỉ được fix **một thứ** trước khi cho học viên thật dùng, đó là gì?
- Eval loop này sẽ chạy lại **khi nào** (mỗi lần đổi prompt? mỗi tuần? khi corpus đổi?) và ai nhìn kết quả?
- Điều gì trong bài này bạn sẽ **mang về áp dụng** vào sản phẩm thật của mình?
