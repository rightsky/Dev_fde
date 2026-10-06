# 01. 애플리케이션 셸 + STEP 1 「데이터셋 조합 1차 추출」 기능 명세

- 분석 대상: `src/markup.html` 1~151행(셸), 152~364행(STEP 1), 3839~3910행(AI 어시스턴트·하단 바·토스트·알림) / `src/logic.js`의 해당 바인딩·핸들러 정의부
- 표기 규칙: `M123` = markup.html 행 번호, `L123` = logic.js 행 번호. 큰따옴표 안의 한글 문구는 화면 표기 그대로(verbatim)이다.
- 분석 방법: 정적 코드 판독이며 목업을 실행하지는 않았다. 바인딩 해석 규칙은 템플릿 런타임(`resources/540eedd9-7fd6-4542-85b2-f289dace820e.js`)의 `walkIf`와 `vals = { ...userProps, ...renderVals() }` 병합부를 읽어 확인했다. 컴포넌트 props는 `violationCount`(기본 0) 하나뿐이다(`template.html` 3938행 `data-props`).
- 범위 밖 화면(STEP 2~8, HOME, 데이터 패브릭 관리, 데이터 카탈로그, 시스템 관리)은 STEP 1과 상태를 공유하는 지점만 언급한다.

---

## 1. 화면 목적

### 1.1 애플리케이션 셸
1. 로그인 게이트를 통과한 사용자에게 5개 평면(HOME / ARD 스튜디오 / 데이터 패브릭 관리 / 데이터 카탈로그 / 시스템 관리) 사이의 이동 수단을 제공한다.
2. ARD 스튜디오 평면에서는 좌측 사이드바로 8단계 워크플로의 진행 상태(완료 ✓ / 진행 가능 / 잠김 🔒)를 보여 주고, 단계 이동을 중앙 게이트(`stepGate`)로 통제한다.
3. 현재 단계의 담당 조직과 정·부 작업자, 관리자를 표시한다.
4. 하단 고정 바에서 이전/다음(확정) 이동, 임시저장, 스냅숏 파일 저장·불러오기, 데모 데이터 지우기·복구를 수행한다.
5. 우측 AI 어시스턴트 패널에서 표준(DCAT, PROV-O, SHACL)과 화면 사용법을 질의한다.
6. 단계 확정 시 다음 단계 담당자에게 알림이 발송되었음을 팝업으로 보여 준다.

### 1.2 STEP 1 「데이터셋 조합 1차 추출」
사용자가 달성하는 것은 다음 네 가지이다.
1. 엑셀·CSV·Parquet 파일을 올려 유형 판별과 프로파일 결과를 카드(또는 리스트)로 확인한다.
2. 스트림 관리에서 유입된 실시간 스트림(데모 2건, 합성 캡처 묶음)을 업로드 파일과 같은 후보 풀에서 본다.
3. 후보 중 작업에 쓸 데이터셋을 체크(☑)로 고르고, 연계키(K축) 기반 "AI 제안 데이터셋 조합"을 채택해 내 작업 조합(`combo`)으로 설정한다.
4. 작업 프로세스(STEP 1~7 작업 상태 묶음) 단위로 저장·불러오기·새 프로세스 시작을 한다.

STEP 1의 산출물은 `manSel`(선택된 후보 집합)과 `combo`(조합 초안)이며, 둘 중 하나라도 1건 이상이면 STEP 2가 열린다(L332~L333).

---

## 2. 화면 구성 (위에서 아래 순)

### 2.1 로그인 게이트 (M4~M28, 조건 `loginGate`)
전체 화면을 덮는 고정 오버레이(z-index 999) 가운데 360px 카드.

| 요소 | 표기 | 비고 |
|---|---|---|
| 로고 | "◈" / "FDE Data Studio" / "Forward Deployed Engineering" | 정적 |
| 입력 | 라벨 "ID", placeholder "아이디" | `loginId`, `loginIdSet`, `loginKey` |
| 입력(password) | 라벨 "Password", placeholder "비밀번호" | `loginPw`, `loginPwSet`, `loginKey` |
| 오류 문구 | "ID 또는 비밀번호가 올바르지 않습니다" | `loginErr`가 참일 때만 |
| 버튼 | "로그인" | `loginGo` |

### 2.2 헤더 (M30~M57, 항상 표시)
왼쪽부터 순서대로.

| 요소 | 표기 | 바인딩 |
|---|---|---|
| 로고 블록 | "◈" "FDE Data Studio" "Forward Deployed Engineering" | 정적 |
| 평면 탭 버튼 1 | "⌂ HOME" | `goHome`, `tabHomeStyle`, `icoHome` |
| 평면 탭 버튼 2 | "◈ ARD 스튜디오" (아이콘 툴팁: "ARD = Applied R&D (실명칭은 발주 측 확정 예정) · 메타데이터 스튜디오 모듈") | `goStudio` |
| 평면 탭 버튼 3 | "▦ 데이터 패브릭 관리" | `goAssets` |
| 평면 탭 버튼 4 | "≣ 데이터 카탈로그" | `goCatalog` |
| 평면 탭 버튼 5 | "⚙ 시스템 관리" | `goAdmin` |
| 프로젝트명 | "프로젝트: 국토교통데이터 암묵지 표준" | 정적 문자열 |
| 저장 상태 | "저장됨 · HH:MM" 또는 "저장 이력 없음" | `saveLabel` (L3077) |
| 배지 | "SHACL 통과 0" | 정적 문자열(계산 없음) |
| 배지 | "위반 {violCount}" | `violCount` = props.violationCount, 기본 0 (L375, L1410) |
| 사용자 칩 버튼 | 아바타 "홍", "홍길동", 빨간 카운트 "4" | `toggleMy`, 이름·숫자 모두 정적 |

### 2.3 사용자 팝오버 (M58~M96, 조건 `myOn`)
우상단 고정 360px 패널. 내용은 전부 정적 문자열이다(값은 4.4절).
- 머리: 아바타 "홍", "홍길동", 역할 배지 "담당자 (검수)", "빅데이터센터 수집운영과 · hong@molit.go.kr", 닫기 "✕"(`toggleMy`)
- "담당 단계:" 칩 3개: "STEP 1 정", "STEP 2 정", "STEP 3 부"
- "MY TASK · 4건": 클릭 가능한 행 4개(`goStep2Task`, `goQueueTask`, `goStep7Task`, `goStep3Task`)
- "최근 알림": 3행
- 하단 링크: "내 정보"(동작 없음), "알림 설정"(동작 없음), "권한 보기"(`goAdminFromMy`), "로그아웃"(동작 없음)

### 2.4 이동 경로 바 (M98~M112, 조건 `trailOn` = 방문 평면 2개 이상)
- 라벨 "이동 경로"
- 방문한 평면마다 칩 1개: 칩 라벨(`tc.label`) 클릭 시 해당 평면으로 이동, "✕"(툴팁 "경로에서 제거") 클릭 시 경로에서 제거. 칩 사이 구분자 "›".

### 2.5 사이드바: 8단계 스텝퍼 (M115~M141, 조건 `isStudio`)
- 제목 "워크플로 8단계"
- 단계 행 8개(`steps`): 원형 마크(`st.mark`: 숫자 / "✓" / "🔒"), "STEP {n}", 단계 라벨
- 구분선 아래 "현재 단계 담당 조직" 박스
  - 조직명(`ownerOrg`)
  - "정" 배지 + `ownerMain` + "작업자"
  - "부" 배지 + `ownerSub` + "작업자"
  - "관" 배지 + `ownerAdmin` + "관리자"
  - 안내문: "확정·승인 권한은 관리자에게 있으며, 단계별 담당 배정은 관리 > 사용자 관리에서 변경합니다" ("관리 > 사용자 관리"는 링크, `goAdmin`)

### 2.6 메인 상단 복귀 배너 (M145~M150, 조건 `fixBackOn`)
- 문구: "⚠ STEP 6 위반 수정 중 — {fixBackShape} · 보강 후 검증으로 복귀하세요 (수정 시 검증 결과 자동 무효화)"
- 버튼 "검증으로 복귀 ↩" (`fixBackGo`)
- STEP 6 결과표의 [수정하러 이동]에서 진입했을 때만 켜진다(L2804). 평면 조건이 없어서 `fixBack`이 남아 있는 동안 모든 평면·단계 상단에 나타난다.

### 2.7 STEP 1 본문 (M152~M364, 조건 `show1` = plane 'studio' 이고 step 1)

#### (1) 제목부 (M155~M156)
- "STEP 1: 데이터셋 조합 1차 추출" + 배지 "AI"
- 부제 "파일 업로드 즉시 유형을 자동판별하고, 연계키 기반 데이터셋 조합을 제안합니다."

#### (2) 작업 프로세스 카드 (M157~M204)
- "작업 프로세스:" + 현재 프로세스명 칩(`procCurName`) + 설명 "STEP 1~7 작업 상태(업로드·선택·조합·분류·검증·직렬화)가 프로세스 단위로 저장·복원됩니다"
- 버튼 "프로세스 목록 ({procCount}건) ▾/▴" (`procListToggle`)
- 모달(조건 `procAskOn`):
  - 제목 "새 프로세스를 시작하시겠습니까?"
  - 본문 "「{procAskCur}」는 STEP 6 변환까지 **완료된 상태**입니다. 새 데이터셋을 선택하면 현재 프로세스는 **자동 저장**되고 「{procAskNext}」가 새로 시작됩니다."
  - 버튼 "아니오 (취소)" (`procAskNo`), 버튼 "예 — 저장 후 {procAskNext} 시작" (`procAskYes`)
- 펼침 목록(조건 `procListOn`):
  - 빈 상태 문구(조건 `procEmpty`): "저장된 프로세스가 없습니다 — 프로세스가 완료된 뒤 새 데이터셋을 선택하면 자동 저장되어 목록에 담깁니다"
  - 프로세스 행(`procRows`): 체크박스(`pr.chk`, `pr.chkToggle`), 이름(굵게), "· {pr.meta}", 버튼 "불러오기"(`pr.load`)
  - 미리보기 박스(조건 `pvOn`): "☑ 선택한 프로세스의 데이터셋 — {pvLabel} · {pvCount}건", 행마다 프로세스명 칩 + 데이터셋명 + "연계키 {keys}"
  - 안내문: "ⓘ 불러오기 시 현재 작업은 자동으로 임시저장된 뒤 해당 프로세스의 STEP 1~7 상태로 전환됩니다 · 프로세스 **삭제·휴지통 관리는 데이터 카탈로그 > 산출물 저장소**에서 — 이동 →" ("이동 →" 링크, `goCatalog`)

#### (3) 2열 영역 (M205~M243)
좌측: 업로드 드롭존(점선 테두리)
- "엑셀 · CSV · Parquet 파일을 끌어다 놓으세요"
- "다중 업로드 지원 · 또는 파일 선택" ("파일 선택"은 숨은 `<input type="file" multiple accept=".csv,.xlsx,.xls,.parquet">`의 라벨, `fileUp`)
- 녹색 안내 박스: "✓ **CCTV 영상 · 센서 스트림 등 대용량 실시간성 데이터는 파일 업로드 대상이 아닙니다** — 현재 `cctv.vehicle.det.v1` · `kma.aws.obs.v1` 2건이 데이터 패브릭 관리 > 스트림 관리 연동으로 유입되어 위 스트림 카드로 표시되고 있습니다. 신규 스트림 추가는 시스템 관리 > 연계·연동 관리(HDFS/S3 · Kafka) → 스트림 관리 등록 순으로 진행하세요 — 데이터 본체는 레이크에 두고 메타데이터만 판독합니다." (링크 2개: `goStream`, `goLinkAdmin`)
- 업로드 완료 박스(조건 `upOn`): "✓ {upSummary} — 유형 자동판별·프로파일 완료, 아래 유형 카드와 AI 제안 조합에 반영되었습니다."

우측: "외부 소스 연계" 카드 (부제 "시스템 관리 > 연계·연동과 동기화됨"). 5행 모두 정적(값은 4.5절). 맨 아래 링크 "+ 소스 추가 — 시스템 관리 > 연계·연동 관리로 이동"(`goLinkAdmin`).

#### (4) 선택 요약·보기 전환 줄 (M244~M255, 조건 `upOn`)
- "☑ **선택한 데이터셋만** AI 제안 조합에 포함됩니다 — 선택 **{manCount}** / {upTotal}건 (업로드 {upFileTotal} + 스트림 2)"
- 버튼 "🗑 업로드 선택 삭제 (n)" / 확인 단계에서는 "정말 삭제? (한 번 더)" (`upClearAll`; 툴팁 "☑ 선택한 업로드 데이터셋만 삭제 — 조합·이후 스텝에서도 함께 제거됩니다 (데모 스트림은 유지)")
- 세그먼트 토글: "▦ 버튼식 보기"(`viewCard`) / "☰ 리스트로 보기"(`viewList`)

#### (5-a) 리스트 보기 (M256~M274, 조건 `upViewList`)
표 헤더: "선택" | "데이터셋" | "유형" | "프로파일" | "연계키 후보" | (빈 칸)
행(`upCards`, 업로드 파일만. 스트림은 리스트 보기에 나오지 않는다):
- 체크박스(읽기 전용, 행 전체 클릭이 토글) | 파일명 + 배지 "AI 추천" | 유형 칩 | 프로파일 문자열 | "K7 시각 (패턴 매칭)" (정적) | 링크 "레이크 적재 요청 →"(`goLakeCell`)

#### (5-b) 버튼식(카드) 보기 (M275~M328, 조건 `upViewCard`, 4열 그리드)
표시 순서는 다음과 같다.
1. 데모 스트림 카드 2장(조건 `strmSoloOn`)
   - 카드 A: 배지 "실시간 스트림" "스트림 관리 유입" "통제", 체크박스 "선택", 제목 "cctv.vehicle.det.v1", 본문 "관측 · PT1S · 8,300 msg/s" / "인식 모델 MDL-000004 v2.1 (차종·번호판 OCR)" / "연계키 후보: K6 차량 · K7 시각 · K5 도로링크", 링크 "스트림 관리에서 규칙(Plan) 보기 →"(`goStreamStop`)
   - 카드 B: 배지 "컨텍스트 스트림" "스트림 관리 유입", 체크박스 "선택", 제목 "kma.aws.obs.v1", 본문 "컨텍스트 · PT10M · 외부(기상청)" / "30.1℃ · 소나기 12.0mm/h · late 1건 (보정 재계산)" / "연계키 후보: K7 시각 · K3 좌표 (관측소 as-of)", 링크 "스트림 관리에서 규칙(Plan) 보기 →"
2. 합성 캡처 묶음 카드(`synCards`, 2칸 폭): 배지 "{실시간 스트림|컨텍스트 스트림}" + "합성 캡처 · 스트림 관리 유입", 체크박스 "선택", 묶음 이름, 메타 한 줄(`sy.meta`), 하위 데이터셋 목록(점 + 이름 + "연계키 {k}"), 링크 "스트림 관리에서 보기 →"
3. 빈 상태 박스(조건 `upEmpty`, 2칸 폭): "아직 판별된 데이터가 없습니다 — 파일을 업로드하면 유형(정형·반정형·비정형·실시간 스트림) 카드가 여기에 생성됩니다"
4. 업로드 파일 카드(`upCards`): 유형 칩 + 배지 "AI 추천", 체크박스 "선택", 파일명, 본문 "{profile}" / "규칙엔진 유형판별 · 프로파일 자동추출 완료" / "연계키 후보: K7 시각 (컬럼명 패턴 매칭)", 링크 "레이크 적재 요청 →"

