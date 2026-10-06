# STEP 6 검증: 게이트 0 + SHACL 기능 명세

대상 목업: FDE Data Studio (`src/markup.html`, `src/logic.js`)
작성 기준: 목업 코드를 데이터로 분석한 역설계 결과. 식별자, 코드, 화면 문구는 원문 그대로 인용한다.

---

## 0. 범위와 선행 주의 사항 (반드시 먼저 읽을 것)

### 0.1 마크업 주석 번호와 화면 번호가 서로 뒤바뀌어 있다

목업은 v8.1에서 6단계와 7단계의 순서를 맞바꿨고(검증이 직렬화보다 먼저), 템플릿 블록은 그대로 둔 채 표시 조건만 교체했다.

| 마크업 블록 | 주석 | 표시 조건 바인딩 | 실제 표시 조건 (logic.js 1407~1409) | 화면 제목 (원문) |
|---|---|---|---|---|
| 1670~1917 | `<!-- STEP 6 -->` | `show6` | `s.plane === 'studio' && s.step === 7` | `STEP 7: 직렬화 · 발행 포맷 변환 + 파생 자가검증` |
| 1919~2277 | `<!-- STEP 7 -->` | `show7` | `s.plane === 'studio' && s.step === 6` | `STEP 6: 검증: 게이트 0 + SHACL` |

logic.js 1407 주석 원문: `// [v8.1-0] 재편 매핑 — show6 게이트의 템플릿 블록(직렬화)은 STEP 7에, show7 블록(검증)은 STEP 6에 표시`

따라서 지시받은 라인 범위(1670~1918)는 실제로는 **직렬화 화면(STEP 7)** 이고, 지시받은 기능 설명(검증, 게이트 0, SHACL, `v7State`, `v6Results`, `simMode`, `fixBack`)은 **마크업 1919~2277** 에 있다.

이 문서의 처리 방침:

- 본문 1~8장: 기능 설명에 해당하는 **검증 화면** (`step === 6`, 마크업 1919~2277 + 전역 복귀 배너 145~149).
- 부록 A: 지시받은 라인 범위 **1670~1917** (화면상 STEP 7 직렬화). `pubMode` 토글과 검증 요약 배너가 이 범위에 있어 검증과 직접 연결된다.
- 부록 B: 목업 결함과 불일치 목록.

### 0.2 상태 변수 이름도 과거 번호 체계를 따른다

`v7State`, `v7Time`, `v7Run`, `v7Rows`, `v7Pass`, `v7Warn`, `v7Joints`는 모두 **현재 STEP 6 검증**의 변수다 (logic.js 328 주석: `v7State = 검증 상태 변수 (재편 후 STEP 6)`). `v6Results`, `v6Stale`, `v6Rows`는 재편 이후 추가된 신규 변수로 역시 검증용이다. 실제 제품에서는 `validation*` 계열로 이름을 통일할 것을 권한다.

### 0.3 저장 스냅숏 마이그레이션

`localStorage['fde-studio-draft']` 복원 시 `stepVer`가 없으면 `step` 6과 7을 서로 바꾸고 `stepVer = 2`를 부여한다 (logic.js 71~78, 데모 복구 경로 1000). `simMode`는 복원 시 항상 `null`로 지운다 (79, 1001).

---

## 1. 화면 목적

1. STEP 2에서 확정한 조합(`combo`)의 각 데이터셋에 대해 **정본(canonical)** 을 만들고, **게이트 0(의미·형상) + SHACL** 판정을 **데이터셋 단위 pass/fail** 로 내린다.
2. 판정 전용 화면이다. 수정은 원인 단계(STEP 2~5)에서만 하고, 위반 행의 `[수정하러 이동]` 버튼으로 해당 단계, 해당 필드로 이동했다가 돌아오는 **왕복 루프**를 제공한다.
3. 검증을 통과한 데이터셋이 1건 이상 있어야 STEP 7(직렬화)이 열린다. 미통과 데이터셋은 직렬화 대상에서 제외된다.
4. 상류 데이터(조합, STEP 3 승인 입력)가 바뀌면 검증 결과를 자동 무효화하고 `재검증 필요` 상태로 만든다.
5. 부가 패널: 4단계 파이프라인(① 자동추출 → ② 담당자 검수 + sLLM 보정 → ③ SHACL 검증 → ④ 발행) 현황, 접합부 계약 점검, N2SF 등급-구역 검사, 배치 일괄 재검증. 이들은 대부분 고정 데모 수치다.

화면 헤더 원문: `STEP 6: 검증: 게이트 0 + SHACL` / 배지 `업무 A — 독립 검증 업무` / 부제 `"검증기가 곧 계약" — 파일은 아직 존재하지 않음 · 판정 전용`

---

## 2. 화면 구성 (위에서 아래 순서)

### 2.0 전역 복귀 배너 (마크업 145~149, 모든 평면과 단계의 본문 최상단)

- 표시 조건: `fixBackOn` (`!!s.fixBack`)
- 문구: `⚠ STEP 6 위반 수정 중 — {{ fixBackShape }} · 보강 후 검증으로 복귀하세요 (수정 시 검증 결과 자동 무효화)`
- 버튼: `검증으로 복귀 ↩` (`fixBackGo`)

### 2.1 헤더 줄 (1922)

제목, 배지, 부제 (1장 참조).

### 2.2 시뮬레이션 및 상태 배지 줄 (1923~1937)

| 요소 | 표시 문구 (원문) | 바인딩 |
|---|---|---|
| 라벨 + 셀렉트 | `검수 시뮬레이션` | `simVal` / `simSet` |
| 옵션 | `끔` (value `off`), `MINT 미등록 재현` (value `nomint`), `publisher 결측 재현` (value `noorg`) | |
| 배지 (조건 `simOn`) | `⚠ 검수 시뮬레이션 중 — 산출물은 검수용 (_SIM 접미)` | |
| 배지 (조건 `v6StaleOn`) | `↺ 재검증 필요 — 정본이 변경되어 이전 결과가 무효화되었습니다` | |

### 2.3 리니지 미결 모달 (1938~1950, 조건 `linAskOn`)

- 제목: `⚠ 리니지 미결 상태입니다`
- 본문: `STEP 5 매핑이 "계산 대기"로 방치되어 있습니다 — 이대로 진행하면 prov 그래프가 불완전합니다. 진행하려면 사유를 입력하세요 (actLog 기록 · 은폐 불가).`
- 텍스트 영역 (2행) placeholder: `그래도 진행하는 사유 — 예: 단일 소스 시범 검증, 리니지는 2차에 보강` (`linReason` / `linReasonSet`)
- 버튼: `돌아가기 (STEP 5)` (`linBack`), `그래도 진행 (사유 기록)` (`linGo`, 사유가 비면 회색 `cursor:not-allowed`)

### 2.4 검증 대상 프로세스 호출 바 (1951~1957)

- 라벨: `검증 대상 프로세스 호출:`
- 버튼 목록 `taskProcOpts`: 저장된 프로세스 이름들. 현재 작업이 미저장이면 `{현재이름} (진행 중)` 항목이 추가된다. 선택된 항목은 `✓ ` 접두와 어두운 배경.
- 안내: `— 클릭으로 복수 선택 가능 · 선택한 프로세스들의 산출물 합집합이 업무(A) 검증 대상이 됩니다 · 다른 프로세스에 영향 없음`

### 2.5 실행 상태 바 (1958~1962)

| 요소 | 값 |
|---|---|
| 상태 배지 `v7StateLabel` | `대기 — 검증 미실행` (회색) / `⟳ 검증 실행 중…` (파랑) / `✓ 검증 완료 — {procName 또는 '현재 프로세스'}` (녹색) |
| 안내 | `프로세스를 호출한 뒤 [검증 실행]을 눌러야 게이트 0 → SHACL 검증이 시작됩니다 — 실행마다 prov:Activity 기록` |
| 버튼 `v7RunLabel` | `▶ 검증 실행 ({combo.length}건)` / `⟳ 실행 중…` / `↺ 재검증 실행` |

### 2.6 대기 안내 상자 (1963~1965, 조건 `v7Idle`)

`검증 대기 중 — {{ g1ProcName }} 조합 {{ comboCount }}건이 대상입니다. [▶ 검증 실행]을 누르면 내부 트리플(buildTriples)에 대해 게이트 0(의미·형상) → SHACL 순으로 판정합니다 — 파일은 아직 존재하지 않으므로 유출이 불가능합니다.`

### 2.7 이하 전부는 `v7Done` (`v7State === 'done'`) 일 때만 표시 (1966~2275)

#### 2.7.1 흐름 안내 (1967)

`흐름: 카탈로그(3) → 검증: 게이트 0 + SHACL (6) → 직렬화 + 파생 자가검증 (7) → 승인 → 발행(8) — 검증 미통과 데이터셋은 직렬화 대상에 포함되지 않습니다.`

#### 2.7.2 데이터셋 단위 판정 결과 패널 (1968~1997, 조건 `v6HasResults`)

- 제목: `데이터셋 단위 판정 결과` / 부제 `— 검증 대상 = buildTriples 출력 (산출물과 동일 원료)`
- 집계: `통과 {{ v6PassN }}건` · `미통과 {{ v6FailN }}건`
- 데이터셋 카드 (`v6Rows` 반복):
  - 데이터셋 이름 `vr.n`
  - 상태 배지 `vr.stLabel`: `통과` (녹색) / `FAIL` (적색 배경 흰 글자)
  - 위반과 경고가 모두 없을 때 (`vr.clean`): `✓ 게이트 0(의미·형상) + SHACL 전 항목 통과 — STEP 7 변환 대상`
  - 위반·경고 행 (`vr.items` 반복): 왼쪽에 `vi.shape` (규칙 이름), 오른쪽에 버튼 `vi.routeLabel` = `수정하러 이동 → STEP {n} ({label})`. 라우팅이 없으면 `라우팅 미선언 — 브리프 위반`. 위반 행은 붉은 테두리 (`#e3b3ab` / `#fdf1ef`), 경고 행은 주황 테두리 (`#f0cf9e` / `#fdf9f2`).
- 하단 안내 (원문): `ⓘ 이 화면은 판정 전용입니다 — 모든 수정은 해당 데이터의 원천 단계(STEP 1~5)에서 이뤄지고, 수정 시 이 검증 결과는 자동 무효화됩니다. 등재 셰이프: PublisherShape (sh:nodeKind sh:IRI) · MediaTypePlacementShape (Distribution 전용) · NoEmptyLiteralShape (sh:minLength 1) · NoDanglingRefShape (참조 IRI 타입 선언 필수)`

#### 2.7.3 게이트 0 패널 (1998~2015)

- 제목: `게이트 0 — 의미·형상 검사` / 배지 `트리플 기반 · SHACL 이전 1차 관문`
- 우측 요약 배지 `gate0Summary`: `게이트 0(의미·형상) 통과 — SHACL 진행 가능` / `게이트 0 ④ 실패 — 민팅 미등록`
- 설명: `SHACL은 파싱된 그래프를 전제로 하는 형상 검증 — 구문 실패와 형상 실패는 원인·담당자가 다르므로 분리 계측합니다. 일반 데이터셋과 파생 이벤트 데이터셋(개방 산출) 모두 동일 게이트 통과 — StreamServiceShape 검증 이전에도 구문 게이트 선행.`
- 표 컬럼: `검사` | `결과` | `상세`
- 표 행:

| 검사 (원문) | 결과 | 상세 (원문) |
|---|---|---|
| `① 파서 통과` + 태그 `이동` | 고정 배지 `STEP 7` | `직렬화 텍스트의 속성 — STEP 7 파생 자가검증에서 변환 직후 자동 검사` |
| `② prefix 완결` + 태그 `이동` | 고정 배지 `STEP 7` | `직렬화 텍스트의 속성 — STEP 7 파생 자가검증에서 자동 검사` |
| `③ 인코딩 UTF-8` + 태그 `이동` | 고정 배지 `STEP 7` | `직렬화 텍스트의 속성 — STEP 7 파생 자가검증에서 자동 검사` |
| `④ ID 잔존 검사 — 패턴 (-신규\|-draft-)` | `gate4Label`: `통과` / `실패` | `gate4Msg` (3.6 참조) |
| `⑤ 정체성 일치 (요청 대상 ↔ 산출물 제목)` | `gate5Label`: `통과` / `실패` | `gate5Msg` (3.6 참조) |

- 하단 안내: `✓ 검수 흐름: prefix 하나를 빼면 게이트 0 ②에서 잡히고 SHACL까지 가지 않음 — 게이트 0(회색·파랑)과 SHACL(기존 색)은 시각 구분`

#### 2.7.4 4단계 파이프라인 카드 (2016~2096)

탭형 상자 4개 (클릭 시 `pipe` 전환, 기본값 3):

1. `① 자동추출`
2. `② 담당자 검수 + sLLM 보정`
3. `③ SHACL 검증`
4. `④ 발행` + 부제 `Turtle 정본 → LPG 투영·문장화 코퍼스`

선택된 탭의 상세 상자 (4칸 그리드):

| 탭 | 제목 | 4칸 내용 (원문) |
|---|---|---|
| ① | `① 자동추출 상세` | `프로파일 대상` `1,894 데이터셋` / `자동추출 필드` `14,208개 (커버리지 71%)` / `푸터 판독` `Parquet 812건 · 수 KB/건` / `기록 Activity` `ACT-K-0301~0388` |
| ② | `② 담당자 검수 + sLLM 보정 상세` + `— 담당자(검수자)가 승인하고, sLLM은 초안만 제안` | `검수 큐 처리` `37건 완료 · 12건 대기` / `sLLM 보정 제안` `61건 (초안)` / `담당자 승인 / 반려` `49 승인` · `12 반려` / `담당 검수자` `검수팀 2인 배정` |
| ③ | `③ SHACL 검증 상세` | `Shape 세트` `DatasetShape 외 4종 · rs-2.1` / `검증 대상` `Turtle 정본 {{ comboCount }}건 ({{ g1ProcName }})` / `최근 실행` `방금 · 소요 4초` / `결과` `통과 {{ v7Pass }}` · `W {{ v7Warn }}` · `V {{ violCount }}` |
| ④ | `④ 발행 상세` | `정본 저장` `트리플스토어 (Fuseki/GraphDB)` / `LPG 투영` `Neo4j · 노드 18종` / `문장화 코퍼스` `마트 벡터DB①·② 적재` / `개방 투영` `필터링 후 단방향 push ◀` |

④ 탭 상세 상자 안의 전송 채널 영역:

- 제목 `검증 완료 후 전송 — API · MCP 채널` + 상태 배지 `sendStateLabel`: `발행 승인됨 · 전송 가능` / `발행 승인 대기 (Violation {viol}건)`
- 카드 3개:
  - `카탈로그 API (JSON-LD)` / `POST /catalog/v3/datasets` / `시스템 간 연계 · @context 외부 참조 · 인증: 기관 API 키` / 배지 `연결됨` / 버튼 `전송`
  - `MCP 서버 노출` / `mcp://catalog.molit.go.kr` / `AI 에이전트용 도구: search_datasets · get_lineage · get_turtle` / 배지 `연결됨` / 버튼 `갱신 알림`
  - `공공데이터포털 push` / `data.go.kr · 개방구역 투영본 ◀` / `필터링 투영본만 단방향 push · 🔒 샘플 레코드 제외` / 배지 `승인 대기` / 버튼 `push`
