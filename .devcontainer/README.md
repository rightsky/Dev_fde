# GitHub Codespaces 에서 FDE Data Studio 띄우기

내 PC 에 Docker 를 설치하지 않고, GitHub 가 띄워 주는 클라우드 컴퓨터에서 바로 돌립니다.

## 처음 한 번

1. GitHub 저장소 페이지 → 초록 **Code** 버튼 → **Codespaces** 탭 → **Create codespace on main**
2. 2~5분 기다립니다. 터미널에 `준비 끝.` 과 함께 **관리자 비밀번호**가 찍힙니다 (복사해 두세요).
3. 브라우저 탭이 자동으로 열립니다. 안 열리면 아래 **포트** 탭에서 `8080` 줄의 지구본 아이콘을 누릅니다.
4. `admin` / 위 비밀번호로 로그인합니다.

## AI 기능 켜기 (선택)

터미널에서 (키는 platform.claude.com 에서 발급):

```bash
sed -i 's/^FDE_ANTHROPIC_API_KEY=.*/FDE_ANTHROPIC_API_KEY=sk-ant-여기에_키/' .env
docker compose up -d --force-recreate backend
```

## 코드가 바뀌었을 때 (PR 머지 뒤)

```bash
git pull
docker compose up -d --build
```

## 알아 둘 것

- 데이터는 이 Codespace 안의 Docker 볼륨에 남습니다. Codespace 를 **삭제**하면 같이 지워집니다 (중지는 괜찮습니다). 남겨야 할 데이터는 `./scripts/backup.sh` 로 백업하세요.
- 30분 동안 쓰지 않으면 자동으로 중지되고, 다시 열면 `docker compose up -d` 로 띄웁니다.
- 8080 포트는 기본이 **비공개**(내 GitHub 계정만)입니다. 다른 사람에게 보여 주려면 포트 탭에서 공개 범위를 바꾸되, 관리자 비밀번호를 먼저 바꾸세요.
- 개인 계정은 월 60시간(2코어 기준)까지 무료입니다.