그리드 아래 주석: "ⓘ Parquet 푸터 수 KB만 판독 — 데이터 본체는 레이크에서 이동하지 않음"

#### (6) AI 제안 데이터셋 조합 (M330~M361)
- 소제목 "AI 제안 데이터셋 조합", 우측 범례 "K = 연계키(조인 키) 9종 중 공유 축 — **K5** 도로링크ID · **K6** 차량ID · **K7** 시각(관측시점)"
- 추천 조합 카드(조건 `upOn`)
  - "업로드 기반 AI 추천 조합" + 배지 "AI 추천"
  - 포함 항목(`upComboItems`): 파란 점 + 이름(확장자 제거) + "{유형} · K7 후보" + 링크 "✕ 제거"(툴팁 "AI 추천 조합에서 제외")
  - 빈 상태(조건 `upComboEmpty`): "선택된 데이터셋이 없습니다 — 위 목록에서 ☑ 선택한 데이터셋만 이 조합에 포함됩니다"
  - "포함 데이터셋 {upComboCount}건 · 결합 후보 계산 중"
  - 칩 "K7 시각" (정적)
  - "신뢰도 82%" (정적), "근거: 업로드 파일 시각 컬럼 패턴 → K7 정렬 후보 · 상세 프로파일 후 재산정" (정적)
  - 버튼 "조합 선택" / "✓ 선택됨" (`pickComboUp`, `pickULabel`, `pickUStyle`)
- 빈 상태(조건 `upEmpty`): "제안된 조합이 없습니다 — 파일 업로드 후 연계키 기반 조합이 자동 제안됩니다"
- 채택 확인 배너(조건 `comboPicked`): "✓ {comboName} 조합이 내 작업 조합으로 설정되었습니다." + (조건 `comboPickedAi`) 배지 "AI 추천" + " 하단 [다음 (확정)]을 누르면 STEP 2 조합 조정으로 이동합니다."

### 2.8 AI 어시스턴트 (M3839~M3874)
- 닫힌 상태(조건 `astOff`): 우하단 떠 있는 버튼 "✦ 어시스턴트" (`astToggle`)
- 열린 상태(조건 `astOn`): 우측 고정 패널(폭 360px, 넓히면 560px)
  - 헤더: "✦", "어시스턴트", "DCAT 2.0/3.0 · PROV-O · SHACL 표준 + 스튜디오 사용법"
  - 헤더 버튼 3개: "⟲"(툴팁 "대화 내용 지우기", `astClear`), "⇤"/"⇥"(툴팁 "창 넓히기/줄이기", `astWide`), "✕"(툴팁 "닫기", `astToggle`)
  - 인사 말풍선: "안녕하세요, ARD 스튜디오(ARD = Applied R&D · 제품명, 메타데이터 스튜디오 모듈 포함) 표준·사용법 어시스턴트입니다. DCAT·PROV-O·SHACL 표준 개념이나 이 화면의 사용법을 물어보세요. 아래 추천 질문은 **{astCtxLabel}** 화면에 맞춰져 있습니다."
  - 대화 목록(`astChat`): 질문 말풍선(우측, 파랑) + 답변 말풍선(좌측, 줄바꿈 유지)
  - "{astCtxLabel} 추천 질문" + 추천 질문 버튼들(`astSuggs`)
  - 입력창(placeholder "표준·사용법 질문 입력…", `astInput`, `astType`, `astKey`) + 버튼 "전송"(`astSend`)
  - 면책 문구: "답변은 초안입니다 — 표준 원문(W3C 권고)과 기관 가이드라인을 우선하세요 · 대화도 prov:Activity로 기록됩니다"

### 2.9 하단 고정 바 (M3876~M3889, 조건 `isStudio`)

| 순서 | 표기 | 핸들러 | 툴팁 |
|---|---|---|---|
| 좌 | "이전" | `prevStep` | 없음 |
| 우1 | "데모 데이터 지우기" / 확인 단계 "정말 전부 지울까요? (다시 클릭)" | `wipeDemo` | "업로드·조합·프로세스 목록·휴지통·임시저장 스냅숏을 모두 지우고 처음 상태로 되돌립니다" |
| 우2 | "↺ 데모 데이터 복구" | `restoreDemo` | "기준 데모 스냅숏(2026-08-21 16:07)으로 전체 작업 상태를 복구합니다" |
| 우3 | "⤓ 파일로 저장" | `draftExport` | "작업 스냅숏을 JSON 파일로 다운로드 — 원하는 폴더(예: Downloads\FDE Studio v1.0)에 보관" |
| 우4 | "⤒ 파일 불러오기" (숨은 file input, accept=".json") | `draftImport` | "보관해 둔 스냅숏 JSON 파일을 불러와 복원" |
| 우5 | "임시저장" / 저장 직후 "✓ 임시저장" | `tempSave` | 없음 |
| 우6 | "다음 (확정)" | `nextStep` | 없음 |

### 2.10 토스트와 알림 팝업 (M3891~M3909)
- 토스트(조건 `toastOn`): 하단 중앙 어두운 알약형, 내용 `toastMsg`
- 다음 단계 담당자 알림 팝업(조건 `notifyOn`): 우하단 340px 카드
  - "🔔 다음 단계 담당자 알림 발송", 닫기 "✕"(`closeNotify`)
  - "**{notifyFrom}** 확정 완료 → **{notifyTo}** 작업 요청"
  - "수신: **{notifyOwner}** (정 홍길동 · 부 이순신) · 참조: 관리자 변학도"
  - 칩 "✓ 시스템 알림", "✓ 기관 메일", "업무포털 쪽지 (설정 꺼짐)"
  - "미확인 시 24시간 후 재발송 · 전자결재 연동 시 결재선 상신 — 발송 이력은 prov:Activity로 기록"

---

## 3. 사용자 동작 → 결과

### 3.0 공통 메커니즘

**`go(patch)` (L4~L28): 모든 이동의 단일 진입점**
1. `patch.step`이 현재와 다르고 대상 평면이 스튜디오이면 `stepGate(patch.step)`을 검사한다. `canEnter`가 거짓이면 상태를 바꾸지 않고 토스트 `'🔒 STEP ' + n + ' 잠김 — ' + reason`을 3000ms 띄운 뒤 반환한다. 예외: `patch.comboMeta.done`이 참이면(STEP 2 조합 확정) 게이트를 건너뛴다.
2. `patch`에 `plane`, `step`, `tab3`, `gran`, `pipe` 중 하나라도 있으면 `savedHere = false`로 되돌린다(임시저장 버튼이 흰색으로 복귀).
3. 400ms 디바운스로 `persistDraft()`(localStorage 저장)를 예약한다.
4. `patch.plane`이 있으면 `trail` 배열에 해당 평면을 중복 없이 뒤에 붙인다.

**토스트 3종**
- `showToast()` (L46~L51): `toastId = 'ACT-K-' + (400 + 0~98 난수)를 4자리로` 를 만들고 2200ms 표시. 문구는 `toastMsg` 기본형 `'✓ prov:Activity ' + toastId + ' 기록됨'` (L1708).
- 직접 지정형: `toast: true, toastText: '...'` 후 `setTimeout`으로 2600~4000ms 뒤 해제.
- `toastP(txt)` (L930): 프로세스 관련 토스트, 3000ms.

**활동 로그 `logAct(who, txt, actId)` (L53~L61)**
- `actId`가 없거나 "신규"를 포함하면 세션 시퀀스(`actSeq`, 초기 420)를 1 올려 `'ACT-K-0421'`부터 발급한다.
- `actLog`에 `{ t: 'HH:MM', who, txt, actId }`를 추가하고 최근 10건만 유지한 뒤 `persistDraft()`.
- `actLog`는 HOME 대시보드에서 소비된다(범위 밖).

**단계 게이트 `stepGate(n)` (L324~L342)**: 4.1절 표 참조.

### 3.1 로그인 (L359~L374)

| 동작 | 결과 |
|---|---|
| ID/Password 입력 | `loginId` / `loginPw` 갱신, `loginErr = false` |
| "로그인" 클릭 또는 입력창에서 Enter | `loginId.trim() === 'admin'` 이고 `loginPw === '9876'` 이면 `authed = true`, `loginErr = false`, `loginPw = ''`, `sessionStorage['fde-authed'] = '1'`. 아니면 `loginErr = true` |
| 게이트 표시 조건 | `loginGate = !authed`. `authed`가 undefined면 `sessionStorage['fde-authed'] === '1'` 여부로 대체(L365~L366) |

토스트·로그 없음. 로그아웃 처리 코드는 없다("로그아웃" 링크는 핸들러 미연결).

### 3.2 헤더

| 컨트롤 | 핸들러 | 결과 |
|---|---|---|
| "HOME" | `goHome` (L519) | `go({ plane: 'home' })` |
| "ARD 스튜디오" | `goStudio` (L1712) | `go({ plane: 'studio' })`, 단계는 직전 `step` 유지 |
| "데이터 패브릭 관리" | `goAssets` (L1712) | `go({ plane: 'assets' })` |
| "데이터 카탈로그" | `goCatalog` (L478) | `go({ plane: 'catalog', catDetail: false })` |
| "시스템 관리" | `goAdmin` (L671) | `go({ plane: 'admin' })` |
| 사용자 칩 | `toggleMy` (L3070) | `go({ my: !my })`, 팝오버 열림/닫힘 |

활성 탭 스타일은 `planeTab(on)` / `planeIco(on, color)` (L407~L410)로 계산한다. 아이콘 배경색: HOME `#e8912d`, 스튜디오 `#1E5EFF`, 패브릭 `#2aa876`, 카탈로그 `#7a6bb0`, 관리 `#111318`.

### 3.3 사용자 팝오버 (L3069~L3076)

| 컨트롤 | 결과 |
|---|---|
| "STEP 2 조합 확정 대기" 행 | `go({ plane: 'studio', step: 2, my: false })` (게이트 적용. 잠겨 있으면 이동도 팝오버 닫힘도 일어나지 않는다) |
| "검수 큐 — 내 배정 5건" 행 | `go({ plane: 'queue', my: false })` |
| "sLLM 보정 제안 승인 대기 2건" 행 | `go({ plane: 'studio', step: 6, pipe: 2, my: false })` |
| "DST-000712 수기 입력" 행 | `go({ plane: 'studio', step: 3, tab3: 4, fixGuide: true, my: false })` |
| "권한 보기" | `go({ plane: 'admin', admTab: 1, my: false })` |
| "내 정보", "알림 설정", "로그아웃" | 핸들러 없음 |

### 3.4 이동 경로 바 (L1713~L1735)
- `trail`이 비어 있으면 `[plane]`으로 간주. 표시 조건은 길이 2 이상.
- 칩 라벨 클릭: `setState({ plane: p })` (go()를 거치지 않으므로 게이트·자동 저장·`savedHere` 초기화가 적용되지 않는다).
- "✕" 클릭: `trail`에서 해당 평면 제거. 제거한 평면이 현재 평면이면 남은 경로의 마지막 평면으로, 남은 것이 없으면 `'home'`으로 이동.
- 현재 평면 칩은 어두운 배경(`#1F2430`)으로 강조.

### 3.5 사이드바 스텝퍼 (L377~L394)
- 단계 행 클릭: `go({ step: n, plane: 'studio' })`. 잠긴 단계는 3.0의 게이트 토스트로 거부된다.
- 마크 규칙: 잠김이고 현재 단계가 아니면 "🔒", 완료면 "✓", 그 외 단계 번호.
- 색 규칙: 현재 단계 행 배경 `rgba(30,94,255,.18)`. 점 색은 잠김 회색, 완료 `#2aa876`, 현재 파란 테두리, 그 외 반투명 흰색.
- "관리 > 사용자 관리" 링크: `goAdmin`. `admTab`을 지정하지 않으므로 직전에 보던 관리 탭(없으면 1번 탭)이 열린다.
- 담당 조직 표시: `ownerOrg`는 `step`에 따른 배열 조회(L1682), 정·부·관리자 이름은 단계와 무관한 고정값(L1683).

### 3.6 복귀 배너
- "검증으로 복귀 ↩": `go({ plane: 'studio', step: 6 })` (L2857). `fixBack`은 STEP 6 재검증 완료 시 null이 된다(L1667).

### 3.7 STEP 1: 작업 프로세스 (L918~L1109)

**현재 프로세스명 `procCurName` 계산 (L933~L935)**
1. `procName`이 있고 `' + '`로 나눈 모든 조각이 `procList`에 존재하면 `procName`
2. 아니면 조합이 있고 `comboName`이 있으면 `comboName`
3. 아니면 `(procList.length + 1) + '차 프로세스'` (목록이 비면 "1차 프로세스")

**다음 프로세스명 `nextName()` (L960~L965)**: `procList` 이름들과 현재 이름의 고유 개수 + 1 을 n으로 잡고, `n + '차 프로세스'`가 이미 있으면 n을 올린다.

**저장 `saveCur(done)` (L936~L945)**: 다음 항목을 만들어 같은 이름의 기존 항목을 교체하고 `procName`을 현재 이름으로 고정한 뒤 `persistDraft()`.
```json
{ "id": "Date.now()", "name": "curName", "savedAt": "MM-DD HH:mm (toISOString 기준 = UTC)",
  "step": "done ? 7 : 현재 step", "ver": 2, "count": "combo.length",
  "done": "done 또는 기존 항목의 done", "snapshot": "workKeys에 해당하는 state 사본" }
```

| 컨트롤 | 결과 |
|---|---|
| "프로세스 목록 (n건)" | `go({ procOpen: !procOpen })` |
| 프로세스 행 체크박스 | `procViewSel[name]` 토글. 체크된 프로세스들의 `snapshot.combo`를 펼쳐 `pvDs`(`{ proc, name: d.n, keys: d.k 또는 'K7' }`)로 미리보기. `pvLabel`은 이름을 `' + '`로 연결 |
| "불러오기" (`pr.load`, L1076~L1080) | ① `saveCur()`로 현재 작업 저장 ② `setState({ ...blank(), ...p.snapshot, procName: p.name, procOpen: false, cands2All: false, taskProcSel: null, plane: 'studio' })` ③ 토스트 `'↺ 프로세스 「' + p.name + '」 불러옴 — 저장 시점 STEP ' + p.step + ' 상태로 복원 (현재 작업은 자동 저장됨)'`. 로그 없음. `step`은 스냅숏 값으로 복원되며 게이트를 거치지 않는다 |
| 모달 "아니오 (취소)" | `go({ procAsk: null })`. 선택 토글은 일어나지 않은 채로 남는다 |
| 모달 "예 — 저장 후 … 시작" (L970~L976) | ① `saveCur()` ② `setState({ ...blank(), procName: next, procOpen: false, procAsk: null, manSel: { [대기 중이던 후보 키]: true } })` ③ 토스트 `'＋ 「' + curName + '」 저장 완료 · 「' + next + '」 시작 — 선택한 데이터셋으로 새 프로세스가 시작되었습니다'` |
| "이동 →" | `goCatalog` |

