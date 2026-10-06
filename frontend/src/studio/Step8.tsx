// STEP 8 가이드라인 준수 진단.
// 점수·판정·근거는 전부 서버의 진단 실행 결과(DiagRun)에서 온다. 화면은 계산하지 않고 보여 주기만 한다.
// 규칙 세트는 가이드라인 전체가 아니라 일부만 구현하므로, 점수 옆에 그 사실을 항상 함께 적는다.
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, downloadFile, downloads } from "../api";
import { useAuth } from "../auth";
import type { DiagItem, DiagLatest, DiagRun, DiagStatus } from "../types";
import { Badge, Banner, Button, Card, ConfirmButton, Empty, Field, Meter, Modal, QueryState, Tabs, cx, fmtDateTime, useToast } from "../ui";
import { useStudio } from "./context";
import { StepHeader } from "./shared";

// ───────────── 표기 규칙 (라벨·색조만 정한다. 값은 서버 응답 그대로)
type BadgeTone = NonNullable<Parameters<typeof Badge>[0]["tone"]>;
type Level = "ok" | "warn" | "err";
type AttestStatus = "met" | "partial" | "unmet";
type Summary = DiagRun["summary"];
type RoadmapRow = Summary["roadmap"][number];

const STATUS: Record<DiagStatus, { label: string; tone: BadgeTone }> = {
  met: { label: "충족", tone: "ok" },
  partial: { label: "부분", tone: "warn" },
  unmet: { label: "미흡", tone: "err" },
  pending: { label: "확인 대기", tone: "info" },
  na: { label: "해당 없음", tone: "muted" },
};
const ATTEST_LABEL: Record<AttestStatus, string> = { met: "충족", partial: "부분 충족", unmet: "미흡" };
// 판정 방식 배지는 판정 결과 배지(초록·주황·빨강)와 섞이지 않게 다른 색조를 쓴다
const METHOD_TONE: Record<string, BadgeTone> = { "AUTO-GRAPH": "muted", "AUTO-PROFILE": "purple", "HUMAN-ATTEST": "dark" };
const DIFFICULTY_TONE: Record<string, BadgeTone> = { 낮음: "ok", 중간: "warn", 높음: "err" };
const DIFFICULTY_LABEL: Record<number, string> = { 1: "낮음", 2: "중간", 3: "높음" };
const GAUGE_COLOR: Record<Level, string> = { ok: "var(--green)", warn: "var(--orange)", err: "var(--err)" };
const LEVEL_TEXT: Record<Level, string> = { ok: "t-ok", warn: "t-warn", err: "t-err" };

const pctLevel = (pct: number): Level => (pct >= 75 ? "ok" : pct >= 40 ? "warn" : "err");
const fmtScore = (n: number | null | undefined) => (n == null ? "—" : Number.isInteger(n) ? String(n) : n.toFixed(1));
const isAttestStatus = (s: DiagStatus | undefined): s is AttestStatus => s === "met" || s === "partial" || s === "unmet";

/** 자동 증빙만으로 판정이 끝난 HUMAN-ATTEST 항목(예: 개인정보 의심 컬럼 미검출)은 담당자 확인 대상이 아니다. */
function isAttestable(item: DiagItem): boolean {
  if (item.method !== "HUMAN-ATTEST") return false;
  return item.datasets.length === 0 || item.datasets.some((d) => d.status === "pending");
}

