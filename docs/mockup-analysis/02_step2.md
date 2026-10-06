# STEP 2 기능 명세: 조합 조정 · 보정 · 확정 + 작업 프로세스 관리

- 분석 대상: `src/markup.html` 365~474행 (STEP 2), 프로세스 관련 UI는 157~202행(STEP 1 동일 패널), 2932~3015행(데이터 카탈로그 > 산출물 저장소·프로세스 관리), 3876~3893행(하단 고정 바·토스트)
- 로직: `src/logic.js` 단일 클래스. 아래 행 번호는 모두 `logic.js` 기준
- 표기 규칙: 화면 문구·토스트·로그는 원문 그대로 인용. `{x}`는 런타임 치환 값

---

## 1. 화면 목적

1. STEP 1에서 선택(☑)하거나 AI 추천으로 인계받은 데이터셋 후보를 「내 작업 조합」(`state.combo`)에 넣고 빼서 결합 대상 집합을 조정한다.
2. 조합에 제목(`dcterms:title`)과 설명(`dcterms:description`)을 붙여 「조합 확정」한다. 확정이 STEP 3~6 진입의 유일한 게이트다 (`stepGate`, 324~342행).
3. 확정된 제목은 조합 이름(`comboName`)이 되고, 살아 있는 저장 프로세스 이름이 없을 때 현재 프로세스 이름으로도 쓰인다 (935행).
4. 화면 상단의 「작업 프로세스」 패널에서 저장된 프로세스 목록을 보고, 체크해서 포함 데이터셋을 미리 보고, 「불러오기」로 다른 프로세스의 STEP 1~7 작업 상태로 전환한다. 삭제·휴지통은 이 화면이 아니라 데이터 카탈로그 > 산출물 저장소에서만 한다.

화면에 "보정(규칙엔진 경고)", "데이터 풀", "추천 데이터셋 조합"이 자리만 잡혀 있고 전부 정적 빈 상태다. 실제 동작하는 것은 후보 → 조합 이동, 조합 확정, 프로세스 목록·불러오기뿐이다 (7장 참조).

문서 구성: 요청된 7개 항목에 더해, 다른 화면에 흩어져 있는 프로세스 관리 로직을 5장으로 따로 묶었다. 그래서 상태 변수는 6장, 시뮬레이션 구분은 7장, 실제 제품 요구는 8장이다.

---

## 2. 화면 구성 (위 → 아래)

표시 조건: `show2 = s.plane === 'studio' && s.step === 2` (1405행). 컨테이너 최대 폭 1080px.

### 2.1 제목

- `STEP 2: 조합 조정 · 보정 · 확정`
- 좌측 사이드바 단계 라벨은 `조합 조정·확정` (377행 `labels[1]`)

### 2.2 작업 프로세스 패널 (markup 369~404, STEP 1의 157~202와 동일 구조)

| 요소 | 원문 라벨 | 바인딩 |
|---|---|---|
| 현재 프로세스 표시 | `작업 프로세스:` + 칩 `{procCurName}` | `procCurName` (978행) |
| 보조 설명 | `STEP 1~7 작업 상태(업로드·선택·조합·분류·검증·직렬화)가 프로세스 단위로 저장·복원됩니다` | 정적 |
| 목록 토글 버튼 | `프로세스 목록 ({procCount}건) {procListCaret}` (캐럿 `▾`/`▴`) | `procListToggle`, `procCount`, `procListCaret` (979, 1007~1008행) |

`procListOn`(= `!!s.procOpen`)일 때 펼쳐지는 영역:

| 요소 | 원문 라벨 | 바인딩 |
|---|---|---|
| 빈 목록 안내 (`procEmpty`) | `저장된 프로세스가 없습니다 — 프로세스가 완료된 뒤 새 데이터셋을 선택하면 자동 저장되어 목록에 담깁니다` | 980행 |
| 프로세스 행 (반복 `procRows`) | 체크박스 + **`{pr.name}`** + `· {pr.meta}` + 버튼 `불러오기` | `pr.chk`, `pr.chkToggle`, `pr.load`, `pr.rowStyle` (1069~1080행) |
| 선택 프로세스 미리보기 (`pvOn`) | `☑ 선택한 프로세스의 데이터셋 — {pvLabel} · {pvCount}건` | 1056~1068행 |
| 미리보기 행 (반복 `pvDs`) | 칩 `{pd.proc}` + **`{pd.name}`** + `연계키 {pd.keys}` | 1061행 |
| 안내문 | `ⓘ 불러오기 시 현재 작업은 자동으로 임시저장된 뒤 해당 프로세스의 STEP 1~7 상태로 전환됩니다 · 프로세스 삭제·휴지통 관리는 데이터 카탈로그 > 산출물 저장소에서 —` + 링크 `이동 →` | `goCatalog` (478행) |

`pr.meta` 형식 (1071행): `{savedAt} 저장 · 데이터셋 {count}건 · ` + (`done` 이면 `✔ 프로세스 종료 (STEP 7 완료)`, 아니면 `STEP {step} 진행`)

`pr.rowStyle`: 체크된 행은 테두리 `#A9C0FF` + 배경 `#F3F6FF`, 아니면 테두리 `#E5E7EB`.

STEP 1 패널에만 있는 추가 요소 (157~173행): 「새 프로세스 시작」 확인 모달 (`procAskOn`). 5.3절 참조.

### 2.3 안내 문구

- `AI 제안 조합에서 데이터셋을 끌어와 내 작업 조합을 구성합니다. 확정 시 Classification Activity가 자동 기록됩니다.`

### 2.4 보정 경고 영역 (markup 406~408)

- `upEmpty`(= `!s.upFile`, 2160행)일 때만: `보정 경고 없음 — 조합 구성 후 규칙엔진이 표기·좌표계·시간포맷 불일치를 여기에 표시합니다`
- 업로드 파일이 있으면 이 영역은 아무것도 그리지 않는다. 경고를 실제로 표시하는 마크업·로직은 없다.

### 2.5 3단 그리드 (300px / 1fr / 1fr)

#### (좌) 데이터 풀 — 전부 정적, 핸들러 없음 (markup 410~420)

- 제목 `데이터 풀` + `· 가져올 수 있는 데이터 0건` (0은 하드코딩)
- 검색 입력 placeholder `데이터셋 검색…` (바인딩 없음)
- 필터 칩 4개: `전체`(선택 상태 고정) · `레이크` · `공공데이터포털` · `MCP` (클릭 핸들러 없음)
- 빈 상태: `데이터 풀이 비어 있습니다 — 레이크 적재·외부 소스 연계(공공데이터포털·MCP) 후 목록이 채워집니다`

#### (중) AI 제안 조합 (markup 421~440)

| 요소 | 원문 라벨 | 조건·바인딩 |
|---|---|---|
| 제목 | `AI 제안 조합` | 정적 |
| 범위 배너 (좁힘) | `◉ 「{cands2ProcName}」 범위 — 이 프로세스의 STEP 1 선택·조합 데이터셋만 표시합니다 ·` + 링크 `전체 후보 보기` | `cands2Scoped` (2207행), `cands2Toggle` (2212행) |
| 범위 배너 (전체) | `전체 후보 표시 중 — 프로세스 범위 밖 데이터셋 포함 ·` + 링크 `「{cands2ProcName}」 범위로 좁히기` | `cands2Wide` (2208행) |
| 빈 상태 | `제안 없음 — STEP 1에서 파일을 업로드하면 조합 후보가 여기에 나타납니다` | `step2CandsEmpty` (2206행) |
| 후보 카드 (반복 `step2Cands`, draggable) | **`{uf.name}`** / `{uf.type}` | 2162~2200행 |
| 카드 내 배지 | `✓ 조합에 포함됨` | `uf.inCombo` |
| 추가 버튼 (title `내 작업 조합으로 이동`) | `내 작업으로 →` | `uf.notInCombo`, `uf.add` |
| 되돌리기 버튼 (title `내 작업 조합에서 빼고 AI 제안으로 되돌리기`) | `← 제안으로 되돌리기` | `uf.inCombo`, `uf.remove` |
| 소제목 | `추천 데이터셋 조합` + 배지 `AI` | 정적 |
| 빈 상태 (고정) | `추천 조합 없음 — 데이터 풀·업로드 데이터가 쌓이면 연계키 기반으로 제안됩니다` | 정적 |

후보 카드 색 (`uf.sugStyle`, 2197행): 조합 포함 = 테두리 `#bfe3cc`·배경 `#f7fbf8`(녹색) / STEP 1 선택분 = `#A9C0FF`·`#F3F6FF`(파랑) / 그 외 = `#E5E7EB`·`#FAFBFC`(회색).

#### (우) 내 작업 조합 (markup 441~469, 패널 전체가 드롭 영역, 파란 2px 테두리)

| 요소 | 원문 라벨 | 바인딩 |
|---|---|---|
| 제목 | `내 작업 조합 — {comboName}` + 보조 `{comboSrcLabel}` | 2040, 2263행 |
| 건수 | `{comboCount}개 데이터셋` | 647행 |
| 조합 항목 카드 (반복 `comboList`) | **`{c.name}`** + 배지 `AI 추천`(`c.isAi`) 또는 `작업자 선택`(`c.isMan`) / `연계키 {c.keys}` + 배지 `검토`(`c.warn`) / 링크 `제거` | 648~651행 |
| 드롭 존 | `여기로 드래그하여 추가 (좌측 카드를 끌어오거나 + 추가 클릭)` / `⌨ 키보드: "+ 추가" 버튼으로 동일 동작 가능` | `dragOver`, `dropCombo` (654~660행) |

문구 불일치: 드롭 존은 "+ 추가" 버튼을 언급하지만 실제 버튼 라벨은 `내 작업으로 →` 다.

조합 확정 카드 (markup 452~468):

