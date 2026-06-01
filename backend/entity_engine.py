"""Entity Engine — the autonomous AI entity. Memory, goals, proactive behavior, follow-up questions, strategies."""

import json
import os
import re
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from groq_agent import generate as groq_generate

_ENTITY_DIR = os.path.join(os.path.dirname(__file__), ".entity_data")
os.makedirs(_ENTITY_DIR, exist_ok=True)

# ── Memory ─────────────────────────────────────────────────────────

class EntityMemory:
    """Persistent memory for the entity. Stores facts, preferences, goals, history."""

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self.path = os.path.join(_ENTITY_DIR, f"memory_{user_id}.json")
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except:
            return {
                "facts": [],
                "preferences": {},
                "goals": [],
                "completed_goals": [],
                "interactions": [],
                "learned_patterns": [],
                "proactive_topics": [],
                "personality_notes": [],
                "last_active": datetime.now().isoformat(),
            }

    def _save(self):
        self._data["last_active"] = datetime.now().isoformat()
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def add_fact(self, fact: str, category: str = "general"):
        with self._lock:
            self._data["facts"].append({
                "fact": fact, "category": category,
                "timestamp": datetime.now().isoformat()
            })
            if len(self._data["facts"]) > 200:
                self._data["facts"] = self._data["facts"][-200:]
            self._save()

    def add_preference(self, key: str, value: str):
        with self._lock:
            self._data["preferences"][key] = {"value": value, "updated": datetime.now().isoformat()}
            self._save()

    def get_preference(self, key: str, default=None):
        with self._lock:
            return self._data["preferences"].get(key, {}).get("value", default)

    def add_goal(self, goal: str, priority: int = 5, deadline: str = ""):
        with self._lock:
            existing = [g for g in self._data["goals"] if g["goal"] == goal]
            if existing:
                existing[0]["priority"] = priority
                existing[0]["deadline"] = deadline
                existing[0]["updated"] = datetime.now().isoformat()
            else:
                self._data["goals"].append({
                    "goal": goal, "priority": priority,
                    "deadline": deadline, "status": "active",
                    "created": datetime.now().isoformat(),
                    "updated": datetime.now().isoformat(),
                    "progress": 0,
                    "steps_completed": [],
                    "steps_planned": [],
                })
            self._save()

    def complete_goal(self, goal: str):
        with self._lock:
            for g in self._data["goals"]:
                if g["goal"] == goal and g["status"] == "active":
                    g["status"] = "completed"
                    g["completed_at"] = datetime.now().isoformat()
                    self._data["completed_goals"].append(g)
                    self._data["goals"].remove(g)
                    break
            self._save()

    def get_active_goals(self) -> list:
        with self._lock:
            return sorted(
                [g for g in self._data["goals"] if g["status"] == "active"],
                key=lambda x: -x["priority"]
            )

    def log_interaction(self, query: str, response: str, action_taken: str = ""):
        with self._lock:
            self._data["interactions"].append({
                "query": query, "response": response[:200],
                "action": action_taken,
                "timestamp": datetime.now().isoformat()
            })
            if len(self._data["interactions"]) > 100:
                self._data["interactions"] = self._data["interactions"][-100:]
            self._save()

    def learn_pattern(self, pattern: str, category: str = "behavior"):
        with self._lock:
            self._data["learned_patterns"].append({
                "pattern": pattern, "category": category,
                "timestamp": datetime.now().isoformat()
            })
            if len(self._data["learned_patterns"]) > 50:
                self._data["learned_patterns"] = self._data["learned_patterns"][-50:]
            self._save()

    def get_summary(self) -> str:
        with self._lock:
            d = self._data
            goals = d.get("goals", [])
            facts = d.get("facts", [])
            prefs = d.get("preferences", {})
            active = [g for g in goals if g.get("status") == "active"]
            parts = []
            if active:
                parts.append(f"Active goals: {len(active)}")
                for g in active[:3]:
                    parts.append(f"  - {g['goal']} (priority {g['priority']})")
            if prefs:
                pref_strs = [f"{k}={v['value']}" for k, v in list(prefs.items())[:5]]
                parts.append(f"Preferences: {', '.join(pref_strs)}")
            if facts:
                recent = [f["fact"] for f in facts[-3:]]
                parts.append(f"Recent facts: {'; '.join(recent)}")
            return "\n".join(parts)


