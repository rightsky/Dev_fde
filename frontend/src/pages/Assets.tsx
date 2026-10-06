// 데이터 패브릭 관리 — 업로드한 파일과 등록한 스트림(원천 풀). 스튜디오 STEP 1 이 이 목록을 후보로 쓴다.
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth, useReference } from "../auth";
import { AssetProfileModal, StreamModal, UploadZone } from "../components/assets";
import type { Asset } from "../types";
import { Badge, Banner, Button, ConfirmButton, Empty, KeyPill, QueryState, cx, fmtDateTime, fmtNum, useToast } from "../ui";

type KindFilter = "" | "dataset" | "stream";

const KINDS: { key: KindFilter; label: string }[] = [
  { key: "", label: "전체" },
  { key: "dataset", label: "파일" },
  { key: "stream", label: "스트림" },
];

/** 입력이 멈춘 뒤 ms 가 지나야 값이 바뀐다 (검색어 → 서버 조회 간격 조절) */
function useDebounced<V>(value: V, ms: number): V {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

/** 원천이 바뀌면 그 원천을 품고 있는 프로세스 화면도 다시 불러와야 한다 */
async function refreshAssets(qc: QueryClient) {
  await qc.invalidateQueries({ queryKey: ["assets"] });
  void qc.invalidateQueries({ queryKey: ["process"] });
  void qc.invalidateQueries({ queryKey: ["processes"] });
}

export function AssetsPage() {
  const { canWrite } = useAuth();
  const [text, setText] = useState("");
  const [kind, setKind] = useState<KindFilter>("");
  const [profileId, setProfileId] = useState<number | null>(null);
  const [streamOpen, setStreamOpen] = useState(false);
  const [fresh, setFresh] = useState<number[]>([]);
  const q = useDebounced(text.trim(), 300);

  const list = useQuery({ queryKey: ["assets", { kind, q }], queryFn: () => api.assets({ kind, q }), placeholderData: keepPreviousData });
  // 유형별 건수는 유형 필터와 무관하게 센다. 유형이 "전체"이면 위 조회와 같은 키라 요청은 한 번만 나간다.
  const pool = useQuery({ queryKey: ["assets", { kind: "", q }], queryFn: () => api.assets({ q }), placeholderData: keepPreviousData });

  const counts: Record<KindFilter, number | undefined> = {
    "": pool.data?.length,
    dataset: pool.data?.filter((a) => a.kind === "dataset").length,
    stream: pool.data?.filter((a) => a.kind === "stream").length,
  };
  const filtered = q !== "" || kind !== "";

  /** 새로 등록한 원천이 현재 필터에 가려지지 않게 한다 */
  const reveal = (created: Asset[]) => {
    setFresh(created.map((a) => a.id));
    setText("");
    if (kind && created.some((a) => a.kind !== kind)) setKind("");
  };

  return (
    <div>
      <div className="row between top wrap">
        <div>
          <h1 className="page-title">데이터 패브릭 관리</h1>
          <p className="page-sub">업로드한 파일과 등록한 스트림입니다. 스튜디오의 모든 프로세스가 이 원천을 후보로 씁니다.</p>
        </div>
        <Button variant="outline" disabled={!canWrite} onClick={() => setStreamOpen(true)} title={canWrite ? "실시간 스트림의 스키마와 시간 규격을 등록합니다" : "열람 전용 계정은 등록할 수 없습니다"}>
          ＋ 스트림 등록
        </Button>
      </div>

      {!canWrite && (
        <div className="mb-8">
          <Banner tone="info">열람 전용 계정입니다 — 업로드 · 스트림 등록 · 삭제는 담당자 이상 권한에서 할 수 있습니다.</Banner>
        </div>
      )}
      <UploadZone onUploaded={reveal} disabled={!canWrite} />

      <div className="row between wrap mt-16 mb-8">
        <div className="row wrap">
          <input
            className="input"
            style={{ width: 260 }}
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="원천 이름 검색"
            aria-label="원천 이름 검색"
          />
          {KINDS.map((k) => (
            <button key={k.key} className={cx("chip", kind === k.key && "on")} aria-pressed={kind === k.key} onClick={() => setKind(k.key)}>
              {k.label}
              {counts[k.key] != null && <span className="score">{fmtNum(counts[k.key])}</span>}
            </button>
          ))}
          {list.isFetching && <span className="spinner" aria-label="불러오는 중" />}
        </div>
        {pool.data && (
          <div className="small dim">
            {q ? `「${q}」 검색 결과 ` : "원천 "}
            <b>{fmtNum(counts[""])}건</b> — 파일 {fmtNum(counts.dataset)}건 · 스트림 {fmtNum(counts.stream)}건
          </div>
        )}
      </div>

      <QueryState q={list}>
        {list.data && list.data.length === 0 ? (
          <Empty>
            {filtered ? (
              <>
                조건에 맞는 원천이 없습니다 —{" "}
                <button
                  className="link-btn"
                  onClick={() => {
                    setText("");
                    setKind("");
                  }}
                >
                  필터 지우기
                </button>
              </>
            ) : (
              "등록된 원천이 없습니다 — 위에서 파일을 올리거나 스트림을 등록하세요"
            )}
          </Empty>
        ) : (
          <AssetTable assets={list.data || []} fresh={fresh} canWrite={canWrite} onProfile={setProfileId} />
        )}
      </QueryState>
      {canWrite && list.data && list.data.length > 0 && (
        <p className="tiny muted mt-8">발행 ID 가 발급되었거나 조합에 포함된 원천은 삭제할 수 없습니다. 삭제하면 아직 조합에 넣지 않은 프로세스의 선택 목록에서도 빠집니다.</p>
      )}

      {profileId != null && <AssetProfileModal assetId={profileId} onClose={() => setProfileId(null)} />}
      {streamOpen && <StreamModal onClose={() => setStreamOpen(false)} onCreated={(a) => reveal([a])} />}
    </div>
  );
}

function AssetTable(props: { assets: Asset[]; fresh: number[]; canWrite: boolean; onProfile: (id: number) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [busyId, setBusyId] = useState<number | null>(null);

  const remove = async (a: Asset) => {
    setBusyId(a.id);
    try {
      await api.deleteAsset(a.id);
      await refreshAssets(qc);
      toast.ok(`원천 삭제 — ${a.name}`);
    } catch (e) {
      toast.error(e); // 발행 ID 발급·조합 포함 등 삭제할 수 없는 사유는 서버 문구 그대로 보여 준다
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>이름</th>
            <th>유형</th>
            <th>형식</th>
            <th className="num">크기</th>
            <th>프로파일</th>
            <th>연계키</th>
            <th className="num">경고</th>
            <th>제공기관</th>
            <th>등록 시각</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {props.assets.map((a) => (
            <AssetRow
              key={a.id}
              asset={a}
              fresh={props.fresh.includes(a.id)}
              canWrite={props.canWrite}
              busy={busyId === a.id}
              onProfile={() => props.onProfile(a.id)}
              onDelete={() => remove(a)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AssetRow(props: { asset: Asset; fresh: boolean; canWrite: boolean; busy: boolean; onProfile: () => void; onDelete: () => void }) {
  const { key_labels } = useReference();
  const a = props.asset;
  const isStream = a.kind === "stream";
  const origin = isStream ? a.stream.endpoint_url : a.filename;
  return (
    <tr>
      <td style={{ minWidth: 180 }}>
        <div className="row gap-4 wrap">
          <button className="link-btn" onClick={props.onProfile} title="프로파일 보기">
            {a.name}
          </button>
          {props.fresh && <Badge tone="solid">방금 등록</Badge>}
        </div>
        {origin && <div className="tiny muted mono">{origin}</div>}
        {a.description && <div className="small dim">{a.description}</div>}
      </td>
      <td>
        <Badge tone={isStream ? "purple" : "info"}>{isStream ? "실시간 스트림" : a.data_form || "파일"}</Badge>
      </td>
      <td>
        {a.ext ? (
          <span className="kbd nowrap" title={a.media_type || undefined}>
            .{a.ext}
          </span>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
      <td className="num" title={a.size != null ? `${fmtNum(a.size)} bytes` : undefined}>
        {a.size_label || "—"}
      </td>
      <td style={{ minWidth: 150 }}>
        {a.profile_status === "error" && (
          <>
            <Badge tone="err" title={a.error || undefined}>
              프로파일 실패
            </Badge>{" "}
          </>
        )}
        <span className={cx(a.profile_status === "error" && "t-err")}>{a.profile_summary || "—"}</span>
      </td>
      <td>
        {a.keys.length > 0 ? (
          <div className="row gap-4 wrap nowrap">
            {a.keys.map((code) => (
              <KeyPill key={code} code={code} label={key_labels[code]} />
            ))}
          </div>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
      <td className="num">
        {a.warnings.length > 0 ? (
          <Badge tone="warn" title={a.warnings.join("\n")}>
            {a.warnings.length}건
          </Badge>
        ) : (
          <span className="muted">0</span>
        )}
      </td>
      <td>
        <OrgCell asset={a} canWrite={props.canWrite} />
      </td>
      <td className="nowrap">{fmtDateTime(a.created_at)}</td>
      <td>
        <div className="row gap-4" style={{ justifyContent: "flex-end" }}>
          <Button size="sm" onClick={props.onProfile}>
            프로파일
          </Button>
          {props.canWrite && (
            <ConfirmButton size="sm" busy={props.busy} onConfirm={props.onDelete}>
              삭제
            </ConfirmButton>
          )}
        </div>
      </td>
    </tr>
  );
}

/** 제공기관 표시 + 그 자리에서 바꾸기 (업로드한 파일은 기관 없이 들어오므로 여기서 지정한다) */
function OrgCell({ asset, canWrite }: { asset: Asset; canWrite: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const orgs = useQuery({ queryKey: ["orgs"], queryFn: api.orgs, enabled: editing });
  const current = asset.org?.id ?? null;

  const save = async (value: string) => {
    const org_id = value ? Number(value) : null;
    if (org_id === current) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      const saved = await api.updateAsset(asset.id, { org_id });
      await refreshAssets(qc);
      toast.ok(`제공기관 ${saved.org ? `지정 — ${saved.org.label}` : "지정 해제"} (${saved.name})`);
      setEditing(false);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <div className="row gap-4 nowrap">
        {asset.org ? <span title={asset.org.code}>{asset.org.label}</span> : <span className="muted">미지정</span>}
        {canWrite && (
          <button className="link-btn small" onClick={() => setEditing(true)}>
            변경
          </button>
        )}
      </div>
    );
  }
  // 비활성 기관은 새로 고를 수 없지만, 이미 지정된 기관이면 선택지에 남겨 둔다
  const options = (orgs.data || []).filter((o) => o.active || o.id === current);
  return (
    <div className="row gap-4">
      {orgs.error ? (
        <span className="small t-err">기관 목록을 불러오지 못했습니다</span>
      ) : (
        <select
          className="select"
          style={{ width: 170 }}
          value={current == null ? "" : String(current)}
          disabled={busy || orgs.isLoading}
          onChange={(e) => save(e.target.value)}
          aria-label={`${asset.name} 제공기관`}
          autoFocus
        >
          <option value="">— 미지정 —</option>
          {/* 목록이 오기 전에도 현재 값이 보이도록 한다 */}
          {!orgs.data && asset.org && <option value={asset.org.id}>{asset.org.label}</option>}
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label} ({o.code})
            </option>
          ))}
        </select>
      )}
      {busy ? (
        <span className="spinner" />
      ) : (
        <button className="link-btn small" onClick={() => setEditing(false)}>
          취소
        </button>
      )}
    </div>
  );
}