`pr.meta` 형식(L1071): `savedAt + ' 저장 · 데이터셋 ' + count + '건 · ' + (done ? '✔ 프로세스 종료 (STEP 7 완료)' : 'STEP ' + step + ' 진행')`

**`blank()` (L923~L928)**: `workKeys` 중 `upList`, `upFile`, `upView`를 뺀 전부를 undefined로 만들고 `combo: [], step: 1, tab3: 1, ds3: 0, plane: 'studio'`를 설정한다. 업로드 풀은 프로세스 간에 공유된다는 뜻이다.

**새 프로세스 가드 `_procGuard(pendingName)` (L949~L959)**: 후보 선택 토글 직전에 호출된다. 다음 세 조건이 모두 참이면 토글을 중단하고 `go({ procAsk: pendingName })`로 모달을 띄운다.
1. 해당 후보가 아직 선택되지 않은 상태다(해제 클릭은 가드 대상이 아니다).
2. `convertState === 'done'` 이거나, 현재 프로세스명이 `procList`에 저장되어 있다.
3. `combo`가 1건 이상이다.

### 3.8 STEP 1: 파일 업로드 `fileUp` (L2213~L2251)
1. 선택된 파일이 없으면 종료.
2. 대용량·스트림성 가드: `f.size > 52428800`(50MB) 이거나 파일명이 `/\.(mp4|avi|ts|pcap|bag)$/i`에 맞으면 제외 대상. 제외 대상이 있으면 토스트 `'⚠ ' + 파일명들(' · ' 연결) + ' — 대용량·실시간성 데이터는 데이터레이크 연동 후 외부 소스 연계로 등록하세요 (시스템 관리 > 연계·연동 관리)'`를 4000ms 표시하고 나머지만 처리한다. 남는 파일이 없으면 종료.
3. 파일마다 항목 생성(규칙은 4.8절): `{ name, size, type, profile }`.
4. 확장자가 csv이면 `FileReader`로 앞 262,144바이트(256KB)만 읽어 첫 줄을 `,`로 나눈 개수를 컬럼 수, 공백 아닌 줄 수 − 1 을 행 수로 삼아 `profile = '스키마 ' + cols + '컬럼 · ' + rows(천 단위 구분) + '행 (실측)'`로 바꾼다. 그 외 확장자는 내용을 읽지 않는다.
5. 모든 파일 처리가 끝나면 `setState({ upFile: 마지막 항목, upList: 이번에 올린 항목 전체 })` 후 `showToast()` (문구 `'✓ prov:Activity ACT-K-04xx 기록됨'`).

유의 사항
- `upList`는 누적이 아니라 **교체**된다. 이전 업로드 목록은 사라지지만 `manSel`의 예전 키는 남는다.
- 업로드 직후 자동 선택은 없다. 새 카드는 미선택(파란 테두리) 상태로 나타난다.
- `logAct` 호출이 없고 `go()`도 거치지 않으므로 이 시점에는 localStorage에 저장되지 않는다(다음 이동·임시저장 때 저장).
- 드롭존 문구와 달리 드래그 앤 드롭 핸들러는 연결되어 있지 않다(M206에 drop 이벤트 없음). 파일 선택 input만 동작한다.

`upSummary` 형식(L2080~L2087): `'「' + (procName 또는 '현재 프로세스') + '」 업로드 ' + N + '건 (' + 이름목록 + ') · 선택 ' + 선택수 + '건'`. 이름목록은 2건 이하면 `' · '`로 나열, 3건 이상이면 `첫 이름 + ' 외 ' + (N-1) + '건'`. 선택수는 `manSel`에서 참인 키 전체 개수(스트림 포함).

### 3.9 STEP 1: 후보 선택과 보기 전환

| 컨트롤 | 핸들러 | 결과 |
|---|---|---|
| 업로드 카드 또는 리스트 행 클릭 | `uf.toggle` (L2109) | 가드 통과 시 `manSel[f.name]` 토글. 키는 **확장자를 포함한 파일명** |
| 데모 스트림 카드 A 클릭 | `strmTogC` (L1112) | 가드 통과 시 `manSel['cctv.vehicle.det.v1']` 토글 |
| 데모 스트림 카드 B 클릭 | `strmTogK` (L1113) | 가드 통과 시 `manSel['kma.aws.obs.v1']` 토글 |
| 합성 캡처 묶음 카드 클릭 | `sy.toggle` (L1221~L1230) | 가드(키는 묶음 이름) 통과 시, 하위 구성원이 전부 선택돼 있으면 전부 해제, 아니면 전부 선택. 구성원 4개 키와 묶음 이름 키를 같은 값으로 설정 |
| "▦ 버튼식 보기" | `viewCard` (L2121) | `go({ upView: 'card' })` |
| "☰ 리스트로 보기" | `viewList` (L2122) | `go({ upView: 'list' })` |
| "레이크 적재 요청 →" | `goLakeCell` (L2570) | `go({ plane: 'assets', fabTab: 1, cell: 'lakeC' })`. 전파 중단이 없어 카드·행 토글도 함께 일어난다 |
| "스트림 관리에서 … 보기 →" | `goStreamStop` (L917) | `stopPropagation` 후 `go({ plane: 'assets', fabTab: 3 })` |
| 안내 박스의 "데이터 패브릭 관리 > 스트림 관리" | `goStream` (L1256) | `go({ plane: 'assets', fabTab: 3 })` |
| "시스템 관리 > 연계·연동 관리", "연계·연동에서 재연결 →", "+ 소스 추가 …" | `goLinkAdmin` (L523) | `go({ plane: 'admin', admTab: 6 })` |
| 외부 MCP 서버 행의 "연결" 버튼 | 없음 | 핸들러 미연결 |

선택 표시 규칙
- 업로드 카드: 선택 시 `border:2px solid #111318` + 그림자, 미선택 시 `border:2px solid #1E5EFF` (L2107). 리스트 행은 선택 시 배경 `#F5F6F8`.
- 데모 스트림 카드: 선택 시 검정 테두리, 미선택 시 `#7a3fa0` (L1114~L1115).
- 묶음 카드: 전 구성원 선택 시 검정 테두리, 아니면 `1px solid #d3b8e6`. 구성원 점은 선택 `#2aa876`, 미선택 `#D1D5DB` (L1220, L1231).

카운트 계산
- `manCount` = `manSel`에서 참인 값의 개수 (L2268)
- `upTotal` = 업로드 파일 수 + 2 (스트림 카드 2장을 항상 더함, L2117)
- `upFileTotal` = 업로드 파일 수 (L2118)
- `upComboCount` = `manSel`에서 참인 키 개수 (L2161)

데모 스트림 카드 표시 조건: `strmSoloOn = !(strmDemoHide ?? true) && synStreams.length === 0` (L1143, L1146). 기본값에서는 숨김이며, 데이터 패브릭 관리 > 스트림 관리의 "↺ 데모 데이터 복원" 버튼(`strmDemoToggle`)으로 켠다. 합성 캡처 묶음이 1건이라도 있으면 개별 데모 카드는 숨는다.

### 3.10 STEP 1: 업로드 선택 삭제 `upClearAll` (L2132~L2158)
- 대상: `upList` 중 `manSel`이 참인 파일(n건). n이 0이면 버튼이 비활성 모양이고 클릭해도 반응 없음.
- 1차 클릭: `go({ upClearAsk: true })`, 라벨이 "정말 삭제? (한 번 더)"로 바뀜(자동 해제 타이머 없음).
- 2차 클릭:
  - `upList`에서 대상 제거, `upFile`은 남은 첫 항목 또는 null
  - `manSel`에서 대상 키 삭제, `upClearAsk = false`
  - `combo`에서 확장자를 뗀 이름이 일치하는 항목 제거. 조합이 비면 `comboName`, `comboMeta`, `comboSel`을 undefined로
  - 토스트(3000ms): `'🗑 선택한 업로드 데이터셋 ' + n + '건 삭제 — STEP 1 카드·조합·이후 스텝에서 동시 제거'`
  - 로그: `logAct('홍길동 (나)', '업로드 선택 삭제 — ' + 이름들(' · ' 연결), 'ACT-DEL-신규')` (ID는 시퀀스로 재발급)
  - `persistDraft()`
- 스트림 선택분은 삭제 대상이 아니다. 조합이 바뀌어도 `invalidateDownstream`은 호출되지 않는다.

### 3.11 STEP 1: AI 제안 조합
**포함 항목 `upComboItems` (L2126~L2129)**: `upList` 중 선택된 파일만. `{ name: 확장자 제거 이름, sub: type + ' · K7 후보' }`. "✕ 제거"는 `manSel[f.name] = false`.

**"조합 선택" `pickComboUp` (L2252~L2260)**
1. `manSel`에서 참인 키 전체(업로드 파일 + 스트림 + 묶음 이름 + 묶음 구성원)를 대상으로 한다. 0건이면 반환(버튼은 회색 비활성 모양).
2. 항목 생성: `{ n: 키에서 /\.(xlsx|xls|csv|parquet)$/i 제거, k: kOf(키), src: 'ai' }`. `kOf`는 4.9절 표.
3. `go({ comboSel: 'up', comboName: 이름들을 '+'로 이어 60자로 자름, ds3: 0, ds3Done: null, tab3: 1, combo: items })`. 기존 조합은 통째로 교체된다.
4. `showToast()` (문구 `'✓ prov:Activity ACT-K-04xx 기록됨'`).
5. 단계 이동은 없다. 배너 "✓ {comboName} 조합이 내 작업 조합으로 설정되었습니다."가 나타나고 버튼 라벨이 "✓ 선택됨"으로 바뀐다.

`comboName` 바인딩(L2040): 조합이 있으면 `s.comboName` 또는 "작업 조합", 없으면 "(비어 있음)".

### 3.12 하단 고정 바

| 컨트롤 | 결과 |
|---|---|
| "이전" (`prevStep`, L2957~L2964) | `persistDraft()` 후 STEP 1에서는 `go({ step: 1 })` (사실상 변화 없음). STEP 3/5/6에서는 내부 탭·뷰를 먼저 한 칸 되돌린다 |
| "다음 (확정)" (`nextStep`, L2965~L2994) | ① `autoSave()`: `saveTime = 'HH:MM'` 기록 후 `persistDraft()` ② (STEP 1에는 내부 하위 단계가 없음) `showToast()` ③ `go({ step: 2, notify: { from: 'STEP 1', to: 'STEP 2', owner: '빅데이터센터 수집운영과' } })` ④ 5000ms 뒤 `notify = null`. 게이트: `manSel` 선택 1건 이상 또는 `combo` 1건 이상이어야 하며, 아니면 토스트 `'🔒 STEP 2 잠김 — STEP 1에서 후보를 1건 이상 선택하세요'` |
| "임시저장" (`tempSave`, L3111~L3122) | `saveTime = 'HH:MM'`, `savedHere = true`, `persistDraft()`. 성공 토스트(3200ms) `'💾 임시저장되었습니다 · ' + HH:MM + ' — 브라우저에 보관되어 새로고침 후에도 복원됩니다 (파일 원본은 재첨부 필요)'`, 실패 토스트 `'⚠ 임시저장 실패 — 브라우저 저장 공간을 확인하세요'` |
| "⤓ 파일로 저장" (`draftExport`, L3078~L3089) | `draftState()` + `exportedAt`(ISO)를 JSON으로 내려받음. 파일명 `'FDE-Studio-작업스냅숏-' + YYYY-MM-DD-HH-mm + '.json'`(UTC). 토스트 `'⤓ 스냅숏 JSON 다운로드됨 — 원하는 폴더(예: Downloads\FDE Studio v1.0)에 보관하세요'` |
| "⤒ 파일 불러오기" (`draftImport`, L3090~L3106) | JSON을 그대로 state에 병합(`setState({ ...d, savedHere: false })`)하고 `persistDraft()`. 토스트 `'⤒ 스냅숏 파일 복원됨 (' + (saveTime 또는 exportedAt) + ' 저장분) — 파일 원본은 재첨부 필요'`. 파싱 실패 시 `'⚠ 복원 실패 — 올바른 스냅숏 JSON 파일이 아닙니다'`. 스키마 검증·버전 마이그레이션 없음 |
| "데모 데이터 지우기" (`wipeDemo`, L982~L994) | 1차 클릭: `wipeAsk = true`(4000ms 뒤 자동 해제). 2차 클릭: localStorage `'fde-studio-draft'` 삭제, state의 모든 키를 undefined로 만든 뒤 `{ plane: 'studio', step: 1, tab3: 1, cell: 'none', edgesOpen: false, combo: [], procList: [], procTrash: [] }` 설정. 토스트 `'🗑 데모 데이터 삭제 완료 — 업로드·조합·프로세스 목록·임시저장이 초기화되었습니다'` |
| "↺ 데모 데이터 복구" (`restoreDemo`, L995~L1005) | `window.__resources.demoSnap` 또는 `./demo-snapshot.json`을 fetch해 state 전체를 교체(`exportedAt` 제거, 구버전이면 단계 6↔7 치환, `simMode = null`). 토스트 `'↺ 데모 데이터 복구 완료 — 2026-08-21 16:07 기준 스냅숏'`, 실패 시 `'⚠ 복구 실패 — demo-snapshot.json을 찾을 수 없습니다'` |

임시저장·복원 부가 규칙
- 저장 위치: `localStorage['fde-studio-draft']`. 저장 제외 키는 `draftState()`의 skip 목록(L93~L95): `toast, toastText, notify, restored, savedHere, ast, astChat, astInput, astW, linkPick, relPick, relSel, ssotPick, taxAxisForm, taxCodeForm, taxAxisName, taxCodeName, taxEditNewV, mapZoom, q4, batchOn, simMode, linAsk, linReason, fixBack, fixField`. 저장 시 `stepVer = 2`를 붙인다.
- 최초 마운트 시 복원(L62~L90): 스냅숏이 있으면 병합하고 토스트 `'↺ 임시저장 스냅숏 복원됨 · ' + saveTime + ' 저장분 — 파일 원본은 재첨부가 필요합니다'`(3600ms). 잠긴 단계로 복원되면 통과 가능한 마지막 단계로 내려간다. `stepVer`가 없으면 단계 6↔7을 맞바꾸고 "신규"가 든 `actLog` ID를 시퀀스로 재부여한다.

### 3.13 AI 어시스턴트 (L2995~L3065)

| 컨트롤 | 결과 |
|---|---|
| "✦ 어시스턴트" / 패널 "✕" | `go({ ast: !ast })` |
| "⟲" | `go({ astChat: [], astInput: '' })` |
| "⇤"/"⇥" | `go({ astW: !astW })`, 패널 폭 360px ↔ 560px |
| 입력 | `go({ astInput: 값 })` |
| Enter 또는 "전송" | 입력이 비어 있지 않으면 `ask(입력.trim())` |
| 추천 질문 버튼 | `ask(질문 문구)` |

