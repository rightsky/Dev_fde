// ARD 관리 — ARD 스튜디오가 만든 산출물의 보관 · 배포 · 이력 (v0.18, 데이터 카탈로그 화면을 대체)
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, downloadFile, downloads } from "../api";
import { useAuth } from "../auth";
import type { ArdArtifact, ArdFilters, ArdHistory, ArdKind, ArdPublished, ArdSummary } from "../types";
import { Badge, Banner, Button, ConfirmButton, Empty, Pager, QueryState, Tabs, cx, fmtBytes, fmtDateTime, fmtNum, shortHash, useToast } from "../ui";

type Tab = "artifacts" | "published" | "history";
type GroupBy = "" | "actor" | "org";

const TABS: { key: Tab; label: string }[] = [
  { key: "artifacts", label: "산출물 보관함" },
  { key: "published", label: "발행본" },
  { key: "history", label: "배포 이력" },
];
const GROUPS: { key: GroupBy; label: string }[] = [
  { key: "", label: "구분 없음" },
  { key: "actor", label: "작업자별" },
  { key: "org", label: "작업조직별" },
];
const KIND_TONE: Record<ArdKind, "info" | "dark" | "purple" | "ok" | "muted"> = { file: "info", zip: "dark", validation: "purple", diagnosis: "ok", package: "muted" };
const GRADE_TONE: Record<string, "ok" | "info" | "warn" | "err"> = { O: "ok", S1: "info", S2: "warn", C: "err" };

/** 페이지 · 크기 · 필터를 URL 에 두어 새로고침 · 뒤로가기 · 공유에 살아남게 한다 */
function useListParams(prefix: string, defaults: Record<string, string>) {
  const [sp, setSp] = useSearchParams();
  const get = (k: string) => sp.get(`${prefix}.${k}`) ?? defaults[k] ?? "";
  const set = (patch: Record<string, string | number | undefined>) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(patch)) {
      const key = `${prefix}.${k}`;
      if (v === undefined || v === "" || String(v) === defaults[k]) next.delete(key);
      else next.set(key, String(v));
    }
    // 필터가 바뀌면 1페이지로
    if (!("page" in patch)) next.delete(`${prefix}.page`);
    setSp(next, { replace: true });
  };
  return { get, set };
}

export function ArdPage() {
  const [sp, setSp] = useSearchParams();
  const tab = (sp.get("tab") as Tab) || "artifacts";
  const setTab = (t: Tab) => {
    const next = new URLSearchParams(sp);
    next.set("tab", t);
    setSp(next, { replace: true });
  };
  const summary = useQuery({ queryKey: ["ard", "summary"], queryFn: api.ardSummary, refetchInterval: 60_000 });
  const filters = useQuery({ queryKey: ["ard", "filters"], queryFn: api.ardFilters });
  return (
    <div>
      <div className="row between top wrap">
        <div>
          <h1 className="page-title">ARD 관리</h1>
          <p className="page-sub">ARD 스튜디오가 만든 산출물(정본 · 파생 포맷 · 보고서)을 보관하고, 외부에 내준 발행본과 배포 이력을 관리합니다.</p>
        </div>
      </div>
      <QueryState q={summary}>{summary.data && <SummaryRow s={summary.data} />}</QueryState>
      <div className="mt-12 mb-12">
        <Tabs<Tab> tabs={TABS.map((t) => ({ key: t.key, label: t.label }))} value={tab} onChange={setTab} />
      </div>
      {filters.data && (
        <>
          {tab === "artifacts" && <ArtifactsTab filters={filters.data} sizes={summary.data?.page_sizes} />}
          {tab === "published" && <PublishedTab filters={filters.data} sizes={summary.data?.page_sizes} />}
          {tab === "history" && <HistoryTab filters={filters.data} sizes={summary.data?.page_sizes} />}
        </>
      )}
    </div>
  );
}

