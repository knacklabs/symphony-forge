#!/usr/bin/env python3
from __future__ import annotations

# UTF-8 console safety (standalone entrypoint — see factory_lib for rationale):
# force UTF-8 stdout/stderr so non-Latin-1 glyphs don't crash a cp1252 console.
import sys as _utf8_sys
for _stream in (_utf8_sys.stdout, _utf8_sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
agents = root / "AGENTS.md"
text = agents.read_text(encoding="utf-8")
lines = text.splitlines()
# Lean renamed the read-order heading. Vendored clients still carry the old
# spelling until they upgrade, so either satisfies the contract.
required_markers = [
    ("## What This Repo Is",),
    ("## Mandatory Read Order", "## Context and Read Order"),
    ("## Runtime Modes",),
    ("## Hard Gates",),
]
missing = [" or ".join(group) for group in required_markers
           if not any(marker in text for marker in group)]
if len(lines) > 110:
    print(f"AGENTS.md is too long: {len(lines)} lines (max 110)")
    sys.exit(1)
if len(text.encode()) > 7000:
    print(f"AGENTS.md is too large: {len(text.encode())} bytes (max 7000)")
    sys.exit(1)
if missing:
    print("AGENTS.md is missing required sections:")
    for marker in missing:
        print(f"- {marker}")
    sys.exit(1)
for linked in ["WORKFLOW.md", "docs/FACTORY.md", "docs/QUALITY.md"]:
    if linked not in text:
        print(f"AGENTS.md must reference {linked}")
        sys.exit(1)
print("AGENTS hygiene OK")
