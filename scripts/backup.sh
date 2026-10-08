#!/usr/bin/env bash
# FDE Data Studio 백업 — DB(PostgreSQL) 덤프와 업로드 원본 파일을 backups/날짜시각 폴더에 저장한다.
# 사용 (프로젝트 폴더에서, 서비스가 떠 있는 상태): ./scripts/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
dir="backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$dir"

echo "1/2 데이터베이스 덤프 중..."
docker compose exec -T db pg_dump -U fde -d fde -Fc -f /tmp/fde.dump
docker compose cp db:/tmp/fde.dump "$dir/fde.dump"
docker compose exec -T db rm -f /tmp/fde.dump

echo "2/2 업로드 파일 묶는 중..."
docker compose exec -T backend tar czf /tmp/storage.tgz -C /data/storage .
docker compose cp backend:/tmp/storage.tgz "$dir/storage.tgz"
docker compose exec -T backend rm -f /tmp/storage.tgz

echo
echo "백업 완료: $dir"
ls -l "$dir"
