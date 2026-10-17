// 검수 큐 — 발행 검수 요청을 보고 승인·반려한다 (가이드라인 3.4.6 표 40 HITL)
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import type { ReviewRequest } from "../types";
import { DatasetTable, RiskBadge, SignalList, STATUS_TONE } from "../review/ReviewParts";
import { Badge, Banner, Button, Card, ConfirmButton, Empty, Field, QueryState, Tabs, fmtDateTime, fmtNum, useToast } from "../ui";

type ListKey = "pending" | "done";

export function ReviewsPage() {
  const rid = Number(useParams().rid) || null;
  const [tab, setTab] = useState<ListKey>("pending");
  const q = useQuery({ queryKey: ["reviews", tab], queryFn: () => api.reviews(tab) });
  const counts = q.data?.counts || {};
  const done = (counts.approved || 0) + (counts.rejected || 0) + (counts.withdrawn || 0);
  return (
    <div>
      <h1 className="page-title">검수 큐</h1>
      <p className="page-sub">
        담당자가 올린 카탈로그 발행 요청을 검토하고 승인 · 반려합니다. 제한공유(N²SF S·C) · 개인정보 의심 · 데이터 결합처럼 위험이 높은 발행은 이 큐를 거쳐야 하고, 승인자는 고위험 신호를 하나씩
        확인해야 합니다 (가이드라인 3.4.6 표 40 HITL). 요청 · 승인 · 반려는 모두 활동 로그에 남습니다.
      </p>
      <div className="grid" style={{ gridTemplateColumns: "minmax(320px, 420px) 1fr", gap: 16, alignItems: "start" }}>
        <Card>
          <Tabs
            tabs={[
              { key: "pending" as ListKey, label: `검수 대기 ${fmtNum(counts.pending || 0)}` },
              { key: "done" as ListKey, label: `처리 완료 ${fmtNum(done)}` },
            ]}
            value={tab}
            onChange={setTab}
          />
          <QueryState q={q}>
            {q.data && q.data.items.length === 0 ? (
              <Empty>{tab === "pending" ? "검수 대기 중인 요청이 없습니다" : "처리한 요청이 없습니다"}</Empty>
            ) : (
              <div className="col gap-8 mt-8">
                {(q.data?.items || []).map((r) => (
                  <ListRow key={r.id} r={r} selected={r.id === rid} />
                ))}
              </div>
            )}
          </QueryState>
        </Card>
        {rid ? <Detail key={rid} id={rid} /> : <Card><Empty>왼쪽에서 요청을 고르세요</Empty></Card>}
      </div>
    </div>
  );
}

function ListRow({ r, selected }: { r: ReviewRequest; selected: boolean }) {
  return (
    <Link to={`/reviews/${r.id}`} className="card tight flat clickable" style={{ textDecoration: "none", color: "inherit", ...(selected ? { borderColor: "var(--primary)", background: "var(--primary-bg)" } : {}) }}>
      <div className="row between wrap">
        <span className="bold">
          #{r.id} {r.process_name}
        </span>
        <div className="row">
          <RiskBadge level={r.risk_level} />
          <Badge tone={STATUS_TONE[r.status]}>{r.status_label}</Badge>
        </div>
      </div>
      <div className="small dim mt-4">
        {r.requested_by} · {fmtDateTime(r.requested_at)} · 데이터셋 {r.datasets.length}건 · 고위험 신호 {r.signals.filter((s) => s.severity === "high").length}건
      </div>
      {r.message && <div className="small mt-4">{r.message}</div>}
    </Link>
  );
}

