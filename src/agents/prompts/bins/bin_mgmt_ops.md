# Bin Guardrails: [MGMT-OPS] — Operations & Session Management

## Functional Scope
Configuration persistence (save/copy), SNMP management, NTP synchronization, syslog, SSH/Telnet session control, terminal parameters, banners, HTTP/HTTPS management access, host identity, and admin session management.

---

## Theme 1: Configuration Persistence

| Platform | Save Running Config | Verify Saved |
|----------|--------------------|-----------  |
| Cisco IOS-XE | `copy running-config startup-config` or `write memory` | `show startup-config` |
| Cisco NX-OS | `copy running-config startup-config` | `show startup-config` |
| Switch Engine | `save` | `show configuration` |
| Fabric Engine | `save config` | `show boot config` |
| SLX-OS | `copy running-config startup-config` | — |

**Switch Engine `save` behavior:** Saves to the currently active configuration partition (primary or secondary). To save to a named file: `save configuration as-script [filename]`. To see available configs: `show configuration`.

---

## Theme 2: Terminal & Session Parameters

| Platform | Disable Paging | Show Active Sessions |
|----------|--------------|---------------------|
| Cisco IOS-XE | `terminal length 0` | `show users` |
| Cisco NX-OS | `terminal length 0` | `show users` |
| Switch Engine | `disable clipaging` | `show session` |
| Fabric Engine | `term more disable` (or `terminal more disable`) | `show session` |
| SLX-OS | `terminal length 0` | — |

**Switch Engine:** `disable clipaging` disables the `--More--` paging prompt for the current session. To disable permanently: `configure cli-config prompt disable`. Note: this is a per-session setting by default.

---

## Theme 3: SNMP & Host Identification

| Platform | Set Hostname | SNMP Community | SNMP Trap |
|----------|-------------|----------------|----------|
| Cisco IOS-XE | `hostname [name]` | `snmp-server community [str] [RO\|RW]` | `snmp-server host [ip] version [2c\|3] [str]` |
| Cisco NX-OS | `hostname [name]` | `snmp-server community [str] group [role]` | `snmp-server host [ip] traps version [ver] [str]` |
| Switch Engine | `configure snmp sysName [name]` | `configure snmp add community [str] [readonly\|readwrite]` | `configure snmp add trapreceiver [ip] community [str]` |
| Fabric Engine | `prompt [name]` AND `sys name [name]` | `snmp-server host [ip]` | — |
| SLX-OS | `system-name [name]` | — | — |

**Switch Engine distinction:** There is no `hostname` command. System name is set via `configure snmp sysName`. This affects the management name shown in SNMP and show outputs.

**Fabric Engine dual-command rule:** BOTH `prompt [name]` (CLI prompt) and `sys name [name]` (system/SNMP name) are needed for complete identity. One alone is insufficient.

---

## Theme 4: NTP Configuration

| Platform | Configure NTP Server | Verify |
|----------|---------------------|--------|
| Cisco IOS-XE | `ntp server [ip]` | `show ntp status`; `show ntp associations` |
| Cisco NX-OS | `feature ntp`; `ntp server [ip]` | `show ntp status` |
| Switch Engine | `configure ntp server add [ip]`; `enable ntp` | `show ntp` |
| Fabric Engine | `ntp server [ip]` — **[Pending Source Verification]** | `show ntp` |
| SLX-OS | `ntp server [ip]` | — |

**NX-OS prerequisite:** `feature ntp` must be enabled first (DME pattern).

**Switch Engine two-step:** Both `configure ntp server add [ip]` AND `enable ntp` are required. Configuring the server without enabling NTP will not synchronize time.

---

## Theme 5: Syslog Configuration

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `logging [ip]`; `logging trap [level]`; `logging buffered [size] [level]` |
| Cisco NX-OS | `logging server [ip] [severity] facility [fac]` |
| Switch Engine | `configure syslog add [ip]`; `configure syslog severity [level]`; `enable syslog` |
| Fabric Engine | `logging remote-address [ip]` — **[Pending Source Verification]** |
| SLX-OS | `logging syslog-server [ip]` |

---

## Theme 6: SSH & Remote Access

| Platform | Enable SSH | Set SSH Version | Verify |
|----------|-----------|----------------|--------|
| Cisco IOS-XE | `crypto key generate rsa`; `ip ssh version 2` | `ip ssh version 2` | `show ip ssh` |
| Cisco NX-OS | `feature ssh`; `ssh key rsa 2048` | `ssh key rsa` | `show ssh server` |
| Switch Engine | `enable ssh2`; `configure ssh2 key` | SSH v2 only via `enable ssh2` | `show ssh2` |
| Fabric Engine | `ssh server enable` — **[Pending Source Verification]** | — | — |
| SLX-OS | `ssh server enable` | — | — |

**Switch Engine:** Uses `ssh2` (not `ssh`) in commands. SSHv1 is not supported. `enable ssh2` enables the SSH server.

---

## Theme 7: Management Access Control (HTTP/HTTPS)

| Platform | Commands |
|----------|---------|
| Cisco IOS-XE | `ip http server`; `ip http secure-server`; `ip http authentication [local\|aaa]` |
| Cisco NX-OS | `feature nxapi`; `nxapi http`; `nxapi https` — NX-API exposes both REST and CLI interfaces |
| Switch Engine | `enable web-mgmt http`; `enable web-mgmt https`; `configure ssl certificate` |
| Fabric Engine | **[Pending Source Verification]** |
| SLX-OS | — |

**NX-OS NX-API note:** Enabling `feature nxapi` creates a Developer Sandbox (accessible via browser) that helps transition from manual CLI to API calls. The NX-API supports both JSON-RPC and REST. This is a uniquely NX-OS capability — no equivalent on IOS-XE or Extreme.

---

## Theme 8: Login Banners

| Platform | MOTD Banner | Login Banner |
|----------|------------|-------------|
| Cisco IOS-XE | `banner motd [delimiter]...[delimiter]` | `banner login [delimiter]...[delimiter]` |
| Cisco NX-OS | `banner motd [delimiter]...[delimiter]` | — |
| Switch Engine | `configure banner [before-login \| after-login] [text]` | Same command, different option |
| Fabric Engine | `banner [text]` — **[Pending Source Verification]** | — |

---

## Guardrails for AI Responses

1. **Switch Engine uses `save`** not `copy running-config startup-config` — and `disable clipaging` not `terminal length 0`.
2. **Fabric Engine identity = `prompt` + `sys name`** — both are needed; never suggest just one.
3. **NX-OS needs `feature ntp`** before NTP config.
4. **Switch Engine NTP requires both `configure ntp server add` and `enable ntp`** — the enable step is frequently missed.
5. **Switch Engine has no `hostname` command** — use `configure snmp sysName`.
6. **NX-API is NX-OS exclusive** — flag it as such; never suggest it for IOS-XE or Extreme.
7. **Switch Engine SSH = `ssh2`** — not `ssh`. Always use the correct verb.
8. **Fabric Engine MGMT-OPS** has limited source documentation — mark uncertain commands as `[Pending Source Verification]`.

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
