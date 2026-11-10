#!/usr/bin/env bash
# Copy the newsletter site files and shared assets from master to gh-pages.
#   portal/newsletter/  → gh-pages:newsletter/
#   portal/assets/      → gh-pages:assets/      (logo used by e-mails, absolute URL)
# Uses a separate worktree so the master checkout is never switched.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
WT="$(mktemp -d)"
git fetch -q origin gh-pages
git worktree add -q -B gh-pages-sync "$WT" origin/gh-pages
trap 'git -C "$ROOT" worktree remove --force "$WT" >/dev/null 2>&1 || true' EXIT

for dir in newsletter assets; do
  if [ -d "$ROOT/portal/$dir" ]; then
    mkdir -p "$WT/$dir"
    cp -R "$ROOT/portal/$dir/." "$WT/$dir/"
  fi
done

cd "$WT"
git add newsletter assets 2>/dev/null || true
if git diff --cached --quiet; then
  echo "gh-pages already up to date (newsletter/assets)."
  exit 0
fi
git commit -q -m "newsletter: sync to gh-pages — $(date -u +'%Y-%m-%d %H:%M UTC')"
for i in 1 2 3; do
  if git pull -q --rebase origin gh-pages && git push -q origin HEAD:gh-pages; then
    echo "gh-pages updated (newsletter/assets)."
    exit 0
  fi
  sleep $((i * 5))
done
echo "Failed to push to gh-pages" >&2
exit 1
