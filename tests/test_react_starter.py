"""A new client React app starts with React Compiler on and no hand-written memoization."""
import json
import re
from pathlib import Path

STORY = "FORGE-REACTDEFAULTS-1"

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "src" / "forge" / "templates" / "starter"


def test_1_a_new_app_starts_with_react_compiler_on():
    package = json.loads((STARTER / "package.json").read_text(encoding="utf-8"))
    assert package["devDependencies"].get("babel-plugin-react-compiler") == "1.0.0"

    web = STARTER / "apps" / "web"
    for config in ("vite.config.ts", "vitest.config.ts"):
        assert "babel-plugin-react-compiler" in (web / config).read_text(encoding="utf-8"), config
    lint = (STARTER / "eslint.config.mjs").read_text(encoding="utf-8")
    assert "reactHooks.configs.flat.recommended" in lint

    ui = web / "src" / "components" / "ui"
    memoized = [
        path.relative_to(web).as_posix()
        for path in (web / "src").rglob("*")
        if path.suffix in (".ts", ".tsx") and not path.is_relative_to(ui)
        and re.search(r"useMemo|useCallback|memo\(", path.read_text(encoding="utf-8"))
    ]
    assert not memoized, f"hand-written memoization outside components/ui: {memoized}"
