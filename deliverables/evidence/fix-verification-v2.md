# Fix verification v2

Ngày thực hiện: 2026-08-21. Đây là evidence cho các sửa runtime sau scorecard
v1; **không phải** kết quả full evaluation v2 và không thay thế results-v1.jsonl.

## Thay đổi

1. JSON/schema: khi JSON model trả về không parse được, tutor gọi một lượt repair
   chỉ để sửa cú pháp. Repair thất bại thì trả fallback đúng contract để pipeline
   không vỡ.
2. Citation ID: source chỉ được giữ nếu doc_id/section_id xuất hiện trong kết quả
   kb_search của chính lượt hỏi. Citation sai được repair một lần bằng allow-list.
3. Quote fidelity: backend phát hành quote nguyên văn ngắn từ section đã xác nhận,
   đồng thời loại source trùng lặp. Model không còn tự paraphrase quote.

## Xác minh đã chạy

- python tests/test_eval_kit.py: 44 pass, 0 fail.
- Runtime targeted:
  - sc-01 và sc-21: JSON parse được, đủ bốn field và đúng ba follow-up questions.
  - sc-10: citation IDs nằm trong retrieval của lượt chạy.
  - Case dataset-review từng quote-fail: code check quote_verbatim = pass.

## Giới hạn

Chưa chạy lại đủ 27/27 rows sau các thay đổi trên. Vì vậy mọi số liệu scorecard,
calibration và verdict trong REPORT.md vẫn được ghi là v1; không suy diễn rằng các
ngưỡng ship đã đạt cho đến khi có results-v2.jsonl sạch.