// ───────────── 요약
function SummaryRow({ s }: { s: ArdSummary }) {
  const { isAdmin } = useAuth();
  return (
    <div className="col gap-8">
      <div className="grid c4">
        <Kpi label="산출물" value={fmtNum(s.artifacts)} sub={`파일 ${fmtNum(s.files)} · 묶음 · 보고서 포함`} />
        <Kpi label="발행본" value={fmtNum(s.published)} sub={`ai-ready ${s.published ? Math.round((s.ai_ready / s.published) * 100) : 0}% · 철회 ${fmtNum(s.withdrawn)}`} />
        <Kpi label="이번 주 다운로드" value={fmtNum(s.downloads_7d)} sub={`MCP 호출 30일 ${fmtNum(s.mcp_calls_30d)}건`} />
        <Kpi label="재변환 필요" value={fmtNum(s.stale.length)} sub="정본이 바뀌어 산출물이 최신 아님" tone={s.stale.length ? "warn" : undefined} />
      </div>
      {s.stale.length > 0 && (
        <Banner tone="warn">
          <b>재변환 필요 {s.stale.length}건</b> —{" "}
          {s.stale.slice(0, 5).map((x, i) => (
            <span key={x.process.id}>
              {i > 0 && " · "}
              <Link to={`/studio/${x.process.id}/step/${x.step}`}>{x.process.name}</Link> <span className="muted">(STEP {x.step})</span>
            </span>
          ))}
          {s.stale.length > 5 && ` 외 ${s.stale.length - 5}건`}. 해당 프로세스에서 [검증 → 변환 → 진단 다시 실행] 을 누르면 됩니다.
        </Banner>
      )}
      {s.retention.candidates > 0 && isAdmin && <RetentionBanner r={s.retention} />}
    </div>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "warn" }) {
  return (
    <div className={cx("card tight", tone === "warn" && "t-warn")}>
      <div className="small dim">{label}</div>
      <div className="bold" style={{ fontSize: 22 }}>
        {value}
      </div>
      {sub && <div className="tiny muted">{sub}</div>}
    </div>
  );
}

