FROM node:20-alpine AS base
RUN apk add --no-cache libc6-compat
WORKDIR /app

# ── Install all dependencies (dev + prod) ────────────────────────────────────
FROM base AS deps
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

# ── Dev target (docker-compose.dev.yml) ──────────────────────────────────────
# src/ and public/ are bind-mounted at runtime; only node_modules and config
# files need to be baked into the image.
FROM base AS dev
COPY --from=deps /app/node_modules ./node_modules
COPY package.json next.config.ts tsconfig.json postcss.config.mjs ./
EXPOSE 3000
CMD ["yarn", "dev"]

# ── Production build ─────────────────────────────────────────────────────────
FROM base AS builder
ENV NEXT_TELEMETRY_DISABLED=1

# NEXT_PUBLIC_* vars are baked into the JS bundle at build time.
# At container startup, docker-entrypoint.sh replaces these with real
# values from the runtime environment.
ENV NEXT_PUBLIC_API_URL=PANDAPROBE_PLACEHOLDER_API_URL
ENV NEXT_PUBLIC_AUTH_ENABLED=PANDAPROBE_PLACEHOLDER_AUTH_ENABLED
ENV NEXT_PUBLIC_FIREBASE_API_KEY=PANDAPROBE_PLACEHOLDER_FIREBASE_API_KEY
ENV NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=PANDAPROBE_PLACEHOLDER_FIREBASE_AUTH_DOMAIN
ENV NEXT_PUBLIC_FIREBASE_PROJECT_ID=PANDAPROBE_PLACEHOLDER_FIREBASE_PROJECT_ID
ENV NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=PANDAPROBE_PLACEHOLDER_FIREBASE_STORAGE_BUCKET
ENV NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=PANDAPROBE_PLACEHOLDER_FIREBASE_MESSAGING_SENDER_ID
ENV NEXT_PUBLIC_FIREBASE_APP_ID=PANDAPROBE_PLACEHOLDER_FIREBASE_APP_ID
ENV NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=PANDAPROBE_PLACEHOLDER_FIREBASE_MEASUREMENT_ID

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN yarn build

# ── Production runner (standalone output — minimal image) ────────────────────
FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --chown=nextjs:nodejs scripts/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
