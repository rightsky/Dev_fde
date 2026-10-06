# 07. STEP 7 — 직렬화 · 발행 포맷 변환 + 파생 자가검증 기능 명세

분석 대상: `src/markup.html`, `src/logic.js` (FDE Data Studio 목업)
작성 목적: 목업을 FastAPI + PostgreSQL + rdflib/pySHACL 백엔드, React 프런트엔드의 실제 제품으로 재구현하기 위한 기능 명세

---

## 0. 범위에 대한 중요 주의 (마크업 주석 번호와 제품 단계 번호가 뒤바뀌어 있음)

요청 범위는 "STEP 7 = 마크업 1919–2277행"이었으나, 실제 코드를 확인한 결과 이 범위는 **직렬화 화면이 아니다**.

| 마크업 행 | 마크업 주석 | 게이트 바인딩 | 실제로 표시되는 화면 (화면 제목 원문) |
|---|---|---|---|
| 1670–1917 | `<!-- STEP 6 -->` | `show6` | **STEP 7: 직렬화 · 발행 포맷 변환 + 파생 자가검증** |
| 1919–2277 | `<!-- STEP 7 -->` | `show7` | **STEP 6: 검증: 게이트 0 + SHACL** |

근거: `logic.js` 1407–1409행.

```js
// [v8.1-0] 재편 매핑 — show6 게이트의 템플릿 블록(직렬화)은 STEP 7에, show7 블록(검증)은 STEP 6에 표시
show5: ..., show6: s.plane === 'studio' && s.step === 7,
show7: s.plane === 'studio' && s.step === 6, show8: ...
```

v8.1에서 단계 순서가 재편(검증 6, 직렬화 7)되면서 마크업 블록 위치는 그대로 두고 표시 조건만 교차시켰다. 상태 변수 이름도 같은 이유로 어긋나 있다. `v7State`, `v7Time`, `v7Run`은 이름과 달리 **STEP 6(검증)** 의 상태이고, `convertState`가 **STEP 7(직렬화)** 의 상태다 (`logic.js` 328행 주석 "v7State = 검증 상태 변수 (재편 후 STEP 6)").

본 문서의 구성은 다음과 같다.

- 본문 1–8장: 요청 취지(직렬화 · 포맷 변환, `fmts`, `convertState`, `svResults`, `serTgt`, 다운로드, 종료 저장)에 해당하는 **제품 STEP 7 = 마크업 1670–1917행**.
- 부록 A: 요청에 적힌 행 범위 **마크업 1919–2277행(제품 STEP 6 검증 화면)** 의 전체 명세. 다른 문서(06)와 범위가 겹치거나 비는 일이 없도록 함께 기록했다.
- 부록 B: 직렬화 산출물이 등록되는 **산출물 저장소**(카탈로그 평면, 마크업 2932–2974행, `outG` · `outOpen` · `outDelId`).

---

## 1. 화면 목적

STEP 6 검증(게이트 0 + SHACL)을 통과한 데이터셋에 한해, 단일 정본(canonical)에서 4종의 표현(Turtle, JSON-LD, 자연어 문장화, JSON Schema)을 **결정적으로** 생성하고, 생성 직후 파생 자가검증 4검사를 자동 실행한 뒤, 통과분만 파일로 내려받고 프로세스를 "종료 저장"하는 화면이다.

핵심 설계 원칙 (코드 주석과 화면 문구에서 확인됨):

1. **정본 1개 → 내부 트리플 → 렌더러 4개** (`logic.js` 104–105행). 검증(STEP 6)과 산출(STEP 7)이 같은 `buildTriples` 출력을 쓴다. "검증한 대상 = 내보내는 대상".
2. **4포맷의 유일한 조립 지점은 `mkContentFor`** (279–288행). 이 함수 밖에서 문자열 조립 금지.
3. **검증 미통과 데이터셋은 직렬화 대상에서 제외**되고 파일이 존재하지 않는다 (2714행 주석).
4. **자가검증 실패 시 해당 산출물 폐기** (290행 주석).
5. 화면 원칙 배지 원문: `원칙: sLLM은 RDF를 직접 생성하지 않는다 — JSON 산출 후 결정적 후처리로 Turtle 변환`.

단계 흐름 문구 원문: `흐름: 카탈로그(3) → 검증: 게이트 0 + SHACL (6) → 직렬화 + 파생 자가검증 (7) → 승인 → 발행(8) — 검증 미통과 데이터셋은 직렬화 대상에 포함되지 않습니다.`

---

## 2. 화면 구성 (위에서 아래, 마크업 1670–1917행)

최대 폭 1120px 단일 컬럼. 하단부만 2열 그리드(좌 340px 실행 패널, 우 미리보기).

### 2.1 머리말 (1673–1681행)

| # | 요소 | 표시 문구 (원문) | 표시 조건 / 바인딩 |
|---|---|---|---|
| H1 | 제목 | `STEP 7: 직렬화 · 발행 포맷 변환 + 파생 자가검증` | 고정 |
| H2 | 흐름 안내 | `흐름: 카탈로그(3) → 검증: 게이트 0 + SHACL (6) → 직렬화 + 파생 자가검증 (7) → 승인 → 발행(8) — 검증 미통과 데이터셋은 직렬화 대상에 포함되지 않습니다.` | 고정 |
| H3 | 검증 요약 배너 | `{{ cvBanner }}` = `STEP 6 검증 — 통과 N건 · 미통과 M건` + (미통과 있으면 ` (미통과분은 변환 제외)`) | `cvBannerOn` = `s.v7State === 'done'`. 미통과 있으면 주황, 없으면 녹색 (`cvBannerStyle`, 2851–2853행) |
| H4 | 시뮬레이션 경고 | `⚠ 검수 시뮬레이션 중 — 산출물은 검수용 (파일명 _SIM 접미)` | `simOn` = `!!s.simMode` |
| H5 | 원칙 배지 | `원칙: sLLM은 RDF를 직접 생성하지 않는다 — JSON 산출 후 결정적 후처리로 Turtle 변환` | 고정 |

### 2.2 접이식 패널 「Turtle 정본 × AI — 3방향 활용 경로」 (1682–1705행)

- 헤더 클릭(`tai3Toggle`) 시 접기/펼치기. 캐럿 문구 `펼치기 ▾` / `접기 ▴`. 기본 접힘 (`s.tai3` 미정의).
- 펼친 내용은 전부 정적 설명 3행.
  1. `입력 — AI가 읽을 때` / `Turtle 정본 → 템플릿 문장화 (0.57×) → 임베딩 → 벡터DB①` / `변환은 결정적 템플릿 — sLLM 답변의 근거 트리플 역참조 가능` / 링크 `자산 매트릭스 마트 셀 →` (`goMartCell`)
  2. `출력 — AI가 쓸 때` / `sLLM → 스키마 JSON → 결정적 변환 → Turtle 후보 → SHACL → 관리자 승인` / `4중 방어: 문법을 확률 모델에 맡기지 않는다` / 링크 `STEP 6 sLLM 보정 제안 →` (`goStep6`)
  3. `거버넌스 — AI를 관리할 때` / `학습셋·모델·편향 명세(rai:dataBiases) → Turtle 정본에 등록 → 리니지 질의` / `"이 모델은 무슨 데이터로 학습했나"가 그래프 질의로 답해진다`
- 하단 주석: `ⓘ Turtle은 AI의 먹이도 산출물도 아니다 — AI 입력을 만들어내는 원천 · AI 출력을 판정하는 기준 · AI 자산을 기술하는 장부. 확률적인 것과 결정적인 것의 경계선이 Turtle 정본이다.`

### 2.3 직렬화 대상 바 (1706–1716행)

| 요소 | 문구 / 바인딩 | 설명 |
|---|---|---|
| 레이블 | `직렬화 대상:` | 고정 |
| 현재 대상 칩 | `{{ serTgtTitle }}` | 현재 커서 데이터셋 이름. 조합이 비면 `(작업 데이터셋 없음)` |
| 레이블 | `대상 전환 —` | 고정 |
| 대상 버튼 목록 | `{{ serTgtOpts }}` 각 `so.name` | 조합(`s.combo`)의 모든 데이터셋. 현재 대상은 이름 앞에 `✓ ` 접두, 어두운 배경 |
| 모드 토글 버튼 | `{{ pubModeLabel }}` = `발행 전 (초안 ID)` / `발행 후 (민팅 적용)` | `pubModeToggle` |
| 모드 주석 | `{{ pubModeNote }}` = `초안 ID(결정적 해시) 상태 — 데이터셋별 고유, 발행 시 민팅 ID로 치환` / `민팅 맵 적용 — 실시간교통사고 = SVC-000043 · eTAS = DST-000962 · kma = SVC-000041` | 고정 문자열 2종 |

### 2.4 포맷 카드 4장 (1717–1750행, 4열 그리드)

각 카드는 클릭 시 미리보기 초점(`fmt`)을 바꾸고, 카드 안의 체크박스 레이블은 변환 대상 선택(`fmts`)을 바꾼다. 선택된 카드는 배경 `#F3F6FF` + 2px 파란 테두리, 초점 카드는 그림자가 추가된다 (`fmtCard`, 401행).

| 카드 | 체크박스 레이블 | 제목 | 설명 | 목적지 배지 | 분량 문구 | 증명 배지 |
|---|---|---|---|---|---|---|
| T | `변환 대상 (정본 · 필수)` (항상 체크, disabled) | `Turtle` `(RDF 정본)` | `정본 저장·발행 · SHACL 검증 대상` | `→ 카탈로그 평면 (Fuseki/GraphDB) + LPG 투영 (Neo4j)` | `상대 분량 1.00배` | `파생 증명: 커버리지 100% · 근거 9건 · tpl-v2.3` |
| J | `변환 대상` (`selJ`) | `JSON-LD` `(RDF 직렬화)` | `시스템 간 API — @context 외부 URL 참조` | `→ API 계층` | `상대 분량 2.13배` | `파생 증명: 커버리지 100% · 근거 9건 · tpl-v2.3` |
| N | `변환 대상` (`selN`) | `자연어 문장화` | `sLLM RAG 입력` | `→ 마트 벡터DB①·② (→ sLLM)` | `상대 분량 0.57배 · 마트 적재 위치: 벡터DB①` + 링크 `데이터 패브릭 관리에서 보기 →` (`goMartCell`) | `파생 증명: 커버리지 100% (5/5) · 근거 9건 · tpl-v2.3 — 100% 미만 시 적색·발행 차단` |
| P | `변환 대상` (`selP`) | `순수 JSON + 스키마` | `sLLM 출력 (제약 디코딩)` | `→ sLLM 생성 결과 수신 → 결정적 후처리로 Turtle 변환` | `상대 분량 — · 스키마 레지스트리 v3.2 참조` | `파생 증명: 커버리지 100% · 근거 9건 · tpl-v2.3` |

분량 배수, 커버리지, 근거 건수, `tpl-v2.3`는 전부 정적 문자열이다.

### 2.5 접합부 계약 안내 띠 (1751행)

원문: `🔒 레이크는 목적지가 아님 — 접합부 계약: 식별자 + checksum + 프로파일 통계(결측률·포맷 위반률·코드값 분포·라벨 일관성) — 레이크 측 프로파일러 잡이 통계를 메타 평면으로 밀어 올리며(↑), 데이터 본체는 여전히 이동하지 않음 · 스트림 파생 이벤트의 프로파일(이벤트 건수 분포·미확정 플래그 비율)도 동일 계약으로 유입 (STEP 7에서 점검)`

링크 `STEP 7에서 점검`은 `goStep7`. 단계 재편 전에 쓰인 문구로, 의도한 대상은 접합부 계약 점검표가 있는 검증 화면(현재 STEP 6)인데 핸들러는 `step: 7`(지금 보고 있는 화면)로 이동한다. 재구현 시 STEP 6으로 연결해야 한다.

### 2.6 접이식 패널 「스키마 레지스트리 · AI 소비 번들 export」 (1752–1784행)

- 헤더: `스키마 레지스트리 · AI 소비 번들 export` `— SHACL 컴파일 · 학습데이터 출구`, 토글 `schBunToggle`, 캐럿 `펼치기 ▾` / `접기 ▴`. 기본 접힘.
- 펼친 내용은 2열, 전부 정적.

좌: `스키마 레지스트리` 배지 `SHACL → JSON Schema 결정적 컴파일`
- 설명: `스키마의 폭 = sLLM이 자동화할 수 있는 메타데이터의 폭 — SHACL이 요구하는데 스키마에 없는 필드는 sLLM이 못 채웁니다. sLLM 제약 디코딩 흐름의 「스키마 JSON」 노드가 이 레지스트리를 참조 →`
- 목록 3행 (5장 데이터 참고)
- `매핑 예: sh:minCount 1 → required[] · sh:datatype xsd:string → "type": "string"`
- `✓ 검수: SHACL 필수 속성 목록과 JSON Schema required 목록 1:1 일치`

우: `AI 소비 번들 export` 배지 `4번째 목적지 — 학습데이터 출구`
- 설명: `정렬 보증된 (Turtle ↔ 문장화) 쌍 — sLLM 파인튜닝 자산 · 범정부 AI 플랫폼 데이터 상품`
- 목록 3행 (5장 데이터 참고)
- 적색 박스: `export 게이트 3조건: ① 정합 검증(파생 증명 100% + 게이트 0 + SHACL) 통과 ② 이벤트 데이터셋은 개방 구역 산출(비식별)만 — 통제 산출 export 불가 (N2SF 게이트) ③ 승인·발행 완료분만 · 미리보기의 차량번호는 마스킹(58로****)만 허용`

이 패널에는 실행 버튼이 없다. 번들 export 기능은 목업에 구현되어 있지 않다.

### 2.7 하단 2열: 좌측 실행 패널 (1850–1914행)

| # | 요소 | 문구 / 바인딩 | 조건 |
|---|---|---|---|
| L1 | 선택 요약 | `선택된 표현 {{ selCount }}/4:` `{{ selSummary }}` (예: `Turtle 정본 · JSON-LD · 문장화`) | 항상 |
| L2 | 실행 버튼 | `{{ convertBtnLabel }}` = `변환 실행 (통과 N건 × 4포맷)` / 실행 중 `⟳ 변환 중…` | 항상. 통과 0건이면 회색 + `cursor:not-allowed` (클릭은 가능, 토스트로 거부) |
| L3 | 진행 카드 | `⟳ 변환 실행 중 — {{ selCount }}개 포맷` / 진행 막대(고정 62%) / `Turtle 정본 생성 → 결정적 후처리 → 파생 표현 재생성 · prov:Activity 기록 중` | `convertRunning` (`convertState === 'run'`) |
| L4 | 완료 카드 | 아래 L4-1 ~ L4-9 | `convertDone` (`convertState === 'done'`) |

완료 카드 내부:

