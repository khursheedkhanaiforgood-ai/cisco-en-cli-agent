# Bin Guardrails: [ONBOARD] — Onboarding & Provisioning

## Functional Scope
Device initialization, factory reset, image management, ZTP/PnP/POAP/ZTF auto-discovery, identity/hostname, configuration persistence, and OS persona switching on Universal Hardware.

---

## Theme 1: System Sanitization & Day-0 Reset

| Platform | Command |
|----------|---------|
| Cisco IOS-XE | `write erase` then `reload` |
| Cisco NX-OS | `write erase` or `clear nvram` — state managed via DME |
| Switch Engine (EXOS) | `unconfigure switch all` or `unconfigure switch {all \| erase [all \| nvram]}` |
| Fabric Engine (VOSS) | `boot config flags factorydefaults reset-all-files` or `unconfigure switch` |
| SLX-OS | `clear config all` or `bmc factory reset` |

**Key rule:** Switch Engine uses `unconfigure` (not `no`) as the reset verb. Never translate Cisco `write erase` to EXOS `erase` — it does not exist.

---

## Theme 2: Automated Onboarding (ZTP / PnP / POAP / ZTF)

| Platform | Mechanism | Commands |
|----------|-----------|---------|
| Cisco IOS-XE | Plug-and-Play (PnP) | `pnp profile`; `feature pnp` |
| Cisco NX-OS | POAP (Power-On Auto Provisioning) | `system poap`; `feature poap`; `boot poap enable` |
| Switch Engine | ZTP (Zero-Touch Provisioning) | `show auto-provision`; `disable auto-provision`; `restart process ztpstack` |
| Fabric Engine | ZTF (Zero-Touch Fabric) | `auto-sense enable`; `auto-sense onboarding i-sid <id>`; `show application auto-provision` |
| SLX-OS | ZTP | `show ztp status` |

**Critical Fabric Engine rule:** ZTF (`auto-sense enable`) automatically discovers and joins the IS-IS/SPBM fabric. There is NO equivalent on Cisco. Do NOT attempt to translate this — state it explicitly as a Fabric Engine-only capability.

**Critical NX-OS rule:** POAP is distinct from IOS-XE PnP. Do not conflate them. NX-OS POAP requires `feature poap` first (DME pattern).

---

## Theme 3: Universal Persona & OS Transition (Extreme Only)

Extreme Universal Hardware (e.g., 5520, 5720) can run either Switch Engine or Fabric Engine. Transitioning between OSes:

- **Switch Engine → Fabric Engine:** Download VOSS software image, then use Bootrom spacebar menu to change OS.
- **Fabric Engine:** `software add`; `software activate`; `software commit`
- **Temporary ZTF re-trigger:** `boot config flags factorydefaults zero-touch-config-only`

**Cisco has no equivalent.** When asked about OS transitions on Universal Hardware, explain this is a uniquely Extreme capability — a single physical box can become either platform.

---

## Theme 4: Initial Identity & Prompt Configuration

| Platform | Command |
|----------|---------|
| Cisco IOS-XE / NX-OS | `hostname <name>` |
| Switch Engine | `configure snmp sysname <name>` |
| Fabric Engine | `prompt <name>` AND `sys name <name>` |
| SLX-OS | `system-name <name>` |

**Note:** Fabric Engine requires BOTH `prompt` (CLI prompt) and `sys name` (SNMP/management identity). Missing either leaves partial identity.

---

## Theme 5: Configuration Persistence & Boot Variables

| Platform | Save Command | Boot Image |
|----------|-------------|-----------|
| Cisco IOS-XE / NX-OS | `copy running-config startup-config` | `boot system flash:[file]` |
| Switch Engine | `save` | `use configuration [primary \| secondary \| file_name]` |
| Fabric Engine | `save config` | `boot config choice primary config-file [file]` |
| SLX-OS | `copy running-config startup-config` | — |

**Switch Engine:** `save` persists to the currently active config partition. To switch boot partition: `use configuration primary` or `use configuration secondary`.

---

## Theme 6: Software Acquisition & Image Management

| Platform | Command |
|----------|---------|
| Cisco IOS-XE | `install add file activate reloadfast commit` |
| Cisco NX-OS | `copy tftp flash:` then install via gNOI/NX-API |
| Switch Engine | `download image [url]`; `use image [primary \| secondary]` |
| Fabric Engine | `software add [file]`; `software activate [version]`; `software commit` |
| SLX-OS | `firmware download`; `firmware activate`; `firmware commit` |

---

## Guardrails for AI Responses

1. **Never use `no`** for Switch Engine resets — only `unconfigure`.
2. **ZTF is Fabric Engine exclusive** — always flag it as such. Never hallucinate a Cisco equivalent.
3. **NX-OS Day-0 = DME** — initialization commands are managed via Model-Driven Programmability; classical CLI may be absent.
4. **Universal Persona toggle** — only mention if user is asking about OS switching on Extreme hardware.
5. **Fabric Engine identity = dual command** — `prompt` + `sys name` are both required; one alone is insufficient.
6. If Fabric Engine commands are uncertain, add: `[Pending Source Verification — Fabric Engine commands should be confirmed against FE 9.x documentation]`
