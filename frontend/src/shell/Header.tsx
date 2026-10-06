import { useState } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api";
import { useAuth, useReference } from "../auth";
import { Badge, Button, Field, Modal, useToast } from "../ui";

const NAV = [
  { to: "/", label: "HOME", ico: "⌂", color: "#e8912d", end: true },
  { to: "/studio", label: "ARD 스튜디오", ico: "◈", color: "#1E5EFF" },
  { to: "/assets", label: "데이터 패브릭 관리", ico: "▦", color: "#2aa876" },
  { to: "/catalog", label: "데이터 카탈로그", ico: "≣", color: "#7a3fa0" },
  { to: "/admin", label: "시스템 관리", ico: "⚙", color: "#111318" },
];

export function Header() {
  const { user, logout } = useAuth();
  const ref = useReference();
  const [menu, setMenu] = useState(false);
  const [pw, setPw] = useState(false);
  const role = ref.roles.find((r) => r.value === user.role);
  return (
    <header className="header">
      <div className="row gap-16 wrap">
        <div className="brand">
          <div className="brand-mark">◈</div>
          <div>
            <div className="brand-name">FDE Data Studio</div>
            <div className="brand-sub">Forward Deployed Engineering</div>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
              <span className="ico" style={{ background: n.color }}>
                {n.ico}
              </span>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="row" style={{ position: "relative" }}>
        <Badge tone="muted" title="셰이프 세트 버전">
          SHACL {ref.shapes_version}
        </Badge>
        <button className="chip" onClick={() => setMenu((v) => !v)} aria-haspopup="menu" aria-expanded={menu}>
          <span
            style={{ width: 22, height: 22, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}
          >
            {user.name.slice(0, 1)}
          </span>
          {user.name}
        </button>
        {menu && (
          <div className="card tight" role="menu" style={{ position: "absolute", top: 40, right: 0, width: 260, zIndex: 60, boxShadow: "var(--shadow-2)" }}>
            <div className="bold">
              {user.name} <Badge tone="info">{role?.label || user.role}</Badge>
            </div>
            <div className="small muted mt-4">
              {user.username}
              {user.org_label ? ` · ${user.org_label}` : ""}
            </div>
            <div className="small muted">{role?.desc}</div>
            <hr className="divider" />
            <div className="row between">
              <button
                className="link-btn"
                onClick={() => {
                  setPw(true);
                  setMenu(false);
                }}
              >
                비밀번호 변경
              </button>
              <button className="link-btn danger" onClick={logout}>
                로그아웃
              </button>
            </div>
          </div>
        )}
      </div>
      {pw && <PasswordModal onClose={() => setPw(false)} />}
    </header>
  );
}

function PasswordModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api.changePassword(cur, next);
      toast.ok("비밀번호를 변경했습니다");
      onClose();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title="비밀번호 변경"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>취소</Button>
          <Button variant="primary" busy={busy} disabled={!cur || next.length < 8} onClick={save}>
            변경
          </Button>
        </>
      }
    >
      <div className="col gap-12">
        <Field label="현재 비밀번호">
          <input className="input" type="password" value={cur} onChange={(e) => setCur(e.target.value)} autoComplete="current-password" />
        </Field>
        <Field label="새 비밀번호" hint="8자 이상">
          <input className="input" type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
        </Field>
      </div>
    </Modal>
  );
}