`ask(q)` (L3046~L3049): 질문 문자열이 사전 `A`의 키와 **정확히 일치**하면 그 답을, 아니면 고정 대체 답변을 골라 `astChat`에 `{ q, a }`를 추가하고 입력을 비운다. 지연·네트워크 호출·로그 기록 없음.

컨텍스트 키: 스튜디오 평면이면 `'step' + step`, 아니면 평면 이름(L2996). 추천 질문은 `suggMap[ctxKey]`, 없으면 `suggMap.home`. 라벨은 `ctxLabels[ctxKey]`, 없으면 "현재".

### 3.14 알림 팝업
- "✕": `go({ notify: null })`. 그 외에는 5000ms 뒤 자동으로 닫힌다.
- 수신자 이름(정 홍길동, 부 이순신, 관리자 변학도)과 채널 칩 3개는 정적이다. 실제 발송은 없다.

---

## 4. 데이터 (하드코딩 값 원문)

### 4.1 워크플로 8단계
라벨 원본(L377):
```js
const labels = ['데이터셋 조합 추출 (AI)', '조합 조정·확정', 'DCAT/PROV-O 카탈로그', '다중분류체계 배정', '매핑 + LPG·리니지', '검증: 게이트 0 + SHACL', '직렬화·발행 포맷 변환', '가이드라인 준수 진단'];
```

| n | label (verbatim) | 담당 조직 `ownerOrg` (L1682, L2989) | 진입 조건 `canEnter` | 완료 조건 `done` | 잠김 사유 `reason` (verbatim) |
|---|---|---|---|---|---|
| 1 | 데이터셋 조합 추출 (AI) | 빅데이터센터 수집운영과 | 항상 | `manSel` 선택 1건 이상 또는 `combo` 1건 이상 | (없음) |
| 2 | 조합 조정·확정 | 빅데이터센터 수집운영과 | STEP 1 완료 조건과 동일 | `combo` 1건 이상이고 `comboMeta.done` | STEP 1에서 후보를 1건 이상 선택하세요 |
| 3 | DCAT/PROV-O 카탈로그 | 메타데이터 표준화팀 | STEP 2 완료(`comboOk`) | `ds3Done` 키 수가 `combo` 길이 이상 | STEP 2 조합 확정을 먼저 완료하세요 |
| 4 | 다중분류체계 배정 | 메타데이터 표준화팀 | `comboOk` | `dsDone4`에 참 값 1건 이상 | STEP 2 조합 확정을 먼저 완료하세요 |
| 5 | 매핑 + LPG·리니지 | 데이터 품질관리팀 | `comboOk` | `relPairs` 1건 이상 또는 `linWaived` | STEP 2 조합 확정을 먼저 완료하세요 |
| 6 | 검증: 게이트 0 + SHACL | 데이터 품질관리팀 | `comboOk` | `v7State === 'done'` 이고 `v6Stale` 아님 | STEP 2 조합 확정을 먼저 완료하세요 |
| 7 | 직렬화·발행 포맷 변환 | 데이터 품질관리팀 | STEP 6 완료이고 통과 1건 이상 | `convertState === 'done'` | 재검증 필요 — 정본이 변경되었습니다. STEP 6 검증을 다시 실행하세요 / STEP 6 검증을 먼저 실행하세요 (통과 1건 이상 필요) |
| 8 | 가이드라인 준수 진단 | 정보화기획담당관 | STEP 7 완료 | `v8State === 'done'` | STEP 7 변환을 먼저 실행하세요 |

담당자(모든 단계 공통, L1683): 정 "홍길동", 부 "이순신", 관리자 "변학도".

게이트 원본(L324~L342):
```js
stepGate(n) {
  const s = this.state;
  const selN = Object.keys(s.manSel || {}).filter(k => s.manSel[k]).length;
  const comboOk = (s.combo || []).length > 0 && !!(s.comboMeta || {}).done;
  const v6done = s.v7State === 'done' && !s.v6Stale; // v7State = 검증 상태 변수 (재편 후 STEP 6)
  const v6passN = (s.v6Results || []).filter(r => r.pass).length;
  const cvDone = s.convertState === 'done';
  const G = {
    1: { done: selN > 0 || (s.combo || []).length > 0, canEnter: true, reason: '' },
    2: { done: comboOk, canEnter: selN > 0 || (s.combo || []).length > 0, reason: 'STEP 1에서 후보를 1건 이상 선택하세요' },
    3: { done: (s.combo || []).length > 0 && Object.keys(s.ds3Done || {}).length >= (s.combo || []).length, canEnter: comboOk, reason: 'STEP 2 조합 확정을 먼저 완료하세요' },
    4: { done: Object.keys(s.dsDone4 || {}).filter(k => s.dsDone4[k]).length > 0, canEnter: comboOk, reason: 'STEP 2 조합 확정을 먼저 완료하세요' },
    5: { done: (s.relPairs || []).length > 0 || !!s.linWaived, canEnter: comboOk, reason: 'STEP 2 조합 확정을 먼저 완료하세요' },
    6: { done: v6done, canEnter: comboOk, reason: 'STEP 2 조합 확정을 먼저 완료하세요' },
    7: { done: cvDone, canEnter: v6done && v6passN >= 1, reason: s.v7State === 'done' && s.v6Stale ? '재검증 필요 — 정본이 변경되었습니다. STEP 6 검증을 다시 실행하세요' : 'STEP 6 검증을 먼저 실행하세요 (통과 1건 이상 필요)' },
    8: { done: s.v8State === 'done', canEnter: cvDone, reason: 'STEP 7 변환을 먼저 실행하세요' }
  };
  return G[n] || { done: false, canEnter: true, reason: '' };
}
```

### 4.2 평면(plane)과 이동 경로 라벨 (L1715)

| plane | 헤더 탭 표기 | trail 칩 라벨 | 아이콘 | 아이콘 색 |
|---|---|---|---|---|
| home | HOME | HOME | ⌂ | #e8912d |
| studio | ARD 스튜디오 | ARD 스튜디오 · STEP {step} | ◈ | #1E5EFF |
| assets | 데이터 패브릭 관리 | 데이터 패브릭 관리 | ▦ | #2aa876 |
| catalog | 데이터 카탈로그 | 데이터 카탈로그 | ≣ | #7a6bb0 |
| admin | 시스템 관리 | 시스템 관리 | ⚙ | #111318 |
| queue | (헤더 탭 없음) | 검수 큐 | | |

초기 상태(L3): `{ plane: 'home', step: 1, tab3: 1, cell: 'none', toast: false, toastId: '', edgesOpen: false, combo: [] }`

### 4.3 로그인 계정 (L360)

| 항목 | 값 |
|---|---|
| ID | `admin` |
| Password | `9876` |
| 세션 키 | `sessionStorage['fde-authed'] = '1'` |

### 4.4 사용자 팝오버 정적 값 (M55~M94)
```json
{
  "user": { "name": "홍길동", "avatar": "홍", "roleBadge": "담당자 (검수)",
            "org": "빅데이터센터 수집운영과", "email": "hong@molit.go.kr", "taskBadge": 4 },
  "stepAssignments": [
    { "step": 1, "role": "정" }, { "step": 2, "role": "정" }, { "step": 3, "role": "부" }
  ],
  "myTasksTitle": "MY TASK · 4건",
  "myTasks": [
    { "title": "STEP 2 조합 확정 대기", "sub": "경고 3건 검토 필요 · 어제 알림 수신", "badge": "오늘 마감",
      "target": { "plane": "studio", "step": 2 } },
    { "title": "검수 큐 — 내 배정 5건", "sub": "F4 미분류 4 · F1 추론분 1",
      "target": { "plane": "queue" } },
    { "title": "sLLM 보정 제안 승인 대기 2건", "sub": "DST-000123 mediaType · SER-0004 주기",
      "target": { "plane": "studio", "step": 6, "pipe": 2 } },
    { "title": "DST-000712 수기 입력", "sub": "HWP 혼재 — 추출 실패분 보완",
      "target": { "plane": "studio", "step": 3, "tab3": 4, "fixGuide": true } }
  ],
  "recentNotifications": [
    { "icon": "🔔", "text": "STEP 1 확정 완료 — STEP 2 작업 요청", "time": "14:02" },
    { "icon": "✓", "text": "sLLM 제안 승인됨 (DST-000390)", "time": "13:47" },
    { "icon": "⚠", "text": "접합부 대조 불일치 1건 발생", "time": "06:00" }
  ],
  "footerLinks": ["내 정보", "알림 설정", "권한 보기", "로그아웃"]
}
```

### 4.5 외부 소스 연계 5건 (M219~M240, 전부 정적)

| # | 이름 | 설명 | 상태 표기 | 행 동작 |
|---|---|---|---|---|
| 1 | 공공데이터포털 API | data.go.kr · OpenAPI 목록 조회 | 배지 "연결됨" | 없음 |
| 2 | 외부 MCP 서버 | 국가교통DB(KTDB) · mcp://ktdb.viewer | 버튼 "연결" | 핸들러 없음 |
| 3 | 문서중앙화 (ECM) | 비정형 원문 312건 유입 · 증분 4시간 | 배지 "정상" | 없음 |
| 4 | 데이터레이크 (HDFS/S3) | Kafka 2토픽 수신 · 푸터 대조 06:00 | 배지 "정상" | 없음 |
| 5 | 시스템 DB (eTAS·KOPSS·VDS) | ✕ eTAS DB 접속 실패 — 계정 만료 추정 | (경고 색 행) 링크 "연계·연동에서 재연결 →" | `goLinkAdmin` |

### 4.6 데모 스트림 카드 2건 (M278~M295)
```json
[
  { "key": "cctv.vehicle.det.v1", "typeBadge": "실시간 스트림",
    "badges": ["스트림 관리 유입", "통제"],
    "line1": "관측 · PT1S · 8,300 msg/s",
    "line2": "인식 모델 MDL-000004 v2.1 (차종·번호판 OCR)",
    "joinKeys": "연계키 후보: K6 차량 · K7 시각 · K5 도로링크",
    "link": "스트림 관리에서 규칙(Plan) 보기 →" },
  { "key": "kma.aws.obs.v1", "typeBadge": "컨텍스트 스트림",
    "badges": ["스트림 관리 유입"],
    "line1": "컨텍스트 · PT10M · 외부(기상청)",
    "line2": "30.1℃ · 소나기 12.0mm/h · late 1건 (보정 재계산)",
    "joinKeys": "연계키 후보: K7 시각 · K3 좌표 (관측소 as-of)",
    "link": "스트림 관리에서 규칙(Plan) 보기 →" }
]
```

### 4.7 합성 캡처 묶음 (L1116~L1234)
묶음 항목(`synStreams[]`) 구조: `{ name, type: '관측'|'컨텍스트', rate, at: 'HH:MM', res?, col?, tz?, wm?, late?, members? }`. 스트림 관리 화면에서 파일을 끌어다 놓거나 이름을 수기 등록해 생성한다(범위 밖). `members`를 채우는 코드는 없으므로 항상 아래 기본 구성원이 쓰인다.

기본 구성원 `DEFAULT_MEMBERS` (L1120~L1125):
```js
const DEFAULT_MEMBERS = [
  { n: 'obu.telemetry.v2', k: 'K6 · K7' },
  { n: 'TRAFFIC_LINK_5MIN', k: 'K5 · K7' },
  { n: 'cctv.vehicle.det.v1', k: 'K5 · K6 · K7' },
  { n: 'kma.aws.obs.v1', k: 'K7 · K3' }
];
```

| 필드 | 의미 |
|---|---|
| `n` | 하위 데이터셋(스트림) 이름. `manSel`의 키로도 쓰인다 |
| `k` | 연계키 축 목록(' · ' 구분) |

유형 추정 규칙(L1126): 이름이 `/기상|kma|aws|weather|obs/i`에 맞으면 "컨텍스트", 아니면 "관측". 수기 등록 시에는 `/기상|kma|aws|weather/i` (L1178).

카드 메타 형식(L1216): `type + ' · ' + (res 또는 'PT5M') + ' · 합성 캡처 (' + rate + ') · 포함 데이터셋 ' + 구성원수 + '건'`

`rate` 값: 파일 유입분은 `Math.max(1, round(size/1024)) + ' KB 캡처'`(크기 0이면 `'— 캡처'`), 수기 등록분은 `'수기 등록'` (L1132, L1178).

스트림 양식 기본값(L1189~L1196): temporalResolution `PT5M`, event-time 컬럼 `event_time`, 타임존 `Asia/Seoul`, 워터마크 `PT2M`, late 정책 `별도 적재`, 처리량 `—`.

### 4.8 업로드 파일 처리 규칙 (L2213~L2251)
원본:
```js
fileUp: e => {
  let files = Array.from(e.target.files || []);
  if (!files.length) return;
  // 대용량(50MB↑)·스트림성 파일 가드 — 레이크 연동 선행 안내
  const big = files.filter(f => f.size > 52428800 || /\.(mp4|avi|ts|pcap|bag)$/i.test(f.name));
  if (big.length) {
    this.setState({ toast: true, toastText: '⚠ ' + big.map(f => f.name).join(' · ') + ' — 대용량·실시간성 데이터는 데이터레이크 연동 후 외부 소스 연계로 등록하세요 (시스템 관리 > 연계·연동 관리)' });
    clearTimeout(this._tt);
    this._tt = setTimeout(() => this.setState({ toast: false, toastText: null }), 4000);
    files = files.filter(f => !big.includes(f));
    if (!files.length) return;
  }
  const results = [];
  let pending = files.length;
  const finish = () => {
    if (--pending > 0) return;
    // 마지막 파일을 대표(upFile)로, 전체는 upList로 기록
    this.setState({ upFile: results[results.length - 1], upList: results });
    this.showToast();
  };
  files.forEach(f => {
    const ext = (f.name.split('.').pop() || '').toLowerCase();
    const type = ext === 'parquet' ? '정형' : (ext === 'csv' ? '정형' : '정형 (엑셀)');
    const size = f.size > 1048576 ? (f.size / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(f.size / 1024)) + ' KB';
    const entry = { name: f.name, size, type, profile: '스키마 자동추론 대기 · ' + size + ' 판독' };
    results.push(entry);
    if (ext === 'csv') {
      const rd = new FileReader();
      rd.onload = () => {
        const first = String(rd.result || '').split(/\r?\n/)[0] || '';
        const cols = first ? first.split(',').length : 0;
        const rows = String(rd.result || '').split(/\r?\n/).filter(x => x.trim()).length - 1;
        entry.profile = '스키마 ' + cols + '컬럼 · ' + Math.max(rows, 0).toLocaleString() + '행 (실측)';
        finish();
      };
      rd.readAsText(f.slice(0, 262144));
    } else finish();
  });
},
```

정리표

