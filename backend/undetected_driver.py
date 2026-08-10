"""
JARVIS Anti-Fingerprint Browser Automation — Stealth web browsing.

Uses Playwright with anti-detection flags + CDP attachment to bypass:
- Cloudflare, DataDome, PerimeterX, Akamai bot detection
- navigator.webdriver flag
- WebGL/Canvas fingerprinting
- Automated browser detection

Features:
- Human-like mouse trajectories (Bézier curves)
- Randomized keystroke latencies (30-150ms)
- WebGL/Canvas noise injection
- CDP attachment to running Chrome instances
"""
import os
import sys
import json
import time
import random
import asyncio
import logging
import math
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("undetected_driver")


@dataclass
class BrowserConfig:
    """Configuration for stealth browser."""
    headless: bool = False
    display: str = ":99"
    user_data_dir: str = ""
    profile_name: str = "Default"
    cdp_port: int = 9222
    viewport_width: int = 1920
    viewport_height: int = 1080
    human_like: bool = True
    anti_fingerprint: bool = True
    proxy: str = ""


# ── Anti-Detection JavaScript Snippets ─────────────────────────────────────

STEALTH_JS = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// Override navigator.plugins to look real
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
        { name: 'Native Client', filename: 'internal-nacl-plugin' },
    ],
});

// Override navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-GB', 'en-US', 'en'],
});

// Override permissions API
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

// Chrome runtime mock
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {},
};

// Override console.debug to suppress DevTools detection
const originalDebug = console.debug;
console.debug = function(...args) {
    if (args[0] && typeof args[0] === 'string' && args[0].includes('Remote Debugging')) {
        return;
    }
    return originalDebug.apply(console, args);
};
"""

WEBGL_NOISE_JS = """
// Add subtle noise to WebGL canvas fingerprint
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    // UNMASKED_VENDOR_WEBGL
    if (parameter === 37445) return 'Intel Inc.';
    // UNMASKED_RENDERER_WEBGL
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, parameter);
};

// Canvas noise injection
const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    if (type === 'image/webp') return originalToDataURL.apply(this, arguments);
    const ctx = this.getContext('2d');
    if (ctx) {
        const imageData = ctx.getImageData(0, 0, this.width, this.height);
        for (let i = 0; i < imageData.data.length; i += 4) {
            imageData.data[i] += Math.floor(Math.random() * 2);
        }
        ctx.putImageData(imageData, 0, 0);
    }
    return originalToDataURL.apply(this, arguments);
};
"""

HUMAN_BEHAVIOR_JS = """
// Override Date to prevent timing-based detection
(function() {
    const originalDate = Date;
    const offset = Math.floor(Math.random() * 1000);

    class CustomDate extends originalDate {
        constructor(...args) {
            if (args.length === 0) {
                super(originalDate.now() + offset);
            } else {
                super(...args);
            }
        }
        static now() {
            return originalDate.now() + offset;
        }
    }
    window.Date = CustomDate;
})();

