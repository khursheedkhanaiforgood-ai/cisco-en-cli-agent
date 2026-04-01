# Bin Guardrails: [IF-PHYS] — Physical Interface & Port Access

## Functional Scope
Port description/naming, speed/duplex/autoneg, port breakout/partitioning, administrative state (enable/disable), MTU/jumbo frame, debounce, and port identification syntax.

---

## Theme 1: Logical Port Lifecycle (Speed / Duplex / Autoneg)

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `interface [type] [id]`; `speed [val]`; `duplex [full\|half]`; `negotiation auto` |
| Cisco NX-OS | `interface ethernet [slot/port]`; `speed [val]`; `duplex [full\|half]` |
| Switch Engine (EXOS) | `configure ports [id] speed [val]`; `configure ports [id] duplex`; `configure ports auto off \| on`; `configure ports auto 1G-optics-in-10G-ports` |
| Fabric Engine (VOSS) | `interface gigabitEthernet [id]`; `channelize enable` — **[Pending Source Verification for full sub-command set]** |
| SLX-OS | `speed` (Ethernet context); `interface ethernet [id]` |

**Critical Switch Engine syntax rule:** No sub-mode for ports. All port configuration is from the global CLI using flat commands: `configure ports [id] speed [val]`. Never use `interface ethernet` syntax for Switch Engine.

---

## Theme 2: Port Breakout & Hardware Profiles

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `interface breakout module [slot] port [range] map [type]` |
| Cisco NX-OS | `interface breakout-profile`; `interface breakout module [id]` |
| Switch Engine | `configure ports [id] speed [breakout_speed]` — uses speed value to trigger channelization |
| Fabric Engine | `interface gigabitEthernet [id/sub-port]` — sub-port notation for channelized interfaces |
| SLX-OS | `breakout mode` |

---

## Theme 3: Administrative Port State

| Platform | Enable Port | Disable Port |
|----------|------------|-------------|
| Cisco IOS-XE / NX-OS | `no shutdown` | `shutdown` |
| Switch Engine | `enable ports [id]` | `disable ports [id]` |
| Fabric Engine | `no shutdown` | `shutdown` |
| SLX-OS | `no shutdown` | `shutdown` |

**Critical rule:** Switch Engine does NOT use `shutdown` / `no shutdown`. It uses `enable ports` and `disable ports`. Translating Cisco `no shutdown` to Switch Engine requires `enable ports [id]`.

---

## Theme 4: Port Description & Display String

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE / NX-OS | `description [text]` (in interface sub-mode) |
| Switch Engine | `configure port [id] description-string [text]`; `configure ports [id] display-string [text]` |
| Fabric Engine | **[Pending Source Verification]** |
| SLX-OS | **[Pending Source Verification]** |

**Switch Engine distinction:** `description-string` is for the CLI description. `display-string` is a shorter label shown in status outputs (max 8 chars). Both can be set independently.

---

## Theme 5: MTU / Jumbo Frames

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `mtu [bytes]` (interface sub-mode) |
| Cisco NX-OS | `mtu [bytes]` (interface sub-mode); `system jumbomtu [bytes]` (global) |
| Switch Engine | `configure jumbo-frame-size [bytes]` (global); affects all ports |
| Fabric Engine | **[Pending Source Verification]** |
| SLX-OS | — |

**Switch Engine note:** Jumbo frame size is a global setting — cannot be set per-port. This differs from Cisco where MTU is per-interface.

---

## Port Numbering and Notation Rules (Switch Engine)

This is a **critical reference** — incorrect port notation causes CLI errors.

### Stand-alone Switches
| Notation | Meaning | Example |
|---------|---------|---------|
| `1` | Single port | `enable ports 1` |
| `1-10` | Contiguous range | `configure ports 1-10 speed 1000` |
| `1,5,9` | Non-contiguous list | `disable ports 1,5,9` |
| `1-5,7,10` | Mixed | `enable ports 1-5,7,10` |

### SummitStack (Stacked Switches)
| Notation | Meaning | Example |
|---------|---------|---------|
| `slot:port` | Specific port on slot | `configure ports 2:1 speed 10000` |
| `slot:*` | All ports on a slot | `enable ports 3:*` |

### Channelized Ports
| Notation | Meaning | Example |
|---------|---------|---------|
| `port:channel` | Channel on a port | `configure ports 49:4 speed 10000` |
| `slot:port:channel` | Channel on stacked | `configure ports 2:49:4` |

### XML-Reserved Characters
Switch Engine CLI does **not** support `&`, `<`, or `>` in any string parameter — these are XML reserved. Avoid in description strings.

---

## Object Naming Rules (Switch Engine) — Applied to Port Objects

When creating named port groups or policies:
- Must start with an **alphabetic character** (not a number, not underscore)
- May contain: letters, digits, underscores only
- Maximum length: **32 characters**
- Example valid: `Corporate_Uplink`; invalid: `1-uplink`, `corp&link`

---

## Guardrails for AI Responses

1. **Switch Engine never uses `shutdown` / `no shutdown`** — always `disable ports` / `enable ports`.
2. **Switch Engine never uses `interface` sub-mode** for port config — all commands are flat/global.
3. **Port notation matters** — always use `slot:port` for stacked, bare number for standalone.
4. **Jumbo frames are global on Switch Engine** — cannot set per-port MTU.
5. **Fabric Engine IF-PHYS commands** are limited in source documentation — mark uncertain entries `[Pending Source Verification]`.
6. **NX-OS IF-PHYS still uses `interface` sub-mode** — `interface ethernet 1/1` is valid NX-OS syntax.

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