| 요소 | 원문 라벨 | 바인딩 |
|---|---|---|
| 제목 | `조합 확정 — 결합 데이터셋 최소 메타데이터` + 배지 `dcterms:title · description` | 정적 |
| 설명 | `확정 시 이 조합이 하나의 작업 단위가 되어 STEP 3 카탈로그 초안 · 프로세스 이름 · 산출물 저장소에 이어집니다 (prov:Activity 기록)` | 정적 |
| 제목 입력 | placeholder `① 제목 — 예: 도로링크·기상 결합 데이터셋` | `cmTitle`, `cmTitleSet` (change 이벤트) |
| 설명 입력 (textarea, 2행) | placeholder `② 개요·설명 — 조합 목적, 포함 데이터셋, 연계키를 한두 문장으로` | `cmDesc`, `cmDescSet` (change 이벤트) |
| AI 초안 표시 (`cmAiTag`) | `✦ sLLM 초안이 채워졌습니다 — 검수 후 수정하여 확정하세요 (초안은 조합 구성·연계키에서 결정적 생성)` | 2050행 |
| AI 초안 버튼 (title `조합 구성·연계키를 근거로 제목·설명 초안 생성 (sLLM-molit-7b)`) | `✦ AI 초안` | `cmAi` (2053~2061행) |
| 확정 버튼 | `조합 확정 → STEP 3 인계 ({comboCount}건)` | `cmConfirm`, `cmBtnStyle` (2062~2072행) |
| 확정 완료 표시 (`cmDone`) | `✓ 「{cmTitle}」 확정됨 · {cmAt} — 수정 후 재확정 가능 · STEP 3 카탈로그와 프로세스 이름에 인계됨` | 2048~2049행 |

### 2.6 하단 고정 바 (스튜디오 평면 공통, markup 3876~3889)

`이전` / `{wipeLabel}`(기본 `데모 데이터 지우기`) / `↺ 데모 데이터 복구` / `⤓ 파일로 저장` / `⤒ 파일 불러오기` / `{tempSaveLabel}`(`임시저장` ↔ `✓ 임시저장`) / `다음 (확정)`

---

## 3. 사용자 동작 → 결과

토스트 공통: `state.toast = true`, `state.toastText = 문구`, 타이머 후 `toast:false, toastText:null`. 표시 문구는 `toastMsg = s.toastText || '✓ prov:Activity ' + toastId + ' 기록됨'` (1708행).

주의: 마크업은 `{{ toastOn }}`으로 토스트를 표시하는데 `logic.js` 어디에도 `toastOn` 정의가 없다. 런타임이 `vals = {...props, ...renderVals()}` 구조이므로 prop으로 주입되지 않으면 토스트가 보이지 않는다. 실제 제품에서는 토스트 표시 상태를 명시적으로 바인딩해야 한다.

로그 공통 `logAct(who, txt, actId)` (53~61행): `actId`에 "신규"가 들어 있으면 버리고 `ACT-K-{actSeq+1, 4자리}`를 새로 발급(시작값 0421), `actLog`는 최근 10건만 유지.

### 3.1 화면 진입

| 경로 | 조건 | 실패 시 |
|---|---|---|
| 사이드바 STEP 2, 홈 칩, `goStep2Home`, `goStep2Task`, STEP 1의 `다음 (확정)` | `stepGate(2).canEnter` = `manSel`에 true가 1건 이상 **또는** `combo.length > 0` (333행) | 토스트 `🔒 STEP 2 잠김 — STEP 1에서 후보를 1건 이상 선택하세요` (3000ms), 이동 취소 (6~15행) |
| STEP 6 결과표 `[수정하러 이동]` (`FIX_ROUTE.identity`, `FIX_ROUTE.mint` → step 2) | 동일 게이트 | 동일. 도착 후 STEP 2에는 `fixField` 하이라이트 대상 요소가 없다 |

`go()`는 단계·평면 이동 시 `savedHere=false`로 만들고 400ms 디바운스로 `persistDraft()`(localStorage `fde-studio-draft`)를 호출한다 (16~20행).

### 3.2 프로세스 패널

| 동작 | 상태 변화·계산 | 토스트·로그 |
|---|---|---|
| `프로세스 목록 (N건)` 클릭 | `procOpen` 토글 (`go`) | 없음 |
| 행 체크박스 변경 | `procViewSel[p.name]` 토글 (1073행). 체크된 프로세스들의 `snapshot.combo`를 펼쳐 `pvDs = [{proc, name: d.n, keys: d.k \|\| 'K7'}]`, `pvLabel = 이름들을 ' + '로 연결`, `pvCount = pvDs.length`. 조회 전용이며 조합에는 영향 없음 | 없음 |
| `불러오기` 클릭 (1076~1080행) | ① `saveCur()`로 현재 작업을 목록에 upsert (5.2절). 빈 작업이어도 저장된다 ② `setState({...blank(), ...p.snapshot, procName: p.name, procOpen: false, cands2All: false, taskProcSel: null, plane: 'studio'})` ③ `persistDraft()`. 단계는 스냅숏의 `step`으로 복원 | 토스트(3000ms): `↺ 프로세스 「{p.name}」 불러옴 — 저장 시점 STEP {p.step} 상태로 복원 (현재 작업은 자동 저장됨)`. 로그 없음 |
| `이동 →` 클릭 | `go({plane: 'catalog', catDetail: false})` | 없음 |

불러오기의 한계 (재구현 시 고쳐야 할 점):
- `blank()`와 스냅숏에 검증 상태(`v7State`, `v6Results`, `v6Stale`, `svResults`, `v8State`)와 STEP 3 승인 입력(`metaOver`)이 들어 있지 않다. 따라서 불러온 뒤에도 이전 프로세스의 검증 결과·정본 덮어쓰기가 남는다. `outGroups.goLast`·`taskProcOpts`는 `v7State/v8State`를 명시적으로 null 처리하지만 `load`는 하지 않는다.
- 불러온 뒤 `stepGate` 재평가가 없다 (재평가는 새로고침 복원 시에만, 81~85행).
- 구버전 스냅숏(ver 없음)의 6↔7 단계 번호 매핑은 `goLast`에만 있고 `load`에는 없다 (871행).
- 현재 프로세스와 같은 이름을 불러오면 `saveCur()`가 목록 항목을 새 스냅숏으로 바꾼 직후, 클로저에 남아 있던 옛 스냅숏으로 상태가 되돌아간다.

### 3.3 후보 → 조합

| 동작 | 상태 변화·계산 | 토스트·로그 |
|---|---|---|
| `전체 후보 보기` / `「…」 범위로 좁히기` | `cands2All` 토글 (`go`) | 없음 |
| `내 작업으로 →` | `addCombo({n: it.nm, k: it.k})` (37~41행): 같은 `n`이 있으면 무시, 없으면 `combo` 끝에 추가 후 `invalidateDownstream('combo', …)` | 하류 상태가 있을 때만 (아래) |
| 후보 카드 드래그 시작 | `dataTransfer.setData('text/plain', it.nm)`, `this._dragName = it.nm` (2196행) | 없음 |
| 조합 패널·드롭 존에 드롭 (654~660행) | `this._drag` 객체가 있으면 그것을, 없으면 이름만으로 `addCombo({n: nm, k: 'K7'})` | 동일 |
| `← 제안으로 되돌리기` | `combo`에서 `n === it.nm` 제거 후 `invalidateDownstream('combo', …)` (2195행) | 동일 |
| 조합 카드 `제거` | `combo`에서 해당 인덱스 제거 후 `invalidateDownstream('combo', …)` (650행) | 동일 |

`invalidateDownstream('combo', msg)` (344~356행):
- `v7State`, `convertState`, `v8State`가 모두 비어 있고 `v6Results`도 없으면 아무 일도 하지 않는다 (346행).
- 그렇지 않으면 `{v6Results: null, v7State: null, v6Stale: false, convertState: null, svResults: null, v8State: null}` 적용 + `persistDraft()`.
- 토스트(3000ms)와 로그(`who='시스템'`) 문구가 같다: `조합 변경 — STEP 6·7 결과가 초기화되었습니다 (재검증 필요)`

주의할 동작:
- 드롭으로 추가하면 연계키가 항상 `'K7'`로 들어간다. 버튼(`uf.add`)은 후보의 실제 키(`it.k`)를 넣는다. 같은 후보라도 경로에 따라 키가 달라진다.
- 드롭 핸들러가 바깥 패널과 안쪽 드롭 존 양쪽에 걸려 있어 안쪽에 떨어뜨리면 버블링으로 두 번 호출된다. 중복 검사가 `this.state.combo`(갱신 전 값)를 보므로 중복 추가 가능성이 있다. 서버에서 (조합, 데이터셋) 유일 제약이 필요하다.
- 스트림 묶음 후보는 주석상 "하위 데이터셋 전체가 한 단위로 들어간다"지만 실제로는 `{n: 묶음이름, k: 키 합집합}` 1건만 들어가고 `group`(구성원)은 전달되지 않는다.
- 조합을 바꿔도 `comboMeta.done`은 그대로다. 확정 후 항목을 추가·제거해도 재확정 없이 STEP 3 이후가 열려 있다. 전부 제거하면 `combo.length === 0`이라 잠기지만, 1건을 다시 넣는 순간 옛 제목으로 다시 열린다.
- STEP 3 완료 표시 `ds3Done`은 조합 인덱스 키(`{"0": true}`)라서 중간 항목을 제거하면 완료 표시가 다른 데이터셋으로 밀린다.

### 3.4 조합 확정 카드

