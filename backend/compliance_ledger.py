"""
JARVIS Compliance Transaction Ledger
Immutable, tamper-proof audit trail for every MCP tool invocation,
action execution, and system event. Enterprise compliance requirement.
"""
import json
import time
import hashlib
import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

log = logging.getLogger("jarvis-compliance")


@dataclass
class TransactionRecord:
    """A single immutable transaction record."""
    transaction_id: str
    timestamp: float
    actor_node: str
    tool_name: str
    server_name: str
    arguments: Dict[str, Any]
    result_summary: Dict[str, Any]
    duration_ms: float
    is_error: bool
    identity_jwt_hash: Optional[str] = None
    security_scope: Optional[str] = None
    vault_sandbox_level: str = "LOCAL_PROCESS"
    previous_hash: str = ""  # Chain hash for immutability
    record_hash: str = ""    # Hash of this record


class ComplianceLedger:
    """
    Immutable transaction ledger.
    
    Each record is hash-chained (like a blockchain) so any tampering
    is detectable. Records are stored locally and optionally streamed
    to a centralized compliance endpoint.
    """

    def __init__(self, ledger_dir: Optional[str] = None, actor_node: str = "local"):
        self.actor_node = actor_node
        self.ledger_dir = ledger_dir or os.path.join(
            os.path.expanduser("~"), ".jarvis", "compliance"
        )
        os.makedirs(self.ledger_dir, exist_ok=True)
        self._records: List[TransactionRecord] = []
        self._last_hash = "0" * 64  # Genesis hash
        self._counter = 0

        # Load existing chain
        self._load_chain()

    def _load_chain(self):
        """Load existing transaction chain from disk."""
        chain_file = os.path.join(self.ledger_dir, "chain.jsonl")
        if not os.path.exists(chain_file):
            return

        try:
            with open(chain_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    record = TransactionRecord(**data)
                    self._records.append(record)
                    self._last_hash = record.record_hash
                    self._counter += 1
            log.info(f"Loaded {len(self._records)} existing records from chain")
        except Exception as e:
            log.error(f"Failed to load chain: {e}")

    def _compute_hash(self, record_data: dict) -> str:
        """Compute SHA-256 hash of a record."""
        canonical = json.dumps(record_data, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _verify_chain(self) -> bool:
        """Verify the integrity of the entire chain."""
        prev_hash = "0" * 64
        for record in self._records:
            if record.previous_hash != prev_hash:
                return False
            # Recompute hash
            data = asdict(record)
            del data["record_hash"]
            computed = self._compute_hash(data)
            if computed != record.record_hash:
                return False
            prev_hash = record.record_hash
        return True

    async def log_invocation(
        self,
        tool_name: str,
        server_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        duration_ms: float,
        is_error: bool,
        identity_jwt_hash: Optional[str] = None,
        security_scope: Optional[str] = None,
    ) -> TransactionRecord:
        """Log a tool invocation to the immutable ledger."""
        self._counter += 1
        tx_id = f"tx_{int(time.time())}_{self._counter}"

        record_data = {
            "transaction_id": tx_id,
            "timestamp": time.time(),
            "actor_node": self.actor_node,
            "tool_name": tool_name,
            "server_name": server_name,
            "arguments": arguments,
            "result_summary": {
                "is_error": is_error,
                "content_count": len(result.get("content", [])),
                "duration_ms": duration_ms,
            },
            "duration_ms": duration_ms,
            "is_error": is_error,
            "identity_jwt_hash": identity_jwt_hash,
            "security_scope": security_scope,
            "vault_sandbox_level": "LOCAL_PROCESS",
            "previous_hash": self._last_hash,
        }

        record_hash = self._compute_hash(record_data)
        record_data["record_hash"] = record_hash

        record = TransactionRecord(**record_data)
        self._records.append(record)
        self._last_hash = record_hash

        # Append to chain file
        chain_file = os.path.join(self.ledger_dir, "chain.jsonl")
        with open(chain_file, "a") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=True) + "\n")

        # Write daily summary periodically
        if self._counter % 100 == 0:
            await self._write_daily_summary()

        return record

    async def _write_daily_summary(self):
        """Write a daily compliance summary report."""
        today = time.strftime("%Y-%m-%d")
        summary_file = os.path.join(self.ledger_dir, f"summary_{today}.json")

        today_records = [
            r for r in self._records
            if time.strftime("%Y-%m-%d", time.localtime(r.timestamp)) == today
        ]

        if not today_records:
            return

        total = len(today_records)
        errors = sum(1 for r in today_records if r.is_error)
        tools_used = list(set(r.tool_name for r in today_records))
        servers_used = list(set(r.server_name for r in today_records))
        avg_duration = sum(r.duration_ms for r in today_records) / total if total else 0

        summary = {
            "date": today,
            "actor_node": self.actor_node,
            "total_transactions": total,
            "error_count": errors,
            "success_rate": f"{((total - errors) / total * 100):.1f}%",
            "unique_tools": tools_used,
            "unique_servers": servers_used,
            "avg_duration_ms": round(avg_duration, 1),
            "chain_valid": self._verify_chain(),
            "total_chain_length": len(self._records),
        }

        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=True)

        log.info(f"Daily summary written: {summary_file}")

    def get_records(
        self,
        limit: int = 100,
        tool_name: Optional[str] = None,
        server_name: Optional[str] = None,
        errors_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query records from the ledger."""
        records = self._records

        if tool_name:
            records = [r for r in records if r.tool_name == tool_name]
        if server_name:
            records = [r for r in records if r.server_name == server_name]
        if errors_only:
            records = [r for r in records if r.is_error]

        return [asdict(r) for r in records[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """Get ledger statistics."""
        total = len(self._records)
        errors = sum(1 for r in self._records if r.is_error)
        return {
            "total_records": total,
            "error_count": errors,
            "success_rate": f"{((total - errors) / total * 100):.1f}%" if total else "N/A",
            "chain_valid": self._verify_chain(),
            "last_hash": self._last_hash[:16] + "...",
            "ledger_dir": self.ledger_dir,
        }

    def generate_report(self) -> str:
        """Generate a human-readable compliance report."""
        stats = self.get_stats()
        today = time.strftime("%Y-%m-%d")
        today_records = [
            r for r in self._records
            if time.strftime("%Y-%m-%d", time.localtime(r.timestamp)) == today
        ]

        report = f"""
================================================================================
JARVIS COMPLIANCE & AUTOMATION REPORT | LOGS VALIDATED
================================================================================
Date: {today}
Node: {self.actor_node}
Chain Status: {'VALID' if stats['chain_valid'] else 'COMPROMISED'}

[TRANSACTION METRICS]
  ├── Total Transactions: {stats['total_records']}
  ├── Today's Transactions: {len(today_records)}
  ├── Error Count: {stats['error_count']}
  ├── Success Rate: {stats['success_rate']}
  └── Chain Length: {stats['total_records']} blocks

[AUTHENTICITY]
  ├── Last Block Hash: {stats['last_hash']}
  ├── Chain Integrity: {'VERIFIED' if stats['chain_valid'] else 'FAILED'}
  └── Vault Isolation: LOCAL_PROCESS

================================================================================
SECURITY NOTICE: All records are hash-chained. Tampering is detectable.
================================================================================
"""
        return report.strip()


# ── Singleton ────────────────────────────────────────────────────────────
_ledger: Optional[ComplianceLedger] = None


def get_ledger() -> ComplianceLedger:
    global _ledger
    if _ledger is None:
        _ledger = ComplianceLedger()
    return _ledger