function Detail({ id }: { id: number }) {
  const { isAdmin, user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["review", id], queryFn: () => api.review(id) });
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const r = q.data;
  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ["reviews"] }), qc.invalidateQueries({ queryKey: ["review", id] }),
    qc.invalidateQueries({ queryKey: ["catalog"] }), r ? qc.invalidateQueries({ queryKey: ["publish-review", r.process_id] }) : Promise.resolve()]);
  const act = async (key: string, fn: () => Promise<string>) => {
    setBusy(key);
    try {
      toast.ok(await fn());
      await refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const toggle = (code: string) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });

  return (
    <QueryState q={q}>
      {r && (() => {
        const high = r.signals.filter((s) => s.severity === "high").map((s) => s.code);
        const allAcked = high.every((c) => checked.has(c));
        const self = r.requested_by_id === user.id;
        const needSelfNote = self && r.risk_level === "high" && note.trim().length < 10;
        const pending = r.status === "pending";
        return (
          <div className="col gap-12">
            <Card
              title={
                <>
                  검수 요청 #{r.id} <RiskBadge level={r.risk_level} /> <Badge tone={STATUS_TONE[r.status]}>{r.status_label}</Badge>
                  {r.self_approved && <Badge tone="warn">자기 승인</Badge>}
                </>
              }
              right={<Link to={`/studio/${r.process_id}/step/7`}>프로세스 STEP 7 열기 →</Link>}
            >
              <dl className="kv">
                <dt>프로세스</dt>
                <dd>{r.process_name}</dd>
                <dt>요청</dt>
                <dd>
                  {r.requested_by} · {fmtDateTime(r.requested_at)}
                </dd>
                <dt>요청 메모</dt>
                <dd>{r.message || <span className="muted">없음</span>}</dd>
                <dt>STEP 8 진단</dt>
                <dd>
                  {r.diagnosis ? (
                    <>
                      {r.diagnosis.score}/{r.diagnosis.max_score}점 ({Math.round(r.diagnosis.ratio * 100)}%){" "}
                      {r.diagnosis.stale && <Badge tone="warn">최신 아님</Badge>} <Link to={`/studio/${r.process_id}/step/8`}>진단 보기</Link>
                    </>
                  ) : (
                    <span className="t-warn">진단 미실행</span>
                  )}
                </dd>
                {!pending && (
                  <>
                    <dt>처리</dt>
                    <dd>
                      {r.reviewer} · {fmtDateTime(r.decided_at)}
                      {r.decision_note && <div className="small">{r.decision_note}</div>}
                    </dd>
                  </>
                )}
              </dl>
              {pending && r.stale && (
                <div className="mt-8">
                  <Banner tone="warn">⚠ {r.stale} — 검토한 내용과 지금 발행될 내용이 다를 수 있어 승인할 수 없습니다. 반려하거나 요청자가 취소한 뒤 다시 요청하세요.</Banner>
                </div>
              )}
            </Card>

            <Card title={`위험 신호 ${r.signals.length}건`}>
              {pending && isAdmin && high.length > 0 && <p className="small dim">승인하려면 고위험 신호를 하나씩 검토하고 확인란에 표시하세요.</p>}
              <SignalList signals={r.signals} checked={checked} onToggle={pending && isAdmin ? toggle : undefined} acknowledged={pending ? undefined : r.acknowledged} />
            </Card>

            <Card title={`발행 대상 ${r.datasets.length}건`}>
              <DatasetTable rows={r.datasets} published={r.published} />
            </Card>

            {pending && (
              <Card title="결정">
                {isAdmin ? (
                  <div className="col gap-8">
                    <Field
                      label="검토 의견"
                      hint={self && r.risk_level === "high" ? "본인이 요청한 고위험 발행입니다 — 직접 승인하려면 사유를 10자 이상 적으세요 (자기 승인으로 기록)" : "반려할 때는 필수입니다"}
                    >
                      <textarea className="textarea" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="예: 차량번호 컬럼은 마스킹 처리 확인 · 결합 키는 도로링크뿐" />
                    </Field>
                    <div className="row" style={{ justifyContent: "flex-end" }}>
                      <Button
                        busy={busy === "reject"}
                        disabled={note.trim().length < 2}
                        title={note.trim().length < 2 ? "반려 사유를 적으세요" : undefined}
                        onClick={() => void act("reject", async () => (await api.rejectReview(id, note), `검수 요청 #${id} 반려`))}
                      >
                        반려
                      </Button>
                      <Button
                        variant="primary"
                        busy={busy === "approve"}
                        disabled={!allAcked || needSelfNote || !!r.stale}
                        title={r.stale ? r.stale : !allAcked ? "고위험 신호를 모두 확인하세요" : needSelfNote ? "자기 승인 사유를 10자 이상 적으세요" : undefined}
                        onClick={() =>
                          void act("approve", async () => {
                            const res = await api.approveReview(id, { note, acknowledged: [...checked] });
                            return `승인 · 카탈로그 발행 ${res.published.length}건 — ${res.published.map((e) => e.resource_id).join(", ")}`;
                          })
                        }
                      >
                        승인하고 발행
                      </Button>
                    </div>
                    {!allAcked && <div className="small t-warn">확인하지 않은 고위험 신호 {high.filter((c) => !checked.has(c)).length}건</div>}
                  </div>
                ) : (
                  <div className="small dim">승인 · 반려는 관리자가 합니다.</div>
                )}
                {(self || isAdmin) && (
                  <div className="row mt-12">
                    <ConfirmButton
                      size="sm"
                      busy={busy === "withdraw"}
                      confirmLabel="정말 취소"
                      title="요청을 취소하면 담당자가 다시 요청해야 합니다"
                      onConfirm={() =>
                        void act("withdraw", async () => {
                          await api.withdrawReview(id);
                          nav("/reviews");
                          return `검수 요청 #${id} 취소`;
                        })
                      }
                    >
                      요청 취소
                    </ConfirmButton>
                  </div>
                )}
              </Card>
            )}
          </div>
        );
      })()}
    </QueryState>
  );
}
