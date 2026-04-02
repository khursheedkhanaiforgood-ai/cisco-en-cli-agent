"""
Document-aware web crawler for vendor CLI documentation.

3-phase workflow:
  1. discover_documents(url)  → list all docs/PDFs found on a landing page
  2. extract_from_doc(url)    → download + extract commands from one document
  3. Caller applies UPSERT via load_extracted_to_db()

Supports:
  - HTML pages with <code>/<pre> blocks (Cisco, Extreme HTML docs)
  - Direct PDF links (downloads to temp, calls pdf_extractor)
  - Index pages that list many sub-documents (Cisco command reference list)
"""
import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Keywords that suggest a link leads to a command reference document
_DOC_KEYWORDS = re.compile(
    r"(command|reference|guide|config|cli|syntax|manual|handbook|"
    r"user.guide|admin|operation|network|layer|protocol|routing|switching)",
    re.IGNORECASE,
)

CLI_VERB_RE = re.compile(
    r"^(configure|show|enable|disable|create|delete|clear|copy|install|"
    r"tftp|ping|traceroute|debug|no |router |interface |vlan |spanning-tree|"
    r"ip |ipv6 |aaa |crypto |snmp|ntp |logging |boot |auto-sense|feature |"
    r"l2tracetree|unconfigure|save|reload|reboot|system |switchport |"
    r"network-policy|storm-control|channel-group|lacp|spanning|"
    r"redistribute|prefix-list|route-map|access-list|class-map|policy-map)",
    re.IGNORECASE,
)

TAG_KEYWORDS = {
    "[ONBOARD]":  ["onboard", "zero touch", "ztp", "factory", "reset", "boot", "provision"],
    "[SEC-ID]":   ["security", "aaa", "authentication", "radius", "tacacs", "802.1x", "dot1x", "acl"],
    "[SYS-INFO]": ["system", "version", "inventory", "hardware", "cpu", "memory", "health"],
    "[IF-PHYS]":  ["interface", "port", "speed", "duplex", "poe", "mirror", "lag", "aggregat"],
    "[L2-SEG]":   ["vlan", "spanning tree", "stp", "lldp", "cdp", "fdb", "mac address", "trunk"],
    "[FAB-SDN]":  ["fabric", "spbm", "isis", "i-sid", "vxlan", "lisp", "fabric attach"],
    "[L3-VIRT]":  ["routing", "ospf", "bgp", "vrrp", "hsrp", "route", "vrf", "multicast", "pim"],
    "[DIAG-LOG]": ["troubleshoot", "debug", "ping", "traceroute", "diagnostic", "log", "counter"],
    "[MGMT-OPS]": ["management", "ntp", "snmp", "syslog", "backup", "restore", "save", "tftp"],
}


def classify_tag_from_text(text: str) -> str:
    text = text.lower()
    scores = {tag: sum(1 for kw in kws if kw in text) for tag, kws in TAG_KEYWORDS.items()}
    scores = {k: v for k, v in scores.items() if v > 0}
    return max(scores, key=scores.get) if scores else "[MGMT-OPS]"


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Document Discovery
# ─────────────────────────────────────────────────────────────────────────────

