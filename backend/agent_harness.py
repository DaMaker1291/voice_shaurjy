"""
JARVIS Agent Harness — ReAct Loop with Pydantic schemas + Self-Healing.

Observe -> Plan (1 tool call) -> Act -> Reflect -> Repeat.
Zero free-text tool arguments. Strict JSON validation.
Self-healing: catch errors, feed back to LLM, retry up to 3 times.
"""
import asyncio
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Callable
from enum import Enum

logger = logging.getLogger("harness")

try:
    from pydantic import BaseModel, Field, validator
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    logger.warning("pydantic not installed — using dict validation fallback")


# ── Tool Schema Definitions ──

if HAS_PYDANTIC:
    class ToolCall(BaseModel):
        action: str = Field(..., description="The tool/action to execute")
        params: dict = Field(default_factory=dict, description="Parameters for the action")
        reasoning: str = Field(default="", description="Why this action was chosen")

    class AgentStep(BaseModel):
        thought: str = Field(..., description="What the agent is thinking")
        action: str = Field(..., description="Action to take")
        params: dict = Field(default_factory=dict)
        observation: str = Field(default="", description="Result of the action")
        done: bool = Field(default=False, description="Whether the goal is achieved")

    class AgentState(BaseModel):
        goal: str
        steps: list[AgentStep] = Field(default_factory=list)
        max_steps: int = Field(default=15)
        current_step: int = Field(default=0)
        success: Optional[bool] = None
        error: Optional[str] = None
        duration_s: float = 0.0

else:
    class ToolCall:
        def __init__(self, action="", params=None, reasoning=""):
            self.action = action
            self.params = params or {}
            self.reasoning = reasoning

    class AgentStep:
        def __init__(self, thought="", action="", params=None, observation="", done=False):
            self.thought = thought
            self.action = action
            self.params = params or {}
            self.observation = observation
            self.done = done

    class AgentState:
        def __init__(self, goal="", steps=None, max_steps=15, current_step=0,
                     success=None, error=None, duration_s=0.0):
            self.goal = goal
            self.steps = steps or []
            self.max_steps = max_steps
            self.current_step = current_step
            self.success = success
            self.error = error
            self.duration_s = duration_s


# ── Available Tools Registry ──

