// STEP 1 — 데이터셋 조합 추출: 원천 업로드·스트림 등록, 후보 선택, 규칙 기반 추천 조합 채택
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { AssetProfileModal, StreamModal, UploadZone } from "../components/assets";
import type { Asset, ComboSuggestion, Dataset, ProcessDetail } from "../types";
import { Badge, Banner, Button, Card, ConfirmButton, Empty, KeyPill, Meter, QueryState, cx, useToast } from "../ui";
import { useStudio } from "./context";
import { ReadOnlyNote, StepHeader } from "./shared";

type KindFilter = "all" | "dataset" | "stream";
type ViewMode = "card" | "list";

const KIND_FILTERS: { key: KindFilter; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "dataset", label: "파일" },
  { key: "stream", label: "스트림" },
];

const formLabel = (a: Asset) => (a.kind === "stream" ? "실시간 스트림" : a.data_form || "파일");
const sameSet = (a: number[], b: number[]) => a.length === b.length && a.every((x) => b.includes(x));
const selectedAssetIds = (d: ProcessDetail) => d.datasets.filter((x) => x.selected).map((x) => x.asset.id);

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

export function Step1() {
  const { pid, detail, combo, reference, editable, go, refresh } = useStudio();
  const toast = useToast();
  const goAfter = useGoAfter();

  const assetsQ = useQuery({ queryKey: ["assets"], queryFn: () => api.assets() });
  const suggQ = useQuery({ queryKey: ["process", pid, "suggestions"], queryFn: () => api.suggestions(pid) });

  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");
  const [view, setView] = useState<ViewMode>("card");
  const [profileId, setProfileId] = useState<number | null>(null);
  const [streamOpen, setStreamOpen] = useState(false);
  const [armedId, setArmedId] = useState<number | null>(null);
  const [selBusy, setSelBusy] = useState(false);
  const [comboBusy, setComboBusy] = useState<string | null>(null);

  /** 이 프로세스의 후보로 선택된 데이터셋 (원천 id 기준) */
  const byAsset = useMemo(() => new Map<number, Dataset>(detail.datasets.filter((d) => d.selected).map((d) => [d.asset.id, d])), [detail.datasets]);
  const comboIds = useMemo(() => combo.map((d) => d.id), [combo]);
  const comboGuard = !!detail.process.combo_confirmed_at && combo.length > 0;

  // ── 후보 선택. 요청은 한 줄로 세워 보내고, 항상 서버가 마지막으로 돌려준 선택 목록에서 계산한다
  //    (업로드가 끝나는 시점과 체크박스 조작이 겹쳐도 서로의 변경을 덮어쓰지 않는다).
  const idsRef = useRef<number[]>(selectedAssetIds(detail));
  useEffect(() => {
    idsRef.current = selectedAssetIds(detail);
  }, [detail]);
  const queue = useRef<Promise<void>>(Promise.resolve());
  const pending = useRef(0);

  const changeSelection = (compute: (current: number[]) => number[], okText: string) => {
    if (!editable) return;
    pending.current += 1;
    setSelBusy(true);
    queue.current = queue.current.then(async () => {
      try {
        const current = idsRef.current;
        const next = Array.from(new Set(compute(current)));
        if (sameSet(current, next)) return;
        const d = await api.setSelection(pid, next);
        idsRef.current = selectedAssetIds(d);
        await refresh();
        const removed = d.removed_from_combo ?? [];
        if (removed.length > 0) toast(`후보 해제로 조합에서도 제외했습니다 — ${removed.join(", ")}`);
        else toast.ok(okText);
      } catch (e) {
        toast.error(e);
        void refresh();
      } finally {
        pending.current -= 1;
        if (pending.current === 0) setSelBusy(false);
      }
    });
  };

  const addAssets = (created: Asset[]) => {
    if (created.length === 0) return;
    const ids = created.map((a) => a.id);
    changeSelection((cur) => [...cur, ...ids], `이 프로세스 후보에 추가 — ${created.map((a) => a.name).join(", ")}`);
  };

  const toggle = (a: Asset) => {
    const ds = byAsset.get(a.id);
    if (!ds) {
      changeSelection((cur) => [...cur, a.id], `후보 선택 — ${a.name}`);
      return;
    }
    // 조합에 편입된 후보는 해제하면 STEP 3~5 입력이 함께 지워지므로 한 번 더 확인한다
    if (ds.in_combo && armedId !== a.id) {
      setArmedId(a.id);
      return;
    }
    setArmedId(null);
    changeSelection((cur) => cur.filter((id) => id !== a.id), `후보 해제 — ${a.name}`);
  };

  // ── 목록 필터
  const assets = useMemo(() => assetsQ.data ?? [], [assetsQ.data]);
  const counts: Record<KindFilter, number> = useMemo(
    () => ({ all: assets.length, dataset: assets.filter((a) => a.kind === "dataset").length, stream: assets.filter((a) => a.kind === "stream").length }),
    [assets],
  );
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return assets.filter((a) => (kind === "all" || a.kind === kind) && (!q || a.name.toLowerCase().includes(q)));
  }, [assets, query, kind]);
  const filtered = visible.length !== assets.length;
  const visibleSelected = visible.filter((a) => byAsset.has(a.id));
  const visibleUnselected = visible.length - visibleSelected.length;
  const visibleInCombo = visibleSelected.some((a) => byAsset.get(a.id)?.in_combo);

  const selectVisible = () => {
    const ids = visible.map((a) => a.id);
    changeSelection((cur) => [...cur, ...ids], `후보 ${visibleUnselected}건 선택`);
  };
  const clearVisible = () => {
    const ids = new Set(visible.map((a) => a.id));
    setArmedId(null);
    changeSelection((cur) => cur.filter((id) => !ids.has(id)), `후보 ${visibleSelected.length}건 해제`);
  };

  // ── 조합 설정 → STEP 2
  const applyCombo = async (key: string, ids: number[], source: "manual" | "suggestion") => {
    if (sameSet(ids, comboIds)) {
      go(2); // 이미 같은 구성 — 순서와 출처를 건드리지 않고 이동만 한다
      return;
    }
    setComboBusy(key);
    try {
      const d = await api.setCombo(pid, ids, source);
      await refresh();
      toast.ok(`조합 설정 — ${ids.length}건 · STEP 2 에서 조정하고 확정하세요`);
      goAfter(2, d);
    } catch (e) {
      toast.error(e);
    } finally {
      setComboBusy(null);
    }
  };

  /** 선택한 후보 전체: 이미 조합에 있는 것은 지금 순서를 지키고, 나머지를 뒤에 붙인다 */
  const allSelectedIds = useMemo(() => {
    const rest = detail.datasets.filter((d) => d.selected && !d.in_combo).map((d) => d.id);
    return [...combo.filter((d) => d.selected).map((d) => d.id), ...rest];
  }, [detail.datasets, combo]);
  const allIsCurrent = allSelectedIds.length > 0 && sameSet(allSelectedIds, comboIds);
  const mutating = selBusy || comboBusy !== null;

  const itemProps = (a: Asset): ItemProps => ({
    asset: a,
    dataset: byAsset.get(a.id),
    armed: armedId === a.id,
    disabled: !editable || mutating,
    onToggle: () => toggle(a),
    onCancel: () => setArmedId(null),
    onProfile: () => setProfileId(a.id),
  });

  const keyLegend = Object.entries(reference.key_labels).sort(([a], [b]) => a.localeCompare(b, "en", { numeric: true }));

  return (
    <div className="col gap-12">
      <div>
        <StepHeader n={1} title="데이터셋 조합 추출" sub="파일을 올리면 컬럼을 실제로 프로파일링하고, 연계키 후보를 기준으로 조합을 추천합니다." />
        <ReadOnlyNote />
      </div>

      <div className="grid side">
        <UploadZone onUploaded={addAssets} disabled={!editable} />
        <Card title="스트림 등록" right={assetsQ.data ? <span className="small muted">등록된 스트림 {counts.stream}건</span> : undefined}>
          <p className="small dim">
            CCTV 영상 · 센서처럼 계속 흘러드는 데이터는 본체를 올리지 않습니다. 토픽 이름과 스키마, 시간 규격(시간 해상도 · event-time 컬럼)만 등록하면 필드 이름에서 연계키 후보를 계산합니다.
          </p>
          <p className="tiny muted mt-8">등록한 스트림은 dcat:DataService 로 다루며, 이 프로세스의 후보에 바로 추가됩니다.</p>
          <div className="mt-12">
            <Button variant="outline" disabled={!editable} onClick={() => setStreamOpen(true)}>
              ＋ 스트림 등록
            </Button>
          </div>
        </Card>
      </div>

      {/* ── 후보 원천 */}
      <section>
        <div className="section-title">
          후보 원천
          <span className="muted small">
            선택 {byAsset.size} / {assets.length}건
          </span>
          {selBusy && <span className="spinner" aria-label="선택을 저장하는 중" />}
        </div>
        <div className="row between wrap mb-8">
          <div className="row wrap">
            <input
              className="input"
              type="search"
              style={{ width: 220 }}
              placeholder="원천 이름 검색…"
              aria-label="원천 이름 검색"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="row wrap gap-4" role="group" aria-label="종류 필터">
              {KIND_FILTERS.map((f) => (
                <button key={f.key} className={cx("chip", kind === f.key && "on")} aria-pressed={kind === f.key} onClick={() => setKind(f.key)}>
                  {f.label} <span className="score">{counts[f.key]}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="row wrap">
            <Button
              size="sm"
              disabled={!editable || mutating || visibleUnselected === 0}
              title={filtered ? `검색 · 필터 결과 ${visible.length}건에 적용` : undefined}
              onClick={selectVisible}
            >
              전체 선택
            </Button>
            {visibleInCombo ? (
              <ConfirmButton size="sm" confirmLabel="조합 편입분도 해제 확인" disabled={!editable || mutating} onConfirm={clearVisible}>
                선택 해제
              </ConfirmButton>
            ) : (
              <Button
                size="sm"
                disabled={!editable || mutating || visibleSelected.length === 0}
                title={filtered ? `검색 · 필터 결과 ${visible.length}건에 적용` : undefined}
                onClick={clearVisible}
              >
                선택 해제
              </Button>
            )}
            <div className="row gap-4" role="group" aria-label="보기 방식">
              <button className={cx("chip", view === "card" && "on")} aria-pressed={view === "card"} onClick={() => setView("card")}>
                카드
              </button>
              <button className={cx("chip", view === "list" && "on")} aria-pressed={view === "list"} onClick={() => setView("list")}>
                목록
              </button>
            </div>
          </div>
        </div>

        <QueryState q={assetsQ}>
          {assets.length === 0 ? (
            <Empty>등록된 원천이 없습니다 — 파일을 올리거나 스트림을 등록하면 프로파일 결과와 함께 여기에 나타납니다</Empty>
          ) : visible.length === 0 ? (
            <Empty>검색 · 필터 조건에 맞는 원천이 없습니다</Empty>
          ) : view === "card" ? (
            <div className="grid c3">
              {visible.map((a) => (
                <AssetCard key={a.id} {...itemProps(a)} />
              ))}
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>선택</th>
                    <th>원천</th>
                    <th>종류</th>
                    <th className="num">크기</th>
                    <th>프로파일</th>
                    <th>연계키 후보</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visible.map((a) => (
                    <AssetRow key={a.id} {...itemProps(a)} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </QueryState>
        {filtered && assets.length > 0 && (
          <div className="tiny muted mt-8">
            {assets.length}건 중 {visible.length}건 표시 — 전체 선택 · 선택 해제는 보이는 항목에만 적용됩니다
          </div>
        )}
      </section>

      {/* ── 규칙 기반 추천 조합 */}
      <section>
        <div className="section-title">
          규칙 기반 추천 조합
          {suggQ.data && <span className="muted small">{suggQ.data.method}</span>}
        </div>
        <QueryState q={suggQ}>
          {suggQ.data &&
            (suggQ.data.suggestions.length === 0 ? (
              <Empty>
                {suggQ.data.selected < 2
                  ? `후보를 2건 이상 선택하면 연계키 후보를 비교해 조합을 추천합니다 (현재 선택 ${suggQ.data.selected}건)`
                  : "연계키를 공유하는 후보가 없습니다 — STEP 2 에서 직접 조합할 수 있습니다"}
              </Empty>
            ) : (
              <div className="col gap-12">
                {suggQ.data.suggestions.map((s) => {
                  const key = `s-${s.dataset_ids.join("-")}`;
                  return (
                    <SuggestionCard
                      key={key}
                      suggestion={s}
                      current={sameSet(s.dataset_ids, comboIds)}
                      guard={comboGuard}
                      disabled={!editable || mutating}
                      busy={comboBusy === key}
                      onAdopt={() => applyCombo(key, s.dataset_ids, "suggestion")}
                    />
                  );
                })}
              </div>
            ))}
        </QueryState>

        <div className="card tight row between wrap mt-12">
          <div className="grow small">
            <b>추천을 쓰지 않고 직접 구성</b>
            <span className="muted">
              {" "}
              — 선택한 후보 {allSelectedIds.length}건을 그대로 조합으로 가져갑니다. 순서와 구성원은 STEP 2 에서 조정합니다.
            </span>
          </div>
          {allIsCurrent ? (
            <Button variant="outline" onClick={() => go(2)}>
              현재 조합과 같습니다 — STEP 2 로 이동 →
            </Button>
          ) : comboGuard ? (
            <ConfirmButton
              variant="outline"
              confirmLabel="확정된 조합을 바꿉니다 — 한 번 더"
              disabled={!editable || mutating || allSelectedIds.length === 0}
              busy={comboBusy === "all"}
              onConfirm={() => applyCombo("all", allSelectedIds, "manual")}
            >
              선택한 후보 전체를 조합으로 → STEP 2
            </ConfirmButton>
          ) : (
            <Button
              variant="outline"
              disabled={!editable || mutating || allSelectedIds.length === 0}
              busy={comboBusy === "all"}
              onClick={() => applyCombo("all", allSelectedIds, "manual")}
            >
              선택한 후보 전체를 조합으로 → STEP 2
            </Button>
          )}
        </div>

        <div className="tiny muted mt-8">
          K = 연계키 {keyLegend.length}종 (
          {keyLegend.map(([code, label], i) => (
            <span key={code}>
              {i > 0 && " · "}
              <b>{code}</b> {label}
            </span>
          ))}
          )
        </div>
      </section>

      {streamOpen && <StreamModal onClose={() => setStreamOpen(false)} onCreated={(a) => addAssets([a])} />}
      {profileId != null && <AssetProfileModal assetId={profileId} onClose={() => setProfileId(null)} />}
    </div>
  );
}

// ───────────── 원천 1건 (카드 · 표 행)
interface ItemProps {
  asset: Asset;
  /** 이 프로세스의 후보로 선택돼 있으면 그 데이터셋 */
  dataset: Dataset | undefined;
  /** 조합 편입 후보의 해제 확인 대기 중 */
  armed: boolean;
  disabled: boolean;
  onToggle: () => void;
  onCancel: () => void;
  onProfile: () => void;
}

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

function StatusBadges({ asset: a, dataset }: { asset: Asset; dataset: Dataset | undefined }) {
  return (
    <>
      {a.profile_status === "error" && (
        <Badge tone="err" title={a.error || undefined}>
          프로파일 오류
        </Badge>
      )}
      {a.warnings.length > 0 && (
        <Badge tone="warn" title={a.warnings.join("\n")}>
          경고 {a.warnings.length}
        </Badge>
      )}
      {dataset?.in_combo && <Badge tone="ok">조합 편입</Badge>}
    </>
  );
}

/** 조합에 편입된 후보를 해제하기 전 확인 */
function DeselectGuard({ disabled, onToggle, onCancel }: Pick<ItemProps, "disabled" | "onToggle" | "onCancel">) {
  return (
    <Banner
      tone="warn"
      right={
        <div className="row gap-4">
          <Button size="sm" variant="danger" disabled={disabled} onClick={onToggle}>
            후보 해제
          </Button>
          <Button size="sm" onClick={onCancel}>
            취소
          </Button>
        </div>
      }
    >
      조합에 편입된 후보입니다 — 해제하면 조합에서 빠지고 STEP 3–5 에서 입력한 메타데이터 · 분류 · 관계가 삭제됩니다.
    </Banner>
  );
}

function AssetCard(p: ItemProps) {
  const { asset: a, dataset } = p;
  return (
    <div className={cx("card tight col gap-4", dataset && "selected")}>
      <div className="row wrap gap-4">
        <Badge tone={a.kind === "stream" ? "purple" : "info"}>{formLabel(a)}</Badge>
        {a.size_label && <span className="tiny muted">{a.size_label}</span>}
        <StatusBadges asset={a} dataset={dataset} />
      </div>
      <div className="bold ellipsis" title={a.name}>
        {a.name}
      </div>
      <div className="small muted">{a.profile_summary}</div>
      <div className="row wrap gap-4">
        <KeyPills codes={a.keys} />
      </div>
      {p.armed ? (
        <DeselectGuard disabled={p.disabled} onToggle={p.onToggle} onCancel={p.onCancel} />
      ) : (
        <div className="row between wrap mt-4">
          <label className="check">
            <input type="checkbox" checked={!!dataset} disabled={p.disabled} onChange={p.onToggle} />이 프로세스 후보로 선택
          </label>
          <Button size="sm" onClick={p.onProfile}>
            프로파일 보기
          </Button>
        </div>
      )}
    </div>
  );
}

function AssetRow(p: ItemProps) {
  const { asset: a, dataset } = p;
  return (
    <tr>
      <td>
        <input type="checkbox" aria-label={`${a.name} — 이 프로세스 후보로 선택`} checked={!!dataset} disabled={p.disabled} onChange={p.onToggle} />
      </td>
      <td>
        <div className="row wrap gap-4">
          <span className="bold">{a.name}</span>
          <StatusBadges asset={a} dataset={dataset} />
        </div>
        {p.armed && (
          <div className="mt-4">
            <DeselectGuard disabled={p.disabled} onToggle={p.onToggle} onCancel={p.onCancel} />
          </div>
        )}
      </td>
      <td>
        <Badge tone={a.kind === "stream" ? "purple" : "info"}>{formLabel(a)}</Badge>
      </td>
      <td className="num">{a.size_label || "—"}</td>
      <td className="muted">{a.profile_summary}</td>
      <td>
        <div className="row wrap gap-4">
          <KeyPills codes={a.keys} />
        </div>
      </td>
      <td className="nowrap right">
        <Button size="sm" onClick={p.onProfile}>
          프로파일 보기
        </Button>
      </td>
    </tr>
  );
}

// ───────────── 추천 조합 1건
function SuggestionCard(props: { suggestion: ComboSuggestion; current: boolean; guard: boolean; disabled: boolean; busy: boolean; onAdopt: () => void }) {
  const { suggestion: s, current } = props;
  return (
    <div className={cx("card", current && "selected")}>
      <div className="row between top wrap gap-16">
        <div className="grow col gap-4" style={{ minWidth: 280 }}>
          <div className="row wrap gap-4">
            <span className="bold">{s.names.join(" · ")}</span>
            <span className="small muted">{s.names.length}건</span>
            {current && <Badge tone="ok">✓ 현재 조합</Badge>}
          </div>
          <div className="row wrap gap-4">
            <span className="small dim">공유 연계키</span>
            {s.shared_keys.map((k) => (
              <KeyPill key={k.code} code={k.code} label={k.label} />
            ))}
          </div>
          <div className="small bold dim mt-4">근거</div>
          <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
            {s.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <div className="tiny muted">{s.method}</div>
        </div>
        <div className="col" style={{ width: 220 }}>
          <div>
            <div className="row between small">
              <span className="dim">신뢰도</span>
              <span className="bold">{s.confidence}%</span>
            </div>
            <div className="mt-4">
              <Meter value={s.confidence} />
            </div>
          </div>
          {current ? (
            <Button variant="outline" block onClick={props.onAdopt}>
              STEP 2 로 이동 →
            </Button>
          ) : props.guard ? (
            <ConfirmButton variant="primary" confirmLabel="확정된 조합을 바꿉니다 — 한 번 더" disabled={props.disabled} busy={props.busy} onConfirm={props.onAdopt}>
              이 조합 채택 → STEP 2
            </ConfirmButton>
          ) : (
            <Button variant="primary" block disabled={props.disabled} busy={props.busy} onClick={props.onAdopt}>
              이 조합 채택 → STEP 2
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
