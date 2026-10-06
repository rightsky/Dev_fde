# STEP 8 기능 명세: 가이드라인 준수 진단 보고서 (업무 B)

- 분석 대상: `src/markup.html` 2278~2426행, `src/logic.js` 중 해당 바인딩 정의부
- 목적: 목업을 FastAPI + PostgreSQL + rdflib/pySHACL 백엔드와 React 프런트엔드로 재구축하기 위한 역설계 명세
- 표기 규칙: 화면 문구와 메시지는 원문 그대로 인용한다. `{…}` 는 런타임 치환 값이다. 행 번호는 별도 표기가 없으면 `logic.js` 기준이다.

> **가장 먼저 알아야 할 사실**
> 목업에는 "80항목"의 개별 목록이 존재하지 않는다. 항목 id, 항목명, 항목별 판정 로직은 `markup.html` 과 `logic.js` 어디에도 없다. 존재하는 것은 (1) 6개 영역의 하드코딩 집계값, (2) 판정 방식 3종의 하드코딩 건수, (3) 예시 문장 3개, (4) 미흡 요약 카드 3장, (5) 조치 로드맵 6행뿐이다. 실제 규칙 엔진을 만들려면 80항목 원문을 가이드라인 문서에서 별도로 시드해야 한다. 본 문서 4장은 목업에 실재하는 값을 빠짐없이 옮겼고, 8장은 그 틀에 맞춘 구현 제안이다.

---

## 1. 화면 목적

1. 8단계 워크플로의 마지막 단계. 화면 제목은 `STEP 8: 가이드라인 준수 진단 보고서`, 배지는 `업무 B — 독립 진단 업무`.
2. 진단 기준은 화면 문구상 `행안부 「공공데이터의 AI 친화적 관리 가이드라인 v1.1」 80항목 자가진단`.
3. 설계 의도(문구 그대로): `설문형이 아닌 증거 리졸버: "적정"이라는 주장이 아니라 증거가 판정의 본체입니다.` 즉 항목마다 판정 근거(SHACL 결과, 프로파일 통계, 첨부 증빙과 서명)를 연결해 보여 주는 화면이다.
4. 부수 기능
   - 저장된 프로세스를 하나 또는 여러 개 호출해 그 데이터셋 합집합을 진단 대상으로 삼는다.
   - 진단이 끝나면 현재 프로세스를 "종료"로 확정 저장한다(프로세스 종료 확정).
   - 미흡 항목 요약, 조치 우선순위 로드맵, 개선 시뮬레이션, PDF 내보내기(버튼만 있음)를 제공한다.
5. 사이드바 단계 라벨은 `가이드라인 준수 진단` (377행 `labels[7]`).

---

## 2. 화면 구성 (위에서 아래 순)

표시 조건: `show8 = s.plane === 'studio' && s.step === 8` (1409행). 컨테이너 최대 폭 1120px.

### 2.1 제목 줄 (markup 2281)

- 텍스트: `STEP 8: 가이드라인 준수 진단 보고서`
- 배지(검정 바탕): `업무 B — 독립 진단 업무`

### 2.2 진단 대상 프로세스 호출 바 (markup 2282~2288)

| 요소 | 문구 / 바인딩 |
|---|---|
| 라벨 | `진단 대상 프로세스 호출:` |
| 칩 버튼 목록 | `<sc-for list="{{ taskProcOpts }}" as="tp">` 각 버튼 텍스트 `{{ tp.name }}`, 클릭 `{{ tp.pickB }}`, 스타일 `{{ tp.style }}` |
| 안내문 | `— 클릭으로 복수 선택 가능 · 선택한 프로세스들의 데이터셋 합집합이 업무(B) 진단 대상이 됩니다 · 다른 프로세스에 영향 없음` (`복수 선택`, `합집합` 굵게) |

칩 표시 규칙(1020~1055행)
- 목록 = 저장된 프로세스(`s.procList`) 전부의 `name` + (현재 프로세스 이름 `curName` 이 저장 목록에 없으면) `{curName} (진행 중)` 1건.
- 선택 상태인 칩은 이름 앞에 `✓ ` 를 붙이고 검정 바탕(`background:#1F2430;color:#fff`), 미선택은 흰 바탕 회색 테두리.
- 선택 집합 `curSel` = `s.taskProcSel` (비어 있지 않으면) / 아니면 `s.procName.split(' + ')` / 아니면 `[curName]`.

### 2.3 상태 및 실행 바 (markup 2289~2293)

| 요소 | 값 (1613~1616행) |
|---|---|
| 상태 배지 `{{ v8StateLabel }}` | 대기: `대기 — 진단 미실행` (회색) / 실행 중: `⟳ 진단 실행 중…` (파랑) / 완료: `✓ 진단 완료 — {s.procName 또는 '현재 프로세스'}` (초록) |
| 안내문 | `프로세스를 호출한 뒤 [진단 실행]을 눌러야 80항목 증거 리졸버 판정이 시작됩니다 — 실행마다 prov:Activity 기록` |
| 실행 버튼 `{{ v8RunLabel }}` | 대기: `▶ 진단 실행 ({combo.length}건)` / 실행 중: `⟳ 실행 중…` (흐린 파랑 `#8fb8d8`) / 완료: `↺ 재진단 실행` |

### 2.4 대기 안내 박스 (markup 2294~2296, `v8Idle` 일 때만)

`진단 대기 중 — {g1ProcName} 조합 {comboCount}건이 대상입니다. [▶ 진단 실행]을 누르면 AUTO-GRAPH · AUTO-PROFILE 자동 판정과 HUMAN-ATTEST 증빙 수집 결과가 표시됩니다.`

- `v8Idle = s.v8State !== 'done' && s.v8State !== 'run'` (1611행)
- `v8State === 'run'` 인 1.4초 동안은 대기 박스도 결과 영역도 표시되지 않는다(빈 화면).

### 2.5 결과 영역 (markup 2297~2423, `v8Done = s.v8State === 'done'` 일 때만)

#### (a) 머리 설명 (2298)
`행안부 「공공데이터의 AI 친화적 관리 가이드라인 v1.1」 80항목 자가진단 결과 — 설문형이 아닌 증거 리졸버: "적정"이라는 주장이 아니라 증거가 판정의 본체입니다.`

#### (b) 2열 카드 행 (2299~2324)

**좌측 카드: 자가진단 — 판정 방식별 집계** (배지 `부록3 공통 34항목 (필수 18 + 권장 16)`)
- 부제: `체크리스트 항목마다 판정 방식 태그 3종 — 유형별 추가 항목도 동일 체계 (다수가 HUMAN-ATTEST)`
- 3개 행

| 태그 | 설명 문구 | 우측 수치 |
|---|---|---|
| `AUTO-GRAPH` (초록) | `카탈로그 그래프 SPARQL/SHACL 질의 자동 판정 — {g1ProcName} {comboCount}건 대상` | `{b8Graph}건 적정` |
| `AUTO-PROFILE` (주황) | `접합부 프로파일 통계 자동 판정` | `4건 중 {b8ProfBad}건 미흡` |
| `HUMAN-ATTEST` (검정) | `증빙 첨부 + 담당자 서명 (서명도 prov:Activity)` | `사람 확인 대기 6건` (고정 문자열) |

- 예시 박스 3줄
  1. `예 (AUTO-GRAPH): "메타데이터 필수 항목 누락 없음" → DatasetShape minCount 통과 · 증거: shape 결과 →` (링크 `증거: shape 결과 →` 클릭 시 `goStep6`)
  2. `예 (AUTO-PROFILE): "결측값 표기 통일" → 결측 표기 패턴 종류 수 = 1 · 증거: 프로파일 지표 — {b8ProfileMsg}` + 배지 `sLLM 보정 제안 연결 — 관리자 승인 필수`
  3. `예 (HUMAN-ATTEST + 자동 증빙): 파생 이벤트의 비식별 조치 → 마스킹 prov:Activity(규칙 v1.2)가 첨부 증빙으로 자동 연결 — 판정은 사람, 증빙 수집은 자동`

**우측 카드: URI 민팅 (채번)** (배지 `발행 시 안정 URI 치환`) 전부 정적 문구
- 부제: `임시 ID가 발행물까지 흘러가면 그래프RAG의 노드 병합이 깨집니다 — 발행 시점에 안정 URI로 치환하고 이후 불변.`
- 행 1: `네임스페이스` `https://catalog.molit.go.kr/id/…` `· 형식` `DST-######` `· 발행 후 불변`
- 행 2: `치환 맵 (prov:Activity 기록)` `DST-신규 → DST-000124`
- 행 3: `채번 대상 확장` `파생 이벤트 데이터셋 · Plan(PLN-######) · 모델 SoftwareAgent(MDL-######) 동일 규칙`
- 각주: `ⓘ 게이트 0의 검사 ④(ID 잔존 — (-신규|-draft-))가 발행 전 최종 방어선 —` + 링크 `STEP 6 게이트 0 →` (`goStep6`)

#### (c) 점수 게이지 + 영역별 충족률 (2325~2357)

**좌측 카드(320px): 반원 게이지**
- SVG `viewBox="0 0 200 120"`, 배경 호 `M 20 110 A 80 80 0 0 1 180 110` (회색 `#EEF1F5`, 두께 16), 값 호 `{{ b8ArcPath }}` (파랑 `#1E5EFF`)
- 중앙 수치: `{b8Score}점` / 아래 `/ 80점 · {b8Pct}`
- 프로세스 이름 필: `{g1ProcName}`
- 보조 막대 2개
  - `자동판정 충족률 (35항목 기준) ~{b8AutoPct}` (막대색 `#1648D6`)
  - `수기확인 충족률 (45항목 기준) ~{b8ManPct}` (막대색 `#e8912d`)
