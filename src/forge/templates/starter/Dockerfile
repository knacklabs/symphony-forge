FROM node:24-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
RUN mkdir -p /app && chown node:node /app
WORKDIR /app
USER node
COPY --chown=node:node package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY --chown=node:node apps/api/package.json ./apps/api/package.json
COPY --chown=node:node apps/web/package.json ./apps/web/package.json
COPY --chown=node:node libs/auth/contracts/package.json ./libs/auth/contracts/package.json
COPY --chown=node:node libs/auth/server/package.json ./libs/auth/server/package.json
COPY --chown=node:node libs/core/server/package.json ./libs/core/server/package.json
COPY --chown=node:node libs/core/web/package.json ./libs/core/web/package.json
COPY --chown=node:node libs/history/contracts/package.json ./libs/history/contracts/package.json
COPY --chown=node:node libs/history/server/package.json ./libs/history/server/package.json
COPY --chown=node:node libs/mcp/server/package.json ./libs/mcp/server/package.json
COPY --chown=node:node libs/notifications/contracts/package.json ./libs/notifications/contracts/package.json
COPY --chown=node:node libs/notifications/server/package.json ./libs/notifications/server/package.json
COPY --chown=node:node libs/organisations/contracts/package.json ./libs/organisations/contracts/package.json
COPY --chown=node:node libs/organisations/server/package.json ./libs/organisations/server/package.json
COPY --chown=node:node libs/projects/contracts/package.json ./libs/projects/contracts/package.json
COPY --chown=node:node libs/projects/server/package.json ./libs/projects/server/package.json
COPY --chown=node:node libs/shared/ui/package.json ./libs/shared/ui/package.json
COPY --chown=node:node libs/shared/util/package.json ./libs/shared/util/package.json
RUN corepack pnpm install --frozen-lockfile
COPY --chown=node:node . .
RUN corepack pnpm run build

ENV NODE_ENV=production
EXPOSE 3000
CMD ["sh", "-c", "corepack pnpm exec prisma migrate deploy || { echo 'Database migration failed. Check DATABASE_URL and the migration, then redeploy.' >&2; exit 1; }; exec corepack pnpm run start:prod"]