| # | 요소 | 문구 / 바인딩 |
|---|---|---|
| L4-1 | 제목 | `✓ 변환 완료 요약 — {{ selCount }}개 포맷` |
| L4-2 | 버튼 | `↺ 결과 지우기` (title: `결과를 지우고 다시 변환`) → `convertReset` |
| L4-3 | 요약 줄 | `Turtle {{ comboCount }}건 (정본)` 항상 / `JSON-LD {{ comboCount }}건` (`selJ`) / `문장화 {{ comboCount }}건` (`selN`) / `JSON 스키마 {{ comboCount }}종` (`selP`) / `소요시간 4초 (작업 조합 기준)` 고정 |
| L4-4 | 검증 범위 안내 | `검증 범위: SHACL은 Turtle 정본 1개에만 적용 — 파생 표현 {{ selCount }}개 중 나머지는 정본 통과 후 자동 재생성되므로 별도 검증이 없습니다.` |
| L4-5 | 소제목 | `결과 파일 저장 · 다운로드` `— 검증·자가검증 통과분만 존재` |
| L4-6 | 산출물 그룹 헤더 (`cvGroups`, 검증 통과 데이터셋별 1행) | 데이터셋명 `{{ cg.n }}` / 고정 배지 `STEP 6 검증 ✓` / 자가검증 배지 `{{ cg.svLabel }}` / 세트 체크섬 `{{ cg.cs }}` = `세트 #xxxxxxxx`. 표시 조건 `cvGroupsOn` = 통과 1건 이상 && `v7State === 'done'` |
| L4-7 | 제외 행 (`cvExcluded`, 검증 미통과 데이터셋별 1행, 점선 테두리) | 데이터셋명 `{{ ce.n }}` / 배지 `검증 미통과 — 제외 (파일 미생성)`. 표시 조건 `cvExcludedOn` |
| L4-8 | 파일 목록 (`cvFiles`) | 포맷 태그 `{{ cf.tag }}` (`TTL` / `JSON-LD` / `문장화` / `스키마`) / 파일명 `{{ cf.short }}` (26자 초과 시 `…` + 뒤 24자, title에 전체 이름) / 크기 `{{ cf.size }}` / 다운로드 링크 `⤓` (`cf.dl`) |
| L4-9 | 전체 다운로드 버튼 | `{{ cvDlAllLabel }}` = `⤓ 전체 다운로드 (N개 파일 — 검증·자가검증 통과분만)` → `cvDlAll` |
| L4-10 | 저장 위치 안내 | `저장 위치: 레이크 통제구역 s3://lake-ctrl/catalog/serialized/ 자동 기록 · 다운로드는 로컬 사본 ·` 링크 `산출물 저장소(데이터 카탈로그)에서 프로세스별 관리 →` (`goCatalog`) |
| L4-11 | 다음 단계 버튼 | `STEP 8 가이드라인 준수 진단 · 발행 승인으로 →` (`goStep8`) |

자가검증 배지(`cg.svLabel`, 2788행) 3상태:

| 상태 | 문구 | 색 |
|---|---|---|
| `svResults`에 해당 데이터셋 결과 없음 | `파생 자가검증 — 변환 시 자동 실행` | 회색 |
| 통과 | `파생 자가검증 ✓ 4/4` | 녹색 |
| 실패 | `파생 자가검증 실패 — 렌더러 결함, 산출물 폐기됨` | 적색 바탕 흰 글씨 |

### 2.8 하단 2열: 우측 「변환 결과 상세」 미리보기 (1786–1849행)

- 헤더: `변환 결과 상세 — {{ fmtTitle }}`. `fmtTitle` = `Turtle (RDF 정본)` / `JSON-LD` / `자연어 문장화` / `순수 JSON + 스키마`.
- `fmt` 값에 따라 4개 본문 중 하나만 표시. **4개 모두 `mkContentFor`의 실제 출력이 아니라 마크업에 박힌 정적 템플릿**이다 (7장 참고).

`fmt = 't'` (1789–1797행):
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
하단 설명: `정본 직렬화 — SHACL 검증 대상이며 트리플스토어(Fuseki/GraphDB)에 저장되고 Neo4j로 LPG 투영됩니다.` / `검증: DatasetShape · DistributionShape 적용 · 인코딩: UTF-8 · prefix 12종`

`fmt = 'j'` (1800–1808행):
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
하단 설명: `시스템 간 API 응답용 — @context는 외부 URL 참조로 본문 경량화.` / `목적지: API 계층 (REST/GraphQL) · 분량: Turtle 대비 2.13배`

`fmt = 'n'` (1810–1835행): 파생 증명(Derivation Proof) 데모.
- 제목: `파생 증명 (Derivation Proof) — 시나리오 데모: 과속 이벤트 EVT-0821` `문장 ↔ 근거 리소스 클릭 역참조 (양방향)`
- 배지: `커버리지 100% (5/5) · 근거 리소스 9건 · 렌더러 tpl-v2.3`
- 좌열 제목: `문장 (txt는 이 배열의 뷰 — 정본은 {문장, 근거 리소스 ID[]})`, 문장 5개 (`dpSents`)
- 우열 제목: `근거 리소스 (트리플 + prov:Activity + 참조 데이터셋)`, 리소스 9개 (`dpRess`)
- 하단 설명: 배지 `가이드라인 부록4 데이터 카드 규격 준수 — 자동 생성` + `섹션: 요약·리니지(3원천 조인)·비식별 조치(마스킹 규칙 v1.2)·편향성(rai:dataBiases — 인식 모델 야간 성능 저하)·라이선스 — 모든 서술이 근거 리소스를 가짐 · 데이터·문서 동시 현행화는 파생 구조상 항상 충족 (4종 표현이 단일 정본에서 렌더링).` / `적재 위치: 마트 벡터DB①·②` 링크 `자산 뷰에서 보기 →` (`goMartCell`) `· 분량: 0.57배 · 커버리지 100% 미만이면 배지 적색 + 발행 차단`

`fmt = 'p'` (1837–1847행):
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
하단 설명: `sLLM 출력 수신용 — 스키마 제약 디코딩으로 형식을 강제하고, 결정적 후처리로 Turtle 변환.` / `원칙: sLLM은 RDF를 직접 생성하지 않음 · 후처리 규칙 rs-2.1 적용`

---

## 3. 사용자 동작 → 결과

토스트는 공통적으로 `{ toast: true, toastText }`를 세팅하고 타이머로 닫는다. 로그는 `logAct(who, txt)` (53–61행)로 `actLog`에 `{ t: 'HH:MM', who, txt, actId: 'ACT-K-####' }`를 추가하며 최근 10건만 유지한다. Activity ID는 세션 시퀀스 `actSeq`(초기 420)에서 +1씩 발급된다.

### 3.0 단계 진입 게이트 (`stepGate`, 324–342행)

| 단계 | `done` 조건 | `canEnter` 조건 | 잠김 사유 문구 |
|---|---|---|---|
| 7 | `convertState === 'done'` | `v7State === 'done' && !v6Stale && (v6Results 중 pass ≥ 1건)` | 재검증 필요 시 `재검증 필요 — 정본이 변경되었습니다. STEP 6 검증을 다시 실행하세요`, 그 외 `STEP 6 검증을 먼저 실행하세요 (통과 1건 이상 필요)` |
| 8 | `v8State === 'done'` | `convertState === 'done'` | `STEP 7 변환을 먼저 실행하세요` |

- 모든 단계 이동은 `go()` (4–28행)의 중앙 게이트를 거친다. 잠긴 단계로 가려 하면 이동하지 않고 토스트 `🔒 STEP {n} 잠김 — {reason}` (3초).
- 저장 스냅숏 복원 시에도 잠긴 단계면 마지막 통과 단계로 되돌린다 (81–84행).
- 주의: STEP 8 진입 조건은 `convertState === 'done'`뿐이다. **자가검증이 전부 실패해도 `convertState`는 `'done'`이 되므로 STEP 8이 열린다.** 실제 제품에서는 "자가검증 통과 산출물 1건 이상"을 조건에 넣어야 한다.

### 3.1 「Turtle 정본 × AI」 / 「스키마 레지스트리」 패널 접기

- `tai3Toggle`: `go({ tai3: !s.tai3 })`. `schBunToggle`: `go({ schBun: !s.schBun })` (2650–2653행). 계산 없음.

### 3.2 직렬화 대상 전환 (`so.pick`, 2734–2738행)

- 동작: `go({ serTgt: i, ds: i, ds3: i })`. STEP 3의 커서(`ds3`)와 STEP 4의 커서(`ds`)를 함께 옮긴다.
- 현재 커서 계산: `curIdx = s.serTgt ?? s.ds ?? 0`, `curItem = s.combo[curIdx] || s.combo[0] || {}` (2691–2692행).
- 결과: `serTgtTitle`, 우측 미리보기의 `ds3Id` / `ds3Title` / `ds3DistId` / `ds3Media`, 그리고 STEP 6 화면의 게이트 0 ⑤(정체성 일치) 검사 대상이 바뀐다.
- **변환 범위에는 영향이 없다.** [변환 실행]은 항상 검증 통과 데이터셋 전체를 대상으로 한다. 검증 미통과 데이터셋도 대상 버튼에 나타난다.
- 토스트, 로그 없음.

### 3.3 발행 전/후 모드 토글 (`pubModeToggle`, 2755–2760행)

- 동작: `setState({ pubMode: !published })`. 이어서 `v7State === 'done'`이면 `v6Results`를 `combo.map(validateDs)`로 **즉시 재계산**하고 `persistDraft()`.
- 주석: "모드 전환은 정본 불변 — 검증 무효화 없이 게이트 0 ④ 재평가만 수행".
- 파급 효과:
  - `mintId` (150–162행)가 초안 ID(`{KIND}-draft-{hash6(name)}`) 대신 `MINT_MAP`의 민팅 ID를 반환한다. 맵에 없는 데이터셋은 `null` → 정본 ID가 `DST-미민팅-{hash6}`이 되고 `validateDs`에서 `게이트 0 ④ — 민팅 미등록 (fallback 발급 금지)` FAIL.
  - 그 결과 통과 데이터셋 집합이 실시간으로 줄어들 수 있고, 파일 목록 · 제외 행 · 버튼 레이블의 통과 건수가 즉시 바뀐다.
  - ID가 바뀌므로 세트 체크섬도 바뀐다 (`cg.cs`는 매 렌더마다 `checksumOf`로 재계산).
  - **`convertState`와 `svResults`는 초기화하지 않는다.** 따라서 모드 전환 후 보이는 "자가검증 ✓" 배지는 이전 모드의 결과다. 다운로드 내용은 다운로드 시점에 다시 생성되므로 새 모드의 ID로 나온다.
- 토스트, 로그 없음.

### 3.4 포맷 카드 클릭 (미리보기 초점) (`setFmtT/J/N/P`, 2641행)

- 동작: `go({ fmt: 't' | 'j' | 'n' | 'p' })`. 기본값 `'t'`.
- 결과: `fmtTitle`과 우측 미리보기 본문 전환, 해당 카드에 그림자.

### 3.5 포맷 선택 체크박스 (`togJ`, `togN`, `togP`, 2644–2646행)

- 동작: `e.stopPropagation()` 후 `go({ fmts: { ...sel, j: !sel.j } })` 등. 기본값 `{ t: true, j: true, n: true, p: false }` (399행).
- Turtle은 필수여서 체크박스가 `disabled`이고 토글 핸들러가 없다.
- 결과: `selCount` (선택 개수), `selSummary` (`Turtle 정본`, `JSON-LD`, `문장화`, `JSON+스키마`를 ` · `로 연결, 2941행), 완료 요약의 포맷별 줄 표시 여부, 진행 카드 문구, 홈 대시보드의 `변환 완료 N개 포맷` 문구 및 문장화 커버리지 KPI (`covVal`, 616행).
- **중요: `fmts`는 실제 생성 · 다운로드되는 파일에 영향을 주지 않는다.** 파일 목록(`files`, 2721–2725행)은 항상 `fmtDefs` 4종 전부를 만든다. 버튼 레이블도 선택과 무관하게 `× 4포맷`이다. 선택은 표시 전용이다.

### 3.6 [변환 실행] (`convertRun`, 2912–2940행)

1. `convertState === 'run'`이면 무시.
2. 대상 산정: `passed = combo.filter(c => v6Results.find(r => r.n === c.n && r.pass))` (2915행).
3. 대상 0건이면 중단. 토스트 `✕ 변환 대상 없음 — STEP 6 검증 통과 데이터셋이 없습니다. 검증을 먼저 실행하거나 STEP 3에서 결측을 보강하세요` (3.2초).
4. 시작: `setState({ convertState: 'run', convertTimeIso: new Date().toISOString().slice(0, 19), ... })`. 토스트 `⟳ 변환 실행 — 직렬화 · 통과 {N}건 × 4포맷 (prov:Activity 기록)`.
   - `convertTimeIso`는 UTC 시각을 `YYYY-MM-DDTHH:MM:SS` 형태(타임존 표기 없음)로 저장한다. `buildTriples` 210행에서 `prov:endedAtTime`으로 쓰인다.
5. **1.6초 타이머** (`this._cvt`) 후:
   - `sv = passed.map(c => ({ n: c.n, ...this.selfVerify(c) }))` (2925행). 4장 4.6 참고.
   - `okN = sv.filter(x => x.pass).length`.
   - `setState({ convertState: 'done', svResults: sv, convertTime: this.nowHM(), ... })`.
   - 토스트: 전부 통과면 `✓ 변환 완료 — 통과 {N}건 × 4포맷 · 파생 자가검증 4/4 통과 · 프로세스 종료 저장됨`, 아니면 `⚠ 파생 자가검증 실패 {K}건 — 렌더러 결함, 해당 산출물 폐기됨` (3.2초).
   - 로그: who `홍길동 (나)`, txt `직렬화·포맷 변환 실행 — 통과 {N}건 × 4포맷 · 파생 자가검증 {okN}/{sv.length}`.
   - **프로세스 종료 저장** (전부 통과한 경우에만, 2932–2935행): `this._saveProc(true)` 호출 후 로그 `프로세스 종료 저장 — {procName || '현재 프로세스'} (STEP 7 변환 완료)`. 3.10 참고.
   - `persistDraft()` (localStorage `fde-studio-draft`).
6. 변환 과정에서 파일 본문은 생성 · 보관되지 않는다. 자가검증만 실제로 렌더러를 한 번 돌리고 결과(`pass`, `checks`, `checksum`)만 저장한다.

### 3.7 [↺ 결과 지우기] (`convertReset`, 2905–2908행)

- 동작: `setState({ convertState: null, ... })` + `persistDraft()`. 토스트 `↺ 변환 결과를 지웠습니다 — [변환 실행]으로 다시 생성하세요` (2.6초).
- `svResults`, `convertTime`, `convertTimeIso`는 그대로 남는다. `convertState`가 `null`이 되므로 STEP 7의 `done`이 풀리고 STEP 8이 다시 잠긴다 (`v8State`는 건드리지 않음).
- 로그 없음.

### 3.8 개별 파일 다운로드 (`cf.dl`, 2772행)

