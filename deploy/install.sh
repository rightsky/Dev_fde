#!/usr/bin/env bash
# FDE Data Studio 운영 서버 1회 설치 (Ubuntu 22.04/24.04, root 또는 sudo 가능 계정).
# 하는 일: Docker 설치 → 저장소 받기 → .env 생성(무작위 비밀값) → HTTPS 프록시 포함 기동 → 매일 백업 cron 등록.
# 사용: curl -fsSL https://raw.githubusercontent.com/rightsky/Dev_fde/main/deploy/install.sh | sudo bash -s -- data.example.go.kr admin@example.go.kr
set -euo pipefail
DOMAIN="${1:-}"; EMAIL="${2:-}"
REPO="${FDE_REPO:-https://github.com/rightsky/Dev_fde.git}"
DIR="${FDE_DIR:-/opt/fde-data-studio}"
if [ -z "$DOMAIN" ]; then echo "사용법: install.sh <도메인> [인증서 안내 메일]"; exit 1; fi

echo "1/5 Docker 설치 확인"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
docker compose version >/dev/null

echo "2/5 저장소 받기 → $DIR"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull --ff-only; else git clone "$REPO" "$DIR"; fi
cd "$DIR"

echo "3/5 .env 준비"
if [ ! -f .env ]; then
  {
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
    echo "FDE_SECRET_KEY=$(openssl rand -hex 32)"
    echo "FDE_ADMIN_USERNAME=admin"
    echo "FDE_ADMIN_PASSWORD=admin-$(openssl rand -hex 5)"
    echo "FDE_ANTHROPIC_API_KEY="
    echo "FDE_AI_MODEL=claude-opus-5-5"
    echo "FDE_BASE_IRI=https://$DOMAIN"
    echo "FDE_DOMAIN=$DOMAIN"
    echo "FDE_ACME_EMAIL=$EMAIL"
    echo "FDE_EXPOSE_API_DOCS=false"
    echo "FDE_SHARE_PROHIBITED=block"
    echo "FDE_REVIEW_SELF_APPROVE=note"
    echo "FDE_TIMEZONE=Asia/Seoul"
  } > .env
  chmod 600 .env
  echo "  .env 를 새로 만들었습니다 (관리자 비밀번호는 마지막에 출력)."
else
  grep -q '^FDE_DOMAIN=' .env || echo "FDE_DOMAIN=$DOMAIN" >> .env
  grep -q '^FDE_ACME_EMAIL=' .env || echo "FDE_ACME_EMAIL=$EMAIL" >> .env
  grep -q '^FDE_EXPOSE_API_DOCS=' .env || echo "FDE_EXPOSE_API_DOCS=false" >> .env
  echo "  기존 .env 를 그대로 씁니다."
fi

echo "4/5 기동 (HTTPS 프록시 포함)"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait --wait-timeout 300

echo "5/5 매일 03:10 백업 cron 등록 (14일 보존)"
chmod +x deploy/backup-cron.sh scripts/backup.sh scripts/restore.sh
cat > /etc/cron.d/fde-backup <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
10 3 * * * root cd $DIR && ./deploy/backup-cron.sh
CRON
chmod 644 /etc/cron.d/fde-backup

echo
echo "준비 끝. 브라우저에서 https://$DOMAIN 을 여세요 (인증서 발급에 1분쯤 걸릴 수 있습니다)."
echo "로그인: $(grep '^FDE_ADMIN_USERNAME=' .env | cut -d= -f2-) / $(grep '^FDE_ADMIN_PASSWORD=' .env | cut -d= -f2-)"
echo "AI 초안을 쓰려면 $DIR/.env 의 FDE_ANTHROPIC_API_KEY= 뒤에 키를 넣고 다음을 실행: cd $DIR && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
