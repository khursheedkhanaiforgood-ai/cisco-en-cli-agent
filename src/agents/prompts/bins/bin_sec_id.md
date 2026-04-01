# Bin Guardrails: [SEC-ID] — Identity, AAA & Policy Authentication

## Functional Scope
AAA framework configuration (RADIUS/TACACS/LDAP), 802.1X/MAB port authentication, macro-security policy (Cisco TrustSec ↔ Extreme ONEPolicy), local account management, and role-based access control.

---

## Theme 1: AAA Framework & Server Reachability

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `aaa new-model`; `aaa authentication login default group radius local`; `aaa group server radius [name]`; `radius-server host` |
| Cisco NX-OS | Feature-first: `feature radius`; then NETCONF/RESTCONF/gRPC YANG model configuration. CLI: `radius-server host [ip]`; `aaa authentication login default group radius` |
| Switch Engine (EXOS) | `enable radius`; `configure radius [id] server [ip]`; `configure radius shared-secret`; `enable tacacs`; `configure tacacs`; `configure ldap domain` |
| Fabric Engine (VOSS) | `radius-server enable`; `radius-server host [ip]` — **[Pending Source Verification]** |
| SLX-OS | `aaa authentication`; `aaa accounting` |

**Critical NX-OS rule:** `feature radius` must be enabled before any AAA configuration. NX-OS AAA is exposed as a YANG sub-tree in the DME — CLI and API writes are equivalent.

**Switch Engine note:** TACACS and RADIUS are independent services — each must be explicitly enabled (`enable radius`, `enable tacacs`). Cisco `aaa new-model` is the closest single-command equivalent but does not map directly.

---

## Theme 2: Port Authentication Protocols (802.1X / MAB / Network Login)

| Platform | 802.1X Enable | Timer Config |
|----------|--------------|-------------|
| Cisco IOS-XE | `dot1x system-auth-control`; `authentication host-mode [single-host \| multi-host \| multi-auth]`; `dot1x pae authenticator` | `dot1x timeout tx-period [val]` |
| Cisco NX-OS | `feature dot1x`; `dot1x timeout tx-period [val]` | Configured via YANG model |
| Switch Engine | `enable netlogin dot1x`; `configure netlogin dot1x timers`; `configure netlogin dot1x eapol-transmit-version` | `configure netlogin add mac-list`; `clear netlogin state` |
| Fabric Engine | `eapol status auto`; `eapol multihost-session-stats` | **[Pending Source Verification]** |
| SLX-OS | Information not in source context | — |

**Switch Engine terminology:** Cisco calls it "dot1x" — Switch Engine calls it "netlogin dot1x". The concept maps directly but the CLI path is entirely different. Never use `dot1x` syntax for Switch Engine.

**Fabric Engine critical note:** VOSS/Fabric Engine uses `eapol` commands. These are distinct from both Cisco and EXOS. Mark as pending verification if specific sub-command syntax is uncertain.

---

## Theme 3: Macro-Security Policy (TrustSec ↔ ONEPolicy)

| Platform | Approach |
|----------|---------|
| Cisco IOS-XE TrustSec | `cts role-based sgt-map [ip] sgt [id]`; `cts role-based permissions from [sgt] to [sgt]` — Security Group Tags (SGTs) |
| Cisco NX-OS TrustSec | SGT propagation via CTS/MACsec; NX-OS acts as relay |
| Switch Engine ONEPolicy | `configure identity-policy [name]`; `configure identity-management role [role] policy [name]` |
| Fabric Engine | `fail-open-isid` (Continuity Mode) — maintains connectivity if policy server unreachable; `i-sid [id]` for policy-linked service segmentation |

**Architectural translation note:** Cisco TrustSec uses Software-Defined Segmentation via SGT labels propagated across the fabric. Extreme ONEPolicy uses Identity-Management roles mapped to VLANs/policies at port level. These are *functionally analogous* but architecturally different — SGT ≠ ONEPolicy role. Always explain the methodology difference, never suggest a 1:1 CLI equivalence.

---

## Theme 4: Local Account & Role-Based Access Management

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `username [name] privilege [0-15] password [pw]` |
| Cisco NX-OS | `username [name] role network-admin`; configured via NETCONF/RESTCONF YANG |
| Switch Engine | `create account [admin \| user \| operator] [name]`; `configure account password-policy`; `clear account lockout [name]`; `disable account`; `enable account` |
| Fabric Engine | **[Pending Source Verification]** |
| SLX-OS | **[Pending Source Verification]** |

**Switch Engine note:** Account types are explicit (`admin`, `user`, `operator`) — not privilege levels 0-15 as in Cisco. The privilege model does not map directly.

---

## Guardrails for AI Responses

1. **NX-OS always needs `feature radius` or `feature dot1x`** before any SEC-ID config.
2. **Switch Engine uses `netlogin` not `dot1x`** — never write `dot1x` commands for EXOS.
3. **TrustSec SGT ≠ ONEPolicy role** — always explain the architectural difference; do not imply 1:1 CLI translation.
4. **Fabric Engine EAPOL syntax** — mark uncertain sub-commands as `[Pending Source Verification]`.
5. **RADIUS and TACACS in Switch Engine are separate services** — both require independent enable commands.