- 동작: `e.preventDefault()` → `dl(f.name, mkContentFor(f.item, f.fmt), f.mime)` → 토스트 `⤓ {파일명} 다운로드 — 레이크 정본은 유지, 로컬 사본 생성 (prov:Activity 기록 — 데모에서는 미기록)` (2.8초).
- `dl` (2700–2707행): `new Blob([content], { type: mime })` → `URL.createObjectURL` → 임시 `<a download>` 클릭 → 4초 후 `revokeObjectURL`.
- 내용은 **클릭 시점의 상태로 다시 생성**된다. 변환 실행 시점의 스냅숏이 아니다.
- 로그 없음 (토스트 문구가 스스로 "데모에서는 미기록"이라고 밝힘).

### 3.9 [전체 다운로드] (`cvDlAll`, 2774–2780행)

- 동작: 파일 목록 전체를 350ms 간격으로 개별 다운로드 (`setTimeout(..., i * 350)`). **ZIP 묶음이 아니다.**
- 이어서 `this._procSave()`를 인자 없이 호출 (3.10 참고. `done` 인자가 없으므로 "종료" 표시는 기존 값 유지, `step`은 현재 단계).
- 토스트: `⤓ {N}개 파일 다운로드 · 「{procName || '현재 프로세스'}」 완료 — 프로세스 목록에 저장 확정 (prov:Activity 기록 — 데모에서는 미기록)` (3.4초).
- 로그 없음.

### 3.10 프로세스 종료 저장 (`_saveProc` = `_procSave` = `saveCur`, 936–947행)

`saveCur(done)`:

```js
entry = { id: Date.now(), name: curName, savedAt: now(), step: done ? 7 : this.state.step, ver: 2,
          count: combo.length, done: !!done || prevDone, snapshot: snap() }
procList = [...procList.filter(p => p.name !== curName), entry];  procName = curName;
```

- `curName` (935행): 저장 목록에 살아 있는 `procName` → 없으면 조합 이름(`comboName`) → 없으면 `{목록 수 + 1}차 프로세스`.
- `savedAt`: `new Date().toISOString().slice(5, 16).replace('T', ' ')` → `MM-DD HH:MM` (UTC).
- `snapshot`: `workKeys` (920행, 5장에 전체 목록)의 상태값 복사. `fmts`와 `convertState`는 포함되지만 **`v6Results`, `v7State`, `svResults`, `convertTime(Iso)`, `pubMode`, `serTgt`, `metaOver`는 포함되지 않는다.** 저장된 프로세스를 다시 불러오면 검증 결과가 없으므로 STEP 6부터 다시 실행해야 한다.
- 같은 이름의 기존 항목은 교체된다 (이름이 사실상 키).
- 프로세스 목록 표시 (1071행): `{savedAt} 저장 · 데이터셋 {count}건 · ` + (`done` ? `✔ 프로세스 종료 (STEP 7 완료)` : `STEP {step} 진행`).
- 호출 지점: [변환 실행] 완료 + 자가검증 전부 통과 (`done = true`), [전체 다운로드] (`done` 없음), STEP 8 진단 완료 (`done = true`, 1625–1627행), 수동 저장 등.

### 3.11 이동 링크

| 링크 문구 | 핸들러 | 이동 |
|---|---|---|
| `자산 매트릭스 마트 셀 →`, `데이터 패브릭 관리에서 보기 →`, `자산 뷰에서 보기 →` | `goMartCell` | `go({ plane: 'assets', fabTab: 1, cell: 'martC' })` |
| `STEP 6 sLLM 보정 제안 →` | `goStep6` | `go({ plane: 'studio', step: 6 })` |
| `STEP 7에서 점검` | `goStep7` | `go({ plane: 'studio', step: 7 })` (자기 자신. 2.5 참고) |
| `산출물 저장소(데이터 카탈로그)에서 프로세스별 관리 →` | `goCatalog` | `go({ plane: 'catalog', catDetail: false })` |
| `STEP 8 가이드라인 준수 진단 · 발행 승인으로 →` | `goStep8` | `go({ plane: 'studio', step: 8 })` (게이트 적용) |

### 3.12 파생 증명 문장 · 근거 클릭 (`dp.pick`, `dr.pick`, 2674–2685행)

- 문장 클릭: `go({ dpS: s.dpS === i ? null : i, dpR: null })`. 선택 문장과 그 문장의 `refs`에 속한 리소스가 강조된다 (문장 파랑, 리소스 주황).
- 리소스 클릭: `go({ dpR: s.dpR === id ? null : id, dpS: null })`. 선택 리소스와 그것을 참조하는 모든 문장이 강조된다.
- 같은 항목을 다시 누르면 해제. 데이터는 하드코딩 (5장).

### 3.13 상류 변경에 의한 자동 무효화 (`invalidateDownstream`, 344–356행)

| 원인 (`kind`) | 호출 지점 | 초기화되는 상태 | 메시지 (토스트 + `시스템` 로그) |
|---|---|---|---|
| `combo` | 조합 추가(40행), 조합 삭제(650, 2195행) | `v6Results: null, v7State: null, v6Stale: false, convertState: null, svResults: null, v8State: null` | `조합 변경 — STEP 6·7 결과가 초기화되었습니다 (재검증 필요)` |
| `catalog` | STEP 3 승인 입력(2885행) | `v7State === 'done'`일 때만 `v6Stale: true, convertState: null, svResults: null, v8State: null` | `카탈로그 승인 입력 — STEP 6 검증 결과 무효화 (재검증 필요 · STEP 7~8 재잠금)` |
| 그 외 | (현재 호출 없음) | `convertState: null, svResults: null, v8State: null` | 호출 측 메시지 |

- `combo` 종류는 하류 결과가 하나도 없으면 아무것도 하지 않는다 (346행).
- STEP 2 조합 확정(2068행)도 같은 6개 키를 직접 초기화한다.
- 검수 시뮬레이션 변경(`simSet`, 2831–2834행)은 `v7State === 'done'`이면 `v6Stale: true`만 세팅한다. STEP 7 재진입이 막히지만 `convertState`는 남는다.

---

## 4. 산출 포맷

### 4.1 공통 파이프라인 (`mkContentFor`, 280–288행)

```
item(조합 항목 {n, meta?})
  → buildCanonical(item)            // 164–185행: 정본 객체 c
  → buildTriples(c)                 // 187–212행: [s, p, o, type] 배열 T
  → cs = hash32hex(JSON.stringify(c))   // 세트 체크섬 (8자리 16진)
  → renderTtl(T, cs) | renderJsonld(T, cs) | renderTxt(c, cs) | renderSchema(c, cs)
```

**정본 `c` 구조** (164–185행):

| 키 | 값 |
|---|---|
| `id` | `mintId(item, 'DST')`, 없으면 `'DST-미민팅-' + hash6(name)` |
| `type` | 스트림이면 `['dcat:Dataset', 'dcat:DataService']`, 아니면 `['dcat:Dataset']` |
| `title` | 데이터셋 이름 (`item.n`) 또는 `null` |
| `publisher` | `{ id: meta.orgId, label: meta.org }` 또는 `null` (시뮬레이션 `noorg`에서 조합 첫 항목은 `null`) |
| `distribution` | 비스트림이고 `meta.mediaTypeIana`가 있으면 `{ id: mintId(item,'DIST') 또는 'DIST-미민팅-'+hash6, mediaType, label: meta.form }`, 아니면 `null` |
| `activity` | `{ id: mintId(item,'ACT') 또는 'ACT-미민팅-'+hash6 }` |
| `temporalResolution`, `eventTimeColumn` | 스트림일 때만 (`meta.temporalResolution`, `meta.eventTime`) |
| `readiness` | `{ required: 스트림 ['title','publisher'] / 그 외 ['title','publisher','distribution'], missing: 결측 키, level: 결측 0이면 'ai-ready' 아니면 'draft' }` |
| `_meta`, `_minted` | 원 메타 전체, 민팅 여부 |

메타 출처 (`getMeta2`, 143–147행): `item.meta` 또는 `META_TABLE[name]`에 STEP 3 승인 입력(`metaOver[name]`, `approved === true`일 때만)을 덮어쓴다.

**ID 규칙 (`mintId`, 150–162행)**:
- 초안 모드(`pubMode !== true`): `{KIND}-draft-{hash6(name)}`. `KIND`는 `DST` / `DIST` / `ACT`, 단 스트림 본체는 `SVC`. `hash6`은 `(h + charCode × 31) mod 999999`의 6자리 십진 (139행).
- 발행 모드: `MINT_MAP[name]` (본체), `{mint}-DIST`, `{mint}-ACT`. 맵에 없으면 `null` (fallback 발급 금지).

**트리플 목록 (`buildTriples`, 187–212행)**. 결측 필드는 트리플을 만들지 않고, 참조와 정의는 항상 쌍으로 만든다.

| 조건 | 트리플 (주어, 술어, 목적어, 타입) |
|---|---|
| 항상 | `c.id rdf:type {각 type}` (iri) |
| `title` | `c.id dcterms:title title` (ko) |
| `publisher` | `c.id dcterms:publisher pub.id` (iri) / `pub.id rdf:type foaf:Agent` (iri) / `pub.id rdfs:label pub.label` (ko) |
| `distribution` | `c.id dcat:distribution dist.id` (iri) / `dist.id rdf:type dcat:Distribution` (iri) / `dist.id dcat:mediaType https://www.iana.org/assignments/media-types/{mt}` (iri) / label이 있으면 `c.id dcterms:format label` (ko) |
| `temporalResolution` | `c.id dcat:temporalResolution value` (plain) |
| `eventTimeColumn` | `c.id fde:eventTimeColumn value` (plain) |
| type에 `dcat:DataService` | `c.id dcat:endpointDescription https://api.molit.go.kr/streams/{hash6(title)}` (iri) |
| 항상 | `c.id prov:wasGeneratedBy act.id` (iri) / `act.id rdf:type prov:Activity` (iri) / `act.id prov:wasAssociatedWith https://catalog.molit.go.kr/id/agent/fde-studio` (iri) |
| `state.convertTimeIso` 있음 | `act.id prov:endedAtTime convertTimeIso` (dt) |

**세트 체크섬** (`hash32hex`, 140행): FNV-1a 32비트 (오프셋 `2166136261`, 소수 `16777619`, UTF-16 코드 단위 기준)를 `JSON.stringify(정본)`에 적용한 8자리 16진수.
- 입력이 파일 바이트가 아니라 **정본 객체**다. `_meta`, `_minted`도 포함된다.
- `convertTimeIso`는 정본에 없으므로 체크섬에 반영되지 않는다 (재변환해도 체크섬 불변, 파일 본문의 `prov:endedAtTime`만 달라짐).
- 4포맷 모두에 같은 값이 박힌다. 화면에는 `세트 #xxxxxxxx`로 표시되고, 산출물 저장소에도 같은 값(`#xxxxxxxx`)이 나와 "같은 세트"임을 대조할 수 있다.

**파일명 규칙** (2720–2724행): `base = (name || 'dataset').replace(/[^가-힣a-zA-Z0-9]+/g, '_').slice(0, 40) + (simMode ? '_SIM' : '')`, 파일명 = `base + 확장자`.

### 4.2 포맷 정의표 (`fmtDefs`, 2708–2713행)

| UI 키 (`fmt`/`fmts`) | 엔진 키 | 표시명 (카드 / 미리보기 제목 / 파일 태그) | 확장자 · 파일명 | MIME | 표시 크기(고정) | 렌더러 | 의도된 소비처 |
|---|---|---|---|---|---|---|---|
| `t` | `ttl` | `Turtle (RDF 정본)` / `TTL` | `{base}.ttl` | `text/turtle` | `2 KB` | `renderTtl` | 카탈로그 평면 트리플스토어(Fuseki/GraphDB) 정본 저장, SHACL 검증 대상, Neo4j LPG 투영 |
| `j` | `jsonld` | `JSON-LD (RDF 직렬화)` / `JSON-LD` | `{base}.jsonld` | `application/ld+json` | `4 KB` | `renderJsonld` | 시스템 간 API 계층 (화면 문구상 `POST /catalog/v3/datasets` 카탈로그 API) |
| `n` | `txt` | `자연어 문장화` / `문장화` | `{base}_문장화.txt` | `text/plain` | `1 KB` | `renderTxt` | sLLM RAG 입력, 마트 벡터DB①·② 적재용 코퍼스 |
| `p` | `schema` | `순수 JSON + 스키마` / `스키마` | `{base}_schema.json` | `application/json` | `1 KB` | `renderSchema` | sLLM 제약 디코딩용 스키마, 스키마 레지스트리 |

### 4.3 Turtle (`renderTtl`, 214–242행)

1. 고정 prefix 8줄을 사용 여부와 무관하게 항상 출력한 뒤 빈 줄.
   ```
   @prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
   @prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
   @prefix dcat:    <http://www.w3.org/ns/dcat#> .
   @prefix dcterms: <http://purl.org/dc/terms/> .
   @prefix prov:    <http://www.w3.org/ns/prov#> .
   @prefix foaf:    <http://xmlns.com/foaf/0.1/> .
   @prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
   @prefix fde:     <https://catalog.molit.go.kr/def/> .
   ```
2. 트리플을 주어별로 묶는다 (첫 등장 순서 유지).
3. 주어 줄, 이어서 술어-목적어를 한 줄씩 2칸 들여쓰기. `rdf:type`은 `a`로 표기. 마지막 줄은 ` .`, 나머지는 ` ;`. 주어 블록 사이 빈 줄.
4. 항 표기 규칙 (`term`): 타입 `iri`는 `http(s):`로 시작하면 `<…>`, 등록 prefix(`rdf|rdfs|dcat|dcterms|prov|foaf|xsd|fde`)로 시작하면 접두 이름 그대로, 그 외는 `<값>` (상대 IRI). 타입 `ko`는 `"…"@ko`, `dt`는 `"…"^^xsd:dateTime`, `plain`은 `"…"`.
5. 리터럴 이스케이프는 `"` → `\"` 하나뿐이다. 빈 문자열이나 `null`이 오면 예외 (`빈 리터럴 — 렌더러 결함`, `빈 IRI — 렌더러 결함`).
6. 맨 끝에 주석 줄 `# fde:setChecksum "{cs}"`.

실제 출력 예 (엔진을 추출해 실행한 결과, 초안 모드, `convertTimeIso = 2026-10-06T08:15:30`):

```turtle
<DST-draft-594866>
  a dcat:Dataset ;
  dcterms:title "sample_공간정보_통합포털_데이터셋_목록_도로"@ko ;
  dcterms:publisher <https://catalog.molit.go.kr/id/org/ORG-1613000> ;
  dcat:distribution <DIST-draft-594866> ;
  dcterms:format "정형(엑셀)"@ko ;
  prov:wasGeneratedBy <ACT-draft-594866> .

<https://catalog.molit.go.kr/id/org/ORG-1613000>
  a foaf:Agent ;
  rdfs:label "국토교통부"@ko .

<DIST-draft-594866>
  a dcat:Distribution ;
  dcat:mediaType <https://www.iana.org/assignments/media-types/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet> .

<ACT-draft-594866>
  a prov:Activity ;
  prov:wasAssociatedWith <https://catalog.molit.go.kr/id/agent/fde-studio> ;
  prov:endedAtTime "2026-10-06T08:15:30"^^xsd:dateTime .

# fde:setChecksum "f123dc90"
```

