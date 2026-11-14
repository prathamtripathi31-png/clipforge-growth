#!/usr/bin/env python3
"""Bounded, key-free cloud research; editorial hypotheses, never posting actions."""
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path


ALLOWED_HOSTS = frozenset({
    "support.google.com", "blog.youtube", "youtube.com", "www.youtube.com",
    "news.google.com", "ads.tiktok.com", "newsroom.tiktok.com", "www.tiktok.com",
})
TACTICS = {
    "youtube": {
        "yt_specific_title": "Use a specific, accurate title that explains the clip's subject.",
        "yt_open_on_payoff": "Open on a compelling moment, then deliver its promised payoff.",
        "yt_one_clear_idea": "Choose one understandable idea with a complete payoff.",
    },
    "tiktok": {
        "tt_immediate_context": "Make the subject and stakes clear immediately.",
        "tt_caption_context": "Use concise caption or on-screen context to help comprehension.",
        "tt_clear_payoff": "Give the opening hook a clear, relevant payoff.",
    },
}
DOCS = (
    ("youtube", "https://support.google.com/youtube/answer/16559650?hl=en",
     "YouTube Shorts content tips", "official_guidance"),
    ("youtube", "https://support.google.com/youtube/answer/12942217?hl=en",
     "YouTube Shorts analytics tips", "official_guidance"),
    ("youtube", "https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/",
     "YouTube Shorts deep dive: hooks and mini stories", "official_guidance"),
    ("tiktok", "https://ads.tiktok.com/business/en/guides/what-is-ad-creative-guide",
     "TikTok ad creative guidance", "ad_guidance_hypothesis"),
)
QUERIES = (
    "site:blog.youtube Shorts audience retention creator tips when:30d",
    "site:newsroom.tiktok.com creator content audience tips when:30d",
)
CHANNEL_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id=UCMupoVC9nl1Oku3FaAvAH4Q"
MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
MAX_RSS_BYTES = 128 * 1024
MAX_JSON_BYTES = 32 * 1024
TIMEOUT_SECONDS = 12


def safe_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    if (len(url) > 1000 or p.scheme != "https" or p.hostname not in ALLOWED_HOSTS
            or p.username or p.password or p.port not in (None, 443)):
        raise ValueError("research URL is not on the trusted HTTPS allowlist")
    return url


class TrustedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, max_bytes: int = MAX_DOCUMENT_BYTES) -> bytes:
    safe_url(url)
    req = urllib.request.Request(url, headers={
        "User-Agent": "ClipForgeGrowthResearch/1.0 (text-only editorial research)",
        "Accept": "text/html,application/xml,application/rss+xml,application/atom+xml,text/xml",
    })
    opener = urllib.request.build_opener(TrustedRedirects())
    with opener.open(req, timeout=TIMEOUT_SECONDS) as response:
        safe_url(response.geturl())
        content_type = response.headers.get_content_type()
        if content_type not in ("text/html", "text/plain", "application/xml", "text/xml",
                                "application/rss+xml", "application/atom+xml"):
            raise ValueError("research response is not text or XML")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("research response exceeds byte limit")
        return body


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.ignored:
            self.ignored -= 1

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def plain_text(body: bytes) -> str:
    parser = VisibleText()
    parser.feed(body.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def supported_tactics(platform: str, text: str) -> list[str]:
    """Select fixed local advice; retrieved pages can never supply prompt instructions."""
    text = text.lower()
    patterns = {
        "youtube": {
            "yt_specific_title": r"\b(title|titles|searchable|search terms)\b",
            "yt_open_on_payoff": r"\b(hook|hooks|attention|first few seconds|first second)\b",
            "yt_one_clear_idea": r"\b(story|storytelling|clear message|one idea|concise)\b",
        },
        "tiktok": {
            "tt_immediate_context": r"\b(hook|hooks|first six seconds|first 6 seconds|attention)\b",
            "tt_caption_context": r"\b(caption|captions|text overlay|text overlays|on-screen text)\b",
            "tt_clear_payoff": r"\b(story|storytelling|structure|hook.body.close|message)\b",
        },
    }
    return [key for key, pattern in patterns[platform].items() if re.search(pattern, text)]


def rss_items(body: bytes, limit: int = 5, platform: str | None = None) -> list[dict]:
    # ElementTree does not fetch external entities. No pages/media linked by RSS are fetched.
    root = ET.fromstring(body)
    items = []
    for entry in root.findall("./channel/item")[:limit]:
        url = entry.findtext("link") or ""
        try:
            safe_url(url)
        except ValueError:
            continue
        title = plain_text((entry.findtext("title") or "").encode())[:180]
        source = entry.find("source")
        source_url = source.get("url", "") if source is not None else ""
        try:
            safe_url(source_url)
        except ValueError:
            continue
        # Search query scope alone is not a trust boundary: verify the item's publisher too.
        publisher_host = urllib.parse.urlsplit(source_url).hostname
        platform_publishers = {
            "youtube": {"support.google.com", "blog.youtube", "youtube.com", "www.youtube.com"},
            "tiktok": {"ads.tiktok.com", "newsroom.tiktok.com", "www.tiktok.com"},
        }
        if platform and publisher_host not in platform_publishers[platform]:
            continue
        items.append({"url": url, "title": title, "kind": "official_news_metadata"})
    return items


def channel_titles(body: bytes) -> list[str]:
    root = ET.fromstring(body)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    return [(entry.findtext("a:title", default="", namespaces=ns))[:180]
            for entry in root.findall("a:entry", ns)[:5]]


def research(fetcher=fetch, now: datetime | None = None) -> tuple[dict, str]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("research time must be timezone aware")
    now = now.astimezone(timezone.utc)
    platforms = {p: {"tactics": [], "evidence": []} for p in TACTICS}
    checked, succeeded = 0, 0
    official_ok = set()
    limitations = [
        "Recommendations are editorial hypotheses, not proof of organic growth or promises of views.",
        "TikTok ad guidance is ad-derived; test its relevance to organic gaming clips cautiously.",
        "Public feed titles do not establish retention, audience satisfaction, or causation.",
        "No authenticated channel analytics are available to this key-free cloud researcher.",
    ]
    for platform, url, title, kind in DOCS:
        checked += 1
        try:
            text = plain_text(fetcher(url, MAX_DOCUMENT_BYTES))
            if len(text) < 100:
                raise ValueError("official page returned insufficient visible text")
            succeeded += 1
            official_ok.add(platform)
            platforms[platform]["tactics"] = sorted(set(platforms[platform]["tactics"])
                                                   | set(supported_tactics(platform, text)))
            platforms[platform]["evidence"].append({"url": url, "title": title, "kind": kind})
            if not platforms[platform]["tactics"]:
                limitations.append(f"{platform}: official page loaded but supported no configured tactic.")
        except (OSError, ValueError, ET.ParseError) as exc:
            limitations.append(f"{platform}: official guidance unavailable ({type(exc).__name__}).")

    for platform, query in zip(("youtube", "tiktok"), QUERIES):
        checked += 1
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
            "q": query, "hl": "en-US", "gl": "US", "ceid": "US:en",
        })
        try:
            items = rss_items(fetcher(url, MAX_RSS_BYTES), platform=platform)
            succeeded += 1
            room = 6 - len(platforms[platform]["evidence"])
            platforms[platform]["evidence"].extend(items[:room])
            # Titles from a verified official publisher can select a fixed local hypothesis.
            # They never enter ClipForge's model prompts as instructions or asserted facts.
            for item in items[:room]:
                platforms[platform]["tactics"] = sorted(set(platforms[platform]["tactics"])
                    | set(supported_tactics(platform, item["title"])))
            if not items:
                limitations.append(f"{platform}: recent official news search returned no trusted items.")
        except (OSError, ValueError, ET.ParseError) as exc:
            limitations.append(f"{platform}: optional news search unavailable ({type(exc).__name__}).")

    checked += 1
    titles = []
    try:
        titles = channel_titles(fetcher(CHANNEL_RSS, MAX_RSS_BYTES))
        succeeded += 1
        if not titles:
            limitations.append("Optional public YouTube feed returned no titles.")
    except (OSError, ValueError, ET.ParseError) as exc:
        limitations.append(f"Optional public YouTube feed unavailable ({type(exc).__name__}).")
    missing = set(platforms) - official_ok
    if missing:
        raise RuntimeError("No official guidance source succeeded for " + ", ".join(sorted(missing))
                           + "; retaining previous report unchanged.")

    strategy = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "platforms": platforms,
        "research": {"sources_checked": checked, "sources_ok": succeeded,
                     "queries": list(QUERIES), "limitations": limitations},
    }
    encoded = json.dumps(strategy, ensure_ascii=False, indent=2).encode()
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("strategy exceeds 32KB")
    report = ["# ClipForge growth research", "", f"Generated: {now.isoformat()}", "",
              "Runs on a cloud runner. No videos, credentials, or raw pages are stored.", ""]
    for platform in ("youtube", "tiktok"):
        report += [f"## {platform.title()}", ""]
        if not platforms[platform]["tactics"]:
            report += ["No supported new tactic; keep the existing editorial baseline.", ""]
        for key in platforms[platform]["tactics"]:
            report.append(f"- Hypothesis: {TACTICS[platform][key]}")
        report.append("")
        for item in platforms[platform]["evidence"]:
            title = html.escape(item["title"]).replace("[", "\\[").replace("]", "\\]")
            report.append(f"- [{title}]({item['url']}) — {item['kind']}")
        report.append("")
    if titles:
        report += ["## Public channel title observations", "",
                   "Titles only; no evidence these formats caused growth.", ""]
        report.extend("- " + re.sub(r"[\r\n]", " ", t).replace("<", "&lt;") for t in titles)
        report.append("")
    report += ["## Limits and source availability", "",
               f"Successful text sources: {succeeded}/{checked}.", ""]
    report.extend("- " + line for line in limitations)
    return strategy, "\n".join(report) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()
    # Research completes and validates before either report is replaced.
    strategy, report = research()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "strategy.json").write_text(
        json.dumps(strategy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "REPORT.md").write_text(report, encoding="utf-8")
    print(f"Research complete: {strategy['research']['sources_ok']}/"
          f"{strategy['research']['sources_checked']} text sources available.")


if __name__ == "__main__":
    main()
