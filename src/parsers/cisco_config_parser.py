"""
Cisco IOS / IOS-XE / NX-OS configuration parser.

Parses a raw config string (from .cfg, .txt, .conf, or extracted .docx text)
into a list of ConfigSection dataclasses.  Each section represents one logical
block: interface, router, vlan, ip dhcp pool, line, aaa, policy-map, etc.
Global (un-indented, non-header) commands are collected into a "global" section.
Prose/narrative text (plain English, not a Cisco keyword) is collected separately
and used only for device-role labelling — never translated.

Supported source OS:  Cisco IOS, IOS-XE 17.x, NX-OS 10.x

Usage:
    from src.parsers.cisco_config_parser import parse_config, detect_source_os
    result = parse_config(raw_text)
    # result.sections   — list[ConfigSection]
    # result.devices    — list[DeviceConfig]  (split on hostname boundaries)
    # result.prose      — list[str]           (narrative text found in file)
    # result.source_os  — str                 (detected OS hint)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Cisco keyword sets ──────────────────────────────────────────────────────

# Keywords that START a new indented section (sub-mode headers)
_SECTION_HEADERS: set[str] = {
    "interface", "router", "line", "vlan", "ip", "ipv6",
    "policy-map", "class-map", "route-map", "key", "keychain",
    "address-family", "vrf", "crypto", "spanning-tree",
    "redundancy", "voice", "dial-peer", "telephony-service",
    "controller", "track", "object-group", "zone", "zone-pair",
    "parameter-map", "template", "event", "action",
    "mac", "pseudowire-class", "l2vpn", "bridge-domain",
    "aaa", "tacacs", "radius", "dot1x",
}

# Keywords valid as GLOBAL (un-indented, no sub-mode body)
_GLOBAL_KEYWORDS: set[str] = {
    "hostname", "enable", "service", "no", "username", "logging",
    "snmp-server", "ntp", "clock", "banner", "boot", "archive",
    "license", "system", "errdisable", "spanning-tree",
    "ip", "ipv6", "mac", "arp", "cdp", "lldp",
    "access-list", "prefix-list", "as-path", "community-list",
    "dns-server", "domain", "mtu", "speed", "duplex",
    "feature",                 # NX-OS prerequisite lines
    "version", "platform",
    "end", "exit",
}

# Combined: any line starting with one of these (case-insensitive) is CLI
_ALL_CLI_KEYWORDS: set[str] = _SECTION_HEADERS | _GLOBAL_KEYWORDS

# Regex: a section-marker comment  ! --- Title ---  or  ! === Title ===
_SECTION_MARKER_RE = re.compile(
    r"^!\s*[-=]{2,}\s*(.+?)\s*[-=]*\s*$"
)

# Regex: plain !  (delimiter with no content worth keeping)
_BARE_BANG_RE = re.compile(r"^!\s*$")

# Regex: detect indented sub-command (starts with whitespace)
_INDENT_RE = re.compile(r"^(\s+)\S")

# Regex: NX-OS "feature <proto>" line
_NXOS_FEATURE_RE = re.compile(r"^feature\s+\S+", re.IGNORECASE)

# Single-line `ip` commands that must NOT open a sub-mode section
_IP_SINGLE_LINE: set[str] = {
    "ip routing", "ip default-gateway", "ip route", "ip name-server",
    "ip domain-name", "ip domain-lookup", "ip forward-protocol",
    "ip classless", "ip subnet-zero", "ip cef", "ip multicast-routing",
    "ip helper-address", "ip http", "ip ftp", "ip tftp",
    "ip arp", "ip sla", "ip flow", "ip nat",
}


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class ConfigLine:
    """A single line within a section body."""
    text: str              # original text (stripped of leading indent)
    raw: str               # original text with indentation preserved
    indent: int            # indent level in spaces


@dataclass
class ConfigSection:
    """
    One logical block in a Cisco configuration.

    section_type values:
        "interface"   – interface GigabitEthernet1/0/1
        "vlan"        – vlan 10 / name DATA
        "router"      – router ospf 1
        "dhcp"        – ip dhcp pool NAME
        "line"        – line vty 0 15
        "aaa"         – aaa new-model ...
        "policy-map"  – policy-map PM_NAME
        "class-map"   – class-map CM_NAME
        "route-map"   – route-map RM_NAME
        "nxos-feature"– NX-OS  feature ospf  (prerequisite, not translated)
        "global"      – un-indented commands not belonging to a section
        "comment"     – section marker  ! --- TITLE ---
        "prose"       – plain English narrative (not translated)
    """
    section_type: str
    header: str                          # first line (the section header)
    body: list[ConfigLine] = field(default_factory=list)
    label: Optional[str] = None          # from nearest preceding ! --- label ---
    device_name: Optional[str] = None    # hostname this section belongs to

    @property
    def raw_text(self) -> str:
        lines = [self.header]
        for cl in self.body:
            lines.append(cl.raw)
        return "\n".join(lines)

    @property
    def all_commands(self) -> list[str]:
        """Returns header + all sub-commands as a flat list of stripped strings."""
        return [self.header.strip()] + [cl.text for cl in self.body]


@dataclass
class DeviceConfig:
    """All sections belonging to one device (hostname boundary)."""
    hostname: str
    sections: list[ConfigSection] = field(default_factory=list)
    source_os_hint: Optional[str] = None   # "ios", "iosxe", "nxos"


@dataclass
class ParseResult:
    """Top-level result returned by parse_config()."""
    sections: list[ConfigSection]          # flat list of all sections
    devices: list[DeviceConfig]            # sections grouped by device
    prose: list[str]                       # narrative text (ignored by translator)
    source_os: str                         # detected OS: "ios" | "iosxe" | "nxos" | "unknown"
    stats: dict                            # parse statistics


# ── OS detection ────────────────────────────────────────────────────────────

def detect_source_os(text: str) -> str:
    """
    Heuristically detect the source Cisco OS from the config text.

    Returns: "nxos" | "iosxe" | "ios" | "unknown"
    """
    t = text.lower()
    if "feature " in t or "nxos" in t or "nexus" in t or "nx-os" in t:
        return "nxos"
    if ("ios-xe" in t or "iosxe" in t or "catalyst" in t
            or re.search(r"version 17\.", t) or re.search(r"version 16\.", t)):
        return "iosxe"
    if re.search(r"version 1[0-5]\.", t):
        return "ios"
    return "unknown"


# ── Line classifier ─────────────────────────────────────────────────────────

def _is_cli_line(line: str) -> bool:
    """Returns True if the line looks like a Cisco CLI command."""
    stripped = line.strip()
    if not stripped or stripped.startswith("!"):
        return False
    first_word = stripped.split()[0].lower()
    return first_word in _ALL_CLI_KEYWORDS


def _is_section_header(line: str) -> bool:
    """Returns True if this un-indented line starts a new sub-mode section."""
    stripped = line.strip()
    if not stripped or stripped.startswith("!"):
        return False
    # Must not be indented
    if _INDENT_RE.match(line):
        return False
    first_word = stripped.split()[0].lower()
    return first_word in _SECTION_HEADERS


def _is_prose(line: str) -> bool:
    """Returns True if the line is plain English narrative (not CLI)."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("!"):
        return False
    return not _is_cli_line(stripped)


