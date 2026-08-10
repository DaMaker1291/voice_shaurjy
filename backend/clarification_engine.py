"""JARVIS Grouped Clarification Engine.

Detects ALL missing parameters for a complex request and asks
grouped follow-up questions in a single prompt.

Example:
  USER: "Find me a cheap 5-star holiday to Vietnam."
  JARVIS: "Before I search, I need:
    1. Where are you flying from?
    2. Approximate dates or date flexibility?
    3. Number of travellers?
    4. Maximum total budget?
    5. Any region preference in Vietnam?"

Instead of asking one question at a time.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

log = logging.getLogger("clarification_engine")


@dataclass
class MissingParam:
    """A parameter that is missing from the user's request."""
    name: str
    description: str
    priority: str = "high"  # high, medium, low
    example: str = ""
    group: str = "general"  # For grouped display
    required: bool = True


@dataclass
class ClarificationPlan:
    """A plan for what to ask the user."""
    missing_params: List[MissingParam] = field(default_factory=list)
    grouped_question: str = ""
    assumptions_would_make: List[str] = field(default_factory=list)
    can_proceed_with_defaults: bool = False
    defaults: Dict[str, str] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
#  REQUEST TYPE DETECTION & PARAMETER REQUIREMENTS
# ══════════════════════════════════════════════════════════════

REQUEST_PARAM_MAP: Dict[str, List[MissingParam]] = {
    "travel": [
        MissingParam("origin", "departure city/airport", "high", "e.g. London, NYC", "logistics"),
        MissingParam("dates", "travel dates or flexibility", "high", "e.g. October, 15-22 Dec", "logistics"),
        MissingParam("duration", "trip length in nights", "medium", "e.g. 7 nights", "logistics"),
        MissingParam("travellers", "number of travellers", "high", "e.g. 2 adults", "logistics"),
        MissingParam("budget", "maximum total budget", "high", "e.g. under £1,500", "preferences"),
        MissingParam("region", "preferred region/area", "low", "e.g. Da Nang, Phu Quoc", "preferences"),
        MissingParam("hotel_stars", "hotel star rating", "low", "e.g. 5-star", "preferences"),
        MissingParam("flight_class", "flight class preference", "low", "e.g. economy", "preferences"),
    ],
    "research": [
        MissingParam("scope", "research scope/depth", "medium", "e.g. overview, deep dive", "parameters"),
        MissingParam("purpose", "purpose/audience", "medium", "e.g. academic, business", "parameters"),
        MissingParam("format", "desired output format", "low", "e.g. paper, summary, report", "parameters"),
        MissingParam("length", "desired length", "low", "e.g. 2000 words, 10 pages", "parameters"),
        MissingParam("sources", "preferred source types", "low", "e.g. academic only, news", "parameters"),
    ],
    "software": [
        MissingParam("language", "programming language", "high", "e.g. Python, TypeScript", "technical"),
        MissingParam("framework", "framework/platform", "medium", "e.g. React, FastAPI", "technical"),
        MissingParam("features", "core features list", "high", "e.g. auth, dashboard, API", "requirements"),
        MissingParam("platform", "target platform", "medium", "e.g. web, desktop, mobile", "requirements"),
        MissingParam("deployment", "deployment target", "low", "e.g. Docker, Vercel", "technical"),
    ],
    "design": [
        MissingParam("style", "visual style", "medium", "e.g. minimalist, corporate", "aesthetic"),
        MissingParam("colors", "color preferences", "low", "e.g. dark theme, blue accent", "aesthetic"),
        MissingParam("dimensions", "dimensions/size", "high", "e.g. 1920x1080, A4", "technical"),
        MissingParam("format", "output format", "medium", "e.g. PNG, SVG, PSD", "technical"),
    ],
    "email": [
        MissingParam("recipient", "recipient name/email", "high", "e.g. john@example.com", "delivery"),
        MissingParam("subject", "email subject", "high", "e.g. Meeting Follow-up", "content"),
        MissingParam("tone", "desired tone", "medium", "e.g. formal, friendly", "content"),
        MissingParam("key_points", "key points to include", "high", "e.g. agenda, deadlines", "content"),
    ],
    "file_operation": [
        MissingParam("file_path", "file path/location", "high", "e.g. ~/Documents/report.pdf", "technical"),
        MissingParam("file_name", "file name", "medium", "e.g. my_report.pdf", "technical"),
    ],
    "application": [
        MissingParam("app_name", "application name", "high", "e.g. Chrome, VS Code", "technical"),
    ],
}


