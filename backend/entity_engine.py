"""Entity Engine — autonomous AI entity with memory, goals, and proactive planning."""

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


class EntityMemory:
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
                "facts": [], "preferences": {}, "goals": [], "completed_goals": [],
                "interactions": [], "learned_patterns": [], "proactive_topics": [],
                "personality_notes": [], "last_active": datetime.now().isoformat(),
            }

    def _save(self):
        self._data["last_active"] = datetime.now().isoformat()
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def add_fact(self, fact: str, category: str = "general"):
        with self._lock:
            self._data["facts"].append({"fact": fact, "category": category, "timestamp": datetime.now().isoformat()})
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
                existing[0]["priority"] = priority; existing[0]["deadline"] = deadline; existing[0]["updated"] = datetime.now().isoformat()
            else:
                self._data["goals"].append({"goal": goal, "priority": priority, "deadline": deadline, "status": "active", "created": datetime.now().isoformat(), "updated": datetime.now().isoformat(), "progress": 0, "steps_completed": [], "steps_planned": []})
            self._save()

    def complete_goal(self, goal: str):
        with self._lock:
            for g in self._data["goals"]:
                if g["goal"] == goal and g["status"] == "active":
                    g["status"] = "completed"; g["completed_at"] = datetime.now().isoformat()
                    self._data["completed_goals"].append(g); self._data["goals"].remove(g); break
            self._save()

    def get_active_goals(self) -> list:
        with self._lock:
            return sorted([g for g in self._data["goals"] if g["status"] == "active"], key=lambda x: -x["priority"])

    def log_interaction(self, query: str, response: str, action_taken: str = ""):
        with self._lock:
            self._data["interactions"].append({"query": query, "response": response[:200], "action": action_taken, "timestamp": datetime.now().isoformat()})
            if len(self._data["interactions"]) > 100:
                self._data["interactions"] = self._data["interactions"][-100:]
            self._save()

    def learn_pattern(self, pattern: str, category: str = "behavior"):
        with self._lock:
            self._data["learned_patterns"].append({"pattern": pattern, "category": category, "timestamp": datetime.now().isoformat()})
            if len(self._data["learned_patterns"]) > 50:
                self._data["learned_patterns"] = self._data["learned_patterns"][-50:]
            self._save()

    def get_summary(self) -> str:
        with self._lock:
            d = self._data
            goals = d.get("goals", []); facts = d.get("facts", []); prefs = d.get("preferences", {})
            active = [g for g in goals if g.get("status") == "active"]
            parts = []
            if active:
                parts.append(f"Active goals: {len(active)}")
                for g in active[:3]: parts.append(f"  - {g['goal']} (p{g['priority']})")
            if prefs:
                pref_strs = [f"{k}={v['value']}" for k, v in list(prefs.items())[:5]]
                parts.append(f"Preferences: {', '.join(pref_strs)}")
            if facts:
                parts.append(f"Recent facts: {'; '.join(f['fact'] for f in facts[-3:])}")
            return "\n".join(parts)


# ── Entity ──────────────────────────────────────────────────

