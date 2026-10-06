# 05. STEP 5 — 전체 매핑 + LPG · 데이터리니지 확정 (기능 명세)

- 분석 대상: `src/markup.html` 1323~1669행 (STEP 5 블록), `src/logic.js` `renderVals()` 내 관련 바인딩
- 연동 범위(STEP 5 블록 밖이지만 STEP 5 상태를 만들거나 소비하는 부분): STEP 4의 "SSOT 우선순위", "연관데이터셋" 패널(markup 1244~1318), STEP 6의 "리니지 미결" 모달(markup 1938~1950), 하단 고정 바(markup 3876~3889), 좌측 스텝퍼, STEP 4 헤더 재검토 배지(markup 1029~1031)
- 표기 규칙: 화면 문구와 데이터 값은 원문 그대로 인용한다. `L1234`는 `logic.js` 행 번호, `M1234`는 `markup.html` 행 번호다.
- 과업 지시서에는 연계키가 K1..K7로 적혀 있으나 코드의 통제어휘는 K1..K9 9종이다(L731, L2381). 본 문서는 9종 전체를 기록한다.

---

## 1. 화면 목적

STEP 2에서 확정한 데이터셋 조합과 STEP 4에서 지정한 결합 관계(SSOT 우선순위 연결 = `JOINED_ON`, 연관데이터셋 = `GROUPED_WITH`)를 PROV-O 기반 리니지 그래프(LPG 투영)로 보여 주고, 네 단계 그래뉼래리티(G1 시스템 → G2 데이터셋 → G3 배포·테이블 → G4 컬럼)를 순서대로 검토한 뒤 확정하는 단계다.

화면이 주장하는 기능은 다음과 같다.

1. 시스템, 데이터셋, 배포본·테이블, 컬럼 수준에서 "무엇이 무엇과 어떤 키로 결합되어 어떤 산출물이 만들어지는가"를 그래프로 표시한다.
2. 노드를 클릭하면 우측 패널에 역할, DCAT 속성, 연계키, 결합 관계 건수, 엣지 프로퍼티를 보여 준다.
3. 편집 모드에서 노드의 표시 이름과 역할 설명을 수정한다. STEP 4와 연동되는 노드(베이스, 차량 흐름, 사고, 기상)는 "변경 요청"으로 접수되어 STEP 4에 재검토 배지를 띄운다.
4. G2, G3 수준에서 리니지 관련 SHACL 위반과 해결 가이드를 보여 준다.
5. "확정 시" 실제 ID(DST, DIST, ACT, COL, TBL) 발급, prov:Activity 기록, 마트 조인 테이블 생성이 일어난다고 안내한다.

현재 목업은 1~4를 정적 그림과 하드코딩 데이터로 흉내 내며, 5는 구현되어 있지 않다(6장 참조).

단계 메타데이터:

| 항목 | 값 | 근거 |
|---|---|---|
| 스텝퍼 라벨 | `매핑 + LPG·리니지` | L377 |
| 화면 제목 | `STEP 5: 전체 매핑 + LPG · 데이터리니지 확정` | M1328 |
| 담당 조직(좌측 사이드바 "현재 단계 담당 조직") | `데이터 품질관리팀` (정 `홍길동`, 부 `이순신`, 관리자 `변학도`) | L1682~1683 |
| 진입 조건 | STEP 2 조합 확정 (`combo.length > 0 && comboMeta.done`) | L327, L336 |
| 완료 조건(✓ 표시) | `relPairs.length > 0` 또는 `linWaived === true` | L336 |
| 잠김 시 토스트 | `🔒 STEP 5 잠김 — STEP 2 조합 확정을 먼저 완료하세요` (3초) | L9~13, L336 |
| 관리 화면의 엔진/외부 연계 표기 | 엔진 `규칙엔진`, 외부 연계 `Neo4j (LPG 투영)`, 상태 `ok` | L1292 |
| 어시스턴트 추천 질문 | `LPG 투영이 뭔가요?`, `엣지 15종은 어디서 오나요?`, `SHACL 검증은 어떻게 동작하나요?` | L3036 |

---

## 2. 화면 구성

### 2.1 전체 레이아웃 (M1325)

가로 2단 flex, `max-width:1280px`, 간격 20px.

- 좌측(가변 폭): 헤더 → 편집 모드 배너 → 그래뉼래리티 탭과 엣지 종류 → 그래프 카드(범례 + SVG + 설명 + G4 전용 컬럼 표) → 안내 바 → SHACL 가이드 카드
- 우측(고정 300px, sticky, `max-height: calc(100vh - 140px)`, 세로 스크롤): 노드 상세 패널

### 2.2 헤더와 편집 모드 배너 (M1327~1333)

