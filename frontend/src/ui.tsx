// 공용 UI 부품. 화면 코드는 여기 있는 것과 styles.css 의 클래스만 조합해서 만든다.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { ApiError } from "./api";
import type { Severity } from "./types";

// ───────────── 형식 도우미
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
export const fmtNum = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString("ko-KR"));
export const fmtPct = (r: number | null | undefined, digits = 0) => (r == null ? "—" : `${(r * 100).toFixed(digits)}%`);
export const shortHash = (h: string | null | undefined, n = 8) => (h ? h.slice(0, n) : "—");
export function errText(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "알 수 없는 오류가 발생했습니다";
}
export const cx = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(" ");

// ───────────── 기본 부품
type BtnVariant = "primary" | "dark" | "outline" | "ok" | "danger" | "default";
export function Button(props: {
  children: ReactNode;
  onClick?: () => void;
  variant?: BtnVariant;
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  busy?: boolean;
  block?: boolean;
  title?: string;
  type?: "button" | "submit";
  style?: CSSProperties;
  "aria-label"?: string;
}) {
  const { variant = "default", size = "md", busy, disabled, block, children, type = "button", ...rest } = props;
  return (
    <button
      type={type}
      className={cx("btn", variant !== "default" && variant, size !== "md" && size, block && "block")}
      disabled={disabled || busy}
      {...rest}
    >
      {busy && <span className="spinner" />}
      {children}
    </button>
  );
}

type Tone = "ok" | "warn" | "err" | "info" | "purple" | "dark" | "solid" | "muted";
export function Badge({ tone = "muted", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={cx("badge", tone !== "muted" && tone)} title={title}>
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const tone: Tone = severity === "Violation" ? "err" : severity === "Warning" ? "warn" : "info";
  return <Badge tone={tone}>{severity}</Badge>;
}

export function KeyPill({ code, label }: { code: string; label?: string | null }) {
  return (
    <span className="key-pill" title={label || undefined}>
      {code}
      {label ? ` ${label}` : ""}
    </span>
  );
}

export function Card(props: { title?: ReactNode; right?: ReactNode; children?: ReactNode; className?: string; style?: CSSProperties; onClick?: () => void }) {
  return (
    <div className={cx("card", props.className, props.onClick && "clickable")} style={props.style} onClick={props.onClick}>
      {(props.title || props.right) && (
        <div className="card-head">
          <div className="card-title">{props.title}</div>
          {props.right}
        </div>
      )}
      {props.children}
    </div>
  );
}

export function Banner({ tone = "info", children, right }: { tone?: "ok" | "warn" | "err" | "info"; children: ReactNode; right?: ReactNode }) {
  return (
    <div className={cx("banner", tone)} role={tone === "err" ? "alert" : undefined}>
      <div className="grow">{children}</div>
      {right}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Loading({ label = "불러오는 중" }: { label?: string }) {
  return (
    <div className="loading">
      <span className="spinner" />
      {label}
    </div>
  );
}

/** react-query 의 조회 상태를 일관되게 그린다. */
export function QueryState({ q, children }: { q: { isLoading: boolean; error: unknown; data: unknown }; children: ReactNode }) {
  if (q.isLoading) return <Loading />;
  if (q.error) return <Banner tone="err">{errText(q.error)}</Banner>;
  if (q.data == null) return null;
  return <>{children}</>;
}

export function Field(props: { label: ReactNode; hint?: ReactNode; children: ReactNode; style?: CSSProperties }) {
  return (
    <label className="field" style={props.style}>
      <span className="label">{props.label}</span>
      {props.children}
      {props.hint && <span className="hint">{props.hint}</span>}
    </label>
  );
}

export function Tabs<K extends string | number>(props: { tabs: { key: K; label: ReactNode }[]; value: K; onChange: (k: K) => void }) {
  return (
    <div className="tabs" role="tablist">
      {props.tabs.map((t) => (
        <button key={String(t.key)} role="tab" aria-selected={t.key === props.value} className={cx("tab", t.key === props.value && "on")} onClick={() => props.onChange(t.key)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Meter({ value, tone }: { value: number; tone?: "ok" | "warn" | "err" }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className={cx("meter", tone)}>
      <span style={{ width: `${v}%` }} />
    </div>
  );
}

export function CodeBlock({ text, wrap, light, maxHeight }: { text: string; wrap?: boolean; light?: boolean; maxHeight?: number }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* 클립보드 권한 없음 */
    }
  };
  return (
    <div style={{ position: "relative" }}>
      <button className="btn sm" style={{ position: "absolute", top: 8, right: 8, opacity: 0.9 }} onClick={copy}>
        {copied ? "복사됨" : "복사"}
      </button>
      <pre className={cx("code", wrap && "wrap", light && "light")} style={maxHeight ? { maxHeight } : undefined}>
        {text}
      </pre>
    </div>
  );
}

export function Modal(props: { title: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(props.onClose);
  onCloseRef.current = props.onClose;
  // 포커스 이동과 Esc 등록은 열릴 때 한 번만 한다 (다시 그릴 때마다 포커스를 뺏으면 모달 안 입력이 끊긴다)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCloseRef.current();
    document.addEventListener("keydown", onKey);
    if (ref.current && !ref.current.contains(document.activeElement)) ref.current.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && props.onClose()}>
      <div className={cx("modal", props.wide && "wide")} role="dialog" aria-modal="true" tabIndex={-1} ref={ref}>
        <div className="modal-head">
          <div className="modal-title">{props.title}</div>
          <button className="link-btn" onClick={props.onClose} aria-label="닫기">
            ✕
          </button>
        </div>
        <div className="modal-body">{props.children}</div>
        {props.footer && <div className="modal-foot">{props.footer}</div>}
      </div>
    </div>
  );
}

// ───────────── 토스트
type ToastItem = { id: number; text: string; tone?: "ok" | "err" };
const ToastCtx = createContext<(text: string, tone?: "ok" | "err") => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);
  const push = useCallback((text: string, tone?: "ok" | "err") => {
    const id = ++seq.current;
    setItems((xs) => [...xs.slice(-3), { id, text, tone }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), tone === "err" ? 6000 : 3200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={cx("toast", t.tone)}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/** toast("문구") · toast.error(e) */
export function useToast() {
  const push = useContext(ToastCtx);
  return useMemo(() => Object.assign((text: string) => push(text), { ok: (text: string) => push(text, "ok"), error: (e: unknown) => push(errText(e), "err") }), [push]);
}

/** 한 번 더 눌러야 실행되는 위험 동작 버튼 */
export function ConfirmButton(props: { children: ReactNode; confirmLabel?: string; onConfirm: () => void; variant?: BtnVariant; size?: "sm" | "md"; disabled?: boolean; busy?: boolean }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(t);
  }, [armed]);
  return (
    <Button
      variant={armed ? "danger" : props.variant}
      size={props.size}
      disabled={props.disabled}
      busy={props.busy}
      onClick={() => {
        if (armed) {
          setArmed(false);
          props.onConfirm();
        } else setArmed(true);
      }}
    >
      {armed ? props.confirmLabel || "한 번 더 눌러 확인" : props.children}
    </Button>
  );
}
