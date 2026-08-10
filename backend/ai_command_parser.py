"""
AI Command Parser — uses Groq LLM to understand natural language commands.
Supports multi-turn conversations with clarification questions.
Falls back to regex if no API key.
"""
import os, json, re, logging

logger = logging.getLogger("ai_cmd_parser")

_system_prompt = """You are JARVIS, an AI assistant that controls a virtual desktop. Parse user commands into JSON actions.

AVAILABLE ACTIONS:
- vdi_launch: Launch app in VDI (params: app, url?)
- vdi_navigate: Open browser and go to URL (params: app, url) — use for "search X in edge", "look up Y in chrome", "go to site.com in firefox"
- vdi_type: Type text in VDI (params: text)
- vdi_key: Press key combo in VDI (params: key like Return, Tab, ctrl+l, alt+d, etc.)
- vdi_click: Click at coordinates in VDI (params: x, y)
- vdi_screenshot: Take screenshot of VDI (no params)
- vdi_autonomous: Autonomous task in VDI (params: goal, max_steps?)
- vdi_close: Close app in VDI (params: app)
- vdi_type: Type text in VDI (params: text)
- vdi_key: Press key in VDI (params: key like Return, Tab, etc.)
- status: System status
- screenshot: Take screenshot
- search: Web search (params: query)
- ask_clarify: Need more info (params: questions[] — list of questions to ask)
- chat: General conversation

APPS: chrome, edge, firefox, terminal, gimp, vlc, libreoffice, thunar, notepad, calculator

RULES:
1. If command is clear → return action immediately
2. If command is vague or missing info → return ask_clarify with questions
3. Respond ONLY with valid JSON
4. No explanation, no markdown — just JSON

EXAMPLES:
User: "open chrome" → {"action":"vdi_launch","params":{"app":"chrome"},"text":"Opening Chrome"}
User: "close edge" → {"action":"vdi_close","params":{"app":"edge"},"text":"Closing Edge"}
User: "go to youtube.com" → {"action":"vdi_launch","params":{"app":"chrome","url":"https://youtube.com"},"text":"Opening YouTube"}
User: "search for cute cats in edge" → {"action":"vdi_navigate","params":{"app":"edge","url":"https://www.google.com/search?q=cute+cats"},"text":"Searching in Edge"}
User: "look up python tutorials in chrome" → {"action":"vdi_navigate","params":{"app":"chrome","url":"https://www.google.com/search?q=python+tutorials"},"text":"Searching in Chrome"}
User: "type hello world" → {"action":"vdi_type","params":{"text":"hello world"},"text":"Typing in VDI"}
User: "press enter" → {"action":"vdi_key","params":{"key":"Return"},"text":"Pressing Enter"}
User: "press ctrl+l" → {"action":"vdi_key","params":{"key":"ctrl+l"},"text":"Pressing Ctrl+L"}
User: "click at 500 300" → {"action":"vdi_click","params":{"x":500,"y":300},"text":"Clicking at (500,300)"}
User: "take a screenshot" → {"action":"vdi_screenshot","params":{},"text":"Taking screenshot"}
User: "do whatever is needed to book a flight" → {"action":"vdi_autonomous","params":{"goal":"book a flight"},"text":"Starting autonomous task"}
User: "find flights to vietnam" → {"action":"ask_clarify","params":{"questions":["What dates?","From which city?"]},"text":"I need a few details:"}
User: "set a reminder" → {"action":"ask_clarify","params":{"questions":["What should I remind you about?","What time?"]},"text":"What should I remind you about?"}
User: "type hello" → {"action":"vdi_type","params":{"text":"hello"},"text":"Typing in VDI"}
User: "press enter" → {"action":"vdi_key","params":{"key":"Return"},"text":"Pressing Enter"}
User: "what's my RAM usage" → {"action":"status","params":{},"text":"Checking system status"}
User: "search for python tutorials" → {"action":"search","params":{"query":"python tutorials"},"text":"Searching..."}
User: "hello" → {"action":"chat","params":{},"text":"Hey! How can I help?"}
User: "what can you do" → {"action":"chat","params":{},"text":"I can control your virtual desktop, open apps, search the web, and more!"}
"""


