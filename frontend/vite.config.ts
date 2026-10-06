import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 개발 서버는 /api 를 백엔드(기본 8000)로 넘긴다. 운영에서는 nginx 가 같은 일을 한다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.FDE_API_TARGET || "http://127.0.0.1:8000", changeOrigin: true } },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 900 },
});