| 동작 | 상태 변화·계산 | 토스트·로그 |
|---|---|---|
| 제목 입력 변경 (`cmTitleSet`, 2051행) | `comboMeta = {...comboMeta, title: v, ai: false, done: false}` | 없음 |
| 설명 입력 변경 (`cmDescSet`, 2052행) | `comboMeta = {...comboMeta, desc: v, done: false}` (`ai` 유지) | 없음 |
| `✦ AI 초안` (`cmAi`, 2053~2061행) | 조합이 비면 무동작. 아니면 `comboMeta = {...comboMeta, ai: true, done: false, title, desc}` 로 덮어쓴다 (4.6절 템플릿) | 없음 |
| `조합 확정 → STEP 3 인계 (N건)` (`cmConfirm`, 2063~2072행) | 게이트: `title.trim()`이 비었거나 `combo.length === 0`이면 무동작 (버튼은 회색 `not-allowed`, 설명은 선택). 통과 시 `go({comboMeta: {...m, title: trim값, done: true, at: nowHM()}, comboName: title, v6Results: null, v7State: null, v6Stale: false, convertState: null, svResults: null, v8State: null, plane: 'studio', step: 3, tab3: 1})` | 로그: who `홍길동 (나)`, `조합 확정 「{title}」 — {N}건 · dcterms:title/description 입력`, actId 인자 `ACT-CMB-신규`(→ `ACT-K-xxxx`로 대체 발급). 토스트(3200ms): `✓ 조합 확정 — 「{title}」 제목·설명이 STEP 3 카탈로그와 프로세스 이름에 인계됩니다 (prov:Activity 기록)` |

규칙 요약:
- 제목·설명을 한 글자라도 바꾸면 `done=false`가 되어 STEP 3~6이 다시 잠긴다 (`comboOk`, 327행). 재확정이 필요하다.
- `cmConfirm`의 `go()`는 `patch.comboMeta.done`이 참이라 중앙 게이트를 우회한다 (8행). 확정과 STEP 3 이동이 한 번에 일어난다.
- 재확정은 하류(검증·변환·진단) 결과를 무조건 초기화한다. `ds3Done`, `dsDone4` 등 STEP 3~5 작업은 건드리지 않는다.
- `comboMeta.title/desc`가 소비되는 곳: STEP 3 상단 배너(markup 499행 `✓ STEP 2 확정 메타데이터 인계 — dcterms:title 「…」 · dcterms:description 「…」 — ② 프러퍼티 폼 초안과 프로세스 이름에 반영됨`)와 프로세스 이름 계산(935행)뿐이다. `buildCanonical`/`buildTriples`(164~212행)는 조합 제목·설명을 쓰지 않는다. 즉 결합 데이터셋 자체는 RDF 정본에 나오지 않는다.

### 3.5 하단 바 (STEP 2에서의 동작)

| 동작 | 결과 |
|---|---|
| `이전` (`prevStep`, 2957~2964행) | `persistDraft()` 후 `go({step: 1})` |
| `다음 (확정)` (`nextStep`, 2965~2994행) | ① `autoSave()`: `saveTime = HH:MM` + `persistDraft()` ② `showToast()`: 가짜 ID `ACT-K-0400~0498` 난수 발급, 토스트 `✓ prov:Activity {toastId} 기록됨` (2200ms). `actLog`에는 기록되지 않는다 ③ `go({step: 3, notify: {from: 'STEP 2', to: 'STEP 3', owner: '메타데이터 표준화팀'}})`. 조합 미확정이면 게이트에 막혀 토스트 `🔒 STEP 3 잠김 — STEP 2 조합 확정을 먼저 완료하세요` (3000ms). 통과하면 알림 팝업이 5초 표시 |
| `임시저장` (`tempSave`, 3111~3122행) | `saveTime`, `savedHere=true`, localStorage 저장. 토스트 `💾 임시저장되었습니다 · {HH:MM} — 브라우저에 보관되어 새로고침 후에도 복원됩니다 (파일 원본은 재첨부 필요)` 또는 `⚠ 임시저장 실패 — 브라우저 저장 공간을 확인하세요` |
| `데모 데이터 지우기` (`wipeDemo`, 982~994행) | 1차 클릭: `wipeAsk=true`, 라벨 `정말 전부 지울까요? (다시 클릭)`, 4초 뒤 원복. 2차 클릭: localStorage 삭제, 모든 state 키를 undefined로, `{plane:'studio', step:1, tab3:1, cell:'none', edgesOpen:false, combo:[], procList:[], procTrash:[]}`. 토스트 `🗑 데모 데이터 삭제 완료 — 업로드·조합·프로세스 목록·임시저장이 초기화되었습니다` |
| `↺ 데모 데이터 복구` (`restoreDemo`, 995~1005행) | `window.__resources.demoSnap`(없으면 `./demo-snapshot.json`)을 fetch해 전체 state 교체. 토스트 `↺ 데모 데이터 복구 완료 — 2026-08-21 16:07 기준 스냅숏` / 실패 시 `⚠ 복구 실패 — demo-snapshot.json을 찾을 수 없습니다` |
| `⤓ 파일로 저장` / `⤒ 파일 불러오기` | 전체 state JSON 내보내기·가져오기 (3078~3106행). 파일명 `FDE-Studio-작업스냅숏-{YYYY-MM-DD-HH-MM}.json` |

담당 조직 알림 표 (2989행, 인덱스 = 도착 STEP - 1):
`['빅데이터센터 수집운영과', '빅데이터센터 수집운영과', '메타데이터 표준화팀', '메타데이터 표준화팀', '데이터 품질관리팀', '데이터 품질관리팀', '데이터 품질관리팀', '정보화기획담당관']`

---

## 4. 데이터 (하드코딩 목록 원문)

### 4.1 연계키(K축) 코드

과업 지시에는 K1~K7로 적혀 있으나 목업의 통제어휘는 **K1~K9 9종**이다 (731, 2381행).

| 코드 | 원문 라벨 (731행) | 의미 | 다른 곳의 표기 변형 |
|---|---|---|---|
| K1 | `K1 행정구역` | 행정구역 코드로 조인 | |
| K2 | `K2 주소` | 주소로 조인 (지오코딩 후보) | |
| K3 | `K3 좌표` | 좌표·공간 조인 | |
| K4 | `K4 건축물ID` | 건축물 식별자 | |
| K5 | `K5 도로링크` | 도로링크 ID (국가표준노드링크) | `K5 도로링크ID` (2374행, STEP 1 markup 332행) |
| K6 | `K6 차량ID` | 차량 식별자 | `K6 차량` (2509행) |
| K7 | `K7 시각` | 관측 시각 정렬 | `K7 시각(관측시점)` (markup 332행) |
| K8 | `K8 사업ID` | 사업 식별자 | |
| K9 | `K9 문서ID` | 문서 식별자 (자동 감지 실패 시 기본값) | |

분류체계 표의 K축 메타 (785행): `['K1~K9 연계키', '필수', 9, '행정구역 · 주소 · 좌표 · 건축물ID · 도로링크 · 차량ID · 시각 …', 'v2.0 (2026-05)', '개정 대기 1']`

조합 항목의 키 문자열 형식: `' · '`(공백 + 가운뎃점 + 공백)로 연결. 예 `'K5 · K6 · K7'`. 파싱은 `split('·').map(trim)` (2057, 2173행).

STEP 1 안내문 (markup 332행): `K = 연계키(조인 키) 9종 중 공유 축 — K5 도로링크ID · K6 차량ID · K7 시각(관측시점)`

### 4.2 이름 기반 연계키 배정 규칙 (목업의 "자동 감지")

(a) STEP 1 AI 추천 조합 인계 시 `kOf` (2254행):

| 데이터셋 이름 | 키 |
|---|---|
| `cctv.vehicle.det.v1` | `K5 · K6 · K7` |
| `kma.aws.obs.v1` | `K7 · K3` |
| 그 외 전부 | `K7` |

(b) 업로드 파일 후보의 키: 무조건 `K7` (2164행, 표시 문자열 `{f.type} · K7 후보`)

(c) STEP 4의 파일명 정규식 감지 (2374~2379행, 참고):

| 정규식 | key | col | note |
|---|---|---|---|
| `/도로/` | `K5 도로링크ID` | `ROAD_LINK_ID (감지)` | `표준: 국가표준노드링크 · 결합 후보 계산 대기` |
| `/도로\|공간\|경계\|좌표/` | `K3 좌표` | `GEOM / X·Y (감지)` | `좌표계 확인 필요 (EPSG 미선언)` |
| `/기상\|관측\|시간\|5분\|소통\|기록/` | `K7 시각` | `OBSV_DT / 관측일시 (감지)` | `ISO 8601 정규화 대상` |
| `/차량\|운행\|eTAS\|OBU/i` | `K6 차량ID` | `VHCL_NO (감지)` | `표기 방식 검수 필요` |
| `/사고/` | `K2 주소` | `ACDNT_ADDR (감지)` | `주소 → 좌표 지오코딩 후보` |
| (해당 없음) | `K9 문서ID` | `(자동 감지 실패)` | `수기 배정 필요 — 검수 큐 이동` |

(d) 카탈로그 목록의 분류·키 표기 `kOf2` (486행):

| 조건 | 값 |
|---|---|
| `cctv.vehicle.det.v1` | `교통물류 · K5 K6 K7` |
| `kma.aws.obs.v1` | `기상 컨텍스트 · K7 K3` |
| `/도로/` | `도로 · K5 K3` |
| `/사고/` | `교통물류 · K2 K7` |
| `/기상/` | `기타 · K7` |
| `/오픈마켓\|eTAS\|운행/i` 및 그 외 | `교통물류 · K7` |

### 4.3 스트림 묶음 기본 구성원 `MEM` / `DEFAULT_MEMBERS` (2165~2168, 1120~1125행)

```json
[
  { "n": "obu.telemetry.v2",    "k": "K6 · K7" },
  { "n": "TRAFFIC_LINK_5MIN",   "k": "K5 · K7" },
  { "n": "cctv.vehicle.det.v1", "k": "K5 · K6 · K7" },
  { "n": "kma.aws.obs.v1",      "k": "K7 · K3" }
]
```

- `synStreams`의 각 항목(탭)은 `members`가 없으면 위 4건을 구성원으로 갖는다. 묶음 키 = 구성원 키의 합집합(등장 순서) → 기본값 `K6 · K7 · K5 · K3`.
- `strmDemoHide === false`(데모 스트림 표시)일 때 단독 후보로 나오는 것은 `MEM.slice(2)`, 즉 `cctv.vehicle.det.v1`, `kma.aws.obs.v1` 2건뿐이다. 단, 어떤 묶음에도 속하지 않을 때만 나온다 (2177~2180행).

### 4.4 후보 목록 생성 규칙 `step2Cands` (2162~2200행)