- 설명: `80항목 중 35항목은 SHACL Shape로 자동판정 (STEP 6 ③ 가이드라인 대조와 동일 엔진) · 45항목은 담당자 확인 기반`
- 각주: `ⓘ 도입 전 실태 진단(~30%)은 최초 1회 컨설팅 산출값 — 재진단 대상 아님`

**우측 카드: 영역별 충족률** (부제 `(충족 1.0 · 부분 0.5 · 미흡 0)`)
- `<sc-for list="{{ areas }}" as="ar">` 6행. 각 행: `{ar.name}` + 배지 `SHACL 자동 {ar.auto}` + 배지 `수기 {ar.manual}` / 막대 `{ar.barStyle}` / `{ar.score} / {ar.items}항목 · {ar.pct}`
- 실제 값은 4.2절 참조.

#### (d) 미흡 요약 카드 3장 (2358~2362)

| 제목(빨강) | 본문 |
|---|---|
| `① 데이터 카드 부재` | `부록4 양식 40여 항목. 내용 절반 기도출, 양식 배치만 남음` + 배지 `난이도 낮음` |
| `② 편향성 명세 공백` | `rai:dataBiases · knownLimitations. {b8BiasMsg}` |
| `③ AI 에이전트·MCP 미검토` | `원칙 10 · 3.4절. API 계층 설계 필요` + 배지 `시스템 구축 과제` |

#### (e) 조치 우선순위 로드맵 표 (2363~2415)

- 제목: `조치 우선순위 로드맵`
- 열 머리글: `순위` / `조치` / `가산` / `난이도` / `해결방안`
- 6행 고정(4.5절 참조). 각 행 마지막 칸은 링크 `보기 ▾` (`rm1`~`rm6`).
- 링크를 누르면 표 아래에 해결방안 패널이 열린다(`rmOn`).
  - 머리: `해결방안 — {rmTitle}` / 우측 링크 `닫기 ✕` (`rmClose`)
  - `가이드라인 근거: {rmBasis}`
  - 본문: `rmIs1`~`rmIs6` 중 해당하는 1개 블록(4.5절 참조)

#### (f) 개선 시뮬레이션 배너 (2417) 정적 문구
`📈 개선 시뮬레이션: 순위 1~4 완료 시 38.5점 → 50.5점 (63%) — 신규 시스템 없이 도달. 80% 이상은 API·피드백 체계 구축 전제`

#### (g) 하단 버튼 줄 (2418~2422)

| 요소 | 문구 | 동작 |
|---|---|---|
| 파란 버튼 | `진단 보고서 PDF 내보내기` | 핸들러 없음(장식) |
| 흰 버튼 | `재진단 실행` (title: `자동판정 35항목 즉시 재계산 · 수기 45항목은 최근 확인값 유지`) | 핸들러 없음(장식) |
| 안내문 | `자동판정 35항목 즉시 재계산 · 수기 45항목은 최근 확인값 유지` | |

---

## 3. 사용자 동작 → 결과

### 3.1 STEP 8 진입

| 경로 | 동작 |
|---|---|
| 사이드바 8번 단계 클릭, STEP 7 화면 버튼 `STEP 8 가이드라인 준수 진단 · 발행 승인으로 →` (markup 1911, `goStep8` 514행) | `this.go({ plane:'studio', step:8 })`. `go()` (4~28행)가 `stepGate(8)` 을 검사한다. |
| 게이트 조건 (339행) | `8: { done: s.v8State === 'done', canEnter: cvDone, reason: 'STEP 7 변환을 먼저 실행하세요' }` 여기서 `cvDone = s.convertState === 'done'` (330행) |
| 잠김 시 토스트 (11행) | `🔒 STEP 8 잠김 — STEP 7 변환을 먼저 실행하세요` (3초 후 사라짐) |
| 사이드바 표시 (388~389행) | 잠김이고 현재 단계가 아니면 `🔒`, `done` 이면 `✓`, 아니면 숫자 `8` |
| 임시저장 복원 시 (81~84행) | 복원된 `step` 의 `canEnter` 가 거짓이면 통과 가능한 단계까지 내려간다. |

주의: 2.2의 프로세스 호출 칩(`pickB`)은 `go()` 를 거치지 않고 `setState({ step: 8, … })` 를 직접 호출하므로 게이트를 우회한다(1036, 1041행).

### 3.2 프로세스 호출 칩 클릭 `tp.pickB` = `toggle(p, 8)` (1025~1044행)

처리 순서
1. `nm` = 저장된 프로세스면 `p.name`, 진행 중 칩이면 `curName`.
2. `next = [...curSel]`.
   - `nm` 이 이미 포함되어 있고 `next.length > 1` 이면 제거한다.
   - 이미 포함되어 있지만 1개뿐이면 제거하지 않는다(최소 1개 유지). 이 경우에도 아래 4번이 실행되어 스냅숏을 다시 불러오고 진단 상태가 초기화된다.
   - 포함되어 있지 않으면 추가한다.
3. 현재 프로세스가 저장 목록에 없고(`!procList.some(x => x.name === curName)`), `next` 또는 `curSel` 이 `curName` 을 포함하면 `saveCur()` 를 먼저 호출해 스냅숏을 확보한다(1031행, `done` 인자 없음 = 종료 아님).
4. `snaps` = `next` 의 각 이름에 해당하는 `procList` 항목. 0건이면 아무 일도 하지 않고 종료.
5. 분기
   - **단일 호출** (`next.length === 1`, 1036~1037행)
     `setState({ ...blank(), ...snaps[0].snapshot, procName: snaps[0].name, taskProcSel: next, plane:'studio', step: 8, v7State: null, v8State: null })` 후 `persistDraft()`.
     토스트: `업무 B(진단) — 「{프로세스명}」 프로세스 호출 · 해당 프로세스 산출물 기준으로 진행`
   - **결합 호출** (`next.length >= 2`, 1039~1042행)
     각 스냅숏의 `combo` 를 데이터셋 이름 `d.n` 기준으로 중복 제거해 합친 `merged` 를 만든다. `setState({ combo: merged, procName: next.join(' + '), taskProcSel: next, plane:'studio', step: 8, v7State: null, v8State: null })` 후 `persistDraft()`. 이때 `blank()` 를 적용하지 않으므로 `combo` 이외의 작업 상태는 직전 프로세스 것이 남는다.
     토스트: `업무 B(진단) — {이름1} · {이름2} ({N}개 프로세스 결합 호출) · 산출물 합집합 {merged.length}건 기준 · 재실행 필요`
6. 토스트는 3초 후 닫힌다(`toastP`, 930행).

결과적 효과: 칩을 누를 때마다 `v7State`(STEP 6 검증 상태)와 `v8State` 가 `null` 이 되어 진단 결과가 사라지고 `대기 — 진단 미실행` 으로 돌아간다. 로그(`logAct`)는 남기지 않는다.

참고(목업 결함으로 보이는 점)
- 토스트 접두 판정이 `step === 7 ? '업무 A(검증)' : '업무 B(진단)'` 이다. STEP 6 화면의 같은 칩(`pickA = toggle(p, 6)`)도 `업무 B(진단)` 으로 표시된다. 단계 재편(6=검증) 이후 미수정된 부분이다.
- 3번의 `saveCur()` 직후 4번이 `this.state.procList` 를 동기적으로 읽는다. `setState` 가 배치 처리되면 방금 저장한 항목이 `snaps` 에서 빠질 수 있다(첫 클릭은 저장만 되고 이동하지 않을 가능성). 실제 제품에서는 서버 저장 완료 후 조회하도록 순서를 보장해야 한다.

### 3.3 `▶ 진단 실행` / `↺ 재진단 실행` 버튼 `v8Run` (1617~1631행)

1. `s.v8State === 'run'` 이면 무시한다. 그 외 선행 조건 검사는 없다(조합 0건이어도, `convertState` 가 `done` 이 아니어도 실행된다).
2. 즉시: `setState({ v8State: 'run', toast: true, toastText })`
   - 토스트: `⟳ 업무 B 진단 실행 — {s.procName 또는 '현재 프로세스'} {combo.length}건 · AUTO-GRAPH/PROFILE 자동 판정 (prov:Activity 기록)`
3. 1400ms 뒤(`setTimeout`, 타이머 핸들 `this._v8t`)
   1. `setState({ v8State: 'done', v8Time: this.nowHM(), toast: true, toastText })` 후 `persistDraft()`
      - 토스트: `✓ 진단 완료 — 자동 판정 결과가 아래에 표시됩니다 · 프로세스가 「종료」로 확정 저장되었습니다`
   2. 활동 로그 1: `logAct('홍길동 (나)', '가이드라인 준수 진단 실행 — {procName 또는 '현재 프로세스'} {combo.length}건')`
   3. `this._saveProc` 가 있으면 `this._saveProc(true)` 호출(프로세스 종료 확정 저장, 3.4절).
   4. 활동 로그 2: `logAct('홍길동 (나)', '프로세스 종료 확정 — {procName 또는 '현재 프로세스'} (STEP 8 진단 완료 · 전 단계 완주)')`
   5. 토스트는 3초 후 닫힌다.
4. 실제 판정 계산은 없다. `done` 이 되면 렌더 시점의 수식(4장)으로 숫자가 그려질 뿐이다.

`logAct` 동작(53~61행): `actSeq` 를 1 증가시켜 `ACT-K-{4자리}` id 를 발급하고 `actLog` 에 `{ t: 'HH:MM', who, txt, actId }` 를 추가한다. `actLog` 는 최근 10건만 유지한다. 진단 1회당 Activity id 가 2개 소모된다.

### 3.4 프로세스 종료 확정 `saveCur(true)` (936~946행)

