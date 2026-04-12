#!/bin/sh
set -eu

NEXT_DIR="/app/.next"

replace() {
  local placeholder="$1"
  local var_name="$2"

  eval "local value=\${${var_name}:-}"

  if [ -z "$value" ]; then
    return
  fi

  # Escape special sed characters in the value
  local escaped_value
  escaped_value=$(printf '%s' "$value" | sed 's/[&|\\]/\\&/g')

  find "$NEXT_DIR" -type f \( -name '*.js' -o -name '*.html' \) \
    -exec sed -i "s|${placeholder}|${escaped_value}|g" {} +
}

echo "[entrypoint] Replacing NEXT_PUBLIC_* placeholders …"

replace "PANDAPROBE_PLACEHOLDER_API_URL"                   "NEXT_PUBLIC_API_URL"
replace "PANDAPROBE_PLACEHOLDER_AUTH_ENABLED"               "NEXT_PUBLIC_AUTH_ENABLED"
replace "PANDAPROBE_PLACEHOLDER_FIREBASE_API_KEY"           "NEXT_PUBLIC_FIREBASE_API_KEY"
replace "PANDAPROBE_PLACEHOLDER_FIREBASE_AUTH_DOMAIN"       "NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN"
replace "PANDAPROBE_PLACEHOLDER_FIREBASE_PROJECT_ID"        "NEXT_PUBLIC_FIREBASE_PROJECT_ID"
replace "PANDAPROBE_PLACEHOLDER_FIREBASE_STORAGE_BUCKET"    "NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET"
replace "PANDAPROBE_PLACEHOLDER_FIREBASE_MESSAGING_SENDER_ID" "NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID"
replace "PANDAPROBE_PLACEHOLDER_FIREBASE_APP_ID"            "NEXT_PUBLIC_FIREBASE_APP_ID"
replace "PANDAPROBE_PLACEHOLDER_FIREBASE_MEASUREMENT_ID"    "NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID"

echo "[entrypoint] Done. Starting Next.js server …"

exec node server.js
