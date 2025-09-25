#!/usr/bin/env bash
set -Eeuo pipefail
url="$(git remote get-url origin 2>/dev/null || true)"
if [ -z "$url" ]; then
  echo "找不到 git origin，略過"; exit 0
fi
# 擷取 USER/REPO
clean="${url%.git}"
if [[ "$clean" =~ github.com[:/]+([^/]+)/([^/]+)$ ]]; then
  user="${BASH_REMATCH[1]}"; repo="${BASH_REMATCH[2]}"
  tmp="$(mktemp)"
  sed -E "s#github.com/USER/REPO#github.com/${user}/${repo}#g; s#codecov.io/gh/USER/REPO#codecov.io/gh/${user}/${repo}#g" README.md > "$tmp"
  mv "$tmp" README.md
  echo "已更新徽章為 ${user}/${repo}"
else
  echo "非 GitHub 遠端或無法解析：$url"
fi