- `entry = { id: Date.now(), name: curName, savedAt: 'MM-DD HH:MM'(UTC ISO 문자열 절단), step: 7, ver: 2, count: combo.length, done: true, snapshot: snap() }`
  - `done` 이 참이면 `step` 은 현재 단계가 아닌 고정값 `7` 로 기록된다.
  - `snapshot` 은 `workKeys` (920행) 만 담는다: `combo, comboName, comboMeta, comboSel, upList, upFile, manSel, upView, ds3, ds3Done, ds3Fold, mainSel, clsSel, propSel, provSel, provRec, clsDone, propDone, provDone, dsExtra, linkSeq, linkKnown, ds, dsDone4, dist2, f1Sel, f2Sel, f3Sel, f4Sel, f5Sel, relPairs, dsGroups, fmts, convertState, step, tab3, gran, pipe, nodeEdits, reviewFlags`. **`v8State`, `v8Time`, `v7State`, `v6Results` 는 스냅숏에 포함되지 않는다.** 진단 결과는 프로세스에 저장되지 않으며 종료 여부만 `entry.done` 으로 남는다.
- `procList` 에서 같은 이름 항목을 교체하고 `procName` 을 `curName` 으로 고정한 뒤 `persistDraft()`.
- 결합 호출 상태(`procName = 'A + B'`)에서 진단을 실행하면 이름이 `A + B` 인 새 프로세스 항목이 `done: true` 로 생성된다. 원본 A, B 의 `done` 은 바뀌지 않는다.
- 종료 확정이 반영되는 다른 화면
  - 프로세스 목록 행(1071행): `{savedAt} 저장 · 데이터셋 {count}건 · ✔ 프로세스 종료 (STEP 7 완료)` (문구가 STEP 7 로 고정되어 있다)
  - 산출물 저장소 그룹명(822행): `v8State === 'done'` 이면 `{프로세스명} (종료)`, 아니면 `{프로세스명} (진행 중)`. 같은 조건으로 `act` 는 `ACT-K-{actSeq 4자리}` / `ACT-미발급`, `fin` 플래그는 true/false.
- STEP 7 변환 완료 시에도 이미 `_saveProc(true)` 가 호출된다(2932~2934행, 로그 `프로세스 종료 저장 — {이름} (STEP 7 변환 완료)`). 즉 목업에서 "종료" 저장은 STEP 7 과 STEP 8 두 곳에서 일어나며 STEP 8 은 "확정"이라는 이름으로 다시 저장한다.

### 3.5 링크와 보조 동작

| 컨트롤 | 핸들러 | 결과 |
|---|---|---|
| `증거: shape 결과 →`, `STEP 6 게이트 0 →` | `goStep6` (513행) | `go({ plane:'studio', step:6 })` STEP 6 게이트 적용 |
| 로드맵 `보기 ▾` (1~6행) | `rm1`~`rm6` (2626행) | `go({ rm: n })`. 해당 행 링크는 `color:#1648D6;text-decoration:underline`, 나머지는 `color:#1E5EFF` (`rmLink`, 404행). 다른 행을 누르면 패널 내용이 교체된다. 같은 행을 다시 눌러도 닫히지 않는다. |
| `닫기 ✕` | `rmClose` (2625행) | `go({ rm: null })` |
| 해결방안 1번 4항의 `입력 →` | `goStep3` (2552행) | `go({ plane:'studio', step:3 })` |
| `진단 보고서 PDF 내보내기` | 없음 | 무동작 |
| 하단 `재진단 실행` | 없음 | 무동작(상단 `↺ 재진단 실행` 만 동작) |

### 3.6 진단 결과 무효화(다른 단계에서 발생)

| 원인 | 코드 | 결과 |
|---|---|---|
| 조합 변경(`addCombo` 등) | `invalidateDownstream('combo', …)` 346~348행 | `v6Results:null, v7State:null, v6Stale:false, convertState:null, svResults:null, v8State:null` |
| 카탈로그(정본) 변경 | 349~350행 | `v7State === 'done'` 일 때만 `v6Stale:true, convertState:null, svResults:null, v8State:null` |
| 그 외 kind | 351행 | `convertState:null, svResults:null, v8State:null` |
| STEP 2 조합 확정 | 2068행 | `v8State:null` 포함 초기화 |
| 산출물/프로세스 삭제 | 888, 891행 | `v8State:null, taskProcSel:null` |

무효화 시 토스트와 `logAct('시스템', msg)` 가 남는다(353~354행). `convertState` 가 `null` 이 되면 STEP 8 은 다시 잠긴다.

주의: 프로세스 불러오기(1078행)와 새 프로세스 시작(1017행, 974행)은 `v8State` 를 초기화하지 않는다. 이전 프로세스의 `done` 이 남아 새 프로세스의 산출물 그룹이 `(종료)` 로 표시될 수 있다. 실제 제품에서는 진단 결과를 프로세스에 귀속시켜 이 문제를 없애야 한다.

---

## 4. 진단 항목 전체 (목업에 실재하는 값)

### 4.1 점수 체계와 총점

| 항목 | 값 | 근거 |
|---|---|---|
| 총 항목 수 | 80 | 화면 문구 `80항목`, `/ 80점` |
| 항목 가중치 | 항목당 1점 동일 가중(별도 가중치 없음) | 영역 `items` 합 = 80 = 만점 |
| 항목 배점 규칙 | `충족 1.0 · 부분 0.5 · 미흡 0` | markup 2348 |
| 자동/수기 구분 | 자동(SHACL Shape) 35항목, 수기(담당자 확인) 45항목 | markup 2341~2344 |
| 등급 구간(A/B/C 등) | **없음** | 목업에 등급 밴드 정의 없음 |
| 기준선 언급 | `도입 전 실태 진단(~30%)`, `63%`, `80% 이상은 API·피드백 체계 구축 전제` | 정적 문구 |

게이지에 표시되는 값의 산식(전부 데모 산식, `n = combo.length`)

| 바인딩 | 산식 | 행 |
|---|---|---|
| `b8Score` | `(30 + n * 3).toFixed(1)` 상한 없음 | 1634 |
| `b8Pct` | `Math.round((30 + n * 3) / 80 * 100) + '%'` 상한 없음 | 1635 |
| `b8AutoPct` | `Math.min(95, 50 + n * 3) + '%'` | 1637, 1640 |
| `b8ManPct` | `Math.min(90, 35 + n * 2) + '%'` | 1638, 1640 |
| `b8AutoBar` | `'width:' + autoP + '%;height:6px;background:#1648D6;border-radius:3px'` | 1641 |
| `b8ManBar` | `'width:' + manP + '%;height:6px;background:#e8912d;border-radius:3px'` | 1642 |
| `b8ArcPath` | `ratio = max(0.02, min(1, (30 + 3n) / 80))`, `ang = π × (1 − ratio)`, `x = 100 + 80·cos(ang)`, `y = 110 − 80·sin(ang)`, 결과 `'M 20 110 A 80 80 0 0 1 ' + x.toFixed(1) + ' ' + y.toFixed(1)` | 1645~1651 |

조합 건수별 표시값

| n | `b8Score` | `b8Pct` | `b8AutoPct` | `b8ManPct` |
|---|---|---|---|---|
| 0 | 30.0 | 38% | 50% | 35% |
| 1 | 33.0 | 41% | 53% | 37% |
| 2 | 36.0 | 45% | 56% | 39% |
| 3 | 39.0 | 49% | 59% | 41% |
| 4 | 42.0 | 53% | 62% | 43% |
| 5 | 45.0 | 56% | 65% | 45% |

경계: `autoP` 는 n ≥ 15 에서 95 고정, `manP` 는 n ≥ 28 에서 90 고정, `b8Score` 는 n ≥ 17 에서 80점을 초과한다(게이지 호만 100% 로 잘린다).

### 4.2 영역별 충족률 (`areasData`, 460~471행, 전부 하드코딩)

배열 형식: `[name, items, score, pct, color, auto, manual]`

| # | 영역명(`name`) | 항목 수(`items`) | 점수(`score`) | 충족률(`pct`) | 막대색 | SHACL 자동(`auto`) | 수기(`manual`) |
|---|---|---|---|---|---|---|---|
| 1 | `메타데이터 필수 항목 (표9~12)` | 22 | `16.5` | 75% | `#2aa876` (초록) | 12 | 10 |
| 2 | `메타데이터 권장·선택 항목` | 7 | `3.0` | 43% | `#e8912d` (주황) | 4 | 3 |
| 3 | `15개 원칙` | 15 | `7.5` | 50% | `#e8912d` (주황) | 5 | 10 |
| 4 | `체크리스트 공통 필수 (부록3)` | 15 | `5.0` | 33% | `#c0392b` (빨강) | 7 | 8 |
| 5 | `체크리스트 공통 권장` | 18 | `6.0` | 33% | `#c0392b` (빨강) | 6 | 12 |
| 6 | `체크리스트 유형별 (수치·개인정보)` | 3 | `0.5` | 17% | `#c0392b` (빨강) | 1 | 2 |
| 합계 | | **80** | **38.5** | 48.1% | | **35** | **45** |

- `barStyle = 'height:12px;border-radius:10px;width:' + pct + '%;background:' + color`
- `pct` 는 `score / items` 를 반올림한 값과 일치한다(16.5/22=75.0, 3.0/7=42.9, 7.5/15=50.0, 5.0/15=33.3, 6.0/18=33.3, 0.5/3=16.7).
- 색상 임계값은 코드에 수식으로 존재하지 않고 행마다 직접 지정되어 있다. 관측값으로 추정하면 75% 이상 초록, 43~50% 주황, 33% 이하 빨강이다. 실제 제품에서는 임계값을 명시적으로 정해야 한다(8.3절 제안).
- 이 표는 상태와 무관한 상수다. 어떤 프로세스를 호출해도, 조합이 몇 건이어도 같은 값이 나온다.

