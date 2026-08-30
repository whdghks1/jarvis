#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$project_dir/.env.production"
compose_file="$project_dir/compose.production.yml"
backup_dir="$project_dir/backups"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$backup_dir/jarvis-$timestamp.sql.gz"

if [[ ! -f "$env_file" ]]; then
  echo ".env.production이 없습니다." >&2
  exit 1
fi

mkdir -p "$backup_dir"
cd "$project_dir"
docker compose --env-file "$env_file" -f "$compose_file" exec -T db \
  sh -c 'pg_dump --clean --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "$backup_file"
find "$backup_dir" -type f -name 'jarvis-*.sql.gz' -mtime +14 -delete
echo "백업 완료: $backup_file"
