"""forge upgrade — re-vendor harness machinery into an existing client repo.

Run FROM the harness clone, targeting the client repo (mirrors `forge init`).
Replaces machinery the harness owns; never touches project-owned content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from factory_lib import (
    SIGNOFF_KEY, canonical_signoff_path, head_sha, insert_signoff_pin,
    load_json, repo_root,
)

from .common import fail
from .scaffold import (
    COPY_CLAUDE, COPY_CODEX, COPY_WORKFLOWS, DOC_CONTRACTS,
    HARNESS_OWNED_SKILLS, PROJECT_STARTERS,
    assert_target_destination,
    assert_target_file_destination,
    ensure_jsonl_attributes,
    guarded_copytree,
)

# Harness-owned: replaced wholesale on upgrade.
UPGRADE_TREES = ["factory", "constitution", "harness"]
UPGRADE_FILES = ["forge", "forge.cmd", "CLAUDE.md", "WORKFLOW.md"]
# .claude is MIXED ownership: client repos legitimately carry their own
# skills, agents, launch.json, and settings.local.json (standard Claude Code
# surfaces — see the thin-adapter linter). Upgrade replaces ONLY the paths
# the harness ships and never deletes client additions; retiring a
# harness-shipped path is an explicit upgrade note, not an rmtree side
# effect. Same rule for .codex/agents and .codex/skills below.
CLAUDE_HARNESS_OWNED = [
    *COPY_CLAUDE,
    *(f"skills/{skill}" for skill in HARNESS_OWNED_SKILLS),
]
CODEX_HARNESS_OWNED_SKILLS = tuple(
    f".codex/skills/{skill}" for skill in HARNESS_OWNED_SKILLS
)
RETIRED_FORGE_PROFILE_HASHES = {
    "architect.toml": "35faa44d7f1b022944b891c94b8694733278708c4ec1c68228838fff13e44b28",
    "backend.toml": "f6e60262307d3314819cb74a37d19c09ec8f6b75e6db86c9ce486b1924a01fcb",
    "debugger.toml": "49a401de95061a44523a96443c0250f0635613d3383dd03bd134bb3813ca4f10",
    "explorer.toml": "005a60fc53d4b444c89c0277264899922c58a14e62d6a4a56d3c83589efac14e",
    "frontend.toml": "973987f868ab4c6106b4f641cb00f1d1341ccdf7085bc9a17df926845c56679a",
    "griller.toml": "a48745f1fceb3544d539bcef3b8ac07bedbd19dfdf1296523b5873fbf20d2d65",
    "lite.toml": "89eb2fdde5648c31e0b073eccd918179f885e3dedfb4c906ea7d545cb98d7e8f",
    "performance.toml": "158305a29dd70b7a1dbbae18d5f8e765b44d224fd21571bf8ad95e65716c8ae5",
    "planner.toml": "c5ac3eb9a7fef55d06c1b11d35be3e213acc862060fb6626cdf322e1bf3e147a",
    "refactorer.toml": "384138f285f4178762f3f2c9c3abf230db09963213cc282efbb6ab2f722b6db5",
    "security.toml": "124e70c1bfc81459b842196be977b2304e85dbbd834166d1c9e60c7909707bbd",
    "tester.toml": "a6770f50e9b9bc772c883e9edd6aa112b30260a78aa9915cb94f1c98b48ed7f6",
}
LEAN_MIGRATION_VERSION = "lean-workflow-v2"
LEAN_MIGRATION_SUPPLEMENT = "lean-workflow-v2-supplement.json"
UPGRADE_RESUME_VERSION = "forge-upgrade-v1"
LEAN_ORIGINAL_EMPTY_RUNTIME_DIGEST = (
    "bb4b6c05b41897447063959fc782e9ca4c2e00f9b219559314b725485b91b2e8"
)
LEAN_LENSES = ("performance", "quality", "security")
UPGRADE_PRESERVED_ROOT = ".factory/migrations/.upgrade-preserved"

_FIXED_REVIEW_OPTIONAL_LIST_FIELDS = (
    "non_blocking_findings", "rejected_findings", "residual_risks",
    "reviewed_scope", "skills_used", "contract_verdicts",
)
_FIXED_REVIEW_OPTIONAL_STRING_FIELDS = (
    "task_id", "recommendation", "review_run_id", "brief_sha256",
    "branch_diff_digest",
)


def _fixed_review_optional_fields_reason(value: dict) -> str:
    for field in _FIXED_REVIEW_OPTIONAL_LIST_FIELDS:
        if field in value and not isinstance(value[field], list):
            return f"fixed review {field} is invalid"
    for field in _FIXED_REVIEW_OPTIONAL_STRING_FIELDS:
        if field in value and not isinstance(value[field], str):
            return f"fixed review {field} is invalid"
    return ""
LEAN_RETAINED_PROFILES = {
    # Keep the complete routed registry here for legacy inventory records. The
    # source registry is still read from the harness at upgrade time; these
    # names let a client-created scaffold classify every current role before
    # the source tree is copied over it.
    "architect.toml", "coder.toml", "debugger.toml",
    "docs-decomposer.toml", "explorer.toml", "frontend.toml",
    "functional-checker.toml", "griller.toml", "lite.toml",
    "performance.toml", "planner-high.toml", "planner.toml",
    "refactorer.toml", "security.toml", "tester.toml", "worker.toml",
}
KNOWN_FORGE_RETAINED_PROFILE_HASHES = {
    "planner-high.toml": {
        "ab70ba3f5ac469d63af14a10edf67a2ccdf8a2eab905bf5841fdd85f3f2225fb",
        "ba68c9092378cb45ba632b76cbb1a3d0e9601da617f4bbc45588a2ada46e912c",
        "d0dbfbea103f552d31ec233eebb53094d6f21c01be4c8b5d4cf69768beb962d2",
        "ee02022932efe1dffd4a9e3402ec11df10c60221d3c33513925be7573bcbe96c",
        "b22e54eef473edf628e6b1166bcf80ea93c97f09da4589c83fe069146b1503f2",
        "55e2b801ee7fa3aa70453e982652caa0da1a53a42077f23258e1b62c5e970b7b",
    },
    "docs-decomposer.toml": {
        "4b8ee76734f910c242e15f2b89232b312f10410f22c9c4e3dbdadccbc781d6fa",
        "ebc2299566ed42b196700ad9393421c79804a737b863db2b0587f79868343f00",
        "23f1007533de1073e449f2e4b40d277c71e31b8b2256ea87e5594f537968881b",
        "c2696d86dd5de5098ef7ff9d2b9d77d061a69be7b58e60601544e93ee560da3d",
        "b3bae16c3042a42762f717ff6357c060b9abec1ecb318182e9ad0a777820cfeb",
    },
    "functional-checker.toml": {
        "6411566c800dab5253346c63305fb61d6082533bf0f86d0283f1ecbb67d6d107",
        "1281c4fa2edbe4bb3f638f292a171b54ef0a677bc558f7b15a229fd2c5a61d3b",
        "ee780a013410a4f85bab129f8e412388e9b31ea307745d8c5f8117c08dcb7850",
        "7ef074d4e35b2e72564371a71c7b80f5aaa7495b9d5db30a56da0cb9b9ffc03e",
    },
}
LEAN_RUNTIME_PATHS = (
    "factory/scripts/forge_cli/approval.py",
    "factory/scripts/post_tool_use.py",
    ".codex/config.toml",
    ".codex/hooks.json",
    ".claude/settings.json",
)
SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def _forge_profile_hashes(harness: Path) -> dict[str, set[str]]:
    """Return known Forge bytes for every profile in the current registry.

    The retired hashes are intentionally kept separate: an old Sol profile is
    a migration input even when its filename is also present in the current
    registry. Current source bytes are added at runtime so adding a routed
    role does not require another hard-coded hash update here.
    """
    known = {
        name: set(hashes)
        for name, hashes in KNOWN_FORGE_RETAINED_PROFILE_HASHES.items()
    }
    agents = harness / ".codex" / "agents"
    if not agents.is_dir() or agents.is_symlink():
        return known
    for path in agents.iterdir():
        if (path.suffix != ".toml" or path.is_symlink() or not path.is_file()):
            continue
        known.setdefault(path.name, set()).add(
            hashlib.sha256(path.read_bytes()).hexdigest()
        )
    return known


def _linked_or_reparse(info: os.stat_result) -> bool:
    return bool(__import__("stat").S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400)


def _require_unlinked_path(target: Path, path: Path) -> None:
    """Refuse a link/reparse leaf or ancestor without rejecting a resolved root."""
    try:
        relative = path.relative_to(target)
    except ValueError:
        fail(f"Lean migration path escapes the target: {path}")
    current = target
    for part in relative.parts:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        try:
            info = current.lstat()
        except OSError as exc:
            fail(f"Lean migration cannot inspect {current}: {exc}")
        if _linked_or_reparse(info):
            fail(f"Lean migration refuses linked or reparse path {current}")


def _lean_manifest_path(target: Path, relative: object) -> Path:
    """Resolve one manifest path without permitting lexical target escape."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        fail("Lean migration manifest contains an unsafe path")
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if (posix.is_absolute() or windows.is_absolute()
            or ".." in posix.parts or "." in posix.parts):
        fail(f"Lean migration manifest path escapes the target: {relative}")
    path = target.joinpath(*posix.parts)
    _require_unlinked_path(target, path)
    return path


def _require_single_link_manifest(target: Path, manifest: Path) -> None:
    """Require a contained ordinary manifest before every in-place write."""
    _require_unlinked_path(target, manifest)
    if not manifest.exists():
        return
    try:
        info = manifest.lstat()
    except OSError as exc:
        fail(f"Lean migration cannot inspect manifest: {exc}")
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or _linked_or_reparse(info)):
        fail("Lean migration manifest is linked or not a regular file")


def _lean_family(relative: str, data: bytes | None = None) -> str:
    """Primary classifier for formats removed by Lean."""
    if relative == ".codex/config.toml" and data and b"codex_hooks = true" in data:
        return "old-hook-flag"
    if relative.startswith(".codex/agents/"):
        name = relative.rsplit("/", 1)[-1]
        expected = RETIRED_FORGE_PROFILE_HASHES.get(name)
        if expected and data is not None and hashlib.sha256(data).hexdigest() == expected:
            return "retired-forge-profile"
    if re.fullmatch(r"\.factory/(?:stories/[^/]+/)?grill-rounds/[^/]+\.json", relative):
        return "grill-round"
    if re.fullmatch(r"\.factory/(?:stories/[^/]+/)?grills/requirements\.json", relative):
        return "requirements-grill"
    if re.fullmatch(r"\.factory/(?:stories/[^/]+/)?grills/plan\.json", relative):
        try:
            value = json.loads(data.decode("utf-8")) if data else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        cold_fields = {
            "cold_input_sha256", "final_artifact_sha256",
            "finding_dispositions", "amendments", "artifact_delta",
        }
        if (not isinstance(value, dict)
                or "cold_input_sha256" not in value
                or (cold_fields.intersection(value)
                    and _current_grill_shape_reason("plan", value))):
            return "old-plan-grill"
    if re.fullmatch(r"\.factory/(?:stories/[^/]+/)?grills/tasks/[^/]+\.json", relative):
        try:
            value = json.loads(data.decode("utf-8")) if data else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        cold_fields = {
            "cold_input_sha256", "final_artifact_sha256",
            "finding_dispositions", "amendments", "artifact_delta",
        }
        if (not isinstance(value, dict) or "rounds" in value
                or "cold_input_sha256" not in value
                or (cold_fields.intersection(value)
                    and _current_grill_shape_reason("task", value))):
            return "old-task-grill"
    if re.fullmatch(r"\.factory/(?:stories/[^/]+/)?plan-approval\.json", relative):
        try:
            approval = json.loads(data.decode("utf-8")) if data else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            approval = None
        native_fields = {
            "approved_plan_sha256", "approved_by", "approved_at", "runtime",
            "session_id", "event_id", "plan_kind", "story", "task",
        }
        if (not isinstance(approval, dict)
                or not native_fields.issubset(approval)
                or approval.get("runtime") not in {"claude", "codex"}
                or approval.get("plan_kind") not in {"story", "task"}
                or approval.get("approved_by") != {
                    "claude": "human-via-Claude",
                    "codex": "human-via-Codex",
                }.get(approval.get("runtime"))
                or any(not isinstance(approval.get(field), str)
                       or not approval[field].strip()
                       for field in ("approved_at", "session_id", "event_id",
                                     "story"))
                or (approval.get("plan_kind") == "story"
                    and approval.get("task") != "")
                or (approval.get("plan_kind") == "task"
                    and (not isinstance(approval.get("task"), str)
                         or not approval["task"].strip()))
                or re.fullmatch(
                    r"[0-9a-f]{64}", str(approval.get("approved_plan_sha256") or ""),
                ) is None):
            return "manual-plan-approval"
    if re.fullmatch(r"\.factory/(?:stories/[^/]+/)?plan-mode/[^/]+\.json", relative):
        return "plan-mode-marker"
    if re.fullmatch(
            r"\.factory/stories/[^/]+/reviews/"
            r"(?:quality|performance|security)\.json",
            relative):
        try:
            value = json.loads(data.decode("utf-8")) if data else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        if isinstance(value, dict) and {
                "aspect", "commit", "brief_sha256", "review_run_id",
        }.issubset(value):
            return "story-fixed-review-lens"
        return "fixed-review-lens"
    if re.fullmatch(
            r"\.factory/stories/[^/]+/tasks/[^/]+/reviews/"
            r"(?:quality|performance|security)\.json",
            relative):
        return "fixed-review-lens"
    if re.fullmatch(
            r"\.factory/history/[^/]+/reviews/"
            r"(?:quality|performance|security)\.json",
            relative):
        return "history-fixed-review-lens"
    if (relative == ".factory/stages.json"
            or re.fullmatch(r"\.factory/stories/[^/]+/stages/[^/]+\.json", relative)):
        try:
            value = json.loads(data.decode("utf-8")) if data else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        if (isinstance(value, dict) and "stages" in value
                and not isinstance(value["stages"], list)):
            return "legacy-stage-stamp"
        records = value.get("stages") if isinstance(value, dict) \
            and "stages" in value else [value]
        stamps = [record.get("local_review_stamp") for record in records
                  if isinstance(record, dict) and "local_review_stamp" in record]
        if stamps and not all(
                isinstance(stamp, dict) and "reviewed_meaning" in stamp
                for stamp in stamps):
            return "legacy-stage-stamp"
    return ""


def _current_grill_shape_reason(gate: str, value: object) -> str:
    """Reject partial or hybrid cold-grill shapes before migration writes."""
    if not isinstance(value, dict):
        return "current grill is not a JSON object"
    if "rounds" in value:
        return "current grill contains retired rounds"
    required = {
        "generated_by": str, "gate": str, "verdict": str,
        "gaps": list, "contradictions": list, "resolutions": list,
        "finding_dispositions": list, "cold_input_sha256": str,
        "final_artifact_sha256": str,
    }
    invalid = [name for name, expected in required.items()
               if not isinstance(value.get(name), expected)]
    if invalid:
        return "current grill has invalid or missing field(s): " + ", ".join(invalid)
    if value.get("gate") != gate:
        return f"current grill gate is not {gate!r}"
    if value.get("verdict") not in {"pass", "blocked"}:
        return "current grill verdict is invalid"
    if any(re.fullmatch(r"[0-9a-f]{64}", value[name]) is None
           for name in ("cold_input_sha256", "final_artifact_sha256")):
        return "current grill has an invalid digest"
    for optional in ("amendments", "artifact_delta"):
        if optional in value and not isinstance(value[optional], list):
            return f"current grill {optional} is invalid"
    if (value["cold_input_sha256"] != value["final_artifact_sha256"]
            and (not value.get("amendments") or "artifact_delta" not in value)):
        return "changed current grill has no amendment bridge"
    if gate == "plan":
        for field in ("issue", "input_sha256"):
            if not isinstance(value.get(field), str) or not value[field].strip():
                return f"current plan grill has invalid or missing {field}"
        if re.fullmatch(r"[0-9a-f]{64}", value["input_sha256"]) is None:
            return "current plan grill has an invalid input digest"
    if gate == "task":
        task_required = {
            "task_id": str, "input_sha256": str, "task_plan_sha256": str,
            "inspected_refs": list, "current_flow": str,
            "criteria_map": dict, "decision": str,
            "new_abstractions": list, "grounding_basis": str,
            "grounding_treeish": str,
        }
        invalid = [name for name, expected in task_required.items()
                   if not isinstance(value.get(name), expected)]
        if invalid:
            return "current task grill has invalid or missing field(s): " + ", ".join(invalid)
        if (not value["task_id"].strip() or not value["current_flow"].strip()
                or not value["inspected_refs"]
                or value["decision"] not in {"keep", "split", "block"}
                or value["grounding_basis"] not in {"working-tree", "stage-baseline"}
                or any(not isinstance(item, str) or not item.strip()
                       for item in value["inspected_refs"])
                or any(not isinstance(item, str) or not item.strip()
                       for item in value["new_abstractions"])
                or any(not isinstance(key, str) or not key
                       or not isinstance(item, str) or not item.strip()
                       for key, item in value["criteria_map"].items())):
            return "current task grill proof fields are invalid"
        if any(re.fullmatch(r"[0-9a-f]{64}", value[name]) is None
               for name in ("input_sha256", "task_plan_sha256")):
            return "current task grill has an invalid proof digest"
    return ""


def _legacy_json_shape_reason(family: str, value: object) -> str:
    """Return why a recognized Lean-owned JSON artifact is not historical proof."""
    if not isinstance(value, dict):
        return "legacy artifact is not a JSON object"

    def fields(required: dict[str, type]) -> str:
        missing = [name for name, expected in required.items()
                   if not isinstance(value.get(name), expected)]
        return ("legacy artifact has invalid or missing field(s): "
                + ", ".join(missing)) if missing else ""

    if family == "grill-round":
        return fields({
            "generated_by": str, "questions": list, "at": str,
            "session_id": str,
        })
    if family in {
            "requirements-grill", "old-plan-grill", "old-task-grill"}:
        gate = {"old-plan-grill": "plan", "old-task-grill": "task"}.get(family)
        if gate and any(name in value for name in (
                "cold_input_sha256", "final_artifact_sha256",
                "finding_dispositions", "amendments", "artifact_delta")):
            return _current_grill_shape_reason(gate, value)
        reason = fields({
            "generated_by": str, "gate": str, "verdict": str,
            "gaps": list, "contradictions": list, "resolutions": list,
        })
        expected_gate = {
            "requirements-grill": "requirements",
            "old-plan-grill": "plan",
            "old-task-grill": "task",
        }[family]
        if not reason and value.get("gate") != expected_gate:
            return f"legacy artifact gate is not {expected_gate!r}"
        if not reason and family == "old-task-grill" \
                and not isinstance(value.get("rounds"), list):
            return "legacy task grill has no rounds list"
        return reason
    if family == "manual-plan-approval":
        reason = fields({
            "approved_plan_sha256": str, "issue": str, "story": str,
            "approver": str, "at": str,
        })
        if not reason and not re.fullmatch(
                r"[0-9a-f]{64}", value["approved_plan_sha256"]):
            return "legacy approval digest is not a SHA-256 identity"
        return reason
    if family == "plan-mode-marker":
        reason = fields({
            "generated_by": str, "path": str, "sha256": str,
            "sha256_body": str, "at": str, "session_id": str,
        })
        if not reason and any(not re.fullmatch(r"[0-9a-f]{64}", value[name])
                              for name in ("sha256", "sha256_body")):
            return "legacy plan-mode marker has an invalid digest"
        return reason
    if family in {"fixed-review-lens", "story-fixed-review-lens"}:
        reason = fields({
            "generated_by": str, "score": int,
            "summary": str, "blocking_findings": list,
            "branch_diff_digest": str,
        })
        if (not reason and (value["generated_by"] != "autoreview"
                            or isinstance(value["score"], bool)
                            or not 0 <= value["score"] <= 10
                            or not value["summary"].strip())):
            return "fixed review lens has invalid proof fields"
        if (not reason and "non_blocking_findings" in value
                and not isinstance(value["non_blocking_findings"], list)):
            return "fixed review lens has invalid non-blocking findings"
        if not reason:
            reason = _fixed_review_optional_fields_reason(value)
        if (not reason and "task_id" in value
                and not isinstance(value["task_id"], str)):
            return "fixed review task identity is invalid"
        if not reason and not re.fullmatch(
                r"[0-9a-f]{64}", value["branch_diff_digest"]):
            return "fixed review lens has an invalid delta identity"
        if (not reason and "task_id" in value
                and SAFE_COMPONENT.fullmatch(value["task_id"]) is None):
            return "fixed review task identity is not a safe path component"
        return reason
    if family == "history-fixed-review-lens":
        reason = fields({
            "generated_by": str, "score": int, "summary": str,
            "blocking_findings": list, "non_blocking_findings": list,
            "aspect": str, "commit": str, "recorded_at": str,
        })
        if (not reason and (value["generated_by"] != "autoreview"
                            or isinstance(value["score"], bool)
                            or not 0 <= value["score"] <= 10
                            or not value["summary"].strip()
                            or value["aspect"] not in LEAN_LENSES
                            or not value["recorded_at"].strip())):
            return "historical fixed review has invalid proof fields"
        if not reason:
            reason = _fixed_review_optional_fields_reason(value)
        if not reason and not re.fullmatch(r"[0-9a-f]{40}", value["commit"]):
            return "historical fixed review has an invalid commit identity"
        return reason
    if family == "legacy-stage-stamp":
        records = value.get("stages") if "stages" in value else [value]
        if not isinstance(records, list) or not records:
            return "legacy stage state has no stage records"
        stamps = [record.get("local_review_stamp")
                  for record in records if isinstance(record, dict)
                  and "local_review_stamp" in record]
        if not stamps:
            return "legacy stage state has no local review stamp"
        if any(not isinstance(stamp, dict) for stamp in stamps):
            return "legacy local review stamp is not an object"
        current = ["reviewed_meaning" in stamp for stamp in stamps]
        if all(current):
            return "legacy stage state contains only current review stamps"
        if any(current):
            return "legacy stage state mixes current and legacy review stamps"
        for stamp in stamps:
            common = {
                "stage_id": str, "base_sha": str, "recorded_at": str,
                "generated_by": str,
            }
            missing = [name for name, expected in common.items()
                       if not isinstance(stamp.get(name), expected)]
            if missing:
                return ("legacy local review stamp has invalid or missing field(s): "
                        + ", ".join(missing))
            if "delta_id" in stamp:
                if not isinstance(stamp["delta_id"], str):
                    return "legacy local review stamp has invalid delta identity"
            elif any(not isinstance(stamp.get(name), str) for name in (
                    "task_sha256", "brief_sha256", "product_tree_digest")):
                return "legacy local review stamp has no historical binding"
    return ""


def _converted_stage_bytes(data: bytes) -> bytes:
    """Build the durable current stage-state bytes from one legacy input."""
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("legacy stage state is not an object")
    records = value.get("stages") if isinstance(value.get("stages"), list) else [value]
    for record in records:
        if isinstance(record, dict):
            stamp = record.get("local_review_stamp")
            if isinstance(stamp, dict) and "reviewed_meaning" not in stamp:
                record.pop("local_review_stamp", None)
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def _entry_identity(relative: str) -> dict:
    parts = Path(relative).parts
    identity: dict[str, object] = {"source_paths": [relative]}
    if (len(parts) > 2 and parts[0] == ".factory"
            and parts[1] in {"stories", "history"}):
        identity["story"] = parts[2]
    if len(parts) > 5 and parts[3] == "tasks":
        identity["task_id"] = parts[4]
    elif "/grills/tasks/" in relative:
        identity["task_id"] = Path(relative).stem
    return identity


def _unique_decomposition_task(target: Path, story: str) -> str:
    """Return the sole authoritative task for pre-task-id story proof."""
    path = target / ".factory" / "stories" / story / "decomposition.json"
    _require_unlinked_path(target, path)
    if not path.is_file():
        return ""
    try:
        info = path.lstat()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or not isinstance(value, dict) or value.get("story") != story
            or not isinstance(value.get("tasks"), list)):
        return ""
    if len(value["tasks"]) != 1:
        return ""
    task = value["tasks"][0]
    return (task["id"] if isinstance(task, dict)
            and isinstance(task.get("id"), str)
            and SAFE_COMPONENT.fullmatch(task["id"]) else "")