def detect_request_type(text: str) -> str:
    """Detect the type of request from user text."""
    text_lower = text.lower()

    travel_keywords = [
        "holiday", "vacation", "trip", "travel", "flight", "hotel",
        "resort", "booking", "visit", "destination", "fly to",
        "cheapest", "best price", "deal", "airbnb",
    ]
    if any(kw in text_lower for kw in travel_keywords):
        return "travel"

    research_keywords = [
        "research", "paper", "study", "analysis", "report", "investigate",
        "literature", "survey", "review", "summarize", "write about",
    ]
    if any(kw in text_lower for kw in research_keywords):
        return "research"

    software_keywords = [
        "build", "app", "website", "application", "code", "program",
        "software", "develop", "create a", "implement", "api",
        "database", "frontend", "backend",
    ]
    if any(kw in text_lower for kw in software_keywords):
        return "software"

    design_keywords = [
        "design", "logo", "banner", "ui", "ux", "mockup", "wireframe",
        "illustration", "graphic", "animation", "3d", "render",
    ]
    if any(kw in text_lower for kw in design_keywords):
        return "design"

    email_keywords = [
        "email", "mail", "send", "compose", "write to", "message",
    ]
    if any(kw in text_lower for kw in email_keywords):
        return "email"

    file_keywords = [
        "file", "document", "folder", "save", "create file",
        "read file", "open file",
    ]
    if any(kw in text_lower for kw in file_keywords):
        return "file_operation"

    app_keywords = [
        "open", "launch", "start", "close", "run",
    ]
    if any(kw in text_lower for kw in app_keywords):
        return "application"

    return "general"


def _extract_provided_params(text: str, request_type: str) -> Dict[str, str]:
    """Extract parameters the user has already provided."""
    provided = {}
    text_lower = text.lower()

    if request_type == "travel":
        # Origin detection
        origin_patterns = [
            r"(?:from|flying from|departing from)\s+([A-Za-z\s]+?)(?:\s+to|\s+for|\s+in|\s*,|\s*$)",
            r"(?:london|nyc|new york|paris|tokyo|dubai|singapore|manchester|birmingham|los angeles|san francisco|chicago|miami)",
        ]
        for p in origin_patterns:
            m = re.search(p, text, re.I)
            if m:
                provided["origin"] = m.group(1) if m.lastindex else m.group(0)
                break

        # Date detection
        date_patterns = [
            r"(?:january|february|march|april|may|june|july|august|september|october|november|december)",
            r"(?:next\s+month|this\s+month|tomorrow|next\s+week)",
            r"\d{1,2}(?:st|nd|rd|th)?\s*(?:to|-)\s*\d{1,2}(?:st|nd|rd|th)?",
        ]
        for p in date_patterns:
            m = re.search(p, text, re.I)
            if m:
                provided["dates"] = m.group(0)
                break

        # Travellers
        travellers_match = re.search(r"(\d+)\s*(?:adult|people|person|traveller|guest|passenger)", text, re.I)
        if travellers_match:
            provided["travellers"] = travellers_match.group(0)

        # Budget
        budget_match = re.search(r"(?:under|below|max|budget|price|cost|spend)\s*[£$€]?\s*(\d[\d,]*)", text, re.I)
        if budget_match:
            provided["budget"] = budget_match.group(0)

        # Duration
        duration_match = re.search(r"(\d+)\s*(?:night|day|week)", text, re.I)
        if duration_match:
            provided["duration"] = duration_match.group(0)

        # Stars
        stars_match = re.search(r"(\d)[\s-]*star", text, re.I)
        if stars_match:
            provided["hotel_stars"] = stars_match.group(0)

    elif request_type == "software":
        # Language
        lang_patterns = [
            r"(?:in|using|with)\s+(python|javascript|typescript|java|c\+\+|rust|go|ruby|php|swift|kotlin)",
        ]
        for p in lang_patterns:
            m = re.search(p, text, re.I)
            if m:
                provided["language"] = m.group(1)
                break

        # Framework
        fw_patterns = [
            r"(?:using|with|in)\s+(react|next\.?js|vue|angular|fastapi|django|flask|express|spring|rails)",
        ]
        for p in fw_patterns:
            m = re.search(p, text, re.I)
            if m:
                provided["framework"] = m.group(1)
                break

    return provided


