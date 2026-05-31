"""Ultra-fast PowerShell executor with persistent runspace. Eliminates 150ms+ process-spawn overhead."""

import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future

_POOL = ThreadPoolExecutor(max_workers=3)
_CACHE: dict[str, tuple[str, float]] = {}  # cmd -> (result, timestamp)
_CACHE_TTL = 5.0  # seconds
_CACHE_MAX = 128
_LOCK = threading.Lock()

# Single persistent PowerShell process for fastest execution
_PS_PROC = None
_PS_LOCK = threading.Lock()


def _ensure_process():
    """Lazy-init a persistent PowerShell process (keeps runspace alive)."""
    global _PS_PROC
    if _PS_PROC is None or _PS_PROC.poll() is not None:
        _PS_PROC = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    return _PS_PROC


def ps(cmd: str, timeout: float = 15.0, use_cache: bool = True) -> str:
    """Execute PowerShell command via persistent runspace. Cached for repeated queries."""
    key = cmd.strip()

    # Cache check
    if use_cache:
        with _LOCK:
            if key in _CACHE:
                result, ts = _CACHE[key]
                if time.time() - ts < _CACHE_TTL:
                    return result

    # Execute via persistent process
    try:
        with _PS_LOCK:
            proc = _ensure_process()
            # Clear any stale output
            proc.stdin.write(f"{cmd}\n")
            proc.stdin.flush()
            # Read until we get output (PowerShell echoes nothing with -Command -)
            # We send a unique marker to know when output ends
            marker = f"`n`n__DONE__{time.time_ns()}__`n`n"
            proc.stdin.write(f'Write-Output "`n`n__DONE__{marker}__`n`n"\n')
            proc.stdin.flush()
            output = []
            done_marker = f"__DONE__{marker}__"
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                if done_marker in line:
                    break
                output.append(line.rstrip("\r\n"))
        result = "\n".join(output).strip()
    except Exception:
        # Fallback: start fresh process
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

    if not result:
        return ""

    # Cache
    if use_cache:
        with _LOCK:
            if len(_CACHE) > _CACHE_MAX:
                # Evict oldest
                oldest = min(_CACHE.keys(), key=lambda k: _CACHE[k][1])
                _CACHE.pop(oldest, None)
            _CACHE[key] = (result, time.time())

    return result[:2000]


def ps_async(cmd: str, timeout: float = 30.0) -> Future:
    """Execute PowerShell command asynchronously."""
    return _POOL.submit(ps, cmd, timeout)


def ps_batch(cmds: list[str]) -> list[str]:
    """Execute multiple independent commands in parallel."""
    futures = [ps_async(cmd) for cmd in cmds]
    return [f.result() for f in futures]


def clear_cache():
    with _LOCK:
        _CACHE.clear()


def get_cache_stats() -> dict:
    with _LOCK:
        return {"size": len(_CACHE), "max": _CACHE_MAX, "ttl": _CACHE_TTL}