def _classify_fixed_review_coverage(target: Path, entries: list[dict]) -> None:
    """Mark display-only fixed proof before any migration output is built."""
    from factory_lib import (
        _committed_task_marker, product_delta_digest,
        read_selected_review_generation,
    )

    def invalidate(rows: list[dict], reason: str) -> None:
        for row in rows:
            row.update(classification="invalid", reason=reason)

    grouped: dict[tuple[str, str], list[dict]] = {}
    for entry in entries:
        if (entry.get("family") != "fixed-review-lens"
                or entry.get("classification") == "invalid"):
            continue
        parts = Path(entry["path"]).parts
        story = parts[2]
        path_task = parts[4] if parts[3] == "tasks" else ""
        grouped.setdefault((story, path_task), []).append(entry)
    resolved: dict[tuple[str, str], list[list[dict]]] = {}
    for (story, path_task), rows in grouped.items():
        values = [json.loads((target / row["path"]).read_text(encoding="utf-8"))
                  for row in rows]
        task_ids = {value.get("task_id") for value in values
                    if "task_id" in value}
        if len(task_ids) > 1 or (task_ids and not all(
                "task_id" in value for value in values)):
            invalidate(rows, "fixed review has invalid or mixed task identity")
            continue
        task = (next(iter(task_ids)) if task_ids else
                path_task or _unique_decomposition_task(target, story))
        if not task and not path_task:
            for row in rows:
                row.update(
                    classification="excluded",
                    reason="unattributed story fixed review requires a fresh review",
                    preserve=True,
                )
            continue
        if (not task or SAFE_COMPONENT.fullmatch(task) is None
                or (path_task and task != path_task)):
            for row in rows:
                row.update(classification="invalid",
                           reason="fixed review has invalid or mixed task identity")
            continue
        for row in rows:
            row["story"], row["task_id"] = story, task
            row["source_paths"] = sorted(item["path"] for item in rows)
        resolved.setdefault((story, task), []).append(rows)
    for (story, task), families in resolved.items():
        if len(families) != 1:
            for rows in families:
                for row in rows:
                    row.update(classification="invalid",
                               reason="fixed review is multiply bound")
            continue
        rows = families[0]
        values = [json.loads((target / row["path"]).read_text(encoding="utf-8"))
                  for row in rows]
        lenses = {Path(row["path"]).stem for row in rows}
        if lenses != set(LEAN_LENSES):
            for row in rows:
                row.update(classification="excluded",
                           reason="incomplete fixed review is display-only",
                           preserve=True)
            continue
        deltas = {value["branch_diff_digest"] for value in values}
        selection = (target / ".factory" / "stories" / story / "tasks" / task
                     / "reviews" / "selected.json")
        _require_unlinked_path(target, selection)
        if (not selection.exists() and not selection.is_symlink()
                and len(deltas) != 1):
            invalidate(rows, "sealed fixed review has conflicting delta identity")
            continue
        marker = (target / ".factory" / "stories" / story / "tasks" / task
                  / "pr-ready.json")
        _require_unlinked_path(target, marker)
        if not marker.is_file():
            if len(deltas) != 1:
                invalidate(rows, "sealed fixed review has conflicting delta identity")
                continue
            for row in rows:
                row.update(classification="eligible",
                           reason="active fixed review requires a fresh review",
                           preserve=False)
            continue
        marker_bytes = marker.read_bytes()
        try:
            marker_value = json.loads(marker_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError):
            invalidate(rows, "sealed fixed review marker is malformed")
            continue
        if not isinstance(marker_value, dict):
            invalidate(rows, "sealed fixed review marker is malformed")
            continue
        committed, marker_problem = _committed_task_marker(
            target, story, task, marker_value, None,
        )
        if marker_problem or committed is None:
            invalidate(rows, "sealed fixed review marker is invalid: "
                       + (marker_problem or "not committed"))
            continue
        sealed = committed["commit"]
        expected_delta = product_delta_digest(
            target, marker_value.get("review_base_sha")
            or marker_value.get("base_main_sha", ""), sealed,
        )
        if selection.exists() or selection.is_symlink():
            generation, pointer, problems = read_selected_review_generation(
                target, story, task, expected_delta_id=expected_delta,
                sealed_commit=sealed,
            )
            if (problems or not isinstance(generation, dict)
                    or not isinstance(pointer, dict)
                    or generation.get("inspected_commit") != sealed):
                invalidate(rows, "mixed canonical and fixed review proof: "
                           + "; ".join(
                               problems or ["selected proof lacks exact sealed binding"],
                           ))
                continue
        elif marker_value.get("reconciled") is True:
            for row in rows:
                row.update(classification="excluded",
                           reason="active fixed review requires a fresh review",
                           preserve=True)
            continue
        else:
            if deltas != {expected_delta}:
                invalidate(rows,
                           "sealed fixed review delta does not match its marker")
                continue
        marker_identity = {
            "path": marker.relative_to(target).as_posix(),
            "sha256": hashlib.sha256(marker_bytes).hexdigest(),
            "commit": sealed,
        }
        for row in rows:
            row.update(reason="sealed complete fixed review",
                       marker_identity=marker_identity)


def _classify_history_fixed_review_coverage(
        target: Path, entries: list[dict]) -> None:
    """Retire only complete fixed review triples from sealed story history."""
    groups: dict[str, list[dict]] = {}
    for entry in entries:
        if (entry.get("family") == "history-fixed-review-lens"
                and entry.get("classification") != "invalid"):
            groups.setdefault(Path(entry["path"]).parts[2], []).append(entry)
    for story, rows in groups.items():
        problem = ""
        if {Path(row["path"]).stem for row in rows} != set(LEAN_LENSES):
            problem = "historical fixed review is incomplete"
        run = target / ".factory" / "history" / story / "run.json"
        _require_unlinked_path(target, run)
        try:
            info = run.lstat()
            state = json.loads(run.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            problem = problem or "historical fixed review has no sealed story state"
        else:
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or not isinstance(state, dict)
                    or state.get("issue_key") != story
                    or state.get("phase") not in {"pr-ready", "done"}):
                problem = problem or "historical fixed review has no sealed story state"
        for row in rows:
            value = json.loads((target / row["path"]).read_text(encoding="utf-8"))
            if value.get("aspect") != Path(row["path"]).stem:
                problem = problem or "historical fixed review aspect does not match its path"
        for row in rows:
            row.update(
                classification="invalid" if problem else "eligible",
                reason=problem or "sealed historical fixed review is retained",
                preserve=not problem,
                source_paths=sorted(item["path"] for item in rows),
            )


def _classify_story_fixed_review_coverage(
        target: Path, entries: list[dict]) -> None:
    """Retire only complete, coherently identified proof for a shipped story."""
    groups: dict[str, list[dict]] = {}
    for entry in entries:
        if (entry.get("family") == "story-fixed-review-lens"
                and entry.get("classification") != "invalid"):
            groups.setdefault(Path(entry["path"]).parts[2], []).append(entry)
    for story, rows in groups.items():
        problem = ""
        if {Path(row["path"]).stem for row in rows} != set(LEAN_LENSES):
            problem = "story fixed review is incomplete"
        shipped = target / ".factory" / "stories" / story / "shipped.json"
        _require_unlinked_path(target, shipped)
        try:
            info = shipped.lstat()
            state = json.loads(shipped.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            problem = problem or "story fixed review has no sealed story state"
        else:
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or not isinstance(state, dict)
                    or state.get("story") != story
                    or state.get("phase") != "shipped"
                    or not isinstance(state.get("shipped_at"), str)
                    or not state["shipped_at"].strip()):
                problem = problem or "story fixed review has no sealed story state"
        identities = []
        for row in rows:
            value = json.loads((target / row["path"]).read_text(encoding="utf-8"))
            if value.get("aspect") != Path(row["path"]).stem:
                problem = problem or "story fixed review aspect does not match its path"
            identity = tuple(value.get(field) for field in (
                "commit", "branch_diff_digest", "brief_sha256", "review_run_id",
            ))
            if (not isinstance(identity[0], str)
                    or re.fullmatch(r"[0-9a-f]{40}", identity[0]) is None
                    or any(not isinstance(value, str)
                           or re.fullmatch(r"[0-9a-f]{64}", value) is None
                           for value in identity[1:])):
                problem = problem or "story fixed review identity is invalid"
            identities.append(identity)
        if identities and any(identity != identities[0] for identity in identities[1:]):
            problem = problem or "story fixed review identity conflicts"
        identity = (identities[0] if identities
                    and all(isinstance(item, str) for item in identities[0])
                    else ("", "", "", ""))
        story_identity = {
            "path": shipped.relative_to(target).as_posix(),
            "sha256": (hashlib.sha256(shipped.read_bytes()).hexdigest()
                       if shipped.is_file() else ""),
            "commit": identity[0], "branch_diff_digest": identity[1],
            "brief_sha256": identity[2], "review_run_id": identity[3],
        }
        for row in rows:
            row.update(
                classification="invalid" if problem else "eligible",
                reason=problem or "sealed story fixed review is retained",
                preserve=not problem,
                source_paths=sorted(item["path"] for item in rows),
                story_identity=story_identity,
            )


def lean_primary_inventory(target: Path) -> list[dict]:
    """Discover only the declared Lean legacy roots and candidate parents."""
    candidates: list[Path] = []

    def directory(path: Path) -> bool:
        _require_unlinked_path(target, path)
        if not path.exists() and not path.is_symlink():
            return False
        try:
            info = path.lstat()
        except OSError as exc:
            fail(f"Lean migration cannot inspect candidate parent {path}: {exc}")
        if (_linked_or_reparse(info)
                or not stat.S_ISDIR(info.st_mode)):
            fail(f"Lean migration refuses linked or non-directory candidate parent {path}")
        return True

    def exact(path: Path) -> None:
        _require_unlinked_path(target, path)
        if path.exists() or path.is_symlink():
            candidates.append(path)

    def matching(parent: Path) -> None:
        if not directory(parent):
            return
        try:
            children = list(os.scandir(parent))
        except OSError as exc:
            fail(f"Lean migration cannot inspect candidate parent {parent}: {exc}")
        candidates.extend(Path(child.path) for child in children)

    config = target / ".codex/config.toml"
    exact(config)
    matching(target / ".codex/agents")

    factory = target / ".factory"
    if directory(factory):
        matching(factory / "grill-rounds")
        matching(factory / "grills")
        matching(factory / "grills/tasks")
        exact(factory / "plan-approval.json")
        matching(factory / "plan-mode")
        exact(factory / "stages.json")
        stories = factory / "stories"
        if directory(stories):
            for entry in os.scandir(stories):
                story = Path(entry.path)
                if (entry.is_symlink()
                        or not entry.is_dir(follow_symlinks=False)):
                    fail(f"Lean migration refuses linked or non-directory candidate parent {story}")
                matching(story / "grill-rounds")
                matching(story / "grills")
                matching(story / "grills/tasks")
                exact(story / "plan-approval.json")
                matching(story / "plan-mode")
                matching(story / "stages")
                matching(story / "reviews")
                tasks = story / "tasks"
                if directory(tasks):
                    for task_entry in os.scandir(tasks):
                        task = Path(task_entry.path)
                        if (task_entry.is_symlink()
                                or not task_entry.is_dir(follow_symlinks=False)):
                            fail("Lean migration refuses linked or non-directory "
                                 f"candidate parent {task}")
                        matching(task / "reviews")
        history = factory / "history"
        if directory(history):
            for entry in os.scandir(history):
                story = Path(entry.path)
                if (entry.is_symlink()
                        or not entry.is_dir(follow_symlinks=False)):
                    fail("Lean migration refuses linked or non-directory "
                         f"candidate parent {story}")
                matching(story / "reviews")
    migration_temps = _bound_lean_temporary_paths(
        target, {path.relative_to(target).as_posix() for path in candidates},
    )
    entries = []
    for path in sorted(set(candidates)):
        relative = path.relative_to(target).as_posix()
        try:
            info = path.lstat()
        except OSError as exc:
            fail(f"Lean migration cannot inventory {relative}: {exc}")
        if _linked_or_reparse(info):
            fail(f"Lean migration refuses linked or non-regular candidate {relative}")
        if stat.S_ISDIR(info.st_mode):
            if (relative.endswith("/grills/tasks")
                    or relative.endswith("/reviews/generations")):
                entries.append({
                    "path": relative, "family": "", "type": "directory",
                    "classification": "excluded",
                    "reason": ("canonical-review-output"
                               if relative.endswith("/reviews/generations")
                               else "current-container"),
                    "preserve": True,
                    **_entry_identity(relative),
                })
                continue
            fail(f"Lean migration refuses unexpected directory candidate {relative}")
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            fail(f"Lean migration refuses linked or non-regular candidate {relative}")
        data = path.read_bytes()
        if relative in migration_temps:
            entries.append({
                "path": relative, "family": "lean-migration-temporary",
                "type": "file", "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "classification": "excluded",
                "reason": "manifest-bound interrupted migration temporary",
                "preserve": False, **_entry_identity(relative),
            })
            continue
        family = _lean_family(relative, data)
        if not data and not family:
            if relative.endswith("/grills/plan.json") \
                    or relative == ".factory/grills/plan.json":
                family = "old-plan-grill"
            elif "/grills/tasks/" in relative and relative.endswith(".json"):
                family = "old-task-grill"
            elif relative.endswith("/plan-approval.json") \
                    or relative == ".factory/plan-approval.json":
                family = "manual-plan-approval"
            elif relative == ".factory/stages.json" or "/stages/" in relative:
                family = "legacy-stage-stamp"
        invalid_reason = ""
        zero_byte_legacy = not data and (
            bool(family)
            or relative == ".factory/stages.json"
            or bool(re.fullmatch(
                r"\.factory/(?:stories/[^/]+/)?(?:grills/(?:plan|requirements)"
                r"|grills/tasks/[^/]+|plan-approval|stages/[^/]+)\.json",
                relative,
            ))
        )
        if zero_byte_legacy:
            invalid_reason = "zero-byte legacy artifact"
        elif family and family not in {"old-hook-flag", "retired-forge-profile"}:
            try:
                invalid_reason = _legacy_json_shape_reason(
                    family, json.loads(data.decode("utf-8")),
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                invalid_reason = "legacy artifact is malformed JSON"
        reason = f"Lean-owned legacy {family}" if family else ""
        preserve = False
        if invalid_reason:
            reason = invalid_reason
        elif not family:
            if relative == ".codex/config.toml":
                reason = "current-runtime"
            elif relative.startswith(".codex/agents/"):
                name = path.name
                if name in RETIRED_FORGE_PROFILE_HASHES:
                    reason, preserve = "client-modified-profile", True
                elif name in LEAN_RETAINED_PROFILES:
                    if hashlib.sha256(data).hexdigest() in (
                            KNOWN_FORGE_RETAINED_PROFILE_HASHES.get(name, set())):
                        reason = "current-runtime-profile"
                    else:
                        reason, preserve = "client-modified-profile", True
                else:
                    reason, preserve = "client-added-profile", True
            else:
                reason, preserve = (
                    "canonical-review-output"
                    if relative.endswith("/reviews/selected.json")
                    else "current-or-project-owned"
                ), True
        entries.append({
            "path": relative, "family": family, "type": "file",
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "classification": ("invalid" if invalid_reason else
                               "eligible" if family else "excluded"),
            "reason": reason, "preserve": preserve,
            **_entry_identity(relative),
        })
    _classify_fixed_review_coverage(target, entries)
    _classify_story_fixed_review_coverage(target, entries)
    _classify_history_fixed_review_coverage(target, entries)
    return entries


def _raw_json_shape_reason(family: str, value: object) -> str:
    """Independently validate JSON recognized by the raw coverage pass."""
    if not isinstance(value, dict):
        return "legacy artifact is not a JSON object"

    def required_fields(required: dict[str, type]) -> str:
        invalid = [key for key, expected in required.items()
                   if not isinstance(value.get(key), expected)]
        return ("legacy artifact has invalid or missing field(s): "
                + ", ".join(invalid)) if invalid else ""

    if family == "grill-round":
        return required_fields({
            "generated_by": str, "questions": list, "at": str,
            "session_id": str,
        })
    if family in {
            "requirements-grill", "old-plan-grill", "old-task-grill"}:
        gate = {"old-plan-grill": "plan", "old-task-grill": "task"}.get(family)
        if gate and any(name in value for name in (
                "cold_input_sha256", "final_artifact_sha256",
                "finding_dispositions", "amendments", "artifact_delta")):
            if "rounds" in value:
                return "current grill contains retired rounds"
            required = {
                "generated_by": str, "gate": str, "verdict": str,
                "gaps": list, "contradictions": list, "resolutions": list,
                "finding_dispositions": list, "cold_input_sha256": str,
                "final_artifact_sha256": str,
            }
            invalid = [name for name, expected in required.items()
                       if not isinstance(value.get(name), expected)]
            if invalid:
                return ("current grill has invalid or missing field(s): "
                        + ", ".join(invalid))
            if value.get("gate") != gate:
                return f"current grill gate is not {gate!r}"
            if value.get("verdict") not in {"pass", "blocked"}:
                return "current grill verdict is invalid"
            if any(re.fullmatch(r"[0-9a-f]{64}", value[name]) is None
                   for name in ("cold_input_sha256", "final_artifact_sha256")):
                return "current grill has an invalid digest"
            for optional in ("amendments", "artifact_delta"):
                if optional in value and not isinstance(value[optional], list):
                    return f"current grill {optional} is invalid"
            if (value["cold_input_sha256"] != value["final_artifact_sha256"]
                    and (not value.get("amendments")
                         or "artifact_delta" not in value)):
                return "changed current grill has no amendment bridge"
            if gate == "plan":
                for field in ("issue", "input_sha256"):
                    if not isinstance(value.get(field), str) or not value[field].strip():
                        return f"current plan grill has invalid or missing {field}"
                if re.fullmatch(r"[0-9a-f]{64}", value["input_sha256"]) is None:
                    return "current plan grill has an invalid input digest"
            if gate == "task":
                task_required = {
                    "task_id": str, "input_sha256": str,
                    "task_plan_sha256": str, "inspected_refs": list,
                    "current_flow": str, "criteria_map": dict,
                    "decision": str, "new_abstractions": list,
                    "grounding_basis": str, "grounding_treeish": str,
                }
                invalid = [name for name, expected in task_required.items()
                           if not isinstance(value.get(name), expected)]
                if invalid:
                    return ("current task grill has invalid or missing field(s): "
                            + ", ".join(invalid))
                if (not value["task_id"].strip()
                        or not value["current_flow"].strip()
                        or not value["inspected_refs"]
                        or value["decision"] not in {"keep", "split", "block"}
                        or value["grounding_basis"] not in {
                            "working-tree", "stage-baseline"}
                        or any(not isinstance(item, str) or not item.strip()
                               for item in value["inspected_refs"])
                        or any(not isinstance(item, str) or not item.strip()
                               for item in value["new_abstractions"])
                        or any(not isinstance(key, str) or not key
                               or not isinstance(item, str) or not item.strip()
                               for key, item in value["criteria_map"].items())):
                    return "current task grill proof fields are invalid"
                if any(re.fullmatch(r"[0-9a-f]{64}", value[name]) is None
                       for name in ("input_sha256", "task_plan_sha256")):
                    return "current task grill has an invalid proof digest"
            return ""
        problem = required_fields({
            "generated_by": str, "gate": str, "verdict": str,
            "gaps": list, "contradictions": list, "resolutions": list,
        })
        required_gate = {
            "requirements-grill": "requirements",
            "old-plan-grill": "plan",
            "old-task-grill": "task",
        }[family]
        if not problem and value.get("gate") != required_gate:
            return f"legacy artifact gate is not {required_gate!r}"
        if (not problem and family == "old-task-grill"
                and not isinstance(value.get("rounds"), list)):
            return "legacy task grill has no rounds list"
        return problem
    if family == "manual-plan-approval":
        problem = required_fields({
            "approved_plan_sha256": str, "issue": str, "story": str,
            "approver": str, "at": str,
        })
        if (not problem and not re.fullmatch(
                r"[0-9a-f]{64}", value["approved_plan_sha256"])):
            return "legacy approval digest is not a SHA-256 identity"
        return problem
    if family == "plan-mode-marker":
        problem = required_fields({
            "generated_by": str, "path": str, "sha256": str,
            "sha256_body": str, "at": str, "session_id": str,
        })
        if (not problem and any(not re.fullmatch(r"[0-9a-f]{64}", value[key])
                                for key in ("sha256", "sha256_body"))):
            return "legacy plan-mode marker has an invalid digest"
        return problem
    if family in {"fixed-review-lens", "story-fixed-review-lens"}:
        problem = required_fields({
            "generated_by": str, "score": int,
            "summary": str, "blocking_findings": list,
            "branch_diff_digest": str,
        })
        if (not problem and (value["generated_by"] != "autoreview"
                             or isinstance(value["score"], bool)
                             or not 0 <= value["score"] <= 10
                             or not value["summary"].strip())):
            return "fixed review lens has invalid proof fields"
        if (not problem and "non_blocking_findings" in value
                and not isinstance(value["non_blocking_findings"], list)):
            return "fixed review lens has invalid non-blocking findings"
        if not problem:
            problem = _fixed_review_optional_fields_reason(value)
        if (not problem and "task_id" in value
                and not isinstance(value["task_id"], str)):
            return "fixed review task identity is invalid"
        if (not problem and not re.fullmatch(
                r"[0-9a-f]{64}", value["branch_diff_digest"])):
            return "fixed review lens has an invalid delta identity"
        if (not problem and "task_id" in value
                and SAFE_COMPONENT.fullmatch(value["task_id"]) is None):
            return "fixed review task identity is not a safe path component"
        return problem
    if family == "history-fixed-review-lens":
        problem = required_fields({
            "generated_by": str, "score": int, "summary": str,
            "blocking_findings": list, "non_blocking_findings": list,
            "aspect": str, "commit": str, "recorded_at": str,
        })
        if (not problem and (value["generated_by"] != "autoreview"
                             or isinstance(value["score"], bool)
                             or not 0 <= value["score"] <= 10
                             or not value["summary"].strip()
                             or value["aspect"] not in LEAN_LENSES
                             or not value["recorded_at"].strip())):
            return "historical fixed review has invalid proof fields"
        if not problem:
            problem = _fixed_review_optional_fields_reason(value)
        if not problem and not re.fullmatch(r"[0-9a-f]{40}", value["commit"]):
            return "historical fixed review has an invalid commit identity"
        return problem
    if family == "legacy-stage-stamp":
        records = value.get("stages") if "stages" in value else [value]
        if not isinstance(records, list) or not records:
            return "legacy stage state has no stage records"
        stamps = [record.get("local_review_stamp")
                  for record in records if isinstance(record, dict)
                  and "local_review_stamp" in record]
        if not stamps:
            return "legacy stage state has no local review stamp"
        if any(not isinstance(stamp, dict) for stamp in stamps):
            return "legacy local review stamp is not an object"
        current = ["reviewed_meaning" in stamp for stamp in stamps]
        if all(current):
            return "legacy stage state contains only current review stamps"
        if any(current):
            return "legacy stage state mixes current and legacy review stamps"
        for stamp in stamps:
            required = {
                "stage_id": str, "base_sha": str, "recorded_at": str,
                "generated_by": str,
            }
            invalid = [key for key, expected in required.items()
                       if not isinstance(stamp.get(key), expected)]
            if invalid:
                return ("legacy local review stamp has invalid or missing field(s): "
                        + ", ".join(invalid))
            if "delta_id" in stamp:
                if not isinstance(stamp["delta_id"], str):
                    return "legacy local review stamp has invalid delta identity"
            elif any(not isinstance(stamp.get(key), str) for key in (
                    "task_sha256", "brief_sha256", "product_tree_digest")):
                return "legacy local review stamp has no historical binding"
    return ""


def _raw_entry_identity(relative: str) -> dict:
    """Independently derive normalized source identity for raw coverage."""
    segments = tuple(relative.split("/"))
    identity: dict[str, object] = {"source_paths": [relative]}
    if (len(segments) > 2 and segments[0] == ".factory"
            and segments[1] in {"stories", "history"}):
        identity["story"] = segments[2]
    if len(segments) > 5 and segments[3] == "tasks":
        identity["task_id"] = segments[4]
    elif "/grills/tasks/" in relative:
        identity["task_id"] = relative.rsplit("/", 1)[-1].removesuffix(".json")
    return identity


def _raw_unique_decomposition_task(target: Path, story: str) -> str:
    """Independently resolve one task for raw pre-task-id coverage."""
    path = target.joinpath(
        ".factory", "stories", story, "decomposition.json",
    )
    _require_unlinked_path(target, path)
    if not path.is_file():
        return ""
    try:
        info = path.lstat()
        value = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or not isinstance(value, dict) or value.get("story") != story
            or not isinstance(value.get("tasks"), list)):
        return ""
    if len(value["tasks"]) != 1:
        return ""
    row = value["tasks"][0]
    return (row["id"] if isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and SAFE_COMPONENT.fullmatch(row["id"]) else "")


