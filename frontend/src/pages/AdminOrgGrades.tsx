// 시스템 관리 › N²SF 기관 등급표 — 기관이 N²SF 1단계(준비)에서 만든 업무정보 · 정보시스템 등급표를 올려 자산과 매칭한다
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useAuth } from "../auth";
import type { OrgGradeEntry } from "../types";
import { Badge, Banner, Card, CodeBlock, ConfirmButton, Empty, QueryState, fmtDateTime, fmtNum, useToast } from "../ui";

const SAMPLE = "업무정보명,정보시스템,소관부서,등급,개인정보 포함,법령 근거,비고\n도로목록,도로대장시스템,도로과,O,,,\n교통사고,사고관리시스템,안전정책과,S2,포함,도로교통법 제54조,\n민원인 명부,민원시스템,민원실,C,포함,개인정보 보호법,\n";
const TONE: Record<string, "ok" | "warn" | "err" | "muted"> = { O: "ok", S1: "warn", S2: "warn", C: "err" };

export function OrgGradesTab() {
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["org-grades"], queryFn: api.orgGrades });
  const assetsQ = useQuery({ queryKey: ["assets", "all"], queryFn: () => api.assets() });
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<{ imported: number; auto_matched: number; skipped: string[] } | null>(null);
  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ["org-grades"] }), qc.invalidateQueries({ queryKey: ["process"] })]);

  const upload = async (f: File) => {
    setBusy("import");
    try {
      const r = await api.importOrgGrades(f);
      setResult(r);
      await refresh();
      toast.ok(`등급표 ${r.imported}행을 가져왔습니다 — 자동 매칭 ${r.auto_matched}건`);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };
  const match = async (e: OrgGradeEntry, assetId: number | null) => {
    setBusy(`m${e.id}`);
    try {
      await api.matchOrgGrade(e.id, assetId);
      await refresh();
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(null);
    }
  };
  const assetName = (id: number | null) => (id == null ? null : assetsQ.data?.find((a) => a.id === id)?.name ?? `#${id}`);

  return (
    <div className="col gap-12">
      <Card title="N²SF 기관 등급표 가져오기">
        <p className="small muted">
          기관이 N²SF 가이드라인 1단계(준비)에서 만든 <b>업무정보 · 정보시스템 등급표</b>를 CSV 로 올립니다. 이름이 같거나 포함 관계인 자산은 자동으로 매칭되고, 나머지는 아래에서 고릅니다.
          매칭된 등급은 STEP 4 의 <b>제안 등급</b>에 반영되어 그보다 낮게 정하려면 사유가 필요하고, 컬럼 민감 항목과 어긋나면 검수 큐에 "기관 등급표와 불일치" 신호가 올라갑니다.
          열 이름은 업무정보명 · 정보시스템 · 소관부서 · 등급(C/S1/S2/O 또는 1/2/3) · 개인정보 포함 · 법령 근거 · 비고를 알아봅니다 (최소 업무정보명 · 등급).
        </p>
        <div className="row wrap gap-8 mt-8" style={{ alignItems: "center" }}>
          <input ref={fileRef} type="file" accept=".csv,text/csv" disabled={!isAdmin || busy !== null} onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])} />
          {!isAdmin && <span className="small muted">가져오기 · 비우기는 관리자만 할 수 있습니다 (매칭 수정은 담당자도 가능)</span>}
          {isAdmin && q.data && q.data.total > 0 && (
            <ConfirmButton size="sm" confirmLabel="정말 비우기" busy={busy === "clear"} onConfirm={() => { setBusy("clear"); api.clearOrgGrades().then(refresh).catch(toast.error).finally(() => setBusy(null)); }}>
              등급표 비우기
            </ConfirmButton>
          )}
        </div>
        {result && (
          <div className="mt-8">
            <Banner tone={result.skipped.length ? "warn" : "ok"}>
              {result.imported}행 가져옴 · 자동 매칭 {result.auto_matched}건{result.skipped.length > 0 && <> · 건너뜀 {result.skipped.length}건: {result.skipped.slice(0, 5).join(" / ")}</>}
            </Banner>
          </div>
        )}
        <details className="mt-8">
          <summary className="small link-btn">양식 예시 보기</summary>
          <CodeBlock text={SAMPLE} />
        </details>
      </Card>

      <Card title={<>등급표 {q.data && <Badge>{fmtNum(q.data.total)}행 · 매칭 {q.data.matched} · 미매칭 {q.data.unmatched}</Badge>}</>}>
        <QueryState q={q}>
          {q.data && q.data.items.length === 0 ? (
            <Empty>가져온 등급표가 없습니다</Empty>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>업무정보명</th>
                  <th>정보시스템 · 부서</th>
                  <th>등급</th>
                  <th>개인정보 · 법령</th>
                  <th>매칭 자산</th>
                  <th>가져온 때</th>
                </tr>
              </thead>
              <tbody>
                {(q.data?.items ?? []).map((e) => (
                  <tr key={e.id}>
                    <td>
                      <b>{e.name}</b>
                      {e.note && <div className="small dim">{e.note}</div>}
                    </td>
                    <td className="small">{[e.system, e.department].filter(Boolean).join(" · ") || "—"}</td>
                    <td><Badge tone={TONE[e.grade] ?? "muted"}>{e.grade_label ?? e.grade}</Badge></td>
                    <td className="small">{[e.personal_data, e.legal_basis].filter(Boolean).join(" · ") || "—"}</td>
                    <td>
                      <select className="input" style={{ minWidth: 200 }} value={e.asset_id ?? ""} disabled={busy !== null}
                        onChange={(ev) => void match(e, ev.target.value ? Number(ev.target.value) : null)}>
                        <option value="">미매칭</option>
                        {e.candidates.map((c) => (
                          <option key={c.asset_id} value={c.asset_id}>
                            {c.name} ({c.score}점)
                          </option>
                        ))}
                        {e.asset_id && !e.candidates.some((c) => c.asset_id === e.asset_id) && <option value={e.asset_id}>{assetName(e.asset_id)}</option>}
                        {(assetsQ.data ?? []).filter((a) => !e.candidates.some((c) => c.asset_id === a.id) && a.id !== e.asset_id).map((a) => (
                          <option key={a.id} value={a.id}>{a.name}</option>
                        ))}
                      </select>
                      {e.asset_id && e.match_score > 0 && e.match_score < 100 && <div className="tiny muted">자동 매칭 {e.match_score}점 — 확인하세요</div>}
                    </td>
                    <td className="small nowrap">{fmtDateTime(e.imported_at)}<div className="tiny dim">{e.source_file}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </QueryState>
      </Card>
    </div>
  );
}