| 규칙 | 값 |
|---|---|
| 허용 확장자(input accept, M208) | `.csv, .xlsx, .xls, .parquet` |
| 차단 조건 | 크기 > 52,428,800바이트(50MB) 또는 확장자 `mp4, avi, ts, pcap, bag` |
| 유형 판별 | `parquet` → "정형", `csv` → "정형", 그 외 전부 → "정형 (엑셀)" |
| 크기 표기 | 1,048,576바이트 초과면 `(size/1048576).toFixed(1) + ' MB'`, 아니면 `Math.max(1, round(size/1024)) + ' KB'` |
| 기본 프로파일 문구 | `'스키마 자동추론 대기 · ' + size + ' 판독'` |
| CSV 프로파일 문구 | `'스키마 ' + cols + '컬럼 · ' + rows + '행 (실측)'` (앞 256KB 기준) |
| 항목 구조 | `{ name: 원본 파일명, size: 표기 문자열, type, profile }` |

화면이 언급하는 유형 체계는 4종("정형·반정형·비정형·실시간 스트림", M314, L1737)이지만 업로드 판별 코드는 "정형"과 "정형 (엑셀)" 두 값만 만든다.

### 4.9 연계키(K축) 코드
코드표 원본(L731, L2381 동일):

| 코드 | 명칭 |
|---|---|
| K1 | 행정구역 |
| K2 | 주소 |
| K3 | 좌표 |
| K4 | 건축물ID |
| K5 | 도로링크 (STEP 1 범례 표기는 "도로링크ID") |
| K6 | 차량ID (스트림 카드 표기는 "차량") |
| K7 | 시각 (STEP 1 범례 표기는 "시각(관측시점)") |
| K8 | 사업ID |
| K9 | 문서ID |

STEP 1 조합 채택 시 연계키 부여 규칙 `kOf` (L2254):

| 후보 키 | 부여되는 `k` |
|---|---|
| `cctv.vehicle.det.v1` | `K5 · K6 · K7` |
| `kma.aws.obs.v1` | `K7 · K3` |
| 그 외 전부(업로드 파일, 묶음 이름, `obu.telemetry.v2`, `TRAFFIC_LINK_5MIN` 포함) | `K7` |

참고: STEP 4에 파일명 정규식 기반 K축 자동 감지 규칙이 따로 있다(L2371~L2379). STEP 1에서는 쓰이지 않지만 실제 제품의 연계키 후보 탐지 규칙 초안으로 쓸 수 있다.
```js
// K 연계키 — 현재 편집 대상 파일명 기반 자동 감지 (하드코딩 아님)
const nm = d.name || '';
const rows = [];
if (/도로/.test(nm)) rows.push({ key: 'K5 도로링크ID', col: 'ROAD_LINK_ID (감지)', note: '표준: 국가표준노드링크 · 결합 후보 계산 대기' });
if (/도로|공간|경계|좌표/.test(nm)) rows.push({ key: 'K3 좌표', col: 'GEOM / X·Y (감지)', note: '좌표계 확인 필요 (EPSG 미선언)' });
if (/기상|관측|시간|5분|소통|기록/.test(nm)) rows.push({ key: 'K7 시각', col: 'OBSV_DT / 관측일시 (감지)', note: 'ISO 8601 정규화 대상' });
if (/차량|운행|eTAS|OBU/i.test(nm)) rows.push({ key: 'K6 차량ID', col: 'VHCL_NO (감지)', note: '표기 방식 검수 필요' });
if (/사고/.test(nm)) rows.push({ key: 'K2 주소', col: 'ACDNT_ADDR (감지)', note: '주소 → 좌표 지오코딩 후보' });
if (!rows.length) rows.push({ key: 'K9 문서ID', col: '(자동 감지 실패)', note: '수기 배정 필요 — 검수 큐 이동' });
```

### 4.10 AI 추천 조합 카드 고정값 (M336~M352)

| 항목 | 값 | 성격 |
|---|---|---|
| 카드 제목 | 업로드 기반 AI 추천 조합 | 정적 |
| 공유 축 칩 | K7 시각 | 정적 |
| 신뢰도 | 신뢰도 82% | 정적 |
| 근거 | 근거: 업로드 파일 시각 컬럼 패턴 → K7 정렬 후보 · 상세 프로파일 후 재산정 | 정적 |
| 상태 문구 | 포함 데이터셋 {n}건 · 결합 후보 계산 중 | n만 동적 |
| 항목 부제 | {유형} · K7 후보 | 유형만 동적 |
| 업로드 카드·리스트의 연계키 후보 | "연계키 후보: K7 시각 (컬럼명 패턴 매칭)" / "K7 시각 (패턴 매칭)" | 정적 |

조합 항목(`combo[]`) 구조: `{ n: 이름, k: 연계키 문자열, src?: 'ai'|'man', w?: 경고 여부, meta?: 메타 덮어쓰기 }`

### 4.11 프로세스 스냅숏 대상 키 `workKeys` (L920)
```js
const workKeys = ['combo', 'comboName', 'comboMeta', 'comboSel', 'upList', 'upFile', 'manSel', 'upView', 'ds3', 'ds3Done', 'ds3Fold', 'mainSel', 'clsSel', 'propSel', 'provSel', 'provRec', 'clsDone', 'propDone', 'provDone', 'dsExtra', 'linkSeq', 'linkKnown', 'ds', 'dsDone4', 'dist2', 'f1Sel', 'f2Sel', 'f3Sel', 'f4Sel', 'f5Sel', 'relPairs', 'dsGroups', 'fmts', 'convertState', 'step', 'tab3', 'gran', 'pipe', 'nodeEdits', 'reviewFlags'];
```
이 중 `upList`, `upFile`, `upView`는 `blank()`에서 보존된다(L924).

### 4.12 후보 데이터셋 레지스트리 `META_TABLE` / `MINT_MAP` (L106~L123)
STEP 1에서 고른 이름이 이후 단계에서 데이터셋인지 스트림인지, 소관 기관이 어디인지 판정되는 근거표다. 이름이 이 표에 없으면 kind 미상의 빈 메타로 취급된다.
```js
META_TABLE = {
  'sample_공간정보_통합포털_데이터셋_목록_도로': { kind: 'dataset', org: '국토교통부', orgId: 'https://catalog.molit.go.kr/id/org/ORG-1613000', form: '정형(엑셀)', mediaTypeIana: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', role: '도로 공간정보 — 사고 원인 분석 조합 베이스' },
  'cctv.vehicle.det.v1': { kind: 'stream', org: '경기도건설본부(데모)', orgId: 'https://catalog.molit.go.kr/id/org/ORG-6410000', form: '실시간 스트림(관측)', role: 'CCTV 차량 관측 — 과속·사고 판정 입력', temporalResolution: 'PT1S', eventTime: 'event_time' },
  'kma.aws.obs.v1': { kind: 'stream', org: '기상청(외부 출처)', orgId: 'https://catalog.molit.go.kr/id/org/ORG-1360000', form: '실시간 스트림(컨텍스트)', role: '기상 관측 — 조건부 기준값 판정 컨텍스트', temporalResolution: 'PT10M', eventTime: 'obs_time' },
  'sample_교통사고심층조사시스템_비정형_': { kind: 'dataset', org: '경찰청·도로교통공단(데모)', orgId: 'https://catalog.molit.go.kr/id/org/ORG-1320000', form: '정형(엑셀)', mediaTypeIana: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', role: '교통사고 심층조사 — 사고 원인·사상 정보' },
  'sample_데이터오픈마켓(30종)': { kind: 'dataset', org: '국토교통부', orgId: 'https://catalog.molit.go.kr/id/org/ORG-1613000', form: '정형(엑셀)', mediaTypeIana: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', role: '오픈마켓 30종 목록 — 사고심층조사 연관 그룹' },
  'sample_디지털운행기록분석시스템(eTAS)': { kind: 'dataset', org: '한국교통안전공단(데모)', orgId: 'https://catalog.molit.go.kr/id/org/ORG-B552016', form: '정형(엑셀)', mediaTypeIana: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', role: '차량 운행기록 — 차량 흐름 분석 입력' },
  'sample_실시간기상관측자료수집시스템_기상청_': { kind: 'dataset', org: '기상청(외부 출처)', orgId: 'https://catalog.molit.go.kr/id/org/ORG-1360000', form: '정형(엑셀)', mediaTypeIana: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', role: '기상 관측 수집 목록 — 협약 확인 필요' },
  '실시간교통사고': { kind: 'stream', org: '국토교통부(데모)', orgId: 'https://catalog.molit.go.kr/id/org/ORG-1613000', form: '실시간 스트림(관측)', temporalResolution: 'PT5M', eventTime: 'event_time', role: '실시간 교통사고 이벤트 — 관제 통보 입력' },
  '디지털운행기록분석시스템(eTAS)_정보시스템': { kind: 'dataset', org: '한국교통안전공단(데모)', orgId: 'https://catalog.molit.go.kr/id/org/ORG-B552016', form: '정형(엑셀)', mediaTypeIana: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', role: '차량 운행기록 분석 — 차량 흐름 분석 입력' }
};
MINT_MAP = {
  'kma.aws.obs.v1': 'SVC-000041',
  'cctv.vehicle.det.v1': 'SVC-000042',
  'sample_공간정보_통합포털_데이터셋_목록_도로': 'DST-000961',
  '실시간교통사고': 'SVC-000043',
  '디지털운행기록분석시스템(eTAS)_정보시스템': 'DST-000962'
};
```

| 필드 | 의미 |
|---|---|
| (키) | 후보 이름(확장자 제거 후의 `combo[].n`) |
| `kind` | `dataset` 또는 `stream` (스트림은 `dcat:Dataset` + `dcat:DataService`) |
| `org` / `orgId` | 생산 기관 표기와 기관 IRI |
| `form` | 형태 표기 |
| `mediaTypeIana` | IANA 미디어타입(파일형만) |
| `role` | 조합 내 역할 서술 |
| `temporalResolution` / `eventTime` | 스트림 전용 속성 |
| `MINT_MAP` 값 | 발행 모드에서 쓰는 확정 ID (`DST-…`, `SVC-…`) |

### 4.13 정의만 있고 화면에 연결되지 않은 후보 조합 (레거시, 시드 후보)
markup 어디에서도 참조되지 않지만 logic.js에 남아 있는 후보 데이터다.

| 핸들러 | comboName | 구성 |
|---|---|---|
| `loadComboRec1` (L2279) | 소통+돌발+기상 | TRAFFIC_LINK_5MIN (K5 · K7), ADMIN_SGG 행정경계 (K5), 돌발상황 이력 (UTIC) (K5 · K7), 기상관측 AWS 10분 (K7) |
| `loadComboRec2` (L2284) | 차량검사+OBU 텔레메트리 | etas_inspect_log (K6 · K7), obu.telemetry.v2 (K6 · K7, 경고 w) |
| `pickComboA` (L2289) | 도로링크+시각 | TRAFFIC_LINK_5MIN (K5 · K7), ADMIN_SGG 행정경계 (K5) |
| `pickComboB` (L2294) | 도로링크+차량+시각 | TRAFFIC_LINK_5MIN (K5 · K7), etas_inspect_log (K6 · K7), obu.telemetry.v2 (K6 · K7, 경고 w) |
| `addVds`~`addBis` (L664~L668) | (단건 추가) | VDS 검지기 5분 교통량 (K5 · K7), 돌발상황 이력 (UTIC) (K5 · K7), 기상관측 ASOS 시간자료 (K7), KTDB 여객 OD 조사 (K5), 버스 BIS 정류장 도착 (K6 · K7) |
| `pickManual` (L2272) | `이름들 + ' (작업자 선택)'` | 선택분 전부 `k: 'K7', src: 'man'` |

### 4.14 데모 스냅숏 중 STEP 1 관련 값 (`resources/f02defb4-…json`, `exportedAt` 2026-08-21T16:07:13.563Z)
`upList`:
```json
[
  {
    "name": "교통사고심층조사시스템(TAIS)_정보시스템.xlsx",
    "size": "20 KB",
    "type": "정형 (엑셀)",
    "profile": "스키마 자동추론 대기 · 20 KB 판독"
  },
  {
    "name": "교통혼잡_지역별_데이터.xlsx",
    "size": "19 KB",
    "type": "정형 (엑셀)",
    "profile": "스키마 자동추론 대기 · 19 KB 판독"
  },
  {
    "name": "도로_행정구역_공간정보.xlsx",
    "size": "17 KB",
    "type": "정형 (엑셀)",
    "profile": "스키마 자동추론 대기 · 17 KB 판독"
  },
  {
    "name": "디지털운행기록분석시스템(eTAS)_정보시스템.xlsx",
    "size": "323 KB",
    "type": "정형 (엑셀)",
    "profile": "스키마 자동추론 대기 · 323 KB 판독"
  },
  {
    "name": "실시간기상관측정보_자료수집시스템_기상청_.xlsx",
    "size": "17 KB",
    "type": "정형 (엑셀)",
    "profile": "스키마 자동추론 대기 · 17 KB 판독"
  }
]
```

`manSel`:
```json
{
  "cctv.vehicle.det.v1": true,
  "kma.aws.obs.v1": true,
  "syn.traffic.stream.v1": false,
  "obu_capture_sample": false,
  "kma_aws_sample": false,
  "실시간 교통사고 정보": false,
  "실시간교통사고": true,
  "obu.telemetry.v2": true,
  "TRAFFIC_LINK_5MIN": true,
  "교통사고심층조사시스템(TAIS)_정보시스템.xlsx": true,
  "교통혼잡_지역별_데이터.xlsx": true,
  "실시간기상관측정보_자료수집시스템_기상청_.xlsx": true,
  "디지털운행기록분석시스템(eTAS)_정보시스템.xlsx": true,
  "도로_행정구역_공간정보.xlsx": true
}
```

`synStreams`, `strmDemoHide`, `upView`, `comboSel`, `comboName`, `procName`:
```json
{
  "synStreams": [
    {
      "name": "실시간교통사고",
      "type": "관측",
      "rate": "수기 등록",
      "at": "22:55"
    }
  ],
  "strmDemoHide": false,
  "upView": "card",
  "comboSel": "up",
  "comboName": "실시간교통사고(스트림)",
  "procName": "실시간교통사고(스트림)"
}
```

`combo`와 `comboMeta`:
```json
{
  "combo": [
    {
      "n": "실시간교통사고",
      "k": "K6 · K7 · K5 · K3"
    },
    {
      "n": "디지털운행기록분석시스템(eTAS)_정보시스템",
      "k": "K7"
    }
  ],
  "comboMeta": {
    "title": "실시간교통사고(스트림)",
    "ai": false,
    "done": true,
    "desc": "실시간교통사고(스트림) 데이터와 교통사고 원인분석 데이터의 모음",
    "at": "23:31"
  }
}
```

`procList` (스냅숏 본문 제외 요약):
```json
[
  {
    "id": 1787327557588,
    "name": "실시간교통사고(스트림)",
    "savedAt": "08-21 15:52",
    "step": 7,
    "ver": 2,
    "count": 2,
    "done": true,
    "snapshotKeys": [
      "clsDone",
      "clsSel",
      "combo",
      "comboMeta",
      "comboName",
      "comboSel",
      "convertState",
      "ds",
      "ds3",
      "ds3Done",
      "dsDone4",
      "dsExtra",
      "f1Sel",
      "f2Sel",
      "f3Sel",
      "f4Sel",
      "f5Sel",
      "fmts",
      "gran",
      "linkSeq",
      "mainSel",
      "manSel",
      "pipe",
      "propDone",
      "propSel",
      "provDone",
      "provSel",
      "relPairs",
      "step",
      "tab3",
      "upFile",
      "upList",
      "upView"
    ],
    "snapshot.combo": [
      {
        "n": "실시간교통사고",
        "k": "K6 · K7 · K5 · K3"
      },
      {
        "n": "디지털운행기록분석시스템(eTAS)_정보시스템",
        "k": "K7"
      }
    ]
  }
]
```

