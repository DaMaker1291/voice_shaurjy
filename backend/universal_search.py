"""
Universal Search Engine — searches EVERYTHING: Google, Bing, DuckDuckGo, Wikipedia,
web scraping, shopping, travel, news. Returns REAL results, never fabricates.
"""

import re
import json
import urllib.request
import urllib.parse
import ssl
from typing import Optional


def _fetch_url(url: str, timeout: int = 10) -> str:
    """Fetch a URL and return text content."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return resp.read().decode("utf-8", errors="ignore")


def _google_search(query: str, num: int = 5) -> list[dict]:
    """Search Google via lite endpoint."""
    try:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num={num}&hl=en&gl=us"
        html = _fetch_url(url)
        results = []
        # Modern Google uses data-sokoban-container or div.r blocks
        # Try to extract from <a> tags inside <div class="r">
        blocks = re.findall(r'<a href="/url\?q=(https?[^&"]+)[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
        for link, title_html in blocks:
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            if title and len(title) > 5:
                results.append({"title": title, "url": urllib.parse.unquote(link), "snippet": ""})
        if results:
            return results[:num]
        # Fallback: extract any external links with nearby text
        links = re.findall(r'href="(https?://(?!google|gstatic|youtube\.com/embed)[^"]+)"', html)
        for link in links[:num]:
            results.append({"title": urllib.parse.unquote(link).split("/")[-1][:80], "url": link, "snippet": ""})
        return results[:num]
    except Exception:
        pass
    return []


def _bing_search(query: str, num: int = 5) -> list[dict]:
    """Search Bing."""
    try:
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={num}"
        html = _fetch_url(url)
        results = []
        # Bing uses <li class="b_algo"> blocks
        blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html, re.DOTALL)
        for block in blocks:
            title_m = re.search(r'<a[^>]*href="(https?[^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if title_m:
                link = title_m.group(1)
                title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
                snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
                snippet = re.sub(r'<[^>]+>', '', snippet_m.group(1)).strip() if snippet_m else ""
                if title:
                    results.append({"title": title, "url": link, "snippet": snippet[:300]})
        if results:
            return results[:num]
        # Fallback: any bing result link
        links = re.findall(r'href="(https?://(?!bing|microsoft)[^"]+)"', html)
        for link in links[:num]:
            results.append({"title": link.split("/")[-1][:80], "url": link, "snippet": ""})
        return results[:num]
    except Exception:
        pass
    return []


def _duckduckgo_search(query: str, num: int = 5) -> list[dict]:
    """Search DuckDuckGo."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num))
        return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")[:300]} for r in results]
    except Exception:
        pass
    return []


def _wikipedia_search(query: str, num: int = 3) -> list[dict]:
    """Search Wikipedia API."""
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit={num}"
        data = json.loads(_fetch_url(url))
        results = []
        for r in data.get("query", {}).get("search", []):
            title = r.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", r.get("snippet", ""))
            results.append({"title": title, "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}", "snippet": snippet[:300]})
        return results
    except Exception:
        pass
    return []


def _wikipedia_summary(query: str) -> Optional[str]:
    """Get a Wikipedia summary for a topic."""
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
        data = json.loads(_fetch_url(url))
        return data.get("extract", "")
    except Exception:
        pass
    return None


def _scrape_url(url: str, max_chars: int = 2000) -> str:
    """Scrape text content from a URL."""
    try:
        html = _fetch_url(url)
        # Remove scripts, styles
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        html = re.sub(r'<[^>]+>', ' ', html)
        html = re.sub(r'\s+', ' ', html).strip()
        return html[:max_chars]
    except Exception:
        return ""