### 4.3 판정 방식별 집계 (부록3 공통 34항목)

배지 문구: `부록3 공통 34항목 (필수 18 + 권장 16)`

| 판정 방식 | 정의(화면 문구) | 건수 | 표시값 산식 | 행 |
|---|---|---|---|---|
| `AUTO-GRAPH` | `카탈로그 그래프 SPARQL/SHACL 질의 자동 판정` | 24 | `b8Graph = 24 - (viol > 0 ? 1 : 0)` → `{b8Graph}건 적정` | 1632 |
| `AUTO-PROFILE` | `접합부 프로파일 통계 자동 판정` | 4 | `b8ProfBad = combo.some(c => /도로/.test(c.n)) ? 1 : 0` → `4건 중 {b8ProfBad}건 미흡` | 1633 |
| `HUMAN-ATTEST` | `증빙 첨부 + 담당자 서명 (서명도 prov:Activity)` | 6 | 고정 문자열 `사람 확인 대기 6건` | markup 2306 |
| 합계 | | 34 | | |

- `viol = this.props.violationCount ?? 0` (375행). 컴포넌트 prop 이며 STEP 6 검증 결과(`s.v6Results`)와 연결되어 있지 않다. prop 이 주어지지 않으면 항상 0 이므로 `b8Graph` 는 항상 24 다.
- `b8ProfileMsg` (1652행)
  - 조합에 이름이 `/도로/` 에 맞는 데이터셋이 있으면: `미흡 1건: 도로 공간정보 GEOM 좌표계 미선언 (프로파일 지표)`
  - 없으면: `미흡 0건 — 전 항목 통과`
- `b8BiasMsg` (1653~1655행)
  - 조합에 `c.n === 'cctv.vehicle.det.v1'` 이 있으면: `인식 모델 MDL-000004의 야간 인식률 −7%p · 우천 OCR −3%p (합성 데모)를 rai:dataBiases로 정량 등록 가능`
  - 없으면: `조합 데이터셋의 프로파일 통계에서 분포 편향 정량 산출 가능`

### 4.4 목업에 문장으로 등장하는 개별 판정 항목 (전수)

목업에서 개별 항목 수준으로 식별 가능한 것은 아래가 전부다. id 는 목업에 없다.

| 출처 | 항목 문구(원문) | 판정 방식 | 판정 기준(원문) | 증거(원문) | 목업에서의 판정 |
|---|---|---|---|---|---|
| markup 2309 | `"메타데이터 필수 항목 누락 없음"` | AUTO-GRAPH | `DatasetShape minCount 통과` | `증거: shape 결과 →` (STEP 6) | 고정(항상 통과로 서술) |
| markup 2310 | `"결측값 표기 통일"` | AUTO-PROFILE | `결측 표기 패턴 종류 수 = 1` | `증거: 프로파일 지표 — {b8ProfileMsg}` | 실제 계산 없음. 표시되는 미흡 문구는 좌표계 건이다(항목과 증거 문구가 어긋남). |
| logic 1652 | `도로 공간정보 GEOM 좌표계 미선언 (프로파일 지표)` | AUTO-PROFILE | 좌표계 선언 여부 | 프로파일 지표 | 데이터셋 이름에 `도로` 포함 여부(정규식) |
| markup 2311 | `파생 이벤트의 비식별 조치` | HUMAN-ATTEST + 자동 증빙 | `판정은 사람, 증빙 수집은 자동` | `마스킹 prov:Activity(규칙 v1.2)가 첨부 증빙으로 자동 연결` | 고정 문구 |
| markup 2359 | `① 데이터 카드 부재` | (미표기) | `부록4 양식 40여 항목. 내용 절반 기도출, 양식 배치만 남음` | | 고정(항상 미흡) |
| markup 2360 | `② 편향성 명세 공백` | (미표기) | `rai:dataBiases · knownLimitations.` | `{b8BiasMsg}` | 고정(항상 미흡), 보조 문구만 조합 연동 |
| markup 2361 | `③ AI 에이전트·MCP 미검토` | (미표기) | `원칙 10 · 3.4절. API 계층 설계 필요` | | 고정(항상 미흡) |
| markup 2322 | `게이트 0의 검사 ④(ID 잔존 — (-신규|-draft-))` | STEP 6 게이트 | 발행물에 임시 ID 패턴 잔존 금지 | STEP 6 게이트 0 | STEP 6 에서 판정(`validateDs` 313행) |

가이드라인 구조에 대한 목업 내 단서(문구에서 추출)

| 가이드라인 위치 | 목업이 말하는 내용 | 출처 |
|---|---|---|
| 표9 | 필수항목 `dcterms:license` | `rmBasis[3]`, markup 2395 |
| 표10 | 권장항목 `rai:dataBiases` · `rai:knownLimitations` | `rmBasis[1]` |
| 표11 | `mediaType` 권장 | `rmBasis[5]`, markup 2407 |
| 표12 | 등재 이력 관리 요건, `dcat:CatalogRecord` (`dcterms:modified · foaf:primaryTopic`) | logic 1796 |
| 15개 원칙 | 원칙 6 `형식 표준화`, 원칙 8 `품질·한계 명시`, 원칙 10 `기계 접근성` | `rmBasis[4]`, `[1]`, `[6]` |
| 3.4절 | `AI 에이전트·MCP 연계` | `rmBasis[6]` |
| 부록3 | 체크리스트: 공통 필수, 공통 권장, 유형별(수치·개인정보) | 4.2, 4.3절 |
| 부록4 | 데이터 카드 양식(40여 항목) | markup 2359, `rmBasis[2]` |
| 체크리스트 공통 필수 | `이용조건 명확화` | `rmBasis[3]` |

### 4.5 조치 우선순위 로드맵 (전부 하드코딩)

표 본문(markup 2368~2373)

| 순위 | 조치 | 가산 | 난이도(배지 색) | `s.rm` |
|---|---|---|---|---|
| `1` | `rai:dataBiases + 결측치 정보 작성` | `+3.5` | `낮음` (초록) | 1 |
| `2` | `데이터 카드 작성 (부록4 양식)` | `+2.5` | `낮음` (초록) | 2 |
| `3` | `라이선스 · dct:references 확정 (공공누리 + 교통안전법 §55)` | `+4.0` | `낮음` (초록) | 3 |
| `4` | `ISO 8601 정규화 + 결측 규칙 통일` | `+2.0` | `중간` (주황) | 4 |
| `5~7` | `코드 도메인 매핑 · 개인정보 판정 통일 · Parquet 추가` | `—` | `중간` (주황) | 5 |
| `8~9` | `API 계층 + MCP 연계 · 피드백 체계` | `—` | `높음` (빨강) | 6 |

- 가산 합계(순위 1~4): 3.5 + 2.5 + 4.0 + 2.0 = 12.0. 시뮬레이션 배너의 `38.5점 → 50.5점 (63%)` 와 일치한다(50.5 / 80 = 63.1%).

패널 제목 `rmTitle` (2629행, 인덱스 = `s.rm`)

```
['', 'rai:dataBiases + 결측치 정보 작성', '데이터 카드 작성 (부록4 양식)', '라이선스 · dct:references 확정',
 'ISO 8601 정규화 + 결측 규칙 통일', '코드 도메인 매핑 · 개인정보 판정 통일 · Parquet 추가', 'API 계층 + MCP 연계 · 피드백 체계']
```

가이드라인 근거 `rmBasis` (2630행)

```
['', '표10 권장항목 rai:dataBiases · rai:knownLimitations / 15개 원칙 중 원칙 8(품질·한계 명시)',
 '부록4 데이터 카드 양식 (40여 항목) / 체크리스트 공통 필수',
 '표9 필수항목 dcterms:license / 체크리스트 공통 필수 (이용조건 명확화)',
 '15개 원칙 중 원칙 6(형식 표준화) / 체크리스트 공통 권장',
 'SKOS 통제어휘 준수 / 체크리스트 유형별(개인정보) / 표11 mediaType 권장',
 '원칙 10(기계 접근성) · 3.4절 AI 에이전트·MCP 연계 / 피드백 체계 권장']
```

해결방안 본문(markup 2383~2413, 원문)

**rm = 1**
1. `eTAS 오류 마스터 61종 · 검사결과 79.7만 건에서 클래스별 분포 편향을 정량 산출 (지역·차종·연식별 집계)`
2. `산출 통계를 rai:dataBiases에, 검사장비·기간 한계는 rai:knownLimitations에 기술`
3. `컬럼별 결측률·결측 사유·대체 규칙을 프로파일 통계에서 추출해 데이터 카드 결측치 항목에 기록`
4. `STEP 3 프러퍼티 폼에 rai: 그룹 추가 후 입력 → · 재진단 시 +3.5점 반영` (`입력 →` 은 `goStep3`)

**rm = 2**
1. `부록4 데이터 카드 양식 40여 항목 중 절반은 기도출 (프로파일·분류·프로버넌스에서 자동 채움)`
2. `잔여 항목(수집 방법·대표성·활용 사례)만 담당자 작성 — 데이터셋당 약 30분 예상`
3. `카드 자체를 dcat:Distribution(문서형)으로 등록해 카탈로그에서 조회 가능하게 배치`

**rm = 3**
1. `dcterms:license에 공공누리 제1유형 URI 지정 (표9 필수 항목)`
2. `dct:references에 수집 근거 교통안전법 §55 조문 링크 명시`
3. `개방구역 투영 필터에 라이선스 없는 데이터셋 제외 규칙 추가 — 가산 +4.0점, SHACL Shape에 minCount 반영`

