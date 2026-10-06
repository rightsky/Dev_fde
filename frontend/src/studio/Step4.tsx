// STEP 4 — 다중분류체계 배정.
// 축·코드는 전부 /taxonomy 에서 오고, 추천은 서버의 규칙 기반 계산 결과(/classification/suggestions)를 그대로 보여 준다.
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { Classification, ClassSuggestion, Dataset, TaxAxis, TaxCode } from "../types";
import { Badge, Banner, Button, Empty, KeyPill, QueryState, cx, errText, fmtDateTime, useToast } from "../ui";
import { useStudio } from "./context";
import { DatasetList, ReadOnlyNote, StepHeader } from "./shared";

// ───────────── 모델

/** PUT /classification 본문이 받는 코드 배열 축 (백엔드 ClassificationIn 의 필드와 같다) */
const F_AXES = ["F1", "F2", "F3", "F4", "F5", "F6"] as const;
type FAxis = (typeof F_AXES)[number];
/** 화면에 그리는 축 순서 */
const AXIS_ORDER: readonly string[] = [...F_AXES, "K", "N2SF"];
/** 비어 있으면 확정이 409 로 거부되는 축 (백엔드 _class_gaps 와 같은 규칙) */
const BLOCKING_AXES: readonly string[] = ["F1", "F2"];
/** F3 코드의 extra.group 표시 순서와 이름 */
const GROUP_ORDER: readonly string[] = ["spatial", "temporal"];
const GROUP_LABEL: Record<string, string> = { spatial: "공간", temporal: "시간" };
const FLASH_MS = 2400;

interface KeyDraft {
  code: string;
  table: string | null;
  column: string | null;
}

interface Draft {
  codes: Record<FAxis, string[]>;
  keys: KeyDraft[];
  n2sf: string | null;
}

interface Thresholds {
  strong: number;
  review: number;
  low: number;
}

/** 한 축의 추천 (점수 내림차순, 활성 코드만) */
interface AxisSuggestions {
  list: ClassSuggestion[];
  byCode: Map<string, ClassSuggestion>;
  th: Thresholds;
}

interface Taxonomy {
  /** 축 코드 → 축 (codes 는 활성 코드만) */
  axes: Map<string, TaxAxis>;
  /** 활성 코드 → 코드 */
  codes: Map<string, TaxCode>;
  /** 화면 순서대로 정렬한 축 */
  ordered: TaxAxis[];
  /** nature 가 '필수' 인 축 */
  required: TaxAxis[];
}

interface TableCols {
  name: string;
  columns: string[];
}

type Busy = "save" | "confirm" | "unconfirm" | null;

const isFAxis = (a: string): a is FAxis => (F_AXES as readonly string[]).includes(a);

function indexTaxonomy(raw: TaxAxis[]): Taxonomy {
  const axes = new Map<string, TaxAxis>();
  const codes = new Map<string, TaxCode>();
  for (const a of raw) {
    const active = a.codes.filter((c) => c.active === true);
    axes.set(a.code, { ...a, codes: active });
    active.forEach((c) => codes.set(c.code, c));
  }
  const ordered = AXIS_ORDER.map((code) => axes.get(code)).filter((a): a is TaxAxis => a !== undefined);
  return { axes, codes, ordered, required: ordered.filter((a) => a.nature === "필수") };
}

function fromServer(cls: Classification | null | undefined): Draft {
  const c = cls ?? {};
  return {
    codes: { F1: [...(c.F1 ?? [])], F2: [...(c.F2 ?? [])], F3: [...(c.F3 ?? [])], F4: [...(c.F4 ?? [])], F5: [...(c.F5 ?? [])], F6: [...(c.F6 ?? [])] },
    keys: (c.K ?? []).map((k) => ({ code: k.code, table: k.table ?? null, column: k.column ?? null })),
    n2sf: c.N2SF ?? null,
  };
}

/** 저장본에 남아 있는 비활성·삭제 코드를 걷어 낸다 (서버는 이런 코드가 든 저장 요청을 422 로 거부한다). */
function dropInactive(d: Draft, tax: Taxonomy): Draft {
  const inAxis = (axis: string, code: string) => tax.axes.get(axis)?.codes.some((c) => c.code === code) ?? false;
  const codes = { ...d.codes };
  for (const a of F_AXES) codes[a] = d.codes[a].filter((c) => inAxis(a, c));
  return { codes, keys: d.keys.filter((k) => inAxis("K", k.code)), n2sf: d.n2sf && inAxis("N2SF", d.n2sf) ? d.n2sf : null };
}

const countCodes = (d: Draft) => F_AXES.reduce((n, a) => n + d.codes[a].length, 0) + d.keys.length + (d.n2sf ? 1 : 0);

/** 순서와 무관한 비교 키. 표는 컬럼이 있을 때만 저장되므로 그때만 비교한다. */
function draftKey(d: Draft): string {
  return JSON.stringify([
    F_AXES.map((a) => [...d.codes[a]].sort()),
    d.keys.map((k) => (k.column ? `${k.code}|${k.table ?? ""}|${k.column}` : k.code)).sort(),
    d.n2sf ?? "",
  ]);
}

function toBody(d: Draft): Classification {
  const body: Classification = {
    F1: d.codes.F1,
    F2: d.codes.F2,
    F3: d.codes.F3,
    F4: d.codes.F4,
    F5: d.codes.F5,
    F6: d.codes.F6,
    K: d.keys.map((k) => (k.column ? { code: k.code, table: k.table, column: k.column } : { code: k.code })),
  };
  if (d.n2sf) body.N2SF = d.n2sf;
  return body;
}

