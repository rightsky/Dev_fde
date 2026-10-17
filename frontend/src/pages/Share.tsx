// 공유 링크 받는 쪽 화면 (로그인 없음). /share/{토큰} — 파일 정보와 남은 횟수를 보이고 내려받는다.
import { useEffect, useState } from "react";
import { api, downloads } from "../api";
import type { ShareInfo } from "../types";
import { Badge, Button, Loading, errText, fmtDateTime } from "../ui";

export function SharePage() {
  const token = decodeURIComponent(window.location.pathname.replace(/^\/share\//, "").replace(/\/+$/, ""));
  const [info, setInfo] = useState<ShareInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = () => api.shareInfo(token).then(setInfo).catch((e) => setError(errText(e)));
  useEffect(() => {
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const download = async () => {
    setBusy(true);
    try {
      // 인증 헤더 없이 받는다. 서버가 횟수를 세고 기록한다
      const res = await fetch(`/api${downloads.shareDownload(token)}`);
      if (!res.ok) {
        let msg = `내려받기 실패 (${res.status})`;
        try {
          const body = await res.json();
          msg = body.detail?.message || body.detail || msg;
        } catch {
          /* 본문 없음 */
        }
        throw new Error(msg);
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = info?.filename || "download";
      a.click();
      URL.revokeObjectURL(a.href);
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="login-card" style={{ maxWidth: 520 }}>
        <div className="row" style={{ alignItems: "center", gap: 8 }}>
          <div>
            <div className="bold">FDE Data Studio</div>
            <div className="tiny muted">공유 링크로 받은 산출물</div>
          </div>
        </div>
        {!info && !error && <Loading />}
        {error && !info && <div className="t-err mt-12">{error}</div>}
        {info && (
          <div className="col gap-8 mt-12">
            <div className="bold" style={{ fontSize: 18, wordBreak: "break-all" }}>
              {info.filename}
            </div>
            <div className="row wrap gap-4">
              <Badge tone="info">{info.kind_label}</Badge>
              {info.grade && <Badge tone={info.grade === "O" ? "ok" : "warn"}>N²SF {info.grade}</Badge>}
            </div>
            <dl className="kv">
              {info.recipient && (
                <>
                  <dt>받는 곳</dt>
                  <dd>{info.recipient}</dd>
                </>
              )}
              <dt>만료</dt>
              <dd>{fmtDateTime(info.expires_at)}</dd>
              <dt>남은 횟수</dt>
              <dd>{info.remaining}회</dd>
              <dt>보낸 사람</dt>
              <dd>{info.created_by}</dd>
              {info.note && (
                <>
                  <dt>메모</dt>
                  <dd>{info.note}</dd>
                </>
              )}
            </dl>
            {info.ok ? (
              <Button variant="primary" busy={busy} onClick={download}>
                ⤓ 내려받기
              </Button>
            ) : (
              <div className="t-err bold">{info.reason}</div>
            )}
            {error && <div className="t-err small">{error}</div>}
            <p className="tiny muted">{info.notice}</p>
          </div>
        )}
      </div>
    </div>
  );
}