**rm = 4**
1. `혼재된 시간포맷 5종을 ISO 8601로 일괄 정규화 (STEP 2 경고 항목과 동일 건)`
2. `갱신 주기는 duration 표기(PT5M)로 통일 — STEP 7 Warning 49건 중 31건 해소`
3. `결측 표기(null·공백·-999 혼재)를 소스별 규칙표로 통일하고 변환 규칙을 prov:Activity로 기록`

**rm = 5**
1. `소스 코드값 도메인을 SKOS 통제어휘 66코드(EVT 4종 포함)에 매핑하는 대응표 작성 (skos:exactMatch)`
2. `개인정보 판정 기준을 체크리스트 유형별(개인정보) 항목에 맞춰 기관 단일 기준으로 통일`
3. `CSV-only 데이터셋에 Parquet 배포본 추가 — 표11 mediaType 권장 충족 + 푸터 대조 가능`

**rm = 6**
1. `JSON-LD 카탈로그 API 계층 설계 (원칙 10: 기계 접근성) — STEP 7 ④ 전송 채널과 연동`
2. `MCP 서버로 검색·리니지·정본 조회 도구 노출 (3.4절 AI 에이전트 연계)`
3. `활용자 피드백 수집 체계 구축 — 오류 신고를 검수 큐로 유입시켜 재검증 루프에 연결 · 시스템 구축 과제로 별도 일정`

### 4.6 목업 내부 수치 불일치 (구현 전 확정 필요)

| # | 불일치 | 내용 |
|---|---|---|
| 1 | 총점 | 게이지는 `30 + 3n` (조합 3건이면 39.0), 영역 표 합계와 시뮬레이션 배너는 38.5 고정 |
| 2 | 부록3 공통 항목 수 | 배지는 `34항목 (필수 18 + 권장 16)`, 영역 표는 공통 필수 15 + 공통 권장 18 = 33 |
| 3 | 자동 판정 수 | 영역 표와 게이지는 SHACL 자동 35 / 수기 45, 판정 방식 집계는 34항목 중 AUTO-GRAPH 24 + AUTO-PROFILE 4 = 28 자동, HUMAN-ATTEST 6. 화면 문구 `유형별 추가 항목도 동일 체계 (다수가 HUMAN-ATTEST)` 로 범위가 다르다고 볼 수 있으나 80항목 전체의 방식별 분포는 정의되어 있지 않다. |
| 4 | 자동/수기 충족률 | `50 + 3n`, `35 + 2n` 은 영역 표의 자동/수기 구성과 무관한 산식 |
| 5 | AUTO-PROFILE 예시 | 항목은 `결측값 표기 통일` 인데 미흡 메시지는 `GEOM 좌표계 미선언` |
| 6 | 종료 문구 | STEP 8 에서 종료 확정해도 목록에는 `✔ 프로세스 종료 (STEP 7 완료)` |
| 7 | "독립 진단 업무" | 배지는 독립 업무라 하지만 게이트는 STEP 7 변환 완료를 요구하고, 호출 칩은 그 게이트를 우회 |
| 8 | STEP 7 버튼 문구 | `STEP 8 가이드라인 준수 진단 · 발행 승인으로 →` 라고 하지만 STEP 8 에 발행 승인 UI 는 없다 |
| 9 | 가이드라인 명칭/버전 | STEP 8 은 `행안부 「공공데이터의 AI 친화적 관리 가이드라인 v1.1」`, 시스템 관리 지식베이스 표(797행)는 `공공데이터 진단척도 가이드` / `행안부 · 메타데이터 80항목·15원칙·체크리스트` / 적용 `v1.1 (2025-11)` / 최신 `v1.2 (2026-07)` / 최신 아님(`false`) / 색인일 `2026-08-14` |

---

## 5. 데이터 (그 밖의 하드코딩 목록)

### 5.1 단계 게이트 표 (331~340행 중 STEP 8 관련)

```
7: { done: cvDone, canEnter: v6done && v6passN >= 1, reason: … }
8: { done: s.v8State === 'done', canEnter: cvDone, reason: 'STEP 7 변환을 먼저 실행하세요' }
```

### 5.2 URI 민팅 카드(정적)

- 네임스페이스 `https://catalog.molit.go.kr/id/…`
- 형식 `DST-######`, `PLN-######`, `MDL-######`
- 치환 예 `DST-신규 → DST-000124`
- 잔존 검사 패턴 `(-신규|-draft-)`
- 참고: 실제 민팅 맵은 `MINT_MAP` (117~123행): `kma.aws.obs.v1 → SVC-000041`, `cctv.vehicle.det.v1 → SVC-000042`, `sample_공간정보_통합포털_데이터셋_목록_도로 → DST-000961`, `실시간교통사고 → SVC-000043`, `디지털운행기록분석시스템(eTAS)_정보시스템 → DST-000962`. 초안 ID 는 `{DST|SVC|DIST|ACT}-draft-{hash6(이름)}` (161행).

### 5.3 STEP 8 관련 주변 데이터

| 위치 | 값 |
|---|---|
| 파이프라인 구성표(1295행) | `[8, '가이드라인 진단', 규칙: '점수 집계', LLM: 'sLLM-molit-7b (진단 요약)' 배지 '보조', 외부연계 '—', 상태 'ok']` |
| 일정표(1317행) | `['STEP 8', '가이드라인 진단', 17, 3, 0, 0, '홍길동(정) · 이관리(부)', '변학도', 'plan']` (시작 셀, 길이, 계획 %, 실적 %, 작업자, 관리자, 상태) |
| 단계 인계 담당 조직(2989행, 8번째) | `정보화기획담당관` |
| 도우미 추천 질문(3039행) | `step8: ['35항목 자동판정의 의미는?', '점수를 올리려면 뭐부터 하나요?']` |
| 답변 1(3017행) | `가이드라인 80항목 중 35항목은 SHACL Shape로 기계 판정됩니다 — STEP 6 ③ 가이드라인 대조와 동일 엔진입니다.\n[재진단 실행]은 이 35항목만 즉시 재계산하고, 수기 45항목은 담당자 최근 확인값을 유지합니다.` |
| 답변 2(3018행) | `조치 우선순위 로드맵의 순위 1~4(rai:dataBiases · 데이터 카드 · 라이선스 확정 · ISO 8601 정규화)가 난이도 낮음~중간이면서 +12점입니다.\n완료 시 38.5점 → 50.5점(63%)으로, 신규 시스템 없이 도달 가능합니다.` |
| 활동 주체 | `홍길동 (나)` (로그 작성자 고정) |

### 5.4 상태 배지/버튼 스타일 상수

| 상태 | 배지 스타일(1614행) | 버튼 스타일(1616행) |
|---|---|---|
| 대기 | `background:#EEF1F5;color:#8B919C` | `background:#1E5EFF;color:#fff` |
| 실행 중 | `background:#E8EEFF;color:#1648D6` | `background:#8fb8d8;color:#fff` |
| 완료 | `background:#e6f4ea;color:#1e7e46` | `background:#1E5EFF;color:#fff` |

---

## 6. 상태 변수

| 키 | 타입 | 의미 | 쓰는 곳 | 영속 |
|---|---|---|---|---|
| `v8State` | `null \| 'run' \| 'done'` | 진단 실행 상태. `done` 이면 결과 영역 표시, 단계 8 완료 표시, 산출물 그룹 `(종료)` | `v8Run`, `pickA/pickB`, `invalidateDownstream`, 조합 확정, 삭제 | localStorage 초안에 저장. 프로세스 스냅숏에는 미포함 |
| `v8Time` | `'HH:MM'` 문자열 | 진단 완료 시각 | `v8Run` 에서 기록 | 초안에 저장. **화면 어디에서도 읽지 않는다** |
| `taskProcSel` | `string[] \| null` | 업무 A/B 에서 호출한 프로세스 이름 목록. `null` 은 현재 프로세스 단일 모드 | `pickA/pickB`, 프로세스 신규/불러오기/삭제 시 `null` | 초안 저장 |
| `procName` | `string` | 현재 프로세스 이름. 결합 호출 시 `'A + B'` 형식 | 호출, 저장 | 초안 저장 |
| `procList` | `Array<{ id, name, savedAt, step, ver, count, done, snapshot }>` | 저장된 프로세스. `done` 이 종료 플래그 | `saveCur` | 초안 저장 |
| `combo` | `Array<{ n: string, meta?: … }>` | 진단 대상 데이터셋 조합. `n` 이 데이터셋 이름 | 결합 호출 시 합집합으로 교체 | 초안, 스냅숏 |
| `convertState` | `null \| 'run' \| 'done'` | STEP 7 변환 상태. STEP 8 진입 게이트 | STEP 7 | 초안, 스냅숏 |
| `v7State` | `null \| 'run' \| 'done'` | STEP 6 검증 상태(이름은 재편 전 잔재) | 호출 칩이 `null` 로 초기화 | 초안 |
| `rm` | `1..6 \| null` | 열려 있는 로드맵 해결방안 번호 | `rm1`~`rm6`, `rmClose` | 초안 저장 |
| `actLog` | `Array<{ t, who, txt, actId }>` 최근 10건 | 활동 로그 | `logAct` | 초안 |
| `actSeq` | `number` (초기 420) | Activity id 시퀀스 | `logAct`, `mintAct` | 초안 |
| `toast`, `toastText` | `boolean`, `string \| null` | 토스트 표시 | 각 동작 | 저장 제외 |
| `plane`, `step` | `string`, `number` | 화면 위치 | `go`, 호출 칩 | 초안 |
| `props.violationCount` | `number` (기본 0) | 위반 건수(컴포넌트 prop, 상태 아님) | 외부 주입 | 해당 없음 |

파생 값(상태 아님): `g1ProcName` (1546행) = `procName` 의 모든 구성 이름이 `procList` 에 있으면 `procName`, 아니면 `'현재 프로세스'`. `comboCount` = `s.combo.length`.

