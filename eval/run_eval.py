"""Chạy tutor trên toàn bộ dataset -> results.jsonl (kèm latency, tokens, chi phí).

Cách dùng:  python3 eval/run_eval.py [dataset.jsonl]
Mặc định đọc dataset.jsonl ở root repo; nếu chưa có thì copy data/dataset.example.jsonl làm mẫu.
Chạy TUẦN TỰ (không song song) để dễ đọc log và tránh vượt rate limit.

Tracing (bài lab yêu cầu): đặt BRAINTRUST_API_KEY hoặc LANGSMITH_API_KEY trong .env —
mỗi câu hỏi sẽ được log thành một trace trong project "ai-evaluation" (xem lại tool
calls, tokens, cost trên app.braintrust.dev / smith.langchain.com). Không có key thì
bỏ qua lặng lẽ. Chi tiết trong README.md mục Tracing.
"""
import json, os, sys, time
from pathlib import Path

# tutor.py nằm ở tutor/ (khu vực sản phẩm) — thêm vào sys.path để import được
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tutor"))

import tutor
import tracing

# --- Tracing (tuỳ chọn): Braintrust hoặc LangSmith, log mỗi câu thành 1 trace
_tracer = tracing.init_tracer()

# Bảng giá USD / 1M tokens (input, output) — theo platform constants.ts
PRICING = {"deepseek-v4-flash": (0.44, 1.32), "gpt-4o-mini": (0.15, 0.60)}

def estimate_cost_usd(model, usage):
    """Ước tính chi phí 1 lượt chạy; model lạ (chưa có giá) thì trả None."""
    short = model.split("/")[-1]
    if short not in PRICING:
        return None
    p_in, p_out = PRICING[short]
    return round((usage.get("prompt_tokens", 0) * p_in
                  + usage.get("completion_tokens", 0) * p_out) / 1_000_000, 8)

def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def main():
    dataset_path = sys.argv[1] if len(sys.argv) > 1 else "dataset.jsonl"
    output_path = os.environ.get("EVAL_RESULTS_FILE", "results.jsonl")
    start = int(os.environ.get("EVAL_START", "0"))
    end_raw = os.environ.get("EVAL_END")
    append = os.environ.get("EVAL_APPEND", "").lower() in {"1", "true", "yes"}
    if not os.path.exists(dataset_path):
        sys.exit("Không thấy %s. Tạo bằng: cp data/dataset.example.jsonl dataset.jsonl"
                 % dataset_path)
    if not tutor.get_api_key():
        sys.exit("Chưa có API key cho model %s.\n"
                 "Tạo file .env trong thư mục eval-kit (xem .env.example), ví dụ:\n"
                 "  DEEPSEEK_API_KEY=sk-...   (cho model deepseek/*)\n"
                 "  OPENAI_API_KEY=sk-...     (cho model openai/*)\n"
                 "rồi chạy lại." % tutor.MODEL)

    all_rows = read_jsonl(dataset_path)
    end = int(end_raw) if end_raw is not None else len(all_rows)
    rows = all_rows[start:end]
    if start < 0 or end < start or end > len(all_rows):
        sys.exit("Khoảng EVAL_START/EVAL_END không hợp lệ cho dataset %d rows." % len(all_rows))
    print("Dataset slice: rows %d:%d / %d | model: %s" %
          (start, end, len(all_rows), tutor.MODEL))
    results, total_cost, t_start = [], 0.0, time.time()

    for i, row in enumerate(rows, 1):
        q = row["input"]
        print("[%d/%d] %s ... " % (i, len(rows), q[:60]), end="", flush=True)
        rec = {"scenario_id": row.get("scenario_id") or row.get("id") or "row-%d" % i,
               "input": q}
        slide = (row.get("metadata") or {}).get("slide")
        if slide:
            rec["slide"] = slide  # giữ lại để judge/report chấm theo đúng bối cảnh
        try:
            output, meta = tutor.call_tutor(q, slide=slide)
            cost = estimate_cost_usd(tutor.MODEL, meta["usage"])
            rec.update(output=output, raw_content=meta["raw_content"],
                       retrieved=meta["retrieved"], latency_s=meta["latency_s"],
                       usage=meta["usage"], cost_usd=cost)
            total_cost += cost or 0
            _tracer.log_run(  # log trace: input, output, tool calls, tokens, cost
                name="tutor-run",
                inputs={"question": q, "slide": slide, "model": tutor.MODEL},
                outputs=output,
                metadata={"steps": meta.get("steps"), "scenario_id": rec["scenario_id"]},
                metrics={**{k: v for k, v in meta["usage"].items()
                            if isinstance(v, (int, float))},
                         "latency_s": meta["latency_s"],
                         **({"cost_usd": cost} if cost else {})},
            )
            print("ok (%.1fs, %s tok, $%s)" % (
                meta["latency_s"], meta["usage"].get("total_tokens", "?"),
                "%.6f" % cost if cost is not None else "?"))
        except Exception as e:  # lỗi 1 câu không được làm chết cả batch
            rec.update(error=str(e))
            print("LỖI: %s" % e)
        results.append(rec)

    with open(output_path, "a" if append else "w", encoding="utf-8") as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("\nXong: ghi %d dòng vào %s | tổng %.1fs | chi phí ~$%.6f"
          % (len(results), output_path, time.time() - t_start, total_cost))
    if _tracer.backend:
        _tracer.flush()
        print("Đã log %d trace lên %s (project '%s')."
              % (len(results), _tracer.backend,
                 os.environ.get("BRAINTRUST_PROJECT") or os.environ.get("LANGSMITH_PROJECT")
                 or "ai-evaluation"))
    print("Bước tiếp: python3 eval/judge.py (chấm tự động) hoặc python3 eval/report.py (xem report)")

if __name__ == "__main__":
    main()
