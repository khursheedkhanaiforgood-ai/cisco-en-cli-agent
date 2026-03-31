"""
Thematic seed data extracted from Google NotebookLLM session (March 31, 2026).
Each entry maps to a functional theme within one of the 9 bins.
Source: Deep-link thematic extraction across VOSS 8.9, EXOS 22.7, IOS-XE 17.x, NX-OS 10.x, SLX-OS.

Run: python -m src.database.seed_themes
"""
import logging
import sys

logger = logging.getLogger(__name__)

# ── Sentinel for "no equivalent on this platform" ────────────────────────────
NE = "No equivalent on this platform"

# ── All 9 volumes, all themes, all 6 OS columns ──────────────────────────────
THEME_DATA = [

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 1: [ONBOARD] Onboarding & Provisioning
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[ONBOARD]", "theme": "System Sanitization & Day-0 Reset",
        "functional_intent": "System Sanitization — Factory reset all configuration to out-of-box state",
        "cisco_ios":     "write erase",
        "cisco_iosxe":   "factory-reset all | write erase",
        "cisco_nxos":    "write erase | clear nvram",
        "extreme_exos":  "unconfigure switch all | unconfigure switch erase all | unconfigure switch erase nvram",
        "extreme_voss":  "boot config flags factorydefaults reset-all-files | unconfigure switch",
        "extreme_slxos": "clear config all | bmc factory reset",
        "negation_cisco": "", "negation_en": "",
        "notes": "Theme: System Sanitization & Day-0 Reset. IOS-XE: factory-reset all (Cat 9k pg 2214). NX-OS: write erase + clear nvram (Index pg 52). EXOS pg 17,246. VOSS pg 342-344. SLX-OS pg 18.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol1-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[ONBOARD]", "theme": "Automated Onboarding (ZTP/PnP/POAP)",
        "functional_intent": "Automated Onboarding — Zero Touch Provisioning enable and status",
        "cisco_ios":     NE,
        "cisco_iosxe":   "pnp profile | feature pnp",
        "cisco_nxos":    "system poap | feature poap | boot poap enable",
        "extreme_exos":  "show auto-provision | disable auto-provision | restart process ztpstack",
        "extreme_voss":  "auto-sense enable | auto-sense onboarding i-sid <id> | show application auto-provision",
        "extreme_slxos": "show ztp status",
        "negation_cisco": "no feature pnp", "negation_en": "disable auto-provision",
        "notes": "Theme: Automated Onboarding (ZTP/PnP/POAP). IOS-XE PnP. NX-OS POAP (Index pg 4908-4909). EXOS ZTP pg 19,73. VOSS ZTF pg 16,75. SLX-OS ZTP Index pg 230. Classic IOS has no ZTP.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol1-Theme2", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[ONBOARD]", "theme": "Universal Persona & OS Transition",
        "functional_intent": "Universal Hardware — Toggle between Switch Engine (EXOS) and Fabric Engine (VOSS) OS",
        "cisco_ios":     NE,
        "cisco_iosxe":   NE,
        "cisco_nxos":    NE,
        "extreme_exos":  "download image <voss-image-url> | (Bootrom spacebar menu: Change switch OS to Fabric Engine)",
        "extreme_voss":  "boot config flags factorydefaults zero-touch-config-only | software add <file> | software activate <version>",
        "extreme_slxos": NE,
        "negation_cisco": "", "negation_en": "software revert",
        "notes": "Theme: Universal Persona & OS Transition. Extreme-specific feature for Universal Hardware that can run either EXOS or VOSS. EXOS pg 13-14. VOSS pg 628,632. No Cisco equivalent.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol1-Theme3", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[ONBOARD]", "theme": "Initial Identity & Prompt Configuration",
        "functional_intent": "Initial Identity — Set system hostname and administrative prompt",
        "cisco_ios":     "hostname <name>",
        "cisco_iosxe":   "hostname <name>",
        "cisco_nxos":    "hostname <name>",
        "extreme_exos":  "configure snmp sysname <name>",
        "extreme_voss":  "prompt <name> | sys name <name>",
        "extreme_slxos": "system-name <name>",
        "negation_cisco": "no hostname", "negation_en": "configure snmp sysname \"\" | no prompt",
        "notes": "Theme: Initial Identity & Prompt. IOS-XE/NX-OS pg 2221. EXOS pg 248. VOSS pg 651. EXOS sets hostname via SNMP sysName; VOSS uses 'prompt' for CLI prompt and 'sys name' for SNMP sysName.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol1-Theme4", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[ONBOARD]", "theme": "Configuration Persistence & Boot Variables",
        "functional_intent": "Config Persistence — Save running configuration and set next-boot image",
        "cisco_ios":     "copy running-config startup-config | boot system flash:<file>",
        "cisco_iosxe":   "copy running-config startup-config | boot system flash:<file>",
        "cisco_nxos":    "copy running-config startup-config",
        "extreme_exos":  "save | use configuration [primary | secondary | <filename>]",
        "extreme_voss":  "save config | boot config choice primary config-file <file>",
        "extreme_slxos": "copy running-config startup-config",
        "negation_cisco": "", "negation_en": "",
        "notes": "Theme: Config Persistence & Boot Variables. IOS-XE/NX-OS pg 2420. EXOS pg 14-15. VOSS pg 16,896. EXOS 'save' writes primary.cfg; 'use configuration' selects boot config.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol1-Theme5", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[ONBOARD]", "theme": "Software Acquisition & Image Management",
        "functional_intent": "Software Upgrade — Download image, activate, and commit firmware",
        "cisco_ios":     "copy tftp flash:<file>",
        "cisco_iosxe":   "copy tftp flash:<file> | install add file <file> activate reloadfast commit",
        "cisco_nxos":    "copy tftp bootflash:<file>",
        "extreme_exos":  "download image <url> | use image [primary | secondary]",
        "extreme_voss":  "software add <file> | software activate <version> | software commit",
        "extreme_slxos": "firmware download | firmware activate | firmware commit",
        "negation_cisco": "install rollback to", "negation_en": "software revert",
        "notes": "Theme: Software Acquisition & Image Management. IOS-XE pg 2237. EXOS pg 11,262. VOSS pg 310,832. SLX-OS pg 229. VOSS uses 3-step: add > activate > commit (same as SLX). IOS-XE 'install' method preferred over 'copy'.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol1-Theme6", "confidence": 1.0, "is_verified": True,
    },

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 2: [SEC-ID] Identity, AAA & Policy Auth
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[SEC-ID]", "theme": "AAA Framework & Server Reachability",
        "functional_intent": "AAA Framework — Enable AAA and configure RADIUS/TACACS+ server group",
        "cisco_ios":     "aaa new-model | aaa authentication login default group radius local | aaa group server radius <name>",
        "cisco_iosxe":   "aaa new-model | aaa authentication login default group radius local | aaa group server radius <name>",
        "cisco_nxos":    "aaa new-model | aaa authentication login default group radius | aaa group server radius <name>",
        "extreme_exos":  "enable radius | configure radius <id> server <ip> client-ip <mgmt-ip> secret <key> vr VR-Mgmt",
        "extreme_voss":  "radius-server enable | radius-server host <ip> key <key>",
        "extreme_slxos": "aaa authentication | aaa accounting",
        "negation_cisco": "no aaa new-model", "negation_en": "disable radius | no radius-server host",
        "notes": "Theme: AAA Framework & Server Reachability. EXOS uses flat radius config; VOSS uses radius-server commands. Cisco requires 'aaa new-model' to activate AAA globally.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol2-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[SEC-ID]", "theme": "Port Authentication Protocols (802.1X/MAB)",
        "functional_intent": "Port Authentication — Configure 802.1X dot1x and MAB on access ports",
        "cisco_ios":     "dot1x system-auth-control | interface <int> | authentication host-mode multi-auth | dot1x pae authenticator",
        "cisco_iosxe":   "dot1x system-auth-control | interface <int> | authentication host-mode multi-auth | dot1x pae authenticator",
        "cisco_nxos":    "feature dot1x | dot1x system-auth-control | interface <int> | dot1x timeout tx-period <n>",
        "extreme_exos":  "enable netlogin dot1x | configure netlogin dot1x timers tx-period <n> | configure netlogin add mac-list ff:ff:ff:ff:ff:ff",
        "extreme_voss":  "eapol status auto | eapol port <slot/port> status auto | eapol multihost-session-stats enable",
        "extreme_slxos": NE,
        "negation_cisco": "no dot1x system-auth-control", "negation_en": "disable netlogin dot1x | no eapol status",
        "notes": "Theme: 802.1X/MAB. NX-OS requires 'feature dot1x'. EXOS uses 'netlogin' for 802.1X. VOSS uses EAPOL commands. SLX-OS is a data center switch; 802.1X not typically configured.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol2-Theme2", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[SEC-ID]", "theme": "Macro-Security Policy (TrustSec/ONEPolicy)",
        "functional_intent": "Macro-Security Policy — TrustSec SGT tagging and Extreme ONEPolicy role-based access",
        "cisco_ios":     NE,
        "cisco_iosxe":   "cts role-based sgt-map <ip> sgt <id> | cts role-based permissions from <sgt> to <sgt> list <acl>",
        "cisco_nxos":    "feature cts | cts role-based sgt-map <ip> sgt <id>",
        "extreme_exos":  "configure identity-policy <name> | configure identity-management role <name> | configure policy profile <id> pvid-status enable pvid <vlan>",
        "extreme_voss":  "fail-open-isid <isid> | i-sid <id> | application onepolicy enable",
        "extreme_slxos": NE,
        "negation_cisco": "no cts role-based sgt-map", "negation_en": "unconfigure identity-policy | no application onepolicy",
        "notes": "Theme: Macro-Security Policy. Cisco TrustSec SGT vs Extreme ONEPolicy (EXOS) and I-SID-based policy (VOSS). VOSS 'fail-open-isid' provides continuity mode when RADIUS unreachable. SLX-OS has no equivalent (DC switch).",
        "source_ref": "NB-Session-2026", "page_ref": "Vol2-Theme3", "confidence": 1.0, "is_verified": True,
    },

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 3: [SYS-INFO] System Health & Inventory
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[SYS-INFO]", "theme": "Hardware Inventory & UDI Data",
        "functional_intent": "Hardware Inventory — Show chassis, module, and UDI/serial number data",
        "cisco_ios":     "show inventory | show version",
        "cisco_iosxe":   "show inventory | show inventory raw | show version",
        "cisco_nxos":    "show inventory | show inventory raw | show version",
        "extreme_exos":  "show switch | show slot <id> detail | show version",
        "extreme_voss":  "show sys-info | show hardware | show version",
        "extreme_slxos": "show inventory | show version",
        "negation_cisco": "", "negation_en": "",
        "notes": "Theme: Hardware Inventory & UDI. IOS-XE 'show inventory raw' includes UDI. EXOS 'show slot detail' for module info. VOSS 'show hardware' for chassis data. All platforms support 'show version'.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol3-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[SYS-INFO]", "theme": "CPU/Memory & Process Throttling",
        "functional_intent": "CPU and Memory — Show utilization and running process resource consumption",
        "cisco_ios":     "show processes cpu | show processes memory",
        "cisco_iosxe":   "show processes cpu platform | show processes cpu | show processes memory platform",
        "cisco_nxos":    "show processes cpu | show processes memory | show memory",
        "extreme_exos":  "show cpu-monitoring | show memory | show process",
        "extreme_voss":  "show process | show storage-usage | show memory-utilization",
        "extreme_slxos": "show processes cpu | show memory",
        "negation_cisco": "", "negation_en": "",
        "notes": "Theme: CPU/Memory. IOS-XE has both process-level and platform-level views. EXOS 'show cpu-monitoring' shows per-process CPU. VOSS 'show storage-usage' tracks flash utilization.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol3-Theme2", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[SYS-INFO]", "theme": "Environmental States (Power/Temp)",
        "functional_intent": "Environmental Health — Show power supply, temperature, and fan status",
        "cisco_ios":     "show environment | show environment power | show environment temperature",
        "cisco_iosxe":   "show env xps | show power detail | show environment all",
        "cisco_nxos":    "show hardware power | show environment | show environment power",
        "extreme_exos":  "show power | show temperature | show fan",
        "extreme_voss":  "show power supply | show alarm database | show sys-info",
        "extreme_slxos": "show environment | show power",
        "negation_cisco": "", "negation_en": "",
        "notes": "Theme: Environmental States. VOSS 'show alarm database' surfaces all hardware alarms including thermal. EXOS has discrete 'show power' and 'show temperature' commands.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol3-Theme3", "confidence": 1.0, "is_verified": True,
    },

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 4: [IF-PHYS] Physical Interface & Port Access
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[IF-PHYS]", "theme": "Logical Port Lifecycle (Speed/Duplex/Neg)",
        "functional_intent": "Port Speed and Duplex — Configure speed, duplex, and auto-negotiation on physical ports",
        "cisco_ios":     "interface <int> | speed [10|100|1000|auto] | duplex [full|half|auto] | negotiation auto",
        "cisco_iosxe":   "interface <int> | speed [10|100|1000|auto] | duplex [full|half|auto] | negotiation auto",
        "cisco_nxos":    "interface <int> | speed [100|1000|10000|auto] | duplex [full|auto]",
        "extreme_exos":  "configure ports <port> speed [10|100|1000|auto] duplex [full|half|auto]",
        "extreme_voss":  "interface gigabitEthernet <slot/port> | speed [10|100|1000|auto] | duplex [full|half|auto]",
        "extreme_slxos": "interface ethernet <slot/port> | speed [1000|10000|40000|auto]",
        "negation_cisco": "no speed | no duplex", "negation_en": "configure ports <port> speed auto duplex auto",
        "notes": "Theme: Port Speed/Duplex. EXOS flat verb-noun: configure ports <id> speed <val>. VOSS uses interface sub-mode like Cisco. NX-OS negotiation auto is default. SLX-OS is DC-focused (higher speeds).",
        "source_ref": "NB-Session-2026", "page_ref": "Vol4-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[IF-PHYS]", "theme": "Port Breakout & Hardware Profiles",
        "functional_intent": "Port Breakout — Split high-speed ports into multiple lower-speed sub-ports",
        "cisco_ios":     NE,
        "cisco_iosxe":   "interface breakout module <slot> port <range> map <40G-4x10G|100G-4x25G>",
        "cisco_nxos":    "interface breakout-profile | interface breakout module <id> port <range> map 10g-4x",
        "extreme_exos":  "configure ports <port> speed [40G|100G] | configure ports <port> channelize enable",
        "extreme_voss":  "interface gigabitEthernet <slot/port/sub-port> | channelize enable",
        "extreme_slxos": "breakout mode 4x10g | interface ethernet <slot/port:sub>",
        "negation_cisco": "no interface breakout module", "negation_en": "unconfigure ports channelize | no channelize",
        "notes": "Theme: Port Breakout. EXOS/VOSS use 'channelize'. SLX-OS uses 'breakout mode'. Classic IOS does not support port breakout (fixed configuration switches). IOS-XE on modular platforms only.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol4-Theme2", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[IF-PHYS]", "theme": "Administrative Port State",
        "functional_intent": "Port Administrative State — Enable or disable a physical port",
        "cisco_ios":     "interface <int> | no shutdown",
        "cisco_iosxe":   "interface <int> | no shutdown",
        "cisco_nxos":    "interface <int> | no shutdown",
        "extreme_exos":  "enable ports <port-list>",
        "extreme_voss":  "interface gigabitEthernet <slot/port> | no shutdown",
        "extreme_slxos": "interface ethernet <slot/port> | no shutdown",
        "negation_cisco": "interface <int> | shutdown", "negation_en": "disable ports <port-list> | interface <int> | shutdown",
        "notes": "Theme: Administrative Port State. EXOS flat command: enable/disable ports <list>. All others use interface sub-mode shutdown/no shutdown. EXOS ports are enabled by default.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol4-Theme3", "confidence": 1.0, "is_verified": True,
    },

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 5: [L2-SEG] VLANs & Layer 2 Segmentation
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[L2-SEG]", "theme": "VLAN Lifecycle & Naming",
        "functional_intent": "VLAN Lifecycle — Create VLAN, assign name, and verify",
        "cisco_ios":     "vlan <id> | name <text>",
        "cisco_iosxe":   "vlan <id> | name <text>",
        "cisco_nxos":    "vlan <id> | name <text>",
        "extreme_exos":  "create vlan <name> tag <id> | configure vlan <name> tag <id>",
        "extreme_voss":  "vlan create <id> name <text> type port | vlan name <id> <text>",
        "extreme_slxos": "vlan <id> | name <text>",
        "negation_cisco": "no vlan <id>", "negation_en": "delete vlan <name> | vlan delete <id>",
        "notes": "Theme: VLAN Lifecycle. EXOS creates VLANs by name first, then assigns tag (ID). VOSS requires 'type port' for access VLANs vs 'type spbm-bvlan' for Fabric Connect. NX-OS: VLANs in vlan database mode.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol5-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[L2-SEG]", "theme": "Trunking & Port Tagging",
        "functional_intent": "VLAN Trunking — Configure 802.1Q trunk and assign allowed VLANs",
        "cisco_ios":     "interface <int> | switchport mode trunk | switchport trunk allowed vlan <id-list>",
        "cisco_iosxe":   "interface <int> | switchport mode trunk | switchport trunk allowed vlan <id-list>",
        "cisco_nxos":    "interface <int> | switchport mode trunk | switchport trunk allowed vlan <id-list>",
        "extreme_exos":  "configure vlan <name> add ports <port-list> tagged",
        "extreme_voss":  "interface gigabitEthernet <slot/port> | encapsulation dot1q | vlan members add <id> <port>",
        "extreme_slxos": "interface ethernet <slot/port> | switchport mode trunk | switchport trunk allowed vlan <id-list>",
        "negation_cisco": "interface <int> | no switchport trunk allowed vlan <id>", "negation_en": "configure vlan <name> delete ports <port-list> tagged",
        "notes": "Theme: Trunking. EXOS: VLANs own ports, not the other way around. Multiple VLANs configured separately per port. VOSS: encapsulation dot1q for tagged mode. SLX-OS: similar to Cisco modal syntax.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol5-Theme2", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[L2-SEG]", "theme": "Spanning Tree & Loop Prevention",
        "functional_intent": "Spanning Tree — Configure STP mode, priority, and loop prevention",
        "cisco_ios":     "spanning-tree mode rapid-pvst | spanning-tree vlan <id> priority <0-61440>",
        "cisco_iosxe":   "spanning-tree mode rapid-pvst | spanning-tree vlan <id> priority <0-61440> | spanning-tree portfast default",
        "cisco_nxos":    "spanning-tree mode rapid-pvst | spanning-tree vlan <id> priority <0-61440>",
        "extreme_exos":  "enable stpd <domain> | configure stpd <domain> mode dot1w | enable stpd <domain> auto-bind vlan <name> | configure elrp-client",
        "extreme_voss":  "vlan create <id> type port-mstprstp <instance> | spanning-tree mstp enable | spanning-tree mstp priority <0-61440>",
        "extreme_slxos": "spanning-tree mode rstp | spanning-tree priority <0-61440>",
        "negation_cisco": "no spanning-tree vlan <id>", "negation_en": "disable stpd <domain> | no spanning-tree",
        "notes": "Theme: Spanning Tree. EXOS uses separate STP domains (stpd); 'auto-bind vlan' links VLANs to STP domain. VOSS integrates STP into VLAN type. EXOS ELRP = Extreme Loop Recovery Protocol (alternative to STP).",
        "source_ref": "NB-Session-2026", "page_ref": "Vol5-Theme3", "confidence": 1.0, "is_verified": True,
    },

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 6: [FAB-SDN] Fabric Connect & SD-Access
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[FAB-SDN]", "theme": "Control Plane Discovery & Adjacency",
        "functional_intent": "Fabric Control Plane — Configure IS-IS/LISP underlay and adjacency discovery",
        "cisco_ios":     NE,
        "cisco_iosxe":   "router lisp | locator-table default | map-server <ip> | map-resolver <ip>",
        "cisco_nxos":    "feature nv overlay | feature vn-segment-vlan-based | router bgp <as>",
        "extreme_exos":  "configure ospf add vlan <name> area <id> | (Fabric Attach via LLDP auto-discovery)",
        "extreme_voss":  "router isis | spbm <id> | manual-area <area-id> | sys-name <name>",
        "extreme_slxos": "router bgp <as> | router ospf <id>",
        "negation_cisco": "no router lisp", "negation_en": "no router isis | no spbm",
        "notes": "Theme: Control Plane. Cisco SD-Access uses LISP for control plane. VOSS Fabric Connect uses IS-IS/SPBM. NX-OS uses BGP EVPN. EXOS does not have a native fabric underlay; uses Fabric Attach to connect to VOSS seed.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol6-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[FAB-SDN]", "theme": "Data Plane Encapsulation",
        "functional_intent": "Fabric Data Plane — Configure VXLAN NVE or SPBM B-VLAN encapsulation",
        "cisco_ios":     NE,
        "cisco_iosxe":   "interface nve1 | source-interface loopback0 | member vni <id> | vni <id> l2",
        "cisco_nxos":    "feature nv overlay | interface nve1 | member vni <id> associate-vrf",
        "extreme_exos":  "(No native fabric encapsulation; uses Fabric Attach to VOSS for SPBM extension)",
        "extreme_voss":  "vlan create <id> type spbm-bvlan | i-sid <isid> | backbone-vlan <bvlan-id>",
        "extreme_slxos": "overlay-gateway <name> | type layer2-extension | vni <id> | map vlan <id> vni <id>",
        "negation_cisco": "no interface nve1", "negation_en": "no i-sid | no vlan spbm-bvlan",
        "notes": "Theme: Data Plane Encapsulation. Cisco uses VXLAN (VNI). VOSS uses SPBM with B-VLAN/I-SID (IEEE 802.1ah PBB). SLX-OS supports VXLAN like Cisco. EXOS delegates fabric to VOSS via Fabric Attach.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol6-Theme2", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[FAB-SDN]", "theme": "Service Mapping (VNI to I-SID)",
        "functional_intent": "Fabric Service Mapping — Map customer VLANs to fabric identifiers (VNI or I-SID)",
        "cisco_ios":     NE,
        "cisco_iosxe":   "eid-table vrf <name> | database-mapping <prefix> <locator> | map-cache <prefix>",
        "cisco_nxos":    "vlan <id> | vn-segment <vni> | evpn | vni <id> l2 | rd auto | route-target both auto",
        "extreme_exos":  "configure vlan <name> add ports <port> | (auto-sense assigns I-SID via Fabric Attach to VOSS)",
        "extreme_voss":  "vlan i-sid <vlan-id> <isid> | auto-sense enable | auto-sense onboarding i-sid <isid>",
        "extreme_slxos": "overlay-gateway <name> | map vlan <id> vni <id>",
        "negation_cisco": "no database-mapping | no vn-segment", "negation_en": "no vlan i-sid | unconfigure vlan i-sid",
        "notes": "Theme: Service Mapping. Cisco: LISP EID-table (SD-Access) or BGP EVPN VNI mapping (NX-OS). VOSS: vlan i-sid maps L2 segment to SPBM service. I-SID is the Extreme macro-segmentation identifier (analogous to VNI). Auto-sense automates I-SID assignment.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol6-Theme3", "confidence": 1.0, "is_verified": True,
    },

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 7: [L3-VIRT] L3 Routing & Virtual Routing
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[L3-VIRT]", "theme": "Virtual Routing Instances (VRF)",
        "functional_intent": "VRF — Create and configure virtual routing instance for traffic isolation",
        "cisco_ios":     "ip vrf <name> | rd <rd-value> | route-target export <rt> | route-target import <rt>",
        "cisco_iosxe":   "vrf definition <name> | address-family ipv4 | rd <rd-value> | route-target export <rt>",
        "cisco_nxos":    "vrf context <name> | rd <rd-value> | address-family ipv4 unicast",
        "extreme_exos":  "create virtual-router <name> | configure vr <name> add ports <port-list>",
        "extreme_voss":  "router vrf <name> | ip vrf <name> | interface vlan <id> | vrf <name>",
        "extreme_slxos": "vrf <name> | rd <rd-value> | address-family ipv4 unicast | route-target export <rt>",
        "negation_cisco": "no vrf definition <name>", "negation_en": "delete virtual-router <name> | no router vrf <name>",
        "notes": "Theme: VRF. EXOS uses 'virtual-router' (VR) with port assignment. VOSS uses 'ip vrf' similar to IOS but within routing context. NX-OS uses 'vrf context'. SLX-OS matches IOS-XE syntax closely.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol7-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[L3-VIRT]", "theme": "Dynamic Routing (OSPF/BGP)",
        "functional_intent": "Dynamic Routing — Configure OSPF and BGP routing protocols",
        "cisco_ios":     "router ospf <id> | network <net> <mask> area <id> | router bgp <as> | neighbor <ip> remote-as <as>",
        "cisco_iosxe":   "router ospf <id> | network <net> <mask> area <id> | router bgp <as> | neighbor <ip> remote-as <as>",
        "cisco_nxos":    "feature ospf | router ospf <tag> | feature bgp | router bgp <as> | neighbor <ip> remote-as <as>",
        "extreme_exos":  "configure ospf add vlan <name> area <id> | configure bgp as-number <as> | create bgp neighbor <ip> remote-as <as>",
        "extreme_voss":  "router ospf enable | area <id> enable | router bgp enable | neighbor <ip> remote-as <as>",
        "extreme_slxos": "router ospf <id> | area <id> | router bgp | neighbor <ip> remote-as <as>",
        "negation_cisco": "no router ospf <id> | no router bgp <as>", "negation_en": "no router ospf | configure ospf delete vlan | no router bgp",
        "notes": "Theme: OSPF/BGP. NX-OS requires 'feature ospf' and 'feature bgp' first. EXOS OSPF is VLAN-based (not interface-based like Cisco). VOSS enables OSPF/BGP globally then configures per-interface via area. EXOS uses create/configure syntax for BGP neighbors.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol7-Theme2", "confidence": 1.0, "is_verified": True,
    },

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 8: [DIAG-LOG] Troubleshooting & Diagnostics
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[DIAG-LOG]", "theme": "Basic Connectivity & Path Tracing",
        "functional_intent": "Connectivity Test — Ping, traceroute, and SPBM fabric L2 path trace",
        "cisco_ios":     "ping <ip> | traceroute <ip>",
        "cisco_iosxe":   "ping <ip> | traceroute <ip> | ping vrf <vrf> <ip>",
        "cisco_nxos":    "ping <ip> | traceroute <ip> | ping <ip> vrf <vrf>",
        "extreme_exos":  "ping <ip> | traceroute <ip> | ping vr <vr-name> <ip>",
        "extreme_voss":  "ping <ip> | traceroute <ip> | l2tracetree i-sid <isid> | l2trace <mac>",
        "extreme_slxos": "ping <ip> | traceroute <ip>",
        "negation_cisco": "", "negation_en": "",
        "notes": "Theme: Basic Connectivity. VOSS l2tracetree is unique — traces SPBM fabric L2 path by I-SID; no Cisco equivalent. VOSS l2trace traces by MAC address. EXOS/IOS-XE/NX-OS support VRF-aware ping.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol8-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[DIAG-LOG]", "theme": "Log Persistence & Event History",
        "functional_intent": "Log History — Show system log, event history, and persistent logging",
        "cisco_ios":     "show logging | show logging history",
        "cisco_iosxe":   "show logging | show platform software audit all | show logging last 100",
        "cisco_nxos":    "show logging log | show system internal <module> event-history | show logging last <n>",
        "extreme_exos":  "show log | show log messages | debug hal <command>",
        "extreme_voss":  "show logging | show logging file | trace level <n>",
        "extreme_slxos": "show logging | show logging raslog",
        "negation_cisco": "clear logging", "negation_en": "clear log | clear logging",
        "notes": "Theme: Log Persistence. NX-OS 'show system internal event-history' provides per-module event traces. EXOS 'debug hal' for hardware abstraction layer events. VOSS 'trace level' controls verbosity. SLX-OS uses raslog (RAS = Reliability, Availability, Serviceability).",
        "source_ref": "NB-Session-2026", "page_ref": "Vol8-Theme2", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[DIAG-LOG]", "theme": "Real-time Packet Capture",
        "functional_intent": "Packet Capture — Capture and analyze packets on an interface in real time",
        "cisco_ios":     "debug ip packet | ip access-list extended <acl>",
        "cisco_iosxe":   "monitor capture <name> interface <int> both | monitor capture <name> start | show monitor capture <name> buffer brief",
        "cisco_nxos":    "ethanalyzer local interface inband | ethanalyzer local interface inband capture-filter <filter>",
        "extreme_exos":  "show ports <port> statistics | debug packet capture",
        "extreme_voss":  "packet capture | packet capture interface <slot/port>",
        "extreme_slxos": "monitor session <n> | source interface <int> | destination interface <int>",
        "negation_cisco": "no monitor capture <name> | monitor capture <name> stop", "negation_en": "no packet capture",
        "notes": "Theme: Packet Capture. IOS-XE Embedded Packet Capture (EPC) is most capable. NX-OS ethanalyzer is tcpdump-based. EXOS 'debug packet capture' writes to file. VOSS has basic packet capture. SLX-OS uses SPAN (monitor session).",
        "source_ref": "NB-Session-2026", "page_ref": "Vol8-Theme3", "confidence": 1.0, "is_verified": True,
    },

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME 9: [MGMT-OPS] Operations & Session Management
    # ─────────────────────────────────────────────────────────────────────────
    {
        "tag": "[MGMT-OPS]", "theme": "Configuration Persistence",
        "functional_intent": "Config Persistence — Save running config and export as script",
        "cisco_ios":     "copy running-config startup-config | write memory",
        "cisco_iosxe":   "copy running-config startup-config | write memory",
        "cisco_nxos":    "copy running-config startup-config",
        "extreme_exos":  "save | save configuration as-script <filename>",
        "extreme_voss":  "save config",
        "extreme_slxos": "copy running-config startup-config",
        "negation_cisco": "", "negation_en": "",
        "notes": "Theme: Config Persistence. EXOS 'save configuration as-script' exports config as executable CLI script (useful for automation). VOSS 'save config' writes to /intflash/config.cfg. 'write memory' is an alias for copy run start on Cisco.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol9-Theme1", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[MGMT-OPS]", "theme": "Terminal & Session Parameters",
        "functional_intent": "Terminal Settings — Disable paging and manage active sessions",
        "cisco_ios":     "terminal length 0 | terminal width 256 | show users",
        "cisco_iosxe":   "terminal length 0 | terminal width 256 | show users",
        "cisco_nxos":    "terminal length 0 | terminal width 256 | show users",
        "extreme_exos":  "disable clipaging | show session",
        "extreme_voss":  "term more disable | terminal length 0 | show who | show session",
        "extreme_slxos": "terminal length 0 | show users",
        "negation_cisco": "terminal length 24 | terminal width 80", "negation_en": "enable clipaging | term more enable",
        "notes": "Theme: Terminal & Session. EXOS 'disable clipaging' prevents --More-- prompts. VOSS 'term more disable' equivalent. EXOS 'show session' shows active VTY sessions. VOSS 'show who' lists logged-in users.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol9-Theme2", "confidence": 1.0, "is_verified": True,
    },
    {
        "tag": "[MGMT-OPS]", "theme": "SNMP & Host Identification",
        "functional_intent": "SNMP Configuration — Set system name, location, contact, and SNMP community",
        "cisco_ios":     "hostname <name> | snmp-server community <str> ro | snmp-server location <loc> | snmp-server contact <contact>",
        "cisco_iosxe":   "hostname <name> | snmp-server community <str> ro | snmp-server location <loc> | snmp-server contact <contact>",
        "cisco_nxos":    "hostname <name> | snmp-server community <str> ro | snmp-server location <loc>",
        "extreme_exos":  "configure snmp sysName <name> | configure snmp add community readonly <str> | configure snmp sysLocation <loc>",
        "extreme_voss":  "prompt <name> | snmp-server host <ip> | snmp-server community <str> ro | snmp-server location <loc>",
        "extreme_slxos": "hostname <name> | snmp-server community <str> ro | snmp-server location <loc>",
        "negation_cisco": "no snmp-server community <str>", "negation_en": "configure snmp delete community readonly <str> | unconfigure snmp",
        "notes": "Theme: SNMP & Host ID. EXOS configures sysName (hostname) via SNMP context. VOSS 'prompt' sets CLI prompt while SNMP system name is separate. All platforms support SNMPv2c communities; SNMPv3 recommended for production.",
        "source_ref": "NB-Session-2026", "page_ref": "Vol9-Theme3", "confidence": 1.0, "is_verified": True,
    },
]


