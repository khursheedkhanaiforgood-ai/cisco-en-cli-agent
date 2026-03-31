"""Central configuration for CISCO-EN CLI Mapping Agent."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SEED_DIR = DATA_DIR / "seed"
EXTRACTED_DIR = DATA_DIR / "extracted"

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/cli_mapping")
# Railway injects postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

# ── Embeddings ────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension

# ── RAG Search ────────────────────────────────────────────────────────────────
RAG_TOP_K = 10           # Default number of results returned
RAG_SIMILARITY_THRESHOLD = 0.35  # Minimum cosine similarity to include

# ── Functional Bins ───────────────────────────────────────────────────────────
FUNCTIONAL_TAGS = [
    "[ONBOARD]",    # Onboarding & Provisioning
    "[SEC-ID]",     # Identity, AAA & Policy
    "[SYS-INFO]",   # System Health & Inventory
    "[IF-PHYS]",    # Physical Interface & Port
    "[L2-SEG]",     # VLAN & Layer 2 Segmentation
    "[FAB-SDN]",    # Fabric & SDN Underlay
    "[L3-VIRT]",    # Layer 3 & Routing
    "[DIAG-LOG]",   # Troubleshooting & Diagnostics
    "[MGMT-OPS]",   # Operations & Management
]

TAG_LABELS = {
    "[ONBOARD]":  "Onboarding & Provisioning",
    "[SEC-ID]":   "Identity, AAA & Policy",
    "[SYS-INFO]": "System Health & Inventory",
    "[IF-PHYS]":  "Physical Interface & Port",
    "[L2-SEG]":   "VLAN & Layer 2 Segmentation",
    "[FAB-SDN]":  "Fabric & SDN Underlay",
    "[L3-VIRT]":  "Layer 3 & Routing",
    "[DIAG-LOG]": "Troubleshooting & Diagnostics",
    "[MGMT-OPS]": "Operations & Management",
}

TAG_DESCRIPTIONS = {
    "[ONBOARD]":  "Factory reset, ZTP, boot flags, initial login, Zero Touch Fabric",
    "[SEC-ID]":   "AAA, TACACS+, RADIUS, 802.1X, TrustSec/ONEPolicy, SGT/GBP",
    "[SYS-INFO]": "show version, inventory, environment, CPU, memory, hardware",
    "[IF-PHYS]":  "Port speed/duplex, enable/disable, PoE, mirroring, stacking, LAG",
    "[L2-SEG]":   "VLAN create/assign, trunk/access, STP, RSTP, MSTP, EAPS, LLDP, CDP",
    "[FAB-SDN]":  "IS-IS, SPBM, LISP, VXLAN, I-SID, VNI, Fabric Attach, SD-Access",
    "[L3-VIRT]":  "IP addressing, OSPF, BGP, RIP, VRRP, static routes, VRF, VSN",
    "[DIAG-LOG]": "ping, traceroute, debug, l2tracetree, show log, show counters",
    "[MGMT-OPS]": "Save config, NTP, SNMP, Syslog, backup/restore, RMON, licensing",
}

# ── OS Column Definitions ─────────────────────────────────────────────────────
OS_COLUMNS = [
    "cisco_ios",
    "cisco_iosxe",
    "cisco_nxos",
    "extreme_exos",
    "extreme_voss",
    "extreme_slxos",
]

OS_LABELS = {
    "cisco_ios":     "Cisco IOS",
    "cisco_iosxe":   "Cisco IOS-XE 17.x",
    "cisco_nxos":    "Cisco NX-OS 10.x",
    "extreme_exos":  "Extreme EXOS 33.x",
    "extreme_voss":  "Extreme VOSS 9.x",
    "extreme_slxos": "Extreme SLX-OS 20.x",
}

OS_SHORT = {
    "cisco_ios":     "IOS",
    "cisco_iosxe":   "IOS-XE",
    "cisco_nxos":    "NX-OS",
    "extreme_exos":  "EXOS",
    "extreme_voss":  "VOSS",
    "extreme_slxos": "SLX-OS",
}

# ── Web Crawler ───────────────────────────────────────────────────────────────
CRAWL_RATE_LIMIT_SEC = 1.0   # Seconds between requests
CRAWL_CACHE_DIR = BASE_DIR / ".crawl_cache"

VENDOR_SEED_URLS = {
    "extreme_exos": "https://documentation.extremenetworks.com/exos_commands_31.4/",
    "extreme_voss": "https://documentation.extremenetworks.com/VOSS/SW/89/vossuserguide/",
    "extreme_slxos": "https://documentation.extremenetworks.com/slxos/",
}

# ── UI ────────────────────────────────────────────────────────────────────────
APP_TITLE = "CISCO-EN CLI Mapping Agent"
APP_SUBTITLE = "The New Rosetta Stone — CLI Command Translator & AI Agent"
APP_ICON = "🔁"