# ── Strategy Generator ─────────────────────────────────────────────

def generate_strategies(user_input: str, context: dict = None) -> dict:
    """Generate multiple strategies with options for a given user request."""
    memory = context.get("memory_summary", "") if context else ""
    goals = context.get("active_goals", []) if context else []
    goals_str = "\n".join(f"- {g['goal']}" for g in goals) if goals else "No active goals"

    prompt = f"""You are a strategic AI assistant that helps plan complex tasks. For the user's request, generate 2-4 distinct strategies/approaches.

User request: {user_input}

Active goals: {goals_str}

Memory context:
{memory}

For each strategy, provide:
1. A name/title for the approach
2. A brief description
3. Pros and cons
4. Estimated complexity (1-10)
5. Key steps involved

Output ONLY valid JSON. No other text.
Format:
{{
  "strategies": [
    {{
      "name": "Strategy name",
      "description": "Brief description",
      "pros": ["pro1", "pro2"],
      "cons": ["con1", "con2"],
      "complexity": 5,
      "key_steps": ["step1", "step2", "step3"]
    }}
  ],
  "recommended": "name of recommended strategy",
  "follow_up_questions": ["question1", "question2"]
}}"""

    raw = groq_generate(prompt + " _RESPOND_ONLY_JSON", max_tokens=300)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except:
            pass
    return {
        "strategies": [{
            "name": "Standard approach",
            "description": f"Work through {user_input} step by step",
            "pros": ["Straightforward", "Proven approach"],
            "cons": ["May need clarification"],
            "complexity": 5,
            "key_steps": ["Plan", "Execute", "Review"]
        }],
        "recommended": "Standard approach",
        "follow_up_questions": ["What specific outcome do you want?"]
    }


# ── Follow-up Question Generator ──────────────────────────────────

def generate_follow_up(user_input: str, response: str, context: dict = None) -> list[str]:
    """Generate intelligent follow-up questions to clarify or extend the conversation."""
    memory = context.get("memory_summary", "") if context else ""
    goals = context.get("active_goals", []) if context else []
    goals_str = "\n".join(f"- {g['goal']}" for g in goals) if goals else "No active goals"

    prompt = f"""Based on the conversation, generate 2-3 relevant follow-up questions the AI could ask the user to either:
- Clarify ambiguous parts of their request
- Offer to do related tasks
- Help them think through next steps
- Proactively suggest useful actions

User: {user_input}
AI: {response[:300]}

Active goals: {goals_str}

Memory: {memory}

Output ONLY a JSON array of strings. Example: ["question1?", "question2?"]"""

    raw = groq_generate(prompt + " _RESPOND_ONLY_JSON_ARRAY", max_tokens=200)
    m = re.search(r'\[.*\]', raw, re.DOTALL)
    if m:
        try:
            questions = json.loads(m.group())
            return questions if isinstance(questions, list) else []
        except:
            pass
    return []


# ── Proactive Suggestion Engine ────────────────────────────────────

