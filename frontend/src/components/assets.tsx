// 원천(Asset) 관련 공용 부품: 업로드, 스트림 등록, 프로파일 보기. STEP 1 과 데이터 패브릭 관리 화면이 함께 쓴다.
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth, useReference } from "../auth";
import { ProfileTable } from "../studio/shared";
import type { Asset } from "../types";
import { Badge, Banner, Button, Empty, Field, KeyPill, Modal, QueryState, Tabs, cx, fmtDateTime, fmtNum, shortHash, useToast } from "../ui";

/** 파일 끌어다 놓기 + 선택. 업로드가 끝나면 생성된 원천 목록을 onUploaded 로 넘긴다. */
export function UploadZone({ onUploaded, disabled }: { onUploaded: (created: Asset[]) => void; disabled?: boolean }) {
  const ref = useReference();
  const qc = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rejected, setRejected] = useState<{ filename: string; reason: string }[]>([]);

  const send = async (files: File[]) => {
    if (!files.length || disabled) return;
    setBusy(true);
    setRejected([]);
    try {
      const r = await api.uploadAssets(files);
      setRejected(r.rejected);
      await qc.invalidateQueries({ queryKey: ["assets"] });
      if (r.created.length) {
        toast.ok(`업로드 ${r.created.length}건 — 프로파일 완료`);
        onUploaded(r.created);
      }
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <div>
      <div
        className={cx("dropzone", over && "over")}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          send(Array.from(e.dataTransfer.files));
        }}
      >
        <div className="bold" style={{ fontSize: 14 }}>
          엑셀 · CSV · JSON · JSON Lines · Parquet 파일을 끌어다 놓으세요
        </div>
        <div className="muted mt-4">
          여러 파일을 한 번에 올릴 수 있습니다 · 파일당 최대 {ref.max_upload_mb}MB · 또는{" "}
          <button className="link-btn" disabled={disabled || busy} onClick={() => input.current?.click()}>
            파일 선택
          </button>
        </div>
        <input
          ref={input}
          type="file"
          multiple
          hidden
          accept={ref.upload_exts.map((e) => `.${e}`).join(",")}
          onChange={(e) => send(Array.from(e.target.files || []))}
        />
        {busy && (
          <div className="row mt-12" style={{ justifyContent: "center" }}>
            <span className="spinner" /> 업로드하고 컬럼을 프로파일링하는 중…
          </div>
        )}
        <div className="tiny muted mt-12">
          올린 파일은 서버에 보관되고, 컬럼 타입 · 결측 · 시간 포맷 · 연계키 후보가 실제 값에서 계산됩니다. 영상·패킷 등 실시간성 대용량 데이터는 스트림으로 등록하세요.
        </div>
      </div>
      {rejected.length > 0 && (
        <div className="mt-8">
          <Banner tone="warn">
            <b>업로드하지 않은 파일 {rejected.length}건</b>
            {rejected.map((r) => (
              <div key={r.filename} className="small">
                {r.filename} — {r.reason}
              </div>
            ))}
          </Banner>
        </div>
      )}
    </div>
  );
}

const FIELD_TYPES = ["string", "integer", "number", "datetime", "boolean"];
const RESOLUTIONS = [
  { v: "PT1S", l: "1초 (PT1S)" }, { v: "PT10S", l: "10초 (PT10S)" }, { v: "PT1M", l: "1분 (PT1M)" }, { v: "PT5M", l: "5분 (PT5M)" },
  { v: "PT10M", l: "10분 (PT10M)" }, { v: "PT1H", l: "1시간 (PT1H)" }, { v: "P1D", l: "1일 (P1D)" }, { v: "", l: "불규칙 · 이벤트 발생 시" },
];
/** 흔한 공공 스트림 예시. 「예시로 채우기」로 넣고 고쳐 쓰게 한다 */
const STREAM_EXAMPLES: { label: string; name: string; description: string; resolution: string; eventTime: string; endpoint: string; fields: { name: string; type: string }[] }[] = [
  { label: "CCTV 차량 검지", name: "cctv.vehicle.det.v1", description: "도로 CCTV 영상에서 검지한 차량 이벤트 (영상 본체는 저장하지 않음)", resolution: "PT1S", eventTime: "event_time",
    endpoint: "kafka://broker:9092/cctv.vehicle.det.v1",
    fields: [{ name: "event_time", type: "datetime" }, { name: "cctv_id", type: "string" }, { name: "link_id", type: "string" }, { name: "vehicle_type", type: "string" }, { name: "speed_kmh", type: "number" }] },
  { label: "기상 관측(AWS)", name: "weather.aws.obs.v1", description: "자동기상관측장비 1분 관측값", resolution: "PT1M", eventTime: "obs_time", endpoint: "https://api.example.go.kr/aws/stream",
    fields: [{ name: "obs_time", type: "datetime" }, { name: "station_id", type: "string" }, { name: "temp_c", type: "number" }, { name: "rain_mm", type: "number" }, { name: "wind_ms", type: "number" }] },
  { label: "교통량 검지기(VDS)", name: "vds.traffic.volume.v1", description: "차량검지기 5분 집계 교통량 · 속도", resolution: "PT5M", eventTime: "collected_at", endpoint: "kafka://broker:9092/vds.traffic.volume.v1",
    fields: [{ name: "collected_at", type: "datetime" }, { name: "vds_id", type: "string" }, { name: "link_id", type: "string" }, { name: "volume", type: "integer" }, { name: "avg_speed", type: "number" }] },
];

