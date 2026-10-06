"""Done-when 4's fallback keeps the existing approval command and trust checks."""
from test_story import DOC, claude_plan, hook, ready, setup

STORY = "FORGE-MOD-1-APPROVE"


def test_4_plan_mode_approval_still_records_and_refuses_changed_docs(repo, claude_payload):
    setup(repo)
    story = ready(repo, 'SHOP')
    shown = claude_plan(claude_payload, DOC)
    changed = DOC.replace('save a basket', 'share a basket')
    (story / 'plans/SHOP.md').write_text(changed, encoding='utf-8')
    assert repo.forge('read', 'SHOP').returncode == 0
    before = repo.git('rev-parse', 'story/SHOP')
    refused = hook(repo, shown)
    assert refused.returncode == 1
    assert 'may have changed since it was shown' in refused.stderr
    assert repo.git('rev-parse', 'story/SHOP') == before
    # Real Claude 2.1.291 mod-call result: accepting the generic exit prompt
    # returned no plan, rather than the supplied story text.
    payload = claude_payload('PostToolUse', 'ExitPlanMode', {},
                             {'plan': None, 'isAgent': False, 'filePath': '/plans/session.md'})
    refused = hook(repo, payload)
    assert refused.returncode == 1
    assert "doesn't match the approval contract" in refused.stderr
    assert repo.git('rev-parse', 'story/SHOP') == before
    current = claude_plan(claude_payload, changed)
    approved = hook(repo, current)
    assert approved.returncode == 0, approved.stderr
    assert 'Recorded the approval' in approved.stdout
    assert 'forge task start SHOP/SAVE' in repo.forge('next').stdout
    assert 'already recorded once' in hook(repo, current).stderr
