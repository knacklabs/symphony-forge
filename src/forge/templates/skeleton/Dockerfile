FROM node:24-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN npm ci && npm run build

ENV NODE_ENV=production
EXPOSE 3000
CMD ["sh", "-c", "npx prisma migrate deploy || { echo 'Database migration failed. Check DATABASE_URL and the migration, then redeploy.' >&2; exit 1; }; exec npm run start:prod"]
