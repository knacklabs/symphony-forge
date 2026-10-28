FROM node:24-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /app
COPY . .
RUN corepack pnpm install --frozen-lockfile && corepack pnpm run build

ENV NODE_ENV=production
EXPOSE 3000
CMD ["sh", "-c", "corepack pnpm exec prisma migrate deploy || { echo 'Database migration failed. Check DATABASE_URL and the migration, then redeploy.' >&2; exit 1; }; exec corepack pnpm run start:prod"]