- 안내: `ⓘ 전송은 발행 승인(Violation 0건) 이후에만 활성화됩니다. 모든 전송은 prov:Activity로 계측되어 채널별 전송 이력이 남습니다.`

카드 하단 띠: `프로버넌스 기록기 — 모든 단계가 prov:Activity 생성 · 사후 작성이 아니라 실행 시점 계측`

#### 2.7.5 탭 ① 본문 (2097~2113)

- KPI 3칸: `자동추출 완료` `{{ p1Ok }}` (`{{ g1ProcName }} 조합 기준`) / `부분 추출 (프리필 검수 필요)` `{{ p1Part }}` / `추출 실패 (수기 입력)` `{{ p1Fail }}`
- 표 컬럼: `대상 리소스` | `추출 항목` | `신뢰도` | `상태` | (링크) `프리필 확인` → `goStep3`

#### 2.7.6 탭 ② 본문 (2114~2131)

- KPI 3칸: `담당자 승인` `{{ p2Ok }}` / `반려` `0` / `검토 대기 (초안)` `{{ p2Wait }}`
- 표 컬럼: `대상 리소스` | `sLLM 보정 제안` | `상태` | `검수자` | (링크) `승인 / 반려` (핸들러 없음)
- 경고 상자: `⚠ sLLM 제안은 항상 초안 상태로 생성됩니다 — 담당자 승인 없이 정본에 반영되지 않으며, 승인·반려 모두 prov:Activity로 기록됩니다.`

#### 2.7.7 탭 ③ 본문 (2132~2170, 기본 표시)

- 칩 4개: `① SKOS 통제어휘 (66코드 준수) ✓` / `② DCAT/PROV-O 필수항목 ✓` / `③ 가이드라인 80항목 대조` (비활성 모양) / `④ 스트림 Shape 3종 (Service · Plan · 파생)` (보라)
- KPI 3칸: `통과` `{{ v7Pass }}` (`{{ g1ProcName }} 조합 기준`) / `Warning` `{{ v7Warn }}` (`검수 후 발행 가능`) / `Violation` `{{ violCount }}`
- 위반 표 컬럼: `대상 리소스` | `위반 Shape` | `심각도` | `위반 메시지` | (링크) `해당 폼으로 이동` → `goStep3`
- 빈 상태 행: `호출된 프로세스의 조합이 비어 있습니다 — 상단에서 프로세스를 호출하세요`
- 패널 `접합부 계약 점검 — 메타 평면 ↔ 데이터 평면 대조`: `v7Joints` 행 (파일명 / 상태 문구)
- 하단 바: 버튼 `위반 수정 후 재검증` (핸들러 없음) / 배지 `sLLM 보정 제안 — 초안 상태 · 관리자 승인 필수` / 안내 `Violation이 남은 데이터셋은 발행 보류로 분리됩니다 — 통과분은 ④ 발행 단계에서 즉시 승인 가능`

#### 2.7.8 탭 ④ 본문 (2171~2274)

- KPI 3칸: `발행 대상 (SHACL 통과)` `{{ v7Pass }}` / `발행 보류 (W·V 잔존)` `{{ v7Warn }}` (`Warning 검수 후 발행 가능`) / `전송 채널` `3`
- 패널 `N2SF 등급-구역 일치 검사` + 배지 `옵션` (조건 `n2sfOn`):
  - `O — Open {{ n2sfOCnt }}건` / `✓ 개방구역 push 가능`
  - `S — Sensitive {{ n2sfSCnt }}건` / `△ 필터링 투영 조건부 — 샘플 레코드·프로파일 통계 제외 확인`
  - `C — Classified {{ n2sfCCnt }}건` / `✕ 통제구역 전용 (cctv — 차량번호 포함) — 개방 선택 시 자동 제외`
  - 안내: `ⓘ 등급-구역 일치는 SHACL Shape(N2SFZoneShape)로 검증되며, 등급 미지정 데이터셋은 보수적으로 S로 간주됩니다 — 등급 지정은 STEP 4 다중분류체계 →` (링크 `goStep4`)
- 발행 바: 라디오 `통제구역 (정본)` (기본 선택) / `개방구역 (필터링 투영본 ◀ push)` + `🔒` (title `개방 불가: 샘플 레코드·프로파일 통계`) / 버튼 `통과분 발행 승인 ({{ v7Pass }}건)` (핸들러 없음)
- 안내: `발행 게이트는 데이터셋 단위로 판정됩니다 — Violation이 있는 데이터셋({{ violCount }}건)만 개별 보류되고, SHACL 통과분 {{ v7Pass }}건({{ g1ProcName }})은 일괄 발행할 수 있습니다. 보류분은 위반 해소 후 재검증 시 다음 발행 배치에 합류합니다. 🔒 개방 불가 항목: 샘플 레코드 · 프로파일 통계 · 발행된 정본은 데이터 카탈로그에서 확인 →` (링크 `goCatalog`)
- 패널 `배치·자동 실행` + 배지 `소프트웨어 주체 — 대화형 런타임과 프로버넌스 레벨 분리` + 버튼 `일괄 재검증 실행` (`batchRun`)
  - 진행 상자 (조건 `batchOn`):
    - 제목 `ACT-B-0032 · 일괄 재검증 구동 중` + `prov:SoftwareAgent batch-revalidator v1.4 · actedOnBehalfOf 박관리`
    - 버튼 `일시정지` (핸들러 없음), `중단` (`batchClose`)
    - 진행률 막대 64% 고정 + `1,213 / 1,894건 (64%) · 남은 시간 약 3분 40초`
    - 5단계: `① 대상 적재` `완료 · 1,894건` / `② Shape 로드` `완료 · v1.2 · 6종 변경` / `③ SHACL 검증` `실행 중 · 1,213건` / `④ 결과 집계` `대기` / `⑤ Activity 기록` `대기`
    - `실시간 처리 로그` (5.6 참조), `중간 집계 (1,213건 처리)`: `통과` `1,168` / `Warning` `36` / `Violation` `9 (v1.2 신설 rai 항목 7)`
    - `완료 시 처리`: `Violation 대상은 검수 큐로 자동 집계 · 담당자 알림 발송 · 결과 리포트는 prov:Activity ACT-B-0032에 첨부`
  - 설명: `가이드라인 개정 등 일괄 재검증은 STEP 1~8 대화형 흐름과 분리된 배치 런타임으로 실행됩니다. 실행 주체는 prov:SoftwareAgent, 승인 관리자는 prov:actedOnBehalfOf로 연결되고 모든 호출이력은 prov:Activity로 기록되어 동일 SHACL 인프라로 검증됩니다(원칙 10 호출이력 요건).`
  - `실행 주체 모델링`: `prov:SoftwareAgent` `batch-revalidator v1.4` / `prov:actedOnBehalfOf` `박관리 (관리자 승인)` / `대상` `{{ g1ProcName }} 산출 {{ comboCount }}건 + 발행 정본 (누적)` / `트리거` `가이드라인 v1.1 → v1.2 개정 (Shape 6종 변경)`
  - `최근 배치 호출이력 (prov:Activity)`: `ACT-B-0031 · 일괄 재검증 {{ comboCount }}건 ({{ g1ProcName }})` `완료 · 통과 {{ v7Pass }}` / `ACT-B-0030 · SKOS 어휘 개정 반영` `완료` / `ACT-B-0029 · 야간 체크섬 대조` `예약 · 매일 03:00`
  - 하단 띠: `대화형 런타임 — 사람 주체 (prov:Person) · STEP 1~8 화면 조작` | `배치 런타임 — 소프트웨어 주체 (prov:SoftwareAgent) · 승인 관리자 actedOnBehalfOf 연결` | `오케스트레이션 MCP는 현 시점 제외 — 니즈 발생 시 이 섹션으로 수용`

### 2.8 화면 하단 공통 내비게이션 (마크업 3879, 3886)

`이전` (`prevStep`), `다음 (확정)` (`nextStep`). STEP 6에서는 `pipe` 1~4를 먼저 순회한다 (3.9 참조).

---

## 3. 사용자 동작 → 결과

### 3.1 검수 시뮬레이션 셀렉트 변경 (`simSet`, logic.js 2831~2834)

- `simMode = (value === 'off') ? null : value`
- `v7State === 'done'` 이면 동시에 `v6Stale = true` (다른 하류 상태 `convertState`, `svResults`, `v8State`는 건드리지 않는다. `invalidateDownstream` 경유가 아니다.)
- 토스트와 actLog 없음. `persistDraft` 호출 없음.
- 효과 (다음 `buildCanonical` / `mintId` 호출부터 즉시 반영):
  - `nomint`: `pubMode === true` 일 때만 작동. `combo[0]` 이름과 같은 항목의 `mintId`가 `null`을 반환한다 (logic.js 153~155). 초안 모드에서는 아무 효과가 없다.
  - `noorg`: 모드와 무관하게 `combo[0]` 항목의 `publisher`를 `null`로 만든다 (logic.js 168, 174).
- 시뮬레이션 중에는 STEP 7 산출 파일명에 `_SIM` 접미가 붙는다 (logic.js 2720, 2723).
- `simMode`는 스냅숏 저장 제외 (logic.js 95), 복원 시 `null` (79).

### 3.2 프로세스 호출 버튼 (`tp.pickA` = `toggle(p, 6)`, logic.js 1020~1055)

- 현재 선택 집합 `curSel` = `taskProcSel` (있으면) 또는 `procName.split(' + ')` 또는 `[curName]`.
- 클릭한 프로세스가 이미 선택돼 있으면 제거 (단 최소 1개는 남긴다), 아니면 추가.
- 현재 작업이 미저장이고 선택 집합에 포함되면 먼저 `saveCur()`로 스냅숏을 만든다.
- 결과 선택이 1개: `blank()` + 해당 프로세스 스냅숏 전체 복원, `procName`, `taskProcSel`, `plane: 'studio'`, `step: 6`, `v7State: null`, `v8State: null`. 토스트: `{업무명} — 「{name}」 프로세스 호출 · 해당 프로세스 산출물 기준으로 진행`
- 결과 선택이 2개 이상: `combo` = 선택 프로세스들의 `snapshot.combo` 합집합 (이름 `n` 기준 중복 제거, 선택 순서 유지), `procName = names.join(' + ')`, `taskProcSel`, `step: 6`, `v7State: null`, `v8State: null`. 토스트: `{업무명} — {names.join(' · ')} ({n}개 프로세스 결합 호출) · 산출물 합집합 {merged.length}건 기준 · 재실행 필요`
- `{업무명}` = `step === 7 ? '업무 A(검증)' : '업무 B(진단)'`. `pickA`가 6을 넘기므로 검증 화면에서 눌러도 `업무 B(진단)`으로 표시된다 (재편 잔재 버그, 부록 B-1).
- 토스트 지속 3000ms. actLog 기록 없음.
- `v6Results`, `v6Stale`, `convertState`(복수 선택 시)는 지우지 않는다 (부록 B-2).

### 3.3 `[▶ 검증 실행]` / `[↺ 재검증 실행]` (`v7Run`, logic.js 1656~1673)

1. `v7State === 'run'` 이면 무시.
2. **리니지 미결 경고 게이트**: `relPairs`가 비어 있고 `linWaived`가 아니고 `combo.length > 1` 이고 `linAsk`가 아니면 `linAsk = true` (모달 표시) 후 종료.
3. `v7State = 'run'`, `linAsk = false`, 토스트 `⟳ STEP 6 검증 실행 — 게이트 0(의미·형상) + SHACL · buildTriples 출력 기준 데이터셋 단위 판정`
4. 1400ms 타이머 후:
   - `rs = combo.map(c => validateDs(c))` (4장 규칙)
   - `passN = rs.filter(r => r.pass).length`
   - 상태: `v7State = 'done'`, `v6Stale = false`, `v6Results = rs`, `v7Time = nowHM()` ("HH:MM"), `fixBack = null`, `persistDraft()`
   - 토스트: `✓ STEP 6 검증 완료 — 통과 {passN}건 · 미통과 {rs.length - passN}건` + (`passN > 0` 이면 ` · STEP 7 직렬화 해제`, 아니면 ` — [수정하러 이동]으로 원인 단계에서 보강하세요`). 3200ms.
   - actLog (`who = '홍길동 (나)'`, `actId = 'ACT-K-' + 4자리 세션 시퀀스`, 0421부터):
     - 직전에 `fixBack`이 있었으면: `재검증 — 직전 위반 {fb.shape} 보강 (원인 단계 STEP {fb.step}) · 통과 {passN}/{rs.length}`
     - 아니면: `STEP 6 검증 실행 — {procName 또는 '현재 프로세스'} · 통과 {passN}/{rs.length}`
5. 재검증은 변경 여부와 무관하게 언제든 실행할 수 있다. `convertState`, `svResults`, `v8State`는 재검증으로 지워지지 않는다.

`validateDs` 결과 구조: `{ n, pass, fails: [{ shape, route }], warns: [{ shape, route }] }`. `pass = (fails.length === 0)`. 경고는 통과 여부에 영향이 없다.

### 3.4 리니지 미결 모달

- 사유 입력 (`linReasonSet`): `linReason = e.target.value`
- `돌아가기 (STEP 5)` (`linBack`): `linAsk = false` 후 `go({ plane: 'studio', step: 5 })`
- `그래도 진행 (사유 기록)` (`linGo`, logic.js 2840~2846):
  - `linReason.trim()`이 비면 무시.
  - actLog: `리니지 미결 상태로 검증 진행 — 사유: {reason}` (`who = '홍길동 (나)'`)
  - 상태: `linWaived = true`, `linAsk = false`, `linReason = ''`
  - 토스트: `사유 기록됨 (prov:Activity) — [검증 실행]을 다시 누르세요` (2800ms)
  - 검증은 자동 실행되지 않는다. 사용자가 다시 실행 버튼을 눌러야 한다.
- `linWaived`는 스냅숏에 저장되고 `stepGate(5).done`도 참으로 만든다 (logic.js 336).

### 3.5 결과 행의 `[수정하러 이동 → STEP n (label)]` (`goFix`, logic.js 2800~2806)

- `r = FIX_ROUTE[route]`. 없으면 무시 (버튼 문구는 `라우팅 미선언 — 브리프 위반`).
- `go({ plane: 'studio', step: r.step, ds3: dsIdx, ds: dsIdx, tab3: 2 (r.step === 3 일 때만), fixBack: { shape, step: r.step }, fixField: route })`
  - `dsIdx` = 해당 데이터셋의 `combo` 내 인덱스 (STEP 3과 STEP 4의 작업 대상 커서를 그 데이터셋으로 맞춘다).
  - `go()`는 중앙 단계 잠금 `stepGate`를 거친다. 잠긴 단계면 토스트 `🔒 STEP {n} 잠김 — {reason}` 후 이동하지 않는다 (logic.js 4~15).