def _raw_classify_fixed_review_coverage(target: Path, rows: list[dict]) -> None:
    """Independently classify fixed review groups found by raw coverage."""
    from factory_lib import (
        _committed_task_marker, product_delta_digest,
        read_selected_review_generation,
    )

    def mark_invalid(group: list[dict], problem: str) -> None:
        for item in group:
            item.update(classification="invalid", reason=problem)

    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        if (row.get("family") != "fixed-review-lens"
                or row.get("classification") == "invalid"):
            continue
        segments = tuple(row["path"].split("/"))
        story = segments[2]
        path_task = segments[4] if segments[3] == "tasks" else ""
        groups.setdefault((story, path_task), []).append(row)

    resolved: dict[tuple[str, str], list[list[dict]]] = {}
    for (story, path_task), group in groups.items():
        values = [json.loads((target / row["path"]).read_text(encoding="utf-8"))
                  for row in group]
        task_ids = {value.get("task_id") for value in values
                    if "task_id" in value}
        if len(task_ids) > 1 or (task_ids and not all(
                "task_id" in value for value in values)):
            mark_invalid(group, "fixed review has invalid or mixed task identity")
            continue
        task = (next(iter(task_ids)) if task_ids else
                path_task or _raw_unique_decomposition_task(target, story))
        if not task and not path_task:
            for row in group:
                row.update(
                    classification="excluded",
                    reason="unattributed story fixed review requires a fresh review",
                    preserve=True,
                )
            continue
        if (not task or SAFE_COMPONENT.fullmatch(task) is None
                or (path_task and task != path_task)):
            mark_invalid(group, "fixed review has invalid or mixed task identity")
            continue
        source_paths = sorted(row["path"] for row in group)
        for row in group:
            row.update(story=story, task_id=task, source_paths=source_paths)
        resolved.setdefault((story, task), []).append(group)

    for (story, task), task_groups in resolved.items():
        if len(task_groups) != 1:
            for group in task_groups:
                mark_invalid(group, "fixed review is multiply bound")
            continue
        group = task_groups[0]
        values = [json.loads((target / row["path"]).read_text(encoding="utf-8"))
                  for row in group]
        lenses = {row["path"].rsplit("/", 1)[-1].removesuffix(".json")
                  for row in group}
        if lenses != set(LEAN_LENSES):
            for row in group:
                row.update(classification="excluded",
                           reason="incomplete fixed review is display-only",
                           preserve=True)
            continue
        deltas = {value["branch_diff_digest"] for value in values}
        selected = (target / ".factory" / "stories" / story / "tasks" / task
                    / "reviews" / "selected.json")
        _require_unlinked_path(target, selected)
        if (not selected.exists() and not selected.is_symlink()
                and len(deltas) != 1):
            mark_invalid(group, "sealed fixed review has conflicting delta identity")
            continue
        marker = (target / ".factory" / "stories" / story / "tasks" / task
                  / "pr-ready.json")
        _require_unlinked_path(target, marker)
        if not marker.is_file():
            if len(deltas) != 1:
                mark_invalid(group, "sealed fixed review has conflicting delta identity")
                continue
            for row in group:
                row.update(classification="eligible",
                           reason="active fixed review requires a fresh review",
                           preserve=False)
            continue
        marker_bytes = marker.read_bytes()
        try:
            marker_value = json.loads(marker_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError):
            mark_invalid(group, "sealed fixed review marker is malformed")
            continue
        if not isinstance(marker_value, dict):
            mark_invalid(group, "sealed fixed review marker is malformed")
            continue
        committed, marker_problem = _committed_task_marker(
            target, story, task, marker_value, None,
        )
        if marker_problem or committed is None:
            mark_invalid(group, "sealed fixed review marker is invalid: "
                         + (marker_problem or "not committed"))
            continue
        sealed = committed["commit"]
        expected_delta = product_delta_digest(
            target, marker_value.get("review_base_sha")
            or marker_value.get("base_main_sha", ""), sealed,
        )
        if selected.exists() or selected.is_symlink():
            generation, pointer, problems = read_selected_review_generation(
                target, story, task, expected_delta_id=expected_delta,
                sealed_commit=sealed,
            )
            if (problems or not isinstance(generation, dict)
                    or not isinstance(pointer, dict)
                    or generation.get("inspected_commit") != sealed):
                mark_invalid(group, "mixed canonical and fixed review proof: "
                             + "; ".join(
                                 problems or [
                                     "selected proof lacks exact sealed binding",
                                 ],
                             ))
                continue
        elif marker_value.get("reconciled") is True:
            for row in group:
                row.update(classification="excluded",
                           reason="active fixed review requires a fresh review",
                           preserve=True)
            continue
        else:
            if deltas != {expected_delta}:
                mark_invalid(group,
                             "sealed fixed review delta does not match its marker")
                continue
        marker_identity = {
            "path": marker.relative_to(target).as_posix(),
            "sha256": hashlib.sha256(marker_bytes).hexdigest(),
            "commit": sealed,
        }
        for row in group:
            row.update(reason="sealed complete fixed review",
                       marker_identity=marker_identity)


def _raw_classify_history_fixed_review_coverage(
        target: Path, rows: list[dict]) -> None:
    """Independently classify complete fixed triples in sealed history."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        if (row.get("family") == "history-fixed-review-lens"
                and row.get("classification") != "invalid"):
            groups.setdefault(tuple(row["path"].split("/"))[2], []).append(row)
    for story, group in groups.items():
        problem = ""
        if {row["path"].rsplit("/", 1)[-1].removesuffix(".json")
                for row in group} != set(LEAN_LENSES):
            problem = "historical fixed review is incomplete"
        run = target.joinpath(".factory", "history", story, "run.json")
        _require_unlinked_path(target, run)
        try:
            info = run.lstat()
            state = json.loads(run.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            problem = problem or "historical fixed review has no sealed story state"
        else:
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or not isinstance(state, dict)
                    or state.get("issue_key") != story
                    or state.get("phase") not in {"pr-ready", "done"}):
                problem = problem or "historical fixed review has no sealed story state"
        for row in group:
            value = json.loads((target / row["path"]).read_bytes().decode("utf-8"))
            lens = row["path"].rsplit("/", 1)[-1].removesuffix(".json")
            if value.get("aspect") != lens:
                problem = problem or "historical fixed review aspect does not match its path"
        for row in group:
            row.update(
                classification="invalid" if problem else "eligible",
                reason=problem or "sealed historical fixed review is retained",
                preserve=not problem,
                source_paths=sorted(item["path"] for item in group),
            )


def _raw_classify_story_fixed_review_coverage(
        target: Path, rows: list[dict]) -> None:
    """Independently classify complete fixed triples for shipped stories."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        if (row.get("family") == "story-fixed-review-lens"
                and row.get("classification") != "invalid"):
            groups.setdefault(tuple(row["path"].split("/"))[2], []).append(row)
    for story, group in groups.items():
        problem = ""
        if {row["path"].rsplit("/", 1)[-1].removesuffix(".json")
                for row in group} != set(LEAN_LENSES):
            problem = "story fixed review is incomplete"
        shipped = target.joinpath(".factory", "stories", story, "shipped.json")
        _require_unlinked_path(target, shipped)
        try:
            info = shipped.lstat()
            state = json.loads(shipped.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            problem = problem or "story fixed review has no sealed story state"
        else:
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or not isinstance(state, dict)
                    or state.get("story") != story
                    or state.get("phase") != "shipped"
                    or not isinstance(state.get("shipped_at"), str)
                    or not state["shipped_at"].strip()):
                problem = problem or "story fixed review has no sealed story state"
        identities = []
        for row in group:
            value = json.loads((target / row["path"]).read_bytes().decode("utf-8"))
            lens = row["path"].rsplit("/", 1)[-1].removesuffix(".json")
            if value.get("aspect") != lens:
                problem = problem or "story fixed review aspect does not match its path"
            identity = tuple(value.get(field) for field in (
                "commit", "branch_diff_digest", "brief_sha256", "review_run_id",
            ))
            if (not isinstance(identity[0], str)
                    or re.fullmatch(r"[0-9a-f]{40}", identity[0]) is None
                    or any(not isinstance(item, str)
                           or re.fullmatch(r"[0-9a-f]{64}", item) is None
                           for item in identity[1:])):
                problem = problem or "story fixed review identity is invalid"
            identities.append(identity)
        if identities and any(identity != identities[0] for identity in identities[1:]):
            problem = problem or "story fixed review identity conflicts"
        identity = (identities[0] if identities
                    and all(isinstance(item, str) for item in identities[0])
                    else ("", "", "", ""))
        story_identity = {
            "path": shipped.relative_to(target).as_posix(),
            "sha256": (hashlib.sha256(shipped.read_bytes()).hexdigest()
                       if shipped.is_file() else ""),
            "commit": identity[0], "branch_diff_digest": identity[1],
            "brief_sha256": identity[2], "review_run_id": identity[3],
        }
        for row in group:
            row.update(
                classification="invalid" if problem else "eligible",
                reason=problem or "sealed story fixed review is retained",
                preserve=not problem,
                source_paths=sorted(item["path"] for item in group),
                story_identity=story_identity,
            )


def _raw_inventory_paths(target: Path) -> list[Path]:
    """Enumerate the fixed legacy universe without following any link."""
    files: list[Path] = []

    def raw_parent(path: Path) -> list[os.DirEntry]:
        _require_unlinked_path(target, path)
        if not path.exists() and not path.is_symlink():
            return []
        try:
            info = path.lstat()
        except OSError as exc:
            fail(f"Lean raw inventory cannot inspect candidate parent {path}: {exc}")
        if (_linked_or_reparse(info)
                or not stat.S_ISDIR(info.st_mode)):
            fail(f"Lean raw inventory refuses linked or non-directory candidate parent {path}")
        try:
            return list(os.scandir(path))
        except OSError as exc:
            fail(f"Lean raw inventory cannot read candidate parent {path}: {exc}")

    def raw_exact(path: Path) -> None:
        _require_unlinked_path(target, path)
        if path.exists() or path.is_symlink():
            files.append(path)

    def raw_matches(parent: Path) -> None:
        files.extend(Path(child.path) for child in raw_parent(parent))

    raw_exact(target / ".codex/config.toml")
    raw_matches(target / ".codex/agents")
    factory = target / ".factory"
    if raw_parent(factory):
        raw_matches(factory / "grill-rounds")
        raw_matches(factory / "grills")
        raw_matches(factory / "grills/tasks")
        raw_exact(factory / "plan-approval.json")
        raw_matches(factory / "plan-mode")
        raw_exact(factory / "stages.json")
        story_entries = raw_parent(factory / "stories")
        for story_entry in story_entries:
            story = Path(story_entry.path)
            if (story_entry.is_symlink()
                    or not story_entry.is_dir(follow_symlinks=False)):
                fail(f"Lean raw inventory refuses linked or non-directory candidate parent {story}")
            raw_matches(story / "grill-rounds")
            raw_matches(story / "grills")
            raw_matches(story / "grills/tasks")
            raw_exact(story / "plan-approval.json")
            raw_matches(story / "plan-mode")
            raw_matches(story / "stages")
            raw_matches(story / "reviews")
            for task_entry in raw_parent(story / "tasks"):
                task = Path(task_entry.path)
                if (task_entry.is_symlink()
                        or not task_entry.is_dir(follow_symlinks=False)):
                    fail("Lean raw inventory refuses linked or non-directory "
                         f"candidate parent {task}")
                raw_matches(task / "reviews")
        for story_entry in raw_parent(factory / "history"):
            story = Path(story_entry.path)
            if (story_entry.is_symlink()
                    or not story_entry.is_dir(follow_symlinks=False)):
                fail("Lean raw inventory refuses linked or non-directory "
                     f"candidate parent {story}")
            raw_matches(story / "reviews")
    return sorted(set(files))


def _raw_legacy_family(relative: str, data: bytes) -> str:
    """Classify one raw candidate independently of the primary pass."""
    family = ""
    if relative == ".codex/config.toml" and b"codex_hooks = true" in data:
        family = "old-hook-flag"
    elif relative.startswith(".codex/agents/"):
        name = relative.rsplit("/", 1)[-1]
        if (name in RETIRED_FORGE_PROFILE_HASHES
                and hashlib.sha256(data).hexdigest()
                == RETIRED_FORGE_PROFILE_HASHES[name]):
            family = "retired-forge-profile"
    elif "/grill-rounds/" in relative and relative.endswith(".json"):
        family = "grill-round"
    elif relative.endswith("/grills/requirements.json") \
            or relative == ".factory/grills/requirements.json":
        family = "requirements-grill"
    elif (relative.endswith("/grills/plan.json")
          or relative == ".factory/grills/plan.json"):
        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = None
        cold_fields = {
            "cold_input_sha256", "final_artifact_sha256",
            "finding_dispositions", "amendments", "artifact_delta",
        }
        if (not isinstance(decoded, dict)
                or "cold_input_sha256" not in decoded
                or (cold_fields.intersection(decoded)
                    and _raw_json_shape_reason("old-plan-grill", decoded))):
            family = "old-plan-grill"
    elif "/grills/tasks/" in relative and relative.endswith(".json"):
        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = None
        cold_fields = {
            "cold_input_sha256", "final_artifact_sha256",
            "finding_dispositions", "amendments", "artifact_delta",
        }
        if (not isinstance(decoded, dict) or "rounds" in decoded
                or "cold_input_sha256" not in decoded
                or (cold_fields.intersection(decoded)
                    and _raw_json_shape_reason("old-task-grill", decoded))):
            family = "old-task-grill"
    elif relative.endswith("/plan-approval.json"):
        try:
            approval = json.loads(data.decode("utf-8")) if data else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            approval = None
        native_fields = {
            "approved_plan_sha256", "approved_by", "approved_at", "runtime",
            "session_id", "event_id", "plan_kind", "story", "task",
        }
        if (not isinstance(approval, dict)
                or not native_fields.issubset(approval)
                or approval.get("runtime") not in {"claude", "codex"}
                or approval.get("plan_kind") not in {"story", "task"}
                or approval.get("approved_by") != {
                    "claude": "human-via-Claude",
                    "codex": "human-via-Codex",
                }.get(approval.get("runtime"))
                or any(not isinstance(approval.get(field), str)
                       or not approval[field].strip()
                       for field in ("approved_at", "session_id", "event_id",
                                     "story"))
                or (approval.get("plan_kind") == "story"
                    and approval.get("task") != "")
                or (approval.get("plan_kind") == "task"
                    and (not isinstance(approval.get("task"), str)
                         or not approval["task"].strip()))
                or re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(approval.get("approved_plan_sha256") or ""),
                ) is None):
            family = "manual-plan-approval"
    elif "/plan-mode/" in relative and relative.endswith(".json"):
        family = "plan-mode-marker"
    elif re.fullmatch(
            r"\.factory/stories/[^/]+/reviews/"
            r"(?:quality|performance|security)\.json", relative):
        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = None
        family = ("story-fixed-review-lens" if isinstance(decoded, dict)
                  and {"aspect", "commit", "brief_sha256", "review_run_id"}
                  .issubset(decoded) else "fixed-review-lens")
    elif re.fullmatch(
            r"\.factory/stories/[^/]+/tasks/[^/]+/reviews/"
            r"(?:quality|performance|security)\.json", relative):
        family = "fixed-review-lens"
    elif re.fullmatch(
            r"\.factory/history/[^/]+/reviews/"
            r"(?:quality|performance|security)\.json", relative):
        family = "history-fixed-review-lens"
    elif relative == ".factory/stages.json" or "/stages/" in relative:
        try:
            stage_value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            stage_value = None
        if (isinstance(stage_value, dict) and "stages" in stage_value
                and not isinstance(stage_value["stages"], list)):
            return "legacy-stage-stamp"
        stage_records = stage_value.get("stages") \
            if isinstance(stage_value, dict) and "stages" in stage_value \
            else [stage_value]
        stage_stamps = [
            record.get("local_review_stamp") for record in stage_records
            if isinstance(record, dict) and "local_review_stamp" in record
        ]
        if stage_stamps and not all(
                isinstance(stamp, dict) and "reviewed_meaning" in stamp
                for stamp in stage_stamps):
            family = "legacy-stage-stamp"
    if not data and not family:
        if (relative.endswith("/grills/plan.json")
                or relative == ".factory/grills/plan.json"):
            family = "old-plan-grill"
        elif "/grills/tasks/" in relative and relative.endswith(".json"):
            family = "old-task-grill"
        elif (relative.endswith("/plan-approval.json")
              or relative == ".factory/plan-approval.json"):
            family = "manual-plan-approval"
        elif relative == ".factory/stages.json" or "/stages/" in relative:
            family = "legacy-stage-stamp"
    return family


