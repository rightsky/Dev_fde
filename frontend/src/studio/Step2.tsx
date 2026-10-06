// STEP 2 — 조합 조정 · 확정: 후보에서 조합을 구성하고 제목·설명을 입력해 확정한다
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { ComboSuggestion, ComboWarning, Dataset, ProcessDetail } from "../types";
import { Badge, Banner, Button, Card, ConfirmButton, Empty, Field, KeyPill, QueryState, cx, fmtDateTime, useToast } from "../ui";
import { useStudio } from "./context";
import { ReadOnlyNote, StepHeader } from "./shared";

type ComboSource = "manual" | "suggestion";

const sameSet = (a: number[], b: number[]) => a.length === b.length && a.every((x) => b.includes(x));
const comboIdsOf = (d: ProcessDetail) =>
  d.datasets
    .filter((x) => x.in_combo)
    .sort((a, b) => a.position - b.position)
    .map((x) => x.id);
const kindLabel = (d: Dataset) => (d.kind === "stream" ? "실시간 스트림" : d.asset.data_form || "파일");

/**
 * 변경 요청으로 열린 단계로 이동한다.
 * go() 는 렌더 시점의 게이트를 보므로, 응답으로 열림을 확인한 뒤 화면의 프로세스 상태가 따라오면 이동한다.
 */
function useGoAfter() {
  const { go, gate } = useStudio();
  const toast = useToast();
  const [target, setTarget] = useState<number | null>(null);
  useEffect(() => {
    if (target == null || !gate(target)?.can_enter) return;
    setTarget(null);
    go(target);
  }, [target, go, gate]);
  return useCallback(
    (step: number, fresh: ProcessDetail) => {
      const g = fresh.state.gates.find((x) => x.step === step);
      if (g && !g.can_enter) toast(`🔒 STEP ${step} 잠김 — ${g.reason}`);
      else setTarget(step);
    },
    [toast],
  );
}