function axisCount(d: Draft, axis: string): number {
  if (axis === "K") return d.keys.length;
  if (axis === "N2SF") return d.n2sf ? 1 : 0;
  return isFAxis(axis) ? d.codes[axis].length : 0;
}

function omit<V>(m: Record<number, V>, id: number): Record<number, V> {
  const next = { ...m };
  delete next[id];
  return next;
}

/** 프로파일의 표·컬럼 이름. 스트림은 등록한 필드가 'stream' 표가 된다. */
function profileTables(d: Dataset): TableCols[] {
  const tables = (d.asset.profile?.tables ?? []).map((t) => ({ name: t.name, columns: t.columns.map((c) => c.name) }));
  if (tables.length > 0) return tables;
  const fields = d.asset.stream?.fields ?? [];
  return d.kind === "stream" && fields.length > 0 ? [{ name: "stream", columns: fields.map((f) => f.name) }] : [];
}

/** 추천이 가리키는 표·컬럼이 프로파일에 실제로 있으면 그 값을, 없으면 빈 값을 돌려준다. */
function bindingFromSuggestion(s: ClassSuggestion | undefined, tables: TableCols[]): { table: string | null; column: string | null } {
  if (!s?.column) return { table: null, column: null };
  if (tables.length === 0) return { table: s.table ?? null, column: s.column };
  const t = tables.find((x) => (s.table ? x.name === s.table : x.columns.includes(s.column as string)));
  return t && t.columns.includes(s.column) ? { table: t.name, column: s.column } : { table: null, column: null };
}

function indexSuggestions(all: ClassSuggestion[], th: Thresholds, tax: Taxonomy): Map<string, AxisSuggestions> {
  const out = new Map<string, AxisSuggestions>();
  for (const axis of tax.ordered) {
    const list = all
      .filter((s) => s.axis === axis.code && axis.codes.some((c) => c.code === s.code))
      .sort((a, b) => b.score - a.score);
    const byCode = new Map<string, ClassSuggestion>();
    for (const s of list) if (!byCode.has(s.code)) byCode.set(s.code, s);
    out.set(axis.code, { list: [...byCode.values()], byCode, th });
  }
  return out;
}

/**
 * 강추천(점수 ≥ strong)을 초안에 더한다.
 * 다중 축은 전부 추가하고, 단일 축은 비어 있을 때만 최고점 1건을 넣는다 — 사람이 이미 고른 값은 덮어쓰지 않는다.
 */
function applyStrong(d: Draft, sugs: Map<string, AxisSuggestions>, tax: Taxonomy, tables: TableCols[]): { next: Draft; added: number } {
  let added = 0;
  const strongOf = (axis: string) => {
    const sv = sugs.get(axis);
    return sv ? sv.list.filter((s) => s.score >= sv.th.strong) : [];
  };
  const codes = { ...d.codes };
  for (const a of F_AXES) {
    const axis = tax.axes.get(a);
    const strong = strongOf(a);
    if (!axis || strong.length === 0) continue;
    if (axis.multi) {
      const fresh = strong.map((s) => s.code).filter((c) => !codes[a].includes(c));
      codes[a] = [...codes[a], ...fresh];
      added += fresh.length;
    } else if (codes[a].length === 0) {
      codes[a] = [strong[0].code];
      added += 1;
    }
  }
  const keys = d.keys.map((k) => ({ ...k }));
  for (const s of strongOf("K")) {
    const b = bindingFromSuggestion(s, tables);
    const cur = keys.find((k) => k.code === s.code);
    if (!cur) {
      keys.push({ code: s.code, ...b });
      added += 1;
    } else if (!cur.column && b.column) {
      cur.table = b.table;
      cur.column = b.column;
      added += 1;
    }
  }
  let n2sf = d.n2sf;
  const grade = strongOf("N2SF")[0];
  if (!n2sf && grade) {
    n2sf = grade.code;
    added += 1;
  }
  return { next: { codes, keys, n2sf }, added };
}

function tier(score: number, th: Thresholds): { label: string; tone: "ok" | "info" | "muted" } {
  if (score >= th.strong) return { label: "강추천", tone: "ok" };
  if (score >= th.review) return { label: "검토", tone: "info" };
  if (score >= th.low) return { label: "참고", tone: "muted" };
  return { label: "해당 낮음", tone: "muted" };
}

function groupCodes(codes: TaxCode[]): { key: string; label: string | null; codes: TaxCode[] }[] {
  const groupOf = (c: TaxCode) => (typeof c.extra.group === "string" && GROUP_ORDER.includes(c.extra.group) ? c.extra.group : "other");
  if (!codes.some((c) => typeof c.extra.group === "string")) return [{ key: "all", label: null, codes }];
  return [...GROUP_ORDER, "other"]
    .map((key) => ({ key, label: GROUP_LABEL[key] ?? "기타", codes: codes.filter((c) => groupOf(c) === key) }))
    .filter((g) => g.codes.length > 0);
}