인스턴스 필드: `this._v8t` (진단 타이머), `this._tt` (토스트 타이머), `this._saveProc` (렌더마다 재할당되는 저장 훅).

---

## 7. 시뮬레이션 vs 실제 계산

| 기능 | 목업 동작 | 분류 |
|---|---|---|
| 진단 실행 | 1.4초 타이머 후 상태만 `done` 으로 변경 | 시뮬레이션 |
| 총점, 충족률 | `30 + 3n` 등 조합 건수 연동 데모 산식(코드 주석 `조합 규모 연동 데모 산식`) | 시뮬레이션 |
| 영역별 점수 6행 | 상수 배열 | 하드코딩 |
| AUTO-GRAPH 건수 | `24 - (viol > 0 ? 1 : 0)`, `viol` 은 외부 prop | 하드코딩에 가까움 |
| AUTO-PROFILE 미흡 | 데이터셋 이름 정규식 `/도로/` | 가짜 판정 |
| HUMAN-ATTEST 대기 6건 | 고정 문자열 | 하드코딩 |
| 편향성 문구 | 조합에 `cctv.vehicle.det.v1` 포함 여부 | 가짜 판정(문구에 `합성 데모` 명시) |
| 미흡 카드 3장, 로드맵, 가산점, 시뮬레이션 배너 | 정적 마크업 | 하드코딩 |
| URI 민팅 카드 | 정적 마크업 | 하드코딩 |
| PDF 내보내기, 하단 재진단 | 핸들러 없음 | 미구현 |
| 증거 링크 | STEP 6/STEP 3 으로 단순 이동(해당 항목 위치로 딥링크하지 않음) | 부분 구현 |
| prov:Activity 기록 | `actLog` 에 문자열 2건 추가, id 는 세션 시퀀스 | 시뮬레이션 |
| 프로세스 호출과 합집합 | 실제로 스냅숏을 불러오고 `combo` 를 이름 기준으로 합친다 | **실제 계산** |
| 프로세스 종료 확정 | 실제로 `procList` 항목을 `done: true` 로 저장하고 localStorage 에 기록 | **실제 계산**(브라우저 로컬 한정) |
| 단계 게이트 | `stepGate(8)` 실제 판정 | **실제 계산** |
| 게이지 호 좌표 | 삼각함수로 실제 계산 | **실제 계산**(입력값이 가짜) |
| 하류 무효화 | 상류 변경 시 `v8State` 초기화 | **실제 계산** |

진단과 STEP 6 실제 검증의 연결 상태: `validateDs` (309~322행)가 데이터셋 단위로 실제 판정하는 항목은 민팅 등록, 제목, publisher, Distribution, 스트림 필수(`temporalResolution`, `eventTimeColumn`), 분류 완료 경고뿐이다. STEP 8 은 이 결과(`s.v6Results`)를 전혀 읽지 않는다.

---

## 8. 실제 제품에서 필요한 기능 (제안)

### 8.1 원칙

1. **항목 카탈로그를 데이터로 관리한다.** 80항목 원문(영역, 번호, 항목명, 필수/권장/선택 구분, 근거 위치)은 가이드라인 문서에서 시드하고 버전을 붙인다. 목업의 지식베이스 표가 이미 v1.1 적용 / v1.2 최신 차이를 보여 주므로 버전 전환을 전제로 설계한다. 본 문서의 4.2절 영역 구성(22/7/15/15/18/3)은 시드 검증용 기대값으로 쓴다. 단 4.6절 #2, #3 의 불일치는 원문 대조로 확정해야 한다.
2. **항목마다 리졸버 1개를 연결한다.** 리졸버 유형은 목업의 3종을 그대로 쓴다: `AUTO_GRAPH` (SPARQL ASK/SELECT 또는 SHACL shape), `AUTO_PROFILE` (프로파일 지표 임계 판정), `HUMAN_ATTEST` (증빙 + 서명, 자동 증빙 수집 선택).
3. **판정 결과는 반드시 증거를 가진다.** 증거 없는 `충족` 은 저장할 수 없게 한다.
4. **진단 실행 단위는 "프로세스 집합의 데이터셋 합집합"이다.** 진단 결과는 프로세스(집합)에 귀속시켜 저장한다. 목업처럼 전역 상태로 두지 않는다.
5. **STEP 6 검증과 같은 엔진, 같은 그래프를 쓴다.** 목업 문구 `STEP 6 ③ 가이드라인 대조와 동일 엔진` 을 지키려면 가이드라인용 shape 그래프를 STEP 6 검증 실행에 포함하고, STEP 8 은 그 결과를 항목 단위로 재집계한다.

### 8.2 판정 방식별 실제 계산 방법

**AUTO_GRAPH**
- 입력: 데이터셋별 정본에서 `buildTriples` 에 해당하는 로직으로 만든 rdflib `Graph` (STEP 7 발행 그래프와 동일 원료), 리니지/프로버넌스 트리플, 분류(SKOS) 트리플.
- 방법 A (SHACL): shape 에 `fde:guidelineItem <항목 IRI>` 주석을 달고 pySHACL 로 검증한다. 결과 그래프의 `sh:sourceShape` 를 항목으로 역매핑한다. 포커스 노드별 위반 0건이면 충족.
- 방법 B (SPARQL): 항목별 `ASK` 또는 `SELECT (COUNT …)` 질의를 저장하고 기대값과 비교한다.
- 증거: 검증 실행 id, shape IRI, 포커스 노드, 위반 메시지, 질의문과 결과 바인딩.

**AUTO_PROFILE**
- 입력: 데이터 평면 프로파일 통계(컬럼별 결측률, 결측 표기 토큰 집합, 날짜 포맷 종류, 코드값 도메인, 좌표계 메타, 클래스 분포).
- 방법: 지표와 임계 연산자를 항목 정의에 저장한다(예: `missing_token_kinds == 1`).
- 증거: 프로파일 실행 id, 지표명, 측정값, 임계값, 표본 컬럼.
- 프로파일이 없는 데이터셋은 `판정불가` 로 두고 미흡과 구분한다.

**HUMAN_ATTEST**
- 입력: 담당자 판정(충족/부분/미흡), 첨부 증빙, 서명자, 서명 시각.
- 자동 증빙 수집: 항목 정의에 증빙 질의를 둔다(예: 대상 데이터셋에 연결된 마스킹 `prov:Activity` 조회). 수집된 증빙은 후보로 제시하고 판정은 사람이 한다.
- 서명 자체를 `prov:Activity` 로 기록한다(목업 문구 `서명도 prov:Activity`).
- 재진단 시 최근 확인값을 이월한다. 단 대상 정본의 체크섬이 바뀌었으면 `재확인 필요` 로 표시한다. 유효기간(예: 12개월)을 항목 정의에 둘 수 있다.

### 8.3 점수 산식 제안

- 항목 × 데이터셋 판정값: `MET = 1.0`, `PARTIAL = 0.5`, `UNMET = 0`, `NA`(해당 없음), `UNKNOWN`(판정불가, 수기 미확인).
- 항목 점수(프로세스 수준): 해당 항목이 적용되는 데이터셋들의 판정값 평균을 구해 다음으로 환산한다. 전부 MET 이면 1.0, 전부 UNMET 이면 0, 그 외 0.5. (대안: 평균값 그대로 사용. 결정 필요)
- `NA` 항목은 분모에서 제외하되 화면에는 원 항목 수와 적용 항목 수를 함께 보여 준다. `UNKNOWN` 은 0점으로 계산하고 "사람 확인 대기" 건수로 따로 집계한다.
- 영역 점수 = 영역 내 항목 점수 합, 영역 충족률 = 영역 점수 / 영역 적용 항목 수.
- 총점 = 영역 점수 합(만점 80), 충족률 = 총점 / 80.
- 자동판정 충족률 = 리졸버가 AUTO_* 인 항목 점수 합 / 해당 항목 수. 수기확인 충족률 = HUMAN_ATTEST 항목 점수 합 / 해당 항목 수.
- 막대 색 임계값(목업 관측값 기반 제안, 설정값으로 관리): 70% 이상 초록 `#2aa876`, 40% 이상 70% 미만 주황 `#e8912d`, 40% 미만 빨강 `#c0392b`.
- 등급 밴드는 목업에 없다. 필요하면 가이드라인 원문 또는 발주 기관 기준으로 별도 정의한다.
- 기준선: `도입 전 실태 진단(~30%)` 을 프로세스 또는 기관 단위 `baseline_score` 로 1회 입력받아 비교 표시한다.

### 8.4 항목별 실제 계산 제안 (목업에 등장한 항목 기준 시드)

아래 id 는 제안값이다. 항목명과 근거는 목업 문구이며, 가이드라인 원문과 대조해 확정한다.