1. `ups` = `upList`(없으면 `[upFile]`)의 각 파일 → `{key: f.name(확장자 포함), nm: 확장자 제거, type: f.type + ' · K7 후보', k: 'K7'}`
2. `strms` = `synStreams` 각 항목 → `{key: t.name, nm: t.name, type: '스트림 묶음 (하위 데이터셋 ' + N + '건) · ' + keys, k: keys, group: mem}` + (데모 표시 시) 단독 스트림 `{key: m.n, nm: m.n, type: '스트림 (데모) · ' + m.k, k: m.k}`
3. `all = [...strms, ...ups]`를 STEP 1 선택 여부(`manSel[key]`) 내림차순으로 정렬 (선택분 먼저)
4. 범위 필터: `procAlive && !cands2All`이면 `manSel[key]`가 참이거나 이미 조합에 있는 것만 남긴다. `procAlive` = `procName`을 `' + '`로 나눈 모든 이름이 `procList`에 존재 (2185행)
5. 각 항목의 `type` 뒤에 STEP 1 미선택이면 `' · STEP 1 미선택'`을 붙인다
6. `inCombo` = `combo.some(c => c.n === it.nm)`

`step2CandsEmpty` (2204~2206행)는 위 목록 길이가 아니라 별도 수식이다: `Σ(synStreams 구성원 수 또는 4) + ups.length + (데모 표시 ? 2 : 0) === 0`. 범위 필터 결과가 0건이어도 이 값이 0이 아니면 빈 상태 문구도 카드도 나오지 않는다 (`this._cands2Count`는 계산만 하고 쓰지 않음).

### 4.5 조합 항목 구조와 하드코딩 조합

조합 항목(`combo[]` 원소):

| 필드 | 타입 | 의미 |
|---|---|---|
| `n` | string | 데이터셋 이름. 사실상 식별자 (중복 검사, `META_TABLE`·`MINT_MAP`·`dsDone4`·`metaOver` 키) |
| `k` | string | 연계키 문자열 (`' · '` 구분) |
| `w` | boolean? | 검토 필요 → `검토` 배지 |
| `src` | `'ai'` \| `'man'`? | 출처. `ai` → `AI 추천` 배지, `man` → `작업자 선택` 배지. STEP 2에서 추가한 항목은 `src` 없음 |
| `meta` | object? | `getMeta2`가 `META_TABLE`보다 우선 사용 (144행). 목업에서 넣는 곳 없음 |

마크업에 연결되지 않은(미사용) 핸들러에 들어 있는 조합·데이터 풀 시드. 예전 버전의 "AI 제안 조합"과 "데이터 풀" 내용이므로 시드 데이터로 쓸 수 있다.

```json
{
  "loadComboRec1 (2279행)": {
    "comboName": "소통+돌발+기상",
    "combo": [
      { "n": "TRAFFIC_LINK_5MIN", "k": "K5 · K7" },
      { "n": "ADMIN_SGG 행정경계", "k": "K5" },
      { "n": "돌발상황 이력 (UTIC)", "k": "K5 · K7" },
      { "n": "기상관측 AWS 10분", "k": "K7" }
    ]
  },
  "loadComboRec2 (2284행)": {
    "comboName": "차량검사+OBU 텔레메트리",
    "combo": [
      { "n": "etas_inspect_log", "k": "K6 · K7" },
      { "n": "obu.telemetry.v2", "k": "K6 · K7", "w": true }
    ]
  },
  "pickComboA (2289행, STEP 2로 이동)": {
    "comboName": "도로링크+시각",
    "combo": [
      { "n": "TRAFFIC_LINK_5MIN", "k": "K5 · K7" },
      { "n": "ADMIN_SGG 행정경계", "k": "K5" }
    ]
  },
  "pickComboB (2294행, STEP 2로 이동)": {
    "comboName": "도로링크+차량+시각",
    "combo": [
      { "n": "TRAFFIC_LINK_5MIN", "k": "K5 · K7" },
      { "n": "etas_inspect_log", "k": "K6 · K7" },
      { "n": "obu.telemetry.v2", "k": "K6 · K7", "w": true }
    ]
  },
  "드래그 시드 (661~663행)": [
    { "handler": "dgTraffic", "n": "TRAFFIC_LINK_5MIN", "k": "K5 · K7" },
    { "handler": "dgAdmin",   "n": "ADMIN_SGG 행정경계", "k": "K5" },
    { "handler": "dgEtas",    "n": "etas_inspect_log", "k": "K6 · K7" }
  ],
  "데이터 풀 추가 시드 (664~668행)": [
    { "handler": "addVds",  "n": "VDS 검지기 5분 교통량", "k": "K5 · K7" },
    { "handler": "addUtic", "n": "돌발상황 이력 (UTIC)", "k": "K5 · K7" },
    { "handler": "addAsos", "n": "기상관측 ASOS 시간자료", "k": "K7" },
    { "handler": "addKtdb", "n": "KTDB 여객 OD 조사", "k": "K5" },
    { "handler": "addBis",  "n": "버스 BIS 정류장 도착", "k": "K6 · K7" }
  ]
}
```

`w: true`(obu.telemetry.v2)의 배경은 도우미 답변에 남아 있다 (3005행): `예: 88% 조합은 K6 차량ID 표기 불일치(CarID vs OBU_IDNT_NMBR)로 −6%p 감점 — STEP 2 경고 1번과 동일 건입니다.` 현재 STEP 2에는 그 "경고 1번"이 없다.

STEP 1에서 STEP 2로 넘기는 실제 경로 (참고):
- `pickComboUp` (2252~2260행): `manSel`이 참인 모든 키 → `{n: 확장자(xlsx|xls|csv|parquet) 제거, k: kOf(k), src: 'ai'}`, `comboSel: 'up'`, `comboName: 이름들을 '+'로 연결 후 60자 절단`, `ds3: 0, ds3Done: null, tab3: 1`. 묶음 이름과 그 구성원 이름이 모두 `manSel`에 있으므로 묶음과 구성원이 함께 조합에 들어갈 수 있다.
- `pickManual` (2272~2278행, 미연결): `{n, k: 'K7', src: 'man'}`, `comboSel: 'man'`, `comboName: 이름 '+' 연결 + ' (작업자 선택)'`

`comboSrcLabel` (2263행): 조합이 비면 `''`, `comboSel === 'man'`이면 `STEP 1 작업자 직접 선택`, 그 외 `comboSel`이 있으면 `STEP 1 AI 제안에서 인계`, 없으면 `''`.

`comboName` 표시값 (2040행): `combo.length ? (s.comboName || '작업 조합') : '(비어 있음)'`

### 4.6 AI 초안 템플릿 (2053~2060행)

```
nm    = combo.map(c => c.n)
short = nm.map(n => n.replace(/^sample_/i, '')
                     .replace(/[._-]v?\d+$/i, '')
                     .split(/[._]/)[0]).slice(0, 3)
keys  = 조합 전체 c.k를 '·'로 쪼갠 뒤 trim, 중복 제거, ' · '로 연결
title = short.join('·') + ' 결합 데이터셋'
desc  = '연계키 ' + (keys || 'K7') + ' 기준으로 ' + nm.join(', ') + ' ' + nm.length
        + '건을 결합한 작업 조합. 소통·컨텍스트 결합 분석을 위한 카탈로그 등록 대상.'
```

예 (데모 시드 조합): title `실시간교통사고·디지털운행기록분석시스템(eTAS) 결합 데이터셋`, desc `연계키 K6 · K7 · K5 · K3 기준으로 실시간교통사고, 디지털운행기록분석시스템(eTAS)_정보시스템 2건을 결합한 작업 조합. 소통·컨텍스트 결합 분석을 위한 카탈로그 등록 대상.`

### 4.7 프로세스 스냅숏 대상 키 `workKeys` (920행, 40개)

```json
["combo","comboName","comboMeta","comboSel","upList","upFile","manSel","upView",
 "ds3","ds3Done","ds3Fold","mainSel","clsSel","propSel","provSel","provRec",
 "clsDone","propDone","provDone","dsExtra","linkSeq","linkKnown","ds","dsDone4",
 "dist2","f1Sel","f2Sel","f3Sel","f4Sel","f5Sel","relPairs","dsGroups","fmts",
 "convertState","step","tab3","gran","pipe","nodeEdits","reviewFlags"]
```

- `blank()`이 지우지 않고 유지하는 키 (프로세스 간 공유 업로드 풀): `["upList","upFile","upView"]` (924행)
- `blank()` 결과: 나머지 37개 키 undefined + `{combo: [], step: 1, tab3: 1, ds3: 0, plane: 'studio'}`
- 스냅숏에 없는 프로세스 종속 상태: `v6Results, v7State, v6Stale, svResults, v8State, convertTime, convertTimeIso, metaOver, f6 관련, cands2All, procViewSel` 등

### 4.8 임시저장 제외 키 (93~95행)

```json
["toast","toastText","notify","restored","savedHere","ast","astChat","astInput","astW",
 "linkPick","relPick","relSel","ssotPick","taxAxisForm","taxCodeForm","taxAxisName",
 "taxCodeName","taxEditNewV","mapZoom","q4","batchOn","simMode","linAsk","linReason",
 "fixBack","fixField"]
```

### 4.9 산출물 저장소 포맷 태그 (812~817행, `outG` 그룹의 행 구성)

| tag | 배지 색 | 파일 접미 | MIME |
|---|---|---|---|
| `TTL` | `#E8EEFF;color:#1648D6` | `.ttl` | `text/turtle` |
| `JSON-LD` | `#e9e3f5;color:#5a4a8a` | `.jsonld` | `application/ld+json` |
| `문장화` | `#dff0ec;color:#1e6e50` | `_문장화.txt` | `text/plain` |
| `스키마` | `#fdf3e7;color:#b05c1a` | `_schema.json` | `application/json` |

