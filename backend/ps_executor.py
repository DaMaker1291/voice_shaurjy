"""Ultra-fast PowerShell executor. Uses subprocess.run() with proper timeouts — no deadlocks."""

import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

_POOL = ThreadPoolExecutor(max_workers=3)

_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 5.0
_CACHE_MAX = 128
_LOCK = threading.Lock()


def ps(cmd: str, timeout: float = 15.0, use_cache: bool = True) -> str:
    """Execute PowerShell command. Always times out properly. Falls back safely."""

    key = cmd.strip()

    if use_cache:
        with _LOCK:
            if key in _CACHE:
                result, ts = _CACHE[key]
                if time.time() - ts < _CACHE_TTL:
                    return result

    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        result = (r.stdout.strip() or r.stderr.strip())[:2000]
    except subprocess.TimeoutExpired:
        result = "timed_out"
    except Exception as e:
        result = f"error: {e}"

    if result and use_cache:
        with _LOCK:
            if len(_CACHE) > _CACHE_MAX:
                oldest = min(_CACHE.keys(), key=lambda k: _CACHE[k][1])
                _CACHE.pop(oldest, None)
            _CACHE[key] = (result, time.time())

    return result[:2000]


def ps_async(cmd: str, timeout: float = 30.0):
    return _POOL.submit(ps, cmd, timeout)


def ps_batch(cmds: list[str]) -> list[str]:
    futures = [ps_async(cmd) for cmd in cmds]
    return [f.result() for f in futures]


def clear_cache():
    with _LOCK:
        _CACHE.clear()


def get_cache_stats() -> dict:
    with _LOCK:
        return {"size": len(_CACHE), "max": _CACHE_MAX, "ttl": _CACHE_TTL}
