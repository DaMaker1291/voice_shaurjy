"""
JARVIS Self-Healing Tool Synthesis Library
===========================================
Automatically catches tool/script failure stack traces, compiles repair patches
using local reflection feedback loops, and stores successful code in the local library.
"""

import os
import json
import traceback
import sys
from typing import Dict, Any, Callable

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "local_tools")

class SelfHealingEngine:
    def __init__(self):
        os.makedirs(TOOLS_DIR, exist_ok=True)

    def register_tool(self, tool_name: str, code_body: str, metadata: Dict[str, Any] = None) -> str:
        """
        Saves a validated tool script into the local tools library.
        """
        clean_name = "".join(c for c in tool_name if c.isalnum() or c in ("_", "-")).lower()
        filepath = os.path.join(TOOLS_DIR, f"{clean_name}.py")
        
        with open(filepath, "w") as f:
            f.write("# JARVIS AUTO-SYNTHESIZED TOOL\n")
            if metadata:
                f.write(f"# Metadata: {json.dumps(metadata)}\n\n")
            f.write(code_body)
            
        return filepath

    def execute_with_healing(
        self, 
        tool_name: str, 
        execute_fn: Callable[[], Any], 
        repair_fn: Callable[[str, str], str]
    ) -> Dict[str, Any]:
        """
        Executes a callable block. If it raises an exception:
        1. Catches trace.
        2. Submits trace & original parameters to repair loop.
        3. Attempts re-compilation and re-runs.
        """
        try:
            result = execute_fn()
            return {"status": "SUCCESS", "result": result, "healed": False}
        except Exception as e:
            error_msg = str(e)
            stack_trace = traceback.format_exc()
            
            # Initiate self-healing loop
            try:
                # Trigger repair prompt to generate code repair
                repaired_code = repair_fn(error_msg, stack_trace)
                
                # Execute repaired script block dynamically
                namespace = {}
                exec(repaired_code, namespace)
                
                # Try executing the repaired handler
                if "run" in namespace:
                    repaired_result = namespace["run"]()
                    # Store repaired tool permanently
                    self.register_tool(tool_name, repaired_code, {"error_repaired": error_msg})
                    return {
                        "status": "HEALED",
                        "result": repaired_result,
                        "healed": True,
                        "repaired_code": repaired_code
                    }
                else:
                    return {
                        "status": "FAILED_HEAL",
                        "error": "Repaired script did not contain 'run()' entrypoint.",
                        "original_error": error_msg
                    }
            except Exception as healing_err:
                return {
                    "status": "FAILED_HEAL",
                    "error": f"Healing pipeline crashed: {str(healing_err)}",
                    "original_error": error_msg,
                    "original_trace": stack_trace
                }

# Global singleton
healer = SelfHealingEngine()
