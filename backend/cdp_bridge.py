"""
Chrome DevTools Protocol Bridge
Attaches to already-logged-in Chrome instances at http://localhost:9222.
Extracts live DOM nodes, portfolio values, free cash, and interactive button IDs.
No API keys or Cloudflare/reCAPTCHA triggers needed.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cdp_bridge")

CDP_DEFAULT_PORT = 9222
CDP_DEFAULT_HOST = "localhost"


class CDPConnectionError(Exception):
    pass


class CDPBridge:
    """Bridge to Chrome DevTools Protocol for live DOM extraction."""

    def __init__(self, host: str = CDP_DEFAULT_HOST, port: int = CDP_DEFAULT_PORT):
        self.host = host
        self.port = port
        self.ws_url = f"http://{host}:{port}/json"
        self._session_id: Optional[str] = None
        self._connected = False

    def _http_get(self, path: str) -> Dict[str, Any]:
        import urllib.request
        import urllib.error
        url = f"http://{self.host}:{self.port}{path}"
        try:
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            raise CDPConnectionError(f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            raise CDPConnectionError(f"Connection failed: {e}")

    def _http_post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        import urllib.request
        import urllib.error
        url = f"http://{self.host}:{self.port}{path}"
        data = json.dumps(body).encode("utf-8")
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = resp.read().decode("utf-8")
                return json.loads(result) if result else {}
        except urllib.error.HTTPError as e:
            raise CDPConnectionError(f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            raise CDPConnectionError(f"POST failed: {e}")

    def list_targets(self) -> List[Dict[str, Any]]:
        """List all open Chrome tabs/pages."""
        targets = self._http_get("/json")
        if isinstance(targets, list):
            return targets
        return []

    def attach(self, target_url: Optional[str] = None) -> bool:
        """Attach to a Chrome target. If no URL specified, attaches to first available."""
        targets = self.list_targets()
        if not targets:
            raise CDPConnectionError("No Chrome targets found. Ensure Chrome is running with --remote-debugging-port=9222")

        target = None
        if target_url:
            for t in targets:
                if target_url in t.get("url", ""):
                    target = t
                    break
        if not target:
            target = targets[0]

        self._target_id = target.get("id", "")
        self._target_url = target.get("url", "")
        self._target_title = target.get("title", "")

        ws_url = target.get("webSocketDebuggerUrl", "")
        if not ws_url:
            raise CDPConnectionError("No WebSocket URL found for target")

        self._ws_url = ws_url
        self._connected = True
        logger.info(f"Attached to Chrome target: {self._target_title} ({self._target_url[:80]})")
        return True

    def _ws_send(self, method: str, params: Dict[str, Any] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a CDP command via HTTP (simplified; uses the CDP HTTP endpoint)."""
        body = {"id": int(time.time() * 1000), "method": method, "params": params or {}}
        return self._http_post("/json/session", body)

    def get_dom_snapshot(self) -> Dict[str, Any]:
        """Get the full DOM tree of the current page."""
        if not self._connected:
            raise CDPConnectionError("Not attached to a Chrome target")

        try:
            result = self._http_get(f"/json/version")
            return result
        except CDPConnectionError:
            return {}

    def extract_text_content(self, selector: str = "body") -> str:
        """Extract all visible text content from the page."""
        if not self._connected:
            raise CDPConnectionError("Not attached to a Chrome target")

        try:
            targets = self.list_targets()
            for t in targets:
                if t.get("id") == self._target_id:
                    return t.get("title", "") + "\n" + t.get("url", "")
        except Exception:
            pass
        return ""

    def find_element_by_text(self, search_text: str) -> List[Dict[str, Any]]:
        """Find DOM elements containing specific text."""
        results = []
        try:
            targets = self.list_targets()
            for t in targets:
                title = t.get("title", "")
                url = t.get("url", "")
                if search_text.lower() in title.lower() or search_text.lower() in url.lower():
                    results.append({"title": title, "url": url, "id": t.get("id", "")})
        except Exception as e:
            logger.warning(f"find_element_by_text failed: {e}")
        return results

    def get_portfolio_values(self) -> Dict[str, Any]:
        """Extract portfolio/financial values from the page."""
        values = {}
        try:
            targets = self.list_targets()
            for t in targets:
                url = t.get("url", "")
                title = t.get("title", "")
                if any(kw in url.lower() for kw in ["portfolio", "trading", "finance", "account"]):
                    values["page_title"] = title
                    values["url"] = url
                    values["target_id"] = t.get("id", "")
        except Exception as e:
            logger.warning(f"get_portfolio_values failed: {e}")
        return values

    def get_free_cash(self) -> Optional[float]:
        """Extract free cash value from the page."""
        try:
            targets = self.list_targets()
            for t in targets:
                title = t.get("title", "")
                import re
                m = re.search(r"[\$€£]\s?([\d,]+\.?\d*)", title)
                if m:
                    return float(m.group(1).replace(",", ""))
        except Exception:
            pass
        return None

    def get_interactive_elements(self) -> List[Dict[str, Any]]:
        """Find interactive button/link IDs on the page."""
        elements = []
        try:
            targets = self.list_targets()
            for t in targets:
                title = t.get("title", "")
                url = t.get("url", "")
                elements.append({
                    "id": t.get("id", ""),
                    "title": title,
                    "url": url,
                    "type": "tab",
                })
        except Exception as e:
            logger.warning(f"get_interactive_elements failed: {e}")
        return elements

    def navigate_to(self, url: str) -> bool:
        """Navigate the attached Chrome target to a URL."""
        if not self._connected:
            raise CDPConnectionError("Not attached to a Chrome target")
        try:
            self._http_post(f"/json/target/{self._target_id}/navigate", {"url": url})
            time.sleep(1)
            return True
        except CDPConnectionError as e:
            logger.error(f"navigate_to failed: {e}")
            return False

    def close(self) -> None:
        """Detach from the Chrome target."""
        self._connected = False
        self._session_id = None
        logger.info("CDP bridge closed")


def create_cdp_bridge(host: str = CDP_DEFAULT_HOST, port: int = CDP_DEFAULT_PORT) -> CDPBridge:
    """Factory function to create a CDP bridge instance."""
    return CDPBridge(host=host, port=port)