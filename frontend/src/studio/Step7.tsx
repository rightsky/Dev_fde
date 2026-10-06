// STEP 7 — 직렬화 · 발행 포맷 변환 + 파생 자가검증 + 카탈로그 발행
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, downloadFile, downloads } from "../api";
import type { Artifact, CatalogEntry, FormatDef, SelfVerify, SerializationRun } from "../types";
import { Badge, Banner, Button, Card, CodeBlock, Empty, Modal, QueryState, cx, fmtDateTime, fmtNum, shortHash, useToast } from "../ui";
import { useStudio } from "./context";
import { ReadOnlyNote, StepHeader } from "./shared";

type Mode = "draft" | "publish";

export function Step7() {
  const { pid, detail, editable, gate, go, refresh } = useStudio();
  const toast = useToast();
  const q = useQuery({ queryKey: ["process", pid, "serialization"], queryFn: () => api.latestSerialization(pid) });
  const latest = q.data;
  const v = detail.state.validation;

  // 기본은 전체 선택. 뺀 포맷만 기억한다 (Turtle 정본은 뺄 수 없다)
  const [excluded, setExcluded] = useState<ReadonlySet<string>>(new Set());
  const [running, setRunning] = useState(false);
  const [preview, setPreview] = useState<Artifact | null>(null);

  const formats = latest?.formats ?? [];
  const selected = formats.filter((f) => f.key === "ttl" || !excluded.has(f.key)).map((f) => f.key);
  const toggle = (key: string) =>
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  // 변환은 최신 검증이 유효하고 통과가 1건 이상일 때만 가능하다 (서버 게이트와 같은 조건)
  const blockedReason = !v.done || v.pass_count < 1 ? v.stale || gate(7).reason || "STEP 6 검증을 먼저 실행하세요" : "";

  const runSerialization = async () => {
    setRunning(true);
    try {
      const r = await api.runSerialization(pid, selected);
      await refresh();
      const text = `변환 완료 — 자가검증 통과 ${r.run.ok_count}건 · 산출물 ${r.run.artifacts.length}개`;
      if (r.run.fail_count > 0) toast(`${text} · 실패 ${r.run.fail_count}건`);
      else toast.ok(text);
    } catch (e) {
      toast.error(e);
    } finally {
      setRunning(false);
    }
  };

  const run = latest?.run ?? null;

  return (
    <div className="col gap-12">
      <StepHeader
        n={7}
        title="직렬화 · 발행 포맷 변환"
        sub="검증을 통과한 데이터셋의 정본 그래프를 4개 포맷으로 변환하고, 산출물을 실제 파서로 다시 읽어 정본과 대조합니다."
      />
      <ReadOnlyNote />
      <QueryState q={q}>
        {latest && (
          <>
            <div className="grid c4">
              {formats.map((f) => (
                <FormatCard key={f.key} format={f} checked={selected.includes(f.key)} disabled={!editable || running} onToggle={() => toggle(f.key)} />
              ))}
            </div>

            <div className="card tight">
              <div className="row between wrap">
                <div className="row wrap small">
                  <span className="bold">변환 대상</span>
                  <span>
                    최신 검증을 통과한 데이터셋 <b>{fmtNum(v.pass_count)}</b>/{fmtNum(v.total)}건
                  </span>
                  {v.mode && <ModeBadge mode={v.mode} />}
                  {v.total > v.pass_count && <span className="muted">· 반려 {fmtNum(v.total - v.pass_count)}건은 변환하지 않습니다</span>}
                  <span className="muted">
                    · 선택 포맷 {selected.length}/{formats.length}
                  </span>
                </div>
                <Button variant="primary" busy={running} disabled={!editable || blockedReason !== "" || selected.length === 0} title={blockedReason || undefined} onClick={runSerialization}>
                  {run ? "↺ 다시 변환" : "변환 실행"}
                </Button>
              </div>
              {blockedReason && (
                <div className="row wrap small t-warn mt-8">
                  <span>⚠ 변환할 수 없습니다 — {blockedReason}</span>
                  <button type="button" className="link-btn" onClick={() => go(6)}>
                    STEP 6 검증으로 →
                  </button>
                </div>
              )}
            </div>

            {latest.stale && (
              <Banner
                tone="warn"
                right={
                  blockedReason ? (
                    <Button size="sm" variant="dark" onClick={() => go(6)}>
                      STEP 6 재검증으로
                    </Button>
                  ) : (
                    <Button size="sm" variant="dark" busy={running} disabled={!editable} onClick={runSerialization}>
                      다시 변환
                    </Button>
                  )
                }
              >
                <b>↺ 이전 변환 결과는 무효입니다</b> — {latest.stale}
              </Banner>
            )}

            {run ? (
              <>
                <RunSummary run={run} formats={formats} />
                {run.self_verify.length === 0 ? (
                  <Empty>이 실행에는 변환 대상(검증 통과 데이터셋)이 없었습니다</Empty>
                ) : (
                  run.self_verify.map((sv) => (
                    <DatasetResult key={sv.dataset_id} sv={sv} artifacts={run.artifacts.filter((a) => a.dataset_id === sv.dataset_id)} formats={formats} onPreview={setPreview} />
                  ))
                )}
              </>
            ) : (
              <Empty>
                <div className="bold dim">아직 변환을 실행하지 않았습니다</div>
                <div className="mt-4">
                  [변환 실행] 을 누르면 검증 통과 데이터셋마다 정본 그래프 1개에서 선택한 포맷을 만들고, 만든 직후 파생 자가검증(재파싱 · prefix · UTF-8 · TTL↔JSON-LD 동형 · 체크섬 · 스키마 적합)을
                  실행합니다.
                </div>
                <div className="mt-4">자가검증에 실패한 데이터셋의 산출물은 저장하지 않습니다.</div>
              </Empty>
            )}

            <PublishCard run={run} blocked={latest.publish_blocked} />

            {run && !latest.stale && run.ok_count > 0 && (
              <Banner
                tone="ok"
                right={
                  <Button size="sm" variant="primary" onClick={() => go(8)}>
                    STEP 8 가이드라인 준수 진단으로 →
                  </Button>
                }
              >
                <b>✓ 변환 완료</b> — 자가검증을 통과한 {fmtNum(run.ok_count)}건의 산출물이 저장되어 있습니다.
              </Banner>
            )}
            {run && !latest.stale && run.ok_count === 0 && <Banner tone="err">자가검증을 통과한 산출물이 없습니다 — STEP 8 은 변환 1건 이상일 때 열립니다.</Banner>}
          </>
        )}
      </QueryState>

      {preview && <PreviewModal artifact={preview} tag={formats.find((f) => f.key === preview.fmt)?.tag ?? preview.fmt} onClose={() => setPreview(null)} />}
    </div>
  );
}