def generate_proactive_suggestions(memory: EntityMemory = None) -> list[str]:
    """Generate proactive suggestions based on user's goals, patterns, and preferences."""
    if not memory:
        return []

    goals = memory.get_active_goals()
    prefs = memory._data.get("preferences", {})
    facts = memory._data.get("facts", [])
    patterns = memory._data.get("learned_patterns", [])

    context_parts = []
    if goals:
        context_parts.append("Active goals: " + "; ".join(g["goal"] for g in goals[:3]))
    if prefs:
        context_parts.append("Preferences: " + "; ".join(f"{k}={v['value']}" for k, v in list(prefs.items())[:5]))
    if patterns:
        context_parts.append("Patterns: " + "; ".join(p["pattern"] for p in patterns[-3:]))
    if facts:
        recent = [f["fact"] for f in facts[-5:]]
        context_parts.append("Recent context: " + "; ".join(recent))

    context_str = "\n".join(context_parts) if context_parts else "New user - no context yet."

    prompt = f"""Based on the user's context, suggest 2-3 proactive things the AI could offer to do.
These should be specific, useful actions that help the user achieve their goals.

Context:
{context_str}

Output ONLY a JSON array of strings, each being a specific suggestion.
Example: ["I can automate your daily reporting", "Want me to scan your network for new devices?"]"""

    raw = groq_generate(prompt + " _RESPOND_ONLY_JSON_ARRAY", max_tokens=200)
    m = re.search(r'\[.*\]', raw, re.DOTALL)
    if m:
        try:
            suggestions = json.loads(m.group())
            return suggestions if isinstance(suggestions, list) else []
        except:
            pass
    return ["Want me to check on your active goals?", "Need help with anything else?"]


# ── Entity Orchestrator ────────────────────────────────────────────

