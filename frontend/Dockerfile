FROM node:20-alpine AS base
WORKDIR /app

# ── Install production + dev dependencies (no Playwright browsers) ───────────
FROM base AS deps
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

# ── Dev target (docker-compose.dev.yml) ────────────
FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["yarn", "dev"]

# ── Production build ─────────────────────────────────────────────────────────
FROM base AS builder
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN yarn build

# ── Production runner (standalone output only — minimal image) ───────────────
FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
