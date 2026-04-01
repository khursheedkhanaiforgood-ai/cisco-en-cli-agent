# Bin Guardrails: [SYS-INFO] — System Health & Inventory

## Functional Scope
Switch identity, hardware inventory, software versioning, environmental health (power/temp), CPU/memory utilization, time/timezone, and NX-OS observability framework.

---

## Theme 1: Hardware Inventory & UDI Data

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `show inventory`; `show inventory raw [entity]` |
| Cisco NX-OS | `show inventory`; NX-OS uses gRPC/NETCONF telemetry agents for structured inventory data |
| Switch Engine | `show switch` (general summary); `show slot [id] detail`; `show slots` |
| Fabric Engine | `show sys-info`; `show hardware` — **[Pending Source Verification for sub-command syntax]** |
| SLX-OS | `show inventory` |

**Switch Engine note:** `show switch` returns a compact one-liner summary (hostname, ports, image, MAC). `show slot` is used for modular chassis inventory. On stackable units, `show switch all` shows all stack members.

---

## Theme 2: Software Versioning

| Platform | Command |
|----------|---------|
| Cisco IOS-XE | `show version` |
| Cisco NX-OS | `show version`; `show module` |
| Switch Engine | `show version` |
| Fabric Engine | `show sys-info` (includes version) |
| SLX-OS | `show version` |

**Naming convention reminder:** As of Release 31.6, ExtremeXOS = **Switch Engine** and VOSS = **Fabric Engine**. Output from `show version` on Switch Engine will reference "Switch Engine" not "ExtremeXOS" on updated images.

---

## Theme 3: CPU/Memory & Process Monitoring

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `show processes cpu platform`; `show processes memory platform` |
| Cisco NX-OS | `show processes cpu`; `show memory` — NX-OS supports streaming **telemetry** via gRPC for real-time CPU/memory visibility without polling |
| Switch Engine | `show cpu-monitoring`; `show memory` |
| Fabric Engine | `show process`; `show storage-usage` |
| SLX-OS | — |

**NX-OS observability model:** Cisco NX-OS recommends gRPC streaming telemetry (not repeated `show` polling) for production monitoring. This is the Model-Driven Programmability (MDP) pattern — the DME database streams state changes rather than responding to SNMP polls.

---

## Theme 4: Environmental States (Power / Temperature)

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `show env xps`; `show power detail` |
| Cisco NX-OS | `show hardware power`; `show environment` |
| Switch Engine | `show power` (summary); `show power monitor`; `show inline-power` (PoE budget) |
| Fabric Engine | `show power supply`; `show alarm database` |
| SLX-OS | — |

**Switch Engine PoE note:** `show inline-power` is the command for Power over Ethernet budget and per-port power state. Cisco equivalent is `show power inline`.

---

## Theme 5: Time & Environment Configuration

| Platform | Show | Configure |
|----------|------|-----------|
| Cisco IOS-XE | `show clock` | `clock set`; `ntp server [ip]` |
| Cisco NX-OS | `show clock` | `clock set`; `ntp server [ip]` — `feature ntp` required first |
| Switch Engine | `show time`; `show timezone` | `configure timezone`; `configure ntp server add [ip]` |
| Fabric Engine | — | `clock set`; `ntp server` — **[Pending Source Verification]** |
| SLX-OS | — | — |

---

## NX-OS Observability Framework (Architectural Context)

When answering questions about NX-OS monitoring or health data, note that NX-OS is designed around three programmability pillars:

1. **YANG Data Modeling** — Device and OpenConfig YANG models describe all state; CLI is a "view" of the same DME database.
2. **Programmable Interface Agents** — NETCONF, RESTCONF, gRPC. These expose the same DME data as CLI but in structured form.
3. **Streaming Telemetry** — Real-time push of state changes (CPU, interface counters, BGP state) via gRPC. Preferred over SNMP polling in modern NX-OS deployments.

The `show` commands still work, but in production NX-OS shops, `show processes cpu` is replaced by a telemetry subscription query.

---

## Guardrails for AI Responses

1. **NX-OS `feature ntp`** must precede any NTP config.
2. **Switch Engine power monitoring** distinguishes `show power` (PSU health) from `show inline-power` (PoE) — do not conflate.
3. **Fabric Engine SYS-INFO commands** have limited source documentation — mark uncertain entries as `[Pending Source Verification]`.
4. **NX-OS production monitoring = telemetry**, not poll-and-show. Mention this when context involves NX-OS health/capacity management.
5. **Naming convention:** Always use "Switch Engine" and "Fabric Engine" in responses, not legacy names, unless the user references the legacy name.

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