- 파일명 베이스: `(ds.n || 'dataset').replace(/[^가-힣a-zA-Z0-9]+/g, '_').slice(0, 32)`
- 위치 표기: `s3://lake-ctrl/catalog/serialized/{base}{ext}`
- 활동 표기: 저장 프로세스 `ACT-SER-{id 끝 4자리} · #{체크섬 8자리}`, 진행 중 `ACT-미발급`, STEP 8 완료 `ACT-K-{actSeq 4자리}`
- 게이트 표기: 저장됨 `완료 · 저장 확정` / 변환 완료 `STEP 6 검증 ✓ · 파생 자가검증 ✓` / 그 외 `STEP 7 변환 대기`

### 4.10 조합 항목 이름이 참조하는 공용 표 (106~123행, 공통 모듈)

`META_TABLE` (키 = 데이터셋 이름. `kind`가 `stream`이면 `dcat:DataService` 병기):

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

`MINT_MAP` (발행 모드 ID 등록표):

```json
{
  "kma.aws.obs.v1": "SVC-000041",
  "cctv.vehicle.det.v1": "SVC-000042",
  "sample_공간정보_통합포털_데이터셋_목록_도로": "DST-000961",
  "실시간교통사고": "SVC-000043",
  "디지털운행기록분석시스템(eTAS)_정보시스템": "DST-000962"
}
```

STEP 2로 되돌아오는 위반 라우팅 (129~138행): `identity: { step: 2, label: '조합 확정 카드' }`, `mint: { step: 2, label: 'ID 발급 안내 · 관리 탭 민팅 정책' }`. STEP 2 마크업에는 "ID 발급 안내"에 해당하는 요소가 없다.

### 4.11 데모 스냅숏의 프로세스·조합 시드

파일: `/home/claude/fde_unpacked/resources/f02defb4-4178-4f75-bb03-944f77dca969.json` (`restoreDemo`가 불러오는 `demoSnap`, `exportedAt: 2026-08-21T16:07:13.563Z`)

```json
{
  "step": 2,
  "combo": [
    { "n": "실시간교통사고", "k": "K6 · K7 · K5 · K3" },
    { "n": "디지털운행기록분석시스템(eTAS)_정보시스템", "k": "K7" }
  ],
  "comboName": "실시간교통사고(스트림)",
  "comboSel": "up",
  "comboMeta": { "title": "실시간교통사고(스트림)", "ai": false, "done": true,
                 "desc": "실시간교통사고(스트림) 데이터와 교통사고 원인분석 데이터의 모음", "at": "23:31" },
  "procName": "실시간교통사고(스트림)",
  "procOpen": false, "procDelId": null, "procPurgeId": null, "procAsk": null,
  "procTrash": [],
  "procViewSel": { "1차 프로세스": false, "1차 프로세스 + 2차 프로세스": true },
  "outG": { "2차 프로세스 (진행 중)": false, "1차 프로세스 + 2차 프로세스 (진행 중)": true, "실시간교통사고(스트림) (진행 중)": false },
  "outOpen": true, "outDelId": null,
  "taskProcSel": ["실시간교통사고(스트림)"],
  "cands2All": false,
  "strmDemoHide": false,
  "synStreams": [ { "name": "실시간교통사고", "type": "관측", "rate": "수기 등록", "at": "22:55" } ],
  "upList": [
    { "name": "교통사고심층조사시스템(TAIS)_정보시스템.xlsx", "size": "20 KB", "type": "정형 (엑셀)", "profile": "스키마 자동추론 대기 · 20 KB 판독" },
    { "name": "교통혼잡_지역별_데이터.xlsx", "size": "19 KB", "type": "정형 (엑셀)", "profile": "스키마 자동추론 대기 · 19 KB 판독" },
    { "name": "도로_행정구역_공간정보.xlsx", "size": "17 KB", "type": "정형 (엑셀)", "profile": "스키마 자동추론 대기 · 17 KB 판독" },
    { "name": "디지털운행기록분석시스템(eTAS)_정보시스템.xlsx", "size": "323 KB", "type": "정형 (엑셀)", "profile": "스키마 자동추론 대기 · 323 KB 판독" },
    { "name": "실시간기상관측정보_자료수집시스템_기상청_.xlsx", "size": "17 KB", "type": "정형 (엑셀)", "profile": "스키마 자동추론 대기 · 17 KB 판독" }
  ],
  "manSel": {
    "cctv.vehicle.det.v1": true, "kma.aws.obs.v1": true, "syn.traffic.stream.v1": false,
    "obu_capture_sample": false, "kma_aws_sample": false, "실시간 교통사고 정보": false,
    "실시간교통사고": true, "obu.telemetry.v2": true, "TRAFFIC_LINK_5MIN": true,
    "교통사고심층조사시스템(TAIS)_정보시스템.xlsx": true, "교통혼잡_지역별_데이터.xlsx": true,
    "실시간기상관측정보_자료수집시스템_기상청_.xlsx": true,
    "디지털운행기록분석시스템(eTAS)_정보시스템.xlsx": true, "도로_행정구역_공간정보.xlsx": true
  },
  "procList": [
    { "id": 1787327557588, "name": "실시간교통사고(스트림)", "savedAt": "08-21 15:52",
      "step": 7, "ver": 2, "count": 2, "done": true,
      "snapshot": "(combo·comboName·comboMeta·comboSel·upList·upFile·manSel 위와 동일, step 7, convertState 'done', ds3Done {\"0\":true,\"1\":true}, fmts {t,j,n,p 모두 true}, relPairs [[\"sample_교통사고심층조사시스템_비정형_\",\"sample_디지털운행기록분석시스템(eTAS)\"]] 외)" }
  ],
  "actSeq": 434
}
```

### 4.12 STEP 2 도우미 추천 질문·답변 (3033, 3003, 3006, 3024행)

추천 질문 목록: `['조합에서 데이터셋을 빼면 어떻게 되나요?', '연계키 K1~K9는 뭔가요?', '스튜디오 사용 순서를 알려주세요']`

| 질문 | 답변 원문 |
|---|---|
| `조합에서 데이터셋을 빼면 어떻게 되나요?` | `[제거]를 누르면 내 작업 조합에서 빠지고, 확정 시점의 조합 구성이 Classification Activity로 기록됩니다.\n빠진 데이터셋은 AI 제안 목록·데이터 풀에 그대로 남아 다시 드래그하거나 [+ 추가]로 되돌릴 수 있습니다.` |
| `연계키 K1~K9는 뭔가요?` | `K축은 "이 데이터가 무엇과 조인되는가"를 나타내는 연계키 분류입니다 (예: K5 도로링크 · K6 차량 · K7 시각).\n컬럼 메타데이터에서 규칙으로 도출되는 확인 사항이며 sLLM 추론 대상이 아닙니다 — 추론 대상은 주제 분류인 F축(F1~F6)입니다.` |
| `스튜디오 사용 순서를 알려주세요` | `STEP 1 업로드·조합 제안 → 2 조합 확정 → 3 DCAT/PROV-O 작성 → 4 다중분류 → 5 매핑·리니지 → 6 검증(게이트 0 + SHACL) → 7 직렬화·포맷 변환(+파생 자가검증) → 8 발행·준수 진단 순서입니다.\n검증(6)이 직렬화(7)보다 앞에 있어 검증 미통과 데이터는 파일로 존재하지 않습니다. 각 단계 확정마다 prov:Activity가 기록되며, 완료 조건을 채우지 못한 단계는 잠깁니다.` |

---

## 5. 프로세스 관리 로직 전체 (918~1109행, 810~916행)

### 5.1 현재 프로세스 이름 `curName` (929~935행)

```
list         = s.procList || []
nameAlive    = s.procName 존재 && s.procName.split(' + ').every(n => list에 n 존재)
liveProcName = nameAlive ? s.procName
             : (list에 s.procName과 같은 이름 존재 ? s.procName : null)
curName      = liveProcName
            || (combo.length && comboName && comboName !== '(비어 있음)' ? comboName : '')
            || ((list.length ? list.length + 1 : 1) + '차 프로세스')
```

- 목록에 없는 `procName`(삭제된 프로세스, 죽은 결합 이름, 방금 시작해 아직 저장 안 된 "N차 프로세스")은 신뢰하지 않는다.
- 그래서 저장 전에는 조합 이름(STEP 1 인계 이름 → STEP 2 확정 제목)이 프로세스 이름이 된다. 조합도 없으면 `{목록 수 + 1}차 프로세스`.
- 다른 화면은 `s.procName || '현재 프로세스'`를 직접 쓴다 (604, 818, 1606, 2084, 2211행 등). 같은 "현재 프로세스 이름"이 두 방식으로 계산되어 화면마다 다르게 보일 수 있다.
- `' + '`로 이은 이름은 STEP 6·8의 복수 프로세스 결합 호출(`taskProcOpts`)에서 만들어진다.

### 5.2 저장 `saveCur(done)` (936~947행)

```
entry = { id: Date.now(), name: curName,
          savedAt: new Date().toISOString().slice(5,16).replace('T',' '),   // 'MM-DD HH:MM', UTC
          step: done ? 7 : state.step, ver: 2,
          count: combo.length,
          done: !!done || (같은 이름 기존 항목의 done),
          snapshot: workKeys 중 undefined가 아닌 값 }
procList = [...같은 이름 제외한 기존 목록, entry]      // 이름 기준 upsert, id는 매번 새로 발급
procName = curName                                       // 이름 고정
→ persistDraft()
```

호출 지점:

