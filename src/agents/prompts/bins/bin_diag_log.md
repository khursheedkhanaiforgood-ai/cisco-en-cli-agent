# Bin Guardrails: [DIAG-LOG] — Troubleshooting & Diagnostics

## Functional Scope
Connectivity testing (ping/traceroute), log management, packet capture (ethanalyzer/debug), interface statistics, L2 fabric path tracing (Fabric Engine), system health checks, and NX-OS event-history.

---

## Theme 1: Basic Connectivity & Path Tracing

| Platform | Ping | Traceroute | L2 Fabric Trace |
|----------|------|-----------|----------------|
| Cisco IOS-XE | `ping [ip]`; `ping [ip] source [intf] repeat [n] size [b]` | `traceroute [ip]` | N/A |
| Cisco NX-OS | `ping [ip]`; `ping [ip] vrf [name]` | `traceroute [ip] vrf [name]` | N/A |
| Switch Engine | `ping [ip]`; `ping [ip] vr [vr-name]` | `traceroute [ip]` | N/A |
| Fabric Engine | `ping [ip]`; `traceroute [ip]` | `traceroute [ip]` | `l2tracetree i-sid [isid]` |
| SLX-OS | `ping [ip]` | `traceroute [ip]` | N/A |

**Fabric Engine `l2tracetree`:** This command traces the Layer 2 multicast tree through the SPBM fabric for a given I-SID. It is Fabric Engine / VOSS exclusive — there is no equivalent on Cisco or Switch Engine. When asked about tracing paths in a fabric, offer this command specifically for VOSS/Fabric Engine environments.

**Switch Engine VR-aware ping:** When pinging from a specific VR (Virtual Router): `ping [ip] vr [vr-name]`. The default VR is `VR-Default`; management VR is `VR-Mgmt`.

---

## Theme 2: Log Persistence & Event History

| Platform | Show Logs | Clear Logs | Set Log Level |
|----------|-----------|-----------|--------------|
| Cisco IOS-XE | `show logging` | `clear logging` | `logging buffered [level]` |
| Cisco NX-OS | `show logging log`; `show system internal [module] event-history` | `clear logging log` | `logging level [module] [level]` |
| Switch Engine | `show log`; `show log [severity]`; `show log match [str]` | `clear log` | `configure syslog [params]` |
| Fabric Engine | `show logging`; `trace [module] [level]` | — | `boot config flags [level]` |
| SLX-OS | `show logging` | — | — |

**NX-OS event-history:** The `show system internal [module] event-history` command is NX-OS specific. It shows per-module internal event logs that are not in the standard syslog. Useful for debugging protocol state machines (e.g., OSPF SPF events, BGP FSM transitions). There is no direct Cisco IOS-XE or Extreme equivalent.

**Switch Engine log filtering:** `show log match [string]` filters log output by string — useful for quick troubleshooting without piping.

---

## Theme 3: Real-time Packet Capture

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `monitor capture [name] start`; `show monitor capture buffer` |
| Cisco NX-OS | `ethanalyzer local interface [inband\|mgmt] capture-filter [filter]`; `debug ethanalyzer` |
| Switch Engine | `show ports [id] statistics`; `show ports [id] rxerrors`; `debug hal [command]` |
| Fabric Engine | `show ports [id] statistics` |
| SLX-OS | — |

**NX-OS `ethanalyzer`:** NX-OS has an embedded Wireshark-compatible packet capture tool (`ethanalyzer`). It captures control-plane traffic on the inband or management interface. Not available on IOS-XE or Extreme platforms in the same form.

**Switch Engine packet analysis:** Switch Engine does not have an embedded packet capture tool equivalent to ethanalyzer. Interface statistics (`show ports [id] statistics`) and error counters are the primary tools. For deep packet capture, span/mirror ports to an external capture device.

---

## Theme 4: Interface Statistics & Error Counters

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `show interfaces [id]`; `show interfaces [id] counters` |
| Cisco NX-OS | `show interface [id]`; `show interface counters` |
| Switch Engine | `show ports [id] statistics`; `show ports [id] rxerrors`; `show ports [id] txerrors`; `show ports [id] collisions` |
| Fabric Engine | `show interfaces gigabitEthernet [id] statistics` |
| SLX-OS | `show interface [id]` |

**Switch Engine note:** Use `show ports [id] statistics detail` for extended counters including broadcast/multicast rates.

---

## Theme 5: System Health Diagnostics

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `show platform health`; `show processes cpu sorted` |
| Cisco NX-OS | `show system health`; `show hardware internal errors` |
| Switch Engine | `show sys-health-check`; `show diagnostics`; `show log messages` |
| Fabric Engine | `show alarm database`; `show trace` |
| SLX-OS | — |

**Switch Engine `show sys-health-check`:** A comprehensive single command that checks power supplies, fans, temperature sensors, and module status. No direct Cisco equivalent — closest is `show environment`.

---

## Theme 6: Debug Commands

| Platform | Enable Debug | Disable Debug |
|----------|-------------|--------------|
| Cisco IOS-XE | `debug [protocol]` | `no debug [protocol]` or `undebug all` |
| Cisco NX-OS | `debug [protocol]` | `no debug [protocol]`; also `show debug` |
| Switch Engine | `debug hal [command]`; `debug [module]` | `no debug` |
| Fabric Engine | `trace [module] [level]`; `trace shutdown` | `no trace [module]` |

**Caution on all platforms:** Debug commands can generate high CPU load. Always use specific debug targets rather than blanket debug all.

---

## Guardrails for AI Responses

1. **`l2tracetree` is Fabric Engine exclusive** — only offer it for VOSS/Fabric Engine environments; explain it has no Cisco equivalent.
2. **NX-OS `ethanalyzer`** — unique to NX-OS; explicitly note it is not available on Cisco IOS or Extreme platforms.
3. **Switch Engine has no embedded packet capture** — always clarify and suggest port mirroring as the alternative.
4. **NX-OS event-history** — useful for protocol FSM debugging; unique to NX-OS; mention it when diagnosing NX-OS protocol issues.
5. **Switch Engine uses `show ports` not `show interfaces`** — the command noun is `ports`, not `interfaces`.
6. **Fabric Engine DIAG-LOG syntax** is limited in source documentation — mark uncertain commands as `[Pending Source Verification]`.

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
