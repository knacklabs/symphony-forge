"""A diff too big for one prompt is reviewed in passes over the whole task.

Decision 0078 dealt such a diff into file groups: each reviewer held one
file and was asked to judge the whole task, and on WF-BIO-1 T4 fifty
one-file groups invented "partial" verdicts on code that had passed. Decision
0081 removed grouping and refused the prompt instead, which made a big task
unsealable. A pass is the opposite shape of a group: every pass reads the
same brief, contracts and journal with the whole tree readable; only the
diff bytes are split, into contiguous slices in git's order; a pass judges
findings on what it holds and gives verdicts only for contracts bound to
files it holds (or bound to none); the passes merge into one generation
with one stamp. The number of passes depends on the diff alone, never on
the brief, and a warning says how many ran. A single path that does not
fit a pass by itself is generated content for the noise list, and that
alone is still refused.
"""
from __future__ import annotations

import copy

from .common import fail


def plan_passes(sizes: dict[str, int], capacity: int) -> list[list[str]]:
    """Contiguous slices of the changed paths, in git's order, each within
    `capacity` bytes of diff."""
    if capacity <= 0:
        fail("the review brief and prompt alone exceed the tool's limit; there is "
             "no room for any diff. Trim what the brief carries (0080).")
    too_big = sorted((path for path, size in sizes.items() if size > capacity),
                     key=lambda path: -sizes[path])
    if too_big:
        fail("one path alone exceeds the room a review pass has for diff "
             f"({capacity // 1000} KB): "
             + ", ".join(f"{path} ({sizes[path] // 1000} KB)" for path in too_big[:5])
             + ". A file that size is generated content: add it to the review noise "
             "list (review_bundle) so it ships with its bytes unreviewed.")
    passes: list[list[str]] = []
    current: list[str] = []
    used = 0
    for path, size in sizes.items():
        if current and used + size > capacity:
            passes.append(current)
            current, used = [], 0
        current.append(path)
        used += size
    if current:
        passes.append(current)
    return passes


def pass_note(index: int, total: int, held: list[str], others: list[str],
              task: dict) -> str:
    """What one pass is told: what it holds, what it does not, and which
    contracts are its to verdict."""
    contracts = [c for c in task.get("plan_contracts") or [] if isinstance(c, dict)]
    held_set = set(held)
    mine = sorted(str(c.get("id")) for c in contracts
                  if not c.get("lands_in") or c.get("lands_in") in held_set)
    theirs = sorted(str(c.get("id")) for c in contracts
                    if c.get("lands_in") and c.get("lands_in") not in held_set)
    return (
        f"REVIEW PASS {index} OF {total}. The task's diff did not fit one prompt, so "
        f"it is reviewed in {total} passes over the SAME task: every pass reads the "
        "same brief, contracts and journal with the whole tree readable; only the "
        "diff bytes are split.\n"
        f"This pass holds the diff for: {', '.join(held)}.\n"
        f"Not in this pass (another pass holds them): {', '.join(others) or 'none'}.\n"
        "Findings only on what this pass holds. Contract verdicts: give one for "
        + (", ".join(mine) if mine else "no contract")
        + (f"; give NONE for {', '.join(theirs)}, whose files another pass holds"
           if theirs else "")
        + ". Never call code missing because its diff is not in this pass: read the tree."
    )


def merge_pass_reports(passes: list[dict]) -> dict:
    """One helper wrapper from N pass results, in the shape the projection
    already reads (pass_reports, merged findings in order, worst correctness):
    the tool's own chunked shape, produced by the harness so the chunker is
    never reached."""
    from .review import _helper_bounded_field, _tagged_finding
    total = len(passes)
    if total < 2:
        fail("merge_pass_reports needs at least two passes")
    findings: list[dict] = []
    seen: set = set()
    set_aside: list[dict] = []
    for index, report in enumerate(passes, 1):
        label = f"chunk {index}/{total}"
        for finding in report.get("findings") or []:
            _lens, _clean, _fingerprint, merge_key = _tagged_finding(finding)
            if merge_key in seen:
                continue
            seen.add(merge_key)
            merged = copy.deepcopy(finding)
            merged["body"] = _helper_bounded_field(f"{label}:\n\n{merged['body']}", 2000)
            findings.append(merged)
        set_aside.extend(copy.deepcopy(report.get("scope_rejected_findings") or []))
    incorrect = bool(findings) or any(
        report.get("overall_correctness") == "patch is incorrect" for report in passes)
    wrapper = {
        "pass_reports": [{"label": f"chunk {index}/{total}", "report": report}
                         for index, report in enumerate(passes, 1)],
        "findings": findings,
        "overall_correctness": "patch is incorrect" if incorrect else "patch is correct",
        "overall_explanation": f"Review ran in {total} passes over the whole task.",
        "overall_confidence": min(float(report.get("overall_confidence") or 0)
                                  for report in passes),
        "review_status": ("incomplete" if set_aside else
                          "findings" if findings else "scoped-clean"),
    }
    if set_aside:
        wrapper["scope_rejected_findings"] = set_aside
    return wrapper