// Randomize Math.random seed (prevents fingerprint correlation)
Math.random = (function() {
    let seed = Date.now() ^ (Math.random() * 0xFFFFFFFF);
    return function() {
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF;
        return seed / 0x7FFFFFFF;
    };
})();
"""


class HumanMouse:
    """Generate human-like mouse movement trajectories using Bézier curves."""

    def __init__(self):
        self.current_x = 0
        self.current_y = 0

    def bezier_curve(self, start: tuple, end: tuple, control: tuple, steps: int = 50) -> list:
        """Generate Bézier curve points."""
        points = []
        for i in range(steps + 1):
            t = i / steps
            x = (1-t)**2 * start[0] + 2*(1-t)*t * control[0] + t**2 * end[0]
            y = (1-t)**2 * start[1] + 2*(1-t)*t * control[1] + t**2 * end[1]
            # Add micro-jitter for human feel
            x += random.uniform(-1.5, 1.5)
            y += random.uniform(-1.5, 1.5)
            points.append((int(x), int(y)))
        return points

    def move_to(self, page, target_x: int, target_y: int):
        """Move mouse to target with human-like trajectory."""
        start = (self.current_x, self.current_y)
        end = (target_x, target_y)

        # Random control point for curve
        mid_x = (start[0] + end[0]) / 2 + random.uniform(-100, 100)
        mid_y = (start[1] + end[1]) / 2 + random.uniform(-100, 100)
        control = (mid_x, mid_y)

        distance = math.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2)
        steps = max(20, min(80, int(distance / 10)))

        points = self.bezier_curve(start, end, control, steps)

        for px, py in points:
            page.mouse.move(px, py)
            # Variable delay: faster in middle, slower at start/end
            delay = random.uniform(0.003, 0.012)
            time.sleep(delay)

        self.current_x = target_x
        self.current_y = target_y

    def click(self, page, x: int, y: int):
        """Human-like click with slight delay."""
        self.move_to(page, x, y)
        time.sleep(random.uniform(0.05, 0.15))
        page.mouse.click(x, y)
        time.sleep(random.uniform(0.02, 0.08))


class HumanTypist:
    """Type with human-like delays and occasional typos."""

    def __init__(self, typo_rate: float = 0.02):
        self.typo_rate = typo_rate

    async def type(self, page, text: str, selector: str = None):
        """Type text with human-like delays."""
        if selector:
            await page.click(selector)

        for char in text:
            # Random delay between keystrokes (30-150ms)
            delay = random.uniform(0.03, 0.15)
            # Occasional longer pause (thinking)
            if random.random() < 0.05:
                delay += random.uniform(0.2, 0.5)
            await asyncio.sleep(delay)
            await page.keyboard.type(char)

    async def type_with_typos(self, page, text: str, selector: str = None):
        """Type with occasional typos and corrections."""
        if selector:
            await page.click(selector)

        typo_map = {
            'a': 's', 'b': 'v', 'c': 'x', 'd': 'f', 'e': 'w',
            'f': 'g', 'g': 'h', 'h': 'j', 'i': 'u', 'j': 'k',
            'k': 'l', 'l': 'k', 'm': 'n', 'n': 'm', 'o': 'i',
            'p': 'o', 'q': 'w', 'r': 't', 's': 'a', 't': 'r',
            'u': 'y', 'v': 'b', 'w': 'q', 'x': 'z', 'y': 't', 'z': 'x',
        }

        for char in text:
            if random.random() < self.typo_rate and char.lower() in typo_map:
                # Type wrong key
                wrong = typo_map[char.lower()]
                await asyncio.sleep(random.uniform(0.03, 0.1))
                await page.keyboard.type(wrong)
                # Pause, then backspace and correct
                await asyncio.sleep(random.uniform(0.3, 0.8))
                await page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.05, 0.15))

            delay = random.uniform(0.03, 0.15)
            if random.random() < 0.05:
                delay += random.uniform(0.2, 0.5)
            await asyncio.sleep(delay)
            await page.keyboard.type(char)


class StealthBrowser:
    """Playwright-based browser with anti-fingerprint protection."""

    def __init__(self, config: BrowserConfig = None):
        self.config = config or BrowserConfig()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.human_mouse = HumanMouse()
        self.human_typist = HumanTypist()

    async def launch(self, url: str = "") -> dict:
        """Launch stealth browser with anti-detection."""
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()

            # Browser launch args with anti-detection flags
            args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                f"--window-size={self.config.viewport_width},{self.config.viewport_height}",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]

            if self.config.proxy:
                args.append(f"--proxy-server={self.config.proxy}")

            # Launch browser
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless,
                args=args,
            )

            # Create context with realistic settings
            self.context = await self.browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="en-GB",
                timezone_id="Europe/London",
                geolocation={"latitude": 51.5074, "longitude": -0.1278},
                permissions=["geolocation"],
            )

            self.page = await self.context.new_page()

            # Inject anti-detection scripts
            if self.config.anti_fingerprint:
                await self.page.add_init_script(STEALTH_JS)
                await self.page.add_init_script(WEBGL_NOISE_JS)
                await self.page.add_init_script(HUMAN_BEHAVIOR_JS)

            if url:
                await self.page.goto(url, wait_until="domcontentloaded")

            return {
                "success": True,
                "url": self.page.url,
                "title": await self.page.title(),
            }

        except Exception as e:
            logger.error(f"Failed to launch stealth browser: {e}")
            return {"success": False, "error": str(e)}

    async def navigate(self, url: str) -> dict:
        """Navigate to URL with human-like behavior."""
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            return {"success": True, "url": self.page.url, "title": await self.page.title()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str = None, x: int = None, y: int = None):
        """Click element or position with human-like behavior."""
        if selector:
            element = await self.page.query_selector(selector)
            if element:
                box = await element.bounding_box()
                if box:
                    x = int(box["x"] + box["width"] / 2 + random.uniform(-3, 3))
                    y = int(box["y"] + box["height"] / 2 + random.uniform(-3, 3))
        if x is not None and y is not None:
            self.human_mouse.click(self.page, x, y)

    async def type(self, text: str, selector: str = None):
        """Type with human-like delays."""
        await self.human_typist.type(self.page, text, selector)

    async def screenshot(self, path: str = None) -> Optional[str]:
        """Take screenshot."""
        if not path:
            path = f"/tmp/jarvis_screenshot_{int(time.time())}.png"
        await self.page.screenshot(path=path)
        return path

    async def get_cookies(self) -> list:
        """Get all cookies (for session transfer)."""
        return await self.context.cookies()

    async def set_cookies(self, cookies: list):
        """Set cookies (for session restore)."""
        await self.context.add_cookies(cookies)

    async def evaluate(self, js: str):
        """Execute JavaScript in page context."""
        return await self.page.evaluate(js)

    async def close(self):
        """Close browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


class CDPSession:
    """Connect to running Chrome via Chrome DevTools Protocol."""

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222"):
        self.cdp_url = cdp_url
        self.browser = None
        self.context = None
        self.page = None

    async def attach(self) -> dict:
        """Attach to running Chrome via CDP."""
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
            self.context = self.browser.contexts[0]
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

            # Inject anti-detection
            await self.page.add_init_script(STEALTH_JS)

            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        """Disconnect from CDP."""
        if self.playwright:
            await self.playwright.stop()


# ── Convenience Functions ──────────────────────────────────────────────────

async def launch_stealth(url: str = "", headless: bool = False, display: str = ":99") -> StealthBrowser:
    """Quick launch a stealth browser."""
    config = BrowserConfig(headless=headless, display=display)
    browser = StealthBrowser(config)
    await browser.launch(url)
    return browser


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[STEALTH] %(message)s")

    async def main():
        browser = await launch_stealth("https://bot.sannysoft.com/")
        input("Press Enter to close...")
        await browser.close()

    asyncio.run(main())