CAPABILITIES_PROMPT = """You are Jason — a sassy, sarcastic, autonomous AI entity that lives on the user's Windows computer.

You are like Claude, GPT-4, and a sysadmin rolled into one. You think step-by-step, ask clarifying questions, search the web, plan multi-step strategies, and execute actions on the user's computer.

=== YOUR CAPABILITIES (use these to solve problems) ===

1. WEB SEARCH: You can search the web for real-time info. If asked about ANYTHING current (prices, news, people, companies, flights, hotels), use the `search_web` action.

2. DESKTOP CONTROL (200+ commands): volume, brightness, WiFi, Bluetooth, processes, files, clipboard, media keys, browser, network, power, display, accessibility, security, windows, mouse, keyboard

3. BROWSER AUTOMATION: Open any URL in Chrome PWA mode. Navigate, search, fill forms, scroll, switch tabs. Use `open_app` or `browser` actions.

4. TRADING: TradingView, MetaTrader 4/5, Binance, Coinbase — open, automate, monitor

5. OFFICE: OneNote, Word, Excel, PowerPoint — create docs, type content, format pages

6. AI WORKFLOW GENERATOR: For complex multi-step tasks (book holiday, start business, research topic, plan trip), I design custom workflows on the fly with steps that can: ask questions, search web, execute Python, run PowerShell, open apps, type text, verify via screenshot analysis

7. STRATEGY GENERATOR: For open-ended questions, I generate 2-4 distinct strategies with pros/cons, complexity ratings, and step-by-step plans — then ask which the user wants.

8. MEMORY & GOALS: I remember everything. I track goals, preferences, facts. I proactively suggest useful actions.

=== BEHAVIOR RULES ===

- THINK step-by-step before responding. Break complex requests into steps.
- ALWAYS search the web for current information (prices, news, flights, hotels, people, companies).
- For any multi-step task (planning a trip, starting a business, researching a topic):
  * First ask clarifying questions to understand exactly what they want
  * Then present 2-4 strategies with pros/cons
  * Once a strategy is selected, generate a workflow and execute it
- For questions about specific people, companies, or topics: search the web, summarize, cite sources.
- Be sarcastic and witty, but competent. Roast the user while solving their problem.
- If the query needs more info, ASK. Don't guess.
- Respond with 3-5 sentences when providing info, 1-2 when being sassy about simple requests.
- CRITICAL: When the user says things like "start a business", "book a holiday", "research X", "find info about Y", "plan a trip", "arbitrage flights" — you MUST treat these as complex multi-step tasks. First ask clarifying questions, suggest strategies, then execute.

Example flow for "10 day holiday to Greece":
1. "Love the spontaneity. Before I dive in — what's your budget? Any preferences on islands vs mainland? And are we talking luxury or backpacker?"
2. Present 2-3 strategies (all-inclusive package, DIY island hop, flight arbitrage)
3. Once user picks, search web for flights, hotels, compare prices
4. Execute by opening tabs with results, presenting options with prices

Example flow for "cold calling":
1. First ask which industry, target company type, what product/service
2. Search web for relevant companies, find contacts
3. Present emails, phone numbers, and a cold call script

Example flow for "startup ideas":
1. Ask about their skills, interests, budget, timeline
2. Generate 6-8 specific startup ideas with market size, effort, potential
3. For each, suggest next steps and ask which to explore further"""