def discover_documents(url: str, max_links: int = 300) -> list[dict]:
    """
    Fetch a landing/index page and return all discoverable documents.

    Each returned document dict:
        {title, url, doc_type ("pdf"|"html"), domain, accessible}

    accessible=False means the link returned a non-200 or requires login.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        return [{"error": "httpx and beautifulsoup4 not installed"}]

    docs = []
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=_HEADERS) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return [{"error": f"HTTP {resp.status_code} — page could not be fetched"}]

            soup = BeautifulSoup(resp.text, "html.parser")
            base_domain = urlparse(url).netloc
            seen_urls = set()

            for a in soup.find_all("a", href=True)[:max_links * 3]:
                href = urljoin(url, a["href"].strip())
                parsed = urlparse(href)

                # Skip anchors, JS links, mailto
                if not parsed.scheme.startswith("http"):
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                link_text = a.get_text(strip=True) or parsed.path.split("/")[-1]

                # Classify document type
                path_lower = parsed.path.lower()
                is_pdf = path_lower.endswith(".pdf")
                is_html = (
                    path_lower.endswith(".html") or
                    path_lower.endswith(".htm") or
                    not Path(path_lower).suffix  # no extension = likely HTML
                )

                # Only include links that look like documentation
                if not (is_pdf or (is_html and _DOC_KEYWORDS.search(link_text + " " + parsed.path))):
                    continue

                docs.append({
                    "title":      link_text[:120],
                    "url":        href,
                    "doc_type":   "pdf" if is_pdf else "html",
                    "domain":     parsed.netloc,
                    "accessible": True,  # optimistic — verified on extraction
                })

                if len(docs) >= max_links:
                    break

    except Exception as e:
        return [{"error": f"Failed to fetch page: {e}"}]

    return docs


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Extract from a single document
# ─────────────────────────────────────────────────────────────────────────────

def extract_from_doc(
    url: str,
    os_col: str,
    max_pages: int = 0,
) -> dict:
    """
    Download and extract CLI commands from one document URL.

    Returns:
        {
            "records":    list[dict],   # extracted command records
            "doc_type":   "pdf"|"html",
            "title":      str,
            "error":      str | None,
        }
    """
    try:
        import httpx
    except ImportError:
        return {"records": [], "error": "httpx not installed", "doc_type": "?", "title": url}

    path_lower = urlparse(url).path.lower()
    is_pdf = path_lower.endswith(".pdf")

    try:
        with httpx.Client(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
            resp = client.get(url)

        if resp.status_code == 403:
            return {
                "records": [], "doc_type": "pdf" if is_pdf else "html",
                "title": url, "error": "HTTP 403 — access denied (login required?)"
            }
        if resp.status_code != 200:
            return {
                "records": [], "doc_type": "pdf" if is_pdf else "html",
                "title": url, "error": f"HTTP {resp.status_code}"
            }

        # Detect actual content type in case server redirects PDF→HTML
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type or is_pdf:
            return _extract_pdf_from_response(resp.content, url, os_col, max_pages)
        else:
            return _extract_html_from_response(resp.text, url, os_col)

    except Exception as e:
        return {"records": [], "error": str(e), "doc_type": "?", "title": url}


def _extract_pdf_from_response(content: bytes, url: str, os_col: str, max_pages: int) -> dict:
    """Write PDF bytes to temp file and run the PDF extractor."""
    from src.extractors.pdf_extractor import extract_from_pdf
    import os

    filename = urlparse(url).path.split("/")[-1] or "download.pdf"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        records = extract_from_pdf(
            tmp_path,
            os_col=os_col,
            source_name=filename,
            max_pages=max_pages,
        )
    finally:
        os.unlink(tmp_path)

    return {
        "records":  records,
        "doc_type": "pdf",
        "title":    filename,
        "error":    None,
    }


def _extract_html_from_response(html: str, url: str, os_col: str) -> dict:
    """Extract CLI commands from an HTML documentation page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.find("title")
    title = page_title.get_text(strip=True) if page_title else urlparse(url).path.split("/")[-1]

    records = []
    seen = set()

    # Strategy 1: <pre> and <code> blocks — most common in Cisco/Extreme HTML docs
    for block in soup.find_all(["pre", "code", "tt", "samp"]):
        block_text = block.get_text()
        section_heading = _nearest_heading(block)
        commands = []

        for line in block_text.splitlines():
            line = line.strip()
            if not line or len(line) < 3:
                continue
            # Strip prompts
            clean = re.sub(r"^\S+[#>$]\s*", "", line).strip()
            if clean and CLI_VERB_RE.match(clean) and clean not in seen:
                seen.add(clean)
                commands.append(clean)

        if commands and section_heading:
            tag = classify_tag_from_text(section_heading + " " + title)
            intent = section_heading[:200]
            records.append({
                "tag":              tag,
                "functional_intent": intent,
                "commands_text":    " | ".join(commands[:10]),
                os_col:             " | ".join(commands[:10]),
                "source_ref":       urlparse(url).netloc,
                "page_ref":         url,
                "notes":            f"Extracted from: {title[:100]}",
            })

    # Strategy 2: If no structured blocks, fall back to all lines
    if not records:
        all_text = soup.get_text(separator="\n")
        commands = []
        for line in all_text.splitlines():
            line = line.strip()
            clean = re.sub(r"^\S+[#>$]\s*", "", line).strip()
            if clean and CLI_VERB_RE.match(clean) and clean not in seen:
                seen.add(clean)
                commands.append(clean)

        if commands:
            tag = classify_tag_from_text(title)
            records.append({
                "tag":              tag,
                "functional_intent": title[:200],
                "commands_text":    " | ".join(commands[:10]),
                os_col:             " | ".join(commands[:10]),
                "source_ref":       urlparse(url).netloc,
                "page_ref":         url,
                "notes":            f"Extracted from: {title[:100]}",
            })

    return {
        "records":  records,
        "doc_type": "html",
        "title":    title,
        "error":    None,
    }


def _nearest_heading(tag) -> str:
    """Walk up/back in DOM to find the nearest h1-h4 before this block."""
    for heading_tag in ["h1", "h2", "h3", "h4"]:
        # Check siblings before this element
        prev = tag.find_previous(heading_tag)
        if prev:
            return prev.get_text(strip=True)
    parent = tag.parent
    if parent:
        title = parent.get("id") or parent.get("class", [""])[0]
        if title:
            return str(title).replace("-", " ").replace("_", " ")
    return ""