| 제안 id | 영역 | 항목(목업 문구) | 리졸버 | 실제 계산 |
|---|---|---|---|---|
| `M-REQ-*` | 메타데이터 필수 (표9~12) | `메타데이터 필수 항목 누락 없음` | AUTO_GRAPH (SHACL) | 클래스별 필수 속성마다 `sh:minCount 1` property shape 를 두고 속성 1개를 항목 1개에 대응시킨다. 현재 정본이 실제로 만드는 술어는 `dcterms:title`, `dcterms:publisher`, `dcat:distribution`, `dcat:mediaType`, `dcterms:format`, `dcat:temporalResolution`, `dcat:endpointDescription`, `prov:wasGeneratedBy` 뿐이므로 표9~12 의 나머지 필수 속성을 정본 스키마에 추가해야 한다. |
| `M-REQ-LICENSE` | 메타데이터 필수 (표9) | `dcterms:license` 지정 | AUTO_GRAPH | `ASK { ?ds dcterms:license ?l . FILTER(isIRI(?l)) }` + 허용 라이선스 목록(공공누리 유형 URI) 포함 여부. 미지정 UNMET, 리터럴이면 PARTIAL. |
| `M-REQ-RECORD` | 메타데이터 필수 (표12) | 등재 이력 관리(`dcat:CatalogRecord`) | AUTO_GRAPH | `?rec a dcat:CatalogRecord ; foaf:primaryTopic ?ds ; dcterms:modified ?m` 존재 여부. |
| `M-REC-BIAS` | 메타데이터 권장 (표10) | `rai:dataBiases` | AUTO_GRAPH + 품질 보조 | 속성 존재하고 길이/정량 수치 포함 시 MET, 존재하나 정성 문구뿐이면 PARTIAL, 없으면 UNMET. 프로파일의 클래스 분포 통계를 증거 후보로 첨부. |
| `M-REC-LIMIT` | 메타데이터 권장 (표10) | `rai:knownLimitations` | AUTO_GRAPH | 속성 존재 여부. |
| `M-REC-MEDIATYPE` | 메타데이터 권장 (표11) | `mediaType` 권장, Parquet 배포본 | AUTO_GRAPH | 모든 Distribution 의 `dcat:mediaType` 이 IANA IRI 인지, 기계 처리 친화 포맷 배포본이 1개 이상인지. CSV 전용이면 PARTIAL. |
| `M-REC-REFERENCES` | 메타데이터 권장 | `dct:references` 수집 근거 | AUTO_GRAPH | `dcterms:references` IRI 존재 여부. 법령 링크 여부는 HUMAN_ATTEST 보조. |
| `P-06` | 15개 원칙 | 원칙 6 `형식 표준화` | AUTO_PROFILE | 날짜/시각 컬럼의 포맷 종류 수 = 1 이고 ISO 8601 정규식 일치율 ≥ 임계. 갱신 주기와 `dcat:temporalResolution` 이 `xsd:duration` 형식인지(AUTO_GRAPH, `sh:datatype xsd:duration`). |
| `P-08` | 15개 원칙 | 원칙 8 `품질·한계 명시` | AUTO_GRAPH + HUMAN_ATTEST | `M-REC-BIAS`, `M-REC-LIMIT`, 품질 측정(`dqv:hasQualityMeasurement`) 존재 여부를 종합. |
| `P-10` | 15개 원칙 | 원칙 10 `기계 접근성` | AUTO_GRAPH + 시스템 점검 | `dcat:accessService` / `dcat:endpointURL` 존재, 카탈로그 JSON-LD API 응답 헬스체크(시스템 수준 항목이므로 데이터셋이 아닌 기관/시스템 범위로 판정). |
| `S-3.4` | 15개 원칙 또는 별도 절 | 3.4절 `AI 에이전트·MCP 연계` | HUMAN_ATTEST + 시스템 점검 | MCP 서버 도구 목록 조회 성공 여부를 자동 증빙으로 첨부, 판정은 사람. |
| `C-COM-MISSING` | 체크리스트 공통 | `결측값 표기 통일` | AUTO_PROFILE | 소스별 결측 표기 토큰 집합(`null`, 공백, `-999` 등)의 종류 수 = 1 이면 MET. 2 이상이면 UNMET, 변환 규칙 `prov:Activity` 가 등록되어 있으면 PARTIAL. |
| `C-COM-CRS` | 체크리스트 공통 | 공간 컬럼 좌표계 선언 | AUTO_PROFILE + AUTO_GRAPH | 프로파일이 GEOM 컬럼을 탐지했는데 `dcterms:conformsTo` 에 EPSG IRI 가 없으면 UNMET (목업 STEP 6 경고 `GEOM 컬럼 EPSG 명시 필요 — EPSG:5186 권장` 과 동일 건). 데이터셋 이름 정규식이 아닌 컬럼 타입 탐지로 판정한다. |
| `C-COM-TERMS` | 체크리스트 공통 필수 | `이용조건 명확화` | AUTO_GRAPH | `M-REQ-LICENSE` 와 `dcterms:accessRights` 를 함께 검사. |
| `C-COM-CARD` | 체크리스트 공통 필수 | `데이터 카드 작성 (부록4 양식)` | AUTO_GRAPH + 완성도 | 데이터 카드 산출물 존재 여부와 필드 채움률. 채움률 ≥ 90% MET, 50~90% PARTIAL, 그 미만 UNMET. 카드가 `dcat:Distribution` (문서형)으로 등록되어 있는지도 확인. |
| `C-COM-VOCAB` | 체크리스트 공통 | SKOS 통제어휘 66코드 준수 | AUTO_GRAPH + AUTO_PROFILE | 분류 값이 통제어휘 스킴 소속인지(`sh:in` 또는 `skos:inScheme`), 소스 코드값 도메인의 `skos:exactMatch` 매핑 커버리지. |
| `C-COM-IDSTABLE` | 체크리스트 공통 | 안정 URI (임시 ID 잔존 금지) | AUTO_GRAPH | 발행 그래프의 모든 IRI 에 대해 정규식 `(-신규|-draft-)` 불일치. 민팅 맵 등록 여부. |
| `C-COM-LINEAGE` | 체크리스트 공통 | 리니지/프로버넌스 연결 | AUTO_GRAPH | `prov:wasGeneratedBy`, `prov:wasDerivedFrom`, `prov:wasAttributedTo` 존재, 리니지 면제(`linWaived`) 시 사유 기록 여부. |
| `C-COM-FEEDBACK` | 체크리스트 공통 권장 | `피드백 체계` | HUMAN_ATTEST | 피드백 접수 채널 URL 과 검수 큐 연동 증빙. |
| `C-TYPE-PII` | 체크리스트 유형별 (개인정보) | `파생 이벤트의 비식별 조치`, `개인정보 판정 통일` | HUMAN_ATTEST + 자동 증빙 | 대상 데이터셋에 연결된 마스킹 `prov:Activity` (규칙 버전 포함)를 자동 수집해 첨부. 판정은 담당자 서명. |
| `C-TYPE-NUM` | 체크리스트 유형별 (수치) | 수치형 데이터 항목 | AUTO_PROFILE | 단위, 정밀도, 이상치 규칙 선언 여부 등. 원문 확인 후 정의. |

나머지 항목은 같은 스키마로 시드한다. 시드 후 검증: 영역별 항목 수가 22/7/15/15/18/3, 자동 35 / 수기 45 와 맞는지 확인하고, 다르면 원문을 기준으로 삼는다.

### 8.5 조치 로드맵과 개선 시뮬레이션

- 항목 정의에 `remediation` (조치명, 난이도 `낮음/중간/높음`, 해결 절차, 이동 대상 화면)을 둔다. 여러 항목이 한 조치를 공유할 수 있으므로 `remediation_action` 과 항목을 N:M 으로 연결한다.
- 가산점 = 해당 조치로 해소되는 미충족 항목들의 `(1.0 − 현재 점수)` 합. 목업의 `+3.5`, `+2.5`, `+4.0`, `+2.0` 을 이 방식으로 재현할 수 있어야 한다.
- 우선순위 = 가산점 내림차순, 난이도 오름차순(동률 시). 수동 순서 조정도 허용.
- 시뮬레이션 API: 선택한 조치 id 집합을 받아 예상 총점과 충족률을 반환한다(`38.5점 → 50.5점 (63%)` 형태).
- 해결방안 패널의 `입력 →` 링크는 대상 데이터셋과 필드까지 딥링크한다(STEP 6 의 `FIX_ROUTE` 방식 재사용, 128~138행).

### 8.6 진단 실행 흐름

1. 클라이언트: `POST /api/diagnoses` (대상 프로세스 id 목록, 가이드라인 버전, 모드 `full | auto_only`).
2. 서버: 대상 데이터셋 합집합을 데이터셋 id 기준으로 확정하고 각 정본의 체크섬을 기록한다(이름 기준 중복 제거는 쓰지 않는다).
3. 사전 조건 검사: 대상 데이터셋 전부가 STEP 6 검증을 통과했는지, STEP 7 발행 그래프가 있는지. 정책 결정 필요: 목업은 `독립 진단 업무` 라 하면서 게이트는 STEP 7 완료를 요구한다. 제안은 "진단은 언제든 실행 가능, 프로세스 종료 확정은 STEP 6/7 완료 시에만 허용".
4. 비동기 작업(Celery/RQ 또는 FastAPI BackgroundTasks): 그래프 로드 → pySHACL 실행 → SPARQL 항목 실행 → 프로파일 항목 평가 → 수기 항목 이월 → 집계 → `prov:Activity` 기록(실행자, 시작/종료 시각, 사용 엔티티 = 정본 체크섬 목록, shape 세트 버전, 가이드라인 버전).
5. 상태: `queued → running → done | failed`. 프런트는 폴링 또는 SSE 로 `대기 — 진단 미실행` / `⟳ 진단 실행 중…` / `✓ 진단 완료 — {프로세스명}` 을 표시한다.
6. 완료 시 프로세스 종료 확정을 같은 트랜잭션 경계에서 처리할지 별도 버튼으로 분리할지 결정한다. 제안: 분리. 목업은 재진단할 때마다 종료 저장과 로그를 반복하므로, 실제 제품에서는 `POST /api/processes/{id}/finalize` 를 멱등으로 만들고 수기 항목 미확정 건수가 남아 있으면 확인 모달을 띄운다.
7. 무효화: 정본, 조합, 분류, 리니지가 바뀌면 최신 진단을 `stale` 로 표시한다(삭제하지 않는다). 진단 이력은 보존한다.

### 8.7 보고서 저장과 내보내기