function StatusBadge({ status }: { status: DiagStatus }) {
  const s = STATUS[status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

/** 이번 화면에서 기록했지만 아직 재진단에 반영되지 않은 담당자 확인 (진단 실행 단위로 묶는다) */
interface LocalAttest {
  status: AttestStatus;
  evidence: string;
  note: string;
  at: string;
}
interface Recorded {
  runId: number | null;
  items: Record<string, LocalAttest>;
}

// ───────────── 화면
export function Step8() {
  const { pid } = useStudio();
  const q = useQuery({ queryKey: ["process", pid, "diagnosis"], queryFn: () => api.latestDiagnosis(pid) });
  return (
    <div className="col" style={{ gap: 14 }}>
      <StepHeader
        n={8}
        title="가이드라인 준수 진단"
        sub="저장된 메타데이터·프로파일·검증 결과로 준수 여부를 판정합니다. 자동 판정과 담당자 확인 항목을 구분해 보여 줍니다."
      />
      <QueryState q={q}>{q.data && <Diagnosis data={q.data} />}</QueryState>
    </div>
  );
}

function Diagnosis({ data }: { data: DiagLatest }) {
  const { pid, detail, combo, gate, refresh, params } = useStudio();
  const { canWrite } = useAuth();
  const toast = useToast();
  const { run, stale, ruleset } = data;
  const [running, setRunning] = useState(false);
  const [recorded, setRecorded] = useState<Recorded>({ runId: null, items: {} });
  const [focus, setFocus] = useState<{ id: string; seq: number } | null>(params.focus ? { id: params.focus, seq: 0 } : null);

  const g8 = gate(8);
  const blocked = !canWrite
    ? "열람 전용 계정은 진단을 실행할 수 없습니다"
    : detail.process.status === "trashed"
      ? "휴지통에 있는 프로세스입니다"
      : g8 && !g8.can_enter
        ? `STEP 8 잠김 — ${g8.reason}`
        : null;

  const runDiagnosis = async () => {
    setRunning(true);
    try {
      const r = await api.runDiagnosis(pid);
      await refresh();
      toast.ok(`진단을 실행했습니다 — ${fmtScore(r.run.score)} / ${fmtScore(r.run.max_score)}점 (구현된 규칙 기준)`);
    } catch (e) {
      toast.error(e);
    } finally {
      setRunning(false);
    }
  };

  // 진단을 다시 실행하면 그 전에 기록한 확인은 결과에 반영된 것이므로 버린다
  const localAttests = run && recorded.runId === run.id ? recorded.items : {};
  const localCount = Object.keys(localAttests).length;
  const onAttested = (itemId: string, a: LocalAttest) => {
    if (!run) return;
    setRecorded((prev) => ({ runId: run.id, items: { ...(prev.runId === run.id ? prev.items : {}), [itemId]: a } }));
  };
  const rerunButton = (
    <Button size="sm" variant="dark" busy={running} disabled={!!blocked} title={blocked || undefined} onClick={runDiagnosis}>
      ↺ 재진단 실행
    </Button>
  );

  return (
    <>
      <Banner tone="info">
        <div>
          <b>{ruleset.guideline}</b> · 규칙 세트 <span className="mono">{ruleset.version}</span> · 구현 <b>{ruleset.implemented_total}</b> / 가이드라인{" "}
          {ruleset.guideline_total}항목
        </div>
        <div className="small mt-4">{ruleset.note}</div>
      </Banner>

      <RunBar run={run} stale={stale} busy={running} blocked={blocked} onRun={runDiagnosis} />

      {run && stale && (
        <Banner tone="warn" right={rerunButton}>
          <b>⚠ 진단 결과가 최신이 아닙니다</b> — {stale}
        </Banner>
      )}
      {run && run.ruleset_version !== ruleset.version && (
        <Banner tone="warn" right={rerunButton}>
          아래 결과는 규칙 세트 <span className="mono">{run.ruleset_version}</span> 로 판정한 것입니다. 현재 규칙 세트는 <span className="mono">{ruleset.version}</span> 입니다 — 재진단하면 현재 규칙으로 다시
          판정합니다.
        </Banner>
      )}
      {run && localCount > 0 && (
        <Banner tone="info" right={rerunButton}>
          담당자 확인 <b>{localCount}건</b>을 기록했습니다. 아래 점수와 판정에는 아직 반영되지 않았습니다 — 재진단을 실행하면 반영됩니다.
        </Banner>
      )}

      {!run ? (
        <Empty>
          아직 진단을 실행하지 않았습니다.
          <br />
          [▶ 진단 실행]을 누르면 조합 {combo.length}건에 대해 구현된 규칙 {ruleset.implemented_total}항목을 판정합니다 (가이드라인 {ruleset.guideline_total}항목 전체가 아닙니다).
        </Empty>
      ) : (
        <>
          <div className="row top wrap" style={{ gap: 14, alignItems: "stretch" }}>
            <ScoreCard run={run} />
            <AreasCard run={run} />
          </div>
          <MethodsCard summary={run.summary} />
          <RoadmapCard roadmap={run.summary.roadmap} onShowItem={(id) => setFocus((f) => ({ id, seq: (f?.seq ?? 0) + 1 }))} />
          <ItemsCard run={run} focus={focus} localAttests={localAttests} onAttested={onAttested} />
        </>
      )}

      <FooterActions run={run} />
    </>
  );
}

// ───────────── 실행 바
function RunBar(props: { run: DiagRun | null; stale: string | null; busy: boolean; blocked: string | null; onRun: () => void }) {
  const { run, stale, busy, blocked } = props;
  return (
    <div className="card tight row between wrap">
      <div className="row wrap" style={{ gap: "6px 14px" }}>
        {!run ? <Badge>대기 — 진단 미실행</Badge> : stale ? <Badge tone="warn">재진단 필요</Badge> : <Badge tone="ok">✓ 진단 완료</Badge>}
        {run && (
          <>
            <Fact label="실행 시각">{fmtDateTime(run.ended_at || run.started_at)}</Fact>
            <Fact label="Activity">
              <span className="mono">{run.activity || "—"}</span>
            </Fact>
            <Fact label="판정 모드">{run.summary.mode === "publish" ? <Badge tone="purple">발행 모드</Badge> : <Badge>초안 모드</Badge>}</Fact>
            <Fact label="대상 데이터셋">{run.summary.dataset_count}건</Fact>
          </>
        )}
        {!run && <span className="small muted">실행할 때마다 prov:Activity 로 기록됩니다.</span>}
      </div>
      <div className="row wrap">
        {blocked && <span className="small t-warn">{blocked}</span>}
        <Button variant="primary" busy={busy} disabled={!!blocked} title={blocked || undefined} onClick={props.onRun}>
          {run ? "↺ 재진단 실행" : "▶ 진단 실행"}
        </Button>
      </div>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="small nowrap">
      <span className="muted">{label}</span> <span className="bold">{children}</span>
    </span>
  );
}

// ───────────── 점수
function Gauge({ ratio, level, label }: { ratio: number; level: Level; label: string }) {
  const r = Math.max(0, Math.min(1, ratio));
  const theta = Math.PI * (1 - r);
  const x = 100 + 80 * Math.cos(theta);
  const y = 100 - 80 * Math.sin(theta);
  return (
    <svg viewBox="0 0 200 108" width="100%" role="img" aria-label={label} style={{ display: "block" }}>
      <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="var(--line)" strokeWidth={16} />
      {r > 0 && <path d={`M 20 100 A 80 80 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)}`} fill="none" stroke={GAUGE_COLOR[level]} strokeWidth={16} />}
    </svg>
  );
}

function ScoreCard({ run }: { run: DiagRun }) {
  const s = run.summary;
  const level = pctLevel(run.pct);
  const ratio = run.max_score > 0 ? run.score / run.max_score : 0;
  const notImplemented = s.guideline_total - s.implemented_total;
  const gain = Math.round((s.potential_score - run.score) * 10) / 10;
  const order: DiagStatus[] = ["met", "partial", "unmet", "pending", "na"];
  return (
    <Card
      title={
        <>
          준수 점수 <Badge tone="dark">구현된 규칙 기준</Badge>
        </>
      }
      style={{ flex: "1 1 320px", maxWidth: 400 }}
    >
      <div style={{ position: "relative", maxWidth: 240, margin: "0 auto" }} title="색 기준: 75% 이상 녹색 · 40~74% 주황 · 40% 미만 빨강">
        <Gauge ratio={ratio} level={level} label={`구현된 규칙 기준 ${fmtScore(run.score)} / ${fmtScore(run.max_score)}점, ${run.pct}%`} />
        <div className="center" style={{ position: "absolute", left: 0, right: 0, bottom: 0 }}>
          <div className="stat">
            {fmtScore(run.score)}{" "}
            <span className="muted" style={{ fontSize: 14, fontWeight: 700 }}>
              / {fmtScore(run.max_score)}점
            </span>
          </div>
          <div className={cx("bold", LEVEL_TEXT[level])}>{run.pct}%</div>
        </div>
      </div>

      <div className="mt-12">
        <Banner tone="warn">
          가이드라인 <b>{s.guideline_total}항목</b> 중 <b>{s.implemented_total}항목</b>만 규칙으로 구현되어 있습니다. 이 점수는 구현된 규칙만으로 계산한 값이며 {s.guideline_total}점 만점 점수가 아닙니다
          {notImplemented > 0 ? ` — 나머지 ${notImplemented}항목은 판정하지 않았습니다.` : "."}
        </Banner>
      </div>

      <div className="row wrap gap-4 mt-12">
        {order.map((k) => (
          <Badge key={k} tone={s.counts[k] > 0 ? STATUS[k].tone : "muted"}>
            {STATUS[k].label} {s.counts[k]}
          </Badge>
        ))}
      </div>
      <div className="small muted mt-8">
        만점 {fmtScore(run.max_score)}점 = 판정 대상 {s.scored_total}항목 (구현 {s.implemented_total} − 해당 없음 {s.counts.na})
      </div>
      <div className="small muted">충족 1.0 · 부분 0.5 · 미흡·대기 0 · 해당 없음은 만점에서 제외</div>
      <hr className="divider" />
      <div className="small">
        쉬운 조치(난이도 낮음)를 모두 반영하면 <b>{fmtScore(s.potential_score)}점</b>{" "}
        <span className="muted">{gain > 0 ? `(현재보다 +${fmtScore(gain)})` : "(남은 쉬운 조치 없음)"}</span>
      </div>
    </Card>
  );
}

// ───────────── 영역별 충족률
function PctCell({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="muted">—</span>;
  return (
    <div className="row" style={{ minWidth: 150 }}>
      <div className="grow">
        <Meter value={pct} tone={pctLevel(pct)} />
      </div>
      <span className="bold right" style={{ width: 38, fontVariantNumeric: "tabular-nums" }}>
        {pct}%
      </span>
    </div>
  );
}

function AreasCard({ run }: { run: DiagRun }) {
  const s = run.summary;
  const auto = s.areas.reduce((n, a) => n + a.auto, 0);
  const manual = s.areas.reduce((n, a) => n + a.manual, 0);
  return (
    <Card title="영역별 충족률" right={<span className="small muted">충족률 = 점수 ÷ 판정 항목 수</span>} style={{ flex: "2 1 520px" }}>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>영역</th>
              <th className="num">판정 항목</th>
              <th className="num">점수</th>
              <th>충족률</th>
              <th className="num">자동 / 수기</th>
              <th className="num">구현 / 가이드라인</th>
            </tr>
          </thead>
          <tbody>
            {s.areas.map((a) => (
              <tr key={a.id}>
                <td>
                  <span className="mono muted">{a.id}</span> <span className="bold">{a.name}</span>
                </td>
                <td className="num">{a.items}</td>
                <td className="num">
                  {fmtScore(a.score)} / {a.items}
                </td>
                <td>
                  <PctCell pct={a.pct} />
                </td>
                <td className="num">
                  {a.auto} / {a.manual}
                </td>
                <td className={cx("num", a.implemented < a.guideline_items && "t-warn")}>
                  구현 {a.implemented} / 가이드라인 {a.guideline_items}
                </td>
              </tr>
            ))}
            <tr>
              <td className="bold">합계</td>
              <td className="num bold">{s.scored_total}</td>
              <td className="num bold">
                {fmtScore(run.score)} / {fmtScore(run.max_score)}
              </td>
              <td>
                <PctCell pct={run.max_score > 0 ? run.pct : null} />
              </td>
              <td className="num bold">
                {auto} / {manual}
              </td>
              <td className={cx("num bold", s.implemented_total < s.guideline_total && "t-warn")}>
                구현 {s.implemented_total} / 가이드라인 {s.guideline_total}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="small muted mt-8">
        판정 항목은 구현된 규칙 가운데 이 조합에 적용되는 항목 수입니다(해당 없음 제외). 구현 수가 가이드라인 항목 수보다 적은 영역의 충족률은 그 영역 전체를 대표하지 않습니다.
      </div>
    </Card>
  );
}

// ───────────── 판정 방식
function MethodsCard({ summary }: { summary: Summary }) {
  return (
    <Card title="판정 방식" right={<span className="small muted">해당 없음 항목은 집계에서 제외</span>}>
      <div className="grid c3">
        {summary.methods.map((m) => (
          <div key={m.id} className="card tight flat">
            <div className="row between">
              <Badge tone={METHOD_TONE[m.id] || "muted"}>{m.id}</Badge>
              <span className="small muted">판정 {m.items}항목</span>
            </div>
            <div className="small mt-8">{m.name}</div>
            <div className="row wrap gap-4 mt-8">
              <Badge tone={m.met > 0 ? "ok" : "muted"}>충족 {m.met}</Badge>
              <Badge tone={m.partial > 0 ? "warn" : "muted"}>부분 {m.partial}</Badge>
              <Badge tone={m.unmet > 0 ? "err" : "muted"}>미흡 {m.unmet}</Badge>
              <Badge tone={m.pending > 0 ? "info" : "muted"}>대기 {m.pending}</Badge>
            </div>
          </div>
        ))}
      </div>
      <div className="small muted mt-8">
        AUTO 항목은 저장된 그래프·프로파일·검증 결과로 자동 판정합니다. HUMAN-ATTEST 항목은 담당자가 증빙과 함께 확인한 기록으로 판정하며, 확인 기록이 없으면 '확인 대기'(0점)입니다.
      </div>
    </Card>
  );
}

// ───────────── 조치 우선순위
function RoadmapCard({ roadmap, onShowItem }: { roadmap: RoadmapRow[]; onShowItem: (itemId: string) => void }) {
  const { go } = useStudio();
  return (
    <Card title="조치 우선순위" right={<span className="small muted">난이도 낮은 순 · 가산 큰 순 — 가산은 조치 후 재진단했을 때 오르는 점수</span>}>
      {roadmap.length === 0 ? (
        <div className="small t-ok bold">✓ 조치가 필요한 항목이 없습니다</div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th className="num">순위</th>
                <th>조치</th>
                <th className="num">가산</th>
                <th>난이도</th>
                <th>근거</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {roadmap.map((r) => (
                <tr key={r.item_id}>
                  <td className="num bold">{r.rank}</td>
                  <td title={r.name}>
                    <div>{r.action}</div>
                    <button className="link-btn tiny" onClick={() => onShowItem(r.item_id)} title="항목별 판정에서 이 항목 보기">
                      <span className="mono">{r.item_id}</span> {r.name}
                    </button>
                  </td>
                  <td className="num bold t-ok">+{fmtScore(r.gain)}</td>
                  <td>
                    <Badge tone={DIFFICULTY_TONE[r.difficulty] || "muted"}>{r.difficulty}</Badge>
                  </td>
                  <td className="small muted">{r.basis}</td>
                  <td className="nowrap right">
                    {r.route && (
                      <Button size="sm" title={`STEP ${r.route.step} · ${r.route.label}`} onClick={() => go(r.route!.step, { focus: r.route!.focus })}>
                        이동
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

// ───────────── 항목별 판정
type StatusFilter = "all" | "todo" | "pending" | "met" | "na";
const FILTER_MATCH: Record<StatusFilter, (s: DiagStatus) => boolean> = {
  all: () => true,
  todo: (s) => s === "unmet" || s === "partial",
  pending: (s) => s === "pending",
  met: (s) => s === "met",
  na: (s) => s === "na",
};
const FILTER_LABEL: Record<StatusFilter, string> = { all: "전체", todo: "미흡·부분", pending: "확인 대기", met: "충족", na: "해당 없음" };

function ItemsCard(props: {
  run: DiagRun;
  focus: { id: string; seq: number } | null;
  localAttests: Record<string, LocalAttest>;
  onAttested: (itemId: string, a: LocalAttest) => void;
}) {
  const { run, focus, localAttests } = props;
  const { detail } = useStudio();
  const { canWrite } = useAuth();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [area, setArea] = useState<string>("all");
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const [flash, setFlash] = useState<string | null>(null);
  const [attesting, setAttesting] = useState<DiagItem | null>(null);
  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // 서버는 종료된 프로세스에도 담당자 확인과 재진단을 허용한다 (휴지통만 제외)
  const attestBlocked = !canWrite ? "열람 전용 계정은 확인을 기록할 수 없습니다" : detail.process.status === "trashed" ? "휴지통에 있는 프로세스입니다" : null;

  const inArea = useMemo(() => (area === "all" ? run.items : run.items.filter((i) => i.area === area)), [run.items, area]);
  const shown = useMemo(() => inArea.filter((i) => FILTER_MATCH[status](i.status)), [inArea, status]);
  const count = (f: StatusFilter) => inArea.filter((i) => FILTER_MATCH[f](i.status)).length;
  const filters: StatusFilter[] = run.summary.counts.na > 0 ? ["all", "todo", "pending", "met", "na"] : ["all", "todo", "pending", "met"];
  const areaTabs = [
    { key: "all", label: `전체 영역 ${run.items.length}` },
    ...run.summary.areas.map((a) => ({ key: a.id, label: `${a.name} ${a.implemented}` })),
  ];

  // 조치 우선순위·다른 화면에서 지목한 항목: 필터를 풀고 펼친 뒤 강조한다
  useEffect(() => {
    if (!focus) return;
    setStatus("all");
    setArea("all");
    setOpen((prev) => new Set(prev).add(focus.id));
    setFlash(focus.id);
    const scroll = setTimeout(() => rowRefs.current[focus.id]?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
    const clear = setTimeout(() => setFlash(null), 2400);
    return () => {
      clearTimeout(scroll);
      clearTimeout(clear);
    };
  }, [focus]);

  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const allOpen = shown.length > 0 && shown.every((i) => open.has(i.id));

  return (
    <Card
      title={
        <>
          항목별 판정{" "}
          <span className="small muted" style={{ fontWeight: 400 }}>
            구현된 {run.items.length}항목 — 가이드라인 {run.summary.guideline_total}항목 중 구현되지 않은 항목은 목록에 없습니다
          </span>
        </>
      }
      right={
        shown.length > 0 ? (
          <button className="link-btn small" onClick={() => setOpen(allOpen ? new Set() : new Set(shown.map((i) => i.id)))}>
            {allOpen ? "모두 접기" : "모두 펼치기"}
          </button>
        ) : undefined
      }
    >
      <div className="row wrap mb-8">
        {filters.map((f) => (
          <button key={f} className={cx("chip", status === f && "on")} aria-pressed={status === f} onClick={() => setStatus(f)}>
            {FILTER_LABEL[f]} <span className="score">{count(f)}</span>
          </button>
        ))}
      </div>
      <Tabs tabs={areaTabs} value={area} onChange={setArea} />

      {shown.length === 0 ? (
        <Empty>조건에 맞는 항목이 없습니다</Empty>
      ) : (
        <div className="col gap-4">
          {shown.map((item) => (
            <ItemRow
              key={item.id}
              item={item}
              open={open.has(item.id)}
              flash={flash === item.id}
              local={localAttests[item.id]}
              attestBlocked={attestBlocked}
              onToggle={() => toggle(item.id)}
              onAttest={() => setAttesting(item)}
              rowRef={(el) => {
                rowRefs.current[item.id] = el;
              }}
            />
          ))}
        </div>
      )}

      {attesting && (
        <AttestModal
          item={attesting}
          local={localAttests[attesting.id]}
          onClose={() => setAttesting(null)}
          onSaved={(a) => {
            props.onAttested(attesting.id, a);
            setAttesting(null);
          }}
        />
      )}
    </Card>
  );
}

function ItemRow(props: {
  item: DiagItem;
  open: boolean;
  flash: boolean;
  local: LocalAttest | undefined;
  attestBlocked: string | null;
  onToggle: () => void;
  onAttest: () => void;
  rowRef: (el: HTMLDivElement | null) => void;
}) {
  const { item, open, local } = props;
  const { go } = useStudio();
  const route = item.route;
  // 이동한 화면에서 바로 고칠 수 있게, 충족하지 못한 첫 데이터셋을 선택해서 넘긴다
  const firstOpen = item.datasets.find((d) => d.status !== "met");
  const attestable = isAttestable(item);
  const bodyId = `diag-item-${item.id}`;
  return (
    <div ref={props.rowRef} className={cx("card tight", props.flash && "flash")} style={{ padding: 0 }}>
      <button
        type="button"
        className="row"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={props.onToggle}
        style={{ width: "100%", gap: 10, padding: "9px 12px", border: 0, background: "none", textAlign: "left", cursor: "pointer" }}
      >
        <span className="mono bold nowrap" style={{ width: 52, flex: "none" }}>
          {item.id}
        </span>
        <span className="grow">
          <span className="bold" style={{ display: "block" }}>
            {item.name}
          </span>
          <span className="small muted" style={{ display: "block" }}>
            {item.basis}
          </span>
        </span>
        {local && <Badge tone="info">확인 기록됨 · 재진단 전</Badge>}
        <Badge tone={METHOD_TONE[item.method] || "muted"}>{item.method}</Badge>
        <StatusBadge status={item.status} />
        <span className="muted" aria-hidden="true" style={{ width: 12, flex: "none" }}>
          {open ? "▾" : "▸"}
        </span>
      </button>

      {open && (
        <div id={bodyId} className="col" style={{ padding: "2px 12px 12px 74px", gap: 10 }}>
          <Section label="판정 근거">
            {item.evidence.length === 0 ? (
              <span className="small muted">기록된 근거가 없습니다</span>
            ) : (
              item.evidence.map((e, i) => (
                <div key={i} className="small">
                  · {e}
                </div>
              ))
            )}
            <div className="small muted mt-4">
              점수 {item.score == null ? "제외 (해당 없음)" : fmtScore(item.score)} · 조치 난이도 {DIFFICULTY_LABEL[item.difficulty] || item.difficulty}
            </div>
          </Section>

          {item.datasets.length > 0 && (
            <Section label={`데이터셋별 판정 ${item.datasets.length}건`}>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>데이터셋</th>
                      <th>판정</th>
                      <th>상세</th>
                      {route && <th />}
                    </tr>
                  </thead>
                  <tbody>
                    {item.datasets.map((d) => (
                      <tr key={d.id}>
                        <td className="bold">{d.name}</td>
                        <td>
                          <StatusBadge status={d.status} />
                        </td>
                        <td>{d.detail}</td>
                        {route && (
                          <td className="nowrap right">
                            {d.status !== "met" && (
                              <button className="link-btn small" onClick={() => go(route.step, { dataset: d.id, focus: route.focus })}>
                                STEP {route.step} 에서 수정
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {item.remedy && (
            <Section label="조치 방법">
              <div className="small">{item.remedy}</div>
            </Section>
          )}

          {item.attestation && (
            <Section label="담당자 확인 기록 (이 진단에 반영됨)">
              <AttestRecord
                status={item.attestation.status}
                by={item.attestation.by}
                at={item.attestation.at}
                evidence={item.attestation.evidence}
                note={item.attestation.note}
              />
            </Section>
          )}
          {local && (
            <Section label="방금 기록한 확인 (재진단 전 — 아직 점수에 반영되지 않음)">
              <AttestRecord status={local.status} by={null} at={local.at} evidence={local.evidence || null} note={local.note || null} />
            </Section>
          )}

          {(route || item.method === "HUMAN-ATTEST") && (
            <div className="row wrap">
              {route && (
                <Button size="sm" title={route.label} onClick={() => go(route.step, { dataset: firstOpen?.id, focus: route.focus })}>
                  수정하러 이동 → STEP {route.step}
                </Button>
              )}
              {attestable && (
                <Button size="sm" variant="outline" disabled={!!props.attestBlocked} title={props.attestBlocked || undefined} onClick={props.onAttest}>
                  담당자 확인
                </Button>
              )}
              {attestable && props.attestBlocked && <span className="small muted">{props.attestBlocked}</span>}
              {item.method === "HUMAN-ATTEST" && !attestable && <span className="small muted">자동 증빙으로 판정이 끝난 항목입니다 — 담당자 확인이 필요하지 않습니다.</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="tiny bold dim" style={{ marginBottom: 3 }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function AttestRecord(props: { status: DiagStatus; by: string | null; at: string; evidence: string | null; note: string | null }) {
  return (
    <dl className="kv">
      <dt>판정</dt>
      <dd>
        <StatusBadge status={props.status} />
      </dd>
      <dt>확인</dt>
      <dd>
        {props.by ? `${props.by} · ` : ""}
        {fmtDateTime(props.at)}
      </dd>
      <dt>증빙</dt>
      <dd style={{ whiteSpace: "pre-wrap" }}>{props.evidence || <span className="muted">없음</span>}</dd>
      <dt>메모</dt>
      <dd>{props.note || <span className="muted">없음</span>}</dd>
    </dl>
  );
}

// ───────────── 담당자 확인
// 입력 상태는 AttestForm 안에만 둔다. Modal 은 다시 그려질 때마다 대화상자로 포커스를 옮기므로,
// Modal 을 그리는 쪽이 글자를 칠 때마다 다시 그려지면 입력 포커스를 잃는다.
function AttestModal(props: { item: DiagItem; local: LocalAttest | undefined; onClose: () => void; onSaved: (a: LocalAttest) => void }) {
  const { item } = props;
  return (
    <Modal
      title={
        <>
          담당자 확인 — <span className="mono">{item.id}</span> {item.name}
        </>
      }
      onClose={props.onClose}
    >
      <AttestForm item={item} local={props.local} onClose={props.onClose} onSaved={props.onSaved} />
    </Modal>
  );
}

function AttestForm(props: { item: DiagItem; local: LocalAttest | undefined; onClose: () => void; onSaved: (a: LocalAttest) => void }) {
  const { item, local } = props;
  const { pid, refresh } = useStudio();
  const toast = useToast();
  const prev = item.attestation;
  const prevStatus = prev?.status;
  const [status, setStatus] = useState<AttestStatus>(local?.status ?? (isAttestStatus(prevStatus) ? prevStatus : "met"));
  const [evidence, setEvidence] = useState(local?.evidence ?? prev?.evidence ?? "");
  const [note, setNote] = useState(local?.note ?? prev?.note ?? "");
  const [busy, setBusy] = useState(false);
  const needEvidence = status !== "unmet";
  const missing = needEvidence && !evidence.trim();

  const save = async () => {
    setBusy(true);
    try {
      const body = { status, evidence: evidence.trim() || undefined, note: note.trim() || undefined };
      await api.attest(pid, item.id, body);
      await refresh();
      toast.ok("확인을 기록했습니다 — 재진단하면 점수에 반영됩니다");
      props.onSaved({ status, evidence: evidence.trim(), note: note.trim(), at: new Date().toISOString() });
    } catch (e) {
      toast.error(e);
      setBusy(false);
    }
  };

  return (
    <div className="col gap-12">
      <div className="small muted">
        {item.basis}
        {item.remedy ? ` · ${item.remedy}` : ""}
      </div>
      {item.evidence.length > 0 && (
        <div className="card tight flat small">
          {item.evidence.map((e, i) => (
            <div key={i}>· {e}</div>
          ))}
        </div>
      )}
      <Field label="판정">
        <select className="select" value={status} disabled={busy} onChange={(e) => setStatus(e.target.value as AttestStatus)}>
          <option value="met">{ATTEST_LABEL.met} (1.0점)</option>
          <option value="partial">{ATTEST_LABEL.partial} (0.5점)</option>
          <option value="unmet">{ATTEST_LABEL.unmet} (0점)</option>
        </select>
      </Field>
      <Field
        label={
          <>
            증빙 {needEvidence ? <Badge tone="err">필수</Badge> : <Badge>선택</Badge>}
          </>
        }
        hint={missing ? "충족·부분 충족 판정에는 증빙(문서 위치·링크·설명)이 필요합니다" : "문서 위치·링크·설명을 적습니다"}
      >
        <textarea className="textarea" value={evidence} disabled={busy} onChange={(e) => setEvidence(e.target.value)} placeholder="예: 문서 관리 시스템의 문서 번호, 공유 폴더 경로, 링크" />
      </Field>
      <Field label="메모">
        <input className="input" value={note} disabled={busy} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <div className="small muted">확인은 prov:Activity 로 기록되고, 같은 항목을 다시 확인하면 이전 기록을 대체합니다. 점수에는 재진단을 실행해야 반영됩니다.</div>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <Button onClick={props.onClose} disabled={busy}>
          취소
        </Button>
        <Button variant="primary" busy={busy} disabled={missing} onClick={save}>
          확인 기록
        </Button>
      </div>
    </div>
  );
}

// ───────────── 하단 동작
function FooterActions({ run }: { run: DiagRun | null }) {
  const { pid, detail, editable, refresh } = useStudio();
  const toast = useToast();
  const [downloading, setDownloading] = useState(false);
  const [completing, setCompleting] = useState(false);
  const p = detail.process;
  const st = detail.state;

  const download = async () => {
    if (!run) return;
    setDownloading(true);
    try {
      await downloadFile(downloads.diagnosisReport(run.id), "diagnosis-report.html");
    } catch (e) {
      toast.error(e);
    } finally {
      setDownloading(false);
    }
  };
  const complete = async () => {
    setCompleting(true);
    try {
      await api.completeProcess(pid);
      await refresh();
      toast.ok("프로세스를 종료했습니다 — 조회 전용으로 전환되었습니다");
    } catch (e) {
      toast.error(e);
    } finally {
      setCompleting(false);
    }
  };

  return (
    <div className="card tight col">
      <div className="row between wrap">
        <div className="row wrap">
          <Button variant="outline" busy={downloading} disabled={!run} title={run ? undefined : "진단을 먼저 실행하세요"} onClick={download}>
            진단 보고서 내려받기 (HTML · 인쇄하면 PDF)
          </Button>
          {run && <span className="small muted">위에 표시된 실행 결과({fmtDateTime(run.ended_at || run.started_at)}) 기준입니다.</span>}
        </div>
        {editable && p.status === "active" && (
          <ConfirmButton variant="dark" confirmLabel="한 번 더 눌러 종료 확정" busy={completing} disabled={!st.serialization.done} onConfirm={complete}>
            프로세스 종료 확정
          </ConfirmButton>
        )}
      </div>
      {editable && p.status === "active" && (
        <div className="small muted">
          종료하면 이 프로세스는 조회 전용이 됩니다. 종료한 뒤에도 프로세스 이름 줄 아래의 [다시 열기]로 다시 열 수 있습니다.
          {!st.serialization.done && <span className="t-warn"> STEP 7 변환을 완료해야 종료할 수 있습니다.</span>}
          {st.serialization.done && !st.diagnosis.done && <span className="t-warn"> 지금 종료하면 최신 진단 결과가 없는 상태로 종료됩니다.</span>}
        </div>
      )}
      {p.status === "completed" && <div className="small muted">종료된 프로세스입니다 ({fmtDateTime(p.completed_at)}). 쓰기 권한이 있으면 화면 위의 [다시 열기]로 다시 열 수 있습니다.</div>}
    </div>
  );
}