def lean_raw_inventory(target: Path) -> list[dict]:
    """Build the independent classified inventory from the raw no-follow walk."""
    rows: list[dict] = []
    paths = _raw_inventory_paths(target)
    migration_temps = _bound_lean_temporary_paths(
        target, {path.relative_to(target).as_posix() for path in paths},
    )
    for path in paths:
        relative = path.relative_to(target).as_posix()
        try:
            info = path.lstat()
        except OSError as exc:
            fail(f"Lean raw inventory cannot inspect candidate {relative}: {exc}")
        if _linked_or_reparse(info):
            fail(f"Lean raw inventory refuses linked or non-regular candidate {relative}")
        if stat.S_ISDIR(info.st_mode):
            if (relative.endswith("/grills/tasks")
                    or relative.endswith("/reviews/generations")):
                rows.append({
                    "path": relative, "family": "", "type": "directory",
                    "classification": "excluded",
                    "reason": ("canonical-review-output"
                               if relative.endswith("/reviews/generations")
                               else "current-container"),
                    "preserve": True,
                    **_raw_entry_identity(relative),
                })
                continue
            fail(f"Lean raw inventory refuses unexpected directory candidate {relative}")
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            fail(f"Lean raw inventory refuses linked or non-regular candidate {relative}")
        data = path.read_bytes()
        if relative in migration_temps:
            rows.append({
                "path": relative, "family": "lean-migration-temporary",
                "type": "file", "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "classification": "excluded",
                "reason": "manifest-bound interrupted migration temporary",
                "preserve": False, **_raw_entry_identity(relative),
            })
            continue
        family = _raw_legacy_family(relative, data)
        invalid_reason = ""
        zero_byte_legacy = not data and (
            bool(family)
            or relative == ".factory/stages.json"
            or bool(re.fullmatch(
                r"\.factory/(?:stories/[^/]+/)?(?:grills/(?:plan|requirements)"
                r"|grills/tasks/[^/]+|plan-approval|stages/[^/]+)\.json",
                relative,
            ))
        )
        if zero_byte_legacy:
            invalid_reason = "zero-byte legacy artifact"
        elif family and family not in {"old-hook-flag", "retired-forge-profile"}:
            try:
                invalid_reason = _raw_json_shape_reason(
                    family, json.loads(data.decode("utf-8")),
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                invalid_reason = "legacy artifact is malformed JSON"
        reason = f"Lean-owned legacy {family}" if family else ""
        preserve = False
        if invalid_reason:
            reason = invalid_reason
        elif not family:
            if relative == ".codex/config.toml":
                reason = "current-runtime"
            elif relative.startswith(".codex/agents/"):
                name = path.name
                if name in RETIRED_FORGE_PROFILE_HASHES:
                    reason, preserve = "client-modified-profile", True
                elif name in LEAN_RETAINED_PROFILES:
                    if hashlib.sha256(data).hexdigest() in (
                            KNOWN_FORGE_RETAINED_PROFILE_HASHES.get(name, set())):
                        reason = "current-runtime-profile"
                    else:
                        reason, preserve = "client-modified-profile", True
                else:
                    reason, preserve = "client-added-profile", True
            else:
                reason, preserve = (
                    "canonical-review-output"
                    if relative.endswith("/reviews/selected.json")
                    else "current-or-project-owned"
                ), True
        rows.append({
            "path": relative, "family": family, "type": "file",
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "classification": ("invalid" if invalid_reason else
                               "eligible" if family else "excluded"),
            "reason": reason, "preserve": preserve,
            **_raw_entry_identity(relative),
        })
    _raw_classify_fixed_review_coverage(target, rows)
    _raw_classify_story_fixed_review_coverage(target, rows)
    _raw_classify_history_fixed_review_coverage(target, rows)
    return rows


def _inventory_digest(entries: list[dict]) -> str:
    identity_entries = [
        entry for entry in entries
        if entry.get("reason") != "canonical-review-output"
    ]
    return hashlib.sha256(json.dumps(
        identity_entries, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def _resume_converted_outputs(migration: dict) -> dict[str, str] | None:
    """Return the authenticated stage bytes recorded before an interruption."""
    raw = migration.get("converted_outputs")
    rows = [] if raw is None else raw
    if not isinstance(rows, list):
        return None
    result: dict[str, str] = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"path", "sha256"}
                or not isinstance(row.get("path"), str)
                or not isinstance(row.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None):
            return None
        if row["path"] in result:
            return None
        result[row["path"]] = row["sha256"]
    return result


def _profile_replacement_hashes(
        migration: dict,
) -> dict[str, str] | None:
    """Read the authenticated current-profile bytes bound to a migration."""
    raw = migration.get("profile_replacements")
    if raw is None:
        return {}
    if not isinstance(raw, list):
        return None
    result: dict[str, str] = {}
    for row in raw:
        if (not isinstance(row, dict) or set(row) != {"path", "sha256"}
                or not isinstance(row.get("path"), str)
                or not isinstance(row.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None):
            return None
        parts = Path(row["path"]).parts
        if (len(parts) != 3 or parts[:2] != (".codex", "agents")
                or SAFE_COMPONENT.fullmatch(parts[2]) is None
                or parts[2] not in RETIRED_FORGE_PROFILE_HASHES
                or row["path"] in result):
            return None
        result[row["path"]] = row["sha256"]
    return result


def _profile_replacement_candidates(
        harness: Path, target: Path, migration: dict | None = None,
) -> list[tuple[Path, Path]]:
    """Return exact retired-profile replacements safe for this migration."""
    expected = {}
    if migration is not None:
        expected = _profile_replacement_hashes(migration)
        if expected is None:
            fail("Lean migration profile replacement metadata is malformed")
    rows: list[tuple[Path, Path]] = []
    if expected:
        candidates = [
            (harness / relative, target / relative)
            for relative in expected
        ]
    else:
        agents = harness / ".codex" / "agents"
        candidates = []
        if agents.is_dir() and not agents.is_symlink():
            for source in agents.iterdir():
                if source.name not in RETIRED_FORGE_PROFILE_HASHES:
                    continue
                candidates.append((source, target / ".codex" / "agents" / source.name))
    for source, destination in candidates:
        relative = destination.relative_to(target).as_posix()
        if (source.is_symlink() or not source.is_file()):
            fail(f"Lean migration current profile source is not a regular file: {relative}")
        source_sha256 = _profile_replacement_source_digest(source)
        expected_sha256 = expected.get(relative)
        if expected_sha256 is not None and source_sha256 != expected_sha256:
            fail(f"Lean migration current profile source changed: {relative}")
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file():
                if expected_sha256 is not None:
                    fail(f"Lean migration current profile destination is linked: {relative}")
                continue
            destination_sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()
            allowed = {RETIRED_FORGE_PROFILE_HASHES[source.name], source_sha256}
            if destination_sha256 not in allowed:
                if expected_sha256 is not None:
                    fail(f"Lean migration current profile destination was modified: {relative}")
                continue
            if expected_sha256 is None and destination_sha256 != RETIRED_FORGE_PROFILE_HASHES[source.name]:
                continue
        elif expected_sha256 is None:
            continue
        rows.append((source, destination))
    if expected:
        found = {
            destination.relative_to(target).as_posix() for _source, destination in rows
        }
        if found != set(expected):
            fail("Lean migration current profile replacement set changed")
    return rows


def _profile_replacement_source_digest(source: Path) -> str:
    """Hash one harness profile while keeping source drift testable."""
    return hashlib.sha256(source.read_bytes()).hexdigest()


def _resume_stage_bytes_match(target: Path, path: str, expected: str) -> bool:
    candidate = target / path
    try:
        return (candidate.is_file() and not candidate.is_symlink()
                and hashlib.sha256(candidate.read_bytes()).hexdigest() == expected)
    except OSError:
        return False


def _revalidate_lean_inventory(target: Path, migration: dict) -> None:
    """Refuse source, classification, or marker drift before pointer publish."""
    primary = lean_primary_inventory(target)
    raw = lean_raw_inventory(target)
    if primary != raw:
        fail("Lean migration independent raw inventory changed before publication")
    replaced_paths = {
        entry["path"] for entry in migration["entries"]
        if (entry.get("family") in {"old-hook-flag", "retired-forge-profile"}
            or entry["path"] in LEAN_RUNTIME_PATHS
            or entry.get("reason") == "current-runtime-profile")
    }
    retired_review_paths = {
        path for sentinel in migration.get("review_sentinels") or []
        for path in sentinel.get("source_paths") or []
    }

    def stable(entries: list[dict]) -> list[dict]:
        return [
            entry for entry in entries
            if entry["path"] not in replaced_paths
            and entry["path"] not in retired_review_paths
            and entry.get("reason") not in {
                "canonical-review-output",
                "manifest-bound interrupted migration temporary",
            }
        ]

    current = {
        entry["path"]: entry for entry in stable(primary)
    }
    expected = {
        entry["path"]: entry for entry in stable(migration["entries"])
    }
    converted = _resume_converted_outputs(migration)
    if converted is None:
        fail("Lean migration converted-output lineage is malformed")
    if set(current) - set(expected):
        fail("Lean migration inventory changed before review publication")
    for path, original in expected.items():
        live = current.get(path)
        if live == original:
            continue
        if (migration.get("resume") and
                original.get("classification") == "eligible"
                and original.get("family") == "legacy-stage-stamp"
                and path in converted
                and live is not None
                and live.get("classification") == "excluded"
                and _resume_stage_bytes_match(target, path, converted[path])):
            continue
        if (migration.get("resume")
                and original.get("classification") == "eligible"
                and original.get("family") != "legacy-stage-stamp"
                and original.get("preserve") is False
                and live is None
                and not (target / path).exists()
                and not (target / path).is_symlink()):
            continue
        if (migration.get("resume")
                and original.get("family") == "fixed-review-lens"
                and original.get("preserve") is False
                and live is not None
                and live.get("classification") == "excluded"
                and live.get("reason") == "incomplete fixed review is display-only"
                and live.get("sha256") == original.get("sha256")):
            continue
        fail("Lean migration inventory changed before review publication")
    candidates, sentinels = _fixed_review_plan(target, migration)
    expected_candidates = migration.get("review_candidates", [])
    expected_sentinels = migration.get("review_sentinels", [])
    candidate_by_task = {
        (candidate[0]["story"], candidate[0]["task_id"]): candidate
        for candidate in candidates
    }
    sentinel_by_task = {
        (sentinel["output"]["story"], sentinel["output"]["task_id"]): sentinel
        for sentinel in sentinels
    }
    expected_candidate_by_task = {
        (candidate[0]["story"], candidate[0]["task_id"]): candidate
        for candidate in expected_candidates
    }
    expected_sentinel_by_task = {
        (sentinel["output"]["story"], sentinel["output"]["task_id"]): sentinel
        for sentinel in expected_sentinels
    }
    if (set(candidate_by_task) | set(sentinel_by_task)
            != set(expected_candidate_by_task) | set(expected_sentinel_by_task)):
        fail("Lean migration selected review sentinel changed before publication")
    for key, expected in expected_sentinel_by_task.items():
        if sentinel_by_task.get(key) != expected:
            fail("Lean migration selected review sentinel changed before publication")
    from factory_lib import review_generation_bytes, review_generation_id
    for key, (candidate, paths) in expected_candidate_by_task.items():
        if candidate_by_task.get(key) == (candidate, paths):
            continue
        sentinel = sentinel_by_task.get(key)
        generation_id = review_generation_id(candidate)
        generation = {**candidate, "generation_id": generation_id}
        expected_output = {
            "story": candidate["story"], "task_id": candidate["task_id"],
            "generation_id": generation_id,
            "generation_sha256": hashlib.sha256(
                review_generation_bytes(generation),
            ).hexdigest(),
        }
        if (not sentinel or sentinel.get("output") != expected_output
                or sentinel.get("sealed_commit")
                != candidate["upgrade"]["sealed_commit"]
                or sentinel.get("source_paths")
                != [path.relative_to(target).as_posix() for path in paths]):
            fail("Lean migration sealed review identity changed before publication")


def _runtime_inventory(target: Path) -> list[dict]:
    paths = [target / relative for relative in LEAN_RUNTIME_PATHS]
    return [{"path": path.relative_to(target).as_posix(),
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in paths if path.is_file() and not path.is_symlink()]


def _manifest_content_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def _is_original_empty_completion(saved: dict) -> bool:
    legacy_keys = {
        "generated_by", "version", "input_inventory_digest", "output_digest",
        "installed_runtime_digest", "entries", "recorded_at", "completed_at",
    }
    empty_digest = _inventory_digest([])
    return (
        set(saved) == legacy_keys
        and saved.get("generated_by") == "upgrade"
        and saved.get("version") == LEAN_MIGRATION_VERSION
        and isinstance(saved.get("recorded_at"), str)
        and bool(saved["recorded_at"].strip())
        and isinstance(saved.get("completed_at"), str)
        and bool(saved["completed_at"].strip())
        and saved.get("entries") == []
        and saved.get("input_inventory_digest") == empty_digest
        and saved.get("output_digest") == empty_digest
        and saved.get("installed_runtime_digest")
        == LEAN_ORIGINAL_EMPTY_RUNTIME_DIGEST
    )


def _validate_completed_manifest(
        target: Path, saved: dict, *, preserve_prior_output_identity: bool = False,
) -> None:
    from factory_lib import (
        _committed_task_marker, product_delta_digest,
        read_selected_review_generation, validate_review_document,
    )
    legacy_keys = {
        "generated_by", "version", "input_inventory_digest", "output_digest",
        "installed_runtime_digest", "entries", "recorded_at", "completed_at",
    }
    legacy_empty_completion = set(saved) == legacy_keys
    if legacy_empty_completion:
        if not _is_original_empty_completion(saved):
            fail("Lean migration completed manifest is incomplete or tampered")
        return
    prior = saved.get("prior_completion")
    prior_digest = saved.get("prior_completion_digest")
    if (prior is None) != (prior_digest is None):
        fail("Lean migration completed manifest has incomplete prior completion")
    if prior is not None:
        if (not isinstance(prior, dict)
                or not isinstance(prior_digest, str)
                or _manifest_content_digest(prior) != prior_digest
                or not prior.get("completed_at")):
            fail("Lean migration completed manifest prior completion is tampered")
        _validate_completed_manifest(
            target, prior, preserve_prior_output_identity=True,
        )
    installed_runtime = saved.get("installed_runtime")
    preserved_entries = saved.get("preserved_entries")
    if (saved.get("generated_by") != "upgrade"
            or saved.get("version") != LEAN_MIGRATION_VERSION
            or not isinstance(saved.get("recorded_at"), str)
            or not saved["recorded_at"].strip()
            or not isinstance(saved.get("completed_at"), str)
            or not saved["completed_at"].strip()
            or not isinstance(saved.get("entries"), list)
            or not isinstance(installed_runtime, list)
            or not isinstance(preserved_entries, list)
            or any(not isinstance(row, dict)
                   or set(row) != {"path", "sha256"}
                   or not isinstance(row["path"], str)
                   or not isinstance(row["sha256"], str)
                   or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                   for row in installed_runtime)
            or len(installed_runtime) != len(LEAN_RUNTIME_PATHS)
            or {row["path"] for row in installed_runtime}
            != set(LEAN_RUNTIME_PATHS)
            or saved.get("input_inventory_digest")
            != _inventory_digest(saved.get("entries") or [])
            or saved.get("installed_runtime_digest")
            != _inventory_digest(installed_runtime)
            or any(entry not in saved["entries"]
                   or not (entry.get("preserve") is True
                           or entry.get("family") == "fixed-review-lens")
                   for entry in preserved_entries
                   if isinstance(entry, dict))
            or any(not isinstance(entry, dict) for entry in preserved_entries)):
        fail("Lean migration completed manifest is incomplete or tampered")
    converted_outputs = saved.get("converted_outputs")
    if converted_outputs is None and not any(
            entry.get("family") == "legacy-stage-stamp"
            for entry in saved.get("entries") or []):
        converted_outputs = []
    if (not isinstance(converted_outputs, list)
            or any(not isinstance(row, dict) or set(row) != {"path", "sha256"}
                   or not isinstance(row["path"], str)
                   or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None
                   for row in converted_outputs)):
        fail("Lean migration completed manifest has invalid converted outputs")
    converted_paths = [row["path"] for row in converted_outputs]
    expected_converted = [
        entry["path"] for entry in saved["entries"]
        if entry.get("classification") == "eligible"
        and entry.get("family") == "legacy-stage-stamp"
    ]
    if (len(converted_paths) != len(set(converted_paths))
            or sorted(converted_paths) != sorted(expected_converted)):
        fail("Lean migration completed manifest converted-output lineage is tampered")
    for row in converted_outputs:
        _require_unlinked_path(target, target / row["path"])

    outputs = saved.get("outputs")
    if not isinstance(outputs, list):
        fail("Lean migration completed manifest has no durable output inventory")
    for row in outputs:
        if not isinstance(row, dict) or set(row) != {
                "story", "task_id", "generation_id", "generation_sha256"}:
            fail("Lean migration completed manifest output is malformed")
        if (not all(isinstance(row[field], str) and row[field]
                    for field in row)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", row["story"])
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", row["task_id"])
                or not re.fullmatch(r"[0-9a-f]{64}", row["generation_id"])
                or not re.fullmatch(r"[0-9a-f]{64}", row["generation_sha256"])):
            fail("Lean migration completed manifest output identity is malformed")
        root = (target / ".factory" / "stories" / row["story"] / "tasks"
                / row["task_id"] / "reviews")
        generation_path = root / "generations" / f"{row['generation_id']}.json"
        selection_path = root / "selected.json"
        _require_unlinked_path(target, generation_path)
        _require_unlinked_path(target, selection_path)
        try:
            generation_bytes = generation_path.read_bytes()
            generation = json.loads(generation_bytes)
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
            validate_review_document(target, generation)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SystemExit) as exc:
            fail(f"Lean migration durable review output is invalid: {exc}")
        marker_data = load_json(root.parent / "pr-ready.json", default={})
        historical_identity_ok = (
            generation.get("generation_id") == row["generation_id"]
            and generation.get("story") == row["story"]
            and generation.get("task_id") == row["task_id"]
            and hashlib.sha256(generation_bytes).hexdigest()
            == row["generation_sha256"]
        )
        if not historical_identity_ok:
            fail("Lean migration durable review output identity is tampered")
        committed, marker_problem = _committed_task_marker(
            target, row["story"], row["task_id"], marker_data, None,
        )
        if marker_problem or committed is None:
            fail("Lean migration durable review output marker is invalid")
        expected_delta = None if preserve_prior_output_identity else product_delta_digest(
            target, marker_data.get("review_base_sha")
            or marker_data.get("base_main_sha", ""), committed["commit"],
        )
        selected, pointer, problems = read_selected_review_generation(
            target, row["story"], row["task_id"],
            expected_delta_id=expected_delta, sealed_commit=committed["commit"],
        )
        if (problems or not isinstance(selected, dict)
                or not isinstance(pointer, dict)
                or selected.get("inspected_commit") != committed["commit"]
                or pointer.get("generation_id") != row["generation_id"]
                or pointer.get("generation_sha256")
                != row["generation_sha256"]):
            fail("Lean migration durable review output lacks exact sealed binding")
    expected_output = hashlib.sha256(json.dumps(
        outputs, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    if saved.get("output_digest") != expected_output:
        fail("Lean migration completed output digest is tampered")


def _prepare_review_outputs(target: Path, migration: dict) -> None:
    from factory_lib import (
        review_generation_bytes, review_generation_id, validate_review_document,
    )
    prepared = []
    with tempfile.TemporaryDirectory(prefix="forge-lean-preflight-") as temporary:
        build = Path(temporary)
        for index, (candidate, _sources) in enumerate(
                migration.get("review_candidates") or []):
            validate_review_document(target, candidate, allow_missing_generation_id=True)
            generation = {**candidate, "generation_id": review_generation_id(candidate)}
            validate_review_document(target, generation)
            body = review_generation_bytes(generation)
            staged = build / f"{index}-{generation['generation_id']}.json"
            staged.write_bytes(body)
            if staged.read_bytes() != body:
                fail("Lean migration temporary review readback differs")
            validate_review_document(target, json.loads(staged.read_text(encoding="utf-8")))
            reviews = (target / ".factory" / "stories" / candidate["story"]
                       / "tasks" / candidate["task_id"] / "reviews")
            generation_path = reviews / "generations" / f"{generation['generation_id']}.json"
            selection_path = reviews / "selected.json"
            for path in (generation_path, selection_path):
                _require_unlinked_path(target, path)
                assert_target_file_destination(target, path)
            already_published = _exact_review_output_exists(
                target, candidate, generation["generation_id"], body,
            )
            prepared.append({
                "candidate": candidate, "generation_id": generation["generation_id"],
                "generation_sha256": hashlib.sha256(body).hexdigest(),
                "already_published": already_published,
            })
    manifest = target / ".factory" / "migrations" / f"{LEAN_MIGRATION_VERSION}.json"
    _require_unlinked_path(target, manifest)
    assert_target_file_destination(target, manifest)
    migration["prepared_reviews"] = prepared


def preflight_lean_migration(target: Path) -> dict | None:
    original_manifest = (
        target / ".factory" / "migrations" / f"{LEAN_MIGRATION_VERSION}.json"
    )
    supplemental_manifest = original_manifest.with_name(LEAN_MIGRATION_SUPPLEMENT)
    _require_unlinked_path(target, original_manifest)
    _require_unlinked_path(target, supplemental_manifest)
    manifest = original_manifest
    if supplemental_manifest.exists() or supplemental_manifest.is_symlink():
        if not original_manifest.is_file():
            fail("Lean migration supplement has no durable original completion")
        original = load_json(original_manifest, default={})
        _validate_completed_manifest(target, original)
        if not _is_original_empty_completion(original):
            fail("Lean migration supplement does not follow the original empty completion")
        manifest = supplemental_manifest
    primary = lean_primary_inventory(target)
    raw = lean_raw_inventory(target)
    if primary != raw:
        fail("Lean migration independent raw inventory does not exactly match primary classification")
    for entry in primary:
        if entry.get("classification") == "invalid":
            fail(f"Lean migration found invalid {entry['family']} input "
                 f"{entry['path']}: {entry['reason']}")
        if entry.get("classification") != "eligible":
            continue
        if entry["family"] in {"old-hook-flag", "retired-forge-profile"}:
            continue
        try:
            value = json.loads((target / entry["path"]).read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            fail(f"Lean migration found malformed {entry['family']} input "
                 f"{entry['path']}: {exc}")
        if not isinstance(value, dict):
            fail(f"Lean migration found malformed {entry['family']} input "
                 f"{entry['path']}: expected a JSON object")
    if manifest.exists() or manifest.is_symlink():
        _require_single_link_manifest(target, manifest)
        saved = load_json(manifest, default={})
        if not isinstance(saved, dict):
            fail("Lean migration manifest must be a JSON object")
        if saved.get("version") != LEAN_MIGRATION_VERSION:
            fail("Lean migration found an unequal partial retry; restore or complete the original checkout")
        if saved.get("completed_at"):
            non_proof_families = {
                "old-hook-flag", "retired-forge-profile",
            }
            supplemental_families = {
                entry.get("family") for entry in primary
                if entry.get("classification") == "eligible"
            } - non_proof_families
            preserve_prior = (
                manifest == supplemental_manifest
                and any(entry.get("classification") == "eligible"
                        and entry.get("family") in supplemental_families
                        for entry in primary)
            )
            _validate_completed_manifest(
                target, saved,
                preserve_prior_output_identity=preserve_prior,
            )
            eligible_current = [
                entry for entry in primary
                if entry.get("classification") == "eligible"
            ]
            if (_is_original_empty_completion(saved)
                    and any(entry.get("family") in non_proof_families
                            for entry in eligible_current)):
                fail(
                    "Lean migration original-empty supplement refuses non-proof "
                    "runtime/profile inputs"
                )
            if (_is_original_empty_completion(saved)
                    and eligible_current):
                migration = {
                    "entries": primary,
                    "input_inventory_digest": _inventory_digest(primary),
                    "manifest_name": LEAN_MIGRATION_SUPPLEMENT,
                    "prior_completion": saved,
                    "prior_completion_digest": _manifest_content_digest(saved),
                }
                (migration["review_candidates"],
                 migration["review_sentinels"]) = _fixed_review_plan(
                    target, migration,
                )
                _prepare_review_outputs(target, migration)
                return migration
            output_paths = {
                f".factory/stories/{row['story']}/tasks/{row['task_id']}"
                "/reviews/selected.json"
                for row in saved.get("outputs") or []
            } | {
                f".factory/stories/{row['story']}/tasks/{row['task_id']}"
                "/reviews/generations"
                for row in saved.get("outputs") or []
            }
            output_paths.update(
                row["path"] for row in saved.get("converted_outputs") or []
            )
            current_fixed = [
                entry for entry in primary
                if entry.get("family") == "fixed-review-lens"
                and entry["path"] not in output_paths
            ]
            current_story_paths = {
                entry["path"] for entry in primary
                if entry.get("family") == "story-fixed-review-lens"
            }
            saved_fixed = [
                entry for entry in saved.get("preserved_entries") or []
                if entry.get("family") == "fixed-review-lens"
                and entry.get("path") not in current_story_paths
                and entry.get("path") not in output_paths
            ]
            preserved_paths = {
                entry.get("path") for entry in saved.get("preserved_entries") or []
                if isinstance(entry, dict) and isinstance(entry.get("path"), str)
            }
            newly_retired = [
                entry for entry in primary
                if entry.get("classification") == "eligible"
                and entry["path"] not in output_paths
                and entry["path"] not in preserved_paths
            ]
            if (manifest == supplemental_manifest
                    and current_fixed == saved_fixed
                    and newly_retired
                    and all(entry.get("family") in supplemental_families
                            for entry in newly_retired)):
                migration = {
                    "entries": primary,
                    "input_inventory_digest": _inventory_digest(primary),
                    "manifest_name": LEAN_MIGRATION_SUPPLEMENT,
                    "extend_completed_sha256": hashlib.sha256(
                        manifest.read_bytes(),
                    ).hexdigest(),
                    "prior_completion": saved,
                    "prior_completion_digest": _manifest_content_digest(saved),
                }
                (migration["review_candidates"],
                 migration["review_sentinels"]) = _fixed_review_plan(
                    target, migration,
                )
                _prepare_review_outputs(target, migration)
                return migration
            if current_fixed != saved_fixed or newly_retired:
                fail("Lean migration found an unequal partial retry; restore or complete the original checkout")
            return None
        profile_replacements = _profile_replacement_hashes(saved)
        if profile_replacements is None:
            fail("Lean migration profile replacement metadata is malformed")
        if profile_replacements:
            _profile_replacement_candidates(repo_root(), target, saved)
        saved_identity = {
            entry["path"]: entry for entry in saved.get("entries") or []
            if isinstance(entry, dict)
            and entry.get("reason") not in {
                "canonical-review-output",
                "manifest-bound interrupted migration temporary",
            }
        }
        primary_identity = {
            entry["path"]: entry for entry in primary
            if entry.get("reason") not in {
                "canonical-review-output",
                "manifest-bound interrupted migration temporary",
            }
        }
        monotonic = True
        converted = _resume_converted_outputs(saved)
        if converted is None:
            fail("Lean migration converted-output lineage is malformed")
        for path, current in primary_identity.items():
            original = saved_identity.get(path)
            if current == original:
                continue
            if (original is not None
                    and original.get("classification") == "eligible"
                    and current.get("classification") == "excluded"):
                if (original.get("family") == "legacy-stage-stamp"
                        and path in converted
                        and _resume_stage_bytes_match(
                            target, path, converted[path],
                        )):
                    continue
                if (original.get("family") == "fixed-review-lens"
                        and current.get("sha256") == original.get("sha256")):
                    continue
                if (original.get("family") == "retired-forge-profile"
                        and path in profile_replacements
                        and current.get("sha256") == profile_replacements[path]):
                    continue
                if path in LEAN_RUNTIME_PATHS:
                    continue
            monotonic = False
            break
        for path, original in saved_identity.items():
            if path in primary_identity:
                continue
            if original.get("classification") == "eligible":
                # A converted stage must still be present with the exact
                # durable bytes recorded before the interruption.  The
                # ordinary deletion exception applies only to an inventoried
                # source that the migration owns and removes; preserved
                # eligible inputs and converted stages cannot disappear.
                if (original.get("family") != "legacy-stage-stamp"
                        and original.get("preserve") is False
                        and not (target / path).exists()
                        and not (target / path).is_symlink()):
                    continue
                monotonic = False
                break
            monotonic = False
            break
        if not monotonic:
            fail("Lean migration found an unequal partial retry; restore or complete the original checkout")
        migration = {**saved, "resume": True, "manifest_name": manifest.name}
        (migration["review_candidates"],
         migration["review_sentinels"]) = _fixed_review_plan(target, migration)
        _prepare_review_outputs(target, migration)
        return migration
    migration = {"entries": primary,
                 "input_inventory_digest": _inventory_digest(primary)}
    (migration["review_candidates"],
     migration["review_sentinels"]) = _fixed_review_plan(target, migration)
    _prepare_review_outputs(target, migration)
    return migration


def _fixed_review_candidates(
        target: Path, migration: dict,
) -> list[tuple[dict, list[Path]]]:
    candidates, _sentinels = _fixed_review_plan(target, migration)
    return candidates


def _fixed_review_plan(
        target: Path, migration: dict,
) -> tuple[list[tuple[dict, list[Path]]], list[dict]]:
    from factory_lib import (
        _committed_task_marker, product_delta_digest,
        read_selected_review_generation, validate_payload,
        validate_review_document,
    )
    invalid = [entry for entry in migration["entries"]
               if entry.get("family") == "fixed-review-lens"
               and entry.get("classification") == "invalid"]
    if invalid:
        fail("Lean migration found invalid fixed-review-lens input "
             f"{invalid[0]['path']}: {invalid[0]['reason']}")
    grouped: dict[tuple[str, str], list[dict]] = {}
    for entry in migration["entries"]:
        if (entry.get("classification") != "eligible"
                or entry["family"] != "fixed-review-lens"):
            continue
        parts = Path(entry["path"]).parts
        story = parts[2]
        task = parts[4] if parts[3] == "tasks" else ""
        grouped.setdefault((story, task), []).append(entry)
    candidates = []
    sentinels = []
    for (story, path_task), entries in sorted(grouped.items()):
        source_paths = [target / entry["path"] for entry in entries]
        missing_sources = [
            path for path in source_paths
            if not path.exists() and not path.is_symlink()
        ]
        if missing_sources:
            if not migration.get("resume"):
                fail(f"fixed review input {missing_sources[0]} disappeared")
            task_ids = {str(entry.get("task_id") or "") for entry in entries}
            if len(task_ids) != 1 or not next(iter(task_ids)):
                fail(f"sealed fixed review {story} cannot identify exactly one task")
            task = next(iter(task_ids))
            expected = [
                row for row in migration.get("outputs") or []
                if row.get("story") == story and row.get("task_id") == task
            ]
            marker = (target / ".factory" / "stories" / story / "tasks" / task
                      / "pr-ready.json")
            if not expected:
                if (marker.exists() or marker.is_symlink()
                        or any(entry.get("preserve") is not False
                               for entry in entries)):
                    fail(f"active fixed review {story}/{task} cannot resume partial retirement")
                reviews = marker.parent / "reviews"
                generations = reviews / "generations"
                _require_unlinked_path(target, generations)
                if ((reviews / "selected.json").exists()
                        or (reviews / "selected.json").is_symlink()
                        or (generations.exists() and any(generations.iterdir()))):
                    fail(f"active fixed review {story}/{task} cannot resume with durable output")
                for entry, path in zip(entries, source_paths):
                    if path in missing_sources:
                        continue
                    if (path.is_symlink() or not path.is_file()
                            or hashlib.sha256(path.read_bytes()).hexdigest()
                            != entry["sha256"]):
                        fail(f"fixed review input {entry['path']} changed during resume")
                continue
            marker_data = load_json(marker, default={})
            committed, marker_problem = _committed_task_marker(
                target, story, task, marker_data, None,
            )
            if marker_problem or committed is None or len(expected) != 1:
                fail(f"sealed fixed review {story}/{task} cannot resume: "
                     f"{marker_problem or 'durable output is missing'}")
            sealed = committed["commit"]
            expected_delta = product_delta_digest(
                target, marker_data.get("review_base_sha")
                or marker_data.get("base_main_sha", ""), sealed,
            )
            generation, selection, problems = read_selected_review_generation(
                target, story, task, expected_delta_id=expected_delta,
                sealed_commit=sealed,
            )
            output = expected[0]
            if (problems or not isinstance(generation, dict)
                    or not isinstance(selection, dict)
                    or generation.get("generation_id") != output.get("generation_id")
                    or selection.get("generation_sha256")
                    != output.get("generation_sha256")):
                fail("Lean migration cannot resume partially retired fixed proof: "
                     + "; ".join(problems or ["durable output identity changed"]))
            for entry, path in zip(entries, source_paths):
                if path in missing_sources:
                    continue
                if (path.is_symlink() or not path.is_file()
                        or hashlib.sha256(path.read_bytes()).hexdigest()
                        != entry["sha256"]):
                    fail(f"fixed review input {entry['path']} changed during resume")
            sentinels.append({
                "output": output, "sealed_commit": sealed,
                "selection_sha256": hashlib.sha256(
                    (marker.parent / "reviews" / "selected.json").read_bytes(),
                ).hexdigest(),
                "source_paths": [entry["path"] for entry in entries],
            })
            continue
        lenses = {}
        for entry in entries:
            try:
                value = json.loads((target / entry["path"]).read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("expected an object")
                if "task_id" not in value:
                    value["task_id"] = entry["task_id"]
                validate_payload(target, "review", value)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError,
                    ValueError, SystemExit) as exc:
                fail(f"fixed review input {entry['path']} is malformed: {exc}")
            lens = Path(entry["path"]).stem
            if value.get("aspect") not in {None, lens}:
                fail(f"fixed review input {entry['path']} has mixed lens identity")
            lenses[lens] = value
        # Individually valid but incomplete sets are inert display history.
        if set(lenses) != set(LEAN_LENSES):
            continue
        task_ids = {str(value.get("task_id") or "") for value in lenses.values()}
        if len(task_ids) != 1 or not next(iter(task_ids)):
            fail(f"sealed fixed review {story} cannot identify exactly one task")
        task = next(iter(task_ids))
        if path_task and task != path_task:
            fail(f"sealed fixed review {story}/{path_task} has mixed task identity")
        by_lens = {Path(entry["path"]).stem: entry for entry in entries}
        marker = target / ".factory" / "stories" / story / "tasks" / task / "pr-ready.json"
        _require_unlinked_path(target, marker)
        if not marker.is_file():
            continue  # active old proof is intentionally retired and reviewed fresh
        marker_data = load_json(marker, default={})
        committed, marker_problem = _committed_task_marker(
            target, story, task, marker_data, None,
        )
        if marker_problem or committed is None:
            fail(f"sealed fixed review {story}/{task} marker is invalid: "
                 f"{marker_problem or 'not committed'}")
        sealed = committed["commit"]
        expected_delta = product_delta_digest(
            target, marker_data.get("review_base_sha")
            or marker_data.get("base_main_sha", ""), sealed,
        )
        selection_path = (target / ".factory" / "stories" / story / "tasks"
                          / task / "reviews" / "selected.json")
        _require_unlinked_path(target, selection_path)
        if selection_path.exists() or selection_path.is_symlink():
            generation, selection, problems = read_selected_review_generation(
                target, story, task, expected_delta_id=expected_delta,
                sealed_commit=sealed,
            )
            if (problems or not isinstance(generation, dict)
                    or not isinstance(selection, dict)
                    or generation.get("inspected_commit") != sealed):
                fail("Lean migration refuses mixed canonical and fixed review proof: "
                     + "; ".join(problems or ["selected proof lacks exact sealed binding"]))
            sentinels.append({
                "output": {
                    "story": story, "task_id": task,
                    "generation_id": generation["generation_id"],
                    "generation_sha256": selection["generation_sha256"],
                },
                "sealed_commit": sealed,
                "selection_sha256": hashlib.sha256(
                    selection_path.read_bytes()).hexdigest(),
                "source_paths": [entry["path"] for entry in entries],
            })
            continue
        deltas = {value.get("branch_diff_digest") for value in lenses.values()
                  if isinstance(value, dict)}
        if len(deltas) != 1 or not next(iter(deltas), ""):
            fail(f"sealed fixed review {story}/{task} has conflicting delta identity")
        if deltas != {expected_delta}:
            fail(f"sealed fixed review {story}/{task} delta does not match its marker")
        candidate = {
            "format": "forge-review-generation/v1", "origin": "upgrade",
            "generated_by": "upgrade", "story": story, "task_id": task,
            "inspected_commit": sealed, "delta_id": next(iter(deltas)),
            "lenses": lenses, "recorded_at": marker_data["sealed_at"],
            "upgrade": {
                "inventory_digest": migration["input_inventory_digest"],
                "source_kind": "sealed", "sealed_commit": sealed,
                "legacy_artifacts": [
                    {"aspect": lens, "path": by_lens[lens]["path"],
                     "sha256": by_lens[lens]["sha256"]}
                    for lens in LEAN_LENSES
                ],
            },
        }
        validate_review_document(target, candidate, allow_missing_generation_id=True)
        candidates.append((candidate, [target / entry["path"] for entry in entries]))
    return candidates, sentinels


def _exact_review_output_exists(
        target: Path, candidate: dict, generation_id: str, body: bytes) -> bool:
    """Reuse only an exact interrupted migration publication; refuse mixed proof."""
    from factory_lib import validate_review_document
    reviews = (target / ".factory" / "stories" / candidate["story"]
               / "tasks" / candidate["task_id"] / "reviews")
    selection_path = reviews / "selected.json"
    if not selection_path.exists() and not selection_path.is_symlink():
        return False
    generation_path = reviews / "generations" / f"{generation_id}.json"
    try:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        generation_bytes = generation_path.read_bytes()
        generation = json.loads(generation_bytes)
        validate_review_document(target, selection)
        validate_review_document(target, generation)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SystemExit) as exc:
        fail(f"Lean migration refuses mixed canonical and fixed review proof: {exc}")
    expected_sha = hashlib.sha256(body).hexdigest()
    if (generation_bytes != body
            or selection.get("story") != candidate["story"]
            or selection.get("task_id") != candidate["task_id"]
            or selection.get("generation_id") != generation_id
            or selection.get("generation_sha256") != expected_sha):
        fail("Lean migration refuses mixed canonical and fixed review proof")
    return True


def _publish_upgrade_review(
        target: Path, migration: dict, candidate: dict,
        expected_id: str, expected_sha: str) -> tuple[dict, dict]:
    """Publish one upgrade generation with inventory and selection serialized."""
    from factory_lib import (
        _publish_immutable_review_file, _replace_review_selection, now_iso,
        read_selected_review_generation, review_generation_bytes,
        validate_review_document,
    )
    from .delegate import delegation_exclusion

    generation = {**candidate, "generation_id": expected_id}
    body = review_generation_bytes(generation)
    reviews = (target / ".factory" / "stories" / candidate["story"]
               / "tasks" / candidate["task_id"] / "reviews")
    generation_path = reviews / "generations" / f"{expected_id}.json"
    selection_path = reviews / "selected.json"
    with delegation_exclusion(
            target, candidate["task_id"], kind="review-selection"):
        _revalidate_lean_inventory(target, migration)
        if _exact_review_output_exists(target, candidate, expected_id, body):
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
        else:
            _publish_immutable_review_file(target, generation_path, body)
            selection = {
                "format": "forge-review-selection/v1",
                "story": candidate["story"], "task_id": candidate["task_id"],
                "generation_id": expected_id,
                "generation_sha256": expected_sha,
                "delta_id": candidate["delta_id"], "selected_at": now_iso(),
            }
            validate_review_document(target, selection)
            _replace_review_selection(target, selection_path, selection)
        published, _pointer, problems = read_selected_review_generation(
            target, candidate["story"], candidate["task_id"],
            expected_delta_id=candidate["delta_id"],
            sealed_commit=candidate["upgrade"]["sealed_commit"],
        )
        if (problems or not isinstance(published, dict)
                or published.get("generation_id") != expected_id):
            fail("selected upgrade review failed readback: "
                 + "; ".join(problems or ["wrong selected generation"]))
    return generation, selection


def _publish_incomplete_lean_manifest(
        target: Path, manifest: dict, *, destination_name: str,
) -> Path:
    """Persist resumable transaction state before any canonical pointer moves."""
    from factory_lib import dump_json

    destination = (
        target / ".factory" / "migrations" / destination_name
    )
    if destination.exists() or destination.is_symlink():
        _require_single_link_manifest(target, destination)
        existing = load_json(destination, default={})
        comparable = {
            key: value for key, value in existing.items()
            if key not in {"recorded_at", "completed_at"}
        }
        expected = {
            key: value for key, value in manifest.items() if key != "recorded_at"
        }
        if comparable != expected:
            fail("Lean migration manifest retry differs from the durable original")
        return destination
    assert_target_destination(target, destination.parent).mkdir(
        parents=True, exist_ok=True,
    )
    dump_json(destination, manifest)
    if load_json(destination, default={}) != manifest:
        fail("Lean migration manifest readback differs")
    return destination


def _upgrade_path_identity(path: Path) -> dict[str, object]:
    """Return a no-follow identity for one upgrade source or destination."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"kind": "missing"}
    except OSError as exc:
        fail(f"could not inspect upgrade resume path {path}: {exc}")
    if stat.S_ISLNK(info.st_mode):
        return {
            "kind": "symlink", "sha256": hashlib.sha256(
                os.readlink(path).encode("utf-8", errors="surrogateescape")
            ).hexdigest(),
        }
    if stat.S_ISREG(info.st_mode):
        body = path.read_bytes()
        return {"kind": "file", "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest()}
    if not stat.S_ISDIR(info.st_mode):
        return {"kind": "other"}
    rows: list[dict[str, object]] = []
    try:
        for current, directories, files in os.walk(path, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in directories):
                return {"kind": "symlinked-tree"}
            for name in files:
                if name == ".DS_Store" or name.endswith(".pyc"):
                    continue
                child = current_path / name
                child_info = child.lstat()
                if (not stat.S_ISREG(child_info.st_mode)
                        or child_info.st_nlink != 1):
                    return {"kind": "nonregular-tree"}
                body = child.read_bytes()
                rows.append({
                    "path": child.relative_to(path).as_posix(),
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                })
    except OSError as exc:
        fail(f"could not inspect upgrade resume tree {path}: {exc}")
    rows.sort(key=lambda row: str(row["path"]))
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {"kind": "tree", "entries": rows,
            "sha256": hashlib.sha256(encoded).hexdigest()}


def _upgrade_resume_harness_identity(
        harness: Path, operations: list[dict[str, object]]) -> str:
    commit = head_sha(harness)
    if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        return commit
    inventory = [
        {"source": row["source"], "identity": row["source_identity"]}
        for row in operations if row.get("kind") in {"tree", "file"}
    ]
    return hashlib.sha256(json.dumps(
        inventory, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def _upgrade_resume_plan(
        harness: Path, target: Path,
        preserve_sources: dict[str, Path],
        profile_replacements: list[tuple[Path, Path]],
        preserve_backups: dict[str, Path] | None = None,
) -> dict[str, object]:
    """Describe every path the public upgrade may mutate before finalization."""
    operations: list[dict[str, object]] = []

    def source_operation(kind: str, source: Path, destination: Path) -> None:
        source_rel = source.relative_to(harness).as_posix()
        destination_rel = destination.relative_to(target).as_posix()
        operations.append({
            "kind": kind, "path": destination_rel, "source": source_rel,
            "source_identity": _upgrade_path_identity(source),
        })

    for relative in UPGRADE_TREES:
        source = harness / relative
        if source.exists():
            source_operation("tree", source, target / relative)
    for relative in CLAUDE_HARNESS_OWNED:
        source = harness / ".claude" / relative
        if source.exists():
            source_operation("tree" if source.is_dir() else "file", source,
                             target / ".claude" / relative)
    for relative in COPY_WORKFLOWS:
        source = harness / relative
        if source.exists():
            source_operation("file", source, target / relative)
    for name in COPY_CODEX:
        source = harness / ".codex" / name
        if source.exists():
            source_operation("file", source, target / ".codex" / name)
    agents = harness / ".codex" / "agents"
    if agents.is_dir():
        for source in sorted(agents.iterdir()):
            source_operation("file", source, target / ".codex" / "agents" / source.name)
    for relative in CODEX_HARNESS_OWNED_SKILLS:
        source = harness / relative
        if source.exists():
            source_operation("tree" if source.is_dir() else "file", source,
                             target / relative)
    for name in UPGRADE_FILES:
        source = harness / name
        if source.exists():
            source_operation("file", source, target / name)
    for source_rel, destination_rel in DOC_CONTRACTS:
        source = harness / source_rel
        if source.exists():
            source_operation("file", source, target / destination_rel)
    for relative, source in preserve_sources.items():
        destination = target / relative
        operation = {
            "kind": "preserve", "path": relative,
            "before": _upgrade_path_identity(destination),
            "source": source.relative_to(target).as_posix()
            if source.is_relative_to(target) else "",
        }
        backup = (preserve_backups or {}).get(relative)
        if backup is not None:
            operation["backup"] = backup.relative_to(target).as_posix()
        operations.append(operation)
    for source, destination in profile_replacements:
        source_operation("file", source, destination)

    # These paths are changed by the finalization tail after Lean migration.
    # Their operation names and source commit are authenticated; the finalizer
    # itself remains idempotent on retry.
    finalization = {
        ".agents", ".envrc", ".gitattributes", "README.md", ".gitignore",
        "harness.yaml", "constitution/VENDORED_FROM",
        "constitution/VENDOR_MANIFEST.json", ".factory/briefs",
        ".factory/diagnostic-briefs", ".factory/delegations.jsonl",
    } | set(PROJECT_STARTERS)
    operations.extend({
        "kind": "finalize", "path": relative,
        "before": _upgrade_path_identity(target / relative),
    } for relative in sorted(finalization))
    # The migration receipt is itself the authenticated resume anchor.
    operations.append({
        "kind": "state", "path": f".factory/migrations/{LEAN_MIGRATION_VERSION}.json",
    })
    operations.sort(key=lambda row: (-len(str(row["path"])), str(row["path"]),
                                    str(row["kind"])))
    plan = {
        "version": UPGRADE_RESUME_VERSION,
        "harness_commit": _upgrade_resume_harness_identity(harness, operations),
        "operations": operations,
    }
    plan["plan_sha256"] = hashlib.sha256(json.dumps(
        plan["operations"], sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    return plan


def _upgrade_resume_plan_is_valid(
        target: Path, harness: Path, plan: object,
) -> bool:
    if not isinstance(plan, dict):
        return False
    operations = plan.get("operations")
    recorded_commit = plan.get("harness_commit")
    if (plan.get("version") != UPGRADE_RESUME_VERSION
            or not isinstance(recorded_commit, str)
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", recorded_commit) is None
            or not isinstance(operations, list)
            or plan.get("plan_sha256") != hashlib.sha256(json.dumps(
                operations, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()):
        return False
    for row in operations:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            return False
        path = Path(row["path"])
        if (path.is_absolute() or ".." in path.parts
                or not row["path"] or "\\" in row["path"]):
            return False
        kind = row.get("kind")
        if kind in {"tree", "file"}:
            source = row.get("source")
            identity = row.get("source_identity")
            if (not isinstance(source, str) or Path(source).is_absolute()
                    or ".." in Path(source).parts or "\\" in source
                    or not isinstance(identity, dict)
                    or _upgrade_path_identity(harness / source) != identity):
                return False
        elif kind in {"preserve", "finalize"}:
            if (not isinstance(row.get("before"), dict)
                    or (kind == "finalize" and "after" in row
                        and not isinstance(row.get("after"), dict))):
                return False
            if kind == "preserve" and "backup" in row:
                backup = row["backup"]
                if not isinstance(backup, str):
                    return False
                backup_path = Path(backup)
                if (backup_path.is_absolute()
                        or ".." in backup_path.parts or "\\" in backup
                        or backup != f"{UPGRADE_PRESERVED_ROOT}/{row['path']}"
                        or not backup.startswith(UPGRADE_PRESERVED_ROOT + "/")):
                    return False
                _require_unlinked_path(target, target / backup_path.parent)
                if (_upgrade_path_identity(target / backup_path) != row["before"]
                        and _upgrade_path_identity(target / row["path"])
                        != row["before"]):
                    return False
        elif kind not in {"remove", "state"}:
            return False
    if recorded_commit != _upgrade_resume_harness_identity(harness, operations):
        return False
    return True


def _persist_prepared_lean_manifest(
        target: Path, migration: dict, *, runtime_source: Path,
        profile_replacements: list[tuple[Path, Path]],
        preserve_sources: dict[str, Path] | None = None,
        preserve_backups: dict[str, Path] | None = None,
) -> None:
    """Publish authenticated retry state before vendoring mutates the target."""
    from factory_lib import dump_json, now_iso, validate_payload

    promoted_paths = {
        path.relative_to(target).as_posix()
        for _candidate, paths in migration.get("review_candidates") or []
        for path in paths
    } | {
        path for sentinel in migration.get("review_sentinels") or []
        for path in sentinel["source_paths"]
    }
    preserved_entries = [
        entry for entry in migration["entries"]
        if entry.get("preserve") is True
        or (entry["family"] == "fixed-review-lens"
            and entry["path"] not in promoted_paths
            and entry.get("preserve") is not False)
    ]
    converted_outputs = []
    for entry in migration["entries"]:
        if (entry.get("classification") == "eligible"
                and entry.get("family") == "legacy-stage-stamp"):
            converted_outputs.append({
                "path": entry["path"],
                "sha256": hashlib.sha256(_converted_stage_bytes(
                    (target / entry["path"]).read_bytes(),
                )).hexdigest(),
            })
    outputs = [
        sentinel["output"] for sentinel in migration.get("review_sentinels") or []
    ]
    prepared = migration.get("prepared_reviews") or []
    for candidate, _paths in migration.get("review_candidates") or []:
        matches = [
            row for row in prepared if row.get("candidate") == candidate
        ]
        if len(matches) != 1:
            fail("Lean migration prepared review is missing before vendoring")
        row = matches[0]
        outputs.append({
            "story": candidate["story"], "task_id": candidate["task_id"],
            "generation_id": row["generation_id"],
            "generation_sha256": row["generation_sha256"],
        })
    runtime = _runtime_inventory(runtime_source)
    manifest = {
        "generated_by": "upgrade", "version": LEAN_MIGRATION_VERSION,
        "input_inventory_digest": migration["input_inventory_digest"],
        "output_digest": hashlib.sha256(json.dumps(
            outputs, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
        "installed_runtime_digest": _inventory_digest(runtime),
        "installed_runtime": runtime,
        "entries": migration["entries"], "outputs": outputs,
        "converted_outputs": converted_outputs,
        "preserved_entries": preserved_entries,
        "recorded_at": now_iso(),
    }
    if profile_replacements:
        manifest["profile_replacements"] = [
            {
                "path": destination.relative_to(target).as_posix(),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
            for source, destination in sorted(
                profile_replacements,
                key=lambda pair: pair[1].relative_to(target).as_posix(),
            )
        ]
    if "prior_completion" in migration:
        manifest.update({
            "prior_completion": migration["prior_completion"],
            "prior_completion_digest": migration["prior_completion_digest"],
        })
    migration["upgrade_resume"] = _upgrade_resume_plan(
        runtime_source, target, preserve_sources or {}, profile_replacements,
        preserve_backups,
    )
    manifest["upgrade_resume"] = migration["upgrade_resume"]
    # This publishes retry state BEFORE vendoring mutates the target, so a target
    # upgrading from a release without this schema does not carry it yet --
    # installing it is what the upgrade is about to do. Divert to the executing
    # harness, which is the authenticated source of the same schema, ONLY when
    # the target schema is absent. Catching read errors instead would swallow a
    # genuine IO fault that callers rely on surfacing.
    from factory_lib import schema_path
    schema_owner = (
        target if schema_path(target, "lean-workflow-migration").is_file()
        else runtime_source
    )
    validate_payload(schema_owner, "lean-workflow-migration", manifest)
    destination_name = str(
        migration.get("manifest_name") or f"{LEAN_MIGRATION_VERSION}.json"
    )
    destination = target / ".factory" / "migrations" / destination_name
    extension_sha = migration.get("extend_completed_sha256")
    if extension_sha:
        with tempfile.TemporaryDirectory(prefix="forge-lean-prepared-") as temporary:
            built = Path(temporary) / destination_name
            dump_json(built, manifest)
            _publish_converted_stage(
                target, destination, built,
                original_sha256=extension_sha,
                output_sha256=hashlib.sha256(built.read_bytes()).hexdigest(),
            )
    _publish_incomplete_lean_manifest(
        target, manifest, destination_name=destination_name,
    )
    migration.pop("extend_completed_sha256", None)


def _publish_converted_stage(
        target: Path, destination: Path, built: Path, *, original_sha256: str,
        output_sha256: str, allow_missing: bool = False) -> None:
    """Atomically replace one exact inventoried stage file from the temp build."""
    _require_unlinked_path(target, destination)
    assert_target_file_destination(target, destination)
    body = built.read_bytes()
    if hashlib.sha256(body).hexdigest() != output_sha256:
        fail("Lean migration temporary converted stage identity changed")
    try:
        current = destination.read_bytes()
    except FileNotFoundError:
        if not allow_missing:
            raise
        current_sha256 = None
    else:
        current_sha256 = hashlib.sha256(current).hexdigest()
    _require_unlinked_path(target, destination.parent)
    for stale in destination.parent.iterdir():
        if re.fullmatch(
                rf"\.{re.escape(destination.name)}\.\d+\.lean\.tmp",
                stale.name,
        ) is None:
            continue
        _require_unlinked_path(target, stale)
        info = stale.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or _linked_or_reparse(info)):
            fail(f"Lean migration refuses unsafe stale temporary {stale.name}")
        stale.unlink()
    if current_sha256 == output_sha256:
        return
    if current_sha256 is not None and current_sha256 != original_sha256:
        fail("Lean migration input changed before conversion")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.lean.tmp")
    assert_target_file_destination(target, temporary)
    publication_mode = stat.S_IMODE(
        (destination if current_sha256 is not None else built).lstat().st_mode,
    )
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0),
        publication_mode,
    )
    try:
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, publication_mode)
            view = memoryview(body)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    fail("Lean migration converted-stage temporary write was incomplete")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if temporary.read_bytes() != body:
            fail("Lean migration converted-stage temporary readback differs")
        temporary = assert_target_file_destination(target, temporary)
        destination = assert_target_file_destination(target, destination)
        os.replace(temporary, destination)
        published = destination.read_bytes()
        if (published != body
                or hashlib.sha256(published).hexdigest() != output_sha256):
            fail("Lean migration converted-stage publication readback differs")
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def apply_lean_migration(
        target: Path, migration: dict | None, *,
        profile_replacements: list[tuple[Path, Path]] | None = None,
) -> None:
    if migration is None:
        return
    from factory_lib import (
        dump_json, now_iso, review_generation_bytes, review_generation_id,
        validate_payload, validate_review_document,
    )
    review_candidates = migration.get("review_candidates") or []
    review_sentinels = migration.get("review_sentinels") or []
    runtime = (
        migration.get("installed_runtime")
        if migration.get("resume") and isinstance(
            migration.get("installed_runtime"), list
        ) else _runtime_inventory(target)
    )
    prepared = {
        row["generation_id"]: row
        for row in migration.get("prepared_reviews") or []
    }
    saved_profile_replacements = _profile_replacement_hashes(migration)
    if saved_profile_replacements is None:
        fail("Lean migration profile replacement metadata is malformed")
    profile_replacements = profile_replacements or []
    if saved_profile_replacements and not profile_replacements:
        fail("Lean migration current profile replacements are missing")
    replacement_inputs: list[tuple[Path, Path, bytes, str, str]] = []
    replacement_rows: dict[str, str] = {}
    entries_by_path = {
        entry["path"]: entry for entry in migration.get("entries") or []
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    for source, destination in profile_replacements:
        relative = destination.relative_to(target).as_posix()
        entry = entries_by_path.get(relative)
        if (not isinstance(entry, dict)
                or entry.get("classification") != "eligible"
                or entry.get("family") != "retired-forge-profile"
                or entry.get("sha256") != RETIRED_FORGE_PROFILE_HASHES.get(
                    destination.name)):
            fail(f"Lean migration profile replacement is not an inventoried retired input: {relative}")
        if source.is_symlink() or not source.is_file():
            fail(f"Lean migration current profile source is not a regular file: {relative}")
        body = source.read_bytes()
        source_sha256 = hashlib.sha256(body).hexdigest()
        if (relative in replacement_rows
                or (saved_profile_replacements
                    and saved_profile_replacements.get(relative) != source_sha256)):
            fail(f"Lean migration current profile source changed: {relative}")
        replacement_rows[relative] = source_sha256
        replacement_inputs.append((
            source, destination, body, entry["sha256"], source_sha256,
        ))
    if saved_profile_replacements and set(replacement_rows) != set(
            saved_profile_replacements):
        fail("Lean migration current profile replacement set changed")
    promoted_paths = {
        path.relative_to(target).as_posix()
        for _candidate, paths in review_candidates for path in paths
    } | {
        path for sentinel in review_sentinels
        for path in sentinel["source_paths"]
    }
    preserved_entries = [
        entry for entry in migration["entries"]
        if entry.get("preserve") is True
        or (entry["family"] == "fixed-review-lens"
            and entry["path"] not in promoted_paths
            and entry.get("preserve") is not False)
    ]
    converted_outputs = []
    converted_bodies: dict[str, bytes] = {}
    for entry in migration["entries"]:
        if (entry.get("classification") == "eligible"
                and entry.get("family") == "legacy-stage-stamp"):
            converted = _converted_stage_bytes(
                (target / entry["path"]).read_bytes(),
            )
            converted_outputs.append({
                "path": entry["path"],
                "sha256": hashlib.sha256(converted).hexdigest(),
            })
            converted_bodies[entry["path"]] = converted
    # Build every durable output away from the target first. Publication starts
    # only after schema validation and byte readback of the whole build.
    with tempfile.TemporaryDirectory(prefix="forge-lean-build-") as temporary:
        build = Path(temporary)
        built_converted: dict[str, Path] = {}
        for index, row in enumerate(converted_outputs):
            path = build / "stages" / f"{index}.json"
            assert_target_destination(build, path.parent).mkdir(
                parents=True, exist_ok=True,
            )
            body = converted_bodies[row["path"]]
            path.write_bytes(body)
            if (path.read_bytes() != body
                    or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]):
                fail("Lean migration temporary converted stage readback differs")
            built_converted[row["path"]] = path
        built_profile_replacements: list[tuple[Path, bytes, str, str]] = []
        for index, (_source, destination, body, original_sha256,
                    output_sha256) in enumerate(replacement_inputs):
            path = build / "profiles" / f"{index}-{destination.name}"
            assert_target_destination(build, path.parent).mkdir(
                parents=True, exist_ok=True,
            )
            path.write_bytes(body)
            if (path.read_bytes() != body
                    or hashlib.sha256(path.read_bytes()).hexdigest()
                    != output_sha256):
                fail("Lean migration temporary profile readback differs")
            built_profile_replacements.append(
                (destination, body, original_sha256, output_sha256),
            )
        built_generations: list[tuple[dict, str, str]] = []
        outputs: list[dict[str, str]] = (
            list(migration.get("outputs") or [])
            if migration.get("resume") else
            [sentinel["output"] for sentinel in review_sentinels]
        )
        for index, (candidate, _paths) in enumerate(review_candidates):
            validate_review_document(target, candidate, allow_missing_generation_id=True)
            generation = dict(candidate)
            generation["generation_id"] = review_generation_id(generation)
            validate_review_document(target, generation)
            body = review_generation_bytes(generation)
            path = build / "reviews" / f"{index}-{generation['generation_id']}.json"
            assert_target_destination(build, path.parent).mkdir(
                parents=True, exist_ok=True,
            )
            path.write_bytes(body)
            if path.read_bytes() != body:
                fail("Lean migration temporary review readback differs")
            validate_review_document(target, json.loads(path.read_text(encoding="utf-8")))
            digest = hashlib.sha256(body).hexdigest()
            prepared_row = prepared.get(generation["generation_id"])
            if (not prepared_row
                    or prepared_row.get("generation_sha256") != digest
                    or prepared_row.get("candidate") != candidate):
                fail("Lean migration prepared review changed after preflight")
            built_generations.append((candidate, generation["generation_id"], digest))
            output = {
                "story": candidate["story"], "task_id": candidate["task_id"],
                "generation_id": generation["generation_id"],
                "generation_sha256": digest,
            }
            if migration.get("resume"):
                if output not in outputs:
                    fail("Lean migration prepared review is absent from durable state")
            else:
                outputs.append(output)

        _revalidate_lean_inventory(target, migration)

        manifest = {
            "generated_by": "upgrade", "version": LEAN_MIGRATION_VERSION,
            "input_inventory_digest": migration["input_inventory_digest"],
            "output_digest": hashlib.sha256(json.dumps(
                outputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "installed_runtime_digest": _inventory_digest(runtime),
            "installed_runtime": runtime,
            "entries": migration["entries"], "outputs": outputs,
            "converted_outputs": converted_outputs,
            "preserved_entries": preserved_entries,
            "recorded_at": now_iso(),
        }
        if replacement_rows:
            manifest["profile_replacements"] = [
                {"path": path, "sha256": replacement_rows[path]}
                for path in sorted(replacement_rows)
            ]
        if "prior_completion" in migration:
            manifest.update({
                "prior_completion": migration["prior_completion"],
                "prior_completion_digest": migration["prior_completion_digest"],
            })
        if "upgrade_resume" in migration:
            manifest["upgrade_resume"] = migration["upgrade_resume"]
        try:
            validate_payload(target, "lean-workflow-migration", manifest)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SystemExit):
            # A retry can reach Lean completion before the replacement factory
            # tree has been copied back.  Use the executing harness's schema
            # for this authenticated in-memory manifest, then restore target
            # machinery in the normal vendoring loop.
            validate_payload(repo_root(), "lean-workflow-migration", manifest)
        built_manifest = build / f"{LEAN_MIGRATION_VERSION}.json"
        dump_json(built_manifest, manifest)
        if load_json(built_manifest, default={}) != manifest:
            fail("Lean migration temporary manifest readback differs")

        destination = (
            target / ".factory" / "migrations" / str(
                migration.get("manifest_name")
                or f"{LEAN_MIGRATION_VERSION}.json"
            )
        )
        extension_sha = migration.get("extend_completed_sha256")
        if extension_sha:
            _publish_converted_stage(
                target, destination, built_manifest,
                original_sha256=extension_sha,
                output_sha256=hashlib.sha256(built_manifest.read_bytes()).hexdigest(),
            )
        destination = _publish_incomplete_lean_manifest(
            target, manifest,
            destination_name=destination.name,
        )
        incomplete_manifest_sha256 = hashlib.sha256(
            destination.read_bytes(),
        ).hexdigest()
        for candidate, expected_id, expected_sha in built_generations:
            generation, selection = _publish_upgrade_review(
                target, migration, candidate, expected_id, expected_sha,
            )
            if (generation["generation_id"] != expected_id
                    or selection["generation_sha256"] != expected_sha):
                fail("Lean migration published review differs from temporary build")
        entries_by_path = {entry["path"]: entry for entry in migration["entries"]}
        for row in converted_outputs:
            entry = entries_by_path[row["path"]]
            _publish_converted_stage(
                target, target / row["path"], built_converted[row["path"]],
                original_sha256=entry["sha256"], output_sha256=row["sha256"],
            )

    # Durable selected outputs and manifest now exist. Retire exactly the
    # inventoried bytes, refusing identity drift instead of deleting by name.
    replacement_by_path = {
        profile_destination: output_sha256
        for profile_destination, _body, _original_sha256, output_sha256
        in built_profile_replacements
    }
    for entry in migration["entries"]:
        if entry.get("classification") != "eligible":
            continue
        path = _lean_manifest_path(target, entry["path"])
        if not path.exists():
            continue
        if entry["family"] == "old-hook-flag":
            if path.is_symlink() or not path.is_file() \
                    or "hooks = true" not in path.read_text(encoding="utf-8") \
                    or "codex_hooks = true" in path.read_text(encoding="utf-8"):
                fail("Lean migration did not install the current Codex hook flag")
            continue
        if (entry["family"] in {
                "fixed-review-lens", "story-fixed-review-lens",
                "history-fixed-review-lens",
        } and entry["path"] not in promoted_paths
                and entry.get("preserve") is not False):
            continue
        expected_profile_sha256 = replacement_by_path.get(path)
        if expected_profile_sha256 is not None and path.is_file() \
                and not path.is_symlink() \
                and hashlib.sha256(path.read_bytes()).hexdigest() \
                == expected_profile_sha256:
            continue
        if path.is_symlink() or not path.is_file():
            fail(f"Lean migration input changed before deletion: {entry['path']}")
        if entry["family"] == "legacy-stage-stamp":
            current = path.read_bytes()
            converted = _converted_stage_bytes(current)
            expected = next(
                row["sha256"] for row in converted_outputs
                if row["path"] == entry["path"]
            )
            current_digest = hashlib.sha256(current).hexdigest()
            if current_digest == expected:
                continue
            if current_digest != entry["sha256"]:
                fail(f"Lean migration input changed before conversion: {entry['path']}")
            fail(f"Lean migration converted stage was not atomically published: {entry['path']}")
        else:
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                fail(f"Lean migration input changed before deletion: {entry['path']}")
            path.unlink()

    # The first temporary build directory has been removed by this point. Keep
    # the authenticated bytes and materialize a fresh short-lived source for
    # each publication so an interruption after deletion can resume safely.
    with tempfile.TemporaryDirectory(prefix="forge-profile-build-") as temporary:
        profile_build = Path(temporary)
        for index, (profile_destination, body, original_sha256,
                    output_sha256) in enumerate(built_profile_replacements):
            built = profile_build / f"{index}-{profile_destination.name}"
            built.write_bytes(body)
            if (built.read_bytes() != body
                    or hashlib.sha256(built.read_bytes()).hexdigest()
                    != output_sha256):
                fail("Lean migration temporary profile readback differs")
            _publish_converted_stage(
                target, profile_destination, built,
                original_sha256=original_sha256,
                output_sha256=output_sha256,
                allow_missing=True,
            )

    completed = load_json(destination, default={})
    if not completed.get("completed_at"):
        completed["completed_at"] = now_iso()
        try:
            validate_payload(target, "lean-workflow-migration", completed)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SystemExit):
            validate_payload(repo_root(), "lean-workflow-migration", completed)
        _require_single_link_manifest(target, destination)
        with tempfile.TemporaryDirectory(prefix="forge-lean-complete-") as temporary:
            built_completed = Path(temporary) / destination.name
            dump_json(built_completed, completed)
            if load_json(built_completed, default={}) != completed:
                fail("Lean migration completion temporary readback differs")
            completed_sha256 = hashlib.sha256(
                built_completed.read_bytes(),
            ).hexdigest()
            _publish_converted_stage(
                target, destination, built_completed,
                original_sha256=incomplete_manifest_sha256,
                output_sha256=completed_sha256,
            )
        if load_json(destination, default={}) != completed:
            fail("Lean migration completion readback differs")


def _retired_forge_profiles(
        target: Path, known_profile_hashes: dict[str, set[str]] | None = None,
) -> tuple[list[Path], list[Path]]:
    """Classify old rows without treating a client edit as ours.

    Current profile names can overlap the retired registry. An exact retired
    byte sequence is removable; a different sequence under that name remains
    client-owned unless it is a known Forge version.
    """
    removable: list[Path] = []
    preserved: list[Path] = []
    root = target / ".codex" / "agents"
    _require_unlinked_path(target, root)
    known_profile_hashes = known_profile_hashes or {
        name: set(hashes)
        for name, hashes in KNOWN_FORGE_RETAINED_PROFILE_HASHES.items()
    }
    for name, expected in RETIRED_FORGE_PROFILE_HASHES.items():
        path = root / name
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file():
            preserved.append(path)
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        (removable if actual == expected else preserved).append(path)
    for name in set(LEAN_RETAINED_PROFILES) | set(known_profile_hashes):
        path = root / name
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file():
            preserved.append(path)
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if (name in RETIRED_FORGE_PROFILE_HASHES
                and actual == RETIRED_FORGE_PROFILE_HASHES[name]):
            continue
        if actual not in known_profile_hashes.get(name, set()):
            preserved.append(path)
    return removable, preserved
# Project-owned: never touched — listed here as the explicit contract.
# .github/workflows/ is project-owned EXCEPT the harness's own COPY_WORKFLOWS,
# which are refreshed file-by-file below — the rest of the tree (deployment,
# release, etc.) is left exactly as the project has it.
PROJECT_OWNED = [
    "harness.yaml", "AGENTS.md", ".factory/", "plans/", "prototype/",
    "docs/product/ (except its README.md doc contract)",
    "docs/decisions/ (except its README.md doc contract)",
    "docs/architecture/ (except its README.md doc contract)",
    "docs/context/ (except its README.md doc contract)",
    "docs/specs/ (except its README.md doc contract)", "docs/memory/",
    ".github/ (except the harness factory workflows)",
    ".claude/ and .codex/ additions the harness does not ship (project skills, agents, launch.json)",
]
# Preserved across the factory replacement (project evolution state).
PRESERVE_IN_AGENTS = ["factory/skills/proposed", "factory/skills/rejected"]
# Ephemeral working state (decision 0025): read from disk in the worktree,
# never from git. Untracked on upgrade — a .gitignore rule alone does nothing
# to an already-tracked file.
EPHEMERAL_UNTRACK = [".factory/briefs/", ".factory/diagnostic-briefs/",
                     ".factory/delegations.jsonl"]
# Must match the marker lines in the harness .gitignore exactly — each is the
# installed-once key for its ignore block below.
EPHEMERAL_MARKER = ("# forge 0025: briefs and the delegation mirror are "
                    "read from disk, never from git")
GSTACK_MARKER = ("# forge gstack: project-local store — projects/ is "
                 "committed, machine noise is not")
GSTACK_RULES = [".gstack/*", "!.gstack/projects/",
                ".gstack/**/brain-cache/", ".gstack/**/timeline.jsonl"]
# Vendoring never ships build or OS noise. .DS_Store is gitignored HERE, so it
# is invisible in this repo while still sitting on disk — and copytree walks
# the filesystem, not the index. It then lands in the client as untracked
# clutter, and inside .claude/ the thin-adapter linter rejects it outright:
# a real upgrade failed check_dual_runtime on a Finder artifact.
VENDOR_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def _replace_path(target: Path, src: Path, dst: Path) -> None:
    if dst.is_dir() and not dst.is_symlink():
        shutil.rmtree(assert_target_destination(target, dst))
    elif dst.exists() or dst.is_symlink():
        (assert_target_destination(target, dst.parent) / dst.name).unlink()
    assert_target_destination(target, dst.parent).mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        guarded_copytree(target, src, dst, ignore=VENDOR_IGNORE, symlinks=False)
    else:
        shutil.copy2(src, assert_target_file_destination(target, dst))


def _keep_path(keep_root: Path, src: Path, dst: Path) -> None:
    """Copy project-owned state into the temporary preservation tree.

    Symlinks are preserved AS symlinks. Dereferencing would copy the referent's
    bytes into the repo under the link's name — and since retirement then
    deletes the original, a link pointing outside the repo would be silently
    replaced by its target's content."""
    assert_target_destination(keep_root, dst.parent).mkdir(parents=True, exist_ok=True)
    if src.is_dir() and not src.is_symlink():
        guarded_copytree(keep_root, src, dst, dirs_exist_ok=True, symlinks=True)
    else:
        shutil.copy2(
            src, assert_target_file_destination(keep_root, dst),
            follow_symlinks=False,
        )


def _backup_upgrade_skills(
        target: Path, preserve_sources: dict[str, Path],
        backups: dict[str, Path],
) -> None:
    """Keep client factory skills recoverable until the upgrade is complete."""
    for relative, backup in backups.items():
        source = preserve_sources[relative]
        _require_unlinked_path(target, source.parent)
        identity = _upgrade_path_identity(source)
        if identity.get("kind") in {"other", "nonregular-tree", "symlinked-tree"}:
            fail(f"cannot record a safe upgrade backup for {relative}")
        _require_unlinked_path(target, backup.parent)
        if backup.exists() or backup.is_symlink():
            fail(f"upgrade preservation backup already exists: {backup}")
        _keep_path(target, source, backup)
        if _upgrade_path_identity(backup) != identity:
            fail(f"upgrade preservation backup readback differs: {relative}")


def _restore_upgrade_backup(target: Path, source: Path, destination: Path) -> None:
    """Restore one missing preserved path from its recorded target-local copy."""
    if destination.exists() or destination.is_symlink():
        fail(f"preserved upgrade destination changed before restore: {destination}")
    assert_target_destination(target, destination.parent).mkdir(
        parents=True, exist_ok=True,
    )
    if source.is_dir() and not source.is_symlink():
        guarded_copytree(target, source, destination, symlinks=True)
    else:
        shutil.copy2(
            source, assert_target_file_destination(target, destination),
            follow_symlinks=False,
        )


def _check_legacy_retirable(target: Path, harness: Path) -> None:
    """Refuse BEFORE anything is written, or the repair cannot be run.

    Validation used to sit next to the delete, after the trees were replaced —
    so refusing left a clean repo dirty, and the "delete it and re-run" the
    message asks for was then rejected by the dirty-target gate above. The
    counterparts are knowable in advance: they are the harness's own factory/
    tree, plus everything under skills/, which survives either because the
    harness ships it or because it is preserved out of .agents/skills/ (the
    one exception, a client skill whose name the harness has since taken, is
    deferred as D-0002)."""
    legacy = target / ".agents"
    # Refuse a symlinked ROOT, do not just decline to retire it: every later
    # step reaches through it. `.agents/skills` resolves past the link, so
    # iterdir() would walk an external directory and copy its contents into
    # factory/skills — importing files from outside the repository entirely.
    if legacy.is_symlink():
        fail(
            ".agents is a symlink. The upgrade would migrate skills by reading "
            "through it, pulling content from outside the repository into "
            "factory/skills, and retiring it would drop the link rather than the "
            "machinery. Replace it with a real directory (or remove it) and "
            "re-run. Nothing was written."
        )
    assert_target_destination(target, legacy)
    if not legacy.is_dir():
        return
    # The whole skills/ subtree is exempt from the counterpart check below
    # because a real directory there is either shipped or preserved. Anything
    # ELSE at that path is neither: a symlink cannot be traversed (iterdir()
    # would walk the referent) and a regular file is never preserved at all,
    # so retirement would delete tracked client content that nothing checked.
    # Refuse the topology before any write rather than exempting it.
    skills_root = legacy / "skills"
    if skills_root.is_symlink() or (
            skills_root.exists() and not skills_root.is_dir()):
        fail(
            ".agents/skills is not a directory. The upgrade preserves client "
            "skills only from a real directory there, so retiring .agents/ would "
            "delete this without it ever being checked — and a symlink would be "
            "migrated by reading through it. Replace it with a real directory "
            "(or move it out of .agents/) and re-run. Nothing was written."
        )
    # A legacy skills entry whose name the harness also ships is treated as the
    # machinery being replaced. That cannot be decided from the paths: an older
    # harness's copy of a skill differs from the current one exactly the way a
    # client's would, and the harness ships factory/skills/forge.md, so
    # refusing every collision would refuse every upgrade. It is not silent
    # either — upgrade refuses a dirty tree, so the replacement lands as a
    # reviewed deletion in the upgrade diff. Conflict policy is D-0002.
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", ".agents"],
        cwd=target, capture_output=True)
    tracked = {
        raw.decode("utf-8", errors="surrogateescape")
        for raw in listing.stdout.split(b"\0") if raw
    }
    missing = []
    for path in sorted(legacy.rglob("*")):
        if not (path.is_file() or path.is_symlink()):
            continue
        rel = path.relative_to(legacy)
        # Vendoring never shipped build noise (VENDOR_IGNORE), so an UNTRACKED
        # .pyc has no counterpart by construction — counting it would abort the
        # upgrade on every real pre-rename repo, which all carry __pycache__
        # from having actually run the machinery. A TRACKED .pyc is committed
        # content, not a build artifact, and gets checked like anything else:
        # exempting by suffix alone would delete it on nothing but its name.
        if path.suffix == ".pyc" and f".agents/{rel.as_posix()}" not in tracked:
            continue
        if rel.parts and rel.parts[0] == "skills":
            continue
        counterpart = harness / "factory" / rel
        if not (counterpart.is_file() or counterpart.is_symlink()):
            missing.append(f".agents/{rel.as_posix()}")
    if missing:
        listing = "\n  ".join(missing[:10])
        more = f"\n  ... and {len(missing) - 10} more" if len(missing) > 10 else ""
        fail(
            f"legacy .agents/ holds {len(missing)} path(s) with no counterpart in the "
            f"vendored factory/ tree, so they cannot be shown to be the machinery "
            f"being replaced:\n  {listing}{more}\n"
            "Nothing was written and nothing under .agents/ was deleted. If this is "
            "retired machinery, delete it and re-run; if it is yours, move it "
            "somewhere the harness does not own."
        )


def _retire_legacy_agents(target: Path) -> bool:
    """Delete only. _check_legacy_retirable already refused anything unknown,
    before the first write."""
    legacy = target / ".agents"
    if not legacy.is_dir() or legacy.is_symlink():
        return False
    shutil.rmtree(assert_target_destination(target, legacy))
    return True


def _preflight_upgrade(
    harness: Path, target: Path, preserved: dict[str, Path],
) -> None:
    """Validate every target destination before upgrade's first mutation."""

    def directory(dst: Path) -> None:
        assert_target_destination(target, dst)

    def file(dst: Path) -> None:
        assert_target_destination(target, dst.parent)
        assert_target_file_destination(target, dst)

    def replacement(_src: Path, dst: Path) -> None:
        # _replace_path removes any existing dst (dir, file, or symlink), then
        # copies fresh — so only the root boundary matters here. A per-leaf or
        # file-type check against the PRE-removal state would falsely reject a
        # legal dir<->file type change, or a stale symlink the removal deletes.
        assert_target_destination(target, dst.parent)
        assert_target_destination(target, dst)

    directory(target)
    for tree in UPGRADE_TREES:
        if (harness / tree).exists():
            # Replacement tree: rmtree'd then copied fresh, so validate the root
            # boundary, not the pre-removal leaves (same reason as replacement()).
            directory(target / tree)
    for rel in CLAUDE_HARNESS_OWNED:
        src = harness / ".claude" / rel
        if src.exists():
            replacement(src, target / ".claude" / rel)
    for rel in COPY_WORKFLOWS:
        if (harness / rel).exists():
            file(target / rel)
    directory(target / ".codex")
    for name in COPY_CODEX:
        file(target / ".codex" / name)
    agents = harness / ".codex" / "agents"
    if agents.is_dir():
        for child in agents.iterdir():
            replacement(child, target / ".codex" / "agents" / child.name)
    for rel in CODEX_HARNESS_OWNED_SKILLS:
        src = harness / rel
        if src.exists():
            replacement(src, target / rel)
    for name in UPGRADE_FILES:
        if (harness / name).exists():
            file(target / name)
    for src_rel, dst_rel in DOC_CONTRACTS:
        if (harness / src_rel).exists():
            file(target / dst_rel)

    # These project-owned entries are deliberately preserved as symlinks.
    # Their leaf is removed by the factory root replacement before restoration,
    # so validate the surviving parent boundary here; the restored leaf itself
    # is routed through the helper once that replacement has made it absent.
    for rel in preserved:
        directory((target / rel).parent)

    for rel in (".gitattributes", "README.md", ".gitignore"):
        file(target / rel)
    # .envrc is create-if-missing: an existing one (even a symlink to a valid
    # external file) is left untouched, so only preflight the write case.
    if not (target / ".envrc").exists():
        file(target / ".envrc")
    # harness.yaml is rewritten only when it is a regular non-symlink file; the
    # mutation skips a symlink, so the preflight must not reject one either.
    manifest_yaml = target / "harness.yaml"
    if manifest_yaml.exists() and not manifest_yaml.is_symlink():
        file(manifest_yaml)
    for rel in PROJECT_STARTERS:
        if not (target / rel).exists():
            file(target / rel)
    file(target / "constitution" / "VENDORED_FROM")
    file(target / "constitution" / "VENDOR_MANIFEST.json")


def _is_harness_owned(rel: str, harness: Path) -> bool:
    def within(root: str) -> bool:
        return rel == root or rel.startswith(root + "/")

    if any(within(root) for root in UPGRADE_TREES + [".agents"]):
        return True
    if rel in UPGRADE_FILES or rel in COPY_WORKFLOWS:
        return True
    if rel in {dst for _, dst in DOC_CONTRACTS}:
        return True
    if any(within(f".claude/{path}") for path in CLAUDE_HARNESS_OWNED):
        return True
    if rel in {f".codex/{name}" for name in COPY_CODEX}:
        return True
    for sub in ("agents", "skills"):
        shipped = harness / ".codex" / sub
        if shipped.is_dir() and any(
            within(f".codex/{sub}/{child.name}") for child in shipped.iterdir()
        ):
            return True
    return False


def _indexed_symlinks_naming_legacy(target: Path) -> list[str]:
    """Symlinks whose target names the retired tree.

    `git grep` skips symlink entries, but a symlink's blob IS its target text —
    and a link into .agents/ breaks exactly like a mention of it does. Read the
    blob from the index rather than the working tree, so no link is ever
    followed and no ancestor can redirect the read out of the repository.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-s", "-z"], cwd=target, capture_output=True)
    if listing.returncode != 0:
        return []
    found = []
    for raw in listing.stdout.split(b"\0"):
        metadata, _, rel = raw.partition(b"\t")
        fields = metadata.split()
        if not rel or len(fields) < 2 or fields[0] != b"120000":
            continue
        blob = subprocess.run(
            ["git", "cat-file", "blob", fields[1].decode()],
            cwd=target, capture_output=True)
        if blob.returncode != 0:
            continue
        link = blob.stdout.decode("utf-8", errors="surrogateescape")
        # Whole path component: `legacy-tools -> .agents` has no trailing slash.
        if ".agents" in link.split("/"):
            found.append(rel.decode("utf-8", errors="surrogateescape"))
    return found


def _stale_agents_references(
    target: Path, harness: Path, migrated: list[str] | None = None,
    from_legacy: set[str] | None = None,
) -> list[str]:
    """Project-owned files that still name the retired tree.

    Searched in the INDEX, never through the working tree. Git streams blob
    content and resolves paths itself, so this cannot follow a symlink (at the
    leaf or at any ancestor) out of the repository, cannot wander into an
    ignored node_modules/ or dist/, and cannot allocate a whole large file to
    look for a short marker. A symlink's blob is its target text, so a link
    that merely NAMES .agents is matched like any other content.
    """
    # `.agents/` WITH the separator. A bare `.agents` is a substring of any
    # identifier that merely starts that way — a real target reports
    # `com.agentstats.push` and `day.agents` as stale machinery references,
    # which is noise the human then has to re-triage by hand. A symlink whose
    # target IS the bare root is caught by component match below, so the
    # slashless form buys nothing here.
    search = subprocess.run(
        ["git", "grep", "-l", "--cached", "-I", "-z", "-F", "-e", ".agents/", "--"],
        cwd=target, capture_output=True,
    )
    # 0 = matches, 1 = none. Anything else is a real failure, but this report
    # is advisory and runs after the migration; it must never abort the upgrade.
    if search.returncode not in (0, 1):
        return []
    hits = [
        raw.decode("utf-8", errors="surrogateescape")
        for raw in search.stdout.split(b"\0") if raw
    ]
    hits.extend(_indexed_symlinks_naming_legacy(target))
    # Client skills carried out of .agents/skills/ land at factory/skills/<name>,
    # untracked until the human stages the upgrade. Their INDEXED source is the
    # .agents/skills/ path, so translate the hit to where the file now lives
    # rather than walking the freshly copied tree.
    # ONLY names actually carried out of the legacy tree. A name preserved from
    # the CURRENT location had its legacy twin deliberately skipped (the
    # current location wins), so translating that discarded copy's hits would
    # name a current file that has no stale reference — or none at all.
    carried = from_legacy or set()
    # A client skill ALREADY at factory/skills/<name> is preserved, not
    # replaced — so it is project-owned even though _is_harness_owned sees it
    # inside an UPGRADE_TREES entry and would otherwise discard it. Match the
    # path itself as well as its descendants: a skill can be a single file
    # (factory/skills/client.md) or a symlink, preserved at that exact path.
    owned = set(migrated or [])
    preserved = tuple(f"{rel}/" for rel in owned)
    stale = set()
    for rel in hits:
        if rel.startswith(".factory/history/"):
            continue
        parts = rel.split("/")
        if parts[0] == ".agents":
            # A bare `.agents` path is a regular file or link at that name, not
            # the machinery directory — retirement leaves it in place, so it is
            # surviving project-owned content and belongs in the report.
            if len(parts) == 1:
                stale.add(rel)
                continue
            if len(parts) > 2 and parts[1] == "skills" and parts[2] in carried:
                stale.add("factory/skills/" + "/".join(parts[2:]))
            continue
        if rel not in owned and not rel.startswith(preserved) \
                and _is_harness_owned(rel, harness):
            continue
        stale.add(rel)
    return sorted(stale)


def _resume_harness_path_matches(harness: Path, target: Path, relative: str) -> bool:
    """Whether one dirty path is the exact result of this harness vendoring it."""
    source: Path | None = None
    if _is_harness_owned(relative, harness):
        source = harness / relative
    for src_rel, dst_rel in DOC_CONTRACTS:
        if relative == dst_rel:
            source = harness / src_rel
            break
    destination = target / relative
    if source is None:
        return False
    if not source.exists():
        return not destination.exists() and not destination.is_symlink()
    if (not source.is_file() or source.is_symlink()
            or not destination.is_file() or destination.is_symlink()):
        return False
    return destination.read_bytes() == source.read_bytes()


def _upgrade_resume_operation_matches(
        harness: Path, target: Path, row: dict, relative: str,
) -> bool:
    """Check one dirty path against the authenticated overall-upgrade plan."""
    root = str(row.get("path") or "")
    backup = row.get("backup")
    if (row.get("kind") == "preserve" and isinstance(backup, str)
            and (relative == backup or relative.startswith(backup + "/"))):
        return (
            _upgrade_path_identity(target / backup) == row.get("before")
            or _upgrade_path_identity(target / root) == row.get("before")
        )
    if relative != root and not relative.startswith(root + "/"):
        return False
    kind = row.get("kind")
    destination = target / relative
    if kind == "state":
        return relative == root and destination.is_file() and not destination.is_symlink()
    if kind == "remove":
        return not destination.exists() and not destination.is_symlink()
    if kind == "finalize":
        actual = _upgrade_path_identity(destination)
        suffix = relative[len(root):].lstrip("/")
        for recorded in (row.get("before"), row.get("after")):
            if not isinstance(recorded, dict):
                continue
            expected = recorded
            if suffix:
                if recorded.get("kind") == "missing":
                    expected = {"kind": "missing"}
                elif recorded.get("kind") == "tree":
                    entries = recorded.get("entries")
                    if not isinstance(entries, list):
                        continue
                    exact = next((entry for entry in entries
                                  if isinstance(entry, dict)
                                  and entry.get("path") == suffix), None)
                    expected = {"kind": "missing"} if exact is None else {
                        "kind": "file", "bytes": exact.get("bytes"),
                        "sha256": exact.get("sha256"),
                    }
                else:
                    continue
            if actual == expected:
                return True
        return False
    if kind == "preserve":
        expected = row.get("before")
        return (isinstance(expected, dict)
                and _upgrade_path_identity(target / root) == expected)
    if kind not in {"file", "tree"}:
        return False
    source_relative = str(row.get("source") or "")
    source_root = harness / source_relative
    suffix = relative[len(root):].lstrip("/")
    source = source_root / suffix if suffix else source_root
    expected = _upgrade_path_identity(source)
    # A removal immediately before guarded_copytree/_replace_path is a valid
    # interrupted state.  The next run will recreate it from the authenticated
    # harness source.
    if not destination.exists() and not destination.is_symlink():
        return expected.get("kind") != "missing"
    return _upgrade_path_identity(destination) == expected


def _upgrade_resume_path_matches(
        harness: Path, target: Path, operations: list[dict], relative: str,
) -> bool:
    """Let the narrowest preserve operation govern its path and descendants."""
    preserving = [
        row for row in operations
        if isinstance(row, dict) and row.get("kind") == "preserve"
        and isinstance(row.get("path"), str)
        and (relative == row["path"] or relative.startswith(row["path"] + "/"))
    ]
    if preserving:
        longest = max(len(row["path"]) for row in preserving)
        operations = [row for row in preserving if len(row["path"]) == longest]
    return any(_upgrade_resume_operation_matches(
        harness, target, row, relative,
    ) for row in operations)


def _authenticated_upgrade_resume_paths(
        target: Path, harness: Path, saved: dict, changed: set[str],
) -> set[str]:
    """Return only dirty paths matching an incomplete overall-upgrade plan."""
    plan = saved.get("upgrade_resume")
    if not isinstance(plan, dict):
        return set()
    if not _upgrade_resume_plan_is_valid(target, harness, plan):
        return set()
    operations = plan["operations"]
    return {
        relative for relative in changed
        if _upgrade_resume_path_matches(harness, target, operations, relative)
        and (not plan.get("completed_at") or any(
            row.get("kind") == "preserve" and isinstance(row.get("backup"), str)
            and (relative == row["backup"]
                 or relative.startswith(row["backup"] + "/"))
            for row in operations if isinstance(row, dict)
        ))
    }


def _complete_upgrade_resume(target: Path) -> None:
    """Seal the overall upgrade receipt only after every finalizer succeeds."""
    from factory_lib import dump_json, now_iso, validate_payload

    migrations = target / ".factory" / "migrations"
    manifests = [
        migrations / f"{LEAN_MIGRATION_VERSION}.json",
        migrations / LEAN_MIGRATION_SUPPLEMENT,
    ]
    for manifest in manifests:
        if not manifest.is_file() or manifest.is_symlink():
            continue
        saved = load_json(manifest, default={})
        if not isinstance(saved, dict):
            fail("overall upgrade resume manifest is malformed")
        plan = saved.get("upgrade_resume")
        if not isinstance(plan, dict) or plan.get("completed_at"):
            continue
        completed = {**saved, "upgrade_resume": {
            **plan, "completed_at": now_iso(),
        }}
        validate_payload(target, "lean-workflow-migration", completed)
        with tempfile.TemporaryDirectory(prefix="forge-upgrade-complete-") as temporary:
            built = Path(temporary) / manifest.name
            dump_json(built, completed)
            body = built.read_bytes()
            _publish_converted_stage(
                target, manifest, built,
                original_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                output_sha256=hashlib.sha256(body).hexdigest(),
            )
        if load_json(manifest, default={}) != completed:
            fail("overall upgrade completion readback differs")


def _cleanup_upgrade_preserve_backups(target: Path) -> None:
    """Remove the authenticated skill backups after the resume receipt is sealed."""
    migrations = target / ".factory" / "migrations"
    for name in (f"{LEAN_MIGRATION_VERSION}.json", LEAN_MIGRATION_SUPPLEMENT):
        manifest = migrations / name
        if not manifest.is_file() or manifest.is_symlink():
            continue
        saved = load_json(manifest, default={})
        plan = saved.get("upgrade_resume") if isinstance(saved, dict) else None
        if not isinstance(plan, dict) or not plan.get("completed_at"):
            continue
        if not _upgrade_resume_plan_is_valid(target, repo_root(), plan):
            fail("overall upgrade preservation backup plan is invalid")
        for row in plan.get("operations") or []:
            if not isinstance(row, dict) or row.get("kind") != "preserve":
                continue
            backup_relative = row.get("backup")
            if not isinstance(backup_relative, str):
                continue
            backup = target / backup_relative
            destination = target / row["path"]
            if _upgrade_path_identity(destination) != row.get("before"):
                fail(f"preserved upgrade path changed before backup cleanup: {row['path']}")
            _require_unlinked_path(target, backup.parent)
            identity = _upgrade_path_identity(backup)
            if identity.get("kind") == "missing":
                continue
            expected = row.get("before")
            partial_tree = (
                isinstance(expected, dict) and expected.get("kind") == "tree"
                and identity.get("kind") == "tree"
                and isinstance(expected.get("entries"), list)
                and isinstance(identity.get("entries"), list)
                and all(entry in expected["entries"]
                        for entry in identity["entries"])
            )
            if identity != expected and not partial_tree:
                fail(f"upgrade preservation backup changed: {backup_relative}")
            if identity.get("kind") == "tree":
                shutil.rmtree(assert_target_destination(target, backup))
            else:
                (assert_target_destination(target, backup.parent) / backup.name).unlink()
            root = target / UPGRADE_PRESERVED_ROOT
            parent = backup.parent
            while parent != root.parent:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent


def _record_upgrade_finalize_outputs(target: Path) -> None:
    """Bind exact finalizer output so resume rejects unrelated user edits."""
    from factory_lib import dump_json, validate_payload

    migrations = target / ".factory" / "migrations"
    manifests = [
        migrations / LEAN_MIGRATION_SUPPLEMENT,
        migrations / f"{LEAN_MIGRATION_VERSION}.json",
    ]
    for manifest in manifests:
        if not manifest.is_file() or manifest.is_symlink():
            continue
        saved = load_json(manifest, default={})
        if not isinstance(saved, dict):
            fail("overall upgrade resume manifest is malformed")
        plan = saved.get("upgrade_resume")
        if not isinstance(plan, dict) or plan.get("completed_at"):
            continue
        operations = plan.get("operations")
        if not isinstance(operations, list):
            fail("overall upgrade resume operations are malformed")
        bound_operations = []
        for row in operations:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str):
                fail("overall upgrade resume operation is malformed")
            bound_operations.append(
                {**row, "after": _upgrade_path_identity(target / row["path"])}
                if row.get("kind") == "finalize" else row
            )
        updated_plan = {**plan, "operations": bound_operations}
        updated_plan["plan_sha256"] = hashlib.sha256(json.dumps(
            bound_operations, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        updated = {**saved, "upgrade_resume": updated_plan}
        validate_payload(target, "lean-workflow-migration", updated)
        with tempfile.TemporaryDirectory(prefix="forge-upgrade-finalize-") as temporary:
            built = Path(temporary) / manifest.name
            dump_json(built, updated)
            body = built.read_bytes()
            _publish_converted_stage(
                target, manifest, built,
                original_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                output_sha256=hashlib.sha256(body).hexdigest(),
            )
        if load_json(manifest, default={}) != updated:
            fail("overall upgrade finalization readback differs")


def _upgrade_resume_preserved_mismatches(
        target: Path, harness: Path, saved: dict,
) -> list[str] | None:
    """Return preserved paths changed during an interrupted upgrade."""
    plan = saved.get("upgrade_resume")
    if (not isinstance(plan, dict) or plan.get("completed_at")
            or not _upgrade_resume_plan_is_valid(target, harness, plan)):
        return None
    mismatches = []
    for row in plan["operations"]:
        if row.get("kind") != "preserve":
            continue
        relative = row["path"]
        destination = target / relative
        _require_unlinked_path(target, destination.parent)
        if _upgrade_path_identity(destination) != row["before"]:
            backup_relative = row.get("backup")
            if (isinstance(backup_relative, str)
                    and _upgrade_path_identity(target / backup_relative)
                    == row["before"]
                    and _upgrade_path_identity(destination).get("kind") == "missing"):
                _restore_upgrade_backup(
                    target, target / backup_relative, destination,
                )
            if _upgrade_path_identity(destination) == row["before"]:
                continue
            mismatches.append(relative)
    return mismatches


def _recorded_lean_temporary_paths(
        target: Path, manifest: Path, saved: dict, candidates: set[str],
) -> set[str]:
    """Recognize only regular temp siblings of recorded migration outputs."""
    destinations = {manifest.relative_to(target).as_posix()}
    if not saved.get("completed_at"):
        converted = _resume_converted_outputs(saved)
        if converted is not None:
            destinations.update(converted)
    allowed = set()
    for relative in candidates:
        temporary = PurePosixPath(relative)
        for destination_relative in destinations:
            destination = _lean_manifest_path(target, destination_relative)
            if (temporary.parent.as_posix()
                    != destination.relative_to(target).parent.as_posix()
                    or re.fullmatch(
                        rf"\.{re.escape(destination.name)}\.\d+\.lean\.tmp",
                        temporary.name,
                    ) is None):
                continue
            path = _lean_manifest_path(target, relative)
            try:
                info = path.lstat()
            except OSError:
                continue
            if (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and not _linked_or_reparse(info)):
                allowed.add(relative)
                break
    return allowed


def _bound_lean_temporary_paths(target: Path, candidates: set[str]) -> set[str]:
    manifest = target / ".factory" / "migrations" / f"{LEAN_MIGRATION_VERSION}.json"
    supplemental = manifest.with_name(LEAN_MIGRATION_SUPPLEMENT)
    if supplemental.exists() or supplemental.is_symlink():
        manifest = supplemental
    if not manifest.exists() and not manifest.is_symlink():
        return set()
    try:
        _require_single_link_manifest(target, manifest)
        saved = load_json(manifest, default={})
        from factory_lib import validate_payload
        try:
            validate_payload(target, "lean-workflow-migration", saved)
        except (OSError, UnicodeError, json.JSONDecodeError, SystemExit):
            validate_payload(repo_root(), "lean-workflow-migration", saved)
    except (OSError, UnicodeError, json.JSONDecodeError, SystemExit):
        return set()
    if not isinstance(saved, dict) or saved.get("version") != LEAN_MIGRATION_VERSION:
        return set()
    return _recorded_lean_temporary_paths(target, manifest, saved, candidates)


def _incomplete_lean_resume_paths(
        target: Path, harness: Path, changed: set[str]) -> set[str]:
    """Return authenticated paths an interrupted Lean migration may dirty."""
    manifest = target / ".factory" / "migrations" / f"{LEAN_MIGRATION_VERSION}.json"
    supplemental = manifest.with_name(LEAN_MIGRATION_SUPPLEMENT)
    if not manifest.exists() and not manifest.is_symlink():
        if not supplemental.exists() and not supplemental.is_symlink():
            return set()
    if supplemental.exists() or supplemental.is_symlink():
        if not manifest.is_file() or manifest.is_symlink():
            return set()
        try:
            original = load_json(manifest, default={})
            if (not isinstance(original, dict)
                    or not _is_original_empty_completion(original)):
                return set()
        except (OSError, UnicodeError, json.JSONDecodeError):
            return set()
        manifest = supplemental
    _require_single_link_manifest(target, manifest)
    try:
        saved = load_json(manifest, default={})
        from factory_lib import validate_payload
        try:
            validate_payload(target, "lean-workflow-migration", saved)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, SystemExit):
            # An interrupted replacement may have removed target/factory before
            # the copy begins.  The authenticated harness clone carries the
            # same schema and is the only safe fallback for this pre-copy read.
            validate_payload(harness, "lean-workflow-migration", saved)
    except (OSError, UnicodeError, json.JSONDecodeError, SystemExit):
        return set()
    if not isinstance(saved, dict):
        return set()
    overall_incomplete = isinstance(saved.get("upgrade_resume"), dict) and not \
        saved["upgrade_resume"].get("completed_at")
    if overall_incomplete:
        preserved_mismatches = _upgrade_resume_preserved_mismatches(
            target, harness, saved,
        )
        if preserved_mismatches is None or preserved_mismatches:
            return set()
    overall_allowed = _authenticated_upgrade_resume_paths(
        target, harness, saved, changed,
    )
    if saved.get("completed_at") and overall_incomplete:
        return (overall_allowed | _recorded_lean_temporary_paths(
            target, manifest, saved, changed,
        )) if changed else set()
    if (saved.get("completed_at")
            and isinstance(saved.get("upgrade_resume"), dict)
            and saved["upgrade_resume"].get("completed_at")):
        return overall_allowed if changed else set()
    profile_replacements = _profile_replacement_hashes(saved)
    if profile_replacements is None:
        return set()
    for relative, expected_sha256 in profile_replacements.items():
        source = harness / relative
        try:
            source_sha256 = (None if source.is_symlink() or not source.is_file()
                             else hashlib.sha256(source.read_bytes()).hexdigest())
        except OSError:
            source_sha256 = None
        if source_sha256 != expected_sha256:
            return set()
    if manifest == supplemental:
        try:
            original = load_json(
                target / ".factory" / "migrations"
                / f"{LEAN_MIGRATION_VERSION}.json", default={},
            )
        except (OSError, UnicodeError, json.JSONDecodeError):
            return set()
        if (not isinstance(original, dict)
                or saved.get("prior_completion") != original
                or saved.get("prior_completion_digest")
                != _manifest_content_digest(original)):
            return set()
    entries = saved.get("entries")
    if (saved.get("version") != LEAN_MIGRATION_VERSION
            or saved.get("completed_at")
            or not isinstance(entries, list)
            or saved.get("input_inventory_digest") != _inventory_digest(entries)
            or saved.get("installed_runtime_digest")
            != _inventory_digest(saved.get("installed_runtime") or [])
            or saved.get("output_digest") != hashlib.sha256(json.dumps(
                saved.get("outputs") or [], sort_keys=True,
                separators=(",", ":"),
            ).encode()).hexdigest()):
        return set()
    converted = _resume_converted_outputs(saved)
    if converted is None:
        return set()
    converted_paths = {
        entry["path"] for entry in entries
        if isinstance(entry, dict)
        and entry.get("classification") == "eligible"
        and entry.get("family") == "legacy-stage-stamp"
    }
    if set(converted) != converted_paths:
        return set()
    try:
        primary = lean_primary_inventory(target)
        raw = lean_raw_inventory(target)
    except SystemExit:
        return set()
    if primary != raw:
        return set()
    current = {entry["path"]: entry for entry in primary}
    saved_paths: set[str] = set()
    for entry in entries:
        if (not isinstance(entry, dict)
                or not isinstance(entry.get("path"), str)
                or entry["path"] in saved_paths):
            return set()
        _lean_manifest_path(target, entry["path"])
        saved_paths.add(entry["path"])
        live = current.get(entry["path"])
        if live == entry:
            continue
        if entry.get("classification") == "eligible":
            if entry.get("family") == "legacy-stage-stamp":
                if (live is None
                        or live.get("classification") != "excluded"
                        or not _resume_stage_bytes_match(
                            target, entry["path"], converted.get(entry["path"], ""),
                        )):
                    return set()
                continue
            if (live is None and not (target / entry["path"]).exists()
                    and not (target / entry["path"]).is_symlink()):
                continue
        if (_is_harness_owned(entry["path"], harness)
                and _resume_harness_path_matches(
                    harness, target, entry["path"])):
            continue
        return set()
    allowed = {manifest.relative_to(target).as_posix()}
    for entry in entries:
        if entry.get("classification") == "eligible":
            allowed.add(entry["path"])
    for row in saved.get("outputs") or []:
        if (not isinstance(row, dict)
                or set(row) != {"story", "task_id", "generation_id",
                               "generation_sha256"}):
            return set()
        story, task, generation = (
            row.get("story"), row.get("task_id"), row.get("generation_id"),
        )
        if (not isinstance(story, str) or SAFE_COMPONENT.fullmatch(story) is None
                or not isinstance(task, str) or SAFE_COMPONENT.fullmatch(task) is None
                or not isinstance(generation, str)
                or re.fullmatch(r"[0-9a-f]{64}", generation) is None):
            return set()
        root = f".factory/stories/{story}/tasks/{task}/reviews"
        allowed.update({
            f"{root}/selected.json",
            f"{root}/generations/{generation}.json",
        })
    for relative in changed:
        if relative in allowed:
            continue
        if overall_incomplete and _upgrade_resume_path_matches(
                harness, target, saved["upgrade_resume"]["operations"], relative):
            allowed.add(relative)
            continue
        if _resume_harness_path_matches(harness, target, relative):
            allowed.add(relative)
            continue
    allowed.update(_recorded_lean_temporary_paths(
        target, manifest, saved, changed,
    ))
    return allowed


def _active_lean_migration_manifest(target: Path) -> dict | None:
    manifest = target / ".factory" / "migrations" / f"{LEAN_MIGRATION_VERSION}.json"
    supplemental = manifest.with_name(LEAN_MIGRATION_SUPPLEMENT)
    if supplemental.exists() or supplemental.is_symlink():
        manifest = supplemental
    try:
        if manifest.is_symlink() or not manifest.is_file():
            return None
        saved = load_json(manifest, default={})
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return saved if isinstance(saved, dict) else None


def _is_client_owned_upgrade_skill_path(relative: str, harness: Path) -> bool:
    parts = PurePosixPath(relative).parts
    if len(parts) < 3 or parts[:2] != ("factory", "skills"):
        return False
    skill = parts[2]
    return skill in {"proposed", "rejected"} or not (
        harness / "factory" / "skills" / skill
    ).exists()


def _only_harness_owned_upgrade_paths(changed: set[str], harness: Path) -> bool:
    resume_state = {
        f".factory/migrations/{LEAN_MIGRATION_VERSION}.json",
        f".factory/migrations/{LEAN_MIGRATION_SUPPLEMENT}",
    }
    return bool(changed) and all(
        relative in resume_state or (
            _is_harness_owned(relative, harness)
            and not _is_client_owned_upgrade_skill_path(relative, harness)
        )
        for relative in changed
    )


def _require_clean_upgrade_target(
        target: Path, *, allow_lean_resume: bool = False) -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=target, capture_output=True,
        text=True, encoding="utf-8", errors="surrogateescape",
    )
    if status.returncode != 0:
        fail(
            f"could not verify that {target} is clean; refusing upgrade: "
            f"{status.stderr.strip() or 'git status failed'}"
        )
    if allow_lean_resume:
        missing_preserved = _missing_preserved_upgrade_paths(
            target, repo_root(),
        )
        if missing_preserved:
            fail(
                "interrupted upgrade cannot resume because preserved path "
                f"is missing or changed: {missing_preserved[0]}"
            )
    dirty = status.stdout.strip()
    if dirty:
        if allow_lean_resume:
            changed = {
                candidate
                for line in status.stdout.splitlines()
                for candidate in [line[3:].split(" -> ")[-1].strip().strip('"')]
                if candidate
            }
            allowed = _incomplete_lean_resume_paths(
                target, repo_root(), changed,
            )
            if allowed and changed and changed <= allowed:
                return
            harness = repo_root()
            if _only_harness_owned_upgrade_paths(changed, harness):
                saved = _active_lean_migration_manifest(target)
                plan = saved.get("upgrade_resume") if saved else None
                if isinstance(plan, dict) and not plan.get("completed_at"):
                    try:
                        valid = _upgrade_resume_plan_is_valid(
                            target, harness, plan,
                        )
                    except SystemExit:
                        valid = False
                    if not valid:
                        recorded = plan.get("harness_commit")
                        label = (
                            recorded if isinstance(recorded, str) and re.fullmatch(
                                r"[0-9a-f]{40}|[0-9a-f]{64}", recorded,
                            ) else "<missing or invalid>"
                        )
                        fail(
                            "incomplete upgrade resume plan for harness commit "
                            f"{label} is invalid; reset/clean only the interrupted "
                            "harness-owned paths to HEAD, then rerun forge upgrade."
                        )
                if saved and saved.get("completed_at"):
                    fail(
                        "the Lean migration is complete, but a later upgrade was "
                        "interrupted; reset/clean only the changed harness-owned "
                        "paths to HEAD, then rerun forge upgrade."
                    )
        fail(
            f"{target} has uncommitted changes. Commit or stash first so the upgrade "
            "is a reviewable diff. Lean migration has no --force bypass."
        )


def _missing_preserved_upgrade_paths(target: Path, harness: Path) -> list[str]:
    manifest = target / ".factory" / "migrations" / f"{LEAN_MIGRATION_VERSION}.json"
    supplemental = manifest.with_name(LEAN_MIGRATION_SUPPLEMENT)
    if supplemental.exists() or supplemental.is_symlink():
        manifest = supplemental
    try:
        _require_single_link_manifest(target, manifest)
        saved = load_json(manifest, default={})
    except (OSError, UnicodeError, json.JSONDecodeError, SystemExit):
        return []
    if not isinstance(saved, dict):
        return []
    return _upgrade_resume_preserved_mismatches(target, harness, saved) or []


def cmd_upgrade(args: argparse.Namespace) -> None:
    harness = repo_root()
    target = Path(args.target).resolve()
    if not (target / ".git").exists() or not (target / "AGENTS.md").exists():
        fail(f"{target} does not look like a scaffolded repo (.git + AGENTS.md required)")
    if target == harness:
        fail("run upgrade FROM the harness clone TARGETING a client repo, not itself")
    # Refuse before writing: the sign-off carry below reads run.json AFTER the
    # machinery replacement, and a parse crash there leaves a half-upgraded
    # target. Unreadable state must stop the upgrade while it is untouched.
    legacy_run = target / ".factory" / "run.json"
    if legacy_run.exists() or legacy_run.is_symlink():
        try:
            if not isinstance(json.loads(legacy_run.read_text(encoding="utf-8")), dict):
                fail(f"{legacy_run} is not a JSON object; fix or delete it, then rerun")
        except json.JSONDecodeError as exc:
            fail(f"{legacy_run} is unreadable JSON ({exc}); fix or delete it, then rerun")
        except OSError as exc:
            fail(f"{legacy_run} is not a readable file ({exc}); fix or delete it, then rerun")
    _require_clean_upgrade_target(target, allow_lean_resume=True)
    from .delegate import delegation_exclusion

    with delegation_exclusion(
            target, "lean-upgrade", kind="review-selection", namespace="state"):
        _require_clean_upgrade_target(target, allow_lean_resume=True)
        _cmd_upgrade_locked(args, harness, target)


def _cmd_upgrade_locked(
        args: argparse.Namespace, harness: Path, target: Path) -> None:
    known_profile_hashes = _forge_profile_hashes(harness)
    _retired_profiles, preserved_profiles = _retired_forge_profiles(
        target, known_profile_hashes,
    )
    deferred_profile_replacements = _profile_replacement_candidates(
        harness, target,
    )
    profile_replacements_applied = False
    lean_migration = preflight_lean_migration(target)
    if lean_migration and lean_migration.get("resume") is True:
        deferred_profile_replacements = _profile_replacement_candidates(
            harness, target, lean_migration,
        )
        apply_lean_migration(
            target, lean_migration,
            profile_replacements=deferred_profile_replacements,
        )
        profile_replacements_applied = True
        print(f"Resumed and completed Lean migration in {target}")
        lean_migration = None
    _check_legacy_retirable(target, harness)

    # factory/skills is mixed ownership too: the `skills` CLI installs
    # project skills there (skills-lock.json repos like knacklabs-ats carry
    # a dozen). Preserve every child the harness does not ship, plus the
    # evolution dirs (proposed/rejected — client's version always wins).
    client_skill_dirs: list[str] = []
    carried_from_legacy: set[str] = set()
    preserve_sources: dict[str, Path] = {}
    target_skills = target / "factory" / "skills"
    legacy_skills = target / ".agents" / "skills"
    harness_skill_names = {p.name for p in (harness / "factory" / "skills").iterdir()} \
        if (harness / "factory" / "skills").is_dir() else set()
    if target_skills.is_dir():
        for child in target_skills.iterdir():
            rel = f"factory/skills/{child.name}"
            if child.name not in harness_skill_names and rel not in PRESERVE_IN_AGENTS:
                client_skill_dirs.append(rel)
    for rel in PRESERVE_IN_AGENTS + client_skill_dirs:
        src = target / rel
        # exists() is False for a DANGLING symlink, and a client skill can
        # legitimately be one. Without the is_symlink() arm it is never
        # preserved, so replacing factory/ deletes project-owned content.
        if src.exists() or src.is_symlink():
            preserve_sources[rel] = src
    # `is_dir()` follows symlinks: a symlinked skills root would have iterdir()
    # walk an external directory and copy its contents into factory/skills.
    if legacy_skills.is_dir() and not legacy_skills.is_symlink():
        for child in legacy_skills.iterdir():
            rel = f"factory/skills/{child.name}"
            # The current location wins when a name exists in BOTH. Copying the
            # legacy one on top would merge into whatever the first copy left
            # at that destination — and if that was a symlink, through it.
            if rel in preserve_sources:
                continue
            if child.name not in harness_skill_names or rel in PRESERVE_IN_AGENTS:
                preserve_sources[rel] = child
                carried_from_legacy.add(child.name)

    _preflight_upgrade(harness, target, preserve_sources)

    keep_root = Path(tempfile.mkdtemp(prefix="forge-upgrade-keep-"))
    preserved: dict[str, Path] = {}
    for rel, src in preserve_sources.items():
        dest = keep_root / rel
        _keep_path(keep_root, src, dest)
        preserved[rel] = dest

    preserve_backups = {
        relative: target / UPGRADE_PRESERVED_ROOT / relative
        for relative, source in preserve_sources.items()
        if (lean_migration is not None
            and relative.startswith("factory/skills/")
            and source.is_relative_to(target)
            and source.relative_to(target).as_posix() == relative)
    }
    if lean_migration is not None:
        _persist_prepared_lean_manifest(
            target, lean_migration, runtime_source=harness,
            profile_replacements=deferred_profile_replacements,
            preserve_sources=preserve_sources,
            preserve_backups=preserve_backups,
        )
        _backup_upgrade_skills(target, preserve_sources, preserve_backups)

    for tree in UPGRADE_TREES:
        src = harness / tree
        if not src.exists():
            continue
        dst = target / tree
        if dst.exists():
            shutil.rmtree(assert_target_destination(target, dst))
        guarded_copytree(target, src, dst, ignore=VENDOR_IGNORE, symlinks=False)
    # .claude is mixed ownership: replace only harness-shipped paths; the
    # client's own skills/agents/launch.json survive untouched.
    for rel in CLAUDE_HARNESS_OWNED:
        src = harness / ".claude" / rel
        if src.exists():
            _replace_path(target, src, target / ".claude" / rel)
    # .github/workflows/ is mixed ownership: refresh only the harness's own
    # factory workflows, file-by-file, so the project's other workflows survive.
    for rel in COPY_WORKFLOWS:
        src = harness / rel
        if src.exists():
            dst = target / rel
            assert_target_destination(target, dst.parent).mkdir(
                parents=True, exist_ok=True)
            shutil.copy2(src, assert_target_file_destination(target, dst))
    assert_target_destination(target, target / ".codex").mkdir(exist_ok=True)
    for name in COPY_CODEX:
        shutil.copy2(
            harness / ".codex" / name,
            assert_target_file_destination(target, target / ".codex" / name),
        )
    # Same mixed-ownership rule: refresh each harness-shipped agent and each
    # allowlisted harness skill; leave client-added entries alone.
    agents = harness / ".codex" / "agents"
    if agents.is_dir():
        for child in agents.iterdir():
            destination = target / ".codex" / "agents" / child.name
            if child.suffix == ".toml" and destination.is_file() \
                    and not destination.is_symlink():
                existing = hashlib.sha256(destination.read_bytes()).hexdigest()
                if (child.name in RETIRED_FORGE_PROFILE_HASHES
                        and existing == RETIRED_FORGE_PROFILE_HASHES[child.name]):
                    # Lean migration inventories and removes the exact old
                    # bytes. Install the current same-name role only after
                    # that durable removal so revalidation cannot mistake the
                    # replacement for tampered migration input.
                    if (child, destination) not in deferred_profile_replacements:
                        deferred_profile_replacements.append((child, destination))
                    continue
                if existing not in known_profile_hashes.get(child.name, set()):
                    # A same-name profile with unknown bytes is a distinct
                    # client profile. The current source still installs any
                    # missing role and refreshes known Forge versions.
                    continue
            _replace_path(
                target, child, destination)
    for rel in CODEX_HARNESS_OWNED_SKILLS:
        src = harness / rel
        if src.exists():
            _replace_path(target, src, target / rel)
    for name in UPGRADE_FILES:
        src = harness / name
        if src.exists():
            shutil.copy2(
                src, assert_target_file_destination(target, target / name))
    replaced_doc_contracts: list[str] = []
    diverged_doc_contracts: list[str] = []
    for src_rel, dst_rel in DOC_CONTRACTS:
        src = harness / src_rel
        if src.exists():
            dst = target / dst_rel
            replaced_doc_contracts.append(dst_rel)
            if (not dst.is_symlink() and dst.is_file()
                    and dst.read_bytes() != src.read_bytes()):
                diverged_doc_contracts.append(dst_rel)
            assert_target_destination(target, dst.parent).mkdir(
                parents=True, exist_ok=True)
            shutil.copy2(src, assert_target_file_destination(target, dst))

    for rel, kept in preserved.items():
        dst = target / rel
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(assert_target_destination(target, dst))
        elif dst.exists() or dst.is_symlink():
            (assert_target_destination(target, dst.parent) / dst.name).unlink()
        assert_target_destination(target, dst.parent).mkdir(
            parents=True, exist_ok=True)
        # Same symlink rule as _keep_path: a link kept as a link must come back
        # as a link, or the round trip quietly materializes its referent.
        if kept.is_dir() and not kept.is_symlink():
            guarded_copytree(target, kept, dst, symlinks=True)
        else:
            shutil.copy2(
                kept, assert_target_file_destination(target, dst),
                follow_symlinks=False,
            )
    shutil.rmtree(
        assert_target_destination(keep_root, keep_root), ignore_errors=True)

    if lean_migration is not None:
        apply_lean_migration(
            target, lean_migration,
            profile_replacements=deferred_profile_replacements,
        )
        profile_replacements_applied = True
    if not profile_replacements_applied:
        for source, destination in deferred_profile_replacements:
            _replace_path(target, source, destination)

    retired_legacy = _retire_legacy_agents(target)

    # Newer harness additions that older scaffolds predate: create-if-missing /
    # append-if-missing (never overwrite — projects may extend these files).
    ensured: list[str] = []
    if not (target / ".envrc").exists():
        shutil.copy2(
            harness / ".envrc",
            assert_target_file_destination(target, target / ".envrc"),
        )
        ensured.append(".envrc (run `direnv allow` in the repo)")
    if ensure_jsonl_attributes(target, harness):
        ensured.append(".gitattributes (missing JSONL merge rules added)")

    # Sign-off moved from a per-worktree run.json flag to a committed
    # harness.yaml pin. A project that signed off under the old scheme keeps
    # its project-owned harness.yaml (no key) and its old run.json, so carry
    # the attestation across rather than silently un-signing the project.
    manifest_yaml = target / "harness.yaml"
    if (manifest_yaml.exists() and not manifest_yaml.is_symlink()
            and not SIGNOFF_KEY.search(manifest_yaml.read_text(encoding="utf-8"))):
        manifest_yaml = assert_target_file_destination(target, manifest_yaml)
        legacy = load_json(target / ".factory" / "run.json", default={})
        carried = (legacy.get("client_signoff_record", "")
                   if legacy.get("client_signoff") else "")
        # Persist the CANONICAL path, never run.json's spelling: run.json is
        # gitignored, per-worktree, ungoverned state, and a value there can
        # resolve to a valid record yet be absolute (machine-specific) or carry
        # quotes/newlines that inject YAML into harness.yaml.
        #
        # NO inference from the decision corpus when it is missing: an accepted
        # client-signoff record is not evidence that sign-off HAPPENED (it can
        # be committed before record_signoff.py ever succeeds, and the required
        # grill leaves no committed trace). Absent legacy state stays unsigned,
        # which is exactly what the old scheme did in a fresh clone.
        carried = canonical_signoff_path(target, carried) if carried else ""
        manifest_yaml.write_text(
            insert_signoff_pin(manifest_yaml.read_text(encoding="utf-8"), carried), encoding="utf-8"
        )
        ensured.append(
            "harness.yaml signoff_record pin ("
            + (carried or "EMPTY — pin it with record_signoff.py [--record <path>]")
            + ")"
        )
    from .scaffold import ensure_onboarding
    if ensure_onboarding(target, target.name):
        ensured.append("README.md ('Working in this repo' onboarding section appended)")
    gitignore = assert_target_file_destination(target, target / ".gitignore")
    # The old blanket `.gstack/` rule hid the COMMITTED projects/ store
    # (WORKFLOW.md: design docs, decisions, learnings) — and git cannot
    # re-include inside an excluded directory, so the corrected block below
    # only takes effect once the blanket line is gone.
    if gitignore.exists():
        kept = [line for line in gitignore.read_text(encoding="utf-8").splitlines(keepends=True)
                if line.strip() != ".gstack/"]
        if "".join(kept) != gitignore.read_text(encoding="utf-8"):
            gitignore.write_text("".join(kept), encoding="utf-8")
            ensured.append(".gitignore (blanket .gstack/ rule removed — it hid "
                           "the committed projects/ store)")
    gstack_text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    # Exact LINE matches everywhere a marker is consulted: marker text quoted
    # inside a longer comment must not count as an installed block.
    if GSTACK_MARKER not in (line.strip() for line in gstack_text.splitlines()):
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(("\n" if gstack_text else "")
                     + GSTACK_MARKER + "\n"
                     + "".join(f"{rule}\n" for rule in GSTACK_RULES))
        ensured.append(".gitignore (gstack block appended)")
    # Decision 0025: briefs and the delegation mirror stay on disk (a running
    # task keeps reading them) but leave the tracked tree. --cached only, so
    # nothing is deleted; the staged untracking rides the client's next commit.
    # Keyed on the marker line, not on rule detection: probing (substring or
    # `git check-ignore`) kept mis-answering — comments, later `!` negations,
    # and machine-local ignore sources (global excludes, .git/info/exclude)
    # all look like installed rules while committing nothing for teammates.
    # The marker exists only where this block was installed (scaffold ships it
    # in .gitignore; upgrade appends it once, creating the file if absent).
    # Appended at the END: a directory rule there is total — git cannot
    # re-include files inside an excluded directory. A client who edits rules
    # under an existing marker has deliberately opted out, and upgrade
    # respects that — including in the untracking below, which touches ONLY
    # paths the committed rules actually ignore. Untracking an opted-back-in
    # path would delete teammates' copies of it on their next pull.
    ignore_text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    ignore_lines = [line.strip() for line in ignore_text.splitlines()]
    if EPHEMERAL_MARKER not in ignore_lines:
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(("\n" if ignore_text else "")
                     + EPHEMERAL_MARKER + "\n"
                     + "".join(f"{rel}\n" for rel in EPHEMERAL_UNTRACK))
        ensured.append(".gitignore (0025 ephemeral paths appended)")
        ignore_lines = [line.strip()
                        for line in gitignore.read_text(encoding="utf-8").splitlines()]
    # Only the marker-owned tail governs, last mention wins: a duplicate
    # positive rule elsewhere in the file must not override an opt-out made
    # under the marker (removing the rule, or negating it below the block).
    marker_tail = ignore_lines[ignore_lines.index(EPHEMERAL_MARKER) + 1:]

    # Exact-path spellings normalized (leading `!`/`/`, trailing `/`) — glob
    # spellings of these paths are outside the opt-out contract.
    def _opted_out(rel: str) -> bool:
        state = True
        for line in marker_tail:
            if line.lstrip("!").strip("/") == rel.strip("/"):
                state = line.startswith("!")
        return state

    to_untrack = [rel for rel in EPHEMERAL_UNTRACK if not _opted_out(rel)]
    untracked = subprocess.run(
        ["git", "-C", str(target), "rm", "-r", "--cached", "--ignore-unmatch",
         "--"] + to_untrack,
        capture_output=True, text=True,
        encoding="utf-8", errors="surrogateescape",
    ) if to_untrack else None
    if untracked and untracked.returncode != 0:
        raise SystemExit("could not untrack ephemeral .factory paths:\n"
                         + untracked.stderr)
    if untracked and untracked.stdout.strip():
        count = len(untracked.stdout.strip().splitlines())
        ensured.append(f"{count} ephemeral .factory file(s) untracked "
                       "(0025 — still on disk HERE, commit the staged removal; "
                       "TEAMMATES' pulls delete their clean local copies — a dev "
                       "mid-task recomposes the brief by re-running "
                       "./forge delegate <task-id>)")
    for rel in PROJECT_STARTERS:
        destination = target / rel
        if not destination.exists():
            assert_target_destination(target, destination.parent).mkdir(
                parents=True, exist_ok=True)
            shutil.copy2(
                harness / rel,
                assert_target_file_destination(target, destination),
            )
            ensured.append(rel)

    commit = head_sha(harness) or "unknown"
    assert_target_file_destination(
        target, target / "constitution" / "VENDORED_FROM").write_text(
        f"symphony-forge @ {commit}\nUpdate by re-vendoring from the harness repo; do not edit in place.\n", encoding="utf-8"
    )
    # Re-freeze the gate surface at the new vendoring (frozen-gate-integrity).
    from check_vendor_integrity import write_manifest
    write_manifest(target, commit)

    drift = ""
    # harness.yaml is PROJECT-owned, so an older scaffold may not have one at
    # all — which is the normal state of the legacy repos this command exists
    # to upgrade. Reading it unconditionally turned "you have no harness.yaml"
    # into a traceback at the very end of a successful upgrade.
    target_harness = target / "harness.yaml"
    if not target_harness.is_file():
        drift = ("\nNOTE: no harness.yaml in this repo — the phase contract falls "
                 "back to the harness default. Copy the harness's harness.yaml if "
                 "this project needs to own it.")
    elif (harness / "harness.yaml").read_text(encoding="utf-8") != target_harness.read_text(encoding="utf-8"):
        drift = ("\nNOTE: harness.yaml differs from the harness default (project-owned, "
                 "left untouched) — diff manually if the phase contract changed upstream.")
    print(f"Upgraded {target} to symphony-forge @ {commit[:8]}")
    migration_paths = (
        target / ".factory" / "migrations" / f"{LEAN_MIGRATION_VERSION}.json",
        target / ".factory" / "migrations" / LEAN_MIGRATION_SUPPLEMENT,
    )
    has_legacy_plan_approval = any(
        isinstance(manifest, dict)
        and any(entry.get("family") == "manual-plan-approval"
                for entry in manifest.get("entries") or []
                if isinstance(entry, dict))
        for path in migration_paths
        for manifest in [load_json(path, default={})]
    )
    if has_legacy_plan_approval:
        try:
            from .approval import ApprovalRefused, eligible_candidates
            candidate = next((item for item in eligible_candidates(target)
                              if item.kind == "story"), None)
        except (ApprovalRefused, OSError, ValueError, SystemExit):
            candidate = None
        if candidate is not None:
            plan_file = candidate.path.relative_to(target).as_posix()
            print(f"Next: re-approve {plan_file} in native Plan Mode after upgrade.")
    print("Replaced (harness-owned): "
          + ", ".join(UPGRADE_TREES + UPGRADE_FILES + COPY_WORKFLOWS))
    print("Replaced doc contracts: " + ", ".join(replaced_doc_contracts))
    if diverged_doc_contracts:
        paths = " ".join(diverged_doc_contracts)
        print("WARNING: replaced doc contracts differed from the new template: "
              + ", ".join(diverged_doc_contracts)
              + f". Review the upgrade with git diff -- {paths}")
    if ensured:
        print("Added (missing on this older scaffold): " + ", ".join(ensured))
    print("Untouched (project-owned): " + ", ".join(PROJECT_OWNED) + drift)
    if retired_legacy:
        print("Retired legacy machinery: .agents/")
    from .scaffold import remediate_windows_hook_entry
    remediate_windows_hook_entry(target)
    _record_upgrade_finalize_outputs(target)
    stale_references = _stale_agents_references(
        target, harness, sorted(preserved), carried_from_legacy)
    # The scan reads the index, which equals the working tree only because the
    # dirty-target gate held. --force bypasses that gate, so uncommitted edits
    # and untracked files are outside what was searched — say so rather than
    # printing a definitive answer the scan cannot support.
    caveat = ""
    if stale_references:
        print(f"Project-owned files still referencing .agents/{caveat}:")
        for rel in stale_references:
            print(f"  {rel}")
    else:
        print(f"Project-owned files still referencing .agents/: none{caveat}")
    if preserved_profiles:
        print("Preserved client-modified retired profile names: "
              + ", ".join(path.name for path in preserved_profiles))
    print("Next: review with `git diff`, run `python3 factory/scripts/check_dual_runtime.py` "
          "and the gate tests, then commit.")
    _complete_upgrade_resume(target)
    _cleanup_upgrade_preserve_backups(target)
