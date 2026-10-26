"""Ship client app skills, check shadcn/ui additions and validate services lists."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from forge import repo

REFUSALS = {
    "services": ("services.toml {problem}.",
                 "fix services.toml to match the Dockerfiles, then forge close {item}"),
    "shadcn": ("This app uses shadcn/ui only, and this change adds {problems}.",
               "use the shadcn/ui component (npx shadcn@4.21.4 add <name>) and remove the copy "
               "or the library, then forge close {item}"),
}
# Component libraries, not the primitives and utilities used by shadcn/ui itself.
LIBRARIES = frozenset({
    "@mui/material", "@mui/joy", "@chakra-ui/react", "antd", "@mantine/core",
    "@nextui-org/react", "@heroui/react", "react-bootstrap", "bootstrap",
    "semantic-ui-react", "primereact", "rsuite", "grommet", "evergreen-ui",
    "baseui", "theme-ui", "rebass", "@fluentui/react", "@fluentui/react-components",
    "@blueprintjs/core", "@headlessui/react", "daisyui", "flowbite-react",
})
COMPONENTS = frozenset("""
    accordion alert alert-dialog aspect-ratio avatar badge breadcrumb button button-group
    calendar card carousel chart checkbox collapsible combobox command context-menu
    data-table date-picker dialog drawer dropdown-menu empty field form hover-card input
    input-group input-otp item kbd label menubar native-select navigation-menu pagination
    popover progress radio-group resizable scroll-area select separator sheet sidebar
    skeleton slider sonner spinner switch table tabs textarea toast toggle toggle-group
    tooltip typography
""".split())


def check(top: Path, cfg: dict[str, Any], base: str) -> None:
    """Refuse only libraries and named component copies added by this change."""
    if cfg.get("repo") != "client":
        return
    paths = repo.git("ls-tree", "-r", "--name-only", "-z", "HEAD", cwd=top).split("\0")
    if not any(PurePosixPath(path).name == "components.json" for path in paths):
        return

    def libraries(ref: str) -> set[str]:
        found = set()
        for path in repo.git("ls-tree", "-r", "--name-only", "-z", ref, cwd=top).split("\0"):
            if PurePosixPath(path).name == "package.json":
                package = json.loads(repo.git("show", f"{ref}:{path}", cwd=top))
                for group in ("dependencies", "devDependencies"):
                    found.update(LIBRARIES.intersection(package.get(group, {})))
        return found

    problems = sorted(libraries("HEAD") - libraries(base))
    names = {name.replace("-", "") for name in COMPONENTS}
    for path in repo.git("diff", "--name-only", "-z", "--no-renames", "--diff-filter=A",
                         base, "HEAD", cwd=top).split("\0"):
        file = PurePosixPath(path)
        ui = any(parts == ("components", "ui") for parts in zip(file.parts, file.parts[1:]))
        if file.suffix in (".tsx", ".jsx") and not ui and file.stem.lower().replace("-", "") in names:
            problems.append(path)
    if problems:
        repo.refuse(REFUSALS["shadcn"], problems="; ".join(problems),
                    item=repo.current_branch(top).partition("/")[2])


def services(top: Path, cfg: dict[str, Any]) -> None:
    """Check the committed list against this branch's committed Dockerfiles."""
    if cfg.get("repo") != "client":
        return
    paths = set(repo.git("ls-tree", "-r", "--name-only", "-z", "HEAD", cwd=top).split("\0")) - {""}
    if "services.toml" not in paths:
        return
    item = repo.current_branch(top).partition("/")[2]
    try:
        listed = tomllib.loads(repo.git("show", "HEAD:services.toml", cwd=top)).get("service", [])
    except tomllib.TOMLDecodeError as error:
        repo.refuse(REFUSALS["services"], problem=f"is not valid TOML: {error}", item=item)
    if not isinstance(listed, list):
        listed = []
    problems = []
    main = 0
    # ponytail: no port, health, command or subdomain checks; add one when a deploy shows the need.
    for service in listed:
        dockerfile = service.get("dockerfile") if isinstance(service, dict) else None
        if not isinstance(dockerfile, str):
            problems.append("has a service with no dockerfile")
        elif dockerfile not in paths:
            problems.append(f"names {dockerfile}, which this branch does not have")
        main += isinstance(service, dict) and service.get("expose") == "main"
    if main != 1:
        problems.append(f'has {main} services with expose = "main"; it needs exactly one')
    if problems:
        repo.refuse(REFUSALS["services"], problem="; ".join(problems), item=item)


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    skill = sync._synced_text(".codex/skills/app-baseline/SKILL.md",
                              "skills/app-baseline/SKILL.md")
    database = (sync.TEMPLATES / "skills/database/SKILL.md").read_text(encoding="utf-8")
    return {f"{host}/skills/{name}/SKILL.md": text
            for host in (".claude", ".codex")
            for name, text in (("app-baseline", skill), ("database", database))}