export function Step2() {
  const { pid, detail, combo, editable, go, refresh } = useStudio();
  const toast = useToast();

  const warnQ = useQuery({ queryKey: ["process", pid, "comboWarnings"], queryFn: () => api.comboWarnings(pid) });
  const suggQ = useQuery({ queryKey: ["process", pid, "suggestions"], queryFn: () => api.suggestions(pid) });

  /** 진행 중인 조합 변경의 식별자 (버튼별 진행 표시). 하나가 진행 중이면 다른 조합 컨트롤은 잠근다. */
  const [busy, setBusy] = useState<string | null>(null);

  const candidates = detail.datasets.filter((d) => d.selected && !d.in_combo);
  const selectedCount = detail.datasets.filter((d) => d.selected).length;
  const comboIds = combo.map((d) => d.id);
  const locked = !editable || busy !== null;
  /** 확정된 뒤에는 하류 작업(메타데이터·분류·관계)이 있을 수 있으므로 구성원을 빼는 동작을 한 번 더 확인한다 */
  const guard = !!detail.process.combo_confirmed_at && combo.length > 0;

  // 조합 변경은 서버가 마지막으로 돌려준 순서에서 계산한다 (화면 갱신 직전의 연속 클릭에도 어긋나지 않게)
  const comboRef = useRef<number[]>(comboIdsOf(detail));
  useEffect(() => {
    comboRef.current = comboIdsOf(detail);
  }, [detail]);

  const changeCombo = async (key: string, compute: (current: number[]) => number[], source: ComboSource, okText: string) => {
    if (!editable || busy !== null) return;
    setBusy(key);
    try {
      const d = await api.setCombo(pid, compute(comboRef.current), source);
      comboRef.current = comboIdsOf(d);
      await refresh();
      toast.ok(okText);
    } catch (e) {
      toast.error(e);
      void refresh();
    } finally {
      setBusy(null);
    }
  };

  const add = (d: Dataset) => changeCombo(`add-${d.id}`, (cur) => (cur.includes(d.id) ? cur : [...cur, d.id]), "manual", `조합에 추가 — ${d.title}`);
  const remove = (d: Dataset) =>
    changeCombo(
      `remove-${d.id}`,
      (cur) => cur.filter((id) => id !== d.id),
      "manual",
      `조합에서 제거 — ${d.title}`,
    );
  const move = (d: Dataset, delta: -1 | 1) =>
    changeCombo(
      `move-${d.id}`,
      (cur) => {
        const i = cur.indexOf(d.id);
        const j = i + delta;
        if (i < 0 || j < 0 || j >= cur.length) return cur;
        const next = [...cur];
        [next[i], next[j]] = [next[j], next[i]];
        return next;
      },
      "manual",
      `순서 변경 — ${d.title}`,
    );
  const replaceWith = (key: string, s: ComboSuggestion) => changeCombo(key, () => s.dataset_ids, "suggestion", `조합 교체 — ${s.names.length}건`);

  const warnings = warnQ.data?.warnings ?? [];
  const errorCount = warnings.filter((w) => w.level === "error").length;

  return (
    <div className="col gap-12">
      <div>
        <StepHeader
          n={2}
          title="조합 조정 · 확정"
          sub="후보에서 데이터셋을 골라 작업 조합을 구성하고, 제목과 설명을 입력해 확정합니다. 확정하면 prov:Activity 가 기록됩니다."
        />
        <ReadOnlyNote />
      </div>

      <Card
        title={
          <>
            보정 경고 (규칙엔진)
            {errorCount > 0 && <Badge tone="err">오류 {errorCount}</Badge>}
            {warnings.length - errorCount > 0 && <Badge tone="warn">경고 {warnings.length - errorCount}</Badge>}
          </>
        }
      >
        <QueryState q={warnQ}>
          <WarningList warnings={warnings} comboEmpty={combo.length === 0} />
        </QueryState>
      </Card>

      <div className="grid c3" style={{ alignItems: "start" }}>
        {/* ── 1. 후보 */}
        <Card
          title={
            <>
              후보 <span className="muted small">{candidates.length}건</span>
            </>
          }
          right={
            <button className="link-btn small" onClick={() => go(1)}>
              STEP 1 에서 후보 추가
            </button>
          }
        >
          {candidates.length === 0 ? (
            <Empty>{selectedCount === 0 ? "선택한 후보가 없습니다 — STEP 1 에서 후보를 선택하세요" : "선택한 후보가 모두 조합에 들어 있습니다"}</Empty>
          ) : (
            <div className="col">
              {candidates.map((d) => (
                <div key={d.id} className="card tight flat">
                  <div className="row between top">
                    <div className="grow">
                      <div className="bold ellipsis" title={d.title}>
                        {d.title}
                      </div>
                      <div className="tiny muted">
                        {kindLabel(d)} · {d.asset.profile_summary}
                      </div>
                    </div>
                    <Button size="sm" variant="outline" title="내 작업 조합에 추가" disabled={locked} busy={busy === `add-${d.id}`} onClick={() => add(d)}>
                      내 작업으로 →
                    </Button>
                  </div>
                  <div className="row wrap gap-4 mt-4">
                    <KeyPills codes={d.asset.keys} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* ── 2. 규칙 기반 추천 조합 */}
        <Card title="규칙 기반 추천 조합">
          <QueryState q={suggQ}>
            {suggQ.data && (
              <>
                <div className="tiny muted mb-8">{suggQ.data.method}</div>
                {suggQ.data.suggestions.length === 0 ? (
                  <Empty>
                    {suggQ.data.selected < 2
                      ? `후보가 2건 이상이어야 추천을 계산합니다 (현재 ${suggQ.data.selected}건)`
                      : "연계키를 공유하는 후보가 없습니다 — 왼쪽 후보에서 직접 구성하세요"}
                  </Empty>
                ) : (
                  <div className="col">
                    {suggQ.data.suggestions.map((s) => {
                      const key = `sugg-${s.dataset_ids.join("-")}`;
                      return (
                        <SuggestionItem
                          key={key}
                          suggestion={s}
                          current={sameSet(s.dataset_ids, comboIds)}
                          guard={guard}
                          disabled={locked}
                          busy={busy === key}
                          onApply={() => replaceWith(key, s)}
                        />
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </QueryState>
        </Card>

        {/* ── 3. 내 작업 조합 + 확정 */}
        <div className="col gap-12">
          <Card
            className="selected"
            title={
              <>
                내 작업 조합 <span className="muted small">{combo.length}건</span>
              </>
            }
            right={
              combo.length > 0 && detail.process.combo_source ? (
                <Badge tone={detail.process.combo_source === "suggestion" ? "info" : "muted"}>
                  {detail.process.combo_source === "suggestion" ? "규칙 기반 추천 채택" : "작업자 구성"}
                </Badge>
              ) : undefined
            }
          >
            {combo.length === 0 ? (
              <Empty>조합이 비어 있습니다 — 후보의 「내 작업으로 →」 또는 추천 조합의 「조합 교체」로 구성하세요</Empty>
            ) : (
              <ol className="col" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {combo.map((d, i) => (
                  <li key={d.id} className="card tight flat row top">
                    <Badge tone="dark">{i + 1}</Badge>
                    <div className="grow">
                      <div className="bold ellipsis" title={d.title}>
                        {d.title}
                      </div>
                      <div className="row wrap gap-4 mt-4">
                        <Badge tone={d.kind === "stream" ? "purple" : "info"}>{kindLabel(d)}</Badge>
                        <KeyPills codes={d.asset.keys} />
                      </div>
                    </div>
                    <div className="row gap-4">
                      <button
                        className="btn sm"
                        aria-label={`${d.title} 위로 이동`}
                        title="위로 이동"
                        disabled={locked || i === 0}
                        onClick={() => move(d, -1)}
                      >
                        ▲
                      </button>
                      <button
                        className="btn sm"
                        aria-label={`${d.title} 아래로 이동`}
                        title="아래로 이동"
                        disabled={locked || i === combo.length - 1}
                        onClick={() => move(d, 1)}
                      >
                        ▼
                      </button>
                      {guard ? (
                        <ConfirmButton size="sm" confirmLabel="제거 확인" disabled={locked} busy={busy === `remove-${d.id}`} onConfirm={() => remove(d)}>
                          제거
                        </ConfirmButton>
                      ) : (
                        <Button size="sm" disabled={locked} busy={busy === `remove-${d.id}`} onClick={() => remove(d)}>
                          제거
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
            {guard && <div className="tiny muted mt-8">확정된 조합입니다 — 구성원을 빼면 그 데이터셋이 걸린 STEP 5 관계도 함께 지워집니다.</div>}
          </Card>

          <ConfirmCard key={pid} draft={warnQ.data?.draft} errorCount={errorCount} comboBusy={busy !== null} />
        </div>
      </div>
    </div>
  );
}

// ───────────── 연계키 알약
function KeyPills({ codes }: { codes: string[] }) {
  const { reference } = useStudio();
  if (codes.length === 0) return <span className="tiny muted">연계키 후보 없음</span>;
  return (
    <>
      {codes.map((c) => (
        <KeyPill key={c} code={c} label={reference.key_labels[c]} />
      ))}
    </>
  );
}

// ───────────── 보정 경고 목록 (오류 → 경고 순)
function WarningList({ warnings, comboEmpty }: { warnings: ComboWarning[]; comboEmpty: boolean }) {
  if (warnings.length === 0) {
    return comboEmpty ? (
      <div className="small muted">경고 없음 — 조합을 구성하면 프로파일 오류 · 표기 혼재 · 연계키 누락을 여기에 표시합니다</div>
    ) : (
      <div className="small t-ok bold">✓ 경고 없음</div>
    );
  }
  const ordered = [...warnings.filter((w) => w.level === "error"), ...warnings.filter((w) => w.level !== "error")];
  return (
    <div className="col gap-4" style={{ maxHeight: 240, overflowY: "auto" }}>
      {ordered.map((w, i) => (
        <Banner key={`${w.dataset_id}-${w.code}-${i}`} tone={w.level === "error" ? "err" : "warn"}>
          <b>{w.name}</b> — {w.message}
        </Banner>
      ))}
    </div>
  );
}

// ───────────── 추천 조합 1건 (간략)
function SuggestionItem(props: { suggestion: ComboSuggestion; current: boolean; guard: boolean; disabled: boolean; busy: boolean; onApply: () => void }) {
  const { suggestion: s, current } = props;
  return (
    <div className={cx("card tight flat col gap-4", current && "selected")}>
      <div className="row between top">
        <div className="bold small grow">{s.names.join(" · ")}</div>
        {current && <Badge tone="ok">✓ 현재 조합</Badge>}
      </div>
      <div className="row wrap gap-4">
        {s.shared_keys.map((k) => (
          <KeyPill key={k.code} code={k.code} label={k.label} />
        ))}
        <span className="small dim nowrap">
          신뢰도 <b>{s.confidence}%</b>
        </span>
      </div>
      <ul className="tiny dim" style={{ margin: 0, paddingLeft: 16 }}>
        {s.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        {props.guard && !current ? (
          <ConfirmButton size="sm" variant="outline" confirmLabel="확정된 조합을 바꿉니다 — 한 번 더" disabled={props.disabled} busy={props.busy} onConfirm={props.onApply}>
            조합 교체
          </ConfirmButton>
        ) : (
          <Button
            size="sm"
            variant="outline"
            title={current ? "현재 조합과 구성이 같습니다" : "내 작업 조합을 이 추천으로 바꿉니다"}
            disabled={props.disabled || current}
            busy={props.busy}
            onClick={props.onApply}
          >
            조합 교체
          </Button>
        )}
      </div>
    </div>
  );
}

// ───────────── 조합 확정 카드 (프로세스가 바뀌면 key 로 다시 만들어 입력값을 맞춘다)
function ConfirmCard({ draft, errorCount, comboBusy }: { draft: { title: string; description: string } | undefined; errorCount: number; comboBusy: boolean }) {
  const { pid, detail, combo, editable, go, refresh, params } = useStudio();
  const toast = useToast();
  const goAfter = useGoAfter();
  const p = detail.process;
  const savedTitle = p.combo_title ?? "";
  const savedDescription = p.combo_description ?? "";

  const [title, setTitle] = useState(savedTitle);
  const [description, setDescription] = useState(savedDescription);
  const [drafted, setDrafted] = useState(false);
  const [busy, setBusy] = useState<"confirm" | "unconfirm" | null>(null);

  // 검증 위반(조합 식별) 수정 경로로 들어오면 이 카드를 강조한다
  const cardRef = useRef<HTMLDivElement>(null);
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    if (params.focus !== "combo") return;
    setFlash(true);
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    const t = setTimeout(() => setFlash(false), 2400);
    return () => clearTimeout(t);
  }, [params.focus]);

  const confirmed = !!p.combo_confirmed_at;
  const dirty = title.trim() !== savedTitle || description.trim() !== savedDescription;
  const settled = confirmed && !dirty && combo.length > 0;
  const locked = !editable || busy !== null || comboBusy;
  const blockReason =
    combo.length === 0
      ? "조합에 데이터셋을 1건 이상 넣어야 확정할 수 있습니다"
      : errorCount > 0
        ? "읽을 수 없는 파일이 조합에 있습니다 — 위 보정 경고의 오류 항목을 조합에서 제거하세요"
        : !title.trim()
          ? "제목은 필수입니다"
          : null;

  const applyDraft = () => {
    if (!draft) return;
    setTitle(draft.title);
    setDescription(draft.description);
    setDrafted(true);
  };
  const revert = () => {
    setTitle(savedTitle);
    setDescription(savedDescription);
    setDrafted(false);
  };

  const confirm = async () => {
    setBusy("confirm");
    try {
      const d = await api.confirmCombo(pid, title.trim(), description.trim() || undefined);
      setTitle(d.process.combo_title ?? "");
      setDescription(d.process.combo_description ?? "");
      setDrafted(false);
      await refresh();
      toast.ok(`조합 확정 — 「${d.process.combo_title ?? title.trim()}」 ${d.process.dataset_count}건 · prov:Activity 기록`);
      goAfter(3, d);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };
  const unconfirm = async () => {
    setBusy("unconfirm");
    try {
      await api.unconfirmCombo(pid);
      await refresh();
      toast.ok("조합 확정을 해제했습니다 — 다시 확정할 때까지 STEP 3 이후가 잠깁니다");
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div ref={cardRef} className={cx("card", flash && "flash")}>
      <div className="card-head">
        <div className="card-title">
          조합 확정 <Badge>dcterms:title · description</Badge>
        </div>
        <Button
          size="sm"
          title="조합 구성원 · 연계키 · 프로파일 실측값으로 만든 템플릿 초안을 채웁니다 (입력한 내용을 덮어씁니다)"
          disabled={locked || !draft?.title}
          onClick={applyDraft}
        >
          규칙 기반 초안
        </Button>
      </div>
      <p className="small muted mb-8">확정하면 이 조합이 하나의 작업 단위가 되어 STEP 3 카탈로그 작성으로 이어집니다.</p>
      <div className="col gap-12">
        <Field
          label={
            <>
              제목 <span className="mono muted">dcterms:title</span> <Badge tone="err">필수</Badge>
            </>
          }
        >
          <input
            className="input"
            value={title}
            maxLength={300}
            disabled={!editable}
            placeholder="예: 도로링크 · 사고 결합 데이터셋"
            onChange={(e) => {
              setTitle(e.target.value);
              setDrafted(false);
            }}
          />
        </Field>
        <Field
          label={
            <>
              설명 <span className="mono muted">dcterms:description</span>
            </>
          }
          hint={drafted ? "규칙 기반 초안을 채웠습니다 — 내용을 확인하고 고친 뒤 확정하세요" : undefined}
        >
          <textarea
            className="textarea"
            rows={3}
            value={description}
            disabled={!editable}
            placeholder="조합 목적, 포함 데이터셋, 연계키를 한두 문장으로"
            onChange={(e) => {
              setDescription(e.target.value);
              setDrafted(false);
            }}
          />
        </Field>

        {settled ? (
          <>
            <Banner
              tone="ok"
              right={
                <button className="link-btn" disabled={locked} onClick={unconfirm}>
                  {busy === "unconfirm" ? "해제하는 중…" : "확정 해제"}
                </button>
              }
            >
              <b>
                ✓ 「{savedTitle}」 확정 · {fmtDateTime(p.combo_confirmed_at)}
              </b>
            </Banner>
            <Button variant="outline" block onClick={() => go(3)}>
              STEP 3 카탈로그 작성으로 이동 →
            </Button>
          </>
        ) : (
          <>
            {confirmed && dirty && (
              <div className="small t-warn">
                확정된 값과 다릅니다 — 재확정해야 반영됩니다 ·{" "}
                <button className="link-btn" onClick={revert}>
                  확정된 값으로 되돌리기
                </button>
              </div>
            )}
            <Button variant="primary" size="lg" block disabled={locked || blockReason !== null} busy={busy === "confirm"} onClick={confirm}>
              {confirmed ? "재확정" : "조합 확정"} → STEP 3 인계 ({combo.length}건)
            </Button>
            {editable && blockReason && <div className="small muted">{blockReason}</div>}
          </>
        )}

        <div className="tiny muted">
          검증을 실행한 뒤 조합 구성원을 바꾸면 STEP 6–8 의 검증 · 변환 · 진단 결과는 서버가 자동으로 무효 처리합니다. 다시 실행하면 됩니다.
        </div>
        {detail.state.validation.stale && <div className="tiny t-warn">현재 상태: {detail.state.validation.stale}</div>}
      </div>
    </div>
  );
}
