# STEP 3: DCAT 2.0/3.0 + PROV-O 표준 카탈로그 작성 — 기능 명세

- 분석 대상: `src/markup.html` 475~1018행(STEP 3 블록), 공용 요소인 145~150행(수정 복귀 배너)과 3876~3889행(하단 고정 바)
- 로직 출처: `src/logic.js` (행 번호는 모두 logic.js 기준, 마크업 행은 `M:` 접두)
- 표기 규칙: 큰따옴표·「」 안의 한국어 문구는 목업 원문 그대로이다. `{…}` 는 바인딩 값이다.

---

## 1. 화면 목적

STEP 2에서 확정한 "작업 조합"(`combo` 배열)에 들어 있는 데이터셋을 **한 건씩** 골라 DCAT/PROV-O 카탈로그 메타데이터를 작성하고 확정하는 화면이다. 데이터셋 한 건에 대해 4개 하위 탭(① 클래스 선택 → ② 프러퍼티 폼 → ③ 프로버넌스 → ④ 관계 맵)을 순서대로 완주한 뒤 하단 [다음 (확정)]을 누르면 해당 데이터셋이 "완료" 처리되고 다음 데이터셋의 ①로 넘어간다. 모든 데이터셋이 완료되면 STEP 4로 이동한다.

이 화면이 실제로 하류 단계(STEP 6 검증, STEP 7 직렬화)에 영향을 주는 입력은 **② 탭 최상단 "ARD 필수 필드 승인 입력" 카드 하나뿐**이다. 여기서 `dcterms:publisher`(생산 기관)와 `dcat:mediaType`(IANA)을 입력하고 [승인 (정본 반영)]을 눌러야 값이 정본(canonical)에 반영된다. 나머지 폼 필드, 클래스·프러퍼티·프로버넌스 선택은 화면 표시용 상태일 뿐 정본 트리플에는 들어가지 않는다(6장 참조).

우측에는 접을 수 있는 "미리보기 · 검증 패널"이 고정되어 Turtle 미리보기, SHACL 결과, 프로버넌스 정합 점검을 보여 준다.

진입 조건(`stepGate(3)`, 334행): `combo.length > 0 && comboMeta.done` (STEP 2 조합 확정). 미충족 시 토스트 `🔒 STEP 3 잠김 — STEP 2 조합 확정을 먼저 완료하세요` (11행, 3초).

---

## 2. 화면 구성

전체 레이아웃(M:477): 좌측 본문(flex:1) + 우측 패널(320px, 확장 시 480px). 최대 폭 1240px.

### 2.0 공통 상단 (모든 하위 탭 공통)

| # | 요소 | 원문 라벨 / 내용 | 바인딩 |
|---|---|---|---|
| 0-1 | 화면 제목 | `STEP 3: DCAT 2.0/3.0 + PROV-O 표준 카탈로그 작성` | 고정 |
| 0-2 | 인계 카드 헤더(클릭 시 접기/펼치기) | `STEP 2 조합 인계 — 작업 대상 {comboCount}건` + 파란 배지 `작성 중: {ds3CurName}` + 회색 `완료 {ds3DoneCount}건` + 우측 `{ds3FoldIcon}` (`목록 접기 ▲` / `목록 펼치기 ▼`) | `ds3FoldToggle` |
| 0-3 | 데이터셋 선택 목록(세로 칩) | 행마다 번호 원 `{d.num}`, 이름 `{d.name}`, 상태 배지 `{d.st}` = `완료 ✓ (보는 중)` / `완료 ✓` / `작성 중` / `대기` | `ds3Chips[].go` |
| 0-4 | 안내문 1 | `현재 작성 대상: {ds3Cur} — ①~④ 완료 후 [다음 (확정)]을 누르면 다음 데이터셋으로 이어집니다 · 데이터셋별 확정마다 prov:Activity 기록` | |
| 0-5 | 안내문 2 | `이 대상에 선택된 클래스: {ds3ClsSummary} — ① 탭의 선택이 현재 작성 대상에 귀속되며, 다음 데이터셋으로 확정 이동 시 선택이 초기화됩니다` | |
| 0-6 | 인계 메타 배너(`cmDone`일 때만) | `✓ STEP 2 확정 메타데이터 인계 — dcterms:title 「{cmTitle}」 · dcterms:description 「{cmDesc}」 — ② 프러퍼티 폼 초안과 프로세스 이름에 반영됨` | |
| 0-7 | 하위 탭 바 | `① 클래스 선택` · `② 프러퍼티 폼` · `③ 프로버넌스` · `④ 관계 맵` | `t1`~`t4` |