- 2400ms 후 `fixField = null` (필드 강조 해제. 주석: `하이라이트 2초 페이드`).
- `fixBack`이 설정된 동안 전역 복귀 배너(2.0)가 모든 화면 상단에 뜬다. 다음 검증 완료 시 `fixBack = null`.
- 필드 강조 구현 범위 (logic.js 2893~2894): `fixField === 'publisher'` → STEP 3 publisher 입력(`ardPubHi`) 배경 `#fdf3e7`, 테두리 `#e8912d`. `fixField === 'mediaType'` 또는 `'stream3'` → STEP 3 mediaType 셀렉트(`ardMtHi`) 같은 강조. 그 외 route(`identity`, `mint`, `class4`, `lineage5`, `emptyLit`)는 강조 대상 요소가 없다. 스트림 데이터셋에는 mediaType 셀렉트가 표시되지 않으므로 `stream3` 강조는 화면에 보이지 않는다 (부록 B-6).

### 3.6 게이트 0 패널 값 (표시 전용 계산, logic.js 2727~2767)

**④ ID 잔존 검사** (2740~2754)

- `mintedAll = comboAll.every(c => !!mintId(c, 'DST'))` (`comboAll` = `combo` 또는 비었으면 `[{ n: 'dataset' }]`)
- `g4 = !published || mintedAll` (`published = pubMode === true`)
- `gate4Label`: `통과` / `실패`. 실패 시 행 배경 `#fdf1ef`.
- `gate4Msg`:
  - 발행 모드, 통과: `민팅 적용 — (-신규|-draft-) 잔존 0건 (실시간교통사고 = SVC-000043 · eTAS = DST-000962 · kma = SVC-000041)`
  - 발행 모드, 실패: `민팅 미등록 데이터셋 존재 — fallback 발급 금지 · 게이트 0 ④ FAIL (관리 탭 민팅 정책에서 등록 후 재검증)`
  - 초안 모드: `초안 ID(결정적 해시) 상태 — 데이터셋별 고유(KIND-draft-XXXXXX) · 발행 시 민팅 ID로 치환 · 발행 산출물에는 (-신규|-draft-) 잔존 불가`
- `gate0Summary`는 ④만 반영한다 (⑤ 실패는 요약에 반영되지 않는다).

**⑤ 정체성 일치** (2727~2731, 2764~2767)

- 대상은 현재 커서 1건뿐이다: `curItem = combo[s.serTgt ?? s.ds ?? 0] || combo[0] || {}`
- `ttlText = mkContentFor(curItem, 'ttl')` 에서 정규식 `/dcterms:title\s+"([^"]+)"/` 로 제목 추출 → `gotTitle`
- `idOk = !!gotTitle && gotTitle === curItem.n`
- `gate5Msg`:
  - 통과: `대상 · 산출물 제목 일치 ({curItem.n 또는 '—'})` + ` · ①~④는 산출물 내부 결함, ⑤는 요청↔산출물 불일치를 잡습니다`
  - 실패: `이 산출물은 '{curItem.n}'이 아니라 '{gotTitle}'을 서술하고 있습니다 — 반려` + 같은 꼬리 문구

### 3.7 파이프라인 탭 (`setPipe1`~`setPipe4`, logic.js 2631~2633)

`go({ pipe: n })`. 기본값 `s.pipe || 3`. `go()`에서 `savedHere = false` 처리와 400ms 디바운스 저장이 따라온다.

### 3.8 탭 본문 링크와 버튼

| 컨트롤 | 핸들러 | 결과 |
|---|---|---|
| `프리필 확인` (탭 ①) | `goStep3` | `go({ plane: 'studio', step: 3 })` |
| `승인 / 반려` (탭 ②) | 없음 | 동작 없음 |
| `해당 폼으로 이동` (탭 ③ 위반 표) | `goStep3` | 행과 무관하게 항상 STEP 3. `fixBack` 미설정 |
| `위반 수정 후 재검증` (탭 ③) | 없음 | 동작 없음 |
| `전송` / `갱신 알림` / `push` (탭 ④) | 없음 | `sendBtnStyle`만 `viol === 0`이면 활성 모양, 아니면 회색 |
| `STEP 4 다중분류체계 →` | `goStep4` | `go({ plane: 'studio', step: 4 })` |
| 라디오 `통제구역 (정본)` / `개방구역 …` | 없음 | 상태 미연결 |
| `통과분 발행 승인 ({{ v7Pass }}건)` | 없음 | `publishBtnStyle` 항상 활성 모양 (logic.js 1707) |
| `데이터 카탈로그에서 확인 →` | `goCatalog` | `go({ plane: 'catalog', catDetail: false })` |
| `일괄 재검증 실행` | `batchRun` (1270) | `batchOn` 토글. 켤 때 토스트 `✓ prov:Activity B-0032 (SoftwareAgent · 재검증 배치) 기록됨` (2600ms). 토스트 본문은 `toastMsg = s.toastText \|\| ('✓ prov:Activity ' + toastId + ' 기록됨')` (1708), `toastId = 'B-0032 (SoftwareAgent · 재검증 배치)'` |
| `일시정지` | 없음 | 동작 없음 |
| `중단` | `batchClose` | `go({ batchOn: false })` |

### 3.9 하단 `이전` / `다음 (확정)` (logic.js 2957~2994)

- `이전`: `step === 6 && pipe > 1` 이면 `pipe - 1`, 아니면 `step - 1`.
- `다음 (확정)`: `autoSave()` 후, `step === 6 && pipe < 4` 이면 `pipe + 1` + `showToast()` (토스트 `✓ prov:Activity ACT-K-04xx 기록됨`, 임의 번호, 2200ms, actLog 미기록). `pipe === 4` 이면 `step: 7`로 이동 시도 + 인계 알림 `notify: { from: 'STEP 6', to: 'STEP 7', owner: '데이터 품질관리팀' }` (5초). 이동은 `stepGate(7)` 통과가 필요하다.

### 3.10 단계 잠금과 무효화 전파 (검증 화면 밖에서 일어나지만 검증 상태를 바꾸는 동작)

**`stepGate(n)`** (logic.js 324~342)

- `comboOk = combo.length > 0 && comboMeta.done`
- `v6done = v7State === 'done' && !v6Stale`
- `v6passN = v6Results.filter(r => r.pass).length`
- STEP 6: `done = v6done`, `canEnter = comboOk`, reason `STEP 2 조합 확정을 먼저 완료하세요`
- STEP 7: `canEnter = v6done && v6passN >= 1`. reason은 `v7State === 'done' && v6Stale` 이면 `재검증 필요 — 정본이 변경되었습니다. STEP 6 검증을 다시 실행하세요`, 아니면 `STEP 6 검증을 먼저 실행하세요 (통과 1건 이상 필요)`
- STEP 8: `canEnter = convertState === 'done'`, reason `STEP 7 변환을 먼저 실행하세요`
- 잠긴 단계 진입 시도 시 토스트 `🔒 STEP {n} 잠김 — {reason}` (3000ms).
- 예외: `patch.comboMeta.done`을 함께 넘기는 이동(STEP 2 확정)은 게이트를 건너뛴다.

**`invalidateDownstream(kind, msg)`** (logic.js 344~356)

| kind | 호출 지점 | 패치 | 메시지 (토스트 + actLog `who = '시스템'`) |
|---|---|---|---|
| `'combo'` | 조합 추가 (40), 조합 제거 (650, 2195) | `{ v6Results: null, v7State: null, v6Stale: false, convertState: null, svResults: null, v8State: null }`. 단 하류 상태가 전혀 없으면 무시 | `조합 변경 — STEP 6·7 결과가 초기화되었습니다 (재검증 필요)` |
| `'catalog'` | STEP 3 `ardApprove` (2885) | `v7State === 'done'` 일 때만 `{ v6Stale: true, convertState: null, svResults: null, v8State: null }` | `카탈로그 승인 입력 — STEP 6 검증 결과 무효화 (재검증 필요 · STEP 7~8 재잠금)` |
| 그 외 | 호출 없음 | `{ convertState: null, svResults: null, v8State: null }` | |

STEP 2 조합 확정 (logic.js 2068) 도 `v6Results: null, v7State: null, v6Stale: false, convertState: null, svResults: null, v8State: null`로 초기화한다.

**무효화가 누락된 변경** (부록 B-4): STEP 3 publisher/mediaType 입력 변경(`ardPubSet`, `ardMtSet`은 `approved: false`로 되돌려 정본이 기본값으로 회귀하지만 무효화하지 않는다), STEP 4 분류 확정 토글(`dsDone4`), STEP 5 연계(`relPairs`), 발행 모드 전환(의도된 설계, 3.11).

### 3.11 발행 모드 토글 (화면은 STEP 7에 있음, `pubModeToggle`, logic.js 2755~2760)

- `pubMode = !published`. 주석: `모드 전환은 정본 불변 — 검증 무효화 없이 게이트 0 ④ 재평가만 수행`
- `v7State === 'done'` 이면 즉시 `v6Results = combo.map(validateDs)` 재계산 후 `persistDraft()`. `v6Stale`, `v7Time`은 바뀌지 않는다. 토스트와 actLog 없음.
- 버튼 문구: `발행 전 (초안 ID)` (주황) / `발행 후 (민팅 적용)` (녹색)
- 옆 주석: `초안 ID(결정적 해시) 상태 — 데이터셋별 고유, 발행 시 민팅 ID로 치환` / `민팅 맵 적용 — 실시간교통사고 = SVC-000043 · eTAS = DST-000962 · kma = SVC-000041`
- 발행 모드에서 `MINT_MAP`에 없는 데이터셋은 즉시 `FAIL`로 바뀌므로 `v6passN`이 0이 되면 STEP 7 재진입이 잠긴다.

### 3.12 `검증으로 복귀 ↩` (`fixBackGo`, 2857)

`go({ plane: 'studio', step: 6 })`. `fixBack`은 유지되며 다음 검증 완료 때 지워진다.

---

## 4. 검증 규칙 전체 목록

### 4.1 정본과 ID 생성 규칙 (모든 규칙의 입력)

- **메타 병합** `getMeta2(item)` (logic.js 143~147): `base = item.meta || META_TABLE[item.n] || {}`, `ov = metaOver[item.n]`. `ov.approved`가 참일 때만 `ov`를 덮어쓴다 (승인 전 입력은 미입력으로 간주).
- **정본** `buildCanonical(item)` (164~185):
  - `id` = `mintId(item, 'DST')` 또는 실패 시 `'DST-미민팅-' + hash6(n)`
  - `type` = 스트림이면 `['dcat:Dataset', 'dcat:DataService']`, 아니면 `['dcat:Dataset']`
  - `title` = `item.n || null`
  - `publisher` = (`noorg` 시뮬레이션 대상이 아니고 `m.orgId`가 있으면) `{ id: m.orgId, label: m.org }`, 아니면 `null`
  - `distribution` = 비스트림이고 `m.mediaTypeIana`가 있으면 `{ id: mintId(item,'DIST') || 'DIST-미민팅-'+hash6, mediaType, label: m.form }`, 아니면 `null`
  - `activity` = `{ id: mintId(item,'ACT') || 'ACT-미민팅-'+hash6 }`
  - 스트림이면 `temporalResolution = m.temporalResolution || null`, `eventTimeColumn = m.eventTime || null`
  - `readiness.required` = 스트림 `['title','publisher']`, 비스트림 `['title','publisher','distribution']`. `missing` 없으면 `level = 'ai-ready'`, 있으면 `'draft'`
  - `_minted = !!minted`
- **ID 민팅** `mintId(item, kind)` (150~162):
  - 발행 모드 (`pubMode === true`): `MINT_MAP[n]`이 있으면 `kind === 'DST'` → 그 값, 그 외 → `값 + '-' + kind` (예: `DST-000961-DIST`, `SVC-000042-ACT`). 없거나 `nomint` 시뮬레이션 대상이면 `null` (fallback 발급 금지).
  - 초안 모드: `{K}-draft-{hash6(n)}`. 스트림의 본체 ID는 `SVC-draft-…`, 그 외 `DST-draft-…`, `DIST-draft-…`, `ACT-draft-…`.
  - `hash6(str)` (139): 각 문자에 대해 `h = (h + charCode * 31) % 999999`, 6자리 0 채움. 문자 순서에 무관한 합 기반 해시라 충돌 가능성이 높다.
- **트리플** `buildTriples(c)` (187~212): 결측 필드는 트리플을 만들지 않는다. 생성 술어: `rdf:type`, `dcterms:title`(@ko), `dcterms:publisher`(IRI) + 기관 노드 `rdf:type foaf:Agent`, `rdfs:label`(@ko), `dcat:distribution` + 배포 노드 `rdf:type dcat:Distribution`, `dcat:mediaType`(IANA IRI `https://www.iana.org/assignments/media-types/{mt}`), `dcterms:format`(@ko, 데이터셋 노드에), `dcat:temporalResolution`(plain), `fde:eventTimeColumn`(plain), `dcat:endpointDescription`(IRI `https://api.molit.go.kr/streams/{hash6(title)}`, DataService만), `prov:wasGeneratedBy` + 활동 노드 `rdf:type prov:Activity`, `prov:wasAssociatedWith <https://catalog.molit.go.kr/id/agent/fde-studio>`, `prov:endedAtTime`(xsd:dateTime, `convertTimeIso`가 있을 때만).

### 4.2 목업이 실제로 평가하는 규칙: `validateDs` (logic.js 309~322)

판정은 `buildCanonical` 결과 객체의 필드 존재 여부로 한다. `buildTriples`는 호출하지 않는다 (화면 문구 `buildTriples 출력 기준`과 다름, 부록 B-3).

