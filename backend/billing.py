"""Open-source license-key validation.
Replaces Stripe. Users get a license file on their machine to unlock Premium."""

import os
import json
import hashlib

LICENSE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LICENSE_FILE = os.path.join(LICENSE_DIR, "license.json")

# Hard-coded demo keys:
#   free-0000-0000-0000  → Free tier (15 min/day)
#   prem-1111-2222-3333  → Premium tier (unlimited)
_DEMO_KEYS = {
    "free-0000-0000-0000": "free",
    "prem-1111-2222-3333": "premium",
}


def _load_license():
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE) as f:
            return json.load(f)
    return {}


def _save_license(data: dict):
    os.makedirs(LICENSE_DIR, exist_ok=True)
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f)


def activate_license(key: str) -> str:
    key = key.strip().lower()
    tier = _DEMO_KEYS.get(key)
    if not tier:
        return "invalid"

    lic = _load_license()
    lic["activated_key"] = key
    lic["tier"] = tier
    _save_license(lic)
    return tier


def get_tier(user_id: str = "local") -> str:
    lic = _load_license()
    return lic.get("tier", "free")


def is_premium(user_id: str = "local") -> bool:
    return get_tier(user_id) == "premium"
