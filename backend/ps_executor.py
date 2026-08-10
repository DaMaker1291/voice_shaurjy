"""Cross-platform command executor with Execution Vault sandboxing."""

import subprocess
import platform
import threading
import time
from concurrent.futures import ThreadPoolExecutor

_POOL = ThreadPoolExecutor(max_workers=3)

_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 5.0
_CACHE_MAX = 128
_LOCK = threading.Lock()

_IS_WINDOWS = platform.system() == "Windows"

# Lazy-load vault to avoid circular imports
_vault = None


def _get_vault():
    global _vault
    if _vault is None:
        try:
            from execution_vault import get_vault
            _vault = get_vault()
        except ImportError:
            _vault = False
    return _vault if _vault is not False else None


def ps(cmd: str, timeout: float = 15.0, use_cache: bool = True) -> str:
    """Execute a shell command with vault sandboxing when available."""

    key = cmd.strip()

    if use_cache:
        with _LOCK:
            if key in _CACHE:
                result, ts = _CACHE[key]
                if time.time() - ts < _CACHE_TTL:
                    return result

    vault = _get_vault()
    if vault:
        # Use vaulted execution
        try:
            from execution_vault import VaultPolicy
            policy = VaultPolicy(timeout=int(timeout))
            vr = vault.execute(cmd, policy=policy)
            if vr.blocked:
                result = f"BLOCKED: {vr.block_reason}"
            elif vr.timed_out:
                result = "timed_out"
            else:
                result = (vr.stdout.strip() or vr.stderr.strip())[:2000]
        except Exception as e:
            result = f"vault_error: {e}"
    else:
        # FAIL-CLOSED: vault unavailable → block raw subprocess entirely
        raise RuntimeError("Execution vault unavailable. Refusing un-sandboxed execution.")

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
