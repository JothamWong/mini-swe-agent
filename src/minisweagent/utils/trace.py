from contextlib import contextmanager
from contextvars import ContextVar, copy_context
import time
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import functools

# span_buffer is globally shared, but it is thread-safe to append to it
# if we run multiple workers, then the order of span_buffer is not deterministic
# so we must sort by timestmap and use parent_id to build the correct order
# NOTE: If somehow the contention on the span_buffer is dramatically intefering
#       with results, tho i somehow doubt it, make it thread local as well
span_buffer: List["Span"] = []
# trace_stack is ContextVar or thread-local, so [-1] is parent
trace_stack: ContextVar[List["Span"]] = ContextVar("trace_stack", default=[])


class Span:
    def __init__(self, name: str, parent_id: Optional[str] = None):
        self.name = name
        self.span_id = str(uuid.uuid4())
        self.parent_id = parent_id
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration: float = 0.0
        self.attributes: Dict[str, Any] = {}

    def set_attribute(self, k: str, v: Any):
        self.attributes[k] = v

    def __repr__(self):
        indent = "\t" * (self.__get_depth())
        attr_str = f" | {self.attributes}" if self.attributes else ""
        return f"{indent}[{self.span_id}] {self.name} ({self.duration:.4f}s){attr_str}"

    def to_dict(self):
        return {
            "id": self.span_id,
            "parent": self.parent_id,
            "name": self.name,
            "start": self.start_time,
            "end": self.end_time,
            "duration": self.duration,
            "attributes": self.attributes,
        }

    def __get_depth(self) -> int:
        return len([s for s in trace_stack.get() if s.span_id != self.span_id])


@contextmanager
def trace_span(name):
    current_stack = trace_stack.get().copy()
    parent = current_stack[-1] if current_stack else None
    span = Span(name, parent_id=parent.span_id if parent else None)
    current_stack.append(span)
    token = trace_stack.set(current_stack)
    span.start_time = time.perf_counter()
    try:
        yield span
    finally:
        span.end_time = time.perf_counter()
        span.duration = span.end_time - span.start_time
        span_buffer.append(span)
        trace_stack.reset(token)


def run_in_context(func, *args, **kwargs):
    """
    Capture current context (including trace_stack) and return callable
    that executes `func` inside that captured context.
    Necessary for not having races on the root span.
    """
    ctx = copy_context()
    return functools.partial(ctx.run, func, *args, **kwargs)


def generate_report():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"mini-swe-agent-run-{timestamp}.json"
    data = [span.to_dict() for span in sorted(span_buffer, key=lambda x: x.start_time)]
    with open(filename, "w") as outf:
        json.dump(data, outf, indent=4)