def _indent_level(line: str) -> int:
    """Returns the number of leading spaces."""
    return len(line) - len(line.lstrip(" \t"))


# ── Main parser ─────────────────────────────────────────────────────────────

def parse_config(raw_text: str) -> ParseResult:
    """
    Parse a raw Cisco configuration string into a ParseResult.

    Handles:
    - Hierarchical sections (interface, router, vlan, etc.)
    - Nested sub-modes (BGP address-family, crypto map, etc.)
    - NX-OS feature prerequisite lines
    - Section marker comments  ! --- LABEL ---
    - Mixed prose + CLI (e.g. from .docx design documents)
    - Multiple devices in a single file (split on hostname boundaries)
    """
    lines = raw_text.splitlines()

    sections: list[ConfigSection] = []
    prose_lines: list[str] = []
    current_section: Optional[ConfigSection] = None
    current_label: Optional[str] = None   # most recent ! --- label ---
    global_cmds: list[ConfigLine] = []
    current_hostname: str = "unknown"

    # Global section bucket (reset per device)
    def _flush_global():
        nonlocal global_cmds
        if global_cmds:
            sec = ConfigSection(
                section_type="global",
                header="! Global commands",
                body=global_cmds.copy(),
                label=None,
                device_name=current_hostname,
            )
            sections.append(sec)
            global_cmds = []

    def _close_section():
        nonlocal current_section
        if current_section is not None:
            sections.append(current_section)
            current_section = None

    for raw_line in lines:
        stripped = raw_line.strip()

        # ── Blank line ──────────────────────────────────────────────────
        if not stripped:
            if current_section and _indent_level(raw_line) == 0:
                # Blank at indent-0 closes the current section
                _close_section()
            continue

        # ── Bare ! delimiter ────────────────────────────────────────────
        if _BARE_BANG_RE.match(stripped):
            _close_section()
            continue

        # ── Section marker  ! --- LABEL --- ────────────────────────────
        m = _SECTION_MARKER_RE.match(stripped)
        if m:
            _close_section()
            current_label = m.group(1).strip()
            sections.append(ConfigSection(
                section_type="comment",
                header=stripped,
                label=current_label,
                device_name=current_hostname,
            ))
            continue

        # ── Indented sub-command (body of current section) ─────────────
        if _INDENT_RE.match(raw_line) and current_section is not None:
            indent = _indent_level(raw_line)
            current_section.body.append(ConfigLine(
                text=stripped,
                raw=raw_line,
                indent=indent,
            ))
            continue

        # ── Indented line with no open section (shouldn't happen, treat as global) ─
        if _INDENT_RE.match(raw_line):
            indent = _indent_level(raw_line)
            global_cmds.append(ConfigLine(text=stripped, raw=raw_line, indent=indent))
            continue

        # ── From here: un-indented (indent=0) non-blank non-comment line ──

        # NX-OS feature line
        if _NXOS_FEATURE_RE.match(stripped):
            _close_section()
            sections.append(ConfigSection(
                section_type="nxos-feature",
                header=stripped,
                label=current_label,
                device_name=current_hostname,
            ))
            continue

        # hostname — device boundary
        if stripped.lower().startswith("hostname "):
            _close_section()
            _flush_global()
            current_hostname = stripped.split(None, 1)[1].strip() if len(stripped.split()) > 1 else "unknown"
            global_cmds.append(ConfigLine(text=stripped, raw=raw_line, indent=0))
            continue

        # Single-line ip commands — treat as global, not section header
        if stripped.lower().startswith("ip "):
            prefix = " ".join(stripped.lower().split()[:3])  # first 3 words
            prefix2 = " ".join(stripped.lower().split()[:2])  # first 2 words
            if any(stripped.lower().startswith(s) for s in _IP_SINGLE_LINE):
                _close_section()
                global_cmds.append(ConfigLine(text=stripped, raw=raw_line, indent=0))
                continue

        # Section header (starts a new sub-mode)
        if _is_section_header(raw_line):
            _close_section()
            first_word = stripped.split()[0].lower()
            # Determine section_type
            if first_word == "interface":
                stype = "interface"
            elif first_word == "router":
                stype = "router"
            elif first_word == "vlan":
                stype = "vlan"
            elif first_word in ("ip",) and "dhcp pool" in stripped.lower():
                stype = "dhcp"
            elif first_word == "line":
                stype = "line"
            elif first_word in ("aaa", "tacacs", "radius"):
                stype = "aaa"
            elif first_word == "policy-map":
                stype = "policy-map"
            elif first_word == "class-map":
                stype = "class-map"
            elif first_word == "route-map":
                stype = "route-map"
            elif first_word in ("crypto",):
                stype = "crypto"
            else:
                stype = first_word
            current_section = ConfigSection(
                section_type=stype,
                header=stripped,
                label=current_label,
                device_name=current_hostname,
            )
            current_label = None   # consumed
            continue

        # Plain CLI global command (un-indented, known keyword, not a section header)
        if _is_cli_line(raw_line):
            _close_section()
            global_cmds.append(ConfigLine(text=stripped, raw=raw_line, indent=0))
            continue

        # Prose / narrative text
        if _is_prose(raw_line):
            _close_section()
            prose_lines.append(stripped)
            sections.append(ConfigSection(
                section_type="prose",
                header=stripped,
                device_name=current_hostname,
            ))
            continue

    # Flush anything remaining
    _close_section()
    _flush_global()

    # ── Group sections into DeviceConfig objects ────────────────────────
    devices = _group_into_devices(sections, current_hostname)

    # ── Stats ───────────────────────────────────────────────────────────
    type_counts: dict[str, int] = {}
    for s in sections:
        type_counts[s.section_type] = type_counts.get(s.section_type, 0) + 1

    stats = {
        "total_sections": len(sections),
        "devices": len(devices),
        "interfaces": type_counts.get("interface", 0),
        "vlans": type_counts.get("vlan", 0),
        "routers": type_counts.get("router", 0),
        "dhcp_pools": type_counts.get("dhcp", 0),
        "nxos_features": type_counts.get("nxos-feature", 0),
        "prose_blocks": type_counts.get("prose", 0),
        "global_commands": sum(
            len(s.body) for s in sections if s.section_type == "global"
        ),
    }

    return ParseResult(
        sections=[s for s in sections if s.section_type != "prose"],
        devices=devices,
        prose=prose_lines,
        source_os=detect_source_os(raw_text),
        stats=stats,
    )


