// STEP 3 — DCAT/PROV-O 카탈로그 작성.
// 데이터셋마다 메타데이터를 쓰고 ARD 필수 필드를 승인한다. 오른쪽 미리보기·검증은 서버의 정본 그래프에서 온다.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, FormEvent, KeyboardEvent, ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { api } from "../api";
import type { CardItem, Dataset, DictRow, MetaField, Org, Preview, Reference, Severity } from "../types";
import { Badge, Banner, Button, Card, CodeBlock, ConfirmButton, Empty, QueryState, Tabs, cx, errText, fmtDateTime, fmtNum, shortHash, useToast } from "../ui";
import { useStudio } from "./context";
import { DatasetList, Gate0List, ProfileTable, ReadOnlyNote, ReadinessBadge, StepHeader, ValidationRows } from "./shared";

// ───────────── 타입 · 상수
type TabKey = "class" | "form" | "card" | "dict" | "prov" | "profile";
type PreviewFmt = "ttl" | "jsonld" | "txt";
/** 폼에서 다루는 값. 태그형은 string[], 나머지는 문자열(기관은 id 를 문자열로)이다. */
type FieldValue = string | string[];
type Draft = Record<string, FieldValue>;
type OrgsQuery = UseQueryResult<Org[]>;

const EMPTY_DRAFT: Draft = {};
const CLASS_FOCUS = "extra_classes";
const DICT_FOCUS = "dictionary";
const LEVELS: MetaField["level"][] = ["필수", "권장", "선택"];
const TABS: { key: TabKey; label: string }[] = [
  { key: "class", label: "① 클래스" },
  { key: "form", label: "② 프러퍼티 폼" },
  { key: "dict", label: "③ 데이터 사전" },
  { key: "card", label: "④ 데이터 카드" },
  { key: "prov", label: "⑤ 프로버넌스" },
  { key: "profile", label: "⑥ 원천 프로파일" },
];
/** 수정 경로의 focus 이름 → 폼 필드 이름 (다른 이름은 필드 이름과 같다) */
const FOCUS_ALIAS: Record<string, string> = { publisher: "publisher_org_id" };
/** readiness.missing 의 이름 → 화면 표기와 고칠 필드 (서버 confirm_meta 의 문구와 같다) */
const MISSING: Record<string, { label: string; field: string }> = {
  title: { label: "제목", field: "title" },
  publisher: { label: "제공기관(승인)", field: "publisher_org_id" },
  distribution: { label: "미디어타입(승인)", field: "media_type" },
  temporalResolution: { label: "시간 해상도(승인)", field: "temporal_resolution" },
  eventTimeColumn: { label: "event-time 컬럼(승인)", field: "event_time_column" },
};
/** readiness.recommended_missing 의 이름 → 화면 표기. field 가 없으면 STEP 4 에서 채우는 항목이다. */
const RECOMMENDED: Record<string, { label: string; field?: string }> = {
  description: { label: "설명", field: "description" },
  keywords: { label: "키워드", field: "keywords" },
  theme: { label: "주제영역 (STEP 4)" },
  dataType: { label: "데이터유형 (STEP 4)" },
  joinKeys: { label: "연계키 (STEP 4)" },
  n2sfGrade: { label: "보안등급 N²SF (STEP 4)" },
  license: { label: "이용조건 (STEP 4)" },
};
// 서버(_clean_meta)와 같은 형식 규칙 — 저장 전에 미리 알려 주기 위한 것이고 최종 판정은 서버가 한다
const DURATION_RE = /^P(?!$)(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$/;
const URL_RE = /^[a-z][a-z0-9+.-]*:\/\/\S+$/i;

// ───────────── 값 도우미
function serverValue(f: MetaField, meta: Dataset["meta"]): FieldValue {
  const raw: unknown = meta[f.name];
  if (f.type === "tags") {
    if (Array.isArray(raw)) return raw.map((x) => String(x).trim()).filter(Boolean);
    return typeof raw === "string" ? splitTags(raw) : [];
  }
  return raw == null ? "" : String(raw);
}

function splitTags(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function sameValue(a: FieldValue, b: FieldValue): boolean {
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((x, i) => x === b[i]);
  }
  return a.trim() === b.trim();
}

const isEmpty = (v: FieldValue) => (Array.isArray(v) ? v.length === 0 : v.trim() === "");

/** PATCH 본문에 넣을 값. 빈 값은 null 로 보내 필드를 지운다. */
function toPayload(f: MetaField, v: FieldValue): unknown {
  if (Array.isArray(v)) return v;
  const s = v.trim();
  if (s === "") return null;
  return f.type === "org" ? Number(s) : s;
}

function formatError(f: MetaField, v: FieldValue): string | null {
  if (Array.isArray(v) || v.trim() === "") return null;
  if (f.type === "duration" && !DURATION_RE.test(v.trim())) return "ISO 8601 duration 형식이어야 합니다 (예: PT5M, P1D)";
  if (f.type === "url" && !URL_RE.test(v.trim())) return "URL 형식이어야 합니다 (예: https://…)";
  return null;
}

function autoFields(meta: Dataset["meta"]): string[] {
  const raw: unknown = meta._auto;
  return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string") : [];
}

function recordTypes(p: Preview | undefined): string[] {
  const raw: unknown = p?.record.type;
  return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string") : [];
}

function initialDatasetId(combo: Dataset[], wanted: number | null): number | null {
  if (wanted != null && combo.some((d) => d.id === wanted)) return wanted;
  return (combo.find((d) => !d.meta_confirmed_at) ?? combo[0])?.id ?? null;
}

const kindLabel = (d: Dataset) => (d.kind === "stream" ? "실시간 스트림" : d.asset.data_form || "파일");

function useMedia(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatches(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return matches;
}

function usePreview(pid: number, did: number) {
  return useQuery({ queryKey: ["process", pid, "dataset", did, "preview"], queryFn: () => api.preview(did) });
}

// ───────────── 화면
export function Step3() {
  const { pid, combo, reference, editable, go, refresh, params, guard } = useStudio();
  const toast = useToast();
  const rootRef = useRef<HTMLDivElement>(null);
  const narrow = useMedia("(max-width: 1100px)");
  const mid = useMedia("(max-width: 1479px)");

  const [selectedId, setSelectedId] = useState<number | null>(() => initialDatasetId(combo, params.dataset));
  const [tab, setTab] = useState<TabKey>("form");
  const [draftState, setDraftState] = useState<{ did: number | null; values: Draft }>({ did: null, values: EMPTY_DRAFT });
  /** 진행 중인 변경 요청의 이름 (save · confirm · unconfirm · approve:필드 · class:IRI). 한 번에 하나만 보낸다. */
  const [busy, setBusy] = useState<string | null>(null);
  const [focusReq, setFocusReq] = useState<{ name: string; n: number } | null>(null);

  const orgsQ = useQuery({ queryKey: ["orgs"], queryFn: api.orgs });

  const dataset = combo.find((d) => d.id === selectedId) ?? combo[0] ?? null;
  const did = dataset?.id ?? null;
  const kind = dataset?.kind ?? null;
  const draft = draftState.did === did ? draftState.values : EMPTY_DRAFT;

  const fields = useMemo(() => (kind ? reference.meta_fields.filter((f) => f.scope === "all" || f.scope === kind) : []), [reference.meta_fields, kind]);
  const fieldNames = useMemo(() => new Set(reference.meta_fields.map((f) => f.name)), [reference.meta_fields]);
  const dirty = useMemo(
    () => (dataset ? fields.filter((f) => f.name in draft && !sameValue(draft[f.name], serverValue(f, dataset.meta))) : []),
    [fields, draft, dataset],
  );
  const dirtyCount = dirty.length;
  // 저장하지 않은 변경이 있으면 단계 이동 전에 확인을 받는다
  useEffect(() => {
    guard.current = () => dirtyCount > 0;
    return () => {
      guard.current = null;
    };
  }, [dirtyCount, guard]);

  // ── 강조 이동: 탭을 바꾸고, 그려진 뒤에 대상 입력을 화면 가운데로 옮겨 flash 를 붙인다
  const requestFocus = useCallback(
    (raw: string) => {
      const name = FOCUS_ALIAS[raw] ?? raw;
      if (name !== CLASS_FOCUS && name !== DICT_FOCUS && !fieldNames.has(name)) return;
      const group = reference.meta_fields.find((f) => f.name === name)?.group;
      setTab(name === CLASS_FOCUS ? "class" : name === DICT_FOCUS ? "dict" : group === "card" ? "card" : "form");
      setFocusReq((r) => ({ name, n: (r?.n ?? 0) + 1 }));
    },
    [fieldNames, reference.meta_fields],
  );

  useEffect(() => {
    if (!focusReq) return;
    const el = rootRef.current?.querySelector<HTMLElement>(`[data-focus="${focusReq.name}"]`);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    // 같은 대상을 다시 가리켜도 애니메이션이 처음부터 돌도록 클래스를 떼었다 붙인다
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
    if (el.matches("input, select, textarea") && !(el as HTMLInputElement).disabled) el.focus({ preventScroll: true });
    const t = window.setTimeout(() => el.classList.remove("flash"), 2400);
    return () => {
      window.clearTimeout(t);
      el.classList.remove("flash");
    };
  }, [focusReq]);

  // ── 다른 화면에서 넘어온 선택 데이터셋·강조 필드 (주소가 바뀔 때마다 한 번씩)
  const paramKey = `${params.dataset ?? ""}|${params.focus ?? ""}`;
  const handledParam = useRef<string | null>(null);
  useEffect(() => {
    if (handledParam.current === paramKey) return;
    const first = handledParam.current === null; // 첫 진입의 선택은 useState 초기값이 이미 처리했다
    handledParam.current = paramKey;
    if (!first && params.dataset != null && combo.some((d) => d.id === params.dataset)) setSelectedId(params.dataset);
    if (params.focus) requestFocus(params.focus);
  }, [paramKey, params.dataset, params.focus, combo, requestFocus]);

  if (!dataset) {
    return (
      <div>
        <StepHeader n={3} title="DCAT/PROV-O 카탈로그" sub="데이터셋마다 메타데이터를 작성하고 ARD 필수 필드를 승인합니다." />
        <Empty>조합에 편입된 데이터셋이 없습니다 — STEP 2 에서 조합을 먼저 확정하세요.</Empty>
      </div>
    );
  }

  const run = async (key: string, fn: () => Promise<void>) => {
    if (busy !== null) return;
    setBusy(key);
    try {
      await fn();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  const valueOf = (f: MetaField): FieldValue => (f.name in draft ? draft[f.name] : serverValue(f, dataset.meta));
  const isDirty = (name: string) => dirty.some((f) => f.name === name);
  const setField = (name: string, v: FieldValue) =>
    setDraftState((s) => ({ did: dataset.id, values: { ...(s.did === dataset.id ? s.values : EMPTY_DRAFT), [name]: v } }));
  /** 서버에 보낸 값과 그대로인 초안만 지운다 (저장 중에 더 고친 값은 남긴다). */
  const clearSaved = (id: number, sent: Draft) =>
    setDraftState((s) => {
      if (s.did !== id) return s;
      const values = { ...s.values };
      for (const k of Object.keys(sent)) if (values[k] === sent[k]) delete values[k];
      return { did: id, values };
    });

  const selectDataset = (id: number) => {
    if (id === dataset.id || busy !== null) return;
    if (dirtyCount > 0 && !window.confirm(`저장하지 않은 변경 ${dirtyCount}건이 있습니다. 버리고 다른 데이터셋으로 이동할까요?`)) return;
    setDraftState({ did: id, values: EMPTY_DRAFT });
    setSelectedId(id);
  };

  const saveAll = () =>
    run("save", async () => {
      if (dirtyCount === 0) return;
      const sent: Draft = {};
      const values: Record<string, unknown> = {};
      for (const f of dirty) {
        sent[f.name] = draft[f.name];
        values[f.name] = toPayload(f, draft[f.name]);
      }
      const reapprove = dirty.filter((f) => dataset.approved_fields.includes(f.name)).map((f) => f.label);
      await api.patchMeta(dataset.id, { values });
      await refresh();
      clearSaved(dataset.id, sent);
      toast.ok(
        reapprove.length > 0
          ? `변경 ${dirtyCount}건을 저장했습니다 — ${reapprove.join(" · ")} 승인이 해제되어 다시 승인해야 합니다`
          : `변경 ${dirtyCount}건을 저장했습니다`,
      );
    });

  const approve = (f: MetaField, on: boolean) => {
    const value = valueOf(f);
    if (on) {
      const err = formatError(f, value);
      if (err) {
        toast(`${f.label} — ${err}`);
        return;
      }
    }
    void run(`approve:${f.name}`, async () => {
      if (on) {
        // 지금 입력된 값을 함께 저장하고 승인한다 (값이 바뀌었으면 서버가 기존 승인을 풀고 새 값으로 승인한다)
        await api.patchMeta(dataset.id, { values: { [f.name]: toPayload(f, value) }, approve: [f.name] });
        await refresh();
        if (f.name in draft) clearSaved(dataset.id, { [f.name]: draft[f.name] });
        toast.ok(`${f.label} 승인 — 정본 그래프에 반영했습니다`);
      } else {
        await api.patchMeta(dataset.id, { unapprove: [f.name] });
        await refresh();
        toast.ok(`${f.label} 승인을 해제했습니다 — 정본에서는 미입력으로 간주합니다`);
      }
    });
  };

  const toggleClass = (iri: string) =>
    run(`class:${iri}`, async () => {
      const on = dataset.extra_classes.includes(iri);
      const next = on ? dataset.extra_classes.filter((c) => c !== iri) : [...dataset.extra_classes, iri];
      await api.patchMeta(dataset.id, { extra_classes: next });
      await refresh();
      toast.ok(on ? `${iri} 선택을 해제했습니다` : `${iri} 를 추가했습니다`);
    });

  const confirmMeta = () =>
    run("confirm", async () => {
      await api.confirmMeta(dataset.id);
      await refresh();
      const idx = combo.findIndex((d) => d.id === dataset.id);
      const next = [...combo.slice(idx + 1), ...combo.slice(0, idx)].find((d) => !d.meta_confirmed_at);
      toast.ok(next ? `「${dataset.title}」 메타데이터를 확정했습니다 — 다음: 「${next.title}」` : `「${dataset.title}」 메타데이터를 확정했습니다`);
      if (next) {
        setDraftState({ did: next.id, values: EMPTY_DRAFT });
        setSelectedId(next.id);
        setTab("form");
      }
    });

  const unconfirmMeta = () =>
    run("unconfirm", async () => {
      await api.unconfirmMeta(dataset.id);
      await refresh();
      toast.ok(`「${dataset.title}」 확정을 해제했습니다`);
    });

  const model: FormModel = { dataset, reference, orgsQ, editable, busy, auto: autoFields(dataset.meta), valueOf, isDirty, setField, approve };
  const confirmedCount = combo.filter((d) => d.meta_confirmed_at).length;
  const allConfirmed = confirmedCount === combo.length;
  const publisherId = dataset.approved_fields.includes("publisher_org_id") ? Number(dataset.meta.publisher_org_id) : null;
  const publisher = publisherId != null ? (orgsQ.data ?? []).find((o) => o.id === publisherId) ?? null : null;

  const columns = narrow ? "minmax(0, 1fr)" : mid ? "minmax(0, 1fr) 400px" : "260px minmax(0, 1fr) 400px";
  const listStyle: CSSProperties | undefined = narrow ? undefined : mid ? { gridColumn: "1 / -1" } : { position: "sticky", top: 12 };
  const sideStyle: CSSProperties | undefined = narrow ? undefined : { position: "sticky", top: 12, maxHeight: "calc(100vh - 150px)" };

  return (
    <div ref={rootRef}>
      <StepHeader
        n={3}
        title="DCAT/PROV-O 카탈로그"
        sub="데이터셋마다 메타데이터를 작성하고 ARD 필수 필드를 승인합니다. 오른쪽 미리보기는 저장할 때마다 실제 정본 그래프로 다시 만들어집니다."
        badge={<Badge tone={allConfirmed ? "ok" : "muted"}>확정 {confirmedCount}/{combo.length}</Badge>}
      />
      <ReadOnlyNote />
      {allConfirmed && (
        <div style={{ margin: "8px 0 14px" }}>
          <Banner
            tone="ok"
            right={
              <Button size="sm" variant="primary" onClick={() => go(4)}>
                STEP 4 분류로 →
              </Button>
            }
          >
            <b>✓ 조합 데이터셋 {combo.length}건의 메타데이터를 모두 확정했습니다.</b> 다음 단계에서 분류 체계를 입힙니다.
          </Banner>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: columns, alignItems: "start", marginTop: 8 }}>
        {/* 왼쪽: 조합 데이터셋 */}
        <div style={listStyle}>
          <DatasetList
            datasets={combo}
            selectedId={dataset.id}
            onSelect={selectDataset}
            status={(d) => (
              <>
                <ReadinessBadge d={d} />
                {d.meta_confirmed_at && <Badge tone="ok">확정</Badge>}
                {d.id === dataset.id && dirtyCount > 0 && <Badge tone="warn">미저장 {dirtyCount}</Badge>}
              </>
            )}
          />
        </div>

        {/* 가운데: 작성 폼 */}
        <div className="col gap-12" style={{ minWidth: 0 }}>
          <div className="row wrap">
            <span className="bold">작성 대상: {dataset.title}</span>
            <Badge tone={dataset.kind === "stream" ? "purple" : "muted"}>{kindLabel(dataset)}</Badge>
            <span className="mono small muted">{dataset.resource_id}</span>
            {!dataset.minted && <Badge title="관리자가 STEP 6 에서 ID 를 발급하면 정식 식별자로 바뀝니다">임시 ID</Badge>}
          </div>
          <Tabs tabs={TABS} value={tab} onChange={setTab} />

          {tab === "class" && <ClassTab key={dataset.id} pid={pid} dataset={dataset} reference={reference} editable={editable} busy={busy} onToggle={toggleClass} />}
          {tab === "form" && <FormTab key={dataset.id} m={model} fields={fields.filter((f) => f.group !== "card")} />}
          {tab === "dict" && <DictTab key={dataset.id} pid={pid} did={dataset.id} editable={editable} onSaved={refresh} />}
          {tab === "card" && <CardTab key={dataset.id} pid={pid} m={model} fields={fields.filter((f) => f.group === "card")} dirtyCount={dirtyCount} />}
          {tab === "prov" && <ProvTab key={dataset.id} pid={pid} dataset={dataset} publisher={publisher} />}
          {tab === "profile" && <ProfileTab key={dataset.id} pid={pid} did={dataset.id} />}

          {(tab === "form" || tab === "card" || dirtyCount > 0) && (
            <SaveBar
              dirty={dirty}
              invalidCount={dirty.filter((f) => formatError(f, draft[f.name]) != null).length}
              reapproveCount={dirty.filter((f) => dataset.approved_fields.includes(f.name)).length}
              editable={editable}
              busy={busy}
              onSave={saveAll}
              onReset={() => setDraftState({ did: dataset.id, values: EMPTY_DRAFT })}
            />
          )}
        </div>

        {/* 오른쪽: 미리보기 · 검증 · 확정 */}
        <div className="col" style={sideStyle}>
          <div style={narrow ? undefined : { overflowY: "auto", minHeight: 0, flex: "1 1 auto" }}>
            <PreviewPanel key={dataset.id} pid={pid} dataset={dataset} fields={fields} dirtyCount={dirtyCount} onFocus={requestFocus} />
          </div>
          <ConfirmBox dataset={dataset} editable={editable} busy={busy} dirtyCount={dirtyCount} onConfirm={confirmMeta} onUnconfirm={unconfirmMeta} />
        </div>
      </div>
    </div>
  );
}

// ───────────── ① 클래스
function classEffect(iri: string, d: Dataset): { text: string; inert?: boolean } | null {
  switch (iri) {
    case "prov:Entity":
    case "qb:DataSet":
    case "foaf:Document":
      return { text: `데이터셋 노드에 rdf:type ${iri} 를 함께 선언합니다.` };
    case "dcat:CatalogRecord":
      return { text: "등재 레코드 노드(dcat:CatalogRecord)를 추가해 등재 이력(등재 시각 · 확정 시각)을 기록합니다." };
    case "csvw:Table":
      if (d.kind === "stream") return { text: "스트림에는 배포본(dcat:Distribution)이 없어 그래프에 반영되지 않습니다.", inert: true };
      if (!d.approved_fields.includes("media_type")) {
        return { text: "프로파일된 컬럼 스키마를 CSVW 로 내보냅니다 — 미디어타입이 승인되어 배포본이 생긴 뒤에 반영됩니다.", inert: true };
      }
      return { text: "프로파일된 컬럼 스키마를 배포본 아래에 CSVW(csvw:Table · csvw:Column)로 내보냅니다." };
    case "prov:Collection":
      return { text: "조합(prov:Collection)은 STEP 2 에서 확정한 조합으로 이미 선언됩니다 — 이 선택은 트리플을 더하지 않습니다.", inert: true };
    default:
      return null;
  }
}

function ClassTab(props: { pid: number; dataset: Dataset; reference: Reference; editable: boolean; busy: string | null; onToggle: (iri: string) => void }) {
  const { dataset: d, reference, editable, busy } = props;
  const preview = usePreview(props.pid, d.id);
  const types = recordTypes(preview.data);
  const isStream = d.kind === "stream";
  const hasDistribution = !isStream && d.approved_fields.includes("media_type");
  return (
    <div className="col gap-12">
      <Card title="주 클래스" right={<span className="tiny muted">데이터 종류에 따라 고정됩니다</span>}>
        <div className="col">
          <div className="row top">
            <Badge tone="solid">dcat:Dataset</Badge>
            <span className="small dim">데이터셋 정본 기술 — 모든 데이터셋에 항상 선언합니다.</span>
          </div>
          {isStream ? (
            <div className="row top">
              <Badge tone="solid">dcat:DataService</Badge>
              <span className="small dim">스트림은 dcat:Dataset 과 dcat:DataService 를 함께 선언합니다. 미디어타입 대신 시간 해상도 · event-time 컬럼을 승인합니다.</span>
            </div>
          ) : (
            <div className="row top">
              <Badge tone={hasDistribution ? "solid" : "muted"}>dcat:Distribution</Badge>
              <span className="small dim">
                배포본 노드는 따로 고르지 않습니다 — 미디어타입(dcat:mediaType)이 승인되면 자동으로 만들어집니다.{" "}
                {hasDistribution ? <span className="t-ok bold">현재 생성됨</span> : <span className="t-warn bold">현재 없음 (미디어타입 승인 대기)</span>}
              </span>
            </div>
          )}
        </div>
        {types.length > 0 && (
          <div className="row wrap gap-4 mt-12">
            <span className="tiny muted">현재 정본의 rdf:type</span>
            {types.map((t) => (
              <span key={t} className="kbd">
                {t}
              </span>
            ))}
          </div>
        )}
      </Card>

      <div data-focus={CLASS_FOCUS} style={{ borderRadius: "var(--r-lg)" }}>
        <Card
          title={
            <>
              추가 클래스 <span className="muted small">{d.extra_classes.length}건 선택</span>
            </>
          }
          right={<span className="tiny muted">누르면 바로 저장됩니다</span>}
        >
          {reference.extra_classes.length === 0 ? (
            <Empty>선택할 수 있는 추가 클래스가 없습니다</Empty>
          ) : (
            <div className="col">
              {reference.extra_classes.map((c) => {
                const on = d.extra_classes.includes(c.iri);
                const effect = classEffect(c.iri, d);
                return (
                  <div key={c.iri} className="row top">
                    <button
                      className={cx("chip", on && "on")}
                      style={{ flex: "none" }}
                      aria-pressed={on}
                      disabled={!editable || busy !== null}
                      onClick={() => props.onToggle(c.iri)}
                    >
                      {busy === `class:${c.iri}` ? <span className="spinner" /> : on ? "✓" : "＋"} <span className="mono">{c.iri}</span>
                    </button>
                    <div className="grow small">
                      <div>
                        <Badge>{c.form}</Badge> {c.desc}
                      </div>
                      {effect && <div className={cx("tiny mt-4", effect.inert ? "t-warn" : "muted")}>그래프 반영: {effect.text}</div>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ───────────── ② 프러퍼티 폼
interface FormModel {
  dataset: Dataset;
  reference: Reference;
  orgsQ: OrgsQuery;
  editable: boolean;
  busy: string | null;
  /** 값이 자동 제안된 필드 이름 (meta._auto) */
  auto: string[];
  valueOf: (f: MetaField) => FieldValue;
  isDirty: (name: string) => boolean;
  setField: (name: string, v: FieldValue) => void;
  approve: (f: MetaField, on: boolean) => void;
}

const fieldDomId = (name: string) => `s3-field-${name}`;
const isWide = (f: MetaField) => f.type === "textarea" || f.type === "tags";

function FormTab({ m, fields }: { m: FormModel; fields: MetaField[] }) {
  const d = m.dataset;
  const approval = d.approval_fields.map((n) => fields.find((f) => f.name === n)).filter((f): f is MetaField => f != null);
  const rest = fields.filter((f) => !d.approval_fields.includes(f.name));
  const approvedCount = approval.filter((f) => d.approved_fields.includes(f.name)).length;
  return (
    <div className="col gap-12">
      <Card
        className="accent-top"
        title={
          <>
            ARD 필수 필드 승인
            <Badge tone={approvedCount === approval.length ? "ok" : "warn"}>
              승인 {approvedCount}/{approval.length}
            </Badge>
          </>
        }
        right={<ReadinessBadge d={d} />}
      >
        <p className="small muted mb-8">
          자동 제안값과 직접 입력한 값 모두 승인하기 전에는 미입력으로 간주합니다. 승인한 값만 정본 그래프에 들어가 STEP 6 검증 · STEP 7 산출물에 똑같이 나타나고, 승인된 값을 고치면 승인이 풀립니다.
        </p>
        <div className="col">
          {approval.map((f) => (
            <ApprovalRow key={f.name} m={m} field={f} />
          ))}
        </div>
      </Card>

      {LEVELS.map((level) => {
        const group = rest.filter((f) => f.level === level);
        if (group.length === 0) return null;
        return (
          <Card
            key={level}
            title={
              <>
                {level} 항목 <span className="muted small">{group.length}개</span>
              </>
            }
          >
            <p className="small muted mb-8">{LEVEL_NOTE[level]}</p>
            <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
              {group.map((f) => (
                <FieldRow key={f.name} m={m} field={f} />
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

// 등급은 가이드라인 표 8 의 우선순위다. 위의 승인 필드와 달리 비워도 확정·발행을 막지 않는다.
const LEVEL_NOTE: Record<MetaField["level"], string> = {
  필수: "가이드라인 표 9~11 이 필수로 정한 항목입니다. 비워 두어도 확정과 발행은 할 수 있지만, STEP 8 진단에서 해당 항목이 미흡으로 판정됩니다.",
  권장: "가이드라인이 작성을 권장하는 항목과 이 스튜디오의 권장 항목입니다. 채우면 STEP 8 진단 점수가 오릅니다.",
  선택: "데이터 특성에 따라 적는 항목입니다. 가이드라인 표 12 의 선택 항목도 STEP 8 진단에서 판정합니다.",
};

function LevelBadge({ level, guide }: { level: MetaField["level"]; guide?: string }) {
  return (
    <Badge tone={level === "필수" ? "dark" : level === "권장" ? "info" : "muted"} title={guide ? `가이드라인 ${guide}` : "이 스튜디오의 항목 (가이드라인 표 9~12 에는 없음)"}>
      {level}
    </Badge>
  );
}

function AutoBadge() {
  return (
    <Badge tone="purple" title="시스템이 원천에서 읽어 제안한 값입니다. 값을 고치면 이 표시가 사라집니다">
      자동 제안
    </Badge>
  );
}

function ApprovalRow({ m, field }: { m: FormModel; field: MetaField }) {
  const id = fieldDomId(field.name);
  const value = m.valueOf(field);
  const dirty = m.isDirty(field.name);
  const approved = m.dataset.approved_fields.includes(field.name);
  const empty = isEmpty(value);
  const error = formatError(field, value);
  const checked = approved && !dirty;
  const busy = m.busy === `approve:${field.name}`;

  let state: ReactNode;
  if (error) state = <span className="t-err">{error}</span>;
  else if (checked) state = <span className="t-ok bold">✓ 승인됨 — 정본 그래프에 반영</span>;
  else if (empty) state = <span className="muted">{approved ? "값을 비웠습니다 — 저장하면 승인이 해제되고 값이 지워집니다" : "값 없음"}</span>;
  else if (approved) state = <span className="t-warn bold">값을 바꿨습니다 — 다시 승인해야 합니다 (저장만 하면 기존 승인이 해제됩니다)</span>;
  else state = <span className="t-warn bold">승인 대기 — 승인 전까지 미입력으로 간주</span>;

  return (
    <div className="card tight flat">
      <div className="row between top wrap">
        <label className="label" htmlFor={id}>
          {field.label}
          <span className="kbd">{field.property}</span>
          {m.auto.includes(field.name) && !dirty && <AutoBadge />}
          {dirty && <Badge tone="warn">미저장</Badge>}
        </label>
        <label className="check" title={dirty && !empty ? "지금 입력한 값을 저장하고 승인합니다" : undefined}>
          <input
            type="checkbox"
            checked={checked}
            disabled={!m.editable || m.busy !== null || (!checked && (empty || error != null))}
            onChange={() => m.approve(field, !checked)}
          />
          <span className="bold">승인</span>
          {busy && <span className="spinner" />}
        </label>
      </div>
      <div className="mt-4">
        <FieldControl m={m} field={field} id={id} value={value} />
      </div>
      <div className="small mt-4">{state}</div>
      <FieldHint m={m} field={field} value={value} />
    </div>
  );
}

function FieldRow({ m, field }: { m: FormModel; field: MetaField }) {
  const id = fieldDomId(field.name);
  const value = m.valueOf(field);
  const dirty = m.isDirty(field.name);
  const error = formatError(field, value);
  return (
    <div className="field" style={isWide(field) ? { gridColumn: "1 / -1" } : undefined}>
      <label className="label" htmlFor={id}>
        {field.label}
        <span className="kbd">{field.property}</span>
        <LevelBadge level={field.level} guide={field.guide} />
        {field.guide && <span className="tiny muted">{field.guide}</span>}
        {m.auto.includes(field.name) && !dirty && <AutoBadge />}
        {dirty && <Badge tone="warn">미저장</Badge>}
      </label>
      <FieldControl m={m} field={field} id={id} value={value} />
      {error && <span className="hint t-err">{error}</span>}
      <FieldHint m={m} field={field} value={value} />
    </div>
  );
}

/** 값 옆에 붙이는 근거: 선택한 기관의 IRI, 원천에서 감지된 값 등 (모두 API 응답에서 온다) */
function FieldHint({ m, field, value }: { m: FormModel; field: MetaField; value: FieldValue }) {
  const asset = m.dataset.asset;
  const text = Array.isArray(value) ? "" : value.trim();
  let hint: ReactNode = null;
  if (field.type === "org") {
    const org = (m.orgsQ.data ?? []).find((o) => String(o.id) === text);
    if (org) hint = <span className="mono">{org.iri}</span>;
  } else if (field.type === "media_type") {
    const def = m.reference.media_types.find((t) => t.value === text);
    hint = (
      <>
        {def && <>데이터 형태: {def.form}</>}
        {def && asset.media_type && " · "}
        {asset.media_type && (
          <>
            원천 파일에서 감지된 값: <span className="mono">{asset.media_type}</span>
          </>
        )}
      </>
    );
    if (!def && !asset.media_type) hint = null;
  } else if (field.name === "temporal_resolution" && asset.stream.temporal_resolution) {
    hint = (
      <>
        스트림 등록값: <span className="mono">{asset.stream.temporal_resolution}</span>
      </>
    );
  } else if (field.name === "event_time_column" && asset.stream.event_time_column) {
    hint = (
      <>
        스트림 등록값: <span className="mono">{asset.stream.event_time_column}</span>
      </>
    );
  }
  return hint ? <span className="hint">{hint}</span> : null;
}

// 입력 예시 (가이드라인 표 9~12 의 예시 열에서 가져왔다)
const PLACEHOLDER: Record<string, string> = {
  creator: "예: 데이터전략과",
  language: "예: ko",
  contact_name: "예: 데이터전략과 홍길동",
  contact_email: "예: data@example.go.kr",
  contact_phone: "예: 044-201-3114",
  version: "예: 2025.01.v1",
  spatial: "예: 대한민국 서울특별시 (25개 자치구)",
  version_notes: "예: 데이터셋 최초 공개 / 결측치 처리 방식 변경 / 측정지역 코드화 및 적용",
  rights: "예: 상업적·비상업적 이용 모두 허용",
  rai_data_biases: "예: 도시 지역(서울·수도권)에 측정소가 집중되어 있어 농촌 지역의 대표성이 낮음",
  quality_annotation: "예: 월 1회 수동 검수 완료 (환경전문가 검토)",
  rai_known_limitations: "예: 일부 측정소는 장비 유지보수 기간 동안 측정값 누락",
  rai_missing_data: "예: 결측 사유: 센서 점검(2.1%), 통신 오류(1.1%)",
};

function FieldControl({ m, field, id, value }: { m: FormModel; field: MetaField; id: string; value: FieldValue }) {
  const disabled = !m.editable;
  const text = Array.isArray(value) ? "" : value;
  const onText = (v: string) => m.setField(field.name, v);
  switch (field.type) {
    case "tags":
      return <TagInput id={id} name={field.name} value={Array.isArray(value) ? value : []} disabled={disabled} onChange={(v) => m.setField(field.name, v)} />;
    case "textarea":
      return (
        <textarea
          id={id}
          className="textarea"
          data-focus={field.name}
          rows={3}
          placeholder={PLACEHOLDER[field.name]}
          value={text}
          disabled={disabled}
          onChange={(e) => onText(e.target.value)}
        />
      );
    case "org":
      return <OrgControl id={id} name={field.name} value={text} disabled={disabled} orgsQ={m.orgsQ} onChange={onText} />;
    case "media_type":
      return (
        <SelectControl
          id={id}
          name={field.name}
          value={text}
          disabled={disabled}
          onChange={onText}
          emptyLabel="미디어타입 선택…"
          options={m.reference.media_types.map((t) => ({ value: t.value, label: `${t.ext} — ${t.value}` }))}
        />
      );
    case "late_policy":
      return (
        <SelectControl
          id={id}
          name={field.name}
          value={text}
          disabled={disabled}
          onChange={onText}
          emptyLabel="선택 안 함"
          options={m.reference.late_policies.map((p) => ({ value: p, label: p }))}
        />
      );
    case "periodicity":
      return (
        <SelectControl
          id={id}
          name={field.name}
          value={text}
          disabled={disabled}
          onChange={onText}
          emptyLabel="선택 안 함"
          options={m.reference.accrual_periodicities.map((p) => ({ value: p.value, label: `${p.label} (${p.value})` }))}
        />
      );
    case "text":
    case "url":
    case "duration":
    case "date": {
      // event-time 컬럼은 스트림 등록 때 적은 필드 이름을 후보로 보여 준다
      const candidates = field.name === "event_time_column" ? m.dataset.asset.stream.fields ?? [] : [];
      const listId = candidates.length > 0 ? `${id}-list` : undefined;
      return (
        <>
          <input
            id={id}
            className="input"
            data-focus={field.name}
            type={field.type === "date" ? "date" : "text"}
            inputMode={field.type === "url" ? "url" : undefined}
            placeholder={field.type === "duration" ? "예: PT5M, P1D" : field.type === "url" ? "예: https://…" : PLACEHOLDER[field.name]}
            list={listId}
            value={text}
            disabled={disabled}
            onChange={(e) => onText(e.target.value)}
          />
          {listId && (
            <datalist id={listId}>
              {candidates.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.type}
                </option>
              ))}
            </datalist>
          )}
        </>
      );
    }
  }
}

function SelectControl(props: {
  id: string;
  name: string;
  value: string;
  disabled: boolean;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  emptyLabel: string;
}) {
  const known = props.value === "" || props.options.some((o) => o.value === props.value);
  return (
    <select id={props.id} className="select" data-focus={props.name} value={props.value} disabled={props.disabled} onChange={(e) => props.onChange(e.target.value)}>
      <option value="">{props.emptyLabel}</option>
      {!known && <option value={props.value}>{props.value} (목록에 없는 값)</option>}
      {props.options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function TagInput(props: { id: string; name: string; value: string[]; disabled: boolean; onChange: (v: string[]) => void }) {
  const { value, disabled, onChange } = props;
  const [text, setText] = useState("");
  const add = (raw: string) => {
    const next = [...value];
    for (const t of splitTags(raw)) if (!next.includes(t)) next.push(t);
    if (next.length !== value.length) onChange(next);
    setText("");
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return; // 한글 조합 중의 Enter 는 글자 확정이다
    if (e.key === "Enter") {
      e.preventDefault();
      add(text);
    } else if (e.key === "Backspace" && text === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };
  return (
    <div className="col gap-4">
      {value.length > 0 && (
        <div className="row wrap gap-4">
          {value.map((t) => (
            <Badge key={t} tone="info">
              {t}
              <button type="button" className="link-btn" aria-label={`${t} 삭제`} disabled={disabled} onClick={() => onChange(value.filter((x) => x !== t))}>
                ✕
              </button>
            </Badge>
          ))}
        </div>
      )}
      <input
        id={props.id}
        className="input"
        data-focus={props.name}
        placeholder="입력 후 Enter 또는 쉼표(,)로 추가"
        value={text}
        disabled={disabled}
        onChange={(e) => (e.target.value.includes(",") ? add(e.target.value) : setText(e.target.value))}
        onKeyDown={onKeyDown}
        onBlur={() => text.trim() && add(text)}
      />
    </div>
  );
}

function OrgControl(props: { id: string; name: string; value: string; disabled: boolean; orgsQ: OrgsQuery; onChange: (v: string) => void }) {
  const { value, disabled, orgsQ } = props;
  const qc = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const orgs = orgsQ.data ?? [];
  // 비활성 기관은 새로 고를 수 없지만, 이미 들어 있는 값이면 보여 준다
  const options = orgs.filter((o) => o.active || String(o.id) === value);
  const known = value === "" || options.some((o) => String(o.id) === value);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!label.trim() || busy) return;
    setBusy(true);
    try {
      const org = await api.createOrg({ label: label.trim(), code: code.trim() || undefined });
      qc.setQueryData<Org[]>(["orgs"], (xs) => (xs && !xs.some((o) => o.id === org.id) ? [...xs, org] : xs));
      await qc.invalidateQueries({ queryKey: ["orgs"] });
      props.onChange(String(org.id));
      toast.ok(`기관을 등록했습니다 — ${org.label} (${org.code})`);
      setOpen(false);
      setLabel("");
      setCode("");
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="col gap-4">
      <div className="row">
        <select
          id={props.id}
          className="select"
          data-focus={props.name}
          value={value}
          disabled={disabled || orgsQ.isLoading}
          onChange={(e) => props.onChange(e.target.value)}
        >
          <option value="">{orgsQ.isLoading ? "기관 목록을 불러오는 중…" : "기관 선택…"}</option>
          {!known && !orgsQ.isLoading && <option value={value}>등록되지 않은 기관 (#{value})</option>}
          {options.map((o) => (
            <option key={o.id} value={String(o.id)}>
              {o.label} ({o.code}){o.active ? "" : " · 비활성"}
            </option>
          ))}
        </select>
        <button type="button" className="link-btn nowrap small" disabled={disabled} onClick={() => setOpen((v) => !v)}>
          {open ? "닫기" : "＋ 기관 등록"}
        </button>
      </div>
      {orgsQ.error != null && <span className="hint t-err">기관 목록을 불러오지 못했습니다 — {errText(orgsQ.error)}</span>}
      {open && !disabled && (
        <form className="card tight col" onSubmit={create}>
          <div className="row wrap top">
            <input className="input" style={{ flex: "2 1 160px" }} placeholder="기관명 (필수)" aria-label="기관명" value={label} maxLength={200} onChange={(e) => setLabel(e.target.value)} />
            <input className="input" style={{ flex: "1 1 140px" }} placeholder="기관 코드 (선택) 예: ORG-1613000" aria-label="기관 코드" value={code} onChange={(e) => setCode(e.target.value)} />
            <Button type="submit" size="sm" variant="outline" busy={busy} disabled={!label.trim()} style={{ height: 36 }}>
              등록 후 선택
            </Button>
          </div>
          <span className="hint">기관 코드를 비우면 로컬 코드가 자동으로 붙습니다. 등록한 기관도 승인해야 정본에 반영됩니다.</span>
        </form>
      )}
    </div>
  );
}

function SaveBar(props: {
  dirty: MetaField[];
  invalidCount: number;
  reapproveCount: number;
  editable: boolean;
  busy: string | null;
  onSave: () => void;
  onReset: () => void;
}) {
  const n = props.dirty.length;
  return (
    <div className="card tight row between wrap" style={n > 0 ? { position: "sticky", bottom: 8, zIndex: 2, borderColor: "var(--primary)" } : undefined}>
      <div className="grow small">
        {n === 0 ? (
          <span className="muted">변경 사항 없음 — 값을 고친 뒤 여기에서 한 번에 저장합니다.</span>
        ) : (
          <>
            <div className="ellipsis" title={props.dirty.map((f) => f.label).join(", ")}>
              <b>변경 {n}건</b> <span className="muted">· {props.dirty.map((f) => f.label).join(", ")}</span>
            </div>
            {props.reapproveCount > 0 && <div className="t-warn">승인된 필드 {props.reapproveCount}건이 바뀌었습니다 — 저장하면 승인이 해제되어 다시 승인해야 합니다.</div>}
            {props.invalidCount > 0 && <div className="t-err">형식 오류 {props.invalidCount}건 — 고친 뒤에 저장할 수 있습니다.</div>}
          </>
        )}
      </div>
      <div className="row">
        <ConfirmButton size="sm" confirmLabel="한 번 더 눌러 되돌리기" disabled={n === 0 || props.busy !== null} onConfirm={props.onReset}>
          되돌리기
        </ConfirmButton>
        <Button variant="primary" busy={props.busy === "save"} disabled={!props.editable || n === 0 || props.invalidCount > 0 || props.busy !== null} onClick={props.onSave}>
          변경 사항 저장{n > 0 ? ` (${n})` : ""}
        </Button>
      </div>
    </div>
  );
}

// ───────────── ③ 데이터 사전
type DictDraft = Record<string, { description: string; unit: string; codes: string }>;
const dictKey = (r: { table: string; column: string }) => `${r.table}\u0000${r.column}`;

function DictTab({ pid, did, editable, onSaved }: { pid: number; did: number; editable: boolean; onSaved: () => Promise<void> }) {
  const q = useQuery({ queryKey: ["process", pid, "dataset", did, "dictionary"], queryFn: () => api.dictionary(did) });
  const toast = useToast();
  const [draft, setDraft] = useState<DictDraft>({});
  const [busy, setBusy] = useState(false);
  const rows = q.data?.rows ?? [];
  const value = (r: DictRow) => draft[dictKey(r)] ?? { description: r.description, unit: r.unit, codes: r.codes };
  const changed = rows.filter((r) => {
    const d = draft[dictKey(r)];
    return d && (d.description.trim() !== r.description || d.unit.trim() !== r.unit || d.codes.trim() !== r.codes);
  });
  const set = (r: DictRow, k: "description" | "unit" | "codes", v: string) => setDraft((s) => ({ ...s, [dictKey(r)]: { ...value(r), [k]: v } }));
  const save = async () => {
    setBusy(true);
    try {
      await api.putDictionary(
        did,
        changed.map((r) => ({ table: r.table, column: r.column, ...value(r) })),
      );
      await onSaved();
      setDraft({});
      toast.ok(`컬럼 ${changed.length}개의 정의를 저장했습니다 — 정본 그래프의 컬럼 구조에 반영했습니다`);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const tables = [...new Set(rows.map((r) => r.table))];
  return (
    <QueryState q={q}>
      {q.data && (
        <div className="col gap-12" data-focus={DICT_FOCUS} style={{ borderRadius: "var(--r-lg)" }}>
          <Card
            title={
              <>
                데이터 사전{" "}
                <Badge tone={q.data.total > 0 && q.data.described === q.data.total ? "ok" : "warn"}>
                  정의 {q.data.described}/{q.data.total}
                </Badge>
              </>
            }
          >
            <p className="small muted">
              컬럼 이름·자료형·결측률·예시값은 원천 프로파일에서 자동으로 채웁니다. 정의·단위·코드값 의미만 적으면 됩니다. 적은 내용은 정본 그래프의 컬럼 구조(CSVW)에 들어가고, STEP 7 에서
              데이터 사전(CSV)·데이터 카드·Croissant 로 함께 나갑니다. 모든 컬럼에 정의가 있어야 STEP 8 의 데이터 사전 항목(C-06)이 충족됩니다.
            </p>
          </Card>
          {rows.length === 0 && <Empty>원천 프로파일에 컬럼이 없습니다.</Empty>}
          {tables.map((t) => (
            <Card key={t} title={<>표 「{t}」</>}>
              <div className="col gap-8">
                {rows
                  .filter((r) => r.table === t)
                  .map((r) => {
                    const v = value(r);
                    const dirty = changed.includes(r);
                    return (
                      <div key={dictKey(r)} className="card tight flat" style={{ display: "grid", gridTemplateColumns: "minmax(160px, 220px) minmax(0, 1fr)", gap: 12 }}>
                        <div className="small">
                          <div className="bold mono" style={{ fontSize: 13 }}>
                            {r.column}
                          </div>
                          <div className="row wrap gap-4 mt-4">
                            <Badge>{r.type_label}</Badge>
                            {r.key && <Badge tone="info">{r.key}</Badge>}
                            {r.pii && <Badge tone="err">개인정보 의심</Badge>}
                            {dirty && <Badge tone="warn">미저장</Badge>}
                          </div>
                          {r.null_rate != null && (
                            <div className="muted mt-4">
                              결측 {(r.null_rate * 100).toFixed(1)}% · 고유값 {fmtNum(r.distinct ?? 0)}
                            </div>
                          )}
                          {r.samples.length > 0 && (
                            <div className="muted ellipsis" title={r.samples.join(" / ")}>
                              예: {r.samples.join(" / ")}
                            </div>
                          )}
                        </div>
                        <div className="col gap-4" style={{ minWidth: 0 }}>
                          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 120px", gap: 8 }}>
                            <textarea
                              className="textarea"
                              rows={2}
                              aria-label={`${r.column} 정의`}
                              value={v.description}
                              disabled={!editable || busy}
                              placeholder="정의: 이 컬럼이 무엇인지 (산정기준 포함)"
                              onChange={(e) => set(r, "description", e.target.value)}
                            />
                            <input className="input" style={{ alignSelf: "start" }} aria-label={`${r.column} 단위`} value={v.unit} disabled={!editable || busy} placeholder="단위 (예: m)" onChange={(e) => set(r, "unit", e.target.value)} />
                          </div>
                          <input
                            className="input"
                            aria-label={`${r.column} 코드값 의미`}
                            value={v.codes}
                            disabled={!editable || busy}
                            placeholder="코드값 의미 (해당 시, 예: 1=국도, 2=지방도)"
                            onChange={(e) => set(r, "codes", e.target.value)}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </Card>
          ))}
          <div className="card tight row between wrap" style={changed.length > 0 ? { position: "sticky", bottom: 8, zIndex: 2, borderColor: "var(--primary)" } : undefined}>
            <span className="small">{changed.length > 0 ? <b>변경 {changed.length}개 컬럼</b> : <span className="muted">변경 사항 없음</span>}</span>
            <div className="row">
              <Button size="sm" disabled={changed.length === 0 || busy} onClick={() => setDraft({})}>
                되돌리기
              </Button>
              <Button variant="primary" busy={busy} disabled={!editable || changed.length === 0} onClick={save}>
                데이터 사전 저장{changed.length > 0 ? ` (${changed.length})` : ""}
              </Button>
            </div>
          </div>
        </div>
      )}
    </QueryState>
  );
}

// ───────────── ④ 데이터 카드
const SOURCE_TONE: Record<CardItem["source"], "ok" | "info" | "warn" | "muted"> = { 자동: "ok", 입력: "info", "작성 필요": "warn", "해당 시": "muted" };

function CardTab({ pid, m, fields, dirtyCount }: { pid: number; m: FormModel; fields: MetaField[]; dirtyCount: number }) {
  const did = m.dataset.id;
  const q = useQuery({ queryKey: ["process", pid, "dataset", did, "card"], queryFn: () => api.cardPreview(did) });
  const byItem = new Map(fields.map((f) => [f.card_item, f]));
  const pct = q.data && q.data.total > 0 ? Math.round((q.data.filled / q.data.total) * 100) : 0;
  return (
    <QueryState q={q}>
      {q.data && (
        <div className="col gap-12">
          <Card
            title={
              <>
                데이터 카드 (부록 4){" "}
                <Badge tone={pct >= 90 ? "ok" : pct >= 50 ? "warn" : "err"}>
                  필수 칸 {q.data.filled}/{q.data.total} · {pct}%
                </Badge>
              </>
            }
          >
            <p className="small muted">
              가이드라인 부록 4 양식 38칸을 지금 메타데이터·분류·프로파일로 채운 결과입니다. "자동"은 시스템이, "입력"은 프러퍼티 폼·데이터 사전에서 채운 칸입니다. "작성 필요" 가운데 이 탭에서만 쓰는 칸은 아래 입력란에 적습니다. 필수 칸을 90% 이상 채우고
              STEP 7 에서 변환하면 STEP 8 의 데이터 카드 항목(R-10)이 충족됩니다.
              {dirtyCount > 0 && <span className="t-warn"> 저장하지 않은 변경은 아래 표에 아직 반영되지 않았습니다.</span>}
            </p>
          </Card>
          {q.data.sections.map((sec, n) => (
            <Card key={sec.section} title={`${n + 1}. ${sec.section}`}>
              <div className="col gap-8">
                {sec.items.map((it) => {
                  const f = byItem.get(it.item);
                  return (
                    <div key={it.item} className="card tight flat">
                      <div className="row between top wrap">
                        <span className="bold">{it.item}</span>
                        <Badge tone={SOURCE_TONE[it.source]}>{it.source}</Badge>
                      </div>
                      {f ? (
                        <div className="mt-4">
                          <FieldControl m={m} field={f} id={fieldDomId(f.name)} value={m.valueOf(f)} />
                          {m.isDirty(f.name) && <span className="hint t-warn">미저장</span>}
                          {it.source === "자동" && it.content && <div className="small muted mt-4">자동으로 채운 내용: {it.content}</div>}
                        </div>
                      ) : (
                        <div className="small mt-4" style={{ whiteSpace: "pre-wrap" }}>
                          {it.content || <span className="muted">{it.source === "해당 시" ? "해당할 때만 적습니다" : "프러퍼티 폼·데이터 사전·STEP 4 에서 채워집니다"}</span>}
                          {it.note && <div className="muted">{it.note}</div>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>
      )}
    </QueryState>
  );
}

// ───────────── ⑤ 프로버넌스
function ProvTab({ pid, dataset, publisher }: { pid: number; dataset: Dataset; publisher: Org | null }) {
  const q = useQuery({ queryKey: ["process", pid, "activities"], queryFn: () => api.processActivities(pid, 100) });
  const rows = (q.data ?? []).filter((a) => a.dataset_id === dataset.id);
  return (
    <div className="col gap-12">
      <Card title="이 데이터셋의 프로버넌스">
        <dl className="kv">
          <dt>작성 활동 (prov:Activity)</dt>
          <dd>{dataset.authoring_activity ? <span className="mono bold">{dataset.authoring_activity}</span> : <span className="muted">기록 없음</span>}</dd>
          <dt>prov:wasGeneratedBy</dt>
          <dd>
            {dataset.authoring_activity ? (
              <>
                <span className="mono">{dataset.resource_id}</span> → <span className="mono">{dataset.authoring_activity}</span>
              </>
            ) : (
              <span className="muted">작성 활동이 없어 기록되지 않습니다</span>
            )}
          </dd>
          <dt>prov:wasAttributedTo</dt>
          <dd>
            {publisher ? (
              <>
                <span className="mono">{dataset.resource_id}</span> → {publisher.label} <span className="mono muted">({publisher.code})</span>
              </>
            ) : (
              <span className="t-warn">제공기관이 승인되지 않아 아직 기록되지 않습니다</span>
            )}
          </dd>
        </dl>
        <p className="small muted mt-8">
          정본 그래프는 이 데이터셋에 prov:wasGeneratedBy → 위 작성 활동, prov:wasAttributedTo → 승인된 제공기관을 기록합니다. 작성 활동은 조합에 편입될 때 자동으로 만들어지고, 승인 · 확정은 아래 활동 기록으로 남습니다.
        </p>
      </Card>

      <Card title="활동 기록" right={<span className="tiny muted">프로세스의 최근 활동 100건 중 이 데이터셋에 해당하는 기록</span>}>
        <QueryState q={q}>
          {rows.length === 0 ? (
            <Empty>이 데이터셋에 기록된 활동이 없습니다</Empty>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>시각</th>
                    <th>Activity ID</th>
                    <th>수행</th>
                    <th>내용</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <tr key={a.id}>
                      <td className="nowrap">{fmtDateTime(a.at)}</td>
                      <td className="mono nowrap">
                        {a.code} {a.code === dataset.authoring_activity && <Badge tone="info">작성 활동</Badge>}
                      </td>
                      <td className="nowrap">
                        {a.actor} {a.agent_type === "software" && <Badge>시스템</Badge>}
                      </td>
                      <td>{a.text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </QueryState>
      </Card>
    </div>
  );
}

// ───────────── ⑥ 원천 프로파일
function ProfileTab({ pid, did }: { pid: number; did: number }) {
  const q = useQuery({ queryKey: ["process", pid, "dataset", did], queryFn: () => api.dataset(did) });
  const asset = q.data?.asset;
  const tables = asset?.profile?.tables ?? [];
  const error = asset?.profile?.error ?? asset?.error ?? null;
  return (
    <QueryState q={q}>
      {asset && (
        <div className="col gap-12">
          <Card
            title={
              <>
                원천 <span className="muted small">{asset.name}</span>
              </>
            }
            right={<Badge>{asset.profile_summary}</Badge>}
          >
            <dl className="kv">
              {asset.filename && (
                <>
                  <dt>파일</dt>
                  <dd>
                    {asset.filename} {asset.size_label && <span className="muted">· {asset.size_label}</span>}
                  </dd>
                </>
              )}
              {asset.data_form && (
                <>
                  <dt>데이터 형태</dt>
                  <dd>{asset.data_form}</dd>
                </>
              )}
              {asset.sha256 && (
                <>
                  <dt>SHA-256</dt>
                  <dd className="mono ellipsis" title={asset.sha256}>
                    {asset.sha256}
                  </dd>
                </>
              )}
            </dl>
            {error && (
              <div className="mt-8">
                <Banner tone="err">{error}</Banner>
              </div>
            )}
            {asset.warnings.length > 0 && (
              <div className="mt-8">
                <Banner tone="warn">
                  <b>프로파일 경고 {asset.warnings.length}건</b>
                  {asset.warnings.map((w) => (
                    <div key={w}>· {w}</div>
                  ))}
                </Banner>
              </div>
            )}
          </Card>
          {tables.length === 0 ? (
            <Empty>프로파일된 표가 없습니다</Empty>
          ) : (
            tables.map((t) => (
              <div key={t.name}>
                <div className="row wrap mb-8">
                  <span className="bold">{t.name}</span>
                  <span className="small muted">
                    {asset.kind === "stream" ? `등록된 스키마 ${fmtNum(t.columns.length)}필드` : `${fmtNum(t.rows)}행 · ${fmtNum(t.columns.length)}컬럼`}
                  </span>
                  {t.truncated && <Badge tone="warn">앞부분만 프로파일</Badge>}
                </div>
                <ProfileTable table={t} asset={asset} />
              </div>
            ))
          )}
        </div>
      )}
    </QueryState>
  );
}

// ───────────── 오른쪽: 미리보기 · 검증
function PreviewPanel(props: { pid: number; dataset: Dataset; fields: MetaField[]; dirtyCount: number; onFocus: (name: string) => void }) {
  const q = usePreview(props.pid, props.dataset.id);
  return (
    <Card
      title="미리보기 · 검증"
      right={
        q.isFetching && !q.isLoading ? (
          <span className="row gap-4 tiny muted">
            <span className="spinner" /> 다시 만드는 중
          </span>
        ) : undefined
      }
    >
      {props.dirtyCount > 0 && <div className="small t-warn mb-8">저장하지 않은 변경 {props.dirtyCount}건은 아직 반영되지 않았습니다.</div>}
      <QueryState q={q}>{q.data && <PreviewBody p={q.data} dataset={props.dataset} fields={props.fields} onFocus={props.onFocus} />}</QueryState>
    </Card>
  );
}

function PreviewBody({ p, dataset, fields, onFocus }: { p: Preview; dataset: Dataset; fields: MetaField[]; onFocus: (name: string) => void }) {
  const [fmt, setFmt] = useState<PreviewFmt>("ttl");
  const [showGate0, setShowGate0] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const v = p.validation;
  const gate0Ok = v.gate0.filter((c) => c.ok).length;

  // 이 화면에서 고칠 수 있는 위반의 대상 필드 (서버가 준 수정 경로에서 뽑는다)
  const jumps: { name: string; label: string; severity: Severity }[] = [];
  for (const r of v.results) {
    if (!r.route || r.route.step !== 3 || !r.route.focus) continue;
    if (r.severity === "Info" && !showInfo) continue;
    const name = FOCUS_ALIAS[r.route.focus] ?? r.route.focus;
    if (jumps.some((j) => j.name === name)) continue;
    const label = name === CLASS_FOCUS ? "추가 클래스" : fields.find((f) => f.name === name)?.label;
    if (label) jumps.push({ name, label, severity: r.severity });
  }

  return (
    <div className="col">
      <div className="row wrap gap-4">
        <span className="mono bold">{p.resource_id}</span>
        {p.readiness.level === "ai-ready" ? <Badge tone="ok">ai-ready</Badge> : <Badge tone="warn">초안 (draft)</Badge>}
        <Badge>{fmtNum(p.triple_count)} 트리플</Badge>
        <span className="tiny muted mono" title={`정본 체크섬 ${p.checksum}`}>
          체크섬 {shortHash(p.checksum)}
        </span>
      </div>

      {p.readiness.missing.length > 0 && (
        <Banner tone="warn">
          <b>필수 결측:</b>{" "}
          {p.readiness.missing.map((name, i) => {
            const def = MISSING[name];
            return (
              <span key={name}>
                {i > 0 && ", "}
                {def ? (
                  <button className="link-btn" title="해당 필드로 이동" onClick={() => onFocus(def.field)}>
                    {def.label}
                  </button>
                ) : (
                  name
                )}
              </span>
            );
          })}
        </Banner>
      )}
      {p.readiness.recommended_missing.length > 0 && (
        <div className="small muted">
          권장 보강:{" "}
          {p.readiness.recommended_missing.map((name, i) => {
            const def = RECOMMENDED[name];
            return (
              <span key={name}>
                {i > 0 && ", "}
                {def?.field ? (
                  <button className="link-btn" title="해당 필드로 이동" onClick={() => onFocus(def.field as string)}>
                    {def.label}
                  </button>
                ) : (
                  def?.label ?? name
                )}
              </span>
            );
          })}
        </div>
      )}

      <div className="mt-4">
        <Tabs<PreviewFmt>
          tabs={[
            { key: "ttl", label: "Turtle" },
            { key: "jsonld", label: "JSON-LD" },
            { key: "txt", label: "문장화" },
          ]}
          value={fmt}
          onChange={setFmt}
        />
        {fmt === "ttl" && <CodeBlock text={p.turtle} maxHeight={340} />}
        {fmt === "jsonld" && <CodeBlock text={p.jsonld} maxHeight={340} />}
        {fmt === "txt" && <CodeBlock text={p.text} wrap light maxHeight={340} />}
      </div>

      <div className="section-title" style={{ marginBottom: 0 }}>
        즉시 검증 {v.passed ? <Badge tone="ok">통과</Badge> : <Badge tone="err">위반 있음</Badge>}
      </div>
      <div className="row wrap gap-4">
        <Badge tone={v.violation_count > 0 ? "err" : "muted"}>Violation {v.violation_count}</Badge>
        <Badge tone={v.warning_count > 0 ? "warn" : "muted"}>Warning {v.warning_count}</Badge>
        <Badge tone={v.info_count > 0 ? "info" : "muted"}>Info {v.info_count}</Badge>
      </div>
      <div className="tiny muted">
        STEP 6 과 같은 검증 엔진(게이트 0 + SHACL)으로 지금 저장된 값을 검사한 결과입니다. 여기서는 실행 기록을 남기지 않습니다 — 정식 검증은 STEP 6 에서 실행합니다.
      </div>

      <div>
        <button className="link-btn small" aria-expanded={showGate0} onClick={() => setShowGate0((x) => !x)}>
          게이트 0 검사 {gate0Ok}/{v.gate0.length} 통과 {showGate0 ? "▴" : "▾"}
        </button>
        {showGate0 && (
          <div className="card tight flat mt-4">
            <Gate0List checks={v.gate0} />
          </div>
        )}
      </div>

      {jumps.length > 0 && (
        <div className="row wrap gap-4 small">
          <span className="muted">이 화면에서 고칠 필드:</span>
          {jumps.map((j) => (
            <button key={j.name} className="link-btn" onClick={() => onFocus(j.name)}>
              {j.label}
              {j.severity === "Violation" ? " (위반)" : ""}
            </button>
          ))}
        </div>
      )}

      <ValidationRows rows={v.results} datasetId={dataset.id} hideInfo={!showInfo} />
      {v.info_count > 0 && (
        <label className="check small">
          <input type="checkbox" checked={showInfo} onChange={(e) => setShowInfo(e.target.checked)} />
          Info {v.info_count}건도 보기
        </label>
      )}
    </div>
  );
}

function ConfirmBox(props: { dataset: Dataset; editable: boolean; busy: string | null; dirtyCount: number; onConfirm: () => void; onUnconfirm: () => void }) {
  const { dataset: d, editable, busy, dirtyCount } = props;
  const missing = d.readiness?.missing ?? [];
  if (d.meta_confirmed_at) {
    return (
      <div className="col gap-4" style={{ flex: "none" }}>
        <Banner
          tone="ok"
          right={
            <button className="link-btn" disabled={!editable || busy !== null} onClick={props.onUnconfirm}>
              {busy === "unconfirm" ? "해제하는 중…" : "확정 해제"}
            </button>
          }
        >
          <b>✓ 메타데이터 확정됨</b> · {fmtDateTime(d.meta_confirmed_at)}
        </Banner>
        {missing.length > 0 && (
          <Banner tone="warn">
            확정한 뒤에 값이나 승인이 바뀌어 필수 필드가 다시 결측입니다 ({missing.map((m) => MISSING[m]?.label ?? m).join(", ")}) — 보강한 뒤 승인하세요.
          </Banner>
        )}
      </div>
    );
  }
  return (
    <div className="card tight col gap-4" style={{ flex: "none" }}>
      <Button variant="primary" block busy={busy === "confirm"} disabled={!editable || busy !== null || dirtyCount > 0} onClick={props.onConfirm}>
        메타데이터 확정
      </Button>
      <div className="tiny muted">
        {dirtyCount > 0
          ? "저장하지 않은 변경이 있습니다 — 먼저 저장하세요."
          : "필수 필드가 채워지고 승인되어 있어야 확정됩니다. 확정은 prov:Activity 로 기록되고 다음 미확정 데이터셋으로 넘어갑니다."}
      </div>
    </div>
  );
}
