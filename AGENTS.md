# JARVIS OS — Backend File Reference

A reference mapping every Python module in `backend/` to its role in the AI infestation.

## AI Control & Reasoning Layers

| File | Purpose |
|------|---------|
| `agent_harness.py` | ReAct (Observe-Plan-Act-Reflect) loop with screenshot + DOM context |
| `agent_pool.py` | Thread-pool of reasoning agents with priority-based dispatch |
| `advanced_cortex.py` | Long-term memory & personality mirroring across sessions |
| `autonomous_agent.py` | Self-improving agent with goal-setting and reflection cycles |
| `autonomous_engine.py` | Autonomous task execution engine |
| `autonomous_loop.py` | Continuous self-directed task loop |
| `brain.py` | Core AI decision-making orchestrator |
| `cdp_bridge.py` | Chrome DevTools Protocol bridge — reads live webpage DOM |
| `cdp_browser.py` | Headless browser control via CDP |
| `code_patcher.py` | LLM-powered code repair for self-healing |
| `computer_use.py` | Anthropic-style computer-use API (PyAutoGUI + OCR) |
| `context_orchestrator.py` | Multi-modal context assembly (screen, DOM, clipboard, memory) |
| `context_relay.py` | Cloud ↔ local context relay bridge |
| `context_injector.py` | Injects context into LLM prompts at inference time |
| `deep_learner.py` | Deep learning inference pipeline (PyTorch-based) |
| `dynamic_engine.py` | Dynamic prompt routing based on context analysis |
| `entity_engine.py` | Entity extraction + action routing from natural language |
| `execution_vault.py` | Sandboxed code execution with self-healing retry logic |
| `goal_planner.py` | Hierarchical goal decomposition → sub-task planning |
| `hyperlocal_ai.py` | TF-IDF + cosine search vector engine (zero ML, zero RAM) |
| `injection_sandbox.py` | Prompt injection attack detection & prevention |
| `intent_understander.py` | Intent classification & parameter extraction |
| `multi_agent_router.py` | Routes queries to the optimal specialized agent |
| `rag_engine.py` | Local RAG with BAAI/bge-small-en-v1.5 embeddings + cosine search |
| `reasoning_engine.py` | Logical reasoning chain executor |
| `rebalancer.py` | Portfolio rebalancing logic for financial AI tasks |
| `self_healing.py` | Error → LLM repair → sandbox validation → retry |
| `self_improvement.py` | LLM-driven codebase self-refactoring |
| `skill_marketplace.py` | Dynamic skill/plugin discovery & loading |
| `task_agent.py` | Task-oriented agent with progress tracking |
| `task_planner.py` | Long-horizon task plan decomposition |
| `tool_registry.py` | Registry of available tools for agent execution |
| `universal_engine.py` | Universal intent → action routing engine |
| `universal_hal.py` | Hardware abstraction layer for cross-platform control |
| `universal_search.py` | Cross-engine search unification |
| `universal_tools.py` | Universal toolkit of AI agent operations |
| `workflow_engine.py` | Multi-step workflow orchestration |

## Workspace — Autonomous Computer Environment

| File | Purpose |
|------|---------|
| `workspace_manager.py` | Persistent workspace lifecycle (create, start, stop, destroy) with virtual display |
| `workspace_agent.py` | Autonomous Observe/Plan/Act/Verify agent with LLM planning + self-healing |
| `workspace_api.py` | HTTP + WebSocket API endpoints for workspace control and live streaming |
| `workspace_replicator.py` | Scans user computer (apps, browsers, files, settings) for workspace cloning |
| `workspace_verifier.py` | Screenshot OCR verification for mission step completion + filesystem checks |
| `mission_state.py` | Mission state machine with disk persistence, crash recovery, and action validation |
