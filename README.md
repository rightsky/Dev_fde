# FDE Data Studio

원천 데이터(파일·스트림)에 DCAT / PROV-O 메타데이터를 입히고, SHACL 로 검증한 뒤 카탈로그에 발행하는 8단계 메타데이터 스튜디오입니다.
목업(v3.0, 단일 HTML)의 화면 구성과 용어를 따르되, 흉내만 내던 부분을 서버에서 실제로 계산하도록 다시 만들었습니다.

- 백엔드: FastAPI · SQLAlchemy · PostgreSQL · rdflib · pySHACL · pandas
- 프런트엔드: React 18 · TypeScript · Vite
- 배포: Docker Compose (PostgreSQL + API + nginx)

## 실행

```bash
cp .env.example .env        # 비밀번호 3개를 바꿉니다
docker compose up -d --build
# http://localhost:8080  →  .env 의 FDE_ADMIN_USERNAME / FDE_ADMIN_PASSWORD 로 로그인
```

Docker 없이 개발용으로 띄우려면:

```bash
# 백엔드 (기본값은 SQLite 파일 ./fde.db)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
FDE_ADMIN_PASSWORD=원하는비밀번호 FDE_SECRET_KEY=$(openssl rand -hex 32) uvicorn app.main:app --reload

# 프런트엔드 (다른 터미널, /api 는 8000 번으로 프록시)
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

테스트:

```bash
cd backend && pytest                                   # SQLite
FDE_DATABASE_URL=postgresql+psycopg://사용자@호스트/DB pytest   # PostgreSQL
cd frontend && npm run build                           # 타입 검사 + 빌드
```

## 8단계가 실제로 하는 일

| STEP | 화면 | 서버가 하는 일 |
|---|---|---|
| 1 | 데이터셋 조합 추출 | 업로드한 엑셀·CSV·JSON·Parquet 을 읽어 표·컬럼 타입·결측·시간 포맷·개인정보 의심 컬럼을 프로파일링하고, 컬럼명과 값 패턴으로 연계키(K1~K9) 후보를 계산합니다. 후보끼리 키 컬럼의 실제 값 일치율을 구해 조합을 추천합니다. 스트림은 스키마와 시간 규격만 등록합니다. |
| 2 | 조합 조정·확정 | 조합 구성원을 정하고 제목·설명을 확정합니다. 프로파일 경고(인코딩·시간 포맷 혼재·결측 표기 혼재·중복 파일)를 보여 줍니다. |
| 3 | DCAT/PROV-O 카탈로그 | 데이터셋별 메타데이터를 저장합니다. 제공기관·미디어타입(스트림은 시간 해상도·event-time 컬럼)은 사람이 승인하기 전까지 정본에 넣지 않습니다. 미리보기는 저장할 때마다 실제 정본 그래프에서 다시 만들고 같은 엔진으로 즉시 검증합니다. |
| 4 | 다중분류체계 배정 | F1~F6 · K · N²SF 축에 코드를 배정합니다. 배정 결과는 `dcat:theme` `dcterms:type` `dcterms:license` 등으로 정본 그래프에 들어갑니다. |
| 5 | 매핑 + LPG·리니지 | JOINED_ON · GROUPED_WITH · DERIVED_FROM 관계를 확정합니다. JOINED_ON 은 두 컬럼의 실제 값으로 일치 건수와 일치율을 계산합니다. 그래프는 저장된 데이터에서 매번 다시 그립니다. |
| 6 | 검증: 게이트 0 + SHACL | 게이트 0(재파싱·prefix·UTF-8·임시 ID 잔존·정체성)과 pySHACL 검증을 실행합니다. 위반마다 원인 단계로 가는 수정 경로가 붙습니다. 발행 모드에서는 민팅 대장에 없는 ID 를 반려합니다. |
| 7 | 직렬화·발행 포맷 변환 | 검증을 통과한 데이터셋을 Turtle · JSON-LD · 자연어 문장 · JSON 스키마로 변환하고, 산출물을 실제 파서로 다시 읽어 정본과 같은지(그래프 동형·체크섬) 확인합니다. 통과한 것만 저장하며 ZIP 으로 내려받거나 카탈로그에 발행합니다. |
| 8 | 가이드라인 준수 진단 | 규칙 파일에 정의한 항목을 정본 그래프 질의·프로파일 통계·담당자 확인으로 판정해 점수와 조치 우선순위를 냅니다. |

상류를 고치면 하류 결과가 자동으로 무효화됩니다. 별도 플래그 없이 "실행 시점 정본 체크섬 ≠ 현재 정본 체크섬"으로 판단하므로, 어느 화면에서 무엇을 고치든 빠지지 않습니다.

## 알아 둘 한계

- **추천은 규칙 기반입니다.** 조합·분류·결합 후보 추천에 LLM 을 쓰지 않습니다. 화면에는 계산 근거를 함께 보여 줍니다.
- **STEP 8 은 가이드라인 80항목 전체가 아닙니다.** 목업에 항목 목록이 없어, 목업에 근거가 드러난 항목과 메타데이터로 자동 판정할 수 있는 33개만 `backend/app/data/guideline_rules.json` 에 구현했습니다. `basis` 가 "제품 규칙"인 항목은 가이드라인 원문과 대조해 확정해야 합니다. 점수는 구현된 항목 기준이며 화면에도 그렇게 표시됩니다.
- **스트림은 메타데이터만 다룹니다.** 브로커에 실제로 접속하지 않습니다.
- **목업의 다음 부분은 만들지 않았습니다:** 검수 큐, AI 어시스턴트, 외부 소스 연계(공공데이터포털·MCP·데이터레이크), PMS, API·MCP 제공 관리, 배치 재검증.
- **DB 스키마 이관 도구가 없습니다.** 기동할 때 없는 테이블만 만듭니다(`create_all`). 운영 전에 Alembic 같은 이관 체계를 붙여야 합니다.
- **Docker 이미지 빌드는 개발 환경에서 검증하지 못했습니다.** compose 파일 문법만 확인했습니다. 백엔드 테스트는 SQLite 와 PostgreSQL 16 에서, 화면은 개발 서버로 업로드부터 발행·진단까지 확인했습니다.

## 확인이 필요한 설계 결정

목업이 정하지 않았거나 화면마다 달랐던 부분을 아래처럼 정했습니다. 바꾸려면 표시한 파일을 고치면 됩니다.

| 결정 | 현재 값 | 위치 |
|---|---|---|
| 스트림의 타입 | 목업대로 `dcat:Dataset` 과 `dcat:DataService` 를 함께 선언 (DCAT 3 의 `servesDataset` 분리 모델 아님) | `services/canonical.py` |
| 분류 축의 RDF 속성 | F1 `dcat:theme` · F2 `dcterms:type` · F3 `fde:granularity` · F4 `dcterms:license`(공공누리)/`dcterms:accessRights` · F5 `fde:aiPurpose` · F6 `fde:governanceMode` · K `fde:joinKey` · N²SF `fde:n2sfGrade` | `services/canonical.py` |
| 관계의 RDF 표현 | JOINED_ON · GROUPED_WITH 는 `dcat:qualifiedRelation` + `dcat:Relationship`, DERIVED_FROM 은 `prov:wasDerivedFrom` | `services/canonical.py` |
| 조합 | `prov:Collection` 노드로 두고 구성원에 `dcterms:isPartOf` | `services/canonical.py` |
| 단일 선택 축 | F4 · F6 · N²SF 는 1개만 (목업은 화면마다 달랐음) | `data/taxonomy.json` |
| F6 코드 | 관리 화면 기준 4종 (기관 내부 관리 · 부처 공유 · 대국민 개방 · 통제) | `data/taxonomy.json` |
| 발행 ID | `DST-000001` · `SVC-000001`, 원천 1건당 1개, 관리자가 명시적으로 발급. 배포본은 `DIST-{번호}-{확장자}` | `services/minting.py` |
| IRI 기준 주소 | `https://catalog.molit.go.kr` (환경변수 `FDE_BASE_IRI`) | `.env` |
| 확정 조건 | 메타데이터 확정은 필수 필드 승인 필요, 분류 확정은 F1·F2 필요, 그 밖의 결측은 검증 Warning | `routers/studio.py` |
| 셰이프 세트 | `rs-3.0`, 공통 + 발행 전용 2개 파일 | `app/shapes/*.ttl` |
| 권한 | 관리자(ID 발급·발행·사용자 관리) · 담당자(작업) · 열람자. 단계별 담당 배정은 없음 | `security.py` |