| # | 규칙 이름 (`shape` 문자열 원문) | 평가 조건 (logic.js 줄) | 심각도 | 대상 클래스 | 속성 경로 | 수정 경로 (`route` → `FIX_ROUTE`) | 실제 평가 |
|---|---|---|---|---|---|---|---|
| R1 | `게이트 0 ④ — 민팅 미등록 (fallback 발급 금지)` | `pubMode === true && !c._minted` (313) | Violation (FAIL) | dcat:Dataset (스트림 포함) | 노드 IRI 자체 | `mint` → STEP 2, `ID 발급 안내 · 관리 탭 민팅 정책` | 평가함 (발행 모드에서만) |
| R2 | `게이트 0 ⑤ — 정체성 (제목 결측)` | `!c.title` (314) | Violation | dcat:Dataset | dcterms:title | `identity` → STEP 2, `조합 확정 카드` | 평가함 (이름이 빈 경우에만 실패) |
| R3 | `PublisherShape — sh:nodeKind sh:IRI (publisher 결측)` | `!c.publisher` (315) | Violation | dcat:Dataset | dcterms:publisher | `publisher` → STEP 3 (tab3 = 2), `publisher 필드` | 평가함 |
| R4 | `MediaTypePlacementShape — Distribution 결측` | `!isStream && !c.distribution` (317) | Violation | dcat:Dataset (dcat:DataService 제외) | dcat:distribution / dcat:mediaType | `mediaType` → STEP 3 (tab3 = 2), `mediaType 드롭다운` | 평가함 |
| R5 | `스트림 필수 — temporalResolution·eventTime 결측` | `isStream && (!c.temporalResolution \|\| !c.eventTimeColumn)` (318) | Violation | dcat:DataService | dcat:temporalResolution, fde:eventTimeColumn | `stream3` → STEP 3 (tab3 = 2), `스트림 속성 카드` | 코드상 평가하나 도달 불가 (스트림 3종 모두 `META_TABLE`에 값이 있고 수정 UI가 없음) |
| R6 | `분류 미완 Warning — f1·f2 미선택 (카탈로그 탐색 불가)` | `!dsDone4[item.n]` (319) | Warning (통과에 영향 없음) | dcat:Dataset | 분류 속성 (F1, F2) | `class4` → STEP 4, `분류 매트릭스` | 평가함. 단 실제 f1/f2 선택값이 아니라 STEP 4의 확정 플래그만 본다 |
| R7 | `렌더러 예외 — {e.message}` | `try/catch` (321) | Violation | (전체) | (없음) | `publisher` → STEP 3 | 예외 발생 시에만 |

`isStream = c.type.includes('dcat:DataService')` (316).

### 4.3 `FIX_ROUTE` 전체 (logic.js 129~138, 단일 상수)

| route 키 | step | label (원문) | `validateDs`가 방출하는가 |
|---|---|---|---|
| `identity` | 2 | `조합 확정 카드` | 예 (R2) |
| `mint` | 2 | `ID 발급 안내 · 관리 탭 민팅 정책` | 예 (R1) |
| `publisher` | 3 | `publisher 필드` | 예 (R3, R7) |
| `mediaType` | 3 | `mediaType 드롭다운` | 예 (R4) |
| `emptyLit` | 3 | `해당 필드` | 아니오 (선언만 있음. NoEmptyLiteralShape용) |
| `stream3` | 3 | `스트림 속성 카드` | 예 (R5) |
| `class4` | 4 | `분류 매트릭스` | 예 (R6) |
| `lineage5` | 5 | `연계 초안 행` | 아니오 (선언만 있음. 리니지 미결은 모달 게이트로 처리) |

### 4.4 게이트 0 표의 5개 검사

| 검사 (원문) | 무엇을 확인하는가 | 심각도 | 대상 / 경로 | 수정 경로 | 실제 평가 |
|---|---|---|---|---|---|
| `① 파서 통과` | 직렬화 텍스트가 파싱되는가 | Violation 상당 (실패 시 산출물 폐기) | 직렬화 Turtle 텍스트 | 없음 (렌더러 결함) | STEP 6에서는 표시만 (`STEP 7`로 이동 표기). STEP 7 `selfVerify` `① TTL 재파싱`이 정규식 `/@prefix dcat:/` 과 `/\.\s*$/m` 로 흉내 (logic.js 299) |
| `② prefix 완결` | 사용된 prefix가 모두 선언됐는가 | 같음 | 직렬화 Turtle 텍스트 | 없음 | STEP 7 `selfVerify` `② prefix 완결` (300~301). 정규식 기반 |
| `③ 인코딩 UTF-8` | UTF-8 정상 | 같음 | 직렬화 텍스트 | 없음 | STEP 7 `selfVerify` `③ UTF-8 정상`은 항상 `true` (302) |
| `④ ID 잔존 검사 — 패턴 (-신규\|-draft-)` | 발행 산출물에 임시 ID가 남지 않았는가 | Violation | 모든 주체 IRI | `mint` → STEP 2 | 패널: `!pubMode \|\| 전 데이터셋 MINT_MAP 등록` (2742~2743). 데이터셋별: R1. 실제 패턴 매칭은 하지 않는다 |
| `⑤ 정체성 일치 (요청 대상 ↔ 산출물 제목)` | 요청한 데이터셋과 산출물 제목이 같은가 | Violation (`반려`) | dcat:Dataset / dcterms:title | `identity` → STEP 2 | 패널: 현재 커서 1건의 TTL에서 제목을 뽑아 비교 (2728~2731). 데이터셋별: R2는 제목 존재만 확인 |

STEP 7 파생 자가검증의 4번째 검사 `④ TTL↔JSON-LD 트리플 일치` (logic.js 303~304: JSON-LD `@graph`의 값 개수 합 = 트리플 수) 는 게이트 0 표에는 없지만 같은 계열이다.

### 4.5 이름만 표시되고 평가하지 않는 셰이프와 규칙

| 이름 (원문) | 출처 (마크업 줄) | 설명 | 심각도 (표시 기준) | 대상 / 경로 | 수정 경로 | 평가 여부 |
|---|---|---|---|---|---|---|
| `NoEmptyLiteralShape (sh:minLength 1)` | 1995 | 빈 리터럴 금지 | Violation | 모든 리터럴 | `emptyLit` → STEP 3 `해당 필드` (선언만) | 미평가. 구조적 보장만 있음: `buildTriples`가 결측 필드를 생략하고, `renderTtl`/`renderJsonld`가 빈 값에서 `빈 리터럴 — 렌더러 결함` 예외 (215, 247) |
| `NoDanglingRefShape (참조 IRI 타입 선언 필수)` | 1995 | 참조된 IRI는 타입 선언이 있어야 함 | Violation | 객체 IRI | 없음 | 미평가. `buildTriples`가 참조와 정의를 쌍으로 생성 (주석 187). 단 `prov:wasAssociatedWith` 에이전트 IRI, IANA mediaType IRI, `dcat:endpointDescription` IRI는 타입 선언이 없다 |
| `DatasetShape` | 2052 (`DatasetShape 외 4종 · rs-2.1`), 2225/2230 (`DatasetShape v1.2`), 1764 (`DatasetShape v3.2`), 1797 | 데이터셋 필수 항목 | | dcat:Dataset | | 표시만 (버전 표기가 3곳에서 서로 다름) |
| `DistributionShape` | 2226, 1765 (`DistributionShape v3.2`), 1797 | 배포본 필수 항목 | | dcat:Distribution | | 표시만 |
| `StreamServiceShape` | 2003, 1766 (`StreamServiceShape v1.0`), logic 1557, 1581 | 스트림 서비스. 고정 행에서 `워터마크 PT1M 선언 확인 · 통제 산출 N2SF 게이트` | Warning (고정 행) | dcat:DataService | | 표시만 |
| `ActivityShape` | 2229 | prov:Activity 형상 | | prov:Activity | | 표시만 |
| `N2SFZoneShape` | 2185 | N2SF 등급과 발행 구역 일치. 등급 미지정은 S로 간주 | | dcat:Dataset | STEP 4 (링크) | 표시만 (건수는 이름 규칙으로 집계) |
| `④ 스트림 Shape 3종 (Service · Plan · 파생)` | 2137 | 평면 B (마크업 2584) 기준 `StreamServiceShape`, `EventPlanShape`, `DerivedEventDatasetShape` | | | | 표시만 |
| `① SKOS 통제어휘 (66코드 준수) ✓` | 2134 | 통제어휘 준수 | | | | 표시만 (항상 ✓) |
| `② DCAT/PROV-O 필수항목 ✓` | 2135 | 필수 항목 | | | | 표시만 (항상 ✓) |
| `③ 가이드라인 80항목 대조` | 2136 | 가이드라인 대조 (80항목 중 35항목 자동판정, 마크업 2344) | | | | 표시만 |
| `prov:wasAttributedTo 외부 출처` | logic 1556 | kma 스트림 고정 행. 메시지 `AGT-기상청 연결 확인 · 공공데이터 이용허락 표기` | Warning | `SVC-신규 (kma)` | `해당 폼으로 이동` → STEP 3 | 고정 데이터 |
| `dcterms:conformsTo (좌표계) 미선언` | logic 1558 | 이름에 `도로` 포함 시. 메시지 `GEOM 컬럼 EPSG 명시 필요 — EPSG:5186 권장` | Warning | `DST-신규 (도로)` | STEP 3 | 고정 데이터 |
| `dcat:mediaType 확인` | logic 1559 | 그 외 모든 데이터셋. 메시지 `{n} — 배포본 mediaType 검수` | Warning | `DST-신규` | STEP 3 | 고정 데이터 |
| `accrualPeriodicity 표기 (신규 Shape)` | 2227 | 배치 로그 `WARN SER-0031` | Warning | 시리즈 | | 고정 문구 |
| `rai:dataBiases 누락 (v1.2 신설 필수)` | 2228 | 배치 로그 `FAIL DST-000871` | Violation | dcat:Dataset | | 고정 문구 |
| 접합부 계약 (`푸터 식별자 · spdx:checksum 일치`) | 2158, logic 1562~1571 | 메타 평면과 데이터 평면 대조 | | 파일 / 배포본 | | 고정 규칙 (5.4) |
| 리니지 미결 경고 게이트 | 1938~1950, logic 1659 | `relPairs` 없음 + 조합 2건 이상 + 미면제 | 경고형 게이트 (사유 입력 시 진행) | 프로세스 | STEP 5 (`돌아가기 (STEP 5)`). `FIX_ROUTE.lineage5`는 미사용 | 실제 평가함 |

Info 심각도는 목업 어디에도 쓰이지 않는다. 표시 체계는 `통과` / `Warning` (또는 `W`, `WARN`) / `Violation` (또는 `V`, `FAIL`) 3단계다.

### 4.6 SHACL Turtle 스니펫

**이 단계의 마크업과 로직에는 SHACL Turtle 스니펫이 하나도 없다.** SHACL 용어가 나오는 원문은 아래 3개가 전부다.

1. 마크업 1995: `등재 셰이프: PublisherShape (sh:nodeKind sh:IRI) · MediaTypePlacementShape (Distribution 전용) · NoEmptyLiteralShape (sh:minLength 1) · NoDanglingRefShape (참조 IRI 타입 선언 필수)`
2. logic.js 315: `'PublisherShape — sh:nodeKind sh:IRI (publisher 결측)'`
3. 마크업 1768 (STEP 7 화면): `매핑 예: sh:minCount 1 → required[] · sh:datatype xsd:string → "type": "string"`

실제 셰이프 그래프는 새로 작성해야 한다 (8.2 제안).

---

## 5. 데이터 (하드코딩 목록 원문)

### 5.1 시뮬레이션 모드

| value | 표시 | 효과 |
|---|---|---|
| `off` | `끔` | `simMode = null` |
| `nomint` | `MINT 미등록 재현` | 발행 모드에서 `combo[0]` 민팅 실패 |
| `noorg` | `publisher 결측 재현` | `combo[0]` publisher 제거 |

### 5.2 `MINT_MAP` (logic.js 117~123)

| 이름 | 민팅 ID |
|---|---|
| `kma.aws.obs.v1` | `SVC-000041` |
| `cctv.vehicle.det.v1` | `SVC-000042` |
| `sample_공간정보_통합포털_데이터셋_목록_도로` | `DST-000961` |
| `실시간교통사고` | `SVC-000043` |
| `디지털운행기록분석시스템(eTAS)_정보시스템` | `DST-000962` |

### 5.3 `META_TABLE` (logic.js 106~116)

| 이름 | kind | org | orgId | 그 외 |
|---|---|---|---|---|
| `sample_공간정보_통합포털_데이터셋_목록_도로` | dataset | `국토교통부` | `https://catalog.molit.go.kr/id/org/ORG-1613000` | form `정형(엑셀)`, xlsx mediaType, role `도로 공간정보 — 사고 원인 분석 조합 베이스` |
| `cctv.vehicle.det.v1` | stream | `경기도건설본부(데모)` | `…/ORG-6410000` | form `실시간 스트림(관측)`, temporalResolution `PT1S`, eventTime `event_time`, role `CCTV 차량 관측 — 과속·사고 판정 입력` |
| `kma.aws.obs.v1` | stream | `기상청(외부 출처)` | `…/ORG-1360000` | form `실시간 스트림(컨텍스트)`, `PT10M`, `obs_time`, role `기상 관측 — 조건부 기준값 판정 컨텍스트` |
| `sample_교통사고심층조사시스템_비정형_` | dataset | `경찰청·도로교통공단(데모)` | `…/ORG-1320000` | xlsx, role `교통사고 심층조사 — 사고 원인·사상 정보` |
| `sample_데이터오픈마켓(30종)` | dataset | `국토교통부` | `…/ORG-1613000` | xlsx, role `오픈마켓 30종 목록 — 사고심층조사 연관 그룹` |
| `sample_디지털운행기록분석시스템(eTAS)` | dataset | `한국교통안전공단(데모)` | `…/ORG-B552016` | xlsx, role `차량 운행기록 — 차량 흐름 분석 입력` |
| `sample_실시간기상관측자료수집시스템_기상청_` | dataset | `기상청(외부 출처)` | `…/ORG-1360000` | xlsx, role `기상 관측 수집 목록 — 협약 확인 필요` |
| `실시간교통사고` | stream | `국토교통부(데모)` | `…/ORG-1613000` | form `실시간 스트림(관측)`, `PT5M`, `event_time`, role `실시간 교통사고 이벤트 — 관제 통보 입력` |
| `디지털운행기록분석시스템(eTAS)_정보시스템` | dataset | `한국교통안전공단(데모)` | `…/ORG-B552016` | xlsx, role `차량 운행기록 분석 — 차량 흐름 분석 입력` |

