#!/bin/bash
# Codespace 가 처음 만들어질 때 한 번 실행: .env 를 임시 값으로 만들고 전체를 띄운다
set -e
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  {
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 12)"
    echo "FDE_SECRET_KEY=$(openssl rand -hex 32)"
    echo "FDE_ADMIN_USERNAME=admin"
    echo "FDE_ADMIN_PASSWORD=admin-$(openssl rand -hex 4)"
    echo "FDE_ANTHROPIC_API_KEY="
    echo "FDE_AI_MODEL=claude-opus-5-5"
  } > .env
  echo ".env 를 새로 만들었습니다. 관리자 비밀번호: $(grep '^FDE_ADMIN_PASSWORD=' .env | cut -d= -f2-)"
fi
docker compose up -d --build
echo
echo "준비 끝. 왼쪽 아래 '포트' 탭에서 8080 을 열거나, 자동으로 열린 브라우저 탭을 보세요."
echo "로그인: $(grep '^FDE_ADMIN_USERNAME=' .env | cut -d= -f2-) / $(grep '^FDE_ADMIN_PASSWORD=' .env | cut -d= -f2-)"
