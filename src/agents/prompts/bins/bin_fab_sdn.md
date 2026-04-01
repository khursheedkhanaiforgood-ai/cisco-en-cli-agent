# Bin Guardrails: [FAB-SDN] — Fabric Connect & SD-Access

## Functional Scope
IS-IS underlay configuration, SPBM control plane (Fabric Engine), BGP-EVPN overlay (Switch Engine), VXLAN/VNI to I-SID architectural mapping, Fabric Attach (FA) for edge devices, Zero-Touch Fabric (ZTF), and NX-OS SD-Access (LISP/VXLAN).

---

## Architectural Foundation

### Two Distinct Fabric Approaches

| Aspect | Cisco SD-Access (NX-OS/IOS-XE) | Extreme Fabric Connect (VOSS/FE) |
|--------|-------------------------------|----------------------------------|
| Underlay | LISP (IOS-XE) or IS-IS (NX-OS) | IS-IS (mandatory) |
| Overlay | VXLAN with VNI labels | SPBM with I-SID labels |
| Control plane | LISP Map-Server/Resolver or BGP-EVPN | IS-IS LSP with SPBM TLVs |
| Config model | DME + YANG (NX-OS); traditional CLI (IOS-XE) | Explicit CLI (`router isis`; `spbm`) |
| ZTP equivalent | PnP / POAP | ZTF (`auto-sense enable`) |

---

## Theme 1: Control Plane Discovery & IS-IS Adjacency

### Cisco SD-Access (NX-OS approach)
```
feature isis
router isis [tag]
  net [area-id.sys-id.00]
  is-type level-2
```
NX-OS: `feature isis` must precede all IS-IS config. Managed via YANG model in DME.

### Cisco IOS-XE SD-Access (LISP-based)
```
router lisp
  locator-table default
  map-server [ip] key [str]
  map-resolver [ip]
```

### Switch Engine (EXOS) — BGP-EVPN underlay
```
create isis area [name]
configure isis area [name] system-id [mac-addr]
enable isis
create bgp evpn instance [name]
```

### Fabric Engine (VOSS) — IS-IS/SPBM
IS-IS is the backbone protocol. Adjacency forms automatically once IS-IS is enabled and SPBM is configured.
```
router isis
  spbm [id]
  manual-area [area-id]
  sys-name [name]
  is-type l1
```
**[Pending Source Verification for exact Fabric Engine IS-IS sub-command syntax]**

### Zero-Touch Fabric (Fabric Engine only)
```
auto-sense enable
auto-sense onboarding i-sid <id>
```
ZTF uses IS-IS Hello packets to auto-discover the fabric and join it without manual IS-IS configuration. **There is no Cisco equivalent.** Always flag ZTF as a uniquely Fabric Engine capability.

---

## Theme 2: Data Plane Encapsulation (VXLAN ↔ SPBM)

| Concept | Cisco NX-OS (VXLAN) | Switch Engine (EVPN) | Fabric Engine (SPBM) |
|---------|---------------------|---------------------|---------------------|
| Encapsulation | VXLAN (UDP 4789) | VXLAN | IEEE 802.1aq (SPB) |
| Service ID | VNI (24-bit) | NSI (Network Service ID) | I-SID (24-bit) |
| L2 overlay object | `interface nve1`; `member vni [id]` | `create virtual-network [name]` | SPBM B-VLAN + I-SID |
| Backbone VLAN | N/A | — | `vlan create [id] type spbm-bvlan` |

**Functional parity rule:** Cisco's VXLAN VNI ≡ Switch Engine NSI ≡ Fabric Engine I-SID. These are architecturally analogous service identifiers for L2 extension across the fabric. Never use the same numeric values — these are independent namespaces.

---

## Theme 3: Service Mapping (VNI to I-SID / NSI)

### Cisco NX-OS
```
vlan [id]
  vn-segment [vni]           ! Binds VLAN to VNI in DME
interface nve1
  member vni [id] ingress-replication
```

### Switch Engine
```
configure vlan [name] add nsi [nsi-id]    ! Maps VLAN to NSI
create virtual-network [name] vxlan vni [id]
```

### Fabric Engine
```
vlan i-sid [vlan-id] [isid-id]            ! Binds VLAN to I-SID in SPBM fabric
configure fabric attach isid-nsi-offset [val]
```

**I-SID assignment rule (Fabric Engine):** I-SIDs are 24-bit values (1 to 16,777,215). The value must be consistent across all nodes for the service to extend. ZTF can auto-assign I-SIDs from a configured range. Always verify I-SID consistency when fabric services are not extending correctly.

---

## Theme 4: Fabric Attachment & Edge Setup

### Fabric Attach (Fabric Engine + Switch Engine)
Fabric Attach (FA) automates the mapping of edge devices to fabric services (I-SIDs) without manual SPBM configuration on the edge.

```
! On Fabric Engine (server role)
configure fabric attach ports [id]

! Edge device (client role — e.g., AP or IP phone)
configure fabric attach isid-nsi-offset [val]
```

FA allows devices that don't run SPBM to attach to the fabric as clients. The FA server (VOSS/FE node) proxies their service mapping. This is the Extreme equivalent of Cisco VxLAN EVPN multi-site edge attachment — but using a different protocol (LLDP-based FA TLVs).

---

## Theme 5: Fabric Infrastructure Initialization

| Platform | Prerequisites | Key Command |
|----------|--------------|-------------|
| Cisco NX-OS | `feature isis`; `feature bgp`; NETCONF/gRPC agents | DME-mediated; YANG model |
| Switch Engine | — | `enable stacking-support` (required for Universal Hardware fabric-ready mode) |
| Fabric Engine | Universal Hardware in FE mode | IS-IS auto-starts; ZTF discovers peers |

**Switch Engine note:** `enable stacking-support` must be run before fabric features are available on Universal Hardware platforms. This is NOT the same as enabling a traditional SummitStack — it enables the universal hardware fabric capability.

---

## Theme 6: Verification & Observability

| Platform | Commands |
|----------|---------|
| Switch Engine | `show bgp evpn`; `show isis`; `show virtual-network`; `show fabric attach ports` |
| Fabric Engine | `show isis adj`; `show spbm`; `show i-sid`; `show application auto-provision` |
| Cisco NX-OS | `show isis adj`; `show nve peers`; `show l2route evpn`; telemetry subscription |

---

## Guardrails for AI Responses

1. **ZTF is Fabric Engine exclusive** — never suggest it works on Cisco or Switch Engine.
2. **I-SID consistency** — if fabric services are not extending, I-SID value mismatch is the #1 cause.
3. **`enable stacking-support`** is required on Switch Engine Universal Hardware before fabric config.
4. **VNI ≠ I-SID ≠ NSI** — they are functionally equivalent service identifiers but in separate namespaces with different protocols.
5. **NX-OS LISP vs IS-IS** — IOS-XE SD-Access uses LISP; NX-OS Nexus fabrics use IS-IS/BGP-EVPN. These are different architectures under the "Cisco fabric" umbrella.
6. **Fabric Engine IS-IS sub-commands** — mark uncertain syntax as `[Pending Source Verification]`.
7. **Fabric Attach (FA)** — only explain FA when user is asking about connecting non-SPBM edge devices to the Fabric Engine fabric.