def _group_into_devices(
    sections: list[ConfigSection], fallback_hostname: str
) -> list[DeviceConfig]:
    """Group parsed sections into DeviceConfig objects by hostname boundary."""
    devices: dict[str, DeviceConfig] = {}

    for sec in sections:
        if sec.section_type in ("prose", "comment"):
            continue
        hn = sec.device_name or fallback_hostname or "unknown"
        if hn not in devices:
            devices[hn] = DeviceConfig(hostname=hn)
        devices[hn].sections.append(sec)

    return list(devices.values())


# ── Topology extractor ──────────────────────────────────────────────────────

@dataclass
class TopologyNode:
    """Represents one device in the parsed topology."""
    hostname: str
    vlans: list[dict]           # [{"id": 10, "name": "DATA"}, ...]
    interfaces: list[dict]      # [{"name": "Gi1/0/1", "mode": "access", ...}]
    svis: list[dict]            # [{"vlan": 10, "ip": "10.10.10.1/24"}, ...]
    routing_enabled: bool
    dhcp_pools: list[dict]      # [{"name": "DATA_POOL", "network": "...", ...}]
    default_gateway: Optional[str]
    uplinks: list[str]          # interface names that are trunks
    access_ports: list[str]     # interface names that are access


def extract_topology(result: ParseResult) -> list[TopologyNode]:
    """
    Extract a simplified topology from a ParseResult for diagram generation.
    Returns one TopologyNode per device.
    """
    nodes: list[TopologyNode] = []

    for device in result.devices:
        vlans: list[dict] = []
        interfaces: list[dict] = []
        svis: list[dict] = []
        dhcp_pools: list[dict] = []
        routing_enabled = False
        default_gateway: Optional[str] = None
        uplinks: list[str] = []
        access_ports: list[str] = []

        for sec in device.sections:
            # VLANs
            if sec.section_type == "vlan":
                m = re.match(r"vlan\s+(\d+)", sec.header, re.IGNORECASE)
                if m:
                    vlan_id = int(m.group(1))
                    name = next(
                        (cl.text.replace("name", "").strip()
                         for cl in sec.body if cl.text.lower().startswith("name")),
                        f"VLAN{vlan_id}"
                    )
                    vlans.append({"id": vlan_id, "name": name})

            # Interfaces
            elif sec.section_type == "interface":
                iface: dict = {"name": sec.header.split(None, 1)[1] if len(sec.header.split()) > 1 else sec.header}
                for cl in sec.body:
                    t = cl.text.lower()
                    if "switchport mode access" in t:
                        iface["mode"] = "access"
                    elif "switchport mode trunk" in t:
                        iface["mode"] = "trunk"
                    elif "switchport access vlan" in t:
                        m2 = re.search(r"vlan\s+(\d+)", t)
                        if m2:
                            iface["access_vlan"] = int(m2.group(1))
                    elif "switchport voice vlan" in t:
                        m2 = re.search(r"vlan\s+(\d+)", t)
                        if m2:
                            iface["voice_vlan"] = int(m2.group(1))
                    elif "switchport trunk allowed vlan" in t:
                        m2 = re.search(r"vlan\s+([\d,\-]+)", t)
                        if m2:
                            iface["trunk_vlans"] = m2.group(1)
                    elif "ip address" in t:
                        parts = cl.text.split()
                        if len(parts) >= 4:
                            iface["ip"] = parts[2]
                            iface["mask"] = parts[3]
                    elif "description" in t:
                        iface["description"] = cl.text.split(None, 1)[1] if len(cl.text.split()) > 1 else ""
                    elif "portfast" in t:
                        iface["portfast"] = True
                    elif "bpduguard enable" in t:
                        iface["bpduguard"] = True
                interfaces.append(iface)
                # Classify uplink vs access
                if iface.get("mode") == "trunk":
                    uplinks.append(iface["name"])
                elif iface.get("mode") == "access":
                    access_ports.append(iface["name"])
                # SVI detection (Vlan<id> interface)
                if re.match(r"[Vv]lan\d+", iface["name"]) and iface.get("ip"):
                    svis.append({
                        "vlan": int(re.search(r"\d+", iface["name"]).group()),
                        "ip": iface["ip"],
                        "mask": iface.get("mask", ""),
                        "description": iface.get("description", ""),
                    })

            # DHCP pools
            elif sec.section_type == "dhcp":
                pool: dict = {"name": sec.header.split()[-1] if sec.header.split() else ""}
                for cl in sec.body:
                    t = cl.text.lower()
                    if t.startswith("network"):
                        parts = cl.text.split()
                        pool["network"] = parts[1] if len(parts) > 1 else ""
                        pool["mask"] = parts[2] if len(parts) > 2 else ""
                    elif "default-router" in t:
                        parts = cl.text.split()
                        pool["gateway"] = parts[1] if len(parts) > 1 else ""
                    elif "dns-server" in t:
                        parts = cl.text.split()
                        pool["dns"] = parts[1] if len(parts) > 1 else ""
                dhcp_pools.append(pool)

            # Global commands
            elif sec.section_type == "global":
                for cl in sec.body:
                    t = cl.text.lower()
                    if t.strip() == "ip routing":
                        routing_enabled = True
                    elif t.startswith("ip default-gateway"):
                        parts = cl.text.split()
                        default_gateway = parts[2] if len(parts) > 2 else None

        nodes.append(TopologyNode(
            hostname=device.hostname,
            vlans=vlans,
            interfaces=interfaces,
            svis=svis,
            routing_enabled=routing_enabled,
            dhcp_pools=dhcp_pools,
            default_gateway=default_gateway,
            uplinks=uplinks,
            access_ports=access_ports,
        ))

    return nodes


