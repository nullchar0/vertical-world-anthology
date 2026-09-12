#!/usr/bin/env bash
# Push / create this repo as nullchar0 without switching the global active gh account.
set -euo pipefail
cd "$(dirname "$0")/.."

# Pin this repository to nullchar0 (does not change global active account).
git config --local github.account nullchar0 || true
git config --local user.name nullchar0 || true
git config --local credential.https://github.com.username nullchar0 || true

if ! gh auth status -h github.com 2>/dev/null | grep -qi 'nullchar0'; then
  echo "nullchar0 is not logged into gh yet."
  echo "Keep SillyHatsOnly as the active/default account, then ADD nullchar0:"
  echo "  gh auth login -h github.com"
  exit 1
fi

TOKEN="$(gh auth token --user nullchar0)"
export GH_TOKEN="$TOKEN"
export GITHUB_TOKEN="$TOKEN"

REPO="nullchar0/vertical-world-anthology"

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Creating $REPO and pushing…"
  gh repo create vertical-world-anthology --public --source=. --remote=origin --push
else
  echo "Pushing to origin…"
  git push -u origin HEAD
fi

# Enable GitHub Pages from /docs if not already configured
if ! gh api "repos/${REPO}/pages" >/dev/null 2>&1; then
  echo "Enabling GitHub Pages (/docs)…"
  gh api -X POST "repos/${REPO}/pages" \
    -f build_type=legacy \
    -f source[branch]=main \
    -f source[path]=/docs \
    || true
fi

echo "Done. Site: https://nullchar0.github.io/vertical-world-anthology/"
