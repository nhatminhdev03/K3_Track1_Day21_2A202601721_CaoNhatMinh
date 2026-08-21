# AI Support Log


Dương Văn Vũ

### AI đã giúp tôi ở đâu?

AI hỗ trợ paraphrase test inputs sau khi nhóm đã khóa dimensions/combinations; gợi ý
assertions cho code checks và cấu trúc prompt judge; tóm tắt pattern từ các case lệch;
và soạn nháp các phần của REPORT.md. AI cũng hỗ trợ triển khai, test và ghi lại evidence
cho JSON contract, citation ID và quote fidelity.

### AI sai, hời hợt hoặc làm mất coverage ở đâu?

AI từng có thể diễn giải pass rate judge tổng quát quá đơn giản. Khi đọc trace, nhóm phát
hiện judge đang trừ các refusal OOS/injection đúng chỉ vì không có citation; vì vậy số
0% ở slice này là dấu hiệu evaluator/spec sai, không thể quy kết ngay tutor hỏng. AI
cũng không thể thay human label, đặc biệt ở ambiguity, scope boundary và groundedness.

### Tôi đã tự sửa hoặc quyết định lại điều gì?

Tôi cùng nhóm tự chốt bốn dimensions, combinations và human labels độc lập; sau đó mới
chốt rubric, routing, threshold và verdict Hold. Nhóm giữ các số liệu v1 nguyên vẹn,
không dùng candidate v2 lỗi để làm đẹp score. Tôi quyết định code checks là blocker cho
schema/citation/quote và giữ groundedness ở LLM assist + expert audit thay vì auto-judge.