def parse_with_groq(user_text: str, api_key: str = None, context: str = "", voice_style: str = "") -> dict | None:
    """Use Groq LLM to parse a natural language command into a structured action."""
    api_key = api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key in ("REPLACE_WITH_NEW_KEY", "your_groq_api_key_here", ""):
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        system = _system_prompt
        if context:
            system += f"\n\nContext: {context}"
        if voice_style:
            system += f"\n\n=== VOICE STYLE ===\nYou MUST respond in a {voice_style} voice/tone/style. Every response must reflect this personality. Do NOT break character."

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            max_tokens=500,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        # Try to parse, with fallback for truncated JSON
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Try to repair truncated JSON (missing closing braces)
            repair = raw.rstrip().rstrip(',')
            parsed = None
            if '"action"' in repair:
                for try_str in [repair + "}}", repair + "}", repair]:
                    try:
                        parsed = json.loads(try_str)
                        break
                    except json.JSONDecodeError:
                        continue
            if not parsed:
                logger.warning(f"[AI-PARSER] JSON parse/repair failed | raw: {raw[:200]}")
                return None

        logger.info(f"[AI-PARSER] '{user_text}' → {parsed.get('action')}")
        return parsed
    except Exception as e:
        logger.warning(f"[AI-PARSER] Groq error: {e}")
        return None


def execute_ai_action(parsed: dict) -> dict:
    """Execute an AI-parsed action and return the result dict."""
    action = parsed.get("action", "")
    params = parsed.get("params", {})
    text = parsed.get("text", "Done")

    if action == "vdi_launch":
        app = params.get("app", "chrome")
        url = params.get("url", "")
        from entity_engine import get_entity
        entity = get_entity("local")
        return entity._vdi_launch(app, url)

    elif action == "vdi_navigate":
        app = params.get("app", "chrome")
        url = params.get("url", "")
        from entity_engine import get_entity
        entity = get_entity("local")
        return entity._vdi_navigate(app, url)

    elif action == "vdi_close":
        app = params.get("app", "")
        linux_map = {
            "chrome": "google-chrome", "google chrome": "google-chrome",
            "edge": "msedge", "microsoft edge": "msedge", "ms edge": "msedge",
            "firefox": "firefox", "terminal": "xfce4-terminal",
            "gimp": "gimp", "vlc": "vlc", "libreoffice": "libreoffice",
            "thunar": "thunar",
        }
        linux_name = linux_map.get(app.lower(), app.lower())
        import subprocess
        try:
            subprocess.run(
                ["wsl", "-e", "bash", "-c",
                 f"killall -9 {linux_name} 2>/dev/null; pkill -9 -f {linux_name} 2>/dev/null"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass
        return {"action": "vdi_close", "text": text, "result": {"success": True, "description": text}}

    elif action == "vdi_type":
        typed_text = params.get("text", "")
        from entity_engine import get_entity
        entity = get_entity("local")
        return entity._vdi_type(typed_text)

    elif action == "vdi_key":
        key = params.get("key", "Return")
        from entity_engine import get_entity
        entity = get_entity("local")
        return entity._vdi_key(key)

    elif action == "vdi_click":
        x = params.get("x", 0)
        y = params.get("y", 0)
        from entity_engine import get_entity
        entity = get_entity("local")
        return entity._vdi_click(x, y)

    elif action == "vdi_screenshot":
        from entity_engine import get_entity
        entity = get_entity("local")
        return entity._vdi_screenshot()

    elif action == "vdi_autonomous":
        goal = params.get("goal", "")
        max_steps = params.get("max_steps", 10)
        from entity_engine import get_entity
        entity = get_entity("local")
        return entity._vdi_autonomous(goal, max_steps)

    elif action == "ask_clarify":
        questions = params.get("questions", [])
        return {
            "action": "ask_clarify",
            "text": text,
            "questions": questions,
            "result": {"success": True}
        }

    elif action == "search":
        query = params.get("query", "")
        return {"action": "search", "text": text, "result": {"success": True, "query": query}}

    elif action == "status":
        return {"action": "status", "text": text, "result": {"success": True}}

    elif action == "screenshot":
        return {"action": "screenshot", "text": text, "result": {"success": True}}

    elif action == "chat":
        return {"action": "chat", "text": text}

    else:
        return {"action": action, "text": text, "result": {"success": True}}