### 4.15 AI 어시스턴트 데이터
컨텍스트 라벨(L2997):
```js
const ctxLabels = { step1: 'STEP 1', step2: 'STEP 2', step3: 'STEP 3', step4: 'STEP 4', step5: 'STEP 5', step6: 'STEP 6', step7: 'STEP 7', step8: 'STEP 8', home: '대시보드 홈', assets: '데이터 패브릭 관리', catalog: '데이터 카탈로그', queue: '검수 큐', admin: '시스템 관리' };
```

컨텍스트별 추천 질문(L3031~L3045):
```js
const suggMap = {
  step1: ['업로드하면 데이터가 이동하나요?', '신뢰도 %는 어떻게 산출되나요?', '연계키 K1~K9는 뭔가요?'],
  step2: ['조합에서 데이터셋을 빼면 어떻게 되나요?', '연계키 K1~K9는 뭔가요?', '스튜디오 사용 순서를 알려주세요'],
  step3: ['dcat:Dataset과 dcat:Distribution의 차이는?', 'DCAT 3.0에서 추가된 것은?', '필수·권장·선택 항목의 기준은?', '프로버넌스는 왜 기록하나요?'],
  step4: ['F축과 K축의 차이는?', '미분류는 어떻게 처리하나요?', '연계키 K1~K9는 뭔가요?'],
  step5: ['LPG 투영이 뭔가요?', '엣지 15종은 어디서 오나요?', 'SHACL 검증은 어떻게 동작하나요?'],
  step6: ['왜 정본이 Turtle인가요?', 'sLLM이 Turtle을 직접 읽거나 쓰나요?', 'JSON-LD가 있는데 왜 Turtle도 쓰나요?'],
  step7: ['Violation이 있으면 발행이 전부 막히나요?', 'sLLM이 Turtle을 직접 읽거나 쓰나요?', '배치 재검증은 누가 실행 주체인가요?'],
  step8: ['35항목 자동판정의 의미는?', '점수를 올리려면 뭐부터 하나요?'],
  home: ['스튜디오 사용 순서를 알려주세요', 'Turtle은 AI에 어떻게 활용되나요?', 'prov:Activity가 뭔가요?'],
  assets: ['AI가 어떤 데이터로 학습했는지 추적할 수 있나요?', '개방구역과 통제구역의 차이는?', '미등록 항목은 왜 문제인가요?'],
  catalog: ['카탈로그 상세에서 뭘 볼 수 있나요?', '왜 정본이 Turtle인가요?', 'DCAT 3.0에서 추가된 것은?'],
  queue: ['검수 큐에는 뭐가 쌓이나요?', '미분류는 어떻게 처리하나요?'],
  admin: ['권한 체계는 어떻게 되나요?', '배치 재검증은 누가 실행 주체인가요?', 'sLLM이 Turtle을 직접 쓰나요?']
};
```

질문·답변 사전(L2998~L3030, 31건, 답변의 `\n`은 줄바꿈):
```js
const A = {
  'dcat:Dataset과 dcat:Distribution의 차이는?': 'dcat:Dataset은 데이터셋 "정본"의 개념적 기술 단위이고, dcat:Distribution은 그 데이터셋의 구체적 배포 형태(포맷·접근URL)입니다.\n예: 교통링크 5분 소통정보(Dataset) 1건이 Parquet 배포본·CSV 배포본(Distribution) 2건을 가질 수 있습니다. 연결은 dcat:distribution 프러퍼티로 합니다.',
  'DCAT 3.0에서 추가된 것은?': '이 스튜디오에서 쓰는 3.0 핵심 추가분은 ① dcat:DatasetSeries(연도별·버전별 시리즈 묶음) ② dcat:inSeries(시리즈 소속) ③ dcat:version(버전 표기 표준화)입니다.\nSTEP 3 ② 프러퍼티 폼에서 [3.0] 배지가 붙은 항목이 해당됩니다. owl:versionInfo는 가이드라인 표기용으로 병기합니다.',
  'prov:Activity가 뭔가요?': 'PROV-O의 활동 단위입니다. "무엇이(Entity) 어떤 활동으로(Activity) 누구에 의해(Agent) 생성·변경되었나"를 기록합니다.\n이 스튜디오에서는 단계 확정·발행 승인·배치 실행 등 모든 행위가 실행 시점에 prov:Activity로 계측됩니다 — 화면 하단 [다음 (확정)]을 누르면 토스트로 기록 ID가 표시됩니다.',
  'SHACL 검증은 어떻게 동작하나요?': 'SHACL은 RDF 그래프가 지켜야 할 형태(Shape)를 선언하고 기계 판정하는 W3C 표준입니다.\n이 시스템은 DatasetShape·DistributionShape 등으로 필수 항목·통제어휘(66코드)·가이드라인 항목을 검증하며, 결과는 통과/Warning/Violation 3단계입니다. Violation이 있는 데이터셋만 발행 보류됩니다(데이터셋 단위 게이트).',
  '연계키 K1~K9는 뭔가요?': 'K축은 "이 데이터가 무엇과 조인되는가"를 나타내는 연계키 분류입니다 (예: K5 도로링크 · K6 차량 · K7 시각).\n컬럼 메타데이터에서 규칙으로 도출되는 확인 사항이며 sLLM 추론 대상이 아닙니다 — 추론 대상은 주제 분류인 F축(F1~F6)입니다.',
  '업로드하면 데이터가 이동하나요?': '아니요. Parquet는 푸터 수 KB만 판독해 스키마·식별자를 추출하고, 데이터 본체는 레이크에서 이동하지 않습니다.\n메타 평면과 데이터 평면은 푸터 식별자·spdx:checksum 대조(접합부 계약)로만 연결됩니다 — STEP 6에서 점검할 수 있습니다.',
  '신뢰도 %는 어떻게 산출되나요?': '연계키 컬럼 매칭율·시각 정렬 일치율 등 규칙 기반 산출값이며, 각 조합 카드 아래 근거 1줄이 함께 표시됩니다.\n예: 88% 조합은 K6 차량ID 표기 불일치(CarID vs OBU_IDNT_NMBR)로 −6%p 감점 — STEP 2 경고 1번과 동일 건입니다.',
  '조합에서 데이터셋을 빼면 어떻게 되나요?': '[제거]를 누르면 내 작업 조합에서 빠지고, 확정 시점의 조합 구성이 Classification Activity로 기록됩니다.\n빠진 데이터셋은 AI 제안 목록·데이터 풀에 그대로 남아 다시 드래그하거나 [+ 추가]로 되돌릴 수 있습니다.',
  '필수·권장·선택 항목의 기준은?': '필수는 SHACL Violation(발행 차단), 권장은 Warning(발행 가능하나 감점), 선택은 검증 대상 아님입니다.\n행안부 가이드라인 표9~12의 메타데이터 항목 구분을 따르며, 우측 SHACL 검증 결과에서 [폼 필드로 이동]으로 바로 수정할 수 있습니다.',
  '프로버넌스는 왜 기록하나요?': '재현성과 책임 추적을 위해서입니다. 판정 기준: "재현에 필요하면 PROV, 소비에 필요하면 마트".\n생애주기 7단계 각 활동이 Agent(책임 조직/담당자)·입출력·파라미터와 함께 기록되어, 산출물이 어떤 경로로 만들어졌는지 역추적할 수 있습니다.',
  'F축과 K축의 차이는?': 'F축(F1~F6)은 "무엇에 관한 데이터인가"(주제·유형·조건), K축(K1~K9)은 "무엇과 조인되는가"(연계키)로 독립 축입니다.\nK축은 컬럼 메타데이터에서 규칙으로 확인되고, F축은 ko-e5-large 유사도로 후보 축소 후 sLLM 재순위화 2단계로 프리필됩니다 — 추론분은 반드시 검수하세요.',
  '미분류는 어떻게 처리하나요?': '필수 축(F1·F2·F4·F6·K)이 비어 있으면 미분류로 검수 큐에 집계됩니다.\n우측 상단 검수 큐 배지에서 [→ 보기]로 이동해 처리하며, 분류 확정도 prov:Activity로 기록됩니다.',
  'LPG 투영이 뭔가요?': 'RDF 정본(Turtle)을 Neo4j 등 속성 그래프(Labeled Property Graph)로 변환하는 것입니다.\n노드 18종(Dataset·Activity·Agent·JoinKey…)·엣지 15종(WAS_DERIVED_FROM 등)으로 투영되어 리니지 체인을 시각 탐색할 수 있습니다. 정본은 어디까지나 Turtle이고 LPG는 파생 표현입니다.',
  '엣지 15종은 어디서 오나요?': 'PROV-O 관계(wasDerivedFrom·wasGeneratedBy·used·wasAttributedTo·wasInformedBy 등)를 LPG 엣지로 매핑한 것입니다.\n각 엣지에는 confidence·ruleSetVersion·executedAt 같은 속성이 붙습니다 — 노드를 클릭하면 우측 상세에서 확인할 수 있습니다.',
  'JSON-LD와 RDF는 다른 건가요?': '아닙니다. JSON-LD는 RDF의 직렬화 문법 중 하나입니다 — RDF vs JSON의 양자택일이 아닙니다.\n하나의 카탈로그 정본을 용도별 4개 표현(Turtle 정본 · JSON-LD API용 · 자연어 문장화 · 순수 JSON+스키마)으로 직렬화합니다.',
  'sLLM이 Turtle을 직접 쓰나요?': '아니요. 원칙상 sLLM은 RDF를 직접 생성하지 않습니다.\nsLLM은 스키마 제약 JSON만 출력하고, 결정적 후처리로 Turtle로 변환합니다. 자연어 문장화도 생성 모델이 아닌 템플릿 규칙으로 처리해 4-포맷 등가성을 보존합니다.',
  'Violation이 있으면 발행이 전부 막히나요?': '아니요. 발행 게이트는 데이터셋 단위입니다.\nViolation이 있는 데이터셋(52건)만 개별 보류되고, SHACL 통과분 1,842건은 [통과분 발행 승인]으로 일괄 발행됩니다. 보류분은 위반 해소 후 재검증 시 다음 발행 배치에 합류합니다.',
  '배치 재검증은 누가 실행 주체인가요?': '배치 런타임은 소프트웨어 주체입니다 — prov:SoftwareAgent(batch-revalidator)로 모델링되고, 승인한 관리자가 prov:actedOnBehalfOf로 연결됩니다.\n대화형 런타임(STEP 1~8 화면 조작)은 사람 주체(prov:Person)로, 두 런타임이 프로버넌스 레벨에서 구분됩니다.',
  '35항목 자동판정의 의미는?': '가이드라인 80항목 중 35항목은 SHACL Shape로 기계 판정됩니다 — STEP 6 ③ 가이드라인 대조와 동일 엔진입니다.\n[재진단 실행]은 이 35항목만 즉시 재계산하고, 수기 45항목은 담당자 최근 확인값을 유지합니다.',
  '점수를 올리려면 뭐부터 하나요?': '조치 우선순위 로드맵의 순위 1~4(rai:dataBiases · 데이터 카드 · 라이선스 확정 · ISO 8601 정규화)가 난이도 낮음~중간이면서 +12점입니다.\n완료 시 38.5점 → 50.5점(63%)으로, 신규 시스템 없이 도달 가능합니다.',
  '개방구역과 통제구역의 차이는?': '통제구역은 정본이 사는 곳, 개방구역은 필터링된 투영본만 단방향 push(◀)되는 곳입니다.\n역방향 연결은 없으며, 샘플 레코드·프로파일 통계는 개방 불가 항목입니다. 레이크 행은 push 없이 대조만 합니다.',
  '미등록 항목은 왜 문제인가요?': '마트 산출물(임베딩 인덱스·학습셋)이 dcat:Dataset으로 등록되지 않으면 리니지가 마트 경계에서 끊깁니다.\n해당 셀에서 [dcat:Dataset 등록]·[prov:Activity 소급 기록]으로 처리할 수 있습니다.',
  '카탈로그 상세에서 뭘 볼 수 있나요?': '보유기관·개방 시스템·데이터 정보(라이선스·갱신주기 PT5M)·배포본·N2SF 등급을 확인할 수 있습니다.\n목록에서 제목을 클릭하면 상세로 들어가고, 메타 데이터 섹션에서 Turtle·JSON-LD 표현으로 이동할 수 있습니다.',
  '검수 큐에는 뭐가 쌓이나요?': '미분류(필수 축 미배정)·SHACL 위반·sLLM 제안 승인 대기가 쌓입니다.\n처리(분류 확정·승인·반려) 시마다 prov:Activity가 기록되고, 완료되면 해당 STEP의 배지 카운트가 줄어듭니다.',
  '권한 체계는 어떻게 되나요?': '조회 → 담당자(검수) → 관리자 3단계이며 권한 상승은 관리자 승인이 필수입니다.\n단계별 담당(정/부)은 시스템 관리 > 사용자 관리 > 담당 단계 배정에서 설정하고, 단계 확정 시 다음 STEP 담당자에게 알림이 갑니다.',
  '스튜디오 사용 순서를 알려주세요': 'STEP 1 업로드·조합 제안 → 2 조합 확정 → 3 DCAT/PROV-O 작성 → 4 다중분류 → 5 매핑·리니지 → 6 검증(게이트 0 + SHACL) → 7 직렬화·포맷 변환(+파생 자가검증) → 8 발행·준수 진단 순서입니다.\n검증(6)이 직렬화(7)보다 앞에 있어 검증 미통과 데이터는 파일로 존재하지 않습니다. 각 단계 확정마다 prov:Activity가 기록되며, 완료 조건을 채우지 못한 단계는 잠깁니다.',
  '왜 정본이 Turtle인가요?': '세 가지 이유입니다. ① 사람 가독성 — 접두어·세미콜론 축약으로 트리플을 문장처럼 읽을 수 있어 검수·diff·미리보기에 가장 적합합니다. ② 분량 — RDF 직렬화 중 가장 경제적입니다 (JSON-LD 2.13배 대비 1.00배 기준점). ③ 생태계 — SHACL Shape 정의와 SPARQL 질의의 사실상 표준 교환 문법이라, 검증 게이트(STEP 6)가 buildTriples 그래프 위에서 직접 동작합니다.\n"무엇이 진실인가"를 물었을 때 최종적으로 가리키는 파일이 Turtle이고, JSON-LD·LPG·문장화는 전부 여기서 단방향 파생됩니다.',
  'sLLM이 Turtle을 직접 읽거나 쓰나요?': '둘 다 아닙니다. 읽기: sLLM에는 Turtle이 아니라 템플릿으로 문장화한 자연어(Turtle 대비 0.57배 토큰)를 입력합니다 — LLM은 RDF 문법보다 자연어를 훨씬 잘 소화하고, 변환이 결정적이라 답변의 근거 트리플을 역참조할 수 있습니다.\n쓰기: sLLM은 스키마 제약된 JSON만 산출하고, 결정적 후처리가 Turtle로 변환한 뒤 SHACL 검증과 사람 승인을 거쳐야 정본에 병합됩니다. 정본의 문법적 무결성을 확률 모델에 맡기지 않는 4중 방어입니다.',
  'JSON-LD가 있는데 왜 Turtle도 쓰나요?': '경쟁 관계가 아닙니다 — 둘 다 같은 RDF 그래프의 직렬화 문법이고, 용도가 다를 뿐입니다. JSON-LD는 @context 기반 기계 간 교환에 적합해 API 계층(외부 시스템 · MCP 에이전트)을 담당하고, Turtle은 정본 저장·SHACL 검증·사람 검수를 담당합니다.\n하나의 카탈로그가 Turtle(정본) · JSON-LD(API) · Parquet 푸터(접합부) · 문장화(sLLM)의 4개 표현으로 직렬화됩니다 — STEP 7에서 변환 대상을 확인할 수 있습니다.',
  'Turtle은 AI에 어떻게 활용되나요?': '세 방향입니다. ① 입력 — Turtle 정본을 문장화해 임베딩하면 벡터DB①(메타데이터 탐색)이 됩니다. ② 출력 — sLLM 보정 제안이 JSON → Turtle 변환 → SHACL → 사람 승인 경로로 정본에 도달합니다. ③ 거버넌스 — 학습셋 리니지(prov:wasDerivedFrom) · 편향 명세(rai:dataBiases) · 모델 하이퍼파라미터가 전부 Turtle 정본에 기록됩니다.\n요약하면 Turtle은 AI 입력의 원천, AI 출력의 판정 기준, AI 자산의 장부입니다 — STEP 7의 활용 경로 카드에서 도식으로 확인할 수 있습니다.',
  'AI가 어떤 데이터로 학습했는지 추적할 수 있나요?': '예 — 그것이 학습셋을 dcat:Dataset으로 등록하는 이유입니다. 학습셋은 prov:wasDerivedFrom으로 원천에, 추출 규칙은 prov:Activity에 연결되어 "이 모델은 무슨 데이터로 학습했나"가 Turtle 그래프 질의로 답해집니다.\n미등록 학습셋(자산 매트릭스 마트 셀의 \'미등록 2\')은 이 추적이 끊긴 상태라 등록을 요구하며, 등록 시 rai:dataBiases(편향 명세) 작성 대상이 됩니다 — 가이드라인 v1.1 조치 로드맵 1위 항목입니다.'
};
```