class Entity:
    """The autonomous AI entity. Maintains memory, generates strategies, follows up proactively.
    Self-contained — imports actions, orchestrator, and Groq directly."""

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self.memory = EntityMemory(user_id)
        self._proactive_interval = 300
        self._last_proactive = 0
        self._lock = threading.Lock()

    def _route_action(self, text: str) -> dict | None:
        from actions import detect_action, execute_action, _ACTION_LABELS
        action = detect_action(text)
        if action:
            result = execute_action(action, text)
            label = _ACTION_LABELS.get(action, "")
            return {"text": f"{label}\n{result}", "action": action}
        return None

    def _route_task(self, text: str) -> dict | None:
        from orchestrator import start_task
        return start_task(self.user_id, text)

    def _route_groq(self, text: str) -> str:
        from groq_agent import generate
        history = self.memory._data.get("interactions", [])
        context = "\n".join(f"User: {h['query']}\nJason: {h['response'][:100]}" for h in history[-5:])
        enhanced = f"[Memory: {context[:500]}]\nUser: {text}" if context else text
        return generate(enhanced, self.user_id)

    def process(self, user_input: str) -> dict:
        now = time.time()

        self.memory.log_interaction(user_input, "")
        self._extract_knowledge(user_input)
        related_goals = self._find_related_goals(user_input)

        is_complex = len(user_input.split()) >= 4 and any(
            t in user_input.lower() for t in
            ["book", "plan", "organize", "arrange", "create", "make", "set up",
             "research", "compare", "build", "develop", "start", "launch",
             "automate", "configure", "design", "implement"]
        )

        result = {"text": "", "action": None, "task": None, "strategies": None,
                  "follow_up": None, "proactive": None, "related_goals": related_goals}

        if is_complex:
            strategies = generate_strategies(user_input, {
                "memory_summary": self.memory.get_summary(),
                "active_goals": self.memory.get_active_goals(),
            })
            result["strategies"] = strategies
            result["follow_up"] = strategies.get("follow_up_questions", [])
            task_result = self._route_task(user_input)
            result["task"] = task_result
            if task_result and task_result.get("text"):
                result["text"] = task_result["text"]
            if task_result and task_result.get("type") in ("ask", "notify", "complete", "workflow"):
                result["task_type"] = task_result["type"]
            return result

        action_result = self._route_action(user_input)
        if action_result and action_result.get("action"):
            result["action"] = action_result["action"]
            result["text"] = action_result.get("text", "")
            self.memory.log_interaction(user_input, result["text"], action_result["action"])
            return result

        groq_result = self._route_groq(user_input)
        result["text"] = groq_result

        if result["text"]:
            follow_ups = generate_follow_up(user_input, result["text"], {
                "memory_summary": self.memory.get_summary(),
                "active_goals": self.memory.get_active_goals(),
            })
            result["follow_up"] = follow_ups[:2]

        if now - self._last_proactive > self._proactive_interval:
            self._last_proactive = now
            proactive = generate_proactive_suggestions(self.memory)
            result["proactive"] = proactive[:2]

        self.memory.log_interaction(user_input, result.get("text", ""))
        return result

    def _extract_knowledge(self, text: str):
        """Try to extract facts and preferences from user input."""
        lower = text.lower()

        # Preference patterns
        pref_patterns = [
            (r"(?:i\s+|i'?a?m?\s+)?(?:like|love|prefer|enjoy)\s+(\w+(?:\s+\w+)?)", "likes"),
            (r"(?:i\s+)?(?:don't\s+like|hate|dislike)\s+(\w+(?:\s+\w+)?)", "dislikes"),
            (r"(?:my\s+)?(?:name\s+is\s+)(.+)", "name"),
            (r"(?:i\s+)?(?:work\s+(?:as|at|for)\s+)(.+)", "profession"),
            (r"(?:i\s+)?(?:use\s+)(\w+(?:\s+\w+)?)", "tools"),
        ]
        for pat, category in pref_patterns:
            m = re.search(pat, lower)
            if m:
                self.memory.add_preference(category, m.group(1).strip())

        # Goal patterns
        goal_patterns = [
            r"(?:i\s+)?(?:want|need|plan|hope)\s+to\s+(.+?)(?:\.|!|$)",
            r"(?:i'?m?\s+)?(?:trying|going|looking)\s+to\s+(.+?)(?:\.|!|$)",
            r"(?:my\s+)?(?:goal|aim|objective)\s+(?:is\s+)?(?:to\s+)?(.+?)(?:\.|!|$)",
        ]
        for pat in goal_patterns:
            m = re.search(pat, lower)
            if m:
                goal = m.group(1).strip()
                if len(goal) > 5 and len(goal) < 100:
                    self.memory.add_goal(goal)

        # Fact patterns
        fact_patterns = [
            r"(?:the\s+)?(?:fact\s+is\s+|truth\s+is\s+)(.+?)(?:\.|!|$)",
            r"(?:i\s+)?(?:live\s+in|work\s+at|study\s+at)\s+(.+?)(?:\.|!|$)",
        ]
        for pat in fact_patterns:
            m = re.search(pat, lower)
            if m:
                self.memory.add_fact(m.group(1).strip())

    def _find_related_goals(self, text: str) -> list[str]:
        """Find goals related to the current input."""
        lower = text.lower()
        related = []
        for goal in self.memory.get_active_goals():
            goal_words = set(goal["goal"].lower().split())
            input_words = set(lower.split())
            overlap = len(goal_words & input_words)
            if overlap >= len(goal_words) * 0.3 and overlap >= 1:
                related.append(goal["goal"])
        return related[:3]

    def continue_conversation(self, user_input: str, previous_response: str) -> dict:
        """Continue a conversation with memory of previous exchange."""
        return self.process(user_input)

    def get_state(self) -> dict:
        return {
            "memory_summary": self.memory.get_summary(),
            "active_goals": self.memory.get_active_goals(),
            "preferences": self.memory._data.get("preferences", {}),
            "interaction_count": len(self.memory._data.get("interactions", [])),
            "last_active": self.memory._data.get("last_active", ""),
        }


# Singleton entity instances
_ENTITIES: dict[str, Entity] = {}
_ENTITY_LOCK = threading.Lock()


def get_entity(user_id: str = "local") -> Entity:
    with _ENTITY_LOCK:
        if user_id not in _ENTITIES:
            _ENTITIES[user_id] = Entity(user_id)
        return _ENTITIES[user_id]
