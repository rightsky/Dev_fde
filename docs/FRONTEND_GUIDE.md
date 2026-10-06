# 프런트엔드 작성 규칙

React 18 + TypeScript + Vite + react-router v6 + @tanstack/react-query v5. 화면 문구는 한국어.

## 건드리지 않는 파일 (공용 기반)

`src/api.ts` · `src/types.ts` · `src/ui.tsx` · `src/styles.css` · `src/auth.tsx` · `src/App.tsx` · `src/main.tsx`
· `src/shell/*` · `src/studio/context.tsx` · `src/studio/StudioLayout.tsx` · `src/studio/shared.tsx` · `src/components/assets.tsx`

화면 파일은 위 파일을 **읽어서 쓰기만** 한다. 부족한 것이 있으면 자기 파일 안에 지역 헬퍼로 만든다.
새 의존성(npm 패키지)·새 CSS 파일은 추가하지 않는다.

## 데이터

- 서버 호출은 `api.*` 만 쓴다 (`src/api.ts`). 응답 타입은 `src/types.ts`, 실제 응답 표본은 `docs/api-samples/*.json`, 전체 경로는 `docs/api-samples/ENDPOINTS.md`.
- **화면에 보이는 모든 값은 API 응답에서 온다.** 데모용 고정 수치·가짜 목록·타이머로 흉내 낸 진행 상태를 넣지 않는다. 값이 없으면 빈 상태(`<Empty>`)를 보여 준다.
- 추천 기능은 LLM 이 아니라 규칙 기반이다. 화면에서 "AI"라고 부르지 않고 "규칙 기반 추천"이라고 쓰며, 서버가 준 근거(reason)를 함께 보여 준다.
- 조회는 `useQuery`. 쿼리 키 규칙:
  - 프로세스에 딸린 조회는 반드시 `["process", pid, ...]` 로 시작한다 (예: `["process", pid, "relations"]`, `["process", pid, "dataset", did, "preview"]`).
    `useStudio().refresh()` 가 `["process", pid]` 를 무효화하므로 이 규칙을 지키면 변경 뒤 화면이 전부 갱신된다.
  - 전역 조회: `["assets"]`, `["assets", id]`, `["orgs"]`, `["taxonomy"]`, `["catalog", ...]`, `["users"]`, `["processes", ...]`.
- 변경은 `try { await api.x(); await refresh(); toast.ok("…") } catch (e) { toast.error(e) }` 형태로 하고, 진행 중에는 버튼에 `busy` 를 건다.
- 서버 오류 문구(`ApiError.message`)는 사용자에게 그대로 보여 줘도 되는 한국어다. `ApiError.code` 로 분기할 수 있다 (`LINEAGE_UNRESOLVED`, `PUBLISH_BLOCKED`).

## 스튜디오 화면 (STEP n)

- `const { pid, detail, combo, reference, editable, isAdmin, gate, go, refresh, params } = useStudio();`
- `editable === false` 이면 (종료된 프로세스·열람 전용 계정) 모든 편집 컨트롤을 `disabled` 로 둔다.
- 단계 이동은 `go(n, { dataset, focus, from, shape })`. 다른 화면에서 넘어올 때의 선택 데이터셋·강조 대상은 `params.dataset` / `params.focus` 로 온다.
  `params.focus` 가 가리키는 입력에는 `flash` 클래스를 2.4초 붙이고 `scrollIntoView` 한다.
- 화면 맨 위에는 `<StepHeader n={…} title="…" sub="…" />` 를 둔다. 프로세스 이름 줄·사이드바·하단 이전/다음 바는 `StudioLayout` 이 이미 그린다.
- 하류 결과의 무효화는 서버가 판단한다 (`detail.state.validation.stale` 등). 화면에서 따로 계산하지 않는다.

## 모양

- `src/styles.css` 의 클래스를 쓴다: `card` `card-head` `card-title` `btn` `badge` `chip` `tabs` `table-wrap/table` `banner` `empty` `kv` `meter` `grid c2/c3/side/side-l` `row` `col` `field/label/input/select/textarea` `code` `stat` 등.
  부품은 `src/ui.tsx` (`Button` `Badge` `Card` `Banner` `Empty` `Field` `Tabs` `Modal` `Meter` `CodeBlock` `QueryState` `ConfirmButton` `KeyPill` `SeverityBadge` `useToast`, `fmtDateTime` `fmtNum` `fmtPct` `shortHash` `errText` `cx`).
- 인라인 `style` 은 배치(너비·간격·정렬)에만 쓴다. 색은 `var(--primary)` 같은 CSS 변수만 쓴다.
- 한 화면에 정보가 많으므로 밀도 있게: 본문 12~13px, 카드 안 여백은 기본값, 표는 `table-wrap` 으로 감싼다.
- 삭제·철회처럼 되돌리기 어려운 동작은 `ConfirmButton` 을 쓴다.

## 마무리

- 끝내기 전에 `cd frontend && npx tsc --noEmit` 를 돌려 **자기 파일의 오류를 0건**으로 만든다 (`noUnusedLocals` 가 켜져 있다).
- 다른 사람이 맡은 파일의 오류는 고치지 않는다.
