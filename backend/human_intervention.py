"""
JARVIS Human Intervention System
Detects when a task hits a wall (login, CAPTCHA, payment, account creation)
and brings it to the user for manual handling.

Rules:
  - JARVIS does the prep work (search, navigate, fill forms, compare)
  - JARVIS NEVER handles money (no card numbers, no bank, no checkout confirm)
  - JARVIS NEVER creates accounts (user does that themselves)
  - JARVIS NEVER logs in (user does that themselves)
  - JARVIS stops, pings user, shows state, asks what to do next
"""
import re
import time
import json
import os
import logging
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

log = logging.getLogger("jarvis-intervention")


class InterventionType(str, Enum):
    LOGIN = "login"
    CAPTCHA = "captcha"
    ACCOUNT_CREATION = "account_creation"
    PAYMENT = "payment"
    PASSWORD = "password"
    TWO_FA = "two_factor"
    EMAIL_VERIFICATION = "email_verification"
    PHONE_VERIFICATION = "phone_verification"
    TERMS_ACCEPT = "terms_accept"
    COOKIE_CONSENT = "cookie_consent"
    UNKNOWN_BLOCK = "unknown_block"


class InterventionAction(str, Enum):
    PAUSE_AND_ASK = "pause_and_ask"        # Stop, show state, ask user
    BRING_TO_DESKTOP = "bring_to_desktop"   # Move window to user's screen
    OPEN_IN_BROWSER = "open_in_browser"     # Open in user's default browser
    SHOW_RECEIPT = "show_receipt"           # Show order summary, ask to confirm
    NAVIGATE_TO_CHECKOUT = "navigate_checkout"  # Go to checkout page, stop
    SKIP = "skip"                           # Try to skip/bypass
    CANCEL = "cancel"                       # Abort the task


# ── Block Detection Patterns ────────────────────────────────────────
BLOCK_PATTERNS = {
    InterventionType.LOGIN: [
        r"sign\s*in", r"log\s*in", r"login", r"authenticate",
        r"enter\s+(?:your\s+)?(?:email|username|password)",
        r"welcome\s+back", r"already\s+have\s+an\s+account",
        r"credentials", r"oauth", r"google\s+sign\s+in",
        r"sign\s+in\s+with", r"continue\s+with\s+(?:google|facebook|apple)",
    ],
    InterventionType.CAPTCHA: [
        r"captcha", r"recaptcha", r"verify\s+you(?:'re|\s+are)\s+(?:a\s+)?human",
        r"i(?:'m|\s+am)\s+not\s+a\s+robot", r"security\s+check",
        r"prove\s+you(?:'re|\s+are)\s+not\s+a\s+robot", r"challenge",
        r"select\s+(?:all|every)\s+(?:image|picture|photo|tile)",
    ],
    InterventionType.ACCOUNT_CREATION: [
        r"create\s+(?:an?\s+)?account", r"sign\s+up", r"register",
        r"new\s+account", r"join\s+(?:us|now|free)",
        r"don'?t\s+have\s+an?\s+account", r"set\s+up\s+(?:your\s+)?account",
        r"enter\s+(?:your\s+)?(?:full\s+)?name", r"choose\s+(?:a\s+)?password",
    ],
    InterventionType.PAYMENT: [
        r"checkout", r"payment\s+method", r"credit\s+card", r"debit\s+card",
        r"card\s+number", r"expiry\s+date", r"cvv", r"billing\s+address\s+and\s+payment",
        r"order\s+summary", r"place\s+order", r"confirm\s+order",
        r"pay\s+(?:now|with)", r"purchase", r"buy\s+now",
        r"total\s+due", r"amount\s+due", r"review\s+your\s+order",
        r"add\s+(?:a\s+)?payment", r"apple\s+pay",
        r"paypal", r"bank\s+transfer", r"wire\s+transfer",
    ],
    InterventionType.PASSWORD: [
        r"enter\s+(?:a\s+)?password", r"create\s+(?:a\s+)?password",
        r"confirm\s+(?:your\s+)?password", r"password\s+(?:must|should|require)",
        r"strong\s+password", r"password\s+strength",
    ],
    InterventionType.TWO_FA: [
        r"two\s+factor", r"2fa", r"verification\s+code",
        r"enter\s+(?:the\s+)?code\s+(?:sent|from)",
        r"authenticator\s+app", r"security\s+code",
    ],
    InterventionType.EMAIL_VERIFICATION: [
        r"verify\s+(?:your\s+)?email", r"confirmation\s+link",
        r"check\s+(?:your\s+)?inbox", r"email\s+sent",
    ],
    InterventionType.PHONE_VERIFICATION: [
        r"phone\s+(?:number\s+)?verification", r"verify\s+(?:your\s+)?phone\s+number",
        r"sms\s+code\s+sent", r"code\s+sent\s+to\s+(?:your\s+)?(?:phone|mobile|number)",
    ],
    InterventionType.TERMS_ACCEPT: [
        r"terms\s+(?:of|and)\s+(?:service|use|agreement)",
        r"privacy\s+policy", r"agree\s+to\s+(?:our|the|these)",
        r"i\s+(?:have\s+)?read\s+and\s+agree",
    ],
    InterventionType.COOKIE_CONSENT: [
        r"cookie\s+(?:policy|notice|consent)", r"accept\s+cookies",
        r"we\s+use\s+cookies", r"cookie\s+preferences",
    ],
}


