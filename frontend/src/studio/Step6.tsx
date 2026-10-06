// STEP 6 — 검증: 게이트 0 + SHACL. 판정 전용 화면이며 수정은 원인 단계에서 한다.
import { useEffect, useRef, useState } from "react";
import type { ReactNode, RefObject } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, api, downloadFile, downloads } from "../api";
import type { ShapeRule, ValidationDataset, ValidationLatest, ValidationRun } from "../types";
import { Badge, Banner, Button, Card, CodeBlock, Empty, Field, Modal, QueryState, SeverityBadge, cx, fmtDateTime, fmtNum, shortHash, useToast } from "../ui";
import { useStudio } from "./context";
import { Gate0List, ReadOnlyNote, StepHeader, ValidationRows } from "./shared";

type Mode = "draft" | "publish";
type Busy = "run" | "mode" | "mint" | null;

/** 서버가 받는 미결 사유의 최소 길이 (WaiverIn.reason min_length) */
const WAIVER_MIN = 5;
const WAIVER_MAX = 1000;

export function Step6() {
  const { pid, detail, combo, editable, isAdmin, go, refresh, params } = useStudio();
  const toast = useToast();
  const pubMode = detail.process.pub_mode;
  const q = useQuery({ queryKey: ["process", pid, "validation"], queryFn: () => api.latestValidation(pid) });
  const latest = q.data;

  const [busy, setBusy] = useState<Busy>(null);
  const [lineageMsg, setLineageMsg] = useState<string | null>(null);
  const [mintPing, setMintPing] = useState(0);
  // 다른 화면의 [수정하러 이동] 이 focus=mint 로 보내거나, 이 화면에서 민팅 패널로 올려 보낼 때 강조한다
  const mint = useFlash<HTMLDivElement>(params.focus === "mint" ? `focus:${mintPing}` : mintPing > 0 ? `ping:${mintPing}` : null, !!latest);

  const runValidation = async () => {
    setBusy("run");
    try {
      const r = await api.runValidation(pid);
      await refresh();
      const text = `검증 완료 — 통과 ${r.run.pass_count}/${r.run.datasets.length}건`;
      if (r.run.fail_count > 0) toast(`${text} · 반려 ${r.run.fail_count}건`);
      else toast.ok(text);
    } catch (e) {
      if (e instanceof ApiError && e.code === "LINEAGE_UNRESOLVED") setLineageMsg(e.message);
      else toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  const changeMode = async (next: boolean) => {
    if (next === pubMode) return;
    setBusy("mode");
    try {
      await api.updateProcess(pid, { pub_mode: next });
      await refresh();
      toast.ok(next ? "발행 모드로 전환했습니다" : "초안 모드로 전환했습니다");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  const mintIds = async () => {
    setBusy("mint");
    try {
      const r = await api.mint(pid);
      await refresh();
      if (r.created.length > 0) toast.ok(`발행 ID ${r.created.length}건 발급 — ${r.created.map((m) => m.minted_id).join(", ")}`);
      else toast("새로 발급할 발행 ID 가 없습니다");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  const run = latest?.run ?? null;

  return (
    <div className="col gap-12">
      <StepHeader
        n={6}
        title="검증: 게이트 0 + SHACL"
        sub="정본 그래프를 게이트 0(파서·prefix·인코딩·ID 잔존·정체성)과 SHACL 셰이프로 검증합니다. 판정은 데이터셋 단위이며 Violation 0건이면 통과입니다."
      />
      <ReadOnlyNote />
      <QueryState q={q}>
        {latest && (
          <>
            <div className="grid c2">
              <ModeCard pubMode={pubMode} hasRun={!!run} disabled={!editable || busy !== null} busy={busy === "mode"} onChange={changeMode} />
              <MintPanel
                rows={latest.mint}
                pubMode={pubMode}
                editable={editable}
                isAdmin={isAdmin}
                locked={busy !== null}
                busy={busy === "mint"}
                onMint={mintIds}
                panelRef={mint.ref}
                flash={mint.flash}
              />
            </div>

            <RunBar
              run={run}
              comboCount={combo.length}
              lineageResolved={latest.lineage_resolved}
              waiver={detail.process.lineage_waiver_reason}
              waivedAt={detail.process.lineage_waived_at}
              disabled={!editable || (busy !== null && busy !== "run")}
              busy={busy === "run"}
              onRun={runValidation}
            />

            {latest.stale && (
              <Banner
                tone="warn"
                right={
                  <Button size="sm" variant="dark" busy={busy === "run"} disabled={!editable || (busy !== null && busy !== "run")} onClick={runValidation}>
                    재검증 실행
                  </Button>
                }
              >
                <b>↺ 이전 결과는 무효입니다</b> — {latest.stale}
              </Banner>
            )}

            {run && !latest.stale && run.pass_count >= 1 && (
              <Banner
                tone="ok"
                right={
                  <Button size="sm" variant="primary" onClick={() => go(7)}>
                    STEP 7 직렬화로 →
                  </Button>
                }
              >
                <b>
                  ✓ 검증 통과 {run.pass_count}/{run.datasets.length}건
                </b>{" "}
                — 통과한 데이터셋만 STEP 7 직렬화 대상입니다{run.fail_count > 0 ? ` (반려 ${run.fail_count}건은 제외)` : ""}.
              </Banner>
            )}
            {run && !latest.stale && run.pass_count === 0 && (
              <Banner tone="err">
                <b>통과한 데이터셋이 없습니다</b> — 아래 위반을 원인 단계에서 수정한 뒤 다시 검증하세요. STEP 7 은 통과 1건 이상일 때 열립니다.
              </Banner>
            )}

            {run ? (
              <Results run={run} focusDatasetId={params.dataset} onGoMint={() => setMintPing((n) => n + 1)} />
            ) : (
              <Empty>
                <div className="bold dim">아직 검증을 실행하지 않았습니다</div>
                <div className="mt-4">
                  [▶ 검증 실행] 을 누르면 조합 {fmtNum(combo.length)}건의 정본 그래프를 데이터셋마다 게이트 0 5개 검사(① 파서 통과 · ② prefix 완결 · ③ 인코딩 UTF-8 · ④ ID 잔존 · ⑤ 정체성 일치) →
                  SHACL 셰이프 순으로 판정합니다.
                </div>
                <div className="mt-4">게이트 0 ①~③ 이 실패한 데이터셋은 SHACL 을 실행하지 않습니다. 실행할 때마다 prov:Activity 가 기록됩니다.</div>
              </Empty>
            )}

            <ShapesCard mode={pubMode ? "publish" : "draft"} />
          </>
        )}
      </QueryState>

      {lineageMsg !== null && (
        <Modal title="리니지 미결" onClose={() => setLineageMsg(null)}>
          <LineageForm message={lineageMsg} onClose={() => setLineageMsg(null)} />
        </Modal>
      )}
    </div>
  );
}

// ───────────── 도우미

/** signal 이 바뀔 때(그리고 대상이 그려진 뒤) 대상으로 스크롤하고 2.4초 강조한다. */
function useFlash<E extends HTMLElement>(signal: string | number | null, ready: boolean): { ref: RefObject<E>; flash: boolean } {
  const ref = useRef<E>(null);
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    if (signal === null || !ready) return;
    ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 2400);
    return () => clearTimeout(t);
  }, [signal, ready]);
  return { ref, flash };
}

function ModeBadge({ mode }: { mode: Mode }) {
  return mode === "publish" ? <Badge tone="purple">발행 모드</Badge> : <Badge>초안 모드</Badge>;
}

// ───────────── 모드

function ModeCard(props: { pubMode: boolean; hasRun: boolean; disabled: boolean; busy: boolean; onChange: (pub: boolean) => void }) {
  const { pubMode, disabled } = props;
  const seg = (pub: boolean, label: string) => (
    <button
      type="button"
      className={cx("chip", pubMode === pub && "on", disabled && pubMode !== pub && "dim")}
      aria-pressed={pubMode === pub}
      disabled={disabled}
      onClick={() => props.onChange(pub)}
    >
      {label}
    </button>
  );
  return (
    <Card
      title="검증 모드"
      right={
        <div className="row gap-4" role="group" aria-label="검증 모드">
          {props.busy && <span className="spinner" />}
          {seg(false, "초안 모드")}
          {seg(true, "발행 모드")}
        </div>
      }
    >
      <div className="col gap-4 small dim">
        <div>
          <b>초안 모드</b> — 본체 ID 로 <span className="kbd">…-draft-…</span> 형태의 초안 ID 를 씁니다. 작성 중 점검용이며, 이 모드의 결과로는 카탈로그에 발행할 수 없습니다.
        </div>
        <div>
          <b>발행 모드</b> — 민팅 대장에 등록된 발행 ID 만 쓰고, 발행 전용 셰이프를 추가로 적용합니다. 발행 ID 가 없는 데이터셋은 게이트 0 ④ ID 잔존 검사에서 반려됩니다.
        </div>
        <div className="muted">모드를 바꾸면 이전 검증 결과는 무효가 됩니다{props.hasRun ? " — 바꾼 모드로 다시 검증하세요" : ""}.</div>
      </div>
    </Card>
  );
}

// ───────────── 민팅

function MintPanel(props: {
  rows: ValidationLatest["mint"];
  pubMode: boolean;
  editable: boolean;
  isAdmin: boolean;
  locked: boolean;
  busy: boolean;
  onMint: () => void;
  panelRef: RefObject<HTMLDivElement>;
  flash: boolean;
}) {
  const { rows, pubMode, isAdmin, editable } = props;
  const missing = rows.filter((r) => !r.minted_id).length;
  const blockedReason = !isAdmin ? "관리자 권한 필요" : !editable ? "진행 중인 프로세스에서만 발급할 수 있습니다" : missing === 0 ? "모든 데이터셋에 발행 ID 가 있습니다" : "";
  const using = <Badge tone="info">현재 모드에서 사용</Badge>;
  return (
    <div ref={props.panelRef} className={cx("card", pubMode && "accent-top", props.flash && "flash")}>
      <div className="card-head">
        <div className="card-title">
          발행 ID 민팅 대장
          {missing > 0 ? <Badge tone={pubMode ? "err" : "warn"}>미발급 {missing}건</Badge> : rows.length > 0 && <Badge tone="ok">전부 발급됨</Badge>}
        </div>
        <Button size="sm" variant={pubMode && missing > 0 ? "primary" : "default"} busy={props.busy} disabled={blockedReason !== "" || props.locked} title={blockedReason || undefined} onClick={props.onMint}>
          발행 ID 발급{missing > 0 ? ` (${missing}건)` : ""}
        </Button>
      </div>
      {pubMode && missing > 0 && (
        <div className="mb-8">
          <Banner tone="err">발행 모드인데 발행 ID 가 없는 데이터셋이 {missing}건 있습니다 — 발급 전에는 게이트 0 ④ 에서 반려됩니다.</Banner>
        </div>
      )}
      {rows.length === 0 ? (
        <Empty>조합에 데이터셋이 없습니다</Empty>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>데이터셋</th>
                <th>초안 ID {!pubMode && using}</th>
                <th>발행 ID {pubMode && using}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.dataset_id}>
                  <td className="bold">{r.name}</td>
                  <td className="mono nowrap">{r.draft_id}</td>
                  <td className="mono nowrap">{r.minted_id ?? <Badge tone="err">미발급</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="small muted mt-8">
        발행 ID 는 대장에 등록된 것만 씁니다 (fallback 발급 금지). 발급은 관리자가 명시적으로 수행하며, 이미 발급된 데이터셋은 건너뜁니다.
        {blockedReason && missing > 0 && <span className="t-warn"> · {blockedReason}</span>}
      </div>
    </div>
  );
}

// ───────────── 실행 바

function RunBar(props: {
  run: ValidationRun | null;
  comboCount: number;
  lineageResolved: boolean;
  waiver: string | null;
  waivedAt: string | null;
  disabled: boolean;
  busy: boolean;
  onRun: () => void;
}) {
  const { run } = props;
  return (
    <div className="card tight">
      <div className="row between wrap">
        <div className="row wrap">
          {run ? (
            <>
              <Badge tone={run.pass_count === run.datasets.length ? "ok" : run.pass_count > 0 ? "warn" : "err"}>
                통과 {run.pass_count}/{run.datasets.length}
              </Badge>
              <Badge tone={run.warning_count > 0 ? "warn" : "muted"}>Warning {fmtNum(run.warning_count)}</Badge>
              <span className="small dim">
                셰이프 <span className="mono">{run.shapes_version}</span>
              </span>
              <ModeBadge mode={run.mode} />
              <span className="small muted">{fmtDateTime(run.ended_at)}</span>
              {run.activity && (
                <span className="small mono muted" title="이 실행을 기록한 prov:Activity">
                  {run.activity}
                </span>
              )}
            </>
          ) : (
            <span className="small muted">검증 대기 — 조합 {fmtNum(props.comboCount)}건이 대상입니다. 실행마다 prov:Activity 가 기록됩니다.</span>
          )}
        </div>
        <Button variant="primary" busy={props.busy} disabled={props.disabled} onClick={props.onRun}>
          {run ? "↺ 재검증 실행" : "▶ 검증 실행"}
        </Button>
      </div>
      {!props.lineageResolved && (
        <div className="small t-warn mt-8">
          ⚠ 리니지 미결 — 조합이 2건 이상인데 확정된 관계가 없습니다. 검증을 실행하면 STEP 5 로 이동하거나 미결 사유를 기록하도록 안내합니다.
        </div>
      )}
      {props.waiver && (
        <div className="small muted mt-8">
          리니지 미결 사유 기록됨 ({fmtDateTime(props.waivedAt)}) — {props.waiver}
        </div>
      )}
    </div>
  );
}

// ───────────── 리니지 미결 (입력 상태는 Modal 안쪽 컴포넌트가 갖는다 — 입력 중 포커스 유지)

function LineageForm({ message, onClose }: { message: string; onClose: () => void }) {
  const { pid, reference, editable, go, refresh } = useStudio();
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const text = reason.trim();
  const types = reference.relation_types.map((t) => t.label).join(" · ");

  const submit = async () => {
    setBusy(true);
    try {
      await api.setWaiver(pid, text);
      const r = await api.runValidation(pid);
      await refresh();
      toast.ok(`미결 사유를 기록하고 검증했습니다 — 통과 ${r.run.pass_count}/${r.run.datasets.length}건`);
      onClose();
    } catch (e) {
      toast.error(e);
      // 사유 기록까지만 성공했을 수 있으므로 화면 상태를 맞춘다
      await refresh().catch(() => undefined);
      setBusy(false);
    }
  };

  return (
    <div className="col gap-12">
      <Banner tone="warn">{message}</Banner>
      <p className="small dim">
        조합이 2건 이상이면 데이터셋 사이의 관계({types})가 1건 이상 확정되어 있어야 검증을 실행합니다. 관계 없이 내보낸 정본은 리니지(prov) 그래프가 비어 있게 되므로, 그대로 진행하려면
        사유를 남겨야 합니다. 사유는 활동 로그에 기록됩니다.
      </p>
      <div className="card tight flat row between wrap">
        <div>
          <div className="bold small">① 관계를 확정한다</div>
          <div className="tiny muted">STEP 5 에서 관계를 1건 이상 확정한 뒤 돌아와 검증합니다.</div>
        </div>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => {
            onClose();
            go(5);
          }}
        >
          STEP 5 로 이동
        </Button>
      </div>
      <div className="card tight flat col">
        <div className="bold small">② 미결 사유를 남기고 진행한다</div>
        <Field label="미결 사유" hint={`${WAIVER_MIN}자 이상 · 현재 ${text.length}자`}>
          <textarea
            className="textarea"
            rows={3}
            maxLength={WAIVER_MAX}
            value={reason}
            disabled={!editable || busy}
            placeholder="예: 단일 소스 시범 검증 — 리니지는 2차에 보강"
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <Button variant="primary" busy={busy} disabled={!editable || text.length < WAIVER_MIN} onClick={submit}>
            사유 기록하고 검증 실행
          </Button>
        </div>
      </div>
    </div>
  );
}

// ───────────── 결과

function Results({ run, focusDatasetId, onGoMint }: { run: ValidationRun; focusDatasetId: number | null; onGoMint: () => void }) {
  const violations = run.datasets.reduce((n, d) => n + d.violation_count, 0);
  const infos = run.datasets.reduce((n, d) => n + d.info_count, 0);
  // 반려를 먼저. 같은 판정끼리는 서버가 준 순서를 유지한다
  const ordered = [...run.datasets].sort((a, b) => Number(a.passed) - Number(b.passed));
  return (
    <>
      <div className="grid c4">
        <Kpi label="통과" value={run.pass_count} unit={`/ ${run.datasets.length} 데이터셋`} tone={run.pass_count > 0 ? "t-ok" : undefined} />
        <Kpi label="반려" value={run.fail_count} unit={`데이터셋 · Violation ${fmtNum(violations)}건`} tone={run.fail_count > 0 ? "t-err" : undefined} />
        <Kpi label="Warning" value={run.warning_count} unit="건 · 통과에 영향 없음" tone={run.warning_count > 0 ? "t-warn" : undefined} />
        <Kpi label="Info" value={infos} unit="건 · 권고" />
      </div>
      {ordered.map((d) => (
        <DatasetCard key={d.dataset_id} d={d} runId={run.id} focused={d.dataset_id === focusDatasetId} onGoMint={onGoMint} />
      ))}
      <div className="small muted">
        ⓘ 이 화면은 판정 전용입니다 — 수정은 [수정하러 이동] 으로 원인 단계에서 하며, 정본이 바뀌면 이 결과는 자동으로 무효가 됩니다.
      </div>
    </>
  );
}

function Kpi({ label, value, unit, tone }: { label: string; value: number; unit: ReactNode; tone?: "t-ok" | "t-warn" | "t-err" }) {
  return (
    <div className="card tight">
      <div className="stat-label">{label}</div>
      <div className="row gap-4" style={{ alignItems: "baseline" }}>
        <span className={cx("stat", tone)}>{fmtNum(value)}</span>
        <span className="tiny muted">{unit}</span>
      </div>
    </div>
  );
}

function DatasetCard({ d, runId, focused, onGoMint }: { d: ValidationDataset; runId: number; focused: boolean; onGoMint: () => void }) {
  const toast = useToast();
  const [showInfo, setShowInfo] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const card = useFlash<HTMLDivElement>(focused ? d.dataset_id : null, true);
  // 게이트 0 ①~③ 이 실패하면 서버는 SHACL 을 실행하지 않고 보고서도 만들지 않는다
  const structuralOk = d.gate0.filter((c) => c.key === "parse" || c.key === "prefix" || c.key === "utf8").every((c) => c.ok);
  const mintFailed = d.gate0.some((c) => c.key === "mint" && !c.ok);

  const download = async () => {
    setDownloading(true);
    try {
      await downloadFile(downloads.validationReport(runId, d.dataset_id), `validation-report-${d.resource_id}.ttl`);
    } catch (e) {
      toast.error(e);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div ref={card.ref} className={cx("card", card.flash && "flash")}>
      <div className="card-head">
        <div className="card-title">
          {d.name}
          <span className="mono muted small">{d.resource_id}</span>
          {d.passed ? <Badge tone="ok">통과</Badge> : <Badge tone="err">반려</Badge>}
        </div>
        <div className="row wrap small muted">
          <span className={cx(d.violation_count > 0 && "t-err bold")}>Violation {fmtNum(d.violation_count)}</span>·
          <span className={cx(d.warning_count > 0 && "t-warn bold")}>Warning {fmtNum(d.warning_count)}</span>·<span>Info {fmtNum(d.info_count)}</span>·
          <span>{fmtNum(d.triple_count)} 트리플</span>
          <span className="mono" title={`정본 체크섬 ${d.checksum}`}>
            #{shortHash(d.checksum)}
          </span>
        </div>
      </div>

      <div className="row between wrap mb-8">
        <div className="small bold dim">게이트 0</div>
        {mintFailed && (
          <button type="button" className="link-btn small" onClick={onGoMint}>
            발행 ID 민팅 대장으로 ↑
          </button>
        )}
      </div>
      <Gate0List checks={d.gate0} />

      <hr className="divider" />

      <div className="row between wrap mb-8">
        <div className="small bold dim">SHACL · 게이트 결과</div>
        {d.info_count > 0 && (
          <label className="check small">
            <input type="checkbox" checked={showInfo} onChange={(e) => setShowInfo(e.target.checked)} />
            Info {fmtNum(d.info_count)}건 표시
          </label>
        )}
      </div>
      {!structuralOk && <div className="small t-warn mb-8">게이트 0 ①~③ 이 실패해 SHACL 은 실행하지 않았습니다 — 구문 문제를 먼저 해결하세요.</div>}
      <ValidationRows rows={d.results} datasetId={d.dataset_id} from={6} hideInfo={!showInfo} />

      <div className="row mt-12">
        <Button size="sm" busy={downloading} disabled={!structuralOk} title={structuralOk ? undefined : "SHACL 을 실행하지 않아 보고서가 없습니다"} onClick={download}>
          ⤓ 검증 보고서 (sh:ValidationReport, Turtle)
        </Button>
      </div>
    </div>
  );
}

// ───────────── 등재 셰이프

function ShapesCard({ mode }: { mode: Mode }) {
  const [open, setOpen] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  const q = useQuery({ queryKey: ["shapes", mode], queryFn: () => api.shapes(mode), enabled: open, staleTime: 5 * 60_000 });
  const rules = q.data?.rules ?? [];
  const publishOnly = rules.filter((r) => r.profile === "publish").length;
  return (
    <div className="card">
      <div className="card-head" style={{ marginBottom: open ? undefined : 0 }}>
        <div className="card-title">
          등재 셰이프
          <ModeBadge mode={mode} />
          {q.data && (
            <span className="small muted">
              <span className="mono">{q.data.version}</span> · 규칙 {fmtNum(rules.length)}개 (공통 {fmtNum(rules.length - publishOnly)} · 발행 전용 {fmtNum(publishOnly)})
            </span>
          )}
        </div>
        <div className="row">
          {open && q.data && (
            <Button size="sm" onClick={() => setSourceOpen(true)}>
              셰이프 원문 보기
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>
            {open ? "접기 ▴" : "펼치기 ▾"}
          </Button>
        </div>
      </div>
      {open && (
        <QueryState q={q}>
          {rules.length === 0 ? (
            <Empty>등재된 셰이프 규칙이 없습니다</Empty>
          ) : (
            <>
              <div className="table-wrap" style={{ maxHeight: 460, overflowY: "auto" }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>이름</th>
                      <th>심각도</th>
                      <th>경로</th>
                      <th>메시지</th>
                      <th>수정 경로</th>
                      <th>프로파일</th>
                      <th>평가</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map((r) => (
                      <ShapeRow key={r.iri} rule={r} mode={mode} />
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="small muted mt-8">
                수정 경로는 위반 행의 [수정하러 이동] 이 보내는 단계입니다.
                {mode === "draft" && publishOnly > 0 && " 발행 전용 규칙은 발행 모드로 검증할 때만 적용됩니다."}
              </div>
            </>
          )}
        </QueryState>
      )}
      {sourceOpen && q.data && (
        <Modal
          wide
          title={
            <>
              셰이프 원문 (Turtle) <span className="small muted mono">{q.data.version}</span> <ModeBadge mode={mode} />
            </>
          }
          onClose={() => setSourceOpen(false)}
        >
          <CodeBlock text={q.data.turtle} />
        </Modal>
      )}
    </div>
  );
}

function ShapeRow({ rule: r, mode }: { rule: ShapeRule; mode: Mode }) {
  const inactive = r.profile === "publish" && mode === "draft";
  return (
    <tr>
      <td>
        <div className={cx("bold", inactive && "muted")}>{r.name}</div>
        {r.local !== r.name && <div className="tiny muted mono">{r.local}</div>}
      </td>
      <td>
        <SeverityBadge severity={r.severity} />
      </td>
      <td className="mono nowrap">{r.path ?? <span className="muted">—</span>}</td>
      <td className={cx(inactive && "muted")}>{r.message || <span className="muted">—</span>}</td>
      <td className="nowrap">
        {r.route ? (
          <>
            STEP {r.route.step} <span className="muted">· {r.route.label}</span>
          </>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
      <td className="nowrap">
        {r.profile === "publish" ? <Badge tone="purple">발행</Badge> : <Badge>공통</Badge>}
        {inactive && <div className="tiny muted">발행 모드에서만 적용</div>}
      </td>
      <td className="nowrap small">{r.evaluator}</td>
    </tr>
  );
}