def render_ascii_topology(nodes: list[TopologyNode], label: str = "Input Config") -> str:
    """
    Render a simple ASCII topology diagram from a list of TopologyNodes.
    Heuristic: devices with routing_enabled=True are core; others are access.
    """
    lines = [f"{'═' * 60}", f"  TOPOLOGY — {label}", f"{'═' * 60}"]

    core_nodes = [n for n in nodes if n.routing_enabled]
    access_nodes = [n for n in nodes if not n.routing_enabled]

    for node in core_nodes:
        lines.append(f"\n[{node.hostname}]  (Core / L3)")
        for svi in node.svis:
            vlan_name = next((v["name"] for v in node.vlans if v["id"] == svi["vlan"]), f"VLAN{svi['vlan']}")
            lines.append(f"  Vlan{svi['vlan']} ({vlan_name}): {svi['ip']}/{_prefix(svi['mask'])}")
        for pool in node.dhcp_pools:
            lines.append(f"  DHCP: {pool['name']} → {pool.get('network', '?')}")
        for iface_name in node.uplinks:
            iface = next((i for i in node.interfaces if i["name"] == iface_name), {})
            vlans = iface.get("trunk_vlans", "all")
            lines.append(f"  {iface_name} → trunk VLANs {vlans}")
            lines.append(f"        │")
            lines.append(f"        │  trunk")
            lines.append(f"        │")

    for node in access_nodes:
        lines.append(f"[{node.hostname}]  (Access / L2)")
        for iface_name in node.uplinks:
            iface = next((i for i in node.interfaces if i["name"] == iface_name), {})
            lines.append(f"  {iface_name} ← uplink  (trunk VLANs {iface.get('trunk_vlans', '?')})")
        for iface_name in node.access_ports:
            iface = next((i for i in node.interfaces if i["name"] == iface_name), {})
            av = iface.get("access_vlan", "?")
            vv = iface.get("voice_vlan")
            desc = iface.get("description", "")
            pf = "portfast" if iface.get("portfast") else ""
            bg = "bpduguard" if iface.get("bpduguard") else ""
            flags = " + ".join(f for f in [pf, bg] if f)
            vlan_name = next((v["name"] for v in node.vlans if v["id"] == av), f"VLAN{av}")
            line = f"  {iface_name} → {desc or 'access port'}"
            line += f"\n    ├── access VLAN {av} ({vlan_name})"
            if vv:
                vv_name = next((v["name"] for v in node.vlans if v["id"] == vv), f"VLAN{vv}")
                line += f"\n    ├── voice VLAN {vv} ({vv_name})"
            if flags:
                line += f"\n    └── {flags}"
            lines.append(line)
        if node.default_gateway:
            lines.append(f"  default-gateway: {node.default_gateway}")
        lines.append(f"        │")
        lines.append(f"  [End devices]")

    lines.append(f"\n{'═' * 60}")
    return "\n".join(lines)