xlsx mediaType = `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. `META_TABLE`에 없는 데이터셋(사용자 업로드 등)은 STEP 3에서 승인 입력을 하기 전까지 R3과 R4에 걸린다.

`IANA_OPTS` (124~127): `xlsx` (위 값), `text/csv` (`csv`), `application/json` (`json`), `application/x-hwp` (`hwp`), `application/pdf` (`pdf`).

### 5.4 탭 ③ 위반 표 고정 행 생성 규칙 (`v7Rows`, logic.js 1554~1561)

조합의 데이터셋마다 정확히 1행을 만든다. 모두 `Warning`.

| 조건 | 대상 리소스 | 위반 Shape | 위반 메시지 |
|---|---|---|---|
| `n === 'kma.aws.obs.v1'` | `SVC-신규 (kma)` | `prov:wasAttributedTo 외부 출처` | `AGT-기상청 연결 확인 · 공공데이터 이용허락 표기` |
| `n === 'cctv.vehicle.det.v1'` | `SVC-신규 (cctv)` | `StreamServiceShape` | `워터마크 PT1M 선언 확인 · 통제 산출 N2SF 게이트` |
| 이름에 `도로` 포함 | `DST-신규 (도로)` | `dcterms:conformsTo (좌표계) 미선언` | `GEOM 컬럼 EPSG 명시 필요 — EPSG:5186 권장` |
| 그 외 | `DST-신규` | `dcat:mediaType 확인` | `{n} — 배포본 mediaType 검수` |

집계: `v7Warn = rows.length` (= 조합 건수), `v7Pass = max(combo.length - (viol > 0 ? 1 : 0), 0)`, `violCount = viol = this.props.violationCount ?? 0` (logic.js 375, 1410, 1587~1588). 즉 `v6Results`와 무관하다.

접합부 계약 행 (`v7Joints`, 1562~1571): 이름이 `/cctv|kma/` 이면 `{n} (스트림)` / `— 스트림: 세션 요약(ACT-S)으로 대조 · 파일 대조 제외`. 비스트림이고 조합 첫 번째(인덱스 0)면 `{n}.xlsx` / `✕ 원본 체크섬 미기록 — 적재 시 부여 필요`. 그 외 `{n}.xlsx` / `✓ 푸터 식별자 · spdx:checksum 일치`.

### 5.5 탭 ①, ② 고정 행 (logic.js 1574~1585)

탭 ① (`p1Rows`):

| 조건 | 대상 리소스 | 추출 항목 | 신뢰도 | 상태 |
|---|---|---|---|---|
| cctv | `SVC-신규 (cctv)` | `토픽 스키마 (Avro) · 인식 모델 MDL-000004 참조` | `99%` | `완료` |
| kma | `SVC-신규 (kma)` | `관측 스키마 · 지점코드 · late 정책` | `98%` | `완료` |
| `도로` 포함 | `DST-신규 (도로)` | `스키마 14컬럼 · PK/FK · GEOM 좌표계 미선언` | `72%` | `부분 추출` |
| 그 외 | `DST-신규` | `{n} — 스키마 자동추론` | `90%` | `완료` |

`p1Ok` = `완료` 수, `p1Part` = `부분 추출` 수, `p1Fail = 0`.

탭 ② (`p2Rows`):

| 조건 | 대상 리소스 | sLLM 보정 제안 | 상태 | 검수자 |
|---|---|---|---|---|
| cctv | `SVC-신규 (cctv)` | `워터마크 PT1M 선언 제안 (StreamServiceShape)` | `초안 · 승인 대기` | `김검수` |
| kma | `SVC-신규 (kma)` | `prov:wasAttributedTo → AGT-기상청 연결 제안` | `승인됨` | `이관리` |
| `도로` 포함 | `DST-신규 (도로)` | `dcterms:conformsTo → EPSG:5186 제안` | `초안 · 승인 대기` | `김검수` |
| 그 외 | `DST-신규` | `{n} — keyword 자동 제안 (sLLM)` | `승인됨` | `김검수` |

`p2Ok` = `승인됨` 수, `p2Wait` = 그 외 수.

### 5.6 배치 실시간 처리 로그 (마크업 2225~2230, 고정)

```
09:41:22 PASS DST-001213 (통제) · DatasetShape v1.2
09:41:22 PASS DST-001212 (개방 투영) · DistributionShape
09:41:21 WARN SER-0031 · accrualPeriodicity 표기 (신규 Shape)
09:41:20 FAIL DST-000871 · rai:dataBiases 누락 (v1.2 신설 필수)
09:41:19 PASS DST-001209 (통제) · ActivityShape
09:41:19 PASS DST-001208 (통제) · DatasetShape v1.2
```

### 5.7 N2SF 집계 (logic.js 1599~1602)

`n2sfOCnt` = 이름이 `cctv.vehicle.det.v1`이 아닌 건수, `n2sfSCnt = 0`, `n2sfCCnt` = `cctv.vehicle.det.v1` 건수. 패널 표시 조건 `n2sfOn = s.n2sfPolicy ?? (props.n2sfEnabled ?? true)` (2299).

### 5.8 상태 배지 색상

| 배지 | 조건 | 스타일 |
|---|---|---|
| 실행 상태 | done / run / idle | `#e6f4ea;#1e7e46` / `#E8EEFF;#1648D6` / `#EEF1F5;#8B919C` |
| 데이터셋 판정 | 통과 / FAIL | `#e6f4ea;#1e7e46` / `#c0392b;#fff` |
| 게이트 0 결과 | 통과 / 실패 / 이동 | `#e6f4ea;#1e7e46` / `#c0392b;#fff` / `#EEF1F5;#8B919C` |
| 심각도 | Warning / Violation | `#fdf3e7;#b05c1a` (`sevW`) / `#fdf1ef;#c0392b` (`sevV`, 정의만 있고 미사용) |

### 5.9 그 외 고정 표시값

`rs-2.1` (Shape 세트 버전), `방금 · 소요 4초`, `ACT-B-0032`, `batch-revalidator v1.4`, `박관리`, `가이드라인 v1.1 → v1.2 개정 (Shape 6종 변경)`, 사용자 `홍길동 (나)`, 검수자 `김검수` / `이관리`.

---

## 6. 상태 변수

| 키 | 타입 | 의미 | 저장(스냅숏) 여부 |
|---|---|---|---|
| `v7State` | `null \| 'run' \| 'done'` | 검증 실행 상태 (이름은 과거 번호) | 저장 |
| `v6Results` | `null \| Array<{ n, pass, fails: {shape, route}[], warns: {shape, route}[] }>` | 데이터셋 단위 판정 결과 | 저장 |
| `v6Stale` | `boolean` | 정본 변경으로 결과가 무효화됨 (재검증 필요) | 저장 |
| `v7Time` | `string "HH:MM"` | 최근 검증 완료 시각 (홈 대시보드 `최근 실행 {v7Time} (내 검증)`) | 저장 |
| `pubMode` | `boolean` (기본 `false`) | 발행 모드. `true`면 `MINT_MAP` 민팅 ID 적용과 게이트 0 ④ 활성 | 저장 |
| `simMode` | `null \| 'nomint' \| 'noorg'` | 검수 시뮬레이션 결함 주입 | 저장 제외, 복원 시 `null` |
| `fixBack` | `null \| { shape: string, step: number }` | 왕복 루프: 어떤 위반을 고치러 어느 단계로 나갔는가 | 저장 제외 |
| `fixField` | `null \| route 키` | 원인 단계의 강조 대상 필드. 2400ms 후 `null` | 저장 제외 |
| `linAsk` | `boolean` | 리니지 미결 모달 표시 | 저장 제외 |
| `linReason` | `string` | 모달 입력 중인 사유 | 저장 제외 |
| `linWaived` | `boolean` | 사유 기록 후 리니지 미결 면제 | 저장 |
| `pipe` | `1..4` (기본 3) | 파이프라인 탭 | 저장 (프로세스 스냅숏 `workKeys`에도 포함) |
| `batchOn` | `boolean` | 배치 진행 상자 표시 | 저장 제외 |
| `taskProcSel` | `null \| string[]` | 검증 대상으로 호출한 프로세스 이름 목록 (`null`이면 현재 프로세스 단일 모드) | 저장 |
| `procName` | `string` | 현재 프로세스 이름 (복수 호출 시 `' + '`로 연결) | 저장 |
| `combo` | `Array<{ n, k, ... }>` | 검증 대상 데이터셋 조합 | 저장 |
| `comboMeta.done` | `boolean` | STEP 2 조합 확정 여부 (`stepGate` 입력) | 저장 |
| `metaOver` | `{ [n]: { org, orgId, mediaTypeIana, approved } }` | STEP 3 승인 입력 (정본 덮어쓰기) | 저장 |
| `dsDone4` | `{ [n]: boolean }` | STEP 4 분류 확정 플래그 (R6 입력) | 저장 |
| `relPairs` | `Array` | STEP 5 연계 쌍 (리니지 게이트 입력) | 저장 |
| `serTgt`, `ds`, `ds3` | `number` | 작업 대상 커서 (게이트 0 ⑤ 패널 대상, `goFix`가 `ds`, `ds3` 설정) | 저장 |
| `convertState`, `svResults`, `v8State` | | 하류(STEP 7, 8) 상태. 무효화 대상 | 저장 |
| `actLog` | `Array<{ t, who, txt, actId }>` (최근 10건) | 활동 로그 | 저장 |
| `actSeq` | `number` (기본 420) | `ACT-K-` 시퀀스 | 저장 |
| `n2sfPolicy` | `boolean \| undefined` | N2SF 정책 적용 여부 | 저장 |
| `toast`, `toastText`, `toastId` | | 토스트 | `toast`, `toastText` 저장 제외 |

컴포넌트 props: `violationCount` (기본 0), `n2sfEnabled` (기본 true).

프로세스 스냅숏 `workKeys` (logic.js 920) 에는 `v7State`, `v6Results`, `v6Stale`, `pubMode`, `linWaived`가 **없다**. 검증 결과는 프로세스 단위로 보존되지 않는다.

---

## 7. 시뮬레이션 vs 실제 계산

### 7.1 실제로 계산되는 것

- 정본 생성 (`buildCanonical`), 메타 병합 (`getMeta2`), ID 발급 (`mintId`, `hash6`).
- `validateDs`의 6개 조건 판정과 데이터셋 단위 pass/fail, 통과/미통과 건수.
- 발행 모드 전환에 따른 즉시 재판정.
- `simMode`에 의한 결함 주입 (정본 생성 단계에 실제로 반영).
- 게이트 0 ④ 패널 (민팅 등록 여부), ⑤ 패널 (TTL 텍스트에서 제목 추출 후 비교).
- `FIX_ROUTE` 조회, 원인 단계 이동, 커서 맞춤, `fixBack` 배너, 필드 강조 (publisher, mediaType 2종).
- `stepGate` 잠금, `invalidateDownstream` 무효화, `v6Stale` 배지.
- 리니지 미결 조건 판정과 사유 기록.
- actLog 기록 (세션 시퀀스 `ACT-K-0421`~), `localStorage` 스냅숏.
- 프로세스 복수 호출 시 조합 합집합 계산.

### 7.2 흉내만 내는 것

- **SHACL 엔진 자체가 없다.** RDF 그래프, 셰이프 그래프, 검증 리포트(`sh:ValidationReport`)가 존재하지 않는다. "SHACL"은 JS 객체 필드의 null 검사다.
- 검증 대상이 트리플이라는 문구와 달리 `validateDs`는 `buildTriples`를 호출하지 않는다.
- 실행 지연 1400ms는 `setTimeout`.
- 실행마다 `prov:Activity` 기록이라는 문구는 actLog 한 줄로 대체. 검증 실행 레코드, 결과 이력, 이전 실행과의 비교가 없다.
- 탭 ①②③④의 KPI, 표, 접합부 점검, N2SF 건수, 전송 채널 상태, 배치 진행 상자는 전부 고정값 또는 이름 패턴 규칙. 특히 탭 ③의 `통과 / Warning / Violation` 수치와 위반 표는 `v6Results`와 연결되지 않는다 (예: 실제 FAIL이 있어도 `V 0`, 모든 데이터셋에 Warning 1건).
- `Shape 세트 DatasetShape 외 4종 · rs-2.1`, `최근 실행 방금 · 소요 4초`는 고정 문구.
- `전송`, `갱신 알림`, `push`, `통과분 발행 승인`, `위반 수정 후 재검증`, `승인 / 반려`, `일시정지`, 구역 라디오는 핸들러가 없다.
- 게이트 0 ①②③은 이 화면에서 `STEP 7` 고정 배지만 보여준다.
- `NoEmptyLiteralShape`, `NoDanglingRefShape`, `DatasetShape`, `DistributionShape`, `StreamServiceShape`, `ActivityShape`, `N2SFZoneShape`는 이름만 있다.
- 토스트의 `ACT-K-04xx` (공통 `showToast`) 는 임의 번호이며 actLog와 무관하다.

---

## 8. 실제 제품에서 필요한 기능 (제안)

### 8.1 처리 파이프라인

1. **정본 그래프 구성**: 데이터셋별로 PostgreSQL의 승인된 메타데이터에서 rdflib `Graph`를 만든다 (데이터셋 1건 = 그래프 1개, 저장 시 named graph `…/graph/dataset/{id}/draft`). 검증 대상과 STEP 7 직렬화 대상이 같은 그래프임을 `canonical_checksum`(정규화 N-Triples의 SHA-256)으로 보증한다.
2. **게이트 0 (코드 검사, SHACL 이전)**:
   - ① 파서 통과: 정본을 Turtle로 직렬화한 뒤 rdflib로 재파싱. 실패 시 해당 데이터셋은 SHACL을 실행하지 않고 종료 (목업 문구 `SHACL까지 가지 않음`).
   - ② prefix 완결: 직렬화 텍스트에서 미선언 prefix 탐지 (재파싱 오류로 흡수 가능하나 원인 분류를 위해 별도 코드).
   - ③ 인코딩 UTF-8: 바이트 디코딩 검사.
   - ④ ID 잔존: 그래프의 모든 IRI에 정규식 `(-신규|-draft-|-미민팅-)` 적용 + 민팅 레지스트리 조회. 발행 프로파일에서만 Violation, 초안 프로파일에서는 Info.
   - ⑤ 정체성 일치: 실행 요청에 담긴 데이터셋 ID와 제목을 그래프의 `dcterms:title`과 대조.
   - ①②③은 목업처럼 STEP 7 직후 자가검증에서도 다시 수행한다.
3. **SHACL**: `pyshacl.validate(data_graph, shacl_graph=shapes, ont_graph=vocab, inference='none', advanced=True, allow_warnings=True, abort_on_first=False)`. 결과 그래프의 `sh:ValidationResult`를 행으로 풀어 저장한다.
4. **판정**: 데이터셋 단위. `sh:Violation` 0건이고 게이트 0 실패가 없으면 통과. Warning과 Info는 통과에 영향을 주지 않되 화면에 표시한다.
5. **기록**: 실행마다 `prov:Activity`(사람 실행은 `prov:Person`, 배치는 `prov:SoftwareAgent` + `prov:actedOnBehalfOf`)와 검증 실행 레코드를 남긴다.

### 8.2 셰이프 그래프 제안 (목업 규칙과의 대응)

아래는 제안이며 목업에 있는 내용이 아니다. `fde:` 네임스페이스는 목업의 `https://catalog.molit.go.kr/def/`를 따른다. 두 Turtle 블록은 rdflib로 파싱하고 pySHACL(`advanced=True`)로 시험 그래프에 실행해 위반과 경고가 의도대로 나오는 것까지 확인했다. SHACL-SPARQL 제약에는 `VALUES`, `MINUS`, `SERVICE` 절을 쓸 수 없으므로 술어 목록은 `FILTER(?path IN (…))`로 적는다.