칩 색상 규칙(1976~1983행): 완료+현재=녹색(#2aa876), 현재=파랑(#1E5EFF), 완료=연녹색 테두리, 그 외=흰색.

### 2.1 탭 ① 클래스 선택 (`tab3 === 1`)

위에서 아래 순서.

1. **조회 줄**
   - 입력창 placeholder `클래스 조회… (예: prov:Entity, dcat:CatalogRecord)` (핸들러 없음)
   - 고정 배지 `★ AI 추천: dcat:Dataset — 정형 Parquet 배치 소스에 적합 (신뢰도 95%)`
2. **주 클래스 카드 그리드(3열, 5장)**
   - 고정 카드: `dcat:Dataset` + 태그 `★ 추천`, 설명 `데이터셋 정본 기술. 정형·반정형·비정형 공통 기본 클래스`, 고정 배지 `✓ 선택됨` (해제 불가)
   - 토글 카드 4장(`mainClsCards`, 4.2절): 버튼 `선택` ↔ `✓ 선택됨`
3. **선택된 추가 클래스 바**(`clsSelOn`일 때만)
   - `선택된 추가 클래스 {clsSelCount}` (예: `2건`) + 칩 `{클래스명}` + `✕`(제거)
   - 안내 `② 프러퍼티 폼의 클래스 칩과 Turtle 미리보기에 함께 반영됩니다 · 확정 시 prov:Activity 기록`
4. **추가 클래스 조회 카드**
   - 헤더 `추가 클래스 조회 · DCAT · PROV-O · 보조 어휘 42종 · 데이터 유형별 필터`
   - 필터 버튼 5개: `전체` `정형` `반정형` `비정형` `실시간 스트림`
   - 행(`clsRows`): `{이름}` `{유형 배지}` `— {설명}` `{적합 배지}` + 버튼 `선택` / `✓ 선택됨`
     - 적합 배지: `★ 추천` / `적합` / `비추천 (선 전처리 필요)`
     - 근거 줄(미선택이고 근거가 있을 때): `근거: {evidence}`
     - 경고 패널(스트림 유형 행을 누른 직후): `⚠ 비추천 — 현재 조합(정형 Parquet 배치)과 유형 불일치: {warnMsg}` / `선택 사유(필수):` + 셀렉트(3개 옵션, 4.6절) + 버튼 `사유와 함께 선택` · `취소`
     - 완료 패널(방금 선택한 행): `✓ 선택 반영됨 — {이름} 그룹이 ② 프러퍼티 폼과 Turtle 미리보기에 추가되었습니다.` / `연쇄 추천 (이 클래스를 선택했으므로 필요해진 항목): {chain}` / 버튼 `연쇄 항목 모두 추가` · `② 프러퍼티 폼에서 편집 →` · `닫기`
   - 푸터 링크 `전체 42종 보기 →` (핸들러 없음)

### 2.2 탭 ② 프러퍼티 폼 (`tab3 === 2`)

1. **ARD 필수 필드 승인 입력 카드**(파란 2px 테두리)
   - 제목 `ARD 필수 필드 승인 입력 — {ardDsName}` + 우측 배지 `readiness: {ardLevel}` (`ai-ready` 녹색 / `draft` 주황 / `—`)
   - 설명 `sLLM 제안·수기 입력 모두 승인 체크 전까지 미입력으로 간주됩니다 — 승인 값만 정본(canonical)에 반영되고 STEP 6 검증·STEP 7 산출물·Turtle 미리보기에 동일하게 나타납니다. 승인 시 기존 검증 결과는 자동 무효화됩니다.`
   - 필드 A: 라벨 `dcterms:publisher — 생산 기관 (Agent IRI로 직렬화)`, 텍스트 입력(placeholder `예: 국토교통부(데모)`), 그 아래 작은 글씨로 기관 IRI `{ardOrgId}` (없으면 `(publisher 입력 시 기관 IRI 자동 구성)`)
   - 필드 B-파일형(`ardIsFile`): 라벨 `dcat:mediaType — IANA 목록 (Distribution 노드에 IRI로 직렬화 · 자유 입력 금지)`, 셀렉트(4.4절)
   - 필드 B-스트림형(`ardIsStream`): 라벨 `스트림 상당 필수 — temporalResolution · event-time (탭 메뉴 양식 값)`, 점선 박스 `dcat:DataService — mediaType 대신 스트림 속성으로 직렬화` (입력 불가)
   - 버튼 `승인 (정본 반영)` ↔ `✓ 승인됨 — 정본 반영`
2. **클래스 칩 바**(보라색)
   - 배지 `클래스` + 칩 `dcat:Dataset ✓`(활성) · `dcat:Distribution` · `dcat:DataService` · `dcat:DatasetSeries` · `dcat:Catalog`(모두 핸들러 없음) + ①에서 고른 추가 클래스 칩 `{이름} ✓ 추가`
   - 설명 `아래 프러퍼티는 선택 클래스 dcat:Dataset의 도메인에 종속됩니다. 클래스 칩을 누르면 해당 클래스의 폼으로 전환. 배포 단위 속성은 dcat:distribution으로 연결된 하위 클래스에 귀속.`
3. **필수 항목 카드** (우측 `domain: dcat:Dataset`)
   - `dcterms:title` [Dataset] : 입력(값 `{ds3Title}`)
   - `dcterms:identifier` [Dataset] : 읽기 전용 입력(값 `{ds3Id}`) + 체크박스 `확인`(기본 체크)
   - 하위 블록 `↳ dcat:Distribution — dcat:Dataset이 dcat:distribution 프러퍼티로 참조하는 하위 클래스 ({ds3DistId})`
     - `dcat:mediaType` [Distribution] : 읽기 전용 입력(값 `{ds3Media}`) + 체크박스 `확인`(기본 해제)
     - `dcat:accessURL` [Distribution] : 입력(값 `{ds3Url}`)
   - 두 번째 배포본 블록(`dist2On`일 때): `↳ dcat:Distribution — 두 번째 배포본 (DIST-000123-csv)` + 링크 `제거`
     - `dcat:mediaType` 입력(값 `text/csv`), `dcat:accessURL` 입력(placeholder `접근 URL 입력…`)
     - `Turtle 반영: dcat:distribution <DIST-000123-pq>, <DIST-000123-csv> ;`
   - 버튼 `+ 배포본 추가 (dcat:distribution)`
4. **시간 규격 카드**(`ds3IsStream`일 때만. 제목 `시간 규격` + 배지 `실시간 스트림`, 우측 `domain: dcat:DataService`)
   - 4.3절 표의 5개 행
   - 주석 `ⓘ 이 선언은 F3 시간 해상도 축(STEP 4)과 StreamServiceShape(STEP 7)의 검증 기준이 됩니다 · 적용 정렬 규칙: PLN-ALN-002 v2.1 → 스트림 관리에서 보기`(링크 `goStream`)
   - 스트림이 아니면 대신 점선 박스: `시간 규격 카드(dcat:DataService)는 실시간 스트림 데이터셋에만 표시됩니다 — 현재 작성 대상({ds3CurName})은 해당 없음`
5. **권장 항목 카드** (`domain: dcat:Dataset`)
   - `dcat:inSeries` [3.0][Dataset] : 입력(값 `SER-0004 교통소통 시리즈`) + `→ range: DatasetSeries`
   - `dcat:version` [3.0][Dataset] : 입력(값 `2.4.1`)
   - 주석 `ⓘ 표기 병존: dcat:version(3.0) 우선 + owl:versionInfo(가이드라인 표기) 병기`
6. **선택 항목 카드** (`domain: dcat:Dataset`)
   - `dcterms:accrualPeriodicity` [Dataset] : 입력(값 `5분`, 붉은 배경) + `비표준 표기`
   - 추가 프러퍼티 행(`propSelChips`): `{이름}` + 배지 `신규 추가` + 입력(placeholder `값 입력…`) + 링크 `제거`
7. **추가 프러퍼티 조회 카드**
   - 헤더 `추가 프러퍼티 조회 · 데이터 유형별 필터` + 필터 5개(①과 동일 라벨)
   - 행 구조는 ①의 조회 행과 같다. 버튼 `폼에 추가` ↔ `✓ 추가됨`. 경고 패널 버튼은 `사유와 함께 추가` · `취소`
   - 완료 패널: `✓ 폼에 추가됨 — 위 「선택 항목」 카드에 {이름} 입력 행이 생성되었습니다 (값 입력 후 Turtle 반영 · 확정 시 prov:Activity 기록).` + `닫기`

### 2.3 탭 ③ 프로버넌스 (`tab3 === 3`)

1. **안내 배너**(파란 배경)
   - `이력의 대부분은 실행 시점에 자동 기록됩니다. 이 화면은 자동 기록분을 확인하고, 공백(외부 유입분 · 소급분)을 연결·보완하는 콘솔입니다 — 확인·연결 행위 자체도 prov:Activity로 기록됩니다.`
   - 좌: `작업자가 할 일 (3가지)` / `① 타임라인의 자동 기록분 확인 — 파라미터·Agent가 맞는지` / `② ★ AI 추천의 공백 후보 연결 — 단계 귀속 배지대로 클릭` / `③ 책임자 Agent·재현 파라미터 누락 보완 — 조회 후 연결`
   - 우: `프로버넌스가 하는 일 (3가지)` / `① 재현 — 동일 입력+파라미터=동일 산출의 근거 보존` / `② 책임 — 누가(Agent) 어떤 활동(Activity)으로 만들었나 귀속` / `③ 리니지 — 원천→정제→파생→학습셋 계보 연결 (단절 방지)`
2. **생애주기 7단계 Activity 타임라인 카드**
   - 7개 노드(클릭 가능): `계획` `수집` `처리·가공` `저장·등록` `공개·제공` `활용` `폐기·보존`. 각 노드 아래 보조 문구(`ACT 기록됨 · 자동+수기` / `ACT 기록됨 · 자동` / `대기`)
   - 상세 박스: `{lcTitle} 상세` + 배지 `{lcBadge}` / 6개 필드 `prov:Activity` · `담당 Agent` · `기간` · `입력 (prov:used)` · `산출 (prov:generated)` · `기록 속성` / 설명문 `{lcNote}`
3. **Agent 카드 3장**(`lcAgents`): `{역할 라벨}` / `{이름}` / `{prov 유형}`
4. **파라미터 카드**: 제목 `{lcParamTitle} — {lcTitle} 기준` + 배지 `판정 기준: 재현에 필요하면 PROV, 소비에 필요하면 마트` + 파라미터 박스 3개(`{label}` / `{value}`)
5. **프로버넌스 연결 카드**
   - 제목 `프로버넌스 연결 — 기존 Activity · Agent 조회 후 연결 (신규 작성 아님 · 공백 보완용)`
   - 안내 박스: `작업 범위 안내 — 7단계마다 입력하는 것이 아닙니다.` / `① 위 타임라인의 자동 기록분은 손댈 필요 없음 (대부분) · ② 아래 ★ AI 추천은 시스템이 감지한 공백만 골라 제시하며, 각 항목이 귀속될 단계가 배지로 표시됨 — 추가하면 해당 단계에 자동 귀속 · ③ 추가 프로버넌스 조회는 단계가 아니라 관계 어휘(wasQuotedFrom 등)를 기록에 더하는 예외 보완 도구`
   - 입력창 placeholder `Activity · Agent · Entity 조회… (예: ACT-K-, 정제, 담당자명)` + 버튼 `조회` (둘 다 핸들러 없음)
   - 소제목 `★ AI 추천 — 이 데이터셋의 리니지 공백을 메울 후보`
   - 추천 행(`provRecRows` 3건): 배지 `{stage}` + `{id}` + `{name}` + (있으면) `추천 사유: {why}` + 버튼 `+ 추가` ↔ `✓ 연결됨`
   - 연결 직후 패널: `✓ 연결됨 — {effect} · 확정 시 prov:Activity로 기록되며 위 생애주기 타임라인과 관계 맵에 반영됩니다.`
6. **추가 프로버넌스 조회 카드**
   - 헤더 `추가 프로버넌스 조회 · PROV-O 관계·Agent · 데이터 유형별 필터` + 필터 5개
   - 행 구조 동일. 버튼 `기록에 추가` ↔ `✓ 추가됨`. 경고 패널 버튼 `사유와 함께 추가` · `취소`
   - 완료 패널: `✓ 기록에 추가됨 — {이름} 관계가 프로버넌스 기록 목록에 반영되었습니다 (Agent·대상 연결 후 확정 시 prov:Activity 기록).` + `닫기`

### 2.4 탭 ④ 관계 맵 (`tab3 === 4`)

1. **관계 맵 카드** 제목 `클래스 · 프러퍼티 · 프로버넌스 관계 맵`, 범례 `클래스 (DCAT)`(보라) · `프로버넌스 (PROV-O)`(주황) · `프러퍼티(엣지)`(파랑)
   - 고정 SVG(860×380). 노드와 엣지는 4.9절 표 참조. 하단 캡션 `클래스(보라)는 프러퍼티(파랑 엣지)로 서로 연결되고, 프로버넌스(주황)는 prov: 엣지로 데이터셋의 생성 이력·책임 주체를 연결합니다`
2. **이번 세션 선택 반영 카드**(파란 2px 테두리)
   - 제목 `이번 세션 선택 반영 — ①~③ 탭에서 선택·추가한 항목이 관계로 표시됩니다` + 배지 `확정 시 prov:Activity 기록`
   - 선택이 하나라도 있으면(`selMapOn`) 3열 구성
     - `① 추가 클래스 {N}건` : 칩 목록, 비었으면 `① 클래스 탭에서 선택 없음`
     - 화살표 `→` + `타이핑·참조`
     - `중심 리소스 + ② 추가 프러퍼티 {N}건` : 고정 박스 `dcat:Dataset` / `DST-000123 교통링크 5분 소통정보`, 칩 `─ {프러퍼티} →`, 비었으면 `② 프러퍼티 탭에서 추가 없음`
     - 화살표 `→` + `이력·책임`
     - `③ 추가 프로버넌스 {N}건` : 칩 목록, 비었으면 `③ 프로버넌스 탭에서 연결 없음`
     - 푸터 `병기형(prov:Entity·qb:DataSet)은 중심 리소스 타입에 병기되고, 나머지 클래스는 대응 리소스(배포본·문서·스키마 등)에 타이핑됩니다 — 좌측 Turtle 미리보기와 동일 기준`
   - 전부 비었으면(`selMapAllEmpty`): `아직 선택된 항목이 없습니다 — ① 클래스 · ② 프러퍼티 · ③ 프로버넌스 탭에서 조회 후 선택하면 이곳에 관계로 표시됩니다`

### 2.5 우측 "미리보기 · 검증 패널" (4개 탭 공통)

- 숨김 상태: 세로 버튼 `◀ 미리보기 · 검증 패널` (title `미리보기 패널 펼치기`)
- 헤더 `미리보기 · 검증 패널` + 버튼 `{rpWideIcon}`(`⇤` 기본 / `⇥` 확장 상태, title `영역 확장/축소`) + 버튼 `▶`(title `패널 감추기`)
- 섹션 1 `Turtle 실시간 미리보기` (헤더 클릭으로 접기, 아이콘 `접기 ▲`/`펼치기 ▼`). 템플릿은 4.10절
- 섹션 2 `SHACL 검증 결과` : 고정 2줄
  - `✕ dcat:mediaType 확인 미완료 · 폼 필드로 이동`
  - `△ accrualPeriodicity 비표준 표기 · 폼 필드로 이동`
- 해결방안 패널(`fixGuideOn`일 때만): 제목 `해결방안 — DST-000712 수기 입력` + `닫기 ✕`
  - `원인: HWP 혼재 문서 묶음 — 파일 메타 자동 판독 불가로 프로파일러가 추출 실패 (STEP 7 ① 자동추출에서 이동됨)`
  - `1. dcterms:title · description 수기 입력 — 문서 표지 기준으로 작성`
  - `2. dcat:mediaType을 application/x-hwp로 지정 (PDF 분리 시 배포본 2건 등록)`
  - `3. dcterms:format · byteSize는 파일 시스템 값으로 입력 (312건 · 1.8 GB)`
  - `4. 장기적으로 PDF/A 일괄 변환 후 재프로파일 권장 — sLLM 주제 제안 활성화 가능`
  - `5. 입력 완료 후 STEP 6 재검증 실행 → (수기 입력도 prov:Activity로 기록)` (링크 `goStep6`)
- 섹션 3 `프로버넌스 정합 점검 — 포함 데이터셋 {comboCount}건`
  - 체인 문자열 `{provChain}` (조합 이름을 ` → ` 로 연결, 비면 `(조합 비어 있음)`)
  - `최신성` : `업로드 {comboCount}건 (2026-08-21 판독)` / `2026-08-21 ✓`
  - `생산 조직` : `{orgOkCount}건` / `국토교통부 계열 ✓`, 경고 행 `✕ {이름}` / `{기관} (타 부처) — 협약 확인 필요`, 경고가 없으면 `타 부처 데이터 없음 — 협약 확인 대상 0건`
  - `데이터 유형 구성` : 100% 파란 막대 + `정형 (엑셀) 100% ({comboCount}건)`

### 2.6 공용 요소

- 수정 복귀 배너(M:145~150, `fixBack`이 있을 때 본문 최상단): `⚠ STEP 6 위반 수정 중 — {fixBackShape} · 보강 후 검증으로 복귀하세요 (수정 시 검증 결과 자동 무효화)` + 버튼 `검증으로 복귀 ↩`
- 하단 고정 바(M:3876~3889): `이전` / `데모 데이터 지우기` / `↺ 데모 데이터 복구` / `⤓ 파일로 저장` / `⤒ 파일 불러오기` / `임시저장`(↔ `✓ 임시저장`) / `다음 (확정)`
- 토스트(화면 하단 중앙): `{toastText}` 또는 기본 문구 `✓ prov:Activity {toastId} 기록됨` (1708행)
- 단계 인계 알림 팝업(우하단, 5초): `🔔 다음 단계 담당자 알림 발송` / `STEP 3 확정 완료 → STEP 4 작업 요청` / `수신: 메타데이터 표준화팀 (정 홍길동 · 부 이순신) · 참조: 관리자 변학도` / 배지 `✓ 시스템 알림` `✓ 기관 메일` `업무포털 쪽지 (설정 꺼짐)`

---

## 3. 사용자 동작 → 결과

### 3.0 공통 메커니즘

| 메커니즘 | 규칙 | 근거 행 |
|---|---|---|
| `go(patch)` | 상태 병합. `patch.tab3`·`step`·`plane` 이 있으면 `savedHere=false`. 400ms 디바운스로 `localStorage['fde-studio-draft']` 저장 | 4~28 |
| 기본 토스트 `showToast()` | `toastId = 'ACT-K-' + (400~498 난수, 4자리)`. 2.2초 표시. 문구 `✓ prov:Activity ACT-K-04xx 기록됨`. **`actLog`에는 기록하지 않는다** | 46~51, 1708 |
| 활동 로그 `logAct(who, txt)` | `actLog`에 `{t:'HH:MM', who, txt, actId}` 추가, 최근 10건만 유지. `actId = 'ACT-K-' + (actSeq+1)` (시작값 0421) | 53~61 |
| 하류 무효화 `invalidateDownstream('catalog', msg)` | `v7State === 'done'` 일 때만 `{v6Stale:true, convertState:null, svResults:null, v8State:null}` 적용 + 토스트 `msg`(3초) + `logAct('시스템', msg)`. 검증 전이면 아무 일도 하지 않는다 | 344~356 |

### 3.1 상단 인계 카드

| 동작 | 결과 |
|---|---|
| 헤더 클릭 | `ds3Fold` 토글(1975행). 목록·안내문·인계 배너가 함께 접힌다 |
| 데이터셋 칩 클릭 | `go({ds3: i})` (1978행). 작성 대상만 바뀐다. **`tab3`와 클래스·프러퍼티·프로버넌스 선택(`mainSel`/`clsSel`/`propSel`/`provSel`)은 초기화되지 않는다.** 완료된 데이터셋도 다시 열 수 있으며 완료 표시는 유지된다 |
| 하위 탭 클릭 | `go({tab3: n})` (2034, 2038행). 탭 이동에는 잠금 조건이 없다 |

파생 값(1940~1984행)

- `ds3Cur` = `{이름} ({ids[이름] 또는 '신규 ID 발급'})`. 조합이 비면 `(없음 — STEP 2에서 조합을 확정하세요)`
- `ds3CurName` = 이름 또는 `(없음)`
- `ds3ClsSummary` = `dcat:Dataset` + (추가 선택이 있으면 ` + ` + `mainSel`과 `clsSel`의 키를 ` · ` 로 연결, 없으면 ` (기본)`)
- `ds3DoneCount` = `ds3Done` 값 중 truthy 개수

### 3.2 탭 ① 클래스 선택

| 컨트롤 | 상태 변화 | 토스트·로그 | 비고 |
|---|---|---|---|
| 주 클래스 카드 `선택`/`✓ 선택됨` | `mainSel[name]` 추가/삭제 토글(2022~2029행) | 추가할 때만 기본 토스트 | `ds3ClsSummary`와 카드 테두리에만 반영. Turtle 미리보기·② 칩·④ 맵에는 반영되지 않음 |
| 필터 버튼 | `go({cls: 라벨})` (1747행) | 없음 | 표시 조건: `라벨==='전체' \|\| 항목유형===라벨 \|\| 항목유형==='공통'` (1750행). 공통 항목은 항상 보인다 |
| 조회 행 `선택` (비스트림 유형) | `clsSel[name]=true`, `clsWarn=null`, `clsDone=name` (1815~1818행) | 기본 토스트 | 완료 패널이 그 행에 열림 |
| 조회 행 `선택` (유형이 `실시간 스트림`) | `clsWarn=name` 만 설정(1837행) | 없음 | 경고 패널이 열림. 현재 데이터셋이 실제 스트림인지와 무관하게 유형 라벨만으로 판정 |
| 경고 패널 `사유와 함께 선택` | 위 `doPick`과 동일 | 기본 토스트 | 셀렉트에서 고른 사유는 **저장되지 않는다** |
| 경고 패널 `취소` | `clsWarn=null` | 없음 | |
| 조회 행 `✓ 선택됨` 재클릭 | `clsSel`에서 삭제(1836행) | 없음 | |
| 완료 패널 `연쇄 항목 모두 추가` | `clsDone=null` (1826행) | 기본 토스트 | **실제로는 아무 항목도 추가하지 않는다** |
| 완료 패널 `② 프러퍼티 폼에서 편집 →` | `go({tab3:2, clsDone:null})` | 없음 | |
| 완료 패널 `닫기` | `clsDone=null` | 없음 | |
| 선택 칩 `✕` | `clsSel`에서 삭제, `clsDone=null` (1936행) | 없음 | |
| 조회 입력창, `전체 42종 보기 →` | 없음 | 없음 | 미구현 |

선택 결과의 파급: `clsSelChips`가 ①의 선택 바, ②의 클래스 칩 바, ④의 "① 추가 클래스" 열에 나타나고, 우측 Turtle 미리보기에 클래스별 고정 스텁(4.8절)이 삽입된다.

### 3.3 탭 ② 프러퍼티 폼

#### 3.3.1 ARD 필수 필드 승인 입력 (2860~2903행) — 이 화면의 핵심 규칙

현재 데이터셋 이름 `nm3 = combo[ds3].n`. 기준값 `base3 = META_TABLE[nm3] || item.meta || {}`. 덮어쓰기 `ov3 = metaOver[nm3] || {}`.

표시값(`cur3`, 2867행): `org`·`orgId`·`mediaTypeIana` 각각 `ov3`에 정의돼 있으면 그 값, 아니면 `base3` 값, 둘 다 없으면 빈 문자열. `approved = !!ov3.approved`.

| 컨트롤 | 상태 변화 | 토스트·로그 |
|---|---|---|
| publisher 입력 변경 | `metaOver[nm3] = {…cur3, …기존, org: 입력값, orgId: 'https://catalog.molit.go.kr/id/org/ORG-' + hash6(입력값), approved: false}` 후 즉시 localStorage 저장(2868, 2875행) | 없음 |
| mediaType 셀렉트 변경 | `metaOver[nm3].mediaTypeIana = 선택값`, `approved: false` (2879행) | 없음 |
| `승인 (정본 반영)` 클릭, `cur3.org` 가 빈 값 | 변화 없음 | 토스트 `✕ publisher(생산 기관)를 먼저 입력하세요 — 승인 없는 정본 반영 금지` (2.6초) |
| `승인 (정본 반영)` 클릭, 정상 | `metaOver[nm3].approved = true` (2883행) | ① `logAct('홍길동 (나)', 'STEP 3 승인 입력 — ' + nm3 + ' publisher·mediaType 확정 (정본 갱신)')` ② `invalidateDownstream('catalog', '카탈로그 승인 입력 — STEP 6 검증 결과 무효화 (재검증 필요 · STEP 7~8 재잠금)')` |

정본 반영 규칙(`getMeta2`, 143~147행)

```js
const base = item.meta || META_TABLE[item.n] || {};
const ov   = metaOver[item.n] || {};
return { ...base, ...(ov.approved ? ov : {}) };   // 승인 전 덮어쓰기는 무시
```

- 승인된 덮어쓰기만 `base` 위에 병합된다. 입력을 고치면 `approved=false`가 되어 **정본은 즉시 기준값(META_TABLE)으로 되돌아간다.**
- 승인 조건은 publisher 존재뿐이다. mediaType이 비어 있어도 승인된다. 이 경우 파일형 데이터셋은 `distribution=null` 이 되어 readiness가 `draft`로 남고 STEP 6에서 `MediaTypePlacementShape — Distribution 결측`으로 실패한다(317행).
- 승인 상태에서 버튼을 다시 눌러도 핸들러는 그대로 실행된다(로그와 무효화가 한 번 더 발생).
- readiness 배지(`ardLevel`)는 `buildCanonical(item).readiness.level` 을 그대로 표시한다(2891행). 필수 키는 파일형 `['title','publisher','distribution']`, 스트림형 `['title','publisher']` (177행). 누락이 0이면 `ai-ready`, 아니면 `draft`.
- 스트림 여부(`ardIsStream`)는 `base3.kind === 'stream'` 로 판정한다(2872행).

하류 무효화 결과: STEP 6 검증이 이미 `done`이었다면 `v6Stale=true`가 되어 `stepGate(6).done=false`, `stepGate(7).canEnter=false`(사유 `재검증 필요 — 정본이 변경되었습니다. STEP 6 검증을 다시 실행하세요`, 338행), 변환 결과(`convertState`, `svResults`)와 STEP 8 결과(`v8State`)가 지워진다. 검증을 아직 돌리지 않았다면 토스트도 시스템 로그도 없다.

STEP 6에서 되돌아온 경우(`goFix`, 2799~2806행): `FIX_ROUTE`의 route가 `publisher`면 publisher 입력이, `mediaType` 또는 `stream3`이면 mediaType 셀렉트가 주황 배경으로 2.4초간 강조된다(2893~2894행). 이때 `ds3`가 해당 데이터셋 인덱스로, `tab3`가 2로 설정되고 상단에 수정 복귀 배너가 뜬다.

#### 3.3.2 나머지 폼

| 컨트롤 | 동작 |
|---|---|
| `dcterms:title` 입력 | 값은 데이터셋 이름. `onChange` 없음(저장되지 않음) |
| `dcterms:identifier` | 읽기 전용. `ids[이름]` 또는 `DST-신규 (확정 시 발급)` |
| `확인` 체크박스 2개 | 비제어. 상태 없음 |
| Distribution `dcat:mediaType` | 읽기 전용. **업로드 파일 확장자**로 계산(1956행): xlsx/xls → `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, csv → `text/csv`, 그 외 → `application/vnd.apache.parquet`. ARD 카드의 셀렉트 값과 무관 |
| Distribution `dcat:accessURL` | `'https://lake.molit.go.kr/' + slug` (slug = 이름에서 영숫자 외 문자를 `_`로 치환, 양끝 `_` 제거, 소문자, 비면 `dataset`). 저장되지 않음 |
| `+ 배포본 추가 (dcat:distribution)` / `제거` | `go({dist2: !dist2})` (653행). 두 번째 배포본 블록 표시 토글. 블록 내용은 고정값 |
| 시간 규격 카드 입력 5개 | 전부 비제어·고정값. 표시 조건은 이름 정규식 `/telemetry\|kafka\|스트림\|실시간/i` (1947행) |
| `스트림 관리에서 보기` | `go({plane:'assets', fabTab:3})` (1256행) |
| 권장·선택 항목 입력 | 비제어·고정값 |
| 프러퍼티 필터 버튼 | `go({prop: 라벨})` |
| 조회 행 `폼에 추가` | `propSel[name]=true`, `propWarn=null`, `propDone=name` + 기본 토스트(1861~1864행). 스트림 유형 행은 먼저 `propWarn=name` |
| 조회 행 `✓ 추가됨` 재클릭, 선택 항목 행 `제거` | `propSel`에서 삭제, `propDone=null` |
| 완료 패널 `닫기` | `propDone=null` |

`propSel` 결과: "선택 항목" 카드에 입력 행이 추가되고 ④의 "② 추가 프러퍼티" 열에 칩이 생긴다. 입력한 값은 어디에도 저장되지 않는다.

### 3.4 탭 ③ 프로버넌스

| 컨트롤 | 동작 |
|---|---|
| 타임라인 노드 클릭 | `go({lc: i})` (414행). 기본 선택은 인덱스 2(처리·가공). 상세 박스·Agent 카드 3장·파라미터 카드가 해당 단계의 고정 데이터로 바뀐다 |
| `조회` 버튼, 조회 입력창 | 미구현 |
| AI 추천 행 `+ 추가` | `provRec[id]=true`, `provRecDone=id` + 기본 토스트(1908행). 연결 패널 표시 |
| AI 추천 행 `✓ 연결됨` 재클릭 | `provRec`에서 삭제, `provRecDone=null` (1907행) |
| 프로버넌스 필터 버튼 | `go({prov: 라벨})` |
| 조회 행 `기록에 추가` | `provSel[name]=true`, `provWarn=null`, `provDone=name` + 기본 토스트. 스트림 유형 행은 먼저 `provWarn=name` |
| 재클릭 / 완료 패널 `닫기` | `provSel`에서 삭제 / `provDone=null` |

`provRec`은 버튼 표시 외에 어디에도 쓰이지 않는다(타임라인·관계 맵 미반영). `provSel`은 ④의 "③ 추가 프로버넌스" 열에만 나타난다.

### 3.5 탭 ④ 관계 맵

조작 가능한 컨트롤이 없다. 표시 전용. 카운트는 `Object.keys(clsSel|propSel|provSel).length + '건'` (1929~1933행).

### 3.6 우측 패널

| 컨트롤 | 동작 |
|---|---|
| `▶` / `◀ 미리보기 · 검증 패널` | `rpHide` true/false (2556~2557행) |
| `⇤`/`⇥` | `rpW` 토글, 폭 320px ↔ 480px (2558~2560행) |
| 섹션 헤더 3개 | `rp1`/`rp2`/`rp3` 토글. 기본은 펼침(`!== false`) (2561~2567행) |
| 해결방안 `닫기 ✕` | `go({fixGuide:false})` |
| `STEP 6 재검증 실행 →` | `go({plane:'studio', step:6})` |
| `폼 필드로 이동` 링크 2개 | 미구현(`href="#"`) |

해결방안 패널은 다른 화면의 `goStep3Map`(2553행) 또는 `goStep3Task`(3075행)가 `{step:3, tab3:4, fixGuide:true}` 로 진입시킬 때만 열린다.

### 3.7 하단 바: `이전` / `다음 (확정)`

`이전`(2957~2964행): 먼저 `persistDraft()`. `tab3 > 1` 이면 `tab3 - 1`, `tab3 === 1` 이면 STEP 2로 이동.

`다음 (확정)`(2965~2994행)

1. `autoSave()` : `saveTime = HH:MM` 기록 후 localStorage 저장.
2. `tab3 < 4` : `tab3 + 1` 로 이동 + 기본 토스트. 끝.
3. `tab3 === 4` 이고 현재가 마지막 데이터셋이 아님(`ds3 < combo.length - 1`): `ds3Done[ds3]=true`, `ds3 += 1`, `tab3=1`, `mainSel=clsSel=propSel=provSel=clsDone=propDone=provDone=null` + 기본 토스트. 끝.
4. `tab3 === 4` 이고 마지막 데이터셋: `done = {...ds3Done, [ds3]: true}`. 미완료 인덱스(`combo.findIndex((_, i) => !done[i])`)가 있으면 그 데이터셋으로 이동(`tab3=1`, 선택 초기화) + 기본 토스트. 끝.
5. 모두 완료: `ds3Done=done` 저장 → 기본 토스트 → `go({step:4, notify:{from:'STEP 3', to:'STEP 4', owner:'메타데이터 표준화팀'}})`. 알림 팝업은 5초 후 닫힌다.

확정 시 유의 사항

- **필수 입력 검사가 없다.** publisher 미승인, mediaType 미선택 상태로도 데이터셋을 확정할 수 있다. 결측은 STEP 6에서야 걸린다.
- 확정 시 `actLog` 기록이 없다. 화면 문구는 "데이터셋별 확정마다 prov:Activity 기록"이지만 실제로는 난수 ID 토스트만 뜬다.
- 초기화 대상에 `provRec`, `dist2`, `clsWarn`/`propWarn`/`provWarn`, 필터(`cls`/`prop`/`prov`), `lc` 는 빠져 있어 다음 데이터셋에 그대로 남는다.
- 클래스·프러퍼티·프로버넌스 선택은 데이터셋별로 보관되지 않고 확정 순간 사라진다.

단계 완료 판정(`stepGate(3).done`, 334행): `combo.length > 0 && Object.keys(ds3Done).length >= combo.length`.

`ds3Done`·`ds3` 초기화 지점: STEP 1/2에서 조합을 새로 구성하는 핸들러(`pickComboUp` 2258행, `pickManual` 2275행, `loadComboRec1/2` 2280·2285행, `pickComboA/B` 2290·2295행)가 `ds3:0, ds3Done:null` 로 되돌린다. 조합 항목 개별 추가(`addCombo`, 37행)·삭제(649행)는 `ds3Done`을 건드리지 않는다.

### 3.8 하류 단계와의 연결 요약

| STEP 3 입력 | 하류 사용처 |
|---|---|
| `metaOver[name]` (승인분) | `buildCanonical` → STEP 6 `validateDs`(309~322행), STEP 7 4포맷 산출(`mkContentFor`, 280~288행), STEP 3 Turtle 미리보기 |
| `ds3Done[index]` | 좌측 단계 표시(✓), HOME 대시보드 작업 배지(`카탈로그 작성 중` → `카탈로그 확정 · 분류 검수 중`, 556~562행), 브리핑의 다음 권장 행동(598행) |
| `ds3` | STEP 7 직렬화 대상 선택과 동기화(2736행), STEP 6 [수정하러 이동] 복귀 대상(2804행) |
| `mainSel`/`clsSel`/`propSel`/`provSel`/`provRec`/`dist2` | 하류 사용 없음 |

STEP 6이 STEP 3으로 되돌려 보내는 위반 경로(`FIX_ROUTE`, 129~138행)

| route | 위반(validateDs의 shape 문구) | 복귀 위치 라벨 |
|---|---|---|
| `publisher` | `PublisherShape — sh:nodeKind sh:IRI (publisher 결측)` | `publisher 필드` |
| `mediaType` | `MediaTypePlacementShape — Distribution 결측` | `mediaType 드롭다운` |
| `emptyLit` | (빈 리터럴) | `해당 필드` |
| `stream3` | `스트림 필수 — temporalResolution·eventTime 결측` | `스트림 속성 카드` |

---

## 4. 데이터 (목업에 하드코딩된 값 전량)

### 4.1 화면에 표시되는 메타데이터 필드 목록

| # | 프러퍼티 | 도메인(귀속 클래스) | 수준 | 입력 형태 | 목업 예시값 | 정본 반영 여부 |
|---|---|---|---|---|---|---|
| 1 | `dcterms:publisher` | dcat:Dataset → foaf:Agent IRI | ARD 필수(승인 필요) | 텍스트 + 자동 IRI | `국토교통부`, placeholder `예: 국토교통부(데모)` | 반영(`publisher.id`, `publisher.label`) |
| 2 | `dcat:mediaType` (ARD 카드) | dcat:Distribution | ARD 필수(파일형, 승인 필요) | IANA 셀렉트 | 4.4절 | 반영(`distribution.mediaType`) |
| 3 | `dcterms:title` | dcat:Dataset | 필수 | 텍스트 | 데이터셋 이름 | 반영(이름 그대로, 편집 불가) |
| 4 | `dcterms:identifier` | dcat:Dataset | 필수 | 읽기 전용 + `확인` | `DST-000123` / `DST-신규 (확정 시 발급)` | 별도 규칙(`mintId`) |
| 5 | `dcat:mediaType` (폼) | dcat:Distribution | 필수 | 읽기 전용 + `확인` | `application/vnd.apache.parquet` 등 | 미반영(표시용) |
| 6 | `dcat:accessURL` | dcat:Distribution | 필수 | 텍스트 | `https://lake.molit.go.kr/{slug}` | 미반영 |
| 7 | 두 번째 배포본 `dcat:mediaType` | dcat:Distribution | 선택 추가 | 텍스트 | `text/csv` | 미반영 |
| 8 | 두 번째 배포본 `dcat:accessURL` | dcat:Distribution | 선택 추가 | 텍스트 | placeholder `접근 URL 입력…` | 미반영 |
| 9 | `dcat:temporalResolution` | dcat:DataService | 스트림 `필수` | 텍스트(ISO 8601 duration) | `PT5M`, 배지 `Avro 스키마에서 추론` | META_TABLE 값만 반영 |
| 10 | `event-time 컬럼` (`fde:eventTimeColumn`) | dcat:DataService | 스트림 필수(정본 기준) | 텍스트 | `OBSV_DT`, 주석 `↔ STEP 4 K7 시각 매핑과 동기화` | META_TABLE 값만 반영 |
| 11 | `타임존` | dcat:DataService | 스트림 `필수` | 텍스트 | `Asia/Seoul (+09:00)` | 미반영 |
| 12 | `워터마크 지연 허용` | dcat:DataService | 스트림 `권장` | 텍스트 | placeholder `PT2M 권장 — 미선언`, 배지 `Warning — STEP 7 연동` | 미반영 |
| 13 | `지각(late) 데이터 정책` | dcat:DataService | 스트림 선택 | 셀렉트 | `별도 적재 (late 파티션)` / `폐기` / `보정 재계산` | 미반영 |
| 14 | `dcat:inSeries` (DCAT 3.0) | dcat:Dataset, range dcat:DatasetSeries | 권장 | 텍스트 | `SER-0004 교통소통 시리즈` | 미반영 |
| 15 | `dcat:version` (DCAT 3.0) | dcat:Dataset | 권장 | 텍스트 | 폼 `2.4.1`, 미리보기 `1.0.0` | 미반영 |
| 16 | `owl:versionInfo` | dcat:Dataset | 권장(병기) | 미리보기에만 표시 | `1.0.0` | 미반영 |
| 17 | `dcterms:accrualPeriodicity` | dcat:Dataset | 선택 | 텍스트 | `5분` (경고 `비표준 표기`) | 미반영 |
| 18 | `dcterms:description` | 조합(결합 데이터셋) | STEP 2 입력분 인계 표시 | 표시 전용 | `{cmDesc}` | 미반영 |
| 19 | `prov:wasGeneratedBy` | dcat:Dataset → prov:Activity | 자동 | 미리보기에 표시 | `ACT-draft-{hash6}` | 반영(자동) |
| 20+ | 추가 프러퍼티(4.6절 11종) | 다양 | 선택 | 텍스트(placeholder `값 입력…`) | | 미반영 |

정본 트리플 전체(`buildTriples`, 187~212행). STEP 3에서 승인한 값이 최종적으로 만들어 내는 출력이다.

| 주어 | 술어 | 목적어 | 생성 조건 |
|---|---|---|---|
| 데이터셋 ID | `rdf:type` | `dcat:Dataset` (스트림이면 `dcat:DataService` 추가) | 항상 |
| 데이터셋 ID | `dcterms:title` | 이름 `@ko` | 제목 존재 |
| 데이터셋 ID | `dcterms:publisher` | 기관 IRI | publisher 존재 |
| 기관 IRI | `rdf:type` / `rdfs:label` | `foaf:Agent` / 기관명 `@ko` | publisher 존재 |
| 데이터셋 ID | `dcat:distribution` | 배포본 ID | 파일형이고 mediaTypeIana 존재 |
| 배포본 ID | `rdf:type` / `dcat:mediaType` | `dcat:Distribution` / `https://www.iana.org/assignments/media-types/{mt}` | 위와 같음 |
| 데이터셋 ID | `dcterms:format` | `form` 라벨 `@ko` (예: `정형(엑셀)`) | 배포본 라벨 존재 |
| 데이터셋 ID | `dcat:temporalResolution` | 예 `PT1S` | 스트림 |
| 데이터셋 ID | `fde:eventTimeColumn` | 예 `event_time` | 스트림 |
| 데이터셋 ID | `dcat:endpointDescription` | `https://api.molit.go.kr/streams/{hash6(제목)}` | 스트림 |
| 데이터셋 ID | `prov:wasGeneratedBy` | Activity ID | 항상 |
| Activity ID | `rdf:type` / `prov:wasAssociatedWith` | `prov:Activity` / `https://catalog.molit.go.kr/id/agent/fde-studio` | 항상 |
| Activity ID | `prov:endedAtTime` | `convertTimeIso` `^^xsd:dateTime` | STEP 7 변환 실행 후 |

네임스페이스(225~234행): `rdf`, `rdfs`, `dcat`(`http://www.w3.org/ns/dcat#`), `dcterms`(`http://purl.org/dc/terms/`), `prov`(`http://www.w3.org/ns/prov#`), `foaf`(`http://xmlns.com/foaf/0.1/`), `xsd`, `fde`(`https://catalog.molit.go.kr/def/`).

### 4.2 주 클래스 카드 (M:516, logic 2010~2014행)

| 클래스 | 설명 | 태그 | 선택 방식 |
|---|---|---|---|
| `dcat:Dataset` | 데이터셋 정본 기술. 정형·반정형·비정형 공통 기본 클래스 | `★ 추천` | 항상 선택(고정) |
| `dcat:Distribution` | 포맷·접근URL 등 배포 단위 기술 | 없음 | 토글 |
| `dcat:DataService` | 실시간 스트림 선택 시 자동 전환 — endpointURL · 보존정책 · 종료조건 | `실시간` | 토글 |
| `dcat:DatasetSeries` | 연도별·버전별 시리즈 묶음 | `3.0` | 토글 |
| `dcat:Catalog` | 카탈로그 자체의 기술 단위 | 없음 | 토글 |

### 4.3 시간 규격 카드 필드 (M:653~657)

| 라벨 | 수준 표시 | 기본값 / placeholder | 우측 주석 |
|---|---|---|---|
| `dcat:temporalResolution` | `필수` | `PT5M` | `Avro 스키마에서 추론` |
| `event-time 컬럼` | (없음) | `OBSV_DT` | `↔ STEP 4 K7 시각 매핑과 동기화` |
| `타임존` | `필수` | `Asia/Seoul (+09:00)` | |
| `워터마크 지연 허용` | `권장` | placeholder `PT2M 권장 — 미선언` | `Warning — STEP 7 연동` |
| `지각(late) 데이터 정책` | (없음) | 옵션 `별도 적재 (late 파티션)` · `폐기` · `보정 재계산` | |

### 4.4 IANA 미디어타입 옵션 (`IANA_OPTS`, 124~127행 / 옵션 생성 2878행)

| value | 표시 라벨 |
|---|---|
| (빈 값) | `— IANA 미디어타입 선택 —` |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `xlsx — application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `text/csv` | `csv — text/csv` |
| `application/json` | `json — application/json` |
| `application/x-hwp` | `hwp — application/x-hwp` |
| `application/pdf` | `pdf — application/pdf` |

직렬화 IRI: `https://www.iana.org/assignments/media-types/{value}` (148행).

### 4.5 데이터셋 기준 메타 테이블과 기관 (`META_TABLE`, 106~116행)

키는 데이터셋 이름(업로드 파일명에서 확장자를 뗀 값 또는 스트림 토픽명)이다.

```json
{
  "sample_공간정보_통합포털_데이터셋_목록_도로": { "kind": "dataset", "org": "국토교통부", "orgId": "https://catalog.molit.go.kr/id/org/ORG-1613000", "form": "정형(엑셀)", "mediaTypeIana": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "role": "도로 공간정보 — 사고 원인 분석 조합 베이스" },
  "cctv.vehicle.det.v1": { "kind": "stream", "org": "경기도건설본부(데모)", "orgId": "https://catalog.molit.go.kr/id/org/ORG-6410000", "form": "실시간 스트림(관측)", "role": "CCTV 차량 관측 — 과속·사고 판정 입력", "temporalResolution": "PT1S", "eventTime": "event_time" },
  "kma.aws.obs.v1": { "kind": "stream", "org": "기상청(외부 출처)", "orgId": "https://catalog.molit.go.kr/id/org/ORG-1360000", "form": "실시간 스트림(컨텍스트)", "role": "기상 관측 — 조건부 기준값 판정 컨텍스트", "temporalResolution": "PT10M", "eventTime": "obs_time" },
  "sample_교통사고심층조사시스템_비정형_": { "kind": "dataset", "org": "경찰청·도로교통공단(데모)", "orgId": "https://catalog.molit.go.kr/id/org/ORG-1320000", "form": "정형(엑셀)", "mediaTypeIana": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "role": "교통사고 심층조사 — 사고 원인·사상 정보" },
  "sample_데이터오픈마켓(30종)": { "kind": "dataset", "org": "국토교통부", "orgId": "https://catalog.molit.go.kr/id/org/ORG-1613000", "form": "정형(엑셀)", "mediaTypeIana": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "role": "오픈마켓 30종 목록 — 사고심층조사 연관 그룹" },
  "sample_디지털운행기록분석시스템(eTAS)": { "kind": "dataset", "org": "한국교통안전공단(데모)", "orgId": "https://catalog.molit.go.kr/id/org/ORG-B552016", "form": "정형(엑셀)", "mediaTypeIana": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "role": "차량 운행기록 — 차량 흐름 분석 입력" },
  "sample_실시간기상관측자료수집시스템_기상청_": { "kind": "dataset", "org": "기상청(외부 출처)", "orgId": "https://catalog.molit.go.kr/id/org/ORG-1360000", "form": "정형(엑셀)", "mediaTypeIana": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "role": "기상 관측 수집 목록 — 협약 확인 필요" },
  "실시간교통사고": { "kind": "stream", "org": "국토교통부(데모)", "orgId": "https://catalog.molit.go.kr/id/org/ORG-1613000", "form": "실시간 스트림(관측)", "temporalResolution": "PT5M", "eventTime": "event_time", "role": "실시간 교통사고 이벤트 — 관제 통보 입력" },
  "디지털운행기록분석시스템(eTAS)_정보시스템": { "kind": "dataset", "org": "한국교통안전공단(데모)", "orgId": "https://catalog.molit.go.kr/id/org/ORG-B552016", "form": "정형(엑셀)", "mediaTypeIana": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "role": "차량 운행기록 분석 — 차량 흐름 분석 입력" }
}
```

필드 의미: `kind`(dataset=파일형 / stream=dcat:DataService 병기), `org`(publisher 라벨), `orgId`(publisher Agent IRI), `form`(dcterms:format 라벨이자 문장화 문구), `mediaTypeIana`(IANA 미디어타입), `role`(문장화용 역할 설명), `temporalResolution`(ISO 8601 duration), `eventTime`(event-time 컬럼명).

기관 시드(위 표에서 중복 제거)

| 기관 코드 | 기관 IRI | 라벨(목업 표기) |
|---|---|---|
| ORG-1613000 | `https://catalog.molit.go.kr/id/org/ORG-1613000` | `국토교통부`, `국토교통부(데모)` |
| ORG-6410000 | `https://catalog.molit.go.kr/id/org/ORG-6410000` | `경기도건설본부(데모)` |
| ORG-1360000 | `https://catalog.molit.go.kr/id/org/ORG-1360000` | `기상청(외부 출처)` |
| ORG-1320000 | `https://catalog.molit.go.kr/id/org/ORG-1320000` | `경찰청·도로교통공단(데모)` |
| ORG-B552016 | `https://catalog.molit.go.kr/id/org/ORG-B552016` | `한국교통안전공단(데모)` |
| (수기 입력) | `https://catalog.molit.go.kr/id/org/ORG-{hash6(입력 문자열)}` | 입력값 그대로 |

시스템 Agent: `https://catalog.molit.go.kr/id/agent/fde-studio` (209행).

식별자 규칙

- 발행 모드 민팅 맵(`MINT_MAP`, 117~123행): `kma.aws.obs.v1`→`SVC-000041`, `cctv.vehicle.det.v1`→`SVC-000042`, `sample_공간정보_통합포털_데이터셋_목록_도로`→`DST-000961`, `실시간교통사고`→`SVC-000043`, `디지털운행기록분석시스템(eTAS)_정보시스템`→`DST-000962`. 배포본·Activity는 `{본체ID}-DIST`, `{본체ID}-ACT`.
- 초안 모드(`mintId`, 150~162행): `{접두}-draft-{hash6(이름)}`. 접두는 `DST`(파일형)·`SVC`(스트림)·`DIST`·`ACT`.
- `hash6`(139행): 문자별 `h = (h + charCode*31) % 999999`, 6자리 0채움. 예: `sample_공간정보_통합포털_데이터셋_목록_도로` → `594866`, `cctv.vehicle.det.v1` → `055490`, `실시간교통사고` → `398805`.
- 폼 표시용 구식 ID 맵(1943행): `TRAFFIC_LINK_5MIN`→`DST-000123`, `ADMIN_SGG 행정경계`→`DST-000871`, `etas_inspect_log`→`DST-000541`, `obu.telemetry.v2`→`SVC-000034`. 정본 ID와는 별개 체계이다.
- 폼 표시용 배포본 ID(1955행): `{구식ID 또는 'DST-신규'}-{업로드 확장자 또는 'pq'}`.

### 4.6 조회 어휘 3종 (1755~1790행)

공통 규칙: `r: true` 는 `★ 추천`, 유형이 `실시간 스트림`이면 `비추천 (선 전처리 필요)`, 나머지는 `적합`. 유형 값은 `공통` / `정형` / `반정형` / `비정형` / `실시간 스트림`. 필터 라벨은 `전체` / `정형` / `반정형` / `비정형` / `실시간 스트림` (1737행).

**(a) 추가 클래스 10종** (화면 문구상 "42종"이나 실제 데이터는 10건)

| 클래스 | 설명 | 유형 | 추천 | 근거(evidence, 1794~1805행) | 연쇄 추천(chain) |
|---|---|---|---|---|---|
| `prov:Entity` | 활동의 입·출력이 되는 일반 개체 — 리니지 중간 산출물에 적합 | 공통 | ★ | 업로드 원본 분석 — 중간 산출물 3건(생활권 구획·중심점) 감지, dcat:Dataset 미달 개체 존재 | prov:qualifiedDerivation (프로버넌스) · dcterms:conformsTo (프러퍼티) |
| `dcat:CatalogRecord` | 카탈로그 내 등재 레코드 자체의 이력 기술 | 공통 | | 등재 이력 관리 요건(가이드라인 표12) 해당 | dcterms:modified · foaf:primaryTopic (프러퍼티) |
| `prov:Collection` | 개체 묶음 (조합 단위 기술) | 공통 | | 내 작업 조합이 4개 데이터셋 묶음 — 조합 단위 기술 가능 | prov:hadMember (프로버넌스) |
| `dcterms:Standard` | 준수 표준(dcterms:conformsTo 대상) 기술 | 공통 | | ISO 8601 정규화 조치(로드맵 4위) 진행 중 — 준수 표준 명시 필요 | dcterms:conformsTo (프러퍼티) |
| `csvw:Table` | 표 형태 데이터의 컬럼·스키마 구조 기술 (CSV on the Web) | 정형 | | 업로드 원본 중 CSV 배포본 예정(DIST-000123-csv) 감지 | csvw:primaryKey · csvw:null (프러퍼티) |
| `qb:DataSet` | 통계 큐브(차원·측정값) 구조 기술 (RDF Data Cube) | 정형 | | 5분 격자 시계열 — 차원(링크×시각)·측정값(속도·교통량) 구조 일치 | qb:dimension · qb:measure (프러퍼티) |
| `csvw:Schema` | JSON·로그 등 추론 스키마의 필드 구조 기술 | 반정형 | | etas_inspect_log 추론 스키마(신뢰 92%) 보유 — 필드 구조 명시 가능 | csvw:null (프러퍼티) · prov:specializationOf (프로버넌스) |
| `foaf:Document` | 보고서·문서 원본(PDF·HWP)의 문서 단위 기술 | 비정형 | | 도로안전점검 보고서 312건(PDF·HWP) — 문서 단위 기술 대상 | dcterms:language · dcterms:extent (프러퍼티) · prov:wasQuotedFrom (프로버넌스) |
| `dcat:DataService` | 스트림·API 서비스 단위 기술 — endpointURL 필수 | 실시간 스트림 | ★(표시는 비추천) | obu.telemetry.v2 스트림 감지 — 단, 현재 조합은 정형 배치 | dcat:temporalResolution · dcat:endpointDescription (프러퍼티) · prov:hadPlan (프로버넌스) |
| `prov:Plan` | 정렬·이벤트 판정 규칙의 버전 단위 기술 | 실시간 스트림 | | 스트림 판정 규칙 미연결 — 스트림 관리 탭 선행 필요 | prov:hadPlan (프로버넌스) |

클래스 경고 문구(1806~1809행)

- `dcat:DataService`: `스트림 데이터는 선 전처리(5분 격자 정렬 · 워터마크 · late 처리)를 거쳐 배치로 적재된 뒤에야 정형 조합과 병행 기술이 가능합니다. PLN-ALN-002 정렬 규칙 선행 적용을 확인하세요.`
- `prov:Plan`: `판정 Plan은 스트림 처리 규칙 전용 클래스입니다. 정형 배치 조합에는 판정 대상 스트림이 없으므로, 스트림 관리 탭에서 스트림 연결 후 사용하세요.`
- 그 외 기본값: `이 클래스는 현재 조합의 데이터 유형과 다릅니다.`

**(b) 추가 프러퍼티 11종** (근거는 `evMap`, 1845~1855행)

| 프러퍼티 | 설명 | 유형 | 추천 | 근거 |
|---|---|---|---|---|
| `dcat:byteSize` | 배포본 크기 (Distribution) | 공통 | | |
| `spdx:checksum` | 접합부 대조용 체크섬 | 공통 | ★ | 접합부 계약 대조에 사용 중 — 신규 배포본(CSV)에 미부여 |
| `dqv:hasQualityMeasurement` | 품질 측정값 연결 (DQV) | 공통 | | |
| `dcterms:conformsTo` | 준수 스키마·표준 참조 | 정형 | ★ | 준수 표준 명시 조치(로드맵 4위) 진행 중 — 스키마 참조 필요 |
| `csvw:primaryKey` | 기본키 컬럼 지정 | 정형 | | 원본 분석 — PK 컬럼(LINK_ID) 자동 감지됨 |
| `dcat:compressFormat` | 압축 포맷 (gzip·snappy) | 정형 | | |
| `csvw:null` | 결측치 표기 규칙 선언 | 반정형 | | |
| `dcterms:language` | 문서 언어 (ko) | 비정형 | | 보고서 312건 한국어 문서 감지 |
| `dcterms:extent` | 문서 분량 (페이지 수·크기) | 비정형 | | |
| `dcat:temporalResolution` | 시간 해상도 (ISO 8601 duration) | 실시간 스트림 | ★(표시는 비추천) | 5분 격자 시계열 감지 — 단, 스트림 선언은 DataService 소관 |
| `dcat:endpointDescription` | 엔드포인트 규격 문서 (Avro 스키마 등) | 실시간 스트림 | | |

**(c) 추가 프로버넌스 9종**

| 항목 | 설명 | 유형 | 추천 | 근거 |
|---|---|---|---|---|
| `prov:wasRevisionOf` | 개정 관계 — 이전 버전 연결 | 공통 | | |
| `prov:qualifiedDerivation` | 파생 관계에 confidence·규칙 버전 속성 부여 | 공통 | ★ | WAS_DERIVED_FROM 엣지 3건에 confidence 속성 미부여 |
| `prov:atLocation` | 활동·개체의 위치 (레이크 경로 등) | 공통 | | |
| `prov:invalidatedAtTime` | 폐기·무효화 시점 기록 | 공통 | | |
| `prov:qualifiedAssociation` | 가공 규칙 승인자·역할 연결 (정제 파이프라인) | 정형 | | 가공 규칙 rs-2.1 승인자 연결 누락 |
| `prov:specializationOf` | 추론 스키마 버전의 일반화 관계 | 반정형 | | |
| `prov:wasQuotedFrom` | 문서 발췌(청킹) 출처 연결 — RAG 코퍼스 추적 | 비정형 | ★ | RAG 코퍼스 청킹 512 tokens 설정 — 발췌 출처 연결 필요 |
| `prov:hadPlan` | 판정 Plan 버전 귀속 — 이벤트 재현 근거 | 실시간 스트림 | ★(표시는 비추천) | 판정 Plan(PLN-EVT-001) 가동 중 — 파생 이벤트 귀속 필요 |
| `prov:SoftwareAgent` | 배치·스트림 러너 등 소프트웨어 주체 Agent | 실시간 스트림 | | |

프러퍼티·프로버넌스 공통 경고 문구(1872행): `스트림 관련 항목은 선 전처리(정렬·워터마크) 및 DataService 선언 이후에 유효합니다.`

**비추천 선택 사유 옵션**(세 조회 카드 공통, M:554·705·825)

1. `스트림 전처리 완료본을 함께 등록 예정`
2. `차기 단계에서 스트림 연계 확정`
3. `기타 (직접 입력)`

### 4.7 프로버넌스 데이터

**(a) 생애주기 7단계** (`lifecycle` 412~418행, `lcData` 419~427행)

| # | 단계(노드) | 상세 제목 | prov:Activity | 담당 Agent | 기간 | 입력 (prov:used) | 산출 (prov:generated) | 기록 속성 | 상태 배지 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 계획 | ① 계획 | ACT-K-0288 | 국토교통 빅데이터센터 (기획) | 2026-03-02 ~ 03-20 | 데이터 수요 조사서 | 수집 계획서 · 대상 소스 4종 정의 | plannedSources=4 · reviewCycle=분기 | prov:Activity 기록됨 (자동+수기) |
| 1 | 수집 | ② 수집 | ACT-K-0301 | 한국도로공사 교통센터 | 2026-04-01 ~ 상시 (5분 주기) | 검지기 원시 스트림 · OBU 텔레메트리 | 원천 파일 (레이크 통제구역 적재) | ingestRate=12,400 msg/s · 결측 규칙 v1.4 | prov:Activity 기록됨 (자동) |
| 2 | 처리·가공 | ③ 처리·가공 | ACT-K-0412 | KOPSS · 빅데이터센터 | 2026-08-12 09:41 ~ 09:44 | 원천 파일 (TRAFFIC_LINK_RAW) | 정제 Parquet (DIST-000123-pq) | 좌표계 EPSG:5181→4326 · ISO 8601 정규화 · rs-2.1 | prov:Activity 기록됨 (자동) |
| 3 | 저장·등록 | ④ 저장·등록 | ACT-K-0415 | 데이터 검수팀 (2인) | 2026-08-14 11:05 | 정제 Parquet + 프로파일 통계 | DCAT 카탈로그 항목 (DST-000123) | F1·F2·K 분류 확정 · 신뢰도 96% | prov:Activity 기록됨 (자동+수기) |
| 4 | 공개·제공 | ⑤ 공개·제공 | — (예정) | 국토교통 빅데이터센터 | 발행 승인 후 | Turtle 정본 | 개방구역 투영본 ◀ · API/MCP 채널 | 필터 규칙: 샘플 레코드·프로파일 통계 제외 | 대기 (예정) |
| 5 | 활용 | ⑥ 활용 | — (예정) | 활용 기관 · sLLM | 발행 이후 상시 | 문장화 코퍼스 · 개방 투영본 | 혼잡지수 파생 컬럼 · RAG 응답 | API 호출·다운로드 이력 집계 | 대기 (예정) |
| 6 | 폐기·보존 | ⑦ 폐기·보존 | — (예정) | 국토교통 빅데이터센터 | 등록일 + 5년 | 보존 대상 정본 | 보존 아카이브 · 폐기 확인서 | prov:wasInvalidatedBy 기록 · 보존 5년 | 대기 (예정) |

노드 보조 문구: 인덱스 0·3 `ACT 기록됨 · 자동+수기`, 1·2 `ACT 기록됨 · 자동`, 4~6 `대기`. 점 색상: 0~3 녹색, 4~6 회색.

단계별 설명문(`lcNote`)

0. `수집 대상(검지기·OBU·검사로그·보고서)과 연계키 축(K5·K6·K7)을 정의한 계획 단계. 계획서 자체도 prov:Entity로 등록되어 후속 Activity가 참조합니다.`
1. `원본은 레이크에 그대로 보존되고 푸터에 식별자·활동ID가 기입됩니다. 수집 실패·재시도도 동일 Activity 속성으로 계측됩니다.`
2. `변환·정제 파라미터가 이 Activity 속성으로 기록됩니다 — 동일 입력 + 동일 파라미터 = 동일 산출이라는 재현 계약의 근거입니다.`
3. `카탈로그 등록과 다중분류 확정이 일어나는 단계. spdx:checksum이 산출되어 STEP 7 접합부 계약 점검의 대조 기준이 됩니다.`
4. `STEP 7 발행 승인(Violation 0건) 시 자동 실행 예정 — 개방 push·API 전송·MCP 갱신 알림이 각각 별도 Activity로 기록됩니다.`
5. `문장화·임베딩·학습셋 구성은 마트 측 Activity로 기록되며, 산출물이 재등록되면 리니지가 이어집니다. 활용 이력은 관리 > 사용 이력과 연동되어 집계됩니다.`
6. `폐기 시에도 카탈로그 항목은 삭제하지 않고 무효화(invalidation) Activity로 종결 — 리니지 추적성이 유지됩니다.`

**(b) 단계별 Agent 3종** (`lcAgents`, 1685~1693행)

| 단계 | 역할 라벨 | Agent 이름 | prov 유형 |
|---|---|---|---|
| 0 계획 | 계획 수립 Agent | 빅데이터센터 기획팀 | prov:Organization |
| 0 | 수요 검토 Agent | 정보화기획담당관 | prov:Organization |
| 0 | 승인 Agent | 변학도 (관리자) | prov:Person |
| 1 수집 | 생산 책임자 Agent | 한국도로공사 교통센터 | prov:Organization |
| 1 | 수집 운영 Agent | 수집운영과 (정 홍길동) | prov:Person |
| 1 | 스트림 운영 Agent | eTAS 운영팀 | prov:Organization |
| 2 처리·가공 | 가공 수행 Agent | KOPSS | prov:SoftwareAgent |
| 2 | 가공 책임자 Agent | 국토교통 빅데이터센터 | prov:Organization |
| 2 | 규칙 승인 Agent | 데이터 검수팀 (2인) | prov:Person |
| 3 저장·등록 | 등록 책임자 Agent | 메타데이터 표준화팀 | prov:Organization |
| 3 | 분류 확정 Agent | 김검수 (담당자) | prov:Person |
| 3 | 검증 Agent | SHACL 엔진 rs-2.1 | prov:SoftwareAgent |
| 4 공개·제공 | 유통 책임자 Agent | 국토교통 빅데이터센터 | prov:Organization |
| 4 | 발행 승인 Agent | 변학도 (관리자) | prov:Person |
| 4 | 개방 push Agent | 개방 투영 파이프라인 | prov:SoftwareAgent |
| 5 활용 | 활용 책임자 Agent | 데이터 검수팀 (2인) | prov:Person |
| 5 | 활용 기관 Agent | KOPSS · 활용 기관 | prov:Organization |
| 5 | 소비 Agent | sLLM-molit-7b | prov:SoftwareAgent |
| 6 폐기·보존 | 보존 책임자 Agent | 국토교통 빅데이터센터 | prov:Organization |
| 6 | 폐기 승인 Agent | 정보화기획담당관 | prov:Organization |
| 6 | 무효화 기록 Agent | 카탈로그 시스템 | prov:SoftwareAgent |

**(c) 단계별 파라미터** (`lcParamTitle` 1694행, `lcParams` 1695~1703행)

| 단계 | 카드 제목 | 파라미터 1 | 파라미터 2 | 파라미터 3 |
|---|---|---|---|---|
| 0 | 계획 파라미터 기록 | 수집 대상 소스 = 4종 (검지기·OBU·검사로그·보고서) | 연계키 축 = K5 · K6 · K7 | 검토 주기 = 분기 1회 |
| 1 | 수집 파라미터 기록 | 처리량 = 12,400 msg/s | 결측 규칙 = v1.4 (null·-999 통일) | 재시도 정책 = 3회 · 백오프 30s |
| 2 | 재현 파라미터 기록 | 좌표계 변환 = EPSG:5181 → 4326 | 정규화 규칙 버전 = rs-2.1 (ISO 8601 시간 정규화) | 결측 보간 규칙 = v1.4 (null·-999 통일) |
| 3 | 등록 파라미터 기록 | 분류 신뢰도 임계값 = 0.85 (미달 시 검수 큐) | 체크섬 알고리즘 = SHA-256 (spdx:checksum) | Shape 세트 = DatasetShape 외 4종 |
| 4 | 발행 파라미터 기록 | 개방 필터 규칙 = 샘플 레코드·프로파일 통계 제외 | push 방향 = 통제 → 개방 단방향 ◀ | 전송 채널 = API · MCP · 포털 push |
| 5 | 활용 파라미터 기록 | 학습 하이퍼파라미터 = lr 2e-5 · epoch 3 · batch 32 | 임베딩 모델 = ko-e5-large v1.2 | 청킹 설정 = 512 tokens · overlap 64 |
| 6 | 보존 파라미터 기록 | 보존 기간 = 등록일 + 5년 | 무효화 기록 = prov:wasInvalidatedBy | 아카이브 위치 = 콜드 스토리지 (180일 후) |

**(d) AI 추천 리니지 공백 후보 3건** (`provRecRows`, 1894~1898행)

| id | 단계 귀속 배지 | 이름 | 추천 사유 | 연결 효과 문구 |
|---|---|---|---|---|
| `ACT-K-0388` | ③ 처리·가공 귀속 | 좌표계 변환 (EPSG:5181→4326) | 처리·가공 단계와 저장·등록 단계 사이 Activity 공백 | ③ 처리·가공 Activity 체인에 삽입 연결 |
| `AGT-012` | ② 수집 귀속 | 한국교통안전공단 eTAS 운영팀 (prov:Organization) | etas_inspect_log의 생산 책임자 Agent 미연결 | 생산 책임자 Agent로 prov:wasAttributedTo 연결 |
| `ACT-K-0301` | ③ 처리·가공 귀속 | 결측치 보간 규칙 적용 v1.4 | (없음) | ③ 처리·가공 Activity에 prov:wasInformedBy 연결 |

### 4.8 클래스별 Turtle 스텁 (`stubs`, 1916~1927행)

선택된 추가 클래스마다 미리보기에 아래 문자열이 그대로 삽입된다. 목록에 없으면 `# {클래스명} — 타이핑 대상 리소스 확인 필요`.

```turtle
# prov:Entity
<DST-000123> a dcat:Dataset, prov:Entity .
# qb:DataSet
<DST-000123> a dcat:Dataset, qb:DataSet .
# prov:Collection
<COL-0007> a prov:Collection ;
  prov:hadMember <DST-000123>, <DST-000541> .
# dcat:CatalogRecord
<REC-000123> a dcat:CatalogRecord ;
  foaf:primaryTopic <DST-000123> .
# foaf:Document
<DOC-000712> a foaf:Document ;
  dcterms:title "도로안전점검 보고서"@ko .
# csvw:Table
<DIST-000123-csv> a dcat:Distribution, csvw:Table .
# csvw:Schema
<SCH-000541> a csvw:Schema .
# dcterms:Standard
<STD-ISO8601> a dcterms:Standard .
<DST-000123> dcterms:conformsTo <STD-ISO8601> .
# dcat:DataService
# dcat:DataService — 기존 <SVC-000034> 블록 참조 (신규 블록 없음)
# prov:Plan
<PLN-EVT-001> a prov:Plan ; dcat:version "1.3" .
```

여기서 읽히는 타이핑 규칙: `prov:Entity`·`qb:DataSet` 은 데이터셋 주어에 병기, `csvw:Table` 은 배포본에 병기, `prov:Collection`·`dcat:CatalogRecord`·`foaf:Document`·`csvw:Schema`·`dcterms:Standard`·`prov:Plan` 은 별도 리소스를 만들고 데이터셋과 관계(hadMember, primaryTopic, conformsTo)로 연결한다.

### 4.9 관계 맵 고정 그래프 (M:854~886)

| 노드 | 부제 | 종류 |
|---|---|---|
| `dcat:Dataset` | `{ds3Id} · 선택 클래스` | 클래스(중심) |
| `dcat:Distribution` | `{ds3DistId}` | 클래스 |
| (리터럴 박스) | `{ds3MediaShort}` : `"application/…sheet"` / `"text/csv"` / `"application/…parquet"` | 값 |
| `dcat:DatasetSeries` | `SER-신규 (시리즈 미지정)` | 클래스 |
| `prov:Activity` | `ACT-신규 (확정 시 발급)` | 프로버넌스 |
| `prov:Agent` | `{ds3Agent}` : `기상청 (타 부처)` / `행정안전부 (타 부처)` / `국토교통부 소관 시스템` | 프로버넌스 |

| 엣지 | 출발 → 도착 | 선 |
|---|---|---|
| `dcat:distribution` | Dataset → Distribution | 파랑 실선 |
| `dcat:inSeries` | Dataset → DatasetSeries | 파랑 실선 |
| `dcat:mediaType` | Distribution → 리터럴 박스 | 파랑 점선 |
| `prov:wasGeneratedBy` | Dataset → Activity | 주황 실선 |
| `prov:wasAttributedTo` | Dataset → Agent | 주황 실선 |
| `prov:wasAssociatedWith` | Activity → Agent | 주황 점선 |

### 4.10 Turtle 미리보기 템플릿 (M:951~960)

```turtle
<{ds3CanonId}> a dcat:Dataset ;
  dcterms:title "{ds3Title}"@ko ;
  dcterms:publisher <{ds3PubId}> ;            # ds3PubOn(정본에 publisher가 있을 때)만
  dcat:version "1.0.0" ;                      # 고정 문자열
  owl:versionInfo "1.0.0" ;                   # 고정 문자열
  dcat:distribution <{ds3DistId}> ;           # ds3MtOn(정본에 distribution이 있을 때)만
  prov:wasGeneratedBy
    <{ds3ActId2}> .
{clsSelStubs[].text ...}                      # 4.8절
<{ds3DistId}> a dcat:Distribution ;           # ds3MtOn일 때만
  dcat:mediaType <{ds3MtIri}> ;
  dcat:accessURL <{ds3Url}> .
<{ds3PubId}> a foaf:Agent ;                   # ds3PubOn일 때만
  rdfs:label "{ardPub}"@ko .
```

바인딩 출처(2896~2901행): `ds3CanonId = canonical.id`, `ds3PubId = canonical.publisher.id`, `ds3MtIri = ianaIri(canonical.distribution.mediaType)`, `ds3ActId2 = canonical.activity.id`. 정본이 없으면 `DST-…`, `ACT-…`.

### 4.11 우측 패널 생산 조직 판정 (1965~1967행)

| 이름 정규식 | 기관 표기 | 결과 |
|---|---|---|
| `/기상청/` | 기상청 | 경고 `✕ {이름}` / `기상청 (타 부처) — 협약 확인 필요` |
| `/행정안전부\|행안부/` | 행정안전부 | 경고 |
| `/경찰청/` | 경찰청 | 경고 |
| 그 외 | (없음) | `orgOkCount` 에 합산, `국토교통부 계열 ✓` |

---

## 5. 상태 변수

| 키 | 타입 | 기본값 | 의미 | 저장 범위 |
|---|---|---|---|---|
| `tab3` | 1~4 | 1 | 하위 탭 | 초안·프로세스 스냅숏 |
| `ds3` | number | 0 | 현재 작성 대상의 `combo` 인덱스 | 초안·프로세스 |
| `ds3Done` | `{[index]: true}` \| null | null | 확정 완료한 데이터셋. **키가 이름이 아니라 인덱스** | 초안·프로세스 |
| `ds3Fold` | boolean | false | 인계 카드 접힘 | 초안·프로세스 |
| `metaOver` | `{[datasetName]: {org, orgId, mediaTypeIana, approved}}` | undefined | publisher·mediaType 덮어쓰기와 승인 여부. 키는 데이터셋 이름 | 초안만. 프로세스 스냅숏(`workKeys`, 920행)에는 **빠져 있음** |
| `mainSel` | `{[className]: true}` \| null | null | 주 클래스 카드 선택 | 초안·프로세스 |
| `clsSel` / `propSel` / `provSel` | `{[name]: true}` \| null | null | 추가 클래스 / 프러퍼티 / 프로버넌스 선택. 데이터셋 구분 없이 전역 1벌 | 초안·프로세스 |
| `clsWarn` / `propWarn` / `provWarn` | string \| null | null | 비추천 경고 패널이 열린 행 이름 | 초안 |
| `clsDone` / `propDone` / `provDone` | string \| null | null | 완료 패널이 열린 행 이름 | 초안·프로세스 |
| `cls` / `prop` / `prov` | string | `'전체'` | 세 조회 카드의 유형 필터 | 초안 |
| `provRec` | `{[id]: true}` | undefined | AI 추천 공백 후보 연결 여부 | 초안·프로세스 |
| `provRecDone` | string \| null | undefined | 방금 연결한 추천 id | 초안 |
| `lc` | 0~6 | 2 | 생애주기 타임라인 선택 단계 | 초안 |
| `dist2` | boolean | false | 두 번째 배포본 블록 표시 | 초안·프로세스 |
| `rpHide` / `rpW` | boolean | false | 우측 패널 숨김 / 확장 | 초안 |
| `rp1` / `rp2` / `rp3` | boolean | undefined(펼침) | 우측 패널 섹션 펼침 | 초안 |
| `fixGuide` | boolean | false | 해결방안 패널 표시 | 초안 |
| `fixBack` | `{shape, step}` \| null | null | STEP 6에서 수정하러 온 위반 정보(복귀 배너) | 저장 제외(93~95행) |
| `fixField` | route 문자열 \| null | null | 강조할 필드(2.4초 후 자동 해제) | 저장 제외 |

읽기만 하는 외부 상태: `combo`(`[{n, k, src, w}]`), `comboMeta`(`{title, desc, done, at, ai}`), `upList`(업로드 파일 `[{name, …}]`, 확장자 판정용), `pubMode`·`simMode`(정본 ID·publisher 시뮬레이션), `v7State`·`v6Stale`·`convertState`·`svResults`·`v8State`(무효화 대상), `actLog`·`actSeq`, `toast`·`toastText`·`toastId`, `notify`, `saveTime`, `savedHere`.

---

## 6. 시뮬레이션 vs 실제 계산

### 6.1 실제로 계산·동작하는 것

| 항목 | 근거 |
|---|---|
| publisher·mediaType 덮어쓰기와 승인 플래그, 승인분만 정본에 병합 | 143~147, 2860~2903행 |
| 정본 생성과 readiness(`ai-ready`/`draft`) 판정, 초안 ID 해시 민팅 | 150~185행 |
| Turtle 미리보기의 주어 ID, publisher·distribution 블록 유무, mediaType IRI, Activity ID가 정본에 연동 | 2896~2901행 |
| 승인 시 활동 로그 기록과 STEP 6·7·8 결과 무효화 | 2884~2885, 344~356행 |
| 데이터셋별 완료 추적과 순회, 미완료 데이터셋으로 되돌아가기, STEP 3 완료 판정 | 2965~2983, 334행 |
| 유형 필터, 선택/해제 토글, 선택 칩과 카운트, 관계 맵 하단 3열 | 1736~1939행 |
| 조합 이름 기반 프로버넌스 체인 문자열과 타 부처 경고(이름 정규식) | 1963~1967행 |
| localStorage 초안 자동 저장·복원 | 62~102행 |

### 6.2 목업이 흉내만 내는 것

| 항목 | 실제 동작 |
|---|---|
| "AI 추천" 전부 (`★ AI 추천: dcat:Dataset … (신뢰도 95%)`, ★ 추천 배지, 근거 문구, 연쇄 추천, 리니지 공백 후보 3건) | 고정 문자열. 데이터셋과 무관하게 항상 같은 내용(TRAFFIC_LINK_5MIN, etas_inspect_log 등 다른 데모 세트 기준) |
| 유형 불일치 판정 `현재 조합(정형 Parquet 배치)` | 항목 유형이 `실시간 스트림`인지로만 판정. 현재 데이터셋의 실제 유형을 보지 않음 |
| 비추천 선택 사유 | 셀렉트 값이 저장되지 않음. "필수"라고 쓰여 있으나 검사 없음 |
| `연쇄 항목 모두 추가` | 토스트만 표시 |
| 클래스·프러퍼티 조회 입력, `전체 42종 보기 →`, 프로버넌스 `조회` | 핸들러 없음. "42종"이지만 데이터는 10건 |
| `prov:Activity ACT-K-04xx 기록됨` 토스트 | 난수 ID. 로그에 남지 않음. 탭 이동·선택·확정 모두 동일 |
| 필수/권장/선택 항목 폼의 값(`2.4.1`, `SER-0004 교통소통 시리즈`, `5분` 등), 시간 규격 카드 | 고정값 비제어 입력. 저장·검증·직렬화에 쓰이지 않음 |
| `확인` 체크박스, ② 클래스 칩 전환 | 동작 없음 |
| `+ 배포본 추가` | 고정 블록 표시 토글. 배포본이 실제로 추가되지 않음(정본은 배포본 1건 고정) |
| Turtle 미리보기의 `dcat:version "1.0.0"`, `owl:versionInfo "1.0.0"`, `dcat:accessURL`, 클래스 스텁 | 고정 문자열. 정본 트리플에는 없음 |
| `SHACL 검증 결과` 2줄 | 고정. 실제 검증은 STEP 6의 `validateDs`에서만 수행 |
| 해결방안 패널(DST-000712) | 고정 시나리오 문구 |
| 생애주기 타임라인, Agent, 파라미터 | 고정 데이터 7세트 |
| `최신성`(2026-08-21), `데이터 유형 구성`(정형 100%), `국토교통부 계열 ✓` | 고정 |
| 관계 맵 SVG | 고정 그래프. 선택 결과가 그래프에 반영되지 않음. 중심 리소스 표기 `DST-000123 교통링크 5분 소통정보` 고정 |
| 단계 인계 알림(시스템 알림·기관 메일) | 팝업만 표시 |
| 타이머 | 토스트 2.2~3초, 알림 5초, 필드 강조 2.4초, 초안 저장 디바운스 0.4초 |

### 6.3 재구현 시 바로잡아야 할 목업의 불일치

1. **스트림 판정이 두 가지**: ARD 카드는 `META_TABLE.kind`(2872행), 시간 규격 카드는 이름 정규식(1947행). 예: `cctv.vehicle.det.v1` 은 정본상 스트림이지만 시간 규격 카드가 뜨지 않고, `sample_실시간기상관측자료수집시스템_기상청_` 은 파일형인데 시간 규격 카드가 뜬다.
2. **스트림 속성을 편집할 수 없다**: `temporalResolution`·`eventTime` 은 META_TABLE에서만 오고 `metaOver`에 쓰는 입력이 없다. STEP 6의 `stream3` 위반은 이 화면에서 해소할 방법이 없다.
3. **"승인 전까지 미입력"이 기준값에는 적용되지 않는다**: META_TABLE에 값이 있는 데이터셋은 승인 없이도 `ai-ready`가 된다. 승인 플래그는 사용자가 고친 값에만 작동한다.
4. **입력 수정 시 무효화 누락**: 승인된 값을 고치면 `approved=false`가 되어 정본이 기준값으로 돌아가는데, 이때는 `invalidateDownstream`이 호출되지 않는다. STEP 6 결과가 낡은 채로 유효하게 남는다.
5. **mediaType이 두 곳에서 따로 계산된다**: 폼의 읽기 전용 필드는 업로드 확장자(Parquet 포함), 정본은 IANA 셀렉트. IANA 옵션에 Parquet이 없다.
6. **ID 체계 혼재**: 미리보기 주어는 정본 ID(`DST-draft-…`), 배포본은 폼용 ID(`DST-신규-pq` 등). 스텁은 `DST-000123` 고정.
7. **미리보기 라벨 불일치**: `rdfs:label` 은 승인 전 입력값(`ardPub`)을 쓰고 IRI는 승인된 정본 값을 쓴다. 스트림도 `a dcat:Dataset` 만 표시한다.
8. **선택이 데이터셋에 귀속되지 않는다**: 화면 문구와 달리 `clsSel` 등은 전역 1벌이라 칩으로 데이터셋을 바꿔도 그대로 따라오고, 확정하면 저장 없이 사라진다.
9. **`ds3Done` 이 인덱스 키**: 조합에서 항목을 추가·삭제하면 완료 표시가 다른 데이터셋으로 밀린다. 개수만 맞으면 STEP 3이 완료로 판정된다.
10. **`metaOver` 가 프로세스 스냅숏에 빠져 있다**: 프로세스를 새로 만들거나 불러와도 이전 덮어쓰기가 이름 기준으로 남는다.
11. **기관 IRI를 라벨 해시로 만든다**: 같은 기관을 다르게 표기하면 서로 다른 IRI가 생긴다.
12. **확정에 필수 검사가 없다**: 결측 상태로 STEP 4까지 진행된다.
13. **STEP 2 인계 문구 불일치**: "② 프러퍼티 폼 초안 … 에 반영됨"이라고 쓰여 있으나 `dcterms:title` 필드는 데이터셋 이름을 쓰고 `cmTitle`/`cmDesc` 는 폼 어디에도 들어가지 않는다.
14. **타 부처 판정 불일치**: 우측 패널은 경찰청을 포함하지만 관계 맵의 `ds3Agent` 는 경찰청을 포함하지 않는다. 둘 다 이름 정규식이며 `publisher` 값과 무관하다.

---

## 7. 실제 제품에서 필요한 기능

### 7.1 백엔드 기능 (FastAPI + PostgreSQL + rdflib/pySHACL)

1. **데이터셋 단위 카탈로그 초안 관리**: 프로세스(작업 조합) 안의 데이터셋마다 메타데이터 초안을 저장한다. 키는 인덱스나 이름이 아닌 데이터셋 UUID.
2. **필드 단위 제안·승인 워크플로**: 각 필드 값에 출처(`profiler` 자동추출 / `sllm` 제안 / `manual` 수기)와 상태(`proposed` / `approved`)를 둔다. 정본은 `approved` 값만으로 조립한다. 기준값(자동추출분)도 동일하게 승인 대상인지 정책으로 결정한다(6.3절 3번).
3. **정본 빌더와 readiness 산정**: `buildCanonical`(164~185행) 규칙을 서버로 옮긴다. 파일형 필수 = title·publisher·distribution(mediaType), 스트림형 필수 = title·publisher + temporalResolution·eventTimeColumn.
4. **rdflib 직렬화 미리보기**: 저장된 초안(승인분)을 실제 그래프로 만들어 Turtle을 반환한다. 미리보기와 STEP 7 산출물이 같은 그래프 빌더를 쓴다.
5. **pySHACL 즉시 검증**: 우측 패널의 "SHACL 검증 결과"를 실제 shape 세트로 계산하고, 위반마다 `focusNode`·`resultPath`·심각도와 폼 필드 경로를 반환해 "폼 필드로 이동"을 구현한다. 최소 shape: PublisherShape(sh:nodeKind sh:IRI), MediaTypePlacementShape(mediaType은 Distribution에, IANA IRI), StreamServiceShape(temporalResolution은 xsd:duration, eventTime 필수), accrualPeriodicity 표준 어휘 검사(Warning).
6. **통제 어휘 서비스**: 클래스·프러퍼티·PROV 용어 카탈로그(4.2·4.6절 시드, 데이터 유형 태그·도메인/레인지·DCAT 버전 포함), IANA 미디어타입, 기관(Agent) 레지스트리, 갱신주기 어휘, 타임존. 검색과 유형 필터 제공.
7. **기관 레지스트리**: publisher는 자유 텍스트가 아닌 기관 선택(자동완성)으로 받고 IRI는 레지스트리의 기관 코드로 만든다. 신규 기관 등록 절차와 "타 부처·협약 필요" 속성을 기관 데이터로 관리한다.
8. **추천 엔진**: 데이터셋 프로파일(형식·스키마·스트림 여부)에 근거한 클래스·프러퍼티 추천, 근거 문구, 연쇄 추천(클래스 선택 시 필요한 프러퍼티·PROV 관계), 유형 불일치 경고. sLLM 연동 시 제안과 신뢰도를 저장하되 승인 전에는 정본에 넣지 않는다.
9. **추가 클래스 타이핑 규칙**: 4.8절의 규칙(병기형 / 배포본 병기 / 별도 리소스 + 관계)을 클래스 카탈로그의 속성으로 정의하고 그래프 빌더가 따른다.
10. **프로버넌스 저장소와 공백 탐지**: Activity·Agent·Entity와 관계(used, generated, wasAssociatedWith, wasAttributedTo, wasInformedBy, qualifiedDerivation 등)를 저장한다. 생애주기 7단계별 조회, 리니지 공백 탐지(단계 사이 Activity 누락, 책임 Agent 미연결), 기존 Activity·Agent 검색 후 연결 기능.
11. **감사 로그(prov:Activity 민팅)**: 선택·승인·확정·연결 행위마다 실제 Activity 레코드를 발급하고(순차 ID, 난수 금지) 수행자·시각·변경 전후 값을 남긴다.
12. **하류 무효화**: 정본에 영향을 주는 변경(승인, 승인 해제, 승인값 수정, 배포본 추가·삭제)이 생기면 해당 프로세스의 검증 결과를 `stale`로 표시하고 직렬화·진단 산출물을 폐기한다. 정본 체크섬 비교로 실제 변경 여부를 판정하면 불필요한 무효화를 줄일 수 있다.
13. **데이터셋 확정과 단계 게이트**: 확정 시 서버에서 필수 필드 검사를 수행한다(차단 또는 경고 정책 선택). 프로세스의 모든 데이터셋이 확정되면 STEP 3 완료. 확정 취소(재편집) 처리와 다음 단계 담당 조직 알림 발송.
14. **식별자 민팅**: 초안 ID와 발행 ID 분리, 데이터셋(DST)·서비스(SVC)·배포본(DIST)·Activity(ACT)·시리즈(SER)별 시퀀스. 발행 모드에서는 임시 ID 대체 발급을 금지한다.
15. **STEP 6 왕복 복귀 지원**: 위반 → 원인 필드 딥링크(`dataset_id`, `field_path`)와 수정 후 재검증 흐름.

### 7.2 API 엔드포인트(안)

| 메서드·경로 | 용도 |
|---|---|
| `GET /api/processes/{pid}/datasets` | 작업 대상 목록, 데이터셋별 STEP 3 상태(대기/작성 중/완료), readiness |
| `GET /api/datasets/{id}/catalog` | 데이터셋 메타 초안 전체(필드 값·출처·승인 상태, 배포본, 서비스 속성, 추가 클래스·프러퍼티·PROV 링크) |
| `PATCH /api/datasets/{id}/catalog/fields` | 필드 값 저장(상태 `proposed` 로 전환) |
| `POST /api/datasets/{id}/catalog/approve` | 지정 필드 승인(정본 반영). 응답에 readiness, 무효화된 하류 결과 포함 |
| `POST /api/datasets/{id}/distributions` · `PATCH/DELETE /api/distributions/{did}` | 배포본 추가·수정·삭제 |
| `PUT /api/datasets/{id}/service` | 스트림(DataService) 속성 저장 |
| `PUT /api/datasets/{id}/classes` | 주 클래스·추가 클래스 선택(비추천 선택 사유 포함) |
| `POST/DELETE /api/datasets/{id}/properties` | 추가 프러퍼티와 값 |
| `GET /api/vocab/classes?type=&q=` · `/vocab/properties` · `/vocab/prov-terms` | 어휘 조회(유형 필터·검색) |
| `GET /api/vocab/media-types` · `GET /api/organizations?q=` · `POST /api/organizations` | IANA 목록, 기관 검색·등록 |
| `GET /api/datasets/{id}/recommendations` | 클래스·프러퍼티·PROV 추천, 근거, 연쇄 추천, 유형 불일치 경고 |
| `GET /api/datasets/{id}/provenance/lifecycle` | 7단계 Activity·Agent·파라미터 |
| `GET /api/provenance/search?q=` | Activity·Agent·Entity 검색 |
| `GET /api/datasets/{id}/provenance/gaps` | 리니지 공백 후보 |
| `POST/DELETE /api/datasets/{id}/provenance/links` | 공백 후보 연결, 추가 PROV 관계 기록 |
| `GET /api/datasets/{id}/preview.ttl` | rdflib 직렬화 미리보기 |
| `POST /api/datasets/{id}/validate` | pySHACL 즉시 검증(위반 목록 + 필드 경로) |
| `GET /api/datasets/{id}/graph` | 관계 맵용 노드·엣지 JSON |
| `GET /api/processes/{pid}/provenance-check` | 프로버넌스 정합 점검(최신성, 생산 조직·협약 필요 여부, 유형 구성) |
| `POST /api/datasets/{id}/catalog/confirm` · `DELETE …/confirm` | 데이터셋 확정·확정 취소(Activity 발급, 필수 검사) |
| `GET /api/processes/{pid}/gates` | 단계 게이트 상태(진입 가능 여부·사유·완료 여부) |
| `GET /api/processes/{pid}/activities` | 활동 로그 |

### 7.3 데이터 모델(안)

**dataset** (dcat:Dataset)

| 컬럼 | 대응 프러퍼티 | 비고 |
|---|---|---|
| `id` (uuid), `process_id` | | |
| `identifier` | `dcterms:identifier` | 초안 ID / 발행 ID 분리 보관 |
| `kind` | (`rdf:type`) | `dataset` / `stream` |
| `title`, `description` | `dcterms:title`, `dcterms:description` | 언어 태그 `ko` |
| `publisher_org_id` → organization | `dcterms:publisher` | |
| `format_label` | `dcterms:format` | 예: 정형(엑셀) |
| `in_series_id` → dataset_series | `dcat:inSeries` | DCAT 3.0 |
| `version`, `version_info` | `dcat:version`, `owl:versionInfo` | 병기 정책 |
| `accrual_periodicity` | `dcterms:accrualPeriodicity` | 통제 어휘 IRI 또는 ISO 8601 |
| `role_note` | (문장화용) | |
| `readiness_level`, `canonical_checksum` | | 계산값 캐시 |
| `step3_status`, `confirmed_at`, `confirmed_by`, `confirm_activity_id` | | 대기/작성 중/완료 |

**dataset_field_value** (제안·승인 추적, 선택 사항으로 dataset 컬럼과 병행)

| 컬럼 | 의미 |
|---|---|
| `dataset_id`, `field_path` | 예: `publisher`, `distribution[0].mediaType` |
| `value`, `source` | `profiler` / `sllm` / `manual` |
| `confidence` | sLLM 제안 신뢰도 |
| `status`, `approved_by`, `approved_at`, `activity_id` | `proposed` / `approved` |

**distribution** (dcat:Distribution): `id`, `dataset_id`, `identifier`, `media_type`(IANA, FK), `access_url`(`dcat:accessURL`), `byte_size`(`dcat:byteSize`), `checksum_algo`·`checksum_value`(`spdx:checksum`), `compress_format`(`dcat:compressFormat`), `conforms_to`(`dcterms:conformsTo`), `status`.

**data_service** (dcat:DataService, 스트림): `dataset_id`, `endpoint_url`, `endpoint_description`(`dcat:endpointDescription`), `temporal_resolution`(`dcat:temporalResolution`, xsd:duration), `event_time_column`(`fde:eventTimeColumn`), `timezone`, `watermark_delay`(xsd:duration), `late_policy`(`별도 적재 (late 파티션)` / `폐기` / `보정 재계산`), `alignment_plan_id`(예: PLN-ALN-002 v2.1).

**organization** (foaf:Agent / prov:Organization): `id`, `code`(예: 1613000), `iri`, `label_ko`, `ministry_family`(국토교통부 계열 여부), `agreement_required`.

**dataset_series** (dcat:DatasetSeries): `id`, `identifier`(SER-…), `title`.

**어휘 테이블**: `vocab_class`(`curie`, `description`, `data_type_tag`, `is_main`, `dcat_version`, `typing_rule`, `stub_template`), `vocab_property`(`curie`, `description`, `data_type_tag`, `domain_class`, `range`, `level` 필수/권장/선택, `dcat_version`), `vocab_prov_term`(`curie`, `description`, `data_type_tag`), `vocab_chain`(클래스 → 연쇄 추천 항목), `media_type`(`iana_name`, `ext`, `iri`).

**선택·확장 값**: `dataset_class`(`dataset_id`, `class_curie`, `mismatch_reason`, `activity_id`), `dataset_property_value`(`dataset_id`, `target` dataset/distribution/service, `property_curie`, `value`, `status`), `dataset_prov_link`(`dataset_id`, `relation_curie`, `target_type`, `target_id`, `lifecycle_stage`, `source` auto/recommended/manual).

**프로버넌스**: `prov_activity`(`id`, `identifier` ACT-…, `lifecycle_stage` 0~6, `started_at`, `ended_at`, `record_mode` 자동/자동+수기, `params` JSONB), `prov_agent`(`id`, `identifier`, `name`, `type` Person/Organization/SoftwareAgent, `org_id`), `prov_association`(`activity_id`, `agent_id`, `role`), `prov_usage`·`prov_generation`(Activity ↔ Entity), `prov_entity`(데이터셋·배포본·문서·계획서 등 참조).

**운영 테이블**: `activity_log`(사용자 행위 감사: who, when, action, target, before/after, activity_id), `validation_run`(`process_id`, `status`, `stale`, 결과 JSON), `notification`(단계 인계 알림).

### 7.4 프론트엔드(React) 구현 메모

- 상태 단위: 서버 상태는 데이터셋별 초안 쿼리, 로컬 상태는 탭·필터·패널 접힘 정도로 한정한다. 데이터셋을 바꾸면 해당 데이터셋의 선택이 서버에서 다시 로드되어야 한다.
- 폼은 클래스(도메인)별 섹션으로 구성하고 필드 정의(라벨, 수준, 입력 형태, 어휘)는 `vocab_property` 에서 내려받아 렌더링한다. 4.1절 표가 초기 필드 정의 시드이다.
- 승인 버튼은 필드 묶음 단위로 두되 변경 감지 시 "미승인 변경 있음" 상태를 분명히 보여 준다.
- 우측 패널의 Turtle·SHACL 결과는 저장 후 서버 응답으로 갱신한다(디바운스).
- 관계 맵은 `/graph` 응답을 그리는 동적 그래프로 대체한다.