def analyze_and_plan(text: str, context: str = "") -> ClarificationPlan:
    """Analyze a user request and create a clarification plan.

    Detects missing parameters, groups them, and generates
    a single grouped question prompt.
    """
    request_type = detect_request_type(text)

    if request_type == "general":
        # Check if the request is actually clear enough to proceed
        if len(text.split()) >= 5:
            return ClarificationPlan(
                can_proceed_with_defaults=True,
                grouped_question="",
            )
        return ClarificationPlan(
            missing_params=[
                MissingParam("intent", "what you'd like me to do", "high",
                           "e.g. search the web, open an app, create a file")
            ],
            grouped_question="What would you like me to do?",
        )

    # Get required params for this request type
    required_params = REQUEST_PARAM_MAP.get(request_type, [])

    # Extract what the user already provided
    provided = _extract_provided_params(text, request_type)

    # Find missing params
    missing = []
    for param in required_params:
        if param.name not in provided:
            missing.append(param)

    if not missing:
        return ClarificationPlan(
            can_proceed_with_defaults=True,
            grouped_question="",
        )

    # Group params by their group field
    groups: Dict[str, List[MissingParam]] = {}
    for p in missing:
        if p.group not in groups:
            groups[p.group] = []
        groups[p.group].append(p)

    # Build grouped question
    question_parts = ["Before I proceed, I need a few details:"]
    param_num = 1
    for group_name, params in groups.items():
        if len(groups) > 1:
            question_parts.append(f"\n{group_name.title()}:")
        for p in params:
            example = f" (e.g. {p.example})" if p.example else ""
            question_parts.append(f"  {param_num}. {p.description}{example}")
            param_num += 1

    grouped_question = "\n".join(question_parts)

    # Generate assumptions that could be made
    assumptions = []
    if request_type == "travel":
        assumptions.extend([
            "Assume economy class flights",
            "Assume bed & breakfast or half-board hotel",
            "Assume direct or 1-stop flights",
        ])
    elif request_type == "software":
        assumptions.extend([
            "Assume modern tech stack",
            "Assume responsive design",
            "Assume standard testing setup",
        ])

    return ClarificationPlan(
        missing_params=missing,
        grouped_question=grouped_question,
        assumptions_would_make=assumptions,
        can_proceed_with_defaults=False,
        defaults={},
    )


def generate_clarification_response(text: str, context: str = "") -> str:
    """Generate a natural clarification response.

    This is the main entry point for the grouped clarification engine.
    Returns a single grouped question if clarification is needed,
    or empty string if the request is clear enough.
    """
    plan = analyze_and_plan(text, context)

    if plan.can_proceed_with_defaults:
        return ""

    if plan.grouped_question:
        return plan.grouped_question

    return ""


def needs_clarification_grouped(text: str) -> Tuple[bool, str, ClarificationPlan]:
    """Check if a request needs grouped clarification.

    Returns (needs_it, question, plan).
    """
    plan = analyze_and_plan(text)
    needs_it = not plan.can_proceed_with_defaults and bool(plan.missing_params)
    return needs_it, plan.grouped_question, plan
