---
name: factory-entry-contract
description: "The accepted entry sequence and planning-lock exits for Symphony Forge work"
metadata:
  node_type: memory
  type: project
---

# Factory entry contract

Prototype work is ceremony-free, but capabilities are captured as specs while
they emerge. Confirm every spec, derive the roadmap from those specs, then
record client sign-off. Existing sign-offs remain valid; this gate applies when
sign-off is recorded or re-recorded.

The product-write lock is always armed. There are three legitimate exits: an
approved plan, a bounded quickfix window opened with `./forge quickfix start
"<reason>"`, or a bounded lite window opened with `./forge mode lite`.

Sources: accepted decisions 0012, 0013, 0014, and 0031.
