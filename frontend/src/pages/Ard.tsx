// ARD 관리 — ARD 스튜디오가 만든 산출물의 보관 · 배포 · 이력 (v0.18, 데이터 카탈로그 화면을 대체)
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, downloadFile, downloads } from "../api";
import { useAuth } from "../auth";
import type { ArdArtifact, ArdDiff, ArdFilters, ArdHistory, ArdKind, ArdPublished, ArdSummary, ArdVersion, ExternalCheck, ShareLink } from "../types";
import { Badge, Banner, Button, ConfirmButton, Empty, Field, Modal, Pager, QueryState, Tabs, cx, fmtBytes, fmtDateTime, fmtNum, shortHash, useToast } from "../ui";

type Tab = "artifacts" | "published" | "history" | "shares" | "check";
type GroupBy = "" | "actor" | "org";

const TABS: { key: Tab; label: string }[] = [
  { key: "artifacts", label: "산출물 보관함" },
  { key: "published", label: "발행본" },
  { key: "history", label: "배포 이력" },
  { key: "shares", label: "공유 링크" },
  { key: "check", label: "외부 정본 검사" },
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
          {tab === "shares" && <SharesTab />}
          {tab === "check" && <CheckTab />}
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
  const [share, setShare] = useState<ArdArtifact | null>(null);
  const [sharePkg, setSharePkg] = useState(false);
  const [compare, setCompare] = useState<{ id: number; title: string; runId: number } | null>(null);
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
                          <>
                            <Button size="sm" variant="outline" busy={busy === `pkg-${a.key}`} disabled={!a.can_download} title="JSON-LD · Croissant · 데이터 카드 · 데이터 사전 + manifest.json 을 한 ZIP 으로" onClick={() => dlPackage(a)}>
                              제출 패키지
                            </Button>
                            <Button size="sm" onClick={() => setCompare({ id: a.dataset!.id, title: a.dataset!.title, runId: a.run_id })} title="이 데이터셋의 다른 회차 · 발행본과 JSON-LD 차이를 봅니다">
                              비교
                            </Button>
                          </>
                        )}
                        {a.can_download && (a.grade === "O" || a.grade === "S1") && (
                          <Button size="sm" onClick={() => { setShare(a); setSharePkg(false); }} title="수요처가 로그인 없이 내려받는 만료형 링크 (O · S1 만)">
                            공유
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
      {share && <ShareModal artifact={share} asPackage={sharePkg} onClose={() => setShare(null)} />}
      {compare && <CompareModal datasetId={compare.id} title={compare.title} initialRunId={compare.runId} onClose={() => setCompare(null)} />}
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


// ───────────── 버전 비교 (v0.19)
export function CompareModal({ datasetId, title, initialRunId, onClose }: { datasetId: number; title: string; initialRunId?: number | null; onClose: () => void }) {
  const vq = useQuery({ queryKey: ["ard", "versions", datasetId], queryFn: () => api.ardVersions(datasetId) });
  const items = vq.data?.items || [];
  const [from, setFrom] = useState<string>("");
  const [to, setTo] = useState<string>("");
  const [onlyChanged, setOnlyChanged] = useState(true);
  useEffect(() => {
    if (!items.length || from || to) return;
    // 기본: 선택한 회차 ↔ 그 직전 회차 (없으면 발행본 ↔ 최신)
    const runs = items.filter((v) => v.kind === "run");
    const idx = runs.findIndex((v) => v.run_id === initialRunId);
    const cur = idx >= 0 ? runs[idx] : runs[0];
    const prev = idx >= 0 && runs[idx + 1] ? runs[idx + 1] : items.find((v) => v.kind === "published") || runs[1];
    if (cur) setTo(cur.ref);
    if (prev) setFrom(prev.ref);
  }, [items, from, to, initialRunId]);
  const dq = useQuery({ queryKey: ["ard", "diff", datasetId, from, to], queryFn: () => api.ardDiff(datasetId, from, to), enabled: !!from && !!to && from !== to });
  const d: ArdDiff | undefined = dq.data;
  const rows = d ? d.rows : [];
  const label = (v: ArdVersion) => `${v.label} · ${fmtDateTime(v.at)}${v.latest ? " · 최신" : ""}${v.status === "withdrawn" ? " · 철회" : ""}`;
  return (
    <Modal title={`버전 비교 — ${title}`} onClose={onClose} wide>
      <QueryState q={vq}>
        {items.length < 2 ? (
          <Empty>비교할 회차가 2개 이상 있어야 합니다 (변환을 한 번 더 실행하거나 발행본이 있어야 함)</Empty>
        ) : (
          <>
            <div className="grid c2">
              <Field label="기준 (이전)">
                <select className="select" value={from} onChange={(e) => setFrom(e.target.value)}>
                  {items.map((v) => (
                    <option key={v.ref} value={v.ref}>
                      {label(v)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="비교 대상 (이후)">
                <select className="select" value={to} onChange={(e) => setTo(e.target.value)}>
                  {items.map((v) => (
                    <option key={v.ref} value={v.ref}>
                      {label(v)}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {from === to && <Banner tone="warn">같은 회차를 골랐습니다</Banner>}
            <QueryState q={dq}>
              {d && (
                <div className="col gap-8 mt-8">
                  {d.identical ? (
                    <Banner tone="ok">
                      <b>차이 없음</b> — 두 판의 정본 그래프가 같습니다 (트리플 {fmtNum(d.unchanged)}개).
                    </Banner>
                  ) : (
                    <Banner tone="info">
                      <b>{d.from.label}</b> → <b>{d.to.label}</b>: 추가 <span className="t-ok bold">{fmtNum(d.added)}</span> · 삭제 <span className="t-err bold">{fmtNum(d.removed)}</span> · 그대로 {fmtNum(d.unchanged)} 트리플
                      {d.truncated && " · 500행까지만 표시"}
                    </Banner>
                  )}
                  {d.by_predicate.length > 0 && (
                    <div className="row wrap gap-4">
                      {d.by_predicate.slice(0, 12).map((p) => (
                        <span key={p.predicate} className="badge" title={`변경 ${p.changed} · 추가 ${p.added} · 삭제 ${p.removed}`}>
                          <span className="mono">{p.predicate}</span> {p.changed + p.added + p.removed}
                        </span>
                      ))}
                    </div>
                  )}
                  {rows.length > 0 && (
                    <>
                      <label className="check small">
                        <input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} /> 값이 바뀐 것만 (추가 · 삭제만 된 행 숨김)
                      </label>
                      <div className="table-wrap" style={{ maxHeight: 420, overflow: "auto" }}>
                        <table className="table">
                          <thead>
                            <tr>
                              <th>속성</th>
                              <th>주어</th>
                              <th>이전</th>
                              <th>이후</th>
                            </tr>
                          </thead>
                          <tbody>
                            {rows.filter((r) => !onlyChanged || r.change === "changed").map((r, i) => (
                              <tr key={i}>
                                <td className="mono small nowrap" title={r.predicate_iri}>
                                  {r.predicate} {r.change === "added" ? <Badge tone="ok">추가</Badge> : r.change === "removed" ? <Badge tone="err">삭제</Badge> : <Badge tone="warn">변경</Badge>}
                                </td>
                                <td className="mono tiny muted" style={{ maxWidth: 200 }}>{r.subject}</td>
                                <td className="small" style={{ maxWidth: 320 }}>{r.old.length ? r.old.map((x, j) => <div key={j} className="t-err" style={{ wordBreak: "break-all" }}>{x}</div>) : <span className="muted">—</span>}</td>
                                <td className="small" style={{ maxWidth: 320 }}>{r.new.length ? r.new.map((x, j) => <div key={j} className="t-ok" style={{ wordBreak: "break-all" }}>{x}</div>) : <span className="muted">—</span>}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}
            </QueryState>
          </>
        )}
      </QueryState>
    </Modal>
  );
}

// ───────────── 공유 링크 (v0.19)
function ShareModal({ artifact, asPackage, onClose }: { artifact: ArdArtifact; asPackage: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [days, setDays] = useState(7);
  const [max, setMax] = useState(10);
  const [recipient, setRecipient] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ url: string; expires_at: string } | null>(null);
  const kind = asPackage ? "package" : artifact.kind;
  const targetId = asPackage ? artifact.dataset!.id : artifact.id;
  const create = async () => {
    setBusy(true);
    try {
      const r = await api.createShareLink({ kind, target_id: targetId, dataset_id: artifact.dataset?.id ?? null, days, max_downloads: max, recipient: recipient || null, note: note || null });
      // 주소는 화면이 열린 도메인 기준으로 만든다 (역방향 프록시 뒤에서 백엔드가 보는 Host · 스킴과 다를 수 있다)
      setResult({ url: `${window.location.origin}/share/${r.token}`, expires_at: r.expires_at });
      void qc.invalidateQueries({ queryKey: ["ard"] });
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.url);
      toast.ok("주소를 복사했습니다");
    } catch {
      toast.error(new Error("복사하지 못했습니다 — 주소를 직접 선택해 복사하세요"));
    }
  };
  return (
    <Modal title="공유 링크 만들기" onClose={onClose} footer={result ? <Button variant="primary" onClick={onClose}>닫기</Button> : <><Button onClick={onClose}>취소</Button><Button variant="primary" busy={busy} onClick={create}>링크 만들기</Button></>}>
      <div className="col gap-8">
        <div>
          <div className="bold">{artifact.filename}</div>
          <div className="small muted">
            {artifact.process.name}
            {artifact.dataset && ` · ${artifact.dataset.title}`} · 등급 {artifact.grade}
          </div>
        </div>
        {result ? (
          <>
            <Banner tone="ok">
              <b>링크를 만들었습니다.</b> 이 주소는 지금 한 번만 보입니다 — 복사해서 받는 쪽에 전달하세요. 만료 {fmtDateTime(result.expires_at)} · 최대 {max}회.
            </Banner>
            <div className="row gap-4">
              <input className="input mono" readOnly value={result.url} onFocus={(e) => e.currentTarget.select()} />
              <Button variant="primary" onClick={copy}>
                복사
              </Button>
            </div>
            <p className="tiny muted">받는 쪽은 로그인 없이 열리는 안내 화면에서 내려받습니다. 내려받을 때마다 배포 이력에 남고, 「공유 링크」 탭에서 언제든 회수할 수 있습니다.</p>
          </>
        ) : (
          <>
            <Banner tone="info">O · S1 등급 산출물만 공유 링크를 만들 수 있습니다. 만든 뒤 등급이 올라가면 링크는 자동으로 막힙니다.</Banner>
            <div className="grid c2">
              <Field label="유효 기간">
                <select className="select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
                  {[1, 3, 7, 14, 30, 90].map((d) => (
                    <option key={d} value={d}>
                      {d}일
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="최대 내려받기 횟수">
                <select className="select" value={max} onChange={(e) => setMax(Number(e.target.value))}>
                  {[1, 3, 5, 10, 30, 100].map((d) => (
                    <option key={d} value={d}>
                      {d}회
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="받는 곳 (선택)" hint="기관 · 담당자. 이력과 안내 화면에 표시">
                <input className="input" value={recipient} onChange={(e) => setRecipient(e.target.value)} maxLength={200} placeholder="예: ○○공단 데이터팀 김○○" />
              </Field>
              <Field label="메모 (선택)" hint="협약 번호 · 목적 등">
                <input className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
              </Field>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

function SharesTab() {
  const qc = useQueryClient();
  const toast = useToast();
  const [state, setState] = useState<string>("active");
  const q = useQuery({ queryKey: ["ard", "shares", state], queryFn: () => api.shareLinks(state === "all" ? undefined : state) });
  const [busy, setBusy] = useState<number | null>(null);
  const revoke = async (l: ShareLink) => {
    setBusy(l.id);
    try {
      await api.revokeShareLink(l.id);
      await qc.invalidateQueries({ queryKey: ["ard"] });
      toast.ok(`회수 — ${l.filename}`);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const tone: Record<ShareLink["state"], "ok" | "muted" | "err" | "warn"> = { active: "ok", expired: "muted", revoked: "err", exhausted: "warn" };
  const label: Record<ShareLink["state"], string> = { active: "유효", expired: "만료", revoked: "회수", exhausted: "횟수 소진" };
  return (
    <div>
      <div className="row between wrap mb-8" style={{ alignItems: "center" }}>
        <div className="row gap-4">
          {["active", "expired", "exhausted", "revoked", "all"].map((k) => (
            <button key={k} type="button" className={cx("chip", state === k && "on")} aria-pressed={state === k} onClick={() => setState(k)}>
              {k === "all" ? "전체" : label[k as ShareLink["state"]]}
            </button>
          ))}
        </div>
        <span className="small muted">수요처가 로그인 없이 내려받는 만료형 링크. O · S1 등급만, 최대 {q.data?.max_days ?? 90}일 · {q.data?.max_downloads ?? 100}회. 산출물 보관함의 「공유」 버튼으로 만듭니다.</span>
      </div>
      <QueryState q={q}>
        {q.data && q.data.items.length === 0 ? (
          <Empty>공유 링크가 없습니다</Empty>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>파일</th>
                  <th>상태</th>
                  <th>등급</th>
                  <th>받는 곳</th>
                  <th className="num">내려받기</th>
                  <th>만료</th>
                  <th>만든 사람</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(q.data?.items || []).map((l) => (
                  <tr key={l.id}>
                    <td style={{ minWidth: 220 }}>
                      <div className="bold">{l.filename}</div>
                      <div className="tiny muted mono">
                        {l.kind_label} · 토큰 {l.token_prefix}…{l.process_id != null && <> · <Link to={`/studio/${l.process_id}`}>#{l.process_id}</Link></>}
                      </div>
                      {l.note && <div className="tiny muted">{l.note}</div>}
                    </td>
                    <td>
                      <Badge tone={tone[l.state]}>{label[l.state]}</Badge>
                    </td>
                    <td>{l.grade ? <Badge tone={GRADE_TONE[l.grade] || "muted"}>{l.grade}</Badge> : "—"}</td>
                    <td>{l.recipient || <span className="muted">—</span>}</td>
                    <td className="num">
                      {l.downloads} / {l.max_downloads}
                      {l.last_downloaded_at && <div className="tiny muted">{fmtDateTime(l.last_downloaded_at)}</div>}
                    </td>
                    <td className="nowrap">{fmtDateTime(l.expires_at)}</td>
                    <td className="nowrap">
                      {l.created_by}
                      <div className="tiny muted">{fmtDateTime(l.created_at)}</div>
                    </td>
                    <td className="nowrap right">
                      {l.state === "active" && (
                        <ConfirmButton size="sm" variant="danger" busy={busy === l.id} onConfirm={() => revoke(l)} confirmLabel="회수">
                          회수
                        </ConfirmButton>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
    </div>
  );
}


// ───────────── 외부 정본 검사 (v0.20)
function CheckTab() {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"draft" | "publish">("publish");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<ExternalCheck[]>([]);
  const [over, setOver] = useState(false);
  const run = async (files: File[]) => {
    if (!files.length) return;
    setBusy(true);
    try {
      const r = await api.checkExternal(files.slice(0, 10), mode);
      setResults(r.results);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="col gap-12">
      <Banner tone="info">
        스튜디오 밖에서 만든 <b>Turtle(.ttl) · JSON-LD(.jsonld)</b> 정본을 올리면 STEP 6 과 같은 <b>게이트 0</b>(① 파서 · ② prefix 완결 · ③ UTF-8 · ④ 임시 ID · ⑤ 정체성)을 돌리고, 게이트 0 을 통과한 파일만 <b>SHACL</b> 까지 검사합니다.
        파일은 저장하지 않고 결과 요약만 활동 로그에 남습니다. 타 기관 · 타 도구 산출물의 사전 점검과 "정본 통과 · 오류본 차단" 시연에 씁니다.
      </Banner>
      <div className="row wrap gap-8" style={{ alignItems: "center" }}>
        <span className="small bold dim">검사 모드</span>
        <button type="button" className={cx("chip", mode === "draft" && "on")} aria-pressed={mode === "draft"} onClick={() => setMode("draft")}>초안 (공통 규칙)</button>
        <button type="button" className={cx("chip", mode === "publish" && "on")} aria-pressed={mode === "publish"} onClick={() => setMode("publish")}>발행 (공통 + 발행 규칙 · 임시 ID 검사)</button>
      </div>
      <div
        className={cx("dropzone", over && "over")}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); void run(Array.from(e.dataTransfer.files)); }}
        style={{ padding: 28, textAlign: "center" }}
      >
        <input ref={input} type="file" multiple accept=".ttl,.turtle,.jsonld,.json,.nt,.rdf,.xml,.trig" style={{ display: "none" }} onChange={(e) => { void run(Array.from(e.target.files || [])); e.target.value = ""; }} />
        <div className="bold">정본 파일을 끌어다 놓으세요 (.ttl · .jsonld · .nt · .rdf)</div>
        <div className="small muted mt-4">
          한 번에 10개 · 파일당 5MB · 또는{" "}
          <button type="button" className="link-btn" onClick={() => input.current?.click()}>
            파일 선택
          </button>
        </div>
        {busy && <div className="small mt-8"><span className="spinner" /> 검사 중…</div>}
      </div>
      {results.map((r) => (
        <div key={r.filename} className="card">
          <div className="row between wrap" style={{ alignItems: "center" }}>
            <div>
              <span className="bold">{r.filename}</span>
              {r.format && <span className="kbd" style={{ marginLeft: 6 }}>{r.format}</span>}
              {r.triples != null && <span className="small muted"> · {fmtNum(r.triples)} 트리플</span>}
              {r.shapes_version && <span className="small muted"> · 규칙 {r.shapes_version}</span>}
            </div>
            {r.error ? <Badge tone="err">{r.error}</Badge> : <Badge tone={r.verdict?.startsWith("통과") ? "ok" : r.verdict?.startsWith("차단") ? "err" : "warn"}>{r.verdict}</Badge>}
          </div>
          {r.gate0 && (
            <div className="mt-8">
              <div className="small bold dim mb-4">게이트 0</div>
              <div className="col gap-4">
                {r.gate0.map((c) => (
                  <div key={c.key} className="row small" style={{ gap: 8, alignItems: "flex-start" }}>
                    <Badge tone={c.skipped ? "muted" : c.ok ? "ok" : "err"}>{c.skipped ? "생략" : c.ok ? "PASS" : "FAIL"}</Badge>
                    <span className="bold nowrap">{c.name}</span>
                    <span className="muted" style={{ wordBreak: "break-all" }}>{c.detail}</span>
                  </div>
                ))}
              </div>
              {r.blocked_before_shacl && <div className="small t-err bold mt-4">→ 게이트 0 ①~③ 실패: SHACL 도달 전 반려 (STEP 6 과 같은 규칙)</div>}
            </div>
          )}
          {r.shacl && (
            <div className="mt-8">
              <div className="small bold dim mb-4">
                SHACL — {r.shacl.conforms ? <span className="t-ok">적합</span> : <span className="t-err">위반 {r.shacl.violations}건</span>} · 경고 {r.shacl.warnings} · 정보 {r.shacl.infos}
              </div>
              {r.shacl.rows.length > 0 && (
                <div className="table-wrap" style={{ maxHeight: 360, overflow: "auto" }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>심각도</th>
                        <th>Shape</th>
                        <th>메시지</th>
                        <th>초점 · 경로</th>
                        <th>값</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.shacl.rows.filter((x) => x.severity !== "Info").map((x, i) => (
                        <tr key={i}>
                          <td><Badge tone={x.severity === "Violation" ? "err" : "warn"}>{x.severity}</Badge></td>
                          <td className="mono small">{x.shape}</td>
                          <td className="small">{x.message}</td>
                          <td className="mono tiny muted">{x.focus}{x.path && ` · ${x.path}`}</td>
                          <td className="tiny muted" style={{ maxWidth: 240, wordBreak: "break-all" }}>{x.value || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