스트림은 주어가 `<SVC-draft-055490>`이고 `a dcat:Dataset ; a dcat:DataService ;` 두 줄, `dcat:temporalResolution "PT1S"`, `fde:eventTimeColumn "event_time"`, `dcat:endpointDescription <https://api.molit.go.kr/streams/055490>`가 추가되며 Distribution 블록이 없다. 발행 모드에서는 `<DST-000961>`, `<DST-000961-DIST>`, `<DST-000961-ACT>`가 된다.

실제 제품 관점의 결함:
- 데이터셋 · 배포 · Activity의 주어가 **상대 IRI** (`<DST-draft-594866>`)다. base IRI 선언이 없어 파서마다 해석이 달라진다.
- 체크섬이 트리플이 아닌 주석이라 재파싱하면 사라진다.
- `\`, 개행 등 `"` 이외 문자는 이스케이프하지 않는다.
- `dcat:temporalResolution`이 `xsd:duration`이 아닌 일반 문자열, `prov:endedAtTime`이 타임존 없는 값이다.
- `dcat:mediaType`의 목적어 IRI에 `dcterms:MediaType` 타입 선언이 없다.

### 4.4 JSON-LD (`renderJsonld`, 244–254행)

- 같은 트리플 배열을 주어별 노드로 묶어 `@graph`로 출력한다.
- `rdf:type` → `@type` (1개면 문자열, 2개 이상이면 배열). 그 외 술어는 접두 이름 그대로 키가 된다.
- 값 표기: `iri` → `{"@id": o}`, `ko` → `{"@value": o, "@language": "ko"}`, `dt` → `{"@value": o, "@type": "xsd:dateTime"}`, `plain` → 문자열. 같은 술어가 반복되면 배열.
- 최상위 구조: `{"@context": "https://catalog.molit.go.kr/context/v3.jsonld", "fde:setChecksum": "{cs}", "@graph": [...]}`, 들여쓰기 2칸.

실제 제품 관점의 결함:
- `@context`가 외부 URL 1개뿐이라, 그 문서가 실제로 호스팅되고 8개 prefix를 정의해야만 RDF로 해석된다.
- 최상위에 `@graph`와 다른 속성(`fde:setChecksum`)이 함께 있으면 JSON-LD 규격상 **이름 있는 그래프**(빈 노드 그래프 이름)로 해석된다. Turtle(기본 그래프)과 구조가 달라지므로 실제 파서로 동형성 검사를 하면 그대로는 일치하지 않는다.
- `@id`가 상대 IRI다.

### 4.5 자연어 문장화 (`renderTxt`, 256–267행)

결측 필드는 문장을 만들지 않는다 (주석: "미상"·"미선언" 금지어).

1. 첫 문장: publisher가 있으면 `「{title}」는 {publisher.label} 소관의 {meta.form || '데이터셋'}이다. `, 없으면 `「{title}」 데이터셋이다. `
2. `meta.role`이 있으면 끝의 마침표와 공백을 정리해 `{role}. `로 덧붙인다.
3. `temporalResolution`이 있으면 `시간 해상도는 {값}` + (`eventTimeColumn`이 있으면 `, event-time 컬럼은 {값}`) + `이다. `
4. 줄바꿈 후 마지막 줄: `readiness.level === 'ai-ready'`이면 `이 서술은 ai-ready 등급 정본에서 생성되었다 (세트 체크섬: {cs}).`, 아니면 `※ 권장 필드 결측 상태의 초안 서술 — 학습 코퍼스 수집 전 보강 권장. (세트 체크섬: {cs})`

출력 예:
```
「cctv.vehicle.det.v1」는 경기도건설본부(데모) 소관의 실시간 스트림(관측)이다. CCTV 차량 관측 — 과속·사고 판정 입력. 시간 해상도는 PT1S, event-time 컬럼은 event_time이다. 
이 서술은 ai-ready 등급 정본에서 생성되었다 (세트 체크섬: 98c2c650).
```

조사 `는`은 받침 여부와 무관하게 고정이다. 문장별 근거 트리플 매핑(파생 증명)은 실제 출력에 포함되지 않는다. 화면의 파생 증명 UI는 별도의 하드코딩 데모다 (7장).

### 4.6 JSON Schema (`renderSchema`, 269–278행)

정본을 순회해 **실제 존재하는 필드만** 속성으로 낸다.

- 항상: `"@id": {type: "string", format: "iri"}`, `"dcterms:title": {type: "string"}`
- publisher 있음: `"dcterms:publisher": {type: "object", properties: {"@id": {string, iri}, "label": {string}}, required: ["@id"]}`
- distribution 있음: `"dcat:distribution": {type: "object", properties: {"@id": {string, iri}, "dcat:mediaType": {string, iri}}, required: ["@id"]}`
- `"dcat:temporalResolution": {type: "string"}`, `"fde:eventTimeColumn": {type: "string"}` (있을 때)
- `required` = `['@id', ...readiness.required를 {title→dcterms:title, publisher→dcterms:publisher, distribution→dcat:distribution}로 바꾼 것 중 properties에 존재하는 키]`
- 최상위: `{"$comment": "generated from canonical {c.id} · readiness: {level} · setChecksum: {cs}", "type": "object", "properties": {...}, "required": [...]}`, 들여쓰기 2칸.

특징: 데이터셋 인스턴스별로 스키마가 달라진다 (필드가 빠지면 스키마에서도 빠짐). `$schema`, `$id`가 없다. 화면 문구의 "SHACL → JSON Schema 결정적 컴파일", "스키마 레지스트리 v3.2 참조"와 달리 **SHACL Shape에서 컴파일하지 않고** 정본 값에서 만든다.

### 4.7 파생 자가검증 4검사 (`selfVerify`, 291–307행)

변환 직후 통과 데이터셋마다 실행한다. 정본 → 트리플 → Turtle 문자열과 JSON-LD 객체를 새로 만든 뒤 4개 검사를 수행한다.

| # | 검사명 (원문) | 실제 판정식 | 평가 |
|---|---|---|---|
| ① | `① TTL 재파싱` | `/@prefix dcat:/.test(ttl) && /\.\s*$/m.test(ttl)` | 문자열에 `@prefix dcat:`이 있고 마침표로 끝나는 줄이 하나라도 있으면 통과. 파서를 쓰지 않으므로 사실상 항상 참 |
| ② | `② prefix 완결` | 정규식 `/(^|\s)([a-z]+):[A-Za-z]/gm`로 접두어 후보를 수집하고(`http`, `https` 제외) 각각에 대해 `ttl.includes('@prefix ' + p + ':')` | 실제 계산. 단 리터럴 내부의 `단어:글자` 패턴(예: 제목에 `note:abc`)도 접두어로 오인해 거짓 실패가 날 수 있음 |
| ③ | `③ UTF-8 정상` | 상수 `true` | 검사 없음 |
| ④ | `④ TTL↔JSON-LD 트리플 일치` | `@graph` 각 노드에서 `@id`를 뺀 모든 키의 값 개수 합 `=== T.length` | 개수 비교만 함. 두 렌더러가 같은 배열 `T`에서 나오므로 구조상 항상 일치 |

반환: `{ pass: 모든 검사 참, checks: [[이름, bool], ...], checksum: cs }`. 렌더러가 예외를 던지면 `{ pass: false, checks: [['렌더러 예외: ' + 메시지, false]], checksum: '' }`.

**실패 시 동작**:
1. `svResults`에 `pass: false`로 기록되고 토스트 `⚠ 파생 자가검증 실패 {K}건 — 렌더러 결함, 해당 산출물 폐기됨`.
2. 해당 데이터셋의 4개 파일이 파일 목록에서 빠진다 (`svFail` 집합, 2717 · 2722행). 다운로드 불가. "폐기"의 실체는 목록에서 제외하는 것이다.
3. 그룹 헤더 배지가 적색 `파생 자가검증 실패 — 렌더러 결함, 산출물 폐기됨`.
4. 하나라도 실패하면 프로세스 종료 저장을 하지 않는다 (2932행 `okN === sv.length`).
5. `convertState`는 그래도 `'done'`이 된다 (3.0의 주의 참고).
6. `checks` 배열은 상태에 저장되지만 화면 어디에도 개별 표시되지 않는다. 통과 시 문구 `✓ 4/4`는 고정 문자열이다.

---

## 5. 데이터 (하드코딩 목록 원문)

### 5.1 포맷 기본 선택

```js
s.fmts 기본값: { t: true, j: true, n: true, p: false }     // 399행
s.fmt  기본값: 't'                                          // 2639행
```

### 5.2 `fmtDefs` (2708–2713행)

```js
['ttl',    '.ttl',          'text/turtle',         'TTL',     '#E8EEFF;color:#1648D6', '2 KB'],
['jsonld', '.jsonld',       'application/ld+json', 'JSON-LD', '#e9e3f5;color:#5a4a8a', '4 KB'],
['txt',    '_문장화.txt',    'text/plain',          '문장화',   '#dff0ec;color:#1e6e50', '1 KB'],
['schema', '_schema.json',  'application/json',    '스키마',   '#fdf3e7;color:#b05c1a', '1 KB']
```

### 5.3 `META_TABLE` (106–116행)

| 키(데이터셋명) | kind | org | orgId | form | mediaTypeIana | role | 스트림 속성 |
|---|---|---|---|---|---|---|---|
| `sample_공간정보_통합포털_데이터셋_목록_도로` | dataset | 국토교통부 | `…/id/org/ORG-1613000` | 정형(엑셀) | xlsx | 도로 공간정보 — 사고 원인 분석 조합 베이스 | |
| `cctv.vehicle.det.v1` | stream | 경기도건설본부(데모) | `…/ORG-6410000` | 실시간 스트림(관측) | | CCTV 차량 관측 — 과속·사고 판정 입력 | `PT1S`, `event_time` |
| `kma.aws.obs.v1` | stream | 기상청(외부 출처) | `…/ORG-1360000` | 실시간 스트림(컨텍스트) | | 기상 관측 — 조건부 기준값 판정 컨텍스트 | `PT10M`, `obs_time` |
| `sample_교통사고심층조사시스템_비정형_` | dataset | 경찰청·도로교통공단(데모) | `…/ORG-1320000` | 정형(엑셀) | xlsx | 교통사고 심층조사 — 사고 원인·사상 정보 | |
| `sample_데이터오픈마켓(30종)` | dataset | 국토교통부 | `…/ORG-1613000` | 정형(엑셀) | xlsx | 오픈마켓 30종 목록 — 사고심층조사 연관 그룹 | |
| `sample_디지털운행기록분석시스템(eTAS)` | dataset | 한국교통안전공단(데모) | `…/ORG-B552016` | 정형(엑셀) | xlsx | 차량 운행기록 — 차량 흐름 분석 입력 | |
| `sample_실시간기상관측자료수집시스템_기상청_` | dataset | 기상청(외부 출처) | `…/ORG-1360000` | 정형(엑셀) | xlsx | 기상 관측 수집 목록 — 협약 확인 필요 | |
| `실시간교통사고` | stream | 국토교통부(데모) | `…/ORG-1613000` | 실시간 스트림(관측) | | 실시간 교통사고 이벤트 — 관제 통보 입력 | `PT5M`, `event_time` |
| `디지털운행기록분석시스템(eTAS)_정보시스템` | dataset | 한국교통안전공단(데모) | `…/ORG-B552016` | 정형(엑셀) | xlsx | 차량 운행기록 분석 — 차량 흐름 분석 입력 | |

`orgId` 접두는 `https://catalog.molit.go.kr/id/org/`, xlsx는 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

### 5.4 `MINT_MAP` (117–123행)

```js
'kma.aws.obs.v1': 'SVC-000041',
'cctv.vehicle.det.v1': 'SVC-000042',
'sample_공간정보_통합포털_데이터셋_목록_도로': 'DST-000961',
'실시간교통사고': 'SVC-000043',
'디지털운행기록분석시스템(eTAS)_정보시스템': 'DST-000962'
```

`META_TABLE`의 나머지 4건은 맵에 없어 발행 모드에서 게이트 0 ④ FAIL이 된다.

### 5.5 `IANA_OPTS` (124–127행)

```js
['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'],
['text/csv', 'csv'], ['application/json', 'json'], ['application/x-hwp', 'hwp'], ['application/pdf', 'pdf']
```

### 5.6 고정 IRI · 네임스페이스

- 실행 주체: `https://catalog.molit.go.kr/id/agent/fde-studio`
- 스트림 엔드포인트: `https://api.molit.go.kr/streams/{hash6(title)}`
- IANA 미디어타입 IRI 접두: `https://www.iana.org/assignments/media-types/`
- JSON-LD context: `https://catalog.molit.go.kr/context/v3.jsonld`
- `fde:` 네임스페이스: `https://catalog.molit.go.kr/def/`
- 저장 위치(문구): `s3://lake-ctrl/catalog/serialized/`

### 5.7 미리보기용 알려진 ID (1942행, STEP 3 커서 기반)

```js
{ 'TRAFFIC_LINK_5MIN': 'DST-000123', 'ADMIN_SGG 행정경계': 'DST-000871', 'etas_inspect_log': 'DST-000541', 'obu.telemetry.v2': 'SVC-000034' }
```
- `ds3Id` = 위 맵 값 또는 `DST-신규 (확정 시 발급)`
- `ds3DistId` = `(knownId || 'DST-신규') + '-' + (업로드 확장자 || 'pq')`
- `ds3Media` = 확장자 xlsx/xls → spreadsheetml.sheet, csv → `text/csv`, 그 외 `application/vnd.apache.parquet`

### 5.8 파생 증명 데모 데이터 (2656–2673행)

문장 (`sents`):

| # | 문장 | refs |
|---|---|---|
| 0 | `이 과속 이벤트는 CCTV 차량 인식 관측에서 판정되었다.` | `T-01`, `OBS-0821-cctv` |
| 1 | `소나기(강수 12mm/h, KMA 지점 401)로 감속 규정(비 20%)이 적용된 상태에서 판정되었다.` | `OBS-KMA-401-0930`, `DST-법정감속규정`, `ACT-CALC-0821` |
| 2 | `적용 규정속도는 64km/h였다 (= 기본 80km/h × 0.8).` | `T-04`, `DST-도로대장`, `ACT-CALC-0821` |
| 3 | `관측 속도 100km/h — 초과 36km/h로 범칙 2구간·심각도 +1이 배정되었다.` | `T-05`, `ACT-CALC-0821` |
| 4 | `차량번호는 개방 산출에서 마스킹(58로****) 처리되었다.` | `ACT-MASK-0821` |

근거 리소스 (`ress`):

| id | desc |
|---|---|
| `T-01` | 트리플 — a :과속이벤트 |
| `T-04` | 트리플 — :적용규정속도 64 |
| `T-05` | 트리플 — :심각도 2 |
| `OBS-0821-cctv` | cctv.vehicle.det.v1 관측 |
| `OBS-KMA-401-0930` | KMA 지점 401 기상 관측 |
| `DST-도로대장` | 참조 데이터셋 v2.4 |
| `DST-법정감속규정` | 참조 데이터셋 v1.0 |
| `ACT-CALC-0821` | 계산 prov:Activity |
| `ACT-MASK-0821` | 마스킹 prov:Activity (규칙 v1.2) |

