# 운영 배포 안내 (상시 호스팅 · HTTPS · 자동 백업)

Codespaces 는 켜 둔 동안만 살아 있고 주소도 바뀝니다. 상시 서비스는 **리눅스 서버 1대 + Docker Compose + Caddy(자동 HTTPS) + 매일 백업 cron** 으로 올립니다. 로컬 PC · Codespaces 에서 쓰던 것과 같은 `docker compose` 명령이라 운영 방법이 달라지지 않습니다. `docs/N2SF-CONTROLS.md` 4절 체크리스트가 이 절차의 보안 점검표입니다.

## 0. 준비물

| 항목 | 설명 |
|---|---|
| 서버 | Ubuntu 22.04 또는 24.04, 2 vCPU · 4GB RAM · 40GB 디스크 이상. 공인 IP 와 **80 · 443 포트 인바운드 허용**. (클라우드: 네이버클라우드 · KT · NHN · AWS Lightsail · Oracle 등 어디든 같음) |
| 도메인 | 예: `data.example.go.kr`. DNS 에 **A 레코드 → 서버 공인 IP** 를 먼저 등록 (Caddy 가 인증서를 받으려면 도메인이 서버를 가리키고 있어야 함) |
| 접속 | 서버에 SSH 로 들어갈 수 있는 계정 (root 또는 sudo) |
| 선택 | Anthropic API 키 (AI 초안 · 시뮬레이션을 쓸 때만) |

## 1. 설치 (서버에서 한 번)

SSH 로 서버에 들어간 뒤 아래 한 줄. 도메인과 메일 주소만 바꿉니다 (메일은 인증서 만료 안내용).

```bash
curl -fsSL https://raw.githubusercontent.com/rightsky/Dev_fde/main/deploy/install.sh | sudo bash -s -- data.example.go.kr admin@example.go.kr
```

하는 일: Docker 설치 → `/opt/fde-data-studio` 에 저장소 받기 → `.env` 생성(무작위 비밀번호 · 비밀키) → HTTPS 프록시 포함 기동 → 매일 03:10 백업 cron 등록(14일 보존). 끝나면 **관리자 비밀번호가 화면에 한 번 출력**되므로 적어 두세요.

브라우저에서 `https://도메인` 을 열면 됩니다. 처음 1분은 인증서 발급 중일 수 있습니다.

## 2. API 키 넣기 (AI 기능을 쓸 때)

```bash
sudo nano /opt/fde-data-studio/.env
```

`FDE_ANTHROPIC_API_KEY=` 뒤에 키를 붙여 넣고 저장(Ctrl+O, Enter, Ctrl+X) 한 뒤:

```bash
cd /opt/fde-data-studio && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 3. 판 올리기 (새 PR 머지 뒤)

```bash
cd /opt/fde-data-studio && sudo git pull && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

DB 이관은 기동할 때 자동으로 적용됩니다. 올리기 전에 백업을 한 번 더 받으려면 `sudo ./scripts/backup.sh`.

## 4. 백업과 복원

- 자동: 매일 03:10 `backups/날짜시각/` 에 DB 덤프(`fde.dump`)와 업로드 원본(`storage.tgz`)을 저장, 14일 지난 폴더는 삭제. 기록은 `backups/backup.log`.
- 보존 기간 변경: `/etc/cron.d/fde-backup` 의 줄에 `FDE_BACKUP_KEEP_DAYS=30` 을 앞에 붙입니다.
- **서버 밖으로 복사**: 서버 디스크가 죽으면 백업도 같이 사라지므로, `backups/` 를 기관 파일서버나 오브젝트 스토리지로 매일 복사하는 작업을 추가하세요 (rsync · rclone 등 기관 표준 도구). 예: `rsync -a /opt/fde-data-studio/backups/ 백업서버:/fde-backups/`
- 복원: `sudo ./scripts/restore.sh backups/20261017-031000` (서비스가 떠 있는 상태에서 실행, 현재 데이터를 덮어씁니다).

## 5. 운영 점검 명령

| 할 일 | 명령 |
|---|---|
| 상태 보기 | `sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` |
| 로그 보기 | `sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail 200 backend` |
| 접속 로그 | `sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec caddy tail -f /data/access.log` |
| 재시작 | `... restart backend` |
| 디스크 | `df -h /` 와 `sudo du -sh /var/lib/docker /opt/fde-data-studio/backups` |

## 6. 보안 설정 (기본값과 바꾸는 법)

`.env` 에서 바꾸고 2절의 `up -d` 로 반영합니다.

| 항목 | 기본값 | 뜻 |
|---|---|---|
| `FDE_EXPOSE_API_DOCS` | `false` | `/api/docs` · `/api/openapi.json` 을 닫음. Caddy 도 같은 경로를 404 로 막아 이중 차단 |
| `FDE_SHARE_PROHIBITED` | `block` | 표 41 공유 불가 데이터셋은 외부 발행 제외 |
| `FDE_REVIEW_SELF_APPROVE` | `note` | 본인 승인 허용(사유 기록). 금지하려면 `deny` |
| `FDE_AI_RATE_PER_MINUTE` / `_PER_DAY` | `6` / `200` | 사용자별 AI 호출 상한 |
| `FDE_CORS_ORIGINS` | (없음) | 같은 도메인에서만 쓰므로 비워 둠 |
| `FDE_BASE_IRI` | `https://도메인` | 발행 IRI 기준. 기관 공식 카탈로그 주소가 따로 있으면 그걸로 |

Caddy 는 HSTS · nosniff · frame 차단 헤더를 붙이고 Let's Encrypt 인증서를 자동 갱신합니다. 서버 방화벽은 22(SSH) · 80 · 443 만 열어 두세요. DB(5432)와 백엔드(8000)는 컨테이너 내부 망에만 있고 밖으로 열리지 않습니다.

## 7. MCP 를 외부 에이전트에 열 때

주소는 `https://도메인/api/mcp` 입니다. 관리 화면의 "연결 방법"에 나오는 명령에서 `http://localhost:8080` 을 이 주소로 바꾸면 됩니다. 키는 HTTPS 로만 오가므로 평문 HTTP 는 열지 않습니다. S2 데이터셋은 키 등급에 더해 건별 승인이 필요합니다.

## 8. 대안: PaaS (Render · Fly.io)

서버를 직접 두기 어려우면 Render 나 Fly.io 에 올릴 수 있지만, 세 컨테이너(화면 · 백엔드 · DB)와 업로드 보관 볼륨을 각각 설정해야 하고, 관리형 PostgreSQL 은 무료 구간이 만료되면 유료입니다. 운영 부담은 서버 1대 + 이 안내가 더 적습니다. PaaS 로 가야 하면 그때 해당 서비스용 설정 파일(render.yaml / fly.toml)을 따로 만듭니다.

## 9. 문제 해결

| 증상 | 확인 |
|---|---|
| `https://도메인` 이 안 열림 · 인증서 오류 | DNS A 레코드가 서버 IP 를 가리키는지(`nslookup 도메인`), 80 · 443 이 열려 있는지. Caddy 로그: `... logs caddy` |
| 로그인 뒤 금방 풀림 | `.env` 의 `FDE_SECRET_KEY` 가 비어 있지 않은지 (비어 있으면 재기동마다 바뀜) |
| 업로드 실패 (413) | `FDE_MAX_UPLOAD_MB` 와 nginx `client_max_body_size`(300m) 확인 |
| 백업이 안 돎 | `sudo cat /etc/cron.d/fde-backup`, `tail backups/backup.log`, `sudo systemctl status cron` |
