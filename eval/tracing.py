"""Tracing tùy chọn cho eval-kit: Braintrust HOẶC LangSmith — chỉ cần một trong hai.

Backend được chọn theo biến môi trường (theo thứ tự):
  1. BRAINTRUST_API_KEY                        -> Braintrust
  2. LANGSMITH_API_KEY / LANGCHAIN_API_KEY     -> LangSmith
  3. không có key nào                          -> Noop (bỏ qua lặng lẽ)

Project mặc định "ai-evaluation" (đổi qua BRAINTRUST_PROJECT / LANGSMITH_PROJECT).
Lỗi tracing (sai key, rớt mạng...) chỉ cảnh báo một lần, KHÔNG làm hỏng dữ liệu eval.

Dùng:
    import tracing
    tracer = tracing.init_tracer()
    tracer.log_run(name="tutor-run", inputs={...}, outputs={...},
                   metrics={...}, metadata={...})
    tracer.flush()   # gọi trước khi thoát để đẩy nốt buffer

Cả 3 backend có cùng interface (duck typing): .backend, .log_run(), .flush().
"""

import os

DEFAULT_PROJECT = "ai-evaluation"
_warned = set()


def _warn_once(backend, err):
    if backend not in _warned:
        _warned.add(backend)
        print("\n[cảnh báo: log trace %s lỗi (%s) — eval vẫn chạy tiếp bình thường]"
              % (backend, err))


class _Noop:
    backend = None

    def log_run(self, name, inputs=None, outputs=None, metrics=None, metadata=None):
        pass

    def flush(self):
        pass


class _Braintrust:
    backend = "braintrust"

    def __init__(self):
        import braintrust
        self._logger = braintrust.init_logger(
            project=os.environ.get("BRAINTRUST_PROJECT", DEFAULT_PROJECT))

    def log_run(self, name, inputs=None, outputs=None, metrics=None, metadata=None):
        try:
            span = self._logger.start_span(name=name, type="task")
            span.log(input=inputs, output=outputs, metrics=metrics, metadata=metadata)
            span.end()
        except Exception as e:
            _warn_once(self.backend, e)

    def flush(self):
        try:
            self._logger.flush()
        except Exception as e:
            _warn_once(self.backend, e)


class _LangSmith:
    backend = "langsmith"

    def __init__(self):
        from langsmith import Client
        # A workspace is required for organization-scoped service keys.  Pass it
        # explicitly so the SDK sends the correct X-Tenant-Id on trace writes.
        workspace_id = os.environ.get("LANGSMITH_WORKSPACE_ID") or None
        self._client = Client(workspace_id=workspace_id)
        self._project = os.environ.get("LANGSMITH_PROJECT", DEFAULT_PROJECT)

    def log_run(self, name, inputs=None, outputs=None, metrics=None, metadata=None):
        extra = {}
        if metadata:
            extra["metadata"] = metadata
        if metrics:
            extra["metrics"] = metrics
        try:
            self._client.create_run(
                name=name, run_type="chain", project_name=self._project,
                inputs=inputs or {}, outputs=outputs or {}, extra=extra or None)
        except Exception as e:
            _warn_once(self.backend, e)

    def flush(self):
        try:
            if hasattr(self._client, "flush"):
                self._client.flush()
        except Exception as e:
            _warn_once(self.backend, e)


def init_tracer():
    """Chọn backend theo biến môi trường. Chưa pip install / init lỗi -> Noop."""
    if os.environ.get("BRAINTRUST_API_KEY"):
        cls = _Braintrust
    elif os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY"):
        cls = _LangSmith
    else:
        return _Noop()
    try:
        return cls()
    except Exception as e:
        print("[cảnh báo: khởi tạo %s lỗi (%s) — chạy không tracing]"
              % (cls.backend, e))
        return _Noop()