/** 스트림 등록. 스트림은 값을 읽지 않고 메타데이터(스키마·시간 규격)만 등록한다. */
export function StreamModal({ onClose, onCreated }: { onClose: () => void; onCreated: (a: Asset) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const orgs = useQuery({ queryKey: ["orgs"], queryFn: api.orgs });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [orgId, setOrgId] = useState<string>("");
  const [resolution, setResolution] = useState("");
  const [eventTime, setEventTime] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [timezone, setTimezone] = useState("Asia/Seoul");
  const [fields, setFields] = useState<{ name: string; type: string }[]>([{ name: "", type: "datetime" }]);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const a = await api.registerStream({
        name: name.trim(),
        description: description.trim() || undefined,
        org_id: orgId ? Number(orgId) : null,
        temporal_resolution: resolution.trim() || undefined,
        event_time_column: eventTime.trim() || fields.find((f) => f.type === "datetime" && f.name.trim())?.name.trim() || undefined,
        endpoint_url: endpoint.trim() || undefined,
        timezone: timezone.trim() || undefined,
        fields: fields.filter((f) => f.name.trim()),
      });
      await qc.invalidateQueries({ queryKey: ["assets"] });
      toast.ok(`스트림 등록 — ${a.name}`);
      onCreated(a);
      onClose();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const setField = (i: number, patch: Partial<{ name: string; type: string }>) => setFields((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)));

  return (
    <Modal
      title="스트림 등록"
      onClose={onClose}
      wide
      footer={
        <>
          <Button onClick={onClose}>취소</Button>
          <Button variant="primary" busy={busy} disabled={!name.trim()} onClick={save}>
            등록
          </Button>
        </>
      }
    >
      <p className="small muted mb-8">
        실시간 스트림은 데이터 본체를 올리지 않습니다. <b>이름만 있으면 등록</b>되고, 나머지는 나중에 STEP 3 에서 채워도 됩니다. 스키마 필드 이름에서 연계키 후보를 계산하니 필드는 적어 두는 게 좋습니다.
      </p>
      <div className="row wrap gap-4 mb-12" style={{ alignItems: "center" }}>
        <span className="small dim">예시로 채우기:</span>
        {STREAM_EXAMPLES.map((ex) => (
          <button
            key={ex.name}
            type="button"
            className="chip"
            onClick={() => {
              setName(ex.name);
              setDescription(ex.description);
              setResolution(ex.resolution);
              setEventTime(ex.eventTime);
              setEndpoint(ex.endpoint);
              setFields(ex.fields.map((f) => ({ ...f })));
            }}
          >
            {ex.label}
          </button>
        ))}
        <span className="tiny muted">넣은 뒤 이름 · 필드를 기관 것으로 고치세요</span>
      </div>
      <div className="grid c2">
        <Field label="스트림(토픽) 이름" hint="기관에서 부르는 이름 그대로. 예: cctv.vehicle.det.v1, 교통량_VDS_5분">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label="제공기관">
          <select className="select" value={orgId} onChange={(e) => setOrgId(e.target.value)}>
            <option value="">— 선택 안 함 —</option>
            {(orgs.data || []).filter((o) => o.active).map((o) => (
              <option key={o.id} value={o.id}>
                {o.label} ({o.code})
              </option>
            ))}
          </select>
        </Field>
        <Field label="데이터가 들어오는 간격 (시간 해상도)" hint="고르면 ISO 8601 duration 으로 저장됩니다 (dcat:temporalResolution)">
          <div className="row gap-4">
            <select className="select" value={RESOLUTIONS.some((r) => r.v === resolution) ? resolution : "__custom"} onChange={(e) => setResolution(e.target.value === "__custom" ? "PT" : e.target.value)}>
              {RESOLUTIONS.map((r) => (
                <option key={r.v || "none"} value={r.v}>
                  {r.l}
                </option>
              ))}
              <option value="__custom">직접 입력…</option>
            </select>
            {!RESOLUTIONS.some((r) => r.v === resolution) && (
              <input className="input mono" style={{ width: 120 }} value={resolution} onChange={(e) => setResolution(e.target.value)} placeholder="PT30S" aria-label="시간 해상도 직접 입력" />
            )}
          </div>
        </Field>
        <Field label="시각이 담긴 필드 (event-time)" hint="아래 스키마 필드 중 datetime 타입 하나. 비우면 첫 datetime 필드를 씁니다">
          <select className="select" value={eventTime} onChange={(e) => setEventTime(e.target.value)}>
            <option value="">— 첫 datetime 필드 —</option>
            {fields.filter((f) => f.name.trim()).map((f) => (
              <option key={f.name} value={f.name}>
                {f.name} ({f.type})
              </option>
            ))}
            {eventTime && !fields.some((f) => f.name === eventTime) && <option value={eventTime}>{eventTime}</option>}
          </select>
        </Field>
        <Field label="엔드포인트 URL (선택)" hint="브로커 · API 주소. 모르면 비워 두세요 (dcat:endpointURL)">
          <input className="input mono" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} placeholder="kafka://broker:9092/topic 또는 https://…" />
        </Field>
        <Field label="타임존">
          <select className="select" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
            {["Asia/Seoul", "UTC"].map((z) => (
              <option key={z}>{z}</option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="설명" style={{ marginTop: 12 }}>
        <textarea className="textarea" value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>
      <div className="section-title">
        스키마 필드 <span className="muted small">이름과 타입 · 시각 필드는 datetime, ID · 코드는 string</span>
      </div>
      <div className="col">
        {fields.map((f, i) => (
          <div className="row" key={i}>
            <input className="input mono" placeholder="필드 이름" value={f.name} onChange={(e) => setField(i, { name: e.target.value })} />
            <select className="select" style={{ width: 140 }} value={f.type} onChange={(e) => setField(i, { type: e.target.value })}>
              {FIELD_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <button className="link-btn danger" onClick={() => setFields((fs) => fs.filter((_, j) => j !== i))} aria-label="필드 삭제">
              ✕
            </button>
          </div>
        ))}
        <div>
          <Button size="sm" onClick={() => setFields((fs) => [...fs, { name: "", type: "string" }])}>
            ＋ 필드 추가
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** 원천 1건의 프로파일 상세 (표·컬럼·표본 행·연계키 후보·경고) */
export function AssetProfileModal({ assetId, onClose }: { assetId: number; onClose: () => void }) {
  const q = useQuery({ queryKey: ["assets", assetId], queryFn: () => api.asset(assetId) });
  const qc = useQueryClient();
  const toast = useToast();
  const { canWrite } = useAuth();
  const [tab, setTab] = useState(0);
  const [view, setView] = useState<"columns" | "rows">("columns");
  const a = q.data;
  const tables = a?.profile?.tables || [];
  const t = tables[Math.min(tab, Math.max(0, tables.length - 1))];
  return (
    <Modal title={a ? a.name : "프로파일"} onClose={onClose} wide>
      <QueryState q={q}>
        {a && (
          <div className="col gap-12">
            <div className="row wrap">
              <Badge tone={a.kind === "stream" ? "purple" : a.source === "dbschema" ? "dark" : "info"}>{a.kind === "stream" ? "실시간 스트림" : a.source === "dbschema" ? "DB 스키마" : a.data_form || "파일"}</Badge>
              <span className="small">{a.profile_summary}</span>
              {a.minted_id && <Badge tone="ok">발행 ID {a.minted_id}</Badge>}
            </div>
            <dl className="kv">
              {a.source === "dbschema" ? (
                <>
                  <dt>원천 표</dt>
                  <dd>
                    <span className="mono">{a.filename}</span> · 커넥터 {a.connector?.name || "—"}
                    {a.connector?.deleted && <Badge tone="warn">커넥터 삭제됨</Badge>}
                  </dd>
                  <dt>구조 지문</dt>
                  <dd className="mono" title="컬럼 이름 · 자료형 · 널 허용 · 기본키로 만든 해시. 동기화 때 바뀌었는지 판단합니다">
                    {shortHash(a.sha256, 24)}…
                  </dd>
                </>
              ) : a.filename ? (
                <>
                  <dt>파일</dt>
                  <dd>
                    {a.filename} · {a.size_label} · <span className="mono">{a.media_type}</span>
                  </dd>
                  <dt>SHA-256</dt>
                  <dd className="mono">{shortHash(a.sha256, 24)}…</dd>
                </>
              ) : null}
              {a.kind === "stream" && (
                <>
                  <dt>시간 규격</dt>
                  <dd className="mono">
                    {a.stream.temporal_resolution || "—"} · event-time {a.stream.event_time_column || "—"} · {a.stream.timezone || "—"}
                  </dd>
                  <dt>엔드포인트</dt>
                  <dd className="mono">{a.stream.endpoint_url || "—"}</dd>
                </>
              )}
              <dt>제공기관</dt>
              <dd>{a.org ? `${a.org.label} (${a.org.code})` : "미지정"}</dd>
              <dt>등록</dt>
              <dd>{fmtDateTime(a.created_at)}</dd>
              {a.used_in && a.used_in.length > 0 && (
                <>
                  <dt>사용 중</dt>
                  <dd>{a.used_in.map((u) => u.name).join(", ")}</dd>
                </>
              )}
            </dl>
            {a.error && <Banner tone="err">프로파일 실패 — {a.error}</Banner>}
            {a.warnings.length > 0 && (
              <Banner tone="warn">
                {a.warnings.map((w) => (
                  <div key={w}>{w}</div>
                ))}
              </Banner>
            )}
            {a.key_candidates.length > 0 && (
              <div>
                <div className="small bold dim mb-8">연계키 후보 (컬럼명·값 패턴 규칙으로 계산)</div>
                <div className="row wrap">
                  {a.key_candidates.map((k) => (
                    <span key={`${k.table}|${k.column}`} className="badge" title={k.reason}>
                      <KeyPill code={k.code} label={k.label} /> {k.column} · {Math.round(k.score * 100)}점
                    </span>
                  ))}
                </div>
              </div>
            )}
            {tables.length === 0 ? (
              <Empty>표 구조 프로파일이 없습니다</Empty>
            ) : (
              <>
                <div className="row between wrap">
                  {tables.length > 1 ? <Tabs tabs={tables.map((x, i) => ({ key: i, label: x.name }))} value={tab} onChange={setTab} /> : <span className="bold">{t.name}</span>}
                  {a.kind !== "stream" && (
                    <Tabs
                      tabs={[
                        { key: "columns", label: "컬럼 프로파일" },
                        { key: "rows", label: "표본 행" },
                      ]}
                      value={view}
                      onChange={setView}
                    />
                  )}
                </div>
                {a.kind !== "stream" && (
                  <div className="small muted">
                    {fmtNum(t.rows)}행 · {t.columns.length}컬럼 · 머리글 {t.header_row}행{t.truncated ? " · 프로파일 상한까지만 판독" : ""}
                    {t.preamble.length > 0 ? ` · 머리글 위 설명 행: ${t.preamble.join(" / ")}` : ""}
                  </div>
                )}
                {view === "columns" || a.kind === "stream" ? (
                  <ProfileTable
                    table={t}
                    asset={a}
                    onEditSamples={
                      canWrite
                        ? async (column, samples) => {
                            try {
                              await api.updateColumn(a.id, t.name, column, { samples });
                              await qc.invalidateQueries({ queryKey: ["assets"] });
                              void qc.invalidateQueries({ queryKey: ["process"] });
                              toast.ok(`예시값 저장 — ${column}`);
                            } catch (e) {
                              toast.error(e);
                              throw e;
                            }
                          }
                        : undefined
                    }
                  />
                ) : (
                  <div className="table-wrap" style={{ maxHeight: 360, overflow: "auto" }}>
                    <table className="table">
                      <thead>
                        <tr>
                          {t.columns.map((c) => (
                            <th key={c.name}>{c.name}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {t.sample_rows.map((r, i) => (
                          <tr key={i}>
                            {r.map((v, j) => (
                              <td key={j} className="nowrap">
                                {v}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </QueryState>
    </Modal>
  );
}