## 구조

```
backend/app
  main.py            앱 진입점 (기동 시 테이블 생성 + 기준 데이터 적재)
  models.py          데이터 모델
  routers/           core(인증·기관·분류체계·원천) · studio(8단계) · catalog(카탈로그·대시보드)
  services/
    profiling.py     파일 프로파일링, 연계키 후보
    suggest.py       규칙 기반 추천 (조합·분류·결합 후보·초안)
    canonical.py     정본 그래프 빌더 — 미리보기·검증·직렬화·발행이 모두 이 출력을 씀
    validation.py    게이트 0 + SHACL
    serialize.py     4포맷 변환 + 파생 자가검증
    lineage.py       결합 통계, LPG 투영
    diagnosis.py     진단 규칙 엔진
    gates.py         단계 잠금·완료·무효화 판정 (한 곳에서만)
    minting.py       ID·IRI 규칙
  shapes/            SHACL 셰이프 (Turtle)
  data/              분류체계·어휘·진단 규칙 시드 (JSON)
backend/tests        프로파일링 단위 테스트 + 8단계 통합 테스트
frontend/src
  api.ts types.ts ui.tsx styles.css   공용 기반
  studio/            StudioLayout + Step1~8
  pages/             Home · Assets · Catalog · Admin
docs/
  FRONTEND_GUIDE.md  화면 작성 규칙
  api-samples/       실제 API 응답 표본과 경로 목록
  mockup-analysis/   목업 v3.0 분석 명세 (화면별 동작·데이터·목업의 결함 목록)
```

API 문서는 기동 후 `/api/docs` 에서 볼 수 있습니다.

## 환경변수

| 이름 | 기본값 | 설명 |
|---|---|---|
| `FDE_DATABASE_URL` | `sqlite:///./fde.db` | SQLAlchemy 접속 주소 |
| `FDE_STORAGE_DIR` | `./storage` | 업로드 원본 보관 위치 |
| `FDE_SECRET_KEY` | (없음) | 로그인 토큰 서명 키. 비우면 기동할 때마다 새로 만들어 재기동 시 로그인이 풀립니다 |
| `FDE_ADMIN_USERNAME` / `FDE_ADMIN_PASSWORD` | `admin` / (없음) | 최초 기동 때 만드는 관리자. 비밀번호를 비우면 무작위로 만들어 로그에 한 번 출력합니다 |
| `FDE_BASE_IRI` | `https://catalog.molit.go.kr` | 발행 IRI 기준 주소 |
| `FDE_MAX_UPLOAD_MB` | `50` | 파일당 업로드 상한 |
| `FDE_PROFILE_MAX_ROWS` | `50000` | 표 1개당 프로파일 행 상한 |
| `FDE_SEED_DEMO_ORGS` | `true` | 시나리오 기관 5곳을 처음에 넣을지 |
