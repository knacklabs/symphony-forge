"""Copy the Python assistant storage template into a new client app."""

import shutil
from pathlib import Path


def copy_assistant_python(app: Path) -> None:
    """Apply the Python README steps to an app created by ``forge init``."""
    skill = app / ".codex" / "skills" / "agents" / "assistant-module" / "python"
    if not skill.exists():
        skill = app / ".claude" / "skills" / "agents" / "assistant-module" / "python"
    if not skill.is_dir():
        raise AssertionError(f"the assistant template is missing from {skill}")

    api = app / "apps" / "api"
    shutil.copytree(
        skill / "apps" / "api" / "app" / "assistant", api / "app" / "assistant"
    )
    shutil.copyfile(
        skill / "apps" / "api" / "migrations" / "versions" / "20261106_assistant.py",
        api / "migrations" / "versions" / "20261106_assistant.py",
    )
    for test in (skill / "apps/api/tests").glob("test_assistant_*.py"):
        shutil.copyfile(test, api / "tests" / test.name)
    shutil.copytree(skill / "libs/assistant/contracts", app / "libs/assistant/contracts")
    _replace_once(
        app / "package.json",
        "tsc --build libs/shared/util/tsconfig.json",
        "tsc --build libs/assistant/contracts/tsconfig.json libs/shared/util/tsconfig.json",
    )
    _replace_once(
        api / "tests" / "test_module_schemas.py",
        "EXPECTED_TABLE_SCHEMAS = (\n",
        "EXPECTED_TABLE_SCHEMAS = (\n"
        '    "assistant.chat",\n'
        '    "assistant.checkpoint_blobs",\n'
        '    "assistant.checkpoint_migrations",\n'
        '    "assistant.checkpoint_writes",\n'
        '    "assistant.checkpoints",\n',
    )

    pyproject = api / "pyproject.toml"
    _replace_once(
        pyproject,
        '    "mcp==2.3.0",',
        '    "mcp==2.3.0",\n    "langgraph-checkpoint-postgres==3.2.0",\n    "langgraph==1.2.20",',
    )
    _replace_once(
        pyproject,
        "[tool.mypy]\n",
        "[[tool.importlinter.contracts]]\n"
        'name = "assistant internals"\n'
        'type = "protected"\n'
        'protected_modules = ["app.assistant.*"]\n'
        'allowed_importers = ["app.assistant"]\n'
        'broken_contract_guidance = "Use the assistant public service."\n\n'
        "[tool.mypy]\n",
    )

    migration_env = api / "migrations" / "env.py"
    _replace_once(
        migration_env,
        "from alembic import context\n",
        "from alembic import context\n"
        "from alembic.runtime.environment import NameFilterParentNames, NameFilterType\n",
    )
    _replace_once(
        migration_env,
        "import app.auth\n",
        "import app.assistant\nimport app.auth\n",
    )
    _replace_once(
        migration_env,
        "def run_migrations_offline() -> None:\n",
        "def include_name(\n"
        "    name: str | None,\n"
        "    type_: NameFilterType,\n"
        "    parent_names: NameFilterParentNames,\n"
        ") -> bool:\n"
        "    return not (\n"
        '        type_ == "table"\n'
        '        and parent_names.get("schema_name") == "assistant"\n'
        "        and name\n"
        "        in {\n"
        '            "checkpoints",\n'
        '            "checkpoint_blobs",\n'
        '            "checkpoint_writes",\n'
        '            "checkpoint_migrations",\n'
        "        }\n"
        "    )\n\n\n"
        "def run_migrations_offline() -> None:\n",
    )
    _replace_once(
        migration_env,
        "\n        include_schemas=True,\n",
        "\n        include_schemas=True,\n        include_name=include_name,\n",
    )
    _replace_once(
        migration_env,
        "\n            include_schemas=True,\n",
        "\n            include_schemas=True,\n            include_name=include_name,\n",
    )

    main = api / "app" / "main.py"
    _replace_once(
        main,
        "from app.auth import router as auth_router\n",
        "from app.assistant import assistant_lifespan\n"
        "from app.assistant import router as assistant_router\n"
        "from app.auth import router as auth_router\n",
    )
    _replace_once(
        main,
        "app.include_router(auth_router)",
        "app.include_router(auth_router)\napp.include_router(assistant_router)",
    )
    _replace_once(
        main,
        "        async with manager.run():\n            yield\n",
        "        async with assistant_lifespan(\n"
        "            session_factory, settings.database_url, settings.app_env\n"
        "        ) as checkpoints:\n"
        "            application.state.assistant_checkpoints = checkpoints\n"
        "            async with manager.run():\n"
        "                yield\n",
    )


def prepare_assistant_python_run(app: Path) -> None:
    """Refresh both copied manifests before the real starter checks run."""
    script = app / "scripts/test.mjs"
    _replace_once(
        script,
        "  run(corepack, ['pnpm', 'install', '--frozen-lockfile']);",
        "  run(corepack, ['pnpm', 'install', '--no-frozen-lockfile']);",
    )
    sync = "  run('uv', ['--directory', 'apps/api', 'sync', '--frozen']);"
    _replace_once(
        script,
        sync,
        "  const previousFrozen = environment.UV_FROZEN;\n"
        "  environment.UV_FROZEN = '0';\n"
        "  run('uv', ['--directory', 'apps/api', 'lock']);\n"
        "  environment.UV_FROZEN = previousFrozen;\n" + sync,
    )


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise AssertionError(f"copy step did not match one location in {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")
