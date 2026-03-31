"""
Web crawler for Extreme Networks documentation sites.
Crawls configured vendor URLs to discover and extract CLI command mappings.

Usage:
    python -m src.extractors.web_crawler                    # Crawl default Extreme docs
    python -m src.extractors.web_crawler --url <url>        # Crawl specific URL
    python -m src.extractors.web_crawler --dry-run          # List URLs without inserting
"""
import logging
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# CLI verb patterns to detect command lines in doc pages
CLI_VERB_RE = re.compile(
    r"^(configure|show|enable|disable|create|delete|clear|copy|install|"
    r"tftp|ping|traceroute|debug|no |router |interface |vlan |spanning-tree|"
    r"ip |ipv6 |aaa |crypto |snmp|ntp |logging |boot |auto-sense|"
    r"l2tracetree|unconfigure|save|reload|reboot|feature |system )",
    re.IGNORECASE,
)

TAG_KEYWORDS = {
    "[ONBOARD]":  ["onboard", "zero touch", "ztp", "factory", "reset", "boot", "provision", "auto-sense"],
    "[SEC-ID]":   ["security", "aaa", "authentication", "radius", "tacacs", "802.1x", "dot1x", "acl", "policy"],
    "[SYS-INFO]": ["system", "version", "inventory", "hardware", "cpu", "memory", "health", "alarm"],
    "[IF-PHYS]":  ["interface", "port", "speed", "duplex", "poe", "mirror", "lag", "stack", "aggregat"],
    "[L2-SEG]":   ["vlan", "spanning tree", "stp", "lldp", "cdp", "fdb", "mac address", "trunk", "eaps"],
    "[FAB-SDN]":  ["fabric", "spbm", "isis", "i-sid", "vxlan", "lisp", "fabric attach", "sd-access"],
    "[L3-VIRT]":  ["routing", "ospf", "bgp", "vrrp", "hsrp", "route", "vrf", "multicast", "pim", "igmp"],
    "[DIAG-LOG]": ["troubleshoot", "debug", "ping", "traceroute", "diagnostic", "log", "capture", "counter"],
    "[MGMT-OPS]": ["management", "ntp", "snmp", "syslog", "backup", "restore", "save", "tftp", "firmware"],
}


def classify_tag_from_text(text: str) -> str:
    text = text.lower()
    scores = {}
    for tag, keywords in TAG_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[tag] = score
    return max(scores, key=scores.get) if scores else "[MGMT-OPS]"


def crawl_url(
    start_url: str,
    os_col: str,
    max_pages: int = 100,
    rate_limit: float = 1.0,
    dry_run: bool = False,
) -> dict:
    """
    Crawl documentation pages starting from start_url, extract CLI commands,
    and insert into the database.

    Args:
        start_url: Root URL to begin crawling
        os_col: Which OS column to populate (e.g. 'extreme_exos')
        max_pages: Maximum pages to crawl
        rate_limit: Seconds between requests
        dry_run: If True, don't insert into DB

    Returns:
        {'crawled': int, 'records': int, 'inserted': int}
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("httpx and beautifulsoup4 required: pip install httpx beautifulsoup4")
        return {"crawled": 0, "records": 0, "inserted": 0}

    visited = set()
    queue = [start_url]
    base_domain = urlparse(start_url).netloc
    all_records = []

    _log_crawl_start(start_url, os_col, max_pages, dry_run)

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                resp = client.get(url, headers={"User-Agent": "CLI-Mapping-Bot/1.0"})
                if resp.status_code != 200:
                    logger.debug(f"  Skip {url} ({resp.status_code})")
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                page_title = soup.find("title")
                title_text = page_title.get_text(strip=True) if page_title else url

                # Extract CLI commands from code blocks and pre tags
                commands = _extract_commands_from_page(soup)

                if commands:
                    tag = classify_tag_from_text(title_text + " " + url)
                    record = {
                        "tag": tag,
                        "functional_intent": title_text[:200],
                        "commands_text": " | ".join(commands[:10]),
                        os_col: " | ".join(commands[:10]),
                        "source_ref": urlparse(url).netloc,
                        "page_ref": url,
                        "notes": f"Crawled from {url}",
                    }
                    all_records.append(record)
                    logger.info(f"  [{len(all_records)}] {tag} — {title_text[:60]} ({len(commands)} cmds)")

                # Queue same-domain links
                for link in soup.find_all("a", href=True):
                    href = urljoin(url, link["href"])
                    parsed = urlparse(href)
                    if parsed.netloc == base_domain and href not in visited:
                        queue.append(href)

                time.sleep(rate_limit)

            except Exception as e:
                logger.warning(f"  Error crawling {url}: {e}")

    logger.info(f"Crawled {len(visited)} pages, found {len(all_records)} records")

    inserted = 0
    if not dry_run and all_records:
        inserted = _insert_crawled_records(all_records, os_col)

    return {"crawled": len(visited), "records": len(all_records), "inserted": inserted}


def _extract_commands_from_page(soup) -> list[str]:
    """Extract CLI command lines from HTML page."""
    commands = []
    seen = set()

    # Code blocks and pre tags are the primary source
    for tag in soup.find_all(["code", "pre", "tt"]):
        text = tag.get_text()
        for line in text.splitlines():
            line = line.strip()
            if line and len(line) > 3 and CLI_VERB_RE.match(line):
                # Strip shell prompts
                clean = re.sub(r"^\S+[#>$]\s*", "", line).strip()
                if clean and clean not in seen and len(clean) > 3:
                    seen.add(clean)
                    commands.append(clean)

    return commands[:20]  # Max 20 per page


def _log_crawl_start(url, os_col, max_pages, dry_run):
    logger.info("=" * 60)
    logger.info(f"  Web Crawler — {os_col}")
    logger.info(f"  Start URL:  {url}")
    logger.info(f"  Max pages:  {max_pages}")
    logger.info(f"  Dry run:    {dry_run}")
    logger.info("=" * 60)


def _insert_crawled_records(records: list[dict], os_col: str) -> int:
    """Insert crawled records into the database."""
    from src.database.connection import get_session
    from src.database.models import CLIMapping
    from src.embeddings.encoder import encode_batch

    intents = [r["functional_intent"] for r in records]
    embeddings = encode_batch(intents)
    inserted = 0

    with get_session() as session:
        for record, embedding in zip(records, embeddings):
            mapping = CLIMapping(
                tag=record["tag"],
                functional_intent=record["functional_intent"],
                **{os_col: record.get("commands_text", "")},
                notes=record.get("notes", ""),
                source_ref=record.get("source_ref", ""),
                page_ref=record.get("page_ref", ""),
                confidence=0.7,
                is_verified=False,
                embedding=embedding,
            )
            session.add(mapping)
            inserted += 1

    logger.info(f"Inserted {inserted} crawled records")
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    from src.config import VENDOR_SEED_URLS

    dry_run = "--dry-run" in sys.argv
    custom_url = None
    if "--url" in sys.argv:
        idx = sys.argv.index("--url")
        if idx + 1 < len(sys.argv):
            custom_url = sys.argv[idx + 1]

    if custom_url:
        os_col = "extreme_exos"  # Default; override with --os flag if needed
        crawl_url(custom_url, os_col=os_col, dry_run=dry_run)
    else:
        for os_col, url in VENDOR_SEED_URLS.items():
            result = crawl_url(url, os_col=os_col, max_pages=50, dry_run=dry_run)
            logger.info(f"  {os_col}: {result}")
