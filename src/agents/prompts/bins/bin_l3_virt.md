# Bin Guardrails: [L3-VIRT] — Layer 3 Routing & Virtual Routing

## Functional Scope
L3 VLAN interface (SVI) configuration, IP addressing, VRF instances, OSPF (v2/v3), BGP (IPv4/IPv6), route redistribution, and static routing. Covers the critical Switch Engine dual-step L3 prerequisite.

---

## CRITICAL RULE: Switch Engine Dual-Step L3 Prerequisite

**Every routing protocol on Switch Engine requires TWO steps:**

1. Configure the protocol on the VLAN
2. Enable IP forwarding on the VLAN

```
! Step 1: Configure OSPF on the VLAN
configure ospf add vlan [vlan-name] area [area-id]

! Step 2: MANDATORY — enable IP forwarding
enable ipforwarding vlan [vlan-name]
```

**If `enable ipforwarding` is missing, traffic will NOT route — even if OSPF adjacency forms and routes appear in the table. This is the most common L3 misconfiguration on Switch Engine.**

This applies to ALL routing protocols: OSPF, OSPFv3, BGP, RIP, IS-IS. Always include `enable ipforwarding vlan [name]` in any L3 config for Switch Engine.

---

## Theme 1: L3 Interface & IP Assignment (SVI)

| Platform | Create L3 Interface | Assign IP |
|----------|--------------------|-----------|
| Cisco IOS-XE | `interface vlan [id]`; `no shutdown` | `ip address [ip] [mask]` |
| Cisco NX-OS | `feature interface-vlan`; `interface vlan [id]` | `ip address [ip/prefix]` |
| Switch Engine | `create vlan [name] tag [id]`; then assign IP | `configure vlan [name] ipaddress [ip/mask]` |
| Fabric Engine | `interface vlan [id]` | `ip address [ip] [mask]` |
| SLX-OS | — | — |

**Switch Engine L3 VLAN flow:**
```
create vlan Mgmt tag 100
configure vlan Mgmt ipaddress 192.168.1.1/24
enable ipforwarding vlan Mgmt           ! Critical step
```

**NX-OS prerequisite:** `feature interface-vlan` must be enabled before VLAN interfaces can be configured (DME pattern).

---

## Theme 2: Secondary IP Addressing

| Platform | Command |
|----------|---------|
| Cisco IOS-XE | `ip address [ip] [mask] secondary` |
| Switch Engine | `configure vlan [name] add secondary-ipaddress [ip/mask]` |
| Fabric Engine | **[Pending Source Verification]** |

---

## Theme 3: Virtual Routing Instances (VRF)

| Platform | Create VRF | Add Interface/Port to VRF |
|----------|-----------|--------------------------|
| Cisco IOS-XE | `vrf definition [name]`; `address-family ipv4` | `ip vrf forwarding [name]` (in interface sub-mode) |
| Cisco NX-OS | `vrf context [name]` — NX-OS VRFs are DME objects; config via NETCONF/YANG also supported | `interface vlan [id]`; `vrf member [name]` |
| Switch Engine | `create virtual-router [name]`; `configure vr [name] description [text]` | `configure vr [name] add ports [port-id]` |
| Fabric Engine | `router vrf [name]` — **[Pending Source Verification for full VRF sub-command set]** | — |
| SLX-OS | `show vrf` (verification) | — |

**Switch Engine VRF terminology:** Called **Virtual Router (VR)** not VRF. The default VR is `VR-Default`. Management traffic uses `VR-Mgmt`. User-created VRs are distinct routing tables.

```
create virtual-router CustomerA
configure vr CustomerA add ports 1,2,3
configure vr CustomerA description "Customer A routing domain"
```

**NX-OS VRF note:** `feature vn-segment-vlan-based` may be required for VRF-lite in VXLAN environments. Standard VRF: `vrf context [name]`.

---

## Theme 4: OSPF Protocol Configuration