### 5.9 스키마 레지스트리 목록 (정적, 1764–1766행)

- `schema v3.2` `← DatasetShape v3.2에서 컴파일 · 2026-08-21 · ACT-SCH-0044`
- `schema v3.2-dist` `← DistributionShape v3.2 · ACT-SCH-0045`
- `schema v1.0-stream` `← StreamServiceShape v1.0 · ACT-SCH-0046`

### 5.10 AI 소비 번들 구성 (정적, 1775–1777행)

- `① 학습쌍 JSONL` `{"graph":"<Turtle>","text":"…차량(58로****)…","sources":["T-01","ACT-CALC-0821"]}` `— 파생 증명 통과분만`
- `② RAG 청크 인덱스` `{문장, 임베딩 대상, 근거 리소스 ID[], 데이터셋 URI} — 청크→그래프 점프용`
- `③ LPG 투영 매핑 명세` `Turtle → Neo4j 노드/엣지 변환 규칙 요약`

### 5.11 프로세스 스냅숏 대상 키 `workKeys` (920행)

```js
['combo', 'comboName', 'comboMeta', 'comboSel', 'upList', 'upFile', 'manSel', 'upView', 'ds3', 'ds3Done', 'ds3Fold',
 'mainSel', 'clsSel', 'propSel', 'provSel', 'provRec', 'clsDone', 'propDone', 'provDone', 'dsExtra', 'linkSeq', 'linkKnown',
 'ds', 'dsDone4', 'dist2', 'f1Sel', 'f2Sel', 'f3Sel', 'f4Sel', 'f5Sel', 'relPairs', 'dsGroups', 'fmts', 'convertState',
 'step', 'tab3', 'gran', 'pipe', 'nodeEdits', 'reviewFlags']
```

### 5.12 단계 라벨 (377행)

`['데이터셋 조합 추출 (AI)', '조합 조정·확정', 'DCAT/PROV-O 카탈로그', '다중분류체계 배정', '매핑 + LPG·리니지', '검증: 게이트 0 + SHACL', '직렬화·발행 포맷 변환', '가이드라인 준수 진단']`

---

## 6. 상태 변수

| 키 | 타입 | 기본값 | 의미 | 임시저장(localStorage) | 프로세스 스냅숏 |
|---|---|---|---|---|---|
| `fmts` | `{t,j,n,p: boolean}` | `{t:true,j:true,n:true,p:false}` | 변환 대상으로 "선택된" 표현. 표시 전용 (파일 생성에 영향 없음) | 저장 | 포함 |
| `fmt` | `'t'｜'j'｜'n'｜'p'` | `'t'` | 미리보기 초점 포맷 | 저장 | 미포함 |
| `convertState` | `null｜'run'｜'done'` | `null` | 변환 실행 상태. STEP 7 `done` 및 STEP 8 `canEnter` 판정 근거 | 저장 | 포함 |
| `convertTime` | `string` `HH:MM` (로컬) | 없음 | 변환 완료 시각. **세팅만 되고 어디에서도 읽지 않음** | 저장 | 미포함 |
| `convertTimeIso` | `string` `YYYY-MM-DDTHH:MM:SS` (UTC, 타임존 표기 없음) | 없음 | 변환 시작 시각. `prov:endedAtTime` 트리플의 값. 한 번 세팅되면 [결과 지우기] 후에도 남아 이후 모든 렌더 출력(미리보기용 Turtle, 다운로드)에 포함됨 | 저장 | 미포함 |
| `svResults` | `Array<{n, pass, checks: [string, boolean][], checksum}>｜null` | `null` | 데이터셋별 파생 자가검증 결과 | 저장 | 미포함 |
| `serTgt` | `number｜undefined` | `s.ds ?? 0` | 직렬화 대상 커서(조합 인덱스). 미리보기와 정체성 검사 대상 | 저장 | 미포함 |
| `ds`, `ds3` | `number` | `0` | STEP 4 · STEP 3 커서. 대상 전환 시 함께 세팅됨 | 저장 | 포함 |
| `pubMode` | `boolean｜undefined` | `false` | `true`면 민팅 ID 적용(발행 후), 아니면 초안 ID | 저장 | 미포함 |
| `simMode` | `null｜'nomint'｜'noorg'` | `null` | 검수 시뮬레이션. 파일명 `_SIM` 접미, 조합 첫 항목의 민팅/발행기관 결측 재현 | **저장 제외**, 복원 시 `null` | 미포함 |
| `v6Results` | `Array<{n, pass, fails[], warns[]}>｜null` | `null` | STEP 6 데이터셋 단위 판정. 변환 대상 필터 | 저장 | 미포함 |
| `v7State` | `null｜'run'｜'done'` | `null` | **STEP 6 검증** 실행 상태 (이름 주의) | 저장 | 미포함 |
| `v6Stale` | `boolean` | `false` | 정본 변경으로 검증 결과가 낡았음. STEP 7 진입 차단 | 저장 | 미포함 |
| `v8State` | `null｜'run'｜'done'` | `null` | STEP 8 진단 상태. 무효화 시 함께 초기화 | 저장 | 미포함 |
| `metaOver` | `{[name]: {org, orgId, mediaTypeIana, approved}}` | `{}` | STEP 3 승인 입력. 정본에 반영됨 | 저장 | **미포함** |
| `combo` | `Array<{n, k?, w?, src?, meta?}>` | `[]` | 작업 조합(데이터셋 목록) | 저장 | 포함 |
| `tai3`, `schBun` | `boolean` | `false` | 접이식 패널 펼침 | 저장 | 미포함 |
| `dpS`, `dpR` | `number｜null`, `string｜null` | `null` | 파생 증명 데모에서 선택된 문장 인덱스 / 리소스 ID | 저장 | 미포함 |
| `procList` | `Array<{id, name, savedAt, step, ver, count, done, snapshot}>` | `[]` | 저장된 프로세스 목록 | 저장 | |
| `procName` | `string` | 없음 | 현재 프로세스 이름. 결합 호출 시 `A + B` | 저장 | |
| `procTrash` | 같은 구조 배열 | `[]` | 삭제된 프로세스 휴지통 | 저장 | |
| `outG` | `{[그룹명]: boolean}` | `{}` | 산출물 저장소 그룹별 펼침 (부록 B) | 저장 | |
| `outOpen` | `boolean｜undefined` | 열림 (`!== false`) | 산출물 저장소 패널 펼침 | 저장 | |
| `outDelId` | `string｜null` | `null` | 삭제 2단계 확인 중인 그룹명 | 저장 | |
| `actLog`, `actSeq` | 배열(최근 10건), `number`(초기 420) | | 활동 로그와 Activity ID 시퀀스 | 저장 | |
| `toast`, `toastText`, `toastId` | | | 토스트 표시 | 제외 | |

인스턴스 필드(상태 아님): `_cvt` (변환 타이머), `_tt` (토스트 타이머), `_saveProc` / `_procSave` (저장 훅), `_blankWork`.

상태 영속의 위험: `convertState: 'run'`인 1.6초 사이에 임시저장이 일어나고 페이지를 새로 고치면 `'run'`이 복원되어 버튼이 `⟳ 변환 중…`으로 고정된다 (`convertRun`이 `'run'`이면 즉시 반환). 실제 제품에서는 작업 상태를 서버가 가져야 한다.

---

## 7. 시뮬레이션 vs 실제 계산

### 7.1 실제로 계산되는 것

| 항목 | 근거 |
|---|---|
| 정본 구성, 트리플 생성, 4포맷 문자열 렌더링 | 164–288행. 결정적이고 실제 데이터(이름, 메타, 승인 입력)에 반응 |
| 초안 ID, 민팅 ID 치환 | 150–162행 |
| 세트 체크섬 (FNV-1a 32비트) | 140, 283행 |
| 변환 대상 필터 (검증 통과분), 자가검증 실패분 제외 | 2715–2725, 2915행 |
| 자가검증 ② prefix 완결, ④ 개수 일치 | 300–304행 (단 ④는 구조상 항상 참) |
| 브라우저 파일 다운로드 (Blob) | 2700–2707행 |
| 단계 게이트와 상류 변경 무효화 | 324–356행 |
| 프로세스 저장 (localStorage) | 936–945행 |

### 7.2 시뮬레이션 · 정적인 것

| 항목 | 실제 동작 |
|---|---|
| 변환 "실행" | 1.6초 `setTimeout`. 그동안 아무 작업도 하지 않음. 진행 막대는 62% 고정 |
| 파일 생성 · 저장 | 파일을 만들지도 보관하지도 않음. 다운로드 클릭 때마다 현재 상태로 재생성 |
| `s3://lake-ctrl/catalog/serialized/` 자동 기록 | 문구뿐. 저장 없음 |
| `(prov:Activity 기록)` | 변환 실행은 `actLog`에 한 줄 남김. 다운로드는 토스트 스스로 `데모에서는 미기록`이라 표기 |
| 자가검증 ① 재파싱, ③ UTF-8 | 파서 없음. ①은 정규식 2개, ③은 상수 `true` |
| 미리보기 「변환 결과 상세」 4종 | 정적 템플릿. `<ACT-신규>`, `<CHK-발급 대기>`, `prefix 12종`, `required: identifier/title/mediaType` 등은 실제 엔진 출력(prefix 8종, `spdx:checksum` 없음, `@id`/`dcterms:title` 기반 스키마)과 다름. ID도 엔진의 `mintId`가 아닌 별도 맵(5.7) 사용 |
| 파생 증명 (문장 ↔ 근거) | 과속 이벤트 EVT-0821 하드코딩 데모. 실제 `renderTxt` 출력과 무관 |
| `커버리지 100%`, `근거 9건`, `tpl-v2.3`, 상대 분량 `1.00/2.13/0.57배` | 정적 문자열 |
| 파일 크기 `2 KB / 4 KB / 1 KB / 1 KB` | 정적 |
| `소요시간 4초 (작업 조합 기준)` | 정적 |
| 완료 요약의 건수 | `comboCount`(조합 전체 수)를 쓴다. 검증 미통과로 제외된 건이 있어도 줄지 않음 |
| 포맷 선택(`fmts`) | 표시 전용. 항상 4포맷 생성 |
| 전체 다운로드 | 개별 다운로드를 350ms 간격으로 연속 실행. ZIP 아님 |
| 스키마 레지스트리, AI 소비 번들 export | 정적 설명. 실행 기능 없음 |
| 카탈로그 발행 | STEP 7 화면에는 발행 동작이 없음. 카탈로그 평면으로 가는 링크와, 산출물 저장소에 현재 조합이 자동으로 "보이는" 것이 전부 (부록 B). 발행 승인 버튼과 전송 채널 버튼은 STEP 6 화면에 있고 핸들러가 없음 (부록 A) |

### 7.3 목업 내부 불일치 (재구현 시 정리 필요)

1. 파일명 자르기 길이: STEP 7은 40자 (2723행), 산출물 저장소는 32자 (837행). 긴 이름은 두 화면에서 파일명이 다르다. `_SIM` 접미도 저장소에는 없다.
2. 산출물 저장소는 검증 통과 여부와 변환 여부에 관계없이 조합 전체 × 4포맷을 나열하고 다운로드도 된다. STEP 7의 "미통과분은 파일이 존재하지 않는다" 원칙과 어긋난다.
3. 체크섬은 정본 해시이고 파일 본문에는 실행 시각이 들어가므로, 같은 체크섬의 파일 바이트가 실행마다 다르다.
4. 발행 모드 전환이 자가검증 결과를 무효화하지 않는다 (3.3).
5. 단계 번호가 섞인 문구: `STEP 7에서 점검` (자기 자신으로 이동), 저장소의 `STEP 6 변환 실행 시` 등.

---

## 8. 실제 제품에서 필요한 기능 (제안)

이 장은 목업에서 확인된 의도를 실제 구현으로 옮기기 위한 설계 제안이다.

### 8.1 백엔드 기능

**(1) 정본 그래프 구성**
- STEP 3–5에서 확정된 메타데이터를 PostgreSQL에서 읽어 데이터셋별 `rdflib.Graph`를 만든다. 목업의 `buildCanonical` + `buildTriples` 규칙(4.1의 트리플 표)을 그대로 옮기되 다음을 바로잡는다.
  - 모든 주어를 절대 IRI로 발급: 예 `https://catalog.molit.go.kr/id/dataset/{id}`, `/id/distribution/{id}`, `/id/activity/{id}`.
  - 타입 지정 리터럴: `dcat:temporalResolution` → `xsd:duration`, `prov:endedAtTime` → 타임존 포함 `xsd:dateTime`. `prov:startedAtTime`도 기록.
  - 미디어타입 IRI에 `dcterms:MediaType` 선언, 체크섬은 주석이 아닌 트리플(`spdx:checksum` 노드: `spdx:algorithm`, `spdx:checksumValue`)로 기술.
- STEP 6 검증(pySHACL)과 STEP 7 직렬화가 **같은 그래프 빌더 함수**를 호출하도록 강제한다. 직렬화 실행 시 "검증한 그래프의 해시 = 지금 만든 그래프의 해시"를 비교해 다르면 실행을 거부한다 (목업의 `v6Stale`에 해당).

**(2) 직렬화**
- Turtle: `g.serialize(format='turtle')`. 고정 prefix 8종을 `g.bind()`로 등록. 재현 가능한 바이트를 위해 정렬된 출력(예: longturtle 또는 정규화 후 직렬화)을 쓴다.
- JSON-LD: `g.serialize(format='json-ld', context=...)`. context 문서(`/context/v3.jsonld`)를 서버가 직접 호스팅하고 버전 관리한다. 오프라인 재파싱을 위해 로컬 문서 로더를 둔다. 체크섬 같은 메타는 `@graph` 옆 최상위에 두지 않는다 (이름 있는 그래프로 해석되는 문제 방지).
- 문장화: 템플릿 버전(`tpl-vX.Y`)을 가진 결정적 렌더러. 출력의 정본은 `[{sentence, source_triples[], source_activities[]}]` 배열이고 `.txt`는 그 뷰다. 커버리지 = 근거가 있는 문장 수 / 전체 문장 수. 100% 미만이면 발행 차단 (화면 문구의 규칙). 조사 처리(은/는) 포함.
- JSON Schema: 등록된 SHACL Shape(DatasetShape, DistributionShape, StreamServiceShape)에서 컴파일 (`sh:minCount 1 → required`, `sh:datatype → type`, `sh:in → enum`, `sh:pattern → pattern`). `$schema`, `$id`, 버전을 넣고 스키마 레지스트리에 등록. 검수 규칙: SHACL 필수 속성 목록과 `required` 목록 1:1 일치.
- 포맷 선택(`fmts`)을 실제 생성 범위에 반영. Turtle은 필수.

**(3) 파생 자가검증 (실제 구현)**

