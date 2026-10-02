import { lazy, Suspense } from "react";
import { Outlet, Route, Routes } from "react-router-dom";
import { Footer } from "./components/Footer";
import { HealthBanner } from "./components/HealthBanner";
import { TopBar } from "./components/TopBar";
import { GamesPage } from "./pages/GamesPage";
import { ModelPage } from "./pages/ModelPage";
import { SearchPage } from "./pages/SearchPage";
import { ReviewPage } from "./pages/review/ReviewPage";
import styles from "./App.module.css";

const DevComponents = import.meta.env.DEV ? lazy(() => import("./pages/DevComponents")) : null;

function Shell() {
  return (
    <>
      <TopBar />
      <HealthBanner />
      <main className={styles.main}>
        <Outlet />
      </main>
      <Footer />
    </>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={<SearchPage />} />
        <Route path="/p/:platform/:name/:tag" element={<GamesPage />} />
        <Route path="/review/:matchId" element={<ReviewPage />} />
        <Route path="/model" element={<ModelPage />} />
        {DevComponents && (
          <Route
            path="/dev/components"
            element={
              <Suspense fallback={null}>
                <DevComponents />
              </Suspense>
            }
          />
        )}
      </Route>
    </Routes>
  );
}
