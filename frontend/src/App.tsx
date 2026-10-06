import { Navigate, Route, Routes } from "react-router-dom";
import { AdminPage } from "./pages/Admin";
import { AssetsPage } from "./pages/Assets";
import { CatalogPage } from "./pages/Catalog";
import { HomePage } from "./pages/Home";
import { Header } from "./shell/Header";
import { Step1 } from "./studio/Step1";
import { Step2 } from "./studio/Step2";
import { Step3 } from "./studio/Step3";
import { Step4 } from "./studio/Step4";
import { Step5 } from "./studio/Step5";
import { Step6 } from "./studio/Step6";
import { Step7 } from "./studio/Step7";
import { Step8 } from "./studio/Step8";
import { StudioIndex, StudioLayout } from "./studio/StudioLayout";
import { useParams } from "react-router-dom";

const STEPS = [Step1, Step2, Step3, Step4, Step5, Step6, Step7, Step8];

function StepRoute() {
  const n = Math.max(1, Math.min(8, Number(useParams().step) || 1));
  const Comp = STEPS[n - 1];
  return <Comp />;
}

/** 스튜디오 밖의 평면(홈·패브릭·카탈로그·관리)은 사이드바 없이 본문만 스크롤한다. */
function Plane({ children }: { children: React.ReactNode }) {
  return (
    <div className="body">
      <main className="main no-bar">{children}</main>
    </div>
  );
}

export function App() {
  return (
    <div className="app">
      <Header />
      <Routes>
        <Route path="/" element={<Plane><HomePage /></Plane>} />
        <Route path="/assets" element={<Plane><AssetsPage /></Plane>} />
        <Route path="/catalog" element={<Plane><CatalogPage /></Plane>} />
        <Route path="/catalog/:rid" element={<Plane><CatalogPage /></Plane>} />
        <Route path="/admin" element={<Plane><AdminPage /></Plane>} />
        <Route path="/studio" element={<div className="body"><StudioIndex /></div>} />
        <Route path="/studio/:pid" element={<StudioLayout />}>
          <Route index element={<Navigate to="step/1" replace />} />
          <Route path="step/:step" element={<StepRoute />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