| 검사 | 구현 |
|---|---|
| ① 재파싱 | 생성한 Turtle 바이트와 JSON-LD 바이트를 각각 새 `Graph().parse()`로 읽는다. 예외 = 실패 |
| ② prefix 완결 | 재파싱 성공으로 대부분 보장. 추가로 직렬화 본문에 `ns1:` 같은 자동 생성 prefix가 없는지, 허용 네임스페이스 목록 밖의 술어가 없는지 확인 |
| ③ UTF-8 | 바이트를 `utf-8` strict로 디코드, BOM 없음, 디코드 후 재인코드 시 바이트 동일, 한글 리터럴 왕복 일치 |
| ④ 동형성 | `rdflib.compare.isomorphic(g_source, g_ttl)` 및 `isomorphic(g_source, g_jsonld)`. 실패 시 `graph_diff`로 차이 트리플을 결과에 저장 |
| ⑤ (추가) 문장화 커버리지 | 모든 문장이 존재하는 트리플을 근거로 가지는지 |
| ⑥ (추가) 스키마 적합 | JSON-LD를 프레이밍한 인스턴스가 생성된 JSON Schema를 통과하는지 (`jsonschema`) |

- 검사별 결과와 상세(오류 메시지, diff)를 저장하고 화면에 개별 표시한다.
- 하나라도 실패하면 해당 데이터셋의 산출물 세트를 `discarded` 상태로 두고 저장소에 올리지 않는다. 실행 전체의 완료 판정과 STEP 8 진입 조건은 "자가검증 통과 세트 1건 이상"으로 한다.

**(4) 체크섬**
- 파일별 SHA-256 (바이트 기준).
- 세트 체크섬 = 정본 그래프를 RDF 정규화(RDFC-1.0/URDNA2015, 또는 `rdflib.compare.to_isomorphic` 후 정렬 N-Triples)한 결과의 SHA-256. 4포맷과 카탈로그 등록 건이 같은 값을 공유해 "같은 세트" 대조에 쓴다.
- 실행 시각처럼 매번 바뀌는 값은 세트 체크섬 입력에서 제외할지 정책으로 정한다 (목업은 제외).

**(5) 산출물 저장**
- 오브젝트 스토리지(S3 호환)에 `catalog/serialized/{process_id}/{run_id}/{dataset_id}/{파일명}`으로 저장. 불변 저장, 실행별 버전 유지.
- 파일명 규칙을 한 곳에서 정의: `{sanitize(name)[:40]}{_SIM?}{확장자}` (4.1). 저장소 화면과 동일 함수 사용.
- 발행(민팅) 후에는 안정 URI로 재직렬화해 새 버전으로 승격 (저장소 안내 문구의 규칙).

**(6) 다운로드**
- 개별 파일: 저장된 바이트를 그대로 스트리밍 (재생성 금지). `Content-Type`에 `charset=utf-8`, `Content-Disposition`은 RFC 5987(`filename*=UTF-8''…`)로 한글 파일명 처리.
- 묶음: 실행 단위 ZIP (`zipfile` 스트리밍). 내부에 `manifest.json` (파일명, 포맷, 크기, SHA-256, 세트 체크섬, 데이터셋 IRI, 실행 ID, 템플릿 · Shape 버전) 포함.
- 모든 다운로드를 `prov:Activity`로 기록 (목업은 미기록).

**(7) 카탈로그 발행**
- 통과 세트의 Turtle 정본을 트리플스토어(Fuseki/GraphDB)에 SPARQL Graph Store Protocol로 적재. 데이터셋별 이름 있는 그래프.
- 통제구역(정본)과 개방구역(필터링 투영본) 구분, N2SF 등급 게이트, 승인자 기록.
- 초안 ID 잔존 검사(`-draft-`, `-신규`, `-미민팅-` 패턴이 발행 산출물에 0건).
- 후속 채널(JSON-LD 카탈로그 API, MCP 갱신 알림, 공공데이터포털 push)은 발행 승인 후 활성화.

**(8) 실행 관리**
- 직렬화는 비동기 작업(작업 큐). 상태 `queued → running → succeeded | partially_failed | failed`. 진행률은 데이터셋 × 포맷 단위.
- 멱등성: 같은 `(process_id, 정본 그래프 해시, 선택 포맷, 모드)`의 재실행은 기존 결과 재사용 가능.
- 상류 변경 무효화: 조합 변경, 카탈로그 승인 입력, 민팅 모드 전환 시 해당 프로세스의 직렬화 실행을 `stale`로 표시하고 STEP 7–8 재잠금 (3.13의 규칙. 목업이 놓친 모드 전환도 포함).
- 직렬화 실행 자체를 `prov:Activity`(`startedAtTime`, `endedAtTime`, `wasAssociatedWith` 사용자와 소프트웨어 에이전트, `used` 정본 그래프, `generated` 산출물)로 기록.
- 전부 통과 시 프로세스를 "종료" 상태로 저장 (목업의 종료 저장). 스냅숏에는 검증 · 자가검증 결과와 승인 입력도 포함한다.

### 8.2 API 엔드포인트 (FastAPI)

| 메서드 · 경로 | 기능 | 비고 |
|---|---|---|
| `GET /api/processes/{pid}/serialization` | STEP 7 화면 초기 데이터: 검증 요약(통과/미통과), 대상 데이터셋, 포맷 정의, 최근 실행, 게이트 상태 | `cvBanner`, `cvGroups`, `cvExcluded` 대응 |
| `GET /api/processes/{pid}/gates` | 단계별 `{done, can_enter, reason}` | `stepGate` 대응 |
| `GET /api/processes/{pid}/datasets/{did}/preview?format=ttl｜jsonld｜txt｜schema&mode=draft｜published` | 저장 없이 실제 렌더 결과 미리보기 | 정적 미리보기 대체 |
| `POST /api/processes/{pid}/serialization-runs` | 변환 실행. body `{formats: ['ttl','jsonld','txt','schema'], mode, simulate?}` → `202 {run_id}` | 통과 0건이면 `409` + 목업의 오류 문구 |
| `GET /api/serialization-runs/{rid}` | 상태, 진행률, 데이터셋별 자가검증 결과(검사별), 체크섬, 파일 목록 | 폴링 또는 SSE |
| `GET /api/serialization-runs/{rid}/events` | 진행 이벤트 스트림 (SSE) | 선택 |
| `DELETE /api/serialization-runs/{rid}` | 결과 지우기 (논리 삭제, STEP 8 재잠금) | `convertReset` 대응 |
| `GET /api/artifacts/{aid}` | 산출물 메타 | |
| `GET /api/artifacts/{aid}/content` | 개별 파일 다운로드 | 다운로드 기록 |
| `GET /api/serialization-runs/{rid}/archive.zip` | 실행 단위 ZIP + manifest | `cvDlAll` 대체 |
| `GET /api/processes/{pid}/datasets/{did}/derivation-proof` | 문장 ↔ 근거 리소스 매핑, 커버리지 | 파생 증명 UI |
| `POST /api/processes/{pid}/finalize` | 프로세스 종료 저장 | `_saveProc(true)` 대응 |
| `PATCH /api/processes/{pid}` | `{mint_mode}` 등 설정 변경 → 무효화 전파 | `pubModeToggle` 대응 |
| `GET /api/catalog/outputs?group_by=process` | 산출물 저장소 목록 (프로세스별 그룹) | 부록 B |
| `DELETE /api/catalog/outputs/{pid}` | 그룹 삭제 (휴지통 이동) | 2단계 확인은 프런트 |
| `POST /api/processes/{pid}/publish` | 통과 세트 카탈로그 발행. body `{zone: 'control'｜'open', dataset_ids?}` | 승인 권한, 게이트 검사 |
| `GET /api/schemas`, `GET /api/schemas/{version}` | 스키마 레지스트리 | |
| `POST /api/exports/ai-bundle` | AI 소비 번들(JSONL 학습쌍, RAG 청크 인덱스, LPG 매핑 명세) | export 게이트 3조건 적용 |
| `GET /api/activities?process_id=` | prov:Activity 로그 | `actLog` 대체 |

### 8.3 데이터 모델 (PostgreSQL)

| 엔티티 | 주요 컬럼 | 설명 |
|---|---|---|
| `process` | `id`, `name`, `status`(in_progress/finished/trashed), `current_step`, `mint_mode`(draft/published), `finished_at`, `owner_id` | 목업의 `procList` 항목 |
| `process_dataset` | `process_id`, `dataset_id`, `position` | 조합 (`combo`) |
| `dataset_canonical` | `id`, `dataset_id`, `version`, `kind`(dataset/stream), `title`, `publisher_iri`, `publisher_label`, `media_type_iana`, `form_label`, `temporal_resolution`, `event_time_column`, `readiness_level`, `graph_hash`, `approved_by`, `approved_at` | 정본. `metaOver` 승인 입력 포함 |
| `minted_id` | `dataset_id`, `kind`(DST/SVC/DIST/ACT), `draft_id`, `minted_id`, `minted_at` | `MINT_MAP` 대체. fallback 발급 금지 |
| `validation_run` / `validation_result` | `run_id`, `process_id`, `graph_hash`, `status`, `stale` / `dataset_id`, `pass`, `fails jsonb`, `warns jsonb` | STEP 6 결과 (`v6Results`) |
| `serialization_run` | `id`, `process_id`, `validation_run_id`, `formats text[]`, `mint_mode`, `simulation`, `status`, `stale`, `started_at`, `ended_at`, `requested_by`, `activity_id`, `template_version`, `shape_set_version` | `convertState`, `convertTimeIso` 대체 |
| `artifact_set` | `id`, `run_id`, `dataset_id`, `canonical_graph_hash`, `set_checksum`, `status`(valid/discarded), `triple_count` | 데이터셋별 4포맷 묶음. `세트 #` |
| `artifact` | `id`, `set_id`, `format`(ttl/jsonld/txt/schema), `file_name`, `mime_type`, `size_bytes`, `sha256`, `storage_uri`, `version`, `created_at` | 개별 파일 |
| `self_verification` | `id`, `set_id`, `check_code`(reparse/prefix/utf8/isomorphic/coverage/schema), `pass`, `detail jsonb` | `svResults[].checks` |
| `derivation_sentence` | `id`, `set_id`, `seq`, `text`, `source_refs jsonb` | 문장화의 정본 |
| `schema_registry` | `id`, `name`, `version`, `source_shape`, `source_shape_version`, `json_schema jsonb`, `activity_id`, `compiled_at` | 스키마 레지스트리 |
| `publish_record` | `id`, `set_id`, `zone`, `target`(triplestore/api/mcp/portal), `named_graph_iri`, `status`, `approved_by`, `published_at`, `activity_id` | 카탈로그 발행 |
| `download_log` | `id`, `artifact_id` 또는 `run_id`, `user_id`, `kind`(file/zip), `at`, `activity_id` | 다운로드 기록 |
| `prov_activity` | `id`(ACT-…), `type`, `agent_id`, `on_behalf_of`, `started_at`, `ended_at`, `used jsonb`, `generated jsonb`, `message` | 모든 실행 계측 |

### 8.4 프런트엔드(React) 유의 사항

- 미리보기는 `preview` API의 실제 렌더 결과를 구문 강조해 보여준다. 대상 전환(`serTgt`)과 모드 전환에 즉시 반응.
- 변환 버튼 비활성 조건과 사유는 서버 게이트 응답을 그대로 사용.
- 완료 요약의 건수는 실제 생성된 세트 수 기준 (조합 전체 수가 아님).
- 자가검증 결과는 검사별로 펼쳐 볼 수 있게 한다 (실패 시 diff 표시).
- 작업 상태는 서버 조회로만 복원 (localStorage에 `run` 상태를 저장하지 않음).
- 목업의 문구 템플릿(3장)은 그대로 재사용 가능하다.

---

## 부록 A. 마크업 1919–2277행 (`show7`) = 제품 STEP 6 「검증: 게이트 0 + SHACL」 화면

표시 조건: `s.plane === 'studio' && s.step === 6`. 진입 조건 `stepGate(6).canEnter` = STEP 2 조합 확정 완료.

### A.1 화면 구성 (위에서 아래)

**(1) 제목 줄 (1922행)**: `STEP 6: 검증: 게이트 0 + SHACL` 배지 `업무 A — 독립 검증 업무` 부제 `"검증기가 곧 계약" — 파일은 아직 존재하지 않음 · 판정 전용`

**(2) 도구 줄 (1923–1937행)**
- 셀렉트 `검수 시뮬레이션` (`simVal`, `simSet`): 옵션 `끔`(`off`) / `MINT 미등록 재현`(`nomint`) / `publisher 결측 재현`(`noorg`)
- `simOn`이면 배지 `⚠ 검수 시뮬레이션 중 — 산출물은 검수용 (_SIM 접미)`
- `v6StaleOn`이면 배지 `↺ 재검증 필요 — 정본이 변경되어 이전 결과가 무효화되었습니다`

**(3) 리니지 미결 모달 (1938–1950행, `linAskOn`)**
- 제목 `⚠ 리니지 미결 상태입니다`
- 본문 `STEP 5 매핑이 "계산 대기"로 방치되어 있습니다 — 이대로 진행하면 prov 그래프가 불완전합니다. 진행하려면 사유를 입력하세요 (actLog 기록 · 은폐 불가).`
- 텍스트 영역 placeholder `그래도 진행하는 사유 — 예: 단일 소스 시범 검증, 리니지는 2차에 보강`
- 버튼 `돌아가기 (STEP 5)` (`linBack`), `그래도 진행 (사유 기록)` (`linGo`, 사유가 비면 회색)

**(4) 프로세스 호출 바 (1951–1957행)**
- 레이블 `검증 대상 프로세스 호출:`
- 버튼 목록 `taskProcOpts` (저장된 프로세스 + 미저장 시 `{현재 이름} (진행 중)`). 선택된 항목은 `✓ ` 접두.
- 안내 `— 클릭으로 복수 선택 가능 · 선택한 프로세스들의 산출물 합집합이 업무(A) 검증 대상이 됩니다 · 다른 프로세스에 영향 없음`

**(5) 실행 바 (1958–1962행)**
- 상태 배지 `v7StateLabel`: `대기 — 검증 미실행` / `⟳ 검증 실행 중…` / `✓ 검증 완료 — {procName || '현재 프로세스'}`
- 안내 `프로세스를 호출한 뒤 [검증 실행]을 눌러야 게이트 0 → SHACL 검증이 시작됩니다 — 실행마다 prov:Activity 기록`
- 버튼 `v7RunLabel`: `▶ 검증 실행 (N건)` / `⟳ 실행 중…` / `↺ 재검증 실행`

**(6) 대기 안내 (1963–1965행, `v7Idle`)**: `검증 대기 중 — {g1ProcName} 조합 {comboCount}건이 대상입니다. [▶ 검증 실행]을 누르면 내부 트리플(buildTriples)에 대해 게이트 0(의미·형상) → SHACL 순으로 판정합니다 — 파일은 아직 존재하지 않으므로 유출이 불가능합니다.`

**이하 (7)–(14)는 `v7Done`일 때만 표시.**

**(7) 흐름 문구 (1967행)**: 본문 2.1의 H2와 동일.