// ───────────── 도우미

function ModeBadge({ mode }: { mode: Mode }) {
  return mode === "publish" ? <Badge tone="purple">발행 모드</Badge> : <Badge>초안 모드</Badge>;
}

/** 내려받기 1건의 진행 상태와 오류 토스트 */
function useDownload(): { busy: boolean; download: (path: string, name: string) => Promise<void> } {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const download = async (path: string, name: string) => {
    setBusy(true);
    try {
      await downloadFile(path, name);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return { busy, download };
}

/** PUBLISH_BLOCKED 오류의 detail.reasons 를 꺼낸다. 없으면 오류 문구 1건. */
function blockedReasons(e: ApiError): string[] {
  const d: unknown = e.detail;
  if (d && typeof d === "object" && "reasons" in d) {
    const rs = (d as { reasons?: unknown }).reasons;
    if (Array.isArray(rs)) {
      const list = rs.filter((x): x is string => typeof x === "string");
      if (list.length > 0) return list;
    }
  }
  return [e.message];
}

// ───────────── 포맷 선택

function FormatCard({ format: f, checked, disabled, onToggle }: { format: FormatDef; checked: boolean; disabled: boolean; onToggle: () => void }) {
  const fixed = f.key === "ttl";
  return (
    <label className={cx("card tight col gap-4", checked && "selected", !fixed && !disabled && "clickable")}>
      <div className="row between">
        <Badge tone={checked ? "info" : "muted"}>{f.tag}</Badge>
        <span className="check">
          <input type="checkbox" checked={checked} disabled={fixed || disabled} onChange={onToggle} />
          변환 대상
        </span>
      </div>
      <div className="bold">{f.label}</div>
      <div className="small dim">{f.use}</div>
      <div className="tiny mono muted">{f.media_type}</div>
      {fixed && <div className="tiny muted">Turtle 정본은 항상 생성</div>}
    </label>
  );
}

// ───────────── 실행 결과

function RunSummary({ run, formats }: { run: SerializationRun; formats: FormatDef[] }) {
  const zip = useDownload();
  const tagOf = (key: string) => formats.find((f) => f.key === key)?.tag ?? key;
  return (
    <div className="card tight row between wrap">
      <div className="row wrap">
        <Badge tone={run.ok_count > 0 ? "ok" : "muted"}>자가검증 통과 {fmtNum(run.ok_count)}</Badge>
        <Badge tone={run.fail_count > 0 ? "err" : "muted"}>실패 {fmtNum(run.fail_count)}</Badge>
        <ModeBadge mode={run.mode} />
        <span className="row gap-4">
          {run.formats.map((k) => (
            <Badge key={k} tone="info">
              {tagOf(k)}
            </Badge>
          ))}
        </span>
        <span className="small muted">
          산출물 {fmtNum(run.artifacts.length)}개 · {fmtDateTime(run.ended_at)}
        </span>
        {run.activity && (
          <span className="small mono muted" title="이 실행을 기록한 prov:Activity">
            {run.activity}
          </span>
        )}
      </div>
      {run.artifacts.length > 0 && (
        <Button size="sm" variant="outline" busy={zip.busy} onClick={() => zip.download(downloads.runZip(run.id), "artifacts.zip")}>
          ⤓ 전체 ZIP 다운로드 (manifest 포함)
        </Button>
      )}
    </div>
  );
}

function DatasetResult(props: { sv: SelfVerify; artifacts: Artifact[]; formats: FormatDef[]; onPreview: (a: Artifact) => void }) {
  const { sv, formats } = props;
  const okCount = sv.checks.filter((c) => c.ok).length;
  const order = (a: Artifact) => {
    const i = formats.findIndex((f) => f.key === a.fmt);
    return i < 0 ? formats.length : i;
  };
  const artifacts = [...props.artifacts].sort((a, b) => order(a) - order(b));
  return (
    <div className="card">
      <div className="card-head">
        <div className="card-title">
          {sv.name}
          <span className="mono muted small">{sv.resource_id}</span>
          {sv.readiness === "ai-ready" ? <Badge tone="ok">ai-ready</Badge> : <Badge tone="warn">{sv.readiness === "draft" ? "초안 · 필수 필드 결측" : sv.readiness}</Badge>}
          {sv.passed ? (
            <Badge tone="ok">
              자가검증 ✓ {okCount}/{sv.checks.length}
            </Badge>
          ) : (
            <Badge tone="err">
              자가검증 실패 {okCount}/{sv.checks.length}
            </Badge>
          )}
        </div>
        <div className="row wrap small muted">
          <span>{fmtNum(sv.triple_count)} 트리플</span>
          <span className="mono" title={`세트 체크섬 ${sv.checksum}`}>
            세트 #{shortHash(sv.checksum)}
          </span>
        </div>
      </div>
      {!sv.passed && (
        <div className="mb-8">
          <Banner tone="err">
            <b>파생 자가검증 실패 — 산출물을 저장하지 않았습니다</b>
          </Banner>
        </div>
      )}
      <div className="grid c2">
        <div>
          <div className="small bold dim mb-8">파생 자가검증</div>
          <div className="col gap-4">
            {sv.checks.map((c) => (
              <div key={c.name} className="row top small">
                <span className={c.ok ? "t-ok" : "t-err"} style={{ width: 16, flex: "none", fontWeight: 700 }}>
                  {c.ok ? "✓" : "✕"}
                </span>
                <span className="bold nowrap">{c.name}</span>
                <span className={c.ok ? "muted" : "t-err"}>— {c.detail}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="small bold dim mb-8">산출물 {artifacts.length > 0 && <span className="muted">{artifacts.length}개</span>}</div>
          {artifacts.length === 0 ? (
            <div className="small muted">{sv.passed ? "저장된 산출물이 없습니다" : "저장된 산출물이 없습니다 — 자가검증을 통과해야 저장됩니다"}</div>
          ) : (
            <div className="col gap-4">
              {artifacts.map((a) => (
                <ArtifactRow key={a.id} artifact={a} tag={formats.find((f) => f.key === a.fmt)?.tag ?? a.fmt} onPreview={() => props.onPreview(a)} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ArtifactRow({ artifact: a, tag, onPreview }: { artifact: Artifact; tag: string; onPreview: () => void }) {
  const dl = useDownload();
  return (
    <div className="card tight flat row between" style={{ padding: "6px 10px" }}>
      <div className="row grow">
        <Badge tone="info">{tag}</Badge>
        <span className="mono small ellipsis" title={a.filename}>
          {a.filename}
        </span>
      </div>
      <div className="row" style={{ flex: "none" }}>
        <span className="tiny muted nowrap">{a.size_label}</span>
        <span className="tiny mono muted nowrap" title={`sha256 ${a.sha256}`}>
          {shortHash(a.sha256)}
        </span>
        <Button size="sm" onClick={onPreview}>
          미리보기
        </Button>
        <Button size="sm" busy={dl.busy} onClick={() => dl.download(downloads.artifact(a.id), a.filename)}>
          다운로드
        </Button>
      </div>
    </div>
  );
}

function PreviewModal({ artifact: a, tag, onClose }: { artifact: Artifact; tag: string; onClose: () => void }) {
  const { pid } = useStudio();
  const dl = useDownload();
  // 산출물은 저장 뒤 바뀌지 않는다
  const q = useQuery({ queryKey: ["process", pid, "artifact", a.id], queryFn: () => api.artifact(a.id), staleTime: Infinity });
  const isText = a.fmt === "txt";
  return (
    <Modal
      wide
      title={
        <span className="row wrap">
          <Badge tone="info">{tag}</Badge>
          <span className="mono">{a.filename}</span>
        </span>
      }
      onClose={onClose}
      footer={
        <>
          <Button busy={dl.busy} onClick={() => dl.download(downloads.artifact(a.id), a.filename)}>
            ⤓ 다운로드
          </Button>
          <Button variant="dark" onClick={onClose}>
            닫기
          </Button>
        </>
      }
    >
      <dl className="kv mb-8">
        <dt>미디어타입</dt>
        <dd className="mono">{a.media_type}</dd>
        <dt>크기</dt>
        <dd>
          {a.size_label} <span className="muted">({fmtNum(a.size)} B)</span>
        </dd>
        <dt>sha256</dt>
        <dd className="mono">{a.sha256}</dd>
        <dt>세트 체크섬</dt>
        <dd className="mono">{a.set_checksum}</dd>
      </dl>
      <QueryState q={q}>{q.data && <CodeBlock text={q.data.content} wrap={isText} light={isText} />}</QueryState>
    </Modal>
  );
}

// ───────────── 카탈로그 발행

function PublishCard({ run, blocked }: { run: SerializationRun | null; blocked: string[] }) {
  const { pid, detail, combo, isAdmin, go, refresh } = useStudio();
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);
  const [justPublished, setJustPublished] = useState<CatalogEntry[]>([]);
  // 이 프로세스에서 발행되어 카탈로그에 게시 중인 항목
  const cat = useQuery({ queryKey: ["catalog", "process", pid], queryFn: () => api.catalog(), select: (d) => d.items.filter((e) => e.process_id === pid) });

  const v = detail.state.validation;
  const trashed = detail.process.status === "trashed";
  // 조회 시점의 차단 사유가 우선. 비어 있는데 발행 요청이 거절됐다면 그때 받은 사유를 보여 준다
  const reasons = blocked.length > 0 ? blocked : rejected;
  const needsValidation = !detail.process.pub_mode || v.mode !== "publish" || !v.done || v.pass_count < 1;
  const mintedCount = combo.filter((d) => d.minted_id).length;
  const disabledReason = !isAdmin ? "관리자 권한 필요" : trashed ? "휴지통에 있는 프로세스는 발행할 수 없습니다" : "";

  const publish = async () => {
    setBusy(true);
    try {
      const r = await api.publish(pid);
      setRejected([]);
      setJustPublished(r.published);
      await Promise.all([refresh(), qc.invalidateQueries({ queryKey: ["catalog"] })]);
      toast.ok(`카탈로그 발행 ${r.published.length}건 — ${r.published.map((e) => e.resource_id).join(", ")}`);
    } catch (e) {
      if (e instanceof ApiError && e.code === "PUBLISH_BLOCKED") {
        setRejected(blockedReasons(e));
        await refresh().catch(() => undefined);
      }
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };

  // 방금 발행한 항목을 앞에, 그 밖에 이미 게시 중인 항목을 뒤에 둔다
  const justIds = new Set(justPublished.map((e) => e.resource_id));
  const fresh = (cat.data ?? []).filter((e) => !justIds.has(e.resource_id));
  const entries = [...justPublished.map((e) => (cat.data ?? []).find((x) => x.resource_id === e.resource_id) ?? e), ...fresh];
  const currentChecksum = new Map((run?.mode === "publish" ? run.self_verify : []).map((s) => [s.resource_id, s.checksum]));

  return (
    <Card
      title={
        <>
          카탈로그 발행
          {reasons.length === 0 ? <Badge tone="ok">발행 가능</Badge> : <Badge tone="warn">조건 미충족 {reasons.length}건</Badge>}
        </>
      }
      right={
        reasons.length === 0 && (
          <Button variant="primary" busy={busy} disabled={disabledReason !== ""} title={disabledReason || undefined} onClick={publish}>
            카탈로그 발행{run && run.ok_count > 0 ? ` (${run.ok_count}건)` : ""}
          </Button>
        )
      }
    >
      <div className="small dim">아래 세 조건을 모두 만족한 데이터셋만 카탈로그 항목으로 등재합니다. 이미 등재된 항목은 정본이 바뀐 경우 새 버전으로 갱신합니다.</div>
      <ol className="small dim" style={{ margin: "6px 0 0", paddingLeft: 18 }}>
        <li>
          <b>발행 모드 검증 통과</b> — 최신 검증이 발행 모드로 실행되었고 현재 정본과 일치합니다.
        </li>
        <li>
          <b>최신 직렬화 자가검증 통과</b> — 그 검증에 대한 변환 결과가 있고 파생 자가검증을 통과했습니다.
        </li>
        <li>
          <b>발행 ID 민팅</b> — 발행 ID 가 민팅 대장에 등록되어 있습니다{" "}
          <span className="muted">
            (현재 {mintedCount}/{combo.length}건 발급)
          </span>
          .
        </li>
      </ol>

      {reasons.length > 0 ? (
        <div className="col gap-4 mt-12">
          {reasons.map((r) => (
            <Banner key={r} tone="warn">
              ⚠ {r}
            </Banner>
          ))}
          <div className="row wrap mt-4">
            <Button size="sm" variant={needsValidation ? "outline" : "default"} onClick={() => go(6)}>
              STEP 6 에서 발행 모드로 검증
            </Button>
            {!needsValidation && <span className="small muted">발행 모드 검증은 유효합니다 — 위의 [{run ? "↺ 다시 변환" : "변환 실행"}] 으로 최신 검증에 대한 산출물을 만든 뒤 발행하세요.</span>}
          </div>
        </div>
      ) : (
        disabledReason && (
          <div className="small t-warn mt-12">
            ⚠ {disabledReason}
            {!isAdmin && " — 카탈로그 발행은 관리자 계정만 할 수 있습니다."}
          </div>
        )
      )}

      {(entries.length > 0 || cat.error != null) && <hr className="divider" />}
      {cat.error != null && entries.length === 0 && <div className="small muted">게시 중인 항목을 불러오지 못했습니다 — 데이터 카탈로그에서 확인하세요.</div>}
      {entries.length > 0 && (
        <>
          <div className="small bold dim mb-8">
            이 프로세스에서 발행한 카탈로그 항목 <span className="muted">{entries.length}건</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>발행 ID</th>
                  <th>제목</th>
                  <th>버전</th>
                  <th>발행</th>
                  <th>상태</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => {
                  const cur = currentChecksum.get(e.resource_id);
                  return (
                    <tr key={e.resource_id}>
                      <td className="mono nowrap">
                        <Link to={`/catalog/${encodeURIComponent(e.resource_id)}`}>{e.resource_id}</Link>
                      </td>
                      <td className="bold">{e.title}</td>
                      <td className="nowrap">v{e.version}</td>
                      <td className="nowrap small muted">
                        {fmtDateTime(e.published_at)} · {e.published_by}
                      </td>
                      <td>
                        <div className="row wrap gap-4">
                          {justIds.has(e.resource_id) && <Badge tone="ok">방금 발행</Badge>}
                          {cur !== undefined && (cur === e.checksum ? <Badge tone="info">최신 산출물과 동일</Badge> : <Badge tone="warn">산출물 변경됨 — 재발행하면 새 버전</Badge>)}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