| 호출 | 인자 | 부가 동작 |
|---|---|---|
| `불러오기` (1077행) | 없음 | 현재 작업 자동 저장 |
| 새 프로세스 확인 `예` (`procAskYes`, 972행) | 없음 | 5.3절 |
| `procSave` (1009행, **마크업 미연결**) | 없음 | 로그 `프로세스 「{curName}」 저장 (STEP {step})` (actId `ACT-PRC-신규`), 토스트 `💾 프로세스 「{curName}」 저장됨 — 목록에서 언제든 불러올 수 있습니다 (prov:Activity 기록)` |
| `procNew` (1010~1019행, **마크업 미연결**) | 없음 | `blank()` + `procName = 다음 이름`, `procOpen: false`, `taskProcSel: null`. 토스트 `＋ 「{curName}」 저장 완료 · 새 프로세스 「{next}」 시작 — STEP 1이 초기화되었습니다` |
| STEP 6·8 프로세스 선택 칩 (`taskProcOpts.toggle`, 1031행) | 없음 | 미저장 작업이 선택에 포함될 때 먼저 저장 |
| STEP 7 변환 성공 (`_saveProc(true)`, 2932~2935행) | `true` | 로그 `프로세스 종료 저장 — {procName} (STEP 7 변환 완료)` |
| STEP 7 전체 다운로드 (`_procSave()`, 2777행) | 없음 | 토스트 `⤓ {N}개 파일 다운로드 · 「{procName}」 완료 — 프로세스 목록에 저장 확정 (prov:Activity 기록 — 데모에서는 미기록)` |
| STEP 8 진단 완료 (`_saveProc(true)`, 1625~1628행) | `true` | 로그 `프로세스 종료 확정 — {procName} (STEP 8 진단 완료 · 전 단계 완주)`. 이때도 `step`은 7로 기록된다 |

### 5.3 완료된 프로세스에서 새 데이터셋 선택 시 가드 (`_procGuard`, 949~959행)

STEP 1의 업로드 카드·스트림 카드·묶음 카드 토글이 먼저 `_procGuard(이름)`을 부른다.

- 조건: 그 항목이 아직 미선택이고, (`convertState === 'done'` 또는 현재 프로세스 이름이 `procList`에 있음)이고, `combo.length > 0`
- 결과: `procAsk = 이름` → 모달 표시, 토글은 중단
- 모달 문구: 제목 `새 프로세스를 시작하시겠습니까?` / 본문 `「{procAskCur}」는 STEP 6 변환까지 완료된 상태입니다. 새 데이터셋을 선택하면 현재 프로세스는 자동 저장되고 「{procAskNext}」가 새로 시작됩니다.` / 버튼 `아니오 (취소)`, `예 — 저장 후 {procAskNext} 시작`
  - 본문의 "STEP 6 변환"은 단계 재편 전 번호다 (현재 변환은 STEP 7).
- `예` (`procAskYes`, 970~976행): `saveCur()` → `{...blank(), procName: next, procOpen: false, procAsk: null, manSel: {[pending]: true}}` → 토스트 `＋ 「{curName}」 저장 완료 · 「{next}」 시작 — 선택한 데이터셋으로 새 프로세스가 시작되었습니다`
- `아니오`: `procAsk = null`

다음 이름 `nextName()` (960~965행): `uniq = {목록의 이름들, curName}`, `n = uniq.size + 1`, `n + '차 프로세스'`가 이미 있으면 n을 올려가며 빈 번호를 찾는다.

### 5.4 삭제·휴지통·영구 삭제 (데이터 카탈로그 > 산출물 저장소)

UI 문구 (markup 2975~3012행): 섹션 제목 `프로세스 관리 (삭제·휴지통)` + `— 삭제는 이 화면에서만 가능 · STEP 1은 불러오기 전용` / 빈 상태 `저장된 프로세스가 없습니다`

| 동작 | 상태 변화 | 토스트·로그 |
|---|---|---|
| 행의 `✕ 삭제` (`pr.del`, 1081행) | `procDelId`를 그 id로 (같으면 null) → 확인 띠 표시: `⚠ 이 프로세스의 저장 지점이 휴지통으로 이동합니다 — 휴지통에서 영구 삭제 시 복구 불가` + 버튼 `휴지통으로 이동` / `취소` | 없음 |
| `휴지통으로 이동` (`pr.confirmDel`, 1082~1089행) | `procList`에서 id로 제거, `procTrash` 끝에 추가, `procDelId: null`, `persistDraft()`. 현재 불러와 작업 중인 프로세스여도 작업 상태는 지우지 않는다 | 토스트 `🗑 「{p.name}」 휴지통으로 이동 — 복원 가능 (prov:Activity 기록)`. 로그는 남기지 않는다 |
| `취소` | `procDelId: null` | 없음 |
| 휴지통 헤더 (`procTrashOn`) | `🗑 휴지통 {procTrashCount}건 — 복원 가능 · 영구 삭제 시 복구 불가`. 행: 취소선 이름 + `{savedAt} 저장 · 데이터셋 {count}건` | |
| `복원` (`pt.restore`, 1098~1101행) | `procTrash`에서 제거, `procList` 끝에 추가, `procPurgeId: null`. 같은 이름이 목록에 이미 있어도 검사하지 않는다 | 토스트 `↺ 「{p.name}」 복원됨 — 프로세스 목록으로 이동` |
| `영구 삭제` (`pt.purge`, 1102~1106행) | 1차 클릭: `procPurgeId = id`, 라벨 `정말 영구 삭제?`. 2차 클릭: `procTrash`에서 제거 | 토스트 `✕ 「{p.name}」 영구 삭제됨 — 복구 불가 (prov:Activity 기록)`. 로그 없음 |

### 5.5 산출물 저장소 그룹과 `outG` (810~916행)

- 그룹 원천: `procList` 중 현재 이름과 다른 것(각각 `saved: true`) + 현재 작업(`{procName || '현재 프로세스'} + (v8State === 'done' ? ' (종료)' : ' (진행 중)')`). 조합이 빈 것은 제외.
- 그룹마다 데이터셋 × 4포맷 행. 그룹 헤더: `📁 {proc} · 산출물 {count}건 · {gate}`
- `outG`: `{ [그룹 라벨]: boolean }`. 그룹 펼침 상태 (`og.toggle`, 876행). 키가 접미사 포함 라벨 문자열이라 이름·상태가 바뀌면 다른 키가 된다.
- `outOpen`: 저장소 전체 접기 (`false`만 접힘).
- `마지막 작업 (STEP n) →` (`og.goLast`, 897~907행): 저장 프로세스면 `{...snapshot, procName, plane: 'studio', step: lastStep}`로 복원(구버전 스냅숏은 6↔7 교환), 진행 중이면 그 단계로 이동. 토스트 `↺ 「{proc}」 마지막 작업 위치(STEP {n})로 이동`
- `🗑 삭제` (`og.del`, 879~895행): 1차 클릭 `outDelId = proc`, 라벨 `정말 삭제? (한 번 더 클릭)`. 2차 클릭:
  - `wipe = {...blank(), upList: undefined, upFile: undefined, upView: undefined}` (업로드 풀까지 삭제)
  - 저장 프로세스 그룹: `procList` → `procTrash` 이동. 현재 불러온 프로세스이면(이름 일치 또는 `' + '` 결합 이름에 포함) `wipe` + `{v7State: null, v8State: null, taskProcSel: null, procName/comboName/comboMeta/comboSel: undefined, cands2All: false}`도 적용. 토스트 `🗑 「{proc}」 산출물 그룹 삭제 — 휴지통 이동` + (현재 프로세스면 ` · STEP 1~6 작업 상태 동시 삭제됨`) + ` (프로세스 관리에서 복원 가능)`
  - 진행 중 그룹: 위 초기화만 적용(휴지통 없음, 복구 불가). 토스트 `🗑 진행 중 산출물 삭제 — STEP 1 업로드·선택부터 조합·분류·변환 결과까지 동시 삭제되었습니다 (대시보드·카탈로그 집계 반영)`
  - 공통 로그: `산출물 그룹 삭제 — 「{proc}」` (actId `ACT-DEL-신규`)

### 5.6 STEP 6·8의 복수 프로세스 호출 (`taskProcOpts`, 1020~1055행)

- 선택 1개: `{...blank(), ...snapshot, procName, taskProcSel: [name], plane: 'studio', step, v7State: null, v8State: null}`. 토스트 `{업무 A(검증)|업무 B(진단)} — 「{name}」 프로세스 호출 · 해당 프로세스 산출물 기준으로 진행`
- 선택 2개 이상: 각 스냅숏의 `combo`를 `n` 기준 합집합 → `{combo: merged, procName: names.join(' + '), taskProcSel: names, …}`. 토스트 `… — {A · B} ({N}개 프로세스 결합 호출) · 산출물 합집합 {M}건 기준 · 재실행 필요`
  - 코드상 버그: 토스트 접두는 `step === 7`일 때만 "업무 A(검증)"인데 검증 칩은 `toggle(p, 6)`으로 호출된다. 그래서 검증 호출도 "업무 B(진단)"으로 표시된다.
- 결합 호출 시 조합만 합치고 나머지 작업 상태(STEP 3~5)는 현재 것 그대로다.

### 5.7 영속화

- 전체 state(4.8절 제외)를 localStorage `fde-studio-draft`에 JSON으로 저장 (`persistDraft`, 101~103행). `procList`의 스냅숏도 그 안에 중첩 저장된다.
- 새로고침 시 복원 (62~90행): 토스트 `↺ 임시저장 스냅숏 복원됨 · {saveTime} 저장분 — 파일 원본은 재첨부가 필요합니다` (3600ms), 잠긴 단계면 통과 가능한 마지막 단계로 후퇴.
- 로그인 `admin` / `9876` 하드코딩 (360행), 작업자명 `홍길동 (나)` 하드코딩.

---

## 6. 상태 변수

