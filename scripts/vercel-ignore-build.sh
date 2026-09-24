#!/usr/bin/env bash

# Vercel skips the build when this script exits 0 and builds when it exits 1.
# Skip commits that only change AI-service files; build for core/shared changes.

if ! git rev-parse --verify HEAD^ >/dev/null 2>&1; then
  echo "No parent commit available; proceeding with the Vercel build."
  exit 1
fi

changed_paths="$(git diff --name-only HEAD^ HEAD)" || {
  echo "Could not inspect the commit diff; proceeding with the Vercel build."
  exit 1
}

while IFS= read -r path; do
  [ -z "$path" ] && continue

  case "$path" in
    ai/*|ai_service/*|.dockerignore|Dockerfile.ai|requirements-ai.txt|render.yaml|scripts/reindex_kb.py|scripts/enable_pgvector.sql|README.md|FRONTEND_INTEGRATION_GUIDE.md|.env.example|workspace_ai_implementation/*)
      ;;
    *)
      echo "Core/shared change detected ($path); proceeding with the Vercel build."
      exit 1
      ;;
  esac
done <<< "$changed_paths"

echo "Only AI-service or documentation files changed; skipping the Vercel build."
exit 0
