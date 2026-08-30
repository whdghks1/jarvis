#!/usr/bin/env bash
set -euo pipefail

if ! command -v tailscale >/dev/null 2>&1; then
  echo "Tailscale이 없습니다. 먼저 https://tailscale.com/download/linux 에 따라 설치하세요." >&2
  exit 1
fi

sudo tailscale serve --bg 8000
tailscale serve status

echo "표시된 https://...ts.net 주소를 Android 앱의 서버 주소로 입력하세요."