**(8) 데이터셋 단위 판정 결과 (1968–1997행, `v6HasResults`)**
- 제목 `데이터셋 단위 판정 결과` `— 검증 대상 = buildTriples 출력 (산출물과 동일 원료)`, 우측 `통과 {v6PassN}건 · 미통과 {v6FailN}건`
- 행(`v6Rows`): 데이터셋명, 상태 배지 `통과` / `FAIL`
  - 위반 · 경고가 없으면 `✓ 게이트 0(의미·형상) + SHACL 전 항목 통과 — STEP 7 변환 대상`
  - 위반(적색) · 경고(주황) 항목마다 Shape 문구와 버튼 `수정하러 이동 → STEP {n} ({label})` (`vi.go`). 라우팅이 없으면 `라우팅 미선언 — 브리프 위반`
- 하단 `ⓘ 이 화면은 판정 전용입니다 — 모든 수정은 해당 데이터의 원천 단계(STEP 1~5)에서 이뤄지고, 수정 시 이 검증 결과는 자동 무효화됩니다. 등재 셰이프: PublisherShape (sh:nodeKind sh:IRI) · MediaTypePlacementShape (Distribution 전용) · NoEmptyLiteralShape (sh:minLength 1) · NoDanglingRefShape (참조 IRI 타입 선언 필수)`

**(9) 게이트 0 표 (1998–2015행)**
- 제목 `게이트 0 — 의미·형상 검사` 배지 `트리플 기반 · SHACL 이전 1차 관문`, 우측 요약 `gate0Summary`
- 설명 `SHACL은 파싱된 그래프를 전제로 하는 형상 검증 — 구문 실패와 형상 실패는 원인·담당자가 다르므로 분리 계측합니다. 일반 데이터셋과 파생 이벤트 데이터셋(개방 산출) 모두 동일 게이트 통과 — StreamServiceShape 검증 이전에도 구문 게이트 선행.`
- 열 `검사` / `결과` / `상세`

| 검사 | 결과 | 상세 |
|---|---|---|
| `① 파서 통과` `이동` | `STEP 7` (회색) | `직렬화 텍스트의 속성 — STEP 7 파생 자가검증에서 변환 직후 자동 검사` |
| `② prefix 완결` `이동` | `STEP 7` | `직렬화 텍스트의 속성 — STEP 7 파생 자가검증에서 자동 검사` |
| `③ 인코딩 UTF-8` `이동` | `STEP 7` | 위와 같음 |
| `④ ID 잔존 검사 — 패턴 (-신규|-draft-)` | `gate4Label` `통과`/`실패` | `gate4Msg` (아래) |
| `⑤ 정체성 일치 (요청 대상 ↔ 산출물 제목)` | `gate5Label` `통과`/`실패` | `gate5Msg` (아래) |

- 하단 `✓ 검수 흐름: prefix 하나를 빼면 게이트 0 ②에서 잡히고 SHACL까지 가지 않음 — 게이트 0(회색·파랑)과 SHACL(기존 색)은 시각 구분`
- ①②③이 STEP 7로 "이동"했다는 표기가 본문 4.7의 자가검증 ①②③과 대응한다.

**(10) 파이프라인 4단계 탭 (2016–2096행)**
- 탭: `① 자동추출` / `② 담당자 검수 + sLLM 보정` / `③ SHACL 검증` / `④ 발행` (부제 `Turtle 정본 → LPG 투영·문장화 코퍼스`). `setPipe1..4` → `go({ pipe: n })`. 기본 3.
- 탭별 상세 카드 (4칸 그리드, 대부분 정적):
  - ①: `프로파일 대상` `1,894 데이터셋` / `자동추출 필드` `14,208개 (커버리지 71%)` / `푸터 판독` `Parquet 812건 · 수 KB/건` / `기록 Activity` `ACT-K-0301~0388`
  - ②: `검수 큐 처리` `37건 완료 · 12건 대기` / `sLLM 보정 제안` `61건 (초안)` / `담당자 승인 / 반려` `49 승인` · `12 반려` / `담당 검수자` `검수팀 2인 배정`
  - ③: `Shape 세트` `DatasetShape 외 4종 · rs-2.1` / `검증 대상` `Turtle 정본 {comboCount}건 ({g1ProcName})` / `최근 실행` `방금 · 소요 4초` / `결과` `통과 {v7Pass}` · `W {v7Warn}` · `V {violCount}`
  - ④: `정본 저장` `트리플스토어 (Fuseki/GraphDB)` / `LPG 투영` `Neo4j · 노드 18종` / `문장화 코퍼스` `마트 벡터DB①·② 적재` / `개방 투영` `필터링 후 단방향 push ◀`
    - 소제목 `검증 완료 후 전송 — API · MCP 채널`, 배지 `sendStateLabel` (`발행 승인됨 · 전송 가능` / `발행 승인 대기 (Violation N건)`)
    - 채널 카드 3개 (버튼에 핸들러 없음, `viol > 0`이면 회색):
      - `카탈로그 API (JSON-LD)` / `POST /catalog/v3/datasets` / `시스템 간 연계 · @context 외부 참조 · 인증: 기관 API 키` / `연결됨` / 버튼 `전송`
      - `MCP 서버 노출` / `mcp://catalog.molit.go.kr` / `AI 에이전트용 도구: search_datasets · get_lineage · get_turtle` / `연결됨` / 버튼 `갱신 알림`
      - `공공데이터포털 push` / `data.go.kr · 개방구역 투영본 ◀` / `필터링 투영본만 단방향 push · 🔒 샘플 레코드 제외` / `승인 대기` / 버튼 `push`
    - `ⓘ 전송은 발행 승인(Violation 0건) 이후에만 활성화됩니다. 모든 전송은 prov:Activity로 계측되어 채널별 전송 이력이 남습니다.`
- 하단 띠 `프로버넌스 기록기 — 모든 단계가 prov:Activity 생성 · 사후 작성이 아니라 실행 시점 계측`

**(11) 탭 ① 본문 (2097–2113행)**: KPI 3개 `자동추출 완료` `{p1Ok}` (`{g1ProcName} 조합 기준`) / `부분 추출 (프리필 검수 필요)` `{p1Part}` / `추출 실패 (수기 입력)` `{p1Fail}`. 표 열 `대상 리소스` / `추출 항목` / `신뢰도` / `상태` / 링크 `프리필 확인` (`goStep3`).

**(12) 탭 ② 본문 (2114–2131행)**: KPI `담당자 승인` `{p2Ok}` / `반려` `0` / `검토 대기 (초안)` `{p2Wait}`. 표 열 `대상 리소스` / `sLLM 보정 제안` / `상태` / `검수자` / 링크 `승인 / 반려` (핸들러 없음). 경고 `⚠ sLLM 제안은 항상 초안 상태로 생성됩니다 — 담당자 승인 없이 정본에 반영되지 않으며, 승인·반려 모두 prov:Activity로 기록됩니다.`

**(13) 탭 ③ 본문 (2132–2170행)**
- 칩 4개: `① SKOS 통제어휘 (66코드 준수) ✓` / `② DCAT/PROV-O 필수항목 ✓` / `③ 가이드라인 80항목 대조` / `④ 스트림 Shape 3종 (Service · Plan · 파생)`
- KPI `통과` `{v7Pass}` / `Warning` `{v7Warn}` (`검수 후 발행 가능`) / `Violation` `{violCount}`
- 위반 표 열 `대상 리소스` / `위반 Shape` / `심각도` / `위반 메시지` / 링크 `해당 폼으로 이동` (`goStep3`). 비면 `호출된 프로세스의 조합이 비어 있습니다 — 상단에서 프로세스를 호출하세요`
- `접합부 계약 점검 — 메타 평면 ↔ 데이터 평면 대조` 목록 (`v7Joints`)
- 하단 바: 버튼 `위반 수정 후 재검증` (핸들러 없음) / 배지 `sLLM 보정 제안 — 초안 상태 · 관리자 승인 필수` / `Violation이 남은 데이터셋은 발행 보류로 분리됩니다 — 통과분은 ④ 발행 단계에서 즉시 승인 가능`

**(14) 탭 ④ 본문 (2171–2273행)**
- KPI `발행 대상 (SHACL 통과)` `{v7Pass}` / `발행 보류 (W·V 잔존)` `{v7Warn}` (`Warning 검수 후 발행 가능`) / `전송 채널` `3`
- `N2SF 등급-구역 일치 검사` `옵션` (`n2sfOn`일 때): `O — Open {n2sfOCnt}건` `✓ 개방구역 push 가능` / `S — Sensitive {n2sfSCnt}건` `△ 필터링 투영 조건부 — 샘플 레코드·프로파일 통계 제외 확인` / `C — Classified {n2sfCCnt}건` `✕ 통제구역 전용 (cctv — 차량번호 포함) — 개방 선택 시 자동 제외`. 주석 `ⓘ 등급-구역 일치는 SHACL Shape(N2SFZoneShape)로 검증되며, 등급 미지정 데이터셋은 보수적으로 S로 간주됩니다 — 등급 지정은 STEP 4 다중분류체계 →` (`goStep4`)
- 발행 바: 라디오 `통제구역 (정본)` (기본 선택) / `개방구역 (필터링 투영본 ◀ push)` 🔒 (title `개방 불가: 샘플 레코드·프로파일 통계`), 버튼 `통과분 발행 승인 ({v7Pass}건)` (**핸들러 없음**, 라디오도 상태와 연결되지 않음)
- 주석 `발행 게이트는 데이터셋 단위로 판정됩니다 — Violation이 있는 데이터셋({violCount}건)만 개별 보류되고, SHACL 통과분 {v7Pass}건({g1ProcName})은 일괄 발행할 수 있습니다. 보류분은 위반 해소 후 재검증 시 다음 발행 배치에 합류합니다. 🔒 개방 불가 항목: 샘플 레코드 · 프로파일 통계 · 발행된 정본은 데이터 카탈로그에서 확인 →` (`goCatalog`)
- `배치·자동 실행` 배지 `소프트웨어 주체 — 대화형 런타임과 프로버넌스 레벨 분리`, 버튼 `일괄 재검증 실행` (`batchRun`)
  - `batchOn`이면 진행 패널 (전부 정적): `ACT-B-0032 · 일괄 재검증 구동 중` `prov:SoftwareAgent batch-revalidator v1.4 · actedOnBehalfOf 박관리`, 버튼 `일시정지`(핸들러 없음) / `중단`(`batchClose`), 진행 `1,213 / 1,894건 (64%) · 남은 시간 약 3분 40초`, 5단계 `① 대상 적재 완료 · 1,894건` / `② Shape 로드 완료 · v1.2 · 6종 변경` / `③ SHACL 검증 실행 중 · 1,213건` / `④ 결과 집계 대기` / `⑤ Activity 기록 대기`, `실시간 처리 로그` 6줄, `중간 집계 (1,213건 처리)` `통과 1,168` / `Warning 36` / `Violation 9 (v1.2 신설 rai 항목 7)`, `완료 시 처리` `Violation 대상은 검수 큐로 자동 집계 · 담당자 알림 발송 · 결과 리포트는 prov:Activity ACT-B-0032에 첨부`
  - 설명 `가이드라인 개정 등 일괄 재검증은 STEP 1~8 대화형 흐름과 분리된 배치 런타임으로 실행됩니다. 실행 주체는 prov:SoftwareAgent, 승인 관리자는 prov:actedOnBehalfOf로 연결되고 모든 호출이력은 prov:Activity로 기록되어 동일 SHACL 인프라로 검증됩니다(원칙 10 호출이력 요건).`
  - `실행 주체 모델링`: `prov:SoftwareAgent` `batch-revalidator v1.4` / `prov:actedOnBehalfOf` `박관리 (관리자 승인)` / `대상` `{g1ProcName} 산출 {comboCount}건 + 발행 정본 (누적)` / `트리거` `가이드라인 v1.1 → v1.2 개정 (Shape 6종 변경)`
  - `최근 배치 호출이력 (prov:Activity)`: `ACT-B-0031 · 일괄 재검증 {comboCount}건 ({g1ProcName})` `완료 · 통과 {v7Pass}` / `ACT-B-0030 · SKOS 어휘 개정 반영` `완료` / `ACT-B-0029 · 야간 체크섬 대조` `예약 · 매일 03:00`
  - 하단 `대화형 런타임 — 사람 주체 (prov:Person) · STEP 1~8 화면 조작` | `배치 런타임 — 소프트웨어 주체 (prov:SoftwareAgent) · 승인 관리자 actedOnBehalfOf 연결` | `오케스트레이션 MCP는 현 시점 제외 — 니즈 발생 시 이 섹션으로 수용`

### A.2 사용자 동작 → 결과

**검수 시뮬레이션 (`simSet`, 2831–2834행)**: `simMode = 'off'이면 null, 아니면 값`. `v7State === 'done'`이면 `v6Stale: true`. 효과: `nomint`는 발행 모드에서 조합 첫 항목의 민팅을 `null`로 (153행), `noorg`는 조합 첫 항목의 publisher를 `null`로 (168행). 임시저장에서 제외되고 복원 시 항상 `null`.

**프로세스 호출 (`tp.pickA` = `toggle(p, 6)`, 1025–1044행)**
- 토글식 복수 선택 (마지막 1개는 해제 불가). 미저장 현재 작업이 관련되면 먼저 `saveCur()`.
- 1개 선택: 해당 스냅숏을 현재 작업으로 복원, `procName`, `taskProcSel`, `step: 6`, `v7State: null`, `v8State: null`. 토스트 `… — 「{이름}」 프로세스 호출 · 해당 프로세스 산출물 기준으로 진행`.
- 2개 이상: 각 스냅숏의 `combo`를 이름 기준 중복 제거 합집합으로 만들어 `combo`에 세팅, `procName = 'A + B'`. 토스트 `… — A · B (N개 프로세스 결합 호출) · 산출물 합집합 M건 기준 · 재실행 필요`.
- **버그**: 토스트 접두가 `(step === 7 ? '업무 A(검증)' : '업무 B(진단)')`인데 재편 후 검증은 `step = 6`으로 호출되므로 STEP 6에서도 `업무 B(진단)`이 표시된다 (1037, 1042행).

**[검증 실행] (`v7Run`, 1656–1673행)**
1. 실행 중이면 무시.
2. 경고형 게이트: `relPairs`가 비었고 `linWaived`가 아니고 조합이 2건 이상이며 모달이 닫혀 있으면 `linAsk: true`로 모달을 열고 중단.
3. `v7State: 'run'`, 토스트 `⟳ STEP 6 검증 실행 — 게이트 0(의미·형상) + SHACL · buildTriples 출력 기준 데이터셋 단위 판정`.
4. 1.4초 뒤 `rs = combo.map(validateDs)`. `v7State: 'done'`, `v6Stale: false`, `v6Results: rs`, `v7Time: HH:MM`, `fixBack: null`. 토스트 `✓ STEP 6 검증 완료 — 통과 {P}건 · 미통과 {F}건` + (통과가 있으면 ` · STEP 7 직렬화 해제`, 없으면 ` — [수정하러 이동]으로 원인 단계에서 보강하세요`).
5. 로그: `fixBack`이 있었으면 `재검증 — 직전 위반 {shape} 보강 (원인 단계 STEP {n}) · 통과 P/N`, 아니면 `STEP 6 검증 실행 — {procName || '현재 프로세스'} · 통과 P/N`.