### Switch Engine (EXOS) — VLAN-Based OSPF
**Key architectural difference:** OSPF in Switch Engine is configured on VLANs, NOT on interfaces. This is the opposite of Cisco's interface-based OSPF.

```
create ospf area [area-id]                          ! Create area (e.g., 0.0.0.0)
configure ospf add vlan [vlan-name] area [area-id]  ! Add VLAN to OSPF area
configure ospf routerid [ip]                         ! Set Router-ID
configure ospf vlan [vlan-name] timer [hello] [dead] ! Optional: tune timers
enable ospf                                          ! Enable OSPF globally
enable ipforwarding vlan [vlan-name]                 ! MANDATORY second step
```

### Cisco IOS-XE — Interface-Based OSPF
```
router ospf [process-id]
  router-id [ip]
  network [ip] [wildcard] area [area-id]
! Or per-interface:
interface vlan [id]
  ip ospf [process-id] area [area-id]
```

### Cisco NX-OS
```
feature ospf                      ! Prerequisite — DME activation
router ospf [tag]
  router-id [ip]
interface vlan [id]
  ip router ospf [tag] area [id]
```

### OSPFv3 (IPv6) on Switch Engine
```
create ospfv3 area [area-id]
configure ospfv3 add interface vlan [vlan-name] area [area-id]
enable ospfv3
enable ipforwarding ipv6 vlan [vlan-name]   ! IPv6 forwarding — also mandatory
```

---

## Theme 5: BGP Protocol Configuration

| Platform | Enable/Init | Neighbor | Address Family |
|----------|------------|----------|----------------|
| Cisco IOS-XE | `router bgp [as]` | `neighbor [ip] remote-as [as]` | `address-family ipv4 unicast` |
| Cisco NX-OS | `feature bgp`; `router bgp [as]` | `neighbor [ip] remote-as [as]` | `address-family ipv4 unicast` |
| Switch Engine | `configure bgp as-number [as]`; `enable bgp` | `configure bgp neighbor [ip] remote-as-number [as]` | `configure bgp add network [prefix]` |
| Fabric Engine | `router bgp enable`; `neighbor [ip] remote-as [as]` — **[Pending Source Verification]** | — | — |

**NX-OS prerequisite:** `feature bgp` before any BGP config.

**Switch Engine BGP note:** BGP is configured from global mode with `configure bgp` commands — not in a sub-mode. This is consistent with Switch Engine's flat CLI paradigm.

---

## Theme 6: Static Routing

| Platform | Command |
|----------|---------|
| Cisco IOS-XE | `ip route [prefix] [mask] [nexthop]` |
| Cisco NX-OS | `ip route [prefix/len] [nexthop]` |
| Switch Engine | `configure iproute add [prefix/len] [nexthop] [metric]` (in VR context: `configure vr [name] add iproute`) |
| Fabric Engine | `ip route [prefix] [mask] [nexthop]` — **[Pending Source Verification]** |

---

## Guardrails for AI Responses

1. **`enable ipforwarding vlan [name]` is mandatory on Switch Engine** — ALWAYS include it after any routing protocol config. Never omit it.
2. **Switch Engine OSPF is VLAN-based** — `configure ospf add vlan [name]`, NOT `ip ospf [pid] area [id]` on an interface.
3. **Switch Engine BGP is flat-command** — no `router bgp` sub-mode.
4. **NX-OS needs `feature ospf` / `feature bgp`** before protocol config.
5. **Switch Engine VRF = Virtual Router (VR)** — terminology is different from Cisco VRF; functionality is the same.
6. **Fabric Engine L3 routing** has limited source documentation — mark uncertain sub-commands as `[Pending Source Verification]`.
7. **OSPFv3 on Switch Engine** also needs `enable ipforwarding ipv6 vlan [name]` — the IPv6 equivalent of the dual-step rule.

---

*© 2026 Khursheed Khan. All rights reserved. | CISCO-EN CLI Mapping Agent | March 31, 2026*
