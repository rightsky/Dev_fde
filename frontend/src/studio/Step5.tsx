// STEP 5 — 관계(JOINED_ON · GROUPED_WITH · DERIVED_FROM) 지정·확정, 리니지 게이트, LPG 그래프 보기.
// 그래프는 서버가 저장된 데이터에서 매번 다시 만든 노드·엣지를 그대로 그린다 (배치만 화면에서 계산).
import { useId, useMemo, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { keepPreviousData, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type {
  Dataset,
  GraphData,
  GraphEdge,
  GraphNode,
  JoinStats,
  NodeType,
  Reference,
  Relation,
  RelationCandidate,
  RelationType,
  RelationsPayload,
} from "../types";
import { Badge, Banner, Button, Card, ConfirmButton, Empty, Field, KeyPill, Meter, Modal, QueryState, Tabs, errText, fmtDateTime, fmtNum, fmtPct, useToast } from "../ui";
import { useStudio } from "./context";
import { ReadOnlyNote, StepHeader } from "./shared";

// ───────────── 공용 타입 · 도우미
type RelTypes = Reference["relation_types"];
type ColRef = { table: string; column: string };
type TableOpt = { name: string; columns: { name: string; type: string }[] };
type TableState = { tables: TableOpt[]; loading: boolean; error: string | null };
type KeyOpt = { code: string; label: string };
type CreateBody = Parameters<typeof api.createRelation>[1];
type UpdateBody = Parameters<typeof api.updateRelation>[1];
/** 변경 요청 1건을 실행한다. 성공하면 true. */
type Act = (key: string, fn: () => Promise<RelationsPayload>, okText: string) => Promise<boolean>;

const EMPTY_REF: ColRef = { table: "", column: "" };
const NO_TABLES: TableState = { tables: [], loading: false, error: null };

/** 상세 조회(프로파일)에서 표·컬럼 선택지를 만든다. 스트림은 표 이름이 "stream" 이다. */
function tableOptions(base: Dataset, full: Dataset | undefined): TableOpt[] {
  const tables = full?.asset.profile?.tables ?? [];
  if (tables.length > 0) return tables.map((t) => ({ name: t.name, columns: t.columns.map((c) => ({ name: c.name, type: c.type })) }));
  const fields = (full ?? base).asset.stream?.fields ?? [];
  if (base.kind === "stream" && fields.length > 0) return [{ name: "stream", columns: fields.map((f) => ({ name: f.name, type: f.type })) }];
  return [];
}

/** 표가 1개뿐이면 표를 고르지 않아도 그 표로 본다. */
function resolveRef(ref: ColRef, tables: TableOpt[]): ColRef {
  const table = ref.table || (tables.length === 1 ? tables[0].name : "");
  return { table, column: ref.column };
}

/** 연계키 코드에 해당하는 컬럼 제안: STEP 4 에서 배정한 컬럼이 먼저, 없으면 프로파일 키 후보 중 점수가 가장 높은 것. */
function suggestRef(d: Dataset | undefined, code: string): ColRef {
  if (!d || !code) return EMPTY_REF;
  const bound = (d.classification.K ?? []).find((k) => k.code === code && k.column);
  if (bound?.column) return { table: bound.table || (d.kind === "stream" ? "stream" : ""), column: bound.column };
  const cand = d.asset.key_candidates.filter((k) => k.code === code).sort((a, b) => b.score - a.score)[0];
  return cand ? { table: cand.table, column: cand.column } : EMPTY_REF;
}

const refText = (table: string | null, column: string | null) => (column ? `${table ? `${table}.` : ""}${column}` : "미지정");
const orNull = (s: string) => (s ? s : null);

// ───────────── 화면
export function Step5() {
  const { pid, combo, reference, editable, refresh } = useStudio();
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [waiverOpen, setWaiverOpen] = useState(false);

  const q = useQuery({ queryKey: ["process", pid, "relations"], queryFn: () => api.relations(pid) });
  const multi = combo.length >= 2;

  // 컬럼 선택지: 조합 데이터셋마다 상세(프로파일)를 읽는다
  const details = useQueries({
    queries: combo.map((d) => ({ queryKey: ["process", pid, "dataset", d.id], queryFn: () => api.dataset(d.id), enabled: multi })),
  });
  const tablesOf = (id: number | null): TableState => {
    const i = combo.findIndex((d) => d.id === id);
    if (i < 0) return NO_TABLES;
    const dq = details[i];
    return { tables: tableOptions(combo[i], dq?.data), loading: !!dq?.isLoading, error: dq?.error ? errText(dq.error) : null };
  };

  const keyOptions: KeyOpt[] = useMemo(
    () =>
      Object.entries(reference.key_labels)
        .map(([code, label]) => ({ code, label }))
        .sort((a, b) => a.code.localeCompare(b.code)),
    [reference.key_labels],
  );

  const act: Act = async (key, fn, okText) => {
    setBusy(key);
    try {
      const payload = await fn();
      qc.setQueryData(["process", pid, "relations"], payload);
      await refresh();
      toast.ok(okText);
      return true;
    } catch (e) {
      toast.error(e);
      return false;
    } finally {
      setBusy(null);
    }
  };

  const saveWaiver = async (reason: string) => {
    setBusy("waiver");
    try {
      await api.setWaiver(pid, reason);
      await refresh();
      toast.ok("리니지 미결 사유를 기록했습니다");
      setWaiverOpen(false);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const clearWaiver = async () => {
    setBusy("waiver");
    try {
      await api.clearWaiver(pid);
      await refresh();
      toast.ok("리니지 미결 사유를 삭제했습니다");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  const locked = !editable || busy !== null;
  const data = q.data;

  return (
    <div className="col gap-12">
      <div>
        <StepHeader
          n={5}
          title="매핑 + LPG · 리니지"
          sub="데이터셋 사이의 결합·연관·파생 관계를 지정하고 확정합니다. 확정한 관계만 정본 그래프에 들어가며, 결합 통계는 실제 컬럼 값으로 계산합니다."
        />
        <ReadOnlyNote />
      </div>

      <QueryState q={q}>
        {data && (
          <LineageStatus
            payload={data}
            comboSize={combo.length}
            locked={locked}
            busy={busy === "waiver"}
            onOpenWaiver={() => setWaiverOpen(true)}
            onClearWaiver={clearWaiver}
          />
        )}
      </QueryState>

      <GraphCard pid={pid} relTypes={data?.types ?? reference.relation_types} />

      {multi && data && (
        <>
          <div className="grid c2">
            <CandidateCard candidates={data.candidates} locked={locked} busy={busy} onAdd={(c, key) => act(key, () => api.createRelation(pid, candidateBody(c)), "결합 후보를 초안 관계로 추가했습니다")} />
            <AddRelationCard
              types={data.types}
              combo={combo}
              keyOptions={keyOptions}
              tablesOf={tablesOf}
              locked={locked}
              busy={busy}
              onCreate={(body) =>
                act(body.confirm ? "create-confirm" : "create", () => api.createRelation(pid, body), body.confirm ? "관계를 추가하고 확정했습니다" : "관계를 초안으로 추가했습니다")
              }
            />
          </div>
          <RelationListCard pid={pid} payload={data} keyOptions={keyOptions} tablesOf={tablesOf} locked={locked} busy={busy} act={act} />
        </>
      )}

      {waiverOpen && <WaiverModal busy={busy === "waiver"} onClose={() => setWaiverOpen(false)} onSave={saveWaiver} />}
    </div>
  );
}

function candidateBody(c: RelationCandidate): CreateBody {
  return {
    type: "JOINED_ON",
    source_id: c.source_id,
    target_id: c.target_id,
    key_code: c.key_code,
    source_table: c.source_table,
    source_column: c.source_column,
    target_table: c.target_table,
    target_column: c.target_column,
  };
}

// ───────────── A. 리니지 상태
function LineageStatus(props: { payload: RelationsPayload; comboSize: number; locked: boolean; busy: boolean; onOpenWaiver: () => void; onClearWaiver: () => void }) {
  const { payload, comboSize } = props;
  if (comboSize < 2) return <Banner tone="info">조합이 1건이라 관계 지정 없이 진행할 수 있습니다</Banner>;
  const confirmed = payload.relations.filter((r) => r.status === "confirmed").length;
  const drafts = payload.relations.length - confirmed;
  return (
    <div className="col">
      {confirmed > 0 && (
        <Banner tone="ok">
          <b>확정 관계 {fmtNum(confirmed)}건</b>
          {drafts > 0 ? ` · 초안 ${fmtNum(drafts)}건은 확정하기 전까지 정본 그래프에 들어가지 않습니다` : " · STEP 6 검증을 시작할 수 있습니다"}
        </Banner>
      )}
      {confirmed === 0 && !payload.waiver && !payload.lineage_resolved && (
        <Banner
          tone="warn"
          right={
            <Button size="sm" variant="dark" disabled={props.locked} onClick={props.onOpenWaiver}>
              미결 사유 기록
            </Button>
          }
        >
          <b>리니지 미결 — 확정된 관계가 없으면 STEP 6 검증을 시작할 수 없습니다</b>
          <div className="small">관계를 1건 이상 확정하거나, 관계를 두지 않는 사유를 기록하세요.</div>
        </Banner>
      )}
      {payload.waiver && (
        <Banner
          tone="info"
          right={
            <ConfirmButton size="sm" confirmLabel="한 번 더 눌러 삭제" disabled={props.locked} busy={props.busy} onConfirm={props.onClearWaiver}>
              사유 삭제
            </ConfirmButton>
          }
        >
          <b>리니지 미결 사유 기록됨</b> <span className="small">· {fmtDateTime(payload.waiver.at)}</span>
          <div className="small" style={{ whiteSpace: "pre-wrap" }}>
            {payload.waiver.reason}
          </div>
          {confirmed === 0 && <div className="tiny">확정된 관계 없이 STEP 6 검증을 진행합니다.</div>}
        </Banner>
      )}
    </div>
  );
}

function WaiverModal({ busy, onClose, onSave }: { busy: boolean; onClose: () => void; onSave: (reason: string) => void }) {
  const [reason, setReason] = useState("");
  const text = reason.trim();
  const ok = text.length >= 5;
  return (
    <Modal
      title="리니지 미결 사유 기록"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>취소</Button>
          <Button variant="primary" busy={busy} disabled={!ok} onClick={() => onSave(text)}>
            사유 저장
          </Button>
        </>
      }
    >
      <p className="small dim mb-8">확정된 관계 없이 검증으로 넘어가는 사유를 남깁니다. 기록한 사유는 활동 로그(prov:Activity)에 남습니다.</p>
      <Field label="사유" hint={`5자 이상 · 현재 ${text.length}자`}>
        <textarea
          className="textarea"
          rows={4}
          maxLength={1000}
          value={reason}
          autoFocus
          placeholder="예: 두 데이터셋은 같은 주제의 참고 자료일 뿐 결합 축이 없습니다"
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>
    </Modal>
  );
}

// ───────────── B. 그래프
const LEVELS: { key: number; label: string; note: string }[] = [
  { key: 1, label: "G1 조합·데이터셋", note: "조합(Collection)과 구성 데이터셋, 데이터셋 사이의 관계" },
  { key: 2, label: "G2 프로버넌스", note: "G1 + 카탈로그 작성과 최근 검증·직렬화·발행 활동(prov:Activity), 수행 주체(prov:Agent)" },
  { key: 3, label: "G3 배포본·표", note: "G2 + 배포본(dcat:Distribution)과 프로파일된 표" },
  { key: 4, label: "G4 컬럼·연계키", note: "G3 + 연계키를 배정한 컬럼, JOINED_ON 매핑 컬럼, 연계키(K) 노드" },
];

type NodeLook = { color: string; mode: "solid" | "tint" | "outline" };
const NODE_LOOK: Record<NodeType, NodeLook> = {
  Agent: { color: "var(--purple)", mode: "outline" },
  Activity: { color: "var(--orange)", mode: "tint" },
  Collection: { color: "var(--dark)", mode: "solid" },
  Dataset: { color: "var(--primary)", mode: "solid" },
  Service: { color: "var(--purple)", mode: "solid" },
  Distribution: { color: "var(--green)", mode: "tint" },
  Table: { color: "var(--green)", mode: "tint" },
  Column: { color: "var(--ink-2)", mode: "tint" },
  JoinKey: { color: "var(--err)", mode: "tint" },
};
const FALLBACK_LOOK: NodeLook = { color: "var(--ink-2)", mode: "tint" };
const lookOf = (type: string): NodeLook => NODE_LOOK[type as NodeType] ?? FALLBACK_LOOK;

/** 왼쪽 → 오른쪽 열 순서. 노드가 없는 열은 건너뛴다. */
const COLUMN_ORDER: NodeType[][] = [["Agent"], ["Activity"], ["Collection"], ["Dataset", "Service"], ["Distribution"], ["Table"], ["Column"], ["JoinKey"]];
const LEGEND_ORDER: NodeType[] = COLUMN_ORDER.flat();
const ANCHOR_SLOT = 3; // Dataset · Service 열을 기준으로 다른 열의 세로 순서를 맞춘다

type EdgeKind = "join" | "group" | "derive" | "other";
const EDGE_COLOR: Record<EdgeKind, string> = { join: "var(--err)", group: "var(--purple)", derive: "var(--primary)", other: "var(--line-strong)" };
const edgeKind = (type: string): EdgeKind => (type === "JOINED_ON" ? "join" : type === "GROUPED_WITH" ? "group" : type === "WAS_DERIVED_FROM" ? "derive" : "other");
const edgeTone = (kind: EdgeKind) => (kind === "join" ? "err" : kind === "group" ? "purple" : kind === "derive" ? "info" : "muted");

const NODE_W = 170;
const NODE_H = 44;
const ROW_GAP = 18;
const PITCH = NODE_H + ROW_GAP;
const COL_GAP = 96;
const PAD = 24;
const MIN_H = 260;

// 글자 폭 어림: 한글·한자는 라틴 소문자의 약 1.8배
const charUnits = (ch: string) => (ch.charCodeAt(0) > 0x2e7f ? 1.8 : ch !== ch.toLowerCase() ? 1.2 : 1);
function textUnits(s: string): number {
  let u = 0;
  for (const ch of s) u += charUnits(ch);
  return u;
}
function fitText(s: string, max: number): string {
  if (textUnits(s) <= max) return s;
  let u = 0;
  let out = "";
  for (const ch of s) {
    u += charUnits(ch);
    if (u > max - 1.2) break;
    out += ch;
  }
  return `${out}…`;
}

interface PlacedNode {
  node: GraphNode;
  col: number;
  x: number;
  y: number; // 왼쪽 위
  cy: number;
}
interface PlacedEdge {
  key: string;
  edge: GraphEdge;
  kind: EdgeKind;
  d: string;
  lx: number;
  ly: number;
  anchor: "start" | "middle";
  text: string; // 화면에 쓰는 (줄인) 라벨
  full: string;
}
interface GraphLayout {
  nodes: PlacedNode[];
  edges: PlacedEdge[];
  width: number;
  height: number;
}

/** 서버가 같은 엣지를 두 번 줄 수 있어(같은 컬럼을 두 경로로 만든 HAS_COLUMN) 이 키로 한 번만 그린다. */
const edgeKeyOf = (e: GraphEdge) => `${e.source}|${e.target}|${e.type}|${e.relation_id ?? ""}`;
const pairKeyOf = (e: GraphEdge) => (e.source < e.target ? `${e.source}|${e.target}` : `${e.target}|${e.source}`);

/** 관계 엣지는 라벨이 비어 있어도 유형을 보여 주고, 구조 엣지(HAD_MEMBER 등)는 라벨이 있을 때만 쓴다. */
function edgeText(e: GraphEdge, kind: EdgeKind): string {
  if (e.label) return e.label;
  return kind === "other" ? "" : e.type;
}

/** 유형별 열 배치. 열 안의 세로 순서는 이미 놓인 이웃 노드의 평균 높이를 따라 정해 교차를 줄인다. */
function layoutGraph(data: GraphData): GraphLayout {
  const slotOf = (type: string) => {
    const i = COLUMN_ORDER.findIndex((ts) => (ts as string[]).includes(type));
    return i < 0 ? COLUMN_ORDER.length : i;
  };
  const bySlot = new Map<number, GraphNode[]>();
  for (const n of data.nodes) {
    const s = slotOf(n.type);
    const list = bySlot.get(s);
    if (list) list.push(n);
    else bySlot.set(s, [n]);
  }
  const used = [...bySlot.keys()].sort((a, b) => a - b);
  if (used.length === 0) return { nodes: [], edges: [], width: 0, height: MIN_H };

  const maxRows = Math.max(...used.map((s) => bySlot.get(s)!.length));
  const height = Math.max(MIN_H, maxRows * NODE_H + (maxRows - 1) * ROW_GAP + PAD * 2);

  const adj = new Map<string, string[]>();
  const link = (a: string, b: string) => {
    const list = adj.get(a);
    if (list) list.push(b);
    else adj.set(a, [b]);
  };
  for (const e of data.edges) {
    link(e.source, e.target);
    link(e.target, e.source);
  }

  // 1) 세로 순서: 기준 열 → 오른쪽 열들 → 왼쪽 열들 순으로 놓는다
  const anchor = Math.max(0, used.indexOf(ANCHOR_SLOT));
  const visit = [anchor];
  for (let i = anchor + 1; i < used.length; i++) visit.push(i);
  for (let i = anchor - 1; i >= 0; i--) visit.push(i);

  const colOf = new Map<string, number>();
  const rowOf = new Map<string, number>();
  const cyOf = new Map<string, number>();
  const ordered: GraphNode[][] = used.map(() => []);
  for (const ci of visit) {
    const list = bySlot.get(used[ci])!;
    const top = (height - (list.length * NODE_H + (list.length - 1) * ROW_GAP)) / 2;
    const keyed = list.map((node, i) => {
      const ys = (adj.get(node.id) ?? []).map((id) => cyOf.get(id)).filter((v): v is number => v !== undefined);
      const own = top + i * PITCH + NODE_H / 2;
      return { node, i, bary: ys.length > 0 ? ys.reduce((a, b) => a + b, 0) / ys.length : own };
    });
    if (ci !== anchor) keyed.sort((a, b) => a.bary - b.bary || a.i - b.i);
    keyed.forEach((k, row) => {
      colOf.set(k.node.id, ci);
      rowOf.set(k.node.id, row);
      cyOf.set(k.node.id, top + row * PITCH + NODE_H / 2);
    });
    ordered[ci] = keyed.map((k) => k.node);
  }

  // 2) 엣지 정리: 중복 제거, 같은 노드 쌍 사이의 평행 엣지 번호
  const seen = new Set<string>();
  const edges: GraphEdge[] = [];
  for (const e of data.edges) {
    if (e.source === e.target || !colOf.has(e.source) || !colOf.has(e.target)) continue;
    const k = edgeKeyOf(e);
    if (seen.has(k)) continue;
    seen.add(k);
    edges.push(e);
  }
  const pairTotal = new Map<string, number>();
  for (const e of edges) pairTotal.set(pairKeyOf(e), (pairTotal.get(pairKeyOf(e)) ?? 0) + 1);
  const pairSeen = new Map<string, number>();

  // 3) 같은 열 안의 엣지는 오른쪽으로 휘는 고리로 그린다. 고리와 라벨이 들어갈 만큼 열 간격을 넓힌다
  const specs = edges.map((e) => {
    const pk = pairKeyOf(e);
    const idx = pairSeen.get(pk) ?? 0;
    pairSeen.set(pk, idx + 1);
    const shift = (idx - ((pairTotal.get(pk) ?? 1) - 1) / 2) * 14;
    const kind = edgeKind(e.type);
    const full = edgeText(e, kind);
    const text = fitText(full, 34);
    const sc = colOf.get(e.source)!;
    const tc = colOf.get(e.target)!;
    const loop = sc === tc;
    const bulge = loop ? Math.min(130, 40 + 16 * Math.abs(rowOf.get(e.source)! - rowOf.get(e.target)!)) + 18 * idx : 0;
    const reach = loop ? bulge * 0.75 + (text ? 8 + textUnits(text) * 6.2 : 0) : 0;
    return { e, kind, full, text, sc, tc, loop, bulge, reach, shift };
  });
  const reachOf = used.map(() => 0);
  for (const s of specs) if (s.loop) reachOf[s.sc] = Math.max(reachOf[s.sc], s.reach);

  const xOf: number[] = [];
  let x = PAD;
  used.forEach((_, ci) => {
    xOf[ci] = x;
    x += NODE_W + Math.max(COL_GAP, reachOf[ci] + 16);
  });
  const last = used.length - 1;
  const width = xOf[last] + NODE_W + reachOf[last] + PAD;

  // 4) 좌표
  const nodes: PlacedNode[] = [];
  ordered.forEach((list, ci) =>
    list.forEach((node) => {
      const cy = cyOf.get(node.id)!;
      nodes.push({ node, col: ci, x: xOf[ci], y: cy - NODE_H / 2, cy });
    }),
  );
  const placed: PlacedEdge[] = specs.map((s) => {
    const key = edgeKeyOf(s.e);
    const sy = cyOf.get(s.e.source)!;
    const ty = cyOf.get(s.e.target)!;
    if (s.loop) {
      // 나가는 쪽은 조금 위, 들어오는 쪽은 조금 아래에 붙여 같은 노드의 고리들이 겹치지 않게 한다
      const x0 = xOf[s.sc] + NODE_W;
      const y0 = sy - 5 + s.shift;
      const y1 = ty + 5 + s.shift;
      const d = `M ${x0} ${y0} C ${x0 + s.bulge} ${y0}, ${x0 + s.bulge} ${y1}, ${x0} ${y1}`;
      return { key, edge: s.e, kind: s.kind, d, lx: x0 + s.bulge * 0.75 + 6, ly: (y0 + y1) / 2, anchor: "start", text: s.text, full: s.full };
    }
    const forward = s.sc < s.tc;
    const x0 = forward ? xOf[s.sc] + NODE_W : xOf[s.sc];
    const x1 = forward ? xOf[s.tc] : xOf[s.tc] + NODE_W;
    const y0 = sy + s.shift;
    const y1 = ty + s.shift;
    const c = Math.max(36, Math.abs(x1 - x0) * 0.45) * (forward ? 1 : -1);
    const d = `M ${x0} ${y0} C ${x0 + c} ${y0}, ${x1 - c} ${y1}, ${x1} ${y1}`;
    return { key, edge: s.e, kind: s.kind, d, lx: (x0 + x1) / 2, ly: (y0 + y1) / 2, anchor: "middle", text: s.text, full: s.full };
  });

  return { nodes, edges: placed, width, height };
}

type Selection = { kind: "node"; id: string } | { kind: "edge"; key: string } | null;

function GraphCard({ pid, relTypes }: { pid: number; relTypes: RelTypes }) {
  const [level, setLevel] = useState(2);
  const [sel, setSel] = useState<Selection>(null);
  const q = useQuery({ queryKey: ["process", pid, "graph", level], queryFn: () => api.graph(pid, level), placeholderData: keepPreviousData });
  const data = q.data;
  const layout = useMemo(() => (data ? layoutGraph(data) : null), [data]);
  // 방향이 없는 관계 유형 (화살표를 그리지 않는다)
  const undirected = useMemo(() => new Set(relTypes.filter((t) => !t.directed).flatMap((t) => [t.type as string, t.label])), [relTypes]);

  const selNode = sel?.kind === "node" ? layout?.nodes.find((n) => n.node.id === sel.id) : undefined;
  const selEdge = sel?.kind === "edge" ? layout?.edges.find((e) => e.key === sel.key) : undefined;
  const current = LEVELS.find((l) => l.key === level);

  return (
    <Card title="LPG 그래프 · 리니지" right={current && <span className="small muted">{current.note}</span>}>
      <Tabs
        tabs={LEVELS.map((l) => ({ key: l.key, label: l.label }))}
        value={level}
        onChange={(k) => {
          setLevel(k);
          setSel(null);
        }}
      />
      <QueryState q={q}>
        {data && layout && (
          <>
            <GraphLegend data={data} />
            {layout.nodes.length === 0 ? (
              <Empty>그래프에 그릴 노드가 없습니다. STEP 2 에서 조합을 확정하면 조합과 데이터셋이 나타납니다.</Empty>
            ) : (
              <div className="row top wrap gap-12 mt-8">
                <div style={{ flex: "1 1 420px", minWidth: 0, opacity: q.isPlaceholderData ? 0.55 : 1 }}>
                  <GraphView layout={layout} selection={sel} undirected={undirected} onSelect={setSel} />
                </div>
                <div style={{ flex: "0 0 280px", maxWidth: "100%" }}>
                  <GraphDetail node={selNode?.node} edge={selEdge} nodes={layout.nodes} undirected={undirected} />
                </div>
              </div>
            )}
          </>
        )}
      </QueryState>
      <p className="small muted mt-8">정본은 RDF(Turtle)이고 이 그래프는 저장된 데이터에서 매번 다시 만드는 파생 표현입니다.</p>
    </Card>
  );
}

function Dot({ type }: { type: string }) {
  const look = lookOf(type);
  return (
    <span
      aria-hidden
      style={{
        width: 10,
        height: 10,
        borderRadius: 3,
        flex: "none",
        display: "inline-block",
        border: `2px solid ${look.color}`,
        background: look.mode === "outline" ? "var(--surface)" : look.color,
        opacity: look.mode === "tint" ? 0.75 : 1,
      }}
    />
  );
}

function GraphLegend({ data }: { data: GraphData }) {
  const known = LEGEND_ORDER.filter((t) => (data.node_counts[t] ?? 0) > 0) as string[];
  const extra = Object.keys(data.node_counts).filter((t) => !known.includes(t) && data.node_counts[t] > 0);
  const edgeTypes = Object.entries(data.edge_counts);
  return (
    <div className="col gap-4">
      <div className="row wrap gap-12 small">
        <span className="bold dim">노드 {fmtNum(data.nodes.length)}개</span>
        {[...known, ...extra].map((t) => (
          <span key={t} className="row gap-4 nowrap">
            <Dot type={t} />
            {t} <span className="muted">{fmtNum(data.node_counts[t])}</span>
          </span>
        ))}
      </div>
      <div className="row wrap gap-4 small">
        <span className="bold dim" style={{ marginRight: 8 }}>
          엣지 {fmtNum(data.edges.length)}개
        </span>
        {edgeTypes.length === 0 && <span className="muted">없음</span>}
        {edgeTypes.map(([t, n]) => {
          const kind = edgeKind(t);
          return (
            <span key={t} className="kbd row gap-4 nowrap" style={{ display: "inline-flex" }}>
              <span aria-hidden style={{ width: 14, height: 0, borderTop: `2px ${kind === "group" ? "dashed" : "solid"} ${EDGE_COLOR[kind]}` }} />
              {t} {fmtNum(n)}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function GraphView(props: { layout: GraphLayout; selection: Selection; undirected: Set<string>; onSelect: (s: Selection) => void }) {
  const { layout, selection, undirected, onSelect } = props;
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const marker = (kind: EdgeKind) => `${uid}-arrow-${kind}`;

  // 선택한 노드·엣지와 맞닿은 것만 또렷하게 보여 준다
  const focus = useMemo(() => {
    if (!selection) return null;
    const nodes = new Set<string>();
    const edges = new Set<string>();
    if (selection.kind === "node") {
      if (!layout.nodes.some((n) => n.node.id === selection.id)) return null;
      nodes.add(selection.id);
      for (const e of layout.edges) {
        if (e.edge.source === selection.id || e.edge.target === selection.id) {
          edges.add(e.key);
          nodes.add(e.edge.source);
          nodes.add(e.edge.target);
        }
      }
    } else {
      const e = layout.edges.find((x) => x.key === selection.key);
      if (!e) return null;
      edges.add(e.key);
      nodes.add(e.edge.source);
      nodes.add(e.edge.target);
    }
    return { nodes, edges };
  }, [selection, layout]);

  const onKey = (e: KeyboardEvent, s: Selection) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(s);
    }
  };

  return (
    <div style={{ overflowX: "auto", border: "1px solid var(--line)", borderRadius: "var(--r-md)", background: "var(--surface-2)" }}>
      {/* 칸이 많은 수준(G3·G4)도 한눈에 보이도록 폭에 맞춰 줄인다. 글자가 너무 작아지는 60% 아래로는 줄이지 않고 가로 스크롤한다. */}
      <svg
        width="100%"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="group"
        aria-label="LPG 그래프"
        style={{ display: "block", margin: "0 auto", height: "auto", maxWidth: layout.width, minWidth: Math.min(layout.width, Math.max(640, layout.width * 0.6)) }}
        onClick={() => onSelect(null)}
      >
        <defs>
          {(Object.keys(EDGE_COLOR) as EdgeKind[]).map((kind) => (
            <marker key={kind} id={marker(kind)} markerUnits="userSpaceOnUse" markerWidth={9} markerHeight={8} refX={8.5} refY={4} orient="auto">
              <path d="M 0 0 L 9 4 L 0 8 z" style={{ fill: EDGE_COLOR[kind] }} />
            </marker>
          ))}
        </defs>

        {layout.edges.map((pe) => {
          const e = pe.edge;
          const on = selection?.kind === "edge" && selection.key === pe.key;
          const dim = focus !== null && !focus.edges.has(pe.key);
          const draft = e.status === "draft";
          const base = pe.kind === "other" ? 1.2 : 1.8;
          const s: Selection = { kind: "edge", key: pe.key };
          return (
            <g
              key={pe.key}
              role="button"
              tabIndex={pe.kind === "other" ? -1 : 0}
              aria-label={`${e.type} ${pe.full}`}
              style={{ cursor: "pointer", opacity: dim ? 0.15 : draft ? 0.5 : 1 }}
              onClick={(ev) => {
                ev.stopPropagation();
                onSelect(s);
              }}
              onKeyDown={(ev) => onKey(ev, s)}
            >
              <title>{`${e.type}${pe.full && pe.full !== e.type ? ` · ${pe.full}` : ""}${draft ? " (초안)" : ""}`}</title>
              <path d={pe.d} fill="none" strokeWidth={14} style={{ stroke: "var(--line)", strokeOpacity: 0, pointerEvents: "stroke" }} />
              <path
                d={pe.d}
                fill="none"
                strokeWidth={on ? base + 1.4 : focus && !dim ? base + 0.4 : base}
                strokeDasharray={draft ? "4 3" : pe.kind === "group" ? "6 4" : undefined}
                strokeLinecap="round"
                markerEnd={undirected.has(e.type) ? undefined : `url(#${marker(pe.kind)})`}
                style={{ stroke: EDGE_COLOR[pe.kind] }}
              />
            </g>
          );
        })}

        {layout.nodes.map((pn) => {
          const n = pn.node;
          const look = lookOf(n.type);
          const on = selection?.kind === "node" && selection.id === n.id;
          const dim = focus !== null && !focus.nodes.has(n.id);
          const solid = look.mode === "solid";
          const ink = solid ? "var(--surface)" : "var(--ink)";
          const sub = solid ? "var(--surface)" : "var(--ink-2)";
          const s: Selection = { kind: "node", id: n.id };
          return (
            <g
              key={n.id}
              role="button"
              tabIndex={0}
              aria-label={`${n.type} ${n.label}`}
              aria-pressed={on}
              transform={`translate(${pn.x} ${pn.y})`}
              style={{ cursor: "pointer", opacity: dim ? 0.4 : 1 }}
              onClick={(ev) => {
                ev.stopPropagation();
                onSelect(s);
              }}
              onKeyDown={(ev) => onKey(ev, s)}
            >
              <title>{`${n.type} · ${n.label}${n.sub ? `\n${n.sub}` : ""}`}</title>
              {on && <rect x={-4} y={-4} width={NODE_W + 8} height={NODE_H + 8} rx={13} fill="none" strokeWidth={2} style={{ stroke: "var(--ink)" }} />}
              <rect width={NODE_W} height={NODE_H} rx={10} style={{ fill: "var(--surface)" }} />
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={10}
                strokeWidth={look.mode === "outline" ? 2 : 1.5}
                fillOpacity={solid ? 1 : look.mode === "tint" ? 0.14 : 0}
                style={{ fill: look.color, stroke: look.color }}
              />
              <text x={12} y={n.sub ? 19 : 27} fontSize={12} fontWeight={700} style={{ fill: ink }}>
                {fitText(n.label, 21)}
              </text>
              {n.sub && (
                <text x={12} y={34} fontSize={10} fillOpacity={solid ? 0.82 : 1} style={{ fill: sub }}>
                  {fitText(n.sub, 26)}
                </text>
              )}
            </g>
          );
        })}

        {layout.edges.map((pe) => {
          if (!pe.text) return null;
          const on = selection?.kind === "edge" && selection.key === pe.key;
          const dim = focus !== null && !focus.edges.has(pe.key);
          return (
            <text
              key={pe.key}
              x={pe.lx}
              y={pe.ly}
              fontSize={11}
              fontWeight={on ? 800 : 600}
              textAnchor={pe.anchor}
              dominantBaseline="middle"
              strokeWidth={4}
              strokeLinejoin="round"
              opacity={dim ? 0.15 : pe.edge.status === "draft" ? 0.6 : 1}
              style={{ fill: pe.kind === "other" ? "var(--ink-2)" : EDGE_COLOR[pe.kind], stroke: "var(--surface)", paintOrder: "stroke", pointerEvents: "none" }}
            >
              {pe.text}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

function DetailList({ detail, extra }: { detail?: Record<string, string>; extra?: [string, ReactNode][] }) {
  const rows: [string, ReactNode][] = [...(extra ?? []), ...Object.entries(detail ?? {})];
  if (rows.length === 0) return <div className="small muted">추가 속성이 없습니다</div>;
  return (
    <dl className="kv">
      {rows.map(([k, v]) => (
        <div key={k} style={{ display: "contents" }}>
          <dt>{k}</dt>
          <dd>{v === "" || v == null ? <span className="muted">—</span> : v}</dd>
        </div>
      ))}
    </dl>
  );
}

function GraphDetail({ node, edge, nodes, undirected }: { node?: GraphNode; edge?: PlacedEdge; nodes: PlacedNode[]; undirected: Set<string> }) {
  const { go } = useStudio();
  if (node) {
    const datasetId = node.dataset_id;
    return (
      <div className="card tight flat col">
        <div className="row wrap gap-4">
          <Dot type={node.type} />
          <Badge tone={node.type === "Dataset" ? "info" : node.type === "Service" || node.type === "Agent" ? "purple" : node.type === "JoinKey" ? "err" : "muted"}>{node.type}</Badge>
        </div>
        <div>
          <div className="bold">{node.label}</div>
          {node.sub && <div className="small muted mono">{node.sub}</div>}
        </div>
        <DetailList detail={node.detail} />
        {datasetId != null && (
          <div className="row wrap">
            <Button size="sm" variant="outline" onClick={() => go(3, { dataset: datasetId })}>
              STEP 3 메타데이터로
            </Button>
            <Button size="sm" variant="outline" onClick={() => go(4, { dataset: datasetId })}>
              STEP 4 분류로
            </Button>
          </div>
        )}
      </div>
    );
  }
  if (edge) {
    const e = edge.edge;
    const name = (id: string) => nodes.find((n) => n.node.id === id)?.node.label ?? id;
    const extra: [string, ReactNode][] = [];
    if (e.label) extra.push(["라벨", <span className="mono">{e.label}</span>]);
    if (e.type === "JOINED_ON" && e.priority != null && e.priority > 0) extra.push(["SSOT 우선순위", `${e.priority}순위`]);
    return (
      <div className="card tight flat col">
        <div className="row wrap gap-4">
          <Badge tone={edgeTone(edge.kind)}>{e.type}</Badge>
          {e.status && <Badge tone={e.status === "confirmed" ? "ok" : "warn"}>{e.status === "confirmed" ? "확정" : "초안"}</Badge>}
        </div>
        <div className="bold">
          {name(e.source)} {undirected.has(e.type) ? "↔" : "→"} {name(e.target)}
        </div>
        {e.status === "draft" && <div className="small t-warn">초안 관계는 정본 그래프에 들어가지 않습니다.</div>}
        <DetailList detail={e.detail} extra={extra} />
      </div>
    );
  }
  return (
    <div className="empty" style={{ padding: "18px 14px" }}>
      노드나 엣지를 누르면 상세가 여기에 표시됩니다
    </div>
  );
}

// ───────────── C. 결합 후보 · 직접 추가
function CandidateCard(props: { candidates: RelationCandidate[]; locked: boolean; busy: string | null; onAdd: (c: RelationCandidate, busyKey: string) => void }) {
  const { candidates } = props;
  return (
    <Card title={<>결합 후보 (규칙 기반) {candidates.length > 0 && <span className="muted small">{fmtNum(candidates.length)}건</span>}</>}>
      {candidates.length === 0 ? (
        <Empty>
          결합 후보가 없습니다. 후보는 두 데이터셋이 같은 연계키(K1~K9) 후보 컬럼을 함께 가질 때 규칙으로 만들어집니다.
          <br />
          오른쪽 「관계 직접 추가」에서 컬럼을 골라 지정할 수 있습니다.
        </Empty>
      ) : (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>데이터셋 A ↔ B</th>
                  <th>연계키</th>
                  <th>컬럼</th>
                  <th className="num">점수</th>
                  <th className="num">값 일치</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => {
                  const key = `cand:${c.source_id}:${c.target_id}:${c.key_code}`;
                  return (
                    <tr key={key}>
                      <td>
                        {c.source_name} ↔ {c.target_name}
                      </td>
                      <td className="nowrap">
                        <KeyPill code={c.key_code} label={c.key_label} />
                      </td>
                      <td className="mono small">
                        {c.source_table}.{c.source_column} = {c.target_table}.{c.target_column}
                      </td>
                      <td className="num">{Math.round(c.score * 100)}</td>
                      <td className="num">
                        <CandidateMatch stats={c.stats} />
                      </td>
                      <td className="nowrap right">
                        {c.already ? (
                          <Badge tone="ok">추가됨</Badge>
                        ) : (
                          <Button size="sm" variant="outline" disabled={props.locked} busy={props.busy === key} onClick={() => props.onAdd(c, key)}>
                            관계 추가
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="tiny muted mt-8">점수는 키 후보 점수와 값 일치율로 계산한 규칙 기반 값입니다. 「관계 추가」는 JOINED_ON 초안을 만들며, 확정은 아래 관계 목록에서 합니다.</p>
        </>
      )}
    </Card>
  );
}

function CandidateMatch({ stats }: { stats: JoinStats | null }) {
  if (!stats || stats.matched == null) return <span className="muted">표본 없음</span>;
  const rate = Math.max(stats.source_match_rate ?? 0, stats.target_match_rate ?? 0);
  return (
    <span title={`A ${fmtNum(stats.source_distinct)}종 · B ${fmtNum(stats.target_distinct)}종${stats.sampled ? " · 표본 기준" : ""}`}>
      {fmtNum(stats.matched)}건 · {fmtPct(rate)}
      {stats.sampled ? " (표본)" : ""}
    </span>
  );
}

function ColumnPicker(props: { label: string; state: TableState; value: ColRef; onChange: (v: ColRef) => void; disabled?: boolean }) {
  const { state, value } = props;
  const eff = resolveRef(value, state.tables);
  const cur = state.tables.find((t) => t.name === eff.table);
  const cols = cur?.columns ?? [];
  const tableMissing = !!eff.table && !cur && !state.loading;
  const colMissing = !!value.column && !cols.some((c) => c.name === value.column) && !state.loading;
  const hint = state.error ? state.error : !state.loading && state.tables.length === 0 ? "프로파일된 표가 없어 컬럼을 고를 수 없습니다" : undefined;
  return (
    <Field label={props.label} hint={hint}>
      <div className="row">
        <select
          className="select"
          aria-label={`${props.label} 표`}
          value={eff.table}
          disabled={props.disabled || state.loading}
          onChange={(e) => props.onChange({ table: e.target.value, column: "" })}
        >
          <option value="">{state.loading ? "불러오는 중…" : "표 선택"}</option>
          {tableMissing && <option value={eff.table}>{eff.table} (프로파일에 없음)</option>}
          {state.tables.map((t) => (
            <option key={t.name} value={t.name}>
              {t.name}
            </option>
          ))}
        </select>
        <select
          className="select"
          aria-label={`${props.label} 컬럼`}
          value={value.column}
          disabled={props.disabled || state.loading || !eff.table}
          onChange={(e) => props.onChange({ table: eff.table, column: e.target.value })}
        >
          <option value="">컬럼 선택</option>
          {colMissing && <option value={value.column}>{value.column} (프로파일에 없음)</option>}
          {cols.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} · {c.type}
            </option>
          ))}
        </select>
      </div>
    </Field>
  );
}

function AddRelationCard(props: {
  types: RelTypes;
  combo: Dataset[];
  keyOptions: KeyOpt[];
  tablesOf: (id: number | null) => TableState;
  locked: boolean;
  busy: string | null;
  onCreate: (body: CreateBody) => Promise<boolean>;
}) {
  const { types, combo, keyOptions, tablesOf, locked } = props;
  const [type, setType] = useState<RelationType>(types[0]?.type ?? "JOINED_ON");
  const [sourceId, setSourceId] = useState<number | null>(combo[0]?.id ?? null);
  const [targetId, setTargetId] = useState<number | null>(combo[1]?.id ?? null);
  const [keyCode, setKeyCode] = useState("");
  const [src, setSrc] = useState<ColRef>(EMPTY_REF);
  const [tgt, setTgt] = useState<ColRef>(EMPTY_REF);

  const def = types.find((t) => t.type === type);
  const needsKey = def?.needs_key ?? type === "JOINED_ON";
  const directed = def?.directed ?? true;
  const byId = (id: number | null) => combo.find((d) => d.id === id);
  // 조합이 바뀌어 사라진 데이터셋은 선택에서 뺀다
  const sId = byId(sourceId) ? sourceId : null;
  const tId = byId(targetId) ? targetId : null;
  const srcState = tablesOf(sId);
  const tgtState = tablesOf(tId);

  const pickSource = (id: number | null) => {
    if (id != null && id === tId) {
      // 같은 데이터셋을 고르면 출발·도착을 맞바꾼다
      setTargetId(sId);
      setTgt(src);
    }
    setSourceId(id);
    setSrc(id != null && id === tId ? tgt : suggestRef(byId(id), keyCode));
  };
  const pickTarget = (id: number | null) => {
    if (id != null && id === sId) {
      setSourceId(tId);
      setSrc(tgt);
    }
    setTargetId(id);
    setTgt(id != null && id === sId ? src : suggestRef(byId(id), keyCode));
  };
  const pickKey = (code: string) => {
    setKeyCode(code);
    setSrc(suggestRef(byId(sId), code));
    setTgt(suggestRef(byId(tId), code));
  };

  const problem =
    sId == null || tId == null ? "출발·도착 데이터셋을 고르세요" : sId === tId ? "서로 다른 데이터셋을 고르세요" : needsKey && !keyCode ? "연계키를 고르세요" : null;

  const submit = async (confirm: boolean) => {
    if (problem || sId == null || tId == null) return;
    const s = resolveRef(src, srcState.tables);
    const t = resolveRef(tgt, tgtState.tables);
    const body: CreateBody = { type, source_id: sId, target_id: tId, confirm };
    if (needsKey) {
      body.key_code = keyCode;
      body.source_table = s.column ? orNull(s.table) : null;
      body.source_column = orNull(s.column);
      body.target_table = t.column ? orNull(t.table) : null;
      body.target_column = orNull(t.column);
    }
    if (await props.onCreate(body)) {
      setKeyCode("");
      setSrc(EMPTY_REF);
      setTgt(EMPTY_REF);
    }
  };

  const dsSelect = (value: number | null, onPick: (id: number | null) => void, label: string) => (
    <select className="select" aria-label={label} value={value ?? ""} disabled={locked} onChange={(e) => onPick(e.target.value ? Number(e.target.value) : null)}>
      <option value="">데이터셋 선택</option>
      {combo.map((d) => (
        <option key={d.id} value={d.id}>
          {d.title}
          {d.kind === "stream" ? " (스트림)" : ""}
        </option>
      ))}
    </select>
  );
  const sourceLabel = directed ? "출발 데이터셋" : "데이터셋 A";
  const targetLabel = directed ? "도착 데이터셋" : "데이터셋 B";

  return (
    <Card title="관계 직접 추가">
      <div className="col gap-12">
        <Field label="관계 유형" hint={def?.desc}>
          <select className="select" value={type} disabled={locked} onChange={(e) => setType(e.target.value as RelationType)}>
            {types.map((t) => (
              <option key={t.type} value={t.type}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>
        <div className="grid c2">
          <Field label={sourceLabel} hint={type === "DERIVED_FROM" ? "파생된 쪽 (결과)" : undefined}>
            {dsSelect(sId, pickSource, sourceLabel)}
          </Field>
          <Field label={targetLabel} hint={type === "DERIVED_FROM" ? "원천이 되는 쪽" : undefined}>
            {dsSelect(tId, pickTarget, targetLabel)}
          </Field>
        </div>
        {needsKey && (
          <>
            <Field label="연계키" hint="연계키를 고르면 STEP 4 배정 컬럼(없으면 프로파일 키 후보)으로 아래 컬럼을 미리 채웁니다">
              <select className="select" value={keyCode} disabled={locked} onChange={(e) => pickKey(e.target.value)}>
                <option value="">연계키 선택</option>
                {keyOptions.map((k) => (
                  <option key={k.code} value={k.code}>
                    {k.code} {k.label}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid c2">
              <ColumnPicker label="출발 표 · 컬럼" state={srcState} value={src} onChange={setSrc} disabled={locked || sId == null} />
              <ColumnPicker label="도착 표 · 컬럼" state={tgtState} value={tgt} onChange={setTgt} disabled={locked || tId == null} />
            </div>
          </>
        )}
        <div className="row wrap">
          <Button disabled={locked || !!problem} busy={props.busy === "create"} onClick={() => submit(false)}>
            초안으로 추가
          </Button>
          <Button variant="primary" disabled={locked || !!problem} busy={props.busy === "create-confirm"} onClick={() => submit(true)}>
            추가하고 확정
          </Button>
          {problem && <span className="small muted">{problem}</span>}
        </div>
      </div>
    </Card>
  );
}

// ───────────── D. 관계 목록
function RelationListCard(props: {
  pid: number;
  payload: RelationsPayload;
  keyOptions: KeyOpt[];
  tablesOf: (id: number | null) => TableState;
  locked: boolean;
  busy: string | null;
  act: Act;
}) {
  const { pid, payload, locked, busy, act } = props;
  const [editingId, setEditingId] = useState<number | null>(null);
  const joined = payload.relations.filter((r) => r.type === "JOINED_ON").sort((a, b) => a.priority - b.priority || a.id - b.id);
  const others = payload.relations.filter((r) => r.type !== "JOINED_ON").sort((a, b) => a.id - b.id);
  const typeOf = (t: RelationType) => payload.types.find((x) => x.type === t);

  const move = (idx: number, dir: -1 | 1) => {
    const ids = joined.map((r) => r.id);
    const j = idx + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[idx], ids[j]] = [ids[j], ids[idx]];
    void act("order", () => api.orderRelations(pid, ids), "SSOT 우선순위를 바꿨습니다");
  };

  const actions = (r: Relation): ReactNode => (
    <>
      {r.status === "confirmed" ? (
        <Button size="sm" disabled={locked} busy={busy === `confirm:${r.id}`} onClick={() => void act(`confirm:${r.id}`, () => api.unconfirmRelation(r.id), "확정을 해제했습니다")}>
          확정 해제
        </Button>
      ) : (
        <Button
          size="sm"
          variant="ok"
          disabled={locked}
          busy={busy === `confirm:${r.id}`}
          onClick={() => void act(`confirm:${r.id}`, () => api.confirmRelation(r.id), "관계를 확정했습니다. 정본 그래프에 반영됩니다")}
        >
          확정
        </Button>
      )}
    </>
  );
  const remove = (r: Relation): ReactNode => (
    <ConfirmButton
      size="sm"
      confirmLabel="한 번 더 눌러 삭제"
      disabled={locked}
      busy={busy === `delete:${r.id}`}
      onConfirm={() => void act(`delete:${r.id}`, () => api.deleteRelation(r.id), "관계를 삭제했습니다")}
    >
      삭제
    </ConfirmButton>
  );

  return (
    <Card title={<>관계 목록 {payload.relations.length > 0 && <span className="muted small">{fmtNum(payload.relations.length)}건</span>}</>}>
      {payload.relations.length === 0 ? (
        <Empty>아직 지정한 관계가 없습니다. 결합 후보에서 추가하거나 「관계 직접 추가」로 만든 뒤 확정하세요.</Empty>
      ) : (
        <div className="col gap-16">
          {joined.length > 0 && (
            <section>
              <div className="small bold dim mb-8">JOINED_ON — SSOT 우선순위 (맨 위 = 판단 기준 1순위)</div>
              <div className="col">
                {joined.map((r, i) => (
                  <div key={r.id} className="card tight" style={{ boxShadow: "none" }}>
                    <div className="row top between wrap gap-12">
                      <div className="row top grow" style={{ minWidth: 260 }}>
                        <Badge tone="dark" title="SSOT 우선순위">
                          {i + 1}
                        </Badge>
                        <div className="col gap-4 grow">
                          <div className="row wrap">
                            <span className="bold">
                              {r.source_name} → {r.target_name}
                            </span>
                            {r.key_code && <KeyPill code={r.key_code} label={r.key_label} />}
                            <StatusBadge status={r.status} />
                          </div>
                          <div className="mono small">
                            {refText(r.source_table, r.source_column)} = {refText(r.target_table, r.target_column)}
                          </div>
                          <JoinStatsView stats={r.stats} />
                          {r.note && <div className="small muted">{r.note}</div>}
                        </div>
                      </div>
                      <div className="row wrap">
                        <Button size="sm" title="우선순위 올리기" disabled={locked || i === 0} onClick={() => move(i, -1)}>
                          ▲
                        </Button>
                        <Button size="sm" title="우선순위 내리기" disabled={locked || i === joined.length - 1} onClick={() => move(i, 1)}>
                          ▼
                        </Button>
                        {actions(r)}
                        <Button size="sm" disabled={locked || editingId === r.id} onClick={() => setEditingId(r.id)}>
                          수정
                        </Button>
                        {remove(r)}
                      </div>
                    </div>
                    {editingId === r.id && (
                      <JoinEdit
                        relation={r}
                        keyOptions={props.keyOptions}
                        srcState={props.tablesOf(r.source_id)}
                        tgtState={props.tablesOf(r.target_id)}
                        locked={locked}
                        busy={busy === `edit:${r.id}`}
                        onCancel={() => setEditingId(null)}
                        onSave={async (body) => {
                          if (await act(`edit:${r.id}`, () => api.updateRelation(r.id, body), "관계를 수정했습니다. 초안으로 돌아갔으니 다시 확정하세요")) setEditingId(null);
                        }}
                      />
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
          {others.length > 0 && (
            <section>
              <div className="small bold dim mb-8">GROUPED_WITH · WAS_DERIVED_FROM</div>
              <div className="col">
                {others.map((r) => {
                  const def = typeOf(r.type);
                  return (
                    <div key={r.id} className="card tight row between wrap gap-12" style={{ boxShadow: "none" }}>
                      <div className="col gap-4 grow" style={{ minWidth: 260 }}>
                        <div className="row wrap">
                          <span className="bold">
                            {r.source_name} {def && !def.directed ? "↔" : "→"} {r.target_name}
                          </span>
                          <Badge tone={r.type === "GROUPED_WITH" ? "purple" : "info"} title={def?.desc}>
                            {def?.label ?? r.type}
                          </Badge>
                          <StatusBadge status={r.status} />
                        </div>
                        {r.note && <div className="small muted">{r.note}</div>}
                      </div>
                      <div className="row wrap">
                        {actions(r)}
                        {remove(r)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      )}
    </Card>
  );
}

function StatusBadge({ status }: { status: Relation["status"] }) {
  return status === "confirmed" ? <Badge tone="ok">확정</Badge> : <Badge tone="warn">초안</Badge>;
}

function JoinStatsView({ stats }: { stats: JoinStats }) {
  if (!stats.computed) return <div className="small muted">{stats.reason || "결합 통계가 아직 계산되지 않았습니다"}</div>;
  const samples = (stats.unmatched_samples ?? []).slice(0, 5);
  return (
    <>
      <div className="small">
        값 일치 {fmtNum(stats.matched)}건 · 출발 {fmtPct(stats.source_match_rate, 1)} ({fmtNum(stats.source_distinct)}종) · 도착 {fmtPct(stats.target_match_rate, 1)} ({fmtNum(stats.target_distinct)}종)
      </div>
      <div style={{ maxWidth: 320 }} title={`출발 일치율 ${fmtPct(stats.source_match_rate, 1)}`}>
        <Meter value={(stats.source_match_rate ?? 0) * 100} />
      </div>
      {samples.length > 0 && <div className="tiny muted mono">불일치 예: {samples.join(", ")}</div>}
    </>
  );
}

function JoinEdit(props: {
  relation: Relation;
  keyOptions: KeyOpt[];
  srcState: TableState;
  tgtState: TableState;
  locked: boolean;
  busy: boolean;
  onCancel: () => void;
  onSave: (body: UpdateBody) => void;
}) {
  const { relation: r, srcState, tgtState } = props;
  const [keyCode, setKeyCode] = useState(r.key_code ?? "");
  const [src, setSrc] = useState<ColRef>({ table: r.source_table ?? "", column: r.source_column ?? "" });
  const [tgt, setTgt] = useState<ColRef>({ table: r.target_table ?? "", column: r.target_column ?? "" });

  const s = resolveRef(src, srcState.tables);
  const t = resolveRef(tgt, tgtState.tables);
  const body: UpdateBody = {
    key_code: orNull(keyCode),
    source_table: s.column ? orNull(s.table) : null,
    source_column: orNull(s.column),
    target_table: t.column ? orNull(t.table) : null,
    target_column: orNull(t.column),
  };
  const changed =
    body.key_code !== r.key_code ||
    body.source_table !== r.source_table ||
    body.source_column !== r.source_column ||
    body.target_table !== r.target_table ||
    body.target_column !== r.target_column;

  return (
    <div className="col gap-12 mt-12">
      <hr className="divider" style={{ margin: 0 }} />
      <div className="grid c3">
        <Field label="연계키">
          <select className="select" value={keyCode} disabled={props.locked} onChange={(e) => setKeyCode(e.target.value)}>
            <option value="">연계키 선택</option>
            {props.keyOptions.map((k) => (
              <option key={k.code} value={k.code}>
                {k.code} {k.label}
              </option>
            ))}
          </select>
        </Field>
        <ColumnPicker label={`출발 표 · 컬럼 (${r.source_name})`} state={srcState} value={src} onChange={setSrc} disabled={props.locked} />
        <ColumnPicker label={`도착 표 · 컬럼 (${r.target_name})`} state={tgtState} value={tgt} onChange={setTgt} disabled={props.locked} />
      </div>
      <div className="row wrap">
        <Button size="sm" variant="primary" disabled={props.locked || !changed || !keyCode} busy={props.busy} onClick={() => props.onSave(body)}>
          저장
        </Button>
        <Button size="sm" disabled={props.busy} onClick={props.onCancel}>
          취소
        </Button>
        <span className="small muted">
          {!keyCode ? "연계키를 고르세요" : "연계키·컬럼을 바꾸면 결합 통계를 다시 계산하고 관계가 초안으로 돌아갑니다. 다시 확정해야 정본 그래프에 들어갑니다."}
        </span>
      </div>
    </div>
  );
}