def extract_topology_from_exos(script: str) -> list[TopologyNode]:
    """
    Extract topology from a translated EXOS flat-syntax script.
    Parses lines like:
      configure snmp sysName "hostname"
      create vlan NAME tag ID
      configure vlan NAME ipaddress X.X.X.X/prefix
      enable ipforwarding [vlan NAME]
      configure iproute add default X
      create dhcp-server pool NAME
      configure dhcp-server pool NAME ipaddress X/prefix
      configure dhcp-server pool NAME default-router X
      configure vlan NAME add ports P [untagged|tagged]
    Returns one TopologyNode per detected device (split on sysName).
    """
    # Build per-device buckets, split on sysName lines
    devices_data: list[dict] = []
    current: dict = _empty_device_data("unknown")

    # First pass: collect all VLANs globally (shared across devices in same script)
    vlan_map: dict[int, str] = {}   # id → name
    for line in script.splitlines():
        s = line.strip()
        m = re.match(r"create\s+vlan\s+(\S+)\s+tag\s+(\d+)", s, re.IGNORECASE)
        if m:
            vlan_map[int(m.group(2))] = m.group(1)

    # Second pass: build per-device nodes
    dhcp_pool_context: str = ""
    for line in script.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue

        # Device boundary: sysName
        m = re.match(r'configure\s+snmp\s+sysName\s+"?([^"]+)"?', s, re.IGNORECASE)
        if m:
            hostname = m.group(1).strip()
            # If current device has content beyond "unknown", save it
            if current["hostname"] != "unknown" or current["svis"] or current["routing_enabled"]:
                devices_data.append(current)
            current = _empty_device_data(hostname)
            # Attach global vlan_map
            current["vlans"] = [{"id": vid, "name": vname} for vid, vname in vlan_map.items()]
            continue

        # SVI: configure vlan NAME ipaddress X.X.X.X/prefix
        m = re.match(r"configure\s+vlan\s+(\S+)\s+ipaddress\s+([\d\.]+)/(\d+)", s, re.IGNORECASE)
        if m:
            vname, ip, prefix = m.group(1), m.group(2), m.group(3)
            vid = next((vid for vid, n in vlan_map.items() if n == vname), 0)
            current["svis"].append({"vlan": vid, "vlan_name": vname, "ip": f"{ip}/{prefix}", "mask": ""})
            continue

        # IP forwarding (global or per-vlan)
        if re.match(r"enable\s+ipforwarding\b", s, re.IGNORECASE):
            current["routing_enabled"] = True
            continue

        # Default gateway
        m = re.match(r"configure\s+iproute\s+add\s+default\s+([\d\.]+)", s, re.IGNORECASE)
        if m:
            current["default_gateway"] = m.group(1)
            continue

        # DHCP pool start
        m = re.match(r"create\s+dhcp-server\s+pool\s+(\S+)", s, re.IGNORECASE)
        if m:
            dhcp_pool_context = m.group(1)
            current["dhcp_pools"].append({"name": dhcp_pool_context, "network": "", "gateway": "", "dns": ""})
            continue

        # DHCP pool network
        m = re.match(r"configure\s+dhcp-server\s+pool\s+(\S+)\s+ipaddress\s+([\d\.]+)/(\d+)", s, re.IGNORECASE)
        if m:
            pname, net, prefix = m.group(1), m.group(2), m.group(3)
            for p in current["dhcp_pools"]:
                if p["name"] == pname:
                    p["network"] = net
                    break
            continue

        # DHCP default-router
        m = re.match(r"configure\s+dhcp-server\s+pool\s+(\S+)\s+default-router\s+([\d\.]+)", s, re.IGNORECASE)
        if m:
            pname, gw = m.group(1), m.group(2)
            for p in current["dhcp_pools"]:
                if p["name"] == pname:
                    p["gateway"] = gw
                    break
            continue

        # Port untagged (access)
        m = re.match(r"configure\s+vlan\s+(\S+)\s+add\s+ports?\s+(\S+)\s+untagged", s, re.IGNORECASE)
        if m:
            vname, port = m.group(1), m.group(2)
            vid = next((vid for vid, n in vlan_map.items() if n == vname), 0)
            iface = _get_or_create_iface(current["interfaces"], port)
            iface["mode"] = "access"
            iface["access_vlan"] = vid
            iface["access_vlan_name"] = vname
            if port not in current["access_ports"]:
                current["access_ports"].append(port)
            continue

        # Port tagged (trunk)
        m = re.match(r"configure\s+vlan\s+(\S+)\s+add\s+ports?\s+(\S+)\s+tagged", s, re.IGNORECASE)
        if m:
            vname, port = m.group(1), m.group(2)
            iface = _get_or_create_iface(current["interfaces"], port)
            iface["mode"] = "trunk"
            tv = iface.get("trunk_vlans_list", [])
            tv.append(vname)
            iface["trunk_vlans_list"] = tv
            iface["trunk_vlans"] = ",".join(tv)
            if port not in current["uplinks"]:
                current["uplinks"].append(port)
                # remove from access_ports if it was added there
                current["access_ports"] = [p for p in current["access_ports"] if p != port]
            continue

    # Save last device
    devices_data.append(current)

    # Build TopologyNodes
    nodes: list[TopologyNode] = []
    for d in devices_data:
        # Ensure vlans list is populated
        if not d["vlans"]:
            d["vlans"] = [{"id": vid, "name": vname} for vid, vname in vlan_map.items()]
        # Convert SVI ip/mask for render_ascii_topology compatibility
        for svi in d["svis"]:
            if "/" in svi["ip"]:
                parts = svi["ip"].split("/")
                svi["ip"] = parts[0]
                svi["mask"] = f"/{parts[1]}"
        nodes.append(TopologyNode(
            hostname=d["hostname"],
            vlans=d["vlans"],
            interfaces=d["interfaces"],
            svis=d["svis"],
            routing_enabled=d["routing_enabled"],
            dhcp_pools=d["dhcp_pools"],
            default_gateway=d["default_gateway"],
            uplinks=d["uplinks"],
            access_ports=d["access_ports"],
        ))
    return nodes


def _empty_device_data(hostname: str) -> dict:
    return {
        "hostname": hostname,
        "vlans": [],
        "interfaces": [],
        "svis": [],
        "routing_enabled": False,
        "dhcp_pools": [],
        "default_gateway": None,
        "uplinks": [],
        "access_ports": [],
    }


def _get_or_create_iface(interfaces: list, port: str) -> dict:
    for i in interfaces:
        if i["name"] == port:
            return i
    iface = {"name": port}
    interfaces.append(iface)
    return iface


def _prefix(mask: str) -> str:
    """Convert dotted-decimal subnet mask to prefix length."""
    try:
        return str(sum(bin(int(o)).count("1") for o in mask.split(".")))
    except Exception:
        return mask