function RetentionBanner({ r }: { r: ArdSummary["retention"] }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const apply = async () => {
    setBusy(true);
    try {
      const res = await api.ardRetentionApply();
      await qc.invalidateQueries({ queryKey: ["ard"] });
      toast.ok(`보존 정리 — 변환 회차 ${res.deleted}건 삭제`);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Banner
      tone="info"
      right={
        <ConfirmButton size="sm" busy={busy} onConfirm={apply} confirmLabel="정리 실행">
          보존 정리
        </ConfirmButton>
      }
    >
      보존 정책(프로세스당 최신 {r.keep}회차 보관)을 넘는 변환 회차 <b>{fmtNum(r.candidates)}건</b> ({fmtBytes(r.size)})이 있습니다. 발행본이 참조하는 회차는 지우지 않습니다. 새 변환을 실행할 때도 자동으로 정리됩니다.
    </Banner>
  );
}

// ───────────── 공용 필터 줄
function FilterBar(props: {
  filters: ArdFilters;
  q: string;
  onQ: (v: string) => void;
  actor: string;
  onActor: (v: string) => void;
  org: string;
  onOrg: (v: string) => void;
  group: GroupBy;
  onGroup: (g: GroupBy) => void;
  children?: ReactNode;
  right?: ReactNode;
  placeholder?: string;
}) {
  const [text, setText] = useState(props.q);
  useEffect(() => setText(props.q), [props.q]);
  useEffect(() => {
    const t = setTimeout(() => {
      if (text.trim() !== props.q) props.onQ(text.trim());
    }, 300);
    return () => clearTimeout(t);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="row between wrap mb-8" style={{ alignItems: "center", gap: 8 }}>
      <div className="row wrap" style={{ gap: 6, alignItems: "center" }}>
        <input className="input" style={{ width: 220 }} type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder={props.placeholder || "검색"} aria-label="검색" />
        <select className="select" style={{ width: 180 }} value={props.actor} onChange={(e) => props.onActor(e.target.value)} aria-label="작업자">
          <option value="">작업자 전체</option>
          {props.filters.actors.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
              {a.org ? ` (${a.org})` : ""}
            </option>
          ))}
        </select>
        <select className="select" style={{ width: 170 }} value={props.org} onChange={(e) => props.onOrg(e.target.value)} aria-label="작업조직">
          <option value="">작업조직 전체</option>
          {props.filters.orgs.map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
        {props.children}
        <span className="small muted" style={{ marginLeft: 6 }}>
          구분:
        </span>
        <div className="row gap-4" role="group" aria-label="구분">
          {GROUPS.map((g) => (
            <button key={g.key} type="button" className={cx("chip", props.group === g.key && "on")} aria-pressed={props.group === g.key} onClick={() => props.onGroup(g.key)}>
              {g.label}
            </button>
          ))}
        </div>
      </div>
      {props.right}
    </div>
  );
}

/** 작업자 · 작업조직으로 묶어 볼 때 그룹 머리글 행 */
function groupRows<T>(items: T[], group: GroupBy, keyOf: (t: T) => string, render: (t: T) => ReactNode, colSpan: number): ReactNode[] {
  if (!group) return items.map(render);
  const out: ReactNode[] = [];
  let last: string | null = null;
  for (const it of items) {
    const k = keyOf(it) || (group === "actor" ? "(작업자 없음)" : "(조직 미지정)");
    if (k !== last) {
      out.push(
        <tr key={`g-${k}`} className="group-row">
          <td colSpan={colSpan} className="bold small" style={{ background: "var(--surface-2, #f6f7f9)" }}>
            {group === "actor" ? "작업자" : "작업조직"} · {k} <span className="muted">(이 페이지 {items.filter((x) => (keyOf(x) || "") === (keyOf(it) || "")).length}건)</span>
          </td>
        </tr>,
      );
      last = k;
    }
    out.push(render(it));
  }
  return out;
}

const actorKey = (a: { actor: { name: string } | null }) => a.actor?.name || "";
const orgKey = (a: { org: string | null }) => a.org || "";

// ───────────── 탭 1 · 산출물 보관함
function ArtifactsTab({ filters, sizes }: { filters: ArdFilters; sizes?: number[] }) {
  const { get, set } = useListParams("a", { page: "1", size: "20", latest: "1" });
  const toast = useToast();
  const group = get("group") as GroupBy;
  const params = {
    page: Number(get("page")), size: Number(get("size")), q: get("q") || undefined, kind: get("kind") || undefined, latest_only: get("latest") === "1",
    actor_id: get("actor") ? Number(get("actor")) : undefined, org: get("org") || undefined, sort: group || "created",
  };
  const q = useQuery({ queryKey: ["ard", "artifacts", params], queryFn: () => api.ardArtifacts(params), placeholderData: keepPreviousData });
  const [busy, setBusy] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(() => new Set());
  const dl = async (a: ArdArtifact) => {
    setBusy(a.key);
    try {
      await downloadFile(downloads.ard(a.kind, a.id, a.dataset?.id ?? null), a.filename);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const dlPackage = async (a: ArdArtifact) => {
    if (!a.dataset) return;
    setBusy(`pkg-${a.key}`);
    try {
      await downloadFile(downloads.ardPackage(a.dataset.id), `${a.dataset.title}_제출패키지.zip`);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const items = q.data?.items || [];
  const selected = items.filter((i) => checked.has(i.key) && i.can_download);
  const dlSelected = async () => {
    setBusy("bulk");
    try {
      for (const a of selected) await downloadFile(downloads.ard(a.kind, a.id, a.dataset?.id ?? null), a.filename);
      setChecked(new Set());
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const cols = 10;
  return (
    <div>
      <FilterBar
        filters={filters}
        q={get("q")} onQ={(v) => set({ q: v })}
        actor={get("actor")} onActor={(v) => set({ actor: v })}
        org={get("org")} onOrg={(v) => set({ org: v })}
        group={group} onGroup={(g) => set({ group: g })}
        placeholder="프로세스 · 데이터셋 · 파일명 검색"
        right={
          <div className="row gap-4">
            {selected.length > 0 && (
              <Button size="sm" variant="primary" busy={busy === "bulk"} onClick={dlSelected}>
                선택 {selected.length}건 내려받기
              </Button>
            )}
          </div>
        }
      >
        <select className="select" style={{ width: 150 }} value={get("kind")} onChange={(e) => set({ kind: e.target.value })} aria-label="종류">
          <option value="">종류 전체</option>
          {filters.kinds.map((k) => (
            <option key={k.kind} value={k.kind}>
              {k.label}
            </option>
          ))}
        </select>
        <label className="check small" style={{ marginLeft: 4 }}>
          <input type="checkbox" checked={get("latest") === "1"} onChange={(e) => set({ latest: e.target.checked ? "1" : "0" })} /> 최신 회차만
        </label>
      </FilterBar>
      <QueryState q={q}>
        {q.data && q.data.total === 0 ? (
          <Empty>조건에 맞는 산출물이 없습니다. STEP 6 검증 · STEP 7 변환 · STEP 8 진단을 실행하면 여기에 쌓입니다</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 28 }} />
                  <th>프로세스 · 데이터셋</th>
                  <th>종류</th>
                  <th>형식</th>
                  <th>회차</th>
                  <th>등급</th>
                  <th className="num">크기</th>
                  <th>작업자 · 조직</th>
                  <th>생성</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {groupRows(items, group, group === "actor" ? actorKey : orgKey, (a) => (
                  <tr key={a.key} className={cx(!a.latest && "muted")}>
                    <td>
                      <input type="checkbox" aria-label="선택" disabled={!a.can_download} checked={checked.has(a.key)} onChange={(e) => setChecked((s) => { const n = new Set(s); if (e.target.checked) n.add(a.key); else n.delete(a.key); return n; })} />
                    </td>
                    <td style={{ minWidth: 220 }}>
                      <div>
                        <Link to={`/studio/${a.process.id}`}>{a.process.name}</Link>
                        {a.process.status === "completed" && <Badge tone="muted">완료</Badge>}
                      </div>
                      {a.dataset && <div className="small dim">{a.dataset.title}</div>}
                      <div className="tiny muted mono">{a.filename}</div>
                    </td>
                    <td>
                      <Badge tone={KIND_TONE[a.kind]}>{a.kind_label}</Badge>
                    </td>
                    <td>
                      <span className="kbd">{a.format_label}</span>
                      {a.detail && <div className="tiny muted">{a.detail}</div>}
                    </td>
                    <td className="nowrap">
                      #{a.run_id} {a.latest ? <Badge tone="ok">최신</Badge> : <Badge tone="muted">이전</Badge>}
                      {a.mode && <div className="tiny muted">{a.mode === "publish" ? "발행 모드" : "초안 모드"}</div>}
                    </td>
                    <td>{a.grade ? <Badge tone={GRADE_TONE[a.grade] || "muted"}>{a.grade}</Badge> : <span className="muted">—</span>}</td>
                    <td className="num" title={a.sha256 ? `SHA-256 ${a.sha256}` : undefined}>
                      {fmtBytes(a.size)}
                      {a.sha256 && <div className="tiny muted mono">{shortHash(a.sha256, 10)}…</div>}
                    </td>
                    <td className="nowrap">
                      {a.actor ? a.actor.name : <span className="muted">—</span>}
                      {a.org && <div className="tiny muted">{a.org}</div>}
                    </td>
                    <td className="nowrap">{fmtDateTime(a.created_at)}</td>
                    <td>
                      <div className="row gap-4" style={{ justifyContent: "flex-end" }}>
                        <Button size="sm" busy={busy === a.key} disabled={!a.can_download} title={a.can_download ? a.filename : "열람 전용 계정은 O 등급 산출물만 내려받을 수 있습니다"} onClick={() => dl(a)}>
                          ⤓ 내려받기
                        </Button>
                        {a.kind === "file" && a.format === "jsonld" && a.dataset && (
                          <Button size="sm" variant="outline" busy={busy === `pkg-${a.key}`} disabled={!a.can_download} title="JSON-LD · Croissant · 데이터 카드 · 데이터 사전 + manifest.json 을 한 ZIP 으로" onClick={() => dlPackage(a)}>
                            제출 패키지
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ), cols)}
              </tbody>
            </table>
          </div>
        )}
        {q.data && <Pager page={q.data.page} pages={q.data.pages} size={q.data.size} total={q.data.total} sizes={sizes} onPage={(p) => set({ page: p })} onSize={(s) => set({ size: s, page: 1 })} />}
      </QueryState>
      <p className="tiny muted mt-8">
        「제출 패키지」는 데이터셋 하나의 JSON-LD(정본) · Croissant · 데이터 카드 · 데이터 사전과 체크섬 · 발행 ID · 등급을 적은 manifest.json 을 한 ZIP 으로 묶습니다. 포털 · 수요처에 보낼 때 이 파일 하나면 됩니다. 모든 내려받기는 배포 이력에 남습니다.
      </p>
    </div>
  );
}

// ───────────── 탭 2 · 발행본
function PublishedTab({ filters, sizes }: { filters: ArdFilters; sizes?: number[] }) {
  const { get, set } = useListParams("p", { page: "1", size: "20", status: "published" });
  const group = get("group") as GroupBy;
  const params = {
    page: Number(get("page")), size: Number(get("size")), q: get("q") || undefined, status: get("status") || undefined, kind: get("kind") || undefined,
    actor_id: get("actor") ? Number(get("actor")) : undefined, org: get("org") || undefined, sort: group || "created",
  };
  const q = useQuery({ queryKey: ["ard", "published", params], queryFn: () => api.ardPublished(params), placeholderData: keepPreviousData });
  const items = q.data?.items || [];
  const cols = 8;
  return (
    <div>
      <FilterBar
        filters={filters}
        q={get("q")} onQ={(v) => set({ q: v })}
        actor={get("actor")} onActor={(v) => set({ actor: v })}
        org={get("org")} onOrg={(v) => set({ org: v })}
        group={group} onGroup={(g) => set({ group: g })}
        placeholder="제목 · 발행 ID · 기관 · 키워드 검색"
      >
        <select className="select" style={{ width: 120 }} value={get("status")} onChange={(e) => set({ status: e.target.value })} aria-label="상태">
          <option value="published">발행 중</option>
          <option value="withdrawn">철회</option>
          <option value="all">전체</option>
        </select>
        <select className="select" style={{ width: 120 }} value={get("kind")} onChange={(e) => set({ kind: e.target.value })} aria-label="유형">
          <option value="">유형 전체</option>
          <option value="dataset">데이터셋</option>
          <option value="stream">스트림</option>
        </select>
      </FilterBar>
      <QueryState q={q}>
        {q.data && q.data.total === 0 ? (
          <Empty>발행본이 없습니다. STEP 7 에서 발행하거나 검수 큐에서 승인하면 여기에 나타납니다</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>발행 ID · 제목</th>
                  <th>상태</th>
                  <th>등급 · 공개</th>
                  <th>준비도</th>
                  <th>MCP</th>
                  <th>발행자 · 조직</th>
                  <th>발행 시각</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {groupRows(items, group, group === "actor" ? actorKey : orgKey, (e: ArdPublished) => (
                  <tr key={e.resource_id}>
                    <td style={{ minWidth: 240 }}>
                      <Link to={`/ard/published/${encodeURIComponent(e.resource_id)}`} className="bold">
                        {e.title}
                      </Link>
                      <div className="tiny muted mono">
                        {e.resource_id} · v{e.version} · {e.kind === "stream" ? "스트림" : "데이터셋"}
                      </div>
                      {e.process_name && <div className="tiny muted">{e.process_name}</div>}
                    </td>
                    <td>{e.status === "published" ? <Badge tone="ok">발행</Badge> : <Badge tone="warn">철회</Badge>}</td>
                    <td className="nowrap">
                      {e.grade ? <Badge tone={GRADE_TONE[e.grade] || "muted"}>{e.grade}</Badge> : <span className="muted">—</span>}
                      {e.visibility && e.visibility !== "detail" && <Badge tone={e.visibility === "internal" ? "err" : "warn"}>{e.visibility === "internal" ? "내부 한정" : "목록만"}</Badge>}
                    </td>
                    <td>{e.readiness === "ai-ready" ? <Badge tone="ok">ai-ready</Badge> : <Badge tone="muted">{e.readiness || "—"}</Badge>}</td>
                    <td className="nowrap small">
                      {e.mcp_exposed ? <Badge tone="info">노출</Badge> : <Badge tone="muted">비노출</Badge>}
                      {e.s2_grants > 0 && <div className="tiny muted">S2 승인 {e.s2_grants}</div>}
                      {e.last_mcp_call && <div className="tiny muted">최근 호출 {fmtDateTime(e.last_mcp_call)}</div>}
                    </td>
                    <td className="nowrap">
                      {e.actor?.name || e.published_by}
                      {e.org && <div className="tiny muted">{e.org}</div>}
                    </td>
                    <td className="nowrap">{fmtDateTime(e.published_at)}</td>
                    <td>
                      <div className="row gap-4" style={{ justifyContent: "flex-end" }}>
                        <Link className="btn sm" to={`/ard/published/${encodeURIComponent(e.resource_id)}`}>
                          상세
                        </Link>
                      </div>
                    </td>
                  </tr>
                ), cols)}
              </tbody>
            </table>
          </div>
        )}
        {q.data && <Pager page={q.data.page} pages={q.data.pages} size={q.data.size} total={q.data.total} sizes={sizes} onPage={(p) => set({ page: p })} onSize={(s) => set({ size: s, page: 1 })} />}
      </QueryState>
      <p className="tiny muted mt-8">발행본은 외부 에이전트(MCP) 와 포털에 내주는 정본입니다. 철회해도 발행 ID 는 남고 목록에서만 빠집니다 (리니지 추적성 유지).</p>
    </div>
  );
}

// ───────────── 탭 3 · 배포 이력
function HistoryTab({ filters, sizes }: { filters: ArdFilters; sizes?: number[] }) {
  const { get, set } = useListParams("h", { page: "1", size: "20" });
  const toast = useToast();
  const group = get("group") as GroupBy;
  const params = {
    page: Number(get("page")), size: Number(get("size")), q: get("q") || undefined, type: get("type") || undefined,
    actor_id: get("actor") ? Number(get("actor")) : undefined, org: get("org") || undefined, sort: group || "created",
  };
  const q = useQuery({ queryKey: ["ard", "history", params], queryFn: () => api.ardHistory(params), placeholderData: keepPreviousData });
  const [busy, setBusy] = useState(false);
  const csv = async () => {
    setBusy(true);
    try {
      const qs = Object.entries(params).filter(([k, v]) => v !== undefined && !["page", "size", "sort"].includes(k)).map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
      await downloadFile(downloads.ardHistoryCsv(qs), "ARD_배포이력.csv");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const items = q.data?.items || [];
  const typeTone: Record<string, "info" | "ok" | "warn" | "muted" | "dark"> = { artifact_download: "info", package_download: "dark", publish: "ok", withdraw: "warn", republish: "ok", retention_apply: "muted" };
  const cols = 6;
  return (
    <div>
      <FilterBar
        filters={filters}
        q={get("q")} onQ={(v) => set({ q: v })}
        actor={get("actor")} onActor={(v) => set({ actor: v })}
        org={get("org")} onOrg={(v) => set({ org: v })}
        group={group} onGroup={(g) => set({ group: g })}
        placeholder="내용 · 파일명 검색"
        right={
          <Button size="sm" busy={busy} onClick={csv} title="현재 필터의 이력 전체를 CSV 로">
            ⤓ CSV
          </Button>
        }
      >
        <select className="select" style={{ width: 140 }} value={get("type")} onChange={(e) => set({ type: e.target.value })} aria-label="구분">
          <option value="">구분 전체</option>
          {filters.history_types.map((t) => (
            <option key={t.type} value={t.type}>
              {t.label}
            </option>
          ))}
        </select>
      </FilterBar>
      <QueryState q={q}>
        {q.data && q.data.total === 0 ? (
          <Empty>이력이 없습니다. 산출물을 내려받거나 발행 · 철회하면 여기에 남습니다</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>시각</th>
                  <th>구분</th>
                  <th>내용</th>
                  <th>작업자 · 조직</th>
                  <th>프로세스</th>
                  <th>상세</th>
                </tr>
              </thead>
              <tbody>
                {groupRows(items, group, group === "actor" ? (h: ArdHistory) => h.actor.name : orgKey, (h: ArdHistory) => (
                  <tr key={h.id}>
                    <td className="nowrap">{fmtDateTime(h.at)}</td>
                    <td>
                      <Badge tone={typeTone[h.type] || "muted"}>{h.type_label}</Badge>
                    </td>
                    <td>{h.text}</td>
                    <td className="nowrap">
                      {h.actor.name}
                      {h.org && <div className="tiny muted">{h.org}</div>}
                    </td>
                    <td className="nowrap">{h.process_id != null ? <Link to={`/studio/${h.process_id}`}>#{h.process_id}</Link> : <span className="muted">—</span>}</td>
                    <td className="tiny muted mono" style={{ maxWidth: 320 }}>
                      <PayloadLine p={h.payload} />
                    </td>
                  </tr>
                ), cols)}
              </tbody>
            </table>
          </div>
        )}
        {q.data && <Pager page={q.data.page} pages={q.data.pages} size={q.data.size} total={q.data.total} sizes={sizes} onPage={(p) => set({ page: p })} onSize={(s) => set({ size: s, page: 1 })} />}
      </QueryState>
      <p className="tiny muted mt-8">AI 기본법 제34조 문서 보관(5년)과 N²SF 이력 관리 증빙으로 쓸 수 있도록 다운로드 · 발행 · 철회 · 복원 · 보존 정리를 모두 남깁니다. 삭제 정책이 없어 사실상 영구 보존됩니다.</p>
    </div>
  );
}

function PayloadLine({ p }: { p: Record<string, unknown> }) {
  const parts = useMemo(() => {
    const out: string[] = [];
    if (typeof p.filename === "string") out.push(p.filename);
    if (typeof p.size === "number") out.push(fmtBytes(p.size));
    if (typeof p.sha256 === "string") out.push(`sha256 ${p.sha256.slice(0, 10)}…`);
    if (typeof p.grade === "string") out.push(`등급 ${p.grade}`);
    if (typeof p.resource_id === "string") out.push(p.resource_id);
    if (Array.isArray(p.runs)) out.push(`회차 ${p.runs.join(", ")}`);
    return out;
  }, [p]);
  return <>{parts.join(" · ") || "—"}</>;
}