| 요소 | 문구 | 바인딩 |
|---|---|---|
| 제목 | `STEP 5: 전체 매핑 + LPG · 데이터리니지 확정` | 고정 |
| 버튼(우측) | 꺼짐 `✎ 편집 모드` / 켜짐 `✎ 편집 모드 종료` | `editModeLabel`, `editModeToggle`, `editModeBtnStyle` (L1437~1440). 켜지면 주황 배경(#e8912d) 흰 글씨, 꺼지면 흰 배경 갈색 글씨 |
| 배너(편집 모드일 때만) | `✎ 편집 모드 — 노드를 클릭한 뒤 우측 상세에서 수정하세요. STEP 5 고유 정보(라벨·설명·파생 설계)는 즉시 저장되고, STEP 4 연동 항목(베이스·차량 흐름·사고·기상의 결합 관계)은 변경 요청으로 접수되어 STEP 4에 재검토 배지가 표시됩니다. 모든 변경은 prov:Activity 기록.` | `editModeOn` |

### 2.3 그래뉼래리티 탭과 엣지 종류 (M1334~1361)

탭 버튼 4개(선택 시 검정 배경 #1F2430, 흰 글씨. `gBtn`, L406):

| 버튼 | 핸들러 | 표시 조건 |
|---|---|---|
| `G1 시스템` | `setG1` → `go({gran:1})` | `gran1` |
| `G2 데이터셋` | `setG2` → `go({gran:2})` | `gran2` (기본값) |
| `G3 배포·테이블` | `setG3` → `go({gran:3})` | `gran3` |
| `G4 컬럼` | `setG4` → `go({gran:4})` | `gran4` |

그 아래 한 줄: `엣지 15종: WAS_DERIVED_FROM · WAS_GENERATED_BY · USED · WAS_ATTRIBUTED_TO · WAS_INFORMED_BY` + 링크 `더보기 (15종 전체) ▾` / `접기 ▴` (`toggleEdges`, L2955~2956).

펼치면 15개 칩(모노스페이스)이 나온다. 목록은 4.2절.

### 2.4 그래프 카드

#### 2.4.1 범례 (M1363~1371, 모든 수준에서 동일하게 고정 표시)

`노드 18종:` 다음에 색 점과 개수.

| 라벨 | 색 | 표기 개수 |
|---|---|---|
| Agent | #7a3fa0 | 3 |
| System | #111318 | 2 |
| Dataset | #1E5EFF | 4 |
| Column | #2aa876 | 2 |
| Activity | #e8912d | 8 |
| JoinKey | #c0392b | 1 |

주의: 표기 개수 합은 20이고 문구는 "18종"이다. 실제로 그려지는 노드 수(G1 8개, G2 8개, G3 5개, G4 5개)와도 맞지 않는다. 수준을 바꿔도 범례는 변하지 않는다.

#### 2.4.2 G1 시스템 수준 (M1372~1430, SVG viewBox `0 0 860 400`)

노드(전부 원):

| 키(클릭 시 `node5`) | 중심(cx,cy) r | 채움 / 테두리 | 1행 라벨 | 2행 라벨 | 표시 조건 |
|---|---|---|---|---|---|
| `base` (`ndBase`) | (115,200) 38 | #E8EEFF / #1F2430 3px | `공간정보 통합포털` | `도로 공간정보 (베이스 지도)` | 항상 |
| `flow` (`ndFlow`) | (438,95) 32 | #E8EEFF / #1E5EFF 2px | `{{ g1N1 }}` | `{{ g1N1Sub }}` | `g1N1On` |
| `acc` (`ndAcc`) | (438,200) 32 | #E8EEFF / #1E5EFF 2px | `{{ g1N2 }}` | `{{ g1N2Sub }}` | `g1N2On` |
| `wx` (`ndWx`) | (438,305) 32 | #f0e6f6 / #7a3fa0 2px | `{{ g1N3 }}` | `{{ g1N3Sub }}` | `g1N3On` |
| `lake` (`ndLake`) | (670,200) 38 | #dff0ec / #2aa876 2.5px | `빅데이터센터` | `레이크·마트 · 사고 원인 분석` | 항상 |
| `fde` (`ndFde`) | (670,80) 22 | #f0e6f6 / #7a3fa0 2px | `FDE 스튜디오` | 없음 | 항상 |
| `api` (`ndApi`) | (160,60) 26 | #fff / #8B919C 1.5px | `외부 API` | `유입 예정` | 항상 (미연결) |
| `mcp` (`ndMcp`) | (255,60) 26 | #fff / #8B919C 1.5px | `MCP 소스` | `유입 예정` | 항상 (미연결) |

엣지(회색 실선 #C4CAD3 1.5px, 화살촉 없음):

| 구간 | 라벨 | 비고 |
|---|---|---|
| base → 중앙 1번 (150,200)→(395,95) | `JOINED_ON ({{ g1E1 }})` | `g1N1On`일 때만 |
| 중앙 1번 → lake (480,95)→(620,185) | (공통 라벨 `WAS_DERIVED_FROM`, 좌표 (500,150)에 1회 표기) | `g1N1On`일 때만 |
| base → 중앙 2번 (155,200)→(398,200) | `JOINED_ON ({{ g1E2 }})` | `g1N2On` |
| 중앙 2번 → lake (480,200)→(618,200) | 위 공통 라벨 | `g1N2On` |
| base → 중앙 3번 (150,200)→(395,305) | `JOINED_ON ({{ g1E3 }})` | `g1N3On` |
| 중앙 3번 → lake (480,305)→(620,215) | 위 공통 라벨, 점선 `4 3` | `g1N3On` (협약 전이라는 의미의 점선) |
| fde → lake (670,102)→(670,160) | `WAS_ASSOCIATED_WITH` | 항상 |

고정 텍스트:

- 상단 (207,20): `향후 유입 채널 (연계 확정 시 연결)`
- 하단 (430,382): `도로 공간정보(지도) 베이스 위에 차량 흐름·교통사고·기상 시스템 데이터를 결합 — 사고 발생 시 원인 분석이 목적`
- SVG 아래 설명 줄: `G1 시스템 수준 — {{ g1ProcName }} 조합 기준: 도로 공간정보 베이스(1차 프로세스 산출 정본이 베이스로 이어짐 — 프로세스 연속성) 위에 {{ g1Names }}를 결합해 빅데이터센터 레이크에서 사고 원인 분석에 사용합니다`

동적 값 산출 규칙은 3.3절.

#### 2.4.3 G2 데이터셋 수준 (M1431~1485, viewBox `0 0 860 400`, 기본 표시 수준)

노드(전부 원, 전부 정적 문구):

| 키 | 중심 r | 채움 / 테두리 | 1행 | 2행 | 유형 |
|---|---|---|---|---|---|
| `base` | (115,200) 34 | #E8EEFF / #1F2430 3px | `도로 공간정보` | `베이스 지도 · SSOT 1순위` | Dataset |
| (클릭 불가) | (115,105) 16 | #fdf1ef / #c0392b 2px | `K5` | 없음 | JoinKey. base와 점선(115,121)→(115,166)으로 연결 |
| `flow` | (330,90) 30 | #E8EEFF / #1E5EFF | `디지털운행기록` | `차량 흐름 (eTAS)` | Dataset |
| `acc` | (330,200) 30 | #E8EEFF / #1E5EFF | `교통사고심층조사` | `+ 데이터오픈마켓 30종` | Dataset (연관 그룹) |
| `wx` | (330,305) 30 | #f0e6f6 / #7a3fa0 | `기상청 관측자료` | `타 부처 · 협약 확인` | Dataset (외부) |
| `act` (`ndAct`) | (567,200) 28 | #fdf3e7 / #e8912d | `ACT-신규` | `사고 원인 분석` | Activity |
| `fde` | (567,85) 22 | #f0e6f6 / #7a3fa0 | `FDE 스튜디오` | 없음 | Agent |
| `out` (`ndOut`) | (730,200) 32 | #dff0ec / #2aa876 2.5px | `사고 원인 분석본` | `DST-신규 (확정 시 발급)` | Dataset (산출) |

엣지:

| 종류 | 구간 | 스타일 | 라벨 |
|---|---|---|---|
| JOINED_ON | base → flow (145,200)→(285,95) | 파란 실선 #1E5EFF 1.5 | `JOINED_ON K5 ①` |
| JOINED_ON | base → acc (150,200)→(288,200) | 파란 실선 | `JOINED_ON K5·K2 ②` |
| JOINED_ON | base → wx (145,200)→(285,305) | 파란 실선 | `JOINED_ON K7 ③` |
| GROUPED_WITH | (345,180)→(345,120): acc 노드와 flow 노드 사이 수직선 | 보라 점선 #7a3fa0 1.8, `5 3` | `GROUPED_WITH` |
| USED | flow → act (370,90)→(540,185) | 회색 실선 | `USED` (435,150에 1회 표기) |
| USED | acc → act (375,200)→(538,200) | 회색 실선 | 위와 공유 |
| USED | wx → act (370,305)→(540,215) | 회색 실선 | 위와 공유 |
| WAS_GENERATED_BY | act → out (595,200)→(695,200) | 회색 실선 | `WAS_GENERATED_BY` |
| WAS_ASSOCIATED_WITH | act → fde (567,172)→(567,110) | 회색 실선 | `WAS_ASSOCIATED_WITH` |

고정 텍스트:

- 하단 범례 (430,382): `파란 실선 = SSOT 우선순위 연결 (JOINED_ON · 번호 = 순위) · 보라 점선 = 연관데이터셋 확정 (GROUPED_WITH)`
- 설명 줄: `G2 데이터셋 수준 — 도로 공간정보(베이스 지도) 위에 차량 흐름(디지털운행기록)·교통사고(심층조사+오픈마켓 연관 그룹)·기상(타 부처)을 SSOT 우선순위로 결합해 사고 원인 분석본을 산출하는 구조 — STEP 4의 SSOT 순위·연관데이터셋 확정이 여기 엣지로 반영되고, STEP 5 확정 시 실제 ID가 발급됩니다`

주의: 설명은 "STEP 4의 SSOT 순위·연관데이터셋 확정이 여기 엣지로 반영"된다고 하지만 G2 SVG는 상태(`dsExtra.ssot`, `relPairs`, `combo`)를 전혀 읽지 않는 정적 그림이다. GROUPED_WITH 점선도 설명("심층조사+오픈마켓 연관 그룹")과 달리 acc와 flow 사이에 그려져 있다.

#### 2.4.4 G3 배포·테이블 수준 (M1486~1533, viewBox `0 0 900 470`)

노드(전부 사각형, rx 10):

| 키 | 위치 x,y w×h | 스타일 | 내용(원문) |
|---|---|---|---|
| `base` | 55,82 150×56 | #E8EEFF / #1F2430 2.5 | `도로 공간정보` / `dcat:Dataset · 베이스` |
| `acc` | 55,302 150×56 | #E8EEFF / #1E5EFF 2 | `교통사고심층조사` / `dcat:Dataset · + 오픈마켓` |
| `distRoad` (`ndDistRoad`) | 330,55 200×120, 헤더 띠 파랑 #1E5EFF | 흰 바탕 / #1E5EFF 1.5 | 헤더 `DIST-신규 · 도로목록.xlsx`; 본문 `ROAD_LINK_ID  PK · K5` / `ROAD_NAME · ROAD_RANK` / `GEOM (K3 · EPSG 미선언 ⚠)` / `LANE_CNT · LIMIT_SPD`; 꼬리 `14컬럼 · mediaType: …sheet` |
| `distAcc` (`ndDistAcc`) | 330,275 200×120, 헤더 띠 파랑 | 흰 바탕 / #1E5EFF 1.5 | 헤더 `DIST-신규 · 사고심층조사.xlsx`; 본문 `ACDNT_ID  PK` / `ACDNT_ADDR (K2 · 지오코딩)` / `OCCUR_DT (K7 · ISO 8601)` / `CAUSE_CD · CASLT_CNT`; 꼬리 `11컬럼 · mediaType: …sheet` |
| `mart` (`ndMart`) | 660,150 210×150, 헤더 띠 주황 #e8912d | 흰 바탕 / #e8912d 1.8 | 헤더 `vw_road_accident (마트 조인)`; 본문 `ROAD_LINK_ID  ← 도로 (K5)` / `ACDNT_ID      ← 사고` / `OCCUR_DT      정렬축 (K7)` / `CAUSE_CD · GEOM` / `WEATHER_CD (기상 · 협약 후)`(주황 글씨); 꼬리 `사고 원인 분석용 · 생성 대기` |

엣지(회색 실선):

| 구간 | 라벨 |
|---|---|
| base → distRoad (205,110)→(330,110) | `HAS_DISTRIBUTION` |
| acc → distAcc (205,330)→(330,330) | `HAS_DISTRIBUTION` |
| distRoad → mart (530,110)→(660,200) | `JOINED_ON (K5)` |
| distAcc → mart (530,330)→(660,250) | `JOINED_ON (K2→K5)` |

고정 텍스트:

- 하단 (450,448): `배포본(xlsx)의 컬럼 구조와 마트 조인 테이블 스키마 — 연계키 컬럼(K5·K2·K7)이 조인 축이 됩니다`
- 설명 줄: `G3 배포·테이블 수준 — 도로목록.xlsx(14컬럼)와 사고심층조사.xlsx(11컬럼)가 K5 도로링크 축으로 조인되어 마트 테이블 vw_road_accident를 구성 (사고 주소는 지오코딩으로 K5 변환) · 기상 컬럼은 협약 확인 후 합류 — 생성은 STEP 5 확정 시 실행`

#### 2.4.5 G4 컬럼 수준 (M1534~1593, viewBox `0 0 820 360`)

노드(전부 원):

| 핸들러 | 중심 r | 스타일 | 1행 | 2행 |
|---|---|---|---|---|
| `ndColCause` | (160,90) 27 | #dff0ec / #2aa876 | `CAUSE_CD` | 없음 |
| `ndColOccur` | (160,180) 27 | #dff0ec / #2aa876 | `OCCUR_DT` | 없음 |
| `ndColAddr` | (160,270) 27 | #fdf1ef / #c0392b | `ACDNT_ADDR` | `K2 → K5 변환` |
| `ndG4Act` | (430,150) 28 | #fdf3e7 / #e8912d | `ACT-신규` | `사고 원인 지수 산출` |
| `ndG4Out` | (660,150) 30 | #dff0ec / #1F2430 3px | `accident_risk_idx` | `파생 컬럼 (설계)` |

엣지:

| 구간 | 스타일 | 라벨 |
|---|---|---|
| CAUSE_CD → ACT (160,90)→(430,150) | 회색 실선 | `USED` |
| OCCUR_DT → ACT (160,180)→(430,150) | 회색 실선 | `USED` |
| ACDNT_ADDR → ACT (160,270)→(430,150) | 연갈색 #e2c39a 점선 `4 3` | `JOINED_ON (K2→K5)` |
| ACT → accident_risk_idx (430,150)→(660,150) | 회색 실선 | `WAS_GENERATED_BY` |
| CAUSE_CD ↔ OCCUR_DT (160,90)→(160,180) | 빨강 #c0392b 점선 `3 3` | `동일 사고 건` |

설명 줄: `G4 컬럼 수준 — 사고 원인(CAUSE_CD)·발생시각(OCCUR_DT)이 사고 원인 지수 산출 Activity를 거쳐 accident_risk_idx로 파생 · 사고 주소(ACDNT_ADDR)는 K2→K5 지오코딩 변환 후 도로링크 조인 키로 사용 (설계 단계 — STEP 5 확정 시 실제 ID 발급)`

### 2.5 G4 전용: 테이블별 컬럼 구성 (M1561~1592)

- 제목: `테이블별 컬럼 구성` + 보조 문구 `— 행을 클릭하면 우측 상세가 해당 컬럼으로 전환됩니다`
- 탭(세그먼트 버튼, 선택 시 검정): `도로목록.xlsx`(`g4TabRoad`), `사고심층조사.xlsx`(`g4TabAcc`, 기본), `vw_road_accident`(`g4TabMart`)
- 표 헤더: `컬럼` | `타입` | `연계키` | `결측률` | `비고`
- 행: `g4Cols` 반복. 컬럼명은 모노스페이스 굵게, 연계키는 값이 있으면 빨간 배지, 없으면 회색 `—`. 선택된 행은 배경 #E8EEFF.
- 데이터는 4.6절.

### 2.6 안내 바 (M1595)

`현재 그래뉼래리티({{ granLabel }}) 검토 중 — 저장·다음 이동은 화면 하단 공통 바를 사용하세요 (다음 (확정)이 G1→G4 순서로 진행)`

`granLabel` = `'G' + (gran || 2)` (L2942).

### 2.7 SHACL 위반 설명 · 해결 가이드 (M1596~1621)

표시 조건 `shaclGuideOn` = `gran`이 2 또는 3 (L2949). 헤더: `SHACL 위반 설명 · 해결 가이드` + 빨간 글씨 `· {{ granLabel }} 해당 {{ guideCount }}건`. `guideCount`는 G2에서 2, 그 외 1 (L2950). 카드 내용은 전부 하드코딩이며 4.8절에 원문을 실었다. 카드의 링크는 모두 `goStep3` (`go({plane:'studio', step:3})`, L2552).

### 2.8 우측 상세 패널 (M1623~1666)

위에서 아래로:

1. 헤더(검정 띠): `{{ node5PanelTitle }} — {{ node5Title }}`
   - `node5PanelTitle`은 선택 노드가 아니라 현재 `gran`으로 정한다: G1 `시스템 상세`, G2 `데이터셋 상세`, G3 `테이블 상세`, G4 `컬럼 상세` (L1435)
2. 안내: `ⓘ 그래프의 원을 클릭하면 해당 노드의 상세가 여기에 표시됩니다`
3. `역할 (분석 구성)`: 파란 박스에 `{{ node5Role }}`
4. `DCAT 속성`
   - `dcterms:title` `{{ node5Title }}`
   - `dcat:version` `1.0.0` (고정)
   - `dcterms:identifier` `{{ node5Id }}`
5. `연계키`: `node5Keys` 칩 반복. 없으면 `해당 없음 (데이터셋 노드가 아님)` (`node5NoKeys`)
6. `결합 관계 (STEP 4 확정분)`
   - `JOINED_ON — SSOT 우선순위 목록 {{ ssotCount }}건` (`ssotCount` = `dsExtra.ssot.length`, L1676)
   - `GROUPED_WITH — 연관데이터셋 {{ relCount }}쌍` (`relCount` = `relPairs.length`, L1677)
   - 선택 노드와 무관하게 전역 건수를 표시한다.
7. `엣지 프로퍼티 (WAS_DERIVED_FROM)` (전부 고정 문구)
   - `confidence` `계산 대기 (매핑 확정 후 산출)`
   - `ruleSetVersion` `rs-2.1`
   - `executedAt` `확정 시 기록`
8. 편집 영역(편집 모드일 때만)
   - 소제목 `✎ 이 노드 편집`
   - 입력 `표시 이름`(placeholder) : `neTitle` / `neTitleType`
   - 텍스트영역 `역할·설명`(placeholder, 3행) : `neRole` / `neRoleType`
   - STEP 4 연동 노드(`node5Linked`): 경고 `⚠ STEP 4 연동 항목 — 저장 시 변경 요청으로 접수되고 STEP 4에 재검토 배지가 표시됩니다` + 주황 버튼 `변경 요청 접수 (재검토 유발)`
   - 그 외 노드(`node5Free`): 초록 버튼 `저장 (STEP 5 고유 — 즉시 반영)`
   - 두 버튼 모두 `neSave`

### 2.9 STEP 5 블록 밖의 연동 UI

| 위치 | 요소 | STEP 5와의 관계 |
|---|---|---|
| STEP 4 우측 패널 `SSOT 우선순위 · AI 의사결정 기준` (M1244~1281) | `+ 연결 추가 — 분류 대상 데이터셋에서 불러오기` / `접기 ▲`, 후보 목록 `분류 대상 데이터셋에서 선택`, 연결 카드(순위 배지, 이름, 키 배지, `▲` `▼` `✕`, 관계 설명, 결합 후보 문구, `리니지 보기 →`) | `dsExtra.ssot`(JOINED_ON 초안)를 만든다. STEP 5의 `ssotCount`가 소비한다. `리니지 보기 →`는 `goStep5` |
| STEP 4 우측 패널 `연관데이터셋` + 배지 `LPG · GROUPED_WITH` (M1282~1317) | `+ 추가 — 데이터셋 2개 묶기`, `묶을 데이터셋 2개를 선택하세요 (n/2)`, `이 두 데이터셋을 연관으로 확정할까요?` + `확정` / `확정 후 계속 추가` / `취소`, 확정 쌍 `✓ A ↔ B` + `✕` | `relPairs`를 만든다. STEP 5 완료 판정과 `relCount`, STEP 6 실행 게이트가 소비한다 |
| STEP 4 `K 연계키` 카드 (M1153~1164) | 드래그 칩 `⠿ K5 도로링크`, `⠿ K6 차량`, `⠿ K7 시각`, 감지 결과 목록, `미배정: …` `+ 키 추가` | 연계키 자동 감지 규칙(4.4절)의 출처 |
| STEP 4 `분류 관계 맵` SVG (M1219~1225) | 하단 파란 박스와 점선 `JOINED_ON (K?)` | `dsExtra.ssot` 앞 4건을 그린다 |
| STEP 4 헤더 (M1029~1031) | `⚠ 재검토 {{ reviewCount }}건 — STEP 5 변경 요청` (tooltip = `reviewTip`) | STEP 5 편집 모드의 `reviewFlags`를 소비 |
| STEP 6 (M1938~1950) | 모달 `⚠ 리니지 미결 상태입니다` | `linAsk`, `linReason`, `linWaived` |
| 하단 고정 바 (M3876~3889) | `이전`, `임시저장`/`✓ 임시저장`, `다음 (확정)` 등 | G1→G4 진행과 STEP 6 이동 |
| 카탈로그 상세 (M2919) | `리니지는 STEP 5 그래프 →` | `goStep5` |

참고: `pipe`(1..4)는 STEP 5가 아니라 STEP 6 검증 화면의 4단 파이프(`① 자동추출` → `② 담당자 검수 + sLLM 보정` → `③ SHACL 검증` → `④ 발행`) 선택 상태다(M2018~2024, L2631~2633). STEP 5와는 `go()`의 임시저장 표시 초기화 규칙(L17)과 `prevStep`/`nextStep`의 하위 뷰 순회 방식만 공유한다.

---

## 3. 사용자 동작 → 결과

모든 `this.go(patch)` 호출은 400ms 디바운스로 `persistDraft()`(localStorage `fde-studio-draft`)를 실행한다(L19~20). `patch`에 `plane`, `step`, `tab3`, `gran`, `pipe` 중 하나라도 있으면 `savedHere=false`가 되어 `✓ 임시저장` 버튼이 `임시저장`으로 돌아간다(L17).

### 3.1 그래뉼래리티 전환

| 동작 | 상태 변화 | 결과 |
|---|---|---|
| `G1 시스템` ~ `G4 컬럼` 클릭 | `gran = 1..4`, `savedHere=false` | 해당 SVG로 교체. 패널 제목 접두(`시스템 상세` 등), `granLabel`, SHACL 가이드 표시 여부와 건수가 바뀐다. `node5`는 초기화되지 않아 이전에 고른 노드 상세가 그대로 남는다 |
| 하단 `다음 (확정)` (L2965~2994) | 먼저 `autoSave()`(L42: `saveTime=HH:MM`, 드래프트 저장). `gran < 4`이면 `gran+1` 후 `showToast()` 하고 종료 | 토스트 `✓ prov:Activity ACT-K-04xx 기록됨` (2.2초). ID는 `'ACT-K-' + (400 + floor(random×99))`를 4자리로 채운 난수(L47)이며 `actLog`에는 남지 않는다 |
| 하단 `다음 (확정)` at G4 | `showToast()` 후 `go({step:6, notify:{from:'STEP 5', to:'STEP 6', owner:'데이터 품질관리팀'}})` | 알림 팝업 `STEP 5 확정 완료 → STEP 6 작업 요청` (5초 후 자동 닫힘, L2991~2992). 이동 전 `stepGate(6).canEnter`(= 조합 확정) 검사 |
| 하단 `이전` (L2957~2964) | `persistDraft()` 후 `gran > 1`이면 `gran-1`, G1이면 `step=4` | 수준을 거꾸로 순회 |

게이트 관련 사실:

- `gran` 기본값이 2이므로 "G1→G4 순서로 진행"이라는 안내와 달리 처음 진입하면 G2에서 시작한다. G1은 `이전` 또는 탭 클릭으로만 볼 수 있다.
- `다음 (확정)`은 SHACL 위반 여부, 관계 지정 여부, 모든 수준 열람 여부를 검사하지 않는다. 탭으로 곧장 G4에 간 뒤 누르면 STEP 6으로 넘어간다.
- 코드에는 쓰이지 않는 확정 버튼 규칙이 남아 있다(L2943~2948). `confirmBtnStyle`은 `gran===4 && viol===0`일 때만 파란색 활성, `confirmNote`는 `마지막 단계(G4 컬럼)까지 검토 완료 후 활성화됩니다 — 현재 G{n} 검토 중` / `모든 수준 검토 완료 · SHACL 통과 — 확정 가능` / `G4 도달 — SHACL 위반 {viol}건 해결 시 활성화됩니다`. 마크업 어디에도 바인딩되지 않았다. 원 설계 의도(G4 도달 + Violation 0건일 때만 확정)로 보고 실제 제품에서 살려야 한다. `viol`은 `props.violationCount ?? 0` (L375).

### 3.2 엣지 목록 펼치기

`더보기 (15종 전체) ▾` 클릭 → `edgesOpen` 토글 → 15개 칩 표시, 라벨이 `접기 ▴`로 바뀐다. 초기 상태는 `false`(L3). 칩은 표시만 하고 필터 기능은 없다.

### 3.3 G1 동적 라벨 계산 (L1530~1548)

입력: `combo`(STEP 2 조합, 각 항목 `{n, k}`), `procName`, `procList`.

1. `others = combo.filter(c => !/공간정보.*도로/.test(c.n))` : 베이스(도로 공간정보)를 뺀 나머지
2. `others`가 비면(`useDefs`) 기본 시나리오 3개를 표시: `['eTAS 운행기록','차량 흐름']`, `['사고심층조사','+ 오픈마켓 30종']`, `['기상청 관측수집','타 부처 · prov:Agent']`
3. `others`가 1건 이상이면 앞에서 최대 3건만 중앙 노드로 쓰고 남는 슬롯은 숨긴다(`g1N?On=false`, 해당 노드와 양쪽 엣지 미표시). 4번째 이후 데이터셋은 그려지지 않는다.
4. 노드 이름 `shortName(n)`: 길이 14 초과면 `sample_` 접두를 떼고 12자 + `…`, 아니면 그대로
5. 노드 부제 `subOf(n)`: 아래 순서로 첫 일치
   - `cctv.vehicle.det.v1` → `관측 스트림 · 통제`
   - `kma.aws.obs.v1` → `컨텍스트 · 기상청`
   - `/사고/` → `사고 원인 정보`
   - `/도로/` → `베이스 지도`
   - `/기상/` → `타 부처 · 협약 확인`
   - 그 외 → `정형 (엑셀)`
6. 엣지 라벨 `g1E?` = `eOf(n)`: `cctv.vehicle.det.v1` → `K5 도로링크 · 관측`, `kma.aws.obs.v1` → `K7 as-of · 컨텍스트`, 그 외 → `K7 시각`. 해당 슬롯에 조합 항목이 없으면 기본 `차량 흐름` / `사고` / `기상`
7. `g1Names` = 표시 중인 노드 이름을 ` · `로 연결(없으면 `(조합 없음)`)
8. `g1ProcName` = `procName`을 ` + `로 나눈 모든 이름이 `procList`에 존재하면 `procName`, 아니면 `현재 프로세스`

결함: 중앙 3노드의 클릭 핸들러는 표시 중인 데이터셋과 무관하게 `flow`/`acc`/`wx`로 고정이다. 조합이 다른 데이터셋이어도 우측에는 eTAS, 사고심층조사, 기상청의 하드코딩 상세가 나온다. 베이스 노드 라벨도 `공간정보 통합포털`로 고정이다.

### 3.4 노드 클릭

| 대상 | 핸들러 | 상태 변화 |
|---|---|---|
| G1~G3의 원/사각형 | `mk(k)` (L1433) | `node5 = k`, `neT = null`, `neR = null` |
| G4의 원 5개 | `mkCol(info)` (L1467) | `node5 = 'col'`, `colInfo = info`. `neT`/`neR`는 초기화하지 않는다(편집 중이던 텍스트가 다른 컬럼 편집란에 남는 결함) |
| G4 표의 행 | `gc.pick` (L1519~1524) | `g4Col = col`, `node5 = 'col'`, `colInfo = { title: '{탭 라벨} · {col}', role: '컬럼 — {note} · 타입 {type}[ · 연계키 {k}] · 결측률 {nullRate}', id: 'COL-신규 (카탈로그 확정 시 발급)', keys: k ? [k] : [] }` |
| G4 탭 | `g4TabRoad/Acc/Mart` | `g4Tab = 'road'|'acc'|'mart'`, `g4Col = null` (`node5`, `colInfo`는 유지) |

패널 값 결정(L1428~1436, L1460~1461):

- `curBase` = `node5 === 'col' && colInfo`이면 `colInfo`, 아니면 `nodes[node5 || 'base']`(없는 키면 `nodes.base`)
- `editKey` = 컬럼이면 `'col:' + colInfo.title`, 아니면 `node5 || 'base'`
- `cur = { ...curBase, ...nodeEdits[editKey] }` : 사용자 수정이 제목과 역할을 덮어쓴다
- `node5Title = cur.title`, `node5Role = cur.role`, `node5Id = cur.id`, `node5Keys = cur.keys`
- `base` 노드의 제목만 동적이다: `combo[0].n` → 없으면 `upList[0].name` → 없으면 `(작업 데이터셋 없음)` (L1412). 조합 첫 항목이 도로 데이터가 아니어도 그대로 베이스로 표시한다.

### 3.5 편집 모드와 노드 편집

| 동작 | 처리 |
|---|---|
| `✎ 편집 모드` 클릭 | `editMode` 토글. 배너와 패널 하단 편집 영역 표시 |
| `표시 이름` 입력 | `neT = 입력값` (매 변경마다 `go()` → 드래프트 저장). 표시값은 `neT ?? cur.title` |
| `역할·설명` 입력 | `neR = 입력값`. 표시값은 `neR ?? cur.role` |
| `저장 (STEP 5 고유 — 즉시 반영)` (비연동 노드) | `nodeEdits[editKey] = { title, role }`, `neT = neR = null`. 토스트 `✓ 저장됨 — STEP 5 고유 정보 즉시 반영 · prov:Activity 기록` (3.2초). 이후 `autoSave()` |
| `변경 요청 접수 (재검토 유발)` (연동 노드) | 위와 동일하게 `nodeEdits`에 즉시 반영하고, 추가로 `reviewFlags`에 `{ target: curBase.title, when: 'YYYY-MM-DD HH:MM' }`를 덧붙인다(`when`은 `toISOString()` 기준이라 UTC). 토스트 `⚠ 변경 요청 접수 — STEP 4에 재검토 배지 표시 · prov:Activity 기록 (승인 시 양쪽 동기화)` |

연동 노드 판정(L1432): `node5`가 `base`, `flow`, `acc`, `wx` 중 하나. `node5`가 비어 있을 때의 기본값도 `base`이므로 연동이다.

STEP 4에 미치는 영향(L1679~1681): `reviewOn = reviewFlags.length > 0`이면 STEP 4 헤더에 `⚠ 재검토 N건 — STEP 5 변경 요청` 배지. tooltip은 각 항목 `{target} ({when})`을 줄바꿈으로 잇고 끝에 `— STEP 5 편집 모드에서 접수된 변경 요청 · 승인 시 양쪽 동기화`.

목업의 한계:

- "변경 요청"이라고 부르지만 승인 전에도 STEP 5 표시값은 즉시 바뀐다. 승인, 반려, 배지 해제 흐름이 없고 `reviewFlags`는 누적만 된다.
- 토스트가 "prov:Activity 기록"이라고 하지만 `logAct()`를 호출하지 않아 `actLog`에 남지 않는다.
- 편집 가능한 것은 제목과 역할 텍스트뿐이다. 배너가 말하는 "파생 설계"나 결합 관계 자체는 편집할 수 없다.
- `invalidateDownstream()`을 부르지 않으므로 STEP 6~8 결과가 무효화되지 않는다.

### 3.6 SHACL 가이드 링크

`STEP 3 폼에서 수정 →`, `STEP 3 프로버넌스에서 추가 →` 모두 `goStep3` → `go({plane:'studio', step:3})`. 특정 데이터셋, 탭, 필드로 가지 않으며 `fixBack`(복귀 배너)도 설정하지 않는다. `sLLM 제안 · 관리자 승인 필수` 배지는 장식이다.

### 3.7 STEP 4에서 일어나는 관계 지정 (STEP 5의 입력)

#### (1) SSOT 우선순위 = JOINED_ON 초안 (`dsExtra.ssot`, `linkSeq.ssot`, `linkKnown.ssot`)

| 동작 | 처리 (L2419~2493) |
|---|---|
| `+ 연결 추가 — 분류 대상 데이터셋에서 불러오기` | `ssotPick` 토글(라벨 `접기 ▲`). 후보는 STEP 4 데이터셋 목록(`liveData` = 조합 기반) 전체. 이미 추가된 것은 이름 뒤 ` ✓`, 초록, 클릭 무시 |
| 후보 클릭 | `dsExtra.ssot`에 `{ name: 데이터셋명, key: 'K 자동감지', rel: '연계키 자동 감지 후보로 연결 — 매핑 컬럼을 지정하세요', pairs: '결합 후보 계산 대기' }` 추가, `ssotPick=false`, `showToast()` |
| `▲` / `▼` | 표시 순서 배열 `linkSeq.ssot`에서 인접 항목과 자리를 바꾸고 `linkKnown.ssot = 현재 건수` 기록, `showToast()`. 맨 위가 `1순위`(검정 배지), 이하 `2순위`… |
| `✕` | `dsExtra.ssot`에서 해당 항목 제거, `linkSeq.ssot = null`, `linkKnown.ssot = 0`(순서가 추가 순으로 초기화됨), `showToast()` |
| `리니지 보기 →` | `goStep5` |

순서 복원 규칙(L2454~2460): `linkSeq.ssot`가 없으면 추가 순. 있으면 범위를 벗어난 인덱스를 버리고, `linkKnown.ssot` 이후에 추가된 항목만 뒤에 붙인다.

미구현 사항: `key`는 항상 문자열 `K 자동감지`이고 매핑 컬럼을 지정하는 UI가 없다. `pairs`도 항상 `결합 후보 계산 대기`다. 연결의 "기준(source)" 데이터셋 개념이 없이 전역 목록 하나다.

죽은 코드: `linkPickOn`/`linkPickToggle`/`linkAddK5`/`linkAddK6`/`linkAddK7`/`dropLink`(L2511~2549)는 마크업에 바인딩되지 않았다. 의도는 (a) K5/K6/K7 키 기준 연결 초안 `{ name: '상대 데이터셋 선택…', key, rel: '{key} 기준 연결 초안 — 상대 데이터셋과 매핑 컬럼을 지정하세요', pairs: '결합 후보 계산 대기 · 확정 시 prov:Activity 기록' }` 추가, (b) 데이터셋 드래그 드롭 시 `{ name, key: '연계키 자동 탐지', rel: '{name} 연결 초안 — 공통 연계키·매핑 컬럼 자동 탐지 중', pairs: '결합 후보 계산 대기 · 확정 시 prov:Activity 기록' }` 추가다. K 칩 드롭 분기는 `dsExtra[dsSel]`(데이터셋 인덱스 키)에 쓰는데 이 값을 읽는 화면이 없다(데모 스냅숏의 `dsExtra["0"]`이 그 잔재). STEP 4 K 칩의 `draggable`은 드롭 대상이 없어 동작하지 않는다.

#### (2) 연관데이터셋 = GROUPED_WITH (`relPairs`, `relPick`, `relSel`)

| 동작 | 처리 (L2388~2417) |
|---|---|
| `+ 추가 — 데이터셋 2개 묶기` | `relPick=true`, `relSel=[]` |
| 후보 버튼 클릭 | 선택 토글. 이미 2개면 추가 선택 무시. 선택된 것은 이름 뒤 ` ✓`와 파란 스타일. 제목 `묶을 데이터셋 2개를 선택하세요 (n/2)` |
| 2개 선택 시 | 확인 박스 `이 두 데이터셋을 연관으로 확정할까요?` 노출 |
| `확정` | `relPairs.push(relSel)`, `relPick=false`, `relSel=[]`, `showToast()`, `autoSave()` |
| `확정 후 계속 추가` | `relPairs.push(relSel)`, `relSel=[]`(선택 UI 유지), `showToast()`, `autoSave()` |
| `취소` | `relPick=false`, `relSel=[]` |
| 확정 쌍의 `✕` (연관 해제) | 해당 인덱스 제거. 토스트와 저장 호출 없음 |

표시 라벨: `sample_` 접두를 뗀 이름으로 `A ↔ B`. 중복 쌍, 순서만 바뀐 쌍(A↔B와 B↔A)을 막지 않는다. 쌍은 방향이 없는 2원소 배열이다.

`relPick`, `relSel`, `ssotPick`, `linkPick`은 드래프트 저장 제외 대상이다(L94).

### 3.8 리니지 미결 게이트와 사유 기록 (STEP 6 `검증 실행` 시점)

`v7Run` 첫머리(L1659):

```
if (!(s.relPairs || []).length && !s.linWaived && (s.combo || []).length > 1 && !s.linAsk) {
  this.setState({ linAsk: true }); return;
}
```

즉 조합이 2건 이상인데 연관데이터셋 쌍이 하나도 없고 사유 기록도 없으면 검증을 실행하지 않고 모달을 띄운다.

모달(M1938~1949):

- 제목 `⚠ 리니지 미결 상태입니다`
- 본문 `STEP 5 매핑이 "계산 대기"로 방치되어 있습니다 — 이대로 진행하면 prov 그래프가 불완전합니다. 진행하려면 사유를 입력하세요 (actLog 기록 · 은폐 불가).`
- 텍스트영역 placeholder `그래도 진행하는 사유 — 예: 단일 소스 시범 검증, 리니지는 2차에 보강` (`linReason`, `linReasonSet`)
- 버튼 `돌아가기 (STEP 5)` (`linBack`): `linAsk=false` 후 STEP 5로 이동
- 버튼 `그래도 진행 (사유 기록)` (`linGo`): 사유가 공백이면 회색 비활성 스타일이고 클릭해도 무시. 사유가 있으면
  - `logAct('홍길동 (나)', '리니지 미결 상태로 검증 진행 — 사유: ' + reason)` → `actLog`에 `{t: HH:MM, who, txt, actId: 'ACT-K-' + 4자리 시퀀스}` 추가(최근 10건 유지, `actSeq` 증가, L53~61)
  - `linWaived=true`, `linAsk=false`, `linReason=''`
  - 토스트 `사유 기록됨 (prov:Activity) — [검증 실행]을 다시 누르세요` (2.8초)

결과: `linWaived=true`는 `stepGate(5).done`도 참으로 만들어 스텝퍼의 STEP 5에 ✓가 뜬다.

결함:

- 게이트 조건이 `relPairs`(GROUPED_WITH)만 본다. SSOT 연결(JOINED_ON)을 아무리 지정해도 미결로 판정하고, 반대로 무관한 두 데이터셋을 한 쌍 묶기만 하면 통과한다. 모달 문구의 "계산 대기"(= SSOT 연결의 `pairs` 문구)와 판정 기준이 어긋난다.
- `linWaived`를 되돌리는 코드가 없다. 프로세스 저장 키(`workKeys`, L920)에도 없어서 새 프로세스를 시작해도 유지된다. 드래프트에는 저장된다. 데모 삭제, 데모 복구 때만 사라진다.
- `linAsk`, `linReason`은 드래프트 저장 제외다(L95).
- `FIX_ROUTE.lineage5 = { step: 5, label: '연계 초안 행' }`(L137)이 정의되어 있으나 `validateDs()`는 리니지 관련 위반을 만들지 않아 쓰이지 않는다. STEP 5에는 "연계 초안 행"이라는 UI도 없다(STEP 4에 있음).

### 3.9 하류 단계 무효화

`invalidateDownstream(kind, msg)`(L344~356) 호출 지점은 조합 추가/제거(`'combo'`)와 STEP 3 승인(`'catalog'`)뿐이다. STEP 5의 어떤 동작(노드 편집, 수준 확정)도, STEP 4의 관계 지정(SSOT 추가/순서 변경/삭제, 연관 쌍 확정/해제)도 하류를 무효화하지 않는다.

STEP 5에 간접적으로 미치는 것은 조합 변경뿐이다. 조합이 바뀌면 G1 라벨과 `base` 제목이 다시 계산되지만 `relPairs`와 `dsExtra.ssot`에 남은 데이터셋 이름은 정리되지 않아 조합에 없는 데이터셋을 가리키는 관계가 남을 수 있다.

실제 제품 요구: 관계(JOINED_ON, GROUPED_WITH, 키 매핑, 순위) 변경과 승인된 변경 요청은 정본 그래프를 바꾸므로 `'catalog'`와 같은 수준의 무효화(검증 결과 stale 표시, 직렬화·진단 초기화, 활동 로그 기록)를 일으켜야 한다.

### 3.10 그 밖의 연동

- 홈 대시보드의 "다음 권장" 로직(L597~603)은 STEP 3 → 4 → 6으로 건너뛰며 STEP 5를 권하지 않는다.
- 프로세스 저장/복원(`workKeys`, L920)에 포함되는 STEP 5 관련 키: `dsExtra`, `linkSeq`, `linkKnown`, `relPairs`, `dsGroups`(어디서도 쓰이지 않는 예약 키), `gran`, `pipe`, `nodeEdits`, `reviewFlags`. 포함되지 않는 키: `node5`, `colInfo`, `g4Tab`, `g4Col`, `editMode`, `neT`, `neR`, `linWaived`, `edgesOpen`.

---

## 4. 데이터 (하드코딩 원문)

### 4.1 노드 상세 사전 `nodes` (L1413~1427)

| key | title | role | id | keys |
|---|---|---|---|---|
| `base` | (동적) `combo[0].n` \|\| `upList[0].name` \|\| `(작업 데이터셋 없음)` | `B 베이스 지도 · SSOT 1순위 — 이 위에 차량 흐름·교통사고·기상 데이터가 결합되어 사고 원인 분석의 기준 공간이 됩니다` | `DST-신규 (확정 시 발급)` | `K5 도로링크`, `K3 좌표 (EPSG 미선언 ⚠)` |
| `flow` | `sample_디지털운행기록분석시스템(eTAS)` | `차량 흐름 — 주행 궤적·속도를 베이스 지도 위 도로링크에 결합 (JOINED_ON)` | `DST-신규 (확정 시 발급)` | `K6 차량ID`, `K7 시각` |
| `acc` | `sample_교통사고심층조사시스템 + 데이터오픈마켓(30종)` | `사고 발생·원인 정보 — 두 데이터셋은 GROUPED_WITH 연관 그룹으로 묶여 분석의 사건 축이 됩니다` | `DST-신규 (확정 시 발급)` | `K2 주소`, `K7 시각` |
| `wx` | `sample_실시간기상관측자료수집시스템_기상청` | `기상 조건 — 사고 시점의 기상을 결합 (타 부처 · 협약 확인 후 연결)` | `DST-예정 (협약 확인 후)` | `K7 시각` |
| `lake` | `빅데이터센터 (레이크·마트)` | `수집·저장 및 사고 원인 분석 실행 환경 — 4개 원천을 레이크로 모아 분석본을 산출합니다` | `SYS-LAKE-01` | (없음) |
| `fde` | `FDE 스튜디오` | `prov:SoftwareAgent — 분석 Activity 수행 주체 (WAS_ASSOCIATED_WITH)` | `AGT-FDE-01` | (없음) |
| `act` | `ACT-신규 · 사고 원인 분석` | `prov:Activity — 3개 원천을 USED로 받아 사고 원인 분석본을 생성 (확정 시 ID 발급·prov 기록)` | `ACT-신규 (확정 시 발급)` | (없음) |
| `out` | `사고 원인 분석본` | `산출 데이터셋 — 도로·차량 흐름·사고·기상 결합 결과 (WAS_GENERATED_BY)` | `DST-신규 (확정 시 발급)` | `K5 도로링크`, `K7 시각` |
| `distRoad` | `DIST-신규 · 도로목록.xlsx` | `도로 공간정보의 배포본 — 14컬럼 · ROAD_LINK_ID(PK·K5)·GEOM(K3, EPSG 미선언 ⚠) 포함, 조인의 기준 테이블` | `DIST-신규 (확정 시 발급)` | `K5 도로링크`, `K3 좌표` |
| `distAcc` | `DIST-신규 · 사고심층조사.xlsx` | `교통사고심층조사의 배포본 — 11컬럼 · 사고 주소(K2)는 지오코딩으로 K5 변환 후 조인` | `DIST-신규 (확정 시 발급)` | `K2 주소`, `K7 시각` |
| `mart` | `vw_road_accident (마트 조인)` | `사고 원인 분석용 마트 테이블 — 도로(K5)+사고 조인, WEATHER_CD는 협약 후 합류 · 생성 대기` | `TBL-신규 (STEP 5 확정 시 생성)` | `K5 도로링크`, `K7 시각` |
| `api` | `외부 API 유입 채널` | `향후 유입 예정 — 공공데이터포털 등 API 연계 확정 시 레이크로 연결됩니다` | `(미연결)` | (없음) |
| `mcp` | `MCP 소스` | `향후 유입 예정 — MCP 서버 경유 데이터 유입, 연계 확정 시 연결됩니다` | `(미연결)` | (없음) |

필드 의미: `title` → 패널 헤더와 `dcterms:title`, `role` → `역할 (분석 구성)`, `id` → `dcterms:identifier`, `keys` → `연계키` 칩.

G4 그래프 노드 5개의 `colInfo` (L1469~1473):

| 핸들러 | title | role | id | keys |
|---|---|---|---|---|
| `ndColCause` | `사고심층조사.xlsx · CAUSE_CD` | `컬럼 — 사고 원인 코드 61종, 분석의 핵심 축 · 타입 코드(3) · 결측률 2.2%` | `COL-신규 (카탈로그 확정 시 발급)` | (없음) |
| `ndColOccur` | `사고심층조사.xlsx · OCCUR_DT` | `컬럼 — 사고 발생시각, 시각 정렬축 · ISO 8601 정규화 완료 · 결측률 0%` | `COL-신규 (카탈로그 확정 시 발급)` | `K7 시각` |
| `ndColAddr` | `사고심층조사.xlsx · ACDNT_ADDR` | `컬럼 — 사고 주소 · ⚠ 지오코딩 → K5 변환 규칙 미등록 (도로링크 조인 차단) · 결측률 0.8%` | `COL-신규 (카탈로그 확정 시 발급)` | `K2 주소` |
| `ndG4Act` | `ACT-신규 · 사고 원인 지수 산출` | `prov:Activity — CAUSE_CD·OCCUR_DT를 USED로 받아 accident_risk_idx를 파생 (확정 시 ID 발급)` | `ACT-신규 (확정 시 발급)` | (없음) |
| `ndG4Out` | `vw_road_accident · accident_risk_idx` | `파생 컬럼 (설계) — 도로링크별 사고 위험 지수 · WAS_GENERATED_BY ACT-신규 · 기상 결합 시 정밀도 향상 예정` | `COL-신규 (STEP 5 확정 시 생성)` | `K5 도로링크` |

ID 접두 체계(화면 문구 기준): `DST-`(데이터셋), `DIST-`(배포본), `TBL-`(마트 테이블), `COL-`(컬럼), `ACT-`(활동), `SYS-`(시스템, 예 `SYS-LAKE-01`), `AGT-`(에이전트, 예 `AGT-FDE-01`). 미발급 표기는 `-신규`, 협약 대기 표기는 `-예정`.

### 4.2 엣지 15종 (M1344~1358)과 표준 속성 대응

목업이 명시하는 내용은 "PROV-O 관계(wasDerivedFrom·wasGeneratedBy·used·wasAttributedTo·wasInformedBy 등)를 LPG 엣지로 매핑한 것", "각 엣지에는 confidence·ruleSetVersion·executedAt 같은 속성이 붙습니다"(L3012), "노드 18종(Dataset·Activity·Agent·JoinKey…)·엣지 15종", "정본은 어디까지나 Turtle이고 LPG는 파생 표현"(L3011)까지다. 아래 표의 "명시 근거" 열에 근거가 없는 대응은 본 명세의 제안이다.

| # | LPG 엣지 | RDF 속성 | 명시 근거 | 목업 화면에서의 용례 |
|---|---|---|---|---|
| 1 | `WAS_DERIVED_FROM` | `prov:wasDerivedFrom` | L3012, L3028~3029 | G1 중앙 3노드 → 레이크. 패널 `엣지 프로퍼티 (WAS_DERIVED_FROM)` |
| 2 | `WAS_GENERATED_BY` | `prov:wasGeneratedBy` | L207, L3012 | G2 act→out(선은 act에서 out으로 그려짐), G4 ACT→accident_risk_idx |
| 3 | `USED` | `prov:used` | L3012 | G2 원천 3종→act, G4 컬럼 2종→ACT |
| 4 | `WAS_ATTRIBUTED_TO` | `prov:wasAttributedTo` | L3012, M1609 | G2 SHACL 위반 카드(기상청 데이터 미연결) |
| 5 | `WAS_INFORMED_BY` | `prov:wasInformedBy` | L3012 | 화면 용례 없음 |
| 6 | `WAS_ASSOCIATED_WITH` | `prov:wasAssociatedWith` | L209 | G1 fde–lake, G2 act–fde |
| 7 | `ACTED_ON_BEHALF_OF` | `prov:actedOnBehalfOf` | L3016 | 화면 용례 없음 |
| 8 | `WAS_REVISION_OF` | `prov:wasRevisionOf` | 제안 | 없음 |
| 9 | `WAS_INVALIDATED_BY` | `prov:wasInvalidatedBy` | L426 | 없음 |
| 10 | `HAD_MEMBER` | `prov:hadMember` | 제안 | 없음 |
| 11 | `SPECIALIZATION_OF` | `prov:specializationOf` | 제안 | 없음 |
| 12 | `ALTERNATE_OF` | `prov:alternateOf` | 제안 | 없음 |
| 13 | `HAS_DISTRIBUTION` | `dcat:distribution` | L197 | G3 데이터셋→배포본 |
| 14 | `IN_SERIES` | `dcat:inSeries` | L3000 | 없음 |
| 15 | `JOINED_ON` | 표준 속성 없음. 제안: `dcat:qualifiedRelation` + `dcat:Relationship`(`dcat:hadRole fde:role/joinedOn`)에 키와 컬럼 매핑을 속성으로 부여 | 제안 | G1~G4 전 수준, STEP 4 분류 관계 맵 |
| (목록 외) | `GROUPED_WITH` | 15종 칩에 없음. 제안: `dcat:qualifiedRelation`(역할 `fde:role/groupedWith`) 또는 `dcterms:relation` | 제안 | G2 보라 점선, STEP 4 `LPG · GROUPED_WITH` |

엣지 방향에 대한 주의: 목업 SVG에는 화살촉이 없다. PROV-O의 방향(`산출물 prov:wasGeneratedBy 활동`, `활동 prov:used 입력`, `산출물 prov:wasDerivedFrom 원천`)과 화면의 좌→우 데이터 흐름이 반대이므로, 실제 제품은 저장은 PROV-O 방향으로 하고 화면은 "흐름 방향 보기" 옵션으로 뒤집어 그려야 한다.

화면에 나오는 관계의 의미 요약:

| 관계 | 의미(화면 문구 근거) |
|---|---|
| `JOINED_ON` | 연계키를 조인 축으로 한 두 데이터셋(또는 배포본·테이블, 컬럼) 간 결합. STEP 4의 "SSOT 우선순위" 목록 항목 1건 = JOINED_ON 1건. 번호(①②③)는 SSOT 순위("맨 위 = 판단 기준 1순위", "AI 의사결정 기준"). `K2→K5`처럼 변환 규칙(지오코딩)이 붙을 수 있다 |
| `GROUPED_WITH` | "연관성 높은 데이터셋 2개를 묶습니다 (예: 데이터오픈마켓 ↔ 교통사고심층조사). 확정 시 LPG에 GROUPED_WITH 엣지로 기록됩니다." "확정마다 prov:Activity 기록 — STEP 5 리니지·마트 학습셋 구성에 활용" (M1286, M1316). 방향 없음 |
| `USED` | Activity가 입력 Entity를 사용 |
| `WAS_GENERATED_BY` | 산출 Entity(데이터셋, 파생 컬럼)가 Activity로 생성됨 |
| `WAS_ASSOCIATED_WITH` | Activity의 수행 주체(`prov:SoftwareAgent` FDE 스튜디오) |
| `WAS_DERIVED_FROM` | 원천에서 레이크·분석본으로의 파생. 엣지 프로퍼티 `confidence`, `ruleSetVersion`(`rs-2.1`), `executedAt`. 관련 문구 `'prov:qualifiedDerivation': 'WAS_DERIVED_FROM 엣지 3건에 confidence 속성 미부여'`(L1851) |
| `HAS_DISTRIBUTION` | 데이터셋과 배포본(xlsx) 연결 |

### 4.3 노드 유형 (범례 기준)

| 유형 | 색 | RDF 클래스(목업 문구 근거) | 화면 예 |
|---|---|---|---|
| Agent | #7a3fa0 | `prov:SoftwareAgent`, `prov:Organization`, `prov:Person` | FDE 스튜디오(`AGT-FDE-01`), 기상청(타 부처) |
| System | #111318 | (명시 없음) | 공간정보 통합포털, 빅데이터센터(`SYS-LAKE-01`) |
| Dataset | #1E5EFF | `dcat:Dataset` | 도로 공간정보, 디지털운행기록, 교통사고심층조사, 기상청 관측자료, 사고 원인 분석본 |
| Distribution/Table | (범례 없음) | `dcat:Distribution`, 마트 테이블 | 도로목록.xlsx, 사고심층조사.xlsx, vw_road_accident |
| Column | #2aa876 | (명시 없음) | CAUSE_CD, OCCUR_DT, ACDNT_ADDR, accident_risk_idx |
| Activity | #e8912d | `prov:Activity` | 사고 원인 분석, 사고 원인 지수 산출 |
| JoinKey | #c0392b | (명시 없음) | K5 |

### 4.4 연계키 통제어휘 K1~K9 (L731, L2381)

| 코드 | 이름 | 화면에 나타난 매핑 컬럼과 설명 |
|---|---|---|
| K1 | 행정구역 | (용례 없음) |
| K2 | 주소 | `ACDNT_ADDR`. "주소 → 좌표 지오코딩 후보", K5로 변환 후 조인 |
| K3 | 좌표 | `GEOM`(WKT), `GEOM / X·Y`. "좌표계 확인 필요 (EPSG 미선언)" |
| K4 | 건축물ID | (용례 없음) |
| K5 | 도로링크 | `ROAD_LINK_ID`(문자(10), PK), `LINK_ID`. "표준: 국가표준노드링크" |
| K6 | 차량ID | `VHCL_NO`, `OBU_IDNT_NMBR`, `obu_id`, `CarID`. "표기 방식 검수 필요" |
| K7 | 시각 | `OCCUR_DT`, `OBSV_DT`, `UPD_DT`, `ts`. "ISO 8601 정규화 대상", as-of 결합 |
| K8 | 사업ID | (용례 없음) |
| K9 | 문서ID | 자동 감지 실패 시 대체 배정 |

분류체계 관리 표의 K축 행(L785, 필드 순서 `[axis, nature, natStyle, count, codes, ver, st, stStyle]`): `['K1~K9 연계키', '필수', (필수 배지 스타일), 9, '행정구역 · 주소 · 좌표 · 건축물ID · 도로링크 · 차량ID · 시각 …', 'v2.0 (2026-05)', '개정 대기 1', (대기 배지 스타일)]`.

K축의 성격(L3003, L3009): "이 데이터가 무엇과 조인되는가"를 나타내는 축이며 "컬럼 메타데이터에서 규칙으로 도출되는 확인 사항이며 sLLM 추론 대상이 아닙니다".

STEP 4의 연계키 자동 감지 규칙(L2371~2385). 주석은 "파일명 기반 자동 감지 (하드코딩 아님)"이라고 하지만 실제로는 데이터셋 이름 정규식이다.

| 이름 정규식 | 배정 키 | 매핑 컬럼 문구 | 비고 문구 |
|---|---|---|---|
| `/도로/` | `K5 도로링크ID` | `ROAD_LINK_ID (감지)` | `표준: 국가표준노드링크 · 결합 후보 계산 대기` |
| `/도로\|공간\|경계\|좌표/` | `K3 좌표` | `GEOM / X·Y (감지)` | `좌표계 확인 필요 (EPSG 미선언)` |
| `/기상\|관측\|시간\|5분\|소통\|기록/` | `K7 시각` | `OBSV_DT / 관측일시 (감지)` | `ISO 8601 정규화 대상` |
| `/차량\|운행\|eTAS\|OBU/i` | `K6 차량ID` | `VHCL_NO (감지)` | `표기 방식 검수 필요` |
| `/사고/` | `K2 주소` | `ACDNT_ADDR (감지)` | `주소 → 좌표 지오코딩 후보` |
| (하나도 일치하지 않음) | `K9 문서ID` | `(자동 감지 실패)` | `수기 배정 필요 — 검수 큐 이동` |

`미배정:` 뒤에는 9종 중 배정되지 않은 코드를 ` · `로 이어 표시한다.

조합 항목이 들고 다니는 키 문자열 `k`의 예(L1121~1124, L2281~2296, L2254): `obu.telemetry.v2` → `K6 · K7`, `TRAFFIC_LINK_5MIN` → `K5 · K7`, `cctv.vehicle.det.v1` → `K5 · K6 · K7`, `kma.aws.obs.v1` → `K7 · K3`, `ADMIN_SGG 행정경계` → `K5`, 업로드 파일 기본값 → `K7`.

### 4.5 G1 기본값과 규칙 상수 (L1532~1540)

```json
{
  "defs": [["eTAS 운행기록", "차량 흐름"], ["사고심층조사", "+ 오픈마켓 30종"], ["기상청 관측수집", "타 부처 · prov:Agent"]],
  "edgeDefaults": ["차량 흐름", "사고", "기상"],
  "baseFilter": "/공간정보.*도로/",
  "eOf": {"cctv.vehicle.det.v1": "K5 도로링크 · 관측", "kma.aws.obs.v1": "K7 as-of · 컨텍스트", "*": "K7 시각"},
  "subOf": [["cctv.vehicle.det.v1", "관측 스트림 · 통제"], ["kma.aws.obs.v1", "컨텍스트 · 기상청"], ["/사고/", "사고 원인 정보"], ["/도로/", "베이스 지도"], ["/기상/", "타 부처 · 협약 확인"], ["*", "정형 (엑셀)"]]
}
```

### 4.6 테이블·컬럼 상세 `tables` (L1478~1505)

각 행은 `[컬럼, 타입, 연계키, 결측률, 비고]`. 연계키가 빈 문자열이면 화면에 `—`.

`road` (라벨 `도로목록.xlsx`):

| 컬럼 | 타입 | 연계키 | 결측률 | 비고 |
|---|---|---|---|---|
| ROAD_LINK_ID | 문자(10) | K5 | 0% | PK · 국가표준노드링크 체계 |
| ROAD_NAME | 문자(60) |  | 0.2% | 도로명 |
| ROAD_RANK | 코드(2) |  | 0% | 도로 등급 (101~107) |
| GEOM | WKT | K3 | 0% | ⚠ EPSG 미선언 — conformsTo 명시 필요 |
| LANE_CNT | 정수 |  | 1.4% | 차로 수 |
| LIMIT_SPD | 정수 |  | 3.1% | 제한속도 (km/h) |
| ROAD_LEN | 실수 |  | 0% | 링크 연장 (m) |
| UPD_DT | 일자 | K7 | 0% | 갱신일 — ISO 8601 정규화 대상 |

`acc` (라벨 `사고심층조사.xlsx`, 기본 탭):

| 컬럼 | 타입 | 연계키 | 결측률 | 비고 |
|---|---|---|---|---|
| ACDNT_ID | 문자(12) |  | 0% | PK · 사고 관리번호 |
| ACDNT_ADDR | 문자(120) | K2 | 0.8% | ⚠ 지오코딩 → K5 변환 규칙 미등록 (조인 차단) |
| OCCUR_DT | 일시 | K7 | 0% | ISO 8601 정규화 완료 |
| CAUSE_CD | 코드(3) |  | 2.2% | 사고 원인 코드 61종 — 분석 대상 축 |
| CASLT_CNT | 정수 |  | 0% | 사상자 수 |
| DTH_CNT | 정수 |  | 0% | 사망자 수 |
| WEATHER | 자유 텍스트 |  | 7.9% | 기상 자유 표기 — 기상청 결합 시 코드 대체 예정 |
| ROAD_COND | 코드(2) |  | 4.5% | 노면 상태 |

`mart` (라벨 `vw_road_accident`):

| 컬럼 | 타입 | 연계키 | 결측률 | 비고 |
|---|---|---|---|---|
| ROAD_LINK_ID | 문자(10) | K5 | — | ← 도로목록 (조인 키) |
| ACDNT_ID | 문자(12) |  | — | ← 사고심층조사 |
| OCCUR_DT | 일시 | K7 | — | 시각 정렬축 |
| CAUSE_CD | 코드(3) |  | — | 사고 원인 |
| GEOM | WKT | K3 | — | ← 도로목록 (사고 지점 스냅) |
| WEATHER_CD | 코드(2) |  | — | 기상청 결합 후 합류 (협약 확인 필요) |
| accident_risk_idx | 실수 |  | — | 파생 컬럼 — ACT-신규 산출 (설계) |

불일치: G3 그림과 `distRoad`/`distAcc` 역할 문구는 "14컬럼", "11컬럼"이라고 하지만 표에는 각 8컬럼만 있다.

### 4.7 마트 조인 정의 (화면 문구에서 추출)

목업에는 조인 정의 객체가 없고 그림과 문구로만 존재한다. 추출하면 다음과 같다.

```json
{
  "mart": "vw_road_accident",
  "status": "생성 대기 (STEP 5 확정 시 생성)",
  "purpose": "사고 원인 분석용",
  "sources": [
    {"table": "도로목록.xlsx", "role": "조인의 기준 테이블", "joinKey": {"k": "K5", "column": "ROAD_LINK_ID"}},
    {"table": "사고심층조사.xlsx", "joinKey": {"k": "K2→K5", "column": "ACDNT_ADDR",
      "transform": "지오코딩 + 최근접 링크 스냅 (주소 → 좌표 → 도로링크)", "ruleStatus": "미등록 (조인 차단)"}},
    {"dataset": "기상청 관측자료", "joinKey": {"k": "K7", "column": "OCCUR_DT"}, "status": "협약 확인 후 합류"}
  ],
  "columns": [
    {"name": "ROAD_LINK_ID", "from": "도로목록", "k": "K5"},
    {"name": "ACDNT_ID", "from": "사고심층조사"},
    {"name": "OCCUR_DT", "from": "사고심층조사", "k": "K7", "note": "시각 정렬축"},
    {"name": "CAUSE_CD", "from": "사고심층조사"},
    {"name": "GEOM", "from": "도로목록", "k": "K3", "note": "사고 지점 스냅"},
    {"name": "WEATHER_CD", "from": "기상청", "note": "협약 후"},
    {"name": "accident_risk_idx", "derived": true, "activity": "ACT-신규 · 사고 원인 지수 산출", "used": ["CAUSE_CD", "OCCUR_DT"]}
  ]
}
```

G2 수준의 결합 정의(그림 기준): 베이스 `도로 공간정보`에 대해 ① `디지털운행기록` JOINED_ON `K5`, ② `교통사고심층조사` JOINED_ON `K5·K2`, ③ `기상청 관측자료` JOINED_ON `K7`. Activity `ACT-신규 · 사고 원인 분석`이 세 원천을 USED, 산출 `사고 원인 분석본`(DST-신규).

### 4.8 SHACL 위반 카드 원문 (M1600~1618)

G3에서 1건:

| 항목 | 내용 |
|---|---|
| 심각도 | `Violation` |
| 대상 | `DIST-신규 (사고심층조사.xlsx)` |
| 제목 | `K2 주소 → K5 변환 규칙 미등록` |
| 설명 | `사고 위치가 주소(ACDNT_ADDR)로만 있어 지오코딩 변환 규칙 없이는 도로링크(K5) 조인 테이블 생성이 차단됩니다 (JoinRuleShape).` |
| 해결방안 | `주소 → 좌표 → 도로링크 매칭 규칙(지오코딩 + 최근접 링크 스냅) 등록 후 재검증.` 링크 `STEP 3 폼에서 수정 →`, 배지 `sLLM 제안 · 관리자 승인 필수` |

G2에서 2건:

| 항목 | 1번 | 2번 |
|---|---|---|
| 심각도 | `Violation` | `Warning` |
| 대상 | `DST-신규 (기상청 관측자료)` | `DST-신규 (도로 공간정보)` |
| 제목 | `prov:wasAttributedTo 미연결` | `좌표계(EPSG) 미선언` |
| 설명 | `타 부처(기상청) 생산 책임자 Agent가 연결되지 않아 리니지에서 책임 주체 추적이 끊깁니다 (ActivityShape) — 협약 확인 전 결합 불가.` | `K3 좌표 컬럼(GEOM)이 감지됐으나 좌표계 선언이 없어 JOINED_ON 공간 결합 검증에서 제외됩니다.` |
| 해결방안 | `기상청 관측수집 Agent(prov:Organization) 연결 + 기관 간 협약 근거 문서 등록.` 링크 `STEP 3 프로버넌스에서 추가 →` | `dcterms:conformsTo EPSG:5186 등 좌표계 명시.` 링크 `STEP 3 폼에서 수정 →` |

G1, G4에서는 카드가 표시되지 않는다. 언급된 Shape 이름: `JoinRuleShape`, `ActivityShape`.

### 4.9 STEP 4 시드 데이터 중 관계 관련 부분 (L2321~2348)

`data[].links`는 현재 화면에서 읽히지 않는 잔존 시드다(`dsLinks`는 `dsExtra.ssot`만 읽고 `baseLen = 0`, L2453, L2477). 실제 제품의 "결합 후보 계산 결과" 형태를 보여 주는 유일한 표본이므로 그대로 옮긴다. 필드: `name`(상대 데이터셋), `key`(연계키), `rel`(결합 의미), `pairs`(결합 후보 쌍 수와 매핑 컬럼 쌍).

```json
{
  "TRAFFIC_LINK_5MIN": [
    {"name": "ADMIN_SGG 행정경계", "key": "K5 도로링크", "rel": "공간 포함 관계 — 행정경계 구간(좌표) 위 도로링크의 소통정보 산출", "pairs": "결합 후보 17,417쌍 · LINK_ID ↔ 경계 내 링크"},
    {"name": "obu.telemetry.v2", "key": "K7 시각", "rel": "시각 동기 결합 — 5분 정렬 시각축으로 텔레메트리와 병합", "pairs": "결합 후보 13,028쌍 · OBSV_DT ↔ ts"}
  ],
  "ADMIN_SGG 행정경계": [
    {"name": "TRAFFIC_LINK_5MIN", "key": "K5 도로링크", "rel": "공간 포함 관계 — 경계 구간(좌표) 위 도로링크 소통정보 연결", "pairs": "결합 후보 17,417쌍 · 경계 내 링크 ↔ LINK_ID"}
  ],
  "etas_inspect_log": [
    {"name": "obu.telemetry.v2", "key": "K6 차량", "rel": "차량ID 결합 — 검사 판정과 실주행 데이터 대조", "pairs": "결합 후보 7,912쌍 · OBU_IDNT_NMBR ↔ obu_id"}
  ],
  "obu.telemetry.v2": [
    {"name": "etas_inspect_log", "key": "K6 차량", "rel": "차량ID 결합 — 검사 이력과 주행 텔레메트리 연결 (표기 불일치 검토 중)", "pairs": "결합 후보 7,912쌍 · obu_id ↔ OBU_IDNT_NMBR"},
    {"name": "TRAFFIC_LINK_5MIN", "key": "K7 시각", "rel": "시각 동기 결합 — 소통정보와 5분 정렬 병합", "pairs": "결합 후보 13,028쌍 · ts ↔ OBSV_DT"}
  ]
}
```

같은 시드의 데이터셋별 키 배열 `k`: `TRAFFIC_LINK_5MIN` `['K5','K7']`, `ADMIN_SGG 행정경계` `['K5','—']`, `etas_inspect_log` `['K6','K7']`, `obu.telemetry.v2` `['K6','K7']`. 시드에 없는 조합 항목은 `combo[].k.split(' · ')`를 쓴다(L2356).

사용자가 만드는 연결 초안의 문구 템플릿(L2431, L2519, L2535):

| 경로 | name | key | rel | pairs |
|---|---|---|---|---|
| SSOT 후보 클릭(현행 유일 경로) | 데이터셋명 | `K 자동감지` | `연계키 자동 감지 후보로 연결 — 매핑 컬럼을 지정하세요` | `결합 후보 계산 대기` |
| 키 기준 추가(죽은 코드) | `상대 데이터셋 선택…` | `K5 도로링크` / `K6 차량` / `K7 시각` | `{key} 기준 연결 초안 — 상대 데이터셋과 매핑 컬럼을 지정하세요` | `결합 후보 계산 대기 · 확정 시 prov:Activity 기록` |
| 데이터셋 드롭(죽은 코드) | 데이터셋명 | `연계키 자동 탐지` | `{name} 연결 초안 — 공통 연계키·매핑 컬럼 자동 탐지 중` | `결합 후보 계산 대기 · 확정 시 prov:Activity 기록` |

### 4.10 데모 스냅숏의 STEP 5 관련 값 (`resources/f02defb4-….json`)

```json
{
  "gran": 4, "pipe": 4, "edgesOpen": true, "editMode": false,
  "node5": "col", "g4Tab": "mart", "g4Col": null,
  "colInfo": {"title": "도로목록.xlsx · ROAD_NAME", "role": "컬럼 — 도로명 · 타입 문자(60) · 결측률 0.2%", "id": "COL-신규 (카탈로그 확정 시 발급)", "keys": []},
  "relPairs": [["sample_교통사고심층조사시스템_비정형_", "sample_디지털운행기록분석시스템(eTAS)"]],
  "dsExtra": {
    "0": [{"name": "상대 데이터셋 선택…", "key": "K5 도로링크", "rel": "K5 도로링크 기준 연결 초안 — 상대 데이터셋과 매핑 컬럼을 지정하세요", "pairs": "결합 후보 계산 대기 · 확정 시 prov:Activity 기록"}],
    "ssot": [{"name": "sample_교통사고심층조사시스템_비정형_", "key": "K 자동감지", "rel": "연계키 자동 감지 후보로 연결 — 매핑 컬럼을 지정하세요", "pairs": "결합 후보 계산 대기"}]
  },
  "linkSeq": {"0": null},
  "combo": [{"n": "실시간교통사고", "k": "K6 · K7 · K5 · K3"}, {"n": "디지털운행기록분석시스템(eTAS)_정보시스템", "k": "K7"}]
}
```

데모 스냅숏의 `relPairs`가 가리키는 두 데이터셋은 스냅숏의 `combo`에 없다. 고아 참조가 실제로 발생한다는 예다.

---

## 5. 상태 변수

| 키 | 타입 / 기본값 | 의미 | 저장 | 근거 |
|---|---|---|---|---|
| `gran` | `1\|2\|3\|4`, 기본 2 | 현재 그래뉼래리티 | 드래프트 O, 프로세스 O | L2942~2953 |
| `edgesOpen` | boolean, false | 엣지 15종 펼침 | 드래프트 O | L3, L2954 |
| `node5` | `'base'\|'flow'\|'acc'\|'wx'\|'lake'\|'fde'\|'act'\|'out'\|'distRoad'\|'distAcc'\|'mart'\|'api'\|'mcp'\|'col'`, 기본 `'base'` | 우측 패널에 표시할 노드 | 드래프트 O | L1428~1433 |
| `colInfo` | `{title, role, id, keys[]}` \| undefined | `node5==='col'`일 때의 컬럼/G4 노드 상세 | 드래프트 O | L1467, L1519 |
| `g4Tab` | `'road'\|'acc'\|'mart'`, 기본 `'acc'` | G4 컬럼 표 탭 | 드래프트 O | L1477 |
| `g4Col` | string \| null | G4 표에서 선택한 컬럼명(행 강조) | 드래프트 O | L1507 |
| `editMode` | boolean | 편집 모드 | 드래프트 O | L1437 |
| `neT`, `neR` | string \| null | 편집 중인 표시 이름, 역할 텍스트(저장 전 버퍼) | 드래프트 O(일시 상태인데 제외 목록에 없음) | L1442~1445 |
| `nodeEdits` | `{ [editKey]: {title, role} }` | 노드별 사용자 수정 오버레이. `editKey`는 노드 키 또는 `'col:' + 컬럼 제목` | 드래프트 O, 프로세스 O | L1429, L1449 |
| `reviewFlags` | `Array<{target, when}>` | STEP 4 연동 노드 변경 요청 목록(누적만 됨) | 드래프트 O, 프로세스 O | L1450, L1679 |
| `relPairs` | `Array<[string, string]>` | 연관데이터셋 확정 쌍(GROUPED_WITH). STEP 5 완료 판정과 STEP 6 게이트의 근거 | 드래프트 O, 프로세스 O | L336, L1659, L2414 |
| `relPick` | boolean | 연관 쌍 선택 UI 열림 | 저장 제외 | L94, L2397 |
| `relSel` | `string[]`(최대 2) | 선택 중인 데이터셋 이름 | 저장 제외 | L94, L2405 |
| `dsExtra` | `{ ssot: Array<{name,key,rel,pairs}>, [dsIndex]: … }` | `ssot` = SSOT 우선순위 연결(JOINED_ON 초안) 전역 목록. 숫자 키는 읽히지 않는 잔재 | 드래프트 O, 프로세스 O | L2423~2433 |
| `linkSeq` | `{ ssot: number[] \| null }` | SSOT 표시 순서(= `dsExtra.ssot` 인덱스 순열) | 드래프트 O, 프로세스 O | L2454~2461 |
| `linkKnown` | `{ ssot: number }` | 순서를 마지막으로 저장했을 때의 연결 건수(새 항목 판별용) | 드래프트 O, 프로세스 O | L2458 |
| `ssotPick` | boolean | SSOT 후보 목록 열림 | 저장 제외 | L94 |
| `linkPick` | boolean | (죽은 UI) 키 기준 연결 추가 팝업 | 저장 제외 | L94, L2511 |
| `linWaived` | boolean | 리니지 미결 상태로 진행한다는 사유가 기록됨. 해제 로직 없음 | 드래프트 O, 프로세스 X | L336, L2844 |
| `linAsk` | boolean | 리니지 미결 모달 열림 | 저장 제외 | L95, L1659 |
| `linReason` | string | 모달 입력 사유 | 저장 제외 | L95, L2837 |
| `pipe` | `1..4`, 기본 3 | STEP 6 파이프 뷰(STEP 5 소관 아님) | 드래프트 O, 프로세스 O | L2631 |
| `dsGroups` | (미사용) | `workKeys`에만 있는 예약 키 | 프로세스 O | L920 |
| `combo`, `comboMeta`, `procName`, `procList`, `upList` | (읽기 전용) | G1 라벨, `base` 제목, 게이트 계산의 입력 | | L1412, L1534, L1546 |
| `actLog`, `actSeq` | (쓰기: 사유 기록 시) | 활동 로그와 `ACT-K-` 시퀀스 | 드래프트 O | L53~61 |
| `toast`, `toastText`, `toastId`, `notify`, `saveTime`, `savedHere` | (공통) | 토스트, 단계 인계 알림, 임시저장 표시 | | L46~51, L2990 |
| `this._dragDs`, `this._dragK` | 인스턴스 필드 | (죽은 경로) 드래그 중인 데이터셋명, 키 | 저장 안 됨 | L2366, L2508 |

---

## 6. 시뮬레이션 vs 실제 계산

| 항목 | 목업의 실제 동작 | 화면이 주장하는 것 |
|---|---|---|
| G2, G3, G4 그래프 | 좌표까지 고정된 정적 SVG. 조합, SSOT 연결, 연관 쌍, 카탈로그를 읽지 않음 | 조합과 STEP 4 확정이 엣지로 반영 |
| G1 그래프 | 중앙 3노드의 이름, 부제, 엣지 키 라벨, 표시 여부만 `combo`에서 계산(이름 정규식). 좌표, 베이스, 레이크, FDE, API, MCP는 고정 | 프로세스 조합 기준 현행화 |
| 노드 상세 | `nodes` 사전의 고정 문구. `base` 제목만 `combo[0].n` | 카탈로그 속성 조회 |
| `dcat:version 1.0.0`, `ruleSetVersion rs-2.1` | 고정 문자열 | 실제 버전 |
| `confidence` | `계산 대기 (매핑 확정 후 산출)` 고정. 산출 로직 없음 | 연계키 매칭율 등 규칙 기반 산출(L3005의 설명) |
| `executedAt` | `확정 시 기록` 고정 | 확정 시각 기록 |
| 컬럼 표(타입, 결측률, PK, 연계키) | 하드코딩 3개 테이블. 업로드 파일과 무관 | 파일 스키마 프로파일 |
| 연계키 감지 | 데이터셋 이름 정규식 6개(L2374~2379) | "파일 스키마 자동 감지 결과" |
| 결합 후보 수 | 문자열 `결합 후보 계산 대기` 또는 시드 문구(`17,417쌍` 등) | 컬럼 값 기반 후보 쌍 계산 |
| SHACL 가이드 | 수준별 고정 카드 3장, `guideCount`는 2 또는 1 상수. STEP 6의 `validateDs()` 결과와 무관 | 리니지 Shape(JoinRuleShape, ActivityShape) 검증 결과 |
| ID 발급(DST/DIST/TBL/COL/ACT-신규) | 발급 로직 없음. STEP 5에서 어떤 ID도 만들지 않음 | STEP 5 확정 시 발급 |
| 마트 테이블 생성 | 없음 | STEP 5 확정 시 `vw_road_accident` 생성 |
| prov:Activity 기록(수준 확정) | `showToast()`가 난수 ID를 토스트로만 표시. `actLog` 미기록 | 모든 확정이 Activity로 기록 |
| prov:Activity 기록(노드 편집) | 토스트 문구뿐. `actLog` 미기록 | 모든 변경이 Activity로 기록 |
| 변경 요청과 재검토 | `reviewFlags`에 누적, STEP 4 배지 숫자만 증가. 승인/반려/동기화 없음, 수정은 즉시 반영 | 승인 시 양쪽 동기화 |
| 리니지의 RDF 반영 | `buildTriples()`(L187~212)는 데이터셋마다 `prov:wasGeneratedBy`, `prov:Activity`, `prov:wasAssociatedWith`만 생성. JOINED_ON, GROUPED_WITH, `prov:used`, `prov:wasDerivedFrom`, 컬럼, 마트는 트리플에 전혀 없음. 따라서 STEP 6 검증과 STEP 7 산출물은 STEP 5 내용을 담지 않음 | Turtle 정본에 리니지 기록, LPG는 그 파생 |
| LPG 투영(Neo4j) | 없음. 관리 화면에 외부 연계명만 표기 | Neo4j 투영 |
| 하류 무효화 | STEP 4, 5의 관계 변경은 무효화하지 않음 | 정본 변경 시 재검증 |

실제로 계산되는 것(결정적 로직):

1. `stepGate(5)`: 진입 = 조합 확정, 완료 = `relPairs.length > 0 || linWaived` (L336)
2. STEP 6 실행 전 리니지 미결 게이트와 사유 필수 입력, `actLog` 기록(L1659, L2840~2846)
3. G1 라벨 파생(L1530~1548)
4. G4 행 선택 시 `colInfo` 문구 조립(L1519~1524)
5. `nodeEdits` 오버레이 병합(L1428~1431)
6. SSOT 순서 순열 유지 로직(L2452~2493)
7. `ssotCount`, `relCount` 집계(L1676~1677)
8. G1→G4 순회와 단계 인계 알림(L2957~2994)

---

## 7. 실제 제품에서 필요한 기능

대상 구성: FastAPI + PostgreSQL + rdflib/pySHACL 백엔드, React 프론트엔드. 본 절의 스키마, 엔드포인트, 트리플 패턴은 목업에서 도출한 제안이다.

### 7.1 백엔드 기능 요구

1. 관계 저장소
   - 프로세스(조합) 단위로 데이터셋 간 관계를 저장한다. 유형은 최소 `JOINED_ON`, `GROUPED_WITH`. 방향(기준 → 상대), SSOT 순위, 상태(초안 / 확정 / 변경 요청 중), 근거(자동 감지 / 수기)를 가진다.
   - `JOINED_ON`은 키 매핑을 1개 이상 가진다: 연계키 코드(K1~K9), 원천 컬럼, 상대 컬럼, 변환 규칙(예 K2→K5 지오코딩 + 최근접 링크 스냅, K7 as-of 허용 오차), 매칭 통계(후보 쌍 수, 매칭율, 표본).
   - `GROUPED_WITH`는 무방향이므로 정규화된 쌍(작은 ID가 앞)으로 저장하고 중복을 막는다.
   - 조합에서 데이터셋이 빠지면 그 데이터셋을 참조하는 관계를 고아로 표시하거나 함께 정리한다.
2. 컬럼 프로파일과 연계키 후보 탐지
   - 업로드/등록된 배포본에서 스키마와 프로파일(타입, 길이, 결측률, 고유값 수, PK 후보, 값 패턴, 최소/최대, 표본 또는 스케치)을 추출해 저장한다.
   - 규칙 기반 K코드 배정: 컬럼명 사전(`ROAD_LINK_ID`, `LINK_ID` → K5 등), 타입, 값 패턴(ISO 8601, WKT, 10자리 링크 ID, 주소 형태), 표준 코드표 대조. 목업 방침(L3003)에 따라 sLLM 추론이 아니라 규칙 엔진으로 처리하고 결과는 "검수 필요"로 표시한다.
   - 데이터셋 쌍별 조인 후보 탐지: 같은 K코드를 가진 컬럼 쌍을 대상으로 값 포함율/자카드(표본 또는 MinHash/HLL 스케치), 유일성, 시간축 겹침 구간과 해상도 정합(K7), 좌표계 선언 여부와 공간 포함(K3), 주소 지오코딩 가능성(K2)을 계산해 `결합 후보 N쌍 · A ↔ B` 형태의 결과와 `confidence`를 만든다. 비동기 작업으로 실행하고 "계산 대기 / 계산 중 / 완료 / 실패" 상태를 제공한다.
3. 리니지 그래프 조립과 수준별 투영
   - G1(시스템), G2(데이터셋), G3(배포본·테이블), G4(컬럼) 뷰를 같은 정본에서 집계해 노드/엣지 JSON으로 제공한다. 레이아웃은 프론트엔드(예: dagre/elk)에서 계산한다.
   - 노드 유형: Agent, System, Dataset, Distribution/Table, Column, Activity, JoinKey. 엣지 유형: 4.2절 15종 + GROUPED_WITH.
   - 범례 개수는 실제 그래프에서 집계한다.
4. PROV 트리플 생성
   - 확정 시 `buildTriples`에 해당하는 서버 측 빌더가 리니지 트리플을 추가 생성한다. 네임스페이스 `fde: <https://catalog.molit.go.kr/def/>`(L233), 에이전트 IRI `https://catalog.molit.go.kr/id/agent/fde-studio`(L209).

   ```turtle
   # 산출 데이터셋과 분석 Activity
   :DST-out a dcat:Dataset ;
     prov:wasGeneratedBy :ACT-x ;
     prov:wasDerivedFrom :DST-road, :DST-etas, :DST-acc ;
     prov:qualifiedDerivation [ a prov:Derivation ;
       prov:entity :DST-acc ; prov:hadActivity :ACT-x ;
       fde:confidence "0.88"^^xsd:decimal ; fde:ruleSetVersion "rs-2.1" ; fde:executedAt "…"^^xsd:dateTime ] .
   :ACT-x a prov:Activity ;
     prov:used :DST-road, :DST-etas, :DST-acc ;
     prov:wasAssociatedWith <https://catalog.molit.go.kr/id/agent/fde-studio> ;
     prov:startedAtTime "…"^^xsd:dateTime ; prov:endedAtTime "…"^^xsd:dateTime .

   # JOINED_ON (SSOT 순위, 키 매핑 포함)
   :DST-road dcat:qualifiedRelation [ a dcat:Relationship ;
     dcterms:relation :DST-acc ; dcat:hadRole fde:role/joinedOn ;
     fde:ssotRank 2 ;
     fde:keyMapping [ fde:linkageKey fde:key/K5 ;
       fde:sourceColumn :COL-road-ROAD_LINK_ID ; fde:targetColumn :COL-acc-ACDNT_ADDR ;
       fde:transformRule :RULE-geocode-snap ] ] .

   # GROUPED_WITH
   :DST-acc dcat:qualifiedRelation [ a dcat:Relationship ;
     dcterms:relation :DST-openmarket ; dcat:hadRole fde:role/groupedWith ] .

   # 책임 주체
   :DST-wx prov:wasAttributedTo :ORG-1360000 .
   ```
   - 관계 지정, 순위 변경, 연관 확정/해제, 노드 주석 수정, 변경 요청 승인, 사유 기록은 각각 `prov:Activity`로 기록하고 실제 `ACT-` ID를 발급한다(난수 토스트 금지).
5. 확정 처리
   - `STEP 5 확정`은 트랜잭션으로 (a) 초안 ID를 실제 ID로 민팅(DST, DIST, TBL, COL, ACT), (b) 리니지 트리플 생성과 그래프 저장, (c) 마트 조인 정의 저장(실제 뷰 생성은 선택 작업), (d) Activity 기록, (e) LPG 투영 갱신을 수행한다.
   - 확정 가능 조건은 목업의 미사용 규칙(L2943~2948)을 채택한다: 모든 수준 검토 완료 + 리니지 Shape Violation 0건. 미충족 시 사유를 표시한다.
6. 리니지 SHACL 검증(pySHACL)
   - `JoinRuleShape`: JOINED_ON 관계는 키 매핑이 1개 이상이어야 하고, 양쪽 컬럼의 K코드가 다르면(K2→K5 등) 변환 규칙이 있어야 한다. 위반 시 Violation(조인 테이블 생성 차단).
   - `ActivityShape`: 조합에 포함된 데이터셋은 `prov:wasAttributedTo`로 책임 Agent가 연결되어야 한다. 타 기관 데이터는 협약 근거 문서 참조를 요구한다.
   - 공간 결합: K3 컬럼이 있는데 `dcterms:conformsTo`(예 `EPSG:5186`)가 없으면 Warning, 공간 결합 검증에서 제외.
   - `prov:qualifiedDerivation`에 `confidence`가 없으면 Warning(L1851의 문구 근거).
   - 결과는 대상 노드, 심각도, Shape, 설명, 해결방안, 수정 위치(단계, 데이터셋, 필드) 딥링크로 반환한다. `FIX_ROUTE.lineage5`에 해당하는 "관계 행으로 이동" 경로를 실제로 제공한다.
7. 리니지 미결 게이트와 면제
   - 검증 실행 전 "조합 2건 이상인데 확정된 관계가 없음"을 서버에서 판정한다. 판정 기준은 GROUPED_WITH만이 아니라 JOINED_ON 확정 여부와 키 매핑 완결성을 포함하도록 고친다.
   - 면제는 프로세스 단위 레코드(사유, 작성자, 시각, Activity ID)로 저장하고, 관계가 추가되거나 조합이 바뀌면 자동 만료한다.
8. 노드 주석과 변경 요청
   - STEP 5 고유 정보(표시 이름, 역할 설명, 파생 설계)는 주석으로 즉시 저장한다.
   - STEP 4 연동 항목은 변경 요청으로 저장하되 승인 전에는 정본을 바꾸지 않는다. 상태(접수 / 승인 / 반려), 승인자, STEP 4 재검토 배지 집계, 승인 시 양쪽 동기화를 구현한다.
9. 무효화 전파
   - 관계, 키 매핑, 순위, 승인된 변경 요청의 변경은 검증 결과를 stale로 만들고 직렬화, 진단 결과를 초기화한다. 메시지는 기존 형식(예 `… — STEP 6 검증 결과 무효화 (재검증 필요 · STEP 7~8 재잠금)`)을 따른다.
10. LPG 투영과 내보내기
    - 정본(Turtle)에서 LPG(노드/엣지 + 속성)를 결정적으로 파생한다. Neo4j 적재는 선택 연계로 두고, 최소한 Cypher 또는 JSON 내보내기를 제공한다.

### 7.2 데이터 모델 (PostgreSQL 엔티티 제안)

| 엔티티 | 주요 컬럼 | 비고 |
|---|---|---|
| `process` | id, name, status, combo_confirmed_at | 조합(프로세스) |
| `process_dataset` | process_id, dataset_id, role(`base`/`source`/`external`/`output`), order | 베이스 지정 포함. 목업은 이름 정규식으로 베이스를 추정함 |
| `system` | id(`SYS-…`), name, kind(source/lake/mart/channel), status(연결/유입 예정) | G1 노드 |
| `agent` | id(`AGT-…`), type(`prov:SoftwareAgent`/`prov:Organization`/`prov:Person`), name, org_iri | |
| `dataset` | id(`DST-…`), title, version, publisher_id, system_id, minted | |
| `distribution` | id(`DIST-…`), dataset_id, file_name, media_type, column_count | G3 노드 |
| `table_def` | id(`TBL-…`), kind(source/mart), name, distribution_id, status(설계/생성 대기/생성됨) | `vw_road_accident` |
| `column_def` | id(`COL-…`), table_id, name, data_type, is_pk, null_rate, distinct_count, pattern, crs, note, derived(bool) | G4 표 |
| `linkage_key` | code(K1~K9), label, description, version | SKOS 통제어휘 |
| `column_key_assignment` | column_id, key_code, source(rule/manual), confidence, status(감지/확정), rule_id | |
| `transform_rule` | id, kind(geocode_snap/time_asof/crs_reproject/…), params(jsonb), status(미등록/초안/승인), approved_by | K2→K5 변환 등 |
| `dataset_relation` | id, process_id, type(JOINED_ON/GROUPED_WITH/…), source_dataset_id, target_dataset_id, ssot_rank, status(draft/confirmed/change_requested), confidence, rule_set_version, executed_at, activity_id | 무방향 유형은 정규화 유니크 제약 |
| `relation_key_mapping` | relation_id, key_code, source_column_id, target_column_id, transform_rule_id, candidate_pairs, match_rate, detail(jsonb) | |
| `join_candidate_job` | id, process_id, status, started_at, finished_at, result(jsonb) | 비동기 탐지 |
| `mart_join_def` | table_id, spec(jsonb: sources, join keys, select columns, derived columns) | 4.7절 구조 |
| `prov_activity` | id(`ACT-…`), type, label, started_at, ended_at, agent_id, process_id, params(jsonb) | |
| `prov_usage` / `prov_generation` | activity_id, entity_type, entity_id, role | USED / WAS_GENERATED_BY |
| `prov_derivation` | derived_entity, source_entity, activity_id, confidence, rule_set_version, executed_at | 엣지 프로퍼티 |
| `lineage_waiver` | process_id, reason, user_id, created_at, activity_id, expired_at | `linWaived` 대체 |
| `node_annotation` | process_id, node_type, node_id, title, role, updated_by | `nodeEdits` 대체 |
| `change_request` | id, process_id, target_node, payload(jsonb), status, requested_by, decided_by, decided_at | `reviewFlags` 대체 |
| `lineage_review` | process_id, level(G1~G4), reviewed_by, reviewed_at | 수준별 검토 완료 기록 |
| `lineage_validation_result` | process_id, node_id, severity, shape, message, remedy, fix_route(jsonb), run_at | |
| `rdf_graph` | process_id, graph_iri, ttl, checksum, version | 정본 스냅숏(rdflib 직렬화) |

### 7.3 API 엔드포인트 (제안)

| 메서드와 경로 | 용도 | 목업 대응 |
|---|---|---|
| `GET /api/vocab/edge-types` | 엣지 유형과 RDF 속성 매핑 | 엣지 15종 칩 |
| `GET /api/vocab/linkage-keys` | K1~K9 | STEP 4 K 카드, 배지 |
| `GET /api/processes/{pid}/lineage/graph?level=G1\|G2\|G3\|G4` | 수준별 노드/엣지/범례 집계 | 그래프 카드 |
| `GET /api/processes/{pid}/lineage/nodes/{nodeId}` | 노드 상세(역할, DCAT 속성, 연계키, 관련 관계, 엣지 프로퍼티) | 우측 패널 |
| `PATCH /api/processes/{pid}/lineage/nodes/{nodeId}/annotation` | STEP 5 고유 정보 저장 | `저장 (STEP 5 고유 — 즉시 반영)` |
| `POST /api/processes/{pid}/change-requests` | STEP 4 연동 항목 변경 요청 | `변경 요청 접수 (재검토 유발)` |
| `GET /api/processes/{pid}/change-requests?status=open` | 재검토 배지 집계 | STEP 4 `⚠ 재검토 N건` |
| `POST /api/change-requests/{id}:approve` / `:reject` | 승인/반려와 동기화 | (목업 없음) |
| `GET /api/processes/{pid}/relations?type=` | 관계 목록(순위 포함) | SSOT 목록, 연관 쌍 |
| `POST /api/processes/{pid}/relations` | 관계 생성(JOINED_ON 초안 또는 GROUPED_WITH) | 후보 클릭, `확정` |
| `PATCH /api/processes/{pid}/relations/{rid}` | 상태, 상대 데이터셋, 설명 수정 | (목업의 "매핑 컬럼을 지정하세요") |
| `DELETE /api/processes/{pid}/relations/{rid}` | 연결 제거, 연관 해제 | `✕` |
| `PUT /api/processes/{pid}/relations/ssot-order` | SSOT 순위 일괄 저장 | `▲` `▼` |
| `PUT /api/processes/{pid}/relations/{rid}/key-mappings` | 키와 컬럼 매핑, 변환 규칙 지정 | (목업 없음) |
| `POST /api/processes/{pid}/join-candidates:detect` | 연계키/조인 후보 탐지 작업 시작 | `결합 후보 계산 대기` |
| `GET /api/processes/{pid}/join-candidates` | 탐지 결과(후보 쌍 수, 매칭율, 컬럼 쌍) | `결합 후보 17,417쌍 · LINK_ID ↔ …` |
| `GET /api/datasets/{id}/tables`, `GET /api/tables/{id}/columns` | 테이블과 컬럼 프로파일 | G3 박스, G4 표 |
| `PATCH /api/columns/{id}/linkage-key` | 컬럼 연계키 확정/수정 | K 배지, `+ 키 추가` |
| `POST /api/transform-rules`, `POST /api/transform-rules/{id}:approve` | 변환 규칙 등록과 승인 | JoinRuleShape 해결방안 |
| `GET/PUT /api/processes/{pid}/mart-tables/{name}` | 마트 조인 정의와 파생 컬럼 설계 | `vw_road_accident` |
| `POST /api/processes/{pid}/mart-tables/{name}:materialize` | 마트 뷰 생성 | "생성은 STEP 5 확정 시 실행" |
| `PUT /api/processes/{pid}/lineage/reviews/{level}` | 수준별 검토 완료 표시 | `다음 (확정)` G1→G4 |
| `POST /api/processes/{pid}/lineage:validate` / `GET …/lineage/validation?level=` | 리니지 SHACL 실행과 결과 | SHACL 가이드 카드, `guideCount` |
| `POST /api/processes/{pid}/lineage:confirm` | STEP 5 확정(민팅, 트리플 생성, Activity) | "STEP 5 확정 시 실제 ID 발급" |
| `GET /api/processes/{pid}/lineage/status` | 진입/완료/미결 여부, 면제 여부 | `stepGate(5)`, STEP 6 게이트 |
| `POST /api/processes/{pid}/lineage/waiver` / `DELETE` | 미결 진행 사유 기록과 해제 | 모달 `그래도 진행 (사유 기록)` |
| `GET /api/processes/{pid}/lineage/export?format=ttl\|jsonld\|cypher\|json` | PROV 트리플과 LPG 내보내기 | "LPG 투영" |
| `GET /api/processes/{pid}/activities` | 활동 로그 | `actLog` |

### 7.4 프론트엔드(React) 요구

- 그래프는 데이터 기반 렌더링(자동 레이아웃, 확대/이동, 노드 유형별 색, 엣지 유형별 선 스타일, 방향 표시). 목업의 고정 좌표는 참고용이다.
- 노드를 클릭하면 실제로 그 노드의 상세를 보여 준다. 패널 제목은 수준이 아니라 노드 유형으로 정한다.
- 수준을 바꾸면 선택 노드를 그 수준의 대응 노드로 바꾸거나 선택을 해제한다.
- 엣지 유형 칩은 필터로 동작하게 한다.
- 관계 편집(상대 데이터셋, 연계키, 컬럼 매핑, 변환 규칙, 순위)을 STEP 5에서도 할 수 있게 하거나, STEP 4의 해당 행으로 가는 딥링크를 제공한다.
- SHACL 가이드의 "수정" 링크는 원인 단계의 해당 데이터셋과 필드로 이동하고 복귀 배너를 띄운다(STEP 6의 `goFix`, L2800~2806과 같은 방식).
- 확정 버튼은 조건 미충족 시 비활성화하고 사유를 표시한다.

### 7.5 수용 기준 예시

1. 조합 3건, JOINED_ON 2건(키 매핑 완료), GROUPED_WITH 1건을 확정하면 내보낸 Turtle에 `prov:used` 3건, `prov:wasGeneratedBy` 1건, `dcat:qualifiedRelation` 3건이 들어 있고 pySHACL 리니지 Shape를 통과한다.
2. K2 컬럼과 K5 컬럼을 변환 규칙 없이 매핑하면 `JoinRuleShape` Violation이 해당 배포본 노드에 표시되고 STEP 5 확정이 거부된다.
3. SSOT 순위를 바꾸면 이전 검증 결과가 stale로 표시되고 활동 로그에 Activity가 1건 추가된다.
4. 조합에서 데이터셋을 제거하면 그 데이터셋을 참조하는 관계가 목록에서 고아로 표시되거나 제거되고, 미결 면제가 만료된다.
5. G4 표의 타입과 결측률은 업로드 파일의 실제 프로파일 값과 일치한다.

---

## 8. 목업에서 확인된 불일치와 결함 요약

| # | 내용 | 근거 |
|---|---|---|
| 1 | STEP 5 완료 판정과 STEP 6 게이트가 GROUPED_WITH 쌍(`relPairs`)만 보고 JOINED_ON(`dsExtra.ssot`)은 보지 않음 | L336, L1659 |
| 2 | `linWaived`를 해제하는 코드가 없고 프로세스 저장 키에도 없어 프로세스 간에 새어 나감 | L920, L2844 |
| 3 | STEP 4, 5의 관계 변경과 노드 편집이 하류 단계를 무효화하지 않음 | L344 호출 지점 |
| 4 | 리니지 정보가 `buildTriples()`에 없어 검증과 산출물에 반영되지 않음 | L187~212 |
| 5 | G2~G4 그래프가 상태와 무관한 정적 그림. G1 중앙 노드 클릭 대상이 표시 데이터셋과 다를 수 있음 | M1431~1560, L1462 |
| 6 | 범례 "노드 18종"과 개수 합(20), 실제 노드 수가 서로 다름 | M1364~1370 |
| 7 | `GROUPED_WITH`가 "엣지 15종" 목록에 없음 | M1344~1358, M1442 |
| 8 | G2의 GROUPED_WITH 점선 위치(사고와 차량 흐름 사이)가 설명(사고심층조사 + 오픈마켓)과 다름 | M1441, L1416 |
| 9 | "14컬럼", "11컬럼" 문구와 컬럼 표(각 8행) 불일치 | M1511, M1519, L1479~1496 |
| 10 | 기본 `gran`이 2라서 "G1→G4 순서" 안내와 달리 G1을 건너뜀. `다음 (확정)`에 검증 조건 없음 | L2942, L2984 |
| 11 | 확정 버튼 활성 규칙(`confirmBtnStyle`, `confirmNote`)이 마크업에 연결되지 않음 | L2943~2948 |
| 12 | "prov:Activity 기록" 토스트가 실제 로그를 남기지 않음(수준 확정, 노드 편집). 수준 확정 ID는 난수 | L46~51, L1453 |
| 13 | 변경 요청이 승인 없이 즉시 반영되고 `reviewFlags`가 누적만 됨. `when`은 UTC | L1449~1450 |
| 14 | G4 노드/행 클릭 시 `neT`/`neR` 미초기화로 편집 버퍼가 다른 노드에 남음 | L1467, L1519 |
| 15 | 패널 제목 접두가 노드 유형이 아니라 `gran`에 따름. 수준 전환 시 `node5` 유지 | L1435 |
| 16 | 패널의 결합 관계 건수가 선택 노드와 무관한 전역 값 | L1676~1677 |
| 17 | `linkPick`, `linkAddK*`, `dropLink` 미바인딩(죽은 코드). K 칩 드래그에 드롭 대상 없음. `dsExtra[숫자]` 잔재. STEP 4 시드 `links` 미사용 | L2511~2549, L2325 |
| 18 | 연관 쌍 중복 방지 없음. 조합 변경 시 관계의 고아 참조 정리 없음 | L2414, 데모 스냅숏 |
| 19 | `FIX_ROUTE.lineage5` 미사용. STEP 5 SHACL 카드 링크는 대상 지정 없이 STEP 3으로만 이동 | L137, L2552 |
| 20 | 홈 "다음 권장"이 STEP 5를 건너뜀 | L597~603 |
| 21 | 과업 지시의 K1..K7과 달리 통제어휘는 K1~K9. 연계키 감지 주석("하드코딩 아님")과 달리 이름 정규식 | L731, L2371~2379 |