/** 초안이 정본 그래프에 어떤 속성으로 들어가는지 (backend canonical.py 의 '분류 (STEP 4)' 와 같은 대응) */
function emitRows(d: Draft, tax: Taxonomy, isStream: boolean): { key: string; prop: string; values: string[] }[] {
  const rows: { key: string; prop: string; values: string[] }[] = [];
  const label = (code: string) => tax.codes.get(code)?.label ?? code;
  for (const axis of tax.ordered) {
    const prop = axis.rdf_property ?? axis.code;
    if (axis.code === "K") {
      rows.push({ key: "K", prop, values: d.keys.map((k) => `${k.code} (${k.column ?? "컬럼 미지정"})`) });
    } else if (axis.code === "N2SF") {
      rows.push({ key: "N2SF", prop, values: d.n2sf ? [d.n2sf.replace(/^N2SF-/, "")] : [] });
    } else if (axis.code === "F4") {
      const picked = d.codes.F4;
      if (picked.length === 0) rows.push({ key: "F4", prop, values: [] });
      for (const code of picked) {
        const isLicense = tax.codes.get(code)?.extra.property === "dcterms:license";
        rows.push({ key: `F4-${code}`, prop: isLicense ? "dcterms:license" : "dcterms:accessRights", values: [label(code)] });
      }
    } else if (isFAxis(axis.code)) {
      rows.push({ key: axis.code, prop, values: d.codes[axis.code].map(label) });
      if (axis.code === "F3" && !isStream) {
        const meters = d.codes.F3.map((c) => tax.codes.get(c)?.extra.meters).filter((m): m is number => typeof m === "number");
        if (meters.length > 0) rows.push({ key: "F3-meters", prop: "dcat:spatialResolutionInMeters", values: meters.map(String) });
      }
    }
  }
  return rows;
}

// ───────────── 화면

interface ConfirmNotice {
  datasetId: number;
  title: string;
  warnings: string[];
}

export function Step4() {
  const { combo, params, guard } = useStudio();
  const toast = useToast();
  const taxQ = useQuery({ queryKey: ["taxonomy"], queryFn: () => api.taxonomy() });
  const tax = useMemo(() => indexTaxonomy(taxQ.data ?? []), [taxQ.data]);
  const ready = taxQ.data != null;

  const [selId, setSelId] = useState<number | null>(params.dataset);
  /** 저장하지 않은 편집본. 데이터셋을 오가도 유지되고, 저장·취소하면 지운다. */
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [notice, setNotice] = useState<ConfirmNotice | null>(null);
  const [flashAxis, setFlashAxis] = useState<string | null>(null);

  // 다른 단계에서 넘어온 선택 데이터셋·강조 축
  useEffect(() => {
    if (params.dataset != null) setSelId(params.dataset);
  }, [params.dataset]);
  useEffect(() => {
    if (ready && params.focus && tax.axes.has(params.focus)) setFlashAxis(params.focus);
    // tax 는 ready 와 함께 바뀌므로 의존성에 따로 넣지 않는다
  }, [ready, params.focus, params.dataset]);
  useEffect(() => {
    if (!flashAxis) return;
    const t = setTimeout(() => setFlashAxis(null), FLASH_MS);
    return () => clearTimeout(t);
  }, [flashAxis]);

  const selected = combo.find((d) => d.id === selId) ?? combo.find((d) => !d.class_confirmed_at) ?? combo[0] ?? null;
  const server = useMemo(() => (selected ? fromServer(selected.classification) : null), [selected]);
  const cleaned = useMemo(() => (server ? dropInactive(server, tax) : null), [server, tax]);

  const unsaved = useMemo(() => {
    const ids = new Set<number>();
    for (const d of combo) {
      const draft = drafts[d.id];
      if (draft && draftKey(draft) !== draftKey(fromServer(d.classification))) ids.add(d.id);
    }
    return ids;
  }, [combo, drafts]);
  // 저장하지 않은 분류 변경이 있으면 단계 이동 전에 확인을 받는다
  useEffect(() => {
    guard.current = () => unsaved.size > 0;
    return () => {
      guard.current = null;
    };
  }, [unsaved, guard]);

  const change = (fn: (d: Draft) => Draft) => {
    if (!selected || !cleaned) return;
    const did = selected.id;
    const baseKey = draftKey(cleaned);
    setDrafts((m) => {
      const next = fn(m[did] ?? cleaned);
      return draftKey(next) === baseKey ? omit(m, did) : { ...m, [did]: next };
    });
  };

  const onConfirmed = (ds: Dataset, warnings: string[]) => {
    const i = combo.findIndex((d) => d.id === ds.id);
    const next = [...combo.slice(i + 1), ...combo.slice(0, Math.max(i, 0))].find((d) => d.id !== ds.id && !d.class_confirmed_at);
    setNotice(warnings.length > 0 ? { datasetId: ds.id, title: ds.title, warnings } : null);
    setSelId(next ? next.id : ds.id);
    toast.ok(
      next
        ? `분류를 확정했습니다 — 다음 미확정 데이터셋 '${next.title}' (으)로 이동합니다`
        : "조합의 모든 데이터셋 분류를 확정했습니다 — STEP 5 관계로 진행할 수 있습니다",
    );
  };

  const requiredFilled = (d: Dataset) => {
    const saved = fromServer(d.classification);
    return tax.required.filter((a) => axisCount(saved, a.code) > 0).length;
  };
  const blockingEmpty = (d: Dataset) => {
    const saved = fromServer(d.classification);
    return BLOCKING_AXES.some((a) => tax.axes.has(a) && axisCount(saved, a) === 0);
  };

  return (
    <>
      <StepHeader
        n={4}
        title="다중분류체계 배정"
        sub="축마다 코드를 배정하고 확정합니다. 배정한 분류는 정본 그래프(dcat:theme · dcterms:type · dcterms:license 등)에 들어가 STEP 6 검증과 STEP 7 산출물에 반영됩니다."
      />
      <QueryState q={taxQ}>
        {combo.length === 0 ? (
          <Empty>조합에 편입된 데이터셋이 없습니다 — STEP 2 에서 조합을 확정하면 여기서 분류를 배정할 수 있습니다</Empty>
        ) : tax.ordered.length === 0 ? (
          <Empty>등록된 분류 축이 없습니다 — 관리 화면의 분류체계를 확인하세요</Empty>
        ) : (
          <div className="col gap-12">
            <ReadOnlyNote />
            {notice && (
              <Banner
                tone="warn"
                right={
                  <div className="row">
                    {selected?.id !== notice.datasetId && (
                      <Button size="sm" onClick={() => setSelId(notice.datasetId)}>
                        해당 데이터셋 열기
                      </Button>
                    )}
                    <Button size="sm" onClick={() => setNotice(null)}>
                      닫기
                    </Button>
                  </div>
                }
              >
                <b>'{notice.title}' 분류는 확정되었습니다.</b> 다만 필수 축이 아직 비어 있습니다: {notice.warnings.join(", ")} — STEP 6 검증에서 Warning 으로 표시됩니다.
              </Banner>
            )}
            <div className="grid" style={{ gridTemplateColumns: "260px minmax(0, 1fr) 320px", alignItems: "start" }}>
              <DatasetList
                datasets={combo}
                selectedId={selected?.id ?? null}
                onSelect={setSelId}
                status={(d) => {
                  const n = requiredFilled(d);
                  const total = tax.required.length;
                  return (
                    <>
                      {d.class_confirmed_at ? <Badge tone="ok">확정</Badge> : <Badge>미확정</Badge>}
                      <Badge tone={n === total ? "ok" : blockingEmpty(d) ? "err" : "warn"} title="저장된 분류 기준">
                        필수 축 {n}/{total}
                      </Badge>
                      {unsaved.has(d.id) && <Badge tone="info">미저장</Badge>}
                    </>
                  );
                }}
              />
              {selected && server && cleaned && (
                <Workbench
                  key={selected.id}
                  ds={selected}
                  tax={tax}
                  current={drafts[selected.id] ?? cleaned}
                  serverKey={draftKey(server)}
                  edited={selected.id in drafts}
                  dropped={countCodes(server) - countCodes(cleaned)}
                  flashAxis={flashAxis}
                  onJump={setFlashAxis}
                  onChange={change}
                  onDiscard={() => setDrafts((m) => omit(m, selected.id))}
                  onConfirmed={(warnings) => onConfirmed(selected, warnings)}
                />
              )}
            </div>
          </div>
        )}
      </QueryState>
    </>
  );
}

