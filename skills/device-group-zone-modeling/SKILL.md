---
name: device-group-zone-modeling
description: Use when modeling an OT/ICS network security zone, a conduit between zones, or a controller-scoped sub-plant grouping (e.g. one PLC operating several independent remote machines). Moqui's existing moqui.device.DeviceGroup/DeviceGroupMember already covers all three cases; do not invent a new Zone/Conduit/Facility-based entity before checking whether a DeviceGroup fits.
metadata:
  author: moqui-cybersecurity-agent
  version: "1.0"
---

# Device Group Zone/Conduit Modeling

IEC 62443-3-2 defines a zone as a grouping of assets that share common
security requirements — verified from the real, loaded norm text, not
assumed: "The intention of grouping assets into zones and conduits is to
identify those assets which share common security requirements..."; the
norm's own example divides a facility into "functional layers" (the Purdue
reference model: MES, supervisory/HMI, control/PLC, safety), which is a
logical/functional division, not necessarily physical containment. A zone
is not defined by where a device physically sits.

`moqui-device`'s existing `DeviceGroup`/`DeviceGroupMember` already models
exactly this: a named grouping of devices, with no constraint limiting a
device to a single group (`DeviceGroupMember`'s primary key is
`deviceId`+`memberDeviceId`, not just `memberDeviceId`). Do not invent a new
`Zone`/`Conduit` entity, and do not reach for `Facility`/`FacilityDevice`
(a physical-location mechanism, a different and orthogonal concern) before
checking whether a `DeviceGroup` fits — in every case examined in this
project so far, it did.

## The three cases

1. **Zone** = one `DeviceGroup` per security zone/network segment. Add each
   member device as a `DeviceGroupMember` with a `purposeEnumId` describing
   its functional role (e.g. `DgmpProcessPLC`, `DgmpRemoteIO`, `DgmpDrive` —
   see `moqui-device`'s seed data for the existing vocabulary before adding
   a new value).
2. **Conduit** (the communication path between two zones) = a boundary
   device (switch/router/firewall) that is a `DeviceGroupMember` of *two or
   more* zone-`DeviceGroup`s at once. The dual membership itself is the
   conduit — no separate edge/relationship entity needed. Mark the
   boundary-device membership row(s) with
   `purposeEnumId="DgmpZoneBoundary"` (added to `DeviceGroupMemberPurpose`
   in this project) so a query can distinguish "this device belongs to the
   zone" from "this device is the zone's boundary/conduit to another zone."
3. **Controller-scoped sub-plant** (one PLC operating N independent remote
   machines/lines) = N distinct `DeviceGroup`s, one per machine, each
   containing only that machine's own drives/I/O/sensors — not a single
   group for everything the PLC touches. This is the same mechanism as
   case 1, applied once per machine instead of once per physical panel.

## Workflow

1. Identify the zones relevant to the assessment (by shared security
   requirement/functional layer, not by room or cabinet). Create one
   `DeviceGroup` per zone if one doesn't already exist for that grouping
   (a panel-level `DeviceGroup` created for BOM/asset-tree purposes, e.g.
   Phase 2's per-panel groups, can double as a zone if that panel really is
   the right security boundary for the assessment at hand — verify this
   rather than assuming every existing `DeviceGroup` is automatically a
   zone).
2. Add each device as a `DeviceGroupMember` of its zone(s), with the
   functional `purposeEnumId` that already fits it.
3. Identify the boundary device(s) physically/logically connecting two
   zones. Add a *second* `DeviceGroupMember` row for that device under the
   other zone's `DeviceGroup`, with `purposeEnumId="DgmpZoneBoundary"`.
   Never guess the boundary device from a schematic without checking —
   text-extracted wiring diagrams lose drawn port-to-port connections; if
   the exact link can't be confirmed, say so explicitly in a comment/
   `description` field rather than asserting it as fact.
4. Query zone membership and conduits directly off `DeviceGroupMember`
   (e.g. "which devices are members of more than one `DeviceGroup`" finds
   every conduit device in the system) — no new view-entity is needed
   beyond what `moqui-device` already provides.

## Related

- `math-model-run-tracking` (same project) — if a zone/conduit-derived
  calculation (e.g. "does this zone have a monitored boundary") needs to be
  tracked over time, wrap it the same way `check#ProductCategoryCompliance`
  and `check#DeviceGroupContinuityImpact` are wrapped, rather than
  persisting the result directly on `DeviceGroup`/`DeviceGroupMember`.
- `norm-product-classification` (same project) — a separate axis: that
  skill classifies *what a product/device is* against norm-derived
  categories; this skill models *how devices are grouped and connected* on
  the network. A single real device typically needs both.