```turtle
@prefix sh:      <http://www.w3.org/ns/shacl#> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix dcat:    <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix prov:    <http://www.w3.org/ns/prov#> .
@prefix foaf:    <http://xmlns.com/foaf/0.1/> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix fde:     <https://catalog.molit.go.kr/def/> .
@prefix fdesh:   <https://catalog.molit.go.kr/shapes/> .

fdesh: a owl:Ontology ;
  owl:versionInfo "rs-2.1" ;
  sh:declare [ sh:prefix "dcat" ;    sh:namespace "http://www.w3.org/ns/dcat#"^^xsd:anyURI ] ,
             [ sh:prefix "dcterms" ; sh:namespace "http://purl.org/dc/terms/"^^xsd:anyURI ] ,
             [ sh:prefix "prov" ;    sh:namespace "http://www.w3.org/ns/prov#"^^xsd:anyURI ] ,
             [ sh:prefix "fde" ;     sh:namespace "https://catalog.molit.go.kr/def/"^^xsd:anyURI ] .

# R2 · 게이트 0 ⑤ (존재 부분) — 정체성
fdesh:DatasetIdentityShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset ;
  sh:property [
    sh:path dcterms:title ;
    sh:minCount 1 ; sh:minLength 1 ; sh:uniqueLang true ;
    sh:severity sh:Violation ;
    fde:fixRoute "identity" ;
    sh:message "게이트 0 ⑤ — 정체성 (제목 결측)"@ko ] .

# R3 — PublisherShape
fdesh:PublisherShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset ;
  sh:property [
    sh:path dcterms:publisher ;
    sh:minCount 1 ; sh:nodeKind sh:IRI ; sh:class foaf:Agent ;
    sh:severity sh:Violation ;
    fde:fixRoute "publisher" ;
    sh:message "PublisherShape — sh:nodeKind sh:IRI (publisher 결측)"@ko ] .

fdesh:AgentShape a sh:NodeShape ;
  sh:targetClass foaf:Agent ;
  sh:property [
    sh:path rdfs:label ; sh:minCount 1 ; sh:minLength 1 ;
    sh:severity sh:Warning ; fde:fixRoute "publisher" ;
    sh:message "기관 라벨 결측"@ko ] .

# R4 (1) — mediaType 배치: Dataset에 직접 두지 않는다 (Distribution 전용)
fdesh:MediaTypePlacementShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset ;
  sh:property [
    sh:path dcat:mediaType ; sh:maxCount 0 ;
    sh:severity sh:Violation ; fde:fixRoute "mediaType" ;
    sh:message "MediaTypePlacementShape — dcat:mediaType은 Distribution 전용"@ko ] .

# R4 (2) — 파일형 데이터셋은 Distribution 1개 이상 (DataService는 면제)
fdesh:FileDatasetDistributionShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset ;
  sh:or ( [ sh:class dcat:DataService ]
          [ sh:property [ sh:path dcat:distribution ; sh:minCount 1 ] ] ) ;
  sh:severity sh:Violation ; fde:fixRoute "mediaType" ;
  sh:message "MediaTypePlacementShape — Distribution 결측"@ko .

fdesh:DistributionShape a sh:NodeShape ;
  sh:targetClass dcat:Distribution ;
  sh:property [
    sh:path dcat:mediaType ;
    sh:minCount 1 ; sh:maxCount 1 ; sh:nodeKind sh:IRI ;
    sh:pattern "^https://www\\.iana\\.org/assignments/media-types/[a-z]+/.+" ;
    sh:severity sh:Violation ; fde:fixRoute "mediaType" ;
    sh:message "dcat:mediaType은 IANA 미디어타입 IRI여야 한다"@ko ] ;
  sh:property [
    sh:path [ sh:inversePath dcat:distribution ] ;
    sh:minCount 1 ; sh:class dcat:Dataset ;
    sh:severity sh:Violation ;
    sh:message "소속 Dataset 없는 Distribution"@ko ] .

# R5 — 스트림 필수
fdesh:StreamServiceShape a sh:NodeShape ;
  sh:targetClass dcat:DataService ;
  sh:property [
    sh:path dcat:temporalResolution ;
    sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:duration ;
    sh:severity sh:Violation ; fde:fixRoute "stream3" ;
    sh:message "스트림 필수 — temporalResolution·eventTime 결측"@ko ] ;
  sh:property [
    sh:path fde:eventTimeColumn ;
    sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ; sh:minLength 1 ;
    sh:severity sh:Violation ; fde:fixRoute "stream3" ;
    sh:message "스트림 필수 — temporalResolution·eventTime 결측"@ko ] ;
  sh:property [
    sh:path dcat:endpointDescription ; sh:minCount 1 ; sh:nodeKind sh:IRI ;
    sh:severity sh:Warning ; fde:fixRoute "stream3" ;
    sh:message "스트림 엔드포인트 기술 결측"@ko ] .

# R6 — 분류 미완 (Warning). F1·F2 속성 IRI는 STEP 4 명세와 맞춘다.
fdesh:ClassificationShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset ;
  sh:property [
    sh:path dcat:theme ; sh:minCount 1 ; sh:class skos:Concept ;
    sh:severity sh:Warning ; fde:fixRoute "class4" ;
    sh:message "분류 미완 Warning — f1·f2 미선택 (카탈로그 탐색 불가)"@ko ] ;
  sh:property [
    sh:path fde:dataForm ; sh:minCount 1 ; sh:class skos:Concept ;
    sh:severity sh:Warning ; fde:fixRoute "class4" ;
    sh:message "분류 미완 Warning — f1·f2 미선택 (카탈로그 탐색 불가)"@ko ] .

# 프로버넌스 (목업의 ActivityShape)
fdesh:DatasetProvenanceShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset ;
  sh:property [
    sh:path prov:wasGeneratedBy ; sh:minCount 1 ; sh:nodeKind sh:IRI ; sh:class prov:Activity ;
    sh:severity sh:Violation ;
    sh:message "생성 Activity 결측"@ko ] .

fdesh:ActivityShape a sh:NodeShape ;
  sh:targetClass prov:Activity ;
  sh:property [ sh:path prov:wasAssociatedWith ; sh:minCount 1 ; sh:nodeKind sh:IRI ;
                sh:severity sh:Violation ; sh:message "Activity 수행 주체 결측"@ko ] ;
  sh:property [ sh:path prov:endedAtTime ; sh:maxCount 1 ; sh:datatype xsd:dateTime ;
                sh:severity sh:Violation ; sh:message "endedAtTime 형식 오류"@ko ] .

# NoEmptyLiteralShape — 빈 리터럴 금지 (SHACL-SPARQL)
fdesh:NoEmptyLiteralShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset , dcat:Distribution , dcat:DataService , prov:Activity , foaf:Agent ;
  sh:severity sh:Violation ; fde:fixRoute "emptyLit" ;
  sh:sparql [
    sh:message "NoEmptyLiteralShape — 빈 리터럴 금지 (sh:minLength 1)"@ko ;
    sh:select """
      SELECT $this ?path ?value WHERE {
        $this ?path ?value .
        FILTER(isLiteral(?value) && STRLEN(STR(?value)) = 0)
      }""" ] .

# NoDanglingRefShape — 참조 IRI 타입 선언 필수 (SHACL-SPARQL)
fdesh:NoDanglingRefShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset , dcat:Distribution , prov:Activity ;
  sh:severity sh:Violation ;
  sh:sparql [
    sh:message "NoDanglingRefShape — 참조 IRI 타입 선언 필수"@ko ;
    sh:prefixes fdesh: ;
    sh:select """
      SELECT $this ?path ?value WHERE {
        $this ?path ?value .
        FILTER(?path IN (dcterms:publisher, dcat:distribution, prov:wasGeneratedBy, prov:wasAssociatedWith))
        FILTER(isIRI(?value))
        FILTER NOT EXISTS { ?value a ?anyType }
      }""" ] .
```

발행 프로파일 전용 셰이프 (별도 파일, `mode = publish` 실행에만 합쳐서 로드):

```turtle
# R1 · 게이트 0 ④ — 임시 ID 잔존 금지
fdesh:MintedIdShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset , dcat:Distribution , prov:Activity ;
  sh:nodeKind sh:IRI ;
  sh:not [ sh:pattern "(-신규|-draft-|-미민팅-)" ] ;
  sh:severity sh:Violation ; fde:fixRoute "mint" ;
  sh:message "게이트 0 ④ — 민팅 미등록 (fallback 발급 금지)"@ko .

# N2SFZoneShape — 등급과 발행 구역 일치 (속성 IRI는 STEP 4·관리 명세와 맞춘다)
fdesh:N2SFZoneShape a sh:NodeShape ;
  sh:targetClass dcat:Dataset ;
  sh:property [ sh:path fde:n2sfGrade ; sh:maxCount 1 ;
                sh:in ( fde:N2SF-C fde:N2SF-S fde:N2SF-O ) ;
                sh:severity sh:Violation ; fde:fixRoute "class4" ;
                sh:message "N2SF 등급 값 오류"@ko ] ;
  sh:property [ sh:path fde:n2sfGrade ; sh:minCount 1 ;
                sh:severity sh:Warning ; fde:fixRoute "class4" ;
                sh:message "N2SF 등급 미지정 — S로 간주"@ko ] ;
  sh:sparql [
    sh:message "N2SFZoneShape — C 등급은 통제구역 전용"@ko ;
    sh:prefixes fdesh: ;
    sh:select """
      SELECT $this WHERE { $this fde:n2sfGrade fde:N2SF-C ; fde:publishZone fde:ZoneOpen . }""" ] .
```

**대응표**

| 목업 규칙 | 실제 구현 | 구현 수단 |
|---|---|---|
| 게이트 0 ① 파서 통과 | 직렬화 후 재파싱 | 코드 (rdflib) |
| 게이트 0 ② prefix 완결 | 미선언 prefix 탐지 | 코드 |
| 게이트 0 ③ 인코딩 UTF-8 | 바이트 디코딩 검사 | 코드 |
| 게이트 0 ④ / R1 | `fdesh:MintedIdShape` + 민팅 레지스트리 조회 | SHACL (발행 프로파일) + 코드 |
| 게이트 0 ⑤ / R2 | `fdesh:DatasetIdentityShape` (존재) + 요청 대상과 제목 대조 | SHACL + 코드 |
| PublisherShape / R3 | `fdesh:PublisherShape`, `fdesh:AgentShape` | SHACL Core |
| MediaTypePlacementShape / R4 | `fdesh:MediaTypePlacementShape`, `fdesh:FileDatasetDistributionShape`, `fdesh:DistributionShape` | SHACL Core |
| 스트림 필수 / R5 | `fdesh:StreamServiceShape` | SHACL Core |
| 분류 미완 Warning / R6 | `fdesh:ClassificationShape` | SHACL Core (`sh:Warning`) |
| NoEmptyLiteralShape | `fdesh:NoEmptyLiteralShape` | SHACL-SPARQL |
| NoDanglingRefShape | `fdesh:NoDanglingRefShape` | SHACL-SPARQL |
| ActivityShape | `fdesh:DatasetProvenanceShape`, `fdesh:ActivityShape` | SHACL Core |
| N2SFZoneShape | `fdesh:N2SFZoneShape` | SHACL Core + SPARQL (발행 프로파일) |
| 리니지 미결 경고 | 프로세스 수준 게이트 + 면제(waiver) 레코드. 그래프 수준으로는 `prov:wasDerivedFrom` 부재를 `sh:Warning`으로 추가 가능 (`fixRoute "lineage5"`) | 코드 + 선택적 SHACL |
| `prov:wasAttributedTo 외부 출처`, `dcterms:conformsTo (좌표계) 미선언`, `accrualPeriodicity`, `rai:dataBiases` | 가이드라인 프로파일 셰이프로 추가 (Warning 또는 버전별 Violation) | SHACL Core |
| 접합부 계약 (`spdx:checksum`) | 레이크 프로파일러가 올린 체크섬과 배포본 메타 대조 | 코드 (SHACL 범위 밖) |

**설계 시 결정해야 할 점**

- 목업은 스트림을 `dcat:Dataset`과 `dcat:DataService` 두 타입으로 동시에 선언한다 (logic.js 172). DCAT 3 관점에서 유지할지, `dcat:DataService` + `dcat:servesDataset`로 분리할지 정해야 하며 셰이프의 `sh:targetClass`가 그 결정에 따른다.
- 목업의 `dcat:temporalResolution`은 타입 없는 리터럴이다 (logic.js 202). 실제 제품은 `xsd:duration`으로 내보내야 위 셰이프를 통과한다.
- 목업 ID는 상대 IRI (`<DST-000961>`) 로 출력된다. 실제 제품은 절대 IRI (예: `https://catalog.molit.go.kr/id/dataset/DST-000961`) 를 민팅하고 `MintedIdShape`에 패턴을 추가한다. STEP 7 화면의 JSON Schema 예시는 `"^DST-[0-9]{6}$"` 를 쓴다.
- `dcterms:format`을 목업은 데이터셋 노드에 붙인다 (logic.js 200). Distribution으로 옮기는 것이 MediaTypePlacement 원칙과 일관된다.
- `NoDanglingRefShape`의 대상 술어 범위 (IANA mediaType IRI, 에이전트 IRI, 엔드포인트 IRI를 포함할지).
- 셰이프 버전 표기 통일 (목업은 `rs-2.1`, `v1.2`, `v3.2`가 혼재).

### 8.3 위반 → 수정 경로 매핑

- 셰이프(또는 property shape)에 주석 속성 `fde:fixRoute "<key>"`를 달고, 서버의 `fix_route` 테이블이 키를 화면 위치로 해석한다. 목업의 `FIX_ROUTE` 8개 키를 초기 데이터로 쓴다.
- 결과 행 응답에 `fixRoute: { key, step, label, deepLink }`를 포함한다. 매핑이 없으면 목업처럼 `라우팅 미선언`을 표시하되, 셰이프 등록 시점에 CI 검사로 누락을 막는다.
- 딥링크 예: `/studio/processes/{pid}/steps/3?dataset={datasetId}&tab=2&focus=publisher&fixRun={runId}&fixResult={resultId}`. 프런트는 `focus` 필드를 2.4초 강조하고, `fixRun`이 있으면 복귀 배너 (`⚠ STEP 6 위반 수정 중 — {shape} · 보강 후 검증으로 복귀하세요 (수정 시 검증 결과 자동 무효화)`) 를 띄운다.
- 모든 route에 강조 대상 UI 앵커를 실제로 만든다 (목업은 publisher, mediaType 2개뿐).
- 재검증 시 서버가 이전 실행과 결과를 비교해 해소된 위반(`resolved_in_run_id`)을 기록하고, 목업의 actLog 문구 `재검증 — 직전 위반 {shape} 보강 (원인 단계 STEP {n}) · 통과 {p}/{t}` 를 자동 생성한다.

### 8.4 무효화 (stale) 규칙

- 서버가 판정한다. 최신 검증 실행의 데이터셋별 `canonical_checksum`과 현재 정본 그래프의 체크섬이 다르면 stale.
- stale 유발 이벤트: 조합 변경(초기화), STEP 3 승인/승인 해제, STEP 4 분류 확정/해제, STEP 5 연계 변경, 셰이프 버전 변경(배치 재검증 트리거).
- stale이면 STEP 7 진입 잠금 (`재검증 필요 — 정본이 변경되었습니다. STEP 6 검증을 다시 실행하세요`), STEP 7~8 결과 폐기.
- 발행 모드 전환은 정본 불변이므로 stale이 아니라 프로파일만 바꾼 새 실행으로 처리한다.

### 8.5 데이터 모델 (PostgreSQL)

