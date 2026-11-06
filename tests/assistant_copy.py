"""Copy the optional assistant module into a new TypeScript starter app."""
import json
import shutil
from pathlib import Path


def copy_assistant(app: Path) -> None:
    """Apply the TypeScript README steps to an app created by `forge init`."""
    skill = app / ".codex" / "skills" / "agents" / "assistant-module" / "typescript"
    if not skill.exists():
        skill = app / ".claude" / "skills" / "agents" / "assistant-module" / "typescript"
    if not skill.is_dir():
        raise AssertionError(f"the assistant template is missing from {skill}")

    shutil.copytree(skill / "libs" / "assistant", app / "libs" / "assistant")
    shutil.copyfile(
        skill / "apps" / "api" / "prisma" / "schema" / "assistant.prisma",
        app / "apps" / "api" / "prisma" / "schema" / "assistant.prisma",
    )
    shutil.copytree(
        skill / "apps" / "api" / "prisma" / "migrations" / "20261106000000_assistant",
        app / "apps" / "api" / "prisma" / "migrations" / "20261106000000_assistant",
    )
    shutil.copytree(
        skill / "apps" / "api" / "prisma" / "migrations" / "20261106010000_assistant_usage",
        app / "apps" / "api" / "prisma" / "migrations" / "20261106010000_assistant_usage",
    )
    shutil.copyfile(
        skill / "apps" / "api" / "test" / "assistant-chats.e2e-spec.ts",
        app / "apps" / "api" / "test" / "assistant-chats.e2e-spec.ts",
    )
    shutil.copyfile(
        skill / "apps" / "api" / "test" / "assistant-model.e2e-spec.ts",
        app / "apps" / "api" / "test" / "assistant-model.e2e-spec.ts",
    )
    shutil.copyfile(
        skill / "apps" / "api" / "test" / "assistant-api.e2e-spec.ts",
        app / "apps" / "api" / "test" / "assistant-api.e2e-spec.ts",
    )

    base_schema = app / "apps" / "api" / "prisma" / "schema" / "base.prisma"
    _replace_once(
        base_schema,
        'schemas  = ["core", "history", "mcp", "notifications", "projects"]',
        'schemas  = ["assistant", "core", "history", "mcp", "notifications", "projects"]',
    )
    _replace_once(app / "prisma.config.ts", "export default defineConfig({\n", (
        "export default defineConfig({\n"
        "  experimental: { externalTables: true },\n"
        "  tables: { external: [\n"
        "    'assistant.checkpoints', 'assistant.checkpoint_blobs',\n"
        "    'assistant.checkpoint_writes', 'assistant.checkpoint_migrations',\n"
        "  ] },\n"
    ))
    organisations = app / "apps" / "api" / "prisma" / "schema" / "organisations.prisma"
    _replace_once(organisations, "  notifications       Notification[]\n", (
        "  notifications       Notification[]\n"
        "  assistantChats      AssistantChat[]\n"
    ))
    auth = app / "apps" / "api" / "prisma" / "schema" / "auth.prisma"
    _replace_once(auth, "  deletedProjects   Project[] @relation(\"ProjectDeletedBy\")\n", (
        "  deletedProjects   Project[] @relation(\"ProjectDeletedBy\")\n"
        "  createdChats      AssistantChat[] @relation(\"ChatCreatedBy\")\n"
        "  modifiedChats     AssistantChat[] @relation(\"ChatModifiedBy\")\n"
        "  assistantUsage    AssistantUsage[]\n"
    ))

    api_package = app / "apps" / "api" / "package.json"
    _edit_json(api_package, lambda data: data["dependencies"].update({
        "@app/assistant-server": "workspace:*",
        "@langchain/langgraph-checkpoint-postgres": "1.1.2",
    }))
    api_tsconfig = app / "apps" / "api" / "tsconfig.json"
    _edit_json(api_tsconfig, lambda data: data["references"].append({
        "path": "../../libs/assistant/server",
    }))
    root_package = app / "package.json"
    def edit_root_package(data):
        data["dependencies"].update({"zod": "4.3.6"})
        data["dependencies"]["@langchain/langgraph-checkpoint-postgres"] = "1.1.2"
        data["scripts"].update({
            "assistant:setup": (
                "pnpm --filter @app/assistant-server exec node --input-type=module -e "
                "\"import { PostgresSaver } from '@langchain/langgraph-checkpoint-postgres'; "
                "const saver = PostgresSaver.fromConnString(process.env.DATABASE_URL, "
                "{ schema: 'assistant' }); try { await saver.setup(); } "
                "finally { await saver.end(); }\""
            ),
        })
    _edit_json(root_package, edit_root_package)
    eslint_config = app / "eslint.config.mjs"
    _replace_once(
        eslint_config,
        "          { sourceTag: 'scope:notifications', onlyDependOnLibsWithTags: ['scope:notifications', 'scope:core', 'scope:shared', 'type:contracts'] },\n",
        "          { sourceTag: 'scope:notifications', onlyDependOnLibsWithTags: ['scope:notifications', 'scope:core', 'scope:shared', 'type:contracts'] },\n"
        "          { sourceTag: 'scope:assistant', onlyDependOnLibsWithTags: ['scope:assistant', 'scope:core', 'scope:shared', 'type:contracts'] },\n",
    )
    dockerfile = app / "Dockerfile"
    _replace_once(
        dockerfile,
        "; exec corepack pnpm run start:prod\"]",
        "; corepack pnpm run assistant:setup || { echo 'Assistant storage setup failed. Check DATABASE_URL and the assistant package.' >&2; exit 1; }; exec corepack pnpm run start:prod\"]",
    )
    app_module = app / "apps" / "api" / "src" / "app.module.ts"
    _replace_once(
        app_module,
        "    ConfigModule.forRoot({ isGlobal: true, validate: validateEnvironment }),\n",
        "    ConfigModule.forRoot({ isGlobal: true, validate: values => ({ ...values, ...validateEnvironment(values) }) }),\n",
    )
    _replace_once(app_module, "import { Module } from '@nestjs/common';\n", (
        "import { Module } from '@nestjs/common';\n"
        "import { AssistantModule } from '@app/assistant-server';\n"
    ))
    _replace_once(app_module, "    HealthModule,\n", (
        "    HealthModule,\n"
        "    AssistantModule,\n"
    ))
    # The copied app has six additional tables even when the module is not
    # imported. Keep the exact catalog check and include their owning schema.
    _replace_once(app / "apps/api/test/database.e2e-spec.ts",
                  "      Notification: 'notifications',\n", (
        "      Notification: 'notifications',\n"
        "      AssistantChat: 'assistant',\n"
        "      AssistantUsage: 'assistant',\n"
        "      checkpoints: 'assistant', checkpoint_blobs: 'assistant',\n"
        "      checkpoint_writes: 'assistant', checkpoint_migrations: 'assistant',\n"
    ))


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise AssertionError(f"copy step did not match one location in {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def _edit_json(path: Path, edit) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
