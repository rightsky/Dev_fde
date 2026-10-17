#!/usr/bin/env bash
# 매일 자동 백업 (cron 용). scripts/backup.sh 를 돌리고 보존 기간이 지난 백업 폴더를 지운다.
# 설치: deploy/install.sh 가 /etc/cron.d/fde-backup 에 등록한다 (매일 03:10, 14일 보존).
set -euo pipefail
cd "$(dirname "$0")/.."
KEEP_DAYS="${FDE_BACKUP_KEEP_DAYS:-14}"
./scripts/backup.sh >> backups/backup.log 2>&1
find backups -maxdepth 1 -mindepth 1 -type d -mtime +"$KEEP_DAYS" -exec rm -rf {} + 2>/dev/null || true
echo "$(date '+%F %T') 백업 완료, ${KEEP_DAYS}일 이전 삭제" >> backups/backup.log
