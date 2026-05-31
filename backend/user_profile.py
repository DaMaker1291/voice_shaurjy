"""User profiler — builds persistent user model from conversations + device data."""

import json
import os
import re
import threading
from datetime import datetime

_PROFILES_DIR = os.path.join(os.path.dirname(__file__), ".user_profiles")
os.makedirs(_PROFILES_DIR, exist_ok=True)
_PROFILE_LOCK = threading.Lock()


def _profile_path(user_id: str) -> str:
    return os.path.join(_PROFILES_DIR, f"{user_id.replace('/', '_')}.json")


def load_profile(user_id: str) -> dict:
    path = _profile_path(user_id)
    if os.path.exists(path):
        try:
            return json.loads(open(path, "r", encoding="utf-8").read())
        except:
            pass
    return _default_profile()


def _default_profile() -> dict:
    return {
        "user_id": "",
        "first_seen": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat(),
        "session_count": 0,
        "total_messages": 0,
        "device": {},
        "interests": [],
        "personality_traits": [],
        "communication_style": "",
        "knowledge_domains": [],
        "recurring_topics": [],
        "preferences": {},
        "facts_about_user": [],
        "recent_topics": [],
    }


def save_profile(user_id: str, profile: dict):
    with _PROFILE_LOCK:
        path = _profile_path(user_id)
        profile["last_seen"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, default=str)


def merge_device_data(profile: dict, device_data: dict):
    """Merge device scan data into profile for personalization."""
    sys = device_data.get("system", {})
    profile["device"] = {
        "os": sys.get("os", ""),
        "hostname": sys.get("hostname", ""),
        "ram_gb": sys.get("ram_gb", ""),
        "cpu": sys.get("cpu", ""),
        "uptime_hours": sys.get("uptime_hours", ""),
        "installed_apps": [a.get("name", "") for a in device_data.get("installed_apps", [])[:20]],
        "browsers": [b.get("browser", "") + " (" + b.get("email", "") + ")" for b in device_data.get("browser_profiles", [])],
        "wifi": device_data.get("wifi_profiles", []),
    }
    usernames = [a.get("Name", "") for a in device_data.get("user_accounts", [])]
    if usernames:
        profile["device"]["accounts"] = usernames
    files = device_data.get("recent_files", [])
    if files:
        profile["device"]["recent_file_types"] = list(set(f.get("ext", "") for f in files))
    return profile


_TOPIC_PATTERNS = [
    (r"\b(programming|coding|python|javascript|code|software|app|web|api|backend|frontend)\b", "technology"),
    (r"\bgame\w*\b", "gaming"),
    (r"\bmusic\b|\bsong\b|\bsing\b|\bplaylist\b", "music"),
    (r"\bmovie\b|\bfilm\b|\bshow\b|\bwatch\b|\bnetflix\b", "entertainment"),
    (r"\bbook\b|\bread\b|\bnovel\b|\bstory\b", "reading"),
    (r"\bsport\b|\bfootball\b|\bbasketball\b|\bworkout\b|\bgym\b", "fitness"),
    (r"\bfood\b|\bcook\b|\brecipe\b|\bdinner\b|\breakfast\b", "food"),
    (r"\btravel\b|\bvacation\b|\btrip\b|\bflight\b|\bholiday\b", "travel"),
    (r"\bcar\b|\bdrive\b|\bvehicle\b|\btruck\b", "automotive"),
    (r"\bhealth\b|\bdoctor\b|\bmedical\b|\bsick\b|\bpain\b", "health"),
    (r"\bfinance\b|\bmoney\b|\binvest\b|\bstock\b|\bbank\b|\bbudget\b", "finance"),
    (r"\bstudy\b|\bschool\b|\bcollege\b|\buniversity\b|\bexam\b|\bhomework\b", "education"),
    (r"\bdesign\b|\bdraw\b|\bart\b|\bcreative\b|\bgraphic\b", "design"),
    (r"\bphoto\b|\bcamera\b|\bvideo\b|\bedit\b", "photography"),
    (r"\bai\b|\bml\b|\bmachine learning\b|\bdeep learning\b|\bLLM\b|\bneural\b", "artificial intelligence"),
    (r"\bstartup\b|\bbusiness\b|\bcompany\b|\bproject\b|\bidea\b", "entrepreneurship"),
]


def extract_topics(text: str) -> list[str]:
    lower = text.lower()
    topics = set()
    for pattern, topic in _TOPIC_PATTERNS:
        if re.search(pattern, lower):
            topics.add(topic)
    return list(topics)


_TRAIT_PATTERNS = [
    (r"\b(hate|annoyed|frustrated|angry|stupid|dumb|terrible|awful)\b", "blunt"),
    (r"\b(please|thanks|thank|appreciate|kindly)\b", "polite"),
    (r"\b(lol|lmao|haha|funny|hilarious|joke)\b", "humorous"),
    (r"\b(interesting|fascinating|cool|awesome|amazing|wow)\b", "curious"),
    (r"\b(urgent|asap|quick|fast|hurry)\b", "impatient"),
    (r"\b(detail|explain|elaborate|specifically|exactly)\b", "thorough"),
    (r"\b(serious|important|crucial|critical|essential)\b", "serious"),
    (r"\b(maybe|perhaps|might|could|possibly|guess)\b", "uncertain"),
    (r"\b(definitely|absolutely|certainly|always|never)\b", "decisive"),
]