사전에 없는 질문의 대체 답변(L3047):
```js
const a = A[q] || '좋은 질문입니다. 데모 목업에서는 대표 질문에 준비된 답변만 제공됩니다 — 아래 추천 질문을 눌러보시거나, 실서비스에서는 sLLM-molit-7b가 표준 문서 RAG(벡터DB①)로 답변합니다.\n관련 표준: DCAT 2.0/3.0 (W3C) · PROV-O · SHACL · 행안부 가이드라인 v1.1';
```

### 4.16 활동 로그·ID 형식

| 항목 | 형식 | 근거 |
|---|---|---|
| 토스트용 임시 ID | `ACT-K-0400` ~ `ACT-K-0498` 난수 | L47 |
| 활동 로그 ID | `ACT-K-0421`부터 1씩 증가 (`actSeq` 초기 420) | L53~L61, L142 |
| 플레이스홀더 ID | `ACT-DEL-신규`, `ACT-PRC-신규`, `ACT-STR-신규`, `ACT-CMB-신규` → 저장 시 시퀀스 ID로 치환 | L56~L58 |
| 로그 행 | `{ t: 'HH:MM', who: '홍길동 (나)' 또는 '시스템', txt, actId }`, 최근 10건 유지 | L59 |

---

## 5. 상태 변수

"영속" 열: D = localStorage 초안(`fde-studio-draft`)에 저장, P = 프로세스 스냅숏(`workKeys`)에 포함, 빈칸 = 휘발성.

### 5.1 셸

| 키 | 타입 | 의미 | 영속 |
|---|---|---|---|
| `authed` | boolean \| undefined | 로그인 여부. undefined면 sessionStorage로 판정 | D |
| `loginId`, `loginPw` | string | 로그인 입력값. 성공 시 `loginPw`는 비움 | D |
| `loginErr` | boolean | 로그인 실패 표시 | D |
| `plane` | 'home' \| 'studio' \| 'assets' \| 'catalog' \| 'queue' \| 'admin' | 현재 평면 | D |
| `step` | 1~8 | 스튜디오 현재 단계 | D, P |
| `trail` | string[] | 방문 평면 경로(중복 없음, 방문 순) | D |
| `my` | boolean | 사용자 팝오버 열림 | D |
| `saveTime` | 'HH:MM' | 마지막 저장 시각(헤더 표기) | D |
| `savedHere` | boolean | 현재 화면에서 임시저장했는지(버튼 강조) | |
| `toast` | boolean | 토스트 표시 플래그 | |
| `toastText` | string \| null | 토스트 문구. null이면 `toastId` 기본 문구 | |
| `toastId` | string | `showToast()`가 만든 임시 활동 ID | D |
| `notify` | `{ from, to, owner }` \| null | 다음 단계 담당자 알림 팝업 내용 | |
| `fixBack` | `{ shape, step }` \| null | STEP 6 위반 수정 왕복 중 표시 | |
| `actLog` | `{ t, who, txt, actId }[]` | 최근 활동 10건 | D |
| `actSeq` | number | 활동 ID 시퀀스(초기 420) | D |
| `wipeAsk` | boolean | "데모 데이터 지우기" 2단계 확인 중 | D |
| `ast` | boolean | 어시스턴트 패널 열림 | |
| `astW` | boolean | 어시스턴트 패널 넓힘 | |
| `astChat` | `{ q, a }[]` | 대화 이력 | |
| `astInput` | string | 입력 중 텍스트 | |
| `stepVer` | 2 | 스냅숏 단계 번호 체계 버전(6=검증, 7=직렬화) | D |
| `restored` | boolean | 초안에서 복원되었음 | |
| `catDetail`, `admTab`, `fabTab`, `cell`, `pipe`, `tab3`, `fixGuide` | 다양 | 셸의 링크가 이동하면서 함께 설정하는 다른 화면의 뷰 상태 | D |

props: `violationCount`(number, 기본 0). 헤더 "위반 n" 배지에만 쓰인다.

### 5.2 STEP 1

| 키 | 타입 | 의미 | 영속 |
|---|---|---|---|
| `upList` | `{ name, size, type, profile }[]` | 업로드 파일 풀(마지막 업로드 묶음). 프로세스 간 공유 | D, P |
| `upFile` | 같은 구조 \| null | 대표 파일(마지막 항목). 있으면 `upOn`, 없으면 `upEmpty` | D, P |
| `upView` | 'card' \| 'list' (기본 'card') | 후보 보기 방식 | D, P |
| `upClearAsk` | boolean | "업로드 선택 삭제" 2단계 확인 중 | D |
| `manSel` | `{ [후보키]: boolean }` | 후보 선택 상태. 키는 업로드 파일명(확장자 포함), 스트림 이름, 묶음 이름, 묶음 구성원 이름 | D, P |
| `synStreams` | 4.7절 구조의 배열 | 스트림 관리에서 유입된 합성 캡처 묶음. STEP 1에서는 읽기만 한다 | D |
| `strmDemoHide` | boolean \| undefined (기본 true로 간주) | 데모 스트림 숨김 여부 | D |
| `combo` | `{ n, k, src?, w?, meta? }[]` | 내 작업 조합 | D, P |
| `comboSel` | 'up' \| 'man' \| undefined | 조합의 출처('up' = AI 추천 채택) | D, P |
| `comboName` | string | 조합 이름(채택 시 이름 연결 60자) | D, P |
| `comboMeta` | `{ title, desc, ai, done, at }` | STEP 2에서 확정. STEP 1은 삭제로 조합이 비면 지운다 | D, P |
| `ds3`, `ds3Done`, `tab3` | number, object \| null, number | 조합 채택 시 STEP 3 진행 위치 초기화(0, null, 1) | D, P |
| `procName` | string | 고정된 현재 프로세스명 | D |
| `procList` | 3.7절 항목 구조의 배열 | 저장된 프로세스 목록 | D |
| `procTrash` | 같은 구조의 배열 | 휴지통(카탈로그 화면에서 관리, STEP 1은 초기화만) | D |
| `procOpen` | boolean | 프로세스 목록 펼침 | D |
| `procAsk` | string \| null | 새 프로세스 확인 모달. 값은 대기 중인 후보 키 | D |
| `procViewSel` | `{ [프로세스명]: boolean }` | 목록에서 체크한 프로세스(미리보기용) | D |
| `convertState` | null \| 'run' \| 'done' | STEP 7 변환 상태. 가드가 읽는다 | D, P |

인스턴스 필드(상태 아님): `_tt`(토스트 타이머), `_ps`(자동 저장 디바운스), `_nt`(알림 타이머), `_wa`(지우기 확인 타이머), `_procGuard`, `_saveProc`, `_procSave`, `_blankWork`.

---

## 6. 시뮬레이션 vs 실제 계산

### 6.1 목업이 꾸며낸 것 (서버·AI·실데이터 없음)

| 영역 | 꾸민 내용 | 근거 |
|---|---|---|
| 인증 | 계정 `admin`/`9876` 하드코딩, 세션은 sessionStorage 플래그 | L360~L362 |
| 사용자·조직 | 홍길동, 이순신, 변학도, 조직명, 이메일, 담당 단계 칩, MY TASK 4건, 최근 알림 3건, 배지 숫자 4 | M55~M94, L1682~L1683 |
| 헤더 지표 | "SHACL 통과 0"은 고정 문자열, "위반 n"은 편집기 prop | M52~M53, L375 |
| 유형 자동판별 | 확장자 3분기뿐. "규칙엔진 유형판별 · 프로파일 자동추출 완료" 문구는 고정 | L2234~L2235, M323 |
| 프로파일 | xlsx·xls·parquet는 내용을 읽지 않고 "스키마 자동추론 대기 · {크기} 판독"만 표기. Parquet 푸터 판독 주석도 문구뿐 | L2237, M329 |
| 연계키 후보 | 모든 업로드 파일에 "K7 시각" 고정. 스트림 2건만 별도 고정값 | M267, M323, L2254 |
| AI 추천 | 모든 업로드 카드에 "AI 추천" 배지 고정. 추천 조합은 선택한 파일의 나열이며 탐색·순위화 없음 | M264, M319, L2126 |
| 신뢰도·근거 | "신뢰도 82%"와 근거 문장 고정. "결합 후보 계산 중"도 고정 | M347~M350 |
| 외부 소스 연계 | 5행과 상태 배지 전부 정적. "연결" 버튼 무동작 | M219~M240 |
| 데모 스트림 | 처리량, 모델 버전, 기상 수치 등 전부 정적 | M278~M295 |
| 묶음 구성원 | 어떤 캡처 파일이든 같은 4개 구성원을 표시 | L1120~L1125, L1211 |
| prov:Activity 기록 | 토스트의 ID는 난수이고 `actLog` 시퀀스와 무관. 업로드·조합 채택·단계 확정은 `actLog`에도 남지 않는다 | L46~L51 |
| 담당자 알림 | 팝업만 띄움. 수신자·채널 칩 고정, 24시간 재발송·전자결재 문구는 서술뿐 | L2987~L2993, M3894~M3908 |
| 어시스턴트 | 31개 고정 문답의 문자열 일치 조회. sLLM·RAG 호출 없음. "대화도 prov:Activity로 기록됩니다"도 문구뿐 | L2998~L3049 |
| 레이크 적재 요청 | 다른 화면으로 이동만 함 | L2570 |
| 저장소 | 모든 작업 상태가 브라우저 localStorage 한 키에 저장. 업로드 파일 본문은 보관하지 않음 | L101~L103 |
| 데모 복구 | 번들된 JSON 스냅숏으로 state 전체를 덮어씀 | L995~L1005 |

### 6.2 목업이 실제로 계산하는 것

| 영역 | 실제 계산 | 근거 |
|---|---|---|
| CSV 프로파일 | 앞 256KB를 읽어 컬럼 수(첫 줄 쉼표 분리)와 행 수(비어 있지 않은 줄 − 1) 산출 | L2239~L2248 |
| 파일 가드 | 50MB 초과와 금지 확장자 차단 | L2217 |
| 크기 표기 | KB/MB 환산 | L2236 |
| 선택 집계 | `manSel` 기반 선택 수, 업로드 수, 조합 포함 수 | L2117~L2118, L2161, L2268 |
| 조합 구성 | 선택 키 → `combo` 항목 변환(확장자 제거, `kOf` 규칙), 이름 60자 절단 | L2252~L2260 |
| 단계 게이트 | `stepGate` 상태기계와 `go()` 중앙 거부 | L4~L15, L324~L342 |
| 프로세스 | 이름 산정, 스냅숏 저장·복원, 새 프로세스 가드, 체크한 프로세스의 데이터셋 미리보기 | L918~L1109 |
| 삭제 연쇄 | 업로드 삭제 시 `manSel`, `combo`, 조합 메타 동시 정리 | L2140~L2157 |
| 활동 로그 | `actLog` 시퀀스 ID 발급과 10건 유지(STEP 1에서는 업로드 선택 삭제만 기록) | L53~L61, L2155 |
| 초안 | localStorage 저장·복원, JSON 내보내기·가져오기, 구버전 단계 번호 마이그레이션 | L62~L103, L3078~L3106 |
| 이동 경로 | 방문 평면 누적과 제거 | L21~L27, L1713~L1735 |

---

## 7. 실제 제품에서 필요한 기능

### 7.1 백엔드 기능
1. **인증·권한**: 계정/SSO 로그인, 세션 또는 JWT, 로그아웃, 역할 3단계(조회 / 담당자(검수) / 관리자), 단계별 정·부 담당 배정 조회. 확정 권한은 관리자 또는 해당 단계 담당자로 제한.
2. **파일 업로드**: 멀티파트 다중 업로드, 용량·확장자 정책 검사(목업 기준 50MB, 스트림성 확장자 거부), 객체 저장소 보관, 체크섬(SHA-256) 산출, 같은 프로세스 내 중복 처리, 누적 업로드(목업의 교체 동작은 결함으로 본다).
3. **스키마 프로파일링(비동기 작업)**
   - xlsx/xls: 시트 목록, 헤더 행 탐지, 컬럼명·추정 타입, 행 수, 결측률, 고유값 수, 샘플 값 (openpyxl 또는 pandas)
   - csv: 인코딩(UTF-8/CP949) 감지, 구분자 감지, 인용부호 처리, 전체 행 수
   - parquet: 푸터 메타데이터만 판독(pyarrow `read_metadata`), 스키마·행 수·row group·키값 메타데이터(식별자, 활동 ID)
   - 작업 상태(대기/실행/완료/실패)와 진행률 조회