**판정 규칙 (`validateDs`, 309–322행)**. pySHACL이 아니라 정본 객체의 필드 존재 검사다.

| 조건 | 종류 | Shape 문구 | 라우팅 |
|---|---|---|---|
| `pubMode === true && !c._minted` | fail | `게이트 0 ④ — 민팅 미등록 (fallback 발급 금지)` | `mint` |
| `!c.title` | fail | `게이트 0 ⑤ — 정체성 (제목 결측)` | `identity` |
| `!c.publisher` | fail | `PublisherShape — sh:nodeKind sh:IRI (publisher 결측)` | `publisher` |
| 비스트림 && `!c.distribution` | fail | `MediaTypePlacementShape — Distribution 결측` | `mediaType` |
| 스트림 && (`temporalResolution` 또는 `eventTimeColumn` 결측) | fail | `스트림 필수 — temporalResolution·eventTime 결측` | `stream3` |
| `!dsDone4[name]` | warn | `분류 미완 Warning — f1·f2 미선택 (카탈로그 탐색 불가)` | `class4` |
| 예외 | fail | `렌더러 예외 — {메시지}` | `publisher` |

`pass = fails.length === 0`. 화면이 등재했다고 밝힌 `NoEmptyLiteralShape`, `NoDanglingRefShape`는 판정 코드에 없다.

**[수정하러 이동] (`goFix`, 2800–2806행)**: `FIX_ROUTE[route]`의 단계로 이동. `go({ plane: 'studio', step, ds3: idx, ds: idx, (step 3이면 tab3: 2), fixBack: { shape, step }, fixField: route })`. 2.4초 뒤 `fixField: null` (강조 해제). 원인 단계 상단의 복귀 배너에서 `fixBackGo`로 STEP 6 복귀.

`FIX_ROUTE` (129–138행):

| route | step | label |
|---|---|---|
| `identity` | 2 | 조합 확정 카드 |
| `mint` | 2 | ID 발급 안내 · 관리 탭 민팅 정책 |
| `publisher` | 3 | publisher 필드 |
| `mediaType` | 3 | mediaType 드롭다운 |
| `emptyLit` | 3 | 해당 필드 |
| `stream3` | 3 | 스트림 속성 카드 |
| `class4` | 4 | 분류 매트릭스 |
| `lineage5` | 5 | 연계 초안 행 |

**리니지 모달**: `linReasonSet`은 입력값 저장. `linBack`은 모달 닫고 STEP 5로. `linGo`는 사유가 비면 무시, 있으면 로그 `리니지 미결 상태로 검증 진행 — 사유: {사유}`, `linWaived: true`, 토스트 `사유 기록됨 (prov:Activity) — [검증 실행]을 다시 누르세요`.

**게이트 0 ④ (2741–2753행)**: `g4 = !published || combo.every(c => !!mintId(c, 'DST'))`.
- 초안 모드 문구: `초안 ID(결정적 해시) 상태 — 데이터셋별 고유(KIND-draft-XXXXXX) · 발행 시 민팅 ID로 치환 · 발행 산출물에는 (-신규|-draft-) 잔존 불가`
- 발행 모드 통과: `민팅 적용 — (-신규|-draft-) 잔존 0건 (실시간교통사고 = SVC-000043 · eTAS = DST-000962 · kma = SVC-000041)`
- 발행 모드 실패: `민팅 미등록 데이터셋 존재 — fallback 발급 금지 · 게이트 0 ④ FAIL (관리 탭 민팅 정책에서 등록 후 재검증)`
- 요약: `게이트 0(의미·형상) 통과 — SHACL 진행 가능` / `게이트 0 ④ 실패 — 민팅 미등록`

**게이트 0 ⑤ (2727–2731, 2764–2767행)**: 직렬화 대상 커서 항목의 Turtle을 실제로 만들어 `/dcterms:title\s+"([^"]+)"/`로 제목을 뽑고 요청 대상 이름과 비교. 통과 `대상 · 산출물 제목 일치 ({이름})`, 실패 `이 산출물은 '{대상}'이 아니라 '{추출 제목}'을 서술하고 있습니다 — 반려`, 공통 꼬리 ` · ①~④는 산출물 내부 결함, ⑤는 요청↔산출물 불일치를 잡습니다`. 현재 대상 1건만 검사한다.

**일괄 재검증 (`batchRun`, 1270행)**: `batchOn` 토글. 켤 때 토스트 `✓ prov:Activity B-0032 (SoftwareAgent · 재검증 배치) 기록됨` (2.6초). 진행 패널은 정적. `batchOn`은 임시저장 제외.

### A.3 하드코딩 데이터

**SHACL 위반 표 `v7Rows` (1554–1559행)**: 조합 항목별 1행, 전부 `Warning`.

| 조건 | 대상 리소스 | 위반 Shape | 메시지 |
|---|---|---|---|
| `kma.aws.obs.v1` | `SVC-신규 (kma)` | `prov:wasAttributedTo 외부 출처` | `AGT-기상청 연결 확인 · 공공데이터 이용허락 표기` |
| `cctv.vehicle.det.v1` | `SVC-신규 (cctv)` | `StreamServiceShape` | `워터마크 PT1M 선언 확인 · 통제 산출 N2SF 게이트` |
| 이름에 `도로` | `DST-신규 (도로)` | `dcterms:conformsTo (좌표계) 미선언` | `GEOM 컬럼 EPSG 명시 필요 — EPSG:5186 권장` |
| 그 외 | `DST-신규` | `dcat:mediaType 확인` | `{이름} — 배포본 mediaType 검수` |

**접합부 계약 `v7Joints` (1562–1571행)**: 스트림(`/cctv|kma/`)은 `{이름} (스트림)` / `— 스트림: 세션 요약(ACT-S)으로 대조 · 파일 대조 제외`. 비스트림 첫 항목은 `{이름}.xlsx` / `✕ 원본 체크섬 미기록 — 적재 시 부여 필요` (데모용 고정 실패). 나머지는 `✓ 푸터 식별자 · spdx:checksum 일치`.

**자동추출 `p1Rows` (1574–1579행)**: cctv `SVC-신규 (cctv)` / `토픽 스키마 (Avro) · 인식 모델 MDL-000004 참조` / `99%` / `완료`. kma `SVC-신규 (kma)` / `관측 스키마 · 지점코드 · late 정책` / `98%` / `완료`. 도로 `DST-신규 (도로)` / `스키마 14컬럼 · PK/FK · GEOM 좌표계 미선언` / `72%` / `부분 추출`. 그 외 `DST-신규` / `{이름} — 스키마 자동추론` / `90%` / `완료`. `p1Fail`은 상수 0.

**sLLM 보정 `p2Rows` (1580–1585행)**: cctv `워터마크 PT1M 선언 제안 (StreamServiceShape)` / `초안 · 승인 대기` / `김검수`. kma `prov:wasAttributedTo → AGT-기상청 연결 제안` / `승인됨` / `이관리`. 도로 `dcterms:conformsTo → EPSG:5186 제안` / `초안 · 승인 대기` / `김검수`. 그 외 `{이름} — keyword 자동 제안 (sLLM)` / `승인됨` / `김검수`.

**집계식**: `v7Pass = max(combo.length - (viol > 0 ? 1 : 0), 0)`, `v7Warn = 행 수`, `violCount = viol = this.props.violationCount ?? 0` (컴포넌트 속성, 기본 0), `n2sfOCnt = cctv 제외 건수`, `n2sfSCnt = 0`, `n2sfCCnt = cctv 건수`.

**배치 로그 6줄 (2225–2230행)**:
```
09:41:22 PASS DST-001213 (통제) · DatasetShape v1.2
09:41:22 PASS DST-001212 (개방 투영) · DistributionShape
09:41:21 WARN SER-0031 · accrualPeriodicity 표기 (신규 Shape)
09:41:20 FAIL DST-000871 · rai:dataBiases 누락 (v1.2 신설 필수)
09:41:19 PASS DST-001209 (통제) · ActivityShape
09:41:19 PASS DST-001208 (통제) · DatasetShape v1.2
```

### A.4 시뮬레이션 vs 실제 (검증 화면)

- 실제 계산: `validateDs`의 필드 존재 판정, 게이트 0 ④⑤, FIX_ROUTE 왕복, 무효화.
- 시뮬레이션: 1.4초 지연, pySHACL 미사용, 파이프라인 탭 ①②의 통계, 탭 ③의 위반 표(이름 패턴 기반 고정 문구이며 `v6Results`와 별개 체계), 접합부 대조, 발행 승인 버튼과 전송 채널 버튼(핸들러 없음), 배치 재검증 패널.
- 같은 화면에 판정 체계가 둘 공존한다. 상단 "데이터셋 단위 판정 결과"(`v6Results`, 실제 계산, STEP 7의 필터)와 탭 ③ "통과/Warning/Violation"(`v7Pass`, `v7Rows`, `violCount`, 데모 수치)이다. 실제 제품에서는 pySHACL 검증 보고서 하나로 통합해야 한다.

---

## 부록 B. 산출물 저장소 (카탈로그 평면, 마크업 2932–2974행, logic 810–916행)

STEP 7의 링크 `산출물 저장소(데이터 카탈로그)에서 프로세스별 관리 →`가 가리키는 곳이다.

### B.1 구성

- 헤더(클릭 시 접기, `outToggle`): `산출물 저장소 — STEP 1~7 결과 파일` 배지 `프로세스 단위 관리 · 4포맷`, 캐럿 `접기 ▴` / `펼치기 ▾`. 기본 펼침 (`outOpen !== false`).
- 비었을 때: `아직 산출물이 없습니다 — STEP 6 변환 실행 시 프로세스 단위로 여기에 등록됩니다`
- 그룹(프로세스)별 카드: `📁 {og.proc}` `· 산출물 {og.count}건 · {og.gate}`, 버튼 `마지막 작업 (STEP {n}) →` (`og.goLast`), 버튼 `🗑 삭제` / 확인 중 `정말 삭제? (한 번 더 클릭)` (`og.del`, title `저장 프로세스는 휴지통으로 이동(복원 가능) · 진행 중 그룹은 현재 산출물 비우기`), 캐럿.
- 펼치면 파일 행: 포맷 태그 / 파일명 / Activity · 체크섬 / 위치 / `⤓`.
- 하단: `ⓘ 산출물은 변환 실행(STEP 6) 시 자동 등록 — 발행(STEP 8 URI 민팅) 후에는 안정 URI로 재직렬화되어 버전이 승격됩니다 · 다운로드는 로컬 사본 (prov:Activity 기록)`

### B.2 그룹과 행의 산출 규칙

- 그룹 목록 `procs` (819–823행): 저장된 프로세스(현재 이름 제외) + 현재 프로세스. 데이터셋이 없는 그룹은 제외.
  - 저장된 프로세스: 이름 그대로, 데이터셋은 `snapshot.combo`, Activity `ACT-SER-{id 끝 4자리}`.
  - 현재 프로세스: 이름 + ` (진행 중)` 또는 `v8State === 'done'`이면 ` (종료)`, Activity는 `ACT-미발급` 또는 종료 시 `ACT-K-{actSeq 4자리}`.
- 상태 문구 `gate` (832행): 저장된 프로세스 `완료 · 저장 확정` (녹색) / 현재 프로세스가 변환 완료 `STEP 6 검증 ✓ · 파생 자가검증 ✓` (주황) / 그 외 `STEP 7 변환 대기` (회색).
- 행: 그룹의 모든 데이터셋 × 태그 4종.

```js
tags = [['TTL', …, '.ttl', 'text/turtle'], ['JSON-LD', …, '.jsonld', 'application/ld+json'],
        ['문장화', …, '_문장화.txt', 'text/plain'], ['스키마', …, '_schema.json', 'application/json']]
base = (ds.n || 'dataset').replace(/[^가-힣a-zA-Z0-9]+/g, '_').slice(0, 32)     // STEP 7은 40자
file = base + ext
act  = p.act + ' · #' + checksumOf(ds).slice(0, 8)
loc  = 's3://lake-ctrl/catalog/serialized/' + base + ext
```

- 다운로드 (`or.dl`, 847–853행): `mkContentFor(ds, 포맷)`을 다시 호출해 Blob 다운로드. 토스트 `⤓ {파일명} 다운로드 — 정본 엔진 산출 · 세트 #{cs} (prov:Activity 기록 — 데모에서는 미기록)`.

### B.3 상태와 동작

| 상태 | 동작 |
|---|---|
| `outOpen` | `outToggle`: `go({ outOpen: s.outOpen === false })` |
| `outG[그룹명]` | `og.toggle`: 해당 그룹 펼침 토글 (기본 접힘) |
| `outDelId` | `og.del` 1차 클릭: `go({ outDelId: 그룹명 })`로 버튼이 적색 확인 상태가 됨. 2차 클릭에 실제 삭제. 자동 해제 타이머 없음 |

삭제 (879–895행):
- 저장된 프로세스 그룹: `procList`에서 제거하고 `procTrash`로 이동. 현재 불러온 프로세스이면 작업 상태도 함께 비움. 토스트 `🗑 「{이름}」 산출물 그룹 삭제 — 휴지통 이동` + (현재 프로세스면 ` · STEP 1~6 작업 상태 동시 삭제됨`) + ` (프로세스 관리에서 복원 가능)`.
- 진행 중(미저장) 그룹: 업로드 목록까지 포함해 작업 상태 전체 초기화. 토스트 `🗑 진행 중 산출물 삭제 — STEP 1 업로드·선택부터 조합·분류·변환 결과까지 동시 삭제되었습니다 (대시보드·카탈로그 집계 반영)`.
- 로그: `산출물 그룹 삭제 — 「{이름}」`.

마지막 작업으로 이동 (`og.goLast`, 897–907행): 저장된 프로세스면 스냅숏 복원 후 저장 시점 단계로, 아니면 현재 단계로 이동. 구버전 스냅숏(`ver` 없음)은 단계 번호 6↔7을 교환한다. 토스트 `↺ 「{이름}」 마지막 작업 위치(STEP {n})로 이동`. 저장 프로세스 복원은 `setState`로 직접 단계를 세팅하므로 `stepGate`를 거치지 않는다.

### B.4 실제 제품과의 차이

- 목업의 "저장소"는 저장된 파일 목록이 아니라 **조합 목록에서 파생된 가상 목록**이다. 변환을 실행하지 않았거나 검증에 실패한 데이터셋도 4포맷 행이 나타나고 내려받을 수 있다.
- 실제 제품에서는 `artifact` 테이블(8.3)의 실존 레코드만 나열하고, 상태(유효/폐기/승격 버전), 파일별 SHA-256, 세트 체크섬, 생성 Activity, 저장 위치를 표시한다. 삭제는 프로세스 휴지통 이동과 산출물 보존 정책을 분리한다.
