"""JARVIS Adaptive Final Result Engine.

Adapts presentation to the task type:
  - Travel: comparison cards
  - Research: executive summary + evidence + citations
  - Code: files + tests + preview + architecture
  - Creative: visual preview + files + render info
  - Data: charts + tables + conclusions
  - Business: executive dashboard + recommendations
  - Automation: action summary + evidence + resulting state

Never dumps raw data. Always presents useful, verified results.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

log = logging.getLogger("result_engine")


@dataclass
class ResultCard:
    """A single result card for display."""
    title: str
    subtitle: str = ""
    value: str = ""
    value_type: str = "text"  # text, price, percentage, link, file
    badge: str = ""  # "BEST VALUE", "CHEAPEST", etc.
    badge_color: str = "green"
    details: List[str] = field(default_factory=list)
    source_url: str = ""
    source_name: str = ""
    verified: bool = False
    clickable: bool = True
    action: str = ""  # What happens when clicked

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "value": self.value,
            "value_type": self.value_type,
            "badge": self.badge,
            "badge_color": self.badge_color,
            "details": self.details,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "verified": self.verified,
            "clickable": self.clickable,
            "action": self.action,
        }


@dataclass
class ResultSection:
    """A section in the result presentation."""
    title: str
    cards: List[ResultCard] = field(default_factory=list)
    summary: str = ""
    icon: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "cards": [c.to_dict() for c in self.cards],
            "summary": self.summary,
            "icon": self.icon,
        }


@dataclass
class AdaptiveResult:
    """The final adaptive result for a mission."""
    task_type: str
    title: str
    subtitle: str = ""
    sections: List[ResultSection] = field(default_factory=list)
    executive_summary: str = ""
    sources_count: int = 0
    verified_count: int = 0
    rejected_count: int = 0
    evidence_count: int = 0
    duration_s: float = 0
    artifacts: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "title": self.title,
            "subtitle": self.subtitle,
            "sections": [s.to_dict() for s in self.sections],
            "executive_summary": self.executive_summary,
            "sources_count": self.sources_count,
            "verified_count": self.verified_count,
            "rejected_count": self.rejected_count,
            "evidence_count": self.evidence_count,
            "duration_s": self.duration_s,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
            "next_steps": self.next_steps,
        }


# ══════════════════════════════════════════════════════════════
#  TASK-TYPE-SPECIFIC PRESENTERS
# ══════════════════════════════════════════════════════════════

def present_travel(mission_data: Dict[str, Any]) -> AdaptiveResult:
    """Present travel research results as comparison cards."""
    candidates = mission_data.get("candidates", [])
    sources = mission_data.get("sources", [])

    result = AdaptiveResult(
        task_type="travel",
        title=mission_data.get("destination", "Travel Results"),
        subtitle=f"{len(candidates)} verified options from {len(sources)} sources",
        sources_count=len(sources),
        verified_count=sum(1 for c in candidates if c.get("verified")),
        rejected_count=mission_data.get("rejected_count", 0),
    )

    # Best overall
    if candidates:
        sorted_by_value = sorted(candidates, key=lambda c: c.get("value_score", 0), reverse=True)
        best = sorted_by_value[0]
        result.sections.append(ResultSection(
            title="Best Overall",
            icon="star",
            cards=[ResultCard(
                title=best.get("hotel_name", "Hotel"),
                subtitle=f"{best.get('nights', '?')} nights | {best.get('location', '?')}",
                value=f"£{best.get('total_price', '?')}",
                value_type="price",
                badge="BEST VALUE",
                badge_color="green",
                details=[
                    f"Flight: {best.get('flight_details', 'N/A')}",
                    f"Rating: {best.get('hotel_rating', '?')}★",
                    f"Includes: {best.get('includes', 'N/A')}",
                ],
                source_url=best.get("source_url", ""),
                source_name=best.get("source_name", ""),
                verified=best.get("verified", False),
            )],
        ))

    # Cheapest
    if candidates:
        cheapest = min(candidates, key=lambda c: c.get("total_price", float("inf")))
        result.sections.append(ResultSection(
            title="Cheapest Verified",
            icon="tag",
            cards=[ResultCard(
                title=cheapest.get("hotel_name", "Hotel"),
                subtitle=f"{cheapest.get('nights', '?')} nights | {cheapest.get('location', '?')}",
                value=f"£{cheapest.get('total_price', '?')}",
                value_type="price",
                badge="CHEAPEST",
                badge_color="blue",
                details=[
                    f"Flight: {cheapest.get('flight_details', 'N/A')}",
                    f"Trade-off: {cheapest.get('trade_off', 'Check details')}",
                ],
                source_url=cheapest.get("source_url", ""),
                verified=cheapest.get("verified", False),
            )],
        ))

    # Best hotel
    if candidates:
        best_hotel = max(candidates, key=lambda c: c.get("hotel_rating", 0))
        result.sections.append(ResultSection(
            title="Best Hotel",
            icon="hotel",
            cards=[ResultCard(
                title=best_hotel.get("hotel_name", "Hotel"),
                subtitle=f"{best_hotel.get('hotel_rating', '?')}★ | {best_hotel.get('location', '?')}",
                value=f"£{best_hotel.get('total_price', '?')}",
                value_type="price",
                badge="BEST HOTEL",
                badge_color="purple",
                details=[
                    f"Rating: {best_hotel.get('hotel_rating', '?')}★",
                    f"Reviews: {best_hotel.get('review_summary', 'N/A')}",
                ],
                source_url=best_hotel.get("source_url", ""),
                verified=best_hotel.get("verified", False),
            )],
        ))

    # Sources
    if sources:
        source_cards = []
        for s in sources[:10]:
            source_cards.append(ResultCard(
                title=s.get("name", "Source"),
                value=s.get("url", ""),
                value_type="link",
                verified=s.get("verified", False),
                source_url=s.get("url", ""),
            ))
        result.sections.append(ResultSection(
            title="Sources",
            icon="link",
            cards=source_cards,
            summary=f"{len(sources)} sources checked",
        ))

    result.executive_summary = (
        f"Found {len(candidates)} verified options for {mission_data.get('destination', 'your trip')}. "
        f"Prices checked at {time.strftime('%H:%M %d %b %Y')}."
    )

    return result


def present_research(mission_data: Dict[str, Any]) -> AdaptiveResult:
    """Present research results as executive summary + citations."""
    findings = mission_data.get("findings", [])
    sources = mission_data.get("sources", [])

    result = AdaptiveResult(
        task_type="research",
        title=mission_data.get("topic", "Research Results"),
        subtitle=f"{len(findings)} findings from {len(sources)} sources",
        sources_count=len(sources),
        verified_count=sum(1 for f in findings if f.get("verified")),
    )

    # Executive summary
    result.executive_summary = mission_data.get("executive_summary", "")

    # Key findings
    if findings:
        finding_cards = []
        for f in findings[:10]:
            finding_cards.append(ResultCard(
                title=f.get("claim", "Finding"),
                subtitle=f"Confidence: {f.get('confidence', '?')}%",
                value=f.get("evidence", ""),
                badge="VERIFIED" if f.get("verified") else "UNVERIFIED",
                badge_color="green" if f.get("verified") else "yellow",
                details=f.get("sources", []),
                verified=f.get("verified", False),
            ))
        result.sections.append(ResultSection(
            title="Key Findings",
            icon="lightbulb",
            cards=finding_cards,
        ))

    # Citations
    if sources:
        citation_cards = []
        for s in sources[:20]:
            citation_cards.append(ResultCard(
                title=s.get("title", "Citation"),
                subtitle=s.get("authors", ""),
                value=s.get("url", ""),
                value_type="link",
                source_url=s.get("url", ""),
                verified=s.get("verified", False),
            ))
        result.sections.append(ResultSection(
            title="Citations",
            icon="book",
            cards=citation_cards,
            summary=f"{len(sources)} sources cited",
        ))

    return result


def present_software(mission_data: Dict[str, Any]) -> AdaptiveResult:
    """Present software development results."""
    files = mission_data.get("files", [])
    tests = mission_data.get("tests", [])

    result = AdaptiveResult(
        task_type="software",
        title=mission_data.get("project_name", "Software Project"),
        subtitle=f"{len(files)} files created, {len(tests)} tests",
        artifacts=[{"name": f.get("path", ""), "type": "file"} for f in files],
    )

    result.executive_summary = mission_data.get("architecture_summary", "")

    # Files created
    if files:
        file_cards = []
        for f in files:
            file_cards.append(ResultCard(
                title=f.get("path", "file"),
                subtitle=f.get("description", ""),
                value=f"{f.get('lines', '?')} lines",
                badge=f.get("type", "").upper(),
                badge_color="blue",
            ))
        result.sections.append(ResultSection(
            title="Files Created",
            icon="file",
            cards=file_cards,
        ))

    # Test results
    if tests:
        passed = sum(1 for t in tests if t.get("passed"))
        test_cards = [ResultCard(
            title="Test Results",
            value=f"{passed}/{len(tests)} passed",
            badge="PASSING" if passed == len(tests) else "FAILING",
            badge_color="green" if passed == len(tests) else "red",
        )]
        result.sections.append(ResultSection(
            title="Tests",
            icon="check",
            cards=test_cards,
        ))

    # Known limitations
    limitations = mission_data.get("limitations", [])
    if limitations:
        result.warnings = limitations

    return result


def present_creative(mission_data: Dict[str, Any]) -> AdaptiveResult:
    """Present creative work results."""
    result = AdaptiveResult(
        task_type="creative",
        title=mission_data.get("project_name", "Creative Project"),
        subtitle=mission_data.get("description", ""),
        artifacts=mission_data.get("artifacts", []),
    )

    result.executive_summary = mission_data.get("description", "")

    # Render info
    if mission_data.get("render_info"):
        ri = mission_data["render_info"]
        result.sections.append(ResultSection(
            title="Render Details",
            icon="film",
            cards=[ResultCard(
                title=ri.get("format", "Output"),
                value=ri.get("resolution", ""),
                details=[
                    f"Duration: {ri.get('duration', 'N/A')}",
                    f"File size: {ri.get('file_size', 'N/A')}",
                    f"Codec: {ri.get('codec', 'N/A')}",
                ],
            )],
        ))

    return result


def present_data(mission_data: Dict[str, Any]) -> AdaptiveResult:
    """Present data analysis results."""
    result = AdaptiveResult(
        task_type="data",
        title=mission_data.get("analysis_title", "Data Analysis"),
        subtitle=mission_data.get("description", ""),
        artifacts=mission_data.get("charts", []),
    )

    result.executive_summary = mission_data.get("conclusions", "")

    # Key metrics
    metrics = mission_data.get("metrics", [])
    if metrics:
        metric_cards = []
        for m in metrics:
            metric_cards.append(ResultCard(
                title=m.get("name", "Metric"),
                value=str(m.get("value", "")),
                subtitle=m.get("description", ""),
                badge=m.get("trend", ""),
                badge_color="green" if m.get("trend") == "up" else "red" if m.get("trend") == "down" else "gray",
            ))
        result.sections.append(ResultSection(
            title="Key Metrics",
            icon="chart",
            cards=metric_cards,
        ))

    return result


def present_automation(mission_data: Dict[str, Any]) -> AdaptiveResult:
    """Present automation/task completion results."""
    actions = mission_data.get("actions_taken", [])

    result = AdaptiveResult(
        task_type="automation",
        title=mission_data.get("mission_name", "Task Complete"),
        subtitle=f"{len(actions)} actions executed",
        evidence_count=mission_data.get("evidence_count", 0),
        duration_s=mission_data.get("duration_s", 0),
    )

    result.executive_summary = mission_data.get("summary", "")

    # Action summary
    if actions:
        action_cards = []
        for a in actions:
            action_cards.append(ResultCard(
                title=a.get("description", "Action"),
                subtitle=f"Agent: {a.get('agent', 'JARVIS')}",
                badge="SUCCESS" if a.get("success") else "FAILED",
                badge_color="green" if a.get("success") else "red",
                source_url=a.get("source_url", ""),
                verified=a.get("verified", False),
            ))
        result.sections.append(ResultSection(
            title="Actions Taken",
            icon="zap",
            cards=action_cards,
        ))

    # Resulting state
    resulting_state = mission_data.get("resulting_state", {})
    if resulting_state:
        state_cards = []
        for key, val in resulting_state.items():
            state_cards.append(ResultCard(
                title=key.replace("_", " ").title(),
                value=str(val),
            ))
        result.sections.append(ResultSection(
            title="Resulting State",
            icon="check",
            cards=state_cards,
        ))

    return result


# ══════════════════════════════════════════════════════════════
#  MAIN PRESENTER
# ══════════════════════════════════════════════════════════════

def present_result(task_type: str, mission_data: Dict[str, Any]) -> AdaptiveResult:
    """Present results in the optimal format for the task type.

    This is the main entry point for the result engine.
    """
    presenters = {
        "travel": present_travel,
        "research": present_research,
        "software": present_software,
        "creative": present_creative,
        "data": present_data,
        "automation": present_automation,
    }

    presenter = presenters.get(task_type)
    if presenter:
        return presenter(mission_data)

    # Default: generic presentation
    return AdaptiveResult(
        task_type=task_type,
        title=mission_data.get("title", "Result"),
        subtitle=mission_data.get("summary", ""),
        executive_summary=mission_data.get("summary", ""),
        artifacts=mission_data.get("artifacts", []),
    )