- 진단 실행 1회 = 불변 스냅숏 1건. 항목 결과, 증거 참조, 집계, 로드맵, 대상 데이터셋과 체크섬, 엔진/shape/가이드라인 버전을 함께 저장한다.
- PDF: 서버 렌더링(WeasyPrint 또는 headless Chromium). 구성은 표지, 총점 게이지, 영역별 충족률, 판정 방식별 집계, 항목별 판정과 증거 목록, 미흡 요약, 조치 로드맵, 개선 시뮬레이션, 서명란.
- 산출물 저장소에 `report` 유형 아티팩트로 등록하고 `prov:wasGeneratedBy` 로 진단 Activity 에 연결한다. 기계 판독용 JSON-LD(DQV `dqv:QualityMeasurement` 또는 EARL `earl:Assertion`)도 함께 내보내면 진단 결과 자체가 카탈로그 그래프의 일부가 된다.
- 재진단(`auto_only`): 자동 항목만 재계산하고 수기 항목은 최근 확인값을 이월한다(목업 문구 `자동판정 35항목 즉시 재계산 · 수기 45항목은 최근 확인값 유지`). 이전 실행과의 차이(항목별 변화, 점수 증감)를 반환한다.

### 8.8 API 엔드포인트 제안

| 메서드/경로 | 용도 |
|---|---|
| `GET /api/guidelines` | 가이드라인 버전 목록(적용 버전, 최신 버전, 색인일) |
| `GET /api/guidelines/{version}/areas` | 영역 목록과 항목 수 |
| `GET /api/guidelines/{version}/items?area=&resolver=&level=` | 항목 카탈로그 |
| `PUT /api/guidelines/{version}/items/{item_id}/resolver` | 리졸버 정의 수정(관리자) |
| `GET /api/processes?status=` | 호출 칩용 프로세스 목록(진행 중/종료, 데이터셋 수) |
| `POST /api/diagnoses` | 진단 실행 생성. body: `{ process_ids: [], guideline_version, mode }` → `202 { run_id }` |
| `GET /api/diagnoses/{run_id}` | 상태, 총점, 충족률, 자동/수기 충족률, 영역별 집계, 방식별 집계, 대상 요약 |
| `GET /api/diagnoses/{run_id}/items?area=&resolver=&verdict=&dataset_id=` | 항목별 판정 목록 |
| `GET /api/diagnoses/{run_id}/items/{item_id}` | 항목 상세(데이터셋별 판정, 증거, 조치) |
| `POST /api/diagnoses/{run_id}/items/{item_id}/attestations` | 수기 판정 + 증빙 첨부 + 서명 |
| `GET /api/diagnoses/{run_id}/pending-attestations` | 사람 확인 대기 목록 |
| `POST /api/diagnoses/{run_id}/rerun` | 재진단(`auto_only` 기본), 차이 반환 |
| `GET /api/diagnoses/{run_id}/roadmap` | 조치 우선순위 로드맵 |
| `POST /api/diagnoses/{run_id}/simulate` | body: `{ action_ids: [] }` → 예상 점수 |
| `POST /api/diagnoses/{run_id}/report` | PDF/JSON-LD 보고서 생성 → 아티팩트 id |
| `GET /api/reports/{report_id}/download` | 보고서 다운로드 |
| `GET /api/processes/{id}/diagnoses` | 프로세스의 진단 이력 |
| `POST /api/processes/{id}/finalize` | 프로세스 종료 확정(멱등, Activity 기록) |
| `GET /api/diagnoses/{run_id}/events` | SSE 진행 상태 |
| `GET /api/uri-mint/policy`, `GET /api/uri-mint/map?process_id=` | URI 민팅 카드용 네임스페이스, 형식, 치환 맵 |

### 8.9 데이터 모델 엔티티 제안 (PostgreSQL)

| 테이블 | 주요 컬럼 |
|---|---|
| `guideline_version` | `id`, `name`, `version`, `published_at`, `is_active`, `source_doc_uri`, `indexed_at` |
| `guideline_area` | `id`, `guideline_version_id`, `code`, `name`, `sort_order`, `expected_item_count` |
| `guideline_item` | `id`, `area_id`, `code`, `title`, `description`, `level` (`required/recommended/optional`), `basis_ref` (예: `표9`, `원칙 8`, `부록3`), `scope` (`dataset/process/system`), `applies_when` (JSONB 조건: 데이터 유형, 스트림 여부, 개인정보 포함 등), `weight` (기본 1.0) |
| `item_resolver` | `id`, `item_id`, `kind` (`AUTO_GRAPH/AUTO_PROFILE/HUMAN_ATTEST`), `shape_iri`, `sparql`, `profile_metric`, `operator`, `threshold`, `partial_rule` (JSONB), `evidence_query`, `attest_valid_days`, `version` |
| `shape_set` | `id`, `version` (목업 표기 `rs-2.1`), `ttl`, `checksum` |
| `diagnosis_run` | `id`, `guideline_version_id`, `shape_set_id`, `mode`, `status`, `started_at`, `ended_at`, `requested_by`, `activity_iri`, `total_score`, `max_score`, `auto_rate`, `manual_rate`, `baseline_score`, `is_stale`, `previous_run_id` |
| `diagnosis_run_process` | `run_id`, `process_id` |
| `diagnosis_run_dataset` | `run_id`, `dataset_id`, `canonical_checksum`, `graph_snapshot_ref` |
| `diagnosis_item_result` | `id`, `run_id`, `item_id`, `dataset_id` (system 범위면 null), `verdict` (`MET/PARTIAL/UNMET/NA/UNKNOWN`), `score`, `resolver_kind`, `message`, `carried_from_result_id` |
| `diagnosis_area_score` | `run_id`, `area_id`, `item_count`, `applicable_count`, `score`, `rate`, `auto_count`, `manual_count` |
| `evidence` | `id`, `result_id`, `kind` (`shacl_result/sparql_binding/profile_metric/prov_activity/file`), `ref` (IRI 또는 아티팩트 id), `payload` (JSONB), `collected_by` (`system/user`) |
| `attestation` | `id`, `result_id`, `verdict`, `comment`, `signed_by`, `signed_at`, `activity_iri`, `expires_at` |
| `remediation_action` | `id`, `guideline_version_id`, `title`, `difficulty`, `basis_text`, `steps` (JSONB), `target_route` (JSONB) |
| `remediation_action_item` | `action_id`, `item_id` |
| `diagnosis_roadmap_entry` | `run_id`, `action_id`, `rank`, `gain`, `affected_item_count` |
| `report_artifact` | `id`, `run_id`, `format` (`pdf/jsonld`), `storage_uri`, `checksum`, `created_by`, `created_at` |
| `process` | `id`, `name`, `status` (`in_progress/finished`), `current_step`, `finished_at`, `finished_by`, `finish_activity_iri`, `latest_diagnosis_run_id` |
| `prov_activity` | `iri`, `type`, `started_at`, `ended_at`, `agent_iri`, `used` (JSONB), `generated` (JSONB) |
| `uri_mint_map` | `temp_id`, `stable_iri`, `kind` (`DST/SVC/PLN/MDL/…`), `minted_at`, `activity_iri` |

### 8.10 프런트엔드(React) 구성 제안

| 컴포넌트 | 대응 목업 영역 | 데이터 |
|---|---|---|
| `ProcessCallBar` | 2.2 | `GET /api/processes`, 다중 선택 상태는 URL 쿼리 또는 서버의 진단 초안에 보관 |
| `DiagnosisStatusBar` | 2.3 | 실행 상태, 실행 버튼 |
| `ResolverSummaryCard` | 2.5(b) 좌 | 방식별 집계, 대기 건수 클릭 시 수기 확인 목록으로 이동 |
| `UriMintCard` | 2.5(b) 우 | 민팅 정책과 치환 맵 |
| `ScoreGauge` | 2.5(c) 좌 | 총점, 충족률(호 좌표 산식은 4.1절 그대로 사용 가능) |
| `AreaRateList` | 2.5(c) 우 | 영역 행 클릭 시 항목 목록 필터 |
| `ItemResultTable` (신규) | 목업에 없음 | 80항목 판정 목록, 증거 드로어, 수기 서명 폼. 실제 제품의 핵심 화면이므로 추가가 필요하다. |
| `GapCards` | 2.5(d) | 가산점 상위 미흡 항목 3건을 동적으로 표시 |
| `RoadmapTable` + `RemediationPanel` | 2.5(e) | 로드맵, 해결방안 |
| `ImprovementSimulator` | 2.5(f) | 조치 선택 → 예상 점수 |
| `ReportActions` | 2.5(g) | PDF 내보내기, 재진단 |

### 8.11 구현 전 결정이 필요한 사항

1. 80항목 원문과 영역별 항목 수(4.6절 #2, #3)를 무엇으로 확정할 것인가. 적용 버전을 v1.1 로 할지 v1.2 로 할지.
2. STEP 8 진입 조건: 독립 업무로 열어 둘지, STEP 7 완료를 요구할지.
3. 프로세스 종료 확정 시점: STEP 7 완료, STEP 8 진단 완료, 별도 확정 버튼 중 무엇인가. 수기 항목 미확정 상태에서 종료를 허용할지.
4. 결합 호출 진단의 귀속: 목업은 `A + B` 라는 새 프로세스를 만든다. 실제 제품에서는 진단 실행이 여러 프로세스를 참조하는 구조(`diagnosis_run_process`)로 두고 새 프로세스는 만들지 않는 것을 제안한다.
5. 항목 점수의 데이터셋 간 집계 방식(8.3절 대안)과 `NA`, `UNKNOWN` 처리.
6. 시스템 범위 항목(API 계층, MCP, 피드백 체계)을 프로세스 진단 점수에 포함할지, 기관 수준 점수로 분리할지.
7. 등급 밴드와 색상 임계값.
8. 발행 승인을 STEP 8 에 둘지(STEP 7 버튼 문구는 `발행 승인으로 →`), STEP 6/7 에 유지할지.
