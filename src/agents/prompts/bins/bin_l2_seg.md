# Bin Guardrails: [L2-SEG] — VLANs & Layer 2 Segmentation

## Functional Scope
VLAN creation/naming/lifecycle, trunk and tagged port assignment, access port mode, VLAN membership verification, Spanning Tree Protocol (STP/RSTP/MSTP), loop prevention (ELRP), and Fabric Engine VLAN-to-I-SID binding.

---

## Theme 1: VLAN Lifecycle & Naming

| Platform | Create | Name | Delete |
|----------|--------|------|--------|
| Cisco IOS-XE | `vlan [id]` (VLAN database mode); `name [text]` | Same sub-mode | `no vlan [id]` |
| Cisco NX-OS | `vlan [id]`; `feature vlan` may be required | `name [text]` | `no vlan [id]` |
| Switch Engine | `create vlan [name] tag [id]` | `configure vlan [name] name [text]` | `delete vlan [name]` |
| Fabric Engine | `vlan create [id] name [text] type port` | Same command | `no vlan [id]` |
| SLX-OS | `vlan [id]`; `extend vlan [id]` (for fabric extension) | `name [text]` | `no vlan [id]` |

**Critical Switch Engine rule:** VLANs are **named objects** — the name is primary, the tag (ID) is secondary. Commands always reference the VLAN by its name, not its ID.

Example: `create vlan Corporate tag 10` — then all subsequent commands use `Corporate`:
- `configure vlan Corporate add ports 1,2,3 tagged` ✓
- `configure vlan 10 add ports 1,2,3 tagged` — MAY work but name is the idiomatic form

**Shortcut logic (advanced):** Once a named VLAN exists and is unambiguous, the `vlan` keyword can be omitted:
- `configure Corporate add ports 1 tagged` is valid once `Corporate` is known as a VLAN.

---

## Theme 2: Trunking & Tagged Port Assignment

| Platform | Trunk Mode | Add Tagged VLAN |
|----------|-----------|----------------|
| Cisco IOS-XE | `switchport mode trunk` | `switchport trunk allowed vlan [id]` |
| Cisco NX-OS | `switchport mode trunk` | `switchport trunk allowed vlan [id]` |
| Switch Engine | No "trunk mode" — use tagged assignment directly | `configure vlan [name] add ports [id] tagged` |
| Fabric Engine | `encapsulation dot1q` (on interface) | `vlan members add [id] [port]` |
| SLX-OS | `switchport mode trunk` | `switchport trunk allowed vlan [id]` |

**Critical Switch Engine rule:** There is NO `switchport mode trunk` concept. Ports are tagged or untagged per-VLAN. To make a port a "trunk," simply add it as `tagged` to all relevant VLANs. A port can simultaneously be:
- **Tagged** in multiple VLANs (acts as trunk for those VLANs)
- **Untagged** in one VLAN (native/access VLAN behavior)

---

## Theme 3: Access Port / Untagged Assignment

| Platform | Command |
|----------|---------|
| Cisco IOS-XE | `switchport mode access`; `switchport access vlan [id]` |
| Cisco NX-OS | `switchport mode access`; `switchport access vlan [id]` |
| Switch Engine | `configure vlan [name] add ports [id] untagged` |
| Fabric Engine | `vlan members add [id] [port]` (untagged is default port type) |
| SLX-OS | `switchport access vlan [id]` |

---

## Theme 4: Native VLAN (Cisco) ↔ Untagged Default VLAN (Extreme)

| Platform | Concept | Command |
|----------|---------|---------|
| Cisco IOS-XE | Native VLAN on trunk port | `switchport trunk native vlan [id]` |
| Switch Engine | Untagged VLAN on a port | `configure vlan [name] add ports [id] untagged` |

Note: A Switch Engine port can only be **untagged** in ONE VLAN at a time. Attempting to add a port as untagged to a second VLAN will fail (or remove it from the first). This is functionally equivalent to Cisco native VLAN behavior.

---

## Theme 5: Spanning Tree & Loop Prevention

| Platform | STP Mode | Commands |
|----------|----------|---------|
| Cisco IOS-XE | PVST+, Rapid-PVST | `spanning-tree mode rapid-pvst`; `spanning-tree vlan [id] priority [val]` |
| Cisco NX-OS | MST | `spanning-tree mode mst`; `spanning-tree mst [instance] priority [val]` |
| Switch Engine | MSTP/RSTP via STP Domains | `create stpd [name]`; `enable stpd [name] auto-bind vlan [vlanname]`; `configure stpd [name] mode dot1w` (RSTP) |
| Fabric Engine | MSTP | `vlan create [id] type port-mstprstp [instance]` |
| SLX-OS | RSTP | `spanning-tree` |

**Switch Engine STP domain model:** Switch Engine uses an explicit **STPD (Spanning Tree Domain)** object that is distinct from Cisco per-VLAN STP. Key commands:
- `create stpd [name]` — creates the domain
- `enable stpd [name] auto-bind vlan [vlanname]` — binds VLANs to the STP domain
- `configure stpd [name] mode dot1w` — sets RSTP mode

The default STPD is `s0`. Do not delete it unless you know what you are doing.

---

## Theme 6: Loop Prevention (ELRP — Switch Engine Only)

Extreme Loop Recovery Protocol (ELRP) is an Extreme-specific active loop detection mechanism. No Cisco equivalent.

```
configure elrp-client periodic [vlan-name] [interval] [retries]
enable elrp-client
```

When a loop is detected, ELRP can automatically disable the offending port. Flag this as Extreme-only when translating from Cisco loop-protection features like `bpduguard`.

---

## Theme 7: Fabric Engine VLAN-to-I-SID Binding

For environments using Fabric Engine (VOSS) with SPBM:

```
vlan create [id] name [text] type port
vlan i-sid [vlan-id] [isid-id]
```

The `vlan i-sid` command binds a traditional VLAN to an I-SID (I-Component Service Identifier) in the SPBM fabric. This allows the VLAN to traverse the IS-IS backbone.

**There is no Cisco IOS/IOS-XE equivalent.** NX-OS VXLAN VNI is the closest architectural analogy (VXLAN VNI ↔ I-SID), but the CLI and protocols are different.

---

## Guardrails for AI Responses

1. **Switch Engine VLANs are named** — always show the `create vlan [name] tag [id]` pattern first.
2. **No `switchport mode trunk`** on Switch Engine — use tagged port assignments.
3. **No `switchport mode access`** on Switch Engine — use `untagged` port assignments.
4. **STP domain model** — Switch Engine uses STPDs, not per-VLAN spanning tree. Explain the mapping.
5. **ELRP is Extreme-only** — flag it as such when translating Cisco loop protection.
6. **I-SID binding** — only relevant for Fabric Engine (VOSS) environments using SPBM fabric. Irrelevant for pure Switch Engine deployments.
7. **Port notation** — always use correct Switch Engine notation (`slot:port` for stacked, plain number for standalone).

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
