import { useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import type { PlayerGames } from "../api/models";
import { useHealth, useModel } from "../api/queries";
import { ErrorBox } from "../components/ErrorBox";
import { Panel } from "../components/Panel";
import { Skeleton } from "../components/Skeleton";
import { AccuracyChart } from "./model/AccuracyChart";
import { CalibrationChart } from "./model/CalibrationChart";
import { FeatureChart } from "./model/FeatureChart";
import { readMetrics } from "./model/metrics";
import { Summary } from "./model/Summary";
import { TierTable } from "./model/TierTable";
import styles from "./model/model.module.css";

const DEFAULT_TIER = "GOLD";

/** The tier of the last player looked up this session, or Gold. */
function useYourTier(): string {
  const queryClient = useQueryClient();
  const hits = queryClient.getQueriesData<InfiniteData<PlayerGames>>({ queryKey: ["player"] });
  for (const [, data] of hits) {
    const tier = data?.pages[0]?.rank?.tier;
    if (tier) return tier;
  }
  return DEFAULT_TIER;
}

function NoModel() {
  return (
    <Panel className={styles.noModel}>
      <p>
        No trained model yet; the app is using a placeholder. Train on Kaggle (Plan Step 10) and put{" "}
        <code className={styles.code}>model.txt</code> and{" "}
        <code className={styles.code}>metrics.json</code> in{" "}
        <code className={styles.code}>models/</code>.
      </p>
    </Panel>
  );
}

const isMissing = (e: unknown) =>
  e instanceof ApiError && (e.code === "model_missing" || e.code === "no_model");

export function ModelPage() {
  const model = useModel();
  const health = useHealth();
  const yourTier = useYourTier();
  const stub = health.data?.model.kind === "stub";

  let intro = null;
  let body;
  if (stub || (model.isError && isMissing(model.error))) {
    body = <NoModel />;
  } else if (model.isError) {
    body = <ErrorBox error={model.error} onRetry={() => void model.refetch()} />;
  } else if (model.isPending) {
    intro = <Skeleton height={48} />;
    body = (
      <div className={styles.grid} aria-label="Loading model details">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} height={340} />
        ))}
      </div>
    );
  } else {
    const view = readMetrics(model.data);
    intro = <Summary view={view} />;
    body = (
      <>
        <div className={styles.grid}>
          {view.minutes.length > 0 && <AccuracyChart rows={view.minutes} />}
          {view.calibration.length > 0 && (
            <CalibrationChart rows={view.calibration} nearest70={view.nearest70} />
          )}
          {view.tiers.length > 0 && <TierTable rows={view.tiers} yourTier={yourTier} />}
          {view.features.length > 0 && <FeatureChart rows={view.features} />}
        </div>
      </>
    );
  }

  return (
    <div>
      <div className={styles.intro}>
        <h1 className={styles.heading}>How much to trust the numbers</h1>
        {intro}
      </div>
      {body}
    </div>
  );
}