def universal_search(query: str, num: int = 5) -> str:
    """Search EVERYTHING and return combined real results.
    Tries multiple sources, combines best results."""
    all_results = []
    sources_tried = []

    # 1. Wikipedia (fast, reliable, good for facts)
    wiki = _wikipedia_search(query, num=2)
    if wiki:
        all_results.extend(wiki)
        sources_tried.append("Wikipedia")

    # 2. DuckDuckGo (privacy-focused, usually works)
    ddg = _duckduckgo_search(query, num=num)
    if ddg:
        all_results.extend(ddg)
        sources_tried.append("DuckDuckGo")

    # 3. Google (best results, may be blocked)
    google = _google_search(query, num=num)
    if google:
        all_results.extend(google)
        sources_tried.append("Google")

    # 4. Bing (backup)
    if len(all_results) < 3:
        bing = _bing_search(query, num=num)
        if bing:
            all_results.extend(bing)
            sources_tried.append("Bing")

    # Deduplicate by title similarity
    seen_titles = set()
    unique = []
    for r in all_results:
        title_key = r["title"].lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique.append(r)

    if not unique:
        return f"I couldn't find results for '{query}' right now."

    # Format results
    lines = [f"🔍 **Search results for '{query}'** (from {', '.join(sources_tried)}):\n"]
    for i, r in enumerate(unique[:num], 1):
        title = r["title"]
        snippet = r["snippet"]
        url = r["url"]
        lines.append(f"**{i}. {title}**")
        if snippet:
            lines.append(f"   {snippet[:250]}")
        if url:
            lines.append(f"   🔗 {url}")
        lines.append("")

    return "\n".join(lines)


def shopping_search(query: str, num: int = 5) -> str:
    """Search for products/prices across shopping sites."""
    # Clean query
    clean_q = re.sub(r'\b(buy|price|cheap|deal|shop|cost|how much|find|best|compare)\b', '', query, flags=re.I).strip()
    if not clean_q:
        clean_q = query

    results = universal_search(clean_q, num=num)

    # Also try specific shopping sites
    extra = []
    sites = [
        ("Amazon", f"site:amazon.com {query}"),
        ("eBay", f"site:ebay.com {query}"),
        ("Walmart", f"site:walmart.com {query}"),
    ]
    for name, site_q in sites:
        try:
            r = _google_search(site_q, num=2)
            if r:
                for item in r[:1]:
                    extra.append(f"🛒 **{name}**: {item['title'][:80]} — {item.get('snippet', '')[:150]}")
        except Exception:
            pass

    if extra:
        results += "\n\n**Price comparison:**\n" + "\n".join(extra)

    return results


def travel_search(query: str, num: int = 5) -> str:
    """Search for travel/holiday info — flights, hotels, destinations."""
    # General travel search
    results = universal_search(query, num=num)

    # Try travel-specific sites
    extra = []
    travel_sites = [
        ("Flights", f"site:skyscanner.com OR site:kayak.com {query} flights"),
        ("Hotels", f"site:booking.com OR site:hotels.com {query} hotel"),
        ("Reviews", f"site:tripadvisor.com {query}"),
    ]
    for name, site_q in travel_sites:
        try:
            r = _google_search(site_q, num=2)
            if r:
                for item in r[:1]:
                    extra.append(f"✈️ **{name}**: {item['title'][:80]} — {item.get('snippet', '')[:150]}")
        except Exception:
            pass

    if extra:
        results += "\n\n**Travel options:**\n" + "\n".join(extra)

    return results


def deep_research(query: str, max_chars: int = 4000) -> str:
    """Deep research — search multiple sources, scrape top results, synthesize."""
    # Step 1: Search
    search_results = universal_search(query, num=8)

    # Step 2: Scrape top results for more detail
    urls_to_scrape = []
    for line in search_results.split("\n"):
        if line.startswith("🔗 "):
            url = line[2:].strip()
            if url.startswith("http"):
                urls_to_scrape.append(url)

    scraped_content = []
    for url in urls_to_scrape[:3]:  # Scrape top 3
        content = _scrape_url(url, max_chars=1500)
        if content and len(content) > 100:
            scraped_content.append(f"**From {url[:50]}:**\n{content[:1000]}")

    # Step 3: Combine
    output = search_results
    if scraped_content:
        output += "\n\n**Detailed information:**\n\n" + "\n\n---\n\n".join(scraped_content)

    return output[:max_chars]
