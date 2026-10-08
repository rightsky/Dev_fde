#!/usr/bin/env bash
# FDE Data Studio 복원 — backup.sh 로 만든 폴더에서 DB 와 업로드 파일을 되돌린다. 지금 데이터는 지워진다.
# 사용 (프로젝트 폴더에서, 서비스가 떠 있는 상태): ./scripts/restore.sh backups/20261008-203000
set -euo pipefail
backup="$(cd "${1:?복원할 백업 폴더를 지정하세요}" && pwd)"
cd "$(dirname "$0")/.."
for f in fde.dump storage.tgz; do [ -f "$backup/$f" ] || { echo "$backup 에 $f 가 없습니다" >&2; exit 1; }; done
echo "복원할 백업: $backup"
read -r -p "지금 데이터를 모두 지우고 이 백업으로 되돌립니다. 계속하려면 yes 를 입력하세요: " answer
[ "$answer" = "yes" ] || { echo "취소했습니다."; exit 1; }

# docker compose cp 로 넣은 파일은 root 소유라 백엔드 사용자(fde)가 지울 수 없다. 풀기는 root 로 하고 소유자를 fde 로 돌린다
echo "1/3 업로드 파일 되돌리는 중..."
docker compose cp "$backup/storage.tgz" backend:/tmp/storage.tgz
docker compose exec -T -u root backend sh -c "find /data/storage -mindepth 1 -delete && tar xzf /tmp/storage.tgz -C /data/storage && chown -R fde /data/storage && rm -f /tmp/storage.tgz"

echo "2/3 데이터베이스 되돌리는 중 (백엔드 잠시 중지)..."
docker compose stop backend
docker compose cp "$backup/fde.dump" db:/tmp/fde.dump
docker compose exec -T db pg_restore -U fde -d fde --clean --if-exists --no-owner --exit-on-error /tmp/fde.dump
docker compose exec -T db rm -f /tmp/fde.dump

echo "3/3 백엔드 다시 시작..."
docker compose start backend
echo
echo "복원 완료. 브라우저를 새로 고치세요."
