import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { Footer } from "./components/Footer";
import { HealthBanner } from "./components/HealthBanner";
import { TopBar } from "./components/TopBar";
import { GamesPage } from "./pages/GamesPage";
import { ModelPage } from "./pages/ModelPage";
import { SearchPage } from "./pages/SearchPage";
import { WorldsPage } from "./pages/WorldsPage";
import { ReviewPage } from "./pages/review/ReviewPage";
import styles from "./App.module.css";

const DevComponents = import.meta.env.DEV ? lazy(() => import("./pages/DevComponents")) : null;

const DevBoard = import.meta.env.DEV ? lazy(() => import("./pages/DevBoard")) : null;

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
        {/* The saved-games demo's id for this game, from links shared before the site went live. */}
        <Route
          path="/review/NA1_1000000004"
          element={<Navigate to="/review/NA1_5650873814?p=1" replace />}
        />
        <Route path="/worlds" element={<WorldsPage />} />
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
        {DevBoard && (
          <Route
            path="/dev/board"
            element={
              <Suspense fallback={null}>
                <DevBoard />
              </Suspense>
            }
          />
        )}
      </Route>
    </Routes>
  );
}