| 엔터티 | 주요 컬럼 |
|---|---|
| `shapes_graph_version` | `id`, `name`('rs'), `version`('2.1'), `profile`(`draft` \| `publish` \| `guideline`), `turtle`(text), `sha256`, `status`(`draft` \| `active` \| `retired`), `created_by`, `activated_at` |
| `shape_rule` | `id`, `shapes_graph_version_id`, `shape_iri`, `rule_key`, `display_name`, `evaluator`(`gate0` \| `shacl`), `target_class`, `property_path`, `severity`(`Violation` \| `Warning` \| `Info`), `fix_route_key`, `message_template`, `enabled` |
| `fix_route` | `key`, `step`, `tab`, `field_anchor`, `label` |
| `validation_run` | `id`, `process_ids[]`, `mode`(`draft` \| `publish`), `is_simulation`, `sim_fault`, `shapes_graph_version_id`, `status`(`queued` \| `running` \| `done` \| `failed` \| `cancelled`), `triggered_by`, `agent_type`(`person` \| `software`), `on_behalf_of`, `started_at`, `ended_at`, `prov_activity_id`, `lineage_waiver_id`, `previous_run_id`, `pass_count`, `fail_count`, `warning_count` |
| `validation_run_dataset` | `id`, `run_id`, `dataset_id`, `canonical_checksum`, `graph_snapshot_ref`, `gate0_passed`, `shacl_conforms`, `pass`, `violation_count`, `warning_count`, `info_count`, `report_turtle` |
| `validation_result` | `id`, `run_dataset_id`, `rule_id`, `source`(`gate0` \| `shacl`), `severity`, `focus_node`, `result_path`, `value`, `source_shape`, `source_constraint_component`, `message`, `fix_route_key`, `resolved_in_run_id` |
| `lineage_waiver` | `id`, `process_id`, `reason`, `created_by`, `created_at`, `prov_activity_id` |
| `mint_registry` | `id`, `resource_kind`(`DST` \| `SVC` \| `DIST` \| `ACT`), `source_key`, `minted_iri`, `status`, `minted_at`, `minted_by` |
| `batch_revalidation_job` | `id`, `trigger`, `shapes_from`, `shapes_to`, `software_agent`, `on_behalf_of`, `total`, `processed`, `pass`, `warning`, `violation`, `status`, `stage`, `prov_activity_id` |
| `prov_activity` | `id`('ACT-K-…', 'ACT-B-…'), `type`, `agent_id`, `started_at`, `ended_at`, `used[]`, `generated[]`, `note` |

프로세스 상태 뷰: `process_validation_state(process_id, latest_run_id, state, stale, stale_reason, pass_count, fail_count, last_run_at)`.

### 8.6 API 엔드포인트 (FastAPI)

| 메서드 · 경로 | 용도 |
|---|---|
| `POST /api/v1/validation-runs` | 검증 실행. 본문 `{ processIds: [], mode: 'draft'\|'publish', lineageWaiverId?, simulate?: { fault: 'nomint'\|'noorg', datasetId } }`. 리니지 미결이고 면제가 없으면 `409 { code: 'LINEAGE_UNRESOLVED' }`. 성공 `202 { runId }` |
| `GET /api/v1/validation-runs/{runId}` | 상태와 요약 (`status`, `passCount`, `failCount`, `startedAt`, `endedAt`, `shapesVersion`) |
| `GET /api/v1/validation-runs/{runId}/datasets` | 데이터셋 단위 판정 목록 (`pass`, 위반·경고 배열, 각 항목의 `fixRoute`) |
| `GET /api/v1/validation-runs/{runId}/datasets/{datasetId}/report` | `sh:ValidationReport` 원문 (Turtle / JSON-LD) |
| `GET /api/v1/validation-runs/{runId}/gate0` | 게이트 0 ①~⑤ 결과 (데이터셋별) |
| `GET /api/v1/validation-runs/{runId}/events` | 진행 상황 SSE |
| `GET /api/v1/processes/{pid}/validation-state` | `{ state: 'idle'\|'running'\|'done', stale, staleReason, latestRunId, passCount, failCount, lastRunAt }` (STEP 7 잠금 판단용) |
| `POST /api/v1/processes/{pid}/lineage-waivers` | 리니지 미결 사유 기록 `{ reason }` |
| `GET /api/v1/shapes/versions` / `GET /api/v1/shapes/versions/{id}` | 셰이프 세트 목록과 Turtle 원문 |
| `GET /api/v1/shapes/rules` | 규칙 카탈로그 (이름, 심각도, 대상 클래스, 경로, 수정 경로, 평가 주체) |
| `GET /api/v1/fix-routes` | 수정 경로 사전 |
| `GET /api/v1/datasets/{id}/canonical-graph?format=turtle` | 검증에 쓰인 정본 그래프 |
| `GET /api/v1/mint-registry?sourceKey=` / `POST /api/v1/mint-registry` | 민팅 조회와 등록 (관리 평면) |
| `POST /api/v1/batch-revalidations`, `GET …/{id}`, `POST …/{id}/pause`, `POST …/{id}/cancel`, `GET …/{id}/events` | 배치 일괄 재검증 |
| `GET /api/v1/datasets/{id}/joint-contract` | 접합부 계약 점검 (식별자, 체크섬 대조) |

### 8.7 프런트엔드 (React) 요구

- 실행 상태 3종 (`idle` / `running` / `done`) + `stale` 배지. 실행 중에는 SSE로 데이터셋별 진행 표시.
- 결과 패널: 데이터셋 카드, 위반(적색)과 경고(주황) 행, `[수정하러 이동]` 딥링크.
- 탭 ③의 KPI와 위반 표는 같은 실행 결과에서 파생한다 (목업처럼 별도 고정 데이터를 두지 않는다).
- 검수 시뮬레이션은 QA 권한 전용 기능으로 분리하고, 시뮬레이션 실행은 `is_simulation = true`로 기록해 STEP 7 잠금 해제에 쓰지 않는다 (또는 산출물에 `_SIM` 접미).
- 발행 모드 토글은 검증 화면에도 노출한다 (목업은 STEP 7에만 있어 검증 화면에서 ④ 실패 원인을 바꿀 수 없다).

---

## 부록 A. 마크업 1670~1917 (`show6` 블록 = 화면상 STEP 7 직렬화) 명세

지시받은 라인 범위의 실제 내용이다. 검증과 맞닿는 부분 위주로 정리하되 컨트롤은 전부 적는다.

### A.1 목적

검증을 통과한 데이터셋만 대상으로, 단일 정본에서 4개 표현(Turtle, JSON-LD, 자연어 문장화, JSON 스키마)을 생성하고 파생 자가검증 4검사를 거쳐 파일로 제공한다.

### A.2 화면 구성과 문구

1. 제목: `STEP 7: 직렬화 · 발행 포맷 변환 + 파생 자가검증`
2. 흐름 안내: 2.7.1과 같은 문구.
3. 검증 요약 배너 (조건 `cvBannerOn` = `v7State === 'done'`): `STEP 6 검증 — 통과 {n}건 · 미통과 {m}건` + (미통과가 있으면 ` (미통과분은 변환 제외)`). 미통과가 있으면 주황, 없으면 녹색.
4. 배지 (조건 `simOn`): `⚠ 검수 시뮬레이션 중 — 산출물은 검수용 (파일명 _SIM 접미)`
5. 원칙 배지: `원칙: sLLM은 RDF를 직접 생성하지 않는다 — JSON 산출 후 결정적 후처리로 Turtle 변환`
6. 접이식 카드 `Turtle 정본 × AI — 3방향 활용 경로` (`tai3Toggle`, 캐럿 `펼치기 ▾` / `접기 ▴`):
   - `입력 — AI가 읽을 때` `Turtle 정본 → 템플릿 문장화 (0.57×) → 임베딩 → 벡터DB①` / `변환은 결정적 템플릿 — sLLM 답변의 근거 트리플 역참조 가능` / 링크 `자산 매트릭스 마트 셀 →` (`goMartCell`)
   - `출력 — AI가 쓸 때` `sLLM → 스키마 JSON → 결정적 변환 → Turtle 후보 → SHACL → 관리자 승인` / `4중 방어: 문법을 확률 모델에 맡기지 않는다` / 링크 `STEP 6 sLLM 보정 제안 →` (`goStep6`)
   - `거버넌스 — AI를 관리할 때` `학습셋·모델·편향 명세(rai:dataBiases) → Turtle 정본에 등록 → 리니지 질의` / `"이 모델은 무슨 데이터로 학습했나"가 그래프 질의로 답해진다`
   - 주석: `ⓘ Turtle은 AI의 먹이도 산출물도 아니다 — AI 입력을 만들어내는 원천 · AI 출력을 판정하는 기준 · AI 자산을 기술하는 장부. 확률적인 것과 결정적인 것의 경계선이 Turtle 정본이다.`
7. 직렬화 대상 바: `직렬화 대상:` + 현재 대상 이름 (`serTgtTitle`, 없으면 `(작업 데이터셋 없음)`) + `대상 전환 —` + 데이터셋 버튼들 (`serTgtOpts`, 현재 항목 `✓ ` 접두) + **발행 모드 버튼** (`pubModeToggle`, 3.11) + 주석 (`pubModeNote`).
8. 포맷 카드 4개 (클릭 시 상세 포커스 `fmt` 전환, 체크박스로 선택 `fmts` 토글):

| 카드 | 체크박스 라벨 | 제목 | 설명 | 목적지 배지 | 분량 | 파생 증명 배지 |
|---|---|---|---|---|---|---|
| T | `변환 대상 (정본 · 필수)` (체크 고정, 비활성) | `Turtle (RDF 정본)` | `정본 저장·발행 · SHACL 검증 대상` | `→ 카탈로그 평면 (Fuseki/GraphDB) + LPG 투영 (Neo4j)` | `상대 분량 1.00배` | `파생 증명: 커버리지 100% · 근거 9건 · tpl-v2.3` |
| J | `변환 대상` | `JSON-LD (RDF 직렬화)` | `시스템 간 API — @context 외부 URL 참조` | `→ API 계층` | `상대 분량 2.13배` | 같음 |
| N | `변환 대상` | `자연어 문장화` | `sLLM RAG 입력` | `→ 마트 벡터DB①·② (→ sLLM)` | `상대 분량 0.57배 · 마트 적재 위치: 벡터DB①` + 링크 `데이터 패브릭 관리에서 보기 →` | `파생 증명: 커버리지 100% (5/5) · 근거 9건 · tpl-v2.3 — 100% 미만 시 적색·발행 차단` |
| P | `변환 대상` | `순수 JSON + 스키마` | `sLLM 출력 (제약 디코딩)` | `→ sLLM 생성 결과 수신 → 결정적 후처리로 Turtle 변환` | `상대 분량 — · 스키마 레지스트리 v3.2 참조` | `파생 증명: 커버리지 100% · 근거 9건 · tpl-v2.3` |

   기본 선택 `fmts = { t: true, j: true, n: true, p: false }` (logic.js 399).

9. 레이크 안내: `🔒 레이크는 목적지가 아님 — 접합부 계약: 식별자 + checksum + 프로파일 통계(결측률·포맷 위반률·코드값 분포·라벨 일관성) — 레이크 측 프로파일러 잡이 통계를 메타 평면으로 밀어 올리며(↑), 데이터 본체는 여전히 이동하지 않음 · 스트림 파생 이벤트의 프로파일(이벤트 건수 분포·미확정 플래그 비율)도 동일 계약으로 유입 (STEP 7에서 점검)` (링크 `goStep7`)
10. 접이식 카드 `스키마 레지스트리 · AI 소비 번들 export` + `— SHACL 컴파일 · 학습데이터 출구` (`schBunToggle`):
    - `스키마 레지스트리` + 배지 `SHACL → JSON Schema 결정적 컴파일`
      - `스키마의 폭 = sLLM이 자동화할 수 있는 메타데이터의 폭 — SHACL이 요구하는데 스키마에 없는 필드는 sLLM이 못 채웁니다. sLLM 제약 디코딩 흐름의 「스키마 JSON」 노드가 이 레지스트리를 참조 →`
      - `schema v3.2` `← DatasetShape v3.2에서 컴파일 · 2026-08-21 · ACT-SCH-0044`
      - `schema v3.2-dist` `← DistributionShape v3.2 · ACT-SCH-0045`
      - `schema v1.0-stream` `← StreamServiceShape v1.0 · ACT-SCH-0046`
      - `매핑 예: sh:minCount 1 → required[] · sh:datatype xsd:string → "type": "string"`
      - `✓ 검수: SHACL 필수 속성 목록과 JSON Schema required 목록 1:1 일치`
    - `AI 소비 번들 export` + 배지 `4번째 목적지 — 학습데이터 출구`
      - `정렬 보증된 (Turtle ↔ 문장화) 쌍 — sLLM 파인튜닝 자산 · 범정부 AI 플랫폼 데이터 상품`
      - `① 학습쌍 JSONL` `{"graph":"<Turtle>","text":"…차량(58로****)…","sources":["T-01","ACT-CALC-0821"]}` `— 파생 증명 통과분만`
      - `② RAG 청크 인덱스` `{문장, 임베딩 대상, 근거 리소스 ID[], 데이터셋 URI} — 청크→그래프 점프용`
      - `③ LPG 투영 매핑 명세` `Turtle → Neo4j 노드/엣지 변환 규칙 요약`
      - `export 게이트 3조건: ① 정합 검증(파생 증명 100% + 게이트 0 + SHACL) 통과 ② 이벤트 데이터셋은 개방 구역 산출(비식별)만 — 통제 산출 export 불가 (N2SF 게이트) ③ 승인·발행 완료분만 · 미리보기의 차량번호는 마스킹(58로****)만 허용`
