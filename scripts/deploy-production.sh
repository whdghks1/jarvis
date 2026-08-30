#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$project_dir/.env.production"
compose_file="$project_dir/compose.production.yml"
release_apk="$project_dir/releases/JARVIS.apk"

if [[ ! -f "$env_file" ]]; then
  echo ".env.production이 없습니다. .env.production.example을 복사해 작성하세요." >&2
  exit 1
fi

if [[ ! -f "$release_apk" ]]; then
  echo "releases/JARVIS.apk가 없습니다. 로컬에서 scripts/prepare-release.sh를 실행하세요." >&2
  exit 1
fi

cd "$project_dir"
docker compose --env-file "$env_file" -f "$compose_file" up -d --build
docker compose --env-file "$env_file" -f "$compose_file" ps
echo "배포 완료. 로컬 상태 확인: curl http://127.0.0.1:8000/ready"