@dataclass
class Intervention:
    """A detected block requiring human intervention."""
    type: InterventionType
    action: InterventionAction
    page_title: str = ""
    page_url: str = ""
    screenshot_path: str = ""
    message: str = ""           # What JARVIS was doing
    question: str = ""          # What JARVIS needs from user
    options: List[str] = field(default_factory=list)  # Possible user choices
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    user_response: str = ""


class HumanInterventionManager:
    """
    Detects when a task hits a wall and brings it to the user.
    
    Flow:
    1. During automation, monitor page content for block patterns
    2. When block detected → pause task
    3. Notify user (desktop notification + sound)
    4. Bring window to user's screen OR open in their browser
    5. Show what JARVIS did so far + what's blocking
    6. Ask user what to do next
    7. Resume based on user's decision
    """

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id
        self._pending: Dict[str, Intervention] = {}
        self._history: List[Dict] = []
        self._auto_actions = {
            InterventionType.COOKIE_CONSENT: InterventionAction.SKIP,
            InterventionType.TERMS_ACCEPT: InterventionAction.PAUSE_AND_ASK,
        }
        self._load_history()

    def _load_history(self):
        path = os.path.expanduser(f"~/.jarvis/interventions_{self.user_id}.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self._history = json.load(f)
            except Exception:
                pass

    def _save_history(self):
        path = os.path.expanduser(f"~/.jarvis/interventions_{self.user_id}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._history[-100:], f, indent=2)

    # ── Detection ───────────────────────────────────────────────────

    def scan_page(self, page_text: str, page_url: str = "",
                  page_title: str = "") -> Optional[Intervention]:
        """
        Scan page content for blocks. Returns Intervention if block found.
        Call this during automation (VM agent, browser agent, etc.)
        """
        lower = page_text.lower()

        for block_type, patterns in BLOCK_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, lower, re.IGNORECASE):
                    intervention = self._create_intervention(
                        block_type, page_text, page_url, page_title
                    )
                    if intervention:
                        log.info(f"Block detected: {block_type.value} on {page_url}")
                        return intervention
        return None

    def scan_screenshot_text(self, ocr_text: str, url: str = "") -> Optional[Intervention]:
        """Scan OCR text from screenshot for blocks."""
        return self.scan_page(ocr_text, url)

    def _create_intervention(self, block_type: InterventionType,
                             page_text: str, url: str, title: str) -> Optional[Intervention]:
        """Create an Intervention based on block type and context."""
        action = self._auto_actions.get(block_type, InterventionAction.PAUSE_AND_ASK)

        # Determine what to ask based on block type
        if block_type == InterventionType.LOGIN:
            question = (
                "I hit a login page. I can't log in for you — "
                "which account should I use, or do you want to log in yourself?"
            )
            options = [
                "Use my Google account",
                "Use my email/password (I'll type it)",
                "Open in my browser so I can log in",
                "Skip this, try something else",
            ]

        elif block_type == InterventionType.PAYMENT:
            action = InterventionAction.SHOW_RECEIPT
            question = (
                "I found what you wanted! Here's the summary. "
                "I can't handle payment — I'll take you to the checkout page "
                "and you complete the purchase yourself."
            )
            options = [
                "Take me to checkout",
                "Show me more options first",
                "Add to cart and continue shopping",
                "Cancel — too expensive",
            ]

        elif block_type == InterventionType.ACCOUNT_CREATION:
            question = (
                "This requires creating an account. I won't create accounts for you — "
                "do you want me to open this in your browser so you can sign up?"
            )
            options = [
                "Open in my browser",
                "I already have an account — use my credentials",
                "Skip this service",
            ]

        elif block_type == InterventionType.CAPTCHA:
            action = InterventionAction.BRING_TO_DESKTOP
            question = (
                "I hit a CAPTCHA/security check. I can't solve these — "
                "I've brought the page to your screen. Can you handle this?"
            )
            options = [
                "Done — I solved it",
                "Can't solve it, try another approach",
            ]

        elif block_type == InterventionType.TWO_FA:
            question = (
                "This needs a 2FA code from your phone/authenticator. "
                "What's the code, or should I wait?"
            )
            options = [
                "I'll enter the code",
                "Use my backup code",
                "Skip this",
            ]

        elif block_type == InterventionType.EMAIL_VERIFICATION:
            question = (
                "A verification email was sent. Check your inbox and click the link, "
                "or tell me when you've verified."
            )
            options = [
                "Done — verified",
                "Resend the email",
                "Use a different email",
            ]

        elif block_type == InterventionType.PHONE_VERIFICATION:
            question = (
                "I need a phone verification code. Enter the code from your SMS, "
                "or I can try another method."
            )
            options = [
                "I'll enter the code",
                "Call me instead",
                "Skip this",
            ]

        elif block_type == InterventionType.TERMS_ACCEPT:
            question = (
                "There are Terms of Service to accept. Want me to accept them "
                "so we can continue, or do you want to read them first?"
            )
            options = [
                "Accept and continue",
                "Open in browser so I can read them",
                "Cancel — I don't agree",
            ]

        elif block_type == InterventionType.COOKIE_CONSENT:
            # Auto-accept cookies (harmless)
            action = InterventionAction.SKIP
            question = "Cookie consent dialog. I'll dismiss it."
            options = []

        else:
            question = (
                f"I hit something I can't handle: {block_type.value}. "
                "What should I do?"
            )
            options = [
                "Open in my browser",
                "Skip this step",
                "Cancel the task",
            ]

        # Build context with what JARVIS accomplished so far
        context = {
            "page_title": title,
            "page_url": url,
            "block_type": block_type.value,
            "suggested_action": action.value,
        }

        intervention = Intervention(
            type=block_type,
            action=action,
            page_title=title,
            page_url=url,
            message=f"Task blocked at {block_type.value}",
            question=question,
            options=options,
            context=context,
        )

        self._pending[str(intervention.timestamp)] = intervention
        return intervention

    # ── User Notification ───────────────────────────────────────────

    def notify_user(self, intervention: Intervention) -> str:
        """
        Send desktop notification and return the intervention message
        for the LLM to relay to the user.
        """
        # Desktop notification
        self._send_desktop_notification(intervention)

        # Build message for user
        msg_parts = [
            f"⚠️ **I need your help** — {intervention.type.value.replace('_', ' ').title()}",
            "",
            f"**What happened:** {intervention.message}",
        ]

        if intervention.page_title:
            msg_parts.append(f"**Page:** {intervention.page_title}")
        if intervention.page_url:
            msg_parts.append(f"**URL:** {intervention.page_url}")

        msg_parts.append("")
        msg_parts.append(f"**{intervention.question}**")

        if intervention.options:
            msg_parts.append("")
            msg_parts.append("**Your options:**")
            for i, opt in enumerate(intervention.options, 1):
                msg_parts.append(f"  {i}. {opt}")

        return "\n".join(msg_parts)

    def _send_desktop_notification(self, intervention: Intervention):
        """Send Windows toast notification."""
        try:
            title = f"JARVIS needs help — {intervention.type.value.replace('_', ' ').title()}"
            msg = intervention.question[:200]

            # Use PowerShell toast notification
            ps_cmd = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $template = @"
            <toast>
                <visual>
                    <binding template="ToastGeneric">
                        <text>{title}</text>
                        <text>{msg}</text>
                    </binding>
                </visual>
                <audio src="ms-winsoundevent:Notification.Default"/>
            </toast>
"@
            $xml = [Windows.Data.Xml.Dom.XmlDocument]::new()
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS").Show($toast)
            '''
            from ps_executor import ps
            ps(ps_cmd)
        except Exception as e:
            log.debug(f"Desktop notification failed: {e}")
            # Fallback: simple message box
            try:
                from ps_executor import ps
                ps(f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("{intervention.question[:100]}", "JARVIS needs help", "OK", "Information")')
            except Exception:
                pass

    # ── Bring to User ───────────────────────────────────────────────

    def bring_to_desktop(self, intervention: Intervention) -> str:
        """
        Bring the blocked page to user's desktop.
        For VM: take screenshot, expand window, show on screen.
        For browser: bring tab to front.
        """
        url = intervention.context.get("page_url", "")
        action = intervention.action

        if action == InterventionAction.BRING_TO_DESKTOP:
            # Move window to user's screen
            try:
                from ps_executor import ps
                # Bring browser to front and maximize
                ps("""
                    Add-Type @"
                    using System;
                    using System.Runtime.InteropServices;
                    public class Win32 {
                        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
                        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                    }
"@
                    $p = Get-Process | Where-Object {$_.MainWindowTitle -ne ""} | Select-Object -First 1
                    if ($p) {
                        [Win32]::SetForegroundWindow($p.MainWindowHandle)
                        [Win32]::ShowWindow($p.MainWindowHandle, 3)  # SW_MAXIMIZE
                    }
                """)
                return "I've brought the page to your screen. Handle the blocking step, then tell me to continue."
            except Exception as e:
                return f"Couldn't bring to screen: {e}. Open this URL manually: {url}"

        elif action == InterventionAction.OPEN_IN_BROWSER:
            if url:
                try:
                    from ps_executor import ps
                    ps(f'Start-Process "{url}"')
                    return f"I've opened this in your browser: {url}\nHandle the blocking step, then tell me to continue."
                except Exception:
                    pass
            return f"Please open this URL in your browser: {url}"

        elif action == InterventionAction.SHOW_RECEIPT:
            return self._show_receipt(intervention)

        elif action == InterventionAction.NAVIGATE_TO_CHECKOUT:
            return self._navigate_to_checkout(intervention)

        return "I've paused here. Handle the blocking step, then tell me to continue."

    def _show_receipt(self, intervention: Intervention) -> str:
        """Show order summary/receipt and take user to checkout."""
        ctx = intervention.context
        summary = ctx.get("order_summary", {})
        url = ctx.get("page_url", "")

        msg_parts = [
            "🛒 **Here's what I found:**",
            "",
        ]

        if summary:
            if summary.get("item"):
                msg_parts.append(f"**Item:** {summary['item']}")
            if summary.get("price"):
                msg_parts.append(f"**Price:** {summary['price']}")
            if summary.get("quantity"):
                msg_parts.append(f"**Quantity:** {summary['quantity']}")
            if summary.get("total"):
                msg_parts.append(f"**Total:** {summary['total']}")
            if summary.get("seller"):
                msg_parts.append(f"**Seller:** {summary['seller']}")
            if summary.get("shipping"):
                msg_parts.append(f"**Shipping:** {summary['shipping']}")
            msg_parts.append("")

        msg_parts.extend([
            "I've navigated to the checkout page. **I will NOT enter any payment details.**",
            "",
            "**You need to:**",
            "  1. Review the order above",
            "  2. Enter your payment details yourself",
            "  3. Confirm the purchase",
            "",
            "I can help with anything else while you do that.",
        ])

        if url:
            msg_parts.append(f"\n**Checkout URL:** {url}")

        return "\n".join(msg_parts)

    def _navigate_to_checkout(self, intervention: Intervention) -> str:
        """Navigate to checkout and stop."""
        url = intervention.context.get("page_url", "")
        if url:
            try:
                from ps_executor import ps
                ps(f'Start-Process "{url}"')
                return (
                    "I've opened the checkout page in your browser.\n\n"
                    "**I'm stopping here.** I will NOT:\n"
                    "  • Enter your card number\n"
                    "  • Enter your billing address\n"
                    "  • Confirm the purchase\n"
                    "  • Handle any money\n\n"
                    "You do the payment yourself. Tell me when you're done or if you need help with anything else."
                )
            except Exception:
                pass
        return "Please go to the checkout page yourself. I won't handle payment details."

    # ── Resolution ──────────────────────────────────────────────────

    def resolve(self, intervention_id: str, user_response: str) -> Dict[str, Any]:
        """
        User has responded. Return what JARVIS should do next.
        """
        intervention = self._pending.get(intervention_id)
        if not intervention:
            return {"action": "continue", "message": "Unknown intervention"}

        intervention.resolved = True
        intervention.user_response = user_response

        # Record in history
        self._history.append(asdict(intervention))
        self._save_history()

        # Determine next action
        lower = user_response.lower()

        if intervention.type == InterventionType.LOGIN:
            if "google" in lower:
                return {"action": "use_google_login", "message": "Using Google sign-in. Click the Google button when it appears."}
            elif "browser" in lower or "myself" in lower or "open" in lower:
                return {"action": "open_in_browser", "message": "Opening in your browser. Log in there."}
            elif "skip" in lower or "cancel" in lower:
                return {"action": "cancel", "message": "Skipping this step."}
            else:
                return {"action": "provide_credentials", "message": "Enter your credentials when prompted."}

        elif intervention.type == InterventionType.PAYMENT:
            if "checkout" in lower or "take me" in lower:
                return {"action": "navigate_to_checkout", "message": "Navigating to checkout. You handle the payment."}
            elif "more options" in lower or "show" in lower:
                return {"action": "show_more_options", "message": "Let me find more options for you."}
            elif "cart" in lower or "continue shopping" in lower:
                return {"action": "add_to_cart", "message": "Added to cart. Continuing to shop."}
            elif "cancel" in lower or "expensive" in lower:
                return {"action": "cancel", "message": "Cancelling this order."}
            else:
                return {"action": "navigate_to_checkout", "message": "Going to checkout. You handle the payment."}

        elif intervention.type == InterventionType.ACCOUNT_CREATION:
            if "browser" in lower or "open" in lower:
                return {"action": "open_in_browser", "message": "Opening in browser. Create your account there."}
            elif "already" in lower or "have" in lower:
                return {"action": "provide_credentials", "message": "Enter your login details when prompted."}
            else:
                return {"action": "skip", "message": "Skipping account creation."}

        elif intervention.type == InterventionType.CAPTCHA:
            if "done" in lower or "solved" in lower:
                return {"action": "continue", "message": "Continuing the task."}
            else:
                return {"action": "try_alternative", "message": "Let me try a different approach."}

        elif intervention.type == InterventionType.TERMS_ACCEPT:
            if "accept" in lower:
                return {"action": "accept_terms", "message": "Accepting terms and continuing."}
            elif "browser" in lower or "read" in lower:
                return {"action": "open_in_browser", "message": "Opening in browser so you can read them."}
            else:
                return {"action": "cancel", "message": "Cancelling."}

        elif intervention.type == InterventionType.COOKIE_CONSENT:
            return {"action": "skip", "message": "Dismissed cookies."}

        else:
            if "browser" in lower or "open" in lower:
                return {"action": "open_in_browser", "message": "Opening in your browser."}
            elif "skip" in lower:
                return {"action": "skip", "message": "Skipping this step."}
            elif "cancel" in lower:
                return {"action": "cancel", "message": "Cancelling the task."}
            else:
                return {"action": "continue", "message": "Continuing."}

    # ── Payment Boundary ────────────────────────────────────────────

    def is_payment_related(self, text: str) -> bool:
        """Check if text involves payment/money — JARVIS should NEVER handle these."""
        lower = text.lower()
        payment_keywords = [
            "card number", "credit card", "debit card", "cvv", "expiry",
            "billing address", "payment method", "bank account", "routing number",
            "social security", "ssn", "tax id", "pin number",
            "wire transfer", "venmo", "cashapp", "zelle",
            "crypto wallet", "bitcoin address", "private key",
        ]
        return any(kw in lower for kw in payment_keywords)

    def get_payment_boundary_message(self) -> str:
        """Message when user asks JARVIS to handle money."""
        return (
            "I can't handle money or payment details for security reasons. "
            "Here's what I CAN do:\n\n"
            "  1. **Find** the best product/price for you\n"
            "  2. **Navigate** to the checkout page\n"
            "  3. **Fill in** non-sensitive info (name, email, shipping address)\n"
            "  4. **Show** you the order summary/receipt\n"
            "  5. **Stop** and let you enter payment details yourself\n\n"
            "I'll get you to the checkout point, then you handle the money part. "
            "That way your financial info never touches my systems."
        )

    # ── Utility ─────────────────────────────────────────────────────

    def get_pending(self) -> List[Dict]:
        """Get all unresolved interventions."""
        return [asdict(i) for i in self._pending.values() if not i.resolved]

    def clear_resolved(self):
        """Clear resolved interventions."""
        self._pending = {k: v for k, v in self._pending.items() if not v.resolved}


# ── Singleton ────────────────────────────────────────────────────────
_instance: Optional[HumanInterventionManager] = None


def get_intervention_manager(user_id: str = "local") -> HumanInterventionManager:
    global _instance
    if _instance is None:
        _instance = HumanInterventionManager(user_id)
    return _instance