| 키 | 타입 | 의미 | 스냅숏 포함 |
|---|---|---|---|
| `combo` | `Array<{n, k, w?, src?, meta?}>` | 내 작업 조합. 초기값 `[]` (3행) | O |
| `comboName` | string? | 조합 이름. STEP 1 인계 시 이름 연결, 확정 시 제목으로 교체 | O |
| `comboSel` | `'up'` \| `'man'`? | 조합 출처 (AI 추천 인계 / 작업자 선택) | O |
| `comboMeta` | `{title?, desc?, ai?: bool, done?: bool, at?: 'HH:MM'}` | 확정 메타. `done`이 STEP 3~6 게이트, `ai`는 AI 초안 표시 | O |
| `manSel` | `{[key]: bool}` | STEP 1 선택. 키 = 업로드 파일명(확장자 포함), 스트림 이름, 묶음 이름, 묶음 구성원 이름 | O |
| `upList` / `upFile` | `Array<{name,size,type,profile}>` / 같은 객체 | 업로드 풀과 대표 파일. 프로세스 간 공유 | O (blank에서 유지) |
| `synStreams` | `Array<{name,type,rate,at,members?,res?,col?,tz?,wm?,late?}>` | 스트림 묶음(탭). 후보 목록 원천 | X (전역) |
| `strmDemoHide` | bool (기본 true 취급) | 데모 단독 스트림 숨김 | X |
| `cands2All` | bool | 후보를 프로세스 범위 밖까지 표시 | X |
| `procList` | `Array<{id:number, name, savedAt:'MM-DD HH:MM', step, ver:2, count, done, snapshot}>` | 저장 프로세스 목록 | 해당 없음 |
| `procTrash` | 같은 구조 배열 | 휴지통 | |
| `procName` | string? | 현재 프로세스 이름. 결합 호출 시 `'A + B'` | |
| `procOpen` | bool | 프로세스 목록 펼침 (STEP 1·2 공용) | |
| `procViewSel` | `{[procName]: bool}` | 목록 체크박스 (미리보기용) | |
| `procAsk` | string \| null | 새 프로세스 확인 모달 대기 중인 선택 항목 이름 | |
| `procDelId` / `procPurgeId` | number \| null | 삭제 확인 / 영구 삭제 확인 대상 id | |
| `outG` | `{[그룹 라벨]: bool}` | 산출물 저장소 그룹 펼침 | |
| `outOpen` | bool? | 산출물 저장소 접힘 (`false`만 접힘) | |
| `outDelId` | string \| null | 산출물 그룹 삭제 확인 대상 라벨 | |
| `taskProcSel` | string[] \| null | STEP 6·8에서 선택한 프로세스 이름들 | |
| `v6Results`, `v7State`, `v6Stale`, `convertState`, `svResults`, `v8State` | 다양 | 하류 결과. 조합 변경·재확정 시 초기화 | `convertState`만 O |
| `actLog` / `actSeq` | `Array<{t, who, txt, actId}>`(최근 10건) / number(기본 420) | 활동 로그와 ID 시퀀스 | X |
| `toast`, `toastText`, `toastId` | bool, string, string | 토스트 | X |
| `notify` | `{from, to, owner}` \| null | 단계 인계 알림 | X |
| `saveTime`, `savedHere`, `wipeAsk` | string, bool, bool | 임시저장 표시, 데모 지우기 확인 | X |
| `step`, `plane`, `tab3` | number, string, number | 내비게이션 | `step`, `tab3` O |

인스턴스 필드(비상태): `_drag`(객체 드래그), `_dragName`(이름 드래그), `_cands2Count`(미사용), `_saveProc`/`_procSave`(= `saveCur`), `_procGuard`, `_blankWork`, 타이머 `_tt`, `_ps`, `_wa`, `_nt`.

---

## 7. 시뮬레이션 vs 실제 계산

### 7.1 실제로 계산·동작하는 것

| 항목 | 근거 |
|---|---|
| 조합 추가·제거, 이름 기준 중복 방지 | 37~41, 650, 2195행 |
| 후보 목록 구성 (업로드 + 스트림 묶음 + 데모 스트림), STEP 1 선택분 우선 정렬, 프로세스 범위 필터 | 2162~2200행 |
| 묶음 키 = 구성원 키 합집합 | 2173행 |
| 조합 확정 게이트 (제목 필수, 1건 이상), 편집 시 확정 해제 | 2044, 2051~2052, 2065행 |
| 단계 잠금 상태기계 (`comboOk` → STEP 3~6) | 324~342행 |
| 조합 변경·재확정 시 하류 결과 무효화 + 시스템 로그 | 344~356, 2068행 |
| AI 초안 문자열 생성 (조합 이름·키에서 결정적 템플릿) | 2053~2060행 |
| 프로세스 스냅숏 저장(upsert)·불러오기·휴지통·복원·영구 삭제, 이름 자동 부여 | 918~1109행 |
| 활동 로그 ID 시퀀스 발급 (`ACT-K-0421~`) | 53~61행 |
| localStorage 임시저장·복원, JSON 내보내기·가져오기 | 62~103, 3078~3106행 |

### 7.2 흉내만 내는 것 (실제 제품에서 구현 필요)

| 항목 | 목업의 실제 모습 |
|---|---|
| "AI 제안 조합" | AI 추천이 아니다. STEP 1에서 올린 파일과 스트림을 그대로 나열한 것이다. 신뢰도·근거 계산 없음 |
| "추천 데이터셋 조합 (AI)" | 항상 빈 상태 문구. 과거 버전의 고정 조합 4개(4.5절)가 미연결 핸들러에 남아 있다 |
| "데이터 풀" | 정적 마크업. 건수 0 고정, 검색·필터 칩 무동작. 과거 시드 5건(4.5절)이 미연결 핸들러에 남아 있다 |
| "보정 경고 / 규칙엔진" | 경고를 만드는 로직도 표시하는 마크업도 없다. `w: true` 플래그와 `검토` 배지만 존재하고, 현재 UI 경로로는 `w`가 설정되지 않는다 |
| 연계키 | 컬럼 프로파일링 없음. 이름 문자열 매칭 또는 `'K7'` 고정. 드롭 추가는 무조건 `'K7'` |
| "✦ AI 초안 (sLLM-molit-7b)" | LLM 호출 없음. 문자열 템플릿. 화면도 "결정적 생성"이라고 밝힘 |
| "Classification Activity 자동 기록", "(prov:Activity 기록)" | `actLog`(최근 10건, 브라우저 메모리·localStorage)에 텍스트 1줄. 조합 구성원·제목·설명은 기록에 구조화되지 않고, PROV 트리플도 만들지 않는다. 휴지통 이동·영구 삭제·불러오기는 토스트만 있고 로그도 없다 |
| `다음 (확정)`의 `✓ prov:Activity ACT-K-04xx 기록됨` | 난수 ID. `actLog`에 없다 |
| 결합 데이터셋의 `dcterms:title/description` | STEP 3 배너와 프로세스 이름에만 쓰이고 TTL·JSON-LD 산출물에는 나오지 않는다 |
| 프로세스 "저장" | 서버 없음. 브라우저 state 스냅숏. `savedAt`은 UTC 기준 `MM-DD HH:MM`, 연도 없음 |
| 산출물 위치 `s3://lake-ctrl/catalog/serialized/…` | 문자열 표기일 뿐. 다운로드는 그때그때 브라우저에서 재생성 |
| 작업자·권한 | `홍길동 (나)` 고정, 단계 담당 조직 알림은 고정 배열 |
| 타이머 | STEP 2 자체에는 가짜 처리 지연이 없다. 토스트 소멸(2200~3600ms)과 저장 디바운스(400ms)뿐 |

---

## 8. 실제 제품에서 필요한 기능

### 8.1 설계 원칙 (목업에서 드러난 문제를 반영)

1. 데이터셋은 이름이 아니라 불변 ID로 식별한다. 목업은 `n`(이름)이 키라서 확장자 제거 규칙, 묶음·구성원 중복, 이름 충돌 문제가 생긴다.
2. 프로세스는 "state 덩어리 스냅숏"이 아니라 정규화된 서버 엔티티로 둔다. 불러오기는 활성 프로세스 전환이고, 검증·변환·승인 입력까지 프로세스에 귀속시켜 다른 프로세스로 새지 않게 한다.
3. 조합 변경은 확정을 자동 해제하거나(권장) 확정 버전을 새로 만든다. 목업처럼 확정 후 조합이 바뀌어도 확정 상태가 유지되면 안 된다.
4. 단계별 완료 표시는 조합 인덱스가 아니라 (프로세스, 데이터셋 ID)로 건다.
5. 게이트·무효화 판정은 서버가 단일 지점에서 한다 (`stepGate`, `invalidateDownstream`의 서버판).
6. "prov:Activity 기록"이라고 표시하는 모든 동작은 실제 PROV 레코드를 남긴다 (조합 확정, 프로세스 저장·삭제·복원·영구 삭제·불러오기).
7. 결합 데이터셋을 RDF 정본의 노드로 만든다.

### 8.2 데이터 모델 (PostgreSQL)

| 엔티티 | 주요 필드 | 비고 |
|---|---|---|
| `process` | `id (uuid)`, `name`, `seq_no`(N차), `status`(`active`/`finished`), `current_step`, `owner_id`, `created_at`, `updated_at`, `finished_at`, `deleted_at`(휴지통), `purged_at`, `parent_process_ids[]`(결합 호출 출처) | `name`은 삭제되지 않은 범위에서 유일. `deleted_at`으로 휴지통 구현 |
| `process_checkpoint` | `id`, `process_id`, `step`, `saved_at (timestamptz)`, `kind`(`auto`/`manual`/`finish`), `dataset_count`, `state_json` | 목업의 `procList[].snapshot` 대응. 감사·되돌리기용. 필수는 아님 |
| `dataset_candidate` (또는 기존 `dataset`) | `id`, `name`, `source_type`(`upload`/`stream`/`stream_bundle`/`lake`/`data_portal`/`mcp`), `form`, `profile_json`, `bundle_id?` | 데이터 풀·업로드·스트림 통합 |
| `stream_bundle_member` | `bundle_id`, `dataset_id` | 묶음 구성원 (4.3절 기본 4건) |
| `process_selection` | `process_id`, `dataset_id`, `selected_at`, `selected_by` | 목업 `manSel` |
| `linkage_key` | `code`(K1~K9), `label`, `description`, `version` | 4.1절 시드. 통제어휘 `v2.0 (2026-05)` |
| `dataset_linkage_key` | `dataset_id`, `key_code`, `column_name`, `detect_method`(`rule`/`manual`), `match_rate`, `note` | 컬럼 프로파일 기반. 목업의 `k` 문자열 대체 |
| `combination` | `id`, `process_id`(1:1), `name`, `title`, `description`, `source`(`ai_suggested`/`manual`/`adjusted`), `status`(`draft`/`confirmed`), `title_ai_drafted (bool)`, `confirmed_at`, `confirmed_by`, `confirm_activity_id`, `version`, `iri` | `comboMeta` + `comboName` + `comboSel` |
| `combination_member` | `combination_id`, `dataset_id`, `position`, `origin`(`ai`/`manual`/`step2_add`), `needs_review (bool)`, `added_at`, `added_by` | UNIQUE(`combination_id`, `dataset_id`). 목업 `combo[]`의 `src`, `w` |
| `combination_warning` | `id`, `combination_id`, `rule_code`(`notation_mismatch`/`crs_mismatch`/`time_format_mismatch`), `key_code`, `dataset_ids[]`, `detail`, `penalty_pct`, `status`(`open`/`acknowledged`/`resolved`) | "보정" 영역 |
| `combination_suggestion` | `id`, `process_id?`, `name`, `member_dataset_ids[]`, `shared_keys[]`, `confidence_pct`, `rationale`, `generated_by`, `generated_at` | "추천 데이터셋 조합". 4.5절 4개가 시드 예 |
| `prov_activity` | `id`(`ACT-K-…` 등 발급 규칙), `type`(`combination_confirm`/`process_save`/`process_load`/`process_trash`/`process_restore`/`process_purge`/`combination_change`/`downstream_invalidate`), `agent_id`, `process_id`, `started_at`, `ended_at`, `used_json`, `generated_json`, `message` | 목업 `actLog` 대체. 10건 제한 없음 |
| `process_step_state` | `process_id`, `step`, `status`(`locked`/`open`/`done`/`stale`), `reason` | `stepGate` 결과 캐시(선택) |