def load_themes(overwrite: bool = False) -> dict:
    """Insert thematic rows into the database."""
    from src.database.connection import get_session
    from src.database.models import CLIMapping
    from src.embeddings.encoder import encode_batch
    from sqlalchemy import text

    logger.info(f"Loading {len(THEME_DATA)} thematic rows from NotebookLM extraction...")

    intents = [r["functional_intent"] for r in THEME_DATA]
    embeddings = encode_batch(intents)

    added = skipped = errors = 0

    with get_session() as session:
        for record, embedding in zip(THEME_DATA, embeddings):
            try:
                if not overwrite:
                    exists = session.execute(
                        text("SELECT 1 FROM cli_mappings WHERE tag = :tag "
                             "AND functional_intent = :intent LIMIT 1"),
                        {"tag": record["tag"], "intent": record["functional_intent"]}
                    ).fetchone()
                    if exists:
                        skipped += 1
                        continue

                mapping = CLIMapping(
                    tag=record["tag"],
                    functional_intent=record["functional_intent"],
                    cisco_ios=record.get("cisco_ios", ""),
                    cisco_iosxe=record.get("cisco_iosxe", ""),
                    cisco_nxos=record.get("cisco_nxos", ""),
                    extreme_exos=record.get("extreme_exos", ""),
                    extreme_voss=record.get("extreme_voss", ""),
                    extreme_slxos=record.get("extreme_slxos", ""),
                    negation_cisco=record.get("negation_cisco", ""),
                    negation_en=record.get("negation_en", ""),
                    notes=record.get("notes", ""),
                    source_ref=record.get("source_ref", "NB-Session-2026"),
                    page_ref=record.get("page_ref", ""),
                    confidence=float(record.get("confidence", 1.0)),
                    is_verified=record.get("is_verified", True),
                    embedding=embedding,
                )
                session.add(mapping)
                added += 1
            except Exception as e:
                logger.error(f"Error inserting theme row: {e}")
                errors += 1

    logger.info(f"Themes: added={added} skipped={skipped} errors={errors}")
    return {"added": added, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s  %(message)s")

    from src.database.connection import init_db
    init_db()

    overwrite = "--overwrite" in sys.argv
    result = load_themes(overwrite=overwrite)
    print(f"\nDone: {result}")
