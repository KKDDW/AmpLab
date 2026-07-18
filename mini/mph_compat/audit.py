"""In-memory MCP tool call audit counters."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from time import perf_counter
from typing import Any, Callable, TypeVar


F = TypeVar("F", bound=Callable[..., Any])
RECENT_LIMIT = 100


@dataclass
class CallRecord:
    tool_name: str
    started_at: str
    elapsed_ms: float
    success: bool
    error: str | None = None


_total_calls = 0
_successful_calls = 0
_failed_calls = 0
_tool_counts: Counter[str] = Counter()
_tool_successes: Counter[str] = Counter()
_tool_failures: Counter[str] = Counter()
_recent_calls: deque[CallRecord] = deque(maxlen=RECENT_LIMIT)


def audit_tool(tool_name: str | None = None) -> Callable[[F], F]:
    """Wrap an MCP tool function and record success/failure counters."""

    def decorator(fn: F) -> F:
        name = tool_name or fn.__name__

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = datetime.now(timezone.utc).isoformat()
            start = perf_counter()
            success = False
            error: str | None = None
            try:
                result = fn(*args, **kwargs)
                success = _result_success(result)
                if not success and isinstance(result, dict):
                    error_value = result.get("error")
                    error = str(error_value)[:300] if error_value else None
                return result
            except Exception as exc:
                error = str(exc)[:300]
                raise
            finally:
                elapsed_ms = round((perf_counter() - start) * 1000, 3)
                record_call(name, started, elapsed_ms, success, error)

        return wrapper  # type: ignore[return-value]

    return decorator


def record_call(tool_name: str, started_at: str, elapsed_ms: float, success: bool, error: str | None = None) -> None:
    global _total_calls, _successful_calls, _failed_calls
    _total_calls += 1
    _tool_counts[tool_name] += 1
    if success:
        _successful_calls += 1
        _tool_successes[tool_name] += 1
    else:
        _failed_calls += 1
        _tool_failures[tool_name] += 1
    _recent_calls.append(
        CallRecord(
            tool_name=tool_name,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
            success=success,
            error=error,
        )
    )


def stats() -> dict[str, Any]:
    success_rate = round(_successful_calls / _total_calls, 4) if _total_calls else 0.0
    tools = {}
    for name in sorted(_tool_counts):
        count = _tool_counts[name]
        successes = _tool_successes[name]
        failures = _tool_failures[name]
        tools[name] = {
            "count": count,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / count, 4) if count else 0.0,
        }
    return {
        "success": True,
        "total_calls": _total_calls,
        "successful_calls": _successful_calls,
        "failed_calls": _failed_calls,
        "success_rate": success_rate,
        "tools": tools,
    }


def recent(limit: int = 20) -> dict[str, Any]:
    clean_limit = max(1, min(int(limit), RECENT_LIMIT))
    records = list(_recent_calls)[-clean_limit:]
    return {
        "success": True,
        "limit": clean_limit,
        "calls": [
            {
                "tool_name": record.tool_name,
                "started_at": record.started_at,
                "elapsed_ms": record.elapsed_ms,
                "success": record.success,
                "error": record.error,
            }
            for record in records
        ],
        "count": len(records),
    }


def reset() -> dict[str, Any]:
    global _total_calls, _successful_calls, _failed_calls
    _total_calls = 0
    _successful_calls = 0
    _failed_calls = 0
    _tool_counts.clear()
    _tool_successes.clear()
    _tool_failures.clear()
    _recent_calls.clear()
    return {"success": True, "message": "MCP call audit counters reset."}


def _result_success(result: Any) -> bool:
    if isinstance(result, dict) and "success" in result:
        return bool(result.get("success"))
    return True