### 8.3 API (FastAPI)

프로세스:

| 메서드·경로 | 기능 | 목업 대응 |
|---|---|---|
| `GET /api/processes?state=active\|trashed` | 목록 (이름, 저장 시각, 데이터셋 수, 단계, 종료 여부) | `procRows`, `procTrashRows` |
| `POST /api/processes` | 새 프로세스 시작. 이름 미지정 시 `N차 프로세스` 자동 부여 (빈 번호 탐색) | `procNew`, `procAskYes`, `nextName` |
| `GET /api/processes/{id}` | 상세 + 단계 게이트 상태 | `procCurName`, `stepGate` |
| `PATCH /api/processes/{id}` | 이름 변경 | 조합 확정 시 이름 인계 |
| `POST /api/processes/{id}/checkpoints` | 수동·자동 저장 | `saveCur`, `procSave` |
| `POST /api/processes/{id}/activate` | 불러오기 (현재 프로세스 자동 저장 후 전환, 복원 단계 반환) | `pr.load` |
| `GET /api/processes/{id}/datasets` | 포함 데이터셋 + 연계키 (체크박스 미리보기, 복수 id 지원) | `pvDs` |
| `DELETE /api/processes/{id}` | 휴지통 이동. 활성 프로세스일 때의 처리 정책을 명시 | `confirmDel`, `og.del` |
| `POST /api/processes/{id}/restore` | 복원. 이름 충돌 시 409 또는 자동 개명 | `pt.restore` |
| `DELETE /api/processes/{id}?purge=true` | 영구 삭제 (휴지통 상태에서만) | `pt.purge` |
| `POST /api/processes/merge-view` | 복수 프로세스 산출물 합집합 뷰 (STEP 6·8용) | `taskProcOpts` |
| `GET /api/processes/{id}/gates` | 단계별 `done`/`canEnter`/`reason` | `stepGate` |

조합:

| 메서드·경로 | 기능 | 목업 대응 |
|---|---|---|
| `GET /api/processes/{id}/candidates?scope=process\|all&q=` | 후보 목록. 선택분 우선 정렬, `in_combination`, `selected_in_step1`, 연계키 포함 | `step2Cands`, `cands2All` |
| `GET /api/data-pool?source=all\|lake\|data_portal\|mcp&q=` | 데이터 풀 검색 | 좌측 패널 |
| `GET /api/processes/{id}/combination` | 조합 + 구성원 + 확정 메타 | `comboList`, `cm*` |
| `POST /api/processes/{id}/combination/members` `{dataset_id}` | 추가 (중복 409). 묶음이면 구성원 전개 정책 적용. 응답에 무효화된 하류 결과 목록 | `addCombo`, `dropCombo` |
| `DELETE /api/processes/{id}/combination/members/{dataset_id}` | 제거. 같은 무효화 응답 | `c.remove`, `uf.remove` |
| `PATCH /api/processes/{id}/combination` `{title?, description?}` | 메타 편집. 서버가 `status=draft`로 되돌림 | `cmTitleSet`, `cmDescSet` |
| `POST /api/processes/{id}/combination/draft-metadata` | 제목·설명 초안. 1차는 4.6절 결정적 템플릿, 이후 sLLM 연동. 응답에 `generated_by` | `cmAi` |
| `POST /api/processes/{id}/combination/confirm` | 확정. 검증: 제목 공백 아님, 구성원 1건 이상 (SHACL로도 표현). 처리: `status=confirmed`, `prov_activity` 생성, 프로세스 이름 인계, 하류 결과 무효화, STEP 3 초안 생성 트리거. 응답 `{activity_id, confirmed_at, next_step: 3}` | `cmConfirm` |
| `GET /api/processes/{id}/combination/warnings` | 규칙엔진 경고 (표기·좌표계·시간포맷 불일치) | "보정 경고" 영역 |
| `POST /api/processes/{id}/combination/warnings/{wid}/resolve` | 경고 처리 | (목업 없음) |
| `GET /api/processes/{id}/combination/suggestions` | 연계키 기반 추천 조합 + 신뢰도·근거 | "추천 데이터셋 조합" |
| `POST /api/processes/{id}/combination/apply-suggestion/{sid}` | 추천 조합을 작업 조합으로 적용 | `loadComboRec*`, `pickCombo*` |

공통:

| 메서드·경로 | 기능 |
|---|---|
| `GET /api/vocab/linkage-keys` | K1~K9 코드표 |
| `GET /api/activities?process_id=&type=` | 활동 로그 조회 |
| `GET /api/outputs?group_by=process` | 산출물 저장소 그룹 (프로세스별 4포맷 파일) |

### 8.4 백엔드 기능

1. **연계키 탐지 엔진**: 업로드 파일·스트림 스키마를 프로파일링해 컬럼 단위로 K1~K9를 배정한다 (목업의 이름 매칭 대체). 결과는 `dataset_linkage_key`. 도우미 답변의 설명대로 규칙 기반이며 sLLM 추론 대상이 아니다.
2. **조합 추천기**: 공유 연계키, 컬럼 매칭률, 시각 정렬 일치율로 후보 조합과 신뢰도·근거 1줄을 산출한다 (3005행 답변의 정의).
3. **보정 규칙엔진**: 조합 구성원 사이의 표기 불일치(예 `CarID` vs `OBU_IDNT_NMBR`), 좌표계 불일치(EPSG), 시간 포맷 불일치(ISO 8601)를 탐지해 경고와 감점을 만든다. 구성원 변경 시 재계산.
4. **조합 확정 처리(트랜잭션)**: 메타 검증 → 확정 → PROV 활동 기록 → 프로세스 이름 인계 → 하류 결과 무효화 → STEP 3 초안 생성.
5. **RDF 정본 반영 (rdflib)**: 결합 데이터셋 노드를 만든다. 제안: `dcat:Dataset`(또는 `dcat:DatasetSeries`)에 `dcterms:title`, `dcterms:description`, 구성원을 `dcterms:hasPart`(또는 `prov:wasDerivedFrom`)로 연결, `prov:wasGeneratedBy`로 확정 활동 연결, 활동에 `prov:used` 구성원·`prov:wasAssociatedWith` 작업자·`prov:endedAtTime`. 목업은 이 노드를 만들지 않으므로 모델 선택은 확정이 필요하다.
6. **SHACL (pySHACL)**: 조합 Shape. `dcterms:title` `sh:minCount 1`, 구성원 `sh:minCount 1`, 구성원 간 공유 연계키 존재 여부는 Warning. `FIX_ROUTE.identity`가 STEP 2 "조합 확정 카드"를 가리키므로 위반 결과에 원인 단계(2)와 대상 필드를 담아 프런트가 하이라이트할 수 있게 한다.
7. **단계 게이트·무효화 서비스**: `stepGate`(324~342행)와 `invalidateDownstream`(344~356행) 규칙을 서버로 옮긴다. STEP 2 관련 규칙: 진입 = 선택 1건 이상 또는 조합 1건 이상, 완료 = 조합 1건 이상이고 확정됨, STEP 3~6 진입 = STEP 2 완료.
8. **프로세스 생애주기**: 자동 저장(단계 이동·확정 시), 종료 처리(STEP 7 변환 성공, STEP 8 진단 완료), 완료된 프로세스에서 새 선택 시 새 프로세스 분기 확인, 소프트 삭제·복원·영구 삭제(산출물 파일 정리 포함), 업로드 풀의 프로세스 간 공유 범위 정책.
9. **감사·권한**: 작업자 식별, 단계 확정 시 다음 단계 담당 조직 알림(2989행 표), 삭제·영구 삭제 권한 분리.

### 8.5 프런트엔드(React) 구현 메모

- 드래그 앤 드롭은 후보 ID를 전달하고, 드롭 핸들러는 한 곳에만 둔다 (이중 호출 방지). 키보드 대체 동작은 버튼으로 제공한다.
- 드롭 존 문구의 "+ 추가"와 버튼 라벨 `내 작업으로 →`를 통일한다.
- 후보 빈 상태는 실제 표시 목록 길이로 판정한다 (범위 필터 결과 0건 처리 포함).
- 제목·설명 입력은 `change`가 아니라 `input` 기준으로 확정 버튼 활성화를 갱신한다.
- 확정 후 조합을 바꾸면 "재확정 필요" 상태를 명확히 표시한다.
- 토스트 표시 상태를 실제로 바인딩한다 (`toastOn` 미정의 문제).
- 새 프로세스 확인 모달의 "STEP 6 변환" 표기를 현행 단계 번호(STEP 7)로 고친다.