4. **유형 판별 규칙엔진**: 정형 / 반정형 / 비정형 / 실시간 스트림 4분류. 확장자와 내용 검사를 함께 쓰고 판별 근거를 저장.
5. **연계키(K1~K9) 후보 탐지**: 컬럼명 패턴, 값 패턴(ISO 8601 시각, 좌표 범위, 차량번호 형식, 도로링크 ID 형식 등), 표준 코드 대조. 후보마다 근거 컬럼과 점수를 저장. 목업 문구상 K축은 sLLM 추론 대상이 아니라 규칙 도출 대상이다(L3003).
6. **후보 레지스트리**: 업로드 파일, 스트림 관리에서 유입된 스트림, 스트림 묶음을 한 목록으로 제공. 프로세스별 선택 상태 저장.
7. **조합 제안 엔진**: 선택된 후보들이 공유하는 K축을 찾고, 신뢰도를 "연계키 컬럼 매칭율·시각 정렬 일치율 등 규칙 기반 산출값"(L3005)으로 계산해 근거 1줄과 함께 반환. 조합 후보가 여러 개면 순위화.
8. **조합 채택**: 제안 채택 또는 수동 구성으로 조합 초안 저장. 조합이 바뀌면 하류 단계 결과(검증·직렬화·진단)를 무효화하고 활동을 기록.
9. **워크플로 게이트**: 4.1절의 `stepGate` 규칙을 서버에서 판정하고 API 수준에서 강제. 프런트는 판정 결과만 표시.
10. **작업 프로세스**: 생성, 이름 부여, 저장(스냅숏), 불러오기, 완료 처리, 휴지통·복원·영구 삭제. 목업과 달리 검증·직렬화 결과까지 프로세스별로 격리.
11. **활동 기록(prov:Activity)**: 업로드, 프로파일, 선택 변경, 조합 채택, 삭제, 단계 확정, 알림 발송, 어시스턴트 대화를 서버 시퀀스 ID로 기록. PostgreSQL에 적재하고 필요 시 rdflib로 PROV-O 트리플로 직렬화.
12. **알림**: 단계 확정 시 다음 단계 정·부 담당자와 참조 관리자에게 시스템 알림·메일 발송, 미확인 24시간 재발송, 내 작업함(MY TASK)과 최근 알림 조회.
13. **외부 소스 커넥터 상태**: 공공데이터포털 API, MCP 서버, ECM, 데이터레이크(HDFS/S3·Kafka), 시스템 DB의 연결 상태·최근 동기화·오류 메시지 조회(관리는 시스템 관리 화면).
14. **초안 자동 저장과 스냅숏**: 서버 측 자동 저장, 스냅숏 내보내기·가져오기(스키마 버전과 검증 포함).
15. **어시스턴트**: 표준 문서 RAG 기반 질의응답(목업 문구상 sLLM-molit-7b + 벡터DB①), 화면 컨텍스트별 추천 질문, 대화 기록.
16. **레이크 적재 요청**: 업로드 파일을 데이터레이크 통제구역에 적재하도록 요청하는 워크플로(목업은 화면 이동만 함).
17. **헤더 집계**: 프로젝트의 SHACL 통과·위반 건수 실집계.

### 7.2 API 엔드포인트 초안 (`/api/v1`)

**인증·사용자**

| 메서드·경로 | 용도 |
|---|---|
| `POST /auth/login`, `POST /auth/logout` | 로그인·로그아웃 |
| `GET /me` | 사용자, 조직, 역할, 담당 단계(정/부) |
| `GET /me/tasks` | MY TASK 목록(제목, 부제, 마감 배지, 이동 대상) |
| `GET /me/notifications?limit=3` | 최근 알림 |
| `GET /projects/{projectId}/summary` | 프로젝트명, SHACL 통과·위반 건수, 마지막 저장 시각 |

**워크플로**

| 메서드·경로 | 용도 |
|---|---|
| `GET /workflow/steps` | 8단계 정의(번호, 라벨, 담당 조직) |
| `GET /processes/{pid}/gates` | 단계별 `{ n, done, canEnter, reason }` |
| `GET /workflow/steps/{n}/owners` | 담당 조직, 정·부 작업자, 관리자 |
| `POST /processes/{pid}/steps/{n}/confirm` | 단계 확정. 게이트 검사, 활동 기록, 다음 단계 담당자 알림. 응답에 `activityId`와 `notification` 포함 |

**프로세스**

| 메서드·경로 | 용도 |
|---|---|
| `GET /projects/{projectId}/processes` | 목록(이름, 저장 시각, 데이터셋 수, 현재 단계, 완료 여부) |
| `POST /projects/{projectId}/processes` | 새 프로세스 시작(선택 후보 초기값 전달 가능) |
| `GET /processes/{pid}` | 프로세스 전체 상태(불러오기) |
| `PATCH /processes/{pid}` | 이름 변경, 완료 처리 |
| `GET /processes/{pid}/datasets` | 조합 데이터셋 미리보기(이름, 연계키) |
| `DELETE /processes/{pid}`, `POST /processes/{pid}/restore` | 휴지통 이동·복원(카탈로그 화면에서 사용) |
| `PUT /processes/{pid}/draft` | 화면 상태 자동 저장 |
| `GET /processes/{pid}/export`, `POST /processes/import` | 스냅숏 내보내기·가져오기 |

**업로드·프로파일**

| 메서드·경로 | 용도 |
|---|---|
| `POST /processes/{pid}/uploads` | 다중 업로드(multipart). 정책 위반 파일은 항목별 거부 사유 반환. 응답 `202` + 업로드 ID·프로파일 작업 ID |
| `GET /processes/{pid}/uploads` | 업로드 목록과 프로파일 요약 |
| `GET /uploads/{uploadId}/profile` | 컬럼 단위 프로파일, 유형 판별 근거, 연계키 후보 |
| `GET /jobs/{jobId}` | 프로파일 작업 상태 |
| `DELETE /processes/{pid}/uploads` (본문 `{ ids: [] }`) | 선택 업로드 일괄 삭제. 조합·선택에서 연쇄 제거 후 영향 범위 반환 |
| `POST /uploads/{uploadId}/lake-ingest-requests` | 레이크 적재 요청 |

**후보·선택·조합**

| 메서드·경로 | 용도 |
|---|---|
| `GET /processes/{pid}/candidates` | 업로드 + 스트림 + 스트림 묶음 통합 후보 목록(유형, 프로파일 요약, 연계키 후보, 선택 여부, 추천 여부) |
| `PUT /processes/{pid}/candidates/{candidateId}/selection` | 선택·해제. 완료된 프로세스면 `409` + 새 프로세스 제안 |
| `GET /streams`, `GET /stream-bundles` | 스트림 관리에서 유입된 스트림과 묶음(구성원 포함) |
| `POST /processes/{pid}/combo-suggestions` | 현재 선택 기준 조합 제안 계산(공유 K축, 신뢰도, 근거) |
| `GET /processes/{pid}/combo-suggestions` | 최근 제안 조회 |
| `PUT /processes/{pid}/combo` | 조합 채택·교체(`suggestionId` 또는 항목 목록). 하류 무효화 결과 반환 |
| `GET /join-keys` | K1~K9 코드표 |
| `GET /connectors` | 외부 소스 연계 상태 목록 |

**활동·어시스턴트**

| 메서드·경로 | 용도 |
|---|---|
| `GET /activities?processId=&limit=` | 활동 로그 |
| `GET /assistant/suggestions?context=step1` | 컨텍스트별 추천 질문 |
| `POST /assistant/messages` | 질문 전송(`context`, `question`) → 답변(근거 문서 포함) |
| `DELETE /assistant/conversations/{id}` | 대화 지우기 |

### 7.3 데이터 모델 초안 (PostgreSQL)

| 엔터티 | 주요 필드 |
|---|---|
| `organization` | id, name, iri |
| `app_user` | id, login_id, password_hash, name, email, org_id, role(view/worker/admin) |
| `step_assignment` | step_no, user_id, kind(main/sub/admin) |
| `workflow_step` | step_no, label, owner_org_id |
| `project` | id, name |
| `process` | id, project_id, name, current_step, status(active/done/trashed), saved_at, created_by |
| `process_draft` | process_id, ui_state(jsonb), schema_version, saved_at |
| `upload_file` | id, process_id(또는 project 공유 풀), original_name, ext, size_bytes, sha256, storage_uri, media_type_iana, uploaded_by, uploaded_at |
| `profile_job` | id, upload_id, status, started_at, finished_at, error |
| `dataset_profile` | upload_id, data_form(정형/반정형/비정형/스트림), form_reason, row_count, column_count, sheet_name |
| `column_profile` | profile_id, ordinal, name, inferred_type, null_ratio, distinct_count, sample_values(jsonb) |
| `join_key_code` | code(K1~K9), name |
| `candidate` | id, process_id, kind(upload/stream/bundle), ref_id, display_name |
| `candidate_join_key` | candidate_id, code, source_column, method(rule/pattern/manual), score |
| `candidate_selection` | process_id, candidate_id, selected, selected_by, selected_at |
| `stream` | id, name, role(관측/컨텍스트), temporal_resolution, event_time_column, timezone, watermark, late_policy, throughput, zone(통제/개방), source_org_id |
| `stream_bundle`, `stream_bundle_member` | 묶음 이름·유형·유입 시각, 구성 스트림과 연계키 |
| `connector` | id, name, kind(api/mcp/ecm/lake/db), endpoint, status, last_sync_at, last_error |
| `combo_suggestion` | id, process_id, shared_keys(text[]), confidence, rationale, created_at |
| `combo_suggestion_item` | suggestion_id, candidate_id |
| `combo` | process_id, name, source(ai/manual), title, description, confirmed_at |
| `combo_item` | combo_id, candidate_id, join_keys(text[]), warning, ordinal |
| `dataset_registry` | name, kind(dataset/stream), org_id, form, media_type_iana, role, temporal_resolution, event_time_column, minted_id (목업 `META_TABLE`·`MINT_MAP` 시드) |
| `prov_activity` | id(시퀀스 기반 `ACT-…`), process_id, type, agent_user_id, summary, started_at, ended_at, params(jsonb) |
| `notification` | id, activity_id, recipient_user_id, channel(system/mail/portal), sent_at, read_at, resend_at |
| `task` | id, user_id, title, subtitle, due_label, target(jsonb) |
| `assistant_conversation`, `assistant_message` | 사용자, 컨텍스트, 질문, 답변, 근거 문서 |
| `assistant_faq` | context, question, answer (목업 31건 시드) |

### 7.4 프런트엔드(React) 구현 메모
- 셸: 로그인 가드, 헤더 평면 탭, 방문 경로 칩, 스텝퍼(게이트 응답 기반), 하단 고정 바, 어시스턴트 패널, 토스트·알림 컨테이너.
- STEP 1: 업로드 드롭존(실제 drag & drop 포함), 프로파일 진행 표시, 후보 카드/리스트 전환, 선택 토글, 제안 조합 카드, 프로세스 목록·미리보기·새 프로세스 확인 모달.
- 서버 상태는 조회 캐시(예: TanStack Query), 화면 상태(보기 방식, 패널 열림)는 로컬에 둔다.

---

## 8. 목업의 결함·불일치 (재구현 시 그대로 옮기지 말 것)

| # | 내용 | 근거 |
|---|---|---|
| 1 | 토스트 블록의 조건 바인딩 `toastOn`이 `renderVals()`에 정의되어 있지 않다(`toastMsg`만 있음). 런타임은 undefined를 거짓으로 처리하므로 정적 분석상 토스트가 화면에 그려지지 않는다. 의도는 `!!s.toast`로 보인다 | M3891, L1708, 런타임 `walkIf` |
| 2 | 업로드할 때마다 `upList`가 교체되고 `manSel`의 예전 키는 남는다. 사라진 파일이 선택 수와 조합에 계속 잡힌다 | L2230 |
| 3 | 드롭존에 drop 핸들러가 없다. 같은 파일 재선택 시 input 값 초기화도 없다 | M206~M208 |
| 4 | `upTotal`은 스트림 카드 표시 여부와 무관하게 항상 +2, 문구도 "스트림 2" 고정 | L2117, M246 |
| 5 | 추천 조합 카드의 항목 목록은 업로드 파일만 보여 주는데 건수(`upComboCount`)와 실제 채택(`pickComboUp`)은 스트림·묶음 키까지 포함한다 | L2126, L2161, L2255 |
| 6 | 업로드 파일이 없으면 추천 조합 카드 자체가 숨겨져, 스트림만 고른 경우 STEP 1에서 조합을 만들 방법이 없다(STEP 2 진입은 가능) | L2075, L2160 |
| 7 | 묶음 카드 선택 시 묶음 이름 키와 구성원 4개 키가 모두 참이 되어 조합에 5건이 들어간다. `kOf`가 `obu.telemetry.v2`, `TRAFFIC_LINK_5MIN`에 `K7`만 부여해 구성원 표의 연계키와 어긋난다 | L1221~L1229, L2254 |
| 8 | 묶음 카드에서 새 프로세스 모달을 승인하면 묶음 이름 키만 선택되고 구성원은 선택되지 않는다 | L1222, L974 |
| 9 | 새 프로세스 가드가 "완료"가 아니라 "저장된 적 있음"만으로도 발동한다. 모달 문구의 "STEP 6 변환"은 단계 재편 전 번호다(현재 변환은 STEP 7) | L952~L953, M166 |
| 10 | `blank()`와 스냅숏이 `v7State`, `v6Results`, `svResults`, `v8State`, `metaOver`, `linWaived`를 다루지 않아 프로세스 사이에 검증 상태가 새어 나간다 | L920~L928 |
| 11 | "불러오기"가 빈 현재 작업도 `saveCur()`로 저장해 데이터셋 0건짜리 항목이 목록에 생긴다 | L1077 |
| 12 | `pickComboUp`과 `upClearAll`은 조합을 바꾸면서 `invalidateDownstream`을 호출하지 않는다 | L2258, L2149 |
| 13 | "레이크 적재 요청 →" 링크가 전파를 막지 않아 선택 토글이 같이 일어난다 | L2570, M268, M324 |
| 14 | 이동 경로 칩 클릭이 `go()`를 우회한다 | L1725 |
| 15 | `authed`가 초안에 저장되어 localStorage 복원이나 스냅숏 가져오기만으로 로그인 게이트가 풀린다. 가져오기는 임의 JSON을 검증 없이 state에 병합한다 | L91~L99, L3097 |
| 16 | 프로세스 `savedAt`과 내보내기 파일명이 UTC 기준이라 화면의 다른 시각(로컬 `HH:MM`)과 어긋난다 | L931, L3083 |
| 17 | `upSummary`는 `procName`(없으면 "현재 프로세스")을 쓰고 프로세스 칩은 `curName`을 써서 같은 화면에 다른 이름이 나올 수 있다 | L2084, L978 |
| 18 | 업로드·조합 채택·단계 확정은 토스트가 "prov:Activity 기록됨"이라 말하지만 `actLog`에 남지 않는다 | L2231, L2259, L2986 |