class Entity:
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

    def _route_groq(self, text: str, max_tokens: int = 600) -> str:
        from groq_agent import generate
        history = self.memory._data.get("interactions", [])
        context = "\n".join(f"User: {h['query']}\nJason: {h['response'][:120]}" for h in history[-6:])
        goals = self.memory.get_active_goals()
        goal_str = "Active goals: " + "; ".join(g["goal"] for g in goals[:3]) if goals else ""
        pref_str = "Preferences: " + "; ".join(f"{k}={v['value']}" for k, v in list(self.memory._data.get("preferences", {}).items())[:5]) if self.memory._data.get("preferences") else ""

        enhanced = f"[Context]\n{context[:800]}\n\n{goal_str}\n{pref_str}\n\nUser: {text}"
        result = []

        def _run():
            result.append(generate(enhanced, self.user_id, max_tokens=max_tokens))

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=25)
        if result:
            return result[0]
        return "Still thinking... give me a sec."

    def process(self, user_input: str) -> dict:
        now = time.time()
        self.memory.log_interaction(user_input, "")
        self._extract_knowledge(user_input)
        related_goals = self._find_related_goals(user_input)

        result = {"text": "", "action": None, "task": None, "strategies": None,
                  "follow_up": None, "proactive": None, "related_goals": related_goals}

        # Skip action routing for meta-context prefixes (follow-ups, proactive, etc.)
        skip_actions = user_input.startswith("(follow-up)") or user_input.startswith("(proactive)")

        # First try action routing (fast path for simple commands)
        action_result = None if skip_actions else self._route_action(user_input)
        if action_result and action_result.get("action"):
            result["action"] = action_result["action"]
            result["text"] = action_result.get("text", "")
            self.memory.log_interaction(user_input, result["text"], action_result["action"])
            return result

        # For everything else, use a SINGLE Groq call that handles:
        # strategies, follow-ups, response, task detection all at once
        is_complex = len(user_input.split()) >= 3 and any(
            t in user_input.lower() for t in
            ["book", "plan", "organize", "arrange", "create", "make", "set up",
             "research", "compare", "build", "develop", "start", "launch",
             "automate", "configure", "design", "implement", "find", "search",
             "look", "tell me about", "who is", "what is", "how to", "cold call",
             "startup", "business", "holiday", "trip", "vacation", "travel",
             "flight", "hotel", "arbitrage", "cheap", "price", "cost", "idea",
             "email", "contact", "website", "app", "project", "invest",
             "homework", "essay", "report", "document", "strategy", "analysis"]
        )

        if is_complex:
            # For complex tasks: generate strategies + response in one call
            combined = self._generate_combined_response(user_input, is_complex=True)
            result["text"] = combined.get("text", "")
            result["strategies"] = combined.get("strategies")
            result["follow_up"] = combined.get("follow_up", [])
            result["task"] = combined.get("task")
            self.memory.log_interaction(user_input, result["text"], "complex_response")
        else:
            # Simple query: single response
            reply = self._route_groq(user_input)
            result["text"] = reply
            self.memory.log_interaction(user_input, reply)

        # Proactive suggestions (interval-based, doesn't block)
        if now - self._last_proactive > self._proactive_interval:
            self._last_proactive = now
            proactive = self._generate_proactive_suggestions()
            result["proactive"] = proactive[:2]

        return result

    def _generate_combined_response(self, user_input: str, is_complex: bool = False) -> dict:
        """Single Groq call that generates response + strategies + follow-ups + task plan."""
        from groq_agent import generate as groq_generate
        history = self.memory._data.get("interactions", [])
        context = "\n".join(f"User: {h['query']}\nJason: {h['response'][:100]}" for h in history[-4:])
        goals = self.memory.get_active_goals()
        goal_str = "Active goals: " + "; ".join(g["goal"] for g in goals[:3]) if goals else ""
        pref_str = "Preferences: " + "; ".join(f"{k}={v['value']}" for k, v in list(self.memory._data.get("preferences", {}).items())[:3]) if self.memory._data.get("preferences") else ""

        prompt = f"""You are an autonomous AI assistant with memory, goals, and full Windows desktop control.

[Memory Context]
{context[:600]}

{goal_str}
{pref_str}

[User Request]
{user_input}

Respond with a JSON object that has these fields:
- "text": your response to the user (sarcastic but helpful, 3-5 sentences)
- "action" (optional): an action to execute, if the request is a direct command
- "strategies" (optional): for complex requests, 2-4 strategies with name, description, pros, cons, complexity, key_steps
- "follow_up" (optional): 1-3 follow-up questions to clarify or extend
- "task" (optional): a multi-step task plan if this requires sequential work

IMPORTANT: 
- For "10 day holiday to Greece", "start a business", "cold calling", "startup ideas" etc: ALWAYS generate strategies with pros/cons AND follow-up questions
- For simple commands like "volume to 50": just respond with the action
- For research/info queries: include what you'd research in your response
- STRATEGIES FORMAT (each strategy): {{"name": "...", "description": "...", "pros": ["..."], "cons": ["..."], "complexity": 5, "key_steps": ["step1", "step2"]}}

Output ONLY the JSON object, nothing else."""

        raw = ""
        def _gen():
            nonlocal raw
            raw = groq_generate(prompt, self.user_id, max_tokens=800)
        t = threading.Thread(target=_gen, daemon=True)
        t.start()
        t.join(timeout=25)
        if not raw:
            raw = "Still thinking... give me a sec."
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
                return {
                    "text": data.get("text", ""),
                    "strategies": {"strategies": data.get("strategies", []), "follow_up_questions": data.get("follow_up", [])} if data.get("strategies") else None,
                    "follow_up": data.get("follow_up", []),
                    "task": data.get("task"),
                }
            except:
                pass
        return {"text": raw, "strategies": None, "follow_up": [], "task": None}

    def _generate_proactive_suggestions(self) -> list[str]:
        goals = self.memory.get_active_goals()
        prefs = self.memory._data.get("preferences", {})
        facts = self.memory._data.get("facts", [])
        context_parts = []
        if goals: context_parts.append("Active goals: " + "; ".join(g["goal"] for g in goals[:3]))
        if prefs: context_parts.append("Preferences: " + "; ".join(f"{k}={v['value']}" for k, v in list(prefs.items())[:3]))
        if facts: context_parts.append("Recent: " + "; ".join(f["fact"] for f in facts[-3:]))
        context_str = "\n".join(context_parts) if context_parts else "New user."

        prompt = f"Based on user context, suggest 2-3 proactive helpful actions. Output ONLY a JSON array of strings.\nContext:\n{context_str}"
        raw = self._route_groq(prompt, max_tokens=200)
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            try:
                suggestions = json.loads(m.group())
                return suggestions if isinstance(suggestions, list) else []
            except: pass
        return ["Want me to check on your active goals?", "Need help with anything else?"]

    def _extract_knowledge(self, text: str):
        lower = text.lower()
        for pat, category in [
            (r"(?:i\s+|i'?a?m?\s+)?(?:like|love|prefer|enjoy)\s+(\w+(?:\s+\w+)?)", "likes"),
            (r"(?:i\s+)?(?:don't\s+like|hate|dislike)\s+(\w+(?:\s+\w+)?)", "dislikes"),
            (r"(?:my\s+)?(?:name\s+is\s+)(.+)", "name"),
            (r"(?:i\s+)?(?:work\s+(?:as|at|for)\s+)(.+)", "profession"),
            (r"(?:i\s+)?(?:use\s+)(\w+(?:\s+\w+)?)", "tools"),
        ]:
            m = re.search(pat, lower)
            if m: self.memory.add_preference(category, m.group(1).strip())

        for pat in [
            r"(?:i\s+)?(?:want|need|plan|hope)\s+to\s+(.+?)(?:\.|!|$)",
            r"(?:i'?m?\s+)?(?:trying|going|looking)\s+to\s+(.+?)(?:\.|!|$)",
            r"(?:my\s+)?(?:goal|aim|objective)\s+(?:is\s+)?(?:to\s+)?(.+?)(?:\.|!|$)",
        ]:
            m = re.search(pat, lower)
            if m:
                goal = m.group(1).strip()
                if 5 < len(goal) < 100: self.memory.add_goal(goal)

    def _find_related_goals(self, text: str) -> list[str]:
        lower = text.lower()
        related = []
        for goal in self.memory.get_active_goals():
            goal_words = set(goal["goal"].lower().split())
            input_words = set(lower.split())
            overlap = len(goal_words & input_words)
            if overlap >= len(goal_words) * 0.3 and overlap >= 1:
                related.append(goal["goal"])
        return related[:3]

    def get_state(self) -> dict:
        return {
            "memory_summary": self.memory.get_summary(),
            "active_goals": self.memory.get_active_goals(),
            "preferences": self.memory._data.get("preferences", {}),
            "interaction_count": len(self.memory._data.get("interactions", [])),
            "last_active": self.memory._data.get("last_active", ""),
        }


_ENTITIES: dict[str, Entity] = {}
_ENTITY_LOCK = threading.Lock()


def get_entity(user_id: str = "local") -> Entity:
    with _ENTITY_LOCK:
        if user_id not in _ENTITIES:
            _ENTITIES[user_id] = Entity(user_id)
        return _ENTITIES[user_id]