11. 2단 영역. 오른쪽 `변환 결과 상세 — {{ fmtTitle }}` (`Turtle (RDF 정본)` / `JSON-LD` / `자연어 문장화` / `순수 JSON + 스키마`):

    Turtle 미리보기 (원문, 바인딩 포함):
    ```
    @prefix dcat: <http://www.w3.org/ns/dcat#> .
    <{{ ds3Id }}> a dcat:Dataset ;
      dcterms:title "{{ ds3Title }}"@ko ;
      dcat:distribution <{{ ds3DistId }}> ;
      prov:wasGeneratedBy <ACT-신규> .
    <{{ ds3DistId }}> a dcat:Distribution ;
      dcat:mediaType "{{ ds3Media }}" ;
      spdx:checksum <CHK-발급 대기> .
    ```
    설명: `정본 직렬화 — SHACL 검증 대상이며 트리플스토어(Fuseki/GraphDB)에 저장되고 Neo4j로 LPG 투영됩니다.` / `검증: DatasetShape · DistributionShape 적용 · 인코딩: UTF-8 · prefix 12종`

    JSON-LD 미리보기 (원문):
    ```
    {
      "@context": "https://catalog.molit.go.kr/context/v3.jsonld",
      "@id": "{{ ds3Id }}",
      "@type": "dcat:Dataset",
      "dcterms:title": {"@value": "{{ ds3Title }}", "@language": "ko"},
      "dcat:distribution": {"@id": "{{ ds3DistId }}"},
      "prov:wasGeneratedBy": {"@id": "ACT-신규"}
    }
    ```
    설명: `시스템 간 API 응답용 — @context는 외부 URL 참조로 본문 경량화.` / `목적지: API 계층 (REST/GraphQL) · 분량: Turtle 대비 2.13배`

    문장화 패널: `파생 증명 (Derivation Proof) — 시나리오 데모: 과속 이벤트 EVT-0821` + `문장 ↔ 근거 리소스 클릭 역참조 (양방향)` + 배지 `커버리지 100% (5/5) · 근거 리소스 9건 · 렌더러 tpl-v2.3`. 좌측 `문장 (txt는 이 배열의 뷰 — 정본은 {문장, 근거 리소스 ID[]})`, 우측 `근거 리소스 (트리플 + prov:Activity + 참조 데이터셋)`. 하단: 배지 `가이드라인 부록4 데이터 카드 규격 준수 — 자동 생성` + `섹션: 요약·리니지(3원천 조인)·비식별 조치(마스킹 규칙 v1.2)·편향성(rai:dataBiases — 인식 모델 야간 성능 저하)·라이선스 — 모든 서술이 근거 리소스를 가짐 · 데이터·문서 동시 현행화는 파생 구조상 항상 충족 (4종 표현이 단일 정본에서 렌더링).` / `적재 위치: 마트 벡터DB①·② 자산 뷰에서 보기 → · 분량: 0.57배 · 커버리지 100% 미만이면 배지 적색 + 발행 차단`

    JSON 스키마 미리보기 (원문):
    ```
    // JSON Schema (제약 디코딩용)
    {
      "type": "object",
      "required": ["identifier", "title", "mediaType"],
      "properties": {
        "identifier": {"pattern": "^DST-[0-9]{6}$"},
        "mediaType": {"enum": ["application/vnd.apache.parquet", …]}
      }
    }
    ```
    설명: `sLLM 출력 수신용 — 스키마 제약 디코딩으로 형식을 강제하고, 결정적 후처리로 Turtle 변환.` / `원칙: sLLM은 RDF를 직접 생성하지 않음 · 후처리 규칙 rs-2.1 적용`

12. 왼쪽 열:
    - `선택된 표현 {{ selCount }}/4:` + `selSummary` (`Turtle 정본` · `JSON-LD` · `문장화` · `JSON+스키마` 중 선택분)
    - 버튼 `convertBtnLabel`: `변환 실행 (통과 {n}건 × 4포맷)` / `⟳ 변환 중…`. 통과 0건이면 회색 `cursor:not-allowed`.
    - 실행 중 상자: `⟳ 변환 실행 중 — {{ selCount }}개 포맷` / 진행 막대 62% 고정 / `Turtle 정본 생성 → 결정적 후처리 → 파생 표현 재생성 · prov:Activity 기록 중`
    - 완료 상자: `✓ 변환 완료 요약 — {{ selCount }}개 포맷` / 버튼 `↺ 결과 지우기` (title `결과를 지우고 다시 변환`) / `Turtle {{ comboCount }}건 (정본)` / `JSON-LD {{ comboCount }}건` / `문장화 {{ comboCount }}건` / `JSON 스키마 {{ comboCount }}종` / `소요시간 4초 (작업 조합 기준)` / `검증 범위: SHACL은 Turtle 정본 1개에만 적용 — 파생 표현 {{ selCount }}개 중 나머지는 정본 통과 후 자동 재생성되므로 별도 검증이 없습니다.`
    - `결과 파일 저장 · 다운로드` + `— 검증·자가검증 통과분만 존재`
      - 통과 그룹 행 (`cvGroups`): 이름 / 배지 `STEP 6 검증 ✓` / 자가검증 배지 (`파생 자가검증 ✓ 4/4` / `파생 자가검증 실패 — 렌더러 결함, 산출물 폐기됨` / `파생 자가검증 — 변환 시 자동 실행`) / `세트 #{checksum}`
      - 제외 행 (`cvExcluded`): 이름 / `검증 미통과 — 제외 (파일 미생성)`
      - 파일 행 (`cvFiles`): 태그 (`TTL` / `JSON-LD` / `문장화` / `스키마`), 파일명, 크기 (`2 KB` / `4 KB` / `1 KB` / `1 KB` 고정), 다운로드 `⤓`
      - 버튼 `⤓ 전체 다운로드 ({n}개 파일 — 검증·자가검증 통과분만)`
      - `저장 위치: 레이크 통제구역 s3://lake-ctrl/catalog/serialized/ 자동 기록 · 다운로드는 로컬 사본 · 산출물 저장소(데이터 카탈로그)에서 프로세스별 관리 →` (링크 `goCatalog`)
    - 버튼 `STEP 8 가이드라인 준수 진단 · 발행 승인으로 →` (`goStep8`)

### A.3 동작

| 컨트롤 | 결과 |
|---|---|
| `tai3Toggle`, `schBunToggle` | `go({ tai3: !tai3 })`, `go({ schBun: !schBun })` |
| `goMartCell` | `go({ plane: 'assets', fabTab: 1, cell: 'martC' })` |
| `goStep6` | `go({ plane: 'studio', step: 6 })` (검증 화면. `pipe`는 바꾸지 않음) |
| `goStep7` | `go({ plane: 'studio', step: 7 })` (자기 자신. 부록 B-7) |
| `so.pick` | `go({ serTgt: i, ds: i, ds3: i })` |
| `pubModeToggle` | 3.11 |
| `setFmtT/J/N/P` | `go({ fmt: 't'\|'j'\|'n'\|'p' })` |
| `togJ/N/P` | `e.stopPropagation()` 후 `go({ fmts: { ...sel, x: !sel.x } })`. T는 해제 불가 |
| `dp.pick`, `dr.pick` | `go({ dpS, dpR })`. 문장 선택 시 근거 리소스 강조, 리소스 선택 시 인용 문장 강조 |
| `convertRun` (logic.js 2912~2940) | 통과분 = `combo` 중 `v6Results`에서 `pass`인 것. 0건이면 토스트 `✕ 변환 대상 없음 — STEP 6 검증 통과 데이터셋이 없습니다. 검증을 먼저 실행하거나 STEP 3에서 결측을 보강하세요` (3200ms). 있으면 `convertState = 'run'`, `convertTimeIso = ISO 19자`, 토스트 `⟳ 변환 실행 — 직렬화 · 통과 {n}건 × 4포맷 (prov:Activity 기록)`. 1600ms 후 `svResults = passed.map(selfVerify)`, `convertState = 'done'`, `convertTime`. 전부 통과면 토스트 `✓ 변환 완료 — 통과 {n}건 × 4포맷 · 파생 자가검증 4/4 통과 · 프로세스 종료 저장됨`, 아니면 `⚠ 파생 자가검증 실패 {k}건 — 렌더러 결함, 해당 산출물 폐기됨`. actLog `직렬화·포맷 변환 실행 — 통과 {n}건 × 4포맷 · 파생 자가검증 {ok}/{total}`. 전부 통과면 `_saveProc(true)` (프로세스 종료 저장) + actLog `프로세스 종료 저장 — {procName} (STEP 7 변환 완료)` |
| `convertReset` | `convertState = null`, 토스트 `↺ 변환 결과를 지웠습니다 — [변환 실행]으로 다시 생성하세요` (2600ms) |
| `cf.dl` | Blob 다운로드 (`mkContentFor(item, fmt)`), 토스트 `⤓ {파일명} 다운로드 — 레이크 정본은 유지, 로컬 사본 생성 (prov:Activity 기록 — 데모에서는 미기록)` (2800ms) |
| `cvDlAll` | 350ms 간격 순차 다운로드, `_procSave()`, 토스트 `⤓ {n}개 파일 다운로드 · 「{procName}」 완료 — 프로세스 목록에 저장 확정 (prov:Activity 기록 — 데모에서는 미기록)` (3400ms) |
| `goStep8` | `go({ plane: 'studio', step: 8 })` (`stepGate(8)`: 변환 완료 필요) |

파일 생성 규칙 (logic.js 2708~2725): 대상 = 검증 통과 그리고 자가검증 미실패 데이터셋. 파일명 = 이름에서 `[^가-힣a-zA-Z0-9]+`를 `_`로 바꾸고 40자로 자른 뒤 (`simMode`면 `_SIM`) + 확장자 `.ttl` (`text/turtle`), `.jsonld` (`application/ld+json`), `_문장화.txt` (`text/plain`), `_schema.json` (`application/json`). 세트 체크섬 = `hash32hex(JSON.stringify(canonical))` (FNV-1a 32비트).

파생 자가검증 `selfVerify` (logic.js 291~307): `① TTL 재파싱`, `② prefix 완결`, `③ UTF-8 정상`, `④ TTL↔JSON-LD 트리플 일치`. 예외 시 `렌더러 예외: {message}`.

### A.4 고정 데이터: 파생 증명 (logic.js 2656~2673)

문장과 근거:

1. `이 과속 이벤트는 CCTV 차량 인식 관측에서 판정되었다.` → `T-01`, `OBS-0821-cctv`
2. `소나기(강수 12mm/h, KMA 지점 401)로 감속 규정(비 20%)이 적용된 상태에서 판정되었다.` → `OBS-KMA-401-0930`, `DST-법정감속규정`, `ACT-CALC-0821`
3. `적용 규정속도는 64km/h였다 (= 기본 80km/h × 0.8).` → `T-04`, `DST-도로대장`, `ACT-CALC-0821`
4. `관측 속도 100km/h — 초과 36km/h로 범칙 2구간·심각도 +1이 배정되었다.` → `T-05`, `ACT-CALC-0821`
5. `차량번호는 개방 산출에서 마스킹(58로****) 처리되었다.` → `ACT-MASK-0821`

근거 리소스: `T-01` `트리플 — a :과속이벤트` / `T-04` `트리플 — :적용규정속도 64` / `T-05` `트리플 — :심각도 2` / `OBS-0821-cctv` `cctv.vehicle.det.v1 관측` / `OBS-KMA-401-0930` `KMA 지점 401 기상 관측` / `DST-도로대장` `참조 데이터셋 v2.4` / `DST-법정감속규정` `참조 데이터셋 v1.0` / `ACT-CALC-0821` `계산 prov:Activity` / `ACT-MASK-0821` `마스킹 prov:Activity (규칙 v1.2)`

### A.5 상태 키

`fmt` (`'t'|'j'|'n'|'p'`, 기본 `'t'`), `fmts` (`{t,j,n,p}`), `serTgt` (number), `pubMode`, `convertState` (`null|'run'|'done'`), `convertTime`, `convertTimeIso`, `svResults` (`Array<{ n, pass, checks: [name, ok][], checksum }>`), `tai3`, `schBun`, `dpS` (number|null), `dpR` (string|null).

### A.6 시뮬레이션 vs 실제

- 실제: `mkContentFor` 4포맷 문자열 생성, Blob 다운로드, 세트 체크섬, 자가검증 4검사(정규식 수준), 검증 통과분 필터.
- 흉내: 상세 미리보기 패널(11번)은 실제 산출물이 아니라 STEP 3 바인딩(`ds3Id` = `DST-신규 (확정 시 발급)` 등)을 쓴 고정 템플릿이다. `<ACT-신규>`, `<CHK-발급 대기>`, 리터럴 `dcat:mediaType`이 들어 있어 게이트 0 ④와 MediaTypePlacement 원칙에 어긋난다. 파생 증명 커버리지, 분량 배수, 파일 크기, 소요시간, 스키마 레지스트리, export 번들, S3 저장은 모두 고정 문구다. 포맷 선택(`fmts`)은 파일 생성에 반영되지 않는다 (항상 4포맷).

---

## 부록 B. 목업 결함·불일치 목록 (재구현 시 그대로 옮기지 말 것)

| # | 내용 | 근거 |
|---|---|---|
| B-1 | 검증 화면에서 프로세스를 호출해도 토스트가 `업무 B(진단)`으로 나온다 | logic.js 1037, 1042는 `step === 7` 비교, 1050은 6 전달 |
| B-2 | 프로세스 호출 시 `v7State`만 지우고 `v6Results`, `v6Stale`은 남는다. 프로세스 스냅숏에 검증 결과가 없다 | 1036, 1041, 920 |
| B-3 | `검증 대상 = buildTriples 출력` 문구와 달리 `validateDs`는 `buildCanonical` 객체만 본다 | 309~322 |
| B-4 | STEP 3 입력 변경(승인 해제), STEP 4 분류, STEP 5 연계 변경이 검증 결과를 무효화하지 않는다 | 2875, 2879, 2442 |
| B-5 | 탭 ③의 통과/Warning/Violation 수치와 위반 표가 실제 판정(`v6Results`)과 무관하다 | 1554~1561, 1587~1588, 375 |
| B-6 | `fixField` 강조는 publisher와 mediaType 2종만 구현. `stream3`는 강조 요소가 스트림에서 숨겨져 보이지 않고, 스트림 속성 수정 UI 자체가 없다 | 2893~2894, 마크업 591~605 |
| B-7 | 재편 전 번호가 남은 문구와 링크: STEP 7 화면의 `STEP 7에서 점검` (자기 자신으로 이동), 마크업 659 `StreamServiceShape(STEP 7)`, 3614 `STEP 7 발행에 등급-구역 일치 게이트` | 마크업 1751, 659, 3614 |
| B-8 | 게이트 0 ④의 이름은 패턴 검사지만 실제로는 `MINT_MAP` 등록 여부만 본다. 초안 모드는 ID에 `-draft-`가 있어도 `통과` | 2742~2751 |
| B-9 | 게이트 0 ⑤ 패널은 현재 커서 1건만 검사하고 요약 배지에 반영되지 않는다. 이름에 큰따옴표가 있으면 이스케이프 때문에 오탐 실패 | 2728~2731, 2751 |
| B-10 | `simSet`은 `v6Stale`만 켜고 STEP 7~8 결과는 그대로 둔다 (`invalidateDownstream`과 불일치) | 2833 |
| B-11 | `hash6`은 문자 순서와 무관한 합 해시라 초안 ID 충돌 가능 | 139 |
| B-12 | 셰이프 세트 버전 표기 혼재: `rs-2.1`, `v1.2`, `v3.2`, `DatasetShape 외 4종`과 평면 B의 7종 목록 | 마크업 2052, 2216, 1764, 2584 |
| B-13 | 실행 도중(`v7State = 'run'`) 스냅숏이 저장된 뒤 새로고침하면 실행 버튼이 영구히 `⟳ 실행 중…`에 머물 수 있다 | 1657, 91~103 |
| B-14 | STEP 7 변환 요약의 건수는 통과 건수가 아니라 `comboCount`를 쓰고, 포맷 선택과 무관하게 4포맷 파일이 생성된다 | 마크업 1867~1870, logic.js 2708~2725 |
| B-15 | 발행 모드 토글이 STEP 7 화면에만 있어, 검증 화면에서는 ④ 실패를 유발하거나 해제할 수 없다 | 마크업 1714 |