class ToolRegistry:
    """Registry of available tools with their schemas."""

    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, name: str, handler: Callable, description: str,
                 params_schema: dict = None, destructive: bool = False):
        """Register a tool."""
        self._tools[name] = {
            "handler": handler,
            "description": description,
            "params_schema": params_schema or {},
            "destructive": destructive,
        }

    def get_descriptions(self) -> str:
        """Get formatted tool descriptions for the LLM prompt."""
        lines = []
        for name, info in self._tools.items():
            params = ", ".join(f"{k}: {v}" for k, v in info["params_schema"].items())
            flag = " [DESTRUCTIVE]" if info["destructive"] else ""
            lines.append(f"- {name}({params}){flag}: {info['description']}")
        return "\n".join(lines)

    async def execute(self, name: str, params: dict) -> dict:
        """Execute a tool by name."""
        if name not in self._tools:
            return {"success": False, "error": f"Unknown tool: {name}"}
        tool = self._tools[name]
        try:
            result = tool["handler"](**params)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, dict):
                return result
            return {"success": True, "output": str(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


# ── ReAct Agent Harness ──

class AgentHarness:
    """
    ReAct loop: Observe -> Plan -> Act -> Reflect.
    Uses LLM for planning, Pydantic for validation, self-healing for errors.
    """

    def __init__(self, tools: ToolRegistry, llm_call: Callable = None,
                 max_steps: int = 15, max_retries: int = 3):
        self.tools = tools
        self.llm_call = llm_call or self._default_llm
        self.max_steps = max_steps
        self.max_retries = max_retries

    def _default_llm(self, messages: list[dict], max_tokens: int = 500,
                     temperature: float = 0.1) -> str:
        """Default LLM call using groq_agent."""
        try:
            from groq_agent import call as groq_call
            return groq_call(messages, max_tokens=max_tokens, temperature=temperature)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _build_system_prompt(self) -> str:
        """Build the system prompt with tool descriptions."""
        return f"""You are JARVIS, an autonomous computer agent. You execute goals step by step.

AVAILABLE TOOLS:
{self.tools.get_descriptions()}

RULES:
1. Output ONLY valid JSON — one tool call per step.
2. Format: {{"thought": "...", "action": "tool_name", "params": {{...}}, "done": false}}
3. When the goal is achieved, set "done": true.
4. Maximum {self.max_steps} steps. Be efficient.
5. Never output free-text explanations — only JSON tool calls.
6. If a tool fails, try a different approach.

OUTPUT FORMAT (strict JSON):
{{"thought": "what I need to do next", "action": "tool_name", "params": {{"param": "value"}}, "done": false}}"""

    async def run(self, goal: str, on_step: Callable = None) -> AgentState:
        """Execute a goal using the ReAct loop."""
        state = AgentState(goal=goal, max_steps=self.max_steps)
        start = time.time()
        conversation = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": f"Goal: {goal}\n\nStart executing."}
        ]

        for step_num in range(self.max_steps):
            state.current_step = step_num + 1

            # ── PLAN: Ask LLM for next action ──
            response = self.llm_call(conversation, max_tokens=500, temperature=0.1)
            if not response:
                state.error = "LLM returned empty response"
                break

            # Parse JSON from response
            parsed = self._parse_llm_response(response)
            if not parsed:
                state.error = f"Failed to parse LLM response: {response[:200]}"
                break

            thought = parsed.get("thought", "")
            action = parsed.get("action", "")
            params = parsed.get("params", {})
            done = parsed.get("done", False)

            step = AgentStep(thought=thought, action=action, params=params)
            state.steps.append(step)

            if on_step:
                on_step(step_num, "planning", thought)

            if done:
                state.success = True
                step.observation = "Goal achieved."
                if on_step:
                    on_step(step_num, "done", "Goal achieved")
                break

            # ── ACT: Execute the tool ──
            if on_step:
                on_step(step_num, "acting", f"{action}({params})")

            result = await self._execute_with_retry(action, params)
            step.observation = json.dumps(result, default=str)[:1000]

            if on_step:
                status = "done" if result.get("success") else "failed"
                on_step(step_num, status, step.observation[:200])

            # ── REFLECT: Feed result back to LLM ──
            conversation.append({
                "role": "assistant",
                "content": response
            })
            conversation.append({
                "role": "user",
                "content": f"Result: {json.dumps(result, default=str)[:800]}\n\nWhat's next?"
            })

        else:
            state.error = f"Reached max steps ({self.max_steps})"
            state.success = False

        state.duration_s = round(time.time() - start, 2)
        return state

    async def _execute_with_retry(self, action: str, params: dict) -> dict:
        """Execute a tool with self-healing retry."""
        last_error = None
        for attempt in range(self.max_retries):
            result = await self.tools.execute(action, params)
            if result.get("success"):
                return result
            last_error = result.get("error", "Unknown error")
            logger.warning(f"Tool {action} failed (attempt {attempt+1}): {last_error}")
            # Feed error back and try to fix params
            if attempt < self.max_retries - 1:
                fixed_params = await self._heal_params(action, params, last_error)
                if fixed_params:
                    params = fixed_params
        return {"success": False, "error": f"Failed after {self.max_retries} attempts: {last_error}"}

    async def _heal_params(self, action: str, params: dict, error: str) -> dict | None:
        """Ask LLM to fix the parameters based on the error."""
        try:
            response = self.llm_call([
                {"role": "system", "content": "Fix the tool parameters. Output ONLY valid JSON."},
                {"role": "user", "content": f"Tool: {action}\nParams: {json.dumps(params)}\nError: {error}\n\nFix the params:"}
            ], max_tokens=300, temperature=0.1)
            return self._parse_llm_response(response)
        except Exception:
            return None

    def _parse_llm_response(self, text: str) -> dict | None:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        # Remove markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return None


# ── Convenience: Build harness from computer_use agent ──

def build_harness_from_agent(agent) -> AgentHarness:
    """Build an AgentHarness from an existing ComputerUseAgent."""
    tools = ToolRegistry()

    # Register all agent actions as tools
    for action_name, handler in agent._action_registry.items():
        destructive = action_name in (
            "type_text", "send_keystrokes", "hotkey", "mouse_click",
            "move_files", "delete_files", "run_command", "run_shell"
        )
        tools.register(
            name=action_name,
            handler=handler,
            description=f"Execute {action_name}",
            destructive=destructive,
        )

    return AgentHarness(tools=tools)