// ───────────── 가운데 편집기 + 오른쪽 요약 (선택한 데이터셋 1건)

function Workbench(props: {
  ds: Dataset;
  tax: Taxonomy;
  current: Draft;
  /** 서버 저장본의 비교 키 */
  serverKey: string;
  /** 사용자가 손댄 편집본이 있는가 */
  edited: boolean;
  /** 저장본에서 걷어 낸 비활성 코드 수 */
  dropped: number;
  flashAxis: string | null;
  onJump: (axis: string) => void;
  onChange: (fn: (d: Draft) => Draft) => void;
  onDiscard: () => void;
  onConfirmed: (warnings: string[]) => void;
}) {
  const { ds, tax, current, onChange } = props;
  const { pid, editable, refresh } = useStudio();
  const toast = useToast();
  const did = ds.id;
  const [busy, setBusy] = useState<Busy>(null);
  const locked = !editable || busy !== null;
  const dirty = draftKey(current) !== props.serverKey;
  const confirmed = ds.class_confirmed_at != null;

  const sugQ = useQuery({ queryKey: ["process", pid, "dataset", did, "classSuggestions"], queryFn: () => api.classSuggestions(did) });
  const dsQ = useQuery({ queryKey: ["process", pid, "dataset", did], queryFn: () => api.dataset(did) });

  const tables = useMemo(() => profileTables(dsQ.data ?? ds), [dsQ.data, ds]);
  const sugs = useMemo(
    () => (sugQ.data ? indexSuggestions(sugQ.data.suggestions, sugQ.data.thresholds, tax) : new Map<string, AxisSuggestions>()),
    [sugQ.data, tax],
  );
  const strongPlan = useMemo(() => applyStrong(current, sugs, tax, tables), [current, sugs, tax, tables]);

  const blockingMissing = BLOCKING_AXES.map((a) => tax.axes.get(a)).filter((a): a is TaxAxis => a !== undefined && axisCount(current, a.code) === 0);

  const toggleCode = (axis: FAxis, code: string, multi: boolean) =>
    onChange((d) => {
      const cur = d.codes[axis];
      const next = cur.includes(code) ? cur.filter((c) => c !== code) : multi ? [...cur, code] : [code];
      return { ...d, codes: { ...d.codes, [axis]: next } };
    });
  const toggleKey = (code: string) =>
    onChange((d) =>
      d.keys.some((k) => k.code === code)
        ? { ...d, keys: d.keys.filter((k) => k.code !== code) }
        : { ...d, keys: [...d.keys, { code, ...bindingFromSuggestion(sugs.get("K")?.byCode.get(code), tables) }] },
    );
  const patchKey = (code: string, patch: Partial<KeyDraft>) => onChange((d) => ({ ...d, keys: d.keys.map((k) => (k.code === code ? { ...k, ...patch } : k)) }));
  const setGrade = (code: string) => onChange((d) => ({ ...d, n2sf: d.n2sf === code ? null : code }));

  const save = async () => {
    setBusy("save");
    try {
      await api.putClassification(did, toBody(current));
      await refresh();
      props.onDiscard();
      toast.ok(confirmed ? "분류를 저장했습니다 — 확정 상태는 유지되고, 이전 검증·산출 결과는 다시 실행해야 합니다" : "분류를 저장했습니다");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  const confirm = async () => {
    setBusy("confirm");
    let saved = false;
    try {
      if (dirty) {
        await api.putClassification(did, toBody(current));
        saved = true;
      }
      const res = await api.confirmClassification(did);
      await refresh();
      props.onDiscard();
      props.onConfirmed(res.warnings ?? []);
    } catch (e) {
      toast.error(e);
      if (saved) {
        // 저장은 끝났고 확정만 거부된 경우 — 화면을 서버 저장본에 맞춘다
        await refresh().catch(() => undefined);
        props.onDiscard();
      }
    } finally {
      setBusy(null);
    }
  };

  const unconfirm = async () => {
    setBusy("unconfirm");
    try {
      await api.unconfirmClassification(did);
      await refresh();
      toast.ok("분류 확정을 해제했습니다");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  const th = sugQ.data?.thresholds;

  return (
    <>
      <div className="col gap-12" style={{ minWidth: 0 }}>
        <div className="card tight row between wrap top">
          <div className="col gap-4 grow">
            <div className="row wrap">
              <span className="bold">{ds.title}</span>
              <span className="mono tiny muted">{ds.resource_id}</span>
              {dirty && <Badge tone="info">미저장 변경</Badge>}
            </div>
            {sugQ.isLoading && <div className="small muted">규칙 기반 추천을 계산하는 중…</div>}
            {sugQ.error != null && <div className="small t-err">추천을 불러오지 못했습니다 — {errText(sugQ.error)} · 코드는 직접 선택할 수 있습니다</div>}
            {sugQ.data && th && (
              <div className="small muted">
                {sugQ.data.method} · 점수 {th.strong} 이상 강추천 · {th.review}~{th.strong - 1} 검토 · {th.low} 미만 해당 낮음
              </div>
            )}
          </div>
          <div className="row">
            <Button
              size="sm"
              variant="outline"
              disabled={locked || strongPlan.added === 0}
              title="다중 축은 강추천을 모두 더하고, 단일 축은 비어 있을 때만 최고점 1건을 넣습니다. 저장 전까지는 반영되지 않습니다."
              onClick={() => {
                onChange(() => strongPlan.next);
                toast(`강추천 ${strongPlan.added}건을 적용했습니다 — 검토한 뒤 저장하세요`);
              }}
            >
              강추천 전체 적용{strongPlan.added > 0 ? ` (${strongPlan.added})` : ""}
            </Button>
            <Button size="sm" disabled={locked || !props.edited} onClick={props.onDiscard}>
              변경 취소
            </Button>
          </div>
        </div>

        {confirmed && (
          <Banner
            tone="ok"
            right={
              <Button size="sm" disabled={!editable || (busy !== null && busy !== "unconfirm")} busy={busy === "unconfirm"} onClick={unconfirm}>
                확정 해제
              </Button>
            }
          >
            <b>✓ 분류 확정됨</b> · {fmtDateTime(ds.class_confirmed_at)}
            <div className="small">확정한 뒤에도 수정할 수 있습니다. 저장하면 확정 상태는 그대로이고, 이전 검증·직렬화·진단 결과는 서버가 재실행 필요로 표시합니다.</div>
          </Banner>
        )}
        {props.dropped > 0 && (
          <Banner tone="warn">저장본에 비활성 코드 {props.dropped}건이 남아 있어 편집본에서 제외했습니다 — 저장하면 저장본에서도 빠집니다.</Banner>
        )}

        {tax.ordered.map((axis) => {
          const sv = sugs.get(axis.code);
          const count = axisCount(current, axis.code);
          return (
            <AxisCard key={axis.code} axis={axis} count={count} flash={props.flashAxis === axis.code}>
              {axis.codes.length === 0 ? (
                <Empty>활성 코드가 없습니다 — 관리 화면의 분류체계에서 코드를 추가하거나 활성화하세요</Empty>
              ) : axis.code === "K" ? (
                <KeyAxis axis={axis} keys={current.keys} sv={sv} tables={tables} profileQ={dsQ} locked={locked} onToggle={toggleKey} onPatch={patchKey} />
              ) : axis.code === "N2SF" ? (
                <GradeAxis axis={axis} value={current.n2sf} sv={sv} locked={locked} onPick={setGrade} />
              ) : isFAxis(axis.code) ? (
                <ChipAxis axis={axis} selected={current.codes[axis.code]} sv={sv} locked={locked} onToggle={(code) => toggleCode(axis.code as FAxis, code, axis.multi)} />
              ) : null}
            </AxisCard>
          );
        })}

        <div className="card tight row between wrap" style={{ position: "sticky", bottom: 0, zIndex: 2 }}>
          <div className="small grow">
            {blockingMissing.length > 0 ? (
              <span className="t-err bold">{blockingMissing.map((a) => `${a.code} ${a.name}`).join(" · ")} 축을 배정해야 확정할 수 있습니다</span>
            ) : dirty ? (
              <span className="t-warn bold">저장하지 않은 변경이 있습니다</span>
            ) : (
              <span className="muted">편집본이 저장본과 같습니다</span>
            )}
          </div>
          <div className="row">
            <Button disabled={!editable || !dirty || busy !== null} busy={busy === "save"} onClick={save}>
              분류 저장
            </Button>
            {!confirmed && (
              <Button
                variant="primary"
                disabled={!editable || blockingMissing.length > 0 || busy !== null}
                busy={busy === "confirm"}
                title={dirty ? "변경을 먼저 저장한 뒤 확정합니다" : undefined}
                onClick={confirm}
              >
                분류 확정
              </Button>
            )}
          </div>
        </div>
      </div>

      <SummaryCard ds={ds} tax={tax} current={current} onJump={props.onJump} />
    </>
  );
}

// ───────────── 축 카드

function AxisCard({ axis, count, flash, children }: { axis: TaxAxis; count: number; flash: boolean; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (flash) ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [flash]);
  const natureTone = axis.nature === "필수" ? "err" : axis.nature === "권장" ? "warn" : "muted";
  const required = axis.nature === "필수";
  return (
    <div ref={ref} className={cx("card", flash && "flash")}>
      <div className="card-head">
        <div className="card-title">
          <span>
            {axis.code} {axis.name}
          </span>
          <Badge tone={natureTone}>{axis.nature}</Badge>
          <Badge>{axis.multi ? "다중" : "단일"}</Badge>
          {axis.rdf_property && <span className="kbd">{axis.rdf_property}</span>}
        </div>
        {count > 0 ? (
          <Badge tone="ok">{count}건 배정</Badge>
        ) : (
          <Badge tone={required ? "err" : "muted"}>{BLOCKING_AXES.includes(axis.code) ? "미배정 · 확정 불가" : "미배정"}</Badge>
        )}
      </div>
      {axis.description && <div className="small muted mb-8">{axis.description}</div>}
      {children}
    </div>
  );
}

function ScoreChip(props: { label: string; hint?: string | null; on: boolean; disabled: boolean; s?: ClassSuggestion; th?: Thresholds; onClick: () => void }) {
  const { s, th } = props;
  const strong = s != null && th != null && s.score >= th.strong;
  const weak = s != null && th != null && s.score < th.low;
  const title = s && th ? `규칙 기반 추천 ${s.score}점 (${tier(s.score, th).label}) — ${s.reason}` : props.hint || undefined;
  return (
    <button
      type="button"
      className={cx("chip", props.on && "on", weak && "dim")}
      style={strong ? { borderColor: "var(--green)" } : undefined}
      aria-pressed={props.on}
      disabled={props.disabled}
      title={title}
      onClick={props.onClick}
    >
      {props.label}
      {s && <span className="score">{s.score}</span>}
    </button>
  );
}

/** 칩 아래의 추천 근거 줄 (상위 3건) */
function SuggestionLines(props: {
  sv: AxisSuggestions | undefined;
  labelOf: (s: ClassSuggestion) => string;
  isOn: (code: string) => boolean;
  onPick: (s: ClassSuggestion) => void;
  locked: boolean;
}) {
  const { sv } = props;
  if (!sv) return null;
  if (sv.list.length === 0) return <div className="small muted mt-8">이 축에는 규칙 기반 추천이 없습니다 — 직접 선택합니다</div>;
  return (
    <div className="col gap-4 mt-8">
      <div className="tiny bold muted">추천 (규칙 기반 · 상위 {Math.min(3, sv.list.length)}건)</div>
      {sv.list.slice(0, 3).map((s) => {
        const t = tier(s.score, sv.th);
        return (
          <div key={s.code} className="row top small">
            <Badge tone={t.tone}>
              {t.label} {s.score}
            </Badge>
            <span className="bold nowrap">{props.labelOf(s)}</span>
            <span className="muted grow">{s.reason}</span>
            {props.isOn(s.code) ? (
              <span className="tiny t-ok bold nowrap">✓ 배정됨</span>
            ) : (
              <button type="button" className="link-btn tiny nowrap" disabled={props.locked} onClick={() => props.onPick(s)}>
                배정
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** F1~F6: 코드 칩. 단일 축은 라디오처럼 동작하고, 선택된 칩을 다시 누르면 해제된다. */
function ChipAxis(props: { axis: TaxAxis; selected: string[]; sv: AxisSuggestions | undefined; locked: boolean; onToggle: (code: string) => void }) {
  const { axis, selected, sv } = props;
  const groups = groupCodes(axis.codes);
  const labelOf = (s: ClassSuggestion) => axis.codes.find((c) => c.code === s.code)?.label ?? s.code;
  return (
    <>
      <div className="col">
        {groups.map((g) => (
          <div key={g.key} className="row wrap top" role="group" aria-label={g.label ?? axis.name}>
            {g.label && (
              <span className="small bold dim nowrap" style={{ width: 32, lineHeight: "30px" }}>
                {g.label}
              </span>
            )}
            <div className="row wrap grow">
              {g.codes.map((c) => (
                <ScoreChip
                  key={c.code}
                  label={c.label}
                  hint={c.definition ? `${c.code} — ${c.definition}` : c.code}
                  on={selected.includes(c.code)}
                  disabled={props.locked}
                  s={sv?.byCode.get(c.code)}
                  th={sv?.th}
                  onClick={() => props.onToggle(c.code)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      <SuggestionLines sv={sv} labelOf={labelOf} isOn={(code) => selected.includes(code)} onPick={(s) => props.onToggle(s.code)} locked={props.locked} />
    </>
  );
}

/** K: 연계키 칩 + 배정한 키마다 표·컬럼 매핑 */
function KeyAxis(props: {
  axis: TaxAxis;
  keys: KeyDraft[];
  sv: AxisSuggestions | undefined;
  tables: TableCols[];
  profileQ: { isLoading: boolean; error: unknown; data: unknown };
  locked: boolean;
  onToggle: (code: string) => void;
  onPatch: (code: string, patch: Partial<KeyDraft>) => void;
}) {
  const { axis, keys, sv, tables } = props;
  const codeOf = (code: string) => axis.codes.find((c) => c.code === code);
  const bound = (code: string) => keys.some((k) => k.code === code);
  return (
    <>
      <div className="row wrap">
        {axis.codes.map((c) => (
          <ScoreChip
            key={c.code}
            label={`${c.code} ${c.label}`}
            hint={c.definition}
            on={bound(c.code)}
            disabled={props.locked}
            s={sv?.byCode.get(c.code)}
            th={sv?.th}
            onClick={() => props.onToggle(c.code)}
          />
        ))}
      </div>

      {keys.length > 0 && (
        <div className="col mt-12">
          <div className="tiny bold muted">매핑 컬럼 — 배정한 키가 이 데이터셋의 어느 컬럼인지 지정합니다</div>
          <QueryState q={props.profileQ}>
            {tables.length === 0 && <div className="small t-warn">프로파일된 컬럼이 없는 원천입니다 — 컬럼 매핑 없이 키만 배정됩니다 (검증에서 Warning)</div>}
            {keys.map((k) => (
              <KeyBindingRow
                key={k.code}
                binding={k}
                label={codeOf(k.code)?.label ?? null}
                suggestion={sv?.byCode.get(k.code)}
                tables={tables}
                locked={props.locked}
                onPatch={(patch) => props.onPatch(k.code, patch)}
                onRemove={() => props.onToggle(k.code)}
              />
            ))}
          </QueryState>
        </div>
      )}

      <SuggestionLines
        sv={sv}
        labelOf={(s) => `${s.code} ${codeOf(s.code)?.label ?? ""}${s.column ? ` → ${s.table ? `${s.table}.` : ""}${s.column}` : ""}`}
        isOn={bound}
        onPick={(s) => props.onToggle(s.code)}
        locked={props.locked}
      />
    </>
  );
}

function KeyBindingRow(props: {
  binding: KeyDraft;
  label: string | null;
  suggestion: ClassSuggestion | undefined;
  tables: TableCols[];
  locked: boolean;
  onPatch: (patch: Partial<KeyDraft>) => void;
  onRemove: () => void;
}) {
  const { binding: b, tables } = props;
  // 표가 하나뿐이면 (스트림의 'stream' 포함) 그 표로 고정한다
  const table = b.table ?? (tables.length === 1 ? tables[0].name : null);
  const columns = tables.find((t) => t.name === table)?.columns ?? [];
  const tableNames = tables.map((t) => t.name);
  const strayTable = b.table != null && !tableNames.includes(b.table);
  const strayColumn = b.column != null && !columns.includes(b.column);
  const suggested = bindingFromSuggestion(props.suggestion, tables);
  const canApplySuggestion = suggested.column != null && (suggested.column !== b.column || suggested.table !== b.table);

  const onTable = (name: string) => {
    const next = name || null;
    const cols = tables.find((t) => t.name === next)?.columns ?? [];
    props.onPatch({ table: next, column: b.column && cols.includes(b.column) ? b.column : null });
  };

  return (
    <div className="row wrap">
      <KeyPill code={b.code} label={props.label} />
      <span className="muted">→</span>
      {tables.length > 0 && (
        <>
          <select className="select" style={{ width: 150 }} aria-label={`${b.code} 표`} value={table ?? ""} disabled={props.locked} onChange={(e) => onTable(e.target.value)}>
            <option value="">표 선택</option>
            {tableNames.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
            {strayTable && <option value={b.table as string}>{b.table} (프로파일에 없음)</option>}
          </select>
          <select
            className="select"
            style={{ width: 180 }}
            aria-label={`${b.code} 컬럼`}
            value={b.column ?? ""}
            disabled={props.locked || table == null}
            onChange={(e) => props.onPatch({ table, column: e.target.value || null })}
          >
            <option value="">{table == null ? "표를 먼저 선택" : "컬럼 선택"}</option>
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
            {strayColumn && <option value={b.column as string}>{b.column} (프로파일에 없음)</option>}
          </select>
        </>
      )}
      {tables.length === 0 && b.column && (
        <span className="mono small">
          {b.table ? `${b.table}.` : ""}
          {b.column}
        </span>
      )}
      {!b.column && tables.length > 0 && <span className="small t-warn">매핑 컬럼 미지정 — 검증에서 Warning</span>}
      {b.column && (strayColumn || strayTable) && tables.length > 0 && <span className="small t-err">프로파일에 없는 컬럼 — 저장이 거부됩니다</span>}
      {canApplySuggestion && (
        <button
          type="button"
          className="link-btn small"
          disabled={props.locked}
          title={props.suggestion ? `규칙 기반 추천 ${props.suggestion.score}점 — ${props.suggestion.reason}` : undefined}
          onClick={() => props.onPatch(suggested)}
        >
          추천 컬럼 적용 ({suggested.column})
        </button>
      )}
      <span className="grow" />
      <button type="button" className="link-btn danger small" disabled={props.locked} onClick={props.onRemove}>
        제거
      </button>
    </div>
  );
}

/** N2SF: 등급 카드 3개 (라디오). 선택된 카드를 다시 누르면 미지정으로 돌아간다. */
function GradeAxis(props: { axis: TaxAxis; value: string | null; sv: AxisSuggestions | undefined; locked: boolean; onPick: (code: string) => void }) {
  const { axis, value, sv } = props;
  return (
    <>
      <div className="grid c3" role="radiogroup" aria-label={axis.name}>
        {axis.codes.map((c) => {
          const s = sv?.byCode.get(c.code);
          const on = value === c.code;
          return (
            <button
              key={c.code}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={props.locked}
              className={cx("card tight", !props.locked && "clickable", on && "selected")}
              style={{ textAlign: "left", width: "100%" }}
              title={s ? `규칙 기반 추천 ${s.score}점 — ${s.reason}` : undefined}
              onClick={() => props.onPick(c.code)}
            >
              <div className="row between">
                <span className="bold">
                  {on ? "● " : "○ "}
                  {c.label}
                </span>
                {s && sv && <Badge tone={tier(s.score, sv.th).tone}>추천 {s.score}</Badge>}
              </div>
              {c.definition && <div className="small muted mt-4">{c.definition}</div>}
            </button>
          );
        })}
      </div>
      <SuggestionLines
        sv={sv}
        labelOf={(s) => axis.codes.find((c) => c.code === s.code)?.label ?? s.code}
        isOn={(code) => value === code}
        onPick={(s) => props.onPick(s.code)}
        locked={props.locked}
      />
      <div className="small dim mt-8">등급은 담당자가 결정합니다. 추천은 컬럼 프로파일에서 계산한 참고 정보이며 자동으로 적용되지 않습니다.</div>
    </>
  );
}

// ───────────── 오른쪽 요약

function SummaryCard({ ds, tax, current, onJump }: { ds: Dataset; tax: Taxonomy; current: Draft; onJump: (axis: string) => void }) {
  const { combo, go } = useStudio();
  const rows = emitRows(current, tax, ds.kind === "stream");
  const missing = tax.required.filter((a) => axisCount(current, a.code) === 0);
  const unbound = current.keys.filter((k) => !k.column).length;
  const confirmedCount = combo.filter((d) => d.class_confirmed_at).length;
  const allConfirmed = combo.length > 0 && confirmedCount === combo.length;
  return (
    <div className="card" style={{ position: "sticky", top: 0 }}>
      <div className="card-head">
        <div className="card-title">정본 반영 미리보기</div>
        <Badge title="저장하지 않은 변경도 포함합니다">편집본 기준</Badge>
      </div>
      <dl className="kv">
        {rows.map((r) => (
          <Fragment key={r.key}>
            <dt className="mono">
              {r.prop.split("|").map((p) => (
                <div key={p}>{p.trim()}</div>
              ))}
            </dt>
            <dd>{r.values.length > 0 ? r.values.join(", ") : <span className="muted">— 방출 없음</span>}</dd>
          </Fragment>
        ))}
      </dl>
      <div className="tiny muted mt-8">저장하면 이 값이 정본 그래프에 들어가고, STEP 6 검증과 STEP 7 산출물에 반영됩니다.</div>

      <hr className="divider" />
      <div className="small bold dim mb-8">필수 축 결측</div>
      {missing.length === 0 ? (
        <div className="small t-ok bold">✓ 필수 축 {tax.required.length}개가 모두 배정되었습니다</div>
      ) : (
        <div className="col gap-4">
          {missing.map((a) => (
            <div key={a.code} className="row between small">
              <button type="button" className="link-btn" title="해당 축으로 이동" onClick={() => onJump(a.code)}>
                {a.code} {a.name}
              </button>
              {BLOCKING_AXES.includes(a.code) ? <Badge tone="err">확정 불가</Badge> : <Badge tone="warn">검증 Warning</Badge>}
            </div>
          ))}
        </div>
      )}
      {unbound > 0 && (
        <div className="row between small mt-4">
          <button type="button" className="link-btn" title="해당 축으로 이동" onClick={() => onJump("K")}>
            연계키 {unbound}건 매핑 컬럼 미지정
          </button>
          <Badge tone="warn">검증 Warning</Badge>
        </div>
      )}

      <hr className="divider" />
      <div className="row between small">
        <span className="dim">조합 분류 확정</span>
        <span className={cx("bold", allConfirmed && "t-ok")}>
          {confirmedCount}/{combo.length}
        </span>
      </div>
      {allConfirmed ? (
        <Button variant="outline" block style={{ marginTop: 8 }} onClick={() => go(5)}>
          STEP 5 관계로 →
        </Button>
      ) : (
        <div className="tiny muted mt-4">조합의 모든 데이터셋을 확정하면 STEP 5 관계로 넘어가는 버튼이 나타납니다.</div>
      )}
    </div>
  );
}