def extract_traits(text: str) -> list[str]:
    lower = text.lower()
    traits = set()
    for pattern, trait in _TRAIT_PATTERNS:
        if re.search(pattern, lower):
            traits.add(trait)
    return list(traits)


def update_from_conversation(profile: dict, user_text: str, assistant_reply: str):
    """Update profile based on a single conversation turn."""
    profile["total_messages"] = profile.get("total_messages", 0) + 1

    # Topics
    topics = extract_topics(user_text)
    current = profile.get("interests", [])
    for t in topics:
        entry = next((x for x in current if x.get("topic") == t), None)
        if entry:
            entry["count"] = entry.get("count", 0) + 1
            entry["last"] = datetime.now().isoformat()
        else:
            current.append({"topic": t, "count": 1, "first": datetime.now().isoformat(), "last": datetime.now().isoformat()})
    current.sort(key=lambda x: x.get("count", 0), reverse=True)
    profile["interests"] = current[:20]

    # Personality traits
    traits = extract_traits(user_text)
    current_traits = profile.get("personality_traits", [])
    for t in traits:
        if t not in current_traits:
            current_traits.append(t)
    profile["personality_traits"] = current_traits

    # Communication style
    words = user_text.split()
    avg_len = sum(len(w) for w in words) / max(len(words), 1)
    if avg_len > 6:
        style = "formal, detailed"
    elif avg_len > 4:
        style = "balanced"
    else:
        style = "casual, direct"
    profile["communication_style"] = style

    # Knowledge domains
    if len(words) > 15 and any(w in user_text.lower() for w in ["because", "since", "therefore", "however", "actually"]):
        domains = profile.get("knowledge_domains", [])
        for t in topics:
            if t not in domains:
                domains.append(t)
        profile["knowledge_domains"] = domains

    # Recurring topics tracker
    recent = profile.get("recent_topics", [])
    recent.append({"topic": topics[0] if topics else "general", "time": datetime.now().isoformat()})
    profile["recent_topics"] = recent[-20:]

    # Count topic recurrences
    from collections import Counter
    topic_counts = Counter(r["topic"] for r in profile.get("recent_topics", []))
    recurring = [t for t, c in topic_counts.most_common(5) if c >= 2 and t != "general"]
    profile["recurring_topics"] = recurring

    # Extract personal facts (I am / I work / I live / I have statements)
    fact_patterns = [
        r"I(?:'m| am) (\w+(?: \w+){0,5})",
        r"I work (?:as|at|for|with) (\w+(?: \w+){0,5})",
        r"I live (?:in|at|near) (\w+(?: \w+){0,5})",
        r"I have (\w+(?: \w+){0,5})",
        r"I (?:like|love|enjoy) (\w+(?: \w+){0,5})",
        r"My name is (\w+)",
        r"I'm (\d+)",
        r"I am (\d+)",
    ]
    for pat in fact_patterns:
        m = re.search(pat, user_text, re.IGNORECASE)
        if m:
            fact = m.group(0).strip()
            facts = profile.get("facts_about_user", [])
            if fact not in facts:
                facts.append(fact)
            profile["facts_about_user"] = facts[-30:]

    return profile


def generate_summary(user_id: str) -> str:
    """Generate a natural-language summary of the user profile for the LLM."""
    profile = load_profile(user_id)
    if not profile or not profile.get("interests"):
        return ""

    parts = [f"User profile for {profile['device'].get('hostname', user_id)}:"]

    interests = profile.get("interests", [])
    if interests:
        top = [i["topic"] for i in interests[:5]]
        parts.append(f"Interests: {', '.join(top)}")

    traits = profile.get("personality_traits", [])
    if traits:
        parts.append(f"Communication style: {profile.get('communication_style', 'unknown')}, traits: {', '.join(traits)}")

    facts = profile.get("facts_about_user", [])
    if facts:
        parts.append(f"Known facts: {'; '.join(facts[-5:])}")

    recurring = profile.get("recurring_topics", [])
    if recurring:
        parts.append(f"Recurring topics: {', '.join(recurring)}")

    device = profile.get("device", {})
    if device:
        device_parts = []
        if device.get("os"): device_parts.append(f"OS: {device['os']}")
        if device.get("installed_apps"):
            top_apps = ", ".join(device["installed_apps"][:8])
            device_parts.append(f"Apps: {top_apps}")
        if device.get("browsers"):
            device_parts.append(f"Browsers: {', '.join(device['browsers'])}")
        if device_parts:
            parts.append("Device: " + " | ".join(device_parts))

    return "\n".join(parts)
