FROM node:24-bookworm-slim AS manifests

WORKDIR /source
COPY . .
RUN node -e 'const fs = require("node:fs"), path = require("node:path"); for (const file of fs.globSync("**/package.json")) { const target = path.join("../manifests", file); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.copyFileSync(file, target); }'

FROM node:24-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
RUN mkdir -p /app && chown node:node /app
WORKDIR /app
USER node
COPY --chown=node:node pnpm-lock.yaml pnpm-workspace.yaml ./
COPY --from=manifests --chown=node:node /manifests/ ./
RUN corepack pnpm install --frozen-lockfile
COPY --chown=node:node . .
RUN corepack pnpm run build

ENV NODE_ENV=production
EXPOSE 3000
CMD ["sh", "-c", "corepack pnpm exec prisma migrate deploy || { echo 'Database migration failed. Check DATABASE_URL and the migration, then redeploy.' >&2; exit 1; }; exec corepack pnpm run start:prod"]
