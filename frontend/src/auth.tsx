import { createContext, useContext, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, auth } from "./api";
import type { Reference, User } from "./types";
import { Button, Loading, errText } from "./ui";

interface AuthValue {
  user: User;
  isAdmin: boolean;
  canWrite: boolean;
  logout: () => void;
}
const AuthCtx = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
  const v = useContext(AuthCtx);
  if (!v) throw new Error("AuthProvider 밖에서 useAuth 를 호출했습니다");
  return v;
}

/** 참조 데이터(단계 라벨·어휘·폼 필드 정의). 로그인 후 한 번만 불러온다. */
export function useReference(): Reference {
  const q = useQuery({ queryKey: ["reference"], queryFn: api.reference, staleTime: Infinity });
  if (!q.data) throw new Error("참조 데이터가 아직 없습니다");
  return q.data;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [token, setToken] = useState(auth.token);
  useEffect(() => {
    const off = auth.onChange(() => setToken(auth.token));
    return () => {
      off();
    };
  }, []);
  const me = useQuery({ queryKey: ["me", token], queryFn: api.me, enabled: !!token, retry: false, staleTime: 60_000 });
  const ref = useQuery({ queryKey: ["reference"], queryFn: api.reference, enabled: !!token && !!me.data, staleTime: Infinity });

  if (!token) return <Login />;
  if (me.isLoading || (me.data && ref.isLoading)) {
    return (
      <div className="login-wrap">
        <Loading />
      </div>
    );
  }
  if (me.error || !me.data || ref.error) {
    return (
      <div className="login-wrap">
        <div className="login-card">
          <div className="t-err bold">{errText(me.error || ref.error)}</div>
          <Button variant="primary" onClick={() => auth.set(null)}>
            다시 로그인
          </Button>
        </div>
      </div>
    );
  }
  const user = me.data;
  const value: AuthValue = {
    user,
    isAdmin: user.role === "admin",
    canWrite: user.role === "admin" || user.role === "worker",
    logout: () => {
      auth.set(null);
      qc.clear();
    },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.login(username.trim(), password);
      auth.set(r.access_token);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="brand">
          <div className="brand-mark">◈</div>
          <div>
            <div className="brand-name">FDE Data Studio</div>
            <div className="brand-sub">Forward Deployed Engineering</div>
          </div>
        </div>
        <div className="col" style={{ gap: 10 }}>
          <label className="field">
            <span className="label">ID</span>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="아이디" autoComplete="username" autoFocus />
          </label>
          <label className="field">
            <span className="label">Password</span>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="비밀번호" autoComplete="current-password" />
          </label>
        </div>
        {error && (
          <div className="small bold t-err" role="alert">
            {error}
          </div>
        )}
        <Button type="submit" variant="primary" size="lg" busy={busy} disabled={!username.trim() || !password}>
          로그인
        </Button>
      </form>
    </div>
  );
}
