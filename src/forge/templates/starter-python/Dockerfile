FROM node:24-bookworm-slim AS web-build

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/package.json
COPY libs/auth/contracts/package.json ./libs/auth/contracts/package.json
COPY libs/core/web/package.json ./libs/core/web/package.json
COPY libs/history/contracts/package.json ./libs/history/contracts/package.json
COPY libs/organisations/contracts/package.json ./libs/organisations/contracts/package.json
COPY libs/projects/contracts/package.json ./libs/projects/contracts/package.json
COPY libs/shared/api-types/package.json ./libs/shared/api-types/package.json
COPY libs/shared/ui/package.json ./libs/shared/ui/package.json
COPY libs/shared/util/package.json ./libs/shared/util/package.json
RUN corepack pnpm install --frozen-lockfile
COPY . .
RUN corepack pnpm run build

FROM python:3.14-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/
WORKDIR /app/apps/api
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app
COPY --chown=app:app apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev
COPY --chown=app:app apps/api/ ./
COPY --from=web-build /app/apps/web/dist /app/apps/web/dist

ENV PYTHONPATH=/app/apps/api
EXPOSE 3000
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head || { echo 'Database migration failed. Check DATABASE_URL and the migration, then redeploy.' >&2; exit 1; }; exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-3000}\" --no-access-log"]
