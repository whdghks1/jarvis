#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$project_dir/.env.production"
compose_file="$project_dir/compose.production.yml"
backup_file="${1:-}"
confirmation="${2:-}"

if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
  echo "사용법: $0 backups/jarvis-날짜.sql.gz --yes" >&2
  exit 1
fi

if [[ "$confirmation" != "--yes" ]]; then
  echo "복원은 현재 DB 내용을 변경합니다. 확인하려면 두 번째 인자로 --yes를 전달하세요." >&2
  exit 1
fi

cd "$project_dir"
gzip -dc "$backup_file" | docker compose --env-file "$env_file" \
  -f "$compose_file" exec -T db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"'
echo "복원 완료: $backup_file"
