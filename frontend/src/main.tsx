import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { AuthGate } from "./auth";
import { SharePage } from "./pages/Share";
import { ToastProvider } from "./ui";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, staleTime: 5_000 } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          {/* 공유 링크(/share/토큰)는 로그인 없이 연다 — 수요처가 받은 주소 */}
          {window.location.pathname.startsWith("/share/") ? (
            <SharePage />
          ) : (
            <AuthGate>
              <App />
            </AuthGate>
          )}
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
